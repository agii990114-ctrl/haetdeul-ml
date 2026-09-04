# Troubleshooting Casebook

Haetdeul Nongsan — ML price forecasting · written 2026-09-04 21:04

**What this is.** Every real failure in this project, with how it looked, what
it actually was, and what we changed. Written in English as a companion to the
Korean files in this folder (`20260818.md`, `20260821_*.md`, `20260824_*.md`),
which cover only the first three cases in depth. Later incidents live in
`진행기록/` and are collected here for the first time.

**Why keep the wrong answers in.** Several entries below record a number we
reported and then had to retract. The retraction is the useful part — it is what
tells the next person which mistake is easy to make.

---

## Quick index

| # | Symptom as it appeared | What it actually was | Class |
|---|---|---|---|
| 1 | Model cannot beat the baseline | Effective sample was 6x smaller than the row count | Evaluation |
| 2 | Baseline improved from 0.2114 to 0.0781 | One expensive item dominated the denominator | Evaluation |
| 3 | A feature looked clearly good | Only one validation year had been checked | Method |
| 4 | A feature with 36.6% coverage | Missingness itself became a date identifier | Leakage |
| 5 | Adding a column changed results everywhere | The new column silently entered the baseline | Method |
| 6 | Calendar validated perfectly | It was validated against the wrong axis | Definition |
| 7 | **Auction target unpredictable at any horizon** | **15 packaging specs averaged together** | **Definition** |
| 8 | Scores looked plausible | 74% of rows scored against a different product | Evaluation |
| 9 | Cabbage error 35.1%, breach rate 9% | Experimental models averaged into production records | Evaluation |
| 10 | Retail prices 100% NULL after a rebuild | Post-processing ran before the TRUNCATE | Pipeline |
| 11 | Predictions stored as 0.049 | The inverse transform was skipped | Pipeline |
| 12 | Retail model quietly worse | Anchor was national, target was Seoul | Definition |
| 13 | "0 new rows" while rows were loading | Item lookup keyed on a name the source renamed | Silent loss |
| 14 | All sources reported current | A pooled MAX hid three stalled items for 8 months | Silent loss |
| 15 | A result reproduced on two seed sets | The tool was training on 24% garlic | Method |
| 16 | Batch green every morning | Validation output was discarded; [14] failed for a week | Unattended |
| 17 | Forecasts shipping normally | Base date one day stale for eight months | Unattended |
| 18 | Drift alarm on healthy weeks | Drift measured as raw error, not gain over anchor | Monitoring |
| 19 | No failure alerts | The batch had not run at all for 66 hours | Monitoring |
| 20 | 137 predictions silently not saved | CRLF in a text file put `\r` inside filenames | Pipeline |
| 21 | "Still failing" after a successful run | The alert file was never cleared | Monitoring |
| 22 | Band width told us the method | Three teams inferred it and all three were wrong | Contract |
| 23 | "The band narrowed" | That axis had two rows that day | Reporting |
| 24 | XGBoost beats LightGBM | Compared at 300 trees; production uses 76 | Method |
| 25 | A feature worth +1.67% | Gone at 20 seeds | Method |
| 26 | Passed all three folds | Reversed under production training length | Method |

---

# A. Definition failures — the data did not mean what we thought

## Case 7. The auction target was a mixture of 15 packaging specs

**The largest failure in this project.** Found 2026-08-27.

### Symptom

No feature improved auction-price prediction. Not weather, not arrival volume,
not calendar. Grades were inverted — the "special" grade was cheaper than the
grade below it on **737 of 815 days**. We had spent weeks assuming a modelling
problem.

### Diagnosis

We pulled one item, one market, one day and looked at the raw transactions
instead of the aggregate. Garak cabbage, special grade, 2026-08-03:

```
mesh bag 10kg      710.8 KRW/kg    79% of volume
pallet   10kg      870.0 KRW/kg     6% of volume
box       4kg    5,841.3 KRW/kg
box       1kg   11,223.7 KRW/kg               <- a retail small pack
[weighted mean]    938.5 KRW/kg               <- what our target was
```

