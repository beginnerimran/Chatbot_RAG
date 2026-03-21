"""
config.py — Page config, CSS (dark/light mode), constants.
"""
import hashlib
import streamlit as st

SEED_USERS = [
    ("admin",    hashlib.sha256("admin123".encode()).hexdigest(), "admin",   "Administrator"),
    ("staff1",   hashlib.sha256("staff123".encode()).hexdigest(), "staff",   "Dr. Priya Sharma"),
    ("student1", hashlib.sha256("student123".encode()).hexdigest(),"student","Student User"),
    ("student2", hashlib.sha256("pass1234".encode()).hexdigest(), "student", "Student User 2"),
]

DEMO_CREDENTIALS_NOTE = """
| Username | Password | Role |
|---|---|---|
| admin | admin123 | Admin |
| staff1 | staff123 | Staff |
| student1 | student123 | Student |
"""

SUGGESTIONS = [
    "What are the admission requirements?",
    "When does the semester start?",
    "What documents are needed for registration?",
    "What is the attendance policy?",
    "How do I apply for leave?",
    "What are the exam guidelines?",
    "Who is the HOD of CSE?",
    "What are the library timings?",
]

LANGUAGES = {"en": "English", "ta": "Tamil", "hi": "Hindi", "tanglish": "Tanglish", "hinglish": "Hinglish"}

SESSION_TIMEOUT_MINUTES = 30


def setup_page():
    st.set_page_config(
        page_title="College AI Assistant",
        page_icon="🎓",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    inject_css()


def inject_css():
    dark = st.session_state.get("dark_mode", True)
    if dark:
        theme = """
        --bg:       #0f1117; --bg-2: #1a1d27; --bg-3: #21253a;
        --border:   #2a2f45; --border-2: #363b55;
        --text:     #e4e8f0; --text-2: #8b92a9; --text-3: #545b72;
        --card-bg:  #1a1d27; --input-bg: #1a1d27;
        --bubble-user: #21253a; --bubble-ai: #151b2e;
        """
    else:
        theme = """
        --bg:       #f4f6fb; --bg-2: #ffffff; --bg-3: #eef1f8;
        --border:   #dde3f0; --border-2: #c8d0e7;
        --text:     #1a1d27; --text-2: #4a5170; --text-3: #8b92a9;
        --card-bg:  #ffffff; --input-bg: #f4f6fb;
        --bubble-user: #eef1f8; --bubble-ai: #f0f7ff;
        """

    st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap');

:root {{
    {theme}
    --teal: #00c9a7; --teal-dim: rgba(0,201,167,0.12); --teal-b: rgba(0,201,167,0.25);
    --blue: #4f8ef7; --orange: #f0a500; --red: #f05252; --green: #0ea472;
    --radius: 14px; --radius-sm: 8px; --shadow: 0 4px 24px rgba(0,0,0,0.12);
}}

*, *::before, *::after {{ box-sizing: border-box; }}
html, body, [class*="css"] {{
    font-family: 'Inter', sans-serif !important;
    background: var(--bg) !important;
    color: var(--text) !important;
    -webkit-font-smoothing: antialiased;
}}
.stApp {{ background: var(--bg) !important; }}
#MainMenu, footer, header {{ visibility: hidden !important; }}

/* Hide anchor copy-link icons */
h1 a, h2 a, h3 a, h4 a,
.stMarkdown h1 a, .stMarkdown h2 a, .stMarkdown h3 a,
[data-testid="stMarkdownContainer"] a.anchor {{ display: none !important; }}

/* Layout */
.block-container {{ padding: 1rem 1rem 6rem 1rem !important; max-width: 100% !important; }}
@media (min-width: 768px)  {{ .block-container {{ padding: 1.5rem 2rem 3rem 2rem !important; }} }}
@media (min-width: 1024px) {{ .block-container {{ padding: 2rem 3rem !important; max-width: 1200px !important; }} }}

/* Sidebar */
[data-testid="stSidebar"] {{ background: var(--bg-2) !important; border-right: 1px solid var(--border) !important; }}
[data-testid="stSidebar"] > div {{ padding: 1.2rem 1rem !important; }}
[data-testid="stSidebar"] * {{ font-size: 0.875rem !important; }}

/* App Header */
.app-header {{
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 14px 20px;
    margin-bottom: 14px;
    display: flex; align-items: center; justify-content: space-between;
    flex-wrap: wrap; gap: 8px; box-shadow: var(--shadow);
}}
.app-header-title {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.1rem; font-weight: 600; color: var(--teal);
    display: flex; align-items: center; gap: 10px;
}}
.app-header-meta {{ display: flex; align-items: center; gap: 10px; font-size: 0.8rem; color: var(--text-2); flex-wrap: wrap; }}
@media (min-width: 768px)  {{ .app-header-title {{ font-size: 1.25rem; }} }}
@media (min-width: 1024px) {{ .app-header-title {{ font-size: 1.4rem; }} }}

