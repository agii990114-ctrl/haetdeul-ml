# -*- coding: utf-8 -*-
"""경락 모멘텀을 중도매가에 넣어 본다 — 백로그 [M-13] 후보 ③

## 왜 하나

중도매가가 셋 다 앵커 수준입니다 (2026 실전: 무 +0.4% · 배추 −2.3% · 양파 −0.3%).
원인을 쟀더니 **중도매가는 열흘 중 엿새가 어제와 값이 같습니다** (58~68%).
앵커가 거의 완벽해 모델이 낄 자리가 없습니다.

**그러면 어디서 신호를 얻나** — 경락가는 거의 매일 움직입니다(같은 날 0.6~1.3%).
경락이 먼저 움직이고 중도매가 따라간다면 그게 신호입니다.

### 먼저 재 봤습니다 (2017~ · 상관)

    기준일까지의 경락 3일 움직임 -> 3~18일 뒤 중도매 변화
        양파   0.237 / 0.173 / 0.155      뚜렷
        배추   0.109 / 0.119 / 0.088      약하지만 일관
        무    -0.036 / -0.015 / -0.002    없음

**무에는 전이가 없습니다.** 이 실험이 무를 고칠 가능성은 낮습니다.
그래도 돌립니다 — 상관이 없다고 트리 모델에 쓸모없는 것은 아니고,
**없다는 것도 기록해야** 다음 사람이 또 안 뒤집니다.

## 무엇을 넣나 — **수준이 아니라 비율**

지금도 `auc_prc_lag1` · `auc_prc_lag3` · `auc_prc_avg7` 이 **수준**으로
들어 있습니다. 없는 것은 **비율**입니다.

    auc_mom3 = auc_prc_lag1 / auc_prc_lag3     최근 3일 방향
    auc_mom7 = auc_prc_lag1 / auc_prc_avg7     7일 평균 대비 위치

트리는 나눗셈을 못 합니다 — 두 수준을 주면 각각 자르기만 하지 비율을
못 만듭니다. 그래서 **비율은 따로 줘야** 합니다.

> 5.13 절에서 배운 것과 같습니다 — *"수준을 넣지 말고 비율로 넣으세요.
> 비율에는 몇 년도인가가 안 남습니다."*

## 판정

**3폴드 · 품목별 · 운영 조건** (CLAUDE.md 5.7 ③).
2폴드 부호 일치는 탐색 기준이고 채택 기준이 아닙니다.

    python exp_auc_momentum.py <csv> --targets whsl --folds A B C
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
ALL_FOLDS = {
    "A": ("A(검증2023)", "2022-12-31", "2023-12-31"),
    "B": ("B(검증2022)", "2021-12-31", "2022-12-31"),
    "C": ("C(검증2021)", "2020-12-31", "2021-12-31"),
}
ITEMS = ["배추", "무", "양파"]

#: 변형 이름 -> 더할 컬럼
VARIANTS = {
    "keep": [],
    "mom3": ["auc_mom3"],
    "mom7": ["auc_mom7"],
    "both": ["auc_mom3", "auc_mom7"],
}


def wmape(a, p):
    a, p = np.asarray(a, float), np.asarray(p, float)
    return float(np.abs(a - p).sum() / np.abs(a).sum())


def add_mom(df):
    """비율 두 개를 만든다. 원본은 안 건드린다."""
    out = df.copy()
    l1 = pd.to_numeric(out.get("auc_prc_lag1"), errors="coerce")
    l3 = pd.to_numeric(out.get("auc_prc_lag3"), errors="coerce")
    a7 = pd.to_numeric(out.get("auc_prc_avg7"), errors="coerce")
    out["auc_mom3"] = l1 / l3.replace(0, np.nan)
    out["auc_mom7"] = l1 / a7.replace(0, np.nan)
    return out


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
    ap = argparse.ArgumentParser(description="경락 모멘텀을 넣어 본다 [M-13 ③]")
    ap.add_argument("csv")
    ap.add_argument("--targets", nargs="+", default=["whsl"])
    ap.add_argument("--variants", nargs="+", default=list(VARIANTS))
    ap.add_argument("--train-start", default="2017-01-01")
    ap.add_argument("--gate-lt", type=int, default=3)
    ap.add_argument("--seeds", nargs="+", type=int, default=list(range(62, 82)))
    ap.add_argument("--folds", nargs="+", default=["A", "B", "C"],
                    choices=["A", "B", "C"])
    a = ap.parse_args()
    folds = [ALL_FOLDS[f] for f in a.folds]

    print("=" * 92)
    print("[경락 모멘텀] 중도매가에 경락 비율을 넣어 본다 · 운영 조건 · 품목별")
    print(f"  시드 {len(a.seeds)}개 · LT>={a.gate_lt} · 폴드 {' '.join(a.folds)}")
    print("  양수 = 그 변형이 현행보다 낫다 (개선율)")
    print("  ★ 상관은 양파에만 뚜렷했습니다 (0.237). 무는 없습니다(-0.036).")
    print("=" * 92)

    tally: dict[tuple, list] = {}
    for kind in a.targets:
        alpha, rounds = OPS[kind]
        for tag, tend, vend in folds:
            tr, va, feats, cats, tgt, anc, label = build(a.csv, kind, tend, vend, alpha)
            tr = add_mom(tr[tr.base_dt >= pd.Timestamp(a.train_start)])
            va = add_mom(va[va.lead_biz_d >= a.gate_lt].copy())
            print(f"\n  [{label} · 폴드 {tag}]  α={alpha} · {rounds}그루"
                  f" · 학습 {len(tr):,}행 · 검증 {len(va):,}행")
            print(f"    {'':<8}{'배추':>11}{'무':>11}{'양파':>11}{'통합':>11}")
            base = None
            for vname in a.variants:
                cols = [c for c in VARIANTS[vname] if c in tr.columns]
                f2 = feats + cols
                r = fit_per_item(tr, va, f2, cats, a.seeds, rounds, tgt, anc)
                if vname == "keep":
                    base = r
                    print("      %-6s" % vname
                          + "".join("%11.4f" % r[k][0] for k in ITEMS + ["통합"]))
                    continue
                cells = []
                for k in ITEMS + ["통합"]:
                    imp = (base[k][0] - r[k][0]) / base[k][0] * 100
                    #   ★ 시드 편차도 같이 담는다. 부호 일치만으로는 판정이
                    #     반쪽이다 — 이득이 편차x2 를 넘어야 한다 (5.7).
                    sd = (base[k][1] + r[k][1]) / 2 / base[k][0] * 100
                    cells.append("%+10.2f%%" % imp)
                    tally.setdefault((kind, vname, k), []).append((imp, sd))
                print("      %-6s" % vname + "".join(cells))

    print("\n" + "=" * 92)
    print("[3폴드 판정]  부호가 다 같아야 방향을 믿습니다 (5.7 ③)")
    print("=" * 92)
    for (kind, vname, item), pairs in sorted(tally.items()):
        if len(pairs) < 2:
            continue
        vals = [p[0] for p in pairs]
        sds = [p[1] for p in pairs]
        same = all(v > 0 for v in vals) or all(v < 0 for v in vals)
        #   합산 이득이 편차x2 를 넘나 (5.7). 부호 일치만으로는 반쪽이다.
        need = 2 * (sum(s * s for s in sds) ** 0.5)
        got = abs(sum(vals))
        if not same:
            mark = "★ 갈림 — 판정 불가"
        elif got < need:
            mark = "부호는 같으나 편차x2 미달 — 증명 못 함 (%.2f < %.2f)" % (got, need)
        else:
            mark = "★ 통과 (양수)" if vals[0] > 0 else "★ 통과 (음수 — 해롭다)"
        print("  %-5s %-5s %-3s  %s  합%+6.2f 필요%5.2f   %s"
              % (kind, vname, item,
                 " ".join("%+6.2f%%" % v for v in vals), sum(vals), need, mark))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
