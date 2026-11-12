"""R08: figure associations, effective typography and real Word field structures."""

from copy import deepcopy
from io import BytesIO

import pytest
from caption_helpers import change_code, child, code_nodes, example, visible_runs
from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml.ns import qn
from docx.shared import Pt

from oformleno.engine import RuleEngine
from oformleno.fixer import fix_document_bytes
from oformleno.loader import load_document
from oformleno.model import DocumentModel
from oformleno.ruleset import load_ruleset


@pytest.mark.parametrize(
    "case", ["good", "good_simple_fields", "good_section_break", "good_page_break"]
)
def test_valid_chapters_and_independent_counters(eom_fixtures, body_check, case):
    assert body_check(Document(eom_fixtures[case]), "R08") == ()


def test_size_acceptance_with_location_sources_and_no_fix(eom_fixtures, body_check):
    document, paragraph, rule = example(eom_fixtures, "R08", "bad_r08")
    findings = body_check(document, "R08")
    assert len(findings) == 1
    item = findings[0]
    assert item.severity == "error" and not item.fixable
    assert item.actual == {"size_pt": [14]}
    assert item.expected == {"size_pt": 12}
    assert item.location.paragraph == 7 and item.location.page is None
    assert (
        item.location.excerpt
        == "".join(run.text for run in DocumentModel(document).runs(paragraph))[:50]
    )
    assert item.quote == rule.quote and item.source_id == "styles"
    assert set(item.parameter_sources.values()) == {"user_reference"}


@pytest.mark.parametrize("property", ["align", "font", "italic", "spacing", "half_point"])
def test_typography_properties_are_independent(eom_fixtures, body_check, property):
    document, paragraph, _rule = example(eom_fixtures, "R08")
    if property == "align":
        paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
        key, actual = "align", "left"
    elif property == "spacing":
        paragraph.paragraph_format.line_spacing = Pt(18)
        key, actual = "line_spacing", {"kind": "exact", "value": 18}
    elif property == "font":
        visible_runs(document, paragraph)[-1].font.name = "Calibri"
        key, actual = "font", ["Calibri"]
    elif property == "italic":
        visible_runs(document, paragraph)[-1].italic = False
        key, actual = "italic", False
    else:
        visible_runs(document, paragraph)[-1].font.size = Pt(12.5)
        key, actual = "size_pt", [12.5]
    findings = body_check(document, "R08")
    assert len(findings) == 1 and findings[0].severity == "error"
    assert findings[0].actual == {key: actual}


@pytest.mark.parametrize("layer", ["derived", "character", "base", "defaults", "theme"])
def test_inherited_caption_formatting(eom_fixtures, body_check, layer):
    document, paragraph, rule = example(eom_fixtures, "R08")
    style = document.styles[rule.params["style"]]
    run = visible_runs(document, paragraph)[-1]
    if layer == "derived":
        derived = document.styles.add_style("Synthetic figure", WD_STYLE_TYPE.PARAGRAPH)
        derived.base_style = style
        paragraph.style = derived
        assert body_check(document, "R08") == ()
        derived.font.size = Pt(11)
    elif layer == "character":
        character = document.styles.add_style("Synthetic emphasis", WD_STYLE_TYPE.CHARACTER)
        character.font.italic = True  # Toggle off the paragraph's inherited italic.
        run.style = character
    elif layer == "base":
        base = document.styles.add_style("Synthetic caption base", WD_STYLE_TYPE.PARAGRAPH)
        base.base_style = style.base_style
        base.font.size = Pt(11)
        style.base_style = base
        style.font.size = None
    elif layer == "defaults":
        style.font.size = None
        style.base_style.font.size = None
        defaults = document.styles.element.find(".//" + qn("w:rPrDefault") + "/" + qn("w:rPr"))
        defaults.find(qn("w:sz")).set(qn("w:val"), "22")
    else:
        fonts = run._r.get_or_add_rPr().get_or_add_rFonts()
        fonts.set(qn("w:hAnsiTheme"), "minorHAnsi")
    findings = body_check(document, "R08")
    errors = [item for item in findings if item.severity == "error"]
    assert errors and all(not item.fixable for item in errors)
    key = "italic" if layer == "character" else "font" if layer == "theme" else "size_pt"
    assert key in errors[0].actual


