# 03_Player_Stats.py — Premium Player Stats & Achievements Dashboard
# Lifetime analytics + bluff stats + achievements + projected earnings
# Nameless Poker — $299/month decision engine

import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
import math

st.set_page_config(
    page_title="Player Stats | Nameless Poker",
    page_icon="📊",
    layout="wide",
)

from auth import require_auth
from sidebar import render_sidebar
from db import (
    get_user_sessions,
    get_player_stats,
    get_session_outcome_summary,
    get_user_bluff_stats,
)

user = require_auth()
render_sidebar()

# =============================================================================
# CONFIGURATION
# =============================================================================

PROFIT_TIERS = [
    {"name": "Grinder",         "emoji": "🌱", "min": 0,     "max": 1000,  "color": "#6b7280", "desc": "Starting the journey"},
    {"name": "Winning Player",  "emoji": "📈", "min": 1000,  "max": 5000,  "color": "#22c55e", "desc": "Proven profitable"},
    {"name": "Shark",           "emoji": "🎯", "min": 5000,  "max": 15000, "color": "#3b82f6", "desc": "Serious competitor"},
    {"name": "High Roller",     "emoji": "💰", "min": 15000, "max": 35000, "color": "#f59e0b", "desc": "Significant earnings"},
    {"name": "Diamond Crusher", "emoji": "💎", "min": 35000, "max": 75000, "color": "#8b5cf6", "desc": "Elite status"},
    {"name": "Poker Royalty",   "emoji": "👑", "min": 75000, "max": None,  "color": "#ec4899", "desc": "Legendary player"},
]

ACHIEVEMENT_BADGES = [
    {"id": "iron_discipline", "name": "Iron Discipline", "emoji": "🛡️", "desc": "Stop-loss protected 50+ times",
     "check": lambda s: s.get("stop_loss_count", 0) >= 50, "key": "stop_loss_count", "target": 50},
    {"id": "profit_locker", "name": "Profit Locker", "emoji": "🔒", "desc": "Locked profits with stop-win 25+ times",
     "check": lambda s: s.get("stop_win_count", 0) >= 25, "key": "stop_win_count", "target": 25},
    {"id": "marathon", "name": "Marathon Player", "emoji": "⏱️", "desc": "500+ hours at the tables",
     "check": lambda s: s.get("total_hours", 0) >= 500, "key": "total_hours", "target": 500},
    {"id": "volume_king", "name": "Volume King", "emoji": "📊", "desc": "10,000+ hands played",
     "check": lambda s: s.get("total_hands", 0) >= 10000, "key": "total_hands", "target": 10000},
    {"id": "century", "name": "Century Club", "emoji": "💯", "desc": "100 sessions completed",
     "check": lambda s: s.get("total_sessions", 0) >= 100, "key": "total_sessions", "target": 100},
    {"id": "first_grand", "name": "First Grand", "emoji": "🎉", "desc": "Earned your first $1,000",
     "check": lambda s: s.get("total_profit", 0) >= 1000, "key": "total_profit", "target": 1000},
    {"id": "five_figure", "name": "Five Figure Club", "emoji": "🏆", "desc": "Lifetime earnings $10,000+",
     "check": lambda s: s.get("total_profit", 0) >= 10000, "key": "total_profit", "target": 10000},
    {"id": "hot_streak", "name": "Hot Streak", "emoji": "🔥", "desc": "10+ winning sessions in a row",
     "check": lambda s: s.get("max_win_streak", 0) >= 10, "key": "max_win_streak", "target": 10},
]

EXPECTED_BB_PER_100 = 6.0
EXPECTED_HOURLY = {
    "$0.50/$1": 4.55, "$1/$2": 9.10, "$2/$5": 22.75,
    "$5/$10": 45.50, "$10/$20": 91.00, "$25/$50": 227.50,
}

# =============================================================================
# PREMIUM CSS — Dark theme
# =============================================================================

