from __future__ import annotations

import time

from app.agents.workflow import BidRiskWorkflow
from app.models import Material, ProjectStatus, Task, TaskStatus, utc_now
from app.realtime import task_connections
from app.repositories.runtime import repository
from app.services.product_matcher import match_products
from app.store import store


async def process_document_task(document_id: str, task_id: str) -> None:
    store.load()
    document = repository.get_document(document_id)
    task = repository.get_task(task_id)
    if document is None or task is None:
        return
    project = repository.get_project(document.project_id)
    if project is None:
        return
    workflow = BidRiskWorkflow()
    try:
        await _advance(task, "file_extract", 10)
        parsed = workflow.document_parser.run(document.storage_path)
        document.parsed_text = parsed.text
        document.page_count = parsed.page_count
        document.parse_status = TaskStatus.PROCESSING

        await _advance(task, "section_classification", 25)
        parsed = workflow.section_classifier.run(parsed)
        await _advance(task, "clause_extraction", 40)
        parsed = workflow.clause_extractor.run(parsed)
        await _advance(task, "risk_scan", 60)
        risks = workflow.risk_scanner.run(parsed.text, document.project_id)
        replace_project_risks(document.project_id, risks)

        await _advance(task, "tech_param_extract", 78)
        requirements = workflow.tech_param_extractor.run(parsed.text, document.project_id)
        replace_project_requirements(document.project_id, requirements)

        await _advance(task, "product_match", 90)
        materials = project_product_materials(document.project_id)
        deviations = workflow.product_matcher.run(requirements, materials)
        deviations = workflow.deviation_judge.run(deviations)
        replace_project_deviations(document.project_id, requirements, deviations)

        document.parse_status = TaskStatus.DONE
        project.status = ProjectStatus.REVIEW_PENDING
        task.status = TaskStatus.DONE
        task.progress = 100
        task.current_step = "completed"
        task.result = repository.project_counts(document.project_id)
        task.updated_at = utc_now()
        repository.touch_project(document.project_id)
        repository.upsert_task(task)
        await send_task_event(task, "task_completed", {"result": task.result})
    except Exception as exc:
        document.parse_status = TaskStatus.FAILED
        task.status = TaskStatus.FAILED
        task.error_message = str(exc)
        task.updated_at = utc_now()
        repository.upsert_task(task)
        await send_task_event(task, "task_failed", {"error_code": 3001, "message": str(exc)})


async def _advance(task: Task, step_name: str, progress: int) -> None:
    task.status = TaskStatus.PROCESSING
    task.progress = progress
    task.current_step = step_name
    task.updated_at = utc_now()
    for step in task.steps:
        if step.name == step_name:
            step.status = TaskStatus.PROCESSING
        elif step.status == TaskStatus.PROCESSING:
            step.status = TaskStatus.DONE
    await send_task_event(task, "task_progress", {"message": f"processing {step_name}"})


async def send_task_event(task: Task, event_name: str, extra: dict | None = None) -> None:
    payload = {
        "event": event_name,
        "task_id": task.id,
        "progress": task.progress,
        "current_step": task.current_step,
        "timestamp": int(time.time()),
    }
    if extra:
        payload.update(extra)
    await task_connections.broadcast(task.id, payload)


def replace_project_risks(project_id: str, risks) -> None:
    repository.clear_project_risks(project_id)
    for risk in risks:
        risk.id = repository.new_id("risk")
        repository.upsert_risk(risk)


def replace_project_requirements(project_id: str, requirements) -> None:
    repository.clear_project_requirements_and_deviations(project_id)
    for requirement in requirements:
        requirement.id = repository.new_id("param")
        repository.upsert_tech_requirement(requirement)


def rematch_project_products(project_id: str, product_ids: list[str] | None = None) -> int:
    requirements = repository.list_project_requirements(project_id)
    materials = project_product_materials(project_id, product_ids)
    results = match_products(requirements, materials)
    replace_project_deviations(project_id, requirements, results)
    return len(results)


def project_product_materials(project_id: str, product_ids: list[str] | None = None) -> list[Material]:
    return repository.list_project_materials(project_id, product_ids)


def replace_project_deviations(project_id: str, requirements, deviations) -> None:
    repository.clear_project_deviations(project_id)
    for requirement, deviation in zip(requirements, deviations, strict=False):
        deviation.id = requirement.id
        deviation.tech_requirement_id = requirement.id
        repository.upsert_deviation(deviation)
