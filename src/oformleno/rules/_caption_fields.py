"""Read caption fields in XML order; cached text never establishes a number."""

import re
from dataclasses import dataclass

from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph


class CaptionUncertain(ValueError):
    pass


@dataclass(frozen=True)
class Field:
    instruction: str
    runs: tuple
    locked: bool = False


def one(parent, name):
    nodes = [] if parent is None else parent.findall(qn(name))
    if len(nodes) > 1:
        raise CaptionUncertain("Властивості підпису або нумерації неоднозначні.")
    return nodes[0] if nodes else None


def value(parent, name):
    node = one(parent, name)
    return None if node is None else node.get(qn("w:val"))


def enabled(node, attribute="w:val"):
    raw = node.get(qn(attribute))
    if raw not in (None, "true", "1", "on", "false", "0", "off"):
        raise CaptionUncertain("Логічну властивість підпису неможливо визначити.")
    return raw not in ("false", "0", "off")


def fields(model, paragraph):
    """Return literal text and Field tokens, plus literal runs, in document order."""
    tokens, literals, current = [], [], None
    runs = {run._r: run for run in model.runs(paragraph)}
    for node in paragraph._p.iter():
        if any(parent.tag == qn("w:fldSimple") for parent in node.iterancestors()):
            continue
        if node.tag == qn("w:fldSimple"):
            if current is not None or any(
                child.tag in {qn("w:fldSimple"), qn("w:fldChar"), qn("w:instrText")}
                for child in node.iterdescendants()
            ):
                raise CaptionUncertain("Вкладені поля підпису потребують ручної перевірки.")
            code = node.get(qn("w:instr"))
            if not code:
                raise CaptionUncertain("Інструкцію поля підпису не задано.")
            result = tuple(run for element, run in runs.items() if node in element.iterancestors())
            tokens.append(
                Field(
                    code,
                    result,
                    enabled(node, "w:fldLock") if qn("w:fldLock") in node.attrib else False,
                )
            )
        elif node.tag == qn("w:fldChar"):
            kind = node.get(qn("w:fldCharType"))
            if kind == "begin" and current is None:
                current = {
                    "code": [],
                    "runs": [],
                    "separated": False,
                    "locked": enabled(node, "w:fldLock")
                    if qn("w:fldLock") in node.attrib
                    else False,
                }
            elif kind == "separate" and current is not None and not current["separated"]:
                current["separated"] = True
            elif kind == "end" and current is not None:
                tokens.append(
                    Field("".join(current["code"]), tuple(current["runs"]), current["locked"])
                )
                current = None
            else:
                raise CaptionUncertain("Межі поля підпису неоднозначні або вкладені.")
        elif node.tag == qn("w:instrText"):
            if current is None or current["separated"]:
                raise CaptionUncertain("Інструкція поля підпису розташована неоднозначно.")
            current["code"].append(node.text or "")
        elif node.tag in {qn("w:t"), qn("w:tab"), qn("w:br"), qn("w:cr")}:
            owner = next(node.iterancestors(qn("w:r")), None)
            run = runs.get(owner)
            if run is None:
                raise CaptionUncertain("Вміст підпису має непідтримуваний контекст.")
            if node.tag != qn("w:t"):
                raise CaptionUncertain("Табуляції або розриви підпису потребують перегляду макета.")
            if current is not None:
                if not current["separated"]:
                    raise CaptionUncertain("Результат поля задано без роздільника.")
                if run not in current["runs"]:
                    current["runs"].append(run)
            else:
                if tokens and isinstance(tokens[-1], str):
                    tokens[-1] += node.text or ""
                else:
                    tokens.append(node.text or "")
                literals.append((run, node.text or ""))
    if current is not None:
        raise CaptionUncertain("Поле підпису не завершене або перетинає абзаци.")
    return tokens, literals


def instruction(field):
    if field.locked:
        raise CaptionUncertain("Заблоковане поле потребує перевірки оновлення номера.")
    # Word field quoting, without interpreting backslashes as shell escapes.
    words = re.findall(r'"[^"\r\n]*"|[^\s"]+', field.instruction)
    if " ".join(words).replace(" ", "") != re.sub(r"\s", "", field.instruction):
        raise CaptionUncertain("Лапки в інструкції поля підпису незавершені.")
    words = [word[1:-1] if word.startswith('"') else word for word in words]
    if len(words) < 2:
        raise CaptionUncertain("Інструкція поля підпису неповна.")
    switches, index = {}, 2
    arity = {
        "\\*": 1,
        "\\s": int(words[0].upper() == "SEQ"),
        "\\r": 1,
        "\\n": 0,
        "\\c": 0,
        "\\h": 0,
    }
    while index < len(words):
        key = words[index].lower()
        if key not in arity or (key in switches and key != "\\*"):
            raise CaptionUncertain("Перемикач поля підпису невідомий або повторюється.")
        count = arity[key]
        # Multiple formatting switches are valid (ARABIC, MERGEFORMAT).
        if key == "\\*":
            if index + 1 >= len(words):
                raise CaptionUncertain("Формат поля підпису не задано.")
            formatting = switches.setdefault(key, [])
            formatting.append(words[index + 1].upper())
            index += 2
            continue
        if index + count >= len(words) or (count and words[index + 1].startswith("\\")):
            raise CaptionUncertain("Аргумент перемикача поля підпису не задано.")
        switches[key] = words[index + 1] if count else True
        index += count + 1
    return words[0].upper(), words[1], switches


