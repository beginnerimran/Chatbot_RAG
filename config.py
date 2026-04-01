"""
config.py — Page config, CSS (SRM blue/white theme), constants.
"""

import hashlib
import streamlit as st


# -------------------------------------------------------------------
# Demo users and constants
# -------------------------------------------------------------------

SEED_USERS = [
    ("admin", hashlib.sha256("admin123".encode()).hexdigest(), "admin", "Administrator"),
    ("staff1", hashlib.sha256("staff123".encode()).hexdigest(), "staff", "Dr. Priya Sharma"),
    ("student1", hashlib.sha256("student123".encode()).hexdigest(), "student", "Student User"),
    ("student2", hashlib.sha256("pass1234".encode()).hexdigest(), "student", "Student User 2"),
]

DEMO_CREDENTIALS_NOTE = """
| Username | Password | Role   |
|---------|----------|--------|
| admin   | admin123 | Admin  |
| staff1  | staff123 | Staff  |
| student1| student123| Student|
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


# -------------------------------------------------------------------
# Page setup
# -------------------------------------------------------------------

def setup_page() -> None:
    st.set_page_config(
        page_title="SRM College AI Assistant",
        page_icon="data:image/svg+xml,S",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_css()


# -------------------------------------------------------------------
# Global CSS (theme, visibility, sidebar toggle, tabs, notifications)
# -------------------------------------------------------------------

def inject_css() -> None:
    st.markdown(
        """
<style>
:root {
  --bg: #f0f4fa;
  --bg-2: #ffffff;
  --bg-3: #e8eef7;
  --border: #d0dbeF;
  --border-2: #b8c9e0;
  --text: #1a2640;
  --text-2: #3d5275;
  --text-3: #6b82a0;
  --card-bg: #ffffff;
  --input-bg: #f7f9fc;
  --blue: #1a4fa0;
  --blue-2: #2563c0;
  --blue-dim: rgba(26,79,160,0.08);
  --blue-b: rgba(26,79,160,0.20);
  --radius: 12px;
  --radius-sm: 8px;
  --shadow: 0 2px 16px rgba(26,79,160,0.10);
  --shadow-lg: 0 4px 32px rgba(26,79,160,0.14);
}

/* Base */
html, body, .stApp {
  font-family: "Inter", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
  background: var(--bg) !important;
  color: var(--text) !important;
}

/* Hide Streamlit chrome (menu/footer) but keep sidebar toggle */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
[data-testid="stToolbar"] { visibility: hidden; }

/* ------------------------------------------------------------------
   Sidebar collapse control — ALWAYS visible at top-left
-------------------------------------------------------------------*/
[data-testid="collapsedControl"] {
  visibility: visible !important;
  display: flex !important;
  opacity: 1 !important;
  position: fixed !important;
  top: 12px !important;
  left: 12px !important;
  z-index: 99999 !important;
  background: #1a4fa0 !important;
  border-radius: 999px !important;
  padding: 6px !important;
  box-shadow: 0 2px 8px rgba(0,0,0,0.25);
}
[data-testid="collapsedControl"] button {
  color: #ffffff !important;
}
[data-testid="stSidebarCollapseButton"] {
  visibility: visible !important;
  display: flex !important;
  opacity: 1 !important;
  z-index: 99999 !important;
}

/* Layout */
.block-container {
  padding: 1rem 1rem 6rem 1rem !important;
  max-width: 100% !important;
}
@media (min-width: 768px) {
  .block-container {
    padding: 1.5rem 2rem 3rem 2rem !important;
  }
}
@media (min-width: 1024px) {
  .block-container {
    padding: 2rem 3rem 3rem 3rem !important;
    max-width: 1200px !important;
  }
}

