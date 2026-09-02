# -*- coding: utf-8 -*-
"""
DB 전체 테이블 정의서 생성
==========================
살아 있는 DB 에서 스키마를 읽어 `DB/DB_전체_테이블_정의서_v3.md` 를 만듭니다.

    python gen_table_doc.py                 # 정의서 생성
    python gen_table_doc.py --emit-comments # 빠진 COMMENT 를 채우는 SQL 도 생성

왜 손으로 안 쓰나
-----------------
`9개_테이블_정의서_v2_2.md`(2026-08-14)가 손으로 쓴 것인데, 열흘 만에
어긋났습니다.

    · `crop_price_train` 절이 경락가 단일 타겟 시절 것 (33컬럼 → 실제 46)
    · `daily_volume` 이 "1,438행 · 배추만" (실제 18,265행 · 5품목)
    · `daily_volume.mmdd` 는 문서에만 있고 실제 컬럼에 없음
    · `auction_prices_daily` · `ref_*` 7종 · `predict_input` 누락

**컬럼 표는 사람이 유지할 수 없습니다.** 스키마에서 뽑고, 사람은 아래
NOTES/DESC 에 "왜 이렇게 생겼나" 만 적습니다.

구성
----
NOTES  테이블별 역할·주의. 사람이 씁니다
DESC   DB COMMENT 가 없는 컬럼의 설명. 사람이 씁니다
       --emit-comments 로 이 내용을 DB 에 밀어 넣는 SQL 을 만들 수 있습니다
그 외  전부 DB 에서 읽습니다
"""
import argparse
import os
import sys
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "DB" / "DB_전체_테이블_정의서_v3.md"
OUT_SQL = ROOT / "SQL" / "31_table_comments.sql"

# ── 테이블 분류와 역할 ────────────────────────────────────────────────
GROUPS = [
    ("RAW — 수집 원본", [
        "veg_daily_price_raw", "auction_prices_daily", "daily_volume",
        "weather_asos_raw", "econ_daily_raw",
        "krei_price_monthly_raw", "krei_production_yearly_raw",
        "krei_import_monthly_raw", "krei_inventory_yearly_raw",
        "daily_volume_stg",
    ]),
    ("기준정보 — 규칙·매핑", [
        "ref_holiday", "ref_calendar", "ref_calendar_override",
        "ref_school_day", "ref_item_station",
    ]),
    ("학습·추론", ["crop_price_train", "predict_input"]),
    ("예측 산출 — 다른 파트 계약", [
        "prediction_log", "ref_prediction_band", "ref_prediction_quality",
    ]),
    ("운영 — 배치 이력", ["batch_run", "batch_run_stage"]),
]

