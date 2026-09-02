# Predicting Vegetable Prices
### Mid-term presentation — ML part · 2026-08-28

---

## 1. What we are trying to do

The company wants to make money by **storage trading**.

```
Buy cheap at auction  →  Keep it in a warehouse  →  Sell when the price rises
```

That plan only works if someone can answer one question:

> **"Will the price go up or down over the next three weeks?"**

**Our part is that question only.** We do not decide how much to buy, what the
warehouse costs, or how much rots. Other teams do that. We hand them a price curve.

### Why three weeks

Cabbage bought today keeps for a few weeks. So we predict **18 business days
ahead** — tomorrow, the day after, all the way out to day 18.

---

## 2. Why this is hard

Vegetable prices are not like phone prices. They move a lot, and fast.

```
Cabbage auction price, measured from our database
  average                777 won/kg
  cheapest days          around 300 won/kg
  most expensive days    over 2,000 won/kg
```

A typhoon can move the whole market in a month. That actually happened —
**Typhoon Hinnamnor, September 2022**: cabbage went from **1,237 won/kg in August
to 2,072 won/kg in September**, a 68% jump.

---

## 3. What we built

Four things.

| # | Thing | What it does |
|---|---|---|
| 1 | **Data pipeline** | Collects 5 kinds of data daily, cleans them, joins them |
| 2 | **Three models** | Auction price · Wholesale price · Retail price |
| 3 | **Daily robot** | Runs at 09:00 every morning with nobody watching |
| 4 | **Delivery table** | Other teams read our forecast straight from a database table |

### How much data (counted today, 2026-08-27)

| Source | Rows | Period |
|---|---|---|
| Auction prices, Garak market | **1,560,545** | 2017-01-02 ~ 2026-08-26 |
| Wholesale + retail prices | **1,044,591** | 2015-01-02 ~ 2026-08-26 |
| Weather, 95 stations | **401,753** | 2015 ~ 2026 |
| Daily arrivals (how much came in) | 18,280 | 2014-12 ~ 2026-08-27 |
| **Training table (all of it joined)** | **198,829 rows · 56 columns** | 2,857 distinct dates |

One warning we keep repeating to ourselves:

> **198,829 rows is not 198,829 examples.** Each day gets copied into up to 54 rows
> (3 vegetables × 18 lead times). The real sample size is **2,857 days**.

Getting this wrong would make our dataset look 70 times bigger than it is.

---

## 4. Three prices, not one

A cabbage changes hands three times before it reaches you, and it has a different
price at each stop.

```
Farm ──[auction]──▶ Middleman ──[sells]──▶ Shop ──[retail]──▶ You
          ▲                       ▲                   ▲
       we BUY here          middle price         we SELL here
```

We predict **all three**, because the trading plan needs both ends of the chain:
buy at the auction price, sell at the retail price.

---

## 5. The idea that made it work

### The wrong way — predict the price

Our first models tried to guess "cabbage will be 850 won on September 10."

They failed in a sneaky way. The model **ignored how far ahead it was predicting.**
A 1-day-ahead guess and an 18-day-ahead guess came out nearly identical.

We could measure the failure:

```
How much the model cared about "how many days ahead"   1.5%   ← almost nothing
Accuracy at 1 day ahead                                −95%   ← terrible
```

The model had simply learned the **average price** and was repeating it.

### The right way — predict the change

Instead we predict **how much the price moves from yesterday.**

```
Learn      y = log( target price ÷ yesterday's price )
Predict    price = yesterday's price × e^(model output)
```

**Analogy.** Don't guess tomorrow's temperature from nothing. Start from today's
temperature and guess how much it will move. Much easier question — and you get
today's temperature for free.

This single change is the reason the models work at all.

---

## 6. How we grade ourselves — the part that matters most

Anyone can say "our model is good." We wrote rules so that we cannot fool ourselves.

### Rule 1 — You must beat the baseline

A **baseline** is a reference number you can produce with no computation at all. We use four:

```
① yesterday's price            ② average of the last 7 days
③ average of the last 14 days  ④ the price on the same date last year
```

If the model cannot beat these, the model is useless — just use the baseline and
save the electricity.

It works like a class average on a test. "60 points" alone tells you nothing;
you need the class average to judge it. The baseline is that class average.

### Rule 2 — Compare against the STRONGEST baseline

We learned this one the hard way.

