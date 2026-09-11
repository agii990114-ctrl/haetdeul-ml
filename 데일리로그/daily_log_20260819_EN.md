# 2026-08-19 (Wed) — Chwijung Daily Log

> Paste each block into the matching form field. Counts are checked against the form limits.

| Field | Value |
|---|---|
| category | `final` |
| status | `completed` |

## title (38/40)
```text
Learning and lead-time curves measured
```

## feature_name (87/100)
```text
Wholesale price training kit, learning-curve and lead-time analysis (cabbage and onion)
```

## problems (158/200)
```text
It was unknown how much history the model needed and at which horizons it actually beat yesterday's price; the backlog still assumed one target and two crops.
```

## solution (170/200)
```text
Built a reusable training kit and measured a learning curve over eight training start years and a per-lead-time curve against the naive baseline, with feature importance.
```

## result (158/200)
```text
A 2019 start scored best (+11.2%, σ 0.0026); the model lost to the baseline at leads 1–3 (−18.0% to −2.5%) and gained from lead 4, reaching +10.1% at lead 11.
```

## content (3606/6000)
````markdown
This day established the first quantitative picture of where the model helps. A reusable training kit was produced, and two measurements answered questions that the initial result had left open: how much historical data the model needs, and at which forecast horizons it outperforms simply repeating yesterday's price. Both measurements shaped decisions taken in the following week.

## Training Kit

A self-contained kit was prepared that trains LightGBM on an exported copy of the training table and compares it with the naive baseline. It reports three outputs: performance by forecast horizon, feature importance, and performance by training start year. Its guidance emphasised three reading rules: judge improvement against the baseline rather than absolute error; treat a stopping point of only a few trees as a sign that no signal was found; and count unique base dates, not rows, as the true sample size, because each base date is repeated for eighteen horizons.

The dataset exported that morning covered Napa cabbage and onion (96,822 rows, base dates 2015-01-05 to 2025-12-30, lead times 1–18). The default target was the Garak wholesale price with the previous wholesale price as anchor, trained to 2024 and validated on 2025.

## Learning Curve

| Training start | Base dates | WMAPE | Improvement | Seed σ |
|---|---|---|---|---|
| 2015 | 1,968 | 0.1970 | +6.8% | 0.0031 |
| 2016 | 1,721 | 0.1947 | +7.9% | 0.0022 |
| 2017 | 1,475 | 0.1967 | +7.0% | 0.0001 |
| 2018 | 1,232 | 0.1916 | +9.4% | 0.0013 |
| **2019** | **988** | **0.1878** | **+11.2%** | 0.0026 |
| 2020 | 742 | 0.1930 | +8.7% | 0.0012 |
| 2021 | 494 | 0.1974 | +6.6% | 0.0006 |
| 2022 | 246 | 0.1949 | +7.8% | 0.0011 |

More data did not monotonically improve accuracy. The 2019 start performed best and was adopted as the working training window.

## Lead-Time Curve

| Lead (business days) | Model | Baseline | Improvement | Direction accuracy |
|---|---|---|---|---|
| 1 | 0.1092 | 0.0926 | −18.0% | 47.7% |
| 2 | 0.1229 | 0.1131 | −8.7% | 50.5% |
| 3 | 0.1337 | 0.1305 | −2.5% | 54.0% |
| 4 | 0.1472 | 0.1489 | +1.2% | 55.0% |
| 7 | 0.1778 | 0.1925 | +7.6% | 56.2% |
| 11 | 0.2119 | 0.2357 | +10.1% | 56.5% |

At the shortest horizons yesterday's price is already close to the answer, so the model adds noise rather than information. The advantage grows with the horizon. This pattern was the origin of the lead-time gate adopted on 2026-08-24, which ships the anchor instead of the model below lead 3.

## Feature Importance

The largest contributors were the 14-day wholesale average (14.4%), growing-degree days in the producing region (14.1%), the previous wholesale price (9.6%), days to the next holiday (7.3%) and the prior-year price (6.6%). Two monthly economic indicators, PPI (6.3%) and M2 growth (5.8%), also ranked highly; the ablation of 2026-08-22 later showed that removing them improved accuracy, indicating that high importance did not mean useful information.

## Planning Baseline

The backlog was revised to version 2.0 on this day, still assuming a single wholesale target and two crops. Within two days the scope expanded to three targets and additional crops.

## Later Revisions

The 2019 training start was superseded after the three-target re-measurement, which favoured 2017 because of its much lower seed variance. The per-horizon finding was retained and became the lead-time gate.

## Lessons Learned

Measuring performance by horizon, rather than as a single average, exposed that the model was harmful exactly where a buyer would first look — the next few days — and useful only further out.
````

---

*Sources (not for pasting): `ML/20260819/ml_train_kit/` (README, `learning_curve.csv`, `curve_leadtime.csv`, `feature_importance.csv`, `crop_price_train_202608190937.csv`) · `진행계획/프로젝트_백로그_v2.md` header*
