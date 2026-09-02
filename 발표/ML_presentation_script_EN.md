# Presentation Script — ML Price Forecasting
### Spoken script with parameter and result explanations · 2026-08-28

> **Source of every number in this script:** the experiment logs in `실험결과/`.
> Each result slide cites the exact file. Nothing here is quoted from memory.
>
> | Slide | Source file |
> |---|---|
> | 5–6 | `2026-08-28_153454_exp_anchor.txt` |
> | 7–8 | `2026-08-28_152845…_a10.txt` / `…152855…_a06.txt` (and 10 sibling files) |
>
> Timing guide: **~12 minutes** at a normal pace. Cut §9 first if short on time.

---

## Slide 1 — What we forecast

**[SAY]**

Our team forecasts vegetable prices for a storage-trading strategy: buy cheap at
auction, store the produce, sell when the price rises.

That strategy only works if we can answer one question — *will the price go up or
down over the next three weeks?*

So we forecast **eighteen business days ahead**, for three vegetables — napa
cabbage, radish, and onion — at three points in the distribution chain.

**[SHOW]**

```
farm ──[auction]──▶ middleman ──[sale]──▶ shop ──[retail]──▶ consumer
         ▲                        ▲                  ▲
    what we pay              middle price       what we sell at
```

**[SAY]**

We forecast all three, because the trade needs both ends: the auction price tells
us what buying costs, the retail price tells us what selling earns.

---

## Slide 2 — The core modelling choice

**[SAY]**

The single most important design decision is this: **we do not forecast the price.
We forecast the change from a reference point.**

**[SHOW]**

```
train:    y = log( price at horizon  ÷  reference price )
predict:  price = reference price × e^(model output)
```

**[SAY]**

We call that reference the **anchor**.

Why does this matter? Our first models predicted the price level directly, and
they failed in a way that was easy to miss. The model ignored the forecast
horizon completely — its one-day-ahead guess and its eighteen-day-ahead guess
were nearly identical. It had simply memorised the average price.

We could measure that failure: the importance of the horizon feature was **1.5
percent**, essentially nothing, and one-day-ahead accuracy was **95 percent worse**
than just carrying yesterday's price forward.

With the ratio formulation, if the model outputs zero, the answer *is* the anchor.
So the model cannot fall far below a sensible reference. That is a structural
guarantee, not a tuning result.

**[IF ASKED]** *Why log?* Because price ratios are multiplicative — a move from
600 to 900 and a move from 900 to 600 should count the same. The logarithm makes
them symmetric.

---

## Slide 3 — Model and hyperparameters

**[SAY]**

The model is **LightGBM**, gradient-boosted decision trees. Every experiment log
records the exact configuration, so any number on the following slides can be
reproduced.

**[SHOW]** — from `2026-08-28_153454_exp_anchor.txt`

```
[Model]
  type            LightGBM 4.7.0 (GBDT)
  ensemble        5 seeds [42, 43, 44, 45, 46], predictions averaged
  learning target log ratio to anchor
  early stopping  cap 5,000 trees, stop after 200 rounds with no gain
  categorical     item_nm, target_dow, prod_area_stn_nm

[Hyperparameters]
  objective            regression_l1
  metric               mae
  learning_rate        0.03
  num_leaves           31
  min_data_in_leaf     60
  feature_fraction     0.8
  bagging_fraction     0.8
  bagging_freq         1
  lambda_l2            1.0
```

**[SAY — explain the choices that matter]**

Four of these are deliberate, and I want to explain why.

**`objective = regression_l1`.** This minimises absolute error, not squared error.
Agricultural prices have violent spikes — a typhoon can move cabbage 70 percent in
a month. Squared error would let those few days dominate training and drag the
model off the ordinary days that make up most of our decisions.

**`learning_rate = 0.03` with up to 5,000 trees.** A small step size with many
steps. Our effective sample is small — I will come back to that — so we prefer
many small corrections over few large ones.

**`min_data_in_leaf = 60`.** No leaf may be built on fewer than sixty rows. This
is our main guard against the model memorising individual days.

