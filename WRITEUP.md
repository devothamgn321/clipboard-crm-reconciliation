# Assessment writeup

I adapted the control-plane architecture of my existing Lead Routing Copilot: FastAPI, SQLite transactions, deterministic fingerprints, explicit review transitions, a local console, and an append-only application audit. I built this assessment in a separate repository so the earlier project remains intact and its history remains available. I replaced its lead-routing rules and automatic outbox behavior completely: here, all mutations start as pending_review.

## Matching and evidence

The crawler starts from both the homepage and directory, follows pagination and same-site detail links, and deduplicates canonical URLs and normalized full addresses. This found 35 facilities across 40 pages, including Findlay, which was only linked from the homepage. A failed request, broken detail layout, conflicting duplicate address, or count below the homepage's stated count aborts the run before stale-account proposals are produced.

I use deterministic street normalization, including directions, street suffixes and Pike/Pk, while keeping street numbers and unit identifiers. A full street/city/state/ZIP match is strongest. Exact name plus street/city/state supports a ZIP-only repair in Portsmouth. An exact name and locality with a conflicting street is ambiguous: Ashtabula's PO box might legitimately be a billing address. A similar name at a different street does not establish identity, as shown by Union Square; Amberly Manor in Colorado is not the Hudson facility. Confidence values are evidence tiers, not measured probabilities.

An exact identity with a current website name produces a targeted rename; equivalent street abbreviations do not create cosmetic address proposals. Raw care offerings are preserved in website evidence. Existing CRM care_type is a single primary category, so I do not erase it to represent a multi-offering website list. New accounts map Memory Support to Memory Care and Short-Term Rehabilitation & Nursing to Skilled Nursing, retaining full offerings in notes.

## Billing, duplicates and stale records

Before any parent change, both financial fields must be present, finite and nonnegative. Positive lifetime revenue AND positive AR means CHOW. Marietta ($51,250 revenue / $3,800 AR) and Tiffin ($84,000 / $12,400) require successors. Approval creates the successor under Bellhaven, records its ID, rechecks the old account, and PATCHes only old.chow_current_account. It verifies all other business fields remained unchanged. The API may naturally update server metadata such as updated_at. Zero revenue OR zero AR allows direct re-parenting.

There are seven losing copies across Monroe, Erie, Kettering, Owosso and Port Clinton. I prefer a billing-history survivor, then existing Bellhaven ownership, active status, and stable account ID. Multiple financial histories or conflicting care types are held for investigation. All actual losing copies have zero revenue and AR. The proposals set duplicate_of_account and Inactive without deleting, merging, re-parenting, or moving balances. Kettering's survivor must be corrected first.

Alliance, Coldwater and Sandusky are absent from the complete website. Absence is insufficient proof of a sale, so they receive Needs Review and notes while retaining parent and billing history. Ashtabula gets a separate identity-investigation flag.

## Approval, idempotency and recovery

Every approval is explicit and named. It re-crawls, re-fetches all CRM accounts, regenerates proposals, compares the fingerprint, re-fetches the target, and re-runs financial/duplicate safety checks. Changes in material evidence require a new review. Fingerprints include policy version, website evidence, material CRM fields, proposed changes, and match rationale; volatile fetch timestamps are excluded. SQLite's unique key suppresses identical approved and rejected work. Daily runs preserve the same database and only generate proposals.

Write intentions and receipts are stored before and after each API step. A lost response or partial CHOW enters recovery_required, blocks further approvals, and never retries a create automatically. This avoids claiming cross-system atomicity that the CRM does not offer. Recovery is deliberately manual and documented. SQLite decisions are atomic; a CRM multi-step change is not. The API exposes no documented conditional-write or idempotency-key support, leaving a small external concurrent-edit window between last read and write.

## AI usage and next steps

I used ChatGPT for initial assessment framing and Codex to inspect my prior project, recover the exact requirements, inspect live read-only data/API documentation, implement the new domain, and generate/run tests and browser checks. No LLM calls, paid keys, or model judgments are required at runtime. The prior chat's findings were treated as hypotheses and checked against fresh data. Test feedback corrected a fingerprint dependency between Kettering's survivor and duplicate decisions.

The delivered queue is pending: I have not claimed that development corrected the live CRM. Before submission I must review and approve the changes I support. Live reads and rerun idempotency were exercised; writes were mocked because no disposable reset capability was documented. I would next add verified reviewer authentication, row versions/conditional writes if the API supports them, a guided recovery UI, migrations/backups, recurring ownership evidence from additional sources, and a labeled matching evaluation focused on shared campuses and mailing addresses.

Time: record the candidate's actual total, including prior discussion, this build, review, live approvals and submission. The automated build session timing is recorded separately in docs/VERIFICATION.md; it is not a substitute for the candidate's total time.
