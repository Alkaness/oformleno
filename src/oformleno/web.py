"""In-memory web processing and session-local results, without retained uploads."""

import base64
import binascii
from dataclasses import dataclass, field

from oformleno.check_options import BODY_TEXT_MODES
from oformleno.engine import Report, RuleEngine
from oformleno.fixer import FixError, fix_document_bytes
from oformleno.loader import MAX_FILE_SIZE_BYTES, DocumentLoadError, load_document_bytes
from oformleno.report_html import render_report_html
from oformleno.ruleset import load_ruleset

_MAX_ENCODED_SIZE = 4 * ((MAX_FILE_SIZE_BYTES + 2) // 3)
_PROCESSING_ERROR = "Не вдалося обробити документ. Оберіть файл і спробуйте ще раз."


@dataclass(frozen=True)
class WebResult:
    before: Report = field(repr=False)
    after: Report | None = field(default=None, repr=False)
    corrected: bytes | None = field(default=None, repr=False)
    copy_error: str | None = None


@dataclass
class WebState:
    result: WebResult | None = field(default=None, repr=False)
    show_corrected: bool = False
    error: str | None = None
    revision: int = 0


def process_upload(payload: object) -> WebResult:
    """Consume a one-shot upload event; clear its source fields on every outcome.

    No files or caches are used. Reports and a genuinely changed new copy are
    the only returned data. An unchanged source is never kept as a download.
    """
    try:
        if not isinstance(payload, dict) or set(payload) not in (
            {"name", "content"},
            {"name", "content", "body_text_mode"},
        ):
            raise DocumentLoadError("Не вдалося прочитати завантаження. Оберіть файл ще раз.")
        body_text_mode = payload.pop("body_text_mode", "ordinary")
        if body_text_mode not in BODY_TEXT_MODES:
            raise DocumentLoadError("Невідомий режим основного тексту. Оберіть режим ще раз.")
        name, encoded = payload.pop("name"), payload.pop("content")
        if not isinstance(name, str) or not isinstance(encoded, str):
            raise DocumentLoadError("Не вдалося прочитати завантаження. Оберіть файл ще раз.")
        if len(encoded) > _MAX_ENCODED_SIZE:
            raise DocumentLoadError("Розмір файлу перевищує 20 МБ.")
        try:
            content = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error):
            raise DocumentLoadError(
                "Не вдалося прочитати завантаження. Оберіть файл ще раз."
            ) from None
        del encoded
        ruleset = load_ruleset()
        document = load_document_bytes(content, filename=name)
        del name
        before = RuleEngine().check(
            document, ruleset, document_type="laboratory_report", body_text_mode=body_text_mode
        )
        del document
        if not before.summary.fixable:
            return WebResult(before)
        try:
            fixed = fix_document_bytes(
                content,
                ruleset,
                filename="document.docx",
                document_type="laboratory_report",
                body_text_mode=body_text_mode,
            )
        except FixError:
            return WebResult(
                before,
                copy_error="Не вдалося безпечно підготувати копію. Звіт доступний; "
                "для повторної спроби завантажте документ ще раз.",
            )
        return WebResult(before, fixed.after, fixed.document_bytes)
    finally:
        if isinstance(payload, dict):
            payload.clear()


def accept_upload(state: WebState, payload: object) -> None:
    """Replace the previous result, including on failure; never log exceptions."""
    state.result = None
    state.show_corrected = False
    state.error = None
    state.revision += 1
    try:
        state.result = process_upload(payload)
    except DocumentLoadError as error:
        state.error = str(error)
    except Exception:
        state.error = _PROCESSING_ERROR


def reveal_copy(state: WebState) -> None:
    if state.result is not None and state.result.corrected is not None:
        state.show_corrected = True
        state.revision += 1


def clear_result(state: WebState) -> None:
    state.result = None
    state.show_corrected = False
    state.error = None
    state.revision += 1


def view_data(state: WebState) -> dict:
    """Only safe UI data and the requested corrected output cross to the browser."""
    result = state.result
    if result is None:
        return {"revision": state.revision, "error": state.error, "report": None}
    report = result.after if state.show_corrected else result.before
    return {
        "revision": state.revision,
        "error": result.copy_error,
        "report": render_report_html(report),
        "fixable": result.before.summary.fixable,
        "ready": state.show_corrected,
        "can_reveal": result.corrected is not None and not state.show_corrected,
        "download": (
            base64.b64encode(result.corrected).decode("ascii") if state.show_corrected else None
        ),
    }
