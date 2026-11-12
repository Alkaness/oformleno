"""Effective formatting from generated, saved and reopened Word packages."""

from copy import deepcopy
from io import BytesIO

import pytest
from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn
from docx.shared import Pt

from oformleno.loader import load_document
from oformleno.model import DocumentModel, LineSpacing


def child(parent, tag, **attributes):
    element = OxmlElement("w:" + tag)
    for key, value in attributes.items():
        element.set(qn("w:" + key), str(value))
    parent.append(element)
    return element


@pytest.fixture
def generated():
    document = Document()
    styles = document.styles
    for element in list(styles.element):
        styles.element.remove(element)
    defaults = child(styles.element, "docDefaults")
    rpr = child(child(defaults, "rPrDefault"), "rPr")
    child(rpr, "rFonts", ascii="Arial", hAnsi="Arial")
    child(rpr, "sz", val=20)
    ppr = child(child(defaults, "pPrDefault"), "pPr")
    child(ppr, "spacing", line=240, lineRule="auto")
    normal = styles.add_style("Normal", WD_STYLE_TYPE.PARAGRAPH)
    normal.element.set(qn("w:default"), "1")
    base = styles.add_style("Generated Base", WD_STYLE_TYPE.PARAGRAPH)
    base.base_style = normal
    assigned = styles.add_style("Generated Assigned", WD_STYLE_TYPE.PARAGRAPH)
    assigned.base_style = base
    paragraph = document.add_paragraph("Тест Latin", assigned)
    return document, paragraph, paragraph.runs[0], rpr, ppr


def reopened(document, tmp_path):
    path = tmp_path / "generated.docx"
    document.save(path)
    return DocumentModel(load_document(path))


def set_theme_font(document, name):
    part = document.part.part_related_by(RT.THEME)
    theme = parse_xml(part.blob)
    theme.find(".//" + qn("a:minorFont") + "/" + qn("a:latin")).set("typeface", name)
    output = BytesIO()
    theme.getroottree().write(output, encoding="UTF-8", xml_declaration=True)
    part._blob = output.getvalue()


@pytest.mark.parametrize(
    ("case", "font_source", "spacing_source"),
    [
        ("direct", "run", "paragraph"),
        ("character", "character_style", "paragraph_style"),
        ("paragraph", "paragraph_style", "paragraph_style"),
        ("base", "base_style", "base_style"),
        ("defaults", "doc_defaults", "doc_defaults"),
        ("theme", "doc_defaults", "doc_defaults"),
    ],
)
def test_six_inheritance_variants(generated, tmp_path, case, font_source, spacing_source):
    document, paragraph, run, rpr, ppr = generated
    if case == "direct":
        font, paragraph_format = run.font, paragraph.paragraph_format
    elif case == "character":
        run.style = document.styles.add_style("Generated Character", WD_STYLE_TYPE.CHARACTER)
        font, paragraph_format = run.style.font, paragraph.style.paragraph_format
    elif case in ("paragraph", "base"):
        style = paragraph.style if case == "paragraph" else paragraph.style.base_style
        font, paragraph_format = style.font, style.paragraph_format
    else:
        font = paragraph_format = None
        rpr.find(qn("w:sz")).set(qn("w:val"), "28")
        ppr.find(qn("w:spacing")).set(qn("w:line"), "360")
        fonts = rpr.find(qn("w:rFonts"))
        fonts.attrib.clear()
        if case == "theme":
            set_theme_font(document, "Times New Roman")
            fonts.set(qn("w:asciiTheme"), "minorHAnsi")
            fonts.set(qn("w:hAnsiTheme"), "minorHAnsi")
        else:
            fonts.set(qn("w:ascii"), "Times New Roman")
            fonts.set(qn("w:hAnsi"), "Times New Roman")
    if font is not None:
        font.name, font.size = "Times New Roman", Pt(14)
        paragraph_format.line_spacing = 1.5

    model = reopened(document, tmp_path)
    paragraph = model.paragraphs[0]
    formatting = model.run_formatting(model.runs(paragraph)[0])

    assert formatting.slots.value == ("ascii", "hAnsi")
    for resolved in formatting.fonts.values():
        assert resolved.resolved and resolved.value == "Times New Roman"
        assert resolved.source == font_source
        assert resolved.theme_reference == ("minorHAnsi" if case == "theme" else None)
    assert formatting.size_pt.value == 14
    assert formatting.size_pt.source == font_source
    spacing = model.effective_line_spacing(paragraph)
    assert spacing.value == LineSpacing("multiple", 1.5)
    assert spacing.source == spacing_source