> We once reported that our arrivals model was **+40% better than baseline.**
> We had only compared it against "yesterday's number." When we compared it to
> "the same week last year" — a much smarter baseline for a seasonal series —
> the honest figure was **+15.3%**. We had overstated by about 8×.

Every number in this document is now measured against the best of all four.

### Rule 3 — Two separate test years must agree

An input is only accepted if it helps in **two different test years**, and the
help must be larger than the random wobble between runs.

This rule has already killed ideas that looked good:

| Idea | Test year 2023 | Test year 2022 | Verdict |
|---|---|---|---|
| School calendar (school-lunch demand) | +0.0036 helps | −0.0017 hurts | **Rejected** |
| Economic indicators (M2, PPI) | hurts | hurts | **Rejected** |

The school-calendar idea would have been announced as **"+3.7% → +5.6%, big win"**
if we had looked at one year only.

### Rule 4 — Never write a number without its conditions

```
BAD    "Auction price accuracy 0.1702"
GOOD   "Auction WMAPE 0.1702 (cabbage/onion/radish · trained 2017–2022 ·
        validated 2023 · anchor transform · 5 seeds · 31 features)"
```

A number without conditions cannot be checked by anyone, including us.

---

## 7. Results

### 7.1 Real operation — 9 months of predictions, graded against reality

These are **not** laboratory numbers. We made these predictions in advance,
waited for the real price to arrive, then compared.

**2025-11-25 ~ 2026-08-26 · 76,614 graded predictions · gated rows excluded**
**Comparison: our model vs "yesterday's price"**

| Price type | Item | Our error | Baseline (yesterday) | Better by | Range hit rate |
|---|---|---|---|---|---|
| **Auction** | Cabbage | **21.11%** | 30.90% | **+31.7%** | 80.0% |
| **Auction** | Onion | **13.67%** | 17.31% | **+21.0%** | 69.7% |
| **Auction** | Radish | 21.68% | 21.53% | **−0.7%** | 80.4% |
| **Retail** | Cabbage | **7.75%** | 9.06% | **+14.5%** | 90.4% |
| **Retail** | Radish | **7.91%** | 9.00% | **+12.1%** | 86.3% |
| **Retail** | Onion | **7.46%** | 8.57% | **+13.0%** | 80.1% |
| Wholesale | Onion | 9.90% | 11.14% | +11.1% | 68.7% |
| Wholesale | Cabbage | 8.38% | 9.10% | +7.9% | 91.9% |
| Wholesale | Radish | 12.47% | 12.50% | +0.2% | 83.8% |

> **Condition:** the comparison here is against yesterday's price only, not
> against the strongest of the four baselines. The lab numbers in §7.2 use the
> strict rule.

**How to read "range hit rate."** We do not give only one number. We give a range,
like a weather forecast saying "70–80% chance of rain." We aim for the real price
to land inside our range **80% of the time.** The measured values are 69–92%, so
our ranges are roughly honest — not squeezed narrow to look confident.

**Retail is our strongest product: all three vegetables positive, all above +12%.**

### 7.2 Laboratory test - all three prices, after we fixed the target (see §8)

**Full re-measurement, 2026-08-28.** Trained from 2017 · 5 random seeds ·
lead-time gate on · **compared against the strongest of the four baselines**

| Price type | Test year 2023 | Test year 2022 | Seed wobble |
|---|---|---|---|
| **Auction** (what we pay) | **+5.6%** | **+15.0%** | ±0.0004 |
| **Wholesale** (middle) | **+14.8%** | **+9.3%** | ±0.0014 |
| **Retail** (what we sell) | **+16.1%** | **+9.1%** | ±0.0007 |

**All three prices are positive in both test years. First time ever.**

**Why "seed wobble" matters.** The model gives slightly different answers on each
run. That wobble is ±0.0004-0.0014, while the improvement is **tens of times
larger.** These numbers are not luck.

### Before the fix - auction price

| Item | Test year 2023 |
|---|---|
| Cabbage | **-7.8%** |
| Radish | +1.2% |
| Onion | **-7.7%** |

Two of three were **worse than doing nothing at all.**

### Per item - this is where the truth is

| Price | Test year | Cabbage | Radish | Onion |
|---|---|---|---|---|
| Auction | 2023 | +3.9% | +1.5% | +8.5% |
| Auction | 2022 | **+19.5%** | +15.2% | +8.9% |
| Wholesale | 2023 | +18.5% | +17.7% | +2.5% |
| Wholesale | 2022 | +13.4% | +10.0% | **-6.4%** |
| Retail | 2023 | **+22.0%** | +8.6% | +6.3% |
| Retail | 2022 | +11.4% | +9.4% | **-9.0%** |

