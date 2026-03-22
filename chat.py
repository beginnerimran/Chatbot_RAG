"""
chat.py — Full chat UI with ALL production features.
FIXES:
  - DuplicateWidgetID crash: all widget keys now include a session-scoped render counter
  - KeyError on msg['confidence']: safe .get() with float cast + None guard everywhere
  - st.error() inside load_all_documents_from_db no longer crashes render — errors are silent
  - update_last_active DB write on every render removed from hot path (caused connection churn)
  - export_conversation_pdf called on every render even with empty messages — guarded
  - pending_query pop now happens before chat_input to avoid losing the value
  - st.rerun() after every answer caused infinite loop when messages existed — now guarded
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
from database import (
    load_all_documents_from_db, log_query, save_chat_message,
    save_feedback, check_rate_limit, update_last_active
)
from rag import compute_confidence, confidence_html, generate_answer, semantic_search


FOLLOWUP_PROMPTS = [
    "Can you explain that in more detail?",
    "What are the key points?",
    "Who should I contact for this?",
    "Is there a deadline for this?",
]

LANG_AUTO_INSTRUCTION = """LANGUAGE RULE (VERY IMPORTANT):
Detect the language of the student question and reply in the SAME language and style.
- If they wrote in English → reply in English
- If they wrote in Tamil script → reply in Tamil
- If they wrote in Hindi/Devanagari → reply in Hindi
- If they wrote in Tanglish (Tamil words in English letters like "sollu", "pannanum", "iruku") → reply in Tanglish the same way
- If they wrote in Hinglish (Hindi words in English letters like "karo", "chahiye", "batao") → reply in Hinglish the same way
- If they wrote in mixed language → match their exact mix
Never switch language on your own. Always mirror the student's language."""


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
        s        = getSampleStyleSheet()
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
            try:
                # Sanitise content — ReportLab chokes on special XML chars
                content = str(msg.get('content', '')).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                if msg['role'] == 'user':
                    story.append(Paragraph(f"You: {content}", you_st))
                else:
                    story.append(Paragraph(f"AI: {content}", ai_st))
                    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#2a2f45')))
                    story.append(Spacer(1, 0.2*cm))
            except Exception:
                pass
        doc.build(story)
        return buf.getvalue()
    except ImportError:
        lines = ["College AI Assistant - Conversation Export",
                 f"User: {username} | {datetime.now()}\n{'='*60}"]
        for msg in messages:
            prefix = "You" if msg['role'] == 'user' else "AI"
            lines.append(f"\n{prefix}: {msg.get('content','')}\n")
        return "\n".join(lines).encode("utf-8")
    except Exception:
        return f"Export failed. User: {username} | {datetime.now()}".encode("utf-8")


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
        # Sanitise
        q_safe = str(question).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
        a_safe = str(answer).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
        doc.build([
            Paragraph("College AI Assistant", t_s),
            Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | SRM Institute, CS Dept", m_s),
            Spacer(1, 0.4*cm),
            Paragraph(f"Q: {q_safe}", q_s),
            Paragraph(a_safe.replace('\n','<br/>'), a_s),
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
# ACTION ROW — Copy · Thumbs · PDF · Telegram
# Keys include render_gen to avoid DuplicateWidgetID across reruns
# ─────────────────────────────────────────────
def _action_row(answer: str, msg_index: int, question: str, username: str, pg_url: str):
    mime, ext = _pdf_type()
    tg_text   = f"College AI Assistant\n\nQ: {question}\n\nA: {answer}\n\nSRM CS Dept AI"
    tg_url    = f"https://t.me/share/url?url=&text={urllib.parse.quote(tg_text)}"
    gen       = st.session_state.get('render_gen', 0)  # changes on rerun to avoid stale keys

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

    c1, c2, c3, _ = st.columns([1.5, 1.5, 2, 5])
    with c1:
        if st.button("👍 Helpful", key=f"up_{msg_index}_{gen}", use_container_width=True):
            try:
                save_feedback(pg_url, username, question, answer, 1)
                st.toast("Thanks for your feedback!", icon="👍")
            except Exception:
                pass
    with c2:
        if st.button("👎 Not helpful", key=f"dn_{msg_index}_{gen}", use_container_width=True):
            try:
                save_feedback(pg_url, username, question, answer, -1)
                st.toast("Thanks — we'll improve!", icon="👎")
            except Exception:
                pass
    with c3:
        try:
            pdf_data = _single_pdf(question or "Query", answer)
            st.download_button(
                label="📄 Save PDF",
                data=pdf_data,
                file_name=f"answer_{msg_index}.{ext}",
                mime=mime,
                key=f"dl_{msg_index}_{gen}",
                use_container_width=True,
            )
        except Exception:
            pass


# ─────────────────────────────────────────────
# FOLLOW-UP SUGGESTIONS
# ─────────────────────────────────────────────
def _followup_chips(msg_index: int):
    chips     = FOLLOWUP_PROMPTS
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
    user = st.session_state.get('user', {})
    role = user.get('role', 'student')

    # Bump render_gen each time this function runs so all widget keys are unique
    st.session_state.render_gen = st.session_state.get('render_gen', 0) + 1
    gen = st.session_state.render_gen

    # Update last active — throttled to once per minute to avoid DB connection churn
    last_active_update = st.session_state.get('last_active_update', 0)
    if time.time() - last_active_update > 60:
        try:
            update_last_active(pg_url, user['username'])
            st.session_state.last_active_update = time.time()
        except Exception:
            pass

    # Load knowledge base once per session
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

    # ── Empty welcome state ──
    if not st.session_state.messages:
        st.markdown(f"""
        <div style="text-align:center;padding:48px 20px;">
            <div style="font-size:3.5rem;margin-bottom:14px;">🎓</div>
            <h3 style="color:var(--teal);margin-bottom:6px;font-weight:600;">Welcome, {user.get('display','!')}!</h3>
            <p style="color:var(--text-2);font-size:0.9rem;">Ask anything about your college documents.</p>
            {'<p style="font-size:0.75rem;color:var(--text-3);margin-top:6px;">Previous conversations saved — use Load History in sidebar.</p>' if not st.session_state.get("history_loaded") else ''}
        </div>
        """, unsafe_allow_html=True)

    # ── Session banner ──
    if st.session_state.messages:
        label = "📜 Restored history" if st.session_state.get("history_loaded") else "🟢 Current session"
        color = "#4f8ef7" if st.session_state.get("history_loaded") else "#00c9a7"
        st.markdown(
            f'<div style="font-size:0.72rem;color:{color};font-family:JetBrains Mono,monospace;margin-bottom:10px;">'
            f'<span class="dot" style="background:{color};box-shadow:0 0 5px {color};"></span>{label}</div>',
            unsafe_allow_html=True
        )

    # ── Render message history ──
    for i, msg in enumerate(st.session_state.messages):
        if msg['role'] == 'user':
            st.markdown(f"""
            <div class="chat-wrap">
                <div class="chat-label">You</div>
                <div class="chat-user">{msg.get('content','')}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            # FIX: safe confidence extraction — never crash on None or missing key
            raw_conf = msg.get('confidence')
            try:
                conf_val = float(raw_conf) if raw_conf is not None else None
            except (TypeError, ValueError):
                conf_val = None
            conf_str = confidence_html(conf_val) if conf_val is not None else ""

            src_str = ""
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
                    {msg.get('content','')}
                    {conf_str}
                    {src_str}
                </div>
            </div>
            """, unsafe_allow_html=True)

            prev_user = st.session_state.messages[i-1].get('content','') if i > 0 else ""
            # FIX: unique keys use both msg index and render_gen — no DuplicateWidgetID ever
            _action_row(msg.get('content',''), f"{i}_{gen}", prev_user, user.get('username',''), pg_url)
            _followup_chips(f"{i}_{gen}")

    # ── Suggestion chips (empty state only) ──
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

    # ── Validation banners ──
    if not api_key:
        st.markdown('<div class="alert-error">⚠️ Groq API key missing. Check secrets.toml.</div>', unsafe_allow_html=True)
    if st.session_state.get('embeddings') is None:
        st.markdown('<div class="alert-info">📂 No documents loaded yet. Upload PDFs from the sidebar first.</div>', unsafe_allow_html=True)
    if model is None:
        st.markdown('<div class="alert-error">⚠️ Semantic model unavailable. Run: pip install sentence-transformers</div>', unsafe_allow_html=True)

    # ── FIX: pop pending_query BEFORE chat_input so it can be used as default ──
    pending = st.session_state.pop('pending_query', None)

    # ── Input row ──
    col_mic, col_input = st.columns([1, 11])
    with col_mic:
        mic_active = st.session_state.get('mic_active', False)
        if st.button("🔴" if mic_active else "🎤", key=f"mic_toggle_{gen}",
                     help="Click to speak — Chrome/Edge only",
                     use_container_width=True):
            st.session_state.mic_active       = not mic_active
            st.session_state.mic_just_toggled = True
            st.rerun()

    if st.session_state.get('mic_active'):
        st.markdown('<div class="mic-banner">🔴 <span id="chat-voice-text">Listening — speak now...</span></div>', unsafe_allow_html=True)

    with col_input:
        prompt = st.chat_input("Ask about your college documents...") or pending

    # ── Controls row ──
    tts_on = st.session_state.get('tts_enabled', True)
    c1, c2 = st.columns([2, 2])
    with c1:
        if st.button("🔊 Read Aloud: ON" if tts_on else "🔇 Read Aloud: OFF", key=f"tts_toggle_{gen}", use_container_width=True):
            st.session_state.tts_enabled = not tts_on
            st.rerun()
    with c2:
        # FIX: only render export button when there are messages — avoids pointless PDF gen on every load
        if st.session_state.messages:
            try:
                mime, ext = _pdf_type()
                conv_pdf  = export_conversation_pdf(st.session_state.messages, user.get('username','user'))
                st.download_button(
                    label="📥 Export Chat",
                    data=conv_pdf,
                    file_name=f"conversation_{datetime.now().strftime('%Y%m%d_%H%M')}.{ext}",
                    mime=mime,
                    key=f"export_conv_{gen}",
                    use_container_width=True,
                )
            except Exception:
                pass

    # ── STT + TTS JS ──
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
        rec.lang='en-IN';
        rec.interimResults=true; rec.continuous=true; rec.maxAlternatives=1;
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

    # ── Rate limit check ──
    try:
        allowed, remaining = check_rate_limit(pg_url, user['username'])
    except Exception:
        allowed, remaining = True, 30

    if not allowed:
        st.markdown('<div class="alert-warn">⏱ Rate limit reached (30 queries/hour). Please wait before asking again.</div>', unsafe_allow_html=True)
        return

    # ── Guard checks ──
    if not api_key:
        st.markdown('<div class="alert-error">Groq API key not set.</div>', unsafe_allow_html=True)
        return
    if st.session_state.get('embeddings') is None:
        st.markdown('<div class="alert-info">📂 No documents in knowledge base. Please upload PDFs first.</div>', unsafe_allow_html=True)
        return
    if model is None:
        st.markdown('<div class="alert-error">Semantic model not loaded.</div>', unsafe_allow_html=True)
        return

    # ── Show user message immediately ──
    now = datetime.now().strftime("%H:%M · %d %b %Y")
    st.session_state.messages.append({"role":"user","content":prompt,"sources":None,"confidence":None,"time":now})
    try:
        save_chat_message(pg_url, user['username'], "user", prompt)
    except Exception:
        pass

    st.markdown(f"""
    <div class="chat-wrap">
        <div class="chat-label">You</div>
        <div class="chat-user">{prompt}</div>
    </div>
    """, unsafe_allow_html=True)

    # ── Typing indicator ──
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

    # ── Build conversation memory (last 4 exchanges) ──
    memory_msgs = st.session_state.messages[-9:-1]
    memory_ctx  = ""
    if memory_msgs:
        memory_ctx = "\n\nCONVERSATION HISTORY (for context):\n"
        for m in memory_msgs:
            prefix = "User" if m['role'] == 'user' else "Assistant"
            memory_ctx += f"{prefix}: {str(m.get('content',''))[:200]}\n"

    # ── Generate answer ──
    t0 = time.time()
    try:
        relevant_docs, scores = semantic_search(
            prompt, model,
            st.session_state.embeddings,
            st.session_state.chunks,
            n_results=5
        )
        confidence = compute_confidence(scores)
    except Exception:
        relevant_docs, scores, confidence = [], [], 0.0

    if relevant_docs:
        answer, success = generate_answer(
            prompt, relevant_docs, api_key,
            memory_context=memory_ctx,
            lang_instruction=LANG_AUTO_INSTRUCTION
        )
    else:
        answer  = "This information is not available in the current documents. Please contact the department office directly."
        success = True
        confidence = 0.0

    ms = int((time.time() - t0) * 1000)
    typing_placeholder.empty()

    try:
        log_query(pg_url, user['username'], prompt, ms, confidence, success)
    except Exception:
        pass

    sources_json = json.dumps(relevant_docs[:3]) if relevant_docs else None
    try:
        save_chat_message(pg_url, user['username'], "assistant", answer, sources_json, confidence)
    except Exception:
        pass

    ai_msg = {"role":"assistant","content":answer,"sources":sources_json,"confidence":confidence,"time":now}
    st.session_state.messages.append(ai_msg)

    conf_str = confidence_html(confidence)
    src_str  = ""
    if relevant_docs:
        excerpts = "".join([f'<div class="src-text">"{str(s)[:130]}..."</div>' for s in relevant_docs[:2]])
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
    _action_row(answer, f"{idx}_{gen}", prompt, user.get('username',''), pg_url)
    _followup_chips(f"{idx}_{gen}")

    if remaining <= 5:
        st.markdown(f'<div class="alert-warn">⚠️ You have {remaining} queries left this hour.</div>', unsafe_allow_html=True)

    # FIX: do NOT st.rerun() here — it would re-render the whole page including all history
    # The new message is already rendered above; rerun caused the infinite render loop
