# =============================================================================
# 04_Bankroll_Health.py — PREMIUM Bankroll Health Dashboard
# =============================================================================
#
# PREMIUM FEATURES ($299/month value):
# 1. Bankroll Status - At-a-glance safety indicator (Green/Yellow/Red)
# 2. Stakes Recommendation - Clear "you should play X" guidance
# 3. Move Up/Down Alerts - Proactive stake level management
# 4. Risk of Ruin Calculator - Mathematical probability of going broke
# 5. Bankroll Growth Projection - "Reach $X in Y months"
# 6. Drawdown Tracker - Current vs max historical drawdown
# 7. Bankroll History Chart - Visual progress over time
# 8. Risk Mode Explanation - Understand Aggressive/Balanced/Conservative
#
# DESIGN PRINCIPLES:
# - One glance = know if you're safe
# - Color-coded everything (Green = good, Yellow = caution, Red = danger)
# - Plain English explanations (no jargon)
# - Clear action items
#
# =============================================================================

import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Tuple
import math

st.set_page_config(
    page_title="Bankroll Health | Poker Decision App",
    page_icon="💰",
    layout="wide",
)

from auth import require_auth
from sidebar import render_sidebar
from db import get_user_sessions, get_player_stats

# ---------- Auth Gate ----------
user = require_auth()
render_sidebar()


# =============================================================================
# CONFIGURATION
# =============================================================================

# Stakes configuration: (name, big_blind, min_buy_in, max_buy_in)
STAKES_CONFIG = [
    {"name": "$0.50/$1", "bb": 1.0, "typical_bi": 100, "min_bankroll": 1300},
    {"name": "$1/$2", "bb": 2.0, "typical_bi": 200, "min_bankroll": 2600},
    {"name": "$2/$5", "bb": 5.0, "typical_bi": 500, "min_bankroll": 6500},
    {"name": "$5/$10", "bb": 10.0, "typical_bi": 1000, "min_bankroll": 13000},
    {"name": "$10/$20", "bb": 20.0, "typical_bi": 2000, "min_bankroll": 26000},
    {"name": "$25/$50", "bb": 50.0, "typical_bi": 5000, "min_bankroll": 65000},
]

# Risk modes with buy-in requirements
RISK_MODES = {
    "aggressive": {
        "name": "Aggressive",
        "emoji": "🔥",
        "buy_ins": 13,
        "description": "Higher risk, faster progression",
        "risk_tolerance": "High variance tolerance, experienced player",
        "color": "#f59e0b",
    },
    "balanced": {
        "name": "Balanced",
        "emoji": "⚖️",
        "buy_ins": 15,
        "description": "Recommended for most players",
        "risk_tolerance": "Moderate variance, steady growth",
        "color": "#3b82f6",
    },
    "conservative": {
        "name": "Conservative",
        "emoji": "🛡️",
        "buy_ins": 17,
        "description": "Lower risk, slower progression",
        "risk_tolerance": "Low variance tolerance, capital preservation",
        "color": "#22c55e",
    },
}

# Health status thresholds (in buy-ins at current stakes)
HEALTH_THRESHOLDS = {
    "excellent": {"min_bi": 20, "color": "#22c55e", "label": "Excellent", "emoji": "🟢"},
    "healthy": {"min_bi": 15, "color": "#22c55e", "label": "Healthy", "emoji": "🟢"},
    "adequate": {"min_bi": 12, "color": "#f59e0b", "label": "Adequate", "emoji": "🟡"},
    "warning": {"min_bi": 8, "color": "#f59e0b", "label": "Warning", "emoji": "🟡"},
    "danger": {"min_bi": 0, "color": "#ef4444", "label": "Danger", "emoji": "🔴"},
}


# =============================================================================
# CUSTOM CSS
# =============================================================================

