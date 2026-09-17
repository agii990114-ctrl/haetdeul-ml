# 2026-08-28 (Fri) — Chwijung Daily Log

> Paste each block into the matching form field. Counts are checked against the form limits.

| Field | Value |
|---|---|
| category | `final` |
| status | `completed` |

## title (33/40)
```text
Shrink anchor and answer-rule fix
```

## feature_name (79/100)
```text
Shrink anchor (blended starting price) and auction ground-truth extraction rule
```

## problems (189/200)
```text
Auction prices move about 14% day to day, so anchoring every forecast on yesterday alone carried one day's noise into all 18 horizons; the auction ground-truth rule also lacked a condition.
```

## solution (182/200)
```text
Tested anchors blending yesterday's price with the 7-day mean at α = 1.0, 0.8, 0.6 and 0.4 over five seeds, adopted α per target, and corrected the ground-truth extraction condition.
```

## result (180/200)
```text
Adopted α = 0.4 (auction), 0.8 (wholesale), 1.0 (retail); auction error fell from 22.5% to 17.5%. A leaked input column went unnoticed and halted the batch for the next three days.
```

## content (2550/6000)
````markdown
Two changes improved the auction model on this day: a new definition of the forecast starting point, and a correction to how the true auction price is extracted. One detail of the first change was not verified end to end, and it caused the batch failures of the following three days; the entry records that omission alongside the gains.

## Shrink-Anchor Experiment

Every model forecasts relative movement from an anchor. Until this day the anchor was the previous observed price. Auction prices, however, change by about 14% from one day to the next, so a single noisy day propagated into all eighteen forecast horizons.

```
anchor = α × previous price + (1 − α) × 7-day mean
α tested: 1.0 (previous price only), 0.8, 0.6, 0.4 — five seeds
```

Approximately seventy training runs were executed across the three targets, α values and both validation folds. The adopted settings were α = 0.4 for auction, 0.8 for wholesale and 1.0 for retail. Auction, the most volatile series, benefited most from blending in the weekly mean; retail, which moves smoothly, kept the previous price unchanged.

## Ground-Truth Extraction Correction

The rule that extracts the true auction price for scoring and training was missing a condition. After the correction, auction error fell from 22.5% to 17.5%, while wholesale and retail were unaffected. The purchase team was notified that the auction values for 08-27 and 08-28 in the handoff table would be replaced with corrected figures.

## Backfill for 2025-12-31

The purchase team asked whether a forecast could be produced as of 2025-12-31. The forecast was generated under the corrected package specification, loaded, and scored.

## Omission and Consequence

The shrink anchor was implemented as a new column, `_anchor_mix`. The column was intended only as the starting point but was inadvertently left in the list of model input features. On this day only the prediction step was checked, and it was checked with an older model bundle; the newly trained models were not run through to the final load stage.

From the next morning, each scheduled batch stopped with the message that the input feature `_anchor_mix` was missing. The failure persisted on 08-29, 08-30 and 08-31 before it was detected.

## Lessons Learned

- A change must be verified through the last stage of the pipeline, not only at the stage that was edited.
- New derived columns that exist for internal calculation must be explicitly excluded from model inputs, and the exclusion should be checked by the pipeline rather than by memory.
````

---

*Sources (not for pasting): `실험결과/2026-08-28_*exp_anchor*.txt` and the α training runs of the day · `연동/20260828/2026-08-28_130815_ml_회신_백필과경락가정정.md`*
