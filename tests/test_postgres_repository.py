import unittest

from app.models import (
    ActivityLog,
    Company,
    DeviationResult,
    Document,
    ExportRecord,
    Material,
    Project,
    ReviewFeedback,
    RiskItem,
    Severity,
    Task,
    TaskStatus,
    TechRequirement,
)
from app.repositories.postgres import (
    PostgresRepository,
    _deviation_params,
    _deviation_from_row,
    _document_params,
    _document_from_row,
    _activity_from_row,
    _activity_params,
    _export_params,
    _export_from_row,
    _company_params,
    _company_from_row,
    _material_from_row,
    _material_params,
    _project_params,
    _risk_from_row,
    _risk_params,
    _task_from_row,
    _task_params,
    _tech_requirement_from_row,
    _tech_requirement_params,
    _feedback_from_row,
    _feedback_params,
)


class PostgresRepositoryTests(unittest.TestCase):
    def test_requires_psycopg_when_instantiated(self):
        try:
            import psycopg  # noqa: F401
        except ImportError:
            with self.assertRaises(RuntimeError):
                PostgresRepository("postgresql://example")
        else:
            repo = PostgresRepository("postgresql://example")
            self.assertEqual(repo.database_url, "postgresql://example")

    def test_param_serializers_use_database_values(self):
        company = Company(id="comp_1", name="Company")
        self.assertEqual(_company_params(company)["name"], "Company")
        project = Project(id="proj_1", name="项目", tender_name="招标", company_id="comp_1")
        self.assertEqual(_project_params(project)["status"], "created")

        document = Document(
            id="doc_1",
            project_id=project.id,
            file_name="tender.txt",
            file_type="tender",
            storage_path="storage/tender.txt",
            object_storage_uri="storage/objects/projects/proj_1/doc_1.txt",
            parse_status=TaskStatus.DONE,
        )
        self.assertEqual(_document_params(document)["parse_status"], "done")
        self.assertEqual(_document_params(document)["object_storage_uri"], "storage/objects/projects/proj_1/doc_1.txt")

        task = Task(id="task_1", project_id=project.id, task_type="document_parse")
        self.assertEqual(_task_params(task)["status"], "pending")
        self.assertEqual(_task_params(task)["steps"], "[]")

        risk = RiskItem(
            id="risk_1",
            project_id=project.id,
            risk_type="资格性废标",
            requirement="须提供材料",
            trigger_keyword="须提供",
            severity=Severity.HIGH,
            source_text="须提供材料，否则投标无效",
            ai_reason="命中规则",
            suggestion="补齐材料",
            confidence=0.9,
            material_ids=["mat_1"],
        )
        self.assertEqual(_risk_params(risk)["severity"], "high")
        self.assertEqual(_risk_params(risk)["material_ids"], '["mat_1"]')

        requirement = TechRequirement(
            id="param_1",
            project_id=project.id,
            item_name="交换机",
            parameter_name="包转发率",
            operator=">=",
            required_value=720,
            unit="Mpps",
            source_text="包转发率≥720Mpps",
        )
        self.assertEqual(_tech_requirement_params(requirement)["operator"], ">=")

        deviation = DeviationResult(
            id="param_1",
            project_id=project.id,
            tech_requirement_id=requirement.id,
            item="交换机",
            parameter="包转发率",
            required_value=">=720Mpps",
        )
        self.assertEqual(_deviation_params(deviation)["deviation_type"], "unknown")

        material = Material(
            id="mat_1",
            company_id="comp_1",
            file_name="产品.txt",
            material_type="product",
            storage_path="storage/product.txt",
            object_storage_uri="storage/objects/companies/comp_1/mat_1.txt",
            tags=["交换机"],
        )
        self.assertEqual(_material_params(material)["tags"], '["交换机"]')
        self.assertEqual(_material_params(material)["object_storage_uri"], "storage/objects/companies/comp_1/mat_1.txt")

        export = ExportRecord(
            id="exp_1",
            project_id=project.id,
            export_type="deviation_table",
            format="xlsx",
            file_path="storage/exp.xlsx",
            task_id="task_1",
        )
        self.assertEqual(_export_params(export)["status"], "done")

        feedback = ReviewFeedback(
            id="fb_1",
            project_id=project.id,
            target_type="risk",
            target_id="risk_1",
            action="confirmed",
            before={"status": "pending"},
            after={"status": "confirmed"},
        )
        self.assertEqual(_feedback_params(feedback)["before"], '{"status": "pending"}')
        activity = ActivityLog(
            id="act_1",
            actor="api_key:test",
            method="POST",
            path="/api/v1/projects/proj_1/complete",
            status_code=409,
            project_id=project.id,
            action="POST /api/v1/projects/proj_{id}/complete",
            detail={"blocked": True},
        )
        self.assertEqual(_activity_params(activity)["status_code"], 409)
        self.assertEqual(_activity_params(activity)["detail"], '{"blocked": true}')

    def test_row_deserializers_restore_models(self):
        project = Project(id="proj_1", name="项目", tender_name="招标", company_id="comp_1")
        company = Company(id="comp_1", name="Company")
        document = Document(
            id="doc_1",
            project_id=project.id,
            file_name="tender.txt",
            file_type="tender",
            storage_path="storage/tender.txt",
            object_storage_uri="storage/objects/projects/proj_1/doc_1.txt",
            parse_status=TaskStatus.DONE,
        )
        task = Task(id="task_1", project_id=project.id, task_type="document_parse", result={"ok": True})
        risk = RiskItem(
            id="risk_1",
            project_id=project.id,
            risk_type="资格性废标",
            requirement="须提供材料",
            trigger_keyword="须提供",
            severity=Severity.HIGH,
            source_text="须提供材料，否则投标无效",
            ai_reason="命中规则",
            suggestion="补齐材料",
            confidence=0.9,
            material_ids=["mat_1"],
        )
        requirement = TechRequirement(
            id="param_1",
            project_id=project.id,
            item_name="交换机",
            parameter_name="包转发率",
            operator=">=",
            required_value=720,
            unit="Mpps",
            source_text="包转发率≥720Mpps",
        )
        deviation = DeviationResult(
            id="param_1",
            project_id=project.id,
            tech_requirement_id=requirement.id,
            item="交换机",
            parameter="包转发率",
            required_value=">=720Mpps",
        )
        material = Material(
            id="mat_1",
            company_id="comp_1",
            file_name="产品.txt",
            material_type="product",
            storage_path="storage/product.txt",
            object_storage_uri="storage/objects/companies/comp_1/mat_1.txt",
            tags=["交换机"],
        )
        export = ExportRecord(
            id="exp_1",
            project_id=project.id,
            export_type="deviation_table",
            format="xlsx",
            file_path="storage/exp.xlsx",
            task_id="task_1",
        )
        feedback = ReviewFeedback(
            id="fb_1",
            project_id=project.id,
            target_type="risk",
            target_id="risk_1",
            action="confirmed",
            before={"status": "pending"},
            after={"status": "confirmed"},
        )
        activity = ActivityLog(
            id="act_1",
            actor="api_key:test",
            method="POST",
            path="/api/v1/projects/proj_1/complete",
            status_code=409,
            project_id=project.id,
            action="POST /api/v1/projects/proj_{id}/complete",
            detail={"blocked": True},
        )

        self.assertEqual(_company_from_row(_company_params(company)).name, "Company")
        self.assertEqual(_document_from_row(_document_params(document)).parse_status.value, "done")
        self.assertEqual(_task_from_row(_task_params(task)).result["ok"], True)
        self.assertEqual(_risk_from_row(_risk_params(risk)).material_ids, ["mat_1"])
        self.assertEqual(_tech_requirement_from_row(_tech_requirement_params(requirement)).unit, "Mpps")
        self.assertEqual(_deviation_from_row(_deviation_params(deviation)).deviation_type.value, "unknown")
        self.assertEqual(_material_from_row(_material_params(material)).tags, ["交换机"])
        self.assertEqual(_export_from_row(_export_params(export)).format, "xlsx")
        self.assertEqual(_feedback_from_row(_feedback_params(feedback)).before["status"], "pending")
        self.assertEqual(_activity_from_row(_activity_params(activity)).detail["blocked"], True)


if __name__ == "__main__":
    unittest.main()
