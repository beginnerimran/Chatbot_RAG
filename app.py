"""
app.py — Main entry point for the College AI Assistant.

Run with:
    streamlit run app.py

Project structure:
    app.py            ← Entry point (this file)
    config.py         ← Page config, CSS, constants
    database.py       ← All PostgreSQL operations
    auth.py           ← Login, session tokens, RBAC
    rag.py            ← PDF extraction, semantic search, LLM
    sidebar.py        ← Sidebar UI
    chat.py           ← Chat UI, mic fix, PDF export, WhatsApp
    ui_components.py  ← Docs panel, user management, change password
"""

import streamlit as st

from config import setup_page
from database import init_db
from auth import render_login, restore_session
from rag import load_semantic_model
from sidebar import render_sidebar
from chat import render_chat
from ui_components import render_docs_panel, render_user_management, render_change_password


def load_secrets():
    try:
        pg_url  = st.secrets["PG_URL"]
        api_key = st.secrets["GROQ_API_KEY"]
        return pg_url, api_key
    except KeyError as e:
        st.error(f"❌ Missing secret: {e}. Add PG_URL and GROQ_API_KEY to .streamlit/secrets.toml")
        st.stop()
    except Exception as e:
        st.error(f"❌ Could not load secrets: {e}")
        st.stop()


def main():
    setup_page()

    pg_url, api_key = load_secrets()

    # ── Init DB once per cold start ──
    if not st.session_state.get('db_initialised'):
        if init_db(pg_url):
            st.session_state.db_initialised = True
        else:
            st.error("❌ Could not connect to the database. Check PG_URL in secrets.toml.")
            st.stop()

    # ── Restore session from URL token on refresh ──
    restore_session(pg_url)

    if not st.session_state.get('authenticated'):
        render_login(pg_url)
        return

    # ── Load semantic model ──
    model = load_semantic_model()
    user  = st.session_state.user
    role  = user['role']

    # ── Sidebar ──
    render_sidebar(pg_url, api_key, model)

    # ── App header ──
    st.markdown(f"""
    <div class="app-header">
        <h1>🎓 College AI Assistant</h1>
        <p>// SRM CS Dept &nbsp;|&nbsp;
           <span class="role-badge role-{role}">{role}</span> &nbsp;{user['display']}
        </p>
    </div>
    """, unsafe_allow_html=True)

    # ── Mobile bottom nav ──
    active_tab = st.query_params.get("tab", "chat")
    nav_items  = [("💬", "Chat", "chat"), ("📚", "Docs", "docs"), ("🔑", "Account", "account")]
    if role == "admin":
        nav_items = [("💬", "Chat", "chat"), ("📚", "Docs", "docs"), ("👥", "Users", "users"), ("🔑", "Account", "account")]

    nav_html = '<div class="bottom-nav">'
    for icon, label, key in nav_items:
        active_cls = "active" if active_tab == key else ""
        nav_html += (
            f'<button class="bottom-nav-btn {active_cls}" '
            f'onclick="window.parent.location.href=window.parent.location.pathname+\'?tab={key}\'">'
            f'<span class="nav-icon">{icon}</span>{label}</button>'
        )
    nav_html += '</div>'
    st.markdown(nav_html, unsafe_allow_html=True)

    # ── Tabs ──
    if role == "admin":
        tabs    = st.tabs(["💬 Chat", "📚 Docs", "👥 Users", "🔑 Account"])
        tab_map = {"chat": 0, "docs": 1, "users": 2, "account": 3}
    else:
        tabs    = st.tabs(["💬 Chat", "📚 Docs", "🔑 Account"])
        tab_map = {"chat": 0, "docs": 1, "account": 2}

    with tabs[tab_map["chat"]]:
        render_chat(pg_url, api_key, model)

    with tabs[tab_map["docs"]]:
        render_docs_panel(pg_url, role)

    if role == "admin":
        with tabs[tab_map["users"]]:
            render_user_management(pg_url, user['username'])
        with tabs[tab_map["account"]]:
            render_change_password(pg_url, user['username'])
    else:
        with tabs[tab_map["account"]]:
            render_change_password(pg_url, user['username'])


if __name__ == "__main__":
    main()