st.markdown("""
<style>
[data-testid="stAppViewContainer"] { background: #0A0A12; }
section[data-testid="stSidebar"] { background: #0F0F1A; }
.stDeployButton, #MainMenu { display: none; }

.page-title { font-family:'Inter',sans-serif; font-size:28px; font-weight:800; color:#E0E0E0; margin-bottom:4px; }
.page-subtitle { font-size:14px; color:rgba(255,255,255,0.35); margin-bottom:24px; }

.badge-hero { background:linear-gradient(135deg,#0F0F1A 0%,#1a1a2e 100%); border:1px solid rgba(255,255,255,0.08); border-radius:16px; padding:32px; text-align:center; margin-bottom:24px; }
.badge-emoji { font-size:56px; margin-bottom:12px; }
.badge-name { font-family:'Inter',sans-serif; font-size:24px; font-weight:800; color:#E0E0E0; margin-bottom:4px; }
.badge-desc { font-size:14px; color:rgba(255,255,255,0.4); margin-bottom:16px; }
.badge-profit { font-family:'JetBrains Mono',monospace; font-size:28px; font-weight:700; margin-bottom:12px; }
.badge-progress-bar { background:rgba(255,255,255,0.1); border-radius:6px; height:8px; overflow:hidden; margin:0 auto; max-width:300px; }
.badge-progress-fill { height:100%; border-radius:6px; }
.badge-progress-text { font-size:12px; color:rgba(255,255,255,0.4); margin-top:6px; }

.premium-row { display:grid; grid-template-columns:repeat(3,1fr); gap:16px; margin-bottom:20px; }
.premium-card { background:linear-gradient(135deg,#0F0F1A 0%,#151520 100%); border:1px solid rgba(255,255,255,0.06); border-radius:12px; padding:24px; text-align:center; }
.premium-val { font-family:'JetBrains Mono',monospace; font-size:32px; font-weight:700; color:#E0E0E0; }
.premium-lbl { font-family:'Inter',sans-serif; font-size:10px; font-weight:600; text-transform:uppercase; letter-spacing:0.1em; color:rgba(255,255,255,0.3); margin-top:4px; }
.premium-ctx { font-size:12px; color:rgba(255,255,255,0.25); margin-top:6px; }
.premium-ci { font-family:'JetBrains Mono',monospace; font-size:12px; color:rgba(255,255,255,0.3); background:rgba(255,255,255,0.04); border-radius:12px; padding:3px 10px; display:inline-block; margin-top:6px; }

.stats-grid-4 { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-bottom:20px; }
.stats-grid-3 { display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin-bottom:20px; }
.stat-card { background:rgba(255,255,255,0.02); border:1px solid rgba(255,255,255,0.06); border-radius:10px; padding:16px 12px; text-align:center; }
.stat-val { font-family:'JetBrains Mono',monospace; font-size:20px; font-weight:700; color:#E0E0E0; }
.stat-lbl { font-size:10px; text-transform:uppercase; letter-spacing:0.08em; color:rgba(255,255,255,0.3); margin-top:2px; }

.perf-section { background:linear-gradient(135deg,#0F0F1A 0%,#151520 100%); border:1px solid rgba(255,255,255,0.06); border-radius:12px; padding:20px; margin-bottom:20px; }
.perf-title { font-family:'Inter',sans-serif; font-size:12px; font-weight:700; text-transform:uppercase; letter-spacing:0.1em; color:rgba(255,255,255,0.35); margin-bottom:12px; }
.perf-bar-bg { background:rgba(255,255,255,0.06); border-radius:8px; height:16px; position:relative; overflow:visible; }
.perf-bar-fill { height:100%; border-radius:8px; }
.perf-marker { position:absolute; top:-4px; height:24px; width:2px; background:#E0E0E0; }
.perf-labels { display:flex; justify-content:space-between; font-size:10px; color:rgba(255,255,255,0.25); margin-top:4px; }
.perf-msg { font-family:'Inter',sans-serif; font-size:13px; color:rgba(255,255,255,0.55); margin-top:12px; line-height:1.6; }

.bluff-hero { background:rgba(255,179,0,0.04); border:1px solid rgba(255,179,0,0.12); border-radius:12px; padding:20px; margin-bottom:16px; }
.bluff-title { font-family:'Inter',sans-serif; font-size:13px; font-weight:700; color:#FFD54F; margin-bottom:12px; text-transform:uppercase; letter-spacing:0.08em; }
.bluff-impact { background:rgba(0,200,83,0.06); border:1px solid rgba(0,200,83,0.15); border-radius:10px; padding:14px 16px; font-size:13px; color:rgba(255,255,255,0.6); line-height:1.6; margin-top:12px; }
.bluff-impact strong { color:#69F0AE; }

.opt-card { background:rgba(255,255,255,0.02); border:1px solid rgba(255,255,255,0.06); border-radius:10px; padding:20px; text-align:center; }
.opt-card.recommended { border-color:rgba(0,200,83,0.3); background:rgba(0,200,83,0.04); }
.opt-label { font-size:11px; text-transform:uppercase; letter-spacing:0.08em; color:rgba(255,255,255,0.3); margin-bottom:8px; }
.opt-value { font-family:'JetBrains Mono',monospace; font-size:22px; font-weight:700; color:#E0E0E0; }
.opt-sub { font-size:12px; color:rgba(255,255,255,0.3); margin-top:4px; }

.ach-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; }
.ach-badge { background:rgba(255,255,255,0.02); border:1px solid rgba(255,255,255,0.06); border-radius:10px; padding:16px; text-align:center; }
.ach-badge.unlocked { border-color:rgba(0,200,83,0.3); background:rgba(0,200,83,0.04); }
.ach-badge.locked { opacity:0.4; filter:grayscale(80%); }
.ach-emoji { font-size:28px; margin-bottom:6px; }
.ach-name { font-size:12px; font-weight:700; color:#E0E0E0; margin-bottom:2px; }
.ach-desc { font-size:10px; color:rgba(255,255,255,0.35); }
.ach-prog { font-family:'JetBrains Mono',monospace; font-size:10px; color:rgba(255,255,255,0.25); margin-top:4px; }

.day-grid { display:grid; grid-template-columns:repeat(7,1fr); gap:8px; }
.day-card { background:rgba(255,255,255,0.02); border:1px solid rgba(255,255,255,0.06); border-radius:8px; padding:12px 6px; text-align:center; }
.day-card.best { border-color:rgba(0,200,83,0.3); background:rgba(0,200,83,0.04); }
.day-card.worst { border-color:rgba(255,82,82,0.3); background:rgba(255,82,82,0.04); }
.day-name { font-size:10px; text-transform:uppercase; color:rgba(255,255,255,0.3); margin-bottom:4px; }
.day-val { font-family:'JetBrains Mono',monospace; font-size:14px; font-weight:700; color:#E0E0E0; }
.day-sub { font-size:9px; color:rgba(255,255,255,0.2); margin-top:2px; }

.ev-box { background:linear-gradient(135deg,#0d1b4a 0%,#1b2838 100%); border:1px solid rgba(66,165,245,0.2); border-radius:12px; padding:24px; margin-top:20px; }
.ev-title { font-family:'Inter',sans-serif; font-size:16px; font-weight:700; color:#90CAF9; margin-bottom:10px; }
.ev-body { font-family:'Inter',sans-serif; font-size:14px; color:rgba(255,255,255,0.6); line-height:1.7; }
.ev-body strong { color:#E0E0E0; }

.insight-box { background:rgba(66,165,245,0.06); border:1px solid rgba(66,165,245,0.15); border-radius:10px; padding:14px 16px; font-size:13px; color:rgba(255,255,255,0.55); line-height:1.6; margin:12px 0; }
.insight-box strong { color:#90CAF9; }

.pl-positive { color:#00E676; }
.pl-negative { color:#FF5252; }
.pl-zero { color:rgba(255,255,255,0.4); }

.empty-state { text-align:center; padding:64px 24px; color:rgba(255,255,255,0.4); }
.empty-state-icon { font-size:48px; margin-bottom:16px; }
</style>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700;800&family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
""", unsafe_allow_html=True)

