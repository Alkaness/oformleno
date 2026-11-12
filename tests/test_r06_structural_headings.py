"""R06 heading identity, inherited flags, conservative fixes and content guards."""

from io import BytesIO
from zipfile import ZipFile

import pytest
from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt
from lxml import etree

from oformleno.engine import RuleEngine
from oformleno.fixer import FixError, fix_document_bytes
from oformleno.model import DocumentModel
from oformleno.rules.r06_structural_headings import StructuralHeadingChecker
from oformleno.ruleset import load_ruleset


def heading(document):
    name = load_ruleset().rules[5].params["style"]
    return next(paragraph for paragraph in document.paragraphs if paragraph.style.name == name)


def packed(document):
    stream = BytesIO()
    document.save(stream)
    return stream.getvalue()


def field_marker(paragraph, kind, *, before=False):
    run = paragraph.add_run()
    marker = OxmlElement("w:fldChar")
    marker.set(qn("w:fldCharType"), kind)
    run._r.append(marker)
    if before:
        paragraph.runs[0]._r.addprevious(run._r)
    return marker


def field_instruction(paragraph, code):
    instruction = OxmlElement("w:instrText")
    instruction.text = code
    paragraph.add_run()._r.append(instruction)
    return instruction


def contents_between_titles(document, *, command="TOC", nested=False):
    first = heading(document)
    first.runs[0].text = "Зміст"
    first.alignment = WD_ALIGN_PARAGRAPH.CENTER
    field_marker(first, "begin")
    # Split instructions exercise XML order rather than one-code-per-run logic.
    field_instruction(first, f" {command[:1]}")
    field_instruction(first, f"{command[1:]} ")
    field_marker(first, "separate")
    entry = document.add_paragraph("Згенерований пункт")
    first._p.addnext(entry._p)
    if nested:
        field_marker(entry, "begin")
        field_instruction(entry, " PAGEREF SyntheticTarget ")
        field_marker(entry, "separate")
        entry.add_run("1")
        field_marker(entry, "end")
    last = document.add_paragraph("Вступ", style=first.style)
    last.alignment = WD_ALIGN_PARAGRAPH.CENTER
    entry._p.addnext(last._p)
    field_marker(last, "end", before=True)
    return first, entry, last


@pytest.mark.parametrize("nested", [False, True])
def test_literal_titles_at_complete_toc_boundaries_are_fixed_without_field_edits(
    eom_fixtures, tmp_path, nested
):
    document = Document(eom_fixtures["good"])
    contents_between_titles(document, nested=nested)
    source = tmp_path / "source.docx"
    document.save(source)
    original = source.read_bytes()

    def field_signature(doc):
        return [
            (node.tag, tuple(sorted(node.attrib.items())), node.text)
            for node in doc.element.iter()
            if node.tag in {qn("w:fldChar"), qn("w:instrText"), qn("w:fldSimple")}
        ]

    fields = field_signature(Document(source))
    result = fix_document_bytes(original, load_ruleset(), document_type="laboratory_report")
    assert source.read_bytes() == original
    assert result.applied_rules == ("R06",)
    found = [f for f in result.before.findings if f.rule_id == "R06"]
    assert len(found) == 2
    assert all(
        f.severity == "error" and f.fixable and f.actual == {"align": "center"} for f in found
    )
    assert not [f for f in result.after.findings if f.rule_id in {"R06", "R07"}]
    corrected = Document(BytesIO(result.document_bytes))
    assert field_signature(corrected) == fields
    assert [node.text for node in corrected.element.iter(qn("w:t"))] == [
        node.text for node in document.element.iter(qn("w:t"))
    ]
    with ZipFile(BytesIO(original)) as before, ZipFile(BytesIO(result.document_bytes)) as after:
        assert before.namelist() == after.namelist()
        assert all(
            before.read(name) == after.read(name)
            for name in before.namelist()
            if name != "word/document.xml"
        )
    assert (
        fix_document_bytes(result.document_bytes, load_ruleset()).document_bytes
        == result.document_bytes
    )


