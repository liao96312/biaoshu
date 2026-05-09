from __future__ import annotations

from app.adapters.llm import DisabledLLMClient, llm_client
from app.models import RiskItem, Severity, TechRequirement


def extract_ai_risks(text: str, project_id: str) -> list[RiskItem]:
    if isinstance(llm_client, DisabledLLMClient):
        return []
    try:
        payload = llm_client.complete_json(_risk_prompt(text), "risk_items")
    except Exception:
        return []
    items = payload.get("items", []) if isinstance(payload, dict) else []
    risks: list[RiskItem] = []
    for item in items:
        source_page = _int_or_none(item.get("source_page"))
        source_text = str(item.get("source_text") or "").strip()
        if source_page is None or not source_text:
            continue
        risks.append(
            RiskItem(
                id=f"AI-R-{len(risks) + 1:03d}",
                project_id=project_id,
                risk_type=str(item.get("risk_type") or "符合性废标"),
                requirement=str(item.get("requirement") or source_text),
                trigger_keyword=str(item.get("trigger_keyword") or "AI"),
                severity=_severity(item.get("severity")),
                need_material=bool(item.get("need_material", True)),
                source_page=source_page,
                source_section=item.get("source_section"),
                source_text=source_text,
                ai_reason=str(item.get("ai_reason") or "AI extracted risk item."),
                suggestion=str(item.get("suggestion") or "请人工复核并补齐材料。"),
                confidence=float(item.get("confidence") or 0.7),
            )
        )
    return risks


def extract_ai_tech_requirements(text: str, project_id: str) -> list[TechRequirement]:
    if isinstance(llm_client, DisabledLLMClient):
        return []
    try:
        payload = llm_client.complete_json(_tech_prompt(text), "tech_requirements")
    except Exception:
        return []
    items = payload.get("items", []) if isinstance(payload, dict) else []
    requirements: list[TechRequirement] = []
    for item in items:
        source_page = _int_or_none(item.get("source_page"))
        source_text = str(item.get("source_text") or "").strip()
        required_value = _float_or_none(item.get("required_value"))
        if source_page is None or not source_text or required_value is None:
            continue
        requirements.append(
            TechRequirement(
                id=f"AI-P-{len(requirements) + 1:03d}",
                project_id=project_id,
                item_name=str(item.get("item_name") or "技术条款"),
                parameter_name=str(item.get("parameter_name") or "参数"),
                operator=str(item.get("operator") or "=="),
                required_value=required_value,
                unit=str(item.get("unit") or ""),
                is_mandatory=bool(item.get("is_mandatory", False)),
                source_page=source_page,
                source_text=source_text,
            )
        )
    return requirements


def _risk_prompt(text: str) -> str:
    return (
        "Extract bid rejection risk items from the tender text. "
        "Return JSON: {\"items\":[{\"risk_type\":\"...\",\"requirement\":\"...\","
        "\"trigger_keyword\":\"...\",\"severity\":\"high|medium|low\",\"need_material\":true,"
        "\"source_page\":1,\"source_section\":\"...\",\"source_text\":\"...\","
        "\"ai_reason\":\"...\",\"suggestion\":\"...\",\"confidence\":0.0}]}.\n\n"
        f"{text[:30000]}"
    )


def _tech_prompt(text: str) -> str:
    return (
        "Extract technical requirements with numeric comparison operators. "
        "Return JSON: {\"items\":[{\"item_name\":\"...\",\"parameter_name\":\"...\","
        "\"operator\":\">=\",\"required_value\":720,\"unit\":\"Mpps\","
        "\"is_mandatory\":true,\"source_page\":1,\"source_text\":\"...\"}]}.\n\n"
        f"{text[:30000]}"
    )


def _severity(value) -> Severity:
    try:
        return Severity(str(value))
    except Exception:
        return Severity.MEDIUM


def _int_or_none(value) -> int | None:
    try:
        return int(value)
    except Exception:
        return None


def _float_or_none(value) -> float | None:
    try:
        return float(value)
    except Exception:
        return None
