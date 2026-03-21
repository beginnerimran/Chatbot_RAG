"""
chat.py — Chat UI with:
  - Fixed microphone / STT (Web Speech API, properly re-triggered on toggle)
  - Text-to-speech read-aloud
  - PDF export of any AI answer
  - WhatsApp share (opens wa.me with text pre-filled — free, instant)
"""

import io
import json
import textwrap
import time
import urllib.parse
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components

from auth import check_permission
from config import SUGGESTIONS
from database import (
    load_all_documents_from_db,
    log_query,
    save_chat_message,
)
from rag import (
    compute_confidence,
    confidence_html,
    generate_answer,
    semantic_search,
)


# ─────────────────────────────────────────────
# PDF EXPORT HELPER
# ─────────────────────────────────────────────
def _build_answer_pdf(question: str, answer: str) -> bytes:
    """
    Build a simple PDF from a Q&A pair using only stdlib (no extra deps).
    Uses reportlab if available, falls back to a plain UTF-8 text bytes.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.units import cm
        from reportlab.lib import colors

        buf    = io.BytesIO()
        doc    = SimpleDocTemplate(buf, pagesize=A4,
                                   leftMargin=2*cm, rightMargin=2*cm,
                                   topMargin=2*cm, bottomMargin=2*cm)
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('Title2', parent=styles['Heading1'],
                                     textColor=colors.HexColor('#00d4aa'), fontSize=16)
        q_style = ParagraphStyle('Q', parent=styles['Normal'],
                                 textColor=colors.HexColor('#3b82f6'), fontSize=11,
                                 spaceAfter=10, fontName='Helvetica-Bold')
        a_style = ParagraphStyle('A', parent=styles['Normal'],
                                 fontSize=11, leading=16, spaceAfter=6)
        meta_style = ParagraphStyle('Meta', parent=styles['Normal'],
                                    textColor=colors.grey, fontSize=9)
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        story = [
            Paragraph("🎓 College AI Assistant — Answer Export", title_style),
            Paragraph(f"Generated: {now} &nbsp;|&nbsp; SRM Institute, CS Dept", meta_style),
            Spacer(1, 0.4*cm),
            Paragraph(f"Q: {question}", q_style),
            Paragraph(answer.replace('\n', '<br/>'), a_style),
        ]
        doc.build(story)
        return buf.getvalue()

    except ImportError:
        # Fallback — plain text bytes that browsers will offer as a .txt download
        content = f"College AI Assistant — Answer Export\n{'='*50}\n\nQ: {question}\n\nA:\n{answer}\n\nGenerated: {datetime.now()}\n"
        return content.encode("utf-8")


def _get_pdf_mime() -> str:
    try:
        from reportlab.lib.pagesizes import A4
        return "application/pdf"
    except ImportError:
        return "text/plain"


def _get_pdf_ext() -> str:
    try:
        from reportlab.lib.pagesizes import A4
        return "pdf"
    except ImportError:
        return "txt"


# ─────────────────────────────────────────────
# CHAT RENDER
# ─────────────────────────────────────────────
def render_chat(pg_url: str, api_key: str, model):
    user = st.session_state.user
    role = user['role']

    st.markdown(f"""
    <div class="app-header">
        <div>
            <h1>🎓 College AI Assistant</h1>
            <p>// Centralising Departmental Knowledge via Semantic RAG &nbsp;|&nbsp;
               <span class="role-badge role-{role}">{role}</span> &nbsp;{user['display']}
            </p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Load embeddings from DB ──
    if not st.session_state.get('docs_loaded'):
        with st.spinner("Loading knowledge base from database..."):
            embeddings, chunks, doc_list = load_all_documents_from_db(pg_url)
            st.session_state.embeddings  = embeddings
            st.session_state.chunks      = chunks
            st.session_state.doc_list    = doc_list
            st.session_state.docs_loaded = True

    if 'messages' not in st.session_state:
        st.session_state.messages       = []
        st.session_state.history_loaded = False

    # ── Empty state ──
    if not st.session_state.messages:
        history_hint = "" if st.session_state.get("history_loaded") else \
            '<div style="font-size:0.75rem;color:#334155;margin-top:8px;font-family:IBM Plex Mono,monospace;">📜 Previous conversations saved — click <b style="color:#475569;">Load My History</b> in the sidebar.</div>'
        st.markdown(f"""
        <div style="text-align:center;padding:40px 20px;color:#475569;">
            <div style="font-size:2.5rem;">🎓</div>
            <div style="font-family:'IBM Plex Mono',monospace;font-size:0.85rem;margin-top:12px;color:#64748b;">
                New session started — ask anything about your college documents
            </div>
            {history_hint}
        </div>
        """, unsafe_allow_html=True)

    # ── Session banner ──
    if st.session_state.messages:
        if st.session_state.get("history_loaded"):
            st.markdown('<div style="background:rgba(59,130,246,0.08);border:1px solid rgba(59,130,246,0.2);border-radius:8px;padding:8px 14px;font-size:0.75rem;color:#60a5fa;font-family:IBM Plex Mono,monospace;margin-bottom:8px;">📜 Showing restored history</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div style="background:rgba(0,212,170,0.06);border:1px solid rgba(0,212,170,0.15);border-radius:8px;padding:8px 14px;font-size:0.75rem;color:#00d4aa;font-family:IBM Plex Mono,monospace;margin-bottom:8px;">🟢 Current session</div>', unsafe_allow_html=True)

    # ── Render message history ──
    for i, msg in enumerate(st.session_state.messages):
        if msg['role'] == 'user':
            st.markdown(f"""
            <div class="chat-label">YOU</div>
            <div class="chat-user">{msg['content']}</div>
            <div class="msg-time">{msg.get('time','')}</div>
            """, unsafe_allow_html=True)
        else:
            conf_html_str = ""
            if msg.get('confidence') is not None:
                conf_html_str = confidence_html(float(msg['confidence']))

            src_html = ""
            if msg.get('sources'):
                try:
                    srcs = json.loads(msg['sources'])
                    if srcs:
                        excerpts = "".join([f'<div class="source-text">"{s[:130]}..."</div>' for s in srcs[:2]])
                        src_html = f'<div class="source-chips"><div class="source-label">📎 Source Excerpts</div>{excerpts}</div>'
                except Exception:
                    pass

            st.markdown(f"""
            <div class="chat-label">AI ASSISTANT</div>
            <div class="chat-assistant">
                {msg['content']}
                {conf_html_str}
                {src_html}
            </div>
            <div class="msg-time">{msg.get('time','')}</div>
            """, unsafe_allow_html=True)

            # ── Share actions: Download PDF + WhatsApp ──
            _render_share_actions(msg['content'], i)

    # ── Suggestions ──
    if not st.session_state.messages:
        st.markdown("**💡 Try asking:**")
        cols = st.columns(4)
        for i, sug in enumerate(SUGGESTIONS[:8]):
            with cols[i % 4]:
                if st.button(sug, key=f"sug_{i}", use_container_width=True):
                    st.session_state.pending_query = sug

    if not check_permission(role, "query"):
        st.markdown('<div class="alert-error">🔒 Your account does not have query access.</div>', unsafe_allow_html=True)
        return

    # ── Validation banners ──
    if not api_key:
        st.markdown('<div class="alert-error">⚠️ <strong>Groq API key missing.</strong></div>', unsafe_allow_html=True)
    if st.session_state.get('embeddings') is None:
        st.markdown('<div class="alert-info">ℹ️ <strong>No documents loaded.</strong> Ask Admin/Staff to upload PDFs first.</div>', unsafe_allow_html=True)
    if model is None:
        st.markdown('<div class="alert-error">❌ <strong>Semantic model unavailable.</strong> Install sentence-transformers.</div>', unsafe_allow_html=True)

    pending = st.session_state.pop('pending_query', None)

    # ── Mic toggle ──
    col_mic, col_input = st.columns([1, 11])
    with col_mic:
        mic_active = st.session_state.get('mic_active', False)
        mic_label  = "🔴" if mic_active else "🎤"
        if st.button(mic_label, key="mic_toggle",
                     help="Click to speak your question (Chrome/Edge only)",
                     use_container_width=True):
            st.session_state.mic_active = not mic_active
            st.session_state.mic_just_toggled = True
            st.rerun()

    if st.session_state.get('mic_active'):
        st.markdown("""
        <div id="chat-voice-preview" style="
            background:rgba(239,68,68,0.08);border:1px dashed rgba(239,68,68,0.4);
            border-radius:8px;padding:8px 14px;margin-bottom:6px;
            font-family:'IBM Plex Mono',monospace;font-size:0.82rem;color:#fca5a5;">
            🔴 <span id="chat-voice-text">Listening — start speaking...</span>
        </div>
        """, unsafe_allow_html=True)

    with col_input:
        prompt = st.chat_input("Ask about your college documents...") or pending

    # ── TTS toggle ──
    tts_on = st.session_state.get('tts_enabled', True)
    c1, c2, c3 = st.columns([2, 2, 4])
    with c1:
        if st.button(f"{'🔊 Read Aloud: ON' if tts_on else '🔇 Read Aloud: OFF'}",
                     key="tts_toggle", use_container_width=True):
            st.session_state.tts_enabled = not tts_on
            st.rerun()
    with c2:
        if st.session_state.get('mic_active'):
            st.markdown('<div style="color:#ef4444;font-size:0.78rem;font-family:IBM Plex Mono,monospace;padding:8px 0;">🔴 Listening — speak now</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div style="color:#475569;font-size:0.72rem;font-family:IBM Plex Mono,monospace;padding:8px 0;">🎤 Click mic to speak</div>', unsafe_allow_html=True)

    # ── ★ FIXED: Mic STT + TTS via JS ──
    # Key fix: we pass a unique `micToggleId` that changes every time the mic is toggled.
    # This forces Streamlit to re-inject the script, restarting SpeechRecognition fresh.
    mic_toggle_id = st.session_state.get('mic_toggle_count', 0)
    if st.session_state.pop('mic_just_toggled', False):
        mic_toggle_id += 1
        st.session_state.mic_toggle_count = mic_toggle_id

    tts_enabled_js = "true" if tts_on else "false"
    mic_active_js  = "true" if st.session_state.get('mic_active') else "false"

    components.html(f"""
    <script>
    (function() {{
        // Unique ID prevents browser from caching and skipping this script block
        const _runId = {mic_toggle_id};
        const ttsEnabled = {tts_enabled_js};
        const micActive  = {mic_active_js};
        const synth      = window.parent.speechSynthesis;

        // ── TTS: auto-speak last assistant message ──
        function speakLast() {{
            if (!ttsEnabled || !synth) return;
            synth.cancel();
            const msgs = window.parent.document.querySelectorAll('.chat-assistant');
            if (!msgs.length) return;
            const last  = msgs[msgs.length - 1];
            if (last.dataset.spoken === 'true') return;
            const clone = last.cloneNode(true);
            clone.querySelectorAll('.confidence-bar-wrap,.source-chips,.share-btn-row').forEach(el => el.remove());
            let text = clone.textContent.replace(/[ \\t\\n\\r]+/g,' ').trim();
            if (text.length > 800) text = text.substring(0,800) + '...';
            const utt  = new SpeechSynthesisUtterance(text);
            utt.lang   = 'en-IN';
            utt.rate   = 0.92;
            utt.pitch  = 1.0;
            const voices = synth.getVoices();
            const voice  = voices.find(v => v.lang==='en-IN') || voices.find(v => v.lang.startsWith('en-')) || voices[0];
            if (voice) utt.voice = voice;
            last.dataset.spoken = 'true';
            synth.speak(utt);
        }}

        const observer = new MutationObserver(() => {{
            const msgs = window.parent.document.querySelectorAll('.chat-assistant');
            if (!msgs.length) return;
            const last = msgs[msgs.length - 1];
            if (last && last.dataset.spoken !== 'true') speakLast();
        }});
        observer.observe(window.parent.document.body, {{ childList:true, subtree:true }});

        // ── STT: start recognition ONLY when mic is active ──
        if (!micActive) return;

        const SR = window.parent.SpeechRecognition || window.parent.webkitSpeechRecognition;
        if (!SR) {{
            const el = window.parent.document.getElementById('chat-voice-text');
            if (el) el.textContent = '⚠️ SpeechRecognition not supported — use Chrome or Edge';
            return;
        }}

        // Stop any previous recognition instance
        if (window._collegeRecognition) {{
            try {{ window._collegeRecognition.stop(); }} catch(e) {{}}
        }}

        const recognition = new SR();
        window._collegeRecognition = recognition;
        recognition.lang             = 'en-IN';
        recognition.interimResults   = true;
        recognition.continuous       = true;
        recognition.maxAlternatives  = 1;

        const liveEl = window.parent.document.getElementById('chat-voice-text');

        recognition.onstart = () => {{
            if (liveEl) liveEl.textContent = 'Listening — speak now...';
        }};

        recognition.onresult = (event) => {{
            let interim = '', final = '';
            for (let i = event.resultIndex; i < event.results.length; i++) {{
                const t = event.results[i][0].transcript;
                if (event.results[i].isFinal) final += t;
                else interim += t;
            }}
            const live = final || interim;
            if (liveEl) liveEl.textContent = live || 'Listening...';

            if (final) {{
                // Push recognised text into Streamlit chat input
                const inputEl = window.parent.document.querySelector('textarea[data-testid="stChatInputTextArea"]');
                if (inputEl) {{
                    const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
                    setter.call(inputEl, final.trim());
                    inputEl.dispatchEvent(new Event('input', {{ bubbles:true }}));
                    inputEl.focus();
                    // Simulate Enter key to submit
                    setTimeout(() => {{
                        inputEl.dispatchEvent(new KeyboardEvent('keydown', {{ key:'Enter', keyCode:13, bubbles:true }}));
                    }}, 300);
                }}
            }}
        }};

        recognition.onerror = (e) => {{
            console.error('STT error:', e.error);
            if (liveEl) liveEl.textContent = '⚠️ Mic error: ' + e.error + ' — try toggling again';
        }};

        recognition.onend = () => {{
            // If mic is still supposed to be on, restart
            if ({mic_active_js}) {{
                try {{ recognition.start(); }} catch(e) {{}}
            }}
        }};

        try {{ recognition.start(); }}
        catch(e) {{ if (liveEl) liveEl.textContent = '⚠️ Could not start mic: ' + e.message; }}
    }})();
    </script>
    """, height=0)

    if not prompt:
        return

    # ── Guard checks ──
    if not api_key:
        st.markdown('<div class="alert-error">⚠️ Cannot process query — Groq API key not set.</div>', unsafe_allow_html=True)
        return
    if st.session_state.get('embeddings') is None:
        st.markdown('<div class="alert-info">ℹ️ Cannot process query — no documents in knowledge base.</div>', unsafe_allow_html=True)
        return
    if model is None:
        st.markdown('<div class="alert-error">❌ Cannot process query — semantic model not loaded.</div>', unsafe_allow_html=True)
        return

    # ── Save & show user message ──
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    st.session_state.messages.append({"role": "user", "content": prompt, "sources": None, "confidence": None, "time": now})
    save_chat_message(pg_url, user['username'], "user", prompt)
    st.markdown(f'<div class="chat-label">YOU</div><div class="chat-user">{prompt}</div><div class="msg-time">{now}</div>', unsafe_allow_html=True)

    # ── Generate answer ──
    with st.spinner("🔍 Searching documents semantically..."):
        t_start = time.time()
        relevant_docs, scores = semantic_search(
            prompt, model,
            st.session_state.embeddings,
            st.session_state.chunks,
            n_results=5
        )
        confidence = compute_confidence(scores)

        if relevant_docs:
            answer, success = generate_answer(prompt, relevant_docs, api_key)
        else:
            answer     = "⚠️ No relevant information found in the uploaded documents. Try rephrasing or ask an admin to upload more documents."
            success    = True
            confidence = 0.0

        response_ms = int((time.time() - t_start) * 1000)

    log_query(pg_url, user['username'], prompt, response_ms, confidence, success)

    sources_json = json.dumps(relevant_docs[:3]) if relevant_docs else None
    save_chat_message(pg_url, user['username'], "assistant", answer, sources_json, confidence)

    now2   = datetime.now().strftime("%Y-%m-%d %H:%M")
    ai_msg = {"role": "assistant", "content": answer, "sources": sources_json, "confidence": confidence, "time": now2}
    st.session_state.messages.append(ai_msg)

    conf_html_str = confidence_html(confidence)
    src_html = ""
    if relevant_docs:
        excerpts = "".join([f'<div class="source-text">"{s[:130]}..."</div>' for s in relevant_docs[:2]])
        src_html = f'<div class="source-chips"><div class="source-label">📎 Source Excerpts ({response_ms}ms)</div>{excerpts}</div>'

    st.markdown(f"""
    <div class="chat-label">AI ASSISTANT</div>
    <div class="chat-assistant">
        {answer}
        {conf_html_str}
        {src_html}
    </div>
    <div class="msg-time">{now2}</div>
    """, unsafe_allow_html=True)

    # ── Share actions for this fresh answer ──
    _render_share_actions(answer, len(st.session_state.messages) - 1, question=prompt)

    st.rerun()


