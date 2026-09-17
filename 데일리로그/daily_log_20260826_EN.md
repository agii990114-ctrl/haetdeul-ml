# 2026-08-26 (Wed) — Chwijung Daily Log

> Paste each block into the matching form field. Counts are checked against the form limits.

| Field | Value |
|---|---|
| category | `final` |
| status | `completed` |

## title (40/40)
```text
Two-stage forecast rejected before build
```

## feature_name (89/100)
```text
Arrival-volume to price two-stage forecasting evaluation and fold-B disagreement analysis
```

## problems (187/200)
```text
A two-stage design (forecast arrivals, then price) was proposed, and fold B had given contradictory feature verdicts three times with no explanation, weakening trust in the decision rule.
```

## solution (185/200)
```text
Measured the design's ceiling first (perfect future arrivals vs a realistic forecast) before building anything, and examined what distinguished the 2022 validation year from the others.
```

## result (187/200)
```text
Perfect arrival knowledge added only 2.9% and a realistic forecast 0.2%, so the design was rejected unbuilt; fold B was explained as the only year with a supply shock (Typhoon Hinnamnor).
```

## content (3146/6000)
````markdown
The scheduled batch ran unattended for the first time. The day's analytical work addressed two questions: whether forecasting arrival volume first would improve price forecasts, and why one validation fold kept disagreeing with the others. Both were answered by measurement before any build effort was committed.

## First Unattended Run

The job registered the previous day ran at 09:00 KST without intervention: run 7, status OK, 8 stages in 774 seconds (12 min 54 s). The training table grew to 198,775 rows. The remaining operational gap was failure notification.

## Ceiling-First Evaluation of the Two-Stage Design

The premise was valid. Every volume feature in the price model looks backward (previous-day and 7-day arrival figures, prior-year arrivals, previous-day auction volume), so the model has no information about arrivals during the forecast horizon.

Rather than building a volume forecaster and a combined pipeline, the maximum achievable benefit was measured first:

```
Perfect knowledge of future arrivals (oracle)   +2.9%
A realistic arrival forecast                     +0.2%
```

A residual decomposition showed about five times more value in the component that cannot be forecast. The design was rejected without building the pipeline. Routing producing-region weather through the volume model was tested the same day and also rejected.

## Volume Model Retained, With a Correction

The volume model was kept as a standalone deliverable. It was first reported as +40% better than persistence (yesterday's value). Because arrivals are strongly seasonal, persistence is the weakest of three candidate baselines; against the strongest (the same period last year) the improvement was +15.3%. A further measurement slip involving rows with zero predictions was caught during recomputation. The corrected figure was used in all submitted logs, and the experiment record was updated the following morning.

## Root-Cause Investigation: Fold B

Fold B (validate 2022) had produced the odd sign three times. In this case, removing producing-region weather scored −0.0010 on fold A and +0.0086 on fold B. The investigation examined market events by year and found that 2022 is the only validation year containing a supply shock: Typhoon Hinnamnor made landfall on 2022-09-06, and cabbage auction prices rose from 1,237 KRW in August to 2,072 KRW in September.

## Decision Rationale

Fold B was reclassified from an unreliable fold to the only fold that tests behaviour under a shock. Earlier rejections that failed only on fold B were re-read as possibly meaning "not useful during a shock" rather than "not useful". The two-fold rule was kept, with the added practice of checking what happened in a year before interpreting a disagreement.

## Lessons Learned

- Measuring the ceiling of an idea is cheaper than building it, and a small ceiling is a complete answer.
- A result reported against the weakest baseline overstates the model; the strongest available baseline must be the reference.

Session-level logging (one English record per request) was also established this day, and two entries were submitted to the team log.
````

---

*Sources (not for pasting): `진행기록/volume_cascade_experiment_20260826.md` · `참고/Claude/2026-08-26_173244.md` and later entries that day*
