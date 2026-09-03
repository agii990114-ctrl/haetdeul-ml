# -*- coding: utf-8 -*-
"""타 도매시장 경락가를 넣어 본다 — 백로그 P3 (2026-09-03)

## 왜 하나

우리는 **서울가락 하나**만 씁니다. 전국 32개 시장 자료가 있는데요.
지역 간 선행성이 있다면 — 산지에 가까운 시장이 먼저 움직이고
서울이 따라간다면 — 그게 신호입니다.

## ★ 시장마다 규격이 다릅니다. 가락 규격을 갖다 대면 안 됩니다

    배추   서울가락 그물망 10kg   ·   서울강서 그물망 12kg   ·   광주서부 12kg
    양파   서울가락 그물망 15kg   ·   대구북부 그물망 20kg   ·   부산반여 20kg

**그대로 섞으면 2026-08-27 사고를 되풀이합니다** (서로 다른 상품을 한
평균에 넣어 배추 ACF 가 0.085 였던 그 사고).

그래서 **시장마다 그 시장의 1위 규격**으로 만듭니다. 그리고 **1위 규격
비중이 50% 미만인 시장은 뺍니다** — 그 시장 안에서도 이미 섞여 있습니다.

## 무엇을 만드나

    mkt{n}_prc_lag1   그 시장의 직전 거래일 경락가
    mkt{n}_gap_lag1   그 시장 값 / 가락 값 − 1   (지역 간 벌어짐)

**둘 다 넣습니다.** 값 자체보다 **가락과 얼마나 벌어졌나**가 신호일 수
있습니다 — 벌어지면 물량이 옮겨 가고 가락 값이 따라 움직입니다.

★ `lag1` 이므로 기준일 시점에 아는 값만 씁니다. 누출이 없습니다.

## 쓰는 법

    python exp_other_markets.py train_20260828b.csv
    python exp_other_markets.py train_20260828b.csv --targets auc --seeds 62 63
"""
from __future__ import annotations

import argparse
import os
import statistics as st
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[2] / "연동"))

import train as T                                            # noqa: E402
from exp_quantile import build                               # noqa: E402

OPS = {"auc": (0.4, 76), "whsl": (0.8, 122), "rtl": (1.0, 81)}
ALL_FOLDS = {
    "A": ("A(검증2023)", "2022-12-31", "2023-12-31"),
    "B": ("B(검증2022)", "2021-12-31", "2022-12-31"),
    "C": ("C(검증2021)", "2020-12-31", "2021-12-31"),
}
ITEMS = ["배추", "무", "양파"]
GARAK = "110001"
MIN_SHARE = 50      # 1위 규격 비중이 이보다 낮은 시장은 뺀다
N_MKT = 3           # 품목마다 물량 상위 몇 곳을 쓸지


def wmape(a, p):
    a, p = np.asarray(a, float), np.asarray(p, float)
    return float(np.abs(a - p).sum() / np.abs(a).sum())


def market_series(verbose=True):
    """품목별로 (시장, 그 시장의 1위 규격) 일별 경락가를 만든다."""
    import psycopg
    from push_forecast import load_env
    load_env()
    out, picked = {}, {}
    with psycopg.connect(os.environ["DATABASE_URL"]) as cn, cn.cursor() as cur:
        for it in ITEMS:
            cur.execute("""
                WITH t AS (
                  SELECT wholesale_market_code mc, wholesale_market_name mn,
                         package_name pk, unit_weight_kg wt,
                         SUM(trade_volume_kg) v,
                         ROW_NUMBER() OVER (PARTITION BY wholesale_market_code
                                            ORDER BY SUM(trade_volume_kg) DESC) rn,
                         SUM(SUM(trade_volume_kg)) OVER (PARTITION BY wholesale_market_code) tot
                    FROM auction_prices_daily
                   WHERE item_name=%s AND grade_code='11'
                     AND auction_date >= '2017-01-01' AND trade_volume_kg > 0
                     AND unit_weight_kg IS NOT NULL
                   GROUP BY 1,2,3,4)
                SELECT mc, mn, pk, wt, ROUND(100.0*v/tot) share, tot
                  FROM t WHERE rn=1 AND mc <> %s AND 100.0*v/tot >= %s
                 ORDER BY tot DESC LIMIT %s""", (it, GARAK, MIN_SHARE, N_MKT))
            picked[it] = cur.fetchall()
            if verbose:
                print(f"  [{it}] 고른 시장")
                for mc, mn, pk, wt, sh, tot in picked[it]:
                    print(f"     {mn:<10} {pk:<6} {wt:>5.0f}kg  1위 비중 {sh:>3.0f}%"
                          f"  총 {tot/1000:,.0f}톤")
            for i, (mc, mn, pk, wt, sh, tot) in enumerate(picked[it], 1):
                cur.execute("""SELECT auction_date,
                                      SUM(trade_amount_krw)/NULLIF(SUM(trade_volume_kg),0)
                                 FROM auction_prices_daily
                                WHERE item_name=%s AND grade_code='11'
                                  AND wholesale_market_code=%s
                                  AND package_name=%s AND unit_weight_kg=%s
                                  AND trade_volume_kg > 0
                                GROUP BY 1 ORDER BY 1""", (it, mc, pk, wt))
                d = pd.DataFrame(cur.fetchall(), columns=["dt", "p"]).dropna()
                d["dt"] = pd.to_datetime(d.dt)
                out[(it, i)] = d.set_index("dt").p.astype(float)
    return out, picked


