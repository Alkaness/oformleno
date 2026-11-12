"""Validate YAML configuration without changing its parameters or quotations."""

import json
import re
import sysconfig
from datetime import date
from os import PathLike
from pathlib import Path
from typing import Annotated, Literal, Self

import yaml
from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StrictBool,
    ValidationError,
    field_validator,
    model_validator,
)

DEFAULT_RULESET_ID = "lpnu-eom-styles-2026"
DocumentType = Literal["laboratory_report", "qualification_thesis", "other_printed_work"]
Severity = Literal["error", "warning", "manual"]


def _nonblank(value: str) -> str:
    if not value.strip():
        raise ValueError("Текстове поле не може бути порожнім.")
    return value


NonBlank = Annotated[str, Field(strict=True, min_length=1), AfterValidator(_nonblank)]


class ConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class Source(ConfigModel):
    id: NonBlank
    file: NonBlank | None = None
    sha256: Annotated[str, Field(pattern=r"^[a-fA-F0-9]{64}$")] | None = None
    kind: Literal["user_selected_example"] | None = None
    description: NonBlank | None = None
    decision_date: date | None = None

    @model_validator(mode="after")
    def validate_origin(self) -> Self:
        if self.kind == "user_selected_example":
            if not self.description or self.file is not None or self.sha256 is not None:
                raise ValueError("Для зразка потрібен опис без персональної назви файлу.")
        elif self.file is None or self.sha256 is None:
            raise ValueError("Для методички потрібні назва файлу й контрольна сума.")
        return self


class Applicability(ConfigModel):
    department: NonBlank
    document_types: tuple[DocumentType, ...] = Field(min_length=1)
    note: NonBlank | None = None


class RuleConfig(ConfigModel):
    id: Annotated[str, Field(pattern=r"^R\d{2}$")]
    name: NonBlank
    params: dict[str, JsonValue] = Field(default_factory=dict)
    severity: Severity
    autofix: StrictBool
    quote: NonBlank
    source_id: NonBlank | None = None
    source_location: NonBlank | None = None
    supporting_quote: NonBlank | None = None
    parameter_sources: dict[str, NonBlank] = Field(default_factory=dict)
    manual_reason: NonBlank | None = None
    manual_when: NonBlank | None = None
    applies_to: tuple[DocumentType, ...] = ()

    @field_validator("params")
    @classmethod
    def validate_json_parameters(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        json.dumps(value, allow_nan=False)
        return value

    @model_validator(mode="after")
    def validate_manual_policy(self) -> Self:
        if self.severity == "manual" and (self.autofix or not self.manual_reason):
            raise ValueError("Ручній перевірці потрібна причина; автовиправлення заборонене.")
        if self.source_id and not self.source_location:
            raise ValueError("Потрібне місце вимоги у джерелі.")
        if not self.parameter_sources.keys() <= self.params.keys():
            raise ValueError("Походження вказано для невідомого параметра.")
        return self


class ManualCheckConfig(RuleConfig):
    id: Annotated[str, Field(pattern=r"^M\d{2}$")]
    severity: Literal["manual"] = "manual"
    autofix: StrictBool = False


class Ruleset(ConfigModel):
    id: Annotated[str, Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")]
    title: NonBlank
    source: NonBlank
    status: Literal["draft", "reviewed"] | None = None
    source_review: NonBlank | None = None
    profile_note: NonBlank | None = None
    sources: tuple[Source, ...] = ()
    applicability: Applicability | None = None
    tolerance_mm: Annotated[float, Field(strict=True, ge=0)] = 0.5
    structural_headings: tuple[NonBlank, ...] = ()
    rules: tuple[RuleConfig, ...] = Field(min_length=1)
    manual_checks: tuple[ManualCheckConfig, ...] = ()

    @model_validator(mode="after")
    def validate_references(self) -> Self:
        source_ids = [source.id for source in self.sources]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("Ідентифікатори джерел повторюються.")
        checks = (*self.rules, *self.manual_checks)
        ids = [rule.id for rule in checks]
        if len(ids) != len(set(ids)):
            raise ValueError("Ідентифікатори перевірок повторюються.")
        for rule in checks:
            referenced = set(rule.parameter_sources.values())
            if rule.source_id:
                referenced.add(rule.source_id)
            if not referenced <= set(source_ids):
                raise ValueError("Вказано невідоме джерело.")
            if self.applicability and not set(rule.applies_to) <= set(
                self.applicability.document_types
            ):
                raise ValueError("Тип роботи не підтримується цим набором.")
        return self


class RulesetLoadError(ValueError):
    """A user-facing configuration error without source contents or paths."""


class _SafeUniqueLoader(yaml.SafeLoader):
    def compose_node(self, parent, index):
        if self.check_event(yaml.AliasEvent):
            raise yaml.YAMLError("Посилання YAML не підтримуються.")
        return super().compose_node(parent, index)

    def construct_mapping(self, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str) or key in result:
                raise yaml.YAMLError("Ключі YAML мають бути унікальними рядками.")
            result[key] = self.construct_object(value_node, deep=deep)
        return result


def _bundled_path(identifier: str) -> Path:
    checkout = Path(__file__).resolve().parents[2] / "rulesets" / (identifier + ".yaml")
    installed = (
        Path(sysconfig.get_path("data")) / "share/oformleno/rulesets" / (identifier + ".yaml")
    )
    for path in (checkout, installed):
        if path.is_file():
            return path
    raise RulesetLoadError(
        "Набір правил не знайдено. Вкажіть його ідентифікатор або шлях до YAML-файлу."
    )


def load_ruleset(source: str | PathLike[str] = DEFAULT_RULESET_ID) -> Ruleset:
    """Load a bundled identifier or an explicit YAML path with strict validation."""
    identifier = None
    if isinstance(source, str) and re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", source):
        identifier = source
        path = _bundled_path(identifier)
    else:
        path = Path(source)
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError, ValueError):
        raise RulesetLoadError("Не вдалося прочитати набір правил.") from None
    try:
        ruleset = Ruleset.model_validate(yaml.load(text, Loader=_SafeUniqueLoader))
    except (yaml.YAMLError, ValidationError, ValueError, RecursionError):
        raise RulesetLoadError("Набір правил має некоректну структуру або значення.") from None
    if identifier is not None and ruleset.id != identifier:
        raise RulesetLoadError("Ідентифікатор набору правил не відповідає його файлу.")
    return ruleset
