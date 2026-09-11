# 2026-08-27 (Thu) — Chwijung Daily Log

> Paste each block into the matching form field. Counts are checked against the form limits.

| Field | Value |
|---|---|
| category | `final` |
| status | `completed` |

## title (39/40)
```text
Fixed auction target mixing 15 products
```

## feature_name (98/100)
```text
Auction price target specification (package and weight filter) and target-aware baseline selection
```

## problems (185/200)
```text
Cabbage auction price had ACF(1) of 0.085, effectively noise, because the collector averaged 15 package specs a day; auction and retail baselines were also drawn from wholesale columns.
```

## solution (183/200)
```text
Traced an anomalous 19,900 KRW/kg daily maximum to per-transaction source rows, fixed the target to bulk 10 kg mesh/pallet packs, and made baseline candidates specific to each target.
```

## result (160/200)
```text
Cabbage ACF(1) rose from 0.085 to 0.901 and auction gains turned positive on all three crops and both folds for the first time (cabbage −7.8% → +2.3% / +21.7%).
```

## content (3435/6000)
````markdown
The most consequential finding of the project was made on this day: the auction price target had been defined incorrectly since the start. A single day of cabbage prices combined fifteen different products, which made the series statistically close to random. After correction, auction forecasting became viable for the first time. Two related defects in evaluation and operations were identified on the same day.

## Discovery Path

The investigation began from a business request rather than a model metric, and each step followed an observation that did not fit:

1. The purchase team requested upper and lower price bounds.
2. The cabbage prediction interval was unusually wide (0.65).
3. The intraday maximum reached 19,900 KRW/kg, about 21 times the mean of 939.
4. Garak market's public website showed the opposite grade order from the internal database.
5. In the database, top-grade cabbage was cheaper than second grade on 737 of 815 days.
6. A direct call to the source API returned one row per transaction, including a package field.
7. Splitting by package revealed fifteen distinct products within a single day.

For 2026-08-03, the weighted mean across all fifteen was 938.5 KRW/kg, while the bulk 10 kg mesh and pallet products that the business actually buys averaged 721.9 KRW/kg; retail 1 kg boxes traded above 11,000 KRW/kg.

## Measured Effect of the Correction

| Metric | Before | After |
|---|---|---|
| Cabbage auction ACF(1) | 0.085 | 0.901 |
| Auction improvement, cabbage | −7.8% | +2.3% / +21.7% (fold A / B) |
| Auction improvement, onion | −7.7% | +10.5% / +8.6% |

ACF(1), the lag-1 autocorrelation, measures how well yesterday's price predicts today's. A value of 0.085 means almost no relationship, so no feature could have improved the model. The package filter was refined in later days, and the final per-crop package lists are recorded separately.

## Second Finding: Misaligned Baselines

The training script selected baseline candidates from wholesale columns regardless of which target was being evaluated. For auction cabbage, the candidate "7-day average" averaged 1,169 KRW/kg against a target averaging 721 KRW/kg — a different series. These candidates always lost, which made "the anchor is the strongest baseline" true by construction. The root cause was a partially completed three-target migration: wholesale had the full set of derived columns, while auction and retail lacked several of them.

## Operational Incident: An Unnoticed Failure

The 09:00 batch stopped at the prediction stage, and the failure went unnoticed for nine hours. A failure alert file was introduced. It was then found that the code created alerts but never removed them, so a single failure would have displayed as permanently failing; a clearing step was added so that the alert reflects the latest run.

## Handoff Coordination

A reply to the master and purchase teams confirmed that per-day fill flags were exposed in the forecast view and that overwrite history was traceable. The grade-conversion request was held because the delivered current price measured exactly as top grade, not second grade, and the discrepancy had to be resolved first.

## Lessons Learned

The correction came from refusing to accept a single implausible number. Model tuning cannot compensate for a target that does not describe one product; data definition must be verified against the source before modelling effort is spent.
````

---

*Sources (not for pasting): `진행기록/경락가_규격분리_20260827.md` · `참고/Claude/2026-08-27_092930.md` · `_095209.md` · `_100821.md` · `연동/20260827/2026-08-27_163739_ml_reply_grade_and_flags.md`*
