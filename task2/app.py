"""
Streamlit frontend for Reddit Sentiment Analyser — Reddit-style card UI.
Run: streamlit run app.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
from datetime import datetime
import re

from model.sentiment_model import build_model
from scraper.reddit_scraper import fetch_reddit_posts
from utils.analyser import analyse_posts
from utils.html_report import build_html_report

# -----------------------
# Page config
# -----------------------
st.set_page_config(
    page_title="Reddit Sentiment Analyser",
    page_icon="🔍",
    layout="wide",
)

# -----------------------
# Global CSS — Reddit-style dark theme
# -----------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'IBM Plex Sans', sans-serif;
    background-color: #0d1117;
    color: #e6edf3;
}

/* Hide Streamlit chrome */
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding: 0 !important; max-width: 100% !important; }

/* ── Top navbar ── */
.reddit-nav {
    background: #161b22;
    border-bottom: 1px solid #30363d;
    padding: 12px 32px;
    display: flex;
    align-items: center;
    gap: 16px;
    position: sticky;
    top: 0;
    z-index: 100;
}
.reddit-nav .logo {
    font-size: 22px;
    font-weight: 700;
    color: #ff4500;
    letter-spacing: -0.5px;
    text-decoration: none;
}
.reddit-nav .logo span { color: #e6edf3; }
.nav-badge {
    background: #ff4500;
    color: white;
    font-size: 11px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 12px;
    letter-spacing: 0.5px;
    text-transform: uppercase;
}

/* ── Layout ── */
.main-layout {
    display: flex;
    gap: 0;
    min-height: 100vh;
}

/* ── Sidebar panel ── */
.sidebar-panel {
    width: 300px;
    min-width: 300px;
    background: #161b22;
    border-right: 1px solid #30363d;
    padding: 24px 20px;
    position: sticky;
    top: 57px;
    height: calc(100vh - 57px);
    overflow-y: auto;
}
.sidebar-panel h3 {
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: #8b949e;
    margin: 0 0 16px 0;
}

/* ── Feed area ── */
.feed-area {
    flex: 1;
    padding: 20px 24px;
    max-width: 900px;
}

/* ── Sort bar ── */
.sort-bar {
    display: flex;
    align-items: center;
    gap: 8px;
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 10px 16px;
    margin-bottom: 16px;
}
.sort-btn {
    background: none;
    border: none;
    color: #8b949e;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    padding: 4px 10px;
    border-radius: 20px;
    font-family: 'IBM Plex Sans', sans-serif;
}
.sort-btn.active {
    background: #ff4500;
    color: white;
}
.post-count {
    margin-left: auto;
    font-size: 12px;
    color: #8b949e;
}

/* ── Reddit post card ── */
.post-card {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    margin-bottom: 10px;
    display: flex;
    overflow: hidden;
    transition: border-color 0.15s ease;
    cursor: pointer;
}
.post-card:hover { border-color: #8b949e; }

/* Vote column */
.vote-col {
    background: #0d1117;
    width: 44px;
    min-width: 44px;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 10px 0;
    gap: 4px;
}
.vote-arrow { font-size: 16px; color: #8b949e; line-height: 1; }
.vote-score {
    font-size: 12px;
    font-weight: 700;
    font-family: 'IBM Plex Mono', monospace;
    line-height: 1;
}
.vote-score.pos { color: #ff4500; }
.vote-score.neg { color: #7193ff; }
.vote-score.neu { color: #8b949e; }

/* Content column */
.post-content {
    padding: 10px 12px;
    flex: 1;
    min-width: 0;
}
.post-meta {
    font-size: 11px;
    color: #8b949e;
    margin-bottom: 6px;
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
}
.post-meta .sub { color: #e6edf3; font-weight: 600; }
.post-meta .dot { color: #30363d; }

.post-title {
    font-size: 15px;
    font-weight: 600;
    color: #e6edf3;
    line-height: 1.4;
    margin-bottom: 8px;
    text-decoration: none;
    display: block;
    word-break: break-word;
}
.post-title:hover { color: #ff4500; }

.post-summary {
    font-size: 12px;
    color: #8b949e;
    line-height: 1.5;
    margin-bottom: 8px;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
}

.post-actions {
    display: flex;
    align-items: center;
    gap: 14px;
}
.action-btn {
    font-size: 11px;
    font-weight: 600;
    color: #8b949e;
    display: flex;
    align-items: center;
    gap: 4px;
    text-decoration: none;
    padding: 2px 6px;
    border-radius: 2px;
}
.action-btn:hover { background: #21262d; color: #e6edf3; }

/* Sentiment pill */
.pill {
    font-size: 10px;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 20px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.pill-pos { background: #0d2e1a; color: #3fb950; border: 1px solid #238636; }
.pill-neg { background: #2d0f0f; color: #f85149; border: 1px solid #da3633; }
.pill-neu { background: #1c1f26; color: #8b949e; border: 1px solid #30363d; }

/* ── Metric cards ── */
.metrics-row {
    display: flex;
    gap: 10px;
    margin-bottom: 16px;
}
.metric-card {
    flex: 1;
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 14px 16px;
    text-align: center;
}
.metric-card .m-value {
    font-size: 26px;
    font-weight: 700;
    font-family: 'IBM Plex Mono', monospace;
    line-height: 1;
    margin-bottom: 4px;
}
.metric-card .m-label {
    font-size: 11px;
    color: #8b949e;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    font-weight: 600;
}
.m-total { color: #e6edf3; }
.m-pos   { color: #3fb950; }
.m-neg   { color: #f85149; }
.m-neu   { color: #8b949e; }

/* Filter tabs */
.filter-tabs {
    display: flex;
    gap: 6px;
    margin-bottom: 14px;
}
.ftab {
    font-size: 12px;
    font-weight: 600;
    padding: 5px 14px;
    border-radius: 20px;
    border: 1px solid #30363d;
    background: none;
    color: #8b949e;
    cursor: pointer;
    font-family: 'IBM Plex Sans', sans-serif;
    transition: all 0.15s;
}
.ftab:hover { border-color: #8b949e; color: #e6edf3; }
.ftab.active-all  { background: #e6edf3; color: #0d1117; border-color: #e6edf3; }
.ftab.active-pos  { background: #238636; color: white;   border-color: #238636; }
.ftab.active-neg  { background: #da3633; color: white;   border-color: #da3633; }
.ftab.active-neu  { background: #30363d; color: #e6edf3; border-color: #30363d; }

/* Empty / loading states */
.empty-state {
    text-align: center;
    padding: 60px 20px;
    color: #8b949e;
}
.empty-state .big { font-size: 48px; margin-bottom: 12px; }
.empty-state h3 { font-size: 18px; color: #e6edf3; margin-bottom: 8px; }

/* Scrollbar */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: #0d1117; }
::-webkit-scrollbar-thumb { background: #30363d; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #8b949e; }
</style>
""", unsafe_allow_html=True)


