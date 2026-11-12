"""Local Oformleno demo. Run: streamlit run app/streamlit_app.py."""

from importlib.resources import files

import streamlit as st

from oformleno.web import WebState, accept_upload, clear_result, reveal_copy, view_data

st.set_page_config(page_title="Оформлено · Перевірка документа", layout="wide")

_ASSETS = files("oformleno").joinpath("web_assets")
_INTERFACE = st.components.v2.component(
    "oformleno_interface",
    html=_ASSETS.joinpath("interface.html").read_text(encoding="utf-8"),
    css=_ASSETS.joinpath("interface.css").read_text(encoding="utf-8"),
    js=_ASSETS.joinpath("interface.js").read_text(encoding="utf-8"),
    isolate_styles=False,
)


def _state() -> WebState:
    if "oformleno_result" not in st.session_state:
        st.session_state.oformleno_result = WebState()
    return st.session_state.oformleno_result


def _upload() -> None:
    payload = st.session_state.oformleno_interface.get("upload")
    if payload is not None:
        accept_upload(_state(), payload)


def _reveal() -> None:
    reveal_copy(_state())


def _reset() -> None:
    clear_result(_state())


_INTERFACE(
    key="oformleno_interface",
    data=view_data(_state()),
    on_upload_change=_upload,
    on_reveal_change=_reveal,
    on_reset_change=_reset,
)
