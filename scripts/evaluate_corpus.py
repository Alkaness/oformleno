"""Collect private T014 evidence; score only independently reviewed annotations.

This is an offline research tool, not part of the checker or web interface.
It deliberately exports no excerpts, document text, style names or raw errors.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from collections import Counter
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from lxml import etree

from oformleno.engine import RuleEngine
from oformleno.fixer import fix_document_bytes
from oformleno.loader import load_document_bytes
from oformleno.ruleset import load_ruleset

ROOT = Path(__file__).resolve().parents[1]
RULES = tuple(f"R{i:02}" for i in range(1, 11))
RECALL_RULES = RULES[:6]
REPORTS = tuple(f"report-{i:02}" for i in range(1, 11))
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def digest(content):
    return hashlib.sha256(content).hexdigest()


def write_bytes(path, content):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent, prefix=".evaluation-", delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(content)
        os.link(temporary, path)  # Publish a complete file without replacing another.
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def write_json(path, data):
    write_bytes(path, (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode())


def code_digest():
    paths = sorted((ROOT / "src/oformleno").rglob("*.py"))
    paths += [Path(__file__).resolve(), ROOT / "rulesets/lpnu-eom-styles-2026.yaml"]
    return digest(
        b"".join(str(p.relative_to(ROOT)).encode() + b"\0" + p.read_bytes() for p in paths)
    )


def private_directory(path, *, resume=False):
    # Keep research artifacts inside the existing ignored private tree.
    path = path.resolve()
    if not path.is_relative_to((ROOT / "private").resolve()) or path == ROOT / "private":
        raise ValueError("Результати оцінювання зберігайте в окремій теці private/.")
    if resume:
        if not path.is_dir():
            raise ValueError("Теки попереднього запуску немає.")
    else:
        path.mkdir(parents=True, mode=0o700, exist_ok=False)
    os.chmod(path, 0o700)
    return path


def compact_report(report):
    """Allowlist metadata rather than removing selected personal fields."""
    findings = []
    for index, item in enumerate(report.findings, 1):
        findings.append(
            {
                "id": f"F{index:04}",
                "rule": item.rule_id,
                "severity": item.severity,
                "location": {
                    name: getattr(item.location, name)
                    for name in ("section", "paragraph", "page")
                    if getattr(item.location, name) is not None
                },
                "fixable": item.fixable,
            }
        )
    counts = Counter((item.rule_id, item.severity) for item in report.findings)
    return {
        "summary": {
            "errors": report.summary.errors,
            "manual": report.summary.manual,
            "fixable": report.summary.fixable,
            "warnings": report.summary.warnings,
        },
        "by_rule": {
            rule: {severity: n for (r, severity), n in counts.items() if r == rule}
            for rule in sorted({r for r, _ in counts})
        },
        "checked_rules": list(report.checked_rules),
        "failed_rules": list(report.failed_rules),
        "unavailable_rules": list(report.unavailable_rules),
        "not_applicable": list(report.not_applicable),
        "findings": findings,
    }


def preservation(before, after):
    """Independent package/content audit; do not reuse Fixer's own signature."""
    with ZipFile(BytesIO(before)) as source, ZipFile(BytesIO(after)) as corrected:
        names = source.namelist()
        same_parts = names == corrected.namelist() and len(names) == len(set(names))
        unchanged_parts = same_parts and all(
            source.read(name) == corrected.read(name)
            for name in names
            if name != "word/document.xml"
        )
        parser = etree.XMLParser(resolve_entities=False, no_network=True)
        a = etree.fromstring(source.read("word/document.xml"), parser)
        b = etree.fromstring(corrected.read("word/document.xml"), parser)
        # Remove property containers, retaining all content, fields, objects,
        # table/paragraph/run ordering and relationships in the main story.
        for tree in (a, b):
            for node in tree.xpath("//w:pPr | //w:rPr | //w:sectPr", namespaces=NS):
                node.getparent().remove(node)
        content_equal = etree.tostring(a, method="c14n") == etree.tostring(b, method="c14n")
        return {
            "same_package_entries": same_parts,
            "other_part_payloads_identical": unchanged_parts,
            "content_structure_identical": content_equal,
        }


