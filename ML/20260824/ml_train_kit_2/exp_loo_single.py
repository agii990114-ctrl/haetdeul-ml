# -*- coding: utf-8 -*-
"""feature 하나씩 빼서 품목별로 잰다 — 백로그 [M-12] 남은 DoD (2026-09-03)

## 무엇을 재나

이름을 준 feature 를 **하나씩** 빼고, **품목별로** 성능을 봅니다.

    auc_vol_lag1          어제 경매 물량
    auc_prc_spread_lag1   등급 스프레드 (상품 - 중품)
    kimchi_season_yn      김장철 예/아니오

## 왜 하나씩인가 — 뭉치면 묻힌다

`auction` 그룹 6개를 통째로 빼면 **6개 중 1개가 해로워도 나머지에 묻힙니다.**
실제로 `calendar` 6개에서 그 일이 있었습니다 (2026-09-01) —

    뭉쳐서   A -0.0009 · B -0.0062   둘 다 음수 -> 제거 후보
    쪼개서   A +0.0004 · B -0.0056   부호 갈림  -> 판정 불가

**작은 양수 여럿이 큰 음수 하나에 묻혀 부호가 같아 보였습니다.**

## ★ 왜 품목별인가

`ablation_ops.py` 는 통합값만 냅니다. 그런데 오늘(2026-09-03) 명절 feature
에서 **품목마다 정반대**인 사례가 확인됐습니다 —

    소매가 통합   +0.0003   <- 아무 일도 없는 것처럼 보임
       속에서는   무 +0.0079  ·  배추 -0.0033  이 상쇄 중

통합값만 보면 이런 것을 놓칩니다 (CLAUDE.md 8절).

## 판정 (5.7절)

    두 폴드에서 부호가 같고, 합산이 시드 표준편차 x 2 를 넘을 것
    품목별로 본다. 통합값으로 결정하지 않는다

## 쓰는 법

    python exp_loo_single.py train_20260828b.csv
    python exp_loo_single.py train_20260828b.csv --feats kimchi_season_yn --seeds 62 63
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

#   운영이 실제로 쓰는 값. ablation_ops.py 와 같아야 한다
#   (5.12절 — 비교는 운영이 쓰는 자리에서 한다).
OPS = {"auc": (0.4, 76), "whsl": (0.8, 122), "rtl": (1.0, 81)}
FOLDS = [("A(검증2023)", "2022-12-31", "2023-12-31"),
         ("B(검증2022)", "2021-12-31", "2022-12-31")]
ITEMS = ["배추", "무", "양파"]
DEFAULT_FEATS = ["auc_vol_lag1", "auc_prc_spread_lag1", "kimchi_season_yn"]


def wmape(a, p):
    a, p = np.asarray(a, float), np.asarray(p, float)
    return float(np.abs(a - p).sum() / np.abs(a).sum())


def fit_per_item(tr, va, feats, cats, seeds, rounds, tgt, anc):
    """시드마다 학습하고 품목별 WMAPE 를 낸다."""
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


def verdict(rs):
    """5.7절 판정. rs = [(손실, 편차) x 폴드수]"""
    tot = sum(r[0] for r in rs)
    need = 2 * max(r[1] for r in rs)
    if (rs[0][0] > 0) != (rs[1][0] > 0):
        return tot, need, "판정 불가 (부호 갈림)"
    if abs(tot) < need:
        return tot, need, "판정 불가 (편차x2 미달)"
    return tot, need, ("★ 빼는 게 낫다" if tot > 0 else "★ 두는 게 낫다")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="feature 를 하나씩 빼서 품목별로 잰다 (운영 조건)")
    ap.add_argument("csv")
    ap.add_argument("--targets", nargs="+", default=["auc", "whsl", "rtl"])
    ap.add_argument("--feats", nargs="+", default=DEFAULT_FEATS)
    ap.add_argument("--train-start", default="2017-01-01")
    ap.add_argument("--gate-lt", type=int, default=3)
    ap.add_argument("--seeds", nargs="+", type=int, default=list(range(62, 82)))
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    print("=" * 88)
    print("[feature 개별 판정] 하나씩 빼기 · 품목별 · 운영 조건")
    print(f"  시드 {len(a.seeds)}개 ({a.seeds[0]}~{a.seeds[-1]}) · LT>={a.gate_lt}"
          f" · 학습 {a.train_start}~")
    print(f"  대상 feature: {', '.join(a.feats)}")
    print("  ※ 양수 = 빼는 게 낫다.  통합값으로 결정하지 않습니다 (8절)")
    print("=" * 88)

    rows = []
    for kind in a.targets:
        alpha, rounds = OPS[kind]
        keep = {}
        for tag, tend, vend in FOLDS:
            tr, va, feats, cats, tgt, anc, label = build(a.csv, kind, tend, vend, alpha)
            tr = tr[tr.base_dt >= pd.Timestamp(a.train_start)]
            va = va[va.lead_biz_d >= a.gate_lt].copy()
            print(f"\n  [{label} · 폴드 {tag}]  α={alpha} · {rounds}그루"
                  f" · 학습 {len(tr):,}행 · 검증 {len(va):,}행")

            base = fit_per_item(tr, va, feats, cats, a.seeds, rounds, tgt, anc)
            print(f"    {'':<22}{'배추':>10}{'무':>10}{'양파':>10}{'통합':>10}")
            print("    %-22s" % "(전부 넣은 값)"
                  + "".join("%10.4f" % base[k][0] for k in ITEMS + ["통합"]))

            for f in a.feats:
                if f not in feats:
                    print(f"    {f:<22}  이 타겟 feature 에 없음 — 건너뜀")
                    continue
                sub = [c for c in feats if c != f]
                r = fit_per_item(tr, va, sub, cats, a.seeds, rounds, tgt, anc)
                line = "    %-22s" % ("- " + f)
                for k in ITEMS + ["통합"]:
                    gain = base[k][0] - r[k][0]       # 양수 = 빼는 게 낫다
                    line += "%+10.4f" % gain
                    keep.setdefault((f, k), []).append(
                        (gain, max(base[k][1], r[k][1])))
                    rows.append(dict(target=kind, fold=tag, feat=f, item=k,
                                     wmape_keep=round(base[k][0], 5),
                                     wmape_drop=round(r[k][0], 5),
                                     gain=round(gain, 5)))
                print(line)

        print(f"\n  [{label} 판정]  (양수 = 빼는 게 낫다)")
        print(f"    {'feature':<22}{'품목':<6}{'폴드A':>10}{'폴드B':>10}"
              f"{'합산':>10}{'필요':>9}  판정")
        for f in a.feats:
            for it in ITEMS + ["통합"]:
                rs = keep.get((f, it))
                if not rs or len(rs) < 2:
                    continue
                tot, need, v = verdict(rs)
                print(f"    {f:<22}{it:<6}{rs[0][0]:>+10.4f}{rs[1][0]:>+10.4f}"
                      f"{tot:>+10.4f}{need:>9.4f}  {v}")

    if a.out:
        pd.DataFrame(rows).to_csv(a.out, index=False, encoding="utf-8-sig")
        print(f"\n[저장] {a.out}")
    print("\n" + "=" * 88)
    print("  판정 불가(△)는 '기여 없음' 이 아닙니다. 증명하지 못했을 뿐입니다 (11절)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
