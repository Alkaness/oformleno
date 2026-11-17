"""Body-size checks resolve saved run/style/default inheritance and manual cases."""

import pytest
from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt
from fixtures.make_fixtures import BODY_BASE_STYLE, BODY_STYLE


def test_ordinary_mode_reads_size_inherited_from_normal(eom_fixtures, body_check):
    document = Document(eom_fixtures["good"])
    document.paragraphs[0].style = document.styles["Normal"]
    document.styles["Normal"].font.size = Pt(12)
    findings = body_check(document, "R04", body_text_mode="ordinary")
    assert len(findings) == 1 and findings[0].severity == "error"
    assert findings[0].actual == {"size_pt": [12]}
    assert findings[0].expected == {"size_pt": 14} and findings[0].fixable


def test_wrong_body_size_has_paragraph_location_and_yaml_expectation(eom_fixtures, body_check):
    document = Document(eom_fixtures["bad_r04"])
    findings = body_check(document, "R04")
    assert len(findings) == 1
    finding = findings[0]
    assert finding.severity == "error"
    assert finding.location.paragraph == 1
    assert finding.actual == {"size_pt": [12]}
    assert finding.expected == {"size_pt": 14}
    assert finding.quote == "Times New Roman 14"
    assert finding.fixable


@pytest.mark.parametrize("layer", ["direct", "character", "paragraph", "base", "defaults"])
def test_font_size_failure_resolves_inheritance(eom_fixtures, body_check, layer):
    document = Document(eom_fixtures["good"])
    if layer == "direct":
        document.paragraphs[0].runs[0].font.size = Pt(12)
    elif layer == "character":
        style = document.styles.add_style("Synthetic Character", WD_STYLE_TYPE.CHARACTER)
        style.font.size = Pt(12)
        document.paragraphs[0].runs[0].style = style
    elif layer == "paragraph":
        document.styles[BODY_STYLE].font.size = Pt(12)
    elif layer == "base":
        document.styles[BODY_BASE_STYLE].font.size = Pt(12)
    else:
        document.styles[BODY_BASE_STYLE].font.size = None
        defaults = document.styles.element.find(".//" + qn("w:rPrDefault") + "/" + qn("w:rPr"))
        defaults.find(qn("w:sz")).set(qn("w:val"), "24")
    findings = body_check(document, "R04")
    assert findings and all(item.severity == "error" for item in findings)
    assert findings[0].location.paragraph == 1
    assert all(item.actual == {"size_pt": [12]} for item in findings)


@pytest.mark.parametrize("size,errors", [(13.5, 1), (14, 0), (14.5, 1)])
def test_half_point_sizes_are_compared_without_rounding(eom_fixtures, body_check, size, errors):
    document = Document(eom_fixtures["good"])
    document.paragraphs[0].runs[0].font.size = Pt(size)
    assert len(body_check(document, "R04")) == errors


def test_known_and_unknown_sizes_are_reported_separately(eom_fixtures, body_check):
    document = Document(eom_fixtures["bad_r04"])
    run = document.paragraphs[0].add_run("Невідомий розмір")
    style = OxmlElement("w:rStyle")
    style.set(qn("w:val"), "MissingSyntheticStyle")
    run._r.get_or_add_rPr().append(style)
    findings = body_check(document, "R04")
    assert [item.severity for item in findings] == ["error", "manual"]


@pytest.mark.parametrize("case", ["good", "manual_role", "manual_inheritance"])
def test_valid_twelve_point_exceptions_and_unknown_roles(eom_fixtures, body_check, case):
    findings = body_check(Document(eom_fixtures[case]), "R04")
    if case == "good":
        assert findings == ()
    else:
        assert len(findings) == 1 and findings[0].severity == "manual"


def test_body_style_inheritance_keeps_derived_body_role(eom_fixtures, body_check):
    document = Document(eom_fixtures["good"])
    style = document.styles.add_style("Synthetic Body Child", WD_STYLE_TYPE.PARAGRAPH)
    style.base_style = document.styles[BODY_STYLE]
    style.font.size = Pt(12)
    document.paragraphs[0].style = style
    findings = body_check(document, "R04")
    assert len(findings) == 1 and findings[0].severity == "error"


@pytest.mark.parametrize("derived", [False, True])
def test_program_size_is_not_checked_as_body_size(eom_fixtures, body_check, derived):
    document = Document(eom_fixtures["bad_r04"])
    program = document.styles.add_style("ЕОМ: Програма", WD_STYLE_TYPE.PARAGRAPH)
    program.base_style = document.styles[BODY_STYLE]
    program.font.size = Pt(10)
    if derived:
        child = document.styles.add_style("Synthetic Program Child", WD_STYLE_TYPE.PARAGRAPH)
        child.base_style = program
        program = child
    document.add_paragraph("return 0;", style=program)
    findings = body_check(document, "R04")
    assert len(findings) == 1 and findings[0].severity == "error"
    assert findings[0].location.paragraph == 1


@pytest.mark.parametrize("kind", ["emoji", "symbol", "broken_size"])
def test_unresolved_script_or_size_is_manual(eom_fixtures, body_check, kind):
    document = Document(eom_fixtures["good"])
    run = document.paragraphs[0].runs[0]
    if kind == "emoji":
        run.text = "Згенерований текст 🌿"
    elif kind == "symbol":
        symbol = OxmlElement("w:sym")
        symbol.set(qn("w:font"), "Wingdings")
        symbol.set(qn("w:char"), "F020")
        run._r.append(symbol)
    else:
        size = OxmlElement("w:sz")
        size.set(qn("w:val"), "SYNTHETIC_PRIVATE_IDENTIFIER")
        run._r.get_or_add_rPr().append(size)
    findings = body_check(document, "R04")
    assert len(findings) == 1 and findings[0].severity == "manual"
    assert "SYNTHETIC_PRIVATE_IDENTIFIER" not in findings[0].model_dump_json()


def test_expected_size_comes_from_rule_data(eom_fixtures, body_check):
    document = Document(eom_fixtures["good"])
    findings = body_check(document, "R04", parameters={"role": "body", "size_pt": 12})
    assert findings and all(item.severity == "error" for item in findings)
    assert all(item.expected == {"size_pt": 12} for item in findings)


@pytest.mark.parametrize(
    "parameters",
    [
        {"role": "body", "size_pt": True},
        {"role": "body", "size_pt": "14"},
        {"role": "body", "size_pt": 0},
        {"role": "other", "size_pt": 14},
        {"role": "body", "size_pt": 14, "body_styles": []},
    ],
)
def test_invalid_size_or_role_configuration_is_manual(eom_fixtures, body_check, parameters):
    findings = body_check(Document(eom_fixtures["good"]), "R04", parameters=parameters)
    assert len(findings) == 1 and findings[0].severity == "manual"
    assert findings[0].location.paragraph is None


def test_complex_script_override_uses_szcs(eom_fixtures, body_check):
    document = Document(eom_fixtures["good"])
    run = document.paragraphs[0].runs[0]
    run.text = "مثال"
    run.font.size = Pt(14)
    properties = run._r.get_or_add_rPr()
    properties.append(OxmlElement("w:cs"))
    size = OxmlElement("w:szCs")
    size.set(qn("w:val"), "24")
    properties.append(size)
    findings = body_check(document, "R04")
    assert len(findings) == 1 and findings[0].actual == {"size_pt": [12]}