NOTES = {
 "veg_daily_price_raw": dict(
  src="aT 오픈API `B552845/perDay/price` · `collect_kamis.py` (증분 · DB 직행)",
  role="중도매가·소매가의 원천. 시장 × 품종 × 등급 × 조사구분의 다차원 격자다.",
  note="""**`se_cd=02`(중도매)는 경매 낙찰가가 아닙니다.** 중도매인이 소상인에게 파는
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
학습·검증 구간에서 달라집니다.**""",
  codes="""| 구분 | 코드 |
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
`collect_kamis.py` 가 이 함정에 걸려 "신규 0행" 으로 잘못 보고했습니다."""),

 "auction_prices_daily": dict(
  src="공공데이터포털 `전국 공영도매시장 경매원천정보` · `auction_collector` 패키지",
  role="경락가(경매 낙찰가)의 원천. 전국 32개 도매시장.",
  note="""**`target_auc_prc` 와 `auc_prc_*` 의 유일한 출처입니다.**
학습에는 서울가락(`wholesale_market_code=110001`) · 특등급(`grade_code=11`) 만 씁니다.

가격 3종(평균·최저·최고)이 다 있어 **일중 스프레드**(`auc_prc_spread_lag1`)를
만들 수 있습니다. 품질 저하·공급 불안의 대리 지표입니다.

`grade_code` 만 NULL 을 허용합니다 — 원천에서 등급 미상인 경우가 있습니다.

수집기가 증분·캐시·검증·DB적재를 갖춘 유일한 물건입니다. 나머지 수집기의
참고 모델로 삼으세요."""),

 "daily_volume": dict(
  src="농넷 수급일보 스크래핑 · `농넷에서 일일산출량 적재.py --load-db`",
  role="품목별 일자별 반입 물량과 상위 산지. 공급 충격 신호.",
  note="""가격만으로는 공급 충격의 **방향**을 알 수 없습니다. 반입량은 가격과 반대로
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
그 이전 구간은 덮어쓰지 않습니다 — **오래된 값이 바뀌면 정정이 아니라 사고**입니다."""),

 "weather_asos_raw": dict(
  src="기상청 ASOS 일자료 · `fetch_asos.py --load-db`",
  role="주산지·소비지 기상. 95개 관측소.",
  note="""**64컬럼 중 4개만 씁니다** — `stnNm` · `tm` · `avgTa` · `sumRn`.
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
다른 API 에서 되는 키도 403 `SERVICE_KEY_IS_NOT_REGISTERED_ERROR` 를 냅니다."""),

 "econ_daily_raw": dict(
  src="한국은행 ECOS · KDI · `fetch_economic_variables.py --load-db`",
  role="M2·EPU·PPI 등 거시 변수.",
  note="""**모델에서 제외돼 있습니다 (ablation 확정).** 세 타겟 모두 손실이 음수였습니다.

월·분기 단위로 갱신되어 일별 예측에서는 같은 값이 한 달간 반복되고, 모델이 이를
**시점 식별자로 오용**합니다. 제거 후 `best_iter` 가 33~51 → 102~140 으로 3배
올랐습니다 — 경제 변수가 조기 종료를 유발하고 있었다는 뜻입니다.

테이블은 유지합니다. `train.py --keep-all` 로 언제든 되살릴 수 있습니다."""),

 "krei_price_monthly_raw": dict(src="KREI 농업관측월보", role="월별 도매가격 동향.", note="미사용."),
 "krei_production_yearly_raw": dict(
  src="KREI 농업관측월보", role="생산전망·재배면적 증감률.",
  note="""`crop_area_yoy_rt` 의 원천이지만 **모델 입력에서 제외**돼 있습니다.

결측 75%. 품목별로는 배추·무·마늘 100%, 양파 1.4%라 사실상 "양파에만 있는
feature" 가 되어 품목 식별자로 오용될 위험이 있습니다.

`yoy_chg_rt` 가 VARCHAR 이고 `"-8.1~-5.2"` 같은 **범위값**이 섞여 있습니다.
한국 통계 관행상 `△` 는 음수이므로 파싱 시 치환이 필요합니다."""),
 "krei_import_monthly_raw": dict(src="KREI 농업관측월보", role="월별 수입 동향.", note="미사용."),
 "krei_inventory_yearly_raw": dict(src="KREI 농업관측월보", role="재고 동향.", note="미사용."),

 "daily_volume_stg": dict(
  src="—", role="반입량 적재용 스테이징. 현재 0행.",
  note="""전 컬럼이 `text` 인 임시 테이블입니다. 지금은 `load_daily_volume.py` 가
직접 UPSERT 하므로 **쓰이지 않습니다.** 정리 대상."""),

 "ref_holiday": dict(
  src="한국천문연구원 특일 정보 API · `fetch_holidays.py`",
  role="공휴일 원본. `ref_calendar` 의 입력.",
  note="""**현재연도 +2년까지만 확정됩니다.** 매년 갱신해야 합니다.

임시공휴일·대체공휴일은 지정된 뒤에야 API 에 올라옵니다. 즉 **예측 시점에 알 수
없는 휴일이 원리적으로 존재**합니다. 과거 재현에는 문제가 없고 미래 추론에서만
리드타임이 어긋날 수 있습니다.

5/1 근로자의 날은 법정공휴일이 아니라 API 가 주지 않습니다. 그런데 KAMIS 조사는
쉬므로 `ref_calendar` 에서 규칙으로 따로 넣습니다."""),

 "ref_calendar": dict(
  src="`25_ref_calendar.sql`", role="달력. **축이 두 개**입니다.",
  note="""```
is_open    경매 거래일 축   2015~2025  3,348일
is_survey  중도매가 조사일 축          2,700일   ← lead_biz_d 는 이쪽
```

648일 차이는 토요일 544 + 공휴일 약 124 + 12월 첫째 금요일 11 + 역방향 16 입니다.
명절도 하루 어긋납니다 — 경매는 명절 전날 거래하고 당일부터 사흘 쉬는데,
조사는 법정 연휴(D-1~D+1)를 그대로 따릅니다.

**`survey_seq` 가 `lead_biz_d` 의 축입니다.** 미래 대상일을 셀 수 있어야 배치
추론이 가능하고, `predict_input` 이 이 컬럼으로 만들어집니다.

상세는 `예측_달력_테이블_컬럼정의서_v1.md` 참조."""),

 "ref_calendar_override": dict(
  src="수작업 (`25_ref_calendar.sql` INSERT)", role="규칙으로 설명 안 되는 휴장·개장.",
  note="""**과거의 정답은 게시판이 아니라 `auction_prices_daily` 실거래일입니다.**
"규칙상 개장인데 거래 0건" 을 뽑아 14건을 찾았고 오탐 0 · 미탐 0 입니다.

다만 그 방법은 **원리적으로 과거만** 채웁니다. 2026-08-24 에 공사 공고를 대조해
미래 시범휴업 3건(10/10 · 11/7 · 12/12)이 개장으로 잡혀 있던 것을 찾아
넣었습니다 — `note` 에 `미검증` 이라고 표시돼 있고, 날짜가 지나면 실거래일로
확정합니다. `watch_garak_notice.py` 로 월 1회 후보를 확인하세요."""),

 "ref_school_day": dict(
  src="NEIS 학사일정 · `build_school_day.py`", role="서울 초·중·고 개교율(급식 수요 대리변수).",
  note="""**3폴드 ablation 에서 기각됐습니다.** 모델 입력이 아닙니다.
테이블은 재실험 비용을 아끼려고 남겼습니다.

`school_open_ratio` 는 실측이 아니라 **연중 프로파일**입니다. NEIS 개방일이
2019-04 이고 API 가 최근 2개 학년도만 보유해 실측이 2020-09 부터라, 학습 구간
커버리지가 36.6% 였습니다. 결측을 그대로 두면 "2020-09 이전인가" 가 시점
식별자가 됩니다.

`school_open_ratio_meas`(실측)는 참고·검증용입니다. **학습에 쓰지 마세요.**"""),

 "ref_item_station": dict(
  src="수작업 + 실측 대조", role="품목 × 월 → 주산지 ASOS 관측소 매핑.",
  note="""**도메인 추정으로 시작했다가 실측 대조에서 배추 4개월 · 무 6개월 · 마늘 12개월이
틀렸습니다.** 마늘은 "난지형/한지형이 계절 교대한다"는 작물학 상식이 유통
실태(저장 출하로 연중 창녕 지배)와 달랐습니다.

가장 중요했던 건 10월 오류입니다. 김장 직전 가격이 형성되는 구간을 남부(해남)
기상으로 보고 있었으나 실제 출하는 고랭지에서 이루어집니다.

**`stn_nm` 은 `weather_asos_raw."stnNm"` 과 정확히 일치해야 합니다.**
어긋나면 기상 feature 가 통째로 NULL 이 됩니다 — v5 검증 [2] 가 잡습니다.

매핑 변경은 SQL 이 아니라 이 테이블을 고쳐 반영합니다."""),

 "crop_price_train": dict(
  src="`DBEAVER_run_v5.sql`", role="학습 테이블. **1행 = (기준일 × 품목 × 리드타임 1~18)**",
  note="""**유효 표본은 행수가 아니라 고유 기준일입니다.** 190,243행이지만 한 기준일이
최대 72행으로 복제되므로 실질 표본은 2,698개, 학습 구간(2017~2022)은 1,475개입니다.
`min_data_in_leaf` 같은 **행 기준** 파라미터를 잡을 때 이걸 놓치면 안 됩니다.

타겟 3종은 서로의 정답이므로 모두 입력에서 제외합니다.

**앵커 변환**을 씁니다. `y = log(target / anchor)` 로 학습하고
`pred = anchor × exp(model_output)` 으로 되돌립니다. 역변환을 빼먹으면
0.049 같은 로그비율이 가격으로 저장됩니다.

컬럼별 상세·결측 현황·데이터 계보는 **`crop_price_train_컬럼정의서_v2.md`** 참조."""),

 "predict_input": dict(
  src="`DBEAVER_run_v5.sql` STEP 8", role="추론 입력. `crop_price_train` 과 같은 feature, 타겟은 없음.",
  note="""`crop_price_train` 은 **타겟이 있는 행만** 담습니다. 대상일 가격이 있는 행만
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
그건 예외가 아니라 그럴듯한 숫자로 나오기 때문입니다."""),

 "prediction_log": dict(
  src="`28_prediction_log.sql` → 이후 배치", role="예측 저장. **다른 파트에 넘기는 계약 테이블.**",
  note="현재 값은 더미지만 구조는 운영과 같습니다. 상세는 `예측_달력_테이블_컬럼정의서_v1.md` 참조."),
 "ref_prediction_band": dict(
  src="`export_band_sql.py` → `27_ref_prediction_band.sql`", role="예측 구간(`pred_lo`/`pred_hi`) 근거.",
  note="모델 재학습 시 갱신합니다. 상세는 `예측_달력_테이블_컬럼정의서_v1.md` 참조."),
 "ref_prediction_quality": dict(
  src="`28_prediction_log.sql` + `33_prediction_quality_v2.sql`",
  role="품목 × 타겟 조합별 실측 신뢰도. **`predict.py` 가 이 표를 보고 게이트합니다.**",
  note="""**판정 규칙 (v2, 2026-08-25)**

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
흔적을 잡으려고 `33_...sql` 의 검증 [2] 가 매번 대조합니다."""),

 "batch_run": dict(
  src="`35_batch_run.sql` · `run_batch.py` 가 실행마다 INSERT",
  role="배치 실행 이력. 한 행 = 실행 한 번.",
  note="""**왜 DB 에 남기나.** 자동 실행을 걸면 사람이 로그 파일을 안 봅니다.
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
실패하면 경고만 찍고 계속합니다."""),

 "batch_run_stage": dict(
  src="`35_batch_run.sql` · `run_batch.py`",
  role="배치 단계별 결과. 실행당 최대 9행.",
  note="""`message` 는 각 단계 출력의 **마지막 몇 줄**입니다. 전체 로그는
`진행기록/batch_logs/batch_YYYY-MM-DD.log` 에 있습니다.

`duration_s` 로 어느 단계가 느려지는지 추적할 수 있습니다.
실측: 수집 5종 ~4분 · rebuild ~80초 · 추론·적재·채점 ~6초."""),
}

