# -*- coding: utf-8 -*-
"""AI 도우미가 쓸 조회 도구 (2026-08-31).

## 무엇인가

AI 가 스스로 "이걸 보여줘" 라고 요청할 수 있는 기능 목록이다.
**이게 있어야 AI 호출이 아니라 agent 가 된다** — 무엇을 볼지 AI 가 정한다.

## 안전선

  · **전부 읽기 전용.** 쓰기·삭제·실행 도구는 주지 않는다
  · DB 는 `SELECT` 만. 정해둔 표 목록 밖은 거부
  · 파일은 우리 작업 폴더 안만. `..` 로 빠져나가는 것 차단
  · **모든 반환값이 mask() 를 지난다.** 예외 없음
  · 한 번에 돌려주는 양에 상한 (AI 컨텍스트 낭비·비용 방지)

## 왜 이 다섯 개인가

2026-08-31 사고를 사람이 조사할 때 실제로 밟은 순서다.

    실패했나?          → batch_recent
    무슨 오류였나?      → batch_stages   ← 오류 원문이 여기 있다
    뭘 바꿨더라?        → recent_changes
    그 코드가 뭐하지?   → read_file
    데이터는 멀쩡한가?  → db_query
"""
from __future__ import annotations

import datetime
import io
import os
from pathlib import Path

from mask import mask, mask_all

ROOT = Path(__file__).resolve().parent.parent

# ★ 조사에서 감출 폴더 (2026-08-31)
#   채점 파일(bench.py)에 **정답이 그대로 적혀 있다.** 검색 도구를 만들자마자
#   AI 가 그걸 찾아낼 수 있게 됐다. 그러면 조사 능력이 아니라 "정답지를 찾는
#   능력" 을 재는 셈이라 시험이 무의미해진다.
#   도우미 자신의 코드는 조사 대상이 아니므로 통째로 감춘다.
HIDE_DIRS = {"agent", ".venv", "__pycache__", ".git", "node_modules", "mainproject"}

# DB 조회를 허용할 표. 여기 없는 표는 거부한다.
ALLOWED_TABLES = {
    "batch_run", "batch_run_stage",
    "auction_prices_daily", "veg_daily_price_raw", "daily_volume",
    "crop_price_train", "predict_input", "prediction_log",
    "ref_calendar", "ref_prediction_quality",
}
MAX_ROWS = 50
MAX_CHARS = 6000

# 읽기를 거부할 파일. 이름 전체로 막는다 (확장자만으로는 .env 를 못 막는다).
DENY_NAMES = {"service_key.txt", "credentials.json", "id_rsa", ".netrc"}
DENY_SUFFIX = {".key", ".pem", ".p12", ".pfx", ".keystore"}


def _env(name: str) -> str | None:
    v = os.environ.get(name)
    if v:
        return v
    p = ROOT / ".env"
    if not p.exists():
        return None
    for line in io.open(p, encoding="utf-8", errors="ignore"):
        if line.strip().startswith(name + "="):
            return line.split("=", 1)[1].strip()
    return None


def _db():
    import psycopg
    url = _env("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL 이 없습니다.")
    return psycopg.connect(url)


def _clip(text: str) -> str:
    if len(text) <= MAX_CHARS:
        return text
    return text[:MAX_CHARS] + f"\n… (너무 길어 {len(text) - MAX_CHARS}자 잘림)"


# ── 도구 ────────────────────────────────────────────────────────────

def batch_recent(limit: int = 10) -> str:
    """최근 배치 실행 목록. 언제 돌았고 어디서 실패했나."""
    limit = max(1, min(int(limit), 30))
    with _db() as c:
        rows = c.execute(
            "SELECT run_id, started_at::timestamp(0), status, n_ok, n_fail, note "
            "FROM batch_run ORDER BY run_id DESC LIMIT %s", (limit,)).fetchall()
    out = ["run_id | 시작(UTC) | 상태 | 성공 | 실패 | 비고"]
    for r in rows:
        out.append(f"{r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5] or ''}")
    return mask("\n".join(out))


