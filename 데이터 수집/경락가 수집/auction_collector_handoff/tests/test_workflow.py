from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from auction_collector.constants import DEFAULT_ITEMS
from auction_collector.workflow import Collector, collection_dates

from .test_aggregate import raw_row


class FakeClient:
    def __init__(self) -> None:
        self.calls = 0

    def fetch_date(self, _date: str, _items: object) -> list[dict[str, object]]:
        self.calls += 1
        return [raw_row()]


class WorkflowTests(unittest.TestCase):
    def test_sundays_are_skipped_by_default(self) -> None:
        values = collection_dates(date(2026, 1, 3), date(2026, 1, 5))
        self.assertEqual([value.isoformat() for value in values], ["2026-01-03", "2026-01-05"])

    def test_cache_allows_resume_without_api_call(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            client = FakeClient()
            collector = Collector(client, DEFAULT_ITEMS, Path(directory), concurrency=1)  # type: ignore[arg-type]
            first, _ = collector.collect_range(date(2026, 1, 2), date(2026, 1, 2))
            second, _ = collector.collect_range(date(2026, 1, 2), date(2026, 1, 2))
            self.assertEqual(client.calls, 1)
            self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()

