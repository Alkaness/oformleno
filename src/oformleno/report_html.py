"""Self-contained Ukrainian reports; all finding content is rendered as text."""

from collections import defaultdict
from html import escape

from pydantic import JsonValue

from oformleno.check_options import BODY_TEXT_MODE_LABELS
from oformleno.engine import Finding, Location, Report

_DOCUMENT_TYPES = {
    "laboratory_report": "Лабораторна робота",
    "qualification_thesis": "Кваліфікаційна робота",
    "other_printed_work": "Інша друкована робота",
}
_SOURCES = {
    "styles": "Стилі кафедри ЕОМ",
    "guide": "Методичні вказівки кафедри ЕОМ",
    "user_reference": "Зразок, обраний користувачем",
}
_LABELS = {
    "width_mm": "Ширина, мм",
    "height_mm": "Висота, мм",
    "left_mm": "Ліве поле, мм",
    "right_mm": "Праве поле, мм",
    "top_mm": "Верхнє поле, мм",
    "bottom_mm": "Нижнє поле, мм",
    "font": "Шрифт",
    "fonts": "Шрифти",
    "size_pt": "Розмір шрифту, пт",
    "line_spacing": "Міжрядковий інтервал",
    "align": "Вирівнювання",
    "bold": "Напівжирний",
    "italic": "Курсив",
    "uppercase": "Усі великі літери",
    "style": "Стиль Word",
    "role": "Роль тексту",
    "position": "Розташування",
    "start_on_new_page": "Починати з нової сторінки",
    "keep_with_next": "Не відривати від наступного",
    "label": "Позначення",
    "title": "Назва",
    "separator": "Роздільник",
    "layout": "Макет підпису",
    "numbering": "Нумерація",
    "method": "Спосіб нумерації",
    "format": "Формат номера",
    "chapter_number": "Автоматичний номер розділу",
    "chapter_heading_level": "Рівень заголовка розділу",
    "chapter_field": "Поле номера розділу",
    "sequence_field": "Поле порядкового номера",
    "sequence_name": "Лічильник",
    "reset_at_heading_level": "Перезапуск на рівні заголовка",
    "number_format": "Формат числа",
    "chapter_number_format": "Формат номера розділу",
    "sequence_number_format": "Формат порядкового номера",
    "header": "Варіант колонтитула",
    "first_page_header": "Колонтитул першої сторінки",
    "page_field": "Поле номера сторінки",
    "prefix": "Префікс стилю",
    "localized_equivalent_names": "Рівнозначні назви іншими мовами",
    "indent_mm": "Відступ, мм",
    "indent_type": "Тип відступу",
    "cells": "Комірки таблиці",
    "header_bold": "Напівжирний у шапці таблиці",
    "targets": "Елементи для перевірки",
    "min_full_pages": "Мінімальна кількість повних сторінок",
    "max_full_pages": "Максимальна кількість повних сторінок",
    "header_distance_mm": "Відстань верхнього колонтитула, мм",
    "footer_distance_mm": "Відстань нижнього колонтитула, мм",
    "measurement": "Відлік відстані",
}
_NUMBER_FORMATS = {
    "arabic": "арабські числа",
    "ARABIC": "арабські числа",
    "ROMAN": "римські числа",
    "ALPHABETIC": "літерна нумерація",
}
_ENUMS = {
    "align": {
        "left": "ліворуч",
        "right": "праворуч",
        "center": "по центру",
        "justify": "по ширині",
    },
    "position": {
        "above": "над об’єктом",
        "below": "під об’єктом",
        "bottom": "унизу",
        "top-right": "у верхньому колонтитулі праворуч",
    },
    "role": {"body": "основний текст"},
    "layout": {"combined_number_and_title": "номер і назва в одному підписі"},
    "method": {"automatic_fields": "автоматичні поля Word", "literal": "номер, набраний текстом"},
    "format": {"chapter.ordinal": "номер розділу.порядковий номер"},
    "number_format": _NUMBER_FORMATS,
    "chapter_number_format": _NUMBER_FORMATS,
    "sequence_number_format": _NUMBER_FORMATS,
    "header": {"default": "звичайний", "even": "парний", "first": "першої сторінки секції"},
    "first_page_header": {"present": "наявний", "absent": "відсутній"},
    "indent_type": {"first_line": "перший рядок"},
    "measurement": {"page_edge": "від краю сторінки"},
    "targets": {
        "headings": "заголовки",
        "figures": "рисунки",
        "tables": "таблиці",
        "bibliography": "джерела",
        "appendices": "додатки",
        "contents": "зміст",
    },
}
_CHECKLIST_IDS = {f"M{number:02}" for number in range(1, 9)}

