"""Read-only pipeline and the sole human-authorized write path."""

from .crm import CRM
from .normalize import address, chow_required, money
from .rules import material, reconcile
from .scraper import scrape
from .store import Conflict, now


def run(store, crm=None, scraper=scrape):
    own = crm is None
    crm = crm or CRM()
    try:
        source = scraper()
        accounts = crm.accounts()
        report = reconcile(source["facilities"], accounts)
        report["crawl"] = {
            "pages": source["pages"],
            "homepage_expected": source["homepage_expected"],
        }
        report["crm_snapshot"] = accounts
        report["crm_read_receipts"] = getattr(crm, "read_receipts", [])
        return store.save_run(report)
    finally:
        if own:
            crm.close()


def verify(actual, expected):
    if (
        not isinstance(actual, dict)
        or not actual.get("account_id")
        or any(actual.get(k) != v for k, v in expected.items())
    ):
        raise Conflict(
            "CRM response/read-back does not match the approved fields; inspect audit before recovery"
        )


def apply(store, pid, reviewer, rationale, crm=None, scraper=scrape):
    if not reviewer.strip() or not rationale.strip():
        raise ValueError("Reviewer and rationale are required")
    p = store.get(pid)
    if p["status"] != "pending_review":
        raise Conflict("Only a pending proposal can be approved")
    own = crm is None
    crm = crm or CRM()
    claimed = False
    sent = False
    try:
        # Reserve before slow checks to prevent concurrent pipeline/approval races.
        p = store.transition(
            pid,
            {"pending_review"},
            "applying",
            "approval_started",
            {"reviewer": reviewer, "rationale": rationale, "at": now()},
        )
        claimed = True
        source = scraper()
        accounts = crm.accounts()
        fresh = reconcile(source["facilities"], accounts)
        if pid not in {x["id"] for x in fresh["proposals"]}:
            raise Conflict(
                "Website, CRM, match candidates or billing changed. Rerun reconciliation and review the new proposal."
            )
        current = p["current"]
        if current:
            live = crm.get(current["account_id"])
            if material(live) != current:
                raise Conflict(
                    "Account changed after inventory read; rerun reconciliation"
                )
        if p["classification"] == "direct_reparent" and chow_required(live):
            raise Conflict("CHOW required; direct parent update blocked")
        if p["classification"] == "chow_required" and not chow_required(live):
            raise Conflict("CHOW safety interpretation changed")
        if p["classification"] == "duplicate":
            survivor = crm.get(p["survivor_id"])
            if (
                survivor["parent_id"] != p["parent_id"]
                or survivor["status"] != "Active"
                or survivor.get("duplicate_of_account")
                or survivor.get("chow_current_account")
                or address(survivor) != address(live)
            ):
                raise Conflict(
                    "Approve the survivor correction first; survivor must be active under Bellhaven at the same address"
                )
            if money(live["lifetime_revenue"]) or money(live["outstanding_ar"]):
                raise Conflict(
                    "Losing duplicate has billing history; manual investigation required"
                )
        store.operation(
            pid,
            "preflight",
            "verified",
            {"source_pages": source["pages"], "current": current},
        )
        kind = p["classification"]
        if kind in ("missing_account", "chow_required"):
            # Marker allows read-only recovery after a response timeout; NEVER retry POST automatically.
            payload = {
                **p["changes"],
                "note": p["changes"]["note"] + "\nReconciliation reference: " + pid,
            }
            store.operation(pid, "create", "intent", {"request": payload})
            sent = True
            created = crm.create(payload)
            if not isinstance(created, dict) or not created.get("account_id"):
                raise Conflict("Create returned no account_id")
            store.operation(
                pid,
                "create",
                "response",
                {
                    "request": payload,
                    "response": created,
                    "account_id": created["account_id"],
                },
            )
            verify(crm.get(created["account_id"]), payload)
            store.operation(
                pid,
                "create",
                "verified",
                {"request": payload, "account_id": created["account_id"]},
            )
            if kind == "chow_required":
                old = crm.get(current["account_id"])
                if material(old) != current or not chow_required(old):
                    raise Conflict(
                        "Old account changed during CHOW; successor created, old account untouched. Recover manually."
                    )
                patch = {"chow_current_account": created["account_id"]}
                store.operation(
                    pid,
                    "link",
                    "intent",
                    {"account_id": current["account_id"], "request": patch},
                )
                response = crm.patch(current["account_id"], patch)
                expected = {k: v for k, v in current.items() if k != "account_id"}
                expected.update(patch)
                verify(crm.get(current["account_id"]), expected)
                store.operation(
                    pid, "link", "verified", {"request": patch, "response": response}
                )
        else:
            store.operation(
                pid,
                "patch",
                "intent",
                {"account_id": current["account_id"], "request": p["changes"]},
            )
            sent = True
            response = crm.patch(current["account_id"], p["changes"])
            expected = {k: v for k, v in current.items() if k != "account_id"}
            expected.update(p["changes"])
            verify(crm.get(current["account_id"]), expected)
            store.operation(
                pid,
                "patch",
                "verified",
                {"request": p["changes"], "response": response},
            )
        return store.transition(
            pid,
            {"applying"},
            "applied",
            "approval_applied",
            {"reviewer": reviewer, "rationale": rationale, "verified": True},
        )
    except Exception as exc:
        if claimed:
            # Do not persist exception strings that could contain credentials or request headers.
            store.transition(
                pid,
                {"applying"},
                "recovery_required" if sent else "pending_review",
                "approval_interrupted",
                {
                    "error_type": type(exc).__name__,
                    "write_may_have_occurred": sent,
                    "reviewer": reviewer,
                },
            )
        raise
    finally:
        if own:
            crm.close()


def reject(store, pid, reviewer, rationale):
    if not reviewer.strip() or not rationale.strip():
        raise ValueError("Reviewer and rationale are required")
    return store.transition(
        pid,
        {"pending_review"},
        "rejected",
        "human_rejected",
        {"reviewer": reviewer, "rationale": rationale, "at": now()},
    )
