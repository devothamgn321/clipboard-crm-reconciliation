# Clipboard CRM Reconciliation

A local review console that reconciles Bellhaven's website with the Clipboard assessment CRM. FastAPI, SQLite, deterministic matching, durable decisions, and an audit trail. **Every CRM mutation requires an individual human approval.**

**Delivered state:** 35 website facilities, 121 CRM accounts, 29 Bellhaven children, 29 pending proposals. All 121 CRM records have an explicit disposition in the All CRM accounts tab and `docs/account-coverage.json`. No live CRM mutations were made during development. The second live pipeline run generated zero new proposals. The assessment evaluates corrected CRM data, so the candidate must review and approve appropriate proposals before submitting.

## Run on this machine

The project already has an installed `.venv` and a live-generated SQLite queue in `runtime/`. From this project's directory:

```sh
# Enter your assessment token privately; it is passed only through the environment.
export CRM_API_TOKEN="$(python3 -c 'import getpass; print(getpass.getpass("CRM API token: "))')"
.venv/bin/python -m reconciliation scrape
.venv/bin/python -m reconciliation reconcile
.venv/bin/python -m reconciliation serve
```

Open http://127.0.0.1:8000. If the delivered server is still running, use it directly or stop that server before launching another on the same port. `serve --port 8002` selects another port.

- `scrape` writes all locations and page hashes to `runtime/website.json`; it never accesses CRM writes.
- `reconcile` reads the website and every CRM page, saves proposals and the run snapshot to SQLite, and exports `runtime/latest-report.json`.
- `serve` starts the local UI. Starting the server does not run or approve anything.
- `summary` prints the latest run counts and current decision statuses.

`CRM_API_TOKEN` is the only credential. `.env.example` documents it; `.env` files are not automatically loaded. The app never persists the token. The default database is `runtime/reconciliation.sqlite3`; set `CRM_DB` to change it. Keep the same database across daily runs and reviews.

## Fresh setup / portable source archive

Requires Python 3.10+; tested on Python 3.12. The macOS system Python 3.9 is insufficient for installing this project.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
export CRM_API_TOKEN="$(python3 -c 'import getpass; print(getpass.getpass("CRM API token: "))')"
.venv/bin/python -m reconciliation reconcile
.venv/bin/python -m reconciliation serve
```

For a credential-free, offline **inspection** demo, use the captured fictional assessment data:

```sh
CRM_DB=runtime/demo.sqlite3 .venv/bin/python -m reconciliation demo
CRM_DB=runtime/demo.sqlite3 .venv/bin/python -m reconciliation serve --port 8002
```

Do not supply a token for an offline demo. Reject decisions are local; approvals always require the token and fresh live evidence, even for snapshot-generated proposals. Mock write testing is in pytest, not a hidden fake-success UI mode.

## Review walkthrough

1. Check the top-line inventory: 35 website facilities and 29 current Bellhaven children as of the last scan. The directory alone has 34; the homepage adds Findlay.
2. Open Lima or Findlay: exact identity, wrong/missing parent, revenue history but zero AR. Review the proposed parent, enter your name and rationale, then **Approve & apply**.
3. Open Marietta or Tiffin: positive revenue and AR. Approval creates the new account and only links the old account to it. The old parent and all other business fields remain intact.
4. Correct Kettering's survivor **before** its two duplicate copies. Duplicate proposals show the losing account and surviving ID. Only the losing copy is marked Inactive and linked with `duplicate_of_account`.
5. Review new accounts, renames, and the Portsmouth ZIP correction. Ashtabula's PO box needs investigation, not a guessed physical-address overwrite. Alliance, Coldwater and Sandusky remain under the old parent and are flagged Needs Review.
6. Refresh proposals after decisions. Applied changes should disappear from proposed work, rejected identical proposals stay rejected, and the audit remains available. A newly changed material state can produce a new proposal.

**Approve is consequential:** it writes to your isolated live CRM. Reject makes no CRM request. There is no bulk approval route, background write worker, or scheduler approval command.

## Validation

```sh
.venv/bin/python -m pytest -q
```

49 tests passed: normalization, exact/renamed matches, ZIP correction, decoys, direct re-parenting, CHOW preservation, duplicate/stale handling, idempotency, changed-state blocking, partial CHOW, lost create response, pagination, scraper completeness, and local approval protection. See `docs/VERIFICATION.md` for the verification record.

The full mock review approves all 29 proposals, performs 31 mutations (two CHOWs require two each), and produces zero further proposals. That is a **simulation**, not the live CRM end state.

Live GET endpoints and page parsing were exercised. The public OpenAPI schema lists POST/PATCH paths but omits request/response body schemas; write payloads use observed account fields and assessment conventions. No disposable sandbox/reset endpoint was documented, so POST/PATCH were tested against mocks rather than leaving test records in the final CRM. The first live human approval remains the integration test for undocumented write semantics; mismatches halt for inspection.

## Daily schedule

`schedule/daily.cron` is a cron template, intentionally not installed. Set the absolute checkout/database paths and arrange secret injection into the job environment. A normal cron job does **not** inherit your interactive shell's token. Keep SQLite on durable local storage; do not recreate the database each day. The scheduled command is only `reconcile` and cannot approve or write to CRM.

## Layout

- `reconciliation/scraper.py` — complete discovery, parsing, source hashes, fail-closed crawl.
- `normalize.py`, `rules.py` — identity keys, billing guard, proposals and fingerprints.
- `crm.py` — paginated CRM reads and exact account endpoint adapter.
- `store.py` — transactional proposals, decisions, operation journal and run history.
- `service.py` — read-only pipeline; explicit approval with fresh checks and read-back.
- `api.py`, `templates/ui.html` — local review, inventory, policy and audit console.
- `tests/` — isolated tests; never contact the live service.
- `data/` — token-free fictional assessment snapshots, captured September 17, 2026.
- `docs/RECONCILIATION_SUMMARY.md` — every CHOW, duplicate and investigation case.
- `docs/RECOVERY.md` — partial-write recovery procedure and honest operational limits.

## Architectural provenance

This is a separate project derived from the control-plane patterns in [lead-routing-copilot](https://github.com/devothamgn321/lead-routing-copilot), inspected at commit `cd448a7613dc98bd7deebe3c358be7a2bae5fd8f`. The transactional SQLite connection/event/review structure was adapted from its `copilot/store.py`; the domain, crawler, matching, financial safety and approval integration are assessment-specific. The original repository was not modified. Its MIT license is retained. See `WRITEUP.md` for matching decisions, AI usage and next steps.
