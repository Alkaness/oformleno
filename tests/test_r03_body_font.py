"""Body font acceptance, inheritance, slot selection and conservative role detection."""

from io import BytesIO
from zipfile import ZipFile

import pytest
from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn
from docx.shared import Pt
from fixtures.make_fixtures import BODY_BASE_STYLE, BODY_STYLE, CASES

from oformleno.engine import RuleEngine
from oformleno.fixer import fix_document_bytes
from oformleno.loader import load_document
from oformleno.ruleset import load_ruleset


@pytest.mark.parametrize("mode", ["styles", "ordinary"])
@pytest.mark.parametrize("font", ["Times New Roman", "Cambria Math"])
@pytest.mark.parametrize("text", ["x ∈ A; ∀ x ∑ x ≥ 0", "⊕"])
def test_unicode_math_in_body_text_is_checked_and_fixed_in_a_preserved_copy(
    eom_fixtures, tmp_path, mode, font, text
):
    document = Document(eom_fixtures["good"])
    paragraph = document.paragraphs[0]
    if mode == "ordinary":
        paragraph.style = document.styles["Normal"]
        paragraph.paragraph_format.line_spacing = 1.5
    run = paragraph.runs[0]
    run.text = text
    run.font.name, run.font.size = font, Pt(14)
    fonts = run._r.rPr.rFonts
    fonts.set(qn("w:ascii"), "Times New Roman")
    fonts.set(qn("w:cs"), "Unused Complex Font")
    path = tmp_path / "generated.docx"
    document.save(path)
    original = path.read_bytes()
    result = fix_document_bytes(original, load_ruleset(), body_text_mode=mode)
    found = [f for f in result.before.findings if f.rule_id == "R03"]
    if font == "Cambria Math":
        assert len(found) == 1 and found[0].severity == "error" and found[0].fixable
        assert found[0].actual == {"fonts": ["Cambria Math"]}
        assert result.applied_rules == ("R03",)
    else:
        assert found == [] and result.document_bytes == original
    assert not [f for f in result.after.findings if f.rule_id in {"R03", "R04"}]
    corrected = Document(BytesIO(result.document_bytes))
    assert [node.text for node in corrected.element.iter(qn("w:t"))] == [
        node.text for node in document.element.iter(qn("w:t"))
    ]
    corrected_fonts = corrected.paragraphs[0].runs[0]._r.rPr.rFonts
    assert corrected_fonts.get(qn("w:cs")) == "Unused Complex Font"
    assert path.read_bytes() == original
    with ZipFile(BytesIO(original)) as before, ZipFile(BytesIO(result.document_bytes)) as after:
        assert before.namelist() == after.namelist()
        assert all(
            before.read(name) == after.read(name)
            for name in before.namelist()
            if name != "word/document.xml"
        )
    assert fix_document_bytes(
        result.document_bytes, load_ruleset(), body_text_mode=mode
    ).document_bytes == (result.document_bytes)


def test_ordinary_mode_finds_calibri_without_departmental_style(eom_fixtures, body_check):
    document = Document(eom_fixtures["good"])
    paragraph = document.paragraphs[0]
    paragraph.style = document.styles["Normal"]
    paragraph.runs[0].font.name = "Calibri"
    findings = body_check(document, "R03", body_text_mode="ordinary")
    assert len(findings) == 1 and findings[0].severity == "error"
    assert findings[0].actual == {"fonts": ["Calibri"]} and findings[0].fixable
    assert findings[0].location.paragraph == 1
    assert findings[0].location.excerpt == paragraph.text[:50]
    strict = body_check(document, "R03")
    assert len(strict) == 1 and strict[0].severity == "manual"


def test_calibri_acceptance_has_paragraph_excerpt_actual_expected_and_quote(eom_fixtures):
    document = load_document(eom_fixtures["bad_r03"])
    report = RuleEngine().check(document, load_ruleset())
    findings = [item for item in report.findings if item.rule_id == "R03"]
    assert len(findings) == 1
    finding = findings[0]
    assert finding.severity == "error"
    assert finding.location.paragraph == 1
    assert finding.location.excerpt == document.paragraphs[0].text[:50]
    assert finding.actual == {"fonts": ["Calibri"]}
    assert finding.expected == {"font": "Times New Roman"}
    assert finding.quote == load_ruleset().rules[2].quote
    assert finding.source_id == "styles"
    assert finding.location.page is None and finding.fixable


