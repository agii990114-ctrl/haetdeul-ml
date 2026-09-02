-- ============================================================
-- prediction_log.gate_reason 추가  (2026-08-25)
--   기존 컬럼·행을 건드리지 않는 **추가 전용** 마이그레이션입니다.
--   다른 파트의 조회는 영향받지 않습니다.
--
--   왜 필요한가
--     `gated = true` 는 "모델을 쓰지 않고 앵커를 그대로 냈다" 는 뜻인데,
--     사유가 두 가지로 늘었습니다.
--
--       lead_time        LT<3. 어제 가격이 이미 정답에 가까워 모델이 개입할 여지가 없다
--       quality          품목×타겟 조합이 baseline 보다 나쁘다 (ref_prediction_quality)
--       quality:unknown  품질표에 없는 조합. 검증 전이므로 안전하게 앵커
--       lead_time+quality  둘 다
--
--     사유를 남기지 않으면 "왜 이 예측은 앵커와 같나" 에 답할 수 없습니다.
--     특히 품질 게이트는 **조합 단위로 통째로** 걸리므로, 사유 없이 보면
--     모델이 고장난 것처럼 보입니다.
-- ============================================================
ALTER TABLE prediction_log
    ADD COLUMN IF NOT EXISTS gate_reason text;

COMMENT ON COLUMN prediction_log.gate_reason IS
  'gated=true 인 사유. lead_time(LT<3) · quality(조합이 baseline 이하) · '
  'quality:unknown(품질표에 없는 조합) · lead_time+quality. gated=false 면 NULL';

-- ── 검증 ────────────────────────────────────────────────────
-- [1] gated 와 gate_reason 의 정합성
--     확인: gated=true 인데 사유가 비어 있으면 안 된다 (기존 더미 행은 예외).
SELECT gated,
       COALESCE(gate_reason, '(없음)') AS 사유,
       COUNT(*)                        AS 행수
FROM prediction_log
GROUP BY 1, 2 ORDER BY 1 DESC, 3 DESC;

-- [2] 게이트된 행은 예측이 앵커와 같아야 한다
--     확인: 불일치 0. 1건이라도 나오면 게이트 적용에 구멍이 있다.
SELECT COUNT(*)                                                   AS 게이트행,
       COUNT(*) FILTER (WHERE pred_prc IS DISTINCT FROM anchor_prc) AS 앵커불일치
FROM prediction_log
WHERE gated;
