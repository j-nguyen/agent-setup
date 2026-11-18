import unittest
from datetime import date

from tally.models import Entry
from tally.reports import by_project


class ByProjectTest(unittest.TestCase):
    def test_totals_and_order(self):
        r = by_project([Entry(date(2026, 11, 2), "acme", 1.5), Entry(date(2026, 11, 3), "globex", 3),
                        Entry(date(2026, 11, 3), "acme", 0.5)])
        self.assertEqual([(x.project, x.hours, x.entries) for x in r.rows],
                         [("globex", 3.0, 1), ("acme", 2.0, 2)])
        self.assertEqual(r.total_hours, 5.0)
        self.assertAlmostEqual(r.rows[0].share, 0.6)

    def test_empty(self):
        self.assertEqual(by_project([]).rows, [])


if __name__ == "__main__":
    unittest.main()
