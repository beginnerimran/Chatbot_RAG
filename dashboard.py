"""
dashboard.py — Admin analytics dashboard with charts.
CHANGES:
  - Mobile-first: stat cards wrap, charts stack to single column on small screens
  - Responsive CSS injected at render time
  - All data queries and chart logic unchanged
"""

import streamlit as st
from database import (
    get_stats, get_queries_per_day, get_top_queries,
    get_feedback_list, get_avg_response_time, get_active_users_today
)


def render_dashboard(pg_url: str):
    st.markdown("### Analytics Dashboard")

    # Responsive CSS for dashboard
    st.markdown("""
<style>
/* ── Mobile-first dashboard ── */

/* Stat row: wrap on small screens */
.dash-stat-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 10px;
    margin-bottom: 16px;
}
@media (min-width: 540px) {
    .dash-stat-grid { grid-template-columns: repeat(3, 1fr); }
}
@media (min-width: 900px) {
    .dash-stat-grid { grid-template-columns: repeat(7, 1fr); }
}
.dash-stat-card {
    background: #f0f6ff;
    border: 1px solid #d0dbef;
    border-radius: 10px;
    padding: 14px 10px;
    text-align: center;
    box-shadow: 0 2px 8px rgba(26,79,160,0.07);
}
.dash-stat-num {
    font-size: 1.5rem;
    font-weight: 800;
    color: #1a2640;
    line-height: 1.2;
}
.dash-stat-lbl {
    font-size: 0.62rem;
    font-weight: 600;
    color: #3d5275;
    text-transform: uppercase;
    letter-spacing: 0.4px;
    margin-top: 2px;
}
</style>
""", unsafe_allow_html=True)

    stats   = get_stats(pg_url)
    avg_rt  = get_avg_response_time(pg_url)
    active  = get_active_users_today(pg_url)

    if not stats:
        st.markdown('<div class="alert-info">No data available yet.</div>', unsafe_allow_html=True)
        return

    thumbs_up  = stats.get('thumbs_up', 0)
    total_fb   = stats.get('feedback', 0)
    sat_pct    = round((thumbs_up / total_fb) * 100) if total_fb > 0 else 0

    # ── Stat cards — responsive grid ──
    st.markdown(f"""
<div class="dash-stat-grid">
    <div class="dash-stat-card"><div class="dash-stat-num">{stats.get('docs',0)}</div><div class="dash-stat-lbl">Documents</div></div>
    <div class="dash-stat-card"><div class="dash-stat-num">{stats.get('queries',0)}</div><div class="dash-stat-lbl">Total Queries</div></div>
    <div class="dash-stat-card"><div class="dash-stat-num">{stats.get('users',0)}</div><div class="dash-stat-lbl">Total Users</div></div>
    <div class="dash-stat-card"><div class="dash-stat-num">{active}</div><div class="dash-stat-lbl">Active Today</div></div>
    <div class="dash-stat-card"><div class="dash-stat-num">{stats.get('avg_conf',0)}%</div><div class="dash-stat-lbl">Avg Confidence</div></div>
    <div class="dash-stat-card"><div class="dash-stat-num">{avg_rt}ms</div><div class="dash-stat-lbl">Avg Response</div></div>
    <div class="dash-stat-card"><div class="dash-stat-num">{sat_pct}%</div><div class="dash-stat-lbl">Satisfaction</div></div>
</div>
""", unsafe_allow_html=True)

    st.markdown("<hr class='divider'>", unsafe_allow_html=True)

    # ── Charts: single column on mobile, two columns on wide screens ──
    # We detect by using st.columns with gap and let CSS handle the stacking feel.
    # Streamlit columns don't collapse natively, so we render them stacked by default
    # and use wide columns only on truly wide displays.

    # Queries per day
    st.markdown('<div class="dash-title">Queries Per Day (Last 7 Days)</div>', unsafe_allow_html=True)
    rows = get_queries_per_day(pg_url, days=7)
    if rows:
        import pandas as pd
        df = pd.DataFrame(rows, columns=["Day", "Count"])
        df["Day"] = df["Day"].astype(str)
        st.bar_chart(df.set_index("Day")["Count"], use_container_width=True)
    else:
        st.markdown('<div class="alert-info">No query data yet.</div>', unsafe_allow_html=True)

    # Satisfaction chart
    st.markdown('<div class="dash-title">User Satisfaction</div>', unsafe_allow_html=True)
    if total_fb > 0:
        import pandas as pd
        df_fb = pd.DataFrame({
            "Feedback": ["Helpful", "Not Helpful"],
            "Count":    [thumbs_up, total_fb - thumbs_up]
        })
        st.bar_chart(df_fb.set_index("Feedback")["Count"], use_container_width=True)
    else:
        st.markdown('<div class="alert-info">No feedback yet.</div>', unsafe_allow_html=True)

    st.markdown("<hr class='divider'>", unsafe_allow_html=True)

    # ── Most asked questions ──
    st.markdown('<div class="dash-title">Most Asked Questions</div>', unsafe_allow_html=True)
    top_qs = get_top_queries(pg_url, limit=8)
    if top_qs:
        for row in top_qs:
            q     = row['query'][:60] + "..." if len(row['query']) > 60 else row['query']
            count = row['count']
            pct   = min(count * 10, 100)
            st.markdown(f"""
            <div style="margin-bottom:10px;">
                <div style="display:flex;justify-content:space-between;
                            font-size:0.80rem;color:var(--text-2);margin-bottom:4px;
                            flex-wrap:wrap;gap:4px;">
                    <span style="flex:1;min-width:0;word-break:break-word;">{q}</span>
                    <span style="color:var(--blue);font-weight:600;white-space:nowrap;">{count}x</span>
                </div>
                <div style="background:var(--blue-dim);border-radius:3px;height:5px;">
                    <div style="background:var(--blue);height:5px;border-radius:3px;width:{pct}%;"></div>
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown('<div class="alert-info">No queries yet.</div>', unsafe_allow_html=True)

    st.markdown("<hr class='divider'>", unsafe_allow_html=True)

    # ── Recent feedback ──
    st.markdown('<div class="dash-title">Recent Feedback</div>', unsafe_allow_html=True)
    feedback_rows = get_feedback_list(pg_url, limit=10)
    if feedback_rows:
        for fb in feedback_rows:
            rating_label = "Helpful" if fb['rating'] == 1 else "Not Helpful"
            color        = "#0a7c4e" if fb['rating'] == 1 else "#c0392b"
            q     = fb['query'][:60] + "..." if len(fb['query']) > 60 else fb['query']
            ts    = str(fb['created_at'])[:16]
            st.markdown(f"""
            <div style="display:flex;gap:8px;align-items:flex-start;padding:8px 0;
                        border-bottom:1px solid var(--border);flex-wrap:wrap;">
                <span style="font-size:0.72rem;font-weight:600;color:{color};padding:2px 8px;
                             background:{color}18;border-radius:4px;white-space:nowrap;">{rating_label}</span>
                <div style="flex:1;min-width:0;">
                    <div style="font-size:0.80rem;color:var(--text-2);word-break:break-word;">{q}</div>
                    <div style="font-size:0.65rem;color:var(--text-3);margin-top:2px;">{fb['username']} &middot; {ts}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown('<div class="alert-info">No feedback yet.</div>', unsafe_allow_html=True)