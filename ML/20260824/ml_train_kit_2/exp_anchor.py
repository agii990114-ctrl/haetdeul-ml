# -*- coding: utf-8 -*-
"""앵커 재검토 실험 (백로그 M-15) — 경락가

    python exp_anchor.py <csv> --alpha 1.0 0.8 0.6 0.5
    python exp_anchor.py <csv> --alpha 0.6 --items 배추 무

## 무엇을 묻는가

지금 경락가 앵커는 `auc_prc_lag1`(어제값) 단독이다. 앵커 변환을 쓰므로
**앵커는 정의상 baseline** 이다 — 모델이 0을 내면 앵커가 답이 된다. 그런데
"그 앵커가 최선인가" 는 한 번도 묻지 않았다.

조용한 날에는 어제값이 거의 정답이라 모델이 개입할수록 손해다. 실측(2026 운영):

    변동 하위 40% 구간   모델이 앵커보다 나쁨 (1분위 −363% · 4분위 −5%)
    변동 상위 20% 구간   모델이 앵커를 +27% 이김 · 여기에 전체 오차의 58%

수축 앵커 `α·어제값 + (1−α)·7일평균` 은 조용한 날의 노이즈를 줄인다.
α=1.0 이 현행이다.

## ★ train.py 의 baseline 이 타겟과 어긋나 있다 (2026-08-27 발견)

`train.py:437` 의 baseline 후보가 **타겟과 무관하게 중도매가 컬럼으로 고정**돼
있다 (`whsl_prc_avg7` · `whsl_prc_prev_yr`). 경락가·소매가를 평가할 때 다른
가격 계열을 갖다 대는 것이라, **"최강 baseline = 어제 가격" 이 구조상 자동으로
참이 된다.** 경락가 무의 "최근7일 평균 0.5057" 이 그 증상이었다.

이 스크립트는 **경락가 계열로만** baseline 을 잡는다:
`auc_prc_lag1` · `auc_prc_lag3` · `auc_prc_avg7`.
(경락가에는 작년 동시기 컬럼이 없다 — M-15 에서 만들 후보다.)

나머지 조리법은 train.py 와 동일하게 유지한다. 여기가 어긋나면 비교가 무의미해진다.
"""
import argparse

import lightgbm as lgb
import numpy as np
import pandas as pd

import sys

# 실험 기록은 train.py 것을 그대로 쓴다 (2026-08-28)
from train import _Tee, _open_log

TARGET = "target_auc_prc"
LAG1, AVG7, LAG3 = "auc_prc_lag1", "auc_prc_avg7", "auc_prc_lag3"
AVG14, PREV = "auc_prc_avg14", "auc_prc_prev_yr"
ANCHOR = "_anchor"

# v5.3 에서 avg14·prev_yr 이 생겨 baseline 후보가 넷이 됐다.
# 실측(검증 2023): 14일평균이 배추·양파에서 어제값보다 강하다.
BASE_COLS = (("어제값", LAG1), ("7일평균", AVG7), ("14일평균", AVG14), ("작년동기", PREV))

DROP = {"id", "created_at", "base_dt", "target_dt", "arr_qty_asof_date",
        "arr_top1_region", "prod_area_fcst_temp_avg10",
        "target_auc_prc", "target_whsl_prc", "target_rtl_prc",
        "crop_area_yoy_rt",
        "m2_growth_rt", "epu_idx", "ppi_idx",      # 경제 — ablation 기각
        "school_open_ratio",                        # 학사일정 — 3폴드 기각
        ANCHOR}
CAT = ["item_nm", "target_dow", "prod_area_stn_nm"]

PARAMS = dict(objective="regression_l1", metric="mae",
              learning_rate=0.03, num_leaves=31,
              feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1,
              min_data_in_leaf=60, lambda_l2=1.0, verbosity=-1)

FOLDS = (("A", "2022-12-31", "2023-12-31"),
         ("B", "2021-12-31", "2022-12-31"))


def wmape(t, p):
    t, p = np.asarray(t, float), np.asarray(p, float)
    m = ~(np.isnan(t) | np.isnan(p))
    return np.abs(t[m] - p[m]).sum() / np.abs(t[m]).sum()


