# -*- coding: utf-8 -*-
"""
Ablation 실험 — feature 그룹별 기여도 측정
==========================================
feature 를 그룹 단위로 넣고 빼며 성능 변화를 잰다.

왜 필요한가
    feature importance 는 "모델이 많이 참조했다" 를 말할 뿐,
    "없으면 나빠진다" 를 증명하지 않는다. 상관된 feature 끼리 중요도를
    나눠 갖기도 하고, 다른 feature 가 대신할 수 있으면 빼도 성능이 같다.

    실제 기여도는 빼보고 재야 나온다.

사용법
    python ablation.py <csv> --target auc --train-start 2017-01-01 --train-end 2022-12-31
    python ablation.py <csv> --target rtl --seeds 42 43 44 45 46
    python ablation.py <csv> --experiments A5 A6 A7      일부만 실행

읽는 법
    · 직전 단계 대비 개선폭(Δ)이 그룹의 순수 기여도다.
    · Δ 가 시드 표준편차보다 커야 유의미하다. 작으면 노이즈다.
    · 판정 열의 O 는 유의, △ 는 판정 불가, X 는 오히려 나빠짐을 뜻한다.
"""
import argparse
import numpy as np
import pandas as pd
import lightgbm as lgb

from train import (TARGETS, DROP, CAT, PARAMS, DEFAULT_ITEMS, wmape, dir_acc, load)

# ── feature 그룹 정의 ────────────────────────────────────────────────
#   앵커는 어느 실험에서든 반드시 포함된다. 타겟 변환의 기준이기 때문이다.
GROUPS = {
    "lag": [       # 단기 가격 관성
        "whsl_prc_lag1", "whsl_prc_lag3", "whsl_prc_lag7",
        "whsl_prc_avg7", "whsl_prc_avg14", "whsl_prc_std7",
        "rtl_prc_lag1",
    ],
    "anchor_season": [  # 계절 앵커
        "whsl_prc_prev_yr",
    ],
    "calendar": [  # 달력·수요
        "lead_biz_d", "target_dow", "kimchi_season_yn",
        "holiday_remain_d", "market_closed_lag1_yn", "market_temp_avg_lag1",
    ],
    "weather": [   # 주산지 기상 ★ 매핑 작업의 가치
        "prod_area_stn_nm", "prod_area_temp_avg_lag1",
        "prod_area_rain_sum7", "prod_area_rain_sum30",
        "prod_area_gdd_sum30", "prod_area_clim_temp_avg10",
        "prod_area_clim_yr_cnt",
    ],
    "volume": [    # 반입량 ★ as-of 결합의 가치
        "arr_qty_lag1", "arr_qty_avg7", "arr_qty_prev_yr",
    ],
    "auction": [   # 경락가 feature ★ 마진 배수의 가치
        "auc_prc_lag1", "auc_prc_lag3", "auc_prc_avg7",
        "auc_prc_spread_lag1", "auc_vol_lag1", "auc_whsl_ratio_lag1",
    ],
    "econ": [      # 경제 지표
        "m2_growth_rt", "epu_idx", "ppi_idx",
    ],
    "item": [      # 품목 식별
        "item_nm",
    ],
}

# ── 실험 설계 ────────────────────────────────────────────────────────
#   누적 방식이다. 직전 단계와의 차이가 그 그룹의 순수 기여도가 된다.
EXPERIMENTS = {
    "A0": ([], "baseline 만 (모델 없음)"),
    "A1": (["item", "lag"], "단기 lag"),
    "A2": (["item", "lag", "anchor_season"], "+ 계절 앵커"),
    "A3": (["item", "lag", "anchor_season", "calendar"], "+ 달력"),
    "A4": (["item", "lag", "anchor_season", "calendar", "econ"], "+ 경제"),
    "A5": (["item", "lag", "anchor_season", "calendar", "econ", "weather"],
           "+ 주산지 기상 ★"),
    "A6": (["item", "lag", "anchor_season", "calendar", "econ", "weather",
            "volume"], "+ 반입량 ★"),
    "A7": (["item", "lag", "anchor_season", "calendar", "econ", "weather",
            "volume", "auction"], "+ 경락가 ★ (전체)"),
}


