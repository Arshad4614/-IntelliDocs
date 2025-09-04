import streamlit as st
import requests
from typing import Optional, Dict, Any

# Your backend URL (update if needed)
BASE_URL = "http://127.0.0.1:8000"


# -----------------------------
# APIResponse wrapper
# -----------------------------
class APIResponse:
    def __init__(self, response: Optional[requests.Response] = None, error: Optional[Exception] = None):
        self._resp = response
        self.error = error

    @property
    def ok(self) -> bool:
        return self._resp is not None and getattr(self._resp, "ok", False)

    @property
    def status_code(self) -> Optional[int]:
        return self._resp.status_code if self._resp is not None else None

    def json(self):
        if not self._resp:
            return None
        try:
            return self._resp.json()
        except Exception:
            return None

    @property
    def text(self) -> str:
        if self._resp is not None:
            try:
                return self._resp.text
            except Exception:
                return ""
        return str(self.error) if self.error else ""

    def raise_for_status(self):
        if self._resp is not None:
            return self._resp.raise_for_status()
        raise requests.HTTPError(str(self.error) or "No response")


# -----------------------------
# Helpers
# -----------------------------
def _auth_headers():
    token = st.session_state.get("token", None)
    if token:
        return {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    else:
        return {"Accept": "application/json"}


def _absolute(path: str) -> str:
    if not path.startswith("/"):
        path = "/" + path
    return f"{BASE_URL}{path}"


# -----------------------------
# HTTP Methods
# -----------------------------
def post(
    path: str,
    json: Optional[Dict[str, Any]] = None,
    files: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    token: str | None = None
) -> APIResponse:
    url = _absolute(path)
    hdrs = headers or _auth_headers()
    if token:
        hdrs["Authorization"] = f"Bearer {token}"

    try:
        if files:  # File upload case
            response = requests.post(url, files=files, headers=hdrs)
        else:  # Normal JSON request
            hdrs.setdefault("Content-Type", "application/json")
            response = requests.post(url, json=json, headers=hdrs)

        return APIResponse(response)
    except requests.RequestException as e:
        st.error(f"POST failed: {e}")
        return APIResponse(error=e)


def get(
    path: str,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    token: str | None = None
) -> APIResponse:
    url = _absolute(path)
    hdrs = headers or _auth_headers()
    if token:
        hdrs["Authorization"] = f"Bearer {token}"
    try:
        response = requests.get(url, params=params, headers=hdrs)
        return APIResponse(response)
    except requests.RequestException as e:
        st.error(f"GET failed: {e}")
        return APIResponse(error=e)


def delete(
    path: str,
    headers: Optional[Dict[str, str]] = None,
    token: str | None = None
) -> APIResponse:
    url = _absolute(path)
    hdrs = headers or _auth_headers()
    if token:
        hdrs["Authorization"] = f"Bearer {token}"
    try:
        response = requests.delete(url, headers=hdrs)
        return APIResponse(response)
    except requests.RequestException as e:
        st.error(f"DELETE failed: {e}")
        return APIResponse(error=e)
