# -*- coding: utf-8 -*-
"""
공휴일 수집기 — 한국천문연구원 특일 정보제공 서비스
====================================================
`getRestDeInfo` 로 공휴일을 받아 `ref_holiday` 로 적재한다.
`ref_calendar`(개장일 달력)의 입력이 되는 기준 데이터다.

왜 필요한가
    미래 기준일에서 리드타임 1~18영업일을 세려면 앞으로의 휴일을 알아야 한다.
    그런데 우리 축은 두 개이고 규칙이 서로 다르다.

        중도매가 조사일   토·일 + 공휴일 + 12월 첫째 금요일        휴무
        가락 경매 거래일  일 + 신정 1/1~1/2 + 명절 당일~+2일
                          + 8월 첫 토요일 + 비정기                 휴장

    두 축 모두 "공휴일이 언제인가" 를 입력으로 쓴다. 그걸 이 API 가 준다.
    양력 고정 공휴일·음력 명절 연휴·대체공휴일·임시공휴일이 모두 포함된다.

    실측 대조(2015~2025, 배추 중도매가 조사일 2,700일)에서
    조사일 축의 결측 평일 170일 중 165일이 공휴일로 설명됐고,
    나머지는 12월 첫째 금요일 11일(11년 연속)뿐이었다.

한계 — 알고 쓸 것
    1. 현재연도 +2년까지만 나온다. 과기부 월력요항 발표(6~8월) 이후
       차차년도가 올라온다. 그 이후 연도는 확정 불가이므로 매년 갱신해야 한다.
    2. 임시공휴일은 지정된 뒤에야 반영된다(최대 1일). 대체공휴일은 대통령령
       시행 이후. 즉 **예측 시점에 알 수 없는 휴일이 원리적으로 존재한다.**
       과거 재현에는 문제가 없고, 미래 추론에서만 리드타임이 어긋날 수 있다.
    3. 갱신 주기가 연 1회이므로 매일 호출할 이유가 없다. 캐시를 쓴다.

사용법
    pip install requests            # DB 적재까지 하려면 psycopg[binary] 추가

    # 1) .env 에 DATA_GO_KR_SERVICE_KEY 를 넣는다
    # 2) 연결 확인 (1개 연도만, 캐시 무시)
    python fetch_holidays.py --start-year 2026 --end-year 2026 --no-cache

    # 3) 전 구간 수집 → CSV + DBeaver 용 SQL
    python fetch_holidays.py

    # 4) PostgreSQL 직접 적재 (DATABASE_URL 필요)
    python fetch_holidays.py --load-db

산출물
    ref_holiday.csv    적재용 (UTF-8 BOM 없음)
    ref_holiday.sql    DBeaver 에서 Alt+X 로 실행. CREATE + TRUNCATE + INSERT
    work/YYYY.json     연도별 원본 응답 캐시
"""
import argparse
import csv
import datetime as dt
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import quote

import requests

BASE = "http://apis.data.go.kr/B090041/openapi/service/SpcdeInfoService"
OP = "getRestDeInfo"          # 공휴일 정보조회. 제헌절 등 비휴일 국경일은 제외된다
TABLE = "ref_holiday"
TIMEOUT = 30
MAX_RETRY = 4
SLEEP = 0.25                  # 30 TPS 제한. 연 단위 호출이라 여유롭다

HERE = Path(__file__).resolve().parent


