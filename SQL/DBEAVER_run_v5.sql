-- ============================================================================
-- crop_price_train 통합 생성 스크립트  v5.0
--
--   생성 → 경락가 feature → 3-타겟 결합 → 검증까지 한 파일로 처리한다.
--   DBeaver 에서 열고 [Alt+X] (Execute script) 한 번이면 끝난다.
--
-- ▣ 실행 범위
--      품목      배추 · 양파 · 무 · 마늘
--      기준일    2015-01-01 ~ 2025-12-31
--      권장 분할 학습 2019~2022 / 검증 2023 / 테스트 2024~ (봉인)
--
-- ▣ 3-타겟 구조
--      산지 → [경매] → 중도매인 → [판매] → 식당·소매상 → [소매] → 소비자
--               ↑                    ↑                        ↑
--        target_auc_prc      target_whsl_prc          target_rtl_prc
--        (농가·산지유통인)    (구매담당 · 주력)          (소비자)
--
--    타겟마다 짝이 되는 앵커가 있다. 앵커 변환 y=log(target/anchor) 을 쓰므로
--    중도매가 타겟에 경락가 앵커를 쓰면 스케일이 어긋난다.
--        target_auc_prc ↔ auc_prc_lag1
--        target_whsl_prc ↔ whsl_prc_lag1
--        target_rtl_prc ↔ rtl_prc_lag1
--
-- ▣ 처리 순서와 이유
--      STEP -1 선행 조건 확인       ref_calendar 없으면 여기서 멈춘다
--      STEP 0  TRUNCATE            ← 이 시점 이전에 채운 값은 모두 사라진다
--      STEP 1  스키마·기준정보      재적재에 영향을 주므로 앞에 온다
--      STEP 2  feature 생성        본체 (INSERT)
--      STEP 3  평년기온             UPDATE
--      STEP 4  반입량              UPDATE
--      STEP 5  경락가 feature       UPDATE
--      STEP 6  타겟 3종            UPDATE
--      STEP 7  검증
--
-- ▣ v5.0 변경
--   1. 품목 확장 : 배추·양파 → 배추·양파·무·마늘
--   2. 무 매핑 수정  (실측 검증, 평균 일치율 56.5% → 87.7%)
--      월동무가 5월까지 이어지고, 가을무는 강원→전북→제주로 남하한다.
--   3. 마늘 매핑 수정 (실측 검증, 평균 일치율 36.7% → 77.0%)
--      1~12월 경남 창녕군 지배. 저장 출하 품목이라 산지 계절 이동이 없다.
--   4. 경락가 feature 6종 통합 (auction_prices_daily 기반)
--   5. 타겟 3종 통합
--
-- ▣ 선행 조건  ★ 실행 순서가 생겼다 (v5.1)
--      1) 데이터 수집/휴일 달력/ref_holiday.sql   공휴일 (연 1회 갱신)
--      2) SQL/25_ref_calendar.sql                 달력 (조사 축 · 경매 축)
--      3) 이 파일
--
--      lead_biz_d 를 ref_calendar.survey_seq 로 세므로 2)가 없으면 실행되지
--      않는다. 아래 DO 블록이 막는다.
--
--      auction_prices_daily 테이블에 경락가가 적재되어 있어야 한다.
--      없으면 경락가 관련 컬럼이 NULL 이 되나 나머지는 정상 동작한다.
--
-- ▣ 재실행 안전
--      TRUNCATE RESTART IDENTITY 로 시작하므로 몇 번을 실행해도 무방하다.
--      컬럼 추가는 모두 IF NOT EXISTS.
--
-- ▣ 실행 후 반드시 확인 (하단 결과 탭)
--      [2] 관측소 매칭 — temp_null 이 rows 와 같으면 관측소명 불일치 → 학습 금지
--      [3] 누수 검사   — 모든 항목 0
--      [9] 타겟 3종    — 채움률과 가격 위계 (경락 < 중도매 < 소매)
--      [12] 소매 서울기준 — 불일치 0건. 1건이라도 나오면 소매 모델 학습 금지
--      [13] 학사일정   — 결측 0. 방학기 개교율이 학기중보다 낮아야 함
--
-- ▣ 선행 실행 (없으면 STEP -1 이 막거나 경고한다)
--      ref_holiday.sql → 25_ref_calendar.sql → 29_ref_school_day.sql → 이 파일
-- ============================================================================


-- ############################################################
-- ## STEP -1. 선행 조건 확인  (v5.1)
-- ##
-- ##   TRUNCATE 앞에서 막는다. 달력이 없는 채로 지워버리면 복구에
-- ##   재적재가 필요하다.
-- ############################################################
DO $$
DECLARE n int; d date;
BEGIN
    SELECT COUNT(*) INTO n FROM information_schema.tables
     WHERE table_name = 'ref_calendar';
    IF n = 0 THEN
        RAISE EXCEPTION
          'ref_calendar 가 없습니다. SQL/25_ref_calendar.sql 을 먼저 실행하세요. (그 전에 ref_holiday.sql)';
    END IF;
    SELECT COUNT(*) INTO n FROM ref_calendar WHERE is_survey;
    IF n < 2500 THEN
        RAISE EXCEPTION 'ref_calendar 조사일이 %건뿐입니다. 달력 생성이 덜 됐습니다.', n;
    END IF;
    -- 학습 구간 전체 + 리드타임 앞까지 덮는가 (v5.3 — 상한 하드코딩 제거)
    --   달력이 오늘보다 앞서 있어야 미래 대상일(predict_input)을 셀 수 있다.
    SELECT COUNT(*) INTO n FROM ref_calendar
     WHERE dt BETWEEN '2015-01-01' AND CURRENT_DATE;
    IF n < 4000 THEN
        RAISE EXCEPTION 'ref_calendar 가 학습 구간을 다 덮지 않습니다 (%일).', n;
    END IF;
    SELECT MAX(dt) INTO d FROM ref_calendar;
    IF d < CURRENT_DATE + 60 THEN
        RAISE EXCEPTION
          'ref_calendar 가 % 에서 끝납니다. 리드타임 18영업일을 셀 수 없습니다. '
          'fetch_holidays.py → 25_ref_calendar.sql 을 다시 돌리세요.', d;
    END IF;

    -- 경락가 규격 컬럼 (v5.4 · 2026-08-27) ★
    --   STEP 5 의 tmp_auc 가 unit_weight_kg 로 규격을 고른다. 컬럼이 없거나
    --   전부 NULL 이면 **경락가 타겟과 앵커가 통째로 빈다.** 조용히 비는 것이
    --   가장 나쁘므로 여기서 막는다.
    SELECT COUNT(*) INTO n FROM information_schema.columns
     WHERE table_name = 'auction_prices_daily' AND column_name = 'unit_weight_kg';
    IF n = 0 THEN
        RAISE EXCEPTION
          'auction_prices_daily 에 unit_weight_kg 가 없습니다. '
          '경락가 수집기를 v3(규격 분리)로 올리고 재적재하세요. '
          '수집기: 데이터 수집/경락가 수집/auction_collector_handoff';
    END IF;
    SELECT COUNT(*) INTO n FROM auction_prices_daily
     WHERE wholesale_market_code = '110001' AND grade_code = '11'
       AND item_name = '배추' AND unit_weight_kg = 10;
    IF n < 1000 THEN
        RAISE EXCEPTION
          '배추 10kg 규격 행이 %건뿐입니다. 규격별 재적재가 덜 됐습니다. '
          '(구 데이터는 규격이 뭉쳐 있어 unit_weight_kg 가 NULL 입니다)', n;
    END IF;

    -- 학사일정 (v5.2)
    --   없어도 다른 feature 는 멀쩡하므로 중단시키지 않는다. 다만 조용히
    --   school_open_ratio 가 전부 NULL 이 되는 것이 가장 나쁜 결과라 경고를 띄운다.
    SELECT COUNT(*) INTO n FROM information_schema.tables
     WHERE table_name = 'ref_school_day';
    IF n = 0 THEN
        RAISE WARNING
          'ref_school_day 가 없습니다. school_open_ratio 가 전부 NULL 이 됩니다. '
          'SQL/29_ref_school_day.sql 을 실행한 뒤 다시 돌리세요.';
    ELSE
        SELECT COUNT(*) INTO n FROM ref_school_day
         WHERE dt BETWEEN '2015-01-01' AND '2028-12-31';
        IF n < 5000 THEN
            RAISE WARNING 'ref_school_day 가 %일뿐입니다. 전 구간(약 5,114일)을 덮지 않습니다.', n;
        END IF;
    END IF;
END $$;


-- ############################################################
-- ## STEP 0. 기존 데이터 삭제
-- ##
-- ##   RESTART IDENTITY 를 반드시 붙인다.
-- ##   TRUNCATE 단독으로는 행만 지우고 BIGSERIAL 시퀀스는 그대로 남아
-- ##   재실행할 때마다 id 가 이어서 증가한다.
-- ##   (모델 학습에는 영향이 없지만, 재현성 확인과 디버깅이 어려워진다)
-- ############################################################
TRUNCATE crop_price_train RESTART IDENTITY;


-- ############################################################
-- ## 05_alter_rename.sql
-- ############################################################

-- ============================================================================
-- 컬럼명 정정 + 보조 컬럼 추가 (재실행 안전)
--
-- 타겟을 중도매인 판매가로 확정했으므로 auc_*(auction, 경매가) 를
-- whsl_*(wholesale) 로 변경한다. 정의서 §4.4·§4.7: se_cd='02' 는 경락가가 아님.
--
-- 이미 변경된 상태에서 다시 실행해도 오류가 나지 않도록 DO 블록으로 감쌌다.
-- ============================================================================
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN
        SELECT * FROM (VALUES
            ('target_auc_prc',  'target_whsl_prc'),
            ('auc_prc_lag1',    'whsl_prc_lag1'),
            ('auc_prc_lag3',    'whsl_prc_lag3'),
            ('auc_prc_lag7',    'whsl_prc_lag7'),
            ('auc_prc_prev_yr', 'whsl_prc_prev_yr'),
            ('auc_prc_avg7',    'whsl_prc_avg7'),
            ('auc_prc_avg14',   'whsl_prc_avg14'),
            ('auc_prc_std7',    'whsl_prc_std7')
        ) AS t(old_nm, new_nm)
    LOOP
        -- 구 이름이 있고, 새 이름이 아직 없을 때만 변경한다.
        -- v5.0 부터 target_auc_prc·auc_prc_lag1 은 경락가 정식 컬럼이므로
        -- 새 이름이 이미 존재하면 rename 대상이 아니다.
        IF EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='crop_price_train' AND column_name=r.old_nm)
           AND NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='crop_price_train' AND column_name=r.new_nm)
        THEN
            EXECUTE format('ALTER TABLE crop_price_train RENAME COLUMN %I TO %I', r.old_nm, r.new_nm);
            RAISE NOTICE '컬럼명 변경: % -> %', r.old_nm, r.new_nm;
        END IF;
    END LOOP;
END $$;

-- 소매가 보조 feature (유통 마진 스프레드 실험용)
ALTER TABLE crop_price_train ADD COLUMN IF NOT EXISTS rtl_prc_lag1 NUMERIC(15,3);

-- 학사일정 (급식 수요 대리변수) — ref_school_day 참조
ALTER TABLE crop_price_train ADD COLUMN IF NOT EXISTS school_open_ratio NUMERIC(6,4);

COMMENT ON COLUMN crop_price_train.target_whsl_prc IS
  '대상일 중도매인 판매가(원/kg). 출처 veg_daily_price_raw se_cd=02, grd_cd=04, 가락도매. 경락가 아님';
COMMENT ON COLUMN crop_price_train.whsl_prc_lag1 IS '직전 영업일 중도매인 판매가(원/kg)';
COMMENT ON COLUMN crop_price_train.whsl_prc_prev_yr IS '대상일 -365일 ±3일 중도매인 판매가 평균(원/kg)';
COMMENT ON COLUMN crop_price_train.rtl_prc_lag1 IS
  '직전 소매가(원/단위). se_cd=01 · 서울(sgg_cd=1101) 한정. '
  '품목별로 단위가 다르므로 스프레드 파생 금지. target_rtl_prc 와 같은 필터여야 함';
COMMENT ON COLUMN crop_price_train.school_open_ratio IS
  '대상일의 서울 초·중·고 개교율 0~1 (급식 수요 대리변수). ref_school_day 의 연중 프로파일. '
  '기준일이 아니라 대상일 기준 — 학사일정은 미리 공시되므로 미래 리드타임도 알 수 있어 누출이 아님';


-- ############################################################
-- ## 10_alter_clim.sql
-- ############################################################

-- ============================================================================
-- 평년 기온(climatology) 컬럼 추가  v2.4
--
-- 배경: prod_area_fcst_temp_avg10(중기예보)은 소스 RAW 미정의로 100% NULL 이며,
--       과거 시점에 발표됐던 예보는 소급 확보가 불가능하다.
--       관측에서 예보를 역산할 수는 없으나, '그 시기의 평년 기온'은 관측만으로
--       계산 가능하고 기준일 시점에 이미 알 수 있는 정보이므로 누수가 아니다.
--       또한 리드타임이 길어질수록 실제 예보도 평년값에 수렴하므로 정보량 손실이 작다.
--
-- fcst 컬럼은 삭제하지 않는다. 두 값은 담는 정보가 다르다.
--   fcst = 그해 고유 정보(태풍·한파 예보)  → 짧은 리드타임에 유효
--   clim = 계절 평균 정보                  → 긴 리드타임에 유효, 전 기간 채워짐
-- 향후 예보 수집이 붙으면 둘 다 투입해 모델이 리드타임별로 가중치를 잡게 한다.
-- ============================================================================
ALTER TABLE crop_price_train
    ADD COLUMN IF NOT EXISTS prod_area_clim_temp_avg10 NUMERIC(10,3),
    ADD COLUMN IF NOT EXISTS prod_area_clim_yr_cnt     SMALLINT;

COMMENT ON COLUMN crop_price_train.prod_area_clim_temp_avg10 IS
  '주산지 평년 기온(℃). 대상 구간(기준일+1~+10일)의 과거 연도 같은 날짜대 평균. 기준일 이전 연도만 사용';
