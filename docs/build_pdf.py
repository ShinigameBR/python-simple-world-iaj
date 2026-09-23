"""Converte docs/solucao.md em docs/solucao.pdf usando reportlab.

Suporta cabeçalhos, parágrafos, listas, tabelas, blocos de código,
negrito/itálico/código inline e imagens (screenshots). Fonte registrada:
Segoe UI (Windows) para cobertura Unicode completa.

Uso: python docs/build_pdf.py
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    Image,
    ListFlowable,
    ListItem,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).parent.parent
SRC = ROOT / "docs" / "solucao.md"
OUT = ROOT / "docs" / "solucao.pdf"
SCREENSHOTS = ROOT / "docs" / "screenshots"

# ----------------------------------------------------------------------
# Fontes (Windows: Segoe UI; senão, usa Helvetica padrão)
# ----------------------------------------------------------------------
FONT = "Helvetica"
FONT_BOLD = "Helvetica-Bold"
FONT_ITALIC = "Helvetica-Oblique"
FONT_MONO = "Courier"
BODY_SIZE = 9.5

if os.path.exists(r"C:\Windows\Fonts\segoeui.ttf"):
    pdfmetrics.registerFont(TTFont("SegoeUI", r"C:\Windows\Fonts\segoeui.ttf"))
    pdfmetrics.registerFont(TTFont("SegoeUI-Bold", r"C:\Windows\Fonts\segoeuib.ttf"))
    pdfmetrics.registerFont(TTFont("SegoeUI-Italic", r"C:\Windows\Fonts\segoeuii.ttf"))
    pdfmetrics.registerFont(TTFont("SegoeUI-SemiBold", r"C:\Windows\Fonts\seguisb.ttf"))
    FONT = "SegoeUI"
    FONT_BOLD = "SegoeUI-Bold"
    FONT_ITALIC = "SegoeUI-Italic"
if os.path.exists(r"C:\Windows\Fonts\consola.ttf"):
    pdfmetrics.registerFont(TTFont("Consola", r"C:\Windows\Fonts\consola.ttf"))
    FONT_MONO = "Consola"


def st(name, **kw):
    base = dict(fontName=FONT, fontSize=BODY_SIZE, leading=13.5,
                spaceAfter=5, textColor=colors.HexColor("#1a1a1a"))
    base.update(kw)
    return ParagraphStyle(name, **base)


S_H1 = st("h1", fontName=FONT_BOLD, fontSize=19, leading=24, spaceAfter=8,
          textColor=colors.HexColor("#0f4c75"))
S_H2 = st("h2", fontName=FONT_BOLD, fontSize=14, leading=18, spaceBefore=12,
          spaceAfter=6, textColor=colors.HexColor("#125c8f"))
S_H3 = st("h3", fontName=FONT_BOLD, fontSize=11.5, leading=15, spaceBefore=9,
          spaceAfter=4, textColor=colors.HexColor("#1a6aa5"))
S_H4 = st("h4", fontName=FONT_BOLD, fontSize=10, leading=13, spaceBefore=6,
          textColor=colors.HexColor("#333333"))
S_BODY = st("body")
S_CODE = st("code", fontName=FONT_MONO, fontSize=8.3, leading=11,
            backColor=colors.HexColor("#f2f3f7"), borderPadding=6,
            leftIndent=8, spaceBefore=4, spaceAfter=6)
S_CELL = st("cell", fontSize=8.3, leading=11, spaceAfter=0)
S_CELLH = st("cellh", fontName=FONT_BOLD, fontSize=8.3, leading=11, spaceAfter=0)
S_DIM = st("dim", fontSize=8, textColor=colors.HexColor("#666666"))
S_TITLE = st("title", fontName=FONT_BOLD, fontSize=22, leading=28, spaceAfter=2)
S_SUB = st("sub", fontSize=10.5, leading=14, textColor=colors.HexColor("#444444"))


# ----------------------------------------------------------------------
# Markdown inline -> markup do Paragraph
# ----------------------------------------------------------------------
def escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def inline(text: str) -> str:
    t = escape(text)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t, flags=re.S)
    t = re.sub(r"`(.+?)`", r'<font face="%s">\1</font>' % FONT_MONO, t, flags=re.S)
    t = re.sub(r"\*(.+?)\*", r"<i>\1</i>", t, flags=re.S)

    def link(m):
        label, url = m.group(1), m.group(2)
        return f'{label} <font color="#6b6b6b">{url}</font>'

    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, t)
    return t


# ----------------------------------------------------------------------
# Parser linha-a-linha
# ----------------------------------------------------------------------
def _is_table_sep(line: str) -> bool:
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", c) for c in cells)


def build_flowables(lines: list[str], doc_path: Path):
    flow: list = []
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if not line.strip():
            i += 1
            continue

        # cabeçalho
        hm = re.match(r"^(#{1,6})\s+(.*)$", line)
        if hm:
            level = len(hm.group(1))
            style = {1: S_H1, 2: S_H2, 3: S_H3, 4: S_H4}.get(level, S_H4)
            flow.append(Paragraph(inline(hm.group(2)), style))
            i += 1
            continue

        # bloco de código
        if line.strip().startswith("```"):
            i += 1
            code_lines = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1  # fecha o bloco
            flow.append(Preformatted("\n".join(code_lines), S_CODE))
            continue

        # tabela
        if line.strip().startswith("|") and i + 1 < len(lines) and _is_table_sep(lines[i + 1]):
            header = [c.strip() for c in line.strip().strip("|").split("|")]
            rows = []
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                rows.append(cells)
                i += 1
            table = _make_table(header, rows)
            if table:
                flow.append(table)
                flow.append(Spacer(1, 6))
            continue

        # regra horizontal
        if re.fullmatch(r"-{3,}\s*", line):
            flow.append(HRFlowable(width="100%", thickness=0.7,
                                   color=colors.HexColor("#cccccc"),
                                   spaceBefore=4, spaceAfter=6))
            i += 1
            continue

        # lista (não ordenada / ordenada)
        um = re.match(r"^\s*[-*]\s+(.*)$", line)
        om = re.match(r"^\s*(\d+)\.\s+(.*)$", line)
        if um or om:
            items = []
            while i < len(lines):
                ln = lines[i].rstrip()
                u2 = re.match(r"^\s*[-*]\s+(.*)$", ln)
                o2 = re.match(r"^\s*(\d+)\.\s+(.*)$", ln)
                if u2 or o2:
                    num = o2.group(1) if o2 else "•"
                    items.append((num, (u2 or o2).group(1)))
                    i += 1
                else:
                    break
            if om:
                lis = [ListItem(Paragraph(inline(txt), S_BODY), leftIndent=16,
                                value=num) for num, txt in items]
                flow.append(ListFlowable(lis, bulletType="1", bulletFontName=FONT,
                                         bulletFontSize=BODY_SIZE, start=1,
                                         leftIndent=10))
            else:
                lis = [ListItem(Paragraph(inline(txt), S_BODY), leftIndent=16,
                                value="•") for _, txt in items]
                flow.append(ListFlowable(lis, bulletType="bullet",
                                         bulletFontName=FONT, bulletFontSize=9,
                                         leftIndent=10))
            continue

        # parágrafo simples
        buf = [line]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(r"^(#{1,6}\s|```|-\s|\d+\.\s|.*\|)", lines[i]):
            buf.append(lines[i].rstrip())
            i += 1
        flow.append(Paragraph(inline(" ".join(buf).replace("<br/>", "<br/>")), S_BODY))

    return flow


def _make_table(header: list[str], rows: list[list[str]]):
    if not header:
        return None
    cols = len(header)
    data = [[Paragraph(inline(h), S_CELLH) for h in header]]
    for row in rows:
        row = row + [""] * (cols - len(row))
        data.append([Paragraph(inline(c), S_CELL) for c in row[:cols]])

    usable = (210 * mm) - 2 * 18 * mm
    widths = [usable / cols] * cols
    table = Table(data, colWidths=widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#125c8f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#9aa6b2")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#eef2f6")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


# ----------------------------------------------------------------------
def main():
    text = SRC.read_text(encoding="utf-8").splitlines()

    doc = SimpleDocTemplate(
        str(OUT), pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=16 * mm, bottomMargin=16 * mm,
        title="Representação do Mundo - Solução", author="Simple World",
    )

    story: list = []
    story.append(Paragraph("Atividade Prática: Representação do Mundo de um Jogo Simples", S_TITLE))
    story.append(Paragraph("IA para Jogos I - Solução desenvolvida em Python (pygame)", S_SUB))
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1.2, color=colors.HexColor("#125c8f"),
                            spaceAfter=10))

    story.extend(build_flowables(text, SRC))

    # Screenshots
    story.append(Spacer(1, 14))
    story.append(Paragraph("Apêndice - Screenshots da solução", S_H2))
    for name, cap in (("menu.png", "Tela inicial (menu)"),
                      ("play.png", "Jogando: viewport, áreas ativas e entidades"),
                      ("paused.png", "Tela pausada")):
        path = SCREENSHOTS / name
        if path.exists():
            img = Image(str(path), width=140 * mm, height=78.75 * mm)
            story.append(img)
            story.append(Paragraph(f"<i>{cap}</i>", S_DIM))
            story.append(Spacer(1, 8))

    doc.build(story)
    print(f"PDF gerado: {OUT}")


if __name__ == "__main__":
    main()