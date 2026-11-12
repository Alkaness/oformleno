"""Verify real profile loading and failures using synthetic YAML files."""

import traceback

import pytest
import yaml

import oformleno.ruleset as configuration
from oformleno.ruleset import RulesetLoadError, load_ruleset


def write_ruleset(tmp_path, data):
    path = tmp_path / "generated.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


def test_loads_eom_by_id_from_another_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    ruleset = load_ruleset("lpnu-eom-styles-2026")

    assert ruleset.status == "reviewed"
    assert len(ruleset.rules) == 10
    assert len(ruleset.manual_checks) == 8
    assert ruleset.rules[1].params["left_mm"] == 25
    assert ruleset.rules[8].parameter_sources["numbering"] == "user_reference"
    assert ruleset.manual_checks[5].applies_to == ("qualification_thesis",)


def test_loads_legacy_profile_without_optional_eom_metadata():
    ruleset = load_ruleset("lpnu-afm-kontrolna-2025")

    assert len(ruleset.rules) == 10
    assert ruleset.sources == ruleset.manual_checks == ()


def test_preserves_parameters_and_exact_quotation(tmp_path, ruleset_data):
    quotation = "  Точна цитата.\nДругий рядок із пробілами.  "
    ruleset_data["rules"][0]["quote"] = quotation
    ruleset_data["rules"][0]["params"] = {
        "line_spacing": 1.5,
        "bold": True,
        "nested": {"labels": ["Рис.", "Табл."]},
    }
    path = write_ruleset(tmp_path, ruleset_data)
    original = path.read_bytes()

    ruleset = load_ruleset(path)

    assert ruleset.rules[0].quote == quotation
    assert ruleset.rules[0].params == ruleset_data["rules"][0]["params"]
    assert path.read_bytes() == original


@pytest.mark.parametrize(
    "damage",
    [
        "no_rules",
        "duplicate_rule",
        "unknown_severity",
        "string_autofix",
        "blank_quote",
        "non_mapping_params",
        "non_finite_parameter",
        "negative_tolerance",
        "boolean_tolerance",
        "extra_field",
        "unknown_source",
        "unknown_parameter_source",
        "manual_without_reason",
        "manual_autofix",
        "unknown_document_type",
    ],
)
def test_rejects_invalid_configuration(tmp_path, ruleset_data, damage):
    rule = ruleset_data["rules"][0]
    if damage == "no_rules":
        ruleset_data["rules"] = []
    elif damage == "duplicate_rule":
        ruleset_data["rules"].append(dict(rule))
    elif damage == "unknown_severity":
        rule["severity"] = "passed"
    elif damage == "string_autofix":
        rule["autofix"] = "true"
    elif damage == "blank_quote":
        rule["quote"] = "  \n "
    elif damage == "non_mapping_params":
        rule["params"] = []
    elif damage == "non_finite_parameter":
        rule["params"]["width_mm"] = float("nan")
    elif damage == "negative_tolerance":
        ruleset_data["tolerance_mm"] = -1
    elif damage == "boolean_tolerance":
        ruleset_data["tolerance_mm"] = True
    elif damage == "extra_field":
        ruleset_data["unexpected"] = True
    elif damage == "unknown_source":
        rule.update(source_id="missing", source_location="Згенероване місце")
    elif damage == "unknown_parameter_source":
        rule["parameter_sources"] = {"width_mm": "missing"}
    elif damage == "manual_without_reason":
        rule.update(severity="manual", autofix=False)
    elif damage == "manual_autofix":
        rule.update(severity="manual", autofix=True, manual_reason="Ручна перевірка.")
    else:
        rule["applies_to"] = ["unknown"]

    with pytest.raises(RulesetLoadError, match="некоректну структуру або значення"):
        load_ruleset(write_ruleset(tmp_path, ruleset_data))


def test_rejects_duplicate_yaml_keys(tmp_path, ruleset_data):
    path = write_ruleset(tmp_path, ruleset_data)
    path.write_text(path.read_text() + "\nid: another-identifier\n", encoding="utf-8")

    with pytest.raises(RulesetLoadError):
        load_ruleset(path)


