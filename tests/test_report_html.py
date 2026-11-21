"""Exercise human-readable reports using synthetic findings and generated DOCX."""

import pytest
from caption_helpers import change_code, code_nodes, example
from lxml import html

from oformleno.engine import Finding, Location, Report, RuleEngine
from oformleno.fixer import fix_document_bytes
from oformleno.loader import load_document
from oformleno.report_html import render_report_html
from oformleno.ruleset import load_ruleset


def finding(**changes):
    values = {
        "rule_id": "R02",
        "rule_name": "Поля",
        "severity": "error",
        "location": Location(section=2),
        "actual": {"left_mm": 20.0025},
        "expected": {"left_mm": 25},
        "quote": "Цитата\nз джерела.",
        "message": "Ліве поле потребує виправлення.",
        "fixable": True,
    }
    return Finding(**(values | changes))


def report(*findings, **changes):
    return Report(
        **(
            {
                "ruleset_id": "generated",
                "ruleset_title": "Згенеровані вимоги",
                "ruleset_status": "reviewed",
                "findings": findings,
            }
            | changes
        )
    )


def parsed(value):
    return html.fromstring(render_report_html(value))


def body_text(tree):
    return tree.find("body").text_content()


def test_manual_findings_have_one_secondary_closed_disclosure_and_keep_all_evidence():
    manuals = [
        finding(
            severity="manual",
            fixable=False,
            location=Location(paragraph=index, excerpt=f"Згенерований уривок {index}."),
            message=f"Згенерована причина {index}.",
            quote=f"Згенерована цитата {index}.",
        )
        for index in range(1, 38)
    ]
    manuals.append(finding(rule_id="M01", severity="manual", fixable=False))
    value = report(finding(), *manuals)
    original = value.model_dump_json()
    tree = parsed(value)
    disclosure = tree.get_element_by_id("manual")
    assert disclosure.tag == "details" and "open" not in disclosure.attrib
    summary = disclosure.find("summary")
    assert summary is not None and "Перевірте самі" in summary.text_content()
    assert "38" in summary.text_content()
    assert len(disclosure.xpath('.//div[@class="finding"]')) == 38
    assert len(tree.xpath('//*[@id="findings"]//div[@class="finding"]')) == 1
    assert not tree.xpath('//nav//a[@href="#manual"]')
    groups = disclosure.xpath('.//details[contains(@class,"manual-group")]')
    assert len(groups) == 2 and all("open" not in group.attrib for group in groups)
    assert not disclosure.xpath('.//article[contains(@class,"rule-group")]')
    for item in manuals:
        assert item.message in disclosure.text_content()
        assert item.quote in disclosure.text_content()
        if item.location.excerpt:
            assert item.location.excerpt in disclosure.text_content()
    assert value.model_dump_json() == original


def test_readable_locations_values_and_exact_source_evidence():
    item = finding(
        location=Location(section=2, paragraph=12, page=4, excerpt="Згенерований уривок."),
        source_id="styles",
        source_location="Параметри сторінки",
        supporting_quote="Додаткова точна цитата.",
    )
    tree = parsed(report(item))
    text = body_text(tree)
    assert "Секція 2 · Абзац 12 · Сторінка 4" in text
    assert "Згенерований уривок." in text
    assert "Ліве поле, мм" in text and "20,0025" in text and "25" in text
    assert tree.xpath("//blockquote/text()") == [item.quote, item.supporting_quote]
    assert "Стилі кафедри ЕОМ · Параметри сторінки" in text
    assert "Можна виправити автоматично" in text


def test_groups_each_rule_once_without_losing_locations_or_severities():
    items = [
        finding(location=Location(section=1)),
        finding(rule_id="R03", rule_name="Шрифт", fixable=False),
        finding(location=Location(section=3), severity="warning", fixable=False),
        finding(severity="manual", location=Location(paragraph=5), fixable=False),
    ]
    tree = parsed(report(*items))
    groups = tree.xpath('//*[@id="findings"]//article')
    assert len(groups) == 2
    assert len(groups[0].xpath('.//div[@class="finding"]')) == 2
    assert "Секція 1" in groups[0].text_content() and "Секція 3" in groups[0].text_content()
    assert "Попередження" in groups[0].text_content()
    assert len(tree.xpath('//*[@id="manual"]//details[contains(@class,"manual-group")]')) == 1
    text = tree.xpath("//aside")[0].text_content()
    assert "Знайдено 2 помилки, 1 можна виправити автоматично." in text
    assert "Попередження: 1" in text and "Перевірте самі: 1" in text


