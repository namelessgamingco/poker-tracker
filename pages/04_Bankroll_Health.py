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
                your risk mode's buy-in requirement at the next stake level
                (e.g. <span class="edu-highlight">15 buy-ins</span> in Balanced mode). 
                The app tracks this automatically and tells you when you're ready.
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
                Annual profit projections at 10 sessions/week, 200 hands/session.
                Includes table winnings (+7 BB/100 average) plus 30% rakeback.
            </div>
            <div class="sg sg-3">
                <div class="si">
                    <div class="si-label">$1/$2</div>
                    <div class="si-val green">$18,000–$22,000</div>
                    <div class="si-detail">per year (table + rakeback)</div>
                </div>
                <div class="si">
                    <div class="si-label">$2/$5</div>
                    <div class="si-val green">$42,000–$50,000</div>
                    <div class="si-detail">per year (table + rakeback)</div>
                </div>
                <div class="si">
                    <div class="si-label">$5/$10</div>
                    <div class="si-val green">$80,000–$96,000</div>
                    <div class="si-detail">per year (table + rakeback)</div>
                </div>
            </div>
            <div style="font-family:'Inter',sans-serif;font-size:11px;color:rgba(255,255,255,0.25);
                margin-top:12px;line-height:1.6;text-align:center;">
                Table winnings: 100,000 hands/yr × win rate × BB size.
                Rakeback: ~30% of rake generated (platform dependent).
                See the <span style="color:rgba(255,255,255,0.40);font-weight:600;">EV System</span> page for detailed breakdowns.
            </div>
        </div>
    """, unsafe_allow_html=True)

    # ================================================================
    # INTERACTIVE SETUP — Risk Mode + Bankroll + Live Preview
    # ================================================================

    st.markdown("""
        <div class="edu-section">
            <div class="edu-title">Set Up Your Bankroll</div>
            <div class="edu-subtitle">
                Two things determine which stakes you should play: your 
                <span class="edu-highlight">bankroll</span> (how much money you have) and your 
                <span class="edu-highlight">risk mode</span> (how much safety cushion you want). 
                Together, these tell us the highest stakes you can safely play without 
                risking going broke during a normal downswing.
            </div>
        </div>
    """, unsafe_allow_html=True)

    # ---- STEP 1: Risk Mode ----
    st.markdown("""
        <div class="edu-section">
            <div class="edu-title" style="font-size: 15px;">
                Step 1 — How much risk can you handle?
            </div>
            <div class="edu-text" style="margin-bottom: 4px;">
                This sets your safety cushion. More buy-ins = safer but slower progression. 
                Fewer buy-ins = faster progression but more exposure to variance. 
                <span style="color: rgba(255,255,255,0.60);">Not sure? Start with Balanced — you can change anytime.</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

    risk_mode = st.radio(
        "YOUR RISK MODE",
        options=list(RISK_MODES.keys()),
        format_func=lambda x: f"{RISK_MODES[x]['emoji']} {RISK_MODES[x]['name']} — {RISK_MODES[x]['buy_ins']} buy-in cushion",
        index=1,
        horizontal=False,
        key="empty_risk_mode"
    )
    st.session_state["risk_mode"] = risk_mode

    # Show selected mode details
    sel_mode = RISK_MODES[risk_mode]
    sel_cls = "agg" if risk_mode == "aggressive" else "bal" if risk_mode == "balanced" else "con"
    rec_tag = '<span class="rec-tag">RECOMMENDED</span>' if risk_mode == "balanced" else ""
    st.markdown(f"""
        <div class="mode-compare {sel_cls}" style="margin-top: 8px; margin-bottom: 20px;">
            <div class="mc-header">
                <div class="mc-name">{sel_mode['emoji']} {sel_mode['name']}{rec_tag}</div>
                <div class="mc-bis" style="color: {sel_mode['color']};">{sel_mode['buy_ins']} Buy-ins</div>
            </div>
            <div class="mc-body">{sel_mode['personality']}</div>
            <div class="mc-stats">
                <div class="mc-stat">
                    <div class="mc-stat-label">Session Stop-Loss</div>
                    <div class="mc-stat-val">{sel_mode['stop_loss']} BI</div>
                </div>
                <div class="mc-stat">
                    <div class="mc-stat-label">Session Stop-Win</div>
                    <div class="mc-stat-val">{sel_mode['stop_win']} BI</div>
                </div>
                <div class="mc-stat">
                    <div class="mc-stat-label">Risk of Ruin</div>
                    <div class="mc-stat-val">{sel_mode['ror_15bi']}</div>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # ---- STEP 2: Bankroll ----
    st.markdown(f"""
        <div class="edu-section">
            <div class="edu-title" style="font-size: 15px;">
                Step 2 — Enter your poker bankroll
            </div>
            <div class="edu-text" style="margin-bottom: 4px;">
                This is the total money you've set aside for poker — not your life savings. 
                With <span style="color: {sel_mode['color']}; font-weight: 600;">{sel_mode['name']}</span> mode, 
                you need <span class="edu-highlight">{sel_mode['buy_ins']} buy-ins</span> at your stake level to play safely. 
                We'll show you exactly which stakes your bankroll unlocks.
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
                try:
                    update_user_bankroll(uid, bankroll)
                    from db import get_supabase_admin
                    supabase = get_supabase_admin()
                    supabase.table("poker_profiles").update(
                        {"user_mode": risk_mode}
                    ).eq("user_id", uid).execute()
                except Exception:
                    pass
            st.rerun()

    # ---- LIVE PREVIEW — What your bankroll unlocks ----
    if bankroll > 0:
        req_bis = sel_mode["buy_ins"]
        rec = get_stakes_for_bankroll(bankroll, risk_mode)
        rec_bis = get_buy_ins(bankroll, rec)
        rec_status = get_health_status(rec_bis)

        # Build mini stakes ladder for this bankroll + mode
        ladder_html = ""
        for s in STAKES_CONFIG:
            min_br = s["typical_bi"] * req_bis
            is_rec = s["name"] == rec["name"]
            is_avail = bankroll >= min_br

            if is_rec:
                sel_r = "75,163,255" if risk_mode == "balanced" else "255,179,0" if risk_mode == "aggressive" else "105,240,174"
                row_bg = f"rgba({sel_r},0.08)"
                row_border = f"1px solid {sel_mode['color']}40"
                name_color = sel_mode['color']
                tag = (f'<span style="font-family:Inter,sans-serif;font-size:9px;font-weight:600;'
                       f'color:{sel_mode["color"]};background:rgba(255,255,255,0.05);padding:2px 6px;'
                       f'border-radius:3px;text-transform:uppercase;letter-spacing:0.05em;margin-left:8px;">'
                       f'← YOUR STAKES</span>')
            elif is_avail:
                row_bg = "rgba(105,240,174,0.03)"
                row_border = "1px solid rgba(105,240,174,0.10)"
                name_color = "#69F0AE"
                tag = ""
            else:
                row_bg = "rgba(255,255,255,0.01)"
                row_border = "1px solid rgba(255,255,255,0.03)"
                name_color = "rgba(255,255,255,0.20)"
                tag = ""

            check = "✓" if is_avail else "🔒"
            need_text = ""
            if not is_avail:
                need_text = (f'<span style="color:rgba(255,255,255,0.20);font-size:11px;">'
                             f' — need {fmtc(min_br - bankroll)} more</span>')

            ladder_html += (
                f'<div style="display:flex;align-items:center;padding:10px 14px;border-radius:8px;'
                f'margin-bottom:4px;background:{row_bg};border:{row_border};">'
                f'<span style="font-size:12px;width:20px;">{check}</span>'
                f'<span style="font-family:JetBrains Mono,monospace;font-size:13px;font-weight:700;'
                f'color:{name_color};min-width:85px;">{s["name"]}</span>'
                f'<span style="font-family:Inter,sans-serif;font-size:11px;color:rgba(255,255,255,0.30);flex:1;">'
                f'{fmtc(min_br)} required{need_text}</span>'
                f'{tag}</div>'
            )

        # Show comparison across all 3 modes
        compare_html = ""
        for mk, mv in RISK_MODES.items():
            m_rec = get_stakes_for_bankroll(bankroll, mk)
            m_bis = get_buy_ins(bankroll, m_rec)
            is_selected = mk == risk_mode
            opacity = "1" if is_selected else "0.45"
            border = f"1px solid {mv['color']}40" if is_selected else "1px solid rgba(255,255,255,0.04)"
            bg = "rgba(255,255,255,0.03)" if is_selected else "rgba(255,255,255,0.01)"
            sel_dot = (f'<span style="color:{mv["color"]};font-size:8px;margin-right:4px;">●</span>'
                       if is_selected else "")

            compare_html += (
                f'<div style="background:{bg};border:{border};border-radius:8px;padding:12px 14px;'
                f'text-align:center;opacity:{opacity};">'
                f'<div style="font-family:Inter,sans-serif;font-size:10px;color:rgba(255,255,255,0.30);'
                f'text-transform:uppercase;letter-spacing:0.05em;margin-bottom:4px;">'
                f'{sel_dot}{mv["emoji"]} {mv["name"]}</div>'
                f'<div style="font-family:JetBrains Mono,monospace;font-size:18px;font-weight:700;'
                f'color:{mv["color"]};">{m_rec["name"]}</div>'
                f'<div style="font-family:JetBrains Mono,monospace;font-size:11px;'
                f'color:rgba(255,255,255,0.35);margin-top:2px;">{m_bis:.1f} buy-ins</div>'
                f'</div>'
            )

        # Check if modes differ
        all_same = all(
            get_stakes_for_bankroll(bankroll, m)['name'] == rec['name'] for m in RISK_MODES
        )
        mode_note = ('Same stakes across all modes at this bankroll.' if all_same
                     else 'Different modes may recommend different stakes for your bankroll. '
                          'A higher risk mode can unlock higher stakes sooner.')

        # Move up/down callout
        nxt = get_next_stakes(rec)
        move_up_text = (f'Move up to {nxt["name"]} when you reach {fmtc(nxt["typical_bi"] * req_bis)} '
                        f'({req_bis} buy-ins at next level).' if nxt else "You're at the highest tracked stakes.")
        move_down_text = (f' Move down if you drop to {fmtc(rec["typical_bi"] * 12)} (12 buy-ins).'
                          if rec != STAKES_CONFIG[0] else '')

        # ---- Render the live preview in separate markdown calls ----
        # Title
        st.markdown(f"""
            <div class="edu-section" style="margin-top: 12px;">
                <div class="edu-title" style="font-size: 15px;">
                    Your Bankroll: {fmtc(bankroll)} in {sel_mode['name']} Mode
                </div>
        """, unsafe_allow_html=True)

        # 3-mode comparison strip
        st.markdown(f"""
            <div style="margin-bottom: 18px;">
                <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:10px;">
                    {compare_html}
                </div>
                <div style="font-family:'Inter',sans-serif;font-size:11px;color:rgba(255,255,255,0.25);text-align:center;">
                    {mode_note}
                </div>
            </div>
        """, unsafe_allow_html=True)

        # Stakes ladder header + rows
        st.markdown(f"""
            <div style="font-family:'Inter',sans-serif;font-size:11px;font-weight:600;color:rgba(255,255,255,0.30);
                text-transform:uppercase;letter-spacing:0.06em;margin-bottom:8px;">
                Stakes unlocked with {fmtc(bankroll)}
            </div>
        """, unsafe_allow_html=True)

        st.markdown(ladder_html, unsafe_allow_html=True)

        # Bottom callout + close the edu-section div
        st.markdown(f"""
                <div class="callout" style="margin-top: 14px;">
                    You'll play <span style="color:{sel_mode['color']};font-weight:600;">{rec['name']}</span> with
                    <span class="edu-highlight">{rec_bis:.1f} buy-ins</span> of cushion.
                    Health: <span style="color:{rec_status['color']};font-weight:600;">{rec_status['emoji']} {rec_status['label']}</span>.
                    {move_up_text}{move_down_text}
                </div>
            </div>
        """, unsafe_allow_html=True)


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

    # Explain data sources: bankroll = manual, stats = automatic from sessions
    if stats["has_data"]:
        source_text = (
            f'Your bankroll updates automatically after each session. '
            f'Adjust it below for deposits or withdrawals. '
            f'Hourly rate, win rate, and hours are pulled from your '
            f'{stats["total_sessions"]} tracked sessions.'
        )
    else:
        source_text = (
            'Your bankroll will update automatically after each session. '
            'Adjust it below for deposits or withdrawals. '
            'Once you play sessions, your hourly rate and win rate will populate automatically '
            'from real data and power your move-up projections.'
        )

    st.markdown(f"""
        <div style="font-family:'Inter',sans-serif;font-size:11px;color:rgba(255,255,255,0.20);
            text-align:center;margin-top:-12px;margin-bottom:16px;line-height:1.5;">
            {source_text}
        </div>
    """, unsafe_allow_html=True)


def render_bankroll_editor(bankroll, user_id, risk_mode, rec_stakes):
    """Bankroll editor with context about when/why to update and impact preview."""
    mode = RISK_MODES[risk_mode]
    bis = get_buy_ins(bankroll, rec_stakes)
    nxt = get_next_stakes(rec_stakes)

    # Context: when should you update?
    st.markdown(f"""
        <div class="dk">
            <div class="dk-hdr">💰 UPDATE BANKROLL</div>
            <div style="font-family:'Inter',sans-serif;font-size:12px;color:rgba(255,255,255,0.40);
                line-height:1.6;margin-bottom:16px;">
                Your bankroll updates automatically after each session. 
                Use this to adjust for deposits, withdrawals, or to sync with your actual total across all accounts.
                Currently <span style="color:#fff;font-weight:600;">{fmtc(bankroll)}</span> = 
                <span style="color:{mode['color']};font-weight:600;">{bis:.1f} buy-ins</span> at 
                <span style="color:#fff;font-weight:600;">{rec_stakes['name']}</span>.
            </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([3, 1])
    with col1:
        new_br = st.number_input("NEW BANKROLL AMOUNT", min_value=0.0, value=bankroll,
                                  step=100.0, format="%.2f", key="br_edit")
    with col2:
        st.markdown("<div style='height: 28px'></div>", unsafe_allow_html=True)
        if st.button("💰 Update", type="primary", use_container_width=True, key="br_btn"):
            if new_br != bankroll:
                st.session_state["bankroll"] = new_br
                try: update_user_bankroll(user_id, new_br)
                except Exception: pass
                st.rerun()

    # Live impact preview when value differs
    if new_br != bankroll and new_br > 0:
        diff = new_br - bankroll
        diff_color = "#69F0AE" if diff > 0 else "#FF5252"
        new_rec = get_stakes_for_bankroll(new_br, risk_mode)
        new_bis = get_buy_ins(new_br, new_rec)
        new_status = get_health_status(new_bis)
        stakes_changed = new_rec["name"] != rec_stakes["name"]

        # Build impact items
        val_cls = 'amber' if stakes_changed else 'blue'
        change_note = '⚠️ STAKES CHANGE' if stakes_changed else 'no change'
        arrow = '↑' if new_bis > bis else '↓'
        impact_html = (
            f'<div style="margin-top:12px;padding:14px 18px;background:rgba(255,255,255,0.02);'
            f'border:1px solid rgba(255,255,255,0.05);border-radius:10px;">'
            f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;">'
            f'<span style="font-family:JetBrains Mono,monospace;font-size:16px;'
            f'font-weight:700;color:{diff_color};">{fmt(diff, sign=True)}</span>'
            f'<span style="font-family:Inter,sans-serif;font-size:11px;'
            f'color:rgba(255,255,255,0.30);">change</span></div>'
            f'<div class="sg sg-3">'
            f'<div class="si"><div class="si-label">New Stakes</div>'
            f'<div class="si-val {val_cls}">{new_rec["name"]}</div>'
            f'<div class="si-detail">{change_note}</div></div>'
            f'<div class="si"><div class="si-label">Buy-ins</div>'
            f'<div class="si-val">{new_bis:.1f}</div>'
            f'<div class="si-detail">{arrow} from {bis:.1f}</div></div>'
            f'<div class="si"><div class="si-label">Health</div>'
            f'<div class="si-val" style="color:{new_status["color"]};">{new_status["label"]}</div>'
            f'<div class="si-detail">{new_status["emoji"]}</div></div>'
            f'</div>'
        )

        if stakes_changed:
            if new_rec["bb"] > rec_stakes["bb"]:
                impact_html += (
                    f'<div class="callout" style="margin-top:10px;">'
                    f'📈 This bankroll increase unlocks <span style="color:#69F0AE;font-weight:600;">{new_rec["name"]}</span> stakes. '
                    f'You\'ll have {new_bis:.1f} buy-ins at the higher level.</div>'
                )
            else:
                impact_html += (
                    f'<div class="callout warn" style="margin-top:10px;">'
                    f'📉 This drop moves your recommended stakes down to '
                    f'<span style="color:#FFB300;font-weight:600;">{new_rec["name"]}</span>. '
                    f'Protect your bankroll by playing at the recommended level.</div>'
                )

        impact_html += "</div>"
        st.markdown(impact_html, unsafe_allow_html=True)

    # Move-up/down thresholds for context
    threshold_parts = []
    if nxt:
        move_up_br = nxt["typical_bi"] * mode["buy_ins"]
        threshold_parts.append(
            f'Move up to <span style="color:#69F0AE;font-weight:600;">{nxt["name"]}</span> '
            f'at {fmtc(move_up_br)} ({mode["buy_ins"]} buy-ins)'
        )
    if rec_stakes != STAKES_CONFIG[0]:
        move_down_br = rec_stakes["typical_bi"] * 12
        threshold_parts.append(
            f'Move down at {fmtc(move_down_br)} (12 buy-ins)'
        )

    if threshold_parts:
        st.markdown(f"""
            <div style="font-family:'Inter',sans-serif;font-size:11px;color:rgba(255,255,255,0.25);
                margin-top:12px;line-height:1.6;">
                {'  ·  '.join(threshold_parts)}
            </div>
        """, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


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

        html += (
            f'<div class="ls {cls}">'
            f'<div class="ls-name">{s["name"]}</div>'
            f'<div class="ls-req">{fmtc(min_br)} required ({req} × {fmtc(s["typical_bi"])})</div>'
            f'<div class="ls-status" style="color:{scol};">{stxt}</div>'
            f'</div>'
        )
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


def render_risk_mode_selector(current_mode, bankroll, rec_stakes):
    """Risk mode selector that shows impact of switching modes on your actual bankroll."""
    mode = RISK_MODES[current_mode]
    bis = get_buy_ins(bankroll, rec_stakes)

    # Build comparison cards showing what each mode means for THIS bankroll
    cards = '<div class="rm-grid">'
    for k, m in RISK_MODES.items():
        sel = k == current_mode
        m_rec = get_stakes_for_bankroll(bankroll, k)
        m_bis = get_buy_ins(bankroll, m_rec)
        m_status = get_health_status(m_bis)
        stakes_differ = m_rec["name"] != rec_stakes["name"]

        scls = "sel" if sel else ""
        bc = m["color"] if sel else "rgba(255,255,255,0.06)"
        bg = "rgba(255,255,255,0.04)" if sel else "rgba(255,255,255,0.02)"

        # Show stakes + buy-ins for this mode
        stakes_color = m["color"] if sel else "rgba(255,255,255,0.55)"
        current_tag = ('<span style="font-size:8px;color:rgba(255,255,255,0.30);'
                       'text-transform:uppercase;letter-spacing:0.05em;">CURRENT</span><br>'
                       if sel else '')

        cards += (
            f'<div class="rm {scls}" style="border-color:{bc};background:{bg};">'
            f'{current_tag}'
            f'<div class="rm-emoji">{m["emoji"]}</div>'
            f'<div class="rm-name">{m["name"]}</div>'
            f'<div class="rm-bis" style="color:{m["color"]};">{m["buy_ins"]} Buy-ins</div>'
            f'<div style="margin-top:10px;padding-top:10px;border-top:1px solid rgba(255,255,255,0.05);">'
            f'<div style="font-family:JetBrains Mono,monospace;font-size:14px;font-weight:700;'
            f'color:{stakes_color};">{m_rec["name"]}</div>'
            f'<div style="font-family:Inter,sans-serif;font-size:10px;color:rgba(255,255,255,0.30);'
            f'margin-top:2px;">{m_bis:.1f} buy-ins · {m_status["emoji"]} {m_status["label"]}</div>'
            f'</div>'
            f'<div class="rm-desc" style="margin-top:8px;">{m["description"]}</div>'
            f'</div>'
        )
    cards += '</div>'

    # Render header and intro text
    st.markdown(f"""
        <div class="dk">
            <div class="dk-hdr">⚙️ RISK MODE</div>
            <div style="font-family:'Inter',sans-serif;font-size:12px;color:rgba(255,255,255,0.40);
                line-height:1.6;margin-bottom:16px;">
                Your risk mode sets how many buy-ins you keep as a safety cushion. 
                Changing modes may change your recommended stakes. Below shows what each mode 
                means for your current bankroll of <span style="color:#fff;font-weight:600;">{fmtc(bankroll)}</span>.
            </div>
    """, unsafe_allow_html=True)

    # Render mode cards separately
    st.markdown(cards, unsafe_allow_html=True)

    # Expanded details for selected mode
    cm = RISK_MODES[current_mode]
    st.markdown(f"""
        <div style="margin-top:14px;">
            <div class="mc-body">{cm['personality']}</div>
            <div class="mc-stats">
                <div class="mc-stat">
                    <div class="mc-stat-label">Session Stop-Loss</div>
                    <div class="mc-stat-val">{cm['stop_loss']} BI ({fmtc(cm['stop_loss'] * rec_stakes['typical_bi'])})</div>
                </div>
                <div class="mc-stat">
                    <div class="mc-stat-label">Session Stop-Win</div>
                    <div class="mc-stat-val">{cm['stop_win']} BI ({fmtc(cm['stop_win'] * rec_stakes['typical_bi'])})</div>
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

    # Show what would change if switching
    if new_mode != current_mode:
        new_m = RISK_MODES[new_mode]
        new_rec = get_stakes_for_bankroll(bankroll, new_mode)
        new_bis = get_buy_ins(bankroll, new_rec)
        new_status = get_health_status(new_bis)
        stakes_change = new_rec["name"] != rec_stakes["name"]

        callout_cls = "callout warn" if stakes_change else "callout"
        stakes_note = ""
        if stakes_change:
            if new_rec["bb"] > rec_stakes["bb"]:
                stakes_note = (f'<br>📈 This unlocks <span style="color:#69F0AE;font-weight:600;">'
                               f'{new_rec["name"]}</span> — you have enough buy-ins at the higher cushion requirement.')
            else:
                stakes_note = (f'<br>📉 Stakes drop to <span style="color:#FFB300;font-weight:600;">'
                               f'{new_rec["name"]}</span> — {new_m["name"]} mode requires more buy-ins per stake level.')

        st.markdown(f"""
            <div class="{callout_cls}" style="margin-top:10px;">
                Switching to <span style="color:{new_m['color']};font-weight:600;">{new_m['name']}</span>: 
                Play <span style="font-weight:600;">{new_rec['name']}</span> with {new_bis:.1f} buy-ins.
                Health: <span style="color:{new_status['color']};font-weight:600;">{new_status['emoji']} {new_status['label']}</span>.
                Stop-loss changes to {new_m['stop_loss']} BI ({fmtc(new_m['stop_loss'] * new_rec['typical_bi'])}).
                {stakes_note}
            </div>
        """, unsafe_allow_html=True)

        st.session_state["risk_mode"] = new_mode
        try:
            from db import get_supabase_admin
            supabase = get_supabase_admin()
            uid = get_user_id()
            if uid:
                supabase.table("poker_profiles").update(
                    {"user_mode": new_mode}
                ).eq("user_id", uid).execute()
        except Exception:
            pass
        st.rerun()


def render_rakeback(bankroll, rec_stakes, stats, risk_mode):
    """Rakeback section — numbers match the EV System page exactly."""
    mode = RISK_MODES[risk_mode]
    bb = rec_stakes["bb"]
    bi = rec_stakes["typical_bi"]
    sub_cost = 299  # monthly subscription

    # Volume: 8,000 hands/month (200 hands/session × 40 sessions) — matches EV System page
    hands_per_month = 8000

    # Monthly gross win rate income from EV System page (average win rate × volume)
    monthly_gross = {
        "$0.50/$1": 640, "$1/$2": 1120, "$2/$5": 2800,
        "$5/$10": 4800, "$10/$20": 8000, "$25/$50": 16000,
    }
    # Monthly net = gross - $299 subscription
    gross = monthly_gross.get(rec_stakes["name"], 1120)
    net = gross - sub_cost

    # Rake per 100 hands (mid-range from EV System page)
    # $0.50/$1: $8-12, $1/$2: $14-20, $2/$5: $18-25, $5/$10: $20-30
    rake_per_100_range = {
        "$0.50/$1": (8, 12), "$1/$2": (14, 20), "$2/$5": (18, 25),
        "$5/$10": (20, 30), "$10/$20": (25, 40), "$25/$50": (30, 50),
    }
    rake_low, rake_high = rake_per_100_range.get(rec_stakes["name"], (14, 20))
    rake_mid = (rake_low + rake_high) / 2

    # Monthly rake = (hands / 100) × rake per 100
    monthly_rake_low = (hands_per_month / 100) * rake_low
    monthly_rake_high = (hands_per_month / 100) * rake_high

    # Platform rakeback data
    platforms = [
        {"name": "ACR / Americas Cardroom", "pct": 27, "note": "Elite Benefits VIP tier", "crypto": True},
        {"name": "GGPoker", "pct": 25, "note": "Fish Buffet Gold+", "crypto": True},
        {"name": "Ignition / Bovada", "pct": 15, "note": "Flat rakeback on all hands", "crypto": True},
        {"name": "CoinPoker", "pct": 33, "note": "CHP token staking bonus", "crypto": True},
        {"name": "Winamax", "pct": 35, "note": "VIP Store rewards (EU)", "crypto": False},
        {"name": "iPoker Network", "pct": 40, "note": "Affiliate deals (varies by skin)", "crypto": False},
        {"name": "PokerStars", "pct": 15, "note": "Chest rewards (lower volume)", "crypto": False},
    ]

    # Intro
    st.markdown(f"""
        <div class="dk">
            <div class="dk-hdr">💎 RAKEBACK & SUBSCRIPTION ROI</div>
            <div style="font-family:Inter,sans-serif;font-size:12px;color:rgba(255,255,255,0.40);
                line-height:1.6;margin-bottom:6px;">
                Every hand you play generates rake — and most platforms give a percentage back.
                At <span style="color:#fff;font-weight:600;">{rec_stakes['name']}</span>, you generate
                <span style="color:#fff;font-weight:600;">{fmtc(monthly_rake_low)}–{fmtc(monthly_rake_high)}/month</span> in rake
                over 8,000 hands. Here's what each platform returns to you.
            </div>
            <div style="font-family:Inter,sans-serif;font-size:10px;color:rgba(255,255,255,0.20);
                margin-bottom:16px;">
                Based on 8,000 hands/month (200 hands/session × 40 sessions) · 5% rake with standard caps · 6-max tables
            </div>
    """, unsafe_allow_html=True)

    # Build platform comparison rows
    rows_html = ""
    for p in platforms:
        rb_low = monthly_rake_low * (p["pct"] / 100)
        rb_high = monthly_rake_high * (p["pct"] / 100)
        rb_mid = (rb_low + rb_high) / 2
        annual_rb = rb_mid * 12
        net_after_sub = rb_mid - sub_cost
        covers_sub = net_after_sub >= 0

        if covers_sub:
            sub_tag = '<span style="color:#69F0AE;font-size:9px;font-weight:600;">✓ COVERS SUB</span>'
        else:
            sub_tag = f'<span style="color:#FFB300;font-size:9px;font-weight:600;">OFFSETS {fmtc(rb_mid)}</span>'

        crypto_dot = '<span style="color:#69F0AE;font-size:8px;">₿</span> ' if p["crypto"] else ''

        rows_html += (
            f'<div style="display:grid;grid-template-columns:1.8fr 0.6fr 1fr 0.8fr 1fr;align-items:center;'
            f'padding:10px 14px;border-bottom:1px solid rgba(255,255,255,0.04);">'
            f'<div>'
            f'<div style="font-family:Inter,sans-serif;font-size:13px;color:#E0E0E0;font-weight:600;">{crypto_dot}{p["name"]}</div>'
            f'<div style="font-family:Inter,sans-serif;font-size:10px;color:rgba(255,255,255,0.25);margin-top:2px;">{p["note"]}</div>'
            f'</div>'
            f'<div style="font-family:JetBrains Mono,monospace;font-size:13px;color:{mode["color"]};text-align:center;">{p["pct"]}%</div>'
            f'<div style="font-family:JetBrains Mono,monospace;font-size:12px;color:#E0E0E0;text-align:center;">{fmtc(rb_low)}–{fmtc(rb_high)}</div>'
            f'<div style="font-family:JetBrains Mono,monospace;font-size:13px;color:#69F0AE;text-align:center;">{fmtc(annual_rb)}</div>'
            f'<div style="text-align:right;">{sub_tag}</div>'
            f'</div>'
        )

    # Table header + rows
    st.markdown(
        f'<div style="display:grid;grid-template-columns:1.8fr 0.6fr 1fr 0.8fr 1fr;'
        f'padding:8px 14px;border-bottom:1px solid rgba(255,255,255,0.08);">'
        f'<div style="font-family:Inter,sans-serif;font-size:10px;color:rgba(255,255,255,0.30);text-transform:uppercase;letter-spacing:0.05em;">Platform</div>'
        f'<div style="font-family:Inter,sans-serif;font-size:10px;color:rgba(255,255,255,0.30);text-transform:uppercase;letter-spacing:0.05em;text-align:center;">Rate</div>'
        f'<div style="font-family:Inter,sans-serif;font-size:10px;color:rgba(255,255,255,0.30);text-transform:uppercase;letter-spacing:0.05em;text-align:center;">Monthly</div>'
        f'<div style="font-family:Inter,sans-serif;font-size:10px;color:rgba(255,255,255,0.30);text-transform:uppercase;letter-spacing:0.05em;text-align:center;">Annual</div>'
        f'<div style="font-family:Inter,sans-serif;font-size:10px;color:rgba(255,255,255,0.30);text-transform:uppercase;letter-spacing:0.05em;text-align:right;">vs $299/mo</div>'
        f'</div>',
        unsafe_allow_html=True
    )
    st.markdown(rows_html, unsafe_allow_html=True)

    # Your Monthly Math — matching EV System page numbers
    # Use 30% rakeback as baseline (matches EV System "common baseline")
    rb_30_low = monthly_rake_low * 0.30
    rb_30_high = monthly_rake_high * 0.30
    rb_30_mid = (rb_30_low + rb_30_high) / 2

    # Use actual stats if available, otherwise use EV System gross
    if stats["has_data"] and stats["hourly_rate"] > 0:
        actual_gross = stats["hourly_rate"] * (hands_per_month / 200)  # hours × hourly rate
        win_label = "Your Win Rate Income"
    else:
        actual_gross = gross
        win_label = "Expected Win Rate Income"

    total_monthly = actual_gross + rb_30_mid
    profit_after_sub = total_monthly - sub_cost
    profit_color = "#69F0AE" if profit_after_sub > 0 else "#FF5252"

    st.markdown(f"""
        <div style="margin-top:20px;padding:16px 18px;background:rgba(255,255,255,0.02);
            border:1px solid rgba(255,255,255,0.06);border-radius:10px;">
            <div style="font-family:Inter,sans-serif;font-size:11px;font-weight:600;color:rgba(255,255,255,0.30);
                text-transform:uppercase;letter-spacing:0.06em;margin-bottom:12px;">
                Your Monthly Math at {rec_stakes['name']} (8,000 hands/month · 30% rakeback)
            </div>
            <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;">
                <div style="text-align:center;">
                    <div style="font-family:Inter,sans-serif;font-size:10px;color:rgba(255,255,255,0.30);margin-bottom:4px;">{win_label}</div>
                    <div style="font-family:JetBrains Mono,monospace;font-size:16px;font-weight:700;color:#69F0AE;">{fmtc(actual_gross)}</div>
                </div>
                <div style="text-align:center;">
                    <div style="font-family:Inter,sans-serif;font-size:10px;color:rgba(255,255,255,0.30);margin-bottom:4px;">30% Rakeback</div>
                    <div style="font-family:JetBrains Mono,monospace;font-size:16px;font-weight:700;color:#4BA3FF;">+{fmtc(rb_30_mid)}</div>
                    <div style="font-family:Inter,sans-serif;font-size:9px;color:rgba(255,255,255,0.20);margin-top:2px;">({fmtc(rb_30_low)}–{fmtc(rb_30_high)} range)</div>
                </div>
                <div style="text-align:center;">
                    <div style="font-family:Inter,sans-serif;font-size:10px;color:rgba(255,255,255,0.30);margin-bottom:4px;">Subscription</div>
                    <div style="font-family:JetBrains Mono,monospace;font-size:16px;font-weight:700;color:#FF5252;">-$299</div>
                </div>
                <div style="text-align:center;">
                    <div style="font-family:Inter,sans-serif;font-size:10px;color:rgba(255,255,255,0.30);margin-bottom:4px;">Net Profit</div>
                    <div style="font-family:JetBrains Mono,monospace;font-size:16px;font-weight:700;color:{profit_color};">{fmtc(profit_after_sub)}</div>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # Rakeback alone vs subscription callout
    st.markdown(f"""
        <div class="callout" style="margin-top:14px;">
            💎 At {rec_stakes['name']} with 30% rakeback, you collect
            <span style="color:#4BA3FF;font-weight:600;">{fmtc(rb_30_low)}–{fmtc(rb_30_high)}/month</span> in rakeback alone.
            {'That more than covers the $299 subscription by itself — your poker winnings are pure profit on top.' if rb_30_low >= sub_cost else f'That offsets {fmtc(rb_30_mid)} of the $299 subscription — your poker winnings cover the rest and then some.'}
        </div>
    """, unsafe_allow_html=True)

    # Move-up acceleration
    nxt = get_next_stakes(rec_stakes)
    if nxt:
        target = nxt["typical_bi"] * mode["buy_ins"]
        needed = max(0, target - bankroll)
        if needed > 0:
            months_without = needed / actual_gross if actual_gross > 0 else 0
            months_with = needed / total_monthly if total_monthly > 0 else 0
            saved = months_without - months_with if months_without > 0 else 0

            if saved > 0.5:
                st.markdown(f"""
                    <div class="callout" style="margin-top:10px;">
                        📈 <strong>Rakeback accelerates your move-up.</strong>
                        With rakeback, you reach <span style="color:#69F0AE;font-weight:600;">{nxt['name']}</span> in
                        ~<span style="font-weight:600;">{months_with:.0f} months</span> instead of
                        ~{months_without:.0f} months — saving you
                        <span style="color:#4BA3FF;font-weight:600;">{saved:.0f} months</span> of grinding.
                    </div>
                """, unsafe_allow_html=True)

    # Pro tip
    st.markdown("""
        <div style="margin-top:14px;font-family:Inter,sans-serif;font-size:11px;color:rgba(255,255,255,0.25);line-height:1.6;">
            💡 <strong style="color:rgba(255,255,255,0.40);">Pro tip:</strong>
            Always sign up through a rakeback affiliate — never use default registration.
            Common deals: 25–33% standard, up to 60% at high volume.
            Platforms marked with <span style="color:#69F0AE;">₿</span> accept crypto deposits.
            See the <strong style="color:rgba(255,255,255,0.40);">EV System</strong> page for detailed rake math.
        </div>
    """, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


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

    # Load bankroll from DB if not already in session state (survives refresh/re-login)
    if not st.session_state.get("bankroll"):
        try:
            from db import get_supabase_admin
            supabase = get_supabase_admin()
            result = supabase.table("poker_profiles").select(
                "current_bankroll, user_mode, default_stakes"
            ).eq("user_id", user_id).execute()
            if result.data and len(result.data) > 0:
                row = result.data[0]
                saved_br = float(row.get("current_bankroll", 0) or 0)
                if saved_br > 0:
                    st.session_state["bankroll"] = saved_br
                saved_mode = row.get("user_mode", "")
                if saved_mode in RISK_MODES:
                    st.session_state["risk_mode"] = saved_mode
                saved_stakes = row.get("default_stakes", "")
                if saved_stakes:
                    st.session_state["default_stakes"] = saved_stakes
        except Exception:
            pass

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
    render_bankroll_editor(bankroll, user_id, risk_mode, rec_stakes)

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    # ===== MOVE-UP PROJECTION =====
    render_move_up(bankroll, stats, rec_stakes, risk_mode)

    # ===== TABBED DEEP DIVES =====
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🎲 Risk Analysis",
        "🪜 Stakes Ladder",
        "⚙️ Risk Mode",
        "📉 Drawdowns",
        "💎 Rakeback",
    ])

    with tab1:
        render_risk_of_ruin(bankroll, rec_stakes, stats["bb_per_100"], stats)

    with tab2:
        render_stakes_ladder(bankroll, risk_mode, rec_stakes)

    with tab3:
        render_risk_mode_selector(risk_mode, bankroll, rec_stakes)

    with tab4:
        render_drawdown(sessions, bankroll)

    with tab5:
        render_rakeback(bankroll, rec_stakes, stats, risk_mode)


if __name__ == "__main__":
    main()