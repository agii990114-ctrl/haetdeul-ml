# -*- coding: utf-8 -*-
"""양파를 떼면 **남는 둘**은 어떻게 되나 — [M-13] ④ 마무리

## 왜 이게 따로 필요한가

`exp_split_model.py` 가 잰 것은 **"셋 묶음 vs 그 품목 혼자"** 입니다.
거기서 중도매 양파만 3폴드를 통과했습니다 (+3.83 / +7.79 / +22.53%).

**그런데 배포하면 모양이 다릅니다.**

    쟀던 것    셋 묶음  ↔  양파 혼자
    배포하면   배추·무 둘 묶음  +  양파 혼자

**배추·무 둘 묶음은 안 쟀습니다.** 양파를 빼면 그 둘의 학습 행이
3분의 2 로 줄고, 셋이 공유하던 것(계절·명절)도 한 품목만큼 사라집니다.
**거기서 손해가 나면 양파 이득이 상쇄될 수 있습니다.**

    python exp_split_onion.py <csv> --targets whsl --folds A B C
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
PAIR = ["배추", "무"]


def wmape(a, p):
    a, p = np.asarray(a, float), np.asarray(p, float)
    return float(np.abs(a - p).sum() / np.abs(a).sum())


def main() -> int:
    ap = argparse.ArgumentParser(description="양파를 뗀 뒤 남는 둘 [M-13 ④]")
    ap.add_argument("csv")
    ap.add_argument("--targets", nargs="+", default=["whsl"])
    ap.add_argument("--train-start", default="2017-01-01")
    ap.add_argument("--gate-lt", type=int, default=3)
    ap.add_argument("--seeds", nargs="+", type=int, default=list(range(62, 72)))
    ap.add_argument("--folds", nargs="+", default=["A", "B", "C"],
                    choices=["A", "B", "C"])
    a = ap.parse_args()
    folds = [ALL_FOLDS[f] for f in a.folds]

    print("=" * 92)
    print("[양파를 떼면 남는 둘은?] 셋 묶음 vs 배추·무 둘 묶음 · 운영 조건")
    print(f"  시드 {len(a.seeds)}개 · LT>={a.gate_lt} · 폴드 {' '.join(a.folds)}")
    print("  양수 = 둘 묶음이 낫다 (= 양파를 빼도 손해가 없다)")
    print("=" * 92)

    tally: dict[tuple, list] = {}
    for kind in a.targets:
        alpha, rounds = OPS[kind]
        for tag, tend, vend in folds:
            tr, va, feats, cats, tgt, anc, label = build(a.csv, kind, tend, vend, alpha)
            tr = tr[tr.base_dt >= pd.Timestamp(a.train_start)]
            va = va[va.lead_biz_d >= a.gate_lt].copy()
            va2 = va[va.item_nm.astype(str).isin(PAIR)].copy()
            tr2 = tr[tr.item_nm.astype(str).isin(PAIR)]
            cat_in = [c for c in cats if c in feats]

            ancv = va2[anc].to_numpy(float)
            actual = va2[tgt].to_numpy(float)
            items = va2["item_nm"].astype(str).to_numpy()
            got = {"셋": {i: [] for i in PAIR}, "둘": {i: [] for i in PAIR}}
            for s in a.seeds:
                p = dict(T.PARAMS, seed=s, bagging_seed=s, feature_fraction_seed=s)
                for tag2, trx in (("셋", tr), ("둘", tr2)):
                    m = lgb.train(p, lgb.Dataset(trx[feats], trx["y"],
                                                 categorical_feature=cat_in),
                                  num_boost_round=rounds)
                    pred = ancv * np.exp(m.predict(va2[feats]))
                    for it in PAIR:
                        k = items == it
                        if k.sum():
                            got[tag2][it].append(wmape(actual[k], pred[k]))

            print(f"\n  [{label} · 폴드 {tag}]  학습 셋 {len(tr):,}행"
                  f" · 둘 {len(tr2):,}행")
            print("      %-8s%11s%11s" % ("", *PAIR))
            for tag2 in ("셋", "둘"):
                print("      %-8s" % (tag2 + " 묶음")
                      + "".join("%11.4f" % st.mean(got[tag2][it]) for it in PAIR))
            cells = []
            for it in PAIR:
                g, s2 = st.mean(got["셋"][it]), st.mean(got["둘"][it])
                imp = (g - s2) / g * 100
                sd = (st.pstdev(got["셋"][it]) + st.pstdev(got["둘"][it])) / 2 / g * 100
                cells.append("%+10.2f%%" % imp)
                tally.setdefault((kind, it), []).append((imp, sd))
            print("      %-8s" % "개선율" + "".join(cells))

    print("\n" + "=" * 92)
    print("[3폴드 판정]  음수면 양파를 뺀 손해다")
    print("=" * 92)
    for (kind, item), pairs in sorted(tally.items()):
        vals = [p[0] for p in pairs]
        sds = [p[1] for p in pairs]
        same = all(v > 0 for v in vals) or all(v < 0 for v in vals)
        need = 2 * (sum(s * s for s in sds) ** 0.5)
        got_ = abs(sum(vals))
        mark = ("★ 갈림 — 판정 불가" if not same else
                "부호는 같으나 편차x2 미달 (%.2f < %.2f)" % (got_, need) if got_ < need else
                ("★ 통과 — 빼도 낫다" if vals[0] > 0 else "★ 통과 — 빼면 손해다"))
        print("  %-5s %-3s  %s  합%+7.2f 필요%6.2f   %s"
              % (kind, item, " ".join("%+7.2f%%" % v for v in vals),
                 sum(vals), need, mark))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
