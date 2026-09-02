# 원가 캣쳐 — DB 전체 테이블 정의서 v3

> PostgreSQL `cost_catcher_raw` · 테이블 22개 · 369컬럼 · 뷰 3개
> 생성 2026-08-25 · **`DB/gen_table_doc.py` 로 재생성합니다. 손으로 고치지 마세요**

## 이 문서를 읽는 법

**컬럼 표는 살아 있는 DB 에서 뽑았습니다.** 타입·NOT NULL·결측률·제약·인덱스는
실제 스키마와 항상 일치합니다. 표 위의 설명글만 사람이 씁니다
(`gen_table_doc.py` 의 `NOTES`·`DESC`).

설명 끝의 `↩` 는 **다른 테이블에서 물려받은 것**입니다 — `predict_input` 은
`crop_price_train` 과 같은 컬럼이라 설명을 따로 두지 않습니다.

`결측%` 는 전체 행 대비 NULL 비율입니다. **정상적인 결측과 사고를 구분하세요** —
예를 들어 `weather_asos_raw.sumRn` 의 62.2%는 ASOS 가 무강수일에 빈 값을 주는
것이고, `crop_price_train.crop_area_yoy_rt` 의 75%는 feature 제외 사유입니다.

### 앞선 문서와의 관계

| 문서 | 범위 | 상태 |
|---|---|---|
| **이 문서** | **전 테이블 22개** | 최신. 생성본 |
| `crop_price_train_컬럼정의서_v2.md` | `crop_price_train` 상세 | 유효. 계보·결측·학습 설정 |
| `예측_달력_테이블_컬럼정의서_v1.md` | 달력·예측 7종 | 유효. 다른 파트 계약 문서 |
| `9개_테이블_정의서_v2_2.md` | RAW 8 + train 1 | **일부 낡음** ↓ |

`9개_테이블_정의서_v2_2.md`(2026-08-14)에서 어긋난 곳입니다.

- `crop_price_train` 절이 **경락가 단일 타겟 시절** 것입니다 (33컬럼 → 실제 46).
  `auc_prc_avg14`·`auc_prc_std7`·`auc_prc_lag7` 은 지금 없습니다
- `daily_volume` 이 "1,438행 · 2021-05-29~ · 배추만" 으로 적혀 있으나
  실제로는 **18,265행 · 2014-12-24~ · 5품목** 입니다
- `daily_volume.mmdd` 생성 컬럼은 **문서에만 있고 실제로는 없습니다**
- `auction_prices_daily` · `ref_*` 5종 · `predict_input` · `prediction_log` 계열이
  통째로 빠져 있습니다

RAW 8종의 **설계 원칙·코드값·출처** 서술은 여전히 유효하니 그쪽을 참고하세요.

---


## 테이블 한눈에

| 그룹 | 테이블 | 행수 | 컬럼 | 역할 |
|---|---|--:|--:|---|
| RAW — 수집 원본 | `veg_daily_price_raw` | 1,044,224 | 22 | 중도매가·소매가의 원천. 시장 × 품종 × 등급 × 조사구분의 다차원 격자다. |
| RAW — 수집 원본 | `auction_prices_daily` | 781,136 | 17 | 경락가(경매 낙찰가)의 원천. 전국 32개 도매시장. |
| RAW — 수집 원본 | `daily_volume` | 18,270 | 12 | 품목별 일자별 반입 물량과 상위 산지. 공급 충격 신호. |
| RAW — 수집 원본 | `weather_asos_raw` | 401,563 | 64 | 주산지·소비지 기상. 95개 관측소. |
| RAW — 수집 원본 | `econ_daily_raw` | 4,199 | 14 | M2·EPU·PPI 등 거시 변수. |
| RAW — 수집 원본 | `krei_price_monthly_raw` | 3,005 | 16 | 월별 도매가격 동향. |
| RAW — 수집 원본 | `krei_production_yearly_raw` | 127 | 16 | 생산전망·재배면적 증감률. |
| RAW — 수집 원본 | `krei_import_monthly_raw` | 1,501 | 11 | 월별 수입 동향. |
| RAW — 수집 원본 | `krei_inventory_yearly_raw` | 120 | 15 | 재고 동향. |
| RAW — 수집 원본 | `daily_volume_stg` | 0 | 10 | 반입량 적재용 스테이징. 현재 0행. |
| 기준정보 — 규칙·매핑 | `ref_holiday` | 264 | 5 | 공휴일 원본. `ref_calendar` 의 입력. |
| 기준정보 — 규칙·매핑 | `ref_calendar` | 5,114 | 8 | 달력. **축이 두 개**입니다. |
| 기준정보 — 규칙·매핑 | `ref_calendar_override` | 18 | 4 | 규칙으로 설명 안 되는 휴장·개장. |
| 기준정보 — 규칙·매핑 | `ref_school_day` | 5,114 | 3 | 서울 초·중·고 개교율(급식 수요 대리변수). |
| 기준정보 — 규칙·매핑 | `ref_item_station` | 17 | 8 | 품목 × 월 → 주산지 ASOS 관측소 매핑. |
| 학습·추론 | `crop_price_train` | 198,721 | 46 | 학습 테이블. **1행 = (기준일 × 품목 × 리드타임 1~18)** |
| 학습·추론 | `predict_input` | 2,160 | 44 | 추론 입력. `crop_price_train` 과 같은 feature, 타겟은 없음. |
| 예측 산출 — 다른 파트 계약 | `prediction_log` | 107,082 | 20 | 예측 저장. **다른 파트에 넘기는 계약 테이블.** |
| 예측 산출 — 다른 파트 계약 | `ref_prediction_band` | 162 | 6 | 예측 구간(`pred_lo`/`pred_hi`) 근거. |
| 예측 산출 — 다른 파트 계약 | `ref_prediction_quality` | 9 | 13 | 품목 × 타겟 조합별 실측 신뢰도. **`predict.py` 가 이 표를 보고 게이트합니다.** |
| 운영 — 배치 이력 | `batch_run` | 3 | 9 | 배치 실행 이력. 한 행 = 실행 한 번. |
| 운영 — 배치 이력 | `batch_run_stage` | 3 | 6 | 배치 단계별 결과. 실행당 최대 9행. |

---

# RAW — 수집 원본

## `veg_daily_price_raw`

| | |
|---|---|
| 역할 | 중도매가·소매가의 원천. 시장 × 품종 × 등급 × 조사구분의 다차원 격자다. |
| 출처·생성 | aT 오픈API `B552845/perDay/price` · `collect_kamis.py` (증분 · DB 직행) |
| 규모 | 1,044,224행 · 22컬럼 |
| 범위 | `exmn_ymd` 2015-01-02 ~ 2026-08-24 |
| PK | `(id)` |
| UNIQUE | `(exmn_ymd, item_cd, vrty_cd, grd_cd, se_cd, sgg_cd, mrkt_cd, unit, unit_sz)` |

**`se_cd=02`(중도매)는 경매 낙찰가가 아닙니다.** 중도매인이 소상인에게 파는
가격이라 경락가와 수준이 다릅니다. 경락가는 `auction_prices_daily` 쪽입니다.

**단위가 섞여 있어 정규화가 필수입니다.** 배추 `포기/1` · `kg(그물망 3포기)/10` ·
`g/100` 이 공존하고, 양파 중도매는 2017-01~2018-06 에 `unit_sz=20` 이 섞여
정규화하지 않으면 그 구간 가격이 33% 튑니다.

**배추는 작형에 따라 품종이 교대됩니다.** 단일 품종만 고르면 시계열이 연중
끊깁니다. 품목 단위로 집계해야 합니다.

학습에 쓰는 필터는 두 가지입니다.
`se_cd=02 · grd_cd=04 · mrkt_nm='가락도매'` → 중도매가,
`se_cd=01 · grd_cd=04 · sgg_cd='1101'`(서울) → 소매가.
**소매를 전국 평균으로 두면 2023년에 조사 점포가 44→59개로 늘어 집계 기준이
학습·검증 구간에서 달라집니다.**

| 컬럼 | 타입 | NN | 결측% | 설명 |
|---|---|:--:|--:|---|
| `id` | bigint | ● | 0.0 | DB 내부 식별자 |
| `exmn_ymd` | date | ● | 0.0 | 조사일자 |
| `ctgry_cd` | character varying(10) | ● | 0.0 | 부류코드 (200=채소류) |
| `ctgry_nm` | character varying(50) |  | 0.0 | 부류명 |
| `item_cd` | character varying(10) | ● | 0.0 | 품목코드. 211 배추 · 231 무 · 241 고추 · 244 피마늘 · 245 양파 · 258 깐마늘. **품목은 이 컬럼으로 센다** (item_nm 은 원천이 바꾼다) |
| `item_nm` | character varying(50) |  | 0.0 | 품목명. **원천이 바꾼다** — 2026 부터 고추→건고추 · 마늘→피마늘. 필터·집계에 쓰지 말 것 |
| `vrty_cd` | character varying(10) | ● | 0.0 | 품종코드. 배추는 작형에 따라 교대 |
| `vrty_nm` | character varying(50) |  | 0.0 | 품종명 |
| `grd_cd` | character varying(10) | ● | 0.0 | 등급코드 (04=상품, 05=중품) |
| `grd_nm` | character varying(50) |  | 0.0 | 등급명 |
| `se_cd` | character varying(10) | ● | 0.0 | 조사구분코드 (01 소매 · 02 중도매). 02 는 경락가가 아님 |
| `se_nm` | character varying(50) |  | 0.0 | 조사구분명 |
| `sgg_cd` | character varying(10) | ● | 0.0 | 시군구코드 (1101=서울). 소매 필터에 사용 |
| `sgg_nm` | character varying(50) |  | 0.0 | 시군구명 |
| `mrkt_cd` | character varying(20) | ● | 0.0 | 시장코드 |
| `mrkt_nm` | character varying(100) |  | 0.0 | 시장명 (중도매 필터: 가락도매) |
| `unit` | character varying(50) | ● | 0.0 | 단위 문자열. kg/포기/g 혼재 |
| `unit_sz` | numeric(12,3) | ● | 0.0 | 단위크기. 원/kg 정규화의 분모 |
| `exmn_dd_prc` | numeric(15,2) |  | 0.0 | 조사일 가격 (unit/unit_sz 기준) |
| `exmn_dd_cnvs_prc` | numeric(15,2) |  | 0.0 | 조사일 kg 환산가격 (원천 제공값) |
| `orgnl_reg_dt` | timestamp with time zone |  | 0.0 | 원본 등록일시 |
| `created_at` | timestamp without time zone | ● | 0.0 | DB 적재 시각 |

