"""Conservative caption roles, object associations and effective typography."""

import math
import re

from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml.ns import qn

from oformleno.engine import Location
from oformleno.rules._body_text import finding, manual
from oformleno.rules._caption_fields import (
    CaptionUncertain,
    Field,
    chapter_context,
    fields,
    numbering,
    one,
    sequence_context,
    value,
)

_OPAQUE = {
    qn("w:" + tag)
    for tag in (
        "pict",
        "object",
        "sym",
        "txbxContent",
        "ins",
        "del",
        "moveFrom",
        "moveTo",
        "rPrChange",
        "pPrChange",
        "sectPrChange",
        "altChunk",
        "footnoteReference",
        "endnoteReference",
        "noBreakHyphen",
        "softHyphen",
    )
} | {"{http://schemas.openxmlformats.org/markup-compatibility/2006}AlternateContent"}


def _name(text):
    return " ".join(text.split()).casefold()


def parameters(rule, ruleset, kind):
    expected = rule.params
    keys = {
        "style",
        "label",
        "align",
        "font",
        "size_pt",
        "italic",
        "line_spacing",
        "position",
        "numbering",
    }
    if kind == "table":
        keys |= {"layout", "bold", "keep_with_next"}
    if set(expected) != keys:
        raise CaptionUncertain("Параметри правила підписів неповні або непідтримувані.")
    for name in ("style", "label", "font"):
        if not isinstance(expected[name], str) or not expected[name].strip():
            raise CaptionUncertain("Потрібні непорожні назви стилю, позначення та шрифту підпису.")
    for name in ("italic", "bold", "keep_with_next"):
        if name in expected and not isinstance(expected[name], bool):
            raise CaptionUncertain("Властивості підпису мають бути логічними значеннями.")
    for name in ("size_pt", "line_spacing"):
        number = expected[name]
        if (
            isinstance(number, bool)
            or not isinstance(number, (int, float))
            or not math.isfinite(number)
            or number <= 0
        ):
            raise CaptionUncertain("Розмір та інтервал підпису мають бути додатними числами.")
    if expected["align"] not in ("left", "center", "right", "justify") or expected[
        "position"
    ] not in ("above", "below"):
        raise CaptionUncertain("Вирівнювання або розташування підпису не підтримується.")
    if kind == "table" and expected["layout"] != "combined_number_and_title":
        raise CaptionUncertain("Інший макет підпису таблиці перевіряється вручну.")
    code = expected["numbering"]
    if not isinstance(code, dict) or set(code) != {
        "method",
        "format",
        "separator",
        "chapter_heading_level",
        "chapter_field",
        "sequence_field",
        "sequence_name",
        "reset_at_heading_level",
        "number_format",
    }:
        raise CaptionUncertain("Параметри нумерації підписів неповні або непідтримувані.")
    if any(
        code[key] != expected_value
        for key, expected_value in {
            "method": "automatic_fields",
            "format": "chapter.ordinal",
            "chapter_field": "STYLEREF",
            "sequence_field": "SEQ",
            "number_format": "arabic",
        }.items()
    ):
        raise CaptionUncertain("Спосіб нумерації підпису не підтримується.")
    for name in ("chapter_heading_level", "reset_at_heading_level"):
        if type(code[name]) is not int or not 1 <= code[name] <= 9:
            raise CaptionUncertain("Рівень розділу або перезапуску підписів не підтримується.")
    if code["chapter_heading_level"] != code["reset_at_heading_level"]:
        raise CaptionUncertain("Рівні розділу й перезапуску лічильника мають збігатися.")
    for name in ("separator", "sequence_name"):
        if not isinstance(code[name], str) or not code[name].strip():
            raise CaptionUncertain("Роздільник та ім'я лічильника підписів не задано.")
    for other in ruleset.rules:
        other_code = other.params.get("numbering")
        if (
            other.id in {"R08", "R09"}
            and other.id != rule.id
            and isinstance(other_code, dict)
            and _name(str(other_code.get("sequence_name", ""))) == _name(code["sequence_name"])
        ):
            raise CaptionUncertain("Рисунки й таблиці потребують окремих лічильників.")
    return expected


