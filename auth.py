"""
auth.py — Auth, RBAC, session tokens, session timeout, login UI.
"""

import base64
import random
import time
from datetime import datetime

import streamlit as st

from config import DEMO_CREDENTIALS_NOTE, SESSION_TIMEOUT_MINUTES
from database import db_authenticate, get_db_connection, mark_onboarded, add_user


def authenticate(pg_url, username, password):
    return db_authenticate(pg_url, username, password)


def check_permission(role: str, action: str) -> bool:
    permissions = {
        "admin":   ["upload","delete","query","view_stats","manage_users"],
        "staff":   ["upload","delete","query"],
        "student": ["query"]
    }
    return action in permissions.get(role, [])


def _make_token(username, role, display) -> str:
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
                cur.execute("SELECT username,role,display_name,email,language,onboarded FROM users WHERE username=%s", (username,))
                row = cur.fetchone()
            if row:
                return {"username":row["username"],"role":row["role"],"display":row["display_name"],
                        "email":row["email"],"language":row["language"] or "en","onboarded":row["onboarded"]}
        finally:
            conn.close()
    except Exception:
        pass
    return None


def _init_captcha():
    a = random.randint(2, 9)
    b = random.randint(1, 9)
    st.session_state.captcha_a   = a
    st.session_state.captcha_b   = b
    st.session_state.captcha_ans = a + b


def check_session_timeout():
    """Returns True if session has timed out."""
    last = st.session_state.get('last_activity')
    if last is None:
        st.session_state.last_activity = time.time()
        return False
    if time.time() - last > SESSION_TIMEOUT_MINUTES * 60:
        return True
    st.session_state.last_activity = time.time()
    return False


def render_login(pg_url: str):
    if 'captcha_ans' not in st.session_state:
        _init_captcha()

    col_l, col_mid, col_r = st.columns([1, 2, 1])
    with col_mid:
        st.markdown("""
        <div style="text-align:center;padding:20px 0 10px;">
            <div style="font-size:3rem;">🎓</div>
            <h2 style="color:var(--teal);font-family:JetBrains Mono,monospace;margin:8px 0 4px;">College AI Assistant</h2>
            <p style="color:var(--text-3);font-size:0.82rem;">SRM Institute of Science and Technology · CS Department</p>
        </div>
        """, unsafe_allow_html=True)

        if st.session_state.get('remembered_user') and \
           st.session_state.get('remember_expires', 0) > datetime.now().timestamp():
            st.info(f"👋 Welcome back, **{st.session_state.remembered_user}**")

        st.markdown("<hr class='divider'>", unsafe_allow_html=True)

        # Sign In / Sign Up tabs
        tab_signin, tab_signup = st.tabs(["Sign In", "Sign Up"])

        # ── SIGN IN ──
        with tab_signin:
            with st.form("login_form", clear_on_submit=False):
                username = st.text_input("Username", placeholder="Enter your username")
                password = st.text_input("Password", placeholder="Enter your password", type="password")
                a = st.session_state.get('captcha_a', '?')
                b = st.session_state.get('captcha_b', '?')
                st.markdown(f"**Verification — What is `{a} + {b}` ?**")
                captcha_answer = st.number_input("Answer", min_value=0, max_value=99, step=1, key="captcha_input")
                remember       = st.checkbox("Keep me signed in for 7 days")
                submitted      = st.form_submit_button("Sign In →", use_container_width=True)

            if submitted:
                if not username or not password:
                    st.error("Please enter both username and password.")
                elif int(captcha_answer) != st.session_state.captcha_ans:
                    st.error("Wrong answer — please try again.")
                    _init_captcha()
                    st.rerun()
                else:
                    with st.spinner("Signing in..."):
                        user = authenticate(pg_url, username, password)
                    if user:
                        st.session_state.user           = user
                        st.session_state.authenticated  = True
                        st.session_state.last_activity  = time.time()
                        st.session_state.language       = user.get('language', 'en')
                        st.query_params["sid"] = _make_token(user["username"], user["role"], user["display"])
                        if remember:
                            st.session_state.remembered_user  = username
                            st.session_state.remember_expires = datetime.now().timestamp() + 7 * 24 * 3600
                        st.rerun()
                    else:
                        st.error("Invalid username or password.")
                        _init_captcha()

            st.markdown("<hr class='divider'>", unsafe_allow_html=True)
            with st.expander("Demo credentials"):
                st.markdown(DEMO_CREDENTIALS_NOTE)

        # ── SIGN UP ──
        with tab_signup:
            st.info("New student accounts are set up as **Student** role. Contact an Admin to get Staff or Admin access.")
            with st.form("signup_form", clear_on_submit=True):
                su_display  = st.text_input("Full Name", placeholder="e.g. Imran Mohamed")
                su_username = st.text_input("Username", placeholder="Choose a username (no spaces)")
                su_email    = st.text_input("Email (optional)", placeholder="your@email.com")
                su_password = st.text_input("Password", type="password", placeholder="Min 6 characters")
                su_confirm  = st.text_input("Confirm Password", type="password")
                su_submit   = st.form_submit_button("Create Account →", use_container_width=True)

            if su_submit:
                if not su_display or not su_username or not su_password:
                    st.error("Full name, username and password are required.")
                elif su_password != su_confirm:
                    st.error("Passwords do not match.")
                elif len(su_password) < 6:
                    st.error("Password must be at least 6 characters.")
                elif " " in su_username:
                    st.error("Username cannot contain spaces.")
                else:
                    ok, msg = add_user(pg_url, su_username, su_password, "student", su_display, su_email)
                    if ok:
                        st.success(f"Account created! You can now sign in with username: **{su_username}**")
                    else:
                        st.error(msg)


