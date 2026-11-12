"""Check orchestration and report contracts without implementing formatting rules."""

import json

import pytest
from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.shared import Pt
from pydantic import ValidationError

from oformleno.engine import Finding, Location, Report, RuleEngine
from oformleno.loader import load_document
from oformleno.model import DocumentModel
from oformleno.ruleset import Ruleset, load_ruleset


class StaticChecker:
    def __init__(self, findings=()):
        self.findings = findings
        self.calls = 0

    def check(self, document, rule, ruleset):
        self.calls += 1
        return self.findings


def sample_finding(**overrides):
    data = {
        "rule_id": "R01",
        "severity": "error",
        "location": Location(section=1),
        "actual": 20,
        "expected": 25,
        "quote": "Згенерована цитата.",
        "message": "Згенероване пояснення порушення.",
        "fixable": True,
    }
    return Finding(**{**data, **overrides})


def test_summary_counts_severities_and_fixability():
    report = Report(
        ruleset_id="generated-guideline",
        ruleset_title="Згенеровані вимоги",
        findings=(
            sample_finding(),
            sample_finding(rule_id="R02", severity="warning", fixable=False),
            sample_finding(rule_id="M01", severity="manual", fixable=False, actual=None),
        ),
    )
    data = json.loads(report.model_dump_json())
    assert data["summary"] == {
        "errors": 1,
        "warnings": 1,
        "manual": 1,
        "fixable": 1,
        "status": "errors_found",
        "message": (
            "Знайдено 1 помилок, 1 можна виправити автоматично. "
            "Попереджень: 1. Перевірте вручну: 1."
        ),
    }
    assert report.exit_code() == 1
    assert "Згенеровані" in report.model_dump_json()


def test_manual_finding_cannot_be_fixable():
    with pytest.raises(ValidationError):
        sample_finding(severity="manual", fixable=True)


def test_non_finite_measurements_cannot_be_reported_as_json():
    with pytest.raises(ValidationError):
        sample_finding(actual=float("nan"))


@pytest.mark.parametrize("location", [{"paragraph": 0}, {"page": -1}, {"excerpt": "x" * 51}])
def test_rejects_invalid_locations(location):
    with pytest.raises(ValidationError):
        Location(**location)


def test_unknown_rules_are_manual_not_passed(ruleset_data):
    report = RuleEngine({}).check(Document(), Ruleset.model_validate(ruleset_data))

    assert report.unavailable_rules == ("R01",)
    assert report.checked_rules == ()
    assert len(report.findings) == 1
    assert report.findings[0].severity == "manual"
    assert not report.findings[0].fixable
    assert report.findings[0].quote == ruleset_data["rules"][0]["quote"]
    assert report.summary.status == "manual_required"
    assert report.exit_code() == 3


@pytest.mark.parametrize(
    ("document_type", "manual_count", "has_thesis_check"),
    [(None, 18, True), ("laboratory_report", 17, False), ("qualification_thesis", 18, True)],
)
def test_eom_checklist_respects_work_type(document_type, manual_count, has_thesis_check):
    ruleset = load_ruleset()
    original = ruleset.model_dump()

    report = RuleEngine({}).check(Document(), ruleset, document_type=document_type)

    ids = {item.rule_id for item in report.findings}
    assert ("M06" in ids) == has_thesis_check
    assert report.summary.manual == manual_count
    assert report.summary.errors == report.summary.fixable == 0
    assert report.summary.status == "manual_required"
    assert ruleset.model_dump() == original
    if document_type is None:
        finding = next(item for item in report.findings if item.rule_id == "M06")
        assert "Тип роботи не вказано" in finding.message
        assert finding.applies_to == ("qualification_thesis",)


def test_registered_checker_preserves_location_and_uses_configuration_quote(ruleset_data):
    rule = ruleset_data["rules"][0]
    rule["severity"] = "warning"
    rule["autofix"] = False
    checker = StaticChecker([sample_finding()])

    report = RuleEngine({"R01": checker}).check(Document(), Ruleset.model_validate(ruleset_data))

    assert checker.calls == 1
    assert report.checked_rules == ("R01",)
    assert report.unavailable_rules == ()
    finding = report.findings[0]
    assert finding.location.section == 1
    assert finding.actual == 20 and finding.expected == 25
    assert finding.severity == "warning" and not finding.fixable
    assert finding.quote == rule["quote"]
    assert report.summary.warnings == 1
    assert report.exit_code() == 0


def test_empty_registered_check_is_checked(ruleset_data):
    report = RuleEngine({"R01": StaticChecker()}).check(
        Document(), Ruleset.model_validate(ruleset_data)
    )
    assert report.findings == ()
    assert report.checked_rules == ("R01",)
    assert report.summary.status == "no_errors"
    assert report.exit_code() == 0


