"""
깐마늘 소매가 수집 및 veg_daily_price_raw 적재

배경
    피마늘(item_cd=244)에는 소매 데이터가 없다. 소매점에서 파는 것은
    껍질 벗긴 깐마늘이며 KAMIS 가 이를 별도 품목으로 관리하기 때문이다.
    저장 트레이딩 모델의 매도가(소매) 예측을 위해 깐마늘 데이터가 필요하다.

    피마늘 39,339행 전부가 se_cd=02(중도매), 소매 0건임을 확인했다.

사용법
    pip install requests pandas psycopg[binary]

    # 1) 깐마늘 품목코드 확인 (필수 선행)
    python at_price_collector.py --discover --keyword 마늘

    # 2) 수집만 (CSV 저장, DB 미적재)
    python load_peeled_garlic.py --item-cd 확인한코드

    # 3) 수집 + DB 적재
    python load_peeled_garlic.py --item-cd 확인한코드 --load-db

    # 3-1) 이미 받아둔 CSV 로 적재 (API 재호출 없음, 훨씬 빠름)
    python load_peeled_garlic.py --from-csv peeled_garlic.csv --load-db

    # 4) 적재 없이 미리보기
    python load_peeled_garlic.py --item-cd 확인한코드 --dry-run

환경변수 (.env 또는 시스템 환경변수)
    DATA_GO_KR_KEY   공공데이터포털 인증키
    DATABASE_URL     postgresql://user:password@host:5432/dbname

    ※ 비밀번호를 코드나 명령행에 직접 쓰지 말 것.
"""

import argparse
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlencode

import pandas as pd
import requests

URL = "https://apis.data.go.kr/B552845/perDay/price"
ROWS = 1000
SLEEP = 0.3
TIMEOUT = 60
MAX_RETRY = 4

# veg_daily_price_raw 의 적재 대상 컬럼 (id·created_at 은 DB 가 생성)
TABLE = "veg_daily_price_raw"
COLUMNS = [
    "exmn_ymd", "ctgry_cd", "ctgry_nm", "item_cd", "item_nm",
    "vrty_cd", "vrty_nm", "grd_cd", "grd_nm", "se_cd", "se_nm",
    "sgg_cd", "sgg_nm", "mrkt_cd", "mrkt_nm",
    "unit", "unit_sz", "exmn_dd_prc", "exmn_dd_cnvs_prc", "orgnl_reg_dt",
]
# 중복 판정 기준. 같은 조사일·품목·품종·등급·구분·시장이면 같은 행으로 본다
NATURAL_KEY = ["exmn_ymd", "item_cd", "vrty_cd", "grd_cd", "se_cd", "mrkt_cd", "sgg_cd"]


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


# ──────────────────────────────────────────────────────── 수집
def find_records(node, out=None):
    if out is None:
        out = []
    if isinstance(node, dict):
        if "exmn_ymd" in node or "item_cd" in node:
            out.append(node)
        else:
            for v in node.values():
                find_records(v, out)
    elif isinstance(node, list):
        for v in node:
            find_records(v, out)
    return out


def find_key(node, key):
    if isinstance(node, dict):
        if key in node and not isinstance(node[key], (dict, list)):
            return node[key]
        for v in node.values():
            got = find_key(v, key)
            if got is not None:
                return got
    elif isinstance(node, list):
        for v in node:
            got = find_key(v, key)
            if got is not None:
                return got
    return None


def request_page(key, params, retry=MAX_RETRY):
    query = {"serviceKey": key, "returnType": "JSON", **params}
    url = f"{URL}?{urlencode(query, safe='[]:')}"
    for attempt in range(retry + 1):
        try:
            r = requests.get(url, timeout=TIMEOUT)
            if r.status_code == 429 or r.status_code >= 500:
                raise RuntimeError(f"재시도 가능: HTTP {r.status_code}")
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
            try:
                return r.json()
            except ValueError:
                raise RuntimeError(f"비JSON 응답(키 확인): {r.text[:300]}")
        except (requests.RequestException, RuntimeError) as e:
            retryable = "재시도 가능" in str(e) or isinstance(e, requests.RequestException)
            if attempt >= retry or not retryable:
                raise
            time.sleep(min(8.0, 0.7 * (2 ** attempt)))


