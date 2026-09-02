-- =====================================================================
-- 28_prediction_log.sql — 예측 결과 저장 테이블 + 더미 데이터
-- =====================================================================
-- 목적
--   ML 파트가 매일 만든 예측을 여기에 쌓는다. 다른 파트(발주·재고·화면)는
--   이 테이블만 보면 된다. 모델이 아직 운영에 올라가지 않았으므로
--   **같은 스키마의 더미 데이터**를 함께 넣어 연동을 먼저 시작할 수 있게 한다.
--
--   더미는 실제 crop_price_train 의 앵커 가격에서 만들어 자릿수와 계절성이
--   실제와 같다. 난수가 아니라 결정적 함수라 몇 번을 돌려도 같은 값이 나온다.
--
-- ▣ 반드시 읽을 것 — 세 가지
--
--   1. 단위가 타겟마다 다르다
--        auc  경락가   원/kg    서울가락 · 특등급
--        whsl 중도매가 원/kg    가락도매 · 상품
--        rtl  소매가   원/단위  서울 · 상품. **배추는 포기 단위라 kg 아님**
--      세 값을 그대로 더하거나 비교하면 안 된다. unit 컬럼을 보고 쓸 것.
--
--   2. 모든 (품목 × 타겟) 조합이 쓸 만하지 않다
--      ref_prediction_quality 테이블에 실측 성능을 넣어 뒀다.
--      use_recommended = false 인 조합은 모델이 "어제 가격 그대로" 보다
--      나쁘다. 그 경우 anchor_prc 를 쓰는 편이 낫다.
--
--   3. lead_biz_d 1~2 는 모델이 개입하지 않는다
--      gated = true 로 나가며 pred_prc = anchor_prc 다. 버그가 아니다.
--      가까운 미래는 어제 가격이 이미 정답에 가까워 모델이 손해였다.
--
-- ▣ 선행 조건 — 실행 순서
--      25_ref_calendar.sql        달력 (대상일 계산)
--      27_ref_prediction_band.sql 예측 구간 (pred_lo / pred_hi 근거)
--      이 파일
--      crop_price_train 도 있어야 한다 (더미의 앵커·정답에 사용).
--
-- ▣ 재실행 안전
--      DROP → CREATE → INSERT. 몇 번을 실행해도 같은 결과다.
--      운영 전환 시에는 이 파일의 STEP 3(더미)만 빼고 쓰면 된다.
-- =====================================================================

-- ############################################################
-- ## STEP 0. 선행 조건 확인
-- ############################################################
--   순서를 틀리면 "relation does not exist" 같은 알기 어려운 오류가 난다.
--   여기서 무엇이 없는지 이름을 대고 멈춘다.
DO $$
DECLARE n int;
BEGIN
    SELECT COUNT(*) INTO n FROM information_schema.tables
     WHERE table_name = 'ref_prediction_band';
    IF n = 0 THEN
        RAISE EXCEPTION 'ref_prediction_band 가 없습니다. SQL/27_ref_prediction_band.sql 을 먼저 실행하세요.';
    END IF;

    SELECT COUNT(*) INTO n FROM information_schema.tables
     WHERE table_name = 'ref_calendar';
    IF n = 0 THEN
        RAISE EXCEPTION 'ref_calendar 가 없습니다. SQL/25_ref_calendar.sql 을 먼저 실행하세요.';
    END IF;

    SELECT COUNT(*) INTO n FROM crop_price_train;
    IF n = 0 THEN
        RAISE EXCEPTION 'crop_price_train 이 비어 있습니다. DBEAVER_run_v5.sql 을 먼저 실행하세요.';
    END IF;

    -- 밴드가 세 타겟 모두 있어야 더미가 완전해진다
    SELECT COUNT(DISTINCT target_kind) INTO n FROM ref_prediction_band;
    IF n < 3 THEN
        RAISE EXCEPTION 'ref_prediction_band 에 타겟이 %개뿐입니다 (auc/whsl/rtl 3개 필요). export_band_sql.py 를 다시 돌리세요.', n;
    END IF;
END $$;


