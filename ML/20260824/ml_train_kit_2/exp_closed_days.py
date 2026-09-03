# -*- coding: utf-8 -*-
"""휴장 일수를 넣어 본다 — 백로그 P3 무비용 feature (2026-09-03)

## 왜 하나

지금 휴장 정보는 **`market_closed_lag1_yn` 예/아니오 하나**입니다.

    일요일 하루 쉼      -> 1
    추석 닷새 쉼        -> 1     ★ 같은 값

**닷새 쉬면 물량이 밀렸다가 한꺼번에 나옵니다.** 하루 쉰 것과 성격이
다른데 모델은 구분하지 못합니다.

## 무엇을 만드나

    closed_run     대상일 직전 연속 휴장 일수 (0 = 전날 개장)
    closed_next    대상일 직후 연속 휴장 일수 (앞으로 며칠 쉬나)

**두 개를 따로 만듭니다** — 밀렸다 나오는 것(직전)과 미리 사두는 것(직후)은
반대 방향입니다.

★ 둘 다 **달력에서만** 나옵니다. 미래 대상일에도 값이 있고 누출이 없습니다.

## 어디서 달력을 얻나

`auction_prices_daily` 의 **실제 거래일**을 씁니다. 규칙(일요일·명절)이
아니라 실측이라 비정기 휴장도 잡힙니다 (CLAUDE.md 5.8절 — 게시판이 아니라
실거래일로 찾는다).

## 쓰는 법

    python exp_closed_days.py train_20260828b.csv
    python exp_closed_days.py train_20260828b.csv --targets auc --seeds 62 63
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


def wmape(a, p):
    a, p = np.asarray(a, float), np.asarray(p, float)
    return float(np.abs(a - p).sum() / np.abs(a).sum())


def open_days():
    """실제 거래가 있던 날. 규칙이 아니라 실측이다."""
    import psycopg
    from push_forecast import load_env
    load_env()
    with psycopg.connect(os.environ["DATABASE_URL"]) as cn, cn.cursor() as cur:
        cur.execute("""SELECT DISTINCT auction_date FROM auction_prices_daily
                        WHERE wholesale_market_code='110001'
                          AND auction_date >= '2014-12-01'
                          AND trade_volume_kg > 0 ORDER BY 1""")
        return pd.DatetimeIndex([r[0] for r in cur.fetchall()])


def closed_maps(opens):
    """날짜 -> (직전 연속 휴장일, 직후 연속 휴장일)"""
    lo, hi = opens.min(), opens.max()
    all_d = pd.date_range(lo, hi, freq="D")
    is_open = pd.Series(all_d.isin(opens), index=all_d)
    prev, nxt = {}, {}
    run = 0
    for d in all_d:                       # 직전 연속 휴장
        prev[d] = run
        run = 0 if is_open[d] else run + 1
    run = 0
    for d in reversed(all_d):             # 직후 연속 휴장
        nxt[d] = run
        run = 0 if is_open[d] else run + 1
    return prev, nxt


def attach(df, prev, nxt):
    td = pd.to_datetime(df["target_dt"])
    out = df.copy()
    out["closed_run"] = td.map(prev).astype("float64")
    out["closed_next"] = td.map(nxt).astype("float64")
    return out


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
    ap = argparse.ArgumentParser(description="휴장 일수 feature [P3]")
    ap.add_argument("csv")
    ap.add_argument("--targets", nargs="+", default=["auc", "whsl", "rtl"])
    ap.add_argument("--folds", nargs="+", default=["A", "B"], choices=["A", "B", "C"])
    ap.add_argument("--train-start", default="2017-01-01")
    ap.add_argument("--gate-lt", type=int, default=3)
    ap.add_argument("--seeds", nargs="+", type=int, default=list(range(62, 82)))
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    opens = open_days()
    prev, nxt = closed_maps(opens)
    vals = pd.Series(list(prev.values()))
    print("=" * 88)
    print("[휴장 일수 · P3] 운영 조건 · 품목별")
    print(f"  실거래일 {len(opens):,}일 ({opens.min().date()} ~ {opens.max().date()})")
    print(f"  직전 연속 휴장  0일 {(vals==0).mean()*100:.0f}% · "
          f"1일 {(vals==1).mean()*100:.0f}% · 2일 이상 {(vals>=2).mean()*100:.0f}% "
          f"· 최대 {vals.max():.0f}일")
    print(f"  시드 {len(a.seeds)}개 · LT>={a.gate_lt} · 폴드 {', '.join(a.folds)}")
    print("  양수 = 넣는 게 낫다")
    print("=" * 88)

    rows = []
    for kind in a.targets:
        alpha, rounds = OPS[kind]
        keep = {}
        for fk in a.folds:
            tag, tend, vend = ALL_FOLDS[fk]
            tr, va, feats, cats, tgt, anc, label = build(a.csv, kind, tend, vend, alpha)
            tr = tr[tr.base_dt >= pd.Timestamp(a.train_start)]
            va = va[va.lead_biz_d >= a.gate_lt].copy()
            t2, v2 = attach(tr, prev, nxt), attach(va, prev, nxt)
            miss = t2.closed_run.isna().mean()
            print(f"\n  [{label} · 폴드 {tag}]  학습 {len(tr):,} · 검증 {len(va):,}"
                  + (f"  ※ 달력 밖 {miss*100:.0f}%" if miss > 0.01 else ""))
            base = fit_per_item(tr, va, feats, cats, a.seeds, rounds, tgt, anc)
            add = fit_per_item(t2, v2, feats + ["closed_run", "closed_next"],
                               cats, a.seeds, rounds, tgt, anc)
            print(f"    {'':<8}{'배추':>10}{'무':>10}{'양파':>10}")
            print("    %-8s" % "현행" + "".join("%10.4f" % base[k][0] for k in ITEMS))
            print("    %-8s" % "넣음" + "".join("%10.4f" % add[k][0] for k in ITEMS))
            for it in ITEMS:
                g = base[it][0] - add[it][0]
                keep.setdefault(it, []).append((g, max(base[it][1], add[it][1])))
                rows.append(dict(target=kind, fold=tag, item=it, gain=round(g, 5)))

        print(f"\n  [{label} 판정]")
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
