# -*- coding: utf-8 -*-
"""시퀀스 신경망(TFT · LSTM · GRU)을 LightGBM 과 같은 자리에서 잰다 (2026-09-10).

## 왜 하나

MLP(2026-09-01)는 LightGBM 이 받는 표 한 줄을 그대로 받아 **단순 평균에도
졌다.** 그런데 그건 «TFT 도 진다» 를 증명하지 않았다. TFT·LSTM·GRU 는

    과거 흐름을 순서대로 읽고
    미리 아는 미래(요일 · 명절까지 며칠)를 따로 받고
    품목처럼 안 변하는 것을 또 따로 받는다

MLP 는 이걸 한 줄로 뭉쳐 받았다. 이번엔 **그 모델들이 원래 쓰는 모양으로** 준다.

## 똑같이 맞춘 것 — 다르면 비교가 아니다

    평가 행     학습표의 (품목, 기준일, 리드) 그대로 · 3품목
    폴드       A 학습~2022 검증 2023 · B 학습~2021 검증 2022 · C 학습~2020 검증 2021
               ★ 테스트 구간(2024~)은 안 연다
    학습 시작   2017-01-01 (운영과 같다)
    지표       가격 WMAPE — 모두 «원/kg» 로 되돌린 값끼리
    기준       LightGBM 운영 설정 (트리 76 · α 0.4 · 운영 파라미터)
    시드       모든 모델이 같은 셋
    주 비교    리드 3 이상 (지금까지 모든 비교가 이 자리였다). 리드 0~2 는 따로 적는다

## 일부러 다르게 둔 것

    LightGBM   log(정답 / 앵커) 를 배운다
    신경망      log(가격) 흐름을 배우고, 창마다 스스로 눈금을 맞춘다 (robust scaler)

신경망에 **유리한 쪽으로만** 전처리한다. 불리하게 만들어 놓고 «역시 안 된다»
고 하면 실험이 아니다 (exp_mlp.py 와 같은 원칙).

⚠️ 한 가지는 신경망에 불리하다 — 조기 종료를 위해 학습 끝 61 조사일(약 3달)을
   검증용으로 떼어 둔다. LightGBM 은 그 구간까지 배운다. 결과를 읽을 때 감안한다.

## 날짜 축

학습표의 대상일은 **기준일 목록에서 리드만큼 뒤**다 (실측 134,862행 중 어긋남 0).
그래서 조사일 하나를 한 칸으로 세면 신경망의 «h 칸 뒤» 가 곧 «리드 h-1» 이다.

    칸 i 의 y        = 기준일 i 의 리드 0 경락가 (그날 밤 경매)
    자르는 자리 c     = 기준일 c+1 의 아침. c 까지의 y 와 과거 입력만 본다
    예측 k 칸째       = 기준일 c+1 · 리드 k-1

## 쓰는 법

    (본 파이썬)  python exp_seq.py <csv> --mode lgb    --fold A
    (venv)      <venv>\\python exp_seq.py <csv> --mode nn --fold A --models tft lstm gru
    (어느 쪽)    python exp_seq.py <csv> --mode report --fold A

★ 두 환경을 나눈 이유 — 토치를 배치가 쓰는 파이썬에 깔면 pandas·numpy 가
  바뀌어 매일 아침 배치가 조용히 달라질 수 있다. 신경망은 따로 둔 venv 에서만 돈다.
"""
from __future__ import annotations

import argparse
import io
import statistics as st
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")      # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
OUT = ROOT / "실험결과" / "시퀀스모델_20260910"

ITEMS = ["배추", "무", "양파"]
ALPHA = 0.4                      # 경락가 앵커 수축 (운영과 같다)
ROUNDS = 76                      # 운영 fixed_iter
TRAIN_START = "2017-01-01"
H = 19                           # 리드 0 ~ 18
FOLDS = {"A": ("2022-12-31", "2023-12-31"),
         "B": ("2021-12-31", "2022-12-31"),
         "C": ("2020-12-31", "2021-12-31")}

BASE_COLS = ["auc_prc_lag1", "auc_prc_avg7", "auc_prc_avg14", "auc_prc_prev_yr"]
NEED = (["base_dt", "target_dt", "item_nm", "lead_biz_d", "target_auc_prc",
         "whsl_prc_lag1", "rtl_prc_lag1", "arr_qty_lag1", "auc_vol_lag1",
         "prod_area_temp_avg_lag1", "prod_area_rain_sum7",
         "target_dow", "holiday_remain_d", "kimchi_season_yn"] + BASE_COLS)


