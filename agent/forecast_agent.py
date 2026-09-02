# -*- coding: utf-8 -*-
"""예측 설명 도우미 (2026-08-31).

## 무엇에 답하나

> **"배추가 2주 뒤에 왜 오른다고 봤어?"**

지금 매입 파트는 **숫자만 받습니다.** 이유를 못 받으니 믿어야 할지 판단하기
어렵습니다.

**오늘 그 문제가 실제로 터졌습니다.** 매입 파트가 812원을 받고 그게 무슨
값인지 몰라, 자기들 mock 시세(1,650원)와 비교했습니다. 실제 경락가의
2.02배라 예측 상한을 넘었고 **모든 매입안이 잘렸습니다.** 이 도우미가
있었다면 그 자리에서 "812원은 어제값 40% + 7일평균 60% 를 섞은 출발점" 이라고
말했을 것입니다.

## 지키는 것

**값을 지어내지 않습니다.** 전부 DB 와 저장된 모델에서 읽습니다.
없으면 "없음" 이라고 씁니다.

**한계(⑤)는 명령줄에서만 나옵니다.** 화면에서는 뺐습니다 (2026-08-31 지시 —
"프로젝트는 ML 예측값이 정확하다는 전제하에 진행한다"). 오차 수치 자체는
아래 두 곳에 남아 있어 사라지지 않습니다.
  · `DB/ml_price_forecasts_컬럼정의서_v1.md` — 매입 파트가 읽는 계약 문서
  · `score_predictions.py` 채점 출력

**규칙이 사실을 모으고, AI 는 그 위에 사람 말 요약을 얹습니다.**
AI 가 없거나 죽어도 아래 다섯 조각은 그대로 나옵니다.

    ① 무엇을 얼마로 봤나        예측값 · 범위
    ② 출발점이 무엇인가         앵커 분해 (α × 어제값 + (1-α) × 7일평균)
    ③ 모델이 얼마나 움직였나     출발점 대비 몇 %
    ④ 그날 모델이 본 값들        중요도 상위 feature 와 실제 값
    ⑤ ★ 한계                  이 조합의 지난 성적 (명령줄만 · 화면에서는 뺌)

## 쓰는 법

    python agent/forecast_agent.py --base-dt 2025-12-31 --item 배추 --lead 14
    python agent/forecast_agent.py --base-dt 2025-12-31 --item 무 --kind whsl --lead 5
    python agent/forecast_agent.py --item 배추 --lead 14          # 최신 기준일
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from core import BAD, OK, WARN, Finding, Report, db, narrate  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
KIT = ROOT / "ML" / "20260824" / "ml_train_kit_2"
KIND_NM = {"auc": "경락가", "whsl": "중도매가", "rtl": "소매가"}
KIND_ROLE = {"auc": "매입 — 경매에서 사는 값",
             "whsl": "중도매 — 도매상이 파는 값",
             "rtl": "매도 — 소비자가 사는 값"}

#   feature 이름을 사람 말로. 없는 이름은 원문 그대로 쓴다 (지어내지 않는다).
NICE = {
    "holiday_remain_d": "명절까지 남은 날",
    "target_dow": "대상일 요일",
    "kimchi_season_yn": "김장철인가",
    "lead_biz_d": "며칠 뒤인가 (장 서는 날 기준)",
    "item_nm": "품목",
    "prod_area_stn_nm": "주산지 관측소",
    "prod_area_temp_avg_lag1": "주산지 어제 기온(℃)",
    "prod_area_clim_temp_avg10": "주산지 평년 기온(℃)",
    "prod_area_rain_sum7": "주산지 최근 7일 비(mm)",
    "prod_area_rain_sum30": "주산지 최근 30일 비(mm)",
    "prod_area_gdd_sum30": "주산지 생육 온도 30일 합",
    "prod_area_clim_yr_cnt": "평년값에 쓴 과거 연도 수",
    "market_temp_avg_lag1": "시장(서울) 어제 기온(℃)",
    "market_closed_lag1_yn": "직전이 휴장이었나",
    "auc_prc_lag1": "경락가 어제", "auc_prc_lag3": "경락가 3일 전",
    "auc_prc_lag7": "경락가 7일 전", "auc_prc_avg7": "경락가 7일평균",
    "auc_prc_avg14": "경락가 14일평균", "auc_prc_std7": "경락가 7일 흔들림",
    "auc_prc_prev_yr": "경락가 작년 같은 시기", "auc_vol_lag1": "경매 물량 어제",
    "auc_prc_spread_lag1": "경락 최고-최저 벌어짐",
    "auc_whsl_ratio_lag1": "경락 대비 중도매 배수",
    "whsl_prc_lag1": "중도매가 어제", "whsl_prc_lag3": "중도매가 3일 전",
    "whsl_prc_lag7": "중도매가 7일 전", "whsl_prc_avg7": "중도매가 7일평균",
    "whsl_prc_avg14": "중도매가 14일평균", "whsl_prc_std7": "중도매가 7일 흔들림",
    "whsl_prc_prev_yr": "중도매가 작년 같은 시기",
    "rtl_prc_lag1": "소매가 어제", "rtl_prc_lag3": "소매가 3일 전",
    "rtl_prc_lag7": "소매가 7일 전", "rtl_prc_avg7": "소매가 7일평균",
    "rtl_prc_avg14": "소매가 14일평균", "rtl_prc_std7": "소매가 7일 흔들림",
    "rtl_prc_prev_yr": "소매가 작년 같은 시기",
    "arr_qty_lag1": "가락 반입량 어제(kg)", "arr_qty_avg7": "가락 반입량 7일평균",
    "arr_qty_prev_yr": "가락 반입량 작년 같은 시기",
    "prod_area_clim_temp_tgt": "주산지 평년 기온 — 대상일 기준(실험)",
    "_anchor_mix": "출발점(섞은 값)",
}


def nice(col: str) -> str:
    return NICE.get(col, col)


def fmt(v) -> str:
    if v is None:
        return "없음"
    if isinstance(v, (int, float)):
        return f"{v:,.1f}" if abs(v) < 10000 else f"{v:,.0f}"
    return str(v)


def load_meta(kind: str) -> dict:
    p = KIT / f"ops_{kind}" / "meta.json"
    if not p.exists():
        raise SystemExit(f"모델 설명서가 없습니다: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def importance(kind: str, feats: list) -> dict:
    """저장된 모델에서 중요도를 읽는다. lightgbm 이 없으면 빈 dict."""
    try:
        import lightgbm as lgb                                # noqa: PLC0415
        import numpy as np                                    # noqa: PLC0415
    except ImportError:
        return {}
    tot, n = None, 0
    for f in sorted(glob.glob(str(KIT / f"ops_{kind}" / "model_seed*.txt"))):
        try:
            imp = lgb.Booster(model_file=f).feature_importance(importance_type="gain")
        except Exception:                                     # noqa: BLE001
            continue
        if len(imp) != len(feats):
            continue
        tot = imp.astype(float) if tot is None else tot + imp
        n += 1
    if not n or tot is None or tot.sum() == 0:
        return {}
    tot = tot / tot.sum() * 100
    return {feats[i]: float(tot[i]) for i in range(len(feats))}


#   앵커가 쓴 '어제' 가 실제로 며칠인지 찾는다.
#
#   ★ 달력으로 하루 빼서 추측하지 않는다. 휴장·휴일이 있어 어긋난다.
#     기준일 직전 며칠의 실제 가격을 뽑아, **앵커 값과 맞아떨어지는 날**만
#     돌려준다. 못 찾으면 None 을 돌려주고 날짜를 안 찍는다.
#     모르는 것을 그럴듯하게 채우면 그게 제일 나쁘다.
_ASOF_SQL = {
    "auc": """
        SELECT auction_date::text,
               SUM(trade_amount_krw)/NULLIF(SUM(trade_volume_kg),0) AS p
          FROM auction_prices_daily
         WHERE item_name=%(item)s AND auction_date < %(bd)s
           AND auction_date >= %(bd)s::date - 30
           AND wholesale_market_code='110001' AND grade_code='11'
           AND trade_volume_kg>0 AND avg_auction_price_krw_per_kg>0
           AND (   (item_name='배추' AND package_name IN ('그물망','파렛트') AND unit_weight_kg=10)
                OR (item_name='무'   AND package_name IN ('상자','파렛트')
                    AND ((auction_date <  DATE '2018-01-01' AND unit_weight_kg=18)
                      OR (auction_date >= DATE '2018-01-01' AND unit_weight_kg=20)))
                OR (item_name='양파' AND package_name IN ('그물망','파렛트') AND unit_weight_kg=15))
         GROUP BY 1 ORDER BY 1 DESC""",
    "whsl": """
        SELECT exmn_ymd::text, AVG(exmn_dd_prc/NULLIF(unit_sz,0)) AS p
          FROM veg_daily_price_raw
         WHERE item_nm=%(item)s AND exmn_ymd < %(bd)s AND exmn_ymd >= %(bd)s::date - 30
           AND se_cd='02' AND grd_cd='04' AND mrkt_nm='가락도매'
           AND exmn_dd_prc IS NOT NULL AND unit_sz>0
         GROUP BY 1 ORDER BY 1 DESC""",
    "rtl": """
        SELECT exmn_ymd::text, AVG(exmn_dd_prc/NULLIF(unit_sz,0)) AS p
          FROM veg_daily_price_raw
         WHERE item_nm=%(item)s AND exmn_ymd < %(bd)s AND exmn_ymd >= %(bd)s::date - 30
           AND se_cd='01' AND grd_cd='04' AND sgg_cd='1101'
           AND exmn_dd_prc IS NOT NULL AND unit_sz>0
         GROUP BY 1 ORDER BY 1 DESC""",
}


def _asof_date(c, kind: str, item: str, base_dt: str, lag1: float) -> str | None:
    try:
        rows = c.execute(_ASOF_SQL[kind], {"item": item, "bd": base_dt}).fetchall()
    except Exception:                                        # noqa: BLE001
        return None
    for d, p in rows:
        if p is not None and abs(float(p) - lag1) < 0.5:
            return d
    return None


def explain(base_dt: str | None, item: str, kind: str, lead: int,
            with_limit: bool = True,
            with_actual: bool = True) -> tuple[Report, dict]:
    """규칙만으로 설명 재료를 모은다. AI 없이 끝까지 돈다."""
    rep = Report("예측설명")
    facts: dict = {"item": item, "kind": kind, "lead": lead}
    meta = load_meta(kind)
    alpha = float(meta.get("anchor_alpha", 1.0))
    anchor_col = meta["anchor_col"]
    pre = anchor_col.replace("_prc_lag1", "")

    with db() as c:
        if not base_dt:
            base_dt = str(c.execute(
                "SELECT MAX(base_dt) FROM prediction_log WHERE target_kind=%s "
                "AND model_ver LIKE 'ops%%'", (kind,)).fetchone()[0])
        facts["base_dt"] = base_dt

        row = c.execute(
            "SELECT target_dt, pred_prc, pred_lo, pred_hi, anchor_prc, actual_prc, "
            "       abs_pct_err, gated, gate_reason, unit, model_ver "
            "  FROM prediction_log "
            " WHERE base_dt=%s AND item_nm=%s AND target_kind=%s AND lead_biz_d=%s "
            "   AND model_ver LIKE 'ops%%' LIMIT 1", (base_dt, item, kind, lead)).fetchone()
        if not row:
            rep.add(Finding(WARN, f"{base_dt} {item} {KIND_NM[kind]} LT{lead} 예측이 없습니다",
                            "기준일·품목·리드타임을 확인하세요."))
            return rep, facts
        (tdt, pred, lo, hi, anchor, actual, err, gated, greason, unit, mver) = row
        pred, lo, hi, anchor = (float(x) for x in (pred, lo, hi, anchor))
        facts.update({"target_dt": str(tdt), "pred": pred, "anchor": anchor})

        # ── ① 무엇을 얼마로 봤나
        nums = [("대상일", f"{tdt}"),
                ("예측", f"{pred:,.0f}{unit}"),
                ("범위", f"{lo:,.0f} ~ {hi:,.0f}{unit}"),
                ("범위 폭", f"예측값의 {(hi-lo)/pred*100:.0f}%")]
        #   ★ with_actual=False 면 실제값 줄을 아예 안 넣는다 (2026-08-31 지시).
        #     운영에서는 예측을 낼 때 정답이 없다. 시연 화면에 정답이 보이면
        #     보는 사람이 "이만큼 맞힌다" 로 읽는데, 실제로 쓸 때의 모습이 아니다.
        if with_actual:
            if actual is not None:
                nums.append(("실제", f"{float(actual):,.0f}{unit}  (오차 {float(err):.1f}%)"))
            else:
                nums.append(("실제", "아직 안 지났거나 채점 전"))
        rep.add(Finding(
            OK, f"{item} · {KIND_NM[kind]} · {lead}영업일 뒤 → {pred:,.0f}{unit}",
            KIND_ROLE[kind], nums))

        # ── ② 출발점이 무엇인가
        f = c.execute(
            f"SELECT {pre}_prc_lag1, {pre}_prc_avg7 FROM crop_price_train "
            " WHERE base_dt=%s AND item_nm=%s AND lead_biz_d=%s",
            (base_dt, item, lead)).fetchone()
        if f and f[0] is not None:
            lag1 = float(f[0])
            avg7 = float(f[1]) if f[1] is not None else lag1
            calc = alpha * lag1 + (1 - alpha) * avg7
            #   ★ 2026-08-31 — 여기 원래 다섯 줄짜리 설명이 붙어 있었다.
            #     "이건 실제 거래가가 아닙니다. 어제 하루 값만 쓰면 …" 하는 글이
            #     **점을 누를 때마다 똑같이** 나왔다.
            #
            #     같은 글이 매번 뜨면 사람이 안 읽는다. 오늘 아침에 고친
            #     데이터 품질 오탐과 같은 실패다 — 늘 있는 것은 없는 것과 같다.
            #
            #     설명을 지우고 **값 자체가 말하게** 바꿨다.
            #       · 식을 보여주면 섞은 값이라는 게 그냥 보인다
            #       · '어제' 가 언제인지는 **날짜를 찍어** 준다.
            #         이게 매입 파트가 실제로 헷갈린 부분이다 (12-30 vs 12-31)
            #     배경 설명은 컬럼정의서에 있다. 보고서마다 되풀이하지 않는다.
            asof = _asof_date(c, kind, item, base_dt, lag1)
            lag_lbl = f"어제값 ({asof} 실측)" if asof else "어제값 (실측)"
            if alpha >= 1.0:
                detail = f"출발점 = 어제값 그대로 = {lag1:,.1f}   (섞지 않습니다)"
                nums = [(lag_lbl, f"{lag1:,.1f}{unit}"),
                        ("7일평균 (안 씀)", f"{avg7:,.1f}{unit}")]
            else:
                detail = (f"출발점 = {alpha:g} × {lag1:,.1f}(어제값)"
                          f" + {1-alpha:g} × {avg7:,.1f}(7일평균) = {calc:,.1f}")
                nums = [(lag_lbl, f"{lag1:,.1f}{unit}"),
                        ("7일평균", f"{avg7:,.1f}{unit}"),
                        ("섞는 비율 α", f"{alpha:g}")]
            rep.add(Finding(OK, f"출발점 {anchor:,.0f}{unit}", detail, nums))
        else:
            rep.add(Finding(WARN, f"출발점 {anchor:,.0f}{unit} — 분해하지 못했습니다",
                            "학습표에 그 기준일 행이 없습니다."))

        # ── ③ 모델이 얼마나 움직였나
        mv = (pred - anchor) / anchor * 100
        if gated:
            rep.add(Finding(
                WARN, "★ 이 값은 모델이 만든 게 아닙니다 — 출발점이 그대로 나갔습니다",
                "3일 안쪽은 어제 가격이 더 잘 맞아서 모델을 비켜세웁니다.",
                [("이유", greason or "알 수 없음")]))
        else:
            rep.add(Finding(
                OK, f"모델이 출발점에서 {mv:+.1f}% 움직였습니다",
                ("올린다고 봤습니다." if mv > 0.5 else
                 "내린다고 봤습니다." if mv < -0.5 else
                 "거의 그대로라고 봤습니다."),
                [("출발점", f"{anchor:,.0f}{unit}"), ("예측", f"{pred:,.0f}{unit}"),
                 ("차이", f"{pred-anchor:+,.0f}{unit}")]))

        # ── ④ 그날 모델이 본 값들
        feats = list(meta.get("features") or [])
        imp = importance(kind, feats)
        cols = [x[0] for x in c.execute(
            "SELECT column_name FROM information_schema.columns "
            " WHERE table_name='crop_price_train'").fetchall()]
        use = [f for f in feats if f in cols]
        if use:
            vals = c.execute(
                f"SELECT {','.join(use)} FROM crop_price_train "
                " WHERE base_dt=%s AND item_nm=%s AND lead_biz_d=%s",
                (base_dt, item, lead)).fetchone()
            got = dict(zip(use, vals)) if vals else {}
            order = sorted(use, key=lambda f: -imp.get(f, 0))[:8]
            nums = []
            for f in order:
                v = got.get(f)
                v = float(v) if isinstance(v, (int, float)) or hasattr(v, "as_tuple") else v
                tag = f" ({imp[f]:.1f}%)" if f in imp else ""
                nums.append((nice(f) + tag, fmt(v)))
            rep.add(Finding(
                OK, "모델이 그날 본 값 (중요한 것부터)",
                "괄호는 모델이 그 값을 얼마나 자주 참고하는지입니다 "
                "(그것 때문에 올랐다는 뜻은 아닙니다).", nums))

        # ── ⑤ ★ 한계
        #
        #   2026-08-31 지시 — **화면(클릭 설명)에서는 뺀다.**
        #     "우리 프로젝트는 ML 예측값이 정확하다는 전제하에 진행한다."
        #
        #   명령줄(`python agent/forecast_agent.py`)에서는 그대로 나온다.
        #   그리고 오차 수치 자체는 아래 두 곳에 남아 있어 사라지지 않는다.
        #     · DB/ml_price_forecasts_컬럼정의서_v1.md  (매입 파트가 읽는 계약 문서)
        #     · score_predictions.py 채점 출력
        if not with_limit:
            return rep, facts

        acc = c.execute(
            "SELECT COUNT(*), ROUND(AVG(abs_pct_err),1), "
            "       ROUND(100.0*COUNT(*) FILTER "
            "         (WHERE actual_prc NOT BETWEEN pred_lo AND pred_hi)/COUNT(*),0) "
            "  FROM prediction_log "
            " WHERE target_kind=%s AND item_nm=%s AND actual_prc IS NOT NULL "
            "   AND lead_biz_d>=3 AND left(model_ver,5)<>'dummy'", (kind, item)).fetchone()
        q = c.execute(
            "SELECT use_recommended, note FROM ref_prediction_quality "
            " WHERE target_kind=%s AND item_nm=%s", (kind, item)).fetchone()
        if acc and acc[0]:
            n, mape, outside = acc[0], float(acc[1]), float(acc[2])
            facts["mape"] = mape
            lv = BAD if mape >= 25 else (WARN if mape >= 12 else OK)
            body = (f"1,000원짜리를 평균 {mape*10:,.0f}원 틀립니다. "
                    f"범위 안에 드는 건 10번 중 {10-outside/10:.0f}번 (목표 8번).")
            nums = [("평균 오차", f"{mape:.1f}%"),
                    ("범위 밖", f"{outside:.0f}%"),
                    ("채점 건수", f"{n:,}건")]
            if q:
                nums.append(("모델 사용 판정", "사용" if q[0] else "★ 미사용 — 출발점이 그대로 나갑니다"))
                if q[1]:
                    nums.append(("판정 근거", q[1][:60]))
            rep.add(Finding(lv, f"★ 한계 — 이 조합의 지난 평균 오차 {mape:.1f}%", body, nums,
                            "예측 하나만 보고 결정하지 마세요."))
        else:
            rep.add(Finding(WARN, "★ 한계 — 채점된 기록이 없습니다",
                            "얼마나 맞는지 아직 모릅니다."))

    return rep, facts


def main() -> int:
    ap = argparse.ArgumentParser(description="예측을 왜 그렇게 냈는지 설명한다")
    ap.add_argument("--base-dt", default=None, help="생략하면 최신 기준일")
    ap.add_argument("--item", default="배추", choices=["배추", "무", "양파"])
    ap.add_argument("--kind", default="auc", choices=["auc", "whsl", "rtl"])
    ap.add_argument("--lead", type=int, default=14, help="며칠 뒤 (장 서는 날 기준) 1~18")
    ap.add_argument("--no-actual", action="store_true",
                    help="실제값을 빼고 낸다 (운영에서는 예측 시점에 정답이 없다)")
    ap.add_argument("--no-ai", action="store_true", help="규칙만 돌린다")
    ap.add_argument("--save", action="store_true", help="진행기록/agent_logs/ 에 남긴다")
    a = ap.parse_args()

    rep, _ = explain(a.base_dt, a.item, a.kind, a.lead, with_actual=not a.no_actual)
    print(rep.text())

    if not a.no_ai:
        s = narrate(rep)
        if s:
            print("─" * 70)
            print("[사람 말 요약]")
            print(s)
    if a.save:
        print(f"[기록] {rep.save()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
