# -*- coding: utf-8 -*-
"""AI 도우미 채점 (2026-08-31).

## 무엇을 하나

**정답을 아는 고장 문제**를 AI 에게 주고, 도구를 쥐어준 뒤 스스로 원인을
찾게 한다. 그리고 우리가 손으로 찾은 답과 대조해 점수를 낸다.

## 왜 먼저 채점하나

도우미 본체를 몇 시간 만들고 나서 "쓸 만한 모델이 아니네" 를 알게 되면
그 시간이 통째로 날아간다. **30분 만에 판가름내는 게 목적이다.**

## 문제

  문제 1 · 2026-08-31 예측 실패 (run 28)
      정답: train.py 가 수축 앵커를 `_anchor_mix` 라는 새 컬럼에 만들어
            feature 로 쓰는데, predict.py 는 그 이름의 컬럼을 만들지 않는다.
            학습과 추론이 어긋나 모델이 입력을 못 찾는다.
            8월 28일 변경에서 생겼다.

  문제 2 · 2026-08-27 경락가 수집 실패
      정답: 자연키를 5개에서 8개 컬럼으로 넓혔는데, 적재 쪽 중복 검사만
            옛 5개 키를 그대로 쓰고 있었다. 규격별로 여러 줄이 있는
            정상 데이터를 중복으로 오판했다.

**두 문제는 성격이 다르다.** 하나는 학습/추론 불일치, 하나는 스키마 변경
누락이다. 둘 다 맞히면 우연이 아니다.

## 채점

  원인 적중   정답에 있어야 할 낱말을 짚었나 (가장 중요)
  헛소리      존재하지 않는 파일·함수를 지어냈나 (하나라도 있으면 감점)
  도구 사용   몇 번 만에 찾았나
  시간

## 쓰는 법

    python agent/bench.py                       기본 모델로 두 문제
    python agent/bench.py --model gemini-3.5-flash
    python agent/bench.py --case 1              한 문제만
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mask import looks_leaky, mask                              # noqa: E402
from tools import SPEC, TOOLS                                   # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODEL = "gemini-3.7-flash"
MAX_TURNS = 12


def _key() -> str:
    v = os.environ.get("GEMINI_API_KEY")
    if v:
        return v
    for line in io.open(ROOT / ".env", encoding="utf-8", errors="ignore"):
        if line.strip().startswith("GEMINI_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("GEMINI_API_KEY 가 없습니다.")


SYSTEM = """너는 농산물 가격 예측 시스템의 장애를 조사하는 도우미다.

## 하는 일
주어진 도구로 **스스로 조사해서** 고장 원인을 찾는다.
한 번에 하나씩 도구를 부르고, 결과를 보고 다음에 무엇을 볼지 정한다.

## 반드시 지킬 것
1. **추측을 사실처럼 말하지 마라.** 확인한 것만 근거로 든다.
2. **파일 이름·함수 이름·줄 번호를 지어내지 마라.** 도구로 본 것만 쓴다.
3. 모르면 "확인하지 못했다" 고 쓴다.
4. 고치지 마라. 조사하고 설명만 한다.

## 조사 요령
· 오류 문구 원문을 먼저 본다 (batch_stages)
· 그 문구에 나온 이름을 코드에서 찾는다 (recent_changes → read_file)
· 최근 변경과 이어지는지 본다

## 끝낼 때
더 볼 게 없으면 도구를 부르지 말고 아래 형식으로 답한다.

