# Haetdeul Nongsan — Development Progress Record

ML team (price forecasting) · written 2026-09-04 20:56:09

**What this document is.** An engineering record of what we built, in what order,
and what each step measured. It is not the method paper
(`발표/ML_price_forecasting_paper_EN.md`) and not the presentation
(`발표/ML_midterm_EN.md`) — those explain the approach and the results. This one
explains **the build**: what shipped, what was rejected, what broke, and where
the project stands today.

Every number below carries the conditions it was measured under. A number
without conditions is not a result (working rule §11).

---

## 0. One page

```
predict auction price -> buy cheap at auction -> store -> predict retail price -> sell high
```

We own the **forecasting models only**. Storage cost, shrinkage and order
quantity belong to other teams. Our deliverable is an accurate price curve,
written daily into a table the buying team reads.

**Three targets, not one.** The same vegetable has three prices along the
distribution chain, and we predict all three, 1-18 business days ahead:

| Target | Stage | Used for |
|---|---|---|
| `target_auc_prc` | auction (farm -> wholesaler) | deciding what to buy |
| `target_whsl_prc` | wholesale (wholesaler -> retailer) | reference |
| `target_rtl_prc` | retail (retailer -> consumer) | deciding when to sell |

**Current state.** The pipeline runs unattended every morning. Three production
models ship forecasts with prediction intervals to the buying team's database.
Accuracy has reached a measured ceiling; the open question is now a business
one, not a technical one (§8).

---

## 1. Timeline

| Phase | When | What was settled |
|---|---|---|
| Data pipeline | ~08-24 | Five sources collected, one SQL file rebuilds the training table |
| Model structure | 08-21 | Three targets, anchor-ratio transform, LightGBM |
| Training window | 08-24 | Start at 2017 — **less data scored better** |
| Feature ablation | 08-24 | Economic variables removed; two-fold rule introduced |
| **Target defect found** | **08-27** | **The auction target was a mixture of 15 packaging specs** |
| Batch automation | 08-25 | Task Scheduler, dashboard, alerting |
| Test unsealing | 09-01 | Opened once, measured, resealed |
| Quantile bands | 09-03 | Model learns the interval instead of reading a fixed table |
| Accuracy push | 09-02~04 | Ten candidates, **one adopted** |
| Operational blind spots | 09-04 | Three "already built, never read" failures found and fixed |

---

## 2. What we built

### 2.1 Collection — five sources, straight into the database

| Source | Content | Collector |
|---|---|---|
| `auction_prices_daily` | auction prices, 32 markets, 2015-2026 | `auction_collector` package |
| `veg_daily_price_raw` | wholesale + retail prices | `collect_kamis.py` |
| `daily_volume` | arrival volume + shipping region | Nongnet scraper |
| `weather_asos_raw` | 95 weather stations | `fetch_asos.py` |
| `econ_daily_raw` | M2, EPU, PPI | `fetch_economic_variables.py` |

All five write **directly to the database**, with no CSV hop. Each collector
compares before it UPSERTs, so re-running does not duplicate rows.

### 2.2 Feature engineering — one SQL file

`DBEAVER_run_v5.sql` rebuilds the entire training table from raw data in one
run. This matters more than it sounds: it means **any result can be reproduced
from scratch**, and it means a fix to the definition propagates everywhere at
once rather than being patched into ten places.

```
crop_price_train    60 columns · 201,106 rows · 2,862 distinct base dates
                    cabbage / onion / radish / garlic · 2015-01-05 to 2026-09-01
                    (measured 2026-09-03)
```

**One row = (base date x item x lead time 1-18 business days).**

> **The effective sample size is base dates, not rows.** One base date expands
> to up to 72 rows (4 items x 18 lead times), so 201,106 rows are really 2,862
> samples — and the training window (2017-2022) is 1,475. We report base-date
> counts, not row counts, whenever we state a sample size.

### 2.3 Two calendar axes

`ref_calendar` distinguishes two things that look like one:

```
is_open     Garak auction trading days       (includes Saturdays)
is_survey   price survey days                (drives lead_biz_d)
```

We found these were different by measurement — 3,348 days vs 2,700 days over
the same span. Version 1 of the calendar had been validated against the wrong
axis. Holiday dates are derived from the government holiday API rather than
hardcoded; the hardcoded version had the 2028 Lunar New Year off by one day.

**Non-scheduled closures are found from actual trading, not from notices.**
We extract "the rules say open, but zero trades happened" and get 14 hits with
**0 false positives and 0 misses** over 2016-2026. Notice-board posts are mostly
images and cannot be parsed reliably.

