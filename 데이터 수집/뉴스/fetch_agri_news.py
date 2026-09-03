# -*- coding: utf-8 -*-
"""농업 전문지 기사 제목 수집 — 날짜별 (2026-09-02)

## 왜 이걸로 하나

LLM 에게 뉴스를 주려면 **기준일 이전 기사만** 써야 한다. 그 뒤 기사에는
답이 적혀 있다 ("배추값 900원 돌파" 같은).

    빅카인즈        외부 발급 불가
    네이버 뉴스 API  날짜 지정이 **없다.** 한 검색어당 1,000건까지만 닿는다
                   → "6월 기사만" 을 요청할 방법이 없다

    ★ 신문사 목록 페이지   날짜로 정확히 자를 수 있다

**날짜로 자르면 새는 것이 구조적으로 막힌다.** API 보다 낫다.

## robots.txt 확인 (2026-09-02)

    한국농어민신문  agrinet.co.kr   Disallow: /admin/ 만
    농민신문       nongmin.com     Disallow: /print/ · /searchMain 만
    농수축산신문    aflnews.co.kr   Disallow: /admin/ 만

**셋 다 기사 목록·본문을 막지 않는다.** 그래도 예의는 지킨다 — 아래 참조.

## 예의

    · 요청 사이에 1.5초 쉰다
    · 같은 날을 다시 안 받는다 (파일에 있으면 건너뜀)
    · 제목만 받는다. 본문은 안 받는다 — 부담이 크고, 신호는 제목으로 충분한지
      먼저 확인해야 한다
    · User-Agent 에 용도를 밝힌다

## 쓰는 법

    python fetch_agri_news.py --from 2026-06-01 --to 2026-08-31
    python fetch_agri_news.py --days 3          # 최근 3일 (배치용)
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import html
import re
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "output"
CSV = OUT / "agri_news.csv"

#   날짜로 정확히 잘리는 매체만 넣는다. 실측으로 확인했다 (2026-09-02).
#
#   ★ 농민신문(nongmin.com)은 뺐다. `?date=` 파라미터를 넣어도 안 걸린다 —
#     8/11 · 8/12 · 6/15 를 각각 요청했는데 **같은 기사 14건이 그대로** 왔다.
#     날짜가 안 걸리면 기준일 이후 기사가 섞여 답을 주게 된다.
SITES = {
    "한국농어민신문": (
        "https://www.agrinet.co.kr/news/articleList.html"
        "?sc_sdate={d}&sc_edate={d}&view_type=sm&page={p}"),
    "농수축산신문": (
        "https://www.aflnews.co.kr/news/articleList.html"
        "?sc_sdate={d}&sc_edate={d}&view_type=sm&page={p}"),
}
#   ★ HTTP 헤더에는 한글을 못 넣는다 (latin-1 만 된다).
#   한글을 넣었다가 UnicodeEncodeError 로 전부 실패했다 (2026-09-02).
UA = ("Mozilla/5.0 (compatible; haetdeul-research/1.0; "
      "crop price forecasting research)")

#   우리 세 품목과 값에 관한 말. 넓게 잡고 나중에 좁힌다.
KEYS = ["배추", "무", "양파", "김장", "가락", "도매", "경락", "시세",
        "가격", "수급", "출하", "작황", "산지", "반입"]

#   매체마다 주소 형식이 다르다 — 한 곳은 절대(https://…), 한 곳은
#   상대(/news/…) 를 쓴다. 절대만 잡았다가 한 매체가 통째로 0건이 됐다.
A_RE = re.compile(
    r'<a href="((?:https?://[^"]*?)?/news/articleView\.html\?idxno=(\d+))"[^>]*>'
    r'(.*?)</a>', re.S)
TAG_RE = re.compile(r"<[^>]+>")


def clean(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(TAG_RE.sub("", s))).strip()


def get(url: str, tries: int = 3) -> str:
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=25) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:                               # noqa: BLE001
            if i == tries - 1:
                print(f"    못 받음: {type(e).__name__}")
                return ""
            time.sleep(3 * (i + 1))
    return ""


def one_day(site: str, tmpl: str, day: str, pause: float):
    """하루치 제목을 모은다. 목록이 여러 쪽일 수 있어 끝까지 넘긴다."""
    seen, rows = set(), []
    for page in range(1, 8):
        h = get(tmpl.format(d=day, p=page))
        if not h:
            break
        new = 0
        for m in A_RE.finditer(h):
            url, idx, inner = m.group(1), m.group(2), m.group(3)
            title = clean(inner)
            #   같은 기사가 사진 링크 + 제목 링크로 두 번 나온다.
            #   제목이 있는 쪽만 쓴다.
            if not title or len(title) < 6 or idx in seen:
                continue
            seen.add(idx)
            rows.append(dict(dt=day, site=site, idxno=idx,
                             title=title, url=url))
            new += 1
        if new == 0:
            break
        time.sleep(pause)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description="농업 전문지 기사 제목을 날짜별로 모은다")
    ap.add_argument("--from", dest="d_from", default=None)
    ap.add_argument("--to", dest="d_to", default=None)
    ap.add_argument("--days", type=int, default=None,
                    help="최근 N일 (배치용). --from/--to 대신")
    ap.add_argument("--pause", type=float, default=1.5)
    a = ap.parse_args()

    if a.days:
        end = dt.date.today() - dt.timedelta(days=1)
        start = end - dt.timedelta(days=a.days - 1)
    else:
        if not (a.d_from and a.d_to):
            sys.exit("--from/--to 또는 --days 를 주세요.")
        start = dt.date.fromisoformat(a.d_from)
        end = dt.date.fromisoformat(a.d_to)

    OUT.mkdir(exist_ok=True)
    #   이미 받은 날은 건너뛴다. 같은 날을 반복해 받지 않는다.
    have = set()
    if CSV.exists():
        with open(CSV, encoding="utf-8-sig", newline="") as f:
            have = {(r["dt"], r["site"]) for r in csv.DictReader(f)}

    days = [(start + dt.timedelta(days=i)).isoformat()
            for i in range((end - start).days + 1)]
    print(f"[수집] {start} ~ {end} · {len(days)}일 · 매체 {len(SITES)}곳")
    print(f"  이미 받은 (날짜,매체) {len(have):,}쌍은 건너뜁니다")

    got, skipped = [], 0
    for d in days:
        for site, tmpl in SITES.items():
            if (d, site) in have:
                skipped += 1
                continue
            rows = one_day(site, tmpl, d, a.pause)
            got += rows
            hit = sum(1 for r in rows if any(k in r["title"] for k in KEYS))
            print(f"  {d} {site}  {len(rows):>3}건 (품목·가격 관련 {hit})")
            time.sleep(a.pause)

    if not got:
        print(f"\n  새로 받은 것이 없습니다 (건너뜀 {skipped}일)")
        return 0

    #   ★ 옆에 붙은 "많이 본 기사" 를 걸러낸다 (2026-09-02 발견).
    #
    #   목록 페이지에 기사 블록이 3개 있다 — 본문 목록 + 인기 기사 등.
    #   인기 기사는 **오늘 기준**이라 어느 날짜를 요청하든 똑같이 딸려 온다.
    #   그대로 두면 **기준일 이후 기사가 섞인다** = 답을 주는 것이다.
    #   실제로 같은 기사가 8/10~8/16 일곱 날 전부에 나왔다.
    #
    #   진짜 기사는 하루에만 나오고, 인기 기사는 모든 날에 나온다.
    #   **두 날짜 이상에 나온 것은 뺀다.**
    from collections import defaultdict
    seen_on = defaultdict(set)
    for r in got:
        seen_on[r["idxno"]].add(r["dt"])
    dup = {k for k, v in seen_on.items() if len(v) > 1}
    if dup:
        before = len(got)
        got = [r for r in got if r["idxno"] not in dup]
        print("\n  [거름] 여러 날짜에 나온 기사 %d개를 뺐습니다 (%d → %d건)"
              % (len(dup), before, len(got)))
        print("        옆에 붙은 '많이 본 기사' 입니다")
    if len(days) < 3:
        print("        ※ 날짜가 3일 미만이면 이 거르기가 부정확합니다")
    if not got:
        print("  남은 기사가 없습니다.")
        return 0

    new = not CSV.exists()
    with open(CSV, "a", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["dt", "site", "idxno", "title", "url"])
        if new:
            w.writeheader()
        w.writerows(got)
    print(f"\n[저장] {CSV}  (새로 {len(got):,}건 · 건너뜀 {skipped}일)")

    hit = [r for r in got if any(k in r["title"] for k in KEYS)]
    print(f"  품목·가격 관련 {len(hit):,}건 ({len(hit)/len(got)*100:.0f}%)")
    print("  예시:")
    for r in hit[:5]:
        print(f"    {r['dt']}  {r['title'][:56]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