@pytest.mark.parametrize(
    "problem",
    ["orphan_end", "orphan_instruction", "unknown_marker", "unclosed", "inline_empty_toc"],
)
def test_unproven_field_boundaries_do_not_allow_heading_fixes(eom_fixtures, problem):
    document = Document(eom_fixtures["bad_r06"])
    paragraph = heading(document)
    if problem == "orphan_end":
        field_marker(paragraph, "end", before=True)
    elif problem == "orphan_instruction":
        field_instruction(paragraph, " TOC ")
    elif problem == "unknown_marker":
        field_marker(paragraph, "SYNTHETIC_PRIVATE_IDENTIFIER")
    else:
        field_marker(paragraph, "begin")
        field_instruction(paragraph, " TOC ")
        field_marker(paragraph, "separate")
        if problem == "inline_empty_toc":
            field_marker(paragraph, "end")
    original = packed(document)
    result = fix_document_bytes(original, load_ruleset())
    found = [f for f in result.before.findings if f.rule_id == "R06"]
    assert len(found) == (2 if problem == "unclosed" else 1)
    assert all(f.severity == "manual" for f in found)
    assert result.document_bytes == original and result.applied_rules == ()
    assert "SYNTHETIC_PRIVATE_IDENTIFIER" not in result.before.model_dump_json()


@pytest.mark.parametrize("command", ["REF", "TOC"])
def test_title_cached_in_a_field_from_another_paragraph_remains_manual(eom_fixtures, command):
    document = Document(eom_fixtures["bad_r06"])
    paragraph = heading(document)
    previous = document.add_paragraph()
    paragraph._p.addprevious(previous._p)
    field_marker(previous, "begin")
    field_instruction(previous, f" {command} SyntheticTarget ")
    field_marker(previous, "separate")
    following = document.add_paragraph()
    paragraph._p.addnext(following._p)
    field_marker(following, "end")
    original = packed(document)
    result = fix_document_bytes(original, load_ruleset())
    found = [f for f in result.before.findings if f.rule_id == "R06"]
    assert len(found) == 1 and found[0].severity == "manual"
    assert result.document_bytes == original and result.applied_rules == ()


@pytest.mark.parametrize("problem", ["unknown_suffix", "duplicate_separator", "revised_begin"])
def test_uncertain_block_fields_do_not_certify_literal_heading_roles(eom_fixtures, problem):
    document = Document(eom_fixtures["good"])
    first, entry, last = contents_between_titles(
        document, command="REF" if problem == "unknown_suffix" else "TOC"
    )
    if problem == "duplicate_separator":
        field_marker(entry, "separate")
    elif problem == "revised_begin":
        marker_run = first.runs[1]._r
        revision = OxmlElement("w:ins")
        marker_run.addprevious(revision)
        revision.append(marker_run)
    original = packed(document)
    result = fix_document_bytes(original, load_ruleset())
    found = [f for f in result.before.findings if f.rule_id == "R06"]
    if problem == "unknown_suffix":
        # The unknown field might append content to its opening title, but its
        # matched end before the closing literal title does not change that title.
        assert [f.severity for f in found] == ["manual", "error"]
        corrected = Document(BytesIO(result.document_bytes))
        assert heading(corrected).alignment == WD_ALIGN_PARAGRAPH.CENTER
        assert (
            next(p for p in corrected.paragraphs if p.text == last.text).alignment
            == WD_ALIGN_PARAGRAPH.JUSTIFY
        )
    else:
        assert len(found) == 2 and all(f.severity == "manual" for f in found)
        assert result.document_bytes == original and result.applied_rules == ()


@pytest.mark.parametrize("position", ["prefix", "between_runs", "cached_spaces"])
def test_inline_fields_cannot_establish_a_literal_heading(eom_fixtures, position):
    document = Document(eom_fixtures["bad_r06"])
    paragraph = heading(document)
    if position == "between_runs":
        paragraph.runs[0].text = "В"
    field_marker(paragraph, "begin")
    field_instruction(paragraph, " TOC ")
    field_marker(paragraph, "separate")
    if position == "cached_spaces":
        paragraph.add_run(" ")
    field_marker(paragraph, "end")
    if position == "prefix":
        paragraph._p.append(paragraph.runs[0]._r)
    elif position == "between_runs":
        paragraph.add_run("ступ")
    original = packed(document)
    result = fix_document_bytes(original, load_ruleset())
    found = [f for f in result.before.findings if f.rule_id == "R06"]
    assert len(found) == 1 and found[0].severity == "manual"
    assert result.document_bytes == original and result.applied_rules == ()


