# -*- coding: utf-8 -*-
"""
crop_price_train 학습 스크립트
==============================
DB 에서 내보낸 CSV 로 LightGBM 을 학습하고 baseline 과 비교한다.

사용법
    python train.py <csv경로>
    python train.py <csv경로> --raw          # 앵커 변환 없이 절대가격 학습(비교용)
    python train.py <csv경로> --train-end 2023-12-31

기본 동작
    학습 2022~2024 / 검증 2025
    타겟은 앵커 대비 로그 비율:  y = log(target / whsl_prc_lag1)
    예측 시 역변환:              pred = whsl_prc_lag1 * exp(model_output)

앵커 변환을 쓰는 이유
    절대가격을 그대로 학습하면 모델이 리드타임을 무시하고 '평균 가격 수준'만
    배운다. 실측에서 lead_biz_d 중요도가 1.5% 에 그쳤고 LT1 성능이 baseline
    대비 95% 나빴다. 비율로 바꾸면 모델이 0 을 출력할 때 자동으로 baseline 과
    같아지므로, baseline 아래로 떨어질 위험이 구조적으로 줄어든다.
    덤으로 트리의 외삽 한계(학습 범위 밖 가격을 못 냄)도 완화된다.

산출물
    curve_leadtime.csv      리드타임별 성능
    feature_importance.csv  feature 기여도
"""
import argparse
import numpy as np
import pandas as pd
import lightgbm as lgb

# 유통 3단계 타겟과 각각의 앵커
#   타겟마다 짝이 되는 앵커를 써야 한다. 중도매가 타겟에 경락가 앵커를 쓰면
#   스케일이 어긋나 앵커 변환의 의미가 사라진다.
TARGETS = {
    "auc":  ("target_auc_prc",  "auc_prc_lag1",  "경락가"),
    "whsl": ("target_whsl_prc", "whsl_prc_lag1", "중도매가"),
    "rtl":  ("target_rtl_prc",  "rtl_prc_lag1",  "소매가"),
}
TARGET = "target_whsl_prc"      # 기본값
ANCHOR = "whsl_prc_lag1"

# 기본 학습 품목
#   마늘은 제외한다. 피마늘/깐마늘 구분이 확정되지 않았고, 중도매가가
#   94% 의 날에 전일과 동일해 예측 문제로서 성격이 다르다.
#   테이블에는 남아 있으므로 --items 로 언제든 포함할 수 있다.
DEFAULT_ITEMS = ["배추", "양파", "무"]

# 경제 지표 — 세 타겟 모두에서 성능을 떨어뜨린다 (ablation 2026-08-22)
#   m2·epu·ppi 는 월·분기 단위로 갱신되어 일별 예측에서는 같은 값이
#   한 달간 반복된다. 모델이 이를 시점 식별자로 오용해 과적합을 유발한다.
#   경락가 +6.8%→+8.6% · 중도매가 +6.1%→+7.2% · 소매가 +12.7%→+15.3%
ECON_COLS = ["m2_growth_rt", "epu_idx", "ppi_idx"]

# 주산지 기상 — 소매가에서만 해롭다 (ablation 2026-08-22, 시드 7)
#   소매가는 유통 마진이 두껍게 완충해 산지 작황의 영향이 희석된다.
#   수요 신호(holiday_remain_d)가 이미 그 역할을 하므로 노이즈로 작용한다.
#   소매가 +12.7% → +17.1%
WEATHER_COLS = ["prod_area_stn_nm", "prod_area_temp_avg_lag1",
                "prod_area_rain_sum7", "prod_area_rain_sum30",
                "prod_area_gdd_sum30", "prod_area_clim_temp_avg10",
                "prod_area_clim_yr_cnt"]

# 타겟별 추가 제외
TARGET_DROP = {
    "auc":  set(ECON_COLS),
    "whsl": set(ECON_COLS),
    "rtl":  set(ECON_COLS) | set(WEATHER_COLS),
}

