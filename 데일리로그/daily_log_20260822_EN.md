# 2026-08-22 (Sat) — Chwijung Daily Log

> Paste each block into the matching form field. Counts are checked against the form limits.

| Field | Value |
|---|---|
| category | `final` |
| status | `completed` |

## title (38/40)
```text
Economic variables removed by ablation
```

## feature_name (92/100)
```text
First-round ablation: per-target exclusion of economic and producing-region weather features
```

## problems (176/200)
```text
All 34 features were fed to every target, including monthly economic indicators and producing-region weather, although their value differed by target and some appeared to hurt.
```

## solution (173/200)
```text
Ran leave-group-out ablation on 2017–2022 training and 2023–2025 validation, then made the training script exclude feature groups per target, with an option to restore them.
```

## result (174/200)
```text
With fewer features all three targets improved: auction +6.8%→+8.6%, wholesale +6.1%→+7.2%, retail +12.7%→+16.2%. The auction figures were later voided by the 08-27 spec fix.
```

## content (3044/6000)
````markdown
The first ablation round was completed and applied. Removing feature groups one at a time showed that monthly economic indicators harmed every target and that producing-region weather harmed retail. The training script was changed to exclude those groups automatically for each target. Fewer features produced better results on all three targets, which reversed the assumption that more information helps.

## Exclusion Rules

The training script now removes feature groups according to the target being trained:

| Target | Excluded groups | Features |
|---|---|---|
| Auction | Economic indicators (M2 growth, EPU, PPI) | 34 → 31 |
| Wholesale | Economic indicators | 34 → 31 |
| Retail | Economic indicators and producing-region weather | 34 → 24 |

A command-line option restores the full feature set for comparison.

## Results by Target

Training 2017–2022, validation 2023–2025; Napa cabbage, onion and radish.

| Target | Before | After | Change |
|---|---|---|---|
| Auction | +6.8% | +8.6% | +1.8 pts |
| Wholesale | +6.1% | +7.2% | +1.1 pts |
| Retail | +12.7% | +16.2% | +3.5 pts |

Monthly and quarterly indicators repeat the same value for a whole month, so a daily model used them as a marker of the time period rather than as an economic signal, which led to overfitting. On 2026-08-19 PPI and M2 growth had ranked sixth and seventh in feature importance; this result showed that high importance did not indicate useful information.

## Results by Crop

| Target | Crop | Improvement | Direction accuracy |
|---|---|---|---|
| Auction | Cabbage | +16.0% | 64.2% |
| Auction | Radish | +3.8% | 60.0% |
| Auction | Onion | −1.2% | 57.5% |
| Retail | Cabbage | +21.3% | 63.3% |
| Retail | Onion | +11.6% | 66.2% |
| Retail | Radish | +5.8% | 61.7% |

Retail reached +21.9% at lead time 18. Onion behaved differently by target: below the baseline for auction but well above it for retail.

## Business Interpretation at the Time

The results were summarised for purchasing decisions: sell-side (retail) forecasts were about twice as accurate as buy-side (auction) forecasts, cabbage was suitable for model use on both sides, radish only as a secondary reference, and onion purchases were advised to rely on current prices while onion sales could use the model.

## Validity Note

The auction figures recorded on this day were later invalidated. On 2026-08-27 the auction target was found to average fifteen different package specifications per day, and on 2026-08-31 the scoring code was found not to apply the corrected specification; every auction score reported before 2026-08-31 was declared void. The wholesale and retail figures were not affected by that defect. The exclusion decisions themselves were retained after the later re-evaluation under operating conditions on 2026-09-01.

## Lessons Learned

Removing information can improve a model when that information identifies the period rather than describing the market. A feature's importance shows how much the model relies on it, not whether that reliance is justified.
````

---

*Sources (not for pasting): `진행기록/ablation_반영_최종성능_20260824.md` (header: "실행일 2026-08-22") · `ML/20260821/ml_train_kit_2/` result files modified 2026-08-22 · `ML/20260819/ml_train_kit/feature_importance.csv`*
