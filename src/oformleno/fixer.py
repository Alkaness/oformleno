"""Fix reliable R01–R06 findings in a new DOCX, then reopen and recheck it."""

import os
import tempfile
from copy import deepcopy
from dataclasses import dataclass, field
from io import BytesIO
from os import PathLike
from pathlib import Path
from zipfile import ZipFile

from docx import Document
from docx.oxml.ns import qn
from lxml import etree

from oformleno.check_options import BodyTextMode
from oformleno.engine import Report, RuleEngine
from oformleno.loader import MAX_FILE_SIZE_BYTES, DocumentLoadError, load_document_bytes
from oformleno.model import DocumentModel
from oformleno.rules import default_checkers
from oformleno.ruleset import DocumentType, Ruleset

_FIX_RULES = frozenset({"R01", "R02", "R03", "R04", "R05", "R06"})


class FixError(ValueError):
    """A fixed Ukrainian error safe to report without filenames or document text."""


@dataclass(frozen=True)
class FixResult:
    document_bytes: bytes = field(repr=False)
    before: Report = field(repr=False)
    after: Report = field(repr=False)
    applied_rules: tuple[str, ...]


def _content_signature(element, heading_paths=()):
    """Retain all content/structure and every property outside permitted fix fields."""
    root = deepcopy(element)
    # R06 adds permission for these flags only at positively identified targets.
    # Bold/caps/alignment elsewhere, styles and page breaks remain protected.
    namespaces = {key: value for key, value in root.nsmap.items() if key is not None}
    for path in heading_paths:
        for paragraph in root.getroottree().xpath(path, namespaces=namespaces):
            properties = paragraph.find(qn("w:pPr"))
            if properties is not None:
                for alignment in list(properties.findall(qn("w:jc"))):
                    alignment.attrib.pop(qn("w:val"), None)
                    if not alignment.attrib and len(alignment) == 0:
                        properties.remove(alignment)
            for run in paragraph.iter(qn("w:r")):
                if next(run.iterancestors(qn("w:p")), None) is not paragraph:
                    continue
                properties = run.find(qn("w:rPr"))
                if properties is not None:
                    for tag in ("w:b", "w:bCs", "w:caps", "w:smallCaps"):
                        for flag in list(properties.findall(qn(tag))):
                            flag.attrib.pop(qn("w:val"), None)
                            if not flag.attrib and len(flag) == 0:
                                properties.remove(flag)
    permitted = {
        "w:pgSz": ("w:w", "w:h"),
        "w:pgMar": ("w:left", "w:top", "w:bottom", "w:right"),
        "w:rFonts": (
            "w:ascii",
            "w:hAnsi",
            "w:cs",
            "w:asciiTheme",
            "w:hAnsiTheme",
            "w:cstheme",
            "w:hint",
        ),
        "w:sz": ("w:val",),
        "w:szCs": ("w:val",),
        "w:spacing": ("w:line", "w:lineRule"),
    }
    for tag, attributes in permitted.items():
        for node in list(root.iter(qn(tag))):
            for attribute in attributes:
                node.attrib.pop(qn(attribute), None)
            if not node.attrib and len(node) == 0:
                node.getparent().remove(node)
    for tag in ("w:rPr", "w:pPr"):
        for node in list(root.iter(qn(tag))):
            if not node.attrib and len(node) == 0:
                node.getparent().remove(node)
    return etree.tostring(root, method="c14n")


def _replace_main_part(content, part_name, replacement):
    output = BytesIO()
    with ZipFile(BytesIO(content)) as original, ZipFile(output, "w") as corrected:
        names = original.namelist()
        if len(names) != len(set(names)) or names.count(part_name) != 1:
            raise FixError("Структура пакета неоднозначна; автоматичне виправлення неможливе.")
        corrected.comment = original.comment
        for entry in original.infolist():
            payload = replacement if entry.filename == part_name else original.read(entry)
            corrected.writestr(deepcopy(entry), payload)
    return output.getvalue()