### 2.4 The daily batch

```
run_batch.py    collect -> rebuild -> infer -> load -> score -> push
```

Runs at 09:00 by Task Scheduler. `--dry-run` prints the plan without acting.
Each stage records its own row, so a failure names the stage that failed and
keeps the error text.

**Training is not part of the daily batch.** Inference runs daily; training runs
monthly or on drift. If we retrained every day the forecast would jitter and we
could not answer "why is this different from yesterday?"

### 2.5 Handoff to the buying team

We are the sole writer of `haetdeul.ml_price_forecasts` in their database.
`push_forecast.py` writes it at the end of every batch. The column contract is
documented in `ml_price_forecasts_컬럼정의서_v1.md` — that document is a
**contract with another team**, not an internal note.

---

## 3. The design decision that made it work

### Anchor-ratio transform

We do not predict the price. We predict **the ratio to yesterday's price**:

```
train:    y = log(target / anchor)
predict:  pred = anchor * exp(model_output)     <- the inverse transform is mandatory
```

Every target has its own paired anchor (`auc_prc_lag1`, `whsl_prc_lag1`,
`rtl_prc_lag1`), drawn from **the same aggregation as the target** — same
market, same grade, same region.

**Why.** Training on absolute prices made the model ignore lead time and learn
the average price instead. Measured: `lead_biz_d` importance 1.5%, and lead-time-1
performance **-95%**.

**The cost of this choice.** The anchor becomes the baseline *by definition*,
which makes it very easy to report a flattering number. So we always compare
against **the strongest of several baselines** — yesterday, 3/7 days ago,
7/14-day means, same period last year, and four shrinkage-anchor variants.
An improvement measured against one anchor alone is inflated.

### Lead-time gate

Below lead time 3, the model is **worse than the anchor** (auction -7.8% at LT1).
Yesterday's price is already close enough that the model can only add noise.
Production ships the anchor directly for LT1-2 (`--gate-lt 3`). Measured across
3 targets x 2 folds: improvement or parity in all 6 combinations; harmful from
k>=5.

---

## 4. The largest finding: the target itself was wrong

**Found 2026-08-27. This is the most important thing in the project.**

The auction API returns individual transactions, and price depends on packaging
spec. Our collector aggregated by (date, market, item, grade) — which **averaged
different products together**.

One day of cabbage at Garak (2026-08-03) contained **15 different specs**:

```
mesh bag 10kg      710.8 KRW/kg    79% of volume
pallet   10kg      870.0 KRW/kg     6% of volume
box       4kg    5,841.3 KRW/kg
box       1kg   11,223.7 KRW/kg               <- retail small pack
[weighted mean]    938.5 KRW/kg               <- what our target was
```

| Metric | Mixed (before) | Spec-fixed |
|---|---|---|
| Cabbage auction **autocorrelation ACF(1)** | **0.085** | **0.795** |
| Coefficient of variation | 0.919 | 0.354 |
| Intraday min/max ratio | 132.7x | 9.7x |
| Grade inversion (special < high) | 737 of 815 days | resolved |

**ACF(1) of 0.085 is white noise.** Yesterday's price told us almost nothing
about today's. We were asking the model to predict an unpredictable series, and
**no feature could have helped.**

The fix pins weight, not packaging: cabbage 10kg, radish 18kg (to 2018) then
20kg, onion 15kg. Mesh, pallet and PE sack at the same weight are the same
product moved differently, so they are combined by volume weight.

### Two consequences we had to chase down

**The baselines were misaligned with the target.** Evaluating auction prices, we
had wholesale columns as baseline candidates — a different order of magnitude,
so they always lost, and "the anchor is the strongest baseline" became
structurally true by accident.

**The scoring code was not applying the spec filter** (found 08-31). The target
was fixed on 08-27 but scoring was not, so **25,866 of 34,905 rows (74%) were
scored against a different product's price.** Worst case: radish on 2026-01-09,
true value 521 KRW scored as 2,545. Everything was rescored (0 mismatches).

> **Every auction-price score produced before 2026-08-31 is void.**

---

## 5. Current performance

**Production configuration, seal opened once on 2026-09-01 and resealed.**
Training 2017-2023, `--fixed-iter`, `--gate-lt 3`, cabbage/radish/onion, 5 seeds.
Because of `--fixed-iter`, neither window below was used in training — both are
pure holdout.

Improvement over the **strongest** baseline, not the anchor alone:

