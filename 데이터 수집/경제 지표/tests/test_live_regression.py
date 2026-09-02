from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path


PACKAGE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_DIR))

import fetch_economic_variables as fetcher  # noqa: E402


class LiveApiRegressionTest(unittest.TestCase):
    def test_live_api_reproduces_2015_2021_reference(self) -> None:
        try:
            api_key = fetcher.read_api_key(PACKAGE_DIR / ".env")
        except fetcher.CollectorError:
            self.skipTest("ECOS_API_KEY가 없어 실 API 회귀 검증을 건너뜁니다.")

        result = fetcher.collect_dataset(
            api_key=api_key,
            start_date=date(2015, 1, 1),
            requested_end_date=date(2021, 12, 31),
        )
        reference = PACKAGE_DIR / "tests" / "fixtures" / "economic_variables_daily_2015_2021.csv"
        with tempfile.TemporaryDirectory() as temp_dir:
            actual = Path(temp_dir) / "actual.csv"
            fetcher.write_csv_atomically(actual, result.rows, result.start_date, result.end_date)
            self.assertEqual(actual.read_bytes(), reference.read_bytes())


if __name__ == "__main__":
    unittest.main()
