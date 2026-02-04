# pages/07_Bankroll_Health.py — Bankroll Health & Bonuses
# Standalone bankroll planner; does NOT affect Tracker, Stats, or Settings.
# ENHANCED: Quick Health Check, auto-detect defensive mode, What If calculator, optional DB persistence

import streamlit as st
st.set_page_config(page_title="Bankroll Health & Bonuses", page_icon="💰", layout="wide")

from auth import require_auth
user = require_auth()

from sidebar import render_sidebar
render_sidebar()

from track_manager import TrackManager
from week_manager import WeekManager

# ---- DB helpers for optional persistence ----
try:
    from db import get_profile_by_auth_id
    from cache import get_cached_tracks
    from db import get_tracks_for_user
    
    # Optional: bankroll plan persistence (create these functions in db.py if you want persistence)
    try:
        from db import save_bankroll_plan, load_bankroll_plan
    except ImportError:
        save_bankroll_plan = None
        load_bankroll_plan = None
except Exception:
    get_cached_tracks = None
    get_tracks_for_user = None
    save_bankroll_plan = None
    load_bankroll_plan = None

# ---- Auth identity extraction ----
def _extract_auth_identity(u) -> tuple[str, str]:
    auth_id = None
    email = None
    if isinstance(u, dict):
        auth_id = u.get("id") or u.get("user_id") or u.get("sub") or u.get("uid")
        email = u.get("email") or u.get("primary_email")
    else:
        for key in ("id", "user_id", "sub", "uid"):
            if hasattr(u, key):
                auth_id = getattr(u, key)
                break
        for key in ("email", "primary_email"):
            if hasattr(u, key):
                email = getattr(u, key)
                break
    return str(auth_id or ""), str(email or "")

auth_id, _ = _extract_auth_identity(user)

# Get user_db_id from session state (set by other pages)
user_db_id = st.session_state.get("user_db_id", "")

# ---------- Styles ----------
st.markdown("""
<style>
.card{border:1px solid #2b2b2b;border-radius:14px;padding:16px 18px;
      background:linear-gradient(135deg,#0f0f0f,#171717);color:#eaeaea;margin:8px 0 18px 0;}
.card-green{border-color:#22c55e !important;}
.card-yellow{border-color:#f59e0b !important;}
.card-red{border-color:#ef4444 !important;}
.h{font-weight:900;font-size:1.05rem;margin-bottom:6px}
.sub{color:#9ca3af;font-size:.90rem;margin-top:4px;margin-bottom:10px}
.small{color:#a7a7a7;font-size:.92rem}
.kpi{display:flex;gap:12px;flex-wrap:wrap}
.kpill{border:1px solid #2b2b2b;background:#101010;color:#eaeaea;border-radius:12px;padding:10px 12px;min-width:160px}
.kpill .l{font-size:.78rem;color:#a5a5a5}
.kpill .v{font-weight:800;font-size:1.05rem}
.badge{display:inline-block;border:1px solid #3a3a3a;border-radius:999px;padding:2px 10px;
       font-size:.80rem;color:#cbd5e1;background:#101010;margin-left:6px}
.good{color:#22c55e}
.warn{color:#f59e0b}
.bad{color:#ef4444}
hr{border:none;border-top:1px solid #2b2b2b;margin:12px 0}

/* Progress bar styles */
.progress-container{background:#1a1a1a;border-radius:8px;height:12px;overflow:hidden;margin:8px 0}
.progress-bar{height:100%;border-radius:8px;transition:width 0.3s ease}
.progress-green{background:linear-gradient(90deg,#22c55e,#4ade80)}
.progress-yellow{background:linear-gradient(90deg,#f59e0b,#fbbf24)}
.progress-red{background:linear-gradient(90deg,#ef4444,#f87171)}

/* Health summary styles */
.health-title{font-weight:900;font-size:1.25rem;margin-bottom:10px}
.health-hero{font-size:1.0rem;line-height:1.5;margin:8px 0}
</style>
""", unsafe_allow_html=True)

st.title("Bankroll Health & Bonuses")

# ---------- Session / Managers ----------
if "unit_value" not in st.session_state:
    st.session_state.unit_value = 1.0

if "tm" not in st.session_state:
    st.session_state.tm = TrackManager(unit_value=float(st.session_state.unit_value))

tm: TrackManager = st.session_state.tm

# ---------- Auto-detect actual track count ----------
def _get_actual_track_count() -> int:
    """Get the user's actual number of tracks from DB."""
    if not user_db_id or not get_cached_tracks or not get_tracks_for_user:
        return len(tm.all_ids()) or 1
    try:
        tracks = get_cached_tracks(user_db_id, get_tracks_for_user) or []
        return max(1, min(3, len(tracks)))  # Clamp to 1-3
    except Exception:
        return len(tm.all_ids()) or 1

# ---------- Auto-detect defensive mode ----------
def _any_track_defensive() -> bool:
    """Check if any track is currently in defensive mode."""
    for tid in tm.all_ids():
        try:
            bundle = tm.ensure(tid)
            wk: WeekManager = bundle.week
            # Check multiple possible locations for defensive flag
            if getattr(wk, "defensive_mode", False):
                return True
            if hasattr(wk, "state") and getattr(wk.state, "defensive_mode", False):
                return True
        except Exception:
            pass
    return False

