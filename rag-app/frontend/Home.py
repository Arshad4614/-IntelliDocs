import streamlit as st
from state.auth import is_logged_in, login, logout
from services.auth_service import signup_request
from utils.helper import toast_ok, toast_err

# Hide sidebar when user is not logged in
if not is_logged_in():
    st.markdown("""
        <style>
        [data-testid="collapsedControl"] {
            display: none
        }
        </style>
        """, unsafe_allow_html=True)

st.set_page_config(page_title="IntelliDocs", page_icon="🤖", layout="wide")

st.title("🤖 IntelliDocs")

backend_url = st.secrets.get("BACKEND_URL")
if backend_url:
    st.info(f"Backend: {backend_url}")

# ------------------- NOT LOGGED IN -------------------
if not is_logged_in():
    st.caption("Login or sign up to start chatting with your documents.")
    st.subheader("Account")

    tab_signin, tab_signup = st.tabs(["Sign in", "Sign up"])

    # ---------- SIGN IN ----------
    with tab_signin:
        with st.form("login_form", clear_on_submit=False):
            c1, c2 = st.columns(2)
            with c1:
                email_in = st.text_input("Email", autocomplete="username")
            with c2:
                pw_in = st.text_input("Password", type="password", autocomplete="current-password")
            submitted = st.form_submit_button("Sign in", type="primary")

        if submitted:
            if not email_in.strip() or not pw_in:
                st.error("Email and password required.")
            else:
                res = login(email_in.strip(), pw_in)
                if res:   # ✅ success
                    st.session_state["user_id"] = res.get("user_id")
                    st.session_state["username"] = res.get("username")
                    toast_ok("Logged in successfully ✅")
                    st.rerun()
                else:
                    toast_err("Login failed. Please check credentials.")

    # ---------- SIGN UP ----------
    with tab_signup:
        st.caption("Create a new account")
        with st.form("signup_form", clear_on_submit=False):
            c1, c2, c3 = st.columns(3)
            with c1:
                name_in = st.text_input("Full name")
            with c2:
                email_new = st.text_input("Email")
            with c3:
                pw_new = st.text_input("Password", type="password")
            submitted_su = st.form_submit_button("Sign up", type="secondary")

        if submitted_su:
            if not (name_in.strip() and email_new.strip() and pw_new):
                st.error("All fields are required.")
            else:
                res = signup_request(name_in.strip(), email_new.strip(), pw_new)
                if res:
                    login_res = login(email_new.strip(), pw_new)
                    if login_res:
                        st.session_state["user_id"] = login_res.get("user_id")
                        st.session_state["username"] = login_res.get("username")
                        toast_ok("Account created and logged in ✅")
                        st.rerun()
                    else:
                        toast_ok("Account created. Please sign in.")
                        st.rerun()
                else:
                    toast_err("Sign up failed.")

    st.markdown("---")
    st.write("Use the **Sign in / Sign up** tabs above to access your account.")

# ------------------- LOGGED IN -------------------
"""else:
    user = st.session_state.get("username", "(anonymous)")
    st.success(f"You are logged in as **{user}**")

    st.markdown("### 🚀 Quick Navigation")

    c1, c2, c3 = st.columns(3)

    with c1:
        if st.button("💬 Chat", use_container_width=True):
            st.switch_page("pages/current_chat.py")

    with c2:
        if st.button("📄 Documents", use_container_width=True):
            st.switch_page("pages/docs_management.py")

    with c3:
        if st.button("🧾 History", use_container_width=True):
            st.switch_page("pages/4_History.py")

    st.divider()
    if st.button("🚪 Logout", use_container_width=True):
        st.switch_page("pages/5_Logout.py")

    st.caption("RAG App v0.1.0")"""