def test_character_base_overrides_paragraph_and_direct_overrides_character(generated, tmp_path):
    document, paragraph, run, *_ = generated
    paragraph.style.font.name = "Paragraph Font"
    base = document.styles.add_style("Generated Character Base", WD_STYLE_TYPE.CHARACTER)
    base.font.name, base.font.size = "Character Font", Pt(13.5)
    assigned = document.styles.add_style("Generated Character", WD_STYLE_TYPE.CHARACTER)
    assigned.base_style = base
    run.style = assigned
    second = paragraph.add_run("Другий")
    second.style = assigned
    second.font.name, second.font.size = "Direct Font", Pt(14)
    model = reopened(document, tmp_path)
    inherited, direct = model.runs(model.paragraphs[0])
    assert model.effective_font(inherited).value == "Character Font"
    assert model.effective_font(inherited).source == "base_style"
    assert model.effective_font_size(inherited).value == 13.5
    assert model.effective_font(direct).value == "Direct Font"
    assert model.effective_font_size(direct).value == 14


def test_default_paragraph_style_is_used_without_explicit_reference(generated, tmp_path):
    document, paragraph, *_ = generated
    paragraph.style = None
    document.styles["Normal"].font.name = "Default Style Font"
    document.styles["Normal"].font.size = Pt(14)
    document.styles["Normal"].paragraph_format.line_spacing = 1.5
    model = reopened(document, tmp_path)
    run = model.runs(model.paragraphs[0])[0]
    assert model.effective_font(run).value == "Default Style Font"
    assert model.effective_font_size(run).value == 14
    assert model.effective_line_spacing(model.paragraphs[0]).value.multiplier == 1.5


@pytest.mark.parametrize("direct_theme", [False, True])
def test_nearer_font_selection_wins_over_other_kind_in_lower_layer(
    generated, tmp_path, direct_theme
):
    document, _, run, rpr, _ = generated
    set_theme_font(document, "Theme Font")
    direct = child(run._r.get_or_add_rPr(), "rFonts")
    if direct_theme:
        direct.set(qn("w:hAnsiTheme"), "minorHAnsi")
    else:
        direct.set(qn("w:hAnsi"), "Direct Font")
        rpr.find(qn("w:rFonts")).attrib.clear()
        rpr.find(qn("w:rFonts")).set(qn("w:hAnsiTheme"), "minorHAnsi")
    model = reopened(document, tmp_path)
    resolved = model.effective_font(model.runs(model.paragraphs[0])[0])
    assert resolved.value == ("Theme Font" if direct_theme else "Direct Font")
    assert resolved.source == "run"


@pytest.mark.parametrize("same_name", [True, False])
def test_same_layer_theme_and_literal_must_agree(generated, tmp_path, same_name):
    document, _, run, *_ = generated
    set_theme_font(document, "Theme Font")
    child(
        run._r.get_or_add_rPr(),
        "rFonts",
        hAnsi="Theme Font" if same_name else "Other Font",
        hAnsiTheme="minorHAnsi",
    )
    model = reopened(document, tmp_path)
    resolved = model.effective_font(model.runs(model.paragraphs[0])[0])
    assert resolved.resolved == same_name
    assert resolved.value == ("Theme Font" if same_name else None)
    if not same_name:
        assert resolved.reason