-- ############################################################
-- ## STEP 1. 예측 저장 테이블
-- ############################################################

DROP TABLE IF EXISTS prediction_log;

CREATE TABLE prediction_log (
    id                bigserial     PRIMARY KEY,

    -- 키 ------------------------------------------------------------
    base_dt           date          NOT NULL,   -- 예측을 수행한 기준일
    target_dt         date          NOT NULL,   -- 예측 대상일
    item_nm           varchar(20)   NOT NULL,   -- 배추 · 양파 · 무
    lead_biz_d        smallint      NOT NULL,   -- 기준일에서 몇 영업일 뒤 (1~18)
    target_kind       varchar(4)    NOT NULL,   -- auc | whsl | rtl

    -- 값 ------------------------------------------------------------
    unit              varchar(10)   NOT NULL,   -- 원/kg · 원/단위
    anchor_prc        numeric(15,3) NOT NULL,   -- 기준일 시점 최신 실제가 (= baseline)
    pred_prc          numeric(15,3) NOT NULL,   -- 예측가
    pred_lo           numeric(15,3),            -- 참고 범위 하단
    pred_hi           numeric(15,3),            -- 참고 범위 상단
    seed_spread       numeric(15,3),            -- 시드 앙상블 표준편차
    gated             boolean       NOT NULL DEFAULT false,

    -- 이력 ----------------------------------------------------------
    model_ver         varchar(40)   NOT NULL,
    model_created_at  timestamp,
    created_at        timestamp     NOT NULL DEFAULT now(),

    -- 사후 채점 (실제값이 나온 뒤 UPDATE) ---------------------------
    actual_prc        numeric(15,3),
    abs_pct_err       numeric(10,4),
    scored_at         timestamp,

    CONSTRAINT prediction_log_uk
        UNIQUE (base_dt, item_nm, lead_biz_d, target_kind, model_ver),
    CONSTRAINT prediction_log_kind_ck
        CHECK (target_kind IN ('auc', 'whsl', 'rtl')),
    CONSTRAINT prediction_log_lead_ck
        CHECK (lead_biz_d BETWEEN 1 AND 18),
    CONSTRAINT prediction_log_prc_ck
        CHECK (pred_prc > 0 AND anchor_prc > 0)
);

COMMENT ON TABLE prediction_log IS
  'ML 예측 결과. 다른 파트는 이 테이블(또는 v_prediction_latest)만 참조한다';
COMMENT ON COLUMN prediction_log.anchor_prc IS
  '기준일 시점에 알 수 있는 최신 실제가. baseline("어제 가격 그대로")이자 예측의 기준값';
COMMENT ON COLUMN prediction_log.pred_lo IS
  '예측 구간 하단 = pred_prc * ref_prediction_band.ratio_q10. 검증 구간 실측 기준 10건 중 8건이 lo~hi 안';
COMMENT ON COLUMN prediction_log.pred_hi IS
  '예측 구간 상단 = pred_prc * ref_prediction_band.ratio_q90';
COMMENT ON COLUMN prediction_log.seed_spread IS
  '시드 앙상블 표준편차. 모델 내부 흔들림이며 예측 구간이 아니다 (실측 1.6~1.8%, 실제 오차는 10~17%). 구간은 pred_lo/hi 를 쓸 것';
COMMENT ON COLUMN prediction_log.gated IS
  'true 면 모델을 쓰지 않고 anchor_prc 를 그대로 내보낸 것. lead_biz_d 1~2 가 해당';
COMMENT ON COLUMN prediction_log.unit IS
  'auc/whsl 은 원/kg, rtl 은 원/단위(배추는 포기). 타겟 간 직접 비교 금지';

CREATE INDEX prediction_log_target_idx ON prediction_log (target_dt, item_nm, target_kind);
CREATE INDEX prediction_log_base_idx   ON prediction_log (base_dt DESC);
CREATE INDEX prediction_log_open_idx   ON prediction_log (item_nm, target_kind)
    WHERE actual_prc IS NULL;