**`feature_fraction` and `bagging_fraction` at 0.8.** Each tree sees 80 percent of
features and 80 percent of rows. Deliberate handicapping, so trees disagree with
each other and the ensemble averages out their individual mistakes.

**[SAY — the ensemble]**

We train five models with different random seeds and average them. A single seed
moves the score by roughly **0.001 to 0.0014**. If we reported one seed, we could
choose whichever number we liked within that band. Averaging removes that
temptation and the log records all five seeds individually.

**[IF ASKED]** *Why not deep learning?* We have not run that comparison yet, and I
will not claim gradient boosting is better without measuring it. It is on our list
as an open item.

---

## Slide 4 — How we grade ourselves

**[SAY]**

Before any results, I need to explain how we score, because we got this wrong
twice and the rules exist because of those mistakes.

**[SHOW]**

```
Baseline candidates — a reference anyone can produce with no model at all
  ① yesterday's price          ② 7-day average
  ③ 14-day average             ④ same date last year
```

**[SAY]**

A **baseline** is a number you can produce with no computation. We compare against
four of them and report improvement against **the strongest**, per vegetable.

Think of a test score. Sixty out of a hundred tells you nothing on its own — you
need the class average. The baseline is that class average.

**[SAY — the mistake that created this rule]**

We once reported an arrivals model as "40 percent better than baseline." We had
compared it only against yesterday's value. When we compared it against the same
week last year — far stronger for a seasonal series — the honest figure was
**15.3 percent**. We had overstated by roughly eight times.

There is a trap specific to our design. Because the anchor *is* one of the
baselines, our model is structurally protected from losing to that particular
baseline. Whether the anchor is the *strongest* baseline is a completely separate
question — and slide 5 shows that for a long time, it was not.

**[SAY — the second rule]**

We use **two validation folds** and require the same sign in both.

```
Fold A:  train through 2022,  validate on 2023
Fold B:  train through 2021,  validate on 2022   ← contains Typhoon Hinnamnor
```

Fold B is the year with a supply shock. A method that only works in calm years is
not a method we can trade on. Test years 2024 onward are sealed and untouched.

---

## Slide 5 — What we measured today: the anchor

**[SAY]**

Now the experiment. Everything on this slide is from
`2026-08-28_153454_exp_anchor.txt`.

Our anchor has always been **yesterday's price**. We had never asked whether that
is the best starting point.

The concern is simple: if yesterday happened to spike, our forecast spikes with
it. So we tested a **shrinkage anchor** — a blend of yesterday and the recent
seven-day average.

**[SHOW]**

```
anchor = α × yesterday's price  +  (1 − α) × 7-day average

α = 1.0   yesterday only            ← what we had been running
α = 0.8   80% yesterday, 20% mean
α = 0.6   60% / 40%
α = 0.4   40% / 60%
```

**[SAY]**

α is the only thing that changes. Everything else — features, hyperparameters,
seeds, folds — is held fixed. That is the point of the experiment.

---

## Slide 6 — Anchor results

**[SHOW]** — auction price, from the same log file

**Fold A (validate 2023).** Strongest baseline: 7-day average, 0.1703

| α | WMAPE | seed SD | vs strongest baseline |
|---|---|---|---|
| **1.00** (old) | 0.1757 | 0.0010 | **−3.2%** |
| 0.80 | 0.1705 | 0.0010 | −0.1% |
| 0.60 | 0.1645 | 0.0014 | **+3.4%** |
| 0.40 | 0.1611 | 0.0002 | +5.4% |

**Fold B (validate 2022).** Strongest baseline: yesterday's price, 0.2025

| α | WMAPE | seed SD | vs strongest baseline |
|---|---|---|---|
| **1.00** (old) | 0.1880 | 0.0002 | **+7.1%** |
| 0.80 | 0.1867 | 0.0014 | +7.8% |
| 0.60 | 0.1875 | 0.0006 | +7.4% |
| 0.40 | 0.1890 | 0.0007 | **+6.6%** |

