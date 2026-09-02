from __future__ import annotations

import json
import urllib.parse
import unittest

from auction_collector.api import DataGoClient, HttpResult, QueryPlan


def response(rows: list[dict[str, object]], total: int) -> bytes:
    return json.dumps(
        {
            "response": {
                "header": {"resultCode": "0", "resultMsg": "NORMAL SERVICE."},
                "body": {"totalCount": total, "items": {"item": rows}},
            }
        }
    ).encode()


class ApiTests(unittest.TestCase):
    def test_pagination(self) -> None:
        calls: list[int] = []

        def transport(url: str, _timeout: float) -> HttpResult:
            page = int(urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["pageNo"][0])
            calls.append(page)
            rows = [{"id": 1}, {"id": 2}] if page == 1 else [{"id": 3}]
            return HttpResult(200, {}, response(rows, 3))

        client = DataGoClient("secret", page_size=2, transport=transport, sleeper=lambda _seconds: None)
        plan = QueryPlan((("gds_lclsf_cd", "EQ", "10"),), frozenset(("10-01",)))
        rows = client.fetch_plan("2026-01-02", plan)
        self.assertEqual([row["id"] for row in rows], [1, 2, 3])
        self.assertEqual(calls, [1, 2])

    def test_retry_on_server_error(self) -> None:
        attempts = 0

        def transport(_url: str, _timeout: float) -> HttpResult:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                return HttpResult(500, {}, b"error")
            return HttpResult(200, {}, response([], 0))

        client = DataGoClient("secret", transport=transport, sleeper=lambda _seconds: None)
        plan = QueryPlan((("gds_lclsf_cd", "EQ", "10"),), frozenset(("10-01",)))
        self.assertEqual(client.fetch_plan("2026-01-02", plan), [])
        self.assertEqual(client.retries, 1)
        self.assertEqual(attempts, 2)


if __name__ == "__main__":
    unittest.main()

