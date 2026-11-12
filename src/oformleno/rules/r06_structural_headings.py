"""R06: recognize structural titles and fix only reliable local formatting."""

import math
import re

from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

from oformleno.engine import Location
from oformleno.rules._body_text import TextParagraph, finding, manual, representable
from oformleno.rules._heading_fields import heading_field_uncertainties
from oformleno.rules._run_formatting import set_font_size, set_font_slots

_ALIGNMENTS = {
    "left": WD_ALIGN_PARAGRAPH.LEFT,
    "center": WD_ALIGN_PARAGRAPH.CENTER,
    "right": WD_ALIGN_PARAGRAPH.RIGHT,
    "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
}


def _key(text):
    # A final period identifies the same title; punctuation is never rewritten.
    return " ".join(text.strip().removesuffix(".").split()).casefold()


def _value(parent, tag):
    nodes = [] if parent is None else parent.findall(qn(tag))
    if len(nodes) > 1:
        raise ValueError("Властивості ролі заголовка неоднозначні.")
    return None if not nodes else nodes[0].get(qn("w:val"))


def _parameters(rule, ruleset):
    values = rule.params
    if set(values) != {"style", "uppercase", "align", "bold", "font", "size_pt", "line_spacing"}:
        raise ValueError("Параметри правила заголовків неповні або непідтримувані.")
    if not ruleset.structural_headings:
        raise ValueError("Перелік назв структурних частин не задано.")
    for name in ("style", "font"):
        if not isinstance(values[name], str) or not values[name].strip():
            raise ValueError("Потрібні непорожні назви стилю й шрифту заголовка.")
    for name in ("uppercase", "bold"):
        if not isinstance(values[name], bool):
            raise ValueError("Великі літери й напівжирний мають бути логічними параметрами.")
    if not isinstance(values["align"], str) or values["align"] not in _ALIGNMENTS:
        raise ValueError("Вирівнювання заголовка не підтримується.")
    for name in ("size_pt", "line_spacing"):
        value = values[name]
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value <= 0
        ):
            raise ValueError("Розмір та інтервал заголовка мають бути додатними числами.")
    return values


def _role(model, paragraph, rule, ruleset):
    chain = model.paragraph_style_chain(paragraph)
    if not chain.resolved:
        return chain.reason
    try:
        names = []
        outline = _value(paragraph._p.pPr, "w:outlineLvl")
        numbering = paragraph._p.find("./" + qn("w:pPr") + "/" + qn("w:numPr"))
        for style in chain.value:
            names.append(_key(_value(style, "w:name") or ""))
            properties = style.find(qn("w:pPr"))
            if outline is None:
                outline = _value(properties, "w:outlineLvl")
            if numbering is None and properties is not None:
                numbering = properties.find(qn("w:numPr"))
        if outline is not None and outline not in {str(value) for value in range(10)}:
            return "Структурний рівень заголовка не визначено."
        if numbering is not None and _value(numbering, "w:numId") != "0":
            return "Назва може бути нумерованим розділом; уточніть роль структурної частини."
        excluded = {
            _key(other.params["style"])
            for other in ruleset.rules
            if other.id in {"R08", "R09", "R10"} and isinstance(other.params.get("style"), str)
        }
        excluded |= {"еом: основний", "body text", "caption", "title", "subtitle"}
        for other in ruleset.rules:
            aliases = other.params.get("body_styles", [])
            if other.id in {"R03", "R04", "R05"} and isinstance(aliases, list):
                excluded.update(_key(name) for name in aliases if isinstance(name, str))
        recognized = {_key(rule.params["style"])}
        for name in names:
            if name in excluded or re.fullmatch(r"toc [1-9]", name):
                return "Назва структурної частини має суперечливу роль стилю."
            if name in recognized or re.fullmatch(r"heading [1-9]", name):
                return None
        if outline not in (None, "9"):
            return None
        return "Роль структурного заголовка не підтверджено стилем або рівнем структури."
    except ValueError as error:
        return str(error)


def heading_paragraphs(model, rule, ruleset):
    titles = {_key(title) for title in ruleset.structural_headings}
    field_uncertainties = heading_field_uncertainties(model)
    for index, paragraph in enumerate(model.paragraphs, 1):
        runs = model.runs(paragraph)
        text = "".join(run.text for run in runs)
        if _key(text) not in titles:
            continue
        yield TextParagraph(
            paragraph,
            Location(paragraph=index, excerpt=text[:50] or None),
            tuple(run for run in runs if run.text),
            _role(model, paragraph, rule, ruleset) or field_uncertainties.get(paragraph._p),
        )


