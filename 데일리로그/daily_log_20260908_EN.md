# 2026-09-08 (Tue) — Chwijung Daily Log

> Paste each block into the matching form field. Counts are checked against the form limits.

| Field | Value |
|---|---|
| category | `final` |
| status | `completed` |

## title (37/40)
```text
Retraining rebuilt as a state machine
```

## feature_name (95/100)
```text
LangGraph retraining workflow, UI integration, stale-server diagnosis and per-lead margin table
```

## problems (185/200)
```text
The retraining flow lived implicitly in scripts and was hard to audit, a new API kept returning 404 despite correct code, and Purchase needed per-lead error margins for its cut formula.
```

## solution (186/200)
```text
Documented the flow as a spec, rebuilt it as a LangGraph state machine with rule-based nodes only, traced the 404 to a surviving reloader worker, and measured one-sided excess quantiles.
```

## result (163/200)
```text
Retraining now runs as an auditable state machine with human checkpoints and no LLM decisions; the 404 cause was documented; a per-lead margin table was delivered.
```

## content (3266/6000)
````markdown
The retraining process was formalised: first documented as a specification, then reimplemented as an explicit state machine that runs alongside the previous version. An interface defect in which an outdated server continued to answer requests was diagnosed. The purchase team received the per-lead error margins required for its purchasing formula, together with a correction of an earlier incorrect claim.

## Specification Before Migration

Before any code was changed, the existing retraining flow was written up in English as the reference specification: the states, the responsibility of each step, the thresholds, the two points at which a person intervenes, and where each component runs. This ensured that the migration could be checked against a written standard rather than against memory.

## State-Machine Design

The flow was rebuilt with LangGraph as a sequence of judge, build, verify, request approval, and apply. State is saved to a checkpoint store after each step, so the process can pause at the approval step and resume later from exactly that point.

No step calls a language model; every decision is a rule. This distinction was documented explicitly, because without it the design would be read as "AI decides whether to retrain", which is neither accurate nor desirable for a system that affects purchasing decisions.

Two endpoints connect the flow to the interface: one reports the current position of the flow from the checkpoint, and one advances it (judge, build, apply or stop).

## Root-Cause Investigation: Stale Server

A newly added endpoint returned HTTP 404 although the code was correct. The development server had been started with automatic reloading, which runs a supervising process and a separate worker process. When the supervisor terminated, the worker continued to hold the port and serve the previous version of the code. The case was recorded in the troubleshooting casebook, and servers are now confirmed to be running current code before a code defect is suspected.

## Per-Lead Excess Quantile Table

The purchase team needed an error margin per lead time to set the maximum purchase price. Because a purchase price below the forecast only increases margin, the margin was measured on one side only: the ratio (actual − forecast) / forecast, counting positive values. Quantiles of this ratio were reported by crop and lead time, together with a mapping from business-day leads to the calendar-day coverage windows used by the purchase team.

## Correction of an Earlier Claim

A previous reply had stated that the purchase team's code would have rejected a mis-dated record. On inspection, their code reads only the base date and not the generation timestamp, so it would not have rejected it. The claim was withdrawn in writing, because an unfounded assurance leaves the other team believing a safeguard exists where none does.

## Preparation for Same-Day Forecasting

A training table including lead time 0 — the auction held on the night of the base date — was prepared, forming the basis of the following day's change.

## Lessons Learned

Writing a specification before migrating makes the migration verifiable. When a server misbehaves, confirm which code it is running before investigating the code itself.
````

---

*Sources (not for pasting): git history of 2026-09-08 (#34–#37) · `연동/20260908/` (two replies) · `진행기록/retrain_flow_EN.md`*
