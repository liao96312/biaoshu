import tempfile
import unittest
from pathlib import Path

from app.models import ActivityLog, Company, Document, ExportRecord, Project, ReviewFeedback, RiskItem, Severity, Task
from app.repositories.runtime import JsonStateRepository
from app.store import InMemoryStore


class RuntimeRepositoryTests(unittest.TestCase):
    def test_project_task_document_and_risk_methods(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            state = InMemoryStore(storage_root=temp_dir, state_file=str(Path(temp_dir) / "state.json"))
            repo = JsonStateRepository(state)
            company = repo.create_company(Company(id="comp_1", name="Company"))
            project = repo.create_project(
                Project(id="proj_1", name="项目", tender_name="招标", company_id="comp_1")
            )
            repo.upsert_task(Task(id="task_1", project_id=project.id, task_type="parse"))
            repo.upsert_task(Task(id="task_other", project_id="proj_other", task_type="parse"))
            repo.upsert_document(
                Document(
                    id="doc_1",
                    project_id=project.id,
                    file_name="tender.txt",
                    file_type="tender",
                    storage_path="tender.txt",
                )
            )
            repo.upsert_risk(
                RiskItem(
                    id="risk_1",
                    project_id=project.id,
                    risk_type="资格性废标",
                    requirement="须提供材料",
                    trigger_keyword="须提供",
                    severity=Severity.HIGH,
                    source_text="须提供材料",
                    ai_reason="命中规则",
                    suggestion="补齐材料",
                    confidence=0.9,
                )
            )

            self.assertEqual(repo.get_project(project.id).name, "项目")
            self.assertEqual(repo.get_company(company.id).name, "Company")
            self.assertEqual(repo.list_companies().total, 1)
            self.assertEqual(repo.get_task("task_1").task_type, "parse")
            self.assertEqual(repo.get_document("doc_1").file_name, "tender.txt")
            self.assertEqual(repo.list_risks(project.id).total, 1)
            repo.upsert_feedback(
                ReviewFeedback(
                    id="fb_1",
                    project_id=project.id,
                    target_type="risk",
                    target_id="risk_1",
                    action="confirmed",
                )
            )
            self.assertEqual(repo.list_feedback(project.id)[0].action, "confirmed")
            repo.upsert_activity_log(
                ActivityLog(
                    id="act_1",
                    actor="api_key:test",
                    method="POST",
                    path="/api/v1/projects/proj_1/complete",
                    status_code=409,
                    project_id=project.id,
                    action="POST /api/v1/projects/proj_{id}/complete",
                )
            )
            repo.upsert_export(
                ExportRecord(
                    id="exp_1",
                    project_id=project.id,
                    export_type="risk_report",
                    format="docx",
                    file_path="storage/exports/exp_1.docx",
                    task_id="task_1",
                )
            )
            self.assertEqual(repo.list_activity_logs(project.id)[0].status_code, 409)
            self.assertEqual(repo.list_project_exports(project.id)[0].id, "exp_1")
            self.assertEqual(repo.metrics()["projects"]["total"], 1)
            repo.delete_project(project.id)
            self.assertIsNone(repo.get_project(project.id))
            self.assertIsNone(repo.get_task("task_1"))
            self.assertEqual(repo.get_task("task_other").project_id, "proj_other")
            self.assertEqual(repo.list_activity_logs(project.id), [])


if __name__ == "__main__":
    unittest.main()