_CSS = """
:root { color-scheme: light; --ink: #0f0f0f; --muted: #5f5f5f;
  --surface: #f6f6f3; --border: #dcded9; --error: #ab342b; --manual: #85500c; }
* { box-sizing: border-box; }
html { scroll-padding-top: 24px; }
body { margin: 0; color: var(--ink); background: #fff;
  font: 16px/1.6 "Funnel Sans", system-ui, sans-serif; overflow-wrap: anywhere; }
.wrap { width: min(100% - 160px, 1280px); margin-inline: auto; }
.brand { border-bottom: 1px solid var(--border); }
.brand .wrap { min-height: 72px; display: flex; align-items: center; font-size: 24px; }
main { padding-block: 48px 64px; }
h1, h2, h3 { font-family: "Funnel Display", "Funnel Sans", system-ui, sans-serif;
  font-weight: 400; line-height: 1.25; }
h1 { font-size: 40px; margin: 0 0 16px; letter-spacing: -.02em; }
h2 { font-size: 26px; margin: 0 0 24px; }
h3 { font-size: 20px; margin: 0; }
p { margin: 12px 0; }
.meta { color: var(--muted); font-size: 14px; }
.headline { margin-bottom: 40px; }
.columns { display: grid; grid-template-columns: minmax(0, 1fr) 352px;
  column-gap: 48px; align-items: start; }
.summary { grid-column: 2; grid-row: 1; padding: 24px; background: var(--surface);
  border-radius: 12px; }
.summary h2 { font-size: 24px; }
.summary-intro { font-size: 20px; line-height: 1.5; }
.summary .counts { margin: 16px 0; padding: 0; list-style: none; }
.summary .counts li { margin-block: 8px; }
.notice { color: var(--manual); }
.findings { grid-column: 1; grid-row: 1; min-width: 0; }
nav { display: flex; flex-wrap: wrap; gap: 8px 24px; margin-bottom: 24px; }
a { color: inherit; text-underline-offset: 4px; text-decoration-thickness: 1px; }
nav a, .summary a { display: inline-flex; align-items: center; min-height: 44px; }
a:hover { text-decoration-thickness: 2px; }
a:focus-visible { outline: 2px solid var(--ink); outline-offset: 4px; border-radius: 2px; }
.skip-link { position: absolute; left: 24px; top: -100px; background: #dafa9c;
  color: var(--ink); padding: 12px 16px; z-index: 10; }
.skip-link:focus { top: 8px; }
.report-section { margin-bottom: 48px; }
.rule-group { margin-bottom: 24px; border: 1px solid var(--border);
  border-radius: 12px; padding: 24px; }
.group-heading { display: flex; align-items: baseline; flex-wrap: wrap; gap: 8px 12px; }
.rule-id { font-size: 14px; color: var(--error); }
.manual-group .rule-id { color: var(--manual); }
.finding { padding-top: 16px; }
.finding + .finding { margin-top: 24px; border-top: 1px solid var(--border); }
.location { color: var(--muted); font-size: 14px; margin: 0 0 12px; }
.excerpt, blockquote { white-space: pre-wrap; }
.excerpt { margin-block: 12px; }
.values { background: var(--surface); border-radius: 8px; padding: 16px; margin-block: 16px; }
.value-label { font-weight: 500; margin: 0 0 8px; }
.value-label:not(:first-child) { margin-top: 16px; }
dl { margin: 0; }
.property { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.3fr);
  gap: 8px 16px; padding-block: 4px; }
dt { color: var(--muted); }
dd { margin: 0; min-width: 0; }
.value-list { margin: 0; padding-left: 20px; }
blockquote { margin: 16px 0 8px; font-size: 16px; }
.source { color: var(--muted); font-size: 14px; }
.provenance { margin-top: 16px; }
.badge { display: inline-block; background: var(--surface); border-radius: 4px;
  padding: 4px 8px; margin-top: 12px; font-size: 14px; }
.badge.manual { background: #fff4df; color: var(--manual); }
.badge.error { background: #fff2ef; color: var(--error); }
.coverage { border-top: 1px solid var(--border); padding-top: 24px; }
@media (max-width: 1199px) { .wrap { width: calc(100% - 96px); }
  .columns { grid-template-columns: minmax(0, 1fr) 288px; column-gap: 32px; } }
@media (max-width: 1023px) { .columns { display: flex; flex-direction: column; gap: 32px; }
  .summary, .findings { width: 100%; } }
@media (max-width: 639px) { .wrap { width: calc(100% - 48px); }
  .brand .wrap { min-height: 64px; } main { padding-block: 32px 48px; }
  h1 { font-size: 32px; } h2 { font-size: 24px; }
  .headline { margin-bottom: 24px; } .summary, .rule-group { padding: 20px; }
  .property { display: block; } dd { margin-top: 4px; } }
@media print { .wrap { width: 100%; } main { padding: 24px 0; }
  .columns { display: block; } .summary { margin-bottom: 24px; }
  nav, .skip-link { display: none; } .finding { break-inside: avoid; }
  .rule-group { border-radius: 0; } }
"""


