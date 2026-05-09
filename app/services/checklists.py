from __future__ import annotations

from app.models import DeviationResult, Material, RiskItem


def build_material_gap_list(risks: list[RiskItem], materials: list[Material] | None = None) -> list[dict]:
    material_names = _material_names(materials or [])
    items: list[dict] = []
    for risk in risks:
        if not risk.need_material:
            continue
        if risk.status.value in {"dismissed", "approved"}:
            continue
        items.append(
            {
                "risk_id": risk.id,
                "severity": risk.severity.value,
                "risk_type": risk.risk_type,
                "material_requirement": risk.requirement,
                "suggestion": risk.suggestion,
                "source_page": risk.source_page,
                "source_section": risk.source_section,
                "status": risk.status.value,
                "material_ids": risk.material_ids,
                "bound_materials": [material_names.get(material_id, material_id) for material_id in risk.material_ids],
            }
        )
    return items


def build_scoring_matrix(
    deviations: list[DeviationResult],
    risks: list[RiskItem],
    materials: list[Material] | None = None,
) -> list[dict]:
    material_names = _material_names(materials or [])
    rows: list[dict] = []
    for deviation in deviations:
        rows.append(
            {
                "source": "tech_deviation",
                "item_id": deviation.id,
                "score_point": f"{deviation.item} - {deviation.parameter}",
                "requirement": deviation.required_value,
                "response": deviation.response_text,
                "evidence": deviation.evidence,
                "source_page": deviation.source_page,
                "status": deviation.deviation_type.value,
                "priority": _deviation_priority(deviation.deviation_type.value),
            }
        )
    for risk in risks:
        if risk.severity.value != "high":
            continue
        rows.append(
            {
                "source": "risk",
                "item_id": risk.id,
                "score_point": risk.risk_type,
                "requirement": risk.requirement,
                "response": risk.suggestion,
                "evidence": ", ".join(material_names.get(material_id, material_id) for material_id in risk.material_ids),
                "source_page": risk.source_page,
                "status": risk.status.value,
                "priority": "high",
            }
        )
    return sorted(rows, key=lambda item: {"high": 0, "medium": 1, "low": 2}.get(item["priority"], 3))


def _material_names(materials: list[Material]) -> dict[str, str]:
    return {
        material.id: material.name or material.file_name or material.id
        for material in materials
    }


def _deviation_priority(deviation_type: str) -> str:
    if deviation_type == "negative":
        return "high"
    if deviation_type == "unknown":
        return "medium"
    return "low"
