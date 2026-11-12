"""Generate synthetic EOM examples without reading any student documents.

The manifest describes intended automatic-rule outcomes, not results from a
checker. Applicable M01–M08 checks remain manual, including for good.docx.
"""

import argparse
import json
import struct
import sys
import tempfile
import zlib
from dataclasses import asdict, dataclass
from io import BytesIO
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION_START
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm, Pt

from oformleno.ruleset import Ruleset, load_ruleset

BODY_STYLE = "ЕОМ: Основний"
BODY_BASE_STYLE = "ЕОМ: Базовий текст"
HEADING_BASE_STYLE = "ЕОМ: Базовий структурний заголовок"
CELL_STYLE = "ЕОМ: Таблиця ліва"
ALIGNMENTS = {
    "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
    "center": WD_ALIGN_PARAGRAPH.CENTER,
    "left": WD_ALIGN_PARAGRAPH.LEFT,
}


@dataclass(frozen=True)
class FixtureCase:
    description: str
    error_rules: tuple[str, ...] = ()
    manual_rules: tuple[str, ...] = ()


CASES = {
    "good": FixtureCase("Погоджений профіль ЕОМ; ручний перелік залишається застосовним."),
    "bad_r01": FixtureCase("Ширина сторінки 190 мм замість 210 мм.", ("R01",)),
    "bad_r02": FixtureCase("Ліве поле 20 мм замість 25 мм.", ("R02",)),
    "bad_r03": FixtureCase("Один фрагмент основного тексту має шрифт Calibri.", ("R03",)),
    "bad_r04": FixtureCase("Один фрагмент основного тексту має розмір 12 пт.", ("R04",)),
    "bad_r05": FixtureCase("Один абзац основного тексту має одинарний інтервал.", ("R05",)),
    "bad_r06": FixtureCase("Структурний заголовок вирівняний по центру.", ("R06",)),
    "bad_r07": FixtureCase("Перед вступом явно вимкнено розрив сторінки.", ("R07",)),
    "bad_r08": FixtureCase("Перший підпис рисунка має розмір 14 пт замість 12 пт.", ("R08",)),
    "bad_r09": FixtureCase("У першому підписі таблиці явно вимкнено курсив.", ("R09",)),
    "bad_r10": FixtureCase("Звичайний верхній колонтитул вирівняний по центру.", ("R10",)),
    "good_page_break": FixtureCase("Явний розрив перед вступом замість успадкованого."),
    "good_section_break": FixtureCase("Вступ після розриву секції з нової сторінки."),
    "good_simple_fields": FixtureCase("Прості поля Word замість складених полів."),
    "bad_r03_hansi": FixtureCase("Лише кириличний шрифтовий набір має Calibri.", ("R03",)),
    "bad_r05_exact": FixtureCase("Точно 21 пт замість кратного інтервалу 1,5.", ("R05",)),
    "bad_r10_first_page": FixtureCase("На першій сторінці є верхній колонтитул.", ("R10",)),
    "manual_role": FixtureCase(
        "Довільний стиль ЕОМ не доводить роль основного тексту.",
        manual_rules=("R03", "R04", "R05"),
    ),
    "manual_inheritance": FixtureCase(
        "Фрагмент посилається на відсутній символьний стиль.", manual_rules=("R03", "R04")
    ),
    "manual_fields": FixtureCase(
        "У перших підписах не вдається розібрати перемикач поля SEQ.",
        manual_rules=("R08", "R09"),
    ),
}


def _child(parent, tag, **attributes):
    element = OxmlElement("w:" + tag)
    for key, value in attributes.items():
        element.set(qn("w:" + key), str(value))
    parent.append(element)
    return element


def _font(font, name, size_pt):
    font.name, font.size = name, Pt(size_pt)
    fonts = font._element.get_or_add_rPr().rFonts
    # Clear template theme references so literal names have no competing source.
    fonts.attrib.clear()
    for slot in ("ascii", "hAnsi", "eastAsia", "cs"):
        fonts.set(qn("w:" + slot), name)


def _style(document, name, base="Normal"):
    style = document.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
    style.base_style = document.styles[base]
    return style