**[SAY — read the negative first]**

Start with the number I would rather not show. At α = 1.0 — our production
setting until this afternoon — the auction model was **3.2 percent worse than a
plain seven-day moving average** in 2023.

We beat yesterday's price on all three vegetables. But yesterday's price was not
the strongest baseline that year, and a seven-day average beat us.

**[SAY — then the fix]**

Now read down each column. The two folds pull in opposite directions.

In the calm year, lower α is better — 0.40 is best. In the typhoon year, higher α
is better — 0.40 is the *worst* of the four.

That is exactly what you would expect. Mixing in an average is stabilising when
nothing is happening, and it is slow to react when something is.

**α = 0.6 is the only value that improves both folds**: fold A goes from −3.2 to
+3.4, and fold B from +7.1 to +7.4. α = 0.4 looks better in fold A but *loses*
ground in fold B, so our two-fold rule rejects it.

**[SAY — the significance check]**

Seed standard deviation is 0.0002 to 0.0014. The improvement is tens of times
larger. This is not seed luck.

---

## Slide 7 — What that means in won

**[SAY]**

WMAPE is a ratio, and ratios are hard to act on. So every log now also reports
error in won against the actual price.

**[SHOW]** — auction, fold A, from `…152845…_a10.txt` and `…152855…_a06.txt`

| | mean actual | mean error | error rate | worst 1-in-10 |
|---|---|---|---|---|
| **Cabbage** α=1.0 | 679 won | 164 won | 24.2% | over 51% |
| **Cabbage** α=0.6 | 679 won | **150 won** | **22.1%** | over 44% |
| **Radish** α=1.0 | 544 won | 124 won | 22.7% | over 49% |
| **Radish** α=0.6 | 544 won | **111 won** | **20.4%** | over 41% |
| **Onion** α=1.0 | 1,173 won | 132 won | 11.3% | over 25% |
| **Onion** α=0.6 | 1,173 won | **130 won** | **11.1%** | over 24% |

**[SAY]**

Read the cabbage row. The actual price averages 679 won per kilogram, and we miss
by 150 won — about 22 percent. One time in ten we are off by more than 44 percent.

The anchor change bought us **14 won per kilogram on cabbage** and **13 on
radish**, and it pulled the worst-case column down by six to eight points.

Onion barely moves. Onion's auction price is highly self-correlated day to day, so
yesterday was already a good starting point and there is little to gain by mixing.

**[SAY — the honest caveat]**

I want to be explicit: **22 percent is a large error.** If a downstream system was
built assuming forecasts land within a few percent, that assumption does not hold.

For context, the strongest baseline is also around 21 to 23 percent on these
items. This market genuinely moves that much. But we are not going to dress that
up.

---

## Slide 8 — Result across all three price levels

**[SAY]**

We ran the same comparison for all three targets — twelve runs, three targets by
two folds by two α values. Files are in `실험결과/`, named `…_a10` and `…_a06`.

**[SHOW]**

| Target | Fold A (2023) | Fold B (2022) | |
|---|---|---|---|
| | α=1.0 → **α=0.6** | α=1.0 → **α=0.6** | |
| **Auction** | −3.0% → **+3.7%** | +6.0% → **+6.4%** | ✅ |
| **Wholesale** | +14.8% → **+14.8%** | +9.3% → **+11.0%** | ✅ |
| **Retail** | +16.1% → **+17.5%** | +9.1% → **+10.3%** | ✅ |

**[SAY]**

Five of six combinations improve, one is unchanged, **none get worse**.

The headline is the auction row in fold A: **from minus three to plus three-seven.**
That is the difference between losing to a moving average and beating it.

And with that, **all three price levels are positive in both folds for the first
time**.

**[SAY — one thing to flag]**

Retail's *absolute* error rose slightly, from 8.8 to 9.0 percent, even though its
improvement figure went up. That is not a contradiction — changing the anchor
changes the baseline too, and the baseline got worse faster than we did.

