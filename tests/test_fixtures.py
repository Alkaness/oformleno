"""Verify generated packages independently of future rule implementations."""

import json
import subprocess
import sys
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile

import pytest
from docx import Document
from docx.enum.section import WD_SECTION_START
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml.ns import qn
from fixtures.make_fixtures import (
    BODY_BASE_STYLE,
    BODY_STYLE,
    CASES,
    CELL_STYLE,
    HEADING_BASE_STYLE,
    generate_fixtures,
)
from lxml import etree

from oformleno.loader import load_document
from oformleno.model import DocumentModel, LineSpacing
from oformleno.ruleset import load_ruleset

SCRIPT = Path(__file__).parent / "fixtures" / "make_fixtures.py"


def params(rule_id):
    return next(rule.params for rule in load_ruleset().rules if rule.id == rule_id)


def paragraphs(document, style_name):
    return [paragraph for paragraph in document.paragraphs if paragraph.style.name == style_name]


def instructions(paragraph):
    return [node.text.strip() for node in paragraph._p.iter(qn("w:instrText"))] + [
        node.get(qn("w:instr")).strip() for node in paragraph._p.iter(qn("w:fldSimple"))
    ]


@pytest.mark.parametrize("name", CASES)
def test_every_fixture_is_readable_with_preserved_content_and_no_external_links(eom_fixtures, name):
    path = eom_fixtures[name]
    original = sha256(path.read_bytes()).digest()
    document = load_document(path)
    assert len(document.tables) == 3
    assert len(document.inline_shapes) == 3
    assert len(paragraphs(document, "Heading 1")) == 2
    assert document.core_properties.author == document.core_properties.last_modified_by == ""
    with ZipFile(path) as package:
        assert package.testzip() is None
        for filename in package.namelist():
            if filename.endswith((".xml", ".rels")):
                element = etree.fromstring(package.read(filename))
                if filename.endswith(".rels"):
                    assert not any(node.get("TargetMode") == "External" for node in element)
    assert sha256(path.read_bytes()).digest() == original


def test_manifest_covers_all_rules_and_distinguishes_errors_from_manual(eom_fixtures):
    manifest = json.loads(eom_fixtures["good"].with_name("manifest.json").read_text())
    assert manifest["ruleset"] == "lpnu-eom-styles-2026"
    assert manifest["document_type"] == "laboratory_report"
    assert set(manifest["cases"]) == {path.name for path in eom_fixtures.values()}
    for rule in load_ruleset().rules:
        case = manifest["cases"]["bad_" + rule.id.lower() + ".docx"]
        assert case["error_rules"] == [rule.id]
        assert case["manual_rules"] == []
    assert manifest["cases"]["good.docx"]["error_rules"] == []
    assert manifest["cases"]["good.docx"]["manual_rules"] == []
    for name in ("manual_role", "manual_inheritance", "manual_fields"):
        assert manifest["cases"][name + ".docx"]["error_rules"] == []
        assert manifest["cases"][name + ".docx"]["manual_rules"]


def test_good_page_geometry_and_inherited_body_formatting(eom_fixtures):
    document = load_document(eom_fixtures["good"])
    section = document.sections[0]
    assert section.page_width.mm == pytest.approx(210, abs=0.05)
    assert section.page_height.mm == pytest.approx(297, abs=0.05)
    for edge, expected in (("left", 25), ("right", 15), ("top", 20), ("bottom", 20)):
        assert getattr(section, edge + "_margin").mm == pytest.approx(expected, abs=0.05)
    model = DocumentModel(document)
    for paragraph in paragraphs(document, BODY_STYLE):
        assert paragraph.paragraph_format.line_spacing is None
        assert model.effective_line_spacing(paragraph).value == LineSpacing("multiple", 1.5)
        for run in paragraph.runs:
            if not run.text:
                continue
            assert run.font.name is run.font.size is None
            formatting = model.run_formatting(run)
            assert formatting.slots.value == ("ascii", "hAnsi")
            assert formatting.size_pt.value == 14
            assert formatting.size_pt.source == "base_style"
            assert {font.value for font in formatting.fonts.values()} == {"Times New Roman"}
    assert document.styles[BODY_STYLE].base_style.name == BODY_BASE_STYLE


