# Daily Log — 2026-08-31 (Mon)

**Project:** Cost Catcher (later Haetdeul Nongsan) · ML team

---

## Summary

The batch had been failing for three days and nobody knew. Fixed it, then built
the monitoring helpers that would have caught it. The same day, the scoring code
was found to have been grading three quarters of auction forecasts against the
wrong product.

## 1. Three silent failures found and fixed

```
08-29 09:00  failed
08-30 09:00  failed
08-31 09:00  failed   ← found today
```

Cause: `_anchor_mix` left in the input list on 08-28 (see that day).
Fix: remove it from the input list, retrain the two affected models (auction and
wholesale), and run through to the final load to confirm.

## 2. Monitoring helpers built

Plan: rules find problems; a helper explains them in plain words; **no helper is
allowed to fix anything** (the rebuild step empties a table, so an automated retry
can lose data).

| Helper | Role |
|---|---|
| Data quality check | Four things that must be true: grade order, same-day price spread, day-to-day link, target/anchor from the same aggregation. All four are accidents we had actually suffered |
| Batch failure investigator | Runs only on failure: which stage, how many days in a row, raw error text, handoff delay. Appends to `ALERT.txt` |
| Forecast explainer | "Why this forecast?" — always states the error margin with the reason |
| Daily Claude check | Scheduled 09:23 as a separate task |

The data quality check produced a false alarm on its first run: the same-day spread
check was pulled by one extreme low price (50 won/kg from a distress sale). Changed to
compare the 90th and 10th percentiles instead of max and min. **A false alarm every
day teaches people to ignore alarms.**

## 3. ★ Scoring code was grading against the wrong product

The target had been fixed to one package spec on 08-27. **The scoring code had not.**

```
Rows scored against a different product   25,866 of 34,905  (74%)
Worst case                                radish 2026-01-09: true 521 won, scored as 2,545
```

Fixed and rescored (mismatch 0). **Every auction score reported before today is void.**

## 4. Flat forecasts — four experiments, all rejected

Within one base date, how much does the forecast move across leads 3–18
(152 base dates)?

| Target | Crop | Forecast range | Actual range | Ratio |
|---|---|---|---|---|
| Auction | Cabbage | 13.7% | 137.8% | **0.10** |
| Auction | Radish | 14.0% | 47.7% | 0.29 |
| Auction | Onion | 12.1% | 34.7% | 0.35 |

When the actual moves 10, the forecast moves 1 to 7. Four attempts to fix it by
adding or removing inputs **all failed at the same point** — the conclusion was that
this is not solvable by changing features.

## 5. Four replies to the purchase team

Axis and 12-31 backfill · interval and price · spec filter and anchor formula ·
back-calculation and load delay. The back-calculation reply pointed out that turning
a 3.3-point margin buffer into an allowed forecast error needs one more number — **the
share of purchase price in total variable cost.**

## Sources

- `진행기록/agent_동작흐름_20260831.md`
- `진행기록/예측_평탄화_실험4건_20260831.md`
- `연동/20260831/` (four replies)
- `진행기록/agent_logs/` first entries of the investigator, quality check and Claude check
