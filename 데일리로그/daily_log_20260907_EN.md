# 2026-09-07 (Mon) — Chwijung Daily Log

> Paste each block into the matching form field. Counts are checked against the form limits.

| Field | Value |
|---|---|
| category | `final` |
| status | `completed` |

## title (35/40)
```text
Retrain agent blocked a worse model
```

## feature_name (83/100)
```text
Retraining agent, null-handling fix, scraper stop, news agent and forecast backfill
```

## problems (172/200)
```text
The production model had not been retrained for 981 days, one day's auction target had vanished without any error, and a scraper was found to violate the site's robots.txt.
```

## solution (187/200)
```text
Built an agent that retrains, verifies and blocks weaker candidates; traced the lost day to nulls stored as the string 'None'; stopped the scraper; limited the news LLM to classification.
```

## result (169/200)
```text
A candidate worse on cabbage (−0.0155) and onion (−0.0086) was blocked; 46,941 corrupted values cleaned and 09-03 restored; 140 days (27,054 rows) delivered to Purchase.
```

## content (3816/6000)
````markdown
A retraining agent was introduced, and on its first use it declined to deploy a model retrained on 981 additional days of data because the new model performed worse. The same day, a collector defect that had erased one day of auction targets was traced to a single line, a scraper was stopped for violating the target site's crawling policy, a news-monitoring agent was built with deliberately restricted use of a language model, and 140 days of forecasts that had never been transmitted were delivered to the purchase team.

## Retraining Agent

The production model had been trained on data ending 2023-12-31, 981 days earlier. The agent judges whether retraining is warranted, builds a candidate, verifies it against the current model, and applies it only if it is better. The first candidate was worse on cabbage (−0.0155) and onion (−0.0086), and the agent blocked it. This result was consistent with the earlier finding that shortening the training history from 2015 to 2017 improved accuracy: more data does not guarantee a better model.

The alerting rule was replayed over history across 195 windows and produced one genuine alarm on the auction target. A safeguard was added for quiet markets, in which the anchor error becomes very small and ratio-based metrics can produce spurious alarms.

## Root-Cause Investigation: Missing Auction Day

The auction target for 2026-09-03 was entirely empty. The collector used a lookup of the form `get(key, default)`, which applies the default only when the key is absent. When the source returned the key with a null value, the code stored the literal string `'None'` in the package field. The package filter then matched no rows for that day.

In total, 46,941 values stored as `'None'` were cleaned. A helper function now converts nulls correctly, the affected days were re-collected and rebuilt, and 09-03 was restored (cabbage 731.8 KRW/kg). Two validation checks were added: an empty target day stops the batch, and the presence of the string `'None'` raises a warning.

## Interface Failure: Silent Button

The "build candidate" button in the interface appeared to do nothing. The agent's report contained an em dash, which the default Korean Windows console encoding (cp949) cannot print, raising an encoding error. UTF-8 output was enforced, and failures now display their log in the interface.

## Compliance Stop

The Garak market notice-board scraper was found to contravene the site's robots.txt policy, which disallows all crawling. The scraper was stopped. No information was lost: the three future closures it had identified were already recorded in an override table, and irregular closures are detected from actual trading-day data.

## News Agent

Agricultural trade publications contained only 0.12% of articles relevant to supply and prices, so collection moved to a news search API yielding about 114 relevant articles per day. Keyword rules could not distinguish homonyms, such as a singer's name that matches a crop name, so a local language model classifies article context. It is not permitted to write summaries, because it fabricated directional claims when asked to summarise.

## Backfill Delivery

Forecasts for 2026 existed in the prediction log but had never been transmitted to the purchase team's table. A total of 140 days (167 base dates, 27,054 rows) was delivered, and nine replies were sent to the purchase team, including an acknowledgement that the missing-day incident had originated on the ML side.

## Lessons Learned

- A retraining system is valuable only if it can refuse to deploy.
- Null handling at the point of ingestion must be explicit; a default argument does not protect against a key that is present with an empty value.
- Crawling permissions must be verified for every source, not only for newly added ones.
````

---

*Sources (not for pasting): `진행기록/daily_log_20260907_EN.md` · `연동/20260907/` (nine replies) · git history of 2026-09-07*
