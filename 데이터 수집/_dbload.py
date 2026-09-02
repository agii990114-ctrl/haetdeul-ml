# -*- coding: utf-8 -*-
"""
수집기 공용 DB 적재
====================
수집기가 만든 행을 **CSV 를 거치지 않고** 바로 DB 에 넣는다.

    import sys; sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    import _dbload
    _dbload.upsert("weather_asos_raw", cols, rows,
                   conflict='("stnId", tm)', compare=["avgTa", "minTa"])

왜 CSV 를 빼나
--------------
CSV 는 **타입을 지운다.** 그리고 로더가 그걸 손으로 복원한다.

    빈 문자열 → NULL      기상 sumRn (무강수일)
    "1718.0"  → int       반입량 total_ton
    "0"       ≠ NULL      0 과 결측은 다르다

복원 규칙이 한 글자만 틀려도 조용히 틀린다. 파이썬에서 바로 넣으면
`None` 은 `None` 이고 `int` 는 `int` 다. 인코딩(utf-8-sig · cp949) 문제도 사라진다.

CSV 자체가 필요한 곳은 남긴다 — 반입량 `raw.jsonl`(25분 스크래핑 이어받기),
경락가 배포본(팀에 넘기는 산출물). **파이프라인 중간 산출물만 없앤다.**

대조 검증은 그대로
------------------
겹치는 구간을 값까지 비교하는 것이 이 프로젝트의 규율이다. 원천이 값을
정정했거나 파싱이 달라지면 **경계를 기준으로 성격이 다른 데이터가 이어붙고**,
모델은 그 경계를 시점으로 학습한다. `compare` 에 열을 주면 넣기 전에 잰다.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def dsn():
    """루트 .env 의 DATABASE_URL."""
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


def _q(c):
    """대소문자 섞인 컬럼(ASOS 의 stnId 등)은 따옴표가 필요하다."""
    return c if c.islower() else '"%s"' % c


def upsert(table, cols, rows, conflict, key_cols=None, compare=None,
           do_update=False, check=False, label=None):
    """행 목록을 표에 넣는다.

    table     대상 테이블
    cols      컬럼 이름 목록 (rows 의 각 항목과 순서가 같아야 함)
    rows      list[list] 또는 list[tuple]. **파이썬 타입 그대로** 넣는다
    conflict  ON CONFLICT 대상. '(dt)' 또는 'ON CONSTRAINT uq_...'
    key_cols  대조에 쓸 키 컬럼 (compare 를 줄 때 필요)
    compare   겹치는 구간에서 값까지 비교할 컬럼. 생략하면 건수만 본다
    do_update 겹치는 행을 덮어쓸지. 기본은 건너뜀(DO NOTHING)
    check     True 면 대조만 하고 쓰지 않는다

    반환: (신규건수, 갱신후보건수, 불일치건수)
    """
    import psycopg

    name = label or table
    if not rows:
        print("  [%s] 넣을 행이 없습니다." % name)
        return 0, 0, 0

    conn = psycopg.connect(dsn(), connect_timeout=30)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM %s" % table)
            n0 = cur.fetchone()[0]

            same = diff = 0
            overlap = 0
            if compare and key_cols:
                ki = [cols.index(c) for c in key_cols]
                ci = [cols.index(c) for c in compare]
                keys = [tuple(r[i] for i in ki) for r in rows]
                # 키 조합을 그대로 IN 으로 넣는다 (컬럼 수만큼 unnest)
                arrs = list(zip(*keys)) if keys else []
                sel = ", ".join(_q(c) for c in key_cols + compare)
                # unnest 는 타입을 못 정하면 "not unique" 로 실패한다.
                # 키 컬럼의 실제 타입을 읽어 캐스트를 붙인다.
                cur.execute(
                    """SELECT a.attname, format_type(a.atttypid, -1)
                       FROM pg_attribute a JOIN pg_class c ON c.oid = a.attrelid
                       JOIN pg_namespace n ON n.oid = c.relnamespace
                       WHERE n.nspname='public' AND c.relname=%s
                         AND a.attname = ANY(%s)""", (table, list(key_cols)))
                kt = dict(cur.fetchall())
                un = ", ".join("unnest(%%s::%s[])" % kt.get(c, "text")
                               for c in key_cols)
                cur.execute(
                    "SELECT %s FROM %s WHERE (%s) IN (SELECT %s)"
                    % (sel, table, ", ".join(_q(c) for c in key_cols), un),
                    [list(a) for a in arrs])
                have = {tuple(r[:len(key_cols)]): r[len(key_cols):]
                        for r in cur.fetchall()}
                samples = []
                for r in rows:
                    k = tuple(r[i] for i in ki)
                    if k not in have:
                        continue
                    overlap += 1
                    old = tuple(_norm(v) for v in have[k])
                    new = tuple(_norm(r[i]) for i in ci)
                    if old == new:
                        same += 1
                    else:
                        diff += 1
                        if len(samples) < 8:
                            samples.append((k, have[k], [r[i] for i in ci]))
                if overlap:
                    print("  [%s] 겹치는 %d행 · 일치 %d · 불일치 %d"
                          % (name, overlap, same, diff))
                    # 건수만 찍으면 무엇이 달라졌는지 알 수 없어 매번 손으로 캐야 한다.
                    for k, o, n in samples:
                        print("      %s  기존 %s → 신규 %s"
                              % (" ".join(str(x) for x in k), list(o), n))
                    if diff > len(samples):
                        print("      … 외 %d건" % (diff - len(samples)))
                else:
                    print("  [%s] 겹치는 구간 없음 (전부 신규)" % name)

            if check:
                print("  [%s] --check 이므로 쓰지 않았습니다." % name)
                return 0, overlap, diff

            act = ("DO UPDATE SET " +
                   ", ".join("%s = EXCLUDED.%s" % (_q(c), _q(c))
                             for c in cols if c not in (key_cols or []))
                   ) if do_update else "DO NOTHING"
            sql = ("INSERT INTO %s (%s) VALUES (%s) ON CONFLICT %s %s"
                   % (table, ", ".join(_q(c) for c in cols),
                      ", ".join(["%s"] * len(cols)), conflict, act))
            cur.executemany(sql, rows)
            conn.commit()

            cur.execute("SELECT COUNT(*) FROM %s" % table)
            n1 = cur.fetchone()[0]
        print("  [%s] 신규 %d행 · 표 전체 %s행" % (name, n1 - n0, format(n1, ",")))
        return n1 - n0, overlap, diff
    finally:
        conn.close()


def _norm(v):
    """대조용 정규화. Decimal·float·str 을 같은 잣대로 본다."""
    if v is None:
        return None
    try:
        return round(float(v), 6)
    except (TypeError, ValueError):
        return str(v).strip()