# ── DB COMMENT 가 없는 컬럼의 설명 ────────────────────────────────────
DESC = {
 "veg_daily_price_raw": {
  "id": "DB 내부 식별자", "exmn_ymd": "조사일자",
  "ctgry_cd": "부류코드 (200=채소류)", "ctgry_nm": "부류명",
  "item_cd": "품목코드. 211 배추 · 231 무 · 241 고추 · 244 피마늘 · 245 양파 · 258 깐마늘. **품목은 이 컬럼으로 센다** (item_nm 은 원천이 바꾼다)", "item_nm": "품목명. **원천이 바꾼다** — 2026 부터 고추→건고추 · 마늘→피마늘. 필터·집계에 쓰지 말 것",
  "vrty_cd": "품종코드. 배추는 작형에 따라 교대", "vrty_nm": "품종명",
  "grd_cd": "등급코드 (04=상품, 05=중품)", "grd_nm": "등급명",
  "se_cd": "조사구분코드 (01 소매 · 02 중도매). 02 는 경락가가 아님", "se_nm": "조사구분명",
  "sgg_cd": "시군구코드 (1101=서울). 소매 필터에 사용", "sgg_nm": "시군구명",
  "mrkt_cd": "시장코드", "mrkt_nm": "시장명 (중도매 필터: 가락도매)",
  "unit": "단위 문자열. kg/포기/g 혼재", "unit_sz": "단위크기. 원/kg 정규화의 분모",
  "exmn_dd_prc": "조사일 가격 (unit/unit_sz 기준)",
  "exmn_dd_cnvs_prc": "조사일 kg 환산가격 (원천 제공값)",
  "orgnl_reg_dt": "원본 등록일시", "created_at": "DB 적재 시각"},
 "auction_prices_daily": {
  "id": "DB 내부 식별자", "auction_date": "경매일자",
  "market_category": "시장 부류", "wholesale_market_code": "도매시장 코드 (110001=서울가락)",
  "wholesale_market_name": "도매시장명", "item_code": "품목코드", "item_name": "품목명",
  "grade_name": "등급명 (11=특)",
  "avg_auction_price_krw_per_kg": "평균 경락가(원/kg). auc_prc_lag1 의 원천",
  "min_auction_price_krw_per_kg": "최저 경락가(원/kg). 일중 스프레드 계산에 사용",
  "max_auction_price_krw_per_kg": "최고 경락가(원/kg). 일중 스프레드 계산에 사용",
  "trade_volume_kg": "거래물량(kg). auc_vol_lag1 의 원천",
  "trade_amount_krw": "거래금액(원)", "package_trade_quantity": "포장 거래수량",
  "source_trade_count": "집계에 사용된 원천 거래 건수", "source": "출처 API 표기"},
 "daily_volume": {
  "base_date": "기준일자. PK(1)", "item_label": "품목명. PK(2)",
  "total_ton": "일 합계 반입량(톤)",
  "top1_region": "1위 산지. 반입 0톤인 날은 NULL", "top1_ton": "1위 산지 물량(톤)",
  "top2_region": "2위 산지", "top2_ton": "2위 산지 물량(톤)",
  "etc_ton": "1·2위 외 기타 산지 합계(톤)",
  "req_date": "수집 일자. base_date 보다 0~7일 늦다. as-of 결합의 기준",
  "top1_raw": "1위 원문. 구분자가 NBSP(U+00A0)", "top2_raw": "2위 원문",
  "loaded_at": "DB 적재 시각"},
 "daily_volume_stg": {c: "스테이징(text). 현재 미사용" for c in
                      ["ymd","item_label","total_ton","top1_raw","top1_ton",
                       "top2_raw","top2_ton","etc_ton","mmdd","req_date"]},
 "ref_holiday": {
  "dt": "날짜. PK(1)", "date_name": "공휴일명. PK(2)",
  "date_kind": "특일 종류 코드", "is_holiday": "공휴일 여부", "seq": "같은 날 순번"},
 "ref_calendar_override": {
  "dt": "날짜. PK(1)", "axis": "open(경매) 또는 survey(조사). PK(2)",
  "is_on": "그 축에서 여는가", "note": "사유. '미검증' 은 공고 기준이라 실거래 대조 전"},
}

