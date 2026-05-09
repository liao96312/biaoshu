import unittest

from app.knowledge_base import KnowledgeBase
from app.models import Material, RiskItem, Severity
from app.services.material_recommender import recommend_materials_for_risk, recommend_materials_for_risks


class MaterialRecommenderTests(unittest.TestCase):
    def test_recommends_company_material_for_risk(self):
        kb = KnowledgeBase()
        material = Material(
            id="mat_1",
            company_id="comp_1",
            file_name="保证金回单.txt",
            material_type="qualification",
            storage_path="",
            parsed_text="投标保证金缴纳凭证 银行回单",
        )
        kb.index_material(material)
        risk = RiskItem(
            id="risk_1",
            project_id="proj_1",
            risk_type="符合性废标",
            requirement="须提供投标保证金缴纳凭证",
            trigger_keyword="须提供",
            severity=Severity.HIGH,
            source_text="投标人须提供投标保证金缴纳凭证，否则投标无效",
            ai_reason="命中规则",
            suggestion="上传投标保证金缴纳凭证",
            confidence=0.9,
        )

        hits = recommend_materials_for_risk(kb, "comp_1", risk)
        rows = recommend_materials_for_risks(kb, "comp_1", [risk])

        self.assertEqual(hits[0]["material_id"], "mat_1")
        self.assertEqual(rows[0]["recommendations"][0]["material_id"], "mat_1")
        self.assertEqual(recommend_materials_for_risk(kb, "comp_2", risk), [])


if __name__ == "__main__":
    unittest.main()
