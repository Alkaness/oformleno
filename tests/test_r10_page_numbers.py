"""R10 header selection, automatic PAGE fields and read-only formatting views."""

from io import BytesIO

import pytest
from docx import Document
from docx.enum.section import WD_SECTION_START
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, Twips
from docx.text.run import Run

from oformleno.engine import RuleEngine
from oformleno.fixer import fix_document_bytes
from oformleno.loader import load_document
from oformleno.model import DocumentModel
from oformleno.ruleset import load_ruleset


def header(document, variant="default", section=0):
    name = {"default": "header", "first": "first_page_header", "even": "even_page_header"}
    return getattr(document.sections[section], name[variant])


def field(paragraph, instruction="PAGE", *, cached="1"):
    paragraph.clear()
    element = OxmlElement("w:fldSimple")
    element.set(qn("w:instr"), instruction)
    run = paragraph.add_run(cached)
    if not cached:
        run._r.append(OxmlElement("w:t"))
    element.append(run._r)
    paragraph._p.append(element)
    return run


def result_run(paragraph):
    return next(
        Run(node, paragraph) for node in paragraph._p.iter(qn("w:r")) if Run(node, paragraph).text
    )


@pytest.mark.parametrize("case", ["good", "good_simple_fields", "good_section_break"])
def test_valid_complex_simple_and_inherited_headers(eom_fixtures, body_check, case):
    assert body_check(Document(eom_fixtures[case]), "R10") == ()


@pytest.mark.parametrize("property", ["align", "font", "size_pt"])
def test_header_format_errors_have_section_location_and_quote(eom_fixtures, body_check, property):
    document = Document(eom_fixtures["good"])
    paragraph = header(document).paragraphs[0]
    run = result_run(paragraph)
    if property == "align":
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    elif property == "font":
        run.font.name = "Calibri"
    else:
        run.font.size = Pt(14)
    findings = body_check(document, "R10")
    assert len(findings) == 1
    item = findings[0]
    assert item.severity == "error" and not item.fixable
    assert set(item.actual) == {"header", property}
    assert item.location.section == 1 and item.location.page is None
    assert item.location.excerpt is None
    rule = next(rule for rule in load_ruleset().rules if rule.id == "R10")
    assert item.quote == rule.quote
    assert item.source_id == rule.source_id


@pytest.mark.parametrize("content", ["PAGE", "literal"])
def test_first_document_header_must_be_absent(eom_fixtures, body_check, content):
    document = Document(eom_fixtures["good"])
    paragraph = header(document, "first").paragraphs[0]
    if content == "PAGE":
        field(paragraph)
    else:
        paragraph.add_run("Згенерований заголовок")
    findings = body_check(document, "R10")
    assert len(findings) == 1 and findings[0].severity == "error"
    assert findings[0].actual == {"first_page_header": "present"}


def test_title_flag_alone_does_not_hide_ordinary_first_header(eom_fixtures, body_check):
    document = Document(eom_fixtures["good"])
    document.sections[0].different_first_page_header_footer = False
    findings = body_check(document, "R10")
    assert len(findings) == 1 and findings[0].actual == {"first_page_header": "present"}


def test_inactive_even_and_first_definitions_are_ignored(eom_fixtures, body_check):
    document = Document(eom_fixtures["good"])
    document.settings.odd_and_even_pages_header_footer = False
    header(document, "even").paragraphs[0].add_run("unused").font.size = Pt(22)
    assert body_check(document, "R10") == ()
    # With titlePg disabled an unused first definition cannot create an error.
    document.sections[0].different_first_page_header_footer = False
    header(document, "first").paragraphs[0].add_run("unused")
    header(document).paragraphs[0].clear()
    findings = body_check(document, "R10")
    assert findings and all(item.severity == "manual" for item in findings)


def test_missing_first_definition_is_blank_without_creating_a_part(eom_fixtures, tmp_path):
    document = Document(eom_fixtures["good"])
    properties = document.sections[0]._sectPr
    node = next(
        n for n in properties.findall(qn("w:headerReference")) if n.get(qn("w:type")) == "first"
    )
    properties.remove(node)
    path = tmp_path / "generated.docx"
    document.save(path)
    original = path.read_bytes()
    reopened = load_document(path)
    parts = {str(part.partname): part.blob for part in reopened.part.package.parts}
    report = RuleEngine().check(reopened, load_ruleset())
    assert not [item for item in report.findings if item.rule_id == "R10"]
    assert parts == {str(part.partname): part.blob for part in reopened.part.package.parts}
    assert path.read_bytes() == original


def test_header_types_inherit_independently(eom_fixtures, body_check):
    document = Document(eom_fixtures["good"])
    document.add_section(WD_SECTION_START.NEW_PAGE)
    # The later first header inherits the empty first variant, not ordinary PAGE.
    findings = body_check(document, "R10")
    assert len(findings) == 1 and findings[0].severity == "error"
    assert findings[0].location.section == 2
    assert findings[0].actual == {"header": "first", "page_field": False}
    paragraph = header(document, "first", 1)
    paragraph.is_linked_to_previous = False
    paragraph = paragraph.paragraphs[0]
    paragraph.style = document.styles[load_ruleset().rules[9].params["style"]]
    field(paragraph)
    assert body_check(document, "R10") == ()


