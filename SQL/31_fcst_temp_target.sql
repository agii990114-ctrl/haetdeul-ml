-- ============================================================================
-- 대상일 기온 예보를 학습표에 붙인다  (실험용 · 2026-08-31)
--
-- ## 왜
--
-- 우리 예측이 18일 내내 거의 일직선이다. 모델 입력 28개 중 17개가 한 기준일
-- 안에서 전부 같은 값이라, "1월 2일"과 "1월 27일"에 같은 이야기를 한다.
--
-- 지금 모델은 **어제까지의 날씨는 알지만 그날 날씨는 모른다.**
-- 중기 기온예보는 우리가 가진 것 중 **유일하게 "그날"을 말해주는 자료**다.
--
-- ## ★ 닿는 구간이 좁다 — 먼저 알고 시작한다
--
-- 실측 (2017~ · 배추·무·양파 · 기준일 이전 발표분만):
--
--     LT1~4   98~100%    (LT1~2 는 게이트라 모델을 안 쓴다)
--     LT5     92.7%
--     LT6     70.3%   ⚠
--     LT7     43.4%   ⚠
--     LT8~18   0%
--
-- **모델을 쓰는 16칸 중 LT3·4·5 세 칸만 덮는다.**
--
-- LT6·7 은 일부러 뺀다. 70%·43% 는 있는 것도 없는 것도 아니고, **결측이
-- 무작위가 아니라 달력 배치를 따라** 생긴다 (연휴 낀 주에는 없다). 모델이
-- 그걸 "이번 주에 연휴가 있나" 를 알아내는 표시로 쓴다. 경제 변수를 뺀
-- 이유(§5.2)와 똑같은 함정이다.
--
-- ## 누수 방지
--
--     tm_fc < base_dt      기준일보다 **앞서 발표된** 것만 쓴다
--     그중 가장 최근 발표    (보통 기준일 전날 18시)
--
-- 예보는 그 시각에 실제로 나와 있던 값이라, "그때 알 수 있었나" 가 자료
-- 자체에 남는다. 뉴스가 위험한 이유(날짜를 믿기 어려움)가 여기엔 없다.
--
-- ## 이건 아직 채택된 게 아니다
--
-- 폴드 두 개(검증 2022·2023)에서 부호가 같고 편차×2 를 넘을 때만 채택한다
-- (§5.7). 그때까지 v5 본문에 넣지 않는다.
-- ============================================================================

ALTER TABLE crop_price_train
    ADD COLUMN IF NOT EXISTS prod_area_fcst_temp_tgt NUMERIC(5,1),
    ADD COLUMN IF NOT EXISTS prod_area_fcst_age_h    SMALLINT;

COMMENT ON COLUMN crop_price_train.prod_area_fcst_temp_tgt IS
  '주산지 대상일 기온 예보(℃) = (최저+최고)/2. 기준일 이전 최신 발표분. '
  'LT3~5 만 채운다 (LT6+ 는 예보가 안 닿아 결측이 시점 식별자가 된다). '
  '실험용 · 2026-08-31';
COMMENT ON COLUMN crop_price_train.prod_area_fcst_age_h IS
  '그 예보가 기준일 기준 몇 시간 전에 발표됐나. 진단용이며 모델 입력이 아니다';

-- 이미 값이 있으면 비운다 (다시 돌릴 때 옛 값이 남지 않게)
UPDATE crop_price_train
   SET prod_area_fcst_temp_tgt = NULL, prod_area_fcst_age_h = NULL
 WHERE prod_area_fcst_temp_tgt IS NOT NULL OR prod_area_fcst_age_h IS NOT NULL;