def _styles(document, ruleset):
    params = {rule.id: rule.params for rule in ruleset.rules}
    manual = {check.id: check.params for check in ruleset.manual_checks}
    body = _style(document, BODY_BASE_STYLE)
    _font(body.font, params["R03"]["font"], params["R04"]["size_pt"])
    body.paragraph_format.line_spacing = params["R05"]["line_spacing"]
    body.paragraph_format.alignment = ALIGNMENTS[manual["M02"]["align"]]
    body.paragraph_format.first_line_indent = Mm(manual["M02"]["indent_mm"])
    body.paragraph_format.space_before = Pt(0)
    body.paragraph_format.space_after = Pt(0)
    _style(document, BODY_STYLE, BODY_BASE_STYLE)

    heading = _style(document, HEADING_BASE_STYLE, BODY_BASE_STYLE)
    _font(heading.font, params["R06"]["font"], params["R06"]["size_pt"])
    heading.font.all_caps = params["R06"]["uppercase"]
    heading.font.bold = params["R06"]["bold"]
    heading.paragraph_format.line_spacing = params["R06"]["line_spacing"]
    heading.paragraph_format.alignment = ALIGNMENTS[params["R06"]["align"]]
    heading.paragraph_format.first_line_indent = Mm(0)
    heading.paragraph_format.page_break_before = params["R07"]["start_on_new_page"]
    heading.paragraph_format.keep_with_next = True
    _style(document, params["R06"]["style"], HEADING_BASE_STYLE)

    chapter = document.styles["Heading 1"]
    chapter.base_style = body
    _font(chapter.font, params["R03"]["font"], params["R04"]["size_pt"])
    chapter.paragraph_format.first_line_indent = Mm(0)
    chapter.paragraph_format.line_spacing = params["R05"]["line_spacing"]

    for rule_id in ("R08", "R09", "R10"):
        values = params[rule_id]
        style = _style(document, values["style"], BODY_BASE_STYLE)
        _font(style.font, values["font"], values["size_pt"])
        style.font.bold = values.get("bold", False)
        style.font.italic = values.get("italic", False)
        style.paragraph_format.alignment = (
            WD_ALIGN_PARAGRAPH.RIGHT if rule_id == "R10" else ALIGNMENTS[values["align"]]
        )
        style.paragraph_format.first_line_indent = Mm(0)
        style.paragraph_format.line_spacing = values.get("line_spacing", 1.5)
        style.paragraph_format.keep_with_next = values.get("keep_with_next", False)

    cells = _style(document, CELL_STYLE, BODY_BASE_STYLE)
    cell_params = manual["M03"]["cells"]
    _font(cells.font, cell_params["font"], cell_params["size_pt"])
    cells.paragraph_format.line_spacing = cell_params["line_spacing"]
    cells.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
    cells.paragraph_format.first_line_indent = Mm(0)


def _numbered_chapters(document):
    numbering = document.part.numbering_part.element
    abstract_id = (
        max(int(node.get(qn("w:abstractNumId"))) for node in numbering.findall(qn("w:abstractNum")))
        + 1
    )
    abstract = OxmlElement("w:abstractNum")
    abstract.set(qn("w:abstractNumId"), str(abstract_id))
    _child(abstract, "multiLevelType", val="singleLevel")
    level = _child(abstract, "lvl", ilvl=0)
    _child(level, "start", val=1)
    _child(level, "numFmt", val="decimal")
    _child(level, "pStyle", val=document.styles["Heading 1"].style_id)
    _child(level, "lvlText", val="%1")
    numbering.insert_element_before(abstract, "w:num", "w:numIdMacAtCleanup")
    number = numbering.add_num(abstract_id)
    ppr = document.styles["Heading 1"].element.get_or_add_pPr()
    numpr = ppr.get_or_add_numPr()
    _child(numpr, "ilvl", val=0)
    _child(numpr, "numId", val=number.numId)


def _field(paragraph, instruction, cached, *, simple=False):
    if simple:
        field = _child(paragraph._p, "fldSimple", instr=" " + instruction + " ")
        _child(_child(field, "r"), "t").text = str(cached)
        return
    _child(paragraph.add_run()._r, "fldChar", fldCharType="begin")
    code = _child(paragraph.add_run()._r, "instrText")
    code.set(qn("xml:space"), "preserve")
    code.text = " " + instruction + " "
    _child(paragraph.add_run()._r, "fldChar", fldCharType="separate")
    paragraph.add_run(str(cached))
    _child(paragraph.add_run()._r, "fldChar", fldCharType="end")


