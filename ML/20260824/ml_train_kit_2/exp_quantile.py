# -*- coding: utf-8 -*-
"""분위수 회귀 — 밴드를 모델이 직접 배우게 한다 (2026-09-01)

## 왜

지금 밴드는 **고정표**다.

    ref_prediction_band   (가격종류 · 품목 · 리드타임) → q10 / q50 / q90 비율

그날 상황과 무관하게 늘 같은 폭이다.

    조용한 날    실제로는 ±5% 안에 들어올 텐데도 ±40% 를 낸다
    흔들리는 날   ±40% 로도 모자란데 같은 값을 낸다

매입 파트가 "구간이 너무 넓어 쓸 수 없다" 고 한 것이 이것이다.
**넓은 게 문제가 아니라, 좁아야 할 날에도 넓은 것이 문제다.**

## 무엇을 하나

    지금    LightGBM(regression_l1) → 가운데 값 + 고정표로 ±폭
    여기    LightGBM(quantile, alpha=0.1/0.5/0.9) → 하한·가운데·상한을 직접

## ★ 판정은 WMAPE 가 아니다

목적이 다르다. 네 가지로 잰다.

    적중률     실제가 하한~상한 안에 든 비율        목표 80%
    평균 폭    (상한−하한) ÷ 예측값                지금보다 좁게
    ★ 조건부성  조용한 날 폭 vs 흔들리는 날 폭       갈라져야 한다
    버퍼 초과   실제가 예측보다 4.7% 넘게 비싼 비율   지금보다 낮게

**조건부성이 핵심이다.** 적중률만 맞추는 건 고정표도 한다.
조용한 날에 좁아지지 않으면 이 실험은 실패다.

## 쓰는 법

    python exp_quantile.py <csv> --target auc --valid-end 2023-12-31
    python exp_quantile.py <csv> --target auc --train-end 2021-12-31 --valid-end 2022-12-31

**두 폴드 다 돌리고 부호가 같을 때만 판정한다** (CLAUDE.md §5.7).

## 실험 기록 규칙

결과는 `실험결과/` 에만 남긴다. **`prediction_log` 에 넣지 않는다** —
2026-09-01 에 실험 기록이 운영 기록과 섞여 매입 파트에 틀린 수치를 보낸
사고가 있었다.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import train as T                                            # noqa: E402

ALPHA_BY_TARGET = {"auc": 0.4, "whsl": 0.8, "rtl": 1.0}
#   기본은 0.1/0.9 (10번 중 8번 목표). 그런데 실측에서 검증 적중이 63.8% 로
#   나왔다 — 학습 구간의 분위수를 너무 꽉 맞춰서 검증에서는 자꾸 벗어난다.
#   트리를 늘리면 더 나빠진다 (300→63.8% · 600→55.5% · 1200→47.7%).
#   그래서 **학습 때 더 넓게 잡아** 검증에서 80% 가 나오게 맞춘다.
QUANTILES = (0.1, 0.5, 0.9)


def build(csv, target, train_end, valid_end, alpha):
    """train.py 와 **같은 재료**로 만든다. 다르면 비교가 성립하지 않는다."""
    tgt, anc, label = T.TARGETS[target]
    df = T.load(csv)

    drop = set(T.DROP) | set(T.TARGET_DROP.get(target, set()))
    drop |= set(T.NEW_PRICE_COLS) - set(T.BASE_CANDS[target][0] if False else [])
    drop |= set(T.CLIM_NEW) | set(T.FCST_COLS) | set(T.FCST_DIAG)
    drop |= set(T.VOLPRED_ORACLE) | set(T.VOLPRED_COLS)

    #   앵커 수축 — train.py 와 같은 방식. 새 컬럼을 만들고 원본은 뺀다.
    avg7 = anc.replace("_lag1", "_avg7")
    if alpha < 1.0 and avg7 in df.columns:
        df = df.assign(_anchor_mix=(alpha * df[anc] + (1 - alpha) * df[avg7]).fillna(df[anc]))
        use_anc = "_anchor_mix"
        drop |= {anc}
    else:
        use_anc = anc

    df = df[df[tgt].notna() & df[use_anc].notna() & (df[use_anc] > 0)].copy()
    df["y"] = np.log(df[tgt] / df[use_anc])
    feats = [c for c in df.columns if c not in drop | {"y"}]
    cats = [c for c in T.CAT if c in feats]

    tr = df[df.base_dt <= pd.Timestamp(train_end)]
    va = df[(df.base_dt > pd.Timestamp(train_end))
            & (df.base_dt <= pd.Timestamp(valid_end))].copy()
    return tr, va, feats, cats, tgt, use_anc, label


def fit_quantiles(tr, va, feats, cats, seeds, n_round, quants=None):
    """분위수 셋을 각각 학습한다. 반환: {q: 검증 예측(로그비율)}"""
    out = {}
    for q in (quants or QUANTILES):
        preds = []
        for s in seeds:
            p = dict(T.PARAMS, objective="quantile", alpha=q, metric="quantile",
                     seed=s, bagging_seed=s, feature_fraction_seed=s)
            m = lgb.train(p, lgb.Dataset(tr[feats], tr["y"], categorical_feature=cats),
                          num_boost_round=n_round)
            preds.append(m.predict(va[feats]))
        out[q] = np.mean(preds, axis=0)
    return out


def fixed_band(va, target):
    """지금 쓰는 고정표를 DB 에서 읽어 같은 행에 붙인다 (대조군)."""
    sys.path.insert(0, str(HERE.parents[2] / "agent"))
    from core import db                                      # noqa: PLC0415
    with db() as c:
        rows = c.execute(
            "SELECT item_nm, lead_biz_d, ratio_q10, ratio_q90 "
            "  FROM ref_prediction_band WHERE target_kind=%s", (target,)).fetchall()
    tab = {(r[0], int(r[1])): (float(r[2]), float(r[3])) for r in rows}
    lo, hi = [], []
    for it, lt in zip(va["item_nm"].astype(str), va["lead_biz_d"].astype(int)):
        b = tab.get((it, lt))
        lo.append(b[0] if b else np.nan)
        hi.append(b[1] if b else np.nan)
    return np.array(lo), np.array(hi)


def score(name, actual, pred, lo, hi, vol_rank):
    """네 가지로 잰다. 적중률만 보면 고정표와 구분이 안 된다."""
    ok = np.isfinite(lo) & np.isfinite(hi) & np.isfinite(pred)
    a, p, l, h = actual[ok], pred[ok], lo[ok], hi[ok]
    # 하한이 상한보다 큰 행(분위수 교차)은 정렬해서 쓰고 개수를 센다
    cross = int((l > h).sum())
    l, h = np.minimum(l, h), np.maximum(l, h)
    hit = ((a >= l) & (a <= h)).mean() * 100
    width = ((h - l) / p).mean() * 100
    over = (a > p * 1.047).mean() * 100
    mape = (np.abs(a - p) / a).mean() * 100

    r = vol_rank[ok]
    calm = (h - l)[r <= 0.25] / p[r <= 0.25]
    wild = (h - l)[r >= 0.75] / p[r >= 0.75]
    return dict(name=name, n=len(a), hit=hit, width=width, over=over, mape=mape,
                calm=calm.mean() * 100 if len(calm) else np.nan,
                wild=wild.mean() * 100 if len(wild) else np.nan, cross=cross)


def by_item(va, actual, f_pred, f_lo, f_hi, q_pred, q_lo, q_hi, std_col, anc):
    """★ 품목별로 나눠 본다 (CLAUDE.md §8).

    통합값은 가격이 높은 품목이 분모를 지배한다. 그리고 밴드는 품목마다
    폭이 크게 다르다 (경락가 고정표: 양파 69% · 배추 93% · 무 111%).
    통합만 보면 한 품목이 망가진 것을 못 본다.

    **변동성 순위는 품목 안에서 매긴다.** 전체 순위로 매기면 값이 비싼
    품목이 '흔들리는 날' 쪽으로 통째로 몰려 잣대가 품목 비교가 되어버린다.
    """
    items = [i for i in ["배추", "무", "양파"] if (va.item_nm == i).any()]
    print(f"\n  ── 품목별 ── (변동성 순위는 품목 안에서)")
    print(f"  {'품목':<5}{'행수':>7}   " + f"{'적중률':>17}{'평균폭':>16}"
          f"{'조용한날':>17}{'흔들날':>16}{'조건부성비':>17}")
    print(f"  {'':<5}{'':>7}   " + "".join(f"{h:>8}" for h in
          ["고정표", "분위수", "고정표", "분위수", "고정표", "분위수",
           "고정표", "분위수", "고정표", "분위수"]))
    for it in items:
        m = (va.item_nm == it).to_numpy()
        vr = pd.Series((va[std_col].astype(float) / va[anc].astype(float))[m]
                       ).rank(pct=True).to_numpy()
        b = score("f", actual[m], f_pred[m], f_lo[m], f_hi[m], vr)
        q = score("q", actual[m], q_pred[m], q_lo[m], q_hi[m], vr)
        rb = b["wild"] / b["calm"] if b["calm"] else float("nan")
        rq = q["wild"] / q["calm"] if q["calm"] else float("nan")
        print(f"  {it:<5}{b['n']:>7,}   "
              f"{b['hit']:>7.1f}%{q['hit']:>7.1f}%"
              f"{b['width']:>7.0f}%{q['width']:>7.0f}%"
              f"{b['calm']:>7.0f}%{q['calm']:>7.0f}%"
              f"{b['wild']:>7.0f}%{q['wild']:>7.0f}%"
              f"{rb:>8.2f}{rq:>8.2f}")
    print("  ※ 적중률 목표 80% · 조건부성 비는 클수록 상황을 읽는 것입니다.")


def main() -> int:
    ap = argparse.ArgumentParser(description="분위수 회귀로 밴드를 직접 배우게 한다")
    ap.add_argument("csv")
    ap.add_argument("--target", default="auc", choices=["auc", "whsl", "rtl"])
    ap.add_argument("--train-start", default="2017-01-01")
    ap.add_argument("--train-end", default="2022-12-31")
    ap.add_argument("--valid-end", default="2023-12-31")
    ap.add_argument("--seeds", nargs="+", type=int, default=[42, 43, 44, 45, 46])
    ap.add_argument("--rounds", type=int, default=300)
    ap.add_argument("--gate-lt", type=int, default=3)
    ap.add_argument("--q", type=float, default=0.1,
                    help="학습에 쓸 하한 분위수. 상한은 1-q. 기본 0.1 "
                         "(넓게 잡으려면 0.03 처럼 작게)")
    a = ap.parse_args()

    alpha = ALPHA_BY_TARGET[a.target]
    tr, va, feats, cats, tgt, anc, label = build(
        a.csv, a.target, a.train_end, a.valid_end, alpha)
    tr = tr[tr.base_dt >= pd.Timestamp(a.train_start)]

    print("=" * 70)
    print(f"[분위수 회귀] {label} · 앵커 α={alpha}")
    print(f"  학습 {len(tr):,}행 ({tr.base_dt.min().date()}~{tr.base_dt.max().date()})")
    print(f"  검증 {len(va):,}행 ({va.base_dt.min().date()}~{va.base_dt.max().date()})")
    print(f"  feature {len(feats)}개 · 시드 {len(a.seeds)}개 · 트리 {a.rounds}그루")
    print("=" * 70)

    #   게이트 구간(LT<3)은 모델을 안 쓴다. 비교에서도 뺀다 —
    #   섞으면 두 방식이 똑같은 값을 내는 행이 21% 들어가 차이가 묻힌다.
    va = va[va.lead_biz_d >= a.gate_lt].copy()
    print(f"  게이트 제외 후 검증 {len(va):,}행 (LT >= {a.gate_lt})\n")

    QS = (a.q, 0.5, 1 - a.q)
    print(f"  학습 분위수 {QS[0]:.2f} / 0.50 / {QS[2]:.2f}")

    qs = fit_quantiles(tr, va, feats, cats, a.seeds, a.rounds, QS)
    ancv = va[anc].to_numpy(float)
    actual = va[tgt].to_numpy(float)

    #   로그비율 → 원래 값. 앵커를 곱해 되돌린다.
    q_pred = ancv * np.exp(qs[0.5])
    q_lo = ancv * np.exp(qs[QS[0]])
    q_hi = ancv * np.exp(qs[QS[2]])

    #   대조군: 지금 방식 = L1 로 낸 가운데 값 + 고정표 비율
    base_preds = []
    for s in a.seeds:
        p = dict(T.PARAMS, seed=s, bagging_seed=s, feature_fraction_seed=s)
        m = lgb.train(p, lgb.Dataset(tr[feats], tr["y"], categorical_feature=cats),
                      num_boost_round=a.rounds)
        base_preds.append(m.predict(va[feats]))
    f_pred = ancv * np.exp(np.mean(base_preds, axis=0))
    r10, r90 = fixed_band(va, a.target)
    f_lo, f_hi = f_pred * r10, f_pred * r90

    #   "조용한 날/흔들리는 날" 은 그날의 최근 변동으로 가른다.
    #   ★ 예측이 아니라 **입력**으로 가른다 — 두 방식에 같은 잣대여야 한다.
    std_col = anc.replace("_anchor_mix", "").replace("_lag1", "_std7")
    if std_col not in va.columns:
        std_col = [c for c in va.columns if c.endswith("_std7")][0]
    vol = (va[std_col].astype(float) / va[anc].astype(float)).to_numpy()
    vol_rank = pd.Series(vol).rank(pct=True).to_numpy()

    rows = [score("지금 (고정표)", actual, f_pred, f_lo, f_hi, vol_rank),
            score("분위수 회귀", actual, q_pred, q_lo, q_hi, vol_rank)]

    print(f"  {'방식':<14}{'적중률':>8}{'평균폭':>8}{'초과':>7}{'오차':>7}"
          f"{'조용한날':>9}{'흔들날':>8}{'교차':>6}")
    for r in rows:
        print(f"  {r['name']:<14}{r['hit']:>7.1f}%{r['width']:>7.0f}%{r['over']:>6.0f}%"
              f"{r['mape']:>6.1f}%{r['calm']:>8.0f}%{r['wild']:>7.0f}%{r['cross']:>6}")

    b, q = rows[0], rows[1]
    print("\n  ── 판정 ──")
    print(f"  적중률   {b['hit']:.1f}% → {q['hit']:.1f}%   (목표 80%)")
    print(f"  평균폭   {b['width']:.0f}% → {q['width']:.0f}%")
    print(f"  버퍼초과 {b['over']:.0f}% → {q['over']:.0f}%")
    print(f"\n  ★ 조건부성 (조용한 날 대비 흔들리는 날의 폭)")
    print(f"     고정표    {b['calm']:.0f}% → {b['wild']:.0f}%  "
          f"(비 {b['wild']/b['calm']:.2f})")
    print(f"     분위수    {q['calm']:.0f}% → {q['wild']:.0f}%  "
          f"(비 {q['wild']/q['calm']:.2f})")
    print("     ※ 이 비가 1에 가까우면 상황을 못 읽는 것입니다.")

    by_item(va, actual, f_pred, f_lo, f_hi, q_pred, q_lo, q_hi, std_col, anc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
