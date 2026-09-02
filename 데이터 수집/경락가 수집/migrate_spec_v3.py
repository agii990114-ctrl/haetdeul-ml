# -*- coding: utf-8 -*-
"""경락가 규격 분리 이관 — auction_prices_daily v2 → v3  (2026-08-27)

    python migrate_spec_v3.py <수집CSV> [<수집CSV> ...] --dry-run
    python migrate_spec_v3.py <수집CSV> [<수집CSV> ...] --commit

## 왜 필요한가

기존 표는 (날짜·시장·품목·등급) 한 행이라 **포장 규격이 전부 뭉쳐 있었다.**
가락 배추 특등급 하루치에 그물망 10kg(711원/kg)부터 1kg 소포장(11,224원/kg)
까지 15개 상품이 한 평균에 섞였고, 그 결과 배추 경락가의 자기상관은
ACF(1) 0.085 — 사실상 백색잡음이었다. 규격을 고르면 0.795 로 올라간다.

## 이 스크립트가 하는 일

1. 백업 존재 확인 (`auction_prices_daily_backup_20260827`). 없으면 만든다
2. 새 컬럼 5종 추가 + 자연키 v2 제거 → v3 생성
3. **구 데이터 삭제** — 규격이 없는 행은 새 행과 섞을 수 없다.
   같은 (날짜·시장·품목·등급)에 규격별 행이 여러 개 생기므로, 구 행을
   남기면 합계가 두 배가 된다
4. CSV 적재 (UPSERT)
5. 검증 — 행수·구간·규격 커버리지

## 되돌리기

    DROP TABLE auction_prices_daily;
    ALTER TABLE auction_prices_daily_backup_20260827 RENAME TO auction_prices_daily;
    -- 그 다음 v5 의 tmp_auc 규격 조건을 되돌려야 한다 (v5.4 이전으로)
"""
import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import psycopg  # noqa: E402

from _dbload import dsn  # noqa: E402

TABLE = "auction_prices_daily"
BACKUP = "auction_prices_daily_backup_20260827"
COLS = ["auction_date", "market_category", "wholesale_market_code",
        "wholesale_market_name", "item_code", "item_name",
        "subclass_code", "subclass_name", "grade_code", "grade_name",
        "package_code", "package_name", "unit_weight_kg",
        "avg_auction_price_krw_per_kg", "min_auction_price_krw_per_kg",
        "max_auction_price_krw_per_kg", "trade_volume_kg", "trade_amount_krw",
        "package_trade_quantity", "source_trade_count", "source"]
NUM = {"unit_weight_kg", "avg_auction_price_krw_per_kg",
       "min_auction_price_krw_per_kg", "max_auction_price_krw_per_kg",
       "trade_volume_kg", "trade_amount_krw", "package_trade_quantity",
       "source_trade_count"}

DDL = f"""
ALTER TABLE {TABLE}
  ADD COLUMN IF NOT EXISTS subclass_code  varchar(20),
  ADD COLUMN IF NOT EXISTS subclass_name  varchar(100),
  ADD COLUMN IF NOT EXISTS package_code   varchar(20),
  ADD COLUMN IF NOT EXISTS package_name   varchar(50),
  ADD COLUMN IF NOT EXISTS unit_weight_kg numeric(18,3);

DROP INDEX IF EXISTS auction_prices_daily_natural_key_uq;
ALTER TABLE {TABLE} DROP CONSTRAINT IF EXISTS auction_prices_daily_natural_key_v2_uq;
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint
                  WHERE conname = 'auction_prices_daily_natural_key_v3_uq') THEN
    ALTER TABLE {TABLE}
      ADD CONSTRAINT auction_prices_daily_natural_key_v3_uq
      UNIQUE NULLS NOT DISTINCT
      (auction_date, wholesale_market_code, item_code, subclass_code,
       grade_code, grade_name, package_code, unit_weight_kg);
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS auction_prices_daily_spec_idx
  ON {TABLE} (item_code, grade_code, package_code, unit_weight_kg, auction_date);
"""