**Fifteen specs in one day.** The source API returns individual transactions and
price depends on packaging; our collector aggregated by
(date, market, item, grade) and averaged **different products** into one number.

| Metric | Mixed | Spec-fixed |
|---|---|---|
| Autocorrelation ACF(1), cabbage | **0.085** | **0.795** |
| Coefficient of variation | 0.919 | 0.354 |
| Intraday min/max ratio | 132.7x | 9.7x |
| Grade inversion | 737 / 815 days | resolved |

### Root cause

**ACF(1) = 0.085 is white noise.** Yesterday's value said almost nothing about
today's. We were asking the model to predict an unpredictable series. **No
feature could ever have helped**, which is exactly what the ablation results had
been telling us for weeks — we read them as "these features are useless" instead
of "this target is noise."

### Fix

Pin the weight, not the packaging: cabbage 10kg, radish 18kg (through 2018) then
20kg, onion 15kg. Mesh, pallet and PE sack at the same weight are the same
product moved differently, so they combine by volume weight. Small packs (8kg
and under) and truckload units are different products and are excluded.

Radish changed packaging standard in 2018 (18kg -> 20kg) with a 3% unit-price
difference across the transition, so the two are joined.

### Lesson

**When every feature fails, suspect the target before the features.** Check the
autocorrelation of what you are predicting. A series that does not predict
itself will not be predicted by anything else, and the signal was visible in
data going back to 2015.

---

## Case 6. The calendar was perfect on history and wrong on the future

### Symptom

`ref_calendar` v1 passed validation against historical trading records, then
produced wrong lead times for future base dates.

### Diagnosis

**There were two calendars, and we had built one.**

```
is_open     Garak auction trading days     3,348 days  (includes Saturdays)
is_survey   price survey days              2,700 days  <- what lead_biz_d needs
```

`lead_biz_d` counts **survey** days, but the calendar had been validated against
**auction** days. It also hardcoded holiday dates, and the 2028 Lunar New Year
was off by one day (01-26 instead of 01-27).

The original closure rule was wrong too: "Sunday + New Year + the day before
through the day after each traditional holiday" gave 18 false positives. Garak
actually **trades the day before a holiday and closes for three days from the
holiday itself.**

### Fix

Two axes with separate sequence numbers (`open_seq`, `survey_seq`). Holidays
derived from the government API rather than hardcoded. Corrected rule:

```
closed = Sunday + Jan 1-2 + holiday through holiday+2 + first Saturday of August
```

Result over 2016-2026: **0 false positives, 14 misses** (1.3 per year, all
non-scheduled) handled by an override table.

**Non-scheduled closures are found from trading, not from notices.** We query
"the rules say open but zero trades happened" and get 14 hits with **0 false
positives and 0 misses**. Notice-board posts are mostly images. The notice
watcher now only checks future dates, monthly — and in that role it found three
scheduled trial closures in late 2026 that the calendar had marked open.

### Lesson

**Passing validation on history proves nothing about the future** when the rule
that generates the future is different from the record that validated it. Ask
what axis your counter actually counts.

---

## Case 12. The anchor and the target came from different aggregations

### Symptom

The retail model was quietly worse than it should have been.

### Diagnosis

`rtl_prc_lag1` (the anchor) was a national average; `target_rtl_prc` was Seoul.
The model was being asked: **"here is yesterday's national price, now predict
today's Seoul price."** That is a different, harder, and pointless problem.

There was a second reason Seoul is required: the national retail survey grew
from **44 to 59 stores in 2023**, so training and validation would use different
aggregation bases. And since wholesale prices are Garak-based, retail has to be
the same metropolitan area.

### Fix

`sgg_cd = '1101'` applied in both places inside the rebuild SQL. Verified with
0 mismatches on 145,197 target rows and 8,094 anchor rows.

Historically this had been a separate post-processing file, which was lost — so
a standalone rebuild silently reverted retail to the national average. It is now
inside the main SQL, and validation query [12] checks it on every rebuild.

### Lesson

**An anchor and its target must come from the same aggregation** — same market,
same grade, same region. Changing one side of the pair is not a filter change;
it changes the question.

