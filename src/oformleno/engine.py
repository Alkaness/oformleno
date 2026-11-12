"""Report types and orchestration of available formatting checks."""

import json
from collections.abc import Iterable, Mapping
from typing import Annotated, Literal, Protocol, Self

from docx.document import Document
from pydantic import Field, JsonValue, StrictBool, computed_field, field_validator, model_validator

from oformleno.model import DocumentModel
from oformleno.ruleset import ConfigModel, DocumentType, NonBlank, RuleConfig, Ruleset, Severity

PositiveIndex = Annotated[int, Field(strict=True, gt=0)]


class Location(ConfigModel):
    section: PositiveIndex | None = None
    paragraph: PositiveIndex | None = None
    page: PositiveIndex | None = None
    excerpt: Annotated[str, Field(strict=True, max_length=50)] | None = None


class Finding(ConfigModel):
    rule_id: NonBlank
    severity: Severity
    location: Location = Field(default_factory=Location)
    actual: JsonValue
    expected: JsonValue
    quote: NonBlank
    fixable: StrictBool = False
    message: NonBlank
    rule_name: NonBlank | None = None
    source_id: NonBlank | None = None
    source_location: NonBlank | None = None
    supporting_quote: NonBlank | None = None
    parameter_sources: dict[str, str] = Field(default_factory=dict)
    source_notes: dict[str, str] = Field(default_factory=dict)
    applies_to: tuple[DocumentType, ...] = ()

    @field_validator("actual", "expected")
    @classmethod
    def validate_json_values(cls, value: JsonValue) -> JsonValue:
        json.dumps(value, allow_nan=False)
        return value

    @model_validator(mode="after")
    def validate_fixability(self) -> Self:
        if self.severity == "manual" and self.fixable:
            raise ValueError("Ручний висновок не можна виправити автоматично.")
        return self


class Summary(ConfigModel):
    errors: int
    warnings: int
    manual: int
    fixable: int
    status: Literal["errors_found", "manual_required", "warnings_found", "no_errors"]
    message: str


class Report(ConfigModel):
    ruleset_id: NonBlank
    ruleset_title: NonBlank
    ruleset_status: Literal["draft", "reviewed"] | None = None
    document_type: DocumentType | None = None
    findings: tuple[Finding, ...] = ()
    checked_rules: tuple[str, ...] = ()
    unavailable_rules: tuple[str, ...] = ()
    failed_rules: tuple[str, ...] = ()
    not_applicable: tuple[str, ...] = ()

    @computed_field
    @property
    def summary(self) -> Summary:
        errors = sum(item.severity == "error" for item in self.findings)
        warnings = sum(item.severity == "warning" for item in self.findings)
        manual = sum(item.severity == "manual" for item in self.findings)
        fixable = sum(item.fixable for item in self.findings)
        if errors:
            status = "errors_found"
        elif (
            manual or self.unavailable_rules or self.failed_rules or self.ruleset_status == "draft"
        ):
            status = "manual_required"
        elif warnings:
            status = "warnings_found"
        else:
            status = "no_errors"
        return Summary(
            errors=errors,
            warnings=warnings,
            manual=manual,
            fixable=fixable,
            status=status,
            message=(
                f"Знайдено {errors} помилок, {fixable} можна виправити автоматично. "
                f"Попереджень: {warnings}. Перевірте вручну: {manual}."
            ),
        )

    def exit_code(self) -> int:
        if self.summary.errors:
            return 1
        if self.summary.status == "manual_required":
            return 3
        return 0


class RuleChecker(Protocol):
    def check(
        self, document: DocumentModel, rule: RuleConfig, ruleset: Ruleset
    ) -> Iterable[Finding]: ...


class EngineError(ValueError):
    """An explained engine input failure safe for user-facing output."""


def _provenance(rule: RuleConfig, ruleset: Ruleset) -> dict:
    sources = {source.id: source for source in ruleset.sources}
    return {
        "rule_id": rule.id,
        "rule_name": rule.name,
        "quote": rule.quote,
        "source_id": rule.source_id,
        "source_location": rule.source_location,
        "supporting_quote": rule.supporting_quote,
        "parameter_sources": dict(rule.parameter_sources),
        "source_notes": {
            identifier: sources[identifier].description or ruleset.source
            for identifier in sorted(set(rule.parameter_sources.values()))
        },
        "applies_to": rule.applies_to,
    }


def _manual(rule: RuleConfig, ruleset: Ruleset, message: str) -> Finding:
    return Finding(
        **_provenance(rule, ruleset),
        severity="manual",
        location=Location(),
        actual=None,
        expected=rule.params,
        fixable=False,
        message=message,
    )


class RuleEngine:
    def __init__(self, checkers: Mapping[str, RuleChecker] | None = None):
        if checkers is None:
            from oformleno.rules import default_checkers

            checkers = default_checkers()
        self._checkers = dict(checkers)

    def check(
        self,
        document: Document | DocumentModel,
        ruleset: Ruleset,
        *,
        document_type: DocumentType | None = None,
    ) -> Report:
        if (
            document_type is not None
            and ruleset.applicability is not None
            and document_type not in ruleset.applicability.document_types
        ):
            raise EngineError("Обраний тип роботи не підтримується цим набором правил.")

        model = document if isinstance(document, DocumentModel) else DocumentModel(document)
        findings = []
        checked = []
        unavailable = []
        failed = []
        not_applicable = []
        for rule in (*ruleset.rules, *ruleset.manual_checks):
            if rule.applies_to:
                if document_type is None:
                    findings.append(
                        _manual(
                            rule,
                            ruleset,
                            "Тип роботи не вказано. Уточніть застосовність цієї вимоги. "
                            + (rule.manual_reason or "Перевірте вимогу вручну."),
                        )
                    )
                    continue
                if document_type not in rule.applies_to:
                    not_applicable.append(rule.id)
                    continue
            if rule.severity == "manual":
                findings.append(_manual(rule, ruleset, rule.manual_reason))
                continue
            if ruleset.status == "draft":
                findings.append(
                    _manual(rule, ruleset, "Набір правил ще не погоджено. Перевірте вимогу вручну.")
                )
                continue
            checker = self._checkers.get(rule.id)
            if checker is None:
                unavailable.append(rule.id)
                findings.append(
                    _manual(rule, ruleset, "Автоматична перевірка цього правила ще не реалізована.")
                )
                continue
            try:
                checked_findings = []
                for item in checker.check(model, rule, ruleset):
                    if item.rule_id != rule.id:
                        raise ValueError("Висновок належить іншому правилу.")
                    severity = "manual" if item.severity == "manual" else rule.severity
                    checked_findings.append(
                        Finding.model_validate(
                            {
                                **item.model_dump(),
                                **_provenance(rule, ruleset),
                                "severity": severity,
                                "fixable": item.fixable and rule.autofix and severity != "manual",
                            }
                        )
                    )
            except Exception:
                # Checkers must not leak document text through exceptions or traces.
                failed.append(rule.id)
                findings.append(
                    _manual(
                        rule, ruleset, "Перевірку не вдалося виконати. Перевірте вимогу вручну."
                    )
                )
            else:
                checked.append(rule.id)
                findings.extend(checked_findings)
        return Report(
            ruleset_id=ruleset.id,
            ruleset_title=ruleset.title,
            ruleset_status=ruleset.status,
            document_type=document_type,
            findings=tuple(findings),
            checked_rules=tuple(checked),
            unavailable_rules=tuple(unavailable),
            failed_rules=tuple(failed),
            not_applicable=tuple(not_applicable),
        )