st.markdown("""
<style>
/* ===== Health Status Card ===== */
.health-card {
    border-radius: 16px;
    padding: 32px;
    text-align: center;
    color: white;
    margin-bottom: 24px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
}
.health-card.excellent, .health-card.healthy {
    background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
}
.health-card.adequate, .health-card.warning {
    background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
}
.health-card.danger {
    background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
}
.health-status-emoji { font-size: 64px; margin-bottom: 16px; }
.health-status-label { font-size: 28px; font-weight: 700; margin-bottom: 8px; }
.health-status-bankroll { font-size: 42px; font-weight: 700; margin-bottom: 8px; }
.health-status-context { font-size: 16px; opacity: 0.9; }

/* ===== Metric Cards ===== */
.metric-card {
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    padding: 24px;
    text-align: center;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}
.metric-value {
    font-size: 32px;
    font-weight: 700;
    margin-bottom: 4px;
}
.metric-value.positive { color: #22c55e; }
.metric-value.negative { color: #ef4444; }
.metric-value.neutral { color: #111827; }
.metric-label {
    font-size: 14px;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.metric-sublabel {
    font-size: 12px;
    color: #9ca3af;
    margin-top: 4px;
}

/* ===== Recommendation Card ===== */
.recommendation-card {
    background: linear-gradient(135deg, #1f2937 0%, #374151 100%);
    border-radius: 12px;
    padding: 24px;
    color: white;
    margin: 16px 0;
}
.recommendation-title {
    font-size: 14px;
    opacity: 0.8;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 8px;
}
.recommendation-stakes {
    font-size: 32px;
    font-weight: 700;
    margin-bottom: 8px;
}
.recommendation-reason {
    font-size: 14px;
    opacity: 0.9;
}

/* ===== Action Card ===== */
.action-card {
    border-radius: 12px;
    padding: 20px;
    margin: 16px 0;
}
.action-card.move-up {
    background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
    border: 2px solid #22c55e;
}
.action-card.stay {
    background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
    border: 2px solid #3b82f6;
}
.action-card.move-down {
    background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
    border: 2px solid #f59e0b;
}
.action-card.danger {
    background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%);
    border: 2px solid #ef4444;
}
.action-title {
    font-size: 18px;
    font-weight: 600;
    margin-bottom: 8px;
    display: flex;
    align-items: center;
    gap: 8px;
}
.action-body {
    font-size: 14px;
    color: #374151;
    line-height: 1.6;
}

/* ===== Risk Gauge ===== */
.risk-gauge {
    background: #f3f4f6;
    border-radius: 12px;
    padding: 24px;
    text-align: center;
}
.risk-gauge-title {
    font-size: 14px;
    color: #6b7280;
    text-transform: uppercase;
    margin-bottom: 12px;
}
.risk-gauge-value {
    font-size: 48px;
    font-weight: 700;
}
.risk-gauge-label {
    font-size: 14px;
    color: #6b7280;
    margin-top: 8px;
}

/* ===== Progress Bar ===== */
.progress-container {
    background: #e5e7eb;
    border-radius: 8px;
    height: 24px;
    overflow: hidden;
    position: relative;
    margin: 12px 0;
}
.progress-fill {
    height: 100%;
    border-radius: 8px;
    transition: width 0.5s ease;
}
.progress-marker {
    position: absolute;
    top: 0;
    height: 100%;
    width: 3px;
    background: #1f2937;
}
.progress-labels {
    display: flex;
    justify-content: space-between;
    font-size: 12px;
    color: #6b7280;
    margin-top: 4px;
}

/* ===== Stakes Ladder ===== */
.stakes-ladder {
    display: flex;
    flex-direction: column;
    gap: 8px;
}
.stakes-step {
    display: flex;
    align-items: center;
    padding: 12px 16px;
    border-radius: 8px;
    background: #f3f4f6;
}
.stakes-step.current {
    background: #dbeafe;
    border: 2px solid #3b82f6;
}
.stakes-step.available {
    background: #dcfce7;
    border: 2px solid #22c55e;
}
.stakes-step.locked {
    opacity: 0.5;
}
.stakes-name {
    font-weight: 600;
    flex: 1;
}
.stakes-requirement {
    font-size: 13px;
    color: #6b7280;
}
.stakes-status {
    font-size: 13px;
    font-weight: 500;
}

/* ===== Info Box ===== */
.info-box {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 20px;
    margin: 16px 0;
}
.info-box-title {
    font-size: 16px;
    font-weight: 600;
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    gap: 8px;
}
.info-box-content {
    font-size: 14px;
    color: #475569;
    line-height: 1.6;
}

/* ===== Projection Card ===== */
.projection-card {
    background: linear-gradient(135deg, #faf5ff 0%, #f3e8ff 100%);
    border: 2px solid #8b5cf6;
    border-radius: 12px;
    padding: 24px;
    text-align: center;
}
.projection-title {
    font-size: 14px;
    font-weight: 600;
    color: #6b21a8;
    text-transform: uppercase;
    margin-bottom: 12px;
}
.projection-value {
    font-size: 32px;
    font-weight: 700;
    color: #7c3aed;
    margin-bottom: 8px;
}
.projection-context {
    font-size: 14px;
    color: #6b7280;
}

/* ===== Drawdown Display ===== */
.drawdown-display {
    text-align: center;
    padding: 20px;
}
.drawdown-current {
    font-size: 36px;
    font-weight: 700;
}
.drawdown-label {
    font-size: 14px;
    color: #6b7280;
    margin-top: 4px;
}
.drawdown-max {
    font-size: 14px;
    color: #9ca3af;
    margin-top: 8px;
}
</style>
""", unsafe_allow_html=True)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_user_id() -> Optional[str]:
    """Get current user's database ID from session state."""
    return st.session_state.get("user_db_id")


