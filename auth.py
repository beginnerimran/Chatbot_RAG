"""
auth.py — Auth, RBAC, session tokens, session timeout, login UI.
CHANGES:
  - College logo URL set to fsh.srmrmp.edu.in logo
  - Logo is small (44px), neat, inline with title
  - Header shows only "SRM Institute of Science and Technology" — no subtitle, no tagline
  - Left-column promotional/welcome text removed; login form is centered & compact
  - All other auth logic unchanged
"""

import base64
import random
import time
from datetime import datetime

import streamlit as st

from config import DEMO_CREDENTIALS_NOTE, SESSION_TIMEOUT_MINUTES
from database import db_authenticate, get_db_connection, mark_onboarded


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
    st.session_state.captcha_a     = a
    st.session_state.captcha_b     = b
    st.session_state.captcha_ans   = a + b
    st.session_state.captcha_error = False


def check_session_timeout():
    last = st.session_state.get('last_activity')
    if last is None:
        st.session_state.last_activity = time.time()
        return False
    if time.time() - last > SESSION_TIMEOUT_MINUTES * 60:
        return True
    st.session_state.last_activity = time.time()
    return False


# ── SVG icon data URIs (URL-encoded) ──
_ICON_USER = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E"
    "%3Cpath fill='%23b0bec5' d='M12 12c2.7 0 4.8-2.1 4.8-4.8S14.7 2.4 12 2.4 7.2 4.5 7.2 7.2 "
    "9.3 12 12 12zm0 2.4c-3.2 0-9.6 1.6-9.6 4.8v2.4h19.2v-2.4c0-3.2-6.4-4.8-9.6-4.8z'/%3E%3C/svg%3E"
)
_ICON_LOCK = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E"
    "%3Cpath fill='%23b0bec5' d='M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10"
    "c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zm-6 9c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 "
    "2-.9 2-2 2zm3.1-9H8.9V6c0-1.71 1.39-3.1 3.1-3.1 1.71 0 3.1 1.39 3.1 3.1v2z'/%3E%3C/svg%3E"
)
_ICON_REFRESH = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E"
    "%3Cpath fill='%23b0bec5' d='M17.65 6.35C16.2 4.9 14.21 4 12 4c-4.42 0-8 3.58-8 8s3.58 8 8 8"
    "c3.73 0 6.84-2.55 7.73-6h-2.08c-.82 2.33-3.04 4-5.65 4-3.31 0-6-2.69-6-6s2.69-6 6-6"
    "c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z'/%3E%3C/svg%3E"
)
_ICON_LOCK_BTN = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E"
    "%3Cpath fill='%23ffffff' d='M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10"
    "c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zm-6 9c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 "
    "2-.9 2-2 2zm3.1-9H8.9V6c0-1.71 1.39-3.1 3.1-3.1 1.71 0 3.1 1.39 3.1 3.1v2z'/%3E%3C/svg%3E"
)

# ── College logo — small and neat ──
COLLEGE_LOGO_URL = "https://fsh.srmrmp.edu.in/wp-content/uploads/2025/07/fsh-logo.png"


