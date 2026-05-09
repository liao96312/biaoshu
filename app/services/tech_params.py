from __future__ import annotations

import re

from app.models import TechRequirement
from app.services.parser import iter_page_chunks


OPERATOR_ALIASES = {
    ">=": ["≥", ">=", "不少于", "不低于", "至少", "以上", "不小于", "不低于"],
    "<=": ["≤", "<=", "不超过", "不高于", "以内", "不大于"],
    ">": [">", "大于", "超过"],
    "<": ["<", "小于", "低于"],
    "==": ["=", "等于", "恰好", "刚好"],
}

UNIT_PATTERN = r"(Tbps|Gbps|Mbps|Mpps|Kpps|GB|MB|TB|W|kW|ms|秒|分钟|小时|天|年|%|个|台|套|项)"
PARAM_PATTERN = re.compile(
    rf"(?P<name>[\u4e00-\u9fa5A-Za-z0-9/（）()\-]{{2,32}}?)"
    rf"(?P<op>≥|≤|>=|<=|>|<|=|不少于|不低于|至少|以上|不小于|不超过|不高于|以内|不大于|大于|超过|小于|低于|等于|恰好|刚好)"
    rf"\s*(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>{UNIT_PATTERN})?"
)


def extract_tech_requirements(text: str, project_id: str) -> list[TechRequirement]:
    requirements: list[TechRequirement] = []
    seen: set[tuple[int | None, str, float, str]] = set()
    for page, chunk in iter_page_chunks(text):
        for sentence in _candidate_sentences(chunk):
            mandatory = "★" in sentence or "必须" in sentence or "不得偏离" in sentence
            for match in PARAM_PATTERN.finditer(sentence):
                name = _clean_name(match.group("name"))
                value = float(match.group("value"))
                unit = match.group("unit") or ""
                operator = normalize_operator(match.group("op"))
                key = (page, name, value, unit)
                if key in seen:
                    continue
                seen.add(key)
                requirements.append(
                    TechRequirement(
                        id=f"P-{len(requirements) + 1:03d}",
                        project_id=project_id,
                        item_name=_guess_item(sentence),
                        parameter_name=name,
                        operator=operator,
                        required_value=value,
                        unit=unit,
                        is_mandatory=mandatory,
                        source_page=page,
                        source_text=_compact(sentence, 260),
                    )
                )
    return requirements


def normalize_operator(value: str) -> str:
    for operator, aliases in OPERATOR_ALIASES.items():
        if value in aliases:
            return operator
    return "=="


def format_requirement(requirement: TechRequirement) -> str:
    value = int(requirement.required_value) if requirement.required_value.is_integer() else requirement.required_value
    return f"{requirement.operator}{value}{requirement.unit}"


def _candidate_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[。；;])|\n+", text)
    return [_compact(part, 320) for part in parts if any(alias in part for aliases in OPERATOR_ALIASES.values() for alias in aliases)]


def _guess_item(sentence: str) -> str:
    if "交换机" in sentence:
        return "交换机"
    if "服务器" in sentence:
        return "服务器"
    if "防火墙" in sentence:
        return "防火墙"
    if "路由器" in sentence:
        return "路由器"
    return "技术条款"


def _clean_name(value: str) -> str:
    value = value.strip(" ，,：:；;。★*")
    for marker in ["支持", "提供", "要求", "参数", "核心"]:
        if value.startswith(marker) and len(value) > len(marker) + 1:
            value = value[len(marker) :]
    return value[-24:] if len(value) > 24 else value


def _compact(value: str, limit: int) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    return value if len(value) <= limit else value[: limit - 1] + "…"