COMMENT ON COLUMN crop_price_train.prod_area_clim_yr_cnt IS
  '평년값 계산에 사용된 과거 연도 수. 3년 미만이면 평년값을 NULL 처리';
COMMENT ON COLUMN crop_price_train.prod_area_fcst_temp_avg10 IS
  '기준일 당시 발표된 주산지 중기예보 10일 평균기온(℃). 중기예보 RAW 확보 전까지 NULL';


-- ############################################################
-- ## 14_ref_station_v3.sql
-- ############################################################

-- ============================================================================
-- ref_item_station 개정 v3 — daily_volume 실산지 데이터 기반
--
-- 배경: v2 매핑은 도메인 추정으로 작성했으나, daily_volume(2021-05~2025-12)의
--       실제 1·2위 산지 물량을 집계한 결과 4개월이 실제와 달랐다.
--
--   월    v2 매핑    실제 최다 산지(물량)              판정
--   ---   --------   -------------------------------   ----
--   1~4   해남       전남 해남군 (98~100%)             ✓
--   5     해남       충남 예산군 53% > 전남 해남 39%   ✗ 수정
--   6     해남       강원 52%(횡성·평창) 경북 30%      ✗ 수정
--   7~8   대관령     강원 평창군 (86~89%)              ✓
--   9     대관령     강원 강릉시 23,755t > 평창 14,311t ✗ 수정
--   10    해남       강원 평창군 88%                   ✗ 수정
--   11~12 해남       전남 해남군 (70~98%)              ✓
--
-- 10월 오류가 특히 중요하다. 김장 직전 구간을 남부 기상으로 보고 있었으나
-- 실제 출하는 여전히 고랭지에서 이루어진다.
-- ============================================================================

-- KREI 작형 매칭 패턴 컬럼 (v3.1 추가)
--   krei_production_yearly_raw.item_variety_kr 는 같은 report_mon 에 작형별로
--   여러 행이 존재한다(예: 2025-12 에 가을배추 -4.1 / 겨울배추 8.5).
--   대상일의 작형에 맞는 행만 골라야 하므로 정규식 패턴으로 필터한다.
--   표기가 제각각이라("2022년산 겨울배추", "겨울배추(24년산)") LIKE 대신 ~ 사용.
ALTER TABLE ref_item_station ADD COLUMN IF NOT EXISTS krei_variety_pat VARCHAR(50);

TRUNCATE ref_item_station;

INSERT INTO ref_item_station (item_nm, mon_from, mon_to, stn_nm, crop_type, gdd_base_c, krei_variety_pat, note) VALUES
-- ─ 배추 (daily_volume 실측 기반, 2026-08 검증)
('배추',  1,  4, '해남',   '월동배추',       5.0, '겨울|월동',
 '전남 해남군 76~100%. 2위 진도군. 시대 무관 안정'),
('배추',  5,  5, '홍성',   '봄배추(충남)',   5.0, '봄',
 '2020~ 충남 예산군 64%. 2015~19 는 해남 44% 였으나 최근 기준 채택'),
('배추',  6,  6, '대관령', '고랭지 전환기',  5.0, '여름|고랭지',
 '강원 52%(횡성·평창) 경북 30%(문경). 전환기라 산지 분산'),
('배추',  7,  8, '대관령', '고랭지배추',     5.0, '여름|고랭지',
 '강원 평창군 89~92%. 7월은 시대 무관 안정'),
('배추',  9,  9, '강릉',   '고랭지(강릉)',   5.0, '여름|고랭지',
 '강원 강릉시 23,755t로 평창 14,311t 상회'),
('배추', 10, 10, '대관령', '고랭지 후기',    5.0, '가을',
 '강원 평창군 88%. 초기 버전에서 해남으로 잘못 매핑했던 구간'),
('배추', 11, 12, '해남',   '가을·월동배추',  5.0, '가을|겨울|월동',
 '전남 해남군 70~98%. 11월은 강원 춘천 24% 혼재'),

-- ─ 무 (2026-08 실측 검증 — 기존 추정 6개월 오류 수정)
--   기존 평균 일치율 56.5% → 87.7% (+31.1%p)
('무',    1,  5, '제주',   '월동무',         5.0, '겨울|월동',
 '제주 제주시 90~100%. 월동무 시즌이 5월까지 이어짐 (기존 4월부터 전북으로 본 것이 오류)'),
('무',    6,  6, '고창군', '봄무',           5.0, '봄',
 '전북 고창군 58%. 제주→육지 전환기라 산지 분산'),
('무',    7,  9, '대관령', '고랭지무',       5.0, '여름|고랭지',
 '강원 평창군 53~100%. 8~9월은 일치율 100%로 안정'),
('무',   10, 10, '홍천',   '가을무(강원)',   5.0, '가을',
 '강원 홍천군 92%. 기존 제주 매핑은 일치율 0% 였음'),
('무',   11, 11, '고창군', '가을무(전북)',   5.0, '가을',
 '전북 고창군 90%. 강원→전북 남하'),
('무',   12, 12, '제주',   '월동무 시작',    5.0, '겨울|월동',
 '제주 제주시 70%. 12월부터 월동무 시즌 진입'),

-- ─ 양파 (ASOS 무안 지점 부재로 인접 목포 사용)
('양파',  1,  3, '목포',   '중만생종',       5.0, '중만생종',
 '전남 무안군 87~96%'),
('양파',  4,  4, '제주',   '조생종',         5.0, '조생종',
 '제주 제주시 53%(2020~). 조생종 출하기 — 실측 기반 분리'),
('양파',  5, 12, '목포',   '중만생종',       5.0, '중만생종',
 '전남 무안군 98~100%. 연중 가장 안정적인 구간'),

-- ─ 마늘 (2026-08 실측 검증 — 기존 추정 전면 수정)
--   기존 평균 일치율 36.7% → 77.0% (+40.3%p)
--   마늘은 6월 수확 후 1년 내내 저장 출하되므로 산지가 계절 이동하지 않는다.
--   기존 '7~12월 한지형(충남 서산)' 가정은 일치율 0~7% 로 완전히 빗나갔다.
('마늘',  1, 12, '밀양',   '난지형(창녕)',   4.0, NULL,
 '경남 창녕군 59~93% 연중 1위. ASOS 창녕 부재로 인접 밀양 사용 (합천보다 가까움)');

-- 검증: 매핑 관측소가 ASOS에 실재하는가 (0행이어야 정상)
SELECT r.item_nm, r.mon_from, r.stn_nm, '★ ASOS 미존재' AS status
FROM ref_item_station r
WHERE NOT EXISTS (SELECT 1 FROM weather_asos_raw w WHERE w."stnNm" = r.stn_nm);


-- ############################################################
-- ## 09_insert_v2_5.sql
-- ############################################################

-- ============================================================================
-- crop_price_train 적재 SQL  v2.5  (단위 정규화 + 주산지 기준정보 테이블)
--
-- ▣ 타겟: 중도매인 판매가 (se_cd='02', grd_cd='04' 상품), 가락도매 기준, 원/kg
--         경락가 아님 — 정의서 §4.4·§4.7
--
-- ▣ v2.2 → v2.3 변경 (실제 데이터 확인 결과 반영)
--   1. 단위 정규화: exmn_dd_cnvs_prc 를 신뢰하지 않고 exmn_dd_prc / unit_sz 로 직접 계산.
--      실측 결과 환산 규칙이 품목마다 다름 (377,230행 중 32,325행만 환산되어 있음).
--        · 배추 중도매 kg(그물망 3포기) unit_sz=10 → 환산 안 됨
--        · 양파 중도매 kg unit_sz=15/20        → 환산됨
--      또한 양파 중도매는 2017-01~2018-06 구간에 unit_sz=20 이 섞여 있어
--      정규화하지 않으면 해당 구간 가격이 33% 튄다.
--   2. 지역/시장 필터: sgg_cd 대신 mrkt_nm='가락도매' 사용.
--      중도매 시장은 7개이며 가락도매만 2015-01-02~2025-12-31 전 기간 완비(11,666행).
--      남포동건어물(4행, 2025-02-13 단일일)은 이 필터로 자동 제외됨.
--   3. 강수량: sumRn 이 NULL 62.2% / 0 이 8.5% 로 혼재. ASOS 가 무강수일에
--      빈 값을 주는 경우가 있어 FEATURE 단계에서 COALESCE(sumRn,0) 적용.
--      (RAW 는 정의서 §14.3 원칙대로 원형 보존)
--   4. crop_area_yoy_rt: KREI 4종이 모두 2025-03~2025-12 만 존재.
--      학습기간 11년 중 10개월에만 값이 있어 사실상 사용 불가 → 결합은 유지하되
--      모델 feature 에서는 제외 권장. NULL 비율을 반드시 확인할 것.
--
--   5. 주산지 매핑을 ref_item_station 기준정보 테이블로 분리 (하드코딩 제거).
--      실측 ASOS 95개 관측소 목록으로 11개 매핑 전건 존재 확인.
--
-- ▣ 여전히 NULL: arr_qty_* 3종(반입량 RAW 미정의), prod_area_fcst_temp_avg10(중기예보 미정의)
-- ============================================================================

-- 적재 대상 기준일 범위. 이 범위의 행만 crop_price_train 에 들어간다.
-- 주의: 원천 시계열(tmp_px)은 범위 제한을 두지 않는다. lag·rolling·전년앵커
--       계산에 from_dt 이전 데이터가 필요하기 때문이다.
-- 대상 품목 (현재 배추 단독. 확장 시 이 값 변경 또는 IN 조건으로 수정)

-- 선행 조건: 13_ref_item_station.sql 실행 (품목×작형 → 관측소 매핑 기준정보)

-- ---------------------------------------------------------------------------
-- STEP 1. 대표 시계열 (중도매·상품·가락도매, 원/kg 정규화)
--   배추는 작형에 따라 품종(vrty_cd)이 교대되므로 품종 구분 없이 품목 단위 평균.
--   단위 정규화: unit 문자열에 따라 kg 단가로 환산한다.
-- ---------------------------------------------------------------------------
--   ▣ 영업일 축 (v5.1, 2026-08-24)
--     bn 은 원래 ROW_NUMBER() 였다. 즉 '그 품목이 관측된 날의 순번' 이라
--     품목마다 축이 달랐고, 무엇보다 **미래 기준일에서는 셀 수 없었다**
--     (관측이 없으므로). 운영 배치의 추론이 불가능한 구조였다.
--
--     ref_calendar.survey_seq(KAMIS 중도매가 조사일 축)로 교체한다.
--     실측 대조: 배추·양파·무는 target_dt·행수가 완전히 동일하다(48,411 각).
--     마늘만 45,405 → 45,010 행으로 줄어드는데, 대상일이 조사되지 않은
--     행이 빠지는 것이다. 지금은 축이 밀리면서 그 결측이 가려져 있었다.
--     마늘은 학습에서 제외돼 있어 실험 기록에는 영향이 없다.
--
--     JOIN 이 조사일 아닌 관측일을 떨어뜨린다 — 실측 1건(2023-09-23 토,
--     마늘·깐마늘·고추만 조사된 날).
DROP TABLE IF EXISTS tmp_px;
CREATE TEMP TABLE tmp_px AS
SELECT p.dt, p.item_nm, p.prc, c.survey_seq AS bn
FROM (
SELECT dt, item_nm,
       AVG(prc_per_kg)::NUMERIC(15,3) AS prc
FROM (
    -- ★★ 이름이 아니라 코드로 거른다 (2026-09-03).
    --   원천이 2026 부터 이름을 바꿨다 — 244 '마늘' -> '피마늘' · 241 '고추' -> '건고추'.
    --   그래서 item_nm IN ('배추','양파','무','마늘') 로 걸던 이 자리에서
    --   **마늘이 2025-12-30 에서 조용히 끊겨 있었다** (다른 셋은 2026-09 까지 있음).
    --   값이 틀린 게 아니라 행이 사라지는 사고라 눈에 안 띈다.
    --   CLAUDE.md 9절이 경고한 그대로인데 이 SQL 만 안 고쳐져 있었다.
    --   코드로 걸고 이름은 여기서 우리가 정한다 — 원천이 또 바꿔도 안 흔들린다.
    SELECT exmn_ymd AS dt,
    CASE item_cd WHEN '211' THEN '배추' WHEN '245' THEN '양파'
                 WHEN '231' THEN '무'   WHEN '244' THEN '마늘' END AS item_nm,
           CASE
               -- 'kg', 'kg(그물망 3포기)' 등 kg 계열 → 단위크기로 나눔
               WHEN unit LIKE '%kg%' THEN exmn_dd_prc / NULLIF(unit_sz,0)
               -- 'g' → g당 가격을 kg 로 환산
               WHEN unit = 'g'       THEN exmn_dd_prc / NULLIF(unit_sz,0) * 1000
               -- '포기' 등 kg 로 환산 불가한 단위는 제외 (중도매엔 해당 없음)
               ELSE NULL
           END AS prc_per_kg
    FROM veg_daily_price_raw
    WHERE se_cd   = '02'        -- 중도매인 판매가
      AND grd_cd  = '04'        -- 상품
      AND mrkt_nm = '가락도매'       -- 가락도매 (전 기간 완비)
      AND item_cd IN ('211','245','231','244')     -- 배추·양파·무·마늘
      AND exmn_dd_prc IS NOT NULL
      AND unit_sz > 0
) x
WHERE prc_per_kg IS NOT NULL
GROUP BY dt, item_nm
) p
JOIN ref_calendar c ON c.dt = p.dt AND c.is_survey;

CREATE INDEX ix_tmp_px_dt ON tmp_px(item_nm, dt);
CREATE INDEX ix_tmp_px_bn ON tmp_px(item_nm, bn);

