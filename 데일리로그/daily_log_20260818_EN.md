# Daily Log — 2026-08-18 (Tue) · Project start through day 7

**Project:** Cost Catcher (renamed Haetdeul Nongsan on 2026-09-03) · ML team
**Covers:** 2026-08-12 → 2026-08-18. No per-day records exist for 08-12 to 08-17;
this entry reconstructs the first week from the progress record written on 08-18.

---

## Summary

The first model could not beat "yesterday's price." The gain was smaller than the
noise between random seeds, so it was not a result at all.

## Where the project started

The first framing was different from the one we ended up with:

| Item | At the start (08-18) |
|---|---|
| Target | Garak market **wholesale** price per crop (won/kg) |
| Horizon | +1 to +18 business days from each morning |
| Crops | Napa cabbage first; onion, radish, garlic planned |
| Users | B2B food purchasers deciding orders and negotiating prices |
| Model | One global LightGBM across crops and lead times |
| Data shape | Long format — one row = (base date × crop × lead time) |

Lead time is a numeric feature, so one model learns near and far horizons together.

## The problem

Trained on 2022–2024, validated on 2025:

| Setup | Validation WMAPE | vs baseline |
|---|---|---|
| Baseline (yesterday's price) | 0.1645 | — |
| LightGBM, absolute price target | 0.1699 | −3.3% |
| LightGBM, anchor-ratio target | 0.1640 | **+0.3%** |

A +0.3% gain against a seed standard deviation of 0.0024 (about 1.5%) is **not
statistically significant.**

Dataset: 17,415 rows · 976 base dates (2022-01-03 → 2025-12-30) · 29 features.

## What carried forward

- **The anchor-ratio target stayed.** Predicting `log(target / anchor)` instead of
  the absolute price was the only setup that did not lose to the baseline. It later
  became the foundation of every model.
- **Three years of data was too little.** Later measurement recorded `best_iter` of
  1–12 on three-year training — a model that stops after a handful of trees has no
  signal to learn. This pushed the next step toward a longer history and more
  targets.

## Sources

- `진행기록/프로젝트_진행기록_20260818.md`
- `트러블슈팅/20260818.md` — "the model cannot beat the baseline"
