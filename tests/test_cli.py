"""Exercise the actual Ukrainian entry point with generated documents."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

import oformleno.cli as cli
from oformleno.engine import Finding, Location, RuleEngine


def invoke(monkeypatch, capsys, *arguments):
    monkeypatch.setattr(sys, "argv", ["oformleno", *map(str, arguments)])
    with pytest.raises(SystemExit) as stopped:
        cli.main()
    captured = capsys.readouterr()
    return stopped.value.code, captured.out, captured.err


@pytest.mark.parametrize("mode", [None, "styles", "ordinary"])
def test_body_mode_check_and_fix_use_same_scope(eom_fixtures, tmp_path, monkeypatch, capsys, mode):
    from docx import Document
    from docx.shared import Pt

    document = Document(eom_fixtures["good"])
    paragraph = document.paragraphs[0]
    paragraph.style = "Normal"
    paragraph.runs[0].font.name = "Calibri"
    paragraph.runs[0].font.size = Pt(12)
    paragraph.paragraph_format.line_spacing = 1
    source, destination = tmp_path / "source.docx", tmp_path / "copy.docx"
    document.save(source)
    original = source.read_bytes()
    options = ["--document-type", "laboratory_report"]
    if mode is not None:
        options += ["--body-text-mode", mode]
    code, out, err = invoke(monkeypatch, capsys, "check", source, *options)
    report = json.loads(out)
    assert not err and report["body_text_mode"] == (mode or "styles")
    assert report["summary"]["errors"] == (3 if mode == "ordinary" else 0)
    assert code == (1 if mode == "ordinary" else 3)
    code, out, err = invoke(monkeypatch, capsys, "fix", source, "--output", destination, *options)
    result = json.loads(out)
    assert code == 3 and not err
    assert result["before"] == report
    assert result["after"]["body_text_mode"] == (mode or "styles")
    assert result["after"]["summary"]["errors"] == 0
    assert source.read_bytes() == original
    if mode == "ordinary":
        assert set(result["applied_rules"]) == {"R03", "R04", "R05"}
        assert destination.read_bytes() != original
    else:
        assert result["applied_rules"] == [] and destination.read_bytes() == original


@pytest.mark.parametrize("command", ["check", "fix"])
def test_invalid_body_mode_does_not_leak_value_or_create_copy(
    tmp_path, monkeypatch, capsys, command
):
    destination = tmp_path / "copy.docx"
    options = ["--output", str(destination)] if command == "fix" else []
    code, out, err = invoke(
        monkeypatch,
        capsys,
        command,
        tmp_path / "missing.docx",
        *options,
        "--body-text-mode",
        "PRIVATE_MARKER",
    )
    assert code == 2 and not out and not destination.exists()
    assert "PRIVATE_MARKER" not in err and "Невідомий режим" in json.loads(err)["error"]


@pytest.mark.parametrize(
    "arguments", [(), ("--help",), ("check", "--help"), ("fix", "--help"), ("-h",)]
)
def test_help_is_ukrainian(monkeypatch, capsys, arguments):
    code, out, err = invoke(monkeypatch, capsys, *arguments)
    assert code == 0
    assert "Використання:" in out
    assert "Usage:" not in out and "Options:" not in out
    assert err == ""


def test_default_check_outputs_only_json_and_marks_incomplete(eom_fixtures, monkeypatch, capsys):
    source = eom_fixtures["good"]
    code, out, err = invoke(monkeypatch, capsys, "check", source)
    report = json.loads(out)
    assert code == 3
    assert err == ""
    assert report["ruleset_id"] == "lpnu-eom-styles-2026"
    assert report["checked_rules"] == [
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
    ]
    assert report["unavailable_rules"] == []
    assert report["summary"]["manual"] == 8
    assert report["summary"]["status"] == "manual_required"
    assert str(source) not in out
    assert "\\u" not in out


@pytest.mark.parametrize("case,expected_code", [("good", 3), ("bad_r02", 1)])
def test_html_format_outputs_complete_report_with_same_exit_semantics(
    eom_fixtures, monkeypatch, capsys, case, expected_code
):
    from lxml import html

    source = eom_fixtures[case]
    original = source.read_bytes()
    code, out, err = invoke(
        monkeypatch,
        capsys,
        "check",
        source,
        "--format",
        "html",
        "--document-type",
        "laboratory_report",
    )
    tree = html.fromstring(out)
    assert code == expected_code and err == ""
    assert out.startswith("<!doctype html>") and tree.get("lang") == "uk"
    assert "Звіт про оформлення" in tree.text_content()
    assert "Перевірте вручну: 7" in tree.text_content()
    assert str(source) not in out and source.name not in out
    assert source.read_bytes() == original


def test_unknown_report_format_is_sanitized_json_error(synthetic_docx, monkeypatch, capsys):
    marker = "SYNTHETIC_PRIVATE_IDENTIFIER"
    code, out, err = invoke(monkeypatch, capsys, "check", synthetic_docx, "--format", marker)
    assert code == 2 and out == ""
    assert json.loads(err) == {"error": "Невідомий формат звіту. Оберіть json або html."}
    assert marker not in err


def test_html_input_failure_retains_json_stderr_contract(tmp_path, monkeypatch, capsys):
    code, out, err = invoke(
        monkeypatch, capsys, "check", tmp_path / "PRIVATE_INPUT.docx", "--format", "html"
    )
    assert code == 2 and out == ""
    assert json.loads(err)["error"]
    assert "PRIVATE_INPUT" not in err and "Traceback" not in err


def test_work_type_excludes_thesis_count_from_laboratory(eom_fixtures, monkeypatch, capsys):
    code, out, err = invoke(
        monkeypatch, capsys, "check", eom_fixtures["good"], "--document-type", "laboratory_report"
    )
    report = json.loads(out)
    assert code == 3 and err == ""
    assert report["summary"]["manual"] == 7
    assert "M06" in report["not_applicable"]
    assert all(item["rule_id"] != "M06" for item in report["findings"])


@pytest.mark.parametrize(
    "case,rule_id",
    [
        ("bad_r07", "R07"),
        ("bad_r08", "R08"),
        ("bad_r09", "R09"),
        ("bad_r10", "R10"),
        ("bad_r10_first_page", "R10"),
    ],
)
def test_check_only_rules_remain_unfixed(
    eom_fixtures, monkeypatch, capsys, tmp_path, case, rule_id
):
    source = eom_fixtures[case]
    original = source.read_bytes()
    code, out, err = invoke(monkeypatch, capsys, "check", source)
    report = json.loads(out)
    assert code == 1 and err == ""
    errors = [item for item in report["findings"] if item["severity"] == "error"]
    assert len(errors) == 1 and errors[0]["rule_id"] == rule_id
    assert not errors[0]["fixable"]
    destination = tmp_path / "new.docx"
    code, out, err = invoke(monkeypatch, capsys, "fix", source, "--output", destination)
    result = json.loads(out)
    assert code == 1 and err == ""
    assert result["applied_rules"] == [] and result["after"]["summary"]["errors"] == 1
    assert destination.read_bytes() == source.read_bytes() == original


def test_custom_yaml_path(eom_fixtures, tmp_path, ruleset_data, monkeypatch, capsys):
    path = tmp_path / "custom.yaml"
    path.write_text(yaml.safe_dump(ruleset_data, allow_unicode=True), encoding="utf-8")
    code, out, err = invoke(monkeypatch, capsys, "check", eom_fixtures["good"], "--rules", path)
    report = json.loads(out)
    assert code == 0 and err == ""
    assert report["ruleset_id"] == "generated-guideline"
    assert report["checked_rules"] == ["R01"]
    assert report["unavailable_rules"] == []


@pytest.mark.parametrize("kind", ["missing", "invalid_type", "invalid_rules", "unknown_work_type"])
def test_failure_is_json_on_stderr_without_private_inputs(
    synthetic_docx, tmp_path, monkeypatch, capsys, kind
):
    marker = "SYNTHETIC_PRIVATE_IDENTIFIER"
    source = tmp_path / (marker + ".docx")
    arguments = ["check", str(source)]
    if kind == "invalid_type":
        source = tmp_path / (marker + ".pdf")
        source.write_bytes(b"%PDF")
        arguments = ["check", str(source)]
    elif kind == "invalid_rules":
        rules = tmp_path / (marker + ".yaml")
        rules.write_text("invalid: [" + marker, encoding="utf-8")
        arguments = ["check", str(synthetic_docx), "--rules", str(rules)]
    elif kind == "unknown_work_type":
        arguments = ["check", str(synthetic_docx), "--document-type", marker]
    code, out, err = invoke(monkeypatch, capsys, *arguments)
    assert code == 2 and out == ""
    assert isinstance(json.loads(err)["error"], str)
    assert marker not in err
    assert "Traceback" not in err


@pytest.mark.parametrize("arguments", [("check",), ("unknown",), ("--unknown",)])
def test_argument_errors_are_ukrainian_json(monkeypatch, capsys, arguments):
    code, out, err = invoke(monkeypatch, capsys, *arguments)
    assert code == 2 and out == ""
    assert "Не вдалося виконати команду" in json.loads(err)["error"]
    assert "Usage:" not in err and "Error:" not in err


def test_detected_errors_use_exit_one(synthetic_docx, monkeypatch, capsys):
    class SyntheticChecker:
        def check(self, document, rule, ruleset):
            return [
                Finding(
                    rule_id=rule.id,
                    severity="error",
                    location=Location(section=1),
                    actual=20,
                    expected=25,
                    quote=rule.quote,
                    fixable=False,
                    message="Згенероване порушення.",
                )
            ]

    engine = RuleEngine({"R01": SyntheticChecker()})
    monkeypatch.setattr(cli, "RuleEngine", lambda: engine)

    code, out, err = invoke(monkeypatch, capsys, "check", synthetic_docx)

    assert code == 1 and err == ""
    assert json.loads(out)["summary"]["errors"] == 1


def test_installed_entry_point_works_outside_checkout(eom_fixtures, tmp_path):
    executable = Path(sys.executable).parent / "oformleno"
    result = subprocess.run(
        [
            str(executable),
            "check",
            str(eom_fixtures["good"]),
            "--document-type",
            "laboratory_report",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 3 and result.stderr == ""
    assert json.loads(result.stdout)["ruleset_id"] == "lpnu-eom-styles-2026"


def test_left_margin_acceptance_runs_real_checker(eom_fixtures, monkeypatch, capsys):
    source = eom_fixtures["bad_r02"]
    original = source.read_bytes()
    code, out, err = invoke(monkeypatch, capsys, "check", source, "--rules", "lpnu-eom-styles-2026")
    report = json.loads(out)
    assert code == 1 and err == ""
    assert report["checked_rules"] == [
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
    ]
    errors = [item for item in report["findings"] if item["severity"] == "error"]
    assert len(errors) == 1
    assert errors[0]["rule_id"] == "R02"
    assert errors[0]["location"]["section"] == 1
    assert errors[0]["actual"]["left_mm"] == pytest.approx(20, abs=0.01)
    assert errors[0]["expected"] == {"left_mm": 25}
    assert errors[0]["quote"]
    assert str(source) not in out
    assert "Згенерований текст перед вступом" not in out
    assert source.read_bytes() == original


@pytest.mark.parametrize("rule_id,paragraph", [("R03", 1), ("R04", 1), ("R05", 1), ("R06", 2)])
def test_paragraph_rule_errors_use_real_cli_and_location(
    eom_fixtures, monkeypatch, capsys, rule_id, paragraph
):
    source = eom_fixtures["bad_" + rule_id.lower()]
    code, out, err = invoke(monkeypatch, capsys, "check", source)
    report = json.loads(out)
    assert code == 1 and err == ""
    errors = [item for item in report["findings"] if item["severity"] == "error"]
    assert len(errors) == 1 and errors[0]["rule_id"] == rule_id
    assert errors[0]["location"]["paragraph"] == paragraph
    assert len(errors[0]["location"]["excerpt"]) <= 50
    assert errors[0]["quote"]
    assert report["summary"]["manual"] == 8


@pytest.mark.parametrize("rule_id", ["R01", "R02", "R03", "R04", "R05", "R06"])
def test_fix_command_creates_a_copy_and_returns_before_after_reports(
    eom_fixtures, tmp_path, monkeypatch, capsys, rule_id
):
    source = eom_fixtures["bad_" + rule_id.lower()]
    original = source.read_bytes()
    output = tmp_path / "corrected.docx"
    code, out, err = invoke(
        monkeypatch,
        capsys,
        "fix",
        source,
        "--output",
        output,
        "--rules",
        "lpnu-eom-styles-2026",
        "--document-type",
        "laboratory_report",
    )
    report = json.loads(out)
    assert code == 3 and err == ""
    assert report["applied_rules"] == [rule_id]
    assert report["before"]["summary"]["errors"] == report["before"]["summary"]["fixable"] == 1
    assert report["after"]["summary"]["errors"] == report["after"]["summary"]["fixable"] == 0
    assert report["after"]["summary"]["manual"] == 7
    assert source.read_bytes() == original
    assert output.exists() and output.read_bytes() != original
    assert str(source) not in out and str(output) not in out


@pytest.mark.parametrize(
    "problem", ["same_path", "existing", "missing_output", "wrong_extension", "unknown_type"]
)
def test_fix_errors_are_sanitized_and_preserve_inputs(
    eom_fixtures, tmp_path, monkeypatch, capsys, problem
):
    source = eom_fixtures["bad_r02"]
    original = source.read_bytes()
    output = tmp_path / "SYNTHETIC_PRIVATE_IDENTIFIER.docx"
    arguments = ["fix", source, "--output", output]
    if problem == "same_path":
        arguments = ["fix", source, "--output", source]
    elif problem == "existing":
        output.write_bytes(b"preserve unrelated file")
    elif problem == "missing_output":
        arguments = ["fix", source]
    elif problem == "wrong_extension":
        arguments = ["fix", source, "--output", output.with_suffix(".pdf")]
    else:
        arguments.extend(["--document-type", "SYNTHETIC_PRIVATE_IDENTIFIER"])
    code, out, err = invoke(monkeypatch, capsys, *arguments)
    assert code == 2 and out == ""
    assert isinstance(json.loads(err)["error"], str)
    assert "SYNTHETIC_PRIVATE_IDENTIFIER" not in err
    assert "Traceback" not in err and "Usage:" not in err
    assert source.read_bytes() == original
    if problem == "existing":
        assert output.read_bytes() == b"preserve unrelated file"
    else:
        assert not output.exists()


def test_installed_fix_entry_point_works_outside_checkout(eom_fixtures, tmp_path):
    executable = Path(sys.executable).parent / "oformleno"
    source = eom_fixtures["bad_r03"]
    original = source.read_bytes()
    output = tmp_path / "corrected.docx"
    result = subprocess.run(
        [str(executable), "fix", str(source), "--output", str(output)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 3 and result.stderr == ""
    report = json.loads(result.stdout)
    assert report["applied_rules"] == ["R03"]
    assert report["after"]["summary"]["errors"] == 0
    assert output.exists() and source.read_bytes() == original
