# Daily Logs — Haetdeul Nongsan · ML team

One English file per working day, from project start (2026-08-12) to 2026-09-10.

**How these were made.** Reconstructed on 2026-09-10 from the project's own records —
dated documents in `진행기록/`, experiment outputs in `실험결과/`, replies in `연동/`,
session logs in `참고/Claude/`, batch and agent logs, and git history. Every entry
lists its sources at the bottom. Nothing was added that the records do not show.

**Project name.** "Cost Catcher" (원가 캣쳐) until 2026-09-03, then "Haetdeul Nongsan"
(햇들농산). Entries use the name in force on that day.

**Gaps.** 08-12 → 08-17 has no per-day records; the 08-18 entry covers that week from
the progress record written that day. No records exist for 08-19, 08-20, 08-22 and
08-23, so there are no files for them.

---

| Date | Day | One line |
|---|---|---|
| [08-18](daily_log_20260818_EN.md) | Tue | Project start (08-12 →). First model could not beat yesterday's price |
| [08-21](daily_log_20260821_EN.md) | Fri | Three targets (auction · wholesale · retail). Pooled-WMAPE illusion found |
| [08-24](daily_log_20260824_EN.md) | Mon | Test window sealed. Two-fold rule born. Three silent defects fixed |
| [08-25](daily_log_20260825_EN.md) | Tue | Batch pipeline end to end · scheduler · first live scoring reversed by afternoon |
| [08-26](daily_log_20260826_EN.md) | Wed | First unattended run · two-stage forecasting rejected · fold B = typhoon |
| [08-27](daily_log_20260827_EN.md) | Thu | ★★ Auction target was 15 products averaged together |
| [08-28](daily_log_20260828_EN.md) | Fri | Shrink anchor adopted · auction error 22.5% → 17.5% · one detail missed |
| [08-29](daily_log_20260829_EN.md) | Sat | *Automated only* — batch failed (`_anchor_mix`), nobody saw it |
| [08-30](daily_log_20260830_EN.md) | Sun | *Automated only* — batch failed again |
| [08-31](daily_log_20260831_EN.md) | Mon | Three-day failure found · monitoring helpers built · scoring was 74% wrong |
| [09-01](daily_log_20260901_EN.md) | Tue | Quantile intervals · test window opened once · correction sent (cabbage inverted) |
| [09-02](daily_log_20260902_EN.md) | Wed | Five-second false alarm · 587 autotuning trials, 0 adopted · LLM trial |
| [09-03](daily_log_20260903_EN.md) | Thu | Renamed · quantile bands live · harness trained on garlic · fold-C rule |
| [09-04](daily_log_20260904_EN.md) | Fri | "It exists, and nobody looks at it" — three defects · per-crop split reversed live |
| [09-05](daily_log_20260905_EN.md) | Sat | *Automated only* — full cycle ran clean |
| [09-06](daily_log_20260906_EN.md) | Sun | *Automated only* — full cycle ran clean |
| [09-07](daily_log_20260907_EN.md) | Mon | Retrain agent refused a worse model · `'None'` bug · scraper stopped · 140 days sent |
| [09-08](daily_log_20260908_EN.md) | Tue | Retraining as a LangGraph state machine (no LLM) · "#242 — I was wrong" |
| [09-09](daily_log_20260909_EN.md) | Wed | Four console tabs · 184 strings · lead 0 · retraining automated and stress-tested |
| [09-10](daily_log_20260910_EN.md) | Thu | Batch false alarm · rerun buttons · remote access · retrain threshold · sequence models |

---

**Related documents**

- `진행기록/experiment_ledger_EN.md` — every experiment, its conditions and verdict
- `진행기록/development_progress_EN.md` — what was built, in order (to 09-04)
- `발표/ML_price_forecasting_paper_EN.md` — method and results as a paper
