"""R08: figure caption placement, typography and automatic chapter numbering."""

from oformleno.rules._captions import check_captions


class FigureCaptionsChecker:
    def check(self, document, rule, ruleset):
        yield from check_captions(document, rule, ruleset, "figure")