def _role(model, paragraph, expected, ruleset):
    text = "".join(run.text for run in model.runs(paragraph))
    hint = re.match(re.escape(expected["label"]) + r"(?:\s|\d|$)", text.strip(), re.IGNORECASE)
    codes = [node.text or "" for node in paragraph._p.iter(qn("w:instrText"))] + [
        node.get(qn("w:instr"), "") for node in paragraph._p.iter(qn("w:fldSimple"))
    ]
    if not text.strip() and not codes:
        return False
    hint = hint or any(
        expected["numbering"]["sequence_name"].casefold() in code.casefold()
        and re.match(r"\s*SEQ\b", code, re.IGNORECASE)
        for code in codes
    )
    chain = model.paragraph_style_chain(paragraph)
    if not chain.resolved:
        if hint:
            raise CaptionUncertain(chain.reason)
        return False
    names = [_name(value(style, "w:name") or "") for style in chain.value]
    target = _name(expected["style"])
    if target not in names:
        if hint:
            raise CaptionUncertain("Можливий підпис не має підтвердженої ролі стилю.")
        return False
    excluded = {"еом: основний", "body text", "title", "subtitle", "toc heading"}
    excluded |= {
        _name(other.params["style"])
        for other in ruleset.rules
        if isinstance(other.params.get("style"), str) and other.params["style"] != expected["style"]
    }
    for other in ruleset.rules:
        aliases = other.params.get("body_styles", [])
        if other.id in {"R03", "R04", "R05"} and isinstance(aliases, list):
            excluded.update(_name(name) for name in aliases if isinstance(name, str))
    if any(
        name in excluded or re.fullmatch(r"(?:heading|toc) [1-9]", name)
        for name in names[: names.index(target)]
    ):
        raise CaptionUncertain("Роль стилю підпису суперечить іншому елементу документа.")
    layers = model.paragraph_property_layers(paragraph)
    if not layers.resolved:
        raise CaptionUncertain(layers.reason)
    for props in layers.value:
        outline = value(props, "w:outlineLvl")
        if outline is not None:
            if outline != "9":
                raise CaptionUncertain("Структурний рівень суперечить ролі підпису.")
            break
    if any(node.tag in _OPAQUE | {qn("w:drawing")} for node in paragraph._p.iter()):
        raise CaptionUncertain("Об'єкти або невирішені зміни підпису потребують ручної перевірки.")
    if any(one(props, "w:framePr") is not None for props in layers.value):
        raise CaptionUncertain("Плаваюче розміщення підпису потребує перегляду макета.")
    for run in model.runs(paragraph):
        if run.text or run._r.find(qn("w:fldChar")) is not None:
            hidden = model.effective_hidden(run)
            if hidden.resolved and hidden.value:
                raise CaptionUncertain(
                    "Прихований або невизначений вміст підпису потребує ручної перевірки."
                )
    return True


def _blocks(parent):
    for node in parent:
        if node.tag in {qn("w:sdt"), qn("w:sdtContent"), qn("w:customXml")}:
            yield from _blocks(node)
        elif node.tag not in {
            qn("w:sdtPr"),
            qn("w:sdtEndPr"),
            qn("w:customXmlPr"),
            qn("w:bookmarkStart"),
            qn("w:bookmarkEnd"),
            qn("w:proofErr"),
        }:
            yield node


