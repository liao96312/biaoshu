from __future__ import annotations

from app.adapters.vector_store import SearchHit, vector_store
from app.models import Material


class KnowledgeBase:
    def __init__(self) -> None:
        self.vector_store = vector_store

    def index_material(self, material: Material) -> None:
        text = material.parsed_text or material.name or material.file_name
        if not text:
            return
        self.vector_store.upsert_text(
            collection=_collection(material.company_id),
            item_id=material.id,
            text=text,
            payload={
                "company_id": material.company_id,
                "material_id": material.id,
                "material_type": material.material_type,
                "file_name": material.file_name,
                "name": material.name,
                "tags": material.tags,
            },
        )

    def delete_material(self, material: Material) -> None:
        self.vector_store.delete_text(_collection(material.company_id), material.id)

    def search(self, company_id: str, query: str, limit: int = 5) -> list[SearchHit]:
        return self.vector_store.search(_collection(company_id), query, limit=limit)


def _collection(company_id: str) -> str:
    return f"company:{company_id}:materials"


knowledge_base = KnowledgeBase()
