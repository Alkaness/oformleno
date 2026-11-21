"""Blinded-reference invariants and meaningful holdout metric boundaries."""

import importlib.util
from copy import deepcopy
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "holdout_score", Path(__file__).resolve().parents[1] / "scripts/score_holdout.py"
)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def fixture():
    reference = {
        "status": "sealed",
        "runtime_sha256": "a" * 64,
        "body_text_mode": "ordinary",
        "documents": [],
    }
    run = {"runtime_sha256": "a" * 64, "body_text_mode": "ordinary", "documents": []}
    for index in range(3):
        identifier = f"synthetic-{index}"
        reference["documents"].append(
            {
                "id": identifier,
                "artifact_sha256": module.digest({"synthetic": identifier}),
                "core_coverage_complete": True,
                "units": [
                    {
                        "rule": "R03",
                        "paragraph": 1,
                        "verdict": "violation",
                        "properties": {"font": "violation"},
                    }
                ],
            }
        )
        run["documents"].append(
            {
                "id": identifier,
                "artifact_sha256": module.digest({"synthetic": identifier}),
                "findings": [
                    {"rule": "R03", "paragraph": 1, "severity": "error", "properties": ["font"]}
                ],
            }
        )
    run["sealed_reference_sha256"] = module.digest(reference)
    return reference, run


def test_manual_violation_is_a_miss_not_a_true_positive():
    reference, run = fixture()
    run["documents"][0]["findings"][0]["severity"] = "manual"
    result = module.score(reference, run)
    assert result["totals"]["true_positive"] == 2
    assert result["totals"]["core_false_negative"] == 1
    assert result["precision"] == 1 and result["recall_r01_r06"] == pytest.approx(2 / 3)


def test_unresolved_opportunity_blocks_recall_without_inventing_a_true_negative():
    reference, run = fixture()
    reference["documents"][0]["units"].append(
        {"rule": "R04", "paragraph": 2, "verdict": "unresolved"}
    )
    run["sealed_reference_sha256"] = module.digest(reference)
    result = module.score(reference, run)
    assert result["precision"] == 1 and result["recall_r01_r06"] is None
    assert result["recall_on_known_violations_only"] == 1 and not result["claim_ready"]


def test_automatic_error_outside_independent_reference_blocks_precision():
    reference, run = fixture()
    run["documents"][0]["findings"].append({"rule": "R08", "paragraph": 5, "severity": "error"})
    result = module.score(reference, run)
    assert result["precision"] is None and result["totals"]["pending"] == 1
    assert not result["claim_ready"]


def test_unknown_severity_cannot_hide_an_unreviewed_prediction():
    reference, run = fixture()
    run["documents"][0]["findings"].append({"rule": "R08", "paragraph": 5, "severity": "typo"})
    with pytest.raises(ValueError):
        module.score(reference, run)


def test_compound_finding_with_a_false_property_is_not_all_true_positive():
    reference, run = fixture()
    unit = reference["documents"][0]["units"][0]
    unit.update(rule="R06", properties={"align": "violation", "bold": "conformant"})
    run["documents"][0]["findings"][0].update(rule="R06", properties=["align", "bold"])
    run["sealed_reference_sha256"] = module.digest(reference)
    result = module.score(reference, run)
    assert result["totals"]["false_positive"] == 1
    assert result["totals"]["core_false_negative"] == 1
    assert result["precision"] == pytest.approx(2 / 3)


@pytest.mark.parametrize(
    "change", ["reference", "artifact", "mode", "runtime", "unsealed", "duplicate"]
)
def test_stale_or_invalid_evidence_is_rejected(change):
    reference, run = fixture()
    if change == "reference":
        reference["documents"][0]["units"][0]["verdict"] = "conformant"
    elif change == "artifact":
        run["documents"][0]["artifact_sha256"] = "changed"
    elif change == "mode":
        run["body_text_mode"] = "styles"
    elif change == "runtime":
        run["runtime_sha256"] = "changed"
    elif change == "unsealed":
        reference["status"] = "draft"
    else:
        run["documents"].append(deepcopy(run["documents"][0]))
    with pytest.raises(ValueError):
        module.score(reference, run)


@pytest.mark.parametrize("status", ["pending", "typo", None])
def test_unknown_property_status_cannot_become_a_true_positive(status):
    reference, run = fixture()
    reference["documents"][0]["units"][0]["properties"]["font"] = status
    run["sealed_reference_sha256"] = module.digest(reference)
    with pytest.raises(ValueError):
        module.score(reference, run)


@pytest.mark.parametrize("field", ["runtime_sha256", "body_text_mode", "artifact_sha256"])
@pytest.mark.parametrize("value", [None, ""])
def test_matching_missing_provenance_is_not_valid(field, value):
    reference, run = fixture()
    if field == "artifact_sha256":
        reference["documents"][0][field] = run["documents"][0][field] = value
    else:
        reference[field] = run[field] = value
    run["sealed_reference_sha256"] = module.digest(reference)
    with pytest.raises(ValueError):
        module.score(reference, run)


@pytest.mark.parametrize(
    "verdict,properties",
    [
        ("violation", {}),
        ("violation", {"font": "conformant"}),
        ("conformant", {"font": "violation"}),
        ("conformant", {"font": "unresolved"}),
    ],
)
def test_contradictory_reference_is_rejected(verdict, properties):
    reference, run = fixture()
    reference["documents"][0]["units"][0].update(verdict=verdict, properties=properties)
    run["sealed_reference_sha256"] = module.digest(reference)
    with pytest.raises(ValueError):
        module.score(reference, run)


def test_distinct_noncore_header_findings_remain_separate_pending_items():
    reference, run = fixture()
    run["documents"][0]["findings"].extend(
        [
            {"rule": "R10", "section": 1, "unit": "default:font", "severity": "error"},
            {"rule": "R10", "section": 1, "unit": "even:font", "severity": "error"},
        ]
    )
    result = module.score(reference, run)
    assert result["totals"]["pending"] == 2 and result["precision"] is None
