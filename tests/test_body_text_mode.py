"""Explicit ordinary prose scope and mode propagation on saved synthetic DOCX."""

import base64
from io import BytesIO
from zipfile import ZipFile

import pytest
from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt
from lxml import etree

from oformleno.engine import EngineError, RuleEngine
from oformleno.fixer import fix_document_bytes
from oformleno.loader import DocumentLoadError, load_document_bytes
from oformleno.model import DocumentModel
from oformleno.report_html import render_report_html
from oformleno.ruleset import load_ruleset
from oformleno.web import process_upload

BODY_RULES = {"R03", "R04", "R05"}


def ordinary_document(eom_fixtures):
    document = Document(eom_fixtures["good"])
    paragraph = document.paragraphs[0]
    paragraph.style = document.styles["Normal"]
    paragraph.runs[0].font.name = "Calibri"
    paragraph.runs[0].font.size = Pt(12)
    paragraph.paragraph_format.line_spacing = 1
    return document


def saved(document):
    output = BytesIO()
    document.save(output)
    return output.getvalue()


def reopened(content):
    return load_document_bytes(content, filename="generated.docx")


def body_findings(report):
    return [item for item in report.findings if item.rule_id in BODY_RULES]


def test_ordinary_copy_fixes_three_errors_and_preserves_excluded_xml_and_other_parts(eom_fixtures):
    document = ordinary_document(eom_fixtures)
    source = saved(document)
    original = bytes(source)
    result = fix_document_bytes(
        source, load_ruleset(), document_type="laboratory_report", body_text_mode="ordinary"
    )
    assert source == original and source != result.document_bytes
    assert result.before.body_text_mode == result.after.body_text_mode == "ordinary"
    assert {item.rule_id for item in body_findings(result.before)} == BODY_RULES
    assert all(item.severity == "error" and item.fixable for item in body_findings(result.before))
    assert not body_findings(result.after)
    assert result.after.summary.errors == 0 and result.after.summary.manual == 7
    assert set(result.applied_rules) == BODY_RULES
    corrected = reopened(result.document_bytes)
    assert [p.text for p in corrected.paragraphs] == [p.text for p in document.paragraphs]
    assert corrected.paragraphs[0].style.name == "Normal"
    # The formatter's generic content signature permits typography globally;
    # independently assert exact XML for every element outside the target prose.
    original_children = list(document.element.body)
    corrected_children = list(corrected.element.body)
    assert len(original_children) == len(corrected_children)
    assert [etree.tostring(p, method="c14n") for p in original_children[1:]] == [
        etree.tostring(p, method="c14n") for p in corrected_children[1:]
    ]
    with ZipFile(BytesIO(source)) as before, ZipFile(BytesIO(result.document_bytes)) as after:
        assert before.namelist() == after.namelist()
        assert all(
            before.read(name) == after.read(name)
            for name in before.namelist()
            if name != "word/document.xml"
        )


@pytest.mark.parametrize("mode", ["styles", "ordinary"])
def test_valid_body_formatting_does_not_become_an_error_due_to_missing_style(eom_fixtures, mode):
    document = ordinary_document(eom_fixtures)
    p = document.paragraphs[0]
    p.runs[0].font.name = "Times New Roman"
    p.runs[0].font.size = Pt(14)
    p.paragraph_format.line_spacing = 1.5
    report = RuleEngine().check(reopened(saved(document)), load_ruleset(), body_text_mode=mode)
    findings = body_findings(report)
    assert not any(item.severity == "error" for item in findings)
    assert len(findings) == (3 if mode == "styles" else 0)