# ---------- Defaults with smart initialization ----------
ss = st.session_state

# Auto-detect track count on first load
actual_tracks = _get_actual_track_count()

ss.setdefault("unit_value", 1.0)
ss.setdefault("__bh_bonus_weekly", 0.0)
ss.setdefault("__bh_bonus_monthly", 0.0)
ss.setdefault("__bh_rakeback", 0.0)
ss.setdefault("__bh_split_pct_active", 50)

unit_value = float(ss.get("unit_value", 1.0))

# ---------- Load saved plan from DB (if available) ----------
# Try to load if values aren't set yet (0.0 means not loaded)
if load_bankroll_plan and (user_db_id or auth_id):
    if ss.get("__bh_active_usd", 0.0) == 0.0 and ss.get("__bh_reserve_usd", 0.0) == 0.0:
        try:
            saved_plan = load_bankroll_plan(user_db_id or auth_id)
            if saved_plan:
                ss["__bh_active_usd"] = float(saved_plan.get("active_usd", 0.0))
                ss["__bh_reserve_usd"] = float(saved_plan.get("reserve_usd", 0.0))
                ss["__bh_track_count"] = int(saved_plan.get("track_count", actual_tracks))
        except Exception as e:
            print(f"[bankroll_health] load_bankroll_plan error: {e!r}")

# Set defaults for anything not loaded
ss.setdefault("__bh_active_usd", 0.0)
ss.setdefault("__bh_reserve_usd", 0.0)
ss.setdefault("__bh_track_count", actual_tracks)

# ---------- Helper calcs ----------
def _targets_for_tracks(n_tracks: int):
    """Returns (active_units, reserve_units, total_units) for given track count."""
    if n_tracks == 1: return 1000, 1000, 2000
    if n_tracks == 2: return 1200, 1600, 2800
    if n_tracks == 3: return 1200, 2200, 3400
    # For 4+ tracks, scale linearly: +400 reserve per additional track
    base_active = 1200
    base_reserve = 2200 + (n_tracks - 3) * 400
    return base_active, base_reserve, base_active + base_reserve

def _status_color(ratio_active: float):
    if 0.40 <= ratio_active <= 0.60: return "good", "🟢 Healthy"
    if (0.30 <= ratio_active < 0.40) or (0.60 < ratio_active <= 0.70): return "warn", "🟡 Moderate"
    return "bad", "🔴 Overexposed"

def _fmt_money(x): return f"${float(x):,.0f}"
def _fmt_units(u): return f"{int(round(u)):,}u"

def _bool_badge(ok: bool, yes="✅ Yes", no="❌ No") -> str:
    return yes if ok else no

def _progress_bar(current: float, target: float, color_cls: str = "progress-green") -> str:
    pct = min(100, max(0, (current / target * 100) if target > 0 else 0))
    return f"""
    <div class='progress-container'>
        <div class='progress-bar {color_cls}' style='width:{pct:.1f}%'></div>
    </div>
    <div class='small' style='margin-top:2px'>{_fmt_money(current)} / {_fmt_money(target)} ({pct:.0f}%)</div>
    """

# ---------- Pre-calculate health metrics for Quick Check ----------
active_usd = float(ss["__bh_active_usd"])
reserve_usd = float(ss["__bh_reserve_usd"])
total_usd = active_usd + reserve_usd
ratio_active = (active_usd / total_usd) if total_usd > 0 else 0.0
cls, label = _status_color(ratio_active)

t_active_u, t_reserve_u, t_total_u = _targets_for_tracks(ss["__bh_track_count"])
total_units_now = (total_usd / unit_value) if unit_value > 0 else 0.0

# Readiness checks
funded_for_selected = total_units_now >= float(t_total_u)
split_healthy = 0.40 <= ratio_active <= 0.60
no_defensive_mode = not _any_track_defensive()  # ✅ Auto-detected!

readiness_score = int(funded_for_selected) + int(split_healthy) + int(no_defensive_mode)

# ==================== QUICK HEALTH CHECK (NEW - TOP OF PAGE) ====================
def _get_health_summary():
    """Generate a single-glance health assessment."""
    issues = []
    
    if not funded_for_selected:
        shortfall = (t_total_u * unit_value) - total_usd
        issues.append(f"underfunded by {_fmt_money(shortfall)}")
    
    if not split_healthy:
        if ratio_active < 0.40:
            issues.append("Active balance too low (< 40%)")
        elif ratio_active > 0.60:
            issues.append("Active balance too high (> 60%)")
    
    if not no_defensive_mode:
        issues.append("one or more tracks in Defensive Mode")
    
    if readiness_score == 3 and total_usd > 0:
        return "good", "🟢 <b>You're in good shape.</b> Bankroll is funded, split is healthy, and no tracks are in defensive mode. You're ready to play or scale."
    elif readiness_score >= 2 and total_usd > 0:
        issue_text = ", ".join(issues) if issues else "minor adjustments needed"
        return "warn", f"🟡 <b>Almost there.</b> {issue_text.capitalize()}. Address this before scaling up."
    elif total_usd == 0:
        return "warn", "🟡 <b>Enter your bankroll values below</b> to get a personalized health assessment."
    else:
        issue_text = ", ".join(issues) if issues else "multiple issues detected"
        return "bad", f"🔴 <b>Pause and rebalance.</b> Issues: {issue_text}. Fix these before continuing live play."