@pytest.mark.parametrize("kind", [WD_SECTION_START.CONTINUOUS, WD_SECTION_START.NEW_COLUMN])
def test_continuous_sections_are_manual(eom_fixtures, body_check, kind):
    document = Document(eom_fixtures["good"])
    document.add_section(kind)
    document.sections[1].different_first_page_header_footer = False
    findings = body_check(document, "R10")
    assert len(findings) == 1 and findings[0].severity == "manual"
    assert findings[0].location.section == 2


@pytest.mark.parametrize("start", [2, 3])
def test_explicit_number_start_selects_first_header_parity(eom_fixtures, body_check, start):
    document = Document(eom_fixtures["good"])
    document.sections[0].different_first_page_header_footer = False
    number = OxmlElement("w:pgNumType")
    number.set(qn("w:start"), str(start))
    document.sections[0]._sectPr.append(number)
    header(document, "even" if start % 2 else "default").paragraphs[0].clear()
    findings = body_check(document, "R10")
    errors = [item for item in findings if item.severity == "error"]
    assert len(errors) == 1 and errors[0].actual == {"first_page_header": "present"}


def test_literal_number_is_not_an_automatic_page_field(eom_fixtures, body_check):
    document = Document(eom_fixtures["good"])
    paragraph = header(document).paragraphs[0]
    paragraph.clear().add_run("2")
    findings = body_check(document, "R10")
    assert len(findings) == 1 and findings[0].severity == "error"
    assert findings[0].actual == {"header": "default", "page_field": False}


@pytest.mark.parametrize("cached", ["wrong cache", "漢", "", "9999"])
def test_page_instruction_defines_numeric_domain_independently_of_cache(
    eom_fixtures, body_check, cached
):
    document = Document(eom_fixtures["good"])
    field(header(document).paragraphs[0], "PAGE \\* MERGEFORMAT", cached=cached)
    assert body_check(document, "R10") == ()


@pytest.mark.parametrize("instruction", ["PAGE \\* CHARFORMAT", "PAGE \\# 000", "DATE"])
def test_unsupported_field_semantics_are_manual(eom_fixtures, body_check, instruction):
    document = Document(eom_fixtures["good"])
    field(header(document).paragraphs[0], instruction)
    findings = body_check(document, "R10")
    assert len(findings) == 1 and findings[0].severity == "manual"


@pytest.mark.parametrize(
    "change",
    [
        "nested",
        "broken",
        "no-result",
        "table",
        "revision",
        "hidden",
        "tab",
        "indent",
        "trailing",
        "unknown-style",
    ],
)
def test_uncertain_header_content_and_geometry_are_manual(eom_fixtures, body_check, change):
    document = Document(eom_fixtures["good"])
    story = header(document)
    paragraph = story.paragraphs[0]
    if change == "nested":
        field(paragraph)
        paragraph._p.find(qn("w:fldSimple")).append(OxmlElement("w:fldSimple"))
    elif change == "broken":
        markers = list(paragraph._p.iter(qn("w:fldChar")))
        markers[-1].getparent().remove(markers[-1])
    elif change == "no-result":
        field(paragraph)
        simple = paragraph._p.find(qn("w:fldSimple"))
        simple.remove(simple[0])
    elif change == "table":
        story.add_table(rows=1, cols=1, width=Twips(1000))
    elif change == "revision":
        paragraph._p.get_or_add_pPr().append(OxmlElement("w:pPrChange"))
    elif change == "hidden":
        result_run(paragraph).font.hidden = True
    elif change == "tab":
        paragraph.add_run().add_tab()
    elif change == "indent":
        paragraph.paragraph_format.right_indent = Twips(100)
    elif change == "trailing":
        paragraph.add_run("текст після номера")
    else:
        paragraph._p.pPr.pStyle.set(qn("w:val"), "missing-style")
    findings = body_check(document, "R10")
    assert findings and all(item.severity == "manual" for item in findings)


@pytest.mark.parametrize("change", ["duplicate", "missing", "unknown-type"])
def test_invalid_header_references_are_manual(eom_fixtures, body_check, change):
    document = Document(eom_fixtures["good"])
    properties = document.sections[0]._sectPr
    node = next(
        n for n in properties.findall(qn("w:headerReference")) if n.get(qn("w:type")) == "default"
    )
    if change == "duplicate":
        from copy import deepcopy

        properties.append(deepcopy(node))
    else:
        node.set(qn("r:id" if change == "missing" else "w:type"), "invalid")
    findings = body_check(document, "R10")
    assert findings and all(item.severity == "manual" for item in findings)