def render_login(pg_url: str):
    if 'captcha_ans' not in st.session_state:
        _init_captcha()

    a = st.session_state.get('captcha_a', '?')
    b = st.session_state.get('captcha_b', '?')

    # ── Login-page CSS overrides ──
    st.markdown(f"""
<style>
/* ── LOGIN PAGE OVERRIDES ── */
[data-testid="stSidebar"]        {{ display: none !important; }}
[data-testid="collapsedControl"] {{ display: none !important; }}
.stApp, html, body, [class*="css"] {{ background: #e9edf4 !important; }}
.block-container {{ padding: 0 !important; max-width: 100% !important; }}

/* ── Header bar ── */
.srm-header {{
    background: #ffffff;
    border-bottom: 1px solid #d8dde8;
    padding: 14px 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
}}
/* Small logo — 44px */
.srm-logo-img {{
    width: 44px;
    height: 44px;
    border-radius: 8px;
    object-fit: cover;
    flex-shrink: 0;
    background: #1a3a7a;
}}
/* Institution name only — no subtitle */
.srm-inst-name {{
    font-size: 1.15rem;
    font-weight: 800;
    color: #1a3a7a;
    letter-spacing: 0.2px;
    font-family: 'Inter', sans-serif;
    line-height: 1.2;
}}

/* Page content padding */
.block-container {{ padding: 8px 1rem 6rem 1rem !important; max-width: 100% !important; }}
@media (min-width: 768px)  {{ .block-container {{ padding: 8px 2rem 3rem 2rem !important; }} }}
@media (min-width: 1024px) {{ .block-container {{ padding: 8px 3rem 3rem 3rem !important; }} }}

/* Login card */
.srm-card        {{ background: #fff; border-radius: 4px; box-shadow: 0 2px 18px rgba(0,0,0,0.13); overflow: hidden; max-width: 480px; margin: 28px auto 0 auto; }}
.srm-card-header {{ background: #3a80c0; color: #fff; font-size: 1.05rem; font-weight: 600; padding: 14px 22px; text-align: center; letter-spacing: 0.2px; }}

/* Input field container label */
.srm-label      {{ font-size: 0.82rem; color: #444; margin-bottom: 4px; margin-top: 12px; }}
.srm-label-note {{ font-size: 0.75rem; color: #888; }}

/* Native inputs with icons */
input[placeholder="srm-netid"] {{
    padding-left: 40px !important;
    background: #fff url("{_ICON_USER}") no-repeat 11px center / 20px !important;
    border: 1px solid #ced4da !important;
    border-radius: 4px !important;
    color: #333 !important;
    font-size: 0.9rem !important;
    min-height: 42px !important;
}}
input[placeholder="srm-password"] {{
    padding-left: 40px !important;
    background: #fff url("{_ICON_LOCK}") no-repeat 11px center / 18px !important;
    border: 1px solid #ced4da !important;
    border-radius: 4px !important;
    color: #333 !important;
    font-size: 0.9rem !important;
    min-height: 42px !important;
}}
input[placeholder="srm-captcha"] {{
    padding-left: 40px !important;
    background: #fff url("{_ICON_REFRESH}") no-repeat 11px center / 18px !important;
    border: 1px solid #ced4da !important;
    border-radius: 4px !important;
    color: #333 !important;
    font-size: 0.9rem !important;
    min-height: 42px !important;
}}
input[placeholder="srm-netid"]:focus,
input[placeholder="srm-password"]:focus,
input[placeholder="srm-captcha"]:focus {{
    border-color: #3a80c0 !important;
    box-shadow: 0 0 0 2px rgba(58,128,192,0.18) !important;
    outline: none !important;
}}
input[placeholder="srm-netid"]::placeholder,
input[placeholder="srm-password"]::placeholder,
input[placeholder="srm-captcha"]::placeholder {{ color: transparent !important; }}

/* Captcha display */
.srm-captcha-img {{
    background: #f5f5f5;
    border: 1px solid #ced4da;
    border-radius: 4px;
    height: 42px;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
}}
.srm-captcha-chars {{
    font-family: 'Georgia', serif;
    font-size: 1.15rem;
    font-weight: 900;
    letter-spacing: 5px;
    background: linear-gradient(135deg, #c0392b 0%, #8e44ad 40%, #2980b9 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    transform: skewX(-8deg) scaleY(1.08);
    display: inline-block;
    filter: drop-shadow(0.5px 0.5px 0 rgba(0,0,0,0.2));
    user-select: none;
    padding: 0 6px;
}}

/* Forgot password */
.srm-forgot {{ text-align: right; font-size: 0.8rem; margin-top: -4px; margin-bottom: 6px; }}
.srm-forgot a {{ color: #3a80c0; text-decoration: none; }}

/* Login button */
.stButton > button {{
    background: #3a80c0 !important;
    border: none !important;
    border-radius: 4px !important;
    color: #ffffff !important;
    font-size: 0.95rem !important;
    font-weight: 600 !important;
    min-height: 44px !important;
    padding-left: 20px !important;
    background-image: url("{_ICON_LOCK_BTN}") !important;
    background-repeat: no-repeat !important;
    background-position: calc(50% - 40px) center !important;
    background-size: 18px !important;
    transition: background-color 0.2s !important;
}}
.stButton > button:hover {{
    background-color: #2e6dab !important;
    box-shadow: 0 3px 12px rgba(58,128,192,0.35) !important;
    transform: none !important;
}}

/* Error box */
.srm-error {{
    background: #fdf0f0;
    border: 1px solid #e8a0a0;
    border-left: 4px solid #c0392b;
    border-radius: 4px;
    padding: 9px 14px;
    color: #a93226;
    font-size: 0.85rem;
    margin-bottom: 10px;
}}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {{ border-bottom: 2px solid #e0e6f0 !important; background: transparent !important; }}
.stTabs [data-baseweb="tab"]      {{ color: #666 !important; font-size: 0.88rem !important; }}
.stTabs [aria-selected="true"]    {{ color: #3a80c0 !important; border-bottom: 2px solid #3a80c0 !important; font-weight: 600 !important; }}

/* Checkbox */
.stCheckbox label {{ font-size: 0.82rem !important; color: #555 !important; }}
.stCheckbox span  {{ font-size: 0.82rem !important; color: #555 !important; }}

/* Form submit button */
.stFormSubmitButton > button {{
    background: #3a80c0 !important;
    border-radius: 4px !important;
    border: none !important;
    color: #fff !important;
    font-weight: 600 !important;
    font-size: 0.95rem !important;
    min-height: 44px !important;
    background-image: url("{_ICON_LOCK_BTN}") !important;
    background-repeat: no-repeat !important;
    background-position: calc(50% - 36px) center !important;
    background-size: 16px !important;
}}
.stFormSubmitButton > button:hover {{
    background-color: #2e6dab !important;
    box-shadow: 0 3px 12px rgba(58,128,192,0.35) !important;
}}
</style>
""", unsafe_allow_html=True)

    # ── Header: small logo + institution name only ──
    st.markdown(f"""
<div class="srm-header">
    <img src="{COLLEGE_LOGO_URL}"
         class="srm-logo-img"
         alt="SRM Logo"
         onerror="this.style.display='none'">
    <div class="srm-inst-name">SRM Institute of Science and Technology</div>
</div>
""", unsafe_allow_html=True)

    # ── Login card — centered, single column ──
    st.markdown("""
<div class="srm-card">
    <div class="srm-card-header">Student Portal — Sign In</div>
</div>
""", unsafe_allow_html=True)

    # Center the form using columns trick
    _, center_col, _ = st.columns([1, 3, 1])

    with center_col:
        if st.session_state.get('captcha_error'):
            st.markdown(
                '<div class="srm-error">Incorrect captcha answer. '
                'A new question has been generated &mdash; please try again.</div>',
                unsafe_allow_html=True
            )

        with st.form("login_form", clear_on_submit=False):
            st.markdown('<div class="srm-label">Username</div>', unsafe_allow_html=True)
            username = st.text_input(
                "netid", placeholder="srm-netid",
                label_visibility="collapsed"
            )

            st.markdown('<div class="srm-label">Password</div>', unsafe_allow_html=True)
            password = st.text_input(
                "password", placeholder="srm-password",
                type="password", label_visibility="collapsed"
            )
            st.markdown(
                '<div class="srm-forgot"><a href="#">Forgot Password?</a></div>',
                unsafe_allow_html=True
            )

            st.markdown('<div class="srm-label">Captcha</div>', unsafe_allow_html=True)
            c_input_col, c_img_col, _ = st.columns([3, 2.2, 0.6])
            with c_input_col:
                captcha_answer = st.number_input(
                    "captcha", min_value=0, max_value=99, step=1,
                    key="captcha_input", label_visibility="collapsed",
                    placeholder="srm-captcha"
                )
            with c_img_col:
                st.markdown(f"""
<div class="srm-captcha-img">
    <span class="srm-captcha-chars">{a}+{b}=?</span>
</div>
""", unsafe_allow_html=True)

            remember  = st.checkbox("Keep me signed in for 7 days")
            submitted = st.form_submit_button("   Login", use_container_width=True)

        if submitted:
            if not username or not password:
                st.error("Please enter both username and password.")
            elif int(captcha_answer) != st.session_state.captcha_ans:
                st.session_state.captcha_input = 0
                _init_captcha()
                st.session_state.captcha_error = True
                st.rerun()
            else:
                st.session_state.captcha_error = False
                with st.spinner("Signing in..."):
                    user = authenticate(pg_url, username, password)
                if user:
                    st.session_state.user          = user
                    st.session_state.authenticated = True
                    st.session_state.last_activity = time.time()
                    st.session_state.language      = user.get('language', 'en')
                    st.query_params["sid"] = _make_token(user["username"], user["role"], user["display"])
                    if remember:
                        st.session_state.remembered_user  = username
                        st.session_state.remember_expires = datetime.now().timestamp() + 7 * 24 * 3600
                    st.rerun()
                else:
                    st.error("Invalid username or password.")
                    _init_captcha()

        st.markdown("<hr>", unsafe_allow_html=True)
        with st.expander("Demo Credentials"):
            st.markdown(DEMO_CREDENTIALS_NOTE)


def restore_session(pg_url: str):
    if not st.session_state.get('authenticated'):
        token = st.query_params.get("sid", "")
        if token:
            restored = _decode_token(token, pg_url)
            if restored:
                st.session_state.user          = restored
                st.session_state.authenticated = True
                st.session_state.last_activity = time.time()
                st.session_state.language      = restored.get('language', 'en')


def render_onboarding(pg_url: str):
    """First-time user welcome tour."""
    user  = st.session_state.user
    step  = st.session_state.get('onboard_step', 1)
    steps = [
        ("Welcome!", f"Hi {user['display']}! Welcome to the College AI Assistant. Let's show you around."),
        ("Chat", "Ask any question about college documents. The AI will search through uploaded files and give accurate answers."),
        ("Voice Input", "Click the Mic button to speak your question instead of typing. Works on Chrome and Edge."),
        ("Export Answers", "Every AI answer can be saved as a PDF using the button below each response."),
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