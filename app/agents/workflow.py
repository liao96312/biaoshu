from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from typing import Any

from app.config import settings
from app.models import DeviationResult, Material, RiskItem, TechRequirement
from app.services.parser import ParsedDocument, parse_document
from app.services.ai_extractors import extract_ai_risks, extract_ai_tech_requirements
from app.services.product_matcher import match_products
from app.services.risk_scanner import scan_risks
from app.services.tech_params import extract_tech_requirements


@dataclass
class WorkflowResult:
    parsed: ParsedDocument
    risks: list[RiskItem]
    requirements: list[TechRequirement]
    deviations: list[DeviationResult]


class DocumentParserAgent:
    def run(self, file_path: str) -> ParsedDocument:
        return parse_document(file_path)


class SectionClassifierAgent:
    def run(self, parsed: ParsedDocument) -> ParsedDocument:
        return parsed


class ClauseExtractorAgent:
    def run(self, parsed: ParsedDocument) -> ParsedDocument:
        return parsed


class RiskScannerAgent:
    def run(self, text: str, project_id: str) -> list[RiskItem]:
        return _dedupe_risks([*scan_risks(text, project_id), *extract_ai_risks(text, project_id)])


class TechParamExtractorAgent:
    def run(self, text: str, project_id: str) -> list[TechRequirement]:
        return _dedupe_requirements(
            [*extract_tech_requirements(text, project_id), *extract_ai_tech_requirements(text, project_id)]
        )


class ProductMatcherAgent:
    def run(
        self,
        requirements: list[TechRequirement],
        materials: list[Material],
    ) -> list[DeviationResult]:
        return match_products(requirements, materials)


class DeviationJudgeAgent:
    def run(self, deviations: list[DeviationResult]) -> list[DeviationResult]:
        return deviations


class DocumentGeneratorAgent:
    pass


class BidRiskWorkflow:
    def __init__(self) -> None:
        self.document_parser = DocumentParserAgent()
        self.section_classifier = SectionClassifierAgent()
        self.clause_extractor = ClauseExtractorAgent()
        self.risk_scanner = RiskScannerAgent()
        self.tech_param_extractor = TechParamExtractorAgent()
        self.product_matcher = ProductMatcherAgent()
        self.deviation_judge = DeviationJudgeAgent()
        self.document_generator = DocumentGeneratorAgent()
        self.engine = "deterministic"
        self._graph = None
        if settings.workflow_engine == "langgraph":
            self._graph = self._build_langgraph()
            if self._graph is not None:
                self.engine = "langgraph"

    def run(self, file_path: str, project_id: str, materials: list[Material]) -> WorkflowResult:
        if self._graph is not None:
            state = self._graph.invoke(
                {
                    "file_path": file_path,
                    "project_id": project_id,
                    "materials": materials,
                }
            )
            return state["result"]
        return self._run_deterministic(file_path, project_id, materials)

    def _run_deterministic(self, file_path: str, project_id: str, materials: list[Material]) -> WorkflowResult:
        parsed = self.document_parser.run(file_path)
        parsed = self.section_classifier.run(parsed)
        parsed = self.clause_extractor.run(parsed)
        risks = self.risk_scanner.run(parsed.text, project_id)
        requirements = self.tech_param_extractor.run(parsed.text, project_id)
        deviations = self.product_matcher.run(requirements, materials)
        deviations = self.deviation_judge.run(deviations)
        return WorkflowResult(
            parsed=parsed,
            risks=risks,
            requirements=requirements,
            deviations=deviations,
        )

    def _build_langgraph(self):
        if importlib.util.find_spec("langgraph") is None:
            return None
        try:
            from langgraph.graph import END, StateGraph
        except Exception:
            return None

        def parse_node(state: dict[str, Any]) -> dict[str, Any]:
            parsed = self.document_parser.run(state["file_path"])
            return {**state, "parsed": parsed}

        def classify_node(state: dict[str, Any]) -> dict[str, Any]:
            return {**state, "parsed": self.section_classifier.run(state["parsed"])}

        def clause_node(state: dict[str, Any]) -> dict[str, Any]:
            return {**state, "parsed": self.clause_extractor.run(state["parsed"])}

        def risk_node(state: dict[str, Any]) -> dict[str, Any]:
            return {**state, "risks": self.risk_scanner.run(state["parsed"].text, state["project_id"])}

        def tech_node(state: dict[str, Any]) -> dict[str, Any]:
            return {
                **state,
                "requirements": self.tech_param_extractor.run(state["parsed"].text, state["project_id"]),
            }

        def product_node(state: dict[str, Any]) -> dict[str, Any]:
            return {
                **state,
                "deviations": self.product_matcher.run(state["requirements"], state["materials"]),
            }

        def judge_node(state: dict[str, Any]) -> dict[str, Any]:
            deviations = self.deviation_judge.run(state["deviations"])
            return {
                **state,
                "deviations": deviations,
                "result": WorkflowResult(
                    parsed=state["parsed"],
                    risks=state["risks"],
                    requirements=state["requirements"],
                    deviations=deviations,
                ),
            }

        try:
            graph = StateGraph(dict)
            graph.add_node("document_parser", parse_node)
            graph.add_node("section_classifier", classify_node)
            graph.add_node("clause_extractor", clause_node)
            graph.add_node("risk_scan", risk_node)
            graph.add_node("tech_param_extract", tech_node)
            graph.add_node("product_match", product_node)
            graph.add_node("deviation_judge", judge_node)
            graph.set_entry_point("document_parser")
            graph.add_edge("document_parser", "section_classifier")
            graph.add_edge("section_classifier", "clause_extractor")
            graph.add_edge("clause_extractor", "risk_scan")
            graph.add_edge("risk_scan", "tech_param_extract")
            graph.add_edge("tech_param_extract", "product_match")
            graph.add_edge("product_match", "deviation_judge")
            graph.add_edge("deviation_judge", END)
            return graph.compile()
        except Exception:
            return None


def _dedupe_risks(items: list[RiskItem]) -> list[RiskItem]:
    seen: set[tuple[int | None, str]] = set()
    result: list[RiskItem] = []
    for item in items:
        key = (item.source_page, item.source_text[:120])
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _dedupe_requirements(items: list[TechRequirement]) -> list[TechRequirement]:
    seen: set[tuple[int | None, str, float, str]] = set()
    result: list[TechRequirement] = []
    for item in items:
        key = (item.source_page, item.parameter_name, item.required_value, item.unit)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result