def numbering(tokens, expected):
    """Known mismatches are errors; unsupported field structures stay manual."""
    code = expected["numbering"]
    items = [token for token in tokens if isinstance(token, Field)]
    if not items:
        return {"method": "literal"}, {"method": code["method"]}, ()
    if len(items) != 2:
        raise CaptionUncertain("Підпис не має однозначної пари полів розділу й лічильника.")
    parsed = [instruction(item) for item in items]
    if [item[0] for item in parsed] != [code["chapter_field"], code["sequence_field"]]:
        raise CaptionUncertain("Типи або порядок полів підпису потребують ручної перевірки.")
    first, second = [index for index, token in enumerate(tokens) if isinstance(token, Field)]
    prefix = "".join(tokens[:first])
    separator = "".join(tokens[first + 1 : second])
    title = "".join(tokens[second + 1 :])
    wrong, target = {}, {}
    if prefix.strip() != expected["label"]:
        wrong["label"], target["label"] = prefix.strip(), expected["label"]
    if separator != code["separator"]:
        wrong["separator"], target["separator"] = separator, code["separator"]
    if not title.strip():
        wrong["title"], target["title"] = False, True
    chapter, sequence = parsed
    level = str(code["chapter_heading_level"])
    if chapter[1] != level:
        # Named styles may be valid equivalents; do not guess their mapping.
        if not chapter[1].isdigit():
            raise CaptionUncertain("Іменований стиль поля розділу потребує ручного зіставлення.")
        wrong["chapter_heading_level"], target["chapter_heading_level"] = (
            chapter[1],
            code["chapter_heading_level"],
        )
    if set(chapter[2]) - {"\\s", "\\n", "\\*"} or ("\\s" in chapter[2] and "\\n" in chapter[2]):
        raise CaptionUncertain("Спосіб отримання номера розділу потребує ручної перевірки.")
    if not ({"\\s", "\\n"} & set(chapter[2])):
        wrong["chapter_number"], target["chapter_number"] = False, True
    if sequence[1].casefold() != code["sequence_name"].casefold():
        wrong["sequence_name"], target["sequence_name"] = sequence[1], code["sequence_name"]
    switches = sequence[2]
    if "\\r" in switches or "\\c" in switches or "\\h" in switches:
        raise CaptionUncertain(
            "Явний перезапуск, повтор або приховування SEQ потребує ручної перевірки."
        )
    reset = switches.get("\\s")
    if reset != str(code["reset_at_heading_level"]):
        wrong["reset_at_heading_level"], target["reset_at_heading_level"] = (
            reset,
            code["reset_at_heading_level"],
        )
    for position, item in enumerate(parsed):
        formats = [name for name in item[2].get("\\*", []) if name != "MERGEFORMAT"]
        if len(formats) > 1:
            raise CaptionUncertain("Числовий формат поля підпису задано неоднозначно.")
        if formats and formats != ["ARABIC"]:
            if formats[0] not in {"ROMAN", "ALPHABETIC"}:
                raise CaptionUncertain("Числовий формат поля підпису не підтримується.")
            key = "chapter_number_format" if position == 0 else "number_format"
            wrong[key], target[key] = formats[0], code["number_format"]
    return wrong, target, tuple(items)


