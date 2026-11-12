"""R05: multiple line spacing is distinct from exact or minimum point spacing."""

from oformleno.engine import Location
from oformleno.rules._body_text import body_paragraphs, finding, manual, parameter, representable


class BodyLineSpacingChecker:
    def check(self, document, rule, ruleset):
        try:
            expected = parameter(rule, "line_spacing")
        except ValueError as error:
            yield manual(rule, Location(), str(error))
            return
        for item in body_paragraphs(document, rule, ruleset):
            if item.reason:
                yield manual(rule, item.location, item.reason)
                continue
            spacing = document.effective_line_spacing(item.paragraph)
            if not spacing.resolved:
                yield manual(rule, item.location, spacing.reason)
                continue
            value = spacing.value
            if value.kind != "multiple" or value.value != expected:
                names = {"multiple": "кратний", "exact": "точно", "at_least": "щонайменше"}
                unit = "рядка" if value.kind == "multiple" else "пт"
                yield finding(
                    rule,
                    item.location,
                    {"kind": value.kind, "value": value.value},
                    {"kind": "multiple", "value": expected},
                    f"Міжрядковий інтервал: {names[value.kind]} {value.value:g} {unit}; "
                    f"потрібно {expected:g} рядка.",
                    fixable=representable(expected, 240),
                )

    def fix(self, document, rule, ruleset):
        locations = {
            item.location.paragraph for item in self.check(document, rule, ruleset) if item.fixable
        }
        plans = [
            item.paragraph
            for item in body_paragraphs(document, rule, ruleset)
            if not item.reason and item.location.paragraph in locations
        ]
        if plans:
            expected = parameter(rule, "line_spacing")
            for paragraph in plans:
                paragraph.paragraph_format.line_spacing = float(expected)
        return len(plans)
