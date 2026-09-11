# 2026-09-04 (Fri) — Chwijung Daily Log

> Paste each block into the matching form field. Counts are checked against the form limits.

| Field | Value |
|---|---|
| category | `final` |
| status | `completed` |

## title (40/40)
```text
Stale base dates and unread checks fixed
```

## feature_name (97/100)
```text
Base-date alignment, batch-read validation, series-level diagnosis (M-13) and per-crop model test
```

## problems (164/200)
```text
Base dates had lagged one day for eight months (contract met on 26 of 248 days), and the batch discarded its own validation results, hiding a week of 100% mismatch.
```

## solution (188/200)
```text
Built base dates from the survey calendar without altering training rows, moved validation into a file the batch reads and stops on, and re-measured all combinations after a 2026 backfill.
```

## result (179/200)
```text
Contract alignment restored; validation now halts the batch on BAD; wholesale identified as the only weak series (unchanged 58–68% of days); per-crop split rejected live (+0.08%).
```

## content (4252/6000)
````markdown
The defects resolved on this day shared one pattern: the data or the check existed, but its output reached no one. Base dates had been one day behind for eight months, and the batch had been discarding its own validation results. The list of unreliable model combinations was also rebuilt from a larger sample, and a model-structure change that passed every fold was rejected on live data.

## Base-Date Lag: Mechanism and Correction

A row with base date D uses only data up to D−1. The inference-input step, however, created base date D only after D's own survey value had arrived. Each morning's forecast was therefore built on the previous day's base date, with a one-day-old anchor and one day less of forecast horizon. The purchase team's contract requires the first forecast day to equal the reference date plus one; it was satisfied on only 26 of 248 days.

The correction inserts empty base-date rows from the day after the last observation up to the current date, within the inference-input step only. The training table was not changed by a single row.

## Discarded Validation Results

The rebuild SQL contains validation queries, but the batch executed the file as a single block and advanced past every result set without reading it:

```python
cur.execute(sql)
while cur.nextset():
    pass   # every validation result is discarded here
```

The results were visible only when a person ran the SQL manually. Validation check [14] had reported mismatches on 1,404 of 1,404 comparison rows for a week, because ten derived columns had been added without updating the inference-input step, leaving seven columns entirely empty. Forecast values were not affected, because those columns were excluded from model inputs.

Validation was moved to a dedicated file whose results the batch reads. Findings are classified as BAD, which stops the batch, or WARN, which only notifies. BAD is reserved for conditions under which the output must not be delivered, because an alarm that fires daily is ignored. Detection of days on which the batch did not run, and checks on successful days, were also added.

## Series-Level Diagnosis (M-13)

The backlog listed three of nine combinations as unusable, but the error history covered only 27 base dates concentrated in January and late August. Measured on that sample, six of nine appeared to lose to the anchor; split by period, six changed sign. After backfilling 137 base dates of 2026, 164 base dates and 21,734 rows were scored. Auction and retail were positive with consistent quarterly signs in five of six cells (+10.1% to +16.9%), while all three wholesale cells were at anchor level.

The cause was structural. The share of days on which the price equals the previous day's price is 0.6–1.3% for auction, 18–26% for retail and 58–68% for wholesale. With wholesale unchanged six days in ten, the anchor is nearly perfect and leaves little to improve. Combinations blocked by the quality table were also found to be unmeasurable, since their forecasts are replaced by the anchor before logging; re-measured in shadow mode, wholesale onion was the only wholesale cell positive in all three quarters (+7.6%, +10.7%, +17.9%).

## Per-Crop Model Split

A dedicated onion auction model passed three folds and the 2σ threshold (+7.19%, +5.48%, +19.20%). Rebuilt under production conditions with seven years of training and scored on 164 live 2026 base dates, it produced +2.67% for onion, −5.70% for cabbage, +2.64% for radish and +0.08% pooled, and was rejected. Folds train on four to six years; the longer the training, the more a pooled model benefits. Structural changes now require a live 2026 check in addition to folds.

## Other Work

Drift detection was built around losses to the anchor measured in percentage points; credentials were consolidated into a single environment file; English versions of the development record and troubleshooting casebook were published; and eight replies were sent to the purchase team, including the addition of a band-method field.

## Lessons Learned

A safeguard that nobody reads provides no protection. Each of the three defects found this day was discovered by a person by chance; the corrections moved the signal to a place where the system acts on it.
````

---

*Sources (not for pasting): `진행기록/있는데_아무도_안본다_20260904.md` · `진행기록/M13_못쓰는조합_재정의_20260904.md` · `진행기록/daily_log_20260902-04_EN.md` · git history of 2026-09-04*
