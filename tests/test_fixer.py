"""New-copy fixes, real rechecks, exact package preservation and publication safety."""

import os
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest
from docx import Document
from docx.enum.section import WD_ORIENT, WD_SECTION_START
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm, Pt
from fixtures.make_fixtures import BODY_BASE_STYLE, BODY_STYLE, CASES
from lxml import etree

from oformleno.engine import RuleEngine
from oformleno.fixer import FixError, fix_document, fix_document_bytes
from oformleno.model import DocumentModel
from oformleno.rules.r03_body_font import BodyFontChecker
from oformleno.ruleset import load_ruleset


def packed(document):
    stream = BytesIO()
    document.save(stream)
    return stream.getvalue()


def combined_document(path):
    document = Document(path)
    section = document.sections[0]
    section.page_width = Mm(190)
    section.left_margin = Mm(20)
    run = document.paragraphs[0].runs[0]
    run.font.name, run.font.size = "Calibri", Pt(12)
    document.paragraphs[0].paragraph_format.line_spacing = 1.0
    return document


@pytest.mark.parametrize("case", CASES)
def test_fixtures_fix_only_implemented_errors_and_preserve_other_parts(eom_fixtures, case):
    content = eom_fixtures[case].read_bytes()
    result = fix_document_bytes(content, load_ruleset(), document_type="laboratory_report")
    expected = tuple(
        rule
        for rule in CASES[case].error_rules
        if rule in {"R01", "R02", "R03", "R04", "R05", "R06"}
    )
    remaining = len(set(CASES[case].error_rules) & {"R07", "R08", "R09", "R10"})
    assert result.applied_rules == expected
    assert result.before.summary.errors == len(expected) + remaining
    assert result.before.summary.fixable == len(expected)
    assert result.after.summary.errors == remaining
    assert result.after.summary.fixable == 0
    assert result.after.summary.manual == result.before.summary.manual
    assert eom_fixtures[case].read_bytes() == content
    if not expected:
        assert result.document_bytes == content
    with ZipFile(BytesIO(content)) as before, ZipFile(BytesIO(result.document_bytes)) as after:
        assert before.namelist() == after.namelist()
        assert before.comment == after.comment
        for name in before.namelist():
            if name != "word/document.xml":
                assert before.read(name) == after.read(name)
    # Reopening/rechecking externally confirms the result's report is real.
    document = Document(BytesIO(result.document_bytes))
    report = RuleEngine().check(document, load_ruleset(), document_type="laboratory_report")
    assert report.model_dump_json() == result.after.model_dump_json()
    assert len(document.inline_shapes) == len(document.tables) == 3
    assert "PK" not in repr(result)


def test_all_five_rules_are_fixed_together_in_a_separate_file(eom_fixtures, tmp_path):
    source, output = tmp_path / "original.docx", tmp_path / "corrected.docx"
    document = combined_document(eom_fixtures["good"])
    document.save(source)
    original = source.read_bytes()
    original_xml = Document(BytesIO(original)).element
    original_text = [node.text for node in original_xml.iter(qn("w:t"))]
    original_drawings = [etree.tostring(node) for node in original_xml.iter(qn("w:drawing"))]
    result = fix_document(source, output, load_ruleset(), document_type="laboratory_report")
    assert result.applied_rules == ("R01", "R02", "R03", "R04", "R05")
    assert result.before.summary.errors == result.before.summary.fixable == 5
    assert result.after.summary.errors == result.after.summary.fixable == 0
    assert result.after.summary.manual == 7
    assert source.read_bytes() == original
    assert output.read_bytes() == result.document_bytes
    assert output.stat().st_mode & 0o777 == 0o600
    assert not list(tmp_path.glob(".oformleno-*"))
    fixed = Document(output)
    assert [node.text for node in fixed.element.iter(qn("w:t"))] == original_text
    assert [
        etree.tostring(node) for node in fixed.element.iter(qn("w:drawing"))
    ] == original_drawings
    assert len(fixed.tables) == 3
    for before, after in zip(document.tables, fixed.tables, strict=True):
        assert etree.tostring(before._tbl) == etree.tostring(after._tbl)


def test_second_fix_is_a_byte_identical_no_op(eom_fixtures):
    first = fix_document_bytes(packed(combined_document(eom_fixtures["good"])), load_ruleset())
    second = fix_document_bytes(first.document_bytes, load_ruleset())
    assert second.document_bytes == first.document_bytes
    assert second.applied_rules == ()
    assert second.before.summary.errors == second.after.summary.errors == 0