/* ------------------------------------------------------------------
   Sidebar (dark blue) — white text only inside sidebar
-------------------------------------------------------------------*/
[data-testid="stSidebar"] {
  background: var(--blue) !important;
  border-right: 1px solid rgba(255,255,255,0.15) !important;
}
[data-testid="stSidebar"] > div {
  padding: 1.2rem 1rem !important;
}
[data-testid="stSidebar"] * {
  color: rgba(255,255,255,0.95) !important;
}
[data-testid="stSidebar"] .stButton button {
  background: rgba(255,255,255,0.15) !important;
  border: 1px solid rgba(255,255,255,0.25) !important;
  color: #ffffff !important;
}
[data-testid="stSidebar"] .stButton button:hover {
  background: rgba(255,255,255,0.28) !important;
}

/* ------------------------------------------------------------------
   Main content: make sure expanders and containers use DARK text
-------------------------------------------------------------------*/
[data-testid="stExpander"] * {
  color: var(--text) !important;
}
[data-testid="stMarkdownContainer"] {
  color: var(--text) !important;
}

/* ------------------------------------------------------------------
   App header (top bar after login)
-------------------------------------------------------------------*/
.app-header {
  background: var(--blue);
  border-radius: var(--radius);
  padding: 14px 20px;
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
  box-shadow: var(--shadow-lg);
}
.app-header-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 1.1rem;
  font-weight: 700;
  color: #ffffff;
}
.app-header-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 0.8rem;
  color: rgba(255,255,255,0.8);
  flex-wrap: wrap;
}
.srm-logo-text {
  background: rgba(255,255,255,0.16);
  color: #ffffff;
  font-weight: 800;
  font-size: 1.1rem;
  padding: 4px 12px;
  border-radius: 6px;
  letter-spacing: 1px;
}

/* Role badges */
.role-badge {
  display: inline-flex;
  align-items: center;
  padding: 3px 10px;
  border-radius: 20px;
  font-size: 0.65rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.8px;
}
.role-admin {
  background: rgba(224,123,0,0.15);
  color: #b86200;
  border: 1px solid rgba(224,123,0,0.3);
}
.role-staff {
  background: rgba(26,79,160,0.12);
  color: #1a4fa0;
  border: 1px solid rgba(26,79,160,0.25);
}
.role-student {
  background: rgba(10,124,78,0.12);
  color: #0a7c4e;
  border: 1px solid rgba(10,124,78,0.25);
}
/* When shown INSIDE sidebar we invert them; login page keeps its own styles */
[data-testid="stSidebar"] .role-badge {
  background: rgba(255,255,255,0.18) !important;
  color: #ffffff !important;
  border-color: rgba(255,255,255,0.3) !important;
}

/* ------------------------------------------------------------------
   Generic cards, chat bubbles, etc.
-------------------------------------------------------------------*/
.stat-card, .doc-card {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 12px 14px;
  box-shadow: var(--shadow);
}

.chat-user {
  background: var(--blue-dim);
  border: 1px solid var(--blue-b);
  border-radius: 16px 16px 4px 16px;
  padding: 12px 16px;
  margin-left: 8%;
  font-size: 0.92rem;
  line-height: 1.65;
  color: var(--text);
}
.chat-assistant {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-left: 3px solid var(--blue);
  border-radius: 4px 16px 16px 16px;
  padding: 14px 16px;
  margin-right: 8%;
  font-size: 0.92rem;
  line-height: 1.75;
  color: var(--text);
}

/* ------------------------------------------------------------------
   Inputs and buttons (shared)
-------------------------------------------------------------------*/
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stNumberInput > div > div > input,
.stSelectbox > div > div > div {
  background: var(--input-bg) !important;
  border: 1px solid var(--border-2) !important;
  color: var(--text) !important;
  border-radius: var(--radius-sm) !important;
  min-height: 44px !important;
  font-size: 0.92rem !important;
}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus,
.stNumberInput > div > div > input:focus,
.stSelectbox > div > div > div:focus {
  border-color: var(--blue) !important;
  box-shadow: 0 0 0 2px var(--blue-dim) !important;
}

/* DO NOT touch checkbox colors here — login page (auth.py) controls them */

