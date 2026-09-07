#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""뉴스 agent — 오늘 기사에서 **우리 품목 이야기만** 골라 보여준다.

    우리 모델은 뉴스를 못 읽습니다. 사람은 읽습니다.
    그 사이를 메우는 것이 이 agent 입니다.

    ─────────────────────────────────────────────────────────────
    ★ AI 가 하는 일은 둘뿐입니다

        ① 관련/무관 가르기      규칙으로 못 하는 일
        ② 이슈에 이름 붙이기    묶음마다 한 줄

    ★ AI 가 **안 하는** 일

        · 문장 지어내기 — 제목을 그대로 보여줍니다
        · 방향 말하기   — "급등했다" 같은 종합을 안 시킵니다
        · 숫자 다루기

    왜 이렇게 나눴나 (2026-09-07 실측)

        통째로 요약시켜 봤더니 **두 군데서 지어냈습니다.**

          ① 출처 번호를 만들어 냄
             제가 번호 없이 넣었는데 "(제목 5개, 9개, 11개…)" 라고 씀
          ② 방향을 단정함
             "배추·무·양파 가격이 급등" 이라 했는데, 그날 제목은 갈렸음
               "시금치 68%·배추 37%↑"          오름
               "무·배추·대파 가격 떨어지면…"     내림
               "경락가 상승·하락 품목"           섞임

        ★ 우리가 이미 잰 약점입니다 — 로컬 LLM 이 26.1% 를 57.2% 보다
          높다고 한 것과 같은 종류입니다. **비교와 방향에서 뒤집습니다.**

        그래서 **판단·집계는 규칙, AI 는 이름만** 으로 되돌렸습니다.
        우리가 처음부터 세워 둔 원칙인데 제가 어겼다가 되돌린 것입니다.

    ─────────────────────────────────────────────────────────────
    두 등급으로 나눕니다

        1군  배추·무·양파가 제목에 있고 값·물량·작황 이야기   반드시 봄
        2군  채소값·농산물 물가 전반                        참고

        ★ 넓게 받되 등급으로 가릅니다. 좁게 받으면 공급 충격을 놓치고,
          다 보여주면 아무도 안 봅니다 (오늘 실측: 넓게 = 하루 63건).

    쓰는 법
        python agent/news_agent.py                 # 오늘 것
        python agent/news_agent.py --date 2026-09-06
        python agent/news_agent.py --no-ai         # 규칙만 (AI 안 부름)
        python agent/news_agent.py --save
