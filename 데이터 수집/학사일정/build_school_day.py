# -*- coding: utf-8 -*-
"""
ref_school_day — 서울 학사일정(급식 수요 대리변수) 생성
=======================================================
NEIS 학사일정 원본 CSV 를 서울 초·중·고 일별 개교율로 집계하고,
연중 프로파일을 유도해 2015~2028 전 구간을 생성한다.

    python build_school_day.py            # 집계 + 프로파일 + SQL 생성
    python build_school_day.py --check    # 검증만 (파일 안 씀)

왜 실측을 그대로 안 쓰는가
--------------------------
NEIS 학사일정 개방일이 2019-04-01 이고 API 는 최근 2개 학년도만 보유한다.
실측은 2020-09 부터라 학습 구간(2017~2022)의 커버리지가 36.6% 에 그친다.
결측을 그대로 두면 "2020-09 이전인가" 라는 시점 식별자가 되어,
경제 변수를 제거한 것과 같은 과적합을 부른다 (CLAUDE.md 5.2).

그래서 실측 5년으로 (월,일) 중앙값 프로파일을 만들고 전 구간에 같은 규칙을
적용한다. 전 구간이 같은 성격이 되고, 배치에서 미래 리드타임도 채울 수 있다.
leave-one-year-out 검증에서 MAE 0.057 · 급식일 이진 일치 94.6% 였다.

집계 기준
---------
분모  서울(B10) 초·중·고 학교 수 (전 기간 등장 학교의 합집합)
분자  수업공제일명 ∈ {휴업일, 공휴일} 인 학교 수 (중복 제거)
      → school_open_ratio = 1 − 분자/분모

프로파일 산출 시 제외
    토·일       NEIS 는 일요일에 휴업일 행을 만들지 않아 "개교" 로 잡힌다.
                실측 일요일 중앙값이 0.995 다. 조사 축(target_dt)은 월~금뿐이라
                실무 영향은 없지만 프로파일이 오염되므로 뺀다.
    공휴일      ref_holiday 기준. 공휴일 휴교는 ref_calendar 가 이미 담당한다.
                학사일정이 새로 주는 정보는 여름·겨울방학뿐이다.

원본의 한계 (그대로 안고 간다)
    파일명과 내용이 어긋난 것이 있다. "2024년10월" 이 10/09~11/08 을 담는 식으로
    31일 창으로 받은 흔적이고, 이어붙여도 8곳 45일이 빈다. 프로파일은 연도별
    중앙값이라 이 구멍의 영향을 거의 받지 않는다.
"""
import argparse
import collections
import csv
import datetime
import glob
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SRC_DIR = os.path.join(ROOT, "DB", "데이터", "학사일정")
HOLIDAY_CSV = os.path.join(ROOT, "데이터 수집", "휴일 달력", "ref_holiday.csv")
OUT_CSV = os.path.join(HERE, "ref_school_day.csv")
MEAS_CSV = os.path.join(HERE, "ref_school_day_meas.csv")
OUT_SQL = os.path.join(ROOT, "SQL", "29_ref_school_day.sql")

CLOSED_KIND = {"휴업일", "공휴일"}
LEVELS = {"초등학교", "중학교", "고등학교"}
SEOUL = "B10"
SPAN = (datetime.date(2015, 1, 1), datetime.date(2028, 12, 31))

# 원본 컬럼 위치
#   헤더 이름이 파일마다 '표준학교코드' / '행정표준코드' 로 갈려서 위치로 읽는다.
C_OFC, C_SCHUL, C_LEVEL, C_KIND, C_YMD = 0, 2, 6, 7, 8

FIXED_MD = {(1, 1), (3, 1), (5, 5), (6, 6), (8, 15), (10, 3), (10, 9), (12, 25)}