---

# B. Evaluation failures — we measured the wrong thing

## Case 8. The scoring code was not applying the spec filter

Found 2026-08-31, four days after Case 7 was fixed.

### Symptom

Auction scores looked plausible and were being reported to the buying team.

### Diagnosis

The **target** was fixed on 08-27. The **scoring** query was not. So predictions
built on spec-fixed prices were being graded against the old mixed aggregate:
**25,866 of 34,905 rows (74%)** were scored against a different product's price.

Worst case: radish on 2026-01-09, true value **521 KRW**, scored as **2,545 KRW**.

### Fix

Same filter applied to scoring; everything rescored (0 mismatches).

> **Every auction score produced before 2026-08-31 is void.** That includes
> numbers already sent to other teams.

### Lesson

**A definition change has to be traced to every consumer of the definition**,
not just the producer. We changed how the target is built and forgot that
something else independently rebuilt the same value to grade against.

---

## Case 9. Experimental models were averaged into production performance

### Symptom

We reported cabbage auction error as **35.1%** and the D+14 buffer-breach rate
as **9%**, and concluded "cabbage is safe enough for an aggressive buying plan."

### Diagnosis

The numbers came from `prediction_log`, which contains both:

```
ops_auc     (underscore)   production
ops-auc-*   (hyphen)       experimental backtests, four variants including old/ung/bnd
```

The filter matched both. Four experimental models were averaged into the
production figure.

Correct values: **19.7%** error and **57%** breach rate.

### Root cause of the damage

**The conclusion reverses.** Not "cabbage is the safest, run an aggressive
plan" — cabbage is **the worst of the three items**. We had to send a correction
to the buying team.

### Fix

Performance is measured from the sealed-holdout run, never from
`prediction_log`. A one-character difference in a model name separates two
completely different things.

### Lesson

**A log that mixes experiments with production is not a measurement source.**
If experiments and production must share a table, the filter has to be exact and
verified — and a name differing by one character is not a safe distinction.

---

## Case 2. The pooled metric improved because of an expensive item

### Symptom

A baseline "improved" from 0.2114 to 0.0781. Correlation of 0.9978 also looked
excellent.

### Diagnosis

WMAPE is volume/value weighted. Garlic at 6,244 KRW/kg was **66% of the
denominator**. Pooling four items meant garlic decided the number, and the
cheap items — the ones we actually trade — were invisible in it.

### Fix

**Every evaluation is broken out per item.** The pooled figure is never used to
make a decision.

### Lesson

**A weighted metric across heterogeneous groups reports the heaviest group.**
This one recurs: retail +11.8% was also a national average smoothing out
regional variation, and the conditional-band ratio of 1.15~1.52 was also an
artifact of item differences, not conditionality (Case 22).

---

## Case 1. The model could not beat the baseline

The first serious investigation, 2026-08-18.

### Symptom

Three-target models sat at or below baseline no matter what we changed.

### Diagnosis — three independent pieces of evidence

**`best_iter` was in single digits (1-12).** The model stopped after a handful
of trees, which means there was nothing to learn.

**The effective sample was not the row count.** 190,243 rows looked like plenty,
but one base date expands to up to 72 rows (4 items x 18 lead times). The real
sample was **2,698 base dates**, and the training window held **1,475**.

**The learning curve was not monotone.** More data did not mean better results.

### Root cause

Distributional heterogeneity across years. Cabbage retail went 2,620 KRW (2015)
-> 3,982 KRW (2016), a 52% jump; the early period's market structure differs
from today's.

### Fix

Start training at 2017 — **less data, better results**:

| Start | Base dates | Improvement | Seed SD |
|---|---|---|---|
| 2015 | 1,968 | +5.9% | 0.0014 |
| 2016 | 1,721 | +6.6% | **0.0029** |
| **2017** | **1,475** | **+6.8%** | **0.0007** |

2017 wins on both improvement and stability, independently for auction and
retail.

### Lesson

**Count your effective samples, not your rows.** And `best_iter` in single
digits is a diagnostic, not a hyperparameter to tune — it means the signal is
not there.

