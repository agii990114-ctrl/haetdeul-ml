# 2026-09-14 (Mon) — Chwijung Daily Log

> Paste each block into the matching form field. Counts are checked against the form limits.

| Field | Value |
|---|---|
| category | `final` |
| status | `completed` |

## title (37/40)
```text
Forecast Q&A agent built and reviewed
```

## feature_name (98/100)
```text
Forecast question-answering agent, its interpretation layer, and the V13 calendar dependency check
```

## problems (199/200)
```text
The purchase team receives forecast numbers with no way to ask about them, and the master agent has no route into our part. Master also asked whether our pipeline depends on the V13 canonical window.
```

## solution (197/200)
```text
Built a LangGraph agent where code owns the numbers and the LLM only picks what was asked, exposed it as one question-shaped endpoint, and measured the calendar dependency rather than recalling it.
```

## result (177/200)
```text
POST and GET /ml/qa answer in markdown with source and error rate attached; 31 tests pass; PR #672 accepted for merge on 09-15. Calendar healthy: 741 rows, 0 mismatches in 2026.
```

## content (4748/6000)
````markdown
Today produced one new capability and two defects found by using it. The capability is a question-answering agent for our forecasts; the defects were both switches that looked connected and were not.

## The Calendar Dependency Question

Master sent a notice declaring V13 the canonical window and asked which parts depend on it. Rather than answer from memory, the dependency was measured. Our calendar table holds 741 rows, was last updated 2026-09-14 09:11 KST by the morning batch, and shows 0 mismatches against actual trading days in 2026. The reply stated that our pipeline reads the calendar but does not read the V13 window itself, so the change does not reach us.

## Why an Agent and Not Document Search

The first idea was retrieval over our documents. It was dropped. The questions that actually arrive are about numbers we already store, and a master agent would not route a document question to the forecasting part in the first place. Retrieval would have added a way for the answer to drift from the table.

## Design: the Code Owns the Numbers

The agent is a small state machine with four steps: interpret, check, fetch, compose. The LLM runs only in the first step and only chooses four things, each constrained to a fixed list: what kind of question it is, which crop, which price series, and which dates. It never produces a price and never writes the answer sentence.

The second step re-checks everything the LLM chose. Constraining a response schema does not guarantee the value is in range: whether a date falls inside the 18-day horizon, and whether that row exists, are questions only the table can answer. A crop outside our three is refused there, not by the model.

Four read-only tools produce every number. The answer is assembled from templates, so the wording cannot invent a figure that the tools did not return. When a source cannot be read, the answer says so instead of falling back to an example value.

## The Accuracy Number Had to Match the Screen

The first version computed the average error from the prediction log and reported 19.7% as 15.1%. Both numbers were arithmetically correct; they came from different windows, and the log also mixes experimental bundles. The screen shows the sealed-run figure. Computation was replaced with the sealed constants for all nine crop-and-series combinations, each carried with its conditions: sealed run 2026-09-01, holdout 2024-2025, 486 base dates, lead time 3 and above. One fact must not have two numbers in circulation.

## Two Switches That Were Not Connected

**The Swagger default body.** The interactive documentation pre-fills the crop field with the literal text "string". The agent read that as a crop, refused the request as out of scope, and never looked at the question. Explicit arguments are now used only when valid; otherwise the question is interpreted and the ignored value is named in the answer.

**The disable switch.** A function existed to turn the LLM off through an environment variable, and nothing called it. Setting it to 0 still called the model. This matters beyond correctness: the team is sharing a quota that returned a rate-limit error today, and a switch that reports off while calling is worse than no switch. The check now runs immediately before the call, and a test asserts that no request is made by making the call function raise.

## What It Still Does Not Do

Asked for the average of two days, the agent returns both days and never uses the word average. The interpretation step has no field for aggregation, so the word is dropped silently. On the day it was found, the two values were identical, so the answer looked correct by coincidence. A silent drop is the worst shape of this failure: the reader cannot tell that part of the question was ignored. The fix adds one aggregation field, with the arithmetic done in code and applied to the predicted value only. Averaging two intervals produces a number with no meaning.

This was deferred rather than fixed. The values, intervals, and sources being returned are all correct, and the pull request is queued for merge tomorrow evening; changing the response shape now would enlarge what the reviewer has to check.

## Review and Merge

The reviewer accepted the direction: our part only, read-only, no overlap with other work. Merge was scheduled for 09-15 between 17:00 and 21:00, after a demonstration, because the LLM quota is shared and paused until then. Two process corrections were requested and applied: attribution lines removed from the pull request body, and no such lines in new commits.

Our own testing today made repeated live model calls against that shared quota without knowing it was shared. That was reported rather than left for them to find.
````
