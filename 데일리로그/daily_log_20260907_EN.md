# Daily Log — 2026-09-07 (Mon)

**Project:** Haetdeul Nongsan · ML team

---

## Summary

A retraining agent was built — and on its first use it **refused** to deploy a model
retrained on 981 more days of data, because the new model was worse. A collector bug
that emptied one day's auction target was traced to a single line. A scraper was
stopped for violating `robots.txt`. And 140 days of forecasts that existed but had
never been sent were delivered to the purchase team.

## 1. Retraining agent — judge, verify, replace from the screen

The production model's training had stopped 981 days earlier (end of 2023). A
retrain attempt made **cabbage worse (−0.0155) and onion worse (−0.0086)**, and the
agent blocked it from production. More data did not guarantee a better model — the
same lesson as cutting the training start from 2015 to 2017.

The alarm rule was replayed over history (`drift_replay.py`): of 195 windows, one real
alarm on auction. A guard was added for quiet markets, where anchor error becomes so
small that ratios explode into false alarms.

## 2. One day of auction targets had vanished

2026-09-03's auction target was **entirely NULL**. The collector wrote the **string
`'None'`** into the package field. Python's `.get(key, default)` only uses the default
when the key is **absent**; when the source sends the key with a null value, you get
`str(None)`. The package filter (`IN ('mesh bag', 'pallet')`) then matched nothing.

Cleaned 46,941 `'None'` strings, added a helper that maps nulls correctly, re-collected
and rebuilt. 09-03 was restored (cabbage 731.8 won/kg). Two checks were added so a
target gap stops the batch.

## 3. "Build" button did nothing

The candidate-model button died silently on Windows: the default console encoding
(cp949) cannot print an em dash (`—`) in the agent's report, raising
`UnicodeEncodeError`. Forced UTF-8 in the agent and made failures show their log on
screen.

## 4. Scraper stopped — `robots.txt`

The Garak market notice-board scraper was violating `robots.txt` (`Disallow: /`).
Stopped. Nothing is lost: the three future market closures it had found were already
in the override table, and irregular closures are detected from actual trading days.
(The scheduled task itself was only disabled on 09-10.)

## 5. News agent

Agricultural trade press had only 0.12% of articles about supply and prices; switched
to the Naver news search API (about 114 relevant articles a day). Regex rules could not
separate homonyms (the singer "Yangpa," "mu" as in "free"), so a local LLM
(`gemma3:4b`) classifies context — **and only classifies**. When asked to summarise
direction it hallucinated, so it is not allowed to write sentences.

## 6. 140 days delivered

Forecasts for 2026 existed in `prediction_log` but had never been pushed to the
purchase team's table: **140 days (167 base dates, 27,054 rows)** sent.

Nine replies to the purchase team that day, including one admitting that incident
#250 (`'None'`) was our own.

## Sources

- `진행기록/daily_log_20260907_EN.md`
- `연동/20260907/` (nine replies)
- git history of 2026-09-07 (#26–#33)
