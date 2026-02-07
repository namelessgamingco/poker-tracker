# =============================================================================
# 03_Player_Stats.py — PREMIUM Player Stats & Achievements Dashboard
# =============================================================================
# 
# PREMIUM FEATURES ($299/month value):
# 1. Hourly Win Rate - Tangible earnings metric ($XX/hour)
# 2. 95% Confidence Interval - Statistical validity on win rate
# 3. Projected Annual Earnings - Based on actual player data
# 4. Performance vs Expected - Visual comparison to optimal play
# 5. Session Length Optimization - Data-driven session recommendations
# 6. Monthly Trend Analysis - BB/100 over time (am I improving?)
# 7. Badge System - Gamification with tier progression
# 8. Achievement Badges - Unlockable milestones
# 9. Personalized EV Messaging - Uses their actual data
# 10. Admin/Discord Export - Badge info for community features
#
# =============================================================================

import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
import math

st.set_page_config(
    page_title="Player Stats | Poker Decision App",
    page_icon="📊",
    layout="wide",
)

from auth import require_auth
from sidebar import render_sidebar
from db import (
    get_user_sessions,
    get_player_stats,
    get_session_outcome_summary,
)

# ---------- Auth Gate ----------
user = require_auth()
render_sidebar()


# =============================================================================
# CONFIGURATION: Badge Tiers & Achievements
# =============================================================================

PROFIT_TIERS = [
    {
        "name": "Grinder",
        "emoji": "🌱",
        "min": 0,
        "max": 1000,
        "color": "#6b7280",
        "description": "Starting the journey"
    },
    {
        "name": "Winning Player",
        "emoji": "📈",
        "min": 1000,
        "max": 5000,
        "color": "#22c55e",
        "description": "Proven profitable"
    },
    {
        "name": "Shark",
        "emoji": "🎯",
        "min": 5000,
        "max": 15000,
        "color": "#3b82f6",
        "description": "Serious competitor"
    },
    {
        "name": "High Roller",
        "emoji": "💰",
        "min": 15000,
        "max": 35000,
        "color": "#f59e0b",
        "description": "Significant earnings"
    },
    {
        "name": "Diamond Crusher",
        "emoji": "💎",
        "min": 35000,
        "max": 75000,
        "color": "#8b5cf6",
        "description": "Elite status"
    },
    {
        "name": "Poker Royalty",
        "emoji": "👑",
        "min": 75000,
        "max": None,
        "color": "#ec4899",
        "description": "Legendary player"
    },
]

ACHIEVEMENT_BADGES = [
    {
        "id": "iron_discipline",
        "name": "Iron Discipline",
        "emoji": "🛡️",
        "description": "Protected bankroll with stop-loss 50+ times",
        "check": lambda stats: stats.get("stop_loss_count", 0) >= 50,
        "progress_key": "stop_loss_count",
        "target": 50,
    },
    {
        "id": "profit_locker",
        "name": "Profit Locker",
        "emoji": "🔒",
        "description": "Locked in profits with stop-win 25+ times",
        "check": lambda stats: stats.get("stop_win_count", 0) >= 25,
        "progress_key": "stop_win_count",
        "target": 25,
    },
    {
        "id": "marathon_player",
        "name": "Marathon Player",
        "emoji": "⏱️",
        "description": "500+ hours at the tables",
        "check": lambda stats: stats.get("total_hours", 0) >= 500,
        "progress_key": "total_hours",
        "target": 500,
    },
    {
        "id": "volume_king",
        "name": "Volume King",
        "emoji": "📊",
        "description": "Played 10,000+ hands",
        "check": lambda stats: stats.get("total_hands", 0) >= 10000,
        "progress_key": "total_hands",
        "target": 10000,
    },
    {
        "id": "century_club",
        "name": "Century Club",
        "emoji": "💯",
        "description": "Completed 100 sessions",
        "check": lambda stats: stats.get("total_sessions", 0) >= 100,
        "progress_key": "total_sessions",
        "target": 100,
    },
    {
        "id": "first_thousand",
        "name": "First Grand",
        "emoji": "🎉",
        "description": "Earned your first $1,000",
        "check": lambda stats: stats.get("total_profit", 0) >= 1000,
        "progress_key": "total_profit",
        "target": 1000,
    },
    {
        "id": "five_figure_club",
        "name": "Five Figure Club",
        "emoji": "🏆",
        "description": "Lifetime earnings of $10,000+",
        "check": lambda stats: stats.get("total_profit", 0) >= 10000,
        "progress_key": "total_profit",
        "target": 10000,
    },
    {
        "id": "consistent_winner",
        "name": "Hot Streak",
        "emoji": "🔥",
        "description": "10+ winning sessions in a row",
        "check": lambda stats: stats.get("max_win_streak", 0) >= 10,
        "progress_key": "max_win_streak",
        "target": 10,
    },
]

# Expected win rate for optimal strategy (from our spec: +6-7 BB/100)
EXPECTED_BB_PER_100 = 6.0


# =============================================================================
# CUSTOM CSS - Premium Styling
# =============================================================================