@pytest.mark.parametrize("derived", [False, True])
def test_body_fix_preserves_program_xml_and_style_payload(eom_fixtures, tmp_path, derived):
    document = combined_document(eom_fixtures["good"])
    program = document.styles.add_style("ЕОМ: Програма", WD_STYLE_TYPE.PARAGRAPH)
    program.base_style = document.styles[BODY_STYLE]
    program.font.name, program.font.size = "Consolas", Pt(10)
    program.paragraph_format.line_spacing = 1.0
    if derived:
        child = document.styles.add_style("Synthetic Program Child", WD_STYLE_TYPE.PARAGRAPH)
        child.base_style = program
        program = child
    paragraph = document.add_paragraph("print('synthetic')", style=program)
    paragraph.runs[0].font.size = Pt(9.5)
    source, output = tmp_path / "source.docx", tmp_path / "fixed.docx"
    document.save(source)
    original = source.read_bytes()
    program_xml = etree.tostring(Document(source).paragraphs[-1]._p, method="c14n")
    result = fix_document(source, output, load_ruleset(), document_type="laboratory_report")
    assert source.read_bytes() == original
    assert result.applied_rules == ("R01", "R02", "R03", "R04", "R05")
    assert result.after.summary.errors == 0
    assert etree.tostring(Document(output).paragraphs[-1]._p, method="c14n") == program_xml
    with ZipFile(BytesIO(original)) as before, ZipFile(output) as after:
        assert before.read("word/styles.xml") == after.read("word/styles.xml")


def test_landscape_and_later_sections_are_fixed_without_changing_orientation(eom_fixtures):
    document = Document(eom_fixtures["good"])
    section = document.add_section(WD_SECTION_START.NEW_PAGE)
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width, section.page_height, section.right_margin = Mm(280), Mm(210), Mm(20)
    result = fix_document_bytes(packed(document), load_ruleset())
    fixed = Document(BytesIO(result.document_bytes))
    assert result.applied_rules == ("R01", "R02")
    assert fixed.sections[1].orientation == WD_ORIENT.LANDSCAPE
    assert fixed.sections[1].page_width.mm == pytest.approx(297, abs=0.02)
    assert fixed.sections[1].page_height.mm == pytest.approx(210, abs=0.02)
    assert fixed.sections[1].right_margin.mm == pytest.approx(15, abs=0.02)


@pytest.mark.parametrize("layer", ["character", "paragraph", "base", "theme"])
def test_inherited_font_fixes_are_local_and_keep_style_xml(eom_fixtures, layer):
    document = Document(eom_fixtures["good"])
    run = document.paragraphs[0].runs[0]
    if layer == "character":
        style = document.styles.add_style("Synthetic Character", WD_STYLE_TYPE.CHARACTER)
        style.font.name = "Calibri"
        run.style = style
    elif layer == "paragraph":
        document.styles[BODY_STYLE].font.name = "Calibri"
    elif layer == "base":
        document.styles[BODY_BASE_STYLE].font.name = "Calibri"
    else:
        fonts = document.styles[BODY_BASE_STYLE].element.rPr.rFonts
        fonts.attrib.clear()
        fonts.set(qn("w:asciiTheme"), "minorHAnsi")
        fonts.set(qn("w:hAnsiTheme"), "minorHAnsi")
        # The generated document's default minor Latin font is Calibri.
    original = packed(document)
    result = fix_document_bytes(original, load_ruleset())
    assert result.applied_rules == ("R03",)
    assert result.after.summary.errors == 0
    with ZipFile(BytesIO(original)) as before, ZipFile(BytesIO(result.document_bytes)) as after:
        assert before.read("word/styles.xml") == after.read("word/styles.xml")
        assert before.read("word/theme/theme1.xml") == after.read("word/theme/theme1.xml")


def test_known_font_slot_is_corrected_without_replacing_unknown_slot(eom_fixtures):
    document = Document(eom_fixtures["good"])
    run = document.paragraphs[0].runs[0]
    run.font.name = "Calibri"
    run._r.rPr.rFonts.set(qn("w:hAnsi"), "+UnresolvedFont")
    result = fix_document_bytes(packed(document), load_ruleset())
    assert result.applied_rules == ("R03",)
    assert any(
        item.rule_id == "R03" and item.severity == "manual" for item in result.after.findings
    )
    fixed = Document(BytesIO(result.document_bytes))
    assert fixed.paragraphs[0].runs[0]._r.rPr.rFonts.get(qn("w:hAnsi")) == "+UnresolvedFont"
    assert fixed.paragraphs[0].runs[0]._r.rPr.rFonts.get(qn("w:ascii")) == "Times New Roman"


