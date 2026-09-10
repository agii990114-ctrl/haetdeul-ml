# Daily Log — 2026-08-21 (Fri)

**Project:** Cost Catcher (later Haetdeul Nongsan) · ML team

---

## Summary

The project took its final shape: **three price series along the chain from farm to
consumer**, one model each. The same day, a baseline that looked too good turned out
to be one crop dominating the average.

## 1. Three targets instead of one

The purpose shifted to **storage trading**: buy cheap at auction, store, sell high at
retail. That needs a forecast at both ends of the chain, not just the middle.

```
farm → [auction] → wholesaler → [wholesale] → restaurant/retailer → [retail] → consumer
         target_auc_prc          target_whsl_prc                    target_rtl_prc
```

Each target gets its own anchor (the previous value of the same series).

Common conditions for the first three-target run:

| Item | Value |
|---|---|
| Crops | Napa cabbage · onion · radish (garlic excluded) |
| Training | 2017-01-02 → 2022-12-30 · **1,475** unique base dates |
| Validation | 2023-01-02 → 2025-12-30 · 730 base dates |
| Features | 34 |
| Target | `y = log(target / anchor)` |
| Seeds | 42 · 43 · 44 |
| Model | LightGBM, `objective=regression_l1` |

All three models beat their baseline.

**Why garlic was excluded:** peeled and unpeeled garlic were not yet separated;
auction price was 11% missing (other crops about 1%); and wholesale price was
identical to the previous day on **94% of days** — a different problem altogether.

A separate first run of the auction model used 2019–2022 training (988 base dates)
for comparison.

## 2. The pooled-WMAPE illusion

Expanding from two crops to four made the baseline suddenly look excellent:

| Setup | Baseline WMAPE |
|---|---|
| Cabbage only | 0.2114 |
| **Four crops** | **0.0781** |

Lead time 1 read 2.7% — as if vegetable prices moved only 2.7% in a day, which is not
true. The validation script also flagged wholesale lag columns as possible leakage
(correlation above 0.995).

**Cause:** garlic. At 6,244 won/kg it held **66% of the WMAPE denominator**, and its
wholesale price barely moves. One flat, expensive series dominated the pooled figure.

**Rule adopted:** read results **per crop**, never pooled.

## Sources

- `진행기록/실험결과_3타겟모델_20260821.md`
- `진행기록/실험기록_경락가모델_20260821.md`
- `트러블슈팅/20260821_트러블슈팅_통합WMAPE착시.md`
