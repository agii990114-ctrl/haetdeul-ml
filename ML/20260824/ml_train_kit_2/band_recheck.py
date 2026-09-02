# -*- coding: utf-8 -*-
"""밴드 적중률 재측정 (2026-09-01)

## 왜 다시 재나

8/28 에 매입 파트에 준 품목별 밴드 적중률(배추 80.0 · 무 80.4 · 양파 69.7)이
`prediction_log` 에서 나왔습니다. 그 표에 실험 백테스트가 섞여 있던 것이
2026-09-01 에 드러났고, 오차 수치는 이미 정정했습니다.
**적중률도 같은 표본이었는지 확인이 필요합니다** (매입 파트 문의).

## 출처를 바꿉니다

    쓰던 것   prediction_log  (ops_* 와 ops-* 등이 섞임)
    쓸 것     실험결과/holdout_auc_pred.csv
              봉인 개봉 실행 출력 · 운영 구성 · 486 기준일 · 2024~2025

밴드는 `ref_prediction_band` 고정표를 예측값에 곱해 만듭니다.
운영 `predict.py` 와 같은 방식입니다.

## 같이 내는 것 — s 범위별 임계표

매입 파트가 s(매입 단가 ÷ 총 변동원가)를 아직 못 냈습니다.
s 가 정해지면 허용 오차 δ 는 δ = 4.7% / s 입니다.
**s 를 모르는 채로 읽을 수 있게 δ 를 축으로 표를 냅니다.**
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from score_predictions import dsn                             # noqa: E402

CSV = HERE.parents[2] / "실험결과" / "holdout_auc_pred.csv"

#   ★ 머리글과 값이 어긋나지 않게 순서를 한 곳에서만 정한다.
#   groupby 는 무·배추·양파 순으로 묶는다. 머리글을 따로 쓰면 반드시 틀린다.
ITEMS = ["배추", "무", "양파"]


def load():
    d = pd.read_csv(CSV, encoding="utf-8-sig",
                    parse_dates=["base_dt", "target_dt"])
    with psycopg.connect(dsn(), connect_timeout=25) as c:
        b = pd.read_sql("""SELECT item_nm, lead_biz_d, ratio_q10, ratio_q50, ratio_q90
                           FROM ref_prediction_band WHERE target_kind = 'auc'""", c)
    m = d.merge(b, on=["item_nm", "lead_biz_d"], how="left")
    miss = m.ratio_q10.isna().sum()
    if miss:
        print(f"  ※ 밴드가 없는 행 {miss:,}개는 빼고 잽니다")
        m = m[m.ratio_q10.notna()]
    return m


def main():
    d = load()
    d["lo"] = d.pred * d.ratio_q10
    d["hi"] = d.pred * d.ratio_q90
    d["hit"] = (d.target_auc_prc >= d.lo) & (d.target_auc_prc <= d.hi)
    #   실제가 예측보다 얼마나 "비쌌나". 싼 쪽은 마진이 늘어나므로 안 센다.
    d["over"] = (d.target_auc_prc - d.pred) / d.pred

    g = d[d.lead_biz_d >= 3]
    print("=" * 70)
    print("[밴드 적중률 재측정] 경락가 · 운영 모델 · 홀드아웃 2024~2025")
    print(f"  {g.base_dt.nunique()} 기준일 · {len(g):,}행 (LT>=3)")
    print("=" * 70)
    print(f"  {'품목':<6}{'행수':>8}{'평균실제가':>11}{'평균오차':>10}"
          f"{'적중률':>9}{'평균폭':>9}   (8/28 에 준 적중률)")
    old = {"배추": 80.0, "무": 80.4, "양파": 69.7}
    for it in ITEMS:
        x = g[g.item_nm == it]
        w = ((x.hi - x.lo) / x.pred).mean()
        mape = (x.target_auc_prc - x.pred).abs().sum() / x.target_auc_prc.abs().sum()
        print(f"  {it:<6}{len(x):>8,}{x.target_auc_prc.mean():>10,.0f}원"
              f"{mape*100:>9.1f}%{x.hit.mean()*100:>8.1f}%{w*100:>8.0f}%"
              f"   {old[it]:>6.1f}%")
    print(f"  {'전체':<6}{len(g):>8,}{g.hit.mean()*100:>8.1f}%")

    #   D+14 = 영업일 9~10 (매입 파트 축과 대응).
    print("\n" + "=" * 70)
    print("[s 범위별 임계표] 실제가 예측보다 δ 넘게 비쌌던 비율 · D+14(LT 9~10)")
    print("  δ = 4.7% ÷ s   ·   s = 매입 단가 ÷ 총 변동원가")
    print("=" * 70)
    h = d[d.lead_biz_d.isin([9, 10])]
    ss = [1.0, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3]
    print(f"  {'s':>5}{'δ':>8}   " + "".join(f"{i:>8}" for i in ITEMS)
          + f"{'전체':>8}")
    for s in ss:
        dl = 0.047 / s
        row = "".join(f"{(h[h.item_nm == i].over > dl).mean()*100:>7.0f}%"
                      for i in ITEMS)
        print(f"  {s:>5.1f}{dl*100:>7.1f}%   {row}{(h.over > dl).mean()*100:>7.0f}%")

    print("  ※ 각 칸은 '10번 중 몇 번 버퍼가 깨지나' 입니다. 낮을수록 좋습니다.")

    #   리드타임을 줄이면 나아지나 — 매입 파트가 막혔다고 한 길.
    print("\n" + "=" * 70)
    print("[리드타임을 줄이면] δ=4.7% (s=1.0) 기준 초과 비율")
    print("=" * 70)
    print(f"  {'LT':>4}{'(D+)':>6}   " + "".join(f"{i:>8}" for i in ITEMS)
          + f"{'전체':>8}")
    for lt, dplus in [(3, 5), (5, 7), (7, 11), (9, 14), (12, 18), (15, 21), (18, 26)]:
        x = d[d.lead_biz_d == lt]
        if x.empty:
            continue
        row = "".join(f"{(x[x.item_nm == i].over > 0.047).mean()*100:>7.0f}%"
                      for i in ITEMS)
        print(f"  {lt:>4}{dplus:>6}   {row}{(x.over > 0.047).mean()*100:>7.0f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