def test_field_from_another_table_cell_cannot_certify_heading_boundary(eom_fixtures):
    document = Document(eom_fixtures["bad_r06"])
    paragraph = heading(document)
    table = document.add_table(rows=1, cols=1)
    paragraph._p.addprevious(table._tbl)
    cell = table.cell(0, 0).paragraphs[0]
    field_marker(cell, "begin")
    field_instruction(cell, " REF SyntheticTarget ")
    field_marker(cell, "separate")
    cell.add_run("Згенерований результат")
    field_marker(paragraph, "end", before=True)
    original = packed(document)
    result = fix_document_bytes(original, load_ruleset())
    found = [f for f in result.before.findings if f.rule_id == "R06"]
    assert len(found) == 1 and found[0].severity == "manual"
    assert result.document_bytes == original


def test_toc_boundary_fix_still_rejects_field_instruction_corruption(
    eom_fixtures, monkeypatch, tmp_path
):
    document = Document(eom_fixtures["good"])
    contents_between_titles(document)
    source = tmp_path / "source.docx"
    document.save(source)
    original = source.read_bytes()
    original_fix = StructuralHeadingChecker.fix

    def corrupt(self, model, rule, ruleset):
        count = original_fix(self, model, rule, ruleset)
        next(model.document.element.iter(qn("w:instrText"))).text = "SYNTHETIC_PRIVATE_IDENTIFIER"
        return count

    monkeypatch.setattr(StructuralHeadingChecker, "fix", corrupt)
    with pytest.raises(FixError) as stopped:
        fix_document_bytes(original, load_ruleset())
    assert "SYNTHETIC_PRIVATE_IDENTIFIER" not in str(stopped.value)
    assert source.read_bytes() == original


def test_title_inside_a_simple_field_wrapper_is_not_literal(eom_fixtures):
    document = Document(eom_fixtures["bad_r06"])
    paragraph = heading(document)
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), " REF SyntheticHeading ")
    paragraph._p.addprevious(field)
    field.append(paragraph._p)
    original = packed(document)
    result = fix_document_bytes(original, load_ruleset())
    found = [f for f in result.before.findings if f.rule_id == "R06"]
    assert len(found) == 1 and found[0].severity == "manual"
    assert result.document_bytes == original and result.applied_rules == ()


def test_textbox_field_state_does_not_extend_into_main_story_heading(eom_fixtures):
    document = Document(eom_fixtures["bad_r06"])
    previous = document.paragraphs[0]
    picture = OxmlElement("w:pict")
    shape = etree.SubElement(picture, "{urn:schemas-microsoft-com:vml}shape")
    textbox = etree.SubElement(shape, "{urn:schemas-microsoft-com:vml}textbox")
    content = OxmlElement("w:txbxContent")
    textbox.append(content)
    inner, run = OxmlElement("w:p"), OxmlElement("w:r")
    marker = OxmlElement("w:fldChar")
    marker.set(qn("w:fldCharType"), "begin")
    run.append(marker)
    inner.append(run)
    content.append(inner)
    previous.add_run()._r.append(picture)
    result = fix_document_bytes(packed(document), load_ruleset())
    found = [f for f in result.before.findings if f.rule_id == "R06"]
    assert len(found) == 1 and found[0].severity == "error"
    assert result.applied_rules == ("R06",)
    corrected = Document(BytesIO(result.document_bytes))
    assert etree.tostring(
        next(corrected.element.iter(qn("w:txbxContent"))), method="c14n"
    ) == etree.tostring(content, method="c14n")


def test_valid_heading_uses_inherited_caps_bold_and_alignment(eom_fixtures, body_check):
    document = Document(eom_fixtures["good"])
    paragraph = heading(document)
    run = paragraph.runs[0]
    assert paragraph.text == "Вступ" and not paragraph.text.isupper()
    assert run.font.all_caps is run.bold is paragraph.alignment is None
    model = DocumentModel(document)
    parts = {str(part.partname): part.blob for part in document.part.package.parts}
    assert model.effective_caps(run).value is True
    assert model.effective_bold(run).value is True
    assert model.effective_alignment(paragraph).value == "justify"
    assert body_check(document, "R06") == ()
    assert parts == {str(part.partname): part.blob for part in document.part.package.parts}


