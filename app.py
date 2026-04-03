"""
app.py — Main entry point for SRM College AI Assistant.
"""

import time
import traceback as _traceback

import streamlit as st

from config import setup_page, SESSION_TIMEOUT_MINUTES
from database import (
    init_db,
    get_notifications,
    mark_notifications_read,
    get_unread_count,
)
from auth import (
    render_login,
    restore_session,
    check_session_timeout,
    render_onboarding,
)
from rag import load_semantic_model
from sidebar import render_sidebar
from chat import render_chat
from dashboard import render_dashboard
from ui_components import (
    render_docs_panel,
    render_user_management,
    render_change_password,
)


# -------------------------------------------------------------------
# Error helpers
# -------------------------------------------------------------------

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
    return "Something went wrong. Please refresh the page and try again."


def show_error(message: str) -> None:
    st.markdown(
        f"""
<div style="
    background: rgba(192,57,43,0.07);
    border: 1px solid rgba(192,57,43,0.25);
    border-left: 4px solid #c0392b;
    border-radius: 10px;
    padding: 20px 24px;
    margin: 20px 0;
    max-width: 600px;
    margin-left: auto;
    margin-right: auto;
">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
    <span style="font-size:1rem;font-weight:700;color:#a93226;">Something went wrong</span>
  </div>
  <p style="color:#c0392b;font-size:0.88rem;margin:0 0 12px 0;line-height:1.6;">
    {message}
  </p>
  <button onclick="window.location.reload()"
    style="
      background: rgba(192,57,43,0.12);
      border: 1px solid rgba(192,57,43,0.35);
      color: #a93226;
      padding: 7px 18px;
      border-radius: 6px;
      cursor: pointer;
      font-size: 0.82rem;
      font-family: Inter, sans-serif;
    ">
    Refresh Page
  </button>
</div>
""",
        unsafe_allow_html=True,
    )


# -------------------------------------------------------------------
# Secrets / safe render
# -------------------------------------------------------------------

def load_secrets():
    try:
        pg_url = st.secrets["PG_URL"]
        api_key = st.secrets["GROQ_API_KEY"]
        return pg_url, api_key
    except Exception:
        show_error("Configuration missing PG_URL or GROQ_API_KEY in secrets.toml.")
        st.stop()
        return None, None


def safe_render(fn, *args, **kwargs):
    """Run a UI function and show a friendly message on error."""
    try:
        fn(*args, **kwargs)
    except Exception as e:  # noqa: BLE001
        print(f"[saferender] ERROR in {fn.__name__}")
        _traceback.print_exc()
        show_error(friendly_error(e))


# -------------------------------------------------------------------
# Main app
# -------------------------------------------------------------------

