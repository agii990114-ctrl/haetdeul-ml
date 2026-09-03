-- ============================================================================
-- 3-타겟 구조 — 경락가 · 중도매가 · 소매가  (DBeaver 실행용)
--
-- ▣ 목적
--    유통 3단계 가격을 각각 예측하는 모델 3개를 만들기 위해
--    타겟 컬럼 3개를 하나의 테이블에 둔다.
--
--        산지 → [경매] → 중도매인 → [판매] → 식당·소매상 → [소매] → 소비자
--                 ↑                    ↑                      ↑
--          target_auc_prc      target_whsl_prc        target_rtl_prc
--
-- ▣ 왜 테이블을 나누지 않는가
--    테이블을 나누면 같은 feature 를 세 벌 관리하게 되고, 나중에 매핑이나
--    계산식을 고칠 때 일부만 수정되는 로직 드리프트가 발생한다.
--
--    학습은 타겟 컬럼만 바꿔 지정하면 된다.
--        for target in [target_auc_prc, target_whsl_prc, target_rtl_prc]:
--            model = lgb.train(..., label=df[target])
--
-- ▣ ★★ 정정 — "feature 가 완전히 동일하다" 는 전제는 틀렸다 (2026-08-27)
--
--    이 파일은 원래 "feature 28개가 완전히 동일하므로 타겟 컬럼 2개만
--    추가하면 된다" 고 적혀 있었다. **타겟마다 달라야 하는 컬럼이 있다.**
--
--    ① 앵커       — 처음부터 타겟별로 분기시켰다 (아래 ▣ 항목)
--    ② baseline   — ★ 분기시키지 않았다. 이게 사고가 됐다
--
--    앵커 변환을 쓰면 **앵커가 곧 baseline** 이다. 그래서 baseline 후보군도
--    타겟마다 있어야 하는데, `train.py` 의 후보 2개가 타겟과 무관하게
--    **중도매가 컬럼으로 고정**돼 있었다.
--
--        경락가를 평가하면서 중도매가 7일평균을 후보로 놓음
--        배추 경락 721원 vs 중도매 1,169원 — 자릿수가 달라 항상 탈락
--        => "최강 baseline = 앵커" 가 구조상 자동으로 참이 됨
--
--    v5.3 에서 파생 컬럼을 대칭화했다 (경락 4종 · 소매 6종 추가).
--    중도매만 7종이고 경락 3종·소매 1종이던 비대칭을 없앴다.
--
--    ★ 단, 신규 10종은 **입력(feature)에서는 기본 제외**다.
--      두 폴드 모두 악화됐다 (0.1801->0.1816 · 0.1820->0.1826).
--      `train.py --with-new-price` 로만 실험한다.
--      **같은 컬럼이 잣대로는 최강인데 입력으로는 해롭다.**
--
--    상세 백로그 [M-16]
--
-- ▣ 앵커도 각각 달라야 한다 ★
--    앵커 변환(y = log(target/anchor))을 쓰므로 타겟마다 짝이 되는 앵커가
--    필요하다. 중도매가 타겟에 경락가 앵커를 쓰면 스케일이 어긋난다.
--
--        target_auc_prc   ↔  auc_prc_lag1
--        target_whsl_prc  ↔  whsl_prc_lag1
--        target_rtl_prc   ↔  rtl_prc_lag1
--
-- ▣ 스케일 주의
--    세 가격은 단위와 수준이 다르다. 하나의 모델로 합치지 말 것.
--        경락가   원/kg      농가 수취
--        중도매가 원/kg      구매자 지불 (경락가의 약 1.5~2배)
--        소매가   원/단위    배추는 '포기' 단위 — kg 환산 불가
--
-- ▣ 실행
--    DBEAVER_run_full.sql 실행 후 이 파일을 [Alt+X].
--    재실행 안전 (컬럼 추가는 IF NOT EXISTS, 값은 UPDATE).
-- ============================================================================

-- ── STEP 1. 타겟 컬럼 추가 ────────────────────────────────────────────
ALTER TABLE crop_price_train
    ADD COLUMN IF NOT EXISTS target_auc_prc NUMERIC(15,3),
    ADD COLUMN IF NOT EXISTS target_rtl_prc NUMERIC(15,3);

COMMENT ON COLUMN crop_price_train.target_auc_prc IS
  '대상일 경매 낙찰가(원/kg). 서울가락·특등급. 사용자=농가·산지유통인';
COMMENT ON COLUMN crop_price_train.target_whsl_prc IS
  '대상일 중도매인 판매가(원/kg). 가락도매·상품. 사용자=식당·급식 구매담당 (주력)';
COMMENT ON COLUMN crop_price_train.target_rtl_prc IS
  '대상일 소매가(원/단위). 배추는 포기 단위이므로 kg 인 다른 타겟과 스케일 다름';


