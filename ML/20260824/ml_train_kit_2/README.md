# 모델 학습 키트

`crop_price_train` CSV 로 LightGBM 을 학습하고 baseline 과 비교합니다.

## 준비

```bash
pip install lightgbm pandas numpy
```

DBeaver 에서 `crop_price_train` 을 CSV 로 내보냅니다.
(테이블 우클릭 → Export Data → CSV)

## 실행

```bash
# 기본: 학습 2022~2024 / 검증 2025, 앵커 대비 로그비율 타겟
python train.py crop_price_train_XXXX.csv

# 학습량-성능 곡선 (데이터를 더 모을 가치가 있는가)
python learning_curve.py crop_price_train_XXXX.csv

# 비교용: 앵커 변환 없이 절대가격 학습
python train.py crop_price_train_XXXX.csv --raw

# 분할 지점 변경
python train.py crop_price_train_XXXX.csv --train-end 2023-12-31
```

## 산출물

| 파일 | 내용 |
|---|---|
| `curve_leadtime.csv` | 리드타임별 모델·baseline·개선율·방향정확도 |
| `feature_importance.csv` | feature 기여도(gain %) |
| `learning_curve.csv` | 학습 시작일별 성능 |

---

## 결과 읽는 법

### 1. baseline 대비 개선율이 핵심

절대 WMAPE 는 의미가 약합니다. `어제 가격 그대로` 를 얼마나 이기는지가 지표입니다.
음수면 모델이 baseline보다 나쁘다는 뜻입니다.

### 2. `best_iter` 를 반드시 보세요

```
seed  42: WMAPE 0.1662  (best_iter 4)
```

`best_iter` 가 한 자릿수면 **모델이 학습을 거의 못 한 것**입니다.
몇 그루만 쌓아도 검증 오차가 늘기 시작했다는 뜻이며,
데이터에서 baseline 을 넘을 신호를 찾지 못한 상태입니다.

정상이라면 수백~수천이 나옵니다.

### 3. 고유 기준일 수가 실질 표본 크기입니다

```
학습  13,230행  (고유 기준일 735)
```

한 기준일이 리드타임 18행으로 복제되므로 `whsl_prc_lag1` 같은
기준일 시점 feature 는 18행 전부 동일합니다.
**행수 13,230 이 아니라 기준일 735 개가 실질 독립 표본**입니다.

feature 29개를 735개 표본으로 학습하는 것은 무리입니다.

### 4. 시드 표준편차와 개선율을 비교하세요

개선율 +5.3%, 표준편차 0.0029(≈1.8%) 라면 차이가 유의합니다.
개선율 +0.7%, 표준편차 0.0022 라면 노이즈와 구분되지 않습니다.

---

## 현재까지 실측 결과 (2026-08-14)

배추 단독, 학습 2022~2024 (기준일 735), 검증 2025

| 구성 | WMAPE | baseline 대비 |
|---|---|---|
| baseline (어제 가격) | 0.1645 | — |
| LightGBM 절대가격 타겟 | 0.1699 | −3.3% |
| LightGBM 앵커 비율 타겟 | 0.1654 | −0.5% |

**둘 다 baseline 을 이기지 못했습니다.**

### 앵커 변환의 효과는 확인됨

| LT | 절대가격 타겟 | 앵커 비율 타겟 | baseline |
|---|---|---|---|
| 1 | 0.1563 (−95%) | 0.0827 (−3%) | 0.0800 |
| 18 | 0.1875 (+11%) | 0.2085 (+0.7%) | 0.2100 |

절대가격 타겟은 `lead_biz_d` 중요도가 1.5% 에 그쳤고 WMAPE 가 리드타임 전체에서
0.156~0.188 로 거의 평평했습니다. 모델이 리드타임을 무시하고 평균 가격 수준만
학습한 것입니다. 앵커 변환 후 LT1 이 baseline 에 붙었고 구조 문제는 해소됐습니다.

### 학습량 곡선 — 아직 노이즈 구간

| 학습 시작 | 기준일 수 | 개선율 | 시드 표준편차 |
|---|---|---|---|
| 2024-01-01 | 244 | −3.1% | 0.0006 |
| 2023-01-01 | 489 | **+5.3%** | 0.0029 |
| 2022-01-01 | 735 | −0.7% | 0.0022 |

