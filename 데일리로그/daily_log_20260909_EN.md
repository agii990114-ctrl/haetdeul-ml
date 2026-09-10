# Daily Log — 2026-09-09 (Wed)

**Project:** Haetdeul Nongsan · ML team

---

## Summary

The ML part got four tabs in the shared operations console. Every piece of on-screen
text was rewritten. Retraining became fully automatic up to the point of a single
human click — and a deliberate simulation found three defects in that path, none of
which raised an error. Tonight's auction became a forecast target, and the lead-time
gates were switched off.

## 1. Lead 0 — forecasting tonight's auction

Garak auctions run **at night**; the batch runs in the morning. So the base date's own
auction has not happened yet and can be forecast — but the table had started at
lead 1. The purchase team could not get tonight's price from us.

Added lead 0 to the training and inference tables, rebuilt the production bundles
under the **same names** (the purchase filter matches names exactly), and set the
lead-time gates to `{auction: 0, wholesale: 3, retail: 0}`.

## 2. Four tabs in the shared console

Price forecast · batch status · AI reports · model retraining. The chart was drawn in
plain SVG with no charting library: many libraries join missing values to zero, and
our "not yet scored" days would read as a price crash.

## 3. 184 strings rewritten

After feedback that the reports were incomprehensible, every string on the ML screen
was rewritten — first into English, then back into plain Korean via a separate
translation pass. Server values stayed untouched (they are filter keys; changing them
returns zero rows with no error). **Breaking that once turned every status badge grey.**

## 4. Report pipeline: Claude drafts in English, Gemini translates

| Approach | Result |
|---|---|
| Gemini flash-lite writing alone | Escalated a false alarm; missed a handoff change |
| Local model (gemma) translating | Mistranslated crops; invented a number |
| **Gemini flash-lite translating** | **216 of 216 numbers preserved, twice** |

Investigation stays with Claude (some facts need direct database queries); flash-lite
only translates. A number check marks omissions — but cannot catch fabrications, so the
English draft is always kept alongside.

## 5. Retraining automated — and tested on purpose

The batch now judges, builds a candidate, and compares it after delivering the day's
forecasts. A losing candidate is deleted silently; a winning one shows a red badge and
a single "Update model" button.

The winning path had never been exercised, so a **deliberately weak model** (two years
of training) was installed in the production slot. Three silent defects surfaced:

```
① Thread id mismatch     badge appeared, button did nothing
② Stale snapshot          the screen kept showing a decision already made
③ Undeclared state field  LangGraph dropped "discarded" and reported "stopped"
```

## 6. Monitoring fixes

- A single em dash had killed the batch investigator for three days on the Korean
  Windows console — fixed once, in the shared core module
- Batch times shown in UTC (09:00 appeared as 00:00) — converted
- The grade-order check raised "50% inverted" on cabbage from **two days**, driven by
  one 50 kg lot against 518,140 kg. Added a minimum share and minimum day count;
  unmeasurable is shown as "not judged," never as 0%
- The same forecast read 422 on a card and 423 on the chart — the server truncated
  422.535 while the screen rounded. Truncation always makes purchase prices look
  cheaper; fixed to round

## 7. Replies to the purchase team

- Same-day forecast contract change
- **"We will not re-push the copy."** Past rows in their table are the record of what
  was actually sent; overwriting them would make the record claim something we never
  sent

## Sources

- `진행기록/daily_log_20260909_EN.md`
- `진행기록/재학습자동화_시험방법_20260909.md`
- git history of 2026-09-09
- `연동/20260909/`
