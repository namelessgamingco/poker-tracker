# pages/02_Track_Overview.py — clean overview …

import streamlit as st
st.set_page_config(page_title="Overview", page_icon="📊", layout="wide")

from auth import require_auth
user = require_auth()

from datetime import datetime, timedelta, time
from math import isfinite

from track_manager import TrackManager
from week_manager import WeekManager
from engine import DiamondHybrid
from sidebar import render_sidebar
from typing import Dict, Any, Optional
from db import get_profile_by_auth_id

from cache import (
    get_cached_tracks,
    get_cached_track_state,
    get_cached_player_totals,
    get_cached_closed_weeks_distribution,
    is_hydrated,
    mark_hydrated,
)

# Cache of raw Supabase track_state per track_id for this run.
# Populated in _force_hydrate_tracks so we can pull week_pl, tone, etc.
TRACK_STATES_RAW: Dict[str, Dict[str, Any]] = {}

# NEW: DB stats helpers
try:
    from db_stats import (
        get_player_totals,
        get_closed_weeks_distribution,
    )
except Exception:
    def get_player_totals(user_id: str):
        return {
            "all_time_units": 0.0,
            "month_units": 0.0,
            "week_units": 0.0,
            "ev_diff_units": 0.0,  # keep consistent with db_stats
        }

    def get_closed_weeks_distribution(user_id: str):
        return {
            "counts": {"+400": 0, "+300": 0, "+160": 0, "-85": 0, "-400": 0},
            "total_closed": 0,
        }

# NEW: DB user + track state helpers
try:
    from db import get_or_create_user, get_tracks_for_user, load_track_state, ensure_track_state, get_week_pl_booked
except Exception:
    def load_track_state(*args, **kwargs) -> Optional[Dict[str, Any]]:
        return None

    def get_tracks_for_user(*args, **kwargs):
        return []

    def get_or_create_user(*args, **kwargs):
        return {}

    def ensure_track_state(*args, **kwargs):
        return None
    
    def get_week_pl_booked(*args, **kwargs):
        return {"units": 0.0, "dollars": 0.0}

render_sidebar()

# ---- Optional timezone for reset timer (PST parity with Tracker/App) ----
_TZ = None  # IMPORTANT: define the name no matter what

try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo("America/Los_Angeles")
except Exception:
    _TZ = None

# ---- Testing Mode badge (simple & clean) ----
def _testing_badge():
    if bool(st.session_state.get("testing_mode", False)):
        st.markdown("""
<style>
.test-pill{
  display:inline-flex;align-items:center;gap:8px;
  border:1px solid #5b1f22;background:linear-gradient(180deg,#1d0f10,#1a0c0d);
  color:#fca5a5;border-radius:999px;padding:6px 10px;font-size:.82rem;
  box-shadow:0 2px 12px rgba(0,0,0,.35)
}
.test-pill .dot{width:7px;height:7px;border-radius:999px;background:#ef4444}
.test-note{color:#9ca3af;font-size:.80rem;margin-top:6px}
</style>
<div class="test-pill"><span class="dot"></span><b>TESTING MODE</b></div>
<div class="test-note">Sandboxed: results don’t affect live totals or closed-week stats.</div>
""", unsafe_allow_html=True)

_testing_badge()

# ---------- Style ----------
st.markdown("""
<style>
.hero-card{border:1px solid #1f1f1f;background:linear-gradient(180deg,#0e0e0f,#121214);
  border-radius:14px;padding:14px 16px;margin-bottom:12px}
.hero-title{color:#9ca3af;font-size:.9rem;margin-bottom:6px}
.hero-value{font-size:1.25rem;font-weight:800;color:#e5e7eb}

.pill{display:inline-flex;align-items:center;gap:8px;border:1px solid #2a2a2a;
  background:#121212;color:#d1d5db;border-radius:999px;padding:6px 10px;font-size:.85rem}
.pill .dot{width:7px;height:7px;border-radius:999px;background:#ef4444}

.kicker{color:#9ca3af;font-size:.85rem}

.table-wrap{border:1px solid #202020;border-radius:12px;overflow:hidden}
.table-hdr{display:grid;grid-template-columns:1.6fr .7fr .7fr .6fr;
  padding:10px 12px;border-bottom:1px solid #232323;background:#121214}
.table-row{display:grid;grid-template-columns:1.6fr .7fr .7fr .6fr;
  padding:8px 12px;border-bottom:1px solid #171717}
.table-row:last-child{border-bottom:none}
.cell{color:#e5e7eb}
.cell.mono{font-variant-numeric:tabular-nums;color:#d1d5db}
.cell.dim{color:#9ca3af}

.snap-table{border:1px solid #202020;border-radius:12px;overflow:hidden}
.snap-hdr{display:grid;grid-template-columns:.9fr 1fr 1.2fr 1.2fr 1.2fr 1.1fr 1fr;
  padding:10px 12px;border-bottom:1px solid #232323;background:#121214}
.snap-row{display:grid;grid-template-columns:.9fr 1fr 1.2fr 1.2fr 1.2fr 1.1fr 1fr;
  padding:8px 12px;border-bottom:1px solid #171717}
.snap-row:last-child{border-bottom:none}
</style>
""", unsafe_allow_html=True)

