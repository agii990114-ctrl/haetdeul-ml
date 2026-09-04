# Haetdeul Nongsan — Product / Sprint Backlog (EN)

Agricultural price forecasting for storage trading · started 2026-08-18 · **updated 2026-09-04**

This is the English counterpart of `진행계획/백로그.md`. The Korean file is the
original; if the two disagree, the Korean one is correct.

`DONE` = shipped and measured. `TODO` = not started. `DROPPED` = tested and rejected —
we keep these rows because a rejection is a result, and deleting it invites someone
to retry the same thing next quarter.

---

## What this system does

```
predict auction price -> buy cheap at auction -> store -> predict retail price -> sell high
```

We own the forecasting models only. Storage cost, shrinkage, and order quantity
belong to other teams. Our job is to hand over an accurate price curve.

---

## Sprint 1 — Data pipeline

**Goal: the system collects public-source price, weather and economic data on its own.**

Acceptance: (1) 2015-2025 loaded with no gaps (2) re-loading UPSERTs instead of
duplicating rows (3) a collection failure is distinguishable from a real zero
(4) re-running gives the same result (5) the latest date stays at yesterday.

| Status | Item |
|---|---|
| DONE | Nongnet price collector |
| DONE | ASOS weather collector (`fetch_asos.py`, 7 contract checks) |
| DONE | ECOS economic indicator collector |
| DONE | RAW table DDL and UPSERT logic |
| DONE | Collection verification queries |
| DONE | Auction price collector (incremental, cached) |
| DONE | Price collector rewrite — `collect_kamis.py`, incremental, straight to DB |
| DONE | Arrival-volume collector — Nongnet scrape, applies 14-day revisions |
| DONE | All five sources current (2026-08-24/25), no CSV hop |
| DONE | Daily schedule running — Task Scheduler, 3 jobs (daily / weekly / monthly) |
| **DONE** | **Restore six items in the collector (09-03)** — it was fetching three. Dried chili, unpeeled garlic and peeled garlic had been frozen for 10 days. 929 rows backfilled |
| **DONE** | **`ingest_agent` — six checks before rebuild (09-03).** Caught the 10-day stall on its first run |

> **Why the stall was invisible for eight months.** The collector asked
> "what is the latest date?" **once for all six items pooled**. Cabbage was
> current, so the pooled answer was current, and nobody ever requested the
> gap for the items that had fallen behind. **One live item makes the whole
> table look healthy.** Both causes are fixed: per-item MAX, and the default
> item list restored to six.

**Goal: raw data becomes something a model can learn from.**

Acceptance: (1) one row = base_date x item x lead time (2) prices normalized to
KRW/kg (3) nothing after the base date leaks into the inputs (4) market holidays
excluded from the business-day axis (5) ids restart at 1 on rebuild
(6) a rebuild matches the previous snapshot on every column.

| Status | Item |
|---|---|
| DONE | Unit normalization (conversion rules differ per item) |
| DONE | lag / rolling / year-ago anchor generation SQL |
| DONE | Lead time 1-18 expansion |
| DONE | Business-day axis from the calendar table (v1 inferred it from "a price row exists", which cannot work for future dates) |
| DONE | Four leakage checks |
| DONE | Retail aggregation-basis check (Seoul-only, verified on every rebuild) |
| **DONE** | **Item filter switched to item codes in v5 (09-03)** — the source renamed `마늘` to `피마늘` in 2026, so garlic had silently ended at 2025-12-30 |
| **DONE** | **Rebuild verification gate (09-04)** — the batch was throwing away v5's own validation output |

> **The item-code fix is not about garlic.** We do not model garlic (§5.4).
> We fixed it because **cabbage, radish and onion break the same way** if the
> source renames them — and then the anchor and the target both go empty while
> forecasts keep shipping. **Rows disappearing is harder to see than values
> being wrong.**

> **The verification gate.** v5 ends with numbered validation queries. The batch
> ran them and discarded the result. Check [14] had been reporting **100%
> mismatch for a week** and no one saw it. `verify_after_rebuild.sql` now returns
> `(check_name, severity, bad, total, detail)`; a BAD row stops the batch, a
> broken check does not.

**Goal: item- and season-appropriate weather for the growing region.**

