"""
config.py — Page configuration, CSS styles, and app-wide constants.
Production-level responsive design. Works on mobile, tablet, and desktop.
"""

import hashlib
import streamlit as st


# ─────────────────────────────────────────────
# SEED DATA & CONSTANTS
# ─────────────────────────────────────────────
SEED_USERS = [
    ("admin",    hashlib.sha256("admin123".encode()).hexdigest(),  "admin",   "Administrator"),
    ("staff1",   hashlib.sha256("staff123".encode()).hexdigest(),  "staff",   "Dr. Priya Sharma"),
    ("student1", hashlib.sha256("student123".encode()).hexdigest(),"student", "Student User"),
    ("student2", hashlib.sha256("pass1234".encode()).hexdigest(),  "student", "Student User 2"),
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


# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────
def setup_page():
    st.set_page_config(
        page_title="College AI Assistant",
        page_icon="🎓",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    inject_css()


# ─────────────────────────────────────────────
# CSS — Production level, fully responsive
# ─────────────────────────────────────────────
def inject_css():
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap');

:root {
    --bg:          #0f1117;
    --bg-2:        #1a1d27;
    --bg-3:        #21253a;
    --border:      #2a2f45;
    --border-2:    #363b55;
    --teal:        #00c9a7;
    --teal-dim:    rgba(0,201,167,0.12);
    --teal-border: rgba(0,201,167,0.25);
    --blue:        #4f8ef7;
    --orange:      #f0a500;
    --red:         #f05252;
    --green:       #0ea472;
    --text:        #e4e8f0;
    --text-2:      #8b92a9;
    --text-3:      #545b72;
    --radius:      14px;
    --radius-sm:   8px;
    --shadow:      0 4px 24px rgba(0,0,0,0.4);
}

*, *::before, *::after { box-sizing: border-box; }

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
    background: var(--bg) !important;
    color: var(--text) !important;
    -webkit-font-smoothing: antialiased;
}
.stApp { background: var(--bg) !important; }
#MainMenu, footer, header { visibility: hidden !important; }

/* Hide anchor link copy buttons on headings */
h1 a, h2 a, h3 a, h4 a,
.stMarkdown h1 a, .stMarkdown h2 a, .stMarkdown h3 a,
[data-testid="stMarkdownContainer"] a.anchor { display: none !important; }

/* Layout */
.block-container { padding: 1rem 1rem 6rem 1rem !important; max-width: 100% !important; }
@media (min-width: 768px)  { .block-container { padding: 1.5rem 2rem 3rem 2rem !important; } }
@media (min-width: 1024px) { .block-container { padding: 2rem 3rem !important; max-width: 1200px !important; } }

/* Sidebar */
[data-testid="stSidebar"] { background: var(--bg-2) !important; border-right: 1px solid var(--border) !important; }
[data-testid="stSidebar"] > div { padding: 1.5rem 1rem !important; }
[data-testid="stSidebar"] * { font-size: 0.875rem !important; }

/* App Header */
.app-header {
    background: linear-gradient(135deg, var(--bg-2) 0%, var(--bg-3) 100%);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 16px 20px;
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 8px;
    box-shadow: var(--shadow);
}
.app-header-title {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.1rem;
    font-weight: 600;
    color: var(--teal);
    display: flex;
    align-items: center;
    gap: 10px;
}
.app-header-meta { display: flex; align-items: center; gap: 10px; font-size: 0.8rem; color: var(--text-2); }
@media (min-width: 768px)  { .app-header-title { font-size: 1.25rem; } }
@media (min-width: 1024px) { .app-header-title { font-size: 1.4rem; } }

/* Role Badges */
.role-badge {
    display: inline-flex; align-items: center;
    padding: 3px 10px; border-radius: 20px;
    font-size: 0.65rem; font-weight: 700;
    font-family: 'JetBrains Mono', monospace;
    letter-spacing: 0.8px; text-transform: uppercase;
}
.role-admin   { background: rgba(240,165,0,0.15);  color: #f0a500; border: 1px solid rgba(240,165,0,0.3); }
.role-staff   { background: rgba(79,142,247,0.15); color: #79aaff; border: 1px solid rgba(79,142,247,0.3); }
.role-student { background: rgba(0,201,167,0.12);  color: #00c9a7; border: 1px solid rgba(0,201,167,0.25); }

/* Chat Bubbles */
.chat-wrap    { margin-bottom: 16px; }
.chat-label   { font-family: 'JetBrains Mono', monospace; font-size: 0.6rem; font-weight: 600; color: var(--text-3); text-transform: uppercase; letter-spacing: 1.2px; margin-bottom: 5px; }
.chat-user    { background: var(--bg-3); border: 1px solid var(--border-2); border-radius: 16px 16px 4px 16px; padding: 12px 16px; margin-left: 8%; color: var(--text); font-size: 0.92rem; line-height: 1.65; word-break: break-word; }
.chat-assistant { background: linear-gradient(135deg, #151b2e 0%, #1a2035 100%); border: 1px solid var(--border); border-left: 3px solid var(--teal); border-radius: 4px 16px 16px 16px; padding: 14px 16px; margin-right: 8%; color: var(--text); font-size: 0.92rem; line-height: 1.75; word-break: break-word; }
@media (max-width: 767px) { .chat-user { margin-left: 0; } .chat-assistant { margin-right: 0; } }
@media (min-width: 1024px) { .chat-user { margin-left: 14%; } .chat-assistant { margin-right: 14%; } }

/* Confidence Bar */
.conf-wrap   { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border); }
.conf-label  { font-size: 0.6rem; font-family: 'JetBrains Mono', monospace; color: var(--text-3); text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 5px; }
.conf-bg     { background: rgba(255,255,255,0.06); border-radius: 4px; height: 5px; }
.conf-fill   { height: 5px; border-radius: 4px; transition: width 0.4s ease; }
.conf-high   { background: linear-gradient(90deg, #0ea472, #00c9a7); }
.conf-medium { background: linear-gradient(90deg, #f0a500, #fbbf24); }
.conf-low    { background: linear-gradient(90deg, #f05252, #f87171); }
.conf-pct    { font-size: 0.7rem; font-family: 'JetBrains Mono', monospace; margin-top: 4px; }

/* Source Excerpts */
.src-wrap  { margin-top: 10px; }
.src-label { font-size: 0.6rem; font-family: 'JetBrains Mono', monospace; color: var(--text-3); text-transform: uppercase; letter-spacing: 0.8px; }
.src-text  { font-size: 0.78rem; color: var(--text-2); background: rgba(0,0,0,0.25); border-radius: var(--radius-sm); padding: 8px 12px; margin-top: 5px; border-left: 2px solid var(--teal); font-style: italic; }

/* Alerts */
.alert-error { background: rgba(240,82,82,0.1);  border: 1px solid rgba(240,82,82,0.3);  border-radius: var(--radius-sm); padding: 10px 14px; color: #fca5a5; font-size: 0.85rem; margin: 6px 0; }
.alert-ok    { background: rgba(14,164,114,0.1); border: 1px solid rgba(14,164,114,0.3); border-radius: var(--radius-sm); padding: 10px 14px; color: #6ee7b7; font-size: 0.85rem; margin: 6px 0; }
.alert-info  { background: rgba(79,142,247,0.1); border: 1px solid rgba(79,142,247,0.3); border-radius: var(--radius-sm); padding: 10px 14px; color: #93c5fd; font-size: 0.85rem; margin: 6px 0; }

/* Status dots */
.dot       { display: inline-block; width: 7px; height: 7px; border-radius: 50%; margin-right: 6px; }
.dot-green { background: var(--green);  box-shadow: 0 0 5px var(--green); }
.dot-red   { background: var(--red);    box-shadow: 0 0 5px var(--red); }
.dot-amber { background: var(--orange); box-shadow: 0 0 5px var(--orange); }

/* Stat Cards */
.stat-row  { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }
.stat-card { flex: 1; min-width: 55px; background: var(--bg-3); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 10px 8px; text-align: center; }
.stat-num  { font-family: 'JetBrains Mono', monospace; font-size: 1.15rem; color: var(--teal); font-weight: 700; }
.stat-lbl  { font-size: 0.6rem; color: var(--text-3); text-transform: uppercase; letter-spacing: 0.4px; margin-top: 2px; }

/* Doc Cards */
.doc-card       { background: var(--bg-3); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 12px 14px; margin-bottom: 8px; transition: border-color 0.2s; }
.doc-card:hover { border-color: var(--teal); }
.doc-card-name  { font-size: 0.85rem; color: var(--text); font-weight: 500; }
.doc-card-meta  { font-size: 0.7rem; color: var(--text-3); margin-top: 3px; }
.ocr-badge      { display: inline-block; background: rgba(240,165,0,0.12); color: var(--orange); border: 1px solid rgba(240,165,0,0.25); border-radius: 4px; padding: 1px 7px; font-size: 0.6rem; font-family: 'JetBrains Mono', monospace; margin-left: 6px; }

/* Inputs & Buttons */
.stTextInput > div > div > input,
.stTextArea  > div > div > textarea,
.stNumberInput > div > div > input {
    background: var(--bg-2) !important; border: 1px solid var(--border-2) !important;
    color: var(--text) !important; border-radius: var(--radius-sm) !important;
    font-family: 'Inter', sans-serif !important; font-size: 0.92rem !important; min-height: 44px !important;
}
.stTextInput > div > div > input:focus { border-color: var(--teal) !important; box-shadow: 0 0 0 2px var(--teal-dim) !important; }

.stButton > button {
    background: linear-gradient(135deg, #00c9a7, #00a88a) !important;
    color: #0a0e1a !important; font-weight: 600 !important; border: none !important;
    border-radius: var(--radius-sm) !important; font-family: 'Inter', sans-serif !important;
    min-height: 44px !important; font-size: 0.88rem !important; transition: all 0.2s !important;
}
.stButton > button:hover {
    background: linear-gradient(135deg, #00deba, #00c9a7) !important;
    box-shadow: 0 4px 16px rgba(0,201,167,0.3) !important; transform: translateY(-1px) !important;
}

/* Divider */
.divider { border: none; border-top: 1px solid var(--border); margin: 14px 0; }

/* Tabs */
.stTabs [data-baseweb="tab-list"] { gap: 4px !important; border-bottom: 1px solid var(--border) !important; }
.stTabs [data-baseweb="tab"] { padding: 10px 18px !important; font-size: 0.88rem !important; font-weight: 500 !important; border-radius: 8px 8px 0 0 !important; color: var(--text-2) !important; background: transparent !important; min-height: 44px !important; }
.stTabs [aria-selected="true"] { color: var(--teal) !important; }

/* File Uploader */
[data-testid="stFileUploader"] { border: 2px dashed var(--border-2) !important; border-radius: var(--radius) !important; background: rgba(0,0,0,0.1) !important; }

/* Mobile Bottom Nav */
.bottom-nav {
    position: fixed; bottom: 0; left: 0; right: 0;
    background: var(--bg-2); border-top: 1px solid var(--border);
    display: flex; justify-content: space-around; align-items: center;
    padding: 6px 0 max(env(safe-area-inset-bottom), 6px);
    z-index: 9999; box-shadow: 0 -4px 20px rgba(0,0,0,0.5);
}
.bottom-nav-btn {
    flex: 1; display: flex; flex-direction: column; align-items: center;
    gap: 2px; padding: 5px 2px; font-size: 0.55rem; color: var(--text-3);
    cursor: pointer; border: none; background: none;
    font-family: 'Inter', sans-serif; text-transform: uppercase; letter-spacing: 0.5px;
    transition: color 0.15s; -webkit-tap-highlight-color: transparent;
}
.bottom-nav-btn .nav-icon { font-size: 1.2rem; }
.bottom-nav-btn.active    { color: var(--teal); }
@media (min-width: 768px) { .bottom-nav { display: none !important; } .block-container { padding-bottom: 2rem !important; } }

/* Mic Banner */
.mic-banner {
    background: rgba(240,82,82,0.07); border: 1px dashed rgba(240,82,82,0.35);
    border-radius: var(--radius-sm); padding: 8px 14px; margin-bottom: 6px;
    font-family: 'JetBrains Mono', monospace; font-size: 0.78rem; color: #fca5a5;
}

/* User Card in Sidebar */
.user-card { background: rgba(0,0,0,0.25); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 12px 14px; margin-bottom: 14px; }
.user-card-label { font-size: 0.62rem; font-family: 'JetBrains Mono', monospace; color: var(--text-3); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px; }
.user-card-name  { font-size: 0.92rem; font-weight: 600; color: var(--text); }
</style>
""", unsafe_allow_html=True)