def load(csv: str) -> pd.DataFrame:
    df = pd.read_csv(csv, usecols=NEED, parse_dates=["base_dt", "target_dt"],
                     encoding="utf-8-sig")
    df = df[df["item_nm"].isin(ITEMS)].copy()
    df["anchor"] = (ALPHA * df["auc_prc_lag1"]
                    + (1 - ALPHA) * df["auc_prc_avg7"]).fillna(df["auc_prc_lag1"])
    return df


def eval_rows(df: pd.DataFrame, fold: str) -> pd.DataFrame:
    """채점할 행. 정답과 앵커가 다 있는 검증 구간의 모든 리드."""
    te, ve = FOLDS[fold]
    r = df[(df.base_dt > te) & (df.base_dt <= ve)
           & df.target_auc_prc.notna() & df.anchor.notna() & (df.anchor > 0)]
    return r[["item_nm", "base_dt", "lead_biz_d", "target_auc_prc", "anchor"] + BASE_COLS]


KEY = ["item_nm", "base_dt", "lead_biz_d"]


def wmape(a, p) -> float:
    a, p = np.asarray(a, float), np.asarray(p, float)
    return float(np.abs(a - p).sum() / np.abs(a).sum())


def save(name: str, fold: str, frame: pd.DataFrame) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"preds_{name}_{fold}.csv"
    frame.to_csv(p, index=False, encoding="utf-8-sig")
    return p


# ── LightGBM — 지금까지 모든 비교가 쓴 틀 그대로 ──────────────────────────
def mode_lgb(a) -> int:
    sys.path.insert(0, str(HERE))
    import exp_models as M                                   # noqa: PLC0415
    from exp_quantile import build                           # noqa: PLC0415

    te, ve = FOLDS[a.fold]
    tr, va, feats, cats, tgt, anc, label = build(a.csv, "auc", te, ve, ALPHA)
    tr = tr[tr.base_dt >= pd.Timestamp(TRAIN_START)]
    print(f"[LightGBM] 폴드 {a.fold} · 학습 {len(tr):,}행 · 검증 {len(va):,}행 · "
          f"feature {len(feats)}개 · 트리 {ROUNDS} · 시드 {a.seeds}")
    out = va[KEY].copy()
    out["base_dt"] = pd.to_datetime(out["base_dt"])
    for s in a.seeds:
        t0 = time.time()
        out[f"s{s}"] = va[anc].to_numpy(float) * np.exp(M.run_lgb(tr, va, feats, cats, s, ROUNDS))
        print(f"  시드 {s}  {time.time() - t0:.0f}초")
    print("  ->", save("lgb", a.fold, out))
    return 0


# ── 신경망 — 조사일 한 칸짜리 시계열로 바꿔 준다 ────────────────────────
HIST = ["h_last", "h_anc", "h_whsl", "h_rtl", "h_arr", "h_vol", "h_temp", "h_rain"]


def _yn(s: pd.Series) -> pd.Series:
    if s.dtype == object:
        return s.map({"Y": 1, "N": 0, "1": 1, "0": 0, "True": 1, "False": 0}).fillna(0).astype(float)
    return pd.to_numeric(s, errors="coerce").fillna(0).astype(float)


