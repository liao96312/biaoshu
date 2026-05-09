from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from app.models import (
    ActivityLog,
    DeviationResult,
    Document,
    ExportRecord,
    Company,
    Material,
    Project,
    ReviewFeedback,
    RiskItem,
    Task,
    TechRequirement,
)


class PostgresRepository:
    def __init__(self, database_url: str) -> None:
        if not database_url:
            raise ValueError("database_url is required")
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RuntimeError("psycopg is not installed") from exc
        self._psycopg = psycopg
        self._dict_row = dict_row
        self.database_url = database_url

    def ping(self) -> bool:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
                return cursor.fetchone()[0] == 1

    def initialize_schema(self, schema_path: str | Path) -> None:
        sql = Path(schema_path).read_text(encoding="utf-8")
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql)
            conn.commit()

    def upsert_project(self, project: Project) -> None:
        sql = """
        INSERT INTO project (id, name, tender_name, company_id, status, created_at, updated_at)
        VALUES (%(id)s, %(name)s, %(tender_name)s, %(company_id)s, %(status)s, %(created_at)s, %(updated_at)s)
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            tender_name = EXCLUDED.tender_name,
            company_id = EXCLUDED.company_id,
            status = EXCLUDED.status,
            updated_at = EXCLUDED.updated_at
        """
        self._execute(sql, _project_params(project))

    def upsert_company(self, company: Company) -> None:
        sql = """
        INSERT INTO company (id, name, created_at)
        VALUES (%(id)s, %(name)s, %(created_at)s)
        ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name
        """
        self._execute(sql, _company_params(company))

    def get_company(self, company_id: str) -> Company | None:
        with self._connect(row_factory=self._dict_row) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM company WHERE id = %s", (company_id,))
                row = cursor.fetchone()
        return _company_from_row(row) if row else None

    def count_companies(self) -> int:
        return self._count("company")

    def list_companies(self, limit: int = 20, offset: int = 0) -> list[Company]:
        sql = "SELECT * FROM company ORDER BY created_at DESC LIMIT %s OFFSET %s"
        with self._connect(row_factory=self._dict_row) as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, (limit, offset))
                rows = cursor.fetchall()
        return [_company_from_row(row) for row in rows]

    def get_project(self, project_id: str) -> Project | None:
        with self._connect(row_factory=self._dict_row) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM project WHERE id = %s", (project_id,))
                row = cursor.fetchone()
        return _project_from_row(row) if row else None

    def count_projects(self, status: str | None = None) -> int:
        if status:
            return self._count("project", "status = %s", [status])
        return self._count("project")

    def list_projects(self, limit: int = 20, offset: int = 0, status: str | None = None) -> list[Project]:
        clauses = []
        params: list[Any] = []
        if status:
            clauses.append("status = %s")
            params.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.extend([limit, offset])
        sql = f"SELECT * FROM project {where} ORDER BY created_at DESC LIMIT %s OFFSET %s"
        with self._connect(row_factory=self._dict_row) as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                rows = cursor.fetchall()
        return [_project_from_row(row) for row in rows]

    def project_counts(self, project_id: str) -> dict[str, object]:
        with self._connect(row_factory=self._dict_row) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT severity, COUNT(*) AS count FROM risk_item WHERE project_id = %s GROUP BY severity",
                    (project_id,),
                )
                risk_rows = cursor.fetchall()
                cursor.execute(
                    "SELECT deviation_type, COUNT(*) AS count FROM deviation_result WHERE project_id = %s GROUP BY deviation_type",
                    (project_id,),
                )
                deviation_rows = cursor.fetchall()
                cursor.execute("SELECT COUNT(*) FROM tech_requirement WHERE project_id = %s", (project_id,))
                requirement_count = cursor.fetchone()["count"]
        risk_count = {"high": 0, "medium": 0, "low": 0}
        for row in risk_rows:
            risk_count[str(row["severity"])] = int(row["count"])
        deviation_count: dict[str, int] = defaultdict(int)
        for row in deviation_rows:
            deviation_count[str(row["deviation_type"])] = int(row["count"])
        return {
            "risk_count": risk_count,
            "tech_param_count": int(requirement_count),
            "deviation_count": dict(deviation_count),
        }

    def upsert_document(self, document: Document) -> None:
        sql = """
        INSERT INTO document (id, project_id, file_name, file_type, storage_path, object_storage_uri, parsed_text, page_count, parse_status, created_at)
        VALUES (%(id)s, %(project_id)s, %(file_name)s, %(file_type)s, %(storage_path)s, %(object_storage_uri)s, %(parsed_text)s, %(page_count)s, %(parse_status)s, %(created_at)s)
        ON CONFLICT (id) DO UPDATE SET
            file_name = EXCLUDED.file_name,
            file_type = EXCLUDED.file_type,
            storage_path = EXCLUDED.storage_path,
            object_storage_uri = EXCLUDED.object_storage_uri,
            parsed_text = EXCLUDED.parsed_text,
            page_count = EXCLUDED.page_count,
            parse_status = EXCLUDED.parse_status
        """
        self._execute(sql, _document_params(document))

    def get_document(self, document_id: str) -> Document | None:
        with self._connect(row_factory=self._dict_row) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM document WHERE id = %s", (document_id,))
                row = cursor.fetchone()
        return _document_from_row(row) if row else None

    def list_project_documents(self, project_id: str) -> list[Document]:
        sql = "SELECT * FROM document WHERE project_id = %s ORDER BY created_at DESC"
        with self._connect(row_factory=self._dict_row) as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, (project_id,))
                rows = cursor.fetchall()
        return [_document_from_row(row) for row in rows]

    def upsert_task(self, task: Task) -> None:
        sql = """
        INSERT INTO task (id, project_id, task_type, status, progress, current_step, steps, result, error_message, created_at, updated_at)
        VALUES (%(id)s, %(project_id)s, %(task_type)s, %(status)s, %(progress)s, %(current_step)s, %(steps)s::jsonb, %(result)s::jsonb, %(error_message)s, %(created_at)s, %(updated_at)s)
        ON CONFLICT (id) DO UPDATE SET
            status = EXCLUDED.status,
            progress = EXCLUDED.progress,
            current_step = EXCLUDED.current_step,
            steps = EXCLUDED.steps,
            result = EXCLUDED.result,
            error_message = EXCLUDED.error_message,
            updated_at = EXCLUDED.updated_at
        """
        self._execute(sql, _task_params(task))

    def get_task(self, task_id: str) -> Task | None:
        with self._connect(row_factory=self._dict_row) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM task WHERE id = %s", (task_id,))
                row = cursor.fetchone()
        return _task_from_row(row) if row else None

    def list_project_tasks(self, project_id: str) -> list[Task]:
        sql = "SELECT * FROM task WHERE project_id = %s ORDER BY created_at DESC"
        with self._connect(row_factory=self._dict_row) as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, (project_id,))
                rows = cursor.fetchall()
        return [_task_from_row(row) for row in rows]

    def upsert_risk(self, risk: RiskItem) -> None:
        sql = """
        INSERT INTO risk_item (
            id, project_id, risk_type, requirement, trigger_keyword, severity, need_material,
            source_page, source_section, source_text, ai_reason, suggestion, confidence,
            status, reviewer_note, material_ids
        )
        VALUES (
            %(id)s, %(project_id)s, %(risk_type)s, %(requirement)s, %(trigger_keyword)s, %(severity)s, %(need_material)s,
            %(source_page)s, %(source_section)s, %(source_text)s, %(ai_reason)s, %(suggestion)s, %(confidence)s,
            %(status)s, %(reviewer_note)s, %(material_ids)s::jsonb
        )
        ON CONFLICT (id) DO UPDATE SET
            risk_type = EXCLUDED.risk_type,
            requirement = EXCLUDED.requirement,
            trigger_keyword = EXCLUDED.trigger_keyword,
            severity = EXCLUDED.severity,
            need_material = EXCLUDED.need_material,
            source_page = EXCLUDED.source_page,
            source_section = EXCLUDED.source_section,
            source_text = EXCLUDED.source_text,
            ai_reason = EXCLUDED.ai_reason,
            suggestion = EXCLUDED.suggestion,
            confidence = EXCLUDED.confidence,
            status = EXCLUDED.status,
            reviewer_note = EXCLUDED.reviewer_note,
            material_ids = EXCLUDED.material_ids
        """
        self._execute(sql, _risk_params(risk))

    def get_risk(self, risk_id: str) -> RiskItem | None:
        with self._connect(row_factory=self._dict_row) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM risk_item WHERE id = %s", (risk_id,))
                row = cursor.fetchone()
        return _risk_from_row(row) if row else None

    def count_risks(self, project_id: str, severity: str | None = None, status: str | None = None) -> int:
        clauses = ["project_id = %s"]
        params: list[Any] = [project_id]
        if severity:
            clauses.append("severity = %s")
            params.append(severity)
        if status:
            clauses.append("status = %s")
            params.append(status)
        return self._count("risk_item", " AND ".join(clauses), params)

    def list_risks(
        self,
        project_id: str,
        limit: int = 20,
        offset: int = 0,
        severity: str | None = None,
        status: str | None = None,
    ) -> list[RiskItem]:
        clauses = ["project_id = %s"]
        params: list[Any] = [project_id]
        if severity:
            clauses.append("severity = %s")
            params.append(severity)
        if status:
            clauses.append("status = %s")
            params.append(status)
        params.extend([limit, offset])
        sql = f"SELECT * FROM risk_item WHERE {' AND '.join(clauses)} ORDER BY created_at DESC LIMIT %s OFFSET %s"
        with self._connect(row_factory=self._dict_row) as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                rows = cursor.fetchall()
        return [_risk_from_row(row) for row in rows]

    def list_project_risks(self, project_id: str) -> list[RiskItem]:
        sql = "SELECT * FROM risk_item WHERE project_id = %s ORDER BY created_at DESC"
        with self._connect(row_factory=self._dict_row) as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, (project_id,))
                rows = cursor.fetchall()
        return [_risk_from_row(row) for row in rows]

    def upsert_tech_requirement(self, requirement: TechRequirement) -> None:
        sql = """
        INSERT INTO tech_requirement (
            id, project_id, item_name, parameter_name, operator, required_value,
            unit, is_mandatory, source_page, source_text
        )
        VALUES (
            %(id)s, %(project_id)s, %(item_name)s, %(parameter_name)s, %(operator)s, %(required_value)s,
            %(unit)s, %(is_mandatory)s, %(source_page)s, %(source_text)s
        )
        ON CONFLICT (id) DO UPDATE SET
            item_name = EXCLUDED.item_name,
            parameter_name = EXCLUDED.parameter_name,
            operator = EXCLUDED.operator,
            required_value = EXCLUDED.required_value,
            unit = EXCLUDED.unit,
            is_mandatory = EXCLUDED.is_mandatory,
            source_page = EXCLUDED.source_page,
            source_text = EXCLUDED.source_text
        """
        self._execute(sql, _tech_requirement_params(requirement))

    def get_tech_requirement(self, requirement_id: str) -> TechRequirement | None:
        with self._connect(row_factory=self._dict_row) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM tech_requirement WHERE id = %s", (requirement_id,))
                row = cursor.fetchone()
        return _tech_requirement_from_row(row) if row else None

    def list_project_requirements(self, project_id: str) -> list[TechRequirement]:
        sql = "SELECT * FROM tech_requirement WHERE project_id = %s ORDER BY created_at DESC"
        with self._connect(row_factory=self._dict_row) as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, (project_id,))
                rows = cursor.fetchall()
        return [_tech_requirement_from_row(row) for row in rows]

    def upsert_deviation(self, deviation: DeviationResult) -> None:
        sql = """
        INSERT INTO deviation_result (
            id, project_id, tech_requirement_id, item, parameter, required_value,
            our_value, deviation_type, response_text, evidence, source_page,
            confidence, reviewer_status
        )
        VALUES (
            %(id)s, %(project_id)s, %(tech_requirement_id)s, %(item)s, %(parameter)s, %(required_value)s,
            %(our_value)s, %(deviation_type)s, %(response_text)s, %(evidence)s, %(source_page)s,
            %(confidence)s, %(reviewer_status)s
        )
        ON CONFLICT (id) DO UPDATE SET
            tech_requirement_id = EXCLUDED.tech_requirement_id,
            item = EXCLUDED.item,
            parameter = EXCLUDED.parameter,
            required_value = EXCLUDED.required_value,
            our_value = EXCLUDED.our_value,
            deviation_type = EXCLUDED.deviation_type,
            response_text = EXCLUDED.response_text,
            evidence = EXCLUDED.evidence,
            source_page = EXCLUDED.source_page,
            confidence = EXCLUDED.confidence,
            reviewer_status = EXCLUDED.reviewer_status
        """
        self._execute(sql, _deviation_params(deviation))

    def get_deviation(self, deviation_id: str) -> DeviationResult | None:
        with self._connect(row_factory=self._dict_row) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM deviation_result WHERE id = %s", (deviation_id,))
                row = cursor.fetchone()
        return _deviation_from_row(row) if row else None

    def count_deviations(self, project_id: str, deviation_type: str | None = None) -> int:
        if deviation_type:
            return self._count("deviation_result", "project_id = %s AND deviation_type = %s", [project_id, deviation_type])
        return self._count("deviation_result", "project_id = %s", [project_id])

    def list_deviations(
        self,
        project_id: str,
        limit: int = 50,
        offset: int = 0,
        deviation_type: str | None = None,
    ) -> list[DeviationResult]:
        clauses = ["project_id = %s"]
        params: list[Any] = [project_id]
        if deviation_type:
            clauses.append("deviation_type = %s")
            params.append(deviation_type)
        params.extend([limit, offset])
        sql = f"SELECT * FROM deviation_result WHERE {' AND '.join(clauses)} ORDER BY created_at DESC LIMIT %s OFFSET %s"
        with self._connect(row_factory=self._dict_row) as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                rows = cursor.fetchall()
        return [_deviation_from_row(row) for row in rows]

    def list_project_deviations(self, project_id: str) -> list[DeviationResult]:
        sql = "SELECT * FROM deviation_result WHERE project_id = %s ORDER BY created_at DESC"
        with self._connect(row_factory=self._dict_row) as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, (project_id,))
                rows = cursor.fetchall()
        return [_deviation_from_row(row) for row in rows]

    def upsert_material(self, material: Material) -> None:
        sql = """
        INSERT INTO material (
            id, company_id, file_name, material_type, storage_path, object_storage_uri, parsed_text,
            page_count, name, tags, created_at
        )
        VALUES (
            %(id)s, %(company_id)s, %(file_name)s, %(material_type)s, %(storage_path)s, %(object_storage_uri)s, %(parsed_text)s,
            %(page_count)s, %(name)s, %(tags)s::jsonb, %(created_at)s
        )
        ON CONFLICT (id) DO UPDATE SET
            file_name = EXCLUDED.file_name,
            material_type = EXCLUDED.material_type,
            storage_path = EXCLUDED.storage_path,
            object_storage_uri = EXCLUDED.object_storage_uri,
            parsed_text = EXCLUDED.parsed_text,
            page_count = EXCLUDED.page_count,
            name = EXCLUDED.name,
            tags = EXCLUDED.tags
        """
        self._execute(sql, _material_params(material))

    def get_material(self, material_id: str) -> Material | None:
        with self._connect(row_factory=self._dict_row) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM material WHERE id = %s", (material_id,))
                row = cursor.fetchone()
        return _material_from_row(row) if row else None

    def count_materials(self, company_id: str, material_type: str | None = None) -> int:
        if material_type:
            return self._count("material", "company_id = %s AND material_type = %s", [company_id, material_type])
        return self._count("material", "company_id = %s", [company_id])

    def list_materials(
        self,
        company_id: str,
        limit: int = 20,
        offset: int = 0,
        material_type: str | None = None,
    ) -> list[Material]:
        clauses = ["company_id = %s"]
        params: list[Any] = [company_id]
        if material_type:
            clauses.append("material_type = %s")
            params.append(material_type)
        params.extend([limit, offset])
        sql = f"SELECT * FROM material WHERE {' AND '.join(clauses)} ORDER BY created_at DESC LIMIT %s OFFSET %s"
        with self._connect(row_factory=self._dict_row) as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                rows = cursor.fetchall()
        return [_material_from_row(row) for row in rows]

    def list_company_materials(self, company_id: str) -> list[Material]:
        sql = "SELECT * FROM material WHERE company_id = %s ORDER BY created_at DESC"
        with self._connect(row_factory=self._dict_row) as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, (company_id,))
                rows = cursor.fetchall()
        return [_material_from_row(row) for row in rows]

    def list_project_materials(self, project_id: str, product_ids: list[str] | None = None) -> list[Material]:
        project = self.get_project(project_id)
        if project is None:
            return []
        clauses = ["company_id = %s", "material_type = %s"]
        params: list[Any] = [project.company_id, "product"]
        if product_ids:
            clauses.append("id = ANY(%s)")
            params.append(product_ids)
        sql = f"SELECT * FROM material WHERE {' AND '.join(clauses)} ORDER BY created_at DESC"
        with self._connect(row_factory=self._dict_row) as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                rows = cursor.fetchall()
        return [_material_from_row(row) for row in rows]

    def list_all_materials(self) -> list[Material]:
        with self._connect(row_factory=self._dict_row) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM material ORDER BY created_at DESC")
                rows = cursor.fetchall()
        return [_material_from_row(row) for row in rows]

    def upsert_export(self, export: ExportRecord) -> None:
        sql = """
        INSERT INTO export_record (id, project_id, export_type, format, file_path, task_id, status, created_at)
        VALUES (%(id)s, %(project_id)s, %(export_type)s, %(format)s, %(file_path)s, %(task_id)s, %(status)s, %(created_at)s)
        ON CONFLICT (id) DO UPDATE SET
            export_type = EXCLUDED.export_type,
            format = EXCLUDED.format,
            file_path = EXCLUDED.file_path,
            task_id = EXCLUDED.task_id,
            status = EXCLUDED.status
        """
        self._execute(sql, _export_params(export))

    def get_export(self, export_id: str) -> ExportRecord | None:
        with self._connect(row_factory=self._dict_row) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM export_record WHERE id = %s", (export_id,))
                row = cursor.fetchone()
        return _export_from_row(row) if row else None

    def list_project_exports(self, project_id: str) -> list[ExportRecord]:
        sql = "SELECT * FROM export_record WHERE project_id = %s ORDER BY created_at DESC"
        with self._connect(row_factory=self._dict_row) as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, (project_id,))
                rows = cursor.fetchall()
        return [_export_from_row(row) for row in rows]

    def upsert_feedback(self, feedback: ReviewFeedback) -> None:
        sql = """
        INSERT INTO review_feedback (id, project_id, target_type, target_id, action, before, after, reviewer_note, created_at)
        VALUES (%(id)s, %(project_id)s, %(target_type)s, %(target_id)s, %(action)s, %(before)s::jsonb, %(after)s::jsonb, %(reviewer_note)s, %(created_at)s)
        ON CONFLICT (id) DO UPDATE SET
            target_type = EXCLUDED.target_type,
            target_id = EXCLUDED.target_id,
            action = EXCLUDED.action,
            before = EXCLUDED.before,
            after = EXCLUDED.after,
            reviewer_note = EXCLUDED.reviewer_note
        """
        self._execute(sql, _feedback_params(feedback))

    def upsert_activity_log(self, activity: ActivityLog) -> None:
        sql = """
        INSERT INTO activity_log (id, actor, method, path, status_code, project_id, action, detail, created_at)
        VALUES (%(id)s, %(actor)s, %(method)s, %(path)s, %(status_code)s, %(project_id)s, %(action)s, %(detail)s::jsonb, %(created_at)s)
        ON CONFLICT (id) DO UPDATE SET
            actor = EXCLUDED.actor,
            method = EXCLUDED.method,
            path = EXCLUDED.path,
            status_code = EXCLUDED.status_code,
            project_id = EXCLUDED.project_id,
            action = EXCLUDED.action,
            detail = EXCLUDED.detail
        """
        self._execute(sql, _activity_params(activity))

    def list_feedback(self, project_id: str) -> list[ReviewFeedback]:
        sql = "SELECT * FROM review_feedback WHERE project_id = %s ORDER BY created_at DESC"
        with self._connect(row_factory=self._dict_row) as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, (project_id,))
                rows = cursor.fetchall()
        return [_feedback_from_row(row) for row in rows]

    def list_activity_logs(self, project_id: str | None = None, limit: int = 100) -> list[ActivityLog]:
        params: list[Any] = []
        where = ""
        if project_id:
            where = "WHERE project_id = %s"
            params.append(project_id)
        params.append(limit)
        sql = f"SELECT * FROM activity_log {where} ORDER BY created_at DESC LIMIT %s"
        with self._connect(row_factory=self._dict_row) as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                rows = cursor.fetchall()
        return [_activity_from_row(row) for row in rows]

    def metrics(self) -> dict[str, object]:
        return {
            "projects": {"total": self._count("project"), "by_status": self._group_count("project", "status")},
            "tasks": {"total": self._count("task"), "by_status": self._group_count("task", "status")},
            "documents": {"total": self._count("document")},
            "risks": {"total": self._count("risk_item"), "by_severity": self._group_count("risk_item", "severity")},
            "deviations": {
                "total": self._count("deviation_result"),
                "by_type": self._group_count("deviation_result", "deviation_type"),
            },
            "materials": {"total": self._count("material")},
            "exports": {"total": self._count("export_record")},
            "feedback": {"total": self._count("review_feedback")},
            "activity_logs": {"total": self._count("activity_log")},
        }

    def clear_project_risks(self, project_id: str) -> None:
        self._execute("DELETE FROM risk_item WHERE project_id = %(project_id)s", {"project_id": project_id})

    def clear_project_requirements_and_deviations(self, project_id: str) -> None:
        self._execute("DELETE FROM deviation_result WHERE project_id = %(project_id)s", {"project_id": project_id})
        self._execute("DELETE FROM tech_requirement WHERE project_id = %(project_id)s", {"project_id": project_id})

    def clear_project_deviations(self, project_id: str) -> None:
        self._execute("DELETE FROM deviation_result WHERE project_id = %(project_id)s", {"project_id": project_id})

    def delete_material(self, material_id: str) -> None:
        self._execute("DELETE FROM material WHERE id = %(id)s", {"id": material_id})

    def delete_project(self, project_id: str) -> None:
        self._execute("DELETE FROM activity_log WHERE project_id = %(project_id)s", {"project_id": project_id})
        self._execute("DELETE FROM project WHERE id = %(project_id)s", {"project_id": project_id})

    def _execute(self, sql: str, params: dict[str, Any]) -> None:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
            conn.commit()

    def _connect(self, **kwargs):
        return self._psycopg.connect(self.database_url, **kwargs)

    def _count(self, table: str, where: str | None = None, params: list[Any] | None = None) -> int:
        sql = f"SELECT COUNT(*) AS count FROM {table}"
        if where:
            sql += f" WHERE {where}"
        with self._connect(row_factory=self._dict_row) as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, params or [])
                row = cursor.fetchone()
        return int(row["count"])

    def _group_count(self, table: str, field: str) -> dict[str, int]:
        sql = f"SELECT {field}, COUNT(*) AS count FROM {table} GROUP BY {field}"
        with self._connect(row_factory=self._dict_row) as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql)
                rows = cursor.fetchall()
        return {str(row[field]): int(row["count"]) for row in rows}


