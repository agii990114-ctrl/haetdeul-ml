# Daily post-batch check — 2026-09-09 (Wed)

Checked 09:23:18 – 09:26:56 (KST) · unattended · **nothing was changed**

---

## Bottom line

**The batch is fine and the hand-off table got today's base date. Two things to report** —
① the data-quality check reported a Problem, but it is a **false alarm built on two days of data** (not a real fault).
② the table we send to the purchasing team **changed shape today** — 12 rows for the nearest dates (leads 1–2) now carry **model values instead of yesterday's price**. A person made that change last night on purpose; it is not a fault.

---

## 1. Batch result: fine — 0 failures

`python agent/batch_agent.py` → verdict **OK**

```
run 65   started 2026-09-09 09:00:02 · 11 succeeded · 0 failed
         no day was skipped · last hand-off 0 hours ago
```

**No stage failed twice in a row. No error text.**

### Side note · the check tool died again on a cp949 console (third day · not fixed)

```
UnicodeEncodeError: 'cp949' codec can't encode character '—' in position 322
   agent/batch_agent.py:520 -> 480   print(rep.text())
```

It is one character: the long dash used in the output. Passing
`PYTHONIOENCODING=utf-8` makes it run normally (the result above was produced
that way). The 09-07 and 09-08 reports already say the same thing.
**This has nothing to do with the batch itself** (the batch writes its own log).
But it is a place where **a successful check looks like a failure.**
Left unfixed, as instructed.

---

## 2. Data quality: **1 Problem — investigated, false alarm**

`python agent/quality_agent.py --days 180` → verdict **Problem**
(the three days before this were all OK.)

### What went off

```
*** Grade order (top >= second)  worst inversion rate 50%
      napa cabbage inverted   1 of 2 days (50%)     <- yesterday it was 0 of 1
      radish inverted       4 of 103 days (4%)
      onion inverted         1 of 23 days (4%)
```

The rule is: a Problem when the inversion rate is above 30%.
**For napa cabbage the denominator is 2 days.**

### What I found by looking at the rows — one 50 kg trade produced this number

Within our target pack spec (net bag / pallet 10 kg) there are only **two days
in 180** with any second-grade napa cabbage at all. Those two days look like this:

```
2026-09-02   top 836.2 KRW (286,360 kg · 3 trades)   second 750.0 KRW (   90 kg · 1 trade)   normal
2026-09-08   top 647.6 KRW (518,140 kg · 4 trades)   second 750.0 KRW (   50 kg · 1 trade)   inverted
```

**A single 50 kg trade that arrived yesterday** (0.0097% of the 518 tonnes) came
in above the top-grade average, and that is what makes 1 of 2 days = 50%.

Second-grade napa cabbage is normally traded in **8 kg boxes** (207 trades ·
710 tonnes over 180 days). Our spec excludes that as a different product
(CLAUDE.md section 4). What remains — second grade in 10 kg net bags — is
**2 trades and 140 kg in the whole 180 days.**

**This is not the same shape as the 08-27 pack-mixing incident.** Back then the
top-grade average itself was contaminated (939 KRW vs. the true 711 KRW).
The top-grade numbers today are sound —

```
napa cabbage, top grade, our spec, last 8 trading days   611 – 923 KRW   09-08 was 647.6
```

### The other three checks are fine

```
within-day spread   worst average 1.7x (napa cabbage)      OK below 2.5x
series soundness    lowest 0.642 (napa cabbage · 150 days) OK at or above 0.60
target-anchor match mismatch 0 rows / 2,299 rows x 3 crops 0%
```

Napa cabbage autocorrelation 0.642 is effectively the same as yesterday (0.642)
and the day before (0.651). Nothing moved.

### To note (not fixed)

**This check has no minimum sample size and no minimum volume.** In a cell where
almost nothing trades — such as second-grade napa cabbage in 10 kg net bags —
**the rate jumps between 0%, 50% and 100% every time one trade arrives.** This
project has already learned that an alarm which cries every day stops being read
(CLAUDE.md section 9). Leaving the judgement to a person.

---

## 3. Drift: not an alert — **no combination has lost three weeks in a row**

`python agent/drift_agent.py` → verdict **Caution** (the alert rule is three weeks in a row)

**The numbers are the same as yesterday.** The 09-07 week has not been scored
yet, so the window did not move.

