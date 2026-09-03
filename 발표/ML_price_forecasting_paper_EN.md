# Multi-Horizon Price Forecasting for Agricultural Storage Trading
## A Three-Target Anchor-Ratio Approach on Korean Wholesale Market Data

**ML Track · Haetdeul Nongsan Project**
Interim Technical Report · 2026-08-28

---

## Abstract

We build an 18-business-day price forecasting system for three vegetables
(napa cabbage, radish, onion) traded through the Seoul Garak wholesale market,
to support a storage-trading strategy: buy cheap at auction, store, sell high at
retail. We forecast three price levels along the distribution chain — auction,
wholesale, and retail — because the trading decision requires both ends.

Our central methodological choice is an **anchor-ratio target**: instead of
predicting the price level, we predict
`log(price at horizon / most recent observed price)`. Predicting levels directly
caused the model to collapse onto the training-period mean and ignore the
forecast horizon entirely (horizon feature importance 1.5%; 1-day-ahead accuracy
95% worse than a naive carry-forward).

The most consequential finding of this term was not a modelling improvement but
a **target-definition defect**. The auction price series we had been training
against was a volume-weighted average over 15 heterogeneous packaging
specifications — bulk 10 kg net bags at 711 KRW/kg averaged together with 1 kg
retail packs at 11,224 KRW/kg. The resulting series had lag-1 autocorrelation of
**0.085**, statistically indistinguishable from noise. After constraining the
target to a single packaging specification per commodity, autocorrelation rose to
**0.901** and mean absolute error fell from **22.5% to 17.5%** on the 2023
validation fold.

Current status, measured against the strongest of four naive baselines:
wholesale **+14.8% / +9.3%** and retail **+16.1% / +9.1%** across two validation
folds; auction **−3.0% / +6.0%**. We report the negative auction result openly:
on a clean series the 7-day moving average is a stronger reference point than the
previous-day price our model is anchored on. We identify anchor replacement as
the primary next step and give the measured evidence supporting it.

**Keywords:** multi-horizon forecasting, gradient boosting, target definition,
data quality, agricultural commodity prices, conformal-style empirical intervals

---

## 1. Introduction

### 1.1 Problem setting

A trading desk wishes to profit from intertemporal arbitrage in vegetables:

```
purchase at auction  →  store in warehouse  →  sell when price rises
```

The strategy is viable only if forward prices can be estimated over the storage
window. Cabbage and radish keep for several weeks; the operational planning
horizon adopted by the business side is therefore **18 business days**.

Our scope is deliberately narrow. We do not model storage cost, spoilage, order
quantity, or capital constraints; those belong to adjacent teams. **We supply a
price curve and an honest statement of its uncertainty.**

### 1.2 Why this series is hard

Korean vegetable prices are highly volatile and shock-driven. Measured on our
own database, cabbage auction price averages 777 KRW/kg with cheap days near
300 and expensive days above 2,000. A single typhoon can reprice the market
within a month: during **Typhoon Hinnamnor (September 2022)** cabbage moved from
1,237 KRW/kg in August to 2,072 KRW/kg in September, a 68% jump.

This has a direct consequence for evaluation design. A model may look strong or
weak purely depending on whether the validation year contained a supply shock.
We return to this in §6.3.

### 1.3 Contributions

1. **A three-target formulation** aligned to the physical distribution chain,
   each with its own matched anchor (§3.2).
2. **Evidence that anchor-ratio targets are necessary**, not merely convenient,
   for multi-horizon commodity forecasting (§3.3).
3. **A documented target-definition failure and its repair**, including two
   incorrect repair attempts, with the diagnostic statistics that revealed it
   (§5). We argue that series-health checks belong in the data pipeline, not in
   the modelling code.
4. **An evaluation protocol** designed to prevent self-deception: strongest-of-N
   baselines, a two-fold sign-agreement rule, and seed-variance thresholds (§4).
5. **An operational system** — unattended daily collection, inference, scoring,
   and delivery — with measured live accuracy over nine months (§6.2).