/* Role Badges */
.role-badge {{ display:inline-flex; align-items:center; padding:3px 10px; border-radius:20px; font-size:0.65rem; font-weight:700; font-family:'JetBrains Mono',monospace; letter-spacing:0.8px; text-transform:uppercase; }}
.role-admin   {{ background:rgba(240,165,0,0.15);  color:#f0a500; border:1px solid rgba(240,165,0,0.3); }}
.role-staff   {{ background:rgba(79,142,247,0.15); color:#79aaff; border:1px solid rgba(79,142,247,0.3); }}
.role-student {{ background:rgba(0,201,167,0.12);  color:#00c9a7; border:1px solid rgba(0,201,167,0.25); }}

/* Chat */
.chat-wrap {{ margin-bottom: 14px; }}
.chat-label {{ font-family:'JetBrains Mono',monospace; font-size:0.6rem; font-weight:600; color:var(--text-3); text-transform:uppercase; letter-spacing:1.2px; margin-bottom:5px; }}
.chat-user {{
    background: var(--bubble-user); border:1px solid var(--border-2);
    border-radius:16px 16px 4px 16px; padding:12px 16px; margin-left:8%;
    font-size:0.92rem; line-height:1.65; word-break:break-word;
}}
.chat-assistant {{
    background: var(--bubble-ai); border:1px solid var(--border);
    border-left:3px solid var(--teal); border-radius:4px 16px 16px 16px;
    padding:14px 16px; margin-right:8%; font-size:0.92rem; line-height:1.75; word-break:break-word;
}}
@media (max-width:767px)  {{ .chat-user {{ margin-left:0; }} .chat-assistant {{ margin-right:0; }} }}
@media (min-width:1024px) {{ .chat-user {{ margin-left:14%; }} .chat-assistant {{ margin-right:14%; }} }}

/* Typing indicator */
.typing-dot {{ display:inline-block; width:8px; height:8px; border-radius:50%; background:var(--teal); margin:0 2px; animation:bounce 1.2s infinite ease-in-out; }}
.typing-dot:nth-child(2) {{ animation-delay:0.2s; }}
.typing-dot:nth-child(3) {{ animation-delay:0.4s; }}
@keyframes bounce {{ 0%,60%,100% {{ transform:translateY(0); }} 30% {{ transform:translateY(-8px); }} }}

/* Confidence */
.conf-wrap   {{ margin-top:12px; padding-top:12px; border-top:1px solid var(--border); }}
.conf-label  {{ font-size:0.6rem; font-family:'JetBrains Mono',monospace; color:var(--text-3); text-transform:uppercase; letter-spacing:0.8px; margin-bottom:5px; }}
.conf-bg     {{ background:rgba(128,128,128,0.1); border-radius:4px; height:5px; }}
.conf-fill   {{ height:5px; border-radius:4px; transition:width 0.4s ease; }}
.conf-high   {{ background:linear-gradient(90deg,#0ea472,#00c9a7); }}
.conf-medium {{ background:linear-gradient(90deg,#f0a500,#fbbf24); }}
.conf-low    {{ background:linear-gradient(90deg,#f05252,#f87171); }}
.conf-pct    {{ font-size:0.7rem; font-family:'JetBrains Mono',monospace; margin-top:4px; }}

/* Sources */
.src-wrap  {{ margin-top:10px; }}
.src-label {{ font-size:0.6rem; font-family:'JetBrains Mono',monospace; color:var(--text-3); text-transform:uppercase; letter-spacing:0.8px; }}
.src-text  {{ font-size:0.78rem; color:var(--text-2); background:rgba(0,0,0,0.05); border-radius:var(--radius-sm); padding:8px 12px; margin-top:5px; border-left:2px solid var(--teal); font-style:italic; }}

/* Action row (copy/feedback/share) */
.action-row {{ display:flex; gap:6px; margin-top:10px; flex-wrap:wrap; align-items:center; }}
.action-btn {{
    display:inline-flex; align-items:center; gap:4px;
    padding:5px 12px; border-radius:6px; font-size:0.75rem; font-weight:500;
    cursor:pointer; border:1px solid var(--border-2); background:var(--bg-3);
    color:var(--text-2); transition:all 0.15s; font-family:'Inter',sans-serif;
    text-decoration:none;
}}
.action-btn:hover {{ border-color:var(--teal); color:var(--teal); background:var(--teal-dim); }}
.action-btn.active {{ background:var(--teal-dim); color:var(--teal); border-color:var(--teal-b); }}

/* Follow-up suggestions */
.followup-wrap {{ margin-top:12px; padding-top:12px; border-top:1px solid var(--border); }}
.followup-label {{ font-size:0.62rem; font-family:'JetBrains Mono',monospace; color:var(--text-3); text-transform:uppercase; letter-spacing:0.8px; margin-bottom:6px; }}
.followup-chip {{
    display:inline-block; padding:5px 12px; border-radius:20px; font-size:0.78rem;
    border:1px solid var(--border-2); background:var(--bg-3); color:var(--text-2);
    cursor:pointer; margin:3px 3px 3px 0; transition:all 0.15s;
}}
.followup-chip:hover {{ border-color:var(--teal); color:var(--teal); }}

/* Alerts */
.alert-error {{ background:rgba(240,82,82,0.1);  border:1px solid rgba(240,82,82,0.3);  border-radius:var(--radius-sm); padding:10px 14px; color:#f05252; font-size:0.85rem; margin:6px 0; }}
.alert-ok    {{ background:rgba(14,164,114,0.1); border:1px solid rgba(14,164,114,0.3); border-radius:var(--radius-sm); padding:10px 14px; color:#0ea472; font-size:0.85rem; margin:6px 0; }}
.alert-info  {{ background:rgba(79,142,247,0.1); border:1px solid rgba(79,142,247,0.3); border-radius:var(--radius-sm); padding:10px 14px; color:#4f8ef7; font-size:0.85rem; margin:6px 0; }}
.alert-warn  {{ background:rgba(240,165,0,0.1);  border:1px solid rgba(240,165,0,0.3);  border-radius:var(--radius-sm); padding:10px 14px; color:#f0a500; font-size:0.85rem; margin:6px 0; }}

/* Status dots */
.dot       {{ display:inline-block; width:7px; height:7px; border-radius:50%; margin-right:6px; }}
.dot-green {{ background:#0ea472; box-shadow:0 0 5px #0ea472; }}
.dot-red   {{ background:#f05252; box-shadow:0 0 5px #f05252; }}
.dot-amber {{ background:#f0a500; box-shadow:0 0 5px #f0a500; }}

/* Stat Cards */
.stat-row  {{ display:flex; gap:8px; flex-wrap:wrap; margin-bottom:12px; }}
.stat-card {{ flex:1; min-width:70px; background:var(--card-bg); border:1px solid var(--border); border-radius:var(--radius-sm); padding:12px 10px; text-align:center; }}
.stat-num  {{ font-family:'JetBrains Mono',monospace; font-size:1.3rem; color:var(--teal); font-weight:700; }}
.stat-lbl  {{ font-size:0.6rem; color:var(--text-3); text-transform:uppercase; letter-spacing:0.4px; margin-top:3px; }}

/* Doc cards */
.doc-card       {{ background:var(--card-bg); border:1px solid var(--border); border-radius:var(--radius-sm); padding:12px 14px; margin-bottom:8px; transition:border-color 0.2s; }}
.doc-card:hover {{ border-color:var(--teal); }}
.doc-card-name  {{ font-size:0.85rem; color:var(--text); font-weight:500; }}
.doc-card-meta  {{ font-size:0.7rem; color:var(--text-3); margin-top:3px; }}
.cat-badge      {{ display:inline-block; padding:2px 8px; border-radius:4px; font-size:0.62rem; font-weight:600; font-family:'JetBrains Mono',monospace; margin-left:6px; }}
.ocr-badge      {{ display:inline-block; background:rgba(240,165,0,0.12); color:#f0a500; border:1px solid rgba(240,165,0,0.25); border-radius:4px; padding:1px 7px; font-size:0.6rem; font-family:'JetBrains Mono',monospace; margin-left:6px; }}

/* Inputs */
.stTextInput > div > div > input,
.stTextArea  > div > div > textarea,
.stNumberInput > div > div > input,
.stSelectbox > div > div > div {{
    background: var(--input-bg) !important; border:1px solid var(--border-2) !important;
    color:var(--text) !important; border-radius:var(--radius-sm) !important;
    font-family:'Inter',sans-serif !important; font-size:0.92rem !important; min-height:44px !important;
}}
.stTextInput > div > div > input:focus {{ border-color:var(--teal) !important; box-shadow:0 0 0 2px var(--teal-dim) !important; }}

/* Buttons */
.stButton > button {{
    background:linear-gradient(135deg,#00c9a7,#00a88a) !important;
    color:#0a0e1a !important; font-weight:600 !important; border:none !important;
    border-radius:var(--radius-sm) !important; font-family:'Inter',sans-serif !important;
    min-height:44px !important; font-size:0.88rem !important; transition:all 0.2s !important;
}}
.stButton > button:hover {{
    background:linear-gradient(135deg,#00deba,#00c9a7) !important;
    box-shadow:0 4px 16px rgba(0,201,167,0.3) !important; transform:translateY(-1px) !important;
}}

/* Divider */
.divider {{ border:none; border-top:1px solid var(--border); margin:12px 0; }}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {{ gap:4px !important; border-bottom:1px solid var(--border) !important; }}
.stTabs [data-baseweb="tab"] {{ padding:10px 18px !important; font-size:0.88rem !important; font-weight:500 !important; border-radius:8px 8px 0 0 !important; color:var(--text-2) !important; background:transparent !important; min-height:44px !important; }}
.stTabs [aria-selected="true"] {{ color:var(--teal) !important; }}

/* File Uploader */
[data-testid="stFileUploader"] {{ border:2px dashed var(--border-2) !important; border-radius:var(--radius) !important; background:transparent !important; }}

/* Mobile Bottom Nav */
.bottom-nav {{
    position:fixed; bottom:0; left:0; right:0; background:var(--bg-2);
    border-top:1px solid var(--border); display:flex; justify-content:space-around;
    align-items:center; padding:6px 0 max(env(safe-area-inset-bottom),6px);
    z-index:9999; box-shadow:0 -4px 20px rgba(0,0,0,0.2);
}}
.bottom-nav-btn {{
    flex:1; display:flex; flex-direction:column; align-items:center;
    gap:2px; padding:5px 2px; font-size:0.55rem; color:var(--text-3);
    cursor:pointer; border:none; background:none; font-family:'Inter',sans-serif;
    text-transform:uppercase; letter-spacing:0.5px; transition:color 0.15s;
    -webkit-tap-highlight-color:transparent;
}}
.bottom-nav-btn .nav-icon {{ font-size:1.2rem; }}
.bottom-nav-btn.active    {{ color:var(--teal); }}
@media (min-width:768px) {{ .bottom-nav {{ display:none !important; }} .block-container {{ padding-bottom:2rem !important; }} }}

/* Mic Banner */
.mic-banner {{ background:rgba(240,82,82,0.07); border:1px dashed rgba(240,82,82,0.35); border-radius:var(--radius-sm); padding:8px 14px; margin-bottom:6px; font-family:'JetBrains Mono',monospace; font-size:0.78rem; color:#f87171; }}

/* Notification Badge */
.notif-badge {{ display:inline-flex; align-items:center; justify-content:center; background:var(--red); color:white; border-radius:10px; font-size:0.6rem; font-weight:700; padding:1px 6px; min-width:18px; margin-left:4px; }}

/* User card */
.user-card {{ background:var(--teal-dim); border:1px solid var(--teal-b); border-radius:var(--radius-sm); padding:12px 14px; margin-bottom:14px; }}
.user-card-label {{ font-size:0.62rem; font-family:'JetBrains Mono',monospace; color:var(--text-3); text-transform:uppercase; letter-spacing:1px; margin-bottom:4px; }}
.user-card-name  {{ font-size:0.95rem; font-weight:600; color:var(--text); }}

/* Onboarding Tour */
.tour-card {{
    background: var(--card-bg); border: 2px solid var(--teal);
    border-radius: var(--radius); padding: 28px 24px;
    box-shadow: 0 8px 40px rgba(0,201,167,0.15);
    text-align: center; max-width: 500px; margin: 40px auto;
}}
.tour-step {{ font-family:'JetBrains Mono',monospace; font-size:0.7rem; color:var(--teal); text-transform:uppercase; letter-spacing:1px; margin-bottom:8px; }}
.tour-title {{ font-size:1.4rem; font-weight:700; color:var(--text); margin-bottom:8px; }}
.tour-desc  {{ font-size:0.9rem; color:var(--text-2); line-height:1.6; }}

/* Dashboard */
.dash-card {{ background:var(--card-bg); border:1px solid var(--border); border-radius:var(--radius); padding:16px 20px; margin-bottom:14px; }}
.dash-title {{ font-size:0.8rem; font-weight:600; color:var(--text-2); text-transform:uppercase; letter-spacing:0.5px; margin-bottom:12px; font-family:'JetBrains Mono',monospace; }}

/* Session timeout warning */
.timeout-bar {{ background:rgba(240,165,0,0.1); border:1px solid rgba(240,165,0,0.3); border-radius:var(--radius-sm); padding:8px 14px; font-size:0.82rem; color:#f0a500; margin-bottom:10px; display:flex; align-items:center; gap:8px; }}
</style>
""", unsafe_allow_html=True)