"""
from __future__ import annotations

import argparse
import csv
import datetime
import io
import itertools
import json
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

#   ★ 자기 출력을 UTF-8 로 고정한다 (윈도우 cp949). 화면에서 부르면
#     PYTHONIOENCODING 이 안 넘어온다 — 2026-09-07 에 이걸로 한 번 죽었다.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")   # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass

from core import Finding, Report, OK, WARN, BAD                # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "데이터 수집" / "뉴스" / "output" / "naver_news.csv"

OLLAMA = "http://localhost:11434/api/generate"
MODEL = "gemma3:4b"          # gemma4:e2b 는 빈 답을 낸다 (2026-09-07 실측)

ITEMS = ("배추", "무", "양파")

#: 값·물량 이야기인지 보는 낱말. **이걸로 최종 판정하지 않는다** — AI 앞에
#: 두는 싼 거름망이고, 애매한 것은 AI 가 본다.
#:
#:   ★ 낱말만으로는 부족하다 (2026-09-07 실측).
#:     "시금치 68%·배추 37%↑…추석 장바구니 '한숨'" 에는 위 낱말이 하나도
#:     없는데 **그날 제일 중요한 기사**였다. 숫자와 화살표가 값 이야기다.
MARKET = re.compile(
    r"가격|값|시세|경락|도매|출하|반입|수급|작황|물가|산지"
    r"|폭락|폭등|급등|급락|재배|생산량|비축|수매"
    r"|상승|하락|올라|올랐|내려|내렸|뛰어|뛰었|치솟"
    r"|[0-9]+\s*%|[↑↓]"
)

#: **값 이야기가 아닌 것이 확실한 낱말.** MARKET 을 넓히면 같이 들어온다.
#:
#:   실측: `배추|양파` 가 든 오늘 기사 12건 중 5건이 「창녕양파마늘가요제」였다.
#:   좁은 MARKET 이 우연히 막고 있었는데, 넓히면 뚫린다.
NOT_MARKET = re.compile(
    r"가요제|축제|공연|무대|콘서트|박물관|전시|기념식|캠페인"
    r"|표창|위촉|임명|간담회|MOU|협약|개장|개소|채용|공모"
)

#: 제목에 우리 품목이 나오나. `무` 는 한 글자라 앞뒤를 본다 —
#: 무엇·무료·나무·의무에 걸리면 안 된다.
RE_ITEM = re.compile(r"배추|양파|(?<![가-힣])무(?![가-힣])|무값|무 값|월동무|가을무|총각무")


# ─────────────────────────────────────────────────────────── 자료
def read_rows(day: str) -> list[dict]:
    if not CSV_PATH.exists():
        return []
    with io.open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
        return [r for r in csv.DictReader(f) if r.get("pub_dt", "").startswith(day)]


# ─────────────────────────────────────────────────────────── 묶기 (규칙)
def _norm(t: str) -> str:
    t = re.sub(r"\[[^\]]*\]|<[^>]*>|\([^)]*\)", " ", t)
    t = re.sub(r"[0-9]+", "", t)          # 1300t · 1천300t · 1300톤 을 같게
    return re.sub(r"[^가-힣A-Za-z]+", "", t)


def _grams(t: str, n: int = 3) -> set[str]:
    s = _norm(t)
    return {s[i:i + n] for i in range(max(0, len(s) - n + 1))}


def cluster(rows: list[dict], th: float = 0.3) -> list[list[int]]:
    """제목이 비슷하면 같은 사건으로 묶는다.

    ★ 글자 3그램을 쓴다. 낱말로 하면 `1300t` 와 `1천300t` 가 안 묶인다
      (실측: 낱말 기준 114 -> 108, 글자 기준 114 -> 95).
    ⚠️ 완벽하지 않다. 같은 사건이 두 묶음으로 갈리기도 하고, "장바구니
      부담 낮춘다" 같은 흔한 문구로 엉뚱한 것이 붙기도 한다.
      **그래서 묶음 안의 제목을 다 보여준다** — 사람이 보면 안다.
    """
    g = [_grams(r["title"]) for r in rows]
    par = list(range(len(rows)))

    def find(x: int) -> int:
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x

    for i, j in itertools.combinations(range(len(rows)), 2):
        if g[i] and g[j] and len(g[i] & g[j]) / len(g[i] | g[j]) >= th:
            a, b = find(i), find(j)
            if a != b:
                par[a] = b
    out: dict[int, list[int]] = {}
    for i in range(len(rows)):
        out.setdefault(find(i), []).append(i)
    return sorted(out.values(), key=len, reverse=True)


# ─────────────────────────────────────────────────────────── 가르기 (AI)
CLASSIFY = (
    "너는 배추·무·양파를 사고파는 사람이 볼 기사를 고르는 일을 한다.\n\n"
    "'관련' 은 아래 중 하나다.\n"
    "  (가) 배추·무·양파의 값·물량·작황·수급을 다룬다\n"
    "  (나) 채소값·농산물 물가 전반을 다룬다 (차례상 물가, 채소값 급등 등)\n"
    "  (다) 날씨·재해가 농작물 공급에 준 영향을 다룬다\n\n"
    "'무관' 은 이렇다.\n"
    "  · 사과·배·쌀·한우·감자 등 **다른 품목만** 다루는 기사\n"
    "  · 행사·축제·가요제·MOU·표창·인사·개장\n"
    "  · 정치·스포츠·기술·맛집·신제품\n"
    "  · 품목이 이름만 스치고 값·물량 얘기가 없는 기사\n\n"
    "출력은 '번호:관련' 또는 '번호:무관' 만. 한 줄에 하나. 설명 금지.\n\n"
)


def ollama(prompt: str, npred: int = 600, timeout: int = 600) -> str | None:
    body = json.dumps({"model": MODEL, "prompt": prompt, "stream": False,
                       "options": {"temperature": 0, "num_predict": npred}}).encode()
    req = urllib.request.Request(OLLAMA, data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8")).get("response", "")
    except Exception:                                        # noqa: BLE001
        return None


def classify(rows: list[dict], batch: int = 20) -> tuple[dict[int, bool], bool]:
    """AI 가 관련/무관을 가른다. 돌려주는 값: (판정, AI가 실제로 돌았나).

    ★ AI 가 죽으면 **규칙으로 떨어진다.** 조용히 0건을 내지 않는다.
    """
    out: dict[int, bool] = {}
    ai_ran = False
    for s in range(0, len(rows), batch):
        part = rows[s:s + batch]
        body = "\n".join(f"{i+1}. {r['title']}" for i, r in enumerate(part))
        resp = ollama(CLASSIFY + body)
        if resp is None:
            break
        ai_ran = True
        for ln in resp.splitlines():
            m = re.match(r"\s*(\d+)\s*[:.]?\s*(관련|무관)", ln.strip())
            if m:
                idx = s + int(m.group(1)) - 1
                if 0 <= idx < len(rows):
                    out[idx] = (m.group(2) == "관련")
    return out, ai_ran


def by_rule(r: dict) -> bool:
    """AI 없이 쓰는 거름망. 넓게 통과시킨다 — 놓치는 것이 더 비싸다."""
    t = r["title"]
    if NOT_MARKET.search(t):
        return False
    return bool(RE_ITEM.search(t) or MARKET.search(t))


# ─────────────────────────────────────────────────────────── 보고
def tier1(r: dict) -> bool:
    """1군 — 우리 품목이 제목에 있고 값·물량 이야기.

    ★ `NOT_MARKET` 이 먼저다. 「창녕양파마늘가요제」처럼 품목 이름이 행사
      이름에 박힌 것이 있다 (오늘만 5건).
    """
    t = r["title"]
    if NOT_MARKET.search(t):
        return False
    return bool(RE_ITEM.search(t) and MARKET.search(t))


def build(day: str, use_ai: bool) -> Report:
    rep = Report("뉴스요약")
    rows = read_rows(day)
    if not rows:
        rep.add(Finding(WARN, f"{day} 기사가 없습니다",
                        "fetch_naver_news.py 를 먼저 돌려 주세요.\n"
                        "★ '뉴스가 없다' 가 아니라 '안 받았다' 입니다.",
                        [("파일", str(CSV_PATH))]))
        return rep

    verdict, ai_ran = ({}, False)
    if use_ai:
        verdict, ai_ran = classify(rows)
    kept = [r for i, r in enumerate(rows)
            if verdict.get(i, by_rule(r) if not ai_ran else False)]

    if use_ai and not ai_ran:
        rep.add(Finding(WARN, "AI 를 못 불렀습니다 — 규칙으로 골랐습니다",
                        "ollama 가 떠 있는지 보세요. 지금 결과는 낱말만 보고 고른 것이라\n"
                        "가수 이름 '양파' 나 '무엇' 같은 것이 섞일 수 있습니다.",
                        [("모델", MODEL), ("주소", OLLAMA)]))

    ones = [r for r in kept if tier1(r)]
    twos = [r for r in kept if not tier1(r)]

    rep.add(Finding(OK, f"{day} — 기사 {len(rows)}건 중 {len(kept)}건이 관련",
                    "1군은 우리 품목이 제목에 있는 것, 2군은 채소·물가 전반입니다.",
                    [("받은 기사", f"{len(rows)}건"),
                     ("관련", f"{len(kept)}건"),
                     ("1군 (품목 직접)", f"{len(ones)}건"),
                     ("2군 (물가 전반)", f"{len(twos)}건"),
                     ("고른 방법", "AI" if ai_ran else "규칙")]))

    #   ── 1군: 하나씩 다 보여준다 ────────────────────────────────
    if ones:
        nums = [(r["pub_dt"][11:], r["title"][:70]) for r in ones[:12]]
        rep.add(Finding(BAD if len(ones) >= 3 else WARN,
                        f"1군 — 배추·무·양파 기사 {len(ones)}건",
                        "★ 제목을 그대로 옮깁니다. **방향을 종합하지 않습니다** —\n"
                        "  같은 날에도 오름과 내림이 같이 있습니다.",
                        nums,
                        "값이 우리 예측과 어긋나면 매입 파트에 알리십시오."))
    else:
        rep.add(Finding(OK, "1군 없음 — 우리 품목 기사가 없습니다",
                        "'조용하다' 는 뜻입니다. 2군만 참고하십시오."))

    #   ── 2군: 묶어서 대표 제목만 ──────────────────────────────
    if twos:
        cs = cluster(twos)
        lines = []
        for c in cs[:8]:
            head = twos[c[0]]["title"][:60]
            lines.append((f"{len(c)}건" if len(c) > 1 else "1건", head))
        rep.add(Finding(OK, f"2군 — 물가·수급 전반 {len(twos)}건 → {len(cs)}갈래",
                        "같은 사건이 여러 매체로 옵니다. 묶어서 대표 제목만 적습니다.",
                        lines))
    return rep


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    ap.add_argument("--no-ai", action="store_true", help="AI 없이 규칙만")
    ap.add_argument("--save", action="store_true")
    a = ap.parse_args()

    rep = build(a.date, use_ai=not a.no_ai)
    print(rep.text())
    if a.save:
        print("기록:", rep.save())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
