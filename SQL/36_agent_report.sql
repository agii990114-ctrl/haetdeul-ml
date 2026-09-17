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
    kind         text,
    verdict      text,
    ran_at       timestamp NOT NULL,
    payload      jsonb,
    body         text,
    source_file  text,
    saved_at     timestamptz NOT NULL DEFAULT now()
);

-- ── 가격 종류 칸 (2026-09-16 추가) ──────────────────────────
--
-- ★ 왜 칸으로 빼나
--   재학습판정·재학습검증은 **가격 종류마다 한 건씩** 나온다. 전에는
--   종류가 `payload->>'kind'` 안에만 있어서 ① 채팅 쪽이 이름을 못 달았고
--   ② 열쇠에 넣을 수가 없었다.
--
-- ★ 왜 열쇠에 넣어야 하나 — **같은 초에 저장된 둘이 서로를 덮었다.**
--   2026-09-16 09:09:08 에 재학습판정 whsl(0초 만에 끝남)과 rtl 이 같은
--   초에 저장됐다. 옛 유일 제약이 (name, ran_at) 뿐이라 뒤엣것이
--   `ON CONFLICT DO NOTHING` 에 걸려 **조용히 버려졌다.**
--   09-11 은 1초 차이라 운으로 둘 다 남았다.
--
-- ★ 종류가 없는 보고서는 그대로다. `COALESCE(kind,'')` 라 빈 문자열이 되어
--   예전과 똑같이 (이름 · 시각)으로만 갈린다. **NULL 을 그대로 쓰면
--   안 된다** — SQL 에서 NULL 은 서로 같지 않아 유일 제약이 안 걸린다.
ALTER TABLE agent_report ADD COLUMN IF NOT EXISTS kind text;

COMMENT ON TABLE agent_report IS
  '감시 도우미 보고서 사본. 원본은 진행기록/agent_logs/ 의 파일이다';
COMMENT ON COLUMN agent_report.name IS
  '도우미 이름. 파일 이름 뒷부분과 같다 (수집검사 · 데이터품질 · …). AI 점검은 claude_check. '
  '★ 가격 종류 접미(_auc 등)는 여기 안 들어간다 — kind 칸으로 간다';
COMMENT ON COLUMN agent_report.kind IS
  '가격 종류 auc · whsl · rtl. 종류가 없는 보고서(수집검사 · 데이터품질 · …)는 NULL. '
  '★ payload->>''kind'' 와 같은 값이다. 열쇠에 쓰려고 칸으로 뺐다';
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

-- 지나간 행에 종류를 채운다. **근거는 payload 하나뿐이다** — 없으면 NULL 로
-- 둔다. 지어내지 않는다. 이미 채워진 행은 안 건드린다.
UPDATE agent_report
   SET kind = payload ->> 'kind'
 WHERE kind IS NULL
   AND payload ->> 'kind' IS NOT NULL;

-- 초 아래 자리 때문에 두 벌이 된 행을 지운다 (2026-09-16 · 실측 4행).
--
-- ★ 저장할 때는 `datetime.now()` 의 마이크로초가 그대로 들어갔고, 파일에서
--   밀어넣을 때는 파일 이름의 초까지만 들어갔다. 같은 보고서가 두 행이 됐다.
--   `agent/core.py` 의 `to_db()` 가 이제 초 아래를 자른다.
--   **초 단위 짝이 있을 때만** 지운다 — 짝이 없으면 그게 유일한 사본이다.
DELETE FROM agent_report a
 WHERE a.ran_at <> date_trunc('second', a.ran_at)
   AND EXISTS (SELECT 1 FROM agent_report b
                WHERE b.name = a.name
                  AND COALESCE(b.kind, '') = COALESCE(a.kind, '')
                  AND b.ran_at = date_trunc('second', a.ran_at)
                  AND b.id <> a.id);

-- 짝이 없던 것은 지우지 말고 초로 맞춘다.
UPDATE agent_report
   SET ran_at = date_trunc('second', ran_at)
 WHERE ran_at <> date_trunc('second', ran_at);

-- 옛 유일 제약을 내리고 표현식 유일 인덱스로 바꾼다. **순서가 중요하다** —
-- 위 UPDATE 는 열쇠를 더 잘게 가를 뿐이라 새 인덱스가 걸릴 일이 없다.
ALTER TABLE agent_report DROP CONSTRAINT IF EXISTS agent_report_name_ran_at_key;

CREATE UNIQUE INDEX IF NOT EXISTS ux_agent_report_name_ran_kind
    ON agent_report (name, ran_at, (COALESCE(kind, '')));

CREATE INDEX IF NOT EXISTS ix_agent_report_name_ran
    ON agent_report (name, ran_at DESC);
CREATE INDEX IF NOT EXISTS ix_agent_report_ran
    ON agent_report (ran_at DESC);

-- ── 검증 ────────────────────────────────────────────────────
-- [1] 표가 생겼나
SELECT to_regclass('agent_report') AS agent_report;

-- [2] 도우미별 · 종류별로 몇 건이 들어 있나 · 마지막이 언제인가
SELECT name, kind, COUNT(*) AS 건수, MAX(ran_at) AS 마지막
  FROM agent_report GROUP BY name, kind ORDER BY 마지막 DESC;

-- [3] 칸과 payload 가 어긋난 행이 있나. **0 이어야 한다**
SELECT COUNT(*) AS kind_어긋남
  FROM agent_report
 WHERE COALESCE(kind, '') <> COALESCE(payload ->> 'kind', '');

-- [4] 유일 제약이 새 것으로 바뀌었나.
--     ux_agent_report_name_ran_kind 하나만 나와야 하고,
--     agent_report_name_ran_at_key 는 없어야 한다
SELECT indexname, indexdef
  FROM pg_indexes
 WHERE tablename = 'agent_report' AND indexdef LIKE '%UNIQUE%'
 ORDER BY indexname;

-- [5] 같은 (이름 · 시각)에 종류가 다른 보고서가 실제로 몇 쌍 있나.
--     ★ 이게 0 이 아니라는 것이 이 고침이 필요했다는 증거다
SELECT name, ran_at, COUNT(*) AS 건수,
       string_agg(COALESCE(kind, '(없음)'), ', ' ORDER BY kind) AS 종류들
  FROM agent_report
 GROUP BY name, ran_at HAVING COUNT(*) > 1
 ORDER BY ran_at DESC;
