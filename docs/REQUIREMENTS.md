# Requirement traceability

| # | Requirement | Implementation and evidence | Status |
|---|---|---|---|
| 1 | Every website location, address and care offering; homepage and pagination | scraper.py; 35 facilities / 40 pages; homepage-only Findlay; canonical URL/full address dedup; completeness tests | Implemented; live read tested |
| 2 | Exact API base; personal token only via environment; .env.example | crm.py reads CRM_API_TOKEN; each request explicitly attaches Authorization: Bearer; rejects redirects; .env.example and ignore rules; no credential in committed files | Implemented; authenticated reads verified |
| 3 | Confident matches, names, parents, missing, stale, duplicates, ambiguity | rules.py; 121/121-account coverage; all 35 website findings; summary enumerates every outcome | Implemented |
| 4 | Nothing writes without approval | pipeline and CLI only read; only explicit UI/API approval invokes write adapter; pending_review default; unchanged has no proposal | Implemented; tested |
| 5 | CHOW exact SOP | money validation; revenue >0 AND AR >0; create new then link old; all old business fields verified preserved; direct allowed for revenue=0 OR AR=0 | Implemented; live balances read; writes mocked |
| 6 | Duplicate marker + Inactive; Needs Review + notes for unresolved stale | Seven losing copies, three stale accounts, one ambiguous identity; no delete/merge endpoint or method | Implemented; tested |
| 7 | Evidence-rich UI; approve/reject; refetch; guard; verification; audit | Review queue has source link, CRM identity/parent, field comparison, confidence rationale, balances and CHOW interpretation; full fresh crawl/inventory, target GET, journal, mutation, response and GET verification | Implemented; browser inspected; actual approval left to candidate |
| 8 | Durable proposals and decisions; deterministic fingerprints | SQLite unique proposal IDs, atomic transitions, material-state fingerprints, supersession, no volatile timestamp hashing; second live run added zero | Implemented; tested |
| 9 | Daily schedule never approves/writes | schedule/daily.cron calls reconcile only and keeps durable SQLite; token injection prerequisite documented | Config supplied; intentionally not installed |
| 10 | README and WRITEUP | Run instructions, architectural provenance, AI usage, normalization/identity choices, CHOW, limitations, recovery and future work | Included |
| 11 | Required tests | 49 passing tests across matching, financial SOP, duplication, stale flags, reruns, concurrency, write failures, auth, pagination, scraper and local API | Passed |
| 12 | Live site/read-only CRM/docs; leave queue ready; mock unsafe write tests | Public pages/API schema and 121 accounts read live; 29 pending proposals; no live writes; request-body schema absent and no disposable reset documented | Read side verified; live mutations intentionally unexercised |
| 13 | Preserve original, separate repo/project | Separate clipboard-crm-reconciliation project; original read-only clone at cd448a7 with clean working tree; MIT provenance retained | Complete |

Additional coverage requested: **every one of 121 CRM accounts is considered**, not only name-filtered Bellhaven results. The captured run read 100 accounts on page 1 and 21 on page 2, checked unique IDs against API total, and produced a reasoned disposition for all 121. Six are corporate parent references, 74 are unrelated, 16 need no change, and 25 are existing mutation targets. Four missing website facilities add four creation proposals.

Every CRM HTTP request includes the user's Bearer token: list pages, single-account reads, create, patch, and verification GETs all share the same authenticated request function. Tests intercept all six request types/steps and check the exact synthetic credential. Read receipts expose only an authenticated boolean, never the value. **Public website crawling does not receive the CRM token**; authorization is required on CRM API calls, and is not disclosed to unrelated endpoints.

Final submission readiness still requires candidate action: review the pending proposals, approve justified changes, refresh and verify CRM end state, publish/share the source archive or repository, and report actual total time. The assessment explicitly scores the corrected CRM; a pending queue alone is not the finished assessment.