def test_rejects_yaml_aliases(tmp_path, ruleset_data):
    path = write_ruleset(tmp_path, ruleset_data)
    text = (
        path.read_text()
        .replace("title: Згенеровані вимоги", "title: &title Згенеровані вимоги")
        .replace("source: Згенероване джерело", "source: *title")
    )
    path.write_text(text, encoding="utf-8")

    with pytest.raises(RulesetLoadError):
        load_ruleset(path)


def test_safe_yaml_does_not_execute_python_tag(tmp_path, ruleset_data):
    path = write_ruleset(tmp_path, ruleset_data)
    marker = tmp_path / "must-not-be-created"
    text = path.read_text().replace(
        "    width_mm: 210",
        f"    width_mm: !!python/object/apply:builtins.open ['{marker}', 'w']",
    )
    assert "!!python/object" in text
    path.write_text(text, encoding="utf-8")

    with pytest.raises(RulesetLoadError):
        load_ruleset(path)
    assert not marker.exists()


def test_rejects_duplicate_sources_and_bad_parameter_reference(tmp_path, ruleset_data):
    source = {"id": "guide", "file": "generated.doc", "sha256": "a" * 64}
    ruleset_data["sources"] = [source, dict(source)]
    with pytest.raises(RulesetLoadError):
        load_ruleset(write_ruleset(tmp_path, ruleset_data))

    ruleset_data["sources"] = [source]
    ruleset_data["rules"][0]["parameter_sources"] = {"missing_parameter": "guide"}
    with pytest.raises(RulesetLoadError):
        load_ruleset(write_ruleset(tmp_path, ruleset_data))


def test_sample_source_cannot_store_personal_filename(tmp_path, ruleset_data):
    ruleset_data["sources"] = [
        {
            "id": "example",
            "kind": "user_selected_example",
            "description": "Згенерований опис зразка.",
            "file": "synthetic-personal-name.docx",
        }
    ]
    with pytest.raises(RulesetLoadError):
        load_ruleset(write_ruleset(tmp_path, ruleset_data))


@pytest.mark.parametrize("content", [b"", b"[", b"\xff\xfe\x00"])
def test_rejects_empty_malformed_or_unreadable_yaml(tmp_path, content):
    path = tmp_path / "generated.yaml"
    path.write_bytes(content)
    with pytest.raises(RulesetLoadError):
        load_ruleset(path)


def test_errors_do_not_leak_input(tmp_path, ruleset_data, capsys, caplog):
    marker = "SYNTHETIC_PRIVATE_IDENTIFIER"
    ruleset_data["rules"][0]["autofix"] = marker
    path = write_ruleset(tmp_path, ruleset_data)
    with pytest.raises(RulesetLoadError) as error:
        load_ruleset(path)
    rendered = "".join(traceback.format_exception(error.value))
    assert marker not in rendered
    assert str(path) not in rendered
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""
    assert caplog.records == []


def test_missing_ruleset_has_explained_error(tmp_path):
    with pytest.raises(RulesetLoadError, match="Набір правил не знайдено"):
        load_ruleset("missing-guideline")
    with pytest.raises(RulesetLoadError, match="Не вдалося прочитати"):
        load_ruleset(tmp_path / "missing.yaml")


def test_uses_installed_profile_outside_checkout(tmp_path, ruleset_data, monkeypatch):
    data_root = tmp_path / "prefix"
    directory = data_root / "share/oformleno/rulesets"
    directory.mkdir(parents=True)
    source = write_ruleset(tmp_path, ruleset_data)
    (directory / "generated-guideline.yaml").write_bytes(source.read_bytes())
    monkeypatch.setattr(configuration.sysconfig, "get_path", lambda _: str(data_root))

    assert load_ruleset("generated-guideline").id == "generated-guideline"
    (directory / "different-id.yaml").write_bytes(source.read_bytes())
    with pytest.raises(RulesetLoadError, match="Ідентифікатор набору правил"):
        load_ruleset("different-id")