def _enum_value(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _project_params(project: Project) -> dict[str, Any]:
    return {
        "id": project.id,
        "name": project.name,
        "tender_name": project.tender_name,
        "company_id": project.company_id,
        "status": _enum_value(project.status),
        "created_at": project.created_at,
        "updated_at": project.updated_at,
    }


def _company_params(company: Company) -> dict[str, Any]:
    return {"id": company.id, "name": company.name, "created_at": company.created_at}


def _project_from_row(row: dict[str, Any]) -> Project:
    return Project(
        id=str(row["id"]),
        name=row["name"],
        tender_name=row["tender_name"],
        company_id=str(row["company_id"]),
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _company_from_row(row: dict[str, Any]) -> Company:
    return Company(id=str(row["id"]), name=row["name"], created_at=row["created_at"])


def _document_from_row(row: dict[str, Any]) -> Document:
    return Document(
        id=str(row["id"]),
        project_id=str(row["project_id"]),
        file_name=row["file_name"],
        file_type=row["file_type"],
        storage_path=row["storage_path"],
        object_storage_uri=row.get("object_storage_uri"),
        parsed_text=row.get("parsed_text") or "",
        page_count=int(row.get("page_count") or 0),
        parse_status=row["parse_status"],
        created_at=row["created_at"],
    )


def _task_from_row(row: dict[str, Any]) -> Task:
    return Task(
        id=str(row["id"]),
        project_id=str(row["project_id"]) if row.get("project_id") else None,
        task_type=row["task_type"],
        status=row["status"],
        progress=int(row.get("progress") or 0),
        current_step=row.get("current_step") or "",
        steps=_json_value(row.get("steps"), []),
        result=_json_value(row.get("result"), {}),
        error_message=row.get("error_message"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _risk_from_row(row: dict[str, Any]) -> RiskItem:
    return RiskItem(
        id=str(row["id"]),
        project_id=str(row["project_id"]),
        risk_type=row["risk_type"],
        requirement=row["requirement"],
        trigger_keyword=row.get("trigger_keyword") or "",
        severity=row["severity"],
        need_material=bool(row.get("need_material")),
        source_page=row.get("source_page"),
        source_section=row.get("source_section"),
        source_text=row["source_text"],
        ai_reason=row.get("ai_reason") or "",
        suggestion=row.get("suggestion") or "",
        confidence=float(row.get("confidence") or 0),
        status=row["status"],
        reviewer_note=row.get("reviewer_note"),
        material_ids=_json_value(row.get("material_ids"), []),
    )


def _tech_requirement_from_row(row: dict[str, Any]) -> TechRequirement:
    return TechRequirement(
        id=str(row["id"]),
        project_id=str(row["project_id"]),
        item_name=row["item_name"],
        parameter_name=row["parameter_name"],
        operator=row["operator"],
        required_value=float(row["required_value"]),
        unit=row.get("unit") or "",
        is_mandatory=bool(row.get("is_mandatory")),
        source_page=row.get("source_page"),
        source_text=row["source_text"],
    )


def _deviation_from_row(row: dict[str, Any]) -> DeviationResult:
    return DeviationResult(
        id=str(row["id"]),
        project_id=str(row["project_id"]),
        tech_requirement_id=str(row["tech_requirement_id"]),
        item=row["item"],
        parameter=row["parameter"],
        required_value=row["required_value"],
        our_value=row.get("our_value"),
        deviation_type=row["deviation_type"],
        response_text=row.get("response_text") or "",
        evidence=row.get("evidence"),
        source_page=row.get("source_page"),
        confidence=float(row.get("confidence") or 0),
        reviewer_status=row["reviewer_status"],
    )


def _material_from_row(row: dict[str, Any]) -> Material:
    return Material(
        id=str(row["id"]),
        company_id=str(row["company_id"]),
        file_name=row["file_name"],
        material_type=row["material_type"],
        storage_path=row["storage_path"],
        object_storage_uri=row.get("object_storage_uri"),
        parsed_text=row.get("parsed_text") or "",
        page_count=int(row.get("page_count") or 0),
        name=row.get("name"),
        tags=_json_value(row.get("tags"), []),
        created_at=row["created_at"],
    )


def _export_from_row(row: dict[str, Any]) -> ExportRecord:
    return ExportRecord(
        id=str(row["id"]),
        project_id=str(row["project_id"]),
        export_type=row["export_type"],
        format=row["format"],
        file_path=row["file_path"],
        task_id=str(row["task_id"]) if row.get("task_id") else "",
        status=row["status"],
        created_at=row["created_at"],
    )


def _feedback_from_row(row: dict[str, Any]) -> ReviewFeedback:
    return ReviewFeedback(
        id=str(row["id"]),
        project_id=str(row["project_id"]),
        target_type=row["target_type"],
        target_id=row["target_id"],
        action=row["action"],
        before=_json_value(row.get("before"), {}),
        after=_json_value(row.get("after"), {}),
        reviewer_note=row.get("reviewer_note"),
        created_at=row["created_at"],
    )


def _activity_from_row(row: dict[str, Any]) -> ActivityLog:
    return ActivityLog(
        id=str(row["id"]),
        actor=row["actor"],
        method=row["method"],
        path=row["path"],
        status_code=int(row["status_code"]),
        project_id=str(row["project_id"]) if row.get("project_id") else None,
        action=row["action"],
        detail=_json_value(row.get("detail"), {}),
        created_at=row["created_at"],
    )


def _document_params(document: Document) -> dict[str, Any]:
    return {
        "id": document.id,
        "project_id": document.project_id,
        "file_name": document.file_name,
        "file_type": document.file_type,
        "storage_path": document.storage_path,
        "object_storage_uri": document.object_storage_uri,
        "parsed_text": document.parsed_text,
        "page_count": document.page_count,
        "parse_status": _enum_value(document.parse_status),
        "created_at": document.created_at,
    }


def _task_params(task: Task) -> dict[str, Any]:
    return {
        "id": task.id,
        "project_id": task.project_id,
        "task_type": task.task_type,
        "status": _enum_value(task.status),
        "progress": task.progress,
        "current_step": task.current_step,
        "steps": _json([step.model_dump(mode="json") for step in task.steps]),
        "result": _json(task.result),
        "error_message": task.error_message,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }


def _risk_params(risk: RiskItem) -> dict[str, Any]:
    return {
        "id": risk.id,
        "project_id": risk.project_id,
        "risk_type": risk.risk_type,
        "requirement": risk.requirement,
        "trigger_keyword": risk.trigger_keyword,
        "severity": _enum_value(risk.severity),
        "need_material": risk.need_material,
        "source_page": risk.source_page,
        "source_section": risk.source_section,
        "source_text": risk.source_text,
        "ai_reason": risk.ai_reason,
        "suggestion": risk.suggestion,
        "confidence": risk.confidence,
        "status": _enum_value(risk.status),
        "reviewer_note": risk.reviewer_note,
        "material_ids": _json(risk.material_ids),
    }


def _tech_requirement_params(requirement: TechRequirement) -> dict[str, Any]:
    return {
        "id": requirement.id,
        "project_id": requirement.project_id,
        "item_name": requirement.item_name,
        "parameter_name": requirement.parameter_name,
        "operator": requirement.operator,
        "required_value": requirement.required_value,
        "unit": requirement.unit,
        "is_mandatory": requirement.is_mandatory,
        "source_page": requirement.source_page,
        "source_text": requirement.source_text,
    }


def _deviation_params(deviation: DeviationResult) -> dict[str, Any]:
    return {
        "id": deviation.id,
        "project_id": deviation.project_id,
        "tech_requirement_id": deviation.tech_requirement_id,
        "item": deviation.item,
        "parameter": deviation.parameter,
        "required_value": deviation.required_value,
        "our_value": deviation.our_value,
        "deviation_type": _enum_value(deviation.deviation_type),
        "response_text": deviation.response_text,
        "evidence": deviation.evidence,
        "source_page": deviation.source_page,
        "confidence": deviation.confidence,
        "reviewer_status": _enum_value(deviation.reviewer_status),
    }


def _material_params(material: Material) -> dict[str, Any]:
    return {
        "id": material.id,
        "company_id": material.company_id,
        "file_name": material.file_name,
        "material_type": material.material_type,
        "storage_path": material.storage_path,
        "object_storage_uri": material.object_storage_uri,
        "parsed_text": material.parsed_text,
        "page_count": material.page_count,
        "name": material.name,
        "tags": _json(material.tags),
        "created_at": material.created_at,
    }


def _export_params(export: ExportRecord) -> dict[str, Any]:
    return {
        "id": export.id,
        "project_id": export.project_id,
        "export_type": export.export_type,
        "format": export.format,
        "file_path": export.file_path,
        "task_id": export.task_id,
        "status": _enum_value(export.status),
        "created_at": export.created_at,
    }


def _feedback_params(feedback: ReviewFeedback) -> dict[str, Any]:
    return {
        "id": feedback.id,
        "project_id": feedback.project_id,
        "target_type": feedback.target_type,
        "target_id": feedback.target_id,
        "action": feedback.action,
        "before": _json(feedback.before),
        "after": _json(feedback.after),
        "reviewer_note": feedback.reviewer_note,
        "created_at": feedback.created_at,
    }


def _activity_params(activity: ActivityLog) -> dict[str, Any]:
    return {
        "id": activity.id,
        "actor": activity.actor,
        "method": activity.method,
        "path": activity.path,
        "status_code": activity.status_code,
        "project_id": activity.project_id,
        "action": activity.action,
        "detail": _json(activity.detail),
        "created_at": activity.created_at,
    }


def _json_value(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return value
