from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from auction_collector.cli import main
from auction_collector.csvio import has_utf8_bom, write_csv_atomic

from .test_csvio import output_row


class CliTests(unittest.TestCase):
    def test_noop_update_prepares_current_artifacts_without_api(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            seed = root / "seed.csv"
            output_dir = root / "outputs"
            state = root / "state.json"
            write_csv_atomic(seed, [output_row("2025-12-31")])
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout), self.assertRaises(SystemExit) as exit_result:
                main(
                    [
                        "update",
                        "--seed-csv",
                        str(seed),
                        "--output-dir",
                        str(output_dir),
                        "--state-file",
                        str(state),
                        "--through",
                        "2025-12-31",
                    ]
                )
            self.assertEqual(exit_result.exception.code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["status"], "up_to_date")
            self.assertFalse(has_utf8_bom(output_dir / "auction_prices_current_db.csv"))
            self.assertTrue(has_utf8_bom(output_dir / "auction_prices_current_excel.csv"))
            self.assertEqual(json.loads(state.read_text(encoding="utf-8"))["lastCompletedDate"], "2025-12-31")


if __name__ == "__main__":
    unittest.main()
