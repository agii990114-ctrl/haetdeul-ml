# -*- coding: utf-8 -*-
"""모델 비교 — LightGBM · XGBoost · CatBoost (2026-09-01)

## 무엇을 하나

**같은 재료로 부스팅 종류만 바꿔** 성능을 비교한다.
feature · 앵커 변환 · 학습 구간 · 시드 · baseline 전부 같다.

## 기대치는 낮다 — 먼저 밝혀 둔다

2026-08-31 에 feature 실험 넷을 했고 전부 기각됐다. 이유가 같았다.

    모델 입력 28개 중 17개가 한 기준일 안에서 전부 같은 값
    18행 내내 진짜로 움직이는 입력의 중요도 합계 22.4%

**입력에 정보가 없으면 모델을 바꿔도 안 나온다.** 그래도 재는 이유는
"부스팅 종류는 봤나" 에 답이 필요하고, 안 해보면 모르기 때문이다.

## 판정

**§5.7 그대로** — 폴드 두 개(검증 2023 · 검증 2022)에서 부호가 같고
합산이 편차×2 를 넘을 때만 채택한다. 한 폴드로 결정하지 않는다.

## 쓰는 법

    python exp_models.py <csv> --target auc --valid-end 2023-12-31
    python exp_models.py <csv> --target auc --train-end 2021-12-31 --valid-end 2022-12-31

결과는 `실험결과/` 에만 남긴다. **`prediction_log` 에 넣지 않는다.**
"""
from __future__ import annotations

import argparse
import statistics as st
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import train as T                                            # noqa: E402
from exp_quantile import build                               # noqa: E402

ALPHA_BY_TARGET = {"auc": 0.4, "whsl": 0.8, "rtl": 1.0}


def wmape(a, p):
    a, p = np.asarray(a, float), np.asarray(p, float)
    return np.abs(a - p).sum() / np.abs(a).sum()


def run_lgb(tr, va, feats, cats, seed, rounds):
    import lightgbm as lgb
    p = dict(T.PARAMS, seed=seed, bagging_seed=seed, feature_fraction_seed=seed)
    m = lgb.train(p, lgb.Dataset(tr[feats], tr["y"], categorical_feature=cats),
                  num_boost_round=rounds)
    return m.predict(va[feats])


def run_xgb(tr, va, feats, cats, seed, rounds):
    """XGBoost. **범주형은 따로 다뤄야 한다** — LightGBM 처럼 이름만 주면 안 된다."""
    import xgboost as xgb
    X, V = tr[feats].copy(), va[feats].copy()
    for c in cats:
        X[c] = X[c].astype("category")
        #   검증에 학습에 없던 값이 있으면 XGBoost 가 터진다. 범주를 맞춘다.
        V[c] = pd.Categorical(V[c], categories=X[c].cat.categories)
    m = xgb.XGBRegressor(
        objective="reg:absoluteerror", n_estimators=rounds, learning_rate=0.03,
        max_leaves=31, subsample=0.8, colsample_bytree=0.8,
        min_child_weight=60, reg_lambda=1.0, random_state=seed,
        enable_categorical=True, tree_method="hist", verbosity=0)
    m.fit(X, tr["y"])
    return m.predict(V)


def run_cat(tr, va, feats, cats, seed, rounds):
    """CatBoost. 범주형을 문자열로 넘긴다 (결측은 빈 문자열)."""
    from catboost import CatBoostRegressor, Pool
    X, V = tr[feats].copy(), va[feats].copy()
    for c in cats:
        X[c] = X[c].astype(str).fillna("")
        V[c] = V[c].astype(str).fillna("")
    idx = [feats.index(c) for c in cats]
    m = CatBoostRegressor(loss_function="MAE", iterations=rounds,
                          learning_rate=0.03, depth=6, l2_leaf_reg=1.0,
                          random_seed=seed, verbose=0, allow_writing_files=False)
    m.fit(Pool(X, tr["y"], cat_features=idx))
    return m.predict(Pool(V, cat_features=idx))


