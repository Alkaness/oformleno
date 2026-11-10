"""Verify the guard against committing student documents."""

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_documents.py"


@pytest.mark.parametrize("name", ["work.docx", "WORK.DOCX", "work.doc"])
def test_rejects_document_paths_without_disclosing_names(name):
    result = subprocess.run([sys.executable, str(SCRIPT), name], capture_output=True, text=True)

    assert result.returncode == 1
    assert "Не додавайте" in result.stderr
    assert name not in result.stderr


def test_allows_fixture_generator_and_source():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "tests/fixtures/make_fixtures.py", "src/oformleno/loader.py"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0


def test_checks_force_added_document(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text("*.docx\n", encoding="utf-8")
    (tmp_path / "work.docx").write_bytes(b"synthetic staged document")
    subprocess.run(["git", "-C", str(tmp_path), "add", "-f", "work.docx"], check=True)

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--tracked"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "work.docx" not in result.stderr
