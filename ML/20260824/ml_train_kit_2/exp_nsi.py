# -*- coding: utf-8 -*-
"""뉴스심리지수(NSI)를 입력에 넣어본다 (2026-09-01)

## 왜 이걸 하나

우리 입력 44개에 **수요를 재는 것이 하나도 없습니다.** 전부 공급 쪽입니다
(가격 이력 24 · 반입량 3 · 기상 10 · 경제 3 · 기타 4).

그리고 예전에 넣었다 뺀 경제 변수(M2·EPU·PPI)는 **월·분기 단위**라
한 달 내내 같은 값이 반복됐고, 모델이 그걸 시점 식별자로 오용했습니다
(CLAUDE.md §5.2).

## NSI 가 그 둘을 다르게 만족한다

    한국은행 뉴스심리지수   ECOS 523Y001 · 항목 A001
    만드는 법              경제 뉴스 문장을 긍정/부정으로 분류해 지수화
    주기                   **일별**            ← 월 단위 반복 함정 없음
    범위                   2005-01-01 ~        ← 학습 구간 전체를 덮음
                          2015~2026 하루도 안 빠짐 (4,261일 · 주말 포함)

**"언제부터 있냐" 가 날짜 이름표가 되는 함정**(학사일정 때 겪은 것)도 없습니다.

## 단서 두 개를 먼저 밝힌다

**① 여전히 기준일 단위입니다.** 대상일마다 값이 달라지지 않으므로 이미 있는
44개와 같은 성격입니다. 18줄 내내 같은 값이 하나 더 느는 것입니다.
**그래도 재는 이유는 44개가 못 재는 것(수요·심리)을 재기 때문입니다.**

**② 전국 경제 심리지 배추 심리가 아닙니다.** EPU 와 같은 약점입니다.
다른 점은 일별이라는 것뿐입니다. 그래서 기대치를 낮게 잡습니다.

## 시차를 왜 7일로 두나

한국은행이 **주 1회** ECOS 에 올립니다. 운영 시점에 기준일 당일 값은 없습니다.
`nsi_lag7`(기준일 7일 전)이면 실제로 늘 손에 있습니다.
**미래 정보를 쓰면 검증에서만 잘 나오고 운영에서 안 나옵니다.**

## 판정

§5.7 그대로 — 폴드 두 개에서 부호가 같고 합산이 편차×2 를 넘을 때만.
결과는 `실험결과/` 에만. `prediction_log` 에 넣지 않습니다.
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

NSI_CSV = HERE.parents[2] / "데이터 수집" / "경제 지표" / "output" / "nsi_daily.csv"
ALPHA = {"auc": 0.4, "whsl": 0.8, "rtl": 1.0}
NSI_COLS = ["nsi_lag7", "nsi_avg30", "nsi_chg30"]
#   --only-fast 는 30일 평균을 빼고 빠른 것만 남긴다.
#   30일 평균은 천천히 움직여 "몇 년 몇 월인가" 를 알려주기 좋다 —
#   §5.2 에서 경제 변수가 걸린 함정이 정확히 그것이었다.
FAST_ONLY = ["nsi_lag7"]


def nsi_frame():
    """기준일에 붙일 NSI 세 가지. 전부 기준일 7일 전까지만 쓴다."""
    d = pd.read_csv(NSI_CSV, encoding="utf-8-sig", parse_dates=["dt"])
    d = d.sort_values("dt").set_index("dt").asfreq("D").ffill()
    #   ffill 은 원래 결측이 없어 아무 일도 안 하지만, 원천이 바뀌어
    #   구멍이 생겨도 조용히 NaN 이 번지지 않게 둔다.
    out = pd.DataFrame(index=d.index)
    out["nsi_lag7"] = d.nsi.shift(7)
    out["nsi_avg30"] = d.nsi.shift(7).rolling(30).mean()
    #   추세: 최근 30일 평균 대비 지금 어디인가. 수준보다 변화가 신호일 수 있다.
    out["nsi_chg30"] = out.nsi_lag7 - out.nsi_avg30
    return out.reset_index().rename(columns={"index": "base_dt", "dt": "base_dt"})


def wmape(a, p):
    a, p = np.asarray(a, float), np.asarray(p, float)
    return np.abs(a - p).sum() / np.abs(a).sum()


def run(tr, va, feats, cats, seeds, rounds, tgt, anc):
    ancv, actual = va[anc].to_numpy(float), va[tgt].to_numpy(float)
    ws = []
    for s in seeds:
        p = dict(T.PARAMS, seed=s, bagging_seed=s, feature_fraction_seed=s)
        m = lgb.train(p, lgb.Dataset(tr[feats], tr["y"], categorical_feature=cats),
                      num_boost_round=rounds)
        ws.append(wmape(actual, ancv * np.exp(m.predict(va[feats]))))
    return st.mean(ws), (st.pstdev(ws) if len(ws) > 1 else 0.0), m


def main() -> int:
    ap = argparse.ArgumentParser(description="뉴스심리지수를 넣고 뺀 차이를 잰다")
    ap.add_argument("csv")
    ap.add_argument("--targets", nargs="+", default=["auc", "whsl", "rtl"])
    ap.add_argument("--seeds", nargs="+", type=int, default=[42, 43, 44, 45, 46])
    ap.add_argument("--rounds", type=int, default=76,
                    help="운영이 쓰는 값. 300 은 과적합 구간이다 (2026-09-01 실측)")
    ap.add_argument("--gate-lt", type=int, default=3)
    ap.add_argument("--only-fast", action="store_true",
                    help="30일 평균을 빼고 nsi_lag7 만 쓴다 (시점 식별자 가설 검증)")
    a = ap.parse_args()

    cols = FAST_ONLY if a.only_fast else NSI_COLS
    nsi = nsi_frame()
    print("=" * 76)
    print("[뉴스심리지수 실험] 한국은행 ECOS 523Y001 · 일별 · 기준일 7일 전 시차")
    print(f"  트리 {a.rounds}그루 · 시드 {len(a.seeds)}개 · LT>={a.gate_lt}")
    print("=" * 76)

    verdict = {}
    for kind in a.targets:
        for tag, tend, vend in [("A(검증2023)", "2022-12-31", "2023-12-31"),
                                ("B(검증2022)", "2021-12-31", "2022-12-31")]:
            tr, va, feats, cats, tgt, anc, label = build(
                a.csv, kind, tend, vend, ALPHA[kind])
            tr = tr[tr.base_dt >= pd.Timestamp("2017-01-01")]
            va = va[va.lead_biz_d >= a.gate_lt].copy()
            tr = tr.merge(nsi, on="base_dt", how="left")
            va = va.merge(nsi, on="base_dt", how="left")
            miss = tr[cols].isna().any(axis=1).sum() + va[cols].isna().any(axis=1).sum()

            w0, s0, _ = run(tr, va, feats, cats, a.seeds, a.rounds, tgt, anc)
            w1, s1, m1 = run(tr, va, feats + cols, cats, a.seeds, a.rounds, tgt, anc)

            d = w0 - w1                       # 양수면 넣는 게 낫다
            sd2 = 2 * max(s0, s1)
            mark = "O" if d > sd2 else ("X" if -d > sd2 else "ㅡ")
            verdict.setdefault(kind, []).append((tag, d, sd2, mark, label))
            print(f"\n  [{label} · 폴드 {tag}]  검증 {len(va):,}행 · NSI 결측 {miss}행")
            print(f"    빼고  {w0:.4f} (시드편차 {s0:.4f})")
            print(f"    넣고  {w1:.4f} (시드편차 {s1:.4f})")
            print(f"    차이  {d:+.4f}   편차×2 {sd2:.4f}   판정 {mark}")
            imp = pd.Series(m1.feature_importance("gain"), index=feats + cols)
            share = imp[cols].sum() / imp.sum() * 100
            print(f"    NSI {len(cols)}개의 중요도 합계 {share:.1f}%  "
                  + " · ".join(f"{c} {imp[c]/imp.sum()*100:.1f}%" for c in cols))

    print("\n" + "=" * 76)
    print("[2폴드 판정] 부호가 같고 합산이 편차×2 를 넘을 때만 채택합니다 (§5.7)")
    print("=" * 76)
    for kind, rs in verdict.items():
        tot = sum(r[1] for r in rs)
        need = max(r[2] for r in rs)
        same = len({np.sign(r[1]) for r in rs}) == 1
        ok = "채택" if (same and tot > need) else ("제거" if (same and -tot > need) else "판정 불가")
        print(f"  {rs[0][4]:<6} " + " · ".join(f"{r[0]} {r[1]:+.4f} {r[3]}" for r in rs)
              + f"  합산 {tot:+.4f} (필요 {need:.4f})  →  {ok}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
