"""
chat.py — Full chat UI.
"""

import html as _html
import io
import json
import re
import time
import urllib.parse
from datetime import datetime

import streamlit as st

from auth import check_permission
from config import SUGGESTIONS
from database import (
    load_all_documents_from_db, log_query, save_chat_message,
    save_feedback, check_rate_limit, update_last_active
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
    """
    Convert AI answer markdown → safe HTML for embedding in st.markdown HTML blocks.

    Uses a placeholder strategy so code blocks are extracted first,
    text is HTML-escaped, markdown is converted, then placeholders restored.
    This prevents backticks / asterisks from breaking Streamlit's parser.
    """
    t = str(text)
    saved: list[str] = []

    # ── 1. Extract fenced code blocks into placeholders ──────────────────────
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

    # ── 2. Extract inline code into placeholders ─────────────────────────────
    def save_inline(m):
        code = _html.escape(m.group(1))
        html = (
            '<code style="background:var(--bg-3);padding:1px 5px;border-radius:4px;'
            f'font-size:0.85em;font-family:JetBrains Mono,monospace;">{code}</code>'
        )
        saved.append(html)
        return f"\x00PH{len(saved)-1}\x00"

    t = re.sub(r'`([^`\n]+)`', save_inline, t)

    # ── 3. Process line by line: bullets + HTML-escape + inline markdown ─────
    def apply_inline_md(s: str) -> str:
        s = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s)
        s = re.sub(r'__(.+?)__',     r'<strong>\1</strong>', s)
        # Italic — only *word* not inside ** (avoid matching lone asterisks)
        s = re.sub(r'(?<!\*)\*([^*\n]+?)\*(?!\*)', r'<em>\1</em>', s)
        return s

    lines     = t.split('\n')
    out_lines = []
    in_list   = False

    for line in lines:
        stripped = line.lstrip()
        # Detect bullet: lines starting with "* ", "- ", or "• "
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

    # ── 4. Join and convert plain newlines → <br/> (skip around list tags) ───
    result = '\n'.join(out_lines)
    result = re.sub(r'\n(<[uo]l)',    r'\1',    result)   # no <br/> before <ul>/<ol>
    result = re.sub(r'(</[uo]l>)\n', r'\1',    result)   # no <br/> after </ul>/<ol>
    result = result.replace('\n', '<br/>')

    # ── 5. Restore code block placeholders ───────────────────────────────────
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
# FIX: removed components.html entirely — was leaking raw HTML into the page.
# Telegram share is a plain markdown anchor. Copy removed (was the leak source).
# ─────────────────────────────────────────────
def _action_row(answer: str, msg_key: str, question: str, username: str, pg_url: str):
    mime, ext = _pdf_type()
    tg_text   = f"College AI Assistant\n\nQ: {question}\n\nA: {answer}\n\nSRM CS Dept"
    tg_enc    = urllib.parse.quote(tg_text)
    tg_deep   = f"tg://msg?text={tg_enc}"      # opens Telegram desktop / mobile app
    tg_web    = f"https://t.me/share/url?url=&text={tg_enc}"  # web fallback

    st.markdown(f"""
    <div style="margin-top:8px;margin-bottom:4px;">
        <a href="#"
           onclick="(function(){{
               var tried = false;
               window.location.href = '{tg_deep}';
               setTimeout(function(){{
                   if (!tried) {{ tried = true; window.open('{tg_web}', '_blank'); }}
               }}, 1500);
           }})(); return false;"
           style="display:inline-flex;align-items:center;gap:5px;padding:5px 14px;
                  border-radius:6px;font-size:0.78rem;font-weight:500;
                  border:1px solid var(--border-2);background:var(--bg-3);
                  color:var(--text-2);text-decoration:none;cursor:pointer;">
            Share on Telegram
        </a>
    </div>
    """, unsafe_allow_html=True)

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
        rows += f'<span class="followup-chip" onclick="(function(){{var i=document.querySelector(\'textarea[data-testid=stChatInputTextArea]\');if(i){{Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,\'value\').set.call(i,\'{safe}\');i.dispatchEvent(new Event(\'input\',{{bubbles:true}}));i.focus();}}}})()">{c}</span>'
    st.markdown(f"""
    <div class="followup-wrap">
        <div class="followup-label">Follow-up suggestions</div>
        {rows}
    </div>
    """, unsafe_allow_html=True)



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
                embeddings, chunks, doc_list = load_all_documents_from_db(pg_url)
                st.session_state.embeddings  = embeddings
                st.session_state.chunks      = chunks
                st.session_state.doc_list    = doc_list
                st.session_state.docs_loaded = True
        except Exception:
            st.session_state.embeddings  = None
            st.session_state.chunks      = []
            st.session_state.doc_list    = []
            st.session_state.docs_loaded = True

    if 'messages' not in st.session_state:
        st.session_state.messages       = []
        st.session_state.history_loaded = False

    if not st.session_state.messages:
        st.markdown(f"""
        <div style="text-align:center;padding:48px 20px;">
            <div style="width:64px;height:64px;background:var(--blue);border-radius:14px;
                        display:inline-flex;align-items:center;justify-content:center;
                        color:#fff;font-weight:900;font-size:1.3rem;margin-bottom:14px;
                        box-shadow:0 4px 20px rgba(26,79,160,0.3);">SRM</div>
            <h3 style="color:var(--blue);margin-bottom:6px;font-weight:700;">Welcome, {user.get('display','!')}!</h3>
            <p style="color:var(--text-2);font-size:0.9rem;">Ask anything about your college documents.</p>
            {'<p style="font-size:0.75rem;color:var(--text-3);margin-top:6px;">Previous conversations saved — use Load History in sidebar.</p>' if not st.session_state.get("history_loaded") else ''}
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
        st.markdown('<div class="alert-info">No documents loaded yet. Admin or Staff must upload PDFs first.</div>', unsafe_allow_html=True)
    pending = st.session_state.pop('pending_query', None)

    # --- Chat input ---
    prompt = st.chat_input("Ask about your college documents...")

    # Apply any pending suggestion query
    if pending and not prompt:
        prompt = pending

    # --- Export Chat ---
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

    # If no prompt, do nothing
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
        st.markdown('<div class="alert-info">No documents uploaded. Ask Admin to upload PDFs first.</div>', unsafe_allow_html=True)
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

    st.session_state.messages.append({"role":"assistant","content":answer,"sources":sources_json,"confidence":confidence,"time":now})

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
    _followup_chips(f"{idx}_{gen}")

    if remaining <= 5:
        st.markdown(f'<div class="alert-warn">You have {remaining} queries left this hour.</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────
# SUMMARIZE & DOWNLOAD  (all roles)
# ─────────────────────────────────────────────
def _build_summary_pdf(query: str, summary: str, username: str) -> bytes:
    """Build a clean PDF for a single summary result."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
        from reportlab.lib.units import cm
        from reportlab.lib import colors

        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf, pagesize=A4,
            leftMargin=2*cm, rightMargin=2*cm,
            topMargin=2*cm, bottomMargin=2*cm,
        )
        s = getSampleStyleSheet()

        title_st = ParagraphStyle(
            'T', parent=s['Heading1'],
            textColor=colors.HexColor('#00c9a7'),
            fontSize=16, spaceAfter=4,
        )
        meta_st = ParagraphStyle(
            'M', parent=s['Normal'],
            textColor=colors.grey, fontSize=9, spaceAfter=14,
        )
        q_st = ParagraphStyle(
            'Q', parent=s['Normal'],
            textColor=colors.HexColor('#4f8ef7'),
            fontSize=12, fontName='Helvetica-Bold', spaceAfter=10,
        )
        body_st = ParagraphStyle(
            'B', parent=s['Normal'],
            fontSize=11, leading=17, spaceAfter=8,
        )

        def esc(t: str) -> str:
            return str(t).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('\n', '<br/>')

        story = [
            Paragraph("SRM College AI Assistant — Summary", title_st),
            Paragraph(
                f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}  |  "
                f"User: {username}  |  SRM Institute CS Dept",
                meta_st,
            ),
            HRFlowable(width="100%", thickness=1, color=colors.HexColor('#2a2f45')),
            Spacer(1, 0.35*cm),
            Paragraph(f"Query: {esc(query)}", q_st),
            Spacer(1, 0.15*cm),
            Paragraph(esc(summary), body_st),
        ]
        doc.build(story)
        return buf.getvalue()
    except Exception:
        txt = (
            f"SRM College AI Assistant — Summary\n"
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}  |  User: {username}\n"
            f"{'='*60}\n\n"
            f"Query: {query}\n\n"
            f"Summary:\n{summary}\n"
        )
        return txt.encode("utf-8")


