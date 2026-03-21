"""
sidebar.py — Sidebar UI: user info, PDF upload, document list, stats, chat controls.
"""

import streamlit as st

from auth import check_permission
from database import (
    clear_chat_history,
    delete_document,
    get_document_list,
    get_db_connection,
    get_stats,
    load_chat_history,
    save_document_to_db,
)
from rag import OCR_AVAILABLE, extract_text_from_pdf


def render_sidebar(pg_url: str, api_key: str, model):
    user = st.session_state.user
    role = user['role']

    with st.sidebar:
        # ── User info ──
        st.markdown(f"""
        <div style="padding:12px;background:rgba(0,0,0,0.3);border-radius:8px;margin-bottom:16px;">
            <div style="font-family:'IBM Plex Mono',monospace;font-size:0.8rem;color:#94a3b8;margin-bottom:4px;">SIGNED IN AS</div>
            <div style="font-weight:600;color:#e2e8f0;">{user['display']}</div>
            <div style="margin-top:6px;"><span class="role-badge role-{role}">{role}</span></div>
        </div>
        """, unsafe_allow_html=True)

        # ── Status indicators ──
        conn_test = get_db_connection(pg_url)
        db_ok = conn_test is not None
        if db_ok:
            conn_test.close()
        st.markdown(
            f'<div style="font-size:0.75rem;color:{"#6ee7b7" if db_ok else "#fca5a5"};">'
            f'<span class="status-dot {"dot-green" if db_ok else "dot-red"}"></span>'
            f'Database {"Connected" if db_ok else "Offline"}</div>',
            unsafe_allow_html=True
        )
        semantic_ok = model is not None
        st.markdown(
            f'<div style="font-size:0.75rem;color:{"#6ee7b7" if semantic_ok else "#fbbf24"};">'
            f'<span class="status-dot {"dot-green" if semantic_ok else "dot-yellow"}"></span>'
            f'{"Semantic Search Active" if semantic_ok else "Keyword Search (fallback)"}</div>',
            unsafe_allow_html=True
        )

        st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)

        # ── Upload — Admin/Staff only ──
        if check_permission(role, "upload"):
            st.markdown("**📄 Upload Documents**")
            uploaded_files = st.file_uploader(
                "PDF files", type=['pdf'],
                accept_multiple_files=True,
                label_visibility="collapsed"
            )
            if uploaded_files and st.button("⚙️ Process & Save", use_container_width=True):
                if not model:
                    st.markdown('<div class="alert-error">❌ Semantic model not loaded.</div>', unsafe_allow_html=True)
                else:
                    any_saved = False
                    for pdf_file in uploaded_files:
                        with st.spinner(f"Processing {pdf_file.name}..."):
                            pdf_bytes = pdf_file.read()
                            chunks, used_ocr = extract_text_from_pdf(pdf_bytes, pdf_file.name)
                            if chunks:
                                embeddings = model.encode(chunks, normalize_embeddings=True, show_progress_bar=False)
                                if save_document_to_db(pg_url, pdf_file.name, user['username'], chunks, embeddings, used_ocr):
                                    ocr_note = " (OCR)" if used_ocr else ""
                                    st.markdown(f'<div class="alert-success">✅ {pdf_file.name}{ocr_note} — {len(chunks)} chunks saved</div>', unsafe_allow_html=True)
                                    any_saved = True
                            else:
                                ocr_msg = "" if OCR_AVAILABLE else " Install pytesseract + pdf2image for scanned PDFs."
                                st.markdown(f'<div class="alert-error">❌ {pdf_file.name}: No text extracted.{ocr_msg}</div>', unsafe_allow_html=True)
                    if any_saved:
                        st.session_state.docs_loaded = False
                        st.rerun()

            st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)

        # ── Document list ──
        docs      = get_document_list(pg_url)
        doc_count = len(docs) if docs else 0
        with st.expander(f"📚 Loaded Documents ({doc_count})", expanded=False):
            if docs:
                for doc in docs:
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        ocr_badge = '<span class="ocr-badge">OCR</span>' if doc['used_ocr'] else ''
                        st.markdown(
                            f"<div style='font-size:0.78rem;color:#94a3b8;'>📄 {doc['filename'][:22]}{'...' if len(doc['filename'])>22 else ''}{ocr_badge}"
                            f"<br><span style='font-size:0.65rem;color:#475569;'>{doc['chunk_count']} chunks</span></div>",
                            unsafe_allow_html=True
                        )
                    with c2:
                        if check_permission(role, "delete"):
                            if st.button("🗑", key=f"del_{doc['id']}"):
                                if delete_document(pg_url, doc['id']):
                                    st.session_state.docs_loaded = False
                                    st.rerun()
            else:
                st.markdown('<div class="alert-info">No documents uploaded yet.</div>', unsafe_allow_html=True)

        # ── Admin stats ──
        if check_permission(role, "view_stats"):
            st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)
            st.markdown("**📊 System Stats**")
            stats = get_stats(pg_url)
            if stats:
                st.markdown(f"""
                <div class="stat-row">
                    <div class="stat-card"><div class="stat-num">{stats.get('docs',0)}</div><div class="stat-lbl">Docs</div></div>
                    <div class="stat-card"><div class="stat-num">{stats.get('chunks',0)}</div><div class="stat-lbl">Chunks</div></div>
                    <div class="stat-card"><div class="stat-num">{stats.get('queries',0)}</div><div class="stat-lbl">Queries</div></div>
                </div>
                <div style="font-size:0.75rem;color:#94a3b8;font-family:'IBM Plex Mono',monospace;">Avg confidence: {stats.get('avg_conf',0)}%</div>
                """, unsafe_allow_html=True)

        st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)

        # ── History controls ──
        if st.button("📜 Load My History", use_container_width=True):
            rows = load_chat_history(pg_url, user['username'], limit=40)
            st.session_state.messages = [
                {"role": r['role'], "content": r['content'],
                 "sources": r['sources'], "confidence": r['confidence'],
                 "time": str(r['created_at'])}
                for r in rows
            ]
            st.session_state.history_loaded = True
            st.rerun()

        c1, c2 = st.columns(2)
        with c1:
            if st.button("🗑 Clear Chat", use_container_width=True):
                clear_chat_history(pg_url, user['username'])
                st.session_state.messages = []
                st.session_state.history_loaded = False
                st.rerun()
        with c2:
            if st.button("🚪 Logout", use_container_width=True):
                st.query_params.clear()
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()
