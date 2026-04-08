"""
chat.py — Full chat UI.
CHANGES:
  - Removed "Previous conversations saved — use Load History in sidebar." line from welcome card
  - _source_pdf_download renamed to _source_file_download, now handles all file types:
      uses get_document_file_info() to fetch correct mime_type for each source file
      label updated: "Source document(s) — download original file"
  - "No documents loaded" hint updated to be file-type agnostic
"""

import html as _html
import io
import json
import re
import time
from datetime import datetime

import streamlit as st

from auth import check_permission
from config import SUGGESTIONS
from database import (
    load_all_documents_from_db, log_query, save_chat_message,
    save_feedback, check_rate_limit, update_last_active,
    get_document_file_info, has_file_blob,
)
from rag import compute_confidence, confidence_html, generate_answer, semantic_search


def keyword_search(query: str, chunks: list, n_results: int = 5):
    """Simple keyword fallback when the semantic model is unavailable."""
    if not chunks:
        return [], []
    q_words = set(query.lower().split())
    scored = []
    for chunk in chunks:
        c_lower = chunk.lower()
        hits = sum(1 for w in q_words if w in c_lower)
        if hits:
            scored.append((hits, chunk))
    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:n_results]
    results = [c for _, c in top]
    scores  = [min(h / max(len(q_words), 1), 1.0) for h, _ in top]
    return results, scores


def _safe_answer_html(text: str) -> str:
    t = str(text)
    saved: list[str] = []

    def save_fenced(m):
        code = _html.escape(m.group(2).strip())
        html = (
            '<pre style="background:var(--bg-3);padding:8px 10px;border-radius:6px;'
            'font-size:0.78rem;overflow-x:auto;white-space:pre-wrap;margin:6px 0;">'
            f'{code}</pre>'
        )
        saved.append(html)
        return f"\x00PH{len(saved)-1}\x00"

    t = re.sub(r'```(\w*)\n?(.*?)```', save_fenced, t, flags=re.DOTALL)

    def save_inline(m):
        code = _html.escape(m.group(1))
        html = (
            '<code style="background:var(--bg-3);padding:1px 5px;border-radius:4px;'
            f'font-size:0.85em;font-family:JetBrains Mono,monospace;">{code}</code>'
        )
        saved.append(html)
        return f"\x00PH{len(saved)-1}\x00"

    t = re.sub(r'`([^`\n]+)`', save_inline, t)

    def apply_inline_md(s: str) -> str:
        s = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s)
        s = re.sub(r'__(.+?)__',     r'<strong>\1</strong>', s)
        s = re.sub(r'(?<!\*)\*([^*\n]+?)\*(?!\*)', r'<em>\1</em>', s)
        return s

    lines     = t.split('\n')
    out_lines = []
    in_list   = False

    for line in lines:
        stripped = line.lstrip()
        bullet_m = re.match(r'^([*\-•])\s+(.*)$', stripped)
        if bullet_m:
            if not in_list:
                out_lines.append('<ul style="margin:6px 0 6px 18px;padding:0;">')
                in_list = True
            item = _html.escape(bullet_m.group(2))
            item = apply_inline_md(item)
            out_lines.append(f'<li style="margin-bottom:3px;">{item}</li>')
        else:
            if in_list:
                out_lines.append('</ul>')
                in_list = False
            safe = _html.escape(line)
            safe = apply_inline_md(safe)
            out_lines.append(safe)

    if in_list:
        out_lines.append('</ul>')

    result = '\n'.join(out_lines)
    result = re.sub(r'\n(<[uo]l)',    r'\1',    result)
    result = re.sub(r'(</[uo]l>)\n', r'\1',    result)
    result = result.replace('\n', '<br/>')

    for i, block in enumerate(saved):
        result = result.replace(f'\x00PH{i}\x00', block)

    return result


FOLLOWUP_PROMPTS = [
    "Can you explain that in more detail?",
    "What are the key points?",
    "Who should I contact for this?",
    "Is there a deadline for this?",
]

LANG_AUTO_INSTRUCTION = """LANGUAGE RULE (VERY IMPORTANT):
Detect the language of the student question and reply in the SAME language and style.
- If they wrote in English reply in English
- If they wrote in Tamil script reply in Tamil
- If they wrote in Hindi/Devanagari reply in Hindi
- If they wrote in Tanglish (Tamil words in English letters like sollu pannanum iruku) reply in Tanglish the same way
- If they wrote in Hinglish (Hindi words in English letters like karo chahiye batao) reply in Hinglish the same way
- If they wrote in mixed language match their exact mix
Never switch language on your own. Always mirror the student language."""