st.markdown("""
<style>
/* ===== Stat Cards ===== */
.stat-card {
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    padding: 24px;
    text-align: center;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}
.stat-card-value {
    font-size: 36px;
    font-weight: 700;
    margin-bottom: 4px;
}
.stat-card-value.positive { color: #22c55e; }
.stat-card-value.negative { color: #ef4444; }
.stat-card-value.neutral { color: #111827; }
.stat-card-label {
    font-size: 14px;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.stat-card-sublabel {
    font-size: 12px;
    color: #9ca3af;
    margin-top: 4px;
}

/* ===== Premium Stat Cards (Dark) ===== */
.premium-stat-card {
    background: linear-gradient(135deg, #1f2937 0%, #374151 100%);
    border-radius: 12px;
    padding: 24px;
    text-align: center;
    color: white;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
}
.premium-stat-value {
    font-size: 42px;
    font-weight: 700;
    margin-bottom: 4px;
}
.premium-stat-label {
    font-size: 14px;
    opacity: 0.8;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.premium-stat-context {
    font-size: 13px;
    opacity: 0.7;
    margin-top: 8px;
}

/* ===== Badge Display ===== */
.badge-card {
    background: linear-gradient(135deg, #1f2937 0%, #374151 100%);
    border-radius: 16px;
    padding: 32px;
    text-align: center;
    color: white;
    margin-bottom: 24px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
}
.badge-emoji { font-size: 64px; margin-bottom: 16px; }
.badge-name { font-size: 28px; font-weight: 700; margin-bottom: 8px; }
.badge-description { font-size: 16px; opacity: 0.8; margin-bottom: 16px; }
.badge-progress {
    background: rgba(255,255,255,0.2);
    border-radius: 8px;
    height: 12px;
    overflow: hidden;
    margin-top: 16px;
}
.badge-progress-fill {
    height: 100%;
    border-radius: 8px;
    transition: width 0.5s ease;
}
.badge-progress-text {
    font-size: 14px;
    margin-top: 8px;
    opacity: 0.8;
}

/* ===== Achievement Badges ===== */
.achievement-badge {
    background: white;
    border: 2px solid #e5e7eb;
    border-radius: 12px;
    padding: 16px;
    text-align: center;
    transition: all 0.2s ease;
}
.achievement-badge.unlocked {
    border-color: #22c55e;
    background: #f0fdf4;
}
.achievement-badge.locked {
    opacity: 0.5;
    filter: grayscale(100%);
}
.achievement-emoji { font-size: 32px; margin-bottom: 8px; }
.achievement-name { font-size: 14px; font-weight: 600; margin-bottom: 4px; }
.achievement-desc { font-size: 12px; color: #6b7280; }
.achievement-progress { font-size: 11px; color: #9ca3af; margin-top: 8px; }

/* ===== Insight Cards ===== */
.insight-card {
    background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
    border: 1px solid #3b82f6;
    border-radius: 12px;
    padding: 20px;
    margin: 16px 0;
}
.insight-card.success {
    background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
    border-color: #22c55e;
}
.insight-card.warning {
    background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%);
    border-color: #f59e0b;
}
.insight-title {
    font-size: 16px;
    font-weight: 600;
    margin-bottom: 8px;
    display: flex;
    align-items: center;
    gap: 8px;
}
.insight-body {
    font-size: 14px;
    color: #374151;
    line-height: 1.6;
}
.insight-highlight {
    font-weight: 700;
    color: #1f2937;
}

/* ===== Confidence Interval Display ===== */
.confidence-display {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    margin-top: 8px;
}
.confidence-range {
    font-size: 14px;
    color: #9ca3af;
    background: rgba(255,255,255,0.3);
    padding: 4px 12px;
    border-radius: 16px;
}

/* ===== Performance Comparison Bar ===== */
.performance-bar {
    height: 24px;
    background: #e5e7eb;
    border-radius: 12px;
    overflow: hidden;
    position: relative;
    margin: 12px 0;
}
.performance-fill {
    height: 100%;
    border-radius: 12px;
    transition: width 0.5s ease;
}
.performance-marker {
    position: absolute;
    top: 0;
    height: 100%;
    width: 3px;
    background: #1f2937;
}
.performance-label {
    display: flex;
    justify-content: space-between;
    font-size: 12px;
    color: #6b7280;
    margin-top: 4px;
}

/* ===== Day of Week Analysis ===== */
.day-stat {
    text-align: center;
    padding: 12px 8px;
    background: #f3f4f6;
    border-radius: 8px;
}
.day-stat.best {
    background: #dcfce7;
    border: 2px solid #22c55e;
}
.day-stat.worst {
    background: #fee2e2;
    border: 2px solid #ef4444;
}
.day-name { font-size: 12px; color: #6b7280; margin-bottom: 4px; }
.day-value { font-size: 16px; font-weight: 600; }

/* ===== Session Optimization Cards ===== */
.optimization-card {
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    padding: 20px;
    text-align: center;
}
.optimization-card.recommended {
    border: 2px solid #22c55e;
    background: #f0fdf4;
}
.optimization-label {
    font-size: 12px;
    color: #6b7280;
    text-transform: uppercase;
    margin-bottom: 8px;
}
.optimization-value {
    font-size: 24px;
    font-weight: 700;
    color: #111827;
}
.optimization-subtext {
    font-size: 13px;
    color: #6b7280;
    margin-top: 4px;
}

/* ===== Empty State ===== */
.empty-state {
    text-align: center;
    padding: 48px;
    color: #6b7280;
}
.empty-state-icon { font-size: 48px; margin-bottom: 16px; }

/* ===== EV Journey Box ===== */
.ev-journey-box {
    background: linear-gradient(135deg, #1e40af 0%, #3b82f6 100%);
    color: white;
    border-radius: 12px;
    padding: 24px;
    margin-top: 24px;
}
.ev-journey-title {
    font-size: 20px;
    font-weight: 600;
    margin-bottom: 12px;
}
.ev-journey-body {
    font-size: 16px;
    line-height: 1.6;
    opacity: 0.95;
}
</style>
""", unsafe_allow_html=True)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_user_id() -> Optional[str]:
    """Get current user's database ID from session state."""
    return st.session_state.get("user_db_id")


def format_money(amount: float, include_sign: bool = True) -> str:
    """Format money with optional sign."""
    if amount is None:
        return "—"
    if include_sign:
        return f"+${amount:,.2f}" if amount >= 0 else f"-${abs(amount):,.2f}"
    return f"${abs(amount):,.2f}"


def format_bb_per_100(bb_per_100: float) -> str:
    """Format BB/100 with sign."""
    if bb_per_100 is None:
        return "—"
    return f"{bb_per_100:+.1f}"


def get_session_duration_minutes(session: dict) -> int:
    """Calculate session duration in minutes."""
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


def parse_session_datetime(session: dict) -> Optional[datetime]:
    """Parse session started_at to datetime."""
    started_at = session.get("started_at")
    if not started_at:
        return None
    try:
        return datetime.fromisoformat(started_at.replace("Z", "+00:00"))
    except Exception:
        return None