| Status | Item |
|---|---|
| DONE | `ref_item_station` reference table |
| DONE | Mapping verified against real shipment data (`daily_volume`) |
| DONE | GDD accumulated-temperature logic |
| DONE | Normal-year temperature (stands in for the medium-range forecast) |
| DONE | Station-matching verification query |
| **DROPPED** | **Ten-day granularity for cabbage in May/June/Nov (09-03)** — 5 of 36 ten-day periods disagree with the mapping, but **the worst-disagreeing period is the one that predicts best**. Not changed |
| **DROPPED** | **`prod_area_top1_share` (09-03)** — passed 2 folds, reversed on fold C |

**Goal: lead time is countable from a future base date.**

| Status | Item |
|---|---|
| DONE | KASI holiday API collector (`ref_holiday`, refreshed yearly) |
| DONE | `ref_calendar` on two axes — `is_open` (auction) and `is_survey` (price survey) |
| DONE | Per-axis sequence numbers — `open_seq`, `survey_seq` |
| DONE | Calendar pass/fail query (`26_check_calendar.sql`) |
| TODO | Yearly `ref_holiday` refresh job — the API only confirms two years ahead |

---

## Sprint 2 — Forecasting model

**Goal: a baseline to judge performance against.**

| Status | Item |
|---|---|
| DONE | Three baselines (yesterday / last-7-day mean / same period last year) |
| DONE | Metrics (WMAPE, directional accuracy) |
| DONE | Time-based split documented (validate 2023, test sealed) |
| DONE | Per-item breakdown in the output |
| **DONE** | **Per-target alternative baselines corrected (closed 09-03)** — v5.3 symmetrizes the derived columns and `train.py` branches per target. **The ten new columns are excluded from the model inputs**: strongest as a yardstick, harmful as a feature |

> **Always compare against the strongest baseline you have, not one.** With an
> anchor-ratio transform the anchor becomes the baseline *by definition*, which
> makes it easy to report a number that is really "we beat the laziest possible
> answer".

**Goal: forecast all three distribution stages 1-18 business days out.**

| Status | Item |
|---|---|
| DONE | LightGBM training script |
| DONE | Anchor-target transform (log ratio) |
| DONE | Seed ensembling, early stopping, `--fixed-iter` for production |
| DONE | Lead-time gate (`--gate-lt 3`) |
| DONE | Three production bundles (`ops_auc`, `ops_whsl`, `ops_rtl`) |
| **DROPPED** | **Auto-research, 587 runs (09-02)** — hyperparameters and feature combinations. **Zero adopted.** The confirmation fold (C) killed one retail candidate that had passed A and B |
| **DROPPED** | **Auction momentum features** — visible at 5 seeds, **gone at 20 seeds** (+0.53/+1.67/+0.36 to -0.07/-0.38/+0.90) |
| **DROPPED** | **Output shrinkage** (pull the prediction toward the anchor) — negative on all three folds |
| **DROPPED** | **Split by lead time** — no gain |
| **DROPPED** | **Split by item** (onion trained separately) — +7.19/+5.48/+19.20% on folds, then **-5.70% on cabbage** under production conditions |
| **CANDIDATE** | **20 seeds instead of 5: +0.72%.** The only surviving accuracy gain of the three days. Not yet deployed |

