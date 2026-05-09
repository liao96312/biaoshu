from __future__ import annotations

from dataclasses import dataclass

from app.config import settings
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
    utc_now,
)
from app.repositories.postgres import PostgresRepository
from app.store import InMemoryStore, store


@dataclass
class Page:
    total: int
    items: list


class JsonStateRepository:
    name = "json_state"

    def __init__(self, state: InMemoryStore = store) -> None:
        self.store = state

    def new_id(self, prefix: str) -> str:
        return self.store.new_id(prefix)

    @property
    def storage_root(self):
        return self.store.storage_root

    @property
    def state_file(self):
        return self.store.state_file

    def save(self) -> None:
        self.store.save()

    def create_project(self, project: Project) -> Project:
        self.store.projects[project.id] = project
        self.store.save()
        return project

    def create_company(self, company: Company) -> Company:
        self.store.companies[company.id] = company
        self.store.save()
        return company

    def get_company(self, company_id: str) -> Company | None:
        return self.store.companies.get(company_id)

    def list_companies(self, page: int = 1, page_size: int = 20) -> Page:
        items = list(self.store.companies.values())
        total = len(items)
        start = max(page - 1, 0) * page_size
        return Page(total=total, items=items[start : start + page_size])

    def get_project(self, project_id: str) -> Project | None:
        return self.store.projects.get(project_id)

    def list_projects(self, page: int = 1, page_size: int = 20, status: str | None = None) -> Page:
        items = list(self.store.projects.values())
        if status:
            items = [item for item in items if item.status.value == status]
        total = len(items)
        start = max(page - 1, 0) * page_size
        return Page(total=total, items=items[start : start + page_size])

    def touch_project(self, project_id: str) -> None:
        project = self.get_project(project_id)
        if project is None:
            return
        project.updated_at = utc_now()
        self.store.save()

    def upsert_task(self, task: Task) -> Task:
        self.store.tasks[task.id] = task
        self.store.save()
        return task

    def get_task(self, task_id: str) -> Task | None:
        return self.store.tasks.get(task_id)

    def list_project_tasks(self, project_id: str) -> list[Task]:
        return [item for item in self.store.tasks.values() if item.project_id == project_id]

    def project_counts(self, project_id: str) -> dict[str, object]:
        return self.store.project_counts(project_id)

    def upsert_document(self, document: Document) -> Document:
        self.store.documents[document.id] = document
        self.store.save()
        return document

    def get_document(self, document_id: str) -> Document | None:
        return self.store.documents.get(document_id)

    def list_project_documents(self, project_id: str) -> list[Document]:
        return [item for item in self.store.documents.values() if item.project_id == project_id]

    def list_risks(
        self,
        project_id: str,
        severity: str | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Page:
        items = [item for item in self.store.risks.values() if item.project_id == project_id]
        if severity:
            items = [item for item in items if item.severity.value == severity]
        if status:
            items = [item for item in items if item.status.value == status]
        total = len(items)
        start = max(page - 1, 0) * page_size
        return Page(total=total, items=items[start : start + page_size])

    def get_risk(self, risk_id: str) -> RiskItem | None:
        return self.store.risks.get(risk_id)

    def upsert_risk(self, risk: RiskItem) -> RiskItem:
        self.store.risks[risk.id] = risk
        self.store.save()
        return risk

    def list_deviations(
        self,
        project_id: str,
        deviation_type: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Page:
        items = [item for item in self.store.deviations.values() if item.project_id == project_id]
        if deviation_type:
            items = [item for item in items if item.deviation_type.value == deviation_type]
        total = len(items)
        start = max(page - 1, 0) * page_size
        return Page(total=total, items=items[start : start + page_size])

    def get_deviation(self, deviation_id: str) -> DeviationResult | None:
        return self.store.deviations.get(deviation_id)

    def upsert_deviation(self, deviation: DeviationResult) -> DeviationResult:
        self.store.deviations[deviation.id] = deviation
        self.store.save()
        return deviation

    def list_project_deviations(self, project_id: str) -> list[DeviationResult]:
        return [item for item in self.store.deviations.values() if item.project_id == project_id]

    def list_project_risks(self, project_id: str) -> list[RiskItem]:
        return [item for item in self.store.risks.values() if item.project_id == project_id]

    def get_tech_requirement(self, requirement_id: str):
        return self.store.tech_requirements.get(requirement_id)

    def upsert_tech_requirement(self, requirement):
        self.store.tech_requirements[requirement.id] = requirement
        self.store.save()
        return requirement

    def list_project_requirements(self, project_id: str):
        return [item for item in self.store.tech_requirements.values() if item.project_id == project_id]

    def list_project_materials(
        self,
        project_id: str,
        product_ids: list[str] | None = None,
    ) -> list[Material]:
        project = self.get_project(project_id)
        if project is None:
            return []
        return [
            item
            for item in self.store.materials.values()
            if item.company_id == project.company_id
            and item.material_type == "product"
            and (not product_ids or item.id in product_ids)
        ]

    def list_company_materials(self, company_id: str) -> list[Material]:
        return [item for item in self.store.materials.values() if item.company_id == company_id]

    def clear_project_risks(self, project_id: str) -> None:
        for item_id, item in list(self.store.risks.items()):
            if item.project_id == project_id:
                self.store.risks.pop(item_id)
        self.store.save()

    def clear_project_requirements_and_deviations(self, project_id: str) -> None:
        for bucket in [self.store.tech_requirements, self.store.deviations]:
            for item_id, item in list(bucket.items()):
                if item.project_id == project_id:
                    bucket.pop(item_id)
        self.store.save()

    def clear_project_deviations(self, project_id: str) -> None:
        for item_id, item in list(self.store.deviations.items()):
            if item.project_id == project_id:
                self.store.deviations.pop(item_id)
        self.store.save()

    def upsert_export(self, export: ExportRecord) -> ExportRecord:
        self.store.exports[export.id] = export
        self.store.save()
        return export

    def get_export(self, export_id: str) -> ExportRecord | None:
        return self.store.exports.get(export_id)

    def list_project_exports(self, project_id: str) -> list[ExportRecord]:
        return [item for item in self.store.exports.values() if item.project_id == project_id]

    def upsert_material(self, material: Material) -> Material:
        self.store.materials[material.id] = material
        self.store.save()
        return material

    def list_materials(
        self,
        company_id: str,
        material_type: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Page:
        items = [item for item in self.store.materials.values() if item.company_id == company_id]
        if material_type:
            items = [item for item in items if item.material_type == material_type]
        total = len(items)
        start = max(page - 1, 0) * page_size
        return Page(total=total, items=items[start : start + page_size])

    def list_all_materials(self) -> list[Material]:
        return list(self.store.materials.values())

    def get_material(self, material_id: str) -> Material | None:
        return self.store.materials.get(material_id)

    def delete_material(self, material_id: str) -> None:
        self.store.materials.pop(material_id, None)
        self.store.save()

    def upsert_feedback(self, feedback: ReviewFeedback) -> ReviewFeedback:
        self.store.feedback[feedback.id] = feedback
        self.store.save()
        return feedback

    def list_feedback(self, project_id: str) -> list[ReviewFeedback]:
        return [item for item in self.store.feedback.values() if item.project_id == project_id]

    def upsert_activity_log(self, activity: ActivityLog) -> ActivityLog:
        self.store.activity_logs[activity.id] = activity
        self.store.save()
        return activity

    def list_activity_logs(self, project_id: str | None = None, limit: int = 100) -> list[ActivityLog]:
        items = list(self.store.activity_logs.values())
        if project_id:
            items = [item for item in items if item.project_id == project_id]
        items.sort(key=lambda item: item.created_at, reverse=True)
        return items[:limit]

    def delete_project(self, project_id: str) -> None:
        buckets = [
            self.store.documents,
            self.store.tasks,
            self.store.risks,
            self.store.tech_requirements,
            self.store.deviations,
            self.store.exports,
            self.store.feedback,
            self.store.activity_logs,
        ]
        for bucket in buckets:
            for item_id, item in list(bucket.items()):
                if getattr(item, "project_id", None) == project_id:
                    bucket.pop(item_id, None)
        self.store.projects.pop(project_id, None)
        self.store.save()

    def metrics(self) -> dict[str, object]:
        task_status: dict[str, int] = {}
        risk_severity: dict[str, int] = {}
        deviation_type: dict[str, int] = {}
        project_status: dict[str, int] = {}
        for project in self.store.projects.values():
            project_status[project.status.value] = project_status.get(project.status.value, 0) + 1
        for task in self.store.tasks.values():
            task_status[task.status.value] = task_status.get(task.status.value, 0) + 1
        for risk in self.store.risks.values():
            risk_severity[risk.severity.value] = risk_severity.get(risk.severity.value, 0) + 1
        for deviation in self.store.deviations.values():
            deviation_type[deviation.deviation_type.value] = deviation_type.get(deviation.deviation_type.value, 0) + 1
        return {
            "projects": {"total": len(self.store.projects), "by_status": project_status},
            "tasks": {"total": len(self.store.tasks), "by_status": task_status},
            "documents": {"total": len(self.store.documents)},
            "risks": {"total": len(self.store.risks), "by_severity": risk_severity},
            "deviations": {"total": len(self.store.deviations), "by_type": deviation_type},
            "materials": {"total": len(self.store.materials)},
            "exports": {"total": len(self.store.exports)},
            "feedback": {"total": len(self.store.feedback)},
            "activity_logs": {"total": len(self.store.activity_logs)},
        }


class HybridPostgresRepository(JsonStateRepository):
    """JSON runtime store plus PostgreSQL mirror/full reads.

    ``postgres_mirror`` keeps JSON as the primary read path and mirrors writes
    to PostgreSQL. ``postgres`` uses PostgreSQL for reads while retaining the
    local JSON file as a lightweight fallback and migration aid.
    """

    def __init__(self, state: InMemoryStore = store) -> None:
        super().__init__(state)
        self.postgres = PostgresRepository(settings.database_url)
        self.read_from_postgres = settings.storage_backend == "postgres"
        self.name = "postgres" if self.read_from_postgres else "json_state+postgres_mirror"

    def get_company(self, company_id: str) -> Company | None:
        if self.read_from_postgres:
            return self.postgres.get_company(company_id)
        return super().get_company(company_id)

    def list_companies(self, page: int = 1, page_size: int = 20) -> Page:
        if self.read_from_postgres:
            offset = max(page - 1, 0) * page_size
            return Page(total=self.postgres.count_companies(), items=self.postgres.list_companies(page_size, offset))
        return super().list_companies(page, page_size)

    def get_project(self, project_id: str) -> Project | None:
        if self.read_from_postgres:
            return self.postgres.get_project(project_id)
        return super().get_project(project_id)

    def list_projects(self, page: int = 1, page_size: int = 20, status: str | None = None) -> Page:
        if self.read_from_postgres:
            offset = max(page - 1, 0) * page_size
            return Page(
                total=self.postgres.count_projects(status=status),
                items=self.postgres.list_projects(page_size, offset, status=status),
            )
        return super().list_projects(page, page_size, status=status)

    def get_task(self, task_id: str) -> Task | None:
        if self.read_from_postgres:
            return self.postgres.get_task(task_id)
        return super().get_task(task_id)

    def list_project_tasks(self, project_id: str) -> list[Task]:
        if self.read_from_postgres:
            return self.postgres.list_project_tasks(project_id)
        return super().list_project_tasks(project_id)

    def project_counts(self, project_id: str) -> dict[str, object]:
        if self.read_from_postgres:
            return self.postgres.project_counts(project_id)
        return super().project_counts(project_id)

    def get_document(self, document_id: str) -> Document | None:
        if self.read_from_postgres:
            return self.postgres.get_document(document_id)
        return super().get_document(document_id)

    def list_project_documents(self, project_id: str) -> list[Document]:
        if self.read_from_postgres:
            return self.postgres.list_project_documents(project_id)
        return super().list_project_documents(project_id)

    def list_risks(
        self,
        project_id: str,
        severity: str | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Page:
        if self.read_from_postgres:
            offset = max(page - 1, 0) * page_size
            return Page(
                total=self.postgres.count_risks(project_id, severity=severity, status=status),
                items=self.postgres.list_risks(project_id, page_size, offset, severity=severity, status=status),
            )
        return super().list_risks(project_id, severity=severity, status=status, page=page, page_size=page_size)

    def get_risk(self, risk_id: str) -> RiskItem | None:
        if self.read_from_postgres:
            return self.postgres.get_risk(risk_id)
        return super().get_risk(risk_id)

    def list_project_risks(self, project_id: str) -> list[RiskItem]:
        if self.read_from_postgres:
            return self.postgres.list_project_risks(project_id)
        return super().list_project_risks(project_id)

    def list_deviations(
        self,
        project_id: str,
        deviation_type: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Page:
        if self.read_from_postgres:
            offset = max(page - 1, 0) * page_size
            return Page(
                total=self.postgres.count_deviations(project_id, deviation_type=deviation_type),
                items=self.postgres.list_deviations(project_id, page_size, offset, deviation_type=deviation_type),
            )
        return super().list_deviations(project_id, deviation_type=deviation_type, page=page, page_size=page_size)

    def get_deviation(self, deviation_id: str) -> DeviationResult | None:
        if self.read_from_postgres:
            return self.postgres.get_deviation(deviation_id)
        return super().get_deviation(deviation_id)

    def list_project_deviations(self, project_id: str) -> list[DeviationResult]:
        if self.read_from_postgres:
            return self.postgres.list_project_deviations(project_id)
        return super().list_project_deviations(project_id)

    def get_tech_requirement(self, requirement_id: str):
        if self.read_from_postgres:
            return self.postgres.get_tech_requirement(requirement_id)
        return super().get_tech_requirement(requirement_id)

    def list_project_requirements(self, project_id: str):
        if self.read_from_postgres:
            return self.postgres.list_project_requirements(project_id)
        return super().list_project_requirements(project_id)

    def list_project_materials(self, project_id: str, product_ids: list[str] | None = None) -> list[Material]:
        if self.read_from_postgres:
            return self.postgres.list_project_materials(project_id, product_ids=product_ids)
        return super().list_project_materials(project_id, product_ids=product_ids)

    def list_company_materials(self, company_id: str) -> list[Material]:
        if self.read_from_postgres:
            return self.postgres.list_company_materials(company_id)
        return super().list_company_materials(company_id)

    def list_materials(
        self,
        company_id: str,
        material_type: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Page:
        if self.read_from_postgres:
            offset = max(page - 1, 0) * page_size
            return Page(
                total=self.postgres.count_materials(company_id, material_type=material_type),
                items=self.postgres.list_materials(company_id, page_size, offset, material_type=material_type),
            )
        return super().list_materials(company_id, material_type=material_type, page=page, page_size=page_size)

    def list_all_materials(self) -> list[Material]:
        if self.read_from_postgres:
            return self.postgres.list_all_materials()
        return super().list_all_materials()

    def get_material(self, material_id: str) -> Material | None:
        if self.read_from_postgres:
            return self.postgres.get_material(material_id)
        return super().get_material(material_id)

    def get_export(self, export_id: str) -> ExportRecord | None:
        if self.read_from_postgres:
            return self.postgres.get_export(export_id)
        return super().get_export(export_id)

    def list_project_exports(self, project_id: str) -> list[ExportRecord]:
        if self.read_from_postgres:
            return self.postgres.list_project_exports(project_id)
        return super().list_project_exports(project_id)

    def list_feedback(self, project_id: str) -> list[ReviewFeedback]:
        if self.read_from_postgres:
            return self.postgres.list_feedback(project_id)
        return super().list_feedback(project_id)

    def list_activity_logs(self, project_id: str | None = None, limit: int = 100) -> list[ActivityLog]:
        if self.read_from_postgres:
            return self.postgres.list_activity_logs(project_id, limit)
        return super().list_activity_logs(project_id, limit)

    def metrics(self) -> dict[str, object]:
        if self.read_from_postgres:
            return self.postgres.metrics()
        return super().metrics()

    def create_project(self, project: Project) -> Project:
        project = super().create_project(project)
        self.postgres.upsert_project(project)
        return project

    def create_company(self, company: Company) -> Company:
        company = super().create_company(company)
        self.postgres.upsert_company(company)
        return company

    def touch_project(self, project_id: str) -> None:
        super().touch_project(project_id)
        project = self.get_project(project_id)
        if project:
            self.postgres.upsert_project(project)

    def upsert_task(self, task: Task) -> Task:
        task = super().upsert_task(task)
        self.postgres.upsert_task(task)
        return task

    def upsert_document(self, document: Document) -> Document:
        document = super().upsert_document(document)
        self.postgres.upsert_document(document)
        return document

    def upsert_risk(self, risk: RiskItem) -> RiskItem:
        risk = super().upsert_risk(risk)
        self.postgres.upsert_risk(risk)
        return risk

    def upsert_deviation(self, deviation: DeviationResult) -> DeviationResult:
        deviation = super().upsert_deviation(deviation)
        self.postgres.upsert_deviation(deviation)
        return deviation

    def upsert_tech_requirement(self, requirement):
        requirement = super().upsert_tech_requirement(requirement)
        self.postgres.upsert_tech_requirement(requirement)
        return requirement

    def upsert_export(self, export: ExportRecord) -> ExportRecord:
        export = super().upsert_export(export)
        self.postgres.upsert_export(export)
        return export

    def upsert_material(self, material: Material) -> Material:
        material = super().upsert_material(material)
        self.postgres.upsert_material(material)
        return material

    def clear_project_risks(self, project_id: str) -> None:
        super().clear_project_risks(project_id)
        self.postgres.clear_project_risks(project_id)

    def clear_project_requirements_and_deviations(self, project_id: str) -> None:
        super().clear_project_requirements_and_deviations(project_id)
        self.postgres.clear_project_requirements_and_deviations(project_id)

    def clear_project_deviations(self, project_id: str) -> None:
        super().clear_project_deviations(project_id)
        self.postgres.clear_project_deviations(project_id)

    def delete_material(self, material_id: str) -> None:
        super().delete_material(material_id)
        self.postgres.delete_material(material_id)

    def upsert_feedback(self, feedback: ReviewFeedback) -> ReviewFeedback:
        feedback = super().upsert_feedback(feedback)
        self.postgres.upsert_feedback(feedback)
        return feedback

    def upsert_activity_log(self, activity: ActivityLog) -> ActivityLog:
        activity = super().upsert_activity_log(activity)
        self.postgres.upsert_activity_log(activity)
        return activity

    def delete_project(self, project_id: str) -> None:
        super().delete_project(project_id)
        self.postgres.delete_project(project_id)


def create_repository():
    if settings.storage_backend in {"postgres", "postgres_mirror"}:
        if not settings.database_url:
            raise RuntimeError("DATABASE_URL is required for postgres storage backend")
        return HybridPostgresRepository()
    return JsonStateRepository()


repository = create_repository()
