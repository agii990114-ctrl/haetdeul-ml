# -*- coding: utf-8 -*-
"""학습 기간만 바꿔서 모델-앵커 격차가 달라지는지 본다.

검증은 2023 으로 고정하고 학습 끝만 옮긴다. 그러면 **학습 기간 하나만** 다르다.
"""
import io, sys, statistics as st
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
import lightgbm as lgb, numpy as np, pandas as pd
import train as T
from exp_quantile import build

OPS = {"auc": (0.4, 76), "rtl": (1.0, 81)}
SEEDS = list(range(62, 72))
ITEMS = ["배추", "무", "양파"]

def wm(a, p):
    a, p = np.asarray(a, float), np.asarray(p, float)
    return float(np.abs(a - p).sum() / np.abs(a).sum())

o = ["검증은 2023 고정 · 학습 끝만 옮김 · 앵커 대비 개선율 (%) · LT>=3", ""]
for kind in ["rtl", "auc"]:
    alpha, rounds = OPS[kind]
    o.append("[%s]" % kind)
    o.append("  학습 기간            배추      무     양파")
    for tend, yrs in (("2019-12-31", 3), ("2020-12-31", 4),
                      ("2021-12-31", 5), ("2022-12-31", 6)):
        tr, va, feats, cats, tgt, anc, label = build(
            "train_20260828b.csv", kind, tend, "2023-12-31", alpha)
        tr = tr[tr.base_dt >= pd.Timestamp("2017-01-01")]
        va = va[(va.base_dt > pd.Timestamp("2022-12-31")) & (va.lead_biz_d >= 3)].copy()
        cat_in = [c for c in cats if c in feats]
        ps = []
        for s in SEEDS:
            p = dict(T.PARAMS, seed=s, bagging_seed=s, feature_fraction_seed=s)
            m = lgb.train(p, lgb.Dataset(tr[feats], tr["y"], categorical_feature=cat_in),
                          num_boost_round=rounds)
            ps.append(va[anc].to_numpy(float) * np.exp(m.predict(va[feats])))
        pred = np.mean(ps, axis=0)
        act = va[tgt].to_numpy(float)
        ancv = va[anc].to_numpy(float)
        it_arr = va.item_nm.astype(str).to_numpy()
        line = "  2017~%s(%d년)" % (tend[:4], yrs)
        for it in ITEMS:
            k = it_arr == it
            wa, wmv = wm(act[k], ancv[k]), wm(act[k], pred[k])
            line += "%9.1f" % ((wa - wmv) / wa * 100)
        o.append(line)
    o.append("")
io.open("C:/Users/403/AppData/Local/Temp/span.txt", "w", encoding="utf-8").write("\n".join(o))