@pytest.mark.parametrize(
    "property", ["align", "uppercase", "bold", "font", "size_pt", "line_spacing"]
)
def test_each_required_property_is_checked_with_location_and_quote(
    eom_fixtures, body_check, property
):
    document = Document(eom_fixtures["good"])
    paragraph = heading(document)
    run = paragraph.runs[0]
    match property:
        case "align":
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        case "uppercase":
            run.font.all_caps = False
        case "bold":
            run.bold = False
        case "font":
            run.font.name = "Calibri"
        case "size_pt":
            run.font.size = Pt(12)
        case "line_spacing":
            paragraph.paragraph_format.line_spacing = Pt(21)
    findings = body_check(document, "R06")
    assert len(findings) == 1
    finding = findings[0]
    assert finding.severity == "error" and finding.fixable
    assert finding.location.paragraph == 2
    assert finding.location.excerpt == paragraph.text
    assert finding.location.page is None
    assert set(finding.actual) == {property}
    assert finding.expected == {property: load_ruleset().rules[5].params[property]}
    assert finding.quote == load_ruleset().rules[5].quote
    assert finding.source_id == "styles"


def test_all_properties_are_fixed_without_changing_text_style_or_page_break(eom_fixtures):
    document = Document(eom_fixtures["good"])
    paragraph = heading(document)
    paragraph.runs[0].text = "Вступ."
    run = paragraph.runs[0]
    run.font.name, run.font.size, run.bold, run.font.all_caps = "Calibri", Pt(12), False, False
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.line_spacing = Pt(21)
    paragraph.paragraph_format.space_before = Pt(9)
    paragraph.paragraph_format.keep_with_next = True
    original = packed(document)
    result = fix_document_bytes(original, load_ruleset(), document_type="laboratory_report")
    assert result.applied_rules == ("R06",)
    assert result.before.summary.errors == result.before.summary.fixable == 1
    assert result.after.summary.errors == result.after.summary.fixable == 0
    assert result.after.summary.manual == 7
    fixed = Document(BytesIO(result.document_bytes))
    corrected = heading(fixed)
    assert corrected.text == "Вступ."
    assert corrected.style.style_id == paragraph.style.style_id
    assert corrected.paragraph_format.page_break_before is None
    assert corrected.paragraph_format.space_before.pt == 9
    assert corrected.paragraph_format.keep_with_next is True
    model = DocumentModel(fixed)
    assert model.effective_bold(corrected.runs[0]).value is True
    assert model.effective_caps(corrected.runs[0]).value is True
    assert model.effective_alignment(corrected).value == "justify"
    assert model.effective_line_spacing(corrected).value.multiplier == 1.5
    with ZipFile(BytesIO(original)) as before, ZipFile(BytesIO(result.document_bytes)) as after:
        assert before.namelist() == after.namelist()
        for name in before.namelist():
            if name != "word/document.xml":
                assert before.read(name) == after.read(name)
    assert [node.text for node in document.element.iter(qn("w:t"))] == [
        node.text for node in fixed.element.iter(qn("w:t"))
    ]
    assert len(fixed.tables) == len(fixed.inline_shapes) == 3
    assert (
        fix_document_bytes(result.document_bytes, load_ruleset()).document_bytes
        == result.document_bytes
    )


def test_uppercase_text_alone_does_not_prove_caps_formatting(eom_fixtures, body_check):
    document = Document(eom_fixtures["good"])
    paragraph = heading(document)
    paragraph.runs[0].text = "ВСТУП"
    paragraph.runs[0].font.all_caps = False
    findings = body_check(document, "R06")
    assert len(findings) == 1 and findings[0].actual == {"uppercase": False}


def test_character_style_toggle_is_combined_with_paragraph_style(eom_fixtures):
    document = Document(eom_fixtures["good"])
    run = heading(document).runs[0]
    character = document.styles.add_style("Synthetic Heading Character", WD_STYLE_TYPE.CHARACTER)
    character.font.bold = True
    run.style = character
    model = DocumentModel(document)
    assert model.effective_bold(run).value is False
    result = fix_document_bytes(packed(document), load_ruleset())
    assert result.applied_rules == ("R06",)
    assert result.after.summary.errors == 0
    corrected = Document(BytesIO(result.document_bytes))
    assert heading(corrected).runs[0].style.name == character.name
    assert heading(corrected).runs[0].bold is True