# ---------- Auth helper → extract id/email for DB ----------
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

    if not auth_id:
        st.error("Auth error: missing user id. Please log out and log back in.")
        st.stop()
    if not email:
        email = "unknown@example.com"

    return str(auth_id), str(email)

# ---------- Helpers ----------
def _fmt_u_d(units: float, dollars: float) -> str:
    """Format units + dollars (for historical data with pre-calculated dollars)."""
    try:
        u = float(units)
        d = float(dollars)
    except Exception:
        return "+0.00u (+$0.00)"
    sign_u = "+" if u >= 0 else ""
    sign_d = "+" if d >= 0 else ""
    return f"{sign_u}{u:.2f}u ({sign_d}${abs(d):,.2f})"

def _fmt_u_d_live(units: float, unit_value: float) -> str:
    """Format units with live dollar conversion (for current/in-progress data)."""
    try:
        u = float(units)
        usd = u * float(unit_value)
    except Exception:
        return "+0.00u (+$0.00)"
    sign_u = "+" if u >= 0 else ""
    sign_d = "+" if usd >= 0 else ""
    return f"{sign_u}{u:.2f}u ({sign_d}${abs(usd):,.2f})"

def _fmt_u_d_precomputed(units: float, dollars: float) -> str:
    """Format units + dollars when dollars are already calculated (historical accuracy)."""
    try:
        u = float(units)
        d = float(dollars)
    except Exception:
        return "+0.00u (+$0.00)"
    sign_u = "+" if u >= 0 else ""
    sign_d = "+" if d >= 0 else ""
    return f"{sign_u}{u:.2f}u ({sign_d}${abs(d):,.2f})"

def _safe_float(x, default=0.0):
    try:
        v = float(x)
        return v if isfinite(v) else default
    except Exception:
        return default

def _pick_state_num(state: dict, *keys, default=0.0) -> float:
    for k in keys:
        if k in state:
            return _safe_float(state.get(k), default)
    return default

def _midnight_countdown():
    tz = globals().get("_TZ", None)  # ✅ safe even if _TZ wasn't defined for some reason
    now = datetime.now(tz) if tz else datetime.now()
    tomorrow = (now + timedelta(days=1)).date()
    next_mid = datetime.combine(tomorrow, time(0, 0, 0), tzinfo=tz) if tz else datetime.combine(tomorrow, time(0, 0, 0))
    rem = max(0, int((next_mid - now).total_seconds()))
    h = rem // 3600
    m = (rem % 3600) // 60
    s = rem % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

# ---------- DB state wrapper (handles both db.py signatures) ----------
def _load_state(user_id: str, track_id: str) -> dict:
    """
    Uses cache to avoid DB hits on every rerun.
    """
    if not track_id or not user_id:
        return {}
    return get_cached_track_state(str(user_id), str(track_id), load_track_state)

# ---------- Session / Managers ----------
# Load user-specific unit_value from DB
if "unit_value" not in st.session_state:
    st.session_state.unit_value = 1.0

if "tm" not in st.session_state:
    st.session_state.tm = TrackManager(unit_value=float(st.session_state.unit_value))

tm: TrackManager = st.session_state.tm
unit_value = float(st.session_state.unit_value)

# Cadence counters (mirror Tracker defaults)
st.session_state.setdefault("sessions_today", 0)
st.session_state.setdefault("lines_in_session", 0)

def _sync_today_pacing():
    st.session_state.setdefault("sessions_today", 0)
    st.session_state.setdefault("lines_in_session", 0)

# ---------- Resolve profile + canonical DB user_id (Tracker-truth) ----------
auth_id, email = _extract_auth_identity(user)

try:
    profile = get_profile_by_auth_id(auth_id) or {}
except Exception:
    st.error("DB error loading profile. Try again in a moment.")
    st.stop()

user_db_id = str(profile.get("user_id") or "")
if not user_db_id:
    st.error("Profile not found for this account. Contact an admin.")
    st.stop()

