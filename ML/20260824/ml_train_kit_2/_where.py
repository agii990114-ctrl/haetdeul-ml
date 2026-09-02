# -*- coding: utf-8 -*-
"""오차가 어디에 몰려 있나. 고칠 곳을 정하려면 이걸 먼저 봐야 한다."""
import numpy as np
import pandas as pd
import lightgbm as lgb
from train import TARGETS, TARGET_DROP, CAT, PARAMS, DROP as BASE_DROP, load, wmape
import train as _train

CSV = "train_20260828b.csv"
TARGET, ANCHOR, _ = TARGETS["auc"]
AVG7 = "auc_prc_avg7"
ALPHA = 0.4

DROP = set(BASE_DROP) | set(TARGET_DROP["auc"]) | set(_train.NEW_PRICE_COLS)
df = load(CSV, target=TARGET, anchor=ANCHOR)
df = df[df.item_nm.astype(str).isin(["배추", "양파", "무"])].copy()
df = df[df.base_dt >= "2017-01-01"]
df["_anc"] = ALPHA * df[ANCHOR] + (1 - ALPHA) * df[AVG7]
df = df[(df[TARGET] > 0) & (df["_anc"] > 0)].copy()
df["y"] = np.log(df[TARGET] / df["_anc"])
DROP |= {ANCHOR, "_anc", "y"}
feats = [c for c in df.columns if c not in DROP]
cats = [c for c in CAT if c in feats]

tr = df[df.base_dt <= "2022-12-31"]
va = df[(df.base_dt > "2022-12-31") & (df.base_dt <= "2023-12-31")].copy()
preds = []
for s in (42, 43, 44):
    p = dict(PARAMS, seed=s, bagging_seed=s, feature_fraction_seed=s)
    m = lgb.train(p, lgb.Dataset(tr[feats], tr.y, categorical_feature=cats),
                  num_boost_round=3000,
                  valid_sets=[lgb.Dataset(va[feats], va.y)],
                  callbacks=[lgb.early_stopping(200, verbose=False)])
    preds.append(va["_anc"].values * np.exp(m.predict(va[feats])))
va["pred"] = np.mean(preds, axis=0)
g = va.lead_biz_d.values < 3
va.loc[g, "pred"] = va.loc[g, "_anc"]
va["err"] = (va.pred - va[TARGET]).abs()

tot = va.err.sum()
print(f"검증 {len(va):,}행 · 전체 오차율 {tot / va[TARGET].sum() * 100:.1f}%")
print()

print("[1] 오차 상위 x% 가 전체 오차의 몇 % 를 차지하나")
s = va.err.sort_values(ascending=False)
for q in (0.01, 0.05, 0.10, 0.20):
    k = int(len(s) * q)
    print(f"  상위 {q*100:>4.0f}% ({k:>5,}행)   전체 오차의 {s[:k].sum()/tot*100:>5.1f}%")
print()

print("[2] 변동성 구간별  (7일 표준편차 ÷ 7일평균)")
va["vol"] = va.auc_prc_std7 / va.auc_prc_avg7
va["q"] = pd.qcut(va.vol, 5, labels=["1 조용", "2", "3", "4", "5 요동"])
for lab, sub in va.groupby("q", observed=True):
    print(f"  {lab:<7} 오차율 {wmape(sub[TARGET], sub.pred)*100:>5.1f}% · "
          f"앵커 {wmape(sub[TARGET], sub['_anc'])*100:>5.1f}% · "
          f"전체오차의 {sub.err.sum()/tot*100:>4.1f}%")
print()

print("[3] 품목별")
for it, sub in va.groupby("item_nm", observed=True):
    print(f"  {str(it):<4} 오차율 {wmape(sub[TARGET], sub.pred)*100:>5.1f}% · "
          f"전체오차의 {sub.err.sum()/tot*100:>4.1f}% · 평균가 {sub[TARGET].mean():>6.0f}원")
print()

print("[4] 리드타임 묶음별")
va["ltg"] = pd.cut(va.lead_biz_d, [0, 2, 6, 12, 18],
                   labels=["1-2 게이트", "3-6", "7-12", "13-18"])
for lab, sub in va.groupby("ltg", observed=True):
    print(f"  {lab:<10} 오차율 {wmape(sub[TARGET], sub.pred)*100:>5.1f}% · "
          f"전체오차의 {sub.err.sum()/tot*100:>4.1f}%")
