import streamlit as st
from state.auth import get_token, is_logged_in
from services.api import get, post, delete

st.set_page_config(
    page_title="Current Chat",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ---------------- CSS for Chat Bubbles ----------------
st.markdown("""
    <style>
    .chat-bubble-user {
        float: right; clear: both;
        background: #DCF8C6;
        padding: 10px 12px; border-radius: 10px;
        margin: 6px; max-width: 70%;
        color: #000; font-size: 15px;
    }
    .chat-bubble-assistant {
        float: left; clear: both;
        background: #F1F0F0;
        padding: 10px 12px; border-radius: 10px;
        margin: 6px; max-width: 70%;
        color: #000; font-size: 15px;
    }
    </style>
""", unsafe_allow_html=True)


# ---------------- Helpers ----------------
def _auth_headers():
    token = get_token()
    return {"Authorization": f"Bearer {token}"} if token else {}

def upload_to_backend(file):
    try:
        files = {"file": (file.name, file.getbuffer(), file.type or "application/pdf")}
        return post("/docs/upload", files=files, headers=_auth_headers())
    except Exception as e:
        st.error(f"File upload error: {e}")
        return None

def ask_backend(question: str, conversation_id: str | None):
    payload = {"question": question}
    if conversation_id:
        payload["conversation_id"] = conversation_id
    try:
        return post("/chat/send", json=payload, headers=_auth_headers())
    except Exception as e:
        st.error(f"Error asking backend: {e}")
        return None

def api_get_conversation(conv_id: str):
    try:
        return get(f"/chat/history/{conv_id}", headers=_auth_headers())
    except Exception as e:
        st.error(f"Error fetching conversation: {e}")
        return None

def api_get_conversations():
    try:
        return get("/chat/conversations", headers=_auth_headers())
    except Exception as e:
        st.error(f"Error fetching conversations: {e}")
        return None


# ---------------- Auth Guard ----------------
if not is_logged_in():
    st.error("⛔ Please sign in to use Chat.")
    st.stop()

# ---------------- Session State ----------------
ss = st.session_state
ss.setdefault("chat_messages", [])
ss.setdefault("chat_conversation_id", None)
ss.setdefault("last_resp", None)

# ---------------- Sidebar ----------------
with st.sidebar:
    st.title("💬 Chat History")

    if st.button("➕ New Chat", use_container_width=True):
        ss.chat_conversation_id = None
        ss.chat_messages = []
        ss.last_resp = None
        st.rerun()

    convs = api_get_conversations()
    conv_list = convs.json().get("conversations", []) if convs and getattr(convs, "ok", False) else []

    if conv_list:
        for conv in conv_list:
            conv_id = conv.get("conversation_id")
            title = conv.get("title") or "Untitled"
            active = (conv_id == ss.chat_conversation_id)

            if st.button(f"{'✅ ' if active else ''}{title}", key=f"open-{conv_id}", use_container_width=True):
                ss.chat_conversation_id = conv_id
                conv_resp = api_get_conversation(conv_id)
                if conv_resp and getattr(conv_resp, "ok", False):
                    ss.chat_messages = conv_resp.json().get("messages", [])
                else:
                    ss.chat_messages = []
                st.rerun()
    else:
        st.caption("No conversations yet. Start a new chat!")

# ---------------- Main Chat Area ----------------
st.title("💬 Chat with your documents")

# --- Display Chat Messages ---
for m in ss.chat_messages:
    if m["role"] == "user":
        st.markdown(f"<div class='chat-bubble-user'>{m['content']}</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='chat-bubble-assistant'>{m['content']}</div>", unsafe_allow_html=True)

# ---------------- Input Bar with Upload ----------------
col1, col2 = st.columns([1, 8])

with col1:
    uploaded_file = st.file_uploader("", type=["pdf"], label_visibility="collapsed")

with col2:
    prompt = st.chat_input("Type your question here…")

# --- Handle Upload ---
if uploaded_file:
    resp = upload_to_backend(uploaded_file)
    if resp and getattr(resp, "ok", False):
        ss.chat_messages.append({"role": "user", "content": f"📂 Uploaded: {uploaded_file.name}"})
        st.success(f"✅ Uploaded: {uploaded_file.name}")
        st.rerun()
    else:
        st.error(f"Upload failed: {getattr(resp, 'text', resp)}")

# --- Handle Question ---
if prompt:
    resp = ask_backend(prompt, ss.chat_conversation_id)
    if resp and getattr(resp, "ok", False):
        data = resp.json()
        ss.chat_conversation_id = data.get("conversation_id", ss.chat_conversation_id)
        ss.chat_messages.append({"role": "user", "content": prompt})
        ss.chat_messages.append({"role": "assistant", "content": data.get("answer", "⚠️ No answer returned")})
        ss.last_resp = resp
        st.rerun()

# ---------------- Sources ----------------
if ss.chat_messages and ss.last_resp:
    sources = ss.last_resp.json().get("sources", [])
    if sources:
        st.markdown("#### Sources")
        for s in sources:
            st.caption(f"- {s['filename']} (score {s['score']:.2f}) → `{s['snippet'][:150]}...`")
