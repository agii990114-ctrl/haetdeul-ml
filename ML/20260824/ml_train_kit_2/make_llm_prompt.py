# -*- coding: utf-8 -*-
"""LLM 예측 시험 — 프롬프트 만들기 + 채점 (2026-09-01)

## 무엇을 하나

**"모델 대신 LLM 이 예측하면 어떤가" 를 실제로 잰다.**

## ★ 왜 2026-06 이후만 쓰나

LLM 은 2026년 5월까지의 글로 배웠다. 그러면 **2022~2025 는 결과를 이미
읽었을 수 있다.** 거기서 재면 예측인지 기억인지 구분할 수 없다.

    시험 구간   2026-06-01 ~ 2026-08-31   (59 기준일 · 정답 96%)

**이 구간은 학습 이후라 결과가 LLM 안에 없다.**

## ★ 날짜를 가린다

`base_dt` · `target_dt` 를 안 준다. "기준일 A" 처럼 이름만 준다.
**날짜를 알면 그것만으로 아는 걸 끌어올 수 있다.**

**다만 완전히 가릴 수는 없다** — 주산지 이름(해남·대관령)과 기온이
계절을 드러낸다. 이건 모델도 받는 입력이라 빼면 비교가 불공정해진다.
**"2026년 여름쯤" 을 아는 것과 "그때 값이 얼마였나" 를 아는 것은 다르다.**

## 공정하게 맞춘 것

    준다      모델이 받는 feature 31개 그대로. 숫자만
    안 준다    실제 결과 · 뉴스 · 날짜 · "지금 배추가 비싸다" 같은 힌트
    비교 대상  LightGBM(운영) · 앵커(어제값 40% + 최근7일평균 60%)

**앵커를 이기는지가 핵심이다.** 오늘 실측에서 LightGBM 도 앵커를
3.5%밖에 못 앞선다.

## 쓰는 법

    python make_llm_prompt.py <csv> --n-dates 10 --out ../../../실험결과/llm_prompt.md
    python make_llm_prompt.py <csv> --score ../../../실험결과/llm_answer.txt
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from exp_quantile import build                               # noqa: E402

ALPHA = 0.4          # 경락가 운영값
ITEMS = ["배추", "무", "양파"]
#   한 기준일 안에서 값이 바뀌는 것 — 리드타임 표로 준다
VARY = ["target_dow", "holiday_remain_d", "kimchi_season_yn",
        "prod_area_stn_nm", "prod_area_temp_avg_lag1", "prod_area_rain_sum7",
        "prod_area_rain_sum30", "prod_area_gdd_sum30",
        "prod_area_clim_temp_avg10", "whsl_prc_prev_yr", "arr_qty_prev_yr"]
NICE = {
    "_anchor_mix": "출발점(어제값 40% + 최근7일평균 60%)",
    "auc_prc_lag3": "경락가 3일 전", "auc_prc_avg7": "경락가 최근 7일 평균",
    "auc_prc_spread_lag1": "경락가 등급 스프레드", "auc_vol_lag1": "경매 물량(kg)",
    "auc_whsl_ratio_lag1": "중도매가÷경락가 배수",
    "whsl_prc_lag1": "중도매가 어제", "whsl_prc_lag3": "중도매가 3일 전",
    "whsl_prc_lag7": "중도매가 7일 전", "whsl_prc_avg7": "중도매가 7일 평균",
    "whsl_prc_avg14": "중도매가 14일 평균", "whsl_prc_std7": "중도매가 7일 표준편차",
    "arr_qty_lag1": "반입량 어제(톤)", "arr_qty_avg7": "반입량 7일 평균(톤)",
    "rtl_prc_lag1": "소매가 어제", "market_temp_avg_lag1": "시장 소재지 기온",
    "market_closed_lag1_yn": "어제 휴장(1=휴장)",
    "target_dow": "대상일 요일", "holiday_remain_d": "명절까지 남은 날",
    "kimchi_season_yn": "김장철(1=예)", "prod_area_stn_nm": "주산지 관측소",
    "prod_area_temp_avg_lag1": "주산지 기온", "prod_area_rain_sum7": "주산지 7일 강수",
    "prod_area_rain_sum30": "주산지 30일 강수", "prod_area_gdd_sum30": "주산지 생육온도 30일",
    "prod_area_clim_temp_avg10": "주산지 평년 기온",
    "whsl_prc_prev_yr": "작년 같은 시기 중도매가", "arr_qty_prev_yr": "작년 같은 시기 반입량",
}


#   ── 영어판 (2026-09-02) ─────────────────────────────────────────────
#   왜: LLM 이 영어로 물었을 때 다르게 답하는지 본다. **한 가지만 바꾼다** —
#   블록·숫자·순서는 완전히 같고 말만 영어다. 그래야 언어 효과만 잰다.
#   품목 이름은 한국어를 괄호로 남긴다. 한국 시장 자료라는 맥락이 사라지면
#   다른 실험이 된다.
ITEM_EN = {"배추": "napa cabbage (배추)", "무": "Korean radish (무)",
           "양파": "onion (양파)"}
DOW_EN = {"월": "Mon", "화": "Tue", "수": "Wed", "목": "Thu",
          "금": "Fri", "토": "Sat", "일": "Sun"}
NICE_EN = {
    "_anchor_mix": "Starting point (40% yesterday + 60% last-7-day mean)",
    "auc_prc_lag3": "Auction price, 3 days ago",
    "auc_prc_avg7": "Auction price, last 7-day mean",
    "auc_prc_spread_lag1": "Auction grade spread",
    "auc_vol_lag1": "Auction volume (kg)",
    "auc_whsl_ratio_lag1": "Wholesale / auction ratio",
    "whsl_prc_lag1": "Wholesale price, yesterday",
    "whsl_prc_lag3": "Wholesale price, 3 days ago",
    "whsl_prc_lag7": "Wholesale price, 7 days ago",
    "whsl_prc_avg7": "Wholesale price, 7-day mean",
    "whsl_prc_avg14": "Wholesale price, 14-day mean",
    "whsl_prc_std7": "Wholesale price, 7-day std dev",
    "arr_qty_lag1": "Arrivals yesterday (tonnes)",
    "arr_qty_avg7": "Arrivals, 7-day mean (tonnes)",
    "rtl_prc_lag1": "Retail price, yesterday",
    "market_temp_avg_lag1": "Temperature at the market city",
    "market_closed_lag1_yn": "Market closed yesterday (1=yes)",
    "target_dow": "Weekday of target day",
    "holiday_remain_d": "Days until the next holiday",
    "kimchi_season_yn": "Kimjang season (1=yes)",
    "prod_area_stn_nm": "Main growing-area station",
    "prod_area_temp_avg_lag1": "Growing-area temperature",
    "prod_area_rain_sum7": "Growing-area rain, 7 days",
    "prod_area_rain_sum30": "Growing-area rain, 30 days",
    "prod_area_gdd_sum30": "Growing-area growing-degree-days, 30 days",
    "prod_area_clim_temp_avg10": "Growing-area normal temperature",
    "whsl_prc_prev_yr": "Wholesale price, same period last year",
    "arr_qty_prev_yr": "Arrivals, same period last year",
}
HEAD_EN = """# Wholesale auction price forecast - fill in 18 steps