# ── .env ────────────────────────────────────────────────────────────────
def load_dotenv(path: Path) -> None:
    """auction_collector 와 같은 방식. 이미 있는 환경변수를 덮지 않는다."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1]
        os.environ.setdefault(k.strip(), v)


def key_param(key: str) -> str:
    """
    공공데이터포털은 인코딩 키와 디코딩 키 두 형태를 준다.
      · 인코딩 키에는 %2B 같은 % 가 들어 있다 → 다시 인코딩하면 깨진다
      · 디코딩 키에는 + / = 가 들어 있다      → 인코딩하지 않으면 깨진다
    이 구분을 안 해서 SERVICE_KEY_IS_NOT_REGISTERED_ERROR 를 만나는 경우가 많다.
    """
    return key if "%" in key else quote(key, safe="")


# ── API ─────────────────────────────────────────────────────────────────
class HolidayApi:
    def __init__(self, service_key: str):
        if not service_key:
            raise SystemExit(
                "DATA_GO_KR_SERVICE_KEY 가 비어 있습니다.\n"
                "  .env 파일에 키를 넣으세요. 공공데이터포털에서 '특일 정보' 활용신청(자동 승인).")
        self.key = key_param(service_key)
        self.calls = 0

    def _url(self, year: int, page: int, rows: int, month: int | None) -> str:
        q = [f"serviceKey={self.key}", f"solYear={year}",
             "_type=json", f"numOfRows={rows}", f"pageNo={page}"]
        if month:
            q.append(f"solMonth={month:02d}")
        return f"{BASE}/{OP}?" + "&".join(q)

    def _get(self, url: str) -> dict:
        last = None
        for attempt in range(MAX_RETRY):
            try:
                r = requests.get(url, timeout=TIMEOUT,
                                 headers={"Accept": "application/json"})
                if r.status_code != 200:
                    last = f"HTTP {r.status_code}"
                else:
                    try:
                        return r.json()
                    except ValueError:
                        # 인증 실패·트래픽 초과는 JSON 이 아니라 XML/HTML 로 온다
                        body = r.text.strip()[:400]
                        for token, msg in (
                            ("SERVICE_KEY_IS_NOT_REGISTERED", "서비스키가 등록되지 않았습니다. 활용신청 승인과 키 형태를 확인하세요."),
                            ("LIMITED_NUMBER_OF_SERVICE_REQUESTS", "일일 트래픽을 초과했습니다."),
                            ("SERVICE_ACCESS_DENIED", "서비스 접근이 거부됐습니다. 활용신청 상태를 확인하세요."),
                            ("HTTP_ERROR", "요청 형식 오류입니다."),
                        ):
                            if token in body:
                                raise SystemExit(f"[API] {msg}\n  응답: {body}")
                        last = f"JSON 아님: {body}"
            except requests.RequestException as e:
                last = str(e)
            time.sleep(0.6 * (attempt + 1))
        raise SystemExit(f"[API] 호출 실패 ({MAX_RETRY}회 재시도): {last}")

    def fetch_year(self, year: int) -> list[dict]:
        """
        solMonth 는 옵션이라 연 단위로 한 번에 받는다(연 12회 → 1회).
        totalCount 와 실제 수신 건수를 대조해 누락이 있으면 페이지를 넘긴다.
        """
        rows, page, out, total = 100, 1, [], None
        while True:
            js = self._get(self._url(year, page, rows, None))
            self.calls += 1
            resp = js.get("response", {})
            head = resp.get("header", {})
            code = str(head.get("resultCode", ""))
            if code not in ("00", "0"):
                raise SystemExit(f"[API] {year}년 resultCode={code} "
                                 f"({head.get('resultMsg')})")
            body = resp.get("body", {}) or {}
            total = int(body.get("totalCount") or 0)
            items = body.get("items") or {}
            if isinstance(items, str):        # totalCount 0 이면 빈 문자열로 온다
                items = {}
            item = items.get("item", [])
            if isinstance(item, dict):        # 1건이면 리스트가 아니라 객체
                item = [item]
            out.extend(item)
            if len(out) >= total or not item:
                break
            page += 1
            time.sleep(SLEEP)
        if total is not None and len(out) != total:
            print(f"  [주의] {year}년 totalCount {total} != 수신 {len(out)}")
        return out


# ── 정규화 ──────────────────────────────────────────────────────────────
def normalize(raw: list[dict]) -> list[dict]:
    out = []
    for r in raw:
        loc = str(r.get("locdate", "")).strip()
        if len(loc) != 8 or not loc.isdigit():
            continue
        out.append({
            "dt": f"{loc[:4]}-{loc[4:6]}-{loc[6:]}",
            "date_name": str(r.get("dateName", "")).strip(),
            "date_kind": str(r.get("dateKind", "")).strip(),
            "is_holiday": "Y" if str(r.get("isHoliday", "")).strip().upper() == "Y" else "N",
            "seq": int(r.get("seq") or 1),
        })
    # 같은 날 두 명칭이 겹칠 수 있다(설날 + 대체공휴일 등). 날짜+명칭으로 유일화.
    seen, uniq = set(), []
    for r in sorted(out, key=lambda x: (x["dt"], x["seq"])):
        k = (r["dt"], r["date_name"])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(r)
    return uniq


# ── 산출물 ──────────────────────────────────────────────────────────────
COLS = ["dt", "date_name", "date_kind", "is_holiday", "seq"]

DDL = f"""CREATE TABLE IF NOT EXISTS {TABLE} (
    dt          date        NOT NULL,
    date_name   varchar(50) NOT NULL,
    date_kind   varchar(2),
    is_holiday  boolean     NOT NULL,
    seq         smallint,
    PRIMARY KEY (dt, date_name)
);
COMMENT ON TABLE {TABLE} IS
  '한국천문연구원 특일 정보(getRestDeInfo) 원본. ref_calendar 의 입력. 매년 갱신 필요';
