import streamlit as st
import streamlit.components.v1 as components
import psycopg2
import psycopg2.extras
from psycopg2 import OperationalError, DatabaseError
from PyPDF2 import PdfReader
import numpy as np
from typing import List, Optional, Tuple
import requests
import hashlib
import pickle
import time
import json
import io
from datetime import datetime
import base64

# ── Sentence Transformers (semantic search) ──
try:
    from sentence_transformers import SentenceTransformer
    SEMANTIC_AVAILABLE = True
except ImportError:
    SEMANTIC_AVAILABLE = False

# ── OCR fallback for scanned PDFs ──
try:
    import pytesseract
    from pdf2image import convert_from_bytes
    from PIL import Image
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="College AI Assistant",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap');

/* ════════════════════════════════════════════════
   DESIGN TOKENS
   ════════════════════════════════════════════════ */
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

/* ════════════════════════════════════════════════
   GLOBAL BASE
   ════════════════════════════════════════════════ */
html, body, [class*="css"] {
    font-family: 'IBM Plex Sans', sans-serif !important;
    background-color: var(--bg-primary) !important;
    color: var(--text-primary) !important;
    -webkit-text-size-adjust: 100%;
    box-sizing: border-box;
}
.stApp { background-color: var(--bg-primary) !important; }
#MainMenu, footer, header { visibility: hidden; }

/* ════════════════════════════════════════════════
   LAYOUT — fluid from 320px phone to 2560px desktop
   ════════════════════════════════════════════════
   Mobile  (<768px):  full width, bottom nav, no sidebar
   Tablet  (768-1024): sidebar collapses, content expands
   Desktop (>1024px): sidebar open, wide content area
   ════════════════════════════════════════════════ */

/* Main content area */
.block-container {
    padding: 1rem 0.8rem 5.5rem 0.8rem !important;  /* bottom pad for mobile nav */
    max-width: 100% !important;
    width: 100% !important;
}

/* Tablet */
@media (min-width: 768px) {
    .block-container {
        padding: 1.5rem 2rem 2.5rem 2rem !important;
    }
}

/* Desktop — generous padding, content breathes */
@media (min-width: 1024px) {
    .block-container {
        padding: 2rem 3rem 2rem 3rem !important;
        max-width: 1100px !important;
    }
}

/* Wide desktop */
@media (min-width: 1440px) {
    .block-container {
        max-width: 1300px !important;
        padding: 2rem 4rem 2rem 4rem !important;
    }
}

/* ════════════════════════════════════════════════
   SIDEBAR — auto on desktop, hidden on mobile
   ════════════════════════════════════════════════ */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0d1525 0%, #111827 100%) !important;
    border-right: 1px solid var(--border) !important;
    min-width: 260px !important;
}
[data-testid="stSidebar"] * {
    font-size: 0.88rem !important;
}

/* On mobile, sidebar is accessible via the hamburger — keep it working */
@media (max-width: 767px) {
    [data-testid="stSidebar"] {
        /* Streamlit handles sidebar overlay on mobile natively */
        min-width: 280px !important;
    }
}

/* ════════════════════════════════════════════════
   APP HEADER
   ════════════════════════════════════════════════ */
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
.app-header h1 {
    font-family: 'IBM Plex Mono', monospace;
    color: var(--accent-teal);
    font-size: 1.1rem;
    margin: 0;
    white-space: nowrap;
}
.app-header p {
    color: var(--text-secondary);
    font-size: 0.75rem;
    margin: 3px 0 0;
    font-family: 'IBM Plex Mono', monospace;
}

/* Tablet and up — bigger header */
@media (min-width: 768px) {
    .app-header { padding: 18px 24px; }
    .app-header h1 { font-size: 1.35rem; }
    .app-header p  { font-size: 0.82rem; }
}

/* Desktop */
@media (min-width: 1024px) {
    .app-header h1 { font-size: 1.55rem; }
    .app-header p  { font-size: 0.85rem; }
}

/* ════════════════════════════════════════════════
   ROLE BADGES
   ════════════════════════════════════════════════ */
