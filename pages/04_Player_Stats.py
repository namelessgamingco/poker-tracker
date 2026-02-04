# pages/04_Player_Stats.py — Player Pulse + Analytics (DB-backed)
# UPDATED: Two-tab layout - "All Tracks" aggregate + "Per Track" detailed view

import streamlit as st
st.set_page_config(page_title="Player Stats", page_icon="🧠", layout="wide")

from auth import require_auth
user = require_auth()

from db import get_profile_by_auth_id
from cache import (
    get_cached_tracks,
    get_cached_track_state,
)

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
        auth_id = "unknown_auth_id"
    if not email:
        email = "unknown@example.com"

    return str(auth_id), str(email)

auth_id, email = _extract_auth_identity(user)

try:
    profile = get_profile_by_auth_id(auth_id) or {}
except Exception as e:
    print(f"[player_stats] get_profile_by_auth_id error: {e!r}")
    st.error("DB error loading profile. Try again in a moment.")
    st.stop()

user_db_id = str(profile.get("user_id") or "")

if not user_db_id:
    if not st.session_state.get("_profile_retry", False):
        st.session_state["_profile_retry"] = True
        st.rerun()

    st.error("Profile not found for this account. Please refresh.")
    st.stop()

# Load user-specific unit_value from DB
if st.session_state.get("_unit_value_user") != user_db_id:
    try:
        from db import get_user_unit_value
        st.session_state.unit_value = get_user_unit_value(user_db_id)
        st.session_state._unit_value_user = user_db_id
    except Exception as e:
        print(f"[player_stats] unit_value load error: {e!r}")

st.session_state["user_db_id"] = user_db_id

user_id = user_db_id

from datetime import datetime, timedelta, time
from math import isfinite
from statistics import mean, pstdev

from track_manager import TrackManager
from week_manager import WeekManager
from engine import DiamondHybrid
from sidebar import render_sidebar

# --- DB + helpers ---
try:
    from db import (
        get_or_create_user,
        get_tracks_for_user,
        load_track_state,
        ensure_track_state,
        fetch_track_events,
    )
    from supabase_client import get_supabase
    supabase = get_supabase()

except Exception:
    def get_or_create_user(auth_id: str, email: str):
        return {"user_id": auth_id, "email": email}

    def get_tracks_for_user(user_id: str):
        return []

    def load_track_state(*args, **kwargs):
        return {}
    
    def ensure_track_state(user_id: str, track_id: str) -> None:
        return None

    def fetch_track_events(user_id: str, track_id: str, limit: int = 50):
        return []

    supabase = None

def _load_state(user_id: str, track_id: str) -> dict:
    if not track_id or not user_id:
        return {}
    return get_cached_track_state(str(user_id), str(track_id), load_track_state)

def _backfill_track_state_rows(user_id: str) -> None:
    if not user_id:
        return
    if st.session_state.get("_track_state_backfilled_player_stats", False):
        return

    try:
        tracks = get_cached_tracks(user_id, get_tracks_for_user) or []
        for t in tracks:
            tid = str(t.get("id") or "")
            if tid:
                try:
                    ensure_track_state(user_id, tid)
                except Exception as e:
                    print(f"[player_stats] ensure_track_state failed tid={tid}: {e!r}")
        st.session_state["_track_state_backfilled_player_stats"] = True
    except Exception as e:
        print(f"[player_stats] backfill track_state rows error: {e!r}")

render_sidebar()

# ---------- Styles ----------
st.markdown("""
<style>
.hero-card{border:1px solid #1f1f1f;background:linear-gradient(180deg,#0e0e0f,#121214);
  border-radius:14px;padding:14px 16px;margin-bottom:12px}
.hero-title{color:#9ca3af;font-size:.9rem;margin-bottom:6px}
.hero-value{font-size:1.25rem;font-weight:800;color:#e5e7eb}
.kicker{color:#9ca3af;font-size:.82rem}
.pill{display:inline-flex;align-items:center;gap:8px;border:1px solid #2a2a2a;
  background:#121212;color:#d1d5db;border-radius:999px;padding:6px 10px;font-size:.85rem}

.section{margin-top:10px;margin-bottom:4px;color:#d1d5db}
.title{font-size:1.05rem;font-weight:800;color:#e5e7eb;margin:10px 0 8px 0}
.dim{color:#9ca3af}
.mono{font-variant-numeric: tabular-nums}

.table-wrap{border:1px solid #202020;border-radius:12px;overflow:hidden}
.table-hdr{display:grid;grid-template-columns:1.6fr .9fr 1fr .9fr;
  padding:10px 12px;border-bottom:1px solid #232323;background:#121214}
.table-row{display:grid;grid-template-columns:1.6fr .9fr 1fr .9fr;
  padding:8px 12px;border-bottom:1px solid #171717}
.table-row:last-child{border-bottom:none}
.cell{color:#e5e7eb}
.cell.dim{color:#9ca3af}

.badge-yellow {
  display:inline-block;padding:2px 10px;font-size:.72rem;border-radius:999px;
  border:1px solid #6f6428;color:#f2e6a5;background:linear-gradient(180deg,#2a280f,#1e1d0c);
  margin-left:8px;vertical-align:middle;box-shadow:0 2px 10px rgba(0,0,0,.25);
}
.badge-yellow.off { opacity:.45; filter: grayscale(25%); }
.badge {
  display:inline-block;padding:2px 8px;font-size:.72rem;border-radius:999px;border:1px solid #2b2b2b;
  color:#cfcfcf;background:#101010;margin-left:8px;vertical-align:middle;
}

.momentum{display:flex;gap:6px;flex-wrap:wrap}
.mom-chip{width:18px;height:18px;border-radius:4px;border:1px solid #2b2b2b;background:#151515}
.mom-W{background:#14532d;border-color:#14532d}
.mom-L{background:#7f1d1d;border-color:#7f1d1d}
.mom-T{background:#3f3f46;border-color:#3f3f46}

.flow-row{display:flex;gap:10px;flex-wrap:wrap}
.flow-pill{border:1px solid #2b2b2b;background:#0f0f0f;color:#e5e5e5;border-radius:12px;padding:8px 10px}
.flow-pill .l{font-size:.78rem;color:#a5a5a5;margin-right:6px}
.flow-pill.good{border-color:#1f5131;background:#0c1510}
.flow-pill.mid{border-color:#2b2b2b}
.flow-pill.bad{border-color:#5b1f22;background:#140c0d}

.card{border:1px solid #2b2b2b;border-radius:14px;padding:16px 18px;
      background:linear-gradient(135deg,#0f0f0f,#171717);color:#eaeaea;margin:10px 0 18px 0;}
.sub{color:#9ca3af;font-size:.90rem;margin-top:4px;margin-bottom:10px}

/* Track summary table for All Tracks view */
.track-summary-table{border:1px solid #202020;border-radius:12px;overflow:hidden;margin:12px 0}
.track-summary-hdr{display:grid;grid-template-columns:1.5fr 1fr 1fr 1fr 1fr;
  padding:10px 12px;border-bottom:1px solid #232323;background:#121214;font-size:.85rem;color:#9ca3af}
.track-summary-row{display:grid;grid-template-columns:1.5fr 1fr 1fr 1fr 1fr;
  padding:10px 12px;border-bottom:1px solid #171717}
.track-summary-row:last-child{border-bottom:none}
</style>
""", unsafe_allow_html=True)

