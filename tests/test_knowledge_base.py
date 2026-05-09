import unittest

from app.knowledge_base import KnowledgeBase
from app.models import Material


class KnowledgeBaseTests(unittest.TestCase):
    def test_indexes_and_searches_materials_by_company(self):
        kb = KnowledgeBase()
        material = Material(
            id="mat_1",
            company_id="comp_1",
            file_name="产品.txt",
            material_type="product",
            storage_path="",
            parsed_text="核心交换机 包转发率 800Mpps",
        )
        kb.index_material(material)
        self.assertEqual(kb.search("comp_1", "交换机 800Mpps")[0].id, "mat_1")
        self.assertEqual(kb.search("comp_2", "交换机"), [])
        kb.delete_material(material)
        self.assertEqual(kb.search("comp_1", "交换机 800Mpps"), [])


if __name__ == "__main__":
    unittest.main()
