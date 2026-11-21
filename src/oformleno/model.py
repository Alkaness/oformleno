"""Read effective formatting from an unchanged in-memory Word document."""

import math
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from functools import cached_property
from types import SimpleNamespace
from typing import Literal

from docx.document import Document
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml import parse_xml
from docx.oxml.ns import qn
from docx.oxml.xmlchemy import BaseOxmlElement
from docx.table import Table
from docx.text.paragraph import Paragraph
from docx.text.run import Run

FontSlot = Literal["ascii", "hAnsi", "eastAsia", "cs"]
ResolutionSource = Literal[
    "run",
    "paragraph",
    "character_style",
    "paragraph_style",
    "base_style",
    "doc_defaults",
    "ooxml_default",
]
_THEME_ATTRIBUTES = {
    "ascii": "asciiTheme",
    "hAnsi": "hAnsiTheme",
    "eastAsia": "eastAsiaTheme",
    "cs": "cstheme",
}
_THEME_FONTS = {
    "majorAscii": ("majorFont", "latin"),
    "majorHAnsi": ("majorFont", "latin"),
    "minorAscii": ("minorFont", "latin"),
    "minorHAnsi": ("minorFont", "latin"),
    "majorEastAsia": ("majorFont", "ea"),
    "minorEastAsia": ("minorFont", "ea"),
    "majorBidi": ("majorFont", "cs"),
    "minorBidi": ("minorFont", "cs"),
}
_REVISIONS = {
    qn("w:" + name)
    for name in ("ins", "del", "moveFrom", "moveTo", "rPrChange", "pPrChange", "sectPrChange")
}


@dataclass(frozen=True)
class Resolution[T]:
    value: T | None = None
    source: ResolutionSource | None = None
    reason: str | None = None
    theme_reference: str | None = None

    def __post_init__(self):
        if (self.value is None) == (self.reason is None):
            raise ValueError("Потрібне значення або причина ручної перевірки.")

    @property
    def resolved(self) -> bool:
        return self.reason is None


@dataclass(frozen=True)
class LineSpacing:
    kind: Literal["multiple", "exact", "at_least"]
    value: float

    @property
    def multiplier(self) -> float | None:
        return self.value if self.kind == "multiple" else None

    @property
    def points(self) -> float | None:
        return self.value if self.kind != "multiple" else None


@dataclass(frozen=True)
class RunFormatting:
    slots: Resolution[tuple[FontSlot, ...]]
    fonts: dict[FontSlot, Resolution[str]]
    size_pt: Resolution[float]


class _Unresolved(Exception):
    """Internal control flow carrying a fixed Ukrainian explanation only."""


@dataclass(frozen=True)
class _Layer:
    element: BaseOxmlElement | None
    source: ResolutionSource


def _one(parent: BaseOxmlElement | None, tag: str) -> BaseOxmlElement | None:
    nodes = [] if parent is None else parent.findall(qn(tag))
    if len(nodes) > 1:
        raise _Unresolved("Властивість задана кілька разів. Потрібна ручна перевірка.")
    return nodes[0] if nodes else None


def _path(parent: BaseOxmlElement | None, *tags: str) -> BaseOxmlElement | None:
    for tag in tags:
        parent = _one(parent, tag)
    return parent


def _on_off(value: str | None, *, present: bool = True) -> bool:
    if value in ("1", "true", "on") or (present and value is None):
        return True
    if value in ("0", "false", "off") or not present:
        return False
    raise _Unresolved("Логічна властивість має непідтримуване значення.")


def _measure(value: str | None, divisor: int, *, allow_zero: bool = False) -> float:
    try:
        number = int(value)
        result = number / divisor
    except (TypeError, ValueError, OverflowError):
        raise _Unresolved("Розмір або інтервал має непідтримуване значення.") from None
    if not math.isfinite(result) or number < 0 or (number == 0 and not allow_zero):
        raise _Unresolved("Розмір або інтервал має непідтримуване значення.")
    return result


