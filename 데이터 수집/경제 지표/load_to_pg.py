# -*- coding: utf-8 -*-
"""
경제변수 CSV → econ_daily_raw 적재
===================================
`fetch_economic_variables.py` 가 만든 CSV 를 DB 에 넣는다.

    python load_to_pg.py output/economic_variables_daily.csv --check
    python load_to_pg.py output/economic_variables_daily.csv

컬럼 이름이 다르다
------------------
CSV 는 영문 서술형, 테이블은 축약형이다. 12개가 1:1 로 대응하므로
아래 MAP 이 유일한 진실이다. **한쪽만 바꾸면 조용히 어긋난다.**

재적재 안전
    `UNIQUE (dt)` 를 기준으로 `ON CONFLICT DO UPDATE` 한다.
    ECOS 는 **수정 후 시계열**을 준다 — 과거 값이 나중에 정정될 수 있으므로
    덮어쓰는 것이 맞다. 다만 덮어쓰기 전에 얼마나 달라지는지 보여준다.

이 데이터는 지금 모델이 쓰지 않는다
-----------------------------------
`m2_yoy_rt` · `epu_idx` · `ppi_idx` 는 ablation 에서 세 타겟 모두 손실이
음수라 제거됐다 (CLAUDE.md 5.2). 월·분기 단위로 갱신되어 일별 예측에서는
같은 값이 한 달간 반복되고, 모델이 이를 시점 식별자로 오용한다.
제거 후 `best_iter` 가 33~51 → 102~140 으로 3배 올랐다.

그래도 수집·적재한다 — 다른 파트가 쓸 수 있고, `--keep-all` 로 재실험할 때
최신 데이터가 있어야 한다. **다만 "수집했으니 feature 에 넣자" 로 이어지면
안 된다.** 넣으려면 2폴드 ablation 을 다시 통과해야 한다.
"""
import argparse
import csv
import os
import sys
from pathlib import Path

import psycopg

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

# CSV 컬럼 → DB 컬럼. 순서는 테이블 정의 순서를 따른다.
MAP = [
    ("date",                      "dt"),
    ("gov_bond_3y_pct",           "gov_bond_3y_rt"),
    ("gov_bond_observation_date", "gov_bond_obs_dt"),
    ("gov_bond_is_observed",      "gov_bond_obs_yn"),
    ("m2_yoy_pct",                "m2_yoy_rt"),
    ("m2_reference_month",        "m2_ref_mon"),
    ("epu_index",                 "epu_idx"),
    ("epu_reference_month",       "epu_ref_mon"),
    ("ppi_index_2020_100",        "ppi_idx"),
    ("ppi_reference_month",       "ppi_ref_mon"),
    ("cpi_yoy_pct",               "cpi_yoy_rt"),
    ("cpi_reference_month",       "cpi_ref_mon"),
]
NUM_DB = {"gov_bond_3y_rt", "m2_yoy_rt", "epu_idx", "ppi_idx", "cpi_yoy_rt"}
INT_DB = {"gov_bond_obs_yn"}
# 값이 달라졌는지 볼 때 쓰는 열 (기준월·관측일은 파생이라 뺀다)
CMP = ["gov_bond_3y_rt", "m2_yoy_rt", "epu_idx", "ppi_idx", "cpi_yoy_rt"]


def dsn():
    p = ROOT / ".env"
    if p.exists():
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