@pytest.mark.parametrize("severity", ["error", "manual"])
def test_all_untrusted_content_is_text_and_never_attributes_or_executable_html(severity):
    hostile = '"><img src="https://invalid.example/x" onerror="alert(1)"><script>x</script>&'
    item = finding(
        severity=severity,
        fixable=False,
        rule_id=hostile,
        rule_name=hostile,
        message=hostile,
        quote=hostile,
        supporting_quote=hostile,
        source_id=hostile,
        source_location=hostile,
        location=Location(excerpt="<script>alert(1)</script>"),
        actual={hostile: [hostile, {"nested": hostile}]},
        expected=hostile,
        parameter_sources={hostile: hostile},
        source_notes={hostile: hostile},
    )
    value = report(
        item,
        ruleset_title=hostile,
        checked_rules=(hostile,),
        failed_rules=(hostile,),
        unavailable_rules=(hostile,),
        not_applicable=(hostile,),
    )
    tree = parsed(value)
    assert not tree.xpath("//script|//img|//iframe|//object|//link|//form")
    assert not tree.xpath("//*[@onerror or @onclick or @src]")
    assert all(link.startswith("#") for link in tree.xpath("//a/@href"))
    assert hostile in body_text(tree)
    assert "<script>alert(1)</script>" in body_text(tree)
    assert hostile not in tree.find("head").text_content()
    assert all(hostile not in attr for node in tree.iter() for attr in node.attrib.values())


@pytest.mark.parametrize("count", [7, 1357])
def test_manual_grouping_never_truncates_large_reports(count):
    items = [
        finding(severity="manual", fixable=False, location=Location(paragraph=index))
        for index in range(1, count + 1)
    ]
    tree = parsed(report(*items))
    disclosure = tree.get_element_by_id("manual")
    assert "open" not in disclosure.attrib
    assert f"Висновків: {count}" in disclosure.find("summary").text_content()
    assert len(disclosure.xpath('.//div[@class="finding"]')) == count
    locations = disclosure.xpath('.//p[@class="location"]/text()')
    assert locations == [f"Абзац {index}" for index in range(1, count + 1)]


@pytest.mark.parametrize(
    "actual,expected,visible",
    [
        ({"kind": "exact", "value": 21}, {"kind": "multiple", "value": 1.5}, "точно 21 пт"),
        (
            {"line_spacing": {"kind": "at_least", "value": 21}},
            {"line_spacing": 1.5},
            "щонайменше 21 пт",
        ),
        ({"align": "center", "bold": False}, {"align": "justify", "bold": True}, "по ширині"),
        ({"font": ["Calibri", "Arial"]}, {"font": "Times New Roman"}, "Arial"),
        ({"nested": {"unexpected": [None, False, 14.5, {}, []]}}, {}, "14,5"),
        (None, "", "Порожній рядок"),
    ],
)
def test_json_values_stay_readable_without_losing_nested_data(actual, expected, visible):
    text = body_text(parsed(report(finding(actual=actual, expected=expected))))
    assert visible in text
    if actual is None:
        assert "Не визначено" in text


def test_clarification_provenance_is_separate_from_exact_quotes():
    item = finding(
        rule_id="R07",
        parameter_sources={"start_on_new_page": "user_reference"},
        source_notes={"user_reference": "Уточнення профілю за зразком користувача."},
        source_id="styles",
        fixable=False,
    )
    tree = parsed(report(item))
    assert tree.xpath("//blockquote/text()") == [item.quote]
    provenance = tree.xpath('//div[@class="provenance"]')[0].text_content()
    assert "Зразок, обраний користувачем" in provenance
    assert "Починати з нової сторінки" in provenance
    assert item.source_notes["user_reference"] in provenance
    assert "Автовиправлення недоступне" in body_text(tree)


@pytest.mark.parametrize(
    "document_type,count",
    [
        ("laboratory_report", 7),
        ("qualification_thesis", 8),
        (None, 8),
    ],
)
def test_real_engine_checklist_applicability_and_quotes(eom_fixtures, document_type, count):
    ruleset = load_ruleset()
    result = RuleEngine().check(
        load_document(eom_fixtures["good"]), ruleset, document_type=document_type
    )
    before = result.model_dump_json()
    tree = parsed(result)
    text = body_text(tree)
    assert result.summary.errors == 0 and result.summary.manual == count
    assert f"Пункти переліку ЕОМ: {count}. Інші ручні висновки: 0." in text
    assert "Перевірку не завершено: потрібен ручний перегляд." in text
    assert "Повний нормоконтроль потребує окремого перегляду." in text
    manual = tree.xpath('//*[@id="manual"]//details[contains(@class,"manual-group")]')
    assert len(manual) == count
    assert all(item.quote in text and item.message in text for item in result.findings)
    for group in manual:
        if any(identifier in group.text_content() for identifier in ("M05", "M08")):
            assert not group.xpath('.//div[@class="values"]')
    if document_type == "laboratory_report":
        assert not any("M06" in group.text_content() for group in manual)
        assert "60" not in text and "100" not in text
    elif document_type is None:
        assert "Тип роботи не вказано. Уточніть застосовність" in text
        assert "Застосовність: Кваліфікаційна робота." in text
    assert result.model_dump_json() == before
    assert render_report_html(result) == render_report_html(result)


