"""Research metrics must not turn automatic output into reference truth."""

import importlib.util
import json
from copy import deepcopy
from io import BytesIO
from pathlib import Path

import pytest
from docx import Document

from oformleno.engine import Finding, Location, Report

spec = importlib.util.spec_from_file_location(
    "evaluation", Path(__file__).resolve().parents[1] / "scripts/evaluate_corpus.py"
)
evaluation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluation)


def finding(identifier="F0001", rule="R04", severity="error", paragraph=1):
    return {
        "id": identifier,
        "rule": rule,
        "severity": severity,
        "location": {"paragraph": paragraph},
        "fixable": severity == "error",
    }


def run_data():
    return {
        "all_sources_unchanged": True,
        "documents": [
            {
                "id": name,
                "before": {
                    "findings": [finding()],
                    "failed_rules": [],
                    "unavailable_rules": [],
                },
                "source_unchanged": True,
                "correction_status": "created",
                "corrected_sha256": "a" * 64,
                "corrected_unchanged_after_open": True,
                "preservation": dict.fromkeys(
                    (
                        "same_package_entries",
                        "other_part_payloads_identical",
                        "content_structure_identical",
                    ),
                    True,
                ),
                "libreoffice": {"status": "opened_exported", "other_diagnostic_lines": 0},
            }
            for name in evaluation.REPORTS
        ],
    }


def reviewed(run):
    review = evaluation.review_template(run)
    for row in review["documents"]:
        for error in row["errors"]:
            error.update(verdict="true_positive", evidence="Independent format inspection.")
        row["coverage"] = dict.fromkeys(evaluation.RULES, True)
        row["coverage_evidence"] = "All applicable elements reviewed, including abstentions."
        row["word"].update(status="opened_without_warnings", evidence="Word open observation.")
    return review


def test_metadata_allowlist_cannot_export_document_text():
    report = Report(
        ruleset_id="profile",
        ruleset_title="Profile",
        findings=(
            Finding(
                rule_id="R04",
                severity="error",
                location=Location(paragraph=1, excerpt="PRIVATE_EXCERPT"),
                actual={"PRIVATE_KEY": "PRIVATE_VALUE"},
                expected="PRIVATE_EXPECTED",
                message="PRIVATE_MESSAGE",
                quote="PRIVATE_QUOTE",
                rule_name="PRIVATE_NAME",
            ),
        ),
    )
    output = evaluation.compact_report(report)
    assert "PRIVATE" not in str(output)
    assert output["findings"][0]["location"] == {"paragraph": 1}


def test_unreviewed_run_has_no_precision_recall_or_pass():
    run = run_data()
    result = evaluation.score(run, evaluation.review_template(run))
    assert result["pending_error_reviews"] == 10
    assert result["precision"] is None
    assert result["recall_r01_r06"] is None
    assert not result["checkpoint_ready"]


def test_complete_independent_reviews_and_both_office_checks_can_pass():
    run = run_data()
    result = evaluation.score(run, reviewed(run))
    assert result["precision"] == result["recall_r01_r06"] == 1
    assert result["checkpoint_ready"]


def test_manual_violation_is_missed_error_never_a_true_positive():
    run = run_data()
    run["documents"][0]["before"]["findings"].append(finding("F0002", "R04", "manual", 2))
    review = reviewed(run)
    row = review["documents"][0]
    row["manual"][0].update(status="violation", evidence="Independent size measurement.")
    row["missed_errors"] = [
        {
            "id": "miss-1",
            "rule": "R04",
            "location": {"paragraph": 2},
            "manual_finding_id": "F0002",
            "evidence": "Confirmed body paragraph with wrong size.",
        }
    ]
    result = evaluation.score(run, review)
    assert result["confirmed_true_positives"] == {"R04": 10}
    assert result["confirmed_missed_errors"] == {"R04": 1}
    assert result["recall_r01_r06"] == pytest.approx(10 / 11)


def test_manuals_cannot_be_injected_into_true_positives():
    run = run_data()
    run["documents"][0]["before"]["findings"].append(finding("F0002", "M01", "manual"))
    review = reviewed(run)
    review["documents"][0]["errors"].append(
        {"finding_id": "F0002", "verdict": "true_positive", "evidence": "No."}
    )
    with pytest.raises(ValueError):
        evaluation.score(run, review)