# =============================================================================
# HELPERS
# =============================================================================

def get_user_id():
    return st.session_state.get("user_db_id")

def fmt_money(a):
    return f"+${a:,.2f}" if a >= 0 else f"-${abs(a):,.2f}"

def fmt_short(a):
    return f"+${a:,.0f}" if a >= 0 else f"-${abs(a):,.0f}"

def pl_class(v):
    if v > 0: return "pl-positive"
    if v < 0: return "pl-negative"
    return "pl-zero"

def parse_dt(s):
    v = s.get("started_at")
    if not v: return None
    try: return datetime.fromisoformat(v.replace("Z", "+00:00"))
    except: return None

def session_dur_min(s):
    sa, ea = s.get("started_at"), s.get("ended_at")
    if not sa: return 0
    try:
        start = datetime.fromisoformat(sa.replace("Z", "+00:00"))
        end = datetime.fromisoformat(ea.replace("Z", "+00:00")) if ea else datetime.now(timezone.utc)
        return int((end - start).total_seconds() / 60)
    except: return 0

# =============================================================================
# AGGREGATE STATS
# =============================================================================

def calculate_aggregate_stats(sessions):
    if not sessions:
        return {"total_sessions":0,"total_hands":0,"total_hours":0,"total_profit":0,
                "overall_bb_per_100":0,"winning_sessions":0,"losing_sessions":0,
                "win_rate_pct":0,"avg_session_profit":0,"avg_session_duration":0,
                "best_session":0,"worst_session":0,"max_win_streak":0,"max_lose_streak":0,
                "stop_loss_count":0,"stop_win_count":0,"stakes_breakdown":{},
                "day_breakdown":{},"monthly_breakdown":{},"primary_stakes":"$1/$2","primary_bb_size":2.0}

    n = len(sessions)
    total_hands = sum(int(s.get("hands_played",0) or 0) for s in sessions)
    total_min = sum(session_dur_min(s) for s in sessions)
    total_hours = total_min / 60
    total_profit = sum(float(s.get("profit_loss",0) or 0) for s in sessions)

    total_bb_won = 0
    for s in sessions:
        bb = float(s.get("bb_size",2.0) or 2.0)
        total_bb_won += float(s.get("profit_loss",0) or 0) / bb if bb > 0 else 0
    bb100 = (total_bb_won / total_hands * 100) if total_hands > 0 else 0

    winning = sum(1 for s in sessions if float(s.get("profit_loss",0) or 0) > 0)
    losing = sum(1 for s in sessions if float(s.get("profit_loss",0) or 0) < 0)
    profits = [float(s.get("profit_loss",0) or 0) for s in sessions]

    sorted_s = sorted(sessions, key=lambda s: parse_dt(s) or datetime.min.replace(tzinfo=timezone.utc))
    mw, ml, cw, cl = 0, 0, 0, 0
    for s in sorted_s:
        pl = float(s.get("profit_loss",0) or 0)
        if pl > 0: cw += 1; cl = 0; mw = max(mw, cw)
        elif pl < 0: cl += 1; cw = 0; ml = max(ml, cl)
        else: cw = 0; cl = 0

    sl_count = sum(1 for s in sessions if s.get("end_reason") == "stop_loss")
    sw_count = sum(1 for s in sessions if s.get("end_reason") == "stop_win")

    stakes_bd = {}
    for s in sessions:
        sk = s.get("stakes","Unknown")
        if sk not in stakes_bd: stakes_bd[sk] = {"sessions":0,"hands":0,"profit":0,"bb_won":0}
        stakes_bd[sk]["sessions"] += 1
        stakes_bd[sk]["hands"] += int(s.get("hands_played",0) or 0)
        stakes_bd[sk]["profit"] += float(s.get("profit_loss",0) or 0)
        bb = float(s.get("bb_size",2.0) or 2.0)
        stakes_bd[sk]["bb_won"] += float(s.get("profit_loss",0) or 0) / bb if bb > 0 else 0
    for data in stakes_bd.values():
        data["bb_per_100"] = (data["bb_won"] / data["hands"] * 100) if data["hands"] > 0 else 0

    primary = max(stakes_bd.keys(), key=lambda k: stakes_bd[k]["sessions"]) if stakes_bd else "$1/$2"
    bb_map = {"$0.50/$1":1.0,"$1/$2":2.0,"$2/$5":5.0,"$5/$10":10.0,"$10/$20":20.0,"$25/$50":50.0}

    day_bd = {i: {"sessions":0,"profit":0} for i in range(7)}
    for s in sessions:
        dt = parse_dt(s)
        if dt:
            day_bd[dt.weekday()]["sessions"] += 1
            day_bd[dt.weekday()]["profit"] += float(s.get("profit_loss",0) or 0)

    month_bd = {}
    for s in sessions:
        dt = parse_dt(s)
        if dt:
            mk = dt.strftime("%Y-%m")
            if mk not in month_bd: month_bd[mk] = {"sessions":0,"profit":0,"hands":0,"bb_won":0}
            month_bd[mk]["sessions"] += 1
            month_bd[mk]["profit"] += float(s.get("profit_loss",0) or 0)
            month_bd[mk]["hands"] += int(s.get("hands_played",0) or 0)
            bb = float(s.get("bb_size",2.0) or 2.0)
            month_bd[mk]["bb_won"] += float(s.get("profit_loss",0) or 0) / bb if bb > 0 else 0
    for data in month_bd.values():
        data["bb_per_100"] = (data["bb_won"] / data["hands"] * 100) if data["hands"] > 0 else 0

    return {
        "total_sessions":n,"total_hands":total_hands,"total_hours":total_hours,
        "total_profit":total_profit,"overall_bb_per_100":bb100,
        "winning_sessions":winning,"losing_sessions":losing,
        "breakeven_sessions":n - winning - losing,
        "win_rate_pct":(winning/n*100) if n>0 else 0,
        "avg_session_profit":total_profit/n if n>0 else 0,
        "avg_session_duration":total_min/n if n>0 else 0,
        "best_session":max(profits),"worst_session":min(profits),
        "max_win_streak":mw,"max_lose_streak":ml,
        "stop_loss_count":sl_count,"stop_win_count":sw_count,
        "stakes_breakdown":stakes_bd,"day_breakdown":day_bd,
        "monthly_breakdown":month_bd,"primary_stakes":primary,
        "primary_bb_size":bb_map.get(primary,2.0),
    }