-- ############################################################
-- ## STEP 2. 품목 × 타겟 실측 성능 (소비자용 안내)
-- ############################################################
--   "이 예측을 믿어도 되는가" 에 답하는 표다.
--   검증 2023 · 테스트 2024~25 두 구간의 baseline 대비 개선율이며,
--   둘 다 양수인 조합만 use_recommended = true 로 뒀다.
--   출처: 진행기록/테스트봉인_ablation2차_20260824.md

DROP TABLE IF EXISTS ref_prediction_quality;

CREATE TABLE ref_prediction_quality (
    target_kind      varchar(4)  NOT NULL,
    item_nm          varchar(20) NOT NULL,
    improve_valid_pct numeric(6,1),   -- 검증 2023  baseline 대비 개선율(%)
    improve_test_pct  numeric(6,1),   -- 테스트 2024~25
    dir_acc_pct       numeric(6,1),   -- 방향정확도 (테스트, 없으면 검증)
    use_recommended   boolean     NOT NULL,
    note              text,
    PRIMARY KEY (target_kind, item_nm)
);

INSERT INTO ref_prediction_quality VALUES
 ('auc','배추',   3.6,  22.4, 66.9, true,  '두 구간 모두 양수. 매입 판단에 활용 가능'),
 ('auc','무',    11.8,   4.7, 60.9, true,  '두 구간 모두 양수이나 폭이 작다. 보조 참고'),
 ('auc','양파',  -0.1,  -6.2, 58.1, false, '두 구간 모두 음수. 매입은 anchor_prc 사용 권장'),
 ('whsl','배추', 16.2,   8.5, NULL, true,  '두 구간 모두 양수'),
 ('whsl','무',   17.3, -13.2, 54.7, false, '테스트에서 크게 음수. 조용한 해에 모델이 손해'),
 ('whsl','양파',  2.2,  -4.7, NULL, false, '방향정확도가 무작위 이하인 구간이 있다'),
 ('rtl','배추',  20.4,  14.9, NULL, true,  '가장 안정적'),
 ('rtl','양파',   4.3,  13.9, 66.2, true,  '매입은 어렵지만 매도는 잘 맞는다'),
 ('rtl','무',    10.7,   8.2, NULL, true,  '두 구간 모두 양수');

COMMENT ON TABLE ref_prediction_quality IS
  '품목×타겟 실측 성능. use_recommended=false 면 baseline(anchor_prc)이 더 낫다';


-- ############################################################
-- ## STEP 3. 더미 데이터
-- ############################################################
--   운영 모델이 붙기 전까지 다른 파트가 연동을 시작할 수 있게 한다.
--
--   · 앵커·대상일은 crop_price_train 의 실제 값을 그대로 쓴다
--   · 예측가는 앵커에 결정적(deterministic) 변동을 얹어 만든다.
--     난수가 아니므로 재실행해도 같은 값이다.
--   · 과거 6 기준일은 actual_prc 까지 채워 채점 흐름을 확인할 수 있고,
--     가장 최근 1 기준일은 actual_prc = NULL 로 "오늘 예측" 상태다.
--
--   ※ 이 값으로 사업 판단을 하지 말 것. 자릿수와 형태만 실제와 같다.

