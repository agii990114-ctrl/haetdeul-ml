#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""드리프트 되감기 — 지난 주마다 그때 이 검사를 돌렸으면 울렸을까.

    왜 필요한가
        drift_agent 는 "3주 연속 앵커보다 밀리면 알린다" 로 판정한다.
        그런데 **한 번도 안 울렸다면** 그 문턱이 맞는지 알 수 없다.
        울린 적 없는 경보 위에 재학습 절차를 얹으면 안 쓰는 것을 만든다.

        그래서 채점 이력을 처음부터 훑으며, 각 주에서 그때까지의 자료만으로
        같은 규칙을 적용해 본다. 미래를 안 쓴다 — 그 주까지만 본다.

    무엇을 답하나
        ① 지금 문턱(3주 연속 · 1.0%p)으로 몇 번 울렸나
        ② 안 울렸다면 어느 문턱이면 울렸나
        ③ 울린 주에 실제로 무슨 일이 있었나 (모델·앵커 오차)

    쓰는 법
        python agent/drift_replay.py
        python agent/drift_replay.py --streak 2 --gap-pp 0.5
        python agent/drift_replay.py --scan          # 문턱을 훑는다
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from core import db                                        # noqa: E402
from drift_agent import SQL, OPS, MIN_ROWS, GAP_PP, STREAK, BASE_WEEKS   # noqa: E402


#   ★ 자기 출력을 UTF-8 로 고정한다 (2026-09-07).
#
#     윈도우 기본이 cp949 라, 보고서에 '—'(em dash) 하나만 있어도
#     UnicodeEncodeError 로 죽는다. 사람이 터미널에서 돌릴 때는
#     PYTHONIOENCODING=utf-8 을 붙여 왔지만, **화면에서 부르면 그게
#     안 넘어온다.** 부모에게 기대지 않고 여기서 직접 고정한다.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")   # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass


def load() -> dict[tuple[str, str], list[dict]]:
    """(타겟, 품목) -> 주별 성적. drift_agent 와 같은 SQL 을 쓴다."""
    with db() as c:
        rows = c.execute(SQL, (OPS,)).fetchall()
    series: dict[tuple[str, str], list[dict]] = {}
    for wk, kind, item, n, wmape, wa, gain in rows:
        series.setdefault((kind, item), []).append(
            dict(wk=wk, n=int(n), wmape=float(wmape or 0),
                 anchor=float(wa or 0), gain=None if gain is None else float(gain)))
    return series


def replay(series, min_rows: int, gap_pp: float, streak: int):
    """각 주를 '오늘' 이라 치고 그때까지의 자료로만 판정한다.

    drift_agent.gather() 와 같은 계산이다. 다른 것은 자료를 끝까지 안 보고
    그 주에서 끊는다는 점 하나다.
    """
    fired = []      # (주, 타겟, 품목, 최근 streak 주)
    judged_weeks = 0

    for (kind, item), ws in sorted(series.items()):
        usable_all = [w for w in ws if w["n"] >= min_rows and w["gain"] is not None]
        need = BASE_WEEKS + streak
        for end in range(need, len(usable_all) + 1):
            usable = usable_all[:end]            # ← 그 주까지만
            judged_weeks += 1
            recent = usable[-streak:]
            bad = [w for w in recent if (w["wmape"] - w["anchor"]) > gap_pp]
            if len(bad) == streak:
                fired.append((recent[-1]["wk"], kind, item, recent))
    return fired, judged_weeks


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-rows", type=int, default=MIN_ROWS)
    ap.add_argument("--gap-pp", type=float, default=GAP_PP)
    ap.add_argument("--streak", type=int, default=STREAK)
    ap.add_argument("--scan", action="store_true", help="문턱을 훑어 본다")
    a = ap.parse_args()

    series = load()
    if not series:
        print("채점된 예측이 없습니다.")
        return 1

    print("=" * 70)
    print("드리프트 되감기")
    print("=" * 70)

    # ── 자료가 얼마나 있나 ────────────────────────────────────────────
    print("\n[자료]")
    for (kind, item), ws in sorted(series.items()):
        usable = [w for w in ws if w["n"] >= a.min_rows and w["gain"] is not None]
        need = BASE_WEEKS + a.streak
        mark = "판정 가능" if len(usable) >= need else f"부족 ({need}주 필요)"
        print(f"  {kind:<5} {item:<4} 전체 {len(ws):>3}주 · 쓸 수 있는 주 {len(usable):>3}주   {mark}")

    # ── 지금 문턱으로 되감기 ──────────────────────────────────────────
    fired, judged = replay(series, a.min_rows, a.gap_pp, a.streak)
    print(f"\n[지금 문턱] {a.streak}주 연속 · 차이 {a.gap_pp}%p · 한 주 {a.min_rows}행 이상")
    print(f"  판정한 (주 × 조합) {judged}개 중 울린 것 {len(fired)}개")

    if fired:
        print("\n  울린 자리")
        for wk, kind, item, recent in fired:
            print(f"    {wk}  {kind} {item}")
            for w in recent:
                print(f"        {w['wk']}  모델 {w['wmape']:.1f}%% · 앵커 {w['anchor']:.1f}%%"
                      f"  (차 {w['wmape']-w['anchor']:+.1f}%p · {w['n']}행)")
    else:
        print("\n  ★ 한 번도 안 울렸습니다.")
        print("    '정상' 이라는 뜻일 수도, 문턱이 너무 높다는 뜻일 수도 있습니다.")

    # ── 문턱을 훑는다 ────────────────────────────────────────────────
    if a.scan:
        print("\n[문턱 훑기] 어디서부터 울리나")
        print("  연속주 \\ 차이(%p)   " + "".join(f"{g:>7}" for g in (0.0, 0.5, 1.0, 2.0, 3.0, 5.0)))
        for st in (2, 3, 4):
            cells = []
            for gp in (0.0, 0.5, 1.0, 2.0, 3.0, 5.0):
                f, _ = replay(series, a.min_rows, gp, st)
                cells.append(f"{len(f):>7}")
            print(f"  {st}주 연속            " + "".join(cells))
        print("\n  ★ 숫자는 '울린 (주 × 조합)' 개수입니다. 0 이면 그 문턱으로는 안 울립니다.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