You forecast agricultural wholesale prices. Using only the information below,
give the **auction price (KRW per kg) at Seoul Garak market for each of the
next 1 to 18 business days**.

## Rules

- **Use only the numbers given.** Do not bring in news or outside knowledge
- Dates are deliberately hidden. Do not try to guess when this is
- Give **18 numbers** per block (1 business day ahead ... 18 business days ahead)
- **Write no explanation.** Output only the lines in the format below
- **Each block is a different date.** Do not shift or copy a previous block's
  answer. Start fresh from that block's own starting point

## Output format

```
BlockID|day1,day2,day3,...,day18
```

Example (the numbers are only an example):

```
B01|812,818,825,830,833,840,845,848,850,855,858,860,862,865,868,870,872,875
```

**Give __N__ lines for all __N__ blocks. Write nothing else.**

## Notes - what these values mean

- **Starting point**: yesterday's price blended with the last 7-day mean.
  The answer is often near this. But leaving it unchanged is the same as
  doing nothing
- **Auction price**: the price struck at auction. Lower than wholesale and
  retail prices
- **Main growing-area station**: the weather station of the main growing
  area for that period
- Prices are KRW per kg; arrivals are in tonnes

---
"""


def fmt(v):
    if pd.isna(v):
        return "-"
    if isinstance(v, (int, np.integer)) or (isinstance(v, float) and float(v).is_integer()):
        return f"{int(v):,}"
    if isinstance(v, (float, np.floating)):
        return f"{v:,.1f}" if abs(v) >= 10 else f"{v:.3f}"
    return str(v)


def daily_series():
    """일별 경락가 원자료를 원천에서 뽑는다 (2026-09-02 추가).

    ## 왜 붙이나

    지금 LLM 이 보는 **경락가 과거가 2개뿐**이다 (3일 전 하루 · 최근 7일 평균).
    맞혀야 하는 값인데 중도매가(6개)보다 적게 준다. 이상한 자리다.

    그리고 5회 시험에서 **먼 날일수록 LLM 이 잘한다**고 나왔다
    (LT13~18 에서 LightGBM 대비 5.3% 앞섬). 먼 날을 본다는 건 큰 흐름을
    읽는다는 뜻이고, **흐름을 보려면 점 두 개보다 곡선**이 낫다.

    ## 왜 학습 CSV 가 아니라 원천에서 뽑나

    `target_auc_prc` 로 되살려 봤더니 **구멍이 있었다** — 품목당 2,343일인데
    원천은 2,928일이다 (25% 더 많음). 조사 축에 안 잡힌 거래일이 빠진다.
    구멍 난 곡선을 주면 "그날 거래가 없었다" 로 오해할 수 있다.

    ## ★ 새지 않는지 확인했다

    base_dt **직전 거래일**의 값이 `auc_prc_lag1` 과 같아야 한다.
    7,091건 대조 **완전일치 100%**.
    프롬프트에는 **base_dt 보다 엄격히 이전 날짜만** 넣는다.
    """
    import psycopg
    from score_predictions import dsn, ACTUAL_SQL
    with psycopg.connect(dsn(), connect_timeout=60) as c:
        s = pd.read_sql(ACTUAL_SQL["auc"], c)
    s["dt"] = pd.to_datetime(s.dt).astype("datetime64[ns]")
    s = s[s.item_nm.isin(ITEMS)].copy()
    s["p"] = s.prc.astype(float)
    return {it: g.sort_values("dt")[["dt", "p"]].reset_index(drop=True)
            for it, g in s.groupby("item_nm")}


def hist_lines(ser, item, base_dt, n):
    """base_dt 직전 n 거래일의 경락가를 최신순으로 준다.

    ★ 날짜를 안 쓴다. "며칠 전" 으로만 쓴다 — 날짜를 가린 것이 이 실험의
    핵심이기 때문이다.
    """
    g = ser.get(item)
    if g is None:
        return []
    b = pd.Timestamp(base_dt).normalize()
    h = g[g.dt < b].tail(n)                 # ★ 엄격히 이전만
    if h.empty:
        return []
    out = ["", f"### 최근 경락가 {len(h)}거래일 (맞혀야 하는 값의 과거)", ""]
    out.append("| 몇 거래일 전 | 경락가(원/kg) |")
    out.append("|---|---|")
    for k, (_, r) in enumerate(h.iloc[::-1].iterrows(), start=1):
        out.append(f"| {k} | {r.p:,.1f} |")
    return out


def fcst_table():
    """기상청 중기예보 — 기준일에 이미 손에 있는 **미래 정보** (2026-09-02).

    ## 왜 붙이나

    우리 입력 31개는 **전부 "무슨 일이 있었나"** 다. "무슨 일이 있을 것
    같나" 를 말해주는 것이 하나도 없다. 사용자가 "뉴스가 필수" 라고 한
    이유가 그 자리다.

    뉴스는 지금 못 구한다 (빅카인즈 외부 발급 불가 · 네이버 2026-07-31
    신규 중단 · KAMIS/가락/농넷은 전부 숫자). 게다가 구해도 **기준일
    이후 기사가 섞이면 답을 주는 것**이라 재기 어렵다.

    **중기예보는 셋 다 만족한다.**

        새지 않는다   기준일 06시 발표. 그 뒤 일은 안 들어간다
        과거가 있다   2015-01-01 ~ · 2017년 이후 발표일 3,530/3,530일 (100%)
        공짜다       이미 DB 에 있다 (477,837행)

    ## 단서

    `--with-fcst` 로 **LightGBM 에 숫자 컬럼으로 넣은 것은 2026-08-31 에
    기각**됐다. 여기서 다시 보는 것은 **LLM 에게 표로 주는 것**이고,
    그건 안 해봤다. 그리고 LLM 은 먼 날(LT13~18)에서 제일 잘하는데
    중기예보가 덮는 구간이 정확히 거기다.
    """
    import psycopg
    from score_predictions import dsn
    q = ("SELECT tm_fc::date AS fc, stn_nm, tm_ef::date AS ef, min_ta, max_ta "
         "FROM kma_mid_temp_raw WHERE tm_fc >= '2026-05-01'")
    with psycopg.connect(dsn(), connect_timeout=60) as c:
        f = pd.read_sql(q, c)
    f["fc"] = pd.to_datetime(f.fc).astype("datetime64[ns]")
    f["ef"] = pd.to_datetime(f.ef).astype("datetime64[ns]")
    #   (발표일, 지역, 대상일) → (최저, 최고)
    return {(r.fc, r.stn_nm, r.ef): (r.min_ta, r.max_ta) for r in f.itertuples()}


def news_table():
    """농업 전문지 기사 제목 — 기준일 **이전** 것만 (2026-09-02).

    ## 왜 붙이나

    우리 입력 31개는 전부 "무슨 일이 있었나" 다. **"앞으로 어떻게 될 것 같나"
    를 말해주는 것이 하나도 없다.** 기사에는 그게 있다.

        "배추 출하 감소 전망…봄배추 저장물량 많아 가격 상승 제한적"
        "배추·무·양배추 등 채소류 가격, 추석까지 약세 이어질 듯"

    ## ★ 새지 않게 하는 법

    기사는 **날짜별 목록 페이지**에서 받았다 (`데이터 수집/뉴스/`).
    날짜로 자르므로 기준일 이후 기사가 섞일 수 없다.

    여기서는 한 번 더 자른다 — **base_dt 보다 엄격히 이전** 기사만 쓴다.

    ## 단서 — 기사가 아주 적다

    실측(7일·두 매체): 품목+값 기사가 **하루 0.7건**이다. 대부분의 기준일에
    0건이다. **그래도 재본다** — 있는 날에만이라도 도움이 되는지는 재봐야
    안다. 세어보고 접는 것은 추정이지 실측이 아니다.
    """
    p = HERE.parents[2] / "데이터 수집" / "뉴스" / "output" / "agri_news.csv"
    if not p.exists():
        raise SystemExit(f"기사 파일이 없습니다: {p}\n"
                         "  데이터 수집/뉴스/fetch_agri_news.py 를 먼저 돌리세요.")
    d = pd.read_csv(p, encoding="utf-8-sig", parse_dates=["dt"])
    #   컬럼명이 dt 라 d.dt 는 pandas 의 날짜 접근자로 잡힌다.
    #   대괄호로 써야 컬럼을 가리킨다.
    d["dt"] = d["dt"].astype("datetime64[ns]")
    #   우리 품목·값에 관한 것만. '무' 는 한 글자라 무더위·무기질에 걸리므로
    #   앞뒤가 한글이 아닌 경우만 잡는다.
    pat = (r"배추|양파|김장|고랭지|(?<![가-힣])무(?![가-힣])|무값|총각무|"
           r"가락시장|경락|도매가|산지가|시세")
    d = d[d.title.str.contains(pat, regex=True, na=False)]
    return d.sort_values("dt")


def news_lines(nd, base_dt, days=21, cap=12):
    """기준일 직전 며칠치 기사 제목. ★ 날짜는 '며칠 전' 으로만 쓴다."""
    b = pd.Timestamp(base_dt).normalize()
    g = nd[(nd["dt"] < b) & (nd["dt"] >= b - pd.Timedelta(days=days))]
    if g.empty:
        return ["", f"### 최근 {days}일 농업 전문지 기사", "",
                "(관련 기사 없음)"]
    out = ["", f"### 최근 {days}일 농업 전문지 기사 ({len(g)}건)", "",
           "| 며칠 전 | 제목 |", "|---|---|"]
    for _, r in g.sort_values("dt", ascending=False).head(cap).iterrows():
        out.append(f"| {int((b - r['dt']).days)} | {r['title']} |")
    return out


def pick(va, n):
    """기준일을 고르게 뽑는다. 앞뒤로 몰리면 계절이 한쪽에 치우친다."""
    ds = sorted(va.base_dt.unique())
    if n >= len(ds):
        return ds
    idx = np.linspace(0, len(ds) - 1, n).round().astype(int)
    return [ds[i] for i in sorted(set(idx))]


def make(va, dates, tgt, anc, out, ser=None, hist=0, fc=None, en=False,
         items=None, nd=None):
    L = []
    if en:
        L.append(HEAD_EN)
    else:
        L.append("# 농산물 경락가 예측 — 18칸 맞히기\n")
        L.append("""당신은 농산물 도매가격을 예측합니다. 아래 정보만 보고