def read_csv(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        missing = [c for c in COLS if c not in (reader.fieldnames or [])]
        if missing:
            raise SystemExit(f"{path.name}: 컬럼 없음 {missing}\n"
                             f"  수집기 v3 로 받은 CSV 인지 확인하세요.")
        for row in reader:
            yield [None if row[c] == "" else row[c] for c in COLS]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="+", type=Path)
    ap.add_argument("--commit", action="store_true", help="실제 반영 (기본은 계획만)")
    ap.add_argument("--batch", type=int, default=20000)
    a = ap.parse_args()

    for p in a.csv:
        if not p.exists():
            raise SystemExit(f"파일 없음: {p}")

    with psycopg.connect(dsn()) as cn:
        with cn.cursor() as cur:
            cur.execute("SELECT to_regclass(%s)", (BACKUP,))
            if cur.fetchone()[0] is None:
                print(f"[백업] {BACKUP} 생성")
                if a.commit:
                    cur.execute(f"CREATE TABLE {BACKUP} AS SELECT * FROM {TABLE}")
            else:
                cur.execute(f"SELECT COUNT(*) FROM {BACKUP}")
                print(f"[백업] 이미 있음 — {cur.fetchone()[0]:,}행")

            cur.execute(f"SELECT COUNT(*), MIN(auction_date), MAX(auction_date) FROM {TABLE}")
            n0, mn0, mx0 = cur.fetchone()
            print(f"[현재] {n0:,}행 · {mn0} ~ {mx0}")

            total = sum(1 for p in a.csv for _ in read_csv(p))
            print(f"[투입] CSV {len(a.csv)}개 · {total:,}행")

            if not a.commit:
                print("\n--dry-run — 아무것도 바꾸지 않았습니다. --commit 으로 실행하세요.")
                return

            print("[DDL] 컬럼 추가 · 자연키 v3")
            cur.execute(DDL)

            # 구 데이터는 규격이 없어 새 행과 섞을 수 없다. 같은 날짜에
            # 규격별 행이 새로 들어오므로 남겨두면 합계가 중복된다.
            print("[삭제] 규격 없는 구 행 (unit_weight_kg IS NULL)")
            cur.execute(f"DELETE FROM {TABLE} WHERE unit_weight_kg IS NULL")
            print(f"        {cur.rowcount:,}행 삭제")

            ph = ",".join(["%s"] * len(COLS))
            sql = (f"INSERT INTO {TABLE} ({','.join(COLS)}) VALUES ({ph}) "
                   f"ON CONFLICT ON CONSTRAINT auction_prices_daily_natural_key_v3_uq "
                   f"DO NOTHING")
            done = 0
            for p in a.csv:
                buf = []
                for row in read_csv(p):
                    buf.append(row)
                    if len(buf) >= a.batch:
                        cur.executemany(sql, buf); done += len(buf); buf = []
                        print(f"        {done:,} / {total:,}", end="\r")
                if buf:
                    cur.executemany(sql, buf); done += len(buf)
                print(f"[적재] {p.name} 누적 {done:,}행")
        cn.commit()

    with psycopg.connect(dsn()) as cn, cn.cursor() as cur:
        cur.execute(f"""SELECT COUNT(*), MIN(auction_date), MAX(auction_date),
                               COUNT(*) FILTER (WHERE unit_weight_kg IS NULL)
                          FROM {TABLE}""")
        n, mn, mx, nul = cur.fetchone()
        print(f"\n[검증] {n:,}행 · {mn} ~ {mx} · 규격 NULL {nul:,}")
        cur.execute(f"""SELECT item_name, unit_weight_kg, COUNT(DISTINCT auction_date) 일수
                          FROM {TABLE}
                         WHERE wholesale_market_code='110001' AND grade_code='11'
                           AND ((item_name='배추' AND unit_weight_kg=10)
                             OR (item_name='무'   AND unit_weight_kg IN (18,20))
                             OR (item_name='양파' AND unit_weight_kg=15))
                         GROUP BY 1,2 ORDER BY 1,2""")
        print(f"  {'품목':<5}{'규격kg':>8}{'거래일':>8}")
        for it, w, d in cur.fetchall():
            print(f"  {it:<5}{float(w):>8.0f}{d:>8,}")


if __name__ == "__main__":
    main()
