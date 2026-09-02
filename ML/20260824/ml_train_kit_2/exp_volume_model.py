# -*- coding: utf-8 -*-
"""반입량 예측 실험 — 2단 예측 판정 및 반입량 모델 자체 평가

`train.py` 는 가격 타겟 3종에 고정돼 있어, **같은 조리법**을 그대로 옮겨
반입량을 타겟으로 학습한다. 운영 스크립트는 건드리지 않는다.

    python exp_volume_model.py <csv> --valid-end 2023-12-31
    python exp_volume_model.py <csv> --anchor arr_qty_prev_yr

같게 유지한 것 (여기가 어긋나면 비교가 무의미해진다)
    · 앵커 로그비율    y = log(target / anchor),  pred = anchor * exp(out)
    · PARAMS           train.py 와 동일 (regression_l1 · lr 0.03 · leaves 31 ...)
    · 자연키 정렬      (base_dt, item_nm, lead_biz_d) — 행 순서가 결과를 바꾼다
    · early_stopping   200
    · 시드 앙상블      예측 평균
    · WMAPE            품목별로 분해. 통합값으로 판단하지 않는다

다른 것
    · target  arr_qty_at_target   (대상일의 실제 반입량, ton)
    · anchor  기본 arr_qty_lag1. `--anchor` 로 교체 가능
    · 제외    가격 타겟 3종 + 타겟 자신

가격 feature 는 **남긴다.** 기준일 시점에 알 수 있는 값이고, 출하자가 가격을
보고 출하를 결정하므로 반입량 예측에 정당한 입력이다.

## baseline 을 3종 다 놓는 이유 (2026-08-26)

앵커 하나만 놓고 개선율을 재면 부풀려진다. 반입량은 계절성이 강해
**작년 동기**가 훨씬 강한 baseline 이다. 실제로 어제값 대비 **+40%** 로
보고했던 것이 작년동기 대비로는 **-1%** 였다. 백로그 M-15 가 가격에 대해
제기한 것과 같은 문제이고, 반입량에서 먼저 드러났다.
"""
import argparse

import lightgbm as lgb
import numpy as np
import pandas as pd

TARGET = "arr_qty_at_target"
BASE_COLS = (("어제값", "arr_qty_lag1"),
             ("7일평균", "arr_qty_avg7"),
             ("작년동기", "arr_qty_prev_yr"))

DROP = {"id", "created_at", "base_dt", "target_dt", "arr_qty_asof_date",
        "arr_top1_region", "prod_area_fcst_temp_avg10",
        "target_auc_prc", "target_whsl_prc", "target_rtl_prc",
        "crop_area_yoy_rt",
        # 경제·학사일정은 가격 모델에서 이미 기각됐다. 조건을 맞춘다
        "m2_growth_rt", "epu_idx", "ppi_idx", "school_open_ratio",
        TARGET}
CAT = ["item_nm", "target_dow", "prod_area_stn_nm"]

PARAMS = dict(objective="regression_l1", metric="mae",
              learning_rate=0.03, num_leaves=31,
              feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1,
              min_data_in_leaf=60, lambda_l2=1.0, verbosity=-1)


