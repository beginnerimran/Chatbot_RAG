"""
config.py — Page configuration, CSS styles, and app-wide constants.
"""

import streamlit as st


# ─────────────────────────────────────────────
# SEED DATA & CONSTANTS
# ─────────────────────────────────────────────
import hashlib

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
# CSS
# ─────────────────────────────────────────────
def inject_css():
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap');

:root {
    --bg-primary:   #0a0e1a;
    --bg-secondary: #111827;
    --bg-card:      #1a2235;
    --accent-teal:  #00d4aa;
    --accent-blue:  #3b82f6;
    --accent-orange:#f59e0b;
    --text-primary: #e2e8f0;
    --text-secondary:#94a3b8;
    --border:       #1e293b;
    --danger:       #ef4444;
    --success:      #10b981;
    --radius:       12px;
}

html, body, [class*="css"] {
    font-family: 'IBM Plex Sans', sans-serif !important;
    background-color: var(--bg-primary) !important;
    color: var(--text-primary) !important;
    box-sizing: border-box;
}
.stApp { background-color: var(--bg-primary) !important; }
#MainMenu, footer, header { visibility: hidden; }

.block-container {
    padding: 1rem 0.8rem 5.5rem 0.8rem !important;
    max-width: 100% !important;
    width: 100% !important;
}
@media (min-width: 768px) {
    .block-container { padding: 1.5rem 2rem 2.5rem 2rem !important; }
}
@media (min-width: 1024px) {
    .block-container { padding: 2rem 3rem 2rem 3rem !important; max-width: 1100px !important; }
}
@media (min-width: 1440px) {
    .block-container { max-width: 1300px !important; padding: 2rem 4rem 2rem 4rem !important; }
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0d1525 0%, #111827 100%) !important;
    border-right: 1px solid var(--border) !important;
    min-width: 260px !important;
}
[data-testid="stSidebar"] * { font-size: 0.88rem !important; }

