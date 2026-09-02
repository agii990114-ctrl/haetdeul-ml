from __future__ import annotations

from pathlib import Path

from .constants import CSV_HEADERS, NATURAL_KEY_COLUMNS
from .csvio import ValidationResult


TABLE_NAME = "auction_prices_daily"
CONSTRAINT_NAME = "auction_prices_daily_natural_key_v3_uq"


def schema_sql() -> str:
    return f"""-- PostgreSQL 15+ 기준
BEGIN;

CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  auction_date date NOT NULL,
  market_category varchar(10) NOT NULL,
  wholesale_market_code varchar(20) NOT NULL,
  wholesale_market_name varchar(100) NOT NULL,
  item_code varchar(20) NOT NULL,
  item_name varchar(50) NOT NULL,
  subclass_code varchar(20),
  subclass_name varchar(100),
  grade_code varchar(20),
  grade_name varchar(50) NOT NULL,
  package_code varchar(20),
  package_name varchar(50),
  unit_weight_kg numeric(18,3),
  avg_auction_price_krw_per_kg numeric(28,6) NOT NULL,
  min_auction_price_krw_per_kg numeric(28,6) NOT NULL,
  max_auction_price_krw_per_kg numeric(28,6) NOT NULL,
  trade_volume_kg numeric(28,6) NOT NULL,
  trade_amount_krw numeric(28,6) NOT NULL,
  package_trade_quantity numeric(28,6) NOT NULL,
  source_trade_count bigint NOT NULL,
  source varchar(200) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 기존 표에 규격 컬럼을 더한다 (재실행 안전)
-- ▣ 적재 시각을 남긴다 (2026-08-28 추가)
--   이 표만 시각 컬럼이 없었다. 다른 RAW 표는 전부 있다 —
--   veg_daily_price_raw·weather_asos_raw·econ_daily_raw 는 created_at,
--   daily_volume 은 loaded_at. 이 수집기는 넘겨받은 패키지라 우리 공용
--   적재기(_dbload.py)를 안 쓰고 자기 스키마를 자기가 만들었고, 거기에
--   시각 컬럼이 없었다.
--
--   없어서 실제로 막혔던 것 (2026-08-28):
--     · "마지막으로 새 행이 들어온 게 언제인가" 를 못 물었다.
--       auction_date 는 경매가 열린 날이지 우리가 받은 날이 아니다.
--       API 가 0건을 돌려주기 시작한 시점을 캐시 파일 수정시각으로
--       추정해야 했다.
--     · 08-27 재수집 때 구 행 78만건을 지웠다. 시각이 있었으면
--       지우지 않고 "그 이전에 들어온 것" 으로 가를 수 있었다.
--     · UPSERT 가 값을 덮어도 흔적이 없었다.
--
--   created_at 은 CSV 헤더에 없으므로 UPSERT 갱신 목록에서 자동 제외된다.
--   updated_at 만 아래에서 따로 갱신한다.
ALTER TABLE {TABLE_NAME}
  ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP;

ALTER TABLE {TABLE_NAME}
  ADD COLUMN IF NOT EXISTS subclass_code  varchar(20),
  ADD COLUMN IF NOT EXISTS subclass_name  varchar(100),
  ADD COLUMN IF NOT EXISTS package_code   varchar(20),
  ADD COLUMN IF NOT EXISTS package_name   varchar(50),
  ADD COLUMN IF NOT EXISTS unit_weight_kg numeric(18,3);

-- ▣ 자연키가 넓어졌다 (2026-08-27)
--   v2 키는 (날짜·시장·품목·등급) 이라 규격이 다른 거래가 한 행에 뭉쳤다.
--   v3 는 소분류·포장·포장중량을 더한다. **v2 제약을 먼저 떼야 한다** —
--   같은 (날짜·시장·품목·등급) 에 규격별 행이 여러 개 생기기 때문이다.
DROP INDEX IF EXISTS auction_prices_daily_natural_key_uq;
ALTER TABLE {TABLE_NAME} DROP CONSTRAINT IF EXISTS auction_prices_daily_natural_key_v2_uq;
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = '{CONSTRAINT_NAME}') THEN
    ALTER TABLE {TABLE_NAME}
      ADD CONSTRAINT {CONSTRAINT_NAME}
      UNIQUE NULLS NOT DISTINCT
      (auction_date, wholesale_market_code, item_code, subclass_code,
       grade_code, grade_name, package_code, unit_weight_kg);
  END IF;
END $$;

-- 언제 들어온 행인지로 훑는다 (신선도 점검·사고 조사용)
CREATE INDEX IF NOT EXISTS auction_prices_daily_created_idx
  ON {TABLE_NAME} (created_at DESC);
CREATE INDEX IF NOT EXISTS auction_prices_daily_item_date_idx
  ON {TABLE_NAME} (item_code, auction_date);
CREATE INDEX IF NOT EXISTS auction_prices_daily_market_date_idx
  ON {TABLE_NAME} (wholesale_market_code, auction_date);
CREATE INDEX IF NOT EXISTS auction_prices_daily_grade_idx
  ON {TABLE_NAME} (grade_code);
-- 규격 지정 조회용 — v5 가 "가락·특등급·그물망 10kg" 같은 조건으로 읽는다
CREATE INDEX IF NOT EXISTS auction_prices_daily_spec_idx
  ON {TABLE_NAME} (item_code, grade_code, package_code, unit_weight_kg, auction_date);

COMMENT ON TABLE {TABLE_NAME} IS '건고추·양파·배추·무·마늘 일별 도매시장 등급별 경매 낙찰 집계';
COMMENT ON COLUMN {TABLE_NAME}.grade_code IS '원천에서 미상인 경우 NULL';
COMMENT ON COLUMN {TABLE_NAME}.unit_weight_kg IS
  '포장당 중량(kg). 원천 unit_qty. 같은 등급이라도 이 값이 다르면 다른 상품이다';
COMMENT ON COLUMN {TABLE_NAME}.package_name IS
  '포장 형태 (그물망·상자·PE대·파렛트 등). 원천 pkg_nm';
COMMENT ON COLUMN {TABLE_NAME}.subclass_name IS
  '소분류 (고냉지배추·쌈배추·저장배추 등). 원천 gds_sclsf_nm. 배추 안에 쌈배추가 섞여 있었다';

COMMIT;
"""