**앞으로 1~18 영업일 뒤의 서울 가락시장 경락가(원/kg)** 를 각각 맞히세요.

## 규칙

- **주어진 숫자만 쓰세요.** 뉴스나 외부 지식을 끌어오지 마세요
- 날짜는 일부러 가렸습니다. 언제인지 추측해서 쓰지 마세요
- 각 블록마다 **18개 숫자**를 냅니다 (1영업일 뒤 ~ 18영업일 뒤)
- **설명은 쓰지 마세요.** 아래 형식의 줄만 출력하세요
- ★ **블록마다 날짜가 다릅니다.** 앞 블록의 답을 밀거나 베껴 쓰지 마세요.
  블록마다 **그 블록의 출발점에서 새로 시작**하세요

## 출력 형식

```
블록번호|1일값,2일값,3일값,...,18일값
```

예시 (숫자는 예시일 뿐입니다):

```
B01|812,818,825,830,833,840,845,848,850,855,858,860,862,865,868,870,872,875
```

**__N__개 블록 전부에 대해 __N__줄을 내세요. 다른 말은 쓰지 마세요.**

## 참고 — 이 값들이 무슨 뜻인가

- **출발점**: 어제 가격과 최근 7일 평균을 섞은 값입니다.
  많은 경우 답은 이 근처입니다. 다만 그대로 두면 아무것도 안 한 것과 같습니다