.app-header {
    background: linear-gradient(135deg, #0d1525 0%, #1a2235 100%);
    border: 1px solid #1e3a5f;
    border-radius: var(--radius);
    padding: 14px 16px;
    margin-bottom: 14px;
    box-shadow: 0 4px 20px rgba(0,212,170,0.08);
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
}
.app-header h1 { font-family:'IBM Plex Mono',monospace; color:var(--accent-teal); font-size:1.1rem; margin:0; }
.app-header p  { color:var(--text-secondary); font-size:0.75rem; margin:3px 0 0; font-family:'IBM Plex Mono',monospace; }
@media (min-width: 768px)  { .app-header { padding:18px 24px; } .app-header h1 { font-size:1.35rem; } }
@media (min-width: 1024px) { .app-header h1 { font-size:1.55rem; } }

.role-badge {
    display:inline-block; padding:3px 10px; border-radius:20px;
    font-size:0.7rem; font-weight:600; font-family:'IBM Plex Mono',monospace;
    letter-spacing:0.5px; text-transform:uppercase;
}
.role-admin   { background:rgba(245,158,11,0.15); color:#f59e0b; border:1px solid rgba(245,158,11,0.3); }
.role-staff   { background:rgba(59,130,246,0.15);  color:#60a5fa; border:1px solid rgba(59,130,246,0.3); }
.role-student { background:rgba(0,212,170,0.12);   color:#00d4aa; border:1px solid rgba(0,212,170,0.25); }

.chat-user {
    background: linear-gradient(135deg, #1e3a5f 0%, #1a2235 100%);
    border: 1px solid #2d4a6e; border-radius: 14px 14px 4px 14px;
    padding: 11px 14px; margin: 6px 0 6px 16px;
    color: var(--text-primary); font-size: 0.9rem; line-height: 1.65; word-break: break-word;
}
.chat-assistant {
    background: linear-gradient(135deg, #162232 0%, #1a2235 100%);
    border: 1px solid #1e4030; border-left: 3px solid var(--accent-teal);
    border-radius: 4px 14px 14px 14px;
    padding: 11px 14px; margin: 6px 16px 6px 0;
    color: var(--text-primary); font-size: 0.9rem; line-height: 1.75; word-break: break-word;
}
@media (min-width: 768px) {
    .chat-user      { margin-left:48px;  font-size:0.93rem; padding:12px 18px; }
    .chat-assistant { margin-right:48px; font-size:0.93rem; padding:12px 18px; }
}
@media (min-width: 1024px) {
    .chat-user      { margin-left:80px;  font-size:0.95rem; }
    .chat-assistant { margin-right:80px; font-size:0.95rem; }
}
.chat-label { font-family:'IBM Plex Mono',monospace; font-size:0.63rem; color:var(--text-secondary); text-transform:uppercase; letter-spacing:1px; margin-bottom:4px; }
.msg-time   { font-family:'IBM Plex Mono',monospace; font-size:0.6rem; color:var(--text-secondary); margin-top:4px; opacity:0.7; }

.confidence-bar-wrap { margin-top:10px; padding-top:10px; border-top:1px solid var(--border); }
.confidence-label    { font-family:'IBM Plex Mono',monospace; font-size:0.63rem; color:var(--text-secondary); text-transform:uppercase; letter-spacing:0.8px; margin-bottom:4px; }
.confidence-bar-bg   { background:rgba(255,255,255,0.07); border-radius:4px; height:6px; width:100%; }
.confidence-bar-fill { height:6px; border-radius:4px; transition:width 0.4s ease; }
.conf-high   { background: linear-gradient(90deg,#10b981,#00d4aa); }
.conf-medium { background: linear-gradient(90deg,#f59e0b,#fbbf24); }
.conf-low    { background: linear-gradient(90deg,#ef4444,#f87171); }
.confidence-pct { font-family:'IBM Plex Mono',monospace; font-size:0.72rem; margin-top:3px; }

.source-chips { margin-top:8px; }
.source-label { font-family:'IBM Plex Mono',monospace; font-size:0.63rem; color:var(--text-secondary); text-transform:uppercase; letter-spacing:0.8px; }
.source-text  { font-size:0.78rem; color:var(--text-secondary); background:rgba(0,0,0,0.3); border-radius:6px; padding:8px 12px; margin-top:4px; border-left:2px solid var(--accent-teal); font-style:italic; }

.ocr-badge { display:inline-block; background:rgba(245,158,11,0.15); color:#f59e0b; border:1px solid rgba(245,158,11,0.3); border-radius:4px; padding:2px 8px; font-size:0.63rem; font-family:'IBM Plex Mono',monospace; margin-left:8px; }

.stat-row  { display:flex; gap:8px; margin-bottom:14px; flex-wrap:wrap; }
.stat-card { flex:1; min-width:60px; background:var(--bg-card); border:1px solid var(--border); border-radius:8px; padding:10px 8px; text-align:center; }
.stat-num  { font-family:'IBM Plex Mono',monospace; font-size:1.2rem; color:var(--accent-teal); font-weight:600; }
.stat-lbl  { font-size:0.63rem; color:var(--text-secondary); text-transform:uppercase; letter-spacing:0.4px; }

.doc-card { background:var(--bg-card); border:1px solid var(--border); border-radius:10px; padding:12px 14px; margin-bottom:8px; transition:border-color 0.2s; }
.doc-card:hover { border-color:var(--accent-teal); }
.doc-card-name { font-size:0.85rem; color:#e2e8f0; font-weight:500; word-break:break-all; }
.doc-card-meta { font-size:0.7rem; color:#475569; margin-top:3px; }

.login-card { background:var(--bg-card); border:1px solid #1e3a5f; border-radius:16px; padding:28px 20px; box-shadow:0 20px 60px rgba(0,0,0,0.5); margin-bottom:12px; max-width:460px; margin-left:auto; margin-right:auto; }
.login-title { font-family:'IBM Plex Mono',monospace; color:var(--accent-teal); font-size:1.3rem; margin-bottom:4px; }
.login-sub   { color:var(--text-secondary); font-size:0.78rem; font-family:'IBM Plex Mono',monospace; }

.status-dot { display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:6px; }
.dot-green  { background:var(--success); box-shadow:0 0 6px var(--success); }
.dot-red    { background:var(--danger);  box-shadow:0 0 6px var(--danger); }
.dot-yellow { background:var(--accent-orange); box-shadow:0 0 6px var(--accent-orange); }
.section-divider { border:none; border-top:1px solid var(--border); margin:14px 0; }
.alert-error   { background:rgba(239,68,68,0.1);  border:1px solid rgba(239,68,68,0.3);  border-radius:8px; padding:10px 14px; color:#fca5a5; font-size:0.85rem; margin:8px 0; }
.alert-success { background:rgba(16,185,129,0.1); border:1px solid rgba(16,185,129,0.3); border-radius:8px; padding:10px 14px; color:#6ee7b7; font-size:0.85rem; margin:8px 0; }
.alert-info    { background:rgba(59,130,246,0.1); border:1px solid rgba(59,130,246,0.3); border-radius:8px; padding:10px 14px; color:#93c5fd; font-size:0.85rem; margin:8px 0; }

.stTextInput > div > div > input,
.stTextArea  > div > div > textarea {
    background:var(--bg-secondary) !important; border:1px solid var(--border) !important;
    color:var(--text-primary) !important; border-radius:10px !important;
    font-family:'IBM Plex Sans',sans-serif !important; font-size:0.95rem !important;
    padding:11px 14px !important; min-height:48px !important;
}
.stButton > button {
    background:linear-gradient(135deg,#00d4aa,#00b894) !important; color:#0a0e1a !important;
    font-weight:600 !important; border:none !important; border-radius:10px !important;
    font-family:'IBM Plex Sans',sans-serif !important; min-height:48px !important;
    font-size:0.92rem !important; transition:box-shadow 0.2s !important;
}
.stButton > button:hover {
    background:linear-gradient(135deg,#00e5b8,#00c9a7) !important;
    box-shadow:0 4px 15px rgba(0,212,170,0.35) !important;
}

.stTabs [data-baseweb="tab-list"] { gap:4px !important; flex-wrap:wrap !important; }
.stTabs [data-baseweb="tab"] { padding:10px 14px !important; font-size:0.88rem !important; border-radius:8px 8px 0 0 !important; white-space:nowrap !important; }

[data-testid="stFileUploader"] { border:2px dashed var(--border) !important; border-radius:10px !important; padding:12px !important; background:rgba(0,0,0,0.15) !important; }

.bottom-nav {
    position:fixed; bottom:0; left:0; right:0; background:#0a0e1a;
    border-top:1px solid #1e293b; display:flex; justify-content:space-around;
    align-items:center; padding:6px 0 env(safe-area-inset-bottom,8px);
    z-index:9999; box-shadow:0 -4px 20px rgba(0,0,0,0.4);
}
.bottom-nav-btn { flex:1; text-align:center; padding:5px 2px; font-size:0.58rem; color:#64748b; cursor:pointer; font-family:'IBM Plex Mono',monospace; text-transform:uppercase; letter-spacing:0.4px; border:none; background:none; display:flex; flex-direction:column; align-items:center; gap:2px; -webkit-tap-highlight-color:transparent; transition:color 0.15s; }
.bottom-nav-btn .nav-icon { font-size:1.25rem; }
.bottom-nav-btn.active    { color:#00d4aa; }
@media (min-width:768px) { .bottom-nav { display:none !important; } .block-container { padding-bottom:2rem !important; } }

.suggestion-wrap { display:grid; grid-template-columns:1fr 1fr; gap:8px; margin:10px 0; }
@media (min-width:640px)  { .suggestion-wrap { grid-template-columns:1fr 1fr 1fr; } }
@media (min-width:1024px) { .suggestion-wrap { grid-template-columns:1fr 1fr 1fr 1fr; } }

/* Share action buttons */
.share-btn-row { display:flex; gap:8px; margin-top:10px; flex-wrap:wrap; }
.share-btn {
    display:inline-flex; align-items:center; gap:6px;
    padding:6px 14px; border-radius:8px; font-size:0.78rem; font-weight:600;
    cursor:pointer; text-decoration:none; border:none; font-family:'IBM Plex Sans',sans-serif;
    transition:opacity 0.2s;
}
.share-btn:hover { opacity:0.85; }
.btn-pdf  { background:rgba(239,68,68,0.15); color:#fca5a5; border:1px solid rgba(239,68,68,0.3); }
.btn-wa   { background:rgba(37,211,102,0.15); color:#4ade80; border:1px solid rgba(37,211,102,0.3); }
</style>
""", unsafe_allow_html=True)
