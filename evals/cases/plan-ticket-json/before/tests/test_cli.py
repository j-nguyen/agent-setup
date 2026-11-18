import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from tally.cli import main


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.file = Path(self.tmp.name) / "entries.jsonl"
        for argv in (["add", "acme", "1.5", "review", "--day", "2026-11-02"],
                     ["add", "globex", "3", "--day", "2026-11-03"],
                     ["add", "acme", "0.5", "--day", "2026-10-30"]):
            self.assertEqual(self.run_cli(argv)[0], 0)

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["--file", str(self.file), *argv])
        return code, out.getvalue()

    def test_report_table(self):
        code, out = self.run_cli(["report", "--since", "2026-11-01"])
        self.assertEqual(code, 0)
        self.assertIn("globex", out)
        self.assertIn("TOTAL", out)
        self.assertIn("4.50", out)

    def test_list(self):
        _, out = self.run_cli(["list"])
        self.assertEqual(len(out.strip().splitlines()), 4)

    def test_export(self):
        target = Path(self.tmp.name) / "out.json"
        code, _ = self.run_cli(["export", "-o", str(target)])
        self.assertEqual(code, 0)
        data = json.loads(target.read_text())
        self.assertEqual(data["report"]["total_hours"], 5.0)
        self.assertEqual(len(data["entries"]), 3)


if __name__ == "__main__":
    unittest.main()
