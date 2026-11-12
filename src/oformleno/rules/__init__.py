"""Available formatting checks; each rule has its own implementation."""


def default_checkers():
    # Imported on demand to keep the report types independent of rule modules.
    from oformleno.rules.r01_page_size import PageSizeChecker
    from oformleno.rules.r02_margins import MarginsChecker
    from oformleno.rules.r03_body_font import BodyFontChecker
    from oformleno.rules.r04_body_font_size import BodyFontSizeChecker
    from oformleno.rules.r05_body_line_spacing import BodyLineSpacingChecker
    from oformleno.rules.r06_structural_headings import StructuralHeadingChecker
    from oformleno.rules.r07_new_page import NewPageChecker
    from oformleno.rules.r08_figure_captions import FigureCaptionsChecker
    from oformleno.rules.r09_table_captions import TableCaptionsChecker
    from oformleno.rules.r10_page_numbers import PageNumbersChecker

    return {
        "R01": PageSizeChecker(),
        "R02": MarginsChecker(),
        "R03": BodyFontChecker(),
        "R04": BodyFontSizeChecker(),
        "R05": BodyLineSpacingChecker(),
        "R06": StructuralHeadingChecker(),
        "R07": NewPageChecker(),
        "R08": FigureCaptionsChecker(),
        "R09": TableCaptionsChecker(),
        "R10": PageNumbersChecker(),
    }
