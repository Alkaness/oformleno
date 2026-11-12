"""Local run-format setters shared by body and structural-heading fixes."""

from docx.oxml import OxmlElement
from docx.oxml.ns import qn


def set_font_slots(run, slots, expected):
    themes = {"ascii": "asciiTheme", "hAnsi": "hAnsiTheme", "cs": "cstheme"}
    fonts = run._r.get_or_add_rPr().get_or_add_rFonts()
    for slot in slots:
        fonts.set(qn("w:" + slot), expected)
        fonts.attrib.pop(qn("w:" + themes[slot]), None)
    if any(slot in ("ascii", "hAnsi") for slot in slots):
        fonts.set(qn("w:hint"), "default")


def set_font_size(run, complex_script, expected):
    properties = run._r.get_or_add_rPr()
    if not complex_script:
        size = properties.get_or_add_sz()
    else:
        size = properties.find(qn("w:szCs"))
        if size is None:
            size = OxmlElement("w:szCs")
            properties.insert_element_before(
                size,
                "w:highlight",
                "w:u",
                "w:effect",
                "w:bdr",
                "w:shd",
                "w:fitText",
                "w:vertAlign",
                "w:rtl",
                "w:cs",
                "w:em",
                "w:lang",
                "w:eastAsianLayout",
                "w:specVanish",
                "w:oMath",
                "w:rPrChange",
            )
    size.set(qn("w:val"), str(int(expected * 2)))
