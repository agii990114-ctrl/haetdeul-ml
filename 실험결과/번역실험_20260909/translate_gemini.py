# -*- coding: utf-8 -*-
"""영어 보고서를 Gemini 로 한국어로 옮긴다 — ollama 실험과 나란히 견주려고.

★ **지시와 조각 나누기를 ollama 쪽과 똑같이 맞춘다.** 안 그러면 모델 차이가
  아니라 지시 차이를 재게 된다.

★ **토큰을 센다.** 매일 도는 자리에 붙일지 정하려면 값이 얼마나 드는지
  알아야 한다. 부르기 전에 세고, 부른 뒤 실제 사용량도 받아 적는다.
"""
from __future__ import annotations

import argparse
import io
import os
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
    """.env 에서만 읽는다. 코드에 절대 안 적는다."""
    env = ROOT / ".env"
    for ln in io.open(env, encoding="utf-8", errors="ignore"):
        if ln.strip().startswith("GEMINI_API_KEY"):
            return ln.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit(".env 에 GEMINI_API_KEY 가 없습니다")


#   ollama 쪽 translate.py 와 **글자 하나까지 같은 지시**를 쓴다.
PROMPT = """You are translating an internal report for a Korean agricultural
trading company. Translate the English below into natural Korean.

Rules:
- The readers are buyers and finance staff. They are not ML engineers.
  Write plain Korean that a middle-school student could follow.
- Short sentences. Conclusion first.
- Do NOT soften bad news. This report deliberately states how wrong our
  forecasts are. Keep that bluntness.
- Keep every number, date, percentage and file name EXACTLY as written.
- Keep markdown structure: headings, code blocks, tables, bullets, bold.
- Inside ``` code blocks, translate only the Korean-facing words; never change
  numbers, alignment, or identifiers.
- Output ONLY the Korean translation. No preamble, no notes.

English:
---
{chunk}
---
Korean:"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gemini-3.5-flash-lite")
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--chunks", type=int, default=0)
    a = ap.parse_args()

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=_key())
    text = io.open(a.src, encoding="utf-8").read()
    parts = [p.strip() for p in text.split("\n---\n") if p.strip()]
    if a.chunks:
        parts = parts[: a.chunks]

    done, sec_all = [], 0.0
    tin = tout = 0
    for i, p in enumerate(parts, 1):
        prompt = PROMPT.format(chunk=p)
        t0 = time.time()
        r = client.models.generate_content(
            model=a.model,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.2),
        )
        sec = time.time() - t0
        sec_all += sec
        u = r.usage_metadata
        tin += u.prompt_token_count or 0
        tout += u.candidates_token_count or 0
        ko = (r.text or "").strip()
        done.append(ko)
        print(f"  [{i}/{len(parts)}] {sec:5.1f}초 · 들어간 글자 {len(p):5d} "
              f"-> 나온 글자 {len(ko):5d} · 토큰 in {u.prompt_token_count} "
              f"out {u.candidates_token_count}", flush=True)

    Path(a.out).write_text("\n\n---\n\n".join(done), encoding="utf-8")
    print(f"\n모델 {a.model} · 토막 {len(parts)}개 · 모두 {sec_all:.1f}초")
    print(f"토큰   들어간 것 {tin:,} · 나온 것 {tout:,} · 합 {tin + tout:,}")
    print(f"-> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
