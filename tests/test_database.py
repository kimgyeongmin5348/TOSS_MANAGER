import unittest

from toss_manager.database import EXPECTED_COLUMNS, SCHEMA_STATEMENTS


class SchemaTests(unittest.TestCase):
    def test_all_erd_tables_have_ddl(self) -> None:
        ddl = "\n".join(SCHEMA_STATEMENTS).lower()
        self.assertEqual(len(SCHEMA_STATEMENTS), 12)
        for table in EXPECTED_COLUMNS:
            self.assertIn(f"create table if not exists {table}", ddl)

    def test_erd_relationships_are_declared(self) -> None:
        ddl = "\n".join(SCHEMA_STATEMENTS).lower()
        self.assertEqual(ddl.count("foreign key"), 11)

    def test_brokerage_account_identity_is_scoped_to_user(self) -> None:
        ddl = "\n".join(SCHEMA_STATEMENTS).lower()
        self.assertIn(
            "unique key uq_brokerage_user_provider_account "
            "(user_id, provider, toss_account_seq)",
            ddl,
        )
        self.assertNotIn("uq_brokerage_provider_account (provider", ddl)

    def test_snapshot_security_and_watchlist_columns_are_declared(self) -> None:
        ddl = "\n".join(SCHEMA_STATEMENTS).lower()
        self.assertIn("failed_login_count int not null default 0", ddl)
        self.assertIn("locked_until datetime(6)", ddl)
        self.assertIn("email_verified_at datetime(6)", ddl)
        self.assertIn(
            "unique key uq_portfolio_account_hash_type "
            "(account_id, content_hash, snapshot_type)",
            ddl,
        )
        self.assertIn("target_price decimal(30,10), last_price decimal(30,10)", ddl)


if __name__ == "__main__":
    unittest.main()
