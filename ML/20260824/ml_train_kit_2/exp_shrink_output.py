# -*- coding: utf-8 -*-
"""모델이 덜 움직이게 하면 나아지나 — 백로그 [M-13] 후보 ①(뒤집은 것)

## 왜 이 방향인가

처음에는 *"중도매가는 값이 바뀌는 32~42% 의 날에만 뜻이 있으니, 바뀌는
날을 골라내자"* 로 생각했습니다. **오차를 갈라 보니 반대였습니다.**

    중도매가 오차 비중 (2026 · LT>=3 · 게이트 제외)
        무     바뀜 41.6%   그대로 58.4%
        배추   바뀜 34.3%   그대로 65.7%

**오차의 절반 넘게가 "값이 안 바뀐 날" 에서 나옵니다.** 그날은 앵커가
정확한데 **모델이 괜히 움직여서** 생긴 오차입니다.

**그러니 고칠 것은 "바뀌는 날을 맞히는 것" 이 아니라
"안 바뀔 날에 가만히 있는 것" 입니다.**

## 무엇을 하나 — 한 개짜리 손잡이

우리 예측은 이렇습니다.

    pred = anchor * exp(model_output)

여기에 **줄임 계수 λ** 를 답니다.

    pred = anchor * exp(λ * model_output)

    λ = 1.0   지금 그대로
    λ = 0.5   모델이 말하는 변화를 절반만 믿는다
    λ = 0.0   앵커 그대로 (모델을 안 쓴다)

**재학습이 필요 없습니다.** 이미 있는 모델 출력에 곱하기만 하면 됩니다.
그래서 결과가 좋으면 바로 반영할 수 있습니다.

## 함정 — 뻔한 결과가 나올 수 있습니다

중도매가는 앵커가 이미 모델보다 낫습니다. 그러면 **λ 를 줄이면 당연히
좋아집니다** — 앵커 쪽으로 가니까요. 그건 발견이 아닙니다.

**그래서 셋을 같이 봅니다.**

    ① 경락·소매도 같이 잰다   거기서도 λ<1 이 좋으면 "우리 모델이 전반적으로
                             과하게 움직인다" 는 뜻이고, 중도매만의 이야기가 아니다
    ② 3폴드에서 최적 λ 가 비슷한가   폴드마다 다른 λ 가 좋으면 못 고른다
    ③ λ=0 과 견준다          λ=0 이 제일 좋으면 그 조합은 모델을 쓸 이유가 없다

    python exp_shrink_output.py <csv> --targets whsl auc rtl --folds A B C
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

OPS = {"auc": (0.4, 76), "whsl": (0.8, 122), "rtl": (1.0, 81)}
ALL_FOLDS = {
    "A": ("A(검증2023)", "2022-12-31", "2023-12-31"),
    "B": ("B(검증2022)", "2021-12-31", "2022-12-31"),
    "C": ("C(검증2021)", "2020-12-31", "2021-12-31"),
}
ITEMS = ["배추", "무", "양파"]
LAMBDAS = [1.0, 0.9, 0.8, 0.6, 0.4, 0.2, 0.0]


def wmape(a, p):
    a, p = np.asarray(a, float), np.asarray(p, float)
    return float(np.abs(a - p).sum() / np.abs(a).sum())


def run_fold(tr, va, feats, cats, seeds, rounds, tgt, anc):
    """시드마다 한 번만 학습하고, λ 는 출력에 곱하기만 한다."""
    ancv = va[anc].to_numpy(float)
    actual = va[tgt].to_numpy(float)
    items = va["item_nm"].astype(str).to_numpy()
    cat_in = [c for c in cats if c in feats]
    #   λ -> 품목 -> 시드별 wmape
    acc = {lam: {it: [] for it in ITEMS + ["통합"]} for lam in LAMBDAS}
    for s in seeds:
        p = dict(T.PARAMS, seed=s, bagging_seed=s, feature_fraction_seed=s)
        m = lgb.train(p, lgb.Dataset(tr[feats], tr["y"], categorical_feature=cat_in),
                      num_boost_round=rounds)
        raw = m.predict(va[feats])                 # 로그 비율
        for lam in LAMBDAS:
            pred = ancv * np.exp(lam * raw)
            acc[lam]["통합"].append(wmape(actual, pred))
            for it in ITEMS:
                k = items == it
                if k.sum():
                    acc[lam][it].append(wmape(actual[k], pred[k]))
    return {lam: {it: (st.mean(v), st.pstdev(v) if len(v) > 1 else 0.0)
                  for it, v in d.items() if v} for lam, d in acc.items()}


def main() -> int:
    ap = argparse.ArgumentParser(description="모델 출력을 줄여 본다 [M-13 ①']")
    ap.add_argument("csv")
    ap.add_argument("--targets", nargs="+", default=["whsl", "auc", "rtl"])
    ap.add_argument("--train-start", default="2017-01-01")
    ap.add_argument("--gate-lt", type=int, default=3)
    ap.add_argument("--seeds", nargs="+", type=int, default=list(range(62, 72)))
    ap.add_argument("--folds", nargs="+", default=["A", "B", "C"],
                    choices=["A", "B", "C"])
    a = ap.parse_args()
    folds = [ALL_FOLDS[f] for f in a.folds]

    print("=" * 96)
    print("[출력 줄이기] pred = anchor * exp(λ · 모델출력) · 운영 조건 · 품목별")
    print(f"  시드 {len(a.seeds)}개 · LT>={a.gate_lt} · 폴드 {' '.join(a.folds)}")
    print("  ★ λ=1.0 이 지금입니다. λ=0.0 은 앵커 그대로(모델 안 씀)입니다.")
    print("  값은 WMAPE — 작을수록 좋습니다.")
    print("=" * 96)

    best: dict[tuple, list] = {}
    for kind in a.targets:
        alpha, rounds = OPS[kind]
        for tag, tend, vend in folds:
            tr, va, feats, cats, tgt, anc, label = build(a.csv, kind, tend, vend, alpha)
            tr = tr[tr.base_dt >= pd.Timestamp(a.train_start)]
            va = va[va.lead_biz_d >= a.gate_lt].copy()
            res = run_fold(tr, va, feats, cats, a.seeds, rounds, tgt, anc)
            print(f"\n  [{label} · 폴드 {tag}]  α={alpha} · {rounds}그루"
                  f" · 검증 {len(va):,}행")
            print("      λ    " + "".join("%11s" % k for k in ITEMS + ["통합"]))
            for lam in LAMBDAS:
                row = "".join("%11.4f" % res[lam][k][0] for k in ITEMS + ["통합"])
                print("    %5.1f  %s" % (lam, row))
            for k in ITEMS + ["통합"]:
                bl = min(LAMBDAS, key=lambda L: res[L][k][0])
                gain = (res[1.0][k][0] - res[bl][k][0]) / res[1.0][k][0] * 100
                best.setdefault((kind, k), []).append((tag, bl, gain))

    print("\n" + "=" * 96)
    print("[폴드마다 가장 좋은 λ]  같은 값이 나와야 고를 수 있습니다")
    print("=" * 96)
    for (kind, item), rows in sorted(best.items()):
        ls = [r[1] for r in rows]
        same = len(set(ls)) == 1
        print("  %-5s %-3s  %s   %s"
              % (kind, item,
                 " · ".join("%s λ=%.1f (%+.1f%%)" % (t, l, g) for t, l, g in rows),
                 "일치" if same else ("가까움" if max(ls) - min(ls) <= 0.2
                                     else "★ 갈림 — 못 고름")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
