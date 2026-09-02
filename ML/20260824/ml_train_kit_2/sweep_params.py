# -*- coding: utf-8 -*-
"""
하이퍼파라미터 탐색 (M-11)
==========================
한 파라미터를 여러 값으로 바꿔가며 3폴드 × 3타겟에서 잰다.

    python sweep_params.py <csv> --param min_data_in_leaf --values 60 180 360 540

왜 min_data_in_leaf 부터인가
    이 프로젝트의 핵심 함정은 "행수 ≠ 실질 표본" 이다. 한 기준일이 리드타임
    18행으로 복제되므로 학습 행 79,650 의 실질 표본은 고유 기준일 1,475 개다.

    그런데 min_data_in_leaf 는 **행** 기준으로 동작한다. 기본값 60 은
    리프 하나에 고유 기준일 3.3 개에 해당한다. 즉 모델이 날짜 3 개짜리
    리프를 만들 수 있고, 그것은 패턴이 아니라 날짜를 외우는 것이다.

    18 의 배수로 올리면 리프가 최소 N 개 기준일을 덮게 된다.
        60 → 3.3개 · 180 → 10개 · 360 → 20개 · 540 → 30개

판정
    ablation 과 같은 규율을 쓴다. 검증 한 해에서 좋아졌다고 바꾸면 그 해에만
    맞는 설정이 된다. **세 폴드에서 부호가 같고 편차×2 를 넘을 때만** 채택한다.

    gain = WMAPE(기준값) − WMAPE(시험값).  양수면 시험값이 더 좋다.

주의 (백로그 v2.0 의 경고)
    표본 대비 시행 횟수가 많으면 검증셋 과적합이다. 20~30회로 제한한다.
    이 스크립트의 기본 그리드는 4값 × 3폴드 = 12회다.
"""
import argparse
import numpy as np
import pandas as pd
import lightgbm as lgb

from train import (TARGETS, TARGET_DROP, CAT, PARAMS, DEFAULT_ITEMS, wmape, load)
import train as _train

FOLDS = [("A", "2022-12-31", "2023-12-31"),
         ("B", "2021-12-31", "2022-12-31"),
         ("C", "2020-12-31", "2021-12-31")]


def prep(csv, target_key, items, train_start):
    """타겟별로 한 번만 로드·정리한다. 그리드는 이 위에서 돈다."""
    target, anchor, label = TARGETS[target_key]
    drop = set(_train.DROP) | TARGET_DROP.get(target_key, set())
    df = load(csv, target=target, anchor=anchor)
    keep = [i for i in items if i in set(df.item_nm.astype(str))]
    df = df[df.item_nm.astype(str).isin(keep)].copy()
    if hasattr(df.item_nm, "cat"):
        df["item_nm"] = df.item_nm.cat.remove_unused_categories()
    df = df[df.base_dt >= train_start]
    df["y_ratio"] = np.log(df[target] / df[anchor])
    feats = [c for c in df.columns if c not in drop | {"y_ratio"}]
    cats = [c for c in CAT if c in feats]
    return df, feats, cats, target, anchor, label