# ✅ Load user-specific unit_value from DB (must be after user_db_id is defined)
if st.session_state.get("_unit_value_user") != user_db_id:
    try:
        from db import get_user_unit_value
        st.session_state.unit_value = get_user_unit_value(user_db_id)
        st.session_state._unit_value_user = user_db_id
    except Exception as e:
        print(f"[overview] unit_value load error: {e!r}")

st.session_state["user_db_id"] = user_db_id
st.session_state["profile"] = profile

# ---------- Hydrate daily counters from DB (global across tracks) ----------
def _hydrate_daily_counters_from_db(user_db_id: str):
    if not user_db_id:
        return

    try:
        tracks = get_cached_tracks(user_db_id, get_tracks_for_user) or []
        if not tracks:
            return

        total_nb = 0
        total_lod = 0

        for t in tracks:
            tid = str(t.get("id") or "")
            if not tid:
                continue

            state = _load_state(user_db_id, tid)
            total_nb += int(state.get("sessions_today", 0) or 0)
            total_lod += int(state.get("lines_in_session", 0) or 0)

        st.session_state["sessions_today"] = total_nb
        st.session_state["lines_in_session"] = total_lod

    except Exception as e:
        print(f"[overview] hydrate_daily_counters_from_db error: {e!r}")

def _backfill_track_state_rows(user_db_id: str):
    """
    Ensure every existing track has a track_state row so Overview can hydrate
    without requiring the user to visit Tracker first.
    """
    if not user_db_id:
        return

    # run once per session
    if st.session_state.get("_track_state_backfilled", False):
        return

    try:
        db_tracks = get_cached_tracks(user_db_id, get_tracks_for_user) or []
        for t in db_tracks:
            tid = str(t.get("id") or "")
            if not tid:
                continue
            try:
                ensure_track_state(user_db_id, tid)
            except Exception as e:
                print(f"[overview] ensure_track_state failed for {tid}: {e!r}")

        st.session_state["_track_state_backfilled"] = True

    except Exception as e:
        print(f"[overview] _backfill_track_state_rows error: {e!r}")

# ---------- Force hydrate TrackManager bundles from DB ----------
def _force_hydrate_tracks(user_db_id: str):
    """
    Mirror Tracker page hydration:
    - For each DB track, ensure a bundle exists
    - If the bundle exposes import_state, feed it the raw saved state.

    This keeps week_pl, tone, fragility, etc. identical to Tracker,
    even on a cold login where Tracker hasn't run yet.
    """
    if not user_db_id:
        return

    try:
        db_tracks = get_cached_tracks(user_db_id, get_tracks_for_user) or []
    except Exception as e:
        print(f"[overview] _force_hydrate_tracks get_tracks error: {e!r}")
        return

    for t in db_tracks:
        tid = str(t.get("id"))
        try:
            bundle = tm.ensure(tid)
        except Exception as e:
            print(f"[overview] _force_hydrate_tracks ensure error for track {t!r}: {e!r}")
            continue

        # ✅ Ensure a row exists (cold login / older users)
        try:
            ensure_track_state(user_db_id, tid)
        except Exception as e:
            print(f"[overview] ensure_track_state failed inside hydrate for {tid}: {e!r}")

        try:
            state = _load_state(user_db_id, tid)
        except Exception as e:
            print(f"[overview] _force_hydrate_tracks load_state error for {tid}: {e!r}")
            continue

        # Cache raw state so Overview can read cadence etc.
        TRACK_STATES_RAW[tid] = state or {}

        # --- Hydrate bundle like Tracker (robust) ---
        imported = False
        if hasattr(bundle, "import_state") and callable(getattr(bundle, "import_state")):
            try:
                bundle.import_state(state or {})
                imported = True
            except Exception as e:
                print(f"[overview] bundle.import_state failed for {tid}: {e!r}")

        # Fallback: hydrate engine + week explicitly
        if not imported:
            try:
                eng_state = (
                    (state or {}).get("engine")
                    or (state or {}).get("eng")
                    or (state or {}).get("engine_state")
                    or (state or {}).get("engine_state_json")
                )
                if isinstance(eng_state, dict) and hasattr(bundle, "eng"):
                    if hasattr(bundle.eng, "import_state"):
                        bundle.eng.import_state(eng_state)
                    elif hasattr(bundle.eng, "load_state"):
                        bundle.eng.load_state(eng_state)
            except Exception as e:
                print(f"[overview] engine hydrate fallback failed for {tid}: {e!r}")

            try:
                wk_state = (
                    (state or {}).get("week")
                    or (state or {}).get("week_state")
                    or (state or {}).get("week_state_json")
                )
                if isinstance(wk_state, dict) and hasattr(bundle, "week"):
                    if hasattr(bundle.week, "import_state"):
                        bundle.week.import_state(wk_state)
                    elif hasattr(bundle.week, "load_state"):
                        bundle.week.load_state(wk_state)
            except Exception as e:
                print(f"[overview] week hydrate fallback failed for {tid}: {e!r}")

