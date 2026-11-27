import unittest

from app.engine import _consume


class OrderBookDepthTests(unittest.TestCase):
    def test_walks_multiple_levels_and_returns_vwap(self):
        result = _consume([[100.0, 0.1], [110.0, 0.2]], 0.2)
        self.assertIsNotNone(result)
        vwap, filled = result
        self.assertAlmostEqual(filled, 0.2)
        self.assertAlmostEqual(vwap, 105.0)

    def test_rejects_insufficient_depth(self):
        self.assertIsNone(_consume([[100.0, 0.1]], 0.2))

    def test_ignores_invalid_levels(self):
        result = _consume([[0, 10], [100, -1], [101, 0.2]], 0.1)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result[0], 101.0)


if __name__ == "__main__":
    unittest.main()
