# Daily Log — 2026-09-10 (Thu)

**Project:** Haetdeul Nongsan · ML team

---

## Summary

The morning batch was stopped by a false alarm and the purchase team got no forecast
until it was re-run by hand — so a rerun button now exists on screen. Remote access to
the ML screen failed for four separate reasons that all looked like the same error.
The retrain threshold turned out to be switched off for three combinations. And the
sequence neural networks (TFT, LSTM, GRU) were finally tested properly — all three lost
clearly to LightGBM and to the plain anchor, and the pipeline was checked before that
result was accepted.

## 1. A false alarm stopped the batch

The collection check flagged "rainfall missing 54% → 85%" and halted the 09:00 batch.
The weather service leaves rainfall blank on dry days, and the rebuild already reads
blanks as 0 mm — **a value, not a gap.** The check compared the last 7 days with the
prior 90 (which included the monsoon), so a dry week looked like an outage. Early
September blank rates range from 11.8% (2019) to 82.9% (2026) year to year.

Replaying the check over 250 days: rainfall would have stopped the batch on **21 of
309 days (6.8%)** — five times all other checks combined. Excluded from the verdict,
**number still shown**. Re-ran the batch: 162 rows delivered for 09-11 → 09-28.

The log had quoted the **wrong line** as the cause (arrival data, whose missing rate
had actually fallen). Noted for fixing.

## 2. Rerun buttons on screen

A morning failure used to stay broken until the next morning. Added "Run again" on the
batch tab (shown **only when today's run failed**) and "Refresh / Create now" on the AI
report. Both run the **same script the scheduler uses**, return immediately and poll
every 3 seconds (a held request would be cut by the proxy while the job kept running),
and allow only one job at a time (the rebuild empties a table).

## 3. Two report defects

- **English showed instead of Korean.** Two report files exist per day
  (`_en.md` draft and `.md` Korean). Both were flagged as the day's report; in reverse
  name order `_` sorts after `.`, so the English draft was picked. Split with an
  `is_draft` flag.
- **"Don't trust these numbers" banner on a correct report.** Ranges like `4-8` were
  written in Korean as "4 to 8," so the whole token was not found. Now checked digit by
  digit: 246 numbers, **0 missing.**

## 4. Remote access — one symptom, four causes

```
① ML server bound to 127.0.0.1 only           → address/port moved to .env, 0.0.0.0
② Port allow rule added, still blocked         → an old BLOCK rule for python.exe
                                                  (from a cancelled prompt) beats ALLOW
③ Address set in .env, still the default        → the proxy never loaded .env; it read
                                                  the variable once at import time
④ 404 on one route                              → the dev server had not picked up a rewrite
```

Cause ③ had been hidden because on the same machine the default happened to be right.
The 502 message now says **where the address came from** (setting vs default). Also
fixed: `.bat` files are pinned to CRLF — one was written with LF and would not start.

## 5. Retrain threshold: 3 weeks → 1 week

Replaying 32 weeks, the longest run of bad weeks was only 2 for cabbage auction, onion
auction and onion retail — **a 3-week threshold could never fire for them.** A false
alarm only costs a 2.5-minute candidate build that is deleted if it loses. Wholesale was
excluded from the verdict (it is identical to the previous day 6 days in 10, so it
cannot beat its anchor), with its numbers still reported.

## 6. Replies to the purchase team (three)

- `predicted` is the **centre value**, not `upper`; lead 2 now exists after the gate
  change (cover-2-day margins: cabbage 9.6% · radish 15.0% · onion 8.8%)
- **Gate effect vs market move, separated** on the same base date: cabbage upper bound
  +21.5% from the gate, −12.2% from the market; their measured +6.6% was the two
  cancelling out. Our sum matched theirs to the decimal
- `current_price` is **the anchor** (0.4 × yesterday + 0.6 × 7-day mean = 704.69,
  matching), not a market price — the source of their failed reproduction
- The two anchor mismatches they found (09-04 and 09-07) were both the **09-03 hole**
  from the `'None'` bug — all six cells match to within ±1 won once 09-03 is removed
- 9,690 re-measured rows delivered as a separate CSV; **the delivered copy was not
  overwritten**

## 7. ★ Sequence neural networks — TFT, LSTM, GRU

The 09-01 MLP lost to a plain average, but that did not show TFT would lose: sequence
models read history in order and take known-future inputs separately. Tested them the
way they are meant to be used.

**Set-up:** the same rows as LightGBM (13,908 / 13,892), folds A and B, 3 seeds,
56-day input window, 8 past inputs (including the production anchor), 7 known-future
inputs, crop as static input. LightGBM at production settings reproduced its earlier
record (0.1667 vs 0.1670).

**Found while building it:** on the survey-day axis, the anchor disagreed with the
previous cell on **95.6% of Mondays** — auctions run on Saturday, surveys do not, and
the production anchor uses Saturday's price. Without a fix the networks alone would
miss Saturday; the last known auction price was added as an input.

**Result (lead ≥ 3):**

```
            anchor   LightGBM   TFT      LSTM     GRU
Fold A      0.1730   0.1667     0.2341   0.2308   0.2689
Fold B      0.2096   0.1956     0.2873   0.3477   0.4001
```

**23 of 24 crop × fold × model cells clearly worse than LightGBM**; one undecided.

**Checked before believing it** — losing to the anchor they were fed looked like a bug:

```
Answer alignment         100.00% of rows match
Early stopping           validation loss bottomed at step 50, then rose
Early stopping off       0.2464 → 0.2294 — still 33% worse than the anchor
```

Not a bug: with about 1,475 training days, a large model starts overfitting within 50
steps — the same data on which LightGBM is best at 50–76 trees. **Rejected.**

Side finding: at leads 0–2, **LightGBM also lost to the strongest baseline on both
folds** (−1.6%, −9.7%). Leads 0–2 went live on 09-09. Not acted on — folds cannot settle
absolute questions, and values are frozen until 09-21.

The networks ran in a **separate virtual environment**: installing them pulled pandas
from 3.0.5 down to 2.3.3, which would have changed the next morning's batch.

## 8. Other

- Batch moved one hour earlier (08:00, Claude check 08:23). Whether yesterday's auction
  is available by 08:00 is **unverified** — to be checked on the first run
- The Garak notice-board scraper had been stopped in code on 09-07 but its **scheduled
  task was still enabled**, due to run on 10-01. Disabled. "Stopping" needs code,
  documentation **and** scheduler
- English experiment ledger (41 experiments) and these daily logs written

## Sources

- git history of 2026-09-10 · mainproject #492 (merged), #497
- `연동/20260910/` (three replies and the CSV)
- `진행기록/시퀀스모델비교_TFT_LSTM_GRU_20260910.md`
- `실험결과/시퀀스모델_20260910/` (reports, predictions, diagnosis)