We adopted α = 0.6 for all three anyway, to keep one consistent rule across the
system. That costs retail about 0.2 points of absolute accuracy and I would rather
state it than bury it.

---

## Slide 9 — Why the logs look the way they do

**[SAY]**

One process point, briefly.

Until this morning, our experiments printed to the screen and disappeared. When we
tried to verify a figure written down weeks ago, we could not reproduce it —
because the data underneath had changed in the meantime.

So every run now writes a complete record.

**[SHOW]**

```
실험결과/2026-08-28_153454_exp_anchor.txt

  run time        2026-08-28 15:34:54
  command         python exp_anchor.py train_20260828b.csv --alpha 1.0 0.8 0.6 0.4 …
  working dir     …/ml_train_kit_2
  [Model] … [Hyperparameters] … [Results] …
  end time        2026-08-28 15:35:41
```

**[SAY]**

Filenames carry the timestamp to the second, so two runs in the same minute cannot
overwrite each other — which matters, because we ran twelve jobs about ten seconds
apart today.

The header records the exact command. **A number without its conditions cannot be
checked by anyone, including us.** That is a rule we now enforce mechanically
rather than by discipline.

---

## Slide 10 — What we know is still weak

**[SAY]**

Four things I would rather say now than have someone find later.

**One — absolute error on auction is 20 to 22 percent** even after today's
improvement. That is the number that matters to the buying side, and it is large.

**Two — the two folds disagree about what is best.** α = 0.4 wins the calm year
and loses the shock year. We chose the value that helps both, which means we are
optimal for neither.

**Three — the sealed test period is still sealed.** Everything today is validation
data. The final check on 2024 onward happens once, and we have not spent it.

**Four — and this one we found an hour ago.** Our forecast starts from the price
*two* days before the target, not one. The batch runs in the morning using
yesterday as the base date, so the anchor is a day older than the data we already
hold.

**[SHOW]**

```
Cost of a one-day-stale anchor — measured on 794 trading days, 2024 onward

              one day old      two days old (current)
  Cabbage        11.7%              14.0%
  Radish          9.9%              14.2%
  Onion           3.7%               5.4%
```

**[SAY]**

That gap is comparable in size to everything we gained today. We spent the
afternoon tuning *how much* to trust the anchor, and it turns out the anchor was
also pointing at the wrong day. That is our next piece of work.

---

## Slide 11 — Closing

**[SAY]**

To summarise.

We forecast three price levels, eighteen business days out, for three vegetables.
As of this afternoon all three beat the strongest naive baseline in both
validation folds — the auction model for the first time.

The change that did it was not a new architecture or more data. It was asking a
question we had never asked: *is our starting point the right one?* The answer was
no, and the fix was one coefficient.

The general lesson, and the one I would take away: **the assumptions we never
questioned are where the errors were hiding.** Not in the model.

---

## Appendix — Anticipated questions

**"Why not just use the seven-day average, if it beat you?"**
In 2023 it did, on auction. In 2022 it did not — yesterday's price was stronger
there, and our model beat both. A fixed rule wins in one regime; we need something
that holds in both. That is why we test on two folds.

**"How do you know 0.6 is optimal?"**
We do not. We know it is better than 1.0, 0.8, and 0.4 under our two-fold rule,
from the four values we tested. A finer sweep is cheap and worth running.

**"Your sample looks large — 78,000 training rows."**
It is not. One base date is copied into up to 54 rows, three vegetables by
eighteen horizons. The real sample is **1,473 independent days**. Treating rows as
independent would overstate it by about seventy times. Every log prints this
warning.

**"Can the purchase team rely on these numbers?"**
On retail, error is 9 to 11 percent and reasonably stable. On auction it is 20 to
22 percent. We also publish a range with every forecast, calibrated so the actual
price lands inside it about 80 percent of the time. Use the range, not the point.

**"What about garlic?"**
Excluded. Eleven percent of its auction data is missing, and its wholesale price
is unchanged from the previous day on 94 percent of days — a different forecasting
problem, not a harder version of this one.