-- STEP 2. 소매 시계열 (보조 feature)
--   ⚠ 배추 소매는 '포기' 단위라 kg 환산 불가 → 품목별로 스케일이 다름.
--     따라서 (소매 − 중도매) 스프레드 파생은 하지 않는다. 모델이 품목별로
--     스케일을 흡수하도록 원단위 값 그대로 둔다.
--
--   ⚠ 서울(sgg_cd='1101') 한정 — 전국 평균을 쓰면 안 된다.
--     2023년에 조사 점포가 44 → 59개로 늘어 학습 구간(2017~2022)과
--     검증 구간의 집계 대상이 달라진다. 중도매가가 가락도매 기준이므로
--     소매도 같은 권역이어야 한다.
--     ※ 아래 STEP 6 의 target_rtl_prc(tmp_rtl_t)와 반드시 같은 필터를 쓸 것.
--       한쪽만 바꾸면 "전국 평균으로 어제 가격을 주고 서울 가격을 맞히라"는
--       어긋난 문제가 된다.
DROP TABLE IF EXISTS tmp_rtl;
CREATE TEMP TABLE tmp_rtl AS
--   ★ 여기도 코드로 건다 (2026-09-03). STEP 1 주석 참조.
SELECT exmn_ymd AS dt,
CASE item_cd WHEN '211' THEN '배추' WHEN '245' THEN '양파'
             WHEN '231' THEN '무'   WHEN '244' THEN '마늘' END AS item_nm,
       AVG(exmn_dd_prc / NULLIF(unit_sz,0))::NUMERIC(15,3) AS prc
FROM veg_daily_price_raw
WHERE se_cd = '01' AND grd_cd = '04'
  AND sgg_cd = '1101'                     -- 서울. 앵커·타겟 동일 기준
  AND item_cd IN ('211','245','231','244')
  AND exmn_dd_prc IS NOT NULL AND unit_sz > 0
GROUP BY 1, 2;
CREATE INDEX ix_tmp_rtl ON tmp_rtl(item_nm, dt);

-- STEP 3. 주산지 기상 사전 집계 (관측소 × 날짜 1회 계산)
--   강수 NULL 은 무강수로 간주(COALESCE). 기온 NULL(0.14%)은 그대로 두어
--   해당 일자의 GDD·기온 feature 가 NULL 이 되도록 한다.
DROP TABLE IF EXISTS tmp_wx;
CREATE TEMP TABLE tmp_wx AS
SELECT "stnNm" AS stn_nm, "tm"::DATE AS dt,
       "avgTa"::NUMERIC(10,3) AS temp_avg,
       SUM(COALESCE("sumRn",0)) OVER w7  ::NUMERIC(12,3) AS rain_sum7,
       SUM(COALESCE("sumRn",0)) OVER w30 ::NUMERIC(12,3) AS rain_sum30,
       SUM(GREATEST("avgTa" - 5.0, 0))   OVER w30 ::NUMERIC(12,3) AS gdd30_base5,
       SUM(GREATEST("avgTa" - 4.0, 0))   OVER w30 ::NUMERIC(12,3) AS gdd30_base4
FROM weather_asos_raw
WINDOW w7  AS (PARTITION BY "stnNm" ORDER BY "tm"::DATE ROWS BETWEEN 6  PRECEDING AND CURRENT ROW),
       w30 AS (PARTITION BY "stnNm" ORDER BY "tm"::DATE ROWS BETWEEN 29 PRECEDING AND CURRENT ROW);
CREATE INDEX ix_tmp_wx ON tmp_wx(stn_nm, dt);

-- STEP 4. 명절 캘린더 — ref_holiday 에서 유도 (v5.3, 2026-08-25)
--
--   전에는 명절 당일 24개가 하드코딩돼 있었고 **2026-09-25 에서 끝났다.**
--   그 이후 대상일은 holiday_remain_d 가 조용히 NULL 이 된다 — 소매가 모델에서
--   importance 2위(11.2%)인 feature 다. 리드타임이 18영업일이라 2026-09 부터
--   실제로 걸릴 참이었다.
--
--   법정 연휴 3일(D-1 · D0 · D+1) 중 **가운데가 당일**이다. ref_calendar 가
--   쓰는 것과 같은 방식이며, ref_holiday 가 2028 까지 있어 자동으로 늘어난다.
--   '대체공휴일(설날)' 은 date_name 이 달라 자동으로 빠진다.
--
--   대조(2026-08-25): 하드코딩 24개와 유도 24개가 **완전 일치**.
--   2027-02-07 · 2027-09-15 · 2028-01-27 · 2028-10-03 이 추가로 덮인다.
DROP TABLE IF EXISTS tmp_holiday;
CREATE TEMP TABLE tmp_holiday AS
WITH lunar AS (
    SELECT date_name, dt,
           ROW_NUMBER() OVER (PARTITION BY EXTRACT(year FROM dt), date_name
                              ORDER BY dt) AS rn
    FROM ref_holiday
    WHERE date_name IN ('설날', '추석') AND is_holiday
)
SELECT dt AS d FROM lunar WHERE rn = 2;

DO $$
DECLARE n int; mx date;
BEGIN
    SELECT COUNT(*), MAX(d) INTO n, mx FROM tmp_holiday;
    IF n < 20 THEN
        RAISE EXCEPTION '명절 당일이 %건뿐입니다. ref_holiday 를 확인하세요.', n;
    END IF;
    -- 리드타임 18영업일(약 4주) 앞까지는 명절을 알아야 한다
    IF mx < CURRENT_DATE + 60 THEN
        RAISE WARNING '명절 캘린더가 % 에서 끝납니다. fetch_holidays.py 로 ref_holiday 를 갱신하세요.', mx;
    END IF;
    RAISE NOTICE '명절 당일 %건 · ~%', n, mx;
END $$;

-- ---------------------------------------------------------------------------
-- STEP 5. 적재
-- ---------------------------------------------------------------------------
INSERT INTO crop_price_train (
    base_dt, item_nm, lead_biz_d, target_dt, target_whsl_prc,
    whsl_prc_lag1, whsl_prc_lag3, whsl_prc_lag7, whsl_prc_prev_yr,
    whsl_prc_avg7, whsl_prc_avg14, whsl_prc_std7,
    arr_qty_lag1, arr_qty_avg7, arr_qty_prev_yr,
    prod_area_stn_nm, prod_area_temp_avg_lag1,
    prod_area_rain_sum7, prod_area_rain_sum30, prod_area_gdd_sum30,
    prod_area_fcst_temp_avg10, market_temp_avg_lag1,
    target_dow, kimchi_season_yn, holiday_remain_d, market_closed_lag1_yn,
    crop_area_yoy_rt, m2_growth_rt, epu_idx, ppi_idx, rtl_prc_lag1,
    school_open_ratio
)
WITH base AS (
    SELECT p.dt AS base_dt, p.item_nm, p.bn,
           LAG(p.prc,1) OVER w AS whsl_prc_lag1,
           LAG(p.prc,3) OVER w AS whsl_prc_lag3,
           LAG(p.prc,7) OVER w AS whsl_prc_lag7,
           AVG(p.prc)         OVER (PARTITION BY p.item_nm ORDER BY p.bn ROWS BETWEEN 7  PRECEDING AND 1 PRECEDING)::NUMERIC(15,3) AS whsl_prc_avg7,
           AVG(p.prc)         OVER (PARTITION BY p.item_nm ORDER BY p.bn ROWS BETWEEN 14 PRECEDING AND 1 PRECEDING)::NUMERIC(15,3) AS whsl_prc_avg14,
           STDDEV_SAMP(p.prc) OVER (PARTITION BY p.item_nm ORDER BY p.bn ROWS BETWEEN 7  PRECEDING AND 1 PRECEDING)::NUMERIC(15,3) AS whsl_prc_std7,
           CASE WHEN p.dt - LAG(p.dt) OVER w > 1 THEN 1 ELSE 0 END AS market_closed_lag1_yn
    FROM tmp_px p
    WINDOW w AS (PARTITION BY p.item_nm ORDER BY p.bn)
),
expanded AS (
    SELECT b.*, l.lead_biz_d, t.dt AS target_dt, t.prc AS target_whsl_prc
    FROM base b
    CROSS JOIN generate_series(1,18) AS l(lead_biz_d)
    JOIN tmp_px t ON t.item_nm = b.item_nm AND t.bn = b.bn + l.lead_biz_d
    -- 상한을 하드코딩하지 않는다 (v5.3, 2026-08-25).
    --   전에는 '2025-12-31' 로 박혀 있었다. RAW 를 2026-08 까지 채우고 v5 를
    --   다시 돌려도 학습 테이블이 2025 에서 멈춰, **아무 경고 없이** 8개월치가
    --   버려졌다. 대상일이 없는 행은 위 JOIN 이 어차피 떨어뜨리므로
    --   상한은 CURRENT_DATE 로 두면 데이터가 있는 만큼 저절로 늘어난다.
    WHERE b.base_dt >= '2015-01-01'::DATE
      AND b.base_dt <= CURRENT_DATE
      AND b.whsl_prc_lag1 IS NOT NULL
)
SELECT
    e.base_dt, e.item_nm, e.lead_biz_d::SMALLINT, e.target_dt, e.target_whsl_prc,
    e.whsl_prc_lag1, e.whsl_prc_lag3, e.whsl_prc_lag7, ly.prc_prev_yr,
    e.whsl_prc_avg7, e.whsl_prc_avg14, e.whsl_prc_std7,
    NULL, NULL, NULL,                                    -- ⚠ 반입량 RAW 미정의
    st.stn_nm, wx.temp_avg, wx.rain_sum7, wx.rain_sum30,
    CASE WHEN st.gdd_base_c = 4.0 THEN wx.gdd30_base4 ELSE wx.gdd30_base5 END,
    NULL,                                                -- ⚠ 중기예보 RAW 미정의
    mk.temp_avg,
    CASE EXTRACT(DOW FROM e.target_dt)
        WHEN 0 THEN '일' WHEN 1 THEN '월' WHEN 2 THEN '화' WHEN 3 THEN '수'
        WHEN 4 THEN '목' WHEN 5 THEN '금' WHEN 6 THEN '토' END,
    CASE WHEN EXTRACT(MONTH FROM e.target_dt) = 11
           OR (EXTRACT(MONTH FROM e.target_dt) = 12 AND EXTRACT(DAY FROM e.target_dt) <= 15)
         THEN 1 ELSE 0 END,
    (SELECT MIN(h.d - e.target_dt) FROM tmp_holiday h WHERE h.d >= e.target_dt),
    e.market_closed_lag1_yn::SMALLINT,
    area.crop_area_yoy_rt,
    ec.m2_yoy_rt, ec.epu_idx, ec.ppi_idx,
    rt.prc,
    sch.school_open_ratio
FROM expanded e

-- 주산지 관측소: 기준정보 테이블 ref_item_station 참조 (§10.5)
--   대상일의 월로 작형을 판정해 관측소와 GDD 기준온도를 함께 가져온다.
--   매핑 변경은 SQL 이 아니라 ref_item_station 을 수정해 반영한다.
LEFT JOIN LATERAL (
    SELECT r.stn_nm, r.gdd_base_c, r.krei_variety_pat
    FROM ref_item_station r
    WHERE r.item_nm = e.item_nm
      AND EXTRACT(MONTH FROM e.target_dt)::INT BETWEEN r.mon_from AND r.mon_to
    LIMIT 1
) st ON TRUE

LEFT JOIN LATERAL (
    SELECT AVG(p.prc)::NUMERIC(15,3) AS prc_prev_yr
    FROM tmp_px p
    WHERE p.item_nm = e.item_nm
      AND p.dt BETWEEN e.target_dt - 368 AND e.target_dt - 362
) ly ON TRUE

LEFT JOIN tmp_wx wx ON wx.stn_nm = st.stn_nm AND wx.dt = e.base_dt - 1
LEFT JOIN tmp_wx mk ON mk.stn_nm = '서울'      AND mk.dt = e.base_dt - 1

LEFT JOIN LATERAL (
    SELECT r.prc FROM tmp_rtl r
    WHERE r.item_nm = e.item_nm AND r.dt < e.base_dt
    ORDER BY r.dt DESC LIMIT 1
) rt ON TRUE

-- 재배면적 증감률 (§10.7)
--   ① report_mon 이 기준일 이전인 것만 사용 (미래정보 누출 방지)
--   ② 같은 report_mon 에 작형별로 여러 행이 존재하므로
--      ref_item_station.krei_variety_pat 으로 대상일의 작형만 선별
--      (예: 2025-12 에 가을배추 -4.1 / 겨울배추 8.5 → 12월은 '가을|겨울|월동')
--   ③ 원본에 동일 내용 행이 중복 적재되어 있어 DISTINCT 로 제거
--   ④ yoy_chg_rt 는 VARCHAR 이며 "-8.1~-5.2" 같은 범위값이 존재.
--      숫자 토큰을 모두 추출해 평균(범위 중간값)을 취한다.
--      한국 통계 관행상 △ 는 음수이므로 '-' 로 치환 후 파싱.
LEFT JOIN LATERAL (
    WITH cand AS (
        SELECT DISTINCT k.item_variety_kr, k.report_mon, k.yoy_chg_rt
        FROM krei_production_yearly_raw k
        WHERE k.item_nm_kr = e.item_nm
          AND k.yoy_chg_rt IS NOT NULL
          AND to_date(k.report_mon, 'YYYY-MM') <= e.base_dt
          AND (st.krei_variety_pat IS NULL
               OR k.item_variety_kr ~ st.krei_variety_pat)
    )
    SELECT ROUND(AVG((
        SELECT AVG(m[1]::NUMERIC)
        FROM regexp_matches(translate(c.yoy_chg_rt, '△▽', '--'),
                            '-?[0-9]+(?:\.[0-9]+)?', 'g') AS m
    )), 3)::NUMERIC(10,3) AS crop_area_yoy_rt
    FROM cand c
    WHERE c.report_mon = (SELECT MAX(report_mon) FROM cand)
) area ON TRUE

LEFT JOIN econ_daily_raw ec ON ec.dt::DATE = e.base_dt

-- 학사일정 (§10.8) — 급식 수요 대리변수
--   기준일이 아니라 대상일로 붙인다. 학사일정은 학년 초에 공시되므로 3주 뒤
--   급식 여부를 오늘 이미 알 수 있다. 미래정보 누출이 아니다.
--   ref_school_day 는 2015~2028 전 구간이 채워져 있어 결측이 나오면 안 된다
--   (검증 [13] 참조). 실측이 아니라 연중 프로파일을 쓰는 이유는 29_ref_school_day.sql 참조.
LEFT JOIN ref_school_day sch ON sch.dt = e.target_dt

