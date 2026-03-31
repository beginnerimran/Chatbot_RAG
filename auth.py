"""
auth.py — Auth, RBAC, session tokens, session timeout, login UI.
Login page styled to match SRM Student Portal.
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
    st.session_state.captcha_error = False


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

    # ── Full-page SRM portal layout ──
    st.markdown("""
    <div class="srm-portal-page">

        <!-- SRM Logo Header -->
        <div class="srm-logo-header">
            <div class="srm-emblem">
                <svg width="64" height="64" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <circle cx="32" cy="32" r="30" fill="#1a3a7a" stroke="#c8a84b" stroke-width="3"/>
                    <circle cx="32" cy="32" r="24" fill="none" stroke="#c8a84b" stroke-width="1"/>
                    <text x="32" y="38" text-anchor="middle" fill="#ffffff" font-size="14"
                          font-weight="bold" font-family="serif">SRM</text>
                </svg>
            </div>
            <div class="srm-logo-text-block">
                <div class="srm-logo-name">SRM</div>
                <div class="srm-logo-sub">INSTITUTE OF SCIENCE &amp; TECHNOLOGY</div>
                <div class="srm-logo-tagline">Deemed to be University u/s 3 of UGC Act, 1956</div>
            </div>
        </div>

        <!-- Two column layout -->
        <div class="srm-login-outer">
    """, unsafe_allow_html=True)

    left_col, right_col = st.columns([1, 1])

    with left_col:
        st.markdown("""
        <div class="srm-welcome-panel">
            <p class="srm-dear">Dear Student,</p>
            <p class="srm-welcome-line">Welcome to <strong>SRMIST STUDENT PORTAL</strong>.</p>
            <p class="srm-info">
                You can access the student portal to know your academic details,
                query college documents, and get AI-powered answers instantly.
            </p>
            <p class="srm-info">
                SRMIST students can login with their university credentials.
                (i.e. If your mail ID is <span style="color:#1a4fa0;">abcd@srmist.edu.in</span>,
                your username is <strong>abcd</strong>)
            </p>
        </div>
        """, unsafe_allow_html=True)

    with right_col:
        # ── Login card header ──
        st.markdown("""
        <div class="srm-card">
            <div class="srm-card-header">Student Portal</div>
        """, unsafe_allow_html=True)

        tab_signin, tab_signup = st.tabs(["Sign In", "Sign Up"])

        with tab_signin:
            # Show captcha error if previous attempt was wrong
            if st.session_state.get('captcha_error'):
                st.markdown("""
                <div class="srm-alert-error">
                    Incorrect captcha. Please solve the verification question again.
                </div>
                """, unsafe_allow_html=True)

            with st.form("login_form", clear_on_submit=False):
                # Username input with icon
                st.markdown('<div class="srm-field-label">Username <span style="font-size:0.75rem;color:var(--text-3);">(without \'@srmist.edu.in\')</span></div>', unsafe_allow_html=True)
                username = st.text_input("Username", placeholder="Username", label_visibility="collapsed")

                st.markdown('<div class="srm-field-label">Password</div>', unsafe_allow_html=True)
                password = st.text_input("Password", placeholder="Password", type="password", label_visibility="collapsed")

                # Captcha
                a = st.session_state.get('captcha_a', '?')
                b = st.session_state.get('captcha_b', '?')
                st.markdown('<div class="srm-field-label">Captcha Verification</div>', unsafe_allow_html=True)

                cap_c1, cap_c2 = st.columns([3, 2])
                with cap_c1:
                    captcha_answer = st.number_input(
                        "Captcha answer", min_value=0, max_value=99, step=1,
                        key="captcha_input", label_visibility="collapsed",
                        placeholder="Enter answer"
                    )
                with cap_c2:
                    st.markdown(f"""
                    <div class="srm-captcha-display">
                        <span class="srm-captcha-text">{a} + {b} = ?</span>
                    </div>
                    """, unsafe_allow_html=True)

                remember  = st.checkbox("Keep me signed in for 7 days")
                submitted = st.form_submit_button("Login", use_container_width=True)

            if submitted:
                if not username or not password:
                    st.error("Please enter both username and password.")
                elif int(captcha_answer) != st.session_state.captcha_ans:
                    st.session_state.captcha_error = True
                    _init_captcha()
                    st.session_state.captcha_error = True  # keep after _init_captcha resets it
                    st.error("Incorrect captcha answer. A new question has been generated.")
                else:
                    st.session_state.captcha_error = False
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
            with st.expander("Demo Credentials"):
                st.markdown(DEMO_CREDENTIALS_NOTE)

        with tab_signup:
            st.info("New accounts are created as **Student** role. Contact an Admin for Staff or Admin access.")
            with st.form("signup_form", clear_on_submit=True):
                su_display  = st.text_input("Full Name", placeholder="e.g. Imran Mohamed")
                su_username = st.text_input("Username", placeholder="Choose a username (no spaces)")
                su_email    = st.text_input("Email (optional)", placeholder="your@srmist.edu.in")
                su_password = st.text_input("Password", type="password", placeholder="Min 6 characters")
                su_confirm  = st.text_input("Confirm Password", type="password")
                su_submit   = st.form_submit_button("Create Account", use_container_width=True)

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
                        st.success(f"Account created! You can now sign in as: **{su_username}**")
                    else:
                        st.error(msg)

        st.markdown("</div>", unsafe_allow_html=True)  # /srm-card

    st.markdown("</div></div>", unsafe_allow_html=True)  # /srm-login-outer /srm-portal-page


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
        ("Welcome!", f"Hi {user['display']}! Welcome to the College AI Assistant. Let's show you around."),
        ("Chat", "Ask any question about college documents. The AI will search through uploaded PDFs and give accurate answers."),
        ("Voice Input", "Click the Mic button to speak your question instead of typing. Works on Chrome and Edge."),
        ("Export Answers", "Every AI answer can be saved as a PDF or shared on Telegram using the buttons below each response."),
        ("Language Support", "The AI auto-detects your language — ask in English, Tamil, Hindi, or even Tanglish."),
        ("You're all set!", "Start by asking a question or clicking one of the suggestion chips below the chat!"),
    ]

    total = len(steps)
    title, desc = steps[step - 1]

    st.markdown(f"""
    <div class="tour-card">
        <div class="tour-step">Step {step} of {total}</div>
        <div class="tour-title">{title}</div>
        <div class="tour-desc">{desc}</div>
        <div style="margin-top:20px;display:flex;justify-content:center;gap:6px;">
            {''.join(['<div style="width:8px;height:8px;border-radius:50%;background:' + ('var(--blue)' if i+1==step else 'var(--border-2)') + ';display:inline-block;"></div>' for i in range(total)])}
        </div>
    </div>
    """, unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        if step > 1:
            if st.button("Back", use_container_width=True):
                st.session_state.onboard_step = step - 1
                st.rerun()
    with c2:
        if step < total:
            if st.button("Next", use_container_width=True):
                st.session_state.onboard_step = step + 1
                st.rerun()
        else:
            if st.button("Get Started", use_container_width=True):
                mark_onboarded(pg_url, user['username'])
                st.session_state.user['onboarded'] = True
                st.session_state.onboard_step = 1
                st.rerun()