# =============================================================================
# PREMIUM CALCULATION FUNCTIONS
# =============================================================================

def calculate_confidence_interval(sessions: List[dict], confidence: float = 0.95) -> Tuple[float, float, float]:
    """
    Calculate win rate with 95% confidence interval.
    
    Returns:
        Tuple of (mean_bb_per_100, lower_bound, upper_bound)
    
    Uses standard error calculation for BB/100 across sessions.
    This gives users statistical confidence in their win rate.
    """
    if not sessions or len(sessions) < 5:
        return (0, 0, 0)
    
    # Calculate BB/100 for each session
    bb_per_100_list = []
    for s in sessions:
        hands = int(s.get("hands_played", 0) or 0)
        bb_size = float(s.get("bb_size", 2.0) or 2.0)
        pl = float(s.get("profit_loss", 0) or 0)
        
        if hands > 0 and bb_size > 0:
            bb_won = pl / bb_size
            session_bb_per_100 = (bb_won / hands) * 100
            bb_per_100_list.append(session_bb_per_100)
    
    if len(bb_per_100_list) < 2:
        return (0, 0, 0)
    
    # Calculate mean and standard deviation
    mean = sum(bb_per_100_list) / len(bb_per_100_list)
    variance = sum((x - mean) ** 2 for x in bb_per_100_list) / (len(bb_per_100_list) - 1)
    std_dev = math.sqrt(variance)
    
    # Standard error of the mean
    std_error = std_dev / math.sqrt(len(bb_per_100_list))
    
    # Z-score for 95% confidence interval
    z_score = 1.96
    margin = z_score * std_error
    
    return (mean, mean - margin, mean + margin)


def calculate_hourly_rate(stats: dict) -> float:
    """
    Calculate hourly win rate in dollars.
    
    This is the most tangible metric for users - "I make $X per hour playing poker"
    """
    total_profit = stats.get("total_profit", 0)
    total_hours = stats.get("total_hours", 0)
    
    if total_hours > 0:
        return total_profit / total_hours
    return 0


def calculate_annual_projection(stats: dict) -> dict:
    """
    Calculate projected annual earnings based on current performance.
    
    Assumes 500 sessions/year (roughly 10/week) as baseline for serious player.
    Provides confidence level based on sample size.
    """
    total_profit = stats.get("total_profit", 0)
    total_sessions = stats.get("total_sessions", 0)
    total_hours = stats.get("total_hours", 0)
    
    if total_sessions < 5:
        return {
            "projected_annual": 0,
            "confidence": "low",
            "sessions_per_year": 500,
            "hours_per_year": 0,
            "profit_per_session": 0,
        }
    
    # Calculate profit per session
    profit_per_session = total_profit / total_sessions
    
    # Calculate average session length
    avg_session_hours = total_hours / total_sessions if total_sessions > 0 else 2
    
    # Project to 500 sessions/year (reasonable for serious player)
    projected_annual = profit_per_session * 500
    projected_hours = avg_session_hours * 500
    
    # Confidence based on sample size
    if total_sessions >= 100:
        confidence = "high"
    elif total_sessions >= 50:
        confidence = "medium"
    else:
        confidence = "low"
    
    return {
        "projected_annual": projected_annual,
        "confidence": confidence,
        "sessions_per_year": 500,
        "hours_per_year": projected_hours,
        "profit_per_session": profit_per_session,
    }


def calculate_session_length_performance(sessions: List[dict]) -> dict:
    """
    Analyze performance by session length to find optimal duration.
    
    Buckets:
    - Short: Under 1.5 hours
    - Optimal: 1.5 - 3 hours (research shows best decision-making)
    - Long: Over 3 hours (fatigue typically sets in)
    """
    buckets = {
        "short": {"label": "Under 1.5 hrs", "min": 0, "max": 90, "sessions": [], "profit": 0},
        "optimal": {"label": "1.5 - 3 hrs", "min": 90, "max": 180, "sessions": [], "profit": 0},
        "long": {"label": "Over 3 hrs", "min": 180, "max": 99999, "sessions": [], "profit": 0},
    }
    
    for s in sessions:
        duration = get_session_duration_minutes(s)
        pl = float(s.get("profit_loss", 0) or 0)
        
        for key, bucket in buckets.items():
            if bucket["min"] <= duration < bucket["max"]:
                bucket["sessions"].append(s)
                bucket["profit"] += pl
                break
    
    # Calculate averages
    for key, bucket in buckets.items():
        count = len(bucket["sessions"])
        bucket["count"] = count
        bucket["avg_profit"] = bucket["profit"] / count if count > 0 else 0
    
    # Find best bucket (by average profit, with minimum 3 sessions)
    valid_buckets = {k: v for k, v in buckets.items() if v["count"] >= 3}
    if valid_buckets:
        best_key = max(valid_buckets.keys(), key=lambda k: valid_buckets[k]["avg_profit"])
    else:
        best_key = "optimal"  # Default recommendation
    
    return {
        "buckets": buckets,
        "best": best_key,
        "recommendation": buckets[best_key]["label"],
    }