```
auc napa cabbage   lost 2 of the last 3 weeks   08-24 gap +3.6%p · 08-31 gap +1.6%p   (median of past 8 weeks +4.9%)
auc onion          lost 1 of the last 3 weeks   08-31 gap +1.9%p                      (median of past 8 weeks +10.9%)
whsl napa cabbage  lost 1 of the last 3 weeks   08-24 gap +10.6%p                     (median of past 8 weeks +58.8%)
the other 6 combinations are all as good as or better than the anchor
```

(gap = model error minus anchor error. A positive number is a week the model lost.)

**No retraining was started.** The batch's own retrain-verdict agent reached the
same conclusion (verdict Caution · no candidate).

> **What to look at tomorrow**: once the 09-07 week is scored for auction napa
> cabbage, check that week first. If it lost, that is three weeks in a row.
> (Same as written in yesterday's report.)

---

## 4. Purchasing hand-off table: today's base date is in — but **the shape changed**

Read directly from the forecast table (read only) —

```
base_dt 2026-09-09 (today)   162 rows = AUC 54 + RTL 54 + WHSL 54
target dates                 2026-09-10 – 2026-09-27
loaded at                    2026-09-09 09:08:10
rows with empty predicted    0
```

**The contract `daily[0] = as_of + 1` holds** (as_of 09-09, first target date 09-10).

### What changed since yesterday — nearby dates now carry model values, not the anchor

Number of rows sent out as the anchor (yesterday's price) instead of a model value:

```
              09-07   09-08   09-09 (today)
AUC  gated       6       6       0        <- gone
RTL  gated       6       6       0        <- gone
WHSL gated      22      22      26        <- unchanged (12 rows added at leads 1-2)
```

Radish (AUC) as an example:

```
09-08   target 1 and 2 days out   anchor 605 KRW passed through (gate on)
09-09   target 1 to 4 days out    model 524 KRW                 (gate off, quantile band)
```

### Cause — not a fault; an intended change made last night

`run_batch.py` carries a **new gate setting dated 2026-09-08.**

```python
GATE_LT = {"auc": 0, "whsl": 3, "rtl": 0}      # 0 means no gate
```

The comment records the evidence for the re-decision (measured on the 2026
production window).

```
auction     979 rows   error 10.06% -> 9.98% (+0.7%)   direction 58.5% -> 63.8% (+5.3%p)
retail      993 rows   error  3.99% -> 4.07% (-2.1%)   direction  5.8% -> 56.0% (+50.2%p)
wholesale   993 rows   error  3.93% -> 5.60% (-42.5%)  -> which is why only wholesale keeps its gate
```

The experiment outputs carry the same timestamps (2026-09-08 18:52-18:55).
**Today's batch is the first run under this setting.**

### Facts only (no judgement, nothing changed)

```
1. The change is not committed yet - git status shows " M run_batch.py"
   (run_batch.py was last committed 2026-09-07 16:46)
2. CLAUDE.md still says that --gate-lt 3 is the recommended production value
   (5.9) and that leads 1-2 are worse than the baseline (section 8). The
   document and what production actually does no longer agree
3. In the table the purchasing team receives, rows at leads 1-2 have changed
   character (is_gated=false, and for AUC band_method='quantile'). This check
   could not confirm whether they were told
```

---

## Side note · the ingest check the batch left behind (for reference only)

The ingest check raised two **Cautions**. Both were checked and neither affects
today's forecast.

```
auction rows on the latest day 248 (baseline 458 · 54%)
   -> the last 8 trading days run 197-273 rows. Only 09-03 had 497 rows, which
      appears to have pulled the baseline up. 248 is normal for recent days
   -> for our target spec (top grade) all three crops are present on every
      trading day from 09-01 to 09-08 (09-08: radish 642 t, napa cabbage 518 t,
      onion 373 t). There is no hole where the target goes empty, as on 09-03

weather rainfall missing over the last 7 days 83.2% (usually 54.1%)
   -> nothing was dug out. The cell is empty when it does not rain
```

---

## What I did today / did not do

```
did        ran the 3 agents, queried the raw auction data directly, read the
           hand-off table, reviewed the run_batch.py change, compared with
           yesterday's log
did not    0 files edited, 0 batch re-runs, 0 retraining, 0 database writes
```
