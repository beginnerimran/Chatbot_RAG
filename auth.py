"""
auth.py — Authentication, role-based access control, session tokens, and Login UI.
"""

import base64
import random
import time
from datetime import datetime

import streamlit as st

from config import DEMO_CREDENTIALS_NOTE
from database import db_authenticate, get_db_connection


# ─────────────────────────────────────────────
# RBAC
# ─────────────────────────────────────────────
def authenticate(pg_url: str, username: str, password: str):
    return db_authenticate(pg_url, username, password)


def check_permission(role: str, action: str) -> bool:
    permissions = {
        "admin":   ["upload", "delete", "query", "view_stats"],
        "staff":   ["upload", "delete", "query"],
        "student": ["query"]
    }
    return action in permissions.get(role, [])


# ─────────────────────────────────────────────
# SESSION TOKEN — keeps user logged in on refresh
# ─────────────────────────────────────────────
def _make_token(username: str, role: str, display: str) -> str:
    payload = f"{username}|{role}|{display}|{int(time.time())}"
    return base64.urlsafe_b64encode(payload.encode()).decode()


def _decode_token(token: str, pg_url: str):
    try:
        payload = base64.urlsafe_b64decode(token.encode()).decode()
        parts   = payload.split("|")
        if len(parts) < 4:
            return None
        username, role, display, ts = parts[0], parts[1], parts[2], parts[3]
        if time.time() - float(ts) > 7 * 24 * 3600:
            return None
        conn = get_db_connection(pg_url)
        if not conn:
            return None
        try:
            import psycopg2.extras
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("SELECT username, role, display_name FROM users WHERE username=%s", (username,))
                row = cur.fetchone()
            if row:
                return {"username": row["username"], "role": row["role"], "display": row["display_name"]}
        finally:
            conn.close()
    except Exception:
        pass
    return None


# ─────────────────────────────────────────────
# CAPTCHA
# ─────────────────────────────────────────────
def _init_captcha():
    a = random.randint(2, 9)
    b = random.randint(1, 9)
    st.session_state.captcha_a   = a
    st.session_state.captcha_b   = b
    st.session_state.captcha_ans = a + b


# ─────────────────────────────────────────────
# LOGIN UI — pure Streamlit widgets (no raw HTML)
# ─────────────────────────────────────────────
def render_login(pg_url: str):
    if 'captcha_ans' not in st.session_state:
        _init_captcha()

    # ── Centered layout ──
    col_l, col_mid, col_r = st.columns([1, 2, 1])
    with col_mid:

        # Header
        st.markdown("## 🎓 College AI Assistant")
        st.markdown("##### // SRM Institute — CS Department")
        st.markdown("---")

        # Welcome back message
        if st.session_state.get('remembered_user') and \
           st.session_state.get('remember_expires', 0) > datetime.now().timestamp():
            st.info(f"👋 Welcome back, **{st.session_state.remembered_user}** — enter your password to continue.")

        # ── Login form ──
        with st.form("login_form", clear_on_submit=False):
            st.markdown("#### Sign In")

            username = st.text_input("👤 Username", placeholder="Enter your username")
            password = st.text_input("🔒 Password", placeholder="Enter your password", type="password")

            # CAPTCHA
            a = st.session_state.get('captcha_a', '?')
            b = st.session_state.get('captcha_b', '?')
            st.markdown(f"**🤖 Prove you're human — What is `{a} + {b}` ?**")
            captcha_answer = st.number_input("Your answer", min_value=0, max_value=99,
                                              step=1, key="captcha_input")

            remember = st.checkbox("Remember me for 7 days")

            submitted = st.form_submit_button("Sign In →", use_container_width=True)

        # ── Process login ──
        if submitted:
            if not username or not password:
                st.error("⚠️ Please enter both username and password.")
            elif int(captcha_answer) != st.session_state.captcha_ans:
                st.error("🤖 Wrong answer! Please try again.")
                _init_captcha()
                st.rerun()
            else:
                with st.spinner("Signing in..."):
                    user = authenticate(pg_url, username, password)
                if user:
                    st.session_state.user          = user
                    st.session_state.authenticated = True
                    st.query_params["sid"] = _make_token(user["username"], user["role"], user["display"])
                    if remember:
                        st.session_state.remembered_user  = username
                        st.session_state.remember_expires = datetime.now().timestamp() + 7 * 24 * 3600
                    st.rerun()
                else:
                    st.error("❌ Invalid username or password.")
                    _init_captcha()

        st.markdown("---")
        with st.expander("📋 Demo credentials"):
            st.markdown(DEMO_CREDENTIALS_NOTE)


def restore_session(pg_url: str):
    """Try to restore session from URL token on page refresh."""
    if not st.session_state.get('authenticated'):
        token = st.query_params.get("sid", "")
        if token:
            restored = _decode_token(token, pg_url)
            if restored:
                st.session_state.user          = restored
                st.session_state.authenticated = True