# Daily Log — 2026-08-28 (Fri)

**Project:** Cost Catcher (later Haetdeul Nongsan) · ML team

---

## Summary

A new starting point for the model — the **shrink anchor** — was measured and
adopted. The auction answer rule gained a missing condition, cutting auction error
from 22.5% to 17.5%. One detail of the anchor change was not caught, and it stopped
the batch for the next three days.

## 1. Shrink anchor (α)

Auction prices jump about 14% day to day. Starting every forecast from yesterday
alone carries that one day's noise into all eighteen horizons.

```
anchor = α × yesterday's price + (1 − α) × 7-day average
α tested: 1.0 (current, yesterday alone) · 0.8 · 0.6 · 0.4   · 5 seeds
```

Adopted per target: **auction 0.4 · wholesale 0.8 · retail 1.0**.

About 70 training runs that day (auction 20+, wholesale 17, retail 17) across
α values and both validation folds.

## 2. The auction answer rule was missing a condition

Fixed the rule that extracts the true auction price. **Auction error fell from
22.5% to 17.5%**. Wholesale and retail were unaffected. The purchase team was told
that the 08-27 and 08-28 auction values in the handoff table were being replaced.

## 3. Backfill for 2025-12-31

The purchase team asked whether a forecast could be produced as of 2025-12-31.
It could, under the new package spec, and it was scored.

## 4. ⚠ What was missed

The shrink anchor was stored as a new column, `_anchor_mix`. That column was
**accidentally also left in the model's input list.** Only the prediction step was
checked that day, on an older model bundle — the freshly trained models were never
run through to the load step.

From the next morning, every batch stopped with:

```
Missing input feature: ['_anchor_mix']
```

(See 08-29, 08-30 and 08-31.)

**Lesson recorded on 08-31:** verify a change all the way through to the final load,
not just the step that was edited.

## Sources

- `실험결과/2026-08-28_*exp_anchor*.txt` and the α training runs of that day
- `연동/20260828/2026-08-28_130815_ml_회신_백필과경락가정정.md`