WITH horizon AS (        -- 리드타임 18개가 모두 있는 최근 7개 기준일
    --   데이터 끝자락 기준일은 먼 리드타임의 대상일이 아직 없어 행이 모자란다.
    --   (2025-12-30 기준일에는 LT1 하나뿐이다)
    --   그런 날을 쓰면 더미에 LT8~18 이 없어 소비자가 먼 리드타임을 못 본다.
    SELECT base_dt
    FROM crop_price_train
    WHERE item_nm = '배추'
    GROUP BY base_dt
    HAVING COUNT(*) = 18
    ORDER BY base_dt DESC
    LIMIT 7
),
latest AS (SELECT MAX(base_dt) AS dt FROM horizon),
src AS (
    SELECT t.base_dt, t.target_dt, t.item_nm, t.lead_biz_d,
           k.kind, k.unit,
           CASE k.kind WHEN 'auc'  THEN t.auc_prc_lag1
                       WHEN 'whsl' THEN t.whsl_prc_lag1
                       ELSE t.rtl_prc_lag1 END AS anchor,
           CASE k.kind WHEN 'auc'  THEN t.target_auc_prc
                       WHEN 'whsl' THEN t.target_whsl_prc
                       ELSE t.target_rtl_prc END AS actual
    FROM crop_price_train t
    JOIN horizon h ON h.base_dt = t.base_dt
    CROSS JOIN (VALUES ('auc','원/kg'), ('whsl','원/kg'), ('rtl','원/단위'))
               AS k(kind, unit)
    WHERE t.item_nm IN ('배추','양파','무')
),
calc AS (
    SELECT s.*,
           -- 결정적 변동. 리드타임이 길수록 앵커에서 멀어지고,
           -- 품목·타겟마다 위상이 달라 실제처럼 서로 다른 곡선이 된다.
           -- ※ sin() 은 double precision 을 반환한다. PostgreSQL 에는
           --   round(double precision, int) 가 없으므로 여기서 numeric 으로
           --   잘라낸다. 안 하면 아래 ROUND(..., 3) 이 전부 42883 으로 죽는다.
           (0.006 * s.lead_biz_d
            * sin(s.lead_biz_d / 2.7
                  + CASE s.item_nm WHEN '배추' THEN 0.0
                                   WHEN '양파' THEN 0.8
                                   ELSE 1.7 END
                  + CASE s.kind WHEN 'auc' THEN 0.0 WHEN 'whsl' THEN 1.1 ELSE 2.3 END)
           )::numeric AS drift,
           -- 시드 편차는 실측상 리드타임과 거의 무관하게 앵커의 1.6~1.8% 다
           0.017 AS rel_spread
    FROM src s
)
INSERT INTO prediction_log
    (base_dt, target_dt, item_nm, lead_biz_d, target_kind, unit,
     anchor_prc, pred_prc, pred_lo, pred_hi, seed_spread, gated,
     model_ver, model_created_at, created_at, actual_prc, abs_pct_err, scored_at)
SELECT
    c.base_dt, c.target_dt, c.item_nm, c.lead_biz_d, c.kind, c.unit,
    ROUND(c.anchor, 3),
    -- LT 1~2 는 게이트: 모델을 쓰지 않고 앵커 그대로
    ROUND(CASE WHEN c.lead_biz_d < 3 THEN c.anchor
               ELSE c.anchor * (1 + c.drift) END, 3),
    -- 예측 구간은 실측 밴드에서. 게이트 행도 밴드가 적용된다
    --   (밴드를 게이트 반영 예측 기준으로 쟀으므로)
    ROUND((CASE WHEN c.lead_biz_d < 3 THEN c.anchor
                ELSE c.anchor * (1 + c.drift) END) * bd.ratio_q10, 3),
    ROUND((CASE WHEN c.lead_biz_d < 3 THEN c.anchor
                ELSE c.anchor * (1 + c.drift) END) * bd.ratio_q90, 3),
    ROUND(CASE WHEN c.lead_biz_d < 3 THEN 0
               ELSE c.anchor * c.rel_spread END, 3),
    (c.lead_biz_d < 3),
    'dummy-v0',
    timestamp '2026-08-24 12:00:00',
    c.base_dt + time '06:30',
    -- 가장 최근 기준일은 아직 정답이 없는 상태로 둔다
    CASE WHEN c.base_dt = (SELECT dt FROM latest) THEN NULL
         ELSE ROUND(c.actual, 3) END,
    CASE WHEN c.base_dt = (SELECT dt FROM latest) OR c.actual IS NULL THEN NULL
         ELSE ROUND(ABS(CASE WHEN c.lead_biz_d < 3 THEN c.anchor
                             ELSE c.anchor * (1 + c.drift) END - c.actual)
                    / NULLIF(c.actual, 0) * 100, 4) END,
    CASE WHEN c.base_dt = (SELECT dt FROM latest) THEN NULL
         ELSE c.target_dt + time '07:00' END