def get_current_bankroll() -> float:
    """Get user's current bankroll from session state."""
    return float(st.session_state.get("bankroll", 0) or 0)


def get_risk_mode() -> str:
    """Get user's current risk mode from session state."""
    return st.session_state.get("risk_mode", "balanced")


def format_money(amount: float, include_sign: bool = False) -> str:
    """Format money with optional sign."""
    if amount is None:
        return "—"
    if include_sign:
        return f"+${amount:,.2f}" if amount >= 0 else f"-${abs(amount):,.2f}"
    return f"${amount:,.2f}"


def get_stakes_for_bankroll(bankroll: float, risk_mode: str) -> dict:
    """
    Get the recommended stakes based on bankroll and risk mode.
    
    Returns the highest stakes the player can safely play.
    """
    mode = RISK_MODES.get(risk_mode, RISK_MODES["balanced"])
    required_bis = mode["buy_ins"]
    
    recommended = STAKES_CONFIG[0]  # Default to lowest
    
    for stakes in STAKES_CONFIG:
        min_bankroll = stakes["typical_bi"] * required_bis
        if bankroll >= min_bankroll:
            recommended = stakes
        else:
            break
    
    return recommended


def get_buy_ins_at_stakes(bankroll: float, stakes: dict) -> float:
    """Calculate how many buy-ins the player has at given stakes."""
    typical_bi = stakes["typical_bi"]
    if typical_bi <= 0:
        return 0
    return bankroll / typical_bi


def get_health_status(buy_ins: float) -> dict:
    """Get health status based on number of buy-ins."""
    if buy_ins >= 20:
        return HEALTH_THRESHOLDS["excellent"]
    elif buy_ins >= 15:
        return HEALTH_THRESHOLDS["healthy"]
    elif buy_ins >= 12:
        return HEALTH_THRESHOLDS["adequate"]
    elif buy_ins >= 8:
        return HEALTH_THRESHOLDS["warning"]
    else:
        return HEALTH_THRESHOLDS["danger"]


def calculate_risk_of_ruin(bankroll: float, stakes: dict, bb_per_100: float = 6.0, std_dev: float = 80.0) -> float:
    """
    Calculate approximate risk of ruin.
    
    Uses simplified formula: RoR ≈ e^(-2 * edge * bankroll / variance)
    
    For poker with:
    - Edge = win rate in BB/100
    - Variance = std deviation squared
    - Bankroll in BB
    
    This is a simplified model but gives a reasonable approximation.
    """
    if bankroll <= 0 or stakes["bb"] <= 0:
        return 1.0
    
    # Convert bankroll to big blinds
    bankroll_bb = bankroll / stakes["bb"]
    
    # Win rate per hand (BB/100 to BB/hand)
    edge_per_hand = bb_per_100 / 100
    
    if edge_per_hand <= 0:
        return 1.0  # No edge = eventual ruin
    
    # Variance per hand (std dev in BB/100 squared, converted to per hand)
    variance_per_hand = (std_dev / 10) ** 2  # Simplified
    
    # Risk of Ruin formula
    exponent = -2 * edge_per_hand * bankroll_bb / variance_per_hand
    
    # Clamp to prevent overflow
    exponent = max(-100, min(100, exponent))
    
    ror = math.exp(exponent)
    
    return min(1.0, max(0.0, ror))


