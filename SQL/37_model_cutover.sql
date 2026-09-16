-- ============================================================
-- model_cutover — 운영 모델 교체 이력  (2026-09-16)
--
-- 왜 필요한가
--   2026-09-15 저녁에 소매가 모델(`ops_rtl`)이 바뀌었다. 학습 끝이
--   2023-12-31 에서 2025-12-31 로 옮겨 갔다. **그런데 그 사실이
--   어디에도 안 적혀 있다.** 남은 것은 백업 폴더 이름뿐이다
--   (`ops_rtl_교체전_20260915`). 화면도 채팅도 «언제 무엇으로 바뀌었나» 를
--   말할 수 없다.
--
--   배치 실행 이력(`batch_run`)과 도우미 보고서(`agent_report`)는 이미
--   이 DB 에 있다. 모델만 없다. 그 구멍을 메우는 표다.
--
-- ★ 모델 «이름» 은 교체해도 안 바뀐다.
--   매입 파트 필터가 `model_ver = ANY('ops_auc','ops_whsl','ops_rtl')`
--   **정확히 일치**라, 이름을 바꾸면 저쪽이 에러 없이 0건이 된다
--   (CLAUDE.md §5.11). 그래서 «지금 어느 모델인가» 는 이름으로 못 가린다.
--   **만든 날(meta.json 의 created_at) + 학습 끝(train_end)** 으로 가린다.
--   그 두 값을 교체 전/후로 나란히 담는 것이 이 표의 요점이다.
--
-- ★ 파일이 원본이고 이 표는 사본이다.
--   여기 쓰기가 실패해도 번들은 이미 바뀌었고 배치도 안 선다.
--   `agent/core.py` 의 `log_cutover()` 가 그렇게 되어 있다 —
--   `to_db()` 와 같은 원칙이다. 알리다가 본 일을 망치면 본말전도다.
--
-- ★ 담는 것과 안 담는 것
--   담는다     운영 번들(ops_auc · ops_whsl · ops_rtl)이 다른 번들로
--              바뀐 일. 되돌리기도 한 행이다 (actor='되돌리기').
--   안 담는다  후보 만들기 · 후보 지우기 · 그림자 번들.
--              운영에 나가는 값이 안 바뀌므로 이력이 아니다.
-- ============================================================

CREATE TABLE IF NOT EXISTS model_cutover (
    id              bigserial PRIMARY KEY,
    kind            text NOT NULL CHECK (kind IN ('AUC', 'WHSL', 'RTL')),
    model_ver       text NOT NULL,
    old_bundle      text,
    new_bundle      text,
    old_train_end   date,
    new_train_end   date,
    old_created_at  timestamp,
    new_created_at  timestamp,
    swapped_at      timestamp NOT NULL,
    time_known      boolean NOT NULL DEFAULT true,
    actor           text,
    note            text,
    saved_at        timestamptz NOT NULL DEFAULT now(),
    UNIQUE (kind, swapped_at)
);

--   ★ 표가 이미 있으면 위 CREATE 는 통째로 건너뛴다. 그러면 나중에 더한
--     칸이 안 생긴다. 그래서 칸을 따로 한 번 더 건다 — 이미 있으면 아무
--     일도 안 한다. **이 파일을 다시 돌려도 안전해야 한다.**
ALTER TABLE model_cutover
    ADD COLUMN IF NOT EXISTS time_known boolean NOT NULL DEFAULT true;

COMMENT ON TABLE model_cutover IS
  '운영 모델 교체 이력. 한 행 = 교체 한 번. 원본은 ML/20260824/ml_train_kit_2/ 의 백업 폴더다';
COMMENT ON COLUMN model_cutover.kind IS
  '가격 종류. AUC=경락가 · WHSL=중도매가 · RTL=소매가';
COMMENT ON COLUMN model_cutover.model_ver IS
  '모델 이름 (ops_auc · ops_whsl · ops_rtl). ★ 교체해도 안 바뀐다 — '
  '매입 파트 필터가 정확히 일치라 바꾸면 저쪽이 에러 없이 0건이 된다';
COMMENT ON COLUMN model_cutover.old_bundle IS
  '바뀌기 전 번들이 옮겨 간 백업 폴더 이름 (예: ops_rtl_교체전_20260915)';
COMMENT ON COLUMN model_cutover.new_bundle IS
  '새로 꽂힌 번들이 원래 있던 폴더 이름 (예: ops_rtl_cand_20260912)';
COMMENT ON COLUMN model_cutover.old_train_end IS
  '바뀌기 전 번들의 학습 끝 날짜. meta.json 의 train_end';
COMMENT ON COLUMN model_cutover.new_train_end IS
  '새 번들의 학습 끝 날짜. meta.json 의 train_end';
COMMENT ON COLUMN model_cutover.old_created_at IS
  '바뀌기 전 번들을 «만든 날». meta.json 의 created_at. ★ 한국시간 그대로(시간대 없음)';
COMMENT ON COLUMN model_cutover.new_created_at IS
  '새 번들을 «만든 날». meta.json 의 created_at. ★ 한국시간 그대로(시간대 없음)';
COMMENT ON COLUMN model_cutover.swapped_at IS
  '★ 교체한 시각. 한국 시간 그대로다 (시간대 없는 값). agent_report.ran_at 과 같은 규칙 — '
  'DB 시계가 UTC 라 시간대 있는 칸에 넣으면 9시간 밀린다';
COMMENT ON COLUMN model_cutover.time_known IS
  '거짓이면 날짜만 확실하고 시각은 모른다 — 백필에서 이름 바꾸기로 만든 백업 폴더. '
  '그런 행의 swapped_at 은 그 날 00:00:00 이다. 화면은 이 칸이 거짓이면 시각을 감춰야 한다';
COMMENT ON COLUMN model_cutover.actor IS
  '누가 바꿨나. 배치 · 사람 · 되돌리기 · 시뮬레이션 · 추정(백업 폴더)';
COMMENT ON COLUMN model_cutover.note IS
  '한 줄 설명. 시각이 확실하지 않으면 «추정» 과 그 근거를 여기 적는다';

CREATE INDEX IF NOT EXISTS ix_model_cutover_kind_at
    ON model_cutover (kind, swapped_at DESC);

-- ── 검증 ────────────────────────────────────────────────────
-- [1] 표가 생겼나
SELECT to_regclass('model_cutover') AS model_cutover;

-- [2] 들어 있는 것 전부 (오래된 것부터)
SELECT kind, model_ver, swapped_at, time_known, actor,
       old_bundle, old_train_end, old_created_at,
       new_bundle, new_train_end, new_created_at, note
  FROM model_cutover
 ORDER BY swapped_at, kind;

-- [3] 종류별 마지막 교체 — 화면이 «최근 업데이트» 로 쓰는 값
SELECT DISTINCT ON (kind) kind, model_ver, swapped_at, time_known, actor,
       new_train_end, new_created_at, note
  FROM model_cutover
 ORDER BY kind, swapped_at DESC;