- **경락가**: 경매에서 낙찰된 가격입니다. 중도매가·소매가보다 쌉니다
- **주산지 관측소**: 그 시기 주산지의 기상 관측소 이름입니다
- 가격 단위는 원/kg, 반입량은 톤입니다
- **예보 최저·최고**: 기상청이 오늘 아침에 낸 주산지 기온 예보입니다.
  아직 안 일어난 일에 대한 예보이지 실제 관측값이 아닙니다.
  **`-` 는 예보가 없다는 뜻입니다** (기상청 중기예보는 10일까지만 나옵니다).
  0도가 아닙니다

---
    """)

    blocks = []
    bno = 0
    for d in dates:
        for it in (items or ITEMS):
            g = va[(va.base_dt == d) & (va.item_nm == it)].sort_values("lead_biz_d")
            if g.empty or g[tgt].notna().sum() < 10:
                continue
            bno += 1
            bid = "B%02d" % bno
            blocks.append((bid, d, it, g))
            r0 = g.iloc[0]
            N = NICE_EN if en else NICE
            unit = "KRW/kg" if en else "원/kg"
            if en:
                L.append(f"\n## {bid} - **{ITEM_EN.get(it, it)}** - start {fmt(r0[anc])} KRW/kg\n")
                L.append("### Values fixed within this block\n")
                L.append("| Item | Value |")
            else:
                L.append(f"\n## {bid} · **{it}** · 출발점 {fmt(r0[anc])}원\n")
                L.append("### 이 블록에서 고정인 값\n")
                L.append("| 항목 | 값 |")
            L.append("|---|---|")
            L.append(f"| **{N['_anchor_mix']}** | **{fmt(r0[anc])} {unit}** |")
            for c in ["auc_prc_lag3", "auc_prc_avg7", "auc_prc_spread_lag1",
                      "auc_vol_lag1", "auc_whsl_ratio_lag1",
                      "whsl_prc_lag1", "whsl_prc_lag3", "whsl_prc_lag7",
                      "whsl_prc_avg7", "whsl_prc_avg14", "whsl_prc_std7",
                      "arr_qty_lag1", "arr_qty_avg7", "rtl_prc_lag1",
                      "market_temp_avg_lag1", "market_closed_lag1_yn"]:
                if c in g.columns:
                    L.append(f"| {N.get(c, c)} | {fmt(r0[c])} |")
            if ser is not None and hist:
                L += hist_lines(ser, it, d, hist)
            if nd is not None:
                L += news_lines(nd, d)
            L.append("\n### Values that change by horizon\n" if en
                     else "\n### 리드타임별로 달라지는 값\n")
            cols = [c for c in VARY if c in g.columns]
            head = [N.get(c, c) for c in cols]
            if fc:
                head += (["Forecast low", "Forecast high"] if en
                         else ["예보 최저", "예보 최고"])
            L.append(("| Days ahead | " if en else "| 며칠 뒤 | ")
                     + " | ".join(head) + " |")
            L.append("|---" * (len(head) + 1) + "|")
            for _, r in g.iterrows():
                cells = [(DOW_EN.get(str(r[c]), str(r[c])) if (en and c == "target_dow")
                          else fmt(r[c])) for c in cols]
                if fc:
                    #   ★ 기준일에 발표된 예보만 쓴다. 그 뒤 발표는 안 쓴다.
                    key = (pd.Timestamp(d).normalize(),
                           str(r.get("prod_area_stn_nm")),
                           pd.Timestamp(r.target_dt).normalize())
                    v = fc.get(key)
                    cells += [fmt(v[0]), fmt(v[1])] if v else ["-", "-"]
                L.append("| **%d** | " % int(r.lead_biz_d) + " | ".join(cells) + " |")
    L.append("\n---\n")
    L.append("**이제 __N__줄을 출력하세요. 설명 없이 `블록번호|숫자18개` 형식만.**\n")

    #   블록 수는 만들어 보기 전에는 모른다 (정답이 얇은 조합은 건너뛴다).
    #   그래서 자리표시자로 써두고 마지막에 채운다.
    Path(out).write_text("\n".join(L).replace("__N__", str(len(blocks))),
                         encoding="utf-8")
    key = pd.DataFrame([{"block": b, "base_dt": d, "item_nm": it}
                        for b, d, it, _ in blocks])
    key.to_csv(str(out).replace(".md", "_key.csv"), index=False, encoding="utf-8-sig")

    #   ★ 사용법은 프롬프트 **밖에** 둔다 (2026-09-02).
    #   안에 넣으면 답하는 쪽이 그것까지 읽어 다른 실험이 된다.
    #
    #   왜 생겼나: 2026-09-01 에 이 프롬프트를 새 대화창에 넣으면서 앞에
    #   "2026년 7월 1일~7월 18일 가격을 예측해줘" 를 붙였다.
    #     · 날짜를 가린 것이 풀렸다 — 그게 이 실험의 핵심이었다
    #     · 게다가 틀린 날짜였다. 실제는 6/1~8/10 에 걸쳐 있고
    #       30블록 중 7월 1~18일은 9개뿐이다
    #   안내를 안 쓴 것은 만든 쪽 잘못이라 파일로 남긴다.
    d0 = sorted({str(pd.Timestamp(d).date()) for _, d, _, _ in blocks})
    guide = f"""사용법 — {Path(out).name}