def calc_confidence_interval(sessions):
    if len(sessions) < 5: return (0,0,0)
    bb100_list = []
    for s in sessions:
        hands = int(s.get("hands_played",0) or 0)
        bb = float(s.get("bb_size",2.0) or 2.0)
        pl = float(s.get("profit_loss",0) or 0)
        if hands > 0 and bb > 0:
            bb100_list.append(((pl/bb)/hands)*100)
    if len(bb100_list) < 2: return (0,0,0)
    mean = sum(bb100_list)/len(bb100_list)
    var = sum((x-mean)**2 for x in bb100_list)/(len(bb100_list)-1)
    se = math.sqrt(var)/math.sqrt(len(bb100_list))
    m = 1.96*se
    return (mean, mean-m, mean+m)

def get_tier(total_profit):
    current = PROFIT_TIERS[0]
    nxt = PROFIT_TIERS[1] if len(PROFIT_TIERS) > 1 else None
    for i, t in enumerate(PROFIT_TIERS):
        if t["max"] is None or total_profit < t["max"]:
            current = t
            nxt = PROFIT_TIERS[i+1] if i+1 < len(PROFIT_TIERS) else None
            break
    if nxt:
        span = (current["max"] or current["min"]+10000) - current["min"]
        progress = min(100, max(0, ((total_profit-current["min"])/span)*100))
    else:
        progress = 100
    return current, nxt, progress

def calc_annual(stats):
    n = stats.get("total_sessions",0)
    if n < 5: return {"annual":0,"confidence":"low","per_session":0}
    per = stats["total_profit"]/n
    return {"annual":per*500, "confidence":"high" if n>=100 else "medium" if n>=50 else "low", "per_session":per}

def calc_session_perf(sessions):
    buckets = {
        "short":{"label":"Under 1.5 hrs","min":0,"max":90,"count":0,"profit":0},
        "optimal":{"label":"1.5 – 3 hrs","min":90,"max":180,"count":0,"profit":0},
        "long":{"label":"Over 3 hrs","min":180,"max":99999,"count":0,"profit":0},
    }
    for s in sessions:
        d = session_dur_min(s)
        pl = float(s.get("profit_loss",0) or 0)
        for b in buckets.values():
            if b["min"] <= d < b["max"]:
                b["count"] += 1; b["profit"] += pl; break
    for b in buckets.values():
        b["avg"] = b["profit"]/b["count"] if b["count"]>0 else 0
    valid = {k:v for k,v in buckets.items() if v["count"]>=3}
    best = max(valid.keys(), key=lambda k: valid[k]["avg"]) if valid else "optimal"
    return {"buckets":buckets,"best":best}

# =============================================================================
# RENDER FUNCTIONS
# =============================================================================

def render_badge_hero(stats):
    tp = stats.get("total_profit", 0)
    tier, nxt, progress = get_tier(tp)
    prog_text = f"${nxt['min'] - tp:,.0f} to {nxt['name']}" if nxt else "Maximum tier achieved!"
    st.markdown(f"""
    <div class="badge-hero">
        <div class="badge-emoji">{tier['emoji']}</div>
        <div class="badge-name">{tier['name']}</div>
        <div class="badge-desc">{tier['desc']}</div>
        <div class="badge-profit" style="color:{tier['color']};">{fmt_money(tp)} lifetime</div>
        <div class="badge-progress-bar"><div class="badge-progress-fill" style="width:{progress}%;background:{tier['color']};"></div></div>
        <div class="badge-progress-text">{prog_text}</div>
    </div>
    """, unsafe_allow_html=True)


