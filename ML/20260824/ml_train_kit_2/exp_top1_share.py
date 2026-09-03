# -*- coding: utf-8 -*-
"""주산지 대표성(1위 산지 비중)을 feature 로 넣어 본다 — 백로그 [M-06]

## 왜 하나

우리는 품목×월로 **주산지 관측소 하나**를 골라 그 기상을 씁니다.
그런데 **1위 산지가 물량의 절반도 대표하지 못하는 날이 많습니다.**

    1위 산지 비중이 50% 미만인 날 (2017~)
        양파  2,023일 (74.1%)      <- 대부분의 날
        배추  1,324일 (48.3%)
        무    1,004일 (36.6%)

월별로도 크게 흔들립니다.

    무     3월 90%  ->  11월 30%
    배추  12월 83%  ->   6월 32%
    양파   5월 74%  ->   1월 32%

**매핑을 고쳐도 이 문제는 안 없어집니다.** 1위가 40%뿐이면 어느 관측소를
골라도 나머지 60%를 못 봅니다. 그래서 **"이 구간은 기상을 덜 믿어라" 를
모델이 배울 수 있게** 비중 자체를 입력으로 줍니다.

## ★ 실측이 아니라 프로파일을 쓴다

예측 대상일은 **아직 안 온 날**이라 그날 비중을 알 수 없습니다.
그래서 (품목 × 월 × 순) 평균 비중을 만들어 씁니다.

**프로파일은 학습 구간 자료로만 만듭니다.** 검증 연도까지 넣어 만들면
답을 미리 보는 셈입니다. (학사일정에서 쓴 방식과 같습니다 — 5.10절)

## 무엇을 견주나

    keep    현행 그대로                      <- 기준
    share   + prod_area_top1_share (프로파일)
    both    + 비중 · 비중x기온 (곱)          <- "믿을 만할 때만 기온을 보라"

★ `both` 를 넣는 이유: 비중만 주면 모델이 스스로 곱해야 합니다.
  트리 모델은 곱셈을 잘 못 만들므로 직접 만들어 줍니다.

## 쓰는 법

    python exp_top1_share.py train_20260828b.csv
    python exp_top1_share.py train_20260828b.csv --targets auc --seeds 62 63
"""
from __future__ import annotations

import argparse
import statistics as st
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import train as T                                            # noqa: E402
from exp_quantile import build                               # noqa: E402

OPS = {"auc": (0.4, 76), "whsl": (0.8, 122), "rtl": (1.0, 81)}
FOLDS = [("A(검증2023)", "2022-12-31", "2023-12-31"),
         ("B(검증2022)", "2021-12-31", "2022-12-31")]
ITEMS = ["배추", "무", "양파"]
VOL = HERE.parents[2] / "DB" / "데이터" / "daily_volume_202608240949.csv"
TEMP = "prod_area_temp_avg_lag1"


def wmape(a, p):
    a, p = np.asarray(a, float), np.asarray(p, float)
    return float(np.abs(a - p).sum() / np.abs(a).sum())


def sun(day):
    """상순(1~10) · 중순(11~20) · 하순(21~)"""
    return np.where(day <= 10, 1, np.where(day <= 20, 2, 3))


def load_profile(train_end):
    """(품목 × 월 × 순) 평균 1위 비중. **학습 구간 자료로만** 만든다."""
    if not VOL.exists():
        sys.exit(f"반입량 자료가 없습니다: {VOL}")
    d = pd.read_csv(VOL)
    d["dt"] = pd.to_datetime(d.base_date)
    d = d[(d.item_label.isin(ITEMS)) & (d.total_ton > 0)
          & (d.dt >= pd.Timestamp("2017-01-01"))
          & (d.dt <= pd.Timestamp(train_end))].copy()
    d["share"] = (d.top1_ton / d.total_ton).clip(0, 1)
    d["mon"] = d.dt.dt.month
    d["sun"] = sun(d.dt.dt.day.to_numpy())
    p = (d.groupby(["item_label", "mon", "sun"]).share.mean()
         .rename("prod_area_top1_share").reset_index()
         .rename(columns={"item_label": "item_nm"}))
    return p


def attach(df, prof):
    """대상일의 (월,순) 으로 붙인다. 대상일은 미래이므로 프로파일만 쓸 수 있다."""
    td = pd.to_datetime(df["target_dt"])
    k = df[["item_nm"]].copy()
    k["mon"] = td.dt.month.to_numpy()
    k["sun"] = sun(td.dt.day.to_numpy())
    k["item_nm"] = k["item_nm"].astype(str)
    m = k.merge(prof, on=["item_nm", "mon", "sun"], how="left")
    out = df.copy()
    out["prod_area_top1_share"] = m["prod_area_top1_share"].to_numpy()
    return out