try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo("America/Los_Angeles")
except Exception:
    _TZ = None

# ---------- Basic utils ----------
def _safe_float(x, default=0.0):
    try:
        f = float(x)
        return f if isfinite(f) else default
    except Exception:
        return default

def _until_next_reset_hms() -> str:
    now = datetime.now(_TZ) if _TZ else datetime.now()
    tomorrow = (now + timedelta(days=1)).date()
    mid = datetime.combine(tomorrow, time(0,0,0), tzinfo=getattr(now, "tzinfo", None))
    rem = max(0, int((mid - now).total_seconds()))
    h = rem // 3600; m = (rem % 3600) // 60; s = rem % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

def last_n(lst, n):
    return lst[-n:] if len(lst) >= n else lst[:]

# ---------- Session / Managers ----------
if "unit_value" not in st.session_state:
    st.session_state.unit_value = 1.0
if "testing_mode" not in st.session_state:
    st.session_state.testing_mode = False
if "tm" not in st.session_state:
    st.session_state.tm = TrackManager(unit_value=float(st.session_state.unit_value))

tm: TrackManager = st.session_state.tm

def _ensure_tracks_for_stats(user_db_id: str):
    """
    Ensure TrackManager has bundles for all DB tracks.
    
    CRITICAL: Do NOT call import_state here — that would overwrite any unsaved
    live state from the Tracker. The Tracker page is the source of truth for
    in-memory state. Player Stats should only READ from DB for historical data
    and use the existing in-memory bundle state for live tone/defensive display.
    
    This function only ensures bundles EXIST, it does not hydrate them.
    Hydration happens on the Tracker page when bundles are first loaded.
    """
    if not user_db_id:
        if not tm.all_ids():
            tm.ensure("Track 1")
        return

    try:
        db_tracks = get_cached_tracks(user_db_id, get_tracks_for_user) or []
    except Exception as e:
        print(f"[player_stats] get_tracks_for_user error: {e!r}")
        db_tracks = []

    if db_tracks:
        for t in db_tracks:
            tid = str(t.get("id"))
            # Just ensure the bundle exists — do NOT import state here
            # The bundle may already have live unsaved state from Tracker
            bundle = tm.ensure(tid)
            
            # Only hydrate from DB if this bundle has NEVER been loaded
            # (i.e., fresh app session where Tracker hasn't been visited yet)
            if not getattr(bundle, "_db_loaded", False):
                try:
                    state = _load_state(user_db_id, tid)
                except Exception as e:
                    print(f"[player_stats] load_track_state error for {tid}: {e!r}")
                    state = {}

                if state:
                    if hasattr(bundle, "import_state") and callable(getattr(bundle, "import_state")):
                        try:
                            bundle.import_state(state)
                        except Exception as e:
                            print(f"[player_stats] bundle.import_state error for {tid}: {e!r}")
                    else:
                        # Fallback: hydrate engine and week separately
                        eng_state = (
                            state.get("engine")
                            or state.get("eng")
                            or state.get("engine_state")
                            or state.get("engine_state_json")
                        )
                        if isinstance(eng_state, dict) and hasattr(bundle, "eng"):
                            try:
                                if hasattr(bundle.eng, "import_state"):
                                    bundle.eng.import_state(eng_state)
                                elif hasattr(bundle.eng, "load_state"):
                                    bundle.eng.load_state(eng_state)
                            except Exception as e:
                                print(f"[player_stats] engine import error for {tid}: {e!r}")

                        wk_state = (
                            state.get("week")
                            or state.get("week_state")
                            or state.get("week_state_json")
                        )
                        if isinstance(wk_state, dict) and hasattr(bundle, "week"):
                            try:
                                if hasattr(bundle.week, "import_state"):
                                    bundle.week.import_state(wk_state)
                                elif hasattr(bundle.week, "load_state"):
                                    bundle.week.load_state(wk_state)
                            except Exception as e:
                                print(f"[player_stats] week import error for {tid}: {e!r}")

                # Mark as loaded so we don't re-import on future visits
                try:
                    bundle._db_loaded = True
                except Exception:
                    pass
    else:
        if not tm.all_ids():
            tm.ensure("Track 1")


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
            tid = str(t.get("id"))
            state = _load_state(user_db_id, tid)
            total_nb += int(state.get("sessions_today", 0) or 0)
            total_lod += int(state.get("lines_in_session", 0) or 0)

        st.session_state["sessions_today"] = total_nb
        st.session_state["lines_in_session"] = total_lod

    except Exception as e:
        print(f"[player_stats] hydrate daily counters error: {e!r}")


def _build_track_labels_for_stats(user_db_id: str) -> dict[str, str]:
    labels: dict[str, str] = {}

    if not user_db_id:
        if not tm.all_ids():
            tm.ensure("Track 1")
        for idx, tid in enumerate(tm.all_ids(), start=1):
            labels[tid] = f"Track {idx}"
        return labels

    try:
        db_tracks = get_cached_tracks(user_db_id, get_tracks_for_user) or []
    except Exception as e:
        print(f"[player_stats] _build_track_labels_for_stats error: {e!r}")
        db_tracks = []

    if db_tracks:
        for idx, t in enumerate(db_tracks, start=1):
            tid = str(t.get("id"))
            label = t.get("track_label") or f"Track {idx}"
            labels[tid] = label
    else:
        if not tm.all_ids():
            tm.ensure("Track 1")
        for idx, tid in enumerate(tm.all_ids(), start=1):
            labels[tid] = f"Track {idx}"

    return labels


