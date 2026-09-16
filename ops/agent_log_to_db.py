# -*- coding: utf-8 -*-
"""감시 도우미 보고서 파일을 DB(`agent_report`)에 넣는다.

## 왜 있나 (2026-09-16)

보고서는 우리 PC 의 파일로만 있다 (`진행기록/agent_logs/`). 팀 채팅 쪽
서버는 우리 파일을 못 본다. 그래서 «오늘 데이터 처리 잘 됐어?» 같은
질문에 답할 수가 없다. 같은 DB 에 사본을 두면 저쪽이 읽을 수 있다.

**새로 만드는 보고서는 `agent/core.py` 가 저장할 때 알아서 넣는다.**
이 프로그램이 맡는 것은 둘뿐이다.

    ① 예전에 쌓인 파일을 한 번에 밀어 넣기 (`--all`)
    ② AI 점검 보고서(`*_claude_check.md`) 넣기
       — 이건 도우미 뼈대를 안 거치고 Claude 가 직접 쓴 파일이라
         저장할 때 넣어 줄 자리가 없다

## 지키는 것

★ **파일이 원본이고 DB 는 사본이다.** 파일을 고치거나 지우지 않는다.

★ **두 번 넣어도 두 벌이 되지 않는다.** (이름 · 시각)이 같으면 건너뛴다.
  그래서 몇 번을 돌려도 안전하다.

★ **시각은 한국 시간 그대로 넣는다.** 파일 이름에 박힌 시각과 같은 값이다.
  DB 시계가 UTC 라 시간대 있는 칸에 넣으면 9시간 밀린다 (`CLAUDE.md` 9절).

★ **담지 않는 것** — `실험결과/` 와 `ML/` 밑의 기록. 모양이 그때그때 다르고
  크며, 질문에 답하는 데 쓰지 않는다.
"""
from __future__ import annotations

import argparse
import datetime
import io
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agent.core import to_db                                  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")     # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass

LOGS = ROOT / "진행기록" / "agent_logs"

#: 도우미 보고서 파일 이름 — `2026-09-15_092316_데이터품질.txt`
_REPORT = re.compile(r"^(\d{4}-\d{2}-\d{2})_(\d{6})_(.+)$")
#: AI 점검 보고서 — `2026-09-15_claude_check.md` · `..._claude_check_en.md`
_CHECK = re.compile(r"^(\d{4}-\d{2}-\d{2})_(claude_check(?:_en)?)$")


def _read(path: Path) -> str:
    return io.open(path, encoding="utf-8", errors="replace").read()


def _one(path: Path) -> tuple[str, str] | None:
    """파일 하나를 넣는다. (이름, 결과) 를 돌려준다."""
    stem = path.stem

    m = _REPORT.match(stem)
    if m and path.suffix == ".txt":
        day, hms, name = m.groups()
        ran_at = datetime.datetime.strptime(f"{day}_{hms}", "%Y-%m-%d_%H%M%S")
        payload, verdict = None, None
        side = path.with_suffix(".json")
        if side.exists():
            try:
                payload = json.loads(_read(side))
                verdict = payload.get("verdict")
            except Exception:                                  # noqa: BLE001
                payload = None                                 # 글은 그대로 넣는다
        ok = to_db(name, verdict, ran_at, payload, _read(path), path.name)
        return name, ("넣음" if ok else "실패")

    m = _CHECK.match(stem)
    if m and path.suffix == ".md":
        day, name = m.groups()
        #   ★ 이 파일 이름에는 시각이 없다. 파일을 만든 시각을 쓴다 —
        #     하루 한 번 나오는 글이라 이것으로 충분히 갈린다.
        made = datetime.datetime.fromtimestamp(path.stat().st_mtime)
        ran_at = datetime.datetime.combine(
            datetime.date.fromisoformat(day), made.time().replace(microsecond=0))
        ok = to_db(name, None, ran_at, None, _read(path), path.name)
        return name, ("넣음" if ok else "실패")

    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="도우미 보고서를 DB 에 사본으로 둔다")
    ap.add_argument("--all", action="store_true", help="쌓인 것 전부")
    ap.add_argument("--day", help="그 날짜만 (YYYY-MM-DD). 기본은 오늘")
    ap.add_argument("--file", help="파일 하나만")
    a = ap.parse_args()

    if a.file:
        files = [Path(a.file)]
    elif a.all:
        files = sorted(LOGS.glob("*.txt")) + sorted(LOGS.glob("*claude_check*.md"))
    else:
        day = a.day or datetime.date.today().isoformat()
        files = sorted(LOGS.glob(f"{day}_*.txt")) + sorted(LOGS.glob(f"{day}_*claude_check*.md"))

    done: dict[str, int] = {}
    skipped = failed = 0
    for f in files:
        if not f.exists():
            print(f"[없음] {f}")
            failed += 1
            continue
        got = _one(f)
        if got is None:
            skipped += 1
            continue
        name, how = got
        if how == "넣음":
            done[name] = done.get(name, 0) + 1
        else:
            failed += 1

    total = sum(done.values())
    print(f"파일 {len(files)}개 · 넣음 {total} · 건너뜀 {skipped} · 실패 {failed}")
    for name, n in sorted(done.items(), key=lambda kv: -kv[1]):
        print(f"   {name:<14} {n}")
    #   ★ 실패해도 0 으로 끝낸다. 이건 사본을 두는 일이라, 여기서 배치를
    #     세우면 «알리다가 배치를 죽이는» 꼴이 된다. 대신 위에 숫자를 찍는다.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
