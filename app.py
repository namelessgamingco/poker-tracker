# app.py — gated home, unified sidebar, clean dashboard with Quick Start + status + Discord link
# MODIFIED: Added caching to reduce DB calls and speed up page loads

import os
from datetime import datetime, timedelta, time
import streamlit as st

# ---- Environment flag ----
APP_ENV = os.getenv("APP_ENV", "prod")

# ---- Page meta (run first) ----
env_suffix = " (DEV)" if APP_ENV == "dev" else ""
st.set_page_config(
    page_title=f"Bacc Core Tracker{env_suffix}",
    page_icon="🃏",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---- Auth gate (hide everything until logged in) ----
from auth import require_auth
user = require_auth()

# ---- Shared sidebar (only after auth) ----
from sidebar import render_sidebar
render_sidebar()

# ---- First login nudge: make sure they notice the sidebar ----
st.session_state.setdefault("first_login_sidebar_hint_shown", False)

is_first_login = bool(st.session_state.get("profile_created", False))
if is_first_login and not st.session_state.first_login_sidebar_hint_shown:
    st.toast("👈 Your menu is in the left sidebar (pages + Testing Mode).", icon="👈")
    st.session_state.first_login_sidebar_hint_shown = True

# ---- Optional timezone for reset timer ----
try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo("America/Los_Angeles")
except Exception:
    _TZ = None

# ---- Pull fast-test knobs (for dynamic nb/LOD display) ----
NB_MAX = 6
LOD_MAX = 2

# ---- Core managers + DB helpers ----
from track_manager import TrackManager
from week_manager import WeekManager
from engine import DiamondHybrid

from typing import Any, Dict, Callable, Optional

# ✅ Import DB functions
try:
    from db import get_tracks_for_user, load_track_state
except Exception:
    def get_tracks_for_user(user_id: str):
        return []

    def load_track_state(user_id: str, track_id: str):
        return None

# ✅ Import ensure_profile separately (optional)
try:
    from db import ensure_profile
except Exception:
    ensure_profile = None

# ✅ ADDED: Import caching functions
from cache import (
    get_cached_tracks,
    get_cached_track_state,
    is_hydrated,
    mark_hydrated,
)


# ✅ MODIFIED: Use cached version for loading state
def _load_state(user_id: str, track_id: str) -> Dict[str, Any]:
    """
    Always returns a dict. Uses cache to avoid DB hits on rerun.
    """
    if not track_id or not user_id:
        return {}

    return get_cached_track_state(str(user_id), str(track_id), load_track_state)


# ---------- Auth helper → extract id/email for DB ----------
def _extract_auth_identity(u) -> tuple[str, str]:
    """
    Try to pull a stable auth_id + email out of whatever `require_auth()` returns.
    Works for dict-like or object-like auth payloads.
    """
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
        raise RuntimeError("Could not extract auth user id from require_auth() payload.")

    return str(auth_id), str(email)

auth_id, cur_email = _extract_auth_identity(user)

USER_DB_ID = None

# ✅ Ensure profile exists (first login) and get canonical DB id
if ensure_profile is not None:
    try:
        prof = ensure_profile(auth_id=auth_id, email=cur_email) or {}
        USER_DB_ID = str(prof.get("user_id") or "")
    except Exception as e:
        print(f"[app] ensure_profile error: {e!r}")
else:
    try:
        from db import get_profile_by_auth_id
        prof = get_profile_by_auth_id(auth_id) or {}
        USER_DB_ID = str(prof.get("user_id") or "")
    except Exception as e:
        print(f"[app] get_profile_by_auth_id error: {e!r}")

if not USER_DB_ID:
    st.error("Profile not found for this account. Contact an admin.")
    st.stop()

st.session_state["user_db_id"] = USER_DB_ID
st.session_state["auth_id"] = auth_id
st.session_state["email"] = cur_email

# ✅ Load user-specific unit_value from DB
if st.session_state.get("_unit_value_user") != st.session_state["user_db_id"]:
    try:
        from db import get_user_unit_value
        st.session_state.unit_value = get_user_unit_value(st.session_state["user_db_id"])
        st.session_state._unit_value_user = st.session_state["user_db_id"]
    except Exception as e:
        print(f"[app] unit_value load error: {e!r}")

# ---------- Track ordering helpers (stable Track 1/2/3...) ----------
def _parse_dt(x):
    if not x:
        return None
    if isinstance(x, datetime):
        return x
    s = str(x)
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None

from datetime import timezone
_AWARE_MAX = datetime.max.replace(tzinfo=timezone.utc)

# ✅ MODIFIED: Use cached tracks
def _get_ordered_tracks(user_db_id: str):
    """
    Deterministic ordering for "Track 1/2/3..." independent of DB return order.
    """
    ts_keys = ("created_at", "inserted_at", "created", "createdOn")
    # ✅ CHANGED: Use cached version
    tracks = [t for t in (get_cached_tracks(user_db_id, get_tracks_for_user) or []) if t.get("id")]

    def sort_key(t):
        dt = None
        for k in ts_keys:
            dt = _parse_dt(t.get(k))
            if dt:
                break
        return (dt is None, dt or datetime.max, str(t.get("id") or ""))

    return sorted(tracks, key=sort_key)

# ---------- Session / Managers ----------
if "unit_value" not in st.session_state:
    st.session_state.unit_value = 1.0

if "tm" not in st.session_state:
    st.session_state.tm = TrackManager(unit_value=float(st.session_state.unit_value))

tm: TrackManager = st.session_state.tm

st.session_state.setdefault("sessions_today", 0)
st.session_state.setdefault("lines_in_session", 0)

def _get_track_week_snapshot(user_id: str, track_id: str) -> tuple[int, float]:
    """
    Returns (week_number, week_pl_live) for the active track.
    """
    if not user_id or not track_id:
        return 1, 0.0

    try:
        b = tm.ensure(str(track_id))
        wk: WeekManager = b.week
        eng: DiamondHybrid = b.eng

        booked = float(getattr(getattr(wk, "state", wk), "week_pl", 0.0))
        live_delta = float(getattr(wk, "_live_delta", 0.0))
        sess_pl = float(getattr(eng, "session_pl_units", 0.0))

        sess_injected = sess_pl
        if abs(live_delta) > 1e-9 and abs(live_delta - sess_pl) < 1e-6:
            sess_injected = 0.0

        wpl_live = booked + live_delta + sess_injected
        wk_no = int(getattr(getattr(wk, "state", wk), "week_number", 1) or 1)
        return wk_no, float(wpl_live)
    except Exception:
        pass

    try:
        s = _load_state(str(user_id), str(track_id)) or {}
        wk_state = s.get("week") or s.get("week_state") or {}
        wk_no = int(wk_state.get("week_number", 1) or 1)
        booked = float(wk_state.get("week_pl", 0.0) or 0.0)
        return wk_no, booked
    except Exception:
        return 1, 0.0

# ✅ MODIFIED: Use cached tracks
def _get_global_cadence(user_id: str) -> tuple[int, int]:
    """
    Global totals for today across ALL tracks.
    """
    if not user_id:
        return 0, 0

    try:
        # ✅ CHANGED: Use cached version
        tracks = get_cached_tracks(str(user_id), get_tracks_for_user) or []
    except Exception as e:
        print(f"[app] _get_global_cadence get_tracks error: {e!r}")
        return 0, 0

    nb_total = 0
    lod_total = 0

    for t in tracks:
        tid = str(t.get("id") or "")
        if not tid:
            continue
        try:
            s = _load_state(str(user_id), tid) or {}
            nb_total += int(s.get("sessions_today", 0) or 0)
            lod_total += int(s.get("lines_in_session", 0) or 0)
        except Exception as e:
            print(f"[app] _get_global_cadence state error tid={tid}: {e!r}")
            continue

    return nb_total, lod_total

# ---------- Force-load track bundles on cold login ----------
# ✅ MODIFIED: Use cached tracks
def _force_hydrate_tracks(user_db_id: str):
    """
    Make sure TrackManager has bundles for all DB tracks.
    """
    if not user_db_id:
        return

    try:
        # ✅ CHANGED: Use cached version
        db_tracks = get_cached_tracks(user_db_id, get_tracks_for_user) or []
    except Exception as e:
        print(f"[app] _force_hydrate_tracks get_tracks error: {e!r}")
        return

    week_by_track = st.session_state.setdefault("week_by_track", {})

    for t in db_tracks:
        try:
            tid = str(t.get("id"))
            bundle = tm.ensure(tid)
        except Exception as e:
            print(f"[app] _force_hydrate_tracks ensure error for track {t!r}: {e!r}")
            continue

        try:
            state = _load_state(user_db_id, tid)
        except Exception as e:
            print(f"[app] _force_hydrate_tracks load_state error for {tid}: {e!r}")
            continue

        if hasattr(bundle, "import_state") and callable(getattr(bundle, "import_state")):
            try:
                bundle.import_state(state)
                week_by_track[tid] = bundle.week
                eng_state = state.get("engine") or state.get("eng") or state.get("engine_state") or state.get("engine_state_json")
                if isinstance(eng_state, dict) and "unit_value" in eng_state:
                    try:
                        st.session_state.unit_value = float(eng_state["unit_value"])
                    except Exception:
                        pass
                continue
            except Exception as e:
                print(f"[app] _force_hydrate_tracks bundle.import_state error for {tid}: {e!r}")

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
                if "unit_value" in eng_state:
                    try:
                        st.session_state.unit_value = float(eng_state["unit_value"])
                    except Exception:
                        pass
            except Exception as e:
                print(f"[app] _force_hydrate_tracks engine import error for {tid}: {e!r}")

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
                print(f"[app] _force_hydrate_tracks week import error for {tid}: {e!r}")

        week_by_track[tid] = bundle.week

# ---------- Build friendly track labels ----------
# ✅ MODIFIED: Use cached tracks
def _ensure_track_labels(user_db_id: str) -> dict[str, str]:
    """
    Mapping of DB track UUID -> track_label from tracks table.
    """
    labels: dict[str, str] = {}

    if not user_db_id:
        return labels

    try:
        # ✅ CHANGED: Use cached version
        db_tracks = get_cached_tracks(user_db_id, get_tracks_for_user) or []
        db_tracks = sorted(
            db_tracks,
            key=lambda t: (
                str(t.get("created_at") or ""),
                str(t.get("id") or ""),
            ),
        )
    except Exception as e:
        print(f"[app] _ensure_track_labels error: {e!r}")
        db_tracks = []

    for t in db_tracks:
        tid = str(t.get("id") or "")
        if not tid:
            continue
        labels[tid] = str(t.get("track_label") or t.get("name") or "Track")

    return labels

# ----- Run hydration before we draw tiles -----
# ✅ MODIFIED: Only hydrate if not already done this session
if not is_hydrated(st.session_state["user_db_id"]):
    _force_hydrate_tracks(st.session_state["user_db_id"])
    mark_hydrated(st.session_state["user_db_id"])

TRACK_LABELS = _ensure_track_labels(st.session_state["user_db_id"])

ordered_tracks = _get_ordered_tracks(st.session_state["user_db_id"]) or []
track_ids = [str(t.get("id") or "") for t in ordered_tracks]
track_ids = [tid for tid in track_ids if tid]

active_track_id = str(st.session_state.get("active_track_id") or "")
if active_track_id not in track_ids:
    active_track_id = track_ids[0] if track_ids else ""
    st.session_state["active_track_id"] = active_track_id

# ------------------ Main Page ------------------
st.title("🃏 Bacc Core Tracker")
st.write("Your command center for running lines, sessions, multiple tracks, and full weekly cycles.")

# ------------------ Quick Status Strip ------------------
def _until_next_reset_hms():
    now = datetime.now(_TZ) if _TZ else datetime.now()
    tomorrow = (now + timedelta(days=1)).date()
    next_mid = datetime.combine(tomorrow, time(0, 0, 0), tzinfo=_TZ) if _TZ else datetime.combine(tomorrow, time(0, 0, 0))
    rem = max(0, int((next_mid - now).total_seconds()))
    h = rem // 3600
    m = (rem % 3600) // 60
    return f"{h:02d}:{m:02d} until reset"

unit = float(st.session_state.get("unit_value", 1.0))

def _get_cadence_for_track(user_id: str, track_id: str) -> tuple[int, int]:
    if not user_id or not track_id:
        return 0, 0
    s = _load_state(user_id, track_id) or {}
    if not isinstance(s, dict):
        s = {}
    nb = int(s.get("sessions_today", 0) or 0)
    lod = int(s.get("lines_in_session", 0) or 0)
    return nb, lod

active_track_label = TRACK_LABELS.get(active_track_id, "—")

tone_name = "neutral"
def_on = False
try:
    if active_track_id:
        wk: WeekManager = tm.ensure(active_track_id).week
        td = wk.current_tone() or {}
        tone_name = str(td.get("tone") or td.get("name") or "neutral").lower()
        def_on = bool(td.get("defensive", False))
except Exception:
    pass

nb_total, lod_total = _get_global_cadence(st.session_state["user_db_id"])
nb_track, lod_track = _get_cadence_for_track(st.session_state["user_db_id"], active_track_id)

track_count = max(1, len(track_ids or []))

lod_cap_per_track = 2
nb_cap_per_track = 6

nb_max_global = nb_cap_per_track * track_count
lod_max_global = lod_cap_per_track * track_count

nb_used = int(nb_total)
lod_used = int(lod_total)

wk_no, wpl_live = _get_track_week_snapshot(st.session_state["user_db_id"], active_track_id)

st.markdown("""
<style>
.hero-card{
  border:1px solid #1f1f1f;
  background:linear-gradient(180deg,#0e0e0f,#121214);
  border-radius:14px;
  padding:14px 16px;
  margin-bottom:12px;

  min-height: 92px;
  display:flex;
  flex-direction:column;
  justify-content:space-between;
}
.hero-title{color:#9ca3af;font-size:.9rem;margin-bottom:6px}
.hero-value{font-size:1.2rem;font-weight:800;color:#e5e7eb}
.kicker{color:#9ca3af;font-size:.82rem}

.badge-yellow {
  display:inline-block;padding:2px 10px;font-size:.72rem;border-radius:999px;
  border:1px solid #6f6428;color:#f2e6a5;background:linear-gradient(180deg,#2a280f,#1e1d0c);
  margin-left:8px;vertical-align:middle;box-shadow:0 2px 10px rgba(0,0,0,.25);
}
.badge-yellow.off { opacity:.45; filter: grayscale(25%); }
.badge { display:inline-block;padding:2px 8px;font-size:.72rem;border-radius:999px;border:1px solid #2b2b2b;
  color:#cfcfcf;background:#101010;margin-left:8px;vertical-align:middle; }
</style>
""", unsafe_allow_html=True)

st.markdown(
    "<div style='margin-bottom:6px; color:#9ca3af; font-size:0.85rem;'>"
    "Dashboard snapshot — global totals + active track context. These update automatically as you run lines and sessions."
    "</div>",
    unsafe_allow_html=True,
)

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(
        "<div class='hero-card'><div class='hero-title'>Active Track</div>"
        f"<div class='hero-value'>{active_track_label}</div>"
        f"<div class='kicker'>Week {wk_no} · WPL {wpl_live:+.1f}u</div></div>",
        unsafe_allow_html=True,
    )
with c2:
    st.markdown(
        "<div class='hero-card'><div class='hero-title'>Tone</div>"
        f"<div class='hero-value'>{tone_name}</div>"
        f"<div class='kicker'>Unit: ${unit:.2f}/u</div></div>",
        unsafe_allow_html=True,
    )
with c3:
    badge_cls = 'badge-yellow' + ('' if def_on else ' off')
    txt = 'ON' if def_on else 'OFF'
    st.markdown(
        "<div class='hero-card'><div class='hero-title'>Defensive</div>"
        f"<div class='hero-value'><span class='{badge_cls}'>🛡️ {txt}</span></div>"
        "<div class='kicker'>Auto-controls mirror core config.</div></div>",
        unsafe_allow_html=True,
    )
with c4:
    st.markdown(
        "<div class='hero-card'><div class='hero-title'>Today's Cadence (All Tracks)</div>"
        f"<div class='hero-value'>nb {nb_used}/{nb_max_global} · LOD {lod_used}/{lod_max_global}</div>"
        f"<div class='kicker'>Active: nb {nb_track}/{NB_MAX} · LOD {lod_track}/{LOD_MAX} · {_until_next_reset_hms()}</div></div>",
        unsafe_allow_html=True,
    )

# ------------------ Primary CTA ------------------
st.page_link("pages/01_Tracker.py", label="→ Continue in Tracker", icon="🎯")

st.markdown("---")

# ------------------ QUICK START ------------------
st.markdown("""
<div class="qs-wrap">
  <div class="qs-title">🚀 Quick Start (Your Trial Week)</div>

  <div class="qs-body">

  You have a <b>one-week free trial</b>. Use it to learn the system before risking real money.

  <b>1) Turn on Testing Mode (do this first)</b>
  - Find the toggle in the left sidebar
  - Testing Mode is a sandbox — nothing counts toward real stats
  - Keep it ON for your entire trial week

  <b>2) Open the Tracker and explore</b>
  - Click 🎯 <b>Tracker</b> below — Track 1 is already set up for you
  - Set your <b>$/unit</b> in the Tracker header (start with $1-5)
  - Look at the <b>Next Bet</b> card — this tells you exactly what to bet

  <b>3) Run your first test session</b>
  - Click <b>Win</b>, <b>Loss</b>, or <b>Tie</b> to log hands
  - Watch how lines open, close, and the session P/L updates
  - Keep going until the session ends automatically (or hit "End Session Now")

  <b>4) Experience the full lifecycle</b>
  - Run <b>5+ test sessions</b> during your trial
  - See a <b>line close</b> (Smart Trim, Kicker, or Trailing Stop)
  - See a <b>session close</b> (Goal or Stop)
  - See a <b>week close</b> (cap, guard, or lock)
  - You're ready for live play when all three feel familiar

  <b>5) Read the docs (20-40 mins total)</b>
  - 📘 <b>How It Works</b> — explains everything you just experienced
  - 📈 <b>Statistical Odds</b> — what to expect over weeks and months
  - 🧠 <b>Master Your Play</b> — scaling and error protocols

  <b>You don't need to memorize everything.</b> These pages are references you'll revisit often — during your first weeks, after your first red week, before scaling up. The goal isn't perfect recall, it's building a <b>feel</b> for how the system works through repetition and experience.

  <b>6) Go live only when ready</b>
  - Turn <b>Testing Mode OFF</b> in the sidebar
  - Follow <b>Next Bet</b> without exception
  - Accept that some weeks will be red — that's normal

  </div>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<style>
.qs-wrap{
  border:1px solid #1f1f1f;
  background:linear-gradient(180deg,#0e0e0f,#121214);
  border-radius:14px;
  padding:12px 14px;
  margin-bottom:10px;
}
.qs-title{
  font-size:1.25rem;
  font-weight:800;
  margin-bottom:6px;
  color:#e5e7eb;
}
.qs-body{
  font-size:0.94rem;
  line-height:1.45;
  color:#d1d5db;
}
.qs-body strong, .qs-body b{ color:#f3f4f6; }
</style>
""", unsafe_allow_html=True)

qc1, qc2, qc3, qc4 = st.columns(4)
with qc1:
    st.page_link("pages/01_Tracker.py", label="Open Tracker", icon="🎯")
with qc2:
    st.page_link("pages/05_How_It_Works.py", label="How It Works", icon="📘")
with qc3:
    st.page_link("pages/03_Statistical_Odds.py", label="Stat Odds", icon="📈")
with qc4:
    st.page_link("pages/08_Master_Your_Play.py", label="Master Your Play", icon="🧠")

st.markdown("---")

# ------------------ Page Navigation ------------------
st.subheader("Navigation")
st.page_link("pages/01_Tracker.py",            label="Tracker",           icon="🎯")
st.page_link("pages/02_Track_Overview.py",     label="Track Overview",    icon="📊")
st.page_link("pages/03_Statistical_Odds.py",   label="Statistical Odds",  icon="📈")
st.page_link("pages/04_Player_Stats.py",       label="Player Stats",      icon="🧠")
st.page_link("pages/05_How_It_Works.py",       label="How the App Works", icon="📘")
st.page_link("pages/06_Settings.py",           label="Settings",          icon="🛠️")
st.page_link("pages/07_Bankroll_Health.py",    label="Bankroll Health + Bonuses", icon="💼")
st.page_link("pages/08_Master_Your_Play.py",   label="Master Your Play",  icon="🧠")
if st.session_state.get("is_admin", False):
    st.page_link("pages/99_Admin.py",          label="Admin Console",     icon="🔐")

# ------------------ Recent Notices ------------------
history = st.session_state.get("modal_queue_history", [])
if isinstance(history, list) and history:
    st.markdown("### Recent Notices")
    for item in reversed(history[-3:]):
        title = str(item.get("title","Notice"))
        kind  = str(item.get("kind","info")).title()
        body  = str(item.get("body","")).strip()
        st.markdown(
            f"<div class='hero-card'><div class='hero-title'>{kind}</div>"
            f"<div class='hero-value' style='font-size:1.05rem'>{title}</div>"
            f"<div class='kicker' style='margin-top:6px'>{body}</div></div>",
            unsafe_allow_html=True,
        )

st.markdown("---")

# ------------------ Footer ------------------
try:
    ENV = st.secrets["ENV"]
except Exception:
    ENV = os.getenv("APP_ENV", "local")

try:
    VER = st.secrets.get("APP_VERSION", "")
except Exception:
    VER = ""

st.caption(f"Environment: **{ENV}**{(' · v' + VER) if VER else ''}")
st.caption("Built on the Core Config · All logic mirrors the live engine.")

# ---- Discord Support Link ----
st.markdown(
    """
    <div style='margin-top:10px; font-size:0.9rem;'>
        💬 Need help or want to report an issue?  
        <a href='https://discord.com/channels/1169748589522718770/1268729463500439553'
           target='_blank' rel='noopener noreferrer'
           style='color:#60a5fa; text-decoration:none; font-weight:600;'>
           → Open a support ticket on Discord
        </a>
    </div>
    """,
    unsafe_allow_html=True
)