def _picture():
    """An original 8x8 PNG made from code, requiring no stored bitmap or dependency."""

    def chunk(kind, data):
        return (
            struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        )

    header = struct.pack(">IIBBBBB", 8, 8, 8, 2, 0, 0, 0)
    pixels = (b"\0" + b"\x40\x80\xc0" * 8) * 8
    return BytesIO(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(pixels))
        + chunk(b"IEND", b"")
    )


def _caption(document, values, chapter, ordinal, simple):
    caption = document.add_paragraph(style=values["style"])
    caption.add_run(values["label"] + " ")
    numbering = values["numbering"]
    _field(caption, f"STYLEREF {numbering['chapter_heading_level']} \\s", chapter, simple=simple)
    caption.add_run(numbering["separator"])
    instruction = (
        f"SEQ {numbering['sequence_name']} \\* ARABIC \\s {numbering['reset_at_heading_level']}"
    )
    _field(caption, instruction, ordinal, simple=simple)
    caption.add_run(" Згенерований приклад")
    return caption


def _base_document(ruleset, simple):
    document = Document()
    document.core_properties.author = ""
    document.core_properties.last_modified_by = ""
    document.core_properties.title = "Синтетична робота для тестування"
    _styles(document, ruleset)
    _numbered_chapters(document)
    params = {rule.id: rule.params for rule in ruleset.rules}
    manual = {check.id: check.params for check in ruleset.manual_checks}
    section = document.sections[0]
    section.page_width = Mm(params["R01"]["width_mm"])
    section.page_height = Mm(params["R01"]["height_mm"])
    for edge in ("left", "right", "top", "bottom"):
        setattr(section, edge + "_margin", Mm(params["R02"][edge + "_mm"]))
    section.header_distance = Mm(manual["M07"]["header_distance_mm"])
    section.footer_distance = Mm(manual["M07"]["footer_distance_mm"])
    section.different_first_page_header_footer = True
    document.settings.odd_and_even_pages_header_footer = True
    # Explicit empty first header, separate from the ordinary/even PAGE fields.
    section.first_page_header.is_linked_to_previous = False
    for header in (section.header, section.even_page_header):
        paragraph = header.paragraphs[0]
        paragraph.style = document.styles[params["R10"]["style"]]
        _field(paragraph, "PAGE", 2, simple=simple)

    opening = document.add_paragraph("Згенерований текст перед вступом. Latin.", BODY_STYLE)
    introduction = document.add_paragraph("Вступ", params["R06"]["style"])
    document.add_paragraph("Згенерований основний текст після вступу. Latin.", BODY_STYLE)
    figures, tables = [], []
    for chapter, count in ((1, 2), (2, 1)):
        document.add_paragraph(f"Згенерований розділ {chapter}", "Heading 1")
        document.add_paragraph("Згенерований основний текст розділу. Latin.", BODY_STYLE)
        # Unequal interleaving catches a single shared counter for figures/tables.
        for ordinal in range(1, count + 1):
            picture = document.add_paragraph(style=BODY_STYLE)
            picture.add_run().add_picture(_picture(), width=Mm(10))
            figures.append(_caption(document, params["R08"], chapter, ordinal, simple))
        for ordinal in range(1, count + 1):
            tables.append(_caption(document, params["R09"], chapter, ordinal, simple))
            table = document.add_table(rows=2, cols=2)
            for row_index, row in enumerate(table.rows):
                for cell in row.cells:
                    paragraph = cell.paragraphs[0]
                    paragraph.style = document.styles[CELL_STYLE]
                    paragraph.add_run("Заголовок" if row_index == 0 else "Значення").bold = (
                        row_index == 0
                    )
    document.add_paragraph("Висновки", params["R06"]["style"])
    document.add_paragraph("Згенерований завершальний текст. Latin.", BODY_STYLE)
    return document, opening, introduction, figures, tables


