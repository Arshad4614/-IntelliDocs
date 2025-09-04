import streamlit as st
from state.auth import logout

st.set_page_config(page_title="Logout", page_icon="🚪")
st.title("🚪 Logout")

st.info("You’re about to log out of your session.")

# clear extra session keys
for key in ("chat_messages", "chat_conversation_id", "selected_conv_id", "selected_conversation_title"):
    st.session_state.pop(key, None)

if st.button("✅ Logout now", type="primary"):
    logout()
    st.query_params.clear()
    st.switch_page("Home.py")   # ✅ direct redirect to Home after logout
    st.rerun()                  # ✅ ensure refresh immediately

if st.button("❌ Cancel"):
    st.info("Logout cancelled.")
