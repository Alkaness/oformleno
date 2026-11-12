"""R07: configured page starts, without guessing rendered pagination."""

from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph

from oformleno.engine import Location
from oformleno.rules._body_text import finding, manual
from oformleno.rules._page_geometry import GeometryUncertain, section_properties, sections
from oformleno.rules.r06_structural_headings import heading_paragraphs


def _blocks(parent):
    for child in parent:
        if child.tag == qn("w:sectPr"):
            continue
        if child.tag == qn("w:sdt"):
            contents = child.findall(qn("w:sdtContent"))
            if len(contents) == 1:
                yield from _blocks(contents[0])
                continue
        yield child


def _trace(model, paragraph):
    """Ordered authored break/content events; None is uncertain, 0 content, 1 page break."""
    result = []
    runs = {run._r: run for run in model.runs(paragraph)}

    def visit(element, visible=True):
        if element.tag in {qn("w:pPr"), qn("w:rPr"), qn("w:bookmarkStart"), qn("w:bookmarkEnd")}:
            return
        if element.tag == qn("w:r"):
            hidden = model.effective_hidden(runs[element])
            visible = hidden.resolved and not hidden.value
        elif element.tag == qn("w:br"):
            kind = element.get(qn("w:type"), "textWrapping")
            if kind == "page":
                result.append(True if visible else None)
            elif kind != "textWrapping":
                result.append(None)
            return
        elif element.tag == qn("w:t"):
            if (element.text or "").strip():
                result.append(False if visible else None)
            return
        elif element.tag in {qn("w:tab"), qn("w:cr")}:
            return
        elif element.tag == qn("w:sdt"):
            content = element.findall(qn("w:sdtContent"))
            if len(content) == 1:
                visit(content[0], visible)
                return
            result.append(None)
            return
        elif element.tag not in {qn("w:p"), qn("w:hyperlink"), qn("w:sdtContent")}:
            # Cached layout, fields, pictures and unknown wrappers cannot prove
            # a boundary. An authored page break after them can still do so.
            result.append(None)
            return
        for child in element:
            visit(child, visible)

    visit(paragraph._p)
    return result


def _section_boundaries(model):
    found = sections(model)
    result = {}
    for index, section in enumerate(found[:-1]):
        source = section_properties(section)
        parent = source.getparent()
        if parent.tag != qn("w:pPr"):
            raise GeometryUncertain("Межу секції не визначено.")
        following = section_properties(found[index + 1])
        kinds = following.findall(qn("w:type"))
        if len(kinds) > 1:
            raise GeometryUncertain("Тип розриву секції неоднозначний.")
        value = kinds[0].get(qn("w:val")) if kinds else "nextPage"
        result[parent.getparent()] = value in {"nextPage", "evenPage", "oddPage"} or None
    return result


def _start_state(model, item, blocks, positions, boundaries):
    paragraph = item.paragraph
    properties = model.paragraph_property_layers(paragraph)
    if not properties.resolved:
        return None
    if any(
        value is not None and value.find(qn("w:framePr")) is not None for value in properties.value
    ):
        return None
    if any(
        not (hidden := model.effective_hidden(run)).resolved or hidden.value for run in item.runs
    ):
        return None
    flag = model.effective_page_break_before(paragraph)
    if not flag.resolved:
        return None
    if flag.value:
        return True
    events = _trace(model, paragraph)
    prefix = []
    for event in events:
        if event is False:
            break
        prefix.append(event)
    if prefix and prefix[-1] is True:
        return True
    if None in prefix:
        return None
    index = positions.get(paragraph._p)
    if index is None or boundaries is None:
        return None
    for block in reversed(blocks[:index]):
        if block.tag != qn("w:p"):
            return None
        if block in boundaries:
            return boundaries[block]
        previous = Paragraph(block, model.document._body)
        previous_properties = model.paragraph_property_layers(previous)
        if not previous_properties.resolved or any(
            value is not None and value.find(qn("w:framePr")) is not None
            for value in previous_properties.value
        ):
            return None
        trail = _trace(model, previous)
        if trail:
            state = trail[-1]
            if state is True:
                return True
            if state is None or None in prefix:
                return None
            return False
        empty_flag = model.effective_page_break_before(previous)
        if not empty_flag.resolved:
            return None
        if empty_flag.value:
            return True
    return None if None in prefix else True  # First content in the document.


class NewPageChecker:
    def check(self, document, rule, ruleset):
        if (
            set(rule.params) != {"style", "start_on_new_page"}
            or not isinstance(rule.params.get("style"), str)
            or not rule.params["style"].strip()
            or rule.params.get("start_on_new_page") is not True
            or not ruleset.structural_headings
        ):
            yield manual(
                rule, Location(), "Параметри початку структурної частини не підтримуються."
            )
            return
        blocks = list(_blocks(document.document.element.body))
        positions = {element: index for index, element in enumerate(blocks)}
        try:
            boundaries = _section_boundaries(document)
        except GeometryUncertain:
            boundaries = None
        for item in heading_paragraphs(document, rule, ruleset):
            if item.reason:
                yield manual(rule, item.location, item.reason)
                continue
            state = _start_state(document, item, blocks, positions, boundaries)
            if state is None:
                yield manual(
                    rule,
                    item.location,
                    "Розрив або межу сторінки неможливо надійно встановити без компонування.",
                )
            elif not state:
                yield finding(
                    rule,
                    item.location,
                    {"start_on_new_page": False},
                    {"start_on_new_page": True},
                    "Перед структурним заголовком не задано початок нової сторінки.",
                )
