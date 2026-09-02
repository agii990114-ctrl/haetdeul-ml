from __future__ import annotations

import os
import unittest

from auction_collector.postgres import CONSTRAINT_NAME, schema_sql


class PostgresSqlTests(unittest.TestCase):
    def test_schema_uses_postgres_15_null_safe_natural_key(self) -> None:
        sql = schema_sql()
        self.assertIn("UNIQUE NULLS NOT DISTINCT", sql)
        self.assertIn(CONSTRAINT_NAME, sql)
        self.assertIn("grade_name", sql)


@unittest.skipUnless(os.environ.get("TEST_DATABASE_URL"), "TEST_DATABASE_URL이 없어 통합 테스트를 건너뜁니다.")
class PostgresIntegrationTests(unittest.TestCase):
    def test_database_connection_is_available(self) -> None:
        try:
            import psycopg
        except ImportError as error:
            self.skipTest(f"psycopg가 없습니다: {error}")
        with psycopg.connect(os.environ["TEST_DATABASE_URL"]) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_setting('server_version_num')::int")
                self.assertGreaterEqual(int(cursor.fetchone()[0]), 150000)


if __name__ == "__main__":
    unittest.main()