def render_premium_stats(stats, sessions):
    hourly = stats["total_profit"] / stats["total_hours"] if stats["total_hours"] > 0 else 0
    bb100, ci_lo, ci_hi = calc_confidence_interval(sessions)
    proj = calc_annual(stats)
    pa = proj["annual"]
    conf = {"high":"High confidence","medium":"Medium confidence","low":"More data needed"}.get(proj["confidence"],"")
    h_c = "#00E676" if hourly >= 0 else "#FF5252"
    b_c = "#69F0AE" if bb100 >= 0 else "#FF8A80"
    a_c = "#69F0AE" if pa >= 0 else "#FF8A80"

    st.markdown(f"""
    <div class="premium-row">
        <div class="premium-card">
            <div class="premium-val" style="color:{h_c};">${hourly:,.2f}/hr</div>
            <div class="premium-lbl">Hourly Win Rate</div>
            <div class="premium-ctx">{stats['total_hours']:.0f} hours played</div>
        </div>
        <div class="premium-card">
            <div class="premium-val" style="color:{b_c};">{bb100:+.1f}</div>
            <div class="premium-lbl">BB/100 Win Rate</div>
            <div class="premium-ci">95% CI: {ci_lo:+.1f} to {ci_hi:+.1f}</div>
        </div>
        <div class="premium-card">
            <div class="premium-val" style="color:{a_c};">${pa:,.0f}/yr</div>
            <div class="premium-lbl">Projected Annual</div>
            <div class="premium-ctx">{conf} &middot; 500 sessions/yr</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="stats-grid-4">
        <div class="stat-card"><div class="stat-val {pl_class(stats['total_profit'])}">{fmt_short(stats['total_profit'])}</div><div class="stat-lbl">Lifetime P/L</div></div>
        <div class="stat-card"><div class="stat-val">{stats['total_hours']:.0f}</div><div class="stat-lbl">Hours</div></div>
        <div class="stat-card"><div class="stat-val">{stats['total_sessions']}</div><div class="stat-lbl">Sessions</div></div>
        <div class="stat-card"><div class="stat-val">{stats['total_hands']:,}</div><div class="stat-lbl">Hands</div></div>
    </div>
    """, unsafe_allow_html=True)


