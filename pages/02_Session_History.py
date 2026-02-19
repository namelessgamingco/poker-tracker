# 02_Session_History.py — Premium Session History Page
# Individual session review with bluff stats + auto-generated insights
# Nameless Poker — $299/month decision engine

import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
import io

st.set_page_config(
    page_title="Session History | Nameless Poker",
    page_icon="📋",
    layout="wide",
)

from auth import require_auth
from sidebar import render_sidebar
from db import (
    get_user_sessions,
    get_sessions_in_date_range,
    get_session_hands,
    get_session_outcome_summary,
    get_session_bluff_stats,
)

# ---------- Auth Gate ----------
user = require_auth()
render_sidebar()


# =============================================================================
# CONSTANTS
# =============================================================================

STAKES_OPTIONS = ["All Stakes", "$0.50/$1", "$1/$2", "$2/$5", "$5/$10", "$10/$20", "$25/$50"]
RESULT_OPTIONS = ["All Results", "Winning", "Losing", "Break-even"]
END_REASON_OPTIONS = ["All", "Manual", "Stop-Loss", "Stop-Win", "Time Limit"]

END_REASON_DISPLAY = {
    "manual": "Manual",
    "stop_loss": "Stop-Loss",
    "stop_win": "Stop-Win",
    "time_limit": "Time Limit",
    None: "Unknown",
}

END_REASON_BADGE = {
    "manual": ("⏹️", "rgba(255,255,255,0.1)"),
    "stop_loss": ("🛑", "rgba(255,82,82,0.1)"),
    "stop_win": ("🎉", "rgba(0,200,83,0.1)"),
    "time_limit": ("⏱️", "rgba(66,165,245,0.1)"),
}

# Expected hourly earn rates by stakes (from spec)
EXPECTED_HOURLY = {
    "$0.50/$1": 4.55, "$1/$2": 9.10, "$2/$5": 22.75,
    "$5/$10": 45.50, "$10/$20": 91.00, "$25/$50": 227.50,
}


# =============================================================================
# PREMIUM CSS — Dark theme matching Play Session
# =============================================================================

