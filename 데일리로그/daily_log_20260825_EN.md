# Daily Log — 2026-08-25 (Tue)

**Project:** Cost Catcher (later Haetdeul Nongsan) · ML team

---

## Summary

The pipeline closed the loop: collect → rebuild → predict → load → score in one
command, then onto the Windows scheduler. The first live scoring produced a
conclusion that reversed the same afternoon.

## 1. The batch pipeline runs end to end

```
python run_batch.py            # everything
python run_batch.py --dry-run  # show the plan only
```

Measured that day:

```
[rebuild] crop_price_train 198,667 rows to 2026-08-20 · predict_input 2,160 rows  (79 s)
[predict] anchor at latest survey day 2026-08-21 · auc / whsl / rtl ok
[load]    prediction_log
[score]   scored
success 4 · failure 0
```

Design principle: **stop where it fails.** A later stage never runs on a broken
earlier one.

## 2. Registered on the Windows scheduler

Unattended daily run registered. Hardcoded API keys removed from the collectors at
the same time.

## 3. Operational model chosen — `ops_*`

| | `model_*` | `ops_*` |
|---|---|---|
| Training | 2017–2022 | **2017–2023** |
| Validation window | 2023 held out | none |
| Trees | early stopping | fixed |

`ops_*` was equal or better on both the point forecast and the interval.
Two caveats were written down with it: the cabbage auction interval was **too
narrow** (74.5% coverage against 80% nominal), and the interval calibration window
overlapped the validation window.

## 4. First live scoring — a conclusion that reversed by afternoon

The first scoring of 2026 predictions read **"the model is worse than the anchor."**

That was measured on **45 days** (June–July). Widened to eight months the same
afternoon:

| Target | Months where the model beat the anchor |
|---|---|
| Retail | **7 of 8** (July was the only loss) |
| Auction | 5 of 8 |
| Wholesale | 4 of 8 |

Those 45 days happened to be retail's only negative stretch. The document was kept
with a reversal banner as a record of **what one window does** — the same trap as
the one-fold illusion from the day before.

## 5. The shared repository — survey and handoff design

Surveyed `nobadai/mainproject` to find where our forecast would plug in.

- **Read-only.** Five teammates work in it; we are a supplier. Fetch and read only.
- The local clone was 12 days stale; real work lived on `dev`.
- **Four contract mismatches** found by measurement.
- Designed `haetdeul.ml_price_forecasts`. The purchase agent expects **calendar days
  D+1 to D+18**; our leads are business days. **We own the conversion** — we hold
  the holiday calendar, and putting that logic in another team's code would copy our
  domain knowledge into it. A `CHECK (target_dt = base_dt + offset_days)` makes a
  mixed-up axis fail at load time.

## Sources

- `진행기록/배치파이프라인_20260825.md`
- `진행기록/스케줄러_등록_20260825.md`
- `진행기록/운영모델채택_20260825.md`
- `진행기록/실전채점_2026구간_20260825.md`
- `진행기록/타파트연동_조사_20260825.md`
- `연동/20260825/2026-08-25_183752_예측표_설계.md`