# Run hydration in the correct order
_backfill_track_state_rows(user_db_id)
if not is_hydrated(user_db_id):
    _force_hydrate_tracks(user_db_id)
    mark_hydrated(user_db_id)
_hydrate_daily_counters_from_db(user_db_id)

# ---------- Hydrate tracks from DB + build labels ----------
def _ensure_tracks_for_overview(user_db_id: str) -> dict[str, str]:
    labels: dict[str, str] = {}

    if not user_db_id:
        # local/dev fallback only (no DB user)
        if not tm.all_ids():
            tm.ensure("Track 1")
        for idx, tid in enumerate(tm.all_ids(), start=1):
            labels[str(tid)] = f"Track {idx}"
        return labels

    try:
        db_tracks = get_cached_tracks(user_db_id, get_tracks_for_user) or []
    except Exception as e:
        print(f"[overview] _ensure_tracks_for_overview error: {e!r}")
        db_tracks = []

    # IMPORTANT: if DB user exists but no tracks, do NOT create fake ones.
    if not db_tracks:
        return {}

    for idx, t in enumerate(db_tracks, start=1):
        tid = str(t.get("id") or "")
        if not tid:
            continue

        label = (
            t.get("track_label")
            or t.get("name")
            or f"Track {idx}"
        )

        labels[tid] = label
        tm.ensure(tid)  # safe: ensure bundle exists for real DB track id only

    return labels

TRACK_LABELS = _ensure_tracks_for_overview(user_db_id)

# Canonical ordered list for the whole page:
TRACK_IDS = list(TRACK_LABELS.keys())

# ---------- Aggregates (Supabase for all-time/month/week) ----------
def _aggregate_totals():
    all_time_u = 0.0
    all_time_d = 0.0  # ✅ NEW
    month_u = 0.0
    month_d = 0.0  # ✅ NEW
    week_u = 0.0
    week_d = 0.0  # ✅ NEW

    try:
        db_totals = get_cached_player_totals(user_db_id, get_player_totals) or {}
        all_time_u = _safe_float(db_totals.get("all_time_units", 0.0))
        all_time_d = _safe_float(db_totals.get("all_time_dollars", 0.0))  # ✅ NEW
        month_u = _safe_float(db_totals.get("month_units", 0.0))
        month_d = _safe_float(db_totals.get("month_dollars", 0.0))  # ✅ NEW
        week_u = _safe_float(db_totals.get("week_units", 0.0))
        week_d = _safe_float(db_totals.get("week_dollars", 0.0))  # ✅ NEW
    except Exception as e:
        print(f"[overview] _aggregate_totals error: {e!r}")

    return all_time_u, all_time_d, month_u, month_d, week_u, week_d

ALL_U, ALL_D, MONTH_U, MONTH_D, WEEK_U, WEEK_D = _aggregate_totals()

# Weekly odds reference
EXPECTED = [
    ("+400", 36.20),
    ("+300", 22.00),
    ("+160", 28.30),
    ("-85", 9.80),
    ("-400", 3.70),
]

def _closed_weeks_stats():
    try:
        db_res = get_cached_closed_weeks_distribution(user_db_id, get_closed_weeks_distribution) or {}
        raw_counts = db_res.get("counts") or {}
        total_closed = int(_safe_float(db_res.get("total_closed", 0)))
        counts = {label: 0 for label, _ in EXPECTED}

        if raw_counts:
            keys = {str(k) for k in raw_counts.keys()}

            if any(k in keys for k in (
                "primary_cap",
                "optimizer_cap",
                "small_green",
                "red_stabilizer",
                "weekly_guard",
                "other",
            )):
                counts["+400"] = int(_safe_float(raw_counts.get("primary_cap", 0)))
                counts["+300"] = int(_safe_float(raw_counts.get("optimizer_cap", 0)))
                counts["+160"] = int(_safe_float(raw_counts.get("small_green", 0)))
                counts["-85"] = int(_safe_float(raw_counts.get("red_stabilizer", 0)))
                counts["-400"] = int(_safe_float(raw_counts.get("weekly_guard", 0)))
            else:
                for label, _ in EXPECTED:
                    counts[label] = int(_safe_float(raw_counts.get(label, 0)))

            if total_closed <= 0:
                total_closed = sum(counts.values())

            if total_closed > 0:
                return counts, total_closed

    except Exception as e:
        print(f"[overview] _closed_weeks_stats DB path error: {e!r}")

    counts = {k: 0 for k, _ in EXPECTED}
    closed_total = 0

    for tid in TRACK_IDS:
        bundle = tm.ensure(tid)
        wk: WeekManager = bundle.week

        raw = getattr(wk.state, "closed_buckets", None)
        if isinstance(raw, dict):
            for k in list(raw.keys()):
                n = int(_safe_float(raw[k], 0))
                k_lower = str(k).lower()
                if "week_cap+400" in k_lower or "+400" in k_lower:
                    counts["+400"] += n
                elif "week_cap+300" in k_lower or "+300" in k_lower:
                    counts["+300"] += n
                elif "small_green" in k_lower or "+160" in k_lower:
                    counts["+160"] += n
                elif "red_stabilizer" in k_lower or "-85" in k_lower:
                    counts["-85"] += n
                elif "week_guard-400" in k_lower or "-400" in k_lower:
                    counts["+400"] += 0  # keep structure consistent
                    counts["-400"] += n

        closed_total += int(_safe_float(getattr(wk.state, "closed_weeks_count", 0)))

    s = sum(counts.values())
    if closed_total == 0 and s > 0:
        closed_total = s

    return counts, closed_total

