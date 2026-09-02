# -*- coding: utf-8 -*-
"""밴드 적중률 — 밴드표와 겹치지 않는 구간에서 (2026-09-01)

## 왜 필요한가

`ref_prediction_band` 는 **2024-01 이후 검증 구간**에서 만들어졌습니다
(`ops_auc/meta.json` · train_end 2023-12-31 · valid_end 없음).
그래서 홀드아웃 2024~2025 에서 적중률을 재면 **만든 자료로 시험 보는 것**이라
부풀려집니다. 기출문제로 시험 본 점수를 실력이라고 할 수 없는 것과 같습니다.

## 그래서 2023 과 2022 에서 잽니다

밴드표는 2024 이후에서 나왔으므로 2023·2022 는 밴드가 본 적 없는 구간입니다.
모델도 그 해를 안 보게 학습 구간을 잘라 씁니다.

    폴드 A   학습 2017~2022  ·  잼 2023
    폴드 B   학습 2017~2021  ·  잼 2022

**밴드표는 운영에서 쓰는 그 표를 그대로 씁니다.** 다시 만들지 않습니다.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import train as T                                             # noqa: E402
from exp_quantile import build                                # noqa: E402
from score_predictions import dsn                             # noqa: E402

ITEMS = ["배추", "무", "양파"]
OLD = {"배추": 80.0, "무": 80.4, "양파": 69.7}
ALPHA = {"auc": 0.4, "whsl": 0.8, "rtl": 1.0}


def band(kind):
    with psycopg.connect(dsn(), connect_timeout=25) as c:
        return pd.read_sql("SELECT item_nm, lead_biz_d, ratio_q10, ratio_q90 "
                           "FROM ref_prediction_band WHERE target_kind = %s",
                           c, params=(kind,))


def fold(csv, kind, train_end, valid_end, tag, seeds=(42, 43, 44), rounds=300):
    import lightgbm as lgb
    tr, va, feats, cats, tgt, anc, label = build(csv, kind, train_end,
                                                 valid_end, ALPHA[kind])
    tr = tr[tr.base_dt >= pd.Timestamp("2017-01-01")]
    va = va[va.lead_biz_d >= 3].copy()
    ps = []
    for s in seeds:
        p = dict(T.PARAMS, seed=s, bagging_seed=s, feature_fraction_seed=s)
        m = lgb.train(p, lgb.Dataset(tr[feats], tr["y"], categorical_feature=cats),
                      num_boost_round=rounds)
        ps.append(m.predict(va[feats]))
    va["pred"] = va[anc].to_numpy(float) * np.exp(np.mean(ps, axis=0))

    v = va.merge(band(kind), on=["item_nm", "lead_biz_d"], how="left")
    v = v[v.ratio_q10.notna()]
    v["hit"] = ((v[tgt] >= v.pred * v.ratio_q10)
                & (v[tgt] <= v.pred * v.ratio_q90))
    v["w"] = (v.ratio_q90 - v.ratio_q10)

    print(f"\n  [{tag}] {label} · {len(v):,}행 · 기준일 {v.base_dt.dt.date.nunique()}개")
    print(f"    {'품목':<6}{'행수':>9}{'적중률':>9}{'평균폭':>9}{'평균오차':>10}"
          + ("   (8/28 값)" if kind == "auc" else ""))
    for it in ITEMS:
        x = v[v.item_nm == it]
        if x.empty:
            continue
        mape = (x[tgt] - x.pred).abs().sum() / x[tgt].abs().sum()
        tail = f"   {OLD[it]:>6.1f}%" if kind == "auc" else ""
        print(f"    {it:<6}{len(x):>9,}{x.hit.mean()*100:>8.1f}%"
              f"{x.w.mean()*100:>8.0f}%{mape*100:>9.1f}%{tail}")
    print(f"    {'전체':<6}{len(v):>9,}{v.hit.mean()*100:>8.1f}%")


def main():
    csv = str(HERE.parents[2] / "실험결과" / "train_clim_20260831.csv")
    print("=" * 74)
    print("[밴드 적중률] 밴드표가 본 적 없는 구간에서 · 목표 80%")
    print("  밴드표 ref_prediction_band 는 2024-01 이후에서 만들어졌습니다")
    print("=" * 74)
    for kind in ("auc", "whsl", "rtl"):
        fold(csv, kind, "2022-12-31", "2023-12-31", f"폴드 A · 잼 2023 · {kind}")
        fold(csv, kind, "2021-12-31", "2022-12-31", f"폴드 B · 잼 2022 · {kind}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