데이터를 늘렸는데 오히려 나빠졌습니다. 단조 증가가 아니라 오르내림이므로
**신호가 아니라 노이즈**입니다. 학습 구간을 조금만 바꿔도 결과가 크게 흔들리는
상태이며, 표본이 부족하다는 증거입니다.

---

## 결론과 다음 단계

**모델이 나쁜 것이 아니라 데이터가 부족합니다.**
3년(735 기준일)으로는 "어제 가격 그대로" 를 이길 패턴을 찾을 수 없습니다.

### 최우선 — 2015~2025 로 재적재

`DBEAVER_run_all.sql` 에서 기간을 바꿔 재실행합니다.

```sql
-- 09_insert 섹션에서 이 부분을 찾아 수정
WHERE b.base_dt BETWEEN '2022-01-01'::DATE AND '2025-12-31'::DATE
                     ↓
WHERE b.base_dt BETWEEN '2015-01-01'::DATE AND '2025-12-31'::DATE
```

반입량은 2021-05 이후만 채워지고 그 전은 NULL 이 됩니다.
LightGBM 은 NULL 을 처리하므로 학습에 문제없습니다.

기대 효과: 고유 기준일 735 → 약 2,700 개 (3.7배)

그다음 분할을 되돌립니다.

```bash
python train.py crop_price_train_XXXX.csv --train-end 2022-12-31   # 검증 2023
python learning_curve.py crop_price_train_XXXX.csv --train-end 2022-12-31
```

학습량 곡선이 이번엔 단조 증가하는지 확인하세요.
그렇다면 데이터 확보가 정답이라는 근거가 됩니다.

### 그다음 — feature 축소 실험

표본 735 개에 feature 29 개는 과합니다. 데이터가 늘기 전까지는
핵심 feature 만 남기는 쪽이 안정적일 수 있습니다.

```
lag 3종 + 앵커 + 리드타임 + 요일  →  6~8개
```

`feature_importance.csv` 상위 항목부터 남기며 성능 변화를 보세요.

### 앵커 변환은 계속 사용

구조적으로 옳은 방향임이 확인됐습니다. 모델이 0 을 출력하면 자동으로
baseline 과 같아지므로, baseline 아래로 크게 떨어질 위험이 줄어듭니다.

---

## 발표 관점

이 결과는 실패가 아니라 **측정**입니다.

> "3년 데이터로는 단순 baseline 을 넘지 못했고, 학습량 곡선이 단조 증가하지
> 않는 것을 확인해 표본 부족이 원인임을 진단했다. 유효 표본이 행수가 아니라
> 고유 기준일 수(735)라는 점도 함께 확인했다."

"모델을 돌렸더니 잘 나왔다" 보다 방어하기 쉬운 서사입니다.

---

## 2026-08-24 변경 (ml_train_kit_2)

- `train.py --valid-end` : 3분할. 검증 (train_end, valid_end] / 테스트 (valid_end, ~) 봉인
- `train.py --report-test` : 테스트 평가 (최종 확인 때만). 검증 best_iter 그대로 적용
- `ablation.py --valid-end` / `--keep-all` : 1차 확정 feature 세트에서 LOO 출발
- `results/` : 이번 실행 로그·CSV. 자세한 해석은 진행기록/테스트봉인_ablation2차_20260824.md

```bash
python train.py <csv> --target auc --train-start 2017-01-01 --train-end 2022-12-31 --valid-end 2023-12-31 --seeds 42 43 44 45 46
python ablation.py <csv> --target auc --mode loo --valid-end 2023-12-31 --seeds 42 43 44 45 46 47 48 49 50 51
python ablation.py <csv> --target auc --mode loo --train-end 2021-12-31 --valid-end 2022-12-31 --seeds 42 43 44 45 46 47 48 49 50 51
```
- `train.py --gate-lt 3` : LT1~2 를 앵커로 대체 (운영 권장). `--save-pred` 예측 저장, `--fixed-iter` 고정 라운드
- `results/gate/` 검증 예측(2022·2023 폴드) · `results/earlystop/` 조기종료 비교 로그
