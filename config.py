"""
config.py — Page config, CSS (SRM blue/white theme), constants.
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

SESSION_TIMEOUT_MINUTES = 30


def setup_page():
    st.set_page_config(
        page_title="SRM College AI Assistant",
        page_icon="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>S</text></svg>",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    inject_css()


def inject_css():
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap');

:root {
    /* SRM Blue & White Theme */
    --bg:        #f0f4fa;
    --bg-2:      #ffffff;
    --bg-3:      #e8eef7;
    --border:    #d0dbe f;
    --border-2:  #b8c9e0;
    --text:      #1a2640;
    --text-2:    #3d5275;
    --text-3:    #6b82a0;
    --card-bg:   #ffffff;
    --input-bg:  #f7f9fc;

    /* SRM Primary Blue */
    --blue:      #1a4fa0;
    --blue-2:    #2563c0;
    --blue-dim:  rgba(26,79,160,0.08);
    --blue-b:    rgba(26,79,160,0.20);
    --blue-light:#4a84d4;

    /* Accent */
    --teal:      #1a4fa0;
    --teal-dim:  rgba(26,79,160,0.08);
    --teal-b:    rgba(26,79,160,0.20);

    --orange:    #e07b00;
    --red:       #c0392b;
    --green:     #0a7c4e;
    --radius:    12px;
    --radius-sm: 8px;
    --shadow:    0 2px 16px rgba(26,79,160,0.10);
    --shadow-lg: 0 4px 32px rgba(26,79,160,0.14);
}

*, *::before, *::after { box-sizing: border-box; }
html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
    background: var(--bg) !important;
    color: var(--text) !important;
    -webkit-font-smoothing: antialiased;
}
.stApp { background: var(--bg) !important; }

/* Hide Streamlit chrome */
#MainMenu { visibility: hidden !important; }
footer    { visibility: hidden !important; }
[data-testid="stToolbar"] { visibility: hidden !important; }
[data-testid="collapsedControl"] { visibility: visible !important; display: flex !important; opacity: 1 !important; }
[data-testid="stSidebarCollapseButton"] { visibility: visible !important; display: flex !important; opacity: 1 !important; }

/* Hide anchor copy-link icons */
h1 a, h2 a, h3 a, h4 a,
.stMarkdown h1 a, .stMarkdown h2 a, .stMarkdown h3 a,
[data-testid="stMarkdownContainer"] a.anchor { display: none !important; }

/* Layout */
.block-container { padding: 1rem 1rem 6rem 1rem !important; max-width: 100% !important; }
@media (min-width: 768px)  { .block-container { padding: 1.5rem 2rem 3rem 2rem !important; } }
@media (min-width: 1024px) { .block-container { padding: 2rem 3rem !important; max-width: 1200px !important; } }

/* Sidebar */
[data-testid="stSidebar"] {
    background: var(--blue) !important;
    border-right: 1px solid rgba(255,255,255,0.12) !important;
}
[data-testid="stSidebar"] > div { padding: 1.2rem 1rem !important; }
[data-testid="stSidebar"] * {
    font-size: 0.875rem !important;
    color: rgba(255,255,255,0.92) !important;
}
[data-testid="stSidebar"] strong { color: #ffffff !important; }
[data-testid="stSidebar"] .stButton > button {
    background: rgba(255,255,255,0.15) !important;
    color: #ffffff !important;
    border: 1px solid rgba(255,255,255,0.25) !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(255,255,255,0.28) !important;
    box-shadow: none !important;
    transform: none !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] {
    background: rgba(255,255,255,0.08) !important;
    border: 1px solid rgba(255,255,255,0.15) !important;
    border-radius: var(--radius-sm) !important;
}
[data-testid="stSidebar"] .stSelectbox > div > div > div {
    background: rgba(255,255,255,0.15) !important;
    border: 1px solid rgba(255,255,255,0.25) !important;
    color: #ffffff !important;
}
[data-testid="stSidebar"] [data-testid="stFileUploader"] {
    border: 2px dashed rgba(255,255,255,0.3) !important;
    background: rgba(255,255,255,0.06) !important;
}
[data-testid="stSidebar"] .stInfo {
    background: rgba(255,255,255,0.12) !important;
    color: rgba(255,255,255,0.9) !important;
}
[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.2) !important; }

/* App Header */
.app-header {
    background: var(--blue);
    border-radius: var(--radius);
    padding: 14px 20px;
    margin-bottom: 16px;
    display: flex; align-items: center; justify-content: space-between;
    flex-wrap: wrap; gap: 8px;
    box-shadow: var(--shadow-lg);
}
.app-header-title {
    font-family: 'Inter', sans-serif;
    font-size: 1.1rem; font-weight: 700; color: #ffffff;
    display: flex; align-items: center; gap: 10px; letter-spacing: 0.2px;
}
.app-header-meta {
    display: flex; align-items: center; gap: 10px;
    font-size: 0.8rem; color: rgba(255,255,255,0.80); flex-wrap: wrap;
}
@media (min-width: 768px)  { .app-header-title { font-size: 1.25rem; } }
@media (min-width: 1024px) { .app-header-title { font-size: 1.4rem; } }

/* SRM Logo area in header */
.srm-logo-text {
    background: rgba(255,255,255,0.15);
    color: #ffffff;
    font-weight: 800;
    font-size: 1.1rem;
    padding: 4px 12px;
    border-radius: 6px;
    letter-spacing: 1px;
}

/* Role Badges */
.role-badge { display:inline-flex; align-items:center; padding:3px 10px; border-radius:20px; font-size:0.65rem; font-weight:700; font-family:'Inter',sans-serif; letter-spacing:0.8px; text-transform:uppercase; }
.role-admin   { background:rgba(224,123,0,0.15);   color:#b86200; border:1px solid rgba(224,123,0,0.3); }
.role-staff   { background:rgba(26,79,160,0.12);   color:#1a4fa0; border:1px solid rgba(26,79,160,0.25); }
.role-student { background:rgba(10,124,78,0.12);   color:#0a7c4e; border:1px solid rgba(10,124,78,0.25); }

/* In sidebar — invert badge colors for dark bg */
[data-testid="stSidebar"] .role-badge { background: rgba(255,255,255,0.18) !important; color: #fff !important; border-color: rgba(255,255,255,0.3) !important; }

/* Chat */
.chat-wrap { margin-bottom: 14px; }
.chat-label { font-family:'Inter',sans-serif; font-size:0.68rem; font-weight:600; color:var(--text-3); text-transform:uppercase; letter-spacing:1.2px; margin-bottom:5px; }
.chat-user {
    background: var(--blue-dim); border:1px solid var(--blue-b);
    border-radius:16px 16px 4px 16px; padding:12px 16px; margin-left:8%;
    font-size:0.92rem; line-height:1.65; word-break:break-word; color:var(--text);
}
.chat-assistant {
    background: var(--card-bg); border:1px solid var(--border);
    border-left:3px solid var(--blue); border-radius:4px 16px 16px 16px;
    padding:14px 16px; margin-right:8%; font-size:0.92rem; line-height:1.75;
    word-break:break-word; color:var(--text); box-shadow: var(--shadow);
}
@media (max-width:767px)  { .chat-user { margin-left:0; } .chat-assistant { margin-right:0; } }
@media (min-width:1024px) { .chat-user { margin-left:14%; } .chat-assistant { margin-right:14%; } }

/* Typing indicator */
.typing-dot { display:inline-block; width:8px; height:8px; border-radius:50%; background:var(--blue); margin:0 2px; animation:bounce 1.2s infinite ease-in-out; }
.typing-dot:nth-child(2) { animation-delay:0.2s; }
.typing-dot:nth-child(3) { animation-delay:0.4s; }
@keyframes bounce { 0%,60%,100% { transform:translateY(0); } 30% { transform:translateY(-8px); } }

/* Confidence */
.conf-wrap   { margin-top:12px; padding-top:12px; border-top:1px solid var(--border); }
.conf-label  { font-size:0.6rem; font-family:'Inter',sans-serif; color:var(--text-3); text-transform:uppercase; letter-spacing:0.8px; margin-bottom:5px; }
.conf-bg     { background:rgba(26,79,160,0.08); border-radius:4px; height:5px; }
.conf-fill   { height:5px; border-radius:4px; transition:width 0.4s ease; }
.conf-high   { background:linear-gradient(90deg,#0a7c4e,#1a9964); }
.conf-medium { background:linear-gradient(90deg,#e07b00,#f59e0b); }
.conf-low    { background:linear-gradient(90deg,#c0392b,#e05252); }
.conf-pct    { font-size:0.7rem; font-family:'JetBrains Mono',monospace; margin-top:4px; }

/* Sources */
.src-wrap  { margin-top:10px; }
.src-label { font-size:0.6rem; font-family:'Inter',sans-serif; color:var(--text-3); text-transform:uppercase; letter-spacing:0.8px; }
.src-text  { font-size:0.78rem; color:var(--text-2); background:var(--blue-dim); border-radius:var(--radius-sm); padding:8px 12px; margin-top:5px; border-left:2px solid var(--blue); font-style:italic; }

/* Action row */
.action-row { display:flex; gap:6px; margin-top:10px; flex-wrap:wrap; align-items:center; }
.action-btn {
    display:inline-flex; align-items:center; gap:4px;
    padding:5px 12px; border-radius:6px; font-size:0.75rem; font-weight:500;
    cursor:pointer; border:1px solid var(--border-2); background:var(--bg-3);
    color:var(--text-2); transition:all 0.15s; font-family:'Inter',sans-serif;
    text-decoration:none;
}
.action-btn:hover { border-color:var(--blue); color:var(--blue); background:var(--blue-dim); }
.action-btn.active { background:var(--blue-dim); color:var(--blue); border-color:var(--blue-b); }

/* Follow-up suggestions */
.followup-wrap { margin-top:12px; padding-top:12px; border-top:1px solid var(--border); }
.followup-label { font-size:0.62rem; font-family:'Inter',sans-serif; color:var(--text-3); text-transform:uppercase; letter-spacing:0.8px; margin-bottom:6px; }
.followup-chip {
    display:inline-block; padding:5px 12px; border-radius:20px; font-size:0.78rem;
    border:1px solid var(--border-2); background:var(--bg-3); color:var(--text-2);
    cursor:pointer; margin:3px 3px 3px 0; transition:all 0.15s;
}
.followup-chip:hover { border-color:var(--blue); color:var(--blue); }

/* Alerts */
.alert-error { background:rgba(192,57,43,0.08);  border:1px solid rgba(192,57,43,0.25);  border-radius:var(--radius-sm); padding:10px 14px; color:#a93226; font-size:0.85rem; margin:6px 0; }
.alert-ok    { background:rgba(10,124,78,0.08);  border:1px solid rgba(10,124,78,0.25);  border-radius:var(--radius-sm); padding:10px 14px; color:#0a7c4e; font-size:0.85rem; margin:6px 0; }
.alert-info  { background:rgba(26,79,160,0.08);  border:1px solid rgba(26,79,160,0.20);  border-radius:var(--radius-sm); padding:10px 14px; color:#1a4fa0; font-size:0.85rem; margin:6px 0; }
.alert-warn  { background:rgba(224,123,0,0.08);  border:1px solid rgba(224,123,0,0.25);  border-radius:var(--radius-sm); padding:10px 14px; color:#b86200; font-size:0.85rem; margin:6px 0; }

/* Status dots */
.dot       { display:inline-block; width:7px; height:7px; border-radius:50%; margin-right:6px; }
.dot-green { background:#0a7c4e; box-shadow:0 0 5px #0a7c4e; }
.dot-red   { background:#c0392b; box-shadow:0 0 5px #c0392b; }
.dot-amber { background:#e07b00; box-shadow:0 0 5px #e07b00; }

/* Stat Cards */
.stat-row  { display:flex; gap:8px; flex-wrap:wrap; margin-bottom:12px; }
.stat-card { flex:1; min-width:70px; background:var(--card-bg); border:1px solid var(--border); border-radius:var(--radius-sm); padding:12px 10px; text-align:center; box-shadow:var(--shadow); }
.stat-num  { font-family:'JetBrains Mono',monospace; font-size:1.3rem; color:var(--blue); font-weight:700; }
.stat-lbl  { font-size:0.6rem; color:var(--text-3); text-transform:uppercase; letter-spacing:0.4px; margin-top:3px; }

/* Doc cards */
.doc-card       { background:var(--card-bg); border:1px solid var(--border); border-radius:var(--radius-sm); padding:12px 14px; margin-bottom:8px; transition:border-color 0.2s; box-shadow:var(--shadow); }
.doc-card:hover { border-color:var(--blue); }
.doc-card-name  { font-size:0.85rem; color:var(--text); font-weight:500; }
.doc-card-meta  { font-size:0.7rem; color:var(--text-3); margin-top:3px; }
.cat-badge      { display:inline-block; padding:2px 8px; border-radius:4px; font-size:0.62rem; font-weight:600; font-family:'Inter',sans-serif; margin-left:6px; background:var(--blue-dim); color:var(--blue); border:1px solid var(--blue-b); }
.ocr-badge      { display:inline-block; background:rgba(224,123,0,0.10); color:#b86200; border:1px solid rgba(224,123,0,0.20); border-radius:4px; padding:1px 7px; font-size:0.6rem; font-family:'JetBrains Mono',monospace; margin-left:6px; }

/* Inputs */
.stTextInput > div > div > input,
.stTextArea  > div > div > textarea,
.stNumberInput > div > div > input,
.stSelectbox > div > div > div {
    background: var(--input-bg) !important; border:1px solid var(--border-2) !important;
    color:var(--text) !important; border-radius:var(--radius-sm) !important;
    font-family:'Inter',sans-serif !important; font-size:0.92rem !important; min-height:44px !important;
}
.stTextInput > div > div > input:focus { border-color:var(--blue) !important; box-shadow:0 0 0 2px var(--blue-dim) !important; }

/* Buttons — SRM Blue primary */
.stButton > button {
    background: linear-gradient(135deg, #1a4fa0, #2563c0) !important;
    color: #ffffff !important; font-weight: 600 !important; border: none !important;
    border-radius: var(--radius-sm) !important; font-family: 'Inter', sans-serif !important;
    min-height: 44px !important; font-size: 0.88rem !important; transition: all 0.2s !important;
}
.stButton > button:hover {
    background: linear-gradient(135deg, #2563c0, #3478d4) !important;
    box-shadow: 0 4px 16px rgba(26,79,160,0.30) !important; transform: translateY(-1px) !important;
}

/* Divider */
.divider { border:none; border-top:1px solid var(--border); margin:12px 0; }

/* Tabs */
.stTabs [data-baseweb="tab-list"] { gap:4px !important; border-bottom:2px solid var(--border) !important; background: transparent !important; }
.stTabs [data-baseweb="tab"] { padding:10px 18px !important; font-size:0.88rem !important; font-weight:500 !important; border-radius:8px 8px 0 0 !important; color:var(--text-2) !important; background:transparent !important; min-height:44px !important; }
.stTabs [aria-selected="true"] { color:var(--blue) !important; border-bottom:2px solid var(--blue) !important; font-weight:600 !important; }

/* File Uploader */
[data-testid="stFileUploader"] { border:2px dashed var(--border-2) !important; border-radius:var(--radius) !important; background:transparent !important; }

/* Mobile Bottom Nav */
.bottom-nav {
    position:fixed; bottom:0; left:0; right:0; background:var(--blue);
    border-top:1px solid rgba(255,255,255,0.15); display:flex; justify-content:space-around;
    align-items:center; padding:6px 0 max(env(safe-area-inset-bottom),6px);
    z-index:9999; box-shadow:0 -4px 20px rgba(26,79,160,0.25);
}
.bottom-nav-btn {
    flex:1; display:flex; flex-direction:column; align-items:center;
    gap:2px; padding:5px 2px; font-size:0.55rem; color:rgba(255,255,255,0.65);
    cursor:pointer; border:none; background:none; font-family:'Inter',sans-serif;
    text-transform:uppercase; letter-spacing:0.5px; transition:color 0.15s;
    -webkit-tap-highlight-color:transparent;
}
.bottom-nav-btn .nav-icon { font-size:1.2rem; }
.bottom-nav-btn.active    { color:#ffffff; }
@media (min-width:768px) { .bottom-nav { display:none !important; } .block-container { padding-bottom:2rem !important; } }

/* Mic Banner */
.mic-banner { background:rgba(192,57,43,0.06); border:1px dashed rgba(192,57,43,0.30); border-radius:var(--radius-sm); padding:8px 14px; margin-bottom:6px; font-family:'JetBrains Mono',monospace; font-size:0.78rem; color:#a93226; }

/* Notification Badge */
.notif-badge { display:inline-flex; align-items:center; justify-content:center; background:var(--red); color:white; border-radius:10px; font-size:0.6rem; font-weight:700; padding:1px 6px; min-width:18px; margin-left:4px; }

/* User card — in sidebar */
.user-card { background: rgba(255,255,255,0.12); border:1px solid rgba(255,255,255,0.22); border-radius:var(--radius-sm); padding:12px 14px; margin-bottom:14px; }
.user-card-label { font-size:0.62rem; font-family:'Inter',sans-serif; color:rgba(255,255,255,0.65); text-transform:uppercase; letter-spacing:1px; margin-bottom:4px; }
.user-card-name  { font-size:0.95rem; font-weight:600; color:#ffffff; }

/* Onboarding Tour */
.tour-card {
    background: var(--card-bg); border: 2px solid var(--blue);
    border-radius: var(--radius); padding: 32px 28px;
    box-shadow: 0 8px 40px rgba(26,79,160,0.15);
    text-align: center; max-width: 520px; margin: 40px auto;
}
.tour-step  { font-family:'Inter',sans-serif; font-size:0.7rem; color:var(--blue); text-transform:uppercase; letter-spacing:1px; margin-bottom:8px; font-weight:600; }
.tour-title { font-size:1.4rem; font-weight:700; color:var(--text); margin-bottom:8px; }
.tour-desc  { font-size:0.9rem; color:var(--text-2); line-height:1.6; }

/* Dashboard */
.dash-card  { background:var(--card-bg); border:1px solid var(--border); border-radius:var(--radius); padding:16px 20px; margin-bottom:14px; box-shadow:var(--shadow); }
.dash-title { font-size:0.8rem; font-weight:600; color:var(--text-2); text-transform:uppercase; letter-spacing:0.5px; margin-bottom:12px; font-family:'Inter',sans-serif; }

/* Session timeout warning */
.timeout-bar { background:rgba(224,123,0,0.08); border:1px solid rgba(224,123,0,0.25); border-radius:var(--radius-sm); padding:8px 14px; font-size:0.82rem; color:#b86200; margin-bottom:10px; display:flex; align-items:center; gap:8px; }

/* ── SRM STUDENT PORTAL LOGIN PAGE ── */

/* Full-page container */
.srm-portal-page {
    min-height: 80vh;
    background: #f0f4fa;
    padding: 0;
}

/* SRM Logo Header */
.srm-logo-header {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 16px;
    padding: 24px 20px 20px;
    background: #ffffff;
    border-bottom: 2px solid #1a4fa0;
    margin-bottom: 0;
}
.srm-emblem {
    flex-shrink: 0;
}
.srm-logo-text-block {
    text-align: left;
}
.srm-logo-name {
    font-size: 2.8rem;
    font-weight: 900;
    color: #1a3a7a;
    line-height: 1;
    letter-spacing: 2px;
    font-family: 'Inter', sans-serif;
}
.srm-logo-sub {
    font-size: 0.78rem;
    font-weight: 600;
    color: #1a3a7a;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    margin-top: 2px;
}
.srm-logo-tagline {
    font-size: 0.68rem;
    color: #666;
    margin-top: 1px;
    font-style: italic;
}

/* Two-column outer */
.srm-login-outer {
    display: flex;
    gap: 0;
    max-width: 1000px;
    margin: 0 auto;
    padding: 32px 20px 48px;
    min-height: 60vh;
}

/* Left welcome panel */
.srm-welcome-panel {
    padding: 20px 32px 20px 0;
}
.srm-dear {
    font-size: 1.25rem;
    font-weight: 700;
    color: #1a2640;
    margin-bottom: 10px;
}
.srm-welcome-line {
    font-size: 0.95rem;
    color: #1a2640;
    margin-bottom: 14px;
}
.srm-info {
    font-size: 0.88rem;
    color: #4a5170;
    line-height: 1.7;
    margin-bottom: 12px;
}

/* Login Card */
.srm-card {
    background: #ffffff;
    border-radius: 6px;
    box-shadow: 0 2px 24px rgba(26,79,160,0.14);
    overflow: hidden;
    flex-shrink: 0;
}
.srm-card-header {
    background: #2a6db5;
    color: #ffffff;
    font-size: 1rem;
    font-weight: 600;
    padding: 14px 24px;
    letter-spacing: 0.3px;
    text-align: center;
}

/* Field labels inside login card */
.srm-field-label {
    font-size: 0.83rem;
    color: #3d5275;
    font-weight: 500;
    margin-bottom: 4px;
    margin-top: 10px;
}

/* Captcha display box — mimics SRM's distorted captcha image */
.srm-captcha-display {
    background: #f8f8f8;
    border: 1px solid #c8d0e7;
    border-radius: 6px;
    height: 44px;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    position: relative;
}
.srm-captcha-text {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.1rem;
    font-weight: 800;
    color: #2a6db5;
    letter-spacing: 4px;
    /* Give it the "distorted captcha" look */
    background: linear-gradient(135deg, #1a4fa0 0%, #6a3fa0 50%, #2563c0 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    filter: drop-shadow(1px 1px 0 rgba(0,0,0,0.15));
    transform: skew(-5deg);
    display: inline-block;
    padding: 0 8px;
    text-shadow: none;
    user-select: none;
}

/* SRM alert error */
.srm-alert-error {
    background: rgba(192,57,43,0.08);
    border: 1px solid rgba(192,57,43,0.30);
    border-left: 4px solid #c0392b;
    border-radius: 6px;
    padding: 10px 14px;
    color: #a93226;
    font-size: 0.88rem;
    margin-bottom: 10px;
    font-weight: 500;
}

/* Captcha box (legacy, kept for other uses) */
.captcha-box {
    background: var(--blue-dim);
    border: 1px solid var(--blue-b);
    border-radius: var(--radius-sm);
    padding: 10px 16px;
    margin-bottom: 8px;
    font-size: 1rem;
    font-weight: 600;
    color: var(--blue);
    font-family: 'JetBrains Mono', monospace;
    text-align: center;
    letter-spacing: 2px;
}
</style>
""", unsafe_allow_html=True)