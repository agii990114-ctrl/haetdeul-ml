# -*- coding: utf-8 -*-
"""
예측 CSV → prediction_log 적재
===============================
`predict.py` 가 만든 CSV 를 DB 에 넣는다. 여러 개를 한 번에 줘도 된다.

    python load_predictions.py pred_auc.csv pred_whsl.csv pred_rtl.csv
    python load_predictions.py pred_*.csv --check

재적재 안전
    UNIQUE (base_dt, item_nm, lead_biz_d, target_kind, model_ver) 가 있다.
    같은 모델로 같은 기준일을 다시 예측하면 **기존 행을 갱신**한다(DO UPDATE).
    모델 버전이 다르면 새 행이 되므로 버전 간 비교가 남는다.

    갱신 대상에서 `actual_prc`·`abs_pct_err`·`scored_at` 은 제외한다.
    채점 결과를 예측 재적재가 지우면 안 된다.

넣기 전에 막는 것
    · 역변환 누락 — pred 가 앵커의 0.2~5배 밖이면 중단.
      predict.py 도 검사하지만, 손으로 만든 CSV 가 들어올 수 있다
    · 미래 대상일이 과거보다 앞서는 행 (target_dt < base_dt)
    · DB CHECK 와 같은 조건(가격 > 0, 리드타임 1~18, target_kind 3종)
    이런 것들은 DB 가 어차피 막지만, **어느 행이 왜 걸렸는지** 알려면
    여기서 먼저 걸러야 한다. 제약 위반 메시지만으로는 못 찾는다.
"""
import argparse
import csv
import os
import sys
from pathlib import Path

import psycopg

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]

COLS = ["base_dt", "target_dt", "item_nm", "lead_biz_d", "target_kind", "unit",
        "anchor_prc", "pred_prc", "pred_lo", "pred_hi", "seed_spread",
        "gated", "gate_reason", "model_ver", "model_created_at",
        #   ★ 구간을 어느 방식으로 만들었나 (2026-09-04).
        #     매입 파트가 폭으로 역산하다 세 번 어긋났다. 표시가 없었기 때문이다.
        #     옛 CSV 에는 이 칸이 없으므로 없으면 그냥 비워 둔다 (아래 miss 검사 제외).
        "band_method"]
NUM = {"anchor_prc", "pred_prc", "pred_lo", "pred_hi", "seed_spread"}
KIND = {"auc", "whsl", "rtl"}


def dsn():
    for p in (ROOT / ".env",):
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


def to_bool(x):
    return str(x).strip().lower() in ("true", "t", "1", "y", "yes")