MODELS = {"LightGBM": run_lgb, "XGBoost": run_xgb, "CatBoost": run_cat}


def main() -> int:
    ap = argparse.ArgumentParser(description="부스팅 종류를 바꿔 비교한다")
    ap.add_argument("csv")
    ap.add_argument("--target", default="auc", choices=["auc", "whsl", "rtl"])
    ap.add_argument("--train-start", default="2017-01-01")
    ap.add_argument("--train-end", default="2022-12-31")
    ap.add_argument("--valid-end", default="2023-12-31")
    ap.add_argument("--seeds", nargs="+", type=int, default=[42, 43, 44])
    ap.add_argument("--rounds", type=int, default=300)
    ap.add_argument("--gate-lt", type=int, default=3)
    ap.add_argument("--only", nargs="+", default=None, help="일부만 돌린다")
    a = ap.parse_args()

    alpha = ALPHA_BY_TARGET[a.target]
    tr, va, feats, cats, tgt, anc, label = build(
        a.csv, a.target, a.train_end, a.valid_end, alpha)
    tr = tr[tr.base_dt >= pd.Timestamp(a.train_start)]
    va = va[va.lead_biz_d >= a.gate_lt].copy()

    print("=" * 74)
    print(f"[모델 비교] {label} · 앵커 α={alpha} · 검증 ~{a.valid_end}")
    print(f"  학습 {len(tr):,}행 · 검증 {len(va):,}행 (LT>={a.gate_lt}) · "
          f"feature {len(feats)}개 · 시드 {len(a.seeds)}개 · 트리 {a.rounds}그루")
    print("=" * 74)

    ancv = va[anc].to_numpy(float)
    actual = va[tgt].to_numpy(float)
    #   앵커 자체가 baseline 이다 (모델이 0을 내면 앵커가 그대로 나온다).
    #   ★ 이게 최선의 baseline 인지는 별개 질문이다 (§11 · 백로그 M-15).
    base = wmape(actual, ancv)

    names = a.only or list(MODELS)
    out = {}
    print(f"  {'모델':<10}{'WMAPE':>9}{'시드편차':>10}{'앵커대비':>10}{'시간':>8}")
    for nm in names:
        fn = MODELS.get(nm)
        if fn is None:
            print(f"  {nm}: 그런 모델이 없습니다")
            continue
        t0 = time.time()
        ws = []
        for s in a.seeds:
            try:
                pr = fn(tr, va, feats, cats, s, a.rounds)
            except Exception as e:                            # noqa: BLE001
                print(f"  {nm:<10} 실패: {type(e).__name__}: {str(e)[:60]}")
                ws = []
                break
            ws.append(wmape(actual, ancv * np.exp(pr)))
        if not ws:
            continue
        m = st.mean(ws)
        sd = st.pstdev(ws) if len(ws) > 1 else 0.0
        out[nm] = (m, sd)
        print(f"  {nm:<10}{m:>9.4f}{sd:>10.4f}{(1-m/base)*100:>9.1f}%"
              f"{time.time()-t0:>7.0f}초")

    print(f"\n  앵커(baseline)  {base:.4f}")
    if len(out) > 1:
        best = min(out, key=lambda k: out[k][0])
        ref = out.get("LightGBM")
        print(f"  가장 낮은 것    {best}")
        if ref and best != "LightGBM":
            d = ref[0] - out[best][0]
            sd2 = 2 * max(ref[1], out[best][1])
            mark = "O" if d > sd2 else ("X" if -d > sd2 else "ㅡ")
            print(f"  LightGBM 대비  {d:+.4f}  (편차×2 {sd2:.4f})  판정 {mark}")
            print("  ※ 폴드 하나로 정하지 않습니다. 검증 2022 도 돌려 부호를 보세요.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
