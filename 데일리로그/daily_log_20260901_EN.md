# Daily Log — 2026-09-01 (Tue)

**Project:** Cost Catcher (later Haetdeul Nongsan) · ML team

---

## Summary

Prediction intervals became **condition-aware** through quantile regression. The
sealed test window was opened once for the final measurement. Four attempts to
change the model or add new data were all rejected. And a correction went to the
purchase team: the error figures sent the day before were wrong, and the conclusion
about cabbage inverted.

## 1. Decisions of the day

| Experiment | Result | Applied |
|---|---|---|
| **Quantile regression** | ✅ **Adopted** — auction and wholesale | Code and batch ready; production swap pending |
| Ablation under operating conditions | ✅ No feature change | Two rules added |
| Holiday feature (radish left blank) | ✅ Auction only | Not deployed |
| Boosting libraries (XGBoost, CatBoost) | ❌ Rejected | Keep LightGBM |
| News sentiment index (Bank of Korea) | ❌ Rejected | — |
| Google search volume | ❌ Undecided | Collector kept |
| Neural network (MLP) | ❌ Lost to a plain average on 6 of 6 | TFT deferred |
| Import volume and price | 🔍 Investigated only | Backlog M-22 |

## 2. ★ Quantile regression — intervals that read the situation

The purchase team said the intervals were too wide to use. Measured within one crop,
the old fixed table gave **exactly the same width ratio (1.00)** for a volatile day
as for a quiet one: width depended only on (crop × lead time).

Quantile LightGBM outputs the lower bound, centre and upper bound directly. Auction
widths narrowed; wholesale, which had missed its 80% coverage target in 5 of 6 cells,
now met it. The trained quantile had to differ by crop — onion at cabbage's setting
fell to 74.5% coverage. **Narrow is not the goal; meeting coverage and no narrower is.**

## 3. Four rejections

- **Boosting libraries.** Changing library moved WMAPE by 1%; getting the tree count
  wrong moved it by 11%. XGBoost first looked better at 300 trees — measured at the
  76 trees production uses, the conclusion reversed. Reported and retracted.
- **MLP.** Lost to a plain average on all six combinations (0.2468 vs 0.1730 on fold
  A). This was the stated basis for not starting TFT — while noting it does not prove
  TFT would lose.
- **News sentiment index.** The model used the 30-day mean heavily (3.8–6.5%
  importance) and got worse. Removing only the slow mean removed the harm. Rule:
  feed news and search data as **ratios**, never long-window levels.
- **Search volume.** Not harmful, not proven.

## 4. Two rules added to the evaluation protocol

1. **A verdict expires when its conditions change.** Round-2 ablation ran before the
   target and anchor changed; re-run under operating conditions, two groups moved.
2. **Split lumped groups before deciding.** The calendar group looked removable as a
   block; split apart, almost all of it was one feature on one fold.

## 5. Test window opened once

The sealed 2024–2025 window was opened for the final check under production
configuration. Retail was positive on all nine crop × window cells; cabbage auction
was +13.1% in both windows. The window was closed again.

## 6. ★ Correction sent to the purchase team

The previous day's reply had drawn error figures from `prediction_log`, which mixes
production records (`ops_auc`, underscore) with experimental backtests (`ops-auc`,
hyphen). One character. The average included deliberately weakened comparison models.

```
                              sent       correct
Cabbage auction mean error    35.1%  →   19.7%
Cabbage D+14 buffer breach       9%  →      57%   ← conclusion inverts
```

Not "cabbage is safe for an aggressive stance" — **cabbage is the worst of the three.**

## Sources

- `진행기록/프로젝트_진행기록_20260901.md`
- `진행기록/부스팅모델비교_XGBoost_CatBoost_20260901.md`
- `진행기록/신경망_사전확인_MLP_20260901.md`
- `연동/20260901/2026-09-01_133502_ml_정정_오차수치와배추결론.md`