# 모델 입력에서 제외 — 식별자·메타·정답·진단용 컬럼
# 모델 입력에서 제외 — 식별자·메타·정답·진단용
#   타겟 3종은 서로의 정답이므로 모두 제외한다. 하나라도 남으면 누수다.
DROP = {"id", "created_at", "base_dt", "target_dt", "arr_qty_asof_date",
        "arr_top1_region", "prod_area_fcst_temp_avg10",
        "target_auc_prc", "target_whsl_prc", "target_rtl_prc",
        # KREI 재배면적: 결측 75%. 결측이 무작위가 아니라 발간 일정에 의존해
        # 모델이 "언제 발표되는가" 를 학습할 위험이 있다.
        "crop_area_yoy_rt"}
CAT = ["item_nm", "target_dow", "prod_area_stn_nm"]

PARAMS = dict(objective="regression_l1", metric="mae",
              learning_rate=0.03, num_leaves=31,
              feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1,
              min_data_in_leaf=60, lambda_l2=1.0, verbosity=-1)


def wmape(t, p):
    t, p = np.asarray(t, float), np.asarray(p, float)
    m = ~(np.isnan(t) | np.isnan(p))
    return np.abs(t[m] - p[m]).sum() / np.abs(t[m]).sum()


def dir_acc(t, p, ref):
    t, p, ref = (np.asarray(x, float) for x in (t, p, ref))
    m = ~(np.isnan(t) | np.isnan(p) | np.isnan(ref))
    return ((t[m] - ref[m]) * (p[m] - ref[m]) > 0).mean()


