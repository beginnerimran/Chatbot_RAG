"""
mobile_sidebar.py — Mobile-only sidebar handling.

Injects a floating toggle button (fixed position, high z-index) visible only
on small screens (≤991 px). The button opens/closes the Streamlit sidebar by
toggling its CSS state. It survives reruns because it uses a JS-side state
variable (window._srmSidebarOpen) combined with a MutationObserver to stay
in sync with whatever Streamlit renders.

Desktop layout (≥992 px) is left completely untouched — handled by config.py.

Usage in app.py:
    from mobile_sidebar import inject_mobile_sidebar
    inject_mobile_sidebar()   # call once per page render, after setup_page()
"""

import streamlit as st


_MOBILE_SIDEBAR_CSS = """
<style>
/* ── Mobile floating toggle button ── */
@media (max-width: 991px) {

  /* Hide Streamlit's own collapse control on mobile — we replace it */
  [data-testid="collapsedControl"] {
    display: none !important;
  }

  /* Floating toggle button */
  #srm-mob-toggle {
    position: fixed;
    top: 14px;
    left: 14px;
    z-index: 99999;
    width: 44px;
    height: 44px;
    border-radius: 10px;
    background: #1a4fa0;
    color: #ffffff;
    border: none;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 2px 12px rgba(26,79,160,0.40);
    font-size: 1.2rem;
    line-height: 1;
    padding: 0;
    transition: background 0.15s;
    /* Always on top, never hidden */
  }
  #srm-mob-toggle:hover {
    background: #2563c0;
  }

  /* When sidebar is open on mobile — overlay backdrop */
  body.srm-sidebar-open::after {
    content: "";
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.38);
    z-index: 9998;
  }

  /* Sidebar drawer — slide in from left */
  section[data-testid="stSidebar"] {
    position: fixed !important;
    top: 0 !important;
    left: 0 !important;
    height: 100vh !important;
    z-index: 99999 !important;
    transform: translateX(-110%) !important;
    transition: transform 0.25s ease !important;
    box-shadow: 4px 0 24px rgba(26,79,160,0.25) !important;
    min-width: 270px !important;
    max-width: 85vw !important;
    overflow-y: auto !important;
  }
  /* Open state */
  section[data-testid="stSidebar"].srm-sidebar-open {
    transform: translateX(0) !important;
  }
}
</style>
"""

_MOBILE_SIDEBAR_JS = """
<script>
(function () {
  // Only run on mobile
  if (window.innerWidth > 991) return;

  // ── State ──────────────────────────────────────────
  var _open = window._srmSidebarOpen || false;

  function getSidebar() {
    return document.querySelector('section[data-testid="stSidebar"]');
  }

  function applyState(open) {
    _open = open;
    window._srmSidebarOpen = open;

    var sb  = getSidebar();
    var btn = document.getElementById('srm-mob-toggle');

    if (sb) {
      if (open) {
        sb.classList.add('srm-sidebar-open');
        document.body.classList.add('srm-sidebar-open');
      } else {
        sb.classList.remove('srm-sidebar-open');
        document.body.classList.remove('srm-sidebar-open');
      }
    }

    if (btn) {
      btn.innerHTML = open ? '✕' : '☰';
      btn.title     = open ? 'Close menu' : 'Open menu';
    }
  }

  // ── Create button if it doesn't exist ──────────────
  function ensureButton() {
    if (document.getElementById('srm-mob-toggle')) return;
    var btn = document.createElement('button');
    btn.id        = 'srm-mob-toggle';
    btn.innerHTML = _open ? '✕' : '☰';
    btn.title     = _open ? 'Close menu' : 'Open menu';
    btn.setAttribute('aria-label', 'Toggle sidebar');
    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      applyState(!_open);
    });
    document.body.appendChild(btn);
  }

  // ── Close sidebar when backdrop is tapped ──────────
  document.addEventListener('click', function (e) {
    if (!_open) return;
    var sb  = getSidebar();
    var btn = document.getElementById('srm-mob-toggle');
    if (sb && !sb.contains(e.target) && btn && !btn.contains(e.target)) {
      applyState(false);
    }
  });

  // ── Re-apply state after Streamlit rerenders ───────
  // Streamlit replaces DOM nodes on reruns; use MutationObserver to reattach.
  var _observer = new MutationObserver(function () {
    ensureButton();
    applyState(_open);            // restore open/closed state
  });
  _observer.observe(document.body, { childList: true, subtree: true });

  // ── Initial setup ─────────────────────────────────
  ensureButton();
  applyState(_open);

})();
</script>
"""


def inject_mobile_sidebar() -> None:
    """
    Call once per page render (after setup_page).
    Injects the CSS and JS that power the mobile floating toggle button.
    Has no effect on desktop (≥ 992 px) — purely additive on mobile.
    """
    st.markdown(_MOBILE_SIDEBAR_CSS, unsafe_allow_html=True)
    st.markdown(_MOBILE_SIDEBAR_JS,  unsafe_allow_html=True)
