# 2026-08-25 (Tue) — Chwijung Daily Log

> Paste each block into the matching form field. Counts are checked against the form limits.

| Field | Value |
|---|---|
| category | `final` |
| status | `completed` |

## title (35/40)
```text
End-to-end batch pipeline went live
```

## feature_name (94/100)
```text
Daily batch pipeline (collect → score), scheduler, operational model, and handoff table design
```

## problems (176/200)
```text
Forecasting ran only as manual scripts, no operational model had been chosen, and the first live scoring concluded the model lost to the anchor based on a single 45-day window.
```

## solution (182/200)
```text
Chained all stages into one fail-fast command on the Windows scheduler, selected the ops bundles, re-scored over eight months, and designed a calendar-day handoff table for Purchase.
```

## result (188/200)
```text
The pipeline ran end to end in one command (rebuild 79 s); the "model loses" finding reversed to 7 of 8 winning months for retail; four contract mismatches with the shared repo were found.
```

## content (3451/6000)
````markdown
The forecasting system moved from manual scripts to an automated daily pipeline registered on the Windows scheduler. The same day, an operational model was selected, the first scoring of live forecasts was carried out, and the integration point in the shared team repository was surveyed. The live-scoring conclusion reversed within hours, which reinforced the rule against drawing conclusions from a single window.

## Pipeline Design

The batch runs five stages in sequence: data collection, rebuild of the training and inference tables, prediction, loading into the prediction log, and scoring of past forecasts against actual prices. The governing principle is fail-fast: if any stage fails, later stages do not run, so no forecast is produced from a broken input.

Measured on the first full run:

```
rebuild   crop_price_train 198,667 rows (to 2026-08-20), predict_input 2,160 rows — 79 s
predict   anchor at latest survey day 2026-08-21; auction, wholesale, retail completed
load      written to prediction_log
score     completed — 4 succeeded, 0 failed
```

A dry-run option prints the execution plan without running it. Hardcoded API keys were removed from the collectors when the job was registered on the scheduler.

## Operational Model Selection

| | model bundles | ops bundles |
|---|---|---|
| Training | 2017–2022 | 2017–2023 |
| Validation window | 2023 held out | none |
| Trees | early stopping | fixed count |

The ops bundles were equal or better on both point forecasts and intervals and were adopted. Two limitations were documented with the decision: the cabbage auction interval was too narrow (74.5% coverage against an 80% target), and the interval calibration window overlapped the validation window.

## Live Scoring and Its Reversal

The first scoring of 2026 forecasts, based on June–July (45 days), indicated that the model was worse than the anchor. Before reporting this, the window was widened to eight months:

| Target | Months in which the model beat the anchor |
|---|---|
| Retail | 7 of 8 (July was the only loss) |
| Auction | 5 of 8 |
| Wholesale | 4 of 8 |

The initial 45 days coincided with retail's only negative period. The original document was retained with a reversal notice as a record of the error, because the mistake had the same structure as the single-fold illusion identified the previous day.

## Shared Repository Survey and Handoff Design

The shared team repository was surveyed to determine where the forecast would be consumed. The repository was treated as read-only because five other members were working in it and the ML part acts only as a data supplier. The local clone was found to be 12 days out of date, with active development on the dev branch, and four contract mismatches were identified by measurement.

A handoff table was designed for the purchase agent. The consuming code expects consecutive calendar days D+1 to D+18, whereas the model forecasts in business days. The ML side took ownership of the conversion because it maintains the holiday calendar; placing that logic in another team's code would duplicate domain knowledge. A database CHECK constraint on target date equals base date plus offset ensures that a mixed-up axis fails at load time rather than reaching a consumer.

## Lessons Learned

A single window can produce a confident and wrong conclusion. Widening the window before reporting cost minutes and prevented a false message to the business team.
````

---

*Sources (not for pasting): `진행기록/배치파이프라인_20260825.md` · `진행기록/스케줄러_등록_20260825.md` · `진행기록/운영모델채택_20260825.md` · `진행기록/실전채점_2026구간_20260825.md` · `진행기록/타파트연동_조사_20260825.md` · `연동/20260825/`*