def test_unresolved_manual_blocks_recall_but_checklist_is_separate():
    run = run_data()
    run["documents"][0]["before"]["findings"].extend(
        [finding("F0002", "R04", "manual"), finding("F0003", "M01", "manual")]
    )
    review = reviewed(run)
    result = evaluation.score(run, review)
    assert result["precision"] == 1
    assert result["recall_r01_r06"] is None
    assert result["unresolved_automatic_manual_findings"] == 1
    review["documents"][0]["manual"][0].update(
        status="no_violation", evidence="Independent inspection."
    )
    assert evaluation.score(run, review)["recall_r01_r06"] == 1


def test_caption_abstention_does_not_block_reviewed_core_recall_or_checkpoint():
    run = run_data()
    run["documents"][0]["before"]["findings"].append(finding("F0002", "R08", "manual"))
    review = reviewed(run)
    review["documents"][0]["coverage"]["R08"] = False
    result = evaluation.score(run, review)
    assert not result["reference_complete"]
    assert result["recall_reference_complete"]
    assert result["unresolved_automatic_manual_findings"] == 1
    assert result["unresolved_recall_manual_findings"] == 0
    assert result["recall_r01_r06"] == 1 and result["checkpoint_ready"]


def test_missing_core_coverage_still_blocks_recall_after_all_error_reviews():
    run = run_data()
    review = reviewed(run)
    review["documents"][0]["coverage"]["R03"] = False
    result = evaluation.score(run, review)
    assert result["precision"] == 1
    assert not result["recall_reference_complete"]
    assert result["recall_r01_r06"] is None and not result["checkpoint_ready"]


def test_unreviewed_caption_error_blocks_precision_but_not_core_recall():
    run = run_data()
    run["documents"][0]["before"]["findings"].append(finding("F0002", "R08"))
    review = reviewed(run)
    review["documents"][0]["errors"][1]["verdict"] = "pending"
    result = evaluation.score(run, review)
    assert result["recall_r01_r06"] == 1
    assert result["precision"] is None and not result["checkpoint_ready"]


def test_manual_violation_requires_matching_missed_error():
    run = run_data()
    run["documents"][0]["before"]["findings"].append(finding("F0002", "R04", "manual"))
    review = reviewed(run)
    review["documents"][0]["manual"][0].update(status="violation", evidence="Wrong size.")
    with pytest.raises(ValueError):
        evaluation.score(run, review)


def test_manual_link_cannot_claim_a_different_location():
    run = run_data()
    run["documents"][0]["before"]["findings"].append(finding("F0002", "R04", "manual"))
    review = reviewed(run)
    row = review["documents"][0]
    row["manual"][0].update(status="violation", evidence="Size.")
    row["missed_errors"] = [
        {
            "id": "miss-1",
            "rule": "R04",
            "location": {"paragraph": 99},
            "manual_finding_id": "F0002",
            "evidence": "Different paragraph.",
        }
    ]
    with pytest.raises(ValueError):
        evaluation.score(run, review)


@pytest.mark.parametrize("mutation", ["changed_run", "duplicate_report", "missing_error"])
def test_stale_or_incomplete_reviews_are_rejected(mutation):
    run = run_data()
    review = reviewed(run)
    if mutation == "changed_run":
        run["documents"][0]["source_unchanged"] = False
    elif mutation == "duplicate_report":
        review["documents"][1] = deepcopy(review["documents"][0])
    else:
        review["documents"][0]["errors"].clear()
    with pytest.raises(ValueError):
        evaluation.score(run, review)


def test_labels_without_evidence_do_not_establish_precision():
    run = run_data()
    review = reviewed(run)
    review["documents"][0]["errors"][0]["evidence"] = ""
    assert evaluation.score(run, review)["precision"] is None


def test_partial_review_reports_bounds_without_claiming_complete_accuracy():
    run = run_data()
    review = reviewed(run)
    review["documents"][0]["errors"][0]["verdict"] = "false_positive"
    review["documents"][1]["errors"][0]["verdict"] = "pending"
    review["documents"][0]["missed_errors"] = [
        {"id": "miss-1", "rule": "R04", "location": {"paragraph": 2}, "evidence": "Size."}
    ]
    review["documents"][0]["coverage"]["R04"] = False
    result = evaluation.score(run, review)
    assert result["precision"] is None
    assert result["precision_upper_bound"] == pytest.approx(9 / 10)
    assert result["recall_r01_r06"] is None
    assert result["recall_upper_bound_r01_r06"] == pytest.approx(9 / 10)