def calculate_aggregate_stats(sessions: List[dict]) -> dict:
    """
    Calculate comprehensive aggregate statistics from all sessions.
    
    Returns a dict with all metrics needed for the dashboard.
    """
    if not sessions:
        return {
            "total_sessions": 0, "total_hands": 0, "total_hours": 0, "total_profit": 0,
            "overall_bb_per_100": 0, "winning_sessions": 0, "losing_sessions": 0,
            "breakeven_sessions": 0, "win_rate_pct": 0, "avg_session_profit": 0,
            "avg_session_duration": 0, "best_session": 0, "worst_session": 0,
            "max_win_streak": 0, "max_lose_streak": 0, "stop_loss_count": 0,
            "stop_win_count": 0, "stakes_breakdown": {}, "day_breakdown": {},
            "monthly_breakdown": {}, "primary_stakes": "$1/$2", "primary_bb_size": 2.0,
        }
    
    # Basic counts
    total_sessions = len(sessions)
    total_hands = sum(int(s.get("hands_played", 0) or 0) for s in sessions)
    total_minutes = sum(get_session_duration_minutes(s) for s in sessions)
    total_hours = total_minutes / 60
    
    # Profit calculations
    total_profit = sum(float(s.get("profit_loss", 0) or 0) for s in sessions)
    
    # BB/100 calculation (weighted by hands)
    total_bb_won = 0
    for s in sessions:
        bb_size = float(s.get("bb_size", 2.0) or 2.0)
        pl = float(s.get("profit_loss", 0) or 0)
        total_bb_won += pl / bb_size if bb_size > 0 else 0
    
    overall_bb_per_100 = (total_bb_won / total_hands * 100) if total_hands > 0 else 0
    
    # Win/Loss counts
    winning_sessions = sum(1 for s in sessions if float(s.get("profit_loss", 0) or 0) > 0)
    losing_sessions = sum(1 for s in sessions if float(s.get("profit_loss", 0) or 0) < 0)
    breakeven_sessions = total_sessions - winning_sessions - losing_sessions
    win_rate_pct = (winning_sessions / total_sessions * 100) if total_sessions > 0 else 0
    
    # Averages
    avg_session_profit = total_profit / total_sessions if total_sessions > 0 else 0
    avg_session_duration = total_minutes / total_sessions if total_sessions > 0 else 0
    
    # Best/Worst sessions
    profits = [float(s.get("profit_loss", 0) or 0) for s in sessions]
    best_session = max(profits) if profits else 0
    worst_session = min(profits) if profits else 0
    
    # Win/Loss streaks
    max_win_streak = 0
    max_lose_streak = 0
    current_win_streak = 0
    current_lose_streak = 0
    
    sorted_sessions = sorted(
        sessions,
        key=lambda s: parse_session_datetime(s) or datetime.min.replace(tzinfo=timezone.utc)
    )
    
    for s in sorted_sessions:
        pl = float(s.get("profit_loss", 0) or 0)
        if pl > 0:
            current_win_streak += 1
            current_lose_streak = 0
            max_win_streak = max(max_win_streak, current_win_streak)
        elif pl < 0:
            current_lose_streak += 1
            current_win_streak = 0
            max_lose_streak = max(max_lose_streak, current_lose_streak)
        else:
            current_win_streak = 0
            current_lose_streak = 0
    
    # End reason counts (for achievements)
    stop_loss_count = sum(1 for s in sessions if s.get("end_reason") == "stop_loss")
    stop_win_count = sum(1 for s in sessions if s.get("end_reason") == "stop_win")
    
    # Stakes breakdown
    stakes_breakdown = {}
    for s in sessions:
        stakes = s.get("stakes", "Unknown")
        if stakes not in stakes_breakdown:
            stakes_breakdown[stakes] = {"sessions": 0, "hands": 0, "profit": 0, "bb_won": 0}
        stakes_breakdown[stakes]["sessions"] += 1
        stakes_breakdown[stakes]["hands"] += int(s.get("hands_played", 0) or 0)
        stakes_breakdown[stakes]["profit"] += float(s.get("profit_loss", 0) or 0)
        bb_size = float(s.get("bb_size", 2.0) or 2.0)
        stakes_breakdown[stakes]["bb_won"] += float(s.get("profit_loss", 0) or 0) / bb_size if bb_size > 0 else 0
    
    # Calculate BB/100 for each stake level
    for stakes, data in stakes_breakdown.items():
        if data["hands"] > 0:
            data["bb_per_100"] = (data["bb_won"] / data["hands"]) * 100
        else:
            data["bb_per_100"] = 0
    
    # Find primary stakes (most sessions)
    primary_stakes = max(stakes_breakdown.keys(), key=lambda k: stakes_breakdown[k]["sessions"]) if stakes_breakdown else "$1/$2"
    stakes_to_bb = {"$0.50/$1": 1.0, "$1/$2": 2.0, "$2/$5": 5.0, "$5/$10": 10.0, "$10/$20": 20.0, "$25/$50": 50.0}
    primary_bb_size = stakes_to_bb.get(primary_stakes, 2.0)
    
    # Day of week breakdown
    day_breakdown = {i: {"sessions": 0, "profit": 0} for i in range(7)}
    for s in sessions:
        dt = parse_session_datetime(s)
        if dt:
            dow = dt.weekday()
            day_breakdown[dow]["sessions"] += 1
            day_breakdown[dow]["profit"] += float(s.get("profit_loss", 0) or 0)
    
    # Monthly breakdown
    monthly_breakdown = {}
    for s in sessions:
        dt = parse_session_datetime(s)
        if dt:
            month_key = dt.strftime("%Y-%m")
            if month_key not in monthly_breakdown:
                monthly_breakdown[month_key] = {"sessions": 0, "profit": 0, "hands": 0, "bb_won": 0}
            monthly_breakdown[month_key]["sessions"] += 1
            monthly_breakdown[month_key]["profit"] += float(s.get("profit_loss", 0) or 0)
            monthly_breakdown[month_key]["hands"] += int(s.get("hands_played", 0) or 0)
            bb_size = float(s.get("bb_size", 2.0) or 2.0)
            monthly_breakdown[month_key]["bb_won"] += float(s.get("profit_loss", 0) or 0) / bb_size if bb_size > 0 else 0
    
    # Calculate BB/100 for each month
    for month, data in monthly_breakdown.items():
        if data["hands"] > 0:
            data["bb_per_100"] = (data["bb_won"] / data["hands"]) * 100
        else:
            data["bb_per_100"] = 0
    
    return {
        "total_sessions": total_sessions,
        "total_hands": total_hands,
        "total_hours": total_hours,
        "total_profit": total_profit,
        "overall_bb_per_100": overall_bb_per_100,
        "winning_sessions": winning_sessions,
        "losing_sessions": losing_sessions,
        "breakeven_sessions": breakeven_sessions,
        "win_rate_pct": win_rate_pct,
        "avg_session_profit": avg_session_profit,
        "avg_session_duration": avg_session_duration,
        "best_session": best_session,
        "worst_session": worst_session,
        "max_win_streak": max_win_streak,
        "max_lose_streak": max_lose_streak,
        "stop_loss_count": stop_loss_count,
        "stop_win_count": stop_win_count,
        "stakes_breakdown": stakes_breakdown,
        "day_breakdown": day_breakdown,
        "monthly_breakdown": monthly_breakdown,
        "primary_stakes": primary_stakes,
        "primary_bb_size": primary_bb_size,
    }