**인덱스**

- `veg_daily_price_raw_pkey`
- `veg_daily_price_raw_uk`

**코드값**

| 구분 | 코드 |
|---|---|
| `se_cd` | 01 소매 · **02 중도매** · 03 친환경 · 07 친환경(신규) |
| `grd_cd` | **04 상품** · 05 중품 · 07 유기농 · 08 무농약 |
| `vrty_cd` | 배추 01 봄 · 02 여름(고랭지) · 03 가을 · 06 월동 / 양파 00 · 02 햇양파 · 10 수입 |
| `ctgry_cd` | 200 채소류 |
| `item_cd` | 211 배추 · 231 무 · 241 고추 · **244 피마늘** · 245 양파 · **258 깐마늘** |

**244 와 258 을 헷갈리지 말 것.** 피마늘과 깐마늘은 다른 물건이고 유통 마진이
다릅니다 (경락 3,398 → 피마늘 5,778 / 깐마늘 7,385). **소매는 258 에만** 있습니다.

**원천이 이름을 바꿉니다 (2026-08-25 발견).** `item_cd` 는 그대로인데
2026 부터 241 `고추`→`건고추`, 244 `마늘`→`피마늘` 로 바뀌었습니다.
품목을 세거나 최신일을 찾을 때 **`item_nm` 이 아니라 `item_cd` 를 쓰세요** —
`collect_kamis.py` 가 이 함정에 걸려 "신규 0행" 으로 잘못 보고했습니다.

## `auction_prices_daily`

| | |
|---|---|
| 역할 | 경락가(경매 낙찰가)의 원천. 전국 32개 도매시장. |
| 출처·생성 | 공공데이터포털 `전국 공영도매시장 경매원천정보` · `auction_collector` 패키지 |
| 규모 | 781,136행 · 17컬럼 |
| 범위 | `auction_date` 2015-01-02 ~ 2026-08-24 |
| PK | `(id)` |
| UNIQUE | `NULLS NOT DISTINCT (auction_date, wholesale_market_code, item_code, grade_code, grade_name)` |

**`target_auc_prc` 와 `auc_prc_*` 의 유일한 출처입니다.**
학습에는 서울가락(`wholesale_market_code=110001`) · 특등급(`grade_code=11`) 만 씁니다.

가격 3종(평균·최저·최고)이 다 있어 **일중 스프레드**(`auc_prc_spread_lag1`)를
만들 수 있습니다. 품질 저하·공급 불안의 대리 지표입니다.

`grade_code` 만 NULL 을 허용합니다 — 원천에서 등급 미상인 경우가 있습니다.

수집기가 증분·캐시·검증·DB적재를 갖춘 유일한 물건입니다. 나머지 수집기의
참고 모델로 삼으세요.

| 컬럼 | 타입 | NN | 결측% | 설명 |
|---|---|:--:|--:|---|
| `id` | bigint | ● | 0.0 | DB 내부 식별자 |
| `auction_date` | date | ● | 0.0 | 경매일자 |
| `market_category` | character varying(10) | ● | 0.0 | 시장 부류 |
| `wholesale_market_code` | character varying(20) | ● | 0.0 | 도매시장 코드 (110001=서울가락) |
| `wholesale_market_name` | character varying(100) | ● | 0.0 | 도매시장명 |
| `item_code` | character varying(20) | ● | 0.0 | 품목코드 |
| `item_name` | character varying(50) | ● | 0.0 | 품목명 |
| `grade_code` | character varying(20) |  | 0.0 | 원천에서 미상인 경우 NULL |
| `grade_name` | character varying(50) | ● | 0.0 | 등급명 (11=특) |
| `avg_auction_price_krw_per_kg` | numeric(28,6) | ● | 0.0 | 평균 경락가(원/kg). auc_prc_lag1 의 원천 |
| `min_auction_price_krw_per_kg` | numeric(28,6) | ● | 0.0 | 최저 경락가(원/kg). 일중 스프레드 계산에 사용 |
| `max_auction_price_krw_per_kg` | numeric(28,6) | ● | 0.0 | 최고 경락가(원/kg). 일중 스프레드 계산에 사용 |
| `trade_volume_kg` | numeric(28,6) | ● | 0.0 | 거래물량(kg). auc_vol_lag1 의 원천 |
| `trade_amount_krw` | numeric(28,6) | ● | 0.0 | 거래금액(원) |
| `package_trade_quantity` | numeric(28,6) | ● | 0.0 | 포장 거래수량 |
| `source_trade_count` | bigint | ● | 0.0 | 집계에 사용된 원천 거래 건수 |
| `source` | character varying(200) | ● | 0.0 | 출처 API 표기 |

**인덱스**

- `auction_prices_daily_grade_idx`
- `auction_prices_daily_item_date_idx`
- `auction_prices_daily_market_date_idx`
- `auction_prices_daily_natural_key_v2_uq`
- `auction_prices_daily_pkey`

## `daily_volume`

| | |
|---|---|
| 역할 | 품목별 일자별 반입 물량과 상위 산지. 공급 충격 신호. |
| 출처·생성 | 농넷 수급일보 스크래핑 · `농넷에서 일일산출량 적재.py --load-db` |
| 규모 | 18,270행 · 12컬럼 |
| 범위 | `base_date` 2014-12-24 ~ 2026-08-25 |
| PK | `(base_date, item_label)` |

가격만으로는 공급 충격의 **방향**을 알 수 없습니다. 반입량은 가격과 반대로
움직이는 대표적 수급 변수이고, 상위 산지는 주산지 기상 매핑(`ref_item_station`)을
실측으로 검증하는 근거가 됩니다.

**`req_date` 가 `base_date` 보다 0~7일 늦습니다.** 8일 창으로 훑는 수집 방식
때문입니다. `crop_price_train` 은 이 지연을 그대로 살려 **as-of 결합**을 합니다 —
기준일까지 실제로 수집이 끝난 물량만 씁니다. 무시하고 결합하면 미래정보 누수입니다.

**HTML 표가 아니라 인라인 자바스크립트를 파싱합니다.** 표가 "데이터가 없습니다"
여도 차트 데이터는 살아 있습니다. 농넷이 개편하면 깨지므로 `probe` 로 먼저
확인하세요.

적재 전에 **겹치는 구간을 값까지 대조**합니다. 기존 행도 같은 스크래퍼로 받은
것이라, 지금 긁은 값이 다르면 경계를 기준으로 성격이 다른 데이터가 이어붙습니다.
(2026-08-24 실측: 겹치는 215행·65행 모두 불일치 0)

`top1_raw`·`top2_raw` 는 최근 수집분에만 있습니다(84% NULL). 구분자가
NBSP(U+00A0)라 일반 공백으로 split 하면 안 됩니다.

**최근 14일은 정정을 반영합니다 (2026-08-25).** 농넷은 수급"일보" 라 최근 물량이
뒤늦게 올라옵니다 — 실측에서 8/18~8/24 17건이 전부 늘었습니다
(8/18 양파 1,407 → 1,658톤). 반영하지 않으면 모델이 낡은 물량으로 학습합니다.
그 이전 구간은 덮어쓰지 않습니다 — **오래된 값이 바뀌면 정정이 아니라 사고**입니다.

| 컬럼 | 타입 | NN | 결측% | 설명 |
|---|---|:--:|--:|---|
| `base_date` | date | ● | 0.0 | 기준일자. PK(1) |
| `item_label` | character varying(20) | ● | 0.0 | 품목명. PK(2) |
| `total_ton` | integer | ● | 0.0 | 일 합계 반입량(톤) |
| `top1_region` | character varying(20) |  | 19.7 | 1위 산지. 반입 0톤인 날은 NULL |
| `top1_ton` | integer | ● | 0.0 | 1위 산지 물량(톤) |
| `top2_region` | character varying(20) |  | 22.3 | 2위 산지 |
| `top2_ton` | integer | ● | 0.0 | 2위 산지 물량(톤) |
| `etc_ton` | integer | ● | 0.0 | 1·2위 외 기타 산지 합계(톤) |
| `req_date` | date | ● | 0.0 | 수집 일자. base_date 보다 0~7일 늦다. as-of 결합의 기준 |
| `top1_raw` | text |  | 84.3 | 1위 원문. 구분자가 NBSP(U+00A0) |
| `top2_raw` | text |  | 84.3 | 2위 원문 |
| `loaded_at` | timestamp with time zone | ● | 0.0 | DB 적재 시각 |

**CHECK 제약**

- `CHECK (((total_ton >= 0) AND (top1_ton >= 0) AND (top2_ton >= 0) AND (etc_ton >= 0)))`
- `CHECK ((top1_ton >= top2_ton))`
- `CHECK ((req_date >= base_date))`

**인덱스**

- `ix_daily_volume_item_date`
- `ix_daily_volume_req_date`
- `ix_daily_volume_top1_region`
- `pk_daily_volume`

## `weather_asos_raw`

| | |
|---|---|
| 역할 | 주산지·소비지 기상. 95개 관측소. |
| 출처·생성 | 기상청 ASOS 일자료 · `fetch_asos.py --load-db` |
| 규모 | 401,563행 · 64컬럼 |
| 범위 | `tm` 2015-01-01 ~ 2026-08-24 |
| PK | `(id)` |
| UNIQUE | `("stnId", tm)` |

**64컬럼 중 4개만 씁니다** — `stnNm` · `tm` · `avgTa` · `sumRn`.
나머지는 원형 보존 원칙에 따라 받아만 뒀습니다. 습도·일조·풍속은 미사용 feature
후보입니다(백로그 P3).

**`sumRn` 은 NULL 62.2% · 0 이 8.5% 로 혼재합니다.** ASOS 가 무강수일에 빈 값을
주는 경우가 있어 feature 단계에서 `COALESCE(sumRn,0)` 을 겁니다. RAW 는 원형을
보존합니다.

**`tm` 이 `character varying` 입니다.** 날짜 비교 시 `"tm"::DATE` 캐스팅이
필요합니다.

**수집기는 2026-08-25 에 확보했습니다.** 계약 점검 7종이 메모리에서 돌고
CSV 를 거치지 않고 바로 적재합니다. 겹치는 1,140행 대조에서 불일치 0 이었습니다.

공공데이터포털은 **계정당 인증키가 하나**입니다. ASOS 를 활용신청하지 않으면
다른 API 에서 되는 키도 403 `SERVICE_KEY_IS_NOT_REGISTERED_ERROR` 를 냅니다.