---

# C. Silent data loss — nothing was wrong, rows were just missing

These are the hardest failures to see. **No value is incorrect. Rows simply stop
existing**, and every dashboard stays green.

## Case 14. A pooled MAX hid three stalled items for eight months

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

Behind that sat a second cause: the collector's default item list had been three
items for **eight months**, and nobody had noticed. Restoring six items would
have immediately hit the pooled-MAX bug.

### Fix

Per-item MAX, default list restored to six, and a `*` marker on items that lag.
929 rows backfilled. The ingest agent now checks per-item staleness before every
rebuild.

### Lesson

**Never ask "is it current?" about a group.** The pooled answer is the healthiest
member. Our own check made the same mistake — the table-level latest date read
"normal" the whole time.

---

## Case 13. The source renamed an item and rows silently stopped

This one caught us **three times**.

### First: peeled garlic

`깐마늘(국산)` does not match `item_nm IN ('마늘')`. Filtering by name dropped it.

### Second: the collector, 2026-08-25

```
item_cd 241   through 2025 '고추'   ->  from 2026 '건고추'
item_cd 244   through 2025 '마늘'   ->  from 2026 '피마늘'
```

`collect_kamis.py` looked up the latest DB date **by item name**. The name no
longer matched, so it reported "0 new rows" **while rows were actually
loading**, and re-fetched eight months of data every run.

### Third: the rebuild SQL, 2026-09-03

The warning was written in our own documentation. **The SQL had never been
fixed.** `DBEAVER_run_v5.sql` still filtered `item_nm IN ('배추','양파','무','마늘')`,
so garlic silently ended at **2025-12-30** in the training table while the other
three ran to 2026-09.

### Fix

Filter by code in all four places, and **name the items ourselves**:

```sql
AND item_cd IN ('211','245','231','244')
CASE item_cd WHEN '211' THEN '배추' ... END AS item_nm
```

Verified: cabbage, radish and onion unchanged to the row (51,363 each); garlic
45,010 -> 47,017 and now runs to 2026-09-01.

### Why we fixed it even though we do not model garlic

**Cabbage, radish and onion break identically if the source renames them** — and
then the anchor and the target both go empty while forecasts keep shipping.

### Lesson

**Never key on a label the source controls.** And a warning in a document is not
a fix: this one was written down and left unapplied for over a week.

---

## Case 10. TRUNCATE order wiped a post-processing step

### Symptom

Retail prices came back **100% NULL** after a rebuild.

### Diagnosis

`DBEAVER_run_v5.sql` truncates its tables at the very top. A post-processing
script that had been run **before** it was erased without a trace.

### Fix

Post-processing merged into the main SQL. A `STEP -1` guard runs before the
TRUNCATE. Validation [12] fails loudly if retail reverts to the national
average, and the rule is written down: **any post-processing runs after v5,
never before.**

---

## Case 20. CRLF put a carriage return inside filenames

### Symptom

A backfill reported success. **137 prediction files were not saved.**

### Diagnosis

A date list file had Windows line endings. Each date read as `2026-01-02\r`, so
the output filename contained a carriage return and the write silently went
nowhere.

### Fix

`tr -d '\r'` on the input. Worth knowing on this repo generally: CRLF has also
broken multi-line text edits repeatedly, and the working method is to normalize
to LF, edit, and convert back.

---

# D. Unattended operation — the batch ran, nobody was reading

Three failures found on 2026-09-04, all with the same root cause: **the check
existed and its output went nowhere.**

## Case 16. Validation output was discarded

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

They were visible only to a human running the file in a database GUI. Check [14]
had been reporting **100% mismatch for a week** (2026-08-27 to 09-04): a schema
change added ten derived columns and STEP 8 was not updated, leaving seven
columns entirely NULL in the inference input.

### Fix

`verify_after_rebuild.sql` returns
`(check_name, severity, bad, total, detail)`. The batch reads it and **stops on
any BAD row.**