health_cls, health_summary = _get_health_summary()
card_border_cls = f"card-{'green' if health_cls == 'good' else 'yellow' if health_cls == 'warn' else 'red'}"

with st.container():
    st.markdown(f'<div class="card {card_border_cls}">', unsafe_allow_html=True)
    st.markdown('<div class="health-title">⚡ Quick Health Check</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="health-hero">{health_summary}</div>', unsafe_allow_html=True)
    
    # Combined stats row (merged from Overview)
    st.markdown(
        f"""<div class='kpi' style='margin-top:12px'>
            <div class='kpill'><div class='l'>Total Bankroll</div><div class='v'>{_fmt_money(total_usd)}</div></div>
            <div class='kpill'><div class='l'>Total Units</div><div class='v'>{_fmt_units(total_units_now)}</div></div>
            <div class='kpill'><div class='l'>Active : Reserve</div><div class='v {cls}'>{ratio_active*100:.0f}% : {100-ratio_active*100:.0f}%</div></div>
            <div class='kpill'><div class='l'>Tracks</div><div class='v'>{ss['__bh_track_count']}</div></div>
            <div class='kpill'><div class='l'>$/unit</div><div class='v'>${unit_value:,.2f}</div></div>
            <div class='kpill'><div class='l'>Defensive Mode</div><div class='v'>{"🔴 ON" if not no_defensive_mode else "🟢 OFF"}</div></div>
            <div class='kpill'><div class='l'>Funded?</div><div class='v'>{"✅ Yes" if funded_for_selected else "❌ No"}</div></div>
        </div>""",
        unsafe_allow_html=True
    )
    st.markdown("</div>", unsafe_allow_html=True)

# ----- Intro & Disclaimer -----
st.markdown(
    "<div class='sub'>This page is a <b>standalone bankroll planner</b>. "
    "It helps you calculate and visualize your total bankroll, active and reserve splits, and bonus allocations. "
    "Nothing you enter here affects your live play, bankroll, or stats — and nothing updates automatically from your Tracker. "
    "<br><br>It's designed purely for <b>planning and structure</b> — to help you make better decisions about "
    "when to rebalance, when to scale up, and how to use your bonuses without any risk to your real data.</div>",
    unsafe_allow_html=True
)

# ---------- Balances ----------
with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="h">📝 Balances & Tracks — Enter Your Info</div>', unsafe_allow_html=True)
    st.markdown(
        "<div class='sub' style='background:#1a1a2e;border:1px solid #334155;border-radius:8px;padding:12px;margin-bottom:12px'>"
        "👉 <b>This page needs your input to work.</b> Enter your current bankroll (Active + Reserve) "
        "and select how many tracks you're playing. The health check and recommendations above will update automatically."
        "</div>",
        unsafe_allow_html=True
    )
    st.markdown(
        "<div class='sub'>• <b>Active</b> = dollars on-platform (in your casino wallet, ready to play)<br>"
        "• <b>Reserve</b> = dollars off-platform (set aside for top-ups, not in play)<br>"
        "• <b>Tracks</b> = how many concurrent tracks you're running<br>"
        "<span style='color:#6b7280;font-size:.85rem'>All values are in <b>USD ($)</b>, not units.</span></div>",
        unsafe_allow_html=True
    )

    c1, c2, c3 = st.columns([1,1,1])
    with c1:
        ss["__bh_active_usd"] = st.number_input("Active (on-platform) — USD $", min_value=0.0, step=50.0, value=float(ss["__bh_active_usd"]), format="%.2f")
    with c2:
        ss["__bh_reserve_usd"] = st.number_input("Strategic Reserve (off-platform) — USD $", min_value=0.0, step=50.0, value=float(ss["__bh_reserve_usd"]), format="%.2f")
    with c3:
        track_options = list(range(1, 11))  # 1-10
        ss["__bh_track_count"] = st.selectbox("Tracks", options=track_options, index=track_options.index(ss["__bh_track_count"]))

    # ✅ Save Plan Button (if persistence is available)
    if save_bankroll_plan and (user_db_id or auth_id):
        if st.button("💾 Save Bankroll Plan", use_container_width=True):
            try:
                save_bankroll_plan(user_db_id or auth_id, {
                    "active_usd": ss["__bh_active_usd"],
                    "reserve_usd": ss["__bh_reserve_usd"],
                    "track_count": ss["__bh_track_count"],
                })
                st.success("Bankroll plan saved! It will load automatically on your next visit.")
            except Exception as e:
                st.error(f"Failed to save: {e!r}")

    st.markdown("</div>", unsafe_allow_html=True)

# Recalculate after input changes
active_usd = float(ss["__bh_active_usd"])
reserve_usd = float(ss["__bh_reserve_usd"])
total_usd = active_usd + reserve_usd
ratio_active = (active_usd / total_usd) if total_usd > 0 else 0.0
cls, label = _status_color(ratio_active)