| 컬럼 | 타입 | NN | 결측% | 설명 |
|---|---|:--:|--:|---|
| `id` | bigint | ● | 0.0 | DB 내부 식별자 |
| `stnId` | character varying(10) | ● | 0.0 | 종관기상관측 지점 번호 |
| `stnNm` | character varying(50) |  | 0.0 | 종관기상관측 지점명 |
| `tm` | character varying(10) | ● | 0.0 | 일시 |
| `avgTa` | double precision |  | 0.1 | 평균 기온(°C) |
| `minTa` | double precision |  | 0.0 | 최저 기온(°C) |
| `minTaHrmt` | character varying(10) |  | 0.0 | 최저 기온 시각(hhmi) |
| `maxTa` | double precision |  | 0.0 | 최고 기온(°C) |
| `maxTaHrmt` | character varying(10) |  | 0.0 | 최고 기온 시각(hhmi) |
| `sumRnDur` | double precision |  | 90.3 | 강수 계속시간(hr) |
| `mi10MaxRn` | double precision |  | 75.7 | 10분 최다강수량(mm) |
| `mi10MaxRnHrmt` | character varying(10) |  | 83.2 | 10분 최다강수량 시각(hhmi) |
| `hr1MaxRn` | double precision |  | 75.7 | 1시간 최다강수량(mm) |
| `hr1MaxRnHrmt` | character varying(10) |  | 82.6 | 1시간 최다 강수량 시각(hhmi) |
| `sumRn` | double precision |  | 62.4 | 일강수량(mm) |
| `maxInsWs` | double precision |  | 0.1 | 최대 순간풍속(m/s) |
| `maxInsWsWd` | double precision |  | 0.1 | 최대 순간 풍속 풍향(16방위) |
| `maxInsWsHrmt` | character varying(10) |  | 0.1 | 최대 순간풍속 시각(hhmi) |
| `maxWs` | double precision |  | 0.1 | 최대 풍속(m/s) |
| `maxWsWd` | double precision |  | 0.1 | 최대 풍속 풍향(16방위) |
| `maxWsHrmt` | character varying(10) |  | 0.1 | 최대 풍속 시각(hhmi) |
| `avgWs` | double precision |  | 0.2 | 평균 풍속(m/s) |
| `hr24SumRws` | double precision |  | 0.2 | 풍정합(100m) |
| `maxWd` | double precision |  | 0.4 | 최다 풍향(16방위) |
| `avgTd` | double precision |  | 0.2 | 평균 이슬점온도(°C) |
| `minRhm` | double precision |  | 0.1 | 최소 상대습도(%) |
| `minRhmHrmt` | character varying(10) |  | 0.1 | 평균 상대습도 시각(hhmi) |
| `avgRhm` | double precision |  | 0.2 | 평균 상대습도(%) |
| `avgPv` | double precision |  | 0.2 | 평균 증기압(hPa) |
| `avgPa` | double precision |  | 0.2 | 평균 현지기압(hPa) |
| `maxPs` | double precision |  | 0.1 | 최고 해면 기압(hPa) |
| `maxPsHrmt` | character varying(10) |  | 0.1 | 최고 해면기압 시각(hhmi) |
| `minPs` | double precision |  | 0.1 | 최저 해면기압(hPa) |
| `minPsHrmt` | character varying(10) |  | 0.1 | 최저 해면기압 시각(hhmi) |
| `avgPs` | double precision |  | 0.2 | 평균 해면기압(hPa) |
| `ssDur` | double precision |  | 0.0 | 가조시간(hr) |
| `sumSsHr` | double precision |  | 0.3 | 합계 일조 시간(hr) |
| `hr1MaxIcsrHrmt` | character varying(10) |  | 49.1 | 1시간 최다 일사 시각(hhmi) |
| `hr1MaxIcsr` | double precision |  | 49.1 | 1시간 최다 일사량(MJ/m2) |
| `sumGsr` | double precision |  | 49.1 | 합계 일사량(MJ/m2) |
| `ddMefs` | double precision |  | 99.3 | 일 최심신적설(cm) |
| `ddMefsHrmt` | character varying(10) |  | 99.4 | 일 최심신적설 시각(hhmi) |
| `ddMes` | double precision |  | 99.0 | 일 최심적설(cm) |
| `ddMesHrmt` | character varying(10) |  | 99.0 | 일 최심적설 시각(hhmi) |
| `sumDpthFhsc` | double precision |  | 99.3 | 합계 3시간 신적설(cm) |
| `avgTca` | double precision |  | 23.0 | 평균 전운량(10분위) |
| `avgLmac` | double precision |  | 25.3 | 평균 중하층운량(10분위) |
| `avgTs` | double precision |  | 0.1 | 평균 지면온도(°C) |
| `minTg` | double precision |  | 0.1 | 최저 초상온도(°C) |
| `avgCm5Te` | double precision |  | 70.6 | 평균 5cm 지중온도(°C) |
| `avgCm10Te` | double precision |  | 70.6 | 평균 10cm 지중온도(°C) |
| `avgCm20Te` | double precision |  | 70.6 | 평균 20cm 지중온도(°C) |
| `avgCm30Te` | double precision |  | 70.6 | 평균 30cm 지중온도(°C) |
| `avgM05Te` | double precision |  | 85.9 | 0.5m 지중온도(°C) |
| `avgM10Te` | double precision |  | 85.9 | 1.0m 지중온도(°C) |
| `avgM15Te` | double precision |  | 85.9 | 1.5m 지중온도(°C) |
| `avgM30Te` | double precision |  | 85.9 | 3.0m 지중온도(°C) |
| `avgM50Te` | double precision |  | 85.9 | 5.0m 지중온도(°C) |
| `sumLrgEv` | double precision |  | 54.1 | 합계 대형증발량(mm) |
| `sumSmlEv` | double precision |  | 53.1 | 합계 소형증발량(mm) |
| `n99Rn` | double precision |  | 91.4 | 9-9강수(mm) |
| `iscs` | text |  | 79.0 | 일기현상 |
| `sumFogDur` | double precision |  | 98.3 | 안개 계속 시간(hr) |
| `created_at` | timestamp without time zone | ● | 0.0 | 데이터베이스 적재 시각 |

**인덱스**

- `uq_weather_asos_raw_station_date`
- `weather_asos_raw_pkey`

## `econ_daily_raw`

| | |
|---|---|
| 역할 | M2·EPU·PPI 등 거시 변수. |
| 출처·생성 | 한국은행 ECOS · KDI · `fetch_economic_variables.py --load-db` |
| 규모 | 4,199행 · 14컬럼 |
| PK | `(id)` |
| UNIQUE | `(dt)` |

**모델에서 제외돼 있습니다 (ablation 확정).** 세 타겟 모두 손실이 음수였습니다.

월·분기 단위로 갱신되어 일별 예측에서는 같은 값이 한 달간 반복되고, 모델이 이를
**시점 식별자로 오용**합니다. 제거 후 `best_iter` 가 33~51 → 102~140 으로 3배
올랐습니다 — 경제 변수가 조기 종료를 유발하고 있었다는 뜻입니다.

테이블은 유지합니다. `train.py --keep-all` 로 언제든 되살릴 수 있습니다.

| 컬럼 | 타입 | NN | 결측% | 설명 |
|---|---|:--:|--:|---|
| `id` | bigint | ● | 0.0 | DB 내부 식별자 |
| `dt` | character varying(10) | ● | 0.0 | 날짜. 관측 기준일(YYYY-MM-DD) |
| `gov_bond_3y_rt` | numeric(12,8) |  | 0.0 | 국고채 3년물 금리. 국고채 3년 유통수익률(연 %) |
| `gov_bond_obs_dt` | character varying(10) |  | 0.0 | 국고채 실제관측일. 해당 값이 실제 시장에서 관측된 날짜(YYYY-MM-DD) |
| `gov_bond_obs_yn` | smallint |  | 0.0 | 국고채 당일관측여부. 1=해당 날짜 실제 관측, 0=직전 거래일 값 전달 |
| `m2_yoy_rt` | numeric(12,8) |  | 0.0 | M2 전년동월비. M2 평잔 원계열 전년동월비 증가율(%) |
| `m2_ref_mon` | character varying(6) |  | 0.0 | M2 기준월. 적용된 M2 통계 기준월(YYYYMM) |
| `epu_idx` | numeric(15,8) |  | 0.0 | 경제정책불확실성지수(EPU). KDI 한국 경제정책 불확실성지수 |
| `epu_ref_mon` | character varying(6) |  | 0.0 | EPU 기준월. 적용된 경제정책불확실성지수 통계 기준월(YYYYMM) |
| `ppi_idx` | numeric(12,8) |  | 0.0 | 생산자물가지수(PPI) 총지수. 2020=100 |
| `ppi_ref_mon` | character varying(6) |  | 0.0 | 생산자물가지수 기준월. 적용된 생산자물가지수 통계 기준월(YYYYMM) |
| `cpi_yoy_rt` | numeric(12,8) |  | 0.0 | 소비자물가 전년동월비. 소비자물가지수 총지수 전년동월비(%) |
| `cpi_ref_mon` | character varying(6) |  | 0.0 | 소비자물가지수 기준월. 적용된 소비자물가지수 통계 기준월(YYYYMM) |
| `created_at` | timestamp without time zone | ● | 0.0 | 데이터베이스 적재 시각 |

**인덱스**

- `econ_daily_raw_pkey`
- `uq_econ_daily_raw_dt`

## `krei_price_monthly_raw`

| | |
|---|---|
| 역할 | 월별 도매가격 동향. |
| 출처·생성 | KREI 농업관측월보 |
| 규모 | 3,005행 · 16컬럼 |
| PK | `(id)` |

미사용.

| 컬럼 | 타입 | NN | 결측% | 설명 |
|---|---|:--:|--:|---|
| `id` | bigint | ● | 0.0 | DB 내부 식별자 |
| `item_nm_kr` | character varying(20) |  | 0.0 | 품목명 |
| `item_cd_en` | character varying(20) |  | 0.0 | 품목 영문 코드 |
| `crop_yr` | integer |  | 0.0 | 연산(수확연도) |
| `crop_yr_start_mon` | integer |  | 0.0 | 연산 시작월. 품목별로 시작월이 다를 수 있음 |
| `grade_cd` | character varying(10) |  | 0.0 | 등급. 상품, 중품, NA 등 |
| `price_dt` | character varying(7) |  | 0.0 | 가격 기준 연월(YYYY-MM) |
| `price_krw` | numeric(10,0) |  | 0.0 | 도매가격 |
| `price_unit` | character varying(20) |  | 0.0 | 가격 단위. 품목별로 원/kg 등 단위가 다를 수 있음 |
| `src_nm` | character varying(50) |  | 100.0 | 가격 자료 출처 |
| `report_mon` | character varying(7) |  | 0.0 | 해당 수치가 수록된 KREI 농업관측월보 발행월(YYYY-MM) |
| `created_at` | timestamp without time zone | ● | 0.0 | 데이터베이스 적재 시각 |
| `월` | character varying(50) |  | 100.0 |  |
| `품목` | character varying(50) |  | 100.0 |  |
| `도매가격(원)` | real |  | 100.0 |  |
| `단위` | character varying(50) |  | 100.0 |  |