def build_features(df, group_names, anchor):
    """그룹 이름들로부터 실제 컬럼 목록을 만든다. 앵커는 항상 포함."""
    cols = []
    for g in group_names:
        cols.extend(GROUPS[g])
    if anchor not in cols:
        cols.append(anchor)          # 앵커는 필수
    seen, out = set(), []
    for c in cols:
        if c in df.columns and c not in DROP and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def run_one(tr, va, feats, target, anchor, seeds):
    """한 구성으로 학습·평가. (WMAPE, 표준편차, 예측, best_iter들) 반환"""
    cats = [c for c in CAT if c in feats]
    preds, iters = [], []
    for s in seeds:
        p = dict(PARAMS, seed=s, bagging_seed=s, feature_fraction_seed=s)
        m = lgb.train(p,
                      lgb.Dataset(tr[feats], tr.y_ratio, categorical_feature=cats),
                      num_boost_round=5000,
                      valid_sets=[lgb.Dataset(va[feats], va.y_ratio)],
                      callbacks=[lgb.early_stopping(200, verbose=False)])
        preds.append(va[anchor].values * np.exp(m.predict(va[feats])))
        iters.append(m.best_iteration)
    ws = [wmape(va[target], p) for p in preds]
    ens = np.mean(preds, axis=0)
    return wmape(va[target], ens), np.std(ws, ddof=1), ens, iters


