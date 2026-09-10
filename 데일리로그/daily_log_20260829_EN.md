# Daily Log — 2026-08-29 (Sat)

**Project:** Cost Catcher (later Haetdeul Nongsan) · ML team
**No development work.** Automated activity only.

---

## What happened

The 09:00 scheduled batch **failed** at the prediction step:

```
Missing input feature (1): ['_anchor_mix']
```

Cause: the shrink-anchor column added on 08-28 had been left in the model's input
list (see 08-28).

A failure alert was written to `ALERT.txt`. **Nobody opened it.** The purchase
team's handoff table stayed at 2026-08-28.

## Why this day is recorded

It is the first of three consecutive silent failures (08-29, 08-30, 08-31). Those
three days are the reason the batch-failure investigator was built on 08-31: the
alert existed, but an alert nobody reads is the same as no alert.

## Sources

- `진행기록/batch_logs/batch_2026-08-29.log`
