"""Read DOCX inputs into memory without changing or retaining source files."""

from io import BytesIO
from os import PathLike
from pathlib import Path

from docx import Document as open_docx
from docx.document import Document
from docx.oxml.ns import qn

MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024


class DocumentLoadError(ValueError):
    """An input could not be loaded; its message is safe to show to the user."""


def load_document(path: str | PathLike[str]) -> Document:
    """Read a DOCX path with a bounded read, then close the source file."""
    source = Path(path)
    _validate_filename(source.name)
    try:
        with source.open("rb") as stream:
            content = stream.read(MAX_FILE_SIZE_BYTES + 1)
    except (OSError, ValueError):
        raise DocumentLoadError(
            "Не вдалося прочитати файл. Перевірте, чи він існує та чи є доступ до читання."
        ) from None

    return load_document_bytes(content, filename=source.name)


def load_document_bytes(content: bytes, *, filename: str) -> Document:
    """Load a named in-memory upload; no temporary files are created."""
    _validate_filename(filename)
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise DocumentLoadError("Розмір файлу перевищує 20 МБ.")

    try:
        document = open_docx(BytesIO(content))
        if document.element.tag != qn("w:document") or document.element.find(qn("w:body")) is None:
            raise ValueError("Missing Word document body")
    except Exception:
        # Parser exceptions can contain input XML. Expose only a fixed message.
        raise DocumentLoadError(
            "Не вдалося відкрити документ .docx. "
            "Файл може бути пошкодженим або мати непідтримувану структуру."
        ) from None

    return document


def _validate_filename(filename: str) -> None:
    if Path(filename).suffix.lower() != ".docx":
        raise DocumentLoadError("Підтримуються лише файли формату .docx.")