def calculate_bankroll_projection(
    current_bankroll: float,
    hourly_rate: float,
    hours_per_week: float = 10,
    target_bankroll: float = None
) -> dict:
    """
    Calculate bankroll growth projection.
    
    Returns time to reach various milestones.
    """
    if hourly_rate <= 0:
        return {
            "weekly_growth": 0,
            "monthly_growth": 0,
            "time_to_target": None,
            "target": target_bankroll,
        }
    
    weekly_growth = hourly_rate * hours_per_week
    monthly_growth = weekly_growth * 4.33  # Average weeks per month
    
    if target_bankroll and target_bankroll > current_bankroll:
        needed = target_bankroll - current_bankroll
        weeks_needed = needed / weekly_growth if weekly_growth > 0 else float('inf')
        months_needed = weeks_needed / 4.33
    else:
        months_needed = None
    
    return {
        "weekly_growth": weekly_growth,
        "monthly_growth": monthly_growth,
        "time_to_target_months": months_needed,
        "target": target_bankroll,
    }


def calculate_drawdown(sessions: List[dict], current_bankroll: float) -> dict:
    """
    Calculate current and max historical drawdown.
    """
    if not sessions:
        return {
            "current_drawdown": 0,
            "current_drawdown_pct": 0,
            "max_drawdown": 0,
            "max_drawdown_pct": 0,
            "peak_bankroll": current_bankroll,
        }
    
    # Sort sessions by date
    sorted_sessions = sorted(
        sessions,
        key=lambda s: s.get("started_at", "") or ""
    )
    
    # Reconstruct bankroll history
    # Start from current and work backwards
    running_bankroll = current_bankroll
    bankroll_history = [running_bankroll]
    
    for session in reversed(sorted_sessions):
        pl = float(session.get("profit_loss", 0) or 0)
        running_bankroll -= pl  # Subtract to get previous bankroll
        bankroll_history.insert(0, running_bankroll)
    
    if not bankroll_history:
        return {
            "current_drawdown": 0,
            "current_drawdown_pct": 0,
            "max_drawdown": 0,
            "max_drawdown_pct": 0,
            "peak_bankroll": current_bankroll,
        }
    
    # Calculate peak and drawdowns
    peak = bankroll_history[0]
    max_drawdown = 0
    max_drawdown_pct = 0
    
    for bankroll in bankroll_history:
        if bankroll > peak:
            peak = bankroll
        drawdown = peak - bankroll
        if drawdown > max_drawdown:
            max_drawdown = drawdown
            max_drawdown_pct = (drawdown / peak * 100) if peak > 0 else 0
    
    # Current drawdown from peak
    current_peak = max(bankroll_history)
    current_drawdown = current_peak - current_bankroll
    current_drawdown_pct = (current_drawdown / current_peak * 100) if current_peak > 0 else 0
    
    return {
        "current_drawdown": max(0, current_drawdown),
        "current_drawdown_pct": max(0, current_drawdown_pct),
        "max_drawdown": max_drawdown,
        "max_drawdown_pct": max_drawdown_pct,
        "peak_bankroll": current_peak,
        "bankroll_history": bankroll_history,
    }


def get_next_stakes(current_stakes: dict) -> Optional[dict]:
    """Get the next higher stakes level."""
    for i, stakes in enumerate(STAKES_CONFIG):
        if stakes["name"] == current_stakes["name"]:
            if i + 1 < len(STAKES_CONFIG):
                return STAKES_CONFIG[i + 1]
    return None


def get_prev_stakes(current_stakes: dict) -> Optional[dict]:
    """Get the next lower stakes level."""
    for i, stakes in enumerate(STAKES_CONFIG):
        if stakes["name"] == current_stakes["name"]:
            if i > 0:
                return STAKES_CONFIG[i - 1]
    return None


# =============================================================================
# RENDER FUNCTIONS
# =============================================================================

def render_health_status(bankroll: float, current_stakes: dict):
    """Render the main health status card."""
    
    buy_ins = get_buy_ins_at_stakes(bankroll, current_stakes)
    status = get_health_status(buy_ins)
    
    status_class = "excellent" if buy_ins >= 20 else "healthy" if buy_ins >= 15 else "adequate" if buy_ins >= 12 else "warning" if buy_ins >= 8 else "danger"
    
    emoji_map = {
        "excellent": "💪",
        "healthy": "✅",
        "adequate": "⚠️",
        "warning": "⚠️",
        "danger": "🚨",
    }
    
    st.markdown(f"""
        <div class="health-card {status_class}">
            <div class="health-status-emoji">{emoji_map[status_class]}</div>
            <div class="health-status-label">{status['label']} Bankroll</div>
            <div class="health-status-bankroll">{format_money(bankroll)}</div>
            <div class="health-status-context">
                {buy_ins:.1f} buy-ins at {current_stakes['name']}
            </div>
        </div>
    """, unsafe_allow_html=True)


