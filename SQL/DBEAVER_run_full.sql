-- ============================================================================
-- crop_price_train 전체 재적재 — DBeaver 실행용  v4.0
--
-- ▣ 이번 실행 범위
--      대상 품목    : 배추 · 양파
--      적재 기준일  : 2015-01-01 ~ 2025-12-31
--      권장 분할    : 학습 2019~2022 / 검증 2023 / 테스트 2024~ (봉인)
--
-- ▣ v4.0 변경 — daily_volume 확장 반영
--   1. 반입량 전 기간 확보
--      기존 2021-05-29~ → 2015-01~ 로 확장되어 arr_qty_* 를 학습 전 구간에서
--      사용할 수 있게 됐다. 배추 연 295~306일, 양파 연 244~304일.
--   2. 양파 산지 데이터 확보 → 매핑 검증 완료
--      1~3·5~12월 전남 무안군 87~100% 로 압도적. 목포 매핑이 정확했음.
--      단 4월만 제주 제주시 53% 로 조생종 출하기 → 제주로 분리.
--   3. 품목 확장 : 배추 → 배추 + 양파
--
-- ▣ 시대별 주산지 이동 (참고 — 매핑은 최근 기준으로 고정)
--      배추 5월  2015-19 해남 44%  →  2020-25 예산 64%
--      배추 8월  2015-19 태백 53%  →  2020-25 평창 43%  (둘 다 강원)
--      양파 4월  2015-19 무안 70%  →  2020-25 제주 53%
--    학습량 곡선에서 2019년 시작이 최적(+11.2%)이므로 최근 기준을 채택한다.
--    학습 구간을 2019~ 로 좁히면 시대 이동 문제가 자연히 해소된다.
--
-- ▣ 실행 방법
--      DBeaver 에서 이 파일을 열고 [Alt+X] (Execute script) 로 전체 실행.
--      ※ Ctrl+Enter 는 커서 위치의 한 문장만 실행되므로 사용 금지.
--      ※ 품목 2개 × 11년이라 수 분 소요될 수 있다.
--
-- ▣ 파라미터를 바꾸려면 (본문에서 해당 문자열을 찾아 수정)
--      품목 확장    : item_nm IN ('배추','양파')  →  무·마늘 추가 시 여기
--      기간 변경    : BETWEEN '2015-01-01'::DATE AND '2025-12-31'::DATE
--      시장 변경    : mrkt_nm = '가락도매'
--
-- ▣ 재실행 안전
--      맨 앞에서 TRUNCATE RESTART IDENTITY 하므로 필터를 바꿔 재실행해도
--      이전 조건의 행이 남지 않고 id 도 1부터 시작한다.
--
-- ▣ 실행 후 반드시 확인 (하단 결과 탭)
--      [2) 관측소 매칭] temp_null 이 rows 와 같으면 관측소명 불일치 → 학습 금지
--      [3) 누수 검사]  4개 항목 모두 0 이어야 정상
--      [5) 반입량 결합] 2015년부터 채움률이 100% 에 가까워야 정상
--      [7) 실제 적재 범위] 최소기준일이 2015-01 인지 확인
-- ============================================================================


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
        IF EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='crop_price_train' AND column_name=r.old_nm)
        THEN
            EXECUTE format('ALTER TABLE crop_price_train RENAME COLUMN %I TO %I', r.old_nm, r.new_nm);
            RAISE NOTICE '컬럼명 변경: % -> %', r.old_nm, r.new_nm;
        END IF;
    END LOOP;
END $$;

-- 소매가 보조 feature (유통 마진 스프레드 실험용)
ALTER TABLE crop_price_train ADD COLUMN IF NOT EXISTS rtl_prc_lag1 NUMERIC(15,3);

COMMENT ON COLUMN crop_price_train.target_whsl_prc IS
  '대상일 중도매인 판매가(원/kg). 출처 veg_daily_price_raw se_cd=02, grd_cd=04, 가락도매. 경락가 아님';
COMMENT ON COLUMN crop_price_train.whsl_prc_lag1 IS '직전 영업일 중도매인 판매가(원/kg)';
COMMENT ON COLUMN crop_price_train.whsl_prc_prev_yr IS '대상일 -365일 ±3일 중도매인 판매가 평균(원/kg)';
COMMENT ON COLUMN crop_price_train.rtl_prc_lag1 IS
  '직전 소매가(원/단위). se_cd=01. 품목별로 단위가 다르므로 스프레드 파생 금지';


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
-- 배추: daily_volume 실측 기반
('배추',  1,  4, '해남',   '월동배추',      5.0, '겨울|월동', '전남 해남군 76~100%. 2위 진도군. 시대 무관 안정'),
('배추',  5,  5, '홍성',   '봄배추(충남)',  5.0, '봄', '2020~ 충남 예산군 64%. 2015~19 는 해남 44% 였으나 최근 기준 채택'),
('배추',  6,  6, '대관령', '고랭지 전환기', 5.0, '여름|고랭지', '강원 52%(횡성·평창) 경북 30%(문경). 전환기라 산지 분산'),
('배추',  7,  8, '대관령', '고랭지배추',    5.0, '여름|고랭지', '강원 평창군 89~92%. 7월은 시대 무관 안정'),
('배추',  9,  9, '강릉',   '고랭지(강릉)',  5.0, '여름|고랭지', '강원 강릉시 23,755t로 평창 14,311t 상회'),
('배추', 10, 10, '대관령', '고랭지 후기',   5.0, '가을', '강원 평창군 88%. v2에서 해남으로 잘못 매핑했던 구간'),
('배추', 11, 12, '해남',   '가을·월동배추', 5.0, '가을|겨울|월동', '전남 해남군 70~98%. 11월은 강원 춘천 24% 혼재'),