@pytest.mark.parametrize(
    "old,new,key,actual",
    [
        ("STYLEREF 1", "STYLEREF 2", "chapter_heading_level", "2"),
        ("STYLEREF 1 \\s", "STYLEREF 1", "chapter_number", False),
        ("SEQ Рис.", "SEQ Табл.", "sequence_name", "Табл."),
        ("\\s 1", "\\s 2", "reset_at_heading_level", "2"),
        ("\\s 1", "", "reset_at_heading_level", None),
        ("ARABIC", "ROMAN", "number_format", "ROMAN"),
    ],
)
def test_known_field_mismatches(eom_fixtures, body_check, old, new, key, actual):
    document, paragraph, _rule = example(eom_fixtures, "R08")
    change_code(paragraph, old, new)
    findings = body_check(document, "R08")
    errors = [item for item in findings if item.severity == "error"]
    assert len(errors) == 1 and errors[0].actual == {key: actual}
    assert all(item.severity == "manual" for item in findings if item not in errors)


@pytest.mark.parametrize("change", ["label", "separator", "literal", "position"])
def test_caption_structure_errors(eom_fixtures, body_check, change):
    document, paragraph, _rule = example(eom_fixtures, "R08")
    if change == "label":
        paragraph.runs[0].text = "Мал. "
        key, actual = "label", "Мал."
    elif change == "separator":
        next(run for run in paragraph.runs if run.text == ".").text = "-"
        key, actual = "separator", "-"
    elif change == "literal":
        paragraph.text = "Рис. 1.1 Згенерований підпис"
        key, actual = "method", "literal"
    else:
        picture = paragraph._p.getprevious()
        picture.addprevious(paragraph._p)
        key, actual = "position", "above"
    findings = body_check(document, "R08")
    assert len(findings) == 1 and findings[0].severity == "error"
    assert findings[0].actual == {key: actual}


@pytest.mark.parametrize("change", ["split", "simple", "quoted", "mergeformat", "cache"])
def test_field_spelling_and_caches_do_not_define_numbers(eom_fixtures, body_check, change):
    document, paragraph, _rule = example(
        eom_fixtures, "R08", "good_simple_fields" if change == "simple" else "good"
    )
    if change == "split":
        code = code_nodes(paragraph)[1]
        original = code.text
        code.text = original[:7]
        child(code.getparent(), "instrText").text = original[7:]
    elif change == "quoted":
        change_code(paragraph, "SEQ Рис.", 'seq "Рис."')
        change_code(paragraph, "STYLEREF 1", 'styleref "1"')
    elif change == "mergeformat":
        code_nodes(paragraph)[1].text += " \\* MERGEFORMAT"
    elif change == "cache":
        for run in visible_runs(document, paragraph):
            if run.text == "1":
                run.text = "STALE"
    assert body_check(document, "R08") == ()


@pytest.mark.parametrize(
    "change",
    [
        "unknown_switch",
        "missing_argument",
        "nested",
        "unclosed",
        "locked",
        "named_style",
        "restart",
        "repeat",
        "unknown_type",
        "quote",
    ],
)
def test_uncertain_field_instructions_are_manual(eom_fixtures, body_check, change):
    document, paragraph, _rule = example(eom_fixtures, "R08")
    if change == "unknown_switch":
        code_nodes(paragraph)[1].text += " \\unknown"
    elif change == "missing_argument":
        change_code(paragraph, "\\s 1", "\\s")
    elif change == "nested":
        paragraph._p.insert(1, deepcopy(paragraph.runs[1]._r))
    elif change == "unclosed":
        end = list(paragraph._p.iter(qn("w:fldChar")))[-1]
        end.getparent().remove(end)
    elif change == "locked":
        next(paragraph._p.iter(qn("w:fldChar"))).set(qn("w:fldLock"), "true")
    elif change == "named_style":
        change_code(paragraph, "STYLEREF 1", 'STYLEREF "Heading 1"')
    elif change == "restart":
        code_nodes(paragraph)[1].text += " \\r 1"
    elif change == "repeat":
        code_nodes(paragraph)[1].text += " \\c"
    elif change == "unknown_type":
        change_code(paragraph, "SEQ", "REF")
    else:
        change_code(paragraph, "Рис.", '"Рис.')
    findings = body_check(document, "R08")
    assert findings and all(item.severity == "manual" for item in findings)