def test_caption_false_positive_affects_precision_and_not_core_recall():
    run = run_data()
    run["documents"][0]["before"]["findings"].append(finding("F0002", "R08"))
    review = reviewed(run)
    review["documents"][0]["errors"][1]["verdict"] = "false_positive"
    review["documents"][0]["missed_errors"] = [
        {"id": "miss-1", "rule": "R08", "location": {"paragraph": 2}, "evidence": "Fields."}
    ]
    result = evaluation.score(run, review)
    assert result["precision"] == pytest.approx(10 / 11)
    assert result["recall_r01_r06"] == 1
    assert result["confirmed_missed_errors"] == {"R08": 1}


@pytest.mark.parametrize("count, passes", [(2, True), (3, False)])
def test_recall_threshold_includes_all_undetected_errors(count, passes):
    run = run_data()
    review = reviewed(run)
    review["documents"][0]["missed_errors"] = [
        {"id": f"miss-{i}", "rule": "R04", "location": {"paragraph": i + 2}, "evidence": "Size."}
        for i in range(count)
    ]
    result = evaluation.score(run, review)
    assert result["recall_r01_r06"] == pytest.approx(10 / (10 + count))
    assert result["checkpoint_ready"] is passes


@pytest.mark.parametrize("kind", ["word_hash", "word_pending", "lo_warning", "source", "parts"])
def test_compatibility_and_preservation_are_required_per_report(kind):
    run = run_data()
    if kind == "lo_warning":
        run["documents"][0]["libreoffice"]["other_diagnostic_lines"] = 1
    elif kind == "source":
        run["documents"][0]["source_unchanged"] = False
    elif kind == "parts":
        run["documents"][0]["preservation"]["other_part_payloads_identical"] = False
    review = reviewed(run)
    if kind == "word_hash":
        review["documents"][0]["word"]["corrected_sha256"] = "b" * 64
    elif kind == "word_pending":
        review["documents"][0]["word"]["status"] = "pending"
    assert not evaluation.score(run, review)["checkpoint_ready"]


def test_duplicate_missed_units_rejected_but_separate_margins_allowed():
    run = run_data()
    review = reviewed(run)
    missed = {"id": "miss-1", "rule": "R02", "location": {"section": 1}, "evidence": "Margin."}
    review["documents"][0]["missed_errors"] = [
        {**missed, "unit": "left_mm"},
        {**missed, "id": "miss-2", "unit": "right_mm"},
    ]
    assert evaluation.score(run, review)["confirmed_missed_errors"] == {"R02": 2}
    review["documents"][0]["missed_errors"][1]["unit"] = "left_mm"
    with pytest.raises(ValueError):
        evaluation.score(run, review)


def test_preservation_audit_detects_text_loss_without_product_signature():
    document = Document()
    document.add_paragraph("Synthetic content")
    source = BytesIO()
    document.save(source)
    document.paragraphs[0].text = "Different synthetic content"
    changed = BytesIO()
    document.save(changed)
    result = evaluation.preservation(source.getvalue(), changed.getvalue())
    assert not result["content_structure_identical"]
    assert result["other_part_payloads_identical"]


@pytest.fixture
def resumable_corpus(tmp_path, monkeypatch, eom_fixtures):
    root = tmp_path / "project"
    corpus = root / "private/corpus"
    corpus.mkdir(parents=True)
    rules = root / "rulesets"
    rules.mkdir()
    (rules / "lpnu-eom-styles-2026.yaml").write_bytes(
        (evaluation.ROOT / "rulesets/lpnu-eom-styles-2026.yaml").read_bytes()
    )
    content = eom_fixtures["good"].read_bytes()
    manifest = []
    for name in evaluation.REPORTS:
        (corpus / f"{name}.docx").write_bytes(content)
        manifest.append({"id": name, "copy_sha256": evaluation.digest(content)})
    (corpus / "manifest.json").write_text(json.dumps({"reports": manifest}))
    monkeypatch.setattr(evaluation, "ROOT", root)
    monkeypatch.setattr(evaluation, "code_digest", lambda: "synthetic-code-version")
    return corpus, root / "private/run", content