원인: (한두 문장)
근거: (무엇을 보고 그렇게 판단했나. 파일과 줄 번호)
영향: (무엇이 안 되고 있나)
확인못함: (조사했지만 확인 못 한 것. 없으면 '없음')
"""

CASES = [
    {
        "id": 1,
        "질문": "2026-08-31 아침 배치가 실패했다. 왜 실패했는지 조사해줘.",
        "필수낱말": [["_anchor_mix"],
                     ["predict.py", "추론"],
                     ["train.py", "학습"]],
        "가점낱말": ["feature", "앵커", "08-28", "8/28", "8월 28"],
        "정답요약": "train.py 가 만든 _anchor_mix 컬럼을 predict.py 가 만들지 않아 "
                    "학습과 추론이 어긋남",
    },
    {
        "id": 2,
        "질문": "2026-08-27 에 경락가 수집(collect_auction)이 실패한 적이 있다. "
                "그 원인을 조사해줘.",
        "필수낱말": [["자연키", "natural", "중복"],
                     ["postgres.py", "적재", "staging"]],
        "가점낱말": ["규격", "키", "5", "8", "unit_weight"],
        "정답요약": "자연키를 8개 컬럼으로 넓혔는데 적재 쪽 중복 검사가 옛 5개 키를 "
                    "그대로 써서 정상 데이터를 중복으로 오판",
    },
]


def _decl():
    """도구 설명을 Gemini 형식으로."""
    out = []
    for s in SPEC:
        props = {k: {"type": "string", "description": v}
                 for k, v in s["params"].items()}
        out.append({"name": s["name"], "description": s["description"],
                    "parameters": {"type": "object", "properties": props}})
    return out


def run_case(client, model: str, case: dict, verbose: bool) -> dict:
    from google.genai import types
    tools = [types.Tool(function_declarations=_decl())]
    cfg = types.GenerateContentConfig(system_instruction=SYSTEM, tools=tools)
    contents = [types.Content(role="user",
                              parts=[types.Part(text=case["질문"])])]
    used, leaked = [], []
    t0 = time.time()
    answer = ""
    for turn in range(MAX_TURNS):
        #   503(혼잡)·429(한도)는 잠깐 기다리면 풀린다. 첫 채점에서 8번째
        #   호출에 503 이 나 시험이 통째로 날아갔다.
        r = None
        for attempt in range(4):
            try:
                r = client.models.generate_content(model=model, contents=contents,
                                                   config=cfg)
                break
            except Exception as e:                           # noqa: BLE001
                msg = str(e)
                if ("503" in msg or "429" in msg or "UNAVAILABLE" in msg) and attempt < 3:
                    wait = 8 * (attempt + 1)
                    if verbose:
                        print(f"    (혼잡 — {wait}초 뒤 재시도)")
                    time.sleep(wait)
                    continue
                raise
        if r is None:
            raise RuntimeError("재시도했으나 응답을 받지 못했습니다.")
        cand = r.candidates[0]
        calls = [p.function_call for p in (cand.content.parts or [])
                 if getattr(p, "function_call", None)]
        if not calls:
            answer = (r.text or "").strip()
            break
        contents.append(cand.content)
        replies = []
        for fc in calls:
            fn = TOOLS.get(fc.name)
            args = dict(fc.args or {})
            used.append(fc.name)
            if verbose:
                print(f"    [{turn+1}] {fc.name}({', '.join(f'{k}={v}' for k, v in args.items())})")
            if fn is None:
                res = f"그런 도구는 없습니다: {fc.name}"
            else:
                try:
                    # 숫자로 받아야 하는 인자를 맞춰준다
                    for k in ("limit", "run_id", "days", "start", "lines"):
                        if k in args:
                            try:
                                args[k] = int(args[k])
                            except (TypeError, ValueError):
                                pass
                    res = fn(**args)
                except Exception as e:                       # noqa: BLE001
                    res = f"도구 실행 실패: {type(e).__name__}: {e}"
            res = mask(str(res))
            hit = looks_leaky(res)
            if hit:
                leaked.append((fc.name, hit))
            replies.append(types.Part.from_function_response(
                name=fc.name, response={"result": res}))
        contents.append(types.Content(role="user", parts=replies))
    return {"answer": answer, "tools": used, "sec": time.time() - t0,
            "leaked": leaked}


def score(case: dict, answer: str) -> dict:
    """정답 낱말이 들어 있나 · 지어낸 이름이 있나."""
    low = answer.lower()
    got = []
    for group in case["필수낱말"]:
        got.append(any(w.lower() in low for w in group))
    bonus = sum(1 for w in case["가점낱말"] if w.lower() in low)

    # 지어낸 파일 이름 찾기 — 답에 나온 .py 가 실제로 있나
    import re
    named = set(re.findall(r"[\w/\\.-]+\.py", answer))
    fake = []
    for n in named:
        base = n.replace("\\", "/").split("/")[-1]
        if not list(ROOT.rglob(base)):
            fake.append(n)
    return {"필수": got, "필수합": sum(got), "필수총": len(got),
            "가점": bonus, "지어냄": fake}


def main() -> int:
    ap = argparse.ArgumentParser(description="AI 도우미 채점")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--case", type=int, default=None, help="1 또는 2")
    ap.add_argument("--verbose", action="store_true", help="도구 호출을 보여줌")
    a = ap.parse_args()

    from google import genai
    client = genai.Client(api_key=_key())

    cases = [c for c in CASES if a.case is None or c["id"] == a.case]
    print("=" * 72)
    print(f"AI 도우미 채점 · 모델 {a.model} · 문제 {len(cases)}개")
    print("=" * 72)

    results = []
    for c in cases:
        print(f"\n[문제 {c['id']}] {c['질문']}")
        print(f"  정답: {c['정답요약']}")
        try:
            r = run_case(client, a.model, c, a.verbose)
        except Exception as e:                               # noqa: BLE001
            print(f"  실행 실패: {type(e).__name__}: {str(e)[:150]}")
            results.append((c, None, None))
            continue
        s = score(c, r["answer"])
        results.append((c, r, s))
        print(f"\n  ── 답 ──")
        for line in r["answer"].splitlines():
            print(f"  {line}")
        print(f"\n  도구 {len(r['tools'])}번: {' → '.join(r['tools'])}")
        print(f"  시간 {r['sec']:.1f}초")
        print(f"  원인 적중 {s['필수합']}/{s['필수총']} · 가점 {s['가점']}")
        print(f"  지어낸 파일: {s['지어냄'] if s['지어냄'] else '없음'}")
        if r["leaked"]:
            print(f"  ⚠ 가림 후에도 위험 신호: {r['leaked']}")

    print("\n" + "=" * 72)
    print("종합")
    print("=" * 72)
    print(f"  {'문제':<6}{'원인적중':>10}{'지어냄':>8}{'도구':>6}{'시간':>8}")
    ok_all = True
    for c, r, s in results:
        if r is None:
            print(f"  {c['id']:<6}{'실행실패':>10}")
            ok_all = False
            continue
        hit = f"{s['필수합']}/{s['필수총']}"
        if s["필수합"] < s["필수총"] or s["지어냄"]:
            ok_all = False
        print(f"  {c['id']:<6}{hit:>10}{len(s['지어냄']):>8}"
              f"{len(r['tools']):>6}{r['sec']:>7.0f}초")
    print()
    print("  판정: " + ("합격 — 본체를 만들어도 됩니다"
                        if ok_all else
                        "불합격 — 모델을 바꾸거나 방식을 다시 봐야 합니다"))
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
