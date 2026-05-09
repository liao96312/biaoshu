from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.models import RiskItem, Severity
from app.services.parser import iter_page_chunks


HIGH_KEYWORDS = [
    "投标无效",
    "无效投标",
    "废标",
    "否决投标",
    "不得偏离",
    "不允许负偏离",
    "实质性响应",
    "否则按无效",
    "资格审查不通过",
    "符合性审查不通过",
]

MEDIUM_KEYWORDS = [
    "必须提供",
    "须提供",
    "未提供",
    "不接受",
    "投标保证金",
    "签字",
    "盖章",
    "原厂质保",
    "交付周期",
]

RISK_TYPES = {
    "资格": "资格性废标",
    "资质": "资格性废标",
    "证书": "资格性废标",
    "信用中国": "资格性废标",
    "审计报告": "资格性废标",
    "保证金": "符合性废标",
    "签字": "符合性废标",
    "盖章": "符合性废标",
    "报价": "商务性废标",
    "付款": "商务性废标",
    "质保": "技术性废标",
    "★": "技术性废标",
    "参数": "技术性废标",
}


@dataclass(frozen=True)
class RiskHit:
    keyword: str
    severity: Severity


def scan_risks(text: str, project_id: str) -> list[RiskItem]:
    risks: list[RiskItem] = []
    seen: set[tuple[int | None, str, str]] = set()

    for page, chunk in iter_page_chunks(text):
        sentences = _split_sentences(chunk)
        section = _guess_section(chunk)
        for sentence in sentences:
            hit = _match_risk(sentence)
            if hit is None:
                continue
            key = (page, hit.keyword, sentence[:80])
            if key in seen:
                continue
            seen.add(key)
            risk_type = _classify_risk(sentence)
            risks.append(
                RiskItem(
                    id=f"R-{len(risks) + 1:03d}",
                    project_id=project_id,
                    risk_type=risk_type,
                    requirement=_compact(sentence, 120),
                    trigger_keyword=hit.keyword,
                    severity=hit.severity,
                    need_material=_needs_material(sentence),
                    source_page=page,
                    source_section=section,
                    source_text=_compact(sentence, 240),
                    ai_reason=f"命中“{hit.keyword}”等硬性要求线索，需人工确认是否会导致废标。",
                    suggestion=_suggest(sentence, risk_type),
                    confidence=0.92 if hit.severity == Severity.HIGH else 0.78,
                )
            )
    return risks


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[。；;])|\n+", text)
    return [_compact(part, 300) for part in parts if part.strip()]


def _match_risk(sentence: str) -> RiskHit | None:
    normalized = sentence.replace(" ", "")
    high_keywords, medium_keywords, _ = _configured_rules()
    for keyword in high_keywords:
        if keyword in normalized:
            return RiskHit(keyword=keyword, severity=Severity.HIGH)
    for keyword in medium_keywords:
        if keyword in normalized:
            return RiskHit(keyword=keyword, severity=Severity.MEDIUM)
    return None


def _classify_risk(sentence: str) -> str:
    _, _, risk_types = _configured_rules()
    for keyword, risk_type in risk_types.items():
        if keyword in sentence:
            return risk_type
    return "符合性废标"


def _guess_section(chunk: str) -> str | None:
    for line in chunk.splitlines()[:8]:
        line = line.strip()
        if 4 <= len(line) <= 40 and any(token in line for token in ["章", "节", "资格", "技术", "商务", "审查"]):
            return line
    return None


def _needs_material(sentence: str) -> bool:
    return any(token in sentence for token in ["提供", "上传", "证明", "证书", "报告", "回单", "材料"])


def _suggest(sentence: str, risk_type: str) -> str:
    if "保证金" in sentence:
        return "核对投标保证金金额、缴纳时间和凭证，并上传银行回单或保函。"
    if "审计" in sentence or "财务" in sentence:
        return "准备对应年度财务审计报告，并确认页数、签章和扫描件清晰度。"
    if "签字" in sentence or "盖章" in sentence:
        return "检查投标文件签字盖章位置，导出前逐页复核。"
    if "质保" in sentence or "参数" in sentence or "★" in sentence:
        return "与产品规格书逐项核对，无法满足时标记为负偏离并升级确认。"
    return f"按{risk_type}要求补齐材料，并在提交前人工确认。"


def _compact(value: str, limit: int) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    return value if len(value) <= limit else value[: limit - 1] + "…"


@lru_cache(maxsize=1)
def _configured_rules() -> tuple[list[str], list[str], dict[str, str]]:
    path = Path(__file__).resolve().parents[1] / "rules" / "risk_rules.json"
    if not path.exists():
        return HIGH_KEYWORDS, MEDIUM_KEYWORDS, RISK_TYPES
    payload = json.loads(path.read_text(encoding="utf-8"))
    high = _merge_terms(HIGH_KEYWORDS, payload.get("high_keywords", []))
    medium = _merge_terms(MEDIUM_KEYWORDS, payload.get("medium_keywords", []))
    risk_types = dict(RISK_TYPES)
    risk_types.update(payload.get("risk_types", {}))
    return high, medium, risk_types


def _merge_terms(defaults: list[str], configured: list[str]) -> list[str]:
    terms: list[str] = []
    for item in [*configured, *defaults]:
        if item and item not in terms:
            terms.append(item)
    return terms


def reload_rules() -> None:
    _configured_rules.cache_clear()
