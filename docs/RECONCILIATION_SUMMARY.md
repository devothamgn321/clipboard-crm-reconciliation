# Reconciliation summary

Read-only live snapshot: 2026-09-17T14:39:35.029533+00:00. **No live changes applied; 29 proposals await human review.**

Discovered **35 website facilities** across **40 pages**, read **121 unique CRM accounts**, and found **29 current Bellhaven children**. Bellhaven parent: `0015QAPLGS3FVYEEEM`.

## Proposed work

| Classification | Proposals |
|---|---:|
| missing_account | 4 |
| direct_reparent | 4 |
| duplicate | 7 |
| field_update | 8 |
| ambiguous | 1 |
| chow_required | 2 |
| stale_needs_review | 3 |
| **Total** | **29** |

16 of 35 website facilities need no changes to their surviving CRM account. Duplicate proposals are additional losing copies, so proposal totals and facility totals measure different things.

## All 121 CRM accounts considered

| Disposition | Accounts |
|---|---:|
| unrelated | 74 |
| field_update | 8 |
| stale_needs_review | 3 |
| matched_no_change | 16 |
| direct_reparent | 4 |
| bellhaven_parent | 1 |
| ambiguous | 1 |
| chow_required | 2 |
| duplicate | 7 |
| other_parent | 5 |

Coverage: 25 proposal-target accounts + 16 matched without changes + 6 parent accounts + 74 unrelated accounts = 121. The four missing facilities have no existing CRM account and are additional proposals.

Authenticated pagination: page 1: 100 records, HTTP 200; page 2: 21 records, HTTP 200. No filtered name-only CRM query was used.

## CHOW-required cases

| Facility | Old account | Old parent | Lifetime revenue | Outstanding AR |
|---|---|---|---:|---:|
| Bellhaven of Marietta | `001A34WFSUYHCRBLFT` | Cedar Trail Communities (Parent Account) | $51,250 | $3,800 |
| Bellhaven of Tiffin | `001U6RW32TY0WSXZZB` | Cedar Trail Communities (Parent Account) | $84,000 | $12,400 |

For both: create a new Bellhaven facility account, then set **only** `chow_current_account` on the old account. Preserve its other business fields.

## All duplicate cases

| Website facility | Losing copy / ID | Surviving account ID |
|---|---|---|
| Bellhaven Gardens of Monroe | Cedar Trail of Monroe — `0011AB44D05WLA9HTX` | `001U1750VLVJAGG1S5` |
| Bellhaven Gardens of Monroe | Monroe Gardens Care Center — `00159PL81N38KM4FHM` | `001U1750VLVJAGG1S5` |
| Bellhaven Shores of Erie | Harborview Shores of Erie — `001BLYF02K97SZLZHH` | `001CVBBCSDM7YHN220` |
| Bellhaven of Kettering | Kettering Senior Campus — `001B7XZAA3AFALS9GP` | `0016KTS1UAWBRXS09J` |
| Bellhaven of Kettering | Kettering Care Centre — `001WR41PYNWXCAE2X4` | `0016KTS1UAWBRXS09J` |
| Bellhaven of Owosso | Bellhaven of Owosso — `001QU150PM4Z15UA71` | `001EGU7BMJ942ZTRE6` |
| Bellhaven of Port Clinton | Harborview Nursing & Rehab of Port Clinton — `001JD2MWRA74LTSN24` | `001UELXDAKFRKB8932` |

Seven losing copies in five groups; each has $0 revenue and $0 AR. Mark Inactive and set duplicate_of_account. Correct Kettering survivor `0016KTS1UAWBRXS09J` first.

## All investigation cases

| Account | ID | Evidence / handling |
|---|---|---|
| Bellhaven of Ashtabula | `001NXP9X46CWEPSLSV` | Website name and locality match, but street differs. Verify mailing versus physical address before changing ownership or billing address. |
| Bellhaven Care Center of Alliance | `00116ETS45BL7DTQP7` | Absent from the complete Bellhaven website crawl. Ownership is unresolved; preserve parent and billing history pending investigation. |
| Bellhaven of Coldwater | `0016PVXH4B25HWR7QE` | Absent from the complete Bellhaven website crawl. Ownership is unresolved; preserve parent and billing history pending investigation. |
| Bellhaven of Sandusky | `001SXSF4ELF0Z2LGDM` | Absent from the complete Bellhaven website crawl. Ownership is unresolved; preserve parent and billing history pending investigation. |

All four proposals set Needs Review and append a note. They preserve parent and financial fields.

## Other corrections

| Classification | Facility | Proposed fields |
|---|---|---|
| missing_account | Amberly Manor | Create new account under Bellhaven |
| direct_reparent | Bellhaven Crossings of Lima | parent_id: 0015QAPLGS3FVYEEEM |
| field_update | Bellhaven Healthcare Centre of Ashland | name: Bellhaven Healthcare Centre of Ashland |
| direct_reparent | Bellhaven Meadows of Findlay | parent_id: 0015QAPLGS3FVYEEEM |
| field_update | Bellhaven Rehabilitation & Nursing of Grove City | name: Bellhaven Rehabilitation & Nursing of Grove City |
| field_update | Bellhaven Willow Creek | name: Bellhaven Willow Creek |
| field_update | Bellhaven at Sycamore Ridge | name: Bellhaven at Sycamore Ridge |
| missing_account | Bellhaven at Union Square | Create new account under Bellhaven |
| missing_account | Bellhaven of Batavia | Create new account under Bellhaven |
| missing_account | Bellhaven of Carlisle | Create new account under Bellhaven |
| field_update | Bellhaven of Chagrin Falls | name: Bellhaven of Chagrin Falls |
| field_update | Bellhaven of Chesterton | name: Bellhaven of Chesterton |
| direct_reparent | Bellhaven of Kettering | name: Bellhaven of Kettering, parent_id: 0015QAPLGS3FVYEEEM |
| field_update | Bellhaven of Portsmouth | billing_zip: 45662 |
| direct_reparent | Bellhaven of Zanesville | name: Bellhaven of Zanesville, parent_id: 0015QAPLGS3FVYEEEM |
| field_update | The Arbors at Bellhaven - Dayton | name: The Arbors at Bellhaven - Dayton |

## After human approval — simulation only

The full mock test applied all 29 decisions through the approval service and verified 31 writes, including two create-and-link CHOW sequences. A rerun produced zero new proposals. The simulated result has 127 total accounts and 39 raw Bellhaven children: 34 Active, four Needs Review (including ambiguous Ashtabula), and one Inactive Owosso duplicate. Raw child counts retain stale and duplicate history; they are not the number of confirmed website matches. **These are projected results, not the live CRM state.**

## Run commands

From the project directory after setting CRM_API_TOKEN privately:

```sh
.venv/bin/python -m reconciliation scrape
.venv/bin/python -m reconciliation reconcile
.venv/bin/python -m reconciliation serve
.venv/bin/python -m reconciliation summary
.venv/bin/python -m pytest -q
```

Open http://127.0.0.1:8000. Fresh installation and token entry are documented in README.md.

Sources: [Bellhaven website](https://analyst-assessment-production.up.railway.app), [API docs](https://analyst-assessment-production.up.railway.app/api/docs), the captured token-free fixtures in data/, and authenticated CRM GET responses.
