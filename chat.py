"""
chat.py — Chat UI.
Features: fixed mic STT, TTS read-aloud, PDF export, Telegram share.
"""

import io
import json
import time
import urllib.parse
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components

from auth import check_permission
from config import SUGGESTIONS
from database import load_all_documents_from_db, log_query, save_chat_message
from rag import compute_confidence, confidence_html, generate_answer, semantic_search


# ─────────────────────────────────────────────
# PDF EXPORT
# ─────────────────────────────────────────────
def _build_answer_pdf(question: str, answer: str) -> bytes:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.units import cm
        from reportlab.lib import colors

        buf  = io.BytesIO()
        doc  = SimpleDocTemplate(buf, pagesize=A4,
                                 leftMargin=2*cm, rightMargin=2*cm,
                                 topMargin=2*cm, bottomMargin=2*cm)
        s    = getSampleStyleSheet()
        t_st = ParagraphStyle('T', parent=s['Heading1'], textColor=colors.HexColor('#00c9a7'), fontSize=16)
        q_st = ParagraphStyle('Q', parent=s['Normal'],   textColor=colors.HexColor('#4f8ef7'), fontSize=11, spaceAfter=10, fontName='Helvetica-Bold')
        a_st = ParagraphStyle('A', parent=s['Normal'],   fontSize=11, leading=16)
        m_st = ParagraphStyle('M', parent=s['Normal'],   textColor=colors.grey, fontSize=9)
        doc.build([
            Paragraph("College AI Assistant — Answer Export", t_st),
            Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | SRM Institute, CS Dept", m_st),
            Spacer(1, 0.4*cm),
            Paragraph(f"Q: {question}", q_st),
            Paragraph(answer.replace('\n', '<br/>'), a_st),
        ])
        return buf.getvalue()
    except ImportError:
        content = f"College AI Assistant\n{'='*50}\nQ: {question}\n\nA:\n{answer}\n\nGenerated: {datetime.now()}\n"
        return content.encode("utf-8")


def _pdf_mime():
    try:
        from reportlab.lib.pagesizes import A4
        return "application/pdf", "pdf"
    except ImportError:
        return "text/plain", "txt"


# ─────────────────────────────────────────────
# SHARE ROW — PDF + Telegram
# ─────────────────────────────────────────────
def _render_share_actions(answer: str, msg_index: int, question: str = ""):
    col1, col2, _ = st.columns([2, 2, 6])
    with col1:
        mime, ext = _pdf_mime()
        st.download_button(
            label="📄 Save PDF",
            data=_build_answer_pdf(question or "College AI Query", answer),
            file_name=f"answer_{msg_index}.{ext}",
            mime=mime,
            key=f"dl_{msg_index}",
            use_container_width=True,
        )
    with col2:
        tg_text = f"College AI Assistant\n\nQ: {question}\n\nA: {answer}\n\nSRM CS Dept AI"
        tg_url  = f"https://t.me/share/url?url=&text={urllib.parse.quote(tg_text)}"
        st.markdown(
            f'<a href="{tg_url}" target="_blank" '
            f'style="display:inline-flex;align-items:center;justify-content:center;gap:6px;'
            f'padding:10px 14px;border-radius:8px;font-size:0.82rem;font-weight:600;'
            f'text-decoration:none;background:rgba(41,182,246,0.15);color:#7dd3fc;'
            f'border:1px solid rgba(41,182,246,0.3);width:100%;">✈️ Telegram</a>',
            unsafe_allow_html=True
        )