def series_frame(df: pd.DataFrame):
    """(품목, 조사일) 한 칸 = 리드 0 행 하나. 반환: 긴 표 · 품목별 조사일 목록."""
    l0 = df[(df.lead_biz_d == 0) & (df.base_dt >= pd.Timestamp(TRAIN_START))].copy()
    l0 = l0.sort_values(["item_nm", "base_dt"], kind="mergesort")
    days = {it: list(g.base_dt) for it, g in l0.groupby("item_nm", observed=True)}
    l0["ds"] = l0.groupby("item_nm", observed=True).cumcount()

    raw_y = np.log(l0["target_auc_prc"])
    l0["available_mask"] = raw_y.notna().astype(float)
    l0["y"] = raw_y.groupby(l0["item_nm"]).transform(lambda s: s.ffill().bfill())

    #   ★ 앵커가 전날 y 와 같은 값인지 찍어 본다.
    #
    #     처음 돌렸을 때 77.78% 였다 (2026-09-10). 앞 조사일과 하루 차이인 칸은
    #     0.0% 불일치, **월요일은 95.6% 불일치**였다. 원인은 토요일 — 경매는
    #     토요일에도 열리는데 조사일 축에는 토요일이 없다. 운영 앵커
    #     (`auc_prc_lag1`)는 «직전 경매일» 값이라 월요일엔 토요일 경매가다
    #     (예시 6개 전부 토요일 경매가와 정확히 일치).
    #
    #     그래서 y 만 주면 **신경망만 토요일을 못 본다.** 불공정한 비교다.
    #     아래 h_last · h_anc 로 운영이 보는 것과 같은 정보를 준다.
    prev = l0.groupby("item_nm")["target_auc_prc"].shift(1)
    both = prev.notna() & l0["auc_prc_lag1"].notna()
    same = np.isclose(prev[both], l0.loc[both, "auc_prc_lag1"], rtol=1e-6).mean()
    print(f"  [축 점검] 기준일 i 의 어제 경락가 = 칸 i-1 의 y : {same * 100:.2f}% 일치 "
          f"({int(both.sum()):,}칸) — 나머지는 토요일 경매. h_last 로 따로 준다")

    #   ★ 그날 아침에 이미 아는 마지막 경매가 · 운영 앵커.
    #     칸 c 의 값 = 기준일 c+1 의 lag1 · 앵커. 자르는 자리 c 에서 예측하는
    #     것이 바로 기준일 c+1 이므로, **그날 아침에 이미 아는 값**이다.
    #     미래를 보지 않는다 — 운영 LightGBM 이 받는 것과 같은 정보다.
    nxt = l0.groupby("item_nm")[["auc_prc_lag1", "anchor"]].shift(-1)
    l0["h_last"] = np.log(nxt["auc_prc_lag1"])
    l0["h_anc"] = np.log(nxt["anchor"])

    #   과거에만 아는 것 — 전날 값들. 자르는 자리 뒤는 모델이 안 본다
    l0["h_whsl"] = np.log(l0["whsl_prc_lag1"])
    l0["h_rtl"] = np.log(l0["rtl_prc_lag1"])
    l0["h_arr"] = np.log1p(l0["arr_qty_lag1"])
    l0["h_vol"] = np.log1p(l0["auc_vol_lag1"])
    l0["h_temp"] = l0["prod_area_temp_avg_lag1"]
    l0["h_rain"] = np.log1p(l0["prod_area_rain_sum7"])
    for c in HIST:
        l0[c] = l0.groupby("item_nm", observed=True)[c].transform(lambda s: s.ffill().bfill()).fillna(0.0)

    #   미리 아는 미래 — 그 칸(대상일) 자신의 달력
    dows = sorted(l0["target_dow"].dropna().unique())
    futr = []
    for d in dows:
        c = f"f_dow_{d}"
        l0[c] = (l0["target_dow"] == d).astype(float)
        futr.append(c)
    l0["f_hol"] = l0["holiday_remain_d"].clip(0, 60).fillna(60) / 60.0
    l0["f_kimchi"] = _yn(l0["kimchi_season_yn"])
    futr += ["f_hol", "f_kimchi"]

    long = l0.rename(columns={"item_nm": "unique_id"})[
        ["unique_id", "ds", "y", "available_mask"] + HIST + futr]
    static = pd.DataFrame({"unique_id": ITEMS})
    for it in ITEMS:
        static[f"s_{it}"] = (static["unique_id"] == it).astype(float)
    return long, static, days, futr, [f"s_{it}" for it in ITEMS]


def make_model(name: str, seed: int, futr, stat, a):
    from neuralforecast.losses.pytorch import MAE             # noqa: PLC0415
    from neuralforecast.models import GRU, LSTM, TFT          # noqa: PLC0415
    common = dict(h=H, input_size=a.input_size, loss=MAE(), scaler_type="robust",
                  futr_exog_list=futr, hist_exog_list=HIST, stat_exog_list=stat,
                  max_steps=a.max_steps, learning_rate=a.lr, batch_size=32,
                  val_check_steps=50, early_stop_patience_steps=5, random_seed=seed,
                  enable_progress_bar=False, enable_model_summary=False, logger=False)
    if name == "tft":
        return TFT(hidden_size=64, n_head=4, dropout=0.1, **common)
    if name == "lstm":
        return LSTM(encoder_n_layers=2, encoder_hidden_size=64,
                    decoder_hidden_size=64, **common)
    if name == "gru":
        return GRU(encoder_n_layers=2, encoder_hidden_size=64,
                   decoder_hidden_size=64, **common)
    raise SystemExit(f"모르는 모델: {name}")


