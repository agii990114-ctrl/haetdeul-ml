#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""재학습 흐름을 LangGraph 상태 기계로 (2026-09-08)

    ─────────────────────────────────────────────────────────────────
    ★ 이건 **agent 틀이 아니라 상태 기계**입니다

        노드 하나도 LLM 을 안 부릅니다. 판정은 전부 규칙입니다.
        LangGraph 를 쓰는 이유는 셋뿐입니다 —

          ① 서버가 죽어도 작업이 남는다 (checkpoint)
          ② "여기서 사람을 기다린다" 를 구조로 적는다 (interrupt)
          ③ 팀 나머지가 쓰는 것과 같은 모양이 된다

        ⚠️ 발표에서 이걸 안 밝히면 **"AI 에게 판정을 맡겼다"** 로 읽힙니다.

    ★ 왜 만들었나 — 지금 것의 진짜 구멍 하나

        `backend/main.py` 의 `_JOB` 은 파이썬 메모리 dict 입니다.
        학습이 2분 반 걸리는데 **그 사이 서버가 재시작되면 작업이 통째로
        사라집니다.** 오늘 서버를 여러 번 다시 띄웠는데, 그때 학습 중이었다면
        흔적도 안 남았을 것입니다.

        SqliteSaver 로 갈면 그 자리가 없어집니다.

    ★ 지금 것을 안 지웠습니다

        `backend/main.py` 의 엔드포인트 다섯은 그대로 돕니다.
        이건 **나란히 두고 견주는 것**이고, 실패해도 잃는 게 없습니다.

    ─────────────────────────────────────────────────────────────────
    흐름

        judge ──(후보 없음)──────────────────> END
          │
        (후보 있음)
          │
          ▼
        build ──(실패)──> END      ← ★ 사람을 안 기다린다 (2026-09-09)
          │
          ▼
        verify
          │
     ┌────┴────┐
   통과       못 통과
     │           │
     ▼           ▼
  ask_apply   discard ──> END   ← ★ 후보를 **지운다**
     │
  interrupt ── 사람이 "적용하자" 라고 할 때까지 멈춤
     │
     ▼
   apply ──> END

    ★ **사람은 한 번만 누릅니다** (2026-09-09 바꿈).

      전에는 「후보를 만들까요」 도 물었습니다. 그런데 후보를 만드는 것은
      운영 모델을 한 글자도 안 건드립니다 — 물어볼 이유가 없었습니다.
      이제 판정이 「필요하다」 면 **바로 만들고 견줍니다.**

      사람이 누르는 자리는 **「바꿀까요」 하나**뿐이고, 그것도 **후보가
      현행보다 나을 때만** 나옵니다.

    ★ **못 통과한 후보는 지웁니다.** 안 지우면 파일이 쌓이고, 무엇보다
      쓸 수 없다고 판정한 것이 폴더에 남아 있으면 나중에 헷갈립니다.

    쓰는 법
        python agent/retrain_graph.py                 # 판정까지 (사람 대기)
        python agent/retrain_graph.py --resume build  # "만들자"
        python agent/retrain_graph.py --resume apply  # "적용하자"
        python agent/retrain_graph.py --resume stop   # 그만둔다
        python agent/retrain_graph.py --show          # 지금 어디 서 있나
        python agent/retrain_graph.py --draw          # 그래프 모양