def get_current_tier(total_profit: float) -> Tuple[dict, dict, float]:
    """
    Get current badge tier, next tier, and progress percentage.
    """
    current_tier = PROFIT_TIERS[0]
    next_tier = PROFIT_TIERS[1] if len(PROFIT_TIERS) > 1 else None
    
    for i, tier in enumerate(PROFIT_TIERS):
        if tier["max"] is None or total_profit < tier["max"]:
            current_tier = tier
            next_tier = PROFIT_TIERS[i + 1] if i + 1 < len(PROFIT_TIERS) else None
            break
    
    # Calculate progress to next tier
    if next_tier:
        tier_start = current_tier["min"]
        tier_end = current_tier["max"] if current_tier["max"] else tier_start + 10000
        progress = ((total_profit - tier_start) / (tier_end - tier_start)) * 100
        progress = min(100, max(0, progress))
    else:
        progress = 100
    
    return current_tier, next_tier, progress


def calculate_running_profit(sessions: List[dict]) -> List[dict]:
    """Calculate running profit curve data for chart."""
    sorted_sessions = sorted(
        sessions,
        key=lambda s: parse_session_datetime(s) or datetime.min.replace(tzinfo=timezone.utc)
    )
    
    running_total = 0
    data = []
    
    for s in sorted_sessions:
        dt = parse_session_datetime(s)
        pl = float(s.get("profit_loss", 0) or 0)
        running_total += pl
        
        if dt:
            data.append({
                "date": dt.strftime("%Y-%m-%d"),
                "session_pl": pl,
                "running_total": running_total,
            })
    
    return data


# =============================================================================
# RENDER FUNCTIONS
# =============================================================================

def render_badge_display(stats: dict):
    """Render the main badge tier display with progress bar."""
    total_profit = stats.get("total_profit", 0)
    current_tier, next_tier, progress = get_current_tier(total_profit)
    
    progress_text = f"${next_tier['min'] - total_profit:,.0f} to {next_tier['name']}" if next_tier else "Maximum tier achieved! 👑"
    
    st.markdown(f"""
        <div class="badge-card">
            <div class="badge-emoji">{current_tier['emoji']}</div>
            <div class="badge-name">{current_tier['name']}</div>
            <div class="badge-description">{current_tier['description']}</div>
            <div style="font-size: 24px; font-weight: 700; color: {current_tier['color']};">
                {format_money(total_profit)} lifetime
            </div>
            <div class="badge-progress">
                <div class="badge-progress-fill" style="width: {progress}%; background: {current_tier['color']};"></div>
            </div>
            <div class="badge-progress-text">{progress_text}</div>
        </div>
    """, unsafe_allow_html=True)


def render_premium_stats(stats: dict, sessions: List[dict]):
    """
    Render the premium headline statistics:
    - Hourly win rate
    - BB/100 with confidence interval
    - Projected annual earnings
    """
    # Calculate premium metrics
    hourly_rate = calculate_hourly_rate(stats)
    bb_per_100, ci_low, ci_high = calculate_confidence_interval(sessions)
    projection = calculate_annual_projection(stats)
    
    # Row 1: Big premium numbers
    col1, col2, col3 = st.columns(3)
    
    with col1:
        color = "#22c55e" if hourly_rate >= 0 else "#ef4444"
        st.markdown(f"""
            <div class="premium-stat-card">
                <div class="premium-stat-value" style="color: {color};">${hourly_rate:,.2f}/hr</div>
                <div class="premium-stat-label">Hourly Win Rate</div>
                <div class="premium-stat-context">Based on {stats.get('total_hours', 0):.0f} hours played</div>
            </div>
        """, unsafe_allow_html=True)
    
    with col2:
        color = "#22c55e" if bb_per_100 >= 0 else "#ef4444"
        st.markdown(f"""
            <div class="premium-stat-card">
                <div class="premium-stat-value" style="color: {color};">{format_bb_per_100(bb_per_100)}</div>
                <div class="premium-stat-label">BB/100 Win Rate</div>
                <div class="confidence-display">
                    <span class="confidence-range">95% CI: {ci_low:+.1f} to {ci_high:+.1f}</span>
                </div>
            </div>
        """, unsafe_allow_html=True)
    
    with col3:
        proj_annual = projection.get("projected_annual", 0)
        confidence = projection.get("confidence", "low")
        confidence_text = {"high": "High confidence", "medium": "Medium confidence", "low": "More data needed"}.get(confidence, "")
        color = "#22c55e" if proj_annual >= 0 else "#ef4444"
        
        st.markdown(f"""
            <div class="premium-stat-card">
                <div class="premium-stat-value" style="color: {color};">{format_money(proj_annual, include_sign=False)}</div>
                <div class="premium-stat-label">Projected Annual</div>
                <div class="premium-stat-context">{confidence_text} • 500 sessions/year</div>
            </div>
        """, unsafe_allow_html=True)
    
    # Row 2: Supporting stats
    st.markdown("")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        pl = stats.get("total_profit", 0)
        pl_class = "positive" if pl >= 0 else "negative"
        st.markdown(f"""
            <div class="stat-card">
                <div class="stat-card-value {pl_class}">{format_money(pl)}</div>
                <div class="stat-card-label">Lifetime Profit</div>
            </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
            <div class="stat-card">
                <div class="stat-card-value neutral">{stats.get('total_hours', 0):.0f}</div>
                <div class="stat-card-label">Hours Played</div>
            </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
            <div class="stat-card">
                <div class="stat-card-value neutral">{stats.get('total_sessions', 0)}</div>
                <div class="stat-card-label">Sessions</div>
            </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
            <div class="stat-card">
                <div class="stat-card-value neutral">{stats.get('total_hands', 0):,}</div>
                <div class="stat-card-label">Hands Played</div>
            </div>
        """, unsafe_allow_html=True)