★ 파일을 **통째로 복사해 그대로만** 붙여넣으세요.
  앞이나 뒤에 아무 말도 더 쓰지 마세요.

  특히 **날짜를 알려주면 안 됩니다.** 날짜를 일부러 가린 것이 이 실험의
  핵심입니다. "숫자만 보고 얼마나 하나" 를 재는 것이라, 시기를 알려주면
  다른 실험이 됩니다.

★ **새 대화창**에서 하세요. 앞서 이 실험을 한 창에 이어서 물으면
  그때 답을 기억해 비슷하게 냅니다.

★ 나온 {len(blocks)}줄을 그대로 llm_answer.txt 에 저장하세요.

──────────────────────────────────────────────────────────
참고 — 블록이 실제로 어느 날인지 (★ 답하는 쪽에 알려주지 마세요)

  기준일 {len(d0)}개 · {d0[0]} ~ {d0[-1]}
  {' · '.join(d0)}

  한 시기에 몰려 있지 않습니다. 여러 달에 걸쳐 고르게 뽑았습니다.
"""
    Path(str(out).replace(".md", "_사용법.txt")).write_text(guide, encoding="utf-8")
    return blocks, key


def score(va, blocks, ans_path, tgt, anc, csv, alpha):
    """LLM 답을 실제값 · LightGBM · 앵커와 대조한다.

    ★ 셋을 **같은 행에서** 비교한다. LLM 이 못 낸 칸이 있으면 그 칸은
    셋 다 뺀다. 안 그러면 쉬운 칸만 남아 누구 하나가 유리해진다.
    """
    import lightgbm as lgb
    import train as T

    got = {}
    for line in Path(ans_path).read_text(encoding="utf-8").splitlines():
        line = line.strip().strip("`")
        if "|" not in line:
            continue
        b, rest = line.split("|", 1)
        try:
            vals = [float(x.replace(",", "").strip()) for x in rest.split(",")]
        except ValueError:
            continue
        if len(vals) >= 5:
            got[b.strip()] = vals
    print("[읽음] 블록 %d개 · 숫자 %d개" % (len(got), sum(len(v) for v in got.values())))
    if not got:
        sys.exit("답을 못 읽었습니다.")

    #   LightGBM 은 운영과 같은 조건으로 새로 학습한다 (학습 ~2025-12-31).
    #   시험 구간(2026-06~08)이 학습에 안 들어가야 공정하다.
    tr, va2, feats, cats, tgt2, anc2, _ = T_build(csv, alpha)
    P = dict(T.PARAMS)
    preds = []
    for sd_ in (42, 43, 44, 45, 46):
        p2 = dict(P, seed=sd_, bagging_seed=sd_, feature_fraction_seed=sd_)
        m = lgb.train(p2, lgb.Dataset(tr[feats], tr["y"], categorical_feature=cats),
                      num_boost_round=76)
        preds.append(m.predict(va2[feats]))
    va2 = va2.assign(lgbm=va2[anc2].to_numpy(float) * np.exp(np.mean(preds, axis=0)))
    look = {(r.base_dt, r.item_nm, int(r.lead_biz_d)): float(r.lgbm)
            for r in va2.itertuples()}

    rows = []
    for bid, d, it, g in blocks:
        if bid not in got:
            continue
        v = got[bid]
        for i, (_, r) in enumerate(g.iterrows()):
            if i >= len(v) or pd.isna(r[tgt]):
                continue
            k = (r.base_dt, it, int(r.lead_biz_d))
            if k not in look:
                continue
            rows.append(dict(block=bid, base_dt=r.base_dt, item_nm=it,
                             lead=int(r.lead_biz_d), actual=float(r[tgt]),
                             llm=v[i], lgbm=look[k], anchor=float(r[anc])))
    return pd.DataFrame(rows)


def T_build(csv, alpha):
    """시험 구간을 학습에서 뺀 LightGBM 을 만들기 위한 재료."""
    return build(csv, "auc", "2025-12-31", "2026-08-31", alpha)


def wm(a, p):
    a, p = np.asarray(a, float), np.asarray(p, float)
    return np.abs(a - p).sum() / np.abs(a).sum()


def report(d):
    if d.empty:
        sys.exit("채점할 행이 없습니다.")
    print("\n" + "=" * 74)
    print("[채점] %d행 · 블록 %d개 · 기준일 %d개"
          % (len(d), d.block.nunique(), d.base_dt.nunique()))
    print("  ※ 셋 다 같은 행에서 잽니다. LLM 이 못 낸 칸은 셋 다 뺐습니다")
    print("=" * 74)

    def tab(x, title):
        print("\n  [%s]  %d행" % (title, len(x)))
        print("    %-14s%10s%12s" % ("", "WMAPE", "앵커 대비"))
        b = wm(x.actual, x.anchor)
        for nm, col in [("앵커(단순평균)", "anchor"), ("LightGBM", "lgbm"), ("LLM", "llm")]:
            w = wm(x.actual, x[col])
            gain = "" if col == "anchor" else "%+9.1f%%" % ((1 - w / b) * 100)
            print("    %-14s%10.4f%12s" % (nm, w, gain))

    tab(d, "전체")
    tab(d[d.lead >= 3], "LT>=3 (운영 구간)")
    print("\n  [품목별 · LT>=3]")
    print("    %-6s%8s%10s%10s%10s%12s" % ("품목", "행수", "앵커", "LightGBM", "LLM", "LLM 대 앵커"))
    for it, x in d[d.lead >= 3].groupby("item_nm"):
        b = wm(x.actual, x.anchor)
        print("    %-6s%8d%10.4f%10.4f%10.4f%11.1f%%"
              % (it, len(x), b, wm(x.actual, x.lgbm), wm(x.actual, x.llm),
                 (1 - wm(x.actual, x.llm) / b) * 100))

    print("\n  [리드타임별 · WMAPE]")
    print("    %-6s%8s%10s%10s%10s" % ("LT", "행수", "앵커", "LightGBM", "LLM"))
    for lo, hi, nm in [(1, 2, "1~2"), (3, 6, "3~6"), (7, 12, "7~12"), (13, 18, "13~18")]:
        x = d[(d.lead >= lo) & (d.lead <= hi)]
        if x.empty:
            continue
        print("    %-6s%8d%10.4f%10.4f%10.4f"
              % (nm, len(x), wm(x.actual, x.anchor), wm(x.actual, x.lgbm),
                 wm(x.actual, x.llm)))

    #   LLM 이 앵커에서 얼마나 움직였나. 거의 안 움직였으면
    #   "앵커를 베낀 것" 이고, 그건 예측이 아니다.
    mv = (d.llm - d.anchor).abs() / d.anchor
    mv2 = (d.lgbm - d.anchor).abs() / d.anchor
    print("\n  [앵커에서 얼마나 움직였나] 예측값이 출발점과 얼마나 다른가")
    print("    LLM       평균 %.1f%% · 중앙 %.1f%%" % (mv.mean() * 100, mv.median() * 100))
    print("    LightGBM  평균 %.1f%% · 중앙 %.1f%%" % (mv2.mean() * 100, mv2.median() * 100))


def main() -> int:
    ap = argparse.ArgumentParser(description="LLM 예측 시험 프롬프트/채점")
    ap.add_argument("csv")
    ap.add_argument("--from", dest="d_from", default="2026-06-01")
    ap.add_argument("--to", dest="d_to", default="2026-08-31")
    ap.add_argument("--n-dates", type=int, default=12)
    ap.add_argument("--parts", type=int, default=1,
                    help="블록을 몇 개 파일로 나눌지. ★ 한 번에 너무 많으면 "
                         "답하는 쪽이 어느 블록인지 놓치고 앞 답을 밀어 쓴다 "
                         "(2026-09-02 실측: 배추 27블록 연속에서 발생)")
    ap.add_argument("--items", nargs="+", default=None,
                    help="이 품목만 낸다. 예: --items 배추. "
                         "★ 한 품목만 하면 같은 블록 수로 기준일을 3배 늘릴 수 있다 "
                         "— 표본이 얇은 것이 지금 제일 큰 약점이다")
    ap.add_argument("--en", action="store_true",
                    help="영어판. ★ 블록·숫자·순서는 완전히 같고 말만 영어다 "
                         "— 그래야 언어 효과만 잰다")
    ap.add_argument("--news", action="store_true",
                    help="농업 전문지 기사 제목을 붙인다. "
                         "★ 기준일보다 엄격히 이전 기사만 들어갑니다")
    ap.add_argument("--fcst", action="store_true",
                    help="기상청 중기예보(주산지 D+3~D+10 기온)를 붙인다. "
                         "★ 기준일에 발표된 것만 들어갑니다")
    ap.add_argument("--hist", type=int, default=0,
                    help="경락가 원자료를 몇 거래일치 붙일지 (0=안 붙임). "
                         "★ base_dt 보다 엄격히 이전 날만 들어갑니다")
    ap.add_argument("--out", default="../../../실험결과/llm_prompt.md")
    ap.add_argument("--score", default=None, help="LLM 답 파일 (채점만)")
    a = ap.parse_args()

    tr, va, feats, cats, tgt, anc, label = build(a.csv, "auc", "2025-12-31",
                                                 a.d_to, ALPHA)
    va = va[(va.base_dt >= pd.Timestamp(a.d_from)) & (va.lead_biz_d >= 1)].copy()
    print("[구간] %s ~ %s · 기준일 %d개 · %d행"
          % (a.d_from, a.d_to, va.base_dt.nunique(), len(va)))

    dates = pick(va, a.n_dates)
    ser = daily_series() if a.hist else None
    if ser:
        print("  [원자료] 일별 경락가 " + " · ".join(
            f"{k} {len(v):,}일" for k, v in ser.items()))
    fc = fcst_table() if a.fcst else None
    if fc:
        print("  [예보] 중기예보 %s건 (기준일 발표분만 씁니다)" % format(len(fc), ","))
    nd = news_table() if a.news else None
    if nd is not None:
        print("  [기사] 품목·값 관련 %s건 (%s ~ %s)"
              % (format(len(nd), ","), nd["dt"].min().date(),
                 nd["dt"].max().date()))
    blocks, key = make(va, dates, tgt, anc, a.out, ser, a.hist, fc, a.en,
                       a.items, nd)
    print("[프롬프트] 블록 %d개 → %s" % (len(blocks), a.out))
    print("           정답 키 → %s" % str(a.out).replace(".md", "_key.csv"))
    p = Path(a.out)
    print("           크기 %.0f KB · %d줄"
          % (p.stat().st_size / 1024, len(p.read_text(encoding='utf-8').splitlines())))

    if a.score:
        d0 = score(va, blocks, a.score, tgt, anc, a.csv, ALPHA)
        d0.to_csv(str(a.out).replace(".md", "_scored.csv"), index=False,
                  encoding="utf-8-sig")
        report(d0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
