# -*- coding: utf-8 -*-
"""리드타임 구간 분리 실험 (2026-08-28 · 정확도 4순위).

## 무엇을 묻는가

지금은 **LT1 이든 LT18 이든 한 모델**이 맞힌다. 리드타임을 feature 로 넣어
모델이 알아서 구분하게 두는 방식이다.

그런데 오차의 72% 가 LT7 이후에 있다 (검증 2023 · 경락가 α=0.4):

    LT 1-2   오차의  8.3%
    LT 3-6   오차의 20.1%
    LT 7-12  오차의 34.5%
    LT13-18  오차의 37.1%

**가까운 날과 먼 날은 다른 문제일 수 있다.** 가까운 날은 어제 가격이 거의
답이고, 먼 날은 계절·작황·수요가 지배한다. 한 모델이 절충하면 양쪽 다
어중간해진다.

## 어떻게 가르나

    가까움  LT 3~8
    멂      LT 9~18
    (LT 1~2 는 게이트라 어느 쪽도 학습하지 않는다)

경계를 8/9 로 둔 이유: 오차 비중이 LT7 부터 크게 늘고, 두 구간의 학습 행
수가 비슷해진다(각 6·10 리드타임). 경계 자체도 실험 대상이지만 먼저
"가르는 게 도움이 되나" 부터 본다.

## 판정

폴드 두 개에서 같은 방향일 때만 채택한다 (CLAUDE.md 5.7).
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
CUT = 9          # LT >= CUT 이면 '멂'


def prep(csv, target, anchor, alpha, tgt_key):
    drop = set(BASE_DROP) | set(TARGET_DROP[tgt_key]) | set(_train.NEW_PRICE_COLS)
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


def run(tr, va, feats, seeds):
    cats = [c for c in CAT if c in feats]
    preds = []
    for s in seeds:
        p = dict(PARAMS, seed=s, bagging_seed=s, feature_fraction_seed=s)
        m = lgb.train(p, lgb.Dataset(tr[feats], tr.y, categorical_feature=cats),
                      num_boost_round=3000,
                      valid_sets=[lgb.Dataset(va[feats], va.y)],
                      callbacks=[lgb.early_stopping(200, verbose=False)])
        preds.append(va["_anc"].values * np.exp(m.predict(va[feats])))
    return np.mean(preds, axis=0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--target", choices=list(TARGETS), default="auc")
    ap.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44])
    ap.add_argument("--gate-lt", type=int, default=3)
    ap.add_argument("--cut", type=int, default=CUT)
    a = ap.parse_args()

    target, anchor, label = TARGETS[a.target]
    alpha = ALPHA[a.target]
    print(f"[타겟] {label} · 앵커 α={alpha} · 게이트 LT<{a.gate_lt} · 시드 {len(a.seeds)}개")
    print(f"[분리 경계] LT {a.gate_lt}~{a.cut-1} (가까움) / LT {a.cut}~18 (멂)")
    print(f"[모델] LightGBM {lgb.__version__} · 시드 {list(a.seeds)} 평균")
    print("[하이퍼파라미터] " + " · ".join(f"{k}={PARAMS[k]}" for k in sorted(PARAMS)))

    df, feats = prep(a.csv, target, anchor, alpha, a.target)
    for tag, tr_end, va_end in FOLDS:
        tr = df[df.base_dt <= tr_end]
        va = df[(df.base_dt > tr_end) & (df.base_dt <= va_end)].copy()
        print(f"\n{'='*72}\n폴드 {tag} (검증 ~{va_end}) · 학습 {len(tr):,}행 · 검증 {len(va):,}행")

        va["p_all"] = run(tr, va, feats, a.seeds)                 # ① 합친 모델
        va["p_sp"] = np.nan                                      # ② 구간별 모델
        for lo, hi, nm in [(a.gate_lt, a.cut - 1, "가까움"), (a.cut, 18, "멂")]:
            mtr = tr[(tr.lead_biz_d >= lo) & (tr.lead_biz_d <= hi)]
            mva = va[(va.lead_biz_d >= lo) & (va.lead_biz_d <= hi)]
            if len(mtr) == 0 or len(mva) == 0:
                continue
            va.loc[mva.index, "p_sp"] = run(mtr, mva, feats, a.seeds)

        # 게이트 구간은 양쪽 다 앵커. 비교에서 뺀다
        ev = va[va.lead_biz_d >= a.gate_lt].copy()
        print(f"\n  {'구간':<10}{'합친 모델':>11}{'구간별 모델':>13}{'차이':>10}{'학습행':>10}")
        for lo, hi, nm in [(a.gate_lt, a.cut - 1, "가까움"), (a.cut, 18, "멂")]:
            m = (ev.lead_biz_d >= lo) & (ev.lead_biz_d <= hi)
            if not m.any():
                continue
            w1 = wmape(ev[target][m], ev.p_all[m])
            w2 = wmape(ev[target][m], ev.p_sp[m])
            n_tr = int(((tr.lead_biz_d >= lo) & (tr.lead_biz_d <= hi)).sum())
            mark = "구간별 우세" if w2 < w1 else ("합친 쪽 우세" if w2 > w1 else "동일")
            print(f"  LT{lo}-{hi:<7}{w1*100:>10.2f}%{w2*100:>12.2f}%"
                  f"{(w1-w2)*100:>+9.2f}%p{n_tr:>10,}   {mark}")
        w1 = wmape(ev[target], ev.p_all)
        w2 = wmape(ev[target], ev.p_sp)
        print(f"  {'전체':<10}{w1*100:>10.2f}%{w2*100:>12.2f}%{(w1-w2)*100:>+9.2f}%p")


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
