"""
ui_components.py — Docs panel, user management, change password.
UPDATES:
  - Strong password validation with real-time rules display
  - Email is mandatory in user creation
  - All text/labels visible (blue-white theme, no black)
  - Clean role field with visible styling
  - Institutional email workflow UI
"""

import streamlit as st

from auth import check_permission
from database import (
    add_user, change_password, delete_document,
    delete_user, get_all_users, get_document_list,
    validate_password,
)


def _password_rules_html(password: str) -> str:
    """Return an HTML checklist of password rules with pass/fail status."""
    rules = [
        ("At least 8 characters",              len(password) >= 8),
        ("One uppercase letter (A-Z)",          any(c.isupper() for c in password)),
        ("One lowercase letter (a-z)",          any(c.islower() for c in password)),
        ("One number (0-9)",                    any(c.isdigit() for c in password)),
        ("One special character (!@#$%^&* …)",  any(c in "!@#$%^&*()_+-=[]{}|;':\",./<>?" for c in password)),
    ]
    items = ""
    for label, passed in rules:
        color = "#0a7c4e" if passed else "#c0392b"
        icon  = "✓" if passed else "✗"
        items += (
            f'<div style="display:flex;align-items:center;gap:6px;margin-bottom:3px;">'
            f'<span style="font-size:0.75rem;font-weight:700;color:{color};width:14px;">{icon}</span>'
            f'<span style="font-size:0.75rem;color:var(--text-2);">{label}</span>'
            f'</div>'
        )
    return f'<div style="padding:8px 12px;background:var(--bg-3);border-radius:6px;margin-top:4px;">{items}</div>'


def render_docs_panel(pg_url: str, role: str):
    st.markdown("### Uploaded Documents")
    docs = get_document_list(pg_url)
    if not docs:
        st.markdown(
            '<div class="alert-info">No documents uploaded yet. '
            'Ask Admin or Staff to upload college PDFs.</div>',
            unsafe_allow_html=True,
        )
        return

    st.markdown(
        f'<div style="font-size:0.78rem;color:var(--text-3);margin-bottom:12px;">'
        f'{len(docs)} document{"s" if len(docs) != 1 else ""} in the knowledge base</div>',
        unsafe_allow_html=True,
    )

    for doc in docs:
        ocr_tag  = '<span class="ocr-badge">OCR</span>' if doc.get("used_ocr") else ""
        cat      = doc.get("category", "General")
        uploader = doc.get("uploaded_by", "-")
        at       = str(doc.get("uploaded_at", ""))[:16]
        chunks   = doc.get("chunk_count", "?")
        fname    = doc["filename"]

        col_info, col_del = st.columns([5, 1])
        with col_info:
            st.markdown(
                f"""
<div class="doc-card">
    <div style="color:var(--text);font-weight:600;font-size:0.88rem;margin-bottom:4px;">
        {fname} {ocr_tag}
        <span style="display:inline-block;padding:1px 8px;border-radius:10px;
                     font-size:0.65rem;font-weight:700;background:rgba(26,79,160,0.10);
                     color:var(--blue);border:1px solid rgba(26,79,160,0.20);margin-left:4px;">
            {cat}
        </span>
    </div>
    <div style="font-size:0.72rem;color:var(--text-3);">
        {chunks} chunks &middot; uploaded by {uploader} &middot; {at}
    </div>
</div>
""",
                unsafe_allow_html=True,
            )
        with col_del:
            if check_permission(role, "delete"):
                if st.button("Delete", key=f"docs_del_{doc['id']}", help="Delete document"):
                    if delete_document(pg_url, doc["id"]):
                        st.session_state.docs_loaded = False
                        st.rerun()


