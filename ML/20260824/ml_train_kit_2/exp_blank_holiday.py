# -*- coding: utf-8 -*-
"""명절 feature 를 무 행에서만 비우기 — 재확인 (2026-09-03)

## 무엇을 재나

`holiday_remain_d`(명절까지 남은 날) 를 **무 행에서만 결측으로 두는 것**이
정말 도움이 되는지 봅니다.

## 왜 이 처방이 나왔나

9/1 개별 판정에서 **품목마다 정반대**로 나왔습니다.
(`holiday_remain_d` 를 통째로 뺐을 때의 손실 · 음수 = 빼는 게 나음)

    무    6/6 조합 음수      빼는 게 낫다
    양파  5/6 조합 양수      있어야 한다
    배추  4/6 음수           애매

**통합 판정이 "제거 후보" 로 나온 건 무가 만든 값**이었고, 그대로 빼면
양파가 손해를 봅니다. **"빼기/두기" 가 답이 아닌 첫 사례**입니다.

LightGBM 은 결측을 그대로 다루므로, **무 행에서만 NaN 으로 두면**
단일 모델을 유지하면서 품목별로 다르게 줄 수 있습니다.

## ★ 왜 다시 재나 — 다중비교 위험

18개 조합(3품목 × 3타겟 × 2폴드)을 **보고 나서** "무가 6/6 음수" 를
골랐습니다. 우연히 한 품목이 6/6 이 될 확률이 품목 3개 기준 약 5% 입니다.

**골라낸 뒤 같은 시드로 다시 재면 같은 답이 나옵니다. 그건 확인이 아닙니다.**
그래서 **처음 쓴 적 없는 시드(62~81)** 로 다시 잽니다.

## 판정 기준 (§5.7)

    두 폴드에서 부호가 같고, 합산이 시드 표준편차 x 2 를 넘을 것
    ★ 그리고 **품목별로** 본다. 통합값으로 결정하지 않는다 (§8)

## 쓰는 법

    python exp_blank_holiday.py train_20260828b.csv
    python exp_blank_holiday.py train_20260828b.csv --seeds 62 63 64   # 빨리 보기
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

#   운영이 실제로 쓰는 값. ablation_ops.py 와 같아야 한다 (§5.12 — 비교는
#   운영이 쓰는 자리에서 한다).
OPS = {"auc": (0.4, 76), "whsl": (0.8, 122), "rtl": (1.0, 81)}
#   ★ 폴드 C 를 쓸 수 있게 한다 (2026-09-03).
#     같은 날 2폴드를 통과한 후보 둘(M-06 · M-15 mix_yr)이 **모두 폴드 C 에서
#     뒤집혔다.** 특히 M-15 는 A·B 가 둘 다 양수이고 새 시드로 재현까지 됐다.
#     운영에 넣을 것은 폴드 C 를 반드시 본다.
ALL_FOLDS = {
    "A": ("A(검증2023)", "2022-12-31", "2023-12-31"),
    "B": ("B(검증2022)", "2021-12-31", "2022-12-31"),
    "C": ("C(검증2021)", "2020-12-31", "2021-12-31"),
}
FOLDS = [ALL_FOLDS["A"], ALL_FOLDS["B"]]
COL = "holiday_remain_d"
ITEMS = ["배추", "무", "양파"]


def wmape(a, p):
    a, p = np.asarray(a, float), np.asarray(p, float)
    return float(np.abs(a - p).sum() / np.abs(a).sum())


def fit_per_item(tr, va, feats, cats, seeds, rounds, tgt, anc):
    """시드마다 학습하고 **품목별** WMAPE 를 낸다.

    ★ 통합값도 같이 내지만 판정은 품목별로 한다. 마늘 사례처럼
      가격 수준이 높은 품목이 분모를 지배할 수 있다 (§8).
    """
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
    out = {}
    for it in ITEMS:
        v = per[it]
        out[it] = (st.mean(v), st.pstdev(v) if len(v) > 1 else 0.0) if v else (float("nan"), 0.0)
    out["통합"] = (st.mean(pooled), st.pstdev(pooled) if len(pooled) > 1 else 0.0)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(
        description="명절 feature 를 무 행에서만 비우는 처방을 새 시드로 재확인")
    ap.add_argument("csv")
    ap.add_argument("--targets", nargs="+", default=["auc", "whsl", "rtl"])
    ap.add_argument("--train-start", default="2017-01-01")
    ap.add_argument("--gate-lt", type=int, default=3)
    #   ★ 9/1 판정에 쓴 시드(42~51)와 **겹치지 않게** 한다.
    #     같은 시드로 다시 재면 같은 답이 나오고, 그건 확인이 아니다.
    ap.add_argument("--seeds", nargs="+", type=int,
                    default=list(range(62, 82)))
    ap.add_argument("--blank-items", nargs="+", default=["무"],
                    help="이 품목의 행에서만 명절 feature 를 비운다")
    ap.add_argument("--folds", nargs="+", default=["A", "B"], choices=["A", "B", "C"])
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    folds = [ALL_FOLDS[f] for f in a.folds]

    print("=" * 88)
    print("[명절 feature 재확인] 무 행에서만 비우기 · 운영 조건")
    print(f"  시드 {len(a.seeds)}개 ({a.seeds[0]}~{a.seeds[-1]}) · LT>={a.gate_lt}"
          f" · 학습 {a.train_start}~ · 비우는 품목 {', '.join(a.blank_items)}")
    print("  ※ 9/1 판정은 시드 42~51 이었습니다. 새 시드로 다시 잽니다")
    print("=" * 88)

    rows = []
    for kind in a.targets:
        alpha, rounds = OPS[kind]
        keep = {}
        for tag, tend, vend in folds:
            tr, va, feats, cats, tgt, anc, label = build(a.csv, kind, tend, vend, alpha)
            tr = tr[tr.base_dt >= pd.Timestamp(a.train_start)]
            va = va[va.lead_biz_d >= a.gate_lt].copy()
            if COL not in feats:
                sys.exit(f"{COL} 이 feature 에 없습니다 — 조건을 확인하세요")

            print(f"\n  [{label} · 폴드 {tag}]  α={alpha} · {rounds}그루"
                  f" · 학습 {len(tr):,}행 · 검증 {len(va):,}행")

            base = fit_per_item(tr, va, feats, cats, a.seeds, rounds, tgt, anc)

            #   ★ 학습·검증 **양쪽** 에서 비운다. 한쪽만 비우면 학습 때 본 것과
            #     예측 때 주는 것이 달라져 그 자체가 성능을 떨어뜨린다.
            m_tr = tr["item_nm"].astype(str).isin(a.blank_items)
            m_va = va["item_nm"].astype(str).isin(a.blank_items)
            tr2 = tr.copy()
            va2 = va.copy()
            tr2.loc[m_tr, COL] = np.nan
            va2.loc[m_va, COL] = np.nan
            blank = fit_per_item(tr2, va2, feats, cats, a.seeds, rounds, tgt, anc)

            print(f"    {'품목':<6}{'그대로':>10}{'비움':>10}{'개선':>11}{'시드편차':>10}")
            for it in ITEMS + ["통합"]:
                b, sd_b = base[it]
                q, sd_q = blank[it]
                gain = b - q                       # 양수 = 비우는 게 낫다
                sd = max(sd_b, sd_q)
                print(f"    {it:<6}{b:>10.4f}{q:>10.4f}{gain:>+11.4f}{sd:>10.4f}")
                keep.setdefault(it, []).append((gain, sd))
                rows.append(dict(target=kind, fold=tag, item=it,
                                 wmape_keep=round(b, 5), wmape_blank=round(q, 5),
                                 gain=round(gain, 5), sd=round(sd, 5)))

        print(f"\n  [{label} 판정]  (양수 = 무 행에서 비우는 게 낫다)")
        print(f"    {'품목':<6}" + "".join("%11s" % ("폴드" + f) for f in a.folds)
              + f"{'합산':>11}{'필요':>10}  판정")
        for it in ITEMS + ["통합"]:
            rs = keep[it]
            tot = sum(r[0] for r in rs)
            need = 2 * max(r[1] for r in rs)
            same = len({r[0] > 0 for r in rs}) == 1
            if not same:
                verd = "판정 불가 (부호 갈림)"
            elif abs(tot) < need:
                verd = "판정 불가 (편차x2 미달)"
            else:
                verd = "★ 비우는 게 낫다" if tot > 0 else "★ 그대로 두는 게 낫다"
            print(f"    {it:<6}" + "".join("%+11.4f" % r[0] for r in rs)
                  + f"{tot:>+11.4f}{need:>10.4f}  {verd}")

    if a.out:
        pd.DataFrame(rows).to_csv(a.out, index=False, encoding="utf-8-sig")
        print(f"\n[저장] {a.out}")
    print("\n" + "=" * 88)
    print("  판정은 품목별로 봅니다. 통합값으로 결정하지 마세요 (§8).")
    print("  두 폴드 부호가 같고 합산이 편차x2 를 넘을 때만 채택합니다 (§5.7).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
