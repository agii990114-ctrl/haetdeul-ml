# Price Forecasting — Complete Experiment Ledger

ML team (Haetdeul Nongsan) · written 2026-09-10 16:54:46 · covers 2026-08-18 → 2026-09-10

**What this document is.** Every experiment we ran on the price-forecasting
problem, in the order we ran it, with the conditions it was measured under and
the verdict. It records **rejections and mistakes as fully as adoptions** —
four of the five most consequential findings came from things that did not work.

**Related documents, so you know what this one is not:**

| Document | What it covers |
|---|---|
| `발표/ML_price_forecasting_paper_EN.md` | Method and results, written as a paper |
| `진행기록/development_progress_EN.md` | What we built, in what order |
| **this file** | **Every experiment, its question, and its verdict** |

**Reading rule.** A number without its conditions is not a result. Every figure
below carries the crops, the training window, the validation fold, and the seed
count it came from.

---

## 0. One page

```
Goal        Forecast three price series 1–18 business days ahead so the firm can
            buy cheap at auction, store, and sell high at retail.

Crops       Napa cabbage · radish · onion   (garlic excluded — §3.4)
Targets     auction (buy) · wholesale (middle) · retail (sell)
Model       LightGBM, objective=regression_l1, 5-seed ensemble, fixed iterations
Transform   y = log(target / anchor);  prediction = anchor × exp(model output)

Experiments run           42
Adopted                    9
Rejected                  20
Undecided (not proven)    13

The single largest finding was not a model change. It was that the target
variable itself had been wrong for the entire project (§4).
```

---

## 1. Timeline

```
08-18 ~ 08-21   First models. Three targets compared
08-24           Train-window curve · ablation · lead-time gate · 3-way split rule
08-25 ~ 08-26   Operational model chosen · batch pipeline · volume cascade rejected
08-27  ★★       Auction target found to be a mixture of 15 package specs
08-28           Shrink anchor introduced (α)
08-31  ★        Scoring code found to be scoring 74% of rows against the wrong product
09-01           Test window opened once · quantile bands · boosting comparison · MLP
09-02           LLM forecasting trial (5 runs)
09-03  ★        Nine backlog items adjudicated in one day. Fold C rule added
09-04           Per-crop model split rejected on live data · wholesale series diagnosed
09-07 ~ 09-09   Lead-0 added · lead-time gates turned off · retraining automated
09-10           Retrain threshold re-measured (3 weeks → 1 week) · TFT/LSTM/GRU tested and rejected
```

---

## 2. The evaluation protocol — built before the experiments, revised three times

Everything below depends on how we decided what counts as a result. That
protocol changed three times, each time because it let something through.

### 2.1 Baselines: strongest-of-many, not the anchor alone

We compare against the **best** of nine candidates: yesterday's value, values
from 3 and 7 days back, 7- and 14-day averages, the same period last year, and
four shrink-anchor settings.

★ **Why this matters.** The anchor-ratio transform makes the anchor a baseline
*by definition* — a model output of zero returns the anchor unchanged. Comparing
only against the anchor makes the improvement look larger than it is.

> **How we learned it.** We reported a volume model at **+40%** against
> yesterday's value alone. Against the same-period-last-year baseline — far
> stronger for a seasonal series — it was **+15%** (2026-08-26).

### 2.2 Two-fold sign agreement (2026-08-24)

Narrowing validation to 2023 alone made ablation verdicts flip by year. The
`auction` feature group was **remove** on fold A and **keep** on fold B, for all
three targets.

```
Rule   Adopt or remove a feature only when both folds agree in sign
       and the sum exceeds 2 × the seed standard deviation.
       Folds: A = validate 2023, B = validate 2022. Ten seeds.
```

### 2.3 Three additions to the rule (2026-09-01 and 09-03)

**① A verdict expires when its conditions change.**

Ablation round 2 ran on 08-24 and concluded "no feature changes." Within three
days the target was re-specified (08-27) and the anchor changed (08-28). At the
time of that verdict, cabbage auction price had autocorrelation 0.085 — **it was
effectively random**, so "no change" may only have meant "nobody can predict
noise." Re-run under operating conditions, `weather` moved O → undecided and
`auction` moved X → undecided.

**② Do not decide on a lumped group. Split it.**

Removing the whole `calendar` group (6 features) was negative on both folds, so
it read as a removal candidate. Split apart, almost all of it was one feature,
and that one only appeared on fold B.

```
Lumped   A −0.0009 · B −0.0062   same sign → removal candidate
Split    A +0.0004 · B −0.0056   signs disagree → undecided
```

**Several small positives were buried under one large negative.**

**③ Anything going to production must be checked on fold C.**

On 2026-09-03, **two candidates that passed the two-fold rule both reversed on
fold C.**

```
M-06 share    A +0.0003 · B +0.0029 · C −0.0006    concentrated in fold B
M-15 mix_yr   A +0.0101 · B +0.0073 · C −0.0166    both positive, still reversed
Holiday feat. A +0.0025 · B +0.0140 · C +0.0044    ★ passed (the only one)
```

