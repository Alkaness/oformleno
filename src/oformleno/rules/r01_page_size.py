"""R01: declared paper dimensions for every reliably represented section."""

from docx.shared import Mm

from oformleno.rules._page_geometry import (
    GeometryUncertain,
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


class PageSizeChecker:
    def check(self, document, rule, ruleset):
        try:
            expected = parameters(rule, ("width_mm", "height_mm"))
            document_sections = sections(document)
        except GeometryUncertain as error:
            yield manual(rule, None, str(error))
            return
        for index, section in enumerate(document_sections, 1):
            try:
                element = section_properties(section)
                property_element(element, "w:pgSz")
                # The public API defaults an omitted orient to portrait. Unknown
                # values are not converted into a guessed orientation.
                try:
                    orientation = section.orientation.name
                except (ValueError, TypeError):
                    raise GeometryUncertain("Орієнтацію сторінки неможливо визначити.") from None
                target = dict(expected)
                if orientation == "LANDSCAPE":
                    target["width_mm"], target["height_mm"] = (
                        target["height_mm"],
                        target["width_mm"],
                    )
                width = measurement(section, "page_width", positive=True)
                height = measurement(section, "page_height", positive=True)
            except GeometryUncertain as error:
                yield manual(rule, index, str(error))
                continue
            if outside_tolerance(
                width, target["width_mm"], ruleset.tolerance_mm
            ) or outside_tolerance(height, target["height_mm"], ruleset.tolerance_mm):
                yield finding(
                    rule,
                    index,
                    {"width_mm": width.mm, "height_mm": height.mm},
                    target,
                    f"Розмір сторінки секції {index}: {width.mm:.2f} × {height.mm:.2f} мм; "
                    f"потрібно {target['width_mm']:g} × {target['height_mm']:g} мм.",
                    fixable=all(
                        fixable_length(value, ruleset.tolerance_mm) for value in target.values()
                    ),
                )

    def fix(self, document, rule, ruleset):
        plans = [item for item in self.check(document, rule, ruleset) if item.fixable]
        section_list = list(document.sections)
        for item in plans:
            section = section_list[item.location.section - 1]
            section.page_width = Mm(item.expected["width_mm"])
            section.page_height = Mm(item.expected["height_mm"])
        return len(plans)