CREATE INDEX IF NOT EXISTS {TABLE}_dt_idx ON {TABLE} (dt) WHERE is_holiday;
"""


def write_csv(rows: list[dict], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)


def write_sql(rows: list[dict], path: Path, y0: int, y1: int) -> None:
    def lit(s: str) -> str:
        return "'" + s.replace("'", "''") + "'"

    parts = [
        "-- ============================================================",
        f"-- {TABLE} — 공휴일 기준 데이터 ({y0}~{y1})",
        "--   출처: 한국천문연구원 특일 정보제공 서비스 getRestDeInfo",
        "--   생성: fetch_holidays.py — 손으로 고치지 말고 재수집할 것",
        "--   ※ 현재연도 +2년까지만 확정된다. 매년 갱신 필요.",
        "-- ============================================================",
        DDL,
        f"TRUNCATE {TABLE};",
        f"INSERT INTO {TABLE} (dt, date_name, date_kind, is_holiday, seq) VALUES",
    ]
    vals = [f"  ({lit(r['dt'])}, {lit(r['date_name'])}, {lit(r['date_kind'])}, "
            f"{'true' if r['is_holiday'] == 'Y' else 'false'}, {r['seq']})"
            for r in rows]
    parts.append(",\n".join(vals) + ";")
    parts.append("")
    parts.append("-- 확인: 연도별 공휴일 수. 15~20건이 정상. 0 이면 수집 실패")
    parts.append(f"SELECT EXTRACT(YEAR FROM dt)::int AS yr, COUNT(*) FILTER (WHERE is_holiday) AS 공휴일,"
                 f" MIN(dt) AS 처음, MAX(dt) AS 마지막\n  FROM {TABLE} GROUP BY 1 ORDER BY 1;")
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def load_db(rows: list[dict], url: str) -> None:
    try:
        import psycopg
    except ImportError:
        raise SystemExit("psycopg 가 없습니다.  pip install \"psycopg[binary]\"")
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        cur.execute(DDL)
        cur.execute(f"TRUNCATE {TABLE}")
        cur.executemany(
            f"INSERT INTO {TABLE} (dt, date_name, date_kind, is_holiday, seq)"
            f" VALUES (%s, %s, %s, %s, %s)",
            [(r["dt"], r["date_name"], r["date_kind"], r["is_holiday"] == "Y", r["seq"])
             for r in rows])
        conn.commit()
    print(f"DB 적재 완료: {TABLE} {len(rows):,}행")


# ── main ────────────────────────────────────────────────────────────────
def main() -> None:
    #   폴더 -> 루트 순 (2026-09-04 · S-01). 먼저 읽은 값이 이긴다.
    load_dotenv(HERE / ".env")
    load_dotenv(HERE.parents[1] / ".env")
    this_year = dt.date.today().year

    ap = argparse.ArgumentParser(description="한국천문연구원 특일 정보 수집")
    ap.add_argument("--start-year", type=int, default=2015)
    ap.add_argument("--end-year", type=int, default=this_year + 2,
                    help="기본은 올해+2년. API 가 그 이상은 주지 않는다")
    ap.add_argument("--out", default=str(HERE / "ref_holiday.csv"))
    ap.add_argument("--sql", default=str(HERE / "ref_holiday.sql"))
    ap.add_argument("--cache-dir", default=str(HERE / "work"))
    ap.add_argument("--no-cache", action="store_true", help="캐시를 무시하고 다시 받는다")
    ap.add_argument("--load-db", action="store_true", help="DATABASE_URL 로 직접 적재")
    a = ap.parse_args()

    #   ★ 경락가 폴더의 같은 이름은 **다른 값**이다. 쓰임 이름을 먼저 본다.
    api = HolidayApi(os.environ.get("HOLIDAY_KEY", "").strip()
                     or os.environ.get("DATA_GO_KR_SERVICE_KEY", "").strip())
    cache = Path(a.cache_dir)
    cache.mkdir(parents=True, exist_ok=True)

    raw: list[dict] = []
    for year in range(a.start_year, a.end_year + 1):
        cf = cache / f"{year}.json"
        if cf.exists() and not a.no_cache:
            got = json.loads(cf.read_text(encoding="utf-8"))
            src = "캐시"
        else:
            got = api.fetch_year(year)
            cf.write_text(json.dumps(got, ensure_ascii=False), encoding="utf-8")
            src = "수집"
            time.sleep(SLEEP)
        raw.extend(got)
        print(f"  {year}  {len(got):3d}건  ({src})")

    rows = normalize(raw)
    hol = [r for r in rows if r["is_holiday"] == "Y"]
    print(f"\n총 {len(rows):,}건 · 공휴일 {len(hol):,}건 · API 호출 {api.calls}회")

    if not hol:
        raise SystemExit("공휴일이 한 건도 없습니다. 키와 응답을 확인하세요.")

    write_csv(rows, Path(a.out))
    write_sql(rows, Path(a.sql), a.start_year, a.end_year)
    print(f"저장: {a.out}\n      {a.sql}")

    if a.load_db:
        url = os.environ.get("DATABASE_URL", "").strip()
        if not url:
            raise SystemExit("DATABASE_URL 이 없습니다. .env 를 확인하세요.")
        load_db(rows, url)

    # ── 자체 점검 ────────────────────────────────────────────────
    #   연도별 공휴일 수가 15~20건을 벗어나면 수집이 덜 됐다는 뜻이다.
    print("\n[연도별 공휴일 수]")
    by_year: dict[int, int] = {}
    for r in hol:
        by_year[int(r["dt"][:4])] = by_year.get(int(r["dt"][:4]), 0) + 1
    warn = []
    for y in range(a.start_year, a.end_year + 1):
        n = by_year.get(y, 0)
        flag = "" if 14 <= n <= 24 else "   <-- 확인 필요"
        if flag:
            warn.append(y)
        print(f"  {y}  {n:2d}{flag}")
    if warn:
        print(f"\n[주의] {warn} 연도의 건수가 통상 범위를 벗어납니다.")
        print("       API 가 아직 해당 연도를 발표하지 않았을 수 있습니다"
              " (현재연도 +2년까지만 확정).")

    # 12월 첫째 금요일은 공휴일이 아니다 — 조사일 축에서 따로 처리해야 한다는 확인
    print("\n[참고] 12월 첫째 금요일은 공휴일이 아니므로 이 표에 없습니다.")
    print("       중도매가 조사일 축에서 별도 규칙으로 처리하세요 (11년 연속 미조사).")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