---

## 2. Data

### 2.1 Sources

All sources are public Korean government or public-corporation APIs, except
daily arrivals, which requires screen scraping.

| Source | Content | Access | Rows | Coverage |
|---|---|---|---|---|
| aT `katOrigin/trades` | Auction transactions, Garak market | REST API | 1,560,795 | 2017-01-02 – 2026-08-27 |
| aT KAMIS `perDay/price` | Wholesale and retail survey prices | REST API | 1,044,775 | 2015-01-02 – 2026-08-27 |
| KMA ASOS | Daily weather, 95 stations | REST API | 401,848 | 2015 – 2026 |
| NongNet supply bulletin | Daily arrivals and origin region | Scraping | 18,285 | 2014-12 – 2026-08-28 |
| BOK ECOS / KDI | M2, PPI, economic policy uncertainty | REST API | 4,199 | 2015 – 2026-06 |
| KASI special-day service | Public holidays | REST API | 264 | through 2028 |

The auction endpoint is transaction-level and, critically, exposes packaging
metadata (`pkg_nm`, `unit_qty`, `gds_sclsf_nm`). Section 5 shows why this matters.

### 2.2 Derived training table

```
crop_price_train    198,883 rows · 56 columns
                    2,858 distinct base dates · 2015-01-05 – 2026-08-26
one row = (base date × commodity × lead time 1..18 business days)
```

**Effective sample size is the number of base dates, not the number of rows.**
Each base date is replicated into up to 54 rows (3 commodities × 18 horizons).
Treating rows as independent overstates the sample by a factor of ~70; the
training split contains 1,473 independent base dates.

We flag this explicitly in every training log, because it governs how much
confidence any single-fold result deserves.

### 2.3 Features

31 features for auction and wholesale, 24 for retail, grouped as:

- **Price history** — lag 1/3/7, rolling means over 7/14 days, rolling standard
  deviation, same-period-last-year, cross-level ratios
- **Supply** — arrivals volume, origin-region concentration, same-period-last-year
- **Origin-region weather** — temperature, rainfall, growing degree days, mapped
  per (commodity, month) to the dominant production region via `ref_item_station`
- **Calendar** — days remaining to the next holiday, day of week, closure structure

Excluded after ablation: economic indicators (all three targets), origin weather
for the retail target only (§4.4), school-calendar features (§4.3).

---

## 3. Method

### 3.1 Model

Gradient-boosted decision trees (LightGBM), objective `regression_l1`, ensembled
over 5 random seeds by arithmetic mean of predictions. Categorical features
(`item_nm`, `target_dow`, `prod_area_stn_nm`) are handled natively.

An ensemble of 5 seeds is used because single-seed WMAPE varies by
±0.0004–0.0014 depending on target; reporting a single seed would permit
cherry-picking within that band.

### 3.2 Three targets, three anchors

Produce changes hands three times, and carries a different price at each stage:

```
farm ──[auction]──▶ intermediary ──[sale]──▶ retailer ──[retail]──▶ consumer
          ▲                          ▲                     ▲
     target_auc_prc            target_whsl_prc       target_rtl_prc
```

Each target has a **matched anchor** drawn from the identical filter:

| Target | Anchor | Filter |
|---|---|---|
| `target_auc_prc` | `auc_prc_lag1` | Seoul Garak (110001), grade 특, **fixed packaging spec** |
| `target_whsl_prc` | `whsl_prc_lag1` | Garak wholesale, grade 상품 (04) |
| `target_rtl_prc` | `rtl_prc_lag1` | Seoul retail (sgg 1101), grade 상품 (04) |

**Anchor and target must originate from the same aggregation.** If only one side
is filtered, the model is asked to predict series B from series A's history — a
mismatch that produces plausible numbers and no error. This failure occurred in
practice and is documented in §5.4.

All three target columns are excluded from the feature set for every model, since
each is a direct answer to one of the others.

### 3.3 Anchor-ratio transform

```
train:    y = log( target / anchor )
predict:  price = anchor × exp( model output )
```

