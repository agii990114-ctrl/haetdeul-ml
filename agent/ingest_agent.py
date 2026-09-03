# -*- coding: utf-8 -*-
"""수집 검사 agent — 재생성 전에 막는다 (2026-09-03 · 백로그 Q-01)

## 왜 여기서 막나

`DBEAVER_run_v5.sql` 은 **맨 앞에서 TRUNCATE** 합니다.
수집이 이상한 자료를 가져오면 **멀쩡한 학습표를 지우고 이상한 걸 채웁니다.**

```
수집 -> [여기서 검사] -> 재생성(TRUNCATE) -> 추론 -> 적재 -> 매입 파트
```

**여기가 마지막으로 되돌릴 수 있는 자리**입니다. 재생성이 지나가면
옛 표가 없습니다.

## `quality_agent` 와 무엇이 다른가

```
quality_agent   배치가 끝난 뒤 · 타겟의 뜻이 맞나 (등급 순서 · 계열 건전성)
ingest_agent    재생성 앞 · 들어온 자료가 평소 같나 (행수 · 결측 · 단위)
```

**앞의 것은 "우리가 만든 값이 말이 되나", 뒤의 것은 "원천이 평소 같나"**
입니다. 08-27 사고는 앞의 것이 잡을 일이었고, **수집기가 조용히 망가지는
것은 뒤의 것이라야 잡습니다.**

## ★ 고정 문턱을 쓰지 않습니다

백로그가 짚은 대로 **정상 결측과 사고성 결측이 다릅니다.**

```
sumRn 결측 62.2%              정상 (비가 안 오면 빈다)
prod_area_temp 0% -> 30%      사고
```

그래서 **최근 이력을 기준선으로 삼고 거기서 얼마나 벗어났나**를 봅니다.
문턱을 손으로 적으면 "62.2% 는 괜찮다" 같은 예외 목록이 끝없이 늘어납니다.

## 검사 여섯

```
① 수집 지연     원천마다 최신일이 며칠 밀렸나
①-2 품목별 지연  ★ 표 전체가 멀쩡해도 한 품목만 멈출 수 있다
② 행수 급감     어제 넣은 행수가 최근 기준선의 몇 % 인가
③ 중복          같은 자연키가 두 번 들어왔나
④ 단위 변화     가격 수준이 갑자기 몇 배로 뛰었나 (원/kg <-> 원/포 같은 사고)
⑤ 결측률 급증   중요 컬럼의 빈 비율이 기준선보다 크게 늘었나
```

## 쓰는 법

    python agent/ingest_agent.py            # 검사만
    python agent/ingest_agent.py --quiet    # 정상이면 조용
    # run_batch.py 의 precheck 단계가 이걸 부릅니다. BAD 면 배치가 멈춥니다
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from core import BAD, OK, WARN, Finding, Report, db, narrate  # noqa: E402

#   원천마다 (표, 날짜컬럼, 허용 지연일, 사람이 읽는 이름)
#   ★ 허용 지연은 원천 사정이 다르므로 하나로 못 묶습니다.
#   ★ 우리가 실제로 모델에 쓰는 품목. **이것만 배치를 막습니다.**
#     2026-09-03 에 건고추·피마늘·깐마늘 수집이 10일 멈춘 것을 이 검사가
#     잡았는데, 그대로 두면 **안 쓰는 품목 때문에 매입 파트 전달표까지
#     멈춥니다.** 막을 것만 막습니다 — 나머지는 알리기만 합니다.
MODELED = {"211", "231", "245"}          # 배추 · 무 · 양파

SOURCES = [
    ("auction_prices_daily", "auction_date", 3, "경락가"),
    ("veg_daily_price_raw", "exmn_ymd", 4, "중도매·소매가"),
    ("daily_volume", "base_date", 4, "반입량"),
    ("weather_asos_raw", "tm", 3, "기상"),
]


def _one(c, sql, args=()):
    with c.cursor() as cur:
        cur.execute(sql, args)
        return cur.fetchone()


def _all(c, sql, args=()):
    with c.cursor() as cur:
        cur.execute(sql, args)
        return cur.fetchall()


def check_lag(c) -> Finding:
    """① 수집 지연 — 원천마다 최신일이 얼마나 밀렸나."""
    nums, bad, warn = [], [], []
    for tbl, col, allow, label in SOURCES:
        r = _one(c, f"SELECT MAX({col})::date, CURRENT_DATE - MAX({col})::date "
                    f"FROM {tbl}")
        if not r or r[0] is None:
            bad.append(f"{label} 비어 있음")
            continue
        mx, lag = r[0], int(r[1])
        nums.append((f"{label} 최신", f"{mx} ({lag}일 전)"))
        if lag > allow * 2:
            bad.append(f"{label} {lag}일 (허용 {allow})")
        elif lag > allow:
            warn.append(f"{label} {lag}일 (허용 {allow})")
    if bad:
        return Finding(BAD, "수집이 크게 밀렸습니다", " · ".join(bad), nums,
                       "그 원천 수집기를 먼저 돌리세요. 재생성하면 낡은 값으로 예측합니다.")
    if warn:
        return Finding(WARN, "수집이 조금 밀렸습니다", " · ".join(warn), nums)
    return Finding(OK, "수집 지연", "원천 넷 다 허용 안", nums)


def check_item_lag(c) -> Finding:
    """①-2 품목별 지연 — ★ 표 전체 최신일만 보면 못 잡는다.

    **2026-09-03 에 실제로 걸렸다.** `veg_daily_price_raw` 의 표 전체 최신일은
    2026-09-02 라 `check_lag` 가 "정상" 으로 찍었는데, 여섯 품목 중 **셋이
    2026-08-24 에서 멈춰 있었다 (10일).**

        211 배추 09-02 · 231 무 09-02 · 245 양파 09-02      정상
        241 건고추 · 244 피마늘 · 258 깐마늘  08-24          10일 멈춤

    **한 품목만 살아 있어도 표 전체는 멀쩡해 보인다.** 오늘 그림자 실행이
    자기 자신과 비교하면서 "성공" 으로 찍히던 것과 같은 종류다.
    """
    nums, bad, warn = [], [], []
    rs = _all(c, """SELECT item_cd,
                           (array_agg(item_nm ORDER BY exmn_ymd DESC))[1],
                           MAX(exmn_ymd)::date,
                           CURRENT_DATE - MAX(exmn_ymd)::date
                      FROM veg_daily_price_raw GROUP BY 1 ORDER BY 1""")
    for cd, nm, mx, lag in rs:
        lag = int(lag)
        used = cd in MODELED
        nums.append((f"{cd} {nm}{'' if used else ' (모델 미사용)'}",
                     f"{mx} ({lag}일 전)"))
        if lag <= 4:
            continue
        (bad if (used and lag > 8) else warn).append(f"{cd} {nm} {lag}일")
    if bad:
        return Finding(BAD, "우리가 쓰는 품목의 수집이 멈췄습니다", " · ".join(bad), nums,
                       "표 전체 최신일은 멀쩡해 보입니다. 그 품목의 원천 응답을 확인하세요.")
    if warn:
        return Finding(WARN, "일부 품목이 밀렸습니다", " · ".join(warn), nums,
                       "모델이 안 쓰는 품목이면 배치를 막지 않습니다. 다만 그대로 두면 영영 안 들어옵니다.")
    return Finding(OK, "품목별 지연", "여섯 품목 다 최신", nums)


def check_rowcount(c) -> Finding:
    """② 행수 급감 — 어제 들어온 행이 최근 기준선의 몇 %인가.

    ★ 기준선은 **최근 30 거래일의 중앙값**이다. 평균을 쓰면 하루 튄 값에
      끌려간다.
    """
    nums, bad, warn = [], [], []
    for tbl, col, _allow, label in SOURCES:
        rs = _all(c, f"""SELECT {col}::date d, COUNT(*) n FROM {tbl}
                          WHERE {col}::date > CURRENT_DATE - 60
                          GROUP BY 1 ORDER BY 1 DESC LIMIT 31""")
        if len(rs) < 10:
            continue
        last_d, last_n = rs[0]
        base = sorted(n for _, n in rs[1:])
        med = base[len(base) // 2]
        pct = last_n / med * 100 if med else 0
        nums.append((f"{label} 최신일 행수", f"{last_n:,} (기준선 {med:,} · {pct:.0f}%)"))
        if pct < 30:
            bad.append(f"{label} {pct:.0f}%")
        elif pct < 60:
            warn.append(f"{label} {pct:.0f}%")
    if bad:
        return Finding(BAD, "행수가 급감했습니다", " · ".join(bad), nums,
                       "원천이 일부만 왔을 수 있습니다. 수집 로그를 보고 다시 받으세요.")
    if warn:
        return Finding(WARN, "행수가 줄었습니다", " · ".join(warn), nums,
                       "휴장·연휴면 정상입니다. 개장일이면 확인하세요.")
    return Finding(OK, "행수", "최신일 행수가 기준선 안", nums)


def check_dup(c) -> Finding:
    """③ 중복 — 같은 자연키가 두 번 들어왔나.

    ★ **자연키를 확인 없이 적으면 오탐이 난다** (2026-09-03 실제로 겪음).

        경락가에서 `subclass_code` 를 빼먹어    1,068건 오탐
        소매가에서 `mrkt_cd`(점포) 를 빼먹어    1,323건 오탐

    소매 조사는 같은 날·같은 품목을 **여러 점포**에서 잽니다. 그게 정상입니다.
    경락가는 같은 규격 안에서도 **소분류**가 갈립니다.
    **잘못된 경보가 매일 뜨면 사람이 진짜 경보도 무시하게 됩니다.**

    적재 UNIQUE 제약과 같은 키를 씁니다 (`collect_kamis.py` 의
    UNIQUE (exmn_ymd, item_cd, vrty_cd, grd_cd, se_cd, sgg_cd, mrkt_cd, unit, unit_sz)).
    """
    checks = [
        ("경락가", """SELECT COUNT(*) FROM (
             SELECT auction_date, wholesale_market_code, item_code, grade_code,
                    package_code, unit_weight_kg, subclass_code, COUNT(*) k
               FROM auction_prices_daily
              WHERE auction_date > CURRENT_DATE - 30
              GROUP BY 1,2,3,4,5,6,7 HAVING COUNT(*) > 1) t"""),
        ("반입량", """SELECT COUNT(*) FROM (
             SELECT base_date, item_label, COUNT(*) k FROM daily_volume
              WHERE base_date > CURRENT_DATE - 30
              GROUP BY 1,2 HAVING COUNT(*) > 1) t"""),
        ("중도매·소매가", """SELECT COUNT(*) FROM (
             SELECT exmn_ymd, item_cd, vrty_cd, grd_cd, se_cd, sgg_cd,
                    mrkt_cd, unit, unit_sz, COUNT(*) k
               FROM veg_daily_price_raw
              WHERE exmn_ymd::date > CURRENT_DATE - 30
              GROUP BY 1,2,3,4,5,6,7,8,9 HAVING COUNT(*) > 1) t"""),
    ]
    nums, bad = [], []
    for label, sql in checks:
        try:
            n = int(_one(c, sql)[0])
        except Exception as e:                               # noqa: BLE001
            nums.append((f"{label} 중복", f"검사 못 함 ({type(e).__name__})"))
            continue
        nums.append((f"{label} 중복 키", f"{n:,}건"))
        if n:
            bad.append(f"{label} {n:,}건")
    if bad:
        return Finding(BAD, "같은 키가 두 번 들어왔습니다", " · ".join(bad), nums,
                       "합치면 물량이 두 배가 됩니다. 적재 UPSERT 조건을 보세요.")
    return Finding(OK, "중복", "최근 30일 중복 없음", nums)


def check_unit(c) -> Finding:
    """④ 단위 변화 — 가격 수준이 갑자기 몇 배로 뛰었나.

    원/kg 을 원/포장 으로 바꿔 넣는 사고가 실제로 흔하다. 그러면 값이
    10~20배가 된다. **최근 7일 중앙값 ÷ 그 앞 30일 중앙값**을 본다.
    """
    nums, bad, warn = [], [], []
    for it in ("배추", "무", "양파"):
        r = _one(c, """
          WITH d AS (
            SELECT auction_date::date dt,
                   SUM(trade_amount_krw)/NULLIF(SUM(trade_volume_kg),0) p
              FROM auction_prices_daily
             WHERE wholesale_market_code='110001' AND grade_code='11'
               AND item_name=%s AND trade_volume_kg > 0
               AND auction_date > CURRENT_DATE - 45
             GROUP BY 1)
          SELECT
            (SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY p) FROM d
              WHERE dt > CURRENT_DATE - 7),
            (SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY p) FROM d
              WHERE dt <= CURRENT_DATE - 7)""", (it,))
        if not r or r[0] is None or r[1] is None or not r[1]:
            continue
        ratio = float(r[0]) / float(r[1])
        nums.append((f"{it} 최근7일/그전30일", f"{ratio:.2f}배 "
                     f"({float(r[0]):,.0f} vs {float(r[1]):,.0f}원/kg)"))
        if ratio > 5 or ratio < 0.2:
            bad.append(f"{it} {ratio:.1f}배")
        elif ratio > 2.5 or ratio < 0.4:
            warn.append(f"{it} {ratio:.1f}배")
    if bad:
        return Finding(BAD, "가격 단위가 바뀐 것 같습니다", " · ".join(bad), nums,
                       "원/kg 을 원/포장 으로 넣었는지 보세요. 5배 넘는 변동은 시장이 아니라 단위입니다.")
    if warn:
        return Finding(WARN, "가격이 크게 움직였습니다", " · ".join(warn), nums,
                       "급등락이면 정상입니다. 단위 사고인지만 확인하세요.")
    return Finding(OK, "단위", "가격 수준이 평소 범위", nums)


def check_null(c) -> Finding:
    """⑤ 결측률 급증 — 기준선 대비 얼마나 늘었나.

    ★ 고정 문턱을 안 쓴다. `sumRn` 62.2% 는 정상이고
      `avgTa` 0% -> 30% 는 사고다. **그 컬럼의 평소와 견준다.**
    """
    cols = [("weather_asos_raw", "tm", "avgTa", "기상 평균기온"),
            ("weather_asos_raw", "tm", "sumRn", "기상 강수량"),
            ("auction_prices_daily", "auction_date", "unit_weight_kg", "경락 규격"),
            ("daily_volume", "base_date", "top1_region", "반입량 1위산지")]
    nums, bad, warn = [], [], []
    for tbl, dcol, col, label in cols:
        r = _one(c, f"""
          SELECT
            AVG(CASE WHEN "{col}" IS NULL THEN 1.0 ELSE 0 END)
              FILTER (WHERE {dcol}::date > CURRENT_DATE - 7),
            AVG(CASE WHEN "{col}" IS NULL THEN 1.0 ELSE 0 END)
              FILTER (WHERE {dcol}::date BETWEEN CURRENT_DATE - 90 AND CURRENT_DATE - 8)
          FROM {tbl} WHERE {dcol}::date > CURRENT_DATE - 90""")
        if not r or r[0] is None or r[1] is None:
            continue
        now, base = float(r[0]) * 100, float(r[1]) * 100
        nums.append((f"{label} 결측", f"최근7일 {now:.1f}% (평소 {base:.1f}%)"))
        #   ★ 절대 증가폭으로 본다. 평소 0.1% 가 0.3% 가 된 것은 사고가 아니다
        if now - base > 30:
            bad.append(f"{label} {base:.0f}% -> {now:.0f}%")
        elif now - base > 10:
            warn.append(f"{label} {base:.0f}% -> {now:.0f}%")
    if bad:
        return Finding(BAD, "결측이 크게 늘었습니다", " · ".join(bad), nums,
                       "그 컬럼을 쓰는 feature 가 비어 재생성하면 조용히 빈 값이 됩니다.")
    if warn:
        return Finding(WARN, "결측이 늘었습니다", " · ".join(warn), nums)
    return Finding(OK, "결측률", "평소 범위 안", nums)


def main() -> int:
    ap = argparse.ArgumentParser(description="수집 검사 — 재생성 전에 막는다")
    ap.add_argument("--quiet", action="store_true", help="정상이면 출력 생략")
    ap.add_argument("--warn-only", action="store_true",
                    help="이상이어도 0 으로 끝낸다 (배치를 안 멈춤)")
    a = ap.parse_args()

    rep = Report("수집검사")
    with db() as c:
        for fn in (check_lag, check_item_lag, check_rowcount,
                   check_dup, check_unit, check_null):
            try:
                rep.add(fn(c))
            except Exception as e:                           # noqa: BLE001
                #   ★ 검사가 죽어도 배치를 멈추지 않는다. 알리다 죽으면 본말전도다.
                rep.add(Finding(WARN, f"{fn.__name__} 검사 실패",
                                f"{type(e).__name__}: {e}"))
                #   ★★ 그리고 **반드시 롤백한다** (2026-09-03 실제로 겪음).
                #     PostgreSQL 은 한 트랜잭션에서 쿼리 하나가 실패하면 그 뒤
                #     쿼리를 전부 거부한다. 롤백을 안 하면 **검사 하나가 죽을 때
                #     나머지가 조용히 다 죽고**, 그런데도 "정상" 으로 찍힌다.
                #     오늘 그림자 실행이 자기 자신과 비교하면서 계속 "성공" 으로
                #     찍히던 것과 같은 종류다.
                try:
                    c.rollback()
                except Exception:                            # noqa: BLE001
                    pass
    #   ★ "검사가 돌았나" 가 아니라 "검사가 실제로 무엇을 봤나" 를 찍는다.
    #     근거 수치가 하나도 없는 검사는 아무것도 못 본 것이다.
    blind = [f.title for f in rep.findings if not f.numbers and f.level == OK]
    if blind:
        rep.add(Finding(WARN, "아무것도 못 본 검사가 있습니다",
                        " · ".join(blind),
                        [("못 본 검사", f"{len(blind)}개 / {len(rep.findings)}개")],
                        "정상이라서가 아니라 볼 자료가 없어서일 수 있습니다."))
    if not (a.quiet and rep.worst == OK):
        print(rep.text())
        s = narrate(rep)
        if s:
            print("[요약]")
            print(s)
    p = rep.save()
    print(f"[기록] {p}")
    return 0 if (a.warn_only or rep.worst != BAD) else 1


if __name__ == "__main__":
    raise SystemExit(main())