| Target | Item | 2024-2025 (486 base dates) | 2026 (160 base dates) |
|---|---|---|---|
| **Retail** | radish | **+9.0%** | **+6.6%** |
| | cabbage | **+12.9%** | **+15.7%** |
| | onion | **+11.8%** | **+9.4%** |
| **Auction** | radish | +2.0% | +0.8% |
| | cabbage | **+13.1%** | **+13.1%** |
| | onion | +4.5% | **+14.6%** |
| **Wholesale** | radish | **−7.3%** | −1.2% |
| | cabbage | +10.9% | **−2.8%** |
| | onion | +5.4% | +9.5% |

**Three things are clear.**

- **Retail is positive in all nine cells.** Two windows, three items, no losses.
  It is the model we trust most.
- **Cabbage auction is +13.1% in both windows** — identical to one decimal.
  Coincidence, but it means stability.
- **Wholesale radish stays negative.** It was +17.7% on validation 2023 and
  flipped on holdout. **One year had made that number.**

### Absolute error — read this before using it to buy

Same run. Holdout 2024-2025, 486 base dates, 1,432 rows per lead time.

| Price | Item | Mean actual | Mean error | Error rate |
|---|---|---|---|---|
| Auction | cabbage | 963 KRW | 190 KRW | **19.7%** |
| | radish | 771 KRW | 144 KRW | 18.6% |
| | onion | 1,098 KRW | 98 KRW | 9.0% |
| Retail | cabbage | 4,814 KRW | 614 KRW | 12.7% |
| | radish | 2,497 KRW | 241 KRW | 9.7% |
| | onion | 2,231 KRW | 184 KRW | 8.3% |

**Error grows with lead time** (auction, pooled): LT3 13.0%, LT9 16.0%,
LT14 17.8%, LT18 19.8%.

### The margin-buffer question — counted one direction only

When the purchase price comes in **below** our forecast, margin improves. Only
the other direction is a risk. Share of cases where the actual was more than X%
**above** the forecast (auction):

| LT | (D+) | >3% | >4.7% | >10% |
|---|---|---|---|---|
| 3 | 5 | 50% | 45% | 31% |
| **9~10** | **14** | 52% | **47%** | 37% |
| 18 | — | 56% | 52% | 42% |

**At D+14 the 4.7% buffer breaks nearly half the time.** Shortening to LT3 gives
45%. There is no lead time at which auction forecasts become "safe enough" —
that is an honest limitation, not a tuning problem.

By item at D+14: cabbage 57% over buffer (worst), radish 46%, onion 38% (best).

> **A correction we had to issue.** We first pulled this table from
> `prediction_log`, which mixes experimental backtests (`ops-*`, hyphen) with
> production records (`ops_*`, underscore). Averaging four experimental models
> in, we reported cabbage auction error as 35.1% and the D+14 breach rate as 9%.
> The correct values are 19.7% and 57%. **The conclusion reverses** — cabbage is
> the worst item, not the safest. We sent a correction to the buying team.
> **Do not measure performance from `prediction_log`.**

---

## 6. What we rejected, and why we keep the rejections

A rejection is a result. Deleting it invites someone to retry the same thing
next quarter.

| Rejected | Evidence |
|---|---|
| Economic variables (M2, EPU, PPI) | Negative on all three targets. Updated monthly, so the same value repeats for a month and the model **uses it as a date identifier** |
| Weather **for retail only** | +12.7% with, +17.1% without. Retail is buffered by distribution margin. Weather still helps auction and wholesale |
| National retail average | The survey grew from 44 to 59 stores in 2023, so train and validation would use different aggregation bases |
| KREI planted-area data | 75% missing, and present for onion (1.4% missing) but absent for cabbage/radish — it would become an item identifier |
| School calendar (meal demand) | Signs disagree across three folds. 1 of 9 cells positive |
| XGBoost, CatBoost | **Tree count matters 10x more than model family** (family 1%, wrong tree count 11%) |
| MLP | Loses to a plain average. This is why we did not start on TFT |
| News sentiment index | The 30-day mean becomes a date identifier — same trap as economic variables, from a *daily* source |
| Two-stage volume prediction | Even a **perfect** arrival-volume forecast gives only +2.9~4.0% |
| Item-split model (onion separate) | Passed 3 folds, then **−5.70% on cabbage** in production conditions |

### The rule that came out of these

**Feature adoption requires the same sign across folds, a sum exceeding 2x the
seed standard deviation, and per-item verification.** Then three refinements,
each paid for by a mistake:

