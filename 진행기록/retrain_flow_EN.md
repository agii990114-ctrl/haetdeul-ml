# Retrain Flow — Current Design

ML team (price forecasting) · written 2026-09-07 17:15

**What this is.** A precise description of how model retraining is decided,
built, verified and applied today — written so it can be re-implemented as a
LangGraph state machine without re-reading the code.

It covers backlog Sprint 4 items ② and ③:

```
① alert when error exceeds the baseline for N consecutive weeks   done 09-04
② the retrain trigger is recorded                                 done 09-07
③ a new model that fails verification is not swapped in           done 09-07
```

---

## 0. The one rule that shapes everything

**Nothing retrains or swaps automatically. A human presses twice.**

A model getting worse may mean **the market got strange**, not that the model
decayed. Training on that stretch teaches the strange market as ground truth.
Fold B (validation year 2022, Typhoon Hinnamnor) produced the opposite sign in
five separate experiments for exactly this reason.

The backlog's acceptance criterion is *"a new model that fails verification is
not swapped in"* — **not** *"a model that passes is swapped in."* Those are
different sentences and we implement the first one.

> This was not theoretical. On 2026-09-07 the obvious move — *"training ended
> 981 days ago, let's retrain"* — produced a candidate that was **worse**:
> cabbage 0.1440 → 0.1595, onion 0.1261 → 0.1347, both beyond 2× seed spread.
> Automatic retraining would have degraded production that day.

---

## 1. States

```
IDLE ──drift fires──> CANDIDATE_SUGGESTED
                            │
                    human presses "Build"
                            ▼
                        BUILDING ──error──> FAILED ──> IDLE
                            │
                            ▼
                        VERIFYING
                            │
              ┌─────────────┴─────────────┐
        verification              verification
           passed                    failed
              │                         │
              ▼                         ▼
      READY_TO_APPLY               REJECTED ──> IDLE
              │
     human presses "Apply"
              ▼
          APPLYING ──> APPLIED
                          │
                 human presses "Rollback"
                          ▼
                     ROLLED_BACK ──> IDLE
```

Two human gates: **Build** and **Apply**. Everything between them is automatic.

---

## 2. Node by node

### 2.1 `judge` — should we retrain at all?

Reads only the database. Takes seconds. Runs daily inside the batch.

**Two independent signals, and they are not equal.**

| Signal | Meaning | Can it trigger alone? |
|---|---|---|
| **Losing ground** | model trails the anchor for N consecutive weeks | **yes** |
| **Stale** | training ended more than `STALE_DAYS` ago | **no** |

Staleness alone never triggers. More data does not reliably help: moving the
training start from 2015 to 2017 — **removing** data — improved results from
+5.9% to +6.8%.

**Losing-ground rule** (shared with `drift_agent`, same SQL, deliberately):

```
week = ISO week of target_dt
gain = (anchor_error - model_error) / anchor_error
bad week  = (model_wmape - anchor_wmape) > GAP_PP

MIN_ROWS    = 60     a week with fewer scored rows is not judged
GAP_PP      = 1.0    percentage points, absolute — not a ratio
STREAK      = 3      consecutive bad weeks required
BASE_WEEKS  = 8      history needed before judging at all
```

**Why points and not a ratio.** The first version flagged weeks the model had
*won* — wholesale cabbage at +3.8% and +29.0% over the anchor were both marked
bad, because that week's anchor happened to be even better. A ratio formulation
blew up to −263.9% when the anchor sat at 4.0%. **In a volatile week everything
degrades; that is the market, not drift.**

**One more guard.** If the last `STREAK` weeks are bad but the anchor was
unusually accurate (`max anchor error < 3.0%` and `max model error < 10.0%`),
this is not a retrain candidate. Wholesale prices are unchanged from the
previous day on 58–68% of days, so in a quiet month the anchor drops to 0.7%
error and a 6.8% model looks "bad" without being bad.

**Scope: auction only.** The buying team's code reads `target_kind = 'AUC'`
literally (`backend/app/master/inputs.py:127`). Wholesale and retail are still
*monitored* by `drift_agent` — the record has to exist for when the selling side
is built — but they do not raise retrain candidates. One flag widens this.

Output: a `Report` (findings + verdict) saved to `진행기록/agent_logs/`, which
the dashboard picks up with no further wiring.

### 2.2 `build` — make a candidate

Runs `train.py` with **the current bundle's exact recipe**, read from its
`meta.json`: `train_start`, `seeds`, `gate_lt`, `anchor_alpha`, `fixed_iter`,
`items`, and the quantile settings. Only one thing changes.

```
current    train 2017-01-01 .. 2023-12-31
candidate  train 2017-01-01 .. (EVAL_FROM - 1 day)
```

Takes about 2.5 minutes. Runs as a background subprocess; the UI polls.

**The training CSV is dumped fresh from the database each time.** `train.py`
takes a CSV but the batch no longer produces one, so the DB stays the source of
truth and a stale CSV cannot silently be used.

### 2.3 `verify` — the part that matters

**The fairness condition:**

