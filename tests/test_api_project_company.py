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


if __name__ == "__main__":
    unittest.main()