ON CONFLICT (base_dt, item_nm, lead_biz_d) DO UPDATE SET
    target_whsl_prc     = EXCLUDED.target_whsl_prc,
    whsl_prc_lag1       = EXCLUDED.whsl_prc_lag1,
    whsl_prc_prev_yr    = EXCLUDED.whsl_prc_prev_yr,
    prod_area_stn_nm    = EXCLUDED.prod_area_stn_nm,
    prod_area_gdd_sum30 = EXCLUDED.prod_area_gdd_sum30,
    rtl_prc_lag1        = EXCLUDED.rtl_prc_lag1,
    crop_area_yoy_rt    = EXCLUDED.crop_area_yoy_rt,
    school_open_ratio   = EXCLUDED.school_open_ratio,
    created_at          = now();


-- ############################################################
-- ## 11_update_clim.sql
-- ############################################################

-- ============================================================================
-- 평년 기온 계산 및 적재  v2.4
--
-- 정의: 기준일 다음날부터 10일간(대상 구간)의 '과거 연도 같은 날짜대' 평균 기온.
--       예) base_dt=2020-08-01 → 대상 구간 08-02~08-11
--           2015~2019년의 08-02~08-11 관측 기온을 모두 평균
--
-- 누수 방지 규칙 (핵심):
--   · 기준일보다 '이전 연도'의 관측만 사용한다. 같은 해와 이후 연도는 제외.
--   · 전체 기간 평균을 한 번 계산해 모든 행에 붙이는 방식은 미래 정보가
--     과거로 새어들어가므로 금지.
--
-- 안정성 규칙:
--   · 참조 가능한 과거 연도가 3년 미만이면 평년값을 NULL 로 둔다.
--     (2015~2017 초기 구간은 표본이 부족해 값이 불안정)
--   · 사용된 연도 수는 prod_area_clim_yr_cnt 에 기록해 추적 가능하게 한다.
--
-- 성능: 대상 구간 10일 × 과거 최대 10년 = 행당 최대 100건 조회.
--       (관측소, 월-일) 인덱스가 있는 임시테이블로 구체화해 처리한다.
-- ============================================================================

-- STEP 1. 관측 기온을 (관측소, 연, 월일) 형태로 펼친 조회용 임시테이블
DROP TABLE IF EXISTS tmp_clim_src;
CREATE TEMP TABLE tmp_clim_src AS
SELECT "stnNm"                        AS stn_nm,
       "tm"::DATE                     AS dt,
       EXTRACT(YEAR  FROM "tm"::DATE)::INT AS yr,
       EXTRACT(MONTH FROM "tm"::DATE)::INT AS mon,
       EXTRACT(DAY   FROM "tm"::DATE)::INT AS dy,
       "avgTa"::NUMERIC(10,3)         AS temp_avg
FROM weather_asos_raw
WHERE "avgTa" IS NOT NULL;

CREATE INDEX ix_clim_src ON tmp_clim_src(stn_nm, mon, dy, yr);

-- STEP 2. 기준일×관측소 단위로 평년값 계산
--   crop_price_train 은 리드타임 18배로 중복되므로, 먼저 distinct 조합만 계산한 뒤
--   UPDATE 로 확산시킨다. (행마다 계산하면 18배 낭비)
DROP TABLE IF EXISTS tmp_clim;
CREATE TEMP TABLE tmp_clim AS
SELECT k.base_dt, k.stn_nm, c.clim_temp, c.yr_cnt
FROM (
    SELECT DISTINCT base_dt, prod_area_stn_nm AS stn_nm
    FROM crop_price_train
    WHERE prod_area_stn_nm IS NOT NULL
) k
CROSS JOIN LATERAL (
    SELECT ROUND(AVG(s.temp_avg), 3)      AS clim_temp,
           COUNT(DISTINCT s.yr)::SMALLINT AS yr_cnt
    FROM generate_series(1, 10) AS g(offs)          -- 대상 구간: 기준일+1 ~ +10일
    JOIN LATERAL (
        SELECT (k.base_dt + g.offs) AS target_d
    ) t ON TRUE
    JOIN tmp_clim_src s
      ON s.stn_nm = k.stn_nm
     AND s.mon    = EXTRACT(MONTH FROM t.target_d)::INT
     AND s.dy     = EXTRACT(DAY   FROM t.target_d)::INT
     AND s.yr     < EXTRACT(YEAR FROM k.base_dt)::INT   -- ★ 기준일 이전 연도만
) c;

CREATE INDEX ix_tmp_clim ON tmp_clim(base_dt, stn_nm);

-- STEP 3. 확산 (과거 연도 3년 미만이면 평년값은 NULL, 연도 수는 기록)
UPDATE crop_price_train t
SET prod_area_clim_temp_avg10 = CASE WHEN c.yr_cnt >= 3 THEN c.clim_temp END,
    prod_area_clim_yr_cnt     = c.yr_cnt
FROM tmp_clim c
WHERE c.base_dt = t.base_dt
  AND c.stn_nm  = t.prod_area_stn_nm;


-- ############################################################
-- ## 15_join_daily_volume.sql
-- ############################################################

-- ============================================================================
-- daily_volume 결합 — arr_qty_* 3컬럼 채우기  v2.6
--
-- ▣ 반영해야 할 데이터 특성 (테이블 정의서 §6 + 실측)
--   1. 기간 2015-01 ~ (v4.0 에서 확장 확인). 학습 전 구간 사용 가능
--   2. item_label 은 배추·양파 (2026-08 확장). 무·마늘은 아직 NULL
--   3. req_date 가 base_date 보다 0~3일 늦음 → 누수 방지에 결정적
--   4. total_ton = 0 인 41일 존재 (명절·연휴 반입 없음) → 평균 계산 시 제외
--   5. total_ton ≠ top1+top2+etc (반올림 ±1) → total_ton 을 그대로 사용
--   6. 일요일 행 없음 → 영업일 축과 정합
--
-- ▣ 누수 방지 설계 (핵심)
--   물량이 base_date 당일에 확정되지 않고 최대 3일 뒤 수집된다.
--   따라서 기준일 시점에 안전하게 알 수 있는 최신 물량은
--     "req_date <= base_dt 인 행 중 base_date 가 가장 최근인 것"
--   이다. 단순히 base_date = base_dt - 1 로 조인하면 아직 수집되지
--   않았을 수 있는 값을 쓰게 되어 백테스트가 낙관적으로 나온다.
--
--   ※ req_date 는 과거 일괄 크롤링 시점일 가능성이 있다. 운영 배치에서
--     실제 공표 지연이 1일이라면 이 조건은 과도하게 보수적일 수 있으므로,
--     팀에서 실제 공표 시점을 확인한 뒤 조정할 것.
-- ============================================================================

ALTER TABLE crop_price_train
    ADD COLUMN IF NOT EXISTS arr_qty_asof_date DATE,
    ADD COLUMN IF NOT EXISTS arr_top1_region   VARCHAR(20);

COMMENT ON COLUMN crop_price_train.arr_qty_lag1 IS
  '기준일 시점에 알 수 있는 최신 반입량(톤). req_date <= base_dt 조건의 as-of 조회';
COMMENT ON COLUMN crop_price_train.arr_qty_asof_date IS
  'arr_qty_lag1 이 실제로 어느 날짜의 물량인지. 지연 추적용';
COMMENT ON COLUMN crop_price_train.arr_top1_region IS
  '해당 시점 1위 산지. 주산지 매핑 검증 및 산지 전환 감지용';

