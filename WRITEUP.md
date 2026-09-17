# Writeup

**Approach.** I reused the review architecture from my Lead Routing Copilot (FastAPI, SQLite, fingerprinted proposals, audit log) and rebuilt the domain logic. The scraper crawls the homepage and directory; it found 35 communities, including Findlay, which is linked only from the homepage. It aborts if fewer communities are found than the homepage states.

**Matching.** Street, city, state and ZIP are normalized (suffixes, directions, "Pike/Pk"). A full address match is the strongest signal. An exact name plus street allows a ZIP fix (Portsmouth). A similar name at a different street is not a match: Union Square, and an Amberly Manor in Colorado, became new accounts, not false links. Ashtabula matched on name and city but its CRM street is a PO Box, so I flagged it Needs Review instead of overwriting a possible billing address.

**Ownership and billing.** Before any parent change the tool re-checks revenue and AR. Both above zero means change of ownership: Marietta and Tiffin kept their old accounts untouched, got new accounts under Bellhaven, and were linked via `chow_current_account`. Otherwise the account moves directly (Lima, Findlay, Kettering, Zanesville). For duplicates, the kept copy is the one with billing history, then Bellhaven ownership, then Active; all 7 losing copies had $0 and were marked Inactive with `duplicate_of_account`. Alliance, Coldwater and Sandusky are missing from the website; that doesn't prove a sale, so they are Needs Review with parent and billing untouched.

**Result.** 29 approved changes, 121 → 127 accounts. A second run proposed nothing new and found 0 open issues.

**AI use.** I used ChatGPT for framing, Codex to build, and Claude to independently re-derive the correct answer from raw data and review the code. The first live write exposed a real bug: the API returns only `{account_id, message}`, but the tool expected the full record, so a successful create was flagged as failed and locked the queue. I verified the account directly, recovered it through the documented procedure, changed verification to a read-back of the stored record, updated the test, and then ran the remaining approvals.

**Next.** Reviewer login, conditional writes if the API supports them, a recovery screen in the app, and a labeled test set for shared campuses and mailing addresses.

**Time:** 1.5 hours
