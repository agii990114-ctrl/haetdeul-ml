# Daily Logs — Haetdeul Nongsan · ML team (Chwijung format)

One English file per working day, 2026-08-18 to 2026-09-10, laid out to match the
Chwijung daily-log form so each field can be pasted directly.

## How to use a file

Each file contains the seven form fields in order. Copy the text **inside each box**
into the field of the same name.

| Field | Form limit | Notes |
|---|---|---|
| `category` | — | `final` for every entry |
| `status` | — | `completed` for every entry |
| `title` | 40 | Achievement-focused summary |
| `feature_name` | 100 | Feature or domain worked on |
| `problems` | 200 | Situation and why it was difficult |
| `solution` | 200 | Approach, decision and rationale |
| `result` | 200 | Outcome, with figures where available |
| `content` | 6,000 | Depth only: investigation, alternatives, lessons. Markdown |

The number in brackets beside each heading, e.g. `title (39/40)`, is the measured
character count against the form limit. Every field was checked by script.

The line **"Sources (not for pasting)"** at the bottom of each file is for reference
only — do not paste it.

## Before pasting

**Already submitted to Chwijung** (per project records) — submit again only to replace:

| Date | Previously submitted |
|---|---|
| 08-25 | Two entries (scheduler rollout · shared-repository survey) |
| 08-26 | Two entries (two-stage forecasting rejected · fold-B cause) |
| 09-09 | One entry |
| 09-10 | One entry, in Korean, status `in_progress` |

**Operations-only days** — no development work took place. Submission is optional:
08-29, 08-30 (batch failures) and 09-05, 09-06 (clean unattended runs).

**Language.** The Chwijung form guidance asks for Korean. These entries are in English
by request.

## Records gaps

08-12 to 08-17 has no per-day records; the 08-18 entry covers that week. 08-19, 08-20
and 08-22 were reconstructed from dated training kits, SQL headers and result files
(listed under *Sources* in each file). No work is recorded for 08-23, so no file exists for it.

---

| Date | Day | title |
|---|---|---|
| [08-18](daily_log_20260818_EN.md) | Tue | First model failed to beat the baseline |
| [08-19](daily_log_20260819_EN.md) | Wed | Learning and lead-time curves measured |
| [08-20](daily_log_20260820_EN.md) | Thu | Three-target kit; arrivals back to 2015 |
| [08-21](daily_log_20260821_EN.md) | Fri | Three-target model and pooled-WMAPE fix |
| [08-22](daily_log_20260822_EN.md) | Sat | Economic variables removed by ablation |
| [08-24](daily_log_20260824_EN.md) | Mon | Evaluation protocol and two-fold rule |
| [08-25](daily_log_20260825_EN.md) | Tue | End-to-end batch pipeline went live |
| [08-26](daily_log_20260826_EN.md) | Wed | Two-stage forecast rejected before build |
| [08-27](daily_log_20260827_EN.md) | Thu | Fixed auction target mixing 15 products |
| [08-28](daily_log_20260828_EN.md) | Fri | Shrink anchor and answer-rule fix |
| [08-29](daily_log_20260829_EN.md) | Sat | *Operations only* — Batch failed silently on a weekend run |
| [08-30](daily_log_20260830_EN.md) | Sun | *Operations only* — Second consecutive silent batch failure |
| [08-31](daily_log_20260831_EN.md) | Mon | Batch outage fixed and monitors built |
| [09-01](daily_log_20260901_EN.md) | Tue | Condition-aware intervals via quantiles |
| [09-02](daily_log_20260902_EN.md) | Wed | False alarm fixed; 587 trials, none kept |
| [09-03](daily_log_20260903_EN.md) | Thu | Quantile bands live; 9 items closed |
| [09-04](daily_log_20260904_EN.md) | Fri | Stale base dates and unread checks fixed |
| [09-05](daily_log_20260905_EN.md) | Sat | *Operations only* — Unattended cycle completed cleanly |
| [09-06](daily_log_20260906_EN.md) | Sun | *Operations only* — Second clean unattended cycle |
| [09-07](daily_log_20260907_EN.md) | Mon | Retrain agent blocked a worse model |
| [09-08](daily_log_20260908_EN.md) | Tue | Retraining rebuilt as a state machine |
| [09-09](daily_log_20260909_EN.md) | Wed | ML console, lead 0 and auto-retraining |
| [09-10](daily_log_20260910_EN.md) | Thu | False alarm fixed; rerun buttons added |

---

**Related documents:** `진행기록/experiment_ledger_EN.md` (every experiment and verdict) ·
`진행기록/development_progress_EN.md` (build history to 09-04) ·
`발표/ML_price_forecasting_paper_EN.md` (method and results)
