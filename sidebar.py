"""
sidebar.py — Sidebar: user info, status, upload with category, doc list, stats, controls.
"""

import streamlit as st

from auth import check_permission
from database import (
    clear_chat_history, delete_document, get_document_list,
    get_db_connection, get_stats, load_chat_history,
    save_document_to_db, get_categories, update_user_language
)
from rag import OCR_AVAILABLE, extract_text_from_pdf


def render_sidebar(pg_url: str, api_key: str, model):
    user = st.session_state.user
    role = user['role']

    with st.sidebar:
        # User card
        st.markdown(f"""
        <div class="user-card">
            <div class="user-card-label">Signed in as</div>
            <div class="user-card-name">{user['display']}</div>
            <div style="margin-top:6px;"><span class="role-badge role-{role}">{role}</span></div>
        </div>
        """, unsafe_allow_html=True)

        # Status
        conn_test = get_db_connection(pg_url)
        db_ok     = conn_test is not None
        if db_ok:
            conn_test.close()
        sem_ok = model is not None

        st.markdown(
            f'<div style="font-size:0.75rem;margin-bottom:4px;"><span class="dot {"dot-green" if db_ok else "dot-red"}"></span>'
            f'{"Database Connected" if db_ok else "Database Offline"}</div>'
            f'<div style="font-size:0.75rem;margin-bottom:10px;"><span class="dot {"dot-green" if sem_ok else "dot-amber"}"></span>'
            f'{"Semantic Search Active" if sem_ok else "Keyword Search (fallback)"}</div>',
            unsafe_allow_html=True
        )

        st.markdown("<hr class='divider'>", unsafe_allow_html=True)

        # Upload — Admin/Staff only
        if check_permission(role, "upload"):
            st.markdown("**Upload Documents**")
            categories  = get_categories(pg_url)
            cat_names   = [c['name'] for c in categories] if categories else ["General"]
            category    = st.selectbox("Category", cat_names, key="upload_category")
            uploaded_files = st.file_uploader("PDF files", type=['pdf'],
                                               accept_multiple_files=True,
                                               label_visibility="collapsed")
            if uploaded_files and st.button("Process & Save", use_container_width=True):
                if not model:
                    st.error("Semantic model not loaded.")
                else:
                    any_saved = False
                    for pdf_file in uploaded_files:
                        with st.spinner(f"Processing {pdf_file.name}..."):
                            pdf_bytes = pdf_file.read()          # capture raw bytes first
                            chunks, used_ocr = extract_text_from_pdf(pdf_bytes, pdf_file.name)
                            if chunks:
                                embeddings = model.encode(chunks, normalize_embeddings=True, show_progress_bar=False)
                                if save_document_to_db(pg_url, pdf_file.name, user['username'],
                                                       chunks, embeddings, used_ocr, category,
                                                       pdf_bytes=pdf_bytes):
                                    ocr_note = " (OCR)" if used_ocr else ""
                                    st.success(f"{pdf_file.name}{ocr_note} — {len(chunks)} chunks saved")
                                    any_saved = True
                            else:
                                st.error(f"{pdf_file.name}: No text extracted.")
                    if any_saved:
                        st.session_state.docs_loaded = False
                        st.rerun()

            st.markdown("<hr class='divider'>", unsafe_allow_html=True)

        # Document list
        docs      = get_document_list(pg_url)
        doc_count = len(docs) if docs else 0
        with st.expander(f"Documents ({doc_count})", expanded=False):
            if docs:
                for doc in docs:
                    c1, c2 = st.columns([4, 1])
                    with c1:
                        cat   = doc.get('category','General')
                        ocr_b = '<span class="ocr-badge">OCR</span>' if doc['used_ocr'] else ''
                        st.markdown(
                            f"<div style='font-size:0.78rem;color:rgba(255,255,255,0.85);'>{doc['filename'][:20]}{'...' if len(doc['filename'])>20 else ''}"
                            f"<br><span style='font-size:0.65rem;color:rgba(255,255,255,0.55);'>{doc['chunk_count']} chunks · {cat}</span>{ocr_b}</div>",
                            unsafe_allow_html=True
                        )
                    with c2:
                        if check_permission(role, "delete"):
                            if st.button("Del", key=f"del_{doc['id']}"):
                                if delete_document(pg_url, doc['id']):
                                    st.session_state.docs_loaded = False
                                    st.rerun()
            else:
                st.info("No documents uploaded yet.")

        # Admin stats
        if check_permission(role, "view_stats"):
            st.markdown("<hr class='divider'>", unsafe_allow_html=True)
            stats = get_stats(pg_url)
            if stats:
                st.markdown(f"""
                <div class="stat-row">
                    <div class="stat-card"><div class="stat-num">{stats.get('docs',0)}</div><div class="stat-lbl">Docs</div></div>
                    <div class="stat-card"><div class="stat-num">{stats.get('queries',0)}</div><div class="stat-lbl">Queries</div></div>
                    <div class="stat-card"><div class="stat-num">{stats.get('users',0)}</div><div class="stat-lbl">Users</div></div>
                </div>
                """, unsafe_allow_html=True)

        st.markdown("<hr class='divider'>", unsafe_allow_html=True)

        # History controls
        if st.button("Load Chat History", use_container_width=True):
            rows = load_chat_history(pg_url, user['username'], limit=40)
            st.session_state.messages = [
                {"role":r['role'],"content":r['content'],
                 "sources":r['sources'],"confidence":r['confidence'],
                 "time":str(r['created_at'])}
                for r in rows
            ]
            st.session_state.history_loaded = True
            st.rerun()

        c1, c2 = st.columns(2)
        with c1:
            if st.button("Clear Chat", use_container_width=True):
                clear_chat_history(pg_url, user['username'])
                st.session_state.messages       = []
                st.session_state.history_loaded = False
                st.rerun()
        with c2:
            if st.button("Logout", use_container_width=True):
                st.query_params.clear()
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()