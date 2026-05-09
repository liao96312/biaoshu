import unittest

from app.integrations import integration_status


class IntegrationTests(unittest.TestCase):
    def test_integration_status_reports_known_keys(self):
        status = integration_status()
        self.assertIn("postgres", status)
        self.assertIn("celery", status)
        self.assertIn("docx", status)


if __name__ == "__main__":
    unittest.main()
