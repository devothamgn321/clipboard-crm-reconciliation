"""Deterministic proposal generation. This module cannot write to the CRM."""

import hashlib
import json
from collections import Counter

from .normalize import address, chow_required, money, text

POLICY = "2026-09-17.v1"
FIELDS = (
    "account_id",
    "name",
    "parent_id",
    "billing_street",
    "billing_city",
    "billing_state",
    "billing_zip",
    "care_type",
    "status",
    "phone",
    "lifetime_revenue",
    "outstanding_ar",
    "chow_current_account",
    "duplicate_of_account",
    "note",
)


def material(a):
    return {k: a.get(k) for k in FIELDS} if a else None


def fingerprint(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def parent_account(accounts):
    matches = [
        a
        for a in accounts
        if text(a["name"]) == "bellhaven senior living parent account"
        and not a["parent_id"]
    ]
    if len(matches) != 1 or matches[0]["status"] != "Active":
        raise ValueError("Unique active Bellhaven parent not found")
    return matches[0]["account_id"]


def care(f):
    mapping = {
        "Assisted Living": "Assisted Living",
        "Memory Support": "Memory Care",
        "Short-Term Rehabilitation & Nursing": "Skilled Nursing",
    }
    return mapping.get(f["care_offerings"][0], f["care_offerings"][0])


def create_fields(f, parent):
    return {
        "name": f["name"],
        "parent_id": parent,
        "billing_street": f["address"],
        "billing_city": f["city"],
        "billing_state": f["state"],
        "billing_zip": f["zip"],
        "care_type": care(f),
        "status": "Active",
        "note": "Website care offerings: "
        + ", ".join(f["care_offerings"])
        + ". Source: "
        + f["url"],
    }


def proposal(kind, f, a, changes, reasons, confidence, parent, survivor=None):
    p = dict(
        policy=POLICY,
        classification=kind,
        facility=f,
        current=material(a),
        changes=changes,
        reasons=reasons,
        confidence=confidence,
        parent_id=parent,
        survivor_id=survivor,
    )
    p["id"] = fingerprint(p)
    p["entity"] = a["account_id"] if a else f["url"]
    p["status"] = "pending_review"
    return p


def needs_review(kind, f, a, reason, parent):
    note = (a.get("note") or "").strip()
    if reason not in note:
        note = (note + "\n" + reason).strip()
    changes = {
        k: v
        for k, v in {"status": "Needs Review", "note": note}.items()
        if a.get(k) != v
    }
    return proposal(kind, f, a, changes, [reason], 0.55, parent) if changes else None


def reconcile(facilities, accounts):
    parent = parent_account(accounts)
    proposals = []
    findings = []
    covered = set()
    by_id = {a["account_id"]: a for a in accounts}
    # Retain historical CHOW accounts and completed duplicate markers; do not resurrect them.
    historical = {
        a["account_id"]
        for a in accounts
        if a.get("chow_current_account") in by_id
        and address(a) == address(by_id[a["chow_current_account"]])
        and by_id[a["chow_current_account"]]["parent_id"] == parent
    }
    usable = [
        a
        for a in accounts
        if a["account_id"] != parent
        and not a.get("duplicate_of_account")
        and a["account_id"] not in historical
    ]
    for f in facilities:
        key = address(f)
        exact = [a for a in usable if all(key) and address(a) == key]
        # A single ZIP typo is repairable only with exact street, city, state AND name.
        zip_matches = (
            [
                a
                for a in usable
                if address(a)[:3] == key[:3] and text(a["name"]) == text(f["name"])
            ]
            if not exact
            else []
        )
        candidates = exact or zip_matches
        if not candidates:
            possible = [
                a
                for a in usable
                if address(a)[1:3] == key[1:3] and text(a["name"]) == text(f["name"])
            ]
            if possible:
                for a in possible:
                    covered.add(a["account_id"])
                    p = needs_review(
                        "ambiguous",
                        f,
                        a,
                        "Website name and locality match, but street differs. Verify mailing versus physical address before changing ownership or billing address.",
                        parent,
                    )
                    if p:
                        proposals.append(p)
                findings.append(
                    {
                        "facility": f,
                        "classification": "ambiguous",
                        "account_ids": [a["account_id"] for a in possible],
                    }
                )
            else:
                proposals.append(
                    proposal(
                        "missing_account",
                        f,
                        None,
                        create_fields(f, parent),
                        [
                            "No exact address or same-name/locality candidate in complete CRM inventory; similar names at different addresses are not identity evidence."
                        ],
                        0.9,
                        parent,
                    )
                )
                findings.append(
                    {
                        "facility": f,
                        "classification": "missing_account",
                        "account_ids": [],
                    }
                )
            continue
        covered.update(a["account_id"] for a in candidates)
        candidates = sorted(
            candidates,
            key=lambda a: (
                -float(money(a["lifetime_revenue"])),
                -float(money(a["outstanding_ar"])),
                a["parent_id"] != parent,
                a["status"] != "Active",
                a["account_id"],
            ),
        )
        if len(candidates) > 1 and (
            sum(
                money(a["lifetime_revenue"]) > 0 or money(a["outstanding_ar"]) > 0
                for a in candidates
            )
            > 1
            or len({a["care_type"] for a in candidates}) > 1
            or any(a.get("chow_current_account") for a in candidates)
        ):
            for a in candidates:
                p = needs_review(
                    "ambiguous",
                    f,
                    a,
                    "Multiple address matches with conflicting care, billing histories, or CHOW links. Resolve identity before duplicate or ownership changes.",
                    parent,
                )
                if p:
                    proposals.append(p)
            findings.append(
                {
                    "facility": f,
                    "classification": "ambiguous",
                    "account_ids": [a["account_id"] for a in candidates],
                }
            )
            continue
        a = candidates[0]
        reasons = [
            "Exact normalized street, city and state.",
            "Exact ZIP."
            if exact
            else "Name also matches exactly; ZIP differs and will be corrected.",
        ]
        if len(candidates) > 1:
            reasons.append(
                "Duplicate survivor ranked by billing history, Bellhaven parent, active status, then stable account ID; losing copies have zero revenue and AR."
            )
        duplicate_reasons = list(reasons)
        changes = {}
        if a["name"] != f["name"]:
            changes["name"] = f["name"]
        if not exact:
            changes["billing_zip"] = f["zip"]
        if a["status"] != "Active":
            changes["status"] = "Active"
        kind = "field_update"
        if a["parent_id"] != parent:
            if chow_required(a):
                kind = "chow_required"
                changes = create_fields(f, parent)
                reasons.append(
                    "Revenue > 0 AND AR > 0: preserve old account; create successor; link old.chow_current_account to successor."
                )
            else:
                kind = "direct_reparent"
                changes["parent_id"] = parent
                reasons.append(
                    "No revenue history OR zero outstanding AR: direct re-parent allowed."
                )
        if a.get("chow_current_account"):
            p = needs_review(
                "ambiguous",
                f,
                a,
                "Existing CHOW link cannot be safely resolved; verify linked account before any mutation.",
                parent,
            )
            kind = "ambiguous"
        else:
            p = (
                proposal(kind, f, a, changes, reasons, 0.99 if exact else 0.94, parent)
                if changes
                else None
            )
        if p:
            proposals.append(p)
        findings.append(
            {
                "facility": f,
                "classification": kind if p else "unchanged",
                "account_ids": [a["account_id"]],
            }
        )
        for loser in candidates[1:]:
            note = (loser.get("note") or "").strip()
            note = (
                note
                + "\nDuplicate at the same normalized address. Survivor: "
                + a["account_id"]
                + ". Billing history preserved; no merge or delete."
            ).strip()
            proposals.append(
                proposal(
                    "duplicate",
                    f,
                    loser,
                    {
                        "duplicate_of_account": a["account_id"],
                        "status": "Inactive",
                        "note": note,
                    },
                    duplicate_reasons
                    + [
                        f"Losing copy points to {a['account_id']}; parent and billing fields stay unchanged."
                    ],
                    0.98,
                    parent,
                    a["account_id"],
                )
            )
    for a in accounts:
        if (
            a["parent_id"] == parent
            and a["account_id"] not in covered | historical
            and not a.get("duplicate_of_account")
        ):
            p = needs_review(
                "stale_needs_review",
                None,
                a,
                "Absent from the complete Bellhaven website crawl. Ownership is unresolved; preserve parent and billing history pending investigation.",
                parent,
            )
            if p:
                proposals.append(p)
    coverage = []
    for a in accounts:
        aid = a["account_id"]
        related = [
            p for p in proposals if p["current"] and p["current"]["account_id"] == aid
        ]
        matches = [f for f in findings if aid in f["account_ids"]]
        if aid == parent:
            disposition, reason = (
                "bellhaven_parent",
                "Verified corporate parent; excluded from facility matching.",
            )
        elif "parent account" in text(a["name"]):
            disposition, reason = (
                "other_parent",
                "Corporate reference used to interpret current ownership.",
            )
        elif related:
            disposition, reason = (
                related[0]["classification"],
                "; ".join(related[0]["reasons"]),
            )
        elif aid in historical:
            disposition, reason = (
                "historical_chow",
                "Preserved billing-history account with a valid Bellhaven successor.",
            )
        elif a.get("duplicate_of_account"):
            disposition, reason = (
                "marked_duplicate",
                "Existing duplicate marker retained; not treated as a missing facility.",
            )
        elif matches:
            disposition, reason = (
                "matched_no_change",
                "Matched website facility; no new mutation needed.",
            )
        elif a["parent_id"] == parent:
            disposition, reason = (
                "already_flagged",
                "Unresolved website absence already flagged; no repeated note or status proposal.",
            )
        else:
            disposition, reason = (
                "unrelated",
                "Compared against all website identities; no supported Bellhaven match and not a Bellhaven child. Left unchanged.",
            )
        coverage.append(
            {
                "account_id": aid,
                "name": a["name"],
                "disposition": disposition,
                "reason": reason,
                "proposal_ids": [p["id"] for p in related],
                "facility_urls": [f["facility"]["url"] for f in matches],
                "considered": True,
            }
        )
    return {
        "account_coverage": coverage,
        "accounts_considered": len(coverage),
        "coverage_counts": dict(Counter(a["disposition"] for a in coverage)),
        "parent_id": parent,
        "website_facilities": len(facilities),
        "crm_accounts": len(accounts),
        "current_bellhaven_children": sum(a["parent_id"] == parent for a in accounts),
        "classification_counts": dict(Counter(p["classification"] for p in proposals)),
        "facility_classification_counts": dict(
            Counter(f["classification"] for f in findings)
        ),
        "proposals": proposals,
        "findings": findings,
    }