def _build_summary_txt(query: str, summary: str, username: str) -> bytes:
    txt = (
        f"SRM College AI Assistant — Summary\n"
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"User: {username}  |  SRM Institute CS Dept\n"
        f"{'='*60}\n\n"
        f"Query:\n{query}\n\n"
        f"Summary:\n{summary}\n"
    )
    return txt.encode("utf-8")


def render_summarize(pg_url: str, api_key: str, model):
    """Standalone Summarize & Download tab — available to all roles."""
    import requests as _req

    user = st.session_state.get('user', {})
    username = user.get('username', 'unknown')

    st.markdown("""
    <div style="margin-bottom:18px;">
        <div style="font-size:1.05rem;font-weight:700;color:var(--blue);margin-bottom:6px;">
            Summarize & Download
        </div>
        <div style="font-size:0.83rem;color:var(--text-2);line-height:1.6;">
            Type any question or topic. The AI will search the college knowledge base,
            generate a focused summary, and let you download the result as a <b>PDF</b> or <b>TXT</b> file.
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Ensure docs are loaded
    if not st.session_state.get('docs_loaded'):
        try:
            with st.spinner("Loading knowledge base..."):
                from database import load_all_documents_from_db
                embeddings, chunks, doc_list = load_all_documents_from_db(pg_url)
                st.session_state.embeddings  = embeddings
                st.session_state.chunks      = chunks
                st.session_state.doc_list    = doc_list
                st.session_state.docs_loaded = True
        except Exception:
            st.session_state.embeddings  = None
            st.session_state.chunks      = []
            st.session_state.docs_loaded = True

    if not api_key:
        st.markdown('<div class="alert-error">Groq API key missing — cannot generate summaries.</div>', unsafe_allow_html=True)
        return
    if st.session_state.get('embeddings') is None:
        st.markdown('<div class="alert-info">No documents in the knowledge base yet. Ask Admin or Staff to upload PDFs first.</div>', unsafe_allow_html=True)
        return

    # ── Input ──
    query = st.text_area(
        "Enter your query or topic",
        placeholder="e.g. Summarise the attendance policy for CS students",
        height=110,
        key="summarize_query_input",
    )

    col_btn, col_clr = st.columns([2, 1])
    with col_btn:
        run = st.button("Generate Summary", use_container_width=True, type="primary")
    with col_clr:
        if st.button("Clear", use_container_width=True):
            for k in ("summarize_result", "summarize_query_done"):
                st.session_state.pop(k, None)
            st.rerun()

    if run:
        if not query or not query.strip():
            st.warning("Please enter a query before generating a summary.")
        else:
            with st.spinner("Searching documents and generating summary…"):
                try:
                    if model is not None:
                        relevant_docs, scores = semantic_search(
                            query, model,
                            st.session_state.embeddings,
                            st.session_state.chunks,
                            n_results=6,
                        )
                    else:
                        relevant_docs, scores = keyword_search(query, st.session_state.chunks, n_results=6)
                    confidence = compute_confidence(scores)
                except Exception:
                    relevant_docs, scores, confidence = [], [], 0.0

                if not relevant_docs:
                    st.session_state.summarize_result      = "This information is not available in the current documents. Please contact the department office directly."
                    st.session_state.summarize_query_done  = query.strip()
                    st.session_state.summarize_confidence  = 0.0
                else:
                    context_text = "\n\n---\n\n".join(relevant_docs)
                    summary_prompt = f"""You are a precise College AI Assistant for SRM Institute of Science and Technology, CS Department.

TASK: Generate a clear, well-structured SUMMARY based ONLY on the document context below.

RULES:
1. Use only information explicitly present in the DOCUMENT CONTEXT.
2. Structure the summary with a brief introduction, key points (as bullet list), and a short conclusion.
3. If information is missing, state: "Some details are not available in the current documents."
4. Be concise, factual, and formal.
5. Do NOT invent or infer data not present in the context.

DOCUMENT CONTEXT:
{context_text}

TOPIC / QUERY: {query.strip()}

SUMMARY:"""

                    ok = False
                    summary = ""
                    for attempt in range(3):
                        try:
                            resp = _req.post(
                                "https://api.groq.com/openai/v1/chat/completions",
                                headers={
                                    "Authorization": f"Bearer {api_key}",
                                    "Content-Type": "application/json",
                                },
                                json={
                                    "model": "llama-3.3-70b-versatile",
                                    "messages": [{"role": "user", "content": summary_prompt}],
                                    "temperature": 0.2,
                                    "max_tokens": 700,
                                },
                                timeout=30,
                            )
                            if resp.status_code == 200:
                                data = resp.json()
                                if data.get('choices'):
                                    summary = data['choices'][0]['message']['content']
                                    ok = True
                                break
                            elif resp.status_code == 429 and attempt < 2:
                                import time as _t; _t.sleep(2 ** attempt)
                                continue
                            else:
                                summary = f"API error: HTTP {resp.status_code}"
                                break
                        except Exception as exc:
                            summary = f"Error generating summary: {exc}"
                            break

                    if not ok and not summary:
                        summary = "Failed to generate summary. Please try again."

                    st.session_state.summarize_result     = summary
                    st.session_state.summarize_query_done = query.strip()
                    st.session_state.summarize_confidence = confidence

    # ── Show result ──
    if st.session_state.get("summarize_result"):
        done_q   = st.session_state.get("summarize_query_done", "")
        summary  = st.session_state["summarize_result"]
        conf_val = st.session_state.get("summarize_confidence", 0.0)

        st.markdown("<hr class='divider'>", unsafe_allow_html=True)

        st.markdown(f"""
        <div style="margin-bottom:10px;">
            <div style="font-size:0.75rem;color:var(--text-3);margin-bottom:4px;">Query</div>
            <div style="font-size:0.88rem;font-weight:600;color:var(--blue);">{_html.escape(done_q)}</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
        <div class="chat-wrap" style="margin-bottom:14px;">
            <div class="chat-label">Summary</div>
            <div class="chat-assistant">
                {_safe_answer_html(summary)}
                {confidence_html(conf_val)}
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ── Download buttons ──
        mime_pdf, ext_pdf = _pdf_type()
        ts = datetime.now().strftime('%Y%m%d_%H%M')

        st.markdown("**Download Summary**")
        dl1, dl2 = st.columns(2)

        with dl1:
            try:
                pdf_bytes = _build_summary_pdf(done_q, summary, username)
                st.download_button(
                    label="Download as PDF",
                    data=pdf_bytes,
                    file_name=f"summary_{ts}.{ext_pdf}",
                    mime=mime_pdf,
                    use_container_width=True,
                    key="dl_summary_pdf",
                )
            except Exception:
                pass

        with dl2:
            try:
                txt_bytes = _build_summary_txt(done_q, summary, username)
                st.download_button(
                    label="Download as TXT",
                    data=txt_bytes,
                    file_name=f"summary_{ts}.txt",
                    mime="text/plain",
                    use_container_width=True,
                    key="dl_summary_txt",
                )
            except Exception:
                pass