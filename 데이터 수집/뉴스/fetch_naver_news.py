# -*- coding: utf-8 -*-
"""네이버 뉴스 검색 수집 — 우리 품목의 가격·작황 기사 (2026-09-07)

## 왜 이걸로 바꿨나

앞서 만든 `fetch_agri_news.py` 는 농업 전문지 두 곳의 목록 페이지를 날짜로
잘라 받았다. **LLM 예측 시험용으로는 그게 맞았다** — 기준일 이후 기사가
새어들면 답이 적혀 있으니 날짜로 정확히 잘라야 했다.

**그런데 매일 도는 agent 에는 안 맞는다.** 실측 (2026-06-01 ~ 08-31 · 2,034건)

    하루 평균 기사              28.2건
    우리 품목 + 가격/충격        0.12건
    쓸 만한 기사가 있는 날       72일 중 8일

★ **아홉 날 중 여덟 날은 쓸 게 없다.** 농업 전문지는 지자체·협회·행사 소식이
  대부분이라 우리가 원하는 신문이 아니었다.

네이버는 **검색어로 부른다.** 원하는 것만 온다.

    검색어 하나당 하루 20~30건 · 그중 쓸 만한 것 2~4건 · 매일 있음

## ★ 옛 주소로 부르면 401 이 난다

2026-07-31 에 네이버가 개발자센터 → NAVER API HUB 로 옮기며 **주소와 인증
헤더 이름을 둘 다 바꿨다.**

    구  https://openapi.naver.com/v1/search/news.json
        X-Naver-Client-Id · X-Naver-Client-Secret
    신  https://naverapihub.apigw.ntruss.com/search/v1/news
        X-NCP-APIGW-API-KEY-ID · X-NCP-APIGW-API-KEY

★ 이걸 몰라 401 을 네 번 봤다. **우리 `fetch_search_trend.py` 주석에 이미
  적혀 있었는데 안 읽고 시작했다.**

`robots.txt` 는 문제되지 않는다 — 공식 API 다.

## ★ 검색어로는 못 거른다 — 그래서 AI 가 필요하다

받은 것을 정규식으로 걸러 봤고 **두 번 연달아 틀렸다.**

    「양파 출하」  → "추석 **사과** 출하 현장 점검" 을 통과시킴
    「무 출하」    → "제철 **금사과**, 껍질째 드세요" 를 통과시킴
    「양파 가격」  → "특설무대 허찬미, **양파**, 정진호" (가수 이름)

`무` 는 한 글자라 `무엇·무료·나무` 에 걸리고, `양파` 는 요리 재료이자 가수
이름이다. `출하·공급` 같은 낱말은 아무 기사에나 있다.

> **낱말이 있나 없나로는 안 되고 문장의 뜻을 읽어야 한다.**
> 이 파일은 **받아서 쌓기만** 한다. 고르는 것은 뒷단(agent)의 몫이다.

## 쓰는 법

    python fetch_naver_news.py                # 최근 것 한 바퀴
    python fetch_naver_news.py --display 30   # 검색어당 30건
    python fetch_naver_news.py --dry-run      # 저장 안 하고 보기만

## 예의

    · 요청 사이에 0.4초 쉰다
    · 같은 링크는 다시 안 쌓는다 (link 로 중복 제거)
    · User-Agent 에 용도를 밝힌다
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "output"
CSV_PATH = OUT / "naver_news.csv"

URL = "https://naverapihub.apigw.ntruss.com/search/v1/news"

#: 품목별 검색어. **실측으로 골랐다** (2026-09-07 · 검색어 16개 시험).
#:
#:   배추  「배추 가격」·「배추 작황」이 20건 중 대부분 관련 기사
#:   무    한 글자라 오염이 심하다. 「무 도매」·「무 출하」가 그나마 낫다
#:   양파  요리 재료이자 가수 이름이다. 「양파 출하」·「양파 수급」이 낫다
#:
#: ★ 그래도 완전히는 안 걸러진다 (위 docstring). 여기서는 **넓게 받고**
#:   뒷단에서 뜻으로 고른다. 좁게 받으면 진짜 기사를 놓친다.
QUERIES = {
    "배추": ["배추 가격", "배추 작황", "배추 도매", "고랭지 배추"],
    "무":   ["무 도매", "무 시세", "가을무", "월동무"],
    "양파": ["양파 출하", "양파 수급", "양파 산지", "양파값"],
    "공통": ["농산물 수급", "농업관측", "채소 가격"],
}

FIELDS = ["fetched_at", "pub_dt", "item", "query", "title", "description", "link", "orig_link"]


def load_env() -> None:
    for p in (ROOT / ".env", HERE / ".env"):
        if p.exists():
            for raw in p.read_text(encoding="utf-8-sig").splitlines():
                line = raw.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip("\"'"))


def creds() -> tuple[str, str]:
    load_env()
    cid = os.environ.get("NAVER_API_ID", "").strip()
    key = os.environ.get("NAVER_API_KEY", "").strip()
    if not (cid and key):
        raise SystemExit(
            "NAVER_API_ID · NAVER_API_KEY 가 필요합니다 (.env).\n"
            "  NAVER Cloud Platform > API HUB 콘솔에서 발급합니다.\n"
            "  ※ 옛 developers.naver.com 키는 주소·헤더가 달라 여기서 안 됩니다."
        )
    return cid, key


def clean(s: str) -> str:
    """태그와 HTML 실체 참조를 걷어낸다. 검색 결과는 <b> 로 강조가 들어온다."""
    s = re.sub(r"<[^>]+>", "", s or "")
    for a, b in (("&quot;", '"'), ("&amp;", "&"), ("&apos;", "'"),
                 ("&lt;", "<"), ("&gt;", ">"), ("&nbsp;", " ")):
        s = s.replace(a, b)
    return s.strip()


def to_kst(pub: str) -> str:
    """RFC1123(`Mon, 07 Sep 2026 14:48:00 +0900`) → `YYYY-MM-DD HH:MM`.

    못 읽으면 원문을 그대로 둔다 — **조용히 버리지 않는다.**
    """
    try:
        dt = datetime.strptime(pub.strip(), "%a, %d %b %Y %H:%M:%S %z")
        return dt.astimezone(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return pub.strip()


def search(cid: str, key: str, query: str, display: int) -> list[dict]:
    url = f"{URL}?query={urllib.parse.quote(query)}&display={display}&sort=date"
    req = urllib.request.Request(url, headers={
        "X-NCP-APIGW-API-KEY-ID": cid,
        "X-NCP-APIGW-API-KEY": key,
        "User-Agent": "haetdeul-ml/1.0 (agri price research; contact via repo)",
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8")).get("items", [])
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", "replace")[:200]
        except Exception:                                    # noqa: BLE001
            pass
        print(f"  [{e.code}] {query} — {body}")
        if e.code == 401:
            print("        ★ 주소·헤더가 새 방식(API HUB)인지 보세요. 위 docstring 참조")
        return []
    except Exception as e:                                   # noqa: BLE001
        print(f"  [실패] {query} — {type(e).__name__}: {e}")
        return []


def existing_links() -> set[str]:
    if not CSV_PATH.exists():
        return set()
    with io.open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
        return {r.get("link", "") for r in csv.DictReader(f)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--display", type=int, default=30, help="검색어당 받을 건수 (최대 100)")
    ap.add_argument("--pause", type=float, default=0.4)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    cid, key = creds()
    OUT.mkdir(parents=True, exist_ok=True)
    seen = existing_links()
    now = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M")

    rows: list[dict] = []
    dup = 0
    print(f"검색어 {sum(len(v) for v in QUERIES.values())}개 · 각 {a.display}건")
    for item, qs in QUERIES.items():
        for q in qs:
            items = search(cid, key, q, a.display)
            new = 0
            for it in items:
                link = it.get("link", "")
                if not link or link in seen:
                    dup += 1
                    continue
                seen.add(link)
                new += 1
                rows.append({
                    "fetched_at": now,
                    "pub_dt": to_kst(it.get("pubDate", "")),
                    "item": item,
                    "query": q,
                    "title": clean(it.get("title", "")),
                    "description": clean(it.get("description", "")),
                    "link": link,
                    "orig_link": it.get("originallink", ""),
                })
            print(f"  {item:<4} {q:<12} 받음 {len(items):>3} · 신규 {new:>3}")
            time.sleep(a.pause)

    print(f"\n신규 {len(rows)}건 · 중복 {dup}건")
    if a.dry_run:
        for r in rows[:10]:
            print(f"  {r['pub_dt']} [{r['item']}] {r['title'][:56]}")
        print("\n--dry-run 이라 저장하지 않았습니다.")
        return 0
    if not rows:
        print("새로 쌓을 것이 없습니다.")
        return 0

    first = not CSV_PATH.exists()
    with io.open(CSV_PATH, "a", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if first:
            w.writeheader()
        w.writerows(rows)
    print(f"저장: {CSV_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
