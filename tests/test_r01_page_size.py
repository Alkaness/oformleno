"""R01 acceptance, orientation, exact tolerance boundaries and uncertain sections."""

from copy import deepcopy

import pytest
from docx import Document
from docx.enum.section import WD_ORIENT, WD_SECTION_START
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm, Twips

from oformleno.engine import RuleEngine
from oformleno.loader import load_document
from oformleno.model import DocumentModel
from oformleno.rules.r01_page_size import PageSizeChecker
from oformleno.ruleset import load_ruleset


def check(document, tmp_path, *, expected=None, tolerance=None):
    path = tmp_path / "generated.docx"
    document.save(path)
    ruleset = load_ruleset()
    if tolerance is not None:
        ruleset = ruleset.model_copy(update={"tolerance_mm": tolerance})
    rule = ruleset.rules[0]
    if expected is not None:
        rule = rule.model_copy(update={"params": expected})
    return list(PageSizeChecker().check(DocumentModel(load_document(path)), rule, ruleset))


@pytest.mark.parametrize(
    "case", ["good", "good_page_break", "good_section_break", "good_simple_fields"]
)
def test_valid_generated_page_sizes(eom_fixtures, tmp_path, case):
    assert check(Document(eom_fixtures[case]), tmp_path) == []


def test_wrong_page_size_reports_section_dimensions_and_yaml_quote(eom_fixtures):
    report = RuleEngine().check(load_document(eom_fixtures["bad_r01"]), load_ruleset())
    finding = next(item for item in report.findings if item.rule_id == "R01")
    assert finding.severity == "error"
    assert finding.location.section == 1
    assert finding.location.page is finding.location.paragraph is None
    assert finding.actual["width_mm"] == pytest.approx(190, abs=0.02)
    assert finding.expected == {"width_mm": 210, "height_mm": 297}
    assert finding.quote == load_ruleset().rules[0].quote
    assert finding.source_id == "styles"
    assert finding.rule_name == "Формат сторінки"
    assert finding.fixable


@pytest.mark.parametrize("landscape", [False, True])
def test_orientation_changes_expected_axis_order(eom_fixtures, tmp_path, landscape):
    document = Document(eom_fixtures["good"])
    section = document.sections[0]
    section.orientation = WD_ORIENT.LANDSCAPE if landscape else WD_ORIENT.PORTRAIT
    section.page_width, section.page_height = (
        (Mm(297), Mm(210)) if landscape else (Mm(210), Mm(297))
    )
    assert check(document, tmp_path) == []


def test_landscape_size_failure_reports_landscape_expected_values(eom_fixtures, tmp_path):
    document = Document(eom_fixtures["good"])
    section = document.sections[0]
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width, section.page_height = Mm(280), Mm(210)
    findings = check(document, tmp_path)
    assert len(findings) == 1
    assert findings[0].expected == {"width_mm": 297, "height_mm": 210}


@pytest.mark.parametrize("offset_twips,errors", [(-73, 1), (-72, 0), (72, 0), (73, 1)])
def test_tolerance_is_inclusive_before_display_rounding(
    eom_fixtures, tmp_path, offset_twips, errors
):
    document = Document(eom_fixtures["good"])
    section = document.sections[0]
    section.page_width, section.page_height = Twips(11520 + offset_twips), Twips(17280)
    # Exact decimal lengths: 8/12 inches and a 0.05 inch tolerance.
    findings = check(
        document, tmp_path, expected={"width_mm": 203.2, "height_mm": 304.8}, tolerance=1.27
    )
    assert len(findings) == errors
    assert all(finding.severity == "error" for finding in findings)


@pytest.mark.parametrize("delta,errors", [(-0.51, 1), (-0.49, 0), (0.49, 0), (0.51, 1)])
def test_active_half_millimetre_tolerance(eom_fixtures, tmp_path, delta, errors):
    document = Document(eom_fixtures["good"])
    document.sections[0].page_width = Mm(210 + delta)
    assert len(check(document, tmp_path)) == errors


def test_second_section_is_checked_independently(eom_fixtures, tmp_path):
    document = Document(eom_fixtures["good"])
    section = document.add_section(WD_SECTION_START.NEW_PAGE)
    section.page_height = Mm(280)
    findings = check(document, tmp_path)
    assert len(findings) == 1
    assert findings[0].location.section == 2
    assert findings[0].actual["height_mm"] == pytest.approx(280, abs=0.02)


