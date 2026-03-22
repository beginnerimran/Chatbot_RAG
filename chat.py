"""
chat.py — Full chat UI.
FIXES v2:
  - Raw HTML leak: components.html Copy button replaced — was rendering raw HTML in page
  - Mic broken: moved JS injection from components.html to st.markdown (sandboxed iframe
    cannot access parent DOM reliably on Chrome/mobile)
  - Read Aloud: live Stop Speaking button appears while AI is talking, disappears when done
  - Docs tab: students blocked at app.py level — no docs tab rendered for student role
  - All widget keys include render_gen to prevent DuplicateWidgetID
"""

import io
import json
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
    tg_url    = f"https://t.me/share/url?url=&text={urllib.parse.quote(tg_text)}"

    st.markdown(f"""
    <div style="margin-top:8px;margin-bottom:4px;">
        <a href="{tg_url}" target="_blank"
           style="display:inline-flex;align-items:center;gap:5px;padding:5px 14px;
                  border-radius:6px;font-size:0.78rem;font-weight:500;
                  border:1px solid var(--border-2);background:var(--bg-3);
                  color:var(--text-2);text-decoration:none;">
            ✈️ Share on Telegram
        </a>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3, _ = st.columns([1.5, 1.8, 2, 4])
    with c1:
        if st.button("👍 Helpful", key=f"up_{msg_key}", use_container_width=True):
            try:
                save_feedback(pg_url, username, question, answer, 1)
                st.toast("Thanks for your feedback!", icon="👍")
            except Exception:
                pass
    with c2:
        if st.button("👎 Not helpful", key=f"dn_{msg_key}", use_container_width=True):
            try:
                save_feedback(pg_url, username, question, answer, -1)
                st.toast("Thanks — we will improve!", icon="👎")
            except Exception:
                pass
    with c3:
        try:
            st.download_button(
                label="📄 Save PDF",
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
# VOICE JS — injected via st.markdown, NOT components.html
# FIX: components.html(height=0) runs in a sandboxed iframe.
# On Chrome and mobile it cannot reliably access window.parent DOM elements
# (textarea, .chat-assistant divs). st.markdown injects directly into the
# main Streamlit document so querySelector works correctly.
# ─────────────────────────────────────────────
def _inject_voice_js(mic_active: bool, tts_on: bool, toggle_id: int):
    tts_js = "true" if tts_on else "false"
    mic_js = "true" if mic_active else "false"
    st.markdown(f"""
<script>
(function() {{
    var uid = 'v{toggle_id}';
    if (window['_vjs_' + uid]) return;
    window['_vjs_' + uid] = true;

    var ttsOn = {tts_js};
    var micOn = {mic_js};
    var synth = window.speechSynthesis;

    // ── TTS ──
    function speakLast() {{
        if (!ttsOn || !synth) return;
        synth.cancel();
        var msgs = document.querySelectorAll('.chat-assistant');
        if (!msgs.length) return;
        var last = msgs[msgs.length - 1];
        if (last.dataset.spoken === 'true') return;
        var clone = last.cloneNode(true);
        clone.querySelectorAll('.conf-wrap,.src-wrap,.followup-wrap').forEach(function(e) {{ e.remove(); }});
        var text = clone.textContent.replace(/\\s+/g, ' ').trim().substring(0, 800);
        var utt  = new SpeechSynthesisUtterance(text);
        utt.lang = 'en-IN'; utt.rate = 0.92; utt.pitch = 1.0;
        var voices = synth.getVoices();
        var voice  = voices.find(function(v) {{ return v.lang === 'en-IN'; }}) ||
                     voices.find(function(v) {{ return v.lang.startsWith('en'); }}) || voices[0];
        if (voice) utt.voice = voice;
        last.dataset.spoken = 'true';
        utt.onstart = function() {{
            var b = document.getElementById('tts-stop-btn');
            if (b) b.style.display = 'flex';
        }};
        utt.onend = utt.onerror = function() {{
            var b = document.getElementById('tts-stop-btn');
            if (b) b.style.display = 'none';
        }};
        synth.speak(utt);
    }}

    // Stop button
    setTimeout(function() {{
        var stopBtn = document.getElementById('tts-stop-btn');
        if (stopBtn) {{
            stopBtn.onclick = function() {{
                if (synth) synth.cancel();
                stopBtn.style.display = 'none';
                var msgs = document.querySelectorAll('.chat-assistant');
                if (msgs.length) msgs[msgs.length - 1].dataset.spoken = 'true';
            }};
        }}
    }}, 500);

    // Watch DOM for new AI messages
    new MutationObserver(function() {{
        var msgs = document.querySelectorAll('.chat-assistant');
        if (!msgs.length) return;
        var last = msgs[msgs.length - 1];
        if (last && last.dataset.spoken !== 'true') speakLast();
    }}).observe(document.body, {{ childList: true, subtree: true }});

    // ── STT ──
    if (!micOn) return;

    // Block mic on mobile over plain HTTP (browser will silently deny anyway)
    var isSecure = location.protocol === 'https:';
    var isLocal  = location.hostname === 'localhost' || location.hostname === '127.0.0.1';
    if (!isSecure && !isLocal) {{
        var el = document.getElementById('chat-voice-text');
        if (el) el.textContent = 'Mic needs HTTPS — works on laptop or after deploying to Streamlit Cloud';
        return;
    }}

    var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) {{
        var el2 = document.getElementById('chat-voice-text');
        if (el2) el2.textContent = 'Speech recognition not supported. Use Chrome or Edge.';
        return;
    }}
    if (window._activeRec) {{ try {{ window._activeRec.stop(); }} catch(e) {{}} }}
    var rec = new SR();
    window._activeRec = rec;
    rec.lang = 'en-IN';
    rec.interimResults  = true;
    rec.continuous      = true;
    rec.maxAlternatives = 1;

    var liveEl = document.getElementById('chat-voice-text');
    rec.onstart  = function() {{ if (liveEl) liveEl.textContent = 'Listening — speak now...'; }};
    rec.onresult = function(e) {{
        var interim = '', final = '';
        for (var i = e.resultIndex; i < e.results.length; i++) {{
            var t = e.results[i][0].transcript;
            if (e.results[i].isFinal) final += t; else interim += t;
        }}
        if (liveEl) liveEl.textContent = final || interim || 'Listening...';
        if (final) {{
            var inp = document.querySelector('textarea[data-testid="stChatInputTextArea"]');
            if (inp) {{
                var setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set;
                setter.call(inp, final.trim());
                inp.dispatchEvent(new Event('input', {{ bubbles: true }}));
                inp.focus();
                setTimeout(function() {{
                    inp.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'Enter', keyCode: 13, bubbles: true }}));
                }}, 350);
            }}
        }}
    }};
    rec.onerror = function(e) {{
        if (liveEl) liveEl.textContent = 'Mic error: ' + e.error + '. Check browser mic permissions.';
    }};
    rec.onend = function() {{ if (micOn) {{ try {{ rec.start(); }} catch(e) {{}} }} }};
    try {{
        rec.start();
    }} catch(e) {{
        if (liveEl) liveEl.textContent = 'Could not start mic: ' + e.message;
    }}
}})();
</script>
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
            <div style="font-size:3.5rem;margin-bottom:14px;">🎓</div>
            <h3 style="color:var(--teal);margin-bottom:6px;font-weight:600;">Welcome, {user.get('display','!')}!</h3>
            <p style="color:var(--text-2);font-size:0.9rem;">Ask anything about your college documents.</p>
            {'<p style="font-size:0.75rem;color:var(--text-3);margin-top:6px;">Previous conversations saved — use Load History in sidebar.</p>' if not st.session_state.get("history_loaded") else ''}
        </div>
        """, unsafe_allow_html=True)

    if st.session_state.messages:
        label = "📜 Restored history" if st.session_state.get("history_loaded") else "🟢 Current session"
        color = "#4f8ef7" if st.session_state.get("history_loaded") else "#00c9a7"
        st.markdown(
            f'<div style="font-size:0.72rem;color:{color};font-family:JetBrains Mono,monospace;margin-bottom:10px;">'
            f'<span class="dot" style="background:{color};box-shadow:0 0 5px {color};"></span>{label}</div>',
            unsafe_allow_html=True
        )

    for i, msg in enumerate(st.session_state.messages):
        if msg['role'] == 'user':
            st.markdown(f"""
            <div class="chat-wrap">
                <div class="chat-label">You</div>
                <div class="chat-user">{msg.get('content','')}</div>
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
                    {msg.get('content','')}
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
    if model is None:
        st.markdown('<div class="alert-error">Semantic model unavailable.</div>', unsafe_allow_html=True)

    pending = st.session_state.pop('pending_query', None)

    col_mic, col_input = st.columns([1, 11])
    with col_mic:
        mic_active = st.session_state.get('mic_active', False)
        if st.button("🔴" if mic_active else "🎤", key=f"mic_toggle_{gen}",
                     help="Mic needs Chrome/Edge. On mobile it only works on HTTPS.",
                     use_container_width=True):
            st.session_state.mic_active       = not mic_active
            st.session_state.mic_toggle_count = st.session_state.get('mic_toggle_count', 0) + 1
            st.rerun()

    if st.session_state.get('mic_active'):
        st.markdown("""
        <div class="mic-banner">🔴 <span id="chat-voice-text">Initialising mic...</span></div>
        <div id="mic-https-warn" style="display:none;background:rgba(240,165,0,0.1);
             border:1px solid rgba(240,165,0,0.3);border-radius:6px;padding:8px 12px;
             font-size:0.78rem;color:#f0a500;margin-top:4px;">
            Mobile mic needs HTTPS. Works on laptop browser or after deploying to Streamlit Cloud.
        </div>
        <script>
        (function() {
            var host     = window.location.hostname;
            var isSecure = window.location.protocol === 'https:';
            var isLocal  = host === 'localhost' || host === '127.0.0.1';
            var isMobile = /Android|iPhone|iPad/i.test(navigator.userAgent);
            if (isMobile && !isSecure && !isLocal) {
                var w = document.getElementById('mic-https-warn');
                if (w) w.style.display = 'block';
                var t = document.getElementById('chat-voice-text');
                if (t) t.textContent = 'Mic blocked — needs HTTPS on mobile';
            }
        })();
        </script>
        """, unsafe_allow_html=True)

    with col_input:
        prompt = st.chat_input("Ask about your college documents...") or pending

    tts_on = st.session_state.get('tts_enabled', True)
    c1, c2, c3 = st.columns([2, 2, 2])
    with c1:
        if st.button("🔊 Read Aloud: ON" if tts_on else "🔇 Read Aloud: OFF",
                     key=f"tts_toggle_{gen}", use_container_width=True):
            st.session_state.tts_enabled = not tts_on
            st.rerun()
    with c2:
        # Stop Speaking button — hidden by default, shown by JS when TTS is active
        st.markdown("""
        <button id="tts-stop-btn"
            style="display:none;width:100%;align-items:center;justify-content:center;
                   gap:6px;padding:10px 0;border-radius:8px;font-size:0.85rem;font-weight:600;
                   cursor:pointer;border:none;min-height:44px;
                   background:linear-gradient(135deg,#f05252,#c0392b);color:#fff;
                   font-family:Inter,sans-serif;">
            ⏹ Stop Speaking
        </button>
        """, unsafe_allow_html=True)
    with c3:
        if st.session_state.messages:
            try:
                mime, ext = _pdf_type()
                st.download_button(
                    label="📥 Export Chat",
                    data=export_conversation_pdf(st.session_state.messages, user.get('username','user')),
                    file_name=f"conversation_{datetime.now().strftime('%Y%m%d_%H%M')}.{ext}",
                    mime=mime,
                    key=f"export_conv_{gen}",
                    use_container_width=True,
                )
            except Exception:
                pass

    _inject_voice_js(
        mic_active=st.session_state.get('mic_active', False),
        tts_on=tts_on,
        toggle_id=st.session_state.get('mic_toggle_count', 0)
    )

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
    if model is None:
        st.markdown('<div class="alert-error">Semantic model not loaded.</div>', unsafe_allow_html=True)
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
        <div class="chat-user">{prompt}</div>
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
        relevant_docs, scores = semantic_search(prompt, model, st.session_state.embeddings, st.session_state.chunks, n_results=5)
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
            {answer}
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
