# 2026-09-11 (Fri) — Chwijung Daily Log

> Paste each block into the matching form field. Counts are checked against the form limits.

| Field | Value |
|---|---|
| category | `final` |
| status | `completed` |

## title (40/40)
```text
Retrain approval bug and base date fixed
```

## feature_name (91/100)
```text
Retraining approval flow, drift monitoring scope, forecast explanation and ML API allowlist
```

## problems (162/200)
```text
An 08:00 batch reported success but sent no new forecast; a pending model-update decision was declined by the next batch; and the forecast popup showed no inputs.
```

## solution (181/200)
```text
Measured each defect before fixing it: reverted the schedule and reran delivery, fixed the retraining router, read popup inputs from the forecast table, and closed 13 unused routes.
```

## result (164/200)
```text
Base date 09-11 delivered (162 rows); an end-to-end retraining test passed all checks with production bundles unchanged; drift now covers leads 0–2; two PRs merged.
```

## content (4908/6000)
````markdown
Four defects were found and fixed on this day. None raised an error: each one reported success while producing a wrong or missing result. Each was confirmed by measurement before it was fixed, and the retraining flow was then tested end to end in an isolated environment.

## Base Date Held Back by the Database Clock

The batch had been moved to 08:00 on the previous day. The database runs on UTC, so at 08:00 KST its `CURRENT_DATE` was still the previous day, and the rebuild created base dates only up to 2026-09-10. All eleven stages succeeded and no alert was raised. The only trace was a collection check showing the latest arrival date as one day in the future. The schedule was reverted to 09:00 (batch) and 09:23 (AI check), and the batch was rerun at 14:17. It delivered base date 2026-09-11 to the purchase team: 54 rows for each of the three targets, covering target dates 09-12 to 09-29. A proper fix, computing "today" in Korean time, changes the rebuild SQL and was deferred until after the 09-21 value freeze.

## Retraining Review

The implemented rule was checked against the intended one. A week counts as bad when the model's WMAPE is more than 1.0 point worse than the anchor's on at least 60 scored rows. One bad week triggers a candidate. The candidate is trained to 2025 and compared per crop on 2026 data. It is offered for approval only if at least one crop improves by more than twice the seed deviation and no crop becomes worse. The review found four defects:

1. **Approval declined automatically.** The auto-runner answered any pending question containing the word "candidate" with "build". The approval question ("replace the production model with the candidate?") contains that word, so the next batch declined it on the person's behalf. A pending retail candidate was declined this way at 14:24; its files remained.
2. **Waiting decisions dropped.** A waiting decision was saved as `waiting`, while the screen reads only `pending`, so the button would have disappeared even after the first fix.
3. **Leads 0–2 not monitored.** Drift used leads 3 and above only, although the lead-time gate had been removed on 09-09. Gated rows, where the forecast equals the anchor, were also counted at every lead: 2,584 such rows at lead 3 and above. The filter is now lead 0 and above, excluding gated rows. Replaying 32 weeks left the latest-week verdict unchanged for all nine combinations.
4. **Wholesale exclusion only half applied.** The exclusion covered the report but not the retraining decision. With the threshold forced to −100 points, wholesale now produces 0 candidates, against 3 for retail.

## End-to-End Verification

The flow was run with a temporary checkpoint, and the replacement step was run on copied bundles.

| Check | Result |
|---|---|
| Retail: decide, build, compare | Onion 6.38% → 6.17%, radish 7.86% → 7.46%, cabbage undecided; passed |
| Rerun while waiting | Button kept; no rebuild |
| Decline | Production model unchanged |
| Approve (copy) | Copy equals candidate; backup equals the previous model |
| Auction, forced candidate | Cabbage 13.65% → 14.79%, onion 11.53% → 12.18%; deleted without asking |

Production bundles and state files had identical hashes before and after.

## Forecast Explanation Popup

The popup read its inputs from the training table, which only receives a row once the actual price is known: cabbage had 0 rows for 09-11 and 1 row for 09-10. It therefore showed "none" for recent forecasts. It now reads the forecast input table first, which holds 19 rows per base date, and falls back to the training table for older dates. Four cases were verified. For example, the 09-11 auction anchor of 762 = 0.4 × 786.2 + 0.6 × 746.0.

## ML Console and API

The "review needed" label fired when the band width was 15% or more. Auction and wholesale bands are 40–78% wide, so the label was on for 32 of 32 base dates; it was removed. An audit of the forecast APIs found 13 routes that nothing calls. Among them were three retraining write paths that could replace or roll back a model from the API docs page without the approval step. All 13 were commented out. Lint passed, 54 tests passed, and blocked routes returned 404 while routes the screen uses returned 200. Both changes were merged (#581, #589).

## Documentation

- A table inventory was written for both databases, covering row counts, date ranges, writers, and about 210 MB of unused tables.
- The date ranges in the project guide were corrected.
- Daily logs for 08-19, 08-20 and 08-22 were added.
- A repository README was drafted.

## Open Items

- Two replacements on the same day would overwrite the backup, because the backup name holds only the date.
- The screen has no rollback control.

## Lessons Learned

A step that reports success is not evidence that it produced the right result. A monitoring rule must be re-read whenever the thing it monitors changes.
````

---

*Sources (not for pasting): `ops/logs/batch_20260911_*.log` · `batch_run` 68–69 · `진행기록/agent_logs/2026-09-11_*재학습*` · mainproject #581, #589 · root commits 2026-09-11 (`fc19421`, `9c156fc`, `58dfd02`, `da3659b`)*
