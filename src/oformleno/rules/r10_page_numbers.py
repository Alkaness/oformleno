"""R10: stored page-number fields and selected header definitions, without layout."""

import math
from dataclasses import dataclass

from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml.ns import qn

from oformleno.model import DocumentModel
from oformleno.rules._page_geometry import (
    GeometryUncertain,
    enabled,
    finding,
    manual,
    section_properties,
    sections,
)

_LABELS = {"default": "звичайний", "even": "парний", "first": "першої сторінки секції"}
_ASCII_FORMATS = {"decimal", "upperRoman", "lowerRoman", "upperLetter", "lowerLetter"}
_OPAQUE = {
    qn("w:" + tag)
    for tag in (
        "tbl",
        "drawing",
        "pict",
        "object",
        "sym",
        "altChunk",
        "ins",
        "del",
        "moveFrom",
        "moveTo",
        "rPrChange",
        "pPrChange",
        "sectPrChange",
    )
} | {"{http://schemas.openxmlformats.org/markup-compatibility/2006}AlternateContent"}


@dataclass(frozen=True)
class _Field:
    instruction: str
    runs: tuple
    paragraph: object
    end: object


def _one(parent, name):
    nodes = parent.findall(qn(name))
    if len(nodes) > 1:
        raise GeometryUncertain("Властивості колонтитула або секції неоднозначні.")
    return nodes[0] if nodes else None


def _story(document, section_list, index, variant, *, footer=False):
    tag, relationship = (
        ("w:footerReference", RT.FOOTER) if footer else ("w:headerReference", RT.HEADER)
    )
    for previous in reversed(section_list[: index + 1]):
        properties = section_properties(previous)
        references = properties.findall(qn(tag))
        if any(node.get(qn("w:type")) not in _LABELS for node in references):
            raise GeometryUncertain("Тип посилання на колонтитул не визначено.")
        matches = [node for node in references if node.get(qn("w:type")) == variant]
        if len(matches) > 1:
            raise GeometryUncertain("Визначення колонтитула дублюється.")
        if not matches:
            continue
        identifier = matches[0].get(qn("r:id"))
        relation = document.part.rels.get(identifier)
        if relation is None or relation.reltype != relationship or relation.is_external:
            raise GeometryUncertain("Посилання на колонтитул відсутнє або непідтримуване.")
        part = relation.target_part
        if not hasattr(part, "element") or part.element.tag != qn("w:ftr" if footer else "w:hdr"):
            raise GeometryUncertain("Частина колонтитула має непідтримувану структуру.")
        return part
    return None  # A blank variant; never create a definition by reading it.


def _fields(model, paragraph):
    fields, outside, current = [], [], None
    runs = {run._r: run for run in model.runs(paragraph)}
    for node in paragraph._p.iter():
        if any(parent.tag == qn("w:fldSimple") for parent in node.iterancestors()):
            continue
        if node.tag == qn("w:fldSimple"):
            if current is not None or any(
                child.tag in {qn("w:fldSimple"), qn("w:fldChar")}
                for child in node.iterdescendants()
            ):
                raise GeometryUncertain("Вкладені поля колонтитула потребують ручної перевірки.")
            code = node.get(qn("w:instr"))
            if not code:
                raise GeometryUncertain("Інструкцію поля колонтитула не задано.")
            result_runs = tuple(
                run for element, run in runs.items() if node in element.iterancestors()
            )
            fields.append(_Field(code, result_runs, paragraph, node))
        elif node.tag == qn("w:fldChar"):
            kind = node.get(qn("w:fldCharType"))
            if kind == "begin" and current is None:
                current = {"code": [], "result": [], "separated": False}
            elif kind == "separate" and current is not None and not current["separated"]:
                current["separated"] = True
            elif kind == "end" and current is not None:
                fields.append(
                    _Field("".join(current["code"]), tuple(current["result"]), paragraph, node)
                )
                current = None
            else:
                raise GeometryUncertain("Межі складеного поля колонтитула неоднозначні.")
        elif node.tag == qn("w:instrText"):
            if current is None or current["separated"]:
                raise GeometryUncertain("Інструкція поля розташована неоднозначно.")
            current["code"].append(node.text or "")
        elif node.tag == qn("w:t"):
            owner = next(node.iterancestors(qn("w:r")), None)
            run = runs.get(owner)
            if run is None:
                raise GeometryUncertain("Результат поля має непідтримуваний контекст.")
            if current is not None:
                if not current["separated"]:
                    raise GeometryUncertain("Результат поля задано без роздільника.")
                if run not in current["result"]:
                    current["result"].append(run)
            elif run not in outside:
                outside.append(run)
    if current is not None:
        raise GeometryUncertain("Поле перетинає абзаци або не має завершення.")
    return fields, outside


