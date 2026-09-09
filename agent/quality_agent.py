# -*- coding: utf-8 -*-
"""데이터 품질 감시 agent (2026-08-31).

## 왜 만드나

08-27 에 찾은 사고 — 경락가 타겟이 포장 규격 15종을 한 평균에 섞고 있었다 —
는 **2015년부터 데이터에 그대로 보였다.** `max 19,900원/kg` 이 평균 939원 옆에
매일 찍혀 있었고, 특등급이 상등급보다 싼 날이 90% 였다.

**우리가 짠 모든 검증 쿼리가 "이미 의심하던 것" 만 보고 있었다.**
괜찮다고 넘겨짚은 것은 아무도 안 봤다.

이 agent 는 **"당연히 성립해야 하는 것"** 만 훑는다. 여기 있는 검사 넷은
전부 그 사고를 몇 년 전에 잡았을 것들이다.

  ① 등급 순서      특 >= 상 인가            → 배추 90% 위반이었음
  ② 일중 분산      위10%/아래10% 3배 넘는가  → 섞이면 3.5배
  ③ 계열 건전성    어제→오늘 연결 0.3 미만   → 0.085 였음
  ④ 정답-앵커 일치  같은 기준으로 뽑았나      → 08-28 에 96% 어긋나 있었음

④ 는 08-28 에 새로 겪은 사고다. 앵커에만 규격을 걸고 정답에는 안 걸어
**모델이 A 상품 어제 가격으로 B 상품 오늘 가격을 맞히고** 있었다.

## 쓰는 법

    python agent/quality_agent.py              # 최근 90일
    python agent/quality_agent.py --days 365
"""
from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from core import BAD, OK, WARN, Finding, Report, db, narrate  # noqa: E402

MARKET = "110001"          # 서울가락
GRADE_TOP, GRADE_2ND = "11", "12"
ITEMS = ("배추", "무", "양파")

#   ★ 등급 순서 검사에 바닥 둘을 둔다 (2026-09-09).
#
#     09-09 에 배추가 «역전율 50% · 이상» 으로 울었는데, 파보니 **분모가
#     2일**이었다. 그중 하루에 상등급 **50kg 한 건**(같은 날 특등급은
#     518,140kg)이 특등급 평균보다 비쌌던 것이 전부다.
#
#     실측 (최근 180일 · 우리 규격) —
#
#         품목   두 등급 다 있는 날   상등급 하루 물량 중앙
#         무           103일              65,480kg   (특의 16%)
#         배추           2일                  50kg   (특의 0.02%)
#         양파          23일                 345kg   (특의 0.07%)
#
#     **50kg 은 가격이 아니라 잡음이다.** 그래서 두 가지를 건다.
MIN_SHARE = 0.01           # 상등급 물량이 특등급의 1% 미만인 날은 안 센다
MIN_DAYS = 20              # 그러고도 20일이 안 모이면 비율을 내지 않는다
#
#     왜 1% 인가 — 특등급 하루 물량이 늘 10만kg 을 넘으므로 1% 는 대략
#     1,000kg 이다. 실측으로 무는 103 -> 96일로 거의 안 줄고, 배추는
#     **3년 통틀어 0일**, 양파는 180일에 2일만 남는다. 규격 사고(08-27)로
#     걸러야 할 것을 못 거르지도 않는다 — 그때는 1kg 소포장 물량이
#     10kg 그물망만큼 컸다.
#
#     왜 20일 인가 — 그보다 적으면 하루가 비율을 5%p 넘게 움직인다.
#     판정 경계가 10%/30% 라서, 몇 건으로 «정상 <-> 이상» 을 넘나든다.
#     오늘 자료로는 3~87 사이 어느 값을 골라도 결과가 같아 예민하지 않다.

# 우리 타겟이 쓰는 규격. v5 의 tmp_auc 와 같아야 한다.
SPEC = ("AND ((item_name='배추' AND package_name IN ('그물망','파렛트') AND unit_weight_kg=10) "
        " OR (item_name='무' AND package_name IN ('상자','파렛트') AND unit_weight_kg=20) "
        " OR (item_name='양파' AND package_name IN ('그물망','파렛트') AND unit_weight_kg=15))")


