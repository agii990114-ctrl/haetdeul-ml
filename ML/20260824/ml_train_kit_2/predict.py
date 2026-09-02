# -*- coding: utf-8 -*-
"""
추론 스크립트
=============
train.py --save-model 로 저장한 번들을 읽어 예측을 만든다.

    python train.py <csv> --target whsl --train-start 2017-01-01 \
        --train-end 2022-12-31 --valid-end 2023-12-31 --seeds 42 43 44 45 46 \
        --gate-lt 3 --save-model model_whsl

    python predict.py <csv> --model-dir model_whsl --out pred.csv

왜 번들인가
    추론은 학습과 **완전히 같은 조건**에서 돌아야 한다. 어긋나면 예외가 나는
    게 아니라 조용히 틀린 값이 나온다. 특히 두 가지가 위험하다.

    1. feature 순서
       LightGBM 은 컬럼 이름이 아니라 위치로 받는다. 한 칸만 밀려도
       "기온 자리에 강수량" 이 들어가고 예측은 그럴듯한 숫자로 나온다.

    2. categorical 수준
       pandas category 는 문자열이 아니라 코드(정수)로 인코딩된다.
       추론 데이터의 카테고리 집합이 다르면 '배추' 가 0 이었다가 1 이 된다.
       품목이 통째로 바뀐 채 예측이 나온다.

    그래서 meta.json 에 feature 목록·순서·카테고리 수준을 박제하고,
    추론 시 하나라도 어긋나면 **멈춘다.**

역변환
    학습 타겟은 앵커 대비 로그비율이다. 반드시 되돌려야 한다.

        pred = anchor * exp(model_output)

    이걸 빼먹으면 0.049 같은 로그비율이 가격으로 저장된다. 실제로 자주 나는
    사고라 아래 sanity check 가 명시적으로 잡는다.

게이트 — 두 종류다
    둘 다 "모델을 쓰지 않고 앵커를 그대로 낸다" 는 뜻이고, gate_reason 으로 구분한다.

    lead_time   LT < gate_lt. 검증 2022·2023 두 폴드, 세 타겟 모두에서 LT1~2 가
                baseline 보다 나빴다. 어제 가격이 이미 정답에 가까워 모델이
                개입할 여지가 없다. 운영 권장값 3
    quality     품목×타겟 조합이 baseline 보다 나쁘다. ref_prediction_quality 의
                use_recommended 를 본다. 9개 조합 중 3개가 false다 —
                경락 양파 · 중도매 무·양파. 그대로 내보내면 매매 판단에 손해다

    품질표는 **실행 시점에 DB 에서 읽는다.** 운영 정책이라 모델과 수명이 달라서,
    meta.json 에 박제하면 정책을 바꿀 때마다 재학습해야 한다.

    **못 읽으면 멈춘다.** 게이트의 목적이 나쁜 조합을 막는 것인데 조용히
    건너뛰면 목적이 사라진다. 끄려면 --no-quality 를 명시해야 한다.
    품질표에 없는 조합도 기본은 앵커 폴백이다 (--unknown-policy pass 로 변경).

정답이 있으면 채점도 한다
    입력에 타겟 컬럼이 있으면(과거 구간) WMAPE·방향정확도를 함께 낸다.
    학습 때 나온 검증 수치와 같은지 확인하는 용도다. 다르면 번들이나
    입력이 어긋난 것이다.
"""
import argparse
import datetime
import json
import os
import sys

import numpy as np
import pandas as pd
import lightgbm as lgb

MODEL_FORMAT = 1


def wmape(t, p):
    t, p = np.asarray(t, float), np.asarray(p, float)
    m = ~(np.isnan(t) | np.isnan(p))
    if not m.any():
        return float("nan")
    return np.abs(t[m] - p[m]).sum() / np.abs(t[m]).sum()


def dir_acc(t, p, ref):
    t, p, ref = (np.asarray(x, float) for x in (t, p, ref))
    m = ~(np.isnan(t) | np.isnan(p) | np.isnan(ref))
    if not m.any():
        return float("nan")
    return ((t[m] - ref[m]) * (p[m] - ref[m]) > 0).mean()