@pytest.mark.parametrize(
    "change", ["missing_style", "body", "normal", "arbitrary", "outline", "revision"]
)
def test_uncertain_caption_roles_are_manual(eom_fixtures, body_check, change):
    document, paragraph, _rule = example(eom_fixtures, "R08")
    if change == "missing_style":
        paragraph._p.pPr.pStyle.set(qn("w:val"), "MissingSyntheticStyle")
    elif change == "body":
        paragraph.style = document.styles["ЕОМ: Основний"]
    elif change == "normal":
        paragraph.style = document.styles["Normal"]
    elif change == "arbitrary":
        paragraph.style = document.styles.add_style("ЕОМ: Arbitrary", WD_STYLE_TYPE.PARAGRAPH)
    elif change == "outline":
        child(paragraph._p.get_or_add_pPr(), "outlineLvl", val=0)
    else:
        child(paragraph._p.get_or_add_pPr(), "pPrChange")
    findings = body_check(document, "R08")
    assert findings and all(item.severity == "manual" for item in findings)


@pytest.mark.parametrize(
    "change", ["floating", "multiple", "broken_relationship", "gap", "text", "hidden", "frame"]
)
def test_uncertain_picture_links_are_manual(eom_fixtures, body_check, change):
    document, paragraph, _rule = example(eom_fixtures, "R08")
    picture = paragraph._p.getprevious()
    if change == "floating":
        next(picture.iter(qn("wp:inline"))).tag = qn("wp:anchor")
    elif change == "multiple":
        picture.append(deepcopy(picture[-1]))
    elif change == "broken_relationship":
        next(picture.iter(qn("a:blip"))).set(qn("r:embed"), "missing-image")
    elif change == "gap":
        paragraph.insert_paragraph_before()
    elif change == "text":
        child(child(picture, "r"), "t").text = "Змішаний вміст"
    elif change == "hidden":
        visible_runs(document, paragraph)[-1].font.hidden = True
    else:
        child(paragraph.style.element.get_or_add_pPr(), "framePr")
    findings = body_check(document, "R08")
    assert findings and all(item.severity == "manual" for item in findings)


@pytest.mark.parametrize(
    "change", ["no_heading", "plain_heading", "unknown_numbering", "roman", "override"]
)
def test_uncertain_chapter_context_is_manual(eom_fixtures, body_check, change):
    document, paragraph, _rule = example(eom_fixtures, "R08")
    heading = next(p for p in document.paragraphs if p.style.name == "Heading 1")
    if change == "no_heading":
        heading._p.getparent().remove(heading._p)
    elif change == "plain_heading":
        heading._p.get_or_add_pPr().get_or_add_numPr().get_or_add_numId().val = 0
    elif change == "unknown_numbering":
        document.part.drop_rel(
            next(
                key
                for key, relation in document.part.rels.items()
                if relation.reltype == RT.NUMBERING
            )
        )
    elif change == "roman":
        root = document.part.numbering_part.element
        target = root.findall(qn("w:abstractNum"))[-1]
        target.find(qn("w:lvl")).find(qn("w:numFmt")).set(qn("w:val"), "upperRoman")
    else:
        child(document.part.numbering_part.element.findall(qn("w:num"))[-1], "lvlOverride", ilvl=0)
    findings = body_check(document, "R08")
    assert findings and all(item.severity == "manual" for item in findings)


def test_known_error_and_unknown_character_formatting_are_separate(eom_fixtures, body_check):
    document, paragraph, _rule = example(eom_fixtures, "R08", "bad_r08")
    child(
        paragraph.add_run(" Невизначений фрагмент")._r.get_or_add_rPr(),
        "rStyle",
        val="MissingSyntheticStyle",
    )
    findings = body_check(document, "R08")
    assert {item.severity for item in findings} == {"error", "manual"}
    assert next(item for item in findings if item.severity == "error").actual == {"size_pt": [14]}


def test_read_only_check_and_new_copy_keep_caption_error(eom_fixtures, caplog):
    path = eom_fixtures["bad_r08"]
    original = path.read_bytes()
    document = load_document(path)
    parts = {str(part.partname): part.blob for part in document.part.package.parts}
    report = RuleEngine().check(DocumentModel(document), load_ruleset())
    assert report.failed_rules == ()
    assert (
        report.model_dump_json() == RuleEngine().check(document, load_ruleset()).model_dump_json()
    )
    assert parts == {str(part.partname): part.blob for part in document.part.package.parts}
    result = fix_document_bytes(original, load_ruleset())
    assert result.applied_rules == () and result.document_bytes == original
    assert result.after.summary.errors == 1 and result.after.summary.fixable == 0
    assert path.read_bytes() == original
    assert len(Document(BytesIO(result.document_bytes)).inline_shapes) == 3
    assert "Згенерований" not in caplog.text