`mix_yr` is the alarming one — A and B agreed **and it reproduced on a disjoint
seed set**, and fold C was more negative than both were positive.

### 2.4 Reproducibility does not catch a wrong setup

The same day, `auc_prc_spread_lag1` reproduced across two disjoint seed sets and
was still void: the experiment harness was training on **different data than
production** (24% garlic). **Reproduction tells you it was not chance. It does
not tell you that you measured the right thing.**

### 2.5 Why fold B kept behaving differently — resolved

Fold B produced the odd sign four separate times. Investigating the fourth case:
**fold B validates on 2022, the only year containing a supply shock** (Typhoon
Hinnamnor, 2022-09-06; cabbage auction price 1,237 → 2,072 won).

**Fold B is not a broken fold. It is the only fold with a shock in it.** So the
earlier rejections may have meant "useless during a shock," not "useless."

---

## 3. Data and scope decisions

### 3.1 Training start: 2017 — **adopted**

Measured by learning curve. **Cutting data improved performance.**

| Start | Base dates | Improvement | Seed σ |
|---|---|---|---|
| 2015 | 1,968 | +5.9% | 0.0014 |
| 2016 | 1,721 | +6.6% | **0.0029** |
| **2017** | 1,475 | **+6.8%** | **0.0007** |

Reproduced independently on auction and retail. The 2015–2016 market structure
differs (cabbage retail 2,620 → 3,982 won, +52% year over year).

### 3.2 Economic variables removed — **adopted**

Ablation loss was negative for all three targets.

| Target | With | Without |
|---|---|---|
| Auction | +6.8% | **+8.7%** |
| Wholesale | +6.1% | +7.2% |
| Retail | +12.7% | **+15.3%** |

`m2_growth_rt`, `epu_idx`, `ppi_idx` update monthly or quarterly, so a daily
model sees the same value repeated for a month and **uses it as a time index**.
After removal, `best_iter` rose from 33–51 to 102–140 — the economic variables
had been triggering early stopping.

> Prior work (Yoon et al., 2024) reports 1–4% RMSE improvement from these
> variables. Our result is the opposite; the horizon (1 day vs 1–18) and model
> structure differ.

### 3.3 Producing-region weather removed **from retail only** — **adopted**

```
Retail with weather      +12.7%
Retail without weather   +17.1%      (7 seeds)
```

Retail has a thick distribution margin that buffers field conditions; consumer
demand dominates, and `holiday_remain_d` (importance rank 2, 11.2%) carries it.

★ **Weather contributes on auction and wholesale.** The same feature has
opposite value depending on the target — that was this experiment's finding.

### 3.4 Garlic excluded — **adopted**

- Unpeeled/peeled distinction unresolved
- Wholesale price **identical to the previous day on 94% of days** — a different
  problem entirely
- Auction price 11% missing (other crops: 1%)
- No Seoul retail data

Kept in the table; `--items` can re-include it at any time.

### 3.5 Retail restricted to Seoul — **adopted**

The national average changes its own basis mid-series: surveyed outlets went
44 → 59 in 2023, so **the training and validation windows aggregate differently**.
Wholesale is Garak market, so retail must be the same region.

### 3.6 KREI planted-area excluded — **adopted**

75% missing overall; by crop, 100% missing for cabbage/radish/garlic and 1.4%
for onion. It becomes **"a feature that only exists for onion"** — a crop
identifier in disguise.

---

## 4. ★★ The largest finding: the target was wrong (2026-08-27)

### 4.1 What was wrong

The source API returns **one row per transaction**, and price varies by package
spec. The collector grouped by (date, market, crop, grade) and **averaged
different products together.**

One day of Garak cabbage, top grade, 2026-08-03 contained **15 specs**:

```
Mesh bag   10 kg      710.8 won/kg    volume 78.6%
Pallet     10 kg      870.0 won/kg    volume  5.9%
Box         8 kg    1,721.2 won/kg    volume  8.7%
Box         1 kg   11,223.7 won/kg    volume  0.6%   ← retail packaging
[weighted mean of all 15]  938.5 won/kg              ← our target at the time
[correct: mesh + pallet, 10 kg]  721.9 won/kg
```

### 4.2 What it did to the series

| Metric | Mixed | Spec-fixed |
|---|---|---|
| Cabbage auction **ACF(1)** | **0.085** | **0.795** |
| Coefficient of variation | 0.919 | 0.354 |
| Intraday min/max ratio | 132.7× | 9.7× |
| Grade inversions (top < second) | 737 of 815 days | resolved |

**ACF(1) = 0.085 is white noise.** We were training on an unpredictable target;
no feature could have helped. Radish and onion have homogeneous packaging and
were barely affected (radish 0.788 → 0.822, onion 0.974 → 0.975).

### 4.3 Two wrong repairs before the right one

**First wrong repair — weight only, packaging open.** Reasoning: "same weight,
same product." Measured over five years, false:

```
Within 10 kg cabbage:  mesh 824 · pallet 943 · box 1,115 · plastic bag 3,071 won
ACF(1):                all 10 kg 0.484  →  mesh only 0.908
```

