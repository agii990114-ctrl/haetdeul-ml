# 2026-08-18 (Tue) — Chwijung Daily Log

> Paste each block into the matching form field. Counts are checked against the form limits.

| Field | Value |
|---|---|
| category | `final` |
| status | `completed` |

## title (39/40)
```text
First model failed to beat the baseline
```

## feature_name (93/100)
```text
Initial wholesale price forecasting model (LightGBM, anchor-ratio target) — project inception
```

## problems (173/200)
```text
The first LightGBM model for Garak wholesale cabbage prices could not beat a naive "yesterday's price" baseline; its +0.3% gain was smaller than seed-to-seed noise (σ≈1.5%).
```

## solution (183/200)
```text
Compared three setups on an identical 2022–2024 / 2025 split (naive baseline, absolute-price target, anchor-ratio target) and judged each gain against seed variance, not a single run.
```

## result (175/200)
```text
Only the anchor-ratio target avoided losing to the baseline (0.1640 vs 0.1645); three years of data proved insufficient, redirecting work to a longer history and more targets.
```

## content (2770/6000)
````markdown
This entry covers the project's first week (2026-08-12 to 2026-08-18), reconstructed from the progress record written on 08-18. The initial objective was to forecast Garak market wholesale prices for B2B food purchasers. The first model's apparent gain proved statistically meaningless, and the analysis of why shaped two decisions that persisted for the rest of the project: the anchor-ratio target and a longer training history.

## Initial Scope

| Item | Definition at inception |
|---|---|
| Target | Garak market wholesale price per crop (KRW/kg) |
| Horizon | +1 to +18 business days from each morning |
| Crops | Napa cabbage first; onion, radish and garlic planned |
| Users | B2B food purchasers (ordering and price negotiation) |
| Model | One global LightGBM model across crops and horizons |
| Data layout | Long format: one row per (base date × crop × lead time) |

Lead time was supplied as a numeric feature so that a single model could learn near and far horizons jointly.

## Experimental Comparison

Training 2022–2024, validation 2025; 17,415 rows, 976 base dates, 29 features.

| Configuration | Validation WMAPE | vs baseline |
|---|---|---|
| Baseline (yesterday's price) | 0.1645 | — |
| LightGBM, absolute price target | 0.1699 | −3.3% |
| LightGBM, anchor-ratio target | 0.1640 | +0.3% |

WMAPE (weighted mean absolute percentage error) is the total absolute error divided by the total actual price; lower is better.

## Significance Assessment

The +0.3% improvement was compared with the variation obtained by retraining the same model under different random seeds. The seed standard deviation was 0.0024, roughly 1.5% of the error level and five times the observed gain. The result was therefore classified as indistinguishable from zero rather than as a small improvement. Judging every gain against seed variance was retained as a standing evaluation rule for the remainder of the project.

## Decision Rationale

- **Anchor-ratio target retained.** Modelling log(target / anchor) — the relative change from a known starting price — was the only configuration that did not underperform the baseline. Predicting the absolute price led the model to disregard the forecast horizon.
- **Longer history required.** Later measurement showed that three-year training stopped after only 1–12 boosting trees, indicating that the model found almost no learnable signal. The next phase extended the history back to 2017 and broadened the set of targets.

## Lessons Learned

A gain reported without its variance is not a result. Establishing the noise floor first prevented an unproductive round of feature tuning on a model that had no signal to tune.

## Records Note

No per-day records exist for 08-12 to 08-17; this entry consolidates that week.
````

---

*Sources (not for pasting): `진행기록/프로젝트_진행기록_20260818.md` · `트러블슈팅/20260818.md`*
