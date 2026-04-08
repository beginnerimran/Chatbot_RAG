"""
app.py — Main entry point for SRM College AI Assistant.
CHANGES:
  - st.tabs replaced with query_params-based navigation
  - Active page tracked via ?page=chat|docs|dashboard|users|account in URL
  - Browser Back/Forward now works: each page change pushes a new history entry
  - Role-based pages preserved: admin(5), staff(3), student(2)
  - Logout clears query params and returns to login
  - All other logic (session, timeout, sidebar, notifications) unchanged
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


# ── Page definitions per role ──────────────────────────────────────────────────
_PAGES = {
    "admin":   [("chat","Chat"), ("docs","Docs"), ("dashboard","Dashboard"), ("users","Users"), ("account","Account")],
    "staff":   [("chat","Chat"), ("docs","Docs"), ("account","Account")],
    "student": [("chat","Chat"), ("account","Account")],
}


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
        pg_url  = st.secrets["PG_URL"]
        api_key = st.secrets["GROQ_API_KEY"]
        return pg_url, api_key
    except Exception:
        show_error("Configuration missing PG_URL or GROQ_API_KEY in secrets.toml.")
        st.stop()
        return None, None


def safe_render(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except Exception as e:  # noqa: BLE001
        print(f"[saferender] ERROR in {fn.__name__}")
        _traceback.print_exc()
        show_error(friendly_error(e))


# -------------------------------------------------------------------
# Navigation helpers
# -------------------------------------------------------------------

def _get_available_pages(role: str):
    """Return list of (page_id, label) for the given role."""
    return _PAGES.get(role, _PAGES["student"])


def _get_current_page(role: str) -> str:
    """Read the current page from query params; fall back to the first page for the role."""
    avail_ids = [p[0] for p in _get_available_pages(role)]
    page = st.query_params.get("page", avail_ids[0])
    if page not in avail_ids:
        page = avail_ids[0]
    return page


def _render_nav(role: str) -> str:
    """
    Render the navigation bar as Streamlit buttons.
    Returns the currently active page_id.

    Each button click sets st.query_params["page"] which changes the URL and
    creates a browser history entry, enabling Back/Forward navigation.
    """
    avail  = _get_available_pages(role)
    active = _get_current_page(role)

    # Nav CSS: style active button differently
    st.markdown("""
<style>
/* Nav bar wrapper */
div[data-testid="stHorizontalBlock"] .nav-active > button {
    background: var(--blue) !important;
    color: #ffffff !important;
    border-bottom: 3px solid #0d3685 !important;
    font-weight: 700 !important;
}
div[data-testid="stHorizontalBlock"] .nav-inactive > button {
    background: var(--bg-2) !important;
    color: var(--text-2) !important;
    border-bottom: 3px solid transparent !important;
}
</style>
""", unsafe_allow_html=True)

    nav_cols = st.columns(len(avail))
    for i, (page_id, page_label) in enumerate(avail):
        is_active = page_id == active
        css_class = "nav-active" if is_active else "nav-inactive"
        with nav_cols[i]:
            st.markdown(f'<div class="{css_class}">', unsafe_allow_html=True)
            clicked = st.button(
                page_label,
                key=f"nav_{page_id}",
                use_container_width=True,
            )
            st.markdown('</div>', unsafe_allow_html=True)
            if clicked and not is_active:
                st.query_params["page"] = page_id
                st.rerun()

    return active


# -------------------------------------------------------------------
# Main app
# -------------------------------------------------------------------

def main() -> None:
    try:
        setup_page()
    except Exception:
        pass

    pg_url, api_key = load_secrets()
    if not pg_url:
        return

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

    try:
        restore_session(pg_url)
    except Exception:
        pass

    if not st.session_state.get("authenticated"):
        try:
            render_login(pg_url)
        except Exception as e:  # noqa: BLE001
            show_error(friendly_error(e))
        return

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

    try:
        model = load_semantic_model()
    except Exception:
        model = None

    user = st.session_state.get("user") or {}
    role = user.get("role", "student")

    if not user.get("onboarded", True):
        try:
            render_onboarding(pg_url)
        except Exception as e:  # noqa: BLE001
            show_error(friendly_error(e))
        return

    try:
        render_sidebar(pg_url, api_key, model)
    except Exception:
        pass

    unread = 0
    try:
        unread = get_unread_count(pg_url, user.get("username", ""))
    except Exception:
        unread = 0

    # ── App header ──────────────────────────────────────────────────────────
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
    with hc1:
        notif_label = f"Notifications ({unread})" if unread > 0 else "Notifications"
        if st.button(notif_label, key="notif_btn", use_container_width=True):
            st.session_state["show_notifications"] = not st.session_state.get(
                "show_notifications", False
            )
            if st.session_state["show_notifications"]:
                try:
                    mark_notifications_read(pg_url, user.get("username", ""))
                except Exception:
                    pass

    if st.session_state.get("show_notifications"):
        try:
            notifs = get_notifications(pg_url, user.get("username", ""))
            with st.expander("Notifications", expanded=True):
                if notifs:
                    for n in notifs:
                        msg = n.get("message", "")
                        ts  = str(n.get("created_at", ""))[:16]
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

    # ── Navigation bar (replaces st.tabs — supports browser Back/Forward) ──
    st.markdown("<div style='margin-top:8px;margin-bottom:4px;'>", unsafe_allow_html=True)
    current_page = _render_nav(role)
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("<hr style='margin:0 0 12px 0;border-color:var(--border);'>", unsafe_allow_html=True)

    # ── Page rendering ───────────────────────────────────────────────────────
    if current_page == "chat":
        safe_render(render_chat, pg_url, api_key, model)

    elif current_page == "docs" and role in ("admin", "staff"):
        safe_render(render_docs_panel, pg_url, role)

    elif current_page == "dashboard" and role == "admin":
        safe_render(render_dashboard, pg_url)

    elif current_page == "users" and role == "admin":
        safe_render(render_user_management, pg_url, user.get("username", ""))

    elif current_page == "account":
        safe_render(render_change_password, pg_url, user.get("username", ""))

    else:
        # Fallback — should not normally reach here
        safe_render(render_chat, pg_url, api_key, model)


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