## `krei_production_yearly_raw`

| | |
|---|---|
| 역할 | 생산전망·재배면적 증감률. |
| 출처·생성 | KREI 농업관측월보 |
| 규모 | 127행 · 16컬럼 |
| PK | `(id)` |

`crop_area_yoy_rt` 의 원천이지만 **모델 입력에서 제외**돼 있습니다.

결측 75%. 품목별로는 배추·무·마늘 100%, 양파 1.4%라 사실상 "양파에만 있는
feature" 가 되어 품목 식별자로 오용될 위험이 있습니다.

`yoy_chg_rt` 가 VARCHAR 이고 `"-8.1~-5.2"` 같은 **범위값**이 섞여 있습니다.
한국 통계 관행상 `△` 는 음수이므로 파싱 시 치환이 필요합니다.

| 컬럼 | 타입 | NN | 결측% | 설명 |
|---|---|:--:|--:|---|
| `id` | bigint | ● | 0.0 | DB 내부 식별자 |
| `item_nm_kr` | character varying(20) |  | 0.0 | 품목명 |
| `item_variety_kr` | character varying(30) |  | 0.0 | 세부 작형 또는 품종명. 가격표의 품목명과 다를 수 있음 |
| `crop_yr` | integer |  | 0.0 | 연산(수확연도) |
| `cult_area_ha` | numeric(10,1) |  | 11.0 | 재배면적(ha) |
| `yield_kg_10a` | character varying(20) |  | 3.1 | 단수(kg/10a). 범위값이 존재할 수 있어 문자열로 저장 |
| `prod_value` | numeric(12,1) |  | 15.0 | 생산량 수치 |
| `prod_unit` | character varying(10) |  | 0.0 | 생산량 단위. 톤 또는 천 톤 등 표마다 다를 수 있으므로 반드시 함께 확인 |
| `yoy_chg_rt` | character varying(20) |  | 72.4 | 전년 대비 증감률(%). 범위값이 존재할 수 있어 문자열로 저장 |
| `normal_yr_chg_rt` | character varying(20) |  | 72.4 | 평년 대비 증감률(%). 범위값이 존재할 수 있어 문자열로 저장 |
| `report_mon` | character varying(7) |  | 0.0 | KREI 농업관측월보 발행월(YYYY-MM) |
| `created_at` | timestamp without time zone | ● | 0.0 | 데이터베이스 적재 시각 |
| `연산` | character varying(50) |  | 100.0 |  |
| `품목` | character varying(50) |  | 100.0 |  |
| `재배면적(ha)` | integer |  | 100.0 |  |
| `생산량(톤)` | integer |  | 100.0 |  |

## `krei_import_monthly_raw`

| | |
|---|---|
| 역할 | 월별 수입 동향. |
| 출처·생성 | KREI 농업관측월보 |
| 규모 | 1,501행 · 11컬럼 |
| PK | `(id)` |

미사용.

| 컬럼 | 타입 | NN | 결측% | 설명 |
|---|---|:--:|--:|---|
| `id` | bigint | ● | 0.0 | DB 내부 식별자 |
| `item_nm_kr` | character varying(20) |  | 0.0 | 품목명 |
| `crop_yr` | integer |  | 0.0 | 연산(수확연도) |
| `import_dt` | character varying(7) |  | 0.0 | 수입 기준 연월(YYYY-MM) |
| `import_vol_ton` | numeric(10,1) |  | 0.0 | 수입량(톤) |
| `import_form_cd` | character varying(20) |  | 0.0 | 수입 형태. 신선, 냉동, 건조 등 |
| `report_mon` | character varying(7) |  | 0.0 | KREI 농업관측월보 발행월(YYYY-MM) |
| `created_at` | timestamp without time zone | ● | 0.0 | 데이터베이스 적재 시각 |
| `월` | character varying(50) |  | 100.0 |  |
| `품목` | character varying(50) |  | 100.0 |  |
| `수입량(톤)` | real |  | 100.0 |  |

## `krei_inventory_yearly_raw`

| | |
|---|---|
| 역할 | 재고 동향. |
| 출처·생성 | KREI 농업관측월보 |
| 규모 | 120행 · 15컬럼 |
| PK | `(id)` |

미사용.

| 컬럼 | 타입 | NN | 결측% | 설명 |
|---|---|:--:|--:|---|
| `id` | bigint | ● | 0.0 | DB 내부 식별자 |
| `item_nm_kr` | character varying(20) |  | 0.0 | 품목명. 재고동향 표가 존재하지 않는 품목도 있음 |
| `crop_yr` | integer |  | 0.0 | 연산(수확연도) |
| `inbound_ton` | numeric(10,1) |  | 0.0 | 입고량(톤). 건고추 등 일부 품목은 원본 표 구조가 다를 수 있음 |
| `outbound_ton` | numeric(10,1) |  | 0.0 | 출고량(톤) |
| `inventory_ton` | numeric(10,1) |  | 0.0 | 재고량(톤) |
| `yoy_chg_rt` | character varying(20) |  | 58.3 | 전년 대비 증감률(%) |
| `normal_yr_chg_rt` | character varying(20) |  | 58.3 | 평년 대비 증감률(%) |
| `report_mon` | character varying(7) |  | 0.0 | KREI 농업관측월보 발행월(YYYY-MM) |
| `created_at` | timestamp without time zone | ● | 0.0 | 데이터베이스 적재 시각 |
| `prod_ton_ref(참고,정식컬럼아님)` | real |  | 100.0 |  |
| `supply_ton_ref(참고,정식컬럼아님)` | real |  | 100.0 |  |
| `기준월` | character varying(50) |  | 100.0 |  |
| `품목` | character varying(50) |  | 100.0 |  |
| `추정재고량(톤)` | integer |  | 100.0 |  |

## `daily_volume_stg`

| | |
|---|---|
| 역할 | 반입량 적재용 스테이징. 현재 0행. |
| 출처·생성 | — |
| 규모 | 0행 · 10컬럼 |

전 컬럼이 `text` 인 임시 테이블입니다. 지금은 `load_daily_volume.py` 가
직접 UPSERT 하므로 **쓰이지 않습니다.** 정리 대상.

| 컬럼 | 타입 | NN | 결측% | 설명 |
|---|---|:--:|--:|---|
| `ymd` | text |  |  | 스테이징(text). 현재 미사용 |
| `item_label` | text |  |  | 스테이징(text). 현재 미사용 |
| `total_ton` | text |  |  | 스테이징(text). 현재 미사용 |
| `top1_raw` | text |  |  | 스테이징(text). 현재 미사용 |
| `top1_ton` | text |  |  | 스테이징(text). 현재 미사용 |
| `top2_raw` | text |  |  | 스테이징(text). 현재 미사용 |
| `top2_ton` | text |  |  | 스테이징(text). 현재 미사용 |
| `etc_ton` | text |  |  | 스테이징(text). 현재 미사용 |
| `mmdd` | text |  |  | 스테이징(text). 현재 미사용 |
| `req_date` | text |  |  | 스테이징(text). 현재 미사용 |

---

# 기준정보 — 규칙·매핑

## `ref_holiday`

| | |
|---|---|
| 역할 | 공휴일 원본. `ref_calendar` 의 입력. |
| 출처·생성 | 한국천문연구원 특일 정보 API · `fetch_holidays.py` |
| 규모 | 264행 · 5컬럼 |
| 범위 | `dt` 2015-01-01 ~ 2028-12-25 |
| PK | `(dt, date_name)` |

**현재연도 +2년까지만 확정됩니다.** 매년 갱신해야 합니다.

임시공휴일·대체공휴일은 지정된 뒤에야 API 에 올라옵니다. 즉 **예측 시점에 알 수
없는 휴일이 원리적으로 존재**합니다. 과거 재현에는 문제가 없고 미래 추론에서만
리드타임이 어긋날 수 있습니다.

5/1 근로자의 날은 법정공휴일이 아니라 API 가 주지 않습니다. 그런데 KAMIS 조사는
쉬므로 `ref_calendar` 에서 규칙으로 따로 넣습니다.

| 컬럼 | 타입 | NN | 결측% | 설명 |
|---|---|:--:|--:|---|
| `dt` | date | ● | 0.0 | 날짜. PK(1) |
| `date_name` | character varying(50) | ● | 0.0 | 공휴일명. PK(2) |
| `date_kind` | character varying(2) |  | 0.0 | 특일 종류 코드 |
| `is_holiday` | boolean | ● | 0.0 | 공휴일 여부 |
| `seq` | smallint |  | 0.0 | 같은 날 순번 |

**인덱스**

- `ref_holiday_dt_idx`
- `ref_holiday_pkey`

## `ref_calendar`

| | |
|---|---|
| 역할 | 달력. **축이 두 개**입니다. |
| 출처·생성 | `25_ref_calendar.sql` |
| 규모 | 5,114행 · 8컬럼 |
| 범위 | `dt` 2015-01-01 ~ 2028-12-31 |
| PK | `(dt)` |

```
is_open    경매 거래일 축   2015~2025  3,348일
is_survey  중도매가 조사일 축          2,700일   ← lead_biz_d 는 이쪽
```

648일 차이는 토요일 544 + 공휴일 약 124 + 12월 첫째 금요일 11 + 역방향 16 입니다.
명절도 하루 어긋납니다 — 경매는 명절 전날 거래하고 당일부터 사흘 쉬는데,
조사는 법정 연휴(D-1~D+1)를 그대로 따릅니다.

**`survey_seq` 가 `lead_biz_d` 의 축입니다.** 미래 대상일을 셀 수 있어야 배치
추론이 가능하고, `predict_input` 이 이 컬럼으로 만들어집니다.

상세는 `예측_달력_테이블_컬럼정의서_v1.md` 참조.

