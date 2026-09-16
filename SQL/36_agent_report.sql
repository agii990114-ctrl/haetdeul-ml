-- ============================================================
-- agent_report — 감시 도우미 보고서 보관  (2026-09-16)
--
-- 왜 필요한가
--   도우미 보고서는 지금 **파일로만** 있다 (`진행기록/agent_logs/`).
--   우리 PC 에서 화면(3100)을 열어야 보인다. 그런데 팀 채팅(마스터 에이전트)
--   쪽에서 «오늘 데이터 처리 잘 됐어?» 같은 질문에 답하려면 저쪽 서버가
--   같은 내용을 읽을 수 있어야 한다. 저쪽은 우리 파일을 못 본다.
--
--   배치 실행 기록(batch_run)은 이미 이 DB 에 있어서 저쪽이 읽고 있다.
--   보고서만 없다. 그 구멍을 메우는 표다.
--
-- ★ 파일이 원본이고 이 표는 사본이다.
--   여기 쓰기가 실패해도 파일은 이미 남았고 배치도 안 선다.
--   `agent/core.py` 의 저장이 그렇게 되어 있다 — 같은 방식이다.
--
-- ★ 담는 것과 안 담는 것
--   담는다     감시 도우미 보고서 (수집검사 · 데이터품질 · 드리프트감지 ·
--              배치장애조사 · 재학습판정 · 재학습검증 · 뉴스요약)
--              + 아침 AI 점검 보고서 (name='claude_check')
--   안 담는다  실험 결과(`실험결과/`) · 학습 기록(`ML/`).
--              그때그때 모양이 다르고 크다. 질문에 답하는 데도 안 쓴다
-- ============================================================

CREATE TABLE IF NOT EXISTS agent_report (
    id           bigserial PRIMARY KEY,
    name         text NOT NULL,
    verdict      text,
    ran_at       timestamp NOT NULL,
    payload      jsonb,
    body         text,
    source_file  text,
    saved_at     timestamptz NOT NULL DEFAULT now(),
    UNIQUE (name, ran_at)
);

COMMENT ON TABLE agent_report IS
  '감시 도우미 보고서 사본. 원본은 진행기록/agent_logs/ 의 파일이다';
COMMENT ON COLUMN agent_report.name IS
  '도우미 이름. 파일 이름 뒷부분과 같다 (수집검사 · 데이터품질 · …). AI 점검은 claude_check';
COMMENT ON COLUMN agent_report.verdict IS
  '정상 · 주의 · 이상. 판정을 내지 않는 보고서(claude_check)는 NULL';
COMMENT ON COLUMN agent_report.ran_at IS
  '★ 한국 시간 그대로다 (시간대 없는 값). 파일 이름에 박힌 시각과 같은 값을 넣는다. '
  'DB 시계가 UTC 라 시간대 있는 칸에 넣으면 9시간 밀린다';
COMMENT ON COLUMN agent_report.payload IS
  '.json 파일 내용 그대로. 판정 배지와 근거 수치가 구조로 들어 있다';
COMMENT ON COLUMN agent_report.body IS
  '.txt(또는 .md) 파일 내용 그대로. 사람이 읽는 글. 요약하지 않는다';
COMMENT ON COLUMN agent_report.source_file IS
  '원본 파일 이름. «이상하다» 싶을 때 파일을 바로 찾기 위한 것';

CREATE INDEX IF NOT EXISTS ix_agent_report_name_ran
    ON agent_report (name, ran_at DESC);
CREATE INDEX IF NOT EXISTS ix_agent_report_ran
    ON agent_report (ran_at DESC);

-- ── 검증 ────────────────────────────────────────────────────
-- [1] 표가 생겼나
SELECT to_regclass('agent_report') AS agent_report;

-- [2] 도우미별로 몇 건이 들어 있나 · 마지막이 언제인가
SELECT name, COUNT(*) AS 건수, MAX(ran_at) AS 마지막
  FROM agent_report GROUP BY name ORDER BY 마지막 DESC;
