"""R07 authored page starts, inherited flags and uncertain layout boundaries."""

from io import BytesIO

import pytest
from docx import Document
from docx.enum.section import WD_SECTION_START
from docx.enum.text import WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from oformleno.engine import RuleEngine
from oformleno.fixer import fix_document_bytes
from oformleno.loader import load_document
from oformleno.model import DocumentModel
from oformleno.ruleset import load_ruleset


def heading(document):
    return next(p for p in document.paragraphs if p.text == "Вступ")


def test_inherited_break_and_direct_false_with_source(eom_fixtures, body_check):
    document = Document(eom_fixtures["good"])
    paragraph = heading(document)
    assert paragraph.paragraph_format.page_break_before is None
    assert body_check(document, "R07") == ()
    paragraph.paragraph_format.page_break_before = False
    findings = body_check(document, "R07")
    assert len(findings) == 1
    item = findings[0]
    assert item.severity == "error" and not item.fixable
    assert item.actual == {"start_on_new_page": False}
    assert item.expected == {"start_on_new_page": True}
    assert item.location.paragraph == 2 and item.location.excerpt == "Вступ"
    assert item.location.page is None
    rule = next(rule for rule in load_ruleset().rules if rule.id == "R07")
    assert item.quote == rule.quote
    assert item.parameter_sources


@pytest.mark.parametrize("position", ["tail", "prefix", "empty", "hyperlink"])
def test_explicit_page_breaks_without_inherited_flag(eom_fixtures, body_check, position):
    document = Document(eom_fixtures["bad_r07"])
    paragraph = heading(document)
    if position == "tail":
        document.paragraphs[0].add_run().add_break(WD_BREAK.PAGE)
    elif position == "prefix":
        run = paragraph.add_run()
        run.add_break(WD_BREAK.PAGE)
        paragraph._p.insert(1, run._r)
    elif position == "empty":
        previous = paragraph.insert_paragraph_before()
        previous.paragraph_format.page_break_before = True
    else:
        link = OxmlElement("w:hyperlink")
        run = document.paragraphs[0].add_run()
        run.add_break(WD_BREAK.PAGE)
        link.append(run._r)
        document.paragraphs[0]._p.append(link)
    assert body_check(document, "R07") == ()


def test_first_content_needs_no_break(eom_fixtures, body_check):
    document = Document(eom_fixtures["bad_r07"])
    paragraph = document.paragraphs[0]
    paragraph._p.getparent().remove(paragraph._p)
    assert body_check(document, "R07") == ()


@pytest.mark.parametrize(
    "kind", [WD_SECTION_START.NEW_PAGE, WD_SECTION_START.ODD_PAGE, WD_SECTION_START.EVEN_PAGE]
)
def test_section_start_uses_following_properties(eom_fixtures, body_check, kind):
    document = Document(eom_fixtures["good_section_break"])
    document.sections[0].start_type = WD_SECTION_START.CONTINUOUS
    document.sections[1].start_type = kind
    assert body_check(document, "R07") == ()


@pytest.mark.parametrize("kind", [WD_SECTION_START.CONTINUOUS, WD_SECTION_START.NEW_COLUMN])
def test_non_page_section_start_needs_layout(eom_fixtures, body_check, kind):
    document = Document(eom_fixtures["good_section_break"])
    document.sections[0].start_type = WD_SECTION_START.NEW_PAGE
    document.sections[1].start_type = kind
    findings = body_check(document, "R07")
    assert len(findings) == 1 and findings[0].severity == "manual"