COUNTS, CLOSED_WEEKS = _closed_weeks_stats()

def _avg_weekly_units(counts: dict, total_closed: int) -> float:
    if total_closed <= 0:
        return 0.0
    weights = {
        "+400": 400.0,
        "+300": 300.0,
        "+160": 160.0,
        "-85": -85.0,
        "-400": -400.0,
    }
    num = sum(float(counts.get(k, 0)) * w for k, w in weights.items())
    return num / float(total_closed)

AVG_WEEKLY_U = _avg_weekly_units(COUNTS, CLOSED_WEEKS)

def _pct_or_zero(n, d):
    if d <= 0:
        return "0.00%"
    return f"{(100.0 * float(n) / float(d)):.2f}%"

def _distribution_deviation_pp(expected_list, counts_dict, total_closed):
    if total_closed <= 0:
        return 0.0
    s = 0.0
    for label, ex in expected_list:
        act = 100.0 * float(counts_dict.get(label, 0)) / float(total_closed)
        s += abs(act - ex)
    return round(s, 2)

# ---------- HEADER ----------
st.title("Overview")

# ---------- HERO SECTION ----------
c1, c2, c3 = st.columns(3)
with c1:
    st.markdown(
        "<div class='hero-card'><div class='hero-title'>All-time P/L</div>"
        f"<div class='hero-value'>{_fmt_u_d(ALL_U, ALL_D)}</div></div>",
        unsafe_allow_html=True,
    )
with c2:
    st.markdown(
        "<div class='hero-card'><div class='hero-title'>This Month</div>"
        f"<div class='hero-value'>{_fmt_u_d(MONTH_U, MONTH_D)}</div></div>",
        unsafe_allow_html=True,
    )
with c3:
    st.markdown(
        "<div class='hero-card'><div class='hero-title'>This Week</div>"
        f"<div class='hero-value'>{_fmt_u_d(WEEK_U, WEEK_D)}</div></div>",
        unsafe_allow_html=True,
    )

st.caption(
    "All-time / Month / Week here use calendar ranges from your DB history "
    "(Week = Monday–Sunday, PST, across all tracks). "
    "On the Tracker page, Week P/L follows your strategy week (#1, #2, etc.), "
    "so those 'week' numbers will differ."
)

st.markdown(
    "<div class='hero-card'>"
    "<div class='hero-title'>Average units / week (closed weeks)</div>"
    f"<div class='hero-value'>{('+' if AVG_WEEKLY_U >= 0 else '')}{AVG_WEEKLY_U:.2f}u</div>"
    "</div>",
    unsafe_allow_html=True,
)
st.caption(
    "Average gain per closed week. The +233u/week target is the modeled long-term expectation for full cadence "
    "performance (+6 sessions/day, 2 lines/session)."
)

# ---------- TODAY AT A GLANCE ----------
st.markdown("### Today at a Glance")

_sync_today_pacing()

# Global totals (already summed across tracks in _hydrate_daily_counters_from_db)
nb_used = int(st.session_state.get("sessions_today", 0))
lod_used = int(st.session_state.get("lines_in_session", 0))

# How many tracks are we actually running?
track_count = len(TRACK_IDS) or 1

lod_cap_per_track = 2  # always 2 lines/session per track

