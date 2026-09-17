# 2026-08-20 (Thu) — Chwijung Daily Log

> Paste each block into the matching form field. Counts are checked against the form limits.

| Field | Value |
|---|---|
| category | `final` |
| status | `completed` |

## title (39/40)
```text
Three-target kit; arrivals back to 2015
```

## feature_name (87/100)
```text
Three-target training, feature table v4.0 (arrivals 2015+, onion) and auction collector
```

## problems (177/200)
```text
The training script could model only wholesale prices, arrival data began in May 2021 so volume features were empty for most of the history, and auction prices had no collector.
```

## solution (177/200)
```text
Added paired target-anchor definitions for auction, wholesale and retail, extended arrival data back to 2015, added onion, and integrated an incremental auction price collector.
```

## result (173/200)
```text
Any of the three targets could be trained from one command; volume features covered all of 2015–2025; an auction dataset for 2015–2025 plus 2026-01-01 to 08-19 was produced.
```

## content (3173/6000)
````markdown
Three foundations for the storage-trading design were laid on this day. The training script was extended from a single wholesale target to all three price series in the supply chain. The feature table was rebuilt so that arrival-volume features covered the full history and onion was included. An incremental collector for auction prices was integrated, providing the buy-side data that the new target required.

## Three-Target Support in the Training Script

The script gained a table of three targets — auction, wholesale and retail — each paired with its own anchor, the previous value of the same series. The pairing was deliberate: using an auction anchor for a wholesale target would place the numerator and denominator on different price scales and remove the benefit of the ratio transform.

All three target columns were excluded from the model inputs regardless of which target was being trained, because each target is effectively the answer for the others, and leaving any one in would leak information. A target selector and a training-start option were added, and the script now stops with an explicit message if the required target or anchor columns are absent from the exported table.

## Feature Table Version 4.0

The rebuild script for the training table was revised with three changes.

- **Arrival volume over the full history.** Arrival data had started on 2021-05-29, leaving volume features empty for most years. It was extended back to January 2015, giving 295–306 observed days per year for cabbage and 244–304 for onion.
- **Onion producing-region mapping verified.** Arrival-origin data showed Muan county supplying 87–100% of onion in January–March and May–December, confirming the existing weather-station mapping. April was the exception, with Jeju supplying 53% during the early-variety season, so April was mapped separately.
- **Crop scope extended** from cabbage alone to cabbage and onion.

The analysis also documented how producing regions had shifted over time — for example, May cabbage moving from Haenam (44% in 2015–2019) to Yesan (64% in 2020–2025). Because the learning curve of the previous day favoured a 2019 training start, the mapping was fixed to recent patterns, which also avoided most of the historical shift.

## Auction Price Collector

An incremental collection package for auction prices was integrated. It retrieves daily auction results for cabbage, radish, onion, dried chili and garlic from the public data portal and stores them in a fixed sixteen-column format, with a natural key to prevent duplicates. It provides commands to append new days, collect a specified period, replace a period, and validate an output file, together with a Windows setup guide and optional direct loading into PostgreSQL.

Two outputs were produced: a validated seed dataset for 2015–2025 and an incremental extract for 2026-01-01 to 2026-08-19.

## Lessons Learned

Extending the model to new targets required changes in data coverage, not only in code. The arrival-volume gap would otherwise have produced features that were missing for most of the training period and could have acted as a hidden indicator of the time period.
````

---

*Sources (not for pasting): `ML/20260820/ml_train_kit_1/train.py` (diff from 08-19) · `SQL/DBEAVER_run_full.sql` v4.0 header · `데이터 수집/경락가 수집/auction_collector_handoff/` (README, manifests)*
