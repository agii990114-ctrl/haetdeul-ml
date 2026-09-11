# 2026-09-02 (Wed) — Chwijung Daily Log

> Paste each block into the matching form field. Counts are checked against the form limits.

| Field | Value |
|---|---|
| category | `final` |
| status | `completed` |

## title (40/40)
```text
False alarm fixed; 587 trials, none kept
```

## feature_name (92/100)
```text
Batch monitor status handling, automated hyperparameter search and LLM direct-forecast trial
```

## problems (174/200)
```text
The batch monitor reported a structural failure for a run that finished five seconds later, and it was unclear whether tuning or an LLM could outperform the production model.
```

## solution (169/200)
```text
Handled in-progress runs separately with a 45-minute escalation, ran an unattended search gated by the two-fold rule, and tested an LLM on identical rows over five runs.
```

## result (168/200)
```text
False alarm eliminated; 587 tuning trials produced no adoptable change; the LLM averaged 0.1774 vs 0.1809 for LightGBM but varied 3–7% between runs and was not adopted.
```

## content (3549/6000)
````markdown
Three questions were settled on this day. A false failure report from the batch monitor was traced to a timing race. An unattended hyperparameter search tested whether the production configuration was leaving accuracy on the table. A large language model was asked to forecast prices directly, to establish whether a fundamentally different approach could compete. The code base was also moved into its own version-controlled repository.

## Root Cause of the False Alarm

At 09:11:40 the batch monitor reported "failure, structural error". The batch finished at 09:11:45 with every stage successful. The run status begins as `running` and changes to `ok`, `partial` or `fail` only at the end. The monitor accepted only `ok` as healthy and treated every other value, including a run still in progress, as a failure.

The monitor was changed to report "still running, N minutes elapsed" and to escalate only after 45 minutes, against a normal duration of about ten minutes. The fix was verified by temporarily setting the status and restoring it. The change mattered because each false alarm triggers an automated investigation and appends to the alert file; repeated false alarms teach people to ignore alerts, which is how real failures go unnoticed.

## Automated Search Design

An autonomous research loop — write a configuration, run it, evaluate it, and keep or roll back — was adapted to the project's evaluation rules. Each trial varied LightGBM settings such as tree count, learning rate, leaf count, minimum leaf size, feature and row sampling, and L2 regularisation. A trial was accepted only if both validation folds improved in sign and the combined gain exceeded twice the seed deviation.

None of the 587 trials passed. Most failed because the two folds disagreed in sign, and the remainder produced combined changes below the noise threshold. The result confirmed that tuning was not the constraint on accuracy.

## LLM Direct-Forecast Trial

The model was given the last 14 days of prices plus the value from the same period a year earlier and asked for the price path. The evaluation window was placed after the LLM's training cutoff to avoid contamination. Five independent runs were scored on the auction target, lead times 3 and above.

| Method | WMAPE | vs anchor |
|---|---|---|
| Anchor | 0.1893 | — |
| LightGBM (production) | 0.1809 | +4.4% |
| LLM, mean of five runs | 0.1774 | +6.3% |

Pooled, the LLM and a model trained on nine years of data could not be distinguished. By crop the results separated clearly: the LLM outperformed LightGBM on cabbage in all five runs and underperformed on onion in all five. The first run inadvertently included date information in the prompt; it was kept and labelled rather than discarded.

## Decision Rationale

The LLM was not adopted for production because identical inputs produced outputs 3–7% apart between runs. A forecast that changes when the same question is asked twice cannot be explained or defended to the purchase team, regardless of its average accuracy.

## Repository and Handoff

The project was placed under its own git repository with an initial commit. The purchase team received advance notice that the interval calculation would change to quantile bands, together with answers on the width axis, regeneration of past days, and the change-reason field in the history table.

## Lessons Learned

A monitor must distinguish "not finished" from "failed". An alternative that matches accuracy on average can still be unsuitable if its answers are not reproducible.
````

---

*Sources (not for pasting): `진행기록/daily_log_20260902_EN.md` · `진행기록/LLM예측시험_5회_20260902.md` · `실험결과/*autoresearch*_20260902.txt` · `연동/20260902/`*
