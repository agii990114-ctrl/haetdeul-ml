# -*- coding: utf-8 -*-
"""경락가를 둘로 나누고 양파에 제 조절값을 준다 — [M-13] ④ + [M-23]

## 두 발견이 같은 곳을 가리킵니다

**M-23 (2026-09-02)** 은 경락가에서 *"덜 외우게"* 설정을 찾았고 폴드 C 까지
통과했는데 **보류**했습니다. 이유가 이랬습니다.

    폴드 C 이득의 출처   양파 +0.0139 · 무 +0.0016 · 배추 -0.0009
    그래서              "양파가 거의 다 만든 값" · "품목별로 갈려 보류"

**오늘 M-13 ④** 는 경락가에서 **양파만 분리가 3폴드를 통과**했습니다
(+7.19 / +5.48 / +19.20%). 그리고 왜 양파만인지도 나왔습니다.

    경락 하루변화   배추 11.93% · 무 11.09%  vs  양파 4.32%   (2.7배)

**같은 신호입니다.** 한 모델이 셋을 맞히려니 조절값도 절충이고, 그 절충이
양파에 해롭습니다. **나누면 양파에 제 조절값을 줄 수 있습니다.**

## 그래서 셋을 견줍니다

    현행       셋 묶음 · 기본 조절값
    나눔       배추·무 묶음 + 양파 전용 · 둘 다 기본 조절값
    나눔+조절   배추·무 묶음(기본) + 양파 전용(M-23 이 찾은 "덜 외우게")

**나눔+조절이 나눔보다 나아야** M-23 설정을 쓸 이유가 생깁니다.
그냥 나누기만 해도 되면 조절값은 안 건드립니다 — 손잡이는 적을수록 좋습니다.

    python exp_onion_model.py <csv> --folds A B C
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

ALL_FOLDS = {
    "A": ("A(검증2023)", "2022-12-31", "2023-12-31"),
    "B": ("B(검증2022)", "2021-12-31", "2022-12-31"),
    "C": ("C(검증2021)", "2020-12-31", "2021-12-31"),
}
ITEMS = ["배추", "무", "양파"]
PAIR = ["배추", "무"]

#: M-23 이 198회 탐색해 찾은 것 (2026-09-02). 폴드 C 까지 통과했으나
#: "품목별로 갈려" 보류했다. 바뀐 넷이 전부 **덜 외우게** 하는 방향이다.
TUNED = dict(num_leaves=45, lambda_l2=30.0,
             feature_fraction=0.5, bagging_fraction=0.7)
TUNED_ROUNDS = 50
BASE_ROUNDS = 76          # 운영 경락가
ALPHA = 0.4               # 운영 경락가 수축 앵커


def wmape(a, p):
    a, p = np.asarray(a, float), np.asarray(p, float)
    return float(np.abs(a - p).sum() / np.abs(a).sum())


def train_predict(tr, va, feats, cats, seed, rounds, extra, tgt, anc):
    p = dict(T.PARAMS, seed=seed, bagging_seed=seed, feature_fraction_seed=seed)
    p.update(extra or {})
    cat_in = [c for c in cats if c in feats]
    m = lgb.train(p, lgb.Dataset(tr[feats], tr["y"], categorical_feature=cat_in),
                  num_boost_round=rounds)
    return va[anc].to_numpy(float) * np.exp(m.predict(va[feats]))


def main() -> int:
    ap = argparse.ArgumentParser(description="경락 양파 전용 모델 + 조절값")
    ap.add_argument("csv")
    ap.add_argument("--train-start", default="2017-01-01")
    ap.add_argument("--gate-lt", type=int, default=3)
    ap.add_argument("--seeds", nargs="+", type=int, default=list(range(62, 72)))
    ap.add_argument("--folds", nargs="+", default=["A", "B", "C"],
                    choices=["A", "B", "C"])
    a = ap.parse_args()
    folds = [ALL_FOLDS[f] for f in a.folds]

    print("=" * 92)
    print("[경락 양파 전용 모델] 현행 vs 나눔 vs 나눔+조절 · 운영 조건")
    print(f"  시드 {len(a.seeds)}개 · LT>={a.gate_lt} · α={ALPHA} · 폴드 {' '.join(a.folds)}")
    print("  M-23 조절값: 트리 76→50 · 잎 31→45 · L2 1.0→30 · feature 0.8→0.5 · 표본 0.8→0.7")
    print("  값은 WMAPE — 작을수록 좋습니다")
    print("=" * 92)

    tally: dict[tuple, list] = {}
    for tag, tend, vend in folds:
        tr, va, feats, cats, tgt, anc, label = build(a.csv, "auc", tend, vend, ALPHA)
        tr = tr[tr.base_dt >= pd.Timestamp(a.train_start)]
        va = va[va.lead_biz_d >= a.gate_lt].copy()
        items = va["item_nm"].astype(str).to_numpy()
        actual = va[tgt].to_numpy(float)

        #   나눈 모델은 item_nm 이 상수가 되므로 뺀다
        f2 = [c for c in feats if c != "item_nm"]
        c2 = [c for c in cats if c != "item_nm"]
        tr_pair = tr[tr.item_nm.astype(str).isin(PAIR)]
        tr_on = tr[tr.item_nm.astype(str) == "양파"]
        va_on = va[va.item_nm.astype(str) == "양파"]

        res = {k: {i: [] for i in ITEMS} for k in ("현행", "나눔", "나눔+조절")}
        for s in a.seeds:
            #   현행 — 셋 묶음
            pred = train_predict(tr, va, feats, cats, s, BASE_ROUNDS, None, tgt, anc)
            for it in ITEMS:
                k = items == it
                if k.sum():
                    res["현행"][it].append(wmape(actual[k], pred[k]))
            #   배추·무 묶음 (나눔 · 나눔+조절 공통)
            pp = train_predict(tr_pair, va, f2, c2, s, BASE_ROUNDS, None, tgt, anc)
            for it in PAIR:
                k = items == it
                if k.sum():
                    v = wmape(actual[k], pp[k])
                    res["나눔"][it].append(v)
                    res["나눔+조절"][it].append(v)
            #   양파 — 기본 조절값 / M-23 조절값
            ao = va_on[tgt].to_numpy(float)
            po1 = train_predict(tr_on, va_on, f2, c2, s, BASE_ROUNDS, None, tgt, anc)
            po2 = train_predict(tr_on, va_on, f2, c2, s, TUNED_ROUNDS, TUNED, tgt, anc)
            res["나눔"]["양파"].append(wmape(ao, po1))
            res["나눔+조절"]["양파"].append(wmape(ao, po2))

        print(f"\n  [{label} · 폴드 {tag}]  학습 셋 {len(tr):,} · 둘 {len(tr_pair):,}"
              f" · 양파 {len(tr_on):,}행")
        print("      %-10s%11s%11s%11s" % ("", *ITEMS))
        for k in ("현행", "나눔", "나눔+조절"):
            print("      %-10s" % k
                  + "".join("%11.4f" % st.mean(res[k][it]) for it in ITEMS))
        for k in ("나눔", "나눔+조절"):
            cells = []
            for it in ITEMS:
                g, s2 = st.mean(res["현행"][it]), st.mean(res[k][it])
                imp = (g - s2) / g * 100
                sd = (st.pstdev(res["현행"][it]) + st.pstdev(res[k][it])) / 2 / g * 100
                cells.append("%+10.2f%%" % imp)
                tally.setdefault((k, it), []).append((imp, sd))
            print("      %-10s" % ("↑ " + k) + "".join(cells))

    print("\n" + "=" * 92)
    print("[3폴드 판정] 현행 대비 · 부호 일치 + 편차x2")
    print("=" * 92)
    for (k, item), pairs in sorted(tally.items()):
        vals = [p[0] for p in pairs]
        sds = [p[1] for p in pairs]
        same = all(v > 0 for v in vals) or all(v < 0 for v in vals)
        need = 2 * (sum(s * s for s in sds) ** 0.5)
        got = abs(sum(vals))
        mark = ("★ 갈림 — 판정 불가" if not same else
                "부호는 같으나 편차x2 미달 (%.2f < %.2f)" % (got, need) if got < need else
                ("★ 통과 — 낫다" if vals[0] > 0 else "★ 통과 — 나쁘다"))
        print("  %-10s %-3s  %s  합%+7.2f 필요%6.2f   %s"
              % (k, item, " ".join("%+7.2f%%" % v for v in vals),
                 sum(vals), need, mark))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
