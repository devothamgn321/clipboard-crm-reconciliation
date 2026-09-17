"""1) Patch service.py: stop requiring the API's write RESPONSE to echo every field
      (it only returns {account_id, message}). The GET read-back check stays.
   2) Re-verify Amberly Manor live (GET only) and, only if it matches, record the
      stuck proposal as applied via manual recovery. No CRM writes.
Run with the review server STOPPED."""
import getpass, json, os, pathlib, sys
import httpx

# ---------- 1) patch ----------
path = pathlib.Path("reconciliation/service.py")
src = path.read_text()
replacements = [
    ("            verify(created, payload)\n", ""),
    ("                verify(response, expected)\n                verify(crm.get(current[\"account_id\"]), expected)",
     "                verify(crm.get(current[\"account_id\"]), expected)"),
    ("            verify(response, expected)\n            verify(crm.get(current[\"account_id\"]), expected)",
     "            verify(crm.get(current[\"account_id\"]), expected)"),
]
changed = 0
for old, new in replacements:
    if old in src:
        src = src.replace(old, new, 1); changed += 1
if changed:
    path.write_text(src)
print(f"service.py: {changed} response-echo checks removed (read-back checks kept)")

tpath = pathlib.Path("tests/test_service.py")
if tpath.exists():
    t = tpath.read_text()
    old_t = """    def bad(aid, changes):
        result = original(aid, changes)
        result["parent_id"] = "wrong"
        return result
"""
    new_t = """    def bad(aid, changes):
        original(aid, changes)
        # CRM persists a wrong value: the GET read-back must catch it
        return original(aid, {"parent_id": "wrong"})
"""
    if old_t in t:
        tpath.write_text(t.replace(old_t, new_t, 1))
        print("tests: corrupt-write test now corrupts the stored record (read-back must catch it)")

# ---------- 2) recover ----------
if "--patch-only" in sys.argv:
    sys.exit(0)
from reconciliation.store import Store
PID_PREFIX = "2a00190c03cc"
store = Store(os.environ.get("CRM_DB", "runtime/reconciliation.sqlite3"))
pid = next(p["id"] for p in store.proposals() if p["id"].startswith(PID_PREFIX))
p = store.get(pid)
if p["status"] != "recovery_required":
    sys.exit(f"Proposal is '{p['status']}', not recovery_required. Nothing to recover.")
ops = store.operations(pid)
new_id = ops["create"]["account_id"]
request = ops["create"]["request"]

token = os.environ.get("CRM_API_TOKEN") or getpass.getpass("CRM API token (read-only use): ")
live = httpx.get(f"https://analyst-assessment-production.up.railway.app/api/v1/accounts/{new_id}",
                 headers={"Authorization": "Bearer " + token}, timeout=25).json()
bad = {k: (v, live.get(k)) for k, v in request.items() if live.get(k) != v}
if bad:
    sys.exit(f"Live account does NOT match, not recovering: {json.dumps(bad, indent=1)}")

store.transition(pid, {"recovery_required"}, "applied", "manual_recovery_verified", {
    "reviewer": "Devothama Gundugurki Narasimhamurthy",
    "rationale": "Create succeeded (account_id returned). API returns only {account_id, message}, "
                 "so response-echo check failed. Live GET read-back matched every requested field.",
    "verified_account_ids": [new_id],
})
print(f"Recovered: {p['facility']['name']} -> account {new_id} marked applied. Queue unlocked.")
