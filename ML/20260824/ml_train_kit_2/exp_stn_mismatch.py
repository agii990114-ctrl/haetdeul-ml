# -*- coding: utf-8 -*-
"""주산지 매핑이 어긋난 구간에서 실제로 더 틀리나 — 백로그 [M-05] (2026-09-03)

## 왜 이걸 먼저 재나

매핑을 고치려면 SQL(`ref_item_station`)을 바꾸고 학습표를 다시 만들어야
합니다. **그 전에 "어긋남이 실제로 손해를 내고 있나" 를 먼저 봅니다.**
손해가 없으면 고칠 이유가 없습니다.

## 무엇이 어긋나 있나 (배추 · 2017~ · 실측)

순(旬) 36칸 중 **다섯 칸**에서 현행 매핑이 실제 1위 산지와 다릅니다.

    5월 하   실제 전남 해남 59%   ->  매핑 홍성(충남)
    6월 상   실제 충남 아산 43%   ->  매핑 대관령(강원)
    8월 하   실제 강원 강릉 55%   ->  매핑 대관령
    9월 하   실제 강원 평창 45%   ->  매핑 강릉
    11월 상  실제 강원 춘천 73%   ->  매핑 해남(전남)

**6월 상순과 11월 상순이 특히 큽니다** — 권역 자체가 다릅니다
(충남 vs 강원 · 강원 vs 전남).

★ 백로그의 처방("11월 상순 = 대관령")은 실측과 다릅니다.
  11월 상순 1위는 **춘천** 입니다.

## 무엇을 재나

**대상일이 어긋난 순에 드는 행**과 **나머지 행**의 오차를 견줍니다.

어긋난 구간에서만 유독 더 틀린다면 매핑이 원인일 수 있습니다.
차이가 없으면 **고쳐도 얻을 게 없습니다.**

★ 이것만으로 인과를 못 정합니다. 그 구간은 계절도 다르고 산지도 분산돼
  있어서(6월 상순 1위 비중 43%) 원래 어려운 구간일 수 있습니다.
  **손해가 없으면 고치지 않는다** 는 판단에만 씁니다.

## 쓰는 법

    python exp_stn_mismatch.py train_20260828b.csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import train as T                                            # noqa: E402
from exp_quantile import build                               # noqa: E402

OPS = {"auc": (0.4, 76), "whsl": (0.8, 122), "rtl": (1.0, 81)}
ALL_FOLDS = {
    "A": ("A(검증2023)", "2022-12-31", "2023-12-31"),
    "B": ("B(검증2022)", "2021-12-31", "2022-12-31"),
    "C": ("C(검증2021)", "2020-12-31", "2021-12-31"),
}
#   (월, 순) — 순 1=상 2=중 3=하
BAD = {(5, 3), (6, 1), (8, 3), (9, 3), (11, 1)}
BAD_NM = {(5, 3): "5월 하 (해남↔홍성)", (6, 1): "6월 상 (아산↔대관령)",
          (8, 3): "8월 하 (강릉↔대관령)", (9, 3): "9월 하 (평창↔강릉)",
          (11, 1): "11월 상 (춘천↔해남)"}


def wm(a, p):
    a, p = np.asarray(a, float), np.asarray(p, float)
    s = np.abs(a).sum()
    return float(np.abs(a - p).sum() / s) if s else float("nan")


def sun(day):
    return np.where(day <= 10, 1, np.where(day <= 20, 2, 3))


def main() -> int:
    ap = argparse.ArgumentParser(description="매핑이 어긋난 구간의 오차 [M-05]")
    ap.add_argument("csv")
    ap.add_argument("--targets", nargs="+", default=["auc", "whsl"])
    ap.add_argument("--folds", nargs="+", default=["A", "B", "C"])
    ap.add_argument("--train-start", default="2017-01-01")
    ap.add_argument("--gate-lt", type=int, default=3)
    ap.add_argument("--seeds", nargs="+", type=int, default=list(range(62, 72)))
    a = ap.parse_args()

    print("=" * 88)
    print("[주산지 매핑 어긋남 · M-05] 배추 · 어긋난 순 vs 나머지")
    print(f"  시드 {len(a.seeds)}개 · LT>={a.gate_lt} · 폴드 {', '.join(a.folds)}")
    print("  ※ 소매가는 주산지 기상을 안 쓰므로 뺍니다 (5.3절)")
    print("=" * 88)

    for kind in a.targets:
        alpha, rounds = OPS[kind]
        print()
        agg = {}
        for fk in a.folds:
            tag, tend, vend = ALL_FOLDS[fk]
            tr, va, feats, cats, tgt, anc, label = build(a.csv, kind, tend, vend, alpha)
            tr = tr[tr.base_dt >= pd.Timestamp(a.train_start)]
            va = va[(va.lead_biz_d >= a.gate_lt)
                    & (va.item_nm.astype(str) == "배추")].copy()
            cat_in = [c for c in cats if c in feats]
            ps = []
            for s in a.seeds:
                p = dict(T.PARAMS, seed=s, bagging_seed=s, feature_fraction_seed=s)
                m = lgb.train(p, lgb.Dataset(tr[feats], tr["y"], categorical_feature=cat_in),
                              num_boost_round=rounds)
                ps.append(va[anc].to_numpy(float) * np.exp(m.predict(va[feats])))
            pred = np.mean(ps, axis=0)
            act = va[tgt].to_numpy(float)
            ancv = va[anc].to_numpy(float)
            td = pd.to_datetime(va["target_dt"])
            key = list(zip(td.dt.month.to_numpy(), sun(td.dt.day.to_numpy())))
            bad = np.array([k in BAD for k in key])
            for nm, msk in (("어긋난 순", bad), ("나머지", ~bad)):
                if msk.sum() < 30:
                    continue
                wmv, wa = wm(act[msk], pred[msk]), wm(act[msk], ancv[msk])
                agg.setdefault(nm, []).append((wmv, wa, int(msk.sum())))
            #   칸별로도 본다
            for k in sorted(BAD):
                msk = np.array([x == k for x in key])
                if msk.sum() < 20:
                    continue
                agg.setdefault(BAD_NM[k], []).append(
                    (wm(act[msk], pred[msk]), wm(act[msk], ancv[msk]), int(msk.sum())))

        print(f"  [{label} · 배추]")
        print(f"    {'구간':<22}{'행수':>7}{'모델':>9}{'앵커':>9}{'개선율':>9}")
        for nm in ["어긋난 순", "나머지"] + [BAD_NM[k] for k in sorted(BAD)]:
            v = agg.get(nm)
            if not v:
                continue
            n = sum(x[2] for x in v)
            wmv = sum(x[0] * x[2] for x in v) / n
            wa = sum(x[1] * x[2] for x in v) / n
            print(f"    {nm:<22}{n:>7}{wmv:>9.4f}{wa:>9.4f}"
                  f"{(wa - wmv) / wa * 100:>+8.1f}%")

    print("\n" + "=" * 88)
    print("  어긋난 구간에서만 유독 나쁘지 않다면 매핑을 고쳐도 얻을 게 없습니다.")
    print("  ★ 이 검사만으로 인과를 못 정합니다 — 그 구간은 산지가 분산돼 있어")
    print("    (6월 상순 1위 43%) 원래 어려운 구간일 수 있습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
