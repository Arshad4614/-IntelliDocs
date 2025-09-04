import streamlit as st
from datetime import datetime, timezone
from services.api import post
import requests

SESSION_TOKEN_KEY = "token"

# -----------------------------
# Helpers (normalization)
# -----------------------------
def _norm_name(name: str) -> str:
    return (name or "").strip()

def _norm_email(email: str) -> str:
    return (email or "").strip().lower()

def _norm_password(password: str) -> str:
    return (password or "").strip()

# -----------------------------
# SIGNUP
# -----------------------------
def signup_request(name: str, email: str, password: str):
    """
    Low-level request that returns APIResponse.
    """
    payload = {
        "name": _norm_name(name),
        "email": _norm_email(email),
        "password": _norm_password(password),
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        response = post("/users/signup", json=payload)
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as e:
        st.error(f"Signup failed: {e}")
        return None

def signup(name: str, email: str, password: str) -> bool:
    r = signup_request(name, email, password)
    return r.ok if r else False

# -----------------------------
# LOGIN
# -----------------------------
def login(email: str, password: str) -> bool:
    """
    Calls /users/login with {email, password}.
    On success, stores JWT in st.session_state["token"].
    """
    payload = {
        "email": _norm_email(email),
        "password": _norm_password(password),
    }

    try:
        r = post("/users/login", json=payload)
        r.raise_for_status()
        if r.ok:
            data = r.json() or {}
            token = data.get("access_token")
            if token:
                st.session_state[SESSION_TOKEN_KEY] = token
                return True
    except requests.exceptions.RequestException as e:
        st.error(f"Login failed: {e}")

    return False

def get_token() -> str | None:
    return st.session_state.get(SESSION_TOKEN_KEY)

# -----------------------------
# LOGOUT
# -----------------------------
def logout():
    """
    Revokes current session on the backend, then clears local session state.
    """
    token = st.session_state.get(SESSION_TOKEN_KEY)
    if token:
        try:
            post("/sessions/revoke/current", json={}, token=token)
        except Exception:
            pass  # even if API call fails, clear session anyway

    # Clear all relevant session keys
    for k in (
        SESSION_TOKEN_KEY,
        "messages", "chat_msgs", "chat_messages",
        "conversation_id", "chat_conversation_id",
        "selected_conv_id", "selected_conversation_title",
        "user"
    ):
        st.session_state.pop(k, None)

    st.rerun()