def test_footer_page_number_is_wrong_position(eom_fixtures, body_check):
    document = Document(eom_fixtures["good"])
    header(document).paragraphs[0].clear()
    footer = document.sections[0].footer.paragraphs[0]
    footer.style = document.styles[load_ruleset().rules[9].params["style"]]
    field(footer)
    findings = body_check(document, "R10")
    assert len(findings) == 1 and findings[0].severity == "error"
    assert findings[0].actual == {"header": "default", "position": "bottom"}


def test_complex_script_result_uses_cs_formatting(eom_fixtures, body_check):
    document = Document(eom_fixtures["good"])
    run = field(header(document).paragraphs[0])
    run._r.get_or_add_rPr().append(OxmlElement("w:cs"))
    size = OxmlElement("w:szCs")
    size.set(qn("w:val"), "28")
    run._r.rPr.append(size)
    findings = body_check(document, "R10")
    assert len(findings) == 1
    assert findings[0].actual == {"header": "default", "size_pt": [14.0]}


def test_parameters_are_data_driven(eom_fixtures, body_check):
    parameters = dict(load_ruleset().rules[9].params, font="Calibri", size_pt=14)
    findings = body_check(Document(eom_fixtures["good"]), "R10", parameters=parameters)
    assert len(findings) == 2
    assert all(item.expected == {"font": "Calibri", "size_pt": 14} for item in findings)
    parameters["position"] = "bottom-left"
    findings = body_check(Document(eom_fixtures["good"]), "R10", parameters=parameters)
    assert len(findings) == 1 and findings[0].severity == "manual"


def test_inherited_default_indent_and_direct_override(eom_fixtures, body_check):
    document = Document(eom_fixtures["good"])
    properties = document.styles.element.find(qn("w:docDefaults"))
    properties = properties.find(qn("w:pPrDefault")).find(qn("w:pPr"))
    indent = OxmlElement("w:ind")
    indent.set(qn("w:right"), "100")
    properties.append(indent)
    findings = body_check(document, "R10")
    assert len(findings) == 2 and all(item.severity == "manual" for item in findings)
    for variant in ("default", "even"):
        header(document, variant).paragraphs[0].paragraph_format.right_indent = Twips(0)
    assert body_check(document, "R10") == ()


def test_trailing_text_in_same_run_as_field_end_is_uncertain(eom_fixtures, body_check):
    document = Document(eom_fixtures["good"])
    paragraph = header(document).paragraphs[0]
    end = list(paragraph._p.iter(qn("w:fldChar")))[-1]
    result = result_run(paragraph)
    result._r.append(end)
    text = OxmlElement("w:t")
    text.text = "Згенерований підпис"
    result._r.append(text)
    findings = body_check(document, "R10")
    assert len(findings) == 1 and findings[0].severity == "manual"


def test_numeric_slot_ignores_non_numeric_cached_script(eom_fixtures, body_check):
    document = Document(eom_fixtures["good"])
    run = field(header(document).paragraphs[0], cached="Кеш")
    fonts = run._r.get_or_add_rPr().get_or_add_rFonts()
    fonts.set(qn("w:hAnsi"), "Calibri")
    assert body_check(document, "R10") == ()
    fonts.set(qn("w:ascii"), "Calibri")
    findings = body_check(document, "R10")
    assert len(findings) == 1 and findings[0].actual["font"] == ["Calibri"]


def test_unknown_font_and_known_alignment_are_both_reported(eom_fixtures, body_check):
    document = Document(eom_fixtures["good"])
    paragraph = header(document).paragraphs[0]
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fonts = result_run(paragraph)._r.get_or_add_rPr().get_or_add_rFonts()
    fonts.set(qn("w:asciiTheme"), "unsupported")
    findings = body_check(document, "R10")
    assert {item.severity for item in findings} == {"manual", "error"}
    error = next(item for item in findings if item.severity == "error")
    assert error.actual == {"header": "default", "align": "center"}


def test_explicit_story_view_and_check_preserve_all_parts_and_original(eom_fixtures):
    path = eom_fixtures["bad_r10"]
    original = path.read_bytes()
    document = load_document(path)
    parts = {str(part.partname): part.blob for part in document.part.package.parts}
    paragraph = header(document).paragraphs[0]
    run = result_run(paragraph)
    assert not DocumentModel(document).effective_font_size(run).resolved
    model = DocumentModel(document, story_part=paragraph.part)
    assert model.effective_font_size(run).value == 12
    with pytest.raises(ValueError):
        DocumentModel(Document(), story_part=paragraph.part)
    report = RuleEngine().check(document, load_ruleset())
    assert report == RuleEngine().check(document, load_ruleset())
    assert not report.failed_rules
    assert parts == {str(part.partname): part.blob for part in document.part.package.parts}
    result = fix_document_bytes(original, load_ruleset())
    assert result.document_bytes == original and result.applied_rules == ()
    assert result.after.summary.errors == 1 and result.after.summary.fixable == 0
    assert path.read_bytes() == original
    assert len(Document(BytesIO(result.document_bytes)).sections) == 1
