"""Smoke test the dependency using an actual generated DOCX package."""

from docx import Document


def test_generated_docx_round_trip(tmp_path):
    path = tmp_path / "generated.docx"
    document = Document()
    document.add_paragraph("Згенерована робота для перевірки середовища.")
    document.add_table(rows=1, cols=1).cell(0, 0).text = "Тестові дані"
    document.save(path)

    reopened = Document(path)

    assert reopened.paragraphs[0].text == "Згенерована робота для перевірки середовища."
    assert reopened.tables[0].cell(0, 0).text == "Тестові дані"
