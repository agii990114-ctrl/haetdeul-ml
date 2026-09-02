-- =====================================================================
-- 25_ref_calendar.sql  —  달력 (경매 축 · 조사 축)   v2.0
-- =====================================================================
-- 목적
--   미래 기준일에서 리드타임 1~18영업일을 세려면 앞으로의 휴일을 알아야 한다.
--
-- ▣ v2.0 변경 — 축이 두 개라는 것을 반영 (2026-08-24)
--   v1 은 축이 하나였고 경매 거래일로만 검증했다. 그런데 학습 테이블의
--   lead_biz_d 는 **중도매가 조사일** 축이다. 두 축은 같지 않다.
--
--       가락 경매 거래일   2015~2025   3,348일
--       중도매가 조사일                2,700일
--
--   648일 차이의 내역:
--       토요일 544      경매는 하지만 KAMIS 조사는 안 한다 (조사일 중 토요일 0건)
--       공휴일 약 124   경매는 열지만 조사는 안 한다
--       12월 첫째 금 11  시장 자체 휴장 (11년 연속)
--       역방향 16       신정 1/2 등 — 경매는 휴장인데 조사는 한다
--
--   명절도 하루씩 어긋난다. 경매는 명절 전날 거래하고 당일부터 사흘 쉬는데,
--   조사는 법정 연휴(D-1~D+1)를 그대로 따른다.
--       (실측: 조사 D-1 미조사 17/17 · D0 16/16 · D+1 14/14, 예외 0건)
--
--   v1 의 축을 그대로 lead_biz_d 에 연결하면 축이 24% 늘어나 모든 target_dt 가
--   이동하고, 토요일·공휴일 target_dt 에는 중도매가가 없어 타겟이 대량 NULL 이 된다.
--
-- ▣ 규칙 (2015~2025 실측 대조)
--   조사 축  휴무 = 토·일 + ref_holiday + 5/1 + 12월 첫째 금요일 + override
--            → 미탐 0 · 오탐 0. 2,700일 완전 일치
--   경매 축  휴장 = 일 + 신정 1/1~1/2 + 명절 당일~+2일 + 8월 첫 토요일 + override
--            → override 반영 후 오탐 0 · 미탐 0 (2016-01 ~ 2026-08 실거래일 대조)
--            ※ 2026-10 이후 3건은 공고 기준이라 아직 실거래로 검증되지 않았다
--
--   5/1 근로자의 날은 ref_holiday 에 없다. 법정공휴일이 아니라 근로자의 날
--   제정에 관한 법률에 따른 유급휴일이라 특일 정보 API 가 주지 않는다.
--   그런데 KAMIS 조사는 쉰다. 그래서 규칙으로 따로 넣는다.
--
-- ▣ 선행 조건
--   ref_holiday 테이블이 있어야 한다.
--     데이터 수집/휴일 달력/fetch_holidays.py  →  ref_holiday.sql  →  DBeaver 실행
--   명절 당일은 하드코딩하지 않고 ref_holiday 에서 유도한다.
--   (v1 은 하드코딩이었고 2028 설날이 하루 틀려 있었다 — 01-26 이 아니라 01-27)
--
-- ▣ 범위
--   2015-01-01 ~ 2028-12-31. 특일 정보 API 가 현재연도 +2년까지만 확정한다.
--   매년 fetch_holidays.py 를 다시 돌려 ref_holiday 를 갱신하고 이 파일을 재실행할 것.
--
-- ▣ 한계
--   임시공휴일·대체공휴일은 지정된 뒤에야 API 에 올라온다. 즉 예측 시점에
--   알 수 없는 휴일이 원리적으로 존재한다. 과거 재현에는 문제가 없고,
--   미래 추론에서만 리드타임이 어긋날 수 있다.
--
-- ▣ 실행 후 반드시 확인 (하단 결과 탭)
--   [2] 경매 축 대조   오탐 0
--   [3] 조사 축 대조   오탐 0 · 미탐 0
--   [4] lead_biz_d 재현  배추·양파·무 불일치 0   ← 가장 중요
--                        (마늘 684건은 정상. 아래 [4] 주석 참조)
--
--   ★ 실행 순서: ref_holiday.sql  →  이 파일  →  DBEAVER_run_v5.sql
--     v5.1 부터 v5 의 lead_biz_d 가 이 달력의 survey_seq 를 쓴다.
-- =====================================================================