def chapter_context(model, paragraphs, index, level):
    """Prove a preceding built-in heading and a simple decimal numbering definition.

    This verifies authored configuration, never cached results or rendered values.
    Complex numbering/forward style lookup remains M04/manual.
    """
    for paragraph in reversed(paragraphs[:index]):
        chain = model.paragraph_style_chain(paragraph)
        if not chain.resolved:
            raise CaptionUncertain("Попередні стилі не дають надійно визначити розділ підпису.")
        names = [(value(style, "w:name") or "").casefold() for style in chain.value]
        if not names:
            raise CaptionUncertain("Стиль попереднього елемента не дає визначити розділ.")
        layers = model.paragraph_property_layers(paragraph)
        if not layers.resolved:
            # Numbering fallthrough is expected for chapter paragraphs; styles
            # remain available separately for reading numPr without formatting.
            properties = [paragraph._p.pPr] + [one(style, "w:pPr") for style in chain.value]
        else:
            properties = layers.value
        outline = next(
            (value(p, "w:outlineLvl") for p in properties if value(p, "w:outlineLvl") is not None),
            None,
        )
        if names[0] != f"heading {level}":
            if f"heading {level}" in names or outline == str(level - 1):
                raise CaptionUncertain(
                    "Похідний або нестандартний заголовок потребує зіставлення STYLEREF."
                )
            continue
        if outline not in (None, str(level - 1)):
            raise CaptionUncertain("Рівень заголовка суперечить полю розділу.")
        if any(
            ancestor.tag
            not in {
                qn("w:body"),
                qn("w:document"),
                qn("w:sdt"),
                qn("w:sdtContent"),
                qn("w:customXml"),
            }
            for ancestor in paragraph._p.iterancestors()
        ) or any(
            element.tag in {qn("w:fldChar"), qn("w:fldSimple"), qn("w:drawing")}
            for element in paragraph._p.iter()
        ):
            raise CaptionUncertain("Роль або контекст заголовка розділу потребує ручної перевірки.")
        number = None
        for props in properties:
            number = one(props, "w:numPr")
            if number is not None:
                break
        identifier, depth = value(number, "w:numId"), value(number, "w:ilvl")
        if identifier in (None, "0") or depth not in (None, str(level - 1)):
            raise CaptionUncertain("Автоматичний номер розділу не підтверджено.")
        try:
            root = model.document.part.part_related_by(RT.NUMBERING).element
        except (KeyError, ValueError, AttributeError) as error:
            raise CaptionUncertain("Визначення нумерації розділу недоступне.") from error
        numbers = [n for n in root.findall(qn("w:num")) if n.get(qn("w:numId")) == identifier]
        if len(numbers) != 1 or numbers[0].find(qn("w:lvlOverride")) is not None:
            raise CaptionUncertain("Номер або перевизначення списку розділів неоднозначні.")
        abstract_id = value(numbers[0], "w:abstractNumId")
        definitions = [
            n
            for n in root.findall(qn("w:abstractNum"))
            if n.get(qn("w:abstractNumId")) == abstract_id
        ]
        if len(definitions) != 1:
            raise CaptionUncertain("Визначення списку розділів неоднозначне.")
        definition = definitions[0]
        if any(one(definition, tag) is not None for tag in ("w:numStyleLink", "w:styleLink")):
            raise CaptionUncertain("Зв'язок стилів нумерації розділу потребує ручної перевірки.")
        levels = [
            n for n in definition.findall(qn("w:lvl")) if n.get(qn("w:ilvl")) == str(level - 1)
        ]
        if len(levels) != 1:
            raise CaptionUncertain("Рівень списку розділів не визначено.")
        current = levels[0]
        if value(current, "w:numFmt") != "decimal" or value(current, "w:lvlText") != f"%{level}":
            raise CaptionUncertain("Числовий вигляд розділу потребує ручної перевірки.")
        return paragraph._p
    raise CaptionUncertain("Попередній автоматично нумерований розділ не визначено.")


def sequence_context(model, heading, caption, expected, known_captions):
    """Do not certify a local ordinal when other fields can change its counter."""
    active = False
    main_paragraphs = {paragraph._p for paragraph in model.paragraphs}
    for node in model.document.element.body.iter(qn("w:p")):
        if node is heading:
            active = True
            continue
        if node is caption:
            return
        if not active:
            continue
        if node not in main_paragraphs:
            chain = model.paragraph_style_chain(Paragraph(node, model.document._body))
            if (
                not chain.resolved
                or any(
                    (value(style, "w:name") or "").casefold()
                    == f"heading {expected['numbering']['chapter_heading_level']}"
                    or value(one(style, "w:pPr"), "w:outlineLvl")
                    == str(expected["numbering"]["chapter_heading_level"] - 1)
                    for style in chain.value
                )
                or value(one(node, "w:pPr"), "w:outlineLvl")
                == str(expected["numbering"]["chapter_heading_level"] - 1)
            ):
                raise CaptionUncertain(
                    "Вкладений елемент може змінювати розділ підпису; потрібне зіставлення."
                )
        if not any(
            element.tag in {qn("w:fldSimple"), qn("w:fldChar"), qn("w:instrText")}
            for element in node.iter()
        ):
            continue
        tokens, _literals = fields(model, Paragraph(node, model.document._body))
        for token in tokens:
            if not isinstance(token, Field) or not re.match(
                r"\s*SEQ\b", token.instruction, re.IGNORECASE
            ):
                continue
            _kind, name, _switches = instruction(token)
            if name.casefold() != expected["numbering"]["sequence_name"].casefold():
                continue
            if node not in known_captions:
                raise CaptionUncertain(
                    "Поле поза підтвердженим підписом може змінювати його лічильник."
                )
            wrong, _target, _items = numbering(tokens, expected)
            if "reset_at_heading_level" in wrong:
                raise CaptionUncertain(
                    "Попередній підпис має іншу схему лічильника; перевірте послідовність."
                )
