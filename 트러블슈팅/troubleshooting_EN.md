# Troubleshooting Casebook — Complete Record

Haetdeul Nongsan (formerly Wonga Catcher) · ML price forecasting
Covers 2026-08-18 through 2026-09-04 · written 2026-09-04

**What this is.** Every failure in this project from the first day to now, with
how it looked, what it actually was, and what changed. It consolidates the three
Korean files in this folder (`20260818.md`, `20260821_*.md`, `20260824_*.md`),
which cover only the first week, together with the incidents recorded across
`진행기록/` — which had never been collected in one place.

**Why the wrong answers are kept.** Several entries record a number we reported
and later retracted. The retraction is the useful part: it is what tells the
next person which mistake is easy to make. Nothing is deleted for looking bad.

---

## Index

### A. The target or the definition was wrong
| # | Symptom | Actually |
|---|---|---|
| A1 | Auction target unpredictable at any horizon | **15 packaging specs averaged together** |
| A2 | Calendar validated perfectly on history | Validated against the wrong axis; future dates wrong |
| A3 | Retail model quietly worse | Anchor national, target Seoul |
| A4 | Auction forecasts missing on Saturdays | Auction target pinned to the survey calendar |

### B. We measured the wrong thing
| # | Symptom | Actually |
|---|---|---|
| B1 | Model cannot beat baseline | Effective sample 18x smaller than the row count |
| B2 | Baseline improved 0.2114 -> 0.0781 | One expensive item was 66% of the denominator |
| B3 | Leakage alarm, correlation 0.9978 | Garlic is unchanged on 94% of days |
| B4 | Scores looked plausible | 74% of rows graded against a different product |
| B5 | Cabbage error 35.1%, breach 9% | Experimental models averaged into production |
| B6 | 5 of 6 combinations worse than the anchor | An experimental bundle, one summer, 45 days |
| B7 | A blocked combination scores at parity | It was shipping the anchor and grading itself |

### C. Rows disappeared and nothing turned red
| # | Symptom | Actually |
|---|---|---|
| C1 | All sources current | A pooled MAX hid three stalled items for 8 months |
| C2 | "0 new rows" while rows loaded | Item lookup keyed on a name the source renamed |
| C3 | Retail 100% NULL after a rebuild | Post-processing ran before the TRUNCATE |
| C4 | Backfill reported success | CRLF put `\r` inside 137 filenames |
| C5 | Predictions stored as 0.049 | The inverse transform was skipped |

### D. It ran unattended and nobody was reading
| # | Symptom | Actually |
|---|---|---|
| D1 | Batch green every morning | Validation output discarded; [14] failed for a week |
| D2 | Forecasts shipping normally | Base date one day stale for eight months |
| D3 | No failure alerts | The batch had not run for 66 hours |
| D4 | "Still failing" after success | The alert file was never cleared |
| D5 | Actuals stopped appearing in the UI | Backfill loaded but never scored |
| D6 | Drift alarms on healthy weeks | Drift measured as raw error, not gain over anchor |
| D7 | Checker said "normal", 3 items were stale | **Three mistakes made while building the checker** |

### E. The experiment was valid, the conclusion was not
| # | Symptom | Actually |
|---|---|---|
| E1 | A feature looked clearly good | Only one validation year had been checked |
| E2 | 36.6% coverage, harmless | Missingness became a date identifier |
| E3 | Adding a column changed everything | The column silently entered the baseline |
| E4 | **Fold B disagreed, five times** | **Fold B is the only fold containing a supply shock** |
| E5 | Reproduced on two seed sets | The tool was training on 24% garlic |
| E6 | A feature worth +1.67% | Gone at 20 seeds |
| E7 | Passed all three folds | Reversed at production training length |
| E8 | XGBoost beats LightGBM | Compared at 300 trees; production uses 76 |
| E9 | The data clearly disagrees with the window | Fixing it changed nothing |

### F. The number was right, the sentence was wrong
| # | Symptom | Actually |
|---|---|---|
| F1 | "The band narrowed" | That axis had two rows that day |
| F2 | Band width told us the method | Three teams inferred it; all three wrong |
| F3 | "Kimjang season shifts 1-2 weeks a year" | Eight of nine years sat in the same two weeks |
| F4 | Predictions barely move across the horizon | Real, but **not** the model being lazy |

### G. Working with another team
| # | Symptom | Actually |
|---|---|---|
| G1 | Their repo looked like a 29-file skeleton | Our clone was 12 days stale; work was on `dev` |
| G2 | Four contract mismatches | Their thresholds assumed an accuracy nobody has |

---

# A. The target or the definition was wrong

## A1. The auction target was a mixture of 15 packaging specs

**The largest failure in this project.** Found 2026-08-27.
Full record: `진행기록/경락가_규격분리_20260827.md`

### Symptom

Nothing improved auction-price prediction. Not weather, not arrival volume, not
calendar. Grades were inverted — the "special" grade cheaper than the grade
below it on **737 of 815 days**. We spent weeks treating this as a modelling
problem.

### Diagnosis

We stopped looking at the aggregate and pulled the raw transactions for one
item, one market, one day. Garak cabbage, special grade, 2026-08-03:

```
mesh bag 10kg      710.8 KRW/kg    79% of volume
pallet   10kg      870.0 KRW/kg     6% of volume
box       4kg    5,841.3 KRW/kg
box       1kg   11,223.7 KRW/kg               <- a retail small pack
[weighted mean]    938.5 KRW/kg               <- what our target was
```

**Fifteen specs in a single day.** The API returns individual transactions and
price depends on packaging; the collector aggregated by
(date, market, item, grade) and averaged **different products** together.

| Metric | Mixed | Spec-fixed |
|---|---|---|
| Autocorrelation ACF(1), cabbage | **0.085** | **0.795** |
| Coefficient of variation | 0.919 | 0.354 |
| Intraday min/max ratio | 132.7x | 9.7x |
| Grade inversion | 737 / 815 days | resolved |

### Root cause

**ACF(1) = 0.085 is white noise.** Yesterday told us almost nothing about today.
We were asking the model to predict an unpredictable series, and **no feature
could have helped** — which is exactly what the ablation results had been saying
for weeks. We read them as "these features are useless" instead of "this target
is noise."

Radish and onion were barely affected because their packaging is homogeneous
(radish 0.788 -> 0.822, onion 0.974 -> 0.975). Only cabbage was destroyed.

### Fix

Pin weight, not packaging: cabbage 10kg, radish 18kg (through 2018) then 20kg,
onion 15kg. Mesh, pallet and PE sack at the same weight are the same product
moved differently and combine by volume weight. Small packs (8kg and under) and
truckload units are different products, excluded.

Radish changed standard in 2018 (18kg -> 20kg) with a 3% unit-price difference
across the transition, so the two are joined.

> **The value our target actually uses is 721.9 KRW** (mesh + pallet 10kg, 84%
> of volume). The 710.8 above is one example spec. The buying team could not
> reproduce our number on 2026-08-31 because they used 710.8. **Do not confuse
> the example with the filter.**

### A follow-on that was *not* a risk

Subclasses are also mixed — cabbage contains wrapped, imported and salad
varieties. We assumed this was a second version of the same problem. **It is
not.** Once the collector began storing `subclass_name`, we filtered and
measured:

```
item     current ACF(1)   subclass-filtered   volume removed
cabbage      0.928             0.928              1.1%
radish       0.940             0.940              1.3%
onion        0.987             0.988             22.2%   <- 22% removed, no change
```

