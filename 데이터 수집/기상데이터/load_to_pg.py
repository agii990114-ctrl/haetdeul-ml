# -*- coding: utf-8 -*-
"""
ASOS CSV → weather_asos_raw 적재
=================================
`fetch_asos.py` 가 만든 CSV 를 DB 에 넣는다.

    python load_to_pg.py asos_daily_20260101_20260824.csv --check
    python load_to_pg.py asos_daily_20260101_20260824.csv

컬럼 목록을 명시해 넣는다
-------------------------
CSV 열 순서와 테이블 열 순서가 지금은 같지만(`fetch_asos.py` 의 계약 점검 7번),
**셋 중 하나만 바뀌어도 조용히 깨지는 종류의 일치**다. 목록 없는 COPY 는
기온 자리에 강수량이 들어가도 예외를 내지 않는다. 그래서 목록을 준다.

빈 문자열은 NULL 로
-------------------
API 는 무강수일에 `sumRn` 을 빈 문자열로 준다. 숫자 컬럼에 `''` 는 못 넣으므로
NULL 로 바꾼다. **0 과 빈값은 다르다** — 0 은 "쟀는데 0", 빈값은 "안 쟀다" 이므로
0 을 NULL 로 바꾸거나 그 반대로 하면 안 된다. 여기서는 빈값만 손댄다.

재적재 안전
-----------
`UNIQUE ("stnId", tm)` 이 있어 `ON CONFLICT DO NOTHING` 으로 넣는다.
같은 구간을 다시 받아도 중복이 쌓이지 않으므로 겹치게 받아도 된다.
"""
import argparse
import csv
import os
import sys
from pathlib import Path

import psycopg

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent

# 숫자·시각 컬럼. 빈 문자열이 오면 NULL 로 바꾼다.
# stnId · stnNm · tm · iscs 는 문자열이므로 건드리지 않는다.
TEXT_COLS = {"stnId", "stnNm", "tm", "iscs"}


def dsn():
    for p in (HERE / ".env", ROOT / ".env"):
        if not p.exists():
            continue
        for raw in p.read_text(encoding="utf-8-sig").splitlines():
            line = raw.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                v = v.strip()
                if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                    v = v[1:-1]
                os.environ.setdefault(k.strip(), v)
    u = os.environ.get("DATABASE_URL")
    if not u:
        sys.exit(".env 에 DATABASE_URL 이 없습니다.")
    return u


def db_columns(cur):
    cur.execute("""SELECT a.attname FROM pg_attribute a
                   JOIN pg_class c ON c.oid = a.attrelid
                   JOIN pg_namespace n ON n.oid = c.relnamespace
                   WHERE n.nspname='public' AND c.relname='weather_asos_raw'
                     AND a.attnum > 0 AND NOT a.attisdropped
                   ORDER BY a.attnum""")
    return [r[0] for r in cur.fetchall()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--check", action="store_true", help="대조만 하고 쓰지 않는다")
    a = ap.parse_args()

    if not os.path.exists(a.csv):
        sys.exit("CSV 가 없습니다: %s" % a.csv)

    with open(a.csv, encoding="utf-8-sig", newline="") as f:
        rd = csv.reader(f)
        header = next(rd)
        rows = list(rd)
    print("[CSV] %s" % a.csv)
    print("  %d행 · %d열" % (len(rows), len(header)))
    if not rows:
        sys.exit("행이 없습니다.")

    conn = psycopg.connect(dsn(), connect_timeout=25)
    with conn.cursor() as cur:
        dbc = db_columns(cur)

        # CSV 에 있는데 테이블에 없는 열은 넣을 수 없다. 조용히 버리지 않고 알린다.
        unknown = [c for c in header if c not in dbc]
        if unknown:
            print("  [주의] 테이블에 없는 열 %s — 적재에서 제외합니다" % unknown)
            print("         API 가 명세 밖 필드를 주기 시작한 것일 수 있습니다.")
        cols = [c for c in header if c in dbc]
        idx = [header.index(c) for c in cols]

        # 기간·지점 요약
        i_tm, i_stn = header.index("tm"), header.index("stnId")
        ds = sorted({r[i_tm] for r in rows})
        print("  기간 %s ~ %s · 지점 %d개" % (ds[0], ds[-1], len({r[i_stn] for r in rows})))

        cur.execute('SELECT COUNT(*), MIN(tm), MAX(tm) FROM weather_asos_raw')
        n0, mn, mx = cur.fetchone()
        print("[DB] 현재 %d행 · %s ~ %s" % (n0, mn, mx))

        # 겹치는 구간이 있으면 값까지 대조한다.
        #   같은 API 에서 받은 값이 다르면 관측이 정정됐거나 파싱이 달라진 것이다.
        cur.execute('''SELECT "stnId", tm, "avgTa"::text, "minTa"::text, "maxTa"::text
                       FROM weather_asos_raw WHERE tm = ANY(%s)''', (ds,))
        have = {(s, t): (a1, b1, c1) for s, t, a1, b1, c1 in cur.fetchall()}
        if have:
            ia, ib, ic = (header.index(x) for x in ("avgTa", "minTa", "maxTa"))
            same = diff = 0
            samples = []
            for r in rows:
                k = (r[i_stn], r[i_tm])
                if k not in have:
                    continue
                old = have[k]
                new = tuple(r[i] if r[i] != "" else None for i in (ia, ib, ic))
                oldn = tuple(None if v is None else str(float(v)) for v in old)
                newn = tuple(None if v is None else str(float(v)) for v in new)
                if oldn == newn:
                    same += 1
                else:
                    diff += 1
                    if len(samples) < 5:
                        samples.append((k, old, new))
            print("[대조] 겹치는 %d행 · 일치 %d · 불일치 %d" % (same + diff, same, diff))
            for k, old, new in samples:
                print("    %s %s  기존 %s → 신규 %s" % (k[0], k[1], old, new))
        else:
            print("[대조] 겹치는 구간 없음 (전부 신규)")

        if a.check:
            print("\n--check 이므로 쓰지 않았습니다.")
            conn.close()
            return

        # 빈 문자열 → NULL. 0 은 그대로 둔다 (0 과 결측은 다르다).
        payload = []
        for r in rows:
            v = []
            for c, i in zip(cols, idx):
                x = r[i] if i < len(r) else ""
                v.append(x if (c in TEXT_COLS or x != "") else None)
            payload.append(v)

        sql = ('INSERT INTO weather_asos_raw (%s) VALUES (%s) '
               'ON CONFLICT ("stnId", tm) DO NOTHING'
               % (", ".join('"%s"' % c for c in cols),
                  ", ".join(["%s"] * len(cols))))
        cur.executemany(sql, payload)
        conn.commit()

        cur.execute('SELECT COUNT(*), MIN(tm), MAX(tm), COUNT(DISTINCT "stnId") '
                    'FROM weather_asos_raw')
        n1, mn, mx, ns = cur.fetchone()
        print("\n적재 완료 — 신규 %d행" % (n1 - n0))
        print("  weather_asos_raw %d행 · %s ~ %s · 지점 %d개" % (n1, mn, mx, ns))
    conn.close()


if __name__ == "__main__":
    main()