-- ── 선행 조건 확인 ────────────────────────────────────────────────────
DO $$
DECLARE n int;
BEGIN
    SELECT COUNT(*) INTO n FROM information_schema.tables
     WHERE table_name = 'ref_holiday';
    IF n = 0 THEN
        RAISE EXCEPTION 'ref_holiday 테이블이 없습니다. 데이터 수집/휴일 달력/ref_holiday.sql 을 먼저 실행하세요.';
    END IF;
    SELECT COUNT(*) INTO n FROM ref_holiday WHERE is_holiday;
    IF n < 200 THEN
        RAISE EXCEPTION 'ref_holiday 공휴일이 %건뿐입니다. 수집이 덜 됐습니다.', n;
    END IF;
END $$;


DROP TABLE IF EXISTS ref_calendar;
DROP TABLE IF EXISTS ref_calendar_override;

-- ── 규칙으로 못 잡는 비정기 휴장·개장 ─────────────────────────────────
--   axis: 'open' = 경매 축 · 'survey' = 조사 축
--
--   과거는 게시판이 아니라 auction_prices_daily 실거래일이 정답이다.
--   "규칙상 개장인데 거래 0건" 을 뽑으면 그게 비정기 휴장이다 (아래 [4] 검증).
--   게시판은 양식이 제각각이고 본문이 이미지인 경우가 많아 신뢰할 수 없다.
--
--   게시판이 필요한 것은 아직 지나지 않은 날뿐이다. 리드타임이 18영업일이므로
--   3~4주 앞까지만 알면 되고, 비정기 휴장은 연 1.3회라 월 1회 확인이면 충분하다.
--   watch_garak_notice.py 가 공고에서 날짜 후보를 뽑아준다 (보조 수단).
CREATE TABLE ref_calendar_override (
    dt      date    NOT NULL,
    axis    text    NOT NULL CHECK (axis IN ('open', 'survey')),
    is_on   boolean NOT NULL,          -- 해당 축에서 여는가
    note    text,
    PRIMARY KEY (dt, axis)
);

INSERT INTO ref_calendar_override (dt, axis, is_on, note) VALUES
 -- 경매 축: 규칙으로 설명 안 되는 17건
 --   14건은 실거래일 대조로 발견한 것(연 1.3회), 3건은 공고에서 미리 넣은 미래분
 ('2017-01-31','open',false,'설 연휴 D+3 징검다리'),
 ('2021-09-20','open',false,'추석 D-1 월요일'),
 ('2022-01-31','open',false,'설 D-1 월요일'),
 ('2023-11-04','open',false,'토요일 시범 휴업'),
 ('2023-12-02','open',false,'토요일 시범 휴업'),
 ('2024-03-02','open',false,'토요일 휴업'),
 ('2025-02-12','open',false,'비정기 휴장'),
 ('2025-03-05','open',false,'비정기 휴장'),
 ('2025-11-01','open',false,'토요일 휴업'),
 ('2025-12-13','open',false,'토요일 휴업'),
 ('2026-03-07','open',false,'토요일 휴업'),
 ('2026-04-04','open',false,'토요일 휴업'),
 ('2026-06-03','open',false,'지방선거일 + 4차 시범휴업 1회'),
 ('2026-07-08','open',false,'4차 시범휴업 2회'),
 -- 아래 3건은 실측이 아니라 공고에서 왔다 (2026-08-24 추가).
 --   서울시농수산식품공사 「가락시장 개장일 탄력적 운영 4차 시범휴업 안내」 atcSn=21661
 --   공고 5회 중 6/3·7/8 은 이미 있었고 나머지가 빠져 있었다.
 --   토요일은 경매 축 규칙상 개장이라 override 가 없으면 미래 lead_biz_d 가 틀어진다.
 --   날짜가 지나면 실거래일 대조로 확정할 것.
 ('2026-10-10','open',false,'4차 시범휴업 3회 (공고 기준·미검증)'),
 ('2026-11-07','open',false,'4차 시범휴업 4회 (공고 기준·미검증)'),
 ('2026-12-12','open',false,'4차 시범휴업 5회 (공고 기준·미검증)'),
 -- 조사 축: 1건. API 에 소급 등록되지 않은 임시공휴일
 ('2015-08-14','survey',false,'광복 70주년 임시공휴일 (특일 정보 API 미수록)');