| 컬럼 | 타입 | NN | 결측% | 설명 |
|---|---|:--:|--:|---|
| `dt` | date | ● | 0.0 |  |
| `dow` | integer |  | 0.0 |  |
| `is_open` | boolean |  | 0.0 |  |
| `is_survey` | boolean |  | 0.0 |  |
| `open_reason` | text |  | 83.2 |  |
| `survey_reason` | text |  | 67.1 |  |
| `open_seq` | bigint |  | 0.0 |  |
| `survey_seq` | bigint |  | 0.0 | lead_biz_d 의 축. crop_price_train 의 tmp_px.bn 과 같은 의미 |

**인덱스**

- `ref_calendar_open_idx`
- `ref_calendar_pkey`
- `ref_calendar_survey_idx`

## `ref_calendar_override`

| | |
|---|---|
| 역할 | 규칙으로 설명 안 되는 휴장·개장. |
| 출처·생성 | 수작업 (`25_ref_calendar.sql` INSERT) |
| 규모 | 18행 · 4컬럼 |
| 범위 | `dt` 2015-08-14 ~ 2026-12-12 |
| PK | `(dt, axis)` |

**과거의 정답은 게시판이 아니라 `auction_prices_daily` 실거래일입니다.**
"규칙상 개장인데 거래 0건" 을 뽑아 14건을 찾았고 오탐 0 · 미탐 0 입니다.

다만 그 방법은 **원리적으로 과거만** 채웁니다. 2026-08-24 에 공사 공고를 대조해
미래 시범휴업 3건(10/10 · 11/7 · 12/12)이 개장으로 잡혀 있던 것을 찾아
넣었습니다 — `note` 에 `미검증` 이라고 표시돼 있고, 날짜가 지나면 실거래일로
확정합니다. `watch_garak_notice.py` 로 월 1회 후보를 확인하세요.

| 컬럼 | 타입 | NN | 결측% | 설명 |
|---|---|:--:|--:|---|
| `dt` | date | ● | 0.0 | 날짜. PK(1) |
| `axis` | text | ● | 0.0 | open(경매) 또는 survey(조사). PK(2) |
| `is_on` | boolean | ● | 0.0 | 그 축에서 여는가 |
| `note` | text |  | 0.0 | 사유. '미검증' 은 공고 기준이라 실거래 대조 전 |

**CHECK 제약**

- `CHECK ((axis = ANY (ARRAY['open'::text, 'survey'::text])))`

## `ref_school_day`

| | |
|---|---|
| 역할 | 서울 초·중·고 개교율(급식 수요 대리변수). |
| 출처·생성 | NEIS 학사일정 · `build_school_day.py` |
| 규모 | 5,114행 · 3컬럼 |
| 범위 | `dt` 2015-01-01 ~ 2028-12-31 |
| PK | `(dt)` |

**3폴드 ablation 에서 기각됐습니다.** 모델 입력이 아닙니다.
테이블은 재실험 비용을 아끼려고 남겼습니다.

`school_open_ratio` 는 실측이 아니라 **연중 프로파일**입니다. NEIS 개방일이
2019-04 이고 API 가 최근 2개 학년도만 보유해 실측이 2020-09 부터라, 학습 구간
커버리지가 36.6% 였습니다. 결측을 그대로 두면 "2020-09 이전인가" 가 시점
식별자가 됩니다.

`school_open_ratio_meas`(실측)는 참고·검증용입니다. **학습에 쓰지 마세요.**

| 컬럼 | 타입 | NN | 결측% | 설명 |
|---|---|:--:|--:|---|
| `dt` | date | ● | 0.0 |  |
| `school_open_ratio` | numeric(6,4) | ● | 0.0 | 연중 프로파일 개교율 0~1. 전 구간 동일 규칙이라 미래 리드타임에도 값이 있다. 모델 입력은 이 컬럼 |
| `school_open_ratio_meas` | numeric(6,4) |  | 58.6 | NEIS 실측 개교율. 2020-09 이후만 존재. 참고·검증용 — 학습에 쓰면 결측이 시점 식별자가 된다 |

## `ref_item_station`

| | |
|---|---|
| 역할 | 품목 × 월 → 주산지 ASOS 관측소 매핑. |
| 출처·생성 | 수작업 + 실측 대조 |
| 규모 | 17행 · 8컬럼 |
| PK | `(item_nm, mon_from)` |

**도메인 추정으로 시작했다가 실측 대조에서 배추 4개월 · 무 6개월 · 마늘 12개월이
틀렸습니다.** 마늘은 "난지형/한지형이 계절 교대한다"는 작물학 상식이 유통
실태(저장 출하로 연중 창녕 지배)와 달랐습니다.

가장 중요했던 건 10월 오류입니다. 김장 직전 가격이 형성되는 구간을 남부(해남)
기상으로 보고 있었으나 실제 출하는 고랭지에서 이루어집니다.

**`stn_nm` 은 `weather_asos_raw."stnNm"` 과 정확히 일치해야 합니다.**
어긋나면 기상 feature 가 통째로 NULL 이 됩니다 — v5 검증 [2] 가 잡습니다.

매핑 변경은 SQL 이 아니라 이 테이블을 고쳐 반영합니다.

| 컬럼 | 타입 | NN | 결측% | 설명 |
|---|---|:--:|--:|---|
| `item_nm` | character varying(50) | ● | 0.0 |  |
| `mon_from` | smallint | ● | 0.0 |  |
| `mon_to` | smallint | ● | 0.0 |  |
| `stn_nm` | character varying(50) | ● | 0.0 | weather_asos_raw."stnNm" 과 정확히 일치해야 함 |
| `crop_type` | character varying(50) |  | 0.0 |  |
| `gdd_base_c` | numeric(4,1) | ● | 0.0 | 작물별 GDD 기준온도(℃). 정의서 §10.6 |
| `note` | text |  | 0.0 |  |
| `krei_variety_pat` | character varying(50) |  | 5.9 |  |

**CHECK 제약**

- `CHECK (((mon_from >= 1) AND (mon_from <= 12)))`
- `CHECK (((mon_to >= 1) AND (mon_to <= 12)))`

---

# 학습·추론

## `crop_price_train`

| | |
|---|---|
| 역할 | 학습 테이블. **1행 = (기준일 × 품목 × 리드타임 1~18)** |
| 출처·생성 | `DBEAVER_run_v5.sql` |
| 규모 | 198,721행 · 46컬럼 |
| 범위 | `base_dt` 2015-01-05 ~ 2026-08-21 |
| PK | `(id)` |
| UNIQUE | `(base_dt, item_nm, lead_biz_d)` |

**유효 표본은 행수가 아니라 고유 기준일입니다.** 190,243행이지만 한 기준일이
최대 72행으로 복제되므로 실질 표본은 2,698개, 학습 구간(2017~2022)은 1,475개입니다.
`min_data_in_leaf` 같은 **행 기준** 파라미터를 잡을 때 이걸 놓치면 안 됩니다.

타겟 3종은 서로의 정답이므로 모두 입력에서 제외합니다.

**앵커 변환**을 씁니다. `y = log(target / anchor)` 로 학습하고
`pred = anchor × exp(model_output)` 으로 되돌립니다. 역변환을 빼먹으면
0.049 같은 로그비율이 가격으로 저장됩니다.

컬럼별 상세·결측 현황·데이터 계보는 **`crop_price_train_컬럼정의서_v2.md`** 참조.