**Do not read the combined number alone.** All three prices are positive overall,
but **onion is negative on the selling side (wholesale, retail) in 2022.**

2022 is the typhoon year. Onion is **easy to buy well (+8% in both years) and hard
to sell well during a supply shock.** See §10.

---

## 8. The biggest finding of this project

### Our answer key was wrong

For over a year we trained models against a target that was, in effect,
**random noise.** We found out on 2026-08-27 — yesterday.

### How we found it

It started as a small oddity nobody had ever asked about.

```
1. Purchase team asked us for a price range      → we checked our ranges
2. Cabbage's range was strangely wide (0.65)     → we looked for the reason
3. One day's highest price was 19,900 won/kg     → 21× the average of 939
4. We called the source API directly
5. The source is per-transaction, and each transaction has a PACKAGE SIZE
6. We split by package size  →  one single day held 15 different products
```

That `19,900` had been in the database since 2015. **No check had ever looked at it.**

### What was actually wrong

The source gives one row per trade. Our collector was **averaging every trade of
the day together** — but different packages are different products.

**Cabbage, top grade, Garak market, one day (2026-08-03):**

| Package | won/kg | Volume |
|---|---|---|
| **Net bag 10kg** | **711** | **322,940 kg (79%)** |
| Box 8kg | 1,721 | 35,640 kg |
| Box 4kg | 5,841 | 3,744 kg |
| Box 1kg | **11,224** | 2,278 kg |
| …11 more package types | | |
| **Weighted average = our old target** | **939** | 410,960 kg |

Small retail packs cost **15× more per kilogram** than bulk net bags. On top of
that, entirely different vegetables were filed under "cabbage" — wrapping cabbage,
imported cabbage, salad cabbage.

**Analogy.** Imagine averaging a 1-litre carton of milk (1,000 won) with a 200 ml
carton (800 won) and calling the result "the price of milk per litre." The small
carton is 4,000 won per litre. The average is a number, but it is not the price of
anything you can actually buy.

### Why this made prediction impossible

The clearest measurement is how much yesterday's price tells you about today's.

```
Mixed target      0.085     ← yesterday tells you almost NOTHING. Near-random
Fixed spec        0.901     ← yesterday tells you a great deal
```

**0.085 means the series was essentially unpredictable.** No feature we added could
ever have helped, because there was nothing there to find. We had spent a year
tuning a model to predict a coin flip.

Other symptoms — all visible for years:

| Check | Mixed | Fixed |
|---|---|---|
| Yesterday → today link | 0.085 | **0.901** |
| Spread of the series | 0.919 | 0.354 |
| Highest ÷ lowest within one day | **132.7×** | 9.7× |
| Days when top grade was CHEAPER than second grade | **737 of 815** | resolved |

Top grade being cheaper than second grade on **90% of days** is impossible in a
real market. It was a loud symptom, and nobody had checked it.

### We got the fix wrong twice

**Attempt 1 — "same weight means same product."** We allowed any package shape at
10kg. Wrong:

```
Cabbage at 10kg:  net bag 824 · pallet 943 · box 1,115 · plastic bag 3,071 won/kg
```

A 10kg plastic bag costs **3.7×** a 10kg net bag. Same weight, different product.

**Attempt 2 — one package list for all vegetables.** We allowed
`net bag / box / pallet` everywhere. Cabbage's score **fell 0.928 → 0.513**,
because `box` — which radish needs — is a small-pack format for cabbage.

**Package format has to be decided per vegetable.** Final specification:

| Item | Package | Weight | Yesterday→today link | Share of volume |
|---|---|---|---|---|
| Cabbage | net bag, pallet | 10kg | 0.901 | 94% |
| Radish | box, pallet | 18kg (to 2017) then 20kg | 0.928 | 76% |
| Onion | net bag, pallet | 15kg | 0.979 | 71% |

Radish is split by year because the industry packaging standard changed in 2018.
Ignoring that split drops its score to 0.373.

### Then we rebuilt everything

```
Re-collected      1,560,545 rows  ·  about 12,000 API calls
Backed up first   781,405 rows · 153 MB
Migration ran     98 seconds
```

**One warning about the headline number.** Our raw error score went
**0.1801 → 0.2127**, which looks worse. It is not. **The target changed.** The old
target's average was inflated to 939 won by tiny retail packs; the real bulk market
price is 777 won, so the same percentage error divides by a smaller number. The
baseline got harder too (0.2557 → 0.3078) — and our model still beat it.