# ─────────────────────────────────────────────
# PDF EXPORT
# ─────────────────────────────────────────────
def export_conversation_pdf(messages: list, username: str) -> bytes:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        buf  = io.BytesIO()
        doc  = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
        s    = getSampleStyleSheet()
        t_st = ParagraphStyle('T', parent=s['Heading1'], textColor=colors.HexColor('#00c9a7'), fontSize=18, spaceAfter=4)
        m_st = ParagraphStyle('M', parent=s['Normal'],   textColor=colors.grey, fontSize=9, spaceAfter=16)
        y_st = ParagraphStyle('Y', parent=s['Normal'],   textColor=colors.HexColor('#4f8ef7'), fontSize=11, fontName='Helvetica-Bold', spaceAfter=4)
        a_st = ParagraphStyle('A', parent=s['Normal'],   fontSize=11, leading=16, spaceAfter=12)
        story = [
            Paragraph("College AI Assistant - Conversation Export", t_st),
            Paragraph(f"User: {username}  |  Exported: {datetime.now().strftime('%Y-%m-%d %H:%M')}  |  SRM Institute CS Dept", m_st),
            HRFlowable(width="100%", thickness=1, color=colors.HexColor('#2a2f45')),
            Spacer(1, 0.3*cm),
        ]
        for msg in messages:
            try:
                c = str(msg.get('content','')).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
                if msg['role'] == 'user':
                    story.append(Paragraph(f"You: {c}", y_st))
                else:
                    story.append(Paragraph(f"AI: {c}", a_st))
                    story.append(Spacer(1, 0.1*cm))
            except Exception:
                pass
        doc.build(story)
        return buf.getvalue()
    except Exception:
        lines = [f"College AI Assistant - Export\nUser: {username}\n{'='*50}"]
        for msg in messages:
            lines.append(f"\n{'You' if msg['role']=='user' else 'AI'}: {msg.get('content','')}\n")
        return "\n".join(lines).encode("utf-8")


def _single_pdf(question: str, answer: str) -> bytes:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
        s   = getSampleStyleSheet()
        doc.build([
            Paragraph("College AI Assistant", ParagraphStyle('T', parent=s['Heading1'], textColor=colors.HexColor('#00c9a7'), fontSize=16)),
            Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | SRM Institute CS Dept", ParagraphStyle('M', parent=s['Normal'], textColor=colors.grey, fontSize=9)),
            Spacer(1, 0.4*cm),
            Paragraph(f"Q: {str(question).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')}",
                      ParagraphStyle('Q', parent=s['Normal'], textColor=colors.HexColor('#4f8ef7'), fontSize=11, fontName='Helvetica-Bold', spaceAfter=10)),
            Paragraph(str(answer).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('\n','<br/>'),
                      ParagraphStyle('A', parent=s['Normal'], fontSize=11, leading=16)),
        ])
        return buf.getvalue()
    except Exception:
        return f"Q: {question}\n\nA: {answer}\n\nGenerated: {datetime.now()}".encode("utf-8")


def _pdf_type():
    try:
        from reportlab.lib.pagesizes import A4  # noqa
        return "application/pdf", "pdf"
    except ImportError:
        return "text/plain", "txt"


# ─────────────────────────────────────────────
# ACTION ROW
# ─────────────────────────────────────────────
def _action_row(answer: str, msg_key: str, question: str, username: str, pg_url: str):
    mime, ext = _pdf_type()

    c1, c2, c3, _ = st.columns([1.5, 1.8, 2, 4])
    with c1:
        if st.button("Helpful", key=f"up_{msg_key}", use_container_width=True):
            try:
                save_feedback(pg_url, username, question, answer, 1)
                st.toast("Thanks for your feedback!")
            except Exception:
                pass
    with c2:
        if st.button("Not Helpful", key=f"dn_{msg_key}", use_container_width=True):
            try:
                save_feedback(pg_url, username, question, answer, -1)
                st.toast("Thanks — we will improve!")
            except Exception:
                pass
    with c3:
        try:
            st.download_button(
                label="Save as PDF",
                data=_single_pdf(question or "Query", answer),
                file_name=f"answer_{msg_key}.{ext}",
                mime=mime,
                key=f"dl_{msg_key}",
                use_container_width=True,
            )
        except Exception:
            pass


