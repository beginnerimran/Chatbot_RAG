"""
config.py — Page config, CSS (SRM blue/white theme), constants.
"""

import hashlib
import streamlit as st

# -------------------------------------------------------------------
# Seed demo users and login note (same credentials you had)
# -------------------------------------------------------------------

SEED_USERS = [
    ("admin",   hashlib.sha256("admin123".encode()).hexdigest(),   "admin",   "Administrator"),
    ("staff1",  hashlib.sha256("staff123".encode()).hexdigest(),   "staff",   "Dr. Priya Sharma"),
    ("student1", hashlib.sha256("student123".encode()).hexdigest(), "student", "Student User"),
    ("student2", hashlib.sha256("pass1234".encode()).hexdigest(),  "student", "Student User 2"),
]

DEMO_CREDENTIALS_NOTE = """
| Username | Password  | Role   |
|---------|-----------|--------|
| admin   | admin123  | Admin  |
| staff1  | staff123  | Staff  |
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
# Global CSS (SRM blue/white theme + sidebar toggle + notifications)
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

/* Hide default Streamlit chrome, but keep sidebar toggle */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
[data-testid="stToolbar"] { visibility: hidden; }

/* --- Always-visible sidebar collapse control (top-left) --- */
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

/* Sidebar styling */
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

/* App header */
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
  color: #ffffff;
  border: 1px solid rgba(255,255,255,0.35);
}
.role-student {
  background: rgba(10,124,78,0.12);
  color: #0a7c4e;
  border: 1px solid rgba(10,124,78,0.25);
}

/* Chat bubbles (short version of your original) */
.chat-user {
  background: var(--blue-dim);
  border: 1px solid var(--blue-b);
  border-radius: 16px 16px 4px 16px;
  padding: 12px 16px;
  margin-left: 8%;
  font-size: 0.92rem;
  line-height: 1.65;
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
}

/* Generic cards */
.stat-card, .doc-card {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 12px 14px;
  box-shadow: var(--shadow);
}

/* Inputs */
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

/* Notification list (readable text) */
.notif-item {
  padding: 8px 10px;
  border-bottom: 1px solid var(--border);
  font-size: 0.83rem;
  background: #ffffff;
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
</style>
        """,
        unsafe_allow_html=True,
    )