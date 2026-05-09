from __future__ import annotations

import hashlib
import json
import math
import urllib.request
from dataclasses import dataclass
from typing import Protocol

from app.config import settings


@dataclass(frozen=True)
class SearchHit:
    id: str
    text: str
    score: float
    payload: dict


class VectorStore(Protocol):
    name: str

    def upsert_text(self, collection: str, item_id: str, text: str, payload: dict) -> None:
        """Index text for semantic retrieval."""

    def delete_text(self, collection: str, item_id: str) -> None:
        """Remove indexed text."""

    def search(self, collection: str, query: str, limit: int = 5) -> list[SearchHit]:
        """Search indexed text."""


class InMemoryVectorStore:
    name = "memory"

    def __init__(self) -> None:
        self._items: dict[str, list[tuple[str, str, dict, list[float]]]] = {}
        self.embedding = create_embedding_provider()

    def upsert_text(self, collection: str, item_id: str, text: str, payload: dict) -> None:
        items = [item for item in self._items.get(collection, []) if item[0] != item_id]
        items.append((item_id, text, payload, self.embedding.embed(text)))
        self._items[collection] = items

    def delete_text(self, collection: str, item_id: str) -> None:
        self._items[collection] = [item for item in self._items.get(collection, []) if item[0] != item_id]

    def search(self, collection: str, query: str, limit: int = 5) -> list[SearchHit]:
        query_vector = self.embedding.embed(query)
        terms = {term for term in query.lower().split() if term}
        hits: list[SearchHit] = []
        for item_id, text, payload, vector in self._items.get(collection, []):
            haystack = text.lower()
            keyword_score = sum(1 for term in terms if term in haystack) / max(len(terms), 1)
            vector_score = _cosine(query_vector, vector) if self.embedding.name != "hash" else 0.0
            score = max(keyword_score, vector_score)
            if score > 0:
                hits.append(SearchHit(id=item_id, text=text, score=score, payload=payload))
        return sorted(hits, key=lambda hit: hit.score, reverse=True)[:limit]


class QdrantVectorStore:
    name = "qdrant"

    def __init__(self) -> None:
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, PointIdsList, PointStruct, VectorParams
        except ImportError as exc:
            raise RuntimeError("qdrant-client is not installed") from exc
        self._PointIdsList = PointIdsList
        self._PointStruct = PointStruct
        self._VectorParams = VectorParams
        self._Distance = Distance
        self.client = QdrantClient(url=settings.qdrant_url)
        self.embedding = create_embedding_provider()

    def upsert_text(self, collection: str, item_id: str, text: str, payload: dict) -> None:
        name = _collection_name(collection)
        vector = self.embedding.embed(text)
        self._ensure_collection(name, len(vector))
        point = self._PointStruct(
            id=_point_id(item_id),
            vector=vector,
            payload={"text": text, "item_id": item_id, **payload},
        )
        self.client.upsert(collection_name=name, points=[point])

    def delete_text(self, collection: str, item_id: str) -> None:
        name = _collection_name(collection)
        existing = {item.name for item in self.client.get_collections().collections}
        if name not in existing:
            return
        self.client.delete(collection_name=name, points_selector=self._PointIdsList(points=[_point_id(item_id)]))

    def search(self, collection: str, query: str, limit: int = 5) -> list[SearchHit]:
        name = _collection_name(collection)
        vector = self.embedding.embed(query)
        self._ensure_collection(name, len(vector))
        results = self.client.search(collection_name=name, query_vector=vector, limit=limit)
        return [
            SearchHit(
                id=str(hit.payload.get("item_id") or hit.id),
                text=str(hit.payload.get("text") or ""),
                score=float(hit.score),
                payload={key: value for key, value in hit.payload.items() if key != "text"},
            )
            for hit in results
        ]

    def _ensure_collection(self, name: str, size: int) -> None:
        existing = {item.name for item in self.client.get_collections().collections}
        if name not in existing:
            self.client.create_collection(
                collection_name=name,
                vectors_config=self._VectorParams(size=size, distance=self._Distance.COSINE),
            )


class EmbeddingProvider(Protocol):
    name: str

    def embed(self, text: str) -> list[float]:
        """Return a vector for retrieval."""


class HashEmbeddingProvider:
    name = "hash"

    def embed(self, text: str) -> list[float]:
        return _hash_embedding(text)


class OpenAICompatibleEmbeddingProvider:
    name = "openai_compatible"

    def __init__(self) -> None:
        self.model = settings.embedding_model or "text-embedding-3-small"
        self.api_key = settings.embedding_api_key or settings.llm_api_key
        self.base_url = (
            settings.embedding_base_url
            or settings.llm_base_url
            or _default_embedding_base_url(settings.embedding_provider)
        ).rstrip("/")
        if not self.api_key:
            raise RuntimeError("embedding api key is required")

    def embed(self, text: str) -> list[float]:
        payload = json.dumps({"model": self.model, "input": text}, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/embeddings",
            data=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
        vector = body.get("data", [{}])[0].get("embedding")
        if not isinstance(vector, list):
            raise RuntimeError("embedding response did not include a vector")
        return [float(item) for item in vector]


def create_embedding_provider() -> EmbeddingProvider:
    if settings.embedding_provider in {"openai", "openai_compatible", "qwen", "deepseek"}:
        return OpenAICompatibleEmbeddingProvider()
    return HashEmbeddingProvider()


def create_vector_store() -> VectorStore:
    if settings.vector_backend == "qdrant":
        return QdrantVectorStore()
    return InMemoryVectorStore()


def _collection_name(collection: str) -> str:
    safe = "".join(ch if ch.isalnum() else "_" for ch in collection)
    return f"{settings.qdrant_collection_prefix}_{safe}"


def _point_id(item_id: str) -> int:
    return int(hashlib.sha256(item_id.encode("utf-8")).hexdigest()[:16], 16)


def _hash_embedding(text: str) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    values = []
    for index in range(64):
        byte = digest[index % len(digest)]
        values.append((byte / 127.5) - 1.0)
    return values


def _cosine(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(item * item for item in left))
    right_norm = math.sqrt(sum(item * item for item in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return max(numerator / (left_norm * right_norm), 0.0)


def _default_embedding_base_url(provider: str) -> str:
    if provider == "qwen":
        return "https://dashscope.aliyuncs.com/compatible-mode/v1"
    if provider == "deepseek":
        return "https://api.deepseek.com/v1"
    return "https://api.openai.com/v1"


vector_store = create_vector_store()