def check_grade_order(c, days: int) -> Finding:
    """① 특등급이 상등급보다 싼 날이 있나.

    ★ **거래가 거의 없는 등급으로는 판정하지 않는다.** 위 MIN_SHARE ·
      MIN_DAYS 를 보라. 지금 우리 규격에서 실제로 판정되는 것은 무 하나이고,
      배추·양파는 «표본 부족» 으로 남는다. 그것이 사실이다 — 억지로 비율을
      내면 한 건이 들어올 때마다 0% <-> 50% <-> 100% 로 튄다.
    """
    rows = c.execute(f"""
        WITH d AS (
          SELECT auction_date dt, item_name it, grade_code g,
                 SUM(trade_amount_krw)/SUM(trade_volume_kg) p,
                 SUM(trade_volume_kg) v
          FROM auction_prices_daily
          WHERE wholesale_market_code=%s AND grade_code IN (%s,%s)
            AND trade_volume_kg>0 AND auction_date >= CURRENT_DATE - %s {SPEC}
          GROUP BY 1,2,3),
        j AS (
          SELECT a.it, a.p pa, b.p pb, b.v / a.v AS share
          FROM d a JOIN d b ON b.dt=a.dt AND b.it=a.it AND b.g=%s
          WHERE a.g=%s)
        SELECT it,
               COUNT(*)                                        AS raw,
               COUNT(*) FILTER (WHERE share >= %s)             AS used,
               COUNT(*) FILTER (WHERE share >= %s AND pa < pb) AS bad
        FROM j GROUP BY 1 ORDER BY 1
    """, (MARKET, GRADE_TOP, GRADE_2ND, days, GRADE_2ND, GRADE_TOP,
          MIN_SHARE, MIN_SHARE)).fetchall()

    nums, worst, judged = [], 0.0, 0
    for it, raw, used, bad in rows:
        if used < MIN_DAYS:
            #   ★ «0%» 로 적지 않는다. 0% 는 «안 틀렸다» 로 읽히는데
            #     사실은 «못 쟀다» 이다.
            nums.append((f"{it} 판정 안 함",
                         f"쓸 수 있는 날 {used}일 (최소 {MIN_DAYS}일) · "
                         f"두 등급 다 있는 날은 {raw}일"))
            continue
        judged += 1
        r = bad / used
        worst = max(worst, r)
        nums.append((f"{it} 역전", f"{used}일 중 {bad}일 ({r*100:.0f}%)"
                                   + (f" · {raw - used}일은 물량이 적어 뺌"
                                      if raw > used else "")))

    if judged == 0:
        return Finding(WARN, "등급 순서 — 판정하지 못했습니다",
                       "상등급 거래가 너무 적어 셋 다 못 쟀습니다." + chr(10) +
                       "**이상이 없다는 뜻이 아닙니다** — 재려면 자료가 모자랍니다.",
                       nums,
                       "규격 조건을 넓힐지는 사람이 정하세요. 넓히면 "
                       "다른 상품이 섞입니다 (배추 상등급은 상자 8kg 이 본류).")

    lv = BAD if worst > 0.30 else (WARN if worst > 0.10 else OK)
    return Finding(
        lv, f"등급 순서 (특 >= 상)  최대 역전율 {worst*100:.0f}% · 판정 {judged}품목",
        #   정상이면 아무 말도 안 한다. 이상할 때만 왜인지 말한다.
        "" if lv == OK else
        ("특등급이 상등급보다 싼 날이 너무 많습니다. 진짜 시장에서는 드뭅니다." + chr(10) +
         "서로 다른 포장 규격이 한 평균에 섞이면 이렇게 됩니다."),
        nums,
        "" if lv == OK else "규격 조건이 타겟과 어긋났는지 확인하세요.")


