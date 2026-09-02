# -*- coding: utf-8 -*-
"""품목별 모델 분리 실험 (2026-08-28 · 정확도 3순위).

## 무엇을 묻는가

지금은 배추·무·양파를 **한 모델**이 맞힌다. `item_nm` 을 범주형 feature 로
넣어 모델이 알아서 구분하게 두는 방식이다.

그런데 오차가 두 배 차이난다 (검증 2023 · α=0.4):

    양파 11.2%   배추 21.6%   무 19.8%

가격 움직임의 성격이 다른데 한 모델이 절충하고 있을 수 있다.
자기상관도 다르다 — 양파 0.987 · 배추 0.927.

## 어느 쪽이 이길지 미리 알 수 없다

  분리하면 좋은 이유   품목마다 다른 규칙을 각자 배운다
  합치면 좋은 이유     학습 행이 3배. 셋이 공유하는 패턴(계절·명절)을 함께 배운다

**표본이 작아서(기준일 1,473개) 분리하면 과적합이 늘 수 있다.** 재봐야 안다.

## 판정

폴드 두 개에서 **같은 방향**일 때만 채택한다 (CLAUDE.md 5.7).
품목별로 결과가 갈리면 그 품목만 분리하는 것도 답이 될 수 있다.
"""
import argparse

import lightgbm as lgb
import numpy as np

import sys

from train import (TARGETS, TARGET_DROP, CAT, PARAMS, DROP as BASE_DROP,
                   load, wmape, _Tee, _open_log)
import train as _train

ALPHA = {"auc": 0.4, "whsl": 0.8, "rtl": 1.0}
FOLDS = (("A", "2022-12-31", "2023-12-31"), ("B", "2021-12-31", "2022-12-31"))
ITEMS = ["배추", "무", "양파"]


def prep(csv, target, anchor, alpha):
    drop = set(BASE_DROP) | set(TARGET_DROP[ARGS.target]) | set(_train.NEW_PRICE_COLS)
    df = load(csv, target=target, anchor=anchor)
    df = df[df.item_nm.astype(str).isin(ITEMS)].copy()
    df = df[df.base_dt >= "2017-01-01"]
    if alpha < 1.0:
        avg7 = anchor.replace("_lag1", "_avg7")
        df["_anc"] = alpha * df[anchor] + (1 - alpha) * df[avg7]
        drop |= {anchor}
    else:
        df["_anc"] = df[anchor]
    df = df[(df[target] > 0) & (df["_anc"] > 0)].copy()
    df["y"] = np.log(df[target] / df["_anc"])
    drop |= {"_anc", "y"}
    return df, [c for c in df.columns if c not in drop]


def run(tr, va, feats, target, seeds, gate):
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
    ens = np.where(g, va["_anc"].values, ens)
    return ens


def main():
    global ARGS
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--target", choices=list(TARGETS), default="auc")
    ap.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44, 45, 46])
    ap.add_argument("--gate-lt", type=int, default=3)
    ARGS = a = ap.parse_args()

    target, anchor, label = TARGETS[a.target]
    alpha = ALPHA[a.target]
    print(f"[타겟] {label} · 앵커 α={alpha} · 게이트 LT<{a.gate_lt} · 시드 {len(a.seeds)}개")
    print(f"[모델] LightGBM {lgb.__version__} · 시드 {list(a.seeds)} 평균")
    print("[하이퍼파라미터] " + " · ".join(f"{k}={PARAMS[k]}" for k in sorted(PARAMS)))

    df, feats = prep(a.csv, target, anchor, alpha)
    for tag, tr_end, va_end in FOLDS:
        tr = df[df.base_dt <= tr_end]
        va = df[(df.base_dt > tr_end) & (df.base_dt <= va_end)].copy()
        print(f"\n{'='*72}\n폴드 {tag} (검증 ~{va_end}) · 학습 {len(tr):,}행 · 검증 {len(va):,}행")

        # ① 합친 모델 (현행)
        va["p_all"] = run(tr, va, feats, target, a.seeds, a.gate_lt)

        # ② 품목별 모델
        va["p_own"] = np.nan
        f_own = [c for c in feats if c != "item_nm"]   # 한 품목뿐이면 무의미
        for it in ITEMS:
            mtr = tr[tr.item_nm.astype(str) == it]
            mva = va[va.item_nm.astype(str) == it]
            if len(mtr) == 0 or len(mva) == 0:
                continue
            va.loc[mva.index, "p_own"] = run(mtr, mva, f_own, target, a.seeds, a.gate_lt)

        print(f"\n  {'품목':<5}{'합친 모델':>11}{'품목별 모델':>13}{'차이':>10}{'학습행':>10}")
        for it in ITEMS:
            m = va.item_nm.astype(str) == it
            if not m.any():
                continue
            w_all = wmape(va[target][m], va.p_all[m])
            w_own = wmape(va[target][m], va.p_own[m])
            n_tr = int((tr.item_nm.astype(str) == it).sum())
            mark = "품목별 우세" if w_own < w_all else ("합친 쪽 우세" if w_own > w_all else "동일")
            print(f"  {it:<5}{w_all*100:>10.2f}%{w_own*100:>12.2f}%"
                  f"{(w_all-w_own)*100:>+9.2f}%p{n_tr:>10,}   {mark}")
        w_all = wmape(va[target], va.p_all)
        w_own = wmape(va[target], va.p_own)
        print(f"  {'전체':<5}{w_all*100:>10.2f}%{w_own*100:>12.2f}%{(w_all-w_own)*100:>+9.2f}%p")


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
                _handle.write("종료 시각  " + _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + chr(10))
                _handle.close()
            except Exception:
                pass
            print(chr(10) + "[기록] %s" % _path)
