import tempfile
import unittest
from pathlib import Path

from app.agents.workflow import BidRiskWorkflow
from app.models import Material


class WorkflowTests(unittest.TestCase):
    def test_workflow_runs_agent_sequence(self):
        tender = "投标人须提供投标保证金缴纳凭证，否则投标无效。\n★核心交换机包转发率≥720Mpps。"
        product = "[[page:3]]\n核心交换机包转发率≥800Mpps。"
        with tempfile.TemporaryDirectory() as temp_dir:
            tender_path = Path(temp_dir) / "tender.txt"
            tender_path.write_text(tender, encoding="utf-8")
            material = Material(
                id="mat_1",
                company_id="comp_1",
                file_name="产品规格.txt",
                material_type="product",
                storage_path="",
                parsed_text=product,
            )
            result = BidRiskWorkflow().run(str(tender_path), "proj_1", [material])
            self.assertGreaterEqual(len(result.risks), 1)
            self.assertEqual(len(result.requirements), 1)
            self.assertEqual(result.deviations[0].deviation_type.value, "positive")

    def test_default_workflow_engine_is_deterministic(self):
        self.assertEqual(BidRiskWorkflow().engine, "deterministic")


if __name__ == "__main__":
    unittest.main()
