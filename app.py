# app.py — Poker Decision App Main Entry Point

import streamlit as st

st.set_page_config(
    page_title="Poker Decision App",
    page_icon="🃏",
    layout="centered",
    initial_sidebar_state="expanded",
)

from auth import require_auth
from sidebar import render_sidebar

# ---------- Auth Gate ----------
# This runs on every page load - user must be logged in
user = require_auth()

# ---------- Render Sidebar ----------
render_sidebar()

# ---------- Main Content ----------
st.title("🃏 Poker Decision App")

# Get user info from session state
email = st.session_state.get("email", "")
role = st.session_state.get("role", "player")
subscription_status = st.session_state.get("subscription_status", "active")

# Welcome message
st.markdown(f"Welcome back, **{email}**")

# Show subscription warning if in grace period
if subscription_status == "grace_period":
    st.warning(
        "⚠️ Your payment is overdue. Please update your payment method to avoid losing access.",
        icon="⚠️"
    )

# ---------- Quick Stats ----------
st.markdown("---")

# Load actual data
from db import get_today_stats, get_active_session

user_db_id = st.session_state.get("user_db_id", "")
today = get_today_stats(user_db_id) if user_db_id else {}
active_session = get_active_session(user_db_id) if user_db_id else None
current_bankroll = st.session_state.get("current_bankroll", 0)

col1, col2, col3 = st.columns(3)

with col1:
    if active_session:
        st.metric(
            label="Session Status",
            value="🟢 Active",
            help="You have an active session"
        )
    else:
        st.metric(
            label="Session Status",
            value="No Active Session",
            help="Start a session to begin tracking"
        )

with col2:
    pl = today.get("profit_loss", 0)
    pl_str = f"+${pl:.2f}" if pl >= 0 else f"-${abs(pl):.2f}"
    st.metric(
        label="Today's P/L",
        value=pl_str,
        help="Profit/loss from today's sessions"
    )

with col3:
    if current_bankroll and current_bankroll > 0:
        st.metric(
            label="Bankroll",
            value=f"${current_bankroll:,.0f}",
            help="Your current bankroll"
        )
    else:
        st.metric(
            label="Bankroll Health",
            value="—",
            help="Set up your bankroll in settings"
        )

# ---------- Quick Actions ----------
st.markdown("---")
st.subheader("Quick Actions")

col1, col2 = st.columns(2)

with col1:
    if st.button("▶️ Start New Session", type="primary", use_container_width=True):
        st.switch_page("pages/01_Play_Session.py")

with col2:
    if st.button("📊 View Stats", use_container_width=True):
        st.switch_page("pages/03_Player_Stats.py")

# ---------- App Philosophy ----------
st.markdown("---")
st.markdown(
    """
    ### How This App Works
    
    **One answer. No thinking required.**
    
    This app tells you exactly what to do in every poker situation:
    - **"RAISE TO $12"** — not "consider raising"
    - **"FOLD"** — not "this is a close spot"
    - **"CALL $25"** — exact amounts, every time
    
    The math is done. Just follow the app.
    
    **Expected results with 100% compliance:**
    - Win rate: +6-7 BB/100
    - At $1/$2: ~$20,000-24,000/year
    """
)

# ---------- Footer ----------
st.markdown("---")
st.caption(
    "Poker Decision App v1.0 • "
    "Texas Hold'em No-Limit 6-Max Cash Games • "
    "[How It Works](pages/06_How_It_Works.py)"
)