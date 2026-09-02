# Two-Stage Forecasting: Predict Arrivals, Then Price — 2026-08-26

*Baseline figures corrected 2026-08-27 — see §2. Earlier "+40% over persistence"
was measured against the weakest of three candidate baselines; the correct figure
is +15.3% against the strongest.*

**Verdict: rejected for price. The volume model itself is worth keeping as a
standalone deliverable.**

Question raised: *would predicting arrival volume first, then feeding that into the
price model, improve price forecasts?*

Structurally the idea is right — the price model currently has **no information about
arrivals during the forecast horizon**. Every volume feature is backward-looking
(`arr_qty_lag1`, `arr_qty_avg7`, `arr_qty_prev_yr`, `auc_vol_lag1`). Empirically it
does not survive.

---

## Setup

Common to every run below, so results are comparable:

```
target      target_auc_prc (auction price, Seoul Garak, grade 특)
items       배추 · 무 · 양파   (마늘 excluded, as always)
train from  2017-01-01
seeds       42 43 44 45 46      (5-seed ensemble)
recipe      anchor log-ratio  y = log(target/anchor),  pred = anchor · exp(out)
            LightGBM regression_l1, lr 0.03, leaves 31, early_stopping 200
folds       A: train→2022, valid 2023
            B: train→2021, valid 2022
```

**Significance threshold.** Per project rule (CLAUDE.md §5.7), a change is adopted only
when both folds agree in sign *and* the summed gain exceeds 2× seed std:

```
2 × (0.0017 + 0.0011) ≈ 0.0056 WMAPE
```

`train.py` was **not modified.** Volume experiments run through two new scripts,
`exp_volume_model.py` and `exp_volume_cascade.py`, which replicate the same recipe.

---

## Summary table

| What the price model receives | Fold A (2023) | Fold B (2022) | Summed gain | |
|---|---|---|---|---|
| current, 31 features | 0.1801 ± 0.0017 | 0.1820 ± 0.0011 | — | |
| **oracle** — true future volume | 0.1749 ± 0.0014 | 0.1747 ± 0.0015 | **0.0125** | ✅ |
| surprise only (true − forecast) | 0.1775 ± 0.0009 | 0.1786 ± 0.0012 | 0.0060 | ✅ |
| synthetic noise, WMAPE 20% | 0.1783 ± 0.0015 | 0.1770 ± 0.0007 | 0.0068 | △ |
| synthetic noise, WMAPE 28% | 0.1789 ± 0.0013 | 0.1793 ± 0.0016 | 0.0039 | ✗ |
| **cascade — real volume forecast** | **0.1800 ± 0.0018** | **0.1810 ± 0.0009** | **0.0011** | ✗ |

---

## 1. Oracle — the ceiling

Added `arr_qty_at_target`: the **actual** arrival tonnage on the target date. This is
unobtainable in production; it measures the maximum any volume model could deliver.

Gain 0.0125 summed, both folds same sign — real, but modest (2.9–4.0% relative).
Feature importance of the oracle column: **7.1%**.

Per-item, the interesting part:

| Item | baseline | with oracle |
|---|---|---|
| 무 | +11.5% | +12.5% |
| 배추 | +5.2% | +5.9% |
| **양파** | **−1.3%** | **+1.3%** |

Onion is our only combination that loses to the anchor. Perfect knowledge of future
arrivals flips it positive. Onion ships from storage, so arrivals are a discretionary
release decision that bears more directly on price.

---

## 2. Volume predictability — an early claim of mine was wrong

I first measured only a **persistence** baseline for volume and concluded volume was
harder to forecast than price. That was measuring the wrong thing.

Persistence at 14 business days (2023, survey axis):

| Item | volume | price |
|---|---|---|
| 무 | 0.2832 | 0.2816 |
| 배추 | 0.3877 | 0.2701 |
| 양파 | 0.2235 | 0.1171 |

True as far as it goes, and it does reflect real structure — daily series 2021–2023:

| Item | Series | CV | ACF(1) | ACF(14) |
|---|---|---|---|---|
| 배추 | volume | 0.528 | 0.780 | 0.451 |
| | price | 0.441 | 0.736 | 0.376 |
| 무 | volume | 0.360 | 0.690 | 0.351 |
| | price | 0.518 | 0.674 | 0.480 |
| 양파 | volume | 0.250 | **0.413** | 0.238 |
| | price | 0.351 | **0.983** | 0.814 |

Onion volume is *less volatile* than onion price yet twice as hard for persistence,
because persistence only fails on variance that doesn't carry over. Onion price is
near a random walk (ACF₁ 0.983); onion volume is mostly day-to-day idiosyncratic.

**But a trained model changes the picture completely.**

| Fold | volume model | persistence range |
|---|---|---|
| A (valid 2023) | **0.1684** ± 0.0004 | 0.250–0.368 |
| B (valid 2022) | **0.1567** ± 0.0010 | 0.200–0.357 |

### Second correction — persistence is the wrong yardstick

I first reported this as "**+40% over persistence**". That number is inflated and
should not be used.