"""
from __future__ import annotations

import argparse
import datetime
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Annotated, Literal, TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parent))

#   ★ 자기 출력을 UTF-8 로 고정한다 (윈도우 cp949).
#     화면에서 부르면 PYTHONIOENCODING 이 안 넘어온다 — 09-07 에 이걸로 죽었다.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")   # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass

from langgraph.graph import END, START, StateGraph          # noqa: E402
from langgraph.checkpoint.sqlite import SqliteSaver         # noqa: E402
from langgraph.types import Command, interrupt              # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "agent"
KIT = ROOT / "ML" / "20260824" / "ml_train_kit_2"

#: 작업 상태가 여기 남는다. **서버가 죽어도 이 파일은 남는다** — 그것이
#: 이 파일을 만든 첫 번째 이유다.
CKPT = ROOT / "진행기록" / "agent_logs" / "_retrain_graph.sqlite"
RESULT_JSON = ROOT / "진행기록" / "agent_logs" / "_retrain_last.json"

BUNDLE = {"auc": "ops_auc", "whsl": "ops_whsl", "rtl": "ops_rtl"}


class S(TypedDict, total=False):
    """그래프가 들고 다니는 것. **판정 결과만 담고 원본은 파일에 둔다.**"""
    kind: str
    #   judge
    verdict: str                 # 정상 / 주의 / 이상
    candidates: list             # [(kind, item), …]
    judge_text: str
    #   build
    candidate: str               # 후보 번들 이름
    build_ok: bool
    build_tail: str
    #   verify
    passed: bool
    verify_text: str
    #   ★ 품목별 수치. **글과 따로 둡니다** — 사람이 «바꿀까요» 에
    #     답하려면 문장이 아니라 숫자를 나란히 봐야 합니다.
    #     화면이 표로 그립니다.
    verify_items: list
    #   apply
    applied: str
    backup: str
    #   공통
    stopped_at: str
    note: str


# ───────────────────────────────────────────────────────── 노드
def _run(cmd: list[str], timeout: int = 3600) -> tuple[bool, str]:
    """하위 프로세스. **UTF-8 을 물려준다** — 윈도우 기본이 cp949 라서."""
    import os
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    try:
        r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                           encoding="utf-8", errors="replace",
                           timeout=timeout, env=env)
        return r.returncode == 0, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return False, f"시간 초과 ({timeout}초)"
    except Exception as e:                                   # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"


def judge(state: S) -> S:
    """다시 배워야 하나. DB 만 훑어 몇 초면 끝난다."""
    import retrain_agent as ra                               # noqa: PLC0415
    from core import Report                                  # noqa: PLC0415

    kind = state.get("kind", "auc")
    rep = Report("재학습판정")
    ra.check_stale(rep, [kind])
    hits = ra.check_drift(rep, [kind], ra.MIN_ROWS, ra.GAP_PP, ra.STREAK)
    ra.verdict(rep, hits, [kind])
    rep.save()                                               # 화면이 읽는다

    return {"verdict": rep.worst,
            "candidates": [(k, i) for k, i, _ in hits],
            "judge_text": rep.text()}


def ask_build(state: S) -> Command[Literal["build", "__end__"]]:
    """★ 사람 대기 하나 — "후보를 만들까요".

    `interrupt` 는 여기서 그래프를 **멈추고 상태를 저장**한다.
    다음에 `Command(resume=...)` 으로 이어받으면 이 자리부터 다시 돈다.
    """
    ans = interrupt({
        "ask": "후보를 만들까요",
        "verdict": state.get("verdict"),
        "candidates": state.get("candidates", []),
        "hint": "build 로 답하면 만들고, 그 밖이면 그만둡니다. 몇 분 걸립니다.",
    })
    if str(ans).strip().lower() != "build":
        return Command(goto=END, update={"stopped_at": "ask_build",
                                         "note": f"사람이 그만두었습니다 ({ans})"})
    return Command(goto="build")


def build(state: S) -> S:
    """후보를 만들고 **바로 검증까지** 한다 (retrain_build 가 둘을 같이 한다).

    ★ 현행과 똑같은 조리법으로, 학습 끝 날짜만 견주는 창 앞으로 당긴다.
    """
    kind = state.get("kind", "auc")
    ok, tail = _run([sys.executable, str(AGENT / "retrain_build.py"),
                     "--kind", kind, "--save", "--json", str(RESULT_JSON)])
    cand = ""
    if RESULT_JSON.exists():
        try:
            cand = json.loads(RESULT_JSON.read_text(encoding="utf-8")).get("candidate", "")
        except (OSError, ValueError):
            pass
    return {"build_ok": ok, "build_tail": tail[-3000:], "candidate": cand}


def _items_from_findings(res: dict) -> list:
    """옛 결과 파일에서 표를 되살린다.

    ★ `items` 는 2026-09-09 에 생겼습니다. 그 전 파일에는 수치가 **글 안에만**
      있습니다(`findings[].numbers`). 그걸 버리면 지난 판정을 표로 못 봅니다.

    ★ **새 파일에는 이 길을 안 씁니다.** 글을 파싱해 숫자를 뽑는 것은
      문장을 고칠 때마다 깨지는 방식이라, 되살리기 용도로만 둡니다.
    """
    def num(v: str) -> float | None:
        try:
            return float(str(v).replace("%", "").replace("+", "").strip())
        except ValueError:
            return None

    rows = []
    for f in res.get("findings", []):
        title = str(f.get("title", ""))
        if "—" not in title:
            continue
        item = title.split("—")[0].strip()
        got = {k: v for k, v in (f.get("numbers") or [])}
        if "현행 WMAPE" not in got and "필요" not in got:
            continue          # 「견주는 창」 같은 머리말 줄
        n = str(got.get("행수", "0")).replace(",", "").replace("행", "")
        verdict = ("후보가 낫다" if "낫습니다" in title
                   else "후보가 나쁘다" if "나쁩니다" in title
                   else "표본 부족" if "표본" in title
                   else "판정 불가")
        rows.append({
            "item": item, "n": int(num(n) or 0), "verdict": verdict,
            "anchor": num(got.get("앵커 WMAPE")),
            "cur": num(got.get("현행 WMAPE")),
            "cand": num(got.get("후보 WMAPE")),
            "diff": num(got.get("차이 (현행−후보)")),
            "need": num(got.get("시드 편차×2")),
        })
    return rows


def verify(state: S) -> S:
    """검증 결과를 읽는다. **판정은 retrain_build 가 이미 했다.**

    ★ 같은 판정을 두 곳에서 하지 않는다. 여기서 다시 계산하면 두 답이
      갈릴 수 있고, 그때 어느 쪽이 맞는지 알 방법이 없다.
    """
    if not state.get("build_ok"):
        return {"passed": False, "verify_items": [], "verify_text": "후보를 못 만들었습니다."}
    if not RESULT_JSON.exists():
        return {"passed": False, "verify_items": [], "verify_text": "검증 결과 파일이 없습니다."}
    try:
        res = json.loads(RESULT_JSON.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return {"passed": False, "verify_items": [], "verify_text": f"검증 결과를 못 읽었습니다: {e}"}

    lines = [f"[{f['level']}] {f['title']}" for f in res.get("findings", [])]
    return {"passed": bool(res.get("passed")),
            "candidate": res.get("candidate", state.get("candidate", "")),
            #   ★ 숫자를 그대로 넘긴다. 여기서 다시 계산하지 않는다 —
            #     판정은 retrain_build 가 이미 했고, 두 곳에서 재면 갈린다.
            "verify_items": res.get("items") or _items_from_findings(res),
            "verify_text": f"판정 {res.get('verdict')}\n" + "\n".join(lines)}


def after_verify(state: S) -> Literal["ask_apply", "discard"]:
    """★ 통과 못 하면 **사람에게 묻지도 않고 지운다.**

    화면에 버튼을 띄워 두고 서버에서 막는 것보다, 물음 자체를 안 내는 편이
    낫다. 실수로 누를 자리가 없어진다.
    """
    return "ask_apply" if state.get("passed") else "discard"


def discard(state: S) -> S:
    """못 쓴다고 판정한 후보를 지운다.

    ★ **왜 지우나.** 안 지우면 매일 하나씩 쌓인다. 그리고 쓸 수 없다고
      판정한 번들이 현행 옆에 남아 있으면, 나중에 사람이 폴더를 보고
      «이건 뭐지» 하게 된다. 판정 결과는 보고서에 남으니 번들은 필요 없다.

    ★ **현행과 백업은 절대 안 건드린다.** 이름이 `ops_{kind}_cand_…` 인
      것만 지운다. 혹시 이름이 어긋나면 **아무것도 안 지우고** 그 사실을
      적는다 — 지우는 일에서는 «아마 맞겠지» 가 제일 위험하다.
    """
    name = str(state.get("candidate", "")).strip()
    kind = state.get("kind", "auc")
    if not name:
        return {"note": "지울 후보 이름이 없습니다."}
    safe = name.startswith(f"ops_{kind}_") and "_cand" in name
    if not safe:
        return {"note": f"후보 이름이 규칙과 달라 안 지웠습니다: {name}"}
    path = KIT / name
    if not path.is_dir():
        return {"note": f"후보 폴더가 이미 없습니다: {name}"}
    try:
        shutil.rmtree(path)
    except OSError as e:
        return {"note": f"후보를 못 지웠습니다: {name} ({e})"}
    return {"discarded": name, "note": f"후보가 현행보다 못해 지웠습니다: {name}"}


def ask_apply(state: S) -> Command[Literal["apply", "__end__"]]:
    """★ 사람 대기 둘 — "바꿀까요"."""
    ans = interrupt({
        "ask": "운영 모델을 후보로 바꿀까요",
        "candidate": state.get("candidate"),
        "verify": state.get("verify_text"),
        #   ★ 물음 **옆에** 숫자를 같이 싣습니다. 사람이 «바꿀까요» 에
        #     답하려면 현행과 후보를 나란히 봐야 합니다. 글만 주면
        #     «낫습니다» 를 믿고 누르는 것 말고 할 수 있는 게 없습니다.
        "items": state.get("verify_items") or [],
        "hint": "apply 로 답하면 바꿉니다. 지금 것은 통째로 백업되고 되돌릴 수 있습니다. "
                "모델 이름은 안 바뀝니다 — 매입 파트가 이름으로 찾습니다.",
    })
    if str(ans).strip().lower() != "apply":
        return Command(goto=END, update={"stopped_at": "ask_apply",
                                         "note": f"사람이 안 바꾸기로 했습니다 ({ans})"})
    return Command(goto="apply")


def apply(state: S) -> S:
    """교체. 지금 것을 통째로 백업하고 이름은 그대로 둔다."""
    import retrain_build as rb                               # noqa: PLC0415
    kind = state.get("kind", "auc")
    cur = KIT / BUNDLE[kind]
    cand = KIT / str(state.get("candidate", ""))
    if not cand.exists():
        return {"note": f"후보 번들이 없습니다: {cand.name}"}
    rb.apply(kind, cur, cand)
    baks = sorted((p.name for p in KIT.glob(f"ops_{kind}_교체전_*")), reverse=True)
    return {"applied": cand.name, "backup": baks[0] if baks else ""}


def after_judge(state: S) -> Literal["build", "__end__"]:
    """★ 사람을 안 기다리고 바로 만든다 (2026-09-09).

    후보를 만드는 것은 **운영 모델을 안 건드린다.** 물어볼 이유가 없었다.
    사람이 답할 자리는 「바꿀까요」 하나로 줄였다.
    """
    return "build" if state.get("candidates") else END


# ───────────────────────────────────────────────────────── 그래프
def make_graph(saver):
    g = StateGraph(S)
    g.add_node("judge", judge)
    #   ★ `ask_build` 는 이제 안 거칩니다. 그래도 **노드는 남겨 둡니다** —
    #     예전 상태 파일이 이 자리에서 멈춰 있을 수 있고, 노드가 없어지면
    #     그 파일을 못 이어받습니다. 새 흐름은 여기로 안 옵니다.
    g.add_node("ask_build", ask_build)
    g.add_node("build", build)
    g.add_node("discard", discard)
    g.add_node("verify", verify)
    g.add_node("ask_apply", ask_apply)
    g.add_node("apply", apply)

    g.add_edge(START, "judge")
    g.add_conditional_edges("judge", after_judge, ["build", END])
    #   ask_build · ask_apply 는 Command 로 스스로 다음을 정한다
    g.add_edge("build", "verify")
    g.add_conditional_edges("verify", after_verify, ["ask_apply", "discard"])
    g.add_edge("discard", END)
    g.add_edge("apply", END)
    return g.compile(checkpointer=saver)


def thread(kind: str) -> dict:
    """작업 하나를 가리키는 이름. 품목별로 따로 돈다."""
    return {"configurable": {"thread_id": f"retrain-{kind}"}}


def show_interrupt(res: dict) -> bool:
    """멈춰 서 있으면 무엇을 묻는지 찍는다. 돌려주는 값 = 멈춰 있나."""
    ints = res.get("__interrupt__") or []
    if not ints:
        return False
    v = ints[0].value if hasattr(ints[0], "value") else ints[0]
    print("\n" + "=" * 62)
    print("  ★ 사람을 기다립니다 —", v.get("ask"))
    for k in ("verdict", "candidates", "candidate"):
        if v.get(k):
            print(f"     {k}: {v[k]}")
    if v.get("verify"):
        print("     검증:")
        for ln in str(v["verify"]).splitlines():
            print("       ", ln)
    print("  " + v.get("hint", ""))
    print("=" * 62)
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", default="auc", choices=["auc", "whsl", "rtl"])
    ap.add_argument("--resume", help="build · apply · stop")
    ap.add_argument("--show", action="store_true", help="지금 어디 서 있나")
    ap.add_argument("--draw", action="store_true", help="그래프 모양")
    a = ap.parse_args()

    CKPT.parent.mkdir(parents=True, exist_ok=True)
    with SqliteSaver.from_conn_string(str(CKPT)) as saver:
        app = make_graph(saver)
        cfg = thread(a.kind)

        if a.draw:
            print(app.get_graph().draw_ascii())
            return 0

        if a.show:
            st = app.get_state(cfg)
            print("다음에 돌 것:", st.next or "(없음 — 끝났거나 시작 전)")
            if st.values:
                for k, v in st.values.items():
                    if k.endswith("_text") or k == "build_tail":
                        continue
                    print(f"  {k}: {v}")
            if st.tasks and any(t.interrupts for t in st.tasks):
                print("  ★ 사람 대기 중입니다. --resume 로 이어받으세요.")
            return 0

        if a.resume:
            res = app.invoke(Command(resume=a.resume), cfg)
        else:
            res = app.invoke({"kind": a.kind}, cfg)

        if not show_interrupt(res):
            print("\n[끝]")
            for k in ("verdict", "candidate", "passed", "applied", "backup",
                      "stopped_at", "note"):
                if res.get(k) not in (None, ""):
                    print(f"  {k}: {res[k]}")
            if res.get("verify_text"):
                print("  검증:")
                for ln in res["verify_text"].splitlines():
                    print("   ", ln)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
