"""
sidebar.py — Sidebar: user info, status, upload with category, doc list, stats, controls.
CHANGES:
  - File uploader now accepts PDF, DOCX, DOC, XLSX, XLS, CSV, TXT, PNG, JPG, JPEG
  - Uses extract_text_from_file() instead of extract_text_from_pdf()
  - Detects file_type and mime_type per file and stores them in DB
  - Per-file try/except: failures are reported per file; batch continues
  - Label is generic (not "PDF files")
"""

import streamlit as st

from auth import check_permission
from database import (
    clear_chat_history, delete_document, get_document_list,
    get_db_connection, get_stats, load_chat_history,
    save_document_to_db, update_user_language,
    ext_from_filename, mime_for_ext,
)
from rag import OCR_AVAILABLE, extract_text_from_file


# Accepted file types for the uploader
_ACCEPTED_TYPES = [
    "pdf", "docx", "doc",
    "xlsx", "xls", "csv",
    "txt",
    "png", "jpg", "jpeg",
]


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
        try:
            conn_test = get_db_connection(pg_url)
            db_ok     = conn_test is not None
            if db_ok:
                conn_test.close()
        except Exception:
            db_ok = False
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
            cat_names = ["Admission", "Exam", "General", "Rules", "Timetable"]
            if "upload_category" not in st.session_state:
                st.session_state["upload_category"] = "Admission"
            category = st.selectbox("Category", cat_names, index=0, key="upload_category")

            uploaded_files = st.file_uploader(
                "Upload files",
                type=_ACCEPTED_TYPES,
                accept_multiple_files=True,
                label_visibility="collapsed",
                help="Supported: PDF, DOCX, DOC, XLSX, XLS, CSV, TXT, PNG, JPG, JPEG",
            )

            if uploaded_files and st.button("Process & Save", use_container_width=True):
                if not model:
                    st.error("Semantic model not loaded. Cannot generate embeddings.")
                else:
                    succeeded = []
                    failed    = []

                    for uploaded_file in uploaded_files:
                        fname = uploaded_file.name
                        try:
                            # Read raw bytes
                            try:
                                file_bytes = uploaded_file.read()
                            except Exception as read_err:
                                print(f"[sidebar] Failed to read '{fname}': {read_err}")
                                st.error(
                                    f"'{fname}': Could not read the file. "
                                    "It may be corrupted or too large. Please try again."
                                )
                                failed.append(fname)
                                continue

                            if not file_bytes:
                                st.error(
                                    f"'{fname}': The file appears to be empty. "
                                    "Please check the file and try again."
                                )
                                failed.append(fname)
                                continue

                            # Detect type info
                            file_ext  = ext_from_filename(fname)
                            file_mime = mime_for_ext(file_ext)

                            # Extract text chunks
                            with st.spinner(f"Processing {fname}..."):
                                try:
                                    chunks, used_ocr = extract_text_from_file(file_bytes, fname)
                                except Exception as extract_err:
                                    print(f"[sidebar] extract_text_from_file crashed for '{fname}': {extract_err}")
                                    st.error(
                                        f"'{fname}': An unexpected error occurred while reading this file. "
                                        "Please re-save it and try again."
                                    )
                                    failed.append(fname)
                                    continue

                            if not chunks:
                                # extract_text_from_file already showed a user message
                                failed.append(fname)
                                continue

                            # Generate embeddings
                            try:
                                embeddings = model.encode(
                                    chunks,
                                    normalize_embeddings=True,
                                    show_progress_bar=False,
                                )
                            except Exception as embed_err:
                                print(f"[sidebar] Embedding failed for '{fname}': {embed_err}")
                                st.error(
                                    f"'{fname}': Embedding generation failed. "
                                    "The semantic model may still be loading. Please try again."
                                )
                                failed.append(fname)
                                continue

                            # Save to DB
                            try:
                                saved = save_document_to_db(
                                    pg_url, fname, user['username'],
                                    chunks, embeddings, used_ocr, category,
                                    file_bytes=file_bytes,
                                    file_type=file_ext,
                                    mime_type=file_mime,
                                )
                            except Exception as save_err:
                                print(f"[sidebar] save_document_to_db crashed for '{fname}': {save_err}")
                                saved = False

                            if saved:
                                ocr_note = " (OCR)" if used_ocr else ""
                                st.success(
                                    f"'{fname}'{ocr_note} — {len(chunks)} chunks saved successfully."
                                )
                                succeeded.append(fname)
                            else:
                                st.error(
                                    f"'{fname}': The file was read successfully, "
                                    "but saving to the database failed. Please try again."
                                )
                                failed.append(fname)

                        except Exception as outer_err:
                            # Catch-all so one bad file never crashes the whole batch
                            print(f"[sidebar] Unexpected error for '{fname}': {outer_err}")
                            st.error(
                                f"'{fname}': An unexpected error occurred. "
                                "Please try again or contact your administrator."
                            )
                            failed.append(fname)

                    # Batch summary
                    if succeeded and failed:
                        st.info(
                            f"{len(succeeded)} file(s) saved. "
                            f"{len(failed)} file(s) failed: {', '.join(failed)}"
                        )
                    elif not succeeded and failed:
                        st.warning(
                            "No files were added. "
                            f"All {len(failed)} file(s) failed: {', '.join(failed)}"
                        )

                    if succeeded:
                        st.session_state.docs_loaded = False
                        st.rerun()

            st.markdown("<hr class='divider'>", unsafe_allow_html=True)

        # Document list — hidden for students
        if role != 'student':
            try:
                docs      = get_document_list(pg_url)
                doc_count = len(docs) if docs else 0
            except Exception:
                docs, doc_count = [], 0

            with st.expander(f"Documents ({doc_count})", expanded=False):
                if docs:
                    for doc in docs:
                        cat   = doc.get('category', 'General')
                        ocr_b = ' · OCR' if doc['used_ocr'] else ''
                        fname = doc['filename']
                        display_name = (fname[:32] + '…') if len(fname) > 32 else fname
                        st.markdown(
                            f"""<div style="
                                background: #ffffff;
                                border: 1px solid #d0dbef;
                                border-radius: 7px;
                                padding: 9px 12px;
                                margin-bottom: 6px;
                                word-break: break-word;
                                overflow-wrap: break-word;
                                white-space: normal;
                                min-width: 0;
                            ">
                                <div style="
                                    font-size: 0.82rem;
                                    font-weight: 700;
                                    color: #1a2640;
                                    margin-bottom: 4px;
                                    word-break: break-word;
                                    overflow-wrap: anywhere;
                                    white-space: normal;
                                    line-height: 1.4;
                                    letter-spacing: 0.01em;
                                ">
                                    {display_name}
                                </div>
                                <div style="
                                    font-size: 0.68rem;
                                    color: #6b82a0;
                                    font-weight: 500;
                                ">
                                    {doc['chunk_count']} chunks &middot; {cat}{ocr_b}
                                </div>
                            </div>""",
                            unsafe_allow_html=True
                        )
                        if check_permission(role, "delete"):
                            st.markdown('<div class="danger-btn">', unsafe_allow_html=True)
                            try:
                                clicked = st.button("Delete", key=f"del_{doc['id']}", use_container_width=True)
                            except Exception:
                                clicked = False
                            st.markdown('</div>', unsafe_allow_html=True)
                            if clicked:
                                try:
                                    if delete_document(pg_url, doc['id']):
                                        st.session_state.docs_loaded = False
                                        st.rerun()
                                except Exception as del_err:
                                    print(f"[sidebar] Delete failed: {del_err}")
                                    st.error("Failed to delete document. Please try again.")
                else:
                    st.info("No documents uploaded yet.")

        # Admin stats
        if check_permission(role, "view_stats"):
            st.markdown("<hr class='divider'>", unsafe_allow_html=True)
            try:
                stats = get_stats(pg_url)
            except Exception:
                stats = {}
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
            try:
                rows = load_chat_history(pg_url, user['username'], limit=40)
                st.session_state.messages = [
                    {"role":r['role'],"content":r['content'],
                     "sources":r['sources'],"confidence":r['confidence'],
                     "time":str(r['created_at'])}
                    for r in rows
                ]
                st.session_state.history_loaded = True
                st.rerun()
            except Exception as hist_err:
                print(f"[sidebar] Load history failed: {hist_err}")
                st.error("Could not load chat history. Please try again.")

        c1, c2 = st.columns(2)
        with c1:
            if st.button("Clear Chat", use_container_width=True):
                try:
                    clear_chat_history(pg_url, user['username'])
                except Exception:
                    pass
                st.session_state.messages       = []
                st.session_state.history_loaded = False
                st.rerun()
        with c2:
            if st.button("Logout", use_container_width=True):
                st.query_params.clear()
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()