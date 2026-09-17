# Clipboard CRM Reconciliation

Keeps Bellhaven Senior Living's facility-to-parent links in the CRM accurate. It scrapes the website, matches every community to a CRM account, and queues each proposed change for human approval. **Nothing writes to the CRM without an approval.** Every write is re-read from the CRM and checked before it counts as applied.

## Final state (Sep 17, 2026)

| | |
|---|---|
| Website communities | 35 |
| CRM accounts | 121 → 127 (6 created) |
| Proposals | 29, all reviewed and applied |
| Second run after decisions | 0 new proposals, 0 open findings |

Applied: 2 change-of-ownership (Marietta, Tiffin), 4 direct re-parents (Lima, Findlay, Kettering, Zanesville), 7 duplicates marked Inactive, 8 name/ZIP fixes, 4 new accounts, 3 not-on-website accounts flagged Needs Review, and Ashtabula flagged Needs Review (PO Box vs street address).

## Setup

Python 3.10+ (tested on 3.12).

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
export CRM_API_TOKEN="$(python3 -c 'import getpass; print(getpass.getpass("CRM API token: "))')"
```

The token is read from the environment only and never saved. The database is `runtime/reconciliation.sqlite3` (override with `CRM_DB`). Keep the same database across runs, because it holds every decision.

## Commands

| Command | What it does | Writes to CRM? |
|---|---|---|
| `.venv/bin/python -m reconciliation reconcile` | Scrape website, read all CRM accounts, queue proposals | No |
| `.venv/bin/python -m reconciliation serve --port 8010` | Review app at http://127.0.0.1:8010 | Only on Approve |
| `.venv/bin/python review.py` | Terminal review: same checks as the app, one item at a time, stops at first failure | Only on approve |
| `.venv/bin/python diagnose.py <proposal-id>` | Compare a proposal's intended write with the live account | No |
| `.venv/bin/python -m reconciliation summary` | Last run counts and queue statuses | No |
| `.venv/bin/python -m pytest -q` | 49 offline tests with a fake CRM | No |

Offline demo with captured data, no token needed:
```sh
CRM_DB=runtime/demo.sqlite3 .venv/bin/python -m reconciliation demo
CRM_DB=runtime/demo.sqlite3 .venv/bin/python -m reconciliation serve --port 8011
```

## How an approval works

1. Re-scrape the website and re-read all CRM accounts. If the proposal no longer matches the current data, block it.
2. Re-fetch the target account; re-check the change-of-ownership rule on fresh revenue and AR.
3. Write (POST or PATCH).
4. Re-read the account with GET and compare every field. Only then mark it applied.
5. If a write may have landed but the check failed, mark it `recovery_required` and lock the queue. See `docs/RECOVERY.md`.

Rejected and applied proposals are fingerprinted and never proposed again. The daily job only runs `reconcile`.

## Daily schedule

`schedule/daily.cron` runs `reconcile` at 07:00. It needs `CRM_API_TOKEN` injected by the scheduler and the same persistent database. It cannot approve or write.

## Layout

- `reconciliation/scraper.py`: crawl, parse, fail if the community count is short
- `reconciliation/normalize.py`, `rules.py`: address/name normalization, matching, billing rule, proposals
- `reconciliation/crm.py`: paginated reads, account endpoints
- `reconciliation/store.py`: proposals, decisions, operation journal, run history
- `reconciliation/service.py`: approval flow with fresh checks and read-back
- `reconciliation/api.py`, `templates/ui.html`: review console
- `review.py`, `diagnose.py`: terminal review and read-only diagnosis
- `tests/`, `data/`: offline tests and token-free snapshots
- `docs/`: recovery procedure, coverage of all accounts

Architecture adapted from my [lead-routing-copilot](https://github.com/devothamgn321/lead-routing-copilot) (MIT).
