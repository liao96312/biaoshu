import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

import app.main as main
from app.models import ProjectCreate
from app.models import Project
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

    def test_ready_response_reports_storage_check(self):
        response = main.readyz()
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'"storage"', response.body)

    def test_safe_download_name_strips_path_and_control_characters(self):
        self.assertEqual(main._safe_download_name("../evil\r\n.txt", "fallback.txt"), "evil .txt")
        self.assertEqual(main._safe_download_name("", "fallback.txt"), "fallback.txt")

    def test_request_id_prefers_valid_header(self):
        request = Mock()
        request.headers = {"x-request-id": "trace-123"}
        self.assertEqual(main._request_id_from_headers(request), "trace-123")

    def test_request_id_rejects_control_characters(self):
        request = Mock()
        request.headers = {"x-request-id": "bad\ntrace"}
        self.assertTrue(main._request_id_from_headers(request).startswith("req_"))

    def test_tenant_header_hides_other_company_project(self):
        original_repository = main.repository
        with tempfile.TemporaryDirectory() as temp_dir:
            state = InMemoryStore(storage_root=temp_dir, state_file=str(Path(temp_dir) / "state.json"))
            main.repository = JsonStateRepository(state)
            main.repository.create_project(Project(id="proj_a", name="A", tender_name="Tender", company_id="comp_a"))
            token = main.tenant_context.set("comp_b")
            try:
                with self.assertRaises(main.HTTPException) as raised:
                    main.get_project_or_404("proj_a")
                self.assertEqual(raised.exception.status_code, 404)
            finally:
                main.tenant_context.reset(token)
                main.repository = original_repository

    def test_tenant_project_list_only_returns_current_company(self):
        original_repository = main.repository
        with tempfile.TemporaryDirectory() as temp_dir:
            state = InMemoryStore(storage_root=temp_dir, state_file=str(Path(temp_dir) / "state.json"))
            main.repository = JsonStateRepository(state)
            main.repository.create_project(Project(id="proj_a", name="A", tender_name="Tender", company_id="comp_a"))
            main.repository.create_project(Project(id="proj_b", name="B", tender_name="Tender", company_id="comp_b"))
            token = main.tenant_context.set("comp_b")
            try:
                page = main._list_tenant_projects("comp_b")
                self.assertEqual(page.total, 1)
                self.assertEqual(page.items[0].id, "proj_b")
            finally:
                main.tenant_context.reset(token)
                main.repository = original_repository


if __name__ == "__main__":
    unittest.main()
