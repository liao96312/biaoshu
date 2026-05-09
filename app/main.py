from __future__ import annotations

import hashlib
import re
import shutil
import time
from pathlib import Path
from zipfile import ZipFile

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.adapters.object_storage import object_storage
from app.integrations import integration_status
from app.jobs import rematch_project_products
from app.knowledge_base import knowledge_base
from app.models import (
    ActivityLog,
    ApiResponse,
    DeviationBatchConfirm,
    DeviationUpdate,
    Document,
    ExportCreate,
    ExportRecord,
    Company,
    CompanyCreate,
    Material,
    MaterialAutoBindRequest,
    ProductRematchRequest,
    Project,
    ProjectCreate,
    ProjectStatus,
    ReviewFeedback,
    ReviewFeedbackCreate,
    RiskBatchConfirm,
    RiskUpdate,
    Task,
    TaskStatus,
    TaskStep,
    utc_now,
)
from app.rate_limit import rate_limiter
from app.realtime import task_connections
from app.repositories.runtime import repository
from app.services.deviation import build_deviation
from app.services.bid_outline import build_bid_outline
from app.services.bid_outline_report import export_bid_outline_docx
from app.services.checklists import build_material_gap_list, build_scoring_matrix
from app.services.clauses import extract_clauses
from app.services.exporter import export_deviation_table, export_material_gap_list, export_scoring_matrix
from app.services.material_recommender import recommend_materials_for_risk, recommend_materials_for_risks
from app.services.parser import parse_document
from app.services.pdf_report import export_bid_outline_pdf, export_risk_report_pdf
from app.services.risk_report import export_risk_report_docx
from app.services.rules import read_risk_rules, write_risk_rules
from app.services.review_gate import review_blockers, review_summary
from app.task_queue import task_queue


app = FastAPI(title="Bid Risk Control Agent", version="0.2.0")
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/app", StaticFiles(directory=static_dir, html=True), name="web")


@app.on_event("startup")
def index_existing_materials() -> None:
    for material in repository.list_all_materials():
        knowledge_base.index_material(material)


@app.get("/")
def index() -> RedirectResponse:
    return RedirectResponse("/app/")


@app.get("/healthz")
def healthz() -> dict:
    return {
        "status": "ok",
        "storage_root": str(repository.storage_root),
        "state_file": str(repository.state_file),
    }


@app.get("/api/v1/system/capabilities")
def system_capabilities() -> ApiResponse:
    return ok(
        {
            "document_types": ["pdf", "docx", "xlsx", "xlsm", "txt", "md"],
            "export_types": {
                "deviation_table": ["xlsx"],
                "risk_report": ["docx", "pdf"],
                "scoring_matrix": ["xlsx"],
                "material_gap_list": ["xlsx"],
                "bid_outline": ["docx", "pdf"],
                "submission_package": ["zip"],
            },
            "authentication": {
                "bearer_token_enabled": bool(settings.token),
                "api_key_enabled": bool(settings.api_keys),
            },
            "storage": repository.name,
            "task_queue": task_queue.name,
            "llm_provider": settings.llm_provider,
            "ocr_provider": settings.ocr_provider,
            "object_storage": settings.object_storage_backend,
            "vector_backend": settings.vector_backend,
            "embedding_provider": settings.embedding_provider,
            "workflow_engine": settings.workflow_engine,
            "adapters": {
                "database_url_configured": bool(settings.database_url),
                "redis_url_configured": bool(settings.redis_url),
                "qdrant_url_configured": bool(settings.qdrant_url),
                "minio_endpoint_configured": bool(settings.minio_endpoint),
                "embedding_api_key_configured": bool(settings.embedding_api_key or settings.llm_api_key),
            },
        }
    )


@app.get("/api/v1/system/metrics")
def system_metrics() -> ApiResponse:
    return ok(repository.metrics())


@app.get("/api/v1/system/integrations")
def system_integrations() -> ApiResponse:
    return ok(integration_status())


@app.get("/api/v1/system/activity")
def system_activity(project_id: str | None = None, limit: int = 100) -> ApiResponse:
    logs = repository.list_activity_logs(project_id=project_id, limit=min(max(limit, 1), 500))
    return ok({"total": len(logs), "items": [item.model_dump() for item in logs]})


@app.get("/api/v1/rules/risk")
def get_risk_rules() -> ApiResponse:
    return ok(read_risk_rules())