def make_fixture(name: str, ruleset: Ruleset | None = None):
    """Build one independent synthetic document; callers save it in tmp_path."""
    if name not in CASES:
        raise ValueError("Невідомий синтетичний приклад.")
    ruleset = ruleset or load_ruleset()
    document, body, heading, figures, tables = _base_document(ruleset, name == "good_simple_fields")
    run = body.runs[0]
    match name:
        case "bad_r01":
            document.sections[0].page_width = Mm(190)
        case "bad_r02":
            document.sections[0].left_margin = Mm(20)
        case "bad_r03":
            _font(run.font, "Calibri", 14)
        case "bad_r04":
            run.font.size = Pt(12)
        case "bad_r05":
            body.paragraph_format.line_spacing = 1.0
        case "bad_r06":
            heading.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
        case "bad_r07":
            heading.paragraph_format.page_break_before = False
        case "bad_r08":
            for fragment in figures[0].runs:
                fragment.font.size = Pt(14)
        case "bad_r09":
            for fragment in tables[0].runs:
                fragment.italic = False
        case "bad_r10":
            document.sections[0].header.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        case "good_page_break":
            heading.paragraph_format.page_break_before = False
            body.add_run().add_break(WD_BREAK.PAGE)
        case "good_section_break":
            heading.paragraph_format.page_break_before = False
            section = document.add_section(WD_SECTION_START.NEW_PAGE)
            heading._p.addprevious(document.paragraphs[-1]._p)
            section.different_first_page_header_footer = False
        case "bad_r03_hansi":
            _font(run.font, "Times New Roman", 14)
            run._r.rPr.rFonts.set(qn("w:hAnsi"), "Calibri")
        case "bad_r05_exact":
            body.paragraph_format.line_spacing = Pt(21)
        case "bad_r10_first_page":
            paragraph = document.sections[0].first_page_header.paragraphs[0]
            paragraph.style = document.styles[
                next(rule.params["style"] for rule in ruleset.rules if rule.id == "R10")
            ]
            _field(paragraph, "PAGE", 1)
        case "manual_role":
            style = _style(document, "ЕОМ: Невизначений елемент")
            _font(style.font, "Calibri", 12)
            style.paragraph_format.line_spacing = 1.0
            document.add_paragraph("Згенерований елемент невідомої ролі. Latin.", style)
        case "manual_inheritance":
            _child(run._r.get_or_add_rPr(), "rStyle", val="MissingSyntheticStyle")
        case "manual_fields":
            for caption in (figures[0], tables[0]):
                for code in caption._p.iter(qn("w:instrText")):
                    if code.text.strip().startswith("SEQ "):
                        code.text = " " + code.text.strip().rsplit(" ", 1)[0] + " "
    return document


def generate_fixtures(output_dir: Path) -> dict[str, Path]:
    """Write packages and an expectation manifest without replacing existing files."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {name: output_dir / (name + ".docx") for name in CASES}
    manifest_path = output_dir / "manifest.json"
    if any(path.exists() for path in (*paths.values(), manifest_path)):
        raise FileExistsError("Синтетичні приклади вже існують. Виберіть іншу тимчасову теку.")
    ruleset = load_ruleset()
    for name, path in paths.items():
        make_fixture(name, ruleset).save(path)
    manifest = {
        "ruleset": ruleset.id,
        "document_type": "laboratory_report",
        "note": "Очікування для автоматичних правил; застосовні M01–M08 залишаються ручними.",
        "cases": {path.name: asdict(CASES[name]) for name, path in paths.items()},
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return paths


def main():
    parser = argparse.ArgumentParser(description="Створення синтетичних прикладів DOCX профілю ЕОМ")
    parser.add_argument(
        "output_dir", nargs="?", type=Path, help="Нова тимчасова тека для прикладів"
    )
    args = parser.parse_args()
    directory = args.output_dir or Path(tempfile.mkdtemp(prefix="oformleno-fixtures-"))
    try:
        paths = generate_fixtures(directory)
    except OSError:
        print(
            "Не вдалося записати приклади. Виберіть нову доступну тимчасову теку.", file=sys.stderr
        )
        return 1
    print(f"Створено {len(paths)} синтетичних документів і manifest.json: {directory}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