def test_east_asian_hint_does_not_turn_a_known_font_fix_into_uncertainty(eom_fixtures):
    document = Document(eom_fixtures["good"])
    run = document.paragraphs[0].runs[0]
    run.font.name = "Calibri"
    run._r.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
    run._r.rPr.rFonts.set(qn("w:hint"), "eastAsia")
    result = fix_document_bytes(packed(document), load_ruleset())
    assert result.applied_rules == ("R03",)
    assert not [item for item in result.after.findings if item.rule_id == "R03"]


def test_complex_script_size_inheritance_is_fixed_using_szcs(eom_fixtures):
    document = Document(eom_fixtures["good"])
    run = document.paragraphs[0].runs[0]
    run.text = "مثال"
    run._r.get_or_add_rPr().append(OxmlElement("w:cs"))
    inherited = OxmlElement("w:szCs")
    inherited.set(qn("w:val"), "24")
    document.styles[BODY_STYLE].element.get_or_add_rPr().append(inherited)
    result = fix_document_bytes(packed(document), load_ruleset())
    assert result.applied_rules == ("R04",)
    fixed = Document(BytesIO(result.document_bytes))
    size = fixed.paragraphs[0].runs[0]._r.rPr.find(qn("w:szCs"))
    assert size.get(qn("w:val")) == "28"
    assert DocumentModel(fixed).effective_font_size(fixed.paragraphs[0].runs[0]).value == 14


def test_manual_run_and_other_paragraph_properties_are_preserved(eom_fixtures):
    document = combined_document(eom_fixtures["good"])
    paragraph = document.paragraphs[0]
    paragraph.paragraph_format.space_before = Pt(8)
    paragraph.paragraph_format.space_after = Pt(6)
    paragraph.paragraph_format.keep_with_next = True
    unknown = paragraph.add_run("Невідоме форматування")
    style = OxmlElement("w:rStyle")
    style.set(qn("w:val"), "MissingSyntheticStyle")
    unknown._r.get_or_add_rPr().append(style)
    unknown_xml = etree.tostring(unknown._r)
    result = fix_document_bytes(packed(document), load_ruleset())
    assert result.after.summary.errors == 0
    assert result.after.summary.manual == result.before.summary.manual
    fixed = Document(BytesIO(result.document_bytes))
    paragraph = fixed.paragraphs[0]
    assert etree.tostring(paragraph.runs[-1]._r) == unknown_xml
    assert paragraph.paragraph_format.space_before.pt == 8
    assert paragraph.paragraph_format.space_after.pt == 6
    assert paragraph.paragraph_format.keep_with_next is True


@pytest.mark.parametrize("rule_id", ["R01", "R02", "R03", "R04", "R05"])
def test_yaml_autofix_false_is_respected(eom_fixtures, rule_id):
    ruleset = load_ruleset()
    ruleset = ruleset.model_copy(
        update={
            "rules": tuple(
                rule.model_copy(update={"autofix": False}) if rule.id == rule_id else rule
                for rule in ruleset.rules
            )
        }
    )
    original = eom_fixtures["bad_" + rule_id.lower()].read_bytes()
    result = fix_document_bytes(original, ruleset)
    assert result.applied_rules == ()
    assert result.document_bytes == original
    assert result.after.summary.errors == 1
    assert result.before.summary.fixable == result.after.summary.fixable == 0


@pytest.mark.parametrize(
    "rule_id,values",
    [
        ("R01", {"width_mm": 210.12345, "height_mm": 297}),
        ("R04", {"role": "body", "size_pt": 13.3}),
        ("R05", {"role": "body", "line_spacing": 1.333}),
    ],
)
def test_unrepresentable_targets_are_not_advertised_or_written(eom_fixtures, rule_id, values):
    ruleset = load_ruleset()
    ruleset = ruleset.model_copy(
        update={
            "tolerance_mm": 0.0 if rule_id == "R01" else ruleset.tolerance_mm,
            "rules": tuple(
                rule.model_copy(update={"params": values}) if rule.id == rule_id else rule
                for rule in ruleset.rules
            ),
        }
    )
    original = eom_fixtures["good"].read_bytes()
    result = fix_document_bytes(original, ruleset)
    assert result.applied_rules == ()
    assert result.document_bytes == original
    assert not any(item.fixable for item in result.before.findings)
    assert result.after.summary.errors > 0


