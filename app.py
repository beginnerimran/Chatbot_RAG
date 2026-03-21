"""
app.py — Main entry point. Run: streamlit run app.py
"""

import time
import streamlit as st

from config import setup_page, SESSION_TIMEOUT_MINUTES
from database import init_db, get_notifications, mark_notifications_read, get_unread_count
from auth import render_login, restore_session, check_session_timeout, render_onboarding
from rag import load_semantic_model
from sidebar import render_sidebar
from chat import render_chat
from dashboard import render_dashboard
from ui_components import render_docs_panel, render_user_management, render_change_password


def load_secrets():
    try:
        return st.secrets["PG_URL"], st.secrets["GROQ_API_KEY"]
    except KeyError as e:
        st.error(f"Missing secret: {e}. Add PG_URL and GROQ_API_KEY to .streamlit/secrets.toml")
        st.stop()
    except Exception as e:
        st.error(f"Could not load secrets: {e}")
        st.stop()


def main():
    setup_page()
    pg_url, api_key = load_secrets()

    # Init DB
    if not st.session_state.get('db_initialised'):
        if init_db(pg_url):
            st.session_state.db_initialised = True
        else:
            st.error("Could not connect to the database. Check PG_URL in secrets.toml.")
            st.stop()

    # Restore session
    restore_session(pg_url)

    if not st.session_state.get('authenticated'):
        render_login(pg_url)
        return

    # Session timeout check
    if check_session_timeout():
        st.warning(f"Session expired after {SESSION_TIMEOUT_MINUTES} minutes of inactivity. Please sign in again.")
        st.query_params.clear()
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
        return

    model = load_semantic_model()
    user  = st.session_state.user
    role  = user['role']

    # Show onboarding tour for first-time users
    if not user.get('onboarded'):
        render_onboarding(pg_url)
        return

    # Sidebar
    render_sidebar(pg_url, api_key, model)

    # Dark / Light mode toggle + notifications in header
    unread = get_unread_count(pg_url, user['username'])
    dark   = st.session_state.get('dark_mode', True)

    notif_badge = f'<span class="notif-badge">{unread}</span>' if unread > 0 else ""

    st.markdown(f"""
    <div class="app-header">
        <div class="app-header-title">🎓 College AI Assistant</div>
        <div class="app-header-meta">
            <span style="color:var(--text-3);font-size:0.78rem;">SRM Institute · CS Dept</span>
            <span class="role-badge role-{role}">{role}</span>
            <span style="font-weight:500;">{user['display']}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Controls: Dark mode toggle + Notifications
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
                mark_notifications_read(pg_url, user['username'])
            st.rerun()

    # Notifications panel
    if st.session_state.get('show_notifications'):
        notifs = get_notifications(pg_url, user['username'])
        with st.expander("🔔 Notifications", expanded=True):
            if notifs:
                for n in notifs:
                    icon  = {"info":"ℹ️","success":"✅","warn":"⚠️","error":"❌"}.get(n['type'],"ℹ️")
                    ts    = str(n['created_at'])[:16]
                    st.markdown(f"""
                    <div style="padding:8px 0;border-bottom:1px solid var(--border);font-size:0.83rem;">
                        {icon} {n['message']}<br>
                        <span style="font-size:0.65rem;color:var(--text-3);">{ts}</span>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.markdown("No notifications.")

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
        tabs    = st.tabs(["💬 Chat","📚 Docs","📊 Dashboard","👥 Users","🔑 Account"])
        tab_map = {"chat":0,"docs":1,"dashboard":2,"users":3,"account":4}
    else:
        tabs    = st.tabs(["💬 Chat","📚 Docs","🔑 Account"])
        tab_map = {"chat":0,"docs":1,"account":2}

    with tabs[tab_map["chat"]]:
        render_chat(pg_url, api_key, model)
    with tabs[tab_map["docs"]]:
        render_docs_panel(pg_url, role)
    if role == "admin":
        with tabs[tab_map["dashboard"]]:
            render_dashboard(pg_url)
        with tabs[tab_map["users"]]:
            render_user_management(pg_url, user['username'])
        with tabs[tab_map["account"]]:
            render_change_password(pg_url, user['username'])
    else:
        with tabs[tab_map["account"]]:
            render_change_password(pg_url, user['username'])


if __name__ == "__main__":
    main()