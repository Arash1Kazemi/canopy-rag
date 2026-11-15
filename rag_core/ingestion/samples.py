"""Make DOCX and simple PDF copies of Markdown documents, with the standard library only.

They are test files for ingestion. They are simpler than files saved by Word or LibreOffice (one font, no
images), so real files made with those programs are still needed: see docs/team_plan.md, Teammate C.
"""
import re
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t#]*$")

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>"""
RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""
DOC_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""
NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def _styles():
    heads = "".join(f'<w:style w:type="paragraph" w:styleId="Heading{i}"><w:name w:val="heading {i}"/>'
                    f'<w:basedOn w:val="Normal"/><w:pPr><w:outlineLvl w:val="{i - 1}"/></w:pPr></w:style>' for i in range(1, 7))
    return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles {NS}>'
            f'<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>{heads}</w:styles>')


def _paragraph(text, style=None):
    ppr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    return f'<w:p>{ppr}<w:r><w:t xml:space="preserve">{escape(text)}</w:t></w:r></w:p>'


def _table(rows):
    body = "".join("<w:tr>" + "".join(f"<w:tc>{_paragraph(c)}</w:tc>" for c in row) + "</w:tr>" for row in rows)
    return f"<w:tbl>{body}</w:tbl>"


def markdown_to_docx(markdown, out_path):
    """Headings become Heading styles, '| a | b |' lines become a table, other lines become paragraphs."""
    blocks, table = [], []
    for line in markdown.split("\n"):
        if line.strip().startswith("|") and line.strip().endswith("|"):
            cells = [c.strip() for c in line.strip()[1:-1].split("|")]
            if not all(re.fullmatch(r":?-{3,}:?", c) for c in cells):   # skip the |---|---| line
                table.append(cells)
            continue
        if table:
            blocks.append(_table(table))
            table = []
        m = HEADING.match(line)
        if m:
            blocks.append(_paragraph(m.group(2), f"Heading{len(m.group(1))}"))
        elif line.strip():
            blocks.append(_paragraph(line.strip()))
    if table:
        blocks.append(_table(table))
    document = f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document {NS}><w:body>{"".join(blocks)}</w:body></w:document>'
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", RELS)
        z.writestr("word/_rels/document.xml.rels", DOC_RELS)
        z.writestr("word/document.xml", document)
        z.writestr("word/styles.xml", _styles())
    return out_path


def _pdf_string(text):
    safe = text.encode("latin-1", "replace").decode("latin-1")
    return "(" + safe.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") + ")"


def text_to_pdf(text, out_path, lines_per_page=48, width=95):
    """A plain PDF with a real text layer (Helvetica, 10 pt). Long lines are wrapped at `width` characters."""
    lines = []
    for line in text.split("\n"):
        line = line.rstrip()
        while len(line) > width:
            cut = line.rfind(" ", 0, width)
            cut = cut if cut > 0 else width
            lines.append(line[:cut])
            line = line[cut:].lstrip()
        lines.append(line)
    pages = [lines[i:i + lines_per_page] for i in range(0, len(lines), lines_per_page)] or [[""]]
    objects = ["<< /Type /Catalog /Pages 2 0 R >>", None, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids = []
    for page in pages:
        stream = "BT /F1 10 Tf 12 TL 50 790 Td " + " ".join(f"{_pdf_string(l)} Tj T*" for l in page) + " ET"
        objects.append(f"<< /Length {len(stream.encode('latin-1'))} >>\nstream\n{stream}\nendstream")
        content_id = len(objects)
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> >> "
                       f"/Contents {content_id} 0 R >>")
        kids.append(f"{len(objects)} 0 R")
    objects[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(kids)} >>"
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n{body}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("latin-1")
    out += "".join(f"{o:010d} 00000 n \n" for o in offsets).encode("latin-1")
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("latin-1")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(bytes(out))
    return out_path
