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
#: 모델 오차가 앵커 오차보다 이만큼(%p) 크면 '나쁜 주'
#
#   ★ 처음에는 "기준선(과거 중앙값)보다 10%p 아래" 로 짰다가 고쳤습니다 (2026-09-04).
#     기준선이 높은 조합에서는 **이기고 있는 주까지 '나쁜 주'** 가 됐습니다.
#     실측: whsl 배추 기준선 +58.8% -> 문턱 +48.8% -> +3.8%, +29.0% 인 주도
#     '나쁨' 으로 세어 '3주 연속' 이 울었습니다. 두 주는 앵커를 이겼는데도요.
#
#   그리고 개선율은 **비율**이라 앵커가 아주 정확한 주에 폭발합니다.
#     실측: 앵커 4.0% · 모델 14.6% -> -263.9%. 신호가 아니라 나눗셈 탓입니다.
#
#   그래서 **오차의 차이(%p)** 로 봅니다. '모델이 앵커보다 1%p 넘게 나쁘다' 는
#   부풀지도 폭발하지도 않고, 읽는 사람이 바로 뜻을 압니다.
GAP_PP = 1.0
#: 나쁜 주가 이만큼 연속이면 알린다
#
#   ★ 3 -> 1 로 내렸습니다 (2026-09-10). **3 은 어떤 조합을 영영 못 잡습니다.**
#
#     2026 32주를 되감아 조합별 「나쁜 주 최장 연속」을 셌습니다.
#
#         auc 배추 2 · auc 양파 2 · rtl 양파 2   <- 3 으로는 절대 안 울림
#         auc 무   3 · rtl 무   3 · rtl 배추 3
#         whsl 무  6 · whsl 배추 15
#
#     아홉 중 셋이 구조상 감지 불가였습니다. 「3주는 신중한 값」이 아니라
#     **그 조합에서는 꺼져 있는 것**이었습니다.
#
#   ★ 헛울림 값이 쌉니다. 울려도 사람에게 안 갑니다 — 후보를 만들어(2분 반)
#     견주고, 지금 것보다 못하면 **지우고 아무 말도 안 합니다.** 사람은 이긴
#     경우만 봅니다. 드는 것은 컴퓨터 시간이고, 놓치는 것은 3주치 나쁜
#     예측입니다.
#
#   되감아 센 울림 횟수 (288 판정 기회):
#         STREAK=1  61회 · =2  38회 · =3  25회 · =4  17회
STREAK = 1
#: 기준선을 잡을 때 쓰는 과거 주 수 (최근 구간은 뺀다)
BASE_WEEKS = 8

#: ★ **판정에서 빼는 계열** (2026-09-10).
#:
#:   중도매가는 **열흘 중 엿새가 어제와 값이 같습니다** (58~68% · CLAUDE.md §8).
#:   앵커가 거의 완벽해서 모델이 이길 수 없습니다. 밀린 게 아니라 **애초에
#:   이길 수 없는 계열**입니다.
#:
#:       whsl 배추   나쁜 주 56% · 최장 연속 15주
#:       whsl 무     나쁜 주 44% · 최장 연속  6주
#:       whsl 양파   차이가 전부 0.0  <- ref_prediction_quality 로 막혀
#:                                      앵커를 그대로 내보내니 «모델=앵커»
#:
#:   STREAK 를 1 로 내리면 이쪽이 거의 매주 울리고, **그 후보는 항상 집니다.**
#:   배치만 하루 최대 7분 길어지고 얻는 것이 없습니다.
#:
#:   ★ 「빼면 못 본다」가 아닙니다 — 숫자는 그대로 보고서에 적고 판정만 안
#:     합니다. 등급 순서 검사에 최소 표본을 둔 것과 같은 방식입니다.
SKIP_KINDS = frozenset({"whsl"})

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
       -- ★ 2026-09-11 — 리드 0 부터 보고, 게이트로 앵커가 그대로 나간 행은 뺀다.
       --   전에는 lead_biz_d >= 3 이었다 («LT1~2 는 게이트라 앵커와 같다»).
       --   게이트를 09-09 에 꺼서 0~2 도 모델이 만든다 — 매입이 제일 먼저 쓰는
       --   오늘 밤·내일 경매 자리인데 감시에서 빠져 있었다.
       --   게이트 행(pred = anchor)은 리드와 무관하게 모델 값이 아니다
       --   (리드 3+ 에도 2,584행). 섞으면 모델·앵커 차이가 묽어진다.
       --   되감아 재니 최근 주 판정은 아홉 조합 모두 그대로, 나쁜 주 수는 ±1.
       AND lead_biz_d >= 0
       AND gated IS NOT TRUE
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