def _get_track_cadence(user_db_id: str, track_id: str) -> tuple[int, int]:
    if supabase is None or not track_id:
        nb = int(st.session_state.get("sessions_today", 0) or 0)
        lod = int(st.session_state.get("lines_in_session", 0) or 0)
        return nb, lod

    nb = 0
    lod = 0

    try:
        state = _load_state(user_db_id, track_id)
        nb = int(state.get("sessions_today", 0) or 0)
        lod = int(state.get("lines_in_session", 0) or 0)
    except Exception as e:
        print(f"[player_stats] _get_track_cadence load_state error for {track_id}: {e!r}")
        nb = int(st.session_state.get("sessions_today", 0) or 0)
        lod = int(st.session_state.get("lines_in_session", 0) or 0)

    return nb, lod


# --- Run hydration ---
_ensure_tracks_for_stats(user_id)
_backfill_track_state_rows(user_id)
_hydrate_daily_counters_from_db(user_id)
TRACK_LABELS = _build_track_labels_for_stats(user_id)

# ---------- DB fetch helpers ----------
def _fetch_sessions(user_id: str, track_id: str = None):
    """Session results for this user (optionally filtered by track)."""
    if supabase is None or not user_id:
        return []
    try:
        query = (
            supabase.table("session_results")
            .select("track_id, session_pl_units, unit_value, end_reason, duration_sec, created_at")
            .eq("user_id", user_id)
            .eq("is_test", False)
            .order("created_at", desc=False)
            .limit(500)
        )
        if track_id:
            query = query.eq("track_id", track_id)
        resp = query.execute()
        rows = resp.data or []
    except Exception as e:
        print(f"[player_stats] _fetch_sessions error: {e!r}")
        rows = []
    return [
        {
            "track_id": r.get("track_id"),
            "ts": r.get("created_at"),
            "pl_units": _safe_float(r.get("session_pl_units", 0)),
            "unit_value": _safe_float(r.get("unit_value", 1.0)) or 1.0,
            "end_reason": r.get("end_reason") or "",
            "duration_sec": r.get("duration_sec"),
        }
        for r in rows
    ]

def _fetch_hands(user_id: str, track_id: str = None):
    """Raw hand outcomes for this user (optionally filtered by track)."""
    if supabase is None or not user_id:
        return []
    try:
        query = (
            supabase.table("hand_outcomes")
            .select("track_id, outcome, delta_units, unit_value, ts, created_at, is_test")
            .eq("user_id", user_id)
            .eq("is_test", False)
            .order("ts", desc=False)
            .limit(2000)
        )
        if track_id:
            query = query.eq("track_id", track_id)
        resp = query.execute()
        rows = resp.data or []
    except Exception as e:
        print(f"[player_stats] _fetch_hands error: {e!r}")
        rows = []
    def _ts(r):
        return r.get("ts") or r.get("created_at")
    return [
        {
            "track_id": r.get("track_id"),
            "outcome": r.get("outcome"),
            "delta_units": _safe_float(r.get("delta_units", 0)),
            "unit_value": _safe_float(r.get("unit_value", 1.0)) or 1.0,
            "ts": _ts(r),
        }
        for r in rows
    ]

def _fetch_events(user_id: str, track_id: str = None):
    """Line-level events."""
    if supabase is None or not user_id:
        return []
    try:
        query = (
            supabase.table("line_events")
            .select("track_id, reason, line_duration_sec, created_at")
            .eq("user_id", user_id)
            .eq("is_test", False)  # Only count live events
            .order("created_at", desc=False)
            .limit(500)
        )
        if track_id:
            query = query.eq("track_id", track_id)
        resp = query.execute()
        rows = resp.data or []
    except Exception as e:
        print(f"[player_stats] _fetch_events error: {e!r}")
        rows = []
    return [
        {
            "track_id": r.get("track_id"),
            "reason": r.get("reason"),
            "line_duration_sec": r.get("line_duration_sec"),
            "ts": r.get("created_at"),
        }
        for r in rows
    ]

def _count_week_caps(user_id: str, track_id: str = None) -> int:
    if supabase is None or not user_id:
        return 0
    try:
        query = (
            supabase.table("week_closures")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .eq("is_test", False)
            .eq("outcome_bucket", "week_cap+400")
        )
        if track_id:
            query = query.eq("track_id", track_id)
        resp = query.execute()
        return int(resp.count or 0)
    except Exception as e:
        print(f"[player_stats] _count_week_caps error: {e!r}")
        return 0

# ---------- Analytics helpers ----------
def _equity_from_sessions(rows):
    eq = []
    total_u = 0.0
    total_d = 0.0
    for r in rows:
        u = _safe_float(r.get("pl_units"), 0.0)
        uv = _safe_float(r.get("unit_value", 1.0)) or 1.0
        total_u += u
        total_d += u * uv
        eq.append({
            "ts": r.get("ts", ""),
            "equity_u": total_u,
            "equity_d": total_d,
        })
    return eq

def _drawdown_series(equity_rows):
    dd = []
    peak = 0.0
    for r in equity_rows:
        e = _safe_float(r.get("equity_u", 0.0))
        peak = max(peak, e)
        dd.append({
            "ts": r.get("ts", ""),
            "drawdown_u": e - peak
        })
    return dd

def _flow_breakdown(session_rows):
    g = n = r = 0
    for s in session_rows:
        pl = _safe_float(s.get("pl_units"), 0.0)
        reason = (s.get("end_reason","") or "").lower()
        if (reason in {"session_goal","profit_preserve"}) and pl > 0:
            g += 1
        elif (reason in {"session_stop"}) or pl < 0:
            r += 1
        else:
            n += 1
    total = max(1, g+n+r)
    return g/total, n/total, r/total

def _market_feel_from_db(hands_log, sessions_log):
    if not hands_log and not sessions_log:
        return ("—", None)

    deltas = [_safe_float(h.get("delta_units"), 0.0) for h in last_n(hands_log, 20)]
    if len(deltas) >= 6:
        sd = pstdev(deltas) if len(deltas) > 1 else 0.0
        score = min(1.0, sd / 5.0)
    else:
        tail = last_n(sessions_log, 10)
        reds = sum(1 for s in tail if _safe_float(s.get("pl_units"), 0.0) < 0)
        score = reds / max(1, len(tail))

    label = "Choppy" if score >= 0.55 else "Stable"
    return (label, float(score))