def attach(df, ser, n):
    """기준일의 **직전 거래일** 값을 붙인다 — 기준일에 아는 값만 쓴다."""
    o = df.copy()
    bd = pd.to_datetime(o["base_dt"])
    items = o["item_nm"].astype(str)
    for i in range(1, n + 1):
        lv = np.full(len(o), np.nan)
        for it in ITEMS:
            s = ser.get((it, i))
            if s is None or s.empty:
                continue
            k = (items == it).to_numpy()
            if not k.any():
                continue
            #   asof — 기준일 **이전** 마지막 거래일
            idx = s.index.searchsorted(bd[k], side="left") - 1
            v = np.where(idx >= 0, s.to_numpy()[np.clip(idx, 0, len(s) - 1)], np.nan)
            lv[k] = v
        o["mkt%d_prc_lag1" % i] = lv
        base = o["auc_prc_lag1"] if "auc_prc_lag1" in o.columns else None
        o["mkt%d_gap_lag1" % i] = (lv / base - 1.0) if base is not None else np.nan
    return o


def fit_per_item(tr, va, feats, cats, seeds, rounds, tgt, anc):
    ancv = va[anc].to_numpy(float)
    actual = va[tgt].to_numpy(float)
    items = va["item_nm"].astype(str).to_numpy()
    cat_in = [c for c in cats if c in feats]
    per = {it: [] for it in ITEMS}
    for s in seeds:
        p = dict(T.PARAMS, seed=s, bagging_seed=s, feature_fraction_seed=s)
        m = lgb.train(p, lgb.Dataset(tr[feats], tr["y"], categorical_feature=cat_in),
                      num_boost_round=rounds)
        pred = ancv * np.exp(m.predict(va[feats]))
        for it in ITEMS:
            k = items == it
            if k.sum():
                per[it].append(wmape(actual[k], pred[k]))
    return {it: (st.mean(v), st.pstdev(v) if len(v) > 1 else 0.0)
            for it, v in per.items() if v}


def main() -> int:
    ap = argparse.ArgumentParser(description="타 도매시장 경락가 [P3]")
    ap.add_argument("csv")
    ap.add_argument("--targets", nargs="+", default=["auc", "whsl", "rtl"])
    ap.add_argument("--folds", nargs="+", default=["A", "B"], choices=["A", "B", "C"])
    ap.add_argument("--train-start", default="2017-01-01")
    ap.add_argument("--gate-lt", type=int, default=3)
    ap.add_argument("--seeds", nargs="+", type=int, default=list(range(62, 82)))
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    print("=" * 88)
    print("[타 도매시장 경락가 · P3] 시장마다 그 시장의 1위 규격으로 만듭니다")
    print(f"  1위 규격 비중 {MIN_SHARE}% 이상인 시장만 · 품목마다 물량 상위 {N_MKT}곳")
    print("=" * 88)
    ser, picked = market_series()
    NEW = sum([["mkt%d_prc_lag1" % i, "mkt%d_gap_lag1" % i] for i in range(1, N_MKT + 1)], [])

    rows = []
    for kind in a.targets:
        alpha, rounds = OPS[kind]
        keep = {}
        for fk in a.folds:
            tag, tend, vend = ALL_FOLDS[fk]
            tr, va, feats, cats, tgt, anc, label = build(a.csv, kind, tend, vend, alpha)
            tr = tr[tr.base_dt >= pd.Timestamp(a.train_start)]
            va = va[va.lead_biz_d >= a.gate_lt].copy()
            t2, v2 = attach(tr, ser, N_MKT), attach(va, ser, N_MKT)
            miss = t2[NEW[0]].isna().mean()
            print(f"\n  [{label} · 폴드 {tag}]  학습 {len(tr):,} · 검증 {len(va):,}"
                  f"  · 값 없는 행 {miss*100:.0f}%")
            base = fit_per_item(tr, va, feats, cats, a.seeds, rounds, tgt, anc)
            add = fit_per_item(t2, v2, feats + NEW, cats, a.seeds, rounds, tgt, anc)
            print(f"    {'':<8}{'배추':>10}{'무':>10}{'양파':>10}")
            print("    %-8s" % "현행" + "".join("%10.4f" % base[k][0] for k in ITEMS))
            print("    %-8s" % "넣음" + "".join("%10.4f" % add[k][0] for k in ITEMS))
            for it in ITEMS:
                g = base[it][0] - add[it][0]
                keep.setdefault(it, []).append((g, max(base[it][1], add[it][1])))
                rows.append(dict(target=kind, fold=tag, item=it, gain=round(g, 5)))

        print(f"\n  [{label} 판정]  양수 = 넣는 게 낫다")
        print(f"    {'품목':<6}" + "".join("%10s" % ("폴드" + f) for f in a.folds)
              + f"{'합산':>10}{'필요':>9}  판정")
        for it in ITEMS:
            rs = keep[it]
            tot, need = sum(r[0] for r in rs), 2 * max(r[1] for r in rs)
            if len({r[0] > 0 for r in rs}) > 1:
                v = "판정 불가 (부호 갈림)"
            elif abs(tot) < need:
                v = "판정 불가 (편차x2 미달)"
            else:
                v = "★ 넣는 게 낫다" if tot > 0 else "★ 넣지 않는 게 낫다"
            print(f"    {it:<6}" + "".join("%+10.4f" % r[0] for r in rs)
                  + f"{tot:>+10.4f}{need:>9.4f}  {v}")

    if a.out:
        pd.DataFrame(rows).to_csv(a.out, index=False, encoding="utf-8-sig")
        print(f"\n[저장] {a.out}")
    print("\n" + "=" * 88)
    print("  통과하면 폴드 C 로 한 번 더 봅니다 (5.7절 ③).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