def load_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        sys.exit("빈 파일입니다: %s" % path)
    miss = [c for c, _ in MAP if c not in rows[0]]
    if miss:
        sys.exit("CSV 에 컬럼이 없습니다: %s\n"
                 "  fetch_economic_variables.py 가 만든 파일인지 확인하세요." % miss)

    out, bad = [], []
    for i, r in enumerate(rows, 2):
        rec = {}
        why = None
        for src, dst in MAP:
            v = (r.get(src) or "").strip()
            if dst in NUM_DB:
                try:
                    rec[dst] = float(v) if v else None
                except ValueError:
                    why = "%s=%r 숫자 아님" % (src, v)
            elif dst in INT_DB:
                try:
                    rec[dst] = int(float(v)) if v else None
                except ValueError:
                    why = "%s=%r 정수 아님" % (src, v)
            else:
                rec[dst] = v or None
        # 결측을 조용히 넣지 않는다. 수집기가 결측을 만들지 않도록 설계돼 있으므로
        # 여기서 NULL 이 나오면 CSV 가 잘못된 것이다.
        if not why:
            empty = [d for _, d in MAP if rec.get(d) is None]
            if empty:
                why = "결측 %s" % empty
        (bad.append((i, why)) if why else out.append(rec))
    return out, bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="?", default="output/economic_variables_daily.csv")
    ap.add_argument("--check", action="store_true", help="대조만 하고 쓰지 않는다")
    a = ap.parse_args()

    path = a.csv if os.path.isabs(a.csv) else os.path.join(HERE, a.csv)
    if not os.path.exists(path):
        sys.exit("CSV 가 없습니다: %s\n"
                 "  먼저 `python fetch_economic_variables.py` 를 돌리세요." % path)

    recs, bad = load_csv(path)
    print("[CSV] %s" % path)
    print("  정상 %d행 · 제외 %d행" % (len(recs), len(bad)))
    for i, why in bad[:8]:
        print("    %d행 — %s" % (i, why))
    if not recs:
        sys.exit("넣을 행이 없습니다.")
    ds = sorted(r["dt"] for r in recs)
    print("  범위 %s ~ %s" % (ds[0], ds[-1]))

    conn = psycopg.connect(dsn(), connect_timeout=25)
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*), MIN(dt), MAX(dt) FROM econ_daily_raw")
        n0, mn, mx = cur.fetchone()
        print("[DB] 현재 %d행 · %s ~ %s" % (n0, mn, mx))

        # 겹치는 구간 값 대조. ECOS 는 수정 후 시계열이라 과거가 바뀔 수 있다.
        cur.execute("SELECT dt, %s FROM econ_daily_raw WHERE dt = ANY(%%s)"
                    % ", ".join(CMP), (ds,))
        have = {r[0]: tuple(r[1:]) for r in cur.fetchall()}
        same = diff = 0
        samples = []
        for r in recs:
            if r["dt"] not in have:
                continue
            old = tuple(None if v is None else round(float(v), 6) for v in have[r["dt"]])
            new = tuple(None if r[c] is None else round(r[c], 6) for c in CMP)
            if old == new:
                same += 1
            else:
                diff += 1
                if len(samples) < 5:
                    samples.append((r["dt"], old, new))
        if have:
            print("[대조] 겹치는 %d행 · 일치 %d · 불일치 %d" % (same + diff, same, diff))
            for d, o, nw in samples:
                print("    %s" % d)
                print("        기존 %s" % (o,))
                print("        신규 %s" % (nw,))
            if diff:
                print("    ※ ECOS 는 수정 후 시계열입니다. 과거 값 정정은 정상이며 덮어씁니다.")
        else:
            print("[대조] 겹치는 구간 없음 (전부 신규)")
        print("  신규 %d행 · 갱신 %d행" % (len(recs) - len(have), len(have)))

        if a.check:
            print("\n--check 이므로 쓰지 않았습니다.")
            conn.close()
            return

        cols = [d for _, d in MAP]
        upd = [c for c in cols if c != "dt"]
        sql = ("INSERT INTO econ_daily_raw (%s) VALUES (%s) "
               "ON CONFLICT (dt) DO UPDATE SET %s"
               % (", ".join(cols), ", ".join(["%s"] * len(cols)),
                  ", ".join("%s = EXCLUDED.%s" % (c, c) for c in upd)))
        cur.executemany(sql, [[r[c] for c in cols] for r in recs])
        conn.commit()

        cur.execute("SELECT COUNT(*), COUNT(DISTINCT dt), MIN(dt), MAX(dt) FROM econ_daily_raw")
        n1, dcnt, mn, mx = cur.fetchone()
        print("\n적재 완료 — 신규 %d행" % (n1 - n0))
        print("  econ_daily_raw %d행 · 고유일 %d · %s ~ %s" % (n1, dcnt, mn, mx))
        if n1 != dcnt:
            print("  [경고] 행수와 고유일이 다릅니다. UNIQUE 제약을 확인하세요.")
    conn.close()


if __name__ == "__main__":
    main()
