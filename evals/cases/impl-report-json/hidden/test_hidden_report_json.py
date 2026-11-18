"""Acceptance test the harness adds after the run; the agent never sees it."""
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from tally.cli import main


class HiddenReportJson(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.file = Path(self.tmp.name) / "entries.jsonl"
        for argv in (["add", "acme", "1.5", "--day", "2026-11-02"], ["add", "globex", "3", "--day", "2026-11-03"]):
            self.run_cli(argv)

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["--file", str(self.file), *argv])
        return code, out.getvalue()

    def test_json_matches_export_report(self):
        code, out = self.run_cli(["report", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        target = Path(self.tmp.name) / "export.json"
        self.run_cli(["export", "-o", str(target)])
        self.assertEqual(data, json.loads(target.read_text())["report"])

    def test_empty_period_is_valid_json(self):
        code, out = self.run_cli(["report", "--json", "--since", "2030-01-01"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["rows"], [])

    def test_text_default_unchanged(self):
        _, out = self.run_cli(["report"])
        self.assertIn("TOTAL", out)
        with self.assertRaises(json.JSONDecodeError):
            json.loads(out)


if __name__ == "__main__":
    unittest.main()