def _create_table_sql() -> str:
    return schema_sql().replace("BEGIN;", "", 1).replace("\nCOMMIT;\n", "\n", 1)


def load_postgres(database_url: str, csv_path: Path, validation: ValidationResult) -> dict[str, object]:
    try:
        import psycopg
    except ImportError as error:
        raise RuntimeError("PostgreSQL 적재에는 `python -m pip install -e '.[postgres]'`가 필요합니다.") from error

    column_sql = ", ".join(CSV_HEADERS)
    create_stage = """
CREATE TEMP TABLE auction_prices_stage (
  auction_date date NOT NULL,
  market_category varchar(10) NOT NULL,
  wholesale_market_code varchar(20) NOT NULL,
  wholesale_market_name varchar(100) NOT NULL,
  item_code varchar(20) NOT NULL,
  item_name varchar(50) NOT NULL,
  subclass_code varchar(20),
  subclass_name varchar(100),
  grade_code varchar(20),
  grade_name varchar(50) NOT NULL,
  package_code varchar(20),
  package_name varchar(50),
  unit_weight_kg numeric(18,3),
  avg_auction_price_krw_per_kg numeric(28,6) NOT NULL,
  min_auction_price_krw_per_kg numeric(28,6) NOT NULL,
  max_auction_price_krw_per_kg numeric(28,6) NOT NULL,
  trade_volume_kg numeric(28,6) NOT NULL,
  trade_amount_krw numeric(28,6) NOT NULL,
  package_trade_quantity numeric(28,6) NOT NULL,
  source_trade_count bigint NOT NULL,
  source varchar(200) NOT NULL
) ON COMMIT DROP;
"""
    # 충돌 시 갱신에서 키 컬럼은 뺀다. 여기도 옛 5컬럼 키가 박혀 있었다
    # (2026-08-28 수정). 키를 자기 값으로 덮는 것이라 동작은 같았지만,
    # 키 정의가 두 군데로 갈라져 있는 것 자체가 다음 사고의 씨앗이다.
    updates = ",\n".join(
        f"  {column} = EXCLUDED.{column}"
        for column in CSV_HEADERS
        if column not in set(NATURAL_KEY_COLUMNS)
    )
    upsert = f"""
INSERT INTO {TABLE_NAME} ({column_sql})
SELECT {column_sql} FROM auction_prices_stage
ON CONFLICT ON CONSTRAINT {CONSTRAINT_NAME} DO UPDATE SET
{updates},
  updated_at = CURRENT_TIMESTAMP;
"""

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(_create_table_sql())
            cursor.execute(create_stage)
            copy_sql = f"COPY auction_prices_stage ({column_sql}) FROM STDIN WITH (FORMAT CSV, HEADER TRUE, NULL '', ENCODING 'UTF8')"
            with cursor.copy(copy_sql) as copy:
                with csv_path.open("r", encoding="utf-8", newline="") as source:
                    for chunk in iter(lambda: source.read(1024 * 1024), ""):
                        copy.write(chunk)
            cursor.execute("SELECT COUNT(*), MIN(auction_date), MAX(auction_date) FROM auction_prices_stage")
            count, min_date, max_date = cursor.fetchone()
            if int(count) != validation.row_count:
                raise RuntimeError(f"staging 행 수 불일치: expected={validation.row_count}, actual={count}")
            # 자연키는 NATURAL_KEY_COLUMNS 하나만 본다 (2026-08-28 수정).
            #   여기에 옛 5컬럼 키(date·market·item·grade_code·grade_name)가
            #   하드코딩돼 있었다. 08-27 에 규격 컬럼을 넣어 키를 8개로 넓혔는데
            #   이 검사만 안 따라와서, **규격별로 여러 줄이 있는 정상 데이터를
            #   중복으로 오판해** 적재가 통째로 막혔다 (08-28 09:00 · 52개 그룹).
            #   같은 (날짜·시장·품목·등급) 안에 그물망 10kg 와 상자 4kg 가
            #   함께 있는 것이 지금은 맞는 모양이다.
            #
            #   상수를 쓰면 다음에 키가 또 바뀔 때 여기가 자동으로 따라온다.
            dup_key = ", ".join(NATURAL_KEY_COLUMNS)
            cursor.execute(
                f"""
SELECT COUNT(*) FROM (
  SELECT {dup_key}
  FROM auction_prices_stage
  GROUP BY {dup_key}
  HAVING COUNT(*) > 1
) duplicated
"""
            )
            duplicate_groups = int(cursor.fetchone()[0])
            if duplicate_groups:
                raise RuntimeError(f"staging 자연키 중복: {duplicate_groups}개 그룹")
            cursor.execute(upsert)
            affected = cursor.rowcount
        connection.commit()
    return {
        "loadedRows": validation.row_count,
        "affectedRows": affected,
        "minDate": min_date.isoformat() if min_date else None,
        "maxDate": max_date.isoformat() if max_date else None,
    }