**A 10 kg plastic bag is 3.7× a 10 kg mesh bag.**

**Second wrong repair — one shared packaging list.** Adding "box" for cabbage
mixed 10 kg box (1,115) into mesh (824) and dropped ACF from 0.928 to 0.513.
**We built it that way and reverted it.** Packaging lists are now **per crop**.

### 4.4 A second defect it exposed

**The scoring code was not applying the spec filter** (found 2026-08-31). The
target was fixed on 08-27; scoring was not. **25,866 of 34,905 rows (74%) were
scored against a different product's price.** Worst case: radish 2026-01-09,
true 521 won, scored as 2,545.

★ **Every auction-price score reported before 2026-08-31 is void.**

### 4.5 And a third

**Baseline candidates were misaligned with the target.** Auction was being
evaluated against a wholesale price column — different magnitude, so the
baseline always lost, and "the anchor is the strongest baseline" became
**structurally true by accident.**

### 4.6 Subclass mixing — investigated, closed as not a risk (2026-09-03)

Cabbage rows also contain wrapped cabbage, imported cabbage, and salad cabbage.
Once `subclass_name` was collected for 2017–2026, we filtered and measured:

| Crop | Current ACF(1) | After subclass filter | Volume removed |
|---|---|---|---|
| Cabbage | 0.928 | 0.928 | 1.1% |
| Radish | 0.940 | 0.940 | 1.3% |
| Onion | 0.987 | 0.988 | **22.2%** |

**Removing 22% of onion volume changed nothing.** The outlier subclasses are
tiny by volume and the weighted mean absorbs them. The spec incident was
different because **both the 1 kg pack and the 10 kg mesh had large volume.**

---

## 5. Model and transform experiments

### 5.1 Anchor-ratio transform — **adopted** (foundational)

```
Training     y = log(target / anchor)
Prediction   forecast = anchor × exp(model output)      ← inverse is mandatory
```

Training on absolute price makes the model ignore lead time and learn the mean
price instead. Measured: `lead_biz_d` importance 1.5%, LT1 performance −95%.

★ **Omitting the inverse transform stores the log ratio (values like 0.049) as a
price.** Check this in any new batch code.

### 5.2 Shrink anchor (α) — **adopted** (2026-08-28)

```
anchor = α × lag1 + (1 − α) × 7-day mean
α:  auction 0.4 · wholesale 0.8 · retail 1.0
```

Auction moves 13.97% day over day; starting from yesterday alone carries that
day's noise into all 18 horizons.

### 5.3 Anchor selection [M-15] — **current is best** (2026-09-03)

Six alternative anchors were compared. **None beat the current one.** Optimal λ
moved with training length (0.2 at 4 years, 0.4 at 6), and at the production
7 years λ=1 (unchanged) beat the anchor by +12.7%.

★ This experiment is where **fold C was breached twice** (§2.3), which mattered
more than the anchor result itself.

### 5.4 Lead-time gate — **adopted then removed**

**Adopted 2026-08-24.** `LT<3` returns the anchor instead of the model. All
6 combinations (3 targets × 2 folds) improved or held (+0.0 to +0.8 pp); k≥5
became harmful.

**Re-adjudicated as [M-14] on 2026-09-03 and found unanswerable by folds** —
three methods (3-fold, live log, sealed holdout) disagreed with each other.
Cause in §8.1.

**Removed 2026-09-09.** `GATE_LT = {auc: 0, whsl: 3, rtl: 0}`. Purchase needed
same-night auction values, and lead 0 = the base date itself.

★ **Measured effect on the delivered upper bound, isolating the market**
(same base date, two sources):

| Crop | Gate effect | Market move | Net |
|---|---|---|---|
| Cabbage | **+21.5%** | −12.2% | +6.6% |
| Radish | **+15.9%** | −3.4% | +11.9% |
| Onion | +3.6% | −0.1% | +3.5% |

The net column reproduces what the purchase team measured independently.

### 5.5 Volatility gate — **rejected** (2026-08-24)

"Fall back to the baseline when volatility is low." The low-volatility quantile
improved in 2023 and worsened in 2022 — **opposite by fold.** The "loses money
in quiet years" pattern seen in testing is not explained by volatility.

### 5.6 Quantile regression for prediction intervals — **adopted, auction and wholesale only** (2026-09-01, live 09-03)

```
Before   LightGBM(regression_l1) → point   +  fixed lookup table → ± width
After    LightGBM(objective=quantile, α = q / 0.5 / 1−q) → lower, mid, upper
```

★ **The fixed table could not read the situation at all.** Measured within a
crop, the ratio of a volatile day's width to a quiet day's width was **exactly
1.00** — width was determined by (crop × lead time) only, leaving no slot for
that day's conditions.

> The pooled figure looks like 1.15–1.52. That is an artifact: radish has wide
> bands (111%) and high volatility, onion narrow (69%) and low, so a **crop
> difference masquerades as conditionality.**