# ─────────────────────────────────────────────
# SHARE ACTIONS — PDF Download + Telegram
# ─────────────────────────────────────────────
def _render_share_actions(answer: str, msg_index: int, question: str = ""):
    """
    Renders two action buttons below an AI answer:
      1. 📄 Download as PDF
      2. ✈️ Share on Telegram (free, no API key needed)

    Telegram share works via https://t.me/share/url — completely free.
    Clicking the button opens Telegram with the answer text pre-filled.
    The user picks a contact or group to send it to.
    """
    col1, col2, col3 = st.columns([2, 2, 6])

    # ── PDF download ──
    with col1:
        pdf_bytes = _build_answer_pdf(question or "College AI Query", answer)
        ext       = _get_pdf_ext()
        mime      = _get_pdf_mime()
        fname     = f"college_ai_answer_{msg_index}.{ext}"
        st.download_button(
            label="📄 Save as PDF",
            data=pdf_bytes,
            file_name=fname,
            mime=mime,
            key=f"dl_pdf_{msg_index}",
            use_container_width=True,
        )

    # ── Telegram share (100% free) ──
    with col2:
        # Build the share text
        tg_text = f"🎓 College AI Assistant\n\nQ: {question}\n\nA: {answer}\n\n— SRM CS Dept AI"
        # Telegram's free share URL — opens app/web with message pre-filled
        tg_url  = f"https://t.me/share/url?url=&text={urllib.parse.quote(tg_text)}"
        st.markdown(
            f'<a href="{tg_url}" target="_blank" '
            f'style="display:inline-flex;align-items:center;gap:6px;padding:10px 14px;'
            f'border-radius:10px;font-size:0.82rem;font-weight:600;text-decoration:none;'
            f'background:rgba(41,182,246,0.15);color:#7dd3fc;'
            f'border:1px solid rgba(41,182,246,0.3);width:100%;justify-content:center;">'
            f'✈️ Telegram</a>',
            unsafe_allow_html=True
        )