@pytest.mark.parametrize("change", ["separator", "title", "label"])
def test_missing_literal_parts_of_a_known_caption_are_errors(eom_fixtures, body_check, change):
    document, paragraph, _rule = example(eom_fixtures, "R08")
    run = (
        paragraph.runs[0]
        if change == "label"
        else visible_runs(document, paragraph)[-1]
        if change == "title"
        else next(run for run in paragraph.runs if run.text == ".")
    )
    run.text = ""
    findings = body_check(document, "R08")
    assert len(findings) == 1 and findings[0].severity == "error"
    assert findings[0].actual == {change: False if change == "title" else ""}


def test_unsupported_cache_characters_and_shared_runs_use_output_domain(eom_fixtures, body_check):
    document, paragraph, _rule = example(eom_fixtures, "R08")
    first_result = next(run for run in paragraph.runs if run.text == "1")
    first_result.text = "🧪"
    following = first_result._r.getnext()
    # Put the field end and literal dot into the same run as its cached result.
    first_result._r.append(following[0])
    dot = next(run for run in paragraph.runs if run.text == ".")
    first_result._r.append(dot._r[0])
    assert body_check(document, "R08") == ()


@pytest.mark.parametrize("location", ["paragraph", "table"])
def test_external_seq_fields_prevent_claiming_local_counter_is_valid(
    eom_fixtures, body_check, location
):
    document, paragraph, _rule = example(eom_fixtures, "R08")
    if location == "paragraph":
        previous = paragraph.insert_paragraph_before(style="ЕОМ: Основний")
    else:
        table = document.add_table(rows=1, cols=1)
        paragraph._p.addprevious(table._tbl)
        previous = table.cell(0, 0).paragraphs[0]
    field = child(previous._p, "fldSimple", instr="SEQ Рис. \\* ARABIC")
    child(child(field, "r"), "t").text = "1"
    findings = body_check(document, "R08")
    assert findings and all(item.severity == "manual" for item in findings)
    assert any("лічильник" in item.message for item in findings)


def test_nested_heading_can_change_chapter_context(eom_fixtures, body_check):
    document, paragraph, _rule = example(eom_fixtures, "R08")
    table = document.add_table(rows=1, cols=1)
    paragraph._p.getprevious().addprevious(table._tbl)
    table.cell(0, 0).paragraphs[0].style = document.styles["Heading 1"]
    findings = body_check(document, "R08")
    assert findings and all(item.severity == "manual" for item in findings)


@pytest.mark.parametrize(
    "change", ["hidden_image", "table_image", "opaque_block", "missing_caption"]
)
def test_unassessed_images_are_reported_for_manual_review(eom_fixtures, body_check, change):
    document, paragraph, _rule = example(eom_fixtures, "R08")
    picture = paragraph._p.getprevious()
    if change == "hidden_image":
        image_run = next(picture.iter(qn("w:r")))
        child(image_run.get_or_add_rPr(), "vanish")
    elif change == "table_image":
        table = document.add_table(rows=1, cols=1)
        picture.addprevious(table._tbl)
        table.cell(0, 0)._tc.append(picture)
    elif change == "opaque_block":
        wrapper = child(document.element.body, "ins")
        picture.addprevious(wrapper)
        wrapper.append(picture)
    else:
        paragraph._p.getparent().remove(paragraph._p)
    findings = body_check(document, "R08")
    assert findings and all(item.severity == "manual" for item in findings)


def test_empty_caption_style_is_not_an_automatic_violation(eom_fixtures, body_check):
    document, _paragraph, rule = example(eom_fixtures, "R08")
    document.add_paragraph(style=rule.params["style"])
    assert body_check(document, "R08") == ()


def test_unknown_field_output_does_not_guess_font_slots_from_its_cache(eom_fixtures, body_check):
    document, paragraph, _rule = example(eom_fixtures, "R08")
    change_code(paragraph, "STYLEREF", "REF")
    result = next(run for run in paragraph.runs if run.text == "1")
    fonts = result._r.get_or_add_rPr().get_or_add_rFonts()
    fonts.set(qn("w:ascii"), "Calibri")
    fonts.set(qn("w:hAnsi"), "Times New Roman")
    findings = body_check(document, "R08")
    assert findings and all(item.severity == "manual" for item in findings)
