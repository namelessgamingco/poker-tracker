# 01_Play_Session.py — Premium Play Session Page
# React component integration + bluff tracking + live session timer
# Nameless Poker — $299/month decision engine

import streamlit as st
import html as _html
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

st.set_page_config(
    page_title="Play Session | Nameless Poker",
    page_icon="🎯",
    layout="wide",
)

from auth import require_auth
from sidebar import render_sidebar, update_sidebar_session_info, clear_sidebar_session_info
from db import (
    get_profile_by_auth_id,
    create_session,
    get_active_session,
    update_session,
    increment_session_stats,
    end_session,
    update_user_bankroll,
    record_bankroll_change,
    get_stakes_options,
    get_stakes_info,
    record_hand_outcome,
    get_session_outcome_summary,
    update_session_bluff_stats,
    get_session_bluff_stats,
)
from engine import (
    get_decision,
    decision_to_dict,
    Action,
    HandStrength,
    BoardTexture,
    BluffContext,
    classify_preflop_hand,
    normalize_hand,
)
from poker_input import poker_input

# ---------- Auth Gate ----------
user = require_auth()
render_sidebar()


# =============================================================================
# CONSTANTS
# =============================================================================

MODE_CONFIG = {
    "aggressive": {"buy_ins": 13, "stop_loss_bi": 0.75, "stop_win_bi": 3.0, "label": "Aggressive"},
    "balanced":   {"buy_ins": 15, "stop_loss_bi": 1.0,  "stop_win_bi": 3.0, "label": "Balanced"},
    "conservative": {"buy_ins": 17, "stop_loss_bi": 1.25, "stop_win_bi": 3.0, "label": "Conservative"},
}

STAKES_BUY_INS = {
    "$0.50/$1": {"bb": 1.0,  "buy_in": 100},
    "$1/$2":    {"bb": 2.0,  "buy_in": 200},
    "$2/$5":    {"bb": 5.0,  "buy_in": 500},
    "$5/$10":   {"bb": 10.0, "buy_in": 1000},
    "$10/$20":  {"bb": 20.0, "buy_in": 2000},
    "$25/$50":  {"bb": 50.0, "buy_in": 5000},
}

# Expected hourly earn rates by stakes (from spec: ~6.5 BB/100, 70 hands/hr)
EXPECTED_HOURLY = {
    "$0.50/$1": 4.55, "$1/$2": 9.10, "$2/$5": 22.75,
    "$5/$10": 45.50, "$10/$20": 91.00, "$25/$50": 227.50,
}

# Approximate losing session frequency (from simulation data, balanced mode)
LOSING_SESSION_PCT = 38  # ~38% of sessions are losing even at +6 BB/100

# Session time thresholds (minutes)
TIME_OPTIMAL = 90
TIME_WARNING = 180
TIME_HARD_STOP = 240

# Table check interval (minutes)
TABLE_CHECK_INTERVAL = 20

# Tilt detection thresholds
TILT_LOSS_STREAK = 3           # Consecutive losses before tilt banner
TILT_STOP_LOSS_PCT = 0.75      # 75% of stop-loss before tilt banner


# =============================================================================
# PREMIUM CSS
# =============================================================================

st.markdown("""
<style>
/* ── Global overrides ── */
[data-testid="stAppViewContainer"] { background: #0A0A12; }
section[data-testid="stSidebar"] { background: #0F0F1A; }

/* ── Session header bar ── */
.session-bar {
    background: linear-gradient(135deg, #0F0F1A 0%, #151520 100%);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 12px;
    padding: 16px 20px;
    margin-bottom: 16px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
}
.session-stat {
    text-align: center;
    flex: 1;
}
.session-stat-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 22px;
    font-weight: 700;
    letter-spacing: 0.02em;
}
.session-stat-label {
    font-family: 'Inter', sans-serif;
    font-size: 10px;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: rgba(255,255,255,0.35);
    margin-top: 2px;
}
.session-stat-divider {
    width: 1px;
    height: 36px;
    background: rgba(255,255,255,0.06);
}

/* ── Live timer ── */
.timer-live {
    font-family: 'JetBrains Mono', monospace;
    font-size: 22px;
    font-weight: 700;
    color: #E0E0E0;
}
.timer-dot {
    display: inline-block;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #00C853;
    margin-right: 8px;
    animation: pulse-dot 2s ease-in-out infinite;
}
@keyframes pulse-dot {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.3; }
}

/* ── P/L display ── */
.pl-positive { color: #00E676; }
.pl-negative { color: #FF5252; }
.pl-zero { color: rgba(255,255,255,0.5); }

/* ── Alert banners ── */
.alert-banner {
    padding: 12px 16px;
    border-radius: 10px;
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    gap: 12px;
    font-family: 'Inter', sans-serif;
    font-size: 13px;
    line-height: 1.5;
}
.alert-banner.danger {
    background: rgba(255,82,82,0.08);
    border: 1px solid rgba(255,82,82,0.25);
    color: #FF8A80;
}
.alert-banner.warning {
    background: rgba(255,179,0,0.06);
    border: 1px solid rgba(255,179,0,0.2);
    color: #FFD54F;
}
.alert-banner.info {
    background: rgba(66,165,245,0.06);
    border: 1px solid rgba(66,165,245,0.2);
    color: #90CAF9;
}
.alert-banner.success {
    background: rgba(0,200,83,0.06);
    border: 1px solid rgba(0,200,83,0.2);
    color: #69F0AE;
}
.alert-banner.mental {
    background: rgba(171,71,188,0.06);
    border: 1px solid rgba(171,71,188,0.2);
    color: #CE93D8;
}
.alert-banner .alert-icon { font-size: 20px; flex-shrink: 0; }
.alert-banner .alert-title { font-weight: 700; }

/* ── Table check button ── */
.table-check-btn {
    background: rgba(255,179,0,0.06);
    border: 1px solid rgba(255,179,0,0.2);
    border-radius: 10px;
    padding: 10px 16px;
    color: #FFD54F;
    font-family: 'Inter', sans-serif;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    text-align: center;
    margin-bottom: 12px;
    transition: all 0.15s ease;
}
.table-check-btn:hover {
    background: rgba(255,179,0,0.1);
    border-color: rgba(255,179,0,0.35);
}

/* ── Outcome modal ── */
.outcome-card {
    background: linear-gradient(135deg, #0F0F1A 0%, #151520 100%);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 14px;
    padding: 28px 24px;
    margin: 16px 0;
}
.outcome-title {
    font-family: 'Inter', sans-serif;
    font-size: 22px;
    font-weight: 800;
    text-align: center;
    margin-bottom: 16px;
    color: #E0E0E0;
}
.outcome-message {
    font-family: 'Inter', sans-serif;
    font-size: 14px;
    line-height: 1.7;
    color: rgba(255,255,255,0.65);
    text-align: center;
    margin-bottom: 20px;
}
.outcome-detail {
    font-family: 'Inter', sans-serif;
    font-size: 13px;
    line-height: 1.6;
    color: rgba(255,255,255,0.5);
    text-align: center;
    margin: 8px 0;
}
.outcome-detail em { color: rgba(255,255,255,0.4); }
.outcome-math {
    background: rgba(66,165,245,0.06);
    border: 1px solid rgba(66,165,245,0.15);
    border-radius: 8px;
    padding: 10px 14px;
    margin: 12px 0;
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    color: #90CAF9;
    text-align: center;
}
.outcome-stat-row {
    display: flex;
    justify-content: center;
    gap: 24px;
    margin: 16px 0;
}
.outcome-stat {
    text-align: center;
}
.outcome-stat-num {
    font-family: 'JetBrains Mono', monospace;
    font-size: 20px;
    font-weight: 700;
}
.outcome-stat-lbl {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: rgba(255,255,255,0.35);
    margin-top: 2px;
}

/* ── Setup page ── */
.setup-hero {
    text-align: center;
    padding: 32px 0 24px;
}
.setup-hero h1 {
    font-family: 'Inter', sans-serif;
    font-size: 28px;
    font-weight: 800;
    color: #E0E0E0;
    margin-bottom: 6px;
}
.setup-hero p {
    font-size: 14px;
    color: rgba(255,255,255,0.4);
}
.setup-section {
    background: linear-gradient(135deg, #0F0F1A 0%, #151520 100%);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 16px;
}
.setup-section-title {
    font-family: 'Inter', sans-serif;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: rgba(255,255,255,0.35);
    margin-bottom: 12px;
}
.edge-context {
    background: rgba(0,200,83,0.04);
    border: 1px solid rgba(0,200,83,0.1);
    border-radius: 10px;
    padding: 14px 16px;
    margin: 12px 0;
    font-family: 'Inter', sans-serif;
    font-size: 13px;
    color: rgba(255,255,255,0.55);
    line-height: 1.6;
    text-align: center;
}
.edge-context strong { color: #69F0AE; }
.limits-row {
    display: flex;
    gap: 16px;
}
.limit-card {
    flex: 1;
    background: rgba(255,255,255,0.02);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 8px;
    padding: 14px;
    text-align: center;
}
.limit-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 20px;
    font-weight: 700;
    color: #E0E0E0;
}
.limit-label {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: rgba(255,255,255,0.3);
    margin-top: 4px;
}
.limit-card.loss .limit-value { color: #FF8A80; }
.limit-card.win .limit-value { color: #69F0AE; }
.limit-card.time .limit-value { color: #90CAF9; }

/* ── Session summary ── */
.summary-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin: 16px 0;
}
.summary-grid-6 {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
    margin: 16px 0;
}
.summary-card {
    background: rgba(255,255,255,0.02);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 10px;
    padding: 16px 12px;
    text-align: center;
}
.summary-val {
    font-family: 'JetBrains Mono', monospace;
    font-size: 22px;
    font-weight: 700;
    color: #E0E0E0;
}
.summary-lbl {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: rgba(255,255,255,0.3);
    margin-top: 4px;
}

/* ── Bluff section ── */
.bluff-section {
    background: rgba(255,179,0,0.04);
    border: 1px solid rgba(255,179,0,0.12);
    border-radius: 10px;
    padding: 16px;
    margin: 16px 0;
}
.bluff-section-title {
    font-family: 'Inter', sans-serif;
    font-size: 13px;
    font-weight: 700;
    color: #FFD54F;
    margin-bottom: 12px;
}

/* ── Sparkline ── */
.sparkline-container {
    background: rgba(255,255,255,0.02);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 10px;
    padding: 12px 16px;
    margin: 12px 0;
    text-align: center;
}
.sparkline-label {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: rgba(255,255,255,0.3);
    margin-bottom: 8px;
}
.sparkline-bar {
    display: inline-block;
    width: 4px;
    margin: 0 1px;
    border-radius: 2px;
    vertical-align: bottom;
}

/* ── End session ── */
.end-session-card {
    background: linear-gradient(135deg, #0F0F1A 0%, #151520 100%);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 14px;
    padding: 28px 24px;
}

/* ── Hide Streamlit default decorations in play mode ── */
.stDeployButton, #MainMenu { display: none; }
</style>

<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700;800&family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
""", unsafe_allow_html=True)