Arrivals are strongly seasonal, so **previous-year same period** is a far stronger
baseline than yesterday's value. Measured against the strongest of three
(yesterday / 7-day average / previous year), on causal expanding-window forecasts,
2023–2026:

| Item | model | prev-year | 7-day avg | yesterday | vs strongest |
|---|---|---|---|---|---|
| **all** | **0.1676** | 0.1979 | 0.2246 | 0.2704 | **+15.3%** |
| 배추 | 0.1867 | 0.2276 | 0.2756 | 0.3158 | +18.0% |
| 무 | 0.1621 | 0.1975 | 0.2198 | 0.2697 | +17.9% |
| 양파 | 0.1604 | 0.1801 | 0.1975 | 0.2434 | +10.9% |

**+15.3% is the honest figure.** The anchor log-ratio transform makes this trap easy
to fall into: the anchor is *by definition* the baseline, because a model that
outputs zero returns the anchor. Whether the anchor is the *best* available baseline
is a separate question, and it was never asked (backlog M-15 raises the same issue
for prices).

The conclusion still holds, and is arguably stronger — the price models beat their
own strongest baselines by +5.4% (auction), +13.3% (wholesale) and +16.0% (retail).
Arrivals at +15.3% sit alongside retail, our best price model, and are the only
target positive on **all three items**.

### A third slip, caught while recomputing

An intermediate comparison put 2023 at 0.2040 while the single-fold run gave 0.1684.
Cause: **2.7% of rows carried a prediction of 0** — anchor fill where
`arr_qty_lag1 ≤ 0` — each contributing 100% error. Excluding them gives 0.1682,
matching. Filter invalid predictions before computing any comparison metric.

`exp_volume_model.py` now always prints all three baselines and computes improvement
against the strongest, so this cannot recur silently.

### Horizon profile

The flat profile is the striking part, and it survives the correction (percentages
below are against the strongest baseline, 2023–2026 causal):

```
LT1  +13.0%    LT7  +14.8%    LT14 +15.2%    LT18 +14.8%
     0.1668         0.1686         0.1686         0.1678
```

Price over the same span degrades 0.1340 → 0.1913. **Arrivals at 18 business days
are as accurate as tomorrow.** They run on a repeating calendar rather than momentum:

```
arr_qty_lag1      35.0%
arr_qty_prev_yr   17.8%
holiday_remain_d  12.1%
arr_qty_avg7       5.6%
whsl_prc_prev_yr   5.6%
prod_area_stn_nm   5.3%
```

---

## 3. The cascade — causal, and it delivers nothing

Volume forecasts generated with an **expanding window**: year *Y* is predicted by a
model trained only on years < *Y*, mirroring annual retraining. Training on all years
at once would let the volume model predict its own training data, handing the price
model something close to the oracle that production could never reproduce.

Against the strongest baseline each year (rows with a valid prediction only):

| Year | volume model | prev-year | vs strongest |
|---|---|---|---|
| 2017 | 0.2075 | 0.1759 | **−17.9%** |
| 2018 | 0.1937 | 0.1865 | **−3.8%** |
| 2019 | 0.1802 | 0.2133 | +15.3% |
| 2020 | 0.1821 | 0.2113 | +13.8% |
| 2021 | 0.1880 | 0.1949 | +3.5% |
| 2022 | 0.1596 | 0.1977 | +19.3% |
| 2023 | 0.1682 | 0.1837 | +8.5% |
| 2024 | 0.1590 | 0.1980 | +19.7% |
| 2025 | 0.1684 | 0.2085 | +19.2% |
| 2026 | 0.1800 | 0.2024 | +11.1% |

**The volume model needs roughly four years of history.** 2017 is trained on
2015–2016 alone and loses to a previous-year lookup; 2018 is still short. From 2019
it is consistently ahead. Worth knowing before promising anything on a new item.

Forecast quality overall — R² 0.70 against actuals, correlation 0.838. Fed into the
price model:

```
Fold A  0.1801 → 0.1800     Fold B  0.1820 → 0.1810
summed gain 0.0011   vs threshold 0.0056
```

**Essentially zero.** Note it also underperforms the *synthetic* 20%-noise run
(0.0068) despite being more accurate — synthetic noise was iid and independent of
everything else, whereas a real forecast is not.

---

## 4. Why — the value lives in the residual

The volume model builds its forecast from features the price model **already has**:

```
arr_qty_lag1 35.0% + arr_qty_prev_yr 17.8% + holiday_remain_d 12.1% + arr_qty_avg7 5.6%
= 70.5% of importance, all already price-model inputs
```

So `arr_qty_pred` is a nonlinear recombination of existing inputs. Gradient boosting
can form those combinations itself.

Decomposition confirms it. Feeding only the **surprise** — actual minus forecast, std
224 t against a 530 t mean, and near-uncorrelated with every existing feature
(`arr_qty_lag1` −0.127, `avg7` +0.111, `prev_yr` +0.129, `holiday_remain_d` −0.008):

```
surprise only      gain 0.0060   ✅
predictable part   gain 0.0011   ✗
oracle (both)      gain 0.0125
```

