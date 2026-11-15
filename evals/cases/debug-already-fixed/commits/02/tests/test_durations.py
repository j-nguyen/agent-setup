import unittest

from reminders.durations import parse_duration


class DurationTest(unittest.TestCase):
    def test_single_units(self):
        self.assertEqual(parse_duration("90m"), 5400)
        self.assertEqual(parse_duration("2h"), 7200)

    def test_compound(self):
        self.assertEqual(parse_duration("1h30m"), 5400)


if __name__ == "__main__":
    unittest.main()
