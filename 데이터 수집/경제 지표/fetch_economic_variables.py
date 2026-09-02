#!/usr/bin/env python3
"""ECOS/KDI 경제변수를 영문 12개 컬럼의 일별 CSV로 수집한다."""

from __future__ import annotations

import argparse
import calendar
import csv
import json
import math
import os
import re
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


VERSION = "1.0.0"
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_ENV_FILE = SCRIPT_DIR / ".env"
DEFAULT_OUTPUT = SCRIPT_DIR / "output" / "economic_variables_daily.csv"
ECOS_BASE_URL = "https://ecos.bok.or.kr/api"
KDI_EPU_URL = "https://eiec.kdi.re.kr/bigdata/epu.do"
KST = timezone(timedelta(hours=9))

HEADERS = [
    "date",
    "gov_bond_3y_pct",
    "gov_bond_observation_date",
    "gov_bond_is_observed",
    "m2_yoy_pct",
    "m2_reference_month",
    "epu_index",
    "epu_reference_month",
    "ppi_index_2020_100",
    "ppi_reference_month",
    "cpi_yoy_pct",
    "cpi_reference_month",
]

NUMERIC_COLUMNS = (1, 4, 6, 8, 10)
REFERENCE_MONTH_COLUMNS = (5, 7, 9, 11)
MONTH_PATTERN = re.compile(r"^\d{6}$")


class CollectorError(RuntimeError):
    """사용자에게 그대로 표시해도 안전한 수집 오류."""


@dataclass(frozen=True)
class SeriesPoint:
    period: str
    value: float


@dataclass(frozen=True)
class CollectionResult:
    rows: list[list[str]]
    start_date: date
    end_date: date
    latest_common_month: str
    raw_counts: Mapping[str, int]


def parse_iso_date(value: str, option_name: str) -> date:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise CollectorError(f"{option_name}은 YYYY-MM-DD 형식이어야 합니다: {value}") from exc
    if parsed.isoformat() != value:
        raise CollectorError(f"{option_name}은 YYYY-MM-DD 형식이어야 합니다: {value}")
    return parsed


def month_key(value: date) -> str:
    return value.strftime("%Y%m")


def month_end(period: str) -> date:
    if not MONTH_PATTERN.fullmatch(period):
        raise CollectorError(f"잘못된 기준월입니다: {period}")
    year = int(period[:4])
    month = int(period[4:])
    return date(year, month, calendar.monthrange(year, month)[1])


def shift_month(value: date, months: int) -> date:
    zero_based = value.year * 12 + value.month - 1 + months
    year, month_index = divmod(zero_based, 12)
    return date(year, month_index + 1, 1)


def iter_dates(start: date, end: date) -> Iterable[date]:
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def parse_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError as exc:
        raise CollectorError(f"환경설정 파일을 읽을 수 없습니다: {path}") from exc

    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise CollectorError(f"환경설정 {line_number}행이 KEY=VALUE 형식이 아닙니다.")
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def read_api_key(env_file: Path) -> str:
    api_key = os.environ.get("ECOS_API_KEY", "").strip()
    if not api_key or api_key == "여기에_한국은행_ECOS_인증키를_입력하세요":
        api_key = parse_env_file(env_file).get("ECOS_API_KEY", "").strip()
    if not api_key or api_key == "여기에_한국은행_ECOS_인증키를_입력하세요":
        raise CollectorError(
            f"ECOS_API_KEY가 없습니다. {env_file}에 ECOS_API_KEY=발급받은키 형식으로 입력하세요."
        )
    if any(character.isspace() for character in api_key):
        raise CollectorError("ECOS_API_KEY에 공백 또는 줄바꿈이 포함되어 있습니다.")
    return api_key