t_active_u, t_reserve_u, t_total_u = _targets_for_tracks(ss["__bh_track_count"])
need_active_usd  = max(0.0, t_active_u  * unit_value - active_usd)
need_reserve_usd = max(0.0, t_reserve_u * unit_value - reserve_usd)

# ---------- Health Summary with Progress Bars ----------
with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="h">Health Status</div>', unsafe_allow_html=True)
    st.markdown(
        "<div class='sub'>This section helps you see whether your bankroll split is balanced. "
        "The goal is to keep about 50% of your total bankroll in play (Active) and 50% in reserve. "
        "Nothing here changes your real bankroll — it's just a health check to guide your decisions.</div>",
        unsafe_allow_html=True
    )

    st.markdown(
        f"""<div class='kpi'>
            <div class='kpill'><div class='l'>Active : Reserve</div><div class='v {cls}'>{ratio_active*100:,.0f}% : {100-ratio_active*100:,.0f}%</div></div>
            <div class='kpill'><div class='l'>Status</div><div class='v {cls}'>{label}</div></div>
            <div class='kpill'><div class='l'>Targets (Units)</div><div class='v'>{t_active_u:,}u / {t_reserve_u:,}u (total {t_total_u:,}u)</div></div>
        </div>""",
        unsafe_allow_html=True
    )

    # Progress bars for Active and Reserve
    st.markdown("<div style='margin-top:16px'>", unsafe_allow_html=True)
    
    target_active_usd = t_active_u * unit_value
    target_reserve_usd = t_reserve_u * unit_value
    
    col_a, col_r = st.columns(2)
    with col_a:
        st.markdown("<div class='small' style='font-weight:700;margin-bottom:4px'>Active Progress</div>", unsafe_allow_html=True)
        active_pct = min(100, (active_usd / target_active_usd * 100) if target_active_usd > 0 else 0)
        active_color = "progress-green" if active_pct >= 100 else "progress-yellow" if active_pct >= 70 else "progress-red"
        st.markdown(_progress_bar(active_usd, target_active_usd, active_color), unsafe_allow_html=True)
        
    with col_r:
        st.markdown("<div class='small' style='font-weight:700;margin-bottom:4px'>Reserve Progress</div>", unsafe_allow_html=True)
        reserve_pct = min(100, (reserve_usd / target_reserve_usd * 100) if target_reserve_usd > 0 else 0)
        reserve_color = "progress-green" if reserve_pct >= 100 else "progress-yellow" if reserve_pct >= 70 else "progress-red"
        st.markdown(_progress_bar(reserve_usd, target_reserve_usd, reserve_color), unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ---------- Optimal Bankroll Targets (Reference Tables) ----------
with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="h">Optimal Bankroll Targets (1–3 Tracks)</div>', unsafe_allow_html=True)
    st.markdown(
        "<div class='sub'>Reference tables for the recommended Active / Reserve split and the modeled annual loss odds (for 1-3 tracks). "
        "Use this to decide whether you're properly capitalized before adding tracks or stepping up $/unit. "
        "For 4+ tracks, the system scales linearly (+400u reserve per additional track).</div>",
        unsafe_allow_html=True
    )

    tables = [
        {
            "title": "Playing 1 Track",
            "rows": [
                ("Active (on-platform)", 1000, "1 / 5,556"),
                ("Strategic Reserve (off-platform)", 1000, "1 / 66,667"),
                ("Optimal Total", 2000, "1 / 166,667"),
            ],
        },
        {
            "title": "Playing 2 Concurrent Tracks",
            "rows": [
                ("Active (on-platform)", 1200, "1 / 7,144"),
                ("Strategic Reserve (off-platform)", 1600, "1 / 100,000"),
                ("Optimal Total", 2800, "1 / 166,667"),
            ],
        },
        {
            "title": "Playing 3 Concurrent Tracks",
            "rows": [
                ("Active (on-platform)", 1200, "1 / 4,762"),
                ("Strategic Reserve (off-platform)", 2200, "1 / 100,000"),
                ("Optimal Total", 3400, "1 / 166,667"),
            ],
        },
    ]

    c1, c2, c3 = st.columns(3)
    cols = [c1, c2, c3]

    for col, t in zip(cols, tables):
        with col:
            st.markdown(f"<div class='sub' style='font-weight:800;color:#e5e7eb'>{t['title']}</div>", unsafe_allow_html=True)
            df = []
            for name, units, odds in t["rows"]:
                df.append({
                    "Component": name,
                    "Units Needed": f"{units:,}",
                    "Units ($)": _fmt_money(units * unit_value),
                    "Annual Loss Odds": odds,
                })
            st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown(
        "<div class='small'>"
        "\"Optimal Total\" combines Active + Reserve to hard-cap downside at the weekly guard and preserve the model's compounding profile. "
        "Nothing removes risk — this just frames it and keeps worst-case scenarios rare."
        "</div>",
        unsafe_allow_html=True
    )

    st.markdown("</div>", unsafe_allow_html=True)

# ==================== WHAT IF CALCULATOR (NEW) ====================
with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="h">🔮 What If Calculator</div>', unsafe_allow_html=True)
    st.markdown(
        "<div class='sub'>Explore hypothetical scenarios before making changes. "
        "See how stepping up $/unit or adding tracks would affect your bankroll requirements.</div>",
        unsafe_allow_html=True
    )

    wi_col1, wi_col2 = st.columns(2)
    
    with wi_col1:
        what_if_unit = st.number_input(
            "What if $/unit was:", 
            min_value=0.5, 
            value=float(unit_value), 
            step=0.5,
            key="__bh_what_if_unit"
        )
    
    with wi_col2:
        wi_track_options = list(range(1, 11))  # 1-10
        wi_current_tracks = min(ss["__bh_track_count"], 10)  # Clamp to valid range
        what_if_tracks = st.selectbox(
            "What if I ran:",
            options=wi_track_options,
            index=wi_current_tracks - 1,
            format_func=lambda x: f"{x} track{'s' if x > 1 else ''}",
            key="__bh_what_if_tracks"
        )

    # Calculate hypothetical requirements
    wi_active_t, wi_reserve_t, wi_total_t = _targets_for_tracks(what_if_tracks)
    wi_total_usd_needed = wi_total_t * what_if_unit
    wi_active_usd_needed = wi_active_t * what_if_unit
    wi_reserve_usd_needed = wi_reserve_t * what_if_unit
    
    wi_funded = total_usd >= wi_total_usd_needed
    wi_shortfall = max(0, wi_total_usd_needed - total_usd)
    
    # Compare to current
    current_total_needed = t_total_u * unit_value
    change_in_requirements = wi_total_usd_needed - current_total_needed

    st.markdown("<hr style='margin:12px 0'>", unsafe_allow_html=True)
    
    # Results
    st.markdown(f"<div class='small' style='font-weight:700;margin-bottom:8px'>At <b>${what_if_unit:.2f}/unit</b> with <b>{what_if_tracks} track{'s' if what_if_tracks > 1 else ''}</b>:</div>", unsafe_allow_html=True)
    
    wi_col_a, wi_col_b, wi_col_c = st.columns(3)
    
    with wi_col_a:
        st.markdown(
            f"<div class='kpill'><div class='l'>Total Required</div>"
            f"<div class='v'>{_fmt_money(wi_total_usd_needed)}</div></div>",
            unsafe_allow_html=True
        )
        st.markdown(
            f"<div class='kpill' style='margin-top:8px'><div class='l'>Active / Reserve</div>"
            f"<div class='v'>{_fmt_money(wi_active_usd_needed)} / {_fmt_money(wi_reserve_usd_needed)}</div></div>",
            unsafe_allow_html=True
        )
    
    with wi_col_b:
        st.markdown(
            f"<div class='kpill'><div class='l'>You Have</div>"
            f"<div class='v'>{_fmt_money(total_usd)}</div></div>",
            unsafe_allow_html=True
        )
        change_cls = "good" if change_in_requirements <= 0 else "bad"
        change_sign = "+" if change_in_requirements > 0 else ""
        st.markdown(
            f"<div class='kpill' style='margin-top:8px'><div class='l'>vs Current Requirements</div>"
            f"<div class='v {change_cls}'>{change_sign}{_fmt_money(change_in_requirements)}</div></div>",
            unsafe_allow_html=True
        )
    
    with wi_col_c:
        if wi_funded:
            st.markdown(
                "<div class='kpill' style='border-color:#22c55e'><div class='l'>Status</div>"
                "<div class='v good'>✅ Funded</div></div>",
                unsafe_allow_html=True
            )
            st.markdown(
                f"<div class='kpill' style='margin-top:8px'><div class='l'>Buffer</div>"
                f"<div class='v good'>+{_fmt_money(total_usd - wi_total_usd_needed)}</div></div>",
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                "<div class='kpill' style='border-color:#ef4444'><div class='l'>Status</div>"
                "<div class='v bad'>❌ Underfunded</div></div>",
                unsafe_allow_html=True
            )
            st.markdown(
                f"<div class='kpill' style='margin-top:8px'><div class='l'>Shortfall</div>"
                f"<div class='v bad'>-{_fmt_money(wi_shortfall)}</div></div>",
                unsafe_allow_html=True
            )

    # Actionable insight
    if wi_funded and change_in_requirements > 0:
        st.markdown(
            "<div class='small' style='margin-top:12px;padding:10px;border:1px solid #22c55e;border-radius:8px;background:#0f1a14'>"
            "💡 <b>You can make this change.</b> Your current bankroll would cover the increased requirements."
            "</div>",
            unsafe_allow_html=True
        )
    elif not wi_funded:
        st.markdown(
            f"<div class='small' style='margin-top:12px;padding:10px;border:1px solid #ef4444;border-radius:8px;background:#1a0f0f'>"
            f"⚠️ <b>Not ready yet.</b> You'd need to add {_fmt_money(wi_shortfall)} to your bankroll before making this change."
            f"</div>",
            unsafe_allow_html=True
        )

    st.markdown("</div>", unsafe_allow_html=True)

# ---------- Decision Tools (A / B / C) ----------
total_units_now = (total_usd / unit_value) if unit_value > 0 else 0.0

# Recalculate readiness with auto-detected defensive mode
funded_for_selected = total_units_now >= float(t_total_u)
split_healthy = 0.40 <= ratio_active <= 0.60

readiness_score = int(funded_for_selected) + int(split_healthy) + int(no_defensive_mode)
if readiness_score == 3:
    step_cls, step_label = "good", "🟢 Ready — step up slowly (small increments)"
elif readiness_score == 2:
    step_cls, step_label = "warn", "🟡 Not yet (close — fix the weak link first)"
else:
    step_cls, step_label = "bad", "🔴 Do not step up"

with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="h">Decision Tools (Use These Before You Change Anything)</div>', unsafe_allow_html=True)
    st.markdown(
        "<div class='sub'>These tools turn your inputs into clear actions: "
        "<b>can you step up $/unit?</b> <b>should you run 1–3 tracks?</b> and <b>how should you rebalance?</b> "
        "Everything here is still reference-only — nothing touches your Tracker.</div>",
        unsafe_allow_html=True
    )

    # ------------------ A) Step-Up Readiness ------------------
    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown('<div class="h">A) Step-Up Readiness (Should you increase $/unit?)</div>', unsafe_allow_html=True)
    st.markdown(
        "<div class='sub'>Use this before you increase $/unit. The idea is simple: "
        "don't raise unit size unless your bankroll structure can actually absorb the downside.</div>",
        unsafe_allow_html=True
    )

    a1, a2 = st.columns([1.2, 1])
    with a1:
        # ✅ Auto-detected defensive mode status (no manual checkbox needed)
        st.markdown(
            f"<div class='small'>"
            f"<b>Checklist:</b><br>"
            f"• Funded for your selected track count ({ss['__bh_track_count']} track{'s' if ss['__bh_track_count'] > 1 else ''}): <b>{_bool_badge(funded_for_selected)}</b><br>"
            f"• Healthy Active/Reserve split (40–60% Active): <b>{_bool_badge(split_healthy)}</b><br>"
            f"• Defensive Mode is OFF everywhere: <b>{_bool_badge(no_defensive_mode)}</b> <span style='color:#6b7280;font-size:.8rem'>(auto-detected)</span>"
            f"</div>",
            unsafe_allow_html=True
        )
    with a2:
        st.markdown(
            f"<div class='kpill'><div class='l'>Step-Up Status</div>"
            f"<div class='v {step_cls}'>{step_label}</div></div>",
            unsafe_allow_html=True
        )
        st.markdown(
            "<div class='small'>"
            "<b>How to use this:</b> If you're not green here, your move is not \"play harder.\" "
            "Your move is to fund the target, rebalance Active/Reserve, and keep running the process until it's stable."
            "</div>",
            unsafe_allow_html=True
        )

    # ------------------ B) Track Count Recommendation ------------------
    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown('<div class="h">B) Track Count Recommendation (How many tracks should you run?)</div>', unsafe_allow_html=True)
    st.markdown(
        "<div class='sub'>This is based on your <b>Total Units</b>. "
        "It tells you the maximum track count your bankroll can support without stretching the risk model.</div>",
        unsafe_allow_html=True
    )

    def _funded_tracks_by_total_units(total_units: float) -> int:
        """Returns max tracks the bankroll can support."""
        for n in range(10, 0, -1):  # Check from 10 down to 1
            _, _, required = _targets_for_tracks(n)
            if total_units >= required:
                return n
        return 0

    max_tracks = _funded_tracks_by_total_units(total_units_now)
    if max_tracks == 0:
        rec_cls, rec_txt = "bad", "🔴 Underfunded (do not run live yet)"
    elif max_tracks == 1:
        rec_cls, rec_txt = "warn", "🟡 Funded for 1 track (keep it simple)"
    elif max_tracks == 2:
        rec_cls, rec_txt = "good", "🟢 Funded for up to 2 tracks"
    elif max_tracks == 3:
        rec_cls, rec_txt = "good", "🟢 Funded for up to 3 tracks"
    else:
        rec_cls, rec_txt = "good", f"🟢 Funded for up to {max_tracks} tracks"

    r1, r2, r3 = st.columns([1.2, 1, 1])
    with r1:
        st.markdown(
            f"<div class='kpill'><div class='l'>Your Total Units</div>"
            f"<div class='v'>{_fmt_units(total_units_now)}</div></div>",
            unsafe_allow_html=True
        )
    with r2:
        st.markdown(
            f"<div class='kpill'><div class='l'>Max Supported Tracks</div>"
            f"<div class='v {rec_cls}'>{max_tracks}</div></div>",
            unsafe_allow_html=True
        )
    with r3:
        st.markdown(
            f"<div class='kpill'><div class='l'>Recommendation</div>"
            f"<div class='v {rec_cls}'>{rec_txt}</div></div>",
            unsafe_allow_html=True
        )

    st.markdown(
        "<div class='small'>"
        "<b>How to use this:</b> Don't add tracks because you're bored. "
        "Add tracks only when your bankroll supports it — otherwise you're just increasing volatility."
        "</div>",
        unsafe_allow_html=True
    )

    # ------------------ C) Top-Up / Rebalance Assistant ------------------
    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown('<div class="h">C) Top-Up & Rebalance Assistant</div>', unsafe_allow_html=True)
    st.markdown(
        "<div class='sub'>This helps you keep the model's structure intact. "
        "If Active is below target, you top-up from Reserve. If Active is too high, you de-risk by moving money back to Reserve.</div>",
        unsafe_allow_html=True
    )

    # Suggested moves
    need_to_topup_active = max(0.0, target_active_usd - active_usd)
    excess_active = max(0.0, active_usd - target_active_usd)

    # Cap top-up by available reserve
    topup_from_reserve = min(need_to_topup_active, reserve_usd)
    move_back_to_reserve = excess_active

    # Cleaner 2-column layout
    rebal_col1, rebal_col2 = st.columns(2)
    
    with rebal_col1:
        st.markdown("<div class='small' style='font-weight:700;margin-bottom:8px'>📥 Top-Up Active</div>", unsafe_allow_html=True)
        
        topup_pct = min(100, (active_usd / target_active_usd * 100) if target_active_usd > 0 else 100)
        topup_color = "progress-green" if topup_pct >= 100 else "progress-yellow" if topup_pct >= 70 else "progress-red"
        st.markdown(_progress_bar(active_usd, target_active_usd, topup_color), unsafe_allow_html=True)
        
        if topup_from_reserve > 0:
            st.markdown(
                f"<div class='kpill' style='margin-top:8px'><div class='l'>Suggested Move (Reserve → Active)</div>"
                f"<div class='v'>{_fmt_money(topup_from_reserve)}</div></div>",
                unsafe_allow_html=True
            )
            if st.button("Apply Top-Up", use_container_width=True, key="topup_btn"):
                ss["__bh_active_usd"] += topup_from_reserve
                ss["__bh_reserve_usd"] -= topup_from_reserve
                st.success(f"Moved {_fmt_money(topup_from_reserve)} from Reserve → Active")
                st.rerun()
        else:
            st.markdown("<div class='small' style='color:#22c55e'>✅ Active is at or above target</div>", unsafe_allow_html=True)

    with rebal_col2:
        st.markdown("<div class='small' style='font-weight:700;margin-bottom:8px'>📤 De-Risk to Reserve</div>", unsafe_allow_html=True)
        
        reserve_pct = min(100, (reserve_usd / target_reserve_usd * 100) if target_reserve_usd > 0 else 100)
        reserve_color = "progress-green" if reserve_pct >= 100 else "progress-yellow" if reserve_pct >= 70 else "progress-red"
        st.markdown(_progress_bar(reserve_usd, target_reserve_usd, reserve_color), unsafe_allow_html=True)
        
        if move_back_to_reserve > 0:
            st.markdown(
                f"<div class='kpill' style='margin-top:8px'><div class='l'>Suggested Move (Active → Reserve)</div>"
                f"<div class='v'>{_fmt_money(move_back_to_reserve)}</div></div>",
                unsafe_allow_html=True
            )
            if st.button("Apply De-Risk", use_container_width=True, key="derisk_btn"):
                ss["__bh_active_usd"] -= move_back_to_reserve
                ss["__bh_reserve_usd"] += move_back_to_reserve
                st.success(f"Moved {_fmt_money(move_back_to_reserve)} from Active → Reserve")
                st.rerun()
        else:
            st.markdown("<div class='small' style='color:#6b7280'>No excess Active to move</div>", unsafe_allow_html=True)

    st.markdown(
        "<div class='small' style='margin-top:12px'>"
        "<b>Best practice:</b> Treat Reserve like your safety net. "
        "Top up Active only to the target — don't keep everything on-platform \"just in case.\""
        "</div>",
        unsafe_allow_html=True
    )

    st.markdown("</div>", unsafe_allow_html=True)

# ---------- Bonuses ----------
with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="h">Bonuses & Rakeback</div>', unsafe_allow_html=True)
    st.markdown(
        "<div class='sub'><b>Take full advantage of every bonus and rakeback offer available.</b> "
        "Enter your expected bonuses below, then decide how to allocate them: "
        "<b>Reserve</b> (safety top-up), <b>Active</b> (scaling toward higher $/unit), or <b>Profit</b> (withdraw).</div>",
        unsafe_allow_html=True
    )

    # Input row
    b1, b2, b3 = st.columns(3)
    with b1:
        ss["__bh_bonus_weekly"] = st.number_input("Weekly Bonus ($)", min_value=0.0, step=10.0, value=float(ss["__bh_bonus_weekly"]))
    with b2:
        ss["__bh_bonus_monthly"] = st.number_input("Monthly Bonus ($)", min_value=0.0, step=10.0, value=float(ss["__bh_bonus_monthly"]))
    with b3:
        ss["__bh_rakeback"] = st.number_input("Rakeback ($)", min_value=0.0, step=10.0, value=float(ss["__bh_rakeback"]))

    total_bonus = ss["__bh_bonus_weekly"] + ss["__bh_bonus_monthly"] + ss["__bh_rakeback"]

    st.markdown("<hr style='margin:16px 0 12px 0;border-color:#2b2b2b'>", unsafe_allow_html=True)
    st.markdown("<div class='small' style='font-weight:700;margin-bottom:8px'>Allocate Your Bonuses</div>", unsafe_allow_html=True)

    # Initialize allocation percentages
    ss.setdefault("__bh_pct_reserve", 50)
    ss.setdefault("__bh_pct_active", 25)
    ss.setdefault("__bh_pct_profit", 25)

    # Allocation inputs
    alloc1, alloc2, alloc3 = st.columns(3)
    with alloc1:
        pct_reserve = st.number_input("To Reserve (%)", min_value=0, max_value=100, value=int(ss["__bh_pct_reserve"]), step=5, key="__bh_pct_reserve_input")
    with alloc2:
        pct_active = st.number_input("To Active (%)", min_value=0, max_value=100, value=int(ss["__bh_pct_active"]), step=5, key="__bh_pct_active_input")
    with alloc3:
        pct_profit = st.number_input("Take Profit (%)", min_value=0, max_value=100, value=int(ss["__bh_pct_profit"]), step=5, key="__bh_pct_profit_input")

    # Update session state
    ss["__bh_pct_reserve"] = pct_reserve
    ss["__bh_pct_active"] = pct_active
    ss["__bh_pct_profit"] = pct_profit

    # Validate total = 100%
    total_pct = pct_reserve + pct_active + pct_profit
    
    if total_pct != 100:
        st.warning(f"⚠️ Allocation must total 100%. Currently: {total_pct}%")
    
    # Calculate amounts
    amt_reserve = total_bonus * (pct_reserve / 100) if total_pct == 100 else 0
    amt_active = total_bonus * (pct_active / 100) if total_pct == 100 else 0
    amt_profit = total_bonus * (pct_profit / 100) if total_pct == 100 else 0

    # Summary pills
    st.markdown(
        f"""<div class='kpi' style='margin-top:12px'>
            <div class='kpill'><div class='l'>Total Bonus</div><div class='v'>{_fmt_money(total_bonus)}</div></div>
            <div class='kpill'><div class='l'>→ Reserve</div><div class='v good'>{_fmt_money(amt_reserve)}</div></div>
            <div class='kpill'><div class='l'>→ Active</div><div class='v warn'>{_fmt_money(amt_active)}</div></div>
            <div class='kpill'><div class='l'>→ Profit</div><div class='v' style='color:#60a5fa'>{_fmt_money(amt_profit)}</div></div>
        </div>""",
        unsafe_allow_html=True
    )

    # Apply button
    if total_pct == 100 and total_bonus > 0:
        if st.button("Apply Allocation (for reference only)", type="primary", use_container_width=True):
            ss["__bh_reserve_usd"] += amt_reserve
            ss["__bh_active_usd"] += amt_active
            # Profit is "taken out" - doesn't go anywhere in the planner
            ss["__bh_bonus_weekly"] = ss["__bh_bonus_monthly"] = ss["__bh_rakeback"] = 0.0
            st.success(f"Applied: {_fmt_money(amt_reserve)} → Reserve, {_fmt_money(amt_active)} → Active, {_fmt_money(amt_profit)} → Profit (withdrawn)")
            st.rerun()

    st.markdown(
        "<div class='small' style='margin-top:12px; padding:10px; border:1px solid #334155; border-radius:8px; background:#0f1115;'>"
        "<b>💡 Pro tip:</b> Most players underutilize bonuses. Treat bonus collection as part of your weekly operating discipline — "
        "not an afterthought. A common split: 50% Reserve / 25% Active / 25% Profit."
        "</div>",
        unsafe_allow_html=True
    )

    st.markdown("</div>", unsafe_allow_html=True)

# ---------- Snapshot ----------
with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="h">Dollar ↔ Unit Snapshot</div>', unsafe_allow_html=True)
    st.markdown(
        "<div class='sub'>This table converts your balances between dollars and units, based on your $/unit from Settings. "
        "It helps you visualize your bankroll in the same terms used throughout the app. "
        "Again, this is for planning only — nothing here changes your actual bankroll.</div>",
        unsafe_allow_html=True
    )

    cur_active_u = active_usd / unit_value if unit_value > 0 else 0.0
    cur_reserve_u = reserve_usd / unit_value if unit_value > 0 else 0.0
    cur_total_u = cur_active_u + cur_reserve_u

    st.dataframe(
        [
            {"Bucket": "Active",  "Balance ($)": _fmt_money(active_usd),  "Units": _fmt_units(cur_active_u)},
            {"Bucket": "Reserve", "Balance ($)": _fmt_money(reserve_usd), "Units": _fmt_units(cur_reserve_u)},
            {"Bucket": "Total",   "Balance ($)": _fmt_money(total_usd),   "Units": _fmt_units(cur_total_u)},
        ],
        hide_index=True, use_container_width=True
    )

    target_total_usd = (t_total_u * unit_value)
    gap_usd = max(0.0, target_total_usd - total_usd)
    st.markdown(
        f"<div class='small'>Target for {ss['__bh_track_count']} track(s): "
        f"<b>{t_total_u:,}u</b> ≈ <b>{_fmt_money(target_total_usd)}</b>. "
        f"Shortfall: <b>{_fmt_money(gap_usd)}</b>. This is informational only.</div>",
        unsafe_allow_html=True
    )

    st.markdown(
        "<div class='sub'>✅ <b>Reminder:</b> This page is completely independent from the rest of the app. "
        "It's meant to help you manage bankroll structure manually. "
        "Your play data, P/L, and bankroll results inside the Tracker will always stay separate.</div>",
        unsafe_allow_html=True
    )

    st.markdown("</div>", unsafe_allow_html=True)