@app.put("/api/v1/rules/risk")
def update_risk_rules(payload: dict) -> ApiResponse:
    return ok(write_risk_rules(payload))


def ok(data=None, message: str = "success") -> ApiResponse:
    return ApiResponse(
        code=0,
        message=message,
        data=data or {},
        request_id=repository.new_id("req"),
        timestamp=int(time.time()),
    )


def error_response(code: int, message: str, status_code: int = 400, data=None) -> JSONResponse:
    payload = ok(data or {}, message=message)
    payload.code = code
    return JSONResponse(status_code=status_code, content=payload.model_dump(mode="json"))


@app.middleware("http")
async def auth_and_rate_headers(request: Request, call_next):
    rate_key = request.headers.get("x-api-key") or (request.client.host if request.client else "anonymous")
    rate = rate_limiter.check(rate_key)
    if not rate.allowed and request.url.path.startswith("/api/"):
        response = error_response(4003, "rate limit exceeded", 429)
        response.headers["X-RateLimit-Limit"] = str(rate.limit)
        response.headers["X-RateLimit-Remaining"] = str(rate.remaining)
        response.headers["X-RateLimit-Reset"] = str(rate.reset)
        _record_activity(request, response.status_code)
        return response
    if request.url.path.startswith("/api/"):
        token = settings.token
        api_keys = set(settings.api_keys)
        if token or api_keys:
            authorization = request.headers.get("authorization", "")
            api_key = request.headers.get("x-api-key", "")
            bearer_ok = token and authorization == f"Bearer {token}"
            api_key_ok = api_key and api_key in api_keys
            if not bearer_ok and not api_key_ok:
                response = error_response(4001, "unauthorized", 401)
                _record_activity(request, response.status_code)
                return response
    response = await call_next(request)
    response.headers["X-RateLimit-Limit"] = str(rate.limit)
    response.headers["X-RateLimit-Remaining"] = str(rate.remaining)
    response.headers["X-RateLimit-Reset"] = str(rate.reset)
    _record_activity(request, response.status_code)
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    code = 1001
    if exc.status_code == 401:
        code = 4001
    elif exc.status_code == 403:
        code = 4003
    elif exc.status_code == 404:
        code = 2001
    elif exc.status_code >= 500:
        code = 3001
    if isinstance(exc.detail, dict):
        message = str(exc.detail.get("message", "request failed"))
        data = {key: value for key, value in exc.detail.items() if key != "message"}
        return error_response(code, message, exc.status_code, data=data)
    return error_response(code, str(exc.detail), exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return error_response(1001, "invalid request parameters", 422)


def get_project_or_404(project_id: str) -> Project:
    project = repository.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    return project


def get_company_or_404(company_id: str) -> Company:
    company = repository.get_company(company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="company not found")
    return company


@app.post("/api/v1/companies")
def create_company(payload: CompanyCreate) -> ApiResponse:
    company = Company(id=repository.new_id("comp"), name=payload.name)
    repository.create_company(company)
    return ok(company.model_dump())


@app.get("/api/v1/companies")
def list_companies(page: int = 1, page_size: int = 20) -> ApiResponse:
    company_page = repository.list_companies(page=page, page_size=page_size)
    return ok({"total": company_page.total, "items": [item.model_dump() for item in company_page.items]})


@app.get("/api/v1/companies/{company_id}")
def get_company(company_id: str) -> ApiResponse:
    return ok(get_company_or_404(company_id).model_dump())


@app.post("/api/v1/projects")
def create_project(payload: ProjectCreate) -> ApiResponse:
    project = Project(id=repository.new_id("proj"), **payload.model_dump())
    repository.create_project(project)
    return ok({"project_id": project.id, "status": project.status, "created_at": project.created_at})


@app.get("/api/v1/projects")
def list_projects(page: int = 1, page_size: int = 20, status: ProjectStatus | None = None) -> ApiResponse:
    project_page = repository.list_projects(page=page, page_size=page_size, status=status.value if status else None)
    data = []
    for project in project_page.items:
        row = project.model_dump()
        row.update(repository.project_counts(project.id))
        data.append(row)
    return ok({"total": project_page.total, "items": data})


@app.get("/api/v1/projects/{project_id}")
def get_project(project_id: str) -> ApiResponse:
    project = get_project_or_404(project_id)
    data = project.model_dump()
    data.update(repository.project_counts(project_id))
    return ok(data)


@app.delete("/api/v1/projects/{project_id}")
def delete_project(project_id: str, delete_files: bool = True) -> ApiResponse:
    get_project_or_404(project_id)
    document_paths = [Path(item.storage_path) for item in repository.list_project_documents(project_id)]
    export_paths = [Path(item.file_path) for item in repository.list_project_exports(project_id)]
    repository.delete_project(project_id)
    removed_files = 0
    if delete_files:
        for path in [*document_paths, *export_paths]:
            removed_files += _delete_file_if_safe(path)
        removed_files += _delete_tree_if_safe(repository.storage_root / "projects" / project_id)
        removed_files += object_storage.delete_prefix(f"projects/{project_id}/")
    return ok({"deleted": project_id, "removed_files": removed_files})


@app.post("/api/v1/projects/{project_id}/complete")
def complete_project(project_id: str) -> ApiResponse:
    project = get_project_or_404(project_id)
    blockers = review_blockers(
        repository.list_project_risks(project_id),
        repository.list_project_deviations(project_id),
    )
    if blockers:
        raise HTTPException(status_code=409, detail={"message": "review blockers exist", "items": blockers})
    project.status = ProjectStatus.COMPLETED
    repository.create_project(project)
    return ok({"project_id": project.id, "status": project.status})


@app.post("/api/v1/projects/{project_id}/feedback")
def create_feedback(project_id: str, payload: ReviewFeedbackCreate) -> ApiResponse:
    get_project_or_404(project_id)
    feedback = ReviewFeedback(
        id=repository.new_id("fb"),
        project_id=project_id,
        **payload.model_dump(),
    )
    repository.upsert_feedback(feedback)
    return ok(feedback.model_dump())


@app.get("/api/v1/projects/{project_id}/feedback")
def list_feedback(project_id: str) -> ApiResponse:
    get_project_or_404(project_id)
    items = repository.list_feedback(project_id)
    return ok({"total": len(items), "items": [item.model_dump() for item in items]})


@app.post("/api/v1/projects/{project_id}/documents")
async def upload_document(
    project_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    doc_type: str = Form("tender"),
) -> ApiResponse:
    project = get_project_or_404(project_id)
    document_id = repository.new_id("doc")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".pdf", ".docx", ".xlsx", ".xlsm", ".txt", ".md", ".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}:
        raise HTTPException(status_code=400, detail="unsupported file type")

    project_dir = repository.storage_root / "projects" / project_id
    project_dir.mkdir(parents=True, exist_ok=True)
    target = project_dir / f"{document_id}{suffix}"
    with target.open("wb") as output:
        shutil.copyfileobj(file.file, output)
    storage_path = object_storage.put_file(target, f"projects/{project_id}/{target.name}")

    task_id = repository.new_id("task_parse")
    task = _new_parse_task(task_id, project_id)
    repository.upsert_task(task)
    repository.upsert_document(Document(
        id=document_id,
        project_id=project_id,
        file_name=file.filename or target.name,
        file_type=doc_type,
        storage_path=str(target),
        object_storage_uri=storage_path,
        parse_status=TaskStatus.PENDING,
    ))
    project.status = ProjectStatus.PARSING
    repository.touch_project(project_id)
    task_queue.enqueue_document_parse(background_tasks, document_id, task_id)

    return ok(
        {
            "document_id": document_id,
            "file_name": file.filename,
            "file_size": target.stat().st_size,
            "page_count": 0,
            "parse_task_id": task_id,
            "status": "parsing",
        }
    )


@app.post("/api/v1/projects/{project_id}/documents/{document_id}/reparse")
def reparse_document(project_id: str, document_id: str, background_tasks: BackgroundTasks) -> ApiResponse:
    project = get_project_or_404(project_id)
    document = repository.get_document(document_id)
    if document is None or document.project_id != project_id or not Path(document.storage_path).exists():
        raise HTTPException(status_code=404, detail="document not found")
    task_id = repository.new_id("task_parse")
    task = _new_parse_task(task_id, project_id)
    document.parse_status = TaskStatus.PENDING
    repository.upsert_document(document)
    repository.upsert_task(task)
    project.status = ProjectStatus.PARSING
    repository.create_project(project)
    task_queue.enqueue_document_parse(background_tasks, document_id, task_id)
    return ok({"document_id": document_id, "parse_task_id": task_id, "status": "parsing"})


@app.get("/api/v1/projects/{project_id}/documents")
def list_documents(project_id: str) -> ApiResponse:
    get_project_or_404(project_id)
    documents = repository.list_project_documents(project_id)
    return ok({"total": len(documents), "items": [item.model_dump() for item in documents]})


@app.get("/api/v1/projects/{project_id}/documents/{document_id}/download")
def download_document(project_id: str, document_id: str) -> FileResponse:
    get_project_or_404(project_id)
    document = repository.get_document(document_id)
    if document is None or document.project_id != project_id or not Path(document.storage_path).exists():
        raise HTTPException(status_code=404, detail="document not found")
    return FileResponse(document.storage_path, filename=document.file_name)

@app.get("/api/v1/tasks/{task_id}")
def get_task(task_id: str) -> ApiResponse:
    task = repository.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    return ok(task.model_dump())


@app.get("/api/v1/projects/{project_id}/tasks")
def list_project_tasks(project_id: str) -> ApiResponse:
    get_project_or_404(project_id)
    tasks = repository.list_project_tasks(project_id)
    return ok({"total": len(tasks), "items": [item.model_dump() for item in tasks]})


@app.websocket("/ws/tasks/{task_id}")
async def task_websocket(task_id: str, websocket: WebSocket) -> None:
    token = settings.token
    if token and websocket.query_params.get("token") != token:
        await websocket.close(code=1008)
        return
    await task_connections.connect(task_id, websocket)
    try:
        task = repository.get_task(task_id)
        if task:
            await websocket.send_json(
                {
                    "event": "task_progress",
                    "task_id": task.id,
                    "progress": task.progress,
                    "current_step": task.current_step,
                    "timestamp": int(time.time()),
                }
            )
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        task_connections.disconnect(task_id, websocket)


@app.get("/api/v1/projects/{project_id}/risks")
def list_risks(
    project_id: str,
    severity: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> ApiResponse:
    get_project_or_404(project_id)
    risk_page = repository.list_risks(project_id, severity=severity, status=status, page=page, page_size=page_size)
    return ok({"total": risk_page.total, "items": [item.model_dump() for item in risk_page.items]})


@app.get("/api/v1/projects/{project_id}/clauses")
def list_project_clauses(project_id: str, clause_type: str | None = None) -> ApiResponse:
    get_project_or_404(project_id)
    items: list[dict] = []
    for document in repository.list_project_documents(project_id):
        if not document.parsed_text:
            continue
        for clause in extract_clauses(document.parsed_text):
            clause["document_id"] = document.id
            clause["file_name"] = document.file_name
            items.append(clause)
    if clause_type:
        items = [item for item in items if item["clause_type"] == clause_type]
    return ok({"total": len(items), "items": items})


@app.patch("/api/v1/projects/{project_id}/risks/{risk_id}")
def update_risk(project_id: str, risk_id: str, payload: RiskUpdate) -> ApiResponse:
    get_project_or_404(project_id)
    risk = repository.get_risk(risk_id)
    if risk is None or risk.project_id != project_id:
        raise HTTPException(status_code=404, detail="risk not found")
    before = risk.model_dump(mode="json")
    risk.status = payload.status
    risk.reviewer_note = payload.reviewer_note
    risk.material_ids = payload.material_ids
    repository.upsert_risk(risk)
    _record_feedback(project_id, "risk", risk.id, payload.status.value, before, risk.model_dump(mode="json"), payload.reviewer_note)
    repository.touch_project(project_id)
    return ok(risk.model_dump())


@app.post("/api/v1/projects/{project_id}/risks/batch-confirm")
def batch_confirm_risks(project_id: str, payload: RiskBatchConfirm) -> ApiResponse:
    get_project_or_404(project_id)
    updated = 0
    for risk_id in payload.risk_ids:
        risk = repository.get_risk(risk_id)
        if risk and risk.project_id == project_id:
            before = risk.model_dump(mode="json")
            risk.status = payload.status
            repository.upsert_risk(risk)
            _record_feedback(project_id, "risk", risk.id, payload.status.value, before, risk.model_dump(mode="json"), None)
            updated += 1
    repository.touch_project(project_id)
    return ok({"updated": updated})


@app.get("/api/v1/projects/{project_id}/risks/{risk_id}/material-recommendations")
def get_risk_material_recommendations(project_id: str, risk_id: str, limit: int = 5) -> ApiResponse:
    project = get_project_or_404(project_id)
    risk = repository.get_risk(risk_id)
    if risk is None or risk.project_id != project_id:
        raise HTTPException(status_code=404, detail="risk not found")
    items = recommend_materials_for_risk(knowledge_base, project.company_id, risk, limit=min(max(limit, 1), 20))
    return ok({"total": len(items), "items": items})


@app.get("/api/v1/projects/{project_id}/deviations")
def list_deviations(
    project_id: str,
    deviation_type: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> ApiResponse:
    get_project_or_404(project_id)
    deviation_page = repository.list_deviations(project_id, deviation_type=deviation_type, page=page, page_size=page_size)
    summary = {"positive": 0, "none": 0, "negative": 0, "unknown": 0}
    for item in repository.list_project_deviations(project_id):
        summary[item.deviation_type.value] += 1
    return ok({"total": deviation_page.total, "summary": summary, "items": [item.model_dump() for item in deviation_page.items]})


@app.patch("/api/v1/projects/{project_id}/deviations/{param_id}")
def update_deviation(project_id: str, param_id: str, payload: DeviationUpdate) -> ApiResponse:
    get_project_or_404(project_id)
    deviation = repository.get_deviation(param_id)
    if deviation is None or deviation.project_id != project_id:
        raise HTTPException(status_code=404, detail="deviation not found")
    before = deviation.model_dump(mode="json")
    patch = payload.model_dump(exclude_unset=True)
    for field, value in patch.items():
        setattr(deviation, field, value)
    if "our_value" in patch and "deviation_type" not in patch:
        requirement = repository.get_tech_requirement(deviation.tech_requirement_id)
        if requirement:
            refreshed = build_deviation(requirement, deviation.our_value)
            deviation.deviation_type = refreshed.deviation_type
            deviation.confidence = refreshed.confidence
            if "response_text" not in patch:
                deviation.response_text = refreshed.response_text
    repository.upsert_deviation(deviation)
    action = deviation.reviewer_status.value if hasattr(deviation.reviewer_status, "value") else "modified"
    _record_feedback(project_id, "deviation", deviation.id, action, before, deviation.model_dump(mode="json"), None)
    repository.touch_project(project_id)
    return ok(deviation.model_dump())


@app.post("/api/v1/projects/{project_id}/deviations/batch-confirm")
def batch_confirm_deviations(project_id: str, payload: DeviationBatchConfirm) -> ApiResponse:
    get_project_or_404(project_id)
    updated = 0
    for deviation_id in payload.deviation_ids:
        deviation = repository.get_deviation(deviation_id)
        if deviation and deviation.project_id == project_id:
            before = deviation.model_dump(mode="json")
            deviation.reviewer_status = payload.reviewer_status
            repository.upsert_deviation(deviation)
            _record_feedback(
                project_id,
                "deviation",
                deviation.id,
                payload.reviewer_status.value,
                before,
                deviation.model_dump(mode="json"),
                None,
            )
            updated += 1
    repository.touch_project(project_id)
    return ok({"updated": updated})


@app.post("/api/v1/projects/{project_id}/deviations/rematch")
def rematch_deviations(project_id: str, payload: ProductRematchRequest) -> ApiResponse:
    get_project_or_404(project_id)
    updated = rematch_project_products(project_id, payload.product_ids)
    repository.touch_project(project_id)
    return ok({"updated": updated, "summary": repository.project_counts(project_id)["deviation_count"]})


@app.get("/api/v1/projects/{project_id}/material-gaps")
def list_material_gaps(project_id: str) -> ApiResponse:
    project = get_project_or_404(project_id)
    risks = repository.list_project_risks(project_id)
    items = build_material_gap_list(risks, repository.list_company_materials(project.company_id))
    return ok({"total": len(items), "items": items})


@app.get("/api/v1/projects/{project_id}/material-recommendations")
def get_project_material_recommendations(project_id: str, limit_per_risk: int = 5) -> ApiResponse:
    project = get_project_or_404(project_id)
    items = recommend_materials_for_risks(
        knowledge_base,
        project.company_id,
        repository.list_project_risks(project_id),
        limit_per_risk=min(max(limit_per_risk, 1), 20),
    )
    return ok({"total": len(items), "items": items})


@app.post("/api/v1/projects/{project_id}/material-recommendations/auto-bind")
def auto_bind_material_recommendations(project_id: str, payload: MaterialAutoBindRequest) -> ApiResponse:
    project = get_project_or_404(project_id)
    updated = 0
    bound = 0
    risks = repository.list_project_risks(project_id)
    for row in recommend_materials_for_risks(
        knowledge_base,
        project.company_id,
        risks,
        limit_per_risk=min(max(payload.limit_per_risk, 1), 20),
    ):
        risk = repository.get_risk(row["risk_id"])
        if risk is None:
            continue
        before = risk.model_dump(mode="json")
        material_ids = list(risk.material_ids)
        for recommendation in row["recommendations"]:
            if recommendation["score"] < payload.min_score:
                continue
            material_id = recommendation["material_id"]
            if material_id not in material_ids:
                material_ids.append(material_id)
                bound += 1
        if material_ids != risk.material_ids:
            risk.material_ids = material_ids
            repository.upsert_risk(risk)
            _record_feedback(
                project_id,
                "risk",
                risk.id,
                "material_bound",
                before,
                risk.model_dump(mode="json"),
                None,
            )
            updated += 1
    repository.touch_project(project_id)
    return ok({"updated_risks": updated, "bound_materials": bound})


@app.get("/api/v1/projects/{project_id}/scoring-matrix")
def get_scoring_matrix(project_id: str) -> ApiResponse:
    project = get_project_or_404(project_id)
    deviations = repository.list_project_deviations(project_id)
    risks = repository.list_project_risks(project_id)
    items = build_scoring_matrix(deviations, risks, repository.list_company_materials(project.company_id))
    return ok({"total": len(items), "items": items})


@app.get("/api/v1/projects/{project_id}/bid-outline")
def get_bid_outline(project_id: str) -> ApiResponse:
    project = get_project_or_404(project_id)
    outline = build_bid_outline(
        repository.list_project_risks(project_id),
        repository.list_project_deviations(project_id),
        repository.list_company_materials(project.company_id),
    )
    return ok({"total": len(outline), "items": outline})


@app.get("/api/v1/projects/{project_id}/review-summary")
def get_review_summary(project_id: str) -> ApiResponse:
    get_project_or_404(project_id)
    return ok(
        review_summary(
            repository.list_project_risks(project_id),
            repository.list_project_deviations(project_id),
        )
    )


@app.post("/api/v1/projects/{project_id}/exports")
def create_export(project_id: str, payload: ExportCreate) -> ApiResponse:
    project = get_project_or_404(project_id)
    export_id = repository.new_id("exp")
    task_id = repository.new_id("task_export")
    export_dir = repository.storage_root / "exports"
    deviations = repository.list_project_deviations(project_id)
    risks = repository.list_project_risks(project_id)
    materials = repository.list_company_materials(project.company_id)

    if payload.export_type == "deviation_table" and payload.format == "xlsx":
        path = export_dir / f"{export_id}.xlsx"
        export_deviation_table(
            path,
            deviations,
            risks=risks,
            include_confidence=bool(payload.options.get("include_confidence", False)),
        )
    elif payload.export_type == "risk_report" and payload.format == "docx":
        path = export_dir / f"{export_id}.docx"
        export_risk_report_docx(path, project, risks)
    elif payload.export_type == "risk_report" and payload.format == "pdf":
        path = export_dir / f"{export_id}.pdf"
        export_risk_report_pdf(path, project, risks)
    elif payload.export_type == "scoring_matrix" and payload.format == "xlsx":
        path = export_dir / f"{export_id}.xlsx"
        export_scoring_matrix(path, build_scoring_matrix(deviations, risks, materials))
    elif payload.export_type == "material_gap_list" and payload.format == "xlsx":
        path = export_dir / f"{export_id}.xlsx"
        export_material_gap_list(path, build_material_gap_list(risks, materials))
    elif payload.export_type == "bid_outline" and payload.format == "docx":
        path = export_dir / f"{export_id}.docx"
        export_bid_outline_docx(
            path,
            project,
            build_bid_outline(risks, deviations, repository.list_company_materials(project.company_id)),
        )
    elif payload.export_type == "bid_outline" and payload.format == "pdf":
        path = export_dir / f"{export_id}.pdf"
        export_bid_outline_pdf(
            path,
            project,
            build_bid_outline(risks, deviations, repository.list_company_materials(project.company_id)),
        )
    elif payload.export_type == "submission_package" and payload.format == "zip":
        path = export_dir / f"{export_id}.zip"
        part_dir = export_dir / f"{export_id}_parts"
        part_dir.mkdir(parents=True, exist_ok=True)
        deviation_path = export_deviation_table(part_dir / "01_deviation_table.xlsx", deviations, risks=risks, include_confidence=True)
        risk_path = export_risk_report_docx(part_dir / "02_risk_report.docx", project, risks)
        gap_path = export_material_gap_list(part_dir / "03_material_gap_list.xlsx", build_material_gap_list(risks, materials))
        scoring_path = export_scoring_matrix(part_dir / "04_scoring_matrix.xlsx", build_scoring_matrix(deviations, risks, materials))
        outline_path = export_bid_outline_docx(
            part_dir / "05_bid_outline.docx",
            project,
            build_bid_outline(risks, deviations, repository.list_company_materials(project.company_id)),
        )
        with ZipFile(path, "w") as archive:
            for item in [deviation_path, risk_path, gap_path, scoring_path, outline_path]:
                archive.write(item, arcname=f"exports/{item.name}")
            for document in repository.list_project_documents(project_id):
                document_path = Path(document.storage_path)
                if document_path.exists():
                    archive.write(document_path, arcname=f"source_documents/{document.file_name}")
        _delete_tree_if_safe(part_dir)
    else:
        raise HTTPException(status_code=400, detail="unsupported export type or format")

    task = Task(
        id=task_id,
        project_id=project_id,
        task_type="export",
        status=TaskStatus.DONE,
        progress=100,
        current_step="completed",
        result={"export_id": export_id},
    )
    record = ExportRecord(
        id=export_id,
        project_id=project_id,
        export_type=payload.export_type,
        format=payload.format,
        file_path=str(path),
        task_id=task_id,
    )
    repository.upsert_task(task)
    repository.upsert_export(record)
    return ok({"export_id": export_id, "task_id": task_id, "status": "done"})


@app.get("/api/v1/exports/{export_id}/download")
def download_export(export_id: str) -> FileResponse:
    record = repository.get_export(export_id)
    if record is None or not Path(record.file_path).exists():
        raise HTTPException(status_code=404, detail="export not found")
    if record.format == "xlsx":
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = f"deviation_table_{record.project_id}.xlsx"
    elif record.format == "zip":
        media_type = "application/zip"
        filename = f"submission_package_{record.project_id}.zip"
    elif record.format == "pdf":
        media_type = "application/pdf"
        filename = f"{record.export_type}_{record.project_id}.pdf"
    else:
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        filename = f"{record.export_type}_{record.project_id}.docx"
    return FileResponse(record.file_path, filename=filename, media_type=media_type)


@app.post("/api/v1/companies/{company_id}/materials")
async def upload_material(
    company_id: str,
    file: UploadFile = File(...),
    material_type: str = Form(...),
    name: str | None = Form(None),
    tags: str = Form(""),
) -> ApiResponse:
    material_id = repository.new_id("mat")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".pdf", ".docx", ".xlsx", ".xlsm", ".txt", ".md", ".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}:
        raise HTTPException(status_code=400, detail="unsupported file type")
    target_dir = repository.storage_root / "companies" / company_id
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{material_id}{suffix}"
    with target.open("wb") as output:
        shutil.copyfileobj(file.file, output)
    object_storage_uri = object_storage.put_file(target, f"companies/{company_id}/{target.name}")

    parsed_text = ""
    page_count = 0
    try:
        parsed = parse_document(target)
        parsed_text = parsed.text
        page_count = parsed.page_count
    except Exception:
        parsed_text = ""

    material = Material(
        id=material_id,
        company_id=company_id,
        file_name=file.filename or target.name,
        material_type=material_type,
        storage_path=str(target),
        object_storage_uri=object_storage_uri,
        parsed_text=parsed_text,
        page_count=page_count,
        name=name,
        tags=[tag.strip() for tag in tags.split(",") if tag.strip()],
    )
    repository.upsert_material(material)
    knowledge_base.index_material(material)
    return ok(material.model_dump())


@app.get("/api/v1/companies/{company_id}/materials")
def list_materials(company_id: str, material_type: str | None = None, page: int = 1, page_size: int = 20) -> ApiResponse:
    material_page = repository.list_materials(company_id, material_type=material_type, page=page, page_size=page_size)
    return ok({"total": material_page.total, "items": [item.model_dump() for item in material_page.items]})


@app.get("/api/v1/companies/{company_id}/materials/search")
def search_materials(company_id: str, q: str, limit: int = 5) -> ApiResponse:
    hits = knowledge_base.search(company_id, q, limit=limit)
    return ok(
        {
            "total": len(hits),
            "items": [
                {
                    "material_id": hit.id,
                    "score": hit.score,
                    "text": hit.text[:500],
                    "payload": hit.payload,
                }
                for hit in hits
            ],
        }
    )


@app.delete("/api/v1/companies/{company_id}/materials/{material_id}")
def delete_material(company_id: str, material_id: str, delete_file: bool = True) -> ApiResponse:
    material = repository.get_material(material_id)
    if material is None or material.company_id != company_id:
        raise HTTPException(status_code=404, detail="material not found")
    knowledge_base.delete_material(material)
    repository.delete_material(material_id)
    removed_files = 0
    if delete_file:
        removed_files += _delete_file_if_safe(Path(material.storage_path))
        removed_files += object_storage.delete_file(f"companies/{company_id}/{Path(material.storage_path).name}")
    return ok({"deleted": material_id, "removed_files": removed_files})


@app.get("/api/v1/companies/{company_id}/materials/{material_id}/download")
def download_material(company_id: str, material_id: str) -> FileResponse:
    material = repository.get_material(material_id)
    if material is None or material.company_id != company_id or not Path(material.storage_path).exists():
        raise HTTPException(status_code=404, detail="material not found")
    return FileResponse(material.storage_path, filename=material.file_name)


def _record_activity(request: Request, status_code: int) -> None:
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return
    if not request.url.path.startswith("/api/"):
        return
    try:
        project_id = _project_id_from_path(request.url.path)
        repository.upsert_activity_log(
            ActivityLog(
                id=repository.new_id("act"),
                actor=_request_actor(request),
                method=request.method,
                path=request.url.path,
                status_code=status_code,
                project_id=project_id,
                action=_activity_action(request.method, request.url.path),
                detail={"query": dict(request.query_params)},
            )
        )
    except Exception:
        return


def _request_actor(request: Request) -> str:
    api_key = request.headers.get("x-api-key")
    if api_key:
        digest = hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:10]
        return f"api_key:{digest}"
    if request.headers.get("authorization"):
        return "bearer_token"
    return request.client.host if request.client else "anonymous"


def _project_id_from_path(path: str) -> str | None:
    match = re.search(r"/projects/([^/]+)", path)
    return match.group(1) if match else None


def _activity_action(method: str, path: str) -> str:
    normalized = re.sub(r"/(proj|doc|risk|param|mat|exp|task|fb|act)_[^/]+", r"/\1_{id}", path)
    return f"{method} {normalized}"


def _delete_file_if_safe(path: Path) -> int:
    try:
        resolved = path.resolve()
        if not _is_under_storage(resolved) or not resolved.is_file():
            return 0
        resolved.unlink()
        return 1
    except OSError:
        return 0


def _delete_tree_if_safe(path: Path) -> int:
    try:
        resolved = path.resolve()
        if not _is_under_storage(resolved) or not resolved.is_dir():
            return 0
        count = sum(1 for item in resolved.rglob("*") if item.is_file())
        shutil.rmtree(resolved)
        return count
    except OSError:
        return 0


def _is_under_storage(path: Path) -> bool:
    storage_root = repository.storage_root.resolve()
    return path == storage_root or storage_root in path.parents


def _new_parse_task(task_id: str, project_id: str) -> Task:
    return Task(
        id=task_id,
        project_id=project_id,
        task_type="document_parse",
        status=TaskStatus.PENDING,
        progress=0,
        current_step="queued",
        steps=[
            TaskStep(name="file_extract", status=TaskStatus.PENDING),
            TaskStep(name="section_classification", status=TaskStatus.PENDING),
            TaskStep(name="clause_extraction", status=TaskStatus.PENDING),
            TaskStep(name="risk_scan", status=TaskStatus.PENDING),
            TaskStep(name="tech_param_extract", status=TaskStatus.PENDING),
            TaskStep(name="product_match", status=TaskStatus.PENDING),
        ],
    )


def _record_feedback(
    project_id: str,
    target_type: str,
    target_id: str,
    action: str,
    before: dict,
    after: dict,
    reviewer_note: str | None,
) -> None:
    repository.upsert_feedback(
        ReviewFeedback(
            id=repository.new_id("fb"),
            project_id=project_id,
            target_type=target_type,
            target_id=target_id,
            action=action,
            before=before,
            after=after,
            reviewer_note=reviewer_note,
        )
    )
