"""
ui_components.py — Docs panel, user management, change password.
"""

import streamlit as st

from auth import check_permission
from database import (
    add_user, change_password, delete_document,
    delete_user, get_all_users, get_document_list
)


def render_docs_panel(pg_url: str, role: str):
    st.markdown("### Uploaded Documents")
    docs = get_document_list(pg_url)
    if not docs:
        st.markdown('<div class="alert-info">No documents uploaded yet. Ask Admin or Staff to upload college PDFs.</div>', unsafe_allow_html=True)
        return

    st.markdown(f'<div style="font-size:0.78rem;color:var(--text-3);margin-bottom:12px;">{len(docs)} document{"s" if len(docs)!=1 else ""} in the knowledge base</div>', unsafe_allow_html=True)

    for doc in docs:
        ocr_tag  = '<span class="ocr-badge">OCR</span>' if doc.get('used_ocr') else ""
        cat      = doc.get('category','General')
        uploader = doc.get('uploaded_by','-')
        at       = str(doc.get('uploaded_at',''))[:16]
        chunks   = doc.get('chunk_count','?')
        fname    = doc['filename']

        col_info, col_del = st.columns([5, 1])
        with col_info:
            st.markdown(f"""
            <div class="doc-card">
                <div class="doc-card-name">{fname} {ocr_tag} <span class="cat-badge">{cat}</span></div>
                <div class="doc-card-meta">{chunks} chunks &middot; uploaded by {uploader} &middot; {at}</div>
            </div>
            """, unsafe_allow_html=True)
        with col_del:
            if check_permission(role, "delete"):
                if st.button("Delete", key=f"docs_del_{doc['id']}", help="Delete document"):
                    if delete_document(pg_url, doc['id']):
                        st.session_state.docs_loaded = False
                        st.rerun()


def render_user_management(pg_url: str, current_username: str):
    st.markdown("### User Management")

    with st.expander("Add New User", expanded=False):
        with st.form("add_user_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                new_uname   = st.text_input("Username")
                new_display = st.text_input("Display Name")
                new_email   = st.text_input("Email (optional)")
            with col2:
                new_pass = st.text_input("Password", type="password")
                new_role = st.selectbox("Role", ["student","staff","admin"])
            if st.form_submit_button("Create User", use_container_width=True):
                ok, msg = add_user(pg_url, new_uname, new_pass, new_role, new_display, new_email)
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

    st.markdown("**Existing Users**")
    users = get_all_users(pg_url)
    if users:
        for u in users:
            c1, c2, c3, c4, c5 = st.columns([2, 1.5, 2, 2, 1])
            with c1:
                st.markdown(f"<div style='font-size:0.82rem;'>{u['username']}</div>", unsafe_allow_html=True)
            with c2:
                st.markdown(f'<span class="role-badge role-{u["role"]}">{u["role"]}</span>', unsafe_allow_html=True)
            with c3:
                st.markdown(f"<div style='font-size:0.75rem;color:var(--text-2);'>{u['display_name']}</div>", unsafe_allow_html=True)
            with c4:
                last_a = str(u.get('last_active',''))[:16]
                st.markdown(f"<div style='font-size:0.65rem;color:var(--text-3);'>Last: {last_a}</div>", unsafe_allow_html=True)
            with c5:
                if u['username'] != current_username:
                    if st.button("Del", key=f"del_user_{u['id']}"):
                        ok, msg = delete_user(pg_url, u['id'], current_username)
                        if ok:
                            st.rerun()
                        else:
                            st.error(msg)
                else:
                    st.markdown("<div style='font-size:0.7rem;color:var(--text-3);'>you</div>", unsafe_allow_html=True)
    else:
        st.info("No users found.")


def render_change_password(pg_url: str, username: str):
    st.markdown("### Account Settings")
    with st.expander("Change Password", expanded=False):
        with st.form("change_pw_form"):
            old_pw  = st.text_input("Current Password", type="password")
            new_pw  = st.text_input("New Password", type="password")
            new_pw2 = st.text_input("Confirm New Password", type="password")
            if st.form_submit_button("Update Password", use_container_width=True):
                if not old_pw or not new_pw or not new_pw2:
                    st.error("All fields are required.")
                elif new_pw != new_pw2:
                    st.error("New passwords do not match.")
                else:
                    ok, msg = change_password(pg_url, username, old_pw, new_pw)
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)