def batch_stages(run_id: int) -> str:
    """한 실행의 단계별 결과. **오류 원문이 여기 들어 있다.**"""
    with _db() as c:
        rows = c.execute(
            "SELECT seq, stage, ok, duration_s, message FROM batch_run_stage "
            "WHERE run_id=%s ORDER BY seq", (int(run_id),)).fetchall()
    if not rows:
        return f"run_id {run_id} 의 단계 기록이 없습니다."
    out = []
    for seq, stage, ok, dur, msg in rows:
        head = f"[{seq}] {stage} · {'성공' if ok else '실패'} · {dur}초"
        body = (msg or "").strip()
        # 성공한 단계는 앞부분만. 실패한 단계는 넉넉히 준다
        body = body[:300] if ok else body[:2500]
        out.append(head + ("\n" + body if body else ""))
    return _clip(mask("\n\n".join(out)))


def recent_changes(days: int = 7, pattern: str = "*.py") -> str:
    """최근 며칠 사이 고쳐진 파일. 고장의 원인이 최근 변경인 경우가 많다."""
    days = max(1, min(int(days), 60))
    cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
    skip = HIDE_DIRS
    found = []
    for p in ROOT.rglob(pattern):
        if any(s in p.parts for s in skip):
            continue
        try:
            m = datetime.datetime.fromtimestamp(p.stat().st_mtime)
        except OSError:
            continue
        if m >= cutoff:
            found.append((m, p.relative_to(ROOT).as_posix(), p.stat().st_size))
    found.sort(reverse=True)
    out = [f"최근 {days}일 수정 · {pattern} · {len(found)}개"]
    for m, rel, size in found[:40]:
        out.append(f"{m:%Y-%m-%d %H:%M}  {rel}  ({size:,}바이트)")
    return mask("\n".join(out))


def read_file(path: str, start: int = 1, lines: int = 80) -> str:
    """파일을 줄 번호와 함께 읽는다. 우리 작업 폴더 안만 허용."""
    lines = max(1, min(int(lines), 200))
    start = max(1, int(start))
    target = (ROOT / path).resolve()
    if ROOT not in target.parents and target != ROOT:
        return f"거부: 작업 폴더 밖입니다 ({path})"
    if not target.is_file():
        return f"없는 파일입니다: {path}"
    if any(part in HIDE_DIRS for part in target.relative_to(ROOT).parts[:-1]):
        return f"거부: 조사 대상이 아닌 폴더입니다 ({path})"
    #   ★ `.env` 는 suffix 가 아니라 **파일 이름 전체**다.
    #     Path(".env").suffix 는 빈 문자열이라 확장자 검사로는 못 막는다.
    #     실제로 첫 시험에서 .env 가 그대로 읽혔다 (값은 가림 처리로 살았지만
    #     읽히는 것 자체가 막혔어야 한다).
    name = target.name.lower()
    if (name.startswith(".env") or name in DENY_NAMES
            or target.suffix.lower() in DENY_SUFFIX):
        return f"거부: 비밀이 들어 있을 수 있는 파일입니다 ({path})"
    try:
        all_lines = io.open(target, encoding="utf-8", errors="replace").read().splitlines()
    except Exception as e:                                   # noqa: BLE001
        return f"읽기 실패: {type(e).__name__}"
    seg = all_lines[start - 1:start - 1 + lines]
    body = "\n".join(f"{start + i:>5}| {t}" for i, t in enumerate(seg))
    head = f"{path} · 전체 {len(all_lines)}줄 · {start}~{start + len(seg) - 1}줄"
    return _clip(mask(head + "\n" + body))


def search_code(keyword: str, pattern: str = "*.py") -> str:
    """낱말이 나오는 파일과 줄을 찾는다.

    ★ 이 도구가 없으면 AI 가 파일을 100줄씩 넘겨가며 헤맨다 (첫 채점에서
      실제로 run_batch.py 를 5번 연속 읽었다). 오류 문구에 나온 이름을
      **어디서 찾아야 할지** 알려주는 게 조사의 출발점이다.
    """
    kw = (keyword or "").strip()
    if len(kw) < 2:
        return "거부: 두 글자 이상으로 찾아주세요."
    skip = HIDE_DIRS
    hits, files = [], 0
    for p in ROOT.rglob(pattern):
        if any(s in p.parts for s in skip) or not p.is_file():
            continue
        if p.name.lower().startswith(".env"):
            continue
        try:
            lines = io.open(p, encoding="utf-8", errors="replace").read().splitlines()
        except Exception:                                    # noqa: BLE001
            continue
        found = [(i + 1, t) for i, t in enumerate(lines) if kw in t]
        if not found:
            continue
        files += 1
        rel = p.relative_to(ROOT).as_posix()
        for ln, t in found[:6]:
            hits.append(f"{rel}:{ln}| {t.strip()[:120]}")
        if len(found) > 6:
            hits.append(f"{rel}  … 그 파일에 {len(found) - 6}곳 더")
        if len(hits) > 60:
            hits.append("… (너무 많아 잘림. 낱말을 더 좁혀주세요)")
            break
    if not hits:
        return f"'{kw}' 를 {pattern} 에서 찾지 못했습니다."
    return _clip(mask(f"'{kw}' · 파일 {files}개\n" + "\n".join(hits)))