# ---------- Player Pulse helpers ----------
def _win_rate_and_quality(hands_log):
    if not hands_log:
        return 0.0, 0.0, 0.0, 0, 0
    wins = [h for h in hands_log if h.get("outcome") == "W"]
    losses = [h for h in hands_log if h.get("outcome") == "L"]
    wr = (len(wins) / max(1, (len(wins)+len(losses)))) * 100.0
    avg_win = mean([_safe_float(h.get("delta_units"), 0.0) for h in wins]) if wins else 0.0
    avg_loss = mean([_safe_float(h.get("delta_units"), 0.0) for h in losses]) if losses else 0.0
    longest_w, longest_l = 0, 0
    cur_w, cur_l = 0, 0
    for h in hands_log:
        o = h.get("outcome")
        if o == "W":
            cur_w += 1; longest_w = max(longest_w, cur_w); cur_l = 0
        elif o == "L":
            cur_l += 1; longest_l = max(longest_l, cur_l); cur_w = 0
        else:
            cur_w = 0; cur_l = 0
    return wr, avg_win, avg_loss, longest_w, longest_l

def _consistency(sessions_log, lookback=10):
    if not sessions_log:
        return 0.0, 0.0, []
    tail = last_n(sessions_log, lookback)
    vals = [_safe_float(s.get("pl_units"), 0.0) for s in tail]
    avg = mean(vals) if vals else 0.0
    sd  = pstdev(vals) if len(vals) > 1 else 0.0
    return avg, sd, vals

def _momentum_chips(hands_log, lookback=10):
    tail = last_n(hands_log, lookback)
    chips = []
    for h in tail:
        o = h.get("outcome")
        if o == "W":
            chips.append(("W", "mom-W", "🟩"))
        elif o == "L":
            chips.append(("L", "mom-L", "🟥"))
        else:
            chips.append(("T", "mom-T", "🟨"))
    return chips

def _auto_caption(hands_log):
    tail = last_n(hands_log, 5)
    score = sum(1 if h.get("outcome") == "W" else (-1 if h.get("outcome") == "L" else 0) for h in tail)
    if score >= 3:  return "🔥 Heating up"
    if score <= -3: return "🧊 Cooling off"
    return "↔️ Steady"

def _behavioral(sessions_log, events_log):
    from statistics import mean as _mean

    total_sessions = len(sessions_log)

    sess_durations = []
    for s in sessions_log:
        d = s.get("duration_sec")
        try:
            d = float(d)
            if d > 0:
                sess_durations.append(d)
        except Exception:
            continue
    avg_session_min = (_mean(sess_durations) / 60.0) if sess_durations else 0.0

    line_durations = []
    for e in events_log:
        d = e.get("line_duration_sec")
        try:
            d = float(d)
            if d > 0:
                line_durations.append(d)
        except Exception:
            continue
    avg_line_min = (_mean(line_durations) / 60.0) if line_durations else 0.0

    return total_sessions, avg_line_min, avg_session_min

def _tier_badge(sessions_log, hands_log, week_caps: int):
    lifetime_u = sum(_safe_float(s.get("pl_units"), 0.0) for s in sessions_log) if sessions_log else 0.0
    lifetime_d = sum(
        _safe_float(s.get("pl_units"), 0.0) * (_safe_float(s.get("unit_value", 1.0)) or 1.0)
        for s in sessions_log
    ) if sessions_log else 0.0
    
    tiers = [
        {"name": "Apprentice",    "emoji": "🌱",   "min": 0,      "max": 1000},
        {"name": "Strategist",    "emoji": "♟️",   "min": 1000,   "max": 3000},
        {"name": "Line Master",   "emoji": "🎯",   "min": 3000,   "max": 7500},
        {"name": "Core Operator", "emoji": "🧮",   "min": 7500,   "max": 15000},
        {"name": "Diamond Hand",  "emoji": "💎",   "min": 15000,  "max": 30000},
        {"name": "Bacc Wizard",   "emoji": "🧙‍♂️", "min": 30000,  "max": None},
    ]

    current = tiers[0]
    next_tier = tiers[1] if len(tiers) > 1 else None

    for idx, t in enumerate(tiers):
        if lifetime_u >= t["min"] and (t["max"] is None or lifetime_u < t["max"]):
            current = t
            next_tier = tiers[idx + 1] if idx + 1 < len(tiers) else None
            break

    label = f'{current["emoji"]} {current["name"]}'

    name = current["name"]
    if name == "Apprentice":
        blurb = "Getting your reps in — focus on clean execution and staying inside the rules."
    elif name == "Strategist":
        blurb = "You're stacking sessions and starting to feel the core config working."
    elif name == "Line Master":
        blurb = "Lines are your playground — trims, caps, and restarts are part of the game."
    elif name == "Core Operator":
        extra = f" Capped {week_caps} week(s) so far." if week_caps > 0 else ""
        blurb = "Running the framework like a business, not a hobby." + extra
    elif name == "Diamond Hand":
        extra = f" Capped {week_caps} week(s) so far." if week_caps > 0 else ""
        blurb = "Proven through variance — you've held the line when it mattered." + extra
    else:  # Bacc Wizard
        extra = f" Capped {week_caps} week(s) so far." if week_caps > 0 else ""
        blurb = "Elite territory — protect the edge and avoid overreach." + extra

    if next_tier is None or current.get("max") is None:
        progress_pct = 100.0
        progress_text = f"Lifetime: {lifetime_u:+.0f}u (${lifetime_d:+,.2f}) · Max tier unlocked."
    else:
        span = float(next_tier["min"] - current["min"])
        progressed = max(0.0, lifetime_u - current["min"])
        progress_pct = max(0.0, min(100.0, (progressed / span) * 100.0))
        progress_text = (
            f"Lifetime: {lifetime_u:+.0f}u (${lifetime_d:+,.2f}) · "
            f"{progressed:.0f}/{span:.0f}u toward {next_tier['name']}."
        )

    return label, blurb, lifetime_u, lifetime_d, progress_pct, progress_text

