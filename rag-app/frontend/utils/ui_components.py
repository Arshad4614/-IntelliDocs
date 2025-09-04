from __future__ import annotations
import streamlit as st
from typing import Callable, Iterable, Optional, Dict, Any
from utils.helper import check_file_size, safe_markdown  # fixed import

# ---------- App chrome ----------
def header(title: str, subtitle: str | None = None):
    st.title(title)
    if subtitle:
        st.caption(subtitle)

def sidebar_nav(items: Iterable[tuple[str, str]]):
    """
    items: list of tuples (label, page_path_hint)
    This just renders links as buttons; adapt to your routing preference.
    """
    st.sidebar.header("Navigation")
    for label, href in items:
        st.sidebar.write(f"- [{label}]({href})")

# ---------- Chat ----------
def chat_message(role: str, content: str, avatar: str | None = None):
    """Render a single chat message with safe markdown + avatar."""
    with st.chat_message(role, avatar=avatar or ("👤" if role == "user" else "🤖")):
        safe_markdown(content)

# ---------- Upload card ----------
def upload_card(
    *,
    label: str = "Upload a PDF/TXT file",
    types: list[str] = ["pdf", "txt"],
    max_mb: int = 50,
    on_upload: Optional[Callable[[Any], Dict[str, Any] | Any]] = None,
):
    """
    Renders a compact uploader with size guard and an Upload button.
    If on_upload is provided, it will be called with the file object.
    Returns whatever on_upload returns, or None, or {"error": "..."}.
    """
    file = st.file_uploader(label, type=types)
    upload_btn = st.button("📤 Upload", disabled=(file is None))

    if upload_btn and file:
        if not check_file_size(file, max_mb=max_mb):
            return {"error": f"File too large (>{max_mb} MB)"}
        if on_upload:
            return on_upload(file)
    return None

# ---------- Confirmation pattern ----------
def confirm_row(action_label: str, key: str) -> bool:
    """
    Simple 2-step confirmation: press action -> shows confirm checkbox -> press again.
    Returns True when confirmed.
    """
    step1 = st.button(action_label, key=f"{key}_btn")
    if step1:
        st.session_state[f"{key}_confirm"] = True

    if st.session_state.get(f"{key}_confirm"):
        st.warning("Confirm?")
        col1, col2 = st.columns(2)
        with col1:
            yes = st.button("Yes", key=f"{key}_yes")
        with col2:
            no = st.button("No", key=f"{key}_no")

        if yes:
            st.session_state.pop(f"{key}_confirm", None)
            return True
        if no:
            st.session_state.pop(f"{key}_confirm", None)
    return False
