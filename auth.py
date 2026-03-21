"""
auth.py — Authentication, role-based access control, session tokens, and Login UI.
"""

import base64
import random
import time
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components

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
# LOGIN UI
# ─────────────────────────────────────────────
def render_login(pg_url: str):
    if 'captcha_ans' not in st.session_state:
        _init_captcha()

    st.markdown("""
    <style>
    .fl-group { position:relative; margin-bottom:24px; }
    .fl-group input {
        width:100%; background:#0d1525 !important; border:1.5px solid #1e3a5f !important;
        border-radius:10px !important; padding:18px 44px 6px 14px !important;
        font-size:1rem !important; color:#e2e8f0 !important; outline:none !important;
        transition:border-color 0.25s,box-shadow 0.25s !important; min-height:56px !important;
        box-sizing:border-box; font-family:'IBM Plex Sans',sans-serif !important;
    }
    .fl-group input:focus { border-color:#00d4aa !important; box-shadow:0 0 0 3px rgba(0,212,170,0.12) !important; }
    .fl-group label {
        position:absolute; left:14px; top:50%; transform:translateY(-50%);
        font-size:0.95rem; color:#64748b; pointer-events:none; transition:all 0.2s ease;
        font-family:'IBM Plex Sans',sans-serif; background:transparent;
    }
    .fl-group input:focus + label,
    .fl-group input:not(:placeholder-shown) + label {
        top:10px; transform:none; font-size:0.68rem; color:#00d4aa;
        letter-spacing:0.5px; text-transform:uppercase;
    }
    .pw-wrap { position:relative; }
    .pw-toggle { position:absolute; right:14px; top:50%; transform:translateY(-50%); background:none; border:none; cursor:pointer; color:#475569; font-size:1.1rem; padding:4px; line-height:1; transition:color 0.2s; }
    .pw-toggle:hover { color:#00d4aa; }
    .captcha-box { background:rgba(0,212,170,0.06); border:1px solid rgba(0,212,170,0.2); border-radius:10px; padding:12px 14px; margin-bottom:18px; display:flex; align-items:center; gap:12px; flex-wrap:wrap; }
    .captcha-question { font-family:'IBM Plex Mono',monospace; font-size:1rem; color:#00d4aa; white-space:nowrap; }
    .captcha-input { width:80px !important; background:#0d1525 !important; border:1.5px solid #1e3a5f !important; border-radius:8px !important; padding:8px 12px !important; font-size:1rem !important; color:#e2e8f0 !important; font-family:'IBM Plex Mono',monospace !important; outline:none !important; min-height:unset !important; transition:border-color 0.2s !important; }
    .captcha-input:focus { border-color:#00d4aa !important; }
    .signin-btn { width:100%; padding:14px; background:linear-gradient(135deg,#00d4aa,#00b894); color:#0a0e1a; font-weight:700; font-size:1rem; border:none; border-radius:10px; cursor:pointer; font-family:'IBM Plex Sans',sans-serif; letter-spacing:0.3px; transition:all 0.2s; margin-top:4px; }
    .signin-btn:hover { background:linear-gradient(135deg,#00e5b8,#00c9a7); box-shadow:0 6px 20px rgba(0,212,170,0.35); transform:translateY(-1px); }
    .form-footer { display:flex; align-items:center; justify-content:space-between; margin:14px 0 20px; flex-wrap:wrap; gap:8px; }
    .remember-label { display:flex; align-items:center; gap:8px; font-size:0.85rem; color:#94a3b8; cursor:pointer; font-family:'IBM Plex Sans',sans-serif; }
    .remember-label input[type=checkbox] { width:16px; height:16px; accent-color:#00d4aa; cursor:pointer; }
    .forgot-link { font-size:0.82rem; color:#00d4aa; text-decoration:none; font-family:'IBM Plex Sans',sans-serif; cursor:pointer; background:none; border:none; padding:0; transition:opacity 0.2s; }
    .forgot-link:hover { opacity:0.75; text-decoration:underline; }
    .login-page-wrap { min-height:100vh; display:flex; align-items:center; justify-content:center; padding:20px 16px 40px; }
    .login-card-v2 { width:100%; max-width:440px; background:#111827; border:1px solid #1e3a5f; border-radius:20px; padding:40px 32px 36px; box-shadow:0 24px 64px rgba(0,0,0,0.6); }
    @media (max-width:480px) { .login-card-v2 { padding:28px 18px 28px; border-radius:16px; } }
    .login-logo { text-align:center; margin-bottom:28px; }
    .login-logo .logo-icon { font-size:2.8rem; display:block; margin-bottom:8px; }
    .login-logo h2 { font-family:'IBM Plex Mono',monospace; color:#00d4aa; font-size:1.4rem; margin:0 0 4px; }
    .login-logo p  { font-family:'IBM Plex Mono',monospace; color:#475569; font-size:0.75rem; margin:0; }
    </style>
    """, unsafe_allow_html=True)

    a = st.session_state.get('captcha_a', '?')
    b = st.session_state.get('captcha_b', '?')

    remembered = ""
    if st.session_state.get('remembered_user') and st.session_state.get('remember_expires', 0) > datetime.now().timestamp():
        remembered = f'<div class="alert-info" style="margin-bottom:18px;">👋 Welcome back, <b>{st.session_state.remembered_user}</b> — enter your password to continue.</div>'

    st.markdown(f"""
    <div class="login-page-wrap">
      <div class="login-card-v2">
        <div class="login-logo">
          <span class="logo-icon">🎓</span>
          <h2>College AI Assistant</h2>
          <p>// SRM Institute — CS Department</p>
        </div>
        {remembered}
        <div id="login-error-msg"></div>
        <div class="fl-group">
          <input type="text" id="fl-username" placeholder=" " autocomplete="username" />
          <label for="fl-username">Username</label>
        </div>
        <div class="fl-group pw-wrap">
          <input type="password" id="fl-password" placeholder=" " autocomplete="current-password" />
          <label for="fl-password">Password</label>
          <button class="pw-toggle" type="button" id="pw-eye" onclick="togglePw()" title="Show/hide password">👁</button>
        </div>
        <div class="captcha-box">
          <span class="captcha-question">🤖 What is <b>{a} + {b}</b> ?</span>
          <input type="number" class="captcha-input" id="fl-captcha" placeholder="Answer" min="0" max="99" />
        </div>
        <div class="form-footer">
          <label class="remember-label">
            <input type="checkbox" id="fl-remember" />
            Remember me for 7 days
          </label>
          <button class="forgot-link" onclick="showForgot()">Forgot password?</button>
        </div>
        <button class="signin-btn" onclick="doLogin()">Sign In →</button>
        <div id="forgot-msg" style="display:none;margin-top:16px;" class="alert-info">
          Contact your admin to reset your password.
        </div>
      </div>
    </div>
    <script>
    function togglePw() {{
        const pw = document.getElementById('fl-password');
        const eye = document.getElementById('pw-eye');
        pw.type = pw.type === 'password' ? 'text' : 'password';
        eye.textContent = pw.type === 'password' ? '👁' : '🙈';
    }}
    function showForgot() {{
        const m = document.getElementById('forgot-msg');
        m.style.display = m.style.display === 'none' ? 'block' : 'none';
    }}
    function doLogin() {{
        const username = document.getElementById('fl-username').value.trim();
        const password = document.getElementById('fl-password').value;
        const captcha  = document.getElementById('fl-captcha').value.trim();
        const remember = document.getElementById('fl-remember').checked;
        if (!username || !password) {{ showError('⚠️ Please enter both username and password.'); return; }}
        if (!captcha) {{ showError('⚠️ Please answer the CAPTCHA.'); return; }}
        sessionStorage.setItem('login_username', username);
        sessionStorage.setItem('login_password', password);
        sessionStorage.setItem('login_captcha',  captcha);
        sessionStorage.setItem('login_remember', remember ? '1' : '0');
        const allBtns = window.parent.document.querySelectorAll('button');
        for (const b of allBtns) {{
            if (b.innerText.includes('_submit_login_')) {{ b.click(); return; }}
        }}
    }}
    function showError(msg) {{
        const el = document.getElementById('login-error-msg');
        if (el) {{ el.innerHTML = '<div class="alert-error">' + msg + '</div>'; setTimeout(() => {{ el.innerHTML = ''; }}, 4000); }}
    }}
    </script>
    """, unsafe_allow_html=True)

    components.html("""
    <script>
    (function() {
        function setStreamlitInput(selector, value) {
            const inputs = window.parent.document.querySelectorAll(selector);
            for (const inp of inputs) {
                const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                setter.call(inp, value);
                inp.dispatchEvent(new Event('input', { bubbles: true }));
            }
        }
        const u = sessionStorage.getItem('login_username') || '';
        const p = sessionStorage.getItem('login_password') || '';
        const c = sessionStorage.getItem('login_captcha')  || '';
        if (u) setStreamlitInput('input[aria-label="_u"]', u);
        if (p) setStreamlitInput('input[aria-label="_p"]', p);
        if (c) setStreamlitInput('input[aria-label="_c"]', c);
    })();
    </script>
    """, height=0)

    username_val = st.text_input("_u", key="hid_user", label_visibility="collapsed")
    password_val = st.text_input("_p", key="hid_pass", label_visibility="collapsed", type="password")
    captcha_val  = st.text_input("_c", key="hid_cap",  label_visibility="collapsed")
    remember_val = st.checkbox("_r",  key="hid_rem",   label_visibility="collapsed")

    with st.form("_login_form_", clear_on_submit=False):
        fu = st.text_input("Username", key="form_user")
        fp = st.text_input("Password", key="form_pass", type="password")
        fc = st.text_input("Captcha",  key="form_cap")
        fr = st.checkbox("Remember me", key="form_rem")
        submitted = st.form_submit_button("_submit_login_", use_container_width=False)

    if submitted and fu:
        try:
            cap_int = int(fc.strip()) if fc else -1
        except ValueError:
            cap_int = -1

        if cap_int != st.session_state.captcha_ans:
            st.markdown('<div class="alert-error">🤖 Wrong CAPTCHA. Please try again.</div>', unsafe_allow_html=True)
            _init_captcha()
        elif not fu or not fp:
            st.markdown('<div class="alert-error">⚠️ Enter both username and password.</div>', unsafe_allow_html=True)
        else:
            with st.spinner("Signing in..."):
                user = authenticate(pg_url, fu, fp)
            if user:
                st.session_state.user          = user
                st.session_state.authenticated = True
                st.query_params["sid"] = _make_token(user["username"], user["role"], user["display"])
                if fr:
                    st.session_state.remembered_user  = fu
                    st.session_state.remember_expires = datetime.now().timestamp() + 7 * 24 * 3600
                st.rerun()
            else:
                st.markdown('<div class="alert-error">❌ Invalid username or password.</div>', unsafe_allow_html=True)
                _init_captcha()

    with st.expander("Demo credentials"):
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