def db_query(sql: str) -> str:
    """DB 조회. SELECT 만 · 허용된 표만 · 최대 50행."""
    s = " ".join(sql.split())
    low = s.lower()
    if not low.startswith("select") and not low.startswith("with"):
        return "거부: SELECT 로 시작하는 조회만 됩니다."
    for bad in ("insert", "update", "delete", "drop", "alter", "truncate",
                "create", "grant", "copy"):
        if f" {bad} " in f" {low} ":
            return f"거부: '{bad}' 는 쓸 수 없습니다."
    used = {t for t in ALLOWED_TABLES if t in low}
    if not used:
        return ("거부: 허용된 표를 쓰지 않았습니다.\n허용 표: "
                + ", ".join(sorted(ALLOWED_TABLES)))
    try:
        with _db() as c:
            cur = c.cursor()
            cur.execute(s)
            cols = [d.name for d in cur.description]
            rows = cur.fetchmany(MAX_ROWS)
    except Exception as e:                                   # noqa: BLE001
        return mask(f"조회 실패: {type(e).__name__}: {e}")
    out = [" | ".join(cols)]
    for r in rows:
        out.append(" | ".join("" if v is None else str(v) for v in r))
    if len(rows) == MAX_ROWS:
        out.append(f"… (최대 {MAX_ROWS}행까지만)")
    return _clip(mask("\n".join(out)))


TOOLS = {
    "batch_recent": batch_recent,
    "batch_stages": batch_stages,
    "recent_changes": recent_changes,
    "read_file": read_file,
    "search_code": search_code,
    "db_query": db_query,
}

# AI 에게 알려줄 설명. 이름·인자를 여기서 한 번만 적는다.
SPEC = [
    {"name": "batch_recent",
     "description": "최근 배치 실행 목록 (언제 돌았고 어디서 실패했는지)",
     "params": {"limit": "몇 건을 볼지 (기본 10, 최대 30)"}},
    {"name": "batch_stages",
     "description": "한 실행의 단계별 결과와 **오류 원문**. 실패 조사의 출발점",
     "params": {"run_id": "batch_recent 에서 본 run_id"}},
    {"name": "recent_changes",
     "description": "최근 며칠 사이 고쳐진 파일 목록. 고장 원인이 최근 변경인 경우가 많다",
     "params": {"days": "며칠 (기본 7)", "pattern": "파일 형태 (기본 *.py)"}},
    {"name": "read_file",
     "description": "파일을 줄 번호와 함께 읽는다",
     "params": {"path": "작업 폴더 기준 경로", "start": "시작 줄", "lines": "몇 줄 (최대 200)"}},
    {"name": "search_code",
     "description": "낱말이 나오는 파일과 줄을 찾는다. **오류 문구에 나온 이름을 "
                    "어디서 찾을지 모를 때 이걸 먼저 쓴다**",
     "params": {"keyword": "찾을 낱말", "pattern": "파일 형태 (기본 *.py)"}},
    {"name": "db_query",
     "description": "DB 조회. SELECT 만, 허용된 표만, 최대 50행",
     "params": {"sql": "SELECT 문"}},
]


if __name__ == "__main__":
    print("=" * 70)
    print("도구 시험")
    print("=" * 70)
    print("\n[batch_recent]")
    print(batch_recent(4))
    print("\n[recent_changes 3일]")
    print(recent_changes(3)[:400])
    print("\n[read_file 거부 시험]")
    print(read_file("../../../etc/passwd"))
    print(read_file(".env"))
    print("\n[db_query 거부 시험]")
    print(db_query("DROP TABLE batch_run"))
    print(db_query("SELECT * FROM pg_user"))
    print("\n[db_query 정상]")
    print(db_query("SELECT run_id, status FROM batch_run ORDER BY run_id DESC LIMIT 3"))
