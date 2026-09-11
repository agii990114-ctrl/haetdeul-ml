# 2026-08-31 (Mon) — Chwijung Daily Log

> Paste each block into the matching form field. Counts are checked against the form limits.

| Field | Value |
|---|---|
| category | `final` |
| status | `completed` |

## title (37/40)
```text
Batch outage fixed and monitors built
```

## feature_name (88/100)
```text
Batch failure recovery, rule-based monitoring agents and auction scoring-code correction
```

## problems (176/200)
```text
The batch had failed three days running without anyone noticing, and the scoring code had been grading 74% of auction forecasts against a different product's price since 08-27.
```

## solution (176/200)
```text
Removed the leaked column and verified through to the final load, then built rule-based monitors that explain failures in plain language but are never permitted to modify data.
```

## result (176/200)
```text
Batch restored; 25,866 of 34,905 mis-scored rows re-scored to zero mismatch; four monitors deployed; the spread check was re-based on percentiles after a first-run false alarm.
```

## content (3655/6000)
````markdown
A three-day silent outage was discovered and resolved, and the monitoring layer that would have caught it was designed and deployed on the same day. During the work, a separate defect was found in the scoring code, invalidating all auction accuracy figures reported before this date. The day also concluded an investigation into unnaturally flat forecasts.

## Incident Timeline and Recovery

| Date | 09:00 batch | Detected |
|---|---|---|
| 08-29 | Failed | No |
| 08-30 | Failed | No |
| 08-31 | Failed | Yes |

The cause was the `_anchor_mix` column left in the input list on 08-28. Recovery consisted of removing the column from the inputs, retraining the two affected models (auction and wholesale), and running the pipeline through to the final load to confirm that the newly trained models worked end to end.

## Monitoring Design Principles

Three principles were set before implementation. Rules detect problems, because comparing dates or counts does not require a language model and always yields the same answer. A helper explains findings in plain language, replacing the manual work of reading logs and tracing recent changes. No helper is permitted to repair anything, because the rebuild stage empties and refills tables and an automated retry could lose data.

| Monitor | Role |
|---|---|
| Data quality check | Tests four properties that must always hold: grade order, same-day price spread, day-to-day continuity, and target/anchor drawn from the same aggregation — each reflecting a past incident |
| Batch failure investigator | Runs only on failure; reports stage, consecutive-day count, raw error text and handoff delay, and appends to the alert file |
| Forecast explainer | Explains a forecast using measured feature importance and always states the error margin |
| Daily Claude review | Scheduled separately at 09:23 to summarise the day |

## First-Run False Alarm

On its first run the same-day spread check raised an alarm driven by one extreme low price of 50 KRW/kg, a distress sale rather than a mixed product. The check was changed from max/min to the ratio of the 90th and 10th percentiles, because a monitor that raises false alarms daily trains people to ignore it.

## Scoring Defect

The target had been restricted to one package specification on 08-27, but the scoring code had not been updated. As a result, 25,866 of 34,905 auction rows (74%) were scored against a different product's price; the worst case, radish on 2026-01-09, compared a true price of 521 KRW with 2,545 KRW. All rows were re-scored with zero remaining mismatch, and every auction accuracy figure published before this date was declared void.

## Flat-Forecast Investigation

Across 152 base dates, forecasts moved far less than actual prices over leads 3–18: for cabbage auction the forecast range was 13.7% against an actual range of 137.8% (ratio 0.10); for radish 0.29 and onion 0.35. Four attempts to address this by adding or removing inputs were all rejected, each failing at the same point, which indicated that the limitation was not solvable through feature changes.

## Business Coordination

Four replies were sent to the purchase team, covering the forecast axis and the 12-31 backfill, intervals and prices, the package filter and anchor formula, and error back-calculation. The last reply showed that converting a 3.3-point margin buffer into an allowed forecast error requires one additional input: the share of purchase price in total variable cost.

## Lessons Learned

An alert that nobody reads does not protect the system. Monitoring must both detect a problem and deliver an explanation that a person will actually see.
````

---

*Sources (not for pasting): `진행기록/agent_동작흐름_20260831.md` · `진행기록/예측_평탄화_실험4건_20260831.md` · `연동/20260831/` (four replies) · first entries in `진행기록/agent_logs/`*