def _page_domain(field, page_format):
    words = field.instruction.split()
    if not words or words[0].upper() != "PAGE":
        return False
    explicit = False
    index = 1
    while index < len(words):
        if words[index] != "\\*" or index + 1 == len(words):
            raise GeometryUncertain("Перемикачі поля PAGE потребують ручної перевірки.")
        value = words[index + 1].upper()
        if value in {"ARABIC", "ROMAN", "ALPHABETIC"}:
            explicit = True
        elif value != "MERGEFORMAT":
            raise GeometryUncertain("Форматування поля PAGE потребує ручної перевірки.")
        index += 2
    if not explicit and page_format not in _ASCII_FORMATS:
        raise GeometryUncertain("Символьний набір номера сторінки неможливо визначити.")
    return True


def _analyse(document, part, page_format):
    if part is None:
        return None, (), (), False
    if any(node.tag in _OPAQUE for node in part.element.iter()):
        raise GeometryUncertain(
            "Таблиці, об'єкти або зміни в колонтитулі потребують ручної перевірки."
        )
    model = DocumentModel(document, story_part=part)
    pages, outside, others = [], [], False
    for paragraph in model.paragraphs:
        properties = model.paragraph_property_layers(paragraph)
        if not properties.resolved:
            raise GeometryUncertain(properties.reason)
        if any(
            value is not None
            and any(value.find(qn(tag)) is not None for tag in ("w:framePr", "w:pBdr", "w:shd"))
            for value in properties.value
        ):
            raise GeometryUncertain(
                "Видимість або геометрія колонтитула потребує ручної перевірки."
            )
        fields, literals = _fields(model, paragraph)
        outside.extend(run for run in literals if run.text.strip())
        for field in fields:
            if _page_domain(field, page_format):
                pages.append(field)
            else:
                others = True
    return model, tuple(pages), tuple(outside), others


def _presence(analysis):
    model, pages, outside, others = analysis
    if model is None:
        return False
    visible = list(outside)
    for field in pages:
        if not field.runs:
            raise GeometryUncertain(
                "Видимість результату PAGE без форматованого фрагмента не визначено."
            )
        visible.extend(field.runs)
    for run in visible:
        hidden = model.effective_hidden(run)
        if not hidden.resolved or hidden.value:
            raise GeometryUncertain(
                "Видимість прихованого або невизначеного тексту колонтитула потребує перевірки."
            )
    if visible:
        return True
    if others:
        raise GeometryUncertain("Видимість інших полів колонтитула потребує ручної перевірки.")
    return False


def _position(model, field):
    paragraph = field.paragraph
    properties = model.paragraph_property_layers(paragraph)
    if not properties.resolved:
        raise GeometryUncertain(properties.reason)
    if any(node.tag == qn("w:tab") for node in paragraph._p.iter()):
        raise GeometryUncertain("Позиція номера з табуляціями потребує ручної перевірки.")
    seen = set()
    for element in properties.value:
        if element is None:
            continue
        indent = _one(element, "w:ind")
        if indent is not None:
            for attribute in ("right", "end", "rightChars", "endChars"):
                if attribute not in seen and indent.get(qn("w:" + attribute)) is not None:
                    seen.add(attribute)
                    try:
                        value = int(indent.get(qn("w:" + attribute)))
                    except (ValueError, TypeError):
                        raise GeometryUncertain("Відступ номера сторінки не визначено.") from None
                    if value != 0:
                        raise GeometryUncertain(
                            "Позиція номера з відступом потребує ручної перевірки."
                        )
    after = False
    trailing = False
    for node in paragraph._p.iter():
        if node is field.end:
            after = True
        elif after and field.end not in node.iterancestors():
            if node.tag == qn("w:t") and (node.text or "").strip():
                trailing = True
    if not field.runs or trailing:
        raise GeometryUncertain(
            "Розташування номера відносно іншого тексту потребує ручної перевірки."
        )
    alignment = model.effective_alignment(paragraph)
    if not alignment.resolved:
        raise GeometryUncertain(alignment.reason)
    return alignment.value


def _inspect(analysis, expected):
    model, pages, _outside, others = analysis
    actual, target, reasons = {}, {}, set()
    if not pages:
        if others:
            reasons.add("Інші поля не підтверджують наявність автоматичного номера PAGE.")
        else:
            actual["page_field"], target["page_field"] = False, "PAGE"
        return actual, target, reasons
    fonts, sizes = set(), set()
    for field in pages:
        try:
            position = _position(model, field)
            if position != "right":
                actual["align"], target["align"] = position, "right"
        except GeometryUncertain as error:
            reasons.add(str(error))
        if not field.runs:
            reasons.add("Форматування результату PAGE без фрагментів потребує ручної перевірки.")
        for run in field.runs:
            hidden = model.effective_hidden(run)
            if not hidden.resolved or hidden.value:
                reasons.add("Видимість номера сторінки потребує ручної перевірки.")
                continue
            # Instructions establish an ASCII numeric result. Cached values are
            # not evidence of the current page or its script selection.
            slots = model.font_slots(run, text="0")
            if not slots.resolved:
                reasons.add(slots.reason)
                continue
            for slot in slots.value:
                font = model.effective_font(run, slot)
                if not font.resolved:
                    reasons.add(font.reason)
                elif font.value.strip().casefold() != expected["font"].strip().casefold():
                    fonts.add(font.value)
            size = model.effective_font_size(run, complex_script=slots.value == ("cs",))
            if not size.resolved:
                reasons.add(size.reason)
            elif size.value != expected["size_pt"]:
                sizes.add(size.value)
    if fonts:
        actual["font"], target["font"] = sorted(fonts), expected["font"]
    if sizes:
        actual["size_pt"], target["size_pt"] = sorted(sizes), expected["size_pt"]
    return actual, target, reasons


