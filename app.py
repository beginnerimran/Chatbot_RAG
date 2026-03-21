"""
app.py — Main entry point. Run: streamlit run app.py
All errors are caught and shown as clean friendly messages — no code tracebacks.
"""

import sys
import time
import traceback
import streamlit as st

from config import setup_page, SESSION_TIMEOUT_MINUTES
from database import init_db, get_notifications, mark_notifications_read, get_unread_count
from auth import render_login, restore_session, check_session_timeout, render_onboarding
from rag import load_semantic_model
from sidebar import render_sidebar
from chat import render_chat
from dashboard import render_dashboard
from ui_components import render_docs_panel, render_user_management, render_change_password


# ─────────────────────────────────────────────
# FRIENDLY ERROR MESSAGES
# Maps common error types to clean user messages
# ─────────────────────────────────────────────
def friendly_error(e: Exception) -> str:
    msg = str(e).lower()
    if "connection" in msg or "pg_url" in msg or "database" in msg or "psycopg" in msg:
        return "Unable to connect to the database. Please try again in a moment."
    if "groq" in msg or "api key" in msg or "401" in msg:
        return "AI service is temporarily unavailable. Please try again shortly."
    if "timeout" in msg:
        return "The request timed out. Please check your internet connection and try again."
    if "rate limit" in msg or "429" in msg:
        return "Too many requests. Please wait a moment before trying again."
    if "memory" in msg or "out of memory" in msg:
        return "The system is under heavy load. Please refresh the page and try again."
    if "sentence" in msg or "model" in msg or "transformer" in msg:
        return "The AI model is still loading. Please wait a moment and refresh."
    if "permission" in msg or "access" in msg:
        return "You do not have permission to perform this action."
    if "not found" in msg or "no such" in msg:
        return "The requested resource was not found. Please refresh and try again."
    # Generic fallback — never show raw error
    return "Something went wrong. Please refresh the page and try again."


def show_error(message: str):
    """Shows a clean, styled error card — no code, no traceback."""
    st.markdown(f"""
    <div style="
        background: rgba(240,82,82,0.08);
        border: 1px solid rgba(240,82,82,0.3);
        border-left: 4px solid #f05252;
        border-radius: 10px;
        padding: 20px 24px;
        margin: 20px 0;
        max-width: 600px;
        margin-left: auto;
        margin-right: auto;
    ">
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
            <span style="font-size:1.4rem;">⚠️</span>
            <span style="font-size:1rem;font-weight:600;color:#f87171;">Something went wrong</span>
        </div>
        <p style="color:#fca5a5;font-size:0.88rem;margin:0 0 12px 0;line-height:1.6;">{message}</p>
        <button onclick="window.location.reload()"
            style="background:rgba(240,82,82,0.2);border:1px solid rgba(240,82,82,0.4);
                   color:#f87171;padding:7px 18px;border-radius:6px;cursor:pointer;
                   font-size:0.82rem;font-family:Inter,sans-serif;">
            🔄 Refresh Page
        </button>
    </div>
    """, unsafe_allow_html=True)


def load_secrets():
    try:
        return st.secrets["PG_URL"], st.secrets["GROQ_API_KEY"]
    except Exception:
        show_error("Configuration is missing. Please contact the administrator.")
        st.stop()


# ─────────────────────────────────────────────
# GLOBAL ERROR BOUNDARY
# Wraps every tab/section so one crash doesn't
# break the whole app
# ─────────────────────────────────────────────
def safe_render(fn, *args, **kwargs):
    """Calls fn(*args) and catches any exception — shows friendly message instead of traceback."""
    try:
        fn(*args, **kwargs)
    except Exception as e:
        show_error(friendly_error(e))