FROM calc c
JOIN ref_prediction_band bd
  ON bd.target_kind = c.kind AND bd.item_nm = c.item_nm AND bd.lead_biz_d = c.lead_biz_d
WHERE c.anchor IS NOT NULL AND c.anchor > 0;


-- ── STEP 3-b. "오늘 예측" 더미 ────────────────────────────────────────
--   위 3-a 는 학습 데이터 구간(2025년) 이라 대상일이 전부 과거다.
--   화면·발주 기능은 앞으로의 날짜를 다루므로, 오늘 기준으로 18영업일 앞을
--   내다보는 세트를 하나 더 넣는다. 운영 배치가 매일 만들 모양과 같다.
--
--   대상일은 ref_calendar 의 조사일 축에서 센다. 앵커는 확보된 마지막
--   실제가를 그대로 쓴다(그 이후 실측이 없으므로).
WITH today_base AS (       -- 오늘 이전의 가장 최근 조사일
    SELECT dt, survey_seq FROM ref_calendar
    WHERE is_survey AND dt <= CURRENT_DATE
    ORDER BY dt DESC LIMIT 1
),
last_px AS (               -- 품목별 마지막으로 확보된 가격
    SELECT DISTINCT ON (item_nm)
           item_nm, base_dt, auc_prc_lag1, whsl_prc_lag1, rtl_prc_lag1
    FROM crop_price_train
    WHERE item_nm IN ('배추','양파','무')
    ORDER BY item_nm, base_dt DESC
),
fut AS (
    SELECT b.dt AS base_dt, t.dt AS target_dt, p.item_nm, l.lead AS lead_biz_d,
           k.kind, k.unit,
           CASE k.kind WHEN 'auc'  THEN p.auc_prc_lag1
                       WHEN 'whsl' THEN p.whsl_prc_lag1
                       ELSE p.rtl_prc_lag1 END AS anchor
    FROM today_base b
    CROSS JOIN generate_series(1, 18) AS l(lead)
    JOIN ref_calendar t ON t.is_survey AND t.survey_seq = b.survey_seq + l.lead
    CROSS JOIN last_px p
    CROSS JOIN (VALUES ('auc','원/kg'), ('whsl','원/kg'), ('rtl','원/단위'))
               AS k(kind, unit)
),
fcalc AS (
    SELECT f.*,
           (0.006 * f.lead_biz_d
            * sin(f.lead_biz_d / 2.7
                  + CASE f.item_nm WHEN '배추' THEN 0.0
                                   WHEN '양파' THEN 0.8
                                   ELSE 1.7 END
                  + CASE f.kind WHEN 'auc' THEN 0.0 WHEN 'whsl' THEN 1.1 ELSE 2.3 END)
           )::numeric AS drift,
           0.017 AS rel_spread
    FROM fut f
)
INSERT INTO prediction_log
    (base_dt, target_dt, item_nm, lead_biz_d, target_kind, unit,
     anchor_prc, pred_prc, pred_lo, pred_hi, seed_spread, gated,
     model_ver, model_created_at, created_at)
SELECT
    c.base_dt, c.target_dt, c.item_nm, c.lead_biz_d, c.kind, c.unit,
    ROUND(c.anchor, 3),
    ROUND(CASE WHEN c.lead_biz_d < 3 THEN c.anchor
               ELSE c.anchor * (1 + c.drift) END, 3),
    -- 예측 구간은 실측 밴드에서. 게이트 행도 밴드가 적용된다
    --   (밴드를 게이트 반영 예측 기준으로 쟀으므로)
    ROUND((CASE WHEN c.lead_biz_d < 3 THEN c.anchor
                ELSE c.anchor * (1 + c.drift) END) * bd.ratio_q10, 3),
    ROUND((CASE WHEN c.lead_biz_d < 3 THEN c.anchor
                ELSE c.anchor * (1 + c.drift) END) * bd.ratio_q90, 3),
    ROUND(CASE WHEN c.lead_biz_d < 3 THEN 0
               ELSE c.anchor * c.rel_spread END, 3),
    (c.lead_biz_d < 3),
    'dummy-v0', timestamp '2026-08-24 12:00:00', now()
