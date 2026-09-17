# Verification record

Verified September 17, 2026. Build workspace was created around 10:23 EDT; final verification took place around 10:42 EDT (approximately 19 minutes of this agent session, excluding prior discussion and the candidate's review/submission time). Report actual total candidate time separately.

## Live, read-only evidence

- Public homepage, directory pagination, about page and all linked facility details: 40 pages, 35 deduplicated facilities. Findlay is captured from the homepage link even though the directory lists 34.
- GET /api/openapi.json retrieved and saved in docs/openapi.json. GET /api/v1/me confirmed the credential was accepted; no token or personal profile is in the deliverable.
- GET /api/v1/accounts: 100 records on page 1, 21 on page 2, total 121, unique-ID check passed. Every request includes Authorization: Bearer from CRM_API_TOKEN. GET /api/v1/accounts/{id} was also exercised.
- 29 current Bellhaven children and 29 pending proposals; second and later live runs added zero new proposals. All 121 accounts have an explicit disposition in docs/account-coverage.json and the UI.
- Latest browser-triggered refresh displayed: “Read-only reconciliation complete: 35 facilities, 0 new proposals.”
- Original repository reference working tree is clean at cd448a7613dc98bd7deebe3c358be7a2bae5fd8f. No original-repository writes or pushes occurred.

## Automated checks

49 tests pass with pytest. Ruff lint passes and Python modules compile. Two dependency deprecation warnings come from Starlette's httpx/AnyIO test harness; no test fails.

Tests cover street/directional/unit normalization, full-address identity, renamed facilities, ZIP repairs, same-name geographic decoys, missing accounts, direct re-parenting, exact CHOW boolean semantics, invalid billing data, duplicate survivor safety, multiple-billing-history ambiguity, stale flags, SQLite rerun and rejection idempotency, changed source/CRM blocking, fresh-account appearance, failed crawl preservation, missing reviewer, concurrent approval exclusion, corrupt write response, lost POST response, partial CHOW, complete 29-decision mock review, all-121 coverage, authenticated pagination/detail/POST/PATCH/read-back requests, redirect blocking, duplicate-page rejection, homepage-only discovery, scraper completeness, and local session/Host protection.

The simulated full review produces 31 API write calls and no further proposals after rerun. Both old CHOW accounts are checked for exact preservation except their successor pointers. There is no production batch-approve command.

## Browser inspection

The local app rendered its queue, source evidence, parent identity, field comparison, billing balances, CHOW instructions, and approval/rejection form. Marietta visibly shows $51,250 revenue and $3,800 AR under Cedar Trail. Inventory displays 121 rows and page receipts for 100 + 21 authenticated records. Searching Amberly Manor returns the Colorado Springs account with an unrelated disposition, while the Hudson facility has its separate creation proposal. Refresh is functional and makes no CRM writes. Source links, policy and audit views are provided. The UI uses no external asset dependencies.

## Deliberately not claimed

No live POST or PATCH was sent. There is no documented disposable sandbox reset; creating test records would pollute the evaluated data. POST/PATCH paths are confirmed by OpenAPI, but body schemas are omitted there. The adapter uses observed account fields and checks the actual response plus a fresh GET. The first candidate-approved write will verify the undocumented write contract.

The live CRM is therefore **not yet corrected**. The candidate must review and approve appropriate items, inspect verification/audit results, refresh the queue, and submit a shared source repository/archive and honest time estimate. No public hosting or GitHub publication was performed. Cron config is supplied but not installed.
