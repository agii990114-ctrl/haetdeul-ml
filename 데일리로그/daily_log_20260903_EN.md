# 2026-09-03 (Thu) — Chwijung Daily Log

> Paste each block into the matching form field. Counts are checked against the form limits.

| Field | Value |
|---|---|
| category | `final` |
| status | `completed` |

## title (35/40)
```text
Quantile bands live; 9 items closed
```

## feature_name (97/100)
```text
Quantile interval cutover, experiment-harness data fix, backlog adjudication and collection check
```

## problems (186/200)
```text
The experiment harness trained on 24% garlic unlike production, two candidates that passed the two-fold rule later reversed, and three items had silently stopped collecting for ten days.
```

## solution (178/200)
```text
Cut over to quantile bundles under unchanged names, filtered the harness to production crops, required a third fold for production changes, and added a per-item collection check.
```

## result (180/200)
```text
0 of 162 prices changed at cutover; 9 backlog items closed with no features adopted; the new check caught a 10-day stall on its first run; the project was renamed Haetdeul Nongsan.
```

## content (4179/6000)
````markdown
Quantile intervals entered production without altering a single price. The same day revealed that the experiment tooling had been training on different data from production, that the two-fold decision rule could still admit false positives, and that part of the data collection had silently stopped ten days earlier. Nine backlog items were closed, none of which resulted in a feature change. The project was renamed from Cost Catcher to Haetdeul Nongsan.

## Cutover Procedure

At 10:36 the auction and wholesale bundles were replaced with quantile bundles. The model names were deliberately kept, because the purchase team's query filters on exact names and a rename would silently return zero rows. Using identical inputs for base date 09-02, no price changed in any of the 162 rows (maximum difference 0.000000 KRW), while interval widths changed by +8.9% for auction and +26.0% for wholesale. The history table recorded the change reason as `band` rather than `price,band`, which served as evidence that only the intervals had moved. The previous bundles were retained and a one-line rollback was prepared.

## Harness Data Discrepancy

The production training script used three crops, while the experiment builder applied no crop filter, so garlic made up 24% of experimental training rows. Experimental results had therefore been measured on different data from production, and the effect was larger than any feature effect tested that day. The builder now filters to production crops and prints the crops used in every run.

## Backlog Adjudication

| Item | Verdict |
|---|---|
| Holiday feature | Passed three folds; a new cabbage loss appeared, so deployment was deferred |
| Kimchi-season definition | Current definition retained |
| Anchor alternatives | Current anchor is best |
| Producing-region share | Reversed on the third fold; not adopted |
| Cabbage region mapping | Result opposite to the hypothesis; unchanged |
| Lead-time gate | Retained; folds cannot determine gate placement |
| Four zero-cost features | None adopted |
| Import data | Data gaps confirmed, so unusable |
| Garlic re-inclusion | Original blocker resolved; a larger one remains |

## Protocol Refinement: Third Fold

Two candidates that satisfied the two-fold rule reversed on a third fold (validate 2021). The regional-share feature scored +0.0003 and +0.0029 on folds A and B but −0.0006 on fold C. The mixed-year anchor scored +0.0101 and +0.0073, reproduced on a separate seed set, and still scored −0.0166 on fold C. The rule was amended: two folds are used for exploration, and any change intended for production must also pass the third fold. Reproducibility demonstrates that a result is not chance; it does not demonstrate that the setup was correct.

## Training-Length Dependence

Onion required more than five years of training to beat its anchor (retail: 3 years −43.0%, 5 years +13.5%). Because folds use shorter training than production, they can answer relative questions, such as whether one feature beats another, but not absolute questions, such as whether the model beats the anchor or where a gate should sit.

## Silent Collection Stall

The new pre-rebuild collection check found on its first run that dried chili, unpeeled garlic and peeled garlic had not been collected since 08-24. The collector had checked one combined latest date across six items, so one current item made the whole table appear current. It now checks each item separately. The rebuild SQL also filtered crops by name; the source had renamed garlic in 2026, so garlic rows silently ended at 2025-12-30. Filters were switched to item codes — the third occurrence of this failure pattern.

## Other Work

The shadow run, which had been comparing the new model with itself after the swap, was restored; the repository was renamed; thirteen pull requests were merged; and seven replies were sent to the purchase team, including a correction of an interval-width trend that had been stated from only two rows.

## Lessons Learned

A check that is combined across items can conceal a failure in any one of them. Each safeguard is only as reliable as the granularity at which it asks its question.
````

---

*Sources (not for pasting): `진행기록/daily_log_20260902-04_EN.md` · `진행기록/실험도구_마늘혼입_20260903.md` · `진행기록/수집검사_Q01_20260903.md` · nine item documents of the day · git history of 2026-09-03*