FROM fcalc c
JOIN ref_prediction_band bd
  ON bd.target_kind = c.kind AND bd.item_nm = c.item_nm AND bd.lead_biz_d = c.lead_biz_d
WHERE c.anchor IS NOT NULL AND c.anchor > 0;


-- ############################################################
-- ## STEP 4. 소비자용 뷰
-- ############################################################
--   "지금 시점에서 가장 최신 예측" 만 뽑는다.
--   같은 target_dt 에 대해 여러 기준일의 예측이 쌓이므로, 가장 최근
--   base_dt 의 것 하나만 남긴다. 다른 파트는 이 뷰를 쓰면 된다.

DROP VIEW IF EXISTS v_prediction_latest;

CREATE VIEW v_prediction_latest AS
SELECT DISTINCT ON (p.target_dt, p.item_nm, p.target_kind)
       p.target_dt, p.item_nm, p.target_kind, p.unit,
       p.base_dt, p.lead_biz_d,
       p.anchor_prc, p.pred_prc, p.pred_lo, p.pred_hi, p.gated,
       q.use_recommended,
       -- 권장하지 않는 조합은 앵커를 쓰라고 알려준다
       CASE WHEN q.use_recommended THEN p.pred_prc ELSE p.anchor_prc END AS prc_to_use,
       q.improve_test_pct, q.note,
       p.model_ver, p.actual_prc
FROM prediction_log p
LEFT JOIN ref_prediction_quality q
       ON q.target_kind = p.target_kind AND q.item_nm = p.item_nm
ORDER BY p.target_dt, p.item_nm, p.target_kind, p.base_dt DESC;

COMMENT ON VIEW v_prediction_latest IS
  '대상일·품목·타겟별 최신 예측 1건. prc_to_use 는 권장 조합이면 예측가, 아니면 앵커가';


-- ############################################################
-- ## 확인
-- ############################################################

-- 1) 적재 요약
SELECT target_kind, unit, COUNT(*) AS 행수,
       COUNT(DISTINCT base_dt) AS 기준일, COUNT(DISTINCT item_nm) AS 품목,
       MIN(base_dt) AS 처음, MAX(base_dt) AS 마지막,
       COUNT(*) FILTER (WHERE actual_prc IS NULL) AS 미채점,
       COUNT(*) FILTER (WHERE gated)              AS 게이트
FROM prediction_log GROUP BY 1,2 ORDER BY 1;

-- 2) 값이 상식 범위인가
--    확인: 경락 < 중도매 (원/kg). 소매는 단위가 달라 비교 대상이 아니다.
SELECT target_kind, item_nm, unit,
       ROUND(AVG(anchor_prc)) AS 평균앵커,
       ROUND(AVG(pred_prc))   AS 평균예측,
       ROUND(AVG(pred_prc / anchor_prc), 4) AS 예측_앵커_배수,
       ROUND(AVG(abs_pct_err), 2) AS 평균오차율
FROM prediction_log GROUP BY 1,2,3 ORDER BY 1,2;

-- 3) 소비자용 뷰 미리보기 — 가장 최근 기준일의 예측
SELECT * FROM v_prediction_latest
WHERE base_dt = (SELECT MAX(base_dt) FROM prediction_log)
ORDER BY item_nm, target_kind, target_dt
LIMIT 30;

-- 4) 실제값 UPDATE 예시 (운영 배치가 매일 돌릴 쿼리)
--    아래는 주석. 실제 실행은 배치가 한다.
-- UPDATE prediction_log p
--    SET actual_prc  = t.target_whsl_prc,
--        abs_pct_err = ROUND(ABS(p.pred_prc - t.target_whsl_prc)
--                            / NULLIF(t.target_whsl_prc,0) * 100, 4),
--        scored_at   = now()
--   FROM crop_price_train t
--  WHERE p.actual_prc IS NULL
--    AND p.target_kind = 'whsl'
--    AND t.base_dt    = p.base_dt
--    AND t.item_nm    = p.item_nm
--    AND t.lead_biz_d = p.lead_biz_d;