def _text(value: str) -> str:
    return escape(value, quote=True)


def _label(key: str) -> str:
    return _LABELS.get(key, key)


def _value(value: JsonValue, key: str = "") -> str:
    if value is None:
        return "Не визначено"
    if isinstance(value, bool):
        return "Так" if value else "Ні"
    if isinstance(value, (int, float)):
        number = str(value).replace(".", ",")
        return f"{number} рядка" if key == "line_spacing" else number
    if isinstance(value, str):
        return _text(_ENUMS.get(key, {}).get(value, value)) or "Порожній рядок"
    if isinstance(value, list):
        if not value:
            return "Немає значень"
        return (
            '<ul class="value-list">'
            + "".join(f"<li>{_value(item, key)}</li>" for item in value)
            + "</ul>"
        )
    if set(value) == {"kind", "value"}:
        kind, number = value["kind"], value["value"]
        if kind in ("multiple", "exact", "at_least"):
            label = {"multiple": "кратний", "exact": "точно", "at_least": "щонайменше"}[kind]
            unit = "рядка" if kind == "multiple" else "пт"
            return f"{label} {_value(number)} {unit}"
    if not value:
        return "Немає значень"
    return (
        "<dl>"
        + "".join(
            f'<div class="property"><dt>{_text(_label(name))}</dt>'
            f"<dd>{_value(item, name)}</dd></div>"
            for name, item in value.items()
        )
        + "</dl>"
    )


def _location(location: Location) -> str:
    parts = [
        f"{label} {number}"
        for label, number in (
            ("Секція", location.section),
            ("Абзац", location.paragraph),
            ("Сторінка", location.page),
        )
        if number is not None
    ]
    return " · ".join(parts) or "Документ загалом"