# Global nb max = sum of per-track caps
nb_max_global = 0
for tid in TRACK_IDS:
    bundle = tm.ensure(tid)
    wk: WeekManager = bundle.week
    try:
        is_fast = bool(wk.is_fast_test())
    except Exception:
        is_fast = False
    nb_max_global += (2 if is_fast else 6)

# Global LOD max still scales with track count
lod_max_global = lod_cap_per_track * track_count

# Backwards-compat
nb_max = nb_max_global
lod_max = lod_max_global

gl1, gl2, gl3 = st.columns([1.1, 1.3, 1.2])
with gl1:
    st.markdown(
        f"<div class='pill'>Sessions today (all tracks): "
        f"<b>{nb_used}</b> / {nb_max_global}</div>",
        unsafe_allow_html=True,
    )

with gl2:
    st.markdown(
        f"<div class='pill'>Lines this session (all tracks): "
        f"<b>{lod_used}</b> / {lod_max_global}</div>",
        unsafe_allow_html=True,
    )

with gl3:
    st.markdown(
        f"<div class='pill'>Midnight reset in <b>{_midnight_countdown()}</b></div>",
        unsafe_allow_html=True,
    )

st.caption(
    "nb = sessions per day, LOD = lines per session. These caps are global and scale with your number of tracks "
    f"(currently {track_count} track{'s' if track_count != 1 else ''}). "
    f"Per-track caps: 6 sessions/day and {lod_cap_per_track} lines/session. "
    "Our engine and model is based on respecting these global pacing limits."
)

# ---------- WEEKLY OUTLOOK ----------
st.markdown("### Weekly Outlook — Expected vs Actual")
st.caption(
    "Each closed week falls into one of five outcomes. Expected % are model odds; Actual % is your historical distribution."
)

st.markdown(
    "<div class='table-wrap'>"
    "<div class='table-hdr'>"
    "<div class='cell dim'>Outcome</div>"
    "<div class='cell dim'>Expected %</div>"
    "<div class='cell dim'>Actual %</div>"
    "<div class='cell dim'>Count</div>"
    "</div>",
    unsafe_allow_html=True,
)
rows = []
for label, exp in EXPECTED:
    cnt = int(COUNTS.get(label, 0))
    act = _pct_or_zero(cnt, CLOSED_WEEKS)
    desc = {
        "+400": "+400 units (Primary cap)",
        "+300": "+300 units (Optimizer cap)",
        "+160": "+160 units (Small green lock)",
        "-85": "-85 units (Red stabilizer)",
        "-400": "-400 units (Weekly guard)",
    }[label]
    rows.append(
        f"<div class='table-row'>"
        f"<div class='cell'>{desc}</div>"
        f"<div class='cell mono'>{exp:.2f}%</div>"
        f"<div class='cell mono'>{act}</div>"
        f"<div class='cell mono'>{cnt}</div>"
        f"</div>"
    )
st.markdown("".join(rows) + "</div>", unsafe_allow_html=True)

if CLOSED_WEEKS > 0:
    dev = _distribution_deviation_pp(EXPECTED, COUNTS, CLOSED_WEEKS)

    # Interpret drift for human-friendly context
    if dev < 20:
        drift_note = "Very aligned — results closely match the model."
    elif dev < 50:
        drift_note = "Normal variance — still within expected randomness."
    else:
        drift_note = "High drift — usually caused by small sample size or execution inconsistency."

    st.markdown(
        "<div class='hero-card' style='margin-top:12px;'>"
        "<div class='hero-title'>Model Drift (%)</div>"
        f"<div class='hero-value'>{dev:.1f}%</div>"
        "<div class='kicker'>"
        "Total difference between expected outcomes and your actual results. "
        "Lower is better."
        "</div>"
        f"<div class='kicker' style='margin-top:4px'>{drift_note}</div>"
        "<div class='kicker' style='margin-top:6px;color:#6b7280'>"
        "Note: Drift naturally stabilizes as more weeks are logged (≈20+ closed weeks)."
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )
else:
    st.caption(
        "Once you’ve closed at least one week, we’ll show your Model Drift — "
        "how closely your results align with the expected odds."
    )
st.divider()

# ---------- TRACKS SNAPSHOT ----------
st.markdown("### Tracks Snapshot")
st.caption("Live status per track—tone, performance, next bet, and pacing.")

st.markdown(
    "<div class='snap-table'>"
    "<div class='snap-hdr'>"
    "<div class='cell dim'>Track</div>"
    "<div class='cell dim'>Tone</div>"
    "<div class='cell dim'>Week P/L</div>"
    "<div class='cell dim'>Session P/L</div>"
    "<div class='cell dim'>Line P/L</div>"
    "<div class='cell dim'>Next Bet</div>"
    "<div class='cell dim'>nb / LOD</div>"
    "</div>",
    unsafe_allow_html=True,
)