| Target | Crop | Trained q | Coverage A / B | Width (table → quantile) | Conditionality |
|---|---|---|---|---|---|
| Auction | Cabbage | q03 | 84.2 / 80.4% | 93% → 75 / 76% | 1.00 → 1.36 / 2.49 |
| | Radish | q03 | 89.0 / 85.4% | 111% → 76 / 78% | 1.00 → 1.25 / 1.23 |
| | Onion | **q02** | 83.2 / 84.3% | 69% → 42 / 55% | 1.00 → 1.90 / 1.49 |
| Wholesale | Cabbage | q03 | 80.9 / 82.3% | 53% → 61 / 65% | 1.00 → 1.26 / 2.10 |
| | Radish | **q02** | 83.6 / 90.5% | 48% → 62 / 65% | 1.00 → 1.20 / 1.30 |
| | Onion | q03 | 81.5 / 85.3% | 28% → 30 / 41% | 1.00 → 2.04 / 1.58 |

★ **The trained quantile must differ per crop.** Setting onion auction to
cabbage's q03 drops coverage to **74.5%** — below target. The better a crop is
predicted, the more aggressively the model narrows the interval.
**Narrow is not the goal; meeting the coverage target and no narrower is.**

**Retail was deferred.** It already meets target in 5 of 6 cells, switching
mostly widens it (radish 32% → 43–47%), conditionality barely appears
(1.07–1.22), and onion reverses on fold B (**0.89**).

**Unchanged:** buffer-breach rate (auction fold A 38% → 38%). The centre is the
same, so this is expected. **We changed "does it warn you how wrong it will be,"
not "how wrong is it."**

★ **Cutover verification (2026-09-03 10:36).** Same inputs, base date 09-02:
**0 of 162 rows changed price** (max difference 0.000000 won). Width changed
+8.9% auction, +26.0% wholesale. The history table recorded
`change_reason='band'`, not `'price,band'` — evidence the centre held.

### 5.7 Boosting library comparison — **rejected, keep LightGBM** (2026-09-01)

| Trees | Fold A LGB / XGB | Fold B LGB / XGB |
|---|---|---|
| 50 | **0.1665** / 0.1686 | 0.1993 / 0.1996 |
| **76 (production)** | **0.1670** / 0.1688 | **0.1968** / 0.1971 |
| 300 | 0.1785 / **0.1760** | 0.1977 / **0.1960** |
| 1200 | 0.1855 / 0.1845 | 0.2049 / 0.2055 |

```
Changing library            0.1670 → 0.1688   (1%)
Getting tree count wrong    0.1665 → 0.1855   (11%)
```

**Tree count matters ten times more than the library.** XGBoost wins at 300
trees — but both are already overfitting there; XGBoost simply degrades more
slowly. CatBoost is clearly worse on fold B (0.2069).

> **Run comparisons at the settings production actually uses.** We first
> measured at 300 trees, reported "XGBoost is better," and retracted it.

### 5.8 MLP pre-check — **rejected, and it stopped a larger effort** (2026-09-01)

An MLP lost to a simple mean. This was the stated basis for **not starting TFT**.

### 5.8b Sequence networks — TFT · LSTM · GRU — **rejected** (2026-09-10)

The MLP result did not show TFT would lose: sequence models read history in order and
take known-future inputs separately, which the MLP could not. Tested them in that form.

```
Rows        identical to LightGBM's (13,908 fold A · 13,892 fold B), auction, 3 crops
Folds       A (validate 2023) · B (validate 2022) — test window not opened
Input       56 survey days · 8 past inputs (incl. production anchor and last known
            auction price) · 7 known-future (weekday ×5, days to holiday, kimchi season)
            · crop as static input · 19 outputs (leads 0–18) at once
Reference   LightGBM at production settings (76 trees, α 0.4) — reproduced 0.1667 vs
            the 09-01 record 0.1670
Seeds       42 · 43 · 44 for every model
```

| Lead ≥ 3 | Anchor | LightGBM | TFT | LSTM | GRU |
|---|---|---|---|---|---|
| Fold A | 0.1730 | **0.1667** | 0.2341 | 0.2308 | 0.2689 |
| Fold B | 0.2096 | **0.1956** | 0.2873 | 0.3477 | 0.4001 |

**23 of 24 crop × fold × model cells were worse than LightGBM by more than 2σ**; one was
undecided (fold A onion, TFT). TFT lost least; GRU lost most and varied most by seed.

★ **Checked before accepting.** The networks were fed the production anchor yet did
twice as badly as copying it at leads 0–2 — the shape of a pipeline bug. Answer
alignment was 100.00%; validation loss bottomed at step 50 and then rose; turning early
stopping off improved GRU only from 0.2464 to 0.2294, still 33% worse than the anchor.
**Not a bug — about 1,475 training days overfit a large model within 50 steps**, on the
same data where LightGBM is best at 50–76 trees.

★ **Found while building it:** on the survey-day axis the anchor disagreed with the
previous cell on 95.6% of Mondays. Auctions run on Saturdays; surveys do not; the
production anchor uses Saturday's price. Without adding the last known auction price
as an input, only the networks would have missed Saturday.

**Not tested:** hyperparameter search (one configuration per model), an
anchor-relative target for the networks (the library forecasts levels), fold C.

