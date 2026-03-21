"""
chat.py — Full chat UI with ALL production features:
  - Typing indicator animation
  - Copy button on every answer
  - Thumbs up / Thumbs down feedback
  - Follow-up question suggestions
  - Conversation memory (last 5 turns sent to LLM)
  - Multi-language support (EN, Tamil, Hindi)
  - Export full conversation as PDF
  - Telegram share
  - Rate limiting guard
  - Fixed mic STT + TTS read-aloud
"""

import io
import json
import time
import urllib.parse
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components

from auth import check_permission
from config import SUGGESTIONS, LANGUAGES
from database import (
    load_all_documents_from_db, log_query, save_chat_message,
    save_feedback, check_rate_limit, update_last_active
)
from rag import compute_confidence, confidence_html, generate_answer, semantic_search


FOLLOWUP_PROMPTS = {
    "en": [
        "Can you explain that in more detail?",
        "What are the key points?",
        "Who should I contact for this?",
        "Is there a deadline for this?",
    ],
    "ta": [
        "இதை விவரமாக சொல்லுங்கள்",
        "முக்கிய புள்ளிகள் என்ன?",
        "யாரை தொடர்பு கொள்வது?",
    ],
    "hi": [
        "इसे विस्तार से बताएं",
        "मुख्य बिंदु क्या हैं?",
        "इसके लिए किससे संपर्क करें?",
    ],
}

LANG_PROMPTS = {
    "en": "Answer in English.",
    "ta": "Answer in Tamil (தமிழில் பதில் சொல்லவும்).",
    "hi": "Answer in Hindi (हिंदी में जवाब दीजिए).",
}


# ─────────────────────────────────────────────
# EXPORT CONVERSATION AS PDF
# ─────────────────────────────────────────────
def export_conversation_pdf(messages: list, username: str) -> bytes:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
        from reportlab.lib.units import cm
        from reportlab.lib import colors

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4,
                                leftMargin=2*cm, rightMargin=2*cm,
                                topMargin=2*cm, bottomMargin=2*cm)
        s   = getSampleStyleSheet()
        title_st = ParagraphStyle('T', parent=s['Heading1'], textColor=colors.HexColor('#00c9a7'), fontSize=18, spaceAfter=4)
        meta_st  = ParagraphStyle('M', parent=s['Normal'],   textColor=colors.grey, fontSize=9, spaceAfter=16)
        you_st   = ParagraphStyle('Y', parent=s['Normal'],   textColor=colors.HexColor('#4f8ef7'), fontSize=11, fontName='Helvetica-Bold', spaceAfter=4)
        ai_st    = ParagraphStyle('A', parent=s['Normal'],   fontSize=11, leading=16, spaceAfter=12)

        story = [
            Paragraph("College AI Assistant — Conversation Export", title_st),
            Paragraph(f"User: {username}  |  Exported: {datetime.now().strftime('%Y-%m-%d %H:%M')}  |  SRM Institute, CS Dept", meta_st),
            HRFlowable(width="100%", thickness=1, color=colors.HexColor('#2a2f45')),
            Spacer(1, 0.3*cm),
        ]
        for msg in messages:
            if msg['role'] == 'user':
                story.append(Paragraph(f"You: {msg['content']}", you_st))
            else:
                story.append(Paragraph(f"AI: {msg['content']}", ai_st))
                story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#2a2f45')))
                story.append(Spacer(1, 0.2*cm))
        doc.build(story)
        return buf.getvalue()
    except ImportError:
        lines = [f"College AI Assistant - Conversation Export",
                 f"User: {username} | {datetime.now()}\n{'='*60}"]
        for msg in messages:
            prefix = "You" if msg['role'] == 'user' else "AI"
            lines.append(f"\n{prefix}: {msg['content']}\n")
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
        t_s = ParagraphStyle('T', parent=s['Heading1'], textColor=colors.HexColor('#00c9a7'), fontSize=16)
        q_s = ParagraphStyle('Q', parent=s['Normal'],   textColor=colors.HexColor('#4f8ef7'), fontSize=11, spaceAfter=10, fontName='Helvetica-Bold')
        a_s = ParagraphStyle('A', parent=s['Normal'],   fontSize=11, leading=16)
        m_s = ParagraphStyle('M', parent=s['Normal'],   textColor=colors.grey, fontSize=9)
        doc.build([
            Paragraph("College AI Assistant", t_s),
            Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | SRM Institute, CS Dept", m_s),
            Spacer(1, 0.4*cm),
            Paragraph(f"Q: {question}", q_s),
            Paragraph(answer.replace('\n','<br/>'), a_s),
        ])
        return buf.getvalue()
    except ImportError:
        return f"Q: {question}\n\nA: {answer}\n\nGenerated: {datetime.now()}".encode("utf-8")


