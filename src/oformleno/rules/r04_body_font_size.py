"""R04: effective run sizes, with unresolved inheritance kept manual."""

from oformleno.engine import Location
from oformleno.rules._body_text import body_paragraphs, finding, manual, parameter, representable
from oformleno.rules._run_formatting import set_font_size


class BodyFontSizeChecker:
    def check(self, document, rule, ruleset):
        try:
            expected = parameter(rule, "size_pt")
        except ValueError as error:
            yield manual(rule, Location(), str(error))
            return
        for item in body_paragraphs(document, rule, ruleset):
            if item.reason:
                yield manual(rule, item.location, item.reason)
                continue
            wrong = set()
            reasons = set()
            fixable = representable(expected, 2)
            for run in item.runs:
                size = document.effective_font_size(run)
                if not size.resolved:
                    reasons.add(size.reason)
                elif size.value != expected:
                    wrong.add(size.value)
                    fixable = fixable and document.font_slots(run).resolved
            if wrong:
                yield finding(
                    rule,
                    item.location,
                    {"size_pt": sorted(wrong)},
                    {"size_pt": expected},
                    "Розмір основного тексту: "
                    + ", ".join(f"{value:g}" for value in sorted(wrong))
                    + f" пт; потрібно {expected:g} пт.",
                    fixable=fixable,
                )
            if reasons:
                yield manual(rule, item.location, " ".join(sorted(reasons)))

    def fix(self, document, rule, ruleset):
        locations = {
            item.location.paragraph for item in self.check(document, rule, ruleset) if item.fixable
        }
        if not locations:
            return 0
        expected = parameter(rule, "size_pt")
        plans = []
        for item in body_paragraphs(document, rule, ruleset):
            if item.reason or item.location.paragraph not in locations:
                continue
            for run in item.runs:
                size = document.effective_font_size(run)
                slots = document.font_slots(run)
                if size.resolved and size.value != expected and slots.resolved:
                    plans.append((run, "w:szCs" if slots.value == ("cs",) else "w:sz"))
        for run, tag in plans:
            set_font_size(run, tag == "w:szCs", expected)
        return len(plans)