.role-badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.7rem;
    font-weight: 600;
    font-family: 'IBM Plex Mono', monospace;
    letter-spacing: 0.5px;
    text-transform: uppercase;
}
.role-admin   { background:rgba(245,158,11,0.15); color:#f59e0b; border:1px solid rgba(245,158,11,0.3); }
.role-staff   { background:rgba(59,130,246,0.15);  color:#60a5fa; border:1px solid rgba(59,130,246,0.3); }
.role-student { background:rgba(0,212,170,0.12);   color:#00d4aa; border:1px solid rgba(0,212,170,0.25); }

/* ════════════════════════════════════════════════
   CHAT BUBBLES
   ════════════════════════════════════════════════ */
.chat-user {
    background: linear-gradient(135deg, #1e3a5f 0%, #1a2235 100%);
    border: 1px solid #2d4a6e;
    border-radius: 14px 14px 4px 14px;
    padding: 11px 14px;
    margin: 6px 0 6px 16px;      /* small indent on mobile */
    color: var(--text-primary);
    font-size: 0.9rem;
    line-height: 1.65;
    word-break: break-word;
}
.chat-assistant {
    background: linear-gradient(135deg, #162232 0%, #1a2235 100%);
    border: 1px solid #1e4030;
    border-left: 3px solid var(--accent-teal);
    border-radius: 4px 14px 14px 14px;
    padding: 11px 14px;
    margin: 6px 16px 6px 0;      /* small indent on mobile */
    color: var(--text-primary);
    font-size: 0.9rem;
    line-height: 1.75;
    word-break: break-word;
}

/* Tablet — more breathing room */
@media (min-width: 768px) {
    .chat-user      { margin-left: 48px;  font-size: 0.93rem; padding: 12px 18px; }
    .chat-assistant { margin-right: 48px; font-size: 0.93rem; padding: 12px 18px; }
}

/* Desktop — generous side margins */
@media (min-width: 1024px) {
    .chat-user      { margin-left: 80px;  font-size: 0.95rem; }
    .chat-assistant { margin-right: 80px; font-size: 0.95rem; }
}

.chat-label {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.63rem;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 4px;
}
.msg-time {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.6rem;
    color: var(--text-secondary);
    margin-top: 4px;
    opacity: 0.7;
}

/* ════════════════════════════════════════════════
   CONFIDENCE METER
   ════════════════════════════════════════════════ */
.confidence-bar-wrap { margin-top:10px; padding-top:10px; border-top:1px solid var(--border); }
.confidence-label { font-family:'IBM Plex Mono',monospace; font-size:0.63rem; color:var(--text-secondary); text-transform:uppercase; letter-spacing:0.8px; margin-bottom:4px; }
.confidence-bar-bg { background:rgba(255,255,255,0.07); border-radius:4px; height:6px; width:100%; }
.confidence-bar-fill { height:6px; border-radius:4px; transition:width 0.4s ease; }
.conf-high   { background: linear-gradient(90deg,#10b981,#00d4aa); }
.conf-medium { background: linear-gradient(90deg,#f59e0b,#fbbf24); }
.conf-low    { background: linear-gradient(90deg,#ef4444,#f87171); }
.confidence-pct { font-family:'IBM Plex Mono',monospace; font-size:0.72rem; margin-top:3px; }

/* ════════════════════════════════════════════════
   SOURCE EXCERPTS
   ════════════════════════════════════════════════ */
.source-chips { margin-top:8px; }
.source-label { font-family:'IBM Plex Mono',monospace; font-size:0.63rem; color:var(--text-secondary); text-transform:uppercase; letter-spacing:0.8px; }
.source-text  { font-size:0.78rem; color:var(--text-secondary); background:rgba(0,0,0,0.3); border-radius:6px; padding:8px 12px; margin-top:4px; border-left:2px solid var(--accent-teal); font-style:italic; }

.ocr-badge { display:inline-block; background:rgba(245,158,11,0.15); color:#f59e0b; border:1px solid rgba(245,158,11,0.3); border-radius:4px; padding:2px 8px; font-size:0.63rem; font-family:'IBM Plex Mono',monospace; margin-left:8px; }

/* ════════════════════════════════════════════════
   STAT CARDS
   ════════════════════════════════════════════════ */
.stat-row  { display:flex; gap:8px; margin-bottom:14px; flex-wrap:wrap; }
.stat-card { flex:1; min-width:60px; background:var(--bg-card); border:1px solid var(--border); border-radius:8px; padding:10px 8px; text-align:center; }
.stat-num  { font-family:'IBM Plex Mono',monospace; font-size:1.2rem; color:var(--accent-teal); font-weight:600; }
.stat-lbl  { font-size:0.63rem; color:var(--text-secondary); text-transform:uppercase; letter-spacing:0.4px; }

/* ════════════════════════════════════════════════
   DOC CARDS
   ════════════════════════════════════════════════ */
.doc-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 12px 14px;
    margin-bottom: 8px;
    transition: border-color 0.2s;
}
.doc-card:hover { border-color: var(--accent-teal); }
.doc-card-name { font-size:0.85rem; color:#e2e8f0; font-weight:500; word-break:break-all; }
.doc-card-meta { font-size:0.7rem; color:#475569; margin-top:3px; }

/* ════════════════════════════════════════════════
   LOGIN CARD — centred on all screen sizes
   ════════════════════════════════════════════════ */
.login-card {
    background: var(--bg-card);
    border: 1px solid #1e3a5f;
    border-radius: 16px;
    padding: 28px 20px;
    box-shadow: 0 20px 60px rgba(0,0,0,0.5);
    margin-bottom: 12px;
    max-width: 460px;
    margin-left: auto;
    margin-right: auto;
}
.login-title { font-family:'IBM Plex Mono',monospace; color:var(--accent-teal); font-size:1.3rem; margin-bottom:4px; }
.login-sub   { color:var(--text-secondary); font-size:0.78rem; font-family:'IBM Plex Mono',monospace; }

@media (min-width: 480px) {
    .login-card  { padding:36px 36px; }
    .login-title { font-size:1.5rem; }
}

/* ════════════════════════════════════════════════
   STATUS DOTS & ALERTS
   ════════════════════════════════════════════════ */
.status-dot  { display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:6px; }
.dot-green   { background:var(--success); box-shadow:0 0 6px var(--success); }
.dot-red     { background:var(--danger);  box-shadow:0 0 6px var(--danger); }
.dot-yellow  { background:var(--accent-orange); box-shadow:0 0 6px var(--accent-orange); }
.section-divider { border:none; border-top:1px solid var(--border); margin:14px 0; }
.alert-error   { background:rgba(239,68,68,0.1);  border:1px solid rgba(239,68,68,0.3);  border-radius:8px; padding:10px 14px; color:#fca5a5; font-size:0.85rem; margin:8px 0; }
.alert-success { background:rgba(16,185,129,0.1); border:1px solid rgba(16,185,129,0.3); border-radius:8px; padding:10px 14px; color:#6ee7b7; font-size:0.85rem; margin:8px 0; }
.alert-info    { background:rgba(59,130,246,0.1); border:1px solid rgba(59,130,246,0.3); border-radius:8px; padding:10px 14px; color:#93c5fd; font-size:0.85rem; margin:8px 0; }

/* ════════════════════════════════════════════════
   INPUTS & BUTTONS — 48px min height (WCAG tap target)
   ════════════════════════════════════════════════ */
.stTextInput > div > div > input,
.stTextArea  > div > div > textarea {
    background: var(--bg-secondary) !important;
    border: 1px solid var(--border) !important;
    color: var(--text-primary) !important;
    border-radius: 10px !important;
    font-family: 'IBM Plex Sans', sans-serif !important;
    font-size: 0.95rem !important;
    padding: 11px 14px !important;
    min-height: 48px !important;
}
.stButton > button {
    background: linear-gradient(135deg, #00d4aa, #00b894) !important;
    color: #0a0e1a !important;
    font-weight: 600 !important;
    border: none !important;
    border-radius: 10px !important;
    font-family: 'IBM Plex Sans', sans-serif !important;
    min-height: 48px !important;
    font-size: 0.92rem !important;
    transition: box-shadow 0.2s !important;
}
.stButton > button:hover {
    background: linear-gradient(135deg, #00e5b8, #00c9a7) !important;
    box-shadow: 0 4px 15px rgba(0,212,170,0.35) !important;
}
/* Checkbox — bigger tap target */
.stCheckbox label { font-size:0.9rem !important; padding: 4px 0 !important; }
.stCheckbox input { width:20px !important; height:20px !important; }

/* ════════════════════════════════════════════════
   TABS — touch-friendly
   ════════════════════════════════════════════════ */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px !important;
    flex-wrap: wrap !important;   /* tabs wrap on narrow screens */
}
.stTabs [data-baseweb="tab"] {
    padding: 10px 14px !important;
    font-size: 0.88rem !important;
    border-radius: 8px 8px 0 0 !important;
    white-space: nowrap !important;
}
@media (min-width: 768px) {
    .stTabs [data-baseweb="tab"] { padding: 11px 20px !important; font-size: 0.92rem !important; }
}

/* ════════════════════════════════════════════════
   FILE UPLOADER — mobile friendly
   ════════════════════════════════════════════════ */
[data-testid="stFileUploader"] {
    border: 2px dashed var(--border) !important;
    border-radius: 10px !important;
    padding: 12px !important;
    background: rgba(0,0,0,0.15) !important;
}

/* ════════════════════════════════════════════════
   BOTTOM NAV — mobile only (hidden on tablet/desktop)
   ════════════════════════════════════════════════ */
.bottom-nav {
    position: fixed;
    bottom: 0; left: 0; right: 0;
    background: #0a0e1a;
    border-top: 1px solid #1e293b;
    display: flex;
    justify-content: space-around;
    align-items: center;
    padding: 6px 0 env(safe-area-inset-bottom, 8px);
    z-index: 9999;
    box-shadow: 0 -4px 20px rgba(0,0,0,0.4);
}
.bottom-nav-btn {
    flex: 1;
    text-align: center;
    padding: 5px 2px;
    font-size: 0.58rem;
    color: #64748b;
    cursor: pointer;
    font-family: 'IBM Plex Mono', monospace;
    text-transform: uppercase;
    letter-spacing: 0.4px;
    border: none;
    background: none;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
    -webkit-tap-highlight-color: transparent;
    transition: color 0.15s;
}
.bottom-nav-btn .nav-icon { font-size: 1.25rem; }
.bottom-nav-btn.active    { color: #00d4aa; }
.bottom-nav-btn:active    { color: #00e5b8; transform: scale(0.95); }

/* Hide bottom nav on tablet and desktop — they use sidebar + tabs */
@media (min-width: 768px) {
    .bottom-nav { display: none !important; }
    /* Also remove the bottom padding reserved for mobile nav */
    .block-container { padding-bottom: 2rem !important; }
}

/* ════════════════════════════════════════════════
   SUGGESTIONS — 2 cols on mobile, 4 on desktop
   ════════════════════════════════════════════════ */
.suggestion-wrap {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    margin: 10px 0;
}
@media (min-width: 640px)  { .suggestion-wrap { grid-template-columns: 1fr 1fr 1fr; } }
@media (min-width: 1024px) { .suggestion-wrap { grid-template-columns: 1fr 1fr 1fr 1fr; } }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# DEFAULT SEED USERS (only inserted once on first DB init)
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
# SEMANTIC MODEL (cached so it loads once)
# ─────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def load_semantic_model():
    """Load sentence-transformers model once and cache it."""
    if not SEMANTIC_AVAILABLE:
        return None
    try:
        # all-MiniLM-L6-v2: fast, small (~80MB), great for English academic text
        model = SentenceTransformer('all-MiniLM-L6-v2')
        return model
    except Exception as e:
        st.warning(f"Semantic model failed to load: {e}. Falling back to keyword search.")
        return None

# ─────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────
def get_db_connection(pg_url: str):
    try:
        conn = psycopg2.connect(pg_url, connect_timeout=10)
        return conn
    except OperationalError as e:
        st.error(f"❌ Database connection failed: {e}")
        return None


def init_db(pg_url: str) -> bool:
    conn = get_db_connection(pg_url)
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            # ── Users table (DB-backed auth, replaces hardcoded dict) ──
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('admin','staff','student')),
                    display_name TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """)
            # Seed default users only if table is empty
            cur.execute("SELECT COUNT(*) FROM users")
            if cur.fetchone()[0] == 0:
                for uname, phash, role, display in SEED_USERS:
                    cur.execute("""
                        INSERT INTO users (username, password_hash, role, display_name)
                        VALUES (%s, %s, %s, %s) ON CONFLICT (username) DO NOTHING
                    """, (uname, phash, role, display))

            cur.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id SERIAL PRIMARY KEY,
                    filename TEXT NOT NULL,
                    uploaded_by TEXT NOT NULL,
                    uploaded_at TIMESTAMP DEFAULT NOW(),
                    chunk_count INTEGER,
                    chunks_blob BYTEA,
                    embeddings_blob BYTEA,
                    used_ocr BOOLEAN DEFAULT FALSE
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id SERIAL PRIMARY KEY,
                    username TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    sources TEXT,
                    confidence FLOAT,
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS query_log (
                    id SERIAL PRIMARY KEY,
                    username TEXT,
                    query TEXT,
                    response_time_ms INTEGER,
                    confidence FLOAT,
                    success BOOLEAN,
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """)
        conn.commit()
        return True
    except DatabaseError as e:
        st.error(f"❌ DB init error: {e}")
        return False
    finally:
        conn.close()


def db_authenticate(pg_url: str, username: str, password: str) -> Optional[dict]:
    """Authenticate against the users table in PostgreSQL."""
    conn = get_db_connection(pg_url)
    if not conn:
        return None
    try:
        phash = hashlib.sha256(password.encode()).hexdigest()
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT username, role, display_name FROM users WHERE username=%s AND password_hash=%s",
                (username.strip().lower(), phash)
            )
            row = cur.fetchone()
        if row:
            return {"username": row["username"], "role": row["role"], "display": row["display_name"]}
        return None
    except DatabaseError:
        return None
    finally:
        conn.close()


def get_all_users(pg_url: str) -> list:
    conn = get_db_connection(pg_url)
    if not conn:
        return []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT id, username, role, display_name, created_at FROM users ORDER BY created_at")
            return cur.fetchall()
    except DatabaseError:
        return []
    finally:
        conn.close()


def add_user(pg_url: str, username: str, password: str, role: str, display_name: str) -> Tuple[bool, str]:
    if not username or not password or not display_name:
        return False, "All fields are required."
    if role not in ("admin", "staff", "student"):
        return False, "Invalid role."
    if len(password) < 6:
        return False, "Password must be at least 6 characters."
    conn = get_db_connection(pg_url)
    if not conn:
        return False, "Database connection failed."
    try:
        phash = hashlib.sha256(password.encode()).hexdigest()
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (username, password_hash, role, display_name) VALUES (%s,%s,%s,%s)",
                (username.strip().lower(), phash, role, display_name.strip())
            )
        conn.commit()
        return True, "User created successfully."
    except psycopg2.errors.UniqueViolation:
        return False, f"Username '{username}' already exists."
    except DatabaseError as e:
        return False, str(e)
    finally:
        conn.close()


def delete_user(pg_url: str, user_id: int, current_username: str) -> Tuple[bool, str]:
    conn = get_db_connection(pg_url)
    if not conn:
        return False, "Database connection failed."
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT username FROM users WHERE id=%s", (user_id,))
            row = cur.fetchone()
            if not row:
                return False, "User not found."
            if row[0] == current_username:
                return False, "You cannot delete your own account."
            cur.execute("DELETE FROM users WHERE id=%s", (user_id,))
        conn.commit()
        return True, "User deleted."
    except DatabaseError as e:
        return False, str(e)
    finally:
        conn.close()


def change_password(pg_url: str, username: str, old_password: str, new_password: str) -> Tuple[bool, str]:
    if len(new_password) < 6:
        return False, "New password must be at least 6 characters."
    conn = get_db_connection(pg_url)
    if not conn:
        return False, "Database connection failed."
    try:
        old_hash = hashlib.sha256(old_password.encode()).hexdigest()
        new_hash = hashlib.sha256(new_password.encode()).hexdigest()
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE username=%s AND password_hash=%s", (username, old_hash))
            if not cur.fetchone():
                return False, "Current password is incorrect."
            cur.execute("UPDATE users SET password_hash=%s WHERE username=%s", (new_hash, username))
        conn.commit()
        return True, "Password changed successfully."
    except DatabaseError as e:
        return False, str(e)
    finally:
        conn.close()


def save_document_to_db(pg_url: str, filename: str, username: str,
                        chunks: List[str], embeddings: np.ndarray,
                        used_ocr: bool = False) -> bool:
    """Store chunks + precomputed embeddings in PostgreSQL."""
    conn = get_db_connection(pg_url)
    if not conn:
        return False
    try:
        chunks_blob     = pickle.dumps(chunks)
        embeddings_blob = pickle.dumps(embeddings)
        with conn.cursor() as cur:
            cur.execute("DELETE FROM documents WHERE filename = %s", (filename,))
            cur.execute("""
                INSERT INTO documents (filename, uploaded_by, chunk_count, chunks_blob, embeddings_blob, used_ocr)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (filename, username, len(chunks),
                  psycopg2.Binary(chunks_blob),
                  psycopg2.Binary(embeddings_blob),
                  used_ocr))
        conn.commit()
        return True
    except DatabaseError as e:
        st.error(f"❌ Failed to save document: {e}")
        return False
    finally:
        conn.close()


def load_all_documents_from_db(pg_url: str):
    """
    Load all precomputed embeddings from DB and merge them.
    Returns: (all_embeddings, all_chunks, doc_list)
    No re-processing of PDFs needed on restart.
    """
    conn = get_db_connection(pg_url)
    if not conn:
        return None, None, []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT filename, chunk_count, chunks_blob, embeddings_blob, used_ocr FROM documents ORDER BY uploaded_at")
            rows = cur.fetchall()

        if not rows:
            return None, None, []

        all_chunks     = []
        all_embeddings = []
        doc_list       = []

        for row in rows:
            chunks     = pickle.loads(bytes(row['chunks_blob']))
            embeddings = pickle.loads(bytes(row['embeddings_blob']))
            all_chunks.extend(chunks)
            all_embeddings.append(embeddings)
            doc_list.append({
                "filename":   row['filename'],
                "chunks":     row['chunk_count'],
                "used_ocr":   row['used_ocr']
            })

        merged_embeddings = np.vstack(all_embeddings)
        return merged_embeddings, all_chunks, doc_list

    except Exception as e:
        st.error(f"❌ Failed to load documents: {e}")
        return None, None, []
    finally:
        conn.close()


def get_document_list(pg_url: str):
    conn = get_db_connection(pg_url)
    if not conn:
        return []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT id, filename, uploaded_by, uploaded_at, chunk_count, used_ocr FROM documents ORDER BY uploaded_at DESC")
            return cur.fetchall()
    except DatabaseError:
        return []
    finally:
        conn.close()


def delete_document(pg_url: str, doc_id: int) -> bool:
    conn = get_db_connection(pg_url)
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM documents WHERE id = %s", (doc_id,))
        conn.commit()
        return True
    except DatabaseError as e:
        st.error(f"❌ Delete failed: {e}")
        return False
    finally:
        conn.close()


def save_chat_message(pg_url: str, username: str, role: str,
                      content: str, sources: Optional[str] = None,
                      confidence: Optional[float] = None):
    conn = get_db_connection(pg_url)
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO chat_history (username, role, content, sources, confidence)
                VALUES (%s, %s, %s, %s, %s)
            """, (username, role, content, sources, confidence))
        conn.commit()
    except DatabaseError:
        pass
    finally:
        conn.close()


def load_chat_history(pg_url: str, username: str, limit: int = 50):
    conn = get_db_connection(pg_url)
    if not conn:
        return []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                SELECT role, content, sources, confidence, created_at
                FROM chat_history WHERE username = %s
                ORDER BY created_at DESC LIMIT %s
            """, (username, limit))
            return list(reversed(cur.fetchall()))
    except DatabaseError:
        return []
    finally:
        conn.close()


def clear_chat_history(pg_url: str, username: str):
    conn = get_db_connection(pg_url)
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM chat_history WHERE username = %s", (username,))
        conn.commit()
    except DatabaseError:
        pass
    finally:
        conn.close()


def log_query(pg_url: str, username: str, query: str,
              response_time_ms: int, confidence: float, success: bool):
    conn = get_db_connection(pg_url)
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO query_log (username, query, response_time_ms, confidence, success)
                VALUES (%s, %s, %s, %s, %s)
            """, (username, query, response_time_ms, confidence, success))
        conn.commit()
    except DatabaseError:
        pass
    finally:
        conn.close()


def get_stats(pg_url: str) -> dict:
    conn = get_db_connection(pg_url)
    if not conn:
        return {}
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM documents"); docs = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM query_log"); queries = cur.fetchone()[0]
            cur.execute("SELECT SUM(chunk_count) FROM documents"); chunks = cur.fetchone()[0] or 0
            cur.execute("SELECT AVG(confidence) FROM query_log WHERE confidence IS NOT NULL"); avg_conf = cur.fetchone()[0] or 0
        return {"docs": docs, "queries": queries, "chunks": chunks, "avg_conf": round(float(avg_conf)*100, 1)}
    except DatabaseError:
        return {}
    finally:
        conn.close()

# ─────────────────────────────────────────────
# PDF EXTRACTION — with OCR fallback
# ─────────────────────────────────────────────
def extract_text_from_pdf(pdf_bytes: bytes, filename: str) -> Tuple[List[str], bool]:
    """
    Extract text chunks from PDF.
    First tries PyPDF2 (fast, for text-based PDFs).
    If little/no text found, falls back to OCR via pytesseract (for scanned PDFs).
    Returns: (chunks, used_ocr)
    """
    chunk_size = 100
    overlap    = 20
    used_ocr   = False

    # ── Attempt 1: PyPDF2 direct text extraction ──
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        raw_text = ""
        for page in reader.pages:
            t = page.extract_text()
            if t:
                raw_text += t + " "

        words = raw_text.split()

        # If we got meaningful text (>50 words), use it
        if len(words) > 50:
            chunks = []
            for i in range(0, len(words), chunk_size - overlap):
                chunk = ' '.join(words[i:i + chunk_size])
                if len(chunk.strip()) > 30:
                    chunks.append(chunk)
            return chunks, False

    except Exception:
        pass

    # ── Attempt 2: OCR via pytesseract ──
    if OCR_AVAILABLE:
        try:
            st.info(f"🔍 '{filename}' appears to be a scanned PDF — running OCR (this takes ~30s per page)...")
            images   = convert_from_bytes(pdf_bytes, dpi=200)
            raw_text = ""
            for img in images:
                raw_text += pytesseract.image_to_string(img, lang='eng') + " "

            words = raw_text.split()
            if len(words) > 20:
                chunks = []
                for i in range(0, len(words), chunk_size - overlap):
                    chunk = ' '.join(words[i:i + chunk_size])
                    if len(chunk.strip()) > 30:
                        chunks.append(chunk)
                return chunks, True
        except Exception as e:
            st.warning(f"OCR failed for '{filename}': {e}")

    else:
        st.warning(f"⚠️ '{filename}' appears to be a scanned PDF and OCR libraries (pytesseract, pdf2image) are not installed. Install them to support scanned PDFs.")

    return [], used_ocr

# ─────────────────────────────────────────────
# SEMANTIC RETRIEVAL
# ─────────────────────────────────────────────
def semantic_search(query: str, model, all_embeddings: np.ndarray,
                    chunks: List[str], n_results: int = 5) -> Tuple[List[str], List[float]]:
    """
    Encode the query and find top-N chunks by cosine similarity.
    Returns (matched_chunks, similarity_scores_0_to_1).
    """
    query_embedding = model.encode([query], normalize_embeddings=True)
    # all_embeddings should already be normalized
    scores = (query_embedding @ all_embeddings.T).flatten()
    top_indices = np.argsort(scores)[-n_results:][::-1]

    results = []
    result_scores = []
    for idx in top_indices:
        if scores[idx] > 0.15:  # minimum relevance threshold
            results.append(chunks[idx])
            result_scores.append(float(scores[idx]))

    return results, result_scores


def compute_confidence(scores: List[float]) -> float:
    """
    Derive an overall confidence score (0–1) from top chunk similarities.
    - Uses top score weighted with average of top-3 to reduce fluke matches.
    """
    if not scores:
        return 0.0
    top = scores[0]
    avg_top3 = np.mean(scores[:3]) if len(scores) >= 3 else np.mean(scores)
    confidence = 0.6 * top + 0.4 * avg_top3
    return round(min(float(confidence), 1.0), 3)


def confidence_html(confidence: float) -> str:
    """Render a coloured confidence bar + percentage."""
    pct = int(confidence * 100)
    if pct >= 65:
        bar_class = "conf-high"
        label = "High confidence"
        color = "#00d4aa"
    elif pct >= 35:
        bar_class = "conf-medium"
        label = "Medium confidence"
        color = "#f59e0b"
    else:
        bar_class = "conf-low"
        label = "Low confidence — answer may be incomplete"
        color = "#ef4444"

    return f"""
    <div class="confidence-bar-wrap">
        <div class="confidence-label">Answer Confidence</div>
        <div class="confidence-bar-bg">
            <div class="confidence-bar-fill {bar_class}" style="width:{pct}%"></div>
        </div>
        <div class="confidence-pct" style="color:{color}">{pct}% — {label}</div>
    </div>
    """

# ─────────────────────────────────────────────
# LLM — Groq with full error handling + retry
# ─────────────────────────────────────────────
def generate_answer(query: str, context: List[str], api_key: str) -> Tuple[str, bool]:
    context_text = "\n\n---\n\n".join(context)
    prompt = f"""You are a formal, accurate College AI Assistant for SRM Institute of Science and Technology's Department of Computer Science.

STRICT RULES — YOU MUST FOLLOW THESE EXACTLY:
1. Answer ONLY using information explicitly stated in the DOCUMENT CONTEXT below.
2. If the answer is not clearly present in the context, respond with EXACTLY this sentence and nothing else:
   "This information is not available in the current documents. Please contact the department office directly."
3. Do NOT guess, infer, suggest alternatives, or recommend external websites.
4. Do NOT add bullet points, extra advice, or filler sentences when the answer is not found.
5. When the answer IS found, be concise, factual, and use bullet points only when listing multiple items.
6. Never mix found and not-found information in the same response.

DOCUMENT CONTEXT:
{context_text}

STUDENT QUESTION: {query}

ANSWER:"""

    for attempt in range(3):
        try:
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": "llama-3.3-70b-versatile",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 600
                },
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                if data.get('choices') and data['choices'][0].get('message'):
                    return data['choices'][0]['message']['content'], True
                return "⚠️ Empty response from AI model. Please try again.", False

            elif response.status_code == 401:
                return "❌ Invalid Groq API key. Please check your credentials.", False
            elif response.status_code == 429:
                if attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                return "⚠️ Rate limit reached. Please wait a moment and try again.", False
            elif response.status_code >= 500:
                if attempt < 2:
                    time.sleep(1)
                    continue
                return f"⚠️ Groq server error ({response.status_code}). Try again shortly.", False
            else:
                return f"⚠️ API error: HTTP {response.status_code}", False

        except requests.exceptions.Timeout:
            if attempt < 2:
                time.sleep(1)
                continue
            return "⚠️ Request timed out. Check your connection.", False
        except requests.exceptions.ConnectionError:
            return "⚠️ Cannot reach Groq API. Check your internet connection.", False
        except Exception as e:
            return f"⚠️ Unexpected error: {e}", False

    return "⚠️ All retry attempts failed. Please try again later.", False

# ─────────────────────────────────────────────
# AUTH & RBAC
# ─────────────────────────────────────────────
def authenticate(pg_url: str, username: str, password: str) -> Optional[dict]:
    """DB-backed authentication. Falls back gracefully if DB is unavailable."""
    return db_authenticate(pg_url, username, password)

def check_permission(role: str, action: str) -> bool:
    permissions = {
        "admin":   ["upload", "delete", "query", "view_stats"],
        "staff":   ["upload", "delete", "query"],
        "student": ["query"]
    }
    return action in permissions.get(role, [])

# ─────────────────────────────────────────────
# LOGIN
# ─────────────────────────────────────────────
def _init_captcha():
    """Generate a fresh math CAPTCHA and store in session."""
    import random
    a = random.randint(2, 9)
    b = random.randint(1, 9)
    st.session_state.captcha_a   = a
    st.session_state.captcha_b   = b
    st.session_state.captcha_ans = a + b


# ─────────────────────────────────────────────
# SESSION TOKEN — keeps user logged in on refresh
# ─────────────────────────────────────────────
def _make_token(username: str, role: str, display: str) -> str:
    payload = f"{username}|{role}|{display}|{int(time.time())}"
    return base64.urlsafe_b64encode(payload.encode()).decode()

def _decode_token(token: str, pg_url: str) -> Optional[dict]:
    try:
        payload = base64.urlsafe_b64decode(token.encode()).decode()
        parts   = payload.split("|")
        if len(parts) < 4:
            return None
        username, role, display, ts = parts[0], parts[1], parts[2], parts[3]
        # Expires after 7 days
        if time.time() - float(ts) > 7 * 24 * 3600:
            return None
        # Re-verify user still exists in DB
        conn = get_db_connection(pg_url)
        if not conn:
            return None
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute(
                    "SELECT username, role, display_name FROM users WHERE username=%s",
                    (username,)
                )
                row = cur.fetchone()
            if row:
                return {"username": row["username"], "role": row["role"], "display": row["display_name"]}
        finally:
            conn.close()
    except Exception:
        pass
    return None

def render_login(pg_url: str):
    if 'captcha_ans' not in st.session_state:
        _init_captcha()

    # ── Inject floating-label + show/hide password CSS ──
    st.markdown("""
    <style>
    /* ── FLOATING LABEL INPUTS ── */
    .fl-group {
        position: relative;
        margin-bottom: 24px;
    }
    .fl-group input {
        width: 100%;
        background: #0d1525 !important;
        border: 1.5px solid #1e3a5f !important;
        border-radius: 10px !important;
        padding: 18px 44px 6px 14px !important;
        font-size: 1rem !important;
        color: #e2e8f0 !important;
        outline: none !important;
        transition: border-color 0.25s, box-shadow 0.25s !important;
        min-height: 56px !important;
        box-sizing: border-box;
        font-family: 'IBM Plex Sans', sans-serif !important;
    }
    .fl-group input:focus {
        border-color: #00d4aa !important;
        box-shadow: 0 0 0 3px rgba(0,212,170,0.12) !important;
    }
    .fl-group label {
        position: absolute;
        left: 14px;
        top: 50%;
        transform: translateY(-50%);
        font-size: 0.95rem;
        color: #64748b;
        pointer-events: none;
        transition: all 0.2s ease;
        font-family: 'IBM Plex Sans', sans-serif;
        background: transparent;
    }
    .fl-group input:focus + label,
    .fl-group input:not(:placeholder-shown) + label {
        top: 10px;
        transform: none;
        font-size: 0.68rem;
        color: #00d4aa;
        letter-spacing: 0.5px;
        text-transform: uppercase;
    }
    /* eye toggle */
    .pw-wrap { position: relative; }
    .pw-toggle {
        position: absolute;
        right: 14px;
        top: 50%;
        transform: translateY(-50%);
        background: none;
        border: none;
        cursor: pointer;
        color: #475569;
        font-size: 1.1rem;
        padding: 4px;
        line-height: 1;
        transition: color 0.2s;
    }
    .pw-toggle:hover { color: #00d4aa; }

    /* ── CAPTCHA BOX ── */
    .captcha-box {
        background: rgba(0,212,170,0.06);
        border: 1px solid rgba(0,212,170,0.2);
        border-radius: 10px;
        padding: 12px 14px;
        margin-bottom: 18px;
        display: flex;
        align-items: center;
        gap: 12px;
        flex-wrap: wrap;
    }
    .captcha-question {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 1rem;
        color: #00d4aa;
        white-space: nowrap;
    }
    .captcha-input {
        width: 80px !important;
        background: #0d1525 !important;
        border: 1.5px solid #1e3a5f !important;
        border-radius: 8px !important;
        padding: 8px 12px !important;
        font-size: 1rem !important;
        color: #e2e8f0 !important;
        font-family: 'IBM Plex Mono', monospace !important;
        outline: none !important;
        min-height: unset !important;
        transition: border-color 0.2s !important;
    }
    .captcha-input:focus { border-color: #00d4aa !important; }

    /* ── SIGN IN BUTTON ── */
    .signin-btn {
        width: 100%;
        padding: 14px;
        background: linear-gradient(135deg, #00d4aa, #00b894);
        color: #0a0e1a;
        font-weight: 700;
        font-size: 1rem;
        border: none;
        border-radius: 10px;
        cursor: pointer;
        font-family: 'IBM Plex Sans', sans-serif;
        letter-spacing: 0.3px;
        transition: all 0.2s;
        margin-top: 4px;
    }
    .signin-btn:hover {
        background: linear-gradient(135deg, #00e5b8, #00c9a7);
        box-shadow: 0 6px 20px rgba(0,212,170,0.35);
        transform: translateY(-1px);
    }
    .signin-btn:active { transform: translateY(0); }

    /* ── REMEMBER + FORGOT ROW ── */
    .form-footer {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin: 14px 0 20px;
        flex-wrap: wrap;
        gap: 8px;
    }
    .remember-label {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 0.85rem;
        color: #94a3b8;
        cursor: pointer;
        font-family: 'IBM Plex Sans', sans-serif;
    }
    .remember-label input[type=checkbox] {
        width: 16px; height: 16px;
        accent-color: #00d4aa;
        cursor: pointer;
    }
    .forgot-link {
        font-size: 0.82rem;
        color: #00d4aa;
        text-decoration: none;
        font-family: 'IBM Plex Sans', sans-serif;
        cursor: pointer;
        background: none;
        border: none;
        padding: 0;
        transition: opacity 0.2s;
    }
    .forgot-link:hover { opacity: 0.75; text-decoration: underline; }

    /* ── LOGIN CARD ── */
    .login-page-wrap {
        min-height: 100vh;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 20px 16px 40px;
    }
    .login-card-v2 {
        width: 100%;
        max-width: 440px;
        background: #111827;
        border: 1px solid #1e3a5f;
        border-radius: 20px;
        padding: 40px 32px 36px;
        box-shadow: 0 24px 64px rgba(0,0,0,0.6);
    }
    @media (max-width: 480px) {
        .login-card-v2 { padding: 28px 18px 28px; border-radius: 16px; }
    }
    .login-logo {
        text-align: center;
        margin-bottom: 28px;
    }
    .login-logo .logo-icon {
        font-size: 2.8rem;
        display: block;
        margin-bottom: 8px;
    }
    .login-logo h2 {
        font-family: 'IBM Plex Mono', monospace;
        color: #00d4aa;
        font-size: 1.4rem;
        margin: 0 0 4px;
    }
    .login-logo p {
        font-family: 'IBM Plex Mono', monospace;
        color: #475569;
        font-size: 0.75rem;
        margin: 0;
    }
    </style>
    """, unsafe_allow_html=True)

    # ── Render the card via HTML form (floating labels need HTML not st.text_input) ──
    a = st.session_state.get('captcha_a', '?')
    b = st.session_state.get('captcha_b', '?')

    remembered = ""
    if st.session_state.get('remembered_user') and st.session_state.get('remember_expires', 0) > datetime.now().timestamp():
        remembered = f'''<div class="alert-info" style="margin-bottom:18px;">
            👋 Welcome back, <b>{st.session_state.remembered_user}</b> — enter your password to continue.
        </div>'''

    # Custom HTML login form
    st.markdown(f"""
    <div class="login-page-wrap">
      <div class="login-card-v2">

        <div class="login-logo">
          <span class="logo-icon">🎓</span>
          <h2>College AI Assistant</h2>
          <p>// SRM Institute — CS Department</p>
        </div>

        {remembered}

        <div id="login-error-msg"></div>

        <div class="fl-group">
          <input type="text" id="fl-username" placeholder=" " autocomplete="username" />
          <label for="fl-username">Username</label>
        </div>

        <div class="fl-group pw-wrap">
          <input type="password" id="fl-password" placeholder=" " autocomplete="current-password" />
          <label for="fl-password">Password</label>
          <button class="pw-toggle" type="button" id="pw-eye" onclick="togglePw()" title="Show/hide password">👁</button>
        </div>

        <div class="captcha-box">
          <span class="captcha-question">🤖 What is <b>{a} + {b}</b> ?</span>
          <input type="number" class="captcha-input" id="fl-captcha" placeholder="Answer" min="0" max="99" />
        </div>

        <div class="form-footer">
          <label class="remember-label">
            <input type="checkbox" id="fl-remember" />
            Remember me for 7 days
          </label>
          <button class="forgot-link" onclick="showForgot()">Forgot password?</button>
        </div>

        <button class="signin-btn" onclick="doLogin()">Sign In →</button>

        <div id="forgot-msg" style="display:none;margin-top:16px;" class="alert-info">
          Contact your admin to reset your password.
        </div>

      </div>
    </div>

    <script>
    function togglePw() {{
        const pw  = document.getElementById('fl-password');
        const eye = document.getElementById('pw-eye');
        if (pw.type === 'password') {{
            pw.type = 'text';
            eye.textContent = '🙈';
        }} else {{
            pw.type = 'password';
            eye.textContent = '👁';
        }}
    }}

    function showForgot() {{
        const m = document.getElementById('forgot-msg');
        m.style.display = m.style.display === 'none' ? 'block' : 'none';
    }}

    // Push values into hidden Streamlit inputs then trigger submit
    function doLogin() {{
        const username = document.getElementById('fl-username').value.trim();
        const password = document.getElementById('fl-password').value;
        const captcha  = document.getElementById('fl-captcha').value.trim();
        const remember = document.getElementById('fl-remember').checked;

        if (!username || !password) {{
            showError('⚠️ Please enter both username and password.');
            return;
        }}
        if (!captcha) {{
            showError('⚠️ Please answer the CAPTCHA.');
            return;
        }}

        // Store in sessionStorage so Streamlit can read them
        sessionStorage.setItem('login_username', username);
        sessionStorage.setItem('login_password', password);
        sessionStorage.setItem('login_captcha',  captcha);
        sessionStorage.setItem('login_remember', remember ? '1' : '0');

        // Click the hidden Streamlit submit button
        const btn = window.parent.document.querySelector('button[data-testid="baseButton-secondary"]');
        const allBtns = window.parent.document.querySelectorAll('button');
        for (const b of allBtns) {{
            if (b.innerText.includes('_submit_login_')) {{
                b.click();
                return;
            }}
        }}
    }}

    function showError(msg) {{
        const el = document.getElementById('login-error-msg');
        if (el) {{
            el.innerHTML = '<div class="alert-error">' + msg + '</div>';
            setTimeout(() => {{ el.innerHTML = ''; }}, 4000);
        }}
    }}
    </script>
    """, unsafe_allow_html=True)

    # ── Hidden Streamlit form that actually processes the login ──
    # Uses st.components to read sessionStorage values
    username_val = st.text_input("_u", key="hid_user", label_visibility="collapsed")
    password_val = st.text_input("_p", key="hid_pass", label_visibility="collapsed", type="password")
    captcha_val  = st.text_input("_c", key="hid_cap",  label_visibility="collapsed")
    remember_val = st.checkbox("_r", key="hid_rem",   label_visibility="collapsed")

    # JS that syncs sessionStorage → Streamlit hidden inputs on page load
    components.html("""
    <script>
    (function() {
        function setStreamlitInput(selector, value) {
            const inputs = window.parent.document.querySelectorAll(selector);
            for (const inp of inputs) {
                const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                setter.call(inp, value);
                inp.dispatchEvent(new Event('input', { bubbles: true }));
            }
        }
        const u = sessionStorage.getItem('login_username') || '';
        const p = sessionStorage.getItem('login_password') || '';
        const c = sessionStorage.getItem('login_captcha')  || '';
        if (u) setStreamlitInput('input[aria-label="_u"]', u);
        if (p) setStreamlitInput('input[aria-label="_p"]', p);
        if (c) setStreamlitInput('input[aria-label="_c"]', c);
    })();
    </script>
    """, height=0)

    with st.form("_login_form_", clear_on_submit=False):
        fu = st.text_input("Username", key="form_user")
        fp = st.text_input("Password", key="form_pass", type="password")
        fc = st.text_input("Captcha", key="form_cap")
        fr = st.checkbox("Remember me", key="form_rem")
        submitted = st.form_submit_button("_submit_login_", use_container_width=False)

    if submitted and fu:
        try:
            cap_int = int(fc.strip()) if fc else -1
        except ValueError:
            cap_int = -1

        if cap_int != st.session_state.captcha_ans:
            st.markdown('<div class="alert-error">🤖 Wrong CAPTCHA. Please try again.</div>', unsafe_allow_html=True)
            _init_captcha()
        elif not fu or not fp:
            st.markdown('<div class="alert-error">⚠️ Enter both username and password.</div>', unsafe_allow_html=True)
        else:
            with st.spinner("Signing in..."):
                user = authenticate(pg_url, fu, fp)
            if user:
                st.session_state.user          = user
                st.session_state.authenticated = True
                st.query_params["sid"] = _make_token(user["username"], user["role"], user["display"])
                if fr:
                    st.session_state.remembered_user    = fu
                    st.session_state.remember_expires   = datetime.now().timestamp() + 7 * 24 * 3600
                st.rerun()
            else:
                st.markdown('<div class="alert-error">❌ Invalid username or password.</div>', unsafe_allow_html=True)
                _init_captcha()

    with st.expander("Demo credentials"):
        st.markdown(DEMO_CREDENTIALS_NOTE)

def render_sidebar(pg_url: str, api_key: str, model):
    user = st.session_state.user
    role = user['role']

    with st.sidebar:
        # User info
        st.markdown(f"""
        <div style="padding:12px;background:rgba(0,0,0,0.3);border-radius:8px;margin-bottom:16px;">
            <div style="font-family:'IBM Plex Mono',monospace;font-size:0.8rem;color:#94a3b8;margin-bottom:4px;">SIGNED IN AS</div>
            <div style="font-weight:600;color:#e2e8f0;">{user['display']}</div>
            <div style="margin-top:6px;"><span class="role-badge role-{role}">{role}</span></div>
        </div>
        """, unsafe_allow_html=True)

        # Status indicators
        conn_test = get_db_connection(pg_url)
        db_ok = conn_test is not None
        if db_ok: conn_test.close()
        st.markdown(
            f'<div style="font-size:0.75rem;color:{"#6ee7b7" if db_ok else "#fca5a5"};">'
            f'<span class="status-dot {"dot-green" if db_ok else "dot-red"}"></span>'
            f'Database {"Connected" if db_ok else "Offline"}</div>',
            unsafe_allow_html=True
        )
        semantic_ok = model is not None
        st.markdown(
            f'<div style="font-size:0.75rem;color:{"#6ee7b7" if semantic_ok else "#fbbf24"};">'
            f'<span class="status-dot {"dot-green" if semantic_ok else "dot-yellow"}"></span>'
            f'{"Semantic Search Active" if semantic_ok else "Keyword Search (fallback)"}</div>',
            unsafe_allow_html=True
        )

        st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)

        # Upload — Admin / Staff only
        if check_permission(role, "upload"):
            st.markdown("**📄 Upload Documents**")
            uploaded_files = st.file_uploader("PDF files", type=['pdf'],
                                               accept_multiple_files=True,
                                               label_visibility="collapsed")
            if uploaded_files and st.button("⚙️ Process & Save", use_container_width=True):
                if not model:
                    st.markdown('<div class="alert-error">❌ Semantic model not loaded. Cannot process documents.</div>',
                                unsafe_allow_html=True)
                else:
                    any_saved = False
                    for pdf_file in uploaded_files:
                        with st.spinner(f"Processing {pdf_file.name}..."):
                            pdf_bytes = pdf_file.read()
                            chunks, used_ocr = extract_text_from_pdf(pdf_bytes, pdf_file.name)
                            if chunks:
                                embeddings = model.encode(chunks, normalize_embeddings=True,
                                                          show_progress_bar=False)
                                if save_document_to_db(pg_url, pdf_file.name,
                                                       user['username'], chunks,
                                                       embeddings, used_ocr):
                                    ocr_note = " (OCR)" if used_ocr else ""
                                    st.markdown(f'<div class="alert-success">✅ {pdf_file.name}{ocr_note} — {len(chunks)} chunks saved</div>',
                                                unsafe_allow_html=True)
                                    any_saved = True
                            else:
                                # Clear error with actionable advice
                                ocr_msg = ""
                                if not OCR_AVAILABLE:
                                    ocr_msg = " Install <code>pytesseract</code> and <code>pdf2image</code> for scanned PDF support."
                                st.markdown(
                                    f'<div class="alert-error">❌ <strong>{pdf_file.name}</strong>: No text could be extracted. ' +
                                    f'The file may be a scanned/image-based PDF or corrupted.{ocr_msg}</div>',
                                    unsafe_allow_html=True
                                )
                    if any_saved:
                        st.session_state.docs_loaded = False
                        st.rerun()

            st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)

        # Document list — collapsible
        docs = get_document_list(pg_url)
        doc_count = len(docs) if docs else 0
        with st.expander(f"📚 Loaded Documents ({doc_count})", expanded=False):
            if docs:
                for doc in docs:
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        ocr_badge = '<span class="ocr-badge">OCR</span>' if doc['used_ocr'] else ''
                        st.markdown(
                            f"<div style='font-size:0.78rem;color:#94a3b8;'>📄 {doc['filename'][:22]}{'...' if len(doc['filename'])>22 else ''}{ocr_badge}"
                            f"<br><span style='font-size:0.65rem;color:#475569;'>{doc['chunk_count']} chunks</span></div>",
                            unsafe_allow_html=True
                        )
                    with c2:
                        if check_permission(role, "delete"):
                            if st.button("🗑", key=f"del_{doc['id']}"):
                                if delete_document(pg_url, doc['id']):
                                    st.session_state.docs_loaded = False
                                    st.rerun()
            else:
                st.markdown('<div class="alert-info">No documents uploaded yet.</div>', unsafe_allow_html=True)

        # Admin stats
        if check_permission(role, "view_stats"):
            st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)
            st.markdown("**📊 System Stats**")
            stats = get_stats(pg_url)
            if stats:
                st.markdown(f"""
                <div class="stat-row">
                    <div class="stat-card"><div class="stat-num">{stats.get('docs',0)}</div><div class="stat-lbl">Docs</div></div>
                    <div class="stat-card"><div class="stat-num">{stats.get('chunks',0)}</div><div class="stat-lbl">Chunks</div></div>
                    <div class="stat-card"><div class="stat-num">{stats.get('queries',0)}</div><div class="stat-lbl">Queries</div></div>
                </div>
                <div style="font-size:0.75rem;color:#94a3b8;font-family:'IBM Plex Mono',monospace;">
                    Avg confidence: {stats.get('avg_conf',0)}%
                </div>
                """, unsafe_allow_html=True)

        st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)

        # ── Load History button ──
        if st.button("📜 Load My History", use_container_width=True):
            rows = load_chat_history(pg_url, user['username'], limit=40)
            st.session_state.messages = [
                {"role": r['role'], "content": r['content'],
                 "sources": r['sources'], "confidence": r['confidence'],
                 "time": str(r['created_at'])}
                for r in rows
            ]
            st.session_state.history_loaded = True
            st.rerun()

        c1, c2 = st.columns(2)
        with c1:
            if st.button("🗑 Clear Chat", use_container_width=True):
                clear_chat_history(pg_url, user['username'])
                st.session_state.messages = []
                st.session_state.history_loaded = False
                st.rerun()
        with c2:
            if st.button("🚪 Logout", use_container_width=True):
                st.query_params.clear()   # clears session token from URL
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()

# ─────────────────────────────────────────────
# CHAT
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

    # Load embeddings from DB (fast — no PDF reprocessing)
    if not st.session_state.get('docs_loaded'):
        with st.spinner("Loading knowledge base from database..."):
            embeddings, chunks, doc_list = load_all_documents_from_db(pg_url)
            st.session_state.embeddings = embeddings
            st.session_state.chunks     = chunks
            st.session_state.doc_list   = doc_list
            st.session_state.docs_loaded = True

    # ── Fresh session on every login — history saved in DB but not auto-loaded ──
    # This ensures a clean slate on every login while preserving full history in DB.
    if 'messages' not in st.session_state:
        st.session_state.messages = []
        st.session_state.history_loaded = False   # tracks if user manually loaded history

    # ── Display chat history ──
    if not st.session_state.messages:
        history_hint = "" if st.session_state.get("history_loaded") else '<div style="font-size:0.75rem;color:#334155;margin-top:8px;font-family:IBM Plex Mono,monospace;">📜 Previous conversations are saved — click <b style="color:#475569;">Load My History</b> in the sidebar to restore them.</div>'
        st.markdown(f"""
        <div style="text-align:center;padding:40px 20px;color:#475569;">
            <div style="font-size:2.5rem;">🎓</div>
            <div style="font-family:'IBM Plex Mono',monospace;font-size:0.85rem;margin-top:12px;color:#64748b;">
                New session started — ask anything about your college documents
            </div>
            {history_hint}
        </div>
        """, unsafe_allow_html=True)

    # ── Session context banner ──
    if st.session_state.messages:
        if st.session_state.get("history_loaded"):
            st.markdown('<div style="background:rgba(59,130,246,0.08);border:1px solid rgba(59,130,246,0.2);border-radius:8px;padding:8px 14px;font-size:0.75rem;color:#60a5fa;font-family:IBM Plex Mono,monospace;margin-bottom:8px;">📜 Showing restored history — new messages will be added below</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div style="background:rgba(0,212,170,0.06);border:1px solid rgba(0,212,170,0.15);border-radius:8px;padding:8px 14px;font-size:0.75rem;color:#00d4aa;font-family:IBM Plex Mono,monospace;margin-bottom:8px;">🟢 Current session</div>', unsafe_allow_html=True)

    for msg in st.session_state.messages:
        if msg['role'] == 'user':
            st.markdown(f"""
            <div class="chat-label">YOU</div>
            <div class="chat-user">{msg['content']}</div>
            <div class="msg-time">{msg.get('time','')}</div>
            """, unsafe_allow_html=True)
        else:
            # Build confidence bar
            conf_html = ""
            if msg.get('confidence') is not None:
                conf_html = confidence_html(float(msg['confidence']))

            # Build source excerpts
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
                {conf_html}
                {src_html}
            </div>
            <div class="msg-time">{msg.get('time','')}</div>
            """, unsafe_allow_html=True)

    # ── Suggestions ──
    if not st.session_state.messages:
        st.markdown("**💡 Try asking:**")
        cols = st.columns(4)
        for i, sug in enumerate(SUGGESTIONS[:8]):
            with cols[i % 4]:
                if st.button(sug, key=f"sug_{i}", use_container_width=True):
                    # Store in session and let normal flow pick it up (no rerun loop)
                    st.session_state.pending_query = sug

    if not check_permission(role, "query"):
        st.markdown('<div class="alert-error">🔒 Your account does not have query access.</div>', unsafe_allow_html=True)
        return

    # ── Upfront validation banners (shown before input so user knows what to fix) ──
    if not api_key:
        st.markdown('<div class="alert-error">⚠️ <strong>Groq API key missing.</strong> Enter it in the sidebar under ⚙️ before querying.</div>', unsafe_allow_html=True)
    if st.session_state.get('embeddings') is None:
        st.markdown('<div class="alert-info">ℹ️ <strong>No documents loaded.</strong> An Admin or Staff member must upload PDFs first.</div>', unsafe_allow_html=True)
    if model is None:
        st.markdown('<div class="alert-error">❌ <strong>Semantic model not available.</strong> Install sentence-transformers.</div>', unsafe_allow_html=True)

    # ── Input row: mic button (col) + chat input ──
    pending = st.session_state.pop('pending_query', None)

    col_mic, col_input = st.columns([1, 11])
    with col_mic:
        if st.session_state.get('mic_active'):
            mic_label = "🔴"
        else:
            mic_label = "🎤"
        if st.button(mic_label, key="mic_toggle", help="Click to speak your question (Chrome only)", use_container_width=True):
            st.session_state.mic_active = not st.session_state.get('mic_active', False)
            st.rerun()

    # ── Live voice transcript preview (shown above chat input when mic is on) ──
    if st.session_state.get('mic_active'):
        st.markdown("""
        <div id="chat-voice-preview" style="
            background:rgba(239,68,68,0.08); border:1px dashed rgba(239,68,68,0.4);
            border-radius:8px; padding:8px 14px; margin-bottom:6px;
            font-family:'IBM Plex Mono',monospace; font-size:0.82rem; color:#fca5a5;">
            🔴 <span id="chat-voice-text">Listening — start speaking...</span>
        </div>
        """, unsafe_allow_html=True)

    with col_input:
        prompt = st.chat_input("Ask about your college documents...") or pending

    # ── TTS + STT controls row ──
    tts_on = st.session_state.get('tts_enabled', True)
    c1, c2, c3 = st.columns([2, 2, 4])
    with c1:
        if st.button(f"{'🔊 Read Aloud: ON' if tts_on else '🔇 Read Aloud: OFF'}", key="tts_toggle", use_container_width=True):
            st.session_state.tts_enabled = not tts_on
            st.rerun()
    with c2:
        if st.session_state.get('mic_active'):
            st.markdown('<div style="color:#ef4444;font-size:0.78rem;font-family:IBM Plex Mono,monospace;padding:8px 0;">🔴 Listening — speak now</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div style="color:#475569;font-size:0.72rem;font-family:IBM Plex Mono,monospace;padding:8px 0;">🎤 Click mic to speak</div>', unsafe_allow_html=True)

    # ── Inject JS for mic STT and TTS ──
    tts_enabled_js = "true" if tts_on else "false"
    mic_active_js  = "true" if st.session_state.get('mic_active') else "false"
    components.html(f"""
    <script>
    (function() {{
        const ttsEnabled = {tts_enabled_js};
        const micActive  = {mic_active_js};
        const synth      = window.parent.speechSynthesis;

        // ── TTS: speak last assistant message ──
        function speakLastMessage() {{
            if (!ttsEnabled || !synth) return;
            synth.cancel();
            const msgs = window.parent.document.querySelectorAll('.chat-assistant');
            if (!msgs.length) return;
            const last = msgs[msgs.length - 1];
            const clone = last.cloneNode(true);
            clone.querySelectorAll('.confidence-bar-wrap, .source-chips').forEach(el => el.remove());
            let text = clone.textContent.replace(/[ \t\n\r]+/g, ' ').trim();
            if (text.length > 800) text = text.substring(0, 800) + '...';
            const utt  = new SpeechSynthesisUtterance(text);
            utt.lang   = 'en-IN';
            utt.rate   = 0.92;
            utt.pitch  = 1.0;
            const voices = synth.getVoices();
            const voice  = voices.find(v => v.lang === 'en-IN') || voices.find(v => v.lang.startsWith('en-')) || voices[0];
            if (voice) utt.voice = voice;
            synth.speak(utt);
        }}

        // ── Watch for new messages and auto-speak ──
        const observer = new MutationObserver(() => {{
            const msgs = window.parent.document.querySelectorAll('.chat-assistant');
            if (!msgs.length) return;
            const last = msgs[msgs.length - 1];
            if (last && last.dataset.spoken !== 'true') {{
                last.dataset.spoken = 'true';
                speakLastMessage();
            }}
        }});
        observer.observe(window.parent.document.body, {{ childList: true, subtree: true }});

        // ── STT: start recognition if mic is active ──
        if (micActive) {{
            const SR = window.parent.SpeechRecognition || window.parent.webkitSpeechRecognition;
            if (!SR) {{ console.warn('SpeechRecognition not supported'); return; }}
            const recognition = new SR();
            recognition.lang  = 'en-IN';
            recognition.interimResults = true;   // ← KEY FIX: shows words as you speak
            recognition.continuous     = true;   // keeps listening until mic toggled off
            recognition.maxAlternatives = 1;

            const chatVoiceText = window.parent.document.getElementById('chat-voice-text');

            recognition.onresult = (event) => {{
                let interim = '';
                let final   = '';
                for (let i = event.resultIndex; i < event.results.length; i++) {{
                    const t = event.results[i][0].transcript;
                    if (event.results[i].isFinal) {{ final += t; }}
                    else {{ interim += t; }}
                }}
                // Show live preview in the red banner
                const live = final || interim;
                if (chatVoiceText) chatVoiceText.textContent = live || 'Listening — start speaking...';

                // Push final result into chat textarea
                if (final) {{
                    const inputEl = window.parent.document.querySelector('textarea[data-testid="stChatInputTextArea"]');
                    if (inputEl) {{
                        const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
                        setter.call(inputEl, final.trim());
                        inputEl.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        inputEl.focus();
                    }}
                }}
            }};
            recognition.onerror = (e) => {{
                console.error('STT error:', e.error);
                if (chatVoiceText) chatVoiceText.textContent = '⚠️ Mic error: ' + e.error + ' — try again';
            }};
            recognition.start();
        }}
    }})();
    </script>
    """, height=0)

    if not prompt:
        return

    # Block query if prerequisites missing
    if not api_key:
        st.markdown('<div class="alert-error">⚠️ Cannot process query — Groq API key is not set.</div>', unsafe_allow_html=True)
        return

    if st.session_state.get('embeddings') is None:
        st.markdown('<div class="alert-info">ℹ️ Cannot process query — no documents in the knowledge base.</div>', unsafe_allow_html=True)
        return

    if model is None:
        st.markdown('<div class="alert-error">❌ Cannot process query — semantic model not loaded.</div>', unsafe_allow_html=True)
        return

    # Save & show user message
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    st.session_state.messages.append({"role": "user", "content": prompt, "sources": None, "confidence": None, "time": now})
    save_chat_message(pg_url, user['username'], "user", prompt)
    st.markdown(f'<div class="chat-label">YOU</div><div class="chat-user">{prompt}</div><div class="msg-time">{now}</div>',
                unsafe_allow_html=True)

    # Generate
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

        t_end        = time.time()
        response_ms  = int((t_end - t_start) * 1000)

    log_query(pg_url, user['username'], prompt, response_ms, confidence, success)

    sources_json = json.dumps(relevant_docs[:3]) if relevant_docs else None
    save_chat_message(pg_url, user['username'], "assistant", answer, sources_json, confidence)

    now2   = datetime.now().strftime("%Y-%m-%d %H:%M")
    ai_msg = {"role": "assistant", "content": answer, "sources": sources_json,
              "confidence": confidence, "time": now2}
    st.session_state.messages.append(ai_msg)

    conf_html = confidence_html(confidence)
    src_html  = ""
    if relevant_docs:
        excerpts = "".join([f'<div class="source-text">"{s[:130]}..."</div>' for s in relevant_docs[:2]])
        src_html = f'<div class="source-chips"><div class="source-label">📎 Source Excerpts ({response_ms}ms)</div>{excerpts}</div>'

    st.markdown(f"""
    <div class="chat-label">AI ASSISTANT</div>
    <div class="chat-assistant">
        {answer}
        {conf_html}
        {src_html}
    </div>
    <div class="msg-time">{now2}</div>
    """, unsafe_allow_html=True)

    st.rerun()

# ─────────────────────────────────────────────
# USER MANAGEMENT (Admin only)
# ─────────────────────────────────────────────
def render_user_management(pg_url: str, current_username: str):
    st.markdown("### 👥 User Management")

    # Add new user
    with st.expander("➕ Add New User", expanded=False):
        with st.form("add_user_form"):
            col1, col2 = st.columns(2)
            with col1:
                new_uname   = st.text_input("Username")
                new_display = st.text_input("Display Name")
            with col2:
                new_pass  = st.text_input("Password", type="password")
                new_role  = st.selectbox("Role", ["student", "staff", "admin"])
            if st.form_submit_button("Create User", use_container_width=True):
                ok, msg = add_user(pg_url, new_uname, new_pass, new_role, new_display)
                if ok:
                    st.markdown(f'<div class="alert-success">✅ {msg}</div>', unsafe_allow_html=True)
                    st.rerun()
                else:
                    st.markdown(f'<div class="alert-error">❌ {msg}</div>', unsafe_allow_html=True)

    # Existing users list
    st.markdown("**Existing Users**")
    users = get_all_users(pg_url)
    if users:
        for u in users:
            c1, c2, c3, c4 = st.columns([2, 1.5, 2, 1])
            with c1:
                st.markdown(f"<div style='font-size:0.82rem;color:#e2e8f0;'>👤 {u['username']}</div>", unsafe_allow_html=True)
            with c2:
                badge_class = f"role-{u['role']}"
                st.markdown(f'<span class="role-badge {badge_class}">{u["role"]}</span>', unsafe_allow_html=True)
            with c3:
                st.markdown(f"<div style='font-size:0.75rem;color:#94a3b8;'>{u['display_name']}</div>", unsafe_allow_html=True)
            with c4:
                if u['username'] != current_username:
                    if st.button("🗑", key=f"del_user_{u['id']}"):
                        ok, msg = delete_user(pg_url, u['id'], current_username)
                        if ok:
                            st.rerun()
                        else:
                            st.error(msg)
                else:
                    st.markdown("<div style='font-size:0.7rem;color:#475569;'>you</div>", unsafe_allow_html=True)
    else:
        st.markdown('<div class="alert-info">No users found.</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────
# CHANGE PASSWORD (all roles)
# ─────────────────────────────────────────────
def render_change_password(pg_url: str, username: str):
    with st.expander("🔑 Change My Password", expanded=False):
        with st.form("change_pw_form"):
            old_pw  = st.text_input("Current Password", type="password")
            new_pw  = st.text_input("New Password", type="password")
            new_pw2 = st.text_input("Confirm New Password", type="password")
            if st.form_submit_button("Update Password", use_container_width=True):
                if not old_pw or not new_pw or not new_pw2:
                    st.markdown('<div class="alert-error">⚠️ All fields are required.</div>', unsafe_allow_html=True)
                elif new_pw != new_pw2:
                    st.markdown('<div class="alert-error">⚠️ New passwords do not match.</div>', unsafe_allow_html=True)
                else:
                    ok, msg = change_password(pg_url, username, old_pw, new_pw)
                    if ok:
                        st.markdown(f'<div class="alert-success">✅ {msg}</div>', unsafe_allow_html=True)
                    else:
                        st.markdown(f'<div class="alert-error">❌ {msg}</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

# ─────────────────────────────────────────────
# DOCS PANEL — full page, easy to read on mobile
# ─────────────────────────────────────────────
def render_docs_panel(pg_url: str, role: str):
    st.markdown("### 📚 Uploaded Documents")
    docs = get_document_list(pg_url)
    if not docs:
        st.markdown('<div class="alert-info">ℹ️ No documents uploaded yet. Ask your Admin or Staff to upload college PDFs.</div>', unsafe_allow_html=True)
        return

    st.markdown(
        f'<div style="font-size:0.8rem;color:#64748b;margin-bottom:12px;">' +
        f'{len(docs)} document{"s" if len(docs)!=1 else ""} in the knowledge base</div>',
        unsafe_allow_html=True
    )

    for doc in docs:
        ocr_tag  = '<span class="ocr-badge">OCR</span>' if doc.get('used_ocr') else ""
        uploader = doc.get('uploaded_by', '-')
        at       = str(doc.get('uploaded_at', ''))[:16]
        chunks   = doc.get('chunk_count', '?')
        fname    = doc['filename']

        col_info, col_del = st.columns([5, 1])
        with col_info:
            st.markdown(f"""
            <div class="doc-card">
                <div class="doc-card-name">📄 {fname} {ocr_tag}</div>
                <div class="doc-card-meta">{chunks} chunks &nbsp;·&nbsp; uploaded by {uploader} &nbsp;·&nbsp; {at}</div>
            </div>
            """, unsafe_allow_html=True)
        with col_del:
            if check_permission(role, "delete"):
                st.markdown("<div style='padding-top:8px'>", unsafe_allow_html=True)
                if st.button("🗑️", key=f"docs_del_{doc['id']}", help="Delete"):
                    if delete_document(pg_url, doc['id']):
                        st.session_state.docs_loaded = False
                        st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)


def load_secrets() -> tuple:
    """
    Load PG_URL and GROQ_API_KEY from .streamlit/secrets.toml automatically.
    No manual input needed from any user.
    """
    try:
        pg_url  = st.secrets["PG_URL"]
        api_key = st.secrets["GROQ_API_KEY"]
        return pg_url, api_key
    except KeyError as e:
        st.error(f"❌ Missing secret: {e}. Make sure your .streamlit/secrets.toml has PG_URL and GROQ_API_KEY.")
        st.stop()
    except Exception as e:
        st.error(f"❌ Could not load secrets: {e}")
        st.stop()


def main():
    pg_url, api_key = load_secrets()

    # ── Init DB once per cold start ──
    if not st.session_state.get('db_initialised'):
        if init_db(pg_url):
            st.session_state.db_initialised = True
        else:
            st.error("❌ Could not connect to the database. Check your PG_URL in secrets.toml.")
            st.stop()

    # ── Restore session from URL token on refresh ──
    # When a user logs in, a token is saved in the URL (?sid=...).
    # On refresh the URL still has it, so we silently restore their session.
    if not st.session_state.get('authenticated'):
        token = st.query_params.get("sid", "")
        if token:
            restored = _decode_token(token, pg_url)
            if restored:
                st.session_state.user          = restored
                st.session_state.authenticated = True

    if not st.session_state.get('authenticated'):
        render_login(pg_url)
        return

    # ── Load semantic model (shows spinner — intentional, runs once) ──
    model = load_semantic_model()
    user  = st.session_state.user
    role  = user['role']

    # ── Sidebar ──
    render_sidebar(pg_url, api_key, model)

    # ── Compact header ──
    st.markdown(f"""
    <div class="app-header">
        <h1>🎓 College AI Assistant</h1>
        <p>// SRM CS Dept &nbsp;|&nbsp;
           <span class="role-badge role-{role}">{role}</span> &nbsp;{user['display']}
        </p>
    </div>
    """, unsafe_allow_html=True)

    # ── Bottom nav (mobile only — hidden on desktop via CSS) ──
    active_tab = st.query_params.get("tab", "chat")
    nav_items = [("💬","Chat","chat"), ("📚","Docs","docs"), ("🔑","Account","account")]
    if role == "admin":
        nav_items = [("💬","Chat","chat"), ("📚","Docs","docs"), ("👥","Users","users"), ("🔑","Account","account")]

    nav_html = '<div class="bottom-nav">'
    for icon, label, key in nav_items:
        active_cls = "active" if active_tab == key else ""
        nav_html += (
            f'<button class="bottom-nav-btn {active_cls}" ' +
            f'onclick="window.parent.location.href=window.parent.location.pathname+\'?tab={key}\'">' +
            f'<span class="nav-icon">{icon}</span>{label}</button>'
        )
    nav_html += '</div>'
    st.markdown(nav_html, unsafe_allow_html=True)

    # ── Main tabs (visible on desktop, hidden on mobile in favour of bottom nav) ──
    if role == "admin":
        tabs = st.tabs(["💬 Chat", "📚 Docs", "👥 Users", "🔑 Account"])
        tab_map = {"chat": 0, "docs": 1, "users": 2, "account": 3}
    else:
        tabs = st.tabs(["💬 Chat", "📚 Docs", "🔑 Account"])
        tab_map = {"chat": 0, "docs": 1, "account": 2}

    # Render each tab
    with tabs[tab_map.get("chat", 0)]:
        render_chat(pg_url, api_key, model)

    with tabs[tab_map.get("docs", 1)]:
        render_docs_panel(pg_url, role)

    if role == "admin":
        with tabs[tab_map.get("users", 2)]:
            render_user_management(pg_url, user['username'])
        with tabs[tab_map.get("account", 3)]:
            render_change_password(pg_url, user['username'])
    else:
        with tabs[tab_map.get("account", 2)]:
            render_change_password(pg_url, user['username'])


if __name__ == "__main__":
    main()