def max_loaded_date(database_url: str) -> str | None:
    """DB 에 들어가 있는 마지막 경매일. 없으면 None.

    왜 필요한가 (2026-08-28):
      `merge_csv` 가 CSV 를 먼저 쓰고 그다음 `load_postgres` 를 부른다.
      적재가 실패하면 **CSV 는 앞서 가고 DB 는 뒤처진 채로 갈라진다.**
      그다음 실행은 CSV 기준으로 "받을 게 없다" 고 판단해 적재를 아예
      건너뛰므로, 한 번 벌어진 차이가 저절로는 절대 안 메워진다.

      실제로 08-28 09:00 에 250행이 CSV 에만 들어가고 DB 에서 빠졌다.
      `update` 를 다시 돌려도 `up_to_date` 라 손을 못 댔다.

      이 함수로 두 쪽 최신일을 대보고, DB 가 뒤처져 있을 때만 다시 싣는다.
    """
    try:
        import psycopg
    except ImportError as error:                             # pragma: no cover
        raise RuntimeError("PostgreSQL 조회에는 psycopg 가 필요합니다.") from error

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT to_regclass(%s) IS NOT NULL", (TABLE_NAME,)
            )
            if not cursor.fetchone()[0]:
                return None
            cursor.execute(f"SELECT MAX(auction_date) FROM {TABLE_NAME}")
            row = cursor.fetchone()
    return row[0].isoformat() if row and row[0] else None