def render_stakes_recommendation(bankroll: float, risk_mode: str, current_stakes: dict):
    """Render stakes recommendation with action card."""
    
    recommended = get_stakes_for_bankroll(bankroll, risk_mode)
    mode = RISK_MODES.get(risk_mode, RISK_MODES["balanced"])
    
    buy_ins_at_current = get_buy_ins_at_stakes(bankroll, current_stakes)
    buy_ins_at_recommended = get_buy_ins_at_stakes(bankroll, recommended)
    
    # Determine action
    if recommended["bb"] > current_stakes["bb"]:
        # Can move up
        action_class = "move-up"
        action_emoji = "📈"
        action_title = "Ready to Move Up!"
        next_stakes = get_next_stakes(current_stakes)
        if next_stakes:
            min_needed = next_stakes["typical_bi"] * mode["buy_ins"]
            action_body = f"""
                Your bankroll supports <strong>{recommended['name']}</strong> stakes. 
                You have {buy_ins_at_recommended:.1f} buy-ins at this level, which exceeds 
                the {mode['buy_ins']} buy-in requirement for {mode['name']} mode.
            """
        else:
            action_body = "You're already at the highest tracked stakes level!"
    elif recommended["bb"] < current_stakes["bb"]:
        # Should move down
        action_class = "move-down"
        action_emoji = "📉"
        action_title = "Consider Moving Down"
        action_body = f"""
            Your bankroll ({buy_ins_at_current:.1f} buy-ins at {current_stakes['name']}) 
            is below the recommended {mode['buy_ins']} buy-ins for {mode['name']} mode. 
            Consider moving to <strong>{recommended['name']}</strong> to protect your bankroll.
        """
    else:
        # Stay at current
        action_class = "stay"
        action_emoji = "✅"
        action_title = "You're at the Right Stakes"
        
        # Calculate progress to next level
        next_stakes = get_next_stakes(current_stakes)
        if next_stakes:
            min_needed = next_stakes["typical_bi"] * mode["buy_ins"]
            needed = min_needed - bankroll
            if needed > 0:
                action_body = f"""
                    You have {buy_ins_at_current:.1f} buy-ins at {current_stakes['name']}, 
                    which is good for {mode['name']} mode. 
                    You need <strong>{format_money(needed)}</strong> more to move up to {next_stakes['name']}.
                """
            else:
                action_body = f"You have {buy_ins_at_current:.1f} buy-ins and are well-positioned at your current stakes."
        else:
            action_body = "You're at the highest stakes level we track. Great work!"
    
    # Check for danger zone
    if buy_ins_at_current < 8:
        action_class = "danger"
        action_emoji = "🚨"
        action_title = "Bankroll Warning"
        action_body = f"""
            <strong>Your bankroll is critically low</strong> for {current_stakes['name']} stakes. 
            With only {buy_ins_at_current:.1f} buy-ins, you're at high risk of going broke during a 
            normal downswing. Move down to <strong>{recommended['name']}</strong> immediately to protect your bankroll.
        """
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown(f"""
            <div class="recommendation-card">
                <div class="recommendation-title">Recommended Stakes ({mode['name']} Mode)</div>
                <div class="recommendation-stakes">{recommended['name']}</div>
                <div class="recommendation-reason">
                    Based on {format_money(bankroll)} bankroll • {mode['buy_ins']} buy-ins required
                </div>
            </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value neutral">{buy_ins_at_recommended:.1f}</div>
                <div class="metric-label">Buy-ins Available</div>
                <div class="metric-sublabel">at {recommended['name']}</div>
            </div>
        """, unsafe_allow_html=True)
    
    # Action card
    st.markdown(f"""
        <div class="action-card {action_class}">
            <div class="action-title">{action_emoji} {action_title}</div>
            <div class="action-body">{action_body}</div>
        </div>
    """, unsafe_allow_html=True)


