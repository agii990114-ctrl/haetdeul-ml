# -*- coding: utf-8 -*-
"""영어 보고서를 ollama 로 한국어로 옮긴다 — 실험용.

★ **왜 하는가.** Claude 가 쓴 한국어가 어렵다는 지적을 받았다. 그래서
  «Claude 는 영어로 쓰고, 번역은 따로 시킨다» 가 통하는지 본다.

★ **조각으로 나눠 보낸다.** 2~4B 짜리 작은 모델은 긴 글을 받으면 뒤를
  통째로 잘라먹는다. `---` 로 갈라 한 토막씩 보낸다.

★ **코드칸과 숫자는 건드리지 말라고 이른다.** 작은 모델은 표 안 숫자를
  «정리» 해 버리는 버릇이 있다. 그러면 보고서가 거짓말이 된다.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import time
import urllib.request
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")     # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass

OLLAMA = "http://localhost:11434/api/generate"

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


def ask(model: str, prompt: str, timeout: int = 900) -> tuple[str, float]:
    body = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": 2048, "num_ctx": 8192},
    }).encode("utf-8")
    req = urllib.request.Request(OLLAMA, data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        out = json.loads(r.read().decode("utf-8"))
    return out.get("response", "").strip(), time.time() - t0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--chunks", type=int, default=0, help="앞에서 몇 토막만 (0=전부)")
    a = ap.parse_args()

    text = io.open(a.src, encoding="utf-8").read()
    parts = [p.strip() for p in text.split("\n---\n") if p.strip()]
    if a.chunks:
        parts = parts[: a.chunks]

    done, total = [], 0.0
    for i, p in enumerate(parts, 1):
        ko, sec = ask(a.model, PROMPT.format(chunk=p))
        total += sec
        done.append(ko)
        print(f"  [{i}/{len(parts)}] {sec:5.1f}초 · 들어간 글자 {len(p):5d} "
              f"-> 나온 글자 {len(ko):5d}", flush=True)

    Path(a.out).write_text("\n\n---\n\n".join(done), encoding="utf-8")
    print(f"모델 {a.model} · 토막 {len(parts)}개 · 모두 {total:.1f}초 -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
