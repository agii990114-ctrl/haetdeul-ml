# Daily Log — 2026-09-02

**Cost Catcher · ML (Jihwan)** · written 2026-09-02 17:49:15

---

## 1. Fixed a false alarm in the batch monitor

Asked the batch agent for status at 09:11:40. It reported **"failure · structural
error."** The batch had actually finished at 09:11:45 with all 10 stages green —
**a 5-second race.**

**Cause:** `batch_run.status` starts as `'running'` and becomes
`'ok'/'partial'/'fail'` at the end. The agent only whitelisted `'ok'` and treated
everything else — including in-progress — as failure.

**Fix:** a `running` branch that reports "still running, N minutes elapsed," and
only escalates to failure past 45 minutes (normal run ≈ 10 min). Verified by
temporarily flipping the status and restoring it.

**Why this mattered:** a false alarm triggers the AI investigation (cost) and
appends to `ALERT.txt`. If that fires daily, people learn to ignore alerts — and
real failures get buried with them. We have already been bitten by that.

`agent/batch_agent.py` (backup `.bak_running`)

---

## 2. Autoresearch — 587 trials, 0 adopted

Adapted Karpathy's AutoResearch loop (2026-03-07) to our rules.

**Kept:** write → run → evaluate → iterate, unattended; keep on improvement,
roll back otherwise.

**Changed four things:**

