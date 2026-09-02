# -*- coding: utf-8 -*-
"""
predict_input → CSV
====================
`predict.py` 는 CSV 를 받는다. DB 의 `predict_input` 을 그 형식으로 내보낸다.

    python export_predict_input.py --out pi.csv                 # 최신 기준일
    python export_predict_input.py --base-dt 2026-08-21 --out pi.csv
    python export_predict_input.py --all --out pi_all.csv        # 전 구간
    python export_predict_input.py --source train --base-dt 2025-12-31 --out pi.csv

`--source train` 은 왜 있나
    `predict_input` 은 **최근 30 조사일만** 담는다 (STEP 8 의 n_base).
    운영 배치는 어제 기준일 하나면 되니 그걸로 충분하지만, 지난 날짜를
    기준일로 삼아 예측하려면(예: 팀 요청 2025-12-31) 그 날이 창 밖이라
    행이 없다.

    같은 feature 가 `crop_price_train` 에 그대로 있다. 두 표가 겹치는
    구간에서 전 컬럼이 일치한다는 것은 v5 검증 [14] 가 매번 확인한다.
    그래서 지난 기준일은 여기서 뽑는다.

    ★ 정답 컬럼(target_*)은 NULL 로 비우고 내보낸다. crop_price_train
      에는 정답이 들어 있어서, 그대로 두면 추론 입력에 정답이 섞인
      CSV 가 디스크에 남는다. predict.py 가 안 쓰더라도 남기지 않는다.

왜 predict.py 가 DB 를 직접 안 읽나
    학습에 쓴 CSV 와 **같은 경로**로 추론해야 조건이 어긋나지 않는다.
    predict.py 가 DB 와 CSV 두 입력을 받으면 둘이 갈라질 자리가 생긴다.
    입구를 하나로 두고, DB→CSV 변환은 이 스크립트가 맡는다.

신선도
    기준일이 오늘과 얼마나 떨어졌는지 함께 찍는다. 판단은 배치가 한다
    (run_batch.py 가 조사일 기준으로 재고 임계를 넘으면 추론을 멈춘다).
"""
import argparse
import os
import sys
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[3]


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="predict_input.csv")
    ap.add_argument("--base-dt", help="이 기준일만. 생략 시 최신")
    ap.add_argument("--all", action="store_true", help="전 구간")
    ap.add_argument("--items", nargs="+", default=None)
    ap.add_argument("--source", choices=("predict_input", "train"),
                    default="predict_input",
                    help="train 이면 crop_price_train 에서 뽑는다 (지난 기준일용)")
    a = ap.parse_args()

    conn = psycopg.connect(dsn(), connect_timeout=25)
    TBL = "predict_input" if a.source == "predict_input" else "crop_price_train"
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass(%s)", (TBL,))
        if cur.fetchone()[0] is None:
            sys.exit("%s 이 없습니다. DBEAVER_run_v5.sql 을 먼저 돌리세요." % TBL)

        where, args = [], []
        if not a.all:
            if a.base_dt:
                where.append("base_dt = %s")
                args.append(a.base_dt)
            else:
                where.append("base_dt = (SELECT MAX(base_dt) FROM %s)" % TBL)
        if a.items:
            where.append("item_nm = ANY(%s)")
            args.append(a.items)
        w = ("WHERE " + " AND ".join(where)) if where else ""

        #   crop_price_train 에서 뽑을 때는 predict_input 과 모양을 맞춘다.
        #     · id · created_at 은 빼고
        #     · 정답 컬럼은 NULL 로 비운다 (위 머리말 ★)
        if a.source == "train":
            cur.execute("""SELECT column_name FROM information_schema.columns
                           WHERE table_name='crop_price_train'
                             AND column_name NOT IN ('id','created_at')
                           ORDER BY ordinal_position""")
            names = [r[0] for r in cur.fetchall()]
            #   ★ 이름으로 거르지 말 것. target_dow(대상일 요일)·target_dt 는
            #     정답이 아니라 입력이다. 실제로 한 번 같이 비웠다가
            #     feature 하나를 통째로 날렸다. 지울 것을 손으로 적는다.
            ANSWERS = ("target_auc_prc", "target_whsl_prc", "target_rtl_prc")
            sel = ", ".join(("NULL::numeric AS " + n) if n in ANSWERS else n
                            for n in names)
        else:
            sel = "*"
        cur.execute("SELECT %s FROM %s %s ORDER BY base_dt, item_nm, lead_biz_d"
                    % (sel, TBL, w), args)
        cols = [d.name for d in cur.description]
        rows = cur.fetchall()
    conn.close()

    if not rows:
        sys.exit("내보낼 행이 없습니다. 조건을 확인하세요.")

    import csv as _csv
    outp = Path(a.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    with open(outp, "w", encoding="utf-8-sig", newline="") as f:
        w_ = _csv.writer(f)
        w_.writerow(cols)
        w_.writerows(rows)

    i_b = cols.index("base_dt")
    i_t = cols.index("target_dt")
    bases = sorted({r[i_b] for r in rows})
    import datetime
    lag = (datetime.date.today() - bases[-1]).days
    print("내보내기: %s" % outp)
    print("  %d행 · 기준일 %s%s · 대상일 최대 %s"
          % (len(rows), bases[0],
             ("" if len(bases) == 1 else " ~ %s" % bases[-1]),
             max(r[i_t] for r in rows)))
    print("  최신 기준일이 오늘보다 %d일 앞섭니다" % lag)


if __name__ == "__main__":
    main()
