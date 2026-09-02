from __future__ import annotations

import unittest

from auction_collector.aggregate import aggregate_date
from auction_collector.constants import DEFAULT_ITEMS


def raw_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "gds_lclsf_cd": "10",
        "gds_mclsf_cd": "01",
        "trd_se": "경매",
        "unit_nm": "kg",
        "unit_qty": "10",
        "unit_tot_qty": "10",
        "qty": "1",
        "scsbd_prc": "10000",
        "totprc": "10000",
        "whsl_mrkt_cd": "110001",
        "whsl_mrkt_nm": "서울가락",
        "grd_cd": "11",
        "grd_nm": "특",
    }
    row.update(overrides)
    return row


class AggregateTests(unittest.TestCase):
    def test_weighted_aggregation_and_filters(self) -> None:
        rows, quality = aggregate_date(
            "2026-01-02",
            [
                raw_row(),
                raw_row(unit_tot_qty="20", qty="2", totprc="40000"),
                raw_row(trd_se="정가수의"),
                raw_row(unit_nm="망"),
                raw_row(unit_qty="0"),
            ],
            DEFAULT_ITEMS,
        )
        self.assertEqual(len(rows), 1)
        result = rows[0]
        self.assertEqual(result["market_category"], "가락")
        self.assertEqual(result["item_name"], "배추")
        self.assertEqual(result["avg_auction_price_krw_per_kg"], "1666.67")
        self.assertEqual(result["min_auction_price_krw_per_kg"], "1000")
        self.assertEqual(result["max_auction_price_krw_per_kg"], "2000")
        self.assertEqual(result["trade_volume_kg"], "30")
        self.assertEqual(result["trade_amount_krw"], "50000")
        self.assertEqual(result["package_trade_quantity"], "3")
        self.assertEqual(result["source_trade_count"], "2")
        self.assertEqual(quality.fetched_rows, 5)
        self.assertEqual(quality.excluded_non_auction, 1)
        self.assertEqual(quality.excluded_non_kg, 1)
        self.assertEqual(quality.excluded_invalid, 1)

    def test_blank_grade_code_is_preserved(self) -> None:
        rows, _quality = aggregate_date("2026-01-02", [raw_row(grd_cd="", grd_nm="미상")], DEFAULT_ITEMS)
        self.assertEqual(rows[0]["grade_code"], "")
        self.assertEqual(rows[0]["grade_name"], "미상")


if __name__ == "__main__":
    unittest.main()

