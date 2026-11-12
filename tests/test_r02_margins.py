"""R02 acceptance, per-edge findings, section coverage and conservative uncertainty."""

from copy import deepcopy

import pytest
from docx import Document
from docx.enum.section import WD_SECTION_START
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm, Twips
from fixtures.make_fixtures import CASES

from oformleno.engine import RuleEngine
from oformleno.loader import load_document
from oformleno.model import DocumentModel
from oformleno.rules.r01_page_size import PageSizeChecker
from oformleno.rules.r02_margins import MarginsChecker
from oformleno.ruleset import load_ruleset

EDGES = {"left": 25, "top": 20, "bottom": 20, "right": 15}


def check(document, tmp_path, *, expected=None, tolerance=None):
    path = tmp_path / "generated.docx"
    document.save(path)
    ruleset = load_ruleset()
    if tolerance is not None:
        ruleset = ruleset.model_copy(update={"tolerance_mm": tolerance})
    rule = ruleset.rules[1]
    if expected is not None:
        rule = rule.model_copy(update={"params": expected})
    return list(MarginsChecker().check(DocumentModel(load_document(path)), rule, ruleset))


def test_acceptance_left_margin_reports_actual_expected_and_source(eom_fixtures):
    report = RuleEngine().check(load_document(eom_fixtures["bad_r02"]), load_ruleset())
    finding = next(item for item in report.findings if item.rule_id == "R02")
    assert finding.severity == "error"
    assert finding.location.section == 1
    assert finding.actual == {"left_mm": pytest.approx(20, abs=0.01)}
    assert finding.expected == {"left_mm": 25}
    assert "Ліве поле" in finding.message
    assert "20.00" in finding.message and "25" in finding.message
    assert finding.quote == load_ruleset().rules[1].quote
    assert finding.source_id == "styles"
    assert finding.source_location == load_ruleset().rules[1].source_location
    assert finding.fixable
    assert report.exit_code() == 1


@pytest.mark.parametrize("case", CASES)
def test_generated_suite_matches_available_rule_expectations(eom_fixtures, case):
    report = RuleEngine({"R01": PageSizeChecker(), "R02": MarginsChecker()}).check(
        load_document(eom_fixtures[case]), load_ruleset(), document_type="laboratory_report"
    )
    expected = set(CASES[case].error_rules) & {"R01", "R02"}
    assert {item.rule_id for item in report.findings if item.severity == "error"} == expected
    assert report.checked_rules == ("R01", "R02")
    assert report.failed_rules == ()
    assert report.unavailable_rules == tuple(f"R{index:02}" for index in range(3, 11))
    assert report.summary.manual == 15
    assert report.exit_code() == (1 if expected else 3)


@pytest.mark.parametrize("edge", EDGES)
def test_each_margin_is_checked_and_named(eom_fixtures, tmp_path, edge):
    document = Document(eom_fixtures["good"])
    setattr(document.sections[0], edge + "_margin", Mm(EDGES[edge] + 5))
    findings = check(document, tmp_path)
    assert len(findings) == 1
    assert findings[0].severity == "error"
    assert findings[0].expected == {edge + "_mm": EDGES[edge]}
    assert findings[0].actual[edge + "_mm"] == pytest.approx(EDGES[edge] + 5, abs=0.02)


def test_multiple_margins_and_sections_keep_stable_locations(eom_fixtures, tmp_path):
    document = Document(eom_fixtures["good"])
    document.add_section(WD_SECTION_START.NEW_PAGE)
    document.sections[0].left_margin = Mm(20)
    document.sections[1].right_margin = Mm(20)
    document.sections[1].bottom_margin = Mm(25)
    findings = check(document, tmp_path)
    assert [(item.location.section, next(iter(item.expected))) for item in findings] == [
        (1, "left_mm"),
        (2, "bottom_mm"),
        (2, "right_mm"),
    ]


@pytest.mark.parametrize("offset_twips,errors", [(-73, 1), (-72, 0), (72, 0), (73, 1)])
def test_margin_tolerance_uses_unrounded_lengths(eom_fixtures, tmp_path, offset_twips, errors):
    document = Document(eom_fixtures["good"])
    document.sections[0].left_margin = Twips(1440 + offset_twips)
    expected = {edge + "_mm": value for edge, value in EDGES.items()}
    expected["left_mm"] = 25.4
    assert len(check(document, tmp_path, expected=expected, tolerance=1.27)) == errors


def test_custom_yaml_margin_parameters_are_used(eom_fixtures, tmp_path):
    document = Document(eom_fixtures["bad_r02"])
    expected = {edge + "_mm": value for edge, value in EDGES.items()}
    expected["left_mm"] = 20
    assert check(document, tmp_path, expected=expected) == []