def _evidence(finding: Finding) -> str:
    source = _SOURCES.get(finding.source_id, finding.source_id) if finding.source_id else None
    labels = [part for part in (source, finding.source_location) if part]
    result = f"<blockquote>{_text(finding.quote)}</blockquote>"
    if labels:
        result += f'<p class="source">Джерело: {_text(" · ".join(labels))}</p>'
    if finding.supporting_quote:
        result += '<p class="source">Додаткова цитата з джерела:</p>'
        result += f"<blockquote>{_text(finding.supporting_quote)}</blockquote>"
    if finding.parameter_sources:
        result += '<div class="provenance"><p>Походження параметрів:</p><ul>'
        for parameter, identifier in finding.parameter_sources.items():
            name = _SOURCES.get(identifier, identifier)
            note = finding.source_notes.get(identifier)
            result += f"<li>{_text(_label(parameter))}: {_text(name)}."
            if note:
                result += " " + _text(note)
            result += "</li>"
        result += "</ul></div>"
    return result


def _finding(finding: Finding) -> str:
    severity = {"error": "Помилка", "warning": "Попередження", "manual": "Перевірте вручну"}[
        finding.severity
    ]
    result = f'<div class="finding"><p class="location">{_location(finding.location)}</p>'
    if finding.location.excerpt:
        result += f'<p class="excerpt">{_text(finding.location.excerpt)}</p>'
    result += f"<p>{_text(finding.message)}</p>"
    if finding.applies_to:
        types = ", ".join(_DOCUMENT_TYPES[item] for item in finding.applies_to)
        result += f'<p class="meta">Застосовність: {types}.</p>'
    if (
        finding.severity != "manual"
        or finding.actual is not None
        or finding.expected not in (None, {})
    ):
        result += '<div class="values">'
        if finding.severity != "manual" or finding.actual is not None:
            result += f'<p class="value-label">Зараз</p>{_value(finding.actual)}'
        result += f'<p class="value-label">Потрібно</p>{_value(finding.expected)}</div>'
    result += _evidence(finding)
    result += f'<span class="badge {finding.severity}">{severity}</span> '
    if finding.fixable:
        result += '<span class="badge">Можна виправити автоматично</span>'
    elif finding.severity != "manual":
        result += '<span class="badge">Автовиправлення недоступне</span>'
    return result + "</div>"


def _groups(findings: list[Finding], *, manual: bool = False) -> str:
    groups = defaultdict(list)
    for finding in findings:
        groups[finding.rule_id].append(finding)
    result = ""
    for rule_id, items in groups.items():
        name = items[0].rule_name or "Правило без назви"
        kind = " manual-group" if manual else ""
        result += f'<article class="rule-group{kind}"><div class="group-heading">'
        result += f'<span class="rule-id">{_text(rule_id)}</span><h3>{_text(name)}</h3></div>'
        result += f'<p class="meta">Кількість висновків: {len(items)}</p>'
        result += "".join(_finding(item) for item in items) + "</article>"
    return result