# ─────────────────────────────────────────────
# MAIN CHAT UI
# ─────────────────────────────────────────────
def render_chat(pg_url: str, api_key: str, model):
    user = st.session_state.user
    role = user['role']

    # Load knowledge base
    if not st.session_state.get('docs_loaded'):
        with st.spinner("Loading knowledge base..."):
            embeddings, chunks, doc_list = load_all_documents_from_db(pg_url)
            st.session_state.embeddings  = embeddings
            st.session_state.chunks      = chunks
            st.session_state.doc_list    = doc_list
            st.session_state.docs_loaded = True

    if 'messages' not in st.session_state:
        st.session_state.messages       = []
        st.session_state.history_loaded = False

    # Empty state
    if not st.session_state.messages:
        hint = "" if st.session_state.get("history_loaded") else \
            '<p style="font-size:0.75rem;color:var(--text-3);margin-top:8px;">Previous conversations are saved — use <b>Load History</b> in the sidebar.</p>'
        st.markdown(f"""
        <div style="text-align:center;padding:48px 20px;">
            <div style="font-size:3rem;margin-bottom:12px;">🎓</div>
            <p style="font-family:JetBrains Mono,monospace;font-size:0.9rem;color:var(--text-2);">
                Ask anything about your college documents
            </p>
            {hint}
        </div>
        """, unsafe_allow_html=True)

    # Session banner
    if st.session_state.messages:
        if st.session_state.get("history_loaded"):
            st.markdown('<div class="alert-info" style="margin-bottom:10px;">📜 Showing restored history — new messages appear below</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div style="display:inline-flex;align-items:center;gap:6px;background:rgba(0,201,167,0.06);border:1px solid rgba(0,201,167,0.15);border-radius:8px;padding:5px 12px;font-size:0.72rem;color:var(--teal);font-family:JetBrains Mono,monospace;margin-bottom:10px;"><span class="dot dot-green"></span>Current session</div>', unsafe_allow_html=True)

    # Render message history
    for i, msg in enumerate(st.session_state.messages):
        if msg['role'] == 'user':
            st.markdown(f"""
            <div class="chat-wrap">
                <div class="chat-label">You</div>
                <div class="chat-user">{msg['content']}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            conf_str = confidence_html(float(msg['confidence'])) if msg.get('confidence') is not None else ""
            src_str  = ""
            if msg.get('sources'):
                try:
                    srcs = json.loads(msg['sources'])
                    if srcs:
                        excerpts = "".join([f'<div class="src-text">"{s[:130]}..."</div>' for s in srcs[:2]])
                        src_str  = f'<div class="src-wrap"><div class="src-label">Source Excerpts</div>{excerpts}</div>'
                except Exception:
                    pass

            st.markdown(f"""
            <div class="chat-wrap">
                <div class="chat-label">AI Assistant</div>
                <div class="chat-assistant">
                    {msg['content']}
                    {conf_str}
                    {src_str}
                </div>
            </div>
            """, unsafe_allow_html=True)
            _render_share_actions(msg['content'], i)

    # Suggestions (empty state)
    if not st.session_state.messages:
        st.markdown("**Try asking:**")
        cols = st.columns(4)
        for i, sug in enumerate(SUGGESTIONS[:8]):
            with cols[i % 4]:
                if st.button(sug, key=f"sug_{i}", use_container_width=True):
                    st.session_state.pending_query = sug

    if not check_permission(role, "query"):
        st.markdown('<div class="alert-error">Your account does not have query access.</div>', unsafe_allow_html=True)
        return

    # Validation banners
    if not api_key:
        st.markdown('<div class="alert-error">Groq API key missing — add it to secrets.toml.</div>', unsafe_allow_html=True)
    if st.session_state.get('embeddings') is None:
        st.markdown('<div class="alert-info">No documents loaded yet. Admin or Staff must upload PDFs first.</div>', unsafe_allow_html=True)
    if model is None:
        st.markdown('<div class="alert-error">Semantic model unavailable — install sentence-transformers.</div>', unsafe_allow_html=True)

    pending = st.session_state.pop('pending_query', None)

    # ── Input row: mic + chat input ──
    col_mic, col_input = st.columns([1, 11])
    with col_mic:
        mic_active = st.session_state.get('mic_active', False)
        if st.button("🔴" if mic_active else "🎤", key="mic_toggle",
                     help="Click to speak (Chrome/Edge only)",
                     use_container_width=True):
            st.session_state.mic_active       = not mic_active
            st.session_state.mic_just_toggled = True
            st.rerun()

    # Mic live preview — no timestamp here
    if st.session_state.get('mic_active'):
        st.markdown("""
        <div class="mic-banner">
            🔴 <span id="chat-voice-text">Listening — speak now...</span>
        </div>
        """, unsafe_allow_html=True)

    with col_input:
        prompt = st.chat_input("Ask about your college documents...") or pending

    # ── TTS toggle — clean, no timestamp ──
    tts_on = st.session_state.get('tts_enabled', True)
    c1, c2 = st.columns([3, 9])
    with c1:
        if st.button(
            "🔊 Read Aloud: ON" if tts_on else "🔇 Read Aloud: OFF",
            key="tts_toggle", use_container_width=True
        ):
            st.session_state.tts_enabled = not tts_on
            st.rerun()

    # ── JS: STT + TTS ──
    mic_toggle_id = st.session_state.get('mic_toggle_count', 0)
    if st.session_state.pop('mic_just_toggled', False):
        mic_toggle_id += 1
        st.session_state.mic_toggle_count = mic_toggle_id

    tts_js     = "true"  if tts_on                              else "false"
    mic_js     = "true"  if st.session_state.get('mic_active') else "false"

    components.html(f"""
    <script>
    (function() {{
        const _id      = {mic_toggle_id};
        const ttsOn    = {tts_js};
        const micOn    = {mic_js};
        const synth    = window.parent.speechSynthesis;

        // TTS — speak last assistant message
        function speakLast() {{
            if (!ttsOn || !synth) return;
            synth.cancel();
            const msgs = window.parent.document.querySelectorAll('.chat-assistant');
            if (!msgs.length) return;
            const last = msgs[msgs.length - 1];
            if (last.dataset.spoken === 'true') return;
            const clone = last.cloneNode(true);
            clone.querySelectorAll('.conf-wrap,.src-wrap,.share-row').forEach(e => e.remove());
            let text = clone.textContent.replace(/[ \\t\\n\\r]+/g,' ').trim();
            if (text.length > 800) text = text.substring(0,800) + '...';
            const utt  = new SpeechSynthesisUtterance(text);
            utt.lang   = 'en-IN'; utt.rate = 0.92; utt.pitch = 1.0;
            const voices = synth.getVoices();
            const voice  = voices.find(v=>v.lang==='en-IN') || voices.find(v=>v.lang.startsWith('en-')) || voices[0];
            if (voice) utt.voice = voice;
            last.dataset.spoken = 'true';
            synth.speak(utt);
        }}
        new MutationObserver(() => {{
            const msgs = window.parent.document.querySelectorAll('.chat-assistant');
            if (!msgs.length) return;
            const last = msgs[msgs.length - 1];
            if (last && last.dataset.spoken !== 'true') speakLast();
        }}).observe(window.parent.document.body, {{ childList:true, subtree:true }});

        // STT — start only when mic is on
        if (!micOn) return;
        const SR = window.parent.SpeechRecognition || window.parent.webkitSpeechRecognition;
        if (!SR) {{
            const el = window.parent.document.getElementById('chat-voice-text');
            if (el) el.textContent = 'SpeechRecognition not supported — use Chrome or Edge';
            return;
        }}
        if (window._rec) {{ try {{ window._rec.stop(); }} catch(e) {{}} }}
        const rec = new SR();
        window._rec = rec;
        rec.lang = 'en-IN'; rec.interimResults = true; rec.continuous = true; rec.maxAlternatives = 1;
        const liveEl = window.parent.document.getElementById('chat-voice-text');

        rec.onstart  = () => {{ if (liveEl) liveEl.textContent = 'Listening — speak now...'; }};
        rec.onresult = (e) => {{
            let interim='', final='';
            for (let i=e.resultIndex; i<e.results.length; i++) {{
                const t = e.results[i][0].transcript;
                if (e.results[i].isFinal) final += t; else interim += t;
            }}
            if (liveEl) liveEl.textContent = final || interim || 'Listening...';
            if (final) {{
                const inp = window.parent.document.querySelector('textarea[data-testid="stChatInputTextArea"]');
                if (inp) {{
                    const set = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype,'value').set;
                    set.call(inp, final.trim());
                    inp.dispatchEvent(new Event('input',{{bubbles:true}}));
                    inp.focus();
                    setTimeout(()=>inp.dispatchEvent(new KeyboardEvent('keydown',{{key:'Enter',keyCode:13,bubbles:true}})),300);
                }}
            }}
        }};
        rec.onerror = (e) => {{ if (liveEl) liveEl.textContent = 'Mic error: '+e.error+' — try again'; }};
        rec.onend   = () => {{ if ({mic_js}) {{ try {{ rec.start(); }} catch(e) {{}} }} }};
        try {{ rec.start(); }} catch(e) {{ if (liveEl) liveEl.textContent = 'Could not start mic: '+e.message; }}
    }})();
    </script>
    """, height=0)

    if not prompt:
        return

    # Guards
    if not api_key:
        st.markdown('<div class="alert-error">Groq API key not set.</div>', unsafe_allow_html=True); return
    if st.session_state.get('embeddings') is None:
        st.markdown('<div class="alert-info">No documents in knowledge base.</div>', unsafe_allow_html=True); return
    if model is None:
        st.markdown('<div class="alert-error">Semantic model not loaded.</div>', unsafe_allow_html=True); return

    # Show user message
    now = datetime.now().strftime("%H:%M · %d %b %Y")
    st.session_state.messages.append({"role":"user","content":prompt,"sources":None,"confidence":None,"time":now})
    save_chat_message(pg_url, user['username'], "user", prompt)
    st.markdown(f"""
    <div class="chat-wrap">
        <div class="chat-label">You</div>
        <div class="chat-user">{prompt}</div>
    </div>
    """, unsafe_allow_html=True)

    # Generate answer
    with st.spinner("Searching documents..."):
        t0 = time.time()
        relevant_docs, scores = semantic_search(prompt, model, st.session_state.embeddings, st.session_state.chunks, n_results=5)
        confidence = compute_confidence(scores)
        if relevant_docs:
            answer, success = generate_answer(prompt, relevant_docs, api_key)
        else:
            answer, success, confidence = "No relevant information found in the uploaded documents. Please ask an admin to upload more documents.", True, 0.0
        ms = int((time.time() - t0) * 1000)

    log_query(pg_url, user['username'], prompt, ms, confidence, success)
    sources_json = json.dumps(relevant_docs[:3]) if relevant_docs else None
    save_chat_message(pg_url, user['username'], "assistant", answer, sources_json, confidence)

    ai_msg = {"role":"assistant","content":answer,"sources":sources_json,"confidence":confidence,"time":datetime.now().strftime("%H:%M · %d %b %Y")}
    st.session_state.messages.append(ai_msg)

    conf_str = confidence_html(confidence)
    src_str  = ""
    if relevant_docs:
        excerpts = "".join([f'<div class="src-text">"{s[:130]}..."</div>' for s in relevant_docs[:2]])
        src_str  = f'<div class="src-wrap"><div class="src-label">Source Excerpts · {ms}ms</div>{excerpts}</div>'

    st.markdown(f"""
    <div class="chat-wrap">
        <div class="chat-label">AI Assistant</div>
        <div class="chat-assistant">
            {answer}
            {conf_str}
            {src_str}
        </div>
    </div>
    """, unsafe_allow_html=True)

    _render_share_actions(answer, len(st.session_state.messages) - 1, question=prompt)
    st.rerun()