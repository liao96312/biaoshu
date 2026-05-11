from __future__ import annotations

import shutil
from pathlib import Path
from typing import Protocol

from app.config import settings


class ObjectStorage(Protocol):
    name: str

    def put_file(self, source: Path, key: str) -> str:
        """Store a file and return its storage path."""

    def delete_file(self, key: str) -> int:
        """Delete one stored object and return the number of files removed."""

    def delete_prefix(self, prefix: str) -> int:
        """Delete stored objects under a prefix and return the number removed."""


class LocalObjectStorage:
    name = "local"

    def __init__(self, root: str = "storage/objects") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def put_file(self, source: Path, key: str) -> str:
        target = self._target_for_key(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        return str(target)

    def delete_file(self, key: str) -> int:
        try:
            target = self._target_for_key(key)
            if not target.is_file():
                return 0
            target.unlink()
            return 1
        except (OSError, ValueError):
            return 0

    def delete_prefix(self, prefix: str) -> int:
        try:
            target = self._target_for_key(prefix)
            if not target.exists():
                return 0
            if target.is_file():
                target.unlink()
                return 1
            count = sum(1 for item in target.rglob("*") if item.is_file())
            shutil.rmtree(target)
            return count
        except (OSError, ValueError):
            return 0

    def _target_for_key(self, key: str) -> Path:
        target = (self.root / key).resolve()
        if not _is_under(target, self.root.resolve()):
            raise ValueError("object key escapes storage root")
        return target


class MinioObjectStorage:
    name = "minio"

    def __init__(self) -> None:
        try:
            from minio import Minio
        except ImportError as exc:
            raise RuntimeError("minio is not installed") from exc
        endpoint = settings.minio_endpoint.replace("http://", "").replace("https://", "")
        secure = settings.minio_endpoint.startswith("https://")
        self.bucket = settings.minio_bucket
        self.client = Minio(
            endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=secure,
        )
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    def put_file(self, source: Path, key: str) -> str:
        self.client.fput_object(self.bucket, key, str(source))
        return f"minio://{self.bucket}/{key}"

    def delete_file(self, key: str) -> int:
        try:
            self.client.remove_object(self.bucket, key)
            return 1
        except Exception:
            return 0

    def delete_prefix(self, prefix: str) -> int:
        try:
            objects = list(self.client.list_objects(self.bucket, prefix=prefix, recursive=True))
            for item in objects:
                self.client.remove_object(self.bucket, item.object_name)
            return len(objects)
        except Exception:
            return 0


def create_object_storage() -> ObjectStorage:
    if settings.object_storage_backend == "minio":
        return MinioObjectStorage()
    return LocalObjectStorage()


object_storage = create_object_storage()


def _is_under(path: Path, root: Path) -> bool:
    return path == root or root in path.parents