Side finding: at leads 0–2 **LightGBM also lost to the strongest baseline on both
folds** (−1.6% · −9.7%). Leads 0–2 went live on 09-09. Not acted on — folds cannot
answer absolute questions (§7.4), and values are frozen until 09-21.

### 5.9 LLM forecasting trial, 5 runs — **rejected** (2026-09-02)

The LLM was prompted directly with the last 14 days plus one point from a year
earlier, and asked for the price path. Five runs, auction, LT≥3:

| | WMAPE | vs anchor |
|---|---|---|
| Anchor | 0.1893 | — |
| LightGBM (production) | 0.1809 | +4.4% |
| **LLM, mean of 5 runs** | **0.1774** | **+6.3%** |

Pooled, the LLM and a model trained on nine years **cannot be told apart**. By
crop they split cleanly: the LLM beat LightGBM on cabbage in 5 of 5 runs, and
lost on onion in 5 of 5.

**Rejected for production because the answer is not stable** — the same question
returned values 3–7% apart from run to run. A forecast that changes when you ask
twice cannot be defended to the purchase team.

### 5.10 Per-crop model split — **rejected on live data** (2026-09-04)

Splitting onion auction into its own model **passed 3 folds and the 2× σ rule**:

```
Fold A (6y) +7.19% · B (5y) +5.48% · C (4y) +19.20%   sum +31.87 (needed 5.93)
```

Rebuilt under production conditions (7-year training) and applied to 164 live
2026 base dates, it **reversed**:

| Crop | Folds | 2026 live |
|---|---|---|
| Onion | +7.19 / +5.48 / +19.20% | **+2.67%** |
| Cabbage | mixed | **−5.70%** |
| Radish | mixed | +2.64% |
| **Pooled** | | **+0.08%** |

**Gains in onion, losses in cabbage, no net benefit.**

★ **Why.** Folds train on less data (C 4y · B 5y · A 6y · production 7y).
**The longer the training, the more pooling pays.** A relative question whose
answer depends on training length cannot be settled by folds.

> **Procedure added:** any change to model structure must pass 3 folds **and
> then be rebuilt under production conditions and checked against 2026 live.**

---

## 6. Feature experiments — nine adjudicated, one adopted

### 6.1 School calendar (school meal demand) — **rejected** (2026-08-24)

| Target | A (2023) | B (2022) | C (2021) | Sum | 2σ |
|---|---|---|---|---|---|
| Auction | **+0.0036 O** | −0.0017 | +0.0027 | +0.0046 | 0.0028 |
| Wholesale | +0.0011 | −0.0014 | −0.0009 | −0.0012 | 0.0023 |
| Retail | −0.0002 | +0.0005 | −0.0005 | −0.0002 | 0.0012 |

**Signs disagree for all three targets.** One of nine cells is a pass. Fold A
alone would have been reported as "auction +3.7% → +5.6%."

The hypothesis was that wholesale buyers are restaurants and school kitchens —
**and wholesale was the worst of the three.**

> Used a year-profile rather than observations: NEIS opened in 2019-04 and keeps
> only two academic years, so observed coverage of the training window was 36.6%.
> Leaving it missing would make "is this before 2020-09" a time index — the same
> trap as §3.2. Leave-one-year-out on the profile: MAE 0.0315, meal-day binary
> agreement 96.7%.

### 6.2 `volume` group — **kept** (2026-08-24, re-adjudicated)

Negative on fold B only; A and C positive for all three targets. Fails the
removal condition. The positives do not clear 2σ, so contribution is **not
proven** either.

### 6.3 News sentiment index (Bank of Korea) — **rejected** (2026-09-01)

Daily, 2005-01-01 onward, no gaps 2015–2026. ECOS key already held.

| Target | Fold A | Fold B | Verdict |
|---|---|---|---|
| Auction | +0.0005 | −0.0020 | undecided |
| Wholesale | +0.0002 | −0.0004 | undecided |
| Retail | −0.0011 | −0.0029 | **remove** |

★ **The failure mode is the finding.** The model used it heavily (6–9%
importance) and got worse. Importance is the evidence:

```
Same-day value (fast)     1.1 – 2.4%
30-day mean (slow)        3.8 – 6.5%     ← the model strongly prefers this
```

Removing only the 30-day mean **eliminated the harm** (retail −0.0040 → +0.0003,
wholesale −0.0003 → +0.0014).

> **§3.2 sharpened.** Was: "monthly/quarterly data becomes a time index."
> **Now: "daily data averaged over a long window falls into the same trap."**
> Feed news and search data as **ratios** (today ÷ 7-day mean), never levels.
> A ratio does not encode which year it is.

### 6.4 Google search volume — **undecided** (2026-09-01)

Daily, 2016-01-01 → 2026-08-31, 3,896 days. All six cells undecided
(−0.0016 to +0.0004); importance 1.7–4.8%. **Not harmful, but not proven.**
Cabbage auction was positive on both folds (+0.0015 / +0.0008) but under 2σ.

★ **Three collection traps, measured:**