def wmape(t, p):
    t, p = np.asarray(t, float), np.asarray(p, float)
    m = ~(np.isnan(t) | np.isnan(p))
    return np.abs(t[m] - p[m]).sum() / np.abs(t[m]).sum()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--train-start", default="2017-01-01")
    ap.add_argument("--train-end", default="2022-12-31")
    ap.add_argument("--valid-end", default="2023-12-31")
    ap.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44, 45, 46])
    ap.add_argument("--items", nargs="+", default=["배추", "양파", "무"])
    ap.add_argument("--anchor", default="arr_qty_lag1",
                    choices=[c for _, c in BASE_COLS])
    a = ap.parse_args()
    anchor = a.anchor

    df = pd.read_csv(a.csv, encoding="utf-8", low_memory=False)
    df["base_dt"] = pd.to_datetime(df["base_dt"])
    df = df[df.item_nm.isin(a.items)].copy()

    # 반입량 0 인 날은 뺀다 — 로그비율이 정의되지 않는다.
    # 휴장·미조사로 생긴 0 이며, 가격 모델이 결측 타겟을 빼는 것과 같은 처리다.
    n0 = len(df)
    df = df[(df[TARGET] > 0) & (df[anchor] > 0)].copy()
    print(f"[표본] {n0:,} -> {len(df):,}행 (반입량 0 제외 {n0 - len(df):,})")

    df = df.sort_values(["base_dt", "item_nm", "lead_biz_d"]).reset_index(drop=True)
    df["y_ratio"] = np.log(df[TARGET] / df[anchor])

    feats = [c for c in df.columns if c not in DROP | {"y_ratio"}]
    for c in CAT:
        if c in df.columns:
            df[c] = df[c].astype("category")
    print(f"[feature] {len(feats)}개 · 앵커 {anchor} 대비 로그비율")

    tr = df[(df.base_dt >= a.train_start) & (df.base_dt <= a.train_end)]
    va = df[(df.base_dt > a.train_end) & (df.base_dt <= a.valid_end)]
    print(f"[분할] 학습 {len(tr):,}행 ({tr.base_dt.min().date()}~{tr.base_dt.max().date()})"
          f" · 검증 {len(va):,}행 ({va.base_dt.min().date()}~{va.base_dt.max().date()})")

    preds = []
    for s in a.seeds:
        p = dict(PARAMS, seed=s, bagging_seed=s, feature_fraction_seed=s)
        m = lgb.train(p, lgb.Dataset(tr[feats], tr.y_ratio),
                      num_boost_round=3000,
                      valid_sets=[lgb.Dataset(va[feats], va.y_ratio)],
                      callbacks=[lgb.early_stopping(200, verbose=False)])
        out = m.predict(va[feats], num_iteration=m.best_iteration)
        preds.append(va[anchor].values * np.exp(out))
        print(f"  seed {s:>3}: WMAPE {wmape(va[TARGET], preds[-1]):.4f}"
              f"  (best_iter {m.best_iteration})")

    ens = np.mean(preds, axis=0)
    per_seed = [wmape(va[TARGET], p) for p in preds]
    print(f"  시드별 {np.mean(per_seed):.4f} +- {np.std(per_seed):.4f} (시드 {len(a.seeds)}개)")
    print(f"  앙상블 {wmape(va[TARGET], ens):.4f}")

    bases = [(n, c) for n, c in BASE_COLS if c in va.columns]
    head = "".join(f"{n:>9}" for n, _ in bases)

    def report(mask, label):
        mw = wmape(va[TARGET][mask], ens[mask])
        bs = [(n, wmape(va[TARGET][mask], va[c].values[mask])) for n, c in bases]
        bn, bw = min(bs, key=lambda x: x[1])
        cells = "".join(f"{v:>9.4f}" for _, v in bs)
        print(f"  {label:<5}{mw:>9.4f}{cells}{bn:>10}{100 * (bw - mw) / bw:>8.1f}%")

    print("")
    print("[품목별] 모델 vs baseline 3종 — 개선율은 **최강 baseline** 대비")
    print(f"  {'품목':<5}{'모델':>9}{head}{'최강':>10}{'개선율':>9}")
    for it in a.items:
        m_ = va.item_nm.astype(str).values == it
        if m_.any():
            report(m_, it)

    print("")
    print("[리드타임별]")
    print(f"  {'LT':<5}{'모델':>9}{head}{'최강':>10}{'개선율':>9}")
    for lt in (1, 3, 7, 14, 18):
        m_ = va.lead_biz_d.values == lt
        if m_.any():
            report(m_, f"LT{lt}")

    imp = pd.Series(m.feature_importance("gain"), index=feats).sort_values(ascending=False)
    print("")
    print("[중요도 상위 10]")
    for k, v in (imp / imp.sum() * 100).head(10).items():
        print(f"  {k:<28}{v:>6.1f}%")


if __name__ == "__main__":
    main()
