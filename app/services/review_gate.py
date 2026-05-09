from __future__ import annotations

from app.models import DeviationResult, RiskItem


def review_summary(risks: list[RiskItem], deviations: list[DeviationResult]) -> dict:
    blockers = review_blockers(risks, deviations)
    risk_status = _count_by([risk.status.value for risk in risks], ["pending", "confirmed", "dismissed", "modified", "approved"])
    risk_severity = _count_by([risk.severity.value for risk in risks], ["high", "medium", "low"])
    deviation_status = _count_by(
        [deviation.reviewer_status.value for deviation in deviations],
        ["pending", "confirmed", "dismissed", "modified", "approved"],
    )
    deviation_type = _count_by(
        [deviation.deviation_type.value for deviation in deviations],
        ["positive", "none", "negative", "unknown"],
    )
    return {
        "ready_to_complete": len(blockers) == 0,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "risks": {
            "total": len(risks),
            "by_status": risk_status,
            "by_severity": risk_severity,
            "pending_high": sum(1 for risk in risks if risk.severity.value == "high" and risk.status.value == "pending"),
            "missing_source": sum(1 for risk in risks if risk.source_page is None),
            "low_confidence": sum(1 for risk in risks if risk.confidence < 0.7),
        },
        "deviations": {
            "total": len(deviations),
            "by_status": deviation_status,
            "by_type": deviation_type,
            "pending_negative_or_unknown": sum(
                1
                for deviation in deviations
                if deviation.deviation_type.value in {"negative", "unknown"}
                and deviation.reviewer_status.value == "pending"
            ),
            "missing_source": sum(1 for deviation in deviations if deviation.source_page is None),
            "low_confidence": sum(1 for deviation in deviations if deviation.confidence < 0.7),
        },
    }


def review_blockers(risks: list[RiskItem], deviations: list[DeviationResult]) -> list[dict]:
    blockers: list[dict] = []
    for risk in risks:
        if risk.source_page is None and risk.status.value == "pending":
            blockers.append(
                {
                    "type": "risk",
                    "id": risk.id,
                    "message": "risk item without source page must be reviewed",
                    "requirement": risk.requirement,
                }
            )
            continue
        if risk.severity.value == "high" and risk.status.value == "pending":
            blockers.append(
                {
                    "type": "risk",
                    "id": risk.id,
                    "message": "high risk item must be reviewed",
                    "requirement": risk.requirement,
                }
            )
        elif risk.confidence < 0.7 and risk.status.value == "pending":
            blockers.append(
                {
                    "type": "risk",
                    "id": risk.id,
                    "message": "low confidence risk item must be reviewed",
                    "requirement": risk.requirement,
                }
            )
    for deviation in deviations:
        if deviation.source_page is None and deviation.reviewer_status.value == "pending":
            blockers.append(
                {
                    "type": "deviation",
                    "id": deviation.id,
                    "message": "deviation without source page must be reviewed",
                    "requirement": deviation.required_value,
                }
            )
            continue
        if deviation.deviation_type.value in {"negative", "unknown"} and deviation.reviewer_status.value == "pending":
            blockers.append(
                {
                    "type": "deviation",
                    "id": deviation.id,
                    "message": "negative or unknown deviation must be reviewed",
                    "requirement": deviation.required_value,
                }
            )
        elif deviation.confidence < 0.7 and deviation.reviewer_status.value == "pending":
            blockers.append(
                {
                    "type": "deviation",
                    "id": deviation.id,
                    "message": "low confidence deviation must be reviewed",
                    "requirement": deviation.required_value,
                }
            )
    return blockers


def _count_by(values: list[str], keys: list[str]) -> dict[str, int]:
    result = {key: 0 for key in keys}
    for value in values:
        result[value] = result.get(value, 0) + 1
    return result
