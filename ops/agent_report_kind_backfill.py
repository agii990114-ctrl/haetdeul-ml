# -*- coding: utf-8 -*-
"""지나간 재학습 보고서에 **가격 종류(kind)** 를 한 번 밀어 넣는다. (2026-09-16)

## 왜 필요한가

오늘부터 `Report(kind=...)` 로 종류가 붙는다. 그런데 **오늘 것과 과거 것은
비어 있다.** 그래서 채팅이 «재학습검증 · (가격 종류 미상)» 으로 보여 준다.
하루에 종류마다 한 건씩 나오는데, 이름이 셋 다 «재학습검증» 이라 구별이
안 된다.

## 무엇을 근거로 종류를 가리나 — 두 가지가 다르다

### ① 재학습판정 — **보고서 자신이 이름을 말한다**

`retrain_agent.check_stale()` · `check_drift()` 가 제목을 이렇게 쓴다.

    "auc — 학습이 990일 전에서 멈춰 있습니다"
    "auc 무 — 1주 연속 앵커에 밀렸습니다 · 재학습 후보"

**제목 맨 앞이 곧 종류다.** 되짚을 것도, 로그를 볼 것도 없다. 한 보고서
안의 제목들이 **전부 같은 종류**일 때만 받아들인다. 하나라도 엇갈리면
그 파일은 건너뛴다.

### ② 재학습검증 — **보고서에 종류가 없다. 배치 로그의 순서로 가린다**

`retrain_build.judge()` 의 제목은 품목 이름이다 ("배추 — 후보가 나쁩니다").
종류가 한 글자도 안 적힌다. 그래서 배치 로그를 본다.

    run_batch.py:660  ->  agent/retrain_auto.py   (--kinds 안 줌)
    retrain_auto.py:52   KINDS = ("auc", "whsl", "rtl")      <- 이 순서
    retrain_auto.py:175  print(f"[{LABEL[kind]}] 도는 중 …")  <- 종류마다 한 줄
    retrain_auto.py:183  print(f"   {WORD[state]}  ({sec:.0f}초)")

`retrain_graph.build()`(:203) 가 `retrain_build.py --kind <종류> --save` 를
**하위 프로세스로** 부른다. 그 안에서 `Report("재학습검증").save()` 가
불린다. 그러니 —

    **재학습검증 파일은 «후보를 실제로 만든 종류» 마다 딱 하나 생긴다.**

후보 만들기는 학습이라 **수십 초** 걸린다. 로그의 `(N초)` 가 그 증거다.

    (55초) (57초) (58초) (60초) (63초) (67초)   후보를 만들었다  -> 검증 있음
    (0초)                                      아무것도 안 했다 -> 검증 없음

`0초` 는 셋 중 하나다 — 판정만 하고 끝났거나(`재학습이 필요하지 않습니다`),
이미 사람 답을 기다리는 중이라 **그래프를 아예 안 돌렸거나**
(`retrain_auto.run_one():102` 의 `route == "keep"` · `"sec": 0.0` 을 그대로
박아 돌려준다), 옛 물음에 걸려 도중에 멈췄거나. **셋 다 학습을 안 한다.**

그래서 규칙은 이렇다.

    그날 로그에서 (N초) 가 **0 보다 큰** 종류를 순서대로 뽑는다
      == 그날 재학습검증 파일을 시각 순으로 세운 것
    개수가 같을 때만 짝짓는다. 다르면 **그날은 통째로 건너뛴다.**

## ★ 안 하는 것

★ **학습 끝 날짜로 되짚지 않는다.** 세 번들의 `train_end` 가 같은 날이
  많아 우연히 맞을 뿐이다. 근거가 아니다.

★ **개수가 안 맞으면 채우지 않는다.** 화면에서 손으로 돌린 재학습
  (`backend/main.py` 의 `/retrain/build` · `/retrain/graph/act`)은 배치
  로그에 안 남는다. 그런 날은 짝이 안 맞고, 그러면 건너뛴다.
  **틀린 이름표는 없는 이름표보다 나쁘다.**

★ **`payload` 가 없는(NULL) 행은 손대지 않는다.** `.json` 을 같이 남기기
  시작한 것이 2026-09-10 이라 그 전 보고서는 글만 있다. 없는 구조를
  지어내지 않는다.

★ **파일이 원본이다.** `.json` 의 다른 칸은 한 글자도 안 바꾼다.

## 두 번 돌려도 같다

`.json` 은 이미 `kind` 가 있으면 건드리지 않는다. DB 는
`payload->>'kind'` 가 비어 있는 행만 고친다.

## 쓰는 법

    python ops/agent_report_kind_backfill.py            # 계획만 본다
    python ops/agent_report_kind_backfill.py --commit   # 실제로 쓴다
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
sys.path.insert(0, str(ROOT / "agent"))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")   # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass

LOGS = ROOT / "진행기록" / "agent_logs"
BATCH_LOGS = ROOT / "진행기록" / "batch_logs"
OPS_LOGS = ROOT / "ops" / "logs"

KINDS = ("auc", "whsl", "rtl")
#: `retrain_auto.py:53` 의 LABEL 을 거꾸로 뒤집은 것. 로그에 한글이 찍힌다.
LABEL_TO_KIND = {"경락가": "auc", "중도매가": "whsl", "소매가": "rtl"}

#: 보고서 파일 이름 — `2026-09-16_090905_재학습검증.txt`
FNAME = re.compile(r"^(\d{4}-\d{2}-\d{2})_(\d{6})_(재학습판정|재학습검증)$")
#: 제목 맨 앞의 종류 — "auc 무 — 1주 연속 …"
TITLE_KIND = re.compile(r"^(auc|whsl|rtl)\b")
#: 로그의 «[경락가] 도는 중 …»
LOG_KIND = re.compile(r"^\[(경락가|중도매가|소매가)\]\s*도는 중")
#: 로그의 «   후보가 못해서 지웠습니다  (57초)»
LOG_SEC = re.compile(r"\((\d+)초\)")


# ─────────────────────────────────────────────────────────────────────
#   ① 재학습판정 — 보고서 자신이 말하는 종류
# ─────────────────────────────────────────────────────────────────────
def kind_from_report(txt_path: Path) -> tuple[str | None, str]:
    """보고서에서 종류를 읽는다. (종류, 근거) 를 돌려준다.

    ★ 제목이 **전부 같은 종류** 일 때만 받는다. 하나라도 엇갈리면 None.
      «아마 이거겠지» 는 안 한다.
    """
    titles: list[str] = []
    side = txt_path.with_suffix(".json")
    if side.exists():
        try:
            d = json.loads(io.open(side, encoding="utf-8").read())
            titles = [str(f.get("title", "")) for f in d.get("findings", [])]
            src = side.name
        except Exception:                                    # noqa: BLE001
            titles = []
    if not titles:
        #   `.json` 이 없던 시절 파일. 글에서 제목 줄만 뽑는다.
        src = txt_path.name
        for line in io.open(txt_path, encoding="utf-8", errors="replace"):
            m = re.match(r"^(?:OK |\*\*\* |▲  )(.+)$", line.rstrip())
            if m:
                titles.append(m.group(1))

    got = {m.group(1) for m in (TITLE_KIND.match(t) for t in titles) if m}
    if len(got) == 1:
        k = got.pop()
        return k, f"{src} 의 제목 {len(titles)}개가 전부 «{k} …» 로 시작"
    if not got:
        return None, f"{src} 의 제목에 종류가 안 적혀 있음 (제목 {len(titles)}개)"
    return None, f"{src} 의 제목에 종류가 섞여 있음 ({sorted(got)})"


# ─────────────────────────────────────────────────────────────────────
#   ② 재학습검증 — 배치 로그의 실행 순서
# ─────────────────────────────────────────────────────────────────────
def built_kinds(day: str) -> tuple[list[tuple[str, str]], str]:
    """그날 «후보를 실제로 만든» 종류를 순서대로. (목록, 로그출처) 를 돌려준다.

    목록의 한 칸은 (종류, 근거가 된 로그 줄) 이다.
    로그가 없으면 빈 목록과 빈 출처를 돌려준다 — 부르는 쪽이 건너뛴다.
    """
    main = BATCH_LOGS / f"batch_{day}.log"
    cands = [main] if main.exists() else []
    if not cands:
        cands = sorted(OPS_LOGS.glob(f"batch_{day.replace('-', '')}_*.log"))
    if not cands:
        return [], ""

    out: list[tuple[str, str]] = []
    for p in cands:
        lines = io.open(p, encoding="utf-8", errors="replace").read().splitlines()
        pending: str | None = None
        for i, line in enumerate(lines):
            m = LOG_KIND.match(line.strip())
            if m:
                pending = LABEL_TO_KIND[m.group(1)]
                continue
            if pending is None:
                continue
            s = LOG_SEC.search(line)
            if not s:
                continue
            #   ★ 0초는 학습을 안 했다는 뜻이다 (머리말 참조). 검증이 없다.
            if int(s.group(1)) > 0:
                out.append((pending, f"{p.name}:{i + 1} «{line.strip()}»"))
            pending = None
    return out, ", ".join(p.name for p in cands)


# ─────────────────────────────────────────────────────────────────────
def plan() -> tuple[list[dict], list[tuple[str, str]]]:
    """(채울 것, 건너뛴 것) 을 돌려준다. **아무것도 안 쓴다.**"""
    days: dict[str, dict[str, list[Path]]] = {}
    for p in sorted(LOGS.glob("*.txt")):
        m = FNAME.match(p.stem)
        if not m:
            continue
        day, hms, name = m.groups()
        days.setdefault(day, {"재학습판정": [], "재학습검증": []})[name].append(p)

    fill: list[dict] = []
    skip: list[tuple[str, str]] = []

    for day in sorted(days):
        #   ── 판정: 보고서가 스스로 말한다 ──────────────────────
        for p in sorted(days[day]["재학습판정"]):
            k, why = kind_from_report(p)
            if k:
                fill.append({"path": p, "day": day, "name": "재학습판정",
                             "kind": k, "why": why})
            else:
                skip.append((p.name, why))

        #   ── 검증: 배치 로그의 순서 ──────────────────────────
        vs = sorted(days[day]["재학습검증"])
        if not vs:
            continue
        built, src = built_kinds(day)
        if not src:
            skip.append((f"{day} 재학습검증 {len(vs)}건",
                         "그날 배치 로그가 없음 — 짝지을 근거가 없다"))
            continue
        if len(built) != len(vs):
            skip.append((
                f"{day} 재학습검증 {len(vs)}건",
                f"로그({src})가 말하는 «후보를 만든» 종류는 {len(built)}개"
                f"{[b[0] for b in built]} 인데 파일은 {len(vs)}개 — 개수가 안 맞아 건너뜀"
                " (화면에서 손으로 돌린 재학습은 배치 로그에 안 남는다)"))
            continue
        for p, (k, why) in zip(vs, built):
            fill.append({"path": p, "day": day, "name": "재학습검증",
                         "kind": k, "why": why})
    return fill, skip


# ─────────────────────────────────────────────────────────────────────
def write_json(row: dict) -> str:
    """`.json` payload 에 kind 를 넣는다. **다른 칸은 안 건드린다.**"""
    side = row["path"].with_suffix(".json")
    if not side.exists():
        return "json 없음"
    try:
        d = json.loads(io.open(side, encoding="utf-8").read())
    except Exception as e:                                   # noqa: BLE001
        return f"★ json 을 못 읽음: {type(e).__name__}"
    if d.get("kind"):
        return "이미 있음"
    #   ★ 자리를 «verdict 다음» 으로 맞춘다 — `core.Report.save()` 가
    #     새로 쓰는 것과 같은 차례여야 나중에 사람이 두 파일을 나란히
    #     놓고 봤을 때 같아 보인다.
    out: dict = {}
    for k, v in d.items():
        out[k] = v
        if k == "verdict":
            out["kind"] = row["kind"]
    if "kind" not in out:
        out["kind"] = row["kind"]
    io.open(side, "w", encoding="utf-8").write(
        json.dumps(out, ensure_ascii=False, indent=1))
    return "넣음"


def write_db(rows: list[dict]) -> dict:
    """DB `agent_report.payload` 에 같은 값을 넣는다.

    ★ `payload` 가 NULL 인 행은 안 건드린다 — 없는 구조를 지어내지 않는다.
    ★ `kind` 가 이미 있는 행도 안 건드린다.
    """
    tally = {"고침": 0, "이미 있음": 0, "payload 없음": 0, "행 없음": 0}
    from core import db                                      # noqa: PLC0415
    with db() as c:
        with c.cursor() as cur:
            for r in rows:
                m = FNAME.match(r["path"].stem)
                ran_at = datetime.datetime.strptime(
                    f"{m.group(1)}_{m.group(2)}", "%Y-%m-%d_%H%M%S")
                cur.execute(
                    "SELECT payload IS NULL, payload->>'kind'"
                    "  FROM agent_report WHERE name = %s AND ran_at = %s",
                    (r["name"], ran_at))
                hit = cur.fetchone()
                if not hit:
                    tally["행 없음"] += 1
                    continue
                if hit[0]:
                    tally["payload 없음"] += 1
                    continue
                if hit[1]:
                    tally["이미 있음"] += 1
                    continue
                cur.execute(
                    "UPDATE agent_report"
                    "   SET payload = jsonb_set(payload, '{kind}', to_jsonb(%s::text))"
                    #   ★ `payload->'kind'` 가 아니라 `->>` 로 본다.
                    #     `{"kind": null}` 이면 `->` 는 «JSON 널» 이라
                    #     SQL 의 IS NULL 에 안 걸린다. `->>` 는 걸린다.
                    #     위 검사(hit[1])와 같은 잣대를 써야 한다 —
                    #     둘이 다르면 «고칠 것» 으로 세고 0건을 고친다.
                    " WHERE name = %s AND ran_at = %s"
                    "   AND payload ->> 'kind' IS NULL",
                    (r["kind"], r["name"], ran_at))
                tally["고침"] += cur.rowcount
        c.commit()
    return tally


def main() -> int:
    ap = argparse.ArgumentParser(description="지나간 재학습 보고서에 가격 종류를 채운다")
    ap.add_argument("--commit", action="store_true", help="실제로 쓴다")
    a = ap.parse_args()

    fill, skip = plan()

    print("=" * 78)
    print("[대응표]  보고서 파일 -> 종류 · 근거")
    print("=" * 78)
    day = ""
    for r in fill:
        if r["day"] != day:
            day = r["day"]
            print(f"\n── {day} ──")
        print(f"  {r['path'].name:<40} {r['kind']:<5} {r['why']}")

    print("\n" + "=" * 78)
    print(f"[건너뛴 것] {len(skip)}건")
    print("=" * 78)
    for what, why in skip:
        print(f"  {what}")
        print(f"      {why}")

    print(f"\n대응된 보고서 {len(fill)}건 · 건너뛴 것 {len(skip)}건")
    if not a.commit:
        print("--commit 이 없어 아무것도 안 썼습니다.")
        return 0

    print("\n[파일]")
    ftally: dict = {}
    for r in fill:
        got = write_json(r)
        ftally[got] = ftally.get(got, 0) + 1
    for k, v in sorted(ftally.items()):
        print(f"  {k:<12} {v}건")

    print("\n[DB agent_report.payload]")
    for k, v in write_db(fill).items():
        print(f"  {k:<12} {v}건")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
