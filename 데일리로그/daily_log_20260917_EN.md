# 2026-09-17 (Thu) — Chwijung Daily Log

> Paste each block into the matching form field. Counts are checked against the form limits.

| Field | Value |
|---|---|
| category | `final` |
| status | `completed` |

## title (40/40)
```text
Dashboard 4.6x faster; local LLM benched
```

## feature_name (93/100)
```text
Dashboard API speed, chat scroll, local LLM for the Q&A interpreter, backlog and presentation
```

## problems (186/200)
```text
The dashboard took 1.79 s and opened 35 DB connections. Chat jumped to the bottom on every reply. The Q&A agent relied on an external API with a shared free quota and no tested fallback.
```

## solution (184/200)
```text
Ran dashboard queries on a thread pool with one connection per request. Moved chat only on my own message. Added an ollama switch and graded local models on the same 17-question bench.
```

## result (172/200)
```text
Dashboard 0.39 s with 10 connections (#804 merged); chat fix merged (#809). Gemini 98.5% vs best local 87.9% at 12.3 s: Gemini stays. WBS backlog of 166 done items written.
```

## content (5654/6000)
````markdown
Development closed this week, so today mixed wrap-up work with a few last fixes. Two pull requests merged, a local LLM was measured and rejected for normal use, and the backlog and presentation material were prepared.

## Dashboard: 1.79 s to 0.39 s

The console dashboard felt slow. Measured on the API alone, one load took 1.79 s. Three causes were found.

- Seven lookups from five parts ran one after another.
- Each query opened its own database connection: 35 connections and 65 queries per load.
- Logistics sent the same 289-row schedule query twice, from two functions that did not know about each other.

Each step was measured on its own.

```text
                               time      connections
baseline                       1.787 s   35
1. share duplicate query       1.584 s   35
2. independent lookups at once 0.557 s   35
3. one read connection/request 0.532 s   10
final                          0.394 s   10
```

The lookups are ordinary synchronous functions, so a thread pool runs them in parallel without rewriting other parts' code. Writes still use their own connections. If one query fails, its shared connection is dropped so it cannot break the queries after it.

The response did not change. Full JSON from dev and from the branch was compared on three base dates, with zero differences. The backend suite passed 8,667 tests.

Two things looked like bugs but were not. The browser showed two identical requests, which is React Strict Mode in development only. The page still felt slower than 0.39 s because the development build ships about 7.9 MB of JavaScript.

This touched ten files owned by other parts. The master agreed in advance, and it went in as one PR (#804, merged).

## Chat Scroll

The master chat scrolled to the bottom whenever a reply arrived, even while the user was reading older messages. The first fix only stopped scrolling if the user had moved the scrollbar. It still jumped when they had not.

The rule is now simple. Sending my own message moves to the bottom. An incoming reply never moves the view. If the view is not at the bottom, a "new message" button appears. Merged as #809.

## Can the Q&A Interpreter Run Locally?

The interpreter reads a question and picks topic, crop, price type and dates from fixed lists. It calls Gemini once. The free tier allows 15 calls per minute and is shared by the team, so a local fallback was worth measuring.

A provider switch was added. The same JSON schema is passed to ollama's format option, with temperature 0. All 151 ML tests pass, and the default is still Gemini. The branch was kept local, with no PR.

The same bench was used as before: 17 questions with known answers, 4 slots each, 2 rounds, base date 09-14. Four slots expect answers that no model can give since the 09-16 route change, so 132 slots are judgeable.

```text
                    correct/132   per question   unstable questions
Gemini flash-lite     98.5%        1.5-1.8 s        not measured
gemma4:e2b            87.9%       12.3 s           8 of 17
exaone3.5:2.4b        72.7%        1.9 s           0 of 17
```

The GPU was an RTX 3050 with 6 GB. All three local models ran fully on GPU at Q4 quantization.

The decisive failure was scope. Both local models answered "green onion" and "garlic" by picking cabbage, radish or onion. The user would get a real price for the wrong crop. Gemini rejects them. gemma4 also changed its answer between rounds on 8 questions despite temperature 0.

Giving the model a fixed date list instead of free text helped both local models. exaone went from 27.2 s to 1.9 s per question; its free-text run also hit four 60-second timeouts.

Decision: Gemini stays in operation. A local model is only an emergency fallback, and a rule is needed first: discard the answer when the question names no supported crop but the crop slot is filled. That rule is not written yet. The full comparison is in the progress records.

## Backlog for the WBS

Four backlog files were updated with a status, completion date and evidence for each item. Items from 09-05 to 09-16 were added. A separate table lists only completed work, grouped by sprint, for the WBS: 166 items from 08-18 to 09-16. Nineteen dates had no record and were estimated from neighbouring work; they are marked.

## Presentation Material

Each part gives about one minute. Two versions were prepared.

- A Korean detail file: all three operating models side by side with hyperparameters, the 31 inputs with meaning and importance per model, input value ranges, the algorithm comparison, and error rates.
- An English one-minute plan: one message, four beats, two slides, a 107-word script and a Q&A sheet.

Seven charts were drawn in English and Korean. Tables were replaced because every comparison is "which bar is shorter". Improvement rates were replaced with error rates, and "best simple forecast" was renamed "baseline".

Two corrections were made along the way. The first draft said the model has 44 inputs; the operating bundles have 31, or 24 for retail. The chart showed cabbage auction error as 19.8% because 0.1975 rounds up; the log's error-rate column and every document say 19.7%, so the chart does too.

The error rates are copied from the 09-01 holdout logs, not re-measured, because the 2024-2025 test period was opened once and is closed. Retail figures come from the model before the 09-15 retrain. Only feature importance was computed today from the live model files.

## Smaller Items

- Font size across the frontend was raised by 4 px (#815, merged).
- A 2022 thesis on weekly tomato price forecasting at Garak market was read and compared with our approach.
````

**Sources (not for pasting):** root commits 11a62d1 · f934a8c · 109ec13; mainproject PRs #804 · #809 · #815; branch `test/ml-qa-local-llm_jh` 6dc7bee;
`진행기록/QA해석기_로컬LLM_비교_20260917.md`; `진행계획/WBS_완료백로그_20260917.md`;
`발표/최종발표_ML_QA_20260917.md`; `발표/1min_plan_ML_QA_20260917_EN.md`; `발표/그래프/make_final_charts.py`
