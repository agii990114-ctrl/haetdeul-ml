from __future__ import annotations

import csv
import json
import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError


PACKAGE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_DIR))

import fetch_economic_variables as fetcher  # noqa: E402


class FakeHeaders:
    def get_content_charset(self) -> str:
        return "utf-8"


class FakeResponse:
    def __init__(self, payload: object) -> None:
        self.payload = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.headers = FakeHeaders()

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.payload


class MappingHttp:
    def get_json(self, url: str, _label: str) -> object:
        if url == fetcher.KDI_EPU_URL:
            return [
                {"date": "202001", "한국 EPU 지수": 90.0},
                {"date": "202002", "한국 EPU 지수": 95.0},
            ]

        if "/161Y006/M/" in url:
            points = []
            for year, multiplier in ((2019, 1.0), (2020, 1.1)):
                for month in (1, 2):
                    points.append({"TIME": f"{year}{month:02d}", "DATA_VALUE": 100 * multiplier + month})
            return self._ecos(points)
        if "/404Y014/M/" in url:
            return self._ecos(
                [
                    {"TIME": "202001", "DATA_VALUE": 99.1},
                    {"TIME": "202002", "DATA_VALUE": 99.3},
                ]
            )
        if "/901Y009/M/" in url:
            points = []
            for year, multiplier in ((2019, 1.0), (2020, 1.02)):
                for month in (1, 2):
                    points.append({"TIME": f"{year}{month:02d}", "DATA_VALUE": 100 * multiplier + month})
            return self._ecos(points)
        if "/817Y002/D/" in url:
            return self._ecos(
                [
                    {"TIME": "20191231", "DATA_VALUE": 1.4},
                    {"TIME": "20200102", "DATA_VALUE": 1.35},
                    {"TIME": "20200203", "DATA_VALUE": 1.30},
                    {"TIME": "20200228", "DATA_VALUE": 1.25},
                ]
            )
        raise AssertionError(f"예상하지 못한 URL: {url.replace('test-key', '[REDACTED]')}")

    @staticmethod
    def _ecos(rows: list[dict[str, object]]) -> dict[str, object]:
        return {"StatisticSearch": {"list_total_count": len(rows), "row": rows}}


class PaginatedHttp:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def get_json(self, url: str, _label: str) -> object:
        self.urls.append(url)
        if "/1/2/" in url:
            rows = [
                {"TIME": "202001", "DATA_VALUE": 100},
                {"TIME": "202002", "DATA_VALUE": 101},
            ]
        elif "/3/4/" in url:
            rows = [{"TIME": "202003", "DATA_VALUE": 102}]
        else:
            raise AssertionError("잘못된 페이지 범위")
        return {"StatisticSearch": {"list_total_count": 3, "row": rows}}


