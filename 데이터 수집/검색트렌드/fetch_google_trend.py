# -*- coding: utf-8 -*-
"""구글 트렌드 검색량 수집 — 키 없이 되는 수요 신호 (2026-09-01)

## 왜 이걸 쓰나

우리 모델 입력 44개가 **전부 공급 쪽**이다. 사람들이 얼마나 사고 싶어
하는지를 재는 입력이 하나도 없다.

원래는 네이버 검색어 트렌드를 쓰려 했으나 **2026-07-31 에 신규 발급이
개발자센터에서 NAVER API HUB(네이버 클라우드) 로 옮겨졌다.** 빅카인즈
신문 기사 건수도 외부 발급이 막혀 있다. 구글 트렌드는 **키가 필요 없다.**

검색은 기사보다 앞선다. 기사는 값이 오른 **뒤에** 나오고 검색은 사기
**전에** 한다.

## ★ 두 가지 함정을 다룬다

**① 긴 구간을 요청하면 주별로 바뀐다.** 구글은 9개월쯤을 넘기면 일별을
안 주고 주별로 뭉쳐 준다. 그래서 **240일씩 끊어 받는다.**

**② 끊어 받으면 잣대가 달라진다.** 응답은 "요청 구간 안에서 제일 큰 날 =
100" 인 상대값이다. 그냥 이어붙이면 구간이 바뀔 때마다 가짜 계단이 생긴다.
**60일을 겹쳐 받아 겹친 구간의 비로 눈금을 맞춘다**(연쇄 보정).

    시험 성적에 비유하면 — 반이 다르면 1등의 100점이 서로 다른 실력이다.
    두 반에 다 있는 학생을 기준으로 눈금을 맞춰야 이어붙일 수 있다.

**③ 검색어 하나씩 따로 받는다.** 한 요청에 여러 개를 넣으면 제일 큰 것이
100 이 되고 나머지가 눌려 해상도를 잃는다 (실측: '무' 와 같이 넣으면
'깍두기' 가 1.2 로 눌린다).

## 검색어를 실측으로 골랐다

2023년으로 재본 결과다. **네이버용으로 짠 말은 구글에서 거의 안 쓴다.**

    배추 39.1 (0인 날 0%)   양파 67.6 (0%)   물가 54.2 (0%)   ← 쓴다
    김장  4.5 (0인 날 76%)                                    ← 계절성. 쓴다
    무값 · 채소값 · "OO 가격"  0.0~1.3 (0인 날 99~100%)        ← 못 쓴다

**무는 아직 쓸 검색어를 못 찾았다.** '무' 는 한 글자라 '무료' 같은 것에
섞일 수 있다. 배추·양파에서 효과가 보이면 그때 다시 판다.

## 쓰는 법

    python fetch_google_trend.py                        # 2016-01-01 ~ 어제
    python fetch_google_trend.py --probe 깍두기 동치미   # 검색어 자료량만 잰다
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
OUT = HERE / "output"

#   실측으로 고른 것만 넣는다 (위 머리말 참조).
KEYWORDS = {
    "gt_cabbage": "배추",
    "gt_onion": "양파",
    "gt_kimjang": "김장",
    "gt_price": "물가",
}


def client():
    try:
        from pytrends.request import TrendReq
    except ImportError:
        sys.exit("pytrends 가 없습니다.  pip install pytrends")
    return TrendReq(hl="ko-KR", tz=540)


def fetch(t, kw, s, e, tries=4):
    """한 구간을 받는다. 구글이 막으면 쉬었다 다시 한다."""
    for i in range(tries):
        try:
            t.build_payload([kw], timeframe=f"{s} {e}", geo="KR")
            d = t.interest_over_time()
            if d.empty:
                return None
            return d[[kw]].rename(columns={kw: "v"})
        except Exception as ex:                            # noqa: BLE001
            wait = 10 * (i + 1)
            print(f"      막힘({type(ex).__name__}) — {wait}초 쉬고 다시")
            time.sleep(wait)
    return None


def series(t, kw, start, end, win=240, overlap=60, pause=4.0):
    """240일씩 60일 겹쳐 받아 눈금을 맞춰 이어 붙인다."""
    out, s = None, pd.Timestamp(start)
    end = pd.Timestamp(end)
    while s <= end:
        e = min(s + pd.Timedelta(days=win), end)
        part = fetch(t, kw, str(s.date()), str(e.date()))
        if part is None:
            print(f"      {s.date()}~{e.date()} 못 받음. 건너뜀")
        elif out is None:
            out = part
        else:
            ov = out.index.intersection(part.index)
            if len(ov) == 0:
                #   겹침이 없으면 눈금을 못 맞춘다. 이어붙이면 가짜 계단이
                #   생기므로 붙이지 않고 멈춘다 — 조용히 틀린 값보다 낫다.
                sys.exit(f"{kw}: {s.date()} 구간에 겹침이 없습니다. "
                         "win/overlap 을 조정하세요.")
            a, b = out.loc[ov, "v"].sum(), part.loc[ov, "v"].sum()
            if b > 0:
                part = part * (a / b)
            out = pd.concat([out, part[~part.index.isin(out.index)]])
        if e >= end:
            break
        s = e - pd.Timedelta(days=overlap)
        time.sleep(pause)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="구글 트렌드 검색량을 일별로 받는다")
    ap.add_argument("--start", default="2016-01-01")
    ap.add_argument("--end", default=str(date.today() - timedelta(days=1)))
    ap.add_argument("--probe", nargs="+", default=None,
                    help="검색어 자료량만 잰다 (하나씩 따로 재야 눌리지 않는다)")
    ap.add_argument("--pause", type=float, default=4.0)
    a = ap.parse_args()
    t = client()

    if a.probe:
        print(f"[자료량 검사] {a.start} ~ {a.end} · 하나씩 따로 잽니다")
        for kw in a.probe:
            d = fetch(t, kw, a.start, a.end)
            if d is None:
                print(f"  {kw:<10} 못 받음")
            else:
                s = d["v"]
                print(f"  {kw:<10} 평균 {s.mean():>6.1f} · "
                      f"0인 날 {(s == 0).mean()*100:>5.1f}% · 최대 {s.max():>3} · "
                      f"{len(s)}일")
            time.sleep(a.pause)
        return 0

    want = pd.date_range(a.start, a.end, freq="D")
    print(f"[수집] {a.start} ~ {a.end} · {len(want):,}일 · 검색어 {len(KEYWORDS)}개")
    cols = {}
    for name, kw in KEYWORDS.items():
        print(f"  {name} ({kw})")
        s = series(t, kw, a.start, a.end, pause=a.pause)
        if s is None:
            print("    못 받았습니다. 건너뜁니다.")
            continue
        cols[name] = s["v"]
        print(f"    {len(s):,}일 · 평균 {s['v'].mean():.1f} · "
              f"0인 날 {(s['v'] == 0).mean()*100:.1f}%")
        time.sleep(a.pause)

    if not cols:
        sys.exit("하나도 못 받았습니다.")
    df = pd.DataFrame(cols).sort_index()
    df.index.name = "dt"

    miss = want.difference(df.index)
    print(f"\n[검사] {df.index.min().date()} ~ {df.index.max().date()} · "
          f"{len(df):,}일 · 빠진 날 {len(miss)}일")
    #   연도별 평균을 찍는다. 눈금 맞추기가 틀어졌으면 여기서 계단이 보인다.
    print("  연도별 평균 (계단이 보이면 눈금 맞추기가 틀어진 것입니다)")
    yr = df.groupby(df.index.year).mean().round(1)
    print("    " + yr.to_string().replace("\n", "\n    "))

    OUT.mkdir(exist_ok=True)
    p = OUT / "google_trend_daily.csv"
    df.round(4).to_csv(p, encoding="utf-8-sig")
    print(f"\n[저장] {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
