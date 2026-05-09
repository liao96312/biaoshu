from __future__ import annotations

import re
from pathlib import Path

from app.models import Project, RiskItem


def export_risk_report_pdf(path: str | Path, project: Project, risks: list[RiskItem]) -> Path:
    lines = [
        "废标风险检查报告",
        f"项目：{project.name}",
        f"招标：{project.tender_name}",
        f"风险总数：{len(risks)}",
        "",
    ]
    for index, risk in enumerate(risks, start=1):
        lines.extend(
            [
                f"{index}. [{risk.severity.value}] {risk.risk_type}",
                f"要求：{risk.requirement}",
                f"来源：第 {risk.source_page or '-'} 页 / {risk.source_section or '-'}",
                f"原文：{risk.source_text}",
                f"建议：{risk.suggestion}",
                f"状态：{risk.status.value}",
                "",
            ]
        )
    return export_text_pdf(path, lines)


def export_bid_outline_pdf(path: str | Path, project: Project, outline: list[dict]) -> Path:
    lines = [
        "投标文件目录",
        f"项目：{project.name}",
        f"招标：{project.tender_name}",
        "",
    ]
    for section in outline:
        lines.append(f"{section.get('code')}. {section.get('title')}")
        for index, item in enumerate(section.get("items", []), start=1):
            lines.append(
                f"{section.get('code')}.{index} {item.get('title')} | {item.get('status')} | {item.get('notes')}"
            )
        lines.append("")
    return export_text_pdf(path, lines)


def export_text_pdf(path: str | Path, lines: list[str]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    pages = _paginate(lines)
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"",
        b"<< /Type /Font /Subtype /Type0 /BaseFont /STSong-Light /Encoding /UniGB-UCS2-H /DescendantFonts [4 0 R] >>",
        b"<< /Type /Font /Subtype /CIDFontType0 /BaseFont /STSong-Light /CIDSystemInfo << /Registry (Adobe) /Ordering (GB1) /Supplement 2 >> /FontDescriptor 5 0 R >>",
        b"<< /Type /FontDescriptor /FontName /STSong-Light /Flags 4 /FontBBox [0 -200 1000 900] /ItalicAngle 0 /Ascent 880 /Descent -120 /CapHeight 700 /StemV 80 >>",
    ]
    page_refs: list[int] = []
    for page_lines in pages:
        page_obj = len(objects) + 1
        content_obj = page_obj + 1
        page_refs.append(page_obj)
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> >> /Contents {content_obj} 0 R >>".encode(
                "ascii"
            )
        )
        stream = _content_stream(page_lines)
        objects.append(b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream")
    objects[1] = f"<< /Type /Pages /Kids [{' '.join(f'{ref} 0 R' for ref in page_refs)}] /Count {len(page_refs)} >>".encode(
        "ascii"
    )
    target.write_bytes(_build_pdf(objects))
    return target


def _paginate(lines: list[str]) -> list[list[str]]:
    wrapped: list[str] = []
    for line in lines:
        wrapped.extend(_wrap(line, 46) if line else [""])
    pages = [wrapped[index : index + 48] for index in range(0, len(wrapped), 48)]
    return pages or [[""]]


def _wrap(text: str, width: int) -> list[str]:
    chunks: list[str] = []
    current = ""
    current_width = 0
    for char in re.sub(r"\s+", " ", text).strip():
        char_width = 2 if ord(char) > 127 else 1
        if current and current_width + char_width > width:
            chunks.append(current)
            current = char
            current_width = char_width
        else:
            current += char
            current_width += char_width
    return chunks or [""]


def _content_stream(lines: list[str]) -> bytes:
    commands = ["BT", "/F1 11 Tf", "50 790 Td", "15 TL"]
    for line in lines:
        commands.append(f"<{line.encode('utf-16-be').hex().upper()}> Tj")
        commands.append("T*")
    commands.append("ET")
    return "\n".join(commands).encode("ascii")


def _build_pdf(objects: list[bytes]) -> bytes:
    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, payload in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode("ascii"))
        output.extend(payload)
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return bytes(output)
