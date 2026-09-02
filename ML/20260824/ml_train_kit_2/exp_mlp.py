# -*- coding: utf-8 -*-
"""신경망이 이 문제를 배울 수 있나 — 싼 사전 확인 (2026-09-01)

## 왜 이걸 먼저 하나

TFT(트랜스포머)를 재려면 `torch` 를 깔아야 하고 2GB 넘는 설치다.
그 전에 **"신경망이 우리 자료에서 부스팅 근처라도 가나" 를 싸게 확인**한다.
`sklearn` 은 이미 깔려 있고 10분이면 끝난다.

**이건 TFT 가 아니다.** TFT 는 "미리 아는 미래" 를 구조로 구분하고 시계열을
직접 다룬다. 여기서 재는 것은 **같은 입력·같은 라벨을 신경망에 줬을 때**
어디까지 가느냐다. 두 가지 판단에 쓴다.

    부스팅 근처도 못 간다   →  TFT 도 어려울 가능성이 크다. 설치 전에 안다
    근처까지 간다           →  구조를 더 준 TFT 는 볼 가치가 있다

**근처까지 가더라도 "TFT 가 이긴다" 는 뜻은 아니다.** 반대로 못 가더라도
"TFT 가 반드시 진다" 는 뜻도 아니다. **설치 비용을 낼지 정하는 근거일 뿐이다.**

## 왜 신경망이 불리하다고 보나 — 미리 밝힌다

```
실질 표본        고유 기준일 1,475개 (2017~2022)
같은 날 부스팅    50그루 0.1665  →  1200그루 0.1855   모델을 키우면 나빠진다
```

**모델을 키우면 나빠지는 자료다.** 신경망은 LightGBM 1200그루보다 훨씬 큰
모델이다. 그래서 기대치를 낮게 잡는다.

## 공정하게 재기 위해 맞춘 것

신경망은 부스팅과 달리 **전처리 없이는 아예 못 배운다.** 그래서 세 가지를 한다.

    결측    중앙값으로 채운다 (부스팅은 결측을 그대로 다룬다)
    범주형   one-hot 으로 편다 (품목 · 요일 · 관측소)
    크기    표준화한다 — 안 하면 큰 값을 가진 입력이 학습을 지배한다

**이 전처리는 신경망에 유리한 쪽으로만 한다.** 불리하게 만들어 놓고
"역시 안 된다" 고 하면 실험이 아니다.

나머지는 전부 같다 — feature · 앵커 변환 · 학습 구간 · 폴드 · baseline.

## 쓰는 법

    python exp_mlp.py <csv> --target auc
    python exp_mlp.py <csv> --sizes 64 "128,64" "256,128,64"
"""
from __future__ import annotations

import argparse
import statistics as st
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import train as T                                            # noqa: E402
from exp_quantile import build                               # noqa: E402

OPS = {"auc": (0.4, 76), "whsl": (0.8, 122), "rtl": (1.0, 81)}
FOLDS = [("A(검증2023)", "2022-12-31", "2023-12-31"),
         ("B(검증2022)", "2021-12-31", "2022-12-31")]


def wmape(a, p):
    a, p = np.asarray(a, float), np.asarray(p, float)
    return np.abs(a - p).sum() / np.abs(a).sum()


def make_xy(tr, va, feats, cats):
    """신경망이 먹을 수 있는 형태로 바꾼다. 학습 자료로만 기준을 잡는다."""
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import OneHotEncoder, StandardScaler

    num = [c for c in feats if c not in cats]
    #   ★ 기준은 학습 자료에서만 잡는다. 검증 자료로 채우거나 표준화하면
    #   미래를 훔쳐보는 것이 되어 검증에서만 잘 나온다.
    imp = SimpleImputer(strategy="median").fit(tr[num])
    sc = StandardScaler().fit(imp.transform(tr[num]))
    Xtr = [sc.transform(imp.transform(tr[num]))]
    Xva = [sc.transform(imp.transform(va[num]))]
    if cats:
        oh = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
        oh.fit(tr[cats].astype(str))
        Xtr.append(oh.transform(tr[cats].astype(str)))
        Xva.append(oh.transform(va[cats].astype(str)))
    return np.hstack(Xtr), np.hstack(Xva)


def run_mlp(Xtr, ytr, Xva, size, seed, iters):
    from sklearn.neural_network import MLPRegressor
    m = MLPRegressor(hidden_layer_sizes=size, activation="relu",
                     solver="adam", learning_rate_init=1e-3,
                     alpha=1e-3,                     # L2. 표본이 얇아 필요하다
                     batch_size=256, max_iter=iters,
                     early_stopping=True, n_iter_no_change=15,
                     validation_fraction=0.15, random_state=seed)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        m.fit(Xtr, ytr)
    return m.predict(Xva), m.n_iter_


