from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    storage_root: str = os.getenv("BID_AGENT_STORAGE_ROOT", "storage")
    state_file: str = os.getenv("BID_AGENT_STATE_FILE", "storage/state.json")
    token: str = os.getenv("BID_AGENT_TOKEN", "")
    api_keys: tuple[str, ...] = tuple(
        item.strip() for item in os.getenv("BID_AGENT_API_KEYS", "").split(",") if item.strip()
    )
    database_url: str = os.getenv("DATABASE_URL", "")
    redis_url: str = os.getenv("REDIS_URL", "")
    qdrant_url: str = os.getenv("QDRANT_URL", "")
    minio_endpoint: str = os.getenv("MINIO_ENDPOINT", "")
    task_queue: str = os.getenv("BID_AGENT_TASK_QUEUE", "local").lower()
    storage_backend: str = os.getenv("BID_AGENT_STORAGE_BACKEND", "json").lower()
    llm_provider: str = os.getenv("BID_AGENT_LLM_PROVIDER", "disabled").lower()
    llm_model: str = os.getenv("BID_AGENT_LLM_MODEL", "")
    llm_api_key: str = os.getenv("BID_AGENT_LLM_API_KEY", "")
    llm_base_url: str = os.getenv("BID_AGENT_LLM_BASE_URL", "")
    ocr_provider: str = os.getenv("BID_AGENT_OCR_PROVIDER", "disabled").lower()
    object_storage_backend: str = os.getenv("BID_AGENT_OBJECT_STORAGE", "local").lower()
    minio_access_key: str = os.getenv("MINIO_ACCESS_KEY", "")
    minio_secret_key: str = os.getenv("MINIO_SECRET_KEY", "")
    minio_bucket: str = os.getenv("MINIO_BUCKET", "bid-agent")
    vector_backend: str = os.getenv("BID_AGENT_VECTOR_BACKEND", "memory").lower()
    qdrant_collection_prefix: str = os.getenv("QDRANT_COLLECTION_PREFIX", "bid_agent")
    embedding_provider: str = os.getenv("BID_AGENT_EMBEDDING_PROVIDER", "hash").lower()
    embedding_model: str = os.getenv("BID_AGENT_EMBEDDING_MODEL", "")
    embedding_api_key: str = os.getenv("BID_AGENT_EMBEDDING_API_KEY", "")
    embedding_base_url: str = os.getenv("BID_AGENT_EMBEDDING_BASE_URL", "")
    workflow_engine: str = os.getenv("BID_AGENT_WORKFLOW_ENGINE", "deterministic").lower()


settings = Settings()