-- 무: daily_volume 미확보 품목. 도메인 추정 유지 (검증 필요)
('무',    1,  3, '제주',   '월동무(추정)',  5.0, '겨울|월동', '※ 실산지 데이터 미확보 — 추정치'),
('무',    4,  6, '고창군', '봄무(추정)',    5.0, '봄', '※ 실산지 데이터 미확보 — 추정치'),
('무',    7,  9, '대관령', '고랭지무(추정)',5.0, '여름|고랭지', '※ 실산지 데이터 미확보 — 추정치'),
('무',   10, 12, '제주',   '월동무(추정)',  5.0, '가을|겨울|월동', '※ 실산지 데이터 미확보 — 추정치'),

-- 양파: ASOS 무안 지점 부재로 인접 목포 사용
('양파',  1,  3, '목포',   '중만생종',      5.0, '중만생종', '전남 무안군 87~96%. ASOS 무안 부재 → 인접 목포 대체'),
('양파',  4,  4, '제주',   '조생종',        5.0, '조생종',   '제주 제주시 53%(2020~). 조생종 출하기 — 실측 기반 분리'),
('양파',  5, 12, '목포',   '중만생종',      5.0, '중만생종', '전남 무안군 98~100%. 연중 가장 안정적인 구간'),

-- 마늘: 난지형/한지형
('마늘',  1,  6, '합천',   '난지형(추정)',  4.0, NULL, '※ 실산지 데이터 미확보 — 추정치'),
('마늘',  7, 12, '서산',   '한지형(추정)',  4.0, NULL, '※ 실산지 데이터 미확보 — 추정치');

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
DROP TABLE IF EXISTS tmp_px;
CREATE TEMP TABLE tmp_px AS
SELECT dt, item_nm,
       AVG(prc_per_kg)::NUMERIC(15,3) AS prc,
       ROW_NUMBER() OVER (PARTITION BY item_nm ORDER BY dt) AS bn
FROM (
    SELECT exmn_ymd AS dt, item_nm,
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
      AND item_nm IN ('배추','양파')   -- 대상 품목
      AND exmn_dd_prc IS NOT NULL
      AND unit_sz > 0
) x
WHERE prc_per_kg IS NOT NULL
GROUP BY dt, item_nm;

CREATE INDEX ix_tmp_px_dt ON tmp_px(item_nm, dt);
CREATE INDEX ix_tmp_px_bn ON tmp_px(item_nm, bn);

-- STEP 2. 소매 시계열 (보조 feature)
--   ⚠ 배추 소매는 '포기' 단위라 kg 환산 불가 → 품목별로 스케일이 다름.
--     따라서 (소매 − 중도매) 스프레드 파생은 하지 않는다. 모델이 품목별로
--     스케일을 흡수하도록 원단위 값 그대로 둔다.
DROP TABLE IF EXISTS tmp_rtl;
CREATE TEMP TABLE tmp_rtl AS
SELECT exmn_ymd AS dt, item_nm,
       AVG(exmn_dd_prc / NULLIF(unit_sz,0))::NUMERIC(15,3) AS prc
FROM veg_daily_price_raw
WHERE se_cd = '01' AND grd_cd = '04'
  AND item_nm IN ('배추','양파')
  AND exmn_dd_prc IS NOT NULL AND unit_sz > 0
GROUP BY exmn_ymd, item_nm;
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

-- STEP 4. 명절 캘린더 (→ ref_calendar 테이블로 분리 권장)
DROP TABLE IF EXISTS tmp_holiday;
CREATE TEMP TABLE tmp_holiday(d DATE);
INSERT INTO tmp_holiday VALUES
 ('2015-02-19'),('2015-09-27'),('2016-02-08'),('2016-09-15'),('2017-01-28'),('2017-10-04'),
 ('2018-02-16'),('2018-09-24'),('2019-02-05'),('2019-09-13'),('2020-01-25'),('2020-10-01'),
 ('2021-02-12'),('2021-09-21'),('2022-02-01'),('2022-09-10'),('2023-01-22'),('2023-09-29'),
 ('2024-02-10'),('2024-09-17'),('2025-01-29'),('2025-10-06'),('2026-02-17'),('2026-09-25');

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
    crop_area_yoy_rt, m2_growth_rt, epu_idx, ppi_idx, rtl_prc_lag1
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
    WHERE b.base_dt BETWEEN '2015-01-01'::DATE AND '2025-12-31'::DATE
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
    rt.prc
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

ON CONFLICT (base_dt, item_nm, lead_biz_d) DO UPDATE SET
    target_whsl_prc     = EXCLUDED.target_whsl_prc,
    whsl_prc_lag1       = EXCLUDED.whsl_prc_lag1,
    whsl_prc_prev_yr    = EXCLUDED.whsl_prc_prev_yr,
    prod_area_stn_nm    = EXCLUDED.prod_area_stn_nm,
    prod_area_gdd_sum30 = EXCLUDED.prod_area_gdd_sum30,
    rtl_prc_lag1        = EXCLUDED.rtl_prc_lag1,
    crop_area_yoy_rt    = EXCLUDED.crop_area_yoy_rt,
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



-- 어느 품목·월에서 NULL이 나는가
SELECT item_nm, EXTRACT(MONTH FROM target_dt)::int AS mon,
       COUNT(*) AS rows,
       ROUND(100.0*COUNT(*) FILTER (WHERE crop_area_yoy_rt IS NULL)/COUNT(*),1) AS null_pct
FROM crop_price_train
WHERE base_dt >= '2020-01-01'
GROUP BY 1,2 ORDER BY 1,2;