# ── 이미 붙어 있지만 틀린 COMMENT ─────────────────────────────────────
#   경락가 단일 타겟 시절의 코멘트가 남아 whsl_* 컬럼을 "경매가" 라고 부른다.
#   중도매가와 경락가는 가격 수준이 다른 별개 계열이라 그대로 두면 오해를 부른다.
#   --emit-comments 가 이것도 함께 고쳐 준다.
FIX = {
 "crop_price_train": {
  "whsl_prc_lag3":  "3영업일 전 중도매인 판매가(원/kg)",
  "whsl_prc_lag7":  "7영업일 전 중도매인 판매가(원/kg)",
  "whsl_prc_avg7":  "최근 7영업일 평균 중도매인 판매가(원/kg)",
  "whsl_prc_avg14": "최근 14영업일 평균 중도매인 판매가(원/kg)",
  "whsl_prc_std7":  "최근 7영업일 중도매인 판매가 표준편차. 단기 가격 변동성",
 },
}


# ── 뷰 설명 (사람이 씀) ───────────────────────────────────────────────
VIEW_NOTES = {
 "v_prediction_latest":
   "소비자용 예측 조회. 다른 파트가 이걸 봅니다. 상세는 `예측_달력_테이블_컬럼정의서_v1.md`",
 "v_batch_latest":
   "최근 배치 실행 요약. 실패 단계가 한 줄로 붙습니다. 대시보드 패널용",
 "v_data_freshness":
   "원천별 신선도. **실시간 계산**이라 배치가 멈춰도 신선도는 계속 정확합니다. "
   "`crop_price_train`·`predict_input` 은 `f_table_freshness()` 로 동적 조회합니다 — "
   "뷰가 직접 참조하면 v5 의 DROP 이 막혀 배치가 죽습니다 (2026-08-25 실제로 겪음)",
}


