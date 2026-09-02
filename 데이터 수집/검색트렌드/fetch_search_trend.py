# -*- coding: utf-8 -*-
"""네이버 검색어 트렌드 수집 — 품목별 수요 신호 (2026-09-01)

## 왜 모으나

우리 모델 입력 44개가 **전부 공급 쪽**이다 (가격 이력 24 · 반입량 3 ·
기상 10 · 경제 3 · 기타 4). **사람들이 얼마나 사고 싶어 하는지를 재는
입력이 하나도 없다.**

검색은 기사보다 앞선다. 기사는 값이 오른 **뒤에** 나오지만
검색은 사기 **전에** 한다.

## 원천

    POST https://naverapihub.apigw.ntruss.com/search-trend/v1/search
    ※ 2026-07-31 에 개발자센터에서 NAVER API HUB 로 옮겨졌다.
      옛 주소(openapi.naver.com)는 2027-06-30 까지만 동작한다.
    시작 가능일   2016-01-01      ← 학습 구간(2017~)을 덮는다
    단위          date (일별)
    한도          월 50,000회 · 초당 50회 (HUB 기준)

## ★ 상대값이라는 함정

응답의 `ratio` 는 **요청한 구간 안에서 가장 큰 값이 100** 이 되도록 맞춘
상대값이다. 구간을 나눠 받아서 이어붙이면 **구간마다 잣대가 달라져
가짜 계단이 생긴다.**

    잘못   2017년 따로 · 2018년 따로 받아 이어붙임 → 해가 바뀔 때마다 점프
    바르게 전 구간을 한 번에 받는다. 나눠야 하면 겹치는 구간으로 잣대를 맞춘다

이 스크립트는 **한 번에 전 구간**을 받고, 응답 일수가 모자라면
겹침 구간으로 이어 붙인다(연쇄 보정).

## ★ '무' 는 검색어로 쓰지 않는다

'무' 는 한 글자라 '무료' · '무슨' 같은 것에 다 걸린다.
**'무값' · '무 가격' · '무 시세' 처럼 값을 묻는 말만 쓴다.**
배추·양파도 같은 이유로 값 관련 어구를 함께 넣는다.

## 쓰는 법

    .env 에 넣고:
        NCP_APIGW_API_KEY_ID=...      (NAVER API HUB · 신규)
        NCP_APIGW_API_KEY=...
      또는 예전 키가 있다면
        NAVER_CLIENT_ID=... / NAVER_CLIENT_SECRET=...

    python fetch_search_trend.py                    # 2016-01-01 ~ 어제
    python fetch_search_trend.py --start 2016-01-01 --end 2026-08-31
    python fetch_search_trend.py --check            # 키만 확인하고 안 받는다

키 값은 **절대 출력하지 않는다.** 있다/없다만 찍는다.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "output"
#   ★ 2026-07-31 에 네이버가 이 API 를 개발자센터 → NAVER API HUB 로 옮겼다.
#   주소도 인증 헤더 이름도 바뀌었다. 신규 신청은 HUB 쪽만 된다.
#     구(舊)  developers.naver.com 에서 발급 · 2027-06-30 까지만 동작
#     신(新)  NAVER Cloud Platform > API HUB 콘솔에서 발급
#   둘 다 지원한다 — 어떤 키가 들어오든 맞춰 부른다.
URL_HUB = "https://naverapihub.apigw.ntruss.com/search-trend/v1/search"
URL_OLD = "https://openapi.naver.com/v1/datalab/search"

#   묶음은 최대 5개, 묶음당 검색어 최대 20개.
#   각 묶음의 검색어는 **합산**되어 하나의 시계열이 된다.
GROUPS = {
    "trend_cabbage": ["배추", "배추값", "배추 가격", "배추 시세"],
    "trend_radish": ["무값", "무 가격", "무 시세", "총각무"],
    "trend_onion": ["양파", "양파값", "양파 가격", "양파 시세"],
    "trend_kimjang": ["김장", "김장철", "김장 배추", "김장 비용"],
    "trend_veg_price": ["채소값", "야채값", "농산물 가격", "장바구니 물가"],
}


def load_env():
    for p in (ROOT / ".env", HERE / ".env"):
        if p.exists():
            for raw in p.read_text(encoding="utf-8-sig").splitlines():
                line = raw.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip("\"'"))


def creds():
    """어느 쪽 키가 있는지 보고 (방식, 아이디, 비밀값) 을 돌려준다."""
    load_env()
    e = os.environ
    hub_id = e.get("NCP_APIGW_API_KEY_ID", "").strip()
    hub_key = e.get("NCP_APIGW_API_KEY", "").strip()
    if hub_id and hub_key:
        return "hub", hub_id, hub_key
    cid = e.get("NAVER_CLIENT_ID", "").strip()
    sec = e.get("NAVER_CLIENT_SECRET", "").strip()
    if cid and sec:
        return "old", cid, sec
    return "", "", ""


def call(mode, cid, sec, start, end):
    """한 번 호출로 5개 묶음을 다 받는다. 실패하면 무엇이 문제인지 말한다."""
    body = json.dumps({
        "startDate": start, "endDate": end, "timeUnit": "date",
        "keywordGroups": [{"groupName": g, "keywords": ks}
                          for g, ks in GROUPS.items()],
    }, ensure_ascii=False).encode("utf-8")
    if mode == "hub":
        url, head = URL_HUB, {"X-NCP-APIGW-API-KEY-ID": cid,
                              "X-NCP-APIGW-API-KEY": sec}
    else:
        url, head = URL_OLD, {"X-Naver-Client-Id": cid,
                              "X-Naver-Client-Secret": sec}
    head["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, method="POST", headers=head)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", "replace")[:300]
        if e.code == 401:
            sys.exit("인증 실패(401). 키가 틀렸거나 아직 반영 전입니다.\n" + msg)
        if e.code == 403:
            sys.exit("권한 없음(403). 애플리케이션의 '사용 API' 에\n"
                     "  데이터랩(검색어 트렌드)\n"
                     "가 추가돼 있는지 확인하세요.\n" + msg)
        if e.code == 429:
            sys.exit("호출 한도 초과(429). 하루 1,000회입니다.\n" + msg)
        sys.exit(f"HTTP {e.code}\n{msg}")


def to_frame(res):
    """응답 → 날짜 × 묶음 표. 없는 날은 그대로 비워 둔다(0 으로 채우지 않는다)."""
    out = None
    for r in res.get("results", []):
        name = r["title"]
        d = pd.DataFrame(r["data"])
        if d.empty:
            continue
        d["period"] = pd.to_datetime(d.period)
        d = d.rename(columns={"ratio": name}).set_index("period")[[name]]
        out = d if out is None else out.join(d, how="outer")
    return out


def chain(prev, cur, cols):
    """겹치는 날짜로 잣대를 맞춰 이어 붙인다.

    구간을 나눠 받으면 구간마다 최댓값이 100 이 되도록 다시 눌린다.
    겹친 구간의 비로 뒤쪽 전체를 곱해 주면 계단이 사라진다.
    """
    ov = prev.index.intersection(cur.index)
    if len(ov) == 0:
        raise SystemExit("겹치는 구간이 없어 잣대를 맞출 수 없습니다.")
    cur = cur.copy()
    for c in cols:
        a, b = prev.loc[ov, c].sum(), cur.loc[ov, c].sum()
        cur[c] = cur[c] * (a / b) if b > 0 else cur[c]
    return pd.concat([prev, cur[~cur.index.isin(prev.index)]])


def main() -> int:
    ap = argparse.ArgumentParser(description="네이버 검색어 트렌드를 일별로 받는다")
    ap.add_argument("--start", default="2016-01-01")
    ap.add_argument("--end", default=str(date.today() - timedelta(days=1)))
    ap.add_argument("--check", action="store_true", help="키만 확인한다")
    ap.add_argument("--chunk-days", type=int, default=1000,
                    help="한 번에 못 받을 때 나눌 크기. 90일씩 겹쳐 이어 붙인다")
    a = ap.parse_args()

    mode, cid, sec = creds()
    print("[키] " + {"hub": "NAVER API HUB 키를 씁니다 (신규 방식)",
                     "old": "개발자센터 키를 씁니다 (2027-06-30 까지)",
                     "": "키가 없습니다"}[mode])
    if not mode:
        print("")
        print("★ 2026-07-31 부로 개발자센터에서는 신규 발급이 안 됩니다.")
        print("  NAVER Cloud Platform > API HUB 콘솔에서 발급받으세요.")
        print("")
        print("  .env 에 넣을 것 (HUB 방식)")
        print("    NCP_APIGW_API_KEY_ID=발급받은_아이디")
        print("    NCP_APIGW_API_KEY=발급받은_키")
        print("")
        print("  이미 예전 키가 있다면 (2027-06-30 까지 동작)")
        print("    NAVER_CLIENT_ID=... / NAVER_CLIENT_SECRET=...")
        return 1
    if a.check:
        return 0

    want = pd.date_range(a.start, a.end, freq="D")
    print(f"[수집] {a.start} ~ {a.end} · {len(want):,}일 · 묶음 {len(GROUPS)}개")
    for g, ks in GROUPS.items():
        print(f"    {g:<18} {' / '.join(ks)}")

    #   먼저 전 구간을 한 번에 시도한다. 그래야 잣대가 하나로 유지된다.
    df = to_frame(call(mode, cid, sec, a.start, a.end))
    if df is None:
        sys.exit("응답에 자료가 없습니다.")
    print(f"\n  한 번에 받은 일수 {len(df):,} / 요청 {len(want):,}")

    if len(df) < len(want) * 0.99:
        print("  → 잘려서 왔습니다. 90일씩 겹쳐 나눠 받고 잣대를 맞춥니다.")
        df, s = None, pd.Timestamp(a.start)
        end = pd.Timestamp(a.end)
        while s <= end:
            e = min(s + pd.Timedelta(days=a.chunk_days), end)
            part = to_frame(call(mode, cid, sec, str(s.date()), str(e.date())))
            df = part if df is None else chain(df, part, list(GROUPS))
            print(f"    {s.date()} ~ {e.date()}  누적 {len(df):,}일")
            if e >= end:
                break
            s = e - pd.Timedelta(days=90)      # 90일 겹침
            time.sleep(0.3)

    df = df.sort_index()
    df.index.name = "dt"
    miss = want.difference(df.index)
    print(f"\n[검사] {df.index.min().date()} ~ {df.index.max().date()} · "
          f"{len(df):,}일 · 빠진 날 {len(miss)}일")
    if len(miss):
        print("  빠진 날 예시:", ", ".join(str(d.date()) for d in miss[:5]))
    for c in GROUPS:
        s = df[c]
        print(f"    {c:<18} 최소 {s.min():>6.2f} · 최대 {s.max():>6.2f} · "
              f"0인 날 {(s == 0).sum():>5}일")

    #   0 이 많으면 검색어가 너무 드문 것이다. 그대로 쓰면 대부분 0 인
    #   컬럼이 되어 아무 정보가 없다. 경고만 하고 저장은 한다.
    for c in GROUPS:
        if (df[c] == 0).mean() > 0.3:
            print(f"  ※ {c} 는 0인 날이 30%를 넘습니다. 검색어를 바꾸세요.")

    OUT.mkdir(exist_ok=True)
    p = OUT / "search_trend_daily.csv"
    df.round(4).to_csv(p, encoding="utf-8-sig")
    print(f"\n[저장] {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