-- ── 달력 ──────────────────────────────────────────────────────────────
CREATE TABLE ref_calendar AS
WITH d AS (
    SELECT gs::date AS dt
    FROM generate_series('2015-01-01'::date, '2028-12-31'::date, '1 day') gs
),
-- 명절 당일. 법정 연휴 3일(D-1, D0, D+1) 중 가운데가 당일이다.
-- ref_holiday 의 date_name 이 정확히 '설날'/'추석'인 행만 쓴다.
-- ('대체공휴일(설날)' 은 이름이 달라 자동으로 빠진다)
lunar AS (
    SELECT date_name, dt,
           ROW_NUMBER() OVER (PARTITION BY EXTRACT(year FROM dt), date_name
                              ORDER BY dt) AS rn
    FROM ref_holiday
    WHERE date_name IN ('설날', '추석') AND is_holiday
),
d0 AS (SELECT date_name, dt FROM lunar WHERE rn = 2),
seol    AS (SELECT dt FROM d0 WHERE date_name = '설날'),
chuseok AS (SELECT dt FROM d0 WHERE date_name = '추석'),
hol AS (
    SELECT dt, MIN(date_name) AS nm FROM ref_holiday WHERE is_holiday GROUP BY dt
),
r AS (
    SELECT d.dt,
           EXTRACT(dow FROM d.dt)::int AS dow,
           -- 경매 축
           CASE
             WHEN EXTRACT(dow FROM d.dt) = 0                              THEN 'sunday'
             WHEN EXTRACT(month FROM d.dt) = 1
              AND EXTRACT(day   FROM d.dt) IN (1, 2)                      THEN 'new_year'
             WHEN EXTRACT(month FROM d.dt) = 8
              AND EXTRACT(dow   FROM d.dt) = 6
              AND EXTRACT(day   FROM d.dt) <= 7                           THEN 'summer_break'
             WHEN EXISTS (SELECT 1 FROM seol s
                           WHERE d.dt BETWEEN s.dt AND s.dt + 2)          THEN 'seol'
             WHEN EXISTS (SELECT 1 FROM chuseok c
                           WHERE d.dt BETWEEN c.dt AND c.dt + 2)          THEN 'chuseok'
           END AS open_reason,
           -- 조사 축
           CASE
             WHEN EXTRACT(dow FROM d.dt) IN (0, 6)                        THEN 'weekend'
             WHEN EXTRACT(month FROM d.dt) = 5
              AND EXTRACT(day   FROM d.dt) = 1                            THEN 'labor_day'
             WHEN EXTRACT(month FROM d.dt) = 12
              AND EXTRACT(dow   FROM d.dt) = 5
              AND EXTRACT(day   FROM d.dt) <= 7                           THEN 'dec_first_fri'
             WHEN h.dt IS NOT NULL                                        THEN 'holiday:' || h.nm
           END AS survey_reason
    FROM d
    LEFT JOIN hol h ON h.dt = d.dt
),
f AS (
    SELECT r.dt, r.dow,
           COALESCE(vo.is_on, r.open_reason   IS NULL) AS is_open,
           COALESCE(vs.is_on, r.survey_reason IS NULL) AS is_survey,
           COALESCE(CASE WHEN vo.dt IS NOT NULL THEN 'override:' || vo.note END,
                    r.open_reason)   AS open_reason,
           COALESCE(CASE WHEN vs.dt IS NOT NULL THEN 'override:' || vs.note END,
                    r.survey_reason) AS survey_reason
    FROM r
    LEFT JOIN ref_calendar_override vo ON vo.dt = r.dt AND vo.axis = 'open'
    LEFT JOIN ref_calendar_override vs ON vs.dt = r.dt AND vs.axis = 'survey'
)
SELECT dt, dow, is_open, is_survey, open_reason, survey_reason,
       -- 축별 일련번호. 두 날짜의 차이가 곧 그 축의 영업일 간격이다.
       --   open_seq   경매 거래일 축   (경락가 타겟)
       --   survey_seq 중도매가 조사일 축 (lead_biz_d · 중도매/소매 타겟)
       SUM(CASE WHEN is_open   THEN 1 ELSE 0 END) OVER (ORDER BY dt) AS open_seq,
       SUM(CASE WHEN is_survey THEN 1 ELSE 0 END) OVER (ORDER BY dt) AS survey_seq
FROM f
ORDER BY dt;

ALTER TABLE ref_calendar ADD PRIMARY KEY (dt);
CREATE INDEX ref_calendar_open_idx   ON ref_calendar (open_seq)   WHERE is_open;
CREATE INDEX ref_calendar_survey_idx ON ref_calendar (survey_seq) WHERE is_survey;

COMMENT ON TABLE ref_calendar IS
  '가락 경매 거래일(is_open) · KAMIS 중도매가 조사일(is_survey) 두 축. ref_holiday 에서 유도';
COMMENT ON COLUMN ref_calendar.survey_seq IS
  'lead_biz_d 의 축. crop_price_train 의 tmp_px.bn 과 같은 의미';


-- ############################################################
-- ## 검증 (결과 탭 5개)
-- ############################################################

-- ── 1) 축별 일수 요약 ───────────────────────────────────
--    확인: 2015~2025 에서 경매 3,348 · 조사 2,700 근처
SELECT EXTRACT(year FROM dt)::int AS yr,
       COUNT(*) FILTER (WHERE is_open)   AS 경매개장,
       COUNT(*) FILTER (WHERE is_survey) AS 조사일