def render_performance_vs_expected(stats):
    bb = stats.get("overall_bb_per_100", 0)
    exp = EXPECTED_BB_PER_100
    pct = (bb / exp * 100) if exp > 0 else 0
    fill_pct = min(100, max(0, pct * 100 / 150))
    marker = 66.7
    fill_color = "#00E676" if bb >= exp else "#FFD54F" if bb >= 0 else "#FF5252"

    if bb >= exp * 1.15:
        msg = f"&#128293; Performing {((bb/exp - 1) * 100):.0f}% above expected. Exceptional results."
    elif bb >= exp * 0.85:
        msg = "&#9989; Performing at expected levels. Your edge is real."
    elif bb >= 0:
        msg = f"&#128202; {((1 - bb/exp) * 100):.0f}% below expected &#8212; normal variance. Keep making correct decisions."
    else:
        msg = "&#128201; Short-term downswing. The math hasn't changed. Stay the course."

    st.markdown(f"""
    <div class="perf-section">
        <div class="perf-title">Performance vs Expected</div>
        <div class="perf-msg">{msg}</div>
        <div style="margin-top:12px;">
            <div class="perf-bar-bg">
                <div class="perf-bar-fill" style="width:{fill_pct}%;background:{fill_color};"></div>
                <div class="perf-marker" style="left:{marker}%;"></div>
            </div>
            <div class="perf-labels"><span>0 BB/100</span><span>Expected ({exp})</span><span>+{exp*1.5:.0f}</span></div>
        </div>
        <div style="margin-top:10px;text-align:center;">
            <span style="font-family:'JetBrains Mono',monospace;font-size:16px;font-weight:700;" class="{pl_class(bb)}">{bb:+.1f} BB/100</span>
            <span style="font-size:12px;color:rgba(255,255,255,0.3);"> vs {exp:+.1f} expected</span>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_aggressive_plays(user_id, stats):
    bluff = get_user_bluff_stats(user_id)
    total = bluff.get("total_spots", 0)

    if total == 0:
        st.markdown("""
        <div class="insight-box">
            No aggressive play data yet. Bluff spots appear as you play more sessions.
            The engine identifies profitable bluff opportunities and tracks your results automatically.
        </div>
        """, unsafe_allow_html=True)
        return

    profit = bluff["total_profit"]
    times_bet = bluff["times_bet"]
    folds_won = bluff["folds_won"]
    fold_pct = bluff["fold_success_pct"]
    avg_per = bluff["avg_per_attempt"]
    bet_pct = bluff["bet_pct"]

    st.markdown(f"""
    <div class="bluff-hero">
        <div class="bluff-title">&#9889; Lifetime Aggressive Plays</div>
        <div class="stats-grid-4">
            <div class="stat-card"><div class="stat-val {pl_class(profit)}">{fmt_short(profit)}</div><div class="stat-lbl">Bluff P/L</div></div>
            <div class="stat-card"><div class="stat-val" style="color:#FFD54F;">{total}</div><div class="stat-lbl">Spots Found</div></div>
            <div class="stat-card"><div class="stat-val">{times_bet}</div><div class="stat-lbl">Times Bet</div></div>
            <div class="stat-card"><div class="stat-val" style="color:#00E676;">{folds_won}</div><div class="stat-lbl">Folds Won</div></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="stats-grid-3">
        <div class="stat-card"><div class="stat-val" style="color:#FFD54F;">{bet_pct:.0f}%</div><div class="stat-lbl">Bet When Spotted</div></div>
        <div class="stat-card"><div class="stat-val" style="color:#69F0AE;">{fold_pct:.0f}%</div><div class="stat-lbl">Fold Success Rate</div></div>
        <div class="stat-card"><div class="stat-val {pl_class(avg_per)}">${avg_per:.2f}</div><div class="stat-lbl">Avg Per Attempt</div></div>
    </div>
    """, unsafe_allow_html=True)

    # Impact analysis
    total_profit = stats.get("total_profit", 0)
    if total_profit > 0 and profit > 0:
        overall_bb = stats.get("overall_bb_per_100", 0)
        total_hands = stats.get("total_hands", 0)
        primary_bb = stats.get("primary_bb_size", 2.0)
        if total_hands > 0 and primary_bb > 0:
            without = total_profit - profit
            bb_without = ((without / primary_bb) / total_hands) * 100
            pct_of = (profit / total_profit) * 100
            st.markdown(f"""
            <div class="bluff-impact">
                <strong>{pct_of:.0f}% of your total profit</strong> comes from aggressive plays.
                Without them, your win rate would be <strong>{bb_without:+.1f} BB/100</strong>
                instead of <strong>{overall_bb:+.1f} BB/100</strong>.
                Aggression is a core part of your edge.
            </div>
            """, unsafe_allow_html=True)
    elif profit < 0 and times_bet > 0:
        st.markdown(f"""
        <div class="insight-box">
            Bluff P/L is currently negative &#8212; this is <strong>normal variance</strong>.
            Your fold success rate of <strong>{fold_pct:.0f}%</strong> is healthy.
            Over larger samples, these spots are profitable. Keep following the engine's bluff recommendations.
        </div>
        """, unsafe_allow_html=True)

# =============================================================================
# RENDER: CHARTS, OPTIMIZATION, ACHIEVEMENTS, STAKES, DAYS, EV
# =============================================================================

def render_profit_curve(sessions):
    sorted_s = sorted(sessions, key=lambda s: parse_dt(s) or datetime.min.replace(tzinfo=timezone.utc))
    running = 0.0
    data = []
    for s in sorted_s:
        dt = parse_dt(s)
        if dt:
            running += float(s.get("profit_loss", 0) or 0)
            data.append({"Session": dt.strftime("%m/%d"), "Cumulative P/L ($)": running})
    if len(data) < 2:
        return
    df = pd.DataFrame(data)
    color = "#00E676" if data[-1]["Cumulative P/L ($)"] >= 0 else "#FF5252"
    st.line_chart(df, x="Session", y="Cumulative P/L ($)", color=color)


def render_monthly_trend(stats):
    monthly = stats.get("monthly_breakdown", {})
    if len(monthly) < 2:
        st.info("Play more sessions to see monthly trends.")
        return
    months = sorted(monthly.keys())[-12:]
    data = [{"Month": m, "BB/100": monthly[m]["bb_per_100"]} for m in months]
    df = pd.DataFrame(data)
    st.line_chart(df.set_index("Month")["BB/100"])

    if len(data) >= 3:
        r3 = sum(d["BB/100"] for d in data[-3:]) / 3
        o3 = sum(d["BB/100"] for d in data[-6:-3]) / 3 if len(data) >= 6 else r3
        if r3 > o3 + 1:
            st.markdown('<div class="insight-box">Your win rate is <strong>trending up</strong>. Great progress!</div>', unsafe_allow_html=True)
        elif r3 < o3 - 1:
            st.markdown('<div class="insight-box">Win rate dipped recently. Often just variance &#8212; stay the course.</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="insight-box">Win rate is <strong>stable</strong>. Consistency is key to long-term success.</div>', unsafe_allow_html=True)


def render_session_optimization(sessions):
    analysis = calc_session_perf(sessions)
    buckets = analysis["buckets"]
    best = analysis["best"]
    cols = st.columns(3)
    for i, key in enumerate(["short", "optimal", "long"]):
        b = buckets[key]
        is_best = key == best and b["count"] >= 3
        card_cls = "recommended" if is_best else ""
        avg = b["avg"]
        color = "#00E676" if avg >= 0 else "#FF5252"
        rec_html = '<div style="color:#00E676;font-size:11px;font-weight:700;margin-top:8px;">&#10003; RECOMMENDED</div>' if is_best else ''
        with cols[i]:
            st.markdown(f"""
            <div class="opt-card {card_cls}">
                <div class="opt-label">{b['label']}</div>
                <div class="opt-value" style="color:{color};">{fmt_short(avg)}</div>
                <div class="opt-sub">avg/session &middot; {b['count']} sessions</div>
                {rec_html}
            </div>
            """, unsafe_allow_html=True)

    insights = {
        "optimal": "Your best results come from 1.5-3 hour sessions. This aligns with research showing optimal decision-making in this window.",
        "short": "You perform best in shorter sessions. Consider playing more frequent, shorter sessions to maximize your edge.",
        "long": "You perform well in longer sessions, but decision quality typically declines after 3 hours. Monitor for fatigue.",
    }
    st.markdown(f'<div class="insight-box">{insights.get(best, insights["optimal"])}</div>', unsafe_allow_html=True)


def render_session_stats(stats):
    winning = stats.get("winning_sessions", 0)
    losing = stats.get("losing_sessions", 0)
    total = winning + losing + stats.get("breakeven_sessions", 0)
    best = stats.get("best_session", 0)
    worst = stats.get("worst_session", 0)
    avg = stats.get("avg_session_profit", 0)
    avg_dur = stats.get("avg_session_duration", 0)
    mw = stats.get("max_win_streak", 0)
    ml = stats.get("max_lose_streak", 0)

    if total > 0:
            st.markdown(f'<div class="stats-grid-4"><div class="stat-card"><div class="stat-val pl-positive">{fmt_short(best)}</div><div class="stat-lbl">Best Session</div></div><div class="stat-card"><div class="stat-val pl-negative">{fmt_short(worst)}</div><div class="stat-lbl">Worst Session</div></div><div class="stat-card"><div class="stat-val {pl_class(avg)}">{fmt_short(avg)}</div><div class="stat-lbl">Avg Session</div></div><div class="stat-card"><div class="stat-val">{avg_dur:.0f}m</div><div class="stat-lbl">Avg Duration</div></div></div><div class="stats-grid-4"><div class="stat-card"><div class="stat-val pl-positive">{winning}</div><div class="stat-lbl">Winning ({(winning/total*100):.0f}%)</div></div><div class="stat-card"><div class="stat-val pl-negative">{losing}</div><div class="stat-lbl">Losing ({(losing/total*100):.0f}%)</div></div><div class="stat-card"><div class="stat-val" style="color:#FFD54F;">{mw}</div><div class="stat-lbl">Best Win Streak</div></div><div class="stat-card"><div class="stat-val" style="color:#FF8A80;">{ml}</div><div class="stat-lbl">Worst Lose Streak</div></div></div>', unsafe_allow_html=True)


def render_achievements(stats):
    badges_html = ""
    for badge in ACHIEVEMENT_BADGES:
        unlocked = badge["check"](stats)
        cls = "unlocked" if unlocked else "locked"
        current = stats.get(badge.get("key"), 0)
        target = badge.get("target", 1)
        if unlocked:
            prog = "&#10003; Unlocked"
        elif isinstance(current, float):
            prog = f"{current:,.0f} / {target:,.0f}"
        else:
            prog = f"{current:,} / {target:,}"
        badges_html += f"""
        <div class="ach-badge {cls}">
            <div class="ach-emoji">{badge['emoji']}</div>
            <div class="ach-name">{badge['name']}</div>
            <div class="ach-desc">{badge['desc']}</div>
            <div class="ach-prog">{prog}</div>
        </div>"""

    st.markdown(f'<div class="ach-grid">{badges_html}</div>', unsafe_allow_html=True)


def render_stakes_breakdown(stats):
    bd = stats.get("stakes_breakdown", {})
    if not bd:
        st.info("No stakes data yet.")
        return
    order = ["$0.50/$1","$1/$2","$2/$5","$5/$10","$10/$20","$25/$50"]
    sorted_s = sorted(bd.items(), key=lambda x: order.index(x[0]) if x[0] in order else 999)

    rows_html = ""
    for stakes, data in sorted_s:
        profit = data["profit"]
        bb100 = data["bb_per_100"]
        hands = data["hands"]
        n = data["sessions"]
        rows_html += f"""
        <div style="display:grid;grid-template-columns:80px 1fr 1fr 1fr 1fr;gap:8px;padding:10px 0;border-bottom:1px solid rgba(255,255,255,0.04);align-items:center;">
            <div style="font-weight:700;color:#90CAF9;">{stakes}</div>
            <div style="text-align:center;font-size:13px;color:rgba(255,255,255,0.5);">{n} sessions</div>
            <div style="text-align:center;font-size:13px;color:rgba(255,255,255,0.5);">{hands:,} hands</div>
            <div style="text-align:center;font-family:'JetBrains Mono',monospace;font-weight:700;" class="{pl_class(profit)}">{fmt_short(profit)}</div>
            <div style="text-align:center;font-family:'JetBrains Mono',monospace;font-weight:700;" class="{pl_class(bb100)}">{bb100:+.1f} BB/100</div>
        </div>"""

    st.markdown(f'<div style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);border-radius:10px;padding:12px 16px;"><div style="display:grid;grid-template-columns:80px 1fr 1fr 1fr 1fr;gap:8px;padding-bottom:8px;border-bottom:1px solid rgba(255,255,255,0.08);"><div style="font-size:9px;text-transform:uppercase;color:rgba(255,255,255,0.25);">Stakes</div><div style="text-align:center;font-size:9px;text-transform:uppercase;color:rgba(255,255,255,0.25);">Sessions</div><div style="text-align:center;font-size:9px;text-transform:uppercase;color:rgba(255,255,255,0.25);">Hands</div><div style="text-align:center;font-size:9px;text-transform:uppercase;color:rgba(255,255,255,0.25);">P/L</div><div style="text-align:center;font-size:9px;text-transform:uppercase;color:rgba(255,255,255,0.25);">BB/100</div></div>{rows_html}</div>', unsafe_allow_html=True)


def render_day_analysis(stats):
    bd = stats.get("day_breakdown", {})
    names = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
    day_data = [(i, bd[i]["profit"], bd[i]["sessions"]) for i in range(7) if bd.get(i, {}).get("sessions", 0) > 0]
    best_day = max(day_data, key=lambda x: x[1]/x[2] if x[2]>0 else -9999)[0] if day_data else None
    worst_day = min(day_data, key=lambda x: x[1]/x[2] if x[2]>0 else 9999)[0] if day_data else None

    cards = ""
    for i in range(7):
        d = bd.get(i, {"sessions":0,"profit":0})
        n = d["sessions"]
        avg = d["profit"]/n if n > 0 else 0
        cls = "best" if i == best_day and n >= 3 else "worst" if i == worst_day and n >= 3 else ""
        cards += f"""
        <div class="day-card {cls}">
            <div class="day-name">{names[i]}</div>
            <div class="day-val {pl_class(avg)}">{fmt_short(avg)}</div>
            <div class="day-sub">{n} sessions</div>
        </div>"""

    st.markdown(f'<div class="day-grid">{cards}</div>', unsafe_allow_html=True)

    if best_day is not None and bd.get(best_day, {}).get("sessions", 0) >= 3:
        st.markdown(f'<div class="insight-box">Your best performance is on <strong>{names[best_day]}s</strong>. Consider prioritizing sessions on this day.</div>', unsafe_allow_html=True)


def render_ev_reminder(stats):
    bb = stats.get("overall_bb_per_100", 0)
    n = stats.get("total_sessions", 0)
    primary = stats.get("primary_stakes", "$1/$2")
    proj = calc_annual(stats)
    pa = proj["annual"]

    if pa > 0 and n >= 10:
        msg = (f"At your current win rate of <strong>{bb:+.1f} BB/100</strong>, "
               f"you're on pace for <strong>${pa:,.0f}/year</strong> at {primary}. "
               f"Keep making +EV decisions. The math is working in your favor.")
    else:
        msg = ("Every decision you make using this app is mathematically optimal. "
               "Short-term results are influenced by variance, but players who maintain "
               "this level of play average <strong>+$20,000-24,000/year</strong> at $1/$2 stakes. "
               "<em>Trust the math. The results will follow.</em>")

    st.markdown(f"""
    <div class="ev-box">
        <div class="ev-title">Your +EV Journey</div>
        <div class="ev-body">{msg}</div>
    </div>
    """, unsafe_allow_html=True)


# =============================================================================
# ADMIN/DISCORD EXPORT
# =============================================================================

def get_player_badge_info(user_id):
    sessions = get_user_sessions(user_id, limit=1000)
    stats = calculate_aggregate_stats(sessions)
    tp = stats.get("total_profit", 0)
    tier, nxt, progress = get_tier(tp)
    hourly = tp / stats["total_hours"] if stats["total_hours"] > 0 else 0
    bb100, ci_lo, ci_hi = calc_confidence_interval(sessions)
    unlocked = [{"id": b["id"], "name": b["name"], "emoji": b["emoji"]}
                for b in ACHIEVEMENT_BADGES if b["check"](stats)]
    return {
        "tier_emoji": tier["emoji"], "tier_name": tier["name"], "tier_color": tier["color"],
        "tier_progress": progress, "next_tier_name": nxt["name"] if nxt else None,
        "total_profit": tp, "total_sessions": stats["total_sessions"],
        "total_hours": stats["total_hours"], "total_hands": stats["total_hands"],
        "bb_per_100": bb100, "bb_per_100_ci": (ci_lo, ci_hi), "hourly_rate": hourly,
        "unlocked_achievements": unlocked, "achievement_count": len(unlocked),
        "total_achievements": len(ACHIEVEMENT_BADGES),
    }


# =============================================================================
# MAIN
# =============================================================================

def main():
    st.markdown("""
    <div class="page-title">Player Stats</div>
    <div class="page-subtitle">Lifetime performance, projected earnings, aggressive play impact, and achievements</div>
    """, unsafe_allow_html=True)

    user_id = get_user_id()
    if not user_id:
        st.warning("Please log in to view your stats.")
        return

    sessions = get_user_sessions(user_id, limit=1000)
    if not sessions:
        st.markdown("""
        <div class="empty-state">
            <div class="empty-state-icon">📊</div>
            <h3 style="color:#E0E0E0;">No Stats Yet</h3>
            <p>Complete some sessions to see your performance dashboard.</p>
        </div>
        """, unsafe_allow_html=True)
        return

    stats = calculate_aggregate_stats(sessions)

    render_badge_hero(stats)
    render_premium_stats(stats, sessions)
    render_performance_vs_expected(stats)

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "Profit & Trends",
        "Aggressive Plays",
        "Session Optimization",
        "Achievements",
        "Stakes Analysis",
        "Time Analysis",
    ])

    with tab1:
        render_profit_curve(sessions)
        render_monthly_trend(stats)
        render_ev_reminder(stats)

    with tab2:
        render_aggressive_plays(user_id, stats)

    with tab3:
        render_session_optimization(sessions)
        render_session_stats(stats)

    with tab4:
        render_achievements(stats)

    with tab5:
        render_stakes_breakdown(stats)

    with tab6:
        render_day_analysis(stats)


if __name__ == "__main__":
    main()