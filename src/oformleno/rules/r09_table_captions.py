"""R09: combined table captions above tables with an independent SEQ counter."""

from oformleno.rules._captions import check_captions


class TableCaptionsChecker:
    def check(self, document, rule, ruleset):
        yield from check_captions(document, rule, ruleset, "table")