def libreoffice_check(docx, work_dir):
    executable = shutil.which("libreoffice")
    if executable is None:
        return {"status": "unavailable"}
    # Process output may contain file paths or document metadata: never relay it.
    try:
        with tempfile.TemporaryDirectory(prefix="lo-", dir=work_dir) as temporary:
            temporary = Path(temporary)
            profile = (temporary / "profile").as_uri()
            process = subprocess.run(
                [
                    executable,
                    f"-env:UserInstallation={profile}",
                    "--headless",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    str(temporary),
                    str(docx),
                ],
                capture_output=True,
                timeout=55,
                check=False,
            )
            pdf = temporary / f"{docx.stem}.pdf"
            valid = pdf.exists() and pdf.read_bytes().startswith(b"%PDF-")
            messages = process.stdout + process.stderr
            # Java's javaldx message concerns the installed environment. Retain
            # only counts so neither paths nor document-derived text is logged.
            lines = [line for line in messages.splitlines() if line.strip()]
            warnings = [
                line
                for line in lines
                if re.search(rb"warn|error|repair|corrupt|damag", line, re.I)
                and b"javaldx" not in line
            ]
            status = "opened_exported" if valid and process.returncode == 0 else "failed"
            return {
                "status": status,
                "exit_code": process.returncode,
                "pdf_header_valid": valid,
                "other_diagnostic_lines": len(warnings),
                "javaldx_environment_warning": b"javaldx" in messages,
                "visual_review": "pending",
            }
    except subprocess.TimeoutExpired:
        return {"status": "timeout"}


def review_template(run):
    documents = []
    for item in run["documents"]:
        documents.append(
            {
                "id": item["id"],
                "errors": [
                    {"finding_id": f["id"], "verdict": "pending", "evidence": ""}
                    for f in item["before"]["findings"]
                    if f["severity"] == "error"
                ],
                "missed_errors": [],
                "coverage": {rule: False for rule in RULES},
                "coverage_evidence": "",
                "manual": [
                    {"finding_id": f["id"], "status": "pending", "evidence": ""}
                    for f in item["before"]["findings"]
                    if f["severity"] == "manual"
                ],
                "word": {
                    "status": "pending",
                    "corrected_sha256": item.get("corrected_sha256"),
                    "evidence": "",
                },
            }
        )
    return {"run_digest": digest(json.dumps(run, sort_keys=True).encode()), "documents": documents}