**BAD is used sparingly** — four of six checks. Marking everything BAD looks
safer but produces an alarm that fires daily, which people learn to ignore, and
that is precisely the failure being fixed. Conversely a check that is itself
broken does **not** stop the batch: dying while trying to notify must not block
the real work.

### Lesson

**"A check exists" and "a check is read" are different properties.** Design the
reader at the same time as the check.

---

## Case 17. The base date was one day stale for eight months

### Symptom

Forecasts shipped normally and looked reasonable.

### Diagnosis

A `base_dt = D` row reads data only through D−1 — it never uses D itself. But
STEP 8 built the axis from **days that had observations**, so `base_dt = D` only
appeared once D's survey data arrived.

```
morning of 9/4    data present through 9/3
   what we made   base_dt 9/3, anchor from 9/2
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

## Case 19. The batch had not run at all

### Symptom

No failure alerts. Also no forecasts.

### Diagnosis

Alert file, desktop notification and webhook all existed and all worked — for
**failures**. Nothing watched for **absence**. A gap of **66 hours**
(2026-08-28 to 08-31) passed unnoticed.

### Fix

Flag gaps over 30 hours between successful push runs. It caught the 66-hour hole
on its first execution.

### Lesson

**A failure alerts; an absence does not.** Monitor the heartbeat, not only the
error.

---

## Case 21. A stale alert file made success look like failure

### Symptom

After a successful run, the system still showed "failing."

### Diagnosis

The alert file was written on failure and **never cleared on success.**

### Lesson

This is Case 16 in the opposite direction. **Both failure modes are the same
bug**: state that only ever moves one way. The dangerous version is the one that
gets stuck on "fine."

---

## Case 18. The drift rule flagged weeks the model had won

### Symptom

Drift alarms on weeks where the model was performing well.

### Diagnosis

The first rule was "flag a week whose error is 10 points above the 8-week
median." In a volatile week **everything** gets worse — the model and the
baseline together. Wholesale cabbage at **+3.8%** and **+29.0%** over the anchor
were both marked bad, because that week's baseline happened to be better still.

A ratio formulation was worse: it blew up to **−263.9%** when the anchor sat at
4.0%.

### Fix

Measure **gain over the anchor**, in points, not raw error:

```python
bad = [w for w in recent if (w["wmape"] - w["anchor"]) > gap_pp]
```

Thresholds: minimum 60 rows, 1.0 point gap, 3 consecutive weeks, 8-week
baseline.

### Lesson

**Drift is not "the error went up." It is "the model lost ground it used to
hold."** In a volatile market the first is normal and the second is not.

---

# E. Method failures — the experiment was valid and the conclusion was not

## Case 3. One validation year decided a feature

### Symptom

A school-calendar feature (meal demand) looked clearly good: **+0.0036** on
auction with validation 2023. Reported as "+3.7% -> +5.6%."

### Diagnosis

Adding folds reversed it:

| Target | A (valid 2023) | B (valid 2022) | C (valid 2021) | Sum | 2x SD |
|---|---|---|---|---|---|
| Auction | **+0.0036** | −0.0017 | +0.0027 | +0.0046 | 0.0028 |
| Wholesale | +0.0011 | −0.0014 | −0.0009 | −0.0012 | 0.0023 |
| Retail | −0.0002 | +0.0005 | −0.0005 | −0.0002 | 0.0012 |

Signs disagree on all three targets; 1 of 9 cells is a clear positive. The
hypothesis had been that wholesale buyers are restaurants and school caterers —
and wholesale is **the worst of the three**.

### Fix — the two-fold rule

> **Adopt or remove a feature only when the sign agrees across two folds
> (validate 2022 and validate 2023) and the sum exceeds 2x the seed standard
> deviation.** Never decide from one fold.

Later refined three more times, each paid for by a mistake:

**① A verdict expires when conditions change.** An ablation from 08-24 said "no
change." Within three days the target definition changed (Case 7) and the anchor
changed. At the time cabbage auction was ACF 0.085, so "no change" may have
meant *"nobody can predict noise."* Re-run under production conditions, two
group verdicts moved.

**② Do not decide on a bundled group.** Removing the `calendar` group whole was
negative on both folds — a removal candidate. Split, it was almost entirely one
member, appearing on **one fold only**:

```
bundled   A -0.0009 · B -0.0062    same sign -> remove
split     A +0.0004 · B -0.0056    signs disagree -> inconclusive
```

Small positives had been buried inside one large negative. (That group also
contains `lead_biz_d`; removing it whole would have made the model blind to lead
time, so it was never removable to begin with.)

**③ Anything going to production must be checked on a third fold.** On
2026-09-03 **two candidates that passed two folds both reversed on fold C**:

```
share       A +0.0003 · B +0.0029 · C -0.0006    all the gain was on fold B
mix_yr      A +0.0101 · B +0.0073 · C -0.0166    A and B agree, C is larger and opposite
```

Cost is negligible — search on two folds, confirm the survivors on three.

> **Why fold B keeps being the exception.** Fold B validates on 2022, the only
> fold containing a supply shock: **Typhoon Hinnamnor, 2022-09-06.** Cabbage
> auction went 1,237 -> 2,072 KRW between August and September. So features
> rejected because they were negative on fold B may not be useless — they may be
> **useless outside a shock**. When folds disagree, first ask what happened that
> year.

---

## Case 26. Three folds passed and production reversed

### Symptom

Splitting onion into its own model passed everything:

```
fold A (6yr) +7.19% · B (5yr) +5.48% · C (4yr) +19.20%    sum +31.87 (needed 5.93)
```

### Diagnosis

Built under production conditions (7 years of training) and measured on 164 real
2026 base dates:

| Item | Folds | 2026 production |
|---|---|---|
| Onion | +7.19 / +5.48 / +19.20% | **+2.67%** |
| Cabbage | mixed | **−5.70%** |
| Radish | mixed | +2.64% |
| **Pooled** | | **+0.08%** |

**The gain on onion is paid for by a loss on cabbage.** Adopting it would have
made cabbage worse for no net benefit.

### Root cause

**Folds train shorter than production.**

```
fold C 4yr · fold B 5yr · fold A 6yr · production 7yr
```

Onion specifically needs more than five years before it beats its own anchor —
its autocorrelation is 0.963, so the anchor is very strong and the model needs
more history to overtake it:

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
> than no feature A") are fine on folds, because both sides train on the same
> span. Absolute questions ("where should the gate go", "split or merge") are
> not.

This was the **second** case the same day; a lead-time-gate experiment had
already produced three mutually contradictory answers from folds, production
records and the sealed holdout, for exactly this reason.

---

## Case 15. Reproducibility does not validate the setup

### Symptom

A feature reproduced across **two disjoint seed sets**. That is normally strong
evidence.

### Diagnosis

The experiment tool's data builder had no item filter. **Garlic was 24% of the
training rows** — an item we deliberately exclude from production because its
wholesale price is unchanged on 94% of days.

### Fix

Verdicts from that tool were rolled back. `exp_quantile.build()` now prints the
item list on every call, and a new experiment starts by asking **"is this
training on the same data as production?"**

### Lesson

**Reproducibility tells you it was not chance. It does not tell you that you
measured the right thing.** Two independent seed sets agreeing on a
wrongly-configured experiment agree perfectly.

---

## Case 25. A feature worth +1.67% disappeared at 20 seeds

### Symptom

Auction momentum features, measured on 5 seeds: **+0.53 / +1.67 / +0.36**.

### Diagnosis

At 20 seeds: **−0.07 / −0.38 / +0.90**.

### Lesson

**Improvement must exceed 2x the seed standard deviation** before it is a
result. A 5-seed run does not estimate that spread well enough for a small
effect. This is the same rule as Case 3, in the seed dimension rather than the
fold dimension.

---

## Case 24. The comparison was run at the wrong hyperparameters

### Symptom

We reported that XGBoost beats LightGBM, then retracted it.

### Diagnosis

The comparison had been run at 300 trees. Production uses 76.

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

At 300 trees both models are already overfitting; XGBoost merely degrades a
little more slowly. **Tree count matters ten times more than model family.**

### Lesson

**Run a comparison at the operating point you actually use.** At an arbitrary
setting the conclusion inverts.

---

## Case 4. Missingness became a date identifier

### Symptom

A candidate feature had 36.6% coverage over the training window.

### Diagnosis

The API only retains two recent school years, so real observations start
2020-09. Leaving the rest missing would let the model learn **"is this before
September 2020?"** — a date identifier, the same trap as the economic variables,
which repeat one monthly value for a month and get used to identify the period.

The economic-variable version of this was measurable: removing them raised
`best_iter` from 33-51 to 102-140, meaning they had been **causing early
stopping**.

A subtler version: the news sentiment index is a **daily** series and still
failed, because the model preferred its 30-day mean (importance 3.8-6.5%) over
the daily value (1.1-2.4%). Removing only the 30-day mean removed the harm.

### Fix

Build a (month, day) median profile from the five observed years and apply the
same rule across the whole span. Leave-one-year-out MAE 0.0315, binary
agreement 96.7%. (The feature was still rejected on its merits — Case 3.)

> **Sharpened rule.** Not just "monthly data becomes a date identifier" but
> **"any series becomes one if you smooth it long enough."** Feed news and search
> data as **ratios** (today / 7-day mean), never levels. A ratio does not encode
> what year it is.

---

## Case 5. A new column silently changed the baseline

### Symptom

Adding a column changed results in places that had nothing to do with it.

### Diagnosis

The new column was picked up as a **baseline candidate**, changing the
comparison standard itself. Every previous number became incomparable.

A related instance: while evaluating auction prices, wholesale columns sat in
the baseline candidate list. Different order of magnitude, so they always lost,
which made **"the anchor is the strongest baseline"** structurally true by
accident.

### Fix

New columns are excluded from model inputs by default and enabled explicitly.
Baseline candidates are chosen per target and verified to be on the same scale.
Ten new derived baselines added on 09-03 are deliberately **excluded from the
inputs**: strongest as a yardstick, harmful as a feature.

---

# F. Reporting failures — the number was right, the sentence was wrong

## Case 23. A direction claimed from two rows

### Symptom

We told the buying team the prediction band had narrowed from **0.676 to 0.544**.

### Diagnosis

That axis (auction, D+14, cabbage and radish) had **two rows** that day. The
next day, the same five axes measured on a new base date were **all wider**
(+8.9 to +21.2%).

**Both measurements were correct.** They were different days. Conditional bands
are *by definition* different every day, so a single day carries no direction.

### Fix — an addition to the working rules

> **Recording conditions is not enough. Record the sample count next to the
> conditions, and do not state a direction when the count is in single digits.**

---

## Case 22. Three teams inferred the method from the width

### Symptom

Which band method produced a given row was being reconstructed from the width of
the band. **Three teams did this and all three got it wrong**, including us.

A related illusion: the fixed table's conditionality ratio looked like 1.15~1.52
pooled, suggesting it did respond to conditions. Measured **per item** it is
**exactly 1.00** — width was a function of (item x lead time) only. Radish has
wide bands and high volatility, onion narrow bands and low volatility, so the
item difference impersonated conditionality. Case 2 again, in a different
dimension.

### Fix

A `band_method` column recorded when the row is written
(`quantile` / `fixed_table` / `none`), carried through to the downstream table.

### Lesson

**Record how a value was produced at the moment you produce it.** Do not leave
anyone to infer it from its shape.

---

# The short version

If you read nothing else:

1. **When every feature fails, check the target's autocorrelation.**
2. **A definition change must be traced to every consumer of the definition.**
3. **Break every metric out per item.** Pooled numbers report the heaviest group.
4. **Never decide from one fold, one seed set, or one day.**
5. **Reproducing a result does not validate the setup that produced it.**
6. **Never key on a label the source controls.**
7. **Never ask "is it current?" about a group.**
8. **A check that exists is not a check that is read.**
9. **A failure alerts; an absence does not.**
10. **Missing rows are harder to see than wrong values.**
11. **Record how a value was produced when you produce it.**
12. **Write the sample count next to the conditions.**