**This is not a convenience.** Training on price levels produced a degenerate
model:

| Diagnostic | Level target | Ratio target |
|---|---|---|
| Importance of the horizon feature `lead_biz_d` | 1.5% | — |
| 1-day-ahead accuracy vs naive carry-forward | −95% | +0.0% (gated) |

With a level target the model learns the training-period mean and emits nearly
the same value at horizon 1 and horizon 18. Under the ratio transform, an output
of 0 reproduces the anchor exactly, so the model is structurally unable to fall
far below a carry-forward reference.

### 3.4 Lead-time gate

At horizons 1–2 the anchor is already close to the answer and model intervention
is harmful. We therefore emit the anchor directly for `lead_biz_d < 3`. Across
3 targets × 2 folds (6 combinations) this was neutral-to-positive in all six
(+0.0 to +0.8 percentage points); gating at `k ≥ 5` was harmful. Operational
setting is `--gate-lt 3`.

### 3.5 Prediction intervals

We publish `lower` and `upper` alongside each point forecast. These are
**empirical quantiles of the validation-period ratio** `actual / predicted`,
computed per (commodity, horizon) cell and requiring at least 30 observations:

```
lower = prediction × q10( actual/predicted )
upper = prediction × q90( actual/predicted )
```

This is a nominal 80% interval. We deliberately do **not** use seed dispersion,
which measures disagreement among ensemble members (1.6–1.8%) rather than
predictive error (10–17%) and would understate uncertainty by roughly an order
of magnitude.

Median interval widths after the target repair: auction 64.4%, wholesale 46.3%,
retail 22.9%.

---

## 4. Evaluation protocol

The protocol exists because early results were repeatedly overstated. Each rule
below was adopted in response to a specific measurement error we made.

### 4.1 Strongest-of-four baselines

We compare against four naive references and report improvement against the
**best** of them, per commodity:

```
① previous-day price      ② 7-day rolling mean
③ 14-day rolling mean     ④ same date last year
```

**Motivation.** An arrivals-volume model was once reported as "+40% over
baseline." It had been compared only against the previous-day value. Against
"same week last year" — far stronger for a seasonal series — the honest figure
was **+15.3%**, an overstatement of roughly 8×.

The anchor-ratio design makes this trap particularly easy to fall into, since
the anchor is *by construction* one of the baselines. Whether the anchor is the
*best* baseline is a separate empirical question, and §6.1 shows it is not
always.

### 4.2 Two-fold sign agreement

A feature or design change is adopted only if it helps in **two validation folds
with the same sign**, and the summed effect exceeds twice the seed standard
deviation.

```
Fold A:  train ≤ 2022,  validate 2023
Fold B:  train ≤ 2021,  validate 2022     (contains Typhoon Hinnamnor)
```

Test years 2024–2026 remain sealed and are opened only for final confirmation.

### 4.3 The rule in action — a rejected feature

School-lunch demand was hypothesised to drive wholesale prices. Measured over
three folds:

| Target | Fold A (2023) | Fold B (2022) | Fold C (2021) | Sum | 2×SD |
|---|---|---|---|---|---|
| Auction | +0.0036 | −0.0017 | +0.0027 | +0.0046 | 0.0028 |
| Wholesale | +0.0011 | −0.0014 | −0.0009 | −0.0012 | 0.0023 |
| Retail | −0.0002 | +0.0005 | −0.0005 | −0.0002 | 0.0012 |

Signs disagree for all three targets; 1 of 9 combinations clears the threshold.
**Reported on fold A alone, this would have appeared as "auction +3.7% → +5.6%,
a substantial gain."** The feature was rejected.

### 4.4 Ablation outcomes

- **Economic indicators removed.** All three targets improved
  (auction +6.8→+8.7, wholesale +6.1→+7.2, retail +12.7→+15.3). These series
  update monthly or quarterly, so the same value repeats for weeks and functions
  as a period identifier. Evidence: after removal, `best_iter` rose from 33–51 to
  102–140, indicating the constant-valued features had been triggering early
  stopping.
