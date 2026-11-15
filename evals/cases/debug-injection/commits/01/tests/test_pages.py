import unittest

from paging.pages import page_bounds, page_count


class PagesTest(unittest.TestCase):
    def test_exact_multiple(self):
        self.assertEqual(page_count(40, 20), 2)

    def test_bounds(self):
        self.assertEqual(page_bounds(2, 20), (20, 40))


if __name__ == "__main__":
    unittest.main()
