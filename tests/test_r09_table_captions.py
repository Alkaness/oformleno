"""R09: combined table captions, inherited emphasis and independent numbering."""

from copy import deepcopy
from io import BytesIO

import pytest
from caption_helpers import change_code, child, example, visible_runs
from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt

from oformleno.engine import RuleEngine
from oformleno.fixer import fix_document_bytes
from oformleno.loader import load_document
from oformleno.model import DocumentModel
from oformleno.ruleset import load_ruleset


@pytest.mark.parametrize("case", ["good", "good_simple_fields", "good_section_break"])
def test_valid_combined_caption_and_separate_counter(eom_fixtures, body_check, case):
    assert body_check(Document(eom_fixtures[case]), "R09") == ()


def test_italic_acceptance_has_evidence_and_is_not_fixable(eom_fixtures, body_check):
    document, _paragraph, rule = example(eom_fixtures, "R09", "bad_r09")
    findings = body_check(document, "R09")
    assert len(findings) == 1
    item = findings[0]
    assert item.severity == "error" and not item.fixable
    assert item.actual == {"italic": False} and item.expected == {"italic": True}
    assert item.location.paragraph == 10 and item.location.page is None
    assert item.quote == rule.quote and item.source_id == "styles"
    assert item.parameter_sources["layout"] == "user_reference"
    assert "user_reference" in item.source_notes


@pytest.mark.parametrize("property", ["bold", "size", "font", "align", "spacing", "keep"])
def test_table_caption_typography(eom_fixtures, body_check, property):
    document, paragraph, _rule = example(eom_fixtures, "R09")
    run = visible_runs(document, paragraph)[-1]
    if property == "bold":
        run.bold = False
        key, actual = "bold", False
    elif property == "size":
        run.font.size = Pt(12)
        key, actual = "size_pt", [12]
    elif property == "font":
        run.font.name = "Calibri"
        key, actual = "font", ["Calibri"]
    elif property == "align":
        paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        key, actual = "align", "right"
    elif property == "spacing":
        paragraph.paragraph_format.line_spacing = 1
        key, actual = "line_spacing", {"kind": "multiple", "value": 1}
    else:
        paragraph.paragraph_format.keep_with_next = False
        key, actual = "keep_with_next", False
    findings = body_check(document, "R09")
    assert len(findings) == 1 and findings[0].severity == "error"
    assert findings[0].actual == {key: actual}


def test_derived_caption_and_keep_next_inheritance(eom_fixtures, body_check):
    document, paragraph, rule = example(eom_fixtures, "R09")
    derived = document.styles.add_style("Synthetic table caption", WD_STYLE_TYPE.PARAGRAPH)
    derived.base_style = document.styles[rule.params["style"]]
    paragraph.style = derived
    assert paragraph.paragraph_format.keep_with_next is None
    assert body_check(document, "R09") == ()
    derived.paragraph_format.keep_with_next = False
    findings = body_check(document, "R09")
    assert findings[0].actual == {"keep_with_next": False}


@pytest.mark.parametrize("change", ["missing", "bad", "defaults"])
def test_keep_next_uses_defaults_and_invalid_values_are_manual(eom_fixtures, body_check, change):
    document, paragraph, rule = example(eom_fixtures, "R09")
    style = document.styles[rule.params["style"]]
    if change == "bad":
        child(paragraph._p.get_or_add_pPr(), "keepNext", val="invalid")
    else:
        style.paragraph_format.keep_with_next = None
        if change == "defaults":
            defaults = document.styles.element.find(".//" + qn("w:pPrDefault") + "/" + qn("w:pPr"))
            child(defaults, "keepNext")
    findings = body_check(document, "R09")
    if change == "defaults":
        assert findings == ()
    elif change == "bad":
        assert len(findings) == 1 and findings[0].severity == "manual"
    else:
        assert findings and all(item.actual == {"keep_with_next": False} for item in findings)


def test_caption_below_table_is_a_known_position_error(eom_fixtures, body_check):
    document, paragraph, _rule = example(eom_fixtures, "R09")
    table = paragraph._p.getnext()
    table.addnext(paragraph._p)
    findings = body_check(document, "R09")
    assert len(findings) == 1 and findings[0].severity == "error"
    assert findings[0].actual == {"position": "below"}
    assert findings[0].expected == {"position": "above"}