| 컬럼 | 타입 | NN | 결측% | 설명 |
|---|---|:--:|--:|---|
| `id` | bigint | ● | 0.0 | DB 내부 식별자 |
| `base_dt` | date | ● | 0.0 | 기준일. 예측을 수행하는 영업일이며 매일 새벽 배치 기준 |
| `item_nm` | character varying(100) | ● | 0.0 | 품목명. 글로벌 모델의 categorical feature |
| `lead_biz_d` | smallint | ● | 0.0 | 리드타임(영업일). 기준일로부터 예측 대상일까지의 영업일 수(1~18) |
| `target_dt` | date | ● | 0.0 | 대상일. 기준일에서 리드타임 영업일만큼 이동한 예측 대상 날짜. 파생용이며 모델 feature로 사용하지 않음 |
| `target_whsl_prc` | numeric(15,3) |  | 0.0 | 대상일 중도매인 판매가(원/kg). 가락도매·상품. 사용자=식당·급식 구매담당 (주력) |
| `whsl_prc_lag1` | numeric(15,3) |  | 0.0 | 직전 영업일 중도매인 판매가(원/kg) |
| `whsl_prc_lag3` | numeric(15,3) |  | 0.1 | 3영업일 전 중도매인 판매가(원/kg) |
| `whsl_prc_lag7` | numeric(15,3) |  | 0.2 | 7영업일 전 중도매인 판매가(원/kg) |
| `whsl_prc_prev_yr` | numeric(15,3) |  | 9.2 | 대상일 -365일 ±3일 중도매인 판매가 평균(원/kg) |
| `whsl_prc_avg7` | numeric(15,3) |  | 0.0 | 최근 7영업일 평균 중도매인 판매가(원/kg) |
| `whsl_prc_avg14` | numeric(15,3) |  | 0.0 | 최근 14영업일 평균 중도매인 판매가(원/kg) |
| `whsl_prc_std7` | numeric(15,3) |  | 0.0 | 최근 7영업일 중도매인 판매가 표준편차. 단기 가격 변동성 |
| `arr_qty_lag1` | numeric(15,3) |  | 0.0 | 기준일 시점에 알 수 있는 최신 반입량(톤). req_date <= base_dt 조건의 as-of 조회 |
| `arr_qty_avg7` | numeric(15,3) |  | 0.0 | 최근 7영업일 평균 반입량(톤) |
| `arr_qty_prev_yr` | numeric(15,3) |  | 8.4 | 작년 대상일 시점 반입량. 대상일 기준 전년 동일 시기 ±3일 평균 |
| `prod_area_stn_nm` | character varying(50) |  | 0.0 | 주산지 관측소명. 품목과 작형/시기에 따라 주산지 매핑 규칙으로 결정 |
| `prod_area_temp_avg_lag1` | numeric(10,3) |  | 0.2 | 주산지 어제 평균기온(℃). 해당 품목 주산지의 직전일 평균기온 |
| `prod_area_rain_sum7` | numeric(12,3) |  | 0.2 | 주산지 최근 7일 누적강수량(mm). 단기 강수 충격 및 수확·출하 지연 반영 |
| `prod_area_rain_sum30` | numeric(12,3) |  | 0.2 | 주산지 최근 30일 누적강수량(mm). 생육기간 누적 강수 영향 반영 |
| `prod_area_gdd_sum30` | numeric(12,3) |  | 0.2 | 주산지 최근 30일 적산온도(GDD, ℃·일). Σ max(일평균기온-작물별 기준온도, 0) |
| `prod_area_fcst_temp_avg10` | numeric(10,3) |  | 100.0 | 기준일 당시 발표된 주산지 중기예보 10일 평균기온(℃). 중기예보 RAW 확보 전까지 NULL |
| `market_temp_avg_lag1` | numeric(10,3) |  | 0.0 | 소비지 어제 평균기온(℃). 서울 가락시장 기준으로 수송 및 단기 수요 영향 보조 변수 |
| `target_dow` | character varying(10) |  | 0.0 | 대상일 요일. 요일별 물량 및 가격 효과 반영용 categorical feature |
| `kimchi_season_yn` | smallint |  | 0.0 | 대상일 김장시즌 여부. 1=김장시즌, 0=비김장시즌 |
| `holiday_remain_d` | integer |  | 0.0 | 대상일 기준 다음 설 또는 추석까지 남은 일수 |
| `market_closed_lag1_yn` | smallint |  | 0.0 | 어제 시장 휴장 여부. 1=휴장, 0=개장 |
| `crop_area_yoy_rt` | numeric(10,3) |  | 74.6 | 재배면적 전년 대비 증감률(%). 발표일 이후부터 적용 |
| `m2_growth_rt` | numeric(12,8) |  | 0.7 | M2 증가율(%). 월간 경제 변수로 실제 발표일 이후부터 적용 |
| `epu_idx` | numeric(15,8) |  | 0.7 | 경제정책불확실성지수(EPU). 유의성 실험 후 feature 유지 여부 판단 |
| `ppi_idx` | numeric(15,8) |  | 0.7 | 생산자물가지수(PPI). 월간 경제 변수로 실제 발표일 이후부터 적용 |
| `created_at` | timestamp without time zone | ● | 0.0 | 데이터베이스 적재 시각 |
| `rtl_prc_lag1` | numeric(15,3) |  | 22.6 | 직전 소매가(원/단위). se_cd=01 · 서울(sgg_cd=1101) 한정. 품목별로 단위가 다르므로 스프레드 파생 금지. target_rtl_prc 와 같은 필터여야 함 |
| `prod_area_clim_temp_avg10` | numeric(10,3) |  | 26.8 | 주산지 평년 기온(℃). 대상 구간(기준일+1~+10일)의 과거 연도 같은 날짜대 평균. 기준일 이전 연도만 사용 |
| `prod_area_clim_yr_cnt` | smallint |  | 0.0 | 평년값 계산에 사용된 과거 연도 수. 3년 미만이면 평년값을 NULL 처리 |
| `arr_qty_asof_date` | date |  | 0.0 | arr_qty_lag1 이 실제로 어느 날짜의 물량인지. 지연 추적용 |
| `arr_top1_region` | character varying(20) |  | 3.0 | 해당 시점 1위 산지. 주산지 매핑 검증 및 산지 전환 감지용 |
| `target_rtl_prc` | numeric(15,3) |  | 22.7 | 대상일 소매가(원/단위) · 서울(sgg_cd=1101) 한정. 앵커 rtl_prc_lag1 과 동일 기준. 배추는 포기 단위이므로 kg 인 다른 타겟과 스케일 다름 |
| `auc_prc_lag1` | numeric(15,3) |  | 0.0 | 직전 영업일 경매 낙찰가(원/kg). 서울가락·특등급. 중도매가의 선행지표 후보 |
| `auc_prc_lag3` | numeric(15,3) |  | 0.1 |  |
| `auc_prc_avg7` | numeric(15,3) |  | 0.0 |  |
| `auc_prc_spread_lag1` | numeric(10,4) |  | 0.0 | 직전 영업일 일중 스프레드 (max-min)/avg. 낙찰가 편차가 클수록 시장 불안정 |
| `auc_vol_lag1` | numeric(18,3) |  | 0.0 |  |
| `auc_whsl_ratio_lag1` | numeric(10,4) |  | 0.0 | 중도매가 / 경락가 배수. 유통 마진 수준. 급등기에 축소되는 경향 |
| `target_auc_prc` | numeric(15,3) |  | 3.3 | 대상일 경매 낙찰가(원/kg). 서울가락·특등급. 사용자=농가·산지유통인 |
| `school_open_ratio` | numeric(6,4) |  | 0.0 | 대상일의 서울 초·중·고 개교율 0~1 (급식 수요 대리변수). ref_school_day 의 연중 프로파일. 기준일이 아니라 대상일 기준 — 학사일정은 미리 공시되므로 미래 리드타임도 알 수 있어 누출이 아님 |

**CHECK 제약**

- `CHECK (((lead_biz_d >= 1) AND (lead_biz_d <= 18)))`
- `CHECK (((kimchi_season_yn IS NULL) OR (kimchi_season_yn = ANY (ARRAY[0, 1]))))`
- `CHECK (((market_closed_lag1_yn IS NULL) OR (market_closed_lag1_yn = ANY (ARRAY[0, 1]))))`

**인덱스**

- `crop_price_train_pkey`
- `uq_crop_price_train`

## `predict_input`

| | |
|---|---|
| 역할 | 추론 입력. `crop_price_train` 과 같은 feature, 타겟은 없음. |
| 출처·생성 | `DBEAVER_run_v5.sql` STEP 8 |
| 규모 | 2,160행 · 44컬럼 |
| 범위 | `base_dt` 2025-11-18 ~ 2026-08-24 |

`crop_price_train` 은 **타겟이 있는 행만** 담습니다. 대상일 가격이 있는 행만
조인하기 때문에 미래 기준일 행이 원리적으로 생기지 않고, `predict.py` 를 돌릴
입력이 없었습니다.

STEP 8 은 같은 feature 계산을 그대로 쓰되 **대상일만 달력에서 셉니다.**

```sql
-- crop_price_train  대상일 = tmp_px 에 값이 있는 날            (미래 불가)
-- predict_input     대상일 = ref_calendar.survey_seq + 리드타임 (미래 가능)
```

feature UPDATE 는 STEP 3·4·5 원문을 복제한 것이라 갈라지면 학습과 추론의
계산식이 달라집니다. **검증 [14]** 가 겹치는 구간을 전 컬럼 대조합니다.

**신선도 가드**가 있습니다. 기준일이 3일 이상 뒤처지면 WARNING 을 냅니다 —
몇 달 전 가격을 앵커로 "오늘의 예측"을 내놓는 것이 가장 나쁜 사고이고,
그건 예외가 아니라 그럴듯한 숫자로 나오기 때문입니다.