def _pdf_type():
    try:
        from reportlab.lib.pagesizes import A4
        return "application/pdf", "pdf"
    except ImportError:
        return "text/plain", "txt"


# ─────────────────────────────────────────────
# ACTION ROW — Copy · Thumbs · PDF · Telegram
# ─────────────────────────────────────────────
def _action_row(answer: str, msg_index: int, question: str, username: str, pg_url: str):
    mime, ext = _pdf_type()
    tg_text   = f"College AI Assistant\n\nQ: {question}\n\nA: {answer}\n\nSRM CS Dept AI"
    tg_url    = f"https://t.me/share/url?url=&text={urllib.parse.quote(tg_text)}"

    # JS copy to clipboard
    components.html(f"""
    <div style="display:flex;gap:6px;margin-top:8px;flex-wrap:wrap;">
        <button onclick="navigator.clipboard.writeText({json.dumps(answer)}).then(()=>{{this.textContent='✅ Copied!';setTimeout(()=>this.textContent='📋 Copy',1500)}})"
            style="display:inline-flex;align-items:center;gap:4px;padding:5px 12px;border-radius:6px;
                   font-size:0.75rem;font-weight:500;cursor:pointer;border:1px solid #2a2f45;
                   background:#1a1d27;color:#8b92a9;transition:all 0.15s;font-family:Inter,sans-serif;">
            📋 Copy
        </button>
        <a href="{tg_url}" target="_blank"
            style="display:inline-flex;align-items:center;gap:4px;padding:5px 12px;border-radius:6px;
                   font-size:0.75rem;font-weight:500;cursor:pointer;border:1px solid #2a2f45;
                   background:#1a1d27;color:#8b92a9;transition:all 0.15s;font-family:Inter,sans-serif;text-decoration:none;">
            ✈️ Telegram
        </a>
    </div>
    """, height=50)

    # Feedback + PDF in Streamlit columns
    c1, c2, c3, _ = st.columns([1.5, 1.5, 2, 5])
    with c1:
        if st.button("👍 Helpful", key=f"up_{msg_index}", use_container_width=True):
            save_feedback(pg_url, username, question, answer, 1)
            st.toast("Thanks for your feedback!", icon="👍")
    with c2:
        if st.button("👎 Not helpful", key=f"dn_{msg_index}", use_container_width=True):
            save_feedback(pg_url, username, question, answer, -1)
            st.toast("Thanks — we'll improve!", icon="👎")
    with c3:
        st.download_button(
            label="📄 Save PDF",
            data=_single_pdf(question or "Query", answer),
            file_name=f"answer_{msg_index}.{ext}",
            mime=mime,
            key=f"dl_{msg_index}",
            use_container_width=True,
        )