-- STEP 1. 물량 시계열 구체화 (0톤 = 반입 없음, 평균 계산에서 제외)
DROP TABLE IF EXISTS tmp_vol;
CREATE TEMP TABLE tmp_vol AS
SELECT base_date, item_label, total_ton, top1_region, req_date,
       AVG(total_ton) FILTER (WHERE total_ton > 0)
         OVER (PARTITION BY item_label ORDER BY base_date
               ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS ma7_ton
FROM daily_volume;
CREATE INDEX ix_tmp_vol ON tmp_vol(item_label, req_date, base_date DESC);
CREATE INDEX ix_tmp_vol2 ON tmp_vol(item_label, base_date);
ANALYZE tmp_vol;

-- STEP 2. as-of 결합
--   PostgreSQL 에서는 UPDATE ... FROM LATERAL 이 대상 테이블(t)을 참조할 수 없으므로
--   SET 절의 상관 서브쿼리로 작성한다.
UPDATE crop_price_train t
SET arr_qty_lag1 = (
        SELECT v.total_ton FROM tmp_vol v
        WHERE v.item_label = t.item_nm
          AND v.req_date  <= t.base_dt      -- 기준일까지 수집 완료된 것만
          AND v.base_date <  t.base_dt      -- 당일 물량 제외
        ORDER BY v.base_date DESC LIMIT 1),
    arr_qty_avg7 = (
        SELECT ROUND(v.ma7_ton, 3) FROM tmp_vol v
        WHERE v.item_label = t.item_nm
          AND v.req_date <= t.base_dt AND v.base_date < t.base_dt
        ORDER BY v.base_date DESC LIMIT 1),
    arr_qty_asof_date = (
        SELECT v.base_date FROM tmp_vol v
        WHERE v.item_label = t.item_nm
          AND v.req_date <= t.base_dt AND v.base_date < t.base_dt
        ORDER BY v.base_date DESC LIMIT 1),
    arr_top1_region = (
        SELECT v.top1_region FROM tmp_vol v
        WHERE v.item_label = t.item_nm
          AND v.req_date <= t.base_dt AND v.base_date < t.base_dt
        ORDER BY v.base_date DESC LIMIT 1)
WHERE EXISTS (SELECT 1 FROM tmp_vol v WHERE v.item_label = t.item_nm);

-- STEP 3. 전년 동시기 물량 (대상일 -365일 ±3일 평균, 0톤 제외)
UPDATE crop_price_train t
SET arr_qty_prev_yr = (
        SELECT ROUND(AVG(v.total_ton), 3) FROM tmp_vol v
        WHERE v.item_label = t.item_nm
          AND v.total_ton > 0
          AND v.base_date BETWEEN t.target_dt - 368 AND t.target_dt - 362)
WHERE EXISTS (SELECT 1 FROM tmp_vol v WHERE v.item_label = t.item_nm);

-- 검증
SELECT EXTRACT(YEAR FROM base_dt)::INT AS yr,
       COUNT(*) AS rows,
       ROUND(100.0*COUNT(arr_qty_lag1)/COUNT(*),1) AS 채움률,
       ROUND(AVG(base_dt - arr_qty_asof_date),2)   AS 평균지연일,
       MAX(base_dt - arr_qty_asof_date)            AS 최대지연일
FROM crop_price_train WHERE item_nm='배추'
GROUP BY 1 ORDER BY 1;

SELECT EXTRACT(MONTH FROM target_dt)::INT AS mon,
       prod_area_stn_nm AS 매핑관측소,
       arr_top1_region  AS 실제1위산지,
       COUNT(*) AS cnt
FROM crop_price_train
WHERE item_nm='배추' AND arr_top1_region IS NOT NULL
GROUP BY 1,2,3
HAVING COUNT(*) > 30
ORDER BY 1, cnt DESC;



-- ############################################################
-- ## STEP 5. 경락가 feature  (21_add_auction_features.sql)
-- ############################################################

-- ── STEP 1. 컬럼 추가 ──────────────────────────────────────────────────
ALTER TABLE crop_price_train
    ADD COLUMN IF NOT EXISTS auc_prc_lag1        NUMERIC(15,3),
    ADD COLUMN IF NOT EXISTS auc_prc_lag3        NUMERIC(15,3),
    ADD COLUMN IF NOT EXISTS auc_prc_avg7        NUMERIC(15,3),
    ADD COLUMN IF NOT EXISTS auc_prc_spread_lag1 NUMERIC(10,4),
    ADD COLUMN IF NOT EXISTS auc_vol_lag1        NUMERIC(18,3),
    ADD COLUMN IF NOT EXISTS auc_whsl_ratio_lag1 NUMERIC(10,4),
    -- ▼ 파생 컬럼 대칭화 (2026-08-27). 중도매가만 7종을 갖고 경락·소매는
    --   각각 3종·1종뿐이었다. 3-타겟 확장 때 "feature 는 공통" 이라는 전제로
    --   타겟 컬럼만 추가한 결과다. 앵커 변환에서는 앵커가 곧 baseline 이므로
    --   baseline 후보군도 타겟마다 있어야 한다 — 없으면 비교 자체가 불가능하다.
    ADD COLUMN IF NOT EXISTS auc_prc_lag7        NUMERIC(15,3),
    ADD COLUMN IF NOT EXISTS auc_prc_avg14       NUMERIC(15,3),
    ADD COLUMN IF NOT EXISTS auc_prc_std7        NUMERIC(15,3),
    ADD COLUMN IF NOT EXISTS auc_prc_prev_yr     NUMERIC(15,3),
    ADD COLUMN IF NOT EXISTS rtl_prc_lag3        NUMERIC(15,3),
    ADD COLUMN IF NOT EXISTS rtl_prc_lag7        NUMERIC(15,3),
    ADD COLUMN IF NOT EXISTS rtl_prc_avg7        NUMERIC(15,3),
    ADD COLUMN IF NOT EXISTS rtl_prc_avg14       NUMERIC(15,3),
    ADD COLUMN IF NOT EXISTS rtl_prc_std7        NUMERIC(15,3),
    ADD COLUMN IF NOT EXISTS rtl_prc_prev_yr     NUMERIC(15,3);

-- ⚠ 위 auc_prc_lag7 · auc_prc_avg14 · auc_prc_std7 · auc_prc_prev_yr 은
--   이 파일 앞부분(05_alter_rename)의 **개명 목록에 같은 이름이 들어 있다.**
--   그 블록은 과거 중도매가가 auc_* 로 잘못 명명됐던 것을 whsl_* 로 바꾸는
--   잔재이며, "구 이름이 있고 새 이름이 없을 때만" 바꾼다.
--   whsl_prc_lag7 등이 이미 존재하므로 지금은 개명되지 않는다.
--   **whsl_* 를 지우면 이 경락가 컬럼들이 조용히 개명된다.** 건드리지 말 것.

COMMENT ON COLUMN crop_price_train.auc_prc_lag1 IS
  '직전 영업일 경매 낙찰가(원/kg). 서울가락·특등급. 중도매가의 선행지표 후보';
COMMENT ON COLUMN crop_price_train.auc_prc_spread_lag1 IS
  '직전 영업일 일중 스프레드 (max-min)/avg. 낙찰가 편차가 클수록 시장 불안정';
COMMENT ON COLUMN crop_price_train.auc_whsl_ratio_lag1 IS
  '중도매가 / 경락가 배수. 유통 마진 수준. 급등기에 축소되는 경향';


-- ── STEP 2. 경락가 시계열 구체화 ──────────────────────────────────────
--   경매 개장일 축으로 lag·rolling 을 계산한다.
--   중도매가와 개장일이 다를 수 있으므로 별도 축을 쓰고, 결합은 달력 기준
--   as-of(기준일 이전 최신)로 처리한다.
DROP TABLE IF EXISTS tmp_auc;
CREATE TEMP TABLE tmp_auc AS
SELECT dt, item_nm, prc, vol, spread,
       LAG(prc, 1) OVER w AS prc_lag1,
       LAG(prc, 3) OVER w AS prc_lag3,
       LAG(prc, 7) OVER w AS prc_lag7,
       AVG(prc) OVER (PARTITION BY item_nm ORDER BY bn
                      ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)::NUMERIC(15,3) AS prc_avg7,
       -- avg14·std7 은 중도매가와 같은 창(1 PRECEDING 까지)을 쓴다.
       -- avg7 만 CURRENT ROW 를 포함하는데, 이는 as-of 결합이 base_dt 이전
       -- 최신 경매일을 가져오므로 그 시점의 '당일' 은 이미 과거다. 누출 아님.
       AVG(prc)         OVER (PARTITION BY item_nm ORDER BY bn
                              ROWS BETWEEN 14 PRECEDING AND 1 PRECEDING)::NUMERIC(15,3) AS prc_avg14,
       STDDEV_SAMP(prc) OVER (PARTITION BY item_nm ORDER BY bn
                              ROWS BETWEEN 7  PRECEDING AND 1 PRECEDING)::NUMERIC(15,3) AS prc_std7,
       LAG(vol, 1)    OVER w AS vol_lag1,
       LAG(spread, 1) OVER w AS spread_lag1
FROM (
    -- ★ 규격 고정 (2026-08-27). 이 WHERE 절이 타겟의 정의다.
    --
    --   예전에는 (시장·등급)만 걸어 **하루 한 행**을 가정했다. 그런데 원천은
    --   포장 규격별로 행이 나뉘어 있었고, 수집기가 그걸 뭉쳐서 한 행으로 만들고
    --   있었다. 그 결과 배추 특등급 하루치에 그물망 10kg(711원/kg)부터
    --   1kg 소포장(11,224원/kg)까지 15개 상품이 한 평균에 섞였다.
    --   실측 피해: 배추 경락가 자기상관 ACF(1) 0.085 — 사실상 백색잡음이었다.
    --   규격을 고정하면 0.795 로 올라간다.
    --
    --   중량으로 거른다. 포장 형태(그물망·파렛트·PE대)는 같은 중량이면
    --   같은 상품이고 운송 방식 차이일 뿐이다 — kg 단가가 서로 비슷하다.
    --
    --   무는 2018년에 18kg → 20kg 로 포장 표준이 바뀌었다. 전환기 kg 단가가
    --   1,279 vs 1,243원(차이 3%)으로 계단이 없어 이어 붙인다.
    --
    --   ⚠ auction_prices_daily 에 unit_weight_kg 가 있어야 한다 (수집기 v3).
    --     구 데이터에는 이 컬럼이 없어 전부 NULL 이 되고 타겟이 빈다.
    --     STEP -1 의 선행 검사가 막는다.
    SELECT auction_date AS dt,
           item_name    AS item_nm,
           avg_auction_price_krw_per_kg AS prc,
           trade_volume_kg              AS vol,
           CASE WHEN avg_auction_price_krw_per_kg > 0
                THEN (max_auction_price_krw_per_kg - min_auction_price_krw_per_kg)
                     / avg_auction_price_krw_per_kg
           END::NUMERIC(10,4) AS spread,
           ROW_NUMBER() OVER (PARTITION BY item_name ORDER BY auction_date) AS bn
    FROM (
        --   같은 (날짜·품목) 안에서 대상 중량 행들을 물량가중으로 합친다.
        --   그물망 10kg 와 파렛트 10kg 가 둘 다 있으면 합쳐 하나로 만든다.
        SELECT auction_date, item_name,
               SUM(trade_amount_krw) / NULLIF(SUM(trade_volume_kg), 0)
                   AS avg_auction_price_krw_per_kg,
               SUM(trade_volume_kg)  AS trade_volume_kg,
               MIN(min_auction_price_krw_per_kg) AS min_auction_price_krw_per_kg,
               MAX(max_auction_price_krw_per_kg) AS max_auction_price_krw_per_kg
          FROM auction_prices_daily
         WHERE wholesale_market_code = '110001'   -- 서울가락
           AND grade_code            = '11'       -- 특등급 (가락 물량의 98%)
           AND avg_auction_price_krw_per_kg > 0
           AND trade_volume_kg > 0
           -- ★ 포장 형태까지 고정한다 (2026-08-27 재수정)
           --   처음엔 "같은 중량이면 같은 상품" 으로 보고 형태를 열어뒀는데
           --   5년치로 재보니 틀렸다. 배추 10kg 안에서도
           --     그물망 824원 · 파렛트 943 · 상자 1,115 · **비닐봉지 3,071**
           --   로 갈린다. 비닐봉지 10kg 은 그물망의 3.7배다.
           --   실측: 10kg 전체 ACF(1) 0.484 → 그물망만 0.908
           --   파렛트는 더해도 무해하다 (0.927 → 0.928, 물량 92%→94%).
           --   대량 유통 형태(그물망·상자·파렛트)만 남기고 소매용 포장을 뺀다.
           --   포장 형태도 **품목마다 다르다.** 공통 목록으로 묶으면 안 된다.
           --   배추에 '상자' 를 넣으면 상자 10kg(1,115원)가 그물망(824원)에
           --   섞여 ACF 가 0.928 → 0.513 으로 떨어진다. 실제로 그렇게 만들었다가
           --   되돌렸다.
           AND (   (item_name = '배추' AND package_name IN ('그물망', '파렛트'))
                OR (item_name = '무'   AND package_name IN ('상자',   '파렛트'))
                OR (item_name = '양파' AND package_name IN ('그물망', '파렛트'))
                OR (item_name NOT IN ('배추', '무', '양파')))
           AND (   (item_name = '배추' AND unit_weight_kg = 10)
                -- 무는 2018년에 18kg → 20kg 로 포장 표준이 바뀌었다.
                -- 2017 은 18kg 227일 / 20kg 63일, 2018 부터는 20kg 300일대.
                -- 연도로 갈라야 양쪽 다 온전하다. 겹쳐 쓰면 2018 이후의
                -- 띄엄띄엄한 18kg 잔여 거래가 섞여 계열이 나빠진다 (ACF 0.373).
                OR (item_name = '무' AND (
                        (auction_date <  DATE '2018-01-01' AND unit_weight_kg = 18)
                     OR (auction_date >= DATE '2018-01-01' AND unit_weight_kg = 20)))
                OR (item_name = '양파' AND unit_weight_kg = 15)
                -- 마늘·고추는 규격 미확정. 종전처럼 전 규격을 쓴다
                OR (item_name NOT IN ('배추', '무', '양파')))
         GROUP BY auction_date, item_name
    ) src
    WHERE avg_auction_price_krw_per_kg > 0
) x
WINDOW w AS (PARTITION BY item_nm ORDER BY bn);

CREATE INDEX ix_tmp_auc ON tmp_auc(item_nm, dt);


-- ── STEP 3. as-of 결합 ────────────────────────────────────────────────
--   기준일 이전(당일 제외)의 가장 최근 경매일 값을 가져온다.
--   중도매가 개장일과 경매 개장일이 어긋나는 날에도 안전하게 동작한다.
-- PostgreSQL 은 UPDATE ... FROM LATERAL 에서 대상 테이블을 참조할 수 없으므로
-- SET 절의 상관 서브쿼리로 작성한다.
UPDATE crop_price_train t
SET auc_prc_lag1 = (
        SELECT a.prc FROM tmp_auc a
        WHERE a.item_nm = t.item_nm AND a.dt < t.base_dt
        ORDER BY a.dt DESC LIMIT 1),
    auc_prc_lag3 = (
        SELECT a.prc_lag3 FROM tmp_auc a
        WHERE a.item_nm = t.item_nm AND a.dt < t.base_dt
        ORDER BY a.dt DESC LIMIT 1),
    auc_prc_avg7 = (
        SELECT a.prc_avg7 FROM tmp_auc a
        WHERE a.item_nm = t.item_nm AND a.dt < t.base_dt
        ORDER BY a.dt DESC LIMIT 1),
    auc_prc_spread_lag1 = (
        SELECT a.spread FROM tmp_auc a
        WHERE a.item_nm = t.item_nm AND a.dt < t.base_dt
        ORDER BY a.dt DESC LIMIT 1),
    auc_vol_lag1 = (
        SELECT a.vol FROM tmp_auc a
        WHERE a.item_nm = t.item_nm AND a.dt < t.base_dt
        ORDER BY a.dt DESC LIMIT 1),
    auc_prc_lag7 = (
        SELECT a.prc_lag7 FROM tmp_auc a
        WHERE a.item_nm = t.item_nm AND a.dt < t.base_dt
        ORDER BY a.dt DESC LIMIT 1),
    auc_prc_avg14 = (
        SELECT a.prc_avg14 FROM tmp_auc a
        WHERE a.item_nm = t.item_nm AND a.dt < t.base_dt
        ORDER BY a.dt DESC LIMIT 1),
    auc_prc_std7 = (
        SELECT a.prc_std7 FROM tmp_auc a
        WHERE a.item_nm = t.item_nm AND a.dt < t.base_dt
        ORDER BY a.dt DESC LIMIT 1)
WHERE EXISTS (SELECT 1 FROM tmp_auc a WHERE a.item_nm = t.item_nm);

-- 경락가 전년 동시기 — 중도매가와 같은 정의 (대상일 -365일 ±3일 평균).
--   base_dt 가 아니라 **target_dt** 기준이다. 1년 전 값이므로 누출이 아니다.
UPDATE crop_price_train t
SET auc_prc_prev_yr = (
        SELECT AVG(a.prc)::NUMERIC(15,3) FROM tmp_auc a
        WHERE a.item_nm = t.item_nm
          AND a.dt BETWEEN t.target_dt - 368 AND t.target_dt - 362)
WHERE EXISTS (SELECT 1 FROM tmp_auc a WHERE a.item_nm = t.item_nm);


-- ── STEP 4. 유통 마진 배수 ────────────────────────────────────────────
--   중도매가 ÷ 경락가. 두 값 모두 원/kg 이므로 직접 나눌 수 있다.
--   급등기에 중도매인이 마진을 줄여 흡수하는 경향이 있어 배수가 축소된다.
UPDATE crop_price_train
SET auc_whsl_ratio_lag1 = ROUND(whsl_prc_lag1 / NULLIF(auc_prc_lag1, 0), 4)
WHERE whsl_prc_lag1 IS NOT NULL AND auc_prc_lag1 IS NOT NULL;


-- ── STEP 5. 소매가 파생 (2026-08-27 추가) ─────────────────────────────
--   소매가는 지금까지 rtl_prc_lag1 하나뿐이었다. 그래서 소매 모델을
--   **자기 앵커 말고는 아무것과도 비교할 수 없었다.** 세 타겟 중 성능이
--   가장 좋다고 기록돼 있지만(+16.0%) 그 값은 앵커 대비일 뿐이다.
--
--   조사 축은 중도매가와 같다(2,365일 vs 2,366일). 그래서 중도매가와
--   같은 창을 쓴다 — 여기가 어긋나면 두 타겟의 비교가 성립하지 않는다.
DROP TABLE IF EXISTS tmp_rtl_d;
CREATE TEMP TABLE tmp_rtl_d AS
SELECT dt, item_nm, prc,
       LAG(prc, 1) OVER w AS prc_lag1,
       LAG(prc, 3) OVER w AS prc_lag3,
       LAG(prc, 7) OVER w AS prc_lag7,
       AVG(prc)         OVER (PARTITION BY item_nm ORDER BY bn
                              ROWS BETWEEN 7  PRECEDING AND 1 PRECEDING)::NUMERIC(15,3) AS prc_avg7,
       AVG(prc)         OVER (PARTITION BY item_nm ORDER BY bn
                              ROWS BETWEEN 14 PRECEDING AND 1 PRECEDING)::NUMERIC(15,3) AS prc_avg14,
       STDDEV_SAMP(prc) OVER (PARTITION BY item_nm ORDER BY bn
                              ROWS BETWEEN 7  PRECEDING AND 1 PRECEDING)::NUMERIC(15,3) AS prc_std7
FROM (SELECT dt, item_nm, prc,
             ROW_NUMBER() OVER (PARTITION BY item_nm ORDER BY dt) AS bn
      FROM tmp_rtl) x
WINDOW w AS (PARTITION BY item_nm ORDER BY bn);
CREATE INDEX ix_tmp_rtl_d ON tmp_rtl_d(item_nm, dt);

--   as-of 결합 — 경락가와 같은 방식(기준일 이전 최신).
--   rtl_prc_lag1 은 STEP 5 의 대량 INSERT 에서 이미 채워지므로 건드리지 않는다.
UPDATE crop_price_train t
SET rtl_prc_lag3 = (
        SELECT r.prc_lag3 FROM tmp_rtl_d r
        WHERE r.item_nm = t.item_nm AND r.dt < t.base_dt
        ORDER BY r.dt DESC LIMIT 1),
    rtl_prc_lag7 = (
        SELECT r.prc_lag7 FROM tmp_rtl_d r
        WHERE r.item_nm = t.item_nm AND r.dt < t.base_dt
        ORDER BY r.dt DESC LIMIT 1),
    rtl_prc_avg7 = (
        SELECT r.prc_avg7 FROM tmp_rtl_d r
        WHERE r.item_nm = t.item_nm AND r.dt < t.base_dt
        ORDER BY r.dt DESC LIMIT 1),
    rtl_prc_avg14 = (
        SELECT r.prc_avg14 FROM tmp_rtl_d r
        WHERE r.item_nm = t.item_nm AND r.dt < t.base_dt
        ORDER BY r.dt DESC LIMIT 1),
    rtl_prc_std7 = (
        SELECT r.prc_std7 FROM tmp_rtl_d r
        WHERE r.item_nm = t.item_nm AND r.dt < t.base_dt
        ORDER BY r.dt DESC LIMIT 1)
WHERE EXISTS (SELECT 1 FROM tmp_rtl_d r WHERE r.item_nm = t.item_nm);

--   소매가 전년 동시기 — 대상일 -365일 ±3일 평균 (중도매·경락과 동일 정의)
UPDATE crop_price_train t
SET rtl_prc_prev_yr = (
        SELECT AVG(r.prc)::NUMERIC(15,3) FROM tmp_rtl_d r
        WHERE r.item_nm = t.item_nm
          AND r.dt BETWEEN t.target_dt - 368 AND t.target_dt - 362)
WHERE EXISTS (SELECT 1 FROM tmp_rtl_d r WHERE r.item_nm = t.item_nm);

COMMENT ON COLUMN crop_price_train.auc_prc_prev_yr IS
  '대상일 -365일 ±3일 경락가 평균(원/kg). 서울가락·특등급';
COMMENT ON COLUMN crop_price_train.auc_prc_std7 IS
  '직전 7 경매일 경락가 표준편차(원/kg). 경매 축 기준';
COMMENT ON COLUMN crop_price_train.rtl_prc_prev_yr IS
  '대상일 -365일 ±3일 소매가 평균(원/단위). 서울(sgg_cd=1101) 한정. '
  '품목별 단위가 다르므로 타 계열과 직접 비교 금지';
COMMENT ON COLUMN crop_price_train.rtl_prc_std7 IS
  '직전 7 조사일 소매가 표준편차(원/단위). 서울 한정';


-- ############################################################
-- ## STEP 6. 타겟 3종  (23_add_three_targets.sql)
-- ############################################################

-- ── STEP 1. 타겟 컬럼 추가 ────────────────────────────────────────────
ALTER TABLE crop_price_train
    ADD COLUMN IF NOT EXISTS target_auc_prc NUMERIC(15,3),
    ADD COLUMN IF NOT EXISTS target_rtl_prc NUMERIC(15,3);

COMMENT ON COLUMN crop_price_train.target_auc_prc IS
  '대상일 경매 낙찰가(원/kg). 서울가락·특등급. 사용자=농가·산지유통인';
COMMENT ON COLUMN crop_price_train.target_whsl_prc IS
  '대상일 중도매인 판매가(원/kg). 가락도매·상품. 사용자=식당·급식 구매담당 (주력)';
COMMENT ON COLUMN crop_price_train.target_rtl_prc IS
  '대상일 소매가(원/단위) · 서울(sgg_cd=1101) 한정. 앵커 rtl_prc_lag1 과 동일 기준. '
  '배추는 포기 단위이므로 kg 인 다른 타겟과 스케일 다름';


-- ── STEP 2. 경락가 타겟 결합 ──────────────────────────────────────────
--   타겟이므로 target_dt 당일 값을 그대로 가져온다.
--   (입력이 아니라 정답 라벨이므로 미래 정보 사용이 정상)
--   ★★ 규격 조건은 tmp_auc(앵커)와 **글자 그대로 같아야 한다** (2026-08-28 수정)
--
--   ▣ 무슨 일이 있었나
--     08-27 에 규격 컬럼을 넣으면서 tmp_auc(앵커)에만 조건을 걸고
--     여기(정답)에는 안 걸었다. 그전에는 (날짜·시장·품목·등급) 조합에
--     행이 **하나뿐**이라 아래 LIMIT 1 이 안전했는데, 규격별로 행이
--     갈라지면서 **한 조합에 15행**이 생겼고 LIMIT 1 이 아무거나 집었다.
--
--       2026-01-27 무   상자 20kg  649원/kg  361,520kg   ← 골라야 할 것
--                       상자  2kg 9,500원/kg     80kg    ← 실제로 고른 것
--
--     실측 피해: 정답값이 규격 기준과 어긋난 비율이
--       무 96% · 배추 68% · 양파 99% 였다.
--
--   ▣ 왜 앵커와 같아야 하나
--     학습이 y = log(정답 / 앵커) 이다. 둘이 다른 상품에서 나오면
--     "A 상품 어제 가격으로 B 상품 오늘 가격을 맞혀라" 가 된다.
--     숫자는 멀쩡히 나오고 에러도 안 난다. CLAUDE.md 9절 참조.
--
--   ▣ 바꿀 때 규칙
--     tmp_auc 의 WHERE 절을 고치면 **여기도 같이 고친다.**
--     아래 STEP 검증 [16] 이 둘의 일치를 자동으로 검사한다.
DROP TABLE IF EXISTS tmp_auc_t;
CREATE TEMP TABLE tmp_auc_t AS
SELECT auction_date AS dt,
       item_name    AS item_nm,
       (SUM(trade_amount_krw) / NULLIF(SUM(trade_volume_kg), 0))::NUMERIC(15,3) AS prc
FROM auction_prices_daily
WHERE wholesale_market_code = '110001'   -- 서울가락
  AND grade_code            = '11'       -- 특등급
  AND avg_auction_price_krw_per_kg > 0
  AND trade_volume_kg > 0
  -- ↓↓ 여기부터 tmp_auc 와 동일 ↓↓
  AND (   (item_name = '배추' AND package_name IN ('그물망', '파렛트'))
       OR (item_name = '무'   AND package_name IN ('상자',   '파렛트'))
       OR (item_name = '양파' AND package_name IN ('그물망', '파렛트'))
       OR (item_name NOT IN ('배추', '무', '양파')))
  AND (   (item_name = '배추' AND unit_weight_kg = 10)
       OR (item_name = '무' AND (
               (auction_date <  DATE '2018-01-01' AND unit_weight_kg = 18)
            OR (auction_date >= DATE '2018-01-01' AND unit_weight_kg = 20)))
       OR (item_name = '양파' AND unit_weight_kg = 15)
       OR (item_name NOT IN ('배추', '무', '양파')))
  -- ↑↑ 여기까지 tmp_auc 와 동일 ↑↑
GROUP BY auction_date, item_name;
CREATE INDEX ix_tmp_auc_t ON tmp_auc_t(item_nm, dt);

--   물량가중으로 (날짜·품목) 당 한 행이 되었으므로 LIMIT 1 은 더 이상
--   "아무거나" 가 아니다. 그래도 명시적으로 남겨 둔다 — 규격 조건이
--   또 빠지면 여기서 조용히 틀리는 대신 [16] 검증에서 걸리게 한다.
UPDATE crop_price_train t
SET target_auc_prc = (
    SELECT a.prc FROM tmp_auc_t a
    WHERE a.item_nm = t.item_nm AND a.dt = t.target_dt
    LIMIT 1);


-- ── STEP 3. 소매가 타겟 결합 ──────────────────────────────────────────
--   기존 rtl_prc_lag1 과 동일한 산출 로직을 써야 한다.
--   lag 과 target 이 다른 시계열에서 나오면 모델이 잘못 학습한다.
--   → 위 STEP 2 의 tmp_rtl 과 필터가 완전히 같아야 한다 (서울 한정 포함).
DROP TABLE IF EXISTS tmp_rtl_t;
CREATE TEMP TABLE tmp_rtl_t AS
--   ★ 앵커(tmp_rtl)와 똑같이 코드로 거른다. 한쪽만 바꾸면 2026 부터
--     이름이 어긋나 조인이 통째로 빈다 (2026-09-03)
SELECT exmn_ymd AS dt,
CASE item_cd WHEN '211' THEN '배추' WHEN '245' THEN '양파'
             WHEN '231' THEN '무'   WHEN '244' THEN '마늘' END AS item_nm,
       AVG(exmn_dd_prc / NULLIF(unit_sz, 0))::NUMERIC(15,3) AS prc
FROM veg_daily_price_raw
WHERE se_cd  = '01'          -- 소매
  AND grd_cd = '04'          -- 상품
  AND sgg_cd = '1101'        -- 서울. tmp_rtl(앵커)과 동일 기준
  AND item_cd IN ('211','245','231','244')
  AND exmn_dd_prc IS NOT NULL
  AND unit_sz > 0
GROUP BY 1, 2;
CREATE INDEX ix_tmp_rtl_t ON tmp_rtl_t(item_nm, dt);

UPDATE crop_price_train t
SET target_rtl_prc = (
    SELECT r.prc FROM tmp_rtl_t r
    WHERE r.item_nm = t.item_nm AND r.dt = t.target_dt
    LIMIT 1);


-- ############################################################
-- ## STEP 8. predict_input — 추론 입력 (v5.2)
-- ##
-- ##   crop_price_train 은 **타겟이 있는 행만** 담는다. expanded 가
-- ##   tmp_px 에 대상일 가격이 있는 행만 조인하기 때문이다. 그래서 미래
-- ##   기준일 행이 원리적으로 생기지 않고, predict.py 를 돌릴 입력이 없다.
-- ##
-- ##   여기서는 같은 feature 계산을 그대로 쓰되 대상일만 달력에서 센다.
-- ##       crop_price_train   target_dt = tmp_px 에 값이 있는 날
-- ##       predict_input      target_dt = ref_calendar.survey_seq + 리드타임
-- ##
-- ##   v5.1 이 bn 을 ROW_NUMBER() 에서 survey_seq 로 바꾼 이유가 이것이다.
-- ##   관측이 없는 미래 날짜는 ROW_NUMBER() 로 셀 수 없었다.
-- ##
-- ##   ▣ feature UPDATE 는 STEP 3·4·5 원문을 그대로 복제한 것이다.
-- ##     둘이 갈라지면 학습과 추론의 계산식이 달라지고, 그때 나오는 것은
-- ##     예외가 아니라 **그럴듯하게 틀린 값**이다. 아래 검증 [14] 가
-- ##     겹치는 구간을 전 컬럼 대조해 갈라짐을 잡는다. 불일치가 나오면
-- ##     STEP 3·4·5 를 고치고 여기도 함께 고칠 것.
-- ############################################################

-- 생성할 기준일 수 (최근 조사일 기준).
--   운영 배치는 1이면 충분하지만, 검증 [14] 가 성립하려면 crop_price_train 과
--   겹치는 구간이 필요하다. 30이면 앞쪽 12개 남짓이 리드타임 18까지 겹친다.
DROP TABLE IF EXISTS tmp_pi_cfg;
CREATE TEMP TABLE tmp_pi_cfg AS SELECT 30 AS n_base;

DROP TABLE IF EXISTS predict_input;
CREATE TABLE predict_input (LIKE crop_price_train);
ALTER TABLE predict_input DROP COLUMN IF EXISTS id,
                          DROP COLUMN IF EXISTS created_at;
COMMENT ON TABLE predict_input IS
  '추론 입력. crop_price_train 과 같은 feature 를 갖되 타겟은 NULL. '
  'target_dt 를 ref_calendar 조사 축에서 세므로 미래 대상일이 들어간다. '
  'DBEAVER_run_v5.sql STEP 8 로 재생성';

INSERT INTO predict_input (
    base_dt, item_nm, lead_biz_d, target_dt,
    whsl_prc_lag1, whsl_prc_lag3, whsl_prc_lag7, whsl_prc_prev_yr,
    whsl_prc_avg7, whsl_prc_avg14, whsl_prc_std7,
    prod_area_stn_nm, prod_area_temp_avg_lag1,
    prod_area_rain_sum7, prod_area_rain_sum30, prod_area_gdd_sum30,
    market_temp_avg_lag1,
    target_dow, kimchi_season_yn, holiday_remain_d, market_closed_lag1_yn,
    crop_area_yoy_rt, m2_growth_rt, epu_idx, ppi_idx, rtl_prc_lag1,
    school_open_ratio
)
WITH base AS (
    SELECT p.dt AS base_dt, p.item_nm, p.bn,
           LAG(p.prc,1) OVER w AS whsl_prc_lag1,
           LAG(p.prc,3) OVER w AS whsl_prc_lag3,
           LAG(p.prc,7) OVER w AS whsl_prc_lag7,
           AVG(p.prc)         OVER (PARTITION BY p.item_nm ORDER BY p.bn ROWS BETWEEN 7  PRECEDING AND 1 PRECEDING)::NUMERIC(15,3) AS whsl_prc_avg7,
           AVG(p.prc)         OVER (PARTITION BY p.item_nm ORDER BY p.bn ROWS BETWEEN 14 PRECEDING AND 1 PRECEDING)::NUMERIC(15,3) AS whsl_prc_avg14,
           STDDEV_SAMP(p.prc) OVER (PARTITION BY p.item_nm ORDER BY p.bn ROWS BETWEEN 7  PRECEDING AND 1 PRECEDING)::NUMERIC(15,3) AS whsl_prc_std7,
           CASE WHEN p.dt - LAG(p.dt) OVER w > 1 THEN 1 ELSE 0 END AS market_closed_lag1_yn
    FROM tmp_px p
    WINDOW w AS (PARTITION BY p.item_nm ORDER BY p.bn)
),
recent AS (
    SELECT item_nm, MAX(bn) AS bn_max FROM tmp_px GROUP BY item_nm
),
-- crop_price_train 과 다른 곳은 여기 하나뿐이다.
--   저기는 tmp_px 에서 대상일을 찾고(=값이 있어야 한다),
--   여기는 ref_calendar 조사 축에서 센다(=미래도 셀 수 있다).
expanded AS (
    SELECT b.*, l.lead_biz_d, c.dt AS target_dt
    FROM base b
    JOIN recent r ON r.item_nm = b.item_nm
                 AND b.bn > r.bn_max - (SELECT n_base FROM tmp_pi_cfg)
    CROSS JOIN generate_series(1,18) AS l(lead_biz_d)
    JOIN ref_calendar c ON c.is_survey AND c.survey_seq = b.bn + l.lead_biz_d
    WHERE b.whsl_prc_lag1 IS NOT NULL
)
SELECT
    e.base_dt, e.item_nm, e.lead_biz_d::SMALLINT, e.target_dt,
    e.whsl_prc_lag1, e.whsl_prc_lag3, e.whsl_prc_lag7, ly.prc_prev_yr,
    e.whsl_prc_avg7, e.whsl_prc_avg14, e.whsl_prc_std7,
    st.stn_nm, wx.temp_avg, wx.rain_sum7, wx.rain_sum30,
    CASE WHEN st.gdd_base_c = 4.0 THEN wx.gdd30_base4 ELSE wx.gdd30_base5 END,
    mk.temp_avg,
    CASE EXTRACT(DOW FROM e.target_dt)
        WHEN 0 THEN '일' WHEN 1 THEN '월' WHEN 2 THEN '화' WHEN 3 THEN '수'
        WHEN 4 THEN '목' WHEN 5 THEN '금' WHEN 6 THEN '토' END,
    CASE WHEN EXTRACT(MONTH FROM e.target_dt) = 11
           OR (EXTRACT(MONTH FROM e.target_dt) = 12 AND EXTRACT(DAY FROM e.target_dt) <= 15)
         THEN 1 ELSE 0 END,
    (SELECT MIN(h.d - e.target_dt) FROM tmp_holiday h WHERE h.d >= e.target_dt),
    e.market_closed_lag1_yn::SMALLINT,
    area.crop_area_yoy_rt,
    ec.m2_yoy_rt, ec.epu_idx, ec.ppi_idx,
    rt.prc,
    sch.school_open_ratio
FROM expanded e
LEFT JOIN LATERAL (
    SELECT r.stn_nm, r.gdd_base_c, r.krei_variety_pat
    FROM ref_item_station r
    WHERE r.item_nm = e.item_nm
      AND EXTRACT(MONTH FROM e.target_dt)::INT BETWEEN r.mon_from AND r.mon_to
    LIMIT 1
) st ON TRUE
LEFT JOIN LATERAL (
    SELECT AVG(p.prc)::NUMERIC(15,3) AS prc_prev_yr
    FROM tmp_px p
    WHERE p.item_nm = e.item_nm
      AND p.dt BETWEEN e.target_dt - 368 AND e.target_dt - 362
) ly ON TRUE
LEFT JOIN tmp_wx wx ON wx.stn_nm = st.stn_nm AND wx.dt = e.base_dt - 1
LEFT JOIN tmp_wx mk ON mk.stn_nm = '서울'      AND mk.dt = e.base_dt - 1
LEFT JOIN LATERAL (
    SELECT r.prc FROM tmp_rtl r
    WHERE r.item_nm = e.item_nm AND r.dt < e.base_dt
    ORDER BY r.dt DESC LIMIT 1
) rt ON TRUE
LEFT JOIN LATERAL (
    WITH cand AS (
        SELECT DISTINCT k.item_variety_kr, k.report_mon, k.yoy_chg_rt
        FROM krei_production_yearly_raw k
        WHERE k.item_nm_kr = e.item_nm
          AND k.yoy_chg_rt IS NOT NULL
          AND to_date(k.report_mon, 'YYYY-MM') <= e.base_dt
          AND (st.krei_variety_pat IS NULL
               OR k.item_variety_kr ~ st.krei_variety_pat)
    )
    SELECT ROUND(AVG((
        SELECT AVG(m[1]::NUMERIC)
        FROM regexp_matches(translate(c.yoy_chg_rt, '△▽', '--'),
                            '-?[0-9]+(?:\.[0-9]+)?', 'g') AS m
    )), 3)::NUMERIC(10,3) AS crop_area_yoy_rt
    FROM cand c
    WHERE c.report_mon = (SELECT MAX(report_mon) FROM cand)
) area ON TRUE
LEFT JOIN econ_daily_raw ec ON ec.dt::DATE = e.base_dt
LEFT JOIN ref_school_day sch ON sch.dt = e.target_dt;

-- ── feature 채우기 — STEP 3·4·5 원문 복제 ──────────────────────────────
UPDATE predict_input t
SET prod_area_clim_temp_avg10 = CASE WHEN c.yr_cnt >= 3 THEN c.clim_temp END,
    prod_area_clim_yr_cnt     = c.yr_cnt
FROM tmp_clim c
WHERE c.base_dt = t.base_dt
  AND c.stn_nm  = t.prod_area_stn_nm;

UPDATE predict_input t
SET arr_qty_lag1 = (
        SELECT v.total_ton FROM tmp_vol v
        WHERE v.item_label = t.item_nm
          AND v.req_date  <= t.base_dt      -- 기준일까지 수집 완료된 것만
          AND v.base_date <  t.base_dt      -- 당일 물량 제외
        ORDER BY v.base_date DESC LIMIT 1),
    arr_qty_avg7 = (
        SELECT ROUND(v.ma7_ton, 3) FROM tmp_vol v
        WHERE v.item_label = t.item_nm
          AND v.req_date <= t.base_dt AND v.base_date < t.base_dt
        ORDER BY v.base_date DESC LIMIT 1),
    arr_qty_asof_date = (
        SELECT v.base_date FROM tmp_vol v
        WHERE v.item_label = t.item_nm
          AND v.req_date <= t.base_dt AND v.base_date < t.base_dt
        ORDER BY v.base_date DESC LIMIT 1),
    arr_top1_region = (
        SELECT v.top1_region FROM tmp_vol v
        WHERE v.item_label = t.item_nm
          AND v.req_date <= t.base_dt AND v.base_date < t.base_dt
        ORDER BY v.base_date DESC LIMIT 1)
WHERE EXISTS (SELECT 1 FROM tmp_vol v WHERE v.item_label = t.item_nm);

UPDATE predict_input t
SET arr_qty_prev_yr = (
        SELECT ROUND(AVG(v.total_ton), 3) FROM tmp_vol v
        WHERE v.item_label = t.item_nm
          AND v.total_ton > 0
          AND v.base_date BETWEEN t.target_dt - 368 AND t.target_dt - 362)
WHERE EXISTS (SELECT 1 FROM tmp_vol v WHERE v.item_label = t.item_nm);

UPDATE predict_input t
SET auc_prc_lag1 = (
        SELECT a.prc FROM tmp_auc a
        WHERE a.item_nm = t.item_nm AND a.dt < t.base_dt
        ORDER BY a.dt DESC LIMIT 1),
    auc_prc_lag3 = (
        SELECT a.prc_lag3 FROM tmp_auc a
        WHERE a.item_nm = t.item_nm AND a.dt < t.base_dt
        ORDER BY a.dt DESC LIMIT 1),
    auc_prc_avg7 = (
        SELECT a.prc_avg7 FROM tmp_auc a
        WHERE a.item_nm = t.item_nm AND a.dt < t.base_dt
        ORDER BY a.dt DESC LIMIT 1),
    auc_prc_spread_lag1 = (
        SELECT a.spread FROM tmp_auc a
        WHERE a.item_nm = t.item_nm AND a.dt < t.base_dt
        ORDER BY a.dt DESC LIMIT 1),
    auc_vol_lag1 = (
        SELECT a.vol FROM tmp_auc a
        WHERE a.item_nm = t.item_nm AND a.dt < t.base_dt
        ORDER BY a.dt DESC LIMIT 1),
    auc_prc_lag7 = (
        SELECT a.prc_lag7 FROM tmp_auc a
        WHERE a.item_nm = t.item_nm AND a.dt < t.base_dt
        ORDER BY a.dt DESC LIMIT 1),
    auc_prc_avg14 = (
        SELECT a.prc_avg14 FROM tmp_auc a
        WHERE a.item_nm = t.item_nm AND a.dt < t.base_dt
        ORDER BY a.dt DESC LIMIT 1),
    auc_prc_std7 = (
        SELECT a.prc_std7 FROM tmp_auc a
        WHERE a.item_nm = t.item_nm AND a.dt < t.base_dt
        ORDER BY a.dt DESC LIMIT 1)
WHERE EXISTS (SELECT 1 FROM tmp_auc a WHERE a.item_nm = t.item_nm);

-- 경락가 전년 동시기 — 중도매가와 같은 정의 (대상일 -365일 ±3일 평균).
--   base_dt 가 아니라 **target_dt** 기준이다. 1년 전 값이므로 누출이 아니다.
UPDATE crop_price_train t
SET auc_prc_prev_yr = (
        SELECT AVG(a.prc)::NUMERIC(15,3) FROM tmp_auc a
        WHERE a.item_nm = t.item_nm
          AND a.dt BETWEEN t.target_dt - 368 AND t.target_dt - 362)
WHERE EXISTS (SELECT 1 FROM tmp_auc a WHERE a.item_nm = t.item_nm);

UPDATE predict_input
SET auc_whsl_ratio_lag1 = ROUND(whsl_prc_lag1 / NULLIF(auc_prc_lag1, 0), 4)
WHERE whsl_prc_lag1 IS NOT NULL AND auc_prc_lag1 IS NOT NULL;

CREATE INDEX ix_predict_input ON predict_input(base_dt, item_nm, lead_biz_d);

-- ── 신선도 경고 ────────────────────────────────────────────────────────
--   가장 나쁜 사고는 몇 달 전 가격을 앵커로 삼아 "오늘의 예측" 을 내놓는 것이다.
--   예외가 아니라 그럴듯한 숫자로 나오므로 여기서 소리를 내야 한다.
DO $$
DECLARE mx date; lag_d int; n int;
BEGIN
    SELECT MAX(base_dt), COUNT(*) INTO mx, n FROM predict_input;
    IF n = 0 THEN
        RAISE WARNING 'predict_input 이 비었습니다. tmp_px 또는 ref_calendar 를 확인하세요.';
        RETURN;
    END IF;
    lag_d := current_date - mx;
    RAISE NOTICE 'predict_input %건 · 최신 기준일 % (지연 %일)', n, mx, lag_d;
    IF lag_d > 3 THEN
        RAISE WARNING
          '중도매가 RAW 가 %일 뒤처져 있습니다 (최신 기준일 %). 앵커가 낡았으므로 '
          '이 입력으로 낸 예측을 오늘 값으로 쓰지 마세요. 수집기를 먼저 돌리세요.',
          lag_d, mx;
    END IF;
END $$;


-- ############################################################
-- ## 검증 (결과 탭 7개 생성)
-- ############################################################

-- ============================================================================
-- 적재 검증 — 이 결과를 반드시 눈으로 확인한 뒤 학습으로 넘어갈 것
-- ============================================================================

-- ── 1) 품목별 적재 요약 ─────────────────────────────
--    확인: 배추/양파 kg당 수백~수천원. 만원대면 단위 정규화 실패
SELECT item_nm,
       COUNT(*)                        AS rows,
       MIN(base_dt)                    AS from_dt,
       MAX(base_dt)                    AS to_dt,
       COUNT(DISTINCT lead_biz_d)      AS leads,
       ROUND(MIN(target_whsl_prc))     AS 최저가,
       ROUND(AVG(target_whsl_prc))     AS 평균가,
       ROUND(MAX(target_whsl_prc))     AS 최고가