def test_good_structural_heading_uses_inherited_caps_and_page_break(eom_fixtures):
    document = load_document(eom_fixtures["good"])
    style = document.styles[params("R06")["style"]]
    assert style.base_style.name == HEADING_BASE_STYLE
    assert style.font.all_caps is None
    assert style.paragraph_format.page_break_before is None
    base = style.base_style
    assert base.font.all_caps is base.font.bold is True
    assert base.paragraph_format.page_break_before is True
    assert base.paragraph_format.alignment == WD_ALIGN_PARAGRAPH.JUSTIFY
    for paragraph in paragraphs(document, style.name):
        assert paragraph.text.upper() in load_ruleset().structural_headings
        assert not paragraph.text.isupper()  # Visible uppercase must come from caps.
        assert paragraph.paragraph_format.page_break_before is None
        assert not any(run.font.all_caps for run in paragraph.runs)


def test_caption_positions_automatic_numbering_and_independent_chapter_resets(eom_fixtures):
    document = load_document(eom_fixtures["good"])
    for rule_id in ("R08", "R09"):
        values = params(rule_id)
        captions = paragraphs(document, values["style"])
        assert len(captions) == 3
        for caption, chapter, ordinal in zip(captions, (1, 1, 2), (1, 2, 1), strict=True):
            assert instructions(caption) == [
                "STYLEREF 1 \\s",
                f"SEQ {values['numbering']['sequence_name']} \\* ARABIC \\s 1",
            ]
            assert caption.text.startswith(f"{values['label']} {chapter}.{ordinal} ")
            if rule_id == "R08":
                assert caption._p.getprevious().find(".//" + qn("w:drawing")) is not None
            else:
                assert caption._p.getnext().tag == qn("w:tbl")
                assert caption.style.paragraph_format.keep_with_next is True
        style = document.styles[values["style"]]
        assert style.font.name == "Times New Roman"
        assert style.font.size.pt == values["size_pt"]
        assert style.font.italic is True
        assert style.paragraph_format.alignment == WD_ALIGN_PARAGRAPH.CENTER

    heading = document.styles["Heading 1"]
    numpr = heading.element.pPr.numPr
    numbering = document.part.numbering_part.element
    number = next(node for node in numbering.num_lst if node.numId == numpr.numId.val)
    abstract_id = number.abstractNumId.val
    abstract = next(
        node
        for node in numbering.findall(qn("w:abstractNum"))
        if node.get(qn("w:abstractNumId")) == str(abstract_id)
    )
    level = abstract.find(qn("w:lvl"))
    assert numpr.ilvl.val == 0
    assert level.find(qn("w:start")).get(qn("w:val")) == "1"
    assert level.find(qn("w:numFmt")).get(qn("w:val")) == "decimal"
    assert level.find(qn("w:pStyle")).get(qn("w:val")) == heading.style_id


def test_correct_twelve_point_tables_and_captions_do_not_use_body_style(eom_fixtures):
    document = load_document(eom_fixtures["good"])
    model = DocumentModel(document)
    for paragraph in paragraphs(document, params("R08")["style"]):
        for run in paragraph.runs:
            if run.text:
                assert model.effective_font_size(run).value == 12
        assert paragraph.style.name != BODY_STYLE
    for table in document.tables:
        for row_index, row in enumerate(table.rows):
            for cell in row.cells:
                paragraph = cell.paragraphs[0]
                assert paragraph.style.name == CELL_STYLE
                assert paragraph.style.font.size.pt == 12
                assert paragraph.style.paragraph_format.line_spacing == 1.0
                assert paragraph.runs[0].bold == (row_index == 0)
                assert paragraph._p not in [item._p for item in model.paragraphs]