snap_rows = []
for tid in TRACK_IDS:
    bundle = tm.ensure(tid)
    eng: DiamondHybrid = bundle.eng
    wk: WeekManager = bundle.week

    track_name = TRACK_LABELS.get(tid, str(tid))

    # --- Pull raw week state from Supabase if available ---
    raw_state = TRACK_STATES_RAW.get(tid) or {}
    if not raw_state:
        # last-resort refresh (fixes cold-load zeros)
        raw_state = _load_state(user_db_id, tid) or {}
        TRACK_STATES_RAW[tid] = raw_state

    # --- IMPORTANT: hydrate bundle so Snapshot doesn't depend on visiting Tracker ---
    if raw_state and not getattr(bundle, "_db_loaded", False):
        try:
            bundle.load_state(raw_state)
            bundle._db_loaded = True
        except Exception:
            pass

    try:
        is_fast_track = bool(wk.is_fast_test())
    except Exception:
        is_fast_track = False

    nb_cap_track = 2 if is_fast_track else 6
    lod_cap_track = 2

    # --- Week P/L (LIVE) + Tone (LIVE) ---
    # Get booked P/L with accurate historical dollars from DB
    week_number = int(getattr(wk.state, "week_number", 1) or 1)
    booked_data = get_week_pl_booked(user_db_id, tid, week_number)
    booked_units = float(booked_data.get("units", 0.0) or 0.0)
    booked_dollars = float(booked_data.get("dollars", 0.0) or 0.0)

    # Live session (in-progress, not yet booked) uses current unit_value
    live_session_units = _pick_state_num(
        raw_state,
        "session_pl_units", "session_pl",
        default=_safe_float(getattr(eng, "session_pl_units", 0.0)),
    )
    live_session_dollars = live_session_units * unit_value

    # Combined week P/L
    week_pl_units = booked_units + live_session_units
    week_pl_dollars = booked_dollars + live_session_dollars

    try:
        tone = wk.current_tone(live_session_pl=live_session_units)
    except TypeError:
        tone = wk.current_tone()
    except Exception:
        tone = {"tone": "neutral", "defensive": False}

    tone_name = str(tone.get("tone", tone.get("name", "neutral"))).lower()
    tone_dot = {"green": "#22c55e", "red": "#ef4444"}.get(tone_name, "#9ca3af")

    # Soft Shield badge
    soft_shield_on = bool(tone.get("soft_shield", False))
    ss_badge = "<span class='badge-yellow' style='margin-left:4px;font-size:.65rem'>⚠️ SS</span>" if soft_shield_on else ""

    # Line P/L and Next Bet for display
    line_pl = _pick_state_num(raw_state, "line_pl_units", "line_pl", default=_safe_float(getattr(eng, "line_pl_units", 0.0)))
    next_u = _safe_float(
        eng.next_bet_units() if hasattr(eng, "next_bet_units") else 0.0
    )

    # nb / LOD – per track from track_state snapshot
    nb_used_r = int((raw_state or {}).get("sessions_today", 0) or 0)
    lod_used_r = int((raw_state or {}).get("lines_in_session", 0) or 0)

    snap_rows.append(
        f"<div class='snap-row'>"
        f"<div class='cell'>{track_name}</div>"
        f"<div class='cell'><span style='display:inline-flex;align-items:center;gap:6px;'>"
        f"<span style='width:8px;height:8px;border-radius:999px;background:{tone_dot};display:inline-block'></span>"
        f"{tone_name}{ss_badge}</span></div>"
        f"<div class='cell mono'>{_fmt_u_d_precomputed(week_pl_units, week_pl_dollars)}</div>"
        f"<div class='cell mono'>{_fmt_u_d_live(live_session_units, unit_value)}</div>"
        f"<div class='cell mono'>{_fmt_u_d_live(line_pl, unit_value)}</div>"
        f"<div class='cell mono'>{next_u:.2f}u (${next_u * unit_value:,.2f})</div>"
        f"<div class='cell mono'>{nb_used_r}/{nb_cap_track} · {lod_used_r}/{lod_cap_track}</div>"
        f"</div>"
    )

st.markdown("".join(snap_rows) + "</div>", unsafe_allow_html=True)

