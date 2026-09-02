# -*- coding: utf-8 -*-
"""
학습량-성능 곡선
================
학습 시작일을 바꿔가며 성능을 측정한다.
"데이터를 더 모으면 나아지는가"에 대한 근거를 만든다.

사용법
    python learning_curve.py <csv경로>
    python learning_curve.py <csv경로> --train-end 2024-12-31

읽는 법
    기준일 수가 늘수록 개선율이 꾸준히 올라가면 → 데이터 확보가 답이다.
    들쭉날쭉하면 → 아직 표본이 적어 노이즈가 지배하는 구간이다.
"""
import argparse
import numpy as np
import pandas as pd
import lightgbm as lgb

from train import (TARGET, ANCHOR, DROP, CAT, PARAMS, wmape, load)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--train-end", default="2024-12-31")
    ap.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44])
    a = ap.parse_args()

    df = load(a.csv)
    df["y_ratio"] = np.log(df[TARGET] / df[ANCHOR])
    feats = [c for c in df.columns if c not in DROP | {"y_ratio"}]
    cats = [c for c in CAT if c in feats]

    tr_all = df[df.base_dt <= a.train_end]
    va = df[df.base_dt > a.train_end]
    bl = wmape(va[TARGET], va[ANCHOR])

    # 학습 시작 후보를 데이터 범위에서 자동 생성 (연 단위)
    y0, y1 = tr_all.base_dt.dt.year.min(), tr_all.base_dt.dt.year.max()
    starts = [f"{y}-01-01" for y in range(y1, y0 - 1, -1)]

    print(f"검증 {va.base_dt.min().date()} ~ {va.base_dt.max().date()}"
          f" · baseline {bl:.4f}\n")
    print(f"  {'학습시작':>12} {'기준일수':>9} {'행수':>9} {'WMAPE':>9} {'개선율':>9} {'표준편차':>9}")

    rows = []
    for s in starts:
        t = tr_all[tr_all.base_dt >= s]
        if t.base_dt.nunique() < 60:
            continue
        ws = []
        for seed in a.seeds:
            p = dict(PARAMS, seed=seed, bagging_seed=seed, feature_fraction_seed=seed)
            m = lgb.train(p, lgb.Dataset(t[feats], t.y_ratio, categorical_feature=cats),
                          num_boost_round=5000,
                          valid_sets=[lgb.Dataset(va[feats], va.y_ratio)],
                          callbacks=[lgb.early_stopping(200, verbose=False)])
            pr = va[ANCHOR].values * np.exp(m.predict(va[feats]))
            ws.append(wmape(va[TARGET], pr))
        mu, sd = np.mean(ws), np.std(ws, ddof=1)
        rows.append(dict(start=s, base_days=t.base_dt.nunique(), rows=len(t),
                         wmape=round(mu, 4), improve=round(1 - mu/bl, 4), std=round(sd, 4)))
        print(f"  {s:>12} {t.base_dt.nunique():9,} {len(t):9,} "
              f"{mu:9.4f} {(1-mu/bl)*100:+8.1f}% {sd:9.4f}")

    pd.DataFrame(rows).to_csv("learning_curve.csv", index=False)
    print("\n저장: learning_curve.csv")
    print("\n해석 도움말")
    print("  · 기준일 수가 늘수록 개선율이 단조 증가 → 데이터 확보가 효과적")
    print("  · 개선율이 오르내림 → 표본 부족으로 노이즈가 지배. 결과를 신뢰하지 말 것")
    print("  · 표준편차가 개선율과 비슷한 크기 → 차이가 유의하지 않음")


if __name__ == "__main__":
    main()