def read(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return [], ["빈 파일"]
    miss = [c for c in COLS
            if c not in rows[0] and c not in ("gate_reason", "band_method")]
    if miss:
        return [], ["필요한 컬럼이 없습니다: %s" % miss]

    out, bad = [], []
    for i, r in enumerate(rows, 2):          # 헤더가 1행
        try:
            rec = {c: (r.get(c) or "").strip() or None for c in COLS}
            for c in NUM:
                rec[c] = float(rec[c]) if rec[c] not in (None, "") else None
            rec["lead_biz_d"] = int(float(r["lead_biz_d"]))
            rec["gated"] = to_bool(r.get("gated"))
        except (ValueError, TypeError) as e:
            bad.append("%s행 파싱 실패: %s" % (i, e))
            continue

        why = None
        if rec["target_kind"] not in KIND:
            why = "target_kind=%r (auc/whsl/rtl 만 허용)" % rec["target_kind"]
        elif not (1 <= rec["lead_biz_d"] <= 18):
            why = "lead_biz_d=%s (1~18)" % rec["lead_biz_d"]
        elif not rec["anchor_prc"] or rec["anchor_prc"] <= 0:
            why = "anchor_prc=%s (0 초과여야 함)" % rec["anchor_prc"]
        elif not rec["pred_prc"] or rec["pred_prc"] <= 0:
            why = "pred_prc=%s (0 초과여야 함)" % rec["pred_prc"]
        elif rec["target_dt"] and rec["base_dt"] and rec["target_dt"] < rec["base_dt"]:
            why = "target_dt(%s) < base_dt(%s)" % (rec["target_dt"], rec["base_dt"])
        elif not rec["model_ver"]:
            why = "model_ver 가 비었습니다"
        if why:
            bad.append("%s행 %s" % (i, why))
        else:
            out.append(rec)
    return out, bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="+")
    ap.add_argument("--check", action="store_true", help="검사만 하고 쓰지 않는다")
    a = ap.parse_args()

    allrec, allbad = [], []
    for p in a.csv:
        if not os.path.exists(p):
            sys.exit("파일이 없습니다: %s" % p)
        rec, bad = read(p)
        print("[%s] %d행%s" % (os.path.basename(p), len(rec),
                               " · 제외 %d" % len(bad) if bad else ""))
        for b in bad[:5]:
            print("    " + b)
        if len(bad) > 5:
            print("    … 외 %d건" % (len(bad) - 5))
        allrec += rec
        allbad += bad
    if not allrec:
        sys.exit("넣을 행이 없습니다.")

    # 역변환 누락 검사 — 가장 흔한 사고. 로그비율은 앵커와 자릿수가 다르다.
    ratios = sorted(r["pred_prc"] / r["anchor_prc"] for r in allrec)
    med = ratios[len(ratios) // 2]
    if not (0.2 < med < 5):
        sys.exit("예측/앵커 중앙값이 %.3f 배입니다. 역변환이 빠진 CSV 로 보입니다.\n"
                 "  predict.py 는 pred = anchor * exp(model_output) 을 냅니다." % med)

    kinds = sorted({r["target_kind"] for r in allrec})
    bases = sorted({r["base_dt"] for r in allrec})
    vers = sorted({r["model_ver"] for r in allrec})
    ng = sum(1 for r in allrec if r["gated"])
    print()
    print("[요약] %d행 · 타겟 %s · 기준일 %s~%s · 모델 %s"
          % (len(allrec), " ".join(kinds), bases[0], bases[-1], " ".join(vers)))
    print("  게이트 %d행 (%.0f%%)" % (ng, 100.0 * ng / len(allrec)))

    conn = psycopg.connect(dsn(), connect_timeout=25)
    with conn.cursor() as cur:
        keys = [(r["base_dt"], r["item_nm"], r["lead_biz_d"],
                 r["target_kind"], r["model_ver"]) for r in allrec]
        cur.execute("""SELECT COUNT(*) FROM prediction_log
                       WHERE (base_dt, item_nm, lead_biz_d, target_kind, model_ver)
                             IN (SELECT unnest(%s::date[]), unnest(%s::text[]),
                                        unnest(%s::smallint[]), unnest(%s::text[]),
                                        unnest(%s::text[]))""",
                    ([k[0] for k in keys], [k[1] for k in keys],
                     [k[2] for k in keys], [k[3] for k in keys], [k[4] for k in keys]))
        dup = cur.fetchone()[0]
        print("  이미 있는 조합 %d행 → 갱신 · 신규 %d행" % (dup, len(allrec) - dup))

        if a.check:
            print("\n--check 이므로 쓰지 않았습니다.")
            conn.close()
            return

        # actual_prc·abs_pct_err·scored_at 은 갱신 대상에서 뺀다.
        # 채점 결과를 예측 재적재가 지우면 안 된다.
        upd = [c for c in COLS
               if c not in ("base_dt", "item_nm", "lead_biz_d", "target_kind", "model_ver")]
        sql = ("INSERT INTO prediction_log (%s) VALUES (%s) "
               "ON CONFLICT (base_dt, item_nm, lead_biz_d, target_kind, model_ver) "
               "DO UPDATE SET %s, created_at = now()"
               % (", ".join(COLS), ", ".join(["%s"] * len(COLS)),
                  ", ".join("%s = EXCLUDED.%s" % (c, c) for c in upd)))
        cur.executemany(sql, [[r[c] for c in COLS] for r in allrec])
        conn.commit()

        cur.execute("""SELECT target_kind, COUNT(*), MIN(base_dt), MAX(base_dt),
                              COUNT(*) FILTER (WHERE actual_prc IS NOT NULL)
                       FROM prediction_log GROUP BY 1 ORDER BY 1""")
        print("\n적재 완료 — prediction_log")
        for k, n, mn, mx, sc in cur.fetchall():
            print("  %-5s %6d행 · %s ~ %s · 채점됨 %d" % (k, n, mn, mx, sc))
    conn.close()


if __name__ == "__main__":
    main()