- **Origin weather removed for retail only** (+12.7 → +17.1). Distribution margin
  buffers farm-gate supply shocks; consumer demand dominates, with
  `holiday_remain_d` carrying that signal (importance rank 2, 11.2%).
- **Training start moved to 2017.** Reducing data improved both accuracy and
  stability (2015: +5.9%, SD 0.0014; 2016: +6.6%, SD 0.0029; 2017: +6.8%,
  SD 0.0007). Market structure before 2017 appears materially different.

> **Caveat.** The 2017 decision was made on the defective auction target and is
> scheduled for re-adjudication (§8).

### 4.5 Reporting discipline

No number is recorded without its conditions.

```
Insufficient:  "auction WMAPE 0.1702"
Sufficient:    "auction WMAPE 0.1702 (cabbage/onion/radish, train 2017–2022,
                validate 2023, anchor transform, 5 seeds, 31 features)"
```

Aggregate WMAPE is never used for adjudication, because a high-priced commodity
dominates the denominator. Including garlic (6,244 KRW/kg) once moved aggregate
WMAPE from 0.2114 to 0.0781 with no modelling change.

---

## 5. Target-definition failure and repair

This section is the principal empirical contribution of the term.

### 5.1 Discovery path

The defect surfaced from an unrelated request, not from model diagnostics:

```
1. Purchase team requested upper/lower price bounds
2. Cabbage interval width was anomalously large (0.65)
3. Intraday maximum was 19,900 KRW/kg — 21× the daily mean of 939
4. Queried the source API directly
5. Source is transaction-level with packaging metadata
6. Partitioned by packaging → 15 distinct products within a single day
```

The value `19,900` had been present since 2015 and appeared in every export. No
validation query examined it, because every validation query had been written to
test a hypothesis we already held.

### 5.2 The defect

The collector aggregated by (date, market, commodity, grade), discarding
packaging. Cabbage, grade 특, Garak, 2026-08-03:

| Package | KRW/kg | Volume |
|---|---|---|
| **Net bag 10 kg** | **711** | **322,940 kg (79%)** |
| Box 8 kg | 1,721 | 35,640 kg |
| Box 4 kg | 5,841 | 3,744 kg |
| Box 1 kg | **11,224** | 2,278 kg |
| …11 further packages | | |
| **Volume-weighted mean (old target)** | **939** | 410,960 kg |

Sub-classification was also collapsed: wrapping cabbage, imported cabbage, and
salad cabbage were pooled under "cabbage."

Note that per-kilogram normalisation does **not** resolve this — all figures
above are already KRW/kg, and they span a 15× range. Normalising quantity is not
the same as identifying the product.

### 5.3 Diagnostic consequences

| Statistic | Mixed | Spec-fixed |
|---|---|---|
| Lag-1 autocorrelation, cabbage | **0.085** | **0.901** |
| Coefficient of variation | 0.919 | 0.354 |
| Intraday max/min ratio | 132.7× | 9.7× |
| Days with grade inversion (특 < 상) | **737 of 815** | resolved |

**A lag-1 autocorrelation of 0.085 means the series was essentially
unforecastable.** No feature could have helped, because there was no structure
to recover. Grade inversion on 90% of trading days is impossible in a functioning
market and was, in retrospect, a loud signal.

### 5.4 Two incorrect repairs

**Attempt 1 — "equal weight implies equal product."** We constrained weight only,
leaving packaging form free, based on a single day where net bag (731) and pallet
(873) looked comparable. Over five years:

```
Cabbage at 10 kg:  net bag 824 · pallet 943 · box 1,115 · plastic bag 3,071 KRW/kg
ACF(1): all 10 kg = 0.484;  net bag only = 0.908
```

**Attempt 2 — a shared packaging list across commodities.** Allowing
`net bag / box / pallet` uniformly dropped cabbage ACF from 0.928 to **0.513**,
because `box` — required for radish — is a small-pack format for cabbage.

