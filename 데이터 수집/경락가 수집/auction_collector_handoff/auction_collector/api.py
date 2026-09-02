from __future__ import annotations

import json
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable, Iterable, Mapping

from .constants import API_URL, DEFAULT_ITEMS, ItemSpec


class ApiError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class HttpResult:
    status: int
    headers: Mapping[str, str]
    body: bytes


@dataclass(frozen=True, slots=True)
class QueryPlan:
    filters: tuple[tuple[str, str, str], ...]
    allowed: frozenset[str]


Transport = Callable[[str, float], HttpResult]


def default_transport(url: str, timeout: float) -> HttpResult:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return HttpResult(
                int(response.status),
                {key.lower(): value for key, value in response.headers.items()},
                response.read(),
            )
    except urllib.error.HTTPError as error:
        return HttpResult(
            int(error.code),
            {key.lower(): value for key, value in error.headers.items()},
            error.read(),
        )


def build_query_plans(items: tuple[ItemSpec, ...]) -> tuple[QueryPlan, ...]:
    if items == DEFAULT_ITEMS:
        return (
            QueryPlan(
                (("gds_lclsf_cd", "LIKE", "1_"), ("gds_mclsf_cd", "EQ", "01")),
                frozenset(("10-01", "11-01", "12-01")),
            ),
            QueryPlan(
                (("gds_lclsf_cd", "EQ", "12"), ("gds_mclsf_cd", "EQ", "07")),
                frozenset(("12-07",)),
            ),
            QueryPlan(
                (("gds_lclsf_cd", "EQ", "12"), ("gds_mclsf_cd", "EQ", "09")),
                frozenset(("12-09",)),
            ),
        )
    return tuple(
        QueryPlan(
            (("gds_lclsf_cd", "EQ", item.large_code), ("gds_mclsf_cd", "EQ", item.middle_code)),
            frozenset((item.api_key,)),
        )
        for item in items
    )


def _as_list(value: object) -> list[dict[str, object]]:
    if value is None:
        return []
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        return [value]
    return []


class DataGoClient:
    def __init__(
        self,
        service_key: str,
        *,
        endpoint: str = API_URL,
        page_size: int = 10_000,
        timeout: float = 90.0,
        max_retries: int = 6,
        transport: Transport = default_transport,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if not service_key:
            raise ValueError("DATA_GO_KR_SERVICE_KEY가 필요합니다.")
        if page_size < 1:
            raise ValueError("page_size는 1 이상이어야 합니다.")
        self.service_key = service_key
        self.endpoint = endpoint
        self.page_size = page_size
        self.timeout = timeout
        self.max_retries = max_retries
        self.transport = transport
        self.sleeper = sleeper
        self.api_calls = 0
        self.retries = 0
        self.rate_limit_remaining: int | None = None

    def _url(self, date: str, plan: QueryPlan, page: int) -> str:
        params: list[tuple[str, str]] = [
            ("serviceKey", self.service_key),
            ("returnType", "json"),
            ("pageNo", str(page)),
            ("numOfRows", str(self.page_size)),
            ("cond[trd_clcln_ymd::EQ]", date),
            ("cond[whsl_mrkt_cd::LIKE]", "%"),
        ]
        for name, operator, value in plan.filters:
            params.append((f"cond[{name}::{operator}]", value))
        return f"{self.endpoint}?{urllib.parse.urlencode(params)}"

    def _request(self, date: str, plan: QueryPlan, page: int) -> dict[str, object]:
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                result = self.transport(self._url(date, plan, page), self.timeout)
                self.api_calls += 1
                remaining = result.headers.get("x-ratelimit-remaining")
                if remaining is not None:
                    try:
                        self.rate_limit_remaining = int(remaining)
                    except ValueError:
                        pass
                if result.status == 429 or result.status >= 500:
                    raise ApiError(f"재시도 가능한 HTTP 오류: {result.status}")
                if result.status < 200 or result.status >= 300:
                    raise ApiError(f"HTTP 오류: {result.status}")
                payload = json.loads(result.body.decode("utf-8-sig"))
                if not isinstance(payload, dict):
                    raise ApiError("API 응답 최상위 값이 객체가 아닙니다.")
                service_error = payload.get("OpenAPI_ServiceResponse")
                if service_error:
                    raise ApiError("공공데이터포털 인증 또는 사용량 오류가 반환되었습니다.")
                response_object = payload.get("response")
                if not isinstance(response_object, dict) or not isinstance(response_object.get("header"), dict):
                    raise ApiError("API 응답에 response.header가 없습니다.")
                header = response_object["header"]
                result_code = str(header.get("resultCode", ""))
                if result_code != "0":
                    message = str(header.get("resultMsg", "API 오류"))
                    raise ApiError(f"API 결과 오류: {message} ({result_code or '?'})")
                return payload
            except (ApiError, OSError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as error:
                last_error = error
                retryable = not isinstance(error, ApiError) or "재시도 가능한" in str(error)
                if attempt >= self.max_retries or not retryable:
                    break
                self.retries += 1
                wait = min(12.0, 0.75 * (2**attempt)) + random.random() * 0.4
                self.sleeper(wait)
        raise ApiError(f"{date} {page}페이지 조회 실패: {last_error}") from last_error

    def fetch_plan(self, date: str, plan: QueryPlan) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        expected_total: int | None = None
        page = 1
        while True:
            payload = self._request(date, plan, page)
            response = payload.get("response")
            if not isinstance(response, dict) or not isinstance(response.get("body"), dict):
                raise ApiError(f"{date} 응답에 response.body가 없습니다.")
            body = response["body"]
            try:
                total = int(body.get("totalCount", 0))
            except (TypeError, ValueError) as error:
                raise ApiError(f"{date} totalCount가 숫자가 아닙니다.") from error
            if expected_total is None:
                expected_total = total
            elif total != expected_total:
                raise ApiError(f"{date} 페이지 사이 totalCount가 변경되었습니다: {expected_total} -> {total}")
            items = body.get("items")
            page_rows = _as_list(items.get("item") if isinstance(items, dict) else None)
            rows.extend(page_rows)
            if len(rows) >= total:
                break
            if not page_rows:
                raise ApiError(f"{date} {page}페이지가 비어 있어 {total}건을 완료하지 못했습니다.")
            page += 1
        if expected_total is not None and len(rows) != expected_total:
            raise ApiError(f"{date} 페이지 합계 불일치: total={expected_total}, rows={len(rows)}")
        return rows

    def fetch_date(self, date: str, items: tuple[ItemSpec, ...]) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for plan in build_query_plans(items):
            fetched = self.fetch_plan(date, plan)
            rows.extend(
                row
                for row in fetched
                if f"{row.get('gds_lclsf_cd', '')}-{row.get('gds_mclsf_cd', '')}" in plan.allowed
            )
        return rows
