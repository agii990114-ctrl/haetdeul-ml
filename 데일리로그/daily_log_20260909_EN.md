# 2026-09-09 (Wed) — Chwijung Daily Log

> Paste each block into the matching form field. Counts are checked against the form limits.

| Field | Value |
|---|---|
| category | `final` |
| status | `completed` |

## title (38/40)
```text
ML console, lead 0 and auto-retraining
```

## feature_name (92/100)
```text
ML console (four tabs), UI copy rewrite, same-day forecast (lead 0) and automated retraining
```

## problems (175/200)
```text
Purchase could not obtain same-night auction forecasts, report text was judged incomprehensible, and the winning-candidate retraining path had never been exercised end to end.
```

## solution (189/200)
```text
Added lead 0 and disabled gates, built four console tabs, rewrote 184 strings, split report writing (Claude) from translation (Gemini), and tested retraining with a deliberately weak model.
```

## result (182/200)
```text
Same-day forecasts delivered; translation preserved 216 of 216 numbers twice; the simulation exposed three silent defects (thread ID, stale snapshot, dropped state field), all fixed.
```

## content (4331/6000)
````markdown
The ML part gained a four-tab section in the shared operations console, all on-screen text was rewritten for business readers, and the auction held on the night of each base date became a forecast target. Retraining was automated up to a single human approval, and because the successful-candidate path had never occurred naturally, it was tested by deliberately installing a weak model. The simulation revealed three defects, none of which had produced an error message.

## Same-Day Forecasting (Lead 0)

Garak auctions take place at night, while the batch runs in the morning, so the auction on the base date itself has not yet occurred and can be forecast. The tables had started at lead 1, which meant the purchase team could not obtain that night's price. Lead 0 was added to the training and inference tables, the production bundles were rebuilt under unchanged names because the consumer filters on exact names, and the lead-time gates were set to 0 for auction and retail and 3 for wholesale.

## Operations Console

Four tabs were added: price forecast, batch status, AI reports, and model retraining. The forecast chart was implemented in plain SVG without a charting library, because many libraries connect missing points through zero, which would present days not yet scored as price collapses.

## Interface Copy Rewrite

All 184 on-screen strings were rewritten after feedback that the reports were difficult to understand, first into English and then into plain Korean through a separate translation pass. Values returned by the server were left unchanged, because they act as filter keys and altering them returns zero rows without an error. An earlier violation of this rule had turned every status badge grey, since the colour lookup keys had been translated along with the labels.

## Report Pipeline Evaluation

| Approach | Outcome |
|---|---|
| Lightweight model writing alone | Escalated a false alarm; omitted a handoff change |
| Local model translating | Mistranslated crop names; introduced an incorrect number |
| Lightweight cloud model translating | Preserved all 216 numbers in two runs |

Investigation remains with Claude, because some findings require direct database queries; the lightweight model only translates the English draft. An automated number comparison flags omissions but cannot detect fabricated statements whose numbers appear in the source, so the English draft is always retained alongside the translation.

## Automated Retraining and Simulation

After delivering the day's forecasts, the batch judges whether retraining is needed, builds a candidate, and compares it with the current model. A losing candidate is deleted without notification; a winning candidate displays a red badge and a single "Update model" button. A model trained on only two years of data was installed in the production slot to force the winning path:

| Defect | Symptom |
|---|---|
| Thread identifier mismatch | Badge appeared, but the button had no effect |
| Stale snapshot | The screen continued to show a decision already made |
| Undeclared state field | The workflow dropped the "discarded" status and reported "stopped" |

## Monitoring Corrections

- A single em dash had disabled the batch investigator for three days on the Korean Windows console; the fix was applied once in the shared core module.
- Batch times stored in UTC were displayed as 00:00 for a 09:00 run; they were converted to local time.
- The grade-order check reported a 50% inversion for cabbage based on two days, driven by one 50 kg lot against 518,140 kg. Minimum volume share and day-count thresholds were added, and unmeasurable cases are labelled "not judged" rather than 0%.
- The same forecast appeared as 422 on a card and 423 on the chart: the server truncated 422.535 while the interface rounded. Truncation systematically understates purchase prices, so the server was changed to round.

## Coordination

A contract change for same-day forecasts was agreed. The team also decided not to overwrite historical rows in the purchase team's table, because those rows record what was actually delivered on each day.

## Lessons Learned

A path that has never executed is untested regardless of how simple it appears. Deliberately creating the conditions for it was the only way to find defects that raise no errors.
````

---

*Sources (not for pasting): `진행기록/daily_log_20260909_EN.md` · `진행기록/재학습자동화_시험방법_20260909.md` · git history of 2026-09-09 · `연동/20260909/`*
