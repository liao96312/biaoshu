from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ApiResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: Any = Field(default_factory=dict)
    request_id: str
    timestamp: int


class ProjectStatus(str, Enum):
    CREATED = "created"
    PARSING = "parsing"
    REVIEW_PENDING = "review_pending"
    COMPLETED = "completed"


class Severity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ReviewStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    DISMISSED = "dismissed"
    MODIFIED = "modified"
    APPROVED = "approved"


class DeviationType(str, Enum):
    POSITIVE = "positive"
    NONE = "none"
    NEGATIVE = "negative"
    UNKNOWN = "unknown"


class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class ProjectCreate(BaseModel):
    name: str
    tender_name: str
    company_id: str


class CompanyCreate(BaseModel):
    name: str


class Company(BaseModel):
    id: str
    name: str
    created_at: datetime = Field(default_factory=utc_now)


class Project(BaseModel):
    id: str
    name: str
    tender_name: str
    company_id: str
    status: ProjectStatus = ProjectStatus.CREATED
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Document(BaseModel):
    id: str
    project_id: str
    file_name: str
    file_type: str
    storage_path: str
    object_storage_uri: str | None = None
    parsed_text: str = ""
    page_count: int = 0
    parse_status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = Field(default_factory=utc_now)


class TaskStep(BaseModel):
    name: str
    status: TaskStatus


class Task(BaseModel):
    id: str
    project_id: str | None = None
    task_type: str
    status: TaskStatus = TaskStatus.PENDING
    progress: int = 0
    current_step: str = ""
    steps: list[TaskStep] = Field(default_factory=list)
    result: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class RiskItem(BaseModel):
    id: str
    project_id: str
    risk_type: str
    requirement: str
    trigger_keyword: str
    severity: Severity
    need_material: bool = True
    source_page: int | None = None
    source_section: str | None = None
    source_text: str
    ai_reason: str
    suggestion: str
    confidence: float
    status: ReviewStatus = ReviewStatus.PENDING
    reviewer_note: str | None = None
    material_ids: list[str] = Field(default_factory=list)


class TechRequirement(BaseModel):
    id: str
    project_id: str
    item_name: str
    parameter_name: str
    operator: str
    required_value: float
    unit: str
    is_mandatory: bool = False
    source_page: int | None = None
    source_text: str


class DeviationResult(BaseModel):
    id: str
    project_id: str
    tech_requirement_id: str
    item: str
    parameter: str
    required_value: str
    our_value: str | None = None
    deviation_type: DeviationType = DeviationType.UNKNOWN
    response_text: str = "待补充我方响应"
    evidence: str | None = None
    source_page: int | None = None
    confidence: float = 0.7
    reviewer_status: ReviewStatus = ReviewStatus.PENDING


class RiskUpdate(BaseModel):
    status: ReviewStatus
    reviewer_note: str | None = None
    material_ids: list[str] = Field(default_factory=list)


class RiskBatchConfirm(BaseModel):
    risk_ids: list[str]
    status: ReviewStatus


class DeviationBatchConfirm(BaseModel):
    deviation_ids: list[str]
    reviewer_status: ReviewStatus


class DeviationUpdate(BaseModel):
    our_value: str | None = None
    deviation_type: DeviationType | None = None
    response_text: str | None = None
    evidence: str | None = None
    reviewer_status: ReviewStatus | None = None


class ProductRematchRequest(BaseModel):
    product_ids: list[str] = Field(default_factory=list)


class MaterialAutoBindRequest(BaseModel):
    limit_per_risk: int = 3
    min_score: float = 0.1


class ExportCreate(BaseModel):
    export_type: str = "deviation_table"
    format: str = "xlsx"
    options: dict[str, Any] = Field(default_factory=dict)


class ExportRecord(BaseModel):
    id: str
    project_id: str
    export_type: str
    format: str
    file_path: str
    task_id: str
    status: TaskStatus = TaskStatus.DONE
    created_at: datetime = Field(default_factory=utc_now)


class Material(BaseModel):
    id: str
    company_id: str
    file_name: str
    material_type: str
    storage_path: str
    object_storage_uri: str | None = None
    parsed_text: str = ""
    page_count: int = 0
    name: str | None = None
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class ReviewFeedbackCreate(BaseModel):
    target_type: str
    target_id: str
    action: str
    before: dict[str, Any] = Field(default_factory=dict)
    after: dict[str, Any] = Field(default_factory=dict)
    reviewer_note: str | None = None


class ReviewFeedback(BaseModel):
    id: str
    project_id: str
    target_type: str
    target_id: str
    action: str
    before: dict[str, Any] = Field(default_factory=dict)
    after: dict[str, Any] = Field(default_factory=dict)
    reviewer_note: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class ActivityLog(BaseModel):
    id: str
    actor: str
    method: str
    path: str
    status_code: int
    project_id: str | None = None
    action: str
    detail: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
