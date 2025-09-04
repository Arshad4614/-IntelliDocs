from __future__ import annotations
import json
import mimetypes
import streamlit as st
from typing import Optional

# ---------- File helpers ----------
def bytes_to_mb(n: int) -> float:
    return round(n / (1024 * 1024), 2)

def check_file_size(file, max_mb: int = 50) -> bool:
    """Return True if file is within limit, else show error and return False."""
    if not file:
        return False
    # support both .size and .getbuffer()
    size_bytes = getattr(file, "size", None) or len(file.getbuffer())
    size_ok = size_bytes <= max_mb * 1024 * 1024
    if not size_ok:
        st.error(f"File too large: {bytes_to_mb(size_bytes)} MB (max {max_mb} MB).")
    return size_ok

def guess_mime(filename: str) -> str:
    return mimetypes.guess_type(filename)[0] or "application/octet-stream"

# ---------- UI helpers ----------
def _toast(msg: str, icon: str, fallback: str = "info"):
    """Internal helper to use st.toast if available, else fallback."""
    if hasattr(st, "toast"):
        st.toast(msg, icon=icon)
    else:
        if fallback == "success":
            st.success(msg)
        elif fallback == "warning":
            st.warning(msg)
        elif fallback == "error":
            st.error(msg)
        else:
            st.info(msg)

def toast_ok(msg: str):
    _toast(msg, "✅", fallback="success")

def toast_warn(msg: str):
    _toast(msg, "⚠️", fallback="warning")

def toast_err(msg: str):
    _toast(msg, "❌", fallback="error")

def safe_markdown(text: str, *, placeholder="(no content)"):
    st.markdown(str(text).strip() if (text and str(text).strip()) else placeholder)

# ---------- Streaming helpers ----------
def default_chunk_decoder(line: str) -> Optional[str]:
    """
    Handles plain text, JSON lines (keys: delta/content/text/answer/message),
    and SSE-style 'data: ...' lines.
    """
    s = line.strip()
    if not s:
        return None
    if s.startswith("data:"):
        s = s[5:].strip()
    try:
        obj = json.loads(s)
        for key in ("delta", "content", "text", "answer", "message"):
            if isinstance(obj.get(key), str):
                return obj[key]
        # fallback: any string value
        for v in obj.values():
            if isinstance(v, str):
                return v
        return None
    except Exception:
        return s

# ---------- Misc ----------
def divider(label: str | None = None):
    st.divider()
    if label:
        st.caption(label)

def is_valid_json(text: str) -> bool:
    try:
        json.loads(text)
        return True
    except json.JSONDecodeError:
        return False