def _fmt_pct(x): return f"{x:.1f}%"
def _fmt_u(x):   return f"{x:+.2f}u"
def _fmt_d(x):   return f"${x:+,.2f}"
def _fmt_min(x): return f"{x:.1f} min"

# ---------- Title & testing badge ----------
st.title("Player Stats")
if bool(st.session_state.get("testing_mode", False)):
    st.markdown(
        "<div class='pill' style='border-color:#5b1f22;background:linear-gradient(180deg,#1d0f10,#1a0c0d);color:#fca5a5'>"
        "<span style='width:7px;height:7px;border-radius:999px;background:#ef4444;display:inline-block'></span>"
        "<b>TESTING MODE</b></div>",
        unsafe_allow_html=True
    )

# Ensure we have a sensible active track
if "active_track_id" not in st.session_state:
    if TRACK_LABELS:
        st.session_state["active_track_id"] = next(iter(TRACK_LABELS.keys()))
    else:
        st.session_state["active_track_id"] = (tm.all_ids() or ["Track 1"])[0]

# ==================== TABS ====================
tab_all, tab_per_track = st.tabs(["📊 All Tracks", "🎯 Per Track"])

# ==================== TAB 1: ALL TRACKS ====================
with tab_all:
    st.markdown(
        "<div class='sub'>Aggregated stats across all your tracks. "
        "See your total performance, then drill into individual tracks in the Per Track tab.</div>",
        unsafe_allow_html=True
    )
    
    # Fetch ALL data (no track filter)
    all_sessions = _fetch_sessions(user_id, track_id=None)
    all_hands = _fetch_hands(user_id, track_id=None)
    all_events = _fetch_events(user_id, track_id=None)
    all_week_caps = _count_week_caps(user_id, track_id=None)
    
    # Calculate aggregate stats
    total_sessions_ct = len(all_sessions)
    total_hands_ct = len(all_hands)
    total_lines_ct = len(all_events)
    
    lifetime_u = sum(_safe_float(s.get("pl_units"), 0.0) for s in all_sessions)
    lifetime_d = sum(
        _safe_float(s.get("pl_units"), 0.0) * (_safe_float(s.get("unit_value", 1.0)) or 1.0)
        for s in all_sessions
    )
    
    # Tier badge (aggregate)
    tier_label, tier_blurb, _, _, tier_progress_pct, tier_progress_text = _tier_badge(
        all_sessions, all_hands, all_week_caps
    )
    
    progress_bar_html = f"""
    <div style="margin-top:6px;background:#111827;border-radius:999px;overflow:hidden;height:6px;">
      <div style="width:{tier_progress_pct:.1f}%;background:linear-gradient(90deg,#22c55e,#fde047);height:100%;"></div>
    </div>
    """
    
    # Hero cards
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            "<div class='hero-card'><div class='hero-title'>Lifetime P/L (All Tracks)</div>"
            f"<div class='hero-value'>{_fmt_u(lifetime_u)}</div>"
            f"<div class='kicker'>{_fmt_d(lifetime_d)}</div></div>",
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            "<div class='hero-card'><div class='hero-title'>Total Sessions</div>"
            f"<div class='hero-value'>{total_sessions_ct}</div>"
            f"<div class='kicker'>{total_hands_ct} hands · {total_lines_ct} lines</div></div>",
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            "<div class='hero-card'><div class='hero-title'>Week Caps (+400)</div>"
            f"<div class='hero-value'>{all_week_caps}</div>"
            f"<div class='kicker'>Across all tracks</div></div>",
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            "<div class='hero-card'><div class='hero-title'>Tracks</div>"
            f"<div class='hero-value'>{len(TRACK_LABELS)}</div>"
            f"<div class='kicker'>Active tracks in your account</div></div>",
            unsafe_allow_html=True,
        )
    
    # Tier badge
    st.markdown(
        "<div class='hero-card'><div class='hero-title'>Your Tier (Overall)</div>"
        f"<div class='hero-value'>{tier_label}</div>"
        f"{progress_bar_html}"
        f"<div class='kicker'>{tier_blurb}</div>"
        f"<div class='kicker' style='margin-top:4px'>{tier_progress_text}</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    
    # Aggregate Equity Curve
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="title">Aggregate Equity Curve</div>', unsafe_allow_html=True)
    st.markdown(
        "<div class='sub'>Your cumulative P/L across all tracks, ordered by session timestamp.</div>",
        unsafe_allow_html=True,
    )
    
    all_equity = _equity_from_sessions(all_sessions)
    all_drawdown = _drawdown_series(all_equity)
    
    eq1, eq2 = st.columns(2)
    with eq1:
        st.markdown("**Equity (units)**")
        if all_equity:
            st.line_chart({"equity_u": [e["equity_u"] for e in all_equity]})
        else:
            st.caption("No sessions yet.")
    with eq2:
        st.markdown("**Drawdown (from peak)**")
        if all_drawdown:
            st.line_chart({"drawdown_u": [d["drawdown_u"] for d in all_drawdown]})
        else:
            st.caption("No sessions yet.")
    
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Per-Track Summary Table
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="title">Per-Track Summary</div>', unsafe_allow_html=True)
    st.markdown(
        "<div class='sub'>Quick breakdown of each track's performance.</div>",
        unsafe_allow_html=True,
    )
    
    # Build summary data per track
    track_summary_rows = []
    for tid, label in TRACK_LABELS.items():
        track_sessions = [s for s in all_sessions if s.get("track_id") == tid]
        track_hands = [h for h in all_hands if h.get("track_id") == tid]
        
        t_pl_u = sum(_safe_float(s.get("pl_units"), 0.0) for s in track_sessions)
        t_pl_d = sum(
            _safe_float(s.get("pl_units"), 0.0) * (_safe_float(s.get("unit_value", 1.0)) or 1.0)
            for s in track_sessions
        )
        t_sessions = len(track_sessions)
        t_hands = len(track_hands)
        
        # Get current tone/defensive
        try:
            bundle = tm.ensure(tid)
            wk: WeekManager = bundle.week
            tone_info = wk.current_tone() or {}
            tone_name = str(tone_info.get("tone", "neutral")).lower()
            def_on = bool(tone_info.get("defensive", False))
            soft_shield_on = bool(tone_info.get("soft_shield", False))
        except Exception:
            tone_name = "—"
            def_on = False
            soft_shield_on = False
        
        track_summary_rows.append({
            "label": label,
            "pl_u": t_pl_u,
            "pl_d": t_pl_d,
            "sessions": t_sessions,
            "hands": t_hands,
            "tone": tone_name,
            "defensive": def_on,
            "soft_shield": soft_shield_on,
        })
    
    # Render table
    st.markdown(
        "<div class='track-summary-table'>"
        "<div class='track-summary-hdr'>"
        "<div>Track</div>"
        "<div>P/L (units)</div>"
        "<div>P/L ($)</div>"
        "<div>Sessions</div>"
        "<div>Tone</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    
    for row in track_summary_rows:
        pl_color = "color:#22c55e" if row["pl_u"] >= 0 else "color:#ef4444"
        def_badge = "<span class='badge-yellow' style='margin-left:4px;font-size:.65rem'>🛡️</span>" if row["defensive"] else ""
        ss_badge = "<span class='badge-yellow' style='margin-left:4px;font-size:.65rem'>⚠️ SS</span>" if row.get("soft_shield") else ""
        st.markdown(
            f"<div class='track-summary-row'>"
            f"<div class='cell'>{row['label']}</div>"
            f"<div class='cell mono' style='{pl_color}'>{row['pl_u']:+.1f}u</div>"
            f"<div class='cell mono' style='{pl_color}'>${row['pl_d']:+,.2f}</div>"
            f"<div class='cell'>{row['sessions']}</div>"
            f"<div class='cell'>{row['tone']}{def_badge}{ss_badge}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Aggregate Flow Breakdown
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="title">Aggregate Flow Breakdown</div>', unsafe_allow_html=True)
    
    flow_g, flow_n, flow_r = _flow_breakdown(all_sessions)
    fb1, fb2, fb3 = st.columns(3)
    with fb1:
        st.markdown(
            f"<div class='flow-pill good'><span class='l'>Green</span><b>{_fmt_pct(flow_g*100)}</b></div>",
            unsafe_allow_html=True,
        )
    with fb2:
        st.markdown(
            f"<div class='flow-pill mid'><span class='l'>Neutral</span><b>{_fmt_pct(flow_n*100)}</b></div>",
            unsafe_allow_html=True,
        )
    with fb3:
        st.markdown(
            f"<div class='flow-pill bad'><span class='l'>Red</span><b>{_fmt_pct(flow_r*100)}</b></div>",
            unsafe_allow_html=True,
        )
    
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Aggregate Win Rate
    wr, avg_win, avg_loss, longest_w, longest_l = _win_rate_and_quality(all_hands)
    
    st.markdown("<div class='title'>Aggregate Win Rate & Decision Quality</div>", unsafe_allow_html=True)
    wc1, wc2, wc3, wc4 = st.columns(4)
    with wc1:
        st.markdown(
            f"<div class='hero-card'><div class='hero-title'>Win rate</div>"
            f"<div class='hero-value mono'>{_fmt_pct(wr)}</div></div>",
            unsafe_allow_html=True,
        )
    with wc2:
        st.markdown(
            f"<div class='hero-card'><div class='hero-title'>Avg units / win</div>"
            f"<div class='hero-value mono'>{_fmt_u(avg_win)}</div></div>",
            unsafe_allow_html=True,
        )
    with wc3:
        st.markdown(
            f"<div class='hero-card'><div class='hero-title'>Avg units / loss</div>"
            f"<div class='hero-value mono'>{_fmt_u(avg_loss)}</div></div>",
            unsafe_allow_html=True,
        )
    with wc4:
        st.markdown(
            f"<div class='hero-card'><div class='hero-title'>Longest streaks</div>"
            f"<div class='hero-value mono'>W{longest_w} · L{longest_l}</div></div>",
            unsafe_allow_html=True,
        )
    
    st.divider()
    
    # Aggregate Behavioral Stats
    agg_total_sessions, agg_avg_line_min, agg_avg_session_min = _behavioral(all_sessions, all_events)
    
    st.markdown("<div class='title'>Aggregate Behavioral Stats</div>", unsafe_allow_html=True)
    bs1, bs2, bs3 = st.columns(3)
    
    with bs1:
        st.markdown(
            f"<div class='hero-card'><div class='hero-title'>Sessions (all tracks)</div>"
            f"<div class='hero-value mono'>{agg_total_sessions}</div></div>",
            unsafe_allow_html=True,
        )
    
    with bs2:
        st.markdown(
            f"<div class='hero-card'><div class='hero-title'>Avg time per line</div>"
            f"<div class='hero-value mono'>{_fmt_min(agg_avg_line_min)}</div></div>",
            unsafe_allow_html=True,
        )
    
    with bs3:
        st.markdown(
            f"<div class='hero-card'><div class='hero-title'>Avg time per session</div>"
            f"<div class='hero-value mono'>{_fmt_min(agg_avg_session_min)}</div></div>",
            unsafe_allow_html=True,
        )
    
    st.caption("Aggregate timing across all tracks — how long you tend to stay in lines and sessions overall.")


# ==================== TAB 2: PER TRACK ====================
with tab_per_track:
    # Track selector
    track_options = list(TRACK_LABELS.keys())
    track_labels_list = [TRACK_LABELS[tid] for tid in track_options]
    
    if not track_options:
        st.info("No tracks found. Create a track in the Tracker to see per-track stats.")
        st.stop()
    
    # Find current selection index
    current_track = st.session_state.get("active_track_id", track_options[0])
    if current_track not in track_options:
        current_track = track_options[0]
    current_idx = track_options.index(current_track)
    
    selected_label = st.selectbox(
        "Select Track",
        options=track_labels_list,
        index=current_idx,
        key="player_stats_track_selector"
    )
    
    # Get the track_id from the selected label
    selected_idx = track_labels_list.index(selected_label)
    active_id = track_options[selected_idx]
    active_label = selected_label
    
    st.markdown(
        f"<div class='sub'>Showing detailed stats for <b>{active_label}</b>. "
        f"Switch tracks using the dropdown above.</div>",
        unsafe_allow_html=True
    )
    
    # Fetch data for selected track
    bundle = tm.ensure(active_id)
    eng: DiamondHybrid = bundle.eng
    week: WeekManager = bundle.week
    
    try:
        tone = week.current_tone()
    except Exception:
        tone = {"tone": "neutral", "defensive": False}
    
    tone_name = str(tone.get("tone","neutral")).lower()
    cap_target = int(tone.get("cap_target", getattr(week.state, "cap_target", 400)))
    def_on = bool(tone.get("defensive", False))
    
    # Hero strip for this track
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            "<div class='hero-card'><div class='hero-title'>Track</div>"
            f"<div class='hero-value'>{active_label}</div></div>",
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            "<div class='hero-card'><div class='hero-title'>Tone</div>"
            f"<div class='hero-value'>{tone_name}</div>"
            f"<div class='kicker'>Cap target: +{cap_target}u</div></div>",
            unsafe_allow_html=True,
        )
    with c3:
        badge_cls = "badge-yellow" + ("" if def_on else " off")
        txt = "ON" if def_on else "OFF"
        
        # Soft Shield status
        soft_shield_on = bool(tone.get("soft_shield", False))
        ss_html = ""
        if soft_shield_on:
            ss_html = "<span class='badge-yellow' style='margin-left:8px'>⚠️ Soft Shield</span>"
        
        st.markdown(
            "<div class='hero-card'><div class='hero-title'>Defensive Mode</div>"
            f"<div class='hero-value'><span class='{badge_cls}'>🛡️ {txt}</span>{ss_html}</div>"
            "<div class='kicker'>Auto-toggles on red/stabilizer, fragility, or 3 reds. "
            "Soft Shield activates at week P/L ≤ -300u.</div></div>",
            unsafe_allow_html=True,
        )
    with c4:
        nb, lod = _get_track_cadence(user_id, active_id)
        SESSIONS_PER_DAY_MAX = 6
        LINES_PER_SESSION_MAX = 2
        st.markdown(
            "<div class='hero-card'><div class='hero-title'>Cadence</div>"
            f"<div class='hero-value'>nb {nb}/{SESSIONS_PER_DAY_MAX} · "
            f"LOD {lod}/{LINES_PER_SESSION_MAX}</div>"
            f"<div class='kicker'>Midnight reset in {_until_next_reset_hms()}</div></div>",
            unsafe_allow_html=True,
        )
    
    # Fetch track-specific data
    sessions = _fetch_sessions(user_id, active_id)
    hands = _fetch_hands(user_id, active_id)
    events = _fetch_events(user_id, active_id)
    week_caps = _count_week_caps(user_id, active_id)
    
    equity = _equity_from_sessions(sessions)
    drawdown = _drawdown_series(equity)
    flow_g, flow_n, flow_r = _flow_breakdown(sessions)
    
    # Analytics
    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="title">Analytics</div>', unsafe_allow_html=True)
        st.markdown(
            f"<div class='sub'>Session equity and risk profile for <b>{active_label}</b>.</div>",
            unsafe_allow_html=True,
        )
    
        a1, a2 = st.columns(2)
        with a1:
            st.markdown("**Equity Curve (sessions)**")
            if equity:
                st.line_chart({"equity_u": [e["equity_u"] for e in equity]})
            else:
                st.caption("No sessions yet.")
            st.caption("Cumulative units per session for this track.")
    
        with a2:
            st.markdown("**Drawdown (from peak)**")
            if drawdown:
                st.line_chart({"drawdown_u": [d["drawdown_u"] for d in drawdown]})
            else:
                st.caption("No sessions yet.")
            st.caption("How far below your prior peak after each session.")
    
        st.markdown("**Flow Breakdown**")
        fb1, fb2, fb3 = st.columns(3)
        with fb1:
            st.markdown(
                f"<div class='flow-pill good'><span class='l'>Green</span><b>{_fmt_pct(flow_g*100)}</b></div>",
                unsafe_allow_html=True,
            )
        with fb2:
            st.markdown(
                f"<div class='flow-pill mid'><span class='l'>Neutral</span><b>{_fmt_pct(flow_n*100)}</b></div>",
                unsafe_allow_html=True,
            )
        with fb3:
            st.markdown(
                f"<div class='flow-pill bad'><span class='l'>Red</span><b>{_fmt_pct(flow_r*100)}</b></div>",
                unsafe_allow_html=True,
            )
    
        st.markdown("</div>", unsafe_allow_html=True)
    
    # Player Pulse for this track
    wr, avg_win, avg_loss, longest_w, longest_l = _win_rate_and_quality(hands)
    cons_avg, cons_sd, _last10 = _consistency(sessions)
    chips = _momentum_chips(hands)
    caption = _auto_caption(hands)
    total_sessions, avg_line_min, avg_session_min = _behavioral(sessions, events)
    tier_label, tier_blurb, lifetime_u, lifetime_d, tier_progress_pct, tier_progress_text = _tier_badge(
        sessions, hands, week_caps
    )
    
    progress_bar_html = f"""
    <div style="margin-top:6px;background:#111827;border-radius:999px;overflow:hidden;height:6px;">
      <div style="width:{tier_progress_pct:.1f}%;background:linear-gradient(90deg,#22c55e,#fde047);height:100%;"></div>
    </div>
    """
    
    # Tier badge
    st.markdown(
        f"<div class='hero-card'><div class='hero-title'>Track Tier ({active_label})</div>"
        f"<div class='hero-value'>{tier_label}</div>"
        f"{progress_bar_html}"
        f"<div class='kicker'>{tier_blurb}</div>"
        f"<div class='kicker' style='margin-top:4px'>{tier_progress_text}</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    
    # Win Rate
    st.markdown("<div class='title'>Win Rate & Decision Quality</div>", unsafe_allow_html=True)
    wc1, wc2, wc3, wc4 = st.columns(4)
    with wc1:
        st.markdown(
            f"<div class='hero-card'><div class='hero-title'>Win rate</div>"
            f"<div class='hero-value mono'>{_fmt_pct(wr)}</div></div>",
            unsafe_allow_html=True,
        )
    with wc2:
        st.markdown(
            f"<div class='hero-card'><div class='hero-title'>Avg units / win</div>"
            f"<div class='hero-value mono'>{_fmt_u(avg_win)}</div></div>",
            unsafe_allow_html=True,
        )
    with wc3:
        st.markdown(
            f"<div class='hero-card'><div class='hero-title'>Avg units / loss</div>"
            f"<div class='hero-value mono'>{_fmt_u(avg_loss)}</div></div>",
            unsafe_allow_html=True,
        )
    with wc4:
        st.markdown(
            f"<div class='hero-card'><div class='hero-title'>Longest streaks</div>"
            f"<div class='hero-value mono'>W{longest_w} · L{longest_l}</div></div>",
            unsafe_allow_html=True,
        )
    st.caption("Judgment quality across hands (independent of variance spikes).")
    
    st.divider()
    
    # Consistency Meter
    st.markdown("<div class='title'>Consistency Meter</div>", unsafe_allow_html=True)
    ccA, ccB = st.columns(2)
    with ccA:
        st.markdown(
            f"<div class='hero-card'><div class='hero-title'>Avg session P/L (last 10)</div>"
            f"<div class='hero-value mono'>{_fmt_u(cons_avg)}</div></div>",
            unsafe_allow_html=True,
        )
    with ccB:
        st.markdown(
            f"<div class='hero-card'><div class='hero-title'>Std. deviation (last 10)</div>"
            f"<div class='hero-value mono'>{cons_sd:.2f}u</div></div>",
            unsafe_allow_html=True,
        )
    st.caption("Smaller swings = steadier execution and mindset.")
    
    st.divider()
    
    # Momentum Bar
    st.markdown("<div class='title'>Momentum</div>", unsafe_allow_html=True)
    mhtml = []
    for _, cls, _emoji in chips:
        mhtml.append(f"<span class='mom-chip {cls}' title='{_emoji}'></span>")
    st.markdown(
        f"<div class='hero-card'><div class='hero-title'>Last 10 outcomes</div>"
        f"<div class='momentum'>{''.join(mhtml) if mhtml else '<span class=\"dim\">No hands yet</span>'}</div>"
        f"<div class='kicker' style='margin-top:6px'>{caption}</div></div>",
        unsafe_allow_html=True,
    )
    
    st.divider()
    
    # Behavioral Stats
    st.markdown("<div class='title'>Behavioral Stats</div>", unsafe_allow_html=True)
    bs1, bs2, bs3 = st.columns(3)
    
    with bs1:
        st.markdown(
            f"<div class='hero-card'><div class='hero-title'>Sessions (this track)</div>"
            f"<div class='hero-value mono'>{total_sessions}</div></div>",
            unsafe_allow_html=True,
        )
    
    with bs2:
        st.markdown(
            f"<div class='hero-card'><div class='hero-title'>Avg time per line</div>"
            f"<div class='hero-value mono'>{_fmt_min(avg_line_min)}</div></div>",
            unsafe_allow_html=True,
        )
    
    with bs3:
        st.markdown(
            f"<div class='hero-card'><div class='hero-title'>Avg time per session</div>"
            f"<div class='hero-value mono'>{_fmt_min(avg_session_min)}</div></div>",
            unsafe_allow_html=True,
        )
    
    st.caption("How long you tend to stay in a line and a session for this track.")
    st.divider()
    
    # Discipline & Notices
    st.markdown("<div class='section'>Discipline & Notices</div>", unsafe_allow_html=True)
    
    nb_track, lod_track = _get_track_cadence(user_id, active_id)
    NB_MAX = 6
    LOD_MAX = 2
    
    nb_badge  = f"<span class='badge'>nb {nb_track}/{NB_MAX}</span>"
    lod_badge = f"<span class='badge'>LOD {lod_track}/{LOD_MAX}</span>"
    
    track_events = []
    if supabase is not None and user_id and active_id:
        try:
            track_events = fetch_track_events(user_db_id, active_id, limit=50)
        except Exception as e:
            print(f"[player_stats] fetch_track_events error: {e!r}")
            track_events = []
    
    history = st.session_state.get("modal_queue_history", [])
    if track_events:
        notices_ct = len(track_events)
    else:
        notices_ct = len(history) if isinstance(history, list) else 0
    
    cA, cB, cC = st.columns(3)
    with cA:
        st.markdown(
            "<div class='hero-card'><div class='hero-title'>Pacing</div>"
            f"<div class='hero-value'>{nb_badge} {lod_badge}</div>"
            "<div class='kicker'>Cadence for this track only.</div></div>",
            unsafe_allow_html=True,
        )
    with cB:
        st.markdown(
            "<div class='hero-card'><div class='hero-title'>Auto Notices</div>"
            f"<div class='hero-value'>{notices_ct}</div>"
            "<div class='kicker'>Line/session/week rules.</div></div>",
            unsafe_allow_html=True,
        )
    with cC:
        frag_hint = "—"
        frag_sub = "Need more data to read table conditions."
    
        try:
            if hasattr(eng, "_fused_fragility_score"):
                raw = eng._fused_fragility_score()
                score = float(raw[0] if isinstance(raw, (tuple, list)) else raw)
                frag_hint = "Choppy" if score >= 0.55 else "Stable"
            else:
                raise Exception("no engine fragility fn")
        except Exception:
            frag_hint, _score = _market_feel_from_db(hands, sessions)
    
        if frag_hint != "—":
            frag_sub = "Fusion of recent win/loss rhythm, line behavior, and volatility."
    
        st.markdown(
            "<div class='hero-card'><div class='hero-title'>Market Feel</div>"
            f"<div class='hero-value'>{frag_hint}</div>"
            f"<div class='kicker'>{frag_sub}</div></div>",
            unsafe_allow_html=True,
        )
    
    # Recent Notices
    st.markdown("### Recent Notices")
    
    recent_items = []
    if track_events:
        recent_items = track_events[:8]
    else:
        history = st.session_state.get("modal_queue_history", [])
        if isinstance(history, list):
            recent_items = list(reversed(history[-8:]))
    
    if recent_items:
        for item in recent_items:
            title = str(item.get("title", "Notice"))
            body  = str(item.get("body", "")).strip()
            kind  = str(item.get("kind", "info"))
            ts    = str(item.get("ts", ""))
    
            st.markdown(
                f"<div class='hero-card'><div class='hero-title'>{kind.title()}</div>"
                f"<div class='hero-value' style='font-size:1.05rem'>{title}</div>"
                f"<div class='kicker' style='margin-top:6px'>{body}</div>"
                f"<div class='kicker' style='margin-top:4px;font-size:.78rem;color:#6b7280'>{ts}</div></div>",
                unsafe_allow_html=True,
            )
    else:
        st.caption(
            "No notices yet — you'll see line/session/week auto rules here."
        )