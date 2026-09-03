# -*- coding: utf-8 -*-
"""앵커를 잘 골랐는가 — 후보 여섯을 견준다. 백로그 [M-15] (2026-09-03)

## 왜 하나

우리 모델은 **앵커에서 얼마나 움직일지**를 배웁니다.

    학습   y = log(정답 / 앵커)
    예측   예측가 = 앵커 x exp(모델 출력)

그래서 **앵커가 곧 출발점이고, 동시에 정의상 baseline** 입니다 —
모델이 0을 내면 앵커가 그대로 나갑니다.

**그런데 "그 앵커가 최선인가" 를 한 번도 안 물었습니다** (CLAUDE.md 11절).
오늘 feature 실험 셋이 전부 "변경 없음" 으로 끝났습니다.
**이득이 feature 에 없다면 토대를 봐야 합니다.**

## 무엇을 견주나

    now      현행 수축앵커  a x 어제값 + (1-a) x 7일평균
             a = 경락 0.4 · 중도매 0.8 · 소매 1.0
    lag1     어제값만
    avg7     최근 7일 평균만
    avg14    최근 14일 평균만
    prev_yr  작년 같은 시기
    mix_yr   현행 x 0.8 + 작년같은시기 x 0.2

★ `prev_yr` 은 앵커로 쓰기엔 거칠어 보이지만 **계절이 강한 계열에서는
  어제값보다 나을 수 있습니다.** 실제로 반입량 모델에서 작년동기가
  훨씬 센 baseline 이었던 적이 있습니다 (2026-08-26 · 11절).

## ★ 공정하게 재는 법 — 두 가지를 맞춥니다

**① 같은 행에서 잰다.** 후보마다 결측이 다릅니다 (`prev_yr` 은 첫 해가 빕니다).
   **여섯 후보가 모두 값이 있는 행만** 남겨 견줍니다. 안 그러면 쉬운 행만
   남은 후보가 유리해집니다.

**② 앵커로 쓴 컬럼은 feature 에서 뺀다.** 운영이 그렇게 합니다
   (`_anchor_mix` 를 만들면 원본 `lag1` 을 뺍니다). 안 빼면 정답을 두 번
   주는 셈입니다.

## 무엇을 보나 — 두 가지

    앵커 자체     그 앵커를 그대로 예측값으로 썼을 때의 오차 (baseline)
    모델          그 앵커로 학습한 모델의 오차

**둘이 갈릴 수 있습니다.** 좋은 baseline 이 좋은 앵커라는 보장은 없습니다 —
앵커가 이미 정확하면 모델이 배울 것이 없습니다.

## 주의

앵커를 바꾸면 **타겟 정의가 바뀌어 기존 성능 기록이 전부 무효**가 됩니다.
2폴드에서 이겨도 바로 안 바꿉니다. 폴드 C 까지 봅니다 (5.7절 ③).

## 쓰는 법

    python exp_anchor_cands.py train_20260828b.csv
    python exp_anchor_cands.py train_20260828b.csv --targets auc --seeds 62 63
"""
from __future__ import annotations

import argparse
import statistics as st
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import train as T                                            # noqa: E402

OPS = {"auc": (0.4, 76), "whsl": (0.8, 122), "rtl": (1.0, 81)}
ALL_FOLDS = {
    "A": ("A(검증2023)", "2022-12-31", "2023-12-31"),
    "B": ("B(검증2022)", "2021-12-31", "2022-12-31"),
    "C": ("C(검증2021)", "2020-12-31", "2021-12-31"),
}
ITEMS = ["배추", "무", "양파"]
CANDS = ["now", "lag1", "avg7", "avg14", "prev_yr", "mix_yr"]


def wmape(a, p):
    a, p = np.asarray(a, float), np.asarray(p, float)
    return float(np.abs(a - p).sum() / np.abs(a).sum())


def cols_for(target):
    """이 타겟의 가격 계열 컬럼 이름들."""
    base = {"auc": "auc_prc", "whsl": "whsl_prc", "rtl": "rtl_prc"}[target]
    return {"lag1": base + "_lag1", "avg7": base + "_avg7",
            "avg14": base + "_avg14", "prev_yr": base + "_prev_yr"}


