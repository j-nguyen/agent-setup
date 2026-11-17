import unittest

from app import migrate
from tests.fakes import FakeConn


class MigrateTest(unittest.TestCase):
    def test_runs_pending_in_order(self):
        conn = FakeConn()
        done = migrate.run(conn, applied={"001_init.sql"})
        self.assertEqual(done[0], "002_plans.sql")
        self.assertEqual(done, sorted(done))


if __name__ == "__main__":
    unittest.main()