# ─────────────────────────────────────────────
# FOLLOW-UP SUGGESTIONS
# ─────────────────────────────────────────────
def _followup_chips(msg_index: int, lang: str = "en"):
    chips = FOLLOWUP_PROMPTS.get(lang, FOLLOWUP_PROMPTS["en"])
    chip_html = "".join([
        f'<span class="followup-chip" onclick="setQuery(\'{c.replace(chr(39), chr(34))}\')">{c}</span>'
        for c in chips
    ])
    st.markdown(f"""
    <div class="followup-wrap">
        <div class="followup-label">Follow-up suggestions</div>
        {chip_html}
    </div>
    <script>
    function setQuery(text) {{
        const inp = window.parent.document.querySelector('textarea[data-testid="stChatInputTextArea"]');
        if (inp) {{
            const set = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype,'value').set;
            set.call(inp, text);
            inp.dispatchEvent(new Event('input',{{bubbles:true}}));
            inp.focus();
        }}
    }}
    </script>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# MAIN CHAT
# ─────────────────────────────────────────────
def render_chat(pg_url: str, api_key: str, model):
    user = st.session_state.user
    role = user['role']
    lang = st.session_state.get('language', user.get('language', 'en'))

    # Update last active (session timeout tracking)
    update_last_active(pg_url, user['username'])

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

    # Empty welcome state
    if not st.session_state.messages:
        st.markdown(f"""
        <div style="text-align:center;padding:48px 20px;">
            <div style="font-size:3.5rem;margin-bottom:14px;">🎓</div>
            <h3 style="color:var(--text);margin-bottom:6px;font-weight:600;">Welcome, {user['display']}!</h3>
            <p style="color:var(--text-2);font-size:0.9rem;">Ask anything about your college documents.</p>
            {'<p style="font-size:0.75rem;color:var(--text-3);margin-top:6px;">Previous conversations saved — use Load History in sidebar.</p>' if not st.session_state.get("history_loaded") else ''}
        </div>
        """, unsafe_allow_html=True)

    # Session banner
    if st.session_state.messages:
        label = "📜 Restored history" if st.session_state.get("history_loaded") else "🟢 Current session"
        color = "#4f8ef7" if st.session_state.get("history_loaded") else "#00c9a7"
        st.markdown(f'<div style="font-size:0.72rem;color:{color};font-family:JetBrains Mono,monospace;margin-bottom:10px;"><span class="dot" style="background:{color};box-shadow:0 0 5px {color};"></span>{label}</div>', unsafe_allow_html=True)

    # Render messages
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

            # Action row + follow-ups for each AI message
            prev_user = st.session_state.messages[i-1]['content'] if i > 0 else ""
            _action_row(msg['content'], i, prev_user, user['username'], pg_url)
            _followup_chips(i, lang)

    # Suggestion chips (empty state)
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
        st.markdown('<div class="alert-error">Groq API key missing.</div>', unsafe_allow_html=True)
    if st.session_state.get('embeddings') is None:
        st.markdown('<div class="alert-info">No documents loaded yet. Admin or Staff must upload PDFs first.</div>', unsafe_allow_html=True)
    if model is None:
        st.markdown('<div class="alert-error">Semantic model unavailable — install sentence-transformers.</div>', unsafe_allow_html=True)

    pending = st.session_state.pop('pending_query', None)

    # Input row
    col_mic, col_input = st.columns([1, 11])
    with col_mic:
        mic_active = st.session_state.get('mic_active', False)
        if st.button("🔴" if mic_active else "🎤", key="mic_toggle",
                     help="Click to speak — Chrome/Edge only",
                     use_container_width=True):
            st.session_state.mic_active       = not mic_active
            st.session_state.mic_just_toggled = True
            st.rerun()

    if st.session_state.get('mic_active'):
        st.markdown('<div class="mic-banner">🔴 <span id="chat-voice-text">Listening — speak now...</span></div>', unsafe_allow_html=True)

    with col_input:
        prompt = st.chat_input("Ask about your college documents...") or pending

    # Controls row
    tts_on = st.session_state.get('tts_enabled', True)
    c1, c2, c3 = st.columns([2, 2, 2])
    with c1:
        if st.button("🔊 Read Aloud: ON" if tts_on else "🔇 Read Aloud: OFF", key="tts_toggle", use_container_width=True):
            st.session_state.tts_enabled = not tts_on
            st.rerun()
    with c2:
        # Export full conversation
        if st.session_state.messages:
            mime, ext = _pdf_type()
            conv_pdf  = export_conversation_pdf(st.session_state.messages, user['username'])
            st.download_button(
                label="📥 Export Chat",
                data=conv_pdf,
                file_name=f"conversation_{datetime.now().strftime('%Y%m%d_%H%M')}.{ext}",
                mime=mime,
                key="export_conv",
                use_container_width=True,
            )
    with c3:
        # Language selector
        lang_options = list(LANGUAGES.keys())
        lang_labels  = list(LANGUAGES.values())
        cur_idx      = lang_options.index(lang) if lang in lang_options else 0
        selected     = st.selectbox("🌐 Language", lang_labels, index=cur_idx, key="lang_select", label_visibility="collapsed")
        new_lang     = lang_options[lang_labels.index(selected)]
        if new_lang != lang:
            st.session_state.language = new_lang
            st.rerun()

    # STT + TTS JS
    mic_toggle_id = st.session_state.get('mic_toggle_count', 0)
    if st.session_state.pop('mic_just_toggled', False):
        mic_toggle_id += 1
        st.session_state.mic_toggle_count = mic_toggle_id

    tts_js = "true" if tts_on else "false"
    mic_js = "true" if st.session_state.get('mic_active') else "false"

    components.html(f"""
    <script>
    (function() {{
        const _id   = {mic_toggle_id};
        const ttsOn = {tts_js};
        const micOn = {mic_js};
        const synth = window.parent.speechSynthesis;

        function speakLast() {{
            if (!ttsOn || !synth) return;
            synth.cancel();
            const msgs = window.parent.document.querySelectorAll('.chat-assistant');
            if (!msgs.length) return;
            const last = msgs[msgs.length-1];
            if (last.dataset.spoken==='true') return;
            const clone = last.cloneNode(true);
            clone.querySelectorAll('.conf-wrap,.src-wrap,.action-row,.followup-wrap').forEach(e=>e.remove());
            let text = clone.textContent.replace(/[ \\t\\n\\r]+/g,' ').trim();
            if (text.length>800) text=text.substring(0,800)+'...';
            const utt = new SpeechSynthesisUtterance(text);
            utt.lang='en-IN'; utt.rate=0.92; utt.pitch=1.0;
            const vs=synth.getVoices();
            const v=vs.find(v=>v.lang==='en-IN')||vs.find(v=>v.lang.startsWith('en-'))||vs[0];
            if(v) utt.voice=v;
            last.dataset.spoken='true';
            synth.speak(utt);
        }}
        new MutationObserver(()=>{{
            const msgs=window.parent.document.querySelectorAll('.chat-assistant');
            if(!msgs.length) return;
            const last=msgs[msgs.length-1];
            if(last&&last.dataset.spoken!=='true') speakLast();
        }}).observe(window.parent.document.body,{{childList:true,subtree:true}});

        if(!micOn) return;
        const SR=window.parent.SpeechRecognition||window.parent.webkitSpeechRecognition;
        if(!SR) {{
            const el=window.parent.document.getElementById('chat-voice-text');
            if(el) el.textContent='SpeechRecognition not supported — use Chrome or Edge';
            return;
        }}
        if(window._rec) {{ try{{window._rec.stop();}}catch(e){{}} }}
        const rec=new SR();
        window._rec=rec;
        rec.lang='en-IN'; rec.interimResults=true; rec.continuous=true; rec.maxAlternatives=1;
        const liveEl=window.parent.document.getElementById('chat-voice-text');
        rec.onstart=()=>{{if(liveEl) liveEl.textContent='Listening — speak now...';}};
        rec.onresult=(e)=>{{
            let interim='',final='';
            for(let i=e.resultIndex;i<e.results.length;i++){{
                const t=e.results[i][0].transcript;
                if(e.results[i].isFinal) final+=t; else interim+=t;
            }}
            if(liveEl) liveEl.textContent=final||interim||'Listening...';
            if(final){{
                const inp=window.parent.document.querySelector('textarea[data-testid="stChatInputTextArea"]');
                if(inp){{
                    const set=Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype,'value').set;
                    set.call(inp,final.trim());
                    inp.dispatchEvent(new Event('input',{{bubbles:true}}));
                    inp.focus();
                    setTimeout(()=>inp.dispatchEvent(new KeyboardEvent('keydown',{{key:'Enter',keyCode:13,bubbles:true}})),300);
                }}
            }}
        }};
        rec.onerror=(e)=>{{if(liveEl) liveEl.textContent='Mic error: '+e.error+' — try again';}};
        rec.onend=()=>{{if({mic_js}){{try{{rec.start();}}catch(e){{}}}}}};
        try{{rec.start();}}catch(e){{if(liveEl) liveEl.textContent='Could not start mic: '+e.message;}}
    }})();
    </script>
    """, height=0)

    if not prompt:
        return

    # Rate limit check
    allowed, remaining = check_rate_limit(pg_url, user['username'])
    if not allowed:
        st.markdown('<div class="alert-warn">⏱ Rate limit reached (30 queries/hour). Please wait before asking again.</div>', unsafe_allow_html=True)
        return

    # Guard checks
    if not api_key:
        st.markdown('<div class="alert-error">Groq API key not set.</div>', unsafe_allow_html=True); return
    if st.session_state.get('embeddings') is None:
        st.markdown('<div class="alert-info">No documents in knowledge base.</div>', unsafe_allow_html=True); return
    if model is None:
        st.markdown('<div class="alert-error">Semantic model not loaded.</div>', unsafe_allow_html=True); return

    # Show user message immediately
    now = datetime.now().strftime("%H:%M · %d %b %Y")
    st.session_state.messages.append({"role":"user","content":prompt,"sources":None,"confidence":None,"time":now})
    save_chat_message(pg_url, user['username'], "user", prompt, language=lang)
    st.markdown(f"""
    <div class="chat-wrap">
        <div class="chat-label">You</div>
        <div class="chat-user">{prompt}</div>
    </div>
    """, unsafe_allow_html=True)

    # Typing indicator
    typing_placeholder = st.empty()
    typing_placeholder.markdown("""
    <div class="chat-wrap">
        <div class="chat-label">AI Assistant</div>
        <div class="chat-assistant" style="padding:14px 20px;">
            <span class="typing-dot"></span>
            <span class="typing-dot"></span>
            <span class="typing-dot"></span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Build conversation memory (last 4 exchanges = 8 messages)
    memory_msgs = st.session_state.messages[-9:-1]  # exclude current user msg
    memory_ctx  = ""
    if memory_msgs:
        memory_ctx = "\n\nCONVERSATION HISTORY (for context):\n"
        for m in memory_msgs:
            prefix = "User" if m['role'] == 'user' else "Assistant"
            memory_ctx += f"{prefix}: {m['content'][:200]}\n"

    # Generate answer
    t0 = time.time()
    relevant_docs, scores = semantic_search(prompt, model, st.session_state.embeddings, st.session_state.chunks, n_results=5)
    confidence = compute_confidence(scores)

    if relevant_docs:
        answer, success = generate_answer(
            prompt, relevant_docs, api_key,
            memory_context=memory_ctx,
            lang_instruction=LANG_PROMPTS.get(lang, "")
        )
    else:
        answer  = "No relevant information found in the uploaded documents. Please ask an admin to upload more documents."
        success = True
        confidence = 0.0

    ms = int((time.time() - t0) * 1000)

    # Remove typing indicator
    typing_placeholder.empty()

    log_query(pg_url, user['username'], prompt, ms, confidence, success, lang)
    sources_json = json.dumps(relevant_docs[:3]) if relevant_docs else None
    save_chat_message(pg_url, user['username'], "assistant", answer, sources_json, confidence, lang)

    ai_msg = {"role":"assistant","content":answer,"sources":sources_json,"confidence":confidence,"time":now}
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

    idx = len(st.session_state.messages) - 1
    _action_row(answer, idx, prompt, user['username'], pg_url)
    _followup_chips(idx, lang)

    if remaining <= 5:
        st.markdown(f'<div class="alert-warn">⚠️ You have {remaining} queries left this hour.</div>', unsafe_allow_html=True)

    st.rerun()