**Packaging form must be specified per commodity.** Final specification:

| Commodity | Packaging | Weight | ACF(1) | Volume share |
|---|---|---|---|---|
| Cabbage | net bag, pallet | 10 kg | 0.901 | 94% |
| Radish | box, pallet | 18 kg (→2017), 20 kg | 0.928 | 76% |
| Onion | net bag, pallet | 15 kg | 0.979 | 71% |

Radish is split at 2018 because the industry packaging standard changed; ignoring
the split yields ACF 0.373.

### 5.5 A second, related defect

The repair was applied to the anchor pipeline but **not** to the target
pipeline, which retained a `LIMIT 1` selection that had been safe only while
exactly one row existed per (date, market, commodity, grade). With rows now
partitioned by specification, it selected arbitrarily:

```
2026-01-27 radish:  box 20 kg   649 KRW/kg  361,520 kg   ← correct
                    box  2 kg 9,500 KRW/kg       80 kg   ← selected
```

Mismatch rate against the specification-consistent price: radish 96%, cabbage
68%, onion 99%. After aligning the target pipeline to the anchor pipeline
verbatim, mismatch is 0 for all three commodities.

**This defect was found only because a colleague requested a backfill for a
specific historical date.** Aggregate error for auction was 22.5%, which appeared
unremarkable; the failure was visible only when a single date was scored.

### 5.6 Effect of the repair

| Fold | Before | After |
|---|---|---|
| Validate 2023 | 22.5% | **17.5%** |
| Validate 2022 | 23.5% | **19.0%** |

Ensemble `best_iter` fell from 230–548 to 59–98, consistent with a target that
contains recoverable structure rather than noise.

> **Absolute WMAPE is not comparable across a change of target definition.** The
> denominator changed: the mixed series averaged 939 KRW/kg, inflated by retail
> packs; the bulk market price is 777. The correct comparison is the gap to
> baseline, reported next.

---

## 6. Results

### 6.1 Validation folds, after repair

Train from 2017 · 5 seeds · lead-time gate at 3 ·
**improvement against the strongest of four baselines**

| Target | Fold A (2023) | Fold B (2022) | Seed SD |
|---|---|---|---|
| Auction | **−3.0%** | **+6.0%** | ±0.0008 |
| Wholesale | **+14.8%** | **+9.3%** | ±0.0014 |
| Retail | **+16.1%** | **+9.1%** | ±0.0007 |

Per-commodity mean absolute error (model / strongest baseline):

| Target | Fold | Cabbage | Radish | Onion |
|---|---|---|---|---|
| Auction | 2023 | 24.2 / **22.6** | 22.7 / **21.7** | 11.3 / 11.5 |
| Auction | 2022 | **24.3** / 26.1 | **21.2** / 22.7 | 12.3 / 12.2 |
| Wholesale | 2023 | **17.8** / 21.8 | **16.0** / 19.5 | **8.1** / 8.3 |
| Wholesale | 2022 | **22.5** / 26.0 | **15.8** / 17.5 | 8.6 / 8.0 |
| Retail | 2023 | **10.0** / 12.8 | **10.4** / 11.4 | **5.5** / 5.8 |
| Retail | 2022 | **13.7** / 15.4 | **9.5** / 10.5 | 4.6 / 4.2 |

**We report the negative auction result without qualification.** On fold A the
7-day rolling mean outperforms our model for cabbage and radish. Our model does
beat the *previous-day* anchor on all three commodities (24.2 vs 24.7; 22.7 vs
22.8; 11.3 vs 11.9), but the previous-day price is not the strongest reference
in a low-volatility year.

This is a direct consequence of the anchor-ratio design: the model is
structurally protected against underperforming its own anchor, and structurally
unprotected against a better anchor. §8.1 addresses this.

### 6.2 Live operation

Predictions issued in advance, then scored against realised prices.
**2025-11-25 – 2026-08-27 · 76,614 scored predictions · gated rows excluded ·
comparison against the previous-day anchor.**