def q(cur, sql, args=None):
    cur.execute(sql, args or ())
    return cur.fetchall()


def dsn():
    for raw in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            v = v.strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                v = v[1:-1]
            os.environ.setdefault(k.strip(), v)
    u = os.environ.get("DATABASE_URL")
    if not u:
        sys.exit(".env 에 DATABASE_URL 이 없습니다.")
    return u


def table_info(cur, t):
    cols = q(cur, """SELECT a.attname, format_type(a.atttypid,a.atttypmod), a.attnotnull,
                            col_description(a.attrelid,a.attnum),
                            pg_get_expr(d.adbin, d.adrelid)
                     FROM pg_attribute a
                     JOIN pg_class cl ON cl.oid=a.attrelid
                     JOIN pg_namespace n ON n.oid=cl.relnamespace
                     LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum
                     WHERE n.nspname='public' AND cl.relname=%s
                       AND a.attnum>0 AND NOT a.attisdropped
                     ORDER BY a.attnum""", (t,))
    n = q(cur, "SELECT COUNT(*) FROM %s" % t)[0][0]
    nulls = {}
    if n:
        sel = ", ".join('COUNT("%s")' % c[0] for c in cols)
        vals = q(cur, "SELECT %s FROM %s" % (sel, t))[0]
        nulls = {c[0]: round(100 * (1 - v / n), 1) for c, v in zip(cols, vals)}
    rng = None
    for c, ty, *_ in cols:
        if ty in ("date",) or (c in ("tm",) and n):
            try:
                a, b = q(cur, 'SELECT MIN("%s")::text, MAX("%s")::text FROM %s' % (c, c, t))[0]
                rng = (c, str(a)[:10], str(b)[:10])
            except Exception:
                pass
            break
    cons = q(cur, """SELECT c.contype, pg_get_constraintdef(c.oid)
                     FROM pg_constraint c JOIN pg_class cl ON cl.oid=c.conrelid
                     JOIN pg_namespace n ON n.oid=cl.relnamespace
                     WHERE n.nspname='public' AND cl.relname=%s ORDER BY c.contype""", (t,))
    idx = q(cur, "SELECT indexname, indexdef FROM pg_indexes "
                 "WHERE schemaname='public' AND tablename=%s ORDER BY 1", (t,))
    return cols, n, nulls, rng, cons, idx


