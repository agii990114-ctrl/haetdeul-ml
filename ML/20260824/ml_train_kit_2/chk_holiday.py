# -*- coding: utf-8 -*-
"""holiday_remain_d 제거를 품목별로 확인 (2026-09-01)

20시드 2폴드에서 중도매가 제거 후보로 나왔다 (합산 −0.0048 · 필요 0.0040).
**한 품목이 만든 값인지 본다** (CLAUDE.md §8).
"""
import statistics as st, sys
import lightgbm as lgb, numpy as np, pandas as pd
sys.path.insert(0, ".")
import train as T
from exp_quantile import build

CSV = "../../../실험결과/train_clim_20260831.csv"
COL = "holiday_remain_d"
import os
#   ★ 다른 시드로 재확인한다. 18개 조합(3품목 × 3타겟 × 2폴드)을 놓고
#   "무가 6/6 음수" 를 골랐는데, 우연히 어떤 품목이 한 방향으로 몰릴 확률이
#   품목 3개 기준 약 5% 다. 여러 개를 놓고 제일 그럴듯한 걸 고르면
#   우연도 그럴듯해 보인다. 그래서 **본 적 없는 시드로 다시 잰다.**
SEEDS = [int(x) for x in os.environ.get("CHK_SEEDS", "").split()] or list(range(42, 62))
ITEMS = ["배추", "무", "양파"]


def wm(a, p):
    return np.abs(a - p).sum() / np.abs(a).sum()


def run(tr, va, feats, cats, tgt, anc, rounds):
    ancv, act = va[anc].to_numpy(float), va[tgt].to_numpy(float)
    per = {it: [] for it in ITEMS}
    tot = []
    for s in SEEDS:
        p = dict(T.PARAMS, seed=s, bagging_seed=s, feature_fraction_seed=s)
        m = lgb.train(p, lgb.Dataset(tr[feats], tr["y"],
                                     categorical_feature=[c for c in cats if c in feats]),
                      num_boost_round=rounds)
        pr = ancv * np.exp(m.predict(va[feats]))
        tot.append(wm(act, pr))
        for it in ITEMS:
            k = (va.item_nm == it).to_numpy()
            per[it].append(wm(act[k], pr[k]))
    return tot, per


for kind, alpha, rounds in [("whsl", 0.8, 122), ("auc", 0.4, 76), ("rtl", 1.0, 81)]:
    print("=" * 66)
    for tag, tend, vend in [("A(2023)", "2022-12-31", "2023-12-31"),
                            ("B(2022)", "2021-12-31", "2022-12-31")]:
        tr, va, feats, cats, tgt, anc, label = build(CSV, kind, tend, vend, alpha)
        tr = tr[tr.base_dt >= pd.Timestamp("2017-01-01")]
        va = va[va.lead_biz_d >= 3].copy()
        if COL not in feats:
            print("  %s: %s 가 입력에 없습니다" % (label, COL))
            break
        t0, p0 = run(tr, va, feats, cats, tgt, anc, rounds)
        t1, p1 = run(tr, va, [c for c in feats if c != COL], cats, tgt, anc, rounds)
        print("  [%s · 폴드 %s]  %s 를 뺐을 때" % (label, tag, COL))
        print("    %-6s%10s%10s%11s%10s" % ("", "있을 때", "뺐을 때", "손실", "편차×2"))
        for nm, a, b in [("전체", t0, t1)] + [(it, p0[it], p1[it]) for it in ITEMS]:
            loss = st.mean(b) - st.mean(a)      # 양수면 있어야 좋다
            sd2 = 2 * max(st.pstdev(a), st.pstdev(b))
            mk = "O 유지" if loss > sd2 else ("X 빼자" if -loss > sd2 else "ㅡ")
            print("    %-6s%10.4f%10.4f%+11.4f%10.4f  %s"
                  % (nm, st.mean(a), st.mean(b), loss, sd2, mk))
