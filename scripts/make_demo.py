"""Generate a synthetic ten-error pitch example and verified before/after evidence."""

import argparse
import hashlib
import json
import sys
import tempfile
from collections import Counter
from io import BytesIO
from pathlib import Path

from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Mm, Pt

from oformleno.fixer import fix_document_bytes
from oformleno.report_html import render_report_html
from oformleno.ruleset import load_ruleset

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from fixtures.make_fixtures import make_fixture  # noqa: E402

EXPECTED_ERRORS = {"R01": 1, "R02": 4, "R03": 1, "R04": 1, "R05": 1, "R06": 1, "R08": 1}
BAD_NAME = "Демо_10_помилок.docx"
COPY_NAME = "Демо_виправлено.docx"


def generate_demo(output_dir: Path) -> dict[str, Path]:
    """Create only generated DOCX; refuse to replace existing demo artifacts."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    names = (
        BAD_NAME,
        COPY_NAME,
        "before.json",
        "after.json",
        "before.html",
        "after.html",
        "manifest.json",
    )
    paths = {name: output_dir / name for name in names}
    if any(path.exists() or path.is_symlink() for path in paths.values()):
        raise FileExistsError("Демонстраційні файли вже існують. Оберіть нову теку.")
    ruleset = load_ruleset()
    document = make_fixture("bad_r08", ruleset)
    section = document.sections[0]
    section.page_width = Mm(190)
    for edge, value in (("left", 20), ("right", 20), ("top", 25), ("bottom", 25)):
        setattr(section, edge + "_margin", Mm(value))
    paragraph = document.paragraphs[0]
    paragraph.style = "Normal"
    paragraph.runs[0].font.name = "Calibri"
    paragraph.runs[0].font.size = Pt(12)
    paragraph.paragraph_format.line_spacing = 1
    heading = next(p for p in document.paragraphs if p.text == "Вступ")
    heading.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    stream = BytesIO()
    document.save(stream)
    source = stream.getvalue()
    fixed = fix_document_bytes(
        source, ruleset, document_type="laboratory_report", body_text_mode="ordinary"
    )
    errors = Counter(item.rule_id for item in fixed.before.findings if item.severity == "error")
    remaining = Counter(item.rule_id for item in fixed.after.findings if item.severity == "error")
    if (
        errors != EXPECTED_ERRORS
        or remaining != {"R08": 1}
        or fixed.before.summary.fixable != 9
        or fixed.before.summary.manual != 7
        or fixed.after.summary.manual != 7
        or fixed.before.failed_rules
        or fixed.after.failed_rules
    ):
        raise RuntimeError("Результат демо змінився. Перевірте очікування перед показом.")
    paths[BAD_NAME].write_bytes(source)
    paths[COPY_NAME].write_bytes(fixed.document_bytes)
    for name, report in (("before", fixed.before), ("after", fixed.after)):
        paths[name + ".json"].write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
        paths[name + ".html"].write_text(render_report_html(report), encoding="utf-8")
    manifest = {
        "ruleset": ruleset.id,
        "document_type": "laboratory_report",
        "body_text_mode": "ordinary",
        "synthetic": True,
        "expected_errors": EXPECTED_ERRORS,
        "expected_after_errors": {"R08": 1},
        "before": fixed.before.summary.model_dump(),
        "after": fixed.after.summary.model_dump(),
        "sha256": {
            BAD_NAME: hashlib.sha256(source).hexdigest(),
            COPY_NAME: hashlib.sha256(fixed.document_bytes).hexdigest(),
        },
        "note": "Синтетичне демо; 7 ручних пунктів залишаються. Це не оцінка точності.",
    }
    paths["manifest.json"].write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return paths


def main():
    parser = argparse.ArgumentParser(description="Створити синтетичне демо з 10 помилками.")
    parser.add_argument("output_dir", nargs="?", type=Path)
    args = parser.parse_args()
    folder = args.output_dir or Path(tempfile.mkdtemp(prefix="oformleno-demo-"))
    try:
        paths = generate_demo(folder)
    except (OSError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(f"Демо: 10 помилок → 1, 9 автовиправлень, 7 ручних пунктів. Тека: {folder}")
    print(paths[BAD_NAME])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