| 컬럼 | 타입 | NN | 결측% | 설명 |
|---|---|:--:|--:|---|
| `base_dt` | date | ● | 0.0 | 기준일. 예측을 수행하는 영업일이며 매일 새벽 배치 기준  ↩ |
| `item_nm` | character varying(100) | ● | 0.0 | 품목명. 글로벌 모델의 categorical feature  ↩ |
| `lead_biz_d` | smallint | ● | 0.0 | 리드타임(영업일). 기준일로부터 예측 대상일까지의 영업일 수(1~18)  ↩ |
| `target_dt` | date | ● | 0.0 | 대상일. 기준일에서 리드타임 영업일만큼 이동한 예측 대상 날짜. 파생용이며 모델 feature로 사용하지 않음  ↩ |
| `target_whsl_prc` | numeric(15,3) |  | 100.0 | 대상일 중도매인 판매가(원/kg). 가락도매·상품. 사용자=식당·급식 구매담당 (주력)  ↩ |
| `whsl_prc_lag1` | numeric(15,3) |  | 0.0 | 직전 영업일 중도매인 판매가(원/kg)  ↩ |
| `whsl_prc_lag3` | numeric(15,3) |  | 0.0 | 3영업일 전 중도매인 판매가(원/kg)  ↩ |
| `whsl_prc_lag7` | numeric(15,3) |  | 0.0 | 7영업일 전 중도매인 판매가(원/kg)  ↩ |
| `whsl_prc_prev_yr` | numeric(15,3) |  | 25.0 | 대상일 -365일 ±3일 중도매인 판매가 평균(원/kg)  ↩ |
| `whsl_prc_avg7` | numeric(15,3) |  | 0.0 | 최근 7영업일 평균 중도매인 판매가(원/kg)  ↩ |
| `whsl_prc_avg14` | numeric(15,3) |  | 0.0 | 최근 14영업일 평균 중도매인 판매가(원/kg)  ↩ |
| `whsl_prc_std7` | numeric(15,3) |  | 0.0 | 최근 7영업일 중도매인 판매가 표준편차. 단기 가격 변동성  ↩ |
| `arr_qty_lag1` | numeric(15,3) |  | 0.0 | 기준일 시점에 알 수 있는 최신 반입량(톤). req_date <= base_dt 조건의 as-of 조회  ↩ |
| `arr_qty_avg7` | numeric(15,3) |  | 0.0 | 최근 7영업일 평균 반입량(톤)  ↩ |
| `arr_qty_prev_yr` | numeric(15,3) |  | 0.0 | 작년 대상일 시점 반입량. 대상일 기준 전년 동일 시기 ±3일 평균  ↩ |
| `prod_area_stn_nm` | character varying(50) |  | 0.0 | 주산지 관측소명. 품목과 작형/시기에 따라 주산지 매핑 규칙으로 결정  ↩ |
| `prod_area_temp_avg_lag1` | numeric(10,3) |  | 0.0 | 주산지 어제 평균기온(℃). 해당 품목 주산지의 직전일 평균기온  ↩ |
| `prod_area_rain_sum7` | numeric(12,3) |  | 0.0 | 주산지 최근 7일 누적강수량(mm). 단기 강수 충격 및 수확·출하 지연 반영  ↩ |
| `prod_area_rain_sum30` | numeric(12,3) |  | 0.0 | 주산지 최근 30일 누적강수량(mm). 생육기간 누적 강수 영향 반영  ↩ |
| `prod_area_gdd_sum30` | numeric(12,3) |  | 0.0 | 주산지 최근 30일 적산온도(GDD, ℃·일). Σ max(일평균기온-작물별 기준온도, 0)  ↩ |
| `prod_area_fcst_temp_avg10` | numeric(10,3) |  | 100.0 | 기준일 당시 발표된 주산지 중기예보 10일 평균기온(℃). 중기예보 RAW 확보 전까지 NULL  ↩ |
| `market_temp_avg_lag1` | numeric(10,3) |  | 0.0 | 소비지 어제 평균기온(℃). 서울 가락시장 기준으로 수송 및 단기 수요 영향 보조 변수  ↩ |
| `target_dow` | character varying(10) |  | 0.0 | 대상일 요일. 요일별 물량 및 가격 효과 반영용 categorical feature  ↩ |
| `kimchi_season_yn` | smallint |  | 0.0 | 대상일 김장시즌 여부. 1=김장시즌, 0=비김장시즌  ↩ |
| `holiday_remain_d` | integer |  | 0.0 | 대상일 기준 다음 설 또는 추석까지 남은 일수  ↩ |
| `market_closed_lag1_yn` | smallint |  | 0.0 | 어제 시장 휴장 여부. 1=휴장, 0=개장  ↩ |
| `crop_area_yoy_rt` | numeric(10,3) |  | 75.0 | 재배면적 전년 대비 증감률(%). 발표일 이후부터 적용  ↩ |
| `m2_growth_rt` | numeric(12,8) |  | 75.0 | M2 증가율(%). 월간 경제 변수로 실제 발표일 이후부터 적용  ↩ |
| `epu_idx` | numeric(15,8) |  | 75.0 | 경제정책불확실성지수(EPU). 유의성 실험 후 feature 유지 여부 판단  ↩ |
| `ppi_idx` | numeric(15,8) |  | 75.0 | 생산자물가지수(PPI). 월간 경제 변수로 실제 발표일 이후부터 적용  ↩ |
| `rtl_prc_lag1` | numeric(15,3) |  | 25.0 | 직전 소매가(원/단위). se_cd=01 · 서울(sgg_cd=1101) 한정. 품목별로 단위가 다르므로 스프레드 파생 금지. target_rtl_prc 와 같은 필터여야 함  ↩ |
| `prod_area_clim_temp_avg10` | numeric(10,3) |  | 6.9 | 주산지 평년 기온(℃). 대상 구간(기준일+1~+10일)의 과거 연도 같은 날짜대 평균. 기준일 이전 연도만 사용  ↩ |
| `prod_area_clim_yr_cnt` | smallint |  | 6.9 | 평년값 계산에 사용된 과거 연도 수. 3년 미만이면 평년값을 NULL 처리  ↩ |
| `arr_qty_asof_date` | date |  | 0.0 | arr_qty_lag1 이 실제로 어느 날짜의 물량인지. 지연 추적용  ↩ |
| `arr_top1_region` | character varying(20) |  | 0.8 | 해당 시점 1위 산지. 주산지 매핑 검증 및 산지 전환 감지용  ↩ |
| `target_rtl_prc` | numeric(15,3) |  | 100.0 | 대상일 소매가(원/단위) · 서울(sgg_cd=1101) 한정. 앵커 rtl_prc_lag1 과 동일 기준. 배추는 포기 단위이므로 kg 인 다른 타겟과 스케일 다름  ↩ |
| `auc_prc_lag1` | numeric(15,3) |  | 0.0 | 직전 영업일 경매 낙찰가(원/kg). 서울가락·특등급. 중도매가의 선행지표 후보  ↩ |
| `auc_prc_lag3` | numeric(15,3) |  | 0.0 |  |
| `auc_prc_avg7` | numeric(15,3) |  | 0.0 |  |
| `auc_prc_spread_lag1` | numeric(10,4) |  | 0.0 | 직전 영업일 일중 스프레드 (max-min)/avg. 낙찰가 편차가 클수록 시장 불안정  ↩ |
| `auc_vol_lag1` | numeric(18,3) |  | 0.0 |  |
| `auc_whsl_ratio_lag1` | numeric(10,4) |  | 0.0 | 중도매가 / 경락가 배수. 유통 마진 수준. 급등기에 축소되는 경향  ↩ |
| `target_auc_prc` | numeric(15,3) |  | 100.0 | 대상일 경매 낙찰가(원/kg). 서울가락·특등급. 사용자=농가·산지유통인  ↩ |
| `school_open_ratio` | numeric(6,4) |  | 0.0 | 대상일의 서울 초·중·고 개교율 0~1 (급식 수요 대리변수). ref_school_day 의 연중 프로파일. 기준일이 아니라 대상일 기준 — 학사일정은 미리 공시되므로 미래 리드타임도 알 수 있어 누출이 아님  ↩ |

**인덱스**

- `ix_predict_input`

---

# 예측 산출 — 다른 파트 계약

## `prediction_log`

| | |
|---|---|
| 역할 | 예측 저장. **다른 파트에 넘기는 계약 테이블.** |
| 출처·생성 | `28_prediction_log.sql` → 이후 배치 |
| 규모 | 107,082행 · 20컬럼 |
| 범위 | `base_dt` 2025-11-25 ~ 2026-08-24 |
| PK | `(id)` |
| UNIQUE | `(base_dt, item_nm, lead_biz_d, target_kind, model_ver)` |

현재 값은 더미지만 구조는 운영과 같습니다. 상세는 `예측_달력_테이블_컬럼정의서_v1.md` 참조.

| 컬럼 | 타입 | NN | 결측% | 설명 |
|---|---|:--:|--:|---|
| `id` | bigint | ● | 0.0 |  |
| `base_dt` | date | ● | 0.0 |  |
| `target_dt` | date | ● | 0.0 |  |
| `item_nm` | character varying(20) | ● | 0.0 |  |
| `lead_biz_d` | smallint | ● | 0.0 |  |
| `target_kind` | character varying(4) | ● | 0.0 |  |
| `unit` | character varying(10) | ● | 0.0 | auc/whsl 은 원/kg, rtl 은 원/단위(배추는 포기). 타겟 간 직접 비교 금지 |
| `anchor_prc` | numeric(15,3) | ● | 0.0 | 기준일 시점에 알 수 있는 최신 실제가. baseline("어제 가격 그대로")이자 예측의 기준값 |
| `pred_prc` | numeric(15,3) | ● | 0.0 |  |
| `pred_lo` | numeric(15,3) |  | 0.0 | 예측 구간 하단 = pred_prc * ref_prediction_band.ratio_q10. 검증 구간 실측 기준 10건 중 8건이 lo~hi 안 |
| `pred_hi` | numeric(15,3) |  | 0.0 | 예측 구간 상단 = pred_prc * ref_prediction_band.ratio_q90 |
| `seed_spread` | numeric(15,3) |  | 0.0 | 시드 앙상블 표준편차. 모델 내부 흔들림이며 예측 구간이 아니다 (실측 1.6~1.8%, 실제 오차는 10~17%). 구간은 pred_lo/hi 를 쓸 것 |
| `gated` | boolean | ● | 0.0 | true 면 모델을 쓰지 않고 anchor_prc 를 그대로 내보낸 것. lead_biz_d 1~2 가 해당 |
| `model_ver` | character varying(40) | ● | 0.0 |  |
| `model_created_at` | timestamp without time zone |  | 0.0 |  |
| `created_at` | timestamp without time zone | ● | 0.0 |  |
| `actual_prc` | numeric(15,3) |  | 1.2 |  |
| `abs_pct_err` | numeric(10,4) |  | 1.2 |  |
| `scored_at` | timestamp without time zone |  | 1.2 |  |
| `gate_reason` | text |  | 72.5 | gated=true 인 사유. lead_time(LT<3) · quality(조합이 baseline 이하) · quality:unknown(품질표에 없는 조합) · lead_time+quality. gated=false 면 NULL |

**CHECK 제약**

- `CHECK (((target_kind)::text = ANY ((ARRAY['auc'::character varying, 'whsl'::character varying, 'rtl'::character varying])::text[])))`
- `CHECK (((lead_biz_d >= 1) AND (lead_biz_d <= 18)))`
- `CHECK (((pred_prc > (0)::numeric) AND (anchor_prc > (0)::numeric)))`

**인덱스**

- `prediction_log_base_idx`
- `prediction_log_open_idx`
- `prediction_log_pkey`
- `prediction_log_target_idx`
- `prediction_log_uk`

## `ref_prediction_band`

| | |
|---|---|
| 역할 | 예측 구간(`pred_lo`/`pred_hi`) 근거. |
| 출처·생성 | `export_band_sql.py` → `27_ref_prediction_band.sql` |
| 규모 | 162행 · 6컬럼 |
| PK | `(target_kind, item_nm, lead_biz_d)` |

모델 재학습 시 갱신합니다. 상세는 `예측_달력_테이블_컬럼정의서_v1.md` 참조.

| 컬럼 | 타입 | NN | 결측% | 설명 |
|---|---|:--:|--:|---|
| `target_kind` | character varying(4) | ● | 0.0 |  |
| `item_nm` | character varying(20) | ● | 0.0 |  |
| `lead_biz_d` | smallint | ● | 0.0 |  |
| `ratio_q10` | numeric(8,4) | ● | 0.0 |  |
| `ratio_q50` | numeric(8,4) | ● | 0.0 |  |
| `ratio_q90` | numeric(8,4) | ● | 0.0 |  |

## `ref_prediction_quality`

| | |
|---|---|
| 역할 | 품목 × 타겟 조합별 실측 신뢰도. **`predict.py` 가 이 표를 보고 게이트합니다.** |
| 출처·생성 | `28_prediction_log.sql` + `33_prediction_quality_v2.sql` |
| 규모 | 9행 · 13컬럼 |
| PK | `(target_kind, item_nm)` |

**판정 규칙 (v2, 2026-08-25)**

```
use_recommended = 세 구간 중 2개 이상에서 +1%p 초과
                  검증2023 · 테스트2024~25 · 운영2026(prediction_log 채점)
```

한 구간으로 정하지 않습니다. 2026-06~07 45일만 보고 "여섯 중 다섯이 음수" 로
결론 냈다가 8개월로 넓히자 뒤집힌 일이 있었습니다. feature 판정의 2폴드
규칙(`CLAUDE.md` 5.7)과 같은 원리입니다.

`+1%p` 문턱을 둔 이유: 중도매 무의 운영 실측이 +0.2% 인데 테스트는 −13.2%
였습니다. 0 근처를 "개선" 으로 세면 노이즈가 판정을 뒤집습니다.

**현재 9조합 중 7 통과.** 차단은 경락 양파·중도매 무입니다. 경락 양파는
2026 에 +21.0%(7/8개월)로 좋지만 통과 구간이 1개뿐이라 유지합니다 —
2026 만 다른 이유를 모르는 채로 풀지 않습니다.