def fix_document_bytes(
    content: bytes,
    ruleset: Ruleset,
    *,
    filename: str = "document.docx",
    document_type: DocumentType | None = None,
    body_text_mode: BodyTextMode = "styles",
) -> FixResult:
    """Return a separate in-memory copy and real before/after reports; never fix manual items."""
    document = load_document_bytes(content, filename=filename)
    checkers = default_checkers()
    engine = RuleEngine(checkers)
    before = engine.check(
        document, ruleset, document_type=document_type, body_text_mode=body_text_mode
    )
    paragraphs = DocumentModel(document).paragraphs
    heading_paths = tuple(
        document.element.getroottree().getpath(paragraphs[index - 1]._p)
        for index in sorted(
            {
                item.location.paragraph
                for item in before.findings
                if item.rule_id == "R06" and item.fixable and item.location.paragraph is not None
            }
        )
    )
    signature = _content_signature(document.element, heading_paths)
    applied = []
    try:
        for rule in ruleset.rules:
            if (
                rule.id in _FIX_RULES
                and rule.autofix
                and any(item.rule_id == rule.id and item.fixable for item in before.findings)
            ):
                # Each handler plans all changes before writing; its model is then
                # discarded. No cached model is reused after editing the document.
                if checkers[rule.id].fix(
                    DocumentModel(document, body_text_mode=body_text_mode), rule, ruleset
                ):
                    applied.append(rule.id)
        if _content_signature(document.element, heading_paths) != signature:
            raise FixError("Вміст документа не пройшов перевірку збереження; копію не видано.")
        corrected = (
            _replace_main_part(content, str(document.part.partname).lstrip("/"), document.part.blob)
            if applied
            else content
        )
        # Output may grow beyond the upload-size limit; this internally generated
        # package is reopened directly, without treating it as another upload.
        reopened = Document(BytesIO(corrected))
        if _content_signature(reopened.element, heading_paths) != signature:
            raise FixError("Вміст виправленої копії не пройшов перевірку збереження.")
        after = engine.check(
            reopened, ruleset, document_type=document_type, body_text_mode=body_text_mode
        )
        if after.failed_rules or any(
            item.rule_id in _FIX_RULES and item.fixable for item in after.findings
        ):
            raise FixError("Повторна перевірка копії не підтвердила виправлення; копію не видано.")
    except FixError:
        raise
    except Exception:
        raise FixError("Не вдалося безпечно виправити документ; оригінал не змінено.") from None
    return FixResult(corrected, before, after, tuple(applied))


def _write_new_copy(destination, content):
    temporary = None
    try:
        # Stage with private permissions, then publish exclusively. link() never
        # replaces an existing path, hardlink or symlink, including the original.
        with tempfile.NamedTemporaryFile(
            dir=destination.parent, prefix=".oformleno-", delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(content)
        os.link(temporary, destination)
    except FileExistsError:
        raise FixError(
            "Файл призначення вже існує. Виберіть новий файл для виправленої копії."
        ) from None
    except (OSError, ValueError):
        raise FixError("Не вдалося зберегти виправлену копію в новому файлі.") from None
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                raise FixError("Не вдалося видалити тимчасову копію після запису.") from None


def fix_document(
    source: str | PathLike[str],
    destination: str | PathLike[str],
    ruleset: Ruleset,
    *,
    document_type: DocumentType | None = None,
    body_text_mode: BodyTextMode = "styles",
) -> FixResult:
    """Read a bounded source, verify a corrected copy, then create a new destination."""
    source, destination = Path(source), Path(destination)
    if destination.suffix.lower() != ".docx":
        raise FixError("Виправлену копію потрібно зберегти у форматі .docx.")
    try:
        if source.resolve() == destination.resolve():
            raise FixError("Оригінал не можна перезаписувати. Виберіть новий файл для копії.")
        if destination.exists() or destination.is_symlink():
            raise FixError("Файл призначення вже існує. Виберіть новий файл для виправленої копії.")
        with source.open("rb") as stream:
            content = stream.read(MAX_FILE_SIZE_BYTES + 1)
    except (OSError, ValueError, RuntimeError) as error:
        if isinstance(error, FixError):
            raise
        raise DocumentLoadError("Не вдалося прочитати файл для виправлення.") from None
    result = fix_document_bytes(
        content,
        ruleset,
        filename=source.name,
        document_type=document_type,
        body_text_mode=body_text_mode,
    )
    _write_new_copy(destination, result.document_bytes)
    return result
