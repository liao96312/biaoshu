import unittest

from app.rate_limit import FixedWindowRateLimiter


class RateLimitTests(unittest.TestCase):
    def test_fixed_window_limiter_blocks_after_limit(self):
        limiter = FixedWindowRateLimiter(limit=2, window_seconds=3600)
        self.assertTrue(limiter.check("client").allowed)
        self.assertTrue(limiter.check("client").allowed)
        third = limiter.check("client")
        self.assertFalse(third.allowed)
        self.assertEqual(third.remaining, 0)


if __name__ == "__main__":
    unittest.main()