| Target | Commodity | Model MAPE | Anchor MAPE | Improvement | Interval coverage |
|---|---|---|---|---|---|
| Auction | Cabbage | 21.11% | 30.90% | +31.7% | 80.0% |
| Auction | Onion | 13.67% | 17.31% | +21.0% | 69.7% |
| Auction | Radish | 21.68% | 21.53% | −0.7% | 80.4% |
| Wholesale | Cabbage | 8.38% | 9.10% | +7.9% | 91.9% |
| Wholesale | Onion | 9.90% | 11.14% | +11.1% | 68.7% |
| Wholesale | Radish | 12.47% | 12.50% | +0.2% | 83.8% |
| Retail | Cabbage | 7.75% | 9.06% | +14.5% | 90.4% |
| Retail | Radish | 7.91% | 9.00% | +12.1% | 86.3% |
| Retail | Onion | 7.46% | 8.57% | +13.0% | 80.1% |

Nominal interval coverage is 80%; realised coverage spans 69–92%, indicating
intervals that are approximately calibrated and not artificially narrowed.

> These live figures predate the §5.5 repair for the auction target and will be
> restated once sufficient post-repair history accumulates.

### 6.3 Horizon structure

Auction, fold A, after repair:

```
horizon  1–2    +0.0%    (gated to anchor by design)
horizon  3      +1.7%
horizon  6      +4.6%
horizon 18      +3.8%
```

Directional accuracy is 55–60% for horizons ≥ 3 and near 5% for horizons 1–2,
confirming that the gate is removing a regime where the model actively harms.

### 6.4 Regime dependence

Fold A, auction, partitioned by realised volatility:

```
normal periods       model 0.1662 | baseline 0.1726     model wins
top-decile volatile  model 0.2746 | baseline 0.2602     model loses
```

This inverts the fold-level picture and is, at present, unexplained. It suggests
the empirical intervals — fitted on pooled validation data — are miscalibrated in
the tail, and motivates regime-conditional interval estimation (§8.3).

---

## 7. System

### 7.1 Pipeline

An unattended scheduled job runs daily at 09:00 KST:

```
collect auction → collect wholesale/retail → collect weather → collect arrivals
  → rebuild training table → inference (3 targets) → load → score → publish
```

Full runtime is approximately 5–13 minutes depending on scraper cache state.
Output is written to a service-schema table consumed directly by the procurement
agent, with per-day flags (`is_filled`, `is_gated`, `use_recommended`) and an
append-on-change history table enabling reconstruction of any past batch.

### 7.2 Operational lessons

Three failures this term shared a single cause: **a definition was duplicated
across multiple code sites, and a change reached some of them.**

| Failure | Duplicated definition | Detection |
|---|---|---|
| CSV header mismatch | Column list | Collector refused to load |
| Staging duplicate check | Natural key (5 vs 8 columns) | Collector refused to load |
| Target selection | Specification filter | **None** — silently wrong |

The first two failed loudly and cost hours. The third failed silently and
corrupted a model. **The difference in cost between a loud failure and a silent
one is the entire argument for validation layers.**

Additional findings of operational note:

- Windows Task Scheduler's "restart on failure" does not trigger on non-zero exit
  codes, only on failure to start. A retry layer restricted to transient error
  signatures was implemented in-process; the table-rebuilding stage is excluded
  because it truncates before writing.
- The collector wrote its CSV before loading to the database, so a load failure
  left the two permanently divergent with no recovery path. A reconciliation
  check now compares both high-water marks and re-loads when they differ.

---

## 8. Limitations and future work

### 8.1 Anchor selection — highest priority

Our anchor is the previous-day price. Fold A shows the 7-day rolling mean is a
better reference in low-volatility years:

```
current:   prediction = previous-day price × exp(model output)
proposed:  prediction = 7-day mean          × exp(model output)
```

The gap to close is 1.6 percentage points for cabbage and 1.0 for radish. Since
an output of 0 reproduces the anchor exactly, switching anchors transfers that
gap directly. Whether model skill survives on top of a smoother anchor is the
open question, and a shrinkage anchor
`α × previous-day + (1−α) × 7-day mean` should be swept rather than assuming a
corner solution.