def make_variant(tr, va, feats, cats, kind, prof):
    if kind == "keep":
        return tr, va, list(feats), list(cats)
    t, v = attach(tr, prof), attach(va, prof)
    f = list(feats) + ["prod_area_top1_share"]
    if kind == "both" and TEMP in feats:
        #   "믿을 만할 때만 기온을 보라" — 트리는 곱셈을 잘 못 만든다
        for d in (t, v):
            d["_share_x_temp"] = d["prod_area_top1_share"] * d[TEMP]
        f = f + ["_share_x_temp"]
    return t, v, f, list(cats)


def fit_per_item(tr, va, feats, cats, seeds, rounds, tgt, anc):
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


def main() -> int:
    ap = argparse.ArgumentParser(description="주산지 1위 비중을 feature 로 넣어 본다")
    ap.add_argument("csv")
    ap.add_argument("--targets", nargs="+", default=["auc", "whsl", "rtl"])
    ap.add_argument("--variants", nargs="+", default=["keep", "share", "both"])
    ap.add_argument("--train-start", default="2017-01-01")
    ap.add_argument("--gate-lt", type=int, default=3)
    ap.add_argument("--seeds", nargs="+", type=int, default=list(range(62, 82)))
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    print("=" * 92)
    print("[주산지 대표성] 1위 산지 비중을 넣어 본다 · 운영 조건 · 품목별")
    print(f"  시드 {len(a.seeds)}개 ({a.seeds[0]}~{a.seeds[-1]}) · LT>={a.gate_lt}")
    print("  ★ 프로파일은 폴드마다 학습 구간 자료로만 만듭니다 (답을 미리 보지 않게)")
    print("  양수 = 그 변형이 현행보다 낫다")
    print("=" * 92)

    rows = []
    for kind in a.targets:
        alpha, rounds = OPS[kind]
        keep = {}
        for tag, tend, vend in FOLDS:
            prof = load_profile(tend)
            tr, va, feats, cats, tgt, anc, label = build(a.csv, kind, tend, vend, alpha)
            tr = tr[tr.base_dt >= pd.Timestamp(a.train_start)]
            va = va[va.lead_biz_d >= a.gate_lt].copy()
            print(f"\n  [{label} · 폴드 {tag}]  α={alpha} · {rounds}그루"
                  f" · 학습 {len(tr):,}행 · 검증 {len(va):,}행"
                  f" · 프로파일 {len(prof)}칸(~{tend})")
            print(f"    {'':<10}{'배추':>10}{'무':>10}{'양파':>10}{'통합':>10}")

            base = None
            for vname in a.variants:
                t2, v2, f2, c2 = make_variant(tr, va, feats, cats, vname, prof)
                if vname != "keep":
                    miss = t2["prod_area_top1_share"].isna().mean()
                    if miss > 0.02:
                        print(f"      ※ 비중이 빈 행 {miss*100:.0f}% — 프로파일 확인 필요")
                r = fit_per_item(t2, v2, f2, c2, a.seeds, rounds, tgt, anc)
                if vname == "keep":
                    base = r
                    print("    %-10s" % "현행"
                          + "".join("%10.4f" % r[k][0] for k in ITEMS + ["통합"]))
                    continue
                line = "    %-10s" % vname
                for k in ITEMS + ["통합"]:
                    gain = base[k][0] - r[k][0]
                    line += "%+10.4f" % gain
                    keep.setdefault((vname, k), []).append(
                        (gain, max(base[k][1], r[k][1])))
                    rows.append(dict(target=kind, fold=tag, variant=vname, item=k,
                                     wmape_keep=round(base[k][0], 5),
                                     wmape_var=round(r[k][0], 5),
                                     gain=round(gain, 5)))
                print(line)

        print(f"\n  [{label} 판정]  (양수 = 넣는 게 낫다)")
        print(f"    {'변형':<10}{'품목':<6}{'폴드A':>10}{'폴드B':>10}"
              f"{'합산':>10}{'필요':>9}  판정")
        for vname in a.variants:
            if vname == "keep":
                continue
            for it in ITEMS + ["통합"]:
                rs = keep.get((vname, it))
                if not rs or len(rs) < 2:
                    continue
                tot = rs[0][0] + rs[1][0]
                need = 2 * max(r[1] for r in rs)
                if (rs[0][0] > 0) != (rs[1][0] > 0):
                    v = "판정 불가 (부호 갈림)"
                elif abs(tot) < need:
                    v = "판정 불가 (편차x2 미달)"
                else:
                    v = "★ 넣는 게 낫다" if tot > 0 else "★ 넣지 않는 게 낫다"
                print(f"    {vname:<10}{it:<6}{rs[0][0]:>+10.4f}{rs[1][0]:>+10.4f}"
                      f"{tot:>+10.4f}{need:>9.4f}  {v}")

    if a.out:
        pd.DataFrame(rows).to_csv(a.out, index=False, encoding="utf-8-sig")
        print(f"\n[저장] {a.out}")
    print("\n" + "=" * 92)
    print("  통합값으로 결정하지 않습니다 (8절). 하나만 걸리면 새 시드로 확인합니다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