@pytest.mark.parametrize(
    "problem",
    [
        "missing_element",
        "missing_width",
        "missing_height",
        "duplicate",
        "invalid_width",
        "invalid_height",
        "zero_width",
        "negative_height",
        "invalid_orientation",
        "revision",
    ],
)
def test_uncertain_page_properties_are_manual(eom_fixtures, tmp_path, problem):
    document = Document(eom_fixtures["good"])
    section = document.sections[0]._sectPr
    size = section.pgSz
    match problem:
        case "missing_element":
            section.remove(size)
        case "missing_width":
            del size.attrib[qn("w:w")]
        case "missing_height":
            del size.attrib[qn("w:h")]
        case "duplicate":
            section.append(deepcopy(size))
        case "invalid_width":
            size.set(qn("w:w"), "SYNTHETIC_PRIVATE_IDENTIFIER")
        case "invalid_height":
            size.set(qn("w:h"), "NaN")
        case "zero_width":
            size.set(qn("w:w"), "0")
        case "negative_height":
            size.set(qn("w:h"), "-20")
        case "invalid_orientation":
            size.set(qn("w:orient"), "SYNTHETIC_PRIVATE_IDENTIFIER")
        case "revision":
            section.append(OxmlElement("w:sectPrChange"))
    findings = check(document, tmp_path)
    assert len(findings) == 1
    assert findings[0].severity == "manual"
    assert findings[0].location.section == 1
    assert findings[0].actual is None
    assert not findings[0].fixable
    assert "вручну" in findings[0].message
    assert "SYNTHETIC_PRIVATE_IDENTIFIER" not in findings[0].model_dump_json()


def test_missing_orientation_uses_documented_portrait_default(eom_fixtures, tmp_path):
    document = Document(eom_fixtures["good"])
    document.sections[0]._sectPr.pgSz.attrib.pop(qn("w:orient"), None)
    assert check(document, tmp_path) == []


def test_manual_section_does_not_hide_known_error_in_later_section(eom_fixtures, tmp_path):
    document = Document(eom_fixtures["good"])
    document.add_section(WD_SECTION_START.NEW_PAGE).page_width = Mm(190)
    document.sections[0]._sectPr.remove(document.sections[0]._sectPr.pgSz)
    findings = check(document, tmp_path)
    assert [(item.severity, item.location.section) for item in findings] == [
        ("manual", 1),
        ("error", 2),
    ]


@pytest.mark.parametrize("problem", ["missing_final", "duplicate_final", "wrapped_boundary"])
def test_unrepresented_or_invalid_sections_cannot_produce_all_clear(
    eom_fixtures, tmp_path, problem
):
    document = Document(eom_fixtures["good"])
    body = document.element.body
    if problem == "missing_final":
        body.remove(body.sectPr)
    elif problem == "duplicate_final":
        body.append(deepcopy(body.sectPr))
    else:
        document.add_section(WD_SECTION_START.NEW_PAGE)
        paragraph = document.paragraphs[-1]._p
        control = OxmlElement("w:sdt")
        content = OxmlElement("w:sdtContent")
        control.append(content)
        paragraph.addprevious(control)
        content.append(paragraph)
    findings = check(document, tmp_path)
    assert len(findings) == 1
    assert findings[0].severity == "manual"
    assert findings[0].location.section is None


@pytest.mark.parametrize(
    "expected",
    [
        {},
        {"width_mm": True, "height_mm": 297},
        {"width_mm": "210", "height_mm": 297},
        {"width_mm": -210, "height_mm": 297},
        {"width_mm": 210, "height_mm": 297, "unknown": 1},
    ],
)
def test_unsupported_rule_parameters_are_manual(eom_fixtures, tmp_path, expected):
    findings = check(Document(eom_fixtures["good"]), tmp_path, expected=expected)
    assert len(findings) == 1
    assert findings[0].severity == "manual"


def test_checking_is_deterministic_and_preserves_all_source_parts(eom_fixtures):
    path = eom_fixtures["bad_r01"]
    original = path.read_bytes()
    document = load_document(path)
    parts = {str(part.partname): part.blob for part in document.part.package.parts}
    ruleset = load_ruleset()
    engine = RuleEngine()
    first = engine.check(document, ruleset).model_dump_json()
    assert engine.check(document, ruleset).model_dump_json() == first
    assert {str(part.partname): part.blob for part in document.part.package.parts} == parts
    assert path.read_bytes() == original
