"""Score a pre-sealed private reference without importing the product checker."""

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

CORE_RULES = {f"R{number:02}" for number in range(1, 7)}
VERDICTS = {"violation", "conformant", "not_applicable", "unresolved"}


def valid_hash(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def digest(data):
    return hashlib.sha256(
        json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def key(item):
    return (
        item["rule"],
        item.get("section"),
        item.get("paragraph"),
        item.get("margin"),
        None if item["rule"] in CORE_RULES else item.get("unit"),
    )


def score(reference, run):
    """Fail closed for stale references, unknown applicability and unreviewed errors.

    One R01/R03–R06 finding is one rule/location unit; R02 additionally uses
    the margin. A compound finding must have every reported property supported.
    Manual findings never match a true positive. This is not an Office gate.
    """
    if reference.get("status") != "sealed":
        raise ValueError("Еталон ще не зафіксовано.")
    if not valid_hash(reference.get("runtime_sha256")) or not valid_hash(run.get("runtime_sha256")):
        raise ValueError("Відсутній відбиток зафіксованої версії.")
    if reference.get("body_text_mode") not in {"ordinary", "styles"}:
        raise ValueError("Відсутній або невідомий режим еталона.")
    if run.get("sealed_reference_sha256") != digest(reference):
        raise ValueError("Еталон не відповідає запуску.")
    if run.get("body_text_mode") != reference.get("body_text_mode"):
        raise ValueError("Режим запуску не відповідає еталону.")
    expected = {item["id"]: item for item in reference["documents"]}
    observed = {item["id"]: item for item in run["documents"]}
    if (
        not 3 <= len(expected) <= 5
        or len(expected) != len(reference["documents"])
        or len(observed) != len(run["documents"])
        or expected.keys() != observed.keys()
    ):
        raise ValueError("Потрібні 3–5 однакових незалежних робіт в еталоні й запуску.")
    if run.get("runtime_sha256") != reference.get("runtime_sha256"):
        raise ValueError("Версія перевіряча змінилася після фіксації еталона.")
    totals = Counter()
    rows = []
    for identifier, truth in expected.items():
        product = observed[identifier]
        if (
            not valid_hash(truth.get("artifact_sha256"))
            or not valid_hash(product.get("artifact_sha256"))
            or type(truth.get("core_coverage_complete")) is not bool
        ):
            raise ValueError("Відсутні контрольні суми документа або стан покриття.")
        if truth["artifact_sha256"] != product["artifact_sha256"]:
            raise ValueError("Документ змінився після фіксації еталона.")
        units = {key(item): item for item in truth["units"]}
        if len(units) != len(truth["units"]):
            raise ValueError("Еталон містить повторні одиниці.")
        if any(item["verdict"] not in VERDICTS for item in units.values()):
            raise ValueError("Невідома еталонна позначка.")
        for unit in units.values():
            properties = unit.get("properties", {})
            if not isinstance(properties, dict) or any(
                value not in VERDICTS for value in properties.values()
            ):
                raise ValueError("Невідома позначка властивості еталона.")
            if unit["verdict"] == "violation" and "violation" not in properties.values():
                raise ValueError("Порушення не підтверджено жодною властивістю.")
            if unit["verdict"] in {"conformant", "not_applicable"} and any(
                value in {"violation", "unresolved"} for value in properties.values()
            ):
                raise ValueError("Позначка одиниці суперечить властивостям еталона.")
        counts = Counter()
        matched = set()
        seen = set()
        for finding in product["findings"]:
            if finding["severity"] not in {"error", "warning", "manual"}:
                raise ValueError("Невідомий рівень автоматичного висновку.")
            if finding["severity"] != "error":
                counts["manual" if finding["severity"] == "manual" else "warnings"] += 1
                continue
            counts["predicted"] += 1
            properties = finding.get("properties", [])
            if (
                not isinstance(properties, list)
                or any(not isinstance(value, str) or not value for value in properties)
                or len(properties) != len(set(properties))
                or finding["rule"] in CORE_RULES
                and not properties
            ):
                raise ValueError("Автоматичний висновок має некоректний склад властивостей.")
            target = key(finding)
            if target in seen:
                raise ValueError("Повторний автоматичний висновок для однієї одиниці.")
            seen.add(target)
            unit = units.get(target)
            verdict = unit["verdict"] if unit else "unresolved"
            if verdict == "violation":
                statuses = [
                    unit.get("properties", {}).get(name, "unresolved") for name in properties
                ]
                if not properties or "conformant" in statuses or "not_applicable" in statuses:
                    result = "false_positive"
                elif "unresolved" in statuses:
                    result = "pending"
                elif all(value == "violation" for value in statuses):
                    result = "true_positive"
                    matched.add(target)
                else:
                    raise ValueError("Невідомий стан зіставлення властивостей.")
            elif verdict in {"conformant", "not_applicable"}:
                result = "false_positive"
            else:
                result = "pending"
            counts[result] += 1
            if finding["rule"] in CORE_RULES:
                counts["core_" + result] += 1
        for target, unit in units.items():
            if unit["rule"] not in CORE_RULES:
                continue
            if unit["verdict"] == "unresolved":
                counts["unresolved_core_units"] += 1
            elif unit["verdict"] == "violation" and target not in matched:
                counts["core_false_negative"] += 1
        if not truth.get("core_coverage_complete"):
            counts["incomplete_documents"] += 1
        if product.get("failed_rules") or product.get("unavailable_rules"):
            counts["incomplete_documents"] += 1
        totals.update(counts)
        rows.append({"id": identifier, **dict(counts)})
    precision = (
        totals["true_positive"] / totals["predicted"]
        if totals["predicted"] and not totals["pending"]
        else None
    )
    denominator = totals["core_true_positive"] + totals["core_false_negative"]
    core_complete = not (
        totals["incomplete_documents"] or totals["unresolved_core_units"] or totals["core_pending"]
    )
    return {
        "sealed_reference_sha256": digest(reference),
        "body_text_mode": reference["body_text_mode"],
        "documents": rows,
        "totals": dict(totals),
        "precision": precision,
        "recall_r01_r06": (
            totals["core_true_positive"] / denominator if core_complete and denominator else None
        ),
        "recall_on_known_violations_only": (
            totals["core_true_positive"] / denominator if denominator else None
        ),
        "core_reference_complete": core_complete,
        "claim_ready": precision is not None and core_complete and denominator > 0,
    }


def main():
    parser = argparse.ArgumentParser(description="Порахувати метрики незалежної приватної вибірки.")
    parser.add_argument("reference", type=Path)
    parser.add_argument("run", type=Path)
    args = parser.parse_args()
    try:
        result = score(json.loads(args.reference.read_text()), json.loads(args.run.read_text()))
    except (ValueError, KeyError, TypeError, OSError):
        print("Не вдалося оцінити запуск: перевірте незмінність і повноту приватного еталона.")
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