def read_csv_any(path):
    for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            return pd.read_csv(path, encoding=enc)
        except UnicodeDecodeError:
            continue
    raise SystemExit("CSV 인코딩을 읽지 못했습니다. UTF-8 로 다시 내보내세요.")


def load_bundle(d):
    mp = os.path.join(d, "meta.json")
    if not os.path.exists(mp):
        raise SystemExit("meta.json 이 없습니다: %s\n"
                         "  train.py --save-model 로 만든 디렉터리를 지정하세요." % d)
    with open(mp, encoding="utf-8") as f:
        meta = json.load(f)
    if meta.get("format") != MODEL_FORMAT:
        raise SystemExit("번들 형식이 다릅니다 (파일 %s / 이 스크립트 %s). "
                         "train.py 와 predict.py 버전을 맞추세요."
                         % (meta.get("format"), MODEL_FORMAT))
    models = []
    for fn in meta["models"]:
        p = os.path.join(d, fn)
        if not os.path.exists(p):
            raise SystemExit("모델 파일이 없습니다: %s" % p)
        models.append(lgb.Booster(model_file=p))

    #   분위수 모델(상한·하한). 없으면 빈 dict — 옛 번들도 그대로 돈다.
    #   ★ 파일이 하나라도 없으면 **멈춘다.** 일부만 읽고 나머지를 조용히
    #   고정표로 채우면, 품목마다 다른 방식으로 만든 구간이 한 표에 섞인다.
    qmods = {}
    for q, names in (meta.get("quantile_models") or {}).items():
        bs = []
        for fn in names:
            p = os.path.join(d, fn)
            if not os.path.exists(p):
                raise SystemExit("분위수 모델 파일이 없습니다: %s  번들이 깨졌습니다. 다시 학습하거나 meta.json 의 quantile_models 를 지우세요." % p)
            bs.append(lgb.Booster(model_file=p))
        qmods[float(q)] = bs
    return meta, models, qmods


def prepare(df, meta):
    """추론 입력을 학습과 동일한 형태로 맞춘다. 어긋나면 멈춘다."""
    feats = meta["features"]
    missing = [c for c in feats if c not in df.columns]
    if missing:
        raise SystemExit("입력에 feature 가 없습니다 (%d개): %s\n"
                         "  학습에 쓴 CSV 와 같은 스키마여야 합니다."
                         % (len(missing), missing[:8]))

    # categorical 수준을 학습 때 그대로 복원한다.
    #   학습에 없던 값은 NaN 이 되고 LightGBM 이 결측으로 처리한다.
    #   조용히 넘어가면 안 되므로 건수를 보고한다.
    for c, levels in meta.get("cat_levels", {}).items():
        if c not in df.columns:
            continue
        raw = df[c].astype(str).where(df[c].notna(), None)
        df[c] = pd.Categorical(raw, categories=levels)
        unseen = raw.notna() & df[c].isna()
        if unseen.any():
            vals = sorted(set(raw[unseen]))[:5]
            print("  [주의] %s: 학습에 없던 값 %d행 -> 결측 처리 %s"
                  % (c, int(unseen.sum()), vals))
    return df[feats]


