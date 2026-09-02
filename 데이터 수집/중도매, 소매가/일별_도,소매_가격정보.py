"""
한국농수산식품유통공사_일별 도,소매 가격정보 (B552845/perDay/price)
배추 / 양파 일별 도소매 가격 수집

uv add requests pandas
# 키는 루트 .env 의 DATA_GO_KR_KEY (환경변수로 줘도 된다)
uv run main.py --probe     # 사전 점검만
uv run main.py             # 전체 수집
"""

import json
import os
import sys
import time
from urllib.parse import urlencode

import pandas as pd
import requests

# 인증키는 루트 .env 의 DATA_GO_KR_KEY 에서 읽는다.
# 하드코딩된 값이 여기 있었고, collect_kamis.py 가 그것을 폴백으로 읽어
# 배치가 소스 파일의 비밀값에 의존하고 있었다 (2026-08-25 제거).
SERVICE_KEY = os.environ.get("DATA_GO_KR_KEY", "")
if not SERVICE_KEY:
    sys.exit("DATA_GO_KR_KEY 가 없습니다. 루트 .env 에 넣으세요.")
URL = "https://apis.data.go.kr/B552845/perDay/price"

START_YEAR, END_YEAR = 2015, 2026

TARGETS = [
    # {"name": "배추", "ctgry_cd": "200", "item_cd": "211"},
    # {"name": "양파", "ctgry_cd": "200", "item_cd": "245"},
    # {"name": "무", "ctgry_cd": "200", "item_cd": "231"},
    {"name": "마늘", "ctgry_cd": "200", "item_cd": "258"},
    # {"name": "고추", "ctgry_cd": "200", "item_cd": "241"},
]

ROWS = 1000
SLEEP = 0.3
TIMEOUT = 60


# ------------------------------------------------- 응답 파싱 (구조 무관)
def find_records(node, out=None):
    """중첩 깊이와 무관하게 exmn_ymd 를 가진 레코드를 전부 수집."""
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
    """중첩 어디에 있든 특정 키의 값을 찾는다 (totalCount 등)."""
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


# ------------------------------------------------------------- 요청
def request_page(target, gte, lte, page, rows=ROWS):
    params = {
        "serviceKey": SERVICE_KEY,
        "returnType": "JSON",
        "pageNo": page,
        "numOfRows": rows,
        "cond[exmn_ymd::GTE]": gte,
        "cond[exmn_ymd::LTE]": lte,
        "cond[ctgry_cd::EQ]": target["ctgry_cd"],
        "cond[item_cd::EQ]": target["item_cd"],
    }
    r = requests.get(f"{URL}?{urlencode(params, safe='[]:')}", timeout=TIMEOUT)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
    try:
        return r.json()
    except ValueError:
        raise RuntimeError(f"비JSON 응답: {r.text[:300]}")


def fetch_year(target, year):
    gte, lte = f"{year}0101", f"{year}1231"
    out, page = [], 1

    while True:
        data = request_page(target, gte, lte, page)

        msg = find_key(data, "resultMsg") or find_key(data, "returnAuthMsg")
        records = find_records(data)

        if not records:
            if page == 1:
                print(f"    {target['name']} {year}: 0건"
                      + (f" ({msg})" if msg else ""))
            break

        out.extend(records)
        total = find_key(data, "totalCount")
        total = int(total) if total is not None else None

        if len(records) < ROWS or (total and page * ROWS >= total):
            break
        page += 1
        time.sleep(SLEEP)

    if out:
        print(f"    {target['name']} {year}: {len(out)}건")
    return out


# ------------------------------------------------------------- 점검
def probe():
    print("[사전 점검]\n")
    for year in (2024, START_YEAR):
        try:
            data = request_page(TARGETS[0], f"{year}0101", f"{year}0107", 1, rows=10)
        except Exception as e:
            print(f"  {year}년: 실패 - {e}\n")
            continue

        records = find_records(data)
        total = find_key(data, "totalCount")
        print(f"  {year}년 -> totalCount={total}, 레코드 {len(records)}건")

        if records:
            print("    컬럼:", list(records[0].keys()))
            print("    샘플:", json.dumps(records[0], ensure_ascii=False)[:300])
        else:
            # 여기서 원인이 드러난다
            print("    !! 레코드 없음. 응답 원문:")
            print("   ", json.dumps(data, ensure_ascii=False, indent=2)[:900])
        print()


def main():
    probe()
    if "--probe" in sys.argv:
        return

    records = []
    for target in TARGETS:
        print(f"[{target['name']}]")
        for year in range(START_YEAR, END_YEAR + 1):
            try:
                records.extend(fetch_year(target, year))
            except Exception as e:
                print(f"    ! {year} 실패: {e}")
            time.sleep(SLEEP)

    if not records:
        print("\n수집 결과 없음. 위 점검 출력의 응답 원문을 확인하세요.")
        return

    df = pd.DataFrame(records)
    if "exmn_ymd" in df:
        df["조사일자"] = pd.to_datetime(df["exmn_ymd"].astype(str),
                                     format="%Y%m%d", errors="coerce")
    for col in ("exmn_dd_prc", "exmn_dd_cnvs_prc"):
        if col in df:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(",", ""), errors="coerce")

    df = df.drop_duplicates()
    df.to_csv("kamis_perday_raw.csv", index=False, encoding="utf-8-sig")
    print(f"\nkamis_perday_raw.csv 저장: {len(df)}행")

    if {"item_nm", "se_nm"} <= set(df.columns):
        print("\n구분별 건수:")
        print(df.groupby(["item_nm", "se_nm"]).size())
    if "조사일자" in df:
        print(f"\n기간: {df['조사일자'].min()} ~ {df['조사일자'].max()}")


if __name__ == "__main__":
    main()