def main():
    try:
        setup_page()
    except Exception:
        pass  # CSS failure should not crash the app

    try:
        pg_url, api_key = load_secrets()
    except Exception:
        show_error("Could not load configuration. Please contact the administrator.")
        st.stop()
        return

    # Init DB
    try:
        if not st.session_state.get('db_initialised'):
            if init_db(pg_url):
                st.session_state.db_initialised = True
            else:
                show_error("Unable to connect to the database. Please try again in a moment.")
                st.stop()
                return
    except Exception as e:
        show_error(friendly_error(e))
        st.stop()
        return

    # Restore session
    try:
        restore_session(pg_url)
    except Exception:
        pass  # Session restore failure is non-critical — just show login

    if not st.session_state.get('authenticated'):
        try:
            render_login(pg_url)
        except Exception as e:
            show_error(friendly_error(e))
        return

    # Session timeout
    try:
        if check_session_timeout():
            st.info("Your session has expired. Please sign in again.")
            st.query_params.clear()
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
            return
    except Exception:
        pass

    # Load semantic model
    try:
        model = load_semantic_model()
    except Exception:
        model = None

    user = st.session_state.get('user', {})
    role = user.get('role', 'student')

    # Onboarding tour
    if not user.get('onboarded'):
        try:
            render_onboarding(pg_url)
        except Exception as e:
            show_error(friendly_error(e))
        return

    # Sidebar
    try:
        render_sidebar(pg_url, api_key, model)
    except Exception:
        pass  # Sidebar failure should not crash main content

    # Header
    try:
        unread = get_unread_count(pg_url, user['username'])
    except Exception:
        unread = 0

    dark = st.session_state.get('dark_mode', True)

    st.markdown(f"""
    <div class="app-header">
        <div class="app-header-title">🎓 College AI Assistant</div>
        <div class="app-header-meta">
            <span style="color:var(--text-3);font-size:0.78rem;">SRM Institute · CS Dept</span>
            <span class="role-badge role-{role}">{role}</span>
            <span style="font-weight:500;">{user.get('display','')}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Dark mode + Notifications
    hc1, hc2, hc3 = st.columns([1.5, 1.5, 9])
    with hc1:
        if st.button("☀️ Light" if dark else "🌙 Dark", key="theme_toggle", use_container_width=True):
            st.session_state.dark_mode = not dark
            st.rerun()
    with hc2:
        notif_label = f"🔔 ({unread})" if unread > 0 else "🔔"
        if st.button(notif_label, key="notif_btn", use_container_width=True):
            st.session_state.show_notifications = not st.session_state.get('show_notifications', False)
            if st.session_state.show_notifications:
                try:
                    mark_notifications_read(pg_url, user['username'])
                except Exception:
                    pass
            st.rerun()

    if st.session_state.get('show_notifications'):
        try:
            notifs = get_notifications(pg_url, user['username'])
            with st.expander("🔔 Notifications", expanded=True):
                if notifs:
                    for n in notifs:
                        icon = {"info":"ℹ️","success":"✅","warn":"⚠️","error":"❌"}.get(n['type'],"ℹ️")
                        ts   = str(n['created_at'])[:16]
                        st.markdown(f"""
                        <div style="padding:8px 0;border-bottom:1px solid var(--border);font-size:0.83rem;">
                            {icon} {n['message']}<br>
                            <span style="font-size:0.65rem;color:var(--text-3);">{ts}</span>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.markdown("No notifications yet.")
        except Exception:
            pass

    # Mobile bottom nav
    active_tab = st.query_params.get("tab", "chat")
    if role == "admin":
        nav_items = [("💬","Chat","chat"),("📚","Docs","docs"),("📊","Stats","dashboard"),("👥","Users","users"),("🔑","Account","account")]
    else:
        nav_items = [("💬","Chat","chat"),("📚","Docs","docs"),("🔑","Account","account")]

    nav_html = '<div class="bottom-nav">'
    for icon, label, key in nav_items:
        active_cls = "active" if active_tab == key else ""
        nav_html  += (f'<button class="bottom-nav-btn {active_cls}" '
                      f'onclick="window.parent.location.href=window.parent.location.pathname+\'?tab={key}\'">'
                      f'<span class="nav-icon">{icon}</span>{label}</button>')
    nav_html += '</div>'
    st.markdown(nav_html, unsafe_allow_html=True)

    # Tabs
    if role == "admin":
        tabs    = st.tabs(["💬 Chat", "📚 Docs", "📊 Dashboard", "👥 Users", "🔑 Account"])
        tab_map = {"chat":0, "docs":1, "dashboard":2, "users":3, "account":4}
    else:
        tabs    = st.tabs(["💬 Chat", "📚 Docs", "🔑 Account"])
        tab_map = {"chat":0, "docs":1, "account":2}

    with tabs[tab_map["chat"]]:
        safe_render(render_chat, pg_url, api_key, model)

    with tabs[tab_map["docs"]]:
        safe_render(render_docs_panel, pg_url, role)

    if role == "admin":
        with tabs[tab_map["dashboard"]]:
            safe_render(render_dashboard, pg_url)
        with tabs[tab_map["users"]]:
            safe_render(render_user_management, pg_url, user['username'])
        with tabs[tab_map["account"]]:
            safe_render(render_change_password, pg_url, user['username'])
    else:
        with tabs[tab_map["account"]]:
            safe_render(render_change_password, pg_url, user['username'])


# ─────────────────────────────────────────────
# TOP-LEVEL SAFETY NET
# Catches anything that escapes the main() try blocks
# ─────────────────────────────────────────────
try:
    main()
except Exception as e:
    try:
        setup_page()
    except Exception:
        pass
    show_error("The application encountered an unexpected error. Please refresh the page.")