class DocumentModel:
    """Formatting view; recreate it after editing the underlying document."""

    def __init__(self, document: Document, *, story_part=None, body_text_mode="styles"):
        from oformleno.check_options import BODY_TEXT_MODES

        if body_text_mode not in BODY_TEXT_MODES:
            raise ValueError("Невідомий режим перевірки основного тексту.")
        self.body_text_mode = body_text_mode
        self.document = document
        self._story_part = story_part
        self._story_root = document.element
        self._story_parent = document._body
        if story_part is not None:
            if story_part.package is not document.part.package or story_part.element.tag not in {
                qn("w:hdr"),
                qn("w:ftr"),
            }:
                raise ValueError(
                    "Колонтитул не належить цьому документу або має непідтримувану структуру."
                )
            self._story_root = story_part.element
            self._story_parent = SimpleNamespace(part=story_part)
        self._styles_error = None
        try:
            self._styles = document.part.part_related_by(RT.STYLES).element
        except KeyError:
            self._styles = None
        except (ValueError, AttributeError):
            self._styles = None
            self._styles_error = "Визначення стилів неоднозначне або непідтримуване."
        if self._styles is not None and self._styles.tag != qn("w:styles"):
            self._styles_error = "Визначення стилів має непідтримувану структуру."
        self._style_ids = defaultdict(list)
        if self._styles is not None and self._styles_error is None:
            for style in self._styles.findall(qn("w:style")):
                self._style_ids[style.get(qn("w:styleId"))].append(style)
        self._defaults = {}
        self._scope_issues = {}

    def with_body_text_mode(self, mode):
        """Keep role-selection context local to this check, without mutating XML."""
        if mode == self.body_text_mode:
            return self
        return DocumentModel(self.document, story_part=self._story_part, body_text_mode=mode)

    @property
    def paragraphs(self) -> list[Paragraph]:
        """Main-story paragraphs, including content controls, excluding table cells/textboxes."""
        body = self.document.element.body if self._story_part is None else self._story_root
        return [
            Paragraph(element, self._story_parent)
            for element in body.iter(qn("w:p"))
            if not any(parent.tag in {qn("w:tc"), qn("w:p")} for parent in element.iterancestors())
        ]

    @property
    def sections(self):
        return self.document.sections

    @property
    def tables(self):
        if self._story_part is not None:
            return [
                Table(element, self._story_parent)
                for element in self._story_root.findall(qn("w:tbl"))
            ]
        return self.document.tables

    def runs(self, paragraph: Paragraph) -> tuple[Run, ...]:
        """Include hyperlink/field/control runs without descending into nested paragraphs."""
        return tuple(
            Run(element, paragraph)
            for element in paragraph._p.iter(qn("w:r"))
            if next(element.iterancestors(qn("w:p")), None) is paragraph._p
        )

    def _scope(self, paragraph: Paragraph) -> None:
        if paragraph.part.package is not self.document.part.package:
            raise _Unresolved("Фрагмент не належить цьому документу.")
        if paragraph._p.getroottree().getroot() is not self._story_root:
            raise _Unresolved("Форматування поза основним текстом потребує ручної перевірки.")
        element = paragraph._p
        if element not in self._scope_issues:
            has_revisions = any(node.tag in _REVISIONS for node in element.iter()) or any(
                node.tag in _REVISIONS for node in element.iterancestors()
            )
            self._scope_issues[element] = (
                "Невирішені виправлення потребують ручної перевірки форматування."
                if has_revisions
                else None
            )
        if self._scope_issues[element]:
            raise _Unresolved(self._scope_issues[element])

    def _paragraph(self, run: Run) -> Paragraph:
        element = next(run._r.iterancestors(qn("w:p")), None)
        if element is None:
            raise _Unresolved("Не вдалося визначити абзац фрагмента.")
        paragraph = Paragraph(element, run._parent)
        self._scope(paragraph)
        return paragraph

    def _default_style(self, kind: str) -> BaseOxmlElement | None:
        if self._styles_error:
            raise _Unresolved(self._styles_error)
        if kind not in self._defaults:
            defaults = [
                style
                for items in self._style_ids.values()
                for style in items
                if style.get(qn("w:type"), "paragraph") == kind
                and _on_off(style.get(qn("w:default")), present=qn("w:default") in style.attrib)
            ]
            if len(defaults) > 1:
                raise _Unresolved("Типовий стиль визначено неоднозначно.")
            self._defaults[kind] = defaults[0] if defaults else None
        return self._defaults[kind]

    def _style(self, identifier: str | None) -> BaseOxmlElement:
        if self._styles_error:
            raise _Unresolved(self._styles_error)
        styles = self._style_ids.get(identifier, ())
        if not identifier or len(styles) != 1:
            raise _Unresolved("Стиль відсутній або визначений неоднозначно.")
        return styles[0]

    def _chain(self, style: BaseOxmlElement | None, kind: str) -> Iterator[BaseOxmlElement]:
        visited = set()
        while style is not None:
            if style in visited:
                raise _Unresolved("Ланцюжок стилів містить цикл.")
            if style.get(qn("w:type"), "paragraph") != kind:
                raise _Unresolved("Тип успадкованого стилю не відповідає фрагменту.")
            visited.add(style)
            yield style
            base = _one(style, "w:basedOn")
            style = None if base is None else self._style(base.get(qn("w:val")))

    def _paragraph_styles(self, paragraph: Paragraph) -> Iterator[BaseOxmlElement]:
        reference = _path(paragraph._p, "w:pPr", "w:pStyle")
        style = (
            self._default_style("paragraph")
            if reference is None
            else self._style(reference.get(qn("w:val")))
        )
        yield from self._chain(style, "paragraph")

    def _lower_context(self, paragraph: Paragraph, p_layers: list[BaseOxmlElement | None]):
        if any(node.tag == qn("w:tc") for node in paragraph._p.iterancestors()):
            raise _Unresolved("Успадкування від стилю таблиці потребує ручної перевірки.")
        for element in p_layers:
            numbering = _one(element, "w:numPr")
            if numbering is not None:
                identifier = _one(numbering, "w:numId")
                if identifier is not None and identifier.get(qn("w:val")) == "0":
                    return
                raise _Unresolved("Успадкування від нумерації потребує ручної перевірки.")

    def paragraph_style_chain(
        self, paragraph: Paragraph
    ) -> Resolution[tuple[BaseOxmlElement, ...]]:
        """Read-only style metadata for role detection; no formatting-based role guess."""
        try:
            self._scope(paragraph)
            styles = tuple(self._paragraph_styles(paragraph))
            if any(node.tag in _REVISIONS for style in styles for node in style.iter()):
                raise _Unresolved("Невирішені зміни стилю потребують ручної перевірки.")
            return Resolution(styles, "paragraph_style")
        except _Unresolved as error:
            return Resolution(reason=str(error))

    def _doc_default(self, kind: str) -> BaseOxmlElement | None:
        if self._styles_error:
            raise _Unresolved(self._styles_error)
        return _path(self._styles, "w:docDefaults", "w:" + kind + "Default", "w:" + kind)

    def paragraph_property_layers(self, paragraph: Paragraph) -> Resolution[tuple]:
        """Read-only cascade, including defaults, for conservative geometry checks."""
        chain = self.paragraph_style_chain(paragraph)
        if not chain.resolved:
            return Resolution(reason=chain.reason)
        try:
            return Resolution(tuple(layer.element for layer in self._paragraph_layers(paragraph)))
        except _Unresolved as error:
            return Resolution(reason=str(error))

    def _run_layers(self, run: Run) -> Iterator[_Layer]:
        paragraph = self._paragraph(run)
        direct = _one(run._r, "w:rPr")
        yield _Layer(direct, "run")
        reference = _one(direct, "w:rStyle")
        if reference is not None:
            style = self._style(reference.get(qn("w:val")))
            for depth, element in enumerate(self._chain(style, "character")):
                if any(node.tag in _REVISIONS for node in element.iter()):
                    raise _Unresolved(
                        "Невирішені зміни символьного стилю потребують ручної перевірки."
                    )
                yield _Layer(
                    _one(element, "w:rPr"), "character_style" if depth == 0 else "base_style"
                )
        p_layers = [_one(paragraph._p, "w:pPr")]
        for depth, style in enumerate(self._paragraph_styles(paragraph)):
            p_layers.append(_one(style, "w:pPr"))
            yield _Layer(_one(style, "w:rPr"), "paragraph_style" if depth == 0 else "base_style")
        self._lower_context(paragraph, p_layers)
        yield _Layer(self._doc_default("rPr"), "doc_defaults")

    def _paragraph_layers(self, paragraph: Paragraph) -> Iterator[_Layer]:
        self._scope(paragraph)
        p_layers = [_one(paragraph._p, "w:pPr")]
        yield _Layer(p_layers[0], "paragraph")
        for depth, style in enumerate(self._paragraph_styles(paragraph)):
            properties = _one(style, "w:pPr")
            p_layers.append(properties)
            yield _Layer(properties, "paragraph_style" if depth == 0 else "base_style")
        self._lower_context(paragraph, p_layers)
        yield _Layer(self._doc_default("pPr"), "doc_defaults")

    @cached_property
    def _theme(self) -> BaseOxmlElement | None:
        try:
            if any(
                rel.reltype.endswith("/themeOverride")
                for part in (self.document.part, self._story_part)
                if part is not None
                for rel in part.rels.values()
            ):
                return None
            root = parse_xml(self.document.part.part_related_by(RT.THEME).blob)
        except Exception:
            return None
        return root if root.tag == qn("a:theme") else None

    def _theme_font(self, reference: str) -> str:
        if reference not in _THEME_FONTS or self._theme is None:
            raise _Unresolved("Не вдалося визначити шрифт теми документа.")
        collection, script = _THEME_FONTS[reference]
        font = _path(
            self._theme, "a:themeElements", "a:fontScheme", "a:" + collection, "a:" + script
        )
        name = None if font is None else font.get("typeface")
        if not name or not name.strip():
            raise _Unresolved("Шрифт теми потребує додаткового мовного зіставлення.")
        return name

    def effective_font(self, run: Run, slot: FontSlot = "hAnsi") -> Resolution[str]:
        """Resolve a declared font slot; font_slots() determines which slots the text uses."""
        if slot not in _THEME_ATTRIBUTES:
            raise ValueError("Непідтримуваний шрифтовий набір.")
        try:
            for layer in self._run_layers(run):
                fonts = _one(layer.element, "w:rFonts")
                if fonts is None:
                    continue
                name = fonts.get(qn("w:" + slot))
                reference = fonts.get(qn("w:" + _THEME_ATTRIBUTES[slot]))
                if name is None and reference is None:
                    continue
                if name is not None and (not name.strip() or name.startswith("+")):
                    raise _Unresolved(
                        "Назва шрифту порожня або потребує непідтримуваного зіставлення."
                    )
                theme_name = self._theme_font(reference) if reference is not None else None
                if name is not None and theme_name is not None and name != theme_name:
                    raise _Unresolved(
                        "Пряма назва шрифту й посилання на тему суперечать одне одному."
                    )
                return Resolution(
                    name if name is not None else theme_name,
                    layer.source,
                    theme_reference=reference,
                )
            raise _Unresolved("Шрифт не визначено в підтримуваному ланцюжку успадкування.")
        except _Unresolved as error:
            return Resolution(reason=str(error))

    def _run_metadata(self, run: Run) -> tuple[bool, str | None]:
        flags = {}
        hint = None
        for layer in self._run_layers(run):
            for flag in ("cs", "rtl"):
                element = _one(layer.element, "w:" + flag)
                if flag not in flags and element is not None:
                    flags[flag] = _on_off(element.get(qn("w:val")))
                    if flags[flag]:
                        return True, None
            fonts = _one(layer.element, "w:rFonts")
            if hint is None and fonts is not None:
                hint = fonts.get(qn("w:hint"))
        return False, hint

    @staticmethod
    def _text_slots(run: Run, text: str | None = None) -> tuple[FontSlot, ...]:
        if _one(run._r, "w:sym") is not None:
            raise _Unresolved("Спеціальний символ потребує ручної перевірки шрифту.")
        used = set()
        for character in run.text if text is None else text:
            code = ord(character)
            if code < 128:
                used.add("ascii")
            elif (
                code <= 0x052F
                or 0x1E00 <= code <= 0x1EFF
                or 0x2000 <= code <= 0x20CF
                # MS-OI29500 §2.1.88: plain Mathematical Operators use hAnsi;
                # the existing hint/complex-script guards still apply.
                or 0x2200 <= code <= 0x22FF
            ):
                used.add("hAnsi")
            else:
                raise _Unresolved("Символьний набір фрагмента потребує ручної перевірки.")
        return tuple(slot for slot in ("ascii", "hAnsi") if slot in used)

    def font_slots(self, run: Run, *, text: str | None = None) -> Resolution[tuple[FontSlot, ...]]:
        """Select Latin/Cyrillic slots or an explicit complex-script override conservatively."""
        try:
            complex_script, hint = self._run_metadata(run)
            if complex_script:
                return Resolution(("cs",), "run")
            if hint not in (None, "default", "eastAsia"):
                raise _Unresolved("Підказка символьного набору потребує ручної перевірки.")
            used = self._text_slots(run, text)
            if hint == "eastAsia" and "hAnsi" in used:
                normal = self.effective_font(run, "hAnsi")
                east_asian = self.effective_font(run, "eastAsia")
                if (
                    not normal.resolved
                    or not east_asian.resolved
                    or normal.value != east_asian.value
                ):
                    raise _Unresolved("Східноазійська підказка може змінювати вибір шрифту.")
            return Resolution(used, "run")
        except _Unresolved as error:
            return Resolution(reason=str(error))

    def effective_font_size(
        self, run: Run, *, complex_script: bool | None = None
    ) -> Resolution[float]:
        if complex_script is None:
            try:
                complex_script, hint = self._run_metadata(run)
                if not complex_script:
                    self._text_slots(run)
                    if hint not in (None, "default", "eastAsia"):
                        raise _Unresolved("Підказка символьного набору потребує ручної перевірки.")
            except _Unresolved as error:
                return Resolution(reason=str(error))
        try:
            for layer in self._run_layers(run):
                size = _one(layer.element, "w:szCs" if complex_script else "w:sz")
                if size is not None:
                    return Resolution(_measure(size.get(qn("w:val")), 2), layer.source)
            raise _Unresolved("Розмір шрифту не визначено в ланцюжку успадкування.")
        except _Unresolved as error:
            return Resolution(reason=str(error))

    def run_formatting(self, run: Run) -> RunFormatting:
        slots = self.font_slots(run)
        fonts = {slot: self.effective_font(run, slot) for slot in slots.value or ()}
        size = self.effective_font_size(run)
        return RunFormatting(slots, fonts, size)

    def _effective_toggle(self, run: Run, tag: str) -> Resolution[bool]:
        try:
            self._paragraph(run)
            direct = _one(_one(run._r, "w:rPr"), tag)
            if direct is not None:
                return Resolution(_on_off(direct.get(qn("w:val"))), "run")
            groups = {"paragraph_style": [], "character_style": []}
            group = None
            default = False
            default_source = "ooxml_default"
            for layer in self._run_layers(run):
                if layer.source in groups:
                    group = layer.source
                if _one(layer.element, "w:rPrChange") is not None:
                    raise _Unresolved("Невирішені зміни стилю потребують ручної перевірки.")
                flag = _one(layer.element, tag)
                if flag is None:
                    continue
                value = _on_off(flag.get(qn("w:val")))
                if layer.source == "doc_defaults":
                    default, default_source = value, "doc_defaults"
                elif layer.source != "run" and group is not None:
                    groups[group].append((value, layer.source))
            # Word's documented deviations and basedOn toggle interpretations are
            # not uniform across consumers. Resolve single declarations per style
            # level and ordinary XOR across paragraph/character levels; ambiguous
            # repeated declarations or true defaults combined with styles stay manual.
            if any(
                len(values) > 1 and any(value for value, _ in values) for values in groups.values()
            ):
                raise _Unresolved(
                    "Повторні перемикачі в ланцюжку стилів потребують ручної перевірки."
                )
            if default and any(groups.values()):
                raise _Unresolved(
                    "Перемикачі стилів і типові значення потребують ручної перевірки."
                )
            result, source = default, default_source
            for name in ("paragraph_style", "character_style"):
                for value, origin in groups[name]:
                    if value:
                        result, source = not result, origin
            return Resolution(result, source)
        except _Unresolved as error:
            return Resolution(reason=str(error))

    def effective_caps(self, run: Run) -> Resolution[bool]:
        return self._effective_toggle(run, "w:caps")

    def effective_small_caps(self, run: Run) -> Resolution[bool]:
        return self._effective_toggle(run, "w:smallCaps")

    def effective_hidden(self, run: Run) -> Resolution[bool]:
        return self._effective_toggle(run, "w:vanish")

    def effective_page_break_before(self, paragraph: Paragraph) -> Resolution[bool]:
        try:
            for layer in self._paragraph_layers(paragraph):
                if _one(layer.element, "w:pPrChange") is not None:
                    raise _Unresolved("Невирішені зміни розриву потребують ручної перевірки.")
                flag = _one(layer.element, "w:pageBreakBefore")
                if flag is not None:
                    return Resolution(_on_off(flag.get(qn("w:val"))), layer.source)
            return Resolution(False, "ooxml_default")
        except _Unresolved as error:
            return Resolution(reason=str(error))

    def effective_bold(self, run: Run, *, complex_script: bool | None = None) -> Resolution[bool]:
        try:
            if complex_script is None:
                complex_script, _hint = self._run_metadata(run)
                if not complex_script:
                    self._text_slots(run)
        except _Unresolved as error:
            return Resolution(reason=str(error))
        return self._effective_toggle(run, "w:bCs" if complex_script else "w:b")

    def effective_italic(self, run: Run, *, complex_script: bool | None = None) -> Resolution[bool]:
        try:
            if complex_script is None:
                complex_script, _hint = self._run_metadata(run)
                if not complex_script:
                    self._text_slots(run)
        except _Unresolved as error:
            return Resolution(reason=str(error))
        return self._effective_toggle(run, "w:iCs" if complex_script else "w:i")

    def effective_keep_with_next(self, paragraph: Paragraph) -> Resolution[bool]:
        try:
            for layer in self._paragraph_layers(paragraph):
                flag = _one(layer.element, "w:keepNext")
                if flag is not None:
                    return Resolution(_on_off(flag.get(qn("w:val"))), layer.source)
            return Resolution(False, "ooxml_default")
        except _Unresolved as error:
            return Resolution(reason=str(error))

    def effective_alignment(self, paragraph: Paragraph) -> Resolution[str]:
        names = {
            "left": "left",
            "center": "center",
            "right": "right",
            "both": "justify",
            "distribute": "distribute",
            "mediumKashida": "justify_medium",
            "highKashida": "justify_high",
            "lowKashida": "justify_low",
            "thaiDistribute": "thai_distribute",
            "numTab": "num_tab",
        }
        try:
            bidi = None
            for layer in self._paragraph_layers(paragraph):
                if _one(layer.element, "w:pPrChange") is not None:
                    raise _Unresolved("Невирішені зміни вирівнювання потребують ручної перевірки.")
                alignment = _one(layer.element, "w:jc")
                if alignment is not None:
                    value = alignment.get(qn("w:val"))
                    if value not in names:
                        raise _Unresolved("Вирівнювання потребує додаткового визначення напрямку.")
                    return Resolution(names[value], layer.source)
                direction = _one(layer.element, "w:bidi")
                if bidi is None and direction is not None:
                    bidi = _on_off(direction.get(qn("w:val")))
            if bidi:
                raise _Unresolved(
                    "Типове вирівнювання за напрямком тексту потребує ручної перевірки."
                )
            return Resolution("left", "ooxml_default")
        except _Unresolved as error:
            return Resolution(reason=str(error))

    def effective_line_spacing(self, paragraph: Paragraph) -> Resolution[LineSpacing]:
        try:
            for layer in self._paragraph_layers(paragraph):
                spacing = _one(layer.element, "w:spacing")
                if spacing is None:
                    continue
                line = spacing.get(qn("w:line"))
                rule = spacing.get(qn("w:lineRule"))
                if line is None:
                    if rule is not None:
                        raise _Unresolved("Правило міжрядкового інтервалу задано без величини.")
                    continue
                if rule in (None, "auto"):
                    value = LineSpacing("multiple", _measure(line, 240, allow_zero=True))
                elif rule in ("exact", "atLeast"):
                    value = LineSpacing(
                        "exact" if rule == "exact" else "at_least",
                        _measure(line, 20, allow_zero=True),
                    )
                else:
                    raise _Unresolved("Правило міжрядкового інтервалу не підтримується.")
                return Resolution(value, layer.source)
            return Resolution(LineSpacing("multiple", 1.0), "ooxml_default")
        except _Unresolved as error:
            return Resolution(reason=str(error))