**The spec incident was 0.085 -> 0.795. This is nothing.** Outlier subclasses are
tiny by volume (imported radish 22.6t vs stored radish 488t) and the
volume-weighted mean absorbs them. The decisive difference: in the spec case
**both the 1kg pack and the 10kg mesh bag had large volume.**

### Lesson

**When every feature fails, suspect the target before the features.** Check the
autocorrelation of what you are predicting. A series that does not predict
itself will not be predicted by anything else — and the signal had been sitting
in the data since 2015.

---

## A2. The calendar was perfect on history and wrong on the future

Found 2026-08-24. Full record: `트러블슈팅/20260824_*.md` §4

### Symptom

`ref_calendar` matched actual trading days for 2016-01 through 2026-08 with
**0 false positives and 0 misses**. Then we compared it against the Seoul
Agro-Fisheries Corporation's notice of trial Saturday closures:

```
2026-06-03 ok    2026-07-08 ok
2026-10-10 (Sat)  !! marked open
2026-11-07 (Sat)  !! marked open
2026-12-12 (Sat)  !! marked open
```

### Diagnosis

**The override table was derived from actual trading days.** That method can
only ever fill in **days that have already passed** — a future date has no
trading record to be absent from. Saturdays are open on the auction axis, so a
future Saturday closure passes through unnoticed.

**The training table was unaffected** — `target_dt` reached only 2026-02. This
was an error that **would only detonate once the batch started running**, and
then future lead times would have silently shifted by a day.

### A second, separate defect in the same table

Version 1 had also been validated against the wrong axis. There are **two**
calendars:

```
is_open     Garak auction trading days     3,348 days  (includes Saturdays)
is_survey   price survey days              2,700 days  <- what lead_biz_d needs
```

`lead_biz_d` counts **survey** days. The calendar had been checked against
**auction** days. Holidays were also hardcoded, and the 2028 Lunar New Year was
off by one day (01-26 instead of 01-27).

The closure rule itself was wrong: "Sunday + New Year + the day before through
the day after each traditional holiday" produced 18 false positives. Garak
actually **trades the day before a holiday and closes for three days from the
holiday itself.**

### Fix

```
closed = Sunday + Jan 1-2 + holiday .. holiday+2 + first Saturday of August
```

Two axes with separate sequence numbers, holidays from the government API, and
a clear division of labour:

```
past     actual trading days   <- authoritative, self-correcting
future   notice board          <- only 3-4 weeks out, checked monthly by a person
```

### Why the notice board cannot be automated

Most notices are **images**. The parser extracts dates from about half.

| Notice type | Machine-readable? |
|---|---|
| Trial closure, dates in the `alt` text | Yes |
| Summer/Chuseok, "vegetables end 7.31 evening" | Boundary dates only — a person must judge |
| Regular/New Year | "See the image for details" |

Summer and holiday notices state **auction start/end boundaries**, not closure
days; which days between them are closed depends on per-category auction hours.
So `watch_garak_notice.py` **prints the notices it could not parse, with URLs,
as "a human must read these"** rather than returning zero.

> **Returning 0 silently is the worst possible output.** It reads as "no
> closures."

### Lesson

**"Perfect on history" does not mean "correct for the future"** when the method
that fills the future differs from the record that validated the past. Write the
**scope of validity** next to every validation result.

---

## A3. The anchor and the target came from different aggregations

### Symptom

The retail model was quietly worse than it should have been.

### Diagnosis

`rtl_prc_lag1` (anchor) was a national average; `target_rtl_prc` was Seoul. The
model was being asked: **"here is yesterday's national price, predict today's
Seoul price."** A different, harder, and pointless problem.

Two independent reasons Seoul is required: the national retail survey grew from
**44 to 59 stores in 2023**, so train and validation would use different
aggregation bases; and since wholesale is Garak-based, retail must be the same
metropolitan area.

### Fix

`sgg_cd = '1101'` applied in **both** places inside the rebuild SQL. Verified
with 0 mismatches on 145,197 target rows and 8,094 anchor rows.

This had previously been a separate post-processing file, which was lost — so a
standalone rebuild silently reverted retail to the national average. It now
lives inside the main SQL, and validation query [12] checks it every rebuild.

> **Anchor lookups are as-of (latest value on or before the base date).**
> Comparing them against "calendar day −1" produces a false positive on every
> market holiday. We hit this while writing the check itself.

### Lesson

**An anchor and its target must come from the same aggregation** — same market,
grade and region. Changing one side is not a filter change; it changes the
question.

---

## A4. The auction target is pinned to the wrong calendar

Found 2026-08-25 while investigating the downstream contract; still open.

### Symptom

Auction forecasts are missing on Saturdays.

### Diagnosis

`target_auc_prc` is an **auction** price, but `lead_biz_d` counts **survey**
days. Garak auctions on Saturdays; the price survey does not.

| | Sunday | Saturday | Some holidays |
|---|---|---|---|
| Garak auction | closed | **open** (34 days in 2026) | **open** |
| Our forecast | none (correct) | **none (gap)** | **none (gap)** |

The mismatch runs both ways, very unevenly:

```
auction closed but we forecast    3 days / 244   (1.2%)
auction open and we do not         57 days       mostly Saturdays, 13.7% of volume
```

The three days in the first row can **never be scored** — there is no actual
value to compare against (2026-01-02, 02-19, 07-08).

### Status

Currently forward-filled and flagged. Moving the auction target onto the auction
axis is the correct fix and is a large change, tracked separately. Raised with
the buying team.

---

# B. We measured the wrong thing

## B1. The model could not beat the baseline

The first serious investigation, 2026-08-18. Full record: `트러블슈팅/20260818.md`

### Symptom

Training 2022-2024 / validating 2025:

