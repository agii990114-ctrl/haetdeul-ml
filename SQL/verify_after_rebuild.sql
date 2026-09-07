-- ============================================================================
-- 재생성 직후 자동 검사  (2026-09-04)
--
-- ▣ 왜 따로 만드나
--    `DBEAVER_run_v5.sql` 안에도 검증 쿼리가 있다. 그런데 배치는 v5 를
--    한 덩어리로 실행하고 **결과 집합을 전부 버린다**(`while cur.nextset(): pass`).
--    사람이 DBeaver 로 돌릴 때만 보이고, **무인 실행에서는 아무도 안 본다.**
--
--    실제로 2026-08-27 ~ 09-04 **일주일 동안** 검증 [14] 가 100% 불일치를
--    내고 있었는데 아무도 몰랐다. 검사가 있는 것과 검사가 읽히는 것은 다르다.
--
--    이 파일은 **배치가 읽고 판단하는 검사**다. 한 행이 검사 하나이고
--    `bad > 0` 이면 배치가 선다(severity='BAD') 또는 알린다('WARN').
--
-- ▣ 규칙
--    · 결과는 (check_name, severity, bad, total, detail) 다섯 칸 고정
--    · **BAD 는 "이대로 예측을 내보내면 안 되는 것" 만** 쓴다.
--      알림용은 WARN 이다. 매일 우는 경보는 아무도 안 본다
--    · 새 검사를 더할 때 UNION ALL 로 붙이면 된다
-- ============================================================================

