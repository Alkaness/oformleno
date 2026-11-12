"""Body-role selection and finding helpers shared by R03–R05.

Known semantic style names identify roles independently of typography. Unknown
names are not guessed from font, size or a departmental style prefix. Expected
formatting and the profile's excluded styles/headings still come from YAML.
"""

import math
import re
from dataclasses import dataclass

from docx.oxml.ns import qn

from oformleno.engine import Finding, Location

_BODY_NAMES = {"еом: основний", "body text"}
_NON_BODY_NAMES = {"caption", "title", "subtitle", "toc heading", "еом: програма"}


@dataclass(frozen=True)
class TextParagraph:
    paragraph: object
    location: Location
    runs: tuple
    reason: str | None = None


def _name(value):
    return " ".join(value.split()).casefold()


def _value(parent, tag):
    nodes = [] if parent is None else parent.findall(qn(tag))
    if len(nodes) > 1:
        raise ValueError("Роль абзацу задана неоднозначно.")
    return None if not nodes else nodes[0].get(qn("w:val"))


def _role(model, paragraph, text, rule, ruleset):
    chain = model.paragraph_style_chain(paragraph)
    if not chain.resolved:
        return "manual", chain.reason
    styles = chain.value
    excluded = {
        _name(rule.params["style"])
        for rule in ruleset.rules
        if rule.id not in {"R03", "R04", "R05"} and isinstance(rule.params.get("style"), str)
    }
    try:
        names = []
        outline = _value(paragraph._p.pPr, "w:outlineLvl")
        numbering = paragraph._p.find("./" + qn("w:pPr") + "/" + qn("w:numPr"))
        for style in styles:
            names.append(_name(_value(style, "w:name") or ""))
            if outline is None:
                outline = _value(style.find(qn("w:pPr")), "w:outlineLvl")
            if numbering is None:
                numbering = style.find("./" + qn("w:pPr") + "/" + qn("w:numPr"))
        if outline is not None and outline not in {str(index) for index in range(10)}:
            raise ValueError("Рівень структури абзацу неможливо визначити.")
        non_body = any(
            name in excluded | _NON_BODY_NAMES or re.fullmatch(r"(?:heading|toc) [1-9]", name)
            for name in names
        ) or outline not in (None, "9")
        body_names = {_name(name) for name in rule.params.get("body_styles", _BODY_NAMES)}
        body = any(name in body_names for name in names)
        if non_body:
            # A heading, caption or program style can inherit body typography
            # while retaining its own semantic role.
            first_body = next(
                (index for index, name in enumerate(names) if name in body_names), len(names)
            )
            first_excluded = next(
                (
                    index
                    for index, name in enumerate(names)
                    if name in excluded | _NON_BODY_NAMES
                    or re.fullmatch(r"(?:heading|toc) [1-9]", name)
                ),
                len(names),
            )
            if first_excluded < first_body:
                return "excluded", None
            if body:
                return "manual", "Стиль і структурна роль абзацу суперечать одне одному."
            return "excluded", None
        if numbering is not None:
            number_id = _value(numbering, "w:numId")
            if number_id != "0":
                return "manual", "Роль нумерованого елемента потребує ручної перевірки."
        if not body:
            return "manual", "Роль основного тексту не підтверджена відомим стилем."
        if _name(text.strip().removesuffix(".")) in {
            _name(name.strip().removesuffix(".")) for name in ruleset.structural_headings
        }:
            return "manual", "Назва структурної частини суперечить ролі основного тексту."
        for rule in ruleset.rules:
            label = rule.params.get("label") if rule.id in {"R08", "R09"} else None
            if isinstance(label, str) and re.match(
                re.escape(label) + r"\s*\d", text.strip(), re.IGNORECASE
            ):
                return "manual", "Можливий підпис має стиль основного тексту; уточніть роль."
        instructions = [node.text or "" for node in paragraph._p.iter(qn("w:instrText"))]
        instructions += [
            node.get(qn("w:instr"), "") for node in paragraph._p.iter(qn("w:fldSimple"))
        ]
        if any(
            re.match(r"\s*(?:TOC|SEQ|STYLEREF)\b", code, re.IGNORECASE) for code in instructions
        ):
            return "manual", "Поля структурного елемента суперечать ролі основного тексту."
        return "body", None
    except ValueError as error:
        return "manual", str(error)


def body_paragraphs(model, rule, ruleset):
    for index, paragraph in enumerate(model.paragraphs, 1):
        all_runs = model.runs(paragraph)
        text = "".join(run.text for run in all_runs)
        symbols = any(run._r.find(qn("w:sym")) is not None for run in all_runs)
        deleted = any(node.tag == qn("w:delText") for node in paragraph._p.iter())
        if not text.strip() and not symbols and not deleted:
            continue  # Empty/image-only paragraphs do not establish body text.
        role, reason = _role(model, paragraph, text, rule, ruleset)
        if role == "excluded":
            continue
        runs = tuple(run for run in all_runs if run.text or run._r.find(qn("w:sym")) is not None)
        yield TextParagraph(
            paragraph,
            Location(paragraph=index, excerpt=text[:50] or None),
            runs,
            reason,
        )


def parameter(rule, key):
    if (
        not {"role", key} <= set(rule.params) <= {"role", key, "body_styles"}
        or rule.params.get("role") != "body"
    ):
        raise ValueError("Параметри правила основного тексту неповні або непідтримувані.")
    if "body_styles" in rule.params:
        styles = rule.params["body_styles"]
        if (
            not isinstance(styles, list)
            or not styles
            or any(not isinstance(name, str) or not name.strip() for name in styles)
        ):
            raise ValueError("Потрібен непорожній перелік стилів основного тексту.")
    value = rule.params[key]
    if key == "font":
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Потрібна непорожня назва шрифту основного тексту.")
    elif (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value <= 0
    ):
        raise ValueError("Потрібна додатна числова величина форматування основного тексту.")
    return value


def representable(value, units):
    scaled = value * units
    return math.isfinite(scaled) and value == round(scaled) / units


def finding(rule, location, actual, expected, message, *, manual=False, fixable=False):
    return Finding(
        rule_id=rule.id,
        severity="manual" if manual else rule.severity,
        location=location,
        actual=actual,
        expected=expected,
        quote=rule.quote,
        fixable=fixable and rule.autofix and not manual,
        message=message,
    )


def manual(rule, location, reason):
    return finding(rule, location, None, rule.params, reason + " Перевірте вручну.", manual=True)
