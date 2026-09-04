# -*- coding: utf-8 -*-
"""품목별 모델 분리 — 백로그 [M-13] 후보 ④ (운영 조건 · 3폴드)

## 왜 다시 하나

`exp_per_item.py` 가 2026-08-28 에 같은 것을 물었습니다. **그 판정은 못 씁니다.**

    거기       조기 종료(3000그루) · 2폴드
    운영       고정 트리 (경락 76 · 중도매 122 · 소매 81) · 3폴드 규칙

5.12 절에서 **트리 개수가 모델 종류보다 10배 크게 작용**한다고 쟀습니다.
조기 종료로 낸 판정을 고정 트리 운영에 옮길 수 없습니다 (5.7 ①).

## 기대치를 낮춰 둡니다

오늘 진단은 **품목 문제가 아니라 계열 문제**였습니다.

    전일과 값이 똑같은 날    경락 0.6~1.3% · 소매 18~26% · 중도매 58~68%

같은 품목인데 경락·소매는 좋고 중도매만 앵커 수준입니다.
**품목별로 나눠도 "엿새는 안 움직인다" 는 성질은 그대로입니다.**

**그래도 돌립니다** — "안 된다" 를 숫자로 남겨야 다음 사람이 또 안 뒤집습니다.

## 무엇을 견주나

    합침(현행)   배추·무·양파를 한 모델이 배운다. item_nm 이 범주형 feature
    나눔         품목마다 따로 배운다. item_nm 은 상수라 뺀다

    나눔이 좋은 이유   품목마다 다른 규칙을 각자 배운다
    합침이 좋은 이유   학습 행이 3배. 셋이 공유하는 것(계절·명절)을 같이 배운다

    ⚠ 나누면 학습 행이 3분의 1 이 됩니다. 8절에서 **양파는 학습 기간을
      가장 많이 타는 품목**이라고 쟀으니 양파가 가장 손해를 볼 수 있습니다.

    python exp_split_model.py <csv> --targets whsl auc rtl --folds A B C
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


def wmape(a, p):
    a, p = np.asarray(a, float), np.asarray(p, float)
    return float(np.abs(a - p).sum() / np.abs(a).sum())


def fit(tr, va, feats, cats, seeds, rounds, tgt, anc):
    """한 묶음을 학습해 시드별 wmape 를 돌려준다."""
    if len(tr) == 0 or len(va) == 0:
        return []
    ancv = va[anc].to_numpy(float)
    actual = va[tgt].to_numpy(float)
    cat_in = [c for c in cats if c in feats]
    out = []
    for s in seeds:
        p = dict(T.PARAMS, seed=s, bagging_seed=s, feature_fraction_seed=s)
        m = lgb.train(p, lgb.Dataset(tr[feats], tr["y"], categorical_feature=cat_in),
                      num_boost_round=rounds)
        out.append(wmape(actual, ancv * np.exp(m.predict(va[feats]))))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="품목별 모델 분리 [M-13 ④]")
    ap.add_argument("csv")
    ap.add_argument("--targets", nargs="+", default=["whsl", "auc", "rtl"])
    ap.add_argument("--train-start", default="2017-01-01")
    ap.add_argument("--gate-lt", type=int, default=3)
    ap.add_argument("--seeds", nargs="+", type=int, default=list(range(62, 72)))
    ap.add_argument("--folds", nargs="+", default=["A", "B", "C"],
                    choices=["A", "B", "C"])
    a = ap.parse_args()
    folds = [ALL_FOLDS[f] for f in a.folds]

    print("=" * 92)
    print("[품목별 모델 분리] 합친 모델 vs 품목마다 따로 · 운영 조건(고정 트리)")
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
            print(f"\n  [{label} · 폴드 {tag}]  α={alpha} · {rounds}그루"
                  f" · 학습 {len(tr):,}행 · 검증 {len(va):,}행")

            #   ── 합친 모델 (현행) — 한 번 학습해 품목별로 잰다
            ancv = va[anc].to_numpy(float)
            actual = va[tgt].to_numpy(float)
            items = va["item_nm"].astype(str).to_numpy()
            cat_in = [c for c in cats if c in feats]
            pooled = {it: [] for it in ITEMS}
            for s in a.seeds:
                p = dict(T.PARAMS, seed=s, bagging_seed=s, feature_fraction_seed=s)
                m = lgb.train(p, lgb.Dataset(tr[feats], tr["y"],
                                             categorical_feature=cat_in),
                              num_boost_round=rounds)
                pred = ancv * np.exp(m.predict(va[feats]))
                for it in ITEMS:
                    k = items == it
                    if k.sum():
                        pooled[it].append(wmape(actual[k], pred[k]))

            print("      %-8s%11s%11s%11s" % ("", *ITEMS))
            print("      %-8s" % "합침"
                  + "".join("%11.4f" % st.mean(pooled[it]) for it in ITEMS))

            #   ── 나눈 모델 — 품목마다 그 품목 행만으로 학습
            #     item_nm 은 상수가 되므로 뺀다 (넣으면 쓸모없는 범주 하나)
            f2 = [c for c in feats if c != "item_nm"]
            c2 = [c for c in cats if c != "item_nm"]
            cells, split = [], {}
            for it in ITEMS:
                tri = tr[tr.item_nm.astype(str) == it]
                vai = va[va.item_nm.astype(str) == it]
                v = fit(tri, vai, f2, c2, a.seeds, rounds, tgt, anc)
                split[it] = v
                cells.append("%11.4f" % (st.mean(v) if v else float("nan")))
            print("      %-8s" % "나눔" + "".join(cells))

            imp_cells = []
            for it in ITEMS:
                if not split[it] or not pooled[it]:
                    imp_cells.append("%11s" % "-"); continue
                g, s2 = st.mean(pooled[it]), st.mean(split[it])
                imp = (g - s2) / g * 100
                sd = (st.pstdev(pooled[it]) + st.pstdev(split[it])) / 2 / g * 100
                imp_cells.append("%+10.2f%%" % imp)
                tally.setdefault((kind, it), []).append((imp, sd))
            print("      %-8s" % "개선율" + "".join(imp_cells))
            print("      %-8s" % "학습행"
                  + "".join("%11s" % format(int((tr.item_nm.astype(str) == it).sum()), ",")
                            for it in ITEMS))

    print("\n" + "=" * 92)
    print("[3폴드 판정]  부호 일치 + 편차x2 (5.7 ③)")
    print("=" * 92)
    for (kind, item), pairs in sorted(tally.items()):
        vals = [p[0] for p in pairs]
        sds = [p[1] for p in pairs]
        same = all(v > 0 for v in vals) or all(v < 0 for v in vals)
        need = 2 * (sum(s * s for s in sds) ** 0.5)
        got = abs(sum(vals))
        mark = ("★ 갈림 — 판정 불가" if not same else
                "부호는 같으나 편차x2 미달 (%.2f < %.2f)" % (got, need) if got < need else
                ("★ 통과 — 나누는 게 낫다" if vals[0] > 0 else "★ 통과 — 합치는 게 낫다"))
        print("  %-5s %-3s  %s  합%+7.2f 필요%6.2f   %s"
              % (kind, item, " ".join("%+7.2f%%" % v for v in vals),
                 sum(vals), need, mark))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
