# -*- coding: utf-8 -*-
"""가격 종류를 파일 이름에 붙이면서 **안 깨져야 하는 것** 둘.

## 어떻게 돌리나

    cd C:\\IDE\\workplace\\mainproject_jh_workplace
    set PYTHONIOENCODING=utf-8
    python agent/tests/test_legacy_and_nokind.py

통과하면 종료코드 0, 실패하면 1 이다. **DB 에 붙는다** — `.env` 의
`DATABASE_URL` 이 있어야 돈다.
짝이 되는 시험은 `agent/tests/test_same_second.py` 다. 둘 다 돌려야 한다.

## 무엇을 지키나

### ① 종류가 없는 도우미는 파일 이름이 **그대로**다

수집검사 · 데이터품질 · 드리프트감지 · 배치장애조사 · 뉴스요약은 가격 종류가
없다. 이름을 바꾸면 화면(3100)의 「날짜별 기록」과 DB 의 지난 기록이 갈린다.
접미는 **종류가 있는 보고서에만** 붙어야 한다.

### ② 접미가 붙기 전에 쌓인 파일을 다시 밀어넣어도 두 벌이 안 된다

2026-09-16 이전 보고서는 이름에 종류가 없고 `.json` 안에만 있다(백필된 것).
그 행은 DB 에서 `kind` 칸이 이미 채워져 있다. 그런데 `ops/agent_log_to_db.py`
가 **이름만 보고** 종류 없이 밀어넣으면 열쇠가 `(이름, 시각, '')` 이 되어
`(이름, 시각, 'auc')` 와 다른 행이 된다 — **같은 보고서가 두 벌이 된다.**

    저장 경로        agent/core.py 의 Report.save() -> to_db()
    밀어넣기 경로     ops/agent_log_to_db.py 의 _one()

**두 경로가 같은 열쇠를 내야 한다.** 그래서 이름에 접미가 없으면 `.json` 의
`kind` 로 물러선다. 이 시험이 그것을 잡는다.

## 운영 자료와 안 겹치게

기준 시각을 **1999-01-02 09:09:08** 로 둔다 (`test_same_second.py` 는 01-01).
이 프로젝트 자료는 2015년부터라 그 앞은 한 행도 없다. 시험이 도중에 죽어
정리를 못 해도 **운영 기록에 섞이지 않는다.** 보고서 폴더도
`진행기록/agent_logs_test2/` 로 따로 쓴다.
"""
from __future__ import annotations

import datetime
import io
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from agent.core import Finding, OK, Report, db          # noqa: E402
from ops.agent_log_to_db import _one                    # noqa: E402

SUB = "agent_logs_test2"
DIR = ROOT / "진행기록" / SUB
#: ★ 운영 자료(2015~)와 절대 안 겹치는 시각. 머리말 참조.
AT = datetime.datetime(1999, 1, 2, 9, 9, 8)


def cleanup() -> None:
    if DIR.exists():
        shutil.rmtree(DIR)
    try:
        with db() as c:
            with c.cursor() as cur:
                cur.execute("DELETE FROM agent_report WHERE ran_at = %s", (AT,))
                n = cur.rowcount
            c.commit()
        print(f"   [정리] DB 행 {n}개 삭제 · 폴더 삭제")
    except Exception as e:                                # noqa: BLE001
        print(f"   [정리] DB 삭제 실패: {type(e).__name__}: {e}")


def main() -> int:
    cleanup()
    ok = True

    #   ① 종류 없는 보고서 — 이름이 그대로여야 한다
    r = Report("수집검사", started=AT)
    r.add(Finding(OK, "시험용", "지워도 됩니다."))
    p = r.save(subdir=SUB)
    want = "1999-01-02_090908_수집검사.txt"
    print(f"① 종류 없는 보고서 파일 이름  {p.name}   (기대 {want})")
    if p.name != want:
        print("*** 실패: 종류가 없는데 이름이 바뀌었다")
        ok = False

    #   ② 옛 규칙 파일 흉내 — 이름엔 종류가 없고 `.json` 에만 있다.
    #      새 규칙으로 한 번 저장한 뒤, 그 파일을 옛 이름으로 복사해 둔다.
    r2 = Report("재학습검증", started=AT, kind="auc")
    r2.add(Finding(OK, "배추 — 시험용", "지워도 됩니다."))
    p2 = r2.save(subdir=SUB)
    old_txt = DIR / "1999-01-02_090908_재학습검증.txt"
    old_json = DIR / "1999-01-02_090908_재학습검증.json"
    shutil.copy(p2, old_txt)
    shutil.copy(p2.with_suffix(".json"), old_json)
    print("   옛 모양 파일의 kind:",
          json.loads(io.open(old_json, encoding="utf-8").read())["kind"])

    _one(old_txt)
    _one(old_txt)
    with db() as c, c.cursor() as cur:
        cur.execute("SELECT name, kind, source_file FROM agent_report"
                    " WHERE ran_at = %s ORDER BY id", (AT,))
        rows = cur.fetchall()
    print(f"② DB 행 {len(rows)}개 (수집검사 1 + 재학습검증 1 = 2 여야 한다)")
    for x in rows:
        print("   ", x)
    if len(rows) != 2:
        print("*** 실패: 옛 모양 파일을 다시 밀어넣었더니 두 벌이 됐다")
        ok = False

    cleanup()
    print("통과" if ok else "실패")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
