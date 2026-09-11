# 2026-09-01 (Tue) — Chwijung Daily Log

> Paste each block into the matching form field. Counts are checked against the form limits.

| Field | Value |
|---|---|
| category | `final` |
| status | `completed` |

## title (39/40)
```text
Condition-aware intervals via quantiles
```

## feature_name (87/100)
```text
Quantile prediction intervals, alternative-model screening and final holdout evaluation
```

## problems (188/200)
```text
The fixed interval table gave identical widths on volatile and quiet days, wholesale missed its 80% coverage target in 5 of 6 cells, and figures sent to Purchase the day before were wrong.
```

## solution (179/200)
```text
Replaced the lookup table with per-crop quantile LightGBM, screened four alternatives under the two-fold rule, opened the sealed test window once, and issued a written correction.
```

## result (177/200)
```text
Quantile bands adopted for auction/wholesale; four alternatives rejected; retail beat the strongest baseline in all 9 holdout cells; cabbage error corrected from 35.1% to 19.7%.
```

## content (4224/6000)
````markdown
Prediction intervals became responsive to market conditions through quantile regression, the sealed test window was opened once for the final measurement, and four proposals to change the model or add new data were rejected. The day ended with a written correction to the purchase team, because error figures sent the previous day had been computed from mixed records and inverted the conclusion for cabbage.

## Why the Fixed Interval Table Failed

The previous interval widths came from a lookup table keyed only by crop and lead time. Measured within a single crop, the width on volatile days divided by the width on quiet days was exactly 1.00: the table had no input through which the day's conditions could enter. A pooled measurement suggested ratios of 1.15–1.52, but this was an artefact of mixing crops with different typical widths and volatility.

## Quantile Regression Design

Separate LightGBM models were trained with a quantile objective to output the lower bound, median and upper bound directly. The trained quantile was chosen per crop as the narrowest setting that kept coverage at or above 80% on both validation folds. For example, cabbage auction used q03 (coverage 84.2% / 80.4%, width 93% → 75–76%); onion auction required q02, because q03 dropped its coverage to 74.5%. The better a crop is predicted, the more aggressively the model narrows the band, so narrower is not automatically better.

Wholesale, which had missed the 80% target in 5 of 6 cells under the fixed table, met it after the change. Retail was deferred: it already met the target in 5 of 6 cells, switching mainly widened its bands, and onion reversed direction on fold B. The median forecast was unchanged, so buffer-breach rates were unaffected; the change improved how well the system warns of its own uncertainty, not how accurate it is.

## Alternatives Screened

| Proposal | Outcome | Key evidence |
|---|---|---|
| XGBoost, CatBoost | Rejected | Library choice moved error 1%; tree count moved it 11% |
| MLP neural network | Rejected | Lost to a plain average on 6 of 6 combinations (0.2468 vs 0.1730) |
| News sentiment index | Rejected | Model relied on the slow 30-day mean (3.8–6.5% importance) and worsened |
| Google search volume | Undecided | Not harmful, not proven |

An initial measurement at 300 trees suggested XGBoost was better; repeated at the 76 trees used in production, the conclusion reversed and was retracted. For news data, removing only the 30-day mean removed the harm, which led to the guideline that such data should be supplied as ratios rather than long-window levels.

## Protocol Refinements

Two rules were added. First, a verdict expires when the conditions under which it was measured change: the second ablation round predated both the target correction and the new anchor, and re-running it under current conditions moved two feature groups. Second, grouped features must be split before a decision: the calendar group appeared removable as a block (fold A −0.0009, fold B −0.0062), but split apart the effect came from one feature on one fold (A +0.0004, B −0.0056).

## Final Holdout Evaluation

The sealed 2024–2025 window was opened once under the production configuration. Retail outperformed the strongest baseline in all nine crop and window cells, and cabbage auction improved by 13.1% in both windows. Wholesale radish remained negative, showing that its earlier validation gain had come from a single year. The window was then closed again.

## Correction to the Purchase Team

The previous day's error figures had been drawn from the prediction log, which mixed production records (`ops_auc`, underscore) with experimental backtests (`ops-auc`, hyphen). Cabbage auction mean error had been reported as 35.1% and the 14-day buffer breach as 9%; the correct figures were 19.7% and 57%. The recommendation reversed: cabbage was the least suitable crop for an aggressive purchasing stance, not the most.

## Lessons Learned

One character in a model name changed the measured population. Performance must be computed only from records filtered by an exact model identifier, and a correction must be sent as soon as an error is found, even when it reverses advice already given.
````

---

*Sources (not for pasting): `진행기록/프로젝트_진행기록_20260901.md` · `진행기록/부스팅모델비교_XGBoost_CatBoost_20260901.md` · `진행기록/신경망_사전확인_MLP_20260901.md` · `연동/20260901/2026-09-01_133502_ml_정정_오차수치와배추결론.md`*