**① A verdict expires when conditions change.** Ablation run 08-24 said "no
change". Within three days the target definition changed (spec fix) and the
anchor changed (shrinkage). At the time cabbage auction was ACF 0.085 — the
verdict may have meant *"nobody can predict noise"*. Re-run under production
conditions, two group verdicts moved.

**② Do not decide on a bundled group. Split it.** Removing the `calendar` group
whole was negative on both folds — a removal candidate. Split, it was almost
entirely one member, and that member appeared on **one fold only**. Small
positives were hidden inside one large negative.

**③ Anything going to production must be checked on fold C.** On 2026-09-03,
**two candidates that passed two folds both reversed on the third.** One of them
had also reproduced on a disjoint seed set. Reproducing tells you it was not
chance; it does not tell you that you measured the right thing.

**④ Folds cannot answer questions whose answer depends on training length.**
Folds train 4, 5 and 6 years; production trains 7. Onion needs more than five
years before it beats its own anchor. So a **structural** change must be built
under production conditions and measured on the 2026 window before adoption.
This caught the item-split result on 09-04.

---

## 7. Operations, and three blind spots we found

The pipeline has run unattended since 08-25. On 09-04 we audited it and found
three failures that shared one cause: **the check existed and nobody read it.**

| What | For how long | Fix |
|---|---|---|
| SQL validation output | Check [14] read **100% mismatch for a week** — the batch discarded every result set | `verify_after_rebuild.sql` returns `(name, severity, bad, total, detail)`; a BAD row stops the batch |
| Days the batch **did not run** | A **66-hour** gap (08-28 to 08-31) that nobody noticed | Flag gaps over 30 hours between successful pushes |
| Base date | **Eight months** one day behind | `px_ext` adds phantom base dates for survey days with no price yet |

**On the base date.** A `base_dt = D` row only reads data through D−1 — it never
uses D itself. But the axis was built from days that had observations, so
`base_dt = D` only appeared once D's survey arrived. The anchor was a day stale
and the horizon a day short. The buying team's contract says
`daily[0] == as_of + 1`; it had been quietly false, passing **26 of 248 days**.
Fixed, and 137 base dates were backfilled. **The training table did not change
by a single row.**

**On alerting.** Alert file, desktop notification and webhook all already
existed. What was missing was the *absence* case — a failure alerts, a
non-run does not.

**On severity.** We split checks into BAD (stop) and WARN (notify), and put BAD
on only four of six. Marking everything BAD looks safer but produces an alarm
that cries daily, which people learn to ignore — **that is exactly the failure
we were fixing.** Conversely, a check that is itself broken does **not** stop the
batch: dying while trying to notify must not block the real work.

### Monitoring agents

Four agents run alongside the batch. All of them **decide by rule, not by model** —
a language model may add a human-readable summary on top, but the report is
produced without it. If the agent dies quietly, "no findings" and "the checker
is dead" must not look the same.

```
ingest_agent   six checks before rebuild — caught a 10-day collection stall
data quality   grade order · intraday spread · autocorrelation · anchor pairing
batch failure  investigates the failing stage and quotes the original error
drift          measures gain over the anchor, not raw error
```

**Why drift is measured against the anchor.** Our first rule — "flag a week
whose error is 10 points above the 8-week median" — flagged weeks the model had
**won**: wholesale cabbage at +3.8% and +29.0% over the anchor were both marked
bad, because the baseline that week was better still. A ratio formulation blew
up to −263.9% when the anchor sat at 4.0%. **In a volatile week everything gets
worse; that is the market.** Drift is the model losing ground it used to hold.

### Prediction intervals

Since 2026-09-03 10:36, auction and wholesale bands are learned by quantile
regression instead of read from a fixed table.

The old fixed table could not see the situation at all: within an item, the
ratio of a volatile day's width to a calm day's width was **exactly 1.00**,
because width was a function of (item x lead time) only.

The cutover **changed 0 of 162 price rows** — only the widths moved. Model names
were deliberately **not** changed: the buying team filters on an exact
`model_ver` match, so a rename would return zero rows with no error.

We also added a `band_method` column. Three teams had tried to infer the method
from the width and **got it wrong three times, us included.** The method is now
recorded when the row is written rather than reconstructed from its shape.

---

## 8. Where the project stands

### Accuracy has hit a measured ceiling

Ten candidates over 09-02~04. **One improved anything.**

