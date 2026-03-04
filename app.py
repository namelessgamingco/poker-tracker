# app.py — NAMELESS POKER Home

import streamlit as st

st.set_page_config(
    page_title="NAMELESS POKER",
    page_icon="🃏",
    layout="wide",
    initial_sidebar_state="expanded",
)

from auth import require_auth
from sidebar import render_sidebar

user = require_auth()
render_sidebar()

# =============================================================================
# CSS
# =============================================================================

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700;800&family=Inter:wght@400;500;600;700;800&family=DM+Sans:wght@400;500;600;700&display=swap');

[data-testid="stAppViewContainer"] { background: #0A0A12; }
.block-container { max-width: 1100px; }

/* Hero */
.home-hero {
    background: linear-gradient(160deg, #0c1220 0%, #0F0F1A 40%, #111825 100%);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 20px;
    padding: 48px 40px;
    text-align: center;
    position: relative;
    overflow: hidden;
    margin-bottom: 32px;
}
.home-hero::before {
    content: '';
    position: absolute;
    top: -60%;
    right: -15%;
    width: 500px;
    height: 500px;
    background: radial-gradient(circle, rgba(105,240,174,0.06) 0%, transparent 65%);
    pointer-events: none;
}
.home-hero::after {
    content: '';
    position: absolute;
    bottom: -40%;
    left: -10%;
    width: 400px;
    height: 400px;
    background: radial-gradient(circle, rgba(66,165,245,0.04) 0%, transparent 65%);
    pointer-events: none;
}
.home-hero-title {
    font-family: 'JetBrains Mono', monospace;
    font-size: 32px;
    font-weight: 800;
    letter-spacing: 0.08em;
    color: #E0E0E0;
    margin-bottom: 12px;
}
.home-hero-sub {
    font-family: 'Inter', sans-serif;
    font-size: 17px;
    color: rgba(255,255,255,0.45);
    line-height: 1.7;
    max-width: 560px;
    margin: 0 auto 28px auto;
}
.home-hero-stat-row {
    display: flex;
    justify-content: center;
    gap: 40px;
    margin-top: 24px;
}
.home-hero-stat {
    text-align: center;
}
.home-hero-stat-num {
    font-family: 'JetBrains Mono', monospace;
    font-size: 24px;
    font-weight: 700;
}
.home-hero-stat-lbl {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: rgba(255,255,255,0.3);
    margin-top: 2px;
}

/* Session card */
.session-cta {
    background: linear-gradient(135deg, #0F0F1A 0%, #151520 100%);
    border: 1px solid rgba(105,240,174,0.2);
    border-radius: 14px;
    padding: 24px;
    margin-bottom: 28px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 20px;
}
.session-cta-info {
    flex: 1;
}
.session-cta-title {
    font-family: 'JetBrains Mono', monospace;
    font-size: 15px;
    font-weight: 700;
    color: #69F0AE;
    margin-bottom: 4px;
}
.session-cta-desc {
    font-size: 13px;
    color: rgba(255,255,255,0.4);
    line-height: 1.5;
}
.session-cta-inactive {
    border-color: rgba(66,165,245,0.2);
}
.session-cta-inactive .session-cta-title {
    color: #42A5F5;
}

/* Getting started */
.gs-card {
    background: linear-gradient(135deg, #0F0F1A 0%, #151520 100%);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 10px;
}
.gs-card-done {
    border-color: rgba(105,240,174,0.15);
    background: linear-gradient(135deg, rgba(105,240,174,0.03) 0%, #0F0F1A 100%);
}
.gs-row {
    display: flex;
    align-items: center;
    gap: 14px;
}
.gs-check {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    flex-shrink: 0;
}
.gs-check-done {
    background: rgba(105,240,174,0.15);
    color: #69F0AE;
}
.gs-check-todo {
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.1);
    color: rgba(255,255,255,0.2);
}
.gs-title {
    font-size: 14px;
    font-weight: 600;
    color: #E0E0E0;
}
.gs-title-done {
    color: rgba(255,255,255,0.4);
}
.gs-desc {
    font-size: 12px;
    color: rgba(255,255,255,0.35);
    margin-top: 2px;
}

/* Performance card */
.perf-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin-bottom: 28px;
}
.perf-card {
    background: linear-gradient(135deg, #0F0F1A 0%, #151520 100%);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 12px;
    padding: 18px 16px;
    text-align: center;
}
.perf-num {
    font-family: 'JetBrains Mono', monospace;
    font-size: 20px;
    font-weight: 700;
    color: #E0E0E0;
}
.perf-lbl {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: rgba(255,255,255,0.3);
    margin-top: 4px;
}

/* Nav cards */
.nav-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 14px;
    margin-top: 20px;
}
.nav-card {
    background: linear-gradient(145deg, #0F0F1A 0%, #1a1a2e 100%);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 14px;
    padding: 24px 20px;
    text-align: center;
    transition: border-color 0.2s ease, transform 0.2s ease;
    cursor: default;
}
.nav-card:hover {
    border-color: rgba(255,255,255,0.12);
}
.nav-card-icon {
    font-size: 32px;
    margin-bottom: 12px;
}
.nav-card-title {
    font-size: 15px;
    font-weight: 700;
    color: #E0E0E0;
    margin-bottom: 6px;
}
.nav-card-desc {
    font-size: 12px;
    color: rgba(255,255,255,0.35);
    line-height: 1.6;
}

/* Section header */
.sec-header {
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 0.06em;
    color: rgba(255,255,255,0.3);
    text-transform: uppercase;
    margin: 32px 0 16px 0;
}
</style>
""", unsafe_allow_html=True)


# =============================================================================
# DATA
# =============================================================================

from db import get_today_stats, get_active_session, get_player_stats, get_user_sessions

user_db_id = st.session_state.get("user_db_id", "")
email = st.session_state.get("email", "")
current_bankroll = st.session_state.get("current_bankroll", 0)
subscription_status = st.session_state.get("subscription_status", "active")

# Fetch data
active_session = get_active_session(user_db_id) if user_db_id else None
today = get_today_stats(user_db_id) if user_db_id else {}
stats = get_player_stats(user_db_id) if user_db_id else {}
recent_sessions = get_user_sessions(user_db_id, limit=5) if user_db_id else []

total_hands = stats.get("total_hands", 0)
total_sessions = stats.get("total_sessions", 0)
total_pl = stats.get("total_profit_loss", 0)
win_rate = stats.get("win_rate_bb_100", 0)
total_hours = stats.get("total_hours", 0)
winning_sessions = stats.get("winning_sessions", 0)

is_new_user = not st.session_state.get("onboarding_dismissed", False)


# =============================================================================
# HERO
# =============================================================================

# Subscription warning
if subscription_status == "grace_period":
    st.warning("⚠️ Your payment is overdue. Update your payment method to keep access.")

# P/L formatting for hero
pl_color = "#69F0AE" if total_pl >= 0 else "#FF5252"
pl_sign = "+" if total_pl >= 0 else ""
wr_color = "#69F0AE" if win_rate >= 0 else "#FF5252"
wr_sign = "+" if win_rate >= 0 else ""

hero_stats = ""
if total_sessions > 0:
    hero_stats = f'<div class="home-hero-stat-row"><div class="home-hero-stat"><div class="home-hero-stat-num" style="color: {pl_color}">{pl_sign}${total_pl:,.0f}</div><div class="home-hero-stat-lbl">Total P/L</div></div><div class="home-hero-stat"><div class="home-hero-stat-num" style="color: {wr_color}">{wr_sign}{win_rate}</div><div class="home-hero-stat-lbl">BB/100</div></div><div class="home-hero-stat"><div class="home-hero-stat-num">{total_hands:,}</div><div class="home-hero-stat-lbl">Hands</div></div><div class="home-hero-stat"><div class="home-hero-stat-num">{total_hours}</div><div class="home-hero-stat-lbl">Hours</div></div></div>'

st.markdown(f"""
<div class="home-hero">
    <div class="home-hero-title">NAMELESS POKER</div>
    <div class="home-hero-sub">One answer. No thinking required. The engine tells you exactly what to do — you just execute.</div>
    {hero_stats}
</div>
""", unsafe_allow_html=True)


# =============================================================================
# SESSION CTA
# =============================================================================

if active_session:
    stakes = active_session.get("stakes", "$1/$2")
    if not stakes.startswith("$"):
        stakes = f"${stakes}"
    session_pl = st.session_state.get("session_pl", 0)
    pl_s = f"+${session_pl:.0f}" if session_pl >= 0 else f"-${abs(session_pl):.0f}"
    st.markdown(f"""
    <div class="session-cta">
        <div class="session-cta-info">
            <div class="session-cta-title">📍 SESSION ACTIVE — {stakes}</div>
            <div class="session-cta-desc">Session P/L: {pl_s} · Pick up where you left off</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("▶️ Continue Session", type="primary", use_container_width=True):
        st.switch_page("pages/01_Play_Session.py")
else:
    st.markdown("""
    <div class="session-cta session-cta-inactive">
        <div class="session-cta-info">
            <div class="session-cta-title">READY TO PLAY</div>
            <div class="session-cta-desc">Start a session to get real-time decisions at the table</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("▶️ Start New Session", type="primary", use_container_width=True):
        st.switch_page("pages/01_Play_Session.py")


# =============================================================================
# NEW USER: GETTING STARTED
# =============================================================================

if is_new_user:
    st.markdown('<div class="sec-header">Getting Started</div>', unsafe_allow_html=True)

    has_bankroll = current_bankroll and current_bankroll > 0
    has_session = total_sessions > 0
    has_10_hands = total_hands >= 10
    has_reviewed_stats = total_sessions >= 3
    # Track page visits via session state (set by each page)
    visited_how_it_works = st.session_state.get("visited_how_it_works", False)
    visited_ev_system = st.session_state.get("visited_ev_system", False)
    visited_master = st.session_state.get("visited_master", False)
    visited_bankroll = st.session_state.get("visited_bankroll", False)
    visited_settings = st.session_state.get("visited_settings", False)

    steps = [
        {
            "done": True,
            "title": "Create your account",
            "desc": "You're in. Welcome to Nameless Poker.",
        },
        {
            "done": visited_how_it_works,
            "title": "Read How It Works",
            "desc": "Understand the 5-step flow — cards, decision, continue, record, review. This is your playbook.",
            "page": "pages/06_How_It_Works.py",
            "btn": "📖 Open How It Works",
        },
        {
            "done": visited_ev_system,
            "title": "Understand the EV System",
            "desc": "Learn why every decision is +EV, how rakeback covers your subscription, and what your expected earnings look like.",
            "page": "pages/07_EV_System.py",
            "btn": "📐 Open EV System",
        },
        {
            "done": has_bankroll,
            "title": "Set up your bankroll",
            "desc": "Go to Bankroll Health and enter your bankroll. Learn why proper bankroll management is the difference between going broke and grinding up.",
            "page": "pages/04_Bankroll_Health.py",
            "btn": "💰 Open Bankroll Health",
        },
        {
            "done": has_session,
            "title": "Play your first session",
            "desc": "Start a session, follow every decision the app gives you. Don't second-guess it — just execute.",
            "page": "pages/01_Play_Session.py",
            "btn": "🎯 Start Session",
        },
        {
            "done": has_10_hands,
            "title": "Complete 10+ hands",
            "desc": "The app tracks your results hand by hand. Play at least 10 to start seeing meaningful data.",
        },
        {
            "done": visited_master,
            "title": "Study Master Your Play",
            "desc": "Deep dive into position strategy, bluff math, and the mistakes that cost most players money.",
            "page": "pages/08_Master_Your_Play.py",
            "btn": "🎓 Open Master Your Play",
        },
        {
            "done": visited_settings,
            "title": "Configure your settings",
            "desc": "Set your default stakes, risk mode, and session preferences. Dial in the app to match your game.",
            "page": "pages/05_Settings.py",
            "btn": "⚙️ Open Settings",
        },
        {
            "done": has_reviewed_stats,
            "title": "Review your results after 3 sessions",
            "desc": "Check Player Stats and Session History to see your win rate, patterns, and progress over time.",
            "page": "pages/03_Player_Stats.py",
            "btn": "📈 Open Player Stats",
        },
    ]

    completed = sum(1 for s in steps if s["done"])

    # DEBUG - remove after testing
    st.write("DEBUG:", {
        "sub_status": st.session_state.get("subscription_status", ""),
        "is_trial": st.session_state.get("is_trial", False),
        "trial_ends_at": st.session_state.get("trial_ends_at"),
    })

    # Trial urgency banner
    sub_status = st.session_state.get("subscription_status", "")
    trial_ends_at = st.session_state.get("trial_ends_at")
    is_trial = st.session_state.get("is_trial", False)
    if (sub_status == "trial" or is_trial) and trial_ends_at:
        try:
            from datetime import datetime, timezone
            if isinstance(trial_ends_at, str):
                ends_dt = datetime.fromisoformat(trial_ends_at.replace("Z", "+00:00"))
            else:
                ends_dt = trial_ends_at
            days_left = max(0, (ends_dt - datetime.now(timezone.utc)).days)
            if days_left <= 3:
                trial_color = "rgba(255,82,82,0.08)"
                trial_border = "rgba(255,82,82,0.2)"
                trial_text = f"⏰ <strong>{days_left} day{'s' if days_left != 1 else ''} left</strong> on your free trial — complete the steps below to see real results before it ends."
            else:
                trial_color = "rgba(105,240,174,0.06)"
                trial_border = "rgba(105,240,174,0.15)"
                trial_text = f"🎁 You have <strong>{days_left} days</strong> of free access. Follow the quickstart below to see how the app pays for itself."
            st.markdown(f"""
            <div style="background:{trial_color};border:1px solid {trial_border};border-radius:10px;padding:12px 16px;margin-bottom:16px;">
                <div style="font-size:13px;color:rgba(255,255,255,0.7);">{trial_text}</div>
            </div>
            """, unsafe_allow_html=True)
        except Exception:
            pass

    st.markdown(f"""
    <div style="font-size: 13px; color: rgba(255,255,255,0.4); margin-bottom: 12px;">
        {completed} of {len(steps)} complete
        <div style="background: rgba(255,255,255,0.06); border-radius: 4px; height: 4px; margin-top: 6px; overflow: hidden;">
            <div style="background: #69F0AE; height: 100%; width: {(completed / len(steps)) * 100}%; border-radius: 4px; transition: width 0.3s ease;"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    for i, s in enumerate(steps):
        done_class = "gs-card-done" if s["done"] else ""
        check_class = "gs-check-done" if s["done"] else "gs-check-todo"
        check_icon = "✓" if s["done"] else str(i + 1)
        title_class = "gs-title-done" if s["done"] else ""

        st.markdown(f"""
        <div class="gs-card {done_class}">
            <div class="gs-row">
                <div class="gs-check {check_class}">{check_icon}</div>
                <div>
                    <div class="gs-title {title_class}">{s['title']}</div>
                    <div class="gs-desc">{s['desc']}</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Show action button for the first incomplete step only
        if not s["done"] and s.get("page"):
            if st.button(s["btn"], use_container_width=True, key=f"gs_{i}"):
                st.switch_page(s["page"])
            break  # Only show one action button at a time

    # Dismiss button once everything is done
    if completed == len(steps):
        st.success("🎉 You've completed the full onboarding. You're ready to grind.")
        if st.button("✅ Dismiss Getting Started", use_container_width=True):
            st.session_state.onboarding_dismissed = True
            st.rerun()


# =============================================================================
# RETURNING USER: PERFORMANCE SNAPSHOT
# =============================================================================

if not is_new_user and total_sessions > 0:
    st.markdown('<div class="sec-header">Your Numbers</div>', unsafe_allow_html=True)

    win_pct = round((winning_sessions / total_sessions) * 100) if total_sessions > 0 else 0

    today_pl = today.get("profit_loss", 0)
    today_pl_color = "#69F0AE" if today_pl >= 0 else "#FF5252"
    today_pl_sign = "+" if today_pl >= 0 else ""
    today_sessions_count = today.get("sessions", 0)

    st.markdown(f"""
    <div class="perf-grid">
        <div class="perf-card">
            <div class="perf-num" style="color: {today_pl_color}">{today_pl_sign}${today_pl:,.0f}</div>
            <div class="perf-lbl">Today ({today_sessions_count} sessions)</div>
        </div>
        <div class="perf-card">
            <div class="perf-num" style="color: {wr_color}">{wr_sign}{win_rate}</div>
            <div class="perf-lbl">BB/100</div>
        </div>
        <div class="perf-card">
            <div class="perf-num">{win_pct}%</div>
            <div class="perf-lbl">Win Rate</div>
        </div>
        <div class="perf-card">
            <div class="perf-num">{total_sessions}</div>
            <div class="perf-lbl">Sessions</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Last session summary
    if recent_sessions:
        last = recent_sessions[0]
        last_pl = float(last.get("profit_loss", 0) or 0)
        last_hands = last.get("hands_played", 0) or 0
        last_stakes = last.get("stakes", "$1/$2")
        if not last_stakes.startswith("$"):
            last_stakes = f"${last_stakes}"
        last_pl_color = "#69F0AE" if last_pl >= 0 else "#FF5252"
        last_pl_sign = "+" if last_pl >= 0 else ""
        last_duration = last.get("duration_minutes", 0) or 0
        last_hrs = last_duration // 60
        last_mins = last_duration % 60

        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #0F0F1A 0%, #151520 100%); border: 1px solid rgba(255,255,255,0.06); border-radius: 12px; padding: 16px 20px; margin-bottom: 28px;">
            <div style="font-size: 11px; color: rgba(255,255,255,0.3); text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 8px;">Last Session</div>
            <div style="display: flex; align-items: center; gap: 20px;">
                <span style="font-family: 'JetBrains Mono', monospace; font-size: 18px; font-weight: 700; color: {last_pl_color};">{last_pl_sign}${abs(last_pl):,.0f}</span>
                <span style="color: rgba(255,255,255,0.2);">·</span>
                <span style="font-size: 13px; color: rgba(255,255,255,0.45);">{last_stakes}</span>
                <span style="color: rgba(255,255,255,0.2);">·</span>
                <span style="font-size: 13px; color: rgba(255,255,255,0.45);">{last_hands} hands</span>
                <span style="color: rgba(255,255,255,0.2);">·</span>
                <span style="font-size: 13px; color: rgba(255,255,255,0.45);">{last_hrs}h {last_mins}m</span>
            </div>
        </div>
        """, unsafe_allow_html=True)


# =============================================================================
# LEARN & EXPLORE
# =============================================================================

st.markdown('<div class="sec-header">Learn &amp; Explore</div>', unsafe_allow_html=True)

st.markdown("""
<div class="nav-grid">
    <div class="nav-card">
        <div class="nav-card-icon">📖</div>
        <div class="nav-card-title">How It Works</div>
        <div class="nav-card-desc">The 5-step flow from cards to decision. Understand how the engine thinks and what every recommendation means.</div>
    </div>
    <div class="nav-card">
        <div class="nav-card-icon">📐</div>
        <div class="nav-card-title">EV System</div>
        <div class="nav-card-desc">The math behind the app. Expected value, rakeback projections, and why $299/month pays for itself at every stake.</div>
    </div>
    <div class="nav-card">
        <div class="nav-card-icon">🎓</div>
        <div class="nav-card-title">Master Your Play</div>
        <div class="nav-card-desc">Go deeper on strategy. Position play, bluff math, bankroll management, and common mistakes that cost you money.</div>
    </div>
</div>
""", unsafe_allow_html=True)

# Clickable buttons below cards (Streamlit can't make HTML divs clickable)
c1, c2, c3 = st.columns(3)
with c1:
    if st.button("📖 How It Works", use_container_width=True, key="nav_how"):
        st.switch_page("pages/06_How_It_Works.py")
with c2:
    if st.button("📐 EV System", use_container_width=True, key="nav_ev"):
        st.switch_page("pages/07_EV_System.py")
with c3:
    if st.button("🎓 Master Your Play", use_container_width=True, key="nav_master"):
        st.switch_page("pages/08_Master_Your_Play.py")


# =============================================================================
# FOOTER
# =============================================================================

st.markdown("---")
st.markdown("""
<div style="text-align: center; padding: 12px 0;">
    <div style="font-family: 'JetBrains Mono', monospace; font-size: 11px; color: rgba(255,255,255,0.2); letter-spacing: 0.05em;">
        NAMELESS POKER v1.0 · Texas Hold'em NL 6-Max Cash
    </div>
</div>
""", unsafe_allow_html=True)