def run(df, alpha, train_end, valid_end, seeds, gate_lt):
    d = df.copy()
    d[ANCHOR] = alpha * d[LAG1] + (1 - alpha) * d[AVG7]
    d = d[(d[TARGET] > 0) & (d[ANCHOR] > 0)].copy()
    d = d.sort_values(["base_dt", "item_nm", "lead_biz_d"]).reset_index(drop=True)
    d["y_ratio"] = np.log(d[TARGET] / d[ANCHOR])

    feats = [c for c in d.columns if c not in DROP | {"y_ratio"}]
    for c in CAT:
        if c in d.columns:
            d[c] = d[c].astype("category")

    tr = d[(d.base_dt >= "2017-01-01") & (d.base_dt <= train_end)]
    va = d[(d.base_dt > train_end) & (d.base_dt <= valid_end)]

    preds = []
    for s in seeds:
        p = dict(PARAMS, seed=s, bagging_seed=s, feature_fraction_seed=s)
        m = lgb.train(p, lgb.Dataset(tr[feats], tr.y_ratio), num_boost_round=3000,
                      valid_sets=[lgb.Dataset(va[feats], va.y_ratio)],
                      callbacks=[lgb.early_stopping(200, verbose=False)])
        out = m.predict(va[feats], num_iteration=m.best_iteration)
        preds.append(va[ANCHOR].values * np.exp(out))

    ens = np.mean(preds, axis=0)
    # 리드타임 게이트 — 운영 기준(--gate-lt 3). LT<k 는 모델 대신 앵커를 쓴다
    if gate_lt:
        g = va.lead_biz_d.values < gate_lt
        ens = np.where(g, va[ANCHOR].values, ens)
    return va, ens, [wmape(va[TARGET], p) for p in preds]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--alpha", type=float, nargs="+", default=[1.0, 0.8, 0.6, 0.5])
    ap.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44, 45, 46])
    ap.add_argument("--items", nargs="+", default=["배추", "양파", "무"])
    ap.add_argument("--gate-lt", type=int, default=3)
    a = ap.parse_args()

    df = pd.read_csv(a.csv, encoding="utf-8", low_memory=False)
    df["base_dt"] = pd.to_datetime(df["base_dt"])
    df = df[df.item_nm.isin(a.items)].copy()
    print(f"[품목] {a.items} · 게이트 LT<{a.gate_lt} · 시드 {len(a.seeds)}개")

    # 무엇으로 어떻게 돌렸나 (2026-08-28). train.py 와 같은 형식.
    print("\n[모델]")
    print(f"  종류        LightGBM {lgb.__version__} (GBDT)")
    print(f"  앙상블      시드 {len(a.seeds)}개 {list(a.seeds)} · 예측 평균")
    print(f"  학습 목표   앵커 대비 로그비율  ({TARGET} / 수축앵커)")
    print(f"  수축 앵커   α×{LAG1} + (1−α)×{AVG7}")
    print(f"  α 후보      {a.alpha}   (1.0 = 현행 · 어제값 단독)")
    print("  트리 수     조기 종료 (상한 5,000 · 200회 개선 없으면 중단)")
    print(f"  범주형      {CAT}")
    print(f"  게이트      리드타임 < {a.gate_lt} 는 모델 대신 앵커 사용")
    print("\n[하이퍼파라미터]")
    for _k in sorted(PARAMS):
        print(f"  {_k:<20} {PARAMS[_k]}")

    # baseline 은 앵커와 무관하게 고정 — α 를 바꿔도 같은 잣대로 잰다
    for tag, tr_end, va_end in FOLDS:
        _, _, _ = None, None, None
        base_rows = {}
        results = {}
        for alpha in a.alpha:
            va, ens, per_seed = run(df, alpha, tr_end, va_end, a.seeds, a.gate_lt)
            results[alpha] = (va, ens, per_seed)
            if not base_rows:
                for n, c in BASE_COLS:
                    if c in va.columns:
                        base_rows[n] = c

        va0 = results[a.alpha[0]][0]
        print(f"\n{'='*74}\n폴드 {tag} (검증 ~{va_end}) · 검증 {len(va0):,}행")
        print(f"  baseline (경락가 계열): " + " · ".join(
            f"{n} {wmape(va0[TARGET], va0[c]):.4f}" for n, c in base_rows.items()))
        bn, bc = min(base_rows.items(), key=lambda kv: wmape(va0[TARGET], va0[kv[1]]))
        bw_all = wmape(va0[TARGET], va0[bc])
        print(f"  최강 baseline: {bn} ({bw_all:.4f})")

        print(f"\n  {'α':<6}{'WMAPE':>9}{'시드편차':>10}{'개선율':>9}   품목별 개선율")
        for alpha in a.alpha:
            va, ens, per_seed = results[alpha]
            mw = wmape(va[TARGET], ens)
            cells = []
            for it in a.items:
                m_ = va.item_nm.astype(str).values == it
                if not m_.any():
                    continue
                iw = wmape(va[TARGET][m_], ens[m_])
                ib = min(wmape(va[TARGET][m_], va[c].values[m_]) for c in base_rows.values())
                cells.append(f"{it} {100*(ib-iw)/ib:+.1f}%")
            mark = " ←현행" if alpha == 1.0 else ""
            print(f"  {alpha:<6.2f}{mw:>9.4f}{np.std(per_seed):>10.4f}"
                  f"{100*(bw_all-mw)/bw_all:>8.1f}%   " + " · ".join(cells) + mark)

        # ── 실제 가격 대비 오차 ★ (2026-08-28 추가) ────────────
        #   WMAPE 만으로는 "얼마나 틀리는지" 가 안 잡힌다. 매입 파트가
        #   임계값을 잡을 때 필요한 건 원 단위 오차다.
        print(f"\n  [실제 가격 대비 오차 · 품목별]")
        print(f"  {'α':<6}{'품목':<6}{'평균 실제가':>12}{'평균오차':>11}"
              f"{'오차율':>9}{'10건중 1건은':>14}")
        for alpha in a.alpha:
            va, ens, _ = results[alpha]
            for it in a.items:
                m_ = va.item_nm.astype(str).values == it
                if not m_.any():
                    continue
                act = np.asarray(va[TARGET].values[m_], float)
                prd = np.asarray(ens[m_], float)
                ok = ~(np.isnan(act) | np.isnan(prd))
                act, prd = act[ok], prd[ok]
                if len(act) == 0:
                    continue
                err = np.abs(prd - act)
                print(f"  {alpha:<6.2f}{it:<6}{act.mean():11,.0f}원"
                      f"{err.mean():10,.0f}원{err.mean()/act.mean()*100:8.1f}%"
                      f"{np.quantile(err / act, 0.9)*100:12.0f}% 이상")
        print("  ※ '10건중 1건은' 은 오차율 상위 10% 지점")


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
            _nl = chr(10)
            try:
                import datetime as _dt
                _handle.write(_nl + "=" * 70 + _nl)
                _handle.write("종료 시각  "
                              + _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + _nl)
                _handle.close()
            except Exception:                                # noqa: BLE001
                pass
            print(_nl + "[기록] %s" % _path)