```
① Pick search terms empirically   "배추 가격" · "무값" · "채소값" are 99–100% zero
                                   on Google. Reusing Naver terms yields empty columns
② Beyond 9 months it returns weekly buckets
                                   Fetch in 240-day chunks overlapping 60 days, rescale
③ ★ Never leave the last chunk short
                                   2026 peaks read 1,148 (cabbage) and 2,286 (prices)
                                   vs 128–235 and 100–369 in other years. The last
                                   chunk was 65 days, inflating the scale 6–10×.
                                   Production uses exactly this window. Must be fixed
```

`김장` (kimchi-making) is searched only in Nov–Dec, so overlap windows come back
all-zero and cannot be rescaled (100% relative error against the reference).
Dropped. `무` (radish) is a single syllable and is contaminated — mean 76.3,
twice cabbage's, which is not plausible. No substitute term found.

### 6.5 Zero-cost features, four tested — **none adopted** (2026-09-03)

```
prod_area_top1_share    not adopted — reversed on fold C [M-06]
Grade spread            could not build — cabbage second grade ships in 8 kg boxes,
                        a different product
Other wholesale markets rejected — all 9 cells undecided. Radish auction was
                        positive on all three folds but missed 2σ by 0.001
Market-closure days     rejected — closures of 2+ days occur on only 2% of days,
                        no sample to learn from
```

### 6.6 Holiday feature [M-12] — **passed 3 folds, deferred** (2026-09-03)

The only candidate that passed fold C (A +0.0025 · B +0.0140 · C +0.0044).
Radish reproduced; **a new cabbage loss appeared.** Held rather than shipped.

### 6.7 Kimchi-season definition [M-07] — **keep current** (2026-09-03)

No basis to change it.

### 6.8 Cabbage producing-region mapping [M-05] — **do not change** (2026-09-03)

Measured the opposite of the hypothesis.

### 6.9 Import volume and price [M-22] — **the gap was real, so it is unusable** (2026-09-03)

### 6.10 Garlic re-inclusion [D-06] — **still excluded, for a bigger reason** (2026-09-03)

The original blocker was resolved; a larger one replaced it (§7.2).

### 6.11 Four attempts to fix flat-looking forecasts — **all four rejected** (2026-08-31)

**All four failed at the same point**, which is the finding: the problem is not
solvable by adding or removing features. Notably, weather forecast data reaches
only calendar +3–10 days while our horizons are business days, and including
the forecast versus excluding it differed by 0.0002–0.0003.

---

## 7. Diagnostic findings that changed how we read results

### 7.1 ★ Read results **per crop**, never pooled

Pooled WMAPE is dominated by whichever crop has the highest price level. Garlic
(6,244 won/kg) held 66% of the denominator and pulled a pooled figure from
0.2114 to 0.0781.

### 7.2 ★★ Wholesale is unchanged from the previous day six days in ten (2026-09-04)

```
Share of days identical to the previous day (2026, measured)
   Auction     0.6 – 1.3%      moves nearly every day
   Retail     18   – 26%
   Wholesale  58   – 68%       ← six days in ten
```

Daily change: cabbage auction 13.97% · cabbage retail 1.98% · cabbage wholesale
1.61%.

**So the anchor is nearly perfect on wholesale.** The 2026 Q1 cabbage wholesale
anchor error was **3.30%**. There is almost no room to beat it.

