-- ============================================================
-- ref_prediction_quality v2 — 운영 실측 구간 추가  (2026-08-25)
--
-- 왜 고치나
--   v1 은 검증 2023 · 테스트 2024~25 두 구간으로 판정했다. 이제 운영 실측
--   (2026-01~08, prediction_log 47,250행 채점)이 생겨 구간이 셋이 됐는데
--   넣을 자리가 없었다.
--
--   그리고 v1 판정이 실제로 틀린 곳이 있었다. **경락 양파는 2026 에 +21.0%
--   (8개월 중 7개월 양수)로 아홉 조합 중 두 번째로 좋다.** 그런데 차단돼 있어
--   가장 잘 맞는 매입 신호 하나를 스스로 버리고 있었다.
--
-- ▣ 판정 규칙 ★
--   use_recommended = (검증2023 · 테스트2024~25 · 운영2026 중
--                      **2개 이상 구간에서 +1%p 초과**)
--
--   한 구간으로 정하지 않는다. 2026-06~07 45일만 보고 "여섯 중 다섯이 음수" 로
--   결론 냈다가 8개월로 넓히자 뒤집힌 일이 같은 날 있었다 (실전채점_2026구간).
--   feature 판정의 2폴드 규칙(CLAUDE.md 5.7)과 같은 원리다.
--
--   +1%p 문턱을 두는 이유: 중도매 무의 운영 실측이 +0.2% 다. 부호는 양수지만
--   사실상 동률이고, 테스트에서 −13.2% 였다. 0 근처를 "개선" 으로 세면
--   노이즈가 판정을 뒤집는다.
--
-- ▣ 이번 변경
--   중도매 양파  차단 → **통과**  (+2.2 / −4.7 / +11.1 → 2개 구간 통과)
--   나머지 8개  판정 유지
--
--   경락 양파는 2026 만 좋아(1/3) **차단을 유지**한다. 왜 2026 만 다른지
--   모르는 채로 풀면, 다시 나빠져도 알 수 없다. 다음 구간에서 또 양수면 풀린다.
-- ============================================================

ALTER TABLE ref_prediction_quality
    ADD COLUMN IF NOT EXISTS improve_live_pct  numeric(6,1),
    ADD COLUMN IF NOT EXISTS live_window       text,
    ADD COLUMN IF NOT EXISTS live_pos_months   smallint,
    ADD COLUMN IF NOT EXISTS live_n_months     smallint,
    ADD COLUMN IF NOT EXISTS n_pass_windows    smallint,
    ADD COLUMN IF NOT EXISTS updated_at        timestamptz DEFAULT now();

COMMENT ON COLUMN ref_prediction_quality.improve_live_pct IS
  '운영 실측 개선율(%). prediction_log 채점 기준. 게이트 해제 상태에서 측정한 모델 자체의 성능';
COMMENT ON COLUMN ref_prediction_quality.live_window IS
  '운영 실측을 잰 구간과 모델. 조건 없는 수치는 기록하지 않는다';
COMMENT ON COLUMN ref_prediction_quality.live_pos_months IS
  '운영 구간에서 개선율이 양수였던 달 수. 총합이 양수라도 이 값이 낮으면 불안정하다';
COMMENT ON COLUMN ref_prediction_quality.n_pass_windows IS
  '세 구간(검증·테스트·운영) 중 +1%p 를 넘은 구간 수. 2 이상이면 use_recommended=true';
COMMENT ON COLUMN ref_prediction_quality.use_recommended IS
  '모델을 쓸지 여부. false 면 predict.py 가 앵커로 폴백하고 gate_reason=quality 를 남긴다. '
  '판정 규칙: 세 구간 중 2개 이상에서 +1%p 초과';

-- ── 운영 실측 반영 ──────────────────────────────────────────
--   측정 조건: 학습 2017~2023(ops_*) · 기준일 2026-01-02~2026-08-20 ·
--   LT<3 만 제외하고 품질 게이트는 해제 · gated 행 제외 · 대상일 실제값 대조
UPDATE ref_prediction_quality q SET
    improve_live_pct = v.imp,
    live_pos_months  = v.pos,
    live_n_months    = 8,
    live_window      = '2026-01~08 · ops(학습~2023) · 게이트 해제 측정'
FROM (VALUES
    ('auc','무',    5.4, 6), ('auc','배추',  37.7, 7), ('auc','양파',  21.0, 7),
    ('rtl','무',   13.8, 7), ('rtl','배추',  16.6, 4), ('rtl','양파',  14.5, 5),
    ('whsl','무',   0.2, 5), ('whsl','배추', 10.7, 4), ('whsl','양파', 11.1, 5)
) AS v(kind, item, imp, pos)
WHERE q.target_kind = v.kind AND q.item_nm = v.item;

-- ── 판정 재계산 ─────────────────────────────────────────────
--   세 구간 중 +1%p 를 넘은 구간 수를 세고, 2 이상이면 통과.
UPDATE ref_prediction_quality SET
    n_pass_windows =
        (CASE WHEN COALESCE(improve_valid_pct, -999) > 1 THEN 1 ELSE 0 END) +
        (CASE WHEN COALESCE(improve_test_pct,  -999) > 1 THEN 1 ELSE 0 END) +
        (CASE WHEN COALESCE(improve_live_pct,  -999) > 1 THEN 1 ELSE 0 END),
    updated_at = now();

UPDATE ref_prediction_quality SET
    use_recommended = (n_pass_windows >= 2);

-- ── 사유 갱신 ───────────────────────────────────────────────
UPDATE ref_prediction_quality SET note =
    CASE
      WHEN target_kind='whsl' AND item_nm='양파' THEN
        '2026-08-25 차단 해제. 검증 +2.2 · 테스트 -4.7 · 운영 +11.1 → 2개 구간 통과. '
        '단 월별 부호가 5/8 로 불안정하니 다음 구간에서 재확인할 것'
      WHEN target_kind='auc' AND item_nm='양파' THEN
        '차단 유지. 운영 2026 은 +21.0%(7/8개월)로 매우 좋으나 검증 -0.1 · 테스트 -6.2 라 '
        '통과 구간이 1개뿐. 2026 만 다른 이유를 모르는 채로 풀지 않는다. '
        '다음 구간에서 또 양수면 해제 대상'
      WHEN target_kind='whsl' AND item_nm='무' THEN
        '차단 유지. 운영 +0.2% 는 사실상 동률이고 테스트가 -13.2% 였다. '
        '통과 구간 1개. 조용한 달(앵커 MAPE 2% 대)에 모델이 개입해 손해를 본다'
      ELSE note
    END
WHERE target_kind IN ('auc','whsl') AND item_nm IN ('무','양파');

-- ── 검증 ────────────────────────────────────────────────────
-- [1] 최종 판정표 — 세 구간을 나란히 본다
SELECT target_kind AS 타겟, item_nm AS 품목,
       improve_valid_pct AS 검증23, improve_test_pct AS 테스트2425,
       improve_live_pct  AS 운영26,
       live_pos_months || '/' || live_n_months AS 월부호,
       n_pass_windows AS 통과구간,
       use_recommended AS 사용
FROM ref_prediction_quality
ORDER BY use_recommended DESC, target_kind, item_nm;

-- [2] 규칙 정합성 — use_recommended 가 규칙과 어긋나면 안 된다
--     확인: 불일치 0
SELECT COUNT(*) AS 전체,
       COUNT(*) FILTER (WHERE use_recommended <> (n_pass_windows >= 2)) AS 규칙불일치
FROM ref_prediction_quality;