def interrupt_collection(monkeypatch, checkpoint_name):
    original = evaluation.write_json

    def save_then_interrupt(path, data):
        original(path, data)
        if path.name == checkpoint_name:
            raise KeyboardInterrupt

    monkeypatch.setattr(evaluation, "write_json", save_then_interrupt)
    return original


def test_interrupted_collection_resumes_completed_checks_and_preserves_review(
    resumable_corpus, monkeypatch
):
    corpus, output, content = resumable_corpus
    writer = interrupt_collection(monkeypatch, "report-02.json")
    with pytest.raises(KeyboardInterrupt):
        evaluation.collect(corpus, output, False)
    assert len(list((output / "checks").glob("*.json"))) == 2
    assert not (output / "run.json").exists()
    monkeypatch.setattr(evaluation, "write_json", writer)
    original_fix = evaluation.fix_document_bytes
    calls = []

    def track_fix(*args, **kwargs):
        calls.append(True)
        return original_fix(*args, **kwargs)

    monkeypatch.setattr(evaluation, "fix_document_bytes", track_fix)
    run = evaluation.collect(corpus, output, False, resume=True)
    assert len(calls) == 8
    assert len(run["documents"]) == 10 and run["all_sources_unchanged"]
    assert all(p.read_bytes() == content for p in (output / "corrected").glob("*.docx"))
    review_path = output / "review.json"
    review = json.loads(review_path.read_text())
    review["documents"][0]["coverage"]["R01"] = True
    review_path.write_text(json.dumps(review))
    reviewed_bytes = review_path.read_bytes()
    assert evaluation.collect(corpus, output, False, resume=True) == run
    assert len(calls) == 8 and review_path.read_bytes() == reviewed_bytes
    assert not list(output.rglob(".evaluation-*"))


def test_resume_adopts_identical_copy_written_before_checkpoint(resumable_corpus, monkeypatch):
    corpus, output, _ = resumable_corpus
    original = evaluation.write_json

    def interrupt_before_checkpoint(path, data):
        if path.name == "report-01.json":
            raise KeyboardInterrupt
        original(path, data)

    monkeypatch.setattr(evaluation, "write_json", interrupt_before_checkpoint)
    with pytest.raises(KeyboardInterrupt):
        evaluation.collect(corpus, output, False)
    copy = output / "corrected/report-01.docx"
    identity = copy.stat().st_ino
    assert copy.exists() and not (output / "checks/report-01.json").exists()
    monkeypatch.setattr(evaluation, "write_json", original)
    run = evaluation.collect(corpus, output, False, resume=True)
    assert copy.stat().st_ino == identity
    assert all(row["correction_status"] == "created" for row in run["documents"])


@pytest.mark.parametrize("changed", ["code", "mode", "source", "corrected_copy"])
def test_resume_rejects_changed_inputs_or_evidence(resumable_corpus, monkeypatch, changed):
    corpus, output, _ = resumable_corpus
    writer = interrupt_collection(monkeypatch, "report-01.json")
    with pytest.raises(KeyboardInterrupt):
        evaluation.collect(corpus, output, False)
    monkeypatch.setattr(evaluation, "write_json", writer)
    if changed == "code":
        monkeypatch.setattr(evaluation, "code_digest", lambda: "different-synthetic-version")
    elif changed == "source":
        (corpus / "report-01.docx").write_bytes(b"changed synthetic input")
    elif changed == "corrected_copy":
        (output / "corrected/report-01.docx").write_bytes(b"changed synthetic output")
    with pytest.raises(ValueError):
        evaluation.collect(corpus, output, changed == "mode", resume=True)
    assert not (output / "checks/report-02.json").exists()


def test_atomic_evidence_writes_never_replace_existing_file(tmp_path):
    path = tmp_path / "evidence.json"
    evaluation.write_json(path, {"initial": True})
    original = path.read_bytes()
    assert path.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        evaluation.write_json(path, {"initial": False})
    assert path.read_bytes() == original and not list(tmp_path.glob(".evaluation-*"))
