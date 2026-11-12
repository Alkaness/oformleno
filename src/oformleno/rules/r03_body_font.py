"""R03: effective fonts of confidently identified body text."""

from oformleno.engine import Location
from oformleno.rules._body_text import body_paragraphs, finding, manual, parameter
from oformleno.rules._run_formatting import set_font_slots


class BodyFontChecker:
    def check(self, document, rule, ruleset):
        try:
            expected = parameter(rule, "font")
        except ValueError as error:
            yield manual(rule, Location(), str(error))
            return
        for item in body_paragraphs(document, rule, ruleset):
            if item.reason:
                yield manual(rule, item.location, item.reason)
                continue
            wrong = set()
            reasons = set()
            for run in item.runs:
                slots = document.font_slots(run)
                if not slots.resolved:
                    reasons.add(slots.reason)
                    continue
                for slot in slots.value:
                    font = document.effective_font(run, slot)
                    if not font.resolved:
                        reasons.add(font.reason)
                    elif font.value.strip().casefold() != expected.strip().casefold():
                        wrong.add(font.value)
            if wrong:
                yield finding(
                    rule,
                    item.location,
                    {"fonts": sorted(wrong)},
                    {"font": expected},
                    f"Шрифт основного тексту: {', '.join(sorted(wrong))}; потрібно {expected}.",
                    fixable=True,
                )
            if reasons:
                yield manual(rule, item.location, " ".join(sorted(reasons)))

    def fix(self, document, rule, ruleset):
        locations = {
            item.location.paragraph for item in self.check(document, rule, ruleset) if item.fixable
        }
        if not locations:
            return 0
        expected = parameter(rule, "font")
        plans = []
        for item in body_paragraphs(document, rule, ruleset):
            if item.reason or item.location.paragraph not in locations:
                continue
            for run in item.runs:
                slots = document.font_slots(run)
                if not slots.resolved:
                    continue
                wrong_slots = []
                for slot in slots.value:
                    font = document.effective_font(run, slot)
                    if (
                        font.resolved
                        and font.value.strip().casefold() != expected.strip().casefold()
                    ):
                        wrong_slots.append(slot)
                if wrong_slots:
                    plans.append((run, wrong_slots))
        for run, slots in plans:
            set_font_slots(run, slots, expected)
        return len(plans)