def collect(corpus, output, use_libreoffice, *, resume=False):
    paths = [corpus / f"{name}.docx" for name in REPORTS]
    if not all(path.is_file() for path in paths):
        raise ValueError("Потрібні всі десять приватних копій report-01.docx — report-10.docx.")
    manifest = json.loads((corpus / "manifest.json").read_text())
    expected = {row["id"]: row["copy_sha256"] for row in manifest["reports"]}
    sources = {name: path.read_bytes() for name, path in zip(REPORTS, paths, strict=True)}
    if any(expected.get(name) != digest(content) for name, content in sources.items()):
        raise ValueError("Контрольні суми вибірки не збігаються з маніфестом T002.")
    output = private_directory(output, resume=resume)
    snapshot = {
        "code_digest": code_digest(),
        "sources": {name: digest(content) for name, content in sources.items()},
        "libreoffice_requested": use_libreoffice,
    }
    if resume:
        if json.loads((output / "snapshot.json").read_text()) != snapshot:
            raise ValueError("Код, набір правил, входи або режим запуску змінилися.")
    else:
        write_json(output / "snapshot.json", snapshot)
    corrected_dir = output / "corrected"
    corrected_dir.mkdir(mode=0o700, exist_ok=resume)
    checks_dir = output / "checks"
    checks_dir.mkdir(mode=0o700, exist_ok=resume)
    ruleset = load_ruleset(ROOT / "rulesets/lpnu-eom-styles-2026.yaml")
    run = {"schema_version": 1, "code_digest": snapshot["code_digest"], "documents": []}
    for name, path in zip(REPORTS, paths, strict=True):
        content = sources[name]
        checkpoint = checks_dir / f"{name}.json"
        corrected = corrected_dir / f"{name}.docx"
        if checkpoint.exists():
            item = json.loads(checkpoint.read_text())
            if (
                item["id"] != name
                or item["source_sha256"] != digest(content)
                or (
                    item["correction_status"] == "created"
                    and digest(corrected.read_bytes()) != item["corrected_sha256"]
                )
            ):
                raise ValueError("Збережена перевірка або виправлена копія змінилися.")
            run["documents"].append(item)
            print(json.dumps({"id": name, "resumed": True}), flush=True)
            continue
        report = RuleEngine().check(
            load_document_bytes(content, filename="report.docx"),
            ruleset,
            document_type="laboratory_report",
        )
        item = {
            "id": name,
            "source_sha256": digest(content),
            "before": compact_report(report),
        }
        try:
            result = fix_document_bytes(
                content, ruleset, filename="report.docx", document_type="laboratory_report"
            )
            if compact_report(result.before) != item["before"]:
                raise ValueError("Повторна перевірка дала інший результат.")
            if corrected.exists():
                if corrected.read_bytes() != result.document_bytes:
                    raise ValueError("Збережена копія не відповідає результату виправлення.")
            else:
                write_bytes(corrected, result.document_bytes)
            item.update(
                correction_status="created",
                corrected_sha256=digest(result.document_bytes),
                after=compact_report(result.after),
                applied_rules=list(result.applied_rules),
                preservation=preservation(content, result.document_bytes),
                libreoffice=(
                    libreoffice_check(corrected, output)
                    if use_libreoffice
                    else {"status": "not_run"}
                ),
            )
            item["corrected_unchanged_after_open"] = (
                digest(corrected.read_bytes()) == item["corrected_sha256"]
            )
        except Exception:
            # Library/Office exceptions can contain private values. A failed fix
            # remains explicit and never prevents collecting other reports.
            item["correction_status"] = "failed"
        item["source_unchanged"] = path.read_bytes() == content
        write_json(checkpoint, item)
        run["documents"].append(item)
        print(
            json.dumps(
                {
                    "id": name,
                    **item["before"]["summary"],
                    "correction_status": item["correction_status"],
                    "libreoffice": item.get("libreoffice", {}).get("status", "not_run"),
                }
            ),
            flush=True,
        )
    run["all_sources_unchanged"] = all(
        path.read_bytes() == sources[name] for name, path in zip(REPORTS, paths, strict=True)
    )
    if (output / "run.json").exists():
        if json.loads((output / "run.json").read_text()) != run:
            raise ValueError("Підсумковий запис запуску змінився.")
    else:
        write_json(output / "run.json", run)
    if (output / "review.json").exists():
        if json.loads((output / "review.json").read_text()).get("run_digest") != digest(
            json.dumps(run, sort_keys=True).encode()
        ):
            raise ValueError("Розмітка не відповідає збереженому запуску.")
    else:
        write_json(output / "review.json", review_template(run))
    return run