def render_risk_of_ruin(bankroll: float, current_stakes: dict, bb_per_100: float):
    """Render risk of ruin calculator."""
    
    st.markdown("### 🎲 Risk of Ruin")
    
    ror = calculate_risk_of_ruin(bankroll, current_stakes, bb_per_100)
    ror_pct = ror * 100
    
    # Determine color and label
    if ror_pct < 1:
        color = "#22c55e"
        label = "Very Low"
        description = "Your bankroll is well-protected against normal variance."
    elif ror_pct < 5:
        color = "#22c55e"
        label = "Low"
        description = "You have a healthy buffer against downswings."
    elif ror_pct < 15:
        color = "#f59e0b"
        label = "Moderate"
        description = "Consider building more bankroll cushion."
    elif ror_pct < 30:
        color = "#f59e0b"
        label = "Elevated"
        description = "Your bankroll is at risk. Consider moving down in stakes."
    else:
        color = "#ef4444"
        label = "High"
        description = "Serious risk of going broke. Move down immediately."
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.markdown(f"""
            <div class="risk-gauge">
                <div class="risk-gauge-title">Risk of Ruin</div>
                <div class="risk-gauge-value" style="color: {color};">{ror_pct:.1f}%</div>
                <div class="risk-gauge-label">{label}</div>
            </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
            <div class="info-box">
                <div class="info-box-title">📊 What This Means</div>
                <div class="info-box-content">
                    {description}
                    <br><br>
                    <strong>Risk of Ruin</strong> estimates the probability of losing your entire bankroll 
                    based on your current stakes, win rate ({bb_per_100:+.1f} BB/100), and bankroll size.
                    <br><br>
                    <em>A risk under 5% is generally considered safe for serious players.</em>
                </div>
            </div>
        """, unsafe_allow_html=True)


def render_bankroll_projection(bankroll: float, hourly_rate: float, current_stakes: dict, risk_mode: str):
    """Render bankroll growth projection."""
    
    st.markdown("### 📈 Bankroll Projection")
    
    # Get next stakes level for target
    next_stakes = get_next_stakes(current_stakes)
    mode = RISK_MODES.get(risk_mode, RISK_MODES["balanced"])
    
    if next_stakes:
        target = next_stakes["typical_bi"] * mode["buy_ins"]
    else:
        target = bankroll * 1.5  # 50% growth if at max stakes
    
    projection = calculate_bankroll_projection(
        current_bankroll=bankroll,
        hourly_rate=hourly_rate,
        hours_per_week=10,
        target_bankroll=target
    )
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        weekly = projection["weekly_growth"]
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value {'positive' if weekly >= 0 else 'negative'}">{format_money(weekly, include_sign=True)}</div>
                <div class="metric-label">Weekly Growth</div>
                <div class="metric-sublabel">at 10 hrs/week</div>
            </div>
        """, unsafe_allow_html=True)
    
    with col2:
        monthly = projection["monthly_growth"]
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value {'positive' if monthly >= 0 else 'negative'}">{format_money(monthly, include_sign=True)}</div>
                <div class="metric-label">Monthly Growth</div>
                <div class="metric-sublabel">projected</div>
            </div>
        """, unsafe_allow_html=True)
    
    with col3:
        months = projection["time_to_target_months"]
        if months and months < 100 and months > 0:
            time_text = f"{months:.1f} months"
        elif months and months <= 0:
            time_text = "Ready now!"
        else:
            time_text = "—"
        
        next_stakes_name = next_stakes["name"] if next_stakes else "Max"
        st.markdown(f"""
            <div class="projection-card">
                <div class="projection-title">Time to {next_stakes_name}</div>
                <div class="projection-value">{time_text}</div>
                <div class="projection-context">Need {format_money(target)} to move up</div>
            </div>
        """, unsafe_allow_html=True)


