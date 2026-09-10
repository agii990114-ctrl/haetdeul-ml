# Daily Log — 2026-08-24 (Mon)

**Project:** Cost Catcher (later Haetdeul Nongsan) · ML team

---

## Summary

The day the evaluation rules were set. The test window was sealed, the two-fold
rule was born from a verdict that flipped by year, and three silent defects —
none of which raised an error — were found and fixed.

## 1. Test window sealed; three-way split

Training / validation 2023 / test 2024 onward. The test window was not to be opened
until the final check. (It was opened once, on 2026-09-01.)

## 2. The two-fold rule

Narrowing validation to 2023 made ablation verdicts flip by year: the `auction`
feature group was **remove** on 2023 and **keep** on 2022, for all three targets.

```
Adopt or remove a feature only when both folds agree in sign
and the sum exceeds 2 × the seed standard deviation.
Fold A = validate 2023 · Fold B = validate 2022 · ten seeds
```

Ablation round 2 under this rule: **no feature changes.** `volume` was a removal
candidate on two folds; a third fold (validate 2021) kept it — fold B was the
exception.

## 3. Feature decisions from ablation

| Change | Auction | Wholesale | Retail |
|---|---|---|---|
| Remove economic variables (M2, EPU, PPI) | +6.8% → **+8.7%** | +6.1% → +7.2% | +12.7% → **+15.3%** |
| Remove producing-region weather (retail only) | — | — | +12.7% → **+17.1%** |

Monthly and quarterly indicators repeat the same value for a month, so a daily model
uses them as a **time index** and overfits. After removal, `best_iter` rose from
33–51 to 102–140.

## 4. Lead-time gate adopted; volatility gate rejected

- **Lead-time gate:** for lead < 3, ship the anchor instead of the model. All six
  combinations (3 targets × 2 folds) improved or held (+0.0 to +0.8 points).
- **Volatility gate** ("fall back when the market is quiet"): rejected. The
  low-volatility bucket improved in 2023 and worsened in 2022 — opposite by fold.
- Auction `best_iter` swung 34–814 because the validation curve is flat; seed WMAPE
  agreed within ±0.0011. Production training uses a fixed tree count.

## 5. School-calendar feature — built and rejected

Hypothesis: wholesale buyers are restaurants and school kitchens, so school holidays
move demand. Built from NEIS as a year profile (observed data covered only 36.6% of
the training window). On three folds **all three targets disagreed in sign**; one
cell of nine passed. Wholesale — the target the hypothesis was about — was the worst.

## 6. Three silent defects

| Defect | What it did |
|---|---|
| Retail Seoul filter missing from the rebuild SQL | Re-running would quietly revert retail to the national average. The post-processing file had been lost. Put the filter directly into v5 |
| Calendar had one axis | Business days count **survey** days; the calendar was validated on **auction** days (3,348 vs 2,700). Split into two axes. Found a hardcoded 2028 Lunar New Year off by one day |
| Results depended on CSV row order | Same data, same seed, three row orders: 0.1394 / 0.1381 / 0.1355. Sorted by natural key |

Also built: `predict.py` with model bundles, and the `prediction_log` table.

## Sources

- `진행기록/테스트봉인_ablation2차_20260824.md`
- `진행기록/ablation_반영_최종성능_20260824.md`
- `진행기록/리드타임게이트_조기종료_20260824.md`
- `진행기록/학사일정_feature_20260824.md`
- `진행기록/달력2축_재현성_추론파이프라인_20260824.md`
- `트러블슈팅/` — "one-fold illusion and a calendar wrong only in the future"
