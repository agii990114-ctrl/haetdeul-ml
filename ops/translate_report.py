# -*- coding: utf-8 -*-
"""일별 점검 보고서를 영어에서 한국어로 옮긴다.

## 왜 이렇게 나눴나 (2026-09-09)

Claude 가 한국어로 쓴 보고서가 **「무슨 말인지 알아들을 수가 없다」**는
지적을 받았다. 그래서 일을 둘로 갈랐다.

    조사와 초안   Claude — DB 를 직접 뒤져야 나오는 것이 있다
    한국어로 쓰기  Gemini flash-lite — 이쪽이 글을 더 낫게 쓴다

실험으로 확인한 것 (`실험결과/번역실험_20260909/`) —

    flash-lite 가 **혼자** 보고서를 쓰면    3.9초 · 1,412자
        · 배추 「이상」이 헛경보인 것을 못 가려내고 진짜 경보로 올렸다
        · 매입 전달표 모양이 바뀐 것을 통째로 빠뜨렸다
        -> 규칙 도구가 낸 줄 밖으로는 한 발도 못 나간다

    Claude 영어 초안 -> flash-lite 번역     15초 · 숫자 216개
        · 두 번 돌려 두 번 다 숫자·품목 안 틀림
        · ollama(gemma4) 는 무를 «감자»·«고구마» 로 옮기고
          「1일 중 0일」을 「103일 중 0일」로 지어냈다

## 이 파일이 지키는 것 셋

★ **숫자를 기계로 대조한다.** 원문의 숫자가 번역에서 사라지면 보고서
  맨 위에 그 사실을 적는다. 이 보고서는 값어치가 숫자에 있다 —
  「50kg 한 건이 2일 중 1일을 만들었다」가 글의 전부인 날이 있다.

★ **번역이 실패해도 보고서는 남긴다.** 열쇠가 없거나 API 가 죽으면
  영어 원문을 그대로 결과 파일로 쓴다. **파일이 없으면 배치가 점검
  실패로 본다** — 읽기 불편한 것과 아예 없는 것은 다르다.

★ **낱말표를 지시에 박는다.** 안 박으면 «전달표» 가 «인수인계 테이블» 이
  되고 «특등급» 이 «상급» 이 된다. 실험에서 실제로 그랬다.
"""
from __future__ import annotations

import argparse
import io
import os
import re
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")     # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent.parent
MODEL = "gemini-3.5-flash-lite"


def _key() -> str | None:
    """열쇠는 .env 에서만 읽는다. 코드나 문서에 절대 안 적는다."""
    got = os.environ.get("GEMINI_API_KEY")
    if got:
        return got
    env = ROOT / ".env"
    if not env.exists():
        return None
    for ln in io.open(env, encoding="utf-8", errors="ignore"):
        ln = ln.strip()
        if ln.startswith("GEMINI_API_KEY") and "=" in ln:
            return ln.split("=", 1)[1].strip().strip('"').strip("'")
    return None


#   ★ 우리가 실제로 쓰는 말. 이걸 안 주면 모델이 제 나름대로 지어낸다.
GLOSSARY = """
경락가 (auction price)      경매에서 우리가 사는 값
중도매가 (wholesale price)  도매상이 파는 값
소매가 (retail price)       소비자가 사는 값
배추 (napa cabbage) · 무 (radish) · 양파 (onion)
특등급 (top grade) · 상등급 (second grade)
기준일 (base date)          예측을 만든 날
대상일 (target date)        예측이 가리키는 날
출발점 (anchor)             어제 가격. 예측의 출발점
전달표 (hand-off table)     매입 파트에 넘기는 예측표
배치 (batch)                매일 아침 자동으로 도는 일
재학습 (retraining)
"""

PROMPT = """아래 영어 보고서를 한국어로 옮겨라.

## 이 글이 무엇인가
농산물 가격 예측 시스템의 **일별 사후 점검 보고서**다. 읽는 사람은 사내
매입·재무 담당자다. 농사 전문가도, 머신러닝 전문가도 아니다.

## 말투
- 초등학생도 알아들을 수 있게. 전문 용어를 쓰면 바로 옆에 풀이를 붙인다
- 짧은 문장. 한 문장에 한 가지만
- 결론 먼저, 이유 나중
- **나쁜 소식을 순화하지 마라.** 이 보고서는 우리 예측이 얼마나 틀리는지를
  일부러 대놓고 적는다. 그 날카로움을 그대로 옮겨라
- **«없다» 와 «0이다» 는 다르다.** 이 구분이 흐려지면 사람이 없는 확신을 갖는다

## 반드시 지킬 것
- **숫자·날짜·비율·파일 이름은 한 글자도 바꾸지 마라.** 「1 of 2 days」를
  「103일 중 0일」처럼 바꾸면 보고서가 통째로 거짓말이 된다
- 마크다운 짜임을 그대로 둔다 — 제목·코드칸·표·굵은 글씨
- ``` 코드칸 안에서는 **줄 맞춤과 숫자를 절대 건드리지 마라.** 사람이
  읽을 낱말만 옮긴다. 오류 메시지와 코드는 영어 그대로 둔다
- 아래 낱말표대로 옮긴다

## 낱말표
{glossary}

## 옮길 글
---
{chunk}
---

한국어 번역만 출력해라. 다른 말은 붙이지 마라."""