FROM crop_price_train GROUP BY 1 ORDER BY 1;

-- ── 2) 관측소 매칭 검증 ─────────────────────────────
--    확인: temp_null 이 rows 와 같으면 관측소명 불일치 (조용한 실패)
SELECT prod_area_stn_nm,
       COUNT(*) AS rows,
       COUNT(*) FILTER (WHERE prod_area_temp_avg_lag1 IS NULL)   AS temp_null,
       COUNT(*) FILTER (WHERE prod_area_gdd_sum30 IS NULL)       AS gdd_null,
       COUNT(*) FILTER (WHERE prod_area_clim_temp_avg10 IS NULL) AS clim_null
FROM crop_price_train GROUP BY 1 ORDER BY 1;

-- ── 3) 누수 검사 ────────────────────────────────────
--    확인: 전부 0 이어야 정상
SELECT 'target_dt <= base_dt'                    AS 검사항목, COUNT(*) AS 위반
  FROM crop_price_train WHERE target_dt <= base_dt
UNION ALL
SELECT 'lead_biz_d 범위 이탈', COUNT(*)
  FROM crop_price_train WHERE lead_biz_d NOT BETWEEN 1 AND 18
UNION ALL
SELECT '반입량 asof 가 기준일 이후', COUNT(*)
  FROM crop_price_train WHERE arr_qty_asof_date >= base_dt
