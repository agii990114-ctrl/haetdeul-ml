-- ============================================================================
-- 대상일 기준 평년 기온  (실험용 · 2026-08-31)
--
-- ## 왜 만드나
--
-- 예측이 18일 내내 거의 일직선이다. 실측:
--
--     한 기준일 안에서 리드타임 3~18 이 움직이는 폭
--       경락가 배추   예측 13.7%  vs  실제 137.8%   (0.10배)
--       소매가 양파   예측  2.5%  vs  실제  15.6%   (0.16배)
--
-- 원인을 재보니 **모델 입력 28개 중 17개가 한 기준일 안에서 전부 같은 값**
-- 이었다. 18행 내내 진짜로 움직이는 입력의 중요도 합계는 22.4% 뿐이다.
--
-- 그중 하나가 평년 기온이다.
--
--     지금 (prod_area_clim_temp_avg10)
--         기준일+1 ~ +10일 을 뭉뚱그린 한 값. 리드타임과 무관하게 고정.
--         2025-12-31 배추 = 1.557도가 18행 내내 같음.
--
--     여기서 만드는 것 (prod_area_clim_temp_tgt)
--         **그 행의 대상일** 기준. LT1 은 1/2 의 평년값, LT18 은 1/27 의 평년값.
--
-- 이미 있는 관측 자료만 쓴다. 새 수집이 필요 없다.
--
-- ## 누수 방지 — 기존 규칙을 그대로 따른다
--
--   · **기준일보다 이전 연도의 관측만** 쓴다. 같은 해와 이후 연도는 제외.
--   · 참조 연도가 3년 미만이면 NULL.
--
-- ## 하루가 아니라 ±3일 창을 쓰는 이유
--
-- 특정 하루의 기온은 해마다 크게 흔들린다. 8년 평균을 내도 들쭉날쭉하다.
-- ±3일(7일 창)로 넓히면 그 잡음이 줄고, 그래도 대상일마다 값이 달라진다.
-- 날씨 예보로 치면 "1월 14일 기온" 이 아니라 "1월 중순 기온" 이다.
--
-- ## 이건 아직 채택된 게 아니다
--
-- **폴드 두 개(검증 2022 · 검증 2023)에서 부호가 같고 편차×2 를 넘을 때만**
-- 채택한다 (CLAUDE.md §5.7). 학사일정도 그럴듯했는데 3폴드에서 기각됐다.
-- 그때까지 이 컬럼은 crop_price_train 에만 있고 v5 본문에는 넣지 않는다.
-- ============================================================================

ALTER TABLE crop_price_train
    ADD COLUMN IF NOT EXISTS prod_area_clim_temp_tgt NUMERIC(10,3),
    ADD COLUMN IF NOT EXISTS prod_area_clim_tgt_yr_cnt SMALLINT;

COMMENT ON COLUMN crop_price_train.prod_area_clim_temp_tgt IS
  '주산지 평년 기온(℃) — 대상일 기준. 대상일 ±3일의 과거 연도 평균. 기준일 이전 연도만 사용. 실험용(2026-08-31)';
COMMENT ON COLUMN crop_price_train.prod_area_clim_tgt_yr_cnt IS
  '위 평년값에 쓰인 과거 연도 수. 3년 미만이면 값을 NULL 로 둔다';

-- STEP 1. 관측 기온을 (관측소, 연, 날짜) 로 펼친다.
--   ±3일 창을 월/일로 맞추면 1월 1일 앞이나 12월 31일 뒤에서 끊긴다.
--   그래서 월/일이 아니라 **연중 일수(1~366)** 로 맞추고, 앞뒤로 넘어가는
--   경우를 모듈로로 이어붙인다.
DROP TABLE IF EXISTS tmp_climt_src;
CREATE TEMP TABLE tmp_climt_src AS
SELECT "stnNm"                                        AS stn_nm,
       EXTRACT(YEAR FROM "tm"::DATE)::INT             AS yr,
       EXTRACT(DOY  FROM "tm"::DATE)::INT             AS doy,
       "avgTa"::NUMERIC(10,3)                         AS temp_avg
FROM weather_asos_raw
WHERE "avgTa" IS NOT NULL;

