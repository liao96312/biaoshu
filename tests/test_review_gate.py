import unittest

from app.models import DeviationResult, DeviationType, ReviewStatus, RiskItem, Severity
from app.services.review_gate import review_blockers, review_summary


class ReviewGateTests(unittest.TestCase):
    def test_blocks_pending_high_risks_and_unknown_deviations(self):
        blockers = review_blockers(
            [
                RiskItem(
                    id="risk_1",
                    project_id="proj_1",
                    risk_type="资格性废标",
                    requirement="须提供材料",
                    trigger_keyword="须提供",
                    severity=Severity.HIGH,
                    source_text="须提供材料",
                    ai_reason="命中规则",
                    suggestion="补齐材料",
                    confidence=0.9,
                )
            ],
            [
                DeviationResult(
                    id="param_1",
                    project_id="proj_1",
                    tech_requirement_id="param_1",
                    item="交换机",
                    parameter="包转发率",
                    required_value=">=720Mpps",
                    deviation_type=DeviationType.UNKNOWN,
                )
            ],
        )
        self.assertEqual(len(blockers), 2)

    def test_blocks_low_confidence_items(self):
        risk = RiskItem(
            id="risk_low",
            project_id="proj_1",
            risk_type="符合性废标",
            requirement="须提供材料",
            trigger_keyword="须提供",
            severity=Severity.LOW,
            source_text="须提供材料",
            ai_reason="低置信度",
            suggestion="人工复核",
            confidence=0.5,
        )
        deviation = DeviationResult(
            id="param_low",
            project_id="proj_1",
            tech_requirement_id="param_low",
            item="交换机",
            parameter="包转发率",
            required_value=">=720Mpps",
            confidence=0.5,
        )
        blockers = review_blockers([risk], [deviation])
        self.assertEqual(len(blockers), 2)

    def test_review_summary_reports_readiness_and_counts(self):
        risk = RiskItem(
            id="risk_1",
            project_id="proj_1",
            risk_type="资格性废标",
            requirement="须提供材料",
            trigger_keyword="须提供",
            severity=Severity.HIGH,
            source_page=1,
            source_text="须提供材料，否则投标无效",
            ai_reason="命中规则",
            suggestion="补齐材料",
            confidence=0.9,
            status=ReviewStatus.CONFIRMED,
        )
        deviation = DeviationResult(
            id="param_1",
            project_id="proj_1",
            tech_requirement_id="param_1",
            item="交换机",
            parameter="包转发率",
            required_value=">=720Mpps",
            deviation_type=DeviationType.NEGATIVE,
            source_page=2,
            reviewer_status=ReviewStatus.APPROVED,
        )
        summary = review_summary([risk], [deviation])
        self.assertTrue(summary["ready_to_complete"])
        self.assertEqual(summary["risks"]["by_status"]["confirmed"], 1)
        self.assertEqual(summary["deviations"]["by_type"]["negative"], 1)
        self.assertEqual(summary["blocker_count"], 0)


if __name__ == "__main__":
    unittest.main()
