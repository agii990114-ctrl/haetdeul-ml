# -*- coding: utf-8 -*-
"""무비용 feature 실험 (2026-08-28 · 정확도 5순위).

## 무엇을 묻는가

이미 DB 에 있는데 안 쓰고 있던 정보 셋을 넣어 본다. 새 수집이 필요 없어
"무비용" 이다.

  ① 등급 스프레드   같은 날 상(12) ÷ 특(11) 가격비.
                   등급 격차가 벌어지면 시장이 상품성에 민감하다는 신호.
                   ※ 양파는 상 등급이 463일뿐이라 사실상 배추·무 전용.
  ② 타 시장 경락가  서울 제외 전국 도매시장의 같은 품목 가격.
                   지역 간 선행성이 있으면 서울 가격을 미리 알려준다.
  ③ 휴장 일수      기준일과 대상일 사이에 경매가 안 열린 날 수.
                   지금은 일요일 1일과 추석 5일이 모델에게 같은 값이다.

## 미래 정보를 안 쓰도록

①②는 **기준일 이전 최신값**으로 붙인다 (merge_asof · allow_exact_matches=False).
당일 값을 쓰면 "그날 아직 모르는 값" 을 쓰는 것이라 성적이 거짓으로 좋아진다.
③은 달력이라 미래도 안전하게 셀 수 있다.

## 방법

한 번에 다 넣지 않는다. **하나씩 넣어 각각의 기여를 본다.**
같이 넣으면 어느 것이 효과를 냈는지 알 수 없고 서로 상쇄될 수도 있다.

## 판정

폴드 두 개에서 부호가 같고, 이득이 시드편차×2 를 넘을 때만 채택 (CLAUDE.md 5.7).
"""
import argparse
import io
import sys

import lightgbm as lgb
import numpy as np
import pandas as pd
import psycopg

from train import (TARGETS, TARGET_DROP, CAT, PARAMS, DROP as BASE_DROP,
                   load, wmape, _Tee, _open_log)
import train as _train

ALPHA = {"auc": 0.4, "whsl": 0.8, "rtl": 1.0}
FOLDS = (("A", "2022-12-31", "2023-12-31"), ("B", "2021-12-31", "2022-12-31"))
ITEMS = ["배추", "무", "양파"]
SPEC = ("AND ((item_name='배추' AND package_name IN ('그물망','파렛트') AND unit_weight_kg=10) "
        " OR (item_name='무' AND package_name IN ('상자','파렛트') AND unit_weight_kg=20) "
        " OR (item_name='양파' AND package_name IN ('그물망','파렛트') AND unit_weight_kg=15))")

TGT = None


def db():
    url = [l.split("=", 1)[1].strip()
           for l in io.open("../../../.env", encoding="utf-8", errors="ignore")
           if l.startswith("DATABASE_URL")][0]
    return psycopg.connect(url)


def fetch_extra():
    out = {}
    with db() as c:
        q1 = ("WITH g AS (SELECT auction_date dt, item_name it, grade_code gc, "
              "SUM(trade_amount_krw)/SUM(trade_volume_kg) p "
              "FROM auction_prices_daily WHERE wholesale_market_code='110001' "
              "AND trade_volume_kg>0 AND grade_code IN ('11','12') " + SPEC +
              " GROUP BY 1,2,3) "
              "SELECT a.dt, a.it, (b.p/NULLIF(a.p,0))::float FROM g a "
              "JOIN g b ON b.dt=a.dt AND b.it=a.it AND b.gc='12' WHERE a.gc='11'")
        out["grade_spread"] = pd.DataFrame(
            c.execute(q1).fetchall(), columns=["dt", "_k", "grade_spread"])

        q2 = ("SELECT auction_date, item_name, "
              "(SUM(trade_amount_krw)/NULLIF(SUM(trade_volume_kg),0))::float "
              "FROM auction_prices_daily WHERE wholesale_market_code <> '110001' "
              "AND grade_code='11' AND trade_volume_kg>0 "
              "AND item_name IN ('배추','무','양파') GROUP BY 1,2")
        out["other_mkt"] = pd.DataFrame(
            c.execute(q2).fetchall(), columns=["dt", "_k", "other_mkt_prc"])
    return out


