# 2026-08-24 (Mon) — Chwijung Daily Log

> Paste each block into the matching form field. Counts are checked against the form limits.

| Field | Value |
|---|---|
| category | `final` |
| status | `completed` |

## title (37/40)
```text
Evaluation protocol and two-fold rule
```

## feature_name (98/100)
```text
Test-window sealing, two-fold sign-agreement rule, feature ablation, lead-time gate, calendar axes
```

## problems (178/200)
```text
Ablation verdicts reversed with the validation year (auction group: remove on 2023, keep on 2022), and three silent defects made results irreproducible without raising any error.
```

## solution (177/200)
```text
Sealed the test window, required sign agreement on two folds plus 2σ before any feature decision, and fixed the retail filter, the single calendar axis and row-order dependence.
```

## result (171/200)
```text
Dropping economic variables raised auction gain +6.8%→+8.7% and retail +12.7%→+15.3%; the lead-time gate helped all six fold cases; results became reproducible run to run.
```

## content (3752/6000)
````markdown
This was the day the evaluation rules were established. The test window was sealed, a two-fold decision rule was introduced after a feature verdict reversed between validation years, several feature groups were adjudicated under that rule, and three defects that produced wrong results without any error message were found and corrected.

## Test Window Sealing

Data was split three ways: training, validation on 2023, and a sealed test window from 2024 onward. The test window was reserved for a single final check under production conditions; it was opened once, on 2026-09-01.

## Origin of the Two-Fold Rule

When validation was narrowed to 2023, the verdict for the auction feature group was "remove" on 2023 and "keep" on 2022, for all three targets. A decision based on one validation year was therefore shown to be unreliable.

```
Adopt or remove a feature only when both folds agree in sign
and the combined effect exceeds twice the seed standard deviation.
Fold A = validate 2023 · Fold B = validate 2022 · ten seeds
```

Round-two ablation under this rule resulted in no feature changes. The volume group appeared removable on two folds, but a third fold (validate 2021) kept it, identifying fold B as the exception.

## Feature Decisions

| Change | Auction | Wholesale | Retail |
|---|---|---|---|
| Remove economic variables (M2, EPU, PPI) | +6.8% → +8.7% | +6.1% → +7.2% | +12.7% → +15.3% |
| Remove producing-region weather (retail only) | — | — | +12.7% → +17.1% |

Monthly and quarterly indicators repeat the same value for a month, so a daily model used them as a time index and overfitted. After removal, the number of trees selected by early stopping rose from 33–51 to 102–140. Weather was found to help auction and wholesale but harm retail, where distribution margins buffer field conditions.

## Lead-Time Gate and Volatility Gate

- Lead-time gate adopted: for lead times below 3, the anchor is shipped instead of the model output. All six combinations of three targets and two folds improved or held (+0.0 to +0.8 points); gates at 5 or more became harmful.
- Volatility gate rejected: falling back to the baseline in quiet markets helped in 2023 and hurt in 2022, so it failed the sign-agreement test.
- Auction early stopping varied between 34 and 814 trees because the validation curve is flat, while seed-level error agreed within ±0.0011. Production training therefore uses a fixed tree count.

## School-Calendar Feature: Built and Rejected

The hypothesis was that school holidays shift wholesale demand through school kitchens. Observed NEIS data covered only 36.6% of the training window, so a year profile was built instead (leave-one-year-out MAE 0.0315; meal-day agreement 96.7%). Across three folds all three targets disagreed in sign, and wholesale — the target the hypothesis concerned — performed worst.

## Silent Defects Corrected

| Defect | Effect | Correction |
|---|---|---|
| Retail Seoul filter absent from the rebuild SQL | Re-running would silently revert retail to the national average | Filter written directly into the rebuild script |
| Calendar held a single axis | Business days count survey days (2,700), not auction days (3,348); a hardcoded 2028 holiday was one day off | Calendar split into survey and auction axes |
| Results depended on CSV row order | Same data and seed gave 0.1394 / 0.1381 / 0.1355 | Rows sorted by natural key before training |

A prediction script with versioned model bundles and a prediction log table were also created.

## Lessons Learned

A rule that allows one validation year to decide will eventually decide wrongly. Equally, a pipeline that never raises an error can still be wrong; defects of this kind are found only by re-deriving results from source.
````

---

*Sources (not for pasting): `진행기록/테스트봉인_ablation2차_20260824.md` · `진행기록/ablation_반영_최종성능_20260824.md` · `진행기록/리드타임게이트_조기종료_20260824.md` · `진행기록/학사일정_feature_20260824.md` · `진행기록/달력2축_재현성_추론파이프라인_20260824.md`*