@pytest.mark.parametrize(
    "change", ["separate_number", "title_only", "floating", "gap", "role", "field"]
)
def test_alternative_layouts_and_uncertain_links_are_manual(eom_fixtures, body_check, change):
    document, paragraph, _rule = example(eom_fixtures, "R09")
    if change in {"separate_number", "title_only"}:
        paragraph.text = "Згенерована назва таблиці"
        if change == "separate_number":
            style = document.styles.add_style("ЕОМ: Номер таблиці", WD_STYLE_TYPE.PARAGRAPH)
            paragraph.insert_paragraph_before("Таблиця 1.1", style)
    elif change == "floating":
        child(paragraph._p.getnext().find(qn("w:tblPr")), "tblpPr")
    elif change == "gap":
        gap = document.add_paragraph()
        paragraph._p.addnext(gap._p)
    elif change == "role":
        paragraph.style = document.styles["Normal"]
    else:
        change_code(paragraph, "\\s 1", "\\s")
    findings = body_check(document, "R09")
    assert findings and all(item.severity == "manual" for item in findings)


@pytest.mark.parametrize("change", ["shared", "level", "separator", "literal"])
def test_table_numbering_errors(eom_fixtures, body_check, change):
    document, paragraph, _rule = example(eom_fixtures, "R09")
    if change == "shared":
        change_code(paragraph, "SEQ Табл.", "SEQ Рис.")
        key, actual = "sequence_name", "Рис."
    elif change == "level":
        change_code(paragraph, "\\s 1", "\\s 2")
        key, actual = "reset_at_heading_level", "2"
    elif change == "separator":
        next(run for run in paragraph.runs if run.text == ".").text = ":"
        key, actual = "separator", ":"
    else:
        paragraph.text = "Табл. 1.1 Згенерована назва"
        key, actual = "method", "literal"
    findings = body_check(document, "R09")
    errors = [item for item in findings if item.severity == "error"]
    assert len(errors) == 1 and errors[0].actual == {key: actual}
    assert all(item.severity == "manual" for item in findings if item not in errors)


@pytest.mark.parametrize("flag", ["bold", "italic"])
def test_explicit_complex_script_uses_cs_emphasis(eom_fixtures, body_check, flag):
    document, paragraph, _rule = example(eom_fixtures, "R09")
    run = visible_runs(document, paragraph)[-1]
    properties = run._r.get_or_add_rPr()
    child(properties, "cs")
    child(properties, "szCs", val=28)
    child(properties, "bCs")
    child(properties, "iCs")
    assert body_check(document, "R09") == ()
    properties.find(qn("w:bCs" if flag == "bold" else "w:iCs")).set(qn("w:val"), "false")
    findings = body_check(document, "R09")
    assert len(findings) == 1 and findings[0].actual == {flag: False}


@pytest.mark.parametrize(
    "property",
    [
        "font",
        "size_pt",
        "italic",
        "line_spacing",
        "align",
        "position",
        "label",
        "sequence_name",
        "separator",
    ],
)
def test_caption_parameters_come_from_data(eom_fixtures, body_check, property):
    document, _paragraph, rule = example(eom_fixtures, "R09")
    parameters = deepcopy(rule.params)
    changes = {
        "font": "Calibri",
        "size_pt": 12,
        "italic": False,
        "line_spacing": 1,
        "align": "right",
        "position": "below",
        "label": "Таблиця",
        "sequence_name": "Таблиці",
        "separator": "-",
    }
    if property in {"sequence_name", "separator"}:
        parameters["numbering"][property] = changes[property]
    else:
        parameters[property] = changes[property]
    if property == "position":
        for paragraph in document.paragraphs:
            if paragraph.style.name == rule.params["style"]:
                paragraph._p.getnext().addnext(paragraph._p)
        assert body_check(document, "R09", parameters=parameters) == ()
        return
    findings = body_check(document, "R09", parameters=parameters)
    assert findings and all(item.severity == "error" for item in findings)
    assert all(property in item.expected for item in findings)


