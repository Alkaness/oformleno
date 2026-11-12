"""R02: declared page margins, with manual review for unsupported layouts."""

from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.shared import Mm

from oformleno.rules._page_geometry import (
    GeometryUncertain,
    enabled,
    finding,
    fixable_length,
    manual,
    measurement,
    outside_tolerance,
    parameters,
    property_element,
    section_properties,
    sections,
)

_EDGES = {"left": "Ліве", "top": "Верхнє", "bottom": "Нижнє", "right": "Праве"}


class MarginsChecker:
    def check(self, document, rule, ruleset):
        try:
            expected = parameters(rule, tuple(edge + "_mm" for edge in _EDGES), allow_zero=True)
            document_sections = sections(document)
            try:
                settings = document.document.part.part_related_by(RT.SETTINGS).element
            except KeyError:
                settings = None
            except (ValueError, AttributeError):
                raise GeometryUncertain("Параметри макета документа задані неоднозначно.") from None
            if any(
                enabled(settings, "w:" + name)
                for name in ("mirrorMargins", "bookFoldPrinting", "bookFoldRevPrinting")
            ):
                raise GeometryUncertain(
                    "Дзеркальні поля або книжковий макет потребують ручної перевірки."
                )
        except GeometryUncertain as error:
            yield manual(rule, None, str(error))
            return
        for index, section in enumerate(document_sections, 1):
            try:
                element = section_properties(section)
                property_element(element, "w:pgMar")
                if enabled(element, "w:rtlGutter") or enabled(element, "w:bidi"):
                    raise GeometryUncertain(
                        "Напрямок макета секції потребує ручної перевірки полів."
                    )
                # A gutter can increase the effective edge spacing; do not silently
                # claim compliance by examining left/right margins alone.
                try:
                    gutter = section.gutter
                except (ValueError, TypeError, OverflowError):
                    raise GeometryUncertain(
                        "Відступ для переплетення неможливо визначити."
                    ) from None
                if gutter is not None and gutter != 0:
                    raise GeometryUncertain(
                        "Відступ для переплетення потребує ручної перевірки полів."
                    )
            except GeometryUncertain as error:
                yield manual(rule, index, str(error))
                continue
            for edge, label in _EDGES.items():
                key = edge + "_mm"
                target = {key: expected[key]}
                try:
                    value = measurement(section, edge + "_margin", signed=edge in ("top", "bottom"))
                except GeometryUncertain as error:
                    yield manual(rule, index, f"{label} поле: {error}", expected=target)
                    continue
                if outside_tolerance(value, expected[key], ruleset.tolerance_mm):
                    yield finding(
                        rule,
                        index,
                        {key: value.mm},
                        target,
                        f"{label} поле секції {index}: {value.mm:.2f} мм; "
                        f"потрібно {expected[key]:g} мм.",
                        fixable=fixable_length(expected[key], ruleset.tolerance_mm),
                    )

    def fix(self, document, rule, ruleset):
        plans = [item for item in self.check(document, rule, ruleset) if item.fixable]
        section_list = list(document.sections)
        for item in plans:
            key, value = next(iter(item.expected.items()))
            setattr(
                section_list[item.location.section - 1],
                key.removesuffix("_mm") + "_margin",
                Mm(value),
            )
        return len(plans)