def load_quality(csv_path=None):
    """ref_prediction_quality → {(target_kind, item_nm): (use_recommended, note)}

    운영 정책이라 모델과 수명이 다르다. meta.json 에 박제하면 정책을 바꿀 때마다
    재학습해야 하므로 실행 시점에 읽는다.

    **못 읽으면 멈춘다.** 이 게이트의 목적이 baseline 보다 나쁜 조합을 막는 것인데,
    조용히 건너뛰면 목적이 사라진다. 일부러 끄려면 --no-quality 를 명시해야 한다.
    """
    if csv_path:
        import csv as _csv
        if not os.path.exists(csv_path):
            raise SystemExit(
                "품질표 CSV 가 없습니다: %s\n"
                "  ref_prediction_quality 를 내보내거나, --quality-csv 를 빼고\n"
                "  DB 에서 읽게 하세요. 정말 끄려면 --no-quality." % csv_path)
        with open(csv_path, encoding="utf-8-sig", newline="") as f:
            rows = list(_csv.DictReader(f))
        need = {"target_kind", "item_nm", "use_recommended"}
        if not rows or not need <= set(rows[0]):
            raise SystemExit(
                "품질표 CSV 형식이 다릅니다: %s\n"
                "  필요한 컬럼: target_kind · item_nm · use_recommended (note 는 선택)"
                % csv_path)
        out = {}
        for r in rows:
            u = str(r.get("use_recommended", "")).strip().lower()
            out[(r["target_kind"].strip(), r["item_nm"].strip())] = (
                u in ("true", "t", "1", "y", "yes"), (r.get("note") or "").strip())
        print("  [품질표] %s · %d조합" % (csv_path, len(out)))
        return out

    try:
        import psycopg
    except ImportError:
        raise SystemExit(
            "품질표를 읽으려면 psycopg 가 필요합니다.\n"
            "  pip install \"psycopg[binary]\"  또는  --quality-csv 로 파일을 주거나\n"
            "  --no-quality 로 게이트를 끄세요 (권장하지 않음).")

    root = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))))
    envp = os.path.join(root, ".env")
    if os.path.exists(envp):
        with open(envp, encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    v = v.strip()
                    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                        v = v[1:-1]
                    os.environ.setdefault(k.strip(), v)
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise SystemExit(
            ".env 에 DATABASE_URL 이 없어 품질표를 읽을 수 없습니다.\n"
            "  --quality-csv 로 파일을 주거나 --no-quality 로 끄세요.")
    try:
        with psycopg.connect(dsn, connect_timeout=15) as c, c.cursor() as cur:
            cur.execute("SELECT target_kind, item_nm, use_recommended, note "
                        "FROM ref_prediction_quality")
            out = {(k, i): (bool(u), n or "") for k, i, u, n in cur.fetchall()}
    except Exception as e:                                   # noqa: BLE001
        raise SystemExit(
            "품질표를 읽지 못했습니다: %s\n"
            "  28_prediction_log.sql 을 실행했는지 확인하세요.\n"
            "  --quality-csv 로 파일을 주거나 --no-quality 로 끌 수 있습니다." % e)
    print("  [품질표] ref_prediction_quality · %d조합 · 미사용 %d"
          % (len(out), sum(1 for v in out.values() if not v[0])))
    return out


def main():
    ap = argparse.ArgumentParser(description="저장된 모델로 예측을 만든다")
    ap.add_argument("csv", help="추론 입력 CSV (crop_price_train 스키마)")
    ap.add_argument("--model-dir", required=True, help="train.py --save-model 디렉터리")
    ap.add_argument("--out", default="prediction.csv")
    ap.add_argument("--base-dt", help="이 기준일만 추론 (생략 시 전체)")
    ap.add_argument("--base-dt-from", help="기준일 시작")
    ap.add_argument("--base-dt-to", help="기준일 끝")
    ap.add_argument("--gate-lt", type=int, default=None,
                    help="번들 값을 덮어쓴다. 지정 안 하면 학습 때 값을 쓴다")
    ap.add_argument("--items", nargs="+", default=None,
                    help="번들 값을 덮어쓴다")
    ap.add_argument("--model-ver", default=None,
                    help="prediction_log.model_ver 에 넣을 값. 생략 시 디렉터리명")
    ap.add_argument("--quality-csv", default=None,
                    help="ref_prediction_quality 를 CSV 로 줄 때. 생략 시 DB 에서 읽는다")
    ap.add_argument("--no-quality", action="store_true",
                    help="품질 게이트를 끈다. baseline 보다 나쁜 조합도 그대로 나간다")
    ap.add_argument("--unknown-policy", choices=["gate", "pass"], default="gate",
                    help="품질표에 없는 조합의 처리. gate=앵커로 폴백(기본) · pass=모델 사용")
    a = ap.parse_args()

    meta, models, qmods = load_bundle(a.model_dir)
    TARGET, ANCHOR = meta["target_col"], meta["anchor_col"]
    gate = meta.get("gate_lt", 0) if a.gate_lt is None else a.gate_lt
    items = meta.get("items") if a.items is None else a.items

    print("[번들] %s" % a.model_dir)
    print("  타겟 %s (%s / 앵커 %s)" % (meta["label"], TARGET, ANCHOR))
    print("  학습 %s ~ %s · 시드 %d개 · feature %d개"
          % (meta.get("train_start"), meta.get("train_end"),
             len(models), len(meta["features"])))
    print("  학습 시 검증 WMAPE %.4f · 게이트 LT<%s"
          % (meta.get("valid_wmape", float("nan")), gate))
    if meta.get("raw"):
        raise SystemExit("--raw 로 학습된 번들은 지원하지 않습니다 (앵커 변환 전용).")

    df = read_csv_any(a.csv)
    for c in ("base_dt", "lead_biz_d", ANCHOR):
        if c not in df.columns:
            raise SystemExit("입력에 필수 컬럼이 없습니다: %s" % c)
    df["base_dt"] = pd.to_datetime(df["base_dt"])

    if items and "item_nm" in df.columns:
        df = df[df.item_nm.isin(items)].copy()
    if a.base_dt:
        df = df[df.base_dt == pd.Timestamp(a.base_dt)].copy()
    if a.base_dt_from:
        df = df[df.base_dt >= pd.Timestamp(a.base_dt_from)].copy()
    if a.base_dt_to:
        df = df[df.base_dt <= pd.Timestamp(a.base_dt_to)].copy()

    # 앵커가 없으면 예측 자체가 불가능하다 (역변환의 기준값)
    n0 = len(df)
    df = df[df[ANCHOR].notna()].copy()
    if len(df) < n0:
        print("  [주의] 앵커 %s 결측 %d행 제외" % (ANCHOR, n0 - len(df)))
    if df.empty:
        raise SystemExit("추론할 행이 없습니다. 기간·품목 조건을 확인하세요.")

    # ── 수축 앵커 ★ (2026-08-28 도입 · 2026-08-31 수정) ───────
    #   계수는 번들 meta 에서 읽는다 — 옵션으로 따로 주게 두면 학습과 추론이
    #   언젠가 반드시 어긋나고, 그러면 역변환이 틀려도 에러 없이 조용히
    #   잘못된 값이 나온다. meta 에 없으면 옛 번들이라 1.0 으로 본다.
    #
    #   ▣ 08-31 수정 — 두 가지를 고쳤다
    #     ① **컬럼 이름을 학습 때와 맞춘다.** train.py 는 수축값을
    #        `_anchor_mix` 라는 새 컬럼에 담고 그걸 feature 로도 쓴다.
    #        여기서는 원본 이름(auc_prc_lag1)에 덮어쓰기만 해서
    #        `_anchor_mix` 가 없었고, 모델이 입력을 못 찾아 멈췄다.
    #          "입력에 feature 가 없습니다 (1개): ['_anchor_mix']"
    #          → 일별 배치가 8/29·8/30·8/31 사흘 연속 predict 에서 실패
    #          → 매입 파트 전달표가 8/28 이후 멈춤
    #     ② **prepare() 앞으로 옮긴다.** 입력 행렬을 만든 뒤에 컬럼을
    #        더해봐야 모델에 안 들어간다.
    _alpha = float(meta.get("anchor_alpha", 1.0))
    _feats = list(meta.get("features") or [])
    if _alpha < 1.0:
        _avg7 = ANCHOR.replace("_lag1", "_avg7")
        if _avg7 not in df.columns:
            raise SystemExit(
                "이 번들은 수축 앵커(α=%.2f)로 학습됐는데 입력에 %s 가 없습니다."
                % (_alpha, _avg7))
        n_na = int(df[_avg7].isna().sum())
        if n_na:
            print("  [주의] %s 결측 %d행 — 그 행은 어제값 단독으로 대체" % (_avg7, n_na))
        _mix = (_alpha * df[ANCHOR] + (1 - _alpha) * df[_avg7]).fillna(df[ANCHOR])
        #   학습이 쓰던 이름으로 넣는다. 그 이름이 feature 목록에 있을 때만
        #   넣으면 되지만, 없어도 해가 없으므로 항상 만들어 둔다.
        df = df.assign(_anchor_mix=_mix)
        ANCHOR = "_anchor_mix"
        print("  [앵커] 수축 α=%.2f  (어제값 %.0f%% + 7일평균 %.0f%%) → %s"
              % (_alpha, _alpha * 100, (1 - _alpha) * 100, ANCHOR))
    elif "_anchor_mix" in _feats:
        # α=1.0 인데 번들이 그 이름을 기대하는 경우 (섞여 저장된 옛 번들 대비)
        df = df.assign(_anchor_mix=df[ANCHOR])

    X = prepare(df, meta)

    # ── 예측 + 역변환 ─────────────────────────────────────────
    anchor = df[ANCHOR].to_numpy(float)
    preds = []
    for m in models:
        out = m.predict(X)
        preds.append(anchor * np.exp(out))     # ★ 역변환. 빼먹으면 로그비율이 저장된다
    pred = np.mean(preds, axis=0)
    spread = np.std(preds, axis=0) if len(preds) > 1 else np.zeros(len(pred))

    # ── 게이트 ────────────────────────────────────────────────
    #   게이트는 두 종류다. 둘 다 "모델을 쓰지 않고 앵커를 그대로 낸다" 는 뜻이지만
    #   사유가 다르므로 gate_reason 으로 구분해 로그에 남긴다.
    #
    #     lead_time  LT<3 은 어제 가격이 이미 정답에 가까워 모델이 개입할 여지가 없다
    #     quality    품목×타겟 조합이 baseline 보다 나쁘다 (ref_prediction_quality)
    lt = df["lead_biz_d"].to_numpy(int)
    gated = np.zeros(len(pred), dtype=bool)
    reason = np.array([""] * len(pred), dtype=object)

    if gate and gate > 0:
        g = lt < gate
        gated |= g
        reason[g] = "lead_time"
        print("  [게이트] LT < %d 는 앵커로 대체 (%d행 · %.0f%%)"
              % (gate, int(g.sum()), g.mean() * 100))

    if not a.no_quality:
        qual = load_quality(a.quality_csv)
        kind = meta["target"]
        items_q = (df["item_nm"].astype(str).to_numpy()
                   if "item_nm" in df.columns else np.array(["?"] * len(pred)))
        bad = np.zeros(len(pred), dtype=bool)
        unknown = np.zeros(len(pred), dtype=bool)
        for i in range(len(pred)):
            v = qual.get((kind, items_q[i]))
            if v is None:
                unknown[i] = True
            elif not v[0]:
                bad[i] = True
        if bad.any():
            for it in sorted(set(items_q[bad])):
                note = qual.get((kind, it), (None, ""))[1]
                print("  [품질게이트] %s × %s — 모델 미사용. %s" % (kind, it, note))
            gated |= bad
            reason[bad & (reason == "")] = "quality"
            reason[bad & (reason == "lead_time")] = "lead_time+quality"
        if unknown.any():
            us = sorted(set(items_q[unknown]))
            if a.unknown_policy == "gate":
                print("  [품질게이트] 품질표에 없는 조합 %s — 앵커로 폴백 "
                      "(--unknown-policy pass 로 바꿀 수 있음)" % us)
                gated |= unknown
                reason[unknown & (reason == "")] = "quality:unknown"
                reason[unknown & (reason == "lead_time")] = "lead_time+quality:unknown"
            else:
                print("  [주의] 품질표에 없는 조합 %s — 검증되지 않은 채로 모델을 씁니다" % us)
    else:
        print("  [주의] --no-quality — 품질 게이트를 껐습니다. "
              "baseline 보다 나쁜 조합도 그대로 나갑니다")

    if gated.any():
        pred = np.where(gated, anchor, pred)
        spread = np.where(gated, 0.0, spread)
        print("  [게이트 합계] %d행 · %.0f%% 가 앵커" % (int(gated.sum()), gated.mean() * 100))

    # ── sanity check ──────────────────────────────────────────
    #   역변환 누락이 가장 흔한 사고다. 로그비율은 0 근처의 작은 값이므로
    #   앵커와 자릿수가 완전히 달라진다. 그걸 잡는다.
    ratio = np.median(pred) / max(np.median(anchor), 1e-9)
    if not (0.2 < ratio < 5):
        raise SystemExit(
            "예측 중앙값이 앵커의 %.3f 배입니다. 역변환이 빠졌거나 앵커가 틀렸습니다.\n"
            "  pred 중앙값 %.4f · anchor 중앙값 %.4f" %
            (ratio, np.median(pred), np.median(anchor)))
    if (pred <= 0).any():
        raise SystemExit("예측에 0 이하가 %d건 있습니다." % int((pred <= 0).sum()))
    far = np.abs(np.log(pred / anchor)) > np.log(3)
    if far.any():
        print("  [주의] 앵커 대비 3배 이상 벗어난 예측 %d행 (%.2f%%)"
              % (int(far.sum()), far.mean() * 100))

    # ── 예측 구간 ─────────────────────────────────────────────
    #   번들에 저장된 경험적 밴드를 쓴다. 검증 구간에서 잰
    #   actual/pred 비율의 q10~q90 이므로 "10건 중 8건이 이 안" 이라는 뜻이다.
    #   시드 편차를 쓰지 않는 이유는 train.py 주석 참조.
    band = meta.get("band") or {}
    qmap = meta.get("quantile_q") or {}
    lo = np.full(len(pred), np.nan)
    hi = np.full(len(pred), np.nan)
    items_arr = (df["item_nm"].astype(str).to_numpy()
                 if "item_nm" in df.columns else None)

    if qmods and qmap and items_arr is not None:
        #   ── 분위수 회귀 (2026-09-01 채택 · CLAUDE.md 5.11) ──────────
        #   모델이 상한·하한을 직접 낸다. 고정표와 달리 **그날 입력에 따라
        #   폭이 달라진다** — 고정표는 (품목 × 리드타임)으로만 정해져
        #   품목 안에서 재면 조용한 날과 흔들리는 날의 폭이 정확히 같다(1.00).
        cache = {q: np.mean([b.predict(X) for b in bs], axis=0)
                 for q, bs in qmods.items()}
        miss_it = set()
        for it, q in qmap.items():
            m = items_arr == it
            if not m.any():
                continue
            klo, khi = round(float(q), 4), round(1 - float(q), 4)
            if klo not in cache or khi not in cache:
                miss_it.add(it)
                continue
            #   ★ 역변환. 빼먹으면 로그비율이 그대로 저장된다 (9절)
            lo[m] = anchor[m] * np.exp(cache[klo][m])
            hi[m] = anchor[m] * np.exp(cache[khi][m])
        unknown = sorted(set(items_arr) - set(qmap))
        if unknown:
            miss_it.update(unknown)
        if miss_it:
            #   조용히 고정표로 메우지 않는다. 한 표 안에 서로 다른 방식으로
            #   만든 구간이 섞이면 매입 파트가 같은 잣대로 못 읽는다.
            print("  [주의] 분위수 설정이 없는 품목 %s — pred_lo/hi 를 비웁니다"
                  % ", ".join(sorted(miss_it)))
        cross = int(np.nansum(lo > hi))
        if cross:
            print("  [주의] 분위수 교차 %d행 — 정렬해서 씁니다" % cross)
            lo, hi = np.minimum(lo, hi), np.maximum(lo, hi)
        print("  [구간] 분위수 회귀 · 품목별 하한 %s"
              % " · ".join("%s %.2f" % (k, float(v)) for k, v in qmap.items()))
    elif band and items_arr is not None:
        #   ── 고정표 (옛 방식) ────────────────────────────────────
        #   검증 구간에서 잰 actual/pred 비율의 q10~q90 이다.
        #   시드 편차를 쓰지 않는 이유는 train.py 주석 참조.
        miss = 0
        for i in range(len(pred)):
            b = band.get("%s|%d" % (items_arr[i], lt[i]))
            if b is None:
                miss += 1
                continue
            lo[i], hi[i] = pred[i] * b[0], pred[i] * b[2]
        if miss:
            print("  [주의] 밴드가 없는 조합 %d행 (pred_lo/hi 는 NULL)" % miss)
        print("  [구간] 고정표(ref_prediction_band 방식) · %d조합" % len(band))
    else:
        print("  [주의] 번들에 밴드도 분위수 모델도 없습니다. pred_lo/hi 를 비웁니다.")

    #   ★ 게이트가 걸린 행은 예측이 앵커 그대로다 (위에서 pred=anchor 로
    #   바꿨다). 구간도 거기에 맞춰야 앞뒤가 맞는다 — 분위수 모델은 그 행을
    #   위해 만든 것이 아니다 (LT 게이트 구간은 학습에서 빼고 잰다).
    #   리드타임 게이트뿐 아니라 품질 게이트·미지 품목도 마찬가지이므로
    #   `gated` 전체를 쓴다.
    if qmods and qmap and gated.any() and items_arr is not None:
        n_g = 0
        for i in np.flatnonzero(gated):
            b = band.get("%s|%d" % (items_arr[i], lt[i]))
            lo[i], hi[i] = ((pred[i] * b[0], pred[i] * b[2]) if b
                            else (np.nan, np.nan))
            n_g += 1
        print("  [구간] 게이트 %d행은 고정표로 붙였습니다 (예측이 앵커이므로)"
              % n_g)

    # ── 출력 ── prediction_log 스키마 그대로 ──────────────────
    #   컬럼 이름·순서를 테이블과 일치시킨다. 그래야 그대로 적재된다.
    unit = "원/단위" if meta["target"] == "rtl" else "원/kg"
    o = pd.DataFrame({
        "base_dt": df["base_dt"].dt.date,
        "target_dt": df["target_dt"] if "target_dt" in df.columns else pd.NaT,
        "item_nm": df["item_nm"] if "item_nm" in df.columns else None,
        "lead_biz_d": lt,
        "target_kind": meta["target"],
        "unit": unit,
        "anchor_prc": np.round(anchor, 3),
        "pred_prc": np.round(pred, 3),
        "pred_lo": np.round(lo, 3),
        "pred_hi": np.round(hi, 3),
        "seed_spread": np.round(spread, 3),
        "gated": gated,
        "gate_reason": np.where(gated, reason, None),
        "model_ver": a.model_ver or os.path.basename(os.path.abspath(a.model_dir)),
        "model_created_at": meta.get("created_at"),
        "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
    })
    if TARGET in df.columns:
        act = df[TARGET].to_numpy(float)
        o["actual_prc"] = np.round(act, 3)
        with np.errstate(invalid="ignore", divide="ignore"):
            o["abs_pct_err"] = np.round(np.abs(pred - act) / np.where(act != 0, act, np.nan) * 100, 4)
    o.to_csv(a.out, index=False, encoding="utf-8-sig")
    print()
    print("예측 저장: %s (%d행)" % (a.out, len(o)))
    print("  기준일 %s ~ %s"
          % (df.base_dt.min().date(), df.base_dt.max().date()))

    # ── 정답이 있으면 채점 ────────────────────────────────────
    if TARGET in df.columns and df[TARGET].notna().any():
        t = df[TARGET].to_numpy(float)
        print()
        print("[채점] 정답이 있는 구간이라 함께 계산합니다")
        print("  %-6s %9s %9s %9s %9s" % ("품목", "모델", "baseline", "개선율", "방향"))
        g = o.copy()
        g["_t"] = t
        for it, sub in g.groupby("item_nm", observed=True) if "item_nm" in g else [("전체", g)]:
            mo = wmape(sub._t, sub.pred_prc)
            bl = wmape(sub._t, sub.anchor_prc)
            da = dir_acc(sub._t, sub.pred_prc, sub.anchor_prc)
            print("  %-6s %9.4f %9.4f %+8.1f%% %8.1f%%"
                  % (it, mo, bl, (1 - mo / bl) * 100, da * 100))
        mo, bl = wmape(t, pred), wmape(t, anchor)
        print("  %-6s %9.4f %9.4f %+8.1f%%" % ("통합", mo, bl, (1 - mo / bl) * 100))
        print("  ※ 통합값은 참고용. 가격 수준이 높은 품목이 분모를 지배합니다.")
        vw = meta.get("valid_wmape")
        if vw and abs(mo - vw) < 1e-6:
            print("  학습 시 검증 WMAPE 와 일치합니다 (%.4f). 번들 재현 확인." % vw)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
