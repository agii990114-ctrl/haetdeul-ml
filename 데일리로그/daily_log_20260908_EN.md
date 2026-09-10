# Daily Log — 2026-09-08 (Tue)

**Project:** Haetdeul Nongsan · ML team

---

## Summary

The retraining flow was written down as a canonical spec, then rebuilt as a LangGraph
state machine — with **no LLM in any node**. The cause of a "dead server that kept
answering" was found. And a reply to the purchase team began with "I was wrong."

## 1. Retraining flow as a state machine

First, the existing flow was written up in English as the canonical spec: states,
what each node does, thresholds, the two places a person steps in, and where each
part runs.

Then rebuilt as a LangGraph state machine, running side by side with the old flow:

```
judge → build → verify → (ask a person) → apply
```

★ **It is a state machine, not an agent framework.** No node calls an LLM; every
decision is a rule. This matters for the presentation — without saying so, it reads
as "we let AI decide whether to retrain."

Wired to the screen:

```
GET  /retrain/graph/status   where the flow is standing (reads the checkpoint)
POST /retrain/graph/act      judge / build / apply / stop
```

## 2. The dead server that kept answering

A newly added API returned 404 even though the code was correct — an old server was
still answering. **Cause:** `uvicorn --reload` starts two processes; when the reloader
died, the old worker kept the port. Recorded as casebook entry D8.

## 3. Replies to the purchase team

- **Per-lead-time excess quantile table** — the item blocking their 09-17 formula.
  Measured the **one-sided excess** `(actual − forecast) / forecast`, positive side
  only, because a purchase price below forecast is not a problem.
- **"#242 — I was wrong."** We had claimed their code would have rejected a mis-dated
  row. It reads only `base_dt`, not `generated_at`, so it would not have. Stated plainly
  because a false "we would have caught it" leaves a check believed to exist where none
  does.
- Business-day width and grade ratio table.

## 4. Preparation for the next day

A training table with **lead 0** (the base date's own night auction) was prepared
(`train_lead0_20260908.csv`), leading to the next day's change.

## Sources

- git history of 2026-09-08 (#34–#37)
- `연동/20260908/` (two replies)
- `진행기록/retrain_flow_EN.md`