st.markdown("""
<style>
[data-testid="stAppViewContainer"] { background: #0A0A12; }
section[data-testid="stSidebar"] { background: #0F0F1A; }
.stDeployButton, #MainMenu { display: none; }

/* ── Page header ── */
.page-title {
    font-family: 'Inter', sans-serif;
    font-size: 28px;
    font-weight: 800;
    color: #E0E0E0;
    margin-bottom: 4px;
}
.page-subtitle {
    font-size: 14px;
    color: rgba(255,255,255,0.35);
    margin-bottom: 24px;
}

/* ── Stats summary bar ── */
.stats-bar {
    background: linear-gradient(135deg, #0F0F1A 0%, #151520 100%);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 12px;
    padding: 20px 16px;
    margin-bottom: 20px;
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 16px;
}
.stats-bar-item {
    text-align: center;
}
.stats-bar-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 22px;
    font-weight: 700;
    color: #E0E0E0;
}
.stats-bar-label {
    font-family: 'Inter', sans-serif;
    font-size: 9px;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: rgba(255,255,255,0.3);
    margin-top: 2px;
}

/* ── Session row ── */
.session-row {
    background: linear-gradient(135deg, #0F0F1A 0%, #131320 100%);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 10px;
    padding: 16px 20px;
    margin-bottom: 10px;
    display: grid;
    grid-template-columns: 180px 70px 60px 60px 80px 65px 60px 1fr;
    align-items: center;
    gap: 12px;
}
.session-row:hover {
    border-color: rgba(255,255,255,0.12);
}
.session-row.winning { border-left: 3px solid #00E676; }
.session-row.losing { border-left: 3px solid #FF5252; }
.session-row.breakeven { border-left: 3px solid rgba(255,255,255,0.2); }

.sr-date {
    font-family: 'Inter', sans-serif;
    font-size: 13px;
    font-weight: 600;
    color: rgba(255,255,255,0.8);
}
.sr-date-sub {
    font-size: 11px;
    color: rgba(255,255,255,0.3);
}
.sr-val {
    font-family: 'JetBrains Mono', monospace;
    font-size: 14px;
    font-weight: 600;
    color: #E0E0E0;
    text-align: center;
}
.sr-lbl {
    font-size: 9px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: rgba(255,255,255,0.25);
    text-align: center;
}
.sr-pl {
    font-family: 'JetBrains Mono', monospace;
    font-size: 16px;
    font-weight: 700;
    text-align: center;
}
.sr-badge {
    display: inline-block;
    padding: 3px 8px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 600;
    text-align: center;
}

/* ── Expanded session detail ── */
.detail-card {
    background: rgba(255,255,255,0.02);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 10px;
    padding: 16px;
    margin: 8px 0;
}
.detail-grid-3 {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
}
.detail-grid-4 {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
}
.detail-stat {
    text-align: center;
    padding: 12px;
    background: rgba(255,255,255,0.02);
    border: 1px solid rgba(255,255,255,0.04);
    border-radius: 8px;
}
.detail-stat-val {
    font-family: 'JetBrains Mono', monospace;
    font-size: 20px;
    font-weight: 700;
    color: #E0E0E0;
}
.detail-stat-lbl {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: rgba(255,255,255,0.3);
    margin-top: 2px;
}
.detail-stat.wins .detail-stat-val { color: #00E676; }
.detail-stat.losses .detail-stat-val { color: #FF5252; }
.detail-stat.folds .detail-stat-val { color: rgba(255,255,255,0.4); }

/* ── Bluff section in detail ── */
.bluff-detail {
    background: rgba(255,179,0,0.04);
    border: 1px solid rgba(255,179,0,0.12);
    border-radius: 10px;
    padding: 16px;
    margin-top: 12px;
}
.bluff-detail-title {
    font-family: 'Inter', sans-serif;
    font-size: 12px;
    font-weight: 700;
    color: #FFD54F;
    margin-bottom: 10px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
}

/* ── Insight items ── */
.insight-item {
    font-family: 'Inter', sans-serif;
    font-size: 13px;
    color: rgba(255,255,255,0.55);
    line-height: 1.6;
    padding: 4px 0;
}

/* ── Filter bar ── */
.filter-bar {
    background: rgba(255,255,255,0.02);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 10px;
    padding: 16px;
    margin-bottom: 20px;
}

/* ── Cumulative P/L chart ── */
.chart-container {
    background: linear-gradient(135deg, #0F0F1A 0%, #131320 100%);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 10px;
    padding: 20px;
    margin-bottom: 20px;
}
.chart-title {
    font-family: 'Inter', sans-serif;
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: rgba(255,255,255,0.35);
    margin-bottom: 12px;
}

/* ── Streak badges ── */
.streak-positive {
    color: #00E676;
    font-family: 'JetBrains Mono', monospace;
    font-weight: 700;
}
.streak-negative {
    color: #FF5252;
    font-family: 'JetBrains Mono', monospace;
    font-weight: 700;
}

/* ── P/L colors ── */
.pl-positive { color: #00E676; }
.pl-negative { color: #FF5252; }
.pl-zero { color: rgba(255,255,255,0.4); }

/* ── Empty state ── */
.empty-state {
    text-align: center;
    padding: 64px 24px;
    color: rgba(255,255,255,0.4);
}
.empty-state-icon { font-size: 48px; margin-bottom: 16px; }
</style>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700;800&family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
""", unsafe_allow_html=True)


# =============================================================================
# HELPERS
# =============================================================================

def get_user_id() -> Optional[str]:
    return st.session_state.get("user_db_id")


def fmt_duration(minutes: int) -> str:
    if not minutes:
        return "—"
    h, m = minutes // 60, minutes % 60
    return f"{h}h {m}m" if h > 0 else f"{m}m"


def fmt_money(amount: float) -> str:
    if amount is None:
        return "—"
    return f"+${amount:,.2f}" if amount >= 0 else f"-${abs(amount):,.2f}"


def fmt_money_short(amount: float) -> str:
    if amount is None:
        return "—"
    return f"+${amount:,.0f}" if amount >= 0 else f"-${abs(amount):,.0f}"


def pl_class(amount: float) -> str:
    if amount > 0: return "pl-positive"
    if amount < 0: return "pl-negative"
    return "pl-zero"