@pytest.mark.parametrize(
    "kind",
    [
        "title",
        "caption",
        "heading",
        "code",
        "custom",
        "outline",
        "numbering",
        "structural_name",
        "caption_label",
        "long_caption_label",
        "field",
        "missing_style",
        "object",
    ],
)
def test_ordinary_mode_retains_non_body_roles_and_uncertainty(eom_fixtures, kind):
    document = ordinary_document(eom_fixtures)
    p = document.paragraphs[0]
    if kind in {"title", "caption", "heading"}:
        p.style = {"title": "Title", "caption": "Caption", "heading": "Heading 1"}[kind]
    elif kind in {"custom", "code"}:
        p.style = document.styles.add_style(
            "ЕОМ: Програма" if kind == "code" else "Synthetic Unknown", WD_STYLE_TYPE.PARAGRAPH
        )
    elif kind in {"outline", "numbering", "missing_style"}:
        node = OxmlElement(
            {"outline": "w:outlineLvl", "numbering": "w:numPr", "missing_style": "w:pStyle"}[kind]
        )
        if kind == "numbering":
            child = OxmlElement("w:numId")
            child.set(qn("w:val"), "1")
            node.append(child)
        else:
            node.set(qn("w:val"), "0" if kind == "outline" else "MissingSyntheticStyle")
        if kind == "missing_style" and p._p.pPr.pStyle is not None:
            p._p.get_or_add_pPr().remove(p._p.pPr.pStyle)
        p._p.get_or_add_pPr().append(node)
    elif kind in {"structural_name", "caption_label", "long_caption_label"}:
        p.runs[0].text = {
            "structural_name": "ВСТУП",
            "caption_label": "Рис. 1.1 Згенерований підпис",
            "long_caption_label": "Таблиця 1.1 Згенерований підпис",
        }[kind]
    elif kind == "object":
        p.add_run()._r.append(OxmlElement("w:object"))
    else:
        field = OxmlElement("w:fldSimple")
        field.set(qn("w:instr"), "TOC")
        p._p.append(field)
    source = saved(document)
    result = fix_document_bytes(source, load_ruleset(), body_text_mode="ordinary")
    assert not any(item.severity == "error" for item in body_findings(result.before))
    assert not set(result.applied_rules) & BODY_RULES
    original_p = reopened(source).paragraphs[0]._p
    corrected_p = reopened(result.document_bytes).paragraphs[0]._p
    assert etree.tostring(original_p, method="c14n") == etree.tostring(corrected_p, method="c14n")


def test_cross_paragraph_toc_results_are_not_body_text(eom_fixtures):
    document = ordinary_document(eom_fixtures)
    first = document.paragraphs[0]
    second = first.insert_paragraph_before("")
    for tag, value in [("w:fldChar", "begin"), ("w:instrText", " TOC "), ("w:fldChar", "separate")]:
        node = OxmlElement(tag)
        if tag == "w:fldChar":
            node.set(qn("w:fldCharType"), value)
        else:
            node.text = value
        second.add_run()._r.append(node)
    last = document.add_paragraph()
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    last.add_run()._r.append(end)
    report = RuleEngine().check(
        reopened(saved(document)), load_ruleset(), body_text_mode="ordinary"
    )
    findings = [item for item in body_findings(report) if item.location.paragraph == 2]
    assert len(findings) == 3 and all(item.severity == "manual" for item in findings)


def test_default_style_can_have_a_localized_name(eom_fixtures):
    document = ordinary_document(eom_fixtures)
    document.styles["Normal"].name = "Звичайний"
    report = RuleEngine().check(
        reopened(saved(document)), load_ruleset(), body_text_mode="ordinary"
    )
    assert {
        item.rule_id for item in body_findings(report) if item.severity == "error"
    } == BODY_RULES


def test_model_mode_is_local_and_reported_without_xml_mutation(eom_fixtures):
    document = reopened(saved(ordinary_document(eom_fixtures)))
    model = DocumentModel(document)
    xml = document.element.xml
    ordinary = RuleEngine().check(model, load_ruleset(), body_text_mode="ordinary")
    strict = RuleEngine().check(model, load_ruleset())
    assert model.body_text_mode == strict.body_text_mode == "styles"
    assert ordinary.body_text_mode == "ordinary" and document.element.xml == xml
    assert "Звичайні абзаци — основний текст" in render_report_html(ordinary)


@pytest.mark.parametrize("mode", [None, "styles", "ordinary"])
def test_web_default_and_explicit_modes_match_check_and_fix(eom_fixtures, mode):
    source = saved(ordinary_document(eom_fixtures))
    event = {"name": "generated.docx", "content": base64.b64encode(source).decode()}
    if mode is not None:
        event["body_text_mode"] = mode
    result = process_upload(event)
    assert event == {}
    assert result.before.body_text_mode == (mode or "ordinary")
    if mode == "styles":
        assert result.corrected is None and result.before.summary.errors == 0
        assert all(item.severity == "manual" for item in body_findings(result.before))
    else:
        assert result.before.summary.errors == 3 and result.after.summary.errors == 0
        assert result.after.body_text_mode == "ordinary" and result.corrected != source


def test_invalid_mode_is_rejected_and_web_event_cleared(eom_fixtures):
    event = {"name": "generated.docx", "content": "", "body_text_mode": "PRIVATE_MARKER"}
    with pytest.raises(DocumentLoadError, match="Невідомий режим"):
        process_upload(event)
    assert event == {}
    with pytest.raises(EngineError, match="Невідомий режим"):
        RuleEngine().check(Document(), load_ruleset(), body_text_mode="PRIVATE_MARKER")