@pytest.mark.parametrize("case", CASES)
def test_fixture_suite_matches_errors_and_manual_expectations(eom_fixtures, case):
    report = RuleEngine().check(
        load_document(eom_fixtures[case]), load_ruleset(), document_type="laboratory_report"
    )
    available = {"R01", "R02", "R03", "R04", "R05", "R06", "R07", "R08", "R09", "R10"}
    assert {item.rule_id for item in report.findings if item.severity == "error"} == (
        set(CASES[case].error_rules) & available
    )
    assert {item.rule_id for item in report.findings if item.severity == "manual"} & available == (
        set(CASES[case].manual_rules) & available
    )
    assert report.checked_rules == (
        "R01",
        "R02",
        "R03",
        "R04",
        "R05",
        "R06",
        "R07",
        "R08",
        "R09",
        "R10",
    )
    assert report.failed_rules == ()
    assert report.unavailable_rules == ()


@pytest.mark.parametrize("layer", ["direct", "character", "paragraph", "base", "defaults", "theme"])
def test_font_failure_resolves_all_inheritance_layers(eom_fixtures, body_check, layer):
    document = Document(eom_fixtures["good"])
    run = document.paragraphs[0].runs[0]
    if layer == "direct":
        run.font.name = "Calibri"
    elif layer == "character":
        style = document.styles.add_style("Synthetic Character", WD_STYLE_TYPE.CHARACTER)
        style.font.name = "Calibri"
        run.style = style
    elif layer == "paragraph":
        document.styles[BODY_STYLE].font.name = "Calibri"
    elif layer == "base":
        document.styles[BODY_BASE_STYLE].font.name = "Calibri"
    elif layer == "defaults":
        base = document.styles[BODY_BASE_STYLE].element.rPr
        base.remove(base.rFonts)
        fonts = document.styles.element.find(
            ".//" + qn("w:rPrDefault") + "/" + qn("w:rPr") + "/" + qn("w:rFonts")
        )
        fonts.attrib.clear()
        fonts.set(qn("w:ascii"), "Calibri")
        fonts.set(qn("w:hAnsi"), "Calibri")
    else:
        fonts = document.styles[BODY_BASE_STYLE].element.rPr.rFonts
        fonts.attrib.clear()
        fonts.set(qn("w:asciiTheme"), "minorHAnsi")
        fonts.set(qn("w:hAnsiTheme"), "minorHAnsi")
        part = document.part.part_related_by(RT.THEME)
        theme = parse_xml(part.blob)
        theme.find(".//" + qn("a:minorFont") + "/" + qn("a:latin")).set("typeface", "Calibri")
        output = BytesIO()
        theme.getroottree().write(output, encoding="UTF-8", xml_declaration=True)
        part._blob = output.getvalue()
    findings = body_check(document, "R03")
    assert findings and all(item.severity == "error" for item in findings)
    assert findings[0].location.paragraph == 1
    assert all(item.actual == {"fonts": ["Calibri"]} for item in findings)


@pytest.mark.parametrize(
    "slot,text,error",
    [
        ("ascii", "Latin", True),
        ("hAnsi", "Кирилиця", True),
        ("ascii", "Кирилиця", False),
        ("hAnsi", "Latin", False),
    ],
)
def test_only_used_font_slots_are_checked(eom_fixtures, body_check, slot, text, error):
    document = Document(eom_fixtures["good"])
    run = document.paragraphs[0].runs[0]
    run.text = text
    run.font.name = "Times New Roman"
    run._r.rPr.rFonts.set(qn("w:" + slot), "Calibri")
    findings = body_check(document, "R03")
    assert len(findings) == int(error)


