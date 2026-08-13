import unittest

from toss_manager.database import EXPECTED_COLUMNS, SCHEMA_STATEMENTS


class SchemaTests(unittest.TestCase):
    def test_all_erd_tables_have_ddl(self) -> None:
        ddl = "\n".join(SCHEMA_STATEMENTS).lower()
        self.assertEqual(len(SCHEMA_STATEMENTS), 9)
        for table in EXPECTED_COLUMNS:
            self.assertIn(f"create table if not exists {table}", ddl)

    def test_erd_relationships_are_declared(self) -> None:
        ddl = "\n".join(SCHEMA_STATEMENTS).lower()
        self.assertEqual(ddl.count("foreign key"), 8)


if __name__ == "__main__":
    unittest.main()
