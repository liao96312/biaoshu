from __future__ import annotations

from app.knowledge_base import KnowledgeBase
from app.models import RiskItem


def recommend_materials_for_risk(
    knowledge_base: KnowledgeBase,
    company_id: str,
    risk: RiskItem,
    limit: int = 5,
) -> list[dict]:
    query = _risk_query(risk)
    hits = knowledge_base.search(company_id, query, limit=limit)
    return [
        {
            "material_id": hit.id,
            "score": round(hit.score, 4),
            "file_name": hit.payload.get("file_name"),
            "name": hit.payload.get("name"),
            "material_type": hit.payload.get("material_type"),
            "tags": hit.payload.get("tags", []),
            "text": hit.text[:500],
        }
        for hit in hits
    ]


def recommend_materials_for_risks(
    knowledge_base: KnowledgeBase,
    company_id: str,
    risks: list[RiskItem],
    limit_per_risk: int = 5,
) -> list[dict]:
    rows: list[dict] = []
    for risk in risks:
        if not risk.need_material or risk.status.value == "dismissed":
            continue
        rows.append(
            {
                "risk_id": risk.id,
                "risk_type": risk.risk_type,
                "severity": risk.severity.value,
                "requirement": risk.requirement,
                "source_page": risk.source_page,
                "bound_material_ids": risk.material_ids,
                "recommendations": recommend_materials_for_risk(
                    knowledge_base,
                    company_id,
                    risk,
                    limit=limit_per_risk,
                ),
            }
        )
    return rows


def _risk_query(risk: RiskItem) -> str:
    values = [
        risk.requirement,
        risk.trigger_keyword,
        risk.risk_type,
        risk.suggestion,
        risk.source_text,
    ]
    expanded: list[str] = []
    for value in values:
        if not value:
            continue
        expanded.append(value)
        cleaned = _clean_material_query(value)
        if cleaned and cleaned != value:
            expanded.append(cleaned)
    return " ".join(dict.fromkeys(expanded))


def _clean_material_query(value: str) -> str:
    cleaned = value
    for token in [
        "投标人",
        "投标方",
        "须提供",
        "必须提供",
        "应提供",
        "需提供",
        "请提供",
        "上传",
        "补齐",
        "材料",
        "否则投标无效",
        "否则按无效投标处理",
        "否则",
        "不接受",
    ]:
        cleaned = cleaned.replace(token, "")
    return cleaned.strip(" ，,。；;：:")
