import unittest

from app.services.rules import read_risk_rules


class RuleTests(unittest.TestCase):
    def test_risk_rules_have_required_sections(self):
        rules = read_risk_rules()
        self.assertIn("high_keywords", rules)
        self.assertIn("medium_keywords", rules)
        self.assertIn("risk_types", rules)
        self.assertIn("投标无效", rules["high_keywords"])


if __name__ == "__main__":
    unittest.main()
