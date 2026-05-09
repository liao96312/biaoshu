from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from uuid import uuid4

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
    TechRequirement,
    utc_now,
)


class InMemoryStore:
    def __init__(self, storage_root: str = settings.storage_root, state_file: str = settings.state_file) -> None:
        self.storage_root = Path(storage_root)
        self.storage_root.mkdir(exist_ok=True)
        self.state_file = Path(state_file)
        self.projects: dict[str, Project] = {}
        self.companies: dict[str, Company] = {}
        self.documents: dict[str, Document] = {}
        self.tasks: dict[str, Task] = {}
        self.risks: dict[str, RiskItem] = {}
        self.tech_requirements: dict[str, TechRequirement] = {}
        self.deviations: dict[str, DeviationResult] = {}
        self.exports: dict[str, ExportRecord] = {}
        self.materials: dict[str, Material] = {}
        self.feedback: dict[str, ReviewFeedback] = {}
        self.activity_logs: dict[str, ActivityLog] = {}
        self.load()

    @staticmethod
    def new_id(prefix: str) -> str:
        return f"{prefix}_{uuid4().hex[:12]}"

    def project_counts(self, project_id: str) -> dict[str, object]:
        risks = [item for item in self.risks.values() if item.project_id == project_id]
        deviations = [
            item for item in self.deviations.values() if item.project_id == project_id
        ]
        risk_count = {"high": 0, "medium": 0, "low": 0}
        for risk in risks:
            risk_count[risk.severity.value] += 1
        deviation_count = defaultdict(int)
        for deviation in deviations:
            deviation_count[deviation.deviation_type.value] += 1
        return {
            "risk_count": risk_count,
            "tech_param_count": len(deviations),
            "deviation_count": dict(deviation_count),
        }

    def touch_project(self, project_id: str) -> None:
        if project_id in self.projects:
            self.projects[project_id].updated_at = utc_now()
            self.save()

    def save(self) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "projects": _dump_bucket(self.projects),
            "companies": _dump_bucket(self.companies),
            "documents": _dump_bucket(self.documents),
            "tasks": _dump_bucket(self.tasks),
            "risks": _dump_bucket(self.risks),
            "tech_requirements": _dump_bucket(self.tech_requirements),
            "deviations": _dump_bucket(self.deviations),
            "exports": _dump_bucket(self.exports),
            "materials": _dump_bucket(self.materials),
            "feedback": _dump_bucket(self.feedback),
            "activity_logs": _dump_bucket(self.activity_logs),
        }
        temp_file = self.state_file.with_name(f"{self.state_file.name}.{uuid4().hex}.tmp")
        temp_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_file.replace(self.state_file)

    def load(self) -> None:
        if not self.state_file.exists():
            return
        payload = json.loads(self.state_file.read_text(encoding="utf-8"))
        self.projects = _load_bucket(payload.get("projects", {}), Project)
        self.companies = _load_bucket(payload.get("companies", {}), Company)
        self.documents = _load_bucket(payload.get("documents", {}), Document)
        self.tasks = _load_bucket(payload.get("tasks", {}), Task)
        self.risks = _load_bucket(payload.get("risks", {}), RiskItem)
        self.tech_requirements = _load_bucket(payload.get("tech_requirements", {}), TechRequirement)
        self.deviations = _load_bucket(payload.get("deviations", {}), DeviationResult)
        self.exports = _load_bucket(payload.get("exports", {}), ExportRecord)
        self.materials = _load_bucket(payload.get("materials", {}), Material)
        self.feedback = _load_bucket(payload.get("feedback", {}), ReviewFeedback)
        self.activity_logs = _load_bucket(payload.get("activity_logs", {}), ActivityLog)


def _dump_bucket(bucket: dict[str, object]) -> dict[str, object]:
    return {key: value.model_dump(mode="json") for key, value in bucket.items()}


def _load_bucket(payload: dict[str, object], model):
    return {key: model.model_validate(value) for key, value in payload.items()}


store = InMemoryStore()
