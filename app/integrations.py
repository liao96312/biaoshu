from __future__ import annotations

import importlib.util

from app.config import settings


def integration_status() -> dict[str, dict[str, object]]:
    return {
        "postgres": {
            "configured": bool(settings.database_url),
            "package": _has_package("psycopg"),
        },
        "redis": {
            "configured": bool(settings.redis_url),
            "package": _has_package("redis"),
        },
        "celery": {
            "configured": settings.task_queue == "celery",
            "package": _has_package("celery"),
        },
        "qdrant": {
            "configured": bool(settings.qdrant_url),
            "package": _has_package("qdrant_client"),
        },
        "minio": {
            "configured": bool(settings.minio_endpoint),
            "package": _has_package("minio"),
        },
        "langgraph": {
            "configured": settings.workflow_engine == "langgraph",
            "engine": settings.workflow_engine,
            "package": _has_package("langgraph"),
        },
        "docx": {
            "configured": True,
            "package": _has_package("docx"),
        },
        "ocr": {
            "configured": settings.ocr_provider != "disabled",
            "provider": settings.ocr_provider,
            "package": _has_package("paddleocr"),
        },
        "llm": {
            "configured": settings.llm_provider != "disabled",
            "provider": settings.llm_provider,
            "model": settings.llm_model,
        },
        "object_storage": {
            "configured": settings.object_storage_backend != "local",
            "provider": settings.object_storage_backend,
            "package": _has_package("minio"),
        },
        "vector_store": {
            "configured": settings.vector_backend != "memory",
            "provider": settings.vector_backend,
            "package": _has_package("qdrant_client"),
        },
        "embedding": {
            "configured": settings.embedding_provider != "hash",
            "provider": settings.embedding_provider,
            "model": settings.embedding_model,
        },
    }


def _has_package(name: str) -> bool:
    return importlib.util.find_spec(name) is not None