| | Original | Ours |
|---|---|---|
| Score | one validation WMAPE | **our decision rule** (2 folds same sign · > 2×seed-sd · no item worse) |
| Rollback | `git commit` / `reset` | file snapshots (our tree wasn't a git repo) |
| Scope | any file | **features locked** — hyperparameters only |
| Who writes | LLM writes code | search; the LLM adds nothing for 7 numeric knobs |

**Why features are locked:** a score-only loop *will* drop `lead_biz_d`. Pooled
WMAPE improves — and the model can no longer tell "tomorrow" from "three weeks
out." That kills the product. It is a documented trap in our CLAUDE.md.

**Held-out fold.** 200 trials will find something that beats folds A and B by
luck. Fold C (valid 2021) was never used during search and checked once at the end.

### Results

| Target | Trials | Accepted | Fold C | Verdict |
|---|---|---|---|---|
| Auction | 198 | 1 | passed (+0.0059) | **held** — per-item signs split |
| Wholesale | 200 | **0** | — | **current settings are best** |
| Retail | 189 | 1 | **rejected (−0.0024)** | **discarded** |

**The retail case is the most valuable result.** The held-out fold caught an
overfit that both search folds had approved. And the *direction* explains why:

```
Auction candidate (passed C)   trees 76→50 · L2 1.0→30 · feature 0.8→0.5
                               "memorize less"
Retail candidate (failed C)    trees 81→200 · leaves 31→63 · min_leaf 60→20
                               "memorize more"
```

**Only the one that reduced capacity survived.**

**Re-confirmed the auction candidate with 20 seeds:** folds A and B fell below
their own thresholds (+0.0012 / need 0.0018; +0.0018 / need 0.0029). Fold C still
passed (+0.0059 / 0.0042), but **no item improved consistently across three
folds** — the gain is almost entirely onion on fold C (+0.0149). Per §8, per-item
beats pooled. **Not adopted.**

`auto_research.py` · `confirm_params.py` · backlog [M-23]

---

## 3. LLM prediction test — what happens when you give it more

Documented the 5-run baseline, then tested three variants. **All three got worse.**

| Condition | WMAPE (LT≥3) | vs anchor | distance from baseline |
|---|---|---|---|
| Anchor | 0.1893 | — | |
| LightGBM | 0.1809 | +4.4% | |
| **Baseline (14-day summaries)** | **0.1774** | **+6.3%** | 5 runs · sd 0.0025 |
| + 60 trading days of raw prices | 0.2005 | −5.9% | **9.2 sd** |
| + mid-term weather forecast | 0.1868 | +1.3% | **3.7 sd** |
| English prompt | 0.1890 | +0.2% | **4.6 sd** |

### Found the mechanism — it over-extrapolates

Measured how far each block's last step drifts from its first:

| Condition | Mean slope | WMAPE |
|---|---|---|
| LightGBM | **2.1%** | 0.1809 |
| Baseline | 7.6% | 0.1774 |
| + forecast | 10.3% | 0.1868 |
| + 60-day history | **15.2%** | 0.2005 |
| *(actual)* | *30.1%* | |

**Slope and error move together, inversely to performance.** Give it more, and it
builds a story — "prices are climbing, so they'll keep climbing." Cabbage auction
prices have day-to-day autocorrelation of 0.795: the story holds for a day or two,
not for three weeks.

**The English prompt is the sharpest evidence.** No extra data at all — only the
wording changed — and it still got worse.

Worst mis-extrapolations with 60-day history:

| Block | Item | LLM slope | Actual |
|---|---|---|---|
| B10 | cabbage | +44.1% | **−1.1%** |
| B14 | radish | +29.2% | **−74.1%** |

**Note on the mid-term forecast.** It is genuinely forward-looking and leak-free
(issued 06:00 on the base date, full history from 2015, 477,837 rows, already in
our DB). But it only covers calendar D+3–D+10 — business-day horizons 1–8 — and
**LT13–18, where the LLM is strongest, was empty.**

### Ensembling works, and 2 runs is enough

| Runs | Mean | **Worst** | vs anchor |
|---|---|---|---|
| 1 | 0.1772 | **0.1806** | +6.4% |
| **2** | **0.1754** | **0.1772** | +7.3% |
| 3 | 0.1748 | 0.1761 | +7.7% |
| 4 | 0.1744 | — | +7.8% |

**The "worst" column decides it.** One run is a coin flip — draw the bad one and
you match LightGBM (0.1809). Two runs beat LightGBM on every combination, and
capture two-thirds of the total gain.

### Larger sample reproduced the per-item ordering

Went from 10 to 17 base dates (51 blocks, 759 rows).
Anchor 0.2064 · LightGBM 0.1948 · LLM 0.1897.

| Item | 10 dates (5-run avg) | 17 dates (1 run) | 9 dates (2-run ens.) |
|---|---|---|---|
| **Cabbage** | LLM wins | **LLM +8.1%** | **LLM +10.0%** |
| Radish | LLM slight | LLM +1.9% | LLM +8.5% |
| **Onion** | **LightGBM wins** | **LightGBM +4.0%** | **LightGBM +4.0%** |

**Three different samples, same ordering.** Cabbage — our worst item, and the one
the buying team flagged (57% buffer breach at D+14) — is where the LLM leads.

**Still not going to production:** run-to-run spread of 3–7%, 162 queries a day
versus 2 seconds, and no reproducibility. Our first principle is "record no number
without its conditions"; that principle does not survive an unreproducible
predictor.

`진행기록/LLM예측시험_5회_20260902.md` · backlog [M-24]

---

## 4. Two ways the LLM's answers break — and a checker

### ① Shift-copy

Gave it 27 cabbage-only blocks at once. It produced one long sequence and slid it
two positions per block:

```
B01  471, 544, 570, 579, 555, 574, 414, 380, …
B02            570, 579, 555, 574, 414, 380, …
B03                      555, 574, 414, 380, …
```

B01→B05 all matched under a 2-step shift. **Cause: too many near-identical
blocks.** The prompts that had worked alternated cabbage/radish/onion, which made
blocks distinguishable. My attempt to grow the sample created the problem.

Fixed three ways — anchor in the block title, an explicit "do not shift or copy"
instruction, and splitting into ~26-block files. **Clean four times running
since**, and run-to-run spread dropped from 3.2–7.4% to 2.7% as a side effect.

### ② All-rising

A later run had no shift-copy but **all 25 blocks rose** — mean +35.3%, max
+120.6%, starting points spread across 945–1158 but all converging to 1134–1186.
That is the over-extrapolation above, at its extreme. Instructions did not stop it.

### The checker

`check_answer.py` — shift-copy, day-over-day jaggedness, distance from the block's
own anchor, block/cell counts. **Run before every scoring.** It caught ② (three
blocks more than 25% off their anchor).

**Why this matters:** scoring a broken answer records *"the method performed
poorly"* when in fact there was no answer. A wrong experimental result in the
record is worse than no result.

---

## 5. News — investigated properly instead of inferring

I had concluded "we can't get news" from article counts alone. That was inference,
not measurement, and it was challenged. Redid it.

**Naver API HUB** — free for now (usage-based pricing announced, notice before
switching). **But no date-range parameter, and a hard 1,000-result cap per query.**
You cannot ask for "articles from June." For a broad query you cannot reach back
three months.

**Agricultural trade papers turned out better than the API** — their list pages
filter by date exactly, which makes as-of control structural rather than
best-effort.

```
Korea Farmers & Fishermen's News   robots.txt: /admin/ only · date filter works
Agriculture Fisheries Livestock    robots.txt: /admin/ only · date filter works
Nongmin Shinmun                    date parameter does nothing → excluded
```

**Three traps found and fixed:**

```
① Nongmin's ?date= is ignored — same 14 articles for 8/11, 8/12, 6/15
② "Most-read" sidebar rides along on every request → today's articles would
   have leaked into June predictions. Filtered by dropping any article
   appearing on more than one date (20 of them)
③ Link format differs by site (absolute vs relative) — one paper silently
   returned zero
```

**Collected 2026-06-01 to 08-31:** 2,034 articles over 72 days; 58 mention our
items with price/supply context; 37 of 72 days have at least one; **0.8 per day.**

Thin — but a 21-day window puts articles into **27 of 30 blocks (90%)**, and some
are exactly the forward-looking statements our 31 features lack:

```
08-07  KREI outlook centre: cabbage/radish shipments up, prices expected to fall
08-11  Cabbage shipments to fall; stored spring crop caps the upside
```

**Prompt built and leak-checked: 243 articles cross-referenced, 0 dated on or
after their base date.** Test not yet run.

`데이터 수집/뉴스/fetch_agri_news.py` · `실험결과/llm_prompt_news.md`

---

## 6. Quantile band cutover — prepared, notified, answered

Built `cutover_quantile.py` (swap in place, keep the old bundle, one-command
rollback). Its pre-check verifies `fixed_iter` and `anchor_alpha` are identical
between bundles — **if either differs, the point predictions change and the swap
must not proceed.**

Sent an advance notice. The buying team came back with three questions; answered
all three by measurement.

### ① Which axis was my width measured on?

Mine was `AUC · all business-day horizons · per item` — none of the five axes they
use. Recomputed on theirs (2025-12-31, calendar offsets):

| Axis | Old (fixed table) | New (quantile) |
|---|---|---|
| AUC · D+14 · cabbage+radish | **0.676** | 0.544 |
| AUC · D+14 · 3 items | **0.562** | 0.474 |
| AUC · all offsets · 3 items | **0.477** | 0.445 |
| All kinds · D+14 | **0.436** | 0.388 |
| All kinds · all offsets | **0.355** | 0.337 |

**The old column matches their measurements to three decimals** (0.676/0.675,
0.477/0.477, 0.436/0.436, 0.355/0.354) — confirmation we are measuring the same
thing.

Per item at D+14: cabbage 0.662→0.484, radish 0.690→0.603, **onion 0.332→0.334
(essentially unchanged** — it is already at target hit rate, so there is nothing
to tighten).

### ② Will past base dates be regenerated?

**No.** `push_forecast.py` pushes `MAX(base_dt)` only. The 8-27 overwrite they saw
was the day we introduced the shrinkage anchor, which changed `predicted` for that
base date — hence `change_reason='price,band'`. This change does not touch
`predicted`. Full history audit: **2025-12-31 has never been overwritten.** Their
capture set stays valid.

### ③ Can we put a marker in `change_reason`?

Not directly — that column is produced by a trigger in their schema.
**Better alternative:** re-push one recent base date right after the swap. Since
`predicted` is unchanged, the trigger emits exactly `'band'` — and that is not only
a marker but **proof that only the interval moved.** Any price change would have
produced `'price,band'`.

### On their conclusion that the band change doesn't revive their aggressive plan

Agreed. The minimum `ci_width` is 0.332 (onion) and their threshold is 0.08. We
overstated on 8-28 when we said the decision branch comes back; that only holds if
the threshold moves too.

What *does* change: the current band cannot see the day at all (calm-vs-volatile
width ratio is exactly **1.00** within an item); the new one ranges **1.23–2.49**.
Once a threshold exists, "today is a narrow day" becomes selectable. It is not
selectable now.

`연동/20260902/` — two documents, both sent

---

## 7. Published the repository

**github.com/agii990114-ctrl/wonga-catcher-ml** — public, 765 files, ~3 MB.

Six pre-publish checks passed. Three things were caught on the way:

**①** `__MACOSX/._.env` — the name doesn't end in `.env`, so the ignore rule
missed it. (macOS leaves these when a zip is unpacked there.)

**②** `agent/mask.py` had our **real DB host** in its test fixture. The module that
redacts secrets was leaking one.

**③ I broke working code.** I replaced the IP in `next.config.ts` with a
placeholder — but that line is live configuration, not documentation. The dev
server would have stopped serving on the LAN. Moved it to
`NEXT_PUBLIC_DEV_ORIGINS` with an example file, which satisfies both.

Excluded: 7 `.env` files, `mainproject/` (shared team repo, read-only for us),
3.7 GB of CSVs (regenerable from the DB), trained bundles, internal IPs, and the
`context/`+`연동/` folders — those carry colleagues' names and the buying team's
cost structure, and nobody consented to publishing those.

---

## Where things stand

```
Waiting     buying team's cutover date  →  quantile swap (prep complete)
Ready       news prompt (30 blocks, leak-checked) — needs a fresh session
Blocked     holiday-feature change — must not land alongside the quantile swap,
            or neither effect can be attributed
```

## The through-line of the past two days

Six independent methods now say the same thing about this dataset:

```
09-01  effective sample is 1,475 unique base dates
09-01  more trees is worse (50 → 0.1665 · 1200 → 0.1855)
09-01  17 of 28 inputs are constant within a base date
09-01  MLP gets lost as it grows
09-02  autoresearch: "memorize less" survives the held-out fold, "memorize more" fails
09-02  a model trained on 9 years is indistinguishable from 14-day summaries
```

And CLAUDE.md §5.1 already had it: cutting training start from 2015 to 2017
**removed data and improved performance** (+5.9% → +6.8%).

## Corrections I made today

```
· Concluded "news won't work" from article counts without running it. Redone.
· Reported band widths without stating the axis. Recomputed on theirs.
· Broke next.config.ts while scrubbing IPs. Fixed with an env var.
· Overstated on 8-28 that the band change revives their decision branch.
  It only does if the threshold moves too.
```