def load_holidays():
    """ref_holiday 의 공휴일 집합. 없으면 양력 고정 공휴일로 대체한다."""
    if not os.path.exists(HOLIDAY_CSV):
        print("  [주의] ref_holiday.csv 가 없어 양력 고정 공휴일만 씁니다.")
        return None
    days = set()
    with open(HOLIDAY_CSV, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if str(r.get("is_holiday", "")).strip() in ("Y", "true", "True", "1"):
                days.add(datetime.date.fromisoformat(r["dt"].strip()))
    return days


def eligible(d, holidays):
    """프로파일 산출 대상인가 — 평일이고 공휴일이 아닌 날"""
    if d.weekday() >= 5:
        return False
    if holidays is None:
        return (d.month, d.day) not in FIXED_MD
    return d not in holidays


def aggregate():
    """원본 CSV → ({date: open_ratio}, 학교 수, 파일 수)"""
    files = sorted(glob.glob(os.path.join(SRC_DIR, "*.csv")))
    if not files:
        sys.exit("원본이 없습니다: %s" % SRC_DIR)
    closed = collections.defaultdict(set)
    seen = collections.defaultdict(set)
    schools = set()
    for fp in files:
        with open(fp, encoding="cp949", errors="replace", newline="") as f:
            rd = csv.reader(f)
            next(rd, None)
            for row in rd:
                if len(row) <= C_YMD:
                    continue
                if row[C_OFC].strip() != SEOUL or row[C_LEVEL].strip() not in LEVELS:
                    continue
                ymd = row[C_YMD].strip()
                if len(ymd) != 8 or not ymd.isdigit():
                    continue
                d = datetime.date(int(ymd[:4]), int(ymd[4:6]), int(ymd[6:]))
                sc = row[C_SCHUL].strip()
                schools.add(sc)
                seen[d].add(sc)
                if row[C_KIND].strip() in CLOSED_KIND:
                    closed[d].add(sc)
    n = len(schools)
    meas = {d: round(1 - len(closed[d]) / n, 4) for d in seen}
    return meas, n, len(files)


def build_profile(meas, holidays):
    """평일·비공휴일 실측 → (월,일) 중앙값 프로파일"""
    pool = collections.defaultdict(list)
    for d, v in meas.items():
        if eligible(d, holidays):
            pool[(d.month, d.day)].append(v)
    prof = {k: round(statistics.median(v), 4) for k, v in pool.items()}
    # 2/29 는 4년에 한 번뿐이라 표본이 없거나 1개다. 그럴 때 2/28 을 쓴다.
    if len(pool.get((2, 29), [])) < 2 and (2, 28) in prof:
        prof[(2, 29)] = prof[(2, 28)]
    return prof, {k: len(v) for k, v in pool.items()}


def validate(meas, holidays):
    """leave-one-year-out — 해당 연도를 빼고 만든 프로파일로 그 해를 맞춘다"""
    W = {d: v for d, v in meas.items() if eligible(d, holidays)}
    rows = []
    for y in sorted({d.year for d in W}):
        pool = collections.defaultdict(list)
        for d, v in W.items():
            if d.year != y:
                pool[(d.month, d.day)].append(v)
        P = {k: statistics.median(v) for k, v in pool.items()}
        act, pre = [], []
        for d, v in sorted(W.items()):
            if d.year == y and (d.month, d.day) in P:
                act.append(v)
                pre.append(P[(d.month, d.day)])
        if len(act) < 20:
            continue
        mae = sum(abs(a - p) for a, p in zip(act, pre)) / len(act)
        agree = sum((a >= .5) == (p >= .5) for a, p in zip(act, pre)) / len(act)
        rows.append((y, len(act), mae, agree))
    return rows


def nearest(prof, d):
    """프로파일에 (월,일)이 없을 때 앞뒤 가장 가까운 날의 평균으로 채운다.

    양력 고정 공휴일(1/1, 3/1, 5/5 …)은 프로파일 산출에서 제외되므로 여기 걸린다.
    1.0(개교)으로 두면 겨울방학 한복판인 신정이 만개교로 보이는 오해를 부른다.
    한쪽만 보면 편향된다 — 신정을 12/31 값만으로 채우면 0.73 이 나오는데,
    12/31 이 겨울방학 시작 경계라 해마다 갈리기 때문이다. 앞뒤를 함께 쓴다.
    윤년 문제를 피하려고 2000년(윤년) 기준으로 날짜를 옮겨 이웃을 찾는다.
    """
    base = datetime.date(2000, d.month, d.day)
    side = []
    for s in (-1, 1):
        for off in range(1, 15):
            k = base + datetime.timedelta(days=off * s)
            if (k.month, k.day) in prof:
                side.append(prof[(k.month, k.day)])
                break
    return round(sum(side) / len(side), 4) if side else 1.0


def span_dates():
    d, end = SPAN
    while d <= end:
        yield d
        d += datetime.timedelta(days=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="검증만 하고 파일은 쓰지 않는다")
    a = ap.parse_args()

    holidays = load_holidays()
    meas, n_school, n_file = aggregate()
    print("[집계] 원본 %d개 · 서울 초·중·고 %d교 · 수록일 %d일 (%s ~ %s)"
          % (n_file, n_school, len(meas), min(meas), max(meas)))

    ds = sorted(meas)
    gaps = [(x, y, (y - x).days - 1) for x, y in zip(ds, ds[1:]) if (y - x).days > 1]
    print("[구멍] %d곳 %d일 — 프로파일은 연도별 중앙값이라 영향이 작다"
          % (len(gaps), sum(g[2] for g in gaps)))
    for x, y, k in gaps:
        print("        %s → %s (%d일)" % (x, y, k))

    prof, cnt = build_profile(meas, holidays)
    thin = [k for k, v in cnt.items() if v < 3]
    print("[프로파일] (월,일) %d개 · 표본 3개 미만 %d개" % (len(prof), len(thin)))

    print()
    print("[검증] leave-one-year-out")
    print("  %-8s %5s %8s %10s" % ("연도", "n", "MAE", "급식일일치"))
    rows = validate(meas, holidays)
    tn = sum(r[1] for r in rows)
    for y, k, mae, agree in rows:
        print("  %-8d %5d %8.4f %9.1f%%" % (y, k, mae, agree * 100))
    mae_w = sum(r[2] * r[1] for r in rows) / tn
    agr_w = 100 * sum(r[3] * r[1] for r in rows) / tn
    print("  %-8s %5d %8.4f %9.1f%%" % ("가중평균", tn, mae_w, agr_w))
    if agr_w < 90:
        print("  [경고] 이진 일치율이 90%% 아래입니다. 프로파일을 그대로 쓰지 마세요.")

    if a.check:
        print()
        print("--check 이므로 파일은 쓰지 않았습니다.")
        return

    out = []
    filled = collections.Counter()
    for d in span_dates():
        v = prof.get((d.month, d.day))
        if v is None:
            v = nearest(prof, d)
            filled[(d.month, d.day)] += 1
        out.append((d, v, meas.get(d)))
    if filled:
        # 양력 고정 공휴일은 프로파일 산출에서 빠지므로 여기 걸린다.
        # 조사 축(target_dt)에는 공휴일이 없어 모델은 이 값을 보지 않지만,
        # 이 테이블은 다른 파트에 넘기는 기준정보라 1.0(개교)로 두면 오해를 부른다.
        print("  [보간] 프로파일에 없는 (월,일) %d개 → 앞뒤 가장 가까운 날 값으로 채움: %s"
              % (len(filled), ", ".join("%d/%d" % k for k in sorted(filled))))

    with open(OUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["dt", "school_open_ratio", "school_open_ratio_meas"])
        for d, v, m in out:
            w.writerow([d.isoformat(), v, "" if m is None else m])

    with open(MEAS_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["dt", "school_open_ratio_meas"])
        for d in sorted(meas):
            w.writerow([d.isoformat(), meas[d]])

    with open(OUT_SQL, "w", encoding="utf-8", newline="\n") as f:
        f.write(SQL_HEAD % (n_file, n_school, min(meas), max(meas), mae_w, agr_w))
        f.write("INSERT INTO ref_school_day (dt, school_open_ratio, school_open_ratio_meas) VALUES\n")
        f.write(",\n".join(
            "  ('%s', %.4f, %s)" % (d.isoformat(), v, "NULL" if m is None else "%.4f" % m)
            for d, v, m in out))
        f.write(";\n")
        f.write(SQL_TAIL)

    print()
    print("생성: %s  (%d행)" % (OUT_CSV, len(out)))
    print("생성: %s  (실측 %d행)" % (MEAS_CSV, len(meas)))
    print("생성: %s" % OUT_SQL)


SQL_HEAD = """-- ============================================================
-- ref_school_day — 서울 학사일정(급식 수요 대리변수) 2015~2028
--   출처: NEIS 학사일정 (open.neis.go.kr) 원본 CSV %d개 · 서울 초·중·고 %d교
--   생성: 데이터 수집/학사일정/build_school_day.py — 손으로 고치지 말고 재생성할 것
--
--   school_open_ratio       연중 프로파일. 전 구간 동일 규칙. ★ 모델 입력은 이 컬럼
--   school_open_ratio_meas  실측. %s ~ %s 만 존재. 참고·검증용, 학습에 쓰지 말 것
--
--   왜 실측을 안 쓰나
--     NEIS 개방일이 2019-04 이고 API 는 최근 2개 학년도만 보유한다. 실측은
--     2020-09 부터라 학습 구간(2017~2022) 커버리지가 36.6%%다. 결측을 그대로
--     두면 "2020-09 이전인가" 라는 시점 식별자가 되어 경제 변수와 같은
--     과적합을 부른다 (CLAUDE.md 5.2). 그래서 실측 5년으로 (월,일) 중앙값
--     프로파일을 만들어 전 구간에 같은 규칙을 적용했다.
--     leave-one-year-out: MAE %.4f · 급식일 이진 일치 %.1f%%
--
--   집계 기준
--     분모  서울(B10) 초·중·고 (전 기간 등장 학교 합집합)
--     분자  수업공제일명 이 {휴업일, 공휴일} 인 학교 수
--     프로파일 산출 시 토·일과 공휴일 제외
--       - NEIS 는 일요일에 휴업일 행을 만들지 않아 "개교"로 잡힌다 (실측 중앙값 0.995)
--       - 공휴일 휴교는 ref_calendar 가 이미 담당한다
--     즉 학사일정이 새로 주는 정보는 여름·겨울방학뿐이다
--
--   양력 고정 공휴일 8일(1/1 3/1 5/5 6/6 8/15 10/3 10/9 12/25)은 프로파일 산출에서
--   빠지므로 앞뒤 값의 평균으로 보간했다. 조사 축(target_dt)에는 공휴일이 없어
--   모델은 이 값을 보지 않는다. 이 날짜의 값을 근거로 삼지 말 것.
--
--   실행 순서
--     ref_holiday.sql → 25_ref_calendar.sql → 이 파일 → DBEAVER_run_v5.sql
--     v5 가 맨 앞에서 crop_price_train 을 TRUNCATE 하지만 이 테이블은 건드리지
--     않는다. 다만 v5 가 이 테이블을 조인하므로 v5 보다 먼저 있어야 한다.
-- ============================================================
CREATE TABLE IF NOT EXISTS ref_school_day (
    dt                      date            NOT NULL PRIMARY KEY,
    school_open_ratio       numeric(6,4)    NOT NULL,
    school_open_ratio_meas  numeric(6,4)
);
COMMENT ON TABLE ref_school_day IS
  '서울 초·중·고 개교율(급식 수요 대리변수). 연중 프로파일 기반. build_school_day.py 로 재생성';
COMMENT ON COLUMN ref_school_day.school_open_ratio IS
  '연중 프로파일 개교율 0~1. 전 구간 동일 규칙이라 미래 리드타임에도 값이 있다. 모델 입력은 이 컬럼';
COMMENT ON COLUMN ref_school_day.school_open_ratio_meas IS
  'NEIS 실측 개교율. 2020-09 이후만 존재. 참고·검증용 — 학습에 쓰면 결측이 시점 식별자가 된다';

TRUNCATE ref_school_day;
"""

SQL_TAIL = """
-- ── 검증 ────────────────────────────────────────────────────
-- [1] 행수·범위
SELECT COUNT(*) AS 행수, MIN(dt) AS 시작, MAX(dt) AS 끝,
       COUNT(school_open_ratio_meas) AS 실측행
FROM ref_school_day;

-- [2] 프로파일 vs 실측 — 급식일(>=0.5) 이진 일치율
--     조사 축(월~금·비공휴일)에서만 본다. 90% 아래면 프로파일을 다시 만들 것
SELECT ROUND(AVG(CASE WHEN (school_open_ratio >= 0.5) = (school_open_ratio_meas >= 0.5)
                      THEN 1 ELSE 0 END) * 100, 1) AS 일치율_pct,
       COUNT(*) AS 대조행
FROM ref_school_day s
JOIN ref_calendar c ON c.dt = s.dt AND c.is_survey
WHERE s.school_open_ratio_meas IS NOT NULL;

-- [3] 월별 프로파일 — 1~2월·8월이 낮고 3~6월·9~11월이 높아야 한다
SELECT EXTRACT(MONTH FROM dt)::int AS 월,
       ROUND(AVG(school_open_ratio), 3) AS 평균개교율
FROM ref_school_day
WHERE EXTRACT(DOW FROM dt) BETWEEN 1 AND 5
GROUP BY 1 ORDER BY 1;
"""


if __name__ == "__main__":
    main()