def test_runtime_uncertainty_remains_manual(ruleset_data):
    finding = sample_finding(severity="manual", fixable=False, actual=None)
    report = RuleEngine({"R01": StaticChecker([finding])}).check(
        Document(), Ruleset.model_validate(ruleset_data)
    )
    assert report.findings[0].severity == "manual"
    assert report.summary.errors == report.summary.fixable == 0
    assert report.exit_code() == 3


def test_configured_manual_rule_does_not_run_checker(ruleset_data):
    rule = ruleset_data["rules"][0]
    rule.update(severity="manual", autofix=False, manual_reason="Згенерована ручна перевірка.")
    checker = StaticChecker([sample_finding()])

    report = RuleEngine({"R01": checker}).check(Document(), Ruleset.model_validate(ruleset_data))

    assert checker.calls == 0
    assert report.findings[0].message == rule["manual_reason"]
    assert report.findings[0].severity == "manual"


def test_draft_profile_does_not_produce_automatic_verdict(ruleset_data):
    ruleset_data["status"] = "draft"
    checker = StaticChecker([sample_finding()])
    report = RuleEngine({"R01": checker}).check(Document(), Ruleset.model_validate(ruleset_data))
    assert checker.calls == 0
    assert report.findings[0].severity == "manual"
    assert report.exit_code() == 3


def test_failed_generator_discards_partial_results_and_does_not_leak(ruleset_data, capsys, caplog):
    class BrokenChecker:
        def check(self, document, rule, ruleset):
            yield sample_finding()
            raise RuntimeError("SYNTHETIC_PRIVATE_IDENTIFIER")

    report = RuleEngine({"R01": BrokenChecker()}).check(
        Document(), Ruleset.model_validate(ruleset_data)
    )
    assert report.failed_rules == ("R01",)
    assert report.checked_rules == ()
    assert len(report.findings) == 1
    assert report.findings[0].severity == "manual"
    assert "SYNTHETIC_PRIVATE_IDENTIFIER" not in report.model_dump_json()
    assert report.summary.errors == 0
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""
    assert caplog.records == []


def test_mismatched_finding_is_not_accepted(ruleset_data):
    report = RuleEngine({"R01": StaticChecker([sample_finding(rule_id="R02")])}).check(
        Document(), Ruleset.model_validate(ruleset_data)
    )
    assert report.failed_rules == ("R01",)
    assert report.findings[0].rule_id == "R01"
    assert report.findings[0].severity == "manual"


def test_failed_check_does_not_abort_remaining_rules(ruleset_data):
    class BrokenChecker:
        def check(self, document, rule, ruleset):
            raise RuntimeError("Згенерована помилка перевірки.")

    second = {**ruleset_data["rules"][0], "id": "R02"}
    ruleset_data["rules"].append(second)
    report = RuleEngine(
        {"R01": BrokenChecker(), "R02": StaticChecker([sample_finding(rule_id="R02")])}
    ).check(Document(), Ruleset.model_validate(ruleset_data))

    assert report.failed_rules == ("R01",)
    assert report.checked_rules == ("R02",)
    assert [item.rule_id for item in report.findings] == ["R01", "R02"]
    assert report.summary.errors == report.summary.manual == 1


def test_source_notes_identify_user_selected_parameters():
    report = RuleEngine({}).check(Document(), load_ruleset(), document_type="laboratory_report")
    finding = next(item for item in report.findings if item.rule_id == "R09")
    assert finding.parameter_sources["numbering"] == "user_reference"
    assert finding.source_notes["user_reference"]
    assert "Лабораторна робота" in finding.source_notes["user_reference"]
    assert finding.quote == load_ruleset().rules[8].quote


@pytest.mark.parametrize("prewrapped", [False, True])
def test_checkers_receive_effective_formatting_model(ruleset_data, tmp_path, prewrapped):
    path = tmp_path / "generated.docx"
    generated = Document()
    style = generated.styles.add_style("Generated Body", WD_STYLE_TYPE.PARAGRAPH)
    style.font.name, style.font.size = "Times New Roman", Pt(14)
    style.paragraph_format.line_spacing = 1.5
    generated.add_paragraph("Згенерований текст", style)
    generated.save(path)
    original = path.read_bytes()
    document = load_document(path)
    argument = DocumentModel(document) if prewrapped else document
    received = []

    class ModelChecker:
        def check(self, model, rule, ruleset):
            received.append(model)
            paragraph = model.paragraphs[0]
            formatting = model.run_formatting(model.runs(paragraph)[0])
            assert formatting.fonts["hAnsi"].value == "Times New Roman"
            assert formatting.size_pt.value == 14
            assert model.effective_line_spacing(paragraph).value.multiplier == 1.5
            return ()

    report = RuleEngine({"R01": ModelChecker()}).check(
        argument, Ruleset.model_validate(ruleset_data)
    )

    assert report.checked_rules == ("R01",)
    assert isinstance(received[0], DocumentModel)
    assert received[0].document is document
    if prewrapped:
        assert received[0] is argument
    assert path.read_bytes() == original
