from __future__ import annotations

import re

from app.services.parser import iter_page_chunks


def extract_clauses(text: str) -> list[dict]:
    clauses: list[dict] = []
    for page, chunk in iter_page_chunks(text):
        section = None
        for line in chunk.splitlines():
            clean = _compact(line, 320)
            if not clean:
                continue
            if _looks_like_section(clean):
                section = clean
                continue
            for sentence in _split_sentences(clean):
                clause_type, keywords = _classify_clause(sentence)
                if clause_type == "other" and len(sentence) < 12:
                    continue
                clauses.append(
                    {
                        "id": f"C-{len(clauses) + 1:04d}",
                        "source_page": page,
                        "source_section": section,
                        "clause_type": clause_type,
                        "keywords": keywords,
                        "clause_text": sentence,
                    }
                )
    return clauses


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[。；;])|\n+", text)
    return [_compact(part, 320) for part in parts if part.strip()]


def _looks_like_section(line: str) -> bool:
    if len(line) > 48:
        return False
    return bool(
        re.match(r"^(第[一二三四五六七八九十\d]+[章节条]|[一二三四五六七八九十\d]+[、.．])", line)
        or any(token in line for token in ["资格审查", "符合性审查", "技术要求", "商务要求", "评审办法"])
    )


def _classify_clause(sentence: str) -> tuple[str, list[str]]:
    groups = {
        "risk": ["投标无效", "废标", "否决投标", "不得偏离", "不允许负偏离", "实质性响应"],
        "material": ["须提供", "必须提供", "应提供", "证明", "证书", "报告", "保证金", "回单"],
        "technical": ["★", "参数", "容量", "转发率", "性能", "兼容", "质保", "交付周期"],
        "business": ["报价", "付款", "履约", "质保期", "有效期", "密封", "正本", "副本"],
    }
    hits_by_type: dict[str, list[str]] = {}
    for clause_type, keywords in groups.items():
        hits = [keyword for keyword in keywords if keyword in sentence]
        if hits:
            hits_by_type[clause_type] = hits
    if not hits_by_type:
        return "other", []
    for preferred in ["risk", "technical", "material", "business"]:
        if preferred in hits_by_type:
            return preferred, hits_by_type[preferred]
    clause_type, hits = next(iter(hits_by_type.items()))
    return clause_type, hits


def _compact(value: str, limit: int) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    return value if len(value) <= limit else value[: limit - 1] + "…"
