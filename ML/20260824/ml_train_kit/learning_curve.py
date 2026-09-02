# -*- coding: utf-8 -*-
"""
학습량-성능 곡선
================
학습 시작일을 바꿔가며 성능을 측정한다.
"데이터를 더 모으면 나아지는가" 에 대한 근거를 만든다.

사용법
    python learning_curve.py <csv경로> --target auc --train-end 2022-12-31
    python learning_curve.py <csv경로> --items 배추 양파 무
    python learning_curve.py <csv경로> --by-item        품목별로 따로 그린다

읽는 법
    · 기준일 수가 늘수록 개선율이 단조 증가 → 데이터 확보가 효과적
    · 개선율이 오르내림 → 표본 부족으로 노이즈가 지배
    · 표준편차가 개선율과 비슷한 크기 → 차이가 유의하지 않음

주의
    통합 개선율은 가격 수준이 높은 품목이 분모를 지배해 착시를 만든다.
    품목이 여럿이면 --by-item 으로 확인할 것.
"""
import argparse

import numpy as np
import pandas as pd
import lightgbm as lgb

from train import (TARGETS, DROP, CAT, PARAMS, DEFAULT_ITEMS, wmape, load)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--target", choices=list(TARGETS), default="whsl",
                    help="auc=경락가 · whsl=중도매가 · rtl=소매가")
    ap.add_argument("--train-end", default="2022-12-31")
    ap.add_argument("--items", nargs="+", default=DEFAULT_ITEMS)
    ap.add_argument("--by-item", action="store_true",
                    help="품목별로 곡선을 따로 그린다")
    ap.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44])
    a = ap.parse_args()

    target, anchor, label = TARGETS[a.target]
    print(f"[타겟] {label}  ({target} / 앵커 {anchor})")

    df = load(a.csv, target=target, anchor=anchor)

    all_items = sorted(df.item_nm.astype(str).unique())
    keep = [i for i in a.items if i in all_items]
    dropped = [i for i in all_items if i not in keep]
    if not keep:
        raise SystemExit(f"선택한 품목이 없습니다. 존재: {all_items}")
    df = df[df.item_nm.astype(str).isin(keep)].copy()
    print(f"[품목] {keep}" + (f" · 제외 {dropped}" if dropped else ""))

    df["y_ratio"] = np.log(df[target] / df[anchor])
    feats = [c for c in df.columns
             if c not in DROP | {"y_ratio", target, anchor} or c == anchor]
    feats = [c for c in df.columns if c not in DROP | {"y_ratio"}]
    cats = [c for c in CAT if c in feats]

    tr_all = df[df.base_dt <= a.train_end]
    va = df[df.base_dt > a.train_end]
    if va.empty:
        raise SystemExit("검증 구간이 비었습니다. --train-end 를 확인하세요.")

    print(f"검증 {va.base_dt.min().date()} ~ {va.base_dt.max().date()}"
          f" · 고유 기준일 {va.base_dt.nunique():,}")

    y0, y1 = tr_all.base_dt.dt.year.min(), tr_all.base_dt.dt.year.max()
    starts = [f"{y}-01-01" for y in range(y1, y0 - 1, -1)]

    # 품목별 baseline (통합 착시 방지)
    base_item = {it: wmape(g[target], g[anchor])
                 for it, g in va.groupby("item_nm", observed=True)}
    bl_all = wmape(va[target], va[anchor])
    print("\n[baseline]")
    for it, v in base_item.items():
        print(f"  {str(it):<6} {v:.4f}")
    print(f"  {'통합':<6} {bl_all:.4f}   ※ 참고용")

    hdr = f"\n  {'학습시작':>12} {'기준일수':>9} {'행수':>9} {'WMAPE':>9} {'개선율':>9} {'표준편차':>9}"
    if a.by_item:
        hdr += "".join(f"{str(it):>9}" for it in base_item)
    print(hdr)

    rows = []
    for s in starts:
        t = tr_all[tr_all.base_dt >= s]
        if t.base_dt.nunique() < 60:
            continue
        preds = []
        for seed in a.seeds:
            p = dict(PARAMS, seed=seed, bagging_seed=seed, feature_fraction_seed=seed)
            m = lgb.train(p, lgb.Dataset(t[feats], t.y_ratio, categorical_feature=cats),
                          num_boost_round=5000,
                          valid_sets=[lgb.Dataset(va[feats], va.y_ratio)],
                          callbacks=[lgb.early_stopping(200, verbose=False)])
            preds.append(va[anchor].values * np.exp(m.predict(va[feats])))

        ws = [wmape(va[target], p) for p in preds]
        mu, sd = np.mean(ws), np.std(ws, ddof=1)
        ens = np.mean(preds, axis=0)

        row = dict(start=s, base_days=t.base_dt.nunique(), rows=len(t),
                   wmape=round(mu, 4), improve=round(1 - mu / bl_all, 4),
                   std=round(sd, 4))
        line = (f"  {s:>12} {t.base_dt.nunique():9,} {len(t):9,} "
                f"{mu:9.4f} {(1-mu/bl_all)*100:+8.1f}% {sd:9.4f}")

        if a.by_item:
            tmp = va.copy(); tmp["pred"] = ens
            for it, g in tmp.groupby("item_nm", observed=True):
                imp = 1 - wmape(g[target], g.pred) / base_item[it]
                row[f"imp_{it}"] = round(imp, 4)
                line += f"{imp*100:+8.1f}%"
        rows.append(row)
        print(line)

    pd.DataFrame(rows).to_csv("learning_curve.csv", index=False)
    print("\n저장: learning_curve.csv")
    print("\n해석 도움말")
    print("  · 기준일 수가 늘수록 개선율이 단조 증가 → 데이터 확보가 효과적")
    print("  · 개선율이 오르내림 → 표본 부족으로 노이즈가 지배")
    print("  · 표준편차가 개선율과 비슷한 크기 → 차이가 유의하지 않음")
    if not a.by_item and len(base_item) > 1:
        print("  · 통합 개선율은 가격 수준이 높은 품목이 분모를 지배한다.")
        print("    --by-item 으로 품목별 곡선을 확인할 것.")


if __name__ == "__main__":
    main()