/* Primary buttons */
.stButton button,
.stFormSubmitButton button {
  background: linear-gradient(135deg, #1a4fa0, #2563c0) !important;
  color: #ffffff !important;
  font-weight: 600 !important;
  border: none !important;
  border-radius: var(--radius-sm) !important;
  min-height: 44px !important;
  font-size: 0.88rem !important;
}
.stButton button:hover,
.stFormSubmitButton button:hover {
  background: linear-gradient(135deg, #2563c0, #3478d4) !important;
  box-shadow: 0 4px 16px rgba(26,79,160,0.30) !important;
}

/* Divider */
.divider {
  border: none;
  border-top: 1px solid var(--border);
  margin: 12px 0;
}

/* ------------------------------------------------------------------
   Tabs (Chat / Docs / Dashboard / Users / Account)
-------------------------------------------------------------------*/
.stTabs [data-baseweb="tab-list"] {
  gap: 4px !important;
  border-bottom: 2px solid var(--border) !important;
  background: transparent !important;
}

.stTabs [data-baseweb="tab"] {
  padding: 10px 18px !important;
  font-size: 0.88rem !important;
  font-weight: 500 !important;
  border-radius: 8px 8px 0 0 !important;
  color: var(--text-2) !important;
  background: transparent !important;
  min-height: 44px !important;
}

.stTabs [aria-selected="true"] {
  color: var(--blue) !important;
  border-bottom: 2px solid var(--blue) !important;
  font-weight: 600 !important;
}

/* ------------------------------------------------------------------
   Bottom mobile nav (when visible)
-------------------------------------------------------------------*/
.bottom-nav {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: var(--blue);
  border-top: 1px solid rgba(255,255,255,0.15);
  display: flex;
  justify-content: space-around;
  align-items: center;
  padding: 6px 0;
  z-index: 9999;
  box-shadow: 0 -4px 20px rgba(26,79,160,0.25);
}
.bottom-nav-btn {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 5px 2px;
  font-size: 0.55rem;
  color: rgba(255,255,255,0.65);
  cursor: pointer;
  border: none;
  background: none;
  font-family: Inter, sans-serif;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.bottom-nav-btn .nav-icon {
  font-size: 1.2rem;
}
.bottom-nav-btn.active {
  color: #ffffff;
}
@media (min-width: 768px) {
  .bottom-nav { display: none !important; }
}

/* ------------------------------------------------------------------
   Notifications (expander + rows) — readable, no dark hover
-------------------------------------------------------------------*/
.notif-item {
  padding: 8px 10px;
  border-bottom: 1px solid var(--border);
  font-size: 0.83rem;
  background: #ffffff;
  color: var(--text);
}
.notif-item:hover {
  background: #f7f9fc;
  color: var(--text);
}
.notif-message {
  color: var(--text);
}
.notif-ts {
  font-size: 0.65rem;
  color: var(--text-3);
  margin-top: 2px;
}
.notif-empty {
  font-size: 0.83rem;
  color: var(--text-2);
}

/* ------------------------------------------------------------------
   Mic banner text (when mic is on)
-------------------------------------------------------------------*/
.mic-banner {
  background: rgba(192,57,43,0.06);
  border: 1px dashed rgba(192,57,43,0.30);
  border-radius: var(--radius-sm);
  padding: 8px 14px;
  margin-bottom: 6px;
  font-family: "JetBrains Mono", monospace;
  font-size: 0.78rem;
  color: #a93226;
}
/* Light, subtle placeholder text for all inputs/textareas */
input::placeholder,
textarea::placeholder {
  color: var(--text-3) !important;
  font-weight: 400 !important;
  opacity: 0.7 !important;
}

/* ------------------------------------------------------------------
   Chat bubbles wrapper & label
-------------------------------------------------------------------*/
.chat-wrap {
  margin-bottom: 18px;
}
.chat-label {
  font-size: 0.70rem;
  font-weight: 700;
  color: var(--text-3);
  text-transform: uppercase;
  letter-spacing: 0.6px;
  margin-bottom: 4px;
  padding-left: 2px;
}

/* Status dot (session label) */
.dot {
  display: inline-block;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  margin-right: 5px;
  vertical-align: middle;
}

/* ------------------------------------------------------------------
   Confidence bar
-------------------------------------------------------------------*/
.conf-wrap {
  margin-top: 12px;
  padding-top: 8px;
  border-top: 1px solid var(--border);
}
.conf-label {
  font-size: 0.68rem;
  font-weight: 600;
  color: var(--text-3);
  text-transform: uppercase;
  letter-spacing: 0.4px;
  margin-bottom: 5px;
}
.conf-bg {
  background: var(--bg-3);
  border-radius: 99px;
  height: 6px;
  width: 100%;
  overflow: hidden;
  margin-bottom: 4px;
}
.conf-fill {
  height: 100%;
  border-radius: 99px;
  transition: width 0.5s ease;
}
.conf-high   { background: #00c9a7; }
.conf-medium { background: #f0a500; }
.conf-low    { background: #f05252; }
.conf-pct {
  font-size: 0.72rem;
  font-weight: 600;
  margin-top: 2px;
}

/* ------------------------------------------------------------------
   Source excerpts
-------------------------------------------------------------------*/
.src-wrap {
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px solid var(--border);
}
.src-label {
  font-size: 0.68rem;
  font-weight: 700;
  color: var(--text-3);
  text-transform: uppercase;
  letter-spacing: 0.4px;
  margin-bottom: 5px;
}
.src-text {
  font-size: 0.75rem;
  color: var(--text-2);
  font-family: "JetBrains Mono", monospace;
  background: var(--bg-3);
  border-left: 2px solid var(--blue-b);
  border-radius: 0 4px 4px 0;
  padding: 5px 9px;
  margin-bottom: 5px;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.5;
}

/* ------------------------------------------------------------------
   Follow-up suggestion chips
-------------------------------------------------------------------*/
.followup-wrap {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}
.followup-label {
  font-size: 0.67rem;
  font-weight: 700;
  color: var(--text-3);
  text-transform: uppercase;
  letter-spacing: 0.4px;
  width: 100%;
  margin-bottom: 2px;
}
.followup-chip {
  display: inline-flex;
  align-items: center;
  padding: 5px 13px;
  border-radius: 20px;
  background: var(--bg-3);
  border: 1px solid var(--border-2);
  color: var(--blue);
  font-size: 0.78rem;
  cursor: pointer;
  font-family: Inter, sans-serif;
  transition: background 0.15s, border-color 0.15s;
  user-select: none;
}
.followup-chip:hover {
  background: var(--blue-dim);
  border-color: var(--blue);
}

/* ------------------------------------------------------------------
   Typing indicator dots
-------------------------------------------------------------------*/
.typing-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  background: var(--blue);
  border-radius: 50%;
  margin: 0 2px;
  animation: typing-bounce 1.2s infinite ease-in-out;
}
.typing-dot:nth-child(1) { animation-delay: 0s; }
.typing-dot:nth-child(2) { animation-delay: 0.2s; }
.typing-dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes typing-bounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.6; }
  30%           { transform: translateY(-7px); opacity: 1; }
}

/* ------------------------------------------------------------------
   Alert banners (error / warn / info)
-------------------------------------------------------------------*/
.alert-error {
  background: rgba(240,82,82,0.09);
  border: 1px solid rgba(240,82,82,0.30);
  color: #c0392b;
  padding: 10px 14px;
  border-radius: var(--radius-sm);
  font-size: 0.85rem;
  margin: 6px 0;
}
.alert-warn {
  background: rgba(240,165,0,0.09);
  border: 1px solid rgba(240,165,0,0.30);
  color: #a0610a;
  padding: 10px 14px;
  border-radius: var(--radius-sm);
  font-size: 0.85rem;
  margin: 6px 0;
}
.alert-info {
  background: rgba(26,79,160,0.07);
  border: 1px solid rgba(26,79,160,0.20);
  color: var(--blue);
  padding: 10px 14px;
  border-radius: var(--radius-sm);
  font-size: 0.85rem;
  margin: 6px 0;
}
</style>
        """,
        unsafe_allow_html=True,
    )