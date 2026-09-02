-- ============================================================
-- batch_run — 배치 실행 이력  (2026-08-25)
--
-- 왜 필요한가
--   지금 배치 결과는 로그 파일에만 있다. 사람이 파일을 열어야 알 수 있고,
--   대시보드도 못 본다. 자동 실행을 걸면 아무도 안 보게 된다.
--
--   **"자동화했는데 실은 3일째 안 돌고 있었다"** 가 가장 흔한 사고다.
--   실행 이력이 DB 에 있으면 대시보드·알림·조회가 전부 같은 곳을 본다.
--
--   부수 효과로 "어제는 됐는데 오늘 왜 안 되지" 를 이력으로 답할 수 있다.
--
-- 구성
--   batch_run         실행 한 번 = 한 행
--   batch_run_stage   단계 한 번 = 한 행 (실행당 최대 9행)
--   v_batch_latest    최근 실행 요약 (대시보드용)
--   v_data_freshness  원천별 신선도 (실시간 계산)
-- ============================================================

CREATE TABLE IF NOT EXISTS batch_run (
    run_id       bigserial PRIMARY KEY,
    started_at   timestamptz NOT NULL DEFAULT now(),
    finished_at  timestamptz,
    status       text NOT NULL DEFAULT 'running'
                 CHECK (status IN ('running', 'ok', 'fail', 'partial')),
    host         text,
    stages_plan  text,
    n_ok         smallint NOT NULL DEFAULT 0,
    n_fail       smallint NOT NULL DEFAULT 0,
    note         text
);
COMMENT ON TABLE batch_run IS
  '배치 실행 이력. run_batch.py 가 실행마다 한 행씩 남긴다';
COMMENT ON COLUMN batch_run.status IS
  'running=진행중 · ok=전부 성공 · partial=수집 일부 실패했으나 계속 · fail=중단';
COMMENT ON COLUMN batch_run.stages_plan IS
  '이번 실행에서 돌리기로 한 단계 목록. --stages·--skip 이 반영된 결과';

CREATE TABLE IF NOT EXISTS batch_run_stage (
    run_id      bigint NOT NULL REFERENCES batch_run(run_id) ON DELETE CASCADE,
    seq         smallint NOT NULL,
    stage       text NOT NULL,
    ok          boolean NOT NULL,
    duration_s  numeric(10,1),
    message     text,
    PRIMARY KEY (run_id, seq)
);
COMMENT ON TABLE batch_run_stage IS
  '배치 단계별 결과. message 는 각 단계 출력의 마지막 몇 줄';

CREATE INDEX IF NOT EXISTS ix_batch_run_started ON batch_run (started_at DESC);

-- ── 최근 실행 요약 ──────────────────────────────────────────
CREATE OR REPLACE VIEW v_batch_latest AS
SELECT r.run_id,
       r.started_at,
       r.finished_at,
       ROUND(EXTRACT(EPOCH FROM (r.finished_at - r.started_at)))::int AS 소요_초,
       r.status,
       r.n_ok,
       r.n_fail,
       (SELECT string_agg(s.stage, ', ' ORDER BY s.seq)
          FROM batch_run_stage s WHERE s.run_id = r.run_id AND NOT s.ok) AS 실패단계,
       r.host
FROM batch_run r
ORDER BY r.started_at DESC;

-- ── 파생 테이블 신선도 — 의존을 만들지 않는 방식 ─────────────
--   v5 가 DROP 하는 표를 뷰가 직접 참조하면 DROP 이 막힌다.
--   함수 안에서 동적 SQL 로 읽으면 의존 관계가 생기지 않는다.
--   표가 없을 때도 죽지 않고 NULL 을 돌려준다.
CREATE OR REPLACE FUNCTION f_table_freshness(tbl text, col text, label text)
RETURNS TABLE (원천 text, 최신 date, 지연일 int, 행수 bigint)
LANGUAGE plpgsql STABLE AS $$
BEGIN
    IF to_regclass(tbl) IS NULL THEN
        RETURN QUERY SELECT label, NULL::date, NULL::int, 0::bigint;
        RETURN;
    END IF;
    RETURN QUERY EXECUTE format(
        'SELECT %L::text, MAX(%I)::date, (CURRENT_DATE - MAX(%I)::date)::int, COUNT(*) FROM %I',
        label, col, col, tbl);
END $$;

-- ── 원천별 신선도 ───────────────────────────────────────────
--   실시간 계산이다. 스냅샷으로 저장하지 않는다 — 저장하면 배치가 안 돌 때
--   신선도도 같이 멈춰서, 정작 문제가 생겼을 때 낡은 값을 보게 된다.
--
--   지연은 **달력일**이다. 조사일 기준 판단은 run_batch.py 가 따로 한다
--   (주말·연휴 때문에 달력일로 임계를 걸면 오탐이 난다).
--
--   ▣ crop_price_train · predict_input 은 **직접 참조하지 않는다** (2026-08-25)
--     v5 가 맨 앞에서 두 표를 DROP/TRUNCATE 하는데, 뷰가 매달려 있으면
--     "cannot drop table because other objects depend on it" 으로 배치가 죽는다.
--     실제로 그렇게 rebuild 가 실패했다.
--     대신 to_regclass 로 존재를 확인하고 동적으로 읽는 함수를 쓴다.
CREATE OR REPLACE VIEW v_data_freshness AS
SELECT '경락가'  AS 원천, MAX(auction_date)::date AS 최신,
       (CURRENT_DATE - MAX(auction_date)::date) AS 지연일, COUNT(*) AS 행수
  FROM auction_prices_daily
UNION ALL
SELECT '도·소매', MAX(exmn_ymd)::date, (CURRENT_DATE - MAX(exmn_ymd)::date), COUNT(*)
  FROM veg_daily_price_raw WHERE item_cd IN ('211', '231', '245')
UNION ALL
SELECT '반입량', MAX(base_date), (CURRENT_DATE - MAX(base_date)), COUNT(*)
  FROM daily_volume
UNION ALL
SELECT '기상', MAX("tm")::date, (CURRENT_DATE - MAX("tm")::date), COUNT(*)
  FROM weather_asos_raw
UNION ALL
SELECT '경제', MAX(dt)::date, (CURRENT_DATE - MAX(dt)::date), COUNT(*)
  FROM econ_daily_raw
UNION ALL
SELECT * FROM f_table_freshness('crop_price_train', 'base_dt', '학습테이블')
UNION ALL
SELECT * FROM f_table_freshness('predict_input', 'base_dt', '추론입력');

-- ── 검증 ────────────────────────────────────────────────────
-- [1] 표가 생겼나
SELECT to_regclass('batch_run') AS batch_run,
       to_regclass('batch_run_stage') AS batch_run_stage,
       to_regclass('v_batch_latest') AS v_batch_latest,
       to_regclass('v_data_freshness') AS v_data_freshness;

-- [2] 지금 신선도
SELECT * FROM v_data_freshness ORDER BY 지연일 DESC;