**Roughly 5× the value sits in the component that is by construction unforecastable.**

This makes the cascade *self-defeating*, not merely weak. Improving the volume model
pushes its output closer to what existing features already imply, so redundancy grows.
The residual that would help is exactly what no model can produce — that is what makes
it a residual.

---

## 5. Follow-up: route production-area weather through volume only?

Proposal: weather affects price *through* supply, so give weather to the volume model
alone and drop it from the price model — same signal, simpler model.

| Price model variant | Fold A | Fold B |
|---|---|---|
| current (weather in, 31 feat) | 0.1801 ± 0.0017 | 0.1820 ± 0.0011 |
| weather removed (24 feat) | **0.1791** ± 0.0007 | **0.1906** ± 0.0011 |
| weather removed + volume forecast (25 feat) | 0.1797 ± 0.0008 | 0.1901 ± 0.0010 |

Dropping weather **helps** in 2023 (−0.0010) and **hurts badly** in 2022 (+0.0086,
4× its own threshold). Adding the volume forecast back recovers 0.0005 of that — noise.

### The mechanism, in one table

배추, second half of 2022. Typhoon Hinnamnor made landfall **6 September 2022**.

| Month | arrivals (t) | idx | price (원/kg) | idx |
|---|---|---|---|---|
| Jun | 424 | 100 | 805 | 100 |
| Aug | 574 | 135 | 1,237 | 154 |
| **Sep** | **625** | **147** | **2,072** | **257** |
| Oct | 599 | 141 | 1,032 | 128 |
| Nov | 857 | 202 | 476 | 59 |

**In September arrivals rose 47% while price rose 157%.** If price tracked arrival
tonnage, more supply would mean lower price — November shows that normal inverse
relation (volume 202, price 59). September inverts it.

The storm destroyed crop *quality* in the field and shifted scarcity expectations,
while growers rushed to move salvageable stock, which *raised* short-run arrivals.
Weather reached price through channels tonnage cannot carry:

- **Grade composition** — same tonnage of storm-damaged cabbage prices very
  differently, and our target is grade 특 specifically
- **Expectations** — a typhoon forecast moves the auction before it moves a truck
- **Sign instability** — during the shock the volume→price mapping *inverts*, so a
  volume forecast is not a weak proxy for weather; it points the wrong way exactly
  when it matters

Weather is also only ~9% of the volume model's own importance. Volume runs on
calendar, not weather. It was never a strong carrier of the weather signal.

**Keep weather in the price model.**

---

## 6. Side finding — fold B is the shock fold

This is the **third time fold B has been the sign outlier** (previously: school-calendar
feature, volume feature group). Our notes flagged that a third case should be
investigated. This appears to be the explanation:

**Fold B validates on 2022, and 2022 contains a major supply catastrophe.**

That reframes the earlier two rejections. Features that looked worthless in fold B may
simply have been useless *during a weather shock*, which is a different claim from
useless in general. Worth remembering whenever folds disagree from now on.

---

## 7. Conclusions

1. **Do not build the two-stage cascade for price.** Measured on two folds with real
   causal forecasts: 0.0011 against a 0.0056 threshold.
2. **Do not drop production-area weather from the price model.** Fold-dependent, and
   the volume forecast does not substitute for it.
3. **The volume model is a keeper on its own terms.** WMAPE 0.17, flat out to 18
   business days, **+15.3% against the strongest baseline** and positive on all
   three items — the only target of ours that manages that. Logistics sizes
   warehouse intake and purchasing sizes orders; that is a deliverable, not a
   feature. Needs ~4 years of history before it beats a previous-year lookup.
   (Do **not** quote the earlier "+40% over persistence" — see §2.)
5. **Report improvement against the strongest of several baselines, always.** The
   anchor transform makes the anchor look like *the* baseline when it is only one
   candidate. Written into `CLAUDE.md` §11; `exp_volume_model.py` now prints all
   three and computes against the best.
4. **The onion gap is real but out of reach this way.** Onion auction is our only
   negative combination, and the oracle flips it positive. The signal exists; a volume
   model cannot supply it. Look instead for *already-published* forward supply
   information — shipment plans, KREI outlook releases — which is the same 7.1% signal
   without needing to forecast it.

---

## Reproduction

```bash
# training CSV: crop_price_train LEFT JOIN daily_volume on (item, target_dt),
#   deduplicated by req_date DESC, adding column arr_qty_at_target

# volume model
python exp_volume_model.py <csv> --valid-end 2023-12-31
python exp_volume_model.py <csv> --train-end 2021-12-31 --valid-end 2022-12-31

# causal volume forecasts → cascade CSV
python exp_volume_cascade.py <csv> <out.csv>

# price model, either fold
python train.py <csv> --target auc --train-start 2017-01-01 \
    --train-end 2022-12-31 --valid-end 2023-12-31 --seeds 42 43 44 45 46
```

Scripts: `ML/20260824/ml_train_kit_2/exp_volume_model.py` ·
`exp_volume_cascade.py`. `train.py` unchanged.