def _object(model, node, kind, paragraph_map):
    if kind == "table":
        if node.tag != qn("w:tbl"):
            return False
        if one(one(node, "w:tblPr"), "w:tblpPr") is not None or any(
            element.tag in _OPAQUE for element in node.iter()
        ):
            raise CaptionUncertain("Плаваюча таблиця або її зміни потребують ручного зіставлення.")
        return True
    if node.tag == qn("w:tbl") and any(
        element.tag in {qn("w:drawing"), qn("w:pict"), qn("w:object")} for element in node.iter()
    ):
        raise CaptionUncertain("Рисунок у таблиці потребує ручного зіставлення з підписом.")
    if node.tag != qn("w:p") or not any(
        element.tag in {qn("w:drawing"), qn("w:pict"), qn("w:object")} for element in node.iter()
    ):
        return False
    if any(element.tag in _OPAQUE or element.tag == qn("wp:anchor") for element in node.iter()):
        raise CaptionUncertain("Плаваючий або непідтримуваний рисунок потребує перегляду макета.")
    drawings, pictures = list(node.iter(qn("w:drawing"))), list(node.iter(qn("pic:pic")))
    if len(drawings) != 1 or len(pictures) != 1 or len(list(node.iter(qn("wp:inline")))) != 1:
        raise CaptionUncertain(
            "Зв'язок кількох або нестандартних рисунків із підписом неоднозначний."
        )
    paragraph = paragraph_map.get(node)
    if (
        paragraph is None
        or any(run.text.strip() for run in model.runs(paragraph))
        or any(
            element.tag
            in {qn("w:fldChar"), qn("w:fldSimple"), qn("w:br"), qn("w:cr"), qn("w:sectPr")}
            for element in node.iter()
        )
    ):
        raise CaptionUncertain("Рисунок має змішаний вміст або межу; зв'язок із підписом непевний.")
    layers = model.paragraph_property_layers(paragraph)
    if not layers.resolved or any(one(props, "w:framePr") is not None for props in layers.value):
        raise CaptionUncertain("Розміщення абзацу рисунка потребує ручної перевірки.")
    for run in model.runs(paragraph):
        if run._r.find(qn("w:drawing")) is not None:
            hidden = model.effective_hidden(run)
            if not hidden.resolved or hidden.value:
                raise CaptionUncertain("Прихований або невизначений рисунок потребує перегляду.")
    blips = list(pictures[0].iter(qn("a:blip")))
    if len(blips) != 1:
        raise CaptionUncertain("Джерело рисунка не визначено однозначно.")
    relation = model.document.part.rels.get(blips[0].get(qn("r:embed")))
    if (
        relation is None
        or relation.is_external
        or relation.reltype != RT.IMAGE
        or blips[0].get(qn("r:link")) is not None
    ):
        raise CaptionUncertain("Зв'язок рисунка з частиною зображення не підтверджено.")
    return True


def _formatting(model, paragraph, tokens, literals, expected):
    actual, target, reasons = {}, {}, set()

    def compare(key, resolution, desired):
        if not resolution.resolved:
            reasons.add(resolution.reason)
        elif resolution.value != desired:
            actual[key], target[key] = resolution.value, desired

    compare("align", model.effective_alignment(paragraph), expected["align"])
    spacing = model.effective_line_spacing(paragraph)
    if not spacing.resolved:
        reasons.add(spacing.reason)
    elif spacing.value.kind != "multiple" or spacing.value.value != expected["line_spacing"]:
        actual["line_spacing"], target["line_spacing"] = (
            {"kind": spacing.value.kind, "value": spacing.value.value},
            expected["line_spacing"],
        )
    if "keep_with_next" in expected:
        compare(
            "keep_with_next", model.effective_keep_with_next(paragraph), expected["keep_with_next"]
        )
    contexts = list(literals)
    for token in tokens:
        if isinstance(token, Field):
            # Known numeric output has an ASCII domain even if the cache is stale.
            contexts.extend((run, "0123456789") for run in token.runs)
            if not token.runs:
                reasons.add("Форматування відсутнього результату поля потребує ручної перевірки.")
    fonts, sizes = set(), set()
    for run, domain in contexts:
        if not domain:
            continue
        hidden = model.effective_hidden(run)
        if not hidden.resolved:
            reasons.add(hidden.reason)
        slots = model.font_slots(run, text=domain)
        if not slots.resolved:
            reasons.add(slots.reason)
        else:
            for slot in slots.value:
                font = model.effective_font(run, slot)
                if not font.resolved:
                    reasons.add(font.reason)
                elif _name(font.value) != _name(expected["font"]):
                    fonts.add(font.value)
        size = model.effective_font_size(
            run, complex_script=slots.value == ("cs",) if slots.resolved else None
        )
        if not size.resolved:
            reasons.add(size.reason)
        elif size.value != expected["size_pt"]:
            sizes.add(size.value)
        for name in ("bold", "italic"):
            if name in expected:
                compare(
                    name,
                    getattr(model, "effective_" + name)(
                        run, complex_script=slots.value == ("cs",) if slots.resolved else None
                    ),
                    expected[name],
                )
    if fonts:
        actual["font"], target["font"] = sorted(fonts), expected["font"]
    if sizes:
        actual["size_pt"], target["size_pt"] = sorted(sizes), expected["size_pt"]
    return actual, target, reasons