UNION ALL
SELECT '타겟 NULL', COUNT(*)
  FROM crop_price_train WHERE target_whsl_prc IS NULL;

-- ── 4) 연도별 feature 채움률 (%) ────────────────────
--    확인: 반입량은 2021 이후만, KREI 는 2025 만 채워지는 것이 정상
SELECT EXTRACT(YEAR FROM base_dt)::INT AS yr,
       COUNT(*) AS rows,
       ROUND(100.0*COUNT(whsl_prc_lag1)            /COUNT(*),1) AS 가격lag,
       ROUND(100.0*COUNT(whsl_prc_prev_yr)         /COUNT(*),1) AS 전년앵커,
       ROUND(100.0*COUNT(prod_area_temp_avg_lag1)  /COUNT(*),1) AS 산지기온,
       ROUND(100.0*COUNT(prod_area_clim_temp_avg10)/COUNT(*),1) AS 평년기온,
       ROUND(100.0*COUNT(arr_qty_lag1)             /COUNT(*),1) AS 반입량,
       ROUND(100.0*COUNT(crop_area_yoy_rt)         /COUNT(*),1) AS 재배면적,
       ROUND(100.0*COUNT(m2_growth_rt)             /COUNT(*),1) AS 경제
FROM crop_price_train GROUP BY 1 ORDER BY 1;