def check_intraday(c, days: int) -> Finding:
    """② 하루 안에서 값이 얼마나 벌어지나.

    ★ 2026-08-31 수정 — **극단값 하나에 휘둘리던 것을 고쳤다.**

      처음에는 `그날 최고가 ÷ 그날 최저가` 로 쟀다. 첫 실행에서 배추가
      평균 10.5배로 '이상' 이 떴는데, 파보니 규격 문제가 아니었다.

          2026-06-04  최저 50원 · 최고 1,640원 · 평균 553원 · 물량 346톤
          2026-07-20  최저 30원 · 최고   890원 · 평균 520원 · 물량 329톤

      **상품성이 떨어져 헐값에 넘긴 건**이었다. 물량도 평균가도 정상이다.
      08-27 사고 때는 평균 자체가 오염됐었다 (939원 vs 진짜 711원).

      잘못된 경보가 매일 뜨면 사람이 무시하게 되고, 그러면 진짜 이상도
      같이 묻힌다. 우리가 경보 파일에서 이미 겪은 실패다.

      그래서 두 가지를 바꿨다.
        · 극단값 대신 **분위수**(위 90% ÷ 아래 10%)로 잰다
        · **물량이 그날 1퍼센트 미만인 거래는 뺀다** — 80kg 짜리 소포장 한 건이
          하루를 대표할 수는 없다

      ※ SQL 문자열 안 주석에 퍼센트 기호를 쓰면 psycopg 가 자리표시자로 읽어
        터진다. 실제로 "incomplete placeholder" 로 두 번 실패했다.
    """
    rows = c.execute(f"""
        WITH r AS (
          SELECT auction_date dt, item_name it,
                 avg_auction_price_krw_per_kg p, trade_volume_kg v,
                 SUM(trade_volume_kg) OVER (PARTITION BY auction_date, item_name) tot
          FROM auction_prices_daily
          WHERE wholesale_market_code=%s AND grade_code=%s
            AND trade_volume_kg>0 AND avg_auction_price_krw_per_kg>0
            AND auction_date >= CURRENT_DATE - %s {SPEC}),
        k AS (
          SELECT dt, it,
                 percentile_cont(0.9) WITHIN GROUP (ORDER BY p) hi,
                 percentile_cont(0.1) WITHIN GROUP (ORDER BY p) lo
          FROM r WHERE v >= tot * 0.01          -- 물량 하위 1퍼센트 거래는 뺀다
          GROUP BY 1,2 HAVING COUNT(*) >= 3)    -- 규격이 하나뿐인 날은 잴 수 없다
        SELECT it, ROUND(AVG(hi/NULLIF(lo,0))::numeric,1),
               ROUND(MAX(hi/NULLIF(lo,0))::numeric,1), COUNT(*)
        FROM k GROUP BY 1 ORDER BY 1
    """, (MARKET, GRADE_TOP, days)).fetchall()
    nums, worst = [], 0.0
    for it, avg, mx, n in rows:
        worst = max(worst, float(avg or 0))
        nums.append((f"{it} 평균 / 최대", f"{avg}배 / {mx}배  ({n}일)"))
    if not rows:
        return Finding(OK, "일중 분산 — 잴 수 있는 날이 없음")
    #   기준선은 짐작이 아니라 2017~2026 실측에서 잡았다.
    #     규격 고정 정상값  1.19 ~ 2.23배  (연도x품목 30개)
    #     규격 안 걸면      배추 3.5배 · 마늘 2.2배 (08-27 사고 상태 재현)
    #   그 사이에 놓는다. 정상 최대 2.23 위, 사고값 3.5 아래.
    lv = BAD if worst > 3.0 else (WARN if worst > 2.5 else OK)
    return Finding(
        lv, f"일중 분산 (위 90% / 아래 10%)  최대 평균 {worst}배",
        "" if lv == OK else
        ("같은 날 같은 등급인데 값이 너무 벌어집니다. 서로 다른 상품이\n"
         "한 평균에 섞였을 때 나타나는 모양입니다.\n"
         "(극단값과 소량 거래는 이미 빼고 잰 값입니다)"),
        nums,
        "" if lv == OK else "포장 규격이 한 종류로 고정돼 있는지 확인하세요.")


