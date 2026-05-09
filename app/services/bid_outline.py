from __future__ import annotations

from app.models import DeviationResult, Material, RiskItem


def build_bid_outline(
    risks: list[RiskItem],
    deviations: list[DeviationResult],
    materials: list[Material],
) -> list[dict]:
    return [
        {"code": "1", "title": "资格审查响应文件", "items": _qualification_items(risks, materials)},
        {"code": "2", "title": "商务响应文件", "items": _business_items(risks)},
        {"code": "3", "title": "技术响应文件", "items": _technical_items(deviations)},
        {
            "code": "4",
            "title": "技术偏离表",
            "items": [
                {
                    "title": "技术偏离表",
                    "source": "deviation_table",
                    "status": "draft",
                    "notes": f"{len(deviations)} 条技术参数响应",
                }
            ],
        },
        {"code": "5", "title": "附件与证明材料", "items": _material_items(materials)},
    ]


def _qualification_items(risks: list[RiskItem], materials: list[Material]) -> list[dict]:
    items = []
    for risk in risks:
        if risk.risk_type == "资格性废标":
            items.append({"title": risk.requirement, "source": f"risk:{risk.id}", "status": risk.status.value, "notes": risk.suggestion})
    for material in materials:
        if material.material_type == "qualification":
            items.append({"title": material.name or material.file_name, "source": f"material:{material.id}", "status": "available", "notes": ",".join(material.tags)})
    return items or [{"title": "资格证明材料", "source": "template", "status": "pending", "notes": "待补充"}]


def _business_items(risks: list[RiskItem]) -> list[dict]:
    items = []
    for risk in risks:
        if risk.risk_type == "商务性废标":
            items.append({"title": risk.requirement, "source": f"risk:{risk.id}", "status": risk.status.value, "notes": risk.suggestion})
    return items or [{"title": "商务条款响应", "source": "template", "status": "draft", "notes": "按招标文件要求编制"}]


def _technical_items(deviations: list[DeviationResult]) -> list[dict]:
    if not deviations:
        return [{"title": "技术方案响应", "source": "template", "status": "pending", "notes": "待解析技术参数"}]
    return [
        {
            "title": f"{item.item} - {item.parameter}",
            "source": f"deviation:{item.id}",
            "status": item.deviation_type.value,
            "notes": item.response_text,
        }
        for item in deviations
    ]


def _material_items(materials: list[Material]) -> list[dict]:
    return [
        {
            "title": material.name or material.file_name,
            "source": f"material:{material.id}",
            "status": "available",
            "notes": material.material_type,
        }
        for material in materials
    ] or [{"title": "附件材料", "source": "template", "status": "pending", "notes": "待上传"}]