@pytest.mark.parametrize("property", ["bold", "all_caps"])
def test_ambiguous_repeated_style_toggles_are_manual(eom_fixtures, property):
    document = Document(eom_fixtures["good"])
    setattr(heading(document).style.font, property, True)
    original = packed(document)
    result = fix_document_bytes(original, load_ruleset())
    findings = [item for item in result.before.findings if item.rule_id == "R06"]
    assert findings and all(item.severity == "manual" for item in findings)
    assert result.applied_rules == () and result.document_bytes == original


def test_direct_false_overrides_ambiguous_style_toggle_without_guessing(eom_fixtures):
    document = Document(eom_fixtures["good"])
    paragraph = heading(document)
    paragraph.style.font.bold = True
    paragraph.runs[0].bold = False
    result = fix_document_bytes(packed(document), load_ruleset())
    assert result.applied_rules == ("R06",) and result.after.summary.errors == 0


def test_small_caps_is_replaced_by_full_caps_without_rewriting_letters(eom_fixtures):
    document = Document(eom_fixtures["good"])
    run = heading(document).runs[0]
    run.font.all_caps, run.font.small_caps = False, True
    result = fix_document_bytes(packed(document), load_ruleset())
    assert result.applied_rules == ("R06",)
    fixed = Document(BytesIO(result.document_bytes))
    corrected = heading(fixed).runs[0]
    assert corrected.text == run.text
    assert corrected.font.all_caps is True and corrected.font.small_caps is False
    assert result.after.summary.errors == 0


def test_conflicting_caps_and_small_caps_are_manual(eom_fixtures):
    document = Document(eom_fixtures["good"])
    run = heading(document).runs[0]
    run.font.all_caps = run.font.small_caps = True
    original = packed(document)
    result = fix_document_bytes(original, load_ruleset())
    assert result.applied_rules == () and result.document_bytes == original
    assert any(
        item.rule_id == "R06" and item.severity == "manual" for item in result.after.findings
    )


@pytest.mark.parametrize(
    "problem",
    ["body_style", "normal", "caption", "numbering", "revision", "missing_style", "field"],
)
def test_unknown_or_conflicting_roles_are_never_fixed(eom_fixtures, problem):
    document = Document(eom_fixtures["good"])
    paragraph = heading(document)
    paragraph.runs[0].text = "Вступ."
    match problem:
        case "body_style":
            paragraph.style = document.styles["ЕОМ: Основний"]
        case "normal":
            paragraph.style = document.styles["Normal"]
        case "caption":
            paragraph.style = document.styles["ЕОМ: Назва рисунку"]
        case "numbering":
            paragraph._p.get_or_add_pPr().get_or_add_numPr().get_or_add_numId().val = 1
        case "revision":
            paragraph._p.get_or_add_pPr().append(OxmlElement("w:pPrChange"))
        case "missing_style":
            paragraph._p.pPr.pStyle.val = "MissingSyntheticStyle"
        case "field":
            paragraph.runs[0].text = ""
            field = OxmlElement("w:fldSimple")
            field.set(qn("w:instr"), "REF SyntheticHeading")
            run, text = OxmlElement("w:r"), OxmlElement("w:t")
            text.text = "Вступ."
            run.append(text)
            field.append(run)
            paragraph._p.append(field)
    original = packed(document)
    result = fix_document_bytes(original, load_ruleset())
    assert result.applied_rules == () and result.document_bytes == original
    findings = [item for item in result.before.findings if item.rule_id == "R06"]
    assert len(findings) == 1 and findings[0].severity == "manual"


def test_known_heading_with_other_style_is_corrected_without_assigning_eom_style(eom_fixtures):
    document = Document(eom_fixtures["good"])
    paragraph = heading(document)
    paragraph.style = document.styles["Heading 2"]
    source_style = paragraph.style.style_id
    result = fix_document_bytes(packed(document), load_ruleset())
    assert result.applied_rules == ("R06",)
    assert {item.rule_id for item in result.after.findings if item.severity == "error"} == {"R07"}
    fixed = Document(BytesIO(result.document_bytes))
    assert fixed.paragraphs[1].style.style_id == source_style
    assert fixed.paragraphs[1].text == "Вступ"


def test_unknown_names_and_absent_structural_parts_are_not_required(eom_fixtures, body_check):
    document = Document(eom_fixtures["good"])
    for paragraph in document.paragraphs:
        if paragraph.style.name == load_ruleset().rules[5].params["style"]:
            paragraph.runs[0].text = "Інший заголовок"
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    assert body_check(document, "R06") == ()


