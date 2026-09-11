# -*- coding: utf-8 -*-
"""Claude 없이 flash-lite 가 일별 점검 보고서를 **직접** 쓰게 해 본다.

★ **주는 것은 아침 배치가 실제로 남긴 것뿐이다.** 09:05~09:23 사이에 규칙
  도구 여섯이 남긴 파일이다. 자동으로 돌 때 손에 쥘 수 있는 게 딱 이만큼이다.

★ **일부러 더 주지 않는다.** 제가 쓴 보고서에는 DB 를 직접 뒤져 찾은 것
  (50kg 거래 한 건)과 `run_batch.py` 변경분이 들어 있다. 그건 규칙 도구가
  안 남긴다. **이 실험은 그 차이가 얼마나 큰지 보려는 것**이다.
"""
from __future__ import annotations

import argparse
import glob
import io
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")     # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent.parent.parent


def _key() -> str:
    for ln in io.open(ROOT / ".env", encoding="utf-8", errors="ignore"):
        if ln.strip().startswith("GEMINI_API_KEY"):
            return ln.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit(".env 에 GEMINI_API_KEY 가 없습니다")


#   말투 규칙은 우리 CLAUDE.md 12절과 문구 대장에 적은 것을 그대로 옮겼다.
PROMPT = """당신은 농산물 가격 예측 시스템의 **일별 사후 점검 보고서**를 쓰는 사람입니다.

오늘 아침(2026-09-09) 자동 배치가 끝난 뒤, 규칙 기반 점검 도구 여섯 개가
아래 결과를 남겼습니다. 이것을 읽고 사람이 읽을 보고서를 한국어로 쓰세요.

## 읽는 사람
사내 **매입·재무 담당자**입니다. 농사 전문가도, 머신러닝 전문가도 아닙니다.
숫자를 보고 «오늘 얼마에 사야 하나» 를 정하는 사람들입니다.

## 말투 규칙 — 이게 제일 중요합니다
- 초등학생도 알아들을 수 있게 씁니다. 전문 용어를 쓰면 바로 옆에 풀이를 붙입니다
- 짧은 문장. 한 문장에 한 가지만
- 결론 먼저, 이유 나중
- 숫자를 그대로 보여줍니다. «크게 개선» 대신 «10번 중 6번 → 8번»
- **나쁜 소식을 순화하지 않습니다.** 쉽게 쓰는 것과 흐리는 것은 다릅니다
- **없는 값을 0 처럼 말하지 않습니다.** «아직 모른다» 와 «0이다» 는 다릅니다

## 반드시 지킬 것
- **자료에 없는 것을 지어내지 마세요.** 원인을 모르면 «모른다» 고 쓰세요
- 숫자·날짜·파일 이름은 자료에 있는 그대로 씁니다
- 판정(정상/주의/이상)은 도구가 낸 것을 그대로 씁니다. 당신이 다시 정하지 않습니다
- 맨 위에 «한 줄 결론» 을 둡니다
- 마크다운으로 씁니다. 수치는 코드칸에 줄 맞춰 넣으면 읽기 좋습니다

## 오늘 도구들이 남긴 것

{material}

## 이제 보고서를 쓰세요
제목은 «# 일별 배치 사후 점검 — 2026-09-09 (수)» 로 시작하세요.
보고서 본문만 출력하세요. 다른 말은 붙이지 마세요."""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gemini-3.5-flash-lite")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    #   아침 배치가 남긴 여섯. 그 뒤 시각의 파일은 오늘 손으로 다시 돌린 것이라 뺀다.
    wanted = ("090528_수집검사", "090810_재학습판정", "090819_뉴스요약",
              "092318_배치장애조사", "092322_데이터품질", "092323_드리프트감지")
    blocks = []
    for tag in wanted:
        hit = glob.glob(str(ROOT / "진행기록" / "agent_logs" / f"2026-09-09_{tag}.txt"))
        if not hit:
            print("없음:", tag)
            continue
        body = io.open(hit[0], encoding="utf-8").read().strip()
        blocks.append(f"### {Path(hit[0]).name}\n\n```\n{body}\n```")
        print(f"  담음 {Path(hit[0]).name}  {len(body):,}자")
    material = "\n\n".join(blocks)

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=_key())
    t0 = time.time()
    r = client.models.generate_content(
        model=a.model,
        contents=PROMPT.format(material=material),
        config=types.GenerateContentConfig(temperature=0.3),
    )
    sec = time.time() - t0
    u = r.usage_metadata
    text = (r.text or "").strip()
    Path(a.out).write_text(text, encoding="utf-8")
    print(f"\n모델 {a.model} · {sec:.1f}초")
    print(f"토큰   들어간 것 {u.prompt_token_count:,} · 나온 것 {u.candidates_token_count:,}")
    print(f"나온 글자 {len(text):,} -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