def load_common(csv, target, alpha):
    """후보 여섯이 모두 값이 있는 행만 남긴 프레임.

    ★ train.py 와 같은 재료로 만든다. 다르면 비교가 성립하지 않는다.
    """
    tgt, anc0, label = T.TARGETS[target]
    df = T.load(csv, target=tgt, anchor=anc0)
    df = df[df["item_nm"].astype(str).isin(T.DEFAULT_ITEMS)].copy()

    C = cols_for(target)
    need = [tgt] + list(C.values())
    miss = [c for c in need if c not in df.columns]
    if miss:
        sys.exit("컬럼이 없습니다: %s" % ", ".join(miss))

    #   ★ 여섯 후보가 모두 성립하는 행만. 같은 행에서 견주기 위해서다.
    ok = df[tgt].notna()
    for c in C.values():
        ok &= df[c].notna() & (df[c] > 0)
    n_all = len(df)
    df = df[ok].copy()

    anc = {}
    anc["lag1"] = df[C["lag1"]].to_numpy(float)
    anc["avg7"] = df[C["avg7"]].to_numpy(float)
    anc["avg14"] = df[C["avg14"]].to_numpy(float)
    anc["prev_yr"] = df[C["prev_yr"]].to_numpy(float)
    anc["now"] = alpha * anc["lag1"] + (1 - alpha) * anc["avg7"]
    anc["mix_yr"] = 0.8 * anc["now"] + 0.2 * anc["prev_yr"]

    #   앵커에 쓰는 컬럼은 전부 feature 에서 뺀다 — 후보마다 feature 가
    #   달라지면 무엇 때문에 좋아졌는지 못 가린다. 여섯이 같은 재료를 본다.
    drop = set(T.DROP) | set(T.TARGET_DROP.get(target, set()))
    drop |= set(T.NEW_PRICE_COLS) | set(T.CLIM_NEW) | set(T.FCST_COLS)
    drop |= set(T.FCST_DIAG) | set(T.VOLPRED_ORACLE) | set(T.VOLPRED_COLS)
    drop |= set(C.values())
    feats = [c for c in df.columns if c not in drop | {"y"}]
    cats = [c for c in T.CAT if c in feats]
    return df, anc, feats, cats, tgt, label, n_all


