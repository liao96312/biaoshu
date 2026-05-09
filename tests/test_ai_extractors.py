import unittest

from app.services.ai_extractors import extract_ai_risks, extract_ai_tech_requirements


class AIExtractorTests(unittest.TestCase):
    def test_disabled_llm_returns_no_items(self):
        self.assertEqual(extract_ai_risks("text", "proj_1"), [])
        self.assertEqual(extract_ai_tech_requirements("text", "proj_1"), [])


if __name__ == "__main__":
    unittest.main()