class FetcherUnitTests(unittest.TestCase):
    def test_headers_are_the_existing_twelve_columns(self) -> None:
        self.assertEqual(
            fetcher.HEADERS,
            [
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
            ],
        )

    def test_environment_variable_has_priority_over_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text("ECOS_API_KEY=file-key\n", encoding="utf-8")
            with patch.dict(os.environ, {"ECOS_API_KEY": "environment-key"}, clear=False):
                self.assertEqual(fetcher.read_api_key(env_path), "environment-key")

    def test_missing_api_key_is_a_safe_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(fetcher.CollectorError, "ECOS_API_KEY"):
                    fetcher.read_api_key(Path(temp_dir) / ".env")

    def test_example_placeholder_is_not_accepted_as_a_key(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "ECOS_API_KEY=여기에_한국은행_ECOS_인증키를_입력하세요\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(fetcher.CollectorError, "ECOS_API_KEY"):
                    fetcher.read_api_key(env_path)

    def test_year_over_year_calculation(self) -> None:
        points = [
            fetcher.SeriesPoint("201901", 100.0),
            fetcher.SeriesPoint("202001", 110.0),
        ]
        self.assertAlmostEqual(fetcher.calculate_year_over_year(points)["202001"], 10.0)

    def test_daily_alignment_and_observation_metadata(self) -> None:
        rows = fetcher.build_daily_rows(
            start_date=date(2021, 1, 1),
            end_date=date(2021, 1, 3),
            bond_by_date={date(2020, 12, 31): 1.25, date(2021, 1, 2): 1.3},
            m2_yoy_by_month={"202101": 8.0},
            epu_by_month={"202101": 101.0},
            ppi_by_month={"202101": 99.0},
            cpi_yoy_by_month={"202101": 1.5},
        )
        self.assertEqual(rows[0][2:4], ["2020-12-31", "0"])
        self.assertEqual(rows[1][2:4], ["2021-01-02", "1"])
        self.assertEqual(rows[2][2:4], ["2021-01-02", "0"])
        fetcher.validate_rows(rows, date(2021, 1, 1), date(2021, 1, 3))

    def test_missing_monthly_value_fails(self) -> None:
        with self.assertRaisesRegex(fetcher.CollectorError, "EPU"):
            fetcher.build_daily_rows(
                start_date=date(2021, 1, 1),
                end_date=date(2021, 1, 1),
                bond_by_date={date(2020, 12, 31): 1.25},
                m2_yoy_by_month={"202101": 8.0},
                epu_by_month={},
                ppi_by_month={"202101": 99.0},
                cpi_yoy_by_month={"202101": 1.5},
            )

    def test_atomic_write_preserves_existing_file_on_validation_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "economic_variables_daily.csv"
            output.write_text("기존 파일\n", encoding="utf-8")
            invalid_row = [["2021-01-01"] * 12]
            with self.assertRaises(fetcher.CollectorError):
                fetcher.write_csv_atomically(output, invalid_row, date(2021, 1, 1), date(2021, 1, 1))
            self.assertEqual(output.read_text(encoding="utf-8"), "기존 파일\n")

    def test_http_client_retries_500_errors(self) -> None:
        calls = 0
        sleeps: list[float] = []

        def fake_urlopen(*_args: object, **_kwargs: object) -> FakeResponse:
            nonlocal calls
            calls += 1
            if calls < 3:
                raise HTTPError("https://example.invalid", 500, "server", None, None)
            return FakeResponse({"ok": True})

        client = fetcher.HttpClient(attempts=4, sleep_fn=sleeps.append)
        with patch.object(fetcher, "urlopen", side_effect=fake_urlopen):
            self.assertEqual(client.get_json("https://example.invalid", "테스트"), {"ok": True})
        self.assertEqual(calls, 3)
        self.assertEqual(sleeps, [0.4, 0.8])

    def test_ecos_client_paginates_until_total_count(self) -> None:
        http = PaginatedHttp()
        client = fetcher.EcosClient("test-key", http, page_size=2)
        points = client.fetch_series(
            stat_code="TEST",
            cycle="M",
            start="202001",
            end="202003",
            item_code="ITEM",
            label="페이지 테스트",
        )
        self.assertEqual([point.period for point in points], ["202001", "202002", "202003"])
        self.assertEqual(len(http.urls), 2)

    def test_ecos_error_does_not_expose_api_key(self) -> None:
        secret = "very-secret-key"

        class ErrorHttp:
            def get_json(self, _url: str, _label: str) -> object:
                return {
                    "RESULT": {
                        "CODE": "INFO-100",
                        "MESSAGE": f"인증키 {secret}가 올바르지 않습니다.",
                    }
                }

        client = fetcher.EcosClient(secret, ErrorHttp())
        with self.assertRaises(fetcher.CollectorError) as caught:
            client.fetch_series(
                stat_code="TEST",
                cycle="M",
                start="202001",
                end="202001",
                item_code="ITEM",
                label="인증 테스트",
            )
        self.assertNotIn(secret, str(caught.exception))
        self.assertIn("[REDACTED]", str(caught.exception))

    def test_automatic_end_uses_latest_common_month_end(self) -> None:
        result = fetcher.collect_dataset(
            api_key="test-key",
            start_date=date(2020, 1, 1),
            requested_end_date=None,
            today=date(2020, 3, 15),
            http=MappingHttp(),
        )
        self.assertEqual(result.end_date, date(2020, 2, 29))
        self.assertEqual(result.latest_common_month, "202002")
        self.assertEqual(len(result.rows), 60)
        self.assertTrue(all(len(row) == 12 for row in result.rows))


class ExistingCsvRegressionTests(unittest.TestCase):
    def test_daily_alignment_matches_2015_2021_reference(self) -> None:
        reference_path = Path(__file__).parent / "fixtures" / "economic_variables_daily_2015_2021.csv"
        with reference_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            self.assertEqual(next(reader), fetcher.HEADERS)
            expected_rows = list(reader)

        bond_by_date: dict[date, float] = {}
        m2: dict[str, float] = {}
        epu: dict[str, float] = {}
        ppi: dict[str, float] = {}
        cpi: dict[str, float] = {}
        for row in expected_rows:
            observed_date = date.fromisoformat(row[2])
            if row[3] == "1" or observed_date < date.fromisoformat(row[0]):
                bond_by_date[observed_date] = float(row[1])
            m2[row[5]] = float(row[4])
            epu[row[7]] = float(row[6])
            ppi[row[9]] = float(row[8])
            cpi[row[11]] = float(row[10])

        actual_rows = fetcher.build_daily_rows(
            start_date=date(2015, 1, 1),
            end_date=date(2021, 12, 31),
            bond_by_date=bond_by_date,
            m2_yoy_by_month=m2,
            epu_by_month=epu,
            ppi_by_month=ppi,
            cpi_yoy_by_month=cpi,
        )
        self.assertEqual(actual_rows, expected_rows)
        self.assertEqual(len(actual_rows), 2557)


if __name__ == "__main__":
    unittest.main()
