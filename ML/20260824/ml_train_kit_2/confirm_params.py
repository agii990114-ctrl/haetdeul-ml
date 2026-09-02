# -*- coding: utf-8 -*-
"""오토리서치가 찾은 조절값을 시드를 늘려 재확인한다 (2026-09-02)

## 왜 따로 하나

탐색은 시드 5개로 돌렸다. 그건 **빠르게 훑기 위한 것**이지 채택 근거가
아니다. 우리 규칙은 "개선율이 시드 표준편차의 2배를 넘어야" 인데,
시드가 적으면 그 표준편차 자체가 부정확하다.

**그리고 세 폴드를 다 본다.** 탐색에는 A·B 만 썼고 C 는 마지막에 한 번만
봤다. 채택 전에는 셋 다 같은 시드로 다시 잰다.

## 쓰는 법

    python confirm_params.py <csv> --target auc --seeds 20
"""
from __future__ import annotations

import argparse
import json
import statistics as st
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import train as T                                            # noqa: E402
from auto_research import (FOLDS, FOLD_C, ITEMS, OPS, Data,   # noqa: E402
                           evaluate)

#   오토리서치가 찾은 것 (2026-09-02 · 198회 중 1회 채택 · 확인 폴드 통과)
FOUND = {
    "auc": {"n_round": 50, "learning_rate": 0.03, "num_leaves": 45,
            "min_data_in_leaf": 60, "feature_fraction": 0.5,
            "bagging_fraction": 0.7, "lambda_l2": 30.0},
}


def main() -> int:
    ap = argparse.ArgumentParser(description="찾은 조절값을 시드를 늘려 확인한다")
    ap.add_argument("csv")
    ap.add_argument("--target", default="auc", choices=list(OPS))
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--params", default=None, help="JSON 으로 직접 주기")
    a = ap.parse_args()

    cand = json.loads(a.params) if a.params else FOUND.get(a.target)
    if not cand:
        raise SystemExit(f"{a.target} 에 대해 찾은 설정이 없습니다. --params 로 주세요.")
    alpha, ops_round = OPS[a.target]
    seeds = list(range(42, 42 + a.seeds))
    start = {k: T.PARAMS[k] for k in cand if k in T.PARAMS}
    start["n_round"] = ops_round

    print("=" * 76)
    print(f"[재확인] {a.target} · 시드 {a.seeds}개 · 세 폴드 전부")
    print("  탐색은 시드 5개였습니다. 그건 훑기용이지 채택 근거가 아닙니다")
    print("=" * 76)
    print("  지금  " + json.dumps(start, ensure_ascii=False))
    print("  찾은  " + json.dumps(cand, ensure_ascii=False))

    data = Data(a.csv, a.target, alpha, "2017-01-01", 3)
    tags = tuple(FOLDS) + ("C",)
    b = evaluate(data, start, seeds, tags=tags)
    c = evaluate(data, cand, seeds, tags=tags)

    print(f"\n  {'폴드':<12}{'지금':>10}{'찾은 것':>10}{'개선':>10}{'편차×2':>10}  판정")
    tot_g = []
    for t, nm in zip(tags, ["A(검증2023)", "B(검증2022)", "C(검증2021)★"]):
        x, y = b[t]["tot"], c[t]["tot"]
        g = st.mean(x) - st.mean(y)
        need = 2 * max(st.pstdev(x), st.pstdev(y))
        mk = "O 좋아짐" if g > need else ("X 나빠짐" if -g > need else "ㅡ")
        tot_g.append(g)
        print(f"  {nm:<12}{st.mean(x):>10.4f}{st.mean(y):>10.4f}{g:>+10.4f}{need:>10.4f}  {mk}")
    print(f"  {'합산':<12}{'':>10}{'':>10}{sum(tot_g):>+10.4f}")

    print(f"\n  [품목별] ★ 통합만 보면 한 품목이 무너져도 모릅니다 (§8)")
    print(f"  {'품목':<6}{'폴드':<12}{'지금':>10}{'찾은 것':>10}{'개선':>10}  판정")
    for i in ITEMS:
        gs = []
        for t, nm in zip(tags, ["A", "B", "C★"]):
            x, y = b[t]["per"][i], c[t]["per"][i]
            if not x or not y:
                continue
            g = st.mean(x) - st.mean(y)
            need = 2 * max(st.pstdev(x), st.pstdev(y))
            gs.append(g)
            mk = "O" if g > need else ("X" if -g > need else "ㅡ")
            print(f"  {i:<6}{nm:<12}{st.mean(x):>10.4f}{st.mean(y):>10.4f}{g:>+10.4f}  {mk}")
        print(f"  {'':<6}{'합산':<12}{'':>10}{'':>10}{sum(gs):>+10.4f}")
    print("\n  ※ 채택하면 밴드(예측 구간)도 다시 만들어야 합니다 — 모델과 짝입니다.")
    print("  ※ 분위수 교체와 동시에 바꾸지 마세요. 무엇이 효과인지 모르게 됩니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
