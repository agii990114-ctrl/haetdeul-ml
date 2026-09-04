# -*- coding: utf-8 -*-
"""조합별 실전 성적 — **못 쓰는 조합을 고르는 자리** (2026-09-04 · 백로그 M-13)

## 왜 필요한가

백로그 M-13 은 *"9개 조합 중 3개가 baseline 이하"* 를 전제합니다.
그 목록은 **규격 고정(08-27)·수축 앵커(08-28) 이전 것**이라 이미 낡았습니다.
운영 차단표(`ref_prediction_quality`)에는 지금 한 칸만 막혀 있습니다.

**그래서 목록을 다시 만듭니다.** 다만 함부로 만들면 안 됩니다 —

    2026-09-04 실측: 기준일 27개(1월에 몰림)로 재니 9칸 중 6칸이 "진다" 로
    나왔는데, 구간을 1~3월 / 8~9월 로 가르니 **6칸이 부호가 뒤집혔습니다.**
    8~9월 쪽 표본이 21~28행(일주일치)이라 -253.8% 같은 값이 나옵니다.

**한 구간으로 방향을 말하지 않습니다** (11절).

## 이 도구가 지키는 것

    ① 품목 × 타겟별로만            통합값은 비싼 품목이 분모를 지배한다 (8절)
    ② 구간을 갈라 부호를 본다        한 구간이 만든 값인지 가른다
    ③ 표본 수를 항상 같이 찍는다     한 자릿수면 방향을 단정하지 않는다
    ④ 앵커는 운영이 쓰는 수축 앵커    prediction_log.anchor_prc 그대로

## 쓰는 법

    python report_combos.py                     # 2026 전체
    python report_combos.py --from 2026-01-01 --to 2026-12-31
    python report_combos.py --by-quarter         # 분기로 갈라 본다
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "agent"))
from core import db  # noqa: E402

MIN_N = 100          # 이만큼 안 되면 방향을 단정하지 않는다

SQL = """
SELECT {grp} AS 구간, target_kind, item_nm,
       COUNT(*) AS n, COUNT(DISTINCT base_dt) AS 기준일,
       ROUND(100.0 * SUM(ABS(actual_prc - pred_prc))
             / NULLIF(SUM(actual_prc), 0), 2) AS 모델,
       ROUND(100.0 * SUM(ABS(actual_prc - anchor_prc))
             / NULLIF(SUM(actual_prc), 0), 2) AS 앵커,
       ROUND(100.0 * (SUM(ABS(actual_prc - anchor_prc)) - SUM(ABS(actual_prc - pred_prc)))
             / NULLIF(SUM(ABS(actual_prc - anchor_prc)), 0), 1) AS 개선율
  FROM prediction_log
 WHERE actual_prc IS NOT NULL
   AND lead_biz_d >= 3
   AND model_ver = ANY(%s)
   AND target_dt BETWEEN %s AND %s
 GROUP BY 1, 2, 3
 ORDER BY 2, 3, 1
"""

OPS = ["ops_auc", "ops_whsl", "ops_rtl"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="d_from", default="2026-01-01")
    ap.add_argument("--to", dest="d_to", default="2026-12-31")
    ap.add_argument("--by-quarter", action="store_true")
    ap.add_argument("--min-n", type=int, default=MIN_N)
    a = ap.parse_args()

    grp = ("'Q' || EXTRACT(quarter FROM target_dt)::int" if a.by_quarter
           else "'전체'")
    with db() as c:
        rows = c.execute(SQL.format(grp=grp), (OPS, a.d_from, a.d_to)).fetchall()

    if not rows:
        print("채점된 행이 없습니다.")
        return 1

    print("조합별 실전 성적 · 대상일 %s ~ %s · LT>=3 · 운영 모델"
          % (a.d_from, a.d_to))
    print("  앵커는 운영이 쓰는 수축 앵커입니다 (경락 0.4·어제값+0.6·7일평균).")
    print("  표본 %d행 미만은 방향을 단정하지 않습니다.\n" % a.min_n)

    cur_key = None
    signs: dict[tuple, list] = {}
    for 구간, kind, item, n, bd, m, anc, imp in rows:
        key = (kind, item)
        if key != cur_key:
            print("── %s %s" % (kind, item))
            cur_key = key
        weak = n < a.min_n
        mark = "  (표본 적음 · 방향 단정 안 함)" if weak else (
            "  ★ 앵커에 진다" if imp is not None and float(imp) < 0 else "")
        print("     %-6s n=%-5d 기준일 %-3d  모델 %5s%%  앵커 %5s%%  개선율 %+6s%%%s"
              % (구간, n, bd, m, anc, imp, mark))
        if not weak and imp is not None:
            signs.setdefault(key, []).append(float(imp) > 0)

    if a.by_quarter:
        print("\n── 구간마다 부호가 같은가 (같아야 방향을 믿는다)")
        for (kind, item), ss in sorted(signs.items()):
            if len(ss) < 2:
                print("     %-4s %-3s  구간이 하나뿐 — 판정 불가" % (kind, item))
            elif all(ss) or not any(ss):
                print("     %-4s %-3s  일치 (%s)"
                      % (kind, item, "양수" if ss[0] else "★ 음수"))
            else:
                print("     %-4s %-3s  ★ 갈림 — 한 구간이 만든 값이다" % (kind, item))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
