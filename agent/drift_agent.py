# -*- coding: utf-8 -*-
"""드리프트 감지 — **모델이 앵커를 잃고 있나** (2026-09-04 · 백로그 I-04)

## 무엇을 재나

"오차가 커졌나" 를 재면 **변동기마다 오탐이 납니다.** 값이 흔들리는 달에는
모델도 앵커도 같이 틀립니다. 그건 모델이 나빠진 게 아닙니다.

그래서 **앵커 대비 개선율**을 봅니다.

    개선율 = (앵커 오차 - 모델 오차) / 앵커 오차

우리 존재 이유가 *"앵커보다 낫다"* 이므로, **그게 무너지는 것이 드리프트**입니다.
변동기에는 둘 다 커져서 비율이 유지됩니다 — 오탐이 안 납니다.

    ※ 5.9 절에서 배운 것과 같은 자리입니다. "변동성이 낮으면 폴백" 을
      기각한 이유가 저변동 분위의 개선율이 폴드마다 반대였기 때문입니다.
      절대 오차로 판정하면 그 함정에 그대로 빠집니다.

## 규칙

    ① 품목 × 타겟별로만 본다        통합값은 비싼 품목이 분모를 지배한다 (8절)
    ② 표본이 적으면 판정 안 한다     하루치로 방향을 말하지 않는다 (11절)
    ③ 여러 주 연속일 때만 운다       한 주로 결정하지 않는다 (5.7절과 같은 정신)

## 무엇을 안 하나

**재학습을 스스로 걸지 않습니다.** 알리는 데까지만 합니다.
재학습은 사람이 근거를 보고 결정합니다 — 자동 재학습은 나쁜 구간을
그대로 배워 넣을 수 있습니다.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from core import BAD, OK, WARN, Finding, Report, db  # noqa: E402

#: 한 주 한 조합에 이만큼은 있어야 판정한다. 적으면 방향이 시드처럼 흔들린다.
MIN_ROWS = 60
#: 기준선보다 이만큼(%p) 아래로 떨어지면 '나쁜 주'
DROP_PP = 10.0
#: 나쁜 주가 이만큼 연속이면 알린다
STREAK = 3
#: 기준선을 잡을 때 쓰는 과거 주 수 (최근 구간은 뺀다)
BASE_WEEKS = 8

SQL = """
WITH scored AS (
    SELECT date_trunc('week', target_dt)::date AS wk,
           target_kind, item_nm,
           SUM(ABS(actual_prc - pred_prc))   AS err_model,
           SUM(ABS(actual_prc - anchor_prc)) AS err_anchor,
           SUM(actual_prc)                   AS tot,
           COUNT(*)                          AS n
      FROM prediction_log
     WHERE actual_prc IS NOT NULL
       AND lead_biz_d >= 3            -- LT1~2 는 게이트라 앵커와 같다
       AND model_ver = ANY(%s)
     GROUP BY 1, 2, 3
)
SELECT wk, target_kind, item_nm, n,
       ROUND(100.0 * err_model  / NULLIF(tot, 0), 3) AS wmape,
       ROUND(100.0 * err_anchor / NULLIF(tot, 0), 3) AS wmape_anchor,
       CASE WHEN err_anchor > 0
            THEN ROUND(100.0 * (err_anchor - err_model) / err_anchor, 2) END AS gain
  FROM scored
 ORDER BY target_kind, item_nm, wk
"""

OPS = ["ops_auc", "ops_whsl", "ops_rtl"]


def gather(min_rows: int, drop_pp: float, streak: int) -> Report:
    rep = Report("드리프트감지")
    with db() as c:
        rows = c.execute(SQL, (OPS,)).fetchall()

    if not rows:
        rep.add(Finding(WARN, "채점된 예측이 없습니다",
                        "score_predictions.py 가 돌아야 오차 이력이 쌓입니다."))
        return rep

    #   (타겟, 품목) 별로 주 단위 개선율을 늘어놓는다
    series: dict[tuple[str, str], list] = {}
    for wk, kind, item, n, wmape, wa, gain in rows:
        series.setdefault((kind, item), []).append(
            dict(wk=wk, n=int(n), wmape=float(wmape or 0),
                 anchor=float(wa or 0), gain=None if gain is None else float(gain)))

    judged = 0
    for (kind, item), ws in sorted(series.items()):
        usable = [w for w in ws if w["n"] >= min_rows and w["gain"] is not None]
        if len(usable) < BASE_WEEKS + streak:
            rep.add(Finding(OK, f"{kind} {item} — 아직 판정 못 합니다",
                            "쓸 수 있는 주가 %d개입니다. %d개는 있어야 합니다."
                            % (len(usable), BASE_WEEKS + streak),
                            [("한 주 최소 행수", f"{min_rows}행"),
                             ("전체 주", f"{len(ws)}개")]))
            continue

        judged += 1
        recent = usable[-streak:]
        base_pool = usable[:-streak][-BASE_WEEKS:]
        base = sorted(w["gain"] for w in base_pool)[len(base_pool) // 2]   # 중앙값
        bad = [w for w in recent if w["gain"] < base - drop_pp]

        nums = [("기준선(과거 %d주 중앙값)" % len(base_pool), f"{base:+.1f}%")] + [
            (str(w["wk"]), "%+.1f%% (모델 %.1f%% · 앵커 %.1f%% · %d행)"
             % (w["gain"], w["wmape"], w["anchor"], w["n"])) for w in recent]

        if len(bad) == streak:
            rep.add(Finding(
                BAD, f"{kind} {item} — {streak}주 연속으로 앵커 대비 밀렸습니다",
                "모델이 어제값보다 못한 상태가 이어집니다. 재학습을 검토하세요. "
                "값이 흔들려서가 아닙니다 — 앵커도 같이 흔들리면 이 비율은 유지됩니다.",
                nums))
        elif bad:
            rep.add(Finding(
                WARN, f"{kind} {item} — 최근 {len(bad)}주가 기준선 아래입니다",
                f"{streak}주 연속이면 알립니다. 아직 아닙니다.", nums))
        else:
            rep.add(Finding(OK, f"{kind} {item} — 기준선 유지", numbers=nums[:2]))

    if judged == 0:
        rep.add(Finding(WARN, "판정한 조합이 하나도 없습니다",
                        "표본이 쌓일 때까지 이 검사는 아무것도 못 봅니다. "
                        "'정상' 이 아니라 '아직 모름' 입니다."))
    return rep


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-rows", type=int, default=MIN_ROWS)
    ap.add_argument("--drop-pp", type=float, default=DROP_PP)
    ap.add_argument("--streak", type=int, default=STREAK)
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    rep = gather(a.min_rows, a.drop_pp, a.streak)
    if not (a.quiet and rep.worst == OK):
        print(rep.text())
    print("[기록] %s" % rep.save())
    return 1 if rep.worst == BAD else 0


if __name__ == "__main__":
    raise SystemExit(main())
