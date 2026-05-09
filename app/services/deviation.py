from __future__ import annotations

import re

from app.models import DeviationResult, DeviationType, TechRequirement
from app.services.tech_params import format_requirement


def build_deviation(requirement: TechRequirement, our_value: str | None = None) -> DeviationResult:
    deviation_type = judge_deviation(requirement.operator, requirement.required_value, our_value, requirement.unit)
    return DeviationResult(
        id=requirement.id,
        project_id=requirement.project_id,
        tech_requirement_id=requirement.id,
        item=requirement.item_name,
        parameter=requirement.parameter_name,
        required_value=format_requirement(requirement),
        our_value=our_value,
        deviation_type=deviation_type,
        response_text=_response_text(requirement, our_value, deviation_type),
        source_page=requirement.source_page,
        confidence=0.82 if our_value else 0.7,
    )


def judge_deviation(
    operator: str,
    required_value: float,
    our_value: str | None,
    required_unit: str | None = None,
) -> DeviationType:
    parsed = parse_number(our_value)
    if parsed is None:
        return DeviationType.UNKNOWN
    parsed = normalize_value(parsed, parse_unit(our_value), required_unit)

    if operator == ">=":
        if parsed > required_value:
            return DeviationType.POSITIVE
        if parsed == required_value:
            return DeviationType.NONE
        return DeviationType.NEGATIVE
    if operator == ">":
        return DeviationType.POSITIVE if parsed > required_value else DeviationType.NEGATIVE
    if operator == "<=":
        if parsed < required_value:
            return DeviationType.POSITIVE
        if parsed == required_value:
            return DeviationType.NONE
        return DeviationType.NEGATIVE
    if operator == "<":
        return DeviationType.POSITIVE if parsed < required_value else DeviationType.NEGATIVE
    if operator == "==":
        return DeviationType.NONE if parsed == required_value else DeviationType.NEGATIVE
    return DeviationType.UNKNOWN


def parse_number(value: str | None) -> float | None:
    if not value:
        return None
    match = re.search(r"\d+(?:\.\d+)?", value)
    return float(match.group(0)) if match else None


def parse_unit(value: str | None) -> str:
    if not value:
        return ""
    match = re.search(r"(Tbps|Gbps|Mbps|Mpps|Kpps|TB|GB|MB|KB|%|年|天|小时|分钟|秒)", value, re.IGNORECASE)
    return match.group(1) if match else ""


def normalize_value(value: float, from_unit: str | None, to_unit: str | None) -> float:
    from_unit = _unit_key(from_unit)
    to_unit = _unit_key(to_unit)
    if not from_unit or not to_unit or from_unit == to_unit:
        return value
    groups = [
        {"tbps": 1_000_000, "gbps": 1_000, "mbps": 1},
        {"mpps": 1_000, "kpps": 1},
        {"tb": 1_000_000, "gb": 1_000, "mb": 1, "kb": 0.001},
        {"年": 365, "天": 1},
        {"小时": 3600, "分钟": 60, "秒": 1},
    ]
    for group in groups:
        if from_unit in group and to_unit in group:
            base = value * group[from_unit]
            return base / group[to_unit]
    return value


def _unit_key(value: str | None) -> str:
    return (value or "").strip().lower()


def _response_text(
    requirement: TechRequirement, our_value: str | None, deviation_type: DeviationType
) -> str:
    if our_value is None:
        return "待补充我方响应"
    if deviation_type == DeviationType.POSITIVE:
        return f"满足，实际提供{our_value}，优于招标要求。"
    if deviation_type == DeviationType.NONE:
        return f"满足，实际提供{our_value}，符合招标要求。"
    if deviation_type == DeviationType.NEGATIVE:
        return f"实际提供{our_value}，低于招标要求，需人工确认。"
    return f"已填写我方参数{our_value}，需人工复核。"
