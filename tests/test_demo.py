"""Verify pitch artifact expectations independently of the generating script."""

import importlib.util
import json
from collections import Counter
from pathlib import Path

import pytest
from docx import Document
from lxml import etree

from oformleno.engine import RuleEngine
from oformleno.ruleset import load_ruleset

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "make_demo.py"
spec = importlib.util.spec_from_file_location("oformleno_demo", SCRIPT)
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)


def test_demo_has_ten_errors_nine_fixes_and_a_real_residual_caption(tmp_path):
    paths = demo.generate_demo(tmp_path)
    original = paths[demo.BAD_NAME].read_bytes()
    before_document = Document(paths[demo.BAD_NAME])
    assert before_document.paragraphs[0].style.name == "Normal"
    assert before_document.paragraphs[0].runs[0].font.name == "Calibri"
    assert before_document.paragraphs[0].runs[0].font.size.pt == 12
    before = RuleEngine().check(
        before_document,
        load_ruleset(),
        document_type="laboratory_report",
        body_text_mode="ordinary",
    )
    after_document = Document(paths[demo.COPY_NAME])
    after = RuleEngine().check(
        after_document, load_ruleset(), document_type="laboratory_report", body_text_mode="ordinary"
    )
    assert Counter(item.rule_id for item in before.findings if item.severity == "error") == {
        "R01": 1,
        "R02": 4,
        "R03": 1,
        "R04": 1,
        "R05": 1,
        "R06": 1,
        "R08": 1,
    }
    assert before.summary.errors == 10 and before.summary.fixable == 9
    assert after.summary.errors == 1 and after.summary.fixable == 0
    assert [item.rule_id for item in after.findings if item.severity == "error"] == ["R08"]
    assert before.summary.manual == after.summary.manual == 7
    assert paths[demo.BAD_NAME].read_bytes() == original
    assert [p.text for p in after_document.paragraphs] == [
        p.text for p in before_document.paragraphs
    ]
    assert [etree.tostring(t._tbl) for t in before_document.tables] == [
        etree.tostring(t._tbl) for t in after_document.tables
    ]
    manifest = json.loads(paths["manifest.json"].read_text())
    assert manifest["synthetic"] and manifest["body_text_mode"] == "ordinary"
    assert json.loads(paths["after.json"].read_text())["summary"]["errors"] == 1


def test_demo_refuses_to_replace_existing_artifacts(tmp_path):
    existing = tmp_path / demo.BAD_NAME
    existing.write_bytes(b"original synthetic artifact")
    with pytest.raises(FileExistsError):
        demo.generate_demo(tmp_path)
    assert existing.read_bytes() == b"original synthetic artifact"
    assert list(tmp_path.iterdir()) == [existing]
