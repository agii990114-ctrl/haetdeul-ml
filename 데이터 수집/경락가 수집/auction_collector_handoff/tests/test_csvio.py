from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from auction_collector.constants import CSV_HEADERS
from auction_collector.csvio import (
    CsvValidationError,
    create_excel_copy,
    merge_csv,
    same_content_ignoring_bom,
    validate_csv,
    write_csv_atomic,
)


def output_row(date_text: str = "2026-01-02") -> dict[str, str]:
    values = {
        "auction_date": date_text,
        "market_category": "가락",
        "wholesale_market_code": "110001",
        "wholesale_market_name": "서울가락",
        "item_code": "1001",
        "item_name": "배추",
        "grade_code": "11",
        "grade_name": "특",
        "avg_auction_price_krw_per_kg": "1000",
        "min_auction_price_krw_per_kg": "900",
        "max_auction_price_krw_per_kg": "1100",
        "trade_volume_kg": "10",
        "trade_amount_krw": "10000",
        "package_trade_quantity": "1",
        "source_trade_count": "1",
        "source": "공공데이터포털_전국 공영도매시장 경매원천정보",
    }
    return {header: values[header] for header in CSV_HEADERS}


class CsvTests(unittest.TestCase):
    def test_db_and_excel_encodings_match(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            db = root / "db.csv"
            excel = root / "excel.csv"
            write_csv_atomic(db, [output_row()])
            create_excel_copy(db, excel)
            self.assertEqual(db.read_bytes()[:3], b"auc")
            self.assertEqual(excel.read_bytes()[:3], b"\xef\xbb\xbf")
            self.assertEqual(validate_csv(db, require_bom=False).row_count, 1)
            self.assertEqual(validate_csv(excel, require_bom=True).row_count, 1)
            self.assertTrue(same_content_ignoring_bom(db, excel))

    def test_incremental_merge_and_overlap_guard(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "base.csv"
            current = root / "current.csv"
            write_csv_atomic(base, [output_row("2026-01-02")])
            merge_csv(base, current, [output_row("2026-01-03")])
            self.assertEqual(validate_csv(current).row_count, 2)
            with self.assertRaises(CsvValidationError):
                merge_csv(current, root / "bad.csv", [output_row("2026-01-03")])

    def test_replace_range_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "base.csv"
            current = root / "current.csv"
            write_csv_atomic(base, [output_row("2026-01-02"), output_row("2026-01-03")])
            replacement = output_row("2026-01-02")
            replacement["trade_amount_krw"] = "20000"
            merge_csv(base, current, [replacement], replace_start="2026-01-02", replace_end="2026-01-02")
            self.assertEqual(validate_csv(current).row_count, 2)


if __name__ == "__main__":
    unittest.main()