CREATE INDEX ix_climt_src ON tmp_climt_src(stn_nm, doy, yr);

-- STEP 2. (기준일 연도 · 대상일 · 관측소) 조합마다 평년값을 계산한다.
--   기준일 연도가 들어가는 이유: 누수 방지 규칙이 "기준일 이전 연도만" 이라
--   같은 대상일이라도 기준일 연도가 다르면 쓸 수 있는 과거가 달라진다.
DROP TABLE IF EXISTS tmp_climt;
CREATE TEMP TABLE tmp_climt AS
SELECT k.base_yr, k.target_dt, k.stn_nm, c.clim_temp, c.yr_cnt
FROM (
    SELECT DISTINCT EXTRACT(YEAR FROM base_dt)::INT AS base_yr,
           target_dt, prod_area_stn_nm AS stn_nm
    FROM crop_price_train
    WHERE prod_area_stn_nm IS NOT NULL AND target_dt IS NOT NULL
) k
CROSS JOIN LATERAL (
    SELECT ROUND(AVG(s.temp_avg), 3)      AS clim_temp,
           COUNT(DISTINCT s.yr)::SMALLINT AS yr_cnt
    FROM tmp_climt_src s
    WHERE s.stn_nm = k.stn_nm
      AND s.yr     < k.base_yr                       -- ★ 기준일 이전 연도만
      -- 대상일 ±3일. 365 로 모듈로해 연말/연초를 이어붙인다.
      AND ((s.doy - EXTRACT(DOY FROM k.target_dt)::INT + 365 + 182) % 365) - 182
          BETWEEN -3 AND 3
) c;

CREATE INDEX ix_tmp_climt ON tmp_climt(base_yr, target_dt, stn_nm);

-- STEP 3. 확산
UPDATE crop_price_train t
SET prod_area_clim_temp_tgt   = CASE WHEN c.yr_cnt >= 3 THEN c.clim_temp END,
    prod_area_clim_tgt_yr_cnt = c.yr_cnt
FROM tmp_climt c
WHERE c.base_yr   = EXTRACT(YEAR FROM t.base_dt)::INT
  AND c.target_dt = t.target_dt
  AND c.stn_nm    = t.prod_area_stn_nm;

-- ============================================================================
-- 검증 — 세 가지를 본다
-- ============================================================================

-- [1] 결측률. 기존 컬럼과 비슷해야 한다 (둘 다 3년 규칙을 쓰므로)
SELECT '결측률' AS 검사,
       COUNT(*)                                                    AS 전체,
       COUNT(*) FILTER (WHERE prod_area_clim_temp_avg10 IS NULL)   AS 기존_결측,
       COUNT(*) FILTER (WHERE prod_area_clim_temp_tgt   IS NULL)   AS 신규_결측
FROM crop_price_train;

-- [2] ★ 핵심 — 한 기준일 안에서 값이 실제로 움직이나
--     기존은 1가지, 신규는 여러 가지여야 한다. 1가지면 만든 의미가 없다.
SELECT '기준일당 서로 다른 값' AS 검사,
       ROUND(AVG(n_old), 2) AS 기존, ROUND(AVG(n_new), 2) AS 신규
FROM (
    SELECT COUNT(DISTINCT prod_area_clim_temp_avg10) AS n_old,
           COUNT(DISTINCT prod_area_clim_temp_tgt)   AS n_new
    FROM crop_price_train
    WHERE item_nm IN ('배추','무','양파') AND base_dt >= '2017-01-01'
    GROUP BY base_dt, item_nm
) x;

-- [3] 누수 검사 — 대상일이 속한 연도의 관측이 섞이지 않았나
--     기준일 연도 이후의 관측을 썼다면 yr_cnt 가 기존보다 클 수 있다.
--     둘 다 '기준일 이전 연도만' 이므로 신규가 기존보다 크면 안 된다.
SELECT '누수 검사' AS 검사,
       COUNT(*) FILTER (WHERE prod_area_clim_tgt_yr_cnt > prod_area_clim_yr_cnt + 1) AS 의심행
FROM crop_price_train
WHERE prod_area_clim_yr_cnt IS NOT NULL AND prod_area_clim_tgt_yr_cnt IS NOT NULL;