@pytest.mark.parametrize(
    "theme_problem", ["missing", "invalid", "empty_facet", "unknown_reference"]
)
def test_unavailable_theme_does_not_fall_back_to_lower_font(generated, tmp_path, theme_problem):
    document, _, run, *_ = generated
    reference = "majorEastAsia" if theme_problem == "empty_facet" else "minorHAnsi"
    if theme_problem == "missing":
        relationship = next(rel for rel in document.part.rels.values() if rel.reltype == RT.THEME)
        document.part.drop_rel(relationship.rId)
    elif theme_problem == "invalid":
        document.part.part_related_by(RT.THEME)._blob = b"invalid XML"
    elif theme_problem == "unknown_reference":
        reference = "SYNTHETIC_PRIVATE_IDENTIFIER"
    child(run._r.get_or_add_rPr(), "rFonts", hAnsiTheme=reference)
    model = reopened(document, tmp_path)
    resolved = model.effective_font(model.runs(model.paragraphs[0])[0])
    assert not resolved.resolved and resolved.value is None
    assert "SYNTHETIC_PRIVATE_IDENTIFIER" not in resolved.reason


def test_ascii_and_cyrillic_font_slots_are_independent(generated, tmp_path):
    document, _, run, rpr, _ = generated
    rpr.find(qn("w:rFonts")).attrib.clear()
    child(run._r.get_or_add_rPr(), "rFonts", ascii="Latin Font")
    model = reopened(document, tmp_path)
    formatting = model.run_formatting(model.runs(model.paragraphs[0])[0])
    assert formatting.fonts["ascii"].value == "Latin Font"
    assert not formatting.fonts["hAnsi"].resolved


@pytest.mark.parametrize("problem", ["missing", "cycle", "duplicate", "wrong_type"])
def test_broken_style_chain_is_manual_and_private(generated, tmp_path, problem):
    document, paragraph, *_ = generated
    style = paragraph.style.element
    base = style.find(qn("w:basedOn"))
    if problem == "missing":
        base.set(qn("w:val"), "SYNTHETIC_PRIVATE_IDENTIFIER")
    elif problem == "cycle":
        base.set(qn("w:val"), paragraph.style.style_id)
    elif problem == "duplicate":
        document.styles.element.append(deepcopy(style))
    else:
        style.set(qn("w:type"), "character")
    model = reopened(document, tmp_path)
    run = model.runs(model.paragraphs[0])[0]
    for result in (
        model.effective_font(run),
        model.effective_font_size(run),
        model.effective_line_spacing(model.paragraphs[0]),
    ):
        assert not result.resolved and result.reason
        assert "SYNTHETIC_PRIVATE_IDENTIFIER" not in result.reason


@pytest.mark.parametrize("value", ["0", "-1", "invalid", "27.5"])
def test_invalid_direct_size_is_not_replaced_by_inherited_value(generated, tmp_path, value):
    document, _, run, *_ = generated
    child(run._r.get_or_add_rPr(), "sz", val=value)
    model = reopened(document, tmp_path)
    assert not model.effective_font_size(model.runs(model.paragraphs[0])[0]).resolved


@pytest.mark.parametrize(
    ("attributes", "expected"),
    [
        ({"line": 360, "lineRule": "auto"}, LineSpacing("multiple", 1.5)),
        ({"line": 360}, LineSpacing("multiple", 1.5)),
        ({"line": 420, "lineRule": "exact"}, LineSpacing("exact", 21)),
        ({"line": 420, "lineRule": "atLeast"}, LineSpacing("at_least", 21)),
        ({"before": 120}, LineSpacing("multiple", 1)),
    ],
)
def test_line_spacing_units_and_partial_overrides(generated, tmp_path, attributes, expected):
    document, paragraph, *_ = generated
    child(paragraph._p.get_or_add_pPr(), "spacing", **attributes)
    model = reopened(document, tmp_path)
    value = model.effective_line_spacing(model.paragraphs[0]).value
    assert value == expected
    assert (value.multiplier is None) == (expected.kind != "multiple")
    assert (value.points is None) == (expected.kind == "multiple")


