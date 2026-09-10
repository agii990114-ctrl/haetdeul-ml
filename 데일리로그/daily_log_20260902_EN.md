# Daily Log — 2026-09-02 (Wed)

**Project:** Cost Catcher (renamed the next day) · ML team

---

## Summary

A false alarm in the batch monitor was traced to a five-second race. An automated
research loop ran 587 trials and adopted none. An LLM was asked to forecast prices
directly and matched the trained model on average — but not reliably enough to use.
The code moved into its own git repository.

## 1. A five-second false alarm

Asked the batch monitor for status at 09:11:40. It reported **"failure · structural
error."** The batch finished at 09:11:45 with every stage green.

**Cause:** the run's status starts as `running` and becomes `ok` / `partial` / `fail`
at the end. The monitor only accepted `ok` and treated everything else — including
still running — as failure.

**Fix:** report "still running, N minutes elapsed," and escalate only past 45 minutes
(a normal run takes about 10). Verified by flipping the status and restoring it.

A daily false alarm triggers the AI investigation and appends to the alert file.
People learn to ignore it — and real failures get buried with it.

## 2. Automated research loop — 587 trials, 0 adopted

Adapted an autonomous research loop (write → run → evaluate → keep or roll back,
unattended) to our rules. Each trial changed LightGBM hyperparameters and was judged
by the **two-fold rule**: both folds must improve in sign and the sum must exceed
2 × seed deviation.

**None passed.** Most failed on disagreeing signs between folds. It confirmed the
production settings were not being held back by tuning.

## 3. LLM forecasting trial — five runs

The LLM was given the last 14 days plus one point from a year earlier and asked for
the price path (auction, lead ≥ 3):

| | WMAPE | vs anchor |
|---|---|---|
| Anchor | 0.1893 | — |
| LightGBM (production) | 0.1809 | +4.4% |
| **LLM, mean of 5 runs** | **0.1774** | **+6.3%** |

By crop it split cleanly — the LLM beat LightGBM on cabbage in 5 of 5 runs and lost
on onion in 5 of 5. **Not used in production:** the same question returned values
3–7% apart from run to run.

## 4. Repository and handoff

- Code moved into its own git repository (first commit)
- Pre-notice to the purchase team that the interval calculation would change
  (quantile bands), with a reply on the width axis, regenerating past days, and the
  `change_reason` field

## Sources

- `진행기록/daily_log_20260902_EN.md`
- `진행기록/LLM예측시험_5회_20260902.md`
- `실험결과/*autoresearch*_20260902.txt`
- `연동/20260902/`
