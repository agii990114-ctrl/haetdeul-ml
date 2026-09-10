# Daily Log — 2026-09-03 (Thu)

**Project:** renamed today — Cost Catcher → **Haetdeul Nongsan** · ML team

---

## Summary

Quantile intervals went live at 10:36 without changing a single price. The
experiment harness turned out to have been training on different data from
production. Nine backlog items were closed with **zero features adopted**, and the
evaluation protocol gained its most important rule. A new collection check caught a
ten-day silent stall on its very first run.

## 1. Quantile intervals in production (10:36)

Swapped `ops_auc` and `ops_whsl` to quantile bundles. **Names kept** — the purchase
team filters on the exact model name, and a rename would return zero rows with no
error.

```
Same inputs, base date 09-02:  0 of 162 rows changed price (max difference 0.000000)
Width change:                  auction +8.9% · wholesale +26.0%
History table:                 change_reason = 'band', not 'price,band'
```

The `'band'` tag is the evidence that only the interval moved.

## 2. ★ The experiment harness was training on garlic

```
train.py (production)   crops: cabbage, onion, radish
build()  (experiments)  no crop filter — garlic was 24% of training rows
```

Experiments had been measured on different data from production. The effect was
larger than any feature effect found that day. Fixed, and the harness now prints the
crops it trained on every time.

## 3. Nine backlog items — zero features adopted

| Item | Verdict |
|---|---|
| M-12 holiday feature | Passed three folds; a new cabbage loss appeared → deferred |
| M-07 kimchi-season definition | Keep current |
| M-15 anchor alternatives | Current anchor is best |
| M-06 producing-region share | Reversed on fold C → not adopted |
| M-05 cabbage region mapping | Opposite of hypothesis → no change |
| M-14 lead-time gate | Keep; **folds cannot settle where the gate goes** |
| P3 four zero-cost features | None adopted |
| M-22 import data | The gap is real, so it cannot be used |
| D-06 garlic re-inclusion | Blocker solved; a bigger one replaced it |

## 4. ★ The fold-C rule

**Two candidates that passed the two-fold rule both reversed on fold C** that day:

```
M-06 share    A +0.0003 · B +0.0029 · C −0.0006
M-15 mix_yr   A +0.0101 · B +0.0073 · C −0.0166   ← agreed on A and B, reproduced
                                                     on a disjoint seed set, still reversed
```

Rule: two folds are for exploring. **Anything going to production is checked on fold
C.** And: reproducibility says it was not chance; it does not say the setup was right.

Also found: **onion needs more than five years of training to beat its anchor**
(3 years −43.0% retail, 5 years +13.5%). So folds with shorter training cannot answer
absolute questions like "does the model beat the anchor."

## 5. Collection check [Q-01] — caught a ten-day stall on day one

Placed before the rebuild. On its first run: **dried chili, unpeeled and peeled garlic
had not been collected since 08-24.** The collector checked one combined "latest date"
for all six items, so one current item made the whole table look current. Fixed to
check per item.

Also: the rebuild SQL filtered crops by **name**; the source had renamed garlic from
`마늘` to `피마늘` in 2026, so garlic silently stopped at 2025-12-30. Switched to item
codes — the third time this trap was hit.

## 6. Other

- Shadow run restored — after the swap it had been comparing the new model against itself
- Repository renamed `wonga-catcher-ml` → `haetdeul-ml`; 13 pull requests merged
- Seven replies to the purchase team, including a correction: an interval-width
  direction had been stated from **two rows** of one day

## Sources

- `진행기록/daily_log_20260902-04_EN.md`
- `진행기록/실험도구_마늘혼입_20260903.md` and the nine item documents of the day
- `진행기록/수집검사_Q01_20260903.md`
- git history of 2026-09-03 (38 commits)