def numbers(text: str) -> list[str]:
    """글 안의 숫자를 뽑는다. 서식 차이는 미리 지운다."""
    t = text.replace("~", "-").replace("–", "-").replace("—", "-")
    t = t.replace(",", "").replace(":", "")
    return [w.rstrip(".-") for w in re.findall(r"\d[\d.\-%]*", t)]


def check(src: str, out: str) -> list[str]:
    """원문에 있는데 번역에서 사라진 숫자.

    ★ 날짜를 풀어 쓴 것(`08-27` -> `8월 27일`)은 잃은 게 아니다.
      그것까지 경보로 내면 매일 울어서 아무도 안 본다.
    """
    got = set(numbers(out))
    #   「8월 27일」 처럼 풀어 쓴 것도 숫자로 잡아 둔다
    for m, d in re.findall(r"(\d{1,2})월\s*(\d{1,2})일", out):
        got.add(f"{int(m):02d}-{int(d):02d}")
        got.add(m); got.add(d)
    return [n for n in dict.fromkeys(numbers(src)) if n not in got]


def ask(client, chunk: str) -> str:
    from google.genai import types
    r = client.models.generate_content(
        model=MODEL,
        contents=PROMPT.format(glossary=GLOSSARY.strip(), chunk=chunk),
        config=types.GenerateContentConfig(temperature=0.2),
    )
    return (r.text or "").strip()


BANNER = """> ⚠ **이 보고서는 기계가 번역했습니다. 숫자 {n}개가 원문과 다릅니다.**
> {lost}
> **이 숫자는 믿지 마시고 영어 원문을 보세요** — `{en}`

"""

#   ★ 숫자가 다 맞아도 이 줄은 늘 붙인다.
#
#     기계 대조는 **사라진 숫자**를 잡지, **지어낸 문장**은 못 잡는다.
#     실험에서 실제로 한 번 나왔다 — 「2일 중 1일 = 50%」 를
#     「103일 중 0일이 아니라 …」 로 늘려 썼다. 103 도 0 도 원문 어딘가에
#     있는 숫자라 대조를 그냥 통과한다. 두 번째 실행에서는 안 나왔다.
#
#     그러니 «이상하다» 싶을 때 한 번에 원문을 볼 수 있어야 한다.
FROM = """> 영어 초안을 기계(gemini-3.5-flash-lite)가 옮긴 글입니다.
> 이상해 보이는 문장은 원문을 보세요 — `{en}`

"""


def main() -> int:
    ap = argparse.ArgumentParser(description="영어 점검 보고서를 한국어로")
    ap.add_argument("--src", required=True, help="Claude 가 쓴 영어 초안")
    ap.add_argument("--out", required=True, help="화면이 읽는 한국어 보고서")
    a = ap.parse_args()

    src_path, out_path = Path(a.src), Path(a.out)
    if not src_path.exists():
        print(f"[실패] 영어 초안이 없습니다: {src_path}")
        return 1
    english = io.open(src_path, encoding="utf-8").read()

    def give_up(why: str) -> int:
        """★ 번역을 못 해도 **보고서는 남긴다.** 없는 것보다 영어가 낫다."""
        head = (f"> ⚠ **한국어 번역을 못 했습니다 — {why}**\n"
                f"> 아래는 영어 원문입니다.\n\n")
        out_path.write_text(head + english, encoding="utf-8")
        print(f"[주의] {why} · 영어 원문을 그대로 남겼습니다 -> {out_path}")
        return 0

    key = _key()
    if not key:
        return give_up(".env 에 GEMINI_API_KEY 가 없습니다")
    try:
        from google import genai
    except ImportError:
        return give_up("google-genai 가 안 깔려 있습니다")

    #   작은 모델은 긴 글을 받으면 뒤를 잘라먹는다. `---` 로 갈라 보낸다.
    parts = [p.strip() for p in english.split("\n---\n") if p.strip()]
    client = genai.Client(api_key=key)
    done, t0 = [], time.time()
    try:
        for i, p in enumerate(parts, 1):
            done.append(ask(client, p))
            print(f"  [{i}/{len(parts)}] {len(p)}자 -> {len(done[-1])}자", flush=True)
    except Exception as error:                                # noqa: BLE001
        return give_up(f"{type(error).__name__}")

    korean = "\n\n---\n\n".join(done)
    lost = check(english, korean)
    head = FROM.format(en=src_path.name)
    if lost:
        head = BANNER.format(n=len(lost), lost=" · ".join(lost[:10]),
                             en=src_path.name)
    korean = head + korean

    out_path.write_text(korean, encoding="utf-8")
    print(f"모델 {MODEL} · {len(parts)}토막 · {time.time() - t0:.1f}초")
    print(f"숫자 대조 — 사라진 것 {len(lost)}개 {lost[:10] if lost else ''}")
    print(f"-> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
