from __future__ import annotations

import asyncio

from fastapi import BackgroundTasks

from app.config import settings
from app.jobs import process_document_task


class LocalTaskQueue:
    name = "local_background"

    def enqueue_document_parse(
        self,
        background_tasks: BackgroundTasks,
        document_id: str,
        task_id: str,
    ) -> None:
        background_tasks.add_task(process_document_task, document_id, task_id)


class CeleryTaskQueue:
    name = "celery"

    def __init__(self) -> None:
        try:
            from celery import Celery
        except ImportError as exc:
            raise RuntimeError("celery is not installed") from exc
        broker = settings.redis_url or "redis://redis:6379/0"
        self.app = Celery("bid_agent", broker=broker, backend=broker)

    def enqueue_document_parse(
        self,
        background_tasks: BackgroundTasks,
        document_id: str,
        task_id: str,
    ) -> None:
        self.app.send_task("app.worker.process_document", args=[document_id, task_id])


def create_task_queue():
    if settings.task_queue == "celery":
        return CeleryTaskQueue()
    return LocalTaskQueue()


task_queue = create_task_queue()


def run_document_parse_sync(document_id: str, task_id: str) -> None:
    asyncio.run(process_document_task(document_id, task_id))
