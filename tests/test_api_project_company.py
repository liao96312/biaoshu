import tempfile
import unittest
from pathlib import Path

import app.main as main
from app.models import ProjectCreate
from app.repositories.runtime import JsonStateRepository
from app.store import InMemoryStore


class ApiProjectCompanyTests(unittest.TestCase):
    def test_project_creation_ensures_company_exists(self):
        original_repository = main.repository
        with tempfile.TemporaryDirectory() as temp_dir:
            state = InMemoryStore(storage_root=temp_dir, state_file=str(Path(temp_dir) / "state.json"))
            main.repository = JsonStateRepository(state)
            try:
                main.create_project(
                    ProjectCreate(
                        name="智能复核项目",
                        tender_name="招标文件",
                        company_id="comp_demo",
                    )
                )
                company = main.repository.get_company("comp_demo")
                self.assertIsNotNone(company)
                self.assertEqual(company.id, "comp_demo")
            finally:
                main.repository = original_repository

    def test_health_response_does_not_expose_local_paths(self):
        payload = main.healthz()
        self.assertEqual(payload["status"], "ok")
        self.assertIn("storage", payload)
        self.assertIn("task_queue", payload)
        self.assertNotIn("storage_root", payload)
        self.assertNotIn("state_file", payload)

    def test_safe_download_name_strips_path_and_control_characters(self):
        self.assertEqual(main._safe_download_name("../evil\r\n.txt", "fallback.txt"), "evil .txt")
        self.assertEqual(main._safe_download_name("", "fallback.txt"), "fallback.txt")


if __name__ == "__main__":
    unittest.main()
