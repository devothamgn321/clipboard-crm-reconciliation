"""READ-ONLY diagnosis of the interrupted approval. Sends GET requests only. Writes nothing."""
import getpass, json, os, sqlite3, sys
import httpx

PID_PREFIX = sys.argv[1] if len(sys.argv) > 1 else "2a00190c03cc"
DB = os.environ.get("CRM_DB", "runtime/reconciliation.sqlite3")
token = os.environ.get("CRM_API_TOKEN") or getpass.getpass("CRM API token (read-only use): ")
api = httpx.Client(base_url="https://analyst-assessment-production.up.railway.app/api/v1/",
                   headers={"Authorization": "Bearer " + token}, timeout=25)

db = sqlite3.connect(DB); db.row_factory = sqlite3.Row
row = db.execute("SELECT id, status, body FROM proposals WHERE id LIKE ?", (PID_PREFIX + "%",)).fetchone()
p = json.loads(row["body"])
print("PROPOSAL :", row["id"][:12], "|", p["classification"], "|", p["facility"]["name"], "| status:", row["status"])
ops = {r["step"]: (r["state"], json.loads(r["body"])) for r in db.execute("SELECT * FROM operations WHERE proposal_id=?", (row["id"],))}
for step, (state, body) in ops.items():
    print(f"\nOP {step} [{state}]:", json.dumps(body, indent=1)[:2500])

def diff(label, expected, actual):
    print(f"\n{label}")
    if not isinstance(actual, dict):
        print("  Response is not an account object:", str(actual)[:500]); return
    if "account_id" not in actual:
        print("  No account_id at top level. Keys:", list(actual)[:15])
    bad = {k: (v, actual.get(k)) for k, v in expected.items() if actual.get(k) != v}
    for k, (want, got) in bad.items():
        print(f"  MISMATCH {k}: expected {want!r} | got {got!r}")
    if not bad:
        print("  All expected fields match.")

if "create" in ops:
    state, body = ops["create"]
    request = body.get("request", {})
    new_id = body.get("account_id") or (body.get("response") or {}).get("account_id")
    if new_id:
        diff(f"CREATED ACCOUNT {new_id} (live GET) vs request", request, api.get(f"accounts/{new_id}").json())
    else:
        print("\nNo account_id recorded. Searching live inventory for the reference marker...")
        hits, page = [], 1
        while True:
            data = api.get("accounts", params={"page": page, "page_size": 100}).json()
            hits += [a for a in data["data"] if row["id"] in (a.get("note") or "")]
            if page * 100 >= data["total"]: break
            page += 1
        print("  Accounts carrying this proposal's marker:", [(a["account_id"], a["name"]) for a in hits])
if p.get("current"):
    cur = p["current"]
    expected = {k: v for k, v in cur.items() if k != "account_id"}
    if p["classification"] != "chow_required":
        expected.update(p["changes"])
    diff(f"EXISTING ACCOUNT {cur['account_id']} (live GET) vs expected", expected, api.get(f"accounts/{cur['account_id']}").json())