`n_pass_windows` 와 `use_recommended` 가 어긋나면 안 됩니다. 손으로 고친
흔적을 잡으려고 `33_...sql` 의 검증 [2] 가 매번 대조합니다.

| 컬럼 | 타입 | NN | 결측% | 설명 |
|---|---|:--:|--:|---|
| `target_kind` | character varying(4) | ● | 0.0 |  |
| `item_nm` | character varying(20) | ● | 0.0 |  |
| `improve_valid_pct` | numeric(6,1) |  | 0.0 |  |
| `improve_test_pct` | numeric(6,1) |  | 0.0 |  |
| `dir_acc_pct` | numeric(6,1) |  | 44.4 |  |
| `use_recommended` | boolean | ● | 0.0 | 모델을 쓸지 여부. false 면 predict.py 가 앵커로 폴백하고 gate_reason=quality 를 남긴다. 판정 규칙: 세 구간 중 2개 이상에서 +1%p 초과 |
| `note` | text |  | 0.0 |  |
| `improve_live_pct` | numeric(6,1) |  | 0.0 | 운영 실측 개선율(%). prediction_log 채점 기준. 게이트 해제 상태에서 측정한 모델 자체의 성능 |
| `live_window` | text |  | 0.0 | 운영 실측을 잰 구간과 모델. 조건 없는 수치는 기록하지 않는다 |
| `live_pos_months` | smallint |  | 0.0 | 운영 구간에서 개선율이 양수였던 달 수. 총합이 양수라도 이 값이 낮으면 불안정하다 |
| `live_n_months` | smallint |  | 0.0 |  |
| `n_pass_windows` | smallint |  | 0.0 | 세 구간(검증·테스트·운영) 중 +1%p 를 넘은 구간 수. 2 이상이면 use_recommended=true |
| `updated_at` | timestamp with time zone |  | 0.0 |  |

---

# 운영 — 배치 이력

## `batch_run`

| | |
|---|---|
| 역할 | 배치 실행 이력. 한 행 = 실행 한 번. |
| 출처·생성 | `35_batch_run.sql` · `run_batch.py` 가 실행마다 INSERT |
| 규모 | 3행 · 9컬럼 |
| PK | `(run_id)` |

**왜 DB 에 남기나.** 자동 실행을 걸면 사람이 로그 파일을 안 봅니다.
**"자동화했는데 실은 3일째 안 돌고 있었다"** 가 가장 흔한 사고입니다.
DB 에 있으면 대시보드·알림·조회가 전부 같은 곳을 봅니다.

`status` 는 넷입니다.

```
running   진행 중 (또는 비정상 종료로 갱신되지 못함)
ok        전부 성공
partial   수집 일부 실패했으나 나머지는 진행 (--strict 없이)
fail      중단됨
```

**기록 실패가 배치를 멈추지 않습니다.** 배치가 본업이므로 `run_begin` 이
실패하면 경고만 찍고 계속합니다.

| 컬럼 | 타입 | NN | 결측% | 설명 |
|---|---|:--:|--:|---|
| `run_id` | bigint | ● | 0.0 |  |
| `started_at` | timestamp with time zone | ● | 0.0 |  |
| `finished_at` | timestamp with time zone |  | 0.0 |  |
| `status` | text | ● | 0.0 | running=진행중 · ok=전부 성공 · partial=수집 일부 실패했으나 계속 · fail=중단 |
| `host` | text |  | 0.0 |  |
| `stages_plan` | text |  | 0.0 | 이번 실행에서 돌리기로 한 단계 목록. --stages·--skip 이 반영된 결과 |
| `n_ok` | smallint | ● | 0.0 |  |
| `n_fail` | smallint | ● | 0.0 |  |
| `note` | text |  | 33.3 |  |

**CHECK 제약**

- `CHECK ((status = ANY (ARRAY['running'::text, 'ok'::text, 'fail'::text, 'partial'::text])))`

**인덱스**

- `batch_run_pkey`
- `ix_batch_run_started`

## `batch_run_stage`

| | |
|---|---|
| 역할 | 배치 단계별 결과. 실행당 최대 9행. |
| 출처·생성 | `35_batch_run.sql` · `run_batch.py` |
| 규모 | 3행 · 6컬럼 |
| PK | `(run_id, seq)` |

`message` 는 각 단계 출력의 **마지막 몇 줄**입니다. 전체 로그는
`진행기록/batch_logs/batch_YYYY-MM-DD.log` 에 있습니다.

`duration_s` 로 어느 단계가 느려지는지 추적할 수 있습니다.
실측: 수집 5종 ~4분 · rebuild ~80초 · 추론·적재·채점 ~6초.

| 컬럼 | 타입 | NN | 결측% | 설명 |
|---|---|:--:|--:|---|
| `run_id` | bigint | ● | 0.0 |  |
| `seq` | smallint | ● | 0.0 |  |
| `stage` | text | ● | 0.0 |  |
| `ok` | boolean | ● | 0.0 |  |
| `duration_s` | numeric(10,1) |  | 0.0 |  |
| `message` | text |  | 0.0 |  |

---

# 뷰

테이블이 아니라 **조회용 정의**입니다. 저장 공간을 쓰지 않고, 볼 때마다 아래 SQL 이 실행됩니다.

## `v_batch_latest`

최근 배치 실행 요약. 실패 단계가 한 줄로 붙습니다. 대시보드 패널용

| 컬럼 | 타입 |
|---|---|
| `run_id` | bigint |
| `started_at` | timestamp with time zone |
| `finished_at` | timestamp with time zone |
| `소요_초` | integer |
| `status` | text |
| `n_ok` | smallint |
| `n_fail` | smallint |
| `실패단계` | text |
| `host` | text |

```sql
SELECT run_id,
    started_at,
    finished_at,
    round(EXTRACT(epoch FROM finished_at - started_at))::integer AS "소요_초",
    status,
    n_ok,
    n_fail,
    ( SELECT string_agg(s.stage, ', '::text ORDER BY s.seq) AS string_agg
           FROM batch_run_stage s
          WHERE s.run_id = r.run_id AND NOT s.ok) AS "실패단계",
    host
   FROM batch_run r
  ORDER BY started_at DESC;
```

## `v_data_freshness`

원천별 신선도. **실시간 계산**이라 배치가 멈춰도 신선도는 계속 정확합니다. `crop_price_train`·`predict_input` 은 `f_table_freshness()` 로 동적 조회합니다 — 뷰가 직접 참조하면 v5 의 DROP 이 막혀 배치가 죽습니다 (2026-08-25 실제로 겪음)

| 컬럼 | 타입 |
|---|---|
| `원천` | text |
| `최신` | date |
| `지연일` | integer |
| `행수` | bigint |

```sql
SELECT '경락가'::text AS "원천",
    max(auction_prices_daily.auction_date) AS "최신",
    CURRENT_DATE - max(auction_prices_daily.auction_date) AS "지연일",
    count(*) AS "행수"
   FROM auction_prices_daily
UNION ALL
 SELECT '도·소매'::text AS "원천",
    max(veg_daily_price_raw.exmn_ymd) AS "최신",
    CURRENT_DATE - max(veg_daily_price_raw.exmn_ymd) AS "지연일",
    count(*) AS "행수"
   FROM veg_daily_price_raw
  WHERE veg_daily_price_raw.item_cd::text = ANY (ARRAY['211'::character varying, '231'::character varying, '245'::character varying]::text[])
UNION ALL
 SELECT '반입량'::text AS "원천",
    max(daily_volume.base_date) AS "최신",
    CURRENT_DATE - max(daily_volume.base_date) AS "지연일",
    count(*) AS "행수"
   FROM daily_volume
UNION ALL
 SELECT '기상'::text AS "원천",
    max(weather_asos_raw.tm::text)::date AS "최신",
    CURRENT_DATE - max(weather_asos_raw.tm::text)::date AS "지연일",
    count(*) AS "행수"
   FROM weather_asos_raw
UNION ALL
 SELECT '경제'::text AS "원천",
    max(econ_daily_raw.dt::text)::date AS "최신",
    CURRENT_DATE - max(econ_daily_raw.dt::text)::date AS "지연일",
    count(*) AS "행수"
   FROM econ_daily_raw
UNION ALL
 SELECT f_table_freshness."원천",
    f_table_freshness."최신",
    f_table_freshness."지연일",
    f_table_freshness."행수"
   FROM f_table_freshness('crop_price_train'::text, 'base_dt'::text, '학습테이블'::text) f_table_freshness("원천", "최신", "지연일", "행수")
UNION ALL
 SELECT f_table_freshness."원천",
    f_table_freshness."최신",
    f_table_freshness."지연일",
    f_table_freshness."행수"
   FROM f_table_freshness('predict_input'::text, 'base_dt'::text, '추론입력'::text) f_table_freshness("원천", "최신", "지연일", "행수");
```

## `v_prediction_latest`

소비자용 예측 조회. 다른 파트가 이걸 봅니다. 상세는 `예측_달력_테이블_컬럼정의서_v1.md`

| 컬럼 | 타입 |
|---|---|
| `target_dt` | date |
| `item_nm` | character varying(20) |
| `target_kind` | character varying(4) |
| `unit` | character varying(10) |
| `base_dt` | date |
| `lead_biz_d` | smallint |
| `anchor_prc` | numeric(15,3) |
| `pred_prc` | numeric(15,3) |
| `pred_lo` | numeric(15,3) |
| `pred_hi` | numeric(15,3) |
| `gated` | boolean |
| `use_recommended` | boolean |
| `prc_to_use` | numeric(15,3) |
| `improve_test_pct` | numeric(6,1) |
| `note` | text |
| `model_ver` | character varying(40) |
| `actual_prc` | numeric(15,3) |

```sql
SELECT DISTINCT ON (p.target_dt, p.item_nm, p.target_kind) p.target_dt,
    p.item_nm,
    p.target_kind,
    p.unit,
    p.base_dt,
    p.lead_biz_d,
    p.anchor_prc,
    p.pred_prc,
    p.pred_lo,
    p.pred_hi,
    p.gated,
    q.use_recommended,
        CASE
            WHEN q.use_recommended THEN p.pred_prc
            ELSE p.anchor_prc
        END AS prc_to_use,
    q.improve_test_pct,
    q.note,
    p.model_ver,
    p.actual_prc
   FROM prediction_log p
     LEFT JOIN ref_prediction_quality q ON q.target_kind::text = p.target_kind::text AND q.item_nm::text = p.item_nm::text
  ORDER BY p.target_dt, p.item_nm, p.target_kind, p.base_dt DESC;
```