def mode_nn(a) -> int:
    import logging                                           # noqa: PLC0415
    logging.getLogger("lightning.pytorch").setLevel(logging.ERROR)
    import torch                                             # noqa: PLC0415
    from neuralforecast import NeuralForecast                # noqa: PLC0415

    print(f"[신경망] torch {torch.__version__} · GPU {torch.cuda.is_available()}")
    df = load(a.csv)
    long, static, days, futr, stat = series_frame(df)

    te, ve = FOLDS[a.fold]
    first, last = {}, {}
    for it, ds_list in days.items():
        idx = [i for i, d in enumerate(ds_list) if pd.Timestamp(te) < d <= pd.Timestamp(ve)]
        first[it], last[it] = idx[0], idx[-1]
    n_win = {it: last[it] - first[it] + 1 for it in days}
    if len(set(n_win.values())) != 1 or len(set(last.values())) != 1:
        raise SystemExit(f"품목마다 조사일 축이 다릅니다: {n_win} {last}")
    W, L = n_win[ITEMS[0]], last[ITEMS[0]]
    cut = long[long.ds <= L + H - 1]
    print(f"  폴드 {a.fold} · 창 {W}개(검증 기준일) · 입력 {a.input_size}칸 · "
          f"외생 과거 {len(HIST)} · 미래 {len(futr)} · 품목 {len(stat)}")

    for name in a.models:
        out = None
        for s in a.seeds:
            t0 = time.time()
            nf = NeuralForecast(models=[make_model(name, s, futr, stat, a)], freq=1)
            cv = nf.cross_validation(df=cut, static_df=static, n_windows=W, step_size=1,
                                     val_size=a.val_size, refit=False)
            col = [c for c in cv.columns if c not in ("unique_id", "ds", "cutoff", "y")][0]
            cv = cv.reset_index() if "unique_id" not in cv.columns else cv
            base_i = (cv["cutoff"] + 1).astype(int)
            lead = (cv["ds"] - cv["cutoff"] - 1).astype(int)
            frame = pd.DataFrame({
                "item_nm": cv["unique_id"].astype(str),
                "base_dt": [days[u][i] for u, i in zip(cv["unique_id"].astype(str), base_i)],
                "lead_biz_d": lead,
                f"s{s}": np.exp(cv[col].to_numpy(float)),
            })
            out = frame if out is None else out.merge(frame, on=KEY, how="outer")
            print(f"  {name:<5} 시드 {s}  {time.time() - t0:.0f}초  ({len(frame):,}행)")
        print("  ->", save(name, a.fold, out))
    return 0


# ── 채점 — 모든 모델을 같은 행에서 ─────────────────────────────────────
NAMES = {"lgb": "LightGBM", "tft": "TFT", "lstm": "LSTM", "gru": "GRU"}