# predict_input 은 crop_price_train 과 같은 컬럼이므로 설명을 물려받는다.
# 둘을 따로 관리하면 반드시 갈라진다.
INHERIT = {"predict_input": "crop_price_train"}
_inherited = {}


def load_inherited(cur):
    for child, parent in INHERIT.items():
        _inherited[child] = {
            r[0]: r[1] for r in q(cur,
                """SELECT a.attname, col_description(a.attrelid, a.attnum)
                   FROM pg_attribute a JOIN pg_class cl ON cl.oid = a.attrelid
                   JOIN pg_namespace n ON n.oid = cl.relnamespace
                   WHERE n.nspname='public' AND cl.relname=%s
                     AND a.attnum>0 AND NOT a.attisdropped
                     AND col_description(a.attrelid, a.attnum) IS NOT NULL""",
                (parent,))}


def desc_of(t, name, comment):
    # FIX 가 DB COMMENT 보다 우선한다. 붙어 있지만 틀린 설명을 바로잡기 위함이다.
    fix = FIX.get(t, {}).get(name) or FIX.get(INHERIT.get(t, ""), {}).get(name)
    if fix:
        return fix + ("  ↩" if t in INHERIT else "")
    if comment:
        return comment.replace("\n", " ").strip()
    d = DESC.get(t, {}).get(name)
    if d:
        return d
    inh = _inherited.get(t, {}).get(name)
    if inh:
        return inh.replace("\n", " ").strip() + "  ↩"
    return ""


