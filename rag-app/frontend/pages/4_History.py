import streamlit as st
from services.api import get, delete
from state.auth import get_token, is_logged_in

st.set_page_config(page_title="History", page_icon="🧾", layout="wide")
st.title("🧾 Chat History")

# ---------------- Helpers ----------------
def _auth_headers():
    tok = get_token()
    return {"Authorization": f"Bearer {tok}"} if tok else {}

def fetch_conversations():
    try:
        resp = get("/chat/conversations", headers=_auth_headers())
        if resp and getattr(resp, "ok", False):
            return resp.json().get("conversations", [])
    except Exception as e:
        st.error(f"Error fetching conversations: {e}")
    return []

def delete_conversation(conv_id: str):
    try:
        resp = delete(f"/chat/history/conversation?conversation_id={conv_id}", headers=_auth_headers())
        return resp and getattr(resp, "ok", False)
    except Exception as e:
        st.error(f"Error deleting conversation: {e}")
        return False

def clear_all_conversations():
    try:
        resp = delete("/chat/clear", headers=_auth_headers())
        return resp and getattr(resp, "ok", False)
    except Exception as e:
        st.error(f"Error clearing history: {e}")
        return False

# ---------------- Auth Guard ----------------
if not is_logged_in():
    st.warning("⚠️ Please login first to view history.")
    st.stop()

# ---------------- Load Conversations ----------------
conversations = fetch_conversations()

if not conversations:
    st.info("No chat history found yet.")
    st.stop()

st.caption(f"Total conversations: **{len(conversations)}**")
st.markdown("---")

# ---------------- Show Each Conversation ----------------
for conv in conversations:
    with st.container():
        cols = st.columns([3, 1, 1])
        with cols[0]:
            st.write(f"**{conv.get('title') or 'Untitled'}**")
            st.caption(f"Created at: {conv.get('created_at')}")
            st.caption(f"ID: `{conv.get('conversation_id')}`")
        with cols[1]:
            if st.button("💬 Open", key=f"open-{conv['conversation_id']}", use_container_width=True):
                st.query_params["conv_id"] = conv["conversation_id"]  # ✅ set query param
                st.switch_page("pages/current_chat.py")               # ✅ go to chat page
        with cols[2]:
            if st.button("🗑 Delete", key=f"del-{conv['conversation_id']}", use_container_width=True):
                if delete_conversation(conv["conversation_id"]):
                    st.success("Conversation deleted ✅")
                    st.rerun()

st.divider()
# ---------------- Clear All ----------------
if st.button("🗑 Clear All History", type="primary", use_container_width=True):
    if clear_all_conversations():
        st.success("All history cleared ✅")
        st.rerun()