def render_drawdown_analysis(sessions: List[dict], bankroll: float):
    """Render drawdown analysis."""
    
    st.markdown("### 📉 Drawdown Analysis")
    
    drawdown = calculate_drawdown(sessions, bankroll)
    
    col1, col2 = st.columns(2)
    
    with col1:
        current_dd = drawdown["current_drawdown"]
        current_dd_pct = drawdown["current_drawdown_pct"]
        
        if current_dd_pct == 0:
            color = "#22c55e"
            label = "At Peak"
        elif current_dd_pct < 10:
            color = "#22c55e"
            label = "Minor"
        elif current_dd_pct < 20:
            color = "#f59e0b"
            label = "Moderate"
        else:
            color = "#ef4444"
            label = "Significant"
        
        st.markdown(f"""
            <div class="metric-card">
                <div class="drawdown-display">
                    <div class="drawdown-current" style="color: {color};">
                        {current_dd_pct:.1f}%
                    </div>
                    <div class="drawdown-label">Current Drawdown ({label})</div>
                    <div class="drawdown-max">{format_money(current_dd)} below peak</div>
                </div>
            </div>
        """, unsafe_allow_html=True)
    
    with col2:
        max_dd = drawdown["max_drawdown"]
        max_dd_pct = drawdown["max_drawdown_pct"]
        peak = drawdown["peak_bankroll"]
        
        st.markdown(f"""
            <div class="metric-card">
                <div class="drawdown-display">
                    <div class="drawdown-current" style="color: #6b7280;">
                        {max_dd_pct:.1f}%
                    </div>
                    <div class="drawdown-label">Max Historical Drawdown</div>
                    <div class="drawdown-max">Peak: {format_money(peak)}</div>
                </div>
            </div>
        """, unsafe_allow_html=True)
    
    # Context
    st.markdown("""
        <div class="info-box">
            <div class="info-box-title">💡 Understanding Drawdowns</div>
            <div class="info-box-content">
                <strong>Drawdown</strong> measures how far your bankroll has fallen from its peak. 
                Even winning players experience drawdowns of 20-30% during normal variance.
                <br><br>
                A healthy bankroll (15+ buy-ins) can withstand these swings without needing to move down in stakes.
            </div>
        </div>
    """, unsafe_allow_html=True)


def render_stakes_ladder(bankroll: float, risk_mode: str, current_stakes: dict):
    """Render visual stakes ladder."""
    
    st.markdown("### 🪜 Stakes Ladder")
    
    mode = RISK_MODES.get(risk_mode, RISK_MODES["balanced"])
    required_bis = mode["buy_ins"]
    
    for stakes in STAKES_CONFIG:
        min_bankroll = stakes["typical_bi"] * required_bis
        buy_ins = get_buy_ins_at_stakes(bankroll, stakes)
        
        is_current = stakes["name"] == current_stakes["name"]
        is_available = bankroll >= min_bankroll
        
        if is_current:
            css_class = "current"
            status = "📍 Current"
            status_color = "#3b82f6"
        elif is_available:
            css_class = "available"
            status = "✅ Available"
            status_color = "#22c55e"
        else:
            css_class = "locked"
            needed = min_bankroll - bankroll
            status = f"🔒 Need {format_money(needed)}"
            status_color = "#9ca3af"
        
        st.markdown(f"""
            <div class="stakes-step {css_class}">
                <div class="stakes-name">{stakes['name']}</div>
                <div class="stakes-requirement">
                    {format_money(min_bankroll)} required ({required_bis} buy-ins)
                </div>
                <div class="stakes-status" style="color: {status_color};">{status}</div>
            </div>
        """, unsafe_allow_html=True)


def render_risk_mode_selector(current_mode: str):
    """Render risk mode selector with explanations."""
    
    st.markdown("### ⚙️ Risk Mode")
    
    cols = st.columns(3)
    
    for i, (mode_key, mode) in enumerate(RISK_MODES.items()):
        with cols[i]:
            is_selected = mode_key == current_mode
            border = f"3px solid {mode['color']}" if is_selected else "1px solid #e5e7eb"
            bg = "#f8fafc" if is_selected else "white"
            
            st.markdown(f"""
                <div style="border: {border}; background: {bg}; border-radius: 12px; padding: 16px; text-align: center;">
                    <div style="font-size: 32px; margin-bottom: 8px;">{mode['emoji']}</div>
                    <div style="font-size: 16px; font-weight: 600; margin-bottom: 4px;">{mode['name']}</div>
                    <div style="font-size: 24px; font-weight: 700; color: {mode['color']}; margin-bottom: 8px;">
                        {mode['buy_ins']} Buy-ins
                    </div>
                    <div style="font-size: 12px; color: #6b7280;">{mode['description']}</div>
                </div>
            """, unsafe_allow_html=True)
    
    # Selector
    st.markdown("")
    new_mode = st.radio(
        "Select Risk Mode",
        options=list(RISK_MODES.keys()),
        format_func=lambda x: f"{RISK_MODES[x]['emoji']} {RISK_MODES[x]['name']}",
        index=list(RISK_MODES.keys()).index(current_mode),
        horizontal=True,
        key="risk_mode_selector"
    )
    
    if new_mode != current_mode:
        st.session_state["risk_mode"] = new_mode
        st.rerun()