def run(df, feats, cats, target, anchor, train_end, valid_end, seeds, gate, params):
    tr = df[df.base_dt <= train_end]
    va = df[(df.base_dt > train_end) & (df.base_dt <= valid_end)].copy()
    preds, iters = [], []
    for s in seeds:
        p = dict(params, seed=s, bagging_seed=s, feature_fraction_seed=s)
        m = lgb.train(p, lgb.Dataset(tr[feats], tr.y_ratio, categorical_feature=cats),
                      num_boost_round=5000,
                      valid_sets=[lgb.Dataset(va[feats], va.y_ratio)],
                      callbacks=[lgb.early_stopping(200, verbose=False)])
        out = m.predict(va[feats], num_iteration=m.best_iteration)
        preds.append(va[anchor].values * np.exp(out))
        iters.append(m.best_iteration)
    if gate > 0:
        g = (va.lead_biz_d < gate).values
        preds = [np.where(g, va[anchor].values, p) for p in preds]
    ws = [wmape(va[target], p) for p in preds]
    ens = wmape(va[target], np.mean(preds, axis=0))
    return dict(ens=ens, sd=float(np.std(ws, ddof=1)) if len(ws) > 1 else 0.0,
                base=wmape(va[target], va[anchor]),
                it_lo=min(iters), it_hi=max(iters),
                n_tr=int(tr.base_dt.nunique()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--param", default="min_data_in_leaf")
    ap.add_argument("--values", type=int, nargs="+", default=[60, 180, 360, 540])
    ap.add_argument("--targets", nargs="+", default=["auc", "whsl", "rtl"])
    ap.add_argument("--items", nargs="+", default=DEFAULT_ITEMS)
    ap.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44, 45, 46])
    ap.add_argument("--train-start", default="2017-01-01")
    ap.add_argument("--gate-lt", type=int, default=3)
    ap.add_argument("--out", default="sweep_result.csv")
    a = ap.parse_args()

    ref = a.values[0]        # 기준값 (현행)
    print("[탐색] %s = %s  ·  기준값 %s" % (a.param, a.values, ref))
    print("[조건] 학습 %s~ · 폴드 3개 · 시드 %d개 · 게이트 LT<%d · %s"
          % (a.train_start, len(a.seeds), a.gate_lt, " ".join(a.items)))
    print("[판정] gain = WMAPE(기준) − WMAPE(시험). 양수면 시험값이 낫다.")
    print("       세 폴드 부호 일치 + 편차×2 초과일 때만 채택")

    rows = []
    for tk in a.targets:
        df, feats, cats, target, anchor, label = prep(a.csv, tk, a.items, a.train_start)
        print()
        print("=" * 78)
        print("  %s  (%s / 앵커 %s) · feature %d개" % (label, target, anchor, len(feats)))
        print("=" * 78)
        print("  %-6s %-6s %9s %9s %9s %9s %8s %10s" %
              ("폴드", a.param[:6], "WMAPE", "baseline", "개선율", "gain", "편차", "iter"))
        for fname, te, ve in FOLDS:
            base_w = None
            for v in a.values:
                params = dict(PARAMS)
                params[a.param] = v
                r = run(df, feats, cats, target, anchor, te, ve,
                        a.seeds, a.gate_lt, params)
                if v == ref:
                    base_w = r["ens"]
                gain = (base_w - r["ens"]) if base_w is not None else float("nan")
                vd = "—" if v == ref else ("O" if gain > 2 * r["sd"]
                                           else "X" if gain < -2 * r["sd"] else "△")
                print("  %-6s %-6d %9.4f %9.4f %+8.1f%% %+9.4f %8.4f %5d~%-4d %s" %
                      (fname, v, r["ens"], r["base"],
                       (1 - r["ens"] / r["base"]) * 100, gain, r["sd"],
                       r["it_lo"], r["it_hi"], vd))
                rows.append(dict(target=tk, fold=fname, param=a.param, value=v,
                                 wmape=round(r["ens"], 4), baseline=round(r["base"], 4),
                                 improve=round(1 - r["ens"] / r["base"], 4),
                                 gain=round(gain, 5) if base_w is not None else None,
                                 std=round(r["sd"], 4), verdict=vd,
                                 iter_lo=r["it_lo"], iter_hi=r["it_hi"],
                                 train_days=r["n_tr"]))
            print()

    d = pd.DataFrame(rows)
    d.to_csv(a.out, index=False, encoding="utf-8-sig")

    # ── 3폴드 종합 ────────────────────────────────────────────
    print("=" * 78)
    print("  [3폴드 종합]  값별 gain 부호와 합산")
    print("=" * 78)
    print("  %-8s %-6s %9s %9s %9s %9s %8s" %
          ("타겟", a.param[:6], "A/2023", "B/2022", "C/2021", "합산", "판정"))
    for tk in a.targets:
        for v in a.values:
            if v == ref:
                continue
            sub = d[(d.target == tk) & (d.value == v)]
            g = {r.fold: r.gain for r in sub.itertuples()}
            sds = sub["std"].tolist()
            tot = sum(g.values())
            same = len({np.sign(x) for x in g.values()}) == 1
            thr = 2 * float(np.mean(sds))
            ok = same and abs(tot) > thr
            vd = ("채택 검토" if ok and tot > 0 else
                  "기각(악화)" if ok and tot < 0 else
                  "부호 불일치" if not same else "미달")
            print("  %-8s %-6d %+9.4f %+9.4f %+9.4f %+9.4f %8s" %
                  (TARGETS[tk][2], v, g.get("A", 0), g.get("B", 0), g.get("C", 0), tot, vd))
    print()
    print("저장: %s" % a.out)


if __name__ == "__main__":
    main()