> **Never compare error scores across a change of target.** Compare the gap to the
> baseline instead.

---

## 9. What runs by itself

Every morning at 09:00, with nobody at the keyboard:

```
1  collect auction prices        6  rebuild the training table
2  collect wholesale/retail      7  run the three models
3  collect weather               8  load + grade past predictions
4  collect arrivals (20–25 min)  9  push to the delivery table
5  collect economic data
```

A full run takes about **13 minutes**. Last night it wrote **54 rows per price
type** (3 vegetables × 18 days), covering 2026-08-27 through 2026-09-13.

### One thing we had to learn the hard way

Windows Task Scheduler has a setting called **"restart on failure."** It does
**not** fire when a program exits with an error code — it only fires when the
program fails to *start*. We had it set to retry twice; a real failure on
2026-08-27 at 09:00 retried **zero** times.

So we wrote our own retry layer. It retries only errors that are clearly temporary
(timeout, connection reset, 5xx). It never retries the rebuild step, because that
step erases the table before it begins — a blind retry there would destroy data.

---

## 10. What we know is still weak

We would rather say these out loud than have someone find them later.

| # | Weakness | Number |
|---|---|---|
| 1 | **Onion sells badly during a supply shock** | Wholesale −6.4%, retail −9.0% (2022) |
| 2 | **Large spread across items and years** | Cabbage auction +3.9% to +19.5% |
| 3 | **Radish auction is still weak** | −0.7% live, +1.5% lab |
| 4 | **Garlic is excluded entirely** | 11% of its auction data missing; two garlic types not separated |
| 5 | **Grade disagreement with the purchase team** | They asked for grade 2; 98% of Garak volume is grade 1 |
| 6 | **The final test period is still sealed** | 2024-2025 will be opened once, at the very end |
| 7 | **"Start training from 2017" needs re-checking** | That decision was made on the broken target |

### On #1 and #2 - we found out why

Cabbage does very well in test year 2022 and only slightly beats the baseline in
2023. We investigated: **2022 is the only test year with a typhoon in it.**

That reframes everything. The model earns its keep during supply shocks and adds
little in a calm year. It also means two ideas we rejected earlier may have been
rejected for the wrong reason — they failed *in the shock year*, which may mean
"useless during a shock," not "useless."

**When two test years disagree, look up what happened that year first.**

### On #4 — a number we could not place

The purchase team quoted "cabbage 1,850 vs 1,650" as their measurement. Our cabbage
price is 610 won/kg — a completely different scale. We went looking, and found
those exact numbers **hard-coded in the purchase team's mock test file**, with a
comment saying they were copied from a specification document.

**They were comparing against example data, not real data.** Worth confirming before
either side changes anything.

---

## 11. What we do next

| Priority | Task |
|---|---|
| 1 | Re-measure wholesale and retail — the auction fix changed their inputs |
| 2 | Re-collect 2015–2016 and re-decide "start training from 2017" |
| 3 | Build automatic data-quality alarms from what §8 taught us |
| 4 | Connect the trigger so the purchase agent starts the moment we finish |
| 5 | Re-include garlic once the two garlic types can be separated |

### The three alarms we are adding

Every one of these would have caught the broken target years ago.

```
Grade order     is top grade ≥ second grade?         → was violated 90% of days
Daily spread    is highest ÷ lowest over 10×?        → it was 132×
Series health   is the yesterday→today link < 0.3?   → it was 0.085
```

The point is not that these three checks are special. The point is that **every
check we had was written to test something we already suspected.** Nothing was
watching the things we assumed were fine.

---

## 12. The one lesson

> **Do not walk past a strange number.**

`19,900 won/kg` was in our database from the very first day. It appeared in every
export. No validation query ever looked at it.

The finding did not come from a better model, a bigger dataset, or a smarter
algorithm. It came from asking why one price range was wider than the others.

---

### Summary in five lines

1. We predict three prices, 18 days ahead, for three vegetables.
2. **All three prices are positive in both test years - first time ever** (auction +5.6/+15.0 - wholesale +14.8/+9.3 - retail +16.1/+9.1).
3. Auction was broken and is now fixed. Before the fix it was -7.8% for cabbage and -7.7% for onion - worse than doing nothing.
4. It runs by itself every morning and delivers into a table the other teams read.
5. The biggest win this term was not a model improvement — it was **discovering the target itself was wrong.**