# -----------------------
# Helper: strip HTML tags from summary
# -----------------------
def strip_html(text: str) -> str:
    text = re.sub(r'<[^>]+>', ' ', text or "")
    text = re.sub(r'\s+', ' ', text).strip()
    return text


# -----------------------
# Session state
# -----------------------
if "results"      not in st.session_state: st.session_state.results      = []
if "topic"        not in st.session_state: st.session_state.topic        = ""
if "active_filter" not in st.session_state: st.session_state.active_filter = "All"


# -----------------------
# Top navbar
# -----------------------
st.markdown("""
<div class="reddit-nav">
    <span class="logo">reddit<span>sentiment</span></span>
    <span class="nav-badge">ML Powered</span>
</div>
""", unsafe_allow_html=True)


# -----------------------
# Two-column layout: sidebar + feed
# -----------------------
left, right = st.columns([1, 3], gap="small")

# ── LEFT SIDEBAR ──
with left:
    st.markdown("### 🔍 Search")
    topic = st.text_input("", placeholder="e.g. Bitcoin, AI, Tesla…", label_visibility="collapsed")
    limit = st.slider("Max posts", 10, 100, 25, 5)
    run_btn = st.button("🚀  Analyse", use_container_width=True, type="primary")

    st.divider()
    st.markdown("**About**")
    st.caption("Fetches Reddit posts via RSS and classifies each as **positive**, **negative**, or **neutral** using TF-IDF + Logistic Regression.")

    if st.session_state.topic:
        st.divider()
        st.markdown(f"**Last search:** `{st.session_state.topic}`")
        st.caption(f"{len(st.session_state.results)} posts fetched")