def score(run, review):
    """Fail closed on missing/stale reviews; manuals never become true positives."""
    expected_digest = digest(json.dumps(run, sort_keys=True).encode())
    if review.get("run_digest") != expected_digest:
        raise ValueError("Розмітка належить іншому запуску оцінювання.")
    rows = review["documents"]
    if len(rows) != 10 or {row["id"] for row in rows} != set(REPORTS):
        raise ValueError("Розмітка має містити рівно десять різних робіт.")
    documents = run["documents"]
    if len(documents) != 10 or {row["id"] for row in documents} != set(REPORTS):
        raise ValueError("Запуск має містити рівно десять різних робіт.")
    by_id = {row["id"]: row for row in rows}
    tp = Counter()
    fp = Counter()
    fn = Counter()
    pending = 0
    pending_core = 0
    unresolved_manual = 0
    unresolved_core_manual = 0
    full_coverage = True
    core_coverage = True
    word_complete = True
    for item in documents:
        row = by_id[item["id"]]
        findings = {f["id"]: f for f in item["before"]["findings"]}
        errors = {key: f for key, f in findings.items() if f["severity"] == "error"}
        annotations = row["errors"]
        if len(annotations) != len(errors) or {a["finding_id"] for a in annotations} != set(errors):
            raise ValueError("Кожна автоматична помилка потребує окремої позначки.")
        for annotation in annotations:
            verdict = annotation["verdict"]
            rule = errors[annotation["finding_id"]]["rule"]
            if verdict not in {"pending", "true_positive", "false_positive"}:
                raise ValueError("Невідома позначка автоматичної помилки.")
            if verdict == "pending" or not annotation.get("evidence", "").strip():
                pending += 1
                pending_core += rule in RECALL_RULES
            elif verdict == "true_positive":
                tp[rule] += 1
            else:
                fp[rule] += 1
        manual = {key for key, f in findings.items() if f["severity"] == "manual"}
        if len(row["manual"]) != len(manual) or {m["finding_id"] for m in row["manual"]} != manual:
            raise ValueError("Кожна ручна перевірка потребує окремої позначки.")
        manual_by_id = {m["finding_id"]: m for m in row["manual"]}
        missed_ids = set()
        linked_manual = set()
        missed_units = set()
        for missed in row["missed_errors"]:
            rule = missed["rule"]
            location = missed.get("location", {})
            unit = (rule, json.dumps(location, sort_keys=True))
            if rule in {"R02", "R10"}:
                # Distinct margins/header variants may share section location.
                if not re.fullmatch(r"[a-z_]{1,40}", missed.get("unit", "")):
                    raise ValueError("Для поля або колонтитула вкажіть окрему властивість unit.")
                unit += (missed["unit"],)
            if (
                rule not in RULES
                or not missed.get("id")
                or missed["id"] in missed_ids
                or unit in missed_units
                or not missed.get("evidence", "").strip()
                or not location
                or any(k not in {"section", "paragraph", "page"} for k in location)
                or any(type(v) is not int or v < 1 for v in location.values())
            ):
                raise ValueError("Пропуск потребує унікального правила, місця та доказу.")
            missed_ids.add(missed["id"])
            missed_units.add(unit)
            manual_id = missed.get("manual_finding_id")
            if manual_id is not None:
                if (
                    manual_id not in manual
                    or findings[manual_id]["rule"] != rule
                    or findings[manual_id]["location"] != location
                ):
                    raise ValueError("Пропуск не відповідає пов'язаній ручній перевірці.")
                linked_manual.add(manual_id)
            fn[rule] += 1
        for key, annotation in manual_by_id.items():
            status = annotation["status"]
            if status not in {"pending", "no_violation", "violation", "unresolved"}:
                raise ValueError("Невідома позначка ручної перевірки.")
            is_automatic = findings[key]["rule"] in RULES
            if status == "violation" and is_automatic and key not in linked_manual:
                raise ValueError("Порушення під manual треба врахувати серед пропусків.")
            if key in linked_manual and status != "violation":
                raise ValueError("Зв'язок із пропуском потребує позначки порушення.")
            if is_automatic and (
                status in {"pending", "unresolved"} or not annotation.get("evidence", "").strip()
            ):
                unresolved_manual += 1
                unresolved_core_manual += findings[key]["rule"] in RECALL_RULES
        coverage = row["coverage"]
        full_coverage &= (
            set(coverage) == set(RULES)
            and all(value is True for value in coverage.values())
            and bool(row.get("coverage_evidence", "").strip())
        )
        core_coverage &= all(coverage.get(rule) is True for rule in RECALL_RULES) and bool(
            row.get("coverage_evidence", "").strip()
        )
        word = row["word"]
        word_complete &= (
            word.get("status") == "opened_without_warnings"
            and word.get("corrected_sha256") == item.get("corrected_sha256")
            and item.get("corrected_sha256") is not None
            and bool(word.get("evidence", "").strip())
        )
    predicted = sum(tp.values()) + sum(fp.values())
    precision = sum(tp.values()) / predicted if pending == 0 and predicted else None
    recall_tp = sum(tp[r] for r in RECALL_RULES)
    recall_fn = sum(fn[r] for r in RECALL_RULES)
    reference_complete = full_coverage and unresolved_manual == 0 and pending == 0
    # Spec recall covers R01–R06. Deferred captions/page checks remain visible
    # without turning their reviews into prerequisites for this metric.
    recall_reference_complete = core_coverage and unresolved_core_manual == 0 and pending_core == 0
    recall = (
        recall_tp / (recall_tp + recall_fn)
        if recall_reference_complete and recall_tp + recall_fn
        else None
    )
    integrity_complete = run.get("all_sources_unchanged") is True and all(
        item.get("source_unchanged") is True
        and item.get("correction_status") == "created"
        and item.get("corrected_unchanged_after_open") is True
        and all(
            item.get("preservation", {}).get(key) is True
            for key in (
                "same_package_entries",
                "other_part_payloads_identical",
                "content_structure_identical",
            )
        )
        and not item["before"]["failed_rules"]
        and not item["before"]["unavailable_rules"]
        for item in documents
    )
    lo_complete = all(
        item.get("libreoffice", {}).get("status") == "opened_exported"
        and item["libreoffice"].get("other_diagnostic_lines") == 0
        for item in documents
    )
    return {
        "confirmed_true_positives": dict(sorted(tp.items())),
        "confirmed_false_positives": dict(sorted(fp.items())),
        "confirmed_missed_errors": dict(sorted(fn.items())),
        "pending_error_reviews": pending,
        "unresolved_automatic_manual_findings": unresolved_manual,
        "unresolved_recall_manual_findings": unresolved_core_manual,
        "reference_complete": reference_complete,
        "recall_reference_complete": recall_reference_complete,
        "precision": precision,
        "precision_upper_bound": (
            (sum(tp.values()) + pending) / (predicted + pending) if predicted + pending else None
        ),
        "recall_r01_r06": recall,
        "recall_upper_bound_r01_r06": (
            (recall_tp + pending_core) / (recall_tp + pending_core + recall_fn)
            if recall_tp + pending_core + recall_fn
            else None
        ),
        "integrity_complete": integrity_complete,
        "libreoffice_complete": lo_complete,
        "word_complete": word_complete,
        "checkpoint_ready": (
            recall_reference_complete
            and precision is not None
            and precision >= 0.9
            and recall is not None
            and recall >= 0.8
            and integrity_complete
            and lo_complete
            and word_complete
        ),
    }