def render_report_html(report: Report) -> str:
    """Return a complete offline HTML document without writing or logging it.

    The report is the only source of counts, applicability, evidence and values.
    Excerpts belong in the requested report, never in diagnostics or metadata.
    """
    summary = report.summary
    findings = [item for item in report.findings if item.severity != "manual"]
    checklist = [
        item
        for item in report.findings
        if item.severity == "manual" and item.rule_id in _CHECKLIST_IDS
    ]
    uncertainties = [
        item
        for item in report.findings
        if item.severity == "manual" and item.rule_id not in _CHECKLIST_IDS
    ]
    body = '<header class="brand"><div class="wrap">Оформлено</div></header>'
    body += '<main id="report" class="wrap" tabindex="-1"><div class="headline">'
    body += "<h1>Звіт про оформлення</h1>"
    body += f'<p class="meta">{_text(report.ruleset_title)}</p>'
    document_type = _DOCUMENT_TYPES.get(report.document_type, "Тип роботи не вказано")
    body += f'<p class="meta">{document_type}</p>'
    body += f'<p class="meta">Режим: {_text(BODY_TEXT_MODE_LABELS[report.body_text_mode])}.</p>'
    if report.body_text_mode == "ordinary":
        body += '<p class="meta">Звичайні абзаци перевірено як основний текст за обраним режимом. '
        body += "Стилі заголовків, підписів, списки й невизначені елементи мають окремі вимоги.</p>"
    body += '</div><div class="columns">'
    body += '<aside class="summary" aria-labelledby="summary-title">'
    body += '<h2 id="summary-title">Підсумок перевірки</h2>'
    error_word = "помилок"
    if summary.errors % 10 == 1 and summary.errors % 100 != 11:
        error_word = "помилку"
    elif 2 <= summary.errors % 10 <= 4 and not 12 <= summary.errors % 100 <= 14:
        error_word = "помилки"
    body += f'<p class="summary-intro">Знайдено {summary.errors} {error_word}, '
    body += f"{summary.fixable} можна виправити автоматично.</p>"
    body += f'<ul class="counts"><li>Попередження: {summary.warnings}</li>'
    body += f'<li class="notice">Перевірте вручну: {summary.manual}</li></ul>'
    body += "<p>Звіт охоплює перевірку форматування. Повний нормоконтроль потребує "
    body += "окремого перегляду.</p>"
    if summary.manual or summary.status == "manual_required":
        body += '<p class="notice">Перевірку не завершено: потрібен ручний перегляд.</p>'
    if summary.manual:
        body += '<a href="#manual">Переглянути ручні перевірки</a>'
    body += '</aside><div class="findings">'
    body += '<nav aria-label="Розділи звіту"><a href="#findings">Помилки та попередження</a>'
    body += '<a href="#manual">Ручні перевірки</a></nav>'
    body += '<section id="findings" class="report-section" aria-labelledby="findings-title">'
    body += '<h2 id="findings-title">Помилки та попередження</h2>'
    if findings:
        body += _groups(findings)
    else:
        body += "<p>Автоматичних помилок і попереджень не знайдено.</p>"
    body += '</section><section id="manual" class="report-section" aria-labelledby="manual-title">'
    body += f'<h2 id="manual-title">Ручні перевірки · {summary.manual}</h2>'
    body += "<p>Ручні висновки не зараховуються як знайдені помилки й не виправляються "
    body += "автоматично.</p>"
    body += f"<p>Пункти переліку ЕОМ: {len(checklist)}. "
    body += f"Інші ручні висновки: {len(uncertainties)}.</p>"
    if checklist:
        body += _groups(checklist, manual=True)
    if uncertainties:
        body += _groups(uncertainties, manual=True)
    if not checklist and not uncertainties:
        body += "<p>У звіті немає ручних висновків.</p>"
    body += '</section><section class="coverage" aria-labelledby="coverage-title">'
    body += '<h2 id="coverage-title">Охоплення перевірки</h2>'
    for label, rules in (
        ("Виконані автоматичні перевірки", report.checked_rules),
        ("Недоступні автоматичні перевірки", report.unavailable_rules),
        ("Не вдалося виконати перевірки", report.failed_rules),
        ("Не застосовуються до цього типу роботи", report.not_applicable),
    ):
        if rules:
            body += f"<p>{label}: {_text(', '.join(rules))}.</p>"
    if report.ruleset_status == "draft":
        body += '<p class="notice">Набір правил ще не погоджено.</p>'
    body += "</section></div></div></main>"
    return (
        '<!doctype html><html lang="uk" data-type="software"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="referrer" content="no-referrer"><meta name="robots" content="noindex">'
        '<meta http-equiv="Content-Security-Policy" content="default-src &#x27;none&#x27;; '
        "style-src &#x27;unsafe-inline&#x27;; base-uri &#x27;none&#x27;; "
        'form-action &#x27;none&#x27;">'
        '<meta name="page-type" content="software"><meta name="site-kind" content="software">'
        "<title>Оформлено · Звіт про оформлення</title>"
        '<meta name="description" content="Результати перевірки форматування документа '
        'з цитатами та ручними перевірками.">'
        f"<style>{_CSS}</style></head><body>"
        '<a class="skip-link" href="#report">Перейти до звіту</a>'
        f"{body}</body></html>"
    )