def test_headers_have_page_fields_and_first_page_is_empty(eom_fixtures):
    document = load_document(eom_fixtures["good"])
    section = document.sections[0]
    assert section.different_first_page_header_footer
    assert document.settings.odd_and_even_pages_header_footer
    assert not section.first_page_header._element.findall(".//" + qn("w:t"))
    assert not section.first_page_header._element.findall(".//" + qn("w:fldChar"))
    for header in (section.header, section.even_page_header):
        paragraph = header.paragraphs[0]
        assert instructions(paragraph) == ["PAGE"]
        assert paragraph.style.font.size.pt == 12
        assert paragraph.style.font.name == "Times New Roman"
        assert paragraph.style.paragraph_format.alignment == WD_ALIGN_PARAGRAPH.RIGHT


@pytest.mark.parametrize("rule_number", range(1, 11))
def test_each_bad_rnn_changes_only_its_targeted_property(eom_fixtures, rule_number):
    # Comparing saved package parts catches accidental secondary mutations, not
    # just the presence of the intended failure. Reset the one intended property.
    good = Document(eom_fixtures["good"])
    bad = Document(eom_fixtures[f"bad_r{rule_number:02}"])
    body = bad.paragraphs[0]
    heading = paragraphs(bad, params("R06")["style"])[0]
    match rule_number:
        case 1:
            assert bad.sections[0].page_width.mm == pytest.approx(190, abs=0.05)
            bad.sections[0].page_width = good.sections[0].page_width
        case 2:
            assert bad.sections[0].left_margin.mm == pytest.approx(20, abs=0.05)
            bad.sections[0].left_margin = good.sections[0].left_margin
        case 3:
            assert body.runs[0].font.name == "Calibri"
            body.runs[0]._r.remove(body.runs[0]._r.rPr)
        case 4:
            assert body.runs[0].font.size.pt == 12
            body.runs[0]._r.remove(body.runs[0]._r.rPr)
        case 5:
            assert body.paragraph_format.line_spacing == 1.0
            body._p.pPr.remove(body._p.pPr.spacing)
        case 6:
            assert heading.alignment == WD_ALIGN_PARAGRAPH.CENTER
            heading.alignment = None
        case 7:
            assert heading.paragraph_format.page_break_before is False
            heading.paragraph_format.page_break_before = None
        case 8:
            caption = paragraphs(bad, params("R08")["style"])[0]
            assert all(run.font.size.pt == 14 for run in caption.runs)
            for run in caption.runs:
                run._r.remove(run._r.rPr)
        case 9:
            caption = paragraphs(bad, params("R09")["style"])[0]
            assert all(run.italic is False for run in caption.runs)
            for run in caption.runs:
                run._r.remove(run._r.rPr)
        case 10:
            header = bad.sections[0].header.paragraphs[0]
            assert header.alignment == WD_ALIGN_PARAGRAPH.CENTER
            header.alignment = None

    # Property setters leave empty pPr wrappers; these are semantically absent.
    def parts(document):
        result = {}
        for part in document.part.package.parts:
            blob = part.blob
            if part.partname.endswith(".xml"):
                root = etree.fromstring(blob)
                for node in list(root.iter(qn("w:pPr"))):
                    if len(node) == 0 and not node.attrib:
                        node.getparent().remove(node)
                blob = etree.tostring(root, method="c14n")
            result[str(part.partname)] = blob
        return result

    assert parts(bad) == parts(good)


def test_explicit_page_break_and_section_break_alternatives(eom_fixtures):
    document = Document(eom_fixtures["good_page_break"])
    heading = paragraphs(document, params("R06")["style"])[0]
    assert heading.paragraph_format.page_break_before is False
    breaks = heading._p.getprevious().findall(".//" + qn("w:br"))
    assert [node.get(qn("w:type")) for node in breaks] == ["page"]

    document = Document(eom_fixtures["good_section_break"])
    heading = paragraphs(document, params("R06")["style"])[0]
    assert len(document.sections) == 2
    assert heading._p.getprevious().find(".//" + qn("w:sectPr")) is not None
    assert heading.paragraph_format.page_break_before is False
    assert document.sections[1].start_type == WD_SECTION_START.NEW_PAGE
    assert not document.sections[1].different_first_page_header_footer
    assert document.sections[1].header.is_linked_to_previous
    assert document.sections[1].even_page_header.is_linked_to_previous