# =============================================================================
# SESSION STATE
# =============================================================================

def init_session_state():
    """Initialize all session state variables."""
    defaults = {
        # Session mode
        "session_mode": "setup",  # 'setup', 'play', 'ending'

        # Session data
        "current_session": None,
        "session_pl": 0.0,
        "our_stack": 0.0,
        "hands_played": 0,
        "decisions_requested": 0,
        "hand_outcomes": [],

        # Decision tracking (for React component bridge)
        "current_decision_dict": None,  # Dict sent to React as decision_result prop
        "current_decision_obj": None,   # Decision object (for modal/recording)
        "last_hand_context": {},

        # Input mode
        "input_mode": "keyboard",  # "standard", "keyboard", "two_table"

        # Modal queue
        "modal_queue": [],

        # Table check
        "table_check_due": False,
        "last_table_check": None,

        # Bluff tracking (session-level)
        "session_bluff_spots": 0,
        "session_bluff_bets": 0,
        "session_bluff_folds_won": 0,
        "session_bluff_profit": 0.0,

        # Streak tracking (mental game)
        "current_loss_streak": 0,
        "tilt_banner_shown_at_streak": 0,
        "tilt_banner_shown_at_pl": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_session_state()


# =============================================================================
# HELPERS
# =============================================================================

def get_user_profile() -> dict:
    user_id = st.session_state.get("user_db_id")
    if not user_id:
        return {}
    return get_profile_by_auth_id(user_id) or {}


def get_session_duration_minutes() -> int:
    session = st.session_state.get("current_session")
    if not session:
        return 0
    started_at = session.get("started_at")
    if not started_at:
        return 0
    try:
        start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        return int((now - start).total_seconds() / 60)
    except Exception:
        return 0


def get_session_duration_display() -> str:
    """Return formatted H:MM:SS for the session timer."""
    session = st.session_state.get("current_session")
    if not session:
        return "0:00:00"
    started_at = session.get("started_at")
    if not started_at:
        return "0:00:00"
    try:
        start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        elapsed = int((now - start).total_seconds())
        h = elapsed // 3600
        m = (elapsed % 3600) // 60
        s = elapsed % 60
        return f"{h}:{m:02d}:{s:02d}"
    except Exception:
        return "0:00:00"


def fmt_money(amount: float) -> str:
    if amount >= 0:
        return f"+${amount:,.2f}"
    return f"-${abs(amount):,.2f}"


def fmt_money_short(amount: float) -> str:
    if amount >= 0:
        return f"+${amount:,.0f}"
    return f"-${abs(amount):,.0f}"


def pl_class(amount: float) -> str:
    if amount > 0:
        return "pl-positive"
    elif amount < 0:
        return "pl-negative"
    return "pl-zero"


def queue_modal(modal_type: str, data: dict):
    st.session_state.modal_queue.append({"type": modal_type, "data": data})


def dismiss_modal():
    if st.session_state.modal_queue:
        st.session_state.modal_queue.pop(0)


def clear_hand_state():
    st.session_state.current_decision_dict = None
    st.session_state.current_decision_obj = None
    st.session_state.last_hand_context = {}


def get_current_loss_streak() -> int:
    """Count consecutive losses from the end of hand_outcomes."""
    streak = 0
    for h in reversed(st.session_state.hand_outcomes):
        if h.get("outcome") == "lost":
            streak += 1
        else:
            break
    return streak


def build_sparkline_html(hand_outcomes: list, max_bars: int = 40) -> str:
    """Build a mini P/L trajectory sparkline from hand outcomes."""
    if not hand_outcomes:
        return ""
    cumulative = []
    running = 0.0
    for h in hand_outcomes:
        running += h.get("profit_loss", 0)
        cumulative.append(running)
    if len(cumulative) > max_bars:
        step = len(cumulative) / max_bars
        sampled = [cumulative[int(i * step)] for i in range(max_bars)]
    else:
        sampled = cumulative
    if not sampled:
        return ""
    min_val, max_val = min(sampled), max(sampled)
    spread = max_val - min_val if max_val != min_val else 1
    bars = ""
    for val in sampled:
        height = 10 + int(((val - min_val) / spread) * 20)
        color = "#00E676" if val >= 0 else "#FF5252"
        bars += f'<span class="sparkline-bar" style="height:{height}px;background:{color};"></span>'
    return f"""
    <div class="sparkline-container">
        <div class="sparkline-label">Session P/L Trajectory</div>
        <div style="height:32px;display:flex;align-items:flex-end;justify-content:center;">{bars}</div>
    </div>"""


# =============================================================================
# SESSION HEADER — Live timer + stats bar
# =============================================================================

def render_session_header():
    """Premium session header: timer, P/L, BB/100, stack, hands, hands/hr."""
    session = st.session_state.current_session
    if not session:
        return

    stakes = session.get("stakes", "$1/$2")
    bb_size = float(session.get("bb_size", 2.0))
    duration_display = get_session_duration_display()
    duration_min = get_session_duration_minutes()
    session_pl = st.session_state.session_pl
    our_stack = st.session_state.our_stack
    stack_bb = our_stack / bb_size if bb_size > 0 else 0
    hands = st.session_state.hands_played

    # BB/100 calculation
    bb_per_100 = 0
    if hands > 0 and bb_size > 0:
        bb_per_100 = ((session_pl / bb_size) / hands) * 100

    # Hands per hour
    hands_per_hr = 0
    if duration_min > 0:
        hands_per_hr = (hands / duration_min) * 60

    # Timer color based on session phase
    timer_color = "#E0E0E0"
    if duration_min >= TIME_HARD_STOP:
        timer_color = "#FF5252"
    elif duration_min >= TIME_WARNING:
        timer_color = "#FFD54F"

    bb100_color = "#69F0AE" if bb_per_100 >= 0 else "#FF8A80"

    st.markdown(f"""
    <div class="session-bar">
        <div class="session-stat">
            <div class="session-stat-value" style="color: #90CAF9;">{stakes}</div>
            <div class="session-stat-label">Stakes</div>
        </div>
        <div class="session-stat-divider"></div>
        <div class="session-stat">
            <div class="session-stat-value" style="color: {timer_color};" id="live-timer"
                 data-start="{session.get('started_at', '')}">
                <span class="timer-dot"></span>{duration_display}
            </div>
            <div class="session-stat-label">Session</div>
        </div>
        <div class="session-stat-divider"></div>
        <div class="session-stat">
            <div class="session-stat-value {pl_class(session_pl)}">{fmt_money(session_pl)}</div>
            <div class="session-stat-label">P/L</div>
        </div>
        <div class="session-stat-divider"></div>
        <div class="session-stat">
            <div class="session-stat-value" style="color: {bb100_color};">{bb_per_100:+.1f}</div>
            <div class="session-stat-label">BB/100</div>
        </div>
        <div class="session-stat-divider"></div>
        <div class="session-stat">
            <div class="session-stat-value" style="color: #E0E0E0;">{stack_bb:.0f}</div>
            <div class="session-stat-label">Stack BB</div>
        </div>
        <div class="session-stat-divider"></div>
        <div class="session-stat">
            <div class="session-stat-value" style="color: rgba(255,255,255,0.5);">{hands}</div>
            <div class="session-stat-label">Hands</div>
        </div>
        <div class="session-stat-divider"></div>
        <div class="session-stat">
            <div class="session-stat-value" style="color: rgba(255,255,255,0.4);">{hands_per_hr:.0f}</div>
            <div class="session-stat-label">Hands/Hr</div>
        </div>
    </div>
    <script>
    (function() {{
        var el = document.getElementById('live-timer');
        if (!el) return;
        var startStr = el.getAttribute('data-start');
        if (!startStr) return;
        var start = new Date(startStr).getTime();
        if (isNaN(start)) return;
        function tick() {{
            var now = Date.now();
            var elapsed = Math.floor((now - start) / 1000);
            var h = Math.floor(elapsed / 3600);
            var m = Math.floor((elapsed % 3600) / 60);
            var s = elapsed % 60;
            var dot = '<span class="timer-dot"></span>';
            el.innerHTML = dot + h + ':' + String(m).padStart(2,'0') + ':' + String(s).padStart(2,'0');
        }}
        tick();
        setInterval(tick, 1000);
    }})();
    </script>
    """, unsafe_allow_html=True)


# =============================================================================
# SESSION ALERTS
# =============================================================================

def check_session_alerts():
    """Check and display session alerts (time, stop-loss, stop-win, table check)."""
    session = st.session_state.current_session
    if not session:
        return

    duration = get_session_duration_minutes()
    session_pl = st.session_state.session_pl

    stakes = session.get("stakes", "$1/$2")
    stakes_info = STAKES_BUY_INS.get(stakes, {"buy_in": 200})
    standard_buy_in = stakes_info["buy_in"]

    profile = get_user_profile()
    user_mode = profile.get("user_mode", "balanced")
    mode_config = MODE_CONFIG.get(user_mode, MODE_CONFIG["balanced"])

    stop_loss = standard_buy_in * mode_config["stop_loss_bi"]
    stop_win = standard_buy_in * mode_config["stop_win_bi"]

    alerts = []

    # Time alerts
    if duration >= TIME_HARD_STOP:
        alerts.append(("danger", "🛑", "4-Hour Hard Stop",
                        "Session should end after this hand. Performance declines sharply past 4 hours."))
    elif duration >= TIME_WARNING:
        alerts.append(("warning", "⏱️", "3-Hour Mark",
                        "Performance typically declines from here. Consider wrapping up."))
    elif duration >= TIME_OPTIMAL and session_pl > 0:
        alerts.append(("info", "💡", "Optimal Time + Winning",
                        "You're at optimal session length and ahead. Locking in profit is always +EV."))

    # Stop-loss
    if session_pl <= -stop_loss:
        alerts.append(("danger", "🛑", f"Stop-Loss Hit (${stop_loss:.0f})",
                        "End the session after this hand. Protect your bankroll."))

    # Stop-win
    if session_pl >= stop_win:
        alerts.append(("success", "🎉", f"Stop-Win Hit (${stop_win:.0f})",
                        "Congratulations! Lock in your profit. You can always come back tomorrow."))

    # Tilt detection: approaching stop-loss (75%)
    tilt_threshold = -stop_loss * TILT_STOP_LOSS_PCT
    shown_at_pl = st.session_state.tilt_banner_shown_at_pl
    if (session_pl <= tilt_threshold
            and session_pl > -stop_loss
            and (shown_at_pl is None or session_pl < shown_at_pl - 20)):
        alerts.append(("mental", "🧠", "Mental Check",
            f"Rough stretch — you're down {fmt_money_short(session_pl)}. "
            f"Your decisions have been mathematically correct. Results ≠ quality. "
            f"Stay the course or end the session with discipline."))
        st.session_state.tilt_banner_shown_at_pl = session_pl

    # Tilt detection: consecutive losses
    streak = get_current_loss_streak()
    shown_at_streak = st.session_state.tilt_banner_shown_at_streak
    if streak >= TILT_LOSS_STREAK and streak > shown_at_streak:
        alerts.append(("mental", "🧠", f"{streak} Losses in a Row",
            "This is normal variance. At +6 BB/100, streaks of 3-5 losses happen in almost "
            "every session. Your edge comes from the next 100 hands, not the last 3. "
            "Take a deep breath. The math hasn't changed."))
        st.session_state.tilt_banner_shown_at_streak = streak

    # Table check (every TABLE_CHECK_INTERVAL minutes)
    if duration > 0 and not st.session_state.table_check_due:
        last_check = st.session_state.last_table_check
        check_needed = False
        if not last_check:
            check_needed = duration >= TABLE_CHECK_INTERVAL
        else:
            elapsed = (datetime.now(timezone.utc) - last_check).total_seconds()
            check_needed = elapsed >= TABLE_CHECK_INTERVAL * 60
        if check_needed:
            st.session_state.table_check_due = True

    # Render alerts
    for alert_type, icon, title, message in alerts:
        st.markdown(f"""
        <div class="alert-banner {alert_type}">
            <span class="alert-icon">{icon}</span>
            <div><span class="alert-title">{title}</span> — {message}</div>
        </div>
        """, unsafe_allow_html=True)

    # Table check prompt
    if st.session_state.table_check_due:
        if st.button("🎯 Quick Table Check — Is your table still good?", use_container_width=True,
                      key="table_check_trigger"):
            queue_modal("table_check", {})
            st.rerun()


# =============================================================================
# MODALS
# =============================================================================

def render_modals() -> bool:
    """Render any queued modals. Returns True if a modal was shown."""
    if not st.session_state.modal_queue:
        return False

    modal = st.session_state.modal_queue[0]
    modal_type = modal.get("type")
    data = modal.get("data", {})

    if modal_type == "outcome":
        return render_outcome_modal(data)
    elif modal_type == "session_end":
        return render_session_end_modal(data)
    elif modal_type == "table_check":
        return render_table_check_modal(data)

    return False


def render_outcome_modal(data: dict) -> bool:
    """Post-hand outcome modal with EV education, decision context, and hand-specific math."""

    outcome = data.get("outcome")
    action_taken = data.get("action_taken", "")
    profit_loss = data.get("profit_loss", 0)
    bluff_context = data.get("bluff_context")
    explanation = data.get("explanation", "")  # Snapshot captured at queue time
    calculation = data.get("calculation", "")  # Snapshot captured at queue time

    # ── Bluff-specific modal ──
    if bluff_context:
        return render_bluff_outcome_modal(bluff_context, data)

    # ── Standard outcome modal ──
    if outcome == "folded":
        icon, title = "🛡️", "Good Fold — Money Saved"
        message = ("Every -EV call you avoid is money in your pocket. "
                   "The best players fold more than recreational players — that's why they win.")
    elif outcome == "won":
        icon, title = "✅", "Correct Play + Win"
        message = ("You made the +EV play and it worked out. "
                   "Keep making these decisions and the results will keep coming.")
    else:
        icon, title = "📊", "Correct Play — Variance"
        message = ("This is exactly how winning players play. "
                   "Variance means you'll lose some +EV spots. Over hundreds of hands, "
                   "these mathematically correct decisions add up to significant profit.")

    # Build detail + math sections
    detail_html = ""
    if action_taken:
        detail_html += f'<div class="outcome-detail"><strong>Your action:</strong> {_html.escape(action_taken)}</div>'
    if explanation:
        detail_html += f'<div class="outcome-detail"><em>{_html.escape(explanation)}</em></div>'
    math_html = f'<div class="outcome-math">{_html.escape(calculation)}</div>' if calculation else ""

    st.markdown(f"""
    <div class="outcome-card">
        <div class="outcome-title">{icon} {title}</div>
        {detail_html}
        {math_html}
        <div class="outcome-message">{message}</div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("Got it → Next Hand", type="primary", use_container_width=True, key="modal_dismiss"):
        dismiss_modal()
        clear_hand_state()
        st.rerun()

    return True


def render_bluff_outcome_modal(bluff_ctx: dict, data: dict) -> bool:
    """Bluff-specific modal with break-even math, EV context, and emotional support."""

    bluff_outcome = bluff_ctx.get("outcome", "")
    profit_loss = data.get("profit_loss", 0)
    fold_pct = bluff_ctx.get("estimated_fold_pct", 0.5)
    break_even_pct = bluff_ctx.get("break_even_pct", 0.4)
    ev_of_bet = bluff_ctx.get("ev_of_bet", 0)
    pot_size = bluff_ctx.get("pot_size", 0)
    bet_amount = bluff_ctx.get("bet_amount", 0)

    # Break-even math line (shown in all bluff modals where we have data)
    be_display = int(break_even_pct * 100) if break_even_pct else 0
    fp_display = int(fold_pct * 100) if fold_pct else 0
    math_line = (f"You bet ${bet_amount:.0f} into ${pot_size:.0f}. "
                 f"Needs {be_display}% folds to break even. "
                 f"Estimated fold rate: {fp_display}%.") if bet_amount else ""

    if bluff_outcome == "fold":
        icon, title = "✅", "They Folded — Bluff Worked!"
        message = (f"You won the ${pot_size:.0f} pot without showdown. "
                   f"This bet is profitable because they fold often enough to cover the misses.")
        stat_html = f"""
        <div class="outcome-stat-row">
            <div class="outcome-stat">
                <div class="outcome-stat-num pl-positive">+${pot_size:.0f}</div>
                <div class="outcome-stat-lbl">Pot Won</div>
            </div>
            <div class="outcome-stat">
                <div class="outcome-stat-num" style="color: #FFD54F;">
                    {st.session_state.session_bluff_folds_won}/{st.session_state.session_bluff_bets}
                </div>
                <div class="outcome-stat-lbl">Bluffs Worked</div>
            </div>
        </div>
        """

    elif bluff_outcome == "call_lost":
        works_out_of_10 = fold_pct * 10
        icon, title = "📊", "They Called — Didn't Work This Time"
        message = (f"This bet works about {works_out_of_10:.0f} out of 10 times. "
                   f"The math is still in your favor over time. "
                   f"It feels bad to get caught. But players who stop bluffing after "
                   f"getting caught leave money on the table. Your opponents don't remember "
                   f"this hand — they'll fold to your next bet just as often.")
        stat_html = f"""
        <div class="outcome-stat-row">
            <div class="outcome-stat">
                <div class="outcome-stat-num pl-negative">-${abs(profit_loss):.0f}</div>
                <div class="outcome-stat-lbl">This Hand</div>
            </div>
            <div class="outcome-stat">
                <div class="outcome-stat-num" style="color: #69F0AE;">+${ev_of_bet:.2f}</div>
                <div class="outcome-stat-lbl">Long-Term EV/Attempt</div>
            </div>
        </div>
        """

    elif bluff_outcome == "checked":
        icon, title = "✋", "You Checked — Hand Over"
        message = (f"Checking is fine. Over time, betting in this spot "
                   f"averages +${ev_of_bet:.2f} per attempt. Something to try when you're ready.")
        stat_html = ""

    else:  # call_won
        icon, title = "✅", "They Called and You Won!"
        message = ("Even better than expected — you bet as a bluff and won at showdown. Bonus profit.")
        stat_html = f"""
        <div class="outcome-stat-row">
            <div class="outcome-stat">
                <div class="outcome-stat-num pl-positive">+${profit_loss:.0f}</div>
                <div class="outcome-stat-lbl">Won at Showdown</div>
            </div>
        </div>
        """

    math_html = f'<div class="outcome-math">{_html.escape(math_line)}</div>' if math_line else ""

    st.markdown(f"""
    <div class="outcome-card">
        <div class="outcome-title">{icon} {title}</div>
        {stat_html}
        {math_html}
        <div class="outcome-message">{message}</div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("Got it → Next Hand", type="primary", use_container_width=True, key="bluff_modal_dismiss"):
        dismiss_modal()
        clear_hand_state()
        st.rerun()

    return True


def render_table_check_modal(data: dict) -> bool:
    """Quick table quality assessment."""

    st.markdown("""
    <div class="outcome-card">
        <div class="outcome-title">🎯 Quick Table Check</div>
        <div class="outcome-message">3 questions about the last 10 hands</div>
    </div>
    """, unsafe_allow_html=True)

    players_to_flop = st.radio(
        "How many players typically see the flop?",
        ["2-3 (Tight)", "3-4 (Average)", "4-5 (Loose)", "5-6 (Very Loose)"],
        key="tc_q1", horizontal=True
    )

    has_limpers = st.radio(
        "Are there limpers?",
        ["Yes", "No"],
        key="tc_q2", horizontal=True
    )

    three_bet_freq = st.radio(
        "Is anyone 3-betting a lot?",
        ["No (Good)", "Sometimes", "Yes (Reg-heavy)"],
        key="tc_q3", horizontal=True
    )

    # Calculate score
    score = 50
    if "5-6" in players_to_flop: score += 30
    elif "4-5" in players_to_flop: score += 20
    elif "3-4" in players_to_flop: score += 10
    else: score -= 10
    score += 15 if has_limpers == "Yes" else -5
    if "No" in three_bet_freq: score += 15
    elif "Yes" in three_bet_freq: score -= 15
    score = max(0, min(100, score))

    st.markdown("---")

    if score >= 60:
        st.markdown(f"""
        <div class="alert-banner success">
            <span class="alert-icon">✅</span>
            <div><span class="alert-title">Score: {score}/100 — Good table, stay!</span></div>
        </div>
        """, unsafe_allow_html=True)
    elif score >= 40:
        st.markdown(f"""
        <div class="alert-banner warning">
            <span class="alert-icon">⚠️</span>
            <div><span class="alert-title">Score: {score}/100 — Average table</span></div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="alert-banner danger">
            <span class="alert-icon">🔴</span>
            <div><span class="alert-title">Score: {score}/100 — Tough table, consider moving</span></div>
        </div>
        """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Done", type="primary", use_container_width=True, key="tc_done"):
            st.session_state.last_table_check = datetime.now(timezone.utc)
            st.session_state.table_check_due = False
            dismiss_modal()
            st.rerun()
    with col2:
        if st.button("Skip", use_container_width=True, key="tc_skip"):
            st.session_state.table_check_due = False
            dismiss_modal()
            st.rerun()

    return True


def render_session_end_modal(data: dict) -> bool:
    """Session summary — comprehensive stats, sparkline, bluff stats, mental coaching."""

    duration_minutes = data.get("duration_minutes", 0)
    h, m = duration_minutes // 60, duration_minutes % 60
    total_hands = data.get("total_hands", 0)
    session_pl = data.get("session_pl", 0)
    wins = data.get("wins", 0)
    losses = data.get("losses", 0)
    folds = data.get("folds", 0)
    bb_size = data.get("bb_size", 2.0)

    bb_per_100 = 0
    if total_hands > 0 and bb_size > 0:
        bb_per_100 = ((session_pl / bb_size) / total_hands) * 100

    hands_per_hr = 0
    if duration_minutes > 0:
        hands_per_hr = (total_hands / duration_minutes) * 60

    dollars_per_hr = session_pl / (duration_minutes / 60) if duration_minutes > 0 else 0

    st.markdown("""
    <div class="outcome-card">
        <div class="outcome-title">📊 Session Complete</div>
    </div>
    """, unsafe_allow_html=True)

    # 6-stat summary grid
    st.markdown(f"""
    <div class="summary-grid-6">
        <div class="summary-card">
            <div class="summary-val" style="color: #90CAF9;">{h}h {m}m</div>
            <div class="summary-lbl">Duration</div>
        </div>
        <div class="summary-card">
            <div class="summary-val">{total_hands}</div>
            <div class="summary-lbl">Hands</div>
        </div>
        <div class="summary-card">
            <div class="summary-val" style="color: rgba(255,255,255,0.5);">{hands_per_hr:.0f}</div>
            <div class="summary-lbl">Hands/Hr</div>
        </div>
        <div class="summary-card">
            <div class="summary-val {pl_class(session_pl)}">{fmt_money_short(session_pl)}</div>
            <div class="summary-lbl">Session P/L</div>
        </div>
        <div class="summary-card">
            <div class="summary-val" style="color: {'#69F0AE' if bb_per_100 >= 0 else '#FF8A80'};">{bb_per_100:+.1f}</div>
            <div class="summary-lbl">BB/100</div>
        </div>
        <div class="summary-card">
            <div class="summary-val" style="color: {'#69F0AE' if dollars_per_hr >= 0 else '#FF8A80'};">${dollars_per_hr:+.0f}</div>
            <div class="summary-lbl">$/Hour</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # P/L sparkline trajectory
    sparkline_html = build_sparkline_html(st.session_state.hand_outcomes)
    if sparkline_html:
        st.markdown(sparkline_html, unsafe_allow_html=True)

    # Outcome breakdown
    if total_hands > 0:
        win_pct = (wins / total_hands) * 100
        loss_pct = (losses / total_hands) * 100
        fold_pct = (folds / total_hands) * 100

        st.markdown(f"""
        <div class="outcome-stat-row">
            <div class="outcome-stat">
                <div class="outcome-stat-num pl-positive">{wins}</div>
                <div class="outcome-stat-lbl">Wins ({win_pct:.0f}%)</div>
            </div>
            <div class="outcome-stat">
                <div class="outcome-stat-num pl-negative">{losses}</div>
                <div class="outcome-stat-lbl">Losses ({loss_pct:.0f}%)</div>
            </div>
            <div class="outcome-stat">
                <div class="outcome-stat-num" style="color: rgba(255,255,255,0.5);">{folds}</div>
                <div class="outcome-stat-lbl">Folds ({fold_pct:.0f}%)</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ── Aggressive Plays section (bluff stats) ──
    bluff_spots = st.session_state.session_bluff_spots
    if bluff_spots > 0:
        bluff_bets = st.session_state.session_bluff_bets
        bluff_folds = st.session_state.session_bluff_folds_won
        bluff_profit = st.session_state.session_bluff_profit

        st.markdown(f"""
        <div class="bluff-section">
            <div class="bluff-section-title">⚡ Aggressive Plays</div>
            <div class="outcome-stat-row">
                <div class="outcome-stat">
                    <div class="outcome-stat-num" style="color: #FFD54F;">{bluff_spots}</div>
                    <div class="outcome-stat-lbl">Bluff Spots</div>
                </div>
                <div class="outcome-stat">
                    <div class="outcome-stat-num" style="color: #E0E0E0;">{bluff_bets}</div>
                    <div class="outcome-stat-lbl">You Bet</div>
                </div>
                <div class="outcome-stat">
                    <div class="outcome-stat-num pl-positive">{bluff_folds}</div>
                    <div class="outcome-stat-lbl">Folds Won</div>
                </div>
                <div class="outcome-stat">
                    <div class="outcome-stat-num {pl_class(bluff_profit)}">{fmt_money_short(bluff_profit)}</div>
                    <div class="outcome-stat-lbl">Bluff P/L</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        if session_pl > 0 and bluff_profit > 0:
            pct = (bluff_profit / session_pl) * 100
            st.markdown(f"""
            <div class="alert-banner success">
                <span class="alert-icon">⚡</span>
                <div><span class="alert-title">{pct:.0f}% of your profit came from aggressive plays.</span></div>
            </div>
            """, unsafe_allow_html=True)
        elif session_pl < 0 and bluff_profit > 0:
            st.markdown(f"""
            <div class="alert-banner info">
                <span class="alert-icon">⚡</span>
                <div><span class="alert-title">Aggressive plays saved you {fmt_money_short(bluff_profit)}.
                Without them you'd be down {fmt_money_short(session_pl - bluff_profit)}.</span></div>
            </div>
            """, unsafe_allow_html=True)

    # ── Contextual variance education with mental coaching ──
    session = st.session_state.current_session
    stakes = session.get("stakes", "$1/$2") if session else "$1/$2"
    expected_hr = EXPECTED_HOURLY.get(stakes, 9.10)

    if session_pl > 0:
        st.markdown(f"""
        <div class="alert-banner success">
            <span class="alert-icon">🎉</span>
            <div><span class="alert-title">Great session.</span>
            You played mathematically sound poker and the results showed it.
            The temptation to move up stakes or extend the session is where winning players
            give back their edge. Lock in this profit and come back tomorrow.</div>
        </div>
        """, unsafe_allow_html=True)
    elif session_pl < 0:
        st.markdown(f"""
        <div class="alert-banner info">
            <span class="alert-icon">📊</span>
            <div><span class="alert-title">Variance happens.</span>
            At {stakes}, a losing session happens roughly {LOSING_SESSION_PCT}% of the time — even
            for winning players. Your expected earn rate is +${expected_hr:.0f}/hour.
            One losing session doesn't change that. Your 10-session average is what matters,
            not any single result. Keep playing correctly.</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="alert-banner info">
            <span class="alert-icon">📊</span>
            <div>Break-even session. You played solid poker. At {stakes} your expected
            rate is +${expected_hr:.0f}/hour. The wins will come with continued play.</div>
        </div>
        """, unsafe_allow_html=True)

    if st.button("Close Session", type="primary", use_container_width=True, key="close_session_btn"):
        dismiss_modal()
        st.session_state.session_mode = "setup"
        st.session_state.current_session = None
        clear_sidebar_session_info()
        st.rerun()

    return True


# =============================================================================
# SETUP MODE
# =============================================================================

def render_setup_mode():
    """Session setup — stakes, buy-in, mode, limits."""

    profile = get_user_profile()
    user_mode = profile.get("user_mode", "balanced")
    current_bankroll = float(profile.get("current_bankroll", 0) or 0)
    default_stakes = profile.get("default_stakes", "$1/$2")
    mode_config = MODE_CONFIG.get(user_mode, MODE_CONFIG["balanced"])
    user_id = st.session_state.get("user_db_id")

    # Check for active session
    active_session = get_active_session(user_id) if user_id else None
    if active_session:
        st.markdown("""
        <div class="alert-banner warning">
            <span class="alert-icon">⚠️</span>
            <div><span class="alert-title">Active session found.</span> Continue or end it?</div>
        </div>
        """, unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("▶️ Continue Session", type="primary", use_container_width=True):
                st.session_state.current_session = active_session
                st.session_state.session_mode = "play"
                st.session_state.our_stack = float(active_session.get("buy_in_amount", 200))
                st.session_state.session_pl = float(active_session.get("profit_loss", 0) or 0)
                update_sidebar_session_info(active_session, st.session_state.session_pl)
                st.rerun()
        with col2:
            if st.button("End Previous", use_container_width=True):
                end_session(active_session["id"], active_session.get("buy_in_amount", 0), "manual")
                st.rerun()
        return

    # ── Hero section ──
    st.markdown("""
    <div class="setup-hero">
        <h1>Start Session</h1>
        <p>Configure your game, then play.</p>
    </div>
    """, unsafe_allow_html=True)

    # ── Stakes + Buy-in ──
    st.markdown('<div class="setup-section"><div class="setup-section-title">Game Setup</div>',
                unsafe_allow_html=True)

    stakes_options = list(STAKES_BUY_INS.keys())
    default_idx = stakes_options.index(default_stakes) if default_stakes in stakes_options else 1

    selected_stakes = st.selectbox("Stakes", stakes_options, index=default_idx,
                                   label_visibility="collapsed")

    stakes_info = STAKES_BUY_INS.get(selected_stakes, {"bb": 2.0, "buy_in": 200})
    bb_size = stakes_info["bb"]
    standard_buy_in = stakes_info["buy_in"]

    buy_in = st.number_input("Buy-in ($)", min_value=float(standard_buy_in * 0.2),
                              max_value=float(standard_buy_in * 4),
                              value=float(standard_buy_in),
                              step=float(bb_size * 10))

    stack_bb = buy_in / bb_size if bb_size > 0 else 100
    if stack_bb < 40:
        st.caption(f"⚠️ {stack_bb:.0f} BB — Short stack adjustments active")
    elif stack_bb > 150:
        st.caption(f"📈 {stack_bb:.0f} BB — Deep stack adjustments active")
    else:
        st.caption(f"{stack_bb:.0f} BB (standard)")

    st.markdown('</div>', unsafe_allow_html=True)

    # ── Input mode ──
    st.markdown('<div class="setup-section"><div class="setup-section-title">Input Mode</div>',
                unsafe_allow_html=True)

    input_mode = st.radio("Mode", ["Keyboard Shortcuts", "Standard (Click)", "Two-Table (Keyboard)"],
                           index=0, horizontal=True, label_visibility="collapsed")
    st.caption("⚡ Keyboard mode is faster — you can still click any button if you prefer.")

    mode_map = {"Standard (Click)": "standard", "Keyboard Shortcuts": "keyboard",
                "Two-Table (Keyboard)": "two_table"}
    st.session_state.input_mode = mode_map.get(input_mode, "keyboard")

    st.markdown('</div>', unsafe_allow_html=True)

    # ── Bankroll check ──
    required_buy_ins = mode_config["buy_ins"]
    override = True

    if current_bankroll > 0:
        buy_ins_available = current_bankroll / standard_buy_in

        if buy_ins_available < required_buy_ins:
            st.markdown(f"""
            <div class="alert-banner warning">
                <span class="alert-icon">⚠️</span>
                <div><span class="alert-title">Bankroll Warning</span> —
                {mode_config['label']} mode needs {required_buy_ins} buy-ins
                (${standard_buy_in * required_buy_ins:,.0f}).
                You have {buy_ins_available:.1f}.</div>
            </div>
            """, unsafe_allow_html=True)
            override = st.checkbox("I understand the risk", key="bankroll_override")
        else:
            st.markdown(f"""
            <div class="alert-banner success">
                <span class="alert-icon">✅</span>
                <div>Bankroll: ${current_bankroll:,.0f} ({buy_ins_available:.1f} buy-ins) —
                adequate for {selected_stakes}</div>
            </div>
            """, unsafe_allow_html=True)

    # ── Session limits ──
    stop_loss = standard_buy_in * mode_config["stop_loss_bi"]
    stop_win = standard_buy_in * mode_config["stop_win_bi"]

    st.markdown(f"""
    <div class="setup-section">
        <div class="setup-section-title">Session Limits — {mode_config['label']} Mode</div>
        <div class="limits-row">
            <div class="limit-card loss">
                <div class="limit-value">${stop_loss:.0f}</div>
                <div class="limit-label">Stop-Loss</div>
            </div>
            <div class="limit-card win">
                <div class="limit-value">${stop_win:.0f}</div>
                <div class="limit-label">Stop-Win</div>
            </div>
            <div class="limit-card time">
                <div class="limit-value">4h</div>
                <div class="limit-label">Time Limit</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Your Edge context ──
    expected_hr = EXPECTED_HOURLY.get(selected_stakes, 9.10)
    st.markdown(f"""
    <div class="edge-context">
        At <strong>{selected_stakes}</strong> in {mode_config['label']} mode,
        your expected earn rate is <strong>+${expected_hr:.2f}/hour</strong>.
        Play 2-3 hours for optimal results.
        Stop-loss at ${stop_loss:.0f} protects your bankroll.
        Follow every recommendation and the math handles the rest.
    </div>
    """, unsafe_allow_html=True)

    # ── Start button ──
    if st.button("▶️  Start Session", type="primary", use_container_width=True, disabled=not override):
        session = create_session(
            user_id=user_id,
            stakes=selected_stakes,
            bb_size=bb_size,
            buy_in_amount=buy_in,
            bankroll_at_start=current_bankroll if current_bankroll > 0 else None,
        )
        if session:
            st.session_state.current_session = session
            st.session_state.session_mode = "play"
            st.session_state.our_stack = buy_in
            st.session_state.session_pl = 0.0
            st.session_state.hands_played = 0
            st.session_state.decisions_requested = 0
            st.session_state.hand_outcomes = []
            st.session_state.session_bluff_spots = 0
            st.session_state.session_bluff_bets = 0
            st.session_state.session_bluff_folds_won = 0
            st.session_state.session_bluff_profit = 0.0
            st.session_state.current_loss_streak = 0
            st.session_state.tilt_banner_shown_at_streak = 0
            st.session_state.tilt_banner_shown_at_pl = None
            clear_hand_state()
            update_sidebar_session_info(session, 0)
            st.rerun()
        else:
            st.error("Failed to create session. Please try again.")


# =============================================================================
# PLAY MODE — React Component Integration
# =============================================================================

def render_play_mode():
    """Main play loop: header → alerts → React component → process events."""

    # Modals take priority
    if render_modals():
        return

    session = st.session_state.current_session
    if not session:
        st.session_state.session_mode = "setup"
        st.rerun()
        return

    # Session header (live timer, P/L, stack)
    render_session_header()

    # Session alerts (time, stop-loss, stop-win, table check)
    check_session_alerts()

    # ── React component ──
    # The component handles: input → decision display → outcome selection
    # It returns events via Streamlit.setComponentValue()

    stakes = session.get("stakes", "$1/$2")
    bb_size = float(session.get("bb_size", 2.0))

    component_value = poker_input(
        mode=st.session_state.input_mode,
        stakes=stakes,
        bb_size=bb_size,
        stack_size=st.session_state.our_stack,
        decision_result=st.session_state.current_decision_dict,
        session_active=True,
        key="poker_input_main",
    )

    # ── Process component events ──
    if component_value is not None:
        event_type = component_value.get("type")

        if event_type == "decision_request":
            handle_decision_request(component_value, session)

        elif event_type == "hand_complete":
            handle_hand_complete(component_value, session)

        elif event_type == "street_continue":
            handle_street_continue(component_value, session)

    # ── End session button (below component) ──
    st.markdown("---")
    if st.button("🏁 End Session", use_container_width=True, key="end_session_play"):
        st.session_state.session_mode = "ending"
        st.rerun()


def handle_decision_request(game_state: dict, session: dict):
    """Component sent a game_state — run engine, send decision back."""

    stakes = session.get("stakes", "$1/$2")
    bb_size = float(session.get("bb_size", 2.0))
    our_stack = st.session_state.our_stack

    # Extract fields from component's game_state
    card1 = game_state.get("card1", "")
    card2 = game_state.get("card2", "")
    our_hand = card1 + card2
    position = game_state.get("position", "BTN")
    street = game_state.get("street", "preflop")
    action_facing = game_state.get("action_facing", "none")
    facing_bet = float(game_state.get("facing_bet", 0))
    pot_size = float(game_state.get("pot_size", 0))
    board = game_state.get("board", None)
    board_texture = game_state.get("board_texture", None)
    hand_strength = game_state.get("hand_strength", None)
    villain_type = game_state.get("villain_type", "unknown")
    we_are_aggressor = game_state.get("we_are_aggressor", False)
    num_limpers = int(game_state.get("num_limpers", 0))

    # Pre-flop hand classification
    if street == "preflop" and not hand_strength:
        hand = normalize_hand(our_hand)
        hs = classify_preflop_hand(hand)
        hand_strength = hs.value

    try:
        decision = get_decision(
            stakes=stakes,
            our_stack=our_stack,
            villain_stack=our_stack,
            pot_size=pot_size,
            facing_bet=facing_bet,
            our_position=position,
            villain_position=None,
            street=street,
            our_hand=our_hand,
            hand_strength=hand_strength or "playable",
            board=board or None,
            board_texture=board_texture,
            num_players=2,
            num_limpers=num_limpers,
            we_are_aggressor=we_are_aggressor,
            action_facing=action_facing,
            villain_type=villain_type,
        )

        # Serialize for React (includes bluff_context + alternative)
        decision_dict = decision_to_dict(decision)

        st.session_state.current_decision_dict = decision_dict
        st.session_state.current_decision_obj = decision
        st.session_state.last_hand_context = game_state
        st.session_state.decisions_requested += 1

        # Increment decisions counter in DB
        session_id = session.get("id")
        if session_id:
            increment_session_stats(session_id, hands=0, decisions=1)

        st.rerun()  # Send decision back to component

    except Exception as e:
        st.error(f"Engine error: {e}")


def handle_hand_complete(component_value: dict, session: dict):
    """Component sent hand_complete — record outcome, update stats, show modal."""

    session_id = session.get("id")
    user_id = st.session_state.get("user_db_id")
    bb_size = float(session.get("bb_size", 2.0))

    outcome = component_value.get("outcome", "folded")
    action_taken = component_value.get("action_taken", "")
    hand_context = component_value.get("hand_context", {})
    bluff_data = component_value.get("bluff_data")  # NEW: bluff tracking

    # ── Capture decision snapshot BEFORE clear_hand_state wipes it ──
    decision_obj = st.session_state.current_decision_obj
    decision_explanation = decision_obj.explanation if decision_obj else ""
    decision_calculation = decision_obj.calculation if decision_obj else ""

    # Calculate profit/loss
    # The React component doesn't calculate P/L — we do it here
    pot_size = float(hand_context.get("pot_size", 0))
    facing_bet = float(hand_context.get("facing_bet", 0))

    if outcome == "won":
        profit_loss = pot_size + facing_bet if pot_size > 0 else (decision_obj.amount if decision_obj else 0) or 0
    elif outcome == "lost":
        loss_amt = (decision_obj.amount if decision_obj and decision_obj.amount else facing_bet) or 0
        profit_loss = -loss_amt
    else:  # folded
        profit_loss = 0

    # Record to database
    record_hand_outcome(
        session_id=session_id,
        user_id=user_id,
        outcome=outcome,
        profit_loss=profit_loss,
        pot_size=pot_size,
        our_position=hand_context.get("position", ""),
        street_reached=hand_context.get("street", "preflop"),
        our_hand=hand_context.get("cards"),
        board=hand_context.get("board"),
        action_taken=action_taken,
        recommendation_given=action_taken,
        we_were_aggressor=hand_context.get("we_are_aggressor", False),
        bluff_context=bluff_data,  # NEW: pass bluff data to DB
    )

    # Update session stats
    increment_session_stats(session_id, hands=1, decisions=0)

    # Update local state
    st.session_state.hands_played += 1
    st.session_state.hand_outcomes.append({
        "outcome": outcome, "profit_loss": profit_loss,
        "street": hand_context.get("street"), "position": hand_context.get("position"),
    })

    if outcome in ("won", "lost"):
        st.session_state.session_pl += profit_loss
        st.session_state.our_stack += profit_loss

    # ── Update loss streak tracking (for tilt detection) ──
    if outcome == "lost":
        st.session_state.current_loss_streak = get_current_loss_streak()
    else:
        st.session_state.current_loss_streak = 0

    # ── Bluff stats tracking ──
    if bluff_data:
        user_bet = bluff_data.get("user_action") == "BET"
        opponent_folded = bluff_data.get("outcome") == "fold"
        bluff_profit = float(bluff_data.get("profit", 0))

        update_session_bluff_stats(session_id, user_bet, opponent_folded, bluff_profit)

        st.session_state.session_bluff_spots += 1
        if user_bet:
            st.session_state.session_bluff_bets += 1
            if opponent_folded:
                st.session_state.session_bluff_folds_won += 1
        st.session_state.session_bluff_profit += bluff_profit

    # Update sidebar
    update_sidebar_session_info(session, st.session_state.session_pl)

    # Queue outcome modal — include decision snapshot so it survives clear_hand_state
    queue_modal("outcome", {
        "outcome": outcome,
        "action_taken": action_taken,
        "hand_context": hand_context,
        "profit_loss": profit_loss,
        "bluff_context": bluff_data,
        "explanation": decision_explanation,     # Snapshot: survives clear
        "calculation": decision_calculation,     # Snapshot: survives clear
    })

    # Clear decision state so component resets
    clear_hand_state()
    st.rerun()


def handle_street_continue(component_value: dict, session: dict):
    """Component sent street_continue — user is continuing to next street.
    Re-run decision with updated game state."""
    # The component sends the updated game_state with the new street info.
    # We treat it the same as a decision_request.
    handle_decision_request(component_value, session)


# =============================================================================
# END SESSION
# =============================================================================

def render_end_session():
    """End session — final stack input + confirmation."""

    session = st.session_state.current_session
    if not session:
        st.session_state.session_mode = "setup"
        st.rerun()
        return

    user_id = st.session_state.get("user_db_id")  # Fix: define user_id at function scope
    duration = get_session_duration_minutes()
    h, m = duration // 60, duration % 60
    session_pl = st.session_state.session_pl
    hands_played = st.session_state.hands_played
    buy_in = float(session.get("buy_in_amount", 200))

    st.markdown("""
    <div class="outcome-card">
        <div class="outcome-title">🏁 End Session</div>
    </div>
    """, unsafe_allow_html=True)

    # Current stats
    st.markdown(f"""
    <div class="summary-grid">
        <div class="summary-card">
            <div class="summary-val" style="color: #90CAF9;">{h}h {m}m</div>
            <div class="summary-lbl">Duration</div>
        </div>
        <div class="summary-card">
            <div class="summary-val">{hands_played}</div>
            <div class="summary-lbl">Hands</div>
        </div>
        <div class="summary-card">
            <div class="summary-val {pl_class(session_pl)}">{fmt_money_short(session_pl)}</div>
            <div class="summary-lbl">Tracked P/L</div>
        </div>
        <div class="summary-card">
            <div class="summary-val" style="color: #E0E0E0;">${st.session_state.our_stack:,.0f}</div>
            <div class="summary-lbl">Est. Stack</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    st.markdown("**Enter your actual final stack** — this overrides the tracked P/L for accuracy.")
    final_stack = st.number_input("Final Stack ($)", min_value=0.0,
                                   value=max(0.0, st.session_state.our_stack),
                                   step=10.0, key="final_stack_input")

    calculated_pl = final_stack - buy_in
    pl_cls = pl_class(calculated_pl)

    st.markdown(f"""
    <div style="text-align: center; margin: 12px 0;">
        <span style="font-family: 'JetBrains Mono', monospace; font-size: 28px; font-weight: 800;"
              class="{pl_cls}">{fmt_money(calculated_pl)}</span>
        <div style="font-size: 11px; color: rgba(255,255,255,0.35); margin-top: 4px;">
            FINAL P/L (${final_stack:,.0f} stack - ${buy_in:,.0f} buy-in)
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("✅ Confirm & End", type="primary", use_container_width=True, key="confirm_end"):
            session_id = session.get("id")
            stakes = session.get("stakes", "$1/$2")
            stakes_info = STAKES_BUY_INS.get(stakes, {"buy_in": 200})
            standard_buy_in = stakes_info["buy_in"]

            profile = get_user_profile()
            user_mode = profile.get("user_mode", "balanced")
            mode_config = MODE_CONFIG.get(user_mode, MODE_CONFIG["balanced"])

            # Determine end reason
            end_reason = "manual"
            if calculated_pl <= -(standard_buy_in * mode_config["stop_loss_bi"]):
                end_reason = "stop_loss"
            elif calculated_pl >= standard_buy_in * mode_config["stop_win_bi"]:
                end_reason = "stop_win"
            elif duration >= TIME_HARD_STOP:
                end_reason = "time_limit"

            end_session(session_id, final_stack, end_reason)

            # Update bankroll
            current_bankroll = float(profile.get("current_bankroll", 0) or 0)
            if current_bankroll > 0:
                new_bankroll = current_bankroll + calculated_pl
                update_user_bankroll(user_id, new_bankroll)
                record_bankroll_change(
                    user_id=user_id,
                    bankroll_amount=new_bankroll,
                    change_amount=calculated_pl,
                    change_type="session_result",
                    session_id=session_id,
                    current_stakes=stakes,
                )

            # Get outcome summary
            summary = get_session_outcome_summary(session_id)

            queue_modal("session_end", {
                "duration_minutes": duration,
                "total_hands": hands_played,
                "session_pl": calculated_pl,
                "wins": summary.get("wins", 0),
                "losses": summary.get("losses", 0),
                "folds": summary.get("folds", 0),
                "bb_size": float(session.get("bb_size", 2.0)),
            })

            st.session_state.session_mode = "play"  # Show modal via play mode
            st.rerun()

    with col2:
        if st.button("← Back to Session", use_container_width=True, key="back_to_session"):
            st.session_state.session_mode = "play"
            st.rerun()


# =============================================================================
# MAIN
# =============================================================================

def main():
    mode = st.session_state.session_mode

    if mode == "setup":
        render_setup_mode()
    elif mode == "play":
        render_play_mode()
    elif mode == "ending":
        render_end_session()
    else:
        render_setup_mode()


if __name__ == "__main__":
    main()