def test_structural_names_are_read_from_ruleset_data(eom_fixtures):
    document = Document(eom_fixtures["bad_r06"])
    heading(document).runs[0].text = "Підсумок"
    ruleset = load_ruleset().model_copy(update={"structural_headings": ("ПІДСУМОК",)})
    result = fix_document_bytes(packed(document), ruleset)
    assert result.applied_rules == ("R06",) and result.after.summary.errors == 0


def test_known_alignment_error_is_fixed_while_unknown_run_is_preserved(eom_fixtures):
    document = Document(eom_fixtures["bad_r06"])
    run = heading(document).runs[0]
    style = OxmlElement("w:rStyle")
    style.set(qn("w:val"), "MissingSyntheticStyle")
    run._r.get_or_add_rPr().append(style)
    original_run = bytes(run._r.xml, "utf-8")
    result = fix_document_bytes(packed(document), load_ruleset())
    assert result.applied_rules == ("R06",)
    assert result.before.summary.manual == result.after.summary.manual
    assert result.after.summary.errors == 0
    corrected = Document(BytesIO(result.document_bytes))
    assert bytes(heading(corrected).runs[0]._r.xml, "utf-8") == original_run


@pytest.mark.parametrize(
    "property", ["align", "uppercase", "bold", "font", "size_pt", "line_spacing"]
)
def test_heading_parameters_are_data_driven(eom_fixtures, body_check, property):
    values = dict(load_ruleset().rules[5].params)
    values[property] = {
        "align": "center",
        "uppercase": False,
        "bold": False,
        "font": "Calibri",
        "size_pt": 12,
        "line_spacing": 2,
    }[property]
    findings = body_check(Document(eom_fixtures["good"]), "R06", parameters=values)
    assert findings and all(item.severity == "error" and item.fixable for item in findings)
    assert all(item.expected == {property: values[property]} for item in findings)


@pytest.mark.parametrize(
    "property,value",
    [
        ("bold", "true"),
        ("uppercase", 1),
        ("align", "unknown"),
        ("size_pt", 0),
        ("line_spacing", True),
        ("font", ""),
    ],
)
def test_invalid_rule_parameters_are_manual(eom_fixtures, body_check, property, value):
    values = {**load_ruleset().rules[5].params, property: value}
    findings = body_check(Document(eom_fixtures["good"]), "R06", parameters=values)
    assert len(findings) == 1 and findings[0].severity == "manual"
    assert findings[0].location.paragraph is None


def test_yaml_autofix_false_keeps_heading_untouched(eom_fixtures):
    ruleset = load_ruleset()
    ruleset = ruleset.model_copy(
        update={
            "rules": tuple(
                rule.model_copy(update={"autofix": False}) if rule.id == "R06" else rule
                for rule in ruleset.rules
            )
        }
    )
    original = eom_fixtures["bad_r06"].read_bytes()
    result = fix_document_bytes(original, ruleset)
    assert result.document_bytes == original and result.applied_rules == ()
    assert result.after.summary.errors == 1 and result.after.summary.fixable == 0


@pytest.mark.parametrize("corruption", ["body_bold", "style", "text", "page_break"])
def test_heading_permissions_do_not_weaken_other_content_guards(
    eom_fixtures, monkeypatch, corruption
):
    original_fix = StructuralHeadingChecker.fix

    def corrupt(self, model, rule, ruleset):
        count = original_fix(self, model, rule, ruleset)
        paragraph = heading(model.document)
        if corruption == "body_bold":
            model.document.paragraphs[0].runs[0].bold = True
        elif corruption == "style":
            paragraph.style = model.document.styles["Normal"]
        elif corruption == "text":
            paragraph.runs[0].text = "SYNTHETIC_PRIVATE_IDENTIFIER"
        else:
            paragraph.paragraph_format.page_break_before = False
        return count

    monkeypatch.setattr(StructuralHeadingChecker, "fix", corrupt)
    source = eom_fixtures["bad_r06"]
    original = source.read_bytes()
    with pytest.raises(FixError) as stopped:
        fix_document_bytes(original, load_ruleset())
    assert "SYNTHETIC_PRIVATE_IDENTIFIER" not in str(stopped.value)
    assert source.read_bytes() == original


