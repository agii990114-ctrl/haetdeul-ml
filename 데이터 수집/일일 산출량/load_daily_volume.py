# -*- coding: utf-8 -*-
"""
농넷 반입량 → daily_volume 적재
================================
`농넷에서 일일산출량 적재.py merge` 가 만든 CSV 를 DB 에 넣는다.

    python load_daily_volume.py --csv ./nongnet_chart/daily_volume.csv --check
    python load_daily_volume.py --csv ./nongnet_chart/daily_volume.csv

기본은 **겹치는 구간을 먼저 대조하고, 새 행만 넣는다.**
기존 행은 건드리지 않는다 (`--update` 를 줘야 덮어쓴다).

왜 대조를 먼저 하나
-------------------
기존 daily_volume 은 같은 스크래퍼로 2014-12~2025-12 를 받아 넣은 것이다.
지금 다시 긁은 값이 그때와 다르면, 2025-12-31 을 경계로 **성격이 다른 데이터가
이어붙는다.** 모델은 그 경계를 "시점" 으로 학습할 수 있고, 그건 예외가 아니라
조용한 성능 저하로 나타난다.

농넷은 수급일보라 나중에 값이 정정될 수 있다. 그래서 불일치가 나오는 것
자체는 이상하지 않지만, **얼마나 어긋나는지 모르고 넣는 것**이 문제다.
이 스크립트는 겹치는 구간의 불일치율을 먼저 보여주고, 임계를 넘으면 멈춘다.

컬럼 매핑
---------
    CSV          daily_volume
    ymd       →  base_date      PK(1)
    item      →  item_label     PK(2)
    req_date  →  req_date       CHECK req_date >= base_date
    나머지 6개   동일

`top1_raw` · `top2_raw` 는 merge CSV 에 없다. 새 행은 NULL 로 들어가고,
기존 행은 (--update 를 줘도) 덮어쓰지 않는다 — 있는 정보를 지울 이유가 없다.

DB 제약 (위반하면 적재 자체가 실패한다)
    total_ton · top1_ton · top2_ton · etc_ton  >= 0 이고 NOT NULL
    top1_ton >= top2_ton
    req_date >= base_date
넣기 전에 같은 조건을 파이썬에서 먼저 걸러 어느 행이 왜 걸리는지 보여준다.
"""
import argparse
import csv
import datetime
import os
import sys
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parent.parent.parent
COLS = ["base_date", "item_label", "total_ton", "top1_region", "top1_ton",
        "top2_region", "top2_ton", "etc_ton", "req_date"]
NUM = ["total_ton", "top1_ton", "top2_ton", "etc_ton"]


def dsn():
    for raw in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
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
    """CSV → 레코드. 제약 위반은 걸러서 따로 돌려준다."""
    ok, bad = [], []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            try:
                rec = {
                    "base_date": datetime.date.fromisoformat(r["ymd"].strip()),
                    "item_label": r["item"].strip(),
                    "req_date": datetime.date.fromisoformat(r["req_date"].strip()),
                    "top1_region": (r.get("top1_region") or "").strip() or None,
                    "top2_region": (r.get("top2_region") or "").strip() or None,
                }
                for c in NUM:
                    v = (r.get(c) or "").strip()
                    # 스크래퍼가 1718.0 처럼 실수로 준다. 컬럼은 integer 다.
                    rec[c] = None if v == "" else int(round(float(v)))
            except (ValueError, KeyError, TypeError) as e:
                bad.append((r, "파싱 실패: %s" % e))
                continue
            why = violation(rec)
            (bad.append((rec, why)) if why else ok.append(rec))
    return ok, bad


def violation(r):
    """DB CHECK 와 같은 조건을 미리 건다."""
    for c in NUM:
        if r[c] is None:
            return "%s 가 NULL (컬럼은 NOT NULL)" % c
        if r[c] < 0:
            return "%s 가 음수 (%s)" % (c, r[c])
    if r["top1_ton"] < r["top2_ton"]:
        return "top1_ton(%s) < top2_ton(%s)" % (r["top1_ton"], r["top2_ton"])
    if r["req_date"] < r["base_date"]:
        return "req_date(%s) < base_date(%s)" % (r["req_date"], r["base_date"])
    return None


