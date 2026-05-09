from __future__ import annotations

from html import escape
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from app.models import Project


def export_bid_outline_docx(path: str | Path, project: Project, outline: list[dict]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(target, "w", ZIP_DEFLATED) as docx:
        docx.writestr("[Content_Types].xml", CONTENT_TYPES)
        docx.writestr("_rels/.rels", RELS)
        docx.writestr("word/_rels/document.xml.rels", DOCUMENT_RELS)
        docx.writestr("word/document.xml", _document_xml(project, outline))
    return target


def _document_xml(project: Project, outline: list[dict]) -> str:
    body = [
        _paragraph("投标文件目录"),
        _paragraph(project.name),
        _paragraph(project.tender_name),
    ]
    for section in outline:
        body.append(_paragraph(f"{section.get('code')}. {section.get('title')}"))
        for index, item in enumerate(section.get("items", []), start=1):
            body.append(
                _paragraph(
                    f"{section.get('code')}.{index} {item.get('title')} | {item.get('status')} | {item.get('notes')}"
                )
            )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    {"".join(body)}
    <w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr>
  </w:body>
</w:document>"""


def _paragraph(text: str) -> str:
    return f"<w:p><w:r><w:t xml:space=\"preserve\">{escape(text)}</w:t></w:r></w:p>"


CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""

RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""

DOCUMENT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>"""