def check_series_health(c, days: int) -> Finding:
    """③ 어제 가격이 오늘 가격을 얼마나 알려주나 (자기상관)."""
    nums, worst = [], 1.0
    for it in ITEMS:
        v = [float(r[0]) for r in c.execute(f"""
            SELECT SUM(trade_amount_krw)/SUM(trade_volume_kg)
            FROM auction_prices_daily
            WHERE item_name=%s AND wholesale_market_code=%s AND grade_code=%s
              AND trade_volume_kg>0 AND auction_date >= CURRENT_DATE - %s {SPEC}
            GROUP BY auction_date ORDER BY auction_date
        """, (it, MARKET, GRADE_TOP, days))]
        if len(v) < 30:
            nums.append((f"{it}", f"거래일 {len(v)}일 — 표본 부족"))
            continue
        m = statistics.mean(v)
        den = sum((x - m) ** 2 for x in v)
        acf = (sum((v[i] - m) * (v[i + 1] - m) for i in range(len(v) - 1)) / den
               if den else 0.0)
        worst = min(worst, acf)
        nums.append((f"{it} 자기상관", f"{acf:.3f}  (거래일 {len(v)})"))
    lv = BAD if worst < 0.30 else (WARN if worst < 0.60 else OK)
    return Finding(
        lv, f"계열 건전성 (어제→오늘)  최저 {worst:.3f}",
        "" if lv == OK else
        ("어제 값이 오늘 값을 거의 알려주지 못합니다. 0 에 가까우면 무작위이고,\n"
         "그런 값은 무엇을 넣어도 예측할 수 없습니다."),
        nums,
        "" if lv == OK else "이 값이 낮으면 어떤 feature 를 넣어도 나아지지 않습니다.")


def check_target_anchor(c, days: int) -> Finding:
    """④ 정답과 앵커가 같은 기준에서 나왔나."""
    rows = c.execute(f"""
        WITH spec AS (
          SELECT auction_date dt, item_name it,
                 SUM(trade_amount_krw)/SUM(trade_volume_kg) p
          FROM auction_prices_daily
          WHERE wholesale_market_code=%s AND grade_code=%s AND trade_volume_kg>0 {SPEC}
          GROUP BY 1,2)
        SELECT t.item_nm, COUNT(*),
               SUM(CASE WHEN ABS(t.target_auc_prc - s.p) > 1 THEN 1 ELSE 0 END)
        FROM crop_price_train t JOIN spec s ON s.dt=t.target_dt AND s.it=t.item_nm
        WHERE t.target_auc_prc IS NOT NULL
          AND t.target_dt >= CURRENT_DATE - %s
        GROUP BY 1 ORDER BY 1
    """, (MARKET, GRADE_TOP, days)).fetchall()
    nums, worst = [], 0.0
    for it, tot, bad in rows:
        r = bad / tot if tot else 0.0
        worst = max(worst, r)
        nums.append((f"{it} 불일치", f"{tot:,}행 중 {bad:,}행 ({r*100:.0f}%)"))
    lv = BAD if worst > 0.05 else (WARN if worst > 0.01 else OK)
    return Finding(
        lv, f"정답-앵커 기준 일치  최대 불일치 {worst*100:.0f}%",
        "" if lv == OK else
        ("맞힐 값과 출발점이 다른 규격에서 나왔습니다.\n"
         "'A 상품 어제 가격으로 B 상품 오늘 가격을 맞혀라' 가 된 상태입니다."),
        nums,
        "" if lv == OK else "v5 의 tmp_auc 와 tmp_auc_t 조건을 대조하세요.")


def main() -> int:
    ap = argparse.ArgumentParser(description="데이터 품질 감시")
    ap.add_argument("--days", type=int, default=90, help="최근 며칠을 볼지")
    ap.add_argument("--quiet", action="store_true", help="정상이면 출력 생략")
    a = ap.parse_args()

    rep = Report("데이터품질")
    with db() as c:
        for fn in (check_grade_order, check_intraday,
                   check_series_health, check_target_anchor):
            try:
                rep.add(fn(c, a.days))
            except Exception as e:                           # noqa: BLE001
                rep.add(Finding(WARN, f"{fn.__name__} 점검 실패",
                                f"{type(e).__name__}: {e}"))
    if not (a.quiet and rep.worst == OK):
        print(rep.text())
        s = narrate(rep)
        if s:
            print("[요약]")
            print(s)
    p = rep.save()
    print(f"[기록] {p}")
    return 1 if rep.worst == BAD else 0


if __name__ == "__main__":
    raise SystemExit(main())
