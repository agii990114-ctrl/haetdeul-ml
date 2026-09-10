# Daily Log — 2026-08-26 (Wed)

**Project:** Cost Catcher (later Haetdeul Nongsan) · ML team

---

## Summary

The scheduler ran by itself for the first time. A two-stage forecasting idea was
rejected by measuring its ceiling before building it, and a three-year puzzle about
one fold disagreeing was traced to a typhoon.

## 1. First unattended run

Registered the day before, fired at 09:00 KST with nobody watching.

```
run_id 7 · status ok · 8 stages · 774 s (12 min 54 s)
crop_price_train → 198,775 rows
```

No intervention needed. The remaining gap was failure notification.

## 2. Two-stage forecasting — rejected

**Proposal:** forecast arrival volume first, then feed it into the price model.

**The premise was right.** Every volume feature is backward-looking
(`arr_qty_lag1`, `arr_qty_avg7`, `arr_qty_prev_yr`, `auc_vol_lag1`), so the price
model knows nothing about arrivals during the forecast horizon.

**The ceiling was too low.** Measured before building the pipeline:

```
Perfect knowledge of future arrivals    +2.9%
A realistic arrival forecast            +0.2%
```

Decomposing the residual showed **five times more value in the unforecastable part**.
Rejected without building anything.

Routing producing-region weather through the volume model was tested the same day
and also rejected.

## 3. The volume model kept as a standalone deliverable — with a correction

First reported as **+40% over persistence** (yesterday's value). Arrivals are
strongly seasonal, so yesterday's value is the **weakest** of three baselines.
Against the strongest (same period last year) the figure is **+15.3%**. The record
was corrected the next morning; the daily logs submitted this day already carried
the corrected number.

## 4. Fold B explained — Typhoon Hinnamnor

Fold B (validate 2022) had produced the odd sign three times. This time, removing
producing-region weather was −0.0010 on fold A and **+0.0086** on fold B.

**2022 is the only validation year with a supply shock** — Typhoon Hinnamnor
(landfall 2022-09-06). Cabbage auction price went from 1,237 won (August) to
2,072 won (September).

**Fold B is not a broken fold. It is the only fold with a shock in it.** Earlier
rejections that failed only on fold B may have meant "useless during a shock,"
not "useless."

## 5. Housekeeping

- Per-request session logging (`참고/Claude/`) set up, one file per request
- Two daily logs submitted to the team log (two-stage rejection · fold-B cause)

## Sources

- `진행기록/volume_cascade_experiment_20260826.md`
- `참고/Claude/2026-08-26_173244.md` and three later entries that day
