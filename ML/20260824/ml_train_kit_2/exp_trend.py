# -*- coding: utf-8 -*-
"""검색량을 입력에 넣어본다 (2026-09-01)

## 왜

우리 모델 입력 44개가 **전부 공급 쪽**이다 (가격 이력 24 · 반입량 3 ·
기상 10 · 경제 3 · 기타 4). **수요를 재는 입력이 하나도 없다.**

검색은 기사보다 앞선다 — 기사는 값이 오른 **뒤에** 나오고,
검색은 사기 **전에** 한다.

## ★ 오늘 배운 규칙을 적용한다

같은 날 뉴스심리지수(NSI) 실험에서 **30일 평균이 성능을 깎았다.**

    셋 다 넣음(당일·30일평균·추세)   소매가 -0.0040  → 제거 판정
    당일값만 남김                    소매가 +0.0003  → 해로움 사라짐

30일 평균은 천천히 움직여 **값 하나로 시기를 알 수 있다.** 모델이
가격 예측 대신 연도 맞히기를 한다 (CLAUDE.md §5.2 의 더 날카로운 판).
중요도가 증거였다 — 느린 것 3.8~6.5% vs 빠른 것 1.1~2.4%.

**그래서 수준(level)을 아예 안 넣는다. 비율만 넣는다.**

    쓰는 것    오늘 ÷ 최근 7일 평균 · 오늘 ÷ 최근 30일 평균
               최근 7일 평균 ÷ 최근 30일 평균
    안 쓰는 것  수준 그대로 · 작년 대비

비율에는 "몇 년도인가" 가 남지 않는다. 그리고 구글 트렌드를 이어붙일 때
생기는 눈금 어긋남(8~12%)에도 휘둘리지 않는다 — 분자와 분모가 거의 같은
구간에 있기 때문이다. 자세한 것은 `trend_frame` 설명에.

## 시차

구글 트렌드는 하루 이틀 뒤에 확정된다. 운영에서 늘 손에 있으려면
**기준일 3일 전**까지만 쓴다. 미래 정보를 쓰면 검증에서만 잘 나온다.

## 판정

§5.7 그대로 — 폴드 두 개(검증 2023 · 검증 2022)에서 부호가 같고
합산이 편차×2 를 넘을 때만. 결과는 `실험결과/` 에만 남긴다.

## 쓰는 법

    python exp_trend.py <csv>
    python exp_trend.py <csv> --targets auc --seeds 42 43 44
    python exp_trend.py <csv> --per-item      # 품목별로도 본다 (§8)
"""
from __future__ import annotations

import argparse
import statistics as st
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import train as T                                            # noqa: E402
from exp_quantile import build                               # noqa: E402

TREND_CSV = (HERE.parents[2] / "데이터 수집" / "검색트렌드" / "output"
             / "google_trend_daily.csv")
ALPHA = {"auc": 0.4, "whsl": 0.8, "rtl": 1.0}
LAG = 3          # 기준일 3일 전까지만 쓴다
#   이어붙이기가 깨진 것은 뺀다 (위 trend_frame 설명 참조).
DROP_KW = ["gt_kimjang"]