def run_lgb(tr, va, feats, cats, seed, rounds):
    import lightgbm as lgb
    p = dict(T.PARAMS, seed=seed, bagging_seed=seed, feature_fraction_seed=seed)
    m = lgb.train(p, lgb.Dataset(tr[feats], tr["y"], categorical_feature=cats),
                  num_boost_round=rounds)
    return m.predict(va[feats])


def main() -> int:
    ap = argparse.ArgumentParser(description="신경망이 부스팅 근처라도 가나")
    ap.add_argument("csv")
    ap.add_argument("--target", default="auc", choices=list(OPS))
    ap.add_argument("--seeds", nargs="+", type=int, default=[42, 43, 44])
    ap.add_argument("--sizes", nargs="+", default=["64", "128,64", "256,128,64"],
                    help="은닉층 크기. 쉼표로 층을 나눈다")
    ap.add_argument("--iters", type=int, default=300)
    ap.add_argument("--gate-lt", type=int, default=3)
    a = ap.parse_args()

    alpha, rounds = OPS[a.target]
    print("=" * 78)
    print("[신경망 사전 확인] TFT 설치 전에 '근처라도 가나' 를 싸게 본다")
    print(f"  앵커 α={alpha} · LightGBM {rounds}그루(운영값) · 시드 {len(a.seeds)}개")
    print("  ※ 이건 TFT 가 아닙니다. 설치 비용을 낼지 정하는 근거입니다")
    print("=" * 78)

    for tag, tend, vend in FOLDS:
        tr, va, feats, cats, tgt, anc, label = build(
            a.csv, a.target, tend, vend, alpha)
        tr = tr[tr.base_dt >= pd.Timestamp("2017-01-01")]
        va = va[va.lead_biz_d >= a.gate_lt].copy()
        ancv, act = va[anc].to_numpy(float), va[tgt].to_numpy(float)
        base = wmape(act, ancv)          # 앵커 = 비교 기준

        Xtr, Xva = make_xy(tr, va, feats, cats)
        ytr = tr["y"].to_numpy(float)
        print(f"\n  [{label} · 폴드 {tag}]  학습 {len(tr):,}행 · 검증 {len(va):,}행")
        print(f"    입력 {len(feats)}개 → 펼친 뒤 {Xtr.shape[1]}개 "
              f"(범주형 {len(cats)}개를 one-hot 으로)")
        print(f"    {'모델':<18}{'WMAPE':>9}{'시드편차':>10}{'앵커대비':>10}{'시간':>8}")

        t0 = time.time()
        ws = [wmape(act, ancv * np.exp(run_lgb(tr, va, feats, cats, s, rounds)))
              for s in a.seeds]
        print(f"    {'LightGBM(운영)':<18}{st.mean(ws):>9.4f}"
              f"{st.pstdev(ws):>10.4f}{(1-st.mean(ws)/base)*100:>9.1f}%"
              f"{time.time()-t0:>7.0f}초")

        for spec in a.sizes:
            size = tuple(int(x) for x in str(spec).split(","))
            t0, ws, its = time.time(), [], []
            for s in a.seeds:
                try:
                    out, ni = run_mlp(Xtr, ytr, Xva, size, s, a.iters)
                except Exception as e:                       # noqa: BLE001
                    print(f"    {'MLP ' + spec:<18} 실패: {type(e).__name__}")
                    ws = []
                    break
                ws.append(wmape(act, ancv * np.exp(out)))
                its.append(ni)
            if not ws:
                continue
            print(f"    {'MLP ' + spec:<18}{st.mean(ws):>9.4f}"
                  f"{st.pstdev(ws):>10.4f}{(1-st.mean(ws)/base)*100:>9.1f}%"
                  f"{time.time()-t0:>7.0f}초   (반복 {int(np.mean(its))}회)")

        print(f"    {'앵커(비교 기준)':<18}{base:>9.4f}")

    print("\n" + "=" * 78)
    print("  읽는 법")
    print("    앵커대비가 음수면 단순 평균에도 진다는 뜻입니다")
    print("    신경망이 부스팅 근처도 못 가면 TFT 도 어려울 가능성이 큽니다")
    print("    ※ 다만 '반드시 진다' 는 뜻은 아닙니다 — TFT 는 구조가 다릅니다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