def gather(min_rows: int, gap_pp: float, streak: int) -> Report:
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
        #   ★ 판정에서 빼는 계열 — 숫자는 적고 판정만 안 한다 (SKIP_KINDS 주석).
        #     조용히 빼면 다음 사람이 「검사가 없네」 하고 도로 넣는다.
        if kind in SKIP_KINDS:
            last = [w for w in ws if w["n"] >= min_rows and w["gain"] is not None][-1:]
            nums = [(str(w["wk"]), "모델 %.1f%% · 앵커 %.1f%% (차 %+.1f%%p · %d행)"
                     % (w["wmape"], w["anchor"], w["wmape"] - w["anchor"], w["n"]))
                    for w in last]
            rep.add(Finding(
                OK, f"{kind} {item} — 판정 안 함",
                "중도매가는 열흘 중 엿새가 어제와 값이 같아 앵커가 거의 완벽합니다.\n"
                "밀린 것이 아니라 이길 수 없는 계열이라, 재학습 신호로 쓰지 않습니다.\n"
                "★ 숫자는 위에 그대로 있습니다 — 보시고 판단하실 수 있습니다.", nums))
            continue

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
        #   나쁜 주 = 모델 오차가 앵커 오차보다 gap_pp 넘게 크다.
        #   비율(개선율)로 재면 앵커가 정확한 주에 폭발한다 (위 GAP_PP 주석).
        bad = [w for w in recent if (w["wmape"] - w["anchor"]) > gap_pp]

        nums = [("참고 · 과거 %d주 개선율 중앙값" % len(base_pool), f"{base:+.1f}%")] + [
            (str(w["wk"]), "모델 %.1f%% · 앵커 %.1f%% (차 %+.1f%%p · %d행)"
             % (w["wmape"], w["anchor"], w["wmape"] - w["anchor"], w["n"]))
            for w in recent]

        if len(bad) == streak:
            rep.add(Finding(
                BAD, f"{kind} {item} — {streak}주 연속으로 앵커 대비 밀렸습니다",
                "모델이 어제값보다 못한 상태가 이어집니다. 재학습을 검토하세요. "
                "값이 흔들려서가 아닙니다 — 앵커도 같이 흔들리면 이 비율은 유지됩니다.",
                nums))
        elif bad:
            rep.add(Finding(
                WARN, f"{kind} {item} — 최근 {len(bad)}주가 앵커보다 나쁩니다",
                f"{streak}주 연속이면 알립니다. 아직 아닙니다.", nums))
        else:
            rep.add(Finding(OK, f"{kind} {item} — 앵커보다 낫거나 비슷", numbers=nums[:2]))

    if judged == 0:
        rep.add(Finding(WARN, "판정한 조합이 하나도 없습니다",
                        "표본이 쌓일 때까지 이 검사는 아무것도 못 봅니다. "
                        "'정상' 이 아니라 '아직 모름' 입니다."))
    return rep


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-rows", type=int, default=MIN_ROWS)
    ap.add_argument("--gap-pp", type=float, default=GAP_PP)
    ap.add_argument("--streak", type=int, default=STREAK)
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    rep = gather(a.min_rows, a.gap_pp, a.streak)
    if not (a.quiet and rep.worst == OK):
        print(rep.text())
    print("[기록] %s" % rep.save())
    return 1 if rep.worst == BAD else 0


if __name__ == "__main__":
    raise SystemExit(main())