def restore_session(pg_url: str):
    if not st.session_state.get('authenticated'):
        token = st.query_params.get("sid", "")
        if token:
            restored = _decode_token(token, pg_url)
            if restored:
                st.session_state.user           = restored
                st.session_state.authenticated  = True
                st.session_state.last_activity  = time.time()
                st.session_state.language       = restored.get('language', 'en')


def render_onboarding(pg_url: str):
    """First-time user welcome tour."""
    user  = st.session_state.user
    step  = st.session_state.get('onboard_step', 1)
    steps = [
        ("👋 Welcome!", f"Hi {user['display']}! Welcome to the College AI Assistant. Let's show you around."),
        ("💬 Chat", "Ask any question about college documents. The AI will search through uploaded PDFs and give accurate answers."),
        ("🎤 Voice Input", "Click the microphone button to speak your question instead of typing. Works on Chrome and Edge."),
        ("📄 Export Answers", "Every AI answer can be saved as a PDF or shared on Telegram using the buttons below each response."),
        ("🌐 Languages", "You can switch between English, Tamil, and Hindi using the language selector in the chat area."),
        ("🚀 You're all set!", "Start by asking a question or clicking one of the suggestion chips below the chat!"),
    ]

    total = len(steps)
    title, desc = steps[step - 1]

    st.markdown(f"""
    <div class="tour-card">
        <div class="tour-step">Step {step} of {total}</div>
        <div class="tour-title">{title}</div>
        <div class="tour-desc">{desc}</div>
        <div style="margin-top:20px;display:flex;justify-content:center;gap:6px;">
            {''.join(['<div style="width:8px;height:8px;border-radius:50%;background:' + ('var(--teal)' if i+1==step else 'var(--border-2)') + ';display:inline-block;"></div>' for i in range(total)])}
        </div>
    </div>
    """, unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        if step > 1:
            if st.button("← Back", use_container_width=True):
                st.session_state.onboard_step = step - 1
                st.rerun()
    with c2:
        if step < total:
            if st.button("Next →", use_container_width=True):
                st.session_state.onboard_step = step + 1
                st.rerun()
        else:
            if st.button("Get Started! 🚀", use_container_width=True):
                mark_onboarded(pg_url, user['username'])
                st.session_state.user['onboarded'] = True
                st.session_state.onboard_step = 1
                st.rerun()