@pytest.mark.parametrize("content", ["text", "field", "cached", "hidden", "table"])
def test_content_after_a_break_does_not_prove_heading_start(eom_fixtures, body_check, content):
    document = Document(eom_fixtures["good_page_break"])
    previous = document.paragraphs[0]
    if content == "text":
        previous.add_run("Текст після розриву")
    elif content == "field":
        field = OxmlElement("w:fldSimple")
        field.set(qn("w:instr"), "PAGE")
        previous._p.append(field)
    elif content == "cached":
        previous.add_run()._r.append(OxmlElement("w:lastRenderedPageBreak"))
    elif content == "hidden":
        previous.add_run("Прихований текст").font.hidden = True
    else:
        table = document.add_table(rows=1, cols=1)
        heading(document)._p.addprevious(table._tbl)
    findings = body_check(document, "R07")
    assert len(findings) == 1
    assert findings[0].severity == ("error" if content == "text" else "manual")


def test_later_explicit_break_resolves_earlier_uncertain_content(eom_fixtures, body_check):
    document = Document(eom_fixtures["bad_r07"])
    previous = document.paragraphs[0]
    previous._p.append(OxmlElement("w:fldSimple"))
    previous.add_run().add_break(WD_BREAK.PAGE)
    assert body_check(document, "R07") == ()


def test_unknown_prefix_after_previous_break_requires_review(eom_fixtures, body_check):
    document = Document(eom_fixtures["good_page_break"])
    paragraph = heading(document)
    paragraph._p.insert(1, OxmlElement("w:lastRenderedPageBreak"))
    findings = body_check(document, "R07")
    assert len(findings) == 1 and findings[0].severity == "manual"


def test_default_frame_geometry_requires_review(eom_fixtures, body_check):
    document = Document(eom_fixtures["good"])
    defaults = document.styles.element.find(qn("w:docDefaults"))
    properties = defaults.find(qn("w:pPrDefault")).find(qn("w:pPr"))
    properties.append(OxmlElement("w:framePr"))
    findings = body_check(document, "R07")
    assert findings and all(item.severity == "manual" for item in findings)


@pytest.mark.parametrize("change", ["flag", "style", "revision", "hidden", "frame"])
def test_uncertain_heading_configuration_is_manual(eom_fixtures, body_check, change):
    document = Document(eom_fixtures["good"])
    paragraph = heading(document)
    if change == "flag":
        paragraph._p.get_or_add_pPr().append(OxmlElement("w:pageBreakBefore"))
        paragraph._p.pPr.pageBreakBefore.set(qn("w:val"), "unknown")
    elif change == "style":
        paragraph._p.pPr.pStyle.set(qn("w:val"), "missing-style")
    elif change == "revision":
        paragraph._p.pPr.append(OxmlElement("w:pPrChange"))
    elif change == "hidden":
        paragraph.runs[0].font.hidden = True
    else:
        paragraph.style.element.get_or_add_pPr().append(OxmlElement("w:framePr"))
    findings = body_check(document, "R07")
    assert findings and all(item.severity == "manual" for item in findings)


@pytest.mark.parametrize(
    "parameters",
    [{"style": "Заголовок", "start_on_new_page": False}, {"style": "", "start_on_new_page": True}],
)
def test_unsupported_parameters_are_manual(eom_fixtures, body_check, parameters):
    findings = body_check(Document(eom_fixtures["good"]), "R07", parameters=parameters)
    assert len(findings) == 1 and findings[0].severity == "manual"


def test_check_is_read_only_and_fix_keeps_r07_error(eom_fixtures):
    path = eom_fixtures["bad_r07"]
    original = path.read_bytes()
    document = load_document(path)
    parts = {str(part.partname): part.blob for part in document.part.package.parts}
    model = DocumentModel(document)
    report = RuleEngine().check(model, load_ruleset())
    assert report.failed_rules == ()
    assert parts == {str(part.partname): part.blob for part in document.part.package.parts}
    result = fix_document_bytes(original, load_ruleset())
    assert result.applied_rules == () and result.document_bytes == original
    assert result.after.summary.errors == 1 and result.after.summary.fixable == 0
    assert path.read_bytes() == original
    assert Document(BytesIO(result.document_bytes)).paragraphs[1].text == "Вступ"
