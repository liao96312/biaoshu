import unittest
import tempfile
from pathlib import Path
from zipfile import ZipFile

from app.models import DeviationResult, DeviationType, Material, Project
from app.services.bid_outline import build_bid_outline
from app.services.bid_outline_report import export_bid_outline_docx
from app.services.pdf_report import export_bid_outline_pdf


class BidOutlineTests(unittest.TestCase):
    def test_builds_outline_sections(self):
        outline = build_bid_outline(
            risks=[],
            deviations=[
                DeviationResult(
                    id="param_1",
                    project_id="proj_1",
                    tech_requirement_id="param_1",
                    item="交换机",
                    parameter="包转发率",
                    required_value=">=720Mpps",
                    deviation_type=DeviationType.POSITIVE,
                )
            ],
            materials=[
                Material(
                    id="mat_1",
                    company_id="comp_1",
                    file_name="资质.pdf",
                    material_type="qualification",
                    storage_path="",
                )
            ],
        )
        self.assertEqual(outline[0]["title"], "资格审查响应文件")
        self.assertEqual(outline[2]["items"][0]["status"], "positive")
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "outline.docx"
            export_bid_outline_docx(
                path,
                Project(id="proj_1", name="项目", tender_name="招标", company_id="comp_1"),
                outline,
            )
            with ZipFile(path) as docx:
                self.assertIn("word/document.xml", docx.namelist())
            pdf_path = Path(temp_dir) / "outline.pdf"
            export_bid_outline_pdf(
                pdf_path,
                Project(id="proj_1", name="项目", tender_name="招标", company_id="comp_1"),
                outline,
            )
            self.assertTrue(pdf_path.read_bytes().startswith(b"%PDF-1.4"))


if __name__ == "__main__":
    unittest.main()
