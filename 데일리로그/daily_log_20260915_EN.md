# 2026-09-15 (Tue) — Chwijung Daily Log

> Paste each block into the matching form field. Counts are checked against the form limits.

| Field | Value |
|---|---|
| category | `final` |
| status | `completed` |

## title (38/40)
```text
Q&A agent wired to master; dates fixed
```

## feature_name (86/100)
```text
Master agent port for the forecast Q&A agent, and date and multi-series interpretation
```

## problems (181/200)
```text
The Q&A agent was reachable only through a test API. Once used from the console it misread dates: "every day" gave one day, far dates returned today, and "today" read future values.
```

## solution (179/200)
```text
Added a port master calls directly, kept the API for testing, let the LLM pick dates from a code-built list, made every schema field required, and bound today to the console date.
```

## result (148/200)
```text
Five PRs merged (#672, #687, #694, #700, #701); master registered our port; #707 open; 76 ML tests pass. Korean prompt scored 100% vs English 93.8%.
```

## content (4739/6000)
````markdown
Today the forecast Q&A agent went from a test endpoint to something the master agent can call. Using it from the real console then exposed five interpretation defects in one afternoon. All were fixed except one, which is open for review.

## Wiring to Master Without the API

Other parts connect to master as in-process functions, not HTTP calls. We did the same: one function that takes master's request and returns a reply plus execution metadata. The test API stays, because we still test through it.

Master's reply checker rejected the first version with four findings. It requires every claim to point at a field in our payload, such as the predicted value of the first forecast row. The payload was reshaped so each number has an address. Master then asked for two changes: read the question from one key only, and keep code names such as series identifiers out of the answer text. Both were applied. The port merged as #687, and master registered it in their own PR.

## Does an English Prompt Work Better?

A common claim is that English instructions produce better results. We had never measured it. The model, temperature, schema, questions, and base date were held fixed, and only the system prompt language changed. Twelve questions with known answers were graded on four fields each.

```text
runs 1-2 (96 cells)   Korean 100.0%   English 93.8%
run 3    (48 cells)   Korean  97.9%   English 95.8%
```

English failed in the same places every time. It read "today's onion wholesale price" as the auction price in all three runs. The crop and price names are Korean, so an English prompt adds a translation step. Korean stays the default.

The first run was invalid. Korean calls went first without pauses, used up the free tier's 15 requests per minute, and all 24 English calls were rejected. The grader recorded that as "English 4.2%." A failed call and a wrong answer must never share a column. The bench now paces calls, alternates languages, and counts failures separately.

## Dates: Let the Model Choose From a List

Asked for "every day", the agent returned one day. Code now builds the 19 dates that can be answered, today plus 18, and the model can only pick from that list. The range words stayed with the model, as an experiment rather than hard-coded rules.

It still skipped dates entirely. The schema listed only the question type as required, so the model was allowed to leave dates out, and it did. Every field is now required, and a test fails if any field becomes optional.

When no date is given, the answer uses today and says so. When something is missing, it asks only for the missing part and states what it understood.

## Several Crops, Several Series

"Cabbage auction and wholesale price" needs two tables. Crops and series are now lists, with one table per pair. "Cabbage auction in 5 days and radish wholesale in 7 days" must not become a 2×2 grid, so the model returns explicit pairs. The model also kept adding series nobody asked for. Two prompt revisions failed to stop it, so a code rule now removes series not named in the question.

## "Today" Was Reading the Future

Today's value came from the latest base date in the prediction log, not the date the console was set to. With the console on February, the answer showed September 15. Nothing raised an error. The lookup is now bound to the chosen base date, with a test.

## Out of Range Returned Today

Asked "radish price in 30 days", the agent answered with today's price. The date was not in the list, so the model dropped it and the default filled in. The model now reports out-of-list days as offsets. Code converts them, and the answer says which dates can be answered. This is #707, still open.

## Smaller Defects

- A 500 error: the database returns the current price as a decimal and the schema expected an integer. It is now rounded, with a decimal test.
- Our adapter test shared a file name with purchase's test, so pytest refused to collect both. Ours was renamed at master's request.
- A benchmark script had been placed outside our folder. It was moved into it.
- Answer text was trimmed. Explanation lines moved to metadata, and the note on copied values now reads "Holidays use the previous forecast."

## Purchase Hand-off

We proposed delivering all 19 forecasts. Purchase replied that their decision row, day 14, already carries lead times 7 to 10, and they are not changing their reader. We explained why today cannot be added to their daily array: their contract requires the first row to be tomorrow.

## Not Yet Testable on the Domain

The team domains serve the deployed main image, which does not include today's work. Testing there needs a dev-to-main merge and the ML console address passed to the container.
````
