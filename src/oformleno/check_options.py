"""Explicit paragraph-role choices, independent of guideline requirements."""

from typing import Literal

BodyTextMode = Literal["styles", "ordinary"]
BODY_TEXT_MODES = ("styles", "ordinary")
BODY_TEXT_MODE_LABELS = {
    "styles": "За стилями документа",
    "ordinary": "Звичайні абзаци — основний текст",
}