def render_performance_comparison(stats: dict):
    """
    Render visual comparison of actual performance vs expected.
    Shows user how they're doing relative to optimal play.
    """
    bb_per_100 = stats.get("overall_bb_per_100", 0)
    expected = EXPECTED_BB_PER_100
    
    # Calculate percentage of expected
    pct_of_expected = (bb_per_100 / expected) * 100 if expected > 0 else 0
    
    # Determine status message
    if bb_per_100 >= expected * 1.15:
        status_text = f"🔥 You're performing {((bb_per_100/expected - 1) * 100):.0f}% above expected"
        card_class = "success"
    elif bb_per_100 >= expected * 0.85:
        status_text = "✅ You're performing at expected levels"
        card_class = ""
    elif bb_per_100 >= 0:
        status_text = f"📊 Performing {((1 - bb_per_100/expected) * 100):.0f}% below expected — variance will balance"
        card_class = "warning"
    else:
        status_text = "📉 Short-term variance — keep making +EV decisions"
        card_class = "warning"
    
    # Visual bar calculation
    bar_pct = min(150, max(0, pct_of_expected))
    marker_pos = (100 / 150) * 100  # Expected at 66.7% of bar
    fill_color = "#22c55e" if bb_per_100 >= expected else "#f59e0b" if bb_per_100 >= 0 else "#ef4444"
    
    st.markdown("### 📊 Performance vs Expected")
    st.markdown(f"""
        <div class="insight-card {card_class}">
            <div class="insight-title">{status_text}</div>
            <div class="insight-body">
                Your win rate: <span class="insight-highlight">{format_bb_per_100(bb_per_100)} BB/100</span><br>
                Expected for optimal play: <span class="insight-highlight">+{expected:.1f} BB/100</span>
            </div>
            <div class="performance-bar">
                <div class="performance-fill" style="width: {bar_pct * 100 / 150}%; background: {fill_color};"></div>
                <div class="performance-marker" style="left: {marker_pos}%;"></div>
            </div>
            <div class="performance-label">
                <span>0 BB/100</span>
                <span>Expected ({expected})</span>
                <span>+{expected * 1.5:.0f}</span>
            </div>
        </div>
    """, unsafe_allow_html=True)


def render_session_length_optimization(sessions: List[dict]):
    """
    Render session length optimization analysis.
    Shows which session duration produces best results.
    """
    st.markdown("### ⏱️ Optimal Session Length")
    
    analysis = calculate_session_length_performance(sessions)
    buckets = analysis["buckets"]
    best = analysis["best"]
    
    cols = st.columns(3)
    bucket_order = ["short", "optimal", "long"]
    
    for i, key in enumerate(bucket_order):
        bucket = buckets[key]
        is_recommended = key == best and bucket["count"] >= 3
        
        with cols[i]:
            card_class = "recommended" if is_recommended else ""
            avg_profit = bucket["avg_profit"]
            profit_color = "#22c55e" if avg_profit >= 0 else "#ef4444"
            
            st.markdown(f"""
                <div class="optimization-card {card_class}">
                    <div class="optimization-label">{bucket['label']}</div>
                    <div class="optimization-value" style="color: {profit_color};">{format_money(avg_profit)}</div>
                    <div class="optimization-subtext">avg per session • {bucket['count']} sessions</div>
                    {'<div style="color: #22c55e; font-weight: 600; margin-top: 8px;">✓ RECOMMENDED</div>' if is_recommended else ''}
                </div>
            """, unsafe_allow_html=True)
    
    # Insight based on best duration
    insights = {
        "optimal": "Your best results come from 1.5-3 hour sessions. This aligns with research showing optimal decision-making in this window.",
        "short": "You're performing best in shorter sessions. Consider playing more frequent, shorter sessions to maximize your edge.",
        "long": "You're performing well in longer sessions, but be aware that decision quality typically declines after 3 hours.",
    }
    
    st.markdown(f"""
        <div class="insight-card">
            <div class="insight-title">💡 Insight</div>
            <div class="insight-body">{insights.get(best, insights['optimal'])}</div>
        </div>
    """, unsafe_allow_html=True)


def render_monthly_trend(stats: dict):
    """Render monthly BB/100 trend chart."""
    st.markdown("### 📈 Monthly Trend")
    
    monthly = stats.get("monthly_breakdown", {})
    
    if len(monthly) < 2:
        st.info("Play more sessions to see monthly trends.")
        return
    
    # Prepare data for chart
    sorted_months = sorted(monthly.keys())[-12:]  # Last 12 months
    data = [{"month": m, "BB/100": monthly[m].get("bb_per_100", 0)} for m in sorted_months]
    df = pd.DataFrame(data)
    
    if len(df) > 0:
        st.line_chart(df.set_index("month")["BB/100"], use_container_width=True)
        
        # Trend analysis
        if len(data) >= 3:
            recent_3 = [d["BB/100"] for d in data[-3:]]
            older_3 = [d["BB/100"] for d in data[-6:-3]] if len(data) >= 6 else recent_3
            
            recent_avg = sum(recent_3) / len(recent_3)
            older_avg = sum(older_3) / len(older_3)
            
            if recent_avg > older_avg + 1:
                st.markdown("📈 Your win rate is **trending up** over recent months. Great progress!")
            elif recent_avg < older_avg - 1:
                st.markdown("📉 Your win rate has dipped recently. This is often variance — stay the course.")
            else:
                st.markdown("➡️ Your win rate is **stable**. Consistency is key to long-term success.")