```
current    trained through 2023-12-31
candidate  trained through 2025-12-31
judged on  2026-01-01 onward        <- neither has seen it
```

Training the candidate up to today and then scoring it on 2026 would let it
recognise what it had memorised. Cutting its training at the start of the
evaluation window keeps both models blind to the same period.

**The sealed test window (2024–2025) is not opened.** 2026 is a window we have
already measured several times.

**Both models are scored by importing `predict.py`'s own `load_bundle` and
`prepare`** — the code that serves production. Re-implementing the anchor mix or
the inverse transform here would mean measuring something that is not
production. An experiment tool once trained on 24% garlic and produced verdicts
we had to roll back; the lesson was to run experiments through the production
path.

**Three adoption rules, each paid for by a past mistake:**

1. **Per item.** A pooled metric reports the heaviest item — garlic once
   dominated 66% of a WMAPE denominator.
2. **Beat 2× the seed standard deviation.** Computed per item from the
   per-seed WMAPE spread of both bundles.
3. **If any item gets worse, reject — even if others improve.** Splitting onion
   into its own model passed all three folds and then cost cabbage −5.70% in
   production.

Verdict:

```
any item worse      ->  REJECTED   (regardless of improvements elsewhere)
no item better      ->  REJECTED   ("inconclusive" is not "equivalent")
otherwise           ->  READY_TO_APPLY
```

Written to a JSON file and to a saved `Report`.

### 2.4 `apply` — human gate two

**The server refuses, not the UI.** The endpoint re-reads the verification JSON
and rejects when:

- no verification result exists
- the result is for a different target
- `passed` is false

A disabled button is not a guard — anyone calling the API directly would get
through. Both refusals were tested by direct call and return HTTP 400.

On success:

```
ops_auc  ->  copied to  ops_auc_교체전_YYYYMMDD     (backup)
candidate ->  copied to  ops_auc                    (same name, always)
```

**The bundle name never changes.** The buying team filters on an exact
`model_ver` match, so a rename returns zero rows with no error.

### 2.5 `rollback`

Restores the most recent backup, or a named one matching
`ops_(auc|whsl|rtl)_교체전_\d{8}`. Any other string is refused.

---

## 3. Where it runs today

```
daily 09:00   batch push stage, as a side-step
                retrain_agent.py --save
              ★ a side-step failing does not fail the batch — the forecast
                has already shipped, so calling it a failure would make the
                alert disagree with reality
              ★ training is NOT in the batch: minutes long, and only needed
                when a human decides

on demand     dashboard "Model" tab
                GET  /retrain/status     judge (seconds)
                POST /retrain/build      start background build+verify
                GET  /retrain/job        poll state + log tail
                POST /retrain/apply      guarded swap
                POST /retrain/rollback   restore backup
```

Only one build runs at a time; a second request returns HTTP 409.

**Failures are shown.** The panel first displayed the log only while running, so
a crash looked like the button doing nothing — which is exactly how the
Windows cp949 encoding bug hid for a while. It now shows the log on failure too,
and re-reads a previous failure when the tab is opened.

---

## 4. What LangGraph would and would not change

**Would fit well**

- The state machine above is real: branching, a long-running node, two
  human-in-the-loop interrupts, and a compensating action (rollback).
- LangGraph checkpointing would replace the in-process `_JOB` dict, which
  today is lost if the server restarts mid-build.
- `interrupt` expresses "wait for a human" better than an idle HTTP endpoint.
- It matches the pattern the rest of the project already uses
  (`purchase_agent/graph.py` — 120 lines, linear nodes, `StateGraph`).

**Would not change**

- Every decision stays rule-based. No node calls a language model. LangGraph
  here is a state machine, not an agent framework — that distinction should be
  stated wherever this is presented, or it reads as if we handed judgment to an
  LLM.
- The four daily checks (`quality`, `drift`, `ingest`, `news`) stay outside.
  They share no state and have no branches; wrapping them in a graph would
  produce `START → a → b → c → END`, which the batch's stage list already is.

**Risks to name up front**

- The current implementation works and is merged. A rewrite in a framework
  trades working code for a cleaner shape.
- Two weeks remain before the project ends (2026-09-21).
- Recommended shape: build the graph **alongside** the existing endpoints and
  compare, rather than replacing them in place.

---

## 5. Files

```
agent/retrain_agent.py     judge (drift + staleness) -> Report
agent/retrain_build.py     build · verify · apply · rollback
agent/drift_agent.py       weekly gain-over-anchor series (shared SQL)
agent/drift_replay.py      replays history to check the thresholds ever fire
backend/main.py            five /retrain/* endpoints, background job
frontend/src/components/RetrainPanel.tsx   two buttons, guarded
```

**On the thresholds.** `drift_replay.py` exists because a rule that never fires
is a rule nobody can trust. Replayed over the scored history, the current
threshold (3 weeks, 1.0 point, 60 rows) fired **12 times out of 195 judged
(week × combination) slots** — and exactly **once** for auction, the only target
that raises candidates today. That single case was real: model 31.6% / 51.8% /
49.6% against an anchor of 28.4% / 43.2% / 40.2%.