def trend_frame():
    """검색량 → feature. **수준을 안 쓰고 비율만 쓴다.**

    이유가 두 가지다.

    **① 이어붙이기가 완벽하지 않다** (2026-09-01 검증).
    구글은 9개월을 넘기면 일별을 안 준다. 240일씩 끊어 60일 겹쳐 받고
    겹친 구간으로 눈금을 맞추는데, 오차가 조금씩 곱해져 쌓인다.

        기준선(한 번에 받은 월별)과 대조   양파 상관 0.83 · 어긋남 8.1%
                                          물가 상관 0.84 · 어긋남 12.4%
                                          김장 상관 0.66 · 어긋남  100%  ← 깨짐

    김장은 11~12월에만 검색돼 **겹친 구간이 통째로 0** 인 경우가 생기고,
    그러면 눈금을 못 맞춘 채 이어진다. **그래서 김장은 뺀다.**

    **② 수준은 시점 식별자가 된다** (같은 날 NSI 실험).
    천천히 움직이는 값은 그것 하나로 "몇 년도인가" 를 알려준다.

    **둘 다 비율로 풀린다.** '오늘 값 ÷ 최근 7일 평균' 은
    분자와 분모가 거의 같은 구간에 있어 눈금이 조금 밀려도 그대로다.
    그리고 수준이 없으니 연도를 알려주지도 않는다.

        쓰는 것    오늘 ÷ 최근 7일 평균 · 오늘 ÷ 최근 30일 평균
                   최근 7일 평균 ÷ 최근 30일 평균
        안 쓰는 것  수준 그대로 · 작년 대비(365일을 건너뛰어 어긋남이 그대로 탄다)

    **30일 평균을 분모로 쓰는 것은 NSI 때와 다르다.** 그때 문제였던 것은
    30일 평균을 **수준 그대로** 넣은 것이고, 여기서는 나눗셈의 분모라
    결과에 수준이 남지 않는다.
    """
    d = pd.read_csv(TREND_CSV, encoding="utf-8-sig", parse_dates=["dt"])
    d = d.sort_values("dt").set_index("dt").asfreq("D").ffill()
    d = d.drop(columns=[c for c in DROP_KW if c in d.columns])
    out = pd.DataFrame(index=d.index)
    for c in d.columns:
        s = d[c].shift(LAG)
        a7, a30 = s.rolling(7).mean(), s.rolling(30).mean()
        #   0 으로 나누지 않는다. 검색이 아예 없던 구간은 비울 뿐 1 로 채우지
        #   않는다 — 1 은 "평소와 같다" 는 뜻이라 없는 것과 다르다.
        out[f"{c}_rel7"] = np.where(a7 > 0, s / a7, np.nan)
        out[f"{c}_rel30"] = np.where(a30 > 0, s / a30, np.nan)
        out[f"{c}_trend"] = np.where(a30 > 0, a7 / a30, np.nan)
    return out.reset_index().rename(columns={"index": "base_dt", "dt": "base_dt"})


def wmape(a, p):
    a, p = np.asarray(a, float), np.asarray(p, float)
    return np.abs(a - p).sum() / np.abs(a).sum()


def run(tr, va, feats, cats, seeds, rounds, tgt, anc, item=None):
    ancv, actual = va[anc].to_numpy(float), va[tgt].to_numpy(float)
    m, ws = None, []
    for s in seeds:
        p = dict(T.PARAMS, seed=s, bagging_seed=s, feature_fraction_seed=s)
        m = lgb.train(p, lgb.Dataset(tr[feats], tr["y"], categorical_feature=cats),
                      num_boost_round=rounds)
        pr = ancv * np.exp(m.predict(va[feats]))
        if item is None:
            ws.append(wmape(actual, pr))
        else:
            k = (va.item_nm == item).to_numpy()
            ws.append(wmape(actual[k], pr[k]))
    return st.mean(ws), (st.pstdev(ws) if len(ws) > 1 else 0.0), m