def test_draft_ruleset_never_changes_document(eom_fixtures):
    original = eom_fixtures["bad_r02"].read_bytes()
    ruleset = load_ruleset().model_copy(update={"status": "draft"})
    result = fix_document_bytes(original, ruleset)
    assert result.document_bytes == original and result.applied_rules == ()
    assert result.after.summary.errors == 0


def test_unreferenced_package_entries_and_archive_metadata_are_preserved(eom_fixtures):
    stream = BytesIO(eom_fixtures["bad_r02"].read_bytes())
    with ZipFile(stream, "a") as package:
        package.writestr("synthetic/extra.bin", b"synthetic preserved data")
        package.comment = b"synthetic archive comment"
    original = stream.getvalue()
    result = fix_document_bytes(original, load_ruleset())
    with ZipFile(BytesIO(original)) as before, ZipFile(BytesIO(result.document_bytes)) as after:
        assert before.namelist() == after.namelist()
        assert before.comment == after.comment
        for entry in before.infolist():
            target = after.getinfo(entry.filename)
            assert target.date_time == entry.date_time
            assert target.compress_type == entry.compress_type
            assert target.external_attr == entry.external_attr
            if entry.filename != "word/document.xml":
                assert before.read(entry) == after.read(entry.filename)


@pytest.mark.parametrize(
    "kind", ["same_path", "existing", "hardlink", "symlink", "wrong_extension"]
)
def test_file_api_never_overwrites_original_or_existing_files(eom_fixtures, tmp_path, kind):
    source = tmp_path / "original.docx"
    source.write_bytes(eom_fixtures["bad_r02"].read_bytes())
    original = source.read_bytes()
    output = tmp_path / "corrected.docx"
    if kind == "same_path":
        output = source
    elif kind == "existing":
        output.write_bytes(b"preserve unrelated file")
    elif kind == "hardlink":
        os.link(source, output)
    elif kind == "symlink":
        output.symlink_to(source)
    else:
        output = tmp_path / "corrected.pdf"
    prior = output.read_bytes() if output.exists() else None
    with pytest.raises(FixError):
        fix_document(source, output, load_ruleset())
    assert source.read_bytes() == original
    if prior is not None:
        assert output.read_bytes() == prior
    else:
        assert not output.exists()
    assert not list(tmp_path.glob(".oformleno-*"))


def test_late_output_collision_is_not_overwritten(eom_fixtures, tmp_path, monkeypatch):
    source = eom_fixtures["bad_r02"]
    output = tmp_path / "corrected.docx"
    original_link = os.link

    def collide(staged, destination):
        Path(destination).write_bytes(b"late existing file")
        return original_link(staged, destination)

    monkeypatch.setattr(os, "link", collide)
    with pytest.raises(FixError, match="вже існує"):
        fix_document(source, output, load_ruleset())
    assert output.read_bytes() == b"late existing file"
    assert not list(tmp_path.glob(".oformleno-*"))


@pytest.mark.parametrize("failure", ["content_loss", "no_change", "exception"])
def test_failed_fix_or_recheck_never_publishes_a_copy(
    eom_fixtures, tmp_path, monkeypatch, failure, capsys, caplog
):
    source = eom_fixtures["bad_r03"]
    original = source.read_bytes()
    output = tmp_path / "corrected.docx"

    def broken(self, model, rule, ruleset):
        if failure == "content_loss":
            model.document.paragraphs[0].text = "SYNTHETIC_PRIVATE_IDENTIFIER"
        elif failure == "exception":
            raise RuntimeError("SYNTHETIC_PRIVATE_IDENTIFIER")
        return 1

    monkeypatch.setattr(BodyFontChecker, "fix", broken)
    with pytest.raises(FixError) as stopped:
        fix_document(source, output, load_ruleset())
    assert "SYNTHETIC_PRIVATE_IDENTIFIER" not in str(stopped.value)
    assert source.read_bytes() == original
    assert not output.exists() and not list(tmp_path.glob(".oformleno-*"))
    captured = capsys.readouterr()
    assert captured.out == captured.err == "" and not caplog.records
