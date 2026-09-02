-- =====================================================================
-- 26_check_calendar.sql — ref_calendar 합격 판정 (한 화면)
-- =====================================================================
--   25_ref_calendar.sql 실행 후 이 파일을 Alt+X.
--   결과가 한 표로 나온다. 판정 열이 전부 'OK' 여야 v5 연결로 넘어간다.
-- =====================================================================

WITH surveyed AS (          -- 실제 중도매가 조사일 (tmp_px 와 같은 필터)
    SELECT DISTINCT exmn_ymd AS dt
    FROM veg_daily_price_raw
    WHERE se_cd = '02' AND grd_cd = '04' AND mrkt_nm = '가락도매'
      AND item_nm = '배추' AND exmn_dd_prc IS NOT NULL AND unit_sz > 0
      AND (unit LIKE '%kg%' OR unit = 'g')
),
chk3 AS (                   -- [3] 조사 축 대조
    SELECT COUNT(*) AS n
    FROM ref_calendar c
    LEFT JOIN surveyed s ON s.dt = c.dt
    WHERE c.dt BETWEEN '2015-01-01' AND '2025-12-31'
      AND c.is_survey <> (s.dt IS NOT NULL)
),
chk4 AS (                   -- [4] lead_biz_d 재현
    SELECT t.item_nm,
           COUNT(*) FILTER (WHERE c2.dt IS DISTINCT FROM t.target_dt) AS bad
    FROM crop_price_train t
    JOIN ref_calendar b  ON b.dt = t.base_dt AND b.is_survey
    LEFT JOIN ref_calendar c2 ON c2.is_survey
                             AND c2.survey_seq = b.survey_seq + t.lead_biz_d
    GROUP BY 1
)
SELECT '[3] 조사 축 대조' AS 검사, '전체' AS 대상, n AS 불일치,
       CASE WHEN n = 0 THEN 'OK' ELSE '*** 실패 ***' END AS 판정
  FROM chk3
UNION ALL
SELECT '[4] lead_biz_d 재현', item_nm, bad,
       CASE WHEN item_nm = '마늘' THEN
                 CASE WHEN bad = 684 THEN 'OK (마늘은 조사 결측 167일)'
                      ELSE '확인 필요' END
            WHEN bad = 0 THEN 'OK'
            ELSE '*** 실패 — v5 연결 금지 ***' END
  FROM chk4
ORDER BY 1, 2;
