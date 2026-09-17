# 1-Minute Talk Plan: Price Forecasting + QA Agent (2026-09-17)

## One message

**"We forecast vegetable prices three weeks ahead, and anyone can ask about them in plain words."**
Everything in the talk supports this sentence. Everything else goes to backup slides.

## Time budget (60 s ≈ 110 spoken words, leaving ~10 s buffer)

| Beat | Seconds | Content | Slide |
|---|---|---|---|
| 1. What | 0–10 | 3 crops × 3 prices × up to 18 business days; runs unattended daily | 1 |
| 2. How well | 10–28 | LightGBM beat XGBoost / CatBoost / neural net; error rates vs baseline | 1 |
| 3. Lesson | 28–38 | Biggest gain was fixing mixed packaging data, not the model | 1 |
| 4. QA agent | 38–55 | One sentence → price + batch + performance; AI only picks, DB gives numbers; 98.5% | 2 |
| Buffer | 55–60 | Pause / transition | — |

## Slides (two only) — charts instead of tables

Charts live in `발표/그래프/최종_EN/` (English) and `발표/그래프/최종_KR/` (Korean, same numbers).
Regenerate with `python 발표/그래프/make_final_charts.py`.

**Slide 1 — Price forecasting**

| Position | Chart | What the audience sees in 2 seconds |
|---|---|---|
| Main (left, large) | `1_error_retail_auction.png` | Green bar is shorter than grey in all 6 pairs |
| Right, top | `2_algorithm_comparison.png` | LightGBM is lowest; neural net is far worse than no model |
| Right, bottom | `3_packaging_fix.png` | 1 kg box costs 15× the 10 kg net; autocorrelation 0.085 → 0.795 |

If the slide is too crowded, keep chart 1 large and chart 2 small, and say the packaging story out loud without chart 3.

**Slide 2 — QA agent**

| Position | Content |
|---|---|
| Left | Flow diagram: Question → AI picks (topic · crop · price · date) → Price / Batch / Performance read DB → Answer |
| Right, top | Chat screenshot of "3-day cabbage prices, yesterday's batch, and model performance" |
| Right, bottom | `4_qa_agent_accuracy.png` — 98.5% vs 87.9% vs 72.7%, with seconds per question |

**Backup slides (Q&A only)**

| Chart | Use when asked |
|---|---|
| `B1_error_all_prices.png` | "What about wholesale?" — shows radish wholesale in red where the baseline wins |
| `B2_error_by_lead_time.png` | "How far ahead can we trust it?" — error 12.5% at 3 days → 18.5% at 18 days |
| `B3_feature_importance.png` | "What does the model look at?" — origin weather 33% of auction model; retail has no weather |

Charts are better than tables here because every comparison is "which bar is shorter".
The audience gets it in under two seconds; a 3×3 table needs reading time you don't have.

**Value check.** Cabbage auction is shown as 19.7%, the log's error-rate column.
The WMAPE column in the same log is 0.1975, which would round to 19.8. Every document uses 19.7, so the chart does too.

## Script (~107 words)

> We forecast cabbage, radish and onion prices — auction, wholesale and retail — up to 18 business days ahead. It runs unattended every morning and feeds the purchasing team.
>
> We use LightGBM; XGBoost, CatBoost and a neural network did no better. On two unseen years, retail error was 8 to 13 percent, lower than the baseline for all three crops.
>
> Our biggest gain came from data, not the model: 1-kilo packs were mixed with 10-kilo nets, making prices look random.
>
> Our QA agent answers price, batch and model questions in one sentence. The AI only chooses what you asked; every number comes from the database. It understood 98.5 percent of our test questions.

## What to cut (move to backup / Q&A)

- Hyperparameter table, 31-feature table, value ranges
- Wholesale price results, lead-time table, LLM-as-forecaster test
- Quantile bands, monitoring agents, retrain button, cutover history

## Q&A backup — likely questions and exact answers

| Question | Answer |
|---|---|
| Does it ever lose? | Yes. Wholesale radish: model 14.3% vs baseline 13.3%. Wholesale price equals yesterday's on 6 of 10 days. |
| How far can buyers trust it? | No safe horizon for auction price. At D+14, actual price exceeded the forecast by >4.7% on 47% of days. |
| Is 98.5% forecast accuracy? | No. It is how often the agent understood the question. Price error is on slide 1. |
| Why not a local LLM? | Tested: 87.9% and 12.3 s per question, and it could not reject out-of-scope crops (green onion, garlic). |
| Key hyperparameters? | Learning rate 0.03, 31 leaves, min 60 rows per leaf, 0.8 feature/row sampling, L2 1.0, L1 loss, 76 trees (auction). |
| Most important input? | Days until the next Seollal/Chuseok holiday — top in all three models (8.3–9.7%). |

## Sources

- Error rates: `실험결과/2026-09-01_133352_train_auc_valid2025.txt`, `2026-08-31_173522_train_rtl_valid2025.txt`
- Algorithm comparison: `진행기록/부스팅모델비교_XGBoost_CatBoost_20260901.md`, `신경망_사전확인_MLP_20260901.md`
- QA scores: `진행기록/QA해석기_로컬LLM_비교_20260917.md`
- Full detail (Korean): `발표/최종발표_ML_QA_20260917.md`