def build(csv, tgt_key):
    target, anchor, _ = TARGETS[tgt_key]
    alpha = ALPHA[tgt_key]
    drop = set(BASE_DROP) | set(TARGET_DROP[tgt_key]) | set(_train.NEW_PRICE_COLS)
    df = load(csv, target=target, anchor=anchor)
    df = df[df.item_nm.astype(str).isin(ITEMS)].copy()
    df = df[df.base_dt >= "2017-01-01"]
    if alpha < 1.0:
        df["_anc"] = (alpha * df[anchor]
                      + (1 - alpha) * df[anchor.replace("_lag1", "_avg7")])
        drop |= {anchor}
    else:
        df["_anc"] = df[anchor]
    df = df[(df[target] > 0) & (df["_anc"] > 0)].copy()
    df["y"] = np.log(df[target] / df["_anc"])
    drop |= {"_anc", "y"}

    df["_k"] = df.item_nm.astype(str)
    df = df.sort_values("base_dt").reset_index(drop=True)
    df["base_dt"] = df["base_dt"].astype("datetime64[ns]")
    ex = fetch_extra()
    added = {}
    for label, key, col in (("등급스프레드", "grade_spread", "grade_spread"),
                            ("타시장경락가", "other_mkt", "other_mkt_prc")):
        t = ex[key]
        if t is None or t.empty:
            continue
        t = t.copy()
        # DB 의 date 는 초 단위, 학습표는 마이크로초 단위로 읽혀 merge_asof 가
        # dtype 불일치로 거부한다. 둘 다 나노초로 맞춘다.
        t["dt"] = pd.to_datetime(t["dt"]).astype("datetime64[ns]")
        t["_k"] = t["_k"].astype(str)
        t = t.sort_values("dt")
        m = pd.merge_asof(df, t, left_on="base_dt", right_on="dt", by="_k",
                          direction="backward", allow_exact_matches=False)
        df[col] = m[col].values
        added[label] = col

    with db() as c:
        cal = pd.DataFrame(
            c.execute("SELECT dt, is_open FROM ref_calendar ORDER BY dt").fetchall(),
            columns=["dt", "is_open"])
    cal["dt"] = pd.to_datetime(cal["dt"])
    cal["cum"] = (~cal.is_open.astype(bool)).cumsum()
    cm = dict(zip(cal.dt, cal.cum))
    tdt = pd.to_datetime(df.target_dt)
    df["closed_days"] = [
        (cm[t] - cm[b]) if (t in cm and b in cm) else np.nan
        for b, t in zip(df.base_dt, tdt)]
    added["휴장일수"] = "closed_days"

    feats0 = [c for c in df.columns
              if c not in drop | {"_k", "dt"} | set(added.values())]
    return df, feats0, added, target


def run(tr, va, feats, seeds, gate):
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
    ws = [wmape(va[TGT], p) for p in preds]
    return np.where(g, va["_anc"].values, ens), ws


def main():
    global TGT
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--target", choices=list(TARGETS), default="auc")
    ap.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44])
    ap.add_argument("--gate-lt", type=int, default=3)
    a = ap.parse_args()

    df, feats0, added, TGT = build(a.csv, a.target)
    print("[타겟] %s · 앵커 α=%s · 게이트 LT<%d · 시드 %d개"
          % (TARGETS[a.target][2], ALPHA[a.target], a.gate_lt, len(a.seeds)))
    print("[모델] LightGBM %s · 시드 %s 평균" % (lgb.__version__, list(a.seeds)))
    print("[하이퍼파라미터] "
          + " · ".join("%s=%s" % (k, PARAMS[k]) for k in sorted(PARAMS)))
    print("[기준 feature] %d개" % len(feats0))
    for n, c_ in added.items():
        print("  후보 %-12s %-16s 결측 %5.1f%%"
              % (n, c_, df[c_].isna().mean() * 100))

    for tag, tr_end, va_end in FOLDS:
        tr = df[df.base_dt <= tr_end]
        va = df[(df.base_dt > tr_end) & (df.base_dt <= va_end)].copy()
        print("\n" + "=" * 72)
        print("폴드 %s (검증 ~%s) · 학습 %s · 검증 %s"
              % (tag, va_end, format(len(tr), ","), format(len(va), ",")))
        base, ws = run(tr, va, feats0, a.seeds, a.gate_lt)
        b = wmape(va[TGT], base)
        sd = float(np.std(ws, ddof=1)) if len(ws) > 1 else 0.0
        print("  기준(현행)  %.2f%%   시드편차 %.4f" % (b * 100, sd))
        print("\n  %-14s%9s%10s   판정" % ("추가 feature", "오차율", "차이"))
        for n, c_ in added.items():
            e, _ = run(tr, va, feats0 + [c_], a.seeds, a.gate_lt)
            w = wmape(va[TGT], e)
            d = b - w
            mark = ("O 유의" if d > 2 * sd
                    else ("X 악화" if d < -2 * sd else "△ 판정불가"))
            print("  %-14s%8.2f%%%+9.2f%%p   %s" % (n, w * 100, d * 100, mark))


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
                _handle.write("종료 시각  "
                              + _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                              + chr(10))
                _handle.close()
            except Exception:                                # noqa: BLE001
                pass
            print(chr(10) + "[기록] %s" % _path)