class HttpClient:
    def __init__(
        self,
        *,
        attempts: int = 4,
        timeout_seconds: float = 30.0,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        if attempts < 1:
            raise ValueError("attempts must be at least 1")
        self.attempts = attempts
        self.timeout_seconds = timeout_seconds
        self.sleep_fn = sleep_fn

    def get_json(self, url: str, label: str) -> Any:
        last_reason = "알 수 없는 오류"
        for attempt in range(1, self.attempts + 1):
            try:
                request = Request(
                    url,
                    headers={"User-Agent": f"Economic-Variables-CSV-Fetcher/{VERSION}"},
                )
                with urlopen(request, timeout=self.timeout_seconds) as response:
                    charset = response.headers.get_content_charset() or "utf-8"
                    payload = response.read().decode(charset)
                return json.loads(payload)
            except HTTPError as exc:
                last_reason = f"HTTP {exc.code}"
                retryable = exc.code == 429 or 500 <= exc.code <= 599
                if not retryable:
                    raise CollectorError(f"{label} 요청 실패 ({last_reason})") from exc
            except (URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as exc:
                last_reason = type(exc).__name__

            if attempt < self.attempts:
                self.sleep_fn(0.4 * (2 ** (attempt - 1)))

        raise CollectorError(f"{label} 요청이 {self.attempts}회 실패했습니다 ({last_reason}).")


class EcosClient:
    def __init__(self, api_key: str, http: HttpClient, *, page_size: int = 1000) -> None:
        self.api_key = api_key
        self.http = http
        self.page_size = page_size

    def fetch_series(
        self,
        *,
        stat_code: str,
        cycle: str,
        start: str,
        end: str,
        item_code: str,
        label: str,
    ) -> list[SeriesPoint]:
        rows: list[dict[str, Any]] = []
        total_count: int | None = None
        offset = 1

        while total_count is None or len(rows) < total_count:
            last = offset + self.page_size - 1
            url = "/".join(
                [
                    ECOS_BASE_URL,
                    "StatisticSearch",
                    quote(self.api_key, safe=""),
                    "json",
                    "kr",
                    str(offset),
                    str(last),
                    stat_code,
                    cycle,
                    start,
                    end,
                    quote(item_code, safe=""),
                ]
            )
            payload = self.http.get_json(url, label)
            if not isinstance(payload, dict):
                raise CollectorError(f"{label}의 ECOS 응답 형식이 예상과 다릅니다.")
            if isinstance(payload.get("RESULT"), dict):
                result = payload["RESULT"]
                code = result.get("CODE", "UNKNOWN")
                message = str(result.get("MESSAGE", "요청을 처리할 수 없습니다.")).replace(
                    self.api_key, "[REDACTED]"
                )
                raise CollectorError(f"{label} ECOS 오류 {code}: {message}")

            result = payload.get("StatisticSearch")
            if not isinstance(result, dict) or not isinstance(result.get("row"), list):
                raise CollectorError(f"{label}의 ECOS 응답 구조가 변경되었거나 데이터가 없습니다.")
            try:
                total_count = int(result["list_total_count"])
            except (KeyError, TypeError, ValueError) as exc:
                raise CollectorError(f"{label}의 ECOS 전체 건수를 확인할 수 없습니다.") from exc

            page_rows = result["row"]
            if not page_rows:
                raise CollectorError(f"{label} 페이지에 데이터가 없습니다.")
            rows.extend(page_rows)
            offset += self.page_size

        points: list[SeriesPoint] = []
        seen_periods: set[str] = set()
        for row in rows[:total_count]:
            try:
                period = str(row["TIME"])
                value = float(str(row["DATA_VALUE"]).replace(",", ""))
            except (KeyError, TypeError, ValueError) as exc:
                raise CollectorError(f"{label} 응답에 잘못된 관측값이 있습니다.") from exc
            if period in seen_periods:
                raise CollectorError(f"{label}에 중복 기준시점이 있습니다: {period}")
            if not math.isfinite(value):
                raise CollectorError(f"{label}에 유효하지 않은 숫자가 있습니다: {period}")
            seen_periods.add(period)
            points.append(SeriesPoint(period, value))

        if not points:
            raise CollectorError(f"{label} 데이터가 없습니다.")
        return sorted(points, key=lambda point: point.period)


def calculate_year_over_year(points: Sequence[SeriesPoint]) -> dict[str, float]:
    levels = {point.period: point.value for point in points}
    output: dict[str, float] = {}
    for point in points:
        if not MONTH_PATTERN.fullmatch(point.period):
            raise CollectorError(f"월별 원자료의 기준월 형식이 잘못되었습니다: {point.period}")
        prior_period = f"{int(point.period[:4]) - 1}{point.period[4:]}"
        prior = levels.get(prior_period)
        if prior is not None:
            if prior == 0:
                raise CollectorError(f"전년동월비를 계산할 기준값이 0입니다: {prior_period}")
            output[point.period] = (point.value / prior - 1.0) * 100.0
    return output


def parse_kdi_epu(payload: Any) -> dict[str, float]:
    if not isinstance(payload, list):
        raise CollectorError("KDI EPU 응답 형식이 예상과 다릅니다.")
    output: dict[str, float] = {}
    for row in payload:
        if not isinstance(row, dict):
            raise CollectorError("KDI EPU 응답에 잘못된 행이 있습니다.")
        period = str(row.get("date", ""))
        if not MONTH_PATTERN.fullmatch(period):
            raise CollectorError(f"KDI EPU 기준월 형식이 잘못되었습니다: {period or '(빈 값)'}")
        try:
            value = float(row["한국 EPU 지수"])
        except (KeyError, TypeError, ValueError) as exc:
            raise CollectorError(f"KDI EPU 값이 잘못되었습니다: {period}") from exc
        if period in output:
            raise CollectorError(f"KDI EPU에 중복 기준월이 있습니다: {period}")
        if not math.isfinite(value):
            raise CollectorError(f"KDI EPU에 유효하지 않은 숫자가 있습니다: {period}")
        output[period] = value
    if not output:
        raise CollectorError("KDI EPU 데이터가 없습니다.")
    return output


def format_number(value: float, digits: int) -> str:
    if not math.isfinite(value):
        raise CollectorError("CSV에 기록할 숫자가 유효하지 않습니다.")
    text = f"{value:.{digits}f}".rstrip("0").rstrip(".")
    return "0" if text in {"-0", ""} else text


def build_daily_rows(
    *,
    start_date: date,
    end_date: date,
    bond_by_date: Mapping[date, float],
    m2_yoy_by_month: Mapping[str, float],
    epu_by_month: Mapping[str, float],
    ppi_by_month: Mapping[str, float],
    cpi_yoy_by_month: Mapping[str, float],
) -> list[list[str]]:
    if end_date < start_date:
        raise CollectorError("종료일은 시작일보다 빠를 수 없습니다.")

    prior_bond_dates = [observed for observed in bond_by_date if observed <= start_date]
    if not prior_bond_dates:
        raise CollectorError("시작일 이전 또는 당일의 국고채 관측값이 없습니다.")
    last_bond_date = max(prior_bond_dates)
    last_bond_value = bond_by_date[last_bond_date]
    rows: list[list[str]] = []

    for current in iter_dates(start_date, end_date):
        if current in bond_by_date:
            last_bond_date = current
            last_bond_value = bond_by_date[current]
        period = month_key(current)
        missing = [
            name
            for name, series in (
                ("M2", m2_yoy_by_month),
                ("EPU", epu_by_month),
                ("PPI", ppi_by_month),
                ("CPI", cpi_yoy_by_month),
            )
            if period not in series
        ]
        if missing:
            raise CollectorError(f"{period} 기준월에 필수 지표가 없습니다: {', '.join(missing)}")

        rows.append(
            [
                current.isoformat(),
                format_number(last_bond_value, 6),
                last_bond_date.isoformat(),
                "1" if current in bond_by_date else "0",
                format_number(m2_yoy_by_month[period], 8),
                period,
                format_number(epu_by_month[period], 8),
                period,
                format_number(ppi_by_month[period], 6),
                period,
                format_number(cpi_yoy_by_month[period], 8),
                period,
            ]
        )
    return rows


def validate_rows(rows: Sequence[Sequence[str]], expected_start: date, expected_end: date) -> None:
    expected_count = (expected_end - expected_start).days + 1
    if len(rows) != expected_count:
        raise CollectorError(f"행 수가 예상과 다릅니다: 예상 {expected_count}, 실제 {len(rows)}")

    seen_dates: set[date] = set()
    previous_date: date | None = None
    previous_observation_date: date | None = None
    for row_number, row in enumerate(rows, start=2):
        if len(row) != len(HEADERS):
            raise CollectorError(f"CSV {row_number}행의 컬럼 수가 {len(HEADERS)}개가 아닙니다.")
        if any(value == "" for value in row):
            raise CollectorError(f"CSV {row_number}행에 결측값이 있습니다.")
        try:
            current = date.fromisoformat(row[0])
            observation_date = date.fromisoformat(row[2])
        except ValueError as exc:
            raise CollectorError(f"CSV {row_number}행의 날짜 형식이 잘못되었습니다.") from exc
        if current in seen_dates:
            raise CollectorError(f"중복 날짜가 있습니다: {current.isoformat()}")
        if previous_date is not None and current != previous_date + timedelta(days=1):
            raise CollectorError(f"날짜가 연속적이지 않습니다: {previous_date} 다음 {current}")
        if observation_date > current:
            raise CollectorError(f"국고채 실제관측일이 기준일보다 늦습니다: {current}")
        if previous_observation_date is not None and observation_date < previous_observation_date:
            raise CollectorError(f"국고채 실제관측일이 역순입니다: {current}")

        observed_flag = row[3]
        if observed_flag not in {"0", "1"}:
            raise CollectorError(f"국고채 당일관측여부가 0 또는 1이 아닙니다: {current}")
        if (observed_flag == "1") != (observation_date == current):
            raise CollectorError(f"국고채 관측일과 당일관측여부가 일치하지 않습니다: {current}")

        expected_month = month_key(current)
        for column_index in REFERENCE_MONTH_COLUMNS:
            if row[column_index] != expected_month:
                raise CollectorError(
                    f"CSV {row_number}행의 {HEADERS[column_index]}가 날짜 기준월과 다릅니다."
                )
        for column_index in NUMERIC_COLUMNS:
            try:
                numeric_value = float(row[column_index])
            except ValueError as exc:
                raise CollectorError(
                    f"CSV {row_number}행의 {HEADERS[column_index]}가 숫자가 아닙니다."
                ) from exc
            if not math.isfinite(numeric_value):
                raise CollectorError(
                    f"CSV {row_number}행의 {HEADERS[column_index]}가 유효한 숫자가 아닙니다."
                )

        seen_dates.add(current)
        previous_date = current
        previous_observation_date = observation_date

    if rows and rows[0][0] != expected_start.isoformat():
        raise CollectorError("CSV 첫 날짜가 요청 시작일과 다릅니다.")
    if rows and rows[-1][0] != expected_end.isoformat():
        raise CollectorError("CSV 마지막 날짜가 요청 종료일과 다릅니다.")


def validate_csv_file(path: Path, expected_start: date, expected_end: date) -> None:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            header = next(reader, None)
            rows = list(reader)
    except OSError as exc:
        raise CollectorError(f"작성된 CSV를 다시 읽을 수 없습니다: {path}") from exc
    if header != HEADERS:
        raise CollectorError("작성된 CSV의 컬럼명 또는 순서가 기준과 다릅니다.")
    validate_rows(rows, expected_start, expected_end)


def write_csv_atomically(
    output_path: Path,
    rows: Sequence[Sequence[str]],
    start_date: date,
    end_date: date,
) -> None:
    validate_rows(rows, start_date, end_date)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=output_path.parent,
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(HEADERS)
            writer.writerows(rows)
            handle.flush()
            os.fsync(handle.fileno())
        validate_csv_file(temp_path, start_date, end_date)
        os.replace(temp_path, output_path)
        temp_path = None
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass


def collect_dataset(
    *,
    api_key: str,
    start_date: date,
    requested_end_date: date | None,
    today: date | None = None,
    http: HttpClient | None = None,
) -> CollectionResult:
    today = today or datetime.now(KST).date()
    if start_date > today:
        raise CollectorError("시작일은 오늘보다 늦을 수 없습니다.")
    if requested_end_date is not None:
        if requested_end_date < start_date:
            raise CollectorError("종료일은 시작일보다 빠를 수 없습니다.")
        if requested_end_date > today:
            raise CollectorError("종료일은 오늘보다 늦을 수 없습니다.")

    http = http or HttpClient()
    ecos = EcosClient(api_key, http)
    monthly_start = shift_month(start_date.replace(day=1), -12).strftime("%Y%m")
    monthly_end_date = requested_end_date or today
    monthly_end = month_key(monthly_end_date)

    with ThreadPoolExecutor(max_workers=4) as executor:
        m2_future = executor.submit(
            ecos.fetch_series,
            stat_code="161Y006",
            cycle="M",
            start=monthly_start,
            end=monthly_end,
            item_code="BBHA00",
            label="M2 평잔 원계열",
        )
        ppi_future = executor.submit(
            ecos.fetch_series,
            stat_code="404Y014",
            cycle="M",
            start=month_key(start_date),
            end=monthly_end,
            item_code="*AA",
            label="생산자물가지수 총지수",
        )
        cpi_future = executor.submit(
            ecos.fetch_series,
            stat_code="901Y009",
            cycle="M",
            start=monthly_start,
            end=monthly_end,
            item_code="0",
            label="소비자물가지수 총지수",
        )
        epu_future = executor.submit(http.get_json, KDI_EPU_URL, "KDI EPU")
        m2_points = m2_future.result()
        ppi_points = ppi_future.result()
        cpi_points = cpi_future.result()
        epu_payload = epu_future.result()

    m2_yoy = calculate_year_over_year(m2_points)
    ppi_by_month = {point.period: point.value for point in ppi_points}
    cpi_yoy = calculate_year_over_year(cpi_points)
    epu_by_month = parse_kdi_epu(epu_payload)

    common_months = (
        set(m2_yoy)
        & set(ppi_by_month)
        & set(cpi_yoy)
        & set(epu_by_month)
    )
    common_months = {
        period
        for period in common_months
        if month_key(start_date) <= period <= month_key(today)
    }
    if not common_months:
        raise CollectorError("요청 기간에 네 월별 지표가 모두 존재하는 공통 기준월이 없습니다.")
    latest_common_month = max(common_months)
    automatic_end = min(month_end(latest_common_month), today)
    end_date = requested_end_date or automatic_end

    required_months = {month_key(current) for current in iter_dates(start_date, end_date)}
    missing_by_series = {
        "M2": sorted(required_months - set(m2_yoy)),
        "EPU": sorted(required_months - set(epu_by_month)),
        "PPI": sorted(required_months - set(ppi_by_month)),
        "CPI": sorted(required_months - set(cpi_yoy)),
    }
    missing_messages = [
        f"{name}({', '.join(periods)})"
        for name, periods in missing_by_series.items()
        if periods
    ]
    if missing_messages:
        raise CollectorError("요청 종료일까지 발표되지 않은 기준월이 있습니다: " + "; ".join(missing_messages))

    bond_query_start = start_date - timedelta(days=62)
    bond_points = ecos.fetch_series(
        stat_code="817Y002",
        cycle="D",
        start=bond_query_start.strftime("%Y%m%d"),
        end=end_date.strftime("%Y%m%d"),
        item_code="010200000",
        label="국고채 3년 유통수익률",
    )
    bond_by_date: dict[date, float] = {}
    for point in bond_points:
        try:
            observed_date = datetime.strptime(point.period, "%Y%m%d").date()
        except ValueError as exc:
            raise CollectorError(f"국고채 관측일 형식이 잘못되었습니다: {point.period}") from exc
        bond_by_date[observed_date] = point.value

    if not any(month_key(observed) == month_key(end_date) for observed in bond_by_date):
        raise CollectorError(f"종료월 {month_key(end_date)}에 국고채 실제 관측값이 없습니다.")

    rows = build_daily_rows(
        start_date=start_date,
        end_date=end_date,
        bond_by_date=bond_by_date,
        m2_yoy_by_month=m2_yoy,
        epu_by_month=epu_by_month,
        ppi_by_month=ppi_by_month,
        cpi_yoy_by_month=cpi_yoy,
    )
    validate_rows(rows, start_date, end_date)
    return CollectionResult(
        rows=rows,
        start_date=start_date,
        end_date=end_date,
        latest_common_month=latest_common_month,
        raw_counts={
            "gov_bond_3y": len(bond_points),
            "m2": len(m2_points),
            "epu": len(epu_by_month),
            "ppi": len(ppi_points),
            "cpi": len(cpi_points),
        },
    )


# CSV 헤더 → econ_daily_raw 컬럼. 12개가 1:1 로 대응한다.
DB_COLUMNS = [
    "dt", "gov_bond_3y_rt", "gov_bond_obs_dt", "gov_bond_obs_yn",
    "m2_yoy_rt", "m2_ref_mon", "epu_idx", "epu_ref_mon",
    "ppi_idx", "ppi_ref_mon", "cpi_yoy_rt", "cpi_ref_mon",
]
_DB_NUM = {1, 4, 6, 8, 10}     # HEADERS 기준 숫자 열
_DB_INT = {3}                  # gov_bond_is_observed


def load_to_db(rows: list[list[str]]) -> int:
    """CSV 를 거치지 않고 econ_daily_raw 에 넣는다.

    행은 문자열이지만 **DB 에 넣기 전에 파이썬 타입으로 되돌린다.**
    CSV 를 경유하면 이 변환을 로더가 다시 해야 하고, 규칙이 갈라질 자리가 생긴다.

    ECOS 는 수정 후 시계열이라 과거 값이 정정될 수 있으므로 덮어쓴다(DO UPDATE).
    덮어쓰기 전에 겹치는 구간의 불일치 건수를 보여준다.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    try:
        import _dbload
    except ImportError as exc:
        print(f"오류: 공용 적재 모듈을 찾지 못했습니다 ({exc})", file=sys.stderr)
        return 1

    typed = []
    for r in rows:
        v = []
        for i, x in enumerate(r):
            x = (x or "").strip()
            if i in _DB_NUM:
                v.append(float(x) if x else None)
            elif i in _DB_INT:
                v.append(int(float(x)) if x else None)
            else:
                v.append(x or None)
        typed.append(v)

    print("[DB 적재] econ_daily_raw")
    try:
        _dbload.upsert(
            "econ_daily_raw", DB_COLUMNS, typed,
            conflict="(dt)", key_cols=["dt"],
            compare=["gov_bond_3y_rt", "m2_yoy_rt", "epu_idx", "ppi_idx", "cpi_yoy_rt"],
            do_update=True, label="econ",
        )
    except Exception as exc:                                 # noqa: BLE001
        print(f"오류: DB 적재 실패 — {exc}", file=sys.stderr)
        return 1
    return 0


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="ECOS와 KDI에서 경제변수를 받아 영문 12개 컬럼의 일별 CSV를 생성합니다."
    )
    parser.add_argument("--start-date", default="2015-01-01", help="시작일 YYYY-MM-DD (기본: 2015-01-01)")
    parser.add_argument(
        "--end-date",
        help="종료일 YYYY-MM-DD (생략: 네 월별 지표의 최신 공통 기준월 말일)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="출력 CSV 경로 (기본: 도구폴더/output/economic_variables_daily.csv)",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=DEFAULT_ENV_FILE,
        help="ECOS_API_KEY가 들어 있는 환경설정 파일 (기본: 도구폴더/.env)",
    )
    parser.add_argument(
        "--load-db",
        action="store_true",
        help="CSV 를 거치지 않고 econ_daily_raw 에 바로 적재합니다",
    )
    parser.add_argument(
        "--no-csv",
        action="store_true",
        help="CSV 를 만들지 않습니다 (--load-db 와 함께 쓰세요)",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return parser


def run(argv: Sequence[str] | None = None) -> int:
    args = build_argument_parser().parse_args(argv)
    try:
        start_date = parse_iso_date(args.start_date, "--start-date")
        requested_end = parse_iso_date(args.end_date, "--end-date") if args.end_date else None
        api_key = read_api_key(args.env_file.expanduser().resolve())
        result = collect_dataset(
            api_key=api_key,
            start_date=start_date,
            requested_end_date=requested_end,
        )
        output_path = args.output.expanduser().resolve()
        if args.no_csv and not args.load_db:
            print("오류: --no-csv 는 --load-db 와 함께 써야 합니다.", file=sys.stderr)
            return 1
        if not args.no_csv:
            write_csv_atomically(output_path, result.rows, result.start_date, result.end_date)
    except CollectorError as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1

    if args.load_db:
        rc = load_to_db(result.rows)
        if rc:
            return rc

    print(f"완료: {output_path if not args.no_csv else '(CSV 미생성)'}")
    print(f"기간: {result.start_date.isoformat()} ~ {result.end_date.isoformat()}")
    print(f"데이터 행: {len(result.rows):,}개 / 컬럼: {len(HEADERS)}개 / 결측값: 0개")
    print(f"최신 공통 기준월: {result.latest_common_month}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
