"""
dashboard.py — Admin analytics dashboard with charts.
Shows: queries/day, top questions, feedback, active users, response times.
"""

import streamlit as st
from database import (
    get_stats, get_queries_per_day, get_top_queries,
    get_feedback_list, get_avg_response_time, get_active_users_today
)


def render_dashboard(pg_url: str):
    st.markdown("### Analytics Dashboard")

    stats   = get_stats(pg_url)
    avg_rt  = get_avg_response_time(pg_url)
    active  = get_active_users_today(pg_url)

    if not stats:
        st.markdown('<div class="alert-info">No data available yet.</div>', unsafe_allow_html=True)
        return

    # ── Top stat cards ──
    thumbs_up  = stats.get('thumbs_up', 0)
    total_fb   = stats.get('feedback', 0)
    sat_pct    = round((thumbs_up / total_fb) * 100) if total_fb > 0 else 0

    st.markdown(f"""
    <div class="stat-row">
        <div class="stat-card"><div class="stat-num">{stats.get('docs',0)}</div><div class="stat-lbl">Documents</div></div>
        <div class="stat-card"><div class="stat-num">{stats.get('queries',0)}</div><div class="stat-lbl">Total Queries</div></div>
        <div class="stat-card"><div class="stat-num">{stats.get('users',0)}</div><div class="stat-lbl">Total Users</div></div>
        <div class="stat-card"><div class="stat-num">{active}</div><div class="stat-lbl">Active Today</div></div>
        <div class="stat-card"><div class="stat-num">{stats.get('avg_conf',0)}%</div><div class="stat-lbl">Avg Confidence</div></div>
        <div class="stat-card"><div class="stat-num">{avg_rt}ms</div><div class="stat-lbl">Avg Response</div></div>
        <div class="stat-card"><div class="stat-num">{sat_pct}%</div><div class="stat-lbl">Satisfaction</div></div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<hr class='divider'>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    # ── Queries per day chart ──
    with col1:
        st.markdown('<div class="dash-title">Queries Per Day (Last 7 Days)</div>', unsafe_allow_html=True)
        rows = get_queries_per_day(pg_url, days=7)
        if rows:
            import pandas as pd
            df = pd.DataFrame(rows, columns=["Day", "Count"])
            df["Day"] = df["Day"].astype(str)
            st.bar_chart(df.set_index("Day")["Count"], use_container_width=True)
        else:
            st.markdown('<div class="alert-info">No query data yet.</div>', unsafe_allow_html=True)

    # ── Feedback chart ──
    with col2:
        st.markdown('<div class="dash-title">User Satisfaction</div>', unsafe_allow_html=True)
        if total_fb > 0:
            import pandas as pd
            df_fb = pd.DataFrame({
                "Feedback": ["Helpful", "Not Helpful"],
                "Count":    [thumbs_up,    total_fb - thumbs_up]
            })
            st.bar_chart(df_fb.set_index("Feedback")["Count"], use_container_width=True)
        else:
            st.markdown('<div class="alert-info">No feedback yet.</div>', unsafe_allow_html=True)

    st.markdown("<hr class='divider'>", unsafe_allow_html=True)

    col3, col4 = st.columns(2)

    # ── Top queries ──
    with col3:
        st.markdown('<div class="dash-title">Most Asked Questions</div>', unsafe_allow_html=True)
        top_qs = get_top_queries(pg_url, limit=8)
        if top_qs:
            for row in top_qs:
                q     = row['query'][:55] + "..." if len(row['query']) > 55 else row['query']
                count = row['count']
                pct   = min(count * 10, 100)
                st.markdown(f"""
                <div style="margin-bottom:8px;">
                    <div style="display:flex;justify-content:space-between;font-size:0.78rem;color:var(--text-2);margin-bottom:3px;">
                        <span>{q}</span><span style="color:var(--blue);font-weight:600;">{count}x</span>
                    </div>
                    <div style="background:var(--blue-dim);border-radius:3px;height:4px;">
                        <div style="background:var(--blue);height:4px;border-radius:3px;width:{pct}%;"></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown('<div class="alert-info">No queries yet.</div>', unsafe_allow_html=True)

    # ── Recent feedback ──
    with col4:
        st.markdown('<div class="dash-title">Recent Feedback</div>', unsafe_allow_html=True)
        feedback_rows = get_feedback_list(pg_url, limit=8)
        if feedback_rows:
            for fb in feedback_rows:
                rating_label = "Helpful" if fb['rating'] == 1 else "Not Helpful"
                color        = "#0a7c4e" if fb['rating'] == 1 else "#c0392b"
                q     = fb['query'][:50] + "..." if len(fb['query']) > 50 else fb['query']
                ts    = str(fb['created_at'])[:16]
                st.markdown(f"""
                <div style="display:flex;gap:8px;align-items:flex-start;padding:7px 0;border-bottom:1px solid var(--border);">
                    <span style="font-size:0.75rem;font-weight:600;color:{color};padding:2px 7px;
                                 background:{color}18;border-radius:4px;">{rating_label}</span>
                    <div>
                        <div style="font-size:0.78rem;color:var(--text-2);">{q}</div>
                        <div style="font-size:0.65rem;color:var(--text-3);">{fb['username']} &middot; {ts}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown('<div class="alert-info">No feedback yet.</div>', unsafe_allow_html=True)