@pytest.mark.parametrize(
    "attributes",
    [{"lineRule": "exact"}, {"line": -1}, {"line": "bad"}, {"line": 360, "lineRule": "unknown"}],
)
def test_unreliable_spacing_is_manual(generated, tmp_path, attributes):
    document, paragraph, *_ = generated
    child(paragraph._p.get_or_add_pPr(), "spacing", **attributes)
    model = reopened(document, tmp_path)
    assert not model.effective_line_spacing(model.paragraphs[0]).resolved


def test_paragraph_mark_formatting_does_not_style_text(generated, tmp_path):
    document, paragraph, *_ = generated
    mark = child(paragraph._p.get_or_add_pPr(), "rPr")
    child(mark, "rFonts", ascii="Mark Font", hAnsi="Mark Font")
    child(mark, "sz", val=60)
    model = reopened(document, tmp_path)
    run = model.runs(model.paragraphs[0])[0]
    assert model.effective_font(run).value == "Arial"
    assert model.effective_font_size(run).value == 10


@pytest.mark.parametrize("flag", ["cs", "rtl"])
@pytest.mark.parametrize("enabled", [True, False])
def test_complex_script_override_and_direct_false(generated, tmp_path, flag, enabled):
    document, paragraph, run, rpr, _ = generated
    child(paragraph.style.element.get_or_add_rPr(), flag)
    child(rpr, "szCs", val=32)
    rpr.find(qn("w:rFonts")).set(qn("w:cs"), "Complex Font")
    if not enabled:
        child(run._r.get_or_add_rPr(), flag, val="false")
    model = reopened(document, tmp_path)
    formatting = model.run_formatting(model.runs(model.paragraphs[0])[0])
    assert formatting.slots.value == (("cs",) if enabled else ("ascii", "hAnsi"))
    assert formatting.size_pt.value == (16 if enabled else 10)
    if enabled:
        assert formatting.fonts["cs"].value == "Complex Font"


def test_east_asian_hint_does_not_hide_known_size(generated, tmp_path):
    document, _, run, *_ = generated
    child(run._r.get_or_add_rPr(), "rFonts", hint="eastAsia", eastAsia="Other Font")
    model = reopened(document, tmp_path)
    formatting = model.run_formatting(model.runs(model.paragraphs[0])[0])
    assert not formatting.slots.resolved
    assert formatting.size_pt.value == 10


@pytest.mark.parametrize("text", ["字", "🙂"])
def test_unsupported_scripts_need_review(generated, tmp_path, text):
    document, _, run, *_ = generated
    run.text = text
    model = reopened(document, tmp_path)
    formatting = model.run_formatting(model.runs(model.paragraphs[0])[0])
    assert not formatting.slots.resolved
    assert not formatting.size_pt.resolved


def test_revision_and_foreign_document_are_not_resolved(generated, tmp_path):
    document, paragraph, run, *_ = generated
    change = child(paragraph._p, "ins")
    change.append(run._r)
    model = reopened(document, tmp_path)
    changed = model.runs(model.paragraphs[0])[0]
    foreign = Document().add_paragraph("Згенерований текст").runs[0]
    for item in (changed, foreign):
        assert not model.effective_font(item).resolved
        assert not model.effective_font_size(item).resolved


