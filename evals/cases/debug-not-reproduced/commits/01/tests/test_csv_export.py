import unittest

from export.csv_export import export_contacts


class ExportTest(unittest.TestCase):
    def test_header_and_row(self):
        out = export_contacts([{"name": "Ann", "email": "ann@x.com"}]).decode("utf-8-sig")
        self.assertEqual(out.splitlines(), ["name,email", "Ann,ann@x.com"])


if __name__ == "__main__":
    unittest.main()