def load(path, *, target=None, anchor=None):
    # Windows 에서 DBeaver 내보내기 인코딩이 제각각이라 순서대로 시도한다
    for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            df = pd.read_csv(path, encoding=enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise SystemExit("CSV 인코딩을 읽지 못했습니다. UTF-8 로 다시 내보내세요.")

    tgt, anc = target or TARGET, anchor or ANCHOR
    missing = [c for c in (tgt, anc, "base_dt", "lead_biz_d") if c not in df.columns]
    if missing:
        raise SystemExit(f"필수 컬럼이 없습니다: {missing}\n"
                         f"내보낸 CSV 가 crop_price_train 이 맞는지 확인하세요.")

    df["base_dt"] = pd.to_datetime(df["base_dt"])
    df = df[df[tgt].notna() & df[anc].notna()].copy()
    for c in CAT:
        if c in df:
            df[c] = df[c].astype("category")
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--train-end", default="2024-12-31")
    ap.add_argument("--raw", action="store_true", help="앵커 변환 없이 절대가격 학습")
    ap.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44])
    ap.add_argument("--target", choices=list(TARGETS), default="whsl",
                    help="auc=경락가 · whsl=중도매가 · rtl=소매가")
    ap.add_argument("--train-start", help="학습 시작일. 생략 시 전체")
    ap.add_argument("--keep-all", action="store_true",
                    help="ablation 으로 제외된 feature 도 모두 사용 (비교용)")
    ap.add_argument("--items", nargs="+", default=DEFAULT_ITEMS,
                    help=f"학습 품목. 기본 {' '.join(DEFAULT_ITEMS)}")
    a = ap.parse_args()

    global TARGET, ANCHOR
    TARGET, ANCHOR, label = TARGETS[a.target]
    print(f"\n[타겟] {label}  ({TARGET} / 앵커 {ANCHOR})")

    global DROP
    if not a.keep_all:
        extra = TARGET_DROP.get(a.target, set())
        DROP = DROP | extra
        if extra:
            groups = []
            if set(ECON_COLS) <= extra:
                groups.append("경제 3종")
            if set(WEATHER_COLS) <= extra:
                groups.append("주산지 기상 7종")
            print(f"[feature] ablation 반영 제외 — {' · '.join(groups)}")
            print(f"          (--keep-all 로 되돌릴 수 있음)")

    df = load(a.csv)

    all_items = sorted(df.item_nm.unique())
    keep = [i for i in a.items if i in all_items]
    dropped = [i for i in all_items if i not in keep]
    if not keep:
        raise SystemExit(f"선택한 품목이 데이터에 없습니다.\n  요청: {a.items}\n  존재: {all_items}")
    df = df[df.item_nm.isin(keep)].copy()
    df["item_nm"] = df.item_nm.cat.remove_unused_categories() \
        if hasattr(df.item_nm, "cat") else df.item_nm
    print(f"[품목] 학습 {keep}" + (f" · 제외 {dropped}" if dropped else ""))

    if a.train_start:
        df = df[df.base_dt >= a.train_start]
    df["y_ratio"] = np.log(df[TARGET] / df[ANCHOR])
    feats = [c for c in df.columns if c not in DROP | {"y_ratio"}]
    cats = [c for c in CAT if c in feats]

    tr = df[df.base_dt <= a.train_end]
    va = df[df.base_dt > a.train_end].copy()
    if len(va) == 0:
        print("검증 구간이 비었습니다. --train-end 를 확인하세요."); return

    print("=" * 68)
    print(f"학습  {len(tr):>7,}행  {tr.base_dt.min().date()} ~ {tr.base_dt.max().date()}"
          f"  (고유 기준일 {tr.base_dt.nunique():,})")
    print(f"검증  {len(va):>7,}행  {va.base_dt.min().date()} ~ {va.base_dt.max().date()}"
          f"  (고유 기준일 {va.base_dt.nunique():,})")
    print(f"feature {len(feats)}개 · 타겟 {'절대가격' if a.raw else '앵커 대비 로그비율'}")
    print("=" * 68)

    # 유효 표본 경고 — 18행은 같은 기준일의 복제이므로 독립 표본이 아니다
    if tr.base_dt.nunique() < 1500:
        print(f"\n[주의] 고유 기준일이 {tr.base_dt.nunique():,}개뿐입니다.")
        print("       한 기준일이 리드타임 18행으로 복제되므로 실질 독립 표본은")
        print("       행수가 아니라 기준일 수입니다. 학습이 불안정할 수 있습니다.")

    # ── baseline ──────────────────────────────────────────────
    #   품목별로 반드시 분해한다. 통합 WMAPE 는 가격 수준이 높은 품목이
    #   분모를 지배해 착시를 만든다. (마늘 6,244원/kg 이 분모의 66% 를
    #   차지하면서 통합값을 0.2114 → 0.0781 로 끌어내린 사례가 있었다)
    CANDS = [("어제 가격", ANCHOR),
             ("최근7일 평균", "whsl_prc_avg7"),
             ("작년 동시기", "whsl_prc_prev_yr")]
    CANDS = [(n, c) for n, c in CANDS if c in va.columns]

    print("\n[BASELINE — 품목별]")
    print(f"  {'품목':<6}" + "".join(f"{n:>14s}" for n, _ in CANDS) + f"{'최강':>12}")
    base_by_item = {}
    for item, g in va.groupby("item_nm", observed=True):
        vals = [(n, wmape(g[TARGET], g[c])) for n, c in CANDS]
        best_n, best_v = min(vals, key=lambda x: x[1])
        base_by_item[item] = (best_n, best_v)
        print(f"  {str(item):<6}" + "".join(f"{v:14.4f}" for _, v in vals)
              + f"{best_n:>12}")

    base = {n: wmape(va[TARGET], va[c]) for n, c in CANDS}
    best_name = min(base, key=base.get)
    best_base = base[best_name]
    print(f"\n  [통합] {best_name} {best_base:.4f}"
          "   ※ 참고용. 품목별 값으로 판단할 것")

    # ── 학습 ──────────────────────────────────────────────────
    print("\n[LightGBM]")
    label_tr = tr[TARGET] if a.raw else tr.y_ratio
    label_va = va[TARGET] if a.raw else va.y_ratio
    preds, iters = [], []
    for s in a.seeds:
        p = dict(PARAMS, seed=s, bagging_seed=s, feature_fraction_seed=s)
        m = lgb.train(p, lgb.Dataset(tr[feats], label_tr, categorical_feature=cats),
                      num_boost_round=5000,
                      valid_sets=[lgb.Dataset(va[feats], label_va)],
                      callbacks=[lgb.early_stopping(200, verbose=False)])
        out = m.predict(va[feats])
        pr = out if a.raw else va[ANCHOR].values * np.exp(out)
        preds.append(pr); iters.append(m.best_iteration)
        print(f"  seed {s:>3}: WMAPE {wmape(va[TARGET], pr):.4f}  (best_iter {m.best_iteration})")
        last = m

    if max(iters) < 20:
        print("\n[주의] best_iter 가 매우 낮습니다. 모델이 학습을 거의 못 했다는 뜻이며,")
        print("       데이터에서 baseline 을 넘을 신호를 찾지 못한 상태입니다.")

    ws = [wmape(va[TARGET], p) for p in preds]
    pred = np.mean(preds, axis=0)
    final = wmape(va[TARGET], pred)
    print(f"\n  시드별 {np.mean(ws):.4f} ± {np.std(ws, ddof=1):.4f}")
    print(f"  앙상블 {final:.4f}   baseline 대비 {(1 - final/best_base)*100:+.1f}%")

    va["pred"] = pred

    # ── 품목별 성능 ★ ─────────────────────────────────────────
    print("\n[품목별 성능]")
    print(f"  {'품목':<6}{'모델':>10}{'baseline':>10}{'개선율':>9}{'방향정확도':>11}{'행수':>9}")
    for item, g in va.groupby("item_nm", observed=True):
        mo = wmape(g[TARGET], g.pred)
        bn, bv = base_by_item[item]
        da = dir_acc(g[TARGET], g.pred, g[ANCHOR])
        print(f"  {str(item):<6}{mo:10.4f}{bv:10.4f}{(1-mo/bv)*100:+8.1f}%"
              f"{da*100:10.1f}%{len(g):9,}")

    # ── 리드타임별 ────────────────────────────────────────────
    print("\n[리드타임별]")
    print(f"  {'LT':>3} {'모델':>9} {'baseline':>9} {'개선율':>8} {'방향정확도':>10}")
    rows = []
    for lt, g in va.groupby("lead_biz_d"):
        mo = wmape(g[TARGET], g.pred)
        bl = wmape(g[TARGET], g[ANCHOR])
        da = dir_acc(g[TARGET], g.pred, g[ANCHOR])
        rows.append(dict(lead_biz_d=lt, model=round(mo, 4), baseline=round(bl, 4),
                         improve=round(1 - mo/bl, 4), dir_acc=round(da, 4)))
        print(f"  {lt:3d} {mo:9.4f} {bl:9.4f} {(1-mo/bl)*100:+7.1f}% {da*100:9.1f}%")
    pd.DataFrame(rows).to_csv("curve_leadtime.csv", index=False)

    # 품목 × 리드타임 교차 — 저장 트레이딩은 품목별 매매 시점이 다르므로
    # 어느 품목이 어느 리드타임에서 잘 맞는지가 중요하다
    cross = []
    for (item, lt), g in va.groupby(["item_nm", "lead_biz_d"], observed=True):
        cross.append(dict(item_nm=item, lead_biz_d=lt,
                          model=round(wmape(g[TARGET], g.pred), 4),
                          baseline=round(wmape(g[TARGET], g[ANCHOR]), 4),
                          dir_acc=round(dir_acc(g[TARGET], g.pred, g[ANCHOR]), 4),
                          n=len(g)))
    pd.DataFrame(cross).to_csv("curve_item_leadtime.csv", index=False)

    # ── feature importance ────────────────────────────────────
    imp = pd.Series(last.feature_importance("gain"), index=feats)
    imp = (imp / max(imp.sum(), 1) * 100).sort_values(ascending=False)
    print("\n[Feature Importance 상위 15]")
    for k, v in imp.head(15).items():
        print(f"  {k:32s} {v:5.1f}%")
    imp.to_csv("feature_importance.csv", header=["gain_pct"])

    # ── 구간별 ────────────────────────────────────────────────
    print("\n[구간별]")
    if "whsl_prc_std7" in va and "whsl_prc_avg7" in va:
        va["vol"] = va.whsl_prc_std7 / va.whsl_prc_avg7
        thr = va.vol.quantile(.9)
        for lab, sub in [("평상시", va[va.vol <= thr]), ("변동기 상위10%", va[va.vol > thr])]:
            print(f"  {lab:14s} 모델 {wmape(sub[TARGET], sub.pred):.4f} | "
                  f"baseline {wmape(sub[TARGET], sub[ANCHOR]):.4f}")

    print("\n저장: curve_leadtime.csv · curve_item_leadtime.csv · feature_importance.csv")


if __name__ == "__main__":
    main()