| Configuration | Validation WMAPE | vs baseline |
|---|---|---|
| baseline (yesterday's price) | 0.1645 | — |
| LightGBM, absolute price target | 0.1699 | −3.3% |
| LightGBM, anchor-ratio target | 0.1640 | **+0.3%** |

+0.3% against a seed standard deviation of 0.0024 (about 1.5%) is **not
significant**.

### Diagnosis — three independent pieces of evidence

**① `best_iter` in single digits.**

```
seed 42: WMAPE 0.1639  (best_iter 12)
seed 43: WMAPE 0.1673  (best_iter  1)   <- one tree
seed 44: WMAPE 0.1627  (best_iter  6)
```

LightGBM normally stacks hundreds of trees. Stopping at 1-12 means validation
error started rising after a handful — **there was no signal to find.** A healthy
run gives three digits.

**② The effective sample was not the row count.**

```
training rows      13,230
distinct base dates    735   <- the real independent observations
rows per base date    18.0
```

Base-date features are identical across all 18 rows:

| Column | Distinct values per base date |
|---|---|
| `whsl_prc_lag1` | 1.00 |
| `whsl_prc_avg7` | 1.00 |
| `arr_qty_lag1` | 1.00 |
| `prod_area_temp_avg_lag1` | 1.34 |

**We were fitting 29 features to 735 samples.** 13,230 was an illusion.

**③ The learning curve was not monotone.**

| Train start | Base dates | WMAPE | vs baseline | Seed SD |
|---|---|---|---|---|
| 2024-01-01 | 244 | 0.1699 | −3.3% | 0.0017 |
| 2023-01-01 | 489 | 0.1555 | **+5.5%** | 0.0052 |
| 2022-01-01 | 735 | 0.1647 | −0.1% | 0.0024 |

**More data made it worse.** That is not a learning curve.

### Root cause — one hypothesis rejected, one confirmed

**Hypothesis A: the 2022 first-half missingness.** `arr_qty_prev_yr` is 72.3%
missing in the first half of 2022 because `daily_volume` starts 2021-05-29.
Tested over 5 seeds:

| Training window | Base dates | WMAPE | vs baseline |
|---|---|---|---|
| all 2022-2024 | 735 | 0.1641 ± 0.0019 | +0.3% |
| **excluding 2022 H1** | 614 | 0.1648 ± 0.0017 | **−0.2%** |
| 2023-2024 | 489 | 0.1551 ± 0.0044 | +5.7% |

Removing only the missing half did not help. **Rejected** — the problem is all
of 2022.

**Hypothesis B: year-to-year distribution heterogeneity.** Confirmed:

| Year | Mean | SD | Coefficient of variation |
|---|---|---|---|
| 2022 | 1,309 | 806 | **0.616** <- most volatile |
| 2023 | 1,179 | 521 | 0.442 |
| 2024 | 1,632 | 831 | 0.509 |
| **2025 (validation)** | 1,588 | 429 | **0.270** <- calmest |

**We were training on the most volatile year to predict the calmest one.**

### Fix

Extend training back to 2015, then measure the learning curve again. The result
settled at 2017 — **less data, better results**:

| Start | Base dates | Improvement | Seed SD |
|---|---|---|---|
| 2015 | 1,968 | +5.9% | 0.0014 |
| 2016 | 1,721 | +6.6% | **0.0029** |
| **2017** | **1,475** | **+6.8%** | **0.0007** |

Cabbage retail went 2,620 KRW (2015) -> 3,982 KRW (2016), a 52% jump; the early
period's market structure differs from today's.

### What was already right — recorded so it was not thrown away

Three signs the model was learning something real, even while losing:

**Directional accuracy rose monotonically with lead time**, 49% -> **65.6%**
(random is 50%). Short horizons leave no room — yesterday is already the answer;
long horizons let weather and planted area matter. **Exactly the structure we
had designed for.**

**It was better in volatile periods**: 0.2161 vs baseline 0.2232 (**+3.2%**) in
the top decile of volatility, versus −0.1% in calm periods. **That is the
commercially useful regime** — nobody needs a forecast when nothing moves.

**Feature importance reflected our data work**: `prod_area_gdd_sum30` at 11.1%
(built from the growing-region mapping we had corrected by measurement) and
`crop_area_yoy_rt` at 9.2%.

### Lesson

**Count effective samples, not rows.** And `best_iter` in single digits is a
diagnostic, not a hyperparameter — it means the signal is not there.

---

## B2. The pooled metric improved because one item is expensive

Found 2026-08-21. Full record: `트러블슈팅/20260821_*.md`

### Symptom

After expanding from 2 items to 4, baseline WMAPE went **0.2114 -> 0.0781**.
Lead time 1 read 0.0272 — implying vegetable prices move 2.7% a day, which is
not true of anything.

### Diagnosis

Row-level inspection showed the structure was **correct** — same base date, same
`lag1` across all 18 rows, target varying by lead time, Friday's lead-1 landing
on Monday. The data was fine.

Breaking out by item found it immediately:

| Item | Mean price | Own WMAPE | **Share of denominator** |
|---|---|---|---|
| **Garlic** | **6,244** | **0.0389** | **66.0%** |
| Onion | 1,135 | 0.0926 | 12.8% |
| Cabbage | 1,088 | **0.2135** | 12.3% |
| Radish | 801 | 0.1603 | 9.0% |
| | | **pooled 0.0781** | |

**Cabbage alone was 0.2135 — essentially unchanged from the old 0.2114.** The
data had not improved. The metric had changed meaning.

### Root cause

WMAPE divides a sum of errors by a sum of actuals, so **a high-priced item
automatically carries a large weight.** Garlic at 6,244 KRW/kg is 6-8x the
others and takes 66% of the denominator.

And garlic is the **easiest** item to predict:

| Item | Days the price changed | Days `lag1` equals the previous day |
|---|---|---|
| **Garlic** | **10.2%** | **94.4%** |
| Onion | 47.6% | 68.5% |
| Cabbage | 66.6% | 43.7% |
| Radish | 75.8% | 37.2% |

**Garlic is identical to yesterday on 19 days out of 20.** Harvested in June and
released from storage all year, so it moves in steps.

**The item with the biggest denominator and the smallest error dominated the
pooled number.**

### Fix

Never report a pooled WMAPE. Every evaluation breaks out by item. This also
raised the stakes on the anchor-ratio transform: with prices 6-8x apart, an
absolute-price target makes the model **optimize garlic error only**. In log
ratio every item becomes "plus or minus a few percent" on one scale.

### Lesson

**A weighted metric across heterogeneous groups reports the heaviest group.**
This recurs throughout the project — retail +11.8% was a national average
smoothing regional variation, and the band conditionality ratio of 1.15~1.52 was
an item artifact (F2).

---

## B3. A leakage alarm that was not leakage

### Symptom

The validation script flagged three columns:

```
[correlation check] |corr| > 0.995 suspected leakage
  whsl_prc_lag1   +0.9978  X
  whsl_prc_lag3   +0.9956  X
  whsl_prc_avg7   +0.9957  X
```

**We initially concluded "do not train"** and suspected a structural error where
target and anchor came from the same row.

### Diagnosis

Same cause as B2. Garlic is unchanged on 94% of days, so `whsl_prc_lag1` and
`target_whsl_prc` correlate near 1. **That is a property of the item, not
leakage.**

`validate_train_table.py` was written for a single item (cabbage) and produced
false positives on correlation and on region mapping once four items were
present.

### Lesson

**A validation tool has assumptions too.** When the context it was built for
changes, the tool has to change with it — otherwise it produces confident wrong
answers, which is worse than no check.

---

## B4. The scoring code was not applying the spec filter

Found 2026-08-31, four days after A1 was fixed.

### Symptom

Auction scores looked plausible and were being reported to the buying team.

### Diagnosis

The **target** was fixed on 08-27. **Scoring was not.** Predictions built on
spec-fixed prices were graded against the old mixed aggregate:
**25,866 of 34,905 rows (74%)** were scored against a different product.

Worst case: radish 2026-01-09, true value **521 KRW**, scored as **2,545 KRW**.

### Fix

Same filter applied to scoring; everything rescored (0 mismatches).

> **Every auction score produced before 2026-08-31 is void**, including numbers
> already sent to other teams.

### Lesson

**A definition change must be traced to every consumer of the definition.** We
changed how the target is built and forgot that something else independently
rebuilt the same value to grade against.

---

## B5. Experimental models were averaged into production performance

### Symptom

We reported cabbage auction error at **35.1%** and the D+14 buffer-breach rate
at **9%**, and concluded "cabbage is safe enough for an aggressive buying plan."

### Diagnosis

`prediction_log` contains both:

```
ops_auc      (underscore)   production
ops-auc-*    (hyphen)       experimental backtests, four variants (old/ung/bnd)
```

The filter matched both. Correct values: **19.7%** error, **57%** breach rate.

### Root cause of the damage

**The conclusion reverses.** Cabbage is not the safest of the three items — it is
**the worst**. We sent a correction to the buying team.

### Fix

Performance is measured from the sealed-holdout run, never from
`prediction_log`. A one-character difference in a model name separates two
completely different things.

### Lesson

**A log that mixes experiments with production is not a measurement source.** If
they must share a table, the filter has to be exact and verified.

---

## B6. The first real scoring said five of six were worse than the anchor

2026-08-25. Full record: `진행기록/실전채점_2026구간_20260825.md`
**The conclusion was later reversed.** The document is kept as a record of what
happens when you decide from one window.

### Symptom

The scoring pipeline ran end-to-end for the first time and produced:

| Target | Item | Rows | Model MAPE | Anchor MAPE | Improvement |
|---|---|---|---|---|---|
| Auction | radish | 496 | 41.25% | 29.64% | **−39.2%** |
| Auction | cabbage | 496 | 32.01% | 27.64% | **−15.8%** |
| Retail | radish | 512 | 6.86% | 6.41% | −7.0% |
| Retail | cabbage | 512 | 9.01% | 7.95% | −13.3% |
| Retail | onion | 512 | 10.48% | 10.49% | +0.1% |
| Wholesale | cabbage | 512 | 6.73% | 9.88% | **+31.9%** |

Retail had been **+15.1%** on validation 2023 and was now −7 to −13%.

### Three reasons the number could not be trusted — written at the time

**① The model was three and a half years out of date.** The bundle was the
experimental one (train 2017-2022, validate 2023), kept that way so early
stopping and ablation could work. The production configuration (train through
2023, `--fixed-iter`) had not been retrained yet. **This measured a model that
had never seen 2023-2025.**

**② It was 45 days of one summer.** The cabbage auction **anchor** MAPE was
27.6% — yesterday's price was that wrong, meaning the window itself was violent.
June-July is the highland transition and is always volatile. And with an
anchor-ratio target, high volatility inflates the variance of the ratio being
predicted, so the model degrades faster than the anchor. **Deciding from one
season repeats the one-fold illusion of E1.**

**③ The bands did not meet their nominal coverage.** `pred_lo`~`pred_hi` were
the validation-period q10-q90, nominally **80%**:

```
wholesale cabbage  100.0%   too wide
retail radish       93.9%
retail cabbage      85.5%
auction cabbage     68.8%   too narrow
auction radish      69.2%
retail onion        56.6%   badly too narrow
```

Shipping a 56.6% interval labelled "8 times out of 10" misleads a trading
decision.

### What it did establish

The pipeline genuinely ran, end to end, for the first time:
`predict_input -> predict.py -> load_predictions.py -> prediction_log -> score_predictions.py`.
5,184 rows loaded with no duplicates on re-run; 5,130 scored; the 72 rows with
no actual yet **left pending rather than filled with zero**; dummy rows excluded
automatically.

### What changed as a result

We **stopped and reordered the plan**: retrain in the production configuration
first, rescore, and score by season across 2026-01~08 rather than one window —
because *"automating now would print predictions worse than the anchor every
day."*

Re-measured properly (§B5's corrected figures and the sealed holdout), auction
cabbage is **+13.1%** in both holdout windows and retail is positive in all nine
cells.

### Lesson

**One window is one fold.** The same illusion that hit the school-calendar
feature hit the first production scoring, in a different disguise.

---

## B7. A blocked combination cannot be evaluated

Found 2026-09-04.

### Symptom

Wholesale onion showed "model 8.41% = anchor 8.41%" — apparently no better and
no worse.

### Diagnosis

`ref_prediction_quality` blocks certain combinations, and `predict.py` ships the
**anchor** for a blocked row. So `prediction_log` was comparing the anchor to
itself: **2,604 of 2,652 rows (98%)** in 2026 were substituted.

**Blocked, therefore unmeasurable; unmeasurable, therefore still blocked.**

### Fix

Re-measured with the gate off, as a daily shadow run. The result **reverses**:
wholesale onion is the **only** one of the three with all quarters positive
(+7.6 / +10.7 / +17.9%), while the two that were *not* blocked (radish −0.3%,
cabbage −1.9%) are the mixed ones.

> **When re-judging a block, you must turn the gate off.** The batch now runs
> `shadow_whsl_nogate` every day so the evidence accumulates.

---

# C. Rows disappeared and nothing turned red

**The hardest class to see. No value is wrong. Rows simply stop existing**, and
every dashboard stays green.

## C1. A pooled MAX hid three stalled items for eight months

Found 2026-09-03 by the ingest agent's first run.

### Symptom

Every source reported "current." Table-level latest dates were normal.

### Diagnosis

The collector asked for the latest date **once, for all six items pooled**:

```sql
SELECT MAX(exmn_ymd) FROM veg_daily_price_raw WHERE item_cd = ANY(...)
```

Cabbage was current, so the pooled answer was current, and **nobody ever
requested the gap for the items that had fallen behind.** Dried chili, unpeeled
garlic and peeled garlic had been frozen at 2026-08-24 for 10 days.

Behind that sat a second cause: the collector's default item list had been
**three items for eight months**. Restoring six would have immediately hit the
pooled-MAX bug.

### Fix

Per-item MAX, default list restored to six, a marker on lagging items. 929 rows
backfilled (dried chili 313, unpeeled garlic 63, peeled garlic 553).

### Lesson

**Never ask "is it current?" about a group.** The pooled answer is the healthiest
member. Our own check made the same mistake — see D7 ③.

---

## C2. The source renamed an item and rows silently stopped

This caught us **three times**.

**First — peeled garlic.** `깐마늘(국산)` does not match `item_nm IN ('마늘')`.

**Second — the collector, 2026-08-25.**

```
item_cd 241   through 2025 '고추'   ->  from 2026 '건고추'
item_cd 244   through 2025 '마늘'   ->  from 2026 '피마늘'
```

`collect_kamis.py` looked up the latest DB date **by name**, so it reported
"0 new rows" **while rows were loading**, and re-fetched eight months every run.

**Third — the rebuild SQL, 2026-09-03.** The warning was already written in our
own documentation. **The SQL had never been fixed.** `DBEAVER_run_v5.sql` still
filtered by name, so garlic silently ended at **2025-12-30** in the training
table while the other three ran to 2026-09.

### Fix

Filter by code in all four places, and **name the items ourselves**:

```sql
AND item_cd IN ('211','245','231','244')
CASE item_cd WHEN '211' THEN '배추' ... END AS item_nm
```

Verified: cabbage, radish, onion unchanged to the row (51,363 each); garlic
45,010 -> 47,017, now running to 2026-09-01.

Reference codes (measured 2026-08-25):
`211 cabbage · 231 radish · 241 dried chili · 244 unpeeled garlic · 245 onion · 258 peeled garlic`.
**244 and 258 are different products** with different margins (auction 3,398 ->
unpeeled wholesale 5,778 / peeled 7,385).

### Why fix it for an item we do not model

**Cabbage, radish and onion break identically if the source renames them** — and
then the anchor and the target both go empty while forecasts keep shipping.

### Lesson

**Never key on a label the source controls.** And a warning in a document is not
a fix — this one sat written and unapplied for over a week.

---

## C3. TRUNCATE order erased a post-processing step

### Symptom

Retail prices came back **100% NULL** after a rebuild.

### Diagnosis

`DBEAVER_run_v5.sql` truncates at the very top. A post-processing script run
**before** it was erased without a trace.

### Fix

Post-processing merged into the main SQL; a `STEP -1` guard runs before the
TRUNCATE; validation [12] fails loudly if retail reverts to the national
average. Rule: **post-processing runs after v5, never before.**

---

## C4. CRLF put a carriage return inside filenames

### Symptom

A backfill reported success. **137 prediction files were never saved.**

### Diagnosis

A date-list file had Windows line endings, so each date read as `2026-01-02\r`,
the output filename contained a carriage return, and the write went nowhere.

### Fix

`tr -d '\r'` on the input. Worth knowing generally on this repo: CRLF has
repeatedly broken multi-line text edits; the reliable method is normalize to LF,
edit, convert back.

---

## C5. The inverse transform was skipped

### Symptom

Predictions stored as values like `0.049`.

### Diagnosis

The model predicts a **log ratio**. Without the inverse transform the ratio
itself gets saved as a price.

```python
pred = anchor * np.exp(model.predict(X))
```

### Lesson

Any code path that produces a price must apply it. This is checked explicitly in
new batch code.

---

# D. It ran unattended and nobody was reading

Four of these were found on 2026-09-04, and they share one root cause: **the
check existed and its output went nowhere.**

## D1. Validation output was discarded

### Symptom

The batch reported success every morning.

### Diagnosis

The rebuild SQL ends with numbered validation queries. The batch executed the
file as one block and threw away every result set:

```python
cur.execute(sql)
while cur.nextset():
    pass          # <- validation results die here
```

They were visible only to a human running the file in a GUI. Check [14] had read
**100% mismatch for a week** (2026-08-27 to 09-04): a schema change added ten
derived columns, STEP 8 was not updated, and seven columns of the inference
input were entirely NULL.

### Fix

`verify_after_rebuild.sql` returns `(check_name, severity, bad, total, detail)`.
The batch reads it and **stops on any BAD row.**

**BAD is used sparingly** — four of six checks. Marking everything BAD looks
safer but produces an alarm that fires daily, which people learn to ignore, and
that is exactly the failure being fixed. Conversely, a check that is itself
broken does **not** stop the batch: dying while trying to notify must not block
the real work.

### Lesson

**"A check exists" and "a check is read" are different properties.** Design the
reader at the same time as the check.

---

## D2. The base date was one day stale for eight months

### Symptom

Forecasts shipped normally and looked reasonable.

### Diagnosis

A `base_dt = D` row reads data only through D−1 — it never uses D itself. But
STEP 8 built the axis from **days that had observations**, so `base_dt = D` only
appeared once D's survey arrived.

```
morning of 9/4    data present through 9/3
   what we made        base_dt 9/3, anchor from 9/2
   what it should be   base_dt 9/4, anchor from 9/3
```

**The anchor was a day old and the horizon a day short.** The buying team's
contract states `daily[0] == as_of + 1`; it had been quietly false, passing
**26 of 248 days**.

### Fix

A `px_ext` CTE inserts phantom base-date rows for survey days that have no price
yet — inside STEP 8 only. **The training table does not change by a single row.**
137 base dates backfilled.

### Lesson

**An off-by-one in an axis produces no wrong values, only wrong alignment**, and
alignment is invisible unless something explicitly checks it. The downstream
contract was the only thing that could have caught this, and nothing was
comparing against it.

---

## D3. The batch had not run at all

### Symptom

No failure alerts. Also no forecasts.

### Diagnosis

Alert file, desktop notification and webhook all existed and worked — for
**failures**. Nothing watched for **absence**. A **66-hour** gap
(2026-08-28 to 08-31) passed unnoticed.

### Fix

Flag gaps over 30 hours between successful push runs. It caught the 66-hour hole
on its first execution.

### Lesson

**A failure alerts; an absence does not.** Monitor the heartbeat, not only the
error.

---

## D4. A stale alert file made success look like failure

2026-08-27.

### Symptom

After a successful run, the system still showed "failing."

### Diagnosis

The alert file was written on failure and **never cleared on success**.

### Lesson

This is D1 in the opposite direction. **Both are the same bug** — state that only
moves one way. The dangerous version is the one that gets stuck on "fine."

---

## D5. The backfill loaded but never scored

### Symptom

Actual values stopped appearing in the dashboard from 1/14 onward. **We found
out because someone looked at the front end.**

### Diagnosis

Backfilling January by hand, we ran `load` and skipped `score`. In the batch the
two are joined; done manually, the second step was simply forgotten. 1,603 rows
filled in.

### The rows that remain unscorable

```
① actual not published yet (normal)      target dates 9/3, 9/4
② auction forecasts landing on non-auction days
     2026-01-02 · 02-19 · 07-08
     -> there is no actual, ever
```

② is the same root as A4.

### Lesson

**A manual run of an automated sequence drops steps.** If a pipeline stage exists
because it belongs to a sequence, running it alone needs the sequence written
down.

---

## D6. The drift rule flagged weeks the model had won

### Symptom

Drift alarms in weeks where the model was performing well.

### Diagnosis

The first rule was "flag a week whose error is 10 points above the 8-week
median." In a volatile week **everything** gets worse — model and baseline
together. Wholesale cabbage at **+3.8%** and **+29.0%** over the anchor were both
marked bad, because that week's baseline happened to be better still.

A ratio formulation was worse: **−263.9%** when the anchor sat at 4.0%.

### Fix

Measure **gain over the anchor**, in points:

```python
bad = [w for w in recent if (w["wmape"] - w["anchor"]) > gap_pp]
```

Thresholds: minimum 60 rows, 1.0 point gap, 3 consecutive weeks, 8-week
baseline.

### Lesson

**Drift is not "error went up." It is "the model lost ground it used to hold."**

---

## D7. Three mistakes made while building the checker

2026-09-03. Full record: `진행기록/수집검사_Q01_20260903.md` §3
**All three were the same traps documented elsewhere in this file.**

### ① One failing check silently killed the rest

```
check_lag fails (wrong column name)
  -> PostgreSQL rejects every later query in that transaction
  -> the other four checks all die
  -> and it printed "duplicates: normal"
```

**No rollback.** Same species as D4: a failure that renders as "fine."

### ② Natural keys written without checking — 1,068 + 1,323 false positives

```
auction: forgot subclass_code   -> 1,068 false duplicates
retail:  forgot mrkt_cd (store) -> 1,323 false duplicates
```

Retail surveys the same item on the same day at **several stores** — that is
normal. Auction rows split by subclass even within one spec. **We had confirmed
that same morning and then forgot it while writing the check.**

> **A false alarm every day teaches people to ignore the real one.**

### ③ Reading the table-level latest date and calling it normal

**Three items were 10 days stale and `check_lag` said "normal"**, because the
table-level max was current thanks to cabbage. A separate per-item check
(`check_item_lag`) was added and caught it.

This is C1 repeated **inside the tool built to catch C1.**

### And a fourth decision: block only what must be blocked

Initially any stalled item raised BAD and stopped the batch. That means
**an item we do not even model would stop the buying team's delivery table.**

```
211 · 231 · 245 (cabbage, radish, onion)   stalled -> BAD, stop the batch
anything else                              stalled -> WARN, notify only
```

### Why the thresholds are relative, not fixed

Normal missingness and incident missingness look identical to a fixed threshold:

```
sumRn (rainfall) missing 57.7%      normal — it does not rain every day
prod_area_temp 0% -> 30%            incident
```

Each check compares against **that column's own recent history**. Hand-written
thresholds turn into an endless exception list (*"62.2% is fine, actually"*).

---

# E. The experiment was valid, the conclusion was not

## E1. One validation year decided a feature

2026-08-24. Full record: `트러블슈팅/20260824_*.md` §1

### Symptom

A school-calendar feature (school-meal demand) looked clearly good on validation
2023:

```
auction  all 32 features   WMAPE 0.1763  +5.6%
         minus school (31) WMAPE 0.1799  +3.7%    loss +0.0036, SD 0.0014  -> significant
```

**+1.9 points**, past twice the seed SD. Wholesale agreed (+12.1% -> +13.2%). The
hypothesis was plausible: wholesale buyers are restaurants and school caterers,
so school holidays should hit demand directly.

### Diagnosis

Adding two more folds:

| Target | A (2023) | B (2022) | C (2021) | Sum | 2x SD |
|---|---|---|---|---|---|
| Auction | **+0.0036** | −0.0017 | +0.0027 | +0.0046 | 0.0028 |
| Wholesale | +0.0011 | −0.0014 | −0.0009 | −0.0012 | 0.0023 |
| Retail | −0.0002 | +0.0005 | −0.0005 | −0.0002 | 0.0012 |

**Signs disagree on all three targets.** One of nine cells is a clear positive.
**Rejected.**

### Why we almost fell for it

**① The model has no time-of-year feature at all.** `base_dt` and `target_dt` are
dropped and there is no month column. `school_open_ratio` is an annual profile
and **correlates +0.443 with month**. It may have been telling the model *"what
month is it"*, not *"is there school"*.

**② A plausible story reduces scrutiny.** The narrative fit so well that fold A's
significance felt like confirmation. **Wholesale — the target the story was about
— was the worst of the three.**

### Fix — the two-fold rule

> **Adopt or remove a feature only when the sign agrees across two folds and the
> sum exceeds 2x the seed standard deviation.** Never decide from one fold.

Refined three more times, each paid for by a mistake:

**① A verdict expires when conditions change.** An ablation from 08-24 said "no
change." Within three days the target definition changed (A1) and the anchor
changed. At the time cabbage auction was ACF 0.085, so "no change" may have meant
*"nobody can predict noise."* Re-run under production conditions, two group
verdicts moved. `ablation_ops.py` exists specifically to reproduce production
conditions; the older `ablation.py` cannot.

**② Do not decide on a bundled group. Split it.** Removing `calendar` whole was
negative on both folds — a removal candidate. Split, it was almost entirely one
member, appearing on **one fold only**:

```
bundled   A -0.0009 · B -0.0062    same sign -> remove
split     A +0.0004 · B -0.0056    signs disagree -> inconclusive
```

Small positives buried inside one large negative. (That group also contains
`lead_biz_d`; removing it whole would blind the model to lead time, so it was
never removable anyway.)

**③ Anything going to production must be checked on fold C.** On 2026-09-03,
**two candidates that passed two folds both reversed on fold C**:

```
share       A +0.0003 · B +0.0029 · C -0.0006    all the gain sat on fold B
mix_yr      A +0.0101 · B +0.0073 · C -0.0166    A and B agree; C is larger and opposite
```

`mix_yr` is the frightening one — it had **also reproduced on a disjoint seed
set**. Search on two folds; confirm survivors on three. The cost is small.

---

## E2. Missingness became a date identifier

### Symptom

A candidate feature with 36.6% coverage over the training window:

| Window | Coverage |
|---|---|
| Train 2017-2022 | **36.6%** |
| Validation 2023 | 97.5% |
| Test 2024-25 | 88.5% |

LightGBM handles NaN, so it runs fine — **and validation, at 97.5% coverage,
would have looked good.**

### Diagnosis

**The missingness itself is the signal "is this before September 2020?"** With
63% of training NULL and 2.5% of validation NULL, the model can learn
*"NULL means training data."*

Third instance of the same trap:

- **Economic variables** repeat one monthly value for a month. Removing them
  raised `best_iter` from 33-51 to **102-140** — they had been *causing early
  stopping*.
- **KREI planted area**: 75% missing, present for onion (1.4%) and absent for
  cabbage/radish/garlic (100%) — it would become an **item** identifier.
- **This one**: a **date** identifier.

A subtler fourth: the news sentiment index is a **daily** series and still
failed, because the model preferred its 30-day mean (importance 3.8-6.5%) over
the daily value (1.1-2.4%). Dropping only the 30-day mean removed the harm
(retail −0.0040 -> +0.0003).

### Fix

We first checked whether more data could be collected. The NEIS API opened
2019-04 and retains **only the two most recent school years** (verified by
direct call). So missingness could not be removed.

Instead, build a (month, day) median profile from the five observed years and
apply the same rule across 2015-2028. Every period now has the same character.
Leave-one-year-out: MAE **0.0315**, binary agreement on school days **96.7%** —
about 3% of signal traded away, and as a bonus the profile has values for future
lead times, which real observations never could.

(The feature was still rejected on its merits — E1.)

> **Sharpened rule.** Not just "monthly data becomes a date identifier" but
> **"any series becomes one if you smooth it long enough."** Feed news and search
> data as **ratios** (today / 7-day mean), never levels.

### Two data defects found while building it

The source CSVs had **file names that disagreed with their contents** — a file
labelled "October 2024" actually held 10/09-11/08, the trace of a 31-day
request window. Stitched together, **8 places totalling 45 days** are missing.
The profile is a per-year median so the impact is small; recorded and accepted.

**NEIS does not emit rows for Sundays**, so the measured Sunday open-ratio
median came out as 0.995 — "school is open." No practical impact (the survey
axis has no Sundays) but it poisons the profile, so Sundays are excluded from
the computation.

---

## E3. A new column silently changed the baseline

### Symptom

`train.py` uses every column not explicitly dropped:

```python
feats = [c for c in df.columns if c not in drop]
```

Rebuilding the table created `school_open_ratio`. **At that moment the settled
31-feature baseline became 32 with no warning**, invalidating the ablation
conclusion — and nobody would know.

### Fix

Default-exclude, enable by flag:

```python
SCHOOL_COLS = ["school_open_ratio"]
TARGET_DROP = { "auc": ECON|SCHOOL, "whsl": ECON|SCHOOL,
                "rtl": ECON|WEATHER|SCHOOL }
# included only with --with-school
```

**The opposite failure was blocked too.** If `--with-school` is passed and the
column is absent, it **stops** instead of continuing — otherwise you print
"school calendar included" and mistake a baseline result for a new one. Verified
by running all three targets on a 46-column CSV and confirming 31/31/24 features.

A related instance: while evaluating auction prices, wholesale columns sat in
the baseline candidate list. Different order of magnitude, so they always lost,
which made **"the anchor is the strongest baseline"** structurally true by
accident. Ten new derived baselines added 2026-09-03 are deliberately **excluded
from the inputs**: strongest as a yardstick, harmful as a feature.

---

## E4. Fold B disagreed five times — and it was not the fold's fault

**The single most useful methodological finding in the project.**

### Symptom

Across unrelated experiments, one fold kept producing the opposite sign:

| Date | Experiment | Fold B alone |
|---|---|---|
| 08-24 | school calendar | negative |
| 08-24 | `volume` ablation | negative |
| 08-26 | removing growing-region weather | opposite (+0.0086) |
| **08-31** | **replacing arrival volume with predictions** | **opposite, 6 of 6** |
| **08-31** | **train-on-actual / validate-on-predicted** | **opposite** |

The first two were recorded as "an oddity, investigate on a third occurrence."

### Diagnosis

**Fold B validates on 2022, the only fold containing a supply shock: Typhoon
Hinnamnor, 2022-09-06.** Cabbage auction went 1,237 -> 2,072 KRW from August to
September.

A table measured for a different purpose on 08-26 held the answer:

| 2022, cabbage | Arrival volume | Price |
|---|---|---|
| September | +47% | **+157%** |
| November | +102% | **−41%** |

**November is the normal inverse relationship. September is inverted.** The
typhoon damaged **quality** in the field, and our target is the top grade. Same
tonnage, different merchantability, different price.

```
normal   volume up   -> price down
shock    volume up   -> price up
```

### What this means

**We have one model learning both regimes.** That is the real reason signs flip
between folds. **It cannot be fixed by adding or removing features** — it needs
something that identifies the shock regime.

It also re-frames the earlier rejections: school calendar and `volume` were
negative on fold B, which may not mean "useless" but **"useless during a
shock."**

### Rule

> **When folds disagree, look at what happened that year before you suspect the
> feature.** Five times out of five it was the year.

---

## E5. Reproducibility does not validate the setup

2026-09-03.

### Symptom

A feature reproduced across **two disjoint seed sets** — normally strong
evidence.

### Diagnosis

The experiment tool's data builder had no item filter. **Garlic was 24% of the
training rows** — an item excluded from production precisely because its
wholesale price is unchanged on 94% of days.

### Fix

Verdicts from that tool were rolled back. `exp_quantile.build()` now prints its
item list on every call, and a new experiment begins by asking **"is this
training on the same data as production?"**

### Lesson

**Reproducing tells you it was not chance. It does not tell you that you
measured the right thing.** Two seed sets agree perfectly on a
wrongly-configured experiment.

---

## E6. A feature worth +1.67% disappeared at 20 seeds

### Symptom

Auction momentum features at 5 seeds: **+0.53 / +1.67 / +0.36**.

### Diagnosis

At 20 seeds: **−0.07 / −0.38 / +0.90**.

The same procedure caught a second case the same week: a `month` feature passed
on seeds 62-81 and **failed to reproduce** on the never-used seeds 82-101
(radish fold A flipped +0.0003 -> −0.0010, i.e. zero), while the *harm* to onion
reproduced in both sets. Not adopted.

### Lesson

**Improvement must exceed 2x the seed standard deviation.** Five seeds do not
estimate that spread well enough for a small effect. Same rule as E1, in the
seed dimension. **When one of many candidates passes, re-measure it on fresh
seeds** — this has now filtered three candidates.

---

## E7. Passed all three folds and reversed in production

2026-09-04.

### Symptom

Splitting onion into its own model passed everything:

```
fold A (6yr) +7.19% · B (5yr) +5.48% · C (4yr) +19.20%    sum +31.87 (needed 5.93)
```

### Diagnosis

Built under production conditions (7 years) and measured on 164 real 2026 base
dates:

| Item | Folds | 2026 production |
|---|---|---|
| Onion | +7.19 / +5.48 / +19.20% | **+2.67%** |
| Cabbage | mixed | **−5.70%** |
| Radish | mixed | +2.64% |
| **Pooled** | | **+0.08%** |

**The gain on onion is paid for by a loss on cabbage.**

### Root cause

**Folds train shorter than production.**

```
fold C 4yr · fold B 5yr · fold A 6yr · production 7yr
```

Onion needs more than five years before it beats its own anchor — its
autocorrelation is 0.963, so the anchor is very strong:

```
train 2017-2019 (3yr)   retail onion -43.0%   auction onion -16.7%
train 2017-2020 (4yr)          -16.3%                -16.5%
train 2017-2021 (5yr)          +13.5%                 +2.2%   <- flips here
```

**The longer the training, the more merging items helps.** Onion's advantage
shrinks and cabbage's loss appears.

### Fix — a fourth rule

> **A structural change must be built under production conditions and measured
> on the 2026 window before adoption.** Relative questions ("is feature A better
> than no A") are fine on folds — both sides train on the same span. Absolute
> questions ("where should the gate go", "split or merge") are not.

This was the **second** case that day; a lead-time-gate experiment had already
produced three mutually contradictory answers from folds, production records and
the sealed holdout, for exactly this reason. A shrinkage-λ experiment the same
day showed the same shape: optimal λ moved with training length (0.2 at 4 years,
0.4 at 6), and at production's 7 years λ=1 beat the anchor by +12.7%.

---

## E8. The comparison ran at the wrong hyperparameters

### Symptom

We reported that XGBoost beats LightGBM, then retracted it.

### Diagnosis

The comparison ran at 300 trees. Production uses 76.

| Trees | Fold A LGB / XGB | Fold B LGB / XGB |
|---|---|---|
| 50 | **0.1665** / 0.1686 | 0.1993 / 0.1996 |
| **76 (production)** | **0.1670** / 0.1688 | **0.1968** / 0.1971 |
| 300 | 0.1785 / **0.1760** | 0.1977 / **0.1960** |
| 1200 | 0.1855 / 0.1845 | 0.2049 / 0.2055 |

```
changing model family     0.1670 -> 0.1688   (1%)
choosing the wrong depth  0.1665 -> 0.1855   (11%)
```

At 300 trees both are already overfitting; XGBoost merely degrades more slowly.
**Tree count matters ten times more than model family.** CatBoost was clearly
worse on fold B (0.2069).

### Lesson

**Run a comparison at the operating point you actually use.**

---

## E9. The data clearly disagreed, and fixing it changed nothing

2026-09-03, the kimjang-season window.

### Symptom

The current kimjang window covered only half of the arrival-volume surge. That
is a real, measurable mismatch, and an obvious thing to fix.

### Diagnosis

We built the corrected window (`wide`) and measured it: **48 cells, all
inconclusive.** Performance did not change.

### Lesson

**"It looks wrong" and "fixing it helps" are different claims.** A mismatch
visible in the data is not automatically a modelling problem. Measure the fix,
not the mismatch.

---

# F. The number was right, the sentence was wrong

## F1. A direction claimed from two rows

### Symptom

We told the buying team the prediction band had narrowed from **0.676 to 0.544**.

### Diagnosis

That axis (auction, D+14, cabbage and radish) had **two rows** that day. The next
day the same five axes, on a new base date, were **all wider** (+8.9 to +21.2%).

**Both measurements were correct.** They were different days. Conditional bands
are *by definition* different every day, so a single day carries no direction.

### Fix — added to the working rules

> **Recording conditions is not enough. Record the sample count next to the
> conditions, and do not state a direction when the count is in single digits.**

---

## F2. Three teams inferred the band method from its width

### Symptom

Which band method produced a row was being reconstructed from the width.
**Three teams did this and all three got it wrong**, us included.

A related illusion: the fixed table's conditionality ratio looked like 1.15~1.52
pooled, suggesting it did respond to conditions. Measured **per item** it is
**exactly 1.00** — width was a function of (item x lead time) only. Radish has
wide bands and high volatility, onion narrow bands and low volatility, so the
item difference impersonated conditionality. **B2 again, in another dimension.**

### Fix

A `band_method` column (`quantile` / `fixed_table` / `none`) written when the row
is produced and carried downstream.

### Lesson

**Record how a value was produced at the moment you produce it.**

---

## F3. A backlog claim that had never been measured

2026-09-03.

### Symptom

The backlog stated: *"the kimjang period shifts one to two weeks each year with
temperature."* An experiment was designed around that premise.

### Diagnosis

Measured from the peak cabbage arrival week:

| Year | Peak week | Week starting |
|---|---|---|
| 2017 | 48 | 11-27 |
| 2018 | 47 | 11-19 |
| 2019 | 48 | 11-25 |
| 2020 | 48 | 11-23 |
| 2021 | 47 | 11-22 |
| 2022 | 47 | 11-21 |
| 2023 | 48 | 11-27 |
| 2024 | 47 | 11-18 |
| **2025** | **43** | **10-20** |

**Eight of nine years sit in weeks 47-48.** Only 2025 departs. The claim was
written more strongly than the data supports.

### Lesson

**Verify the premise before designing the experiment**, including premises
written in our own documents. Otherwise you carefully fix the wrong thing.

---

## F4. Predictions barely move across the horizon

2026-08-31. This one is **real**, and the obvious interpretation is wrong.

### Symptom

Within one base date, how much does the forecast move from lead 3 to lead 18?
(152 base dates)

| Target | Item | Forecast range | Actual range | Ratio |
|---|---|---|---|---|
| Auction | cabbage | 13.7% | **137.8%** | **0.10** |
| Auction | radish | 14.0% | 47.7% | 0.29 |
| Auction | onion | 12.1% | 34.7% | 0.35 |
| Wholesale | cabbage | 11.3% | 15.0% | 0.75 |
| Retail | onion | 2.5% | 15.6% | 0.16 |

**When reality moves 10, the forecast moves 1 to 7.** And the small movement is
not even directionally right — direction correlation 0.192 (wholesale cabbage),
0.007 (auction onion), **−0.063** (auction radish, i.e. backwards).

### Diagnosis

It is in the inputs:

```
of 28 model inputs
  17  identical across all 18 rows of a base date
  11  vary, but 6 of those change only once or twice
```

Inputs that genuinely vary across the horizon carry a **combined importance of
22.4%**. The other 77.6% say the same thing whether the target date is January 2
or January 27.

### Why this is not "the model being lazy"

> If nothing in the inputs says what will happen on January 14, then **the
> least-wrong answer available is "similar to today."** Forcing the curve to
> oscillate makes accuracy worse, not better. The uncertainty is carried by the
> band, and the bands do hold 76-85%.

### Lesson

**A flat forecast can be the correct response to flat information.** The fix is
not a penalty term; it is an input that varies with the target date. Four
attempts at that (normal temperature on the target date, medium-range forecast,
predicted arrival volume, mismatched train/validate) all failed — and three of
them failed *only on fold B*, which is how E4 was found.

---

# G. Working with another team

## G1. Our clone of their repository was 12 days stale

2026-08-25.

### Symptom

Their repo looked like a 29-file deployment skeleton. We nearly wrote an
integration design against it.

### Diagnosis

`git fetch` showed 24 remote branches. All real work was on `dev`.

| | main | dev |
|---|---|---|
| Files | 29 | **155** |
| Last commit | 08-13 | **08-25 (that day)** |
| Contributors | 2 | **5, 81 commits** |

It is a LangGraph multi-agent system. Notably, their Critic runs a **different
model** from the orchestrator, on the stated grounds that *"the same model would
approve its own explanation"* — a boundary we should respect in our own agent
design (and did: our checks decide by rule, never by model).

### Lesson

**Fetch before you read.** A default branch is not the project.

---

## G2. Four contract mismatches, one of them a design problem

Full record: `진행기록/타파트연동_조사_20260825.md` §3

Their code already defines our slot:

```python
def get_forecast(item: str, as_of: date) -> dict:
    """Garak auction price forecast, 18 days. (supplier: ML)"""
```

**① Their uncertainty threshold assumes an accuracy nobody has.** ★

`ci_width = (upper − lower) / predicted >= 0.08` classifies a day as
"uncertain", which removes the aggressive buying plan.

| Item | Our ci_width at LT14 | Their mock | Threshold |
|---|---|---|---|
| Cabbage | **0.73** | 0.03~0.12 | 0.08 |
| Radish | **0.65** | | 0.08 |
| Onion | **0.40** | | 0.08 |

**We suspected our own bands first** and measured the actual error separately:

```
D+14 absolute error   mean  cabbage 21.1% · radish 24.0% · onion 18.1%
                      p80   cabbage 27.6% · radish 34.2% · onion 28.2%
```

**The bands are not inflated — the error really is that large.** A threshold of
0.08 presumes ±4% error, which is unreachable 14 days out. It appears to have
been calibrated against mock data. Connected as-is, **every day would be
"uncertain" from day one and the aggressive plan would never appear.**

Their mock also holds `ci_width` constant across 18 days (deliberately — the
README explains that judging on one day makes the verdict flip silently as the
base date moves), whereas ours **doubles from 0.42 at LT1 to 0.83 at LT18**.

**② Business days vs calendar days.** Their contract is consecutive calendar days
D+1..D+18 and their code indexes `daily[13]` as D+14, with the test name
`..._is_the_fourteenth_calendar_day`. Our `lead_biz_d` counts business days:
our LT1-18 spans **24-26 calendar days**, so an 18-day horizon is a surplus, not
a shortfall — but **4 days inside their window are blank** (2 Saturdays, 2
Sundays).

**③ Their D+14 decision day is empty 10.8% of the time.** Because 14 = 2x7 it
always lands on the same weekday as the base date, so never on a weekend
(0 of 157). But on **17 of 157** it fell on a public holiday, many of which are
days when **the auction opens and the survey does not**.

**④ Item mismatch.** Their contract lists four items including unpeeled garlic;
we exclude garlic. The other three are available now.

### Lesson

**A downstream threshold is an assumption about your accuracy.** Check it against
your measured error before you connect, not after. And **suspect your own side
first** — we did, and it was still their threshold.

---

# The short version

If you read nothing else:

1. **When every feature fails, check the target's autocorrelation.** (A1)
2. **"Perfect on history" is not "correct for the future."** Write the scope of
   validity next to every validation result. (A2)
3. **An anchor and its target must come from the same aggregation.** (A3)
4. **Count effective samples, not rows.** (B1)
5. **Break every metric out per item.** A weighted metric reports the heaviest
   group. (B2)
6. **A definition change must be traced to every consumer of it.** (B4)
7. **Never decide from one fold, one seed set, one season, or one day.**
   (E1, E6, B6, F1)
8. **When folds disagree, look at what happened that year.** (E4)
9. **Reproducing a result does not validate the setup that produced it.** (E5)
10. **Never key on a label the source controls.** (C2)
11. **Never ask "is it current?" about a group.** (C1, D7)
12. **A check that exists is not a check that is read.** Before writing a check,
    answer *"if this fails, who finds out, and when?"* If the answer is "someone
    opens the file", it is not a check. (D1)
13. **A failure alerts; an absence does not.** (D3)
14. **Missing rows are harder to see than wrong values.** (C1-C3)
15. **A false alarm every day teaches people to ignore the real one.** (D7)
16. **Verify the premise before designing the experiment** — including premises
    in your own documents. (F3)
17. **Record how a value was produced when you produce it.** (F2)
18. **Write the sample count next to the conditions.** (F1)
19. **A downstream threshold is an assumption about your accuracy.** (G2)