```
auto-research, 587 runs        0 adopted
momentum features             visible at 5 seeds, gone at 20
output shrinkage              negative on all three folds
lead-time split               no gain
item split                    passed 3 folds -> -5.70% on cabbage in production
20 seeds instead of 5         +0.72%    <- the only survivor
perfect arrival volume        +2.9 to 4.0% relative   <- the ceiling
```

**The last line is the argument.** Even knowing arrival volume with **zero
error** buys about 3%. The remaining error is not information we failed to
collect — **it is how much the auction price moves on its own.** Cabbage changes
13.97% day over day.

### The wholesale targets are a different problem

```
share of days identical to yesterday (2026, measured)
   auction      0.6 ~  1.3%
   retail      18   ~ 26%
   wholesale   58   ~ 68%      <- six days in ten
```

When the anchor is already correct two days in three, there is almost nothing to
beat: the anchor's own error on 2026 Q1 wholesale cabbage is **3.30%**. This is
a property of the series, not of the items — the same items do well at auction
and retail. All four candidates aimed at wholesale were rejected.

> **A gated combination cannot be evaluated.** Blocked combinations are shipped
> as the anchor, so `prediction_log` ends up comparing the anchor to itself
> (2026 wholesale onion: 2,604 of 2,652 rows substituted). Measured with the
> gate off, wholesale onion is the **only** one of the three with all quarters
> positive (+7.6 / +10.7 / +17.9%). **Blocked, so unmeasurable; unmeasurable,
> so still blocked.** The batch now runs an ungated shadow daily.

### Is 5% error reachable?

Asked and answered 2026-09-04: **not on auction prices.** Current error is
9.0-19.7% by item, and the anchor itself is off 13.97% on cabbage. Reaching 5%
would mean being three times more accurate than yesterday's price. Onion is
closest at 9.0%; retail is a different problem at 8.3-12.7%.

### So the blocker is a business number

We need the target margin and the tolerable loss. Without them we cannot say
whether current accuracy is sufficient — and there is very little headroom left
to improve. This has been deferred repeatedly and is now the critical path.

---

## 9. Open items

| Item | State |
|---|---|
| Business-side agreement — target margin, tolerable loss | **Blocking.** Everything else waits on this |
| 20-seed bundle (+0.72%) | Built, not deployed |
| Retraining trigger | **Deliberately not automatic** — it will alert; a human decides |
| Move from a desktop Task Scheduler to an internal server + cron | Unblocked now that credentials are consolidated |
| `ml_calendar_days` DDL into the shared repo | PR open, awaiting the maintainer |
| Password rotation for the two market-portal accounts | Human task, still open |

---

## 10. Working rules earned the hard way

1. **Suspect a number that looks like an improvement.** A baseline that went
   0.2114 -> 0.0781 was garlic dominating the denominator. Retail +11.8% was a
   national average smoothing out variation.
2. **Never record a number without its conditions.**
3. **Write the sample count next to the conditions.** We reported a band
   narrowing from 0.676 to 0.544; that axis had **two rows** that day, and the
   next day all five axes were wider. Both measurements were correct. Stating a
   direction from one day was the error.
4. **Verify estimates by measurement.** Our growing-region mapping came from
   domain reasoning and was wrong for 4 months of cabbage, 6 of radish, and 12 of
   garlic.
5. **Inconclusive is not "no effect."** It means unproven.
6. **Never decide from a single year.**
7. **Always compare against several baselines and take the strongest.**
8. **Do not ask "is it current?" for a group.** Ask per item — a pooled answer
   is the healthiest member. A pooled MAX hid a 10-day collection stall for
   eight months.
9. **Rows disappearing is harder to see than values being wrong.** The source
   renamed an item and it silently vanished from the training table. We now
   filter by code, and we name items ourselves.
10. **A check that exists is not a check that is read.** Design who reads the
    output at the same time you write the check.

---

## 11. Document map

| Document | What it holds |
|---|---|
| `CLAUDE.md` | The working context. **Read this first** |
| `발표/ML_price_forecasting_paper_EN.md` | Method and results, paper form |
| `발표/ML_midterm_EN.md` | Presentation narrative |
| `진행계획/backlog_EN.md` | Product and sprint backlog (EN) |
| `진행기록/daily_log_20260902-04_EN.md` | The last three days in detail |
| `진행기록/경락가_규격분리_20260827.md` | The target-definition failure |
| `진행기록/있는데_아무도_안본다_20260904.md` | The three operational blind spots |
| `진행기록/M13_못쓰는조합_재정의_20260904.md` | Why wholesale is a different problem |
| `ml_price_forecasts_컬럼정의서_v1.md` | **Contract with the buying team** |