WITH
-- ── ① 추론 입력이 학습표와 같은 계산식인가 ────────────────────────────
--    STEP 8 은 STEP 3·4·5 를 복제한 것이다. 갈라지면 나오는 건 예외가
--    아니라 **그럴듯하게 틀린 값**이다.
--    ※ 아래 7칸은 STEP 8 이 아예 안 만든다 (v5.3 파생 10종 중 일부).
--      모델 입력에서 뺀 것들이라 예측에는 영향이 없다. 자세한 것은
--      v5 의 [14] 주석. 채택하게 되면 이 목록에서 빼고 STEP 8 을 고칠 것.
skipped(cols) AS (
    SELECT ARRAY['auc_prc_prev_yr','rtl_prc_lag3','rtl_prc_lag7','rtl_prc_avg7',
                 'rtl_prc_avg14','rtl_prc_std7','rtl_prc_prev_yr']
),
pi_cmp AS (
    SELECT ((to_jsonb(p) - 'target_whsl_prc' - 'target_auc_prc' - 'target_rtl_prc')
            - (SELECT cols FROM skipped)) AS pj,
           ((to_jsonb(t) - 'id' - 'created_at'
                         - 'target_whsl_prc' - 'target_auc_prc' - 'target_rtl_prc')
            - (SELECT cols FROM skipped)) AS tj
    FROM predict_input p
    JOIN crop_price_train t USING (base_dt, item_nm, lead_biz_d)
),
-- ── ② 소매 타겟이 서울 기준인가 ──────────────────────────────────────
--    전국 평균으로 새면 학습 구간과 검증 구간의 조사 점포 수가 달라져
--    (2023년 44 -> 59개) 성능이 조용히 왜곡된다. CLAUDE.md 9절.
seoul AS (
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
-- ── ③ 품목이 조용히 끊기지 않았나 ────────────────────────────────────
--    2026-09-03 에 마늘이 학습표에서 2025-12-30 에 끊겨 있던 것을 찾았다.
--    원천이 이름을 바꾸면(마늘 -> 피마늘) **값이 틀리는 게 아니라 행이
--    사라진다.** 눈에 안 띄는 쪽이다.
item_tail AS (
    SELECT item_nm, MAX(base_dt) AS mx FROM crop_price_train GROUP BY 1
),
-- ── ④ 앵커가 낡지 않았나 ────────────────────────────────────────────
pi_fresh AS (SELECT MAX(base_dt) AS mx FROM predict_input)

SELECT '추론입력 계산식 대조'::TEXT AS check_name, 'BAD'::TEXT AS severity,
       COUNT(*) FILTER (WHERE pj IS DISTINCT FROM tj)::BIGINT AS bad,
       COUNT(*)::BIGINT AS total,
       '학습표와 겹치는 (기준일·품목·리드타임) 전 컬럼 대조'::TEXT AS detail
FROM pi_cmp
UNION ALL
SELECT '추론입력 대조행 있음', 'BAD',
       CASE WHEN COUNT(*) = 0 THEN 1 ELSE 0 END, COUNT(*),
       '0 이면 대조가 성립하지 않은 것이다 (겹치는 구간 없음)'
FROM pi_cmp
UNION ALL
SELECT '소매 타겟 서울 기준', 'BAD',
       COUNT(*) FILTER (WHERE t.target_rtl_prc IS DISTINCT FROM s.prc), COUNT(*),
       '불일치가 있으면 소매 앵커·타겟이 전국 평균으로 샌 것이다'
FROM crop_price_train t
JOIN seoul s ON s.dt = t.target_dt AND s.item_nm = t.item_nm
WHERE t.target_rtl_prc IS NOT NULL
UNION ALL
SELECT '품목 끊김 (7일 넘게 뒤처짐)', 'WARN',
       COUNT(*) FILTER (WHERE (SELECT MAX(mx) FROM item_tail) - mx > 7), COUNT(*),
       string_agg(item_nm || ' ' || mx::TEXT, ' · ' ORDER BY mx)
FROM item_tail
UNION ALL
SELECT '추론입력 신선도 (3일 초과면 앵커가 낡음)', 'WARN',
       CASE WHEN CURRENT_DATE - mx > 3 THEN 1 ELSE 0 END, (CURRENT_DATE - mx),
       '최신 기준일 ' || mx::TEXT
FROM pi_fresh
UNION ALL
SELECT '앵커 결측', 'BAD',
       COUNT(*) FILTER (WHERE whsl_prc_lag1 IS NULL), COUNT(*),
       '추론 입력에 중도매 앵커가 없는 행'
FROM predict_input
UNION ALL
-- ────────────────────────────────────────────────────────────────────
--  ★ 경매일인데 경락가 정답이 없는 날 (2026-09-07 추가 · 매입 #250)
--
--  왜 필요한가
--    2026-09-03 하루가 통째로 비어 있었는데 **일주일 넘게 몰랐다.**
--    수집기가 `package_name` 에 문자열 'None' 을 넣었고, v5 규격 필터가
--    한 행도 못 걸러 타겟이 전부 NULL 이 됐다.
--
--    ★ **값이 틀린 게 아니라 행이 사라진 사고**라 아무 경보도 안 울렸다.
--      매입 파트가 물어봐서 알았고, 그때도 우리는 다른 표를 보고
--      "이상 없다" 고 답했다.
--
--  왜 BAD 인가
--    정답이 없으면 그날은 채점이 안 되고, 드리프트 판정 표본에서도
--    조용히 빠진다. 모델은 계속 예측을 내보낸다.
--
--  ⚠️ 오탐이 하나 있다 — 거래가 진짜로 없는 날
--    2026-02-24 는 가락 배추 특등급이 11행뿐이고 전부 소포장이라
--    (그물망·파렛트 10kg 0건 · 물량 690kg) 정답이 없는 게 맞다.
--    그래서 **물량이 있는데 정답이 없는 날만** 센다.
--  ⚠️ 오탐이 또 하나 있다 — **토요일**
--    가락은 토요일에 경매하지만 도소매 조사는 안 한다. 우리 타겟 행은
--    조사 축(`is_survey`)으로 만들어져서 **토요일엔 행 자체가 없다.**
--    `is_open` 만 걸면 토요일이 전부 '구멍' 으로 잡힌다 (실측 64일).
--    그건 이 검사가 답할 물음이 아니다 — 경락가 타겟을 경매 축으로
--    옮기는 별도 과제다. 여기서는 **둘 다 서는 날**만 본다.
SELECT '경락가 타겟 구멍 (조사·경매 둘 다 서는 날인데 정답 0)', 'BAD',
       COUNT(*)::BIGINT,
       (SELECT COUNT(DISTINCT c.dt) FROM ref_calendar c
         WHERE c.is_open AND c.is_survey
           AND c.dt >= CURRENT_DATE - 400 AND c.dt < CURRENT_DATE)::BIGINT,
       COALESCE(string_agg(dt::TEXT, ' · ' ORDER BY dt), '없음')
FROM (
    SELECT c.dt
      FROM ref_calendar c
     WHERE c.is_open AND c.is_survey
       AND c.dt >= CURRENT_DATE - 400
       AND c.dt <  CURRENT_DATE
       --  그날 가락에 우리 규격 물량이 있었나 (있는데 타겟이 없으면 사고다)
       AND EXISTS (
            SELECT 1 FROM auction_prices_daily a
             WHERE a.auction_date = c.dt
               AND a.wholesale_market_code = '110001'
               AND a.grade_code = '11'
               AND a.item_name = '배추'
               AND a.package_name IN ('그물망', '파렛트')
               AND a.unit_weight_kg = 10
               AND a.trade_volume_kg > 0)
       AND NOT EXISTS (
            SELECT 1 FROM crop_price_train x
             WHERE x.target_dt = c.dt AND x.item_nm = '배추'
               AND x.target_auc_prc IS NOT NULL)
) hole
UNION ALL
-- ────────────────────────────────────────────────────────────────────
--  ★ 원천에 문자열 'None' 이 들어왔나 (2026-09-07 추가)
--
--  위 구멍의 **원인 쪽**을 직접 본다. 구멍이 나기 전에 잡으려는 것이다.
--  `str(None)` 이 "None" 이 되는 자리이고, 파이썬 `.get(키, 기본값)` 은
--  **키가 없을 때만** 기본값을 쓰므로 원천이 null 을 주면 못 막는다.
--
--  WARN 인 이유: 옛 자료에 464행이 남아 있고(461일에 하루 1행꼴) 그건
--  규격 필터에 안 걸려 해가 없다. **오늘 새로 생기면** 눈에 띄어야 한다.
SELECT '원천에 문자열 ''None'' (최근 7일)', 'WARN',
       COUNT(*)::BIGINT,
       (SELECT COUNT(*) FROM auction_prices_daily
         WHERE auction_date >= CURRENT_DATE - 7)::BIGINT,
       COALESCE(string_agg(DISTINCT auction_date::TEXT, ' · '), '없음')
FROM auction_prices_daily
WHERE auction_date >= CURRENT_DATE - 7
  AND (package_name = 'None' OR subclass_name = 'None' OR grade_name = 'None');
