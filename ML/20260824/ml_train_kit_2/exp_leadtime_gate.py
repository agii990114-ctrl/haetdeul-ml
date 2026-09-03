# -*- coding: utf-8 -*-
"""리드타임별로 모델이 앵커를 이기는가 — 백로그 [M-14] (2026-09-03)

## 왜 하나

지금 게이트는 **`LT<3` 하나**입니다. 타겟·품목에 상관없이 같습니다.

그런데 테스트 2024~25 에서 **중도매가는 LT1~10 이 전부 음수**였습니다
(LT3 −15.2%). 게이트가 3 이면 LT3~10 은 모델이 나가는데, 그 구간에서
앵커보다 못했다는 뜻입니다.

`ref_prediction_quality` 는 **품목 × 타겟까지만** 다루고 **리드타임 축이
없습니다.** 그래서 "중도매가 배추 LT5 는 쓰지 마라" 를 표현할 방법이 없습니다.

## 무엇을 재나

리드타임 1~18 각각에서 **모델 오차**와 **앵커 오차**를 견줍니다.

    개선율 = (앵커오차 - 모델오차) / 앵커오차

음수면 그 자리는 **모델을 안 쓰는 게 낫습니다.**

## ★ 세 폴드로 본다 (5.7절 ③)

한 해만 보면 그 해 사정이 그대로 들어옵니다. **세 해에서 모두 음수인
자리만** 게이트 후보로 봅니다.

## ★ 앵커는 운영이 쓰는 것 그대로

수축 앵커(α×어제값 + (1−α)×7일평균)입니다. 어제값 단독이 아닙니다 —
그걸로 재면 게이트가 실제보다 유리해 보입니다.

## 쓰는 법

    python exp_leadtime_gate.py train_20260828b.csv
    python exp_leadtime_gate.py train_20260828b.csv --targets whsl --seeds 62 63
"""
from __future__ import annotations

import argparse
import statistics as st
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import train as T                                            # noqa: E402
from exp_quantile import build                               # noqa: E402

OPS = {"auc": (0.4, 76), "whsl": (0.8, 122), "rtl": (1.0, 81)}
ALL_FOLDS = {
    "A": ("A(검증2023)", "2022-12-31", "2023-12-31"),
    "B": ("B(검증2022)", "2021-12-31", "2022-12-31"),
    "C": ("C(검증2021)", "2020-12-31", "2021-12-31"),
}
ITEMS = ["배추", "무", "양파"]


def wmape(a, p):
    a, p = np.asarray(a, float), np.asarray(p, float)
    s = np.abs(a).sum()
    return float(np.abs(a - p).sum() / s) if s else float("nan")


def run_fold(csv, kind, tend, vend, train_start, seeds):
    """한 폴드에서 (품목, 리드타임)별 모델·앵커 오차를 낸다."""
    alpha, rounds = OPS[kind]
    tr, va, feats, cats, tgt, anc, label = build(csv, kind, tend, vend, alpha)
    tr = tr[tr.base_dt >= pd.Timestamp(train_start)]
    #   ★ 게이트를 걸지 않는다. 게이트를 걸 자리를 찾는 실험이다.
    cat_in = [c for c in cats if c in feats]
    ancv = va[anc].to_numpy(float)
    actual = va[tgt].to_numpy(float)
    preds = []
    for s in seeds:
        p = dict(T.PARAMS, seed=s, bagging_seed=s, feature_fraction_seed=s)
        m = lgb.train(p, lgb.Dataset(tr[feats], tr["y"], categorical_feature=cat_in),
                      num_boost_round=rounds)
        preds.append(ancv * np.exp(m.predict(va[feats])))
    pred = np.mean(preds, axis=0)
    out = {}
    it_arr = va["item_nm"].astype(str).to_numpy()
    lt_arr = va["lead_biz_d"].to_numpy(int)
    for it in ITEMS:
        for lt in range(1, 19):
            k = (it_arr == it) & (lt_arr == lt)
            if k.sum() < 10:
                continue
            wa, wm = wmape(actual[k], ancv[k]), wmape(actual[k], pred[k])
            out[(it, lt)] = ((wa - wm) / wa * 100 if wa else float("nan"),
                             wa, wm, int(k.sum()))
    return out, label


def main() -> int:
    ap = argparse.ArgumentParser(description="리드타임별 게이트 판정 [M-14]")
    ap.add_argument("csv")
    ap.add_argument("--targets", nargs="+", default=["auc", "whsl", "rtl"])
    ap.add_argument("--folds", nargs="+", default=["A", "B", "C"], choices=["A", "B", "C"])
    ap.add_argument("--train-start", default="2017-01-01")
    ap.add_argument("--seeds", nargs="+", type=int, default=list(range(62, 72)))
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    print("=" * 92)
    print("[리드타임별 게이트 판정 · M-14] 운영 조건 · 품목별 · 세 폴드")
    print(f"  시드 {len(a.seeds)}개 · 학습 {a.train_start}~ · 폴드 {', '.join(a.folds)}")
    print("  개선율 = (앵커오차 − 모델오차) / 앵커오차 ·  음수면 모델을 안 쓰는 게 낫다")
    print("  ※ 게이트를 걸지 않고 잽니다. 걸 자리를 찾는 실험입니다")
    print("=" * 92)

    rows = []
    for kind in a.targets:
        per = {}
        label = kind
        for fk in a.folds:
            tag, tend, vend = ALL_FOLDS[fk]
            r, label = run_fold(a.csv, kind, tend, vend, a.train_start, a.seeds)
            for key, v in r.items():
                per.setdefault(key, {})[fk] = v
                rows.append(dict(target=kind, fold=tag, item=key[0], lead=key[1],
                                 imp_pct=round(v[0], 2), wmape_anchor=round(v[1], 5),
                                 wmape_model=round(v[2], 5), n=v[3]))
        print(f"\n  [{label}]  리드타임별 개선율 (%) · 음수 = 앵커가 낫다")
        for it in ITEMS:
            print(f"\n    {it}")
            print("      LT  " + "".join("%9s" % ("폴드" + f) for f in a.folds)
                  + "   판정")
            for lt in range(1, 19):
                v = per.get((it, lt))
                if not v:
                    continue
                gs = [v[f][0] for f in a.folds if f in v]
                line = "      %2d  " % lt + "".join("%+9.1f" % g for g in gs)
                if all(g < 0 for g in gs):
                    line += "   ★ 모델을 안 쓰는 게 낫다"
                elif all(g > 0 for g in gs):
                    line += "   모델이 낫다"
                else:
                    line += "   갈림"
                print(line)

        #   게이트 후보 — 세 폴드 모두 음수인 리드타임
        print(f"\n    [{label} 게이트 후보]  세 폴드 모두 음수인 자리")
        any_c = False
        for it in ITEMS:
            bad = [lt for lt in range(1, 19)
                   if (it, lt) in per
                   and all(per[(it, lt)][f][0] < 0 for f in a.folds if f in per[(it, lt)])]
            if bad:
                any_c = True
                print(f"      {it:<5} LT {', '.join(map(str, bad))}")
        if not any_c:
            print("      없음")

    if a.out:
        pd.DataFrame(rows).to_csv(a.out, index=False, encoding="utf-8-sig")
        print(f"\n[저장] {a.out}")
    print("\n" + "=" * 92)
    print("  게이트를 넓히면 그 구간이 앵커로 나갑니다. 예측이 평탄해지므로")
    print("  '먼 리드타임일수록 개선폭이 크다' 는 사업 가치와 맞바꿉니다 (8절).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
