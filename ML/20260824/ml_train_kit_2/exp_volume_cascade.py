# -*- coding: utf-8 -*-
"""2단 예측 캐스케이드 CSV 생성 — 반입량 예측을 가격 모델의 feature 로

    python exp_volume_cascade.py <vol_oracle.csv> <출력.csv>

`arr_qty_at_target`(대상일의 **실제** 반입량)을 지우고, 그 자리에
`arr_qty_pred`(반입량 모델의 **예측**)를 넣는다. 오라클 실험이 상한을
보여줬다면 이것이 실제로 도달 가능한 값이다.

## 누수 방지 — 확장 윈도우

한 번 학습해 전 구간을 예측하면 학습에 쓴 해를 자기가 예측하게 되어
반입량 예측이 실제보다 정확해진다. 그러면 가격 모델이 오라클에 가까운
입력을 받고, 운영에서 재현되지 않는다.

연도 Y 의 반입량 예측은 **Y 이전 데이터만으로 학습한 모델**이 만든다.

    2017 예측 ← 2015~2016 학습
    2018 예측 ← 2015~2017 학습
    ...
    2023 예측 ← 2015~2022 학습

운영에서 매년 재학습하는 모습과 같다. 초기 연도는 학습량이 적어 예측이
나쁘고, 그것도 현실의 일부다.
"""
import sys

import lightgbm as lgb
import numpy as np
import pandas as pd

TARGET = "arr_qty_at_target"
ANCHOR = "arr_qty_lag1"
PRED = "arr_qty_pred"

DROP = {"id", "created_at", "base_dt", "target_dt", "arr_qty_asof_date",
        "arr_top1_region", "prod_area_fcst_temp_avg10",
        "target_auc_prc", "target_whsl_prc", "target_rtl_prc",
        "crop_area_yoy_rt",
        "m2_growth_rt", "epu_idx", "ppi_idx", "school_open_ratio",
        TARGET}
CAT = ["item_nm", "target_dow", "prod_area_stn_nm"]
PARAMS = dict(objective="regression_l1", metric="mae",
              learning_rate=0.03, num_leaves=31,
              feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1,
              min_data_in_leaf=60, lambda_l2=1.0, verbosity=-1)
SEEDS = [42, 43, 44]        # 가격 모델보다 적게 — feature 생성용이라 3개로 충분
MIN_TRAIN_YEARS = 2


def wmape(t, p):
    t, p = np.asarray(t, float), np.asarray(p, float)
    return np.abs(t - p).sum() / np.abs(t).sum()


def main():
    src, dst = sys.argv[1], sys.argv[2]
    df = pd.read_csv(src, encoding="utf-8", low_memory=False)
    df["base_dt"] = pd.to_datetime(df["base_dt"])
    df = df.sort_values(["base_dt", "item_nm", "lead_biz_d"]).reset_index(drop=True)

    ok = (df[TARGET] > 0) & (df[ANCHOR] > 0)
    work = df[ok].copy()
    work["y_ratio"] = np.log(work[TARGET] / work[ANCHOR])
    feats = [c for c in work.columns if c not in DROP | {"y_ratio", PRED}]
    for c in CAT:
        if c in work.columns:
            work[c] = work[c].astype("category")

    df[PRED] = np.nan
    years = sorted(work.base_dt.dt.year.unique())
    print(f"[캐스케이드] feature {len(feats)}개 · 연도 {years[0]}~{years[-1]}")

    for y in years:
        tr = work[work.base_dt.dt.year < y]
        if tr.base_dt.dt.year.nunique() < MIN_TRAIN_YEARS:
            print(f"  {y}: 학습 연도 부족 — 건너뜀 (예측 없음)")
            continue
        va = work[work.base_dt.dt.year == y]
        preds = []
        for s in SEEDS:
            p = dict(PARAMS, seed=s, bagging_seed=s, feature_fraction_seed=s)
            m = lgb.train(p, lgb.Dataset(tr[feats], tr.y_ratio), num_boost_round=400)
            preds.append(va[ANCHOR].values * np.exp(m.predict(va[feats])))
        ens = np.mean(preds, axis=0)
        df.loc[va.index, PRED] = ens
        print(f"  {y}: 학습 {len(tr):,}행({tr.base_dt.dt.year.min()}~{y-1}) "
              f"→ 예측 {len(va):,}행 · WMAPE {wmape(va[TARGET], ens):.4f} "
              f"(persistence {wmape(va[TARGET], va[ANCHOR]):.4f})")

    # 반입량 예측이 없는 행은 앵커(어제값)로 메운다 — 운영에서도 그렇게 한다
    n_fill = int(df[PRED].isna().sum())
    df[PRED] = df[PRED].fillna(df[ANCHOR])
    df = df.drop(columns=[TARGET])          # 오라클 컬럼은 반드시 뺀다
    df.to_csv(dst, index=False)
    print(f"\n저장: {dst}")
    print(f"  {len(df):,}행 · {PRED} 결측 보정 {n_fill:,}행 (앵커로 대체)")


if __name__ == "__main__":
    main()