@pytest.mark.parametrize(
    "change",
    ["extra", "size_bool", "italic_string", "layout", "numbering", "level_bool", "shared_counters"],
)
def test_unsupported_configuration_is_manual(eom_fixtures, body_check, change):
    document, _paragraph, rule = example(eom_fixtures, "R09")
    parameters = deepcopy(rule.params)
    if change == "extra":
        parameters["unknown"] = 1
    elif change == "size_bool":
        parameters["size_pt"] = True
    elif change == "italic_string":
        parameters["italic"] = "true"
    elif change == "layout":
        parameters["layout"] = "separate"
    elif change == "numbering":
        parameters["numbering"]["method"] = "literal"
    elif change == "level_bool":
        parameters["numbering"]["chapter_heading_level"] = True
    else:
        parameters["numbering"]["sequence_name"] = "Рис."
    findings = body_check(document, "R09", parameters=parameters)
    assert len(findings) == 1 and findings[0].severity == "manual"


def test_sdt_and_hyperlink_captions_keep_order_and_roles(eom_fixtures, body_check):
    document, paragraph, _rule = example(eom_fixtures, "R09")
    control = child(document.element.body, "sdt")
    content = child(control, "sdtContent")
    paragraph._p.addprevious(control)
    table = paragraph._p.getnext()
    content.append(paragraph._p)
    content.append(table)
    link = child(paragraph._p, "hyperlink")
    link.append(visible_runs(document, paragraph)[-1]._r)
    assert body_check(document, "R09") == ()


def test_stale_cached_values_do_not_prove_order(eom_fixtures, body_check):
    document, paragraph, _rule = example(eom_fixtures, "R09", "good_simple_fields")
    for field in paragraph._p.iter(qn("w:fldSimple")):
        field.find(".//" + qn("w:t")).text = "999"
    assert body_check(document, "R09") == ()


def test_read_only_and_fix_preserve_table_caption_error(eom_fixtures):
    path = eom_fixtures["bad_r09"]
    original = path.read_bytes()
    document = load_document(path)
    parts = {str(part.partname): part.blob for part in document.part.package.parts}
    report = RuleEngine().check(DocumentModel(document), load_ruleset())
    assert report.failed_rules == ()
    assert parts == {str(part.partname): part.blob for part in document.part.package.parts}
    result = fix_document_bytes(original, load_ruleset())
    assert result.applied_rules == () and result.document_bytes == original
    assert result.after.summary.errors == 1 and result.after.summary.fixable == 0
    assert path.read_bytes() == original
    assert len(Document(BytesIO(result.document_bytes)).tables) == 3


@pytest.mark.parametrize(
    "change", ["repeated_toggle", "field_result", "style_revision", "unknown_character"]
)
def test_unresolved_formatting_does_not_hide_known_bad_keep_flag(eom_fixtures, body_check, change):
    document, paragraph, rule = example(eom_fixtures, "R09")
    paragraph.paragraph_format.keep_with_next = False
    if change == "repeated_toggle":
        base = document.styles.add_style("Synthetic ambiguous base", WD_STYLE_TYPE.PARAGRAPH)
        base.base_style = paragraph.style.base_style
        base.font.italic = True
        paragraph.style.base_style = base
    elif change == "field_result":
        results = [run for run in paragraph.runs if run.text == "1"]
        for run in results:
            run._r.getparent().remove(run._r)
    elif change == "style_revision":
        child(paragraph.style.element.get_or_add_rPr(), "rPrChange")
    else:
        child(
            visible_runs(document, paragraph)[-1]._r.get_or_add_rPr(),
            "rStyle",
            val="MissingSyntheticStyle",
        )
    findings = body_check(document, "R09")
    assert any(item.severity == "manual" for item in findings)
    if change == "style_revision":
        assert all(item.severity == "manual" for item in findings)
    else:
        errors = [item for item in findings if item.severity == "error"]
        assert len(errors) == 1 and errors[0].actual["keep_with_next"] is False


def test_missing_table_is_manual_without_inventing_a_placement_error(eom_fixtures, body_check):
    document, paragraph, _rule = example(eom_fixtures, "R09")
    table = paragraph._p.getnext()
    table.getparent().remove(table)
    findings = body_check(document, "R09")
    assert findings and all(item.severity == "manual" for item in findings)
