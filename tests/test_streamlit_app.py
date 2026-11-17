"""Run the actual app with Streamlit's component-event protocol and session state."""

import base64
import json
from pathlib import Path

from docx import Document
from docx.shared import Pt
from streamlit.components.v2.bidi_component.main import _make_trigger_id
from streamlit.proto.WidgetStates_pb2 import WidgetStates
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py"


def event(app, kind, value):
    component = app.get("bidi_component")[0]
    states = WidgetStates()
    trigger = states.widgets.add()
    trigger.id = _make_trigger_id(component.proto.id, "events")
    trigger.json_trigger_value = json.dumps([{"event": kind, "value": value}])
    return app._run(states)


def view(app):
    assert not app.exception
    return json.loads(app.get("bidi_component")[0].proto.json)


def test_initial_app_is_ukrainian_with_no_retained_uploads():
    app = AppTest.from_file(str(APP)).run()
    assert view(app)["report"] is None
    assert app.session_state.oformleno_result.result is None
    assert app.session_state.oformleno_interface.upload is None


def test_real_component_handles_ordinary_text_and_clears_upload(eom_fixtures, tmp_path):
    document = Document(eom_fixtures["good"])
    paragraph = document.paragraphs[0]
    paragraph.style = "Normal"
    paragraph.runs[0].font.name = "Calibri"
    paragraph.runs[0].font.size = Pt(12)
    paragraph.paragraph_format.line_spacing = 1
    source = tmp_path / "generated.docx"
    document.save(source)
    original = source.read_bytes()
    encoded = base64.b64encode(original).decode("ascii")
    app = AppTest.from_file(str(APP)).run()
    event(
        app, "upload", {"name": "generated.docx", "content": encoded, "body_text_mode": "ordinary"}
    )
    result = app.session_state.oformleno_result.result
    assert result.before.summary.errors == 3 and result.after.summary.errors == 0
    assert result.before.body_text_mode == result.after.body_text_mode == "ordinary"
    assert "Звичайні абзаци — основний текст" in view(app)["report"]
    assert app.session_state.oformleno_interface.upload is None
    assert encoded not in repr(app.session_state.to_dict())
    assert all(encoded not in str(widget) for widget in app._session_state.get_widget_states())
    event(app, "reveal", True)
    assert base64.b64decode(view(app)["download"]) == result.corrected != original
    assert source.read_bytes() == original
    event(app, "reset", True)
    assert view(app)["report"] is None


def test_real_component_upload_reveal_download_bytes_and_reset(eom_fixtures):
    app = AppTest.from_file(str(APP)).run()
    original = eom_fixtures["bad_r02"].read_bytes()
    encoded = base64.b64encode(original).decode("ascii")
    event(app, "upload", {"name": "PRIVATE_IDENTIFIER.docx", "content": encoded})
    initial = view(app)
    assert initial["can_reveal"] and initial["download"] is None
    assert "Знайдено 1 помилку" in initial["report"]
    assert app.session_state.oformleno_interface.upload is None
    assert encoded not in repr(app.session_state.to_dict())
    assert "PRIVATE_IDENTIFIER" not in repr(app.session_state.to_dict())
    for widget in app._session_state.get_widget_states():
        assert encoded not in str(widget) and "PRIVATE_IDENTIFIER" not in str(widget)
    event(app, "reveal", True)
    ready = view(app)
    assert ready["ready"] and "Знайдено 0 помилок" in ready["report"]
    corrected = base64.b64decode(ready["download"], validate=True)
    assert (
        corrected != original and corrected == app.session_state.oformleno_result.result.corrected
    )
    event(app, "reset", True)
    assert view(app)["report"] is None and app.session_state.oformleno_result.result is None
    app.run()
    assert view(app)["report"] is None


def test_invalid_input_clears_stale_copy_and_does_not_expose_filename(eom_fixtures):
    app = AppTest.from_file(str(APP)).run()
    event(
        app,
        "upload",
        {
            "name": "generated.docx",
            "content": base64.b64encode(eom_fixtures["bad_r02"].read_bytes()).decode("ascii"),
        },
    )
    event(app, "reveal", True)
    event(app, "upload", {"name": "PRIVATE_IDENTIFIER.docx", "content": "bm90LWRvY3g="})
    current = view(app)
    assert current["report"] is None and current["error"]
    assert "PRIVATE_IDENTIFIER" not in json.dumps(current)
    assert app.session_state.oformleno_result.result is None
    assert app.session_state.oformleno_interface.upload is None


def test_separate_apptest_sessions_are_isolated(eom_fixtures):
    first = AppTest.from_file(str(APP)).run()
    second = AppTest.from_file(str(APP)).run()
    event(
        first,
        "upload",
        {
            "name": "generated.docx",
            "content": base64.b64encode(eom_fixtures["bad_r08"].read_bytes()).decode("ascii"),
        },
    )
    assert view(first)["report"] and view(second)["report"] is None
    second.run()
    assert second.session_state.oformleno_result.result is None