def test_missing_name_configuration_is_manual_without_guessing(eom_fixtures):
    ruleset = load_ruleset().model_copy(update={"structural_headings": ()})
    report = RuleEngine().check(Document(eom_fixtures["good"]), ruleset)
    findings = [item for item in report.findings if item.rule_id == "R06"]
    assert len(findings) == 1 and findings[0].severity == "manual"
    assert findings[0].location.paragraph is None


def test_complex_script_heading_bold_uses_bcs_without_changing_text(eom_fixtures):
    document = Document(eom_fixtures["good"])
    run = heading(document).runs[0]
    properties = run._r.get_or_add_rPr()
    properties.append(OxmlElement("w:cs"))
    size = OxmlElement("w:szCs")
    size.set(qn("w:val"), "28")
    properties.insert_element_before(size, "w:cs")
    result = fix_document_bytes(packed(document), load_ruleset())
    assert result.applied_rules == ("R06",) and result.after.summary.errors == 0
    fixed = Document(BytesIO(result.document_bytes))
    corrected = heading(fixed).runs[0]
    assert corrected.text == run.text
    assert corrected._r.rPr.bCs.val is True
    assert corrected._r.rPr.b is None


@pytest.mark.parametrize("tag", ["b", "caps"])
def test_true_defaults_combined_with_style_toggles_are_manual(eom_fixtures, tag):
    document = Document(eom_fixtures["good"])
    defaults = document.styles.element.find(".//" + qn("w:rPrDefault") + "/" + qn("w:rPr"))
    getattr(defaults, "get_or_add_" + tag)().val = True
    original = packed(document)
    result = fix_document_bytes(original, load_ruleset())
    findings = [item for item in result.before.findings if item.rule_id == "R06"]
    assert findings and all(item.severity == "manual" for item in findings)
    assert result.applied_rules == () and result.document_bytes == original


@pytest.mark.parametrize("property", ["bold", "align"])
def test_unknown_property_values_are_manual_without_leaking_xml(eom_fixtures, property):
    document = Document(eom_fixtures["good"])
    paragraph = heading(document)
    if property == "bold":
        flag = paragraph.runs[0]._r.get_or_add_rPr().get_or_add_b()
    else:
        flag = paragraph._p.get_or_add_pPr().get_or_add_jc()
    flag.set(qn("w:val"), "SYNTHETIC_PRIVATE_IDENTIFIER")
    original = packed(document)
    result = fix_document_bytes(original, load_ruleset())
    assert result.document_bytes == original and result.applied_rules == ()
    findings = [item for item in result.after.findings if item.rule_id == "R06"]
    assert len(findings) == 1 and findings[0].severity == "manual"
    assert "SYNTHETIC_PRIVATE_IDENTIFIER" not in result.after.model_dump_json()


@pytest.mark.parametrize("kind", ["paragraph", "character"])
def test_tracked_style_formatting_is_not_overwritten(eom_fixtures, kind):
    document = Document(eom_fixtures["good"])
    paragraph = heading(document)
    if kind == "paragraph":
        style = paragraph.style
    else:
        style = document.styles.add_style("Synthetic Tracked Character", WD_STYLE_TYPE.CHARACTER)
        style.font.name = "Calibri"
        paragraph.runs[0].style = style
    style.element.get_or_add_rPr().append(OxmlElement("w:rPrChange"))
    original = packed(document)
    result = fix_document_bytes(original, load_ruleset())
    findings = [item for item in result.after.findings if item.rule_id == "R06"]
    assert findings and all(item.severity == "manual" for item in findings)
    assert result.applied_rules == () and result.document_bytes == original


def test_explicit_body_role_alias_conflicts_with_heading_inheritance(eom_fixtures):
    document = Document(eom_fixtures["good"])
    style = document.styles.add_style("Synthetic Explicit Body", WD_STYLE_TYPE.PARAGRAPH)
    style.base_style = document.styles["Heading 2"]
    heading(document).style = style
    ruleset = load_ruleset()
    ruleset = ruleset.model_copy(
        update={
            "rules": tuple(
                rule.model_copy(
                    update={"params": {**rule.params, "body_styles": [style.name, "ЕОМ: Основний"]}}
                )
                if rule.id in {"R03", "R04", "R05"}
                else rule
                for rule in ruleset.rules
            )
        }
    )
    original = packed(document)
    result = fix_document_bytes(original, ruleset)
    assert result.document_bytes == original and result.applied_rules == ()
    assert any(
        item.rule_id == "R06" and item.severity == "manual" for item in result.after.findings
    )
