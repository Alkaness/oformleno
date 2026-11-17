"""Measure the web processing path on a generated, rendered 30-page DOCX."""

import argparse
import base64
import hashlib
import json
import platform
import re
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path
from time import perf_counter

from docx.oxml.ns import qn
from docx.shared import Pt

from oformleno.web import WebState, process_upload, view_data

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from fixtures.make_fixtures import CELL_STYLE, make_fixture  # noqa: E402


def make_benchmark_document(destination):
    document = make_fixture("good")
    for child in list(document.element.body):
        if child.tag != qn("w:sectPr"):
            document.element.body.remove(child)
    normal = document.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(14)
    normal.paragraph_format.line_spacing = 1.5
    normal.paragraph_format.space_after = Pt(0)
    sentence = "Синтетичний текст для перевірки швидкості оформлення документа. "
    for page in range(30):
        for index in range(4):
            paragraph = document.add_paragraph(style="Normal")
            if page and index == 0:
                paragraph.paragraph_format.page_break_before = True
            for _ in range(4):
                paragraph.add_run(sentence)
        if page % 5 == 4:
            table = document.add_table(rows=2, cols=2)
            for row in table.rows:
                for cell in row.cells:
                    cell.paragraphs[0].style = CELL_STYLE
                    cell.paragraphs[0].add_run("Згенеровані дані")
    document.save(destination)


def benchmark(output_dir, runs=7):
    directory = Path(output_dir).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    source = directory / "benchmark-30-pages.docx"
    result_path = directory / "benchmark.json"
    if any(path.exists() for path in (source, result_path, directory / "layout")):
        raise FileExistsError("Приклади вже існують. Оберіть нову теку.")
    make_benchmark_document(source)
    initial = source.read_bytes()
    layout = directory / "layout"
    layout.mkdir()
    # A generated file only; no user's LibreOffice profile or original is edited.
    with tempfile.TemporaryDirectory(prefix="oformleno-benchmark-lo-") as profile:
        conversion = subprocess.run(
            [
                "libreoffice",
                "-env:UserInstallation=" + Path(profile).as_uri(),
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(layout),
                str(source),
            ],
            check=True,
            capture_output=True,
            timeout=90,
        )
        if conversion.returncode != 0:
            raise RuntimeError("Не вдалося відтворити документ для перевірки сторінок.")
    pdf = layout / "benchmark-30-pages.pdf"
    pdf_info = subprocess.check_output(["pdfinfo", str(pdf)], text=True, timeout=10)
    match = re.search(r"^Pages:\s+(\d+)\s*$", pdf_info, re.MULTILINE)
    if not match or int(match[1]) != 30:
        raise RuntimeError("Файл не має рівно 30 відтворених сторінок; час не зараховано.")
    times = []
    summaries = []
    for _ in range(runs):
        started = perf_counter()
        event = {
            "name": "generated.docx",
            "content": base64.b64encode(source.read_bytes()).decode(),
            "body_text_mode": "ordinary",
        }
        result = process_upload(event)
        ui = view_data(WebState(result=result))
        elapsed = perf_counter() - started
        assert event == {} and ui["report"] and result.corrected is None
        assert not result.before.failed_rules and len(result.before.checked_rules) == 10
        assert result.before.summary.errors == 0
        times.append(elapsed)
        summaries.append(result.before.summary.model_dump())
    assert source.read_bytes() == initial
    result = {
        "pages": 30,
        "page_evidence": "LibreOffice PDF export + pdfinfo",
        "libreoffice": subprocess.check_output(["libreoffice", "--version"], text=True).strip(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "input_bytes": len(initial),
        "input_sha256": hashlib.sha256(initial).hexdigest(),
        "generated": True,
        "paragraphs": 120,
        "body_runs": 480,
        "tables": 6,
        "mode": "ordinary",
        "measured_path": "file read + base64 encode/decode + DOCX load + YAML + R01–R10 + HTML",
        "excluded": "PDF rendering, interpreter startup, network/host/browser latency, copy fixes",
        "seconds": times,
        "first_seconds": times[0],
        "median_seconds": statistics.median(times),
        "max_seconds": max(times),
        "all_under_5_seconds": all(value < 5 for value in times),
        "report_summary": summaries[0],
        "identical_summaries": all(summary == summaries[0] for summary in summaries),
        "original_unchanged": True,
    }
    result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Заміряти перевірку відтвореного 30-сторінкового DOCX."
    )
    parser.add_argument("output_dir", nargs="?", type=Path)
    args = parser.parse_args()
    directory = args.output_dir or Path(tempfile.mkdtemp(prefix="oformleno-benchmark-"))
    result = benchmark(directory)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["all_under_5_seconds"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
