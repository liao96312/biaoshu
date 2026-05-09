from __future__ import annotations

from celery import Celery

from app.config import settings
from app.task_queue import run_document_parse_sync

broker = settings.redis_url or "redis://redis:6379/0"
celery_app = Celery("bid_agent", broker=broker, backend=broker)


@celery_app.task(name="app.worker.process_document")
def process_document(document_id: str, task_id: str) -> None:
    run_document_parse_sync(document_id, task_id)