@pytest.mark.parametrize("case", [f"bad_r{number:02}" for number in range(1, 11)])
def test_all_real_rule_outputs_retain_required_evidence(eom_fixtures, case):
    source = eom_fixtures[case]
    original = source.read_bytes()
    result = RuleEngine().check(
        load_document(source), load_ruleset(), document_type="laboratory_report"
    )
    tree = parsed(result)
    text = body_text(tree)
    assert result.summary.errors == 1
    for item in result.findings:
        assert item.quote in text and item.message in text
    assert len(tree.xpath('//*[@id="findings"]//article')) == 1
    assert "Знайдено 1 помилку" in tree.xpath("//aside")[0].text_content()
    assert source.read_bytes() == original


def test_report_after_fix_uses_remaining_counts_and_keeps_manual_review(eom_fixtures):
    source = eom_fixtures["bad_r02"]
    result = fix_document_bytes(
        source.read_bytes(),
        load_ruleset(),
        filename="generated.docx",
        document_type="laboratory_report",
    )
    before, after = parsed(result.before), parsed(result.after)
    assert "Знайдено 1 помилку" in before.xpath("//aside")[0].text_content()
    assert (
        "Знайдено 0 помилок, 0 можна виправити автоматично."
        in after.xpath("//aside")[0].text_content()
    )
    assert len(after.xpath('//*[@id="manual"]//details[contains(@class,"manual-group")]')) == 7
    assert "потрібен ручний перегляд" in body_text(after)


@pytest.mark.parametrize("rule_id", ["R08", "R09"])
@pytest.mark.parametrize(
    "kind,key,label",
    [
        ("literal", "method", "номер, набраний текстом"),
        ("ROMAN", "number_format", "римські числа"),
        ("ALPHABETIC", "number_format", "літерна нумерація"),
        ("ROMAN", "chapter_number_format", "римські числа"),
    ],
)
def test_actual_caption_numbering_errors_are_localized(
    eom_fixtures, tmp_path, rule_id, kind, key, label
):
    document, paragraph, _rule = example(eom_fixtures, rule_id)
    if kind == "literal":
        prefix = "Рис." if rule_id == "R08" else "Табл."
        paragraph.text = f"{prefix} 1.1 Згенерований підпис"
    elif key == "chapter_number_format":
        node = next(node for node in code_nodes(paragraph) if "STYLEREF" in node.text)
        node.text += " \\* " + kind
    else:
        change_code(paragraph, "ARABIC", kind)
    source = tmp_path / "generated.docx"
    document.save(source)
    result = RuleEngine().check(
        load_document(source), load_ruleset(), document_type="laboratory_report"
    )
    assert any(
        item.rule_id == rule_id and item.actual.get(key) == kind
        for item in result.findings
        if item.severity == "error"
    )
    tree = parsed(result)
    values = " ".join(node.text_content() for node in tree.xpath('//div[@class="values"]'))
    assert label in values and kind not in values


@pytest.mark.parametrize(
    "metadata,phrase",
    [
        ({"failed_rules": ("R03",)}, "Не вдалося виконати перевірки: R03"),
        ({"unavailable_rules": ("R03",)}, "Недоступні автоматичні перевірки: R03"),
        ({"ruleset_status": "draft"}, "Набір правил ще не погоджено"),
    ],
)
def test_incomplete_metadata_does_not_become_success_even_without_findings(metadata, phrase):
    text = body_text(parsed(report(**metadata)))
    assert phrase in text and "Перевірку не завершено" in text


def test_empty_report_and_offline_document_have_accessible_structure():
    tree = parsed(report())
    assert tree.get("lang") == "uk"
    assert tree.xpath('//meta[@charset="utf-8"]')
    assert tree.xpath('//meta[@name="viewport"]')
    assert tree.xpath('//meta[@http-equiv="Content-Security-Policy"]')
    assert "Автоматичних помилок і попереджень не знайдено." in body_text(tree)
    assert "У звіті немає ручних висновків." in body_text(tree)
    assert tree.xpath("//a")[0].get("href") == "#report"
    ids = tree.xpath("//*[@id]/@id")
    assert len(ids) == len(set(ids))
    assert all(anchor[1:] in ids for anchor in tree.xpath("//a/@href"))
    assert len(tree.xpath("//h1")) == 1
    assert not tree.xpath("//button|//input|//script|//link|//img")