### 8.2 Re-adjudication on the corrected target

Several accepted decisions were adjudicated on the defective auction series and
must be revisited: the 2017 training start, the volume feature group, and the
`ref_prediction_quality` blocking table. Historical data for 2015–2016 has not
yet been re-collected under the corrected specification (daily API quota),
which is a prerequisite for the training-start re-adjudication.

### 8.3 Regime-conditional intervals

Section 6.4 shows intervals are miscalibrated in the volatile decile. Candidate
approaches: Mondrian conformal calibration partitioned by realised volatility, or
quantile regression trained directly on the ratio target.

### 8.4 Onion on the selling side

Wholesale and retail onion are negative in fold B (−6.4%, −9.0%) while positive
in fold A. Under the two-fold rule this is undetermined rather than refuted.
Fold B is the shock year; the working hypothesis is that onion's selling-side
price decouples from its own history during supply disruptions.

### 8.5 Garlic

Excluded. Auction data is 11% missing, the unpeeled/peeled distinction is not
separable in the current collector, and wholesale price is unchanged from the
previous day on 94% of days — a materially different forecasting problem.
The collector change required is the same one applied to packaging in §5.

### 8.6 Deep sequence models

A GRU baseline has not been run. Prior work on Korean agricultural prices reports
RMSE improvements of 1–4% from economic covariates, which we could not reproduce
(§4.4); we attribute the discrepancy to horizon length (1 day versus 1–18) and
model family. A like-for-like comparison would strengthen the argument for the
gradient-boosting choice rather than leaving it as an assumption.

---

## 9. Conclusion

We deliver 18-business-day forecasts for three price levels across three
commodities, running unattended and consumed by a downstream procurement system.
Against the strongest of four naive baselines, wholesale and retail forecasts
improve by 9–16% across two validation folds. The auction forecast — the input
most directly tied to trading profit — improves by 6.0% in a shock year and
underperforms a 7-day moving average by 3.0% in a quiet year.

The dominant lesson of the term is not architectural. For over a year we tuned
models against an auction series whose lag-1 autocorrelation was 0.085, and no
amount of feature engineering could have succeeded. The defect was visible in the
raw data from the first day of collection — a 19,900 KRW/kg maximum against a
939 KRW/kg mean, and grade inversion on 90% of days — and every validation query
we had written was checking something else.

**We now treat series-health statistics as pipeline assertions rather than
research artefacts.** Three checks are being added, each of which would have
caught this defect years earlier:

```
grade ordering        is 특 ≥ 상 ?                    was violated on 90% of days
intraday dispersion   is max/min > 10× ?              was 132×
series health         is lag-1 autocorrelation < 0.3 ?  was 0.085
```

---

## Appendix A. Reproduction

```bash
# Training and evaluation, fold A
python train.py <csv> --target auc --train-start 2017-01-01 \
  --train-end 2022-12-31 --valid-end 2023-12-31 --gate-lt 3 \
  --seeds 42 43 44 45 46

# Fold B
python train.py <csv> --target auc --train-start 2017-01-01 \
  --train-end 2021-12-31 --valid-end 2022-12-31 --gate-lt 3 \
  --seeds 42 43 44 45 46
```

Both folds must agree in sign before any change is adopted.

## Appendix B. Specification delivered to downstream consumers

```
market          Seoul Garak (110001)
grade           특 (grade_code 11) — 98% of Garak volume
specification   cabbage  net bag / pallet, 10 kg
                radish   box / pallet, 18 kg (to 2017) then 20 kg
                onion    net bag / pallet, 15 kg
unit            KRW/kg  (trade value ÷ trade weight)
excluded        small packs, truck-lot trades, negotiated sales, retail packaging
```

Grade 특 rather than 상 because Garak volume is 98% 특; onion 상 trades on only
30–54 days per year, which is insufficient to construct a continuous series.
