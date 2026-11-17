"""Synthetic inputs shared by report, ruleset, and CLI tests."""

import pytest
from docx import Document
from fixtures.make_fixtures import generate_fixtures

from oformleno.engine import RuleEngine
from oformleno.loader import load_document
from oformleno.ruleset import load_ruleset


@pytest.fixture(scope="session")
def eom_fixtures(tmp_path_factory):
    """Reusable saved EOM examples; no generated document is stored in the repo."""
    return generate_fixtures(tmp_path_factory.mktemp("eom-fixtures"))


@pytest.fixture
def body_check(tmp_path):
    """Run a real registered body rule after saving/reopening a generated DOCX."""

    def run(document, rule_id, *, parameters=None, body_text_mode="styles"):
        path = tmp_path / "generated.docx"
        document.save(path)
        ruleset = load_ruleset()
        if parameters is not None:
            ruleset = ruleset.model_copy(
                update={
                    "rules": tuple(
                        rule.model_copy(update={"params": parameters})
                        if rule.id == rule_id
                        else rule
                        for rule in ruleset.rules
                    )
                }
            )
        report = RuleEngine().check(
            load_document(path),
            ruleset,
            document_type="laboratory_report",
            body_text_mode=body_text_mode,
        )
        assert not report.failed_rules
        return tuple(finding for finding in report.findings if finding.rule_id == rule_id)

    return run


@pytest.fixture
def synthetic_docx(tmp_path):
    path = tmp_path / "generated.docx"
    document = Document()
    document.add_paragraph("Згенерований основний текст.")
    document.add_table(rows=1, cols=1).cell(0, 0).text = "Згенерована комірка"
    document.save(path)
    return path


@pytest.fixture
def ruleset_data():
    return {
        "id": "generated-guideline",
        "title": "Згенеровані вимоги",
        "source": "Згенероване джерело",
        "rules": [
            {
                "id": "R01",
                "name": "Згенероване правило",
                "params": {"width_mm": 210, "height_mm": 297},
                "severity": "error",
                "autofix": True,
                "quote": "Цитата зі згенерованого джерела.",
            }
        ],
    }