# ─────────────────────────────────────────────
# FOLLOW-UP CHIPS
# ─────────────────────────────────────────────
def _followup_chips(msg_key: str):
    chips = FOLLOWUP_PROMPTS
    rows  = ""
    for c in chips:
        safe = c.replace("'", "\\'")
        rows += f'<span class="followup-chip" onclick="(function(){{var i=document.querySelector(\'textarea[data-testid=stChatInputTextArea]\');if(i){{Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,\'value\').set.call(i,\'{safe}\');i.dispatchEvent(new Event(\'input\',{{bubbles:true}}));i.focus();}}}})()\">{c}</span>'
    st.markdown(f"""
    <div class="followup-wrap">
        <div class="followup-label">Follow-up suggestions</div>
        {rows}
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# SOURCE FILE DOWNLOAD  (generic — not PDF-only)
# ─────────────────────────────────────────────
def _source_file_download(source_doc_names: list, pg_url: str, key_suffix: str):
    """Show source document info and download buttons for the original uploaded files.

    Uses get_document_file_info() to retrieve the correct MIME type so non-PDF
    files download with the right extension and content type.
    """
    if not source_doc_names:
        return

    st.markdown("""
    <div style="margin-top:12px;padding:10px 14px;
                background:rgba(26,79,160,0.06);
                border:1px solid rgba(26,79,160,0.18);
                border-radius:8px;margin-bottom:4px;">
        <div style="font-size:0.70rem;font-weight:700;color:var(--text-3);
                    text-transform:uppercase;letter-spacing:0.5px;">
            📎 Source document(s) — download original file
        </div>
    </div>
    """, unsafe_allow_html=True)

    for i, fname in enumerate(source_doc_names):
        try:
            short_name = (fname[:40] + "…") if len(fname) > 40 else fname

            # Check blob availability first (avoids loading full BYTEA just to render UI)
            try:
                available = has_file_blob(pg_url, fname)
            except Exception as e:
                print(f"[chat] has_file_blob error for '{fname}': {e}")
                available = False

            if available:
                try:
                    file_data, file_type, file_mime = get_document_file_info(pg_url, fname)
                except Exception as e:
                    print(f"[chat] get_document_file_info error for '{fname}': {e}")
                    file_data, file_type, file_mime = None, "pdf", "application/pdf"

                if file_data:
                    st.download_button(
                        label=f"⬇  {short_name}",
                        data=file_data,
                        file_name=fname,
                        mime=file_mime,
                        key=f"src_dl_{key_suffix}_{i}",
                        use_container_width=True,
                        help=f"Download source file: {fname}",
                    )
                else:
                    st.markdown(
                        f'<div style="font-size:0.78rem;color:var(--text-3);padding:4px 0;">'
                        f'📎 {short_name} '
                        f'<span style="font-size:0.72rem;color:#c0392b;">'
                        f'(file data unreadable — please re-upload)</span></div>',
                        unsafe_allow_html=True,
                    )
            else:
                st.markdown(
                    f'<div style="font-size:0.78rem;color:var(--text-3);padding:6px 0;">'
                    f'📎 <strong style="color:var(--text-2);">{short_name}</strong> '
                    f'<span style="font-size:0.72rem;color:var(--text-3);">'
                    f'(original file not stored — ask Admin/Staff to re-upload this file '
                    f'to enable source download)</span></div>',
                    unsafe_allow_html=True,
                )
        except Exception as e:
            print(f"[chat] _source_file_download error for '{fname}': {e}")


# Keep old name as alias for backward compatibility
_source_pdf_download = _source_file_download


# ─────────────────────────────────────────────
# MAIN CHAT
# ─────────────────────────────────────────────
def render_chat(pg_url: str, api_key: str, model):
    user = st.session_state.get('user', {})
    role = user.get('role', 'student')

    st.session_state.render_gen = st.session_state.get('render_gen', 0) + 1
    gen = st.session_state.render_gen

    if time.time() - st.session_state.get('last_active_update', 0) > 60:
        try:
            update_last_active(pg_url, user['username'])
            st.session_state.last_active_update = time.time()
        except Exception:
            pass

    if not st.session_state.get('docs_loaded'):
        try:
            with st.spinner("Loading knowledge base..."):
                embeddings, chunks, doc_list, chunk_doc_names = load_all_documents_from_db(pg_url)
                st.session_state.embeddings       = embeddings
                st.session_state.chunks           = chunks
                st.session_state.doc_list         = doc_list
                st.session_state.chunk_doc_names  = chunk_doc_names
                st.session_state.docs_loaded      = True
        except Exception:
            st.session_state.embeddings       = None
            st.session_state.chunks           = []
            st.session_state.doc_list         = []
            st.session_state.chunk_doc_names  = []
            st.session_state.docs_loaded      = True

    if 'messages' not in st.session_state:
        st.session_state.messages       = []
        st.session_state.history_loaded = False

    # Welcome card — no extra hint line
    if not st.session_state.messages:
        st.markdown(f"""
        <div style="text-align:center;padding:48px 20px;">
            <div style="width:64px;height:64px;background:var(--blue);border-radius:14px;
                        display:inline-flex;align-items:center;justify-content:center;
                        color:#fff;font-weight:900;font-size:1.3rem;margin-bottom:14px;
                        box-shadow:0 4px 20px rgba(26,79,160,0.3);">SRM</div>
            <h3 style="color:var(--blue);margin-bottom:6px;font-weight:700;">Welcome, {user.get('display','!')}!</h3>
            <p style="color:var(--text-2);font-size:0.9rem;">Ask anything about your college documents.</p>
        </div>
        """, unsafe_allow_html=True)

    if st.session_state.messages:
        label = "Restored history" if st.session_state.get("history_loaded") else "Current session"
        color = "#2563c0" if st.session_state.get("history_loaded") else "#0a7c4e"
        st.markdown(
            f'<div style="font-size:0.72rem;color:{color};font-family:Inter,sans-serif;margin-bottom:10px;">'
            f'<span class="dot" style="background:{color};"></span>{label}</div>',
            unsafe_allow_html=True
        )

    for i, msg in enumerate(st.session_state.messages):
        if msg['role'] == 'user':
            st.markdown(f"""
            <div class="chat-wrap">
                <div class="chat-label">You</div>
                <div class="chat-user">{_html.escape(str(msg.get('content','')))}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            raw_conf = msg.get('confidence')
            try:
                conf_val = float(raw_conf) if raw_conf is not None else None
            except (TypeError, ValueError):
                conf_val = None
            conf_str = confidence_html(conf_val) if conf_val is not None else ""
            src_str  = ""
            if msg.get('sources'):
                try:
                    srcs = json.loads(msg['sources']) if isinstance(msg['sources'], str) else msg['sources']
                    if srcs and isinstance(srcs, list):
                        excerpts = "".join([f'<div class="src-text">"{str(s)[:130]}..."</div>' for s in srcs[:2]])
                        src_str  = f'<div class="src-wrap"><div class="src-label">Source Excerpts</div>{excerpts}</div>'
                except Exception:
                    pass
            st.markdown(f"""
            <div class="chat-wrap">
                <div class="chat-label">AI Assistant</div>
                <div class="chat-assistant">
                    {_safe_answer_html(msg.get('content',''))}
                    {conf_str}
                    {src_str}
                </div>
            </div>
            """, unsafe_allow_html=True)
            prev = st.session_state.messages[i-1].get('content','') if i > 0 else ""
            _action_row(msg.get('content',''), f"{i}_{gen}", prev, user.get('username',''), pg_url)
            src_docs = msg.get('source_docs', [])
            if src_docs:
                _source_file_download(src_docs, pg_url, f"hist_{i}_{gen}")
            _followup_chips(f"{i}_{gen}")

    if not st.session_state.messages:
        st.markdown("**Try asking:**")
        cols = st.columns(4)
        for i, sug in enumerate(SUGGESTIONS[:8]):
            with cols[i % 4]:
                if st.button(sug, key=f"sug_{i}_{gen}", use_container_width=True):
                    st.session_state.pending_query = sug

    if not check_permission(role, "query"):
        st.markdown('<div class="alert-error">Your account does not have query access.</div>', unsafe_allow_html=True)
        return

    if not api_key:
        st.markdown('<div class="alert-error">Groq API key missing.</div>', unsafe_allow_html=True)
    if st.session_state.get('embeddings') is None:
        st.markdown('<div class="alert-info">No documents loaded yet. Admin or Staff must upload documents first.</div>', unsafe_allow_html=True)
    pending = st.session_state.pop('pending_query', None)

    prompt = st.chat_input("Ask about your college documents...")

    if pending and not prompt:
        prompt = pending

    if st.session_state.get("messages"):
        try:
            mime, ext = _pdf_type()
            st.download_button(
                label="Export Chat",
                data=export_conversation_pdf(
                    st.session_state["messages"],
                    user.get("username", ""),
                ),
                file_name=f"conversation_{datetime.now().strftime('%Y%m%d_%H%M')}.{ext}",
                mime=mime,
                key=f"export_conv_{gen}",
                use_container_width=True,
            )
        except Exception:
            pass

    if not prompt:
        return

    try:
        allowed, remaining = check_rate_limit(pg_url, user['username'])
    except Exception:
        allowed, remaining = True, 30

    if not allowed:
        st.markdown('<div class="alert-warn">Rate limit reached (30/hour). Please wait.</div>', unsafe_allow_html=True)
        return
    if not api_key:
        st.markdown('<div class="alert-error">Groq API key not set.</div>', unsafe_allow_html=True)
        return
    if st.session_state.get('embeddings') is None:
        st.markdown('<div class="alert-info">No documents uploaded. Ask Admin to upload documents first.</div>', unsafe_allow_html=True)
        return

    now = datetime.now().strftime("%H:%M · %d %b %Y")
    st.session_state.messages.append({"role":"user","content":prompt,"sources":None,"confidence":None,"time":now})
    try:
        save_chat_message(pg_url, user['username'], "user", prompt)
    except Exception:
        pass

    st.markdown(f"""
    <div class="chat-wrap">
        <div class="chat-label">You</div>
        <div class="chat-user">{_html.escape(str(prompt))}</div>
    </div>
    """, unsafe_allow_html=True)

    typing_ph = st.empty()
    typing_ph.markdown("""
    <div class="chat-wrap">
        <div class="chat-label">AI Assistant</div>
        <div class="chat-assistant" style="padding:14px 20px;">
            <span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    memory_msgs = st.session_state.messages[-9:-1]
    memory_ctx  = ""
    if memory_msgs:
        memory_ctx = "\n\nCONVERSATION HISTORY:\n"
        for m in memory_msgs:
            memory_ctx += f"{'User' if m['role']=='user' else 'Assistant'}: {str(m.get('content',''))[:200]}\n"

    t0 = time.time()
    try:
        if model is not None:
            relevant_docs, scores = semantic_search(prompt, model, st.session_state.embeddings, st.session_state.chunks, n_results=5)
        else:
            relevant_docs, scores = keyword_search(prompt, st.session_state.chunks, n_results=5)
        confidence = compute_confidence(scores)
    except Exception:
        relevant_docs, scores, confidence = [], [], 0.0

    if relevant_docs:
        answer, success = generate_answer(prompt, relevant_docs, api_key, memory_context=memory_ctx, lang_instruction=LANG_AUTO_INSTRUCTION)
    else:
        answer, success, confidence = "This information is not available in the current documents. Please contact the department office directly.", True, 0.0

    ms = int((time.time() - t0) * 1000)
    typing_ph.empty()

    try:
        log_query(pg_url, user['username'], prompt, ms, confidence, success)
    except Exception:
        pass

    sources_json = json.dumps(relevant_docs[:3]) if relevant_docs else None
    try:
        save_chat_message(pg_url, user['username'], "assistant", answer, sources_json, confidence)
    except Exception:
        pass

    source_doc_names = []
    if relevant_docs:
        chunk_doc_names_map = st.session_state.get('chunk_doc_names', [])
        all_chunks_list     = st.session_state.get('chunks', [])
        for doc_chunk in relevant_docs:
            for j, c in enumerate(all_chunks_list):
                if c == doc_chunk and j < len(chunk_doc_names_map):
                    name = chunk_doc_names_map[j]
                    if name not in source_doc_names:
                        source_doc_names.append(name)
                    break

    st.session_state.messages.append({
        "role": "assistant", "content": answer,
        "sources": sources_json, "source_docs": source_doc_names,
        "confidence": confidence, "time": now
    })

    src_str = ""
    if relevant_docs:
        excerpts = "".join([f'<div class="src-text">"{str(s)[:130]}..."</div>' for s in relevant_docs[:2]])
        src_str  = f'<div class="src-wrap"><div class="src-label">Source Excerpts · {ms}ms</div>{excerpts}</div>'

    st.markdown(f"""
    <div class="chat-wrap">
        <div class="chat-label">AI Assistant</div>
        <div class="chat-assistant">
            {_safe_answer_html(answer)}
            {confidence_html(confidence)}
            {src_str}
        </div>
    </div>
    """, unsafe_allow_html=True)

    idx = len(st.session_state.messages) - 1
    _action_row(answer, f"{idx}_{gen}", prompt, user.get('username',''), pg_url)
    if source_doc_names:
        _source_file_download(source_doc_names, pg_url, f"{idx}_{gen}")
    _followup_chips(f"{idx}_{gen}")

    if remaining <= 5:
        st.markdown(f'<div class="alert-warn">You have {remaining} queries left this hour.</div>', unsafe_allow_html=True)