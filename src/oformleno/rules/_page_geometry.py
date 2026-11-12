"""Read-only helpers for R01/R02, without application or printer defaults."""

import math
from decimal import Decimal

from docx.oxml.ns import qn
from docx.shared import Mm, Twips

from oformleno.engine import Finding, Location


class GeometryUncertain(ValueError):
    """A fixed Ukrainian reason that never contains source XML or exception text."""


def parameters(rule, names, *, allow_zero=False):
    if set(rule.params) != set(names):
        raise GeometryUncertain("Параметри правила неповні або непідтримувані.")
    result = {}
    for name in names:
        value = rule.params[name]
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < 0
            or (value == 0 and not allow_zero)
        ):
            raise GeometryUncertain("Параметри правила мають непідтримувані значення.")
        result[name] = value
    return result


def sections(model):
    """Refuse unrepresented section boundaries rather than silently skipping them."""
    body = model.document.element.body
    final = body.findall(qn("w:sectPr"))
    known = list(model.sections)
    live = [
        node
        for node in body.iter(qn("w:sectPr"))
        if not any(
            ancestor.tag in {qn("w:sectPrChange"), qn("w:pPrChange")}
            for ancestor in node.iterancestors()
        )
    ]
    if (
        len(final) != 1
        or final[0] is not body[-1]
        or [section._sectPr for section in known] != live
    ):
        raise GeometryUncertain("Неможливо надійно визначити всі секції документа.")
    return known


def section_properties(section):
    element = section._sectPr
    if element.find(qn("w:sectPrChange")) is not None or any(
        ancestor.tag in {qn("w:ins"), qn("w:del"), qn("w:moveFrom"), qn("w:moveTo")}
        for ancestor in element.iterancestors()
    ):
        raise GeometryUncertain("Невирішені зміни властивостей секції потребують ручної перевірки.")
    parent = element.getparent()
    if parent.tag == qn("w:pPr") and parent.find(qn("w:pPrChange")) is not None:
        raise GeometryUncertain("Невирішені зміни межі секції потребують ручної перевірки.")
    return element


def property_element(parent, name):
    nodes = parent.findall(qn(name))
    if len(nodes) != 1:
        raise GeometryUncertain("Властивості сторінки відсутні або задані неоднозначно.")
    return nodes[0]


def measurement(section, attribute, *, positive=False, signed=False):
    try:
        value = getattr(section, attribute)
    except (ValueError, TypeError, OverflowError):
        raise GeometryUncertain("Розмір сторінки або поля має непідтримуване значення.") from None
    if value is None:
        raise GeometryUncertain(
            "Розмір сторінки або поля не задано явно; типове значення не вгадується."
        )
    if (positive and value <= 0) or (not signed and value < 0):
        raise GeometryUncertain("Розмір сторінки або поля має непідтримуване значення.")
    return value


def outside_tolerance(actual, expected_mm, tolerance_mm):
    # Compare EMU before rounding for display. Decimal preserves YAML's decimal
    # millimetres, including an inclusive tolerance boundary after DOCX twips.
    return abs(Decimal(int(actual)) - Decimal(str(expected_mm)) * 36000) > (
        Decimal(str(tolerance_mm)) * 36000
    )


def fixable_length(value_mm, tolerance_mm):
    """A saved DOCX must represent the target within the configured tolerance."""
    try:
        saved = Twips(Mm(value_mm).twips)
        return not outside_tolerance(saved, value_mm, tolerance_mm)
    except (ValueError, TypeError, OverflowError):
        return False


def finding(rule, section, actual, expected, message, *, manual=False, fixable=False):
    return Finding(
        rule_id=rule.id,
        severity="manual" if manual else rule.severity,
        location=Location(section=section),
        actual=actual,
        expected=expected,
        quote=rule.quote,
        fixable=fixable and rule.autofix and not manual,
        message=message,
    )


def manual(rule, section, message, *, expected=None):
    return finding(
        rule,
        section,
        None,
        rule.params if expected is None else expected,
        message + " Перевірте вручну.",
        manual=True,
    )


def enabled(parent, name):
    if parent is None:
        return False
    nodes = parent.findall(qn(name))
    if not nodes:
        return False
    if len(nodes) != 1:
        raise GeometryUncertain("Параметри макета задані неоднозначно.")
    value = nodes[0].get(qn("w:val"))
    if value in (None, "1", "true", "on"):
        return True
    if value in ("0", "false", "off"):
        return False
    raise GeometryUncertain("Параметри макета мають непідтримувані значення.")