FROM ref_calendar GROUP BY 1 ORDER BY 1;


-- ── 2) 경매 축 대조 ─────────────────────────────────────
--    확인: '규칙 휴장·거래 있음'(오탐) 0건.
--          '규칙 개장·거래 없음'(미탐)은 비정기 휴장이므로 override 후보.
SELECT c.dt, c.dow, c.open_reason,
       CASE WHEN a.auction_date IS NULL THEN '규칙 개장·거래 없음'
            ELSE '규칙 휴장·거래 있음' END AS mismatch
FROM ref_calendar c
LEFT JOIN (SELECT DISTINCT auction_date
             FROM auction_prices_daily
            WHERE wholesale_market_code = '110001') a ON a.auction_date = c.dt
WHERE c.dt BETWEEN '2016-01-01' AND (SELECT MAX(auction_date) FROM auction_prices_daily)
  AND c.is_open <> (a.auction_date IS NOT NULL)
ORDER BY c.dt;


-- ── 3) 조사 축 대조 ★ ───────────────────────────────────
--    확인: 0행. 1건이라도 나오면 규칙이 틀린 것이므로 v5 연결 금지.
--    (배추 기준. 가락도매·중도매·상품·kg 환산 가능 = tmp_px 와 같은 필터)
WITH surveyed AS (
    SELECT DISTINCT exmn_ymd AS dt
    FROM veg_daily_price_raw
    WHERE se_cd = '02' AND grd_cd = '04' AND mrkt_nm = '가락도매'
      AND item_nm = '배추' AND exmn_dd_prc IS NOT NULL AND unit_sz > 0
      AND (unit LIKE '%kg%' OR unit = 'g')
)
SELECT c.dt, c.dow, c.survey_reason,
       CASE WHEN s.dt IS NULL THEN '규칙 조사일·실제 없음'
            ELSE '규칙 휴무·실제 조사함' END AS mismatch
FROM ref_calendar c
LEFT JOIN surveyed s ON s.dt = c.dt
WHERE c.dt BETWEEN '2015-01-01' AND '2025-12-31'
  AND c.is_survey <> (s.dt IS NOT NULL)
ORDER BY c.dt;


-- ── 4) lead_biz_d 재현 ★★ ──────────────────────────────
--    학습 테이블의 target_dt 가 조사 축으로 재현되는가. v5 연결의 합격 조건이다.
--
--    확인: 배추·양파·무 불일치 0.
--          마늘은 684건이 정상이다. tmp_px.bn 이 PARTITION BY item_nm 이라
--          품목별 관측일 축인데, 마늘만 조사일이 2,533일로 167일 적다.
--          즉 달력이 틀린 게 아니라 마늘 중도매가 조사가 빠진 날이 있는 것이다.
--          달력 축으로 바꾸면 마늘도 다른 품목과 같은 축을 쓰게 되고,
--          빠진 날은 target NULL 로 드러난다 (지금은 축이 밀려 가려져 있다).
--          마늘은 학습에서 제외돼 있으므로 실험 기록에는 영향이 없다.
SELECT t.item_nm,
       COUNT(*)                                                   AS 대조행수,
       COUNT(*) FILTER (WHERE c2.dt IS NULL)                      AS 대상일없음,
       COUNT(*) FILTER (WHERE c2.dt IS DISTINCT FROM t.target_dt) AS 불일치
FROM crop_price_train t
JOIN ref_calendar b  ON b.dt = t.base_dt AND b.is_survey
LEFT JOIN ref_calendar c2 ON c2.is_survey
                         AND c2.survey_seq = b.survey_seq + t.lead_biz_d
GROUP BY 1 ORDER BY 1;


-- ── 5) 미래 구간 동작 확인 ──────────────────────────────
--    오늘 기준 1~18영업일 뒤가 축별로 언제인가.
--    운영 배치가 쓰게 될 값이다.
SELECT l.lead_biz_d,
       (SELECT dt FROM ref_calendar
         WHERE is_survey AND survey_seq =
               (SELECT survey_seq FROM ref_calendar WHERE dt = CURRENT_DATE) + l.lead_biz_d
         LIMIT 1) AS 조사축_대상일,
       (SELECT dt FROM ref_calendar
         WHERE is_open AND open_seq =
               (SELECT open_seq FROM ref_calendar WHERE dt = CURRENT_DATE) + l.lead_biz_d
         LIMIT 1) AS 경매축_대상일
FROM generate_series(1, 18) AS l(lead_biz_d)
ORDER BY 1;