def fetch_year(key, item_cd, year):
    out, page = [], 1
    while True:
        data = request_page(key, {
            "pageNo": page, "numOfRows": ROWS,
            "cond[exmn_ymd::GTE]": f"{year}0101",
            "cond[exmn_ymd::LTE]": f"{year}1231",
            "cond[ctgry_cd::EQ]": "200",
            "cond[item_cd::EQ]": item_cd,
        })
        records = find_records(data)
        if not records:
            if page == 1:
                msg = find_key(data, "resultMsg") or find_key(data, "returnAuthMsg")
                print(f"    {year}: 0건" + (f" ({msg})" if msg else ""))
            break
        out.extend(records)
        total = find_key(data, "totalCount")
        total = int(total) if total is not None else None
        if len(records) < ROWS or (total and page * ROWS >= total):
            break
        page += 1
        time.sleep(SLEEP)
    if out:
        print(f"    {year}: {len(out)}건")
    return out


# ──────────────────────────────────────────────────── 정규화
def normalize(records, item_cd):
    """API 응답을 veg_daily_price_raw 스키마에 맞춘다."""
    df = pd.DataFrame(records)
    if df.empty:
        return df

    missing = [c for c in COLUMNS if c not in df.columns]
    if missing:
        print(f"  [주의] 응답에 없는 컬럼: {missing} — 빈값으로 채웁니다.")
        for c in missing:
            df[c] = None

    df = df[COLUMNS].copy()

    # 날짜 정규화
    #   API 원본은 20230731, 이미 저장된 CSV 는 2023-07-31 형태다.
    #   두 형식을 모두 받아들여야 --from-csv 로 재적재할 때 걸러지지 않는다.
    raw_dt = df["exmn_ymd"].astype(str).str.strip()
    parsed = pd.to_datetime(raw_dt, format="%Y%m%d", errors="coerce")
    fallback = pd.to_datetime(raw_dt, errors="coerce")   # ISO 등 기타 형식
    df["exmn_ymd"] = parsed.fillna(fallback).dt.date

    # 수치: 쉼표 제거 후 변환
    for c in ("unit_sz", "exmn_dd_prc", "exmn_dd_cnvs_prc"):
        df[c] = pd.to_numeric(df[c].astype(str).str.replace(",", ""), errors="coerce")

    df = df.dropna(subset=["exmn_ymd", "exmn_dd_prc"])
    before = len(df)
    df = df.drop_duplicates(subset=NATURAL_KEY)
    if before != len(df):
        print(f"  자연키 중복 {before - len(df)}행 제거")
    return df


def summarize(df):
    if df.empty:
        print("\n수집 결과 없음.")
        return
    print(f"\n[요약] {len(df):,}행 · {df.exmn_ymd.min()} ~ {df.exmn_ymd.max()}")
    print(f"  품목: {df.item_nm.dropna().unique().tolist()}")
    if "se_nm" in df:
        print("\n  구분별 건수:")
        for (cd, nm), n in df.groupby(["se_cd", "se_nm"]).size().items():
            mark = "  ← 소매" if str(cd) == "01" else ""
            print(f"    {cd} {nm:<8} {n:>7,}{mark}")
    if "unit" in df:
        print("\n  단위:")
        for (u, sz), n in df.groupby(["unit", "unit_sz"]).size().nlargest(5).items():
            print(f"    {u} × {sz}  {n:,}행")
        # kg 환산 가능 여부 — 배추 소매가 '포기' 단위라 못 나눴던 문제 확인
        kg = df[df.unit.astype(str).str.contains("kg", case=False, na=False)]
        print(f"  kg 단위 비율: {len(kg)/len(df)*100:.1f}%")
        if len(kg) < len(df):
            print("    ※ kg 이 아닌 단위가 섞여 있습니다. 학습 시 환산 가능 여부를 확인하세요.")