def render(cur, t, level=2):
    cols, n, nulls, rng, cons, idx = table_info(cur, t)
    meta = NOTES.get(t, {})
    L = ["#" * level + " `%s`" % t, ""]
    L.append("| | |")
    L.append("|---|---|")
    L.append("| 역할 | %s |" % meta.get("role", "—"))
    L.append("| 출처·생성 | %s |" % meta.get("src", "—"))
    L.append("| 규모 | %s행 · %d컬럼 |" % (format(n, ","), len(cols)))
    if rng:
        L.append("| 범위 | `%s` %s ~ %s |" % rng)
    pk = [d for c, d in cons if c == "p"]
    if pk:
        L.append("| PK | `%s` |" % pk[0].replace("PRIMARY KEY ", ""))
    uq = [d for c, d in cons if c == "u"]
    if uq:
        L.append("| UNIQUE | `%s` |" % uq[0].replace("UNIQUE ", ""))
    L.append("")

    if meta.get("note"):
        L.append(meta["note"])
        L.append("")

    L.append("| 컬럼 | 타입 | NN | 결측% | 설명 |")
    L.append("|---|---|:--:|--:|---|")
    hide_pct = n == 0
    for name, ty, notnull, comment, default in cols:
        d = desc_of(t, name, comment)
        p = "" if hide_pct else ("%.1f" % nulls.get(name, 0.0))
        L.append("| `%s` | %s | %s | %s | %s |"
                 % (name, ty, "●" if notnull else "", p, d))
    L.append("")

    ck = [d for c, d in cons if c == "c"]
    if ck:
        L.append("**CHECK 제약**")
        L.append("")
        for d in ck:
            L.append("- `%s`" % d)
        L.append("")
    other = [(nm, dd) for nm, dd in idx if not dd.startswith("CREATE UNIQUE INDEX %s" % (pk[0] if pk else "@"))]
    if len(idx) > (1 if pk else 0):
        L.append("**인덱스**")
        L.append("")
        for nm, dd in idx:
            L.append("- `%s`" % nm)
        L.append("")
    if meta.get("codes"):
        L.append("**코드값**")
        L.append("")
        L.append(meta["codes"])
        L.append("")
    return "\n".join(L)


