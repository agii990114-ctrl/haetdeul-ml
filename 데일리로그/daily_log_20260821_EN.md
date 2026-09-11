# 2026-08-21 (Fri) — Chwijung Daily Log

> Paste each block into the matching form field. Counts are checked against the form limits.

| Field | Value |
|---|---|
| category | `final` |
| status | `completed` |

## title (39/40)
```text
Three-target model and pooled-WMAPE fix
```

## feature_name (82/100)
```text
Three-target forecasting (auction, wholesale, retail) and per-crop evaluation rule
```

## problems (177/200)
```text
Storage trading needs buy- and sell-side prices, yet only wholesale was modelled. Expanding to four crops also made the baseline look implausibly strong (WMAPE 0.2114 → 0.0781).
```

## solution (188/200)
```text
Restructured the problem into three supply-chain targets, each with its own anchor, and traced the baseline anomaly to garlic dominating the pooled denominator; adopted per-crop reporting.
```

## result (184/200)
```text
All three target models beat their baselines on 2017–2022 training (1,475 base dates). Garlic, 66% of the WMAPE denominator, was excluded and per-crop reporting became a standing rule.
```

## content (3127/6000)
````markdown
On this day the project took its final structure: three price series along the chain from farm to consumer, one model per series. In parallel, an evaluation anomaly — a baseline that suddenly appeared far stronger than before — was traced to a single crop dominating the aggregate metric. Both outcomes became permanent design rules.

## Business Framing Change

The project purpose shifted from supporting wholesale purchasers to supporting storage trading: buying at auction when prices are low, storing, and selling at retail when prices are high. This requires forecasts at both ends of the supply chain, not only in the middle.

```
farm → [auction] → wholesaler → [wholesale] → restaurant/retailer → [retail] → consumer
         target_auc_prc          target_whsl_prc                    target_rtl_prc
```

Each target was paired with its own anchor, defined as the previous observed value of the same series, so that every model learns relative movement from a price of the same kind.

## Experimental Conditions

| Item | Value |
|---|---|
| Crops | Napa cabbage, onion, radish (garlic excluded) |
| Training | 2017-01-02 to 2022-12-30 — 1,475 unique base dates |
| Validation | 2023-01-02 to 2025-12-30 — 730 base dates |
| Features | 34 |
| Target transform | y = log(target / anchor) |
| Seeds | 42, 43, 44 |
| Model | LightGBM, L1 (absolute error) objective |

A separate first run of the auction model on 2019–2022 training (988 base dates) was kept for comparison. All three target models outperformed their respective baselines.

## Garlic Exclusion Criteria

Garlic was excluded on four measured grounds: peeled and unpeeled products were not yet separated in the source data; auction prices were 11% missing against roughly 1% for other crops; wholesale prices were identical to the previous day on 94% of days, which makes it a different forecasting problem; and no Seoul retail data existed for it. The data remains in the table and can be re-included through a command-line option.

## Root-Cause Investigation: Pooled WMAPE Anomaly

After the crop set expanded from two to four, the baseline WMAPE fell from 0.2114 (cabbage alone) to 0.0781. At lead time 1 it read 2.7%, implying that vegetable prices move only 2.7% in a day, which contradicts observed market behaviour. The validation script also flagged wholesale lag features as possible data leakage, with correlations above 0.995.

The investigation found no leakage. Garlic, priced at about 6,244 KRW/kg, accounted for roughly 66% of the WMAPE denominator, and its wholesale price rarely changes. A single expensive, nearly flat series was therefore dominating the pooled figure and masking the behaviour of the other crops.

## Decision Rationale

Pooled metrics were retained only as a secondary view. All model decisions from this date onward were made on per-crop results, because a pooled figure weights crops by price level rather than by business importance.

## Lessons Learned

An improvement that looks too good is a signal to inspect the denominator before celebrating. The leakage warning was a symptom of aggregation, not of the model.
````

---

*Sources (not for pasting): `진행기록/실험결과_3타겟모델_20260821.md` · `진행기록/실험기록_경락가모델_20260821.md` · `트러블슈팅/20260821_트러블슈팅_통합WMAPE착시.md`*
