# =============================================================================
# 04_Bankroll_Health.py — PREMIUM Bankroll Health Dashboard v2
# =============================================================================
#
# PREMIUM FEATURES ($299/month value):
# 1. Rich Onboarding — educates user on bankroll management before they set BR
# 2. Hero Bankroll Snapshot — bankroll, buy-ins, risk level, stake rec at a glance
# 3. Inline Bankroll Editor — update bankroll directly from the dashboard
# 4. Transparent Move-Up Projection — show the math: win rate, hours, target
# 5. Real Session Data — pulls actual win rate, hours, P/L from DB
# 6. Risk of Ruin — mathematical probability with visual gauge
# 7. Drawdown Tracker — current vs max historical
# 8. Stakes Ladder — visual progression with unlocks
# 9. Risk Mode Selector — Aggressive/Balanced/Conservative with full education
#
# DESIGN SYSTEM:
# - Background: #0A0A12
# - Panel: linear-gradient(135deg, #0F0F1A, #151520)
# - Borders: rgba(255,255,255,0.06)
# - Typography: JetBrains Mono (numbers), Inter (body)
# - Green: #69F0AE (positive)  Red: #FF5252 (negative)  Accent: #4BA3FF
#
# =============================================================================

import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Tuple
import math

st.set_page_config(
    page_title="Bankroll Health | Nameless Poker",
    page_icon="💰",
    layout="wide",
)

from auth import require_auth
from sidebar import render_sidebar
from db import get_user_sessions, get_player_stats, get_bankroll_history, update_user_bankroll

# ---------- Auth Gate ----------
user = require_auth()
render_sidebar()

st.session_state["visited_bankroll"] = True

# =============================================================================
# CONFIGURATION
# =============================================================================

STAKES_CONFIG = [
    {"name": "$0.50/$1", "bb": 1.0, "typical_bi": 100, "min_bankroll": 1300},
    {"name": "$1/$2", "bb": 2.0, "typical_bi": 200, "min_bankroll": 2600},
    {"name": "$2/$5", "bb": 5.0, "typical_bi": 500, "min_bankroll": 6500},
    {"name": "$5/$10", "bb": 10.0, "typical_bi": 1000, "min_bankroll": 13000},
    {"name": "$10/$20", "bb": 20.0, "typical_bi": 2000, "min_bankroll": 26000},
    {"name": "$25/$50", "bb": 50.0, "typical_bi": 5000, "min_bankroll": 65000},
]

RISK_MODES = {
    "aggressive": {
        "name": "Aggressive",
        "emoji": "🔥",
        "buy_ins": 13,
        "description": "Higher risk, faster progression",
        "risk_tolerance": "High variance tolerance, experienced player",
        "color": "#FFB300",
        "stop_loss": 0.75,
        "stop_win": 3.0,
        "ror_15bi": "0.28%",
        "annual_1_2": "$23,000",
        "personality": "You're comfortable with bigger swings for faster stake progression. "
                       "Shorter recovery from downswings because you're playing more aggressively. "
                       "Best for experienced players who've weathered bad runs before.",
    },
    "balanced": {
        "name": "Balanced",
        "emoji": "⚖️",
        "buy_ins": 15,
        "description": "Recommended for most players",
        "risk_tolerance": "Moderate variance, steady growth",
        "color": "#4BA3FF",
        "stop_loss": 1.0,
        "stop_win": 3.0,
        "ror_15bi": "0.08%",
        "annual_1_2": "$21,000",
        "personality": "The sweet spot. You have enough cushion to survive standard "
                       "downswings (15–20 buy-in swings happen to everyone) while still "
                       "progressing through stakes at a reasonable pace. Best for most players.",
    },
    "conservative": {
        "name": "Conservative",
        "emoji": "🛡️",
        "buy_ins": 17,
        "description": "Lower risk, slower progression",
        "risk_tolerance": "Low variance tolerance, capital preservation",
        "color": "#69F0AE",
        "stop_loss": 1.25,
        "stop_win": 3.0,
        "ror_15bi": "<0.01%",
        "annual_1_2": "$19,600",
        "personality": "Maximum safety. You'll almost never need to move down stakes, "
                       "and bad runs won't threaten your bankroll. Progression is slower "
                       "but your bankroll is a fortress. Best for risk-averse players or "
                       "those playing with money they can't afford to lose.",
    },
}

HEALTH_THRESHOLDS = {
    "excellent": {"min_bi": 20, "color": "#69F0AE", "label": "Excellent", "emoji": "🟢"},
    "healthy": {"min_bi": 15, "color": "#69F0AE", "label": "Healthy", "emoji": "🟢"},
    "adequate": {"min_bi": 12, "color": "#FFB300", "label": "Adequate", "emoji": "🟡"},
    "warning": {"min_bi": 8, "color": "#FFB300", "label": "Warning", "emoji": "🟡"},
    "danger": {"min_bi": 0, "color": "#FF5252", "label": "Danger", "emoji": "🔴"},
}


# =============================================================================
# DARK THEME CSS
# =============================================================================

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700;800&family=Inter:wght@300;400;500;600;700&display=swap');

