"""R05 distinguishes multiple spacing from exact/minimum values in points."""

import pytest
from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt
from fixtures.make_fixtures import BODY_BASE_STYLE, BODY_STYLE


def test_single_spacing_is_a_localized_body_error(eom_fixtures, body_check):
    findings = body_check(Document(eom_fixtures["bad_r05"]), "R05")
    assert len(findings) == 1
    finding = findings[0]
    assert finding.severity == "error"
    assert finding.location.paragraph == 1
    assert finding.actual == {"kind": "multiple", "value": 1}
    assert finding.expected == {"kind": "multiple", "value": 1.5}
    assert "Міжрядковий інтервал" in finding.message
    assert finding.fixable


@pytest.mark.parametrize("kind", ["exact", "at_least"])
def test_twenty_one_points_is_not_one_and_a_half_lines(eom_fixtures, body_check, kind):
    document = Document(eom_fixtures["good"])
    formatting = document.paragraphs[0].paragraph_format
    formatting.line_spacing = Pt(21)
    if kind == "at_least":
        formatting.line_spacing_rule = WD_LINE_SPACING.AT_LEAST
    findings = body_check(document, "R05")
    assert len(findings) == 1 and findings[0].severity == "error"
    assert findings[0].actual == {"kind": kind, "value": 21}


@pytest.mark.parametrize("layer", ["direct", "paragraph", "base", "defaults"])
def test_spacing_failure_resolves_inherited_values(eom_fixtures, body_check, layer):
    document = Document(eom_fixtures["good"])
    if layer == "direct":
        document.paragraphs[0].paragraph_format.line_spacing = 2.0
    elif layer == "paragraph":
        document.styles[BODY_STYLE].paragraph_format.line_spacing = 2.0
    elif layer == "base":
        document.styles[BODY_BASE_STYLE].paragraph_format.line_spacing = 2.0
    else:
        document.styles[BODY_BASE_STYLE].paragraph_format.line_spacing = None
        spacing = document.styles.element.find(
            ".//" + qn("w:pPrDefault") + "/" + qn("w:pPr") + "/" + qn("w:spacing")
        )
        spacing.set(qn("w:line"), "480")
        spacing.set(qn("w:lineRule"), "auto")
    findings = body_check(document, "R05")
    assert findings and all(item.severity == "error" for item in findings)
    assert all(item.actual == {"kind": "multiple", "value": 2} for item in findings)


def test_before_after_spacing_does_not_override_inherited_line_spacing(eom_fixtures, body_check):
    document = Document(eom_fixtures["good"])
    formatting = document.paragraphs[0].paragraph_format
    formatting.space_before, formatting.space_after = Pt(8), Pt(8)
    assert body_check(document, "R05") == ()


@pytest.mark.parametrize("case", ["good", "good_simple_fields", "manual_inheritance"])
def test_caption_and_table_spacing_are_excluded_and_run_uncertainty_is_independent(
    eom_fixtures, body_check, case
):
    assert body_check(Document(eom_fixtures[case]), "R05") == ()


def test_manual_role_does_not_create_line_spacing_error(eom_fixtures, body_check):
    findings = body_check(Document(eom_fixtures["manual_role"]), "R05")
    assert len(findings) == 1 and findings[0].severity == "manual"


@pytest.mark.parametrize("derived", [False, True])
def test_program_spacing_is_not_checked_as_body_spacing(eom_fixtures, body_check, derived):
    document = Document(eom_fixtures["bad_r05"])
    program = document.styles.add_style("ЕОМ: Програма", WD_STYLE_TYPE.PARAGRAPH)
    program.base_style = document.styles[BODY_STYLE]
    program.paragraph_format.line_spacing = 1.0
    if derived:
        child = document.styles.add_style("Synthetic Program Child", WD_STYLE_TYPE.PARAGRAPH)
        child.base_style = program
        program = child
    document.add_paragraph("return 0;", style=program)
    findings = body_check(document, "R05")
    assert len(findings) == 1 and findings[0].severity == "error"
    assert findings[0].location.paragraph == 1


@pytest.mark.parametrize("problem", ["orphan_rule", "invalid_line", "duplicate", "revision"])
def test_ambiguous_spacing_stays_manual(eom_fixtures, body_check, problem):
    document = Document(eom_fixtures["good"])
    paragraph = document.paragraphs[0]
    spacing = OxmlElement("w:spacing")
    spacing.set(qn("w:lineRule"), "auto")
    if problem != "orphan_rule":
        spacing.set(
            qn("w:line"), "SYNTHETIC_PRIVATE_IDENTIFIER" if problem == "invalid_line" else "360"
        )
    paragraph._p.get_or_add_pPr().append(spacing)
    if problem == "duplicate":
        paragraph._p.pPr.append(OxmlElement("w:spacing"))
    elif problem == "revision":
        paragraph._p.pPr.append(OxmlElement("w:pPrChange"))
    findings = body_check(document, "R05")
    assert len(findings) == 1 and findings[0].severity == "manual"
    assert "SYNTHETIC_PRIVATE_IDENTIFIER" not in findings[0].model_dump_json()


def test_line_spacing_is_data_driven(eom_fixtures, body_check):
    document = Document(eom_fixtures["good"])
    findings = body_check(document, "R05", parameters={"role": "body", "line_spacing": 2})
    assert findings and all(item.severity == "error" for item in findings)
    assert all(item.expected == {"kind": "multiple", "value": 2} for item in findings)


def test_invalid_spacing_parameter_is_manual(eom_fixtures, body_check):
    findings = body_check(
        Document(eom_fixtures["good"]), "R05", parameters={"role": "body", "line_spacing": "1.5"}
    )
    assert len(findings) == 1 and findings[0].severity == "manual"