def main():
    ap = argparse.ArgumentParser(description="feature 그룹별 기여도 측정")
    ap.add_argument("csv")
    ap.add_argument("--target", choices=list(TARGETS), default="auc")
    ap.add_argument("--train-start", default="2017-01-01")
    ap.add_argument("--train-end", default="2022-12-31")
    ap.add_argument("--items", nargs="+", default=DEFAULT_ITEMS)
    ap.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44, 45, 46])
    ap.add_argument("--experiments", nargs="+", default=list(EXPERIMENTS))
    ap.add_argument("--mode", choices=["cumulative", "loo", "both"],
                    default="both",
                    help="cumulative=누적 추가 · loo=전체에서 하나씩 제거")
    ap.add_argument("--out", default="ablation_result.csv")
    a = ap.parse_args()

    target, anchor, label = TARGETS[a.target]
    print(f"[타겟] {label}  ({target} / 앵커 {anchor})")

    df = load(a.csv, target=target, anchor=anchor)
    keep = [i for i in a.items if i in set(df.item_nm.astype(str))]
    df = df[df.item_nm.astype(str).isin(keep)].copy()
    if a.train_start:
        df = df[df.base_dt >= a.train_start]
    df["y_ratio"] = np.log(df[target] / df[anchor])

    tr = df[df.base_dt <= a.train_end]
    va = df[df.base_dt > a.train_end].copy()
    print(f"[품목] {keep}")
    print(f"학습 {len(tr):,}행 (기준일 {tr.base_dt.nunique():,}) · "
          f"검증 {len(va):,}행 (기준일 {va.base_dt.nunique():,})")
    print(f"시드 {len(a.seeds)}개\n")

    # baseline
    bl = wmape(va[target], va[anchor])
    bl_item = {it: wmape(g[target], g[anchor])
               for it, g in va.groupby("item_nm", observed=True)}
    print(f"[baseline] 통합 {bl:.4f}  " +
          "  ".join(f"{it} {v:.4f}" for it, v in bl_item.items()))

    # ── 실행 ─────────────────────────────────────────────────────────
    print("\n" + "=" * 92)
    print(f"  {'실험':<4}{'구성':<20}{'feat':>5}{'WMAPE':>9}{'개선율':>8}"
          f"{'Δ':>8}{'편차':>8}{'판정':>6}{'iter':>7}")
    print("=" * 92)

    rows, prev_w = [], None
    for key in (a.experiments if a.mode in ("cumulative", "both") else []):
        if key not in EXPERIMENTS:
            continue
        groups, desc = EXPERIMENTS[key]

        if not groups:      # A0 = baseline
            print(f"  {key:<4}{desc:<20}{'—':>5}{bl:9.4f}{'—':>8}{'—':>8}"
                  f"{'—':>8}{'—':>6}{'—':>7}")
            rows.append(dict(exp=key, desc=desc, n_feat=0, wmape=round(bl, 4),
                             improve=0.0, delta=None, std=None, verdict="—"))
            prev_w = bl
            continue

        feats = build_features(df, groups, anchor)
        w, sd, ens, iters = run_one(tr, va, feats, target, anchor, a.seeds)

        delta = prev_w - w if prev_w is not None else None
        # 판정: 개선폭이 표준편차의 2배를 넘으면 유의
        if delta is None:
            verdict = "—"
        elif delta > 2 * sd:
            verdict = "O"
        elif delta < -2 * sd:
            verdict = "X"
        else:
            verdict = "△"

        print(f"  {key:<4}{desc:<20}{len(feats):>5}{w:9.4f}"
              f"{(1-w/bl)*100:+7.1f}%"
              f"{(delta if delta is not None else 0):+8.4f}{sd:8.4f}"
              f"{verdict:>6}{min(iters):>4}~{max(iters):<3}")

        r = dict(exp=key, desc=desc, n_feat=len(feats), wmape=round(w, 4),
                 improve=round(1 - w / bl, 4),
                 delta=round(delta, 4) if delta is not None else None,
                 std=round(sd, 4), verdict=verdict,
                 iter_min=min(iters), iter_max=max(iters))
        # 품목별
        tmp = va.copy(); tmp["pred"] = ens
        for it, g in tmp.groupby("item_nm", observed=True):
            r[f"imp_{it}"] = round(1 - wmape(g[target], g.pred) / bl_item[it], 4)
            r[f"dir_{it}"] = round(dir_acc(g[target], g.pred, g[anchor]), 4)
        rows.append(r)
        prev_w = w

    print("=" * 92)

    # ── 품목별 표 ────────────────────────────────────────────────────
    items = sorted(bl_item)
    print(f"\n[품목별 개선율]")
    print(f"  {'실험':<4}{'구성':<20}" + "".join(f"{it:>10}" for it in items))
    for r in rows:
        if r["delta"] is None and r["exp"] != "A0":
            continue
        if r["exp"] == "A0":
            print(f"  {r['exp']:<4}{r['desc']:<20}" + "".join(f"{'—':>10}" for _ in items))
            continue
        print(f"  {r['exp']:<4}{r['desc']:<20}" +
              "".join(f"{r.get(f'imp_{it}', 0)*100:+9.1f}%" for it in items))
    for r in rows:
        if r["exp"] == "A0":
            continue
        print(f"  {r['exp']:<4}{r['desc']:<20}" +
              "".join(f"{r.get(f'imp_{it}', 0)*100:+9.1f}%" for it in items))
        break

    # ── Leave-One-Out ────────────────────────────────────────────────
    #   누적 방식은 순서에 좌우된다. 앞에 추가된 그룹이 뒤 그룹의 자리를
    #   차지하면 뒤 그룹의 기여가 과소평가된다.
    #   전체에서 하나씩 빼보면 순서 의존 없이 순수 기여도를 잴 수 있다.
    loo_rows = []
    if a.mode in ("loo", "both"):
        all_groups = EXPERIMENTS["A7"][0]
        full_feats = build_features(df, all_groups, anchor)
        w_full, sd_full, _, it_full = run_one(tr, va, full_feats, target, anchor, a.seeds)

        print("\n" + "=" * 92)
        print("  [Leave-One-Out] 전체에서 그룹 하나씩 제거")
        print("=" * 92)
        print(f"  {'제거 그룹':<16}{'feat':>5}{'WMAPE':>9}{'개선율':>8}"
              f"{'손실':>9}{'편차':>8}{'판정':>6}")
        print(f"  {'(제거 없음)':<16}{len(full_feats):>5}{w_full:9.4f}"
              f"{(1-w_full/bl)*100:+7.1f}%{'—':>9}{sd_full:8.4f}{'—':>6}")

        for g in all_groups:
            if g == "item":
                continue        # 품목 식별자는 제거 대상이 아님
            rest = [x for x in all_groups if x != g]
            feats = build_features(df, rest, anchor)
            w, sd, _, iters = run_one(tr, va, feats, target, anchor, a.seeds)
            loss = w - w_full           # 양수면 빼서 나빠짐 = 기여했음
            if loss > 2 * sd:
                verdict = "O"           # 필요함
            elif loss < -2 * sd:
                verdict = "X"           # 빼는 게 나음
            else:
                verdict = "△"
            print(f"  {('− ' + g):<16}{len(feats):>5}{w:9.4f}"
                  f"{(1-w/bl)*100:+7.1f}%{loss:+9.4f}{sd:8.4f}{verdict:>6}")
            loo_rows.append(dict(removed=g, n_feat=len(feats), wmape=round(w, 4),
                                 improve=round(1 - w / bl, 4),
                                 loss=round(loss, 4), std=round(sd, 4),
                                 verdict=verdict))
        print("=" * 92)
        print("  손실  그룹을 뺐을 때 나빠진 정도. 클수록 기여가 크다")
        print("  판정  O = 필요함  ·  △ = 판정 불가  ·  X = 빼는 것이 나음")

    pd.DataFrame(rows).to_csv(a.out, index=False, encoding="utf-8-sig")
    if loo_rows:
        loo_path = a.out.replace(".csv", "_loo.csv")
        pd.DataFrame(loo_rows).to_csv(loo_path, index=False, encoding="utf-8-sig")
        print(f"\n저장: {a.out} · {loo_path}")
    else:
        print(f"\n저장: {a.out}")
    print("\n[읽는 법]")
    print("  Δ    직전 단계 대비 개선폭. 그 그룹의 순수 기여도")
    print("  판정  O = Δ > 편차×2 (유의)  ·  △ = 판정 불가  ·  X = 오히려 악화")
    print("  ※ Δ 가 편차보다 작으면 그 feature 는 기여를 증명하지 못한 것")


if __name__ == "__main__":
    main()
