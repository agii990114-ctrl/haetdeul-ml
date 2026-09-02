# -*- coding: utf-8 -*-
"""이월 재고·대체재 실험 (2026-08-28 · 6순위).

`context/20260828/agricultural_price_prediction_factors.md` 가 지적한 두 가지를
우리 데이터로 만들어 본다. 둘 다 **이미 DB 에 있는 값의 조합**이라 새 수집이
필요 없다.

## ① 미판매율 — "이월 재고" 의 대리값

  문서: "전날 낙찰되지 못하고 이월된 재고가 많으면 내일 경매가를 끌어내린다"

  우리에게 두 값이 따로 있는데 **차이는 안 보고 있다.**
      arr_qty_lag1   반입량 (들어온 양) · 단위 **톤**
      auc_vol_lag1   경매 낙찰량 (팔린 양) · 단위 **kg**

  단위가 달라 1000 을 곱해 맞춘다. 실측 비율이 약 770~1,070 이라
  톤↔kg 환산(1,000)과 자릿수가 맞다.

      미판매율 = 1 − 낙찰kg / (반입톤 × 1000)

  ※ 둘의 집계 범위가 완전히 같지는 않다 (반입량은 농넷 품목 전체,
    낙찰량은 우리 규격). 그래서 절대값보다 **날짜별 변동**에 의미가 있다.

## ② 대체재 가격

  문서: "배추가 폭등하면 무·양배추 수요가 늘어 함께 상승"

  우리는 세 품목을 한 모델이 맞히지만 **서로의 가격은 입력이 아니다.**
  같은 기준일의 다른 품목 어제 가격을 넣는다. 같은 표 안의 값이라
  미래 정보가 아니다.

## 판정

폴드 두 개에서 부호가 같고 이득이 시드편차×2 를 넘을 때만 채택 (CLAUDE.md 5.7).
"""
import argparse
import sys

import lightgbm as lgb
import numpy as np

from train import (TARGETS, TARGET_DROP, CAT, PARAMS, DROP as BASE_DROP,
                   load, wmape, _Tee, _open_log)
import train as _train

ALPHA = {"auc": 0.4, "whsl": 0.8, "rtl": 1.0}
FOLDS = (("A", "2022-12-31", "2023-12-31"), ("B", "2021-12-31", "2022-12-31"))
ITEMS = ["배추", "무", "양파"]

TGT = None


def build(csv, tgt_key):
    target, anchor, _ = TARGETS[tgt_key]
    alpha = ALPHA[tgt_key]
    drop = set(BASE_DROP) | set(TARGET_DROP[tgt_key]) | set(_train.NEW_PRICE_COLS)
    df = load(csv, target=target, anchor=anchor)
    df = df[df.item_nm.astype(str).isin(ITEMS)].copy()
    df = df[df.base_dt >= "2017-01-01"]
    if alpha < 1.0:
        df["_anc"] = (alpha * df[anchor]
                      + (1 - alpha) * df[anchor.replace("_lag1", "_avg7")])
        drop |= {anchor}
    else:
        df["_anc"] = df[anchor]
    df = df[(df[target] > 0) & (df["_anc"] > 0)].copy()
    df["y"] = np.log(df[target] / df["_anc"])
    drop |= {"_anc", "y"}
    df = df.sort_values(["base_dt", "item_nm", "lead_biz_d"]).reset_index(drop=True)

    added = {}

    # ① 미판매율 — 반입(톤)을 kg 으로 맞춘 뒤 낙찰량을 뺀다
    arr_kg = df["arr_qty_lag1"].astype(float) * 1000.0
    sold = df["auc_vol_lag1"].astype(float)
    ratio = np.where(arr_kg > 0, sold / arr_kg, np.nan)
    df["unsold_rate"] = 1.0 - ratio
    added["미판매율"] = "unsold_rate"

    # ② 대체재 가격 — 같은 기준일 다른 품목의 어제 가격
    #    피벗해서 (기준일 → 품목별 어제값) 을 만들고 자기 자신은 뺀다
    lag_col = anchor          # 예: auc_prc_lag1
    piv = (df.drop_duplicates(["base_dt", "item_nm"])
             .pivot(index="base_dt", columns="item_nm", values=lag_col))
    piv.columns = [f"_sub_{c}" for c in piv.columns]
    df = df.merge(piv, left_on="base_dt", right_index=True, how="left")
    sub_cols = []
    for it in ITEMS:
        c_ = f"_sub_{it}"
        if c_ not in df.columns:
            continue
        # 자기 품목 값은 앵커와 같으므로 지운다 (중복 입력 방지)
        df.loc[df.item_nm.astype(str) == it, c_] = np.nan
        sub_cols.append(c_)
    df["_sub_mean"] = df[sub_cols].mean(axis=1)
    added["대체재평균"] = "_sub_mean"

    feats0 = [c for c in df.columns
              if c not in drop | set(added.values()) | set(sub_cols)]
    return df, feats0, added, target