def fit_eval(tr, va, anc_tr, anc_va, feats, cats, seeds, rounds, tgt):
    """앵커 하나로 학습하고 품목별 WMAPE 를 낸다."""
    y = np.log(tr[tgt].to_numpy(float) / anc_tr)
    actual = va[tgt].to_numpy(float)
    items = va["item_nm"].astype(str).to_numpy()
    cat_in = [c for c in cats if c in feats]
    per = {it: [] for it in ITEMS}
    for s in seeds:
        p = dict(T.PARAMS, seed=s, bagging_seed=s, feature_fraction_seed=s)
        m = lgb.train(p, lgb.Dataset(tr[feats], y, categorical_feature=cat_in),
                      num_boost_round=rounds)
        pred = anc_va * np.exp(m.predict(va[feats]))
        for it in ITEMS:
            k = items == it
            if k.sum():
                per[it].append(wmape(actual[k], pred[k]))
    out = {it: (st.mean(v), st.pstdev(v) if len(v) > 1 else 0.0)
           for it, v in per.items() if v}
    #   앵커 자체를 예측값으로 썼을 때 (baseline)
    out["_anchor"] = {it: wmape(actual[items == it], anc_va[items == it])
                      for it in ITEMS if (items == it).sum()}
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="앵커 후보 여섯을 견준다 [M-15]")
    ap.add_argument("csv")
    ap.add_argument("--targets", nargs="+", default=["auc", "whsl", "rtl"])
    ap.add_argument("--cands", nargs="+", default=CANDS)
    ap.add_argument("--folds", nargs="+", default=["A", "B"], choices=["A", "B", "C"])
    ap.add_argument("--train-start", default="2017-01-01")
    ap.add_argument("--gate-lt", type=int, default=3)
    ap.add_argument("--seeds", nargs="+", type=int, default=list(range(62, 72)))
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    print("=" * 96)
    print("[앵커 후보 비교 · M-15] 운영 조건 · 품목별 · 여섯 후보가 다 있는 행에서만")
    print(f"  시드 {len(a.seeds)}개 · LT>={a.gate_lt} · 학습 {a.train_start}~"
          f" · 폴드 {', '.join(a.folds)}")
    print("  ※ 앵커에 쓰는 가격 컬럼은 여섯 후보 모두 feature 에서 뺐습니다")
    print("=" * 96)

    rows = []
    for kind in a.targets:
        alpha, rounds = OPS[kind]
        df, anc, feats, cats, tgt, label, n_all = load_common(a.csv, kind, alpha)
        print(f"\n  [{label}]  α={alpha} · {rounds}그루 · feature {len(feats)}개")
        print(f"    여섯 후보가 다 있는 행 {len(df):,} / {n_all:,}"
              f" ({len(df)/n_all*100:.0f}%)")
        keep = {}
        for fk in a.folds:
            tag, tend, vend = ALL_FOLDS[fk]
            m_tr = (df.base_dt >= pd.Timestamp(a.train_start)) & (df.base_dt <= pd.Timestamp(tend))
            m_va = ((df.base_dt > pd.Timestamp(tend)) & (df.base_dt <= pd.Timestamp(vend))
                    & (df.lead_biz_d >= a.gate_lt))
            tr, va = df[m_tr], df[m_va]
            print(f"\n    폴드 {tag} · 학습 {len(tr):,}행 · 검증 {len(va):,}행")
            print(f"      {'후보':<9}{'배추':>9}{'무':>9}{'양파':>9}   "
                  f"{'(앵커만) 배추':>13}{'무':>8}{'양파':>8}")
            for c in a.cands:
                r = fit_eval(tr, va, anc[c][m_tr.to_numpy()], anc[c][m_va.to_numpy()],
                             feats, cats, a.seeds, rounds, tgt)
                line = "      %-9s" % c
                for it in ITEMS:
                    line += "%9.4f" % r[it][0]
                line += "   "
                for it in ITEMS:
                    line += "%8.4f" % r["_anchor"][it]
                print(line)
                for it in ITEMS:
                    keep.setdefault((c, it), []).append((r[it][0], r[it][1]))
                    rows.append(dict(target=kind, fold=tag, cand=c, item=it,
                                     wmape=round(r[it][0], 5),
                                     sd=round(r[it][1], 5),
                                     anchor_only=round(r["_anchor"][it], 5)))

        print(f"\n  [{label} 판정]  현행(now) 대비 · 양수 = 그 후보가 낫다")
        print(f"    {'후보':<9}{'품목':<6}"
              + "".join("%10s" % ("폴드" + f) for f in a.folds)
              + f"{'합산':>10}{'필요':>9}  판정")
        for c in a.cands:
            if c == "now":
                continue
            for it in ITEMS:
                base = keep[("now", it)]
                cur = keep[(c, it)]
                gs = [b[0] - x[0] for b, x in zip(base, cur)]
                sds = [max(b[1], x[1]) for b, x in zip(base, cur)]
                tot, need = sum(gs), 2 * max(sds)
                if len({g > 0 for g in gs}) > 1:
                    v = "판정 불가 (부호 갈림)"
                elif abs(tot) < need:
                    v = "판정 불가 (편차x2 미달)"
                else:
                    v = "★ 이 후보가 낫다" if tot > 0 else "★ 현행이 낫다"
                print(f"    {c:<9}{it:<6}" + "".join("%+10.4f" % g for g in gs)
                      + f"{tot:>+10.4f}{need:>9.4f}  {v}")

    if a.out:
        pd.DataFrame(rows).to_csv(a.out, index=False, encoding="utf-8-sig")
        print(f"\n[저장] {a.out}")
    print("\n" + "=" * 96)
    print("  ★ 앵커를 바꾸면 타겟 정의가 바뀌어 기존 성능 기록이 전부 무효가 됩니다.")
    print("    2폴드에서 이겨도 바로 안 바꿉니다 — 폴드 C 까지 봅니다 (5.7절 ③).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