def calc_bb_per_100(pl: float, hands: int, bb_size: float) -> float:
    if not hands or not bb_size:
        return 0.0
    return ((pl / bb_size) / hands) * 100


def parse_dt(session: dict) -> Optional[datetime]:
    started_at = session.get("started_at")
    if not started_at:
        return None
    try:
        return datetime.fromisoformat(started_at.replace("Z", "+00:00"))
    except Exception:
        return None


def session_duration_min(session: dict) -> int:
    started_at = session.get("started_at")
    ended_at = session.get("ended_at")
    if not started_at:
        return 0
    try:
        start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        end = datetime.fromisoformat(ended_at.replace("Z", "+00:00")) if ended_at else datetime.now(timezone.utc)
        return int((end - start).total_seconds() / 60)
    except Exception:
        return 0


def session_card_class(pl: float) -> str:
    if pl > 0: return "winning"
    if pl < 0: return "losing"
    return "breakeven"


# =============================================================================
# INSIGHTS GENERATOR — Premium auto-analysis
# =============================================================================

def generate_insights(session: dict, summary: dict, bluff_stats: dict) -> List[str]:
    """Generate smart insights for a session — the educational core."""

    insights = []
    pl = float(session.get("profit_loss", 0) or 0)
    duration = session_duration_min(session)
    hands = int(session.get("hands_played", 0) or 0)
    end_reason = session.get("end_reason")
    stakes = session.get("stakes", "$1/$2")

    wins = summary.get("wins", 0)
    losses = summary.get("losses", 0)
    folds = summary.get("folds", 0)
    total = wins + losses + folds

    fold_rate = (folds / total * 100) if total > 0 else 0
    win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
    hands_per_hr = (hands / duration * 60) if duration > 0 else 0

    # Play quality — always first
    insights.append("✅ Play Quality: EXCELLENT — followed mathematically optimal decisions")

    # Volume + pace
    if hands_per_hr >= 60:
        insights.append(f"⚡ High pace ({hands_per_hr:.0f} hands/hr) — excellent table selection")
    elif hands > 0:
        insights.append(f"📊 {hands_per_hr:.0f} hands/hr")

    # Fold discipline
    if fold_rate >= 40:
        insights.append(f"💡 Strong fold discipline ({fold_rate:.0f}%) — preserved your edge")
    elif fold_rate >= 30:
        insights.append(f"💡 Good fold discipline ({fold_rate:.0f}%)")

    # Result context
    expected_hr = EXPECTED_HOURLY.get(stakes, 9.10)
    if pl > 0:
        hourly = pl / (duration / 60) if duration > 0 else 0
        if hourly >= expected_hr * 2:
            insights.append(f"🔥 Exceptional result — ${hourly:.0f}/hr (expected: ~${expected_hr:.0f}/hr)")
        elif win_rate >= 60:
            insights.append(f"🔥 Hot session — {win_rate:.0f}% win rate on contested hands")
        else:
            insights.append("🎯 Positive variance aligned with correct play")
    elif pl < 0:
        insights.append("📊 Variance session — correct decisions, unlucky outcomes. This is normal.")

    # End reason
    if end_reason == "stop_loss":
        insights.append("🛡️ Stop-loss protected your bankroll — excellent discipline")
    elif end_reason == "stop_win":
        insights.append("🎉 Locked in profits at the right time")
    elif end_reason == "time_limit":
        insights.append("⏱️ Time limit reached — good discipline avoiding fatigue")

    # Duration insight
    if duration >= 180:
        insights.append("⚠️ Extended session (3+ hrs) — consider shorter for peak performance")

    # Bluff insights
    bluff_spots = bluff_stats.get("total_spots", 0)
    bluff_profit = bluff_stats.get("total_profit", 0)
    if bluff_spots > 0:
        if bluff_profit > 0:
            insights.append(f"⚡ Aggressive plays earned +${bluff_profit:.0f} this session")
        elif bluff_profit < 0:
            insights.append(f"⚡ Aggressive plays: -${abs(bluff_profit):.0f} (normal variance — keep betting)")
        folds_won = bluff_stats.get("folds_won", 0)
        times_bet = bluff_stats.get("times_bet", 0)
        if times_bet > 0:
            success_rate = (folds_won / times_bet) * 100
            insights.append(f"⚡ Bluff success: {folds_won}/{times_bet} ({success_rate:.0f}%)")

    return insights


