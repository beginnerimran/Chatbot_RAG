"""
ui_components.py — Reusable UI components:
  - Docs panel (full page)
  - User management (admin only)
  - Change password
"""

import streamlit as st

from auth import check_permission
from database import (
    add_user,
    change_password,
    delete_document,
    delete_user,
    get_all_users,
    get_document_list,
)


def render_docs_panel(pg_url: str, role: str):
    st.markdown("### 📚 Uploaded Documents")
    docs = get_document_list(pg_url)
    if not docs:
        st.markdown('<div class="alert-info">ℹ️ No documents uploaded yet. Ask Admin/Staff to upload college PDFs.</div>', unsafe_allow_html=True)
        return

    st.markdown(
        f'<div style="font-size:0.8rem;color:#64748b;margin-bottom:12px;">'
        f'{len(docs)} document{"s" if len(docs) != 1 else ""} in the knowledge base</div>',
        unsafe_allow_html=True
    )

    for doc in docs:
        ocr_tag  = '<span class="ocr-badge">OCR</span>' if doc.get('used_ocr') else ""
        uploader = doc.get('uploaded_by', '-')
        at       = str(doc.get('uploaded_at', ''))[:16]
        chunks   = doc.get('chunk_count', '?')
        fname    = doc['filename']

        col_info, col_del = st.columns([5, 1])
        with col_info:
            st.markdown(f"""
            <div class="doc-card">
                <div class="doc-card-name">📄 {fname} {ocr_tag}</div>
                <div class="doc-card-meta">{chunks} chunks &nbsp;·&nbsp; uploaded by {uploader} &nbsp;·&nbsp; {at}</div>
            </div>
            """, unsafe_allow_html=True)
        with col_del:
            if check_permission(role, "delete"):
                st.markdown("<div style='padding-top:8px'>", unsafe_allow_html=True)
                if st.button("🗑️", key=f"docs_del_{doc['id']}", help="Delete"):
                    if delete_document(pg_url, doc['id']):
                        st.session_state.docs_loaded = False
                        st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)


def render_user_management(pg_url: str, current_username: str):
    st.markdown("### 👥 User Management")

    with st.expander("➕ Add New User", expanded=False):
        with st.form("add_user_form"):
            col1, col2 = st.columns(2)
            with col1:
                new_uname   = st.text_input("Username")
                new_display = st.text_input("Display Name")
            with col2:
                new_pass = st.text_input("Password", type="password")
                new_role = st.selectbox("Role", ["student", "staff", "admin"])
            if st.form_submit_button("Create User", use_container_width=True):
                ok, msg = add_user(pg_url, new_uname, new_pass, new_role, new_display)
                if ok:
                    st.markdown(f'<div class="alert-success">✅ {msg}</div>', unsafe_allow_html=True)
                    st.rerun()
                else:
                    st.markdown(f'<div class="alert-error">❌ {msg}</div>', unsafe_allow_html=True)

    st.markdown("**Existing Users**")
    users = get_all_users(pg_url)
    if users:
        for u in users:
            c1, c2, c3, c4 = st.columns([2, 1.5, 2, 1])
            with c1:
                st.markdown(f"<div style='font-size:0.82rem;color:#e2e8f0;'>👤 {u['username']}</div>", unsafe_allow_html=True)
            with c2:
                st.markdown(f'<span class="role-badge role-{u["role"]}">{u["role"]}</span>', unsafe_allow_html=True)
            with c3:
                st.markdown(f"<div style='font-size:0.75rem;color:#94a3b8;'>{u['display_name']}</div>", unsafe_allow_html=True)
            with c4:
                if u['username'] != current_username:
                    if st.button("🗑", key=f"del_user_{u['id']}"):
                        ok, msg = delete_user(pg_url, u['id'], current_username)
                        if ok:
                            st.rerun()
                        else:
                            st.error(msg)
                else:
                    st.markdown("<div style='font-size:0.7rem;color:#475569;'>you</div>", unsafe_allow_html=True)
    else:
        st.markdown('<div class="alert-info">No users found.</div>', unsafe_allow_html=True)


def render_change_password(pg_url: str, username: str):
    with st.expander("🔑 Change My Password", expanded=False):
        with st.form("change_pw_form"):
            old_pw  = st.text_input("Current Password", type="password")
            new_pw  = st.text_input("New Password", type="password")
            new_pw2 = st.text_input("Confirm New Password", type="password")
            if st.form_submit_button("Update Password", use_container_width=True):
                if not old_pw or not new_pw or not new_pw2:
                    st.markdown('<div class="alert-error">⚠️ All fields are required.</div>', unsafe_allow_html=True)
                elif new_pw != new_pw2:
                    st.markdown('<div class="alert-error">⚠️ New passwords do not match.</div>', unsafe_allow_html=True)
                else:
                    ok, msg = change_password(pg_url, username, old_pw, new_pw)
                    if ok:
                        st.markdown(f'<div class="alert-success">✅ {msg}</div>', unsafe_allow_html=True)
                    else:
                        st.markdown(f'<div class="alert-error">❌ {msg}</div>', unsafe_allow_html=True)