def test_simple_fields_keep_instructions_and_cached_numbers(eom_fixtures):
    document = Document(eom_fixtures["good_simple_fields"])
    assert not list(document.element.iter(qn("w:instrText")))
    for rule_id in ("R08", "R09"):
        for paragraph, chapter, ordinal in zip(
            paragraphs(document, params(rule_id)["style"]), (1, 1, 2), (1, 2, 1), strict=True
        ):
            fields = paragraph._p.findall(qn("w:fldSimple"))
            assert len(fields) == 2
            assert [field.find(".//" + qn("w:t")).text for field in fields] == [
                str(chapter),
                str(ordinal),
            ]
            assert instructions(paragraph)[0] == "STYLEREF 1 \\s"
    assert instructions(document.sections[0].header.paragraphs[0]) == ["PAGE"]


def test_font_slots_exact_spacing_and_first_header_boundary_cases(eom_fixtures):
    model = DocumentModel(Document(eom_fixtures["bad_r03_hansi"]))
    run = model.runs(model.paragraphs[0])[0]
    assert model.font_slots(run).value == ("ascii", "hAnsi")
    assert model.effective_font(run, "ascii").value == "Times New Roman"
    assert model.effective_font(run, "hAnsi").value == "Calibri"
    document = Document(eom_fixtures["bad_r05_exact"])
    paragraph = document.paragraphs[0]
    assert paragraph.paragraph_format.line_spacing_rule == WD_LINE_SPACING.EXACTLY
    assert DocumentModel(document).effective_line_spacing(paragraph).value == LineSpacing(
        "exact", 21
    )
    document = Document(eom_fixtures["bad_r10_first_page"])
    assert document.sections[0].different_first_page_header_footer
    assert instructions(document.sections[0].first_page_header.paragraphs[0]) == ["PAGE"]


def test_unresolved_font_inheritance_and_unproven_roles_are_distinct(eom_fixtures):
    document = Document(eom_fixtures["manual_inheritance"])
    model = DocumentModel(document)
    run = model.runs(model.paragraphs[0])[0]
    assert model.effective_font(run).reason
    assert model.effective_font_size(run).reason
    assert model.effective_line_spacing(model.paragraphs[0]).value == LineSpacing("multiple", 1.5)

    document = Document(eom_fixtures["manual_role"])
    paragraph = document.paragraphs[-1]
    assert paragraph.style.name.startswith("ЕОМ:")
    assert paragraph.style.name != BODY_STYLE
    model = DocumentModel(document)
    run = paragraph.runs[0]
    assert model.effective_font(run).value == "Calibri"
    assert model.effective_font_size(run).value == 12
    assert model.effective_line_spacing(paragraph).value == LineSpacing("multiple", 1)


def test_uncertain_caption_fields_keep_plausible_cached_numbers(eom_fixtures):
    document = Document(eom_fixtures["manual_fields"])
    for rule_id in ("R08", "R09"):
        paragraph = paragraphs(document, params(rule_id)["style"])[0]
        assert instructions(paragraph)[1].endswith("\\s")  # No heading-level argument.
        assert paragraph.text.startswith(params(rule_id)["label"] + " 1.1 ")
        assert len(list(paragraph._p.iter(qn("w:fldChar")))) == 6


def test_generator_refuses_to_replace_existing_files(tmp_path):
    existing = tmp_path / "bad_r02.docx"
    existing.write_bytes(b"preserve existing contents")
    with pytest.raises(FileExistsError, match="тимчасову теку"):
        generate_fixtures(tmp_path)
    assert existing.read_bytes() == b"preserve existing contents"
    assert list(tmp_path.iterdir()) == [existing]


def test_generator_cli_creates_a_complete_suite_outside_checkout(tmp_path):
    result = subprocess.run(
        [sys.executable, str(SCRIPT.resolve()), str(tmp_path / "examples")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "Створено" in result.stdout
    assert len(list((tmp_path / "examples").glob("*.docx"))) == len(CASES)
