"""Terminal review for the pending queue.

Same approval path as the web app (service.apply / service.reject): fresh crawl,
fresh CRM read, fingerprint match, billing re-check, write, GET read-back.
You decide every item. It stops at the first failure.

  .venv/bin/python review.py
"""
import os
import sys

from reconciliation import service
from reconciliation.store import Store

REVIEWER = "Devothama Gundugurki Narasimhamurthy"

# Order matters: Marietta proves the last untested write type first;
# Kettering's survivor must be under Bellhaven before its duplicates.
ORDER = ["chow_required", "direct_reparent", "duplicate", "field_update", "missing_account",
         "stale_needs_review", "ambiguous"]

RATIONALE = {
    "chow_required": "Revenue and AR both > 0: new Bellhaven account created, old account preserved and linked via chow_current_account per SOP.",
    "direct_reparent": "Listed on Bellhaven website; no revenue history or zero AR, so SOP allows direct re-parent.",
    "duplicate": "Same normalized address as the surviving account; losing copy has $0 revenue and $0 AR. Marked Inactive with duplicate_of_account.",
    "field_update": "Website shows the current name/ZIP for this confirmed match.",
    "missing_account": "Community listed on Bellhaven website with no matching CRM account.",
    "stale_needs_review": "Under Bellhaven in CRM but absent from the complete website crawl. Flagged Needs Review; parent and billing left untouched.",
    "ambiguous": "Confirmed on website under Bellhaven; PO Box is a valid billing address. Keep Active, no identity change.",
}
# Recommended action per class. Ashtabula is the one real judgment call.
DEFAULT_ACTION = {"ambiguous": "r"}


def name_of(p):
    return (p.get("facility") or {}).get("name") or (p.get("current") or {}).get("name") or p["id"][:12]


def city_of(p):
    return (p.get("facility") or {}).get("city") or (p.get("current") or {}).get("billing_city")


def sort_key(p):
    kind = p["classification"]
    first = 0
    if kind == "chow_required" and "Marietta" in name_of(p):
        first = -1
    if kind == "direct_reparent" and city_of(p) == "Kettering":
        first = -1
    return (ORDER.index(kind) if kind in ORDER else 99, first, name_of(p))


def money(v):
    try:
        return f"${float(v):,.0f}"
    except (TypeError, ValueError):
        return str(v)


def show(p, n, total):
    cur = p.get("current") or {}
    print("\n" + "=" * 78)
    print(f"[{n}/{total}] {p['classification'].upper()}  |  {name_of(p)}  |  {p['id'][:12]}")
    f = p.get("facility")
    if f:
        print(f"  Website : {f.get('address')}, {f.get('city')}, {f.get('state')} {f.get('zip')}")
    else:
        print("  Website : not listed")
    if cur:
        print(f"  CRM     : {cur.get('account_id')}  {cur.get('name')}  |  {cur.get('billing_street')}, {cur.get('billing_zip')}")
        print(f"  Parent  : {cur.get('parent_id') or '(none)'}  |  status {cur.get('status')}  |  "
              f"revenue {money(cur.get('lifetime_revenue'))}  AR {money(cur.get('outstanding_ar'))}")
    if p.get("survivor_id"):
        print(f"  Survivor: {p['survivor_id']}")
    changes = {k: (v if len(str(v)) < 70 else str(v)[:67] + "...") for k, v in (p.get("changes") or {}).items()}
    print(f"  Writes  : {changes}")
    for r in p.get("reasons") or []:
        print(f"   - {r}")


def after_check(crm, p):
    """Extra confirmation for CHOW, printed from a fresh GET."""
    if p["classification"] != "chow_required" or not hasattr(crm, "get"):
        return
    old = crm.get(p["current"]["account_id"])
    new_id = old.get("chow_current_account")
    new = crm.get(new_id) if new_id else {}
    same = all(old.get(k) == p["current"].get(k) for k in ("parent_id", "lifetime_revenue", "outstanding_ar", "status", "name"))
    print(f"  CHOW check: old parent {old.get('parent_id')} | revenue {money(old.get('lifetime_revenue'))} "
          f"AR {money(old.get('outstanding_ar'))} | unchanged={same}")
    print(f"              new account {new_id} under {new.get('parent_id')} ({new.get('parent_name')})")
    if not same or not new_id:
        raise SystemExit("CHOW check failed. Stop and send this output.")


def main(store=None, crm=None, scraper=None, ask=input):
    store = store or Store(os.environ.get("CRM_DB", "runtime/reconciliation.sqlite3"))
    pending = sorted([p for p in store.proposals() if p["status"] == "pending_review"], key=sort_key)
    blocked = [p for p in store.proposals() if p["status"] in ("applying", "recovery_required")]
    if blocked:
        sys.exit(f"Queue locked by {blocked[0]['id'][:12]} ({blocked[0]['status']}). Resolve that first.")
    if not pending:
        print("Nothing pending.")
        return {}

    own_crm = crm is None
    if own_crm:
        from reconciliation.crm import CRM
        crm = CRM()
    kwargs = {"crm": crm}
    if scraper:
        kwargs["scraper"] = scraper

    print(f"{len(pending)} pending. Keys: Enter = recommended, a = approve, r = reject, s = skip, q = quit")
    results = {"approved": [], "rejected": [], "skipped": []}
    try:
        for n, p in enumerate(pending, 1):
            show(p, n, len(pending))
            default = DEFAULT_ACTION.get(p["classification"], "a")
            label = {"a": "approve", "r": "reject"}[default]
            choice = (ask(f"  Action [Enter={label}] a/r/s/q: ").strip().lower() or default)[:1]
            if choice == "q":
                break
            if choice == "s":
                results["skipped"].append(name_of(p))
                continue
            rationale = RATIONALE.get(p["classification"], "Reviewed evidence.")
            custom = ask("  Rationale [Enter=default]: ").strip()
            rationale = custom or rationale
            if choice == "r":
                service.reject(store, p["id"], REVIEWER, rationale)
                print("  REJECTED (no CRM call)")
                results["rejected"].append(name_of(p))
                continue
            try:
                service.apply(store, p["id"], REVIEWER, rationale, **kwargs)
            except Exception as error:  # stop at first failure, never continue past it
                status = store.get(p["id"])["status"]
                print(f"\n  STOPPED: {type(error).__name__}: {error}\n  Proposal status: {status}")
                print("  Send this output before doing anything else.")
                break
            print("  APPLIED and verified by read-back")
            after_check(crm, p)
            results["approved"].append(name_of(p))
    finally:
        if own_crm:
            crm.close()

    statuses = {}
    for p in store.proposals():
        statuses[p["status"]] = statuses.get(p["status"], 0) + 1
    print("\nDONE:", {k: len(v) for k, v in results.items()}, "| queue:", statuses)
    print("Next: .venv/bin/python -m reconciliation reconcile   (expect new_proposals: 0)")
    return results


if __name__ == "__main__":
    main()