def _page_properties(properties):
    value = _one(properties, "w:pgNumType")
    return (value.get(qn("w:fmt"), "decimal") if value is not None else "decimal", value)


class PageNumbersChecker:
    def check(self, document, rule, ruleset):
        expected = rule.params
        if (
            set(expected) != {"style", "position", "first_page_header", "font", "size_pt"}
            or expected.get("position") != "top-right"
            or expected.get("first_page_header") != "absent"
            or any(
                not isinstance(expected.get(name), str) or not expected[name].strip()
                for name in ("style", "font")
            )
            or isinstance(expected.get("size_pt"), bool)
            or not isinstance(expected.get("size_pt"), (int, float))
            or not math.isfinite(expected["size_pt"])
            or expected["size_pt"] <= 0
        ):
            yield manual(rule, None, "Параметри номера сторінки не підтримуються.")
            return
        main = document.document
        try:
            section_list = sections(document)
            try:
                settings = main.part.part_related_by(RT.SETTINGS).element
            except KeyError:
                settings = None
            odd_even = enabled(settings, "w:evenAndOddHeaders")
        except (GeometryUncertain, ValueError, AttributeError):
            yield manual(rule, None, "Неможливо надійно визначити секції або режими колонтитулів.")
            return
        for index, section in enumerate(section_list):
            number = index + 1
            try:
                properties = section_properties(section)
                title = enabled(properties, "w:titlePg")
                kind = _one(properties, "w:type")
                if (
                    index
                    and kind is not None
                    and kind.get(qn("w:val")) not in {"nextPage", "evenPage", "oddPage"}
                ):
                    raise GeometryUncertain(
                        "Колонтитули непосторінкового розриву секції потребують компонування."
                    )
                page_format, page_numbers = _page_properties(properties)
                variants = ["default", "even"] if odd_even else ["default"]
                selected = ["first"] if title else list(variants)
                if index == 0 and not title:
                    selected = ["default"]  # The implicit document start number is 1.
                if (
                    not title
                    and odd_even
                    and page_numbers is not None
                    and page_numbers.get(qn("w:start")) is not None
                ):
                    try:
                        start = int(page_numbers.get(qn("w:start")))
                        if start < 0:
                            raise ValueError
                    except ValueError:
                        raise GeometryUncertain("Початковий номер сторінки не визначено.") from None
                    selected = ["even" if start % 2 == 0 else "default"]
                analyses = {}
                for variant in dict.fromkeys(variants + selected):
                    try:
                        part = _story(main, section_list, index, variant)
                        analyses[variant] = _analyse(main, part, page_format)
                    except GeometryUncertain as error:
                        analyses[variant] = error
                if index == 0:
                    states = []
                    for variant in selected:
                        value = analyses[variant]
                        if isinstance(value, GeometryUncertain):
                            states.append(None)
                        else:
                            try:
                                states.append(_presence(value))
                            except GeometryUncertain:
                                states.append(None)
                    if all(value is True for value in states):
                        yield finding(
                            rule,
                            number,
                            {"first_page_header": "present"},
                            {"first_page_header": "absent"},
                            "На першій сторінці документа задано непорожній верхній колонтитул.",
                        )
                    elif not all(value is False for value in states):
                        yield manual(
                            rule,
                            number,
                            "Вигляд верхнього колонтитула першої сторінки "
                            "потребує ручної перевірки.",
                        )
                elif title:
                    variants = ["first", *variants]
                for variant in variants:
                    analysis = analyses[variant]
                    label = f"Верхній колонтитул секції {number} ({_LABELS[variant]})"
                    if isinstance(analysis, GeometryUncertain):
                        yield manual(rule, number, label + ": " + str(analysis))
                        continue
                    actual, target, reasons = _inspect(analysis, expected)
                    if actual.get("page_field") is False:
                        # A blank ordinary variant may be unused on a one-page
                        # section. A later section's selected first variant is used.
                        required = index > 0 and variant in selected and len(selected) == 1
                        if not required and not _presence(analysis):
                            footer = _story(main, section_list, index, variant, footer=True)
                            footer_analysis = _analyse(main, footer, page_format)
                            if footer_analysis[1] and _presence(footer_analysis):
                                actual, target = {"position": "bottom"}, {"position": "top-right"}
                            else:
                                actual, target = {}, {}
                                reasons.add(
                                    "Наявність сторінок з цим порожнім колонтитулом "
                                    "потребує ручної перевірки."
                                )
                    if actual:
                        yield finding(
                            rule,
                            number,
                            {"header": variant, **actual},
                            target,
                            label + ": властивості номера не відповідають вимогам.",
                        )
                    if reasons:
                        yield manual(rule, number, label + ": " + " ".join(sorted(reasons)))
            except GeometryUncertain as error:
                yield manual(rule, number, str(error))