def render_achievements(stats: dict):
    """Render achievement badges grid."""
    st.markdown("### 🏆 Achievements")
    
    cols = st.columns(4)
    
    for i, badge in enumerate(ACHIEVEMENT_BADGES):
        with cols[i % 4]:
            unlocked = badge["check"](stats)
            badge_class = "unlocked" if unlocked else "locked"
            
            # Calculate progress
            progress_key = badge.get("progress_key")
            target = badge.get("target", 1)
            current = stats.get(progress_key, 0) if progress_key else 0
            
            if not unlocked and progress_key:
                if isinstance(current, float):
                    progress_text = f"{current:,.0f} / {target:,.0f}"
                else:
                    progress_text = f"{current:,} / {target:,}"
            elif unlocked:
                progress_text = "✓ Unlocked"
            else:
                progress_text = ""
            
            st.markdown(f"""
                <div class="achievement-badge {badge_class}">
                    <div class="achievement-emoji">{badge['emoji']}</div>
                    <div class="achievement-name">{badge['name']}</div>
                    <div class="achievement-desc">{badge['description']}</div>
                    <div class="achievement-progress">{progress_text}</div>
                </div>
            """, unsafe_allow_html=True)


def render_profit_curve(sessions: List[dict]):
    """Render profit curve chart with key metrics."""
    st.markdown("### 📈 Profit Curve")
    
    data = calculate_running_profit(sessions)
    
    if not data:
        st.info("No session data to display.")
        return
    
    df = pd.DataFrame(data)
    st.line_chart(df.set_index("date")["running_total"], use_container_width=True)
    
    # Key stats below chart
    col1, col2, col3 = st.columns(3)
    
    with col1:
        best_point = max(d["running_total"] for d in data) if data else 0
        st.metric("Peak Profit", format_money(best_point, include_sign=False))
    
    with col2:
        worst_point = min(d["running_total"] for d in data) if data else 0
        st.metric("Lowest Point", format_money(worst_point))
    
    with col3:
        current = data[-1]["running_total"] if data else 0
        st.metric("Current", format_money(current))


def render_stakes_breakdown(stats: dict):
    """Render performance breakdown by stakes level."""
    st.markdown("### 💵 Performance by Stakes")
    
    breakdown = stats.get("stakes_breakdown", {})
    
    if not breakdown:
        st.info("No stakes data to display.")
        return
    
    # Sort by stakes level
    stakes_order = ["$0.50/$1", "$1/$2", "$2/$5", "$5/$10", "$10/$20", "$25/$50"]
    sorted_stakes = sorted(
        breakdown.items(),
        key=lambda x: stakes_order.index(x[0]) if x[0] in stakes_order else 999
    )
    
    for stakes, data in sorted_stakes:
        profit = data["profit"]
        sessions_count = data["sessions"]
        bb_per_100 = data["bb_per_100"]
        
        profit_color = "#22c55e" if profit >= 0 else "#ef4444"
        bb_color = "#22c55e" if bb_per_100 >= 0 else "#ef4444"
        
        col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
        
        with col1:
            st.markdown(f"**{stakes}**")
        with col2:
            st.markdown(f"{sessions_count} sessions")
        with col3:
            st.markdown(f"<span style='color: {profit_color}; font-weight: 600;'>{format_money(profit)}</span>", unsafe_allow_html=True)
        with col4:
            st.markdown(f"<span style='color: {bb_color}; font-weight: 600;'>{format_bb_per_100(bb_per_100)} BB/100</span>", unsafe_allow_html=True)
        
        st.markdown("---")


def render_day_analysis(stats: dict):
    """Render day of week performance analysis."""
    st.markdown("### 📅 Best Days to Play")
    
    breakdown = stats.get("day_breakdown", {})
    
    if not breakdown:
        st.info("No day data to display.")
        return
    
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    
    # Find best and worst days (by average profit per session)
    day_data = [(i, breakdown[i]["profit"], breakdown[i]["sessions"]) for i in range(7) if breakdown[i]["sessions"] > 0]
    
    if day_data:
        best_day = max(day_data, key=lambda x: x[1] / x[2] if x[2] > 0 else 0)[0]
        worst_day = min(day_data, key=lambda x: x[1] / x[2] if x[2] > 0 else 0)[0]
    else:
        best_day = None
        worst_day = None
    
    cols = st.columns(7)
    
    for i, col in enumerate(cols):
        with col:
            data = breakdown.get(i, {"sessions": 0, "profit": 0})
            sessions_count = data["sessions"]
            profit = data["profit"]
            avg_profit = profit / sessions_count if sessions_count > 0 else 0
            
            css_class = ""
            if i == best_day and sessions_count >= 3:
                css_class = "best"
            elif i == worst_day and sessions_count >= 3:
                css_class = "worst"
            
            st.markdown(f"""
                <div class="day-stat {css_class}">
                    <div class="day-name">{day_names[i]}</div>
                    <div class="day-value">{format_money(avg_profit)}</div>
                    <div style="font-size: 11px; color: #9ca3af;">{sessions_count} sessions</div>
                </div>
            """, unsafe_allow_html=True)
    
    # Insight
    if best_day is not None and breakdown[best_day]["sessions"] >= 3:
        st.markdown(f"""
            <div class="insight-card success">
                <div class="insight-title">💡 Insight</div>
                <div class="insight-body">
                    Your best performance is on <strong>{day_names[best_day]}s</strong>. 
                    Consider prioritizing your sessions on this day.
                </div>
            </div>
        """, unsafe_allow_html=True)


def render_session_stats(stats: dict):
    """Render session statistics including win/loss distribution and streaks."""
    st.markdown("### 📊 Session Statistics")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Win/Loss Distribution**")
        
        winning = stats.get("winning_sessions", 0)
        losing = stats.get("losing_sessions", 0)
        breakeven = stats.get("breakeven_sessions", 0)
        total = winning + losing + breakeven
        
        if total > 0:
            win_pct = (winning / total) * 100
            lose_pct = (losing / total) * 100
            
            st.markdown(f"🟢 Winning: **{winning}** ({win_pct:.0f}%)")
            st.markdown(f"🔴 Losing: **{losing}** ({lose_pct:.0f}%)")
            if breakeven > 0:
                st.markdown(f"⚪ Break-even: **{breakeven}**")
            
            st.progress(win_pct / 100)
    
    with col2:
        st.markdown("**Session Records**")
        
        best = stats.get("best_session", 0)
        worst = stats.get("worst_session", 0)
        avg = stats.get("avg_session_profit", 0)
        avg_duration = stats.get("avg_session_duration", 0)
        
        st.markdown(f"🏆 Best Session: **{format_money(best)}**")
        st.markdown(f"📉 Worst Session: **{format_money(worst)}**")
        st.markdown(f"📊 Average Session: **{format_money(avg)}**")
        st.markdown(f"⏱️ Avg Duration: **{avg_duration:.0f} min**")
    
    st.markdown("---")
    
    # Streaks
    col1, col2 = st.columns(2)
    
    with col1:
        win_streak = stats.get("max_win_streak", 0)
        st.metric("🔥 Longest Win Streak", f"{win_streak} sessions")
    
    with col2:
        lose_streak = stats.get("max_lose_streak", 0)
        st.metric("❄️ Longest Losing Streak", f"{lose_streak} sessions")


