# Haetdeul Nongsan — Product / Sprint Backlog (EN)

Agricultural price forecasting for storage trading · started 2026-08-18 · **updated 2026-09-04**

This is the English counterpart of `진행계획/백로그.md`. The Korean file is the
original; if the two disagree, the Korean one is correct.

`DONE` = shipped and measured. `TODO` = not started. `DROPPED` = tested and rejected —
we keep these rows because a rejection is a result, and deleting it invites someone
to retry the same thing next quarter.

**Updated 2026-09-17 — status and completion dates added; evidence is git / PR / 진행기록.**

Every table row now ends with **· Done …**. How to read it:

```
2026-09-03             done that day (confirmed by a commit, a PR, or a dated document)
~2026-08-25            already finished by that day; the start date is unknown
date unknown           no evidence found. Nothing was guessed
not started, no date   not done yet
```

Only three kinds of evidence were used: this repo's `git log` (hashes), merge times of
`nobadai/mainproject` pull requests (converted to KST), and the dates in
`진행기록/`, `실험결과/`, `연동/<date>/` filenames and CLAUDE.md.
**This repo's git history starts 2026-09-02**, so for anything older the only evidence is
the date written in a document; where a document does not carry one, the row says
*date unknown*.

**Nothing was deleted.** Rows whose status later changed keep their original text and gain
a note (retraining trigger, pre-swap validation, the lead-time gate, the production bundles,
and PR #264). Work done after 09-04 is in the new section below.

---

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
| DONE | Nongnet price collector · **Done** ~2026-08-25 |
| DONE | ASOS weather collector (`fetch_asos.py`, 7 contract checks) · **Done** 2026-08-25 |
| DONE | ECOS economic indicator collector · **Done** ~2026-08-25 |
| DONE | RAW table DDL and UPSERT logic · **Done** date unknown |
| DONE | Collection verification queries · **Done** date unknown |
| DONE | Auction price collector (incremental, cached) · **Done** 2026-08-20 (daily log 08-20) |
| DONE | Price collector rewrite — `collect_kamis.py`, incremental, straight to DB · **Done** 2026-08-25 |
| DONE | Arrival-volume collector — Nongnet scrape, applies 14-day revisions · **Done** ~2026-08-25 |
| DONE | All five sources current (2026-08-24/25), no CSV hop · **Done** 2026-08-24/25 |
| DONE | Daily schedule running — Task Scheduler, 3 jobs (daily / weekly / monthly) · **Done** 2026-08-25 |
| **DONE** | **Restore six items in the collector (09-03)** — it was fetching three. Dried chili, unpeeled garlic and peeled garlic had been frozen for 10 days. 929 rows backfilled · **Done** 2026-09-03 |
| **DONE** | **`ingest_agent` — six checks before rebuild (09-03).** Caught the 10-day stall on its first run · **Done** 2026-09-03 |

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
| DONE | Unit normalization (conversion rules differ per item) · **Done** date unknown |
| DONE | lag / rolling / year-ago anchor generation SQL · **Done** ~2026-08-20 (daily log 08-20) |
| DONE | Lead time 1-18 expansion · **Done** ~2026-08-19 (daily log 08-19) |
| DONE | Business-day axis from the calendar table (v1 inferred it from "a price row exists", which cannot work for future dates) · **Done** 2026-08-24 |
| DONE | Four leakage checks · **Done** ~2026-08-21 (daily log 08-21) |
| DONE | Retail aggregation-basis check (Seoul-only, verified on every rebuild) · **Done** 2026-08-24 |
| **DONE** | **Item filter switched to item codes in v5 (09-03)** — the source renamed `마늘` to `피마늘` in 2026, so garlic had silently ended at 2025-12-30 · **Done** 2026-09-03 |
| **DONE** | **Rebuild verification gate (09-04)** — the batch was throwing away v5's own validation output · **Done** 2026-09-04 |

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
| DONE | `ref_item_station` reference table · **Done** date unknown |
| DONE | Mapping verified against real shipment data (`daily_volume`) · **Done** 2026-08-20 (daily log 08-20) |
| DONE | GDD accumulated-temperature logic · **Done** date unknown |
| DONE | Normal-year temperature (stands in for the medium-range forecast) · **Done** date unknown |
| DONE | Station-matching verification query · **Done** date unknown |
| **DROPPED** | **Ten-day granularity for cabbage in May/June/Nov (09-03)** — 5 of 36 ten-day periods disagree with the mapping, but **the worst-disagreeing period is the one that predicts best**. Not changed · **Done** 2026-09-03 |
| **DROPPED** | **`prod_area_top1_share` (09-03)** — passed 2 folds, reversed on fold C · **Done** 2026-09-03 |

**Goal: lead time is countable from a future base date.**

| Status | Item |
|---|---|
| DONE | KASI holiday API collector (`ref_holiday`, refreshed yearly) · **Done** 2026-08-24 |
| DONE | `ref_calendar` on two axes — `is_open` (auction) and `is_survey` (price survey) · **Done** 2026-08-24 |
| DONE | Per-axis sequence numbers — `open_seq`, `survey_seq` · **Done** 2026-08-24 |
| DONE | Calendar pass/fail query (`26_check_calendar.sql`) · **Done** 2026-08-24 |
| TODO | Yearly `ref_holiday` refresh job — the API only confirms two years ahead · **Done** not started, no date |

---

## Sprint 2 — Forecasting model

**Goal: a baseline to judge performance against.**

| Status | Item |
|---|---|
| DONE | Three baselines (yesterday / last-7-day mean / same period last year) · **Done** ~2026-08-19 (daily logs 08-18, 08-19) |
| DONE | Metrics (WMAPE, directional accuracy) · **Done** 2026-08-18 (daily log 08-18) |
| DONE | Time-based split documented (validate 2023, test sealed) · **Done** 2026-08-24 |
| DONE | Per-item breakdown in the output · **Done** 2026-08-21 (daily log 08-21) |
| **DONE** | **Per-target alternative baselines corrected (closed 09-03)** — v5.3 symmetrizes the derived columns and `train.py` branches per target. **The ten new columns are excluded from the model inputs**: strongest as a yardstick, harmful as a feature · **Done** 2026-09-03 |

> **Always compare against the strongest baseline you have, not one.** With an
> anchor-ratio transform the anchor becomes the baseline *by definition*, which
> makes it easy to report a number that is really "we beat the laziest possible
> answer".

**Goal: forecast all three distribution stages 1-18 business days out.**

| Status | Item |
|---|---|
| DONE | LightGBM training script · **Done** 2026-08-18 (daily log 08-18) |
| DONE | Anchor-target transform (log ratio) · **Done** 2026-08-18 (daily log 08-18) |
| DONE | Seed ensembling, early stopping, `--fixed-iter` for production · **Done** 2026-08-24 |
| DONE | Lead-time gate (`--gate-lt 3`) · **Done** 2026-08-24 — **the gate was turned off for all three targets on 2026-09-09** (commit `c6dad48`) |
| DONE | Three production bundles (`ops_auc`, `ops_whsl`, `ops_rtl`) · **Done** 2026-08-25 — **rebuilt as lead-0 bundles on 2026-09-09** (commits `fac1c9d`, `c6dad48`) |
| **DROPPED** | **Auto-research, 587 runs (09-02)** — hyperparameters and feature combinations. **Zero adopted.** The confirmation fold (C) killed one retail candidate that had passed A and B · **Done** 2026-09-02 |
| **DROPPED** | **Auction momentum features** — visible at 5 seeds, **gone at 20 seeds** (+0.53/+1.67/+0.36 to -0.07/-0.38/+0.90) · **Done** 2026-09-02..04 |
| **DROPPED** | **Output shrinkage** (pull the prediction toward the anchor) — negative on all three folds · **Done** 2026-09-02..04 |
| **DROPPED** | **Split by lead time** — no gain · **Done** 2026-09-02..04 |
| **DROPPED** | **Split by item** (onion trained separately) — +7.19/+5.48/+19.20% on folds, then **-5.70% on cabbage** under production conditions · **Done** 2026-09-04 |
| **CANDIDATE** | **20 seeds instead of 5: +0.72%.** The only surviving accuracy gain of the three days. Not yet deployed · **Done** measured 2026-09-04, **still not deployed as of 2026-09-17** |

> **New adoption rule, learned from the item-split result (09-04).**
> Passing three folds is not enough for a **structural** change. Folds train on
> 4, 5 and 6 years; production trains on 7. Onion in particular needs more than
> five years of history before it beats its own anchor (§8). So:
> **build the change under production conditions and measure it on the 2026
> window before adopting it.** For a relative question ("is feature A better
> than no feature A") folds are fine — both sides train on the same span.

| Status | Item |
|---|---|
| **DONE** | **Per-feature ablation (09-03)** — all 36 cells inconclusive. **No change** · **Done** 2026-09-03 |
| **DONE** | **Four zero-cost features (09-03)** — none adopted. Subclass mixing confirmed *not* to be a risk, and that item is closed · **Done** 2026-09-03 |
| **DONE** | **Experiment-tool garlic contamination fixed (09-03)** — `exp_quantile.build()` had no item filter, so **garlic was 24% of the training rows**. Verdicts produced with that tool were rolled back · **Done** 2026-09-03 |
| **DONE** | **Three-fold adoption rule (09-03)** — two matching signs is a *search* threshold, not an *adoption* threshold · **Done** 2026-09-03 |
| TODO | **Combinations that do not beat the anchor — redefined (09-04)** · **Done** redefined 2026-09-04; the four candidates are not started |

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
| DROPPED | XGBoost, CatBoost — **tree count matters 10x more than model family** (family 1%, wrong tree count 11%) · **Done** 2026-09-01 |
| DROPPED | MLP — loses to a plain average. This is why TFT was not started · **Done** 2026-09-01 |
| DROPPED | Bank-of-Korea news sentiment index — the 30-day mean becomes a date identifier · **Done** 2026-09-01 |
| INCONCLUSIVE | Google search volume — never harmful, never proven useful · **Done** 2026-09-01 |

---

## Sprint 3 — Delivering the service

**Goal: a daily batch runs unattended and hands the forecast to the buying team.**

| Status | Item |
|---|---|
| DONE | `run_batch.py` — collect, rebuild, infer, load, score · **Done** 2026-08-25 |
| DONE | `predict.py` — condition checks against `meta.json`, LT gate, quality gate · **Done** 2026-08-24 |
| DONE | `prediction_log` and scoring · **Done** 2026-08-25 |
| DONE | `push_forecast.py` — writes `haetdeul.ml_price_forecasts` · **Done** ~2026-08-31 (`연동/push_forecast.py.bak_20260831`) |
| DONE | Dashboard at `localhost:3100` · **Done** date unknown |
| **DONE** | **Failure alerting (09-04)** · **Done** 2026-09-04 |
| **DONE** | **Checks on successful days too (09-04)** — the batch printed one line on success and never looked at what it had shipped · **Done** 2026-09-04 |
| **DONE** | **Credential cleanup `S-01` (09-04)** — keys consolidated at the repo root and renamed for what they are used for · **Done** 2026-09-04 |
| **DONE** | **`ml_calendar_days` / `v_ml_batch_days` (09-04)** — mainproject PR #264, awaiting the maintainer's review · **Done** **not awaiting review any more — merged 2026-09-04 19:18 KST** (PR #264) |
| **DONE** | **Base dates were one day stale for eight months (09-04)** · **Done** 2026-09-04 |

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
| DONE | Quantile regression evaluated per item (auction, wholesale) · **Done** 2026-09-01 |
| DONE | Per-item quantile levels — onion needs q02 where cabbage needs q03 · **Done** 2026-09-01 |
| **DONE** | **Production cutover 2026-09-03 10:36** — **0 of 162 price rows changed**; 75 rows marked `change_reason='band'` · **Done** 2026-09-03 10:36 |
| DONE | Buying team notified in advance, cutover date documented · **Done** 2026-09-03 |
| **DONE** | **`band_method` column (09-04)** · **Done** 2026-09-04 |
| **DONE** | **Answered "what does the width respond to" (09-04)** — market volatility. At the same D+14: fixed table 0.650 (Jan) / 0.694 (Aug); quantile 0.419 -> 1.239 · **Done** 2026-09-04 |
| HELD | Retail stays on the fixed table — it already meets the 80% target in 5 of 6 cells, and quantile bands would only widen it · **Done** held, not done (confirmed 2026-09-17) |

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
| **DONE** | **Drift detection `I-04` (09-04)** — measured as **gain over the anchor**, not raw error · **Done** 2026-09-04 |
| **DONE** | **Error history backfilled (09-04)** — 137 base dates, 164 total, 21,734 scored rows · **Done** 2026-09-04 |
| DONE **(`TODO` as of 09-04)** | Retraining trigger — **deliberately not automatic.** It alerts; a human decides · **Done** **no longer TODO — shipped 2026-09-07** (commit `3330968`, PR #26); threshold 3 weeks -> 1 week on 2026-09-10 (`6d52ecf`) |
| DONE **(`TODO` as of 09-04)** | New-model validation before replacement · **Done** **no longer TODO — shipped 2026-09-07**; the server refuses a swap that fails validation. «skip when already up to date» 2026-09-16 (`f8fcb1f`) |
| TODO | Order-planning integration (blocked on the business team) · **Done** not started, no date (blocked on B-01) |

> **Why drift is measured against the anchor.** Our first rule was "flag a week
> whose error is 10 points above the 8-week median". It flagged weeks the model
> had **won** — wholesale cabbage at +3.8% and +29.0% over the anchor were both
> marked bad, because the baseline that week was even better. Ratios also blew
> up (-263.9% when the anchor sat at 4.0%). **In a volatile week everything gets
> worse; that is the market, not drift.** Drift is the model losing ground it
> used to hold.

---

## What happened 2026-09-05 to 09-16 (added 2026-09-17)

This file stopped at 09-04. Twelve more days follow. **Most of this code lives in the shared
`mainproject` repository, so only half of it shows up in our own `git log`** — the rest is
tracked by PR number. PR times are merge times converted to KST.

| Status | Item · Done |
|---|---|
| DONE | Retraining agent — judge, build a candidate, validate, swap, all from the screen · **Done** 2026-09-07 (commit `3330968`, PR #26) |
| DONE | Retraining flow ported to a LangGraph state machine · **Done** 2026-09-08 (commit `657afda`, PR #35) |
| DONE | Judge, build and compare with no human; show it only when it is better · **Done** 2026-09-09 (commit `2078b5f`) |
| DONE | Retraining threshold 3 weeks -> 1 week; wholesale dropped from the judgement · **Done** 2026-09-10 (commit `6d52ecf`), wording aligned 2026-09-11 (`da3659b`) |
| DONE | The "update the model" button was being refused by the next batch instead of the human · **Done** 2026-09-11 (commit `9c156fc`) |
| DONE | If the current model already learned up to the latest data, record a «skip» instead of building a candidate · **Done** 2026-09-16 (commit `f8fcb1f`, with a regression test) |
| DONE | News agent — Naver collector, AI only splits and names, wired into batch and screen · **Done** 2026-09-07 (commits `4cd9d67`, `1c77054`, `5b5dbb4`; PRs #31-#33) |
| DONE | Collector wrote the string `'None'`, so the auction target was empty for a whole day · **Done** 2026-09-07 (commit `5700cfc`, PR #27) |
| DONE | Garak notice-board watcher stopped — it violated `robots.txt` · **Done** code 2026-09-07 (`2bc5e2c`), **scheduler task disabled 2026-09-10** |
| DONE | Lead 0 (tonight's auction) added as a target; **the lead-time gate turned off on all three** · **Done** 2026-09-09 (`fac1c9d`, `c6dad48`), docs corrected 2026-09-13 (`b22b569`) |
| DONE | Daily check report split into «Claude English draft -> Gemini Korean» · **Done** 2026-09-09 (`8417237`), honorifics unified and flash-lite -> flash 2026-09-16 (`3488c5e`, `bba9569`) |
| DONE | Batch moved to 08:00, **base date slipped a day** (the DB clock is UTC), moved back to 09:00 · **Done** moved 2026-09-10 (`635dfbb`), reverted 2026-09-11 |
| DROPPED | TFT, LSTM and GRU measured in the same place as LightGBM · **Done** 2026-09-10, **all three rejected** (commit `5d18e3f`) |
| DONE | Inventory of the DB tables we actually use; auction source start date corrected to 2017-01-02 · **Done** 2026-09-11 (`6659a07`, `34f6cdb`) |
| DONE | Forecast explanation popup showed «none» for the latest base date · **Done** 2026-09-11 (`fc19421`) |
| HELD | **Forecast pipeline code frozen** — report defects, do not fix them · **Done** instruction 2026-09-13 |
| DONE | Forecast Q&A agent `/ml/qa` · **Done** designed 2026-09-13/14, merged **2026-09-15 14:27** (PR #672) |
| DONE | Master port — an in-process function, not HTTP · **Done** **2026-09-15 15:01** (PR #687; master side #689 at 15:22) |
| DONE | Date interpretation, answer cleanup, "today", out-of-range dates · **Done** 2026-09-15 15:52 / 16:03 / 17:04 / 21:08 (PRs #694, #700, #701, #707) |
| DONE | Batch and performance branches added; with no item named it answers all nine cells · **Done** **2026-09-16 12:37** (PR #746; master routing #748 at 12:52) |
| DONE | 09-16 ML bundle — console calendar, screen polish, chat close, update-model button · **Done** **2026-09-16 17:25** (PR #773; the separate PRs #755, #763, #765, #766 were closed unmerged and folded into it) |
| DONE | A date after the base date no longer falls back to today's values · **Done** **2026-09-16 17:50** (PR #774) |
| DONE | Agent reports also written to the DB (`agent_report`) so the chat side can read them · **Done** 2026-09-16 (`d77afa8`, `SQL/36_agent_report.sql`) |
| DONE | Model cutover history (`model_cutover`) · **Done** 2026-09-16 (`99984b7`, `SQL/37_model_cutover.sql`) |
| DONE | Two reports produced in the same second overwrote each other · **Done** 2026-09-16 (`3c53be1`, tests `d295f87`, backfill `f4b126f`) |
| DONE | Date range (from, to) on the console history endpoints · **Done** 2026-09-16 (`396bfe3`) |
| TODO | Q&A silently drops aggregate requests such as "average" · **Done** **not done**, found 2026-09-14 |

---

## Held until after the presentation (2026-09-21) — compiled 2026-09-17

| Status | Item · Done |
|---|---|
| HELD | Repository cleanup (plan B) · **Done** investigated **2026-09-16**, not done — the repo measured 5.7GB; of plans A/B/C, **plan B was deferred until after the presentation** |
| HELD | Retail retraining-check design (move the comparison window) · **Done** raised **2026-09-16**, not done — commit `f8fcb1f` header: properly checking a model trained to the latest data "needs a separate design that moves the comparison window (after the presentation)" |
| HELD | Old expected values in the scoring table (`accuracy`, `usability`) · **Done** raised **2026-09-16** during the scoring run, not done — they still hard-code the sealed-holdout figures (2026-09-01, 486 base dates, 19.7%). PR #774, `backend/app/ml/ops/qa_prompt_bench.py:69-70` (기대값 accuracy·usability 가 #746 이후 어휘에 없음) |
| HELD | Whether "up to 5 days out" should include today · **Done** raised **2026-09-16**, not done — the buying contract requires `daily[0] = as_of + 1` |
| HELD | The two retraining judges disagree · **Done** raised **2026-09-15**, not done — the daily check report: the judges that ran at 09:09:21 and 09:09:24 say different things about auction onion (+0.8%p apart), **every day since 2026-09-12**. `진행기록/agent_logs/2026-09-15_claude_check.md` |
| HELD | Q&A aggregate requests ("average") · **Done** not done, found 2026-09-14 |
| HELD | Quantile bands for retail · **Done** not done — 5 of 6 cells already meet the target |
| HELD | Make the batch's "today" Korean time · **Done** not done — it touches the rebuild SQL, so after the presentation |
| HELD | Yearly `ref_holiday` refresh job · **Done** not done — the calendar runs to 2028-12-31 |
| HELD | Order-planning integration · **Done** not done — blocked on the business conversation |
| TODO | Business conversation (target margin, tolerable loss) · **Done** **unresolved** — pending since 2026-08-19 |

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
