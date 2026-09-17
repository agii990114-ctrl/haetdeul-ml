# -*- coding: utf-8 -*-
"""같은 초에 저장된 보고서 둘이 서로를 덮지 않는가.

## 어떻게 돌리나

    cd C:\\IDE\\workplace\\mainproject_jh_workplace
    set PYTHONIOENCODING=utf-8
    python agent/tests/test_same_second.py

통과하면 종료코드 0, 실패하면 1 이다. 무엇이 어긋났는지 `*** 실패:` 줄로 찍는다.
**DB 에 붙는다** — `.env` 의 `DATABASE_URL` 이 있어야 돈다.

## 무엇을 지키나

2026-09-16 09:09:08 에 재학습판정 **whsl**(0초 만에 끝남)과 **rtl** 이 같은 초에
`Report.save()` 되어 둘 다 잃을 뻔했다.

    파일   stem 이 `%Y-%m-%d_%H%M%S_{name}` 뿐이라 rtl 이 whsl 파일을 **덮었다**
    DB     `UNIQUE (name, ran_at)` + `ON CONFLICT DO NOTHING` 이라 뒤엣것이
           **조용히 버려졌다**

09-11 은 1초 차이라 운으로 둘 다 남았다. **운에 기대지 않게 하려고 이 시험이 있다.**

그래서 이 시험이 지키는 것은 넷이다.

    ① 같은 초 · 같은 이름 · 다른 종류면 `.txt` 가 **둘** 남는다
    ② `.json` 도 **둘** 남는다
    ③ DB `agent_report` 에 **두 행**이 들어가고 `kind` 칸이 whsl · rtl 로 갈린다
    ④ 그 파일을 다시 밀어넣어도(`ops/agent_log_to_db.py`) **두 벌이 안 된다**
       — 저장 경로와 파일 밀어넣기 경로가 **같은 열쇠**를 내야 한다

## 운영 자료와 안 겹치게

기준 시각을 **1999-01-01 09:09:08** 로 둔다. 이 프로젝트 자료는 2015년부터라
그 앞은 한 행도 없다. 시험이 도중에 죽어 정리를 못 해도 **운영 기록에 섞이지
않는다.** 보고서 폴더도 `진행기록/agent_logs_test/` 로 따로 쓴다.
시작할 때와 끝날 때 두 번 지운다 — 앞선 실행이 남긴 것이 있어도 깨끗해진다.
"""
from __future__ import annotations

import datetime
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from agent.core import Finding, OK, Report, db          # noqa: E402

SUB = "agent_logs_test"
DIR = ROOT / "진행기록" / SUB
#: ★ 운영 자료(2015~)와 절대 안 겹치는 시각. 머리말 참조.
AT = datetime.datetime(1999, 1, 1, 9, 9, 8)
NAME = "재학습판정"


def cleanup() -> None:
    if DIR.exists():
        shutil.rmtree(DIR)
    try:
        with db() as c:
            with c.cursor() as cur:
                cur.execute("DELETE FROM agent_report WHERE name = %s AND ran_at = %s",
                            (NAME, AT))
                n = cur.rowcount
            c.commit()
        print(f"   [정리] DB 행 {n}개 삭제 · 폴더 삭제")
    except Exception as e:                                # noqa: BLE001
        print(f"   [정리] DB 삭제 실패: {type(e).__name__}: {e}")


def main() -> int:
    cleanup()
    for kind in ("whsl", "rtl"):
        r = Report(NAME, started=AT, kind=kind)
        r.add(Finding(OK, f"{kind} — 시험용 보고서", "지워도 되는 줄입니다."))
        r.save(subdir=SUB)

    txts = sorted(p.name for p in DIR.glob("*.txt"))
    jsons = sorted(p.name for p in DIR.glob("*.json"))
    print(f"파일 .txt  {len(txts)}개  {txts}")
    print(f"파일 .json {len(jsons)}개  {jsons}")

    with db() as c, c.cursor() as cur:
        cur.execute("SELECT name, kind, ran_at, source_file, payload->>'kind'"
                    "  FROM agent_report WHERE name = %s AND ran_at = %s"
                    " ORDER BY id", (NAME, AT))
        rows = cur.fetchall()
    print(f"DB 행 {len(rows)}개")
    for r in rows:
        print("   ", r)

    ok = True
    if len(txts) != 2:
        print(f"*** 실패: .txt 가 2개여야 하는데 {len(txts)}개")
        ok = False
    if len(jsons) != 2:
        print(f"*** 실패: .json 이 2개여야 하는데 {len(jsons)}개")
        ok = False
    if len(rows) != 2:
        print(f"*** 실패: DB 행이 2개여야 하는데 {len(rows)}개")
        ok = False
    if {r[1] for r in rows} != {"whsl", "rtl"}:
        print(f"*** 실패: DB kind 칸이 {{whsl, rtl}} 이어야 하는데 "
              f"{sorted(str(r[1]) for r in rows)}")
        ok = False

    #   ④ 두 번 넣어도 두 벌이 되지 않는가 (파일에서 다시 밀어넣기)
    from ops.agent_log_to_db import _one                  # noqa: PLC0415
    for p in sorted(DIR.glob("*.txt")):
        _one(p)
        _one(p)
    with db() as c, c.cursor() as cur:
        cur.execute("SELECT count(*) FROM agent_report WHERE name = %s AND ran_at = %s",
                    (NAME, AT))
        again = cur.fetchone()[0]
    print(f"파일에서 두 번 더 밀어넣은 뒤 DB 행 {again}개 (2 여야 한다)")
    if again != 2:
        print(f"*** 실패: 두 번 돌렸더니 {again}개")
        ok = False

    cleanup()
    print("통과" if ok else "실패")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