-- ── 채우기 ───────────────────────────────────────────────────────────────
--   (관측소 × 대상일 × 기준일) 마다 **기준일 이전 최신 발표분**을 하나 고른다.
--   DISTINCT ON 이 그 일을 한 번에 한다 — ORDER BY 의 첫 행만 남긴다.
--
--   ★ 기준일 자체를 뺀다(tm_fc < base_dt). 기준일 06시 발표분을 쓰면 하루를
--     더 벌 수 있지만, 우리 앵커가 "기준일 이전 최신" 규칙을 쓰므로 맞춘다.
--     한쪽만 더 최신 정보를 쓰면 비교가 어긋난다.
DROP TABLE IF EXISTS tmp_fcst_pick;
CREATE TEMP TABLE tmp_fcst_pick AS
SELECT DISTINCT ON (k.base_dt, k.stn_nm, k.target_dt)
       k.base_dt, k.stn_nm, k.target_dt,
       ((f.min_ta + f.max_ta) / 2.0)::NUMERIC(5,1) AS fcst_temp,
       (EXTRACT(EPOCH FROM (k.base_dt::timestamp - f.tm_fc)) / 3600)::SMALLINT AS age_h
  FROM (
      SELECT DISTINCT base_dt, prod_area_stn_nm AS stn_nm, target_dt
        FROM crop_price_train
       WHERE lead_biz_d BETWEEN 3 AND 5              -- ★ 닿는 구간만
         AND prod_area_stn_nm IS NOT NULL
         AND base_dt >= '2016-11-01'                 -- 예보 구역 개설 이후
  ) k
  JOIN kma_mid_temp_raw f
    ON f.stn_nm      = k.stn_nm
   AND f.tm_ef::date = k.target_dt
   AND f.tm_fc       < k.base_dt::timestamp
 WHERE f.min_ta IS NOT NULL AND f.max_ta IS NOT NULL
 ORDER BY k.base_dt, k.stn_nm, k.target_dt, f.tm_fc DESC;   -- 가장 최근 발표

CREATE INDEX ix_tmp_fcst_pick ON tmp_fcst_pick(base_dt, stn_nm, target_dt);

UPDATE crop_price_train t
   SET prod_area_fcst_temp_tgt = p.fcst_temp,
       prod_area_fcst_age_h    = p.age_h
  FROM tmp_fcst_pick p
 WHERE p.base_dt   = t.base_dt
   AND p.stn_nm    = t.prod_area_stn_nm
   AND p.target_dt = t.target_dt
   AND t.lead_biz_d BETWEEN 3 AND 5;

-- ── 검증 ─────────────────────────────────────────────────────────────────

-- [1] 리드타임별로 얼마나 찼나. LT3~5 만 차고 나머지는 0 이어야 한다.
SELECT lead_biz_d,
       COUNT(*) AS 행수,
       COUNT(prod_area_fcst_temp_tgt) AS 예보있음,
       ROUND(100.0 * COUNT(prod_area_fcst_temp_tgt) / COUNT(*), 1) AS 비율
  FROM crop_price_train
 WHERE base_dt >= '2017-01-01' AND item_nm IN ('배추','무','양파')
 GROUP BY 1 ORDER BY 1;

-- [2] ★ 누수 검사 — 예보가 기준일보다 먼저 나왔나.
--     age_h 가 0 이하면 기준일 이후 발표분을 쓴 것이다. 하나도 없어야 한다.
SELECT '누수(발표가 기준일 이후)' AS 검사,
       COUNT(*) FILTER (WHERE prod_area_fcst_age_h <= 0) AS 위반,
       MIN(prod_area_fcst_age_h) AS 최소_시간차,
       ROUND(AVG(prod_area_fcst_age_h)) AS 평균_시간차
  FROM crop_price_train
 WHERE prod_area_fcst_temp_tgt IS NOT NULL;

-- [3] 예보가 실제 기온과 비슷한가 (터무니없는 값이 붙지 않았나).
--     같은 관측소·같은 날의 실측 평균기온과 견준다.
SELECT '예보 vs 실측' AS 검사,
       COUNT(*) AS 대조행,
       ROUND(AVG(ABS(t.prod_area_fcst_temp_tgt - w.ta))::numeric, 2) AS 평균차_도,
       ROUND(CORR(t.prod_area_fcst_temp_tgt, w.ta)::numeric, 3)      AS 상관
  FROM crop_price_train t
  JOIN (SELECT "stnNm" AS stn, "tm"::date AS dt, AVG("avgTa") AS ta
          FROM weather_asos_raw WHERE "avgTa" IS NOT NULL GROUP BY 1,2) w
    ON w.stn = t.prod_area_stn_nm AND w.dt = t.target_dt
 WHERE t.prod_area_fcst_temp_tgt IS NOT NULL;

-- [4] 한 기준일 안에서 값이 실제로 움직이나 (이게 목적이다).
SELECT '기준일당 서로 다른 값' AS 검사,
       ROUND(AVG(n)::numeric, 2) AS 평균가짓수
  FROM (SELECT COUNT(DISTINCT prod_area_fcst_temp_tgt) AS n
          FROM crop_price_train
         WHERE lead_biz_d BETWEEN 3 AND 5 AND base_dt >= '2017-01-01'
           AND item_nm IN ('배추','무','양파')
         GROUP BY base_dt, item_nm) x;