@pytest.mark.parametrize("edge", EDGES)
def test_missing_margin_is_manual_without_guessing_a_default(eom_fixtures, tmp_path, edge):
    document = Document(eom_fixtures["good"])
    del document.sections[0]._sectPr.pgMar.attrib[qn("w:" + edge)]
    findings = check(document, tmp_path)
    assert len(findings) == 1
    assert findings[0].severity == "manual"
    assert findings[0].expected == {edge + "_mm": EDGES[edge]}
    assert findings[0].location.section == 1
    assert findings[0].actual is None
    assert not findings[0].fixable


def test_missing_edge_does_not_hide_another_known_failure(eom_fixtures, tmp_path):
    document = Document(eom_fixtures["bad_r02"])
    del document.sections[0]._sectPr.pgMar.attrib[qn("w:right")]
    findings = check(document, tmp_path)
    assert [(item.severity, next(iter(item.expected))) for item in findings] == [
        ("error", "left_mm"),
        ("manual", "right_mm"),
    ]


@pytest.mark.parametrize(
    "problem",
    [
        "missing_element",
        "duplicate",
        "invalid_margin",
        "negative_left",
        "revision",
        "gutter",
        "invalid_gutter",
        "rtl_gutter",
        "bidi",
        "mirror",
        "book_fold",
        "invalid_mirror",
    ],
)
def test_ambiguous_or_unsupported_margin_layouts_are_manual(eom_fixtures, tmp_path, problem):
    document = Document(eom_fixtures["good"])
    section = document.sections[0]._sectPr
    margins = section.pgMar
    match problem:
        case "missing_element":
            section.remove(margins)
        case "duplicate":
            section.append(deepcopy(margins))
        case "invalid_margin":
            margins.set(qn("w:left"), "SYNTHETIC_PRIVATE_IDENTIFIER")
        case "negative_left":
            margins.set(qn("w:left"), "-100")
        case "revision":
            section.append(OxmlElement("w:sectPrChange"))
        case "gutter":
            document.sections[0].gutter = Mm(10)
        case "invalid_gutter":
            margins.set(qn("w:gutter"), "SYNTHETIC_PRIVATE_IDENTIFIER")
        case "rtl_gutter" | "bidi":
            section.append(OxmlElement("w:rtlGutter" if problem == "rtl_gutter" else "w:bidi"))
        case "mirror" | "book_fold" | "invalid_mirror":
            setting = OxmlElement(
                "w:bookFoldPrinting" if problem == "book_fold" else "w:mirrorMargins"
            )
            if problem == "invalid_mirror":
                setting.set(qn("w:val"), "SYNTHETIC_PRIVATE_IDENTIFIER")
            document.settings.element.append(setting)
    findings = check(document, tmp_path)
    assert len(findings) == 1
    assert findings[0].severity == "manual"
    assert not findings[0].fixable
    assert "SYNTHETIC_PRIVATE_IDENTIFIER" not in findings[0].model_dump_json()


def test_explicitly_disabled_mirror_layout_does_not_block_checking(eom_fixtures, tmp_path):
    document = Document(eom_fixtures["good"])
    setting = OxmlElement("w:mirrorMargins")
    setting.set(qn("w:val"), "false")
    document.settings.element.append(setting)
    assert check(document, tmp_path) == []


def test_legal_signed_top_margin_is_a_known_mismatch(eom_fixtures, tmp_path):
    document = Document(eom_fixtures["good"])
    document.sections[0].top_margin = Mm(-20)
    findings = check(document, tmp_path)
    assert len(findings) == 1
    assert findings[0].severity == "error"
    assert findings[0].actual["top_mm"] < 0


def test_missing_settings_part_is_not_created_during_checking(eom_fixtures, tmp_path):
    document = Document(eom_fixtures["good"])
    for relation in list(document.part.rels.values()):
        if relation.reltype == RT.SETTINGS:
            document.part.drop_rel(relation.rId)
    path = tmp_path / "generated.docx"
    document.save(path)
    document = load_document(path)
    original = path.read_bytes()
    parts = {str(part.partname): part.blob for part in document.part.package.parts}
    report = RuleEngine().check(document, load_ruleset())
    assert not [item for item in report.findings if item.rule_id in ("R01", "R02")]
    assert report.checked_rules == (
        "R01",
        "R02",
        "R03",
        "R04",
        "R05",
        "R06",
        "R07",
        "R08",
        "R09",
        "R10",
    )
    assert {str(part.partname): part.blob for part in document.part.package.parts} == parts
    assert path.read_bytes() == original


def test_explicit_empty_registry_disables_builtin_rules(eom_fixtures):
    report = RuleEngine({}).check(load_document(eom_fixtures["bad_r02"]), load_ruleset())
    assert report.checked_rules == ()
    assert report.summary.errors == 0
    assert "R02" in report.unavailable_rules