def _inspect(model, item, expected):
    wrong, targets, reasons, plans = {}, {}, set(), []
    capable = True
    alignment = model.effective_alignment(item.paragraph)
    if not alignment.resolved:
        reasons.add(alignment.reason)
    elif alignment.value != expected["align"]:
        wrong["align"], targets["align"] = alignment.value, expected["align"]
        plans.append(("align", item.paragraph, expected["align"]))
    spacing = model.effective_line_spacing(item.paragraph)
    if not spacing.resolved:
        reasons.add(spacing.reason)
    elif spacing.value.kind != "multiple" or spacing.value.value != expected["line_spacing"]:
        wrong["line_spacing"] = {"kind": spacing.value.kind, "value": spacing.value.value}
        targets["line_spacing"] = expected["line_spacing"]
        can_fix = representable(expected["line_spacing"], 240)
        capable &= can_fix
        if can_fix:
            plans.append(("spacing", item.paragraph, expected["line_spacing"]))
    fonts, sizes = set(), set()
    for run in item.runs:
        slots = model.font_slots(run)
        if not slots.resolved:
            reasons.add(slots.reason)
        else:
            bad_slots = []
            for slot in slots.value:
                font = model.effective_font(run, slot)
                if not font.resolved:
                    reasons.add(font.reason)
                elif font.value.strip().casefold() != expected["font"].strip().casefold():
                    fonts.add(font.value)
                    bad_slots.append(slot)
            if bad_slots:
                plans.append(("font", run, bad_slots))
        size = model.effective_font_size(run)
        if not size.resolved:
            reasons.add(size.reason)
        elif size.value != expected["size_pt"]:
            sizes.add(size.value)
            can_fix = representable(expected["size_pt"], 2) and slots.resolved
            capable &= can_fix
            if can_fix:
                plans.append(("size", run, slots.value == ("cs",)))
        bold = model.effective_bold(run)
        if not bold.resolved:
            reasons.add(bold.reason)
        elif bold.value != expected["bold"]:
            wrong["bold"], targets["bold"] = bold.value, expected["bold"]
            capable &= slots.resolved
            if slots.resolved:
                plans.append(("bold", run, slots.value == ("cs",)))
        if not any(character.lower() != character.upper() for character in run.text):
            continue
        caps, small = model.effective_caps(run), model.effective_small_caps(run)
        if not caps.resolved or not small.resolved:
            reasons.update(value.reason for value in (caps, small) if not value.resolved)
        elif caps.value and small.value:
            reasons.add(
                "Великі та дрібні великі літери задані одночасно; вигляд потребує ручної перевірки."
            )
        elif caps.value != expected["uppercase"]:
            wrong["uppercase"], targets["uppercase"] = caps.value, expected["uppercase"]
            plans.append(("caps", run, small.value))
    if fonts:
        wrong["font"], targets["font"] = sorted(fonts), expected["font"]
    if sizes:
        wrong["size_pt"], targets["size_pt"] = sorted(sizes), expected["size_pt"]
    return wrong, targets, reasons, plans, capable


class StructuralHeadingChecker:
    def check(self, document, rule, ruleset):
        try:
            expected = _parameters(rule, ruleset)
        except ValueError as error:
            yield manual(rule, Location(), str(error))
            return
        for item in heading_paragraphs(document, rule, ruleset):
            if item.reason:
                yield manual(rule, item.location, item.reason)
                continue
            actual, target, reasons, _plans, capable = _inspect(document, item, expected)
            if actual:
                yield finding(
                    rule,
                    item.location,
                    actual,
                    target,
                    "Форматування структурного заголовка не відповідає вимогам; "
                    "фактичні й потрібні властивості наведено у висновку.",
                    fixable=capable,
                )
            if reasons:
                yield manual(rule, item.location, " ".join(sorted(reasons)))

    def fix(self, document, rule, ruleset):
        locations = {
            item.location.paragraph for item in self.check(document, rule, ruleset) if item.fixable
        }
        if not locations:
            return 0
        expected, plans = _parameters(rule, ruleset), []
        for item in heading_paragraphs(document, rule, ruleset):
            if not item.reason and item.location.paragraph in locations:
                plans.extend(_inspect(document, item, expected)[3])
        for action, element, extra in plans:
            if action == "align":
                element.paragraph_format.alignment = _ALIGNMENTS[extra]
            elif action == "spacing":
                element.paragraph_format.line_spacing = float(extra)
            elif action == "font":
                set_font_slots(element, extra, expected["font"])
            elif action == "size":
                set_font_size(element, extra, expected["size_pt"])
            elif action == "bold":
                properties = element._r.get_or_add_rPr()
                flag = properties.get_or_add_bCs() if extra else properties.get_or_add_b()
                flag.val = expected["bold"]
            elif action == "caps":
                element.font.all_caps = expected["uppercase"]
                if extra and expected["uppercase"]:
                    element.font.small_caps = False
        return len(plans)
