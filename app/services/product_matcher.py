from __future__ import annotations

from difflib import SequenceMatcher

from app.models import DeviationResult, Material, TechRequirement
from app.services.deviation import normalize_value
from app.services.deviation import build_deviation
from app.services.tech_params import extract_tech_requirements


def match_products(
    requirements: list[TechRequirement],
    materials: list[Material],
) -> list[DeviationResult]:
    product_params = _extract_product_params(materials)
    results: list[DeviationResult] = []
    for requirement in requirements:
        match = _best_match(requirement, product_params)
        if match is None:
            results.append(build_deviation(requirement))
            continue

        material, product_param, score = match
        our_value = _format_value(product_param.required_value, product_param.unit)
        result = build_deviation(requirement, our_value)
        result.evidence = f"{material.file_name}"
        if product_param.source_page:
            result.evidence += f" 第{product_param.source_page}页"
        result.confidence = max(0.7, min(0.95, score))
        results.append(result)
    return results


def _extract_product_params(
    materials: list[Material],
) -> list[tuple[Material, TechRequirement]]:
    params: list[tuple[Material, TechRequirement]] = []
    for material in materials:
        if material.material_type != "product" or not material.parsed_text:
            continue
        for param in extract_tech_requirements(material.parsed_text, material.company_id):
            params.append((material, param))
    return params


def _best_match(
    requirement: TechRequirement,
    product_params: list[tuple[Material, TechRequirement]],
) -> tuple[Material, TechRequirement, float] | None:
    best: tuple[Material, TechRequirement, float] | None = None
    for material, product_param in product_params:
        if requirement.unit and product_param.unit and not _units_compatible(product_param.unit, requirement.unit):
            continue
        score = _similarity(requirement.parameter_name, product_param.parameter_name)
        if requirement.item_name and requirement.item_name == product_param.item_name:
            score += 0.08
        if score < 0.45:
            continue
        if best is None or score > best[2]:
            best = (material, product_param, score)
    return best


def _similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    if left in right or right in left:
        return 0.88
    return SequenceMatcher(None, left, right).ratio()


def _format_value(value: float, unit: str) -> str:
    display = int(value) if value.is_integer() else value
    return f"{display}{unit}"


def _units_compatible(left: str, right: str) -> bool:
    if left == right:
        return True
    return normalize_value(1, left, right) != 1 or normalize_value(1, right, left) != 1
