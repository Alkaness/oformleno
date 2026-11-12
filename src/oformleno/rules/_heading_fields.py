"""Distinguish literal headings from cached fields across paragraph boundaries.

A TOC may begin after its literal title and end before the next literal title.
Only those complete, separate block fields may share a heading's trailing runs.
Other field output, malformed boundaries and symbols still require review.
"""

import re
from collections import defaultdict
from dataclasses import dataclass, field

from docx.oxml.ns import qn

_REASON = "Поле або спеціальний символ не дозволяє надійно визначити текст заголовка."
_REVISIONS = {qn(f"w:{tag}") for tag in ("ins", "del", "moveFrom", "moveTo")}


@dataclass(eq=False)
class _Field:
    start: object
    cell: object | None = None
    instruction: list[str] = field(default_factory=list)
    end: object | None = None
    separated: bool = False
    invalid: bool = False

    @property
    def complete(self):
        return (
            self.end is not None
            and self.separated
            and bool("".join(self.instruction).strip())
            and not self.invalid
        )

    @property
    def toc(self):
        return re.match(r"\s*TOC(?:\s|$)", "".join(self.instruction), re.IGNORECASE) is not None


def heading_field_uncertainties(model):
    """Read the main story once, keeping complex-field state between paragraphs."""
    events = defaultdict(list)
    stack = []

    def visit(node, paragraph=None, revised=False):
        if node.tag == qn("w:txbxContent"):
            return  # A text box has its own story and field state.
        if node.tag == qn("w:p"):
            if paragraph is not None:
                return
            paragraph = node
        revised |= node.tag in _REVISIONS
        tag = node.tag
        if tag in {qn("w:fldSimple"), qn("w:sym")}:
            events[paragraph].append(("opaque", None))
            for nested in node.iter(qn("w:p")):
                events[nested].append(("opaque", None))
            return  # Do not let nested simple fields alter the outer stack.
        if tag == qn("w:fldChar"):
            kind = node.get(qn("w:fldCharType"))
            current = stack[-1] if stack else None
            cell = next(node.iterancestors(qn("w:tc")), None)
            malformed = node.getparent().tag != qn("w:r")
            if kind == "begin":
                current = _Field(paragraph, cell, invalid=revised or malformed or paragraph is None)
                if stack and not stack[-1].separated:
                    stack[-1].invalid = current.invalid = True
                stack.append(current)
            elif current is None:
                kind = "opaque"
            elif kind == "separate":
                current.invalid |= current.separated or revised or malformed
                current.separated = True
            elif kind == "end":
                current.end = paragraph
                current.invalid |= revised or malformed or cell is not current.cell
                stack.pop()
                if stack and not current.complete:
                    stack[-1].invalid = True
            else:
                current.invalid = True
                kind = "opaque"
            events[paragraph].append((kind, current))
        elif tag == qn("w:instrText"):
            current = stack[-1] if stack else None
            if current is not None:
                current.invalid |= current.separated or revised or node.getparent().tag != qn("w:r")
                current.instruction.append(node.text or "")
            events[paragraph].append(("instruction", current))
        elif tag == qn("w:t") and node.text:
            events[paragraph].append(("cached" if stack else "literal", None))
        for child in node:
            visit(child, paragraph, revised)

    visit(model.document.element.body)
    uncertain = {}
    for paragraph, items in events.items():
        if paragraph is None:
            continue
        if any(kind in {"opaque", "cached"} for kind, _ in items):
            uncertain[paragraph] = _REASON
            continue
        text = [index for index, (kind, _) in enumerate(items) if kind == "literal"]
        fields = [(index, kind, span) for index, (kind, span) in enumerate(items) if span]
        if not text:
            if len(items):
                uncertain[paragraph] = _REASON
            continue
        first, last = text[0], text[-1]
        suffix = {span for index, _, span in fields if index > last}
        if (
            any(kind == "instruction" and span is None for kind, span in items)
            or any(not span.complete for _, _, span in fields)
            or any(first < index < last for index, _, _ in fields)
            or any(kind != "end" for index, kind, _ in fields if index < first)
            or len(suffix) > 1
            or any(
                not span.toc or span.start is not paragraph or span.end is paragraph
                for span in suffix
            )
        ):
            uncertain[paragraph] = _REASON
    return uncertain
