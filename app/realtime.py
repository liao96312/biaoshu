from __future__ import annotations

from collections import defaultdict
from typing import Any

from fastapi import WebSocket


class TaskConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, task_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[task_id].add(websocket)

    def disconnect(self, task_id: str, websocket: WebSocket) -> None:
        self._connections[task_id].discard(websocket)
        if not self._connections[task_id]:
            self._connections.pop(task_id, None)

    async def broadcast(self, task_id: str, event: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for websocket in self._connections.get(task_id, set()):
            try:
                await websocket.send_json(event)
            except Exception:
                dead.append(websocket)
        for websocket in dead:
            self.disconnect(task_id, websocket)


task_connections = TaskConnectionManager()
