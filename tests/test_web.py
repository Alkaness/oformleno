"""Consume generated uploads, preserve source bytes, and retain only web results."""

import base64

import pytest

import oformleno.web as web
from oformleno.engine import Report
from oformleno.fixer import FixError
from oformleno.loader import MAX_FILE_SIZE_BYTES, DocumentLoadError, load_document_bytes


def payload(content, name="generated.docx"):
    return {"name": name, "content": base64.b64encode(content).decode("ascii")}


@pytest.mark.parametrize("rule_id", [f"R{number:02}" for number in range(1, 7)])
def test_corrected_copy_is_prepared_and_source_event_is_consumed(eom_fixtures, rule_id):
    source = eom_fixtures["bad_" + rule_id.lower()]
    original = source.read_bytes()
    event = payload(original, "PRIVATE_IDENTIFIER.docx")
    result = web.process_upload(event)
    assert event == {} and source.read_bytes() == original
    assert result.before.summary.errors == result.before.summary.fixable == 1
    assert result.after.summary.errors == result.after.summary.fixable == 0
    assert result.after.summary.manual == 7
    assert result.corrected and result.corrected != original
    load_document_bytes(result.corrected, filename="new.docx")
    assert original not in vars(result).values()
    assert "PRIVATE_IDENTIFIER" not in repr(result)


@pytest.mark.parametrize("case", ["good", "bad_r07", "bad_r08", "bad_r09", "bad_r10"])
def test_no_fixable_errors_means_no_retained_source_or_fake_download(eom_fixtures, case):
    event = payload(eom_fixtures[case].read_bytes())
    result = web.process_upload(event)
    assert event == {}
    assert result.corrected is None and result.after is None
    assert result.before.summary.manual == 7
    view = web.view_data(web.WebState(result=result))
    assert view["download"] is None and not view["can_reveal"] and not view["ready"]


@pytest.mark.parametrize(
    "value",
    [
        None,
        [],
        "private",
        {},
        {"name": "PRIVATE.docx"},
        {"name": 3, "content": "abc"},
        {"name": "PRIVATE.docx", "content": "<private>"},
        {"name": "PRIVATE.docx", "content": "кирилиця"},
        {"name": "PRIVATE.pdf", "content": ""},
        {"name": "PRIVATE.docx", "content": "", "extra": "private"},
    ],
)
def test_malformed_events_are_discarded_with_safe_ukrainian_errors(value):
    state = web.WebState()
    web.accept_upload(state, value)
    assert state.result is None and not state.show_corrected
    assert state.error and "PRIVATE" not in state.error and "private" not in state.error
    assert "Traceback" not in state.error
    if isinstance(value, dict):
        assert value == {}


@pytest.mark.parametrize("extra,expected", [(0, "Не вдалося відкрити"), (1, "перевищує 20 МБ")])
def test_decoded_size_limit_is_inclusive(extra, expected):
    event = payload(b"x" * (MAX_FILE_SIZE_BYTES + extra))
    with pytest.raises(DocumentLoadError, match=expected):
        web.process_upload(event)
    assert event == {}


def test_unexpected_failure_clears_previous_result_and_does_not_log_private_exception(
    eom_fixtures, monkeypatch, capsys, caplog
):
    state = web.WebState(
        result=web.process_upload(payload(eom_fixtures["bad_r02"].read_bytes())),
        show_corrected=True,
    )

    def fail():
        raise RuntimeError("PRIVATE_DOCUMENT_CONTENT")

    monkeypatch.setattr(web, "load_ruleset", fail)
    event = payload(b"invalid")
    web.accept_upload(state, event)
    assert event == {} and state.result is None and not state.show_corrected
    assert "PRIVATE_DOCUMENT_CONTENT" not in (state.error + caplog.text + repr(capsys.readouterr()))


def test_copy_failure_preserves_report_without_source_or_download(eom_fixtures, monkeypatch):
    def fail(*args, **kwargs):
        raise FixError("PRIVATE_DOCUMENT_CONTENT")

    monkeypatch.setattr(web, "fix_document_bytes", fail)
    event = payload(eom_fixtures["bad_r02"].read_bytes())
    result = web.process_upload(event)
    assert event == {} and result.before.summary.errors == 1
    assert result.corrected is None and result.after is None
    assert result.copy_error and "PRIVATE_DOCUMENT_CONTENT" not in result.copy_error
    state = web.WebState(result=result)
    web.reveal_copy(state)
    assert not state.show_corrected and web.view_data(state)["download"] is None


def test_ui_transitions_use_current_counts_and_reset_every_retained_result(eom_fixtures):
    event = payload(eom_fixtures["bad_r02"].read_bytes())
    state = web.WebState()
    web.accept_upload(state, event)
    before = web.view_data(state)
    assert before["can_reveal"] and before["fixable"] == 1 and before["download"] is None
    assert "Знайдено 1 помилку" in before["report"]
    web.reveal_copy(state)
    after = web.view_data(state)
    assert after["ready"] and not after["can_reveal"]
    assert "Знайдено 0 помилок" in after["report"]
    assert "Перевірте самі" in after["report"] and "Висновків: 7" in after["report"]
    assert base64.b64decode(after["download"]) == state.result.corrected
    web.clear_result(state)
    assert web.view_data(state) == {"revision": 3, "error": None, "report": None}
    assert state.result is None and not state.show_corrected


def test_session_states_do_not_share_document_results(eom_fixtures):
    first, second = web.WebState(), web.WebState()
    web.accept_upload(first, payload(eom_fixtures["bad_r02"].read_bytes()))
    assert second.result is None
    web.accept_upload(second, payload(eom_fixtures["bad_r08"].read_bytes()))
    assert first.result.before.findings != second.result.before.findings
    web.clear_result(first)
    assert first.result is None and second.result.before.summary.errors == 1


def test_incomplete_checks_remain_manual_in_web_view():
    report = Report(
        ruleset_id="generated",
        ruleset_title="Згенеровані вимоги",
        unavailable_rules=("R03",),
        failed_rules=("R05",),
    )
    view = web.view_data(web.WebState(result=web.WebResult(report)))
    assert "Перевірку не завершено" in view["report"]
    assert view["download"] is None and not view["can_reveal"]
