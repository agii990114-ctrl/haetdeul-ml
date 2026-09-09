# -*- coding: utf-8 -*-
"""재학습을 **사람 없이** 판정하고, 필요하면 후보까지 만들어 견줘 둔다.

## 왜 이걸 만들었나 (2026-09-09)

전에는 사람이 화면에 들어가 「판정하기」 → 「후보 만들기」 를 눌러야
비교표가 나왔습니다. 그런데 **후보를 만드는 것은 운영 모델을 한 글자도
안 건드립니다.** 물어볼 이유가 없었습니다.

    바뀐 뒤   배치가 끝나면 이 프로그램이 혼자 돕니다
                판정 -> (필요하면) 후보 만들기 -> 견주기
              후보가 나으면      화면에 「모델 재학습」 탭이 뜹니다
              후보가 못하면      후보를 지우고 아무것도 안 알립니다

    사람이 누르는 자리는 **「모델 업데이트」 하나**뿐입니다.

## 이 프로그램이 절대 안 하는 것

★ **운영 모델을 안 바꿉니다.** 바꾸는 것은 사람이 화면에서 누를 때만
  일어납니다. 여기서는 만들고 견주기까지입니다.

★ **못 통과한 후보를 남기지 않습니다.** 그래프의 `discard` 가 지웁니다.
  쓸 수 없다고 판정한 번들이 현행 옆에 남아 있으면 나중에 헷갈립니다.

★ **실패해도 배치 결과를 안 바꿉니다.** 이건 «알려주는 일» 이고,
  알리다가 죽어서 본 일을 망치면 본말전도입니다.

## 세 종류를 따로 돕니다

경락가·중도매가·소매가는 성격이 다릅니다 (중도매가는 열흘 중 엿새가
어제와 같아 앵커가 거의 완벽합니다). **하나가 실패해도 나머지는 돕니다.**
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")     # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass

from core import ROOT                                          # noqa: E402

KINDS = ("auc", "whsl", "rtl")
LABEL = {"auc": "경락가", "whsl": "중도매가", "rtl": "소매가"}
OUT = ROOT / "진행기록" / "agent_logs" / "_retrain_pending.json"


def run_one(kind: str, streak: int | None = None,
            gap_pp: float | None = None) -> dict:
    """한 종류를 돌린다. 결과를 한 줄로 요약해 돌려준다."""
    import retrain_graph as rg                                 # noqa: PLC0415
    from langgraph.checkpoint.sqlite import SqliteSaver        # noqa: PLC0415

    t0 = time.time()
    #   ★ 상태를 파일에 담습니다. 학습이 2분 반 걸리는데 그 사이 서버가
    #     다시 뜨면 메모리 판은 흔적도 안 남습니다.
    with SqliteSaver.from_conn_string(str(rg.CKPT)) as sv:
        graph = rg.make_graph(sv)
        #   ★ **이름표는 `rg.thread()` 가 정하는 것을 그대로 씁니다.**
        #     여기서 따로 짓지 않습니다 — 전에 `kind` 를 그냥 썼다가
        #     서버는 `retrain-auc` 를, 이쪽은 `auc` 를 열어 **같은 파일을
        #     보면서 서로 못 봤습니다.** 화면 버튼이 아무 일도 안 했습니다.
        cfg = rg.thread(kind)

        #   ★ 예전 상태 파일이 「후보를 만들까요」 에서 멈춰 있을 수 있다.
        #     그 물음은 이제 안 쓰므로 «만들자» 로 대신 답해 이어 준다.
        st = graph.get_state(cfg)
        ask = ""
        if st.tasks and getattr(st.tasks[0], "interrupts", None):
            ask = str(st.tasks[0].interrupts[0].value.get("ask", ""))

        if "후보" in ask:
            graph.invoke(rg.Command(resume="build"), cfg)
        elif "바꿀까요" in ask:
            #   이미 사람 답을 기다리는 중이면 건드리지 않는다.
            return {"kind": kind, "state": "waiting", "sec": 0.0}
        else:
            #   ★ 새로 시작한다. 지난 판정이 남아 있으면 지우고 시작한다 —
            #     어제 것을 오늘 결과로 착각하면 안 된다.
            seed: dict = {"kind": kind}
            if streak is not None:
                seed["streak"] = streak
            if gap_pp is not None:
                seed["gap_pp"] = gap_pp
            graph.invoke(seed, cfg)

        st = graph.get_state(cfg)
        v = dict(st.values or {})
        ask2 = ""
        if st.tasks and getattr(st.tasks[0], "interrupts", None):
            ask2 = str(st.tasks[0].interrupts[0].value.get("ask", ""))

    sec = time.time() - t0
    if "바꿀까요" in ask2:
        return {"kind": kind, "state": "pending", "sec": sec,
                "candidate": v.get("candidate", ""),
                "items": v.get("verify_items") or [],
                "verify": v.get("verify_text", "")}
    if v.get("discarded"):
        return {"kind": kind, "state": "discarded", "sec": sec,
                "candidate": v.get("discarded", ""), "note": v.get("note", "")}
    if not v.get("candidates"):
        return {"kind": kind, "state": "not_needed", "sec": sec,
                "verdict": v.get("verdict", "")}
    return {"kind": kind, "state": "stopped", "sec": sec,
            "note": v.get("note", "") or v.get("build_tail", "")[-200:]}


WORD = {
    "pending": "★ 후보가 낫습니다 — 사람이 «모델 업데이트» 를 눌러야 합니다",
    "discarded": "후보가 못해서 지웠습니다",
    "not_needed": "재학습이 필요하지 않습니다",
    "waiting": "이미 사람 답을 기다리는 중입니다",
    "stopped": "도중에 멈췄습니다",
    "error": "오류",
}


def main() -> int:
    ap = argparse.ArgumentParser(description="재학습 자동 판정·후보 생성")
    ap.add_argument("--kinds", nargs="*", default=list(KINDS))
    #   ★ 시험용. 평소에는 안 준다 — 안 주면 drift_agent 와 같은 규칙이다.
    #     낮춰도 «만들어 견주기» 까지만 간다. 바꾸는 것은 사람이 화면에서
    #     누를 때만 일어난다.
    ap.add_argument("--streak", type=int, default=None,
                    help="몇 주 연속 밀리면 후보로 볼까 (시험용 · 평소 3)")
    ap.add_argument("--gap-pp", type=float, default=None,
                    help="얼마나 밀려야 «졌다» 로 볼까 (시험용)")
    a = ap.parse_args()

    rows = []
    for kind in a.kinds:
        if kind not in KINDS:
            print(f"모르는 종류: {kind}")
            continue
        print(f"[{LABEL[kind]}] 도는 중 …", flush=True)
        try:
            r = run_one(kind, a.streak, a.gap_pp)
        except Exception as error:                             # noqa: BLE001
            #   ★ 하나가 죽어도 나머지는 돈다.
            r = {"kind": kind, "state": "error", "sec": 0.0,
                 "note": f"{type(error).__name__}: {error}"}
        rows.append(r)
        print(f"   {WORD.get(r['state'], r['state'])}  ({r['sec']:.0f}초)")
        if r.get("note"):
            print(f"   {r['note'][:200]}")

    #   ★ 화면이 읽는 파일. **기다리는 것이 없으면 빈 목록**을 쓴다.
    #     파일을 안 지우는 이유는, 없는 파일과 «오늘 확인했는데 없더라» 가
    #     다르기 때문이다.
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "pending": [r for r in rows if r["state"] == "pending"],
        "all": rows,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    n = sum(1 for r in rows if r["state"] == "pending")
    print(f"\n기다리는 결정 {n}개 -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