def test_known_error_and_unknown_run_are_both_reported(eom_fixtures, body_check):
    document = Document(eom_fixtures["bad_r03"])
    run = document.paragraphs[0].add_run("Невідоме успадкування")
    style = OxmlElement("w:rStyle")
    style.set(qn("w:val"), "MissingSyntheticStyle")
    run._r.get_or_add_rPr().append(style)
    findings = body_check(document, "R03")
    assert [item.severity for item in findings] == ["error", "manual"]
    assert findings[0].actual == {"fonts": ["Calibri"]}
    assert findings[1].actual is None


@pytest.mark.parametrize("kind", ["caption", "table", "heading", "header", "derived_caption"])
def test_non_body_elements_with_other_fonts_are_excluded(eom_fixtures, body_check, kind):
    document = Document(eom_fixtures["good"])
    if kind == "caption" or kind == "derived_caption":
        paragraph = next(p for p in document.paragraphs if p.style.name == "ЕОМ: Назва рисунку")
        if kind == "derived_caption":
            style = document.styles.add_style("Synthetic Caption Child", WD_STYLE_TYPE.PARAGRAPH)
            style.base_style = paragraph.style
            paragraph.style = style
        run = paragraph.runs[0]
    elif kind == "table":
        run = document.tables[0].cell(0, 0).paragraphs[0].runs[0]
    elif kind == "heading":
        run = next(p for p in document.paragraphs if p.style.name == "Heading 1").runs[0]
    else:
        run = document.sections[0].header.paragraphs[0].add_run("Колонтитул")
    run.font.name, run.font.size = "Calibri", Pt(12)
    assert body_check(document, "R03") == ()


def test_body_role_can_be_configured_without_code_or_profile_changes(eom_fixtures, body_check):
    document = Document(eom_fixtures["good"])
    style = document.styles.add_style("Synthetic Other Body", WD_STYLE_TYPE.PARAGRAPH)
    style.font.name = "Calibri"
    document.paragraphs[0].style = style
    findings = body_check(
        document,
        "R03",
        parameters={
            "role": "body",
            "font": "Calibri",
            "body_styles": ["Synthetic Other Body", BODY_STYLE],
        },
    )
    # The custom paragraph passes; ordinary EOM body paragraphs now violate the
    # changed expected font, proving both the role mapping and parameter are used.
    assert findings and all(item.severity == "error" for item in findings)
    assert all(item.location.paragraph != 1 for item in findings)
    assert all(item.expected == {"font": "Calibri"} for item in findings)


@pytest.mark.parametrize("derived", [False, True])
def test_program_role_overrides_inherited_body_font_role(eom_fixtures, body_check, derived):
    document = Document(eom_fixtures["bad_r03"])
    program = document.styles.add_style("ЕОМ: Програма", WD_STYLE_TYPE.PARAGRAPH)
    program.base_style = document.styles[BODY_STYLE]
    program.font.name = "Consolas"
    if derived:
        child = document.styles.add_style("Synthetic Program Child", WD_STYLE_TYPE.PARAGRAPH)
        child.base_style = program
        program = child
    document.add_paragraph("print('synthetic')", style=program)
    findings = body_check(document, "R03")
    assert len(findings) == 1 and findings[0].severity == "error"
    assert findings[0].location.paragraph == 1


def test_explicit_body_alias_conflicting_with_program_role_is_manual(eom_fixtures, body_check):
    document = Document(eom_fixtures["good"])
    program = document.styles.add_style("ЕОМ: Програма", WD_STYLE_TYPE.PARAGRAPH)
    program.base_style = document.styles[BODY_STYLE]
    program.font.name = "Consolas"
    document.add_paragraph("return 0;", style=program)
    findings = body_check(
        document,
        "R03",
        parameters={
            "role": "body",
            "font": "Times New Roman",
            "body_styles": [BODY_STYLE, program.name],
        },
    )
    assert len(findings) == 1 and findings[0].severity == "manual"