def main() -> None:
    # Page + theme
    try:
        setup_page()
    except Exception:
        # Even if setup_page CSS fails, continue rendering minimal UI
        pass

    # Secrets
    pg_url, api_key = load_secrets()
    if not pg_url:
        return

    # Initialise DB once per session
    try:
        if not st.session_state.get("db_initialised"):
            if init_db(pg_url):
                st.session_state["db_initialised"] = True
            else:
                show_error("Unable to connect to the database. Please try again.")
                st.stop()
                return
    except Exception as e:  # noqa: BLE001
        show_error(friendly_error(e))
        st.stop()
        return

    # Restore existing session from token (if any)
    try:
        restore_session(pg_url)
    except Exception:
        # Non-fatal; user can still log in manually
        pass

    # If not authenticated, show login and exit
    if not st.session_state.get("authenticated"):
        try:
            render_login(pg_url)
        except Exception as e:  # noqa: BLE001
            show_error(friendly_error(e))
        return

    # Session timeout handling
    try:
        if check_session_timeout():
            st.info("Your session has expired. Please sign in again.")
            st.query_params.clear()
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
            return
    except Exception:
        # If timeout check fails, do nothing special
        pass

    # Load semantic model (may be None -> keyword fallback)
    try:
        model = load_semantic_model()
    except Exception:
        model = None

    user = st.session_state.get("user") or {}
    role = user.get("role", "student")

    # Onboarding tour for first-time users
    if not user.get("onboarded", True):
        try:
            render_onboarding(pg_url)
        except Exception as e:  # noqa: BLE001
            show_error(friendly_error(e))
        return

    # Sidebar (user info, uploads, stats, etc.)
    try:
        render_sidebar(pg_url, api_key, model)
    except Exception:
        # Sidebar is non‑fatal; keep main UI usable
        pass

    # Unread notifications count
    unread = 0
    try:
        unread = get_unread_count(pg_url, user.get("username", ""))
    except Exception:
        unread = 0

    # ------------------------------------------------------------------
    # Header: title + role + notifications
    # ------------------------------------------------------------------
    st.markdown(
        f"""
<div class="app-header">
  <div class="app-header-title">
    <span class="srm-logo-text">SRM</span>
    <span>College AI Assistant</span>
  </div>
  <div class="app-header-meta">
    <span style="color:rgba(255,255,255,0.70);font-size:0.78rem;">CS Department</span>
    <span class="role-badge role-{role}">{role.title()}</span>
    <span style="color:#ffffff;font-weight:500;">{user.get("display", "")}</span>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    hc1, hc2 = st.columns([1.5, 10.5])

    # Notifications button (left column)
    with hc1:
        notif_label = f"Notifications ({unread})" if unread > 0 else "Notifications"
        if st.button(notif_label, key="notif_btn", use_container_width=True):
            st.session_state["show_notifications"] = not st.session_state.get(
                "show_notifications", False
            )
            # Mark as read when opening
            if st.session_state["show_notifications"]:
                try:
                    mark_notifications_read(pg_url, user.get("username", ""))
                except Exception:
                    pass

    # Notifications list (below header)
    if st.session_state.get("show_notifications"):
        try:
            notifs = get_notifications(pg_url, user.get("username", ""))
            with st.expander("Notifications", expanded=True):
                if notifs:
                    for n in notifs:
                        msg = n.get("message", "")
                        ts = str(n.get("created_at", ""))[:16]
                        st.markdown(
                            f"""
<div class="notif-item">
  <div class="notif-message">{msg}</div>
  <div class="notif-ts">{ts}</div>
</div>
""",
                            unsafe_allow_html=True,
                        )
                else:
                    st.markdown(
                        '<div class="notif-empty">No notifications yet.</div>',
                        unsafe_allow_html=True,
                    )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Tabs: Chat / Docs / Dashboard / Users / Account
    # ------------------------------------------------------------------
    if role == "admin":
        chat_tab, docs_tab, dash_tab, users_tab, account_tab = st.tabs(
            ["Chat", "Docs", "Dashboard", "Users", "Account"]
        )
    elif role == "staff":
        chat_tab, docs_tab, account_tab = st.tabs(["Chat", "Docs", "Account"])
        dash_tab = users_tab = None
    else:
        # Students: no Docs tab
        chat_tab, account_tab = st.tabs(["Chat", "Account"])
        docs_tab = dash_tab = users_tab = None

    # Chat tab (everyone)
    with chat_tab:
        safe_render(render_chat, pg_url, api_key, model)

    # Docs tab (admin + staff only — students cannot see this)
    if role in ("admin", "staff") and docs_tab is not None:
        with docs_tab:
            safe_render(render_docs_panel, pg_url, role)

    # Dashboard + Users (admin only)
    if role == "admin":
        with dash_tab:
            safe_render(render_dashboard, pg_url)
        with users_tab:
            safe_render(render_user_management, pg_url, user.get("username", ""))

    # Account tab (change password, etc.)
    with account_tab:
        safe_render(render_change_password, pg_url, user.get("username", ""))


# -------------------------------------------------------------------
# Streamlit entrypoint
# -------------------------------------------------------------------

try:
    main()
except Exception as e:  # noqa: BLE001
    try:
        setup_page()
    except Exception:
        pass
    print("TOP-LEVEL ERROR")
    _traceback.print_exc()
    show_error("The application encountered an unexpected error. Please refresh the page.")