def mode_report(a) -> int:
    df = load(a.csv)
    ev = eval_rows(df, a.fold)
    found = {}
    for k in NAMES:
        p = OUT / f"preds_{k}_{a.fold}.csv"
        if p.exists():
            f = pd.read_csv(p, parse_dates=["base_dt"], encoding="utf-8-sig")
            found[k] = f
    if not found:
        raise SystemExit("예측 파일이 없습니다. --mode lgb / nn 을 먼저 돌리세요.")

    #   ★ 공통 행만 잰다. 행이 다르면 비교가 아니다 — 그래서 몇 행이 빠졌는지 찍는다
    common = ev[KEY]
    for k, f in found.items():
        common = common.merge(f[KEY], on=KEY)
    print(f"[채점] 폴드 {a.fold} · 채점 대상 {len(ev):,}행 · 모든 모델 공통 {len(common):,}행")
    for k, f in found.items():
        print(f"  {NAMES[k]:<9} 예측 {len(f):,}행")

    base = ev.merge(common, on=KEY)
    lines = []

    def table(sub: pd.DataFrame, title: str):
        lines.append(f"\n== {title} · {len(sub):,}행 ==")
        crops = ["전체"] + ITEMS
        hdr = f"  {'':<12}" + "".join(f"{c:>18}" for c in crops)
        lines.append(hdr)
        # baselines
        bl = {"앵커(α0.4)": "anchor", "어제": "auc_prc_lag1", "7일평균": "auc_prc_avg7",
              "14일평균": "auc_prc_avg14", "작년동기": "auc_prc_prev_yr"}
        best = {}
        for nm, col in bl.items():
            row = f"  {nm:<12}"
            for c in crops:
                s = sub if c == "전체" else sub[sub.item_nm == c]
                m = s[col].notna()
                w = wmape(s.loc[m, "target_auc_prc"], s.loc[m, col]) if m.any() else np.nan
                if m.mean() > 0.99 and (c not in best or w < best[c][1]):
                    best[c] = (nm, w)
                row += f"{w:>18.4f}"
            lines.append(row)
        res = {}
        for k, f in found.items():
            j = sub.merge(f, on=KEY)
            seeds = [c for c in f.columns if c.startswith("s") and c[1:].isdigit()]
            row = f"  {NAMES[k]:<12}"
            res[k] = {}
            for c in crops:
                s = j if c == "전체" else j[j.item_nm == c]
                ws = [wmape(s["target_auc_prc"], s[sd]) for sd in seeds if s[sd].notna().all()]
                m_, sd_ = (st.mean(ws), st.pstdev(ws)) if ws else (np.nan, 0.0)
                res[k][c] = (m_, sd_, len(ws))
                row += f"{m_:>10.4f} ±{sd_:.4f}"
            lines.append(row)
        lines.append(f"  {'가장 센 baseline':<12}" + "".join(
            f"{best[c][0]:>10} {best[c][1]:.4f}" if c in best else f"{'-':>18}" for c in crops))
        #   판정 — LightGBM 대비. 편차×2 를 넘어야 O/X
        if "lgb" in res:
            for k in res:
                if k == "lgb":
                    continue
                row = f"  {NAMES[k] + ' vs LGB':<12}"
                for c in crops:
                    lm, ls, _ = res["lgb"][c]
                    nm_, ns, _ = res[k][c]
                    d = lm - nm_
                    sd2 = 2 * max(ls, ns)
                    mark = "O" if d > sd2 else ("X" if -d > sd2 else "ㅡ")
                    row += f"{d:>+11.4f} {mark:>6}"
                lines.append(row)
        for k in res:
            row = f"  {NAMES[k] + ' vs 최강':<12}"
            for c in crops:
                if c in best:
                    row += f"{(1 - res[k][c][0] / best[c][1]) * 100:>+17.1f}%"
                else:
                    row += f"{'-':>18}"
            lines.append(row)

    table(base[base.lead_biz_d >= 3], "주 비교 · 리드 3 이상")
    table(base[base.lead_biz_d <= 2], "참고 · 리드 0~2 (게이트를 끈 자리)")
    lines.append("\n  O = LightGBM 보다 편차×2 넘게 좋음 · X = 넘게 나쁨 · ㅡ = 판정 불가")
    lines.append("  ※ 폴드 하나로 정하지 않는다. 두 폴드의 부호가 같을 때만 믿는다.")
    text = "\n".join(lines)
    print(text)
    OUT.mkdir(parents=True, exist_ok=True)
    rp = OUT / f"report_{a.fold}.txt"
    io.open(rp, "w", encoding="utf-8").write(text + "\n")
    print("\n  ->", rp)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="시퀀스 신경망 vs LightGBM — 경락가")
    ap.add_argument("csv")
    ap.add_argument("--mode", required=True, choices=["lgb", "nn", "report"])
    ap.add_argument("--fold", default="A", choices=list(FOLDS))
    ap.add_argument("--models", nargs="+", default=["tft", "lstm", "gru"])
    ap.add_argument("--seeds", nargs="+", type=int, default=[42, 43, 44])
    ap.add_argument("--input-size", type=int, default=56)
    ap.add_argument("--max-steps", type=int, default=2000)
    ap.add_argument("--val-size", type=int, default=61)
    ap.add_argument("--lr", type=float, default=1e-3)
    a = ap.parse_args()
    return {"lgb": mode_lgb, "nn": mode_nn, "report": mode_report}[a.mode](a)


if __name__ == "__main__":
    raise SystemExit(main())
