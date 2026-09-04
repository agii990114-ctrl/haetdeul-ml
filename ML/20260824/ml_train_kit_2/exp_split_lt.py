# -*- coding: utf-8 -*-
"""리드타임 구간별 모델 분리 — 경락가 정확도 [M-13 후속]

## 왜

한 모델이 **3영업일 뒤와 18영업일 뒤를 같이** 맞힙니다. `lead_biz_d` 를
feature 로 주고 모델이 알아서 구분하게 두는 방식입니다.

그런데 오차가 리드타임에 따라 크게 다릅니다 (2026 실전).

    경락 무    LT3~5 16.3%  ->  LT11~18 21.5%
    경락 배추   LT3~5 14.2%  ->  LT11~18 17.4%

**가까운 날은 앵커가 세고, 먼 날은 계절·수급이 지배합니다.** 성격이 다른
문제를 한 모델이 절충하고 있을 수 있습니다 — 오늘 양파에서 확인한 것과
같은 모양입니다.

## 함정

**나누면 학습 행이 절반 이하가 됩니다.** 양파 분리 때와 같은 대가입니다.
그리고 `lead_biz_d` 는 나눠도 구간 안에서 여전히 필요합니다 (상수가 아님).

## 견주는 것

    현행     LT3~18 한 모델
    나눔     LT3~5 · LT6~10 · LT11~18 세 모델
    둘로     LT3~7 · LT8~18 두 모델

    python exp_split_lt.py <csv> --targets auc --folds A B C
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
#: 나누는 방식들. (이름, 구간 목록)
SPLITS = {
    "셋으로": [(3, 5), (6, 10), (11, 18)],
    "둘로":   [(3, 7), (8, 18)],
}


def wmape(a, p):
    a, p = np.asarray(a, float), np.asarray(p, float)
    return float(np.abs(a - p).sum() / np.abs(a).sum())


def fit_pred(tr, va, feats, cats, seed, rounds, tgt, anc):
    p = dict(T.PARAMS, seed=seed, bagging_seed=seed, feature_fraction_seed=seed)
    cat_in = [c for c in cats if c in feats]
    m = lgb.train(p, lgb.Dataset(tr[feats], tr["y"], categorical_feature=cat_in),
                  num_boost_round=rounds)
    return va[anc].to_numpy(float) * np.exp(m.predict(va[feats]))


def main() -> int:
    ap = argparse.ArgumentParser(description="리드타임 구간 분리")
    ap.add_argument("csv")
    ap.add_argument("--targets", nargs="+", default=["auc"])
    ap.add_argument("--train-start", default="2017-01-01")
    ap.add_argument("--gate-lt", type=int, default=3)
    ap.add_argument("--seeds", nargs="+", type=int, default=list(range(62, 72)))
    ap.add_argument("--folds", nargs="+", default=["A", "B", "C"],
                    choices=["A", "B", "C"])
    a = ap.parse_args()
    folds = [ALL_FOLDS[f] for f in a.folds]

    print("=" * 92)
    print("[리드타임 구간 분리] 한 모델이 3일 뒤와 18일 뒤를 같이 맞히고 있다")
    print(f"  시드 {len(a.seeds)}개 · LT>={a.gate_lt} · 폴드 {' '.join(a.folds)}")
    print("  양수 = 나누는 게 낫다")
    print("=" * 92)

    tally: dict[tuple, list] = {}
    for kind in a.targets:
        alpha, rounds = OPS[kind]
        for tag, tend, vend in folds:
            tr, va, feats, cats, tgt, anc, label = build(a.csv, kind, tend, vend, alpha)
            tr = tr[tr.base_dt >= pd.Timestamp(a.train_start)]
            va = va[va.lead_biz_d >= a.gate_lt].copy()
            items = va["item_nm"].astype(str).to_numpy()
            actual = va[tgt].to_numpy(float)
            lt = va["lead_biz_d"].to_numpy(int)

            base = {i: [] for i in ITEMS}
            got = {k: {i: [] for i in ITEMS} for k in SPLITS}
            for s in a.seeds:
                #   현행 — 한 모델
                pred = fit_pred(tr, va, feats, cats, s, rounds, tgt, anc)
                for it in ITEMS:
                    k = items == it
                    if k.sum():
                        base[it].append(wmape(actual[k], pred[k]))
                #   나눔 — 구간마다 모델 하나. 예측을 다시 이어 붙인다
                for name, spans in SPLITS.items():
                    out = np.full(len(va), np.nan)
                    for lo, hi in spans:
                        m_tr = tr.lead_biz_d.between(lo, hi)
                        m_va = (lt >= lo) & (lt <= hi)
                        if not m_tr.any() or not m_va.any():
                            continue
                        out[m_va] = fit_pred(tr[m_tr], va[m_va], feats, cats,
                                             s, rounds, tgt, anc)
                    for it in ITEMS:
                        k = (items == it) & ~np.isnan(out)
                        if k.sum():
                            got[name][it].append(wmape(actual[k], out[k]))

            print(f"\n  [{label} · 폴드 {tag}]  학습 {len(tr):,} · 검증 {len(va):,}행")
            print("      %-8s%11s%11s%11s" % ("", *ITEMS))
            print("      %-8s" % "현행" + "".join("%11.4f" % st.mean(base[i]) for i in ITEMS))
            for name in SPLITS:
                print("      %-8s" % name
                      + "".join("%11.4f" % st.mean(got[name][i]) for i in ITEMS))
            for name in SPLITS:
                cells = []
                for it in ITEMS:
                    g, s2 = st.mean(base[it]), st.mean(got[name][it])
                    imp = (g - s2) / g * 100
                    sd = (st.pstdev(base[it]) + st.pstdev(got[name][it])) / 2 / g * 100
                    cells.append("%+10.2f%%" % imp)
                    tally.setdefault((kind, name, it), []).append((imp, sd))
                print("      %-8s" % ("↑ " + name) + "".join(cells))

    print("\n" + "=" * 92)
    print("[3폴드 판정] 부호 일치 + 편차x2")
    print("=" * 92)
    for (kind, name, item), pairs in sorted(tally.items()):
        vals = [p[0] for p in pairs]; sds = [p[1] for p in pairs]
        same = all(v > 0 for v in vals) or all(v < 0 for v in vals)
        need = 2 * (sum(s * s for s in sds) ** 0.5); got_ = abs(sum(vals))
        mark = ("★ 갈림 — 판정 불가" if not same else
                "편차x2 미달 (%.2f < %.2f)" % (got_, need) if got_ < need else
                ("★ 통과 — 나누는 게 낫다" if vals[0] > 0 else "★ 통과 — 합치는 게 낫다"))
        print("  %-5s %-6s %-3s  %s  합%+7.2f 필요%6.2f   %s"
              % (kind, name, item, " ".join("%+7.2f%%" % v for v in vals),
                 sum(vals), need, mark))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