@pytest.mark.parametrize(
    "context",
    ["unknown_style", "body_heading", "body_caption", "numbering", "revision", "missing_style"],
)
def test_uncertain_roles_do_not_create_font_errors(eom_fixtures, body_check, context):
    document = Document(eom_fixtures["bad_r03"])
    paragraph = document.paragraphs[0]
    if context == "unknown_style":
        paragraph.style = document.styles.add_style("ЕОМ: Невідомий стиль", WD_STYLE_TYPE.PARAGRAPH)
    elif context == "body_heading":
        paragraph.text = "Вступ"
    elif context == "body_caption":
        paragraph.text = "Рис. 1.1 Згенерований підпис"
    elif context == "numbering":
        paragraph._p.get_or_add_pPr().get_or_add_numPr().get_or_add_numId().val = 1
    elif context == "revision":
        paragraph._p.get_or_add_pPr().append(OxmlElement("w:pPrChange"))
    else:
        paragraph._p.pPr.pStyle.val = "MissingSyntheticStyle"
    findings = body_check(document, "R03")
    assert len(findings) == 1
    assert findings[0].severity == "manual"


def test_hyperlink_text_is_checked_and_excerpts_include_it(eom_fixtures, body_check):
    document = Document(eom_fixtures["bad_r03"])
    paragraph = document.paragraphs[0]
    run = paragraph.runs[0]
    link = OxmlElement("w:hyperlink")
    paragraph._p.append(link)
    link.append(run._r)
    findings = body_check(document, "R03")
    assert len(findings) == 1 and findings[0].severity == "error"
    assert findings[0].location.excerpt.startswith("Згенерований текст")


def test_findings_do_not_log_document_content(eom_fixtures, capsys, caplog):
    path = eom_fixtures["bad_r03"]
    original = path.read_bytes()
    document = load_document(path)
    parts = {str(part.partname): part.blob for part in document.part.package.parts}
    engine = RuleEngine()
    report = engine.check(document, load_ruleset())
    assert engine.check(document, load_ruleset()).model_dump_json() == report.model_dump_json()
    assert path.read_bytes() == original
    assert parts == {str(part.partname): part.blob for part in document.part.package.parts}
    captured = capsys.readouterr()
    assert captured.out == captured.err == "" and not caplog.records


def test_body_in_content_control_keeps_paragraph_number_and_excerpt(eom_fixtures, body_check):
    document = Document(eom_fixtures["bad_r03"])
    paragraph = document.paragraphs[0]
    empty = OxmlElement("w:p")
    paragraph._p.addprevious(empty)
    control, content = OxmlElement("w:sdt"), OxmlElement("w:sdtContent")
    control.append(content)
    paragraph._p.addprevious(control)
    content.append(paragraph._p)
    findings = body_check(document, "R03")
    assert len(findings) == 1 and findings[0].severity == "error"
    assert findings[0].location.paragraph == 2
    assert findings[0].location.excerpt == paragraph.text[:50]


def test_complex_script_override_selects_cs_font(eom_fixtures, body_check):
    document = Document(eom_fixtures["good"])
    run = document.paragraphs[0].runs[0]
    run.text = "مثال"
    run.font.name = "Times New Roman"
    run._r.rPr.rFonts.set(qn("w:cs"), "Calibri")
    run._r.rPr.append(OxmlElement("w:cs"))
    findings = body_check(document, "R03")
    assert len(findings) == 1 and findings[0].actual == {"fonts": ["Calibri"]}


def test_invalid_font_parameter_is_manual(eom_fixtures, body_check):
    findings = body_check(
        Document(eom_fixtures["good"]), "R03", parameters={"role": "body", "font": ""}
    )
    assert len(findings) == 1 and findings[0].severity == "manual"


def test_missing_style_part_is_not_created_or_guessed(eom_fixtures, tmp_path):
    document = Document(eom_fixtures["good"])
    for relation in list(document.part.rels.values()):
        if relation.reltype == RT.STYLES:
            document.part.drop_rel(relation.rId)
    path = tmp_path / "generated.docx"
    document.save(path)
    document = load_document(path)
    parts = {str(part.partname): part.blob for part in document.part.package.parts}
    report = RuleEngine().check(document, load_ruleset())
    assert not report.failed_rules
    assert all(
        item.severity == "manual"
        for item in report.findings
        if item.rule_id in {"R03", "R04", "R05"}
    )
    assert parts == {str(part.partname): part.blob for part in document.part.package.parts}
