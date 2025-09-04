import streamlit as st
from datetime import datetime
from state.auth import get_token, is_logged_in
from services.api import get, delete

st.set_page_config(page_title="Documents", page_icon="📄", layout="wide")
st.title("📄 Documents")
st.caption("Manage and delete your uploaded documents here. Uploads happen on the Chat page.")

# ---------------------- Helpers ----------------------
def _auth_headers():
    tok = get_token()
    return {"Authorization": f"Bearer {tok}"} if tok else {}

def list_docs():
    try:
        return get("/docs/list", headers=_auth_headers())
    except Exception as e:
        st.error(f"Error fetching documents: {e}")
        return None

def delete_doc(doc_id: str):
    try:
        return delete(f"/docs/delete/{doc_id}", headers=_auth_headers())
    except Exception as e:
        st.error(f"Error deleting document: {e}")
        return None

def clear_all_docs():
    try:
        return delete("/docs/clear", headers=_auth_headers())
    except Exception as e:
        st.error(f"Error clearing documents: {e}")
        return None

def fmt_bytes(n):
    try:
        n = int(n or 0)
    except Exception:
        return "—"
    for unit in ["B", "KB", "MB", "GB"]:
        if n < 1024.0:
            return f"{n:.0f} {unit}"
        n /= 1024.0
    return f"{n:.1f} TB"

def fmt_dt(x):
    try:
        return datetime.fromisoformat(str(x).replace("Z","")).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return x or "—"

# ---------------------- Auth Guard -------------------
if not is_logged_in():
    st.warning("Please sign in first.")
    st.stop()

# ---------------------- Actions ----------------------
colL, colR = st.columns([1,4])
with colL:
    if st.button("🔄 Refresh"):
        st.rerun()
with colR:
    st.write("")

# ---------------------- Fetch Documents ----------------
resp = list_docs()
items = []

if resp:
    if hasattr(resp, "ok") and resp.ok:
        try:
            data = resp.json()
            if isinstance(data, dict) and "documents" in data:
                items = data["documents"]
            elif isinstance(data, list):
                items = data
            else:
                items = []

            # ✅ Deduplicate silently by _id (or id)
            seen = set()
            deduped = []
            for it in items:
                if not isinstance(it, dict):
                    continue
                _id = it.get("_id") or it.get("id")
                if _id and _id in seen:
                    continue
                if _id:
                    seen.add(_id)
                deduped.append(it)
            items = deduped

        except Exception as e:
            st.error(f"Failed to parse document list: {e}")
            items = []
    elif isinstance(resp, list):
        items = resp
    else:
        st.error(getattr(resp, "text", "Failed to load documents."))

# ---------------------- Render Documents ----------------
if not items:
    st.info("No documents yet.")
else:
    def _key(it):
        if isinstance(it, dict):
            return it.get("created_at") or it.get("created") or ""
        return str(it) or ""

    items = [i for i in items if isinstance(i, dict)]
    items = sorted(items, key=_key, reverse=True)

    page_size = 10
    total = len(items)
    page = st.number_input(
        "Page",
        min_value=1,
        max_value=max(1, (total - 1)//page_size + 1),
        value=1,
        step=1
    )
    start = (page - 1) * page_size
    items = items[start:start+page_size]

    # Header
    h1, h2, h3, h4, h5, h6 = st.columns([3, 5, 2, 2, 3, 1])
    h1.write("**id**")
    h2.write("**filename**")
    h3.write("**chunks**")
    h4.write("**size**")
    h5.write("**created**")
    h6.write("**del**")

    # Rows
    for idx, it in enumerate(items):
        c1, c2, c3, c4, c5, c6 = st.columns([3, 5, 2, 2, 3, 1])
        _id = it.get("_id") or it.get("id") or ""
        _filename = it.get("filename") or "(unnamed)"
        _chunks = it.get("chunk_count", it.get("chunks", 0))
        _size = fmt_bytes(it.get("size_bytes") or it.get("size"))
        _created = fmt_dt(it.get("created_at") or it.get("created"))

        c1.code((_id[:10] + "…") if len(_id) > 10 else _id)
        c2.write(_filename)
        c3.write(_chunks)
        c4.write(_size)
        c5.write(_created)

        del_key = f"del_{_id}_{idx}"
        if c6.button("🗑️", key=del_key, help="Delete this document", use_container_width=True, disabled=not _id):
            r = delete_doc(_id)
            if getattr(r, "ok", False):
                st.success("Deleted.")
                st.rerun()
            else:
                st.error(f"Delete failed: {getattr(r, 'text', r)}")

    st.write("")
    if st.button("🧹 Clear All"):
        r = clear_all_docs()
        if getattr(r, "ok", False):
            st.success("All cleared.")
            st.rerun()
        else:
            st.error(f"Clear failed: {getattr(r, 'text', r)}")
