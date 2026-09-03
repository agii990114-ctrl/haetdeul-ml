# -*- coding: utf-8 -*-
"""김장철 정의를 바꿔가며 잰다 — 백로그 [M-07] (2026-09-03)

## 왜 하나

지금 정의는 **해마다 똑같은 달력 구간**입니다.

    kimchi_season_yn = 1   WHEN 대상일이 11월 전체 OR 12월 1~15일

2026-09-03 개별 판정에서 이 feature 가 **24칸 전부 판정 불가**로 나왔습니다.
"쓸모없다" 가 아니라 **"이 정의로는 증명 못 했다"** 일 수 있어 정의를 바꿔 봅니다.

## 자료로 먼저 본 것

배추 반입량이 그 해 중앙값의 1.3배를 넘는 구간은 **9월~12월 중순**입니다
(9~14주). 지금 창은 그중 **44~64% 만** 덮습니다.

    2017  09-05 ~ 12-08   64% 덮음
    2023  09-01 ~ 12-15   44% 덮음

★ 다만 9~10월 반입량은 **가을배추 수확** 때문일 수 있습니다. 그건 공급이지
김장 수요가 아닙니다. 반입량만으로는 갈라지지 않으므로 **붙여서 재봅니다.**

한편 반입량 **최대 주**는 2017~2024 내내 47~48주로 아주 안정적이고
2025 만 43주였습니다. 백로그의 "해마다 1~2주 이동" 은 실제보다 세게
적힌 표현으로 보입니다.

## 무엇을 견주나

    keep      현행 그대로 (11/1~12/15)                <- 기준
    drop      김장 feature 를 뺀다
    wide      창을 넓힌다 (10/1~12/15)
    month     현행 + 대상일 '월' (categorical 12개)
    week      현행 + 대상일 '주차' (숫자 1~53)

★ month·week 는 김장 전용이 아니라 **일반 계절 정보**입니다.
  "모델이 계절을 못 보고 있나" 를 같이 묻는 셈입니다.
  단, 주차는 값이 53개라 기준일 1,475개에는 과할 수 있습니다.

## 판정 (5.7절 · 8절)

    두 폴드 부호가 같고 합산이 시드 표준편차 x 2 를 넘을 것. **품목별로** 본다.

## 쓰는 법

    python exp_kimchi_def.py train_20260828b.csv
    python exp_kimchi_def.py train_20260828b.csv --targets rtl --seeds 62 63
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
FOLDS = [("A(검증2023)", "2022-12-31", "2023-12-31"),
         ("B(검증2022)", "2021-12-31", "2022-12-31")]
ITEMS = ["배추", "무", "양파"]
COL = "kimchi_season_yn"
VARIANTS = ["keep", "drop", "wide", "month", "week"]


def wmape(a, p):
    a, p = np.asarray(a, float), np.asarray(p, float)
    return float(np.abs(a - p).sum() / np.abs(a).sum())


def make_variant(tr, va, feats, cats, kind):
    """정의를 바꾼 (학습, 검증, feature, cat) 을 돌려준다.

    ★ 학습·검증 **양쪽** 에 똑같이 적용한다. 한쪽만 바꾸면 학습 때 본 것과
      예측 때 주는 것이 달라져 그 자체가 성능을 떨어뜨린다.
    """
    t, v = tr.copy(), va.copy()
    f, c = list(feats), list(cats)
    if kind == "keep":
        return t, v, f, c
    if kind == "drop":
        return t, v, [x for x in f if x != COL], c
    if kind == "wide":
        #   10/1 ~ 12/15 로 넓힌다
        for d in (t, v):
            td = pd.to_datetime(d["target_dt"])
            d[COL] = (((td.dt.month.isin([10, 11]))
                       | ((td.dt.month == 12) & (td.dt.day <= 15)))
                      .astype(int))
        return t, v, f, c
    if kind == "month":
        for d in (t, v):
            d["_mon"] = pd.to_datetime(d["target_dt"]).dt.month.astype("category")
        return t, v, f + ["_mon"], c + ["_mon"]
    if kind == "week":
        for d in (t, v):
            d["_wk"] = (pd.to_datetime(d["target_dt"])
                        .dt.isocalendar().week.astype(int))
        return t, v, f + ["_wk"], c
    raise SystemExit("모르는 변형: " + kind)


def fit_per_item(tr, va, feats, cats, seeds, rounds, tgt, anc):
    ancv = va[anc].to_numpy(float)
    actual = va[tgt].to_numpy(float)
    items = va["item_nm"].astype(str).to_numpy()
    cat_in = [c for c in cats if c in feats]
    per = {it: [] for it in ITEMS}
    pooled = []
    for s in seeds:
        p = dict(T.PARAMS, seed=s, bagging_seed=s, feature_fraction_seed=s)
        m = lgb.train(p, lgb.Dataset(tr[feats], tr["y"], categorical_feature=cat_in),
                      num_boost_round=rounds)
        pred = ancv * np.exp(m.predict(va[feats]))
        pooled.append(wmape(actual, pred))
        for it in ITEMS:
            k = items == it
            if k.sum():
                per[it].append(wmape(actual[k], pred[k]))
    out = {it: (st.mean(v), st.pstdev(v) if len(v) > 1 else 0.0)
           for it, v in per.items() if v}
    out["통합"] = (st.mean(pooled), st.pstdev(pooled) if len(pooled) > 1 else 0.0)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="김장철 정의를 바꿔가며 잰다")
    ap.add_argument("csv")
    ap.add_argument("--targets", nargs="+", default=["auc", "whsl", "rtl"])
    ap.add_argument("--variants", nargs="+", default=VARIANTS)
    ap.add_argument("--train-start", default="2017-01-01")
    ap.add_argument("--gate-lt", type=int, default=3)
    ap.add_argument("--seeds", nargs="+", type=int, default=list(range(62, 82)))
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    print("=" * 92)
    print("[김장철 정의 비교] 운영 조건 · 품목별")
    print(f"  시드 {len(a.seeds)}개 ({a.seeds[0]}~{a.seeds[-1]}) · LT>={a.gate_lt}"
          f" · 학습 {a.train_start}~")
    print("  현행 = 11/1~12/15 고정 창.  양수 = 현행보다 낫다")
    print("=" * 92)

    rows = []
    for kind in a.targets:
        alpha, rounds = OPS[kind]
        keep = {}
        for tag, tend, vend in FOLDS:
            tr, va, feats, cats, tgt, anc, label = build(a.csv, kind, tend, vend, alpha)
            tr = tr[tr.base_dt >= pd.Timestamp(a.train_start)]
            va = va[va.lead_biz_d >= a.gate_lt].copy()
            if COL not in feats:
                sys.exit(f"{COL} 이 feature 에 없습니다")
            print(f"\n  [{label} · 폴드 {tag}]  α={alpha} · {rounds}그루"
                  f" · 학습 {len(tr):,}행 · 검증 {len(va):,}행")
            print(f"    {'':<10}{'배추':>10}{'무':>10}{'양파':>10}{'통합':>10}")

            base = None
            for vname in a.variants:
                t2, v2, f2, c2 = make_variant(tr, va, feats, cats, vname)
                r = fit_per_item(t2, v2, f2, c2, a.seeds, rounds, tgt, anc)
                if vname == "keep":
                    base = r
                    print("    %-10s" % "현행"
                          + "".join("%10.4f" % r[k][0] for k in ITEMS + ["통합"]))
                    continue
                line = "    %-10s" % vname
                for k in ITEMS + ["통합"]:
                    gain = base[k][0] - r[k][0]      # 양수 = 이 변형이 낫다
                    line += "%+10.4f" % gain
                    keep.setdefault((vname, k), []).append(
                        (gain, max(base[k][1], r[k][1])))
                    rows.append(dict(target=kind, fold=tag, variant=vname, item=k,
                                     wmape_keep=round(base[k][0], 5),
                                     wmape_var=round(r[k][0], 5),
                                     gain=round(gain, 5)))
                print(line)

        print(f"\n  [{label} 판정]  (양수 = 현행보다 낫다)")
        print(f"    {'변형':<10}{'품목':<6}{'폴드A':>10}{'폴드B':>10}"
              f"{'합산':>10}{'필요':>9}  판정")
        for vname in a.variants:
            if vname == "keep":
                continue
            for it in ITEMS + ["통합"]:
                rs = keep.get((vname, it))
                if not rs or len(rs) < 2:
                    continue
                tot = rs[0][0] + rs[1][0]
                need = 2 * max(r[1] for r in rs)
                if (rs[0][0] > 0) != (rs[1][0] > 0):
                    v = "판정 불가 (부호 갈림)"
                elif abs(tot) < need:
                    v = "판정 불가 (편차x2 미달)"
                else:
                    v = "★ 이 변형이 낫다" if tot > 0 else "★ 현행이 낫다"
                print(f"    {vname:<10}{it:<6}{rs[0][0]:>+10.4f}{rs[1][0]:>+10.4f}"
                      f"{tot:>+10.4f}{need:>9.4f}  {v}")

    if a.out:
        pd.DataFrame(rows).to_csv(a.out, index=False, encoding="utf-8-sig")
        print(f"\n[저장] {a.out}")
    print("\n" + "=" * 92)
    print("  통합값으로 결정하지 않습니다 (8절). 판정 불가는 '기여 없음' 이 아닙니다 (11절)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