def render_bankroll_editor(current_bankroll: float):
    """Render bankroll editor."""
    
    st.markdown("### 💰 Update Bankroll")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        new_bankroll = st.number_input(
            "Current Bankroll",
            min_value=0.0,
            value=current_bankroll,
            step=100.0,
            format="%.2f",
            key="bankroll_input"
        )
    
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Update Bankroll", type="primary", use_container_width=True):
            st.session_state["bankroll"] = new_bankroll
            st.success(f"Bankroll updated to {format_money(new_bankroll)}")
            st.rerun()


def render_empty_state():
    """Render empty state when no bankroll is set."""
    
    st.markdown("""
        <div style="text-align: center; padding: 48px; color: #6b7280;">
            <div style="font-size: 48px; margin-bottom: 16px;">💰</div>
            <h3>Set Your Bankroll</h3>
            <p>Enter your poker bankroll to see your health status and recommendations.</p>
        </div>
    """, unsafe_allow_html=True)
    
    bankroll = st.number_input(
        "Enter your bankroll",
        min_value=0.0,
        value=1000.0,
        step=100.0,
        format="%.2f"
    )
    
    if st.button("Set Bankroll", type="primary"):
        st.session_state["bankroll"] = bankroll
        st.rerun()


# =============================================================================
# MAIN PAGE
# =============================================================================

def main():
    """Main render function for Bankroll Health page."""
    
    st.title("💰 Bankroll Health")
    st.caption("Monitor your bankroll safety and get stakes recommendations")
    
    user_id = get_user_id()
    
    if not user_id:
        st.warning("Please log in to view your bankroll health.")
        return
    
    # Get current bankroll
    bankroll = get_current_bankroll()
    
    if bankroll <= 0:
        render_empty_state()
        return
    
    # Get risk mode and calculate recommended stakes
    risk_mode = get_risk_mode()
    recommended_stakes = get_stakes_for_bankroll(bankroll, risk_mode)
    
    # Get session data for projections
    sessions = get_user_sessions(user_id, limit=500)
    
    # Calculate stats for projections
    total_profit = sum(float(s.get("profit_loss", 0) or 0) for s in sessions) if sessions else 0
    total_hours = sum(
        (datetime.fromisoformat(s.get("ended_at", s.get("started_at", "")).replace("Z", "+00:00")) -
         datetime.fromisoformat(s.get("started_at", "").replace("Z", "+00:00"))).total_seconds() / 3600
        for s in sessions if s.get("started_at")
    ) if sessions else 0
    
    hourly_rate = total_profit / total_hours if total_hours > 0 else 0
    
    # Calculate BB/100 for risk of ruin
    total_hands = sum(int(s.get("hands_played", 0) or 0) for s in sessions) if sessions else 0
    total_bb_won = sum(
        float(s.get("profit_loss", 0) or 0) / float(s.get("bb_size", 2.0) or 2.0)
        for s in sessions
    ) if sessions else 0
    bb_per_100 = (total_bb_won / total_hands * 100) if total_hands > 0 else 6.0  # Default to expected
    
    # ===== HEALTH STATUS =====
    render_health_status(bankroll, recommended_stakes)
    
    # ===== STAKES RECOMMENDATION =====
    render_stakes_recommendation(bankroll, risk_mode, recommended_stakes)
    
    st.markdown("---")
    
    # ===== TABBED SECTIONS =====
    tab1, tab2, tab3, tab4 = st.tabs([
        "🎲 Risk Analysis",
        "📈 Projections",
        "🪜 Stakes Ladder",
        "⚙️ Settings"
    ])
    
    with tab1:
        render_risk_of_ruin(bankroll, recommended_stakes, bb_per_100)
        render_drawdown_analysis(sessions, bankroll)
    
    with tab2:
        render_bankroll_projection(bankroll, hourly_rate, recommended_stakes, risk_mode)
    
    with tab3:
        render_stakes_ladder(bankroll, risk_mode, recommended_stakes)
    
    with tab4:
        render_risk_mode_selector(risk_mode)
        st.markdown("---")
        render_bankroll_editor(bankroll)


if __name__ == "__main__":
    main()