-- ── STEP 2. 경락가 타겟 결합 ──────────────────────────────────────────
--   타겟이므로 target_dt 당일 값을 그대로 가져온다.
--   (입력이 아니라 정답 라벨이므로 미래 정보 사용이 정상)
DROP TABLE IF EXISTS tmp_auc_t;
CREATE TEMP TABLE tmp_auc_t AS
SELECT auction_date AS dt,
       item_name    AS item_nm,
       avg_auction_price_krw_per_kg::NUMERIC(15,3) AS prc
FROM auction_prices_daily
WHERE wholesale_market_code = '110001'   -- 서울가락
  AND grade_code            = '11'       -- 특등급
  AND avg_auction_price_krw_per_kg > 0;
CREATE INDEX ix_tmp_auc_t ON tmp_auc_t(item_nm, dt);

UPDATE crop_price_train t
SET target_auc_prc = (
    SELECT a.prc FROM tmp_auc_t a
    WHERE a.item_nm = t.item_nm AND a.dt = t.target_dt
    LIMIT 1);


-- ── STEP 3. 소매가 타겟 결합 ──────────────────────────────────────────
--   기존 rtl_prc_lag1 과 동일한 산출 로직을 써야 한다.
--   lag 과 target 이 다른 시계열에서 나오면 모델이 잘못 학습한다.
DROP TABLE IF EXISTS tmp_rtl_t;
CREATE TEMP TABLE tmp_rtl_t AS
SELECT exmn_ymd AS dt, item_nm,
       AVG(exmn_dd_prc / NULLIF(unit_sz, 0))::NUMERIC(15,3) AS prc
FROM veg_daily_price_raw
WHERE se_cd  = '01'          -- 소매
  AND grd_cd = '04'          -- 상품
  AND exmn_dd_prc IS NOT NULL
  AND unit_sz > 0
GROUP BY exmn_ymd, item_nm;
CREATE INDEX ix_tmp_rtl_t ON tmp_rtl_t(item_nm, dt);

UPDATE crop_price_train t
SET target_rtl_prc = (
    SELECT r.prc FROM tmp_rtl_t r
    WHERE r.item_nm = t.item_nm AND r.dt = t.target_dt
    LIMIT 1);


-- ── STEP 4. 검증 ──────────────────────────────────────────────────────

-- 4-1) 타겟 3종 채움률
--   확인: 경락가·중도매가는 높아야 정상. 소매가는 조사일에만 있어 낮을 수 있음
SELECT EXTRACT(YEAR FROM base_dt)::INT AS yr,
       COUNT(*) AS rows,
       ROUND(100.0*COUNT(target_auc_prc) /COUNT(*),1) AS "경락가_채움률",
       ROUND(100.0*COUNT(target_whsl_prc)/COUNT(*),1) AS "중도매가_채움률",
       ROUND(100.0*COUNT(target_rtl_prc) /COUNT(*),1) AS "소매가_채움률"
FROM crop_price_train GROUP BY 1 ORDER BY 1;

-- 4-2) 품목별 가격 수준 — 유통 단계가 올라갈수록 비싸야 정상
SELECT item_nm,
       ROUND(AVG(target_auc_prc))  AS "경락가",
       ROUND(AVG(target_whsl_prc)) AS "중도매가",
       ROUND(AVG(target_rtl_prc))  AS "소매가",
       ROUND(AVG(target_whsl_prc) / NULLIF(AVG(target_auc_prc),0), 2) AS "중도매/경락 배수"
FROM crop_price_train
GROUP BY 1 ORDER BY 1;

-- 4-3) 앵커 짝 확인 — 타겟과 앵커가 같은 계열인지
--   확인: 세 비율 모두 1 근처여야 정상 (타겟/앵커는 하루 차이라 비슷해야 함)
SELECT item_nm,
       ROUND(AVG(target_auc_prc  / NULLIF(auc_prc_lag1,0)),  3) AS "경락가/앵커",
       ROUND(AVG(target_whsl_prc / NULLIF(whsl_prc_lag1,0)), 3) AS "중도매가/앵커",
       ROUND(AVG(target_rtl_prc  / NULLIF(rtl_prc_lag1,0)),  3) AS "소매가/앵커"
FROM crop_price_train
GROUP BY 1 ORDER BY 1;

-- 4-4) 학습 가능 행수 — 타겟과 앵커가 모두 있어야 학습에 쓸 수 있다
SELECT '경락가 모델'  AS 모델, COUNT(*) AS 학습가능행수
  FROM crop_price_train WHERE target_auc_prc IS NOT NULL AND auc_prc_lag1 IS NOT NULL
UNION ALL
SELECT '중도매가 모델', COUNT(*)
  FROM crop_price_train WHERE target_whsl_prc IS NOT NULL AND whsl_prc_lag1 IS NOT NULL
UNION ALL
SELECT '소매가 모델', COUNT(*)
  FROM crop_price_train WHERE target_rtl_prc IS NOT NULL AND rtl_prc_lag1 IS NOT NULL;