def compare(cur, recs):
    """겹치는 (base_date, item_label) 을 값까지 대조한다."""
    keys = [(r["base_date"], r["item_label"]) for r in recs]
    cur.execute(
        "SELECT base_date, item_label, total_ton, top1_region, top1_ton,"
        "       top2_region, top2_ton, etc_ton"
        "  FROM daily_volume WHERE (base_date, item_label) IN"
        "       (SELECT unnest(%s::date[]), unnest(%s::text[]))",
        ([k[0] for k in keys], [k[1] for k in keys]))
    have = {(r[0], r[1]): r[2:] for r in cur.fetchall()}

    same, diff, new = 0, [], []
    for r in recs:
        k = (r["base_date"], r["item_label"])
        if k not in have:
            new.append(r)
            continue
        old = have[k]
        cur_v = (r["total_ton"], r["top1_region"], r["top1_ton"],
                 r["top2_region"], r["top2_ton"], r["etc_ton"])
        if tuple(old) == cur_v:
            same += 1
        else:
            diff.append((k, tuple(old), cur_v))
    return same, diff, new


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="./nongnet_chart/daily_volume.csv")
    ap.add_argument("--check", action="store_true", help="대조만 하고 쓰지 않는다")
    ap.add_argument("--update", action="store_true",
                    help="겹치는 행도 새 값으로 덮어쓴다 (기본은 새 행만 넣음)")
    ap.add_argument("--max-diff-pct", type=float, default=2.0,
                    help="겹치는 구간 불일치율 상한(%%). 넘으면 멈춘다")
    ap.add_argument("--force", action="store_true", help="불일치율 상한을 무시")
    a = ap.parse_args()

    if not os.path.exists(a.csv):
        sys.exit("CSV 가 없습니다: %s\n  먼저 `농넷에서 일일산출량 적재.py merge` 를 돌리세요." % a.csv)

    recs, bad = load_csv(a.csv)
    print("[CSV] %s" % a.csv)
    print("  정상 %d행 · 제외 %d행" % (len(recs), len(bad)))
    for r, why in bad[:10]:
        k = "%s %s" % (r.get("base_date", "?"), r.get("item_label", "?")) if isinstance(r, dict) else "?"
        print("    제외 %s — %s" % (k, why))
    if len(bad) > 10:
        print("    … 외 %d행" % (len(bad) - 10))
    if not recs:
        sys.exit("넣을 행이 없습니다.")

    ds = sorted(r["base_date"] for r in recs)
    items = sorted({r["item_label"] for r in recs})
    print("  범위 %s ~ %s · 품목 %s" % (ds[0], ds[-1], " ".join(items)))

    with psycopg.connect(dsn(), connect_timeout=20) as conn, conn.cursor() as cur:
        same, diff, new = compare(cur, recs)
        overlap = same + len(diff)
        print()
        print("[대조] 겹치는 %d행 · 일치 %d · 불일치 %d · 신규 %d"
              % (overlap, same, len(diff), len(new)))
        if overlap:
            pct = 100.0 * len(diff) / overlap
            print("  불일치율 %.2f%% (상한 %.2f%%)" % (pct, a.max_diff_pct))
            for (k, old, cur_v) in diff[:8]:
                print("    %s %s" % k)
                print("        기존 %s" % (old,))
                print("        신규 %s" % (cur_v,))
            if len(diff) > 8:
                print("    … 외 %d건" % (len(diff) - 8))
            if pct > a.max_diff_pct and not a.force:
                sys.exit(
                    "\n불일치율이 상한을 넘습니다. 같은 스크래퍼로 받은 값이 이렇게 갈리면\n"
                    "농넷이 값을 정정했거나 파싱이 달라진 것입니다. 원인을 먼저 확인하세요.\n"
                    "  그래도 넣으려면 --force")
        else:
            print("  [주의] 겹치는 구간이 없어 대조가 성립하지 않았습니다.")
            print("         기존 데이터와 같은 기준인지 확인되지 않은 채로 들어갑니다.")

        if a.check:
            print("\n--check 이므로 쓰지 않았습니다.")
            return

        rows = recs if a.update else new
        if not rows:
            print("\n넣을 새 행이 없습니다.")
            return

        sql = ("INSERT INTO daily_volume (%s) VALUES (%s) "
               "ON CONFLICT (base_date, item_label) DO %s"
               % (", ".join(COLS), ", ".join(["%s"] * len(COLS)),
                  ("UPDATE SET " + ", ".join(
                      "%s = EXCLUDED.%s" % (c, c) for c in COLS[2:])
                   + ", loaded_at = now()") if a.update else "NOTHING"))
        cur.executemany(sql, [[r[c] for c in COLS] for r in rows])
        conn.commit()
        print("\n적재 %d행 (%s)" % (cur.rowcount if cur.rowcount and cur.rowcount > 0 else len(rows),
                                 "덮어쓰기" if a.update else "새 행만"))

        cur.execute("SELECT item_label, MIN(base_date), MAX(base_date), COUNT(*) "
                    "FROM daily_volume GROUP BY 1 ORDER BY 1")
        print("\n[적재 후 daily_volume]")
        for r in cur.fetchall():
            print("  %-6s %s ~ %s · %d행" % r)


if __name__ == "__main__":
    main()