def test_main_paragraphs_and_runs_include_controls_and_hyperlinks(generated, tmp_path):
    document, paragraph, run, *_ = generated
    hyperlink = child(paragraph._p, "hyperlink")
    hyperlink.append(run._r)
    document.add_table(rows=1, cols=1).cell(0, 0).text = "Згенерована комірка"
    controlled = document.add_paragraph("Згенерований вміст")
    control = child(document.element.body, "sdt")
    child(control, "sdtContent").append(controlled._p)
    model = reopened(document, tmp_path)
    assert len(model.paragraphs) == 2
    assert len(model.runs(model.paragraphs[0])) == 1
    assert model.effective_font(model.runs(model.paragraphs[0])[0]).value == "Arial"
    assert len(model.tables) == len(model.sections) == 1
    assert not model.effective_font(model.tables[0].cell(0, 0).paragraphs[0].runs[0]).resolved


def test_missing_styles_part_is_not_created_and_source_is_unchanged(generated, tmp_path):
    document, paragraph, *_ = generated
    paragraph.style = None
    relationship = next(rel for rel in document.part.rels.values() if rel.reltype == RT.STYLES)
    document.part.drop_rel(relationship.rId)
    model = reopened(document, tmp_path)
    path = tmp_path / "generated.docx"
    original = path.read_bytes()
    before = model.document.element.xml
    relationships = tuple(model.document.part.rels)
    run = model.runs(model.paragraphs[0])[0]
    assert not model.effective_font(run).resolved
    assert not model.effective_font_size(run).resolved
    assert model.effective_line_spacing(model.paragraphs[0]).value == LineSpacing("multiple", 1)
    assert model.document.element.xml == before
    assert tuple(model.document.part.rels) == relationships
    assert not any(rel.reltype == RT.STYLES for rel in model.document.part.rels.values())
    assert path.read_bytes() == original


def test_queries_preserve_package_parts_and_input_bytes(generated, tmp_path):
    document, _, _, rpr, _ = generated
    fonts = rpr.find(qn("w:rFonts"))
    fonts.attrib.clear()
    fonts.set(qn("w:hAnsiTheme"), "minorHAnsi")
    fonts.set(qn("w:asciiTheme"), "minorHAnsi")
    model = reopened(document, tmp_path)
    path = tmp_path / "generated.docx"
    original = path.read_bytes()
    parts = {str(part.partname): part.blob for part in model.document.part.package.parts}
    for paragraph in model.paragraphs:
        model.effective_line_spacing(paragraph)
        for run in model.runs(paragraph):
            model.run_formatting(run)
    assert {str(part.partname): part.blob for part in model.document.part.package.parts} == parts
    assert path.read_bytes() == original


@pytest.mark.parametrize("numbering_enabled", [False, True])
def test_numbering_inheritance_is_not_guessed(generated, tmp_path, numbering_enabled):
    document, paragraph, *_ = generated
    numbering = child(paragraph._p.get_or_add_pPr(), "numPr")
    child(numbering, "numId", val=1 if numbering_enabled else 0)
    model = reopened(document, tmp_path)
    run = model.runs(model.paragraphs[0])[0]
    assert model.effective_font(run).resolved == (not numbering_enabled)
    assert model.effective_line_spacing(model.paragraphs[0]).resolved == (not numbering_enabled)


def test_explicit_spacing_without_rule_does_not_inherit_exact_units(generated, tmp_path):
    document, paragraph, *_ = generated
    paragraph.style.paragraph_format.line_spacing = Pt(21)
    child(paragraph._p.get_or_add_pPr(), "spacing", line=360)
    model = reopened(document, tmp_path)
    assert model.effective_line_spacing(model.paragraphs[0]).value == LineSpacing("multiple", 1.5)


def test_unsupported_story_needs_review(generated, tmp_path):
    document, *_ = generated
    document.sections[0].header.paragraphs[0].text = "Згенерований колонтитул"
    model = reopened(document, tmp_path)
    paragraph = model.sections[0].header.paragraphs[0]
    assert not model.effective_font(paragraph.runs[0]).resolved
    assert not model.effective_line_spacing(paragraph).resolved