# ---------- SUMMARY PANELS ----------
def _live_week_total_for_track(tid: str) -> tuple[float, float]:
    """Returns (units, dollars) for this track's current week."""
    bundle = tm.ensure(tid)
    wk: WeekManager = bundle.week
    eng: DiamondHybrid = bundle.eng

    # Booked P/L with accurate historical dollars
    week_number = int(getattr(wk.state, "week_number", 1) or 1)
    booked_data = get_week_pl_booked(user_db_id, str(tid), week_number)
    booked_units = float(booked_data.get("units", 0.0) or 0.0)
    booked_dollars = float(booked_data.get("dollars", 0.0) or 0.0)

    # Live session uses current unit_value
    raw = TRACK_STATES_RAW.get(str(tid)) or {}
    live_session_units = _pick_state_num(
        raw,
        "session_pl_units", "session_pl",
        default=_safe_float(getattr(eng, "session_pl_units", 0.0)),
    )
    live_session_dollars = live_session_units * unit_value

    return (booked_units + live_session_units, booked_dollars + live_session_dollars)

scores = []
for tid in TRACK_IDS:
    units, dollars = _live_week_total_for_track(tid)
    scores.append((tid, units, dollars))
scores.sort(key=lambda x: x[1], reverse=True)  # Sort by units
best = scores[0] if scores else None
worst = scores[-1] if scores else None

cA, cB = st.columns(2)
with cA:
    st.markdown(
        "<div class='hero-card'><div class='hero-title'>Top Performer (Week)</div>",
        unsafe_allow_html=True,
    )
    if best:
        tid, units, dollars = best
        name = TRACK_LABELS.get(tid, str(tid))
        st.markdown(
            f"<div class='hero-value'>{name} · {_fmt_u_d_precomputed(units, dollars)}</div>",
            unsafe_allow_html=True,
        )
        st.caption("Highest current week performance (booked + live session) across all tracks.")
    else:
        st.caption("No tracks yet.")
    st.markdown("</div>", unsafe_allow_html=True)

with cB:
    st.markdown(
        "<div class='hero-card'><div class='hero-title'>Needs Attention</div>",
        unsafe_allow_html=True,
    )
    if worst:
        tid, units, dollars = worst
        name = TRACK_LABELS.get(tid, str(tid))
        st.markdown(
            f"<div class='hero-value'>{name} · {_fmt_u_d_precomputed(units, dollars)}</div>",
            unsafe_allow_html=True,
        )
        st.caption("Lowest current week performance—watch tone/fragility before taking entries.")
    else:
        st.caption("No tracks yet.")
    st.markdown("</div>", unsafe_allow_html=True)

# ---------- FRAGILITY PULSE ----------
frag_scores: list[float] = []
choppy_count = 0
tracked = 0

for tid in TRACK_IDS:
    tid = str(tid)
    if tid not in TRACK_LABELS:
        continue

    bundle = tm.ensure(tid)
    eng: DiamondHybrid = bundle.eng

    try:
        raw = eng._fused_fragility_score()

        # Same pattern as before: support (score, meta) or plain score
        if isinstance(raw, (tuple, list)) and len(raw) > 0:
            score = float(raw[0])
        else:
            score = float(raw)

        frag_scores.append(score)
        tracked += 1

        # Define "choppy" purely from frag score
        if score >= 0.55:
            choppy_count += 1

    except Exception as e:
        print(f"[overview] fragility pulse error for {tid}: {e!r}")
        continue

avg_frag = (sum(frag_scores) / tracked) if tracked > 0 else 0.0
choppy_pct = (100.0 * choppy_count / tracked) if tracked > 0 else 0.0

st.markdown(
    "<div class='hero-card'><div class='hero-title'>Fragility Pulse</div>"
    f"<div class='hero-value'>{avg_frag:.2f}</div>"
    f"<div class='kicker'>Choppy: {choppy_pct:.1f}% of tracks "
    "(fragility score ≥ 0.55)</div></div>",
    unsafe_allow_html=True,
)
st.caption(
    "Each track has a fused fragility score based on recent lines and sessions. "
    "A track is counted as 'choppy' when its fragility score is at or above 0.55. "
    "If this stays at 0%, all active tracks are currently in the calm zone."
)

# ---------- CURRENT STREAKS ----------
st.markdown(
    "<div class='hero-card'><div class='hero-title'>Current Streaks</div>",
    unsafe_allow_html=True,
)
if scores:
    for tid, _units, _dollars in scores:
        name = TRACK_LABELS.get(tid, str(tid))
        bundle = tm.ensure(tid)
        eng: DiamondHybrid = bundle.eng
        streak = getattr(eng, "streak_label", lambda: "—")()
        st.markdown(f"- **{name}**: {streak}")
else:
    st.markdown("No tracks yet.")
st.markdown("</div>", unsafe_allow_html=True)
st.caption(
    "Quick glance at wins/losses momentum per track (informational only; strategy remains rule-based)."
)