def render_user_management(pg_url: str, current_username: str):
    st.markdown("### User Management")

    with st.expander("➕  Add New User", expanded=False):
        st.markdown(
            '<div class="alert-info" style="margin-bottom:12px;">'
            "Accounts are created by administrators only. "
            "All fields are required — email is mandatory and password must be strong."
            "</div>",
            unsafe_allow_html=True,
        )

        with st.form("add_user_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                new_uname   = st.text_input("Username *", placeholder="e.g. student2024")
                new_display = st.text_input("Display Name *", placeholder="e.g. Priya Sharma")
                new_email   = st.text_input(
                    "Email * (required)",
                    placeholder="student@srmist.edu.in or personal@gmail.com",
                )
            with col2:
                new_pass = st.text_input(
                    "Password *",
                    type="password",
                    placeholder="Min 8 chars, upper, lower, number, special",
                )
                new_pass2 = st.text_input("Confirm Password *", type="password")
                new_role  = st.selectbox(
                    "Role *",
                    ["student", "staff", "admin"],
                    format_func=lambda x: x.capitalize(),
                )

            if new_pass:
                st.markdown(
                    '<div style="font-size:0.72rem;font-weight:700;color:var(--text-3);'
                    'text-transform:uppercase;letter-spacing:0.3px;margin-top:4px;margin-bottom:2px;">'
                    "Password Requirements</div>",
                    unsafe_allow_html=True,
                )
                st.markdown(_password_rules_html(new_pass), unsafe_allow_html=True)

            submitted = st.form_submit_button("Create User", use_container_width=True)

        if submitted:
            errors = []
            if not new_uname.strip():
                errors.append("Username is required.")
            elif " " in new_uname:
                errors.append("Username cannot contain spaces.")
            if not new_display.strip():
                errors.append("Display Name is required.")
            if not new_email.strip():
                errors.append("Email is required.")
            if not new_pass:
                errors.append("Password is required.")
            elif new_pass != new_pass2:
                errors.append("Passwords do not match.")
            else:
                ok_pw, pw_msg = validate_password(new_pass)
                if not ok_pw:
                    errors.append(pw_msg)

            if errors:
                for err in errors:
                    st.error(err)
            else:
                ok, msg = add_user(
                    pg_url, new_uname.strip(), new_pass, new_role,
                    new_display.strip(), new_email.strip()
                )
                if ok:
                    st.success(f"✓ User '{new_uname.strip()}' created successfully as {new_role.capitalize()}.")
                    st.rerun()
                else:
                    st.error(msg)

    with st.expander("🏛  Create Institutional Email (@srmist.edu.in)", expanded=False):
        st.markdown(
            '<div class="alert-info" style="margin-bottom:12px;">'
            "Create an official SRM college email for an existing student. "
            "Notify the student's personal email with their new login details."
            "</div>",
            unsafe_allow_html=True,
        )
        all_users = get_all_users(pg_url)
        student_options = {
            u["username"]: f"{u['display_name']} ({u['username']})"
            for u in all_users
            if u["role"] == "student"
        }
        if not student_options:
            st.info("No student accounts found.")
        else:
            with st.form("institutional_email_form", clear_on_submit=True):
                sel_student = st.selectbox(
                    "Select Student",
                    options=list(student_options.keys()),
                    format_func=lambda x: student_options[x],
                )
                inst_local = st.text_input(
                    "College Username (before @srmist.edu.in)",
                    placeholder="e.g. priya.sharma2024",
                )
                inst_pass  = st.text_input("Initial Password *", type="password",
                                            placeholder="Min 8 chars, upper, lower, number, special")
                inst_pass2 = st.text_input("Confirm Password *", type="password")

                if inst_pass:
                    st.markdown(_password_rules_html(inst_pass), unsafe_allow_html=True)

                inst_submit = st.form_submit_button("Create & Notify Student", use_container_width=True)

            if inst_submit:
                errors = []
                if not inst_local.strip():
                    errors.append("College username is required.")
                elif " " in inst_local:
                    errors.append("College username cannot contain spaces.")
                if not inst_pass:
                    errors.append("Password is required.")
                elif inst_pass != inst_pass2:
                    errors.append("Passwords do not match.")
                else:
                    ok_pw, pw_msg = validate_password(inst_pass)
                    if not ok_pw:
                        errors.append(pw_msg)

                if errors:
                    for err in errors:
                        st.error(err)
                else:
                    inst_email    = f"{inst_local.strip().lower()}@srmist.edu.in"
                    inst_username = inst_local.strip().lower()
                    sel_display   = next(
                        (u["display_name"] for u in all_users if u["username"] == sel_student), sel_student
                    )
                    personal_email = next(
                        (u["email"] for u in all_users if u["username"] == sel_student), ""
                    )
                    ok, msg = add_user(
                        pg_url, inst_username, inst_pass, "student",
                        sel_display, inst_email
                    )
                    if ok:
                        st.success(f"✓ Institutional account created: **{inst_email}**")
                        if personal_email:
                            st.info(
                                f"📧 Please send the following to **{personal_email}**:\n\n"
                                f"- **New college email / username:** {inst_email}\n"
                                f"- **Display name:** {sel_display}\n"
                                f"- **Role:** Student\n"
                                f"- **Password:** *(as set above)*"
                            )
                        else:
                            st.warning("No personal email on file — inform the student directly.")
                        st.rerun()
                    else:
                        st.error(msg)

    st.markdown(
        '<div style="font-size:0.9rem;font-weight:700;color:var(--text);margin:16px 0 8px 0;">'
        "Existing Users</div>",
        unsafe_allow_html=True,
    )
    users = get_all_users(pg_url)
    if users:
        st.markdown(
            '<div style="display:grid;grid-template-columns:2fr 1.2fr 2fr 2fr 1fr;'
            'gap:8px;padding:6px 8px;background:var(--blue-dim);border-radius:6px;'
            'font-size:0.70rem;font-weight:700;color:var(--text-3);'
            'text-transform:uppercase;letter-spacing:0.4px;margin-bottom:4px;">'
            "<span>Username</span><span>Role</span><span>Display Name</span>"
            "<span>Last Active</span><span>Action</span></div>",
            unsafe_allow_html=True,
        )
        for u in users:
            c1, c2, c3, c4, c5 = st.columns([2, 1.2, 2, 2, 1])
            with c1:
                st.markdown(
                    f'<div style="font-size:0.83rem;color:var(--text);padding:4px 0;">{u["username"]}</div>',
                    unsafe_allow_html=True,
                )
            with c2:
                role_color = {"admin": "#b86200", "staff": "#1a4fa0", "student": "#0a7c4e"}.get(u["role"], "#555")
                role_bg    = {"admin": "rgba(224,123,0,0.12)", "staff": "rgba(26,79,160,0.10)",
                              "student": "rgba(10,124,78,0.10)"}.get(u["role"], "#eee")
                st.markdown(
                    f'<span style="display:inline-block;padding:2px 8px;border-radius:10px;'
                    f'font-size:0.65rem;font-weight:700;text-transform:uppercase;letter-spacing:0.4px;'
                    f'background:{role_bg};color:{role_color};">{u["role"]}</span>',
                    unsafe_allow_html=True,
                )
            with c3:
                st.markdown(
                    f'<div style="font-size:0.80rem;color:var(--text-2);padding:4px 0;">{u["display_name"]}</div>',
                    unsafe_allow_html=True,
                )
            with c4:
                last_a = str(u.get("last_active", ""))[:16]
                st.markdown(
                    f'<div style="font-size:0.70rem;color:var(--text-3);padding:4px 0;">{last_a or "—"}</div>',
                    unsafe_allow_html=True,
                )
            with c5:
                if u["username"] != current_username:
                    if st.button("Delete", key=f"del_user_{u['id']}", help=f"Delete {u['username']}"):
                        ok, msg = delete_user(pg_url, u["id"], current_username)
                        if ok:
                            st.rerun()
                        else:
                            st.error(msg)
                else:
                    st.markdown(
                        '<div style="font-size:0.70rem;color:var(--blue);padding:4px 0;">you</div>',
                        unsafe_allow_html=True,
                    )
    else:
        st.info("No users found.")


def render_change_password(pg_url: str, username: str):
    st.markdown("### Account Settings")

    st.markdown(
        """
<div style="background:var(--blue-dim);border:1px solid var(--blue-b);border-radius:8px;
            padding:12px 16px;margin-bottom:14px;">
    <div style="font-size:0.78rem;font-weight:700;color:var(--blue);margin-bottom:6px;">
        Password Requirements
    </div>
    <div style="font-size:0.78rem;color:var(--text-2);line-height:1.8;">
        ✓ Minimum <strong>8 characters</strong><br>
        ✓ At least one <strong>uppercase letter</strong> (A-Z)<br>
        ✓ At least one <strong>lowercase letter</strong> (a-z)<br>
        ✓ At least one <strong>number</strong> (0-9)<br>
        ✓ At least one <strong>special character</strong> (!@#$%^&amp;* etc.)
    </div>
</div>
""",
        unsafe_allow_html=True,
    )

    with st.expander("Change Password", expanded=False):
        with st.form("change_pw_form"):
            old_pw  = st.text_input("Current Password", type="password")
            new_pw  = st.text_input(
                "New Password",
                type="password",
                placeholder="Min 8 chars, upper, lower, number, special",
            )
            new_pw2 = st.text_input("Confirm New Password", type="password")

            if new_pw:
                st.markdown(_password_rules_html(new_pw), unsafe_allow_html=True)

            submit = st.form_submit_button("Update Password", use_container_width=True)

        if submit:
            if not old_pw or not new_pw or not new_pw2:
                st.error("All fields are required.")
            elif new_pw != new_pw2:
                st.error("New passwords do not match.")
            else:
                ok_pw, pw_msg = validate_password(new_pw)
                if not ok_pw:
                    st.error(pw_msg)
                else:
                    ok, msg = change_password(pg_url, username, old_pw, new_pw)
                    if ok:
                        st.success("✓ " + msg)
                    else:
                        st.error(msg)