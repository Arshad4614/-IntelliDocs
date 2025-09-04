from __future__ import annotations
import streamlit as st
from typing import List, Dict, Any, Optional

# Consistent keys across project
_TOKEN_KEY = "token"
_USER_KEY = "username"
_MSGS_KEY = "messages"   # legacy key
_CHAT_MSGS_KEY = "chat_messages"  # preferred
_CHAT_CONV_KEY = "chat_conversation_id"
_SELECTED_CONV_KEY = "selected_conv_id"


class SessionManager:
    # -----------------------------
    # Auth
    # -----------------------------
    @staticmethod
    def is_logged_in() -> bool:
        return bool(st.session_state.get(_TOKEN_KEY))

    @staticmethod
    def get_token() -> Optional[str]:
        return st.session_state.get(_TOKEN_KEY)

    @staticmethod
    def set_token(token: Optional[str]):
        if token:
            st.session_state[_TOKEN_KEY] = token
        else:
            st.session_state.pop(_TOKEN_KEY, None)

    @staticmethod
    def set_username(username: Optional[str]):
        if username:
            st.session_state[_USER_KEY] = username
        else:
            st.session_state.pop(_USER_KEY, None)

    # -----------------------------
    # Chat messages
    # -----------------------------
    @staticmethod
    def get_messages() -> List[Dict[str, Any]]:
        if _CHAT_MSGS_KEY not in st.session_state:
            st.session_state[_CHAT_MSGS_KEY] = []
        return st.session_state[_CHAT_MSGS_KEY]

    @staticmethod
    def add_message(role: str, content: str):
        msgs = SessionManager.get_messages()
        msgs.append({"role": role, "content": content})

    @staticmethod
    def clear_messages():
        for k in (_MSGS_KEY, _CHAT_MSGS_KEY):
            st.session_state.pop(k, None)

    # -----------------------------
    # Global clear
    # -----------------------------
    @staticmethod
    def clear_all():
        """Logout-like cleanup (auth + UI caches + chat)."""
        for key in (
            _TOKEN_KEY,
            _USER_KEY,
            _MSGS_KEY,
            _CHAT_MSGS_KEY,
            _CHAT_CONV_KEY,
            _SELECTED_CONV_KEY,
            "selected_conversation_title",
        ):
            st.session_state.pop(key, None)