def render_ev_reminder(stats: dict):
    """
    Render personalized EV reminder box.
    Uses actual player data to make the message more impactful.
    """
    bb_per_100 = stats.get("overall_bb_per_100", 0)
    total_sessions = stats.get("total_sessions", 0)
    primary_stakes = stats.get("primary_stakes", "$1/$2")
    
    projection = calculate_annual_projection(stats)
    proj_annual = projection.get("projected_annual", 0)
    
    if proj_annual > 0 and total_sessions >= 10:
        # Personalized message based on their data
        message = f"""
            At your current win rate of <strong>{format_bb_per_100(bb_per_100)} BB/100</strong>, 
            you're on pace for <strong>{format_money(proj_annual, include_sign=False)}/year</strong> at {primary_stakes}.
            <br><br>
            Keep making +EV decisions. The math is working in your favor.
        """
    else:
        # Generic encouraging message for new players
        message = """
            Every decision you make using this app is mathematically optimal. 
            Short-term results are influenced by variance, but players who maintain 
            this level of play average <strong>+$20,000-24,000/year</strong> at $1/$2 stakes.
            <br><br>
            <em>Trust the math. The results will follow.</em>
        """
    
    st.markdown(f"""
        <div class="ev-journey-box">
            <div class="ev-journey-title">📊 Your +EV Journey</div>
            <div class="ev-journey-body">{message}</div>
        </div>
    """, unsafe_allow_html=True)


def render_empty_state():
    """Render empty state when no session data exists."""
    st.markdown("""
        <div class="empty-state">
            <div class="empty-state-icon">📊</div>
            <h3>No Stats Yet</h3>
            <p>Complete some sessions to see your performance statistics and unlock achievements!</p>
        </div>
    """, unsafe_allow_html=True)


# =============================================================================
# ADMIN/DISCORD EXPORT FUNCTIONS
# =============================================================================

def get_player_badge_info(user_id: str) -> dict:
    """
    Get comprehensive badge information for a player.
    
    This function can be called from:
    - Admin dashboard to view player badges
    - Discord bot to display player rank in community
    - Leaderboard pages
    
    Returns:
        dict with tier info, stats, and unlocked achievements
    """
    sessions = get_user_sessions(user_id, limit=1000)
    stats = calculate_aggregate_stats(sessions)
    
    total_profit = stats.get("total_profit", 0)
    current_tier, next_tier, progress = get_current_tier(total_profit)
    
    # Calculate premium metrics
    hourly_rate = calculate_hourly_rate(stats)
    bb_per_100, ci_low, ci_high = calculate_confidence_interval(sessions)
    
    # Get unlocked achievements
    unlocked_achievements = []
    for badge in ACHIEVEMENT_BADGES:
        if badge["check"](stats):
            unlocked_achievements.append({
                "id": badge["id"],
                "name": badge["name"],
                "emoji": badge["emoji"],
            })
    
    return {
        # Tier info
        "tier_emoji": current_tier["emoji"],
        "tier_name": current_tier["name"],
        "tier_color": current_tier["color"],
        "tier_progress": progress,
        "next_tier_name": next_tier["name"] if next_tier else None,
        
        # Core stats
        "total_profit": total_profit,
        "total_sessions": stats.get("total_sessions", 0),
        "total_hours": stats.get("total_hours", 0),
        "total_hands": stats.get("total_hands", 0),
        
        # Premium stats
        "bb_per_100": bb_per_100,
        "bb_per_100_ci": (ci_low, ci_high),
        "hourly_rate": hourly_rate,
        
        # Achievements
        "unlocked_achievements": unlocked_achievements,
        "achievement_count": len(unlocked_achievements),
        "total_achievements": len(ACHIEVEMENT_BADGES),
    }


# =============================================================================
# MAIN PAGE
# =============================================================================

def main():
    """Main render function for Player Stats page."""
    
    st.title("📊 Player Stats")
    st.caption("Your complete performance dashboard with insights and achievements")
    
    user_id = get_user_id()
    
    if not user_id:
        st.warning("Please log in to view your stats.")
        return
    
    # Get all sessions
    sessions = get_user_sessions(user_id, limit=1000)
    
    if not sessions:
        render_empty_state()
        return
    
    # Calculate aggregate stats
    stats = calculate_aggregate_stats(sessions)
    
    # ===== BADGE DISPLAY =====
    render_badge_display(stats)
    
    # ===== PREMIUM STATS (Hourly Rate, BB/100 with CI, Projected Annual) =====
    render_premium_stats(stats, sessions)
    
    st.markdown("---")
    
    # ===== PERFORMANCE VS EXPECTED =====
    render_performance_comparison(stats)
    
    st.markdown("---")
    
    # ===== TABBED SECTIONS =====
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📈 Profit & Trends",
        "⏱️ Session Optimization",
        "🏆 Achievements",
        "💵 Stakes Analysis",
        "📅 Time Analysis"
    ])
    
    with tab1:
        render_profit_curve(sessions)
        render_monthly_trend(stats)
        render_ev_reminder(stats)
    
    with tab2:
        render_session_length_optimization(sessions)
        render_session_stats(stats)
    
    with tab3:
        render_achievements(stats)
    
    with tab4:
        render_stakes_breakdown(stats)
    
    with tab5:
        render_day_analysis(stats)


if __name__ == "__main__":
    main()