-- ── 5) 반입량 결합 상세 (배추) ──────────────────────
--    확인: 평균지연 1~2일. 3일 초과면 as-of 조건 재검토
SELECT EXTRACT(YEAR FROM base_dt)::INT AS yr,
       COUNT(*) AS rows,
       COUNT(arr_qty_lag1) AS 채움,
       ROUND(AVG(base_dt - arr_qty_asof_date),2) AS 평균지연일,
       MAX(base_dt - arr_qty_asof_date)          AS 최대지연일,
       ROUND(AVG(arr_qty_lag1))                  AS 평균물량톤
FROM crop_price_train
WHERE item_nm = '배추' AND arr_qty_lag1 IS NOT NULL
GROUP BY 1 ORDER BY 1;

-- ── 6) 주산지 매핑 vs 실제 1위 산지 ─────────────────
--    확인: 매핑 관측소가 실산지와 같은 권역인지
SELECT EXTRACT(MONTH FROM target_dt)::INT AS mon,
       prod_area_stn_nm AS 매핑관측소,
       arr_top1_region  AS 실제1위산지,
       COUNT(*) AS cnt
FROM crop_price_train
WHERE item_nm='배추' AND arr_top1_region IS NOT NULL
GROUP BY 1,2,3 HAVING COUNT(*) > 100
ORDER BY 1, cnt DESC;

-- ── 7) 실제 적재 범위 확인 ★ ─────────────────────────
--    화면 라벨이 아니라 이 결과의 최소·최대 날짜로 판단할 것
SELECT MIN(base_dt)              AS 최소기준일,
       MAX(base_dt)              AS 최대기준일,
       COUNT(*)                  AS 행수,
       COUNT(DISTINCT base_dt)   AS 고유기준일,
       COUNT(DISTINCT item_nm)   AS 품목수
FROM crop_price_train;

-- ── 8) 권장 분할 미리보기 (학습 ~2022 / 검증 2023 / 테스트 2024~) ──
SELECT CASE WHEN base_dt <= '2022-12-31' THEN 'A. 학습(2015~2022)'
            WHEN base_dt <= '2023-12-31' THEN 'B. 검증(2023)'
            ELSE 'C. 테스트(2024~) ★봉인' END AS 구간,
       COUNT(*)                  AS rows,
       COUNT(DISTINCT base_dt)   AS 기준일,
       ROUND(100.0*COUNT(arr_qty_lag1)/COUNT(*),1) AS 반입량채움률
FROM crop_price_train GROUP BY 1 ORDER BY 1;


-- ── 9) 타겟 3종 채움률과 가격 위계 ★ ────────────────
--    확인: 경락가 < 중도매가 < 소매가 순으로 비싸야 정상
SELECT item_nm,
       ROUND(100.0*COUNT(target_auc_prc) /COUNT(*),1) AS "경락가_채움%",
       ROUND(100.0*COUNT(target_whsl_prc)/COUNT(*),1) AS "중도매_채움%",
       ROUND(100.0*COUNT(target_rtl_prc) /COUNT(*),1) AS "소매_채움%",
       ROUND(AVG(target_auc_prc))  AS "경락가",
       ROUND(AVG(target_whsl_prc)) AS "중도매가",
       ROUND(AVG(target_rtl_prc))  AS "소매가"
FROM crop_price_train GROUP BY 1 ORDER BY 1;

-- ── 10) 모델별 학습 가능 행수 ───────────────────────
--    타겟과 앵커가 모두 있어야 학습에 쓸 수 있다
SELECT '경락가 모델'   AS 모델, COUNT(*) AS 학습가능행수
  FROM crop_price_train WHERE target_auc_prc IS NOT NULL AND auc_prc_lag1 IS NOT NULL
UNION ALL
SELECT '중도매가 모델', COUNT(*)
  FROM crop_price_train WHERE target_whsl_prc IS NOT NULL AND whsl_prc_lag1 IS NOT NULL
UNION ALL
SELECT '소매가 모델',   COUNT(*)
  FROM crop_price_train WHERE target_rtl_prc IS NOT NULL AND rtl_prc_lag1 IS NOT NULL;

-- ── 11) 품목별 주산지 매핑 적용 결과 ────────────────
SELECT item_nm, EXTRACT(MONTH FROM target_dt)::INT AS mon,
       prod_area_stn_nm AS 관측소, COUNT(*) AS rows
FROM crop_price_train
GROUP BY 1,2,3 ORDER BY 1,2;

-- ── 12) 소매가 집계 기준 검사 ★ ─────────────────────
--    소매 앵커·타겟이 서울(1101) 기준으로 만들어졌는지 원본에서 재계산해 대조한다.
--    전국 평균으로 새면 학습 구간과 검증 구간의 조사 점포 수가 달라져
--    (2023년 44 → 59개) 성능이 조용히 왜곡된다. 과거 후처리 SQL 로 고쳤다가
--    그 파일을 잃어버려 재현이 끊긴 이력이 있으므로 여기서 상시 검사한다.
--
--    확인: 두 행 모두 불일치 0 이어야 정상. 1건이라도 나오면 소매 모델 학습 금지.
WITH seoul AS (
    -- ★ tmp_rtl / tmp_rtl_t 와 같은 기준이어야 2026 이후 오탐이 안 난다 (2026-09-03)
    SELECT exmn_ymd AS dt,
    CASE item_cd WHEN '211' THEN '배추' WHEN '245' THEN '양파'
                 WHEN '231' THEN '무'   WHEN '244' THEN '마늘' END AS item_nm,
           AVG(exmn_dd_prc / NULLIF(unit_sz,0))::NUMERIC(15,3) AS prc
    FROM veg_daily_price_raw
    WHERE se_cd = '01' AND grd_cd = '04' AND sgg_cd = '1101'
      AND item_cd IN ('211','245','231','244')
      AND exmn_dd_prc IS NOT NULL AND unit_sz > 0
    GROUP BY 1, 2
),
-- 앵커는 as-of(기준일 이전 최신)라 달력 -1 일이 아니다. 행마다 LATERAL 로 훑으면
-- 14만 행 × 시계열 스캔이 되므로, 각 관측일이 유효한 구간(dt, next_dt] 을 만들어
-- 범위 조인 한 번으로 끝낸다.
seoul_span AS (
    SELECT item_nm, dt, prc,
           LEAD(dt) OVER (PARTITION BY item_nm ORDER BY dt) AS next_dt
    FROM seoul
),
-- rtl_prc_lag1 은 (품목 × 기준일) 안에서 리드타임 18행이 모두 같은 값이므로
-- 중복을 걷어내고 대조한다
anchor_pt AS (
    SELECT DISTINCT item_nm, base_dt, rtl_prc_lag1
    FROM crop_price_train WHERE rtl_prc_lag1 IS NOT NULL
)
SELECT 'target_rtl_prc' AS 대상, '행' AS 단위, COUNT(*) AS 대조건수,
       COUNT(*) FILTER (WHERE ABS(t.target_rtl_prc - s.prc) > 0.01) AS 불일치
  FROM crop_price_train t
  JOIN seoul s ON s.item_nm = t.item_nm AND s.dt = t.target_dt
 WHERE t.target_rtl_prc IS NOT NULL
UNION ALL
SELECT 'rtl_prc_lag1', '품목×기준일', COUNT(*),
       COUNT(*) FILTER (WHERE ABS(a.rtl_prc_lag1 - s.prc) > 0.01)
  FROM anchor_pt a
  JOIN seoul_span s ON s.item_nm = a.item_nm
                   AND a.base_dt >  s.dt
                   AND (s.next_dt IS NULL OR a.base_dt <= s.next_dt);


-- ---------------------------------------------------------------------------
-- [13] 학사일정 결합 검사  (v5.2)
--   확인 ① 결측 0 — ref_school_day 는 2015~2028 전 구간이 채워져 있으므로
--                   NULL 이 나오면 조인이 어긋났거나 테이블이 없는 것이다.
--        ② 방학중 비율이 학기중보다 낮아야 한다 (1~2월·8월 vs 3~6월·9~11월).
--           뒤집혀 있으면 대상일이 아니라 기준일로 붙였거나 프로파일이 잘못된 것.
-- ---------------------------------------------------------------------------
SELECT CASE WHEN EXTRACT(MONTH FROM target_dt) IN (1,2,8) THEN '방학기(1·2·8월)'
            WHEN EXTRACT(MONTH FROM target_dt) IN (3,4,5,6,9,10,11) THEN '학기중'
            ELSE '전환기(7·12월)' END                      AS 구간,
       COUNT(*)                                            AS 행수,
       COUNT(*) FILTER (WHERE school_open_ratio IS NULL)   AS 결측,
       ROUND(AVG(school_open_ratio), 3)                    AS 평균개교율
FROM crop_price_train
GROUP BY 1 ORDER BY 4;


-- ---------------------------------------------------------------------------
-- [14] predict_input 대조  (v5.2)
--   STEP 8 은 STEP 3·4·5 의 UPDATE 를 복제한 것이다. 복제본이 원본과 갈라지면
--   학습과 추론의 계산식이 달라지고, 그때 나오는 건 예외가 아니라 그럴듯하게
--   틀린 값이다. 겹치는 (기준일·품목·리드타임)을 **전 컬럼** 대조해 잡는다.
--
--   확인 ① 불일치 0. 1건이라도 나오면 STEP 8 과 STEP 3·4·5 가 갈라진 것이다.
--        ② 대조행이 0 이면 대조가 성립하지 않은 것이다(겹치는 구간 없음).
--           tmp_pi_cfg.n_base 를 늘릴 것.
--        ③ 지연일 — 3일을 넘으면 앵커가 낡았다. 예측을 오늘 값으로 쓰지 말 것.
-- ---------------------------------------------------------------------------
WITH cmp AS (
    SELECT (to_jsonb(p) - 'target_whsl_prc' - 'target_auc_prc' - 'target_rtl_prc') AS pj,
           (to_jsonb(t) - 'id' - 'created_at'
                        - 'target_whsl_prc' - 'target_auc_prc' - 'target_rtl_prc') AS tj
    FROM predict_input p
    JOIN crop_price_train t USING (base_dt, item_nm, lead_biz_d)
)
SELECT 'feature 대조'                                  AS 항목,
       COUNT(*)                                        AS 대조행,
       COUNT(*) FILTER (WHERE pj IS DISTINCT FROM tj)  AS 불일치
FROM cmp
UNION ALL
SELECT '미래 대상일 (학습 범위 밖)',
       COUNT(*),
       COUNT(*) FILTER (WHERE target_dt > (SELECT MAX(target_dt) FROM crop_price_train))
FROM predict_input
UNION ALL
SELECT '데이터 지연(일) — 3 초과면 앵커가 낡음',
       (current_date - MAX(base_dt)),
       COUNT(*) FILTER (WHERE whsl_prc_lag1 IS NULL)
FROM predict_input;


-- [15] 파생 컬럼 대칭 검사  (v5.3 · 2026-08-27)
--   세 가격 계열이 같은 파생 컬럼 세트를 갖는지 본다.
--   중도매만 7종이고 경락 3종·소매 1종이던 비대칭을 고친 뒤의 확인용이다.
--   결측률이 중도매와 크게 다르면 창 계산이나 as-of 결합이 어긋난 것이다.
SELECT '경락'  AS 계열,
       ROUND(100.0*COUNT(*) FILTER (WHERE auc_prc_lag1    IS NULL)/COUNT(*),2) AS lag1,
       ROUND(100.0*COUNT(*) FILTER (WHERE auc_prc_lag3    IS NULL)/COUNT(*),2) AS lag3,
       ROUND(100.0*COUNT(*) FILTER (WHERE auc_prc_lag7    IS NULL)/COUNT(*),2) AS lag7,
       ROUND(100.0*COUNT(*) FILTER (WHERE auc_prc_avg7    IS NULL)/COUNT(*),2) AS avg7,
       ROUND(100.0*COUNT(*) FILTER (WHERE auc_prc_avg14   IS NULL)/COUNT(*),2) AS avg14,
       ROUND(100.0*COUNT(*) FILTER (WHERE auc_prc_std7    IS NULL)/COUNT(*),2) AS std7,
       ROUND(100.0*COUNT(*) FILTER (WHERE auc_prc_prev_yr IS NULL)/COUNT(*),2) AS prev_yr
  FROM crop_price_train WHERE base_dt >= '2017-01-01'
UNION ALL
SELECT '중도매',
       ROUND(100.0*COUNT(*) FILTER (WHERE whsl_prc_lag1    IS NULL)/COUNT(*),2),
       ROUND(100.0*COUNT(*) FILTER (WHERE whsl_prc_lag3    IS NULL)/COUNT(*),2),
       ROUND(100.0*COUNT(*) FILTER (WHERE whsl_prc_lag7    IS NULL)/COUNT(*),2),
       ROUND(100.0*COUNT(*) FILTER (WHERE whsl_prc_avg7    IS NULL)/COUNT(*),2),
       ROUND(100.0*COUNT(*) FILTER (WHERE whsl_prc_avg14   IS NULL)/COUNT(*),2),
       ROUND(100.0*COUNT(*) FILTER (WHERE whsl_prc_std7    IS NULL)/COUNT(*),2),
       ROUND(100.0*COUNT(*) FILTER (WHERE whsl_prc_prev_yr IS NULL)/COUNT(*),2)
  FROM crop_price_train WHERE base_dt >= '2017-01-01'
UNION ALL
SELECT '소매',
       ROUND(100.0*COUNT(*) FILTER (WHERE rtl_prc_lag1    IS NULL)/COUNT(*),2),
       ROUND(100.0*COUNT(*) FILTER (WHERE rtl_prc_lag3    IS NULL)/COUNT(*),2),
       ROUND(100.0*COUNT(*) FILTER (WHERE rtl_prc_lag7    IS NULL)/COUNT(*),2),
       ROUND(100.0*COUNT(*) FILTER (WHERE rtl_prc_avg7    IS NULL)/COUNT(*),2),
       ROUND(100.0*COUNT(*) FILTER (WHERE rtl_prc_avg14   IS NULL)/COUNT(*),2),
       ROUND(100.0*COUNT(*) FILTER (WHERE rtl_prc_std7    IS NULL)/COUNT(*),2),
       ROUND(100.0*COUNT(*) FILTER (WHERE rtl_prc_prev_yr IS NULL)/COUNT(*),2)
  FROM crop_price_train WHERE base_dt >= '2017-01-01';
