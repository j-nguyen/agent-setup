import json
import unittest
from datetime import date

from tally.models import Entry, Report, ReportRow
from tally.serialize import to_json


class SerializeTest(unittest.TestCase):
    def test_report_round_trips_to_plain_json(self):
        rep = Report(date(2026, 11, 1), None, [ReportRow("acme", 2.0, 2, 1.0)], 2.0)
        self.assertEqual(json.loads(to_json(rep)), {
            "since": "2026-11-01", "until": None, "total_hours": 2.0,
            "rows": [{"project": "acme", "hours": 2.0, "entries": 2, "share": 1.0}]})

    def test_entries(self):
        self.assertEqual(json.loads(to_json([Entry(date(2026, 1, 2), "x", 1.0, "n")])),
                         [{"day": "2026-01-02", "project": "x", "hours": 1.0, "note": "n"}])


if __name__ == "__main__":
    unittest.main()