> **New adoption rule, learned from the item-split result (09-04).**
> Passing three folds is not enough for a **structural** change. Folds train on
> 4, 5 and 6 years; production trains on 7. Onion in particular needs more than
> five years of history before it beats its own anchor (§8). So:
> **build the change under production conditions and measure it on the 2026
> window before adopting it.** For a relative question ("is feature A better
> than no feature A") folds are fine — both sides train on the same span.

| Status | Item |
|---|---|
| **DONE** | **Per-feature ablation (09-03)** — all 36 cells inconclusive. **No change** |
| **DONE** | **Four zero-cost features (09-03)** — none adopted. Subclass mixing confirmed *not* to be a risk, and that item is closed |
| **DONE** | **Experiment-tool garlic contamination fixed (09-03)** — `exp_quantile.build()` had no item filter, so **garlic was 24% of the training rows**. Verdicts produced with that tool were rolled back |
| **DONE** | **Three-fold adoption rule (09-03)** — two matching signs is a *search* threshold, not an *adoption* threshold |
| TODO | **Combinations that do not beat the anchor — redefined (09-04)** |

> **The old "three bad combinations" list is obsolete.** It predates the auction
> spec fix and the shrinkage anchor. Re-measured on the 164 real 2026 base dates:
> **auction and retail are fine in all six cells; only the three wholesale cells
> sit at anchor level.**
>
> ```
> retail cabbage  +16.9%    auction onion   +16.4%    auction cabbage +13.5%
> retail onion    +12.0%    retail radish   +10.1%    auction radish   +2.4%
> wholesale (all three)  ~= anchor
> ```
>
> **Wholesale has a structural reason.** The wholesale price is **identical to
> yesterday on 58-68% of days** (auction 0.6-1.3%, retail 18-26%). When the
> anchor is already the right answer two days out of three, there is very little
> left to beat. All four candidates aimed at it were rejected.

---

### Model / algorithm comparisons (2026-09-01)

| Status | Item |
|---|---|
| DROPPED | XGBoost, CatBoost — **tree count matters 10x more than model family** (family 1%, wrong tree count 11%) |
| DROPPED | MLP — loses to a plain average. This is why TFT was not started |
| DROPPED | Bank-of-Korea news sentiment index — the 30-day mean becomes a date identifier |
| INCONCLUSIVE | Google search volume — never harmful, never proven useful |

---

## Sprint 3 — Delivering the service

**Goal: a daily batch runs unattended and hands the forecast to the buying team.**

| Status | Item |
|---|---|
| DONE | `run_batch.py` — collect, rebuild, infer, load, score |
| DONE | `predict.py` — condition checks against `meta.json`, LT gate, quality gate |
| DONE | `prediction_log` and scoring |
| DONE | `push_forecast.py` — writes `haetdeul.ml_price_forecasts` |
| DONE | Dashboard at `localhost:3100` |
| **DONE** | **Failure alerting (09-04)** |
| **DONE** | **Checks on successful days too (09-04)** — the batch printed one line on success and never looked at what it had shipped |
| **DONE** | **Credential cleanup `S-01` (09-04)** — keys consolidated at the repo root and renamed for what they are used for |
| **DONE** | **`ml_calendar_days` / `v_ml_batch_days` (09-04)** — mainproject PR #264, awaiting the maintainer's review |
| **DONE** | **Base dates were one day stale for eight months (09-04)** |

> **Alerting: what was actually missing.** Alert file, Windows notification and
> webhook all already existed. What no one had built was **"the batch did not
> run at all"** — a failure alerts, an absence does not. We now flag gaps over
> 30 hours between successful `push` runs. **The first run found 2026-08-28 to
> 08-31, a 66-hour hole.**

> **Credentials.** `DATA_GO_KR_SERVICE_KEY` held **two different values in two
> folders**. Consolidating them naively would have broken one collector silently.
> Plaintext password files moved out of the repository; **rotating the passwords
> themselves is a human task** and is still open.

> **Base dates.** v5 STEP 8 built the inference axis from rows that exist in the
> price table, so the newest base date was always the last *surveyed* day — one
> day behind. The buying team's contract says `daily[0] == as_of + 1`; it had
> been quietly false since January. `px_ext` now adds phantom rows for survey
> days that have no price yet, and 137 base dates were backfilled.

---

## Sprint 3.5 — Prediction intervals

| Status | Item |
|---|---|
| DONE | Quantile regression evaluated per item (auction, wholesale) |
| DONE | Per-item quantile levels — onion needs q02 where cabbage needs q03 |
| **DONE** | **Production cutover 2026-09-03 10:36** — **0 of 162 price rows changed**; 75 rows marked `change_reason='band'` |
| DONE | Buying team notified in advance, cutover date documented |
| **DONE** | **`band_method` column (09-04)** |
| **DONE** | **Answered "what does the width respond to" (09-04)** — market volatility. At the same D+14: fixed table 0.650 (Jan) / 0.694 (Aug); quantile 0.419 -> 1.239 |
| HELD | Retail stays on the fixed table — it already meets the 80% target in 5 of 6 cells, and quantile bands would only widen it |

> **The cutover changed no prices, only widths.** `change_reason='band'` rather
> than `'price,band'` is the evidence. Model names were deliberately **not**
> changed: the buying team filters on an exact `model_ver` match, so a rename
> would return **zero rows with no error**.

> **Why `band_method` exists.** Three teams tried to infer which method produced
> a band by looking at its width, and **got it wrong three times** — including
> us. The method is now recorded when the row is written instead of reconstructed
> afterward.

> **A one-day reading has no direction.** We once told the buying team the band
> had narrowed 0.676 -> 0.544. That axis had **two rows** that day; the next day
> all five axes were wider. Both measurements were correct. **Record the sample
> count next to the condition, and do not state a direction on single digits.**

---

## Sprint 4 — Operational stability

| Status | Item |
|---|---|
| **DONE** | **Drift detection `I-04` (09-04)** — measured as **gain over the anchor**, not raw error |
| **DONE** | **Error history backfilled (09-04)** — 137 base dates, 164 total, 21,734 scored rows |
| TODO | Retraining trigger — **deliberately not automatic.** It alerts; a human decides |
| TODO | New-model validation before replacement |
| TODO | Order-planning integration (blocked on the business team) |

> **Why drift is measured against the anchor.** Our first rule was "flag a week
> whose error is 10 points above the 8-week median". It flagged weeks the model
> had **won** — wholesale cabbage at +3.8% and +29.0% over the anchor were both
> marked bad, because the baseline that week was even better. Ratios also blew
> up (-263.9% when the anchor sat at 4.0%). **In a volatile week everything gets
> worse; that is the market, not drift.** Drift is the model losing ground it
> used to hold.

---

## What is actually blocking us — updated 2026-09-04

Collection is unblocked. Automation is unblocked. Alerting is unblocked.
Credentials are cleaned up, so the move to an internal server plus cron is ready.

### Accuracy has hit its practical ceiling

Ten candidates in three days. **One improved anything** (20 seeds, +0.72%).

```
auto-research, 587 runs        0 adopted
momentum features             disappeared at 20 seeds
output shrinkage              negative on all three folds
lead-time split               no gain
item split                    passed 3 folds -> -5.70% on cabbage in production
perfect arrival volume        +2.9 to +4.0% relative        <- the ceiling
```

**The last line is the important one.** Even if we knew arrival volume with
**zero error**, we would gain about 3%. The remaining error is not information
we failed to collect — **it is how much the auction price moves by itself**
(cabbage changes 13.97% day to day).

### So the blocker is a business number, not a technical one

We need the target margin and the tolerable loss. Without them we cannot say
whether the current accuracy is sufficient — and there is very little left to
improve. This is `B-01`, and it has been deferred repeatedly.

### For reference: 5% error is not reachable on auction prices

Asked and answered 2026-09-04. Current error is 9.0-19.7% by item. The anchor
itself — yesterday's price — is off by 13.97% on cabbage. **Hitting 5% would
mean being three times more accurate than yesterday's price.** Onion is closest
at 9.0%. Retail is a different problem at 8.3-12.7%.

---

## What changed 2026-09-02 to 09-04

Besides the accuracy work above, three things turned out to be **already built
and simply not being looked at**:

| What | For how long | Fix |
|---|---|---|
| v5 validation output | Check [14] read 100% mismatch **for a week** | Rebuild gate; BAD stops the batch |
| Days the batch **did not run** | 66-hour hole on 08-28 to 08-31, unnoticed | Gap detection between successful pushes |
| Base date | **Eight months** one day behind | `px_ext` in v5 STEP 8 |

And two silent data failures:

```
collector fetching 3 of 6 items    eight months; three items frozen for 10 days
v5 filtering on item_nm            source renamed garlic; rows ended 2025-12-30
```

**Neither produced a wrong value. Both produced missing rows**, which is why
they went unseen. `ingest_agent` caught the first one on its first run.

Full narrative: `진행기록/daily_log_20260902-04_EN.md`

---

## Working rules that came out of this

1. **Do not ask "is it current?" for a group.** Ask per item. The pooled answer
   is the healthiest member.
2. **Three folds is a search threshold.** A structural change must also be built
   under production conditions and measured on the live window.
3. **Reproducibility does not validate the setup.** A result reproduced across
   two disjoint seed sets was still meaningless because the tool was training on
   24% garlic. Reproducing tells you it was not chance; it does not tell you that
   you measured the right thing.
4. **Record the sample count next to the condition.** Single digits carry no
   direction.
5. **Measure against the anchor, not against raw error.** Everything looks worse
   in a volatile week.
6. **Record how a value was produced when you produce it.** Do not let anyone
   reconstruct it later from its shape.
