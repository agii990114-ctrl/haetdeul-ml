# Daily Log — 2026-08-27 (Thu) ★★

**Project:** Cost Catcher (later Haetdeul Nongsan) · ML team

---

## Summary

**The auction target had been wrong for the whole project.** One day of cabbage
contained fifteen different products averaged together, which made the series
statistically indistinguishable from noise. Fixed the same day. Separately, the
baseline comparison for two of three targets turned out to be rigged by accident,
and a batch failure went unnoticed for nine hours.

## 1. ★★ Fifteen products in one number

The source API returns **one row per transaction**, and price differs by package.
The collector grouped by (date, market, crop, grade) and averaged them all.

**How it was found — the path matters more than the result:**

1. The purchase team asked for upper and lower price bounds
2. Our cabbage interval was unusually wide (0.65)
3. The intraday **maximum was 19,900 won/kg** — 21 times the mean of 939
4. Garak market's own website showed the **opposite grade order** from our DB
5. In our DB, top grade was cheaper than second grade on **737 of 815 days**
6. Called the raw API directly: per-transaction rows, with a package field
7. Split by package: **15 products in one day**

It came down to not letting one strange number pass.

**Effect of fixing the spec (as measured that day):**

```
Cabbage auction ACF(1)     0.085 → 0.901
Auction improvement        cabbage −7.8% → +2.3% / +21.7%
                           onion   −7.7% → +10.5% / +8.6%
```

**For the first time, all three crops were positive on both folds.** ACF(1) of 0.085
means yesterday's price says almost nothing about today's — no feature could have
helped. (The filter was refined afterwards; the final per-crop package lists are in
the experiment ledger.)

## 2. The baseline comparison was rigged by accident

`train.py` chose baseline candidates from **wholesale columns regardless of target**.
For auction, the "7-day average" candidate averaged 1,169 won/kg against a target
averaging 721 — a different series. The mismatched candidates always lost, so
**"the strongest baseline is the anchor" was true by construction**, and every
auction and retail improvement was really "versus the anchor."

Root cause: the three-target migration was completed halfway. Wholesale had the full
family of derived columns (lag3, lag7, avg14, std7, prev_yr); auction and retail did
not.

## 3. Volume figure corrected in the record

`+40% over persistence` restated as **+15.3% against the strongest baseline** in the
experiment record.

## 4. A batch failure nobody saw for nine hours

The 09:00 batch stopped at inference. **Nobody noticed for nine hours.** Failure
notification (`ALERT.txt`) was added. The same day it became clear that the code
wrote alerts but **never cleared them** — a single failure would leave "failing"
showing forever, and a permanently lit alarm gets ignored.

## 5. Handoff to the purchase team

Reply to Master and Purchase:

- Per-day flags (`is_filled`) exposed inside each day of the forecast view — done
- Overwrite traceability — done, stronger than proposed
- Grade conversion — **blocked on a measurement conflict**: our `current_price`
  measured as top grade exactly, not second grade

## Sources

- `진행기록/경락가_규격분리_20260827.md`
- `참고/Claude/2026-08-27_092930.md` · `_095209.md` · `_100821.md`
- `연동/20260827/2026-08-27_163739_ml_reply_grade_and_flags.md`
