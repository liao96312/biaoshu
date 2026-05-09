from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.services.risk_scanner import reload_rules


RISK_RULES_PATH = Path(__file__).resolve().parents[1] / "rules" / "risk_rules.json"


def read_risk_rules() -> dict[str, Any]:
    return json.loads(RISK_RULES_PATH.read_text(encoding="utf-8"))


def write_risk_rules(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = {
        "high_keywords": _strings(payload.get("high_keywords", [])),
        "medium_keywords": _strings(payload.get("medium_keywords", [])),
        "risk_types": {
            str(key).strip(): str(value).strip()
            for key, value in payload.get("risk_types", {}).items()
            if str(key).strip() and str(value).strip()
        },
    }
    RISK_RULES_PATH.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    reload_rules()
    return normalized


def _strings(values: list[Any]) -> list[str]:
    result: list[str] = []
    for value in values:
        item = str(value).strip()
        if item and item not in result:
            result.append(item)
    return result