# ────────────────────────────────────────────────────── DB 적재
def load_db(df, dsn, dry_run=False):
    """자연키 중복 시 갱신(UPSERT). 기존 마늘 데이터는 건드리지 않는다."""
    try:
        import psycopg
    except ImportError:
        sys.exit("psycopg 가 필요합니다:  pip install 'psycopg[binary]'")

    if dry_run:
        print(f"\n[dry-run] {len(df):,}행을 {TABLE} 에 적재할 예정입니다.")
        print(df.head(3).to_string())
        return

    cols = ", ".join(COLUMNS)
    placeholders = ", ".join(["%s"] * len(COLUMNS))
    rows = [tuple(None if pd.isna(v) else v for v in r)
            for r in df[COLUMNS].itertuples(index=False, name=None)]

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            # 기존 건수 (적재 전후 비교용)
            cur.execute(f"SELECT COUNT(*) FROM {TABLE} WHERE item_cd = %s",
                        (df.item_cd.iloc[0],))
            before = cur.fetchone()[0]

            # 재적재 안전 (2026-08-25 추가).
            #   veg_daily_price_raw_uk 가 걸려 있어 같은 구간을 다시 넣으면
            #   UniqueViolation 으로 통째로 실패했다. 겹치는 구간을 그냥
            #   건너뛰면 증분만 들어간다 — 다른 수집기들과 같은 방식이다.
            cur.executemany(
                f"INSERT INTO {TABLE} ({cols}) VALUES ({placeholders}) "
                f"ON CONFLICT ON CONSTRAINT veg_daily_price_raw_uk DO NOTHING", rows)

            cur.execute(f"SELECT COUNT(*) FROM {TABLE} WHERE item_cd = %s",
                        (df.item_cd.iloc[0],))
            after = cur.fetchone()[0]
        conn.commit()

    print(f"\n[DB 적재] {TABLE}")
    print(f"  item_cd={df.item_cd.iloc[0]}  적재 전 {before:,} → 적재 후 {after:,}행")
    print(f"  신규 {after - before:,}행")


def main():
    ap = argparse.ArgumentParser(description="깐마늘 소매가 수집·적재")
    ap.add_argument("--item-cd",
                    help="깐마늘 품목코드. --discover 로 먼저 확인할 것")
    ap.add_argument("--from-csv", type=Path,
                    help="이미 받아둔 CSV 로 적재. API 를 다시 부르지 않는다")
    ap.add_argument("--start", type=int, default=2015)
    ap.add_argument("--end", type=int, default=2025)
    ap.add_argument("--out", default="peeled_garlic_raw.csv")
    ap.add_argument("--load-db", action="store_true", help="DB 적재까지 수행")
    ap.add_argument("--dry-run", action="store_true", help="적재하지 않고 미리보기")
    ap.add_argument("--env-file", type=Path, default=Path(".env"))
    a = ap.parse_args()

    load_dotenv(a.env_file)

    if a.from_csv:
        # 이미 받아둔 CSV 를 그대로 쓴다. API 호출 없음
        if not a.from_csv.exists():
            sys.exit(f"파일이 없습니다: {a.from_csv}")
        print(f"[CSV 로드] {a.from_csv}")
        df = pd.read_csv(a.from_csv, dtype=str, low_memory=False)
        # normalize 를 거친 CSV 든 원본이든 동일하게 정규화한다
        df = normalize(df.to_dict("records"), a.item_cd or "")
        summarize(df)
        if df.empty:
            return
    else:
        if not a.item_cd:
            sys.exit("--item-cd 또는 --from-csv 중 하나가 필요합니다.")
        key = os.environ.get("DATA_GO_KR_KEY", "").strip()
        if not key:
            sys.exit("DATA_GO_KR_KEY 가 없습니다. .env 에 넣으세요.")

        print(f"[수집] item_cd={a.item_cd}  {a.start}~{a.end}")
        records = []
        for year in range(a.start, a.end + 1):
            try:
                records.extend(fetch_year(key, a.item_cd, year))
            except Exception as e:
                print(f"    ! {year} 실패: {e}")
            time.sleep(SLEEP)

        df = normalize(records, a.item_cd)
        summarize(df)
        if df.empty:
            return
        df.to_csv(a.out, index=False, encoding="utf-8-sig")
        print(f"\n{a.out} 저장")

    if a.load_db or a.dry_run:
        dsn = os.environ.get("DATABASE_URL", "").strip()
        if not dsn:
            sys.exit("DATABASE_URL 이 없습니다. .env 에 넣으세요.")
        load_db(df, dsn, dry_run=a.dry_run)


if __name__ == "__main__":
    main()