-- ============================================================
-- econ_daily_raw — dt UNIQUE 추가  (2026-08-25)
--
--   왜 필요한가
--     이 테이블은 PK(id) 만 있어 같은 날짜를 몇 번이든 넣을 수 있었다.
--     수집기를 붙이려면 재실행이 안전해야 하는데, UNIQUE 가 없으면
--     ON CONFLICT 를 걸 수 없어 돌릴 때마다 행이 쌓인다.
--
--     dt 는 달력일이라 하루에 한 행이 맞다.
--     확인(2026-08-25): 4,018행 · 고유 dt 4,018 · 중복 0 · 형식 위반 0
--
--   다른 RAW 테이블도 같은 방식이다
--     veg_daily_price_raw   UNIQUE (exmn_ymd, item_cd, …)
--     auction_prices_daily  UNIQUE (auction_date, market_code, …)
--     daily_volume          PK (base_date, item_label)
--     weather_asos_raw      UNIQUE ("stnId", tm)
-- ============================================================
ALTER TABLE econ_daily_raw
    ADD CONSTRAINT uq_econ_daily_raw_dt UNIQUE (dt);

COMMENT ON CONSTRAINT uq_econ_daily_raw_dt ON econ_daily_raw IS
  '달력일당 1행. 수집기 재실행 시 ON CONFLICT 의 기준';

-- ── 검증 ────────────────────────────────────────────────────
SELECT COUNT(*) AS 행수, COUNT(DISTINCT dt) AS 고유일,
       MIN(dt) AS 시작, MAX(dt) AS 끝
FROM econ_daily_raw;