# ── RIGHT FEED ──
with right:

    # Run analysis
    if run_btn:
        if not topic.strip():
            st.warning("Enter a topic first.")
        else:
            with st.spinner(f"Fetching posts for **{topic}**…"):
                model   = build_model()
                posts   = fetch_reddit_posts(topic, limit=limit)
            if not posts:
                st.error("No posts found. Try a different topic or check your connection.")
            else:
                with st.spinner("Analysing sentiment…"):
                    results = analyse_posts(posts, model)
                st.session_state.results       = results
                st.session_state.topic         = topic
                st.session_state.active_filter = "All"

    results = st.session_state.results

    if not results:
        st.markdown("""
        <div class="empty-state">
            <div class="big">🤖</div>
            <h3>Nothing here yet</h3>
            <p>Enter a topic in the sidebar and hit <b>Analyse</b></p>
        </div>
        """, unsafe_allow_html=True)

    else:
        topic_used = st.session_state.topic
        total = len(results)
        pos   = sum(1 for r in results if r["sentiment"] == "positive")
        neg   = sum(1 for r in results if r["sentiment"] == "negative")
        neu   = total - pos - neg

        # Metrics row
        st.markdown(f"""
        <div class="metrics-row">
            <div class="metric-card"><div class="m-value m-total">{total}</div><div class="m-label">Posts</div></div>
            <div class="metric-card"><div class="m-value m-pos">{pos}</div><div class="m-label">Positive</div></div>
            <div class="metric-card"><div class="m-value m-neg">{neg}</div><div class="m-label">Negative</div></div>
            <div class="metric-card"><div class="m-value m-neu">{neu}</div><div class="m-label">Neutral</div></div>
        </div>
        """, unsafe_allow_html=True)

        # Filter tabs
        af = st.session_state.active_filter
        c1, c2, c3, c4, _ = st.columns([1,1,1,1,4])
        if c1.button("All",      key="f_all"): st.session_state.active_filter = "All"
        if c2.button("Positive", key="f_pos"): st.session_state.active_filter = "positive"
        if c3.button("Negative", key="f_neg"): st.session_state.active_filter = "negative"
        if c4.button("Neutral",  key="f_neu"): st.session_state.active_filter = "neutral"

        af = st.session_state.active_filter
        filtered = results if af == "All" else [r for r in results if r["sentiment"] == af]

        st.markdown(f"<div style='font-size:12px;color:#8b949e;margin-bottom:12px;'>"
                    f"Showing <b style='color:#e6edf3'>{len(filtered)}</b> posts · "
                    f"r/all · <b style='color:#e6edf3'>{topic_used}</b></div>",
                    unsafe_allow_html=True)

        # Post cards
        cards_html = ""
        for i, r in enumerate(filtered):
            clean_summary = strip_html(r["summary"])[:200]
            if len(strip_html(r["summary"])) > 200:
                clean_summary += "…"

            score     = r["score"]
            sentiment = r["sentiment"]

            if sentiment == "positive":
                pill_cls  = "pill-pos"
                pill_lbl  = "▲ Positive"
                score_cls = "pos"
            elif sentiment == "negative":
                pill_cls  = "pill-neg"
                pill_lbl  = "▼ Negative"
                score_cls = "neg"
            else:
                pill_cls  = "pill-neu"
                pill_lbl  = "● Neutral"
                score_cls = "neu"

            cards_html += f"""
            <div class="post-card">
                <div class="vote-col">
                    <span class="vote-arrow">▲</span>
                    <span class="vote-score {score_cls}">{score:+d}</span>
                    <span class="vote-arrow" style="color:#30363d">▼</span>
                </div>
                <div class="post-content">
                    <div class="post-meta">
                        <span class="sub">r/all</span>
                        <span class="dot">•</span>
                        <span>Posted by u/redditor_{i+1}</span>
                        <span class="dot">•</span>
                        <span class="pill {pill_cls}">{pill_lbl}</span>
                    </div>
                    <a class="post-title" href="{r['link']}" target="_blank">{r['title']}</a>
                    {"" if not clean_summary else f'<div class="post-summary">{clean_summary}</div>'}
                    <div class="post-actions">
                        <a class="action-btn" href="{r['link']}" target="_blank">💬 Comments</a>
                        <span class="action-btn">🔗 Share</span>
                        <span class="action-btn">⭐ Save</span>
                    </div>
                </div>
            </div>
            """

        st.markdown(cards_html, unsafe_allow_html=True)

        # Download button
        st.divider()
        html_report = build_html_report(topic_used, results)
        st.download_button(
            "⬇️ Download HTML Report",
            data=html_report,
            file_name=f"reddit_sentiment_{topic_used.replace(' ','_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
            mime="text/html",
            use_container_width=True,
        )