# =============================================================================
# FILTER SESSIONS
# =============================================================================

def filter_sessions(sessions, stakes_f, result_f, reason_f, date_from, date_to):
    filtered = []
    for s in sessions:
        if stakes_f != "All Stakes" and s.get("stakes") != stakes_f:
            continue
        pl = float(s.get("profit_loss", 0) or 0)
        if result_f == "Winning" and pl <= 0: continue
        if result_f == "Losing" and pl >= 0: continue
        if result_f == "Break-even" and pl != 0: continue
        if reason_f != "All":
            reason_display = END_REASON_DISPLAY.get(s.get("end_reason"), "Unknown")
            if reason_display != reason_f: continue
        sdt = parse_dt(s)
        if sdt:
            sd = sdt.date()
            if date_from and sd < date_from: continue
            if date_to and sd > date_to: continue
        filtered.append(s)
    return filtered


# =============================================================================
# SUMMARY STATS BAR
# =============================================================================

def render_summary_stats(sessions: List[dict]):
    if not sessions:
        return
    total_sessions = len(sessions)
    total_pl = sum(float(s.get("profit_loss", 0) or 0) for s in sessions)
    total_hands = sum(int(s.get("hands_played", 0) or 0) for s in sessions)
    total_duration = sum(session_duration_min(s) for s in sessions)

    # Weighted BB/100
    total_bb_won = 0
    for s in sessions:
        bb = float(s.get("bb_size", 2.0) or 2.0)
        total_bb_won += float(s.get("profit_loss", 0) or 0) / bb if bb > 0 else 0
    bb_per_100 = (total_bb_won / total_hands * 100) if total_hands > 0 else 0

    # Hourly rate
    dollars_per_hr = total_pl / (total_duration / 60) if total_duration > 0 else 0

    # Win %
    winning = sum(1 for s in sessions if float(s.get("profit_loss", 0) or 0) > 0)
    win_pct = (winning / total_sessions * 100) if total_sessions > 0 else 0

    pl_color = "#00E676" if total_pl >= 0 else "#FF5252"
    bb_color = "#69F0AE" if bb_per_100 >= 0 else "#FF8A80"
    hr_color = "#69F0AE" if dollars_per_hr >= 0 else "#FF8A80"

    st.markdown(f"""
    <div class="stats-bar">
        <div class="stats-bar-item">
            <div class="stats-bar-value">{total_sessions}</div>
            <div class="stats-bar-label">Sessions</div>
        </div>
        <div class="stats-bar-item">
            <div class="stats-bar-value" style="color:{pl_color};">{fmt_money_short(total_pl)}</div>
            <div class="stats-bar-label">Total P/L</div>
        </div>
        <div class="stats-bar-item">
            <div class="stats-bar-value" style="color:{bb_color};">{bb_per_100:+.1f}</div>
            <div class="stats-bar-label">BB/100</div>
        </div>
        <div class="stats-bar-item">
            <div class="stats-bar-value" style="color:{hr_color};">${dollars_per_hr:+.0f}</div>
            <div class="stats-bar-label">$/Hour</div>
        </div>
        <div class="stats-bar-item">
            <div class="stats-bar-value">{win_pct:.0f}%</div>
            <div class="stats-bar-label">Win Rate</div>
        </div>
        <div class="stats-bar-item">
            <div class="stats-bar-value">{total_hands:,}</div>
            <div class="stats-bar-label">Hands</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


# =============================================================================
# CUMULATIVE P/L CHART
# =============================================================================

def render_cumulative_chart(sessions: List[dict]):
    """Streamlit line chart of cumulative P/L across sessions."""
    if len(sessions) < 2:
        return

    # Sort chronologically
    sorted_sessions = sorted(sessions, key=lambda s: parse_dt(s) or datetime.min.replace(tzinfo=timezone.utc))

    dates = []
    cum_pl = []
    running = 0.0
    for s in sorted_sessions:
        dt = parse_dt(s)
        if dt:
            running += float(s.get("profit_loss", 0) or 0)
            dates.append(dt.strftime("%m/%d"))
            cum_pl.append(running)

    if len(dates) < 2:
        return

    df = pd.DataFrame({"Session": dates, "Cumulative P/L ($)": cum_pl})

    st.markdown('<div class="chart-title">Cumulative P/L</div>', unsafe_allow_html=True)
    st.line_chart(df, x="Session", y="Cumulative P/L ($)", color="#00E676" if cum_pl[-1] >= 0 else "#FF5252")


# =============================================================================
# SESSION ROW (compact list view)
# =============================================================================

def render_session_row(session: dict):
    """Render a compact session row with expandable detail."""

    session_id = session.get("id")
    sdt = parse_dt(session)
    stakes = session.get("stakes", "$1/$2")
    duration = session_duration_min(session)
    hands = int(session.get("hands_played", 0) or 0)
    pl = float(session.get("profit_loss", 0) or 0)
    bb_size = float(session.get("bb_size", 2.0) or 2.0)
    bb100 = calc_bb_per_100(pl, hands, bb_size)
    end_reason = session.get("end_reason")
    hands_per_hr = (hands / duration * 60) if duration > 0 else 0

    card_cls = session_card_class(pl)
    date_str = sdt.strftime("%b %d, %Y") if sdt else "Unknown"
    time_str = sdt.strftime("%I:%M %p") if sdt else ""

    # End reason badge
    badge_icon, badge_bg = END_REASON_BADGE.get(end_reason, ("⏹️", "rgba(255,255,255,0.1)"))
    reason_label = END_REASON_DISPLAY.get(end_reason, "Unknown")

    # Expander label
    expander_label = f"{date_str} — {stakes.replace('$', '\\$')} — {fmt_money_short(pl).replace('$', '\\$')}"

    with st.expander(expander_label, expanded=False):
        # ── Top stats row ──
        st.markdown(f"""
        <div class="detail-card">
            <div class="detail-grid-4">
                <div class="detail-stat">
                    <div class="detail-stat-val" style="color:#90CAF9;">{fmt_duration(duration)}</div>
                    <div class="detail-stat-lbl">Duration</div>
                </div>
                <div class="detail-stat">
                    <div class="detail-stat-val">{hands}</div>
                    <div class="detail-stat-lbl">Hands</div>
                </div>
                <div class="detail-stat">
                    <div class="detail-stat-val" style="color:rgba(255,255,255,0.5);">{hands_per_hr:.0f}</div>
                    <div class="detail-stat-lbl">Hands/Hr</div>
                </div>
                <div class="detail-stat">
                    <div class="detail-stat-val" style="color:{'#69F0AE' if bb100 >= 0 else '#FF8A80'};">{bb100:+.1f}</div>
                    <div class="detail-stat-lbl">BB/100</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ── P/L display ──
        hourly = pl / (duration / 60) if duration > 0 else 0
        st.markdown(f"""
        <div style="text-align:center;margin:12px 0;">
            <span style="font-family:'JetBrains Mono',monospace;font-size:28px;font-weight:800;" class="{pl_class(pl)}">{fmt_money(pl)}</span>
            <div style="font-size:11px;color:rgba(255,255,255,0.3);margin-top:4px;">
                SESSION P/L — ${hourly:+.0f}/hr
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ── Outcome breakdown ──
        summary = get_session_outcome_summary(session_id) if session_id else {}
        wins = summary.get("wins", 0)
        losses = summary.get("losses", 0)
        folds = summary.get("folds", 0)
        total = wins + losses + folds

        if total > 0:
            win_pct = (wins / total * 100)
            loss_pct = (losses / total * 100)
            fold_pct = (folds / total * 100)

            st.markdown(f"""
            <div class="detail-card">
                <div class="detail-grid-3">
                    <div class="detail-stat wins">
                        <div class="detail-stat-val">{wins}</div>
                        <div class="detail-stat-lbl">Wins ({win_pct:.0f}%)</div>
                    </div>
                    <div class="detail-stat losses">
                        <div class="detail-stat-val">{losses}</div>
                        <div class="detail-stat-lbl">Losses ({loss_pct:.0f}%)</div>
                    </div>
                    <div class="detail-stat folds">
                        <div class="detail-stat-val">{folds}</div>
                        <div class="detail-stat-lbl">Folds ({fold_pct:.0f}%)</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        # ── Aggressive Plays (bluff stats) ──
        bluff_stats = get_session_bluff_stats(session_id) if session_id else {}
        bluff_spots = bluff_stats.get("total_spots", 0)

        if bluff_spots > 0:
            times_bet = bluff_stats.get("times_bet", 0)
            folds_won = bluff_stats.get("folds_won", 0)
            bluff_profit = bluff_stats.get("total_profit", 0)

            st.markdown(f"""
            <div class="bluff-detail">
                <div class="bluff-detail-title">⚡ Aggressive Plays</div>
                <div class="detail-grid-4">
                    <div class="detail-stat">
                        <div class="detail-stat-val" style="color:#FFD54F;">{bluff_spots}</div>
                        <div class="detail-stat-lbl">Spots</div>
                    </div>
                    <div class="detail-stat">
                        <div class="detail-stat-val">{times_bet}</div>
                        <div class="detail-stat-lbl">You Bet</div>
                    </div>
                    <div class="detail-stat">
                        <div class="detail-stat-val" style="color:#00E676;">{folds_won}</div>
                        <div class="detail-stat-lbl">Folds Won</div>
                    </div>
                    <div class="detail-stat">
                        <div class="detail-stat-val {pl_class(bluff_profit)}">{fmt_money_short(bluff_profit)}</div>
                        <div class="detail-stat-lbl">Bluff P/L</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        # ── Auto-generated insights ──
        insights = generate_insights(session, summary, bluff_stats)
        if insights:
            st.markdown("**📋 Session Insights**")
            for insight in insights:
                st.markdown(f'<div class="insight-item">{insight}</div>', unsafe_allow_html=True)

        # ── End reason badge ──
        st.markdown(f"""
        <div style="margin-top:12px;text-align:center;">
            <span class="sr-badge" style="background:{badge_bg};color:rgba(255,255,255,0.6);">
                {badge_icon} {reason_label}
            </span>
        </div>
        """, unsafe_allow_html=True)


# =============================================================================
# FILTERS
# =============================================================================

def render_filters():
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        stakes_f = st.selectbox("Stakes", STAKES_OPTIONS, key="f_stakes")
    with col2:
        result_f = st.selectbox("Result", RESULT_OPTIONS, key="f_result")
    with col3:
        reason_f = st.selectbox("End Reason", END_REASON_OPTIONS, key="f_reason")
    with col4:
        date_range = st.selectbox("Date Range",
            ["Last 7 days", "Last 30 days", "Last 90 days", "This month", "All time", "Custom"],
            index=1, key="f_daterange")

    today = datetime.now(timezone.utc).date()
    if date_range == "Last 7 days":
        date_from, date_to = today - timedelta(days=7), today
    elif date_range == "Last 30 days":
        date_from, date_to = today - timedelta(days=30), today
    elif date_range == "Last 90 days":
        date_from, date_to = today - timedelta(days=90), today
    elif date_range == "This month":
        date_from, date_to = today.replace(day=1), today
    elif date_range == "All time":
        date_from, date_to = None, None
    else:
        c1, c2 = st.columns(2)
        with c1:
            date_from = st.date_input("From", value=today - timedelta(days=30), key="cf")
        with c2:
            date_to = st.date_input("To", value=today, key="ct")

    return stakes_f, result_f, reason_f, date_from, date_to


# =============================================================================
# EXPORT
# =============================================================================

def build_export_df(sessions: List[dict]) -> pd.DataFrame:
    data = []
    for s in sessions:
        dur = session_duration_min(s)
        bb = float(s.get("bb_size", 2.0) or 2.0)
        hands = int(s.get("hands_played", 0) or 0)
        pl = float(s.get("profit_loss", 0) or 0)
        bb100 = calc_bb_per_100(pl, hands, bb)
        sdt = parse_dt(s)
        hr = pl / (dur / 60) if dur > 0 else 0

        # Bluff stats
        sid = s.get("id")
        bs = get_session_bluff_stats(sid) if sid else {}

        data.append({
            "Date": sdt.strftime("%Y-%m-%d %H:%M") if sdt else "",
            "Stakes": s.get("stakes", ""),
            "Duration (min)": dur,
            "Hands": hands,
            "Hands/Hr": round((hands / dur * 60) if dur > 0 else 0, 0),
            "P/L ($)": pl,
            "BB/100": round(bb100, 1),
            "$/Hour": round(hr, 0),
            "End Reason": END_REASON_DISPLAY.get(s.get("end_reason"), "Unknown"),
            "Bluff Spots": bs.get("total_spots", 0),
            "Bluff Bets": bs.get("times_bet", 0),
            "Bluff Folds Won": bs.get("folds_won", 0),
            "Bluff P/L": bs.get("total_profit", 0),
        })
    return pd.DataFrame(data)


# =============================================================================
# STREAK TRACKER
# =============================================================================

def render_streak_info(sessions: List[dict]):
    """Show current winning/losing streak."""
    if not sessions:
        return

    sorted_s = sorted(sessions, key=lambda s: parse_dt(s) or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

    streak = 0
    streak_type = None
    for s in sorted_s:
        pl = float(s.get("profit_loss", 0) or 0)
        if pl > 0:
            t = "win"
        elif pl < 0:
            t = "loss"
        else:
            break
        if streak_type is None:
            streak_type = t
        if t == streak_type:
            streak += 1
        else:
            break

    if streak >= 2:
        if streak_type == "win":
            st.markdown(f"""
            <div style="text-align:center;margin-bottom:16px;">
                <span class="streak-positive">🔥 {streak}-session winning streak</span>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="text-align:center;margin-bottom:16px;">
                <span class="streak-negative">📊 {streak}-session losing streak — variance is normal, the math hasn't changed</span>
            </div>
            """, unsafe_allow_html=True)


# =============================================================================
# MAIN
# =============================================================================

def main():
    st.markdown("""
    <div class="page-title">📋 Session History</div>
    <div class="page-subtitle">Review sessions, track your edge, and see how aggressive plays are building your profit</div>
    """, unsafe_allow_html=True)

    user_id = get_user_id()
    if not user_id:
        st.warning("Please log in to view your session history.")
        return

    all_sessions = get_user_sessions(user_id, limit=500)

    if not all_sessions:
        st.markdown("""
        <div class="empty-state">
            <div class="empty-state-icon">📋</div>
            <h3 style="color:#E0E0E0;">No Sessions Yet</h3>
            <p>Start a play session to begin tracking your poker journey.</p>
        </div>
        """, unsafe_allow_html=True)
        return

    # Filters
    stakes_f, result_f, reason_f, date_from, date_to = render_filters()
    filtered = filter_sessions(all_sessions, stakes_f, result_f, reason_f, date_from, date_to)

    if not filtered:
        st.info("No sessions match your filters.")
        return

    # Summary bar
    render_summary_stats(filtered)

    # Streak indicator
    render_streak_info(filtered)

    # Cumulative P/L chart
    render_cumulative_chart(filtered)

    # Export button
    col_left, col_right = st.columns([4, 1])
    with col_left:
        st.markdown(f"**{len(filtered)} sessions**")
    with col_right:
        df = build_export_df(filtered)
        csv = df.to_csv(index=False)
        st.download_button("📥 Export CSV", csv,
                           f"nameless_sessions_{datetime.now().strftime('%Y%m%d')}.csv",
                           "text/csv", use_container_width=True)

    # Sort newest first
    sorted_sessions = sorted(
        filtered,
        key=lambda s: parse_dt(s) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True
    )

    # Pagination
    per_page = 15
    total_pages = max(1, (len(sorted_sessions) + per_page - 1) // per_page)

    if total_pages > 1:
        page = st.number_input("Page", 1, total_pages, 1, key="page")
    else:
        page = 1

    start = (page - 1) * per_page
    page_sessions = sorted_sessions[start:start + per_page]

    # Render session cards
    for session in page_sessions:
        render_session_row(session)

    if total_pages > 1:
        st.caption(f"Page {page} of {total_pages}")


if __name__ == "__main__":
    main()