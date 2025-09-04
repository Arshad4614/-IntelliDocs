import streamlit as st
from datetime import datetime, timezone
from services.api import post, APIResponse

_TOKEN_KEY = "token"
_USER_KEY = "username"  # we'll store the email here for simplicity


# -----------------------------
# Session helpers
# -----------------------------
def _save_session(token: str | None, email: str | None = None):
    if token:
        st.session_state[_TOKEN_KEY] = token
    if email:
        st.session_state[_USER_KEY] = email

def get_token() -> str | None: 
    return st.session_state.get(_TOKEN_KEY)

def is_logged_in() -> bool: 
    return bool(st.session_state.get(_TOKEN_KEY))


# -----------------------------
# Token extraction (fallback)
# -----------------------------
def _extract_token(resp: APIResponse):
    if not resp or not resp.ok:
        return None
    data = resp.json() or {}
    return (
        data.get("access_token")
        or data.get("token")
        or (data.get("data") or {}).get("access_token")
        or (data.get("data") or {}).get("token")
    )


# -----------------------------
# API wrappers (clean return)
# -----------------------------
def login(email: str, password: str):
    """POST /users/login with email+password"""
    r = post("/users/login", json={"email": email, "password": password})
    if r and r.ok:
        data = r.json() or {}
        tok = data.get("access_token") or _extract_token(r)
        if tok:
            _save_session(tok, email)
            return {
                "user_id": data.get("user_id"),
                "username": data.get("username") or email
            }
    return None


def signup(name: str, email: str, password: str) -> bool:
    """POST /users/signup with name, email, password, is_active, created_at"""
    body = {
        "name": name,
        "email": email,
        "password": password,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    r = post("/users/signup", json=body)
    return bool(r and r.ok)


# -----------------------------
# Logout
# -----------------------------
def logout():
    """Call backend logout, then clear session state"""
    token = st.session_state.get(_TOKEN_KEY)
    if token:
        try:
            post("/sessions/revoke/current", token=token)
        except Exception:
            pass  # ignore errors

    for k in (
        _TOKEN_KEY, _USER_KEY,
        "messages", "chat_msgs", "chat_messages",
        "conversation_id", "chat_conversation_id",
        "selected_conv_id", "selected_conversation_id", "selected_conversation_title",
        "user"
    ):
        st.session_state.pop(k, None)