def main():
    parser = argparse.ArgumentParser(description="Приватне оцінювання десяти робіт ЕОМ (T014).")
    sub = parser.add_subparsers(dest="command", required=True)
    collect_parser = sub.add_parser("collect", help="Перевірити роботи й створити нові копії.")
    collect_parser.add_argument("--corpus", type=Path, default=ROOT / "private/t002/corpus")
    collect_parser.add_argument("--output", type=Path, required=True)
    collect_parser.add_argument("--libreoffice", action="store_true")
    collect_parser.add_argument(
        "--resume", action="store_true", help="Продовжити незмінний запуск."
    )
    score_parser = sub.add_parser("score", help="Порахувати метрики за незалежною розміткою.")
    score_parser.add_argument("--run", type=Path, required=True)
    score_parser.add_argument("--review", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "collect":
            collect(args.corpus, args.output, args.libreoffice, resume=args.resume)
        else:
            result = score(json.loads(args.run.read_text()), json.loads(args.review.read_text()))
            print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception:
        # Even parse/I/O errors can embed private paths or text. Keep stdout and
        # stderr safe; artifacts already created remain available for inspection.
        parser.exit(
            2, "Оцінювання не завершено. Перевірте приватні вхідні дані й доступ до теки.\n"
        )


if __name__ == "__main__":
    main()