def main() -> int:
    ap = argparse.ArgumentParser(description="검색량을 넣고 뺀 차이를 잰다")
    ap.add_argument("csv")
    ap.add_argument("--targets", nargs="+", default=["auc", "whsl", "rtl"])
    ap.add_argument("--seeds", nargs="+", type=int, default=[42, 43, 44])
    ap.add_argument("--rounds", type=int, default=76,
                    help="운영이 쓰는 값. 300 은 과적합 구간 (2026-09-01 실측)")
    ap.add_argument("--gate-lt", type=int, default=3)
    ap.add_argument("--per-item", action="store_true", help="품목별로도 본다")
    ap.add_argument("--only", nargs="+", default=None,
                    help="쓸 검색량 컬럼만 고른다 (예: gt_cabbage gt_cabbage_avg7)")
    a = ap.parse_args()

    if not TREND_CSV.exists():
        sys.exit(f"검색량 파일이 없습니다: {TREND_CSV}\n"
                 "  먼저 데이터 수집/검색트렌드/fetch_google_trend.py 를 돌리세요.")
    tf = trend_frame()
    cols = a.only or [c for c in tf.columns if c != "base_dt"]

    print("=" * 78)
    print("[검색량 실험] 구글 트렌드 · 일별 · 기준일 3일 전 시차")
    print(f"  넣는 컬럼 {len(cols)}개: " + ", ".join(cols[:6])
          + (" …" if len(cols) > 6 else ""))
    print(f"  트리 {a.rounds}그루 · 시드 {len(a.seeds)}개 · LT>={a.gate_lt}")
    print("  ※ 수준은 안 넣고 비율만 넣습니다 — 이어붙이기 어긋남과")
    print("     시점 식별자 함정을 둘 다 피하기 위해서입니다")
    print("=" * 78)

    verdict = {}
    for kind in a.targets:
        for tag, tend, vend in [("A(검증2023)", "2022-12-31", "2023-12-31"),
                                ("B(검증2022)", "2021-12-31", "2022-12-31")]:
            tr, va, feats, cats, tgt, anc, label = build(
                a.csv, kind, tend, vend, ALPHA[kind])
            tr = tr[tr.base_dt >= pd.Timestamp("2017-01-01")]
            va = va[va.lead_biz_d >= a.gate_lt].copy()
            tr = tr.merge(tf[["base_dt"] + cols], on="base_dt", how="left")
            va = va.merge(tf[["base_dt"] + cols], on="base_dt", how="left")
            miss = int(tr[cols].isna().any(axis=1).sum()
                       + va[cols].isna().any(axis=1).sum())

            w0, s0, _ = run(tr, va, feats, cats, a.seeds, a.rounds, tgt, anc)
            w1, s1, m1 = run(tr, va, feats + cols, cats, a.seeds, a.rounds, tgt, anc)
            d = w0 - w1                        # 양수면 넣는 게 낫다
            sd2 = 2 * max(s0, s1)
            mark = "O" if d > sd2 else ("X" if -d > sd2 else "ㅡ")
            verdict.setdefault(kind, []).append((tag, d, sd2, mark, label))

            print(f"\n  [{label} · 폴드 {tag}]  검증 {len(va):,}행 · 검색량 결측 {miss:,}행")
            print(f"    빼고  {w0:.4f} (시드편차 {s0:.4f})")
            print(f"    넣고  {w1:.4f} (시드편차 {s1:.4f})")
            print(f"    차이  {d:+.4f}   편차×2 {sd2:.4f}   판정 {mark}")
            imp = pd.Series(m1.feature_importance("gain"), index=feats + cols)
            tot = imp.sum()
            print(f"    검색량 중요도 합계 {imp[cols].sum()/tot*100:.1f}%  "
                  + " · ".join(f"{c} {imp[c]/tot*100:.1f}%"
                               for c in imp[cols].nlargest(3).index))

            if a.per_item:
                #   통합값은 가격이 높은 품목이 분모를 지배한다 (§8).
                print("    품목별:", end=" ")
                for it in ["배추", "무", "양파"]:
                    if not (va.item_nm == it).any():
                        continue
                    i0, _, _ = run(tr, va, feats, cats, a.seeds, a.rounds,
                                   tgt, anc, item=it)
                    i1, _, _ = run(tr, va, feats + cols, cats, a.seeds,
                                   a.rounds, tgt, anc, item=it)
                    print(f"{it} {i0 - i1:+.4f}", end="  ")
                print()

    print("\n" + "=" * 78)
    print("[2폴드 판정] 부호가 같고 합산이 편차×2 를 넘을 때만 채택합니다 (§5.7)")
    print("=" * 78)
    for kind, rs in verdict.items():
        tot = sum(r[1] for r in rs)
        need = max(r[2] for r in rs)
        same = len({np.sign(r[1]) for r in rs}) == 1
        ok = ("채택" if (same and tot > need)
              else "제거" if (same and -tot > need) else "판정 불가")
        print(f"  {rs[0][4]:<6} " + " · ".join(f"{r[0]} {r[1]:+.4f} {r[3]}" for r in rs)
              + f"  합산 {tot:+.4f} (필요 {need:.4f})  →  {ok}")
    print("\n  ※ 폴드가 갈리면 그해에 무슨 일이 있었는지 먼저 보세요.")
    print("    폴드 B 의 검증 2022 에는 태풍 힌남노(9/6)가 들어 있습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
