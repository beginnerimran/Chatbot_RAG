"""
chat.py — Full chat UI.
FIXES v3:
  - Mic fixed: use st.components.v1.html for JS so scripts actually execute
    (st.markdown strips <script> tags; components.v1.html runs in an iframe that
    CAN reach parent DOM via window.parent on same-origin Streamlit pages)
  - Read Aloud: live Stop Speaking button appears while AI is talking
  - Docs tab: students blocked at app.py level
  - All widget keys include render_gen to prevent DuplicateWidgetID
  - Emojis removed throughout
"""

import html as _html
import io
import json
import re
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


def _transcribe_groq(audio_bytes: bytes, api_key: str) -> str:
    """Send recorded audio to Groq Whisper for speech-to-text."""
    import requests as _req
    try:
        resp = _req.post(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {api_key}"},
            files={"file": ("audio.wav", audio_bytes, "audio/wav")},
            data={"model": "whisper-large-v3"},
            timeout=30,
        )
        if resp.status_code == 200:
            return resp.json().get("text", "").strip()
    except Exception:
        pass
    return ""


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
# VOICE JS
# FIX: st.markdown strips <script> tags (innerHTML doesn't execute them).
# components.v1.html runs in a same-origin iframe; we use window.parent to
# reach the Streamlit textarea and .chat-assistant bubbles in the parent frame.
# ─────────────────────────────────────────────
def _inject_voice_js(mic_active: bool, tts_on: bool, toggle_id: int):
    tts_js = "true" if tts_on else "false"
    mic_js = "true" if mic_active else "false"
    # language=html
    html_code = f"""
<!DOCTYPE html>
<html><body style="margin:0;padding:0;">
<script>
(function() {{
    var uid = 'v{toggle_id}';
    // Guard: only run once per toggle state
    if (window.top['_vjs_' + uid]) return;
    window.top['_vjs_' + uid] = true;

    var ttsOn = {tts_js};
    var micOn = {mic_js};
    var doc   = window.parent.document;
    var synth = window.parent.speechSynthesis;

    // ── TTS ──
    function speakLast() {{
        if (!ttsOn || !synth) return;
        synth.cancel();
        var msgs = doc.querySelectorAll('.chat-assistant');
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
            var b = doc.getElementById('tts-stop-btn');
            if (b) b.style.display = 'flex';
        }};
        utt.onend = utt.onerror = function() {{
            var b = doc.getElementById('tts-stop-btn');
            if (b) b.style.display = 'none';
        }};
        synth.speak(utt);
    }}

    // Stop button wiring (parent document)
    setTimeout(function() {{
        var stopBtn = doc.getElementById('tts-stop-btn');
        if (stopBtn) {{
            stopBtn.onclick = function() {{
                if (synth) synth.cancel();
                stopBtn.style.display = 'none';
                var msgs = doc.querySelectorAll('.chat-assistant');
                if (msgs.length) msgs[msgs.length - 1].dataset.spoken = 'true';
            }};
        }}
    }}, 600);

    // Watch parent DOM for new AI messages
    new MutationObserver(function() {{
        var msgs = doc.querySelectorAll('.chat-assistant');
        if (!msgs.length) return;
        var last = msgs[msgs.length - 1];
        if (last && last.dataset.spoken !== 'true') speakLast();
    }}).observe(doc.body, {{ childList: true, subtree: true }});

    // ── STT ──
    if (!micOn) return;

    // Check security context in the PARENT window (the real app)
    var pLoc     = window.parent.location;
    var isSecure = pLoc.protocol === 'https:';
    var isLocal  = pLoc.hostname === 'localhost' || pLoc.hostname === '127.0.0.1';

    var liveEl = doc.getElementById('chat-voice-text');

    if (!isSecure && !isLocal) {{
        if (liveEl) liveEl.textContent = 'Mic requires HTTPS — works on Streamlit Cloud or localhost.';
        return;
    }}

    // Use parent window SpeechRecognition (same origin)
    var SR = window.parent.SpeechRecognition || window.parent.webkitSpeechRecognition;
    if (!SR) {{
        if (liveEl) liveEl.textContent = 'Speech recognition not supported in this browser. Please use Chrome or Edge.';
        return;
    }}

    // Stop any existing recognition session
    if (window.top['_activeRec']) {{
        try {{ window.top['_activeRec'].stop(); }} catch(e) {{}}
    }}

    var rec = new SR();
    window.top['_activeRec'] = rec;
    rec.lang            = 'en-IN';
    rec.interimResults  = true;
    rec.continuous      = false;  // single utterance; we restart on end for reliability
    rec.maxAlternatives = 1;

    rec.onstart = function() {{
        if (liveEl) liveEl.textContent = 'Listening — speak now ...';
    }};

    rec.onresult = function(e) {{
        var interim = '', final_text = '';
        for (var i = e.resultIndex; i < e.results.length; i++) {{
            var t = e.results[i][0].transcript;
            if (e.results[i].isFinal) final_text += t;
            else interim += t;
        }}
        if (liveEl) liveEl.textContent = final_text || interim || 'Listening ...';

        if (final_text.trim()) {{
            // Insert transcribed text into Streamlit chat input in the parent doc
            var inp = doc.querySelector('textarea[data-testid="stChatInputTextArea"]');
            if (inp) {{
                var setter = Object.getOwnPropertyDescriptor(
                    window.parent.HTMLTextAreaElement.prototype, 'value'
                ).set;
                setter.call(inp, final_text.trim());
                inp.dispatchEvent(new window.parent.Event('input', {{ bubbles: true }}));
                inp.focus();
                // Trigger send after brief delay
                setTimeout(function() {{
                    inp.dispatchEvent(new window.parent.KeyboardEvent('keydown', {{
                        key: 'Enter', keyCode: 13, bubbles: true
                    }}));
                }}, 400);
            }} else {{
                if (liveEl) liveEl.textContent = 'Transcribed: ' + final_text.trim() + ' (could not auto-submit — click the chat input and press Enter)';
            }}
        }}
    }};

    rec.onerror = function(e) {{
        var msg = e.error;
        if (msg === 'not-allowed') msg = 'Microphone access denied — please allow mic in browser settings.';
        if (msg === 'no-speech')   msg = 'No speech detected. Please try again.';
        if (liveEl) liveEl.textContent = 'Mic error: ' + msg;
        // Restart on recoverable errors
        if (e.error !== 'not-allowed' && e.error !== 'service-not-allowed') {{
            setTimeout(function() {{ try {{ rec.start(); }} catch(ex) {{}} }}, 1000);
        }}
    }};

    rec.onend = function() {{
        // Keep listening as long as mic is toggled on
        if (micOn) {{
            setTimeout(function() {{ try {{ rec.start(); }} catch(e) {{}} }}, 300);
        }}
    }};

    try {{
        rec.start();
    }} catch(e) {{
        if (liveEl) liveEl.textContent = 'Could not start microphone: ' + e.message;
    }}
}})();
</script>
</body></html>
"""
    components.html(html_code, height=0, scrolling=False)


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
    if model is None:
        st.markdown('<div class="alert-error">Semantic model unavailable.</div>', unsafe_allow_html=True)

    pending = st.session_state.pop('pending_query', None)

    # ── MIC: st.audio_input (Streamlit 1.33+) + Groq Whisper ────────────────
    # This replaces Web Speech API which was blocked by browsers inside iframes.
    # st.audio_input works on ALL browsers and ALL platforms (HTTP + HTTPS).
        # --- Voice input via Groq Whisper (multi‑language) ---
    colmic, colinput = st.columns([1, 11])

    with colmic:
        audioval = st.audio_input(
            "Record",
            key=f"mic_audio_{gen}",
            label_visibility="collapsed",
            help=(
                "Click to record your question – works with English, Tamil, Hindi, "
                "Tanglish, Hinglish etc. (Groq Whisper)."
            ),
        )

        if audioval is not None:
            if apikey:
                with st.spinner("Transcribing..."):
                    transcript = transcribe_groq_audio_bytes(audioval.read(), apikey)
                if transcript:
                    # feed transcribed text into the normal chat flow
                    st.session_state["pendingquery"] = transcript
                    st.rerun()
                else:
                    st.toast(
                        "Could not transcribe audio. Please type your question.",
                        icon="⚠️",
                    )
            else:
                st.toast(
                    "Groq API key missing – cannot transcribe.",
                    icon="⚠️",
                )

    # --- Chat input (text box) ---
    pending = st.session_state.pop("pendingquery", None)

    with colinput:
        prompt = st.chat_input(
            "Ask about your college documents..." if not pending else None
        )
        # if we have a pending transcript and user has not typed anything,
        # use the transcript as the prompt
        if pending and not prompt:
            prompt = pending

    # --- Read Aloud controls + Export Chat ---
    ttson = st.session_state.get("ttsenabled", True)
    c1, c2, c3 = st.columns([2, 2, 2])

    # Read‑aloud toggle
    with c1:
        tts_label = "Read Aloud ON" if ttson else "Read Aloud OFF"
        if st.button(
            tts_label,
            key=f"tts_toggle_{gen}",
            use_container_width=True,
        ):
            st.session_state["ttsenabled"] = not ttson
            st.rerun()

    # Stop‑speaking button (shown/hidden by JS)
    with c2:
        st.markdown(
            """
            <button id="tts-stop-btn"
                    style="
                        display:none;
                        width:100%;
                        align-items:center;
                        justify-content:center;
                        gap:6px;
                        padding:10px 0;
                        border-radius:8px;
                        font-size:0.85rem;
                        font-weight:600;
                        cursor:pointer;
                        border:none;
                        min-height:44px;
                        background:linear-gradient(135deg,#c0392b,#a93226);
                        color:#fff;
                        font-family:Inter,sans-serif;
                    ">
                Stop Speaking
            </button>
            """,
            unsafe_allow_html=True,
        )

    # Export whole conversation as PDF
    with c3:
        if st.session_state.get("messages"):
            try:
                mime, ext = pdftype()
                st.download_button(
                    label="Export Chat",
                    data=exportconversationpdf(
                        st.session_state["messages"],
                        user.getusername(),  # keep same user method you already use
                    ),
                    file_name=f"conversation_{datetime.now().strftime('%Y%m%d_%H%M')}.{ext}",
                    mime=mime,
                    key=f"export_conv_{gen}",
                    use_container_width=True,
                )
            except Exception:
                # export is optional; ignore failures
                pass

    # Inject JS for Read‑Aloud only (mic handled by st.audio_input + Groq Whisper)
    injectvoicejs(
        micactive=False,  # disable old Web Speech API mic path
        ttson=ttson,
        toggleid=st.session_state.get("mictogglecount", 0),
    )

    # If there is still no prompt (nothing typed and no transcript), do nothing
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