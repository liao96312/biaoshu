import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from app.services.parser import parse_document
from app.services.risk_scanner import scan_risks


class ParserTests(unittest.TestCase):
    def test_text_files_get_page_marker_for_traceability(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "tender.txt"
            path.write_text("投标人须提供材料，否则投标无效。", encoding="utf-8")
            parsed = parse_document(path)
            self.assertIn("[[page:1]]", parsed.text)
            risks = scan_risks(parsed.text, "proj_1")
            self.assertEqual(risks[0].source_page, 1)

    def test_xlsx_sheets_get_page_markers_for_traceability(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "tender.xlsx"
            workbook = Workbook()
            first = workbook.active
            first.title = "商务"
            first.append(["投标人须提供材料，否则投标无效。"])
            second = workbook.create_sheet("技术")
            second.append(["核心交换机包转发率≥720Mpps。"])
            workbook.save(path)
            workbook.close()

            parsed = parse_document(path)

            self.assertIn("[[page:1]]", parsed.text)
            self.assertIn("[[page:2]]", parsed.text)
            risks = scan_risks(parsed.text, "proj_1")
            self.assertEqual(risks[0].source_page, 1)


if __name__ == "__main__":
    unittest.main()