HEAD = """# 원가 캣쳐 — DB 전체 테이블 정의서 v3

> PostgreSQL `cost_catcher_raw` · 테이블 {NT}개 · {NC}컬럼 · 뷰 {NV}개
> 생성 {DATE} · **`DB/gen_table_doc.py` 로 재생성합니다. 손으로 고치지 마세요**

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
| **이 문서** | **전 테이블 {NT}개** | 최신. 생성본 |
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

"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--emit-comments", action="store_true",
                    help="DB COMMENT 가 없는 컬럼에 DESC 를 넣는 SQL 을 생성")
    a = ap.parse_args()

    import datetime
    conn = psycopg.connect(dsn(), connect_timeout=25)
    with conn.cursor() as cur:
        allt = [r[0] for r in q(cur, """SELECT c.relname FROM pg_class c
                                        JOIN pg_namespace n ON n.oid=c.relnamespace
                                        WHERE n.nspname='public' AND c.relkind='r'
                                        ORDER BY 1""")]
        views = q(cur, """SELECT c.relname, obj_description(c.oid),
                                 pg_get_viewdef(c.oid, true)
                          FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                          WHERE n.nspname='public' AND c.relkind='v' ORDER BY 1""")
        listed = [t for _, ts in GROUPS for t in ts]
        missing = [t for t in allt if t not in listed]
        if missing:
            GROUPS.append(("분류 미지정", missing))
            print("  [주의] GROUPS 에 없는 테이블 %s — '분류 미지정' 으로 넣었습니다" % missing)

        ncol = q(cur, """SELECT COUNT(*) FROM pg_attribute a
                         JOIN pg_class c ON c.oid=a.attrelid
                         JOIN pg_namespace n ON n.oid=c.relnamespace
                         WHERE n.nspname='public' AND c.relkind='r'
                           AND a.attnum>0 AND NOT a.attisdropped""")[0][0]
        load_inherited(cur)
        today = datetime.date.today().isoformat()
        parts = [HEAD.replace("{NT}", str(len(allt)))
             .replace("{NC}", str(ncol))
             .replace("{DATE}", today)
             .replace("{NV}", str(len(views)))]

        parts.append("## 테이블 한눈에\n")
        parts.append("| 그룹 | 테이블 | 행수 | 컬럼 | 역할 |")
        parts.append("|---|---|--:|--:|---|")
        for gname, ts in GROUPS:
            for t in ts:
                if t not in allt:
                    continue
                cols, n, *_ = table_info(cur, t)
                parts.append("| %s | `%s` | %s | %d | %s |"
                             % (gname, t, format(n, ","), len(cols),
                                NOTES.get(t, {}).get("role", "—")))
        parts.append("")

        for gname, ts in GROUPS:
            parts.append("---\n")
            parts.append("# %s\n" % gname)
            for t in ts:
                if t in allt:
                    parts.append(render(cur, t, level=2))

        # ── 뷰 ────────────────────────────────────────────────
        #   테이블이 아니라 조회 정의다. 저장 공간을 쓰지 않는다.
        if views:
            parts.append("---\n")
            parts.append("# 뷰\n")
            parts.append("테이블이 아니라 **조회용 정의**입니다. "
                         "저장 공간을 쓰지 않고, 볼 때마다 아래 SQL 이 실행됩니다.\n")
            for vname, vcomment, vdef in views:
                parts.append("## `%s`\n" % vname)
                parts.append((VIEW_NOTES.get(vname) or vcomment or "—") + "\n")
                vcols = q(cur, """SELECT a.attname, format_type(a.atttypid, a.atttypmod)
                                  FROM pg_attribute a JOIN pg_class c ON c.oid = a.attrelid
                                  JOIN pg_namespace n ON n.oid = c.relnamespace
                                  WHERE n.nspname='public' AND c.relname=%s
                                    AND a.attnum > 0 AND NOT a.attisdropped
                                  ORDER BY a.attnum""", (vname,))
                parts.append("| 컬럼 | 타입 |")
                parts.append("|---|---|")
                for cn, ct in vcols:
                    parts.append("| `%s` | %s |" % (cn, ct))
                parts.append("")
                parts.append("```sql")
                parts.append(vdef.strip())
                parts.append("```")
                parts.append("")

        OUT.write_text("\n".join(parts), encoding="utf-8")
        print("생성: %s" % OUT)

        if a.emit_comments:
            lines = ["-- 자동 생성: DB/gen_table_doc.py --emit-comments",
                     "-- COMMENT 가 비어 있는 컬럼에 정의서의 설명을 넣습니다.",
                     "-- 실행해도 데이터는 바뀌지 않습니다 (메타데이터만).", ""]
            cnt = 0
            for t, dmap in FIX.items():
                if t not in allt:
                    continue
                lines.append("-- 정정: 경락가 단일 타겟 시절 코멘트가 남아 있던 컬럼")
                for name, txt in dmap.items():
                    lines.append("COMMENT ON COLUMN %s.%s IS '%s';"
                                 % (t, name, txt.replace("'", "''")))
                    cnt += 1
                lines.append("")
            for t, dmap in DESC.items():
                if t not in allt:
                    continue
                cols, *_ = table_info(cur, t)
                for name, ty, nn, comment, dflt in cols:
                    if comment or name not in dmap:
                        continue
                    lines.append("COMMENT ON COLUMN %s.%s IS '%s';"
                                 % (t, name, dmap[name].replace("'", "''")))
                    cnt += 1
            OUT_SQL.write_text("\n".join(lines) + "\n", encoding="utf-8")
            print("생성: %s  (%d개 COMMENT)" % (OUT_SQL, cnt))
    conn.close()


if __name__ == "__main__":
    main()