> This is exactly why garlic was excluded in §3.4 ("wholesale identical on 94%
> of days"). **The same property holds for the other three crops, only weaker.**

Live results follow directly (2026, 164 base dates, quarterly signs checked):

```
Auction and retail, six cells   five agree in sign and are positive (+10.1 – +16.9%)
Wholesale, three cells          +0.4% · −2.3% · not evaluable — all at anchor level
```

**It is a series problem, not a crop problem** — the same crops do well on
auction and retail. This is why "split models per crop" was dropped as the
first candidate under [M-13].

### 7.3 ★ Blocked combinations cannot be evaluated (2026-09-04)

Combinations disabled in `ref_prediction_quality` have their forecast **replaced
by the anchor** before logging. The log then contains **an anchor compared to
itself.**

```
2026 wholesale onion: 2,604 of 2,652 rows (98%) anchor-substituted
   → the table reads "model 8.41% = anchor 8.41%"
```

**Blocked, so unmeasurable; unmeasurable, so it stays blocked.**

Re-measured with the gate off in shadow mode, it **reversed**: wholesale onion
is the **only one of the three with all three quarters positive** (+7.6 / +10.7
/ +17.9%), while the unblocked radish (−0.3%) and cabbage (−1.9%) are the ones
that disagree.

> **Turn the gate off before re-adjudicating a block.** The batch now runs
> `shadow_whsl_nogate` daily and records it.

### 7.4 ★ Onion needs more than five years of training to beat its anchor (2026-09-03)

Validation fixed at 2023, training end moved:

```
Training window      Retail onion    Auction onion   (cabbage/radish positive at 3y)
2017–2019  3 years      −43.0%          −16.7%
2017–2020  4 years      −16.3%          −16.5%
2017–2021  5 years      +13.5%           +2.2%   ← flips here
2017–2022  6 years       +7.7%           +1.5%
```

Onion autocorrelation is 0.963 — the anchor itself is strong, so beating it
requires more learning. (Not confirmed as the mechanism.)

> ★ **Therefore folds cannot answer "does the model beat the anchor."**
> A **relative** question ("is feature A better?") is fine — both sides train on
> the same window. An **absolute** question ("where should the gate go?") does
> not cancel out. [M-14] hit exactly this: three folds, live log, and sealed
> holdout each gave a different answer.

### 7.5 ★ Do not state a direction from one day's data (2026-09-03)

We told the purchase team "interval width falls from 0.676 to 0.544." That axis
(auction · D+14 · cabbage and radish) had **two rows** that day. Re-measured the
next day on the same axis, **all five axes had widened** (+8.9 to +21.2%).
**Both measurements are correct — they measured different days.**

**Write the sample size next to the conditions, and do not state a direction on
a single-digit sample.**

---

## 8. Final performance

**Sealed test window opened once, 2026-09-01, and closed again.** Production
configuration: training 2017–2023, `--fixed-iter`, `--gate-lt 3`, three crops,
5 seeds. Both windows below are pure holdout.

Baseline is the **strongest of nine candidates**, not the anchor alone (§2.1).

| Target | Crop | 2024–2025 (486 base dates) | 2026 (160 base dates) |
|---|---|---|---|
| **Retail (sell)** | Radish | **+9.0%** | **+6.6%** |
| | Cabbage | **+12.9%** | **+15.7%** |
| | Onion | **+11.8%** | **+9.4%** |
| **Auction (buy)** | Radish | +2.0% | +0.8% |
| | Cabbage | **+13.1%** | **+13.1%** |
| | Onion | +4.5% | **+14.6%** |
| **Wholesale** | Radish | **−7.3%** | −1.2% |
| | Cabbage | +10.9% | **−2.8%** |
| | Onion | +5.4% | +9.5% |

**Three things are clear.**

- **Retail is positive in all nine cells.** It never loses, in either window, on
  any crop. It is the most trustworthy of the three models.
- **Cabbage auction is +13.1% in both windows** — identical to one decimal.
  Coincidence, but it indicates stability, and it is why cabbage was the crop we
  recommended for an aggressive stance.
- **Wholesale radish stays negative.** It was +17.7% on validation 2023 and
  reversed on holdout. **One year had produced that number.**

### 8.1 Larger margins during volatility

Storage trading is used when prices move, so this matters.

```
Auction     normal        model 0.1466 · baseline 0.1585
            top 10% vol   model 0.2113 · baseline 0.2399   ← gap widens
Wholesale   top 10% vol   model 0.1775 · baseline 0.2197
```

### 8.2 Absolute error — read before using this to buy

Source: the sealed-window run above (production model, holdout 2024–2025,
486 base dates, 1,432 rows per lead time).

| Series | Crop | Mean actual | Mean error | Error rate |
|---|---|---|---|---|
| Auction | Cabbage | 963 won | 190 won | **19.7%** |
| | Radish | 771 won | 144 won | 18.6% |
| | Onion | 1,098 won | 98 won | 9.0% |
| Wholesale | Cabbage | 1,603 won | 296 won | 18.5% |
| | Radish | 1,108 won | 158 won | 14.3% |
| | Onion | 1,347 won | 99 won | 7.3% |
| Retail | Cabbage | 4,814 won | 614 won | 12.7% |
| | Radish | 2,497 won | 241 won | 9.7% |
| | Onion | 2,231 won | 184 won | 8.3% |

Degrades with horizon (auction, pooled): LT3 13.0% · LT9 16.0% · LT14 17.8% ·
LT18 19.8%.

### 8.3 ★ Margin buffer — counted in one direction only

Buying below forecast increases margin, so it is not a problem. Below is the
share of cases where **the actual was more than X% above the forecast.**

| LT | (D+) | >3% | >4.7% | >10% |
|---|---|---|---|---|
| 3 | 5 | 50% | 45% | 31% |
| **9–10** | **14** | 52% | **47%** | 37% |
| 18 | — | 56% | 52% | 42% |

**At D+14, nearly half (47%) breach the buffer.** Shortening to LT3 (D+5) still
leaves 45%. **There is no horizon at which auction price is "safe enough."**

By crop (D+14, 952–960 rows):

| Crop | Mean error | >4.7% | >10% |
|---|---|---|---|
| **Cabbage** | 20.3% | **57%** | 51% |
| Radish | 18.9% | 46% | 38% |
| **Onion** | **9.5%** | **38%** | 23% |

**Onion is the safest and cabbage the worst.**

> ★ **Correction issued 2026-09-01.** This table was first drawn from
> `prediction_log`, which mixes `ops-*` (hyphen) experimental backtests with
> `ops_*` (underscore) production records. Averaging four experimental variants
> produced **"cabbage auction error 35.1%, D+14 breach 9%"** — wrong. The correct
> values are 19.7% and 57%. **The breach figure inverts the conclusion**: cabbage
> is the worst crop, not the one safe for an aggressive stance. A correction was
> sent to the purchase team.
>
> **Do not measure performance from `prediction_log`.** One character in the
> model name changes what you are measuring.

---

## 9. Operational experiments (2026-09-09 → 09-10)

### 9.1 Retraining automated — **adopted**

The decision chain is now `judge → build → verify → (pending | discard)`, run by
the batch after the handoff table is delivered. **The live model changes only
when a person clicks.** Losing candidates are deleted and never surfaced.

**Validated by deliberately installing a weak model** (2-year training) in the
production slot. This surfaced **three defects, none of which raised an error**:

```
① Thread id mismatch     server used retrain-auc, tooling used auc
                         → badge appeared, button did nothing
② Stale snapshot         the screen read only the batch's saved file
③ Undeclared state field discarded was not declared in the TypedDict,
                         so LangGraph dropped it silently
```

### 9.2 Retrain threshold re-measured — **3 weeks → 1 week** (2026-09-10)

Replaying 32 weeks of 2026, the longest run of consecutive bad weeks per
combination:

```
auc cabbage 2 · auc onion 2 · rtl onion 2   ← STREAK=3 can never fire
auc radish 3 · rtl radish 3 · rtl cabbage 3
whsl radish 6 · whsl cabbage 15
```

**Three of nine combinations were structurally undetectable.** "Three weeks" was
not a conservative setting; it was an off switch for those series.

A false alarm is cheap — it builds a candidate (2.5 min), compares, and deletes
it if it loses. **The cost is compute; the cost of waiting is three weeks of
degraded forecasts.**

**Wholesale removed from adjudication** (numbers still reported). Per §7.2 it
cannot beat its anchor, so at STREAK=1 it would fire nearly every week and lose
every time.

### 9.3 Report generation split — **adopted** (2026-09-09)

| Approach | Result |
|---|---|
| flash-lite writing alone | 3.9 s. **Escalated a false alarm** and missed a handoff-table change |
| ollama gemma4:e2b translating | 139 s. Mistranslated radish as potato/sweet potato; **fabricated "0 of 103 days" from "0 of 1 day"** |
| **Gemini flash-lite translating** | **15 s. All 216 numbers matched, twice** |

**A rule-based writer cannot step outside what the rule-based tools produced.**
Facts like "this figure came from a single 50 kg lot" require querying the
database directly, so **investigation stays with Claude.**

★ Machine number-matching **catches omissions but not fabrications.** One
occurred during testing and passed the check because both numbers existed in the
source. The English draft is therefore always kept and linked.

---

## 10. Where this stands

### 10.1 Accuracy has hit a measured ceiling

Nine feature experiments produced **one** pass, which was then deferred. Anchor
alternatives produced none. The MLP lost to a mean; an LLM given a 14-day
summary was indistinguishable from nine years of training.

**The remaining gains are not in features.**

### 10.2 The wholesale target is a different problem

Six days in ten it does not move. The anchor is at 3.30% error. **This is not a
model that needs improving; it is a question that needs restating.**

### 10.3 The blocker is a business number, not a model number

Auction error is 19.7% and the D+14 buffer breach is 47%. **Whether that is
usable depends on the target margin and tolerable loss, which are not ours to
set.** Until those exist, "is the model good enough" has no answer.

### 10.4 Open items

```
What the interval width responds to     shadow record accumulating; ~2 weeks
Re-adjudicate blocked combinations      gate-off shadow now recorded daily
Holiday feature [M-12]                  passed 3 folds, cabbage loss unresolved
Garlic re-inclusion [D-06]              blocked by §7.2, not by data
Deep sequence models (TFT/LSTM/GRU)     tested 09-10 and rejected (§5.8b)
Leads 0–2 after the gate was removed     LightGBM lost on both folds — check on 2026 live
Google search last-chunk scaling        ★ must be fixed before any reuse
```

---

## 11. Working rules earned here

```
①  Suspect any number that looks like an improvement
②  A number without conditions is not a result — and write the sample size
③  Verify estimates by measurement (region mapping was wrong for 4–12 months
   per crop; agronomic common sense contradicted distribution reality)
④  "Undecided" is not "no contribution" — it is "not proven"
⑤  Never decide from one year, one fold, or one lumped group
⑥  Always compare against the strongest of several baselines
⑦  A verdict expires when the conditions it was measured under change
⑧  Reproducibility does not catch a wrong setup
⑨  Anything reaching production is checked on live 2026, not folds alone
⑩  Read per crop, never pooled
⑪  Do not measure performance from the operational log without filtering
⑫  A check that exists is not a check that is read
```

★ **Rule ⑫ cost us a week.** `DBEAVER_run_v5.sql` contains validation queries,
but the batch executes the file as one block and discards every result set. They
were visible only when a human ran it in DBeaver. Validation query [14] returned
**100% mismatch for a week** (2026-08-27 → 09-04) and nobody saw it. The batch
now reads `SQL/verify_after_rebuild.sql` and stops on `BAD`.

**Use `BAD` sparingly. An alarm that cries every day is an alarm nobody reads** —
which is the substance of that same incident.