def check_captions(model, rule, ruleset, kind):
    try:
        expected = parameters(rule, ruleset, kind)
    except CaptionUncertain as error:
        yield manual(rule, Location(), str(error))
        return
    paragraphs = model.paragraphs
    paragraph_map = {paragraph._p: paragraph for paragraph in paragraphs}
    indexes = {paragraph._p: index for index, paragraph in enumerate(paragraphs, 1)}
    blocks = list(_blocks(model.document.element.body))
    positions = {node: index for index, node in enumerate(blocks)}
    objects, object_reasons, captions = set(), {}, []
    for node in blocks:
        try:
            markers = (
                {qn("w:tbl")}
                if kind == "table"
                else {qn("w:drawing"), qn("w:pict"), qn("w:object")}
            )
            if node.tag not in {qn("w:p"), qn("w:tbl"), qn("w:sectPr")} and any(
                element.tag in markers for element in node.iter()
            ):
                raise CaptionUncertain(
                    "Об'єкт у непідтримуваному блоці потребує ручного зіставлення."
                )
            if _object(model, node, kind, paragraph_map):
                objects.add(node)
        except CaptionUncertain as error:
            object_reasons[node] = str(error)
    for index, paragraph in enumerate(paragraphs, 1):
        text = "".join(run.text for run in model.runs(paragraph))
        location = Location(paragraph=index, excerpt=text[:50] or None)
        try:
            if _role(model, paragraph, expected, ruleset):
                captions.append((paragraph, location))
        except CaptionUncertain as error:
            yield manual(rule, location, str(error))
    offset = -1 if expected["position"] == "below" else 1
    used, links = set(), {}
    for paragraph, _location in captions:
        position = positions.get(paragraph._p)
        if position is not None and 0 <= position + offset < len(blocks):
            node = blocks[position + offset]
            if node in objects and node not in used:
                links[paragraph._p] = (node, expected["position"])
                used.add(node)
    for paragraph, location in captions:
        actual, target, reasons = {}, {}, set()
        tokens, literals, format_fields = [], [], []
        try:
            tokens, literals = fields(model, paragraph)
            # An alternative table layout is explicitly a manual case, including
            # an isolated title styled as the combined caption.
            if kind == "table" and (
                not any(isinstance(token, Field) for token in tokens)
                and not re.match(
                    re.escape(expected["label"]) + r"\s*\d",
                    "".join(token for token in tokens if isinstance(token, str)).strip(),
                    re.IGNORECASE,
                )
            ):
                raise CaptionUncertain(
                    "Альтернативний макет номера й назви таблиці перевіряється вручну."
                )
            wrong, desired, numeric_fields = numbering(tokens, expected)
            actual.update(wrong)
            target.update(desired)
            if numeric_fields:
                heading = chapter_context(
                    model,
                    paragraphs,
                    location.paragraph - 1,
                    expected["numbering"]["chapter_heading_level"],
                )
                sequence_context(
                    model, heading, paragraph._p, expected, {p._p for p, _loc in captions}
                )
                if not {"chapter_number", "chapter_heading_level"} & set(wrong):
                    format_fields = numeric_fields
        except CaptionUncertain as error:
            reasons.add(str(error))
        # Field results with unknown output domains are never treated as literal
        # text. Independently parsed literal fragments and paragraph properties
        # remain checkable even when numbering needs manual review.
        wrong, desired, uncertainties = _formatting(
            model, paragraph, format_fields, literals, expected
        )
        actual.update(wrong)
        target.update(desired)
        reasons.update(uncertainties)
        link = links.get(paragraph._p)
        if link is None:
            position = positions.get(paragraph._p)
            if position is not None and 0 <= position - offset < len(blocks):
                node = blocks[position - offset]
                if node in objects and node not in used:
                    link = (node, "above" if expected["position"] == "below" else "below")
                    used.add(node)
            if link is None:
                reasons.add(
                    "Не вдалося однозначно пов'язати підпис із сусіднім рисунком або таблицею."
                )
        if link is not None and link[1] != expected["position"]:
            actual["position"], target["position"] = link[1], expected["position"]
        if actual:
            yield finding(
                rule,
                location,
                actual,
                target,
                "Підпис не відповідає вимогам; "
                "фактичні й потрібні властивості наведено у висновку.",
            )
        if reasons:
            yield manual(rule, location, " ".join(sorted(reasons)))
    # Unmatched objects may be decorative images or layout tables; never invent
    # an absent required caption or silently declare their association checked.
    for node in blocks:
        if node in objects - used or node in object_reasons:
            location = Location(paragraph=indexes.get(node))
            yield manual(
                rule,
                location,
                object_reasons.get(
                    node, "Зв'язок об'єкта з підписом не підтверджено; уточніть його роль і підпис."
                ),
            )