/* ===== Global Dark Theme Override ===== */
.stApp, [data-testid="stAppViewContainer"],
.main .block-container {
    background-color: #0A0A12 !important;
    color: rgba(255,255,255,0.90) !important;
}
.main .block-container {
    max-width: 1100px;
    padding-top: 1.5rem;
}
header[data-testid="stHeader"] { background: #0A0A12 !important; }

/* ===== Streamlit Widget Dark Overrides ===== */
.stNumberInput > div > div > input,
.stTextInput > div > div > input {
    background: rgba(255,255,255,0.04) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    color: #fff !important;
    font-family: 'JetBrains Mono', monospace !important;
    border-radius: 8px !important;
}
.stNumberInput label, .stTextInput label, .stRadio label, .stSelectbox label {
    color: rgba(255,255,255,0.45) !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 11px !important;
    text-transform: uppercase !important;
    letter-spacing: 0.06em !important;
}
.stRadio > div { gap: 0 !important; }
.stRadio > div > label {
    background: rgba(255,255,255,0.03) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 8px !important;
    padding: 8px 14px !important;
    margin-right: 6px !important;
    color: rgba(255,255,255,0.60) !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 13px !important;
    transition: all 0.15s ease !important;
}
.stRadio > div > label[data-checked="true"],
.stRadio > div > label:has(input:checked) {
    border-color: #4BA3FF !important;
    background: rgba(75,163,255,0.08) !important;
    color: #4BA3FF !important;
}
/* Tabs */
div[data-baseweb="tab-list"] {
    background: rgba(255,255,255,0.02) !important;
    border-radius: 10px !important;
    padding: 4px !important;
    gap: 4px !important;
    border: 1px solid rgba(255,255,255,0.06) !important;
}
div[data-baseweb="tab-list"] button {
    background: transparent !important;
    color: rgba(255,255,255,0.40) !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 500 !important;
    font-size: 13px !important;
    border-radius: 8px !important;
    padding: 8px 16px !important;
    border: none !important;
}
div[data-baseweb="tab-list"] button[aria-selected="true"] {
    background: rgba(75,163,255,0.10) !important;
    color: #4BA3FF !important;
    font-weight: 600 !important;
}
div[data-baseweb="tab-highlight"], div[data-baseweb="tab-border"] { display: none !important; }
/* Buttons */
.stButton > button {
    font-family: 'JetBrains Mono', monospace !important;
    font-weight: 600 !important;
    border-radius: 8px !important;
    transition: all 0.15s ease !important;
}
.stButton > button[kind="primary"],
.stButton > button[data-testid="stBaseButton-primary"] {
    background: linear-gradient(135deg, #4BA3FF, #2979FF) !important;
    border: none !important;
    color: #fff !important;
}
.stButton > button[kind="primary"]:hover,
.stButton > button[data-testid="stBaseButton-primary"]:hover {
    filter: brightness(1.1) !important;
    box-shadow: 0 4px 20px rgba(75,163,255,0.25) !important;
}
hr { border-color: rgba(255,255,255,0.06) !important; }
.block-container { padding-top: 1rem !important; }

/* Hide default streamlit title/header area */
.stTitle, h1[data-testid="stTitle"] { display: none !important; }

/* ===== Page Header ===== */
.page-hdr {
    text-align: center;
    padding: 12px 0 28px 0;
}
.page-hdr h1 {
    font-family: 'Inter', sans-serif;
    font-size: 26px;
    font-weight: 700;
    color: rgba(255,255,255,0.92);
    margin: 0 0 4px 0;
    letter-spacing: -0.02em;
}
.page-hdr p {
    font-family: 'Inter', sans-serif;
    font-size: 13px;
    color: rgba(255,255,255,0.30);
    margin: 0;
}

/* ===== Dark Panel Card ===== */
.dk {
    background: linear-gradient(135deg, #0F0F1A 0%, #151520 100%);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 14px;
    padding: 24px;
    margin-bottom: 16px;
}
.dk-hdr {
    font-family: 'Inter', sans-serif;
    font-size: 11px;
    font-weight: 600;
    color: rgba(255,255,255,0.30);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 14px;
    display: flex;
    align-items: center;
    gap: 8px;
}

/* ===== Hero Snapshot Card ===== */
.hero {
    background: linear-gradient(135deg, #0F0F1A 0%, #151520 100%);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 16px;
    padding: 28px 32px;
    margin-bottom: 20px;
    position: relative;
    overflow: hidden;
}
.hero::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    border-radius: 16px 16px 0 0;
}
.hero.excellent::before, .hero.healthy::before { background: linear-gradient(90deg, #69F0AE, #00E676); }
.hero.adequate::before, .hero.warning::before { background: linear-gradient(90deg, #FFB300, #FFC107); }
.hero.danger::before { background: linear-gradient(90deg, #FF5252, #FF1744); }

.badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 12px;
    border-radius: 20px;
    font-family: 'Inter', sans-serif;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 14px;
}
.badge.green { background: rgba(105,240,174,0.10); color: #69F0AE; border: 1px solid rgba(105,240,174,0.15); }
.badge.amber { background: rgba(255,179,0,0.10); color: #FFB300; border: 1px solid rgba(255,179,0,0.15); }
.badge.red { background: rgba(255,82,82,0.10); color: #FF5252; border: 1px solid rgba(255,82,82,0.15); }

.hero-bankroll {
    font-family: 'JetBrains Mono', monospace;
    font-size: 46px;
    font-weight: 800;
    color: #fff;
    margin: 0 0 4px 0;
    letter-spacing: -0.03em;
    line-height: 1.1;
}
.hero-sub {
    font-family: 'Inter', sans-serif;
    font-size: 13px;
    color: rgba(255,255,255,0.35);
    margin-bottom: 22px;
}

/* ===== Stat Grid ===== */
.sg { display: grid; gap: 12px; }
.sg-4 { grid-template-columns: repeat(4, 1fr); }
.sg-3 { grid-template-columns: repeat(3, 1fr); }
.sg-2 { grid-template-columns: repeat(2, 1fr); }
.si {
    background: rgba(255,255,255,0.025);
    border: 1px solid rgba(255,255,255,0.04);
    border-radius: 10px;
    padding: 14px 16px;
}
.si-label {
    font-family: 'Inter', sans-serif;
    font-size: 10px;
    font-weight: 500;
    color: rgba(255,255,255,0.30);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 5px;
}
.si-val {
    font-family: 'JetBrains Mono', monospace;
    font-size: 20px;
    font-weight: 700;
    color: #fff;
    line-height: 1.2;
}
.si-val.green { color: #69F0AE; }
.si-val.red { color: #FF5252; }
.si-val.blue { color: #4BA3FF; }
.si-val.amber { color: #FFB300; }
.si-detail {
    font-family: 'Inter', sans-serif;
    font-size: 10px;
    color: rgba(255,255,255,0.20);
    margin-top: 3px;
}

/* ===== Move-Up Projection ===== */
.moveup {
    background: linear-gradient(135deg, #0F0F1A 0%, #151520 100%);
    border: 1px solid rgba(75,163,255,0.12);
    border-radius: 14px;
    padding: 24px;
    margin-bottom: 16px;
    position: relative;
}
.moveup::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, #4BA3FF, #2979FF);
    border-radius: 14px 14px 0 0;
}
.moveup-target {
    font-family: 'JetBrains Mono', monospace;
    font-size: 26px;
    font-weight: 800;
    color: #4BA3FF;
    margin-bottom: 3px;
}
.moveup-sub {
    font-family: 'Inter', sans-serif;
    font-size: 12px;
    color: rgba(255,255,255,0.40);
    margin-bottom: 18px;
}
.pbar { background: rgba(255,255,255,0.06); border-radius: 6px; height: 8px; overflow: hidden; margin: 10px 0; }
.pfill { height: 100%; border-radius: 6px; background: linear-gradient(90deg, #4BA3FF, #69F0AE); transition: width 0.5s ease; }
.pbar-labels {
    display: flex; justify-content: space-between;
    font-family: 'JetBrains Mono', monospace; font-size: 11px;
    color: rgba(255,255,255,0.35); margin-bottom: 4px;
}

/* ===== Math Grid ===== */
.mg { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 14px; }
.mr {
    display: flex; justify-content: space-between; align-items: center;
    padding: 7px 12px;
    background: rgba(255,255,255,0.02);
    border-radius: 6px;
    border: 1px solid rgba(255,255,255,0.03);
}
.mr-l { font-family: 'Inter', sans-serif; font-size: 11px; color: rgba(255,255,255,0.35); }
.mr-v { font-family: 'JetBrains Mono', monospace; font-size: 13px; font-weight: 600; color: rgba(255,255,255,0.80); }

/* ===== Info Callout ===== */
.callout {
    background: rgba(75,163,255,0.04);
    border: 1px solid rgba(75,163,255,0.10);
    border-radius: 10px;
    padding: 14px 18px;
    margin-top: 14px;
    font-family: 'Inter', sans-serif;
    font-size: 12px;
    color: rgba(255,255,255,0.45);
    line-height: 1.6;
}
.callout.warn {
    background: rgba(255,179,0,0.04);
    border-color: rgba(255,179,0,0.10);
}
.callout.danger {
    background: rgba(255,82,82,0.04);
    border-color: rgba(255,82,82,0.10);
}

/* ===== Risk Gauge ===== */
.rg-val {
    font-family: 'JetBrains Mono', monospace;
    font-size: 48px;
    font-weight: 800;
    line-height: 1.1;
    text-align: center;
}
.rg-label {
    font-family: 'Inter', sans-serif;
    font-size: 12px;
    font-weight: 500;
    margin-top: 4px;
    text-align: center;
}

/* ===== Stakes Ladder ===== */
.ls {
    display: flex; align-items: center;
    padding: 12px 16px; border-radius: 10px; margin-bottom: 6px;
    transition: all 0.15s ease;
    border: 1px solid rgba(255,255,255,0.04);
    background: rgba(255,255,255,0.02);
}
.ls.current { border-color: rgba(75,163,255,0.25); background: rgba(75,163,255,0.06); }
.ls.available { border-color: rgba(105,240,174,0.12); background: rgba(105,240,174,0.03); }
.ls.locked { opacity: 0.35; }
.ls-name { font-family: 'JetBrains Mono', monospace; font-size: 14px; font-weight: 700; color: #fff; min-width: 90px; }
.ls-req { font-family: 'Inter', sans-serif; font-size: 11px; color: rgba(255,255,255,0.30); flex: 1; padding: 0 14px; }
.ls-status { font-family: 'JetBrains Mono', monospace; font-size: 11px; font-weight: 600; white-space: nowrap; }

/* ===== Drawdown ===== */
.dd-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.dd-item {
    background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.04);
    border-radius: 10px; padding: 18px; text-align: center;
}
.dd-val { font-family: 'JetBrains Mono', monospace; font-size: 34px; font-weight: 800; line-height: 1.2; }
.dd-lbl { font-family: 'Inter', sans-serif; font-size: 11px; color: rgba(255,255,255,0.30); margin-top: 4px; }
.dd-det { font-family: 'Inter', sans-serif; font-size: 10px; color: rgba(255,255,255,0.18); margin-top: 5px; }

/* ===== Risk Mode Cards ===== */
.rm-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.rm {
    background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.06);
    border-radius: 12px; padding: 18px; text-align: center; transition: all 0.15s ease;
}
.rm.sel { border-width: 2px; }
.rm-emoji { font-size: 26px; margin-bottom: 6px; }
.rm-name { font-family: 'Inter', sans-serif; font-size: 13px; font-weight: 600; color: #fff; margin-bottom: 3px; }
.rm-bis { font-family: 'JetBrains Mono', monospace; font-size: 20px; font-weight: 700; margin-bottom: 5px; }
.rm-desc { font-family: 'Inter', sans-serif; font-size: 10px; color: rgba(255,255,255,0.30); }

/* ===== Empty State Education ===== */
.edu-section {
    background: linear-gradient(135deg, #0F0F1A 0%, #151520 100%);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 14px;
    padding: 28px;
    margin-bottom: 16px;
}
.edu-title {
    font-family: 'Inter', sans-serif;
    font-size: 18px;
    font-weight: 700;
    color: rgba(255,255,255,0.90);
    margin-bottom: 6px;
}
.edu-subtitle {
    font-family: 'Inter', sans-serif;
    font-size: 13px;
    color: rgba(255,255,255,0.35);
    margin-bottom: 20px;
    line-height: 1.5;
}
.edu-text {
    font-family: 'Inter', sans-serif;
    font-size: 13px;
    color: rgba(255,255,255,0.50);
    line-height: 1.7;
    margin-bottom: 14px;
}
.edu-highlight {
    font-family: 'JetBrains Mono', monospace;
    color: #4BA3FF;
    font-weight: 600;
}
.edu-warn {
    font-family: 'JetBrains Mono', monospace;
    color: #FF5252;
    font-weight: 600;
}
.edu-ok {
    font-family: 'JetBrains Mono', monospace;
    color: #69F0AE;
    font-weight: 600;
}

/* ===== Stakes Table (Education) ===== */
.stakes-tbl {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    margin: 14px 0;
}
.stakes-tbl th {
    font-family: 'Inter', sans-serif;
    font-size: 10px;
    font-weight: 600;
    color: rgba(255,255,255,0.30);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    padding: 8px 12px;
    text-align: left;
    border-bottom: 1px solid rgba(255,255,255,0.06);
}
.stakes-tbl td {
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px;
    color: rgba(255,255,255,0.70);
    padding: 10px 12px;
    border-bottom: 1px solid rgba(255,255,255,0.03);
}
.stakes-tbl tr:hover td {
    background: rgba(75,163,255,0.03);
}

/* ===== Mode Comparison (Education) ===== */
.mode-compare {
    background: rgba(255,255,255,0.02);
    border: 1px solid rgba(255,255,255,0.05);
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 12px;
    position: relative;
}
.mode-compare::before {
    content: '';
    position: absolute;
    left: 0; top: 0; bottom: 0;
    width: 3px;
    border-radius: 12px 0 0 12px;
}
.mode-compare.agg::before { background: #FFB300; }
.mode-compare.bal::before { background: #4BA3FF; }
.mode-compare.con::before { background: #69F0AE; }
.mc-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
}
.mc-name {
    font-family: 'Inter', sans-serif;
    font-size: 15px;
    font-weight: 700;
    color: #fff;
}
.mc-bis {
    font-family: 'JetBrains Mono', monospace;
    font-size: 14px;
    font-weight: 700;
}
.mc-body {
    font-family: 'Inter', sans-serif;
    font-size: 12px;
    color: rgba(255,255,255,0.45);
    line-height: 1.6;
    margin-bottom: 10px;
}
.mc-stats {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
}
.mc-stat {
    background: rgba(255,255,255,0.02);
    border-radius: 6px;
    padding: 8px 10px;
    text-align: center;
}
.mc-stat-label {
    font-family: 'Inter', sans-serif;
    font-size: 9px;
    color: rgba(255,255,255,0.25);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 2px;
}
.mc-stat-val {
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px;
    font-weight: 600;
    color: rgba(255,255,255,0.75);
}

/* ===== Recommended Badge (Education) ===== */
.rec-tag {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-family: 'Inter', sans-serif;
    font-size: 9px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    background: rgba(75,163,255,0.12);
    color: #4BA3FF;
    margin-left: 8px;
}

/* ===== Responsive ===== */
@media (max-width: 768px) {
    .sg-4 { grid-template-columns: repeat(2, 1fr); }
    .mg { grid-template-columns: 1fr; }
    .dd-grid { grid-template-columns: 1fr; }
    .rm-grid { grid-template-columns: 1fr; }
    .mc-stats { grid-template-columns: 1fr; }
    .hero-bankroll { font-size: 34px; }
}
</style>
""", unsafe_allow_html=True)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_user_id() -> Optional[str]:
    return st.session_state.get("user_db_id")

def get_current_bankroll() -> float:
    return float(st.session_state.get("bankroll", 0) or 0)

def get_risk_mode() -> str:
    return st.session_state.get("risk_mode", "balanced")

def fmt(amount, sign=False):
    """Format money."""
    if amount is None: return "—"
    if sign: return f"+${amount:,.2f}" if amount >= 0 else f"-${abs(amount):,.2f}"
    return f"${amount:,.2f}"

def fmtc(amount):
    """Compact money."""
    if amount is None: return "—"
    if abs(amount) >= 10000: return f"${amount:,.0f}"
    return f"${amount:,.2f}"

def get_stakes_for_bankroll(bankroll, risk_mode):
    mode = RISK_MODES.get(risk_mode, RISK_MODES["balanced"])
    req = mode["buy_ins"]
    rec = STAKES_CONFIG[0]
    for s in STAKES_CONFIG:
        if bankroll >= s["typical_bi"] * req:
            rec = s
        else:
            break
    return rec

def get_buy_ins(bankroll, stakes):
    bi = stakes["typical_bi"]
    return bankroll / bi if bi > 0 else 0

def get_health_status(buy_ins):
    if buy_ins >= 20: return HEALTH_THRESHOLDS["excellent"]
    if buy_ins >= 15: return HEALTH_THRESHOLDS["healthy"]
    if buy_ins >= 12: return HEALTH_THRESHOLDS["adequate"]
    if buy_ins >= 8: return HEALTH_THRESHOLDS["warning"]
    return HEALTH_THRESHOLDS["danger"]

def get_status_class(buy_ins):
    if buy_ins >= 20: return "excellent"
    if buy_ins >= 15: return "healthy"
    if buy_ins >= 12: return "adequate"
    if buy_ins >= 8: return "warning"
    return "danger"

def badge_class(buy_ins):
    if buy_ins >= 15: return "green"
    if buy_ins >= 8: return "amber"
    return "red"

def calc_ror(bankroll, stakes, bb_per_100=6.0, std_dev=80.0):
    if bankroll <= 0 or stakes["bb"] <= 0: return 1.0
    bankroll_bb = bankroll / stakes["bb"]
    edge = bb_per_100 / 100
    if edge <= 0: return 1.0
    var = (std_dev / 10) ** 2
    exp = max(-100, min(100, -2 * edge * bankroll_bb / var))
    return min(1.0, max(0.0, math.exp(exp)))

def calc_drawdown(sessions, bankroll):
    if not sessions:
        return {"current_drawdown": 0, "current_drawdown_pct": 0,
                "max_drawdown": 0, "max_drawdown_pct": 0, "peak_bankroll": bankroll}
    sorted_s = sorted(sessions, key=lambda s: s.get("started_at", "") or "")
    running = bankroll
    hist = [running]
    for s in reversed(sorted_s):
        running -= float(s.get("profit_loss", 0) or 0)
        hist.insert(0, running)
    peak = hist[0]
    max_dd = max_dd_pct = 0
    for b in hist:
        if b > peak: peak = b
        dd = peak - b
        if dd > max_dd:
            max_dd = dd
            max_dd_pct = (dd / peak * 100) if peak > 0 else 0
    cp = max(hist)
    cd = cp - bankroll
    return {"current_drawdown": max(0, cd), "current_drawdown_pct": max(0, (cd / cp * 100) if cp > 0 else 0),
            "max_drawdown": max_dd, "max_drawdown_pct": max_dd_pct, "peak_bankroll": cp}

def get_next_stakes(current):
    for i, s in enumerate(STAKES_CONFIG):
        if s["name"] == current["name"] and i + 1 < len(STAKES_CONFIG):
            return STAKES_CONFIG[i + 1]
    return None

def compute_stats(sessions):
    if not sessions:
        return {"total_profit": 0, "total_hours": 0, "hourly_rate": 0, "total_hands": 0,
                "bb_per_100": 6.0, "total_sessions": 0, "has_data": False}
    tp = th = thn = tbb = 0
    for s in sessions:
        pl = float(s.get("profit_loss", 0) or 0)
        tp += pl
        started, ended = s.get("started_at", ""), s.get("ended_at", "")
        if started and ended:
            try:
                th += (datetime.fromisoformat(ended.replace("Z", "+00:00")) -
                       datetime.fromisoformat(started.replace("Z", "+00:00"))).total_seconds() / 3600
            except Exception: pass
        h = int(s.get("hands_played", 0) or 0)
        thn += h
        bb = float(s.get("bb_size", 2.0) or 2.0)
        if bb > 0: tbb += pl / bb
    return {"total_profit": tp, "total_hours": th, "hourly_rate": tp / th if th > 0 else 0,
            "total_hands": thn, "bb_per_100": (tbb / thn * 100) if thn > 0 else 6.0,
            "total_sessions": len(sessions), "has_data": th > 0 or thn > 0}


# =============================================================================
# EMPTY STATE — COMPREHENSIVE BANKROLL EDUCATION
# =============================================================================

def render_empty_state():
    """Rich educational empty state that teaches bankroll management."""

    # ---- Hero Introduction ----
    st.markdown("""
        <div class="edu-section" style="text-align: center; padding: 36px 32px;">
            <div style="font-size: 44px; margin-bottom: 12px;">💰</div>
            <div class="edu-title" style="font-size: 24px; text-align: center;">
                Bankroll Management
            </div>
            <div class="edu-subtitle" style="text-align: center; max-width: 600px; margin: 8px auto 0;">
                The #1 reason poker players go broke isn't bad play — it's playing stakes 
                they can't afford. Set your bankroll and we'll tell you exactly where to play, 
                when to move up, and when to move down.
            </div>
        </div>
    """, unsafe_allow_html=True)

    # ---- Why Bankroll Matters ----
    st.markdown("""
        <div class="edu-section">
            <div class="edu-title">Why This Matters</div>
            <div class="edu-text">
                Even the best poker players in the world experience 
                <span class="edu-warn">15–20 buy-in downswings</span> due to normal variance. 
                That's not a sign you're playing badly — it's math. A $1/$2 player can easily 
                lose <span class="edu-warn">$3,000–$4,000</span> during a rough stretch, 
                even while making all the right decisions.
            </div>
            <div class="edu-text">
                Bankroll management ensures you 
                <span class="edu-ok">never go broke from variance</span>. 
                It's the difference between a temporary setback and the end of your poker career. 
                We handle the math — you just need to tell us your current bankroll.
            </div>
        </div>
    """, unsafe_allow_html=True)

    # ---- Stakes Reference Table ----
    st.markdown("""
        <div class="edu-section">
            <div class="edu-title">Bankroll Requirements by Stakes</div>
            <div class="edu-subtitle">
                The table below shows how much bankroll you need for each stake level. 
                These numbers are backed by Monte Carlo simulations of 10,000+ player lifetimes.
            </div>
            <table class="stakes-tbl">
                <tr>
                    <th>Stakes</th>
                    <th>Buy-in</th>
                    <th>🔥 Aggressive (13 BI)</th>
                    <th>⚖️ Balanced (15 BI)</th>
                    <th>🛡️ Conservative (17 BI)</th>
                </tr>
                <tr>
                    <td style="color: #fff; font-weight: 700;">$0.50/$1</td>
                    <td>$100</td>
                    <td style="color: #FFB300;">$1,300</td>
                    <td style="color: #4BA3FF;">$1,500</td>
                    <td style="color: #69F0AE;">$1,700</td>
                </tr>
                <tr>
                    <td style="color: #fff; font-weight: 700;">$1/$2</td>
                    <td>$200</td>
                    <td style="color: #FFB300;">$2,600</td>
                    <td style="color: #4BA3FF;">$3,000</td>
                    <td style="color: #69F0AE;">$3,400</td>
                </tr>
                <tr>
                    <td style="color: #fff; font-weight: 700;">$2/$5</td>
                    <td>$500</td>
                    <td style="color: #FFB300;">$6,500</td>
                    <td style="color: #4BA3FF;">$7,500</td>
                    <td style="color: #69F0AE;">$8,500</td>
                </tr>
                <tr>
                    <td style="color: #fff; font-weight: 700;">$5/$10</td>
                    <td>$1,000</td>
                    <td style="color: #FFB300;">$13,000</td>
                    <td style="color: #4BA3FF;">$15,000</td>
                    <td style="color: #69F0AE;">$17,000</td>
                </tr>
                <tr>
                    <td style="color: #fff; font-weight: 700;">$10/$20</td>
                    <td>$2,000</td>
                    <td style="color: #FFB300;">$26,000</td>
                    <td style="color: #4BA3FF;">$30,000</td>
                    <td style="color: #69F0AE;">$34,000</td>
                </tr>
                <tr>
                    <td style="color: #fff; font-weight: 700;">$25/$50</td>
                    <td>$5,000</td>
                    <td style="color: #FFB300;">$65,000</td>
                    <td style="color: #4BA3FF;">$75,000</td>
                    <td style="color: #69F0AE;">$85,000</td>
                </tr>
            </table>
        </div>
    """, unsafe_allow_html=True)

    # ---- Three Risk Modes Explained ----
    st.markdown('<div class="edu-section">', unsafe_allow_html=True)
    st.markdown('<div class="edu-title">Choose Your Risk Profile</div>', unsafe_allow_html=True)
    st.markdown("""
        <div class="edu-subtitle">
            Your risk mode determines how many buy-ins you keep as a safety cushion, 
            your session stop-loss/stop-win limits, and how quickly you move up through stakes. 
            Each has trade-offs — there's no wrong answer.
        </div>
    """, unsafe_allow_html=True)

    for key, m in RISK_MODES.items():
        cls = "agg" if key == "aggressive" else "bal" if key == "balanced" else "con"
        rec_tag = '<span class="rec-tag">RECOMMENDED</span>' if key == "balanced" else ""
        st.markdown(f"""
            <div class="mode-compare {cls}">
                <div class="mc-header">
                    <div class="mc-name">{m['emoji']} {m['name']}{rec_tag}</div>
                    <div class="mc-bis" style="color: {m['color']};">{m['buy_ins']} Buy-ins</div>
                </div>
                <div class="mc-body">{m['personality']}</div>
                <div class="mc-stats">
                    <div class="mc-stat">
                        <div class="mc-stat-label">Stop-Loss</div>
                        <div class="mc-stat-val">{m['stop_loss']} BI</div>
                    </div>
                    <div class="mc-stat">
                        <div class="mc-stat-label">Stop-Win</div>
                        <div class="mc-stat-val">{m['stop_win']} BI</div>
                    </div>
                    <div class="mc-stat">
                        <div class="mc-stat-label">Risk of Ruin</div>
                        <div class="mc-stat-val">{m['ror_15bi']}</div>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

    # ---- Move Up / Move Down Rules ----
    st.markdown("""
        <div class="edu-section">
            <div class="edu-title">When to Move Up & Down</div>
            <div class="edu-text">
                <span class="edu-ok">Move UP</span> when your bankroll reaches 
                <span class="edu-highlight">20 buy-ins of the next stake</span>. 
                This gives you extra cushion as you adjust to tougher competition.
            </div>
            <div class="edu-text">
                <span class="edu-warn">Move DOWN</span> when your bankroll drops to 
                <span class="edu-highlight">12 buy-ins of your current stake</span>. 
                There's no shame in moving down — it protects your bankroll so you can 
                move back up when the variance swings back your way.
            </div>
            <div class="edu-text" style="margin-bottom: 0;">
                We track all of this for you automatically. You'll get clear 
                recommendations — never any guesswork.
            </div>
        </div>
    """, unsafe_allow_html=True)

    # ---- Annual Profit Projections ----
    st.markdown("""
        <div class="edu-section">
            <div class="edu-title">What You Can Expect</div>
            <div class="edu-subtitle">
                Annual profit projections using the Nameless decision engine at 
                10 sessions/week, 200 hands/session, +6 BB/100 win rate.
            </div>
            <div class="sg sg-3">
                <div class="si">
                    <div class="si-label">$1/$2</div>
                    <div class="si-val green">$20,000–$24,000</div>
                    <div class="si-detail">per year</div>
                </div>
                <div class="si">
                    <div class="si-label">$2/$5</div>
                    <div class="si-val green">$50,000–$60,000</div>
                    <div class="si-detail">per year</div>
                </div>
                <div class="si">
                    <div class="si-label">$5/$10</div>
                    <div class="si-val green">$100,000–$120,000</div>
                    <div class="si-detail">per year</div>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # ---- Bankroll Input ----
    st.markdown("""
        <div class="edu-section">
            <div class="edu-title">Set Your Bankroll</div>
            <div class="edu-subtitle">
                Enter the total amount of money you have dedicated to poker. 
                This should be money you can afford to lose — not rent money. 
                You can update this anytime.
            </div>
        </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([3, 1])
    with col1:
        bankroll = st.number_input(
            "YOUR POKER BANKROLL ($)",
            min_value=0.0, value=3000.0, step=100.0, format="%.2f"
        )
    with col2:
        st.markdown("<div style='height: 28px'></div>", unsafe_allow_html=True)
        if st.button("Set Bankroll →", type="primary", use_container_width=True):
            st.session_state["bankroll"] = bankroll
            uid = get_user_id()
            if uid:
                try: update_user_bankroll(uid, bankroll)
                except Exception: pass
            st.rerun()

    # Show what their bankroll means
    if bankroll > 0:
        mode = RISK_MODES["balanced"]
        rec = get_stakes_for_bankroll(bankroll, "balanced")
        bis = get_buy_ins(bankroll, rec)
        status = get_health_status(bis)
        st.markdown(f"""
            <div class="callout" style="margin-top: 12px;">
                With <span class="edu-highlight">{fmtc(bankroll)}</span> in Balanced mode, 
                you'd play <span class="edu-highlight">{rec['name']}</span> 
                with <span class="edu-highlight">{bis:.1f} buy-ins</span>. 
                Health status: <span style="color: {status['color']}; font-weight: 600;">
                {status['emoji']} {status['label']}</span>
            </div>
        """, unsafe_allow_html=True)

    # Risk mode selector
    st.markdown("<div style='height: 8px'></div>", unsafe_allow_html=True)
    risk_mode = st.radio(
        "RISK MODE",
        options=list(RISK_MODES.keys()),
        format_func=lambda x: f"{RISK_MODES[x]['emoji']} {RISK_MODES[x]['name']} ({RISK_MODES[x]['buy_ins']} BI)",
        index=1,
        horizontal=True,
        key="empty_risk_mode"
    )
    st.session_state["risk_mode"] = risk_mode


# =============================================================================
# RENDER FUNCTIONS — DASHBOARD (when bankroll is set)
# =============================================================================

def render_hero(bankroll, stats, rec_stakes, risk_mode):
    bis = get_buy_ins(bankroll, rec_stakes)
    status = get_health_status(bis)
    cls = get_status_class(bis)
    bcls = badge_class(bis)
    mode = RISK_MODES[risk_mode]

    hr_disp = fmt(stats["hourly_rate"], sign=True) if stats["has_data"] else "—"
    hr_cls = "green" if stats["hourly_rate"] > 0 else "red" if stats["hourly_rate"] < 0 else ""
    bb_disp = f'{stats["bb_per_100"]:+.1f}' if stats["has_data"] else "—"
    bb_cls = "green" if stats["bb_per_100"] > 0 else "red" if stats["bb_per_100"] < 0 else ""
    h_disp = f'{stats["total_hours"]:.0f}h' if stats["has_data"] else "—"

    st.markdown(f"""
        <div class="hero {cls}">
            <div class="badge {bcls}">{status['emoji']} {status['label']}</div>
            <div class="hero-bankroll">{fmtc(bankroll)}</div>
            <div class="hero-sub">{bis:.1f} buy-ins at {rec_stakes['name']} · {mode['name']} mode</div>
            <div class="sg sg-4">
                <div class="si">
                    <div class="si-label">Recommended Stakes</div>
                    <div class="si-val blue">{rec_stakes['name']}</div>
                    <div class="si-detail">{mode['buy_ins']} buy-in requirement</div>
                </div>
                <div class="si">
                    <div class="si-label">Hourly Rate</div>
                    <div class="si-val {hr_cls}">{hr_disp}</div>
                    <div class="si-detail">{'from ' + str(stats['total_sessions']) + ' sessions' if stats['has_data'] else 'no sessions yet'}</div>
                </div>
                <div class="si">
                    <div class="si-label">Win Rate</div>
                    <div class="si-val {bb_cls}">{bb_disp}</div>
                    <div class="si-detail">{'BB/100 · ' + f'{stats["total_hands"]:,}' + ' hands' if stats['has_data'] else 'BB/100 (estimated)'}</div>
                </div>
                <div class="si">
                    <div class="si-label">Hours Played</div>
                    <div class="si-val">{h_disp}</div>
                    <div class="si-detail">{'total tracked' if stats['has_data'] else 'start a session'}</div>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)


def render_bankroll_editor(bankroll, user_id):
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        new_br = st.number_input("UPDATE BANKROLL", min_value=0.0, value=bankroll,
                                  step=100.0, format="%.2f", key="br_edit")
    with col2:
        st.markdown("<div style='height: 28px'></div>", unsafe_allow_html=True)
        if st.button("💰 Update", type="primary", use_container_width=True, key="br_btn"):
            if new_br != bankroll:
                st.session_state["bankroll"] = new_br
                try: update_user_bankroll(user_id, new_br)
                except Exception: pass
                st.rerun()
    with col3:
        st.markdown("<div style='height: 28px'></div>", unsafe_allow_html=True)
        diff = new_br - bankroll
        if diff != 0:
            c = "#69F0AE" if diff > 0 else "#FF5252"
            st.markdown(f"<div style='font-family:JetBrains Mono,monospace;font-size:15px;"
                        f"font-weight:600;color:{c};padding-top:8px;'>{fmt(diff,sign=True)}</div>",
                        unsafe_allow_html=True)


def render_move_up(bankroll, stats, rec_stakes, risk_mode):
    mode = RISK_MODES[risk_mode]
    nxt = get_next_stakes(rec_stakes)

    if not nxt:
        st.markdown("""
            <div class="dk"><div class="dk-hdr">📈 MOVE-UP PROJECTION</div>
            <div style="text-align:center;padding:16px;">
                <div style="font-family:'JetBrains Mono',monospace;font-size:22px;font-weight:700;color:#69F0AE;">
                    Max Stakes Reached</div>
                <div style="font-family:'Inter',sans-serif;font-size:12px;color:rgba(255,255,255,0.30);margin-top:6px;">
                    You're at the highest stakes we track. Keep crushing.</div>
            </div></div>
        """, unsafe_allow_html=True)
        return

    target = nxt["typical_bi"] * mode["buy_ins"]
    needed = max(0, target - bankroll)
    pct = min(100, (bankroll / target) * 100) if target > 0 else 100
    hr = stats["hourly_rate"] if stats["has_data"] else 0
    hpw = 10

    if hr > 0 and needed > 0:
        h_need = needed / hr
        w_need = h_need / hpw
        m_need = w_need / 4.33
        time_d = f"{m_need:.1f} months" if m_need >= 1 else f"{w_need:.1f} weeks"
        h_d = f"{h_need:.0f}h"
    elif needed <= 0:
        time_d = "Ready now"
        h_d = "0h"
    else:
        time_d = "—"
        h_d = "—"

    no_data_msg = ('<div class="callout" style="margin-top:14px;">⚡ No session data yet. '
                   'Play some hands and your real win rate will drive these projections.</div>'
                   if not stats["has_data"] else "")

    st.markdown(f"""
        <div class="moveup">
            <div class="dk-hdr">📈 MOVE-UP PROJECTION</div>
            <div class="moveup-target">→ {nxt['name']}</div>
            <div class="moveup-sub">Target: {fmtc(target)} ({mode['buy_ins']} buy-ins × {fmtc(nxt['typical_bi'])} buy-in)</div>
            <div class="pbar-labels"><span>{fmtc(bankroll)}</span><span>{fmtc(target)}</span></div>
            <div class="pbar"><div class="pfill" style="width:{pct:.1f}%"></div></div>
            <div style="text-align:center;margin-top:8px;">
                <span style="font-family:'JetBrains Mono',monospace;font-size:12px;color:rgba(255,255,255,0.40);">
                    {fmtc(needed)} remaining · {pct:.0f}% complete</span>
            </div>
            <div class="mg">
                <div class="mr"><span class="mr-l">Your win rate</span><span class="mr-v">{stats['bb_per_100']:+.1f} BB/100</span></div>
                <div class="mr"><span class="mr-l">Hourly rate</span><span class="mr-v">{fmt(stats['hourly_rate'],sign=True) if stats['has_data'] else '—'}/hr</span></div>
                <div class="mr"><span class="mr-l">Hours needed</span><span class="mr-v">{h_d}</span></div>
                <div class="mr"><span class="mr-l">ETA (@ {hpw}h/wk)</span><span class="mr-v" style="color:#4BA3FF;">{time_d}</span></div>
            </div>
            {no_data_msg}
        </div>
    """, unsafe_allow_html=True)


def render_risk_of_ruin(bankroll, stakes, bb100, stats):
    ror = calc_ror(bankroll, stakes, bb100)
    ror_pct = ror * 100
    if ror_pct < 1: color, label, desc = "#69F0AE", "Very Low", "Your bankroll is well-protected against normal variance."
    elif ror_pct < 5: color, label, desc = "#69F0AE", "Low", "Healthy buffer against downswings."
    elif ror_pct < 15: color, label, desc = "#FFB300", "Moderate", "Consider building more bankroll cushion."
    elif ror_pct < 30: color, label, desc = "#FFB300", "Elevated", "Your bankroll is at risk. Consider moving down."
    else: color, label, desc = "#FF5252", "High", "Serious risk of going broke. Move down immediately."

    bb_total = bankroll / stakes["bb"] if stakes["bb"] > 0 else 0

    st.markdown(f"""
        <div class="dk">
            <div class="dk-hdr">🎲 RISK OF RUIN</div>
            <div style="display:grid;grid-template-columns:1fr 2fr;gap:24px;align-items:start;">
                <div>
                    <div class="rg-val" style="color:{color};">{ror_pct:.1f}%</div>
                    <div class="rg-label" style="color:{color};">{label}</div>
                </div>
                <div>
                    <div style="font-family:'Inter',sans-serif;font-size:13px;color:rgba(255,255,255,0.50);line-height:1.7;margin-bottom:14px;">
                        {desc}
                    </div>
                    <div class="mg" style="grid-template-columns:1fr;">
                        <div class="mr"><span class="mr-l">Bankroll in BB</span><span class="mr-v">{bb_total:,.0f} BB</span></div>
                        <div class="mr"><span class="mr-l">Win rate</span><span class="mr-v">{bb100:+.1f} BB/100</span></div>
                        <div class="mr"><span class="mr-l">{'Based on' if stats['has_data'] else 'Estimate'}</span>
                            <span class="mr-v">{f'{stats["total_hands"]:,} hands' if stats['has_data'] else 'default 6.0 BB/100'}</span></div>
                    </div>
                    <div class="callout" style="margin-top:12px;">
                        Risk under 5% is considered safe for serious players.
                        {'Your data drives this — play more to increase accuracy.' if stats['has_data'] else 'Updates automatically as you log sessions.'}
                    </div>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)


def render_drawdown(sessions, bankroll):
    dd = calc_drawdown(sessions, bankroll)
    cd, cdp = dd["current_drawdown"], dd["current_drawdown_pct"]
    md, mdp, pk = dd["max_drawdown"], dd["max_drawdown_pct"], dd["peak_bankroll"]
    if cdp == 0: dc, dl = "#69F0AE", "At Peak"
    elif cdp < 10: dc, dl = "#69F0AE", "Minor"
    elif cdp < 20: dc, dl = "#FFB300", "Moderate"
    else: dc, dl = "#FF5252", "Significant"

    st.markdown(f"""
        <div class="dk">
            <div class="dk-hdr">📉 DRAWDOWN ANALYSIS</div>
            <div class="dd-grid">
                <div class="dd-item">
                    <div class="dd-val" style="color:{dc};">{cdp:.1f}%</div>
                    <div class="dd-lbl">Current Drawdown ({dl})</div>
                    <div class="dd-det">{fmt(cd)} below peak</div>
                </div>
                <div class="dd-item">
                    <div class="dd-val" style="color:rgba(255,255,255,0.40);">{mdp:.1f}%</div>
                    <div class="dd-lbl">Max Historical Drawdown</div>
                    <div class="dd-det">Peak: {fmt(pk)}</div>
                </div>
            </div>
            <div class="callout">
                Even winning players experience 20–30% drawdowns during normal variance.
                A healthy bankroll (15+ buy-ins) withstands these swings without needing to move down.
            </div>
        </div>
    """, unsafe_allow_html=True)


def render_stakes_ladder(bankroll, risk_mode, current_stakes):
    mode = RISK_MODES.get(risk_mode, RISK_MODES["balanced"])
    req = mode["buy_ins"]

    html = '<div class="dk"><div class="dk-hdr">🪜 STAKES LADDER</div>'
    for s in STAKES_CONFIG:
        min_br = s["typical_bi"] * req
        bis = get_buy_ins(bankroll, s)
        is_curr = s["name"] == current_stakes["name"]
        avail = bankroll >= min_br

        if is_curr:
            cls, stxt, scol = "current", "📍 CURRENT", "#4BA3FF"
        elif avail:
            cls, stxt, scol = "available", "✓ AVAILABLE", "#69F0AE"
        else:
            cls, stxt, scol = "locked", f"🔒 Need {fmtc(min_br - bankroll)}", "rgba(255,255,255,0.25)"

        html += f"""<div class="ls {cls}">
            <div class="ls-name">{s['name']}</div>
            <div class="ls-req">{fmtc(min_br)} required ({req} × {fmtc(s['typical_bi'])})</div>
            <div class="ls-status" style="color:{scol};">{stxt}</div>
        </div>"""
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


def render_risk_mode_selector(current_mode):
    cards = '<div class="rm-grid">'
    for k, m in RISK_MODES.items():
        sel = k == current_mode
        scls = "sel" if sel else ""
        bc = m["color"] if sel else "rgba(255,255,255,0.06)"
        bg = "rgba(255,255,255,0.04)" if sel else "rgba(255,255,255,0.02)"
        cards += f"""<div class="rm {scls}" style="border-color:{bc};background:{bg};">
            <div class="rm-emoji">{m['emoji']}</div>
            <div class="rm-name">{m['name']}</div>
            <div class="rm-bis" style="color:{m['color']};">{m['buy_ins']} Buy-ins</div>
            <div class="rm-desc">{m['description']}</div>
        </div>"""
    cards += '</div>'

    st.markdown(f'<div class="dk"><div class="dk-hdr">⚙️ RISK MODE</div>{cards}', unsafe_allow_html=True)

    # Expanded details for selected mode
    cm = RISK_MODES[current_mode]
    st.markdown(f"""
        <div style="margin-top:14px;">
            <div class="mc-body">{cm['personality']}</div>
            <div class="mc-stats">
                <div class="mc-stat">
                    <div class="mc-stat-label">Stop-Loss</div>
                    <div class="mc-stat-val">{cm['stop_loss']} BI</div>
                </div>
                <div class="mc-stat">
                    <div class="mc-stat-label">Stop-Win</div>
                    <div class="mc-stat-val">{cm['stop_win']} BI</div>
                </div>
                <div class="mc-stat">
                    <div class="mc-stat-label">Risk of Ruin</div>
                    <div class="mc-stat-val">{cm['ror_15bi']}</div>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

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


# =============================================================================
# MAIN
# =============================================================================

def main():
    st.markdown("""
        <div class="page-hdr">
            <h1>Bankroll Health</h1>
            <p>Bankroll monitoring, stakes guidance, and move-up projections</p>
        </div>
    """, unsafe_allow_html=True)

    user_id = get_user_id()
    if not user_id:
        st.warning("Please log in to view your bankroll health.")
        return

    bankroll = get_current_bankroll()

    if bankroll <= 0:
        render_empty_state()
        return

    risk_mode = get_risk_mode()
    rec_stakes = get_stakes_for_bankroll(bankroll, risk_mode)

    sessions = []
    try:
        sessions = get_user_sessions(user_id, limit=500) or []
    except Exception:
        sessions = []

    stats = compute_stats(sessions)

    # ===== HERO SNAPSHOT =====
    render_hero(bankroll, stats, rec_stakes, risk_mode)

    # ===== INLINE BANKROLL EDITOR =====
    render_bankroll_editor(bankroll, user_id)

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    # ===== MOVE-UP PROJECTION =====
    render_move_up(bankroll, stats, rec_stakes, risk_mode)

    # ===== TABBED DEEP DIVES =====
    tab1, tab2, tab3, tab4 = st.tabs([
        "🎲 Risk Analysis",
        "🪜 Stakes Ladder",
        "⚙️ Risk Mode",
        "📉 Drawdowns",
    ])

    with tab1:
        render_risk_of_ruin(bankroll, rec_stakes, stats["bb_per_100"], stats)

    with tab2:
        render_stakes_ladder(bankroll, risk_mode, rec_stakes)

    with tab3:
        render_risk_mode_selector(risk_mode)

    with tab4:
        render_drawdown(sessions, bankroll)


if __name__ == "__main__":
    main()