def run(tr, va, feats, seeds, gate):
    cats = [c for c in CAT if c in feats]
    preds = []
    for s in seeds:
        p = dict(PARAMS, seed=s, bagging_seed=s, feature_fraction_seed=s)
        m = lgb.train(p, lgb.Dataset(tr[feats], tr.y, categorical_feature=cats),
                      num_boost_round=3000,
                      valid_sets=[lgb.Dataset(va[feats], va.y)],
                      callbacks=[lgb.early_stopping(200, verbose=False)])
        preds.append(va["_anc"].values * np.exp(m.predict(va[feats])))
    ens = np.mean(preds, axis=0)
    g = va.lead_biz_d.values < gate
    ws = [wmape(va[TGT], p) for p in preds]
    return np.where(g, va["_anc"].values, ens), ws


def main():
    global TGT
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--target", choices=list(TARGETS), default="auc")
    ap.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44])
    ap.add_argument("--gate-lt", type=int, default=3)
    a = ap.parse_args()

    df, feats0, added, TGT = build(a.csv, a.target)
    print("[타겟] %s · 앵커 α=%s · 게이트 LT<%d · 시드 %d개"
          % (TARGETS[a.target][2], ALPHA[a.target], a.gate_lt, len(a.seeds)))
    print("[모델] LightGBM %s · 시드 %s 평균" % (lgb.__version__, list(a.seeds)))
    print("[하이퍼파라미터] "
          + " · ".join("%s=%s" % (k, PARAMS[k]) for k in sorted(PARAMS)))
    print("[기준 feature] %d개" % len(feats0))
    for n, c_ in added.items():
        v = df[c_]
        print("  후보 %-10s %-14s 결측 %5.1f%% · 중앙값 %s"
              % (n, c_, v.isna().mean() * 100,
                 "-" if v.notna().sum() == 0 else round(float(v.median()), 3)))

    for tag, tr_end, va_end in FOLDS:
        tr = df[df.base_dt <= tr_end]
        va = df[(df.base_dt > tr_end) & (df.base_dt <= va_end)].copy()
        print("\n" + "=" * 72)
        print("폴드 %s (검증 ~%s) · 학습 %s · 검증 %s"
              % (tag, va_end, format(len(tr), ","), format(len(va), ",")))
        base, ws = run(tr, va, feats0, a.seeds, a.gate_lt)
        b = wmape(va[TGT], base)
        sd = float(np.std(ws, ddof=1)) if len(ws) > 1 else 0.0
        print("  기준(현행)  %.2f%%   시드편차 %.4f" % (b * 100, sd))
        print("\n  %-14s%9s%10s   판정" % ("추가 feature", "오차율", "차이"))
        results = list(added.items()) + [("둘 다", None)]
        for n, c_ in results:
            extra = list(added.values()) if c_ is None else [c_]
            e, _ = run(tr, va, feats0 + extra, a.seeds, a.gate_lt)
            w = wmape(va[TGT], e)
            d = b - w
            mark = ("O 유의" if d > 2 * sd
                    else ("X 악화" if d < -2 * sd else "△ 판정불가"))
            print("  %-14s%8.2f%%%+9.2f%%p   %s" % (n, w * 100, d * 100, mark))


if __name__ == "__main__":
    _handle, _path = _open_log(sys.argv[1:])
    if _handle is None:
        main()
    else:
        _saved = sys.stdout
        sys.stdout = _Tee(_saved, _handle)
        try:
            main()
        finally:
            sys.stdout = _saved
            try:
                import datetime as _dt
                _handle.write(chr(10) + "=" * 70 + chr(10))
                _handle.write("종료 시각  "
                              + _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                              + chr(10))
                _handle.close()
            except Exception:                                # noqa: BLE001
                pass
            print(chr(10) + "[기록] %s" % _path)
