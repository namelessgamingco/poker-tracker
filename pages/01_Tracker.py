# pages/01_Tracker.py — …

import streamlit as st
st.set_page_config(page_title="Tracker", page_icon="🎯", layout="wide")  # ← move here

from auth import require_auth
user = require_auth()

st.markdown("""
<style>
/* Remove default top padding */
.block-container {
    padding-top: 0 !important;
}

/* Remove visual focus ring on buttons (keeps functionality, removes highlight) */
div[data-testid="stButton"] button {
    outline: none !important;
    box-shadow: none !important;
}

div[data-testid="stButton"] button:focus,
div[data-testid="stButton"] button:focus-visible {
    outline: none !important;
    box-shadow: none !important;
    border: 1px solid rgba(250, 250, 250, 0.2) !important;
}

/* --- Header row tightening (kills the 'jump' / extra whitespace) --- */
div[data-testid="stHorizontalBlock"] { gap: 0.75rem; }

/* Tighten widget vertical spacing inside the header area */
div[data-testid="stSelectbox"] { margin-top: -8px; }
div[data-testid="stButton"] { margin-top: -2px; }

/* Remove extra space Streamlit adds above/below labels even when collapsed */
div[data-testid="stWidgetLabel"] { display: none !important; }

/* Make the selectbox itself slightly more compact */
div[data-testid="stSelectbox"] > div { padding-top: 0px; }
</style>
""", unsafe_allow_html=True)

# ---------- Auth helper → extract id/email for DB ----------
def _extract_auth_identity(u) -> tuple[str, str]:
    """
    Try to pull a stable auth_id + email out of whatever `require_auth()` returns.
    This is defensive so we don't explode if the auth object shape changes.
    """
    auth_id = None
    email = None

    # dict-like
    if isinstance(u, dict):
        auth_id = u.get("id") or u.get("user_id") or u.get("sub") or u.get("uid")
        email = u.get("email") or u.get("primary_email")
    else:
        # object-like
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


from db import get_profile_by_auth_id

auth_id, email = _extract_auth_identity(user)

# ----- Resolve canonical DB user id (profiles.user_id) -----
try:
    profile = get_profile_by_auth_id(auth_id) or {}
except Exception:
    st.error("DB error loading profile. Try again in a moment.")
    st.stop()

# MUST be the UUID in profiles.user_id
USER_ID = str(profile.get("user_id") or "")
if not USER_ID:
    st.error("Profile not found for this account. Contact an admin.")
    st.stop()

# Store canonical id once, under a single key
st.session_state["user_db_id"] = USER_ID

# Verify session state matches (catch stale state from previous user)
if st.session_state.get("_last_verified_user_id") and st.session_state["_last_verified_user_id"] != USER_ID:
    print(f"[WARN] User changed! Clearing stale caches. Old={st.session_state['_last_verified_user_id']}, New={USER_ID}")
    # Clear any user-specific caches
    st.session_state.pop("sessions_this_week_by_track", None)
    st.session_state.pop("_sessions_week_hydrated", None)
    st.session_state.pop("nb_by_track", None)
    st.session_state.pop("lod_by_track", None)
st.session_state["_last_verified_user_id"] = USER_ID

# Also keep auth id separate (never call it user_id)
AUTH_ID = str(auth_id)
st.session_state["auth_id"] = AUTH_ID

# ✅ Load user-specific unit_value from DB
if st.session_state.get("_unit_value_user") != USER_ID:
    try:
        from db import get_user_unit_value
        st.session_state.unit_value = get_user_unit_value(USER_ID)
        st.session_state._unit_value_user = USER_ID
    except Exception as e:
        print(f"[tracker] unit_value load error: {e!r}")

import html as _pyhtml
from typing import Any, Dict, List

import traceback

from engine import DiamondHybrid
from week_manager import WeekManager
from track_manager import TrackManager  # manages multiple engines
from sidebar import render_sidebar
render_sidebar()

from db import (
    get_or_create_user,
    get_tracks_for_user,
    create_track_for_user,
    save_track_state,
    load_track_state,
    log_track_event,
    fetch_track_events,
    log_hand_outcome,
    log_session_result,
    log_line_event,
    log_week_closure,
    get_sessions_this_week_count,
    get_week_pl_booked,
)

# 🔧 NEW: unified counter helpers
from play_counters import is_line_close, is_session_close, normalize_reason

from cache import (
    get_cached_tracks,
    get_cached_track_state,
    set_cached_track_state,
    invalidate_player_totals_cache,
    invalidate_closed_weeks_cache,
)

# --- timezone for daily reset (sim-fidelity) ---
from datetime import datetime, timedelta, time
try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo("America/Los_Angeles")
except Exception:
    _TZ = None

def _pst_day_key() -> str:
    now = datetime.now(_TZ) if _TZ else datetime.now()
    return now.strftime("%Y-%m-%d")

def _sf(x, default=0.0) -> float:
    try:
        return float(x)
    except Exception:
        return float(default)

def _live_week_pl(week, eng) -> float:
    booked = _sf(getattr(getattr(week, "state", week), "week_pl", 0.0))
    live_delta = _sf(getattr(week, "_live_delta", 0.0))
    sess_pl = _sf(getattr(eng, "session_pl_units", 0.0))

    sess_injected = sess_pl
    if abs(live_delta) > 1e-9 and abs(live_delta - sess_pl) < 1e-6:
        sess_injected = 0.0

    return booked + live_delta + sess_injected

def _get_sessions_this_week(track_id) -> int:
    tid = str(track_id) if track_id else ""
    if not tid:
        return 0

    m = st.session_state.get("sessions_this_week_by_track", {})
    if not isinstance(m, dict):
        m = {}

    # ✅ If missing, hydrate once (LIVE only) so header is correct on refresh
    if (tid not in m) and (not bool(st.session_state.get("testing_mode", False))) and st.session_state.get("user_db_id"):
        try:
            wk_no = _current_week_number()
            _ensure_week_cache_for_track(st.session_state["user_db_id"], tid, wk_no)
            m = st.session_state.get("sessions_this_week_by_track", {}) or {}
        except Exception as e:
            print(f"[tracker] _get_sessions_this_week hydrate suppressed: {e!r}")

    try:
        return int(m.get(tid, 0) or 0)
    except Exception:
        return 0

def _get_sessions_this_week_db(track_id, week_no: int) -> int:
    """
    DB source of truth. Count how many sessions have been CLOSED for this week
    for this user + track. Uses session_results table.
    """
    if not track_id:
        return 0
    try:
        return int(get_sessions_this_week_count(st.session_state["user_db_id"], str(track_id), int(week_no or 1)) or 0)
    except Exception:
        return 0

def _get_week_pl_booked_db(track_id, week_no: int) -> dict:
    """Returns {"units": float, "dollars": float} from DB."""
    if not track_id:
        return {"units": 0.0, "dollars": 0.0}
    try:
        result = get_week_pl_booked(st.session_state["user_db_id"], str(track_id), int(week_no or 1))
        if isinstance(result, dict):
            return result
        # Fallback for old float return
        return {"units": float(result or 0.0), "dollars": float(result or 0.0) * float(st.session_state.unit_value)}
    except Exception:
        return {"units": 0.0, "dollars": 0.0}

def _set_sessions_this_week(track_id, value: int) -> None:
    m = st.session_state.get("sessions_this_week_by_track", {})
    if not isinstance(m, dict):
        m = {}
    m[str(track_id)] = int(value or 0)
    st.session_state.sessions_this_week_by_track = m

def _ensure_maps():
    st.session_state.setdefault("sessions_this_week_by_track", {})
    st.session_state.setdefault("_sessions_week_hydrated", {})  # {track_id: bool}
    # REMOVE week_no_by_track entirely (authoritative drift risk)

def _ensure_week_cache_for_track(
    user_id: str,
    track_id: str,
    week_no: int,
    *,
    force: bool = False,   # ✅ NEW
) -> None:
    tid = str(track_id) if track_id else ""
    if not tid:
        return

    sw = st.session_state.setdefault("sessions_this_week_by_track", {})
    if not isinstance(sw, dict):
        sw = {}
        st.session_state.sessions_this_week_by_track = sw

    wk = int(week_no or 1)

    hydr = st.session_state.setdefault("_sessions_week_hydrated", {})

    # ✅ NEW RULE:
    # - If force=True → ALWAYS rehydrate from DB
    # - Else → only hydrate if missing or not yet hydrated
    if (not force) and (sw.get(tid) is not None) and hydr.get(tid, False):
        return

    try:
        db_count = int(get_sessions_this_week_count(user_id, tid, wk) or 0)

        sw[tid] = db_count
        st.session_state.sessions_this_week_by_track = sw

        hydr[tid] = True
        st.session_state["_sessions_week_hydrated"] = hydr
    except Exception as e:
        print(f"[hydrate] sessions_this_week hydrate suppressed: {e!r}")

def _hydrate_track_caches_from_bundle_and_db(tid: str):
    if not tid:
        return

    # Only keep the sessions_this_week cache map
    st.session_state.setdefault("sessions_this_week_by_track", {})
    tid_s = str(tid)

    # 1) Week number: single source of truth = bundle.week.state.week_number
    try:
        b = tm.ensure(tid_s)
        wk_use = int(getattr(b.week.state, "week_number", 1) or 1)
    except Exception as e:
        print(f"[hydrate] week_number from bundle suppressed: {e!r}")
        wk_use = 1  # safe fallback only

    # 2) Sessions-this-week from DB using that week number
    try:
        st.session_state["sessions_this_week_by_track"][tid_s] = int(
            _get_sessions_this_week_db(tid_s, wk_use) or 0
        )
        hydr = st.session_state.setdefault("_sessions_week_hydrated", {})
        hydr[tid_s] = True
        st.session_state["_sessions_week_hydrated"] = hydr
    except Exception as e:
        print(f"[hydrate] sessions_this_week hydrate suppressed: {e!r}")
        # do NOT set hydr True on failure
        pass

# ---- Testing Mode badge (simple & clean) ----
def _testing_badge():
    if bool(st.session_state.get("testing_mode", False)):
        st.markdown("""
<style>
.test-pill{
  display:inline-flex;align-items:center;gap:8px;
  border:1px solid #5b1f22;background:linear-gradient(180deg,#1d0f10,#1a0c0d);
  color:#fca5a5;border-radius:999px;padding:4px 10px;font-size:.8rem;
  box-shadow:0 2px 12px rgba(0,0,0,.35)
}
.test-pill .dot{width:7px;height:7px;border-radius:999px;background:#ef4444}
.test-note{color:#9ca3af;font-size:.78rem;margin-top:3px}
</style>
<div class="test-pill"><span class="dot"></span><b>TESTING MODE</b></div>
<div class="test-note">Sandboxed: results don’t affect live totals or closed-week stats.</div>
""", unsafe_allow_html=True)

# ------------------------ EARLY modal gate (so nothing else renders behind it) ------------------------
st.session_state.setdefault("modal_queue", [])

# ---------- Player Stats logs (init) ----------
st.session_state.setdefault("hand_outcomes", [])        # per-hand stream
st.session_state.setdefault("session_results", [])      # per-session summary
st.session_state.setdefault("line_events", [])          # line-close reasons
st.session_state.setdefault("modal_queue_history", [])  # modal history feed


def _now_iso():
    try:
        return datetime.now(_TZ).isoformat()
    except Exception:
        return datetime.utcnow().isoformat() + "Z"


def queue_modal(title: str, body_md: str, kind: str):
    """
    Queue a blocking modal AND record it into:
      • modal_queue_history (in-session view)
      • track_events table (persistent Event Feed) for major kinds

    The `body_md` value is treated as pre-formatted HTML/markdown-ish text.
    Newlines are converted to <br> at render-time; inline tags like <b> are allowed.
    """
    ts = _now_iso()
    item = {"title": title, "body": body_md, "kind": kind, "ts": ts}
    st.session_state.modal_queue.append(item)
    try:
        st.session_state.modal_queue_history.append(item)
    except Exception:
        st.session_state.modal_queue_history = [item]

    # Persist major events to DB for this track
    try:
        track_id = st.session_state.get("active_track_id")
        if (
            track_id
            and not bool(st.session_state.get("testing_mode", False))
            and kind in {"line", "session", "week"}
        ):
            log_track_event(
                st.session_state["user_db_id"],
                track_id=track_id,
                kind=kind,
                title=title,
                body=body_md,
                ts=ts,
            )
    except Exception as e:
        print(f"[queue_modal] log_track_event suppressed: {e!r}")


def _render_blocking_modal_early() -> bool:
    mq = st.session_state.get("modal_queue", [])
    if not mq:
        return False

    m = mq[0]
    title = m.get("title", "Notice")
    # Treat body as pre-formatted text/HTML snippet; keep line breaks
    body_raw = m.get("body", "") or ""
    body = body_raw.replace("\n", "<br>")

    # Centered card + full-width button (shares same width, stays in content area)
    st.markdown("""
    <style>
      .modal-stack{
        min-height:72vh;
        display:flex; flex-direction:column; align-items:center; justify-content:center;
        --mw: min(560px, 92%);
        gap: 0;
      }
      .modal-card{
        width: var(--mw);
        background: linear-gradient(135deg,#101010,#1b1b1d);
        border:1px solid #2b2b2b;
        border-radius:16px 16px 0 0;
        box-shadow:0 10px 40px rgba(0,0,0,.55);
        padding:24px;
        color:#eaeaea; text-align:center;
      }
      .modal-title{ font-size:1.25rem; font-weight:800; margin-bottom:12px; }
      .modal-body{ color:#d7d7d7; line-height:1.55; }

      .modal-btn-row{ width: var(--mw); }

      /* ✅ Only style the modal button */
      .modal-btn-row div[data-testid="stButton"] button{
        width:100% !important;
        border-radius:0 0 16px 16px !important;
        background:linear-gradient(180deg,#27272a,#1f2937) !important;
        color:#fafafa !important;
        border:1px solid #3f3f46 !important;
        border-top:0 !important;
        padding:12px 0 !important;
        font-size:.95rem !important;
        font-weight:600 !important;
        box-shadow:0 0 12px rgba(0,0,0,0.25) !important;
        transition:background .2s ease, box-shadow .2s ease !important;
      }
      .modal-btn-row div[data-testid="stButton"] button:hover{
        background:linear-gradient(180deg,#374151,#111827) !important;
        box-shadow:0 0 20px rgba(0,0,0,0.45) !important;
      }
    </style>
    """, unsafe_allow_html=True)

    # Card + button share the same centered stack (no columns, no vw)
    st.markdown(
        f"""
        <div class="modal-stack">
          <div class="modal-card">
            <div class="modal-title">{_pyhtml.escape(title)}</div>
            <div class="modal-body">{body}</div>
          </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<div class='modal-btn-row'>", unsafe_allow_html=True)
    if st.button("Got it", key="modal_ack_early", use_container_width=True):
        st.session_state.modal_queue.pop(0)
        st.rerun()
    st.markdown("</div></div>", unsafe_allow_html=True)

    return True


# stop if any modal is showing
if _render_blocking_modal_early():
    st.stop()

# ✅ Scroll-to-top on rerun (track switch / new track)
if st.session_state.pop("__scroll_to_top__", False):
    st.markdown(
        """
        <script>
          (function() {
            window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
            // run again after layout paints (fixes "fake top gap" on heavy rerenders)
            setTimeout(() => window.scrollTo({ top: 0, left: 0, behavior: 'instant' }), 0);
            setTimeout(() => window.scrollTo({ top: 0, left: 0, behavior: 'instant' }), 50);
          })();
        </script>
        """,
        unsafe_allow_html=True,
    )

# ------------------------ Helpers ------------------------
def _get_nb(track_id) -> int:
    d = st.session_state.get("nb_by_track", {}) or {}
    try:
        return int(d.get(str(track_id), 0) or 0)
    except Exception:
        return 0


def _set_nb(track_id, value: int) -> None:
    d = st.session_state.get("nb_by_track", {}) or {}
    d[str(track_id)] = int(value or 0)
    st.session_state.nb_by_track = d


def _get_lod(track_id) -> int:
    d = st.session_state.get("lod_by_track", {}) or {}
    try:
        return int(d.get(str(track_id), 0) or 0)
    except Exception:
        return 0


def _set_lod(track_id, value: int) -> None:
    d = st.session_state.get("lod_by_track", {}) or {}
    d[str(track_id)] = int(value or 0)
    st.session_state.lod_by_track = d


def _get_session_index(track_id: str) -> int:
    m = st.session_state.setdefault("_session_index_by_track", {})
    return int(m.get(track_id, 0) or 0)

def _set_session_index(track_id: str, v: int) -> None:
    m = st.session_state.setdefault("_session_index_by_track", {})
    m[track_id] = int(v)

def _bump_session_index(track_id: str) -> int:
    cur = _get_session_index(track_id)
    nxt = cur + 1
    _set_session_index(track_id, nxt)
    return nxt

def _get_hand_index(track_id: str) -> int:
    m = st.session_state.setdefault("_hand_index_by_track", {})
    return int(m.get(track_id, 0) or 0)

def _bump_hand_index(track_id: str) -> int:
    m = st.session_state.setdefault("_hand_index_by_track", {})
    nxt = int(m.get(track_id, 0) or 0) + 1
    m[track_id] = nxt
    return nxt

def _reset_hand_index(track_id: str) -> None:
    m = st.session_state.setdefault("_hand_index_by_track", {})
    m[str(track_id)] = 0

# ------------------------ Helpers: formatting ------------------------
def _fmt_pl_both(units: float, unit_value: float) -> str:
    try:
        units = float(units)
        unit_value = float(unit_value)
    except Exception:
        return f"{units}u"
    usd = units * unit_value

    u_sign = "+" if units >= 0 else ""
    d_sign = "+" if usd >= 0 else "-"

    return f"{u_sign}{units:.2f}u ({d_sign}${abs(usd):,.2f})"

def _fmt_pl_both_precomputed(units: float, dollars: float) -> str:
    """Format P/L when dollars are already computed (e.g., from DB with historical unit_value)."""
    try:
        units = float(units)
        dollars = float(dollars)
    except Exception:
        return f"{units}u"

    u_sign = "+" if units >= 0 else ""
    d_sign = "+" if dollars >= 0 else "-"

    return f"{u_sign}{units:.2f}u ({d_sign}${abs(dollars):,.2f})"

def _fmt_units_dollars(units: float, unit_value: float) -> str:
    try:
        units = float(units)
        unit_value = float(unit_value)
    except Exception:
        return f"{units}u"
    usd = units * unit_value
    d_sign = "+" if usd >= 0 else "-"

    return f"{units:.2f}u ({d_sign}${abs(usd):,.2f})"

def _ensure_daily_rollover_for_active_track() -> None:
    """
    Enforce daily rollover for the ACTIVE track only.
    - If stored day_key != today's PST day_key => reset nb to 0 (and optionally LOD).
    - Keep it safe in Testing Mode (still ok, but won't write to DB unless you persist).
    """
    tid = st.session_state.get("active_track_id")
    if not tid:
        return

    today = _pst_day_key()

    # Prefer session_state day_key, else fall back to bundle-saved key if present
    saved = st.session_state.get("day_key")
    try:
        # bundle has imported state already at this point (usually)
        saved_bundle = getattr(tm.ensure(str(tid)), "export_state", lambda: {})().get("day_key")
        if not saved and saved_bundle:
            saved = saved_bundle
    except Exception:
        pass

    # First time: set it and continue
    if not saved:
        st.session_state["day_key"] = today
        return

    # New day: reset daily counters
    if str(saved) != str(today):
        _set_nb(tid, 0)

        # Optional: I recommend resetting LOD too (clean slate UX)
        _set_lod(tid, 0)

        st.session_state["day_key"] = today

        # Persist only in LIVE mode (guard against early call before function defined)
        if not bool(st.session_state.get("testing_mode", False)):
            try:
                _persist_active_track()
            except NameError:
                pass

        st.rerun()

# ✅ enforce midnight rollover before rendering anything
_ensure_daily_rollover_for_active_track()

# ------------------------ Styles (including header) ------------------------
st.markdown("""
<style>
.track-header{position:static;top:auto;z-index:auto;background:transparent;border:0;padding:0;margin:0}
.track-row{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
.track-row .left{display:flex;align-items:center;gap:10px;flex:1 1 320px;min-width:260px}
.track-row .right{display:flex;align-items:center;gap:10px}
.track-label{color:#cfcfcf;font-size:.92rem}

/* Header titles above each control (lock baseline) */
.hdr-title{
  color:#8b8b8b;
  font-size:.78rem;
  letter-spacing:.2px;
  height:14px;          /* ✅ fixed title height */
  line-height:14px;
  margin:0 0 10px 2px;
}

/* TOTAL should look like a Streamlit control (rectangle cell) */
.total-shell{
  height:44px;
  width:100%;
  display:flex;
  align-items:center;
  justify-content:center;

  border:1px solid #2b2b2b;
  border-radius:10px;
  background:linear-gradient(180deg,#151515,#101010);
  box-shadow:0 1px 0 rgba(255,255,255,0.03) inset;

  transform: translateY(-6px); /* ✅ key: align with select/button */
}

.total-value{
  font-size:.95rem;
  font-weight:700;
  color:#eaeaea;
  line-height:1;
}

/* chip (base) */
.count-chip{
  border:1px solid #2b2b2b;
  background:#121212;
  color:#eaeaea;
  padding:6px 10px;
  border-radius:999px;
  font-size:.85rem;
  display:inline-flex;
  width:auto;
  line-height:1;
}

@keyframes nbPulse{0%{box-shadow:0 0 0 0 var(--nb-glow);}50%{box-shadow:0 0 24px 12px var(--nb-glow);}100%{box-shadow:0 0 0 0 var(--nb-glow);}}
@keyframes textPulse{0%{text-shadow:0 0 0 rgba(34,197,94,0);}50%{text-shadow:0 0 10px rgba(34,197,94,.6);}100%{text-shadow:0 0 0 rgba(34,197,94,0);}}

.tone-chip{display:inline-flex;align-items:center;gap:8px;font-size:.9rem;color:#d0d0d0;flex-wrap:wrap}
.tone-dot{width:10px;height:10px;border-radius:999px;border:1px solid:#444}
.badge{display:inline-block;padding:2px 8px;font-size:.72rem;border-radius:999px;border:1px solid #2b2b2b;color:#cfcfcf;background:#101010;margin-left:8px;vertical-align:middle}
.badge.lock{border-color:#446;color:#cfe3ff;background:linear-gradient(180deg,#0f1420,#0c111a)}
.badge-yellow{display:inline-block;padding:2px 10px;font-size:.72rem;border-radius:999px;border:1px solid #6f6428;color:#f2e6a5;background:linear-gradient(180deg,#2a280f,#1e1d0c);margin-left:8px;vertical-align:middle;box-shadow:0 2px 10px rgba(0,0,0,.25)}
.badge-yellow.off{opacity:.45;filter:grayscale(25%)}

.nb-card{text-align:center;margin:28px auto;padding:32px 22px;border-radius:18px;width:65%;border:2px solid var(--nb-border);background:linear-gradient(135deg,var(--nb-bg-a),var(--nb-bg-b));color:#fff;box-shadow:var(--nb-shadow)}
.nb-card.green{--nb-border:#18c964;--nb-bg-a:#07140b;--nb-bg-b:#0e1d13;--nb-shadow:0 6px 20px rgba(0,0,0,.45);--nb-glow:rgba(24,201,100,.40)}
.nb-card.red{--nb-border:#ff5964;--nb-bg-a:#1a0b0c;--nb-bg-b:#220f10;--nb-shadow:0 6px 20px rgba(0,0,0,.45);--nb-glow:rgba(255,89,100,.45)}
.nb-card.neutral{--nb-border:#3a3a3a;--nb-bg-a:#0c0c0c;--nb-bg-b:#181818;--nb-shadow:0 6px 20px rgba(0,0,0,.45);--nb-glow:rgba(0,0,0,0)}

.nb-card.green.nb-pulse,
.nb-card.red.nb-pulse{animation: nbPulse 2.2s ease-in-out infinite;}

.metric-chip{display:flex;align-items:baseline;gap:6px;padding:6px 10px;border-radius:10px;border:1px solid #2b2b2b;background:#0f0f0f;color:#e5e5e5;font-size:.86rem}
.metric-chip .label{color:#a9a9a9}
.metric-chip .value{font-weight:700}
.metric-chip.positive .value{color:#22c55e}
.metric-chip.negative .value{color:#ef4444}

/* Side indicator styles for hero card */
.side-banker{
  display:inline-flex;align-items:center;gap:6px;
  padding:6px 14px;border-radius:999px;font-weight:700;font-size:.95rem;
  background:linear-gradient(135deg,#7f1d1d,#991b1b);
  border:1px solid #dc2626;color:#fecaca;
  box-shadow:0 2px 8px rgba(220,38,38,0.3);
}
.side-player{
  display:inline-flex;align-items:center;gap:6px;
  padding:6px 14px;border-radius:999px;font-weight:700;font-size:.95rem;
  background:linear-gradient(135deg,#1e3a5f,#1e40af);
  border:1px solid #3b82f6;color:#bfdbfe;
  box-shadow:0 2px 8px rgba(59,130,246,0.3);
}
</style>
""", unsafe_allow_html=True)

# --- Week chip style ---
st.markdown("""
<style>
.chip {
  display:inline-block;
  border:1px solid #334155;
  background:linear-gradient(135deg,#0f1115,#161a22);
  border-radius:999px;
  padding:4px 10px;
  font-size:.85rem;
  color:#cbd5e1;
}
.chip.neutral {
  background:linear-gradient(135deg,#1a1a1a,#222);
  border-color:#3a3a3a;
}
</style>
""", unsafe_allow_html=True)

# ------------------------ Init app session ------------------------
# Load user-specific unit_value from DB
if "unit_value" not in st.session_state:
    st.session_state.unit_value = 1.0
if "testing_mode" not in st.session_state:
    st.session_state.testing_mode = False

st.session_state.setdefault("_prev_testing_mode", bool(st.session_state.get("testing_mode", False)))

# Cadence counters (per-day, per-track)
st.session_state.setdefault("nb_by_track", {})            # {track_id: nb_today}
st.session_state.setdefault("lod_by_track", {})           # {track_id: lod_this_session}

# Timing anchors
st.session_state.setdefault("session_started_at", None)  # datetime for current session start
st.session_state.setdefault("line_started_at", None)     # datetime for current line start

# Other state
st.session_state.setdefault("_last_reason", None)
st.session_state.setdefault("_cache_session_pl", 0.0)
st.session_state.setdefault("_cache_week_pl", 0.0)
st.session_state.setdefault("_tone_name", "neutral")
st.session_state.setdefault("_wpl_live", 0.0)
st.session_state.setdefault("show_unit_editor", False)
st.session_state.setdefault("_confirm_end_session", False)

# Undo last hand (per-track)
st.session_state.setdefault("_last_hand", None)          # dict: {track_id, delta_units, outcome, ts, can_undo}
st.session_state.setdefault("_last_hand_block_reason", "")  # string for smart-guard caption

# 🔧 NEW: snapshot of state BEFORE the most recent hand (for true undo)
st.session_state.setdefault("_pre_hand_state", None)         # dict from bundle.export_state()
st.session_state.setdefault("_pre_hand_track_id", None)      # active track id at snapshot time

# Per-track rollups for Overview
st.session_state.setdefault("sessions_this_week_by_track", {})

# Per-track previous-state caches for Event Feed (defensive / optimizer flips)
st.session_state.setdefault("_prev_defensive_by_track", {})
st.session_state.setdefault("_prev_cap_target_by_track", {})

if "tm" not in st.session_state:
    st.session_state.tm = TrackManager(unit_value=float(st.session_state.unit_value))

tm: TrackManager = st.session_state.tm

# ------------------------ Role helpers ------------------------
def _is_admin() -> bool:
    try:
        if bool(profile.get("is_admin", False)):
            return True
        role = str(profile.get("role", "")).lower()
        return role in {"admin", "dev"}
    except Exception:
        return False

# Fetch tracks from DB
_tracks = get_cached_tracks(st.session_state["user_db_id"], get_tracks_for_user)

# If none, create a default one
if not _tracks:
    default_row = create_track_for_user(st.session_state["user_db_id"], "Track 1")
    _tracks = [default_row]

# Build id → name mapping (UUID-based ids from DB) ✅ string-normalized
track_ids = [str(t.get("id") or "") for t in _tracks]
track_ids = [tid for tid in track_ids if tid]  # safety

# Ensure active_track_id is always a real DB UUID
if "active_track_id" not in st.session_state or st.session_state.active_track_id not in track_ids:
    if track_ids:
        st.session_state.active_track_id = track_ids[0]
        st.session_state["last_active_track_id"] = track_ids[0]

track_name_by_id = {
    str(t.get("id") or ""): (t.get("track_label") or t.get("name") or "Track")
    for t in _tracks
    if t.get("id")
}

def _clear_track_scoped_ui_state():
    """
    Anything that should NOT bleed when switching tracks.
    Keep it intentionally small: only things that can corrupt UX / saving.
    """
    st.session_state["_confirm_end_session"] = False

    # undo safety
    st.session_state["_last_hand"] = None
    st.session_state["_last_hand_block_reason"] = ""
    st.session_state["_pre_hand_state"] = None
    st.session_state["_pre_hand_track_id"] = None

    # timers should not carry across tracks
    st.session_state["session_started_at"] = None
    st.session_state["line_started_at"] = None

    # caches used for display + continuity
    st.session_state["_last_reason"] = None
    st.session_state["_cache_session_pl"] = 0.0
    st.session_state["_cache_week_pl"] = 0.0
    st.session_state["_tone_name"] = "neutral"
    st.session_state["_wpl_live"] = 0.0

def _persist_track(tid):
    if bool(st.session_state.get("testing_mode", False)):
        return
    if not tid:
        return
    try:
        _bundle = tm.ensure(tid)
        state = _bundle.export_state() or {}

        # ---------- FORCE week blob into saved state ----------
        wk = state.get("week") or {}
        try:
            wk["week_number"]  = int(getattr(_bundle.week.state, "week_number", 1) or 1)
            wk["week_pl"]      = float(getattr(_bundle.week.state, "week_pl", 0.0) or 0.0)
            wk["cap_target"]   = int(getattr(_bundle.week.state, "cap_target", 0) or 0)
            wk["closed"]       = bool(getattr(_bundle.week.state, "closed", False))
            wk["closed_reason"]= getattr(_bundle.week.state, "closed_reason", None)
        except Exception:
            pass
        state["week"] = wk

        # ---------- FORCE engine blob into saved state ----------
        eng_state = state.get("engine") or {}
        try:
            eng_state["session_pl_units"] = float(getattr(_bundle.eng, "session_pl_units", 0.0) or 0.0)
            eng_state["line_pl_units"]    = float(getattr(_bundle.eng, "line_pl_units", 0.0) or 0.0)
            # keep if you still use it anywhere
            eng_state["week_pl_units"]    = float(getattr(_bundle.eng, "week_pl_units", 0.0) or 0.0)
        except Exception:
            pass
        state["engine"] = eng_state

        # cadence counters
        state["sessions_today"] = _get_nb(tid)
        state["lines_in_session"] = _get_lod(tid)
        state["sessions_this_week"] = _get_sessions_this_week(tid)

        state["day_key"] = _pst_day_key()

        save_track_state(st.session_state["user_db_id"], str(tid), state)
        
        # Update cache so next rerun doesn't re-fetch from DB
        set_cached_track_state(st.session_state["user_db_id"], str(tid), state)

    except Exception as e:
        print(f"[tracker] _persist_track({tid}) suppressed error: {e!r}")

def _on_active_track_change():
    new_id = st.session_state.get("__active_track_select__")
    if not new_id:
        return

    old_id = st.session_state.get("active_track_id")
    if str(new_id) == str(old_id):
        return

    # ✅ persist the track we are leaving
    try:
        _persist_track(old_id)
    except Exception as e:
        print(f"[tracker] persist-before-switch suppressed: {e!r}")

    st.session_state.active_track_id = str(new_id)
    st.session_state["last_active_track_id"] = str(new_id)

    # ✅ Request scroll-to-top on the NEXT render
    st.session_state["__scroll_to_top__"] = True

    _clear_track_scoped_ui_state()
    return

# when resolving active track
if "active_track_id" not in st.session_state:
    last = st.session_state.get("last_active_track_id")
    if last in track_ids:
        st.session_state.active_track_id = last
    else:
        st.session_state.active_track_id = track_ids[0]

# 🔹 1.3: ensure nb/LOD entries exist for this active track
active_id = st.session_state.active_track_id

# make sure the per-track dicts exist
st.session_state.setdefault("nb_by_track", {})
st.session_state.setdefault("lod_by_track", {})

if str(active_id) not in st.session_state.nb_by_track:
    st.session_state.nb_by_track[str(active_id)] = 0

if str(active_id) not in st.session_state.lod_by_track:
    st.session_state.lod_by_track[str(active_id)] = 0

# ------------------------ Config knobs (SIM-FIDELITY) ------------------------
SESSIONS_PER_DAY_MAX  = 6
LINES_PER_SESSION_MAX = 2
SESSION_GOAL_UNITS    = 30.0
FRAGILITY_STOP = 0.62

# ------------------------ Dev flags ------------------------
# Prefer secrets so you can hard-disable in prod
DEV_MODE = bool(getattr(st, "secrets", {}).get("DEV_MODE", False))

# ------------------------ Track Header (clean, non-sticky) ------------------------
with st.container():
    # Order: Active Track | Total | Add Track
    cA, cT, cB = st.columns([5.1, 0.9, 1.6], vertical_alignment="center")

    # Active Track selector
    with cA:
        st.markdown("<div class='hdr-title'>Active Track</div>", unsafe_allow_html=True)

        if not track_ids:
            st.warning("No tracks found for this user.")
            st.stop()

        if st.session_state.active_track_id not in track_ids:
            st.session_state.active_track_id = track_ids[0]

        st.selectbox(
            label="Track",
            options=track_ids,
            index=track_ids.index(st.session_state.active_track_id),
            key="__active_track_select__",
            label_visibility="collapsed",
            format_func=lambda tid: track_name_by_id.get(tid, str(tid)),
            on_change=_on_active_track_change,
        )

    # Total tracks
    with cT:
        total = len(track_ids)
        st.markdown(
            f"""
            <div class="hdr-title">Total</div>
            <div class="total-shell">
            <div class="total-value">{total}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    # Add Track button
    with cB:
        st.markdown("<div class='hdr-title'>Add Track</div>", unsafe_allow_html=True)

        if st.button("＋ New", key="__add_track_btn__", use_container_width=True):
            # ✅ Fetch FRESH tracks from DB (bypass cache) to get accurate naming
            from db import get_tracks_for_user
            fresh_tracks = get_tracks_for_user(st.session_state["user_db_id"])
            existing_names = [t.get("track_label") or "" for t in fresh_tracks]
            
            idx = 1
            while f"Track {idx}" in existing_names:
                idx += 1

            new_track = create_track_for_user(st.session_state["user_db_id"], f"Track {idx}")
            tm.ensure(new_track["id"])
            st.session_state.active_track_id = str(new_track["id"])
            st.session_state["last_active_track_id"] = str(new_track["id"])

            # ✅ Invalidate the tracks cache so the dropdown refreshes
            try:
                from cache import invalidate_tracks_cache
                invalidate_tracks_cache(st.session_state["user_db_id"])
            except Exception:
                pass

            st.session_state["__scroll_to_top__"] = True
            _clear_track_scoped_ui_state()
            st.rerun()

# ------------------------ Helper: derive Week # and Session # of week ------------------------
def _week_number_fallback() -> int:
    try:
        for attr in ("week_no", "week_number", "number", "index"):
            if hasattr(week.state, attr):
                return int(getattr(week.state, attr))
        if hasattr(week, "week_no"):
            return int(getattr(week, "week_no"))
    except Exception:
        pass
    return 1

def _current_week_number() -> int:
    try:
        return int(week.state.week_number)
    except Exception:
        return _week_number_fallback()

def _sessions_of_week_including_active() -> int:
    """
    Session # shown in the header.

    - Base = how many sessions have been CLOSED in this week for this track
      (tracked in sessions_this_week_by_track).
    - If there is an active session (non-zero P/L or line_active), we show +1
      for the in-progress one.
    """
    base = 0
    try:
        tid = st.session_state.get("active_track_id")
        if tid:
            base = _get_sessions_this_week(tid)
    except Exception:
        base = 0

    try:
        active_bump = 1 if (
            abs(float(eng.session_pl_units)) > 1e-9
            or bool(getattr(eng, "line_active", False))
        ) else 0
    except Exception:
        active_bump = 0

    return max(1, base + active_bump)

# ------------------------ Bind active track objects ------------------------
prev_active_id = st.session_state.get("last_active_track_id")
active_id = st.session_state.active_track_id

track_switched = (str(prev_active_id or "") != str(active_id or ""))
st.session_state["last_active_track_id"] = active_id

# ✅ Reset one-time rerun flag when switching tracks
if track_switched:
    st.session_state["_did_tracker_entry_rerun"] = False

bundle = tm.ensure(active_id)
eng: DiamondHybrid = bundle.eng
week: WeekManager = bundle.week
is_test = bool(st.session_state.testing_mode)

# 🔧 NEW: lazy-load DB state for this track once per app session
if not getattr(bundle, "_db_loaded", False):
    loaded = None
    try:
        loaded = load_track_state(st.session_state["user_db_id"], str(active_id))

        if loaded:
            # ✅ Single source of truth: TrackBundle import restores engine + week + counters
            bundle.import_state(loaded)

            # 🔧 ENFORCE week + engine P/L from saved payload (Tracker display depends on these)
            try:
                wk = (loaded or {}).get("week") or {}
                if "week_pl" in wk:
                    week.state.week_pl = float(wk.get("week_pl") or 0.0)
                if "week_number" in wk:
                    week.state.week_number = int(wk.get("week_number") or 1)
            except Exception as e:
                print(f"[tracker] post-import week enforce suppressed: {e!r}")

            try:
                eng_state = (loaded or {}).get("engine") or {}
                if "session_pl_units" in eng_state:
                    eng.session_pl_units = float(eng_state.get("session_pl_units") or 0.0)
                if "line_pl_units" in eng_state:
                    eng.line_pl_units = float(eng_state.get("line_pl_units") or 0.0)
            except Exception as e:
                print(f"[tracker] post-import engine enforce suppressed: {e!r}")

            # ✅ Hydrate week/session caches so refresh doesn't zero out the UI
            try:
                _hydrate_track_caches_from_bundle_and_db(active_id)
            except Exception:
                pass

            # ✅ Hydrate nb / LOD into session_state dicts (UI uses these)
            try:
                _set_nb(active_id, int(loaded.get("sessions_today", 0) or 0))
                _set_lod(active_id, int(loaded.get("lines_in_session", 0) or 0))
            except Exception as e:
                print(f"[tracker] cadence hydrate error for track_id={active_id}: {e!r}")

            # ✅ Hydrate sessions_this_week (if present) — use helper
            try:
                if active_id:
                    _set_sessions_this_week(active_id, int(loaded.get("sessions_this_week", 0) or 0))
                    hydr = st.session_state.setdefault("_sessions_week_hydrated", {})
                    hydr[str(active_id)] = False
                    st.session_state["_sessions_week_hydrated"] = hydr
            except Exception:
                pass

        # ✅ Mark loaded even if empty (prevents DB hit every rerun)
        bundle._db_loaded = True  # type: ignore[attr-defined]

    except Exception as e:
        print(f"[tracker] load_track_state error for track_id={active_id}: {e!r}")
        try:
            bundle._db_loaded = True  # type: ignore[attr-defined]
        except Exception:
            pass

# ✅ Ensure sessions_this_week cache is hydrated BEFORE header pills are computed (LIVE only)
if (not is_test) and st.session_state.get("user_db_id") and active_id:
    tid_s = str(active_id)
    wk_no = _current_week_number()

    sess_map = st.session_state.get("sessions_this_week_by_track", {}) or {}
    hydr = st.session_state.get("_sessions_week_hydrated", {}) or {}

    had_cache = (
        (tid_s in sess_map)
        and (sess_map.get(tid_s) is not None)
        and bool(hydr.get(tid_s, False))   # ✅ requires real DB hydration
    )

    if track_switched or (not had_cache):
        try:
            _ensure_week_cache_for_track(st.session_state["user_db_id"], tid_s, wk_no, force=track_switched)
        except Exception as e:
            print(f"[tracker] ensure_week_cache (entry) suppressed: {e!r}")

        # ✅ One-time rerun only if we were missing cache (fixes "Session #" not loading until click)
        if (not had_cache) and (not st.session_state.get("_did_tracker_entry_rerun", False)):
            st.session_state["_did_tracker_entry_rerun"] = True
            st.rerun()

# keep engine's $/u synced with stored session value
try:
    eng.set_unit_value(float(st.session_state.unit_value))
except Exception:
    pass

# ------------------------ Testing Mode sandbox snapshot/restore ------------------------
prev_test = bool(st.session_state.get("_prev_testing_mode", False))
is_test   = bool(st.session_state.get("testing_mode", False))
active_id = st.session_state.active_track_id
tid = str(active_id)  # ✅ stable key for snapshots

# Only run logic on an actual transition
if is_test != prev_test:

    if is_test and (not prev_test):
        # ▶ Entering Testing Mode: snapshot the current live state
        try:
            full_state = bundle.export_state()

            snaps = st.session_state.get("_testing_snapshots", {})
            if not isinstance(snaps, dict):
                snaps = {}

            snaps[tid] = {
                "bundle_state": full_state,
                "nb":  _get_nb(active_id),
                "lod": _get_lod(active_id),
            }
            st.session_state["_testing_snapshots"] = snaps
            print(f"[testing] snapshot captured for track {active_id}")
        except Exception as e:
            print(f"[testing] snapshot failed: {e!r}")

    elif (not is_test) and prev_test:
        # ◀ Leaving Testing Mode: restore the live state
        try:
            snaps = st.session_state.get("_testing_snapshots", {}) or {}
            snap = snaps.get(tid)

            if snap:
                full_state = snap.get("bundle_state", {}) or {}
                try:
                    bundle.import_state(full_state)
                except Exception as e:
                    print(f"[testing] import_state restore failed: {e!r}")

                _set_nb(active_id, int(snap.get("nb", 0) or 0))
                _set_lod(active_id, int(snap.get("lod", 0) or 0))

                # Recompute live week P/L cache used in header
                try:
                    st.session_state["_wpl_live"] = _live_week_pl(week, eng)
                except Exception:
                    pass

                print(f"[testing] state restored for track {active_id}")

            else:
                # Fallback: reload last persisted state from DB if no snapshot found
                try:
                    loaded = get_cached_track_state(st.session_state["user_db_id"], str(active_id), load_track_state)
                    if not loaded:
                        raise ValueError("No saved state found for active track")

                    bundle.import_state(loaded)

                    # 🔧 ENFORCE week + engine P/L from saved payload
                    try:
                        wk = (loaded or {}).get("week") or {}
                        if "week_pl" in wk:
                            week.state.week_pl = float(wk.get("week_pl") or 0.0)
                        if "week_number" in wk:
                            week.state.week_number = int(wk.get("week_number") or 1)
                    except Exception as e:
                        print(f"[tracker] post-import week enforce suppressed: {e!r}")

                    try:
                        eng_state = (loaded or {}).get("engine") or {}
                        if "session_pl_units" in eng_state:
                            eng.session_pl_units = float(eng_state.get("session_pl_units") or 0.0)
                        if "line_pl_units" in eng_state:
                            eng.line_pl_units = float(eng_state.get("line_pl_units") or 0.0)
                    except Exception as e:
                        print(f"[tracker] post-import engine enforce suppressed: {e!r}")

                    # now hydrate UI counters
                    _set_nb(active_id, int(loaded.get("sessions_today", 0) or 0))
                    _set_lod(active_id, int(loaded.get("lines_in_session", 0) or 0))

                    try:
                        bundle._db_loaded = True  # type: ignore[attr-defined]
                    except Exception:
                        pass

                    print(f"[testing] restored from DB fallback for track {active_id}")

                except Exception as e:
                    print(f"[testing] DB restore fallback failed: {e!r}")

        except Exception as e:
            print(f"[testing] testing-mode restore error: {e!r}")

# ✅ ALWAYS update prev state AFTER handling transitions (this is the whole fix)
st.session_state["_prev_testing_mode"] = is_test

# 🔧 helper: persist currently active track
def _persist_active_track():
    _persist_track(st.session_state.get("active_track_id"))

# 🔧 DEV ONLY: hard reset this track so testing doesn't get stuck
if DEV_MODE and bool(st.session_state.get("testing_mode", False)) and _is_admin():
    with st.expander("⚠️ Dev Reset — TESTING MODE ONLY"):
        st.markdown(
            """
**This tool appears *only* in Testing Mode.**

It performs a **hard wipe** of this track's *local progression*:

- Resets **week** back to Week 1  
- Resets **session P/L**  
- Resets **line P/L**  
- Resets **nb / LOD counters**  
- Resets **engine state**  
- Updates Supabase with the cleared state  

⚠️ **This DOES NOT delete or affect closed-week totals, event logs, or any other tracks.**  
⚠️ **Use only for debugging.**
""",
            unsafe_allow_html=True,
        )

        if st.button("Hard Reset This Track", key="dev_hard_reset"):
            # Reset the week back to Week 1 baseline
            try:
                week.reset_for_new_week(increment=False, last_closed_week=None)
            except Exception as e:
                print(f"[dev_reset] week.reset_for_new_week error: {e!r}")

            # Reset engine
            try:
                eng.session_pl_units = 0.0
                setattr(eng, "line_pl_units", 0.0)
                if hasattr(eng, "reset_for_new_session"):
                    eng.reset_for_new_session()
            except Exception as e:
                print(f"[dev_reset] engine reset error: {e!r}")

            # Reset counters for this track only
            tid = st.session_state.get("active_track_id")
            if tid:
                _set_nb(tid, 0)
                _set_lod(tid, 0)
                _set_sessions_this_week(tid, 0)

            # Reset cached display vars
            st.session_state._cache_session_pl = 0.0
            st.session_state._cache_week_pl = 0.0
            st.session_state["_wpl_live"] = 0.0
            st.session_state["_tone_name"] = "neutral"

            # Reset day key
            from datetime import datetime
            st.session_state.day_key = datetime.now().strftime("%Y-%m-%d")

            # Persist reset
            _persist_active_track()

            try:
                st.toast("Dev Reset Complete — Track cleared.", icon="⚠️")
            except Exception:
                pass

            st.rerun()

def _sync_week_pl_cache_after_booking():
    booked = float(getattr(week.state, "week_pl", 0.0) or 0.0)

    # keep engine aligned if it exists/you rely on it
    try:
        eng.week_pl_units = booked
    except Exception:
        pass

    # booked cache
    st.session_state["_cache_week_pl"] = booked

    # derived live cache (booked + current session)
    st.session_state["_wpl_live"] = _live_week_pl(week, eng)

# ------------------------ Tone helpers ------------------------
def _tone_theme(name: str):
    n = str(name or "neutral").lower()
    if n in ("green", "cautious"):
        return {
            "label": "green",
            "border": "#18c964",
            "glow": "rgba(24,201,100,0.40)",
            "bg_a": "#07140b",
            "bg_b": "#0e1d13",
            "panel_bg_a": "#0b140f",
            "panel_bg_b": "#111c17",
            "pulse": True,
            "pulse_scale": 1.0,
            "shadow": "0 6px 20px rgba(0,0,0,.45)",
        }
    if n in ("red", "defensive"):
        return {
            "label": "red",
            "border": "#ff5964",
            "glow": "rgba(255,89,100,0.45)",
            "bg_a": "#1a0b0c",
            "bg_b": "#220f10",
            "panel_bg_a": "#1b0f0f",
            "panel_bg_b": "#221414",
            "pulse": True,
            "pulse_scale": 1.25,
            "shadow": "0 6px 20px rgba(0,0,0,.45)",
        }
    return {
        "label": "neutral",
        "border": "#3a3a3a",
        "glow": "rgba(0,0,0,0.0)",
        "bg_a": "#0c0c0c",
        "bg_b": "#181818",
        "panel_bg_a": "#0f0f0f",
        "panel_bg_b": "#151515",
        "pulse": False,
        "pulse_scale": 1.0,
        "shadow": "0 6px 20px rgba(0,0,0,.45)",
    }


def _log_flip_events_if_any(week: WeekManager):
    """
    Detect:
      • Defensive ON/OFF flips
      • Cap target flips (optimizer raising/lowering cap)

    and log them to track_events so they survive refresh / relog.
    """
    track_id = st.session_state.get("active_track_id")
    if not track_id:
        return
    tid = str(track_id)  # ✅ normalize dict keys

    # 🔐 Don't write flip events from Testing Mode into the live DB
    if bool(st.session_state.get("testing_mode", False)):
        return

    # Pull per-track caches
    prev_def_map = st.session_state.get("_prev_defensive_by_track", {})
    prev_cap_map = st.session_state.get("_prev_cap_target_by_track", {})

    cur_def = bool(getattr(week, "defensive_mode", False) or getattr(week.state, "defensive_mode", False))
    cur_cap = int(getattr(week.state, "cap_target", 0))

    prev_def = prev_def_map.get(tid)
    prev_cap = prev_cap_map.get(tid)

    ts = _now_iso()

    # --- Defensive flip ---
    if prev_def is not None and prev_def != cur_def:
        try:
            if cur_def:
                title = "Defensive Mode ON"
                body = (
                    "The system flipped into Defensive mode based on recent drawdown / fragility. "
                    "Stakes are tightened to protect the bankroll."
                )
            else:
                title = "Defensive Mode OFF"
                body = (
                    "Defensive mode has been cleared. Conditions improved enough to return to "
                    "normal tone and sizing."
                )
            log_track_event(
                st.session_state["user_db_id"],
                track_id=track_id,
                kind="defensive",
                title=title,
                body=body,
                ts=ts,
            )
        except Exception as e:
            print(f"[flip_log] defensive flip log suppressed: {e!r}")

    # --- Cap / optimizer flip ---
    if prev_cap is not None and prev_cap != cur_cap and cur_cap > 0:
        try:
            if cur_cap > prev_cap:
                title = f"Cap Raised to +{cur_cap}u"
                body = (
                    f"Weekly cap raised from +{prev_cap}u to +{cur_cap}u after a strong early-week run. "
                    "Optimizer allowed the primary cap to engage."
                )
            else:
                title = f"Optimizer Cap Engaged (+{cur_cap}u)"
                body = (
                    f"Weekly cap tightened from +{prev_cap}u to +{cur_cap}u based on fragility/variance. "
                    "Optimizer flipped the cap down to preserve gains."
                )
            log_track_event(
                st.session_state["user_db_id"],
                track_id=track_id,
                kind="optimizer",
                title=title,
                body=body,
                ts=ts,
            )
        except Exception as e:
            print(f"[flip_log] cap flip log suppressed: {e!r}")

    # Update caches
    prev_def_map[tid] = cur_def
    prev_cap_map[tid] = cur_cap
    st.session_state["_prev_defensive_by_track"] = prev_def_map
    st.session_state["_prev_cap_target_by_track"] = prev_cap_map

# ------------------------ Continuation & nb/LOD helpers (SIM-FIDELITY) ------------------------
def _until_next_reset_hms() -> str:
    now = datetime.now(_TZ) if _TZ else datetime.now()
    tomorrow = (now + timedelta(days=1)).date()
    if _TZ:
        next_midnight = datetime.combine(tomorrow, time(0, 0, 0), tzinfo=_TZ)
    else:
        next_midnight = datetime.combine(tomorrow, time(0, 0, 0))
    remaining = max(0, int((next_midnight - now).total_seconds()))
    h = remaining // 3600
    m = (remaining % 3600) // 60
    s = remaining % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def _update_continuation_and_limits():
    glide_ok = True
    try:
        score = eng._fused_fragility_score()
        glide_ok = float(score) < float(FRAGILITY_STOP)
    except Exception:
        glide_ok = True

    active_id = st.session_state.get("active_track_id")
    nb_val  = _get_nb(active_id) if active_id else 0
    lod_val = _get_lod(active_id) if active_id else 0

    lod_limit_hit = (
        nb_val  >= int(SESSIONS_PER_DAY_MAX) or
        lod_val >= int(LINES_PER_SESSION_MAX)
    )
    try:
        week.set_glide_ok(bool(glide_ok))
        week.set_lod_limit_hit(bool(lod_limit_hit))
    except Exception:
        pass

# Keep defensive synced on init
eng.set_defensive(week.defensive_mode)

# ---- LIVE Tone hook (green / neutral / red) ----
tone = week.current_tone()  # live-aware now uses internal buffer

# Feed engine
if hasattr(eng, "update_week_tone"):
    eng.update_week_tone(tone)
else:
    try:
        eng.apply_week_tone(tone)
    except Exception:
        pass

# Continuation/nb/LOD update: run every render
_update_continuation_and_limits()

# Store for header
st.session_state["_tone_name"] = str(tone.get("name", tone.get("tone", "neutral")))

# If last event was a LINE reason, mirror *session* cache back only
st.session_state._cache_session_pl = float(getattr(eng, "session_pl_units", 0.0))

# ------------------------ Week-close copy helper ------------------------
def _week_close_modal_copy(tag: str, week_pl: float) -> tuple[str, str]:
    """
    Build the title/body for the Week Closed modal.

    NOTE:
    - Week closure is week-level: it locks this week and prepares the next one.
    - nb (sessions/day) is day-level: it is tied to the calendar day and does NOT reset
      just because a new week starts.
    """
    title = "Week Closed"
    body = ""

    if tag == "week_cap+400":
        title = "Week Closed (+400 — Primary Cap)"
        body = (
            "You hit the <b>primary weekly cap</b> and locked in a strong win for this week.<br><br>"
            "To keep the variance profile identical to the sim, play stops here for this week and you "
            "continue from a <b>new week</b>."
        )
    elif tag == "week_cap+300":
        title = "Week Closed (+300 — Optimizer Cap)"
        body = (
            "Your weekly P/L reached the <b>optimizer cap</b>. The optimizer flipped the cap down based on the "
            "week’s fragility profile and locked the win before pushing further.<br><br>"
            "This week is now finished and you continue from <b>Week N+1</b>."
        )
    elif tag == "week_guard-400":
        title = "Week Closed (−400 — Weekly Guard)"
        body = (
            "The <b>weekly guard</b> was hit. Downside is capped at this level to protect the bankroll.<br><br>"
            "Rather than digging deeper in the same week, the system closes it here and forces a fresh start "
            "from the next week."
        )
    elif tag == "red_stabilizer_lock":
        title = "Week Closed (🟥 Red Week — Early Containment)"
        body = (
            "The week dropped below <b>−85u</b> and the system detected worsening conditions "
            "(elevated fragility, consecutive losses, or sustained defensive mode).<br><br>"
            "Rather than risking a slide toward the <b>−400u guard</b>, the Red Stabilizer locked the week early "
            "to contain the drawdown. This is intentional: cut it, contain the red, reset clean.<br><br>"
            "Most red weeks end between <b>−60u and −90u</b> thanks to this mechanism — "
            "protecting your bankroll from rare but devastating tail events."
        )
    elif tag == "small_green_lock":
        title = "Week Closed (🟩 Smaller Green — Profit Locked)"
        body = (
            "A <b>smaller green week</b> was locked in after conditions turned fragile or continuation weakened.<br><br>"
            "Instead of forcing extra risk for a few more units, the system banks the win and advances you to the next week."
        )
    else:
        # Fallback for any unknown tag
        body = (
            "This week has been <b>locked</b> based on the weekly rules (cap, guard, or stabilizer).<br><br>"
            "You now continue from <b>Week N+1</b> with a fresh slate."
        )

    # Always append final summary + next-step explainer
    body += (
        f"<br><br><b>Final week P/L (booked):</b> {week_pl:.2f}u"
        "<br><br>---<br><br>"
        "<b>What happens next</b><br>"
        "• This week is now <b>permanently locked</b> — you can review it in your stats, but you <b>cannot keep playing in this week</b>.<br>"
        "• To continue playing, scroll down and use <b>Start Next Week</b> to move forward to <b>Week N+1</b> with a clean slate.<br>"
        "• Your <b>daily session count (nb)</b> is tied to the <b>calendar day</b>, not the week. "
        "Starting a new week <b>does not reset nb</b> — it only resets when a new day starts."
    )

    return title, body

# ======================== MAIN BODY (container) ========================
with st.container():

    st.session_state._cache_session_pl = float(getattr(eng, "session_pl_units", 0.0))
    st.session_state._cache_week_pl    = float(getattr(week.state, "week_pl", 0.0))  # ✅ booked truth

    # ------- Compact metrics row -------
    wk_no       = _week_number_fallback()
    sess_no_w   = _sessions_of_week_including_active()
    wk_no = _current_week_number()

    if not is_test:
        week_pl_data = _get_week_pl_booked_db(active_id, wk_no)
        # Handle both old (float) and new (dict) return types
        if isinstance(week_pl_data, dict):
            week_pl_booked_units = float(week_pl_data.get("units", 0.0))
            week_pl_booked_dollars = float(week_pl_data.get("dollars", 0.0))
        else:
            week_pl_booked_units = float(week_pl_data or 0.0)
            week_pl_booked_dollars = week_pl_booked_units * unit_value  # fallback

        # keep internal state aligned so tone/closures see the same truth
        try:
            week.state.week_pl = week_pl_booked_units
            eng.week_pl_units = week_pl_booked_units
        except Exception:
            pass
    else:
        # testing mode stays sandboxed
        week_pl_booked_units = float(week.state.week_pl)
        week_pl_booked_dollars = week_pl_booked_units * unit_value

    # booked cache only (truth)
    st.session_state["_cache_week_pl"] = float(week_pl_booked_units)

    # session cache only (truth-ish)
    st.session_state["_cache_session_pl"] = float(getattr(eng, "session_pl_units", 0.0) or 0.0)

    # derived live cache used for header/UI
    st.session_state["_wpl_live"] = _live_week_pl(week, eng)

    # if you still want a local variable for display:
    week_pl_live = float(st.session_state["_wpl_live"])

    sess_pl = float(st.session_state["_cache_session_pl"])
    line_pl = float(getattr(eng, "line_pl_units", 0.0))
    next_u  = float(eng.next_bet_units())
    unit_value = float(st.session_state.unit_value)

    def _pl_class(v: float) -> str:
        return "positive" if v >= 0 else "negative"

    c1, c2, c3, c4, c5, c6, c7 = st.columns([0.9, 1.2, 2.3, 2.3, 2.3, 2.1, 2.2])

    with c1:
        st.markdown(f"<div class='metric-chip'><span class='label'>Week #</span><span class='value'>{wk_no}</span></div>", unsafe_allow_html=True)
    with c2:
        st.markdown(f"<div class='metric-chip'><span class='label'>Session #</span><span class='value'>{sess_no_w}</span></div>", unsafe_allow_html=True)
    with c3:
        # Week P/L: booked dollars are historical, only live session uses current unit_value
        live_session_units = float(getattr(eng, "session_pl_units", 0.0) or 0.0)
        live_session_dollars = live_session_units * unit_value
        
        week_pl_display_units = week_pl_booked_units + live_session_units
        week_pl_display_dollars = week_pl_booked_dollars + live_session_dollars
        
        st.markdown(
            f"<div class='metric-chip {_pl_class(week_pl_display_units)}'><span class='label'>Week P/L</span>"
            f"<span class='value'>{_fmt_pl_both_precomputed(week_pl_display_units, week_pl_display_dollars)}</span></div>",
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            f"<div class='metric-chip {_pl_class(sess_pl)}'><span class='label'>Session P/L</span>"
            f"<span class='value'>{_fmt_pl_both(sess_pl, unit_value)}</span></div>",
            unsafe_allow_html=True,
        )
    with c5:
        st.markdown(
            f"<div class='metric-chip {_pl_class(line_pl)}'><span class='label'>Line P/L</span>"
            f"<span class='value'>{_fmt_pl_both(line_pl, unit_value)}</span></div>",
            unsafe_allow_html=True,
        )
    with c6:
        st.markdown(
            f"<div class='metric-chip'><span class='label'>Next Bet</span>"
            f"<span class='value'>{_fmt_units_dollars(next_u, unit_value)}</span></div>",
            unsafe_allow_html=True,
        )
    with c7:
        unit = float(st.session_state.unit_value)
        
        # Check if ANY track has mid-session or mid-line (lock unit size globally)
        def _any_track_active_for_lock() -> bool:
            for tid in tm.all_ids():
                try:
                    _bundle = tm.ensure(tid)
                    _eng = _bundle.eng
                    _sess = float(getattr(_eng, "session_pl_units", 0) or 0)
                    _line = float(getattr(_eng, "line_pl_units", 0) or 0)
                    if abs(_sess) > 0.001 or abs(_line) > 0.001:
                        return True
                except Exception:
                    pass
            return False
        
        _unit_locked = _any_track_active_for_lock()
        
        if _unit_locked:
            # Show locked state - no editing allowed mid-session
            st.markdown(
                f"<div style='padding:10px 12px;border:1px solid #374151;border-radius:8px;"
                f"background:linear-gradient(180deg,#1a1a1a,#141414);color:#9ca3af;"
                f"font-size:.9rem;text-align:center;cursor:not-allowed;'>"
                f"<div style='font-weight:700;color:#e5e7eb;'>${unit:.2f}/u 🔒</div>"
                f"<div style='font-size:.72rem;margin-top:4px;color:#6b7280;'>"
                f"Locked during active session</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
        else:
            # Normal popover when not in active play
            with st.popover(f"${unit:.2f}/u ✎", use_container_width=True):
                st.markdown("**Unit Size ($/unit)**")
                st.caption("This applies globally to all tracks.")
                new_unit = st.number_input(
                    label="$/unit",
                    min_value=0.5,
                    step=0.5,
                    value=unit,
                    key="unit_input_popover",
                    label_visibility="collapsed",
                )
                if st.button("Apply", key="apply_unit_popover", use_container_width=True):
                    st.session_state.unit_value = float(new_unit)
                    # ✅ Persist to DB for this user
                    try:
                        from db import set_user_unit_value
                        _uid = st.session_state.get("user_db_id")  # ← Get from session_state
                        if _uid:
                            set_user_unit_value(_uid, float(new_unit))
                    except Exception:
                        pass
                    try:
                        eng.set_unit_value(float(new_unit))
                    except Exception:
                        pass
                    try:
                        for tid in tm.all_ids():
                            _bundle = tm.ensure(tid)
                            _bundle.eng.set_unit_value(float(new_unit))
                    except Exception:
                        pass
                    try:
                        st.toast(f"Unit size set to ${float(new_unit):.2f}/u (all tracks)")
                    except Exception:
                        pass
                    _persist_active_track()
                    st.rerun()

    # --- sync defensive mode live BEFORE tone display (fix) ---
    try:
        week._maybe_flip_defensive()
    except Exception:
        pass
    eng.set_defensive(week.defensive_mode)

    # ---- Tone row ----
    _tone_name = st.session_state.get("_tone_name", "neutral").lower()
    _theme = _tone_theme(_tone_name)
    cap_target = int(week.state.cap_target)
    optimizer_threshold = 300
    # Log any defensive/cap flips after state is up-to-date
    _log_flip_events_if_any(week)

    badge_opt = (
        f"<span class='badge'>Optimizer cap (+{cap_target})</span>"
        if cap_target <= optimizer_threshold and cap_target > 0
        else ""
    )

    def_on = bool(week.defensive_mode)
    badge_def_cls = "badge-yellow" + ("" if def_on else " off")
    badge_def_txt = "ON" if def_on else "OFF"
    badge_def = f"<span class='{badge_def_cls}'>🛡️ Defensive: {badge_def_txt}</span>"

    # Soft Shield badge
    soft_shield_on = week.is_soft_shield_active()
    badge_ss = ""
    if soft_shield_on:
        badge_ss = "<span class='badge-yellow'>⚠️ Soft Shield</span>"

    # Raw counters from state
    active_id = st.session_state.get("active_track_id")
    nb_raw  = _get_nb(active_id) if active_id else 0
    lod_raw = _get_lod(active_id) if active_id else 0

    # Clamp just for display (never show 7/6 etc.)
    nb_used  = min(nb_raw, SESSIONS_PER_DAY_MAX)
    lod_used = min(lod_raw, LINES_PER_SESSION_MAX)

    nb_badge  = (
        f"<span class='badge' title='Sessions today (nb) / daily max'>"
        f"nb {nb_used}/{SESSIONS_PER_DAY_MAX}</span>"
    )
    lod_badge = (
        f"<span class='badge' title='Lines this session (LOD) / per-session max'>"
        f"LOD {lod_used}/{LINES_PER_SESSION_MAX}</span>"
    )

    # Midnight reset badge (always visible)
    hms_reset = _until_next_reset_hms()
    reset_badge = (
        f"<span class='badge' title='nb resets automatically at local midnight'>"
        f"Reset {hms_reset}</span>"
    )

    st.markdown(
    f"""
<div class="tone-chip">
  <span class="tone-dot" style="background:{_theme['border']}; border-color:{_theme['border']}"></span>
  <span>
    <b>{_tone_name}</b> · cap +{cap_target} · week P/L <b>live</b> {st.session_state.get('_wpl_live', 0.0):.2f}u
    {badge_opt}{badge_def}{badge_ss}{nb_badge}{lod_badge}{reset_badge}
  </span>
</div>
""",
        unsafe_allow_html=True,
    )
    
    # ---- nb/LOD alerts + inline explainer (tighter) ----
    lod_hint = ""
    try:
        NB_WARN_AT  = SESSIONS_PER_DAY_MAX - 1
        LOD_WARN_AT = LINES_PER_SESSION_MAX - 1

        # `nb_used` / `lod_used` already defined in the tone row above
        if nb_used < SESSIONS_PER_DAY_MAX and nb_used == NB_WARN_AT:
            st.info(f"📅 **Approaching daily limit**: nb {nb_used}/{SESSIONS_PER_DAY_MAX}.")
        if lod_used < LINES_PER_SESSION_MAX and lod_used == LOD_WARN_AT:
            lod_hint = (
                f" · LOD {lod_used}/{LINES_PER_SESSION_MAX} — one more line allowed this session."
            )
    except Exception:
        pass

    explainer = (
        "Tone shows week health; <b>Defensive ON</b> means bets are tightened. "
        "<b>Cap</b> is the weekly profit ceiling, and <b>nb / LOD</b> are your daily session and line limits. "
        f"When <b>nb</b> is maxed, it unlocks after the reset timer (<b>{hms_reset}</b>)."
        f"{lod_hint}"
    )

    # tighter vertical spacing than st.caption()
    st.markdown(
        f"<div style='margin-top:2px;margin-bottom:0px;font-size:.80rem;color:#9ca3af;'>{explainer}</div>",
        unsafe_allow_html=True,
    )

    # ---- Cap / guard proximity banners ----
    try:
        live_wpl = _live_week_pl(week, eng)
        guard_val = float(getattr(week, "_weekly_guard", -400))
        cap_target = int(getattr(getattr(week, "state", week), "cap_target", 400))
        CAP_ALERT_FRAC   = 0.90
        GUARD_ALERT_FRAC = 0.90
        if cap_target > 0 and live_wpl >= CAP_ALERT_FRAC * cap_target:
            st.info(
                f"⚠️ Approaching weekly cap (+{cap_target}u). "
                "The week will close after this session is banked."
            )
        elif guard_val < 0 and live_wpl <= GUARD_ALERT_FRAC * guard_val:
            st.warning(
                f"🛑 Nearing weekly guard ({guard_val}u). "
                "The week will close after this session is banked."
            )
    except Exception:
        pass

    # ------------------------ Session progress + Bet Banker Only + Week chip (same line) ------------------------
    cur = float(eng.session_pl_units)
    tgt = float(SESSION_GOAL_UNITS)
    sign = "+" if cur >= 0 else ""
    pct = 0.0 if tgt <= 1e-9 else max(0.0, min(1.0, cur / tgt))
    hit_goal = cur >= tgt
    is_negative = cur < 0.0

    # Build the week chip from WeekManager.current_tone()
    wk_num       = int(tone.get("week_number", 1))
    just_closed  = bool(tone.get("just_closed", False))
    last_closed  = tone.get("last_closed_week", None)

    if just_closed and last_closed:
        chip_html = f"<span class='chip'>🗓️ Week {int(last_closed)} complete → Week {wk_num} ready</span>"
        # Clear the banner so it only shows once
        try:
            week.mark_week_banner_seen()
        except Exception:
            pass
    else:
        chip_html = f"<span class='chip neutral'>Week {wk_num} active</span>"

    color = "#22c55e"; extra = ""; status_hint = ""
    if is_negative:
        color = "#ef4444"; status_hint = " — below 0"
    elif hit_goal:
        color = "#22c55e"; extra = "animation:textPulse 1.5s ease-in-out infinite;"; status_hint = " — goal hit"

    st.markdown(
        f"""
<div style="margin:2px 0 0 0; display:flex; align-items:center; gap:18px; flex-wrap:wrap;">
  <div style="font-size:.92rem; color:#dcdcdc; display:flex; align-items:center; gap:10px; flex-wrap:wrap;">
    <span>
      <span style="color:#a9a9a9;">Session progress:</span>
      <span style="font-weight:700; color:{color}; {extra}">
        {sign}{cur:.2f} / +{tgt:.0f}u
      </span>
      <span style="color:#8c8c8c; font-size:.82rem;">({int(round(pct*100))}%{status_hint})</span>
    </span>
    {chip_html}
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    # Testing Mode pill — sits directly under the session progress / Bet Banker row
    _testing_badge()
    
    # ------------------------ Next bet "hero" card ------------------------
    pv = eng.preview_next_bet()
    dollars   = int(pv["dollars"])
    units_eff = pv["effective_units"]
    
    # +233 Diamond+ config: Banker-only (100%)
    side_label = "BANKER"
    side_class = "side-banker"

    _tone_name = st.session_state.get("_tone_name", "neutral").lower()
    tone_class = "green" if _tone_name in ("green", "cautious") else ("red" if _tone_name in ("red", "defensive") else "neutral")
    pulse_cls = " nb-pulse" if tone_class in ("green", "red") else ""
    st.markdown(
        f"""
<div class="nb-card {tone_class}{pulse_cls}">
  <div style="font-size:1rem;color:#aaa;margin-bottom:8px;">Bet this amount next <span style="font-size:1.4rem;">&#8594;</span></div>
  <div style="font-size:3.2rem;font-weight:800;">${dollars}</div>
  <div style="font-size:1.2rem;color:#ccc;margin-bottom:12px;">({units_eff:.2f} units)</div>
  <div class="{side_class}">Bet {side_label}</div>
</div>
""",
        unsafe_allow_html=True,
    )

# Banker-only explainer
    st.markdown(
        "<div style='text-align:center;margin-top:-8px;margin-bottom:12px;font-size:.82rem;color:#9ca3af;'>"
        "Always bet <b>Banker</b> — the +233 config uses 100% Banker for optimal edge."
        "</div>",
        unsafe_allow_html=True,
    )

    # ------------------------ Steps remaining ------------------------
    rem = eng.remaining_steps()
    TOTAL_STEPS = 14
    cur_step = TOTAL_STEPS - len(rem) + 1 if rem else 1

    def _chip(v, i):
        if i == 0:
            return (f"<span style='display:inline-block;min-width:48px;text-align:center;"
                    f"border:2px solid #1E88E5;border-radius:12px;padding:8px 10px;"
                    f"margin:6px 6px 0 0;background:#0f172a;color:#e6f2ff;font-weight:700;'>{v:g}u</span>")
        if i == 1:
            return (f"<span style='display:inline-block;min-width:48px;text-align:center;"
                    f"border:1px solid #3a4a6a;border-radius:12px;padding:8px 10px;"
                    f"margin:6px 6px 0 0;background:#111827;color:#dbeafe;'>{v:g}u</span>")
        return (f"<span style='display:inline-block;min-width:48px;text-align:center;"
                f"border:1px solid #3a3a3a;border-radius:12px;padding:8px 10px;"
                f"margin:6px 6px 0 0;background:#1f1f1f;color:#f5f5f5;'>{v:g}u</span>")

    chips_html = "".join(_chip(v, i) for i, v in enumerate(rem))
    st.markdown(
        f"""
<div style="border:1px solid {_theme['border']};border-radius:14px;padding:16px 18px;
            background:linear-gradient(135deg,{_theme['panel_bg_a']},{_theme['panel_bg_b']});color:#eaeaea;margin:8px 0 18px 0;">
  <div style="display:flex;align-items:center;justify-content:space-between;">
    <div style="font-size:1.05rem;font-weight:800;">Line — Steps Remaining</div>
    <div style="font-size:0.95rem;color:#cfcfcf;">Step <b>{cur_step}</b> of <b>{TOTAL_STEPS}</b></div>
  </div>
  <div style="margin-top:10px;line-height:2.4;">{chips_html}</div>
  <div style="font-size:0.9rem;color:#b5b5b5;margin-top:10px;">
    Next two: {", ".join(f"{x:g}u" for x in rem[:2]) if rem else "—"}
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

# ------------------------ Manual Reset (week-level) ------------------------
def render_manual_week_reset(week: WeekManager, eng: DiamondHybrid):
    if not getattr(week.state, "closed", False):
        return

    # N+1 preview (safe fallback)
    try:
        current_week = int(week.state.week_number)
    except Exception:
        current_week = 1
    next_week = current_week + 1

    with st.expander("➡️ Start Next Week"):
        st.markdown(
            f"""
### Start Week {next_week}

Your current week is **locked** because one of the weekly conditions was hit  
(cap, guard, small green lock, or red stabilizer).

To keep execution consistent with the engine, you now **move forward**, not backward.

**What this does:**

- Archives the completed week  
- Starts **Week {next_week}** with a clean slate  
- Keeps all closed-week history, stats, and performance logs  
- Does *not* reset your daily nb counter (that resets at midnight only)

This cannot be undone.
""",
            unsafe_allow_html=True,
        )

        confirm = st.checkbox("I understand and want to begin the next week.")
        text = st.text_input("Type NEXT to confirm:", "", placeholder="NEXT")

        # Ensure no active line
        any_active = False
        try:
            any_active = eng.line_active
        except Exception:
            any_active = False

        if any_active:
            st.warning("Finish or close the current line before starting the next week.")
            return

        disabled = not (confirm and text.strip().upper() == "NEXT")

        if st.button("Start Next Week", disabled=disabled, type="primary"):
            # 1) WeekManager roll-forward (source of truth)
            week.reset_for_new_week()

            # 2) Reset per-track week/session counters
            try:
                active_id = st.session_state.get("active_track_id")
                if active_id:
                    _set_sessions_this_week(active_id, 0)
                    _set_lod(active_id, 0)
            except Exception:
                pass

            # 3) ✅ Week-roll: wipe engine + UI caches so header resets correctly
            try:
                eng.session_pl_units = 0.0
                eng.line_pl_units = 0.0
                if hasattr(eng, "week_pl_units"):
                    eng.week_pl_units = 0.0
                if hasattr(eng, "reset_for_new_session"):
                    eng.reset_for_new_session()
            except Exception as e:
                print(f"[week_roll] engine reset suppressed: {e!r}")

            try:
                st.session_state._cache_session_pl = 0.0
                st.session_state._cache_week_pl = 0.0
                st.session_state["_wpl_live"] = 0.0
                st.session_state["_tone_name"] = "neutral"
            except Exception:
                pass

            try:
                st.session_state.session_started_at = None
                st.session_state.line_started_at = None
            except Exception:
                pass

            # 4) Re-apply defensive after reset (fine either way)
            try:
                eng.set_defensive(week.defensive_mode)
            except Exception:
                pass

            # 5) Persist + rerun
            _persist_active_track()

            try:
                st.toast(f"Week {int(getattr(week.state, 'week_number', 1) or 1)} started.", icon="➡️")
            except Exception:
                pass

            st.rerun()

def _set_last_hand_meta(track_id, outcome: str, delta_units: float, can_undo: bool, block_reason: str = ""):
    st.session_state["_last_hand"] = {
        "track_id": str(track_id),
        "outcome": str(outcome),
        "delta_units": float(delta_units),
        "ts": _now_iso(),
        "can_undo": bool(can_undo),
    }
    st.session_state["_last_hand_block_reason"] = str(block_reason or "")


def undo_last_hand():
    active_id = st.session_state.get("active_track_id")
    is_test = bool(st.session_state.get("testing_mode", False))
    meta = st.session_state.get("_last_hand") or {}

    # Hard guards
    if not active_id:
        return
    if str(meta.get("track_id", "")) != str(active_id):
        return
    if not bool(meta.get("can_undo", False)):
        return
    if getattr(week.state, "closed", False):
        return
    if st.session_state.get("_confirm_end_session", False):
        return

    pre_state = st.session_state.get("_pre_hand_state")
    pre_tid   = str(st.session_state.get("_pre_hand_track_id") or "")
    if not pre_state:
        return
    if pre_tid != str(active_id):
        return

    delta = float(meta.get("delta_units", 0.0) or 0.0)
    if abs(delta) < 1e-12:
        st.session_state["_last_hand"] = None
        st.session_state["_last_hand_block_reason"] = ""
        st.session_state["_pre_hand_state"] = None
        st.session_state["_pre_hand_track_id"] = None
        return

    # 1) Restore EXACT pre-hand snapshot (true undo)
    try:
        bundle.import_state(pre_state)
    except Exception as e:
        print(f"[undo] import_state failed: {e!r}")
        return

    # 2) Ledger-safe DB log (LIVE only)
    try:
        if (not is_test) and st.session_state.get("user_db_id") and active_id:
            wk_no = _current_week_number()
            sess_idx = _get_session_index(str(active_id))
            hand_idx = _bump_hand_index(str(active_id))  # treat undo as an audit hand id

            log_hand_outcome(
                user_id=st.session_state["user_db_id"],
                track_id=str(active_id),
                week_number=wk_no,
                session_index=sess_idx,
                hand_index=hand_idx,
                delta_units=float(-delta),
                outcome="UNDO",
                ts=_now_iso(),
            )
    except Exception as e:
        print(f"[tracker] log_hand_outcome (UNDO) error: {e!r}")

    # 3) Local in-session stream (optional)
    try:
        st.session_state.hand_outcomes.append({
            "ts": _now_iso(),
            "track": active_id,
            "outcome": "UNDO",
            "delta_units": float(-delta),
        })
    except Exception:
        pass

    # 4) Recompute UI tone/caches
    try:
        live_tone = week.current_tone()
        if hasattr(eng, "update_week_tone"):
            eng.update_week_tone(live_tone)
        else:
            try:
                eng.apply_week_tone(live_tone)
            except Exception:
                pass

        try:
            week._maybe_flip_defensive()
        except Exception:
            pass
        eng.set_defensive(week.defensive_mode)

        st.session_state["_tone_name"] = str(live_tone.get("name", live_tone.get("tone", "neutral")))
        st.session_state["_wpl_live"] = _live_week_pl(week, eng)
    except Exception:
        pass

    st.session_state["_cache_session_pl"] = float(getattr(eng, "session_pl_units", 0.0))
    st.session_state["_cache_week_pl"]    = float(getattr(eng, "week_pl_units", 0.0))

    # 5) Clear undo + snapshot so it can’t be spammed
    st.session_state["_last_hand"] = None
    st.session_state["_last_hand_block_reason"] = ""
    st.session_state["_pre_hand_state"] = None
    st.session_state["_pre_hand_track_id"] = None

    try:
        st.toast("Undid last hand (state restored).", icon="↩️")
    except Exception:
        pass

    _persist_active_track()

# ------------------------ Core hand-settle helper ------------------------
def record_hand(outcome: str):
    """
    Thin click-path for WIN / LOSS / TIE.

    - Guards LOD (per-session line cap) before settling.
    - Settles the hand through the engine.
    - Logs hand, line, session, and week events (LIVE only).
    - Updates tone and cached P/L.
    - Handles auto line/session/week closures and queues modals.
    - Persists the active track state.
    """
    if outcome not in {"W", "L", "T"}:
        return

    active_id = st.session_state.get("active_track_id")

    # --- HARD GATE: cannot play/log hands while the week is closed ---
    if (not is_test) and getattr(week.state, "closed", False):
        queue_modal(
            "Week locked",
            "This week is closed. Use <b>Start Next Week</b> to continue.",
            kind="week",
        )
        _persist_active_track()
        st.rerun()

    # Hard guard: if LOD is already at cap, show modal and exit early.
    if (_get_lod(active_id) if active_id else 0) >= LINES_PER_SESSION_MAX:
        queue_modal(
            "Session LOD reached",
            "You’ve hit the per-session line limit. Use <b>End Session Now</b> to bank this session and start fresh.",
            kind="session",
        )
        st.rerun()

    # (everything else in your original record_hand continues below here)

    # --- Start timers if this is the first hand of the session / line ---
    try:
        from datetime import datetime as _dt_now  # local alias
        now_ts = _dt_now.now(_TZ) if _TZ else _dt_now.utcnow()

        if st.session_state.get("session_started_at") is None:
            st.session_state.session_started_at = now_ts

        if st.session_state.get("line_started_at") is None:
            st.session_state.line_started_at = now_ts
    except Exception as _e:
        print(f"[tracker] session/line timer init suppressed: {_e!r}")

    # ✅ TIE = counted hand (exposure/time/volume) but no progression movement
    if outcome == "T":
        # Count as a hand for cadence/fragility denominators (sim-fidelity)
        try:
            week.note_hand_played(is_test=is_test)
        except Exception:
            pass

        # Start timers already happened above; now optionally log for Player Stats
        try:
            st.session_state.hand_outcomes.append({
                "ts": _now_iso(),
                "track": active_id,
                "outcome": "T",
                "delta_units": 0.0,
            })
        except Exception:
            pass

        # (Optional) DB log as Δ0 for audit/history — does NOT affect P/L
        try:
            if (not is_test) and st.session_state.get("user_db_id") and active_id:
                wk_no = _current_week_number()
                sess_idx = _get_session_index(str(active_id))
                hand_idx = _bump_hand_index(str(active_id))

                log_hand_outcome(
                    user_id=st.session_state["user_db_id"],
                    track_id=str(active_id),
                    week_number=wk_no,
                    session_index=sess_idx,
                    hand_index=hand_idx,
                    delta_units=0.0,
                    outcome="T",
                    ts=_now_iso(),
                )
        except Exception as e:
            print(f"[tracker] log_hand_outcome (TIE) suppressed: {e!r}")

        try:
            st.toast("Tie: push (Δ 0.00u). Next bet unchanged.")
        except Exception:
            pass
        
        _persist_active_track()
        st.rerun()

    # --- Settle the hand through the engine ---
    # ✅ Snapshot PRE-hand state so Undo restores progression correctly (not just P/L)
    try:
        st.session_state["_pre_hand_state"] = bundle.export_state()
        st.session_state["_pre_hand_track_id"] = str(active_id)
    except Exception as e:
        print(f"[tracker] pre-hand snapshot failed: {e!r}")
        st.session_state["_pre_hand_state"] = None
        st.session_state["_pre_hand_track_id"] = None

    try:
        hd = eng.settle(outcome)
    except Exception as e:
        # ✅ If settle fails, don't leave a stale undo snapshot around
        st.session_state["_pre_hand_state"] = None
        st.session_state["_pre_hand_track_id"] = None
        print(f"[tracker] eng.settle failed: {e!r}")
        return

    reason = normalize_reason(getattr(hd, "reason", None))

    # Assume undo is allowed unless this hand closes line/session/week
    _set_last_hand_meta(
        track_id=active_id,
        outcome=outcome,
        delta_units=float(getattr(hd, "delta_units", 0.0)),
        can_undo=True,
        block_reason="",
    )

    # --- DB: persist this hand outcome (LIVE ONLY) ---
    try:
        if (not is_test) and st.session_state.get("user_db_id") and active_id:
            wk_no = _current_week_number()
            sess_idx = _get_session_index(str(active_id))
            hand_idx = _bump_hand_index(str(active_id))

            log_hand_outcome(
                user_id=st.session_state["user_db_id"],
                track_id=str(active_id),
                week_number=wk_no,
                session_index=sess_idx,
                hand_index=hand_idx,
                delta_units=float(getattr(hd, "delta_units", 0.0)),
                outcome=str(outcome),
                ts=_now_iso(),
            )
    except Exception as e:
        print(f"[tracker] log_hand_outcome error: {e!r}")

    # ---- Player Stats: per-hand log (in-session only) ----
    try:
        st.session_state.hand_outcomes.append({
            "ts": _now_iso(),
            "track": active_id,
            "outcome": outcome,
            "delta_units": float(getattr(hd, "delta_units", 0.0)),
        })
    except Exception:
        pass

    # Count this hand for fragility denominator
    try:
        week.note_hand_played(is_test=is_test)
    except Exception:
        pass

    # ---- Live tone & fragility feed ----
    try:
        if not is_test:
            week.feed_live_delta(hd.delta_units, is_test=False)
            if reason:
                week.record_hand_reason(reason, is_test=False)

        live_tone = week.current_tone()
        if hasattr(eng, "update_week_tone"):
            eng.update_week_tone(live_tone)
        else:
            try:
                eng.apply_week_tone(live_tone)
            except Exception:
                pass

        try:
            week._maybe_flip_defensive()
        except Exception:
            pass
        eng.set_defensive(week.defensive_mode)

        st.session_state["_tone_name"] = str(
            live_tone.get("name", live_tone.get("tone", "neutral"))
        )
        st.session_state["_wpl_live"] = _live_week_pl(week, eng)

    except Exception:
        pass

    # Toast for quick feedback
    try:
        st.toast(f"Hand settled: Δ {hd.delta_units:.2f}u (≈ ${hd.delta_dollars:.2f})")
    except Exception:
        pass

    # Cache P/L for continuity
    st.session_state._cache_session_pl = eng.session_pl_units
    st.session_state._cache_week_pl = eng.week_pl_units
    st.session_state._last_reason = reason

    # ---------------- LINE events — increment LOD (per session) ----------------
    if is_line_close(reason) and active_id:
        new_lod = _get_lod(active_id) + 1
        _set_lod(active_id, new_lod)
        _set_last_hand_meta(
            track_id=active_id,
            outcome=outcome,
            delta_units=float(getattr(hd, "delta_units", 0.0)),
            can_undo=False,
            block_reason="Unavailable because the last hand closed a line.",
        )

        # 🔧 Step 5: clear snapshot when undo becomes unavailable
        st.session_state["_pre_hand_state"] = None
        st.session_state["_pre_hand_track_id"] = None

        # Player Stats: line close log
        try:
            st.session_state.line_events.append({
                "ts": _now_iso(),
                "track": active_id,
                "reason": reason,
            })
        except Exception:
            pass

        # --- Compute line duration (sec) ---
        line_duration_sec = None
        try:
            from datetime import datetime as _dt_now
            start = st.session_state.get("line_started_at")
            if start is not None:
                now_ts = _dt_now.now(_TZ) if _TZ else _dt_now.utcnow()
                line_duration_sec = max(1.0, (now_ts - start).total_seconds())
        except Exception as _e:
            print(f"[tracker] line_duration_sec calc suppressed: {_e!r}")
            line_duration_sec = None

        # --- DB: persist line event (LIVE ONLY) ---
        try:
            if (not is_test) and st.session_state.get("user_db_id") and active_id:
                sess_idx = _get_session_index(str(active_id))

                log_line_event(
                    user_id=st.session_state["user_db_id"],
                    track_id=str(active_id),
                    week_number=_current_week_number(),
                    session_index=sess_idx,
                    reason=str(reason or ""),
                    ts=_now_iso(),
                    line_duration_sec=line_duration_sec,
                )
        except Exception as e:
            print(f"[tracker] log_line_event error: {e!r}")

        # Next line starts on next hand
        st.session_state.line_started_at = None

        # Mirror cached P/L for continuity
        eng.session_pl_units = float(st.session_state._cache_session_pl)
        eng.week_pl_units = float(st.session_state._cache_week_pl)

        _update_continuation_and_limits()

        title = {
            "smart_trim": "Smart Trim Triggered",
            "trailing_stop": "Trailing Stop Hit",
            "kicker_hit": "Kicker Goal Hit",
            "kicker": "Kicker Goal Hit",  # ✅ Add alias
            "line_cap": "Line Profit Cap Reached",
            "line_closed": "Line Closed",
            "line_complete": "Line Complete",  # ✅ Add for clarity
        }.get(reason, "Line Closed")

        queue_modal(
            title,
            "Line closed. A fresh line has started automatically.",
            kind="line",
        )

        # ✅ NEW: if that line close makes LOD hit max, immediately tell them
        if new_lod >= LINES_PER_SESSION_MAX:
            queue_modal(
                "Session LOD reached",
                "You’ve hit the per-session line limit. Use <b>End Session Now</b> to bank this session and start fresh.",
                kind="session",
            )

        _persist_active_track()
        st.rerun()

        # ---------------- SESSION events — ledger-first close -------------
    if is_session_close(reason):
        nb_before = _get_nb(active_id)

        # Log implicit line close if session ends mid-line (e.g., session_goal hit before line closed)
        try:
            line_started = st.session_state.get("line_started_at")
            if (not is_test) and line_started is not None and st.session_state.get("user_db_id") and active_id:
                line_duration_sec = None
                try:
                    now_ts = datetime.now(_TZ) if _TZ else datetime.utcnow()
                    line_duration_sec = max(1.0, (now_ts - line_started).total_seconds())
                except Exception:
                    pass
                
                log_line_event(
                    user_id=st.session_state["user_db_id"],
                    track_id=str(active_id),
                    week_number=_current_week_number(),
                    session_index=_get_session_index(str(active_id)),
                    reason="session_end",
                    ts=_now_iso(),
                    line_duration_sec=line_duration_sec,
                )
        except Exception as e:
            print(f"[tracker] implicit line_event (auto) error: {e!r}")

        _set_last_hand_meta(
            track_id=active_id,
            outcome=outcome,
            delta_units=float(getattr(hd, "delta_units", 0.0)),
            can_undo=False,
            block_reason="Unavailable because the last hand closed a session.",
        )
        st.session_state["_pre_hand_state"] = None
        st.session_state["_pre_hand_track_id"] = None

        # --- Compute session duration (sec) ---
        duration_sec = None
        try:
            from datetime import datetime as _dt_now
            start = st.session_state.get("session_started_at")
            if start is not None:
                now_ts = _dt_now.now(_TZ) if _TZ else _dt_now.utcnow()
                duration_sec = max(1.0, (now_ts - start).total_seconds())
        except Exception as _e:
            print(f"[tracker] session duration (auto) calc suppressed: {_e!r}")
            duration_sec = None

        # --- DB: persist session result (LIVE ONLY) ---
        db_session_write_ok = True
        try:
            if (not is_test) and st.session_state.get("user_db_id") and active_id:
                wk_no = _current_week_number()
                sess_idx = _get_session_index(active_id)

                log_session_result(
                    user_id=st.session_state["user_db_id"],
                    track_id=active_id,
                    week_number=wk_no,
                    session_index=sess_idx,
                    session_pl_units=float(st.session_state._cache_session_pl),
                    end_reason=reason,
                    ts=_now_iso(),
                    duration_sec=duration_sec,
                    soft_shield_active=week.is_soft_shield_active(),  # ✅ NEW
                )

                # After successful DB write, sync cache from DB
                try:
                    _ensure_week_cache_for_track(st.session_state["user_db_id"], str(active_id), wk_no)
                    _set_sessions_this_week(
                        active_id,
                        int(get_sessions_this_week_count(st.session_state["user_db_id"], str(active_id), wk_no) or 0),
                    )
                except Exception as e:
                    print(f"[tracker] sessions_this_week hydrate (auto) suppressed: {e!r}")

                _bump_session_index(active_id)

                # Invalidate totals cache so Overview/Stats refresh
                invalidate_player_totals_cache(st.session_state["user_db_id"])

        except Exception as e:
            db_session_write_ok = False
            print(f"[tracker] log_session_result (auto) error: {e!r}")
            print("[tracker] log_session_result (auto) traceback:\n" + traceback.format_exc())
            if DEV_MODE and _is_admin():
                st.error(f"log_session_result failed: {e!r}")

        # ---- DB write result gate ----
        if (not is_test) and (not db_session_write_ok):
            queue_modal(
                "DB write failed",
                "Session could not be banked (database write failed). Please try again — do not continue playing.",
                kind="session",
            )
            _persist_active_track()
            st.rerun()

        # ---- SUCCESS PATH (LIVE or TEST) ----
        if active_id:
            _set_nb(active_id, nb_before + 1)
            _set_lod(active_id, 0)

            nb_after = _get_nb(active_id)  # authoritative
            if nb_after >= SESSIONS_PER_DAY_MAX:
                queue_modal(
                    "Day Locked",
                    f"You hit the daily session cap (nb={SESSIONS_PER_DAY_MAX}).<br>"
                    f"Resets in <b>{_until_next_reset_hms()}</b> at local midnight.",
                    kind="session",  # keep as session so it persists/logs consistently
                )

        # ✅ Only append AFTER DB gate
        try:
            st.session_state.session_results.append({
                "ts": _now_iso(),
                "track": active_id,
                "pl_units": float(st.session_state._cache_session_pl),
                "end_reason": reason,
            })
        except Exception:
            pass

        # Book the session into the week (LIVE only)
        if not is_test:
            try:
                sess_pl_to_book = float(st.session_state._cache_session_pl)
                prev_booked = float(getattr(week.state, "week_pl", 0.0))

                week.end_session(sess_pl_to_book, is_test=False)

                now_booked = float(getattr(week.state, "week_pl", 0.0))
                if abs(now_booked - prev_booked) < 1e-9:
                    week.state.week_pl = prev_booked + sess_pl_to_book

                try:
                    eng.week_pl_units = now_booked
                except Exception:
                    pass

                _sync_week_pl_cache_after_booking()
            except Exception as e:
                print(f"[tracker] week.end_session (auto) error: {e!r}")

        _update_continuation_and_limits()

        # Hard reset for new session
        try:
            eng.session_pl_units = 0.0
            eng.line_pl_units = 0.0
            if hasattr(eng, "reset_for_new_session"):
                eng.reset_for_new_session()
        except Exception:
            pass

        try:
            if active_id:
                _reset_hand_index(str(active_id))
        except Exception:
            pass

        st.session_state._cache_session_pl = 0.0
        if active_id:
            _set_lod(active_id, 0)

        st.session_state.session_started_at = None
        st.session_state.line_started_at = None

        try:
            st.session_state["_wpl_live"] = _live_week_pl(week, eng)
        except Exception:
            pass

        # ✅ If this session ended the week, handle it *here* (before rerun)
        if bool(getattr(week.state, "closed", False)):
            tag = week.state.closed_reason
            wpl = week.state.week_pl

            # ✅ one-shot guard so reruns don't double-log
            wk_no = _current_week_number()
            wk_close_guard_key = f"_wk_close_logged__{active_id}__{wk_no}"
            already_logged = bool(st.session_state.get(wk_close_guard_key, False))

            if not already_logged:
                st.session_state[wk_close_guard_key] = True  # set immediately

                try:
                    if (not is_test) and st.session_state.get("user_db_id") and active_id:
                        log_week_closure(
                            user_id=st.session_state["user_db_id"],
                            track_id=str(active_id),
                            week_number=wk_no,
                            week_pl_units=wpl,
                            outcome_bucket=tag,
                            is_test=False,
                            ts=_now_iso(),
                        )
                        
                        # Invalidate caches so Overview/Stats show new data
                        invalidate_player_totals_cache(st.session_state["user_db_id"])
                        invalidate_closed_weeks_cache(st.session_state["user_db_id"])
                        
                except Exception as e:
                    # if DB logging fails, allow retry on next rerun
                    st.session_state[wk_close_guard_key] = False
                    print(f"[tracker] log_week_closure error: {e!r}")

            # Reset weekly session counter on closure (safe either way)
            try:
                if active_id:
                    _set_sessions_this_week(active_id, 0)
            except Exception:
                pass

            wk_title, wk_body = _week_close_modal_copy(tag, wpl)
            queue_modal(wk_title, wk_body, kind="week")

        title = {
            "session_cap": "Session Closed (Cap hit)",
            "session_guard": "Session Closed (Guard hit)",
            "session_closed": "Session Closed",
            "profit_preserve": "Profit Preserve Triggered",  # ✅ ADD
        }.get(reason, "Session Closed")

        body = {
            "profit_preserve": (
                "Smart Trim detected a fragile line while you had significant session gains.<br><br>"
                "<b>Profit Preserve</b> upgraded this to a full session close to lock in your profits.<br><br>"
                "Session P/L has been banked to the week."
            ),
        }.get(reason, "Session closed. Bank recorded.")

        queue_modal(title, body, kind="session")

        _persist_active_track()
        st.rerun()

# ================= Buttons (manual only) ======================
st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

clicked = None
week_locked = getattr(week.state, "closed", False)
active_id = st.session_state.get("active_track_id")
nb_locked  = (_get_nb(active_id) if active_id else 0) >= SESSIONS_PER_DAY_MAX
lod_locked = (_get_lod(active_id) if active_id else 0) >= LINES_PER_SESSION_MAX

if week_locked:
    st.info(
        "🔒 **This week is complete — start the next week to continue.**\n\n"
        "You’ve reached one of the weekly limits (cap, guard, or stabilizer), so this week has been "
        "**automatically closed**. Use the **Start Next Week** section below to move to **Week N+1**.",
        icon="🔒"
    )
    render_manual_week_reset(week, eng)

# ---- Day-locked (nb max) path ----
elif nb_locked:
    hms = _until_next_reset_hms()
    active_id = st.session_state.get("active_track_id")
    nb_raw_today = _get_nb(active_id) if active_id else 0
    display_nb_today = min(nb_raw_today, SESSIONS_PER_DAY_MAX)
    st.markdown(
        f"""
<div style="border:1px solid #7c2d12;border-radius:14px;padding:16px 18px;
            background:linear-gradient(135deg,#1b100b,#23130d);color:#fef3c7;
            box-shadow:0 8px 28px rgba(0,0,0,.45);">
  <div style="font-weight:900;font-size:1.05rem;display:flex;align-items:center;gap:8px;">
    <span>🔒</span><span>Day Locked — Daily session max reached (nb={SESSIONS_PER_DAY_MAX}).</span>
  </div>
  <div style="margin-top:8px;color:#fde68a;">
    Resets automatically at <b>local midnight</b>{' ' + ('('+_TZ.key+')' if _TZ else '')}.
    Time remaining: <code style="font-size:1rem;">{hms}</code>
  </div>
    <div style="margin-top:8px;color:#fcd34d;">Today: nb {display_nb_today}/{SESSIONS_PER_DAY_MAX}</div>
</div>
""",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<script>setTimeout(function(){window.location.reload();}, 30000);</script>",
        unsafe_allow_html=True,
    )

    # ------------------------ Admin: Force New Day ------------------------
    # Resets nb for active track by forcing a stale day_key.
    if _is_admin():
        if st.button("🔓 Force NEW DAY (Admin)", key="day_force_new"):
            st.session_state["day_key"] = "1900-01-01"
            _persist_active_track()
            st.rerun()

# ---- LOD-locked (per-session line max) path ----
elif lod_locked:
    st.markdown(
        f"""
<div style="border:1px solid #7c2d12;border-radius:14px;padding:16px 18px;
            background:linear-gradient(135deg,#1b100b,#23130d);color:#fee2e2;
            box-shadow:0 8px 28px rgba(0,0,0,.45);">
  <div style="font-weight:900;font-size:1.05rem;display:flex;align-items:center;gap:8px;">
    <span>🚫</span><span>Session LOD reached — no more hands allowed.</span>
  </div>
  <div style="margin-top:8px;color:#fecaca;">
    You’ve hit the per-session line limit (LOD = {LINES_PER_SESSION_MAX}/{LINES_PER_SESSION_MAX}). 
    Use <b>End Session Now</b> to bank this session and start a fresh one.
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

# ---- Normal play path ----
if (not week_locked) and (not nb_locked) and (not lod_locked):
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("WIN ✅", use_container_width=True, key="btn_win_main"):
            clicked = "W"
    with c2:
        if st.button("LOSS ❌", use_container_width=True, key="btn_loss_main"):
            clicked = "L"
    with c3:
        if st.button("TIE ⏸", use_container_width=True, key="btn_tie_main"):
            clicked = "T"

# ---- Undo last hand (clean, subtle, full-width) ----
meta = st.session_state.get("_last_hand") or {}
can_undo = (
    (not week_locked) and (not nb_locked) and (not lod_locked)
    and (not st.session_state.get("_confirm_end_session", False))
    and bool(meta)
    and (str(meta.get("track_id", "")) == str(active_id))
    and bool(meta.get("can_undo", False))
)

if (not week_locked) and (not nb_locked) and (not lod_locked):
    if st.button("↩️ Undo last hand", use_container_width=True, key="btn_undo_last", disabled=(not can_undo)):
        undo_last_hand()
        st.rerun()

    # Smart-guard caption (always shown, explains availability)
    block_reason = st.session_state.get("_last_hand_block_reason", "") or ""
    caption = (
        block_reason
        if block_reason
        else "Available only if the last hand didn’t close a line, session, or week."
    )
    st.markdown(
        f"<div style='margin-top:2px;margin-bottom:10px;font-size:.80rem;color:#9ca3af;'>{caption}</div>",
        unsafe_allow_html=True,
    )

# ---- Manual session end (guarded) ----
if (not week_locked) and (not nb_locked):

    # Step 1: arm confirm
    if not st.session_state.get("_confirm_end_session", False):
        if st.button("End Session Now", type="primary", use_container_width=True, key="lod_end_now_arm"):
            st.session_state["_confirm_end_session"] = True
            st.rerun()

    # Step 2: confirm / cancel
    else:
        st.warning("⚠️ End the session now? This will bank the current session and start a fresh one next time.")

        cc1, cc2 = st.columns([1, 1])
        with cc1:
            do_end = st.button("Yes — End Session", type="primary", use_container_width=True, key="lod_end_now_confirm")
        with cc2:
            if st.button("Cancel", use_container_width=True, key="lod_end_now_cancel"):
                st.session_state["_confirm_end_session"] = False
                st.rerun()

        if do_end:
            # Immediately drop the confirm state so refreshes don't re-show it
            st.session_state["_confirm_end_session"] = False

            manual_reason = normalize_reason("session_closed")

            nb_before = _get_nb(active_id)

            # Log implicit line close if session ends mid-line
            try:
                line_started = st.session_state.get("line_started_at")
                if (not is_test) and line_started is not None and st.session_state.get("user_db_id") and active_id:
                    line_duration_sec = None
                    try:
                        now_ts = datetime.now(_TZ) if _TZ else datetime.utcnow()
                        line_duration_sec = max(1.0, (now_ts - line_started).total_seconds())
                    except Exception:
                        pass
                    
                    log_line_event(
                        user_id=st.session_state["user_db_id"],
                        track_id=str(active_id),
                        week_number=_current_week_number(),
                        session_index=_get_session_index(str(active_id)),
                        reason="session_end",
                        ts=_now_iso(),
                        line_duration_sec=line_duration_sec,
                    )
            except Exception as e:
                print(f"[tracker] implicit line_event (manual) error: {e!r}")

            # 🔧 Step 5: manual session end makes undo unavailable — clear snapshot
            _set_last_hand_meta(
                track_id=active_id,
                outcome="MANUAL_END",
                delta_units=0.0,
                can_undo=False,
                block_reason="Unavailable because the session was closed manually.",
            )
            st.session_state["_pre_hand_state"] = None
            st.session_state["_pre_hand_track_id"] = None

            # --- Compute session duration (sec) ---
            duration_sec = None
            try:
                from datetime import datetime as _dt_now
                start = st.session_state.get("session_started_at")
                if start is not None:
                    now_ts = _dt_now.now(_TZ) if _TZ else _dt_now.utcnow()
                    duration_sec = max(1.0, (now_ts - start).total_seconds())
            except Exception as _e:
                print(f"[tracker] session duration (lod_end_now) calc suppressed: {_e!r}")
                duration_sec = None

            # --- DB: persist session result (LIVE ONLY) ---
            db_session_write_ok = True

            try:
                if (not is_test) and st.session_state.get("user_db_id") and active_id:
                    wk_no = _current_week_number()
                    sess_idx = _get_session_index(active_id)

                    log_session_result(
                        user_id=st.session_state["user_db_id"],
                        track_id=active_id,
                        week_number=wk_no,
                        session_index=sess_idx,
                        session_pl_units=float(st.session_state._cache_session_pl),
                        end_reason=manual_reason,
                        ts=_now_iso(),
                        duration_sec=duration_sec,
                        soft_shield_active=week.is_soft_shield_active(),  # ✅ NEW
                    )

                    try:
                        _ensure_week_cache_for_track(st.session_state["user_db_id"], str(active_id), wk_no)
                        _set_sessions_this_week(active_id, int(get_sessions_this_week_count(st.session_state["user_db_id"], str(active_id), wk_no) or 0))
                    except Exception as e:
                        print(f"[tracker] sessions_this_week hydrate (manual) suppressed: {e!r}")

                    _bump_session_index(active_id)

                    # ✅ Invalidate caches so Overview/Stats refresh immediately
                    invalidate_player_totals_cache(st.session_state["user_db_id"])

            except Exception as e:
                db_session_write_ok = False
                print(f"[tracker] log_session_result (manual) error: {e!r}")
                print("[tracker] log_session_result (manual) traceback:\n" + traceback.format_exc())
                if DEV_MODE and _is_admin():
                    st.error(f"log_session_result failed: {e!r}")

            # ✅ LIVE: if DB write failed, DO NOT close locally
            if (not is_test) and (not db_session_write_ok):
                queue_modal(
                    "DB write failed",
                    "Session could not be banked (database write failed). Please try again — do not continue playing.",
                    kind="session",
                )
                _persist_active_track()
                st.rerun()

            # ---- SUCCESS PATH ----
            if active_id:
                _set_nb(active_id, nb_before + 1)
                _set_lod(active_id, 0)

                nb_after = _get_nb(active_id)  # authoritative
                if nb_after >= SESSIONS_PER_DAY_MAX:
                    queue_modal(
                        "Day Locked",
                        f"You hit the daily session cap (nb={SESSIONS_PER_DAY_MAX}).<br>"
                        f"Resets in <b>{_until_next_reset_hms()}</b> at local midnight.",
                        kind="session",
                    )

            # ✅ Now safe to log local Player Stats (only after DB success gate)
            try:
                st.session_state.session_results.append({
                    "ts": _now_iso(),
                    "track": active_id,
                    "pl_units": float(st.session_state._cache_session_pl),
                    "end_reason": manual_reason,
                })
            except Exception:
                pass

            # --- Book the session into the week (LIVE only)
            if not is_test:
                try:
                    sess_pl_to_book = float(st.session_state._cache_session_pl)
                    prev_booked = float(getattr(week.state, "week_pl", 0.0))

                    week.end_session(sess_pl_to_book, is_test=False)

                    now_booked = float(getattr(week.state, "week_pl", 0.0))
                    if abs(now_booked - prev_booked) < 1e-9:
                        week.state.week_pl = prev_booked + sess_pl_to_book

                    _sync_week_pl_cache_after_booking()
                except Exception as e:
                    print(f"[tracker] week.end_session (manual) error: {e!r}")

            _update_continuation_and_limits()

            # Hard reset for a fresh session (ALWAYS)
            try:
                eng.session_pl_units = 0.0
                eng.line_pl_units = 0.0
                if hasattr(eng, "reset_for_new_session"):
                    eng.reset_for_new_session()
            except Exception:
                pass

            st.session_state._cache_session_pl = 0.0
            if active_id:
                _set_lod(active_id, 0)
                _reset_hand_index(str(active_id))

            st.session_state.session_started_at = None
            st.session_state.line_started_at = None

            # ✅ Queue modals BEFORE rerun
            queue_modal(
                "Session Closed",
                "Session closed manually. Bank recorded and a fresh session will start next time you play.",
                kind="session",
            )

            # ✅ If that booking also closed the week, queue the week modal too
            if bool(getattr(week.state, "closed", False)):
                tag = week.state.closed_reason
                wpl = week.state.week_pl

                try:
                    if (not is_test) and st.session_state.get("user_db_id") and active_id:
                        log_week_closure(
                            user_id=st.session_state["user_db_id"],
                            track_id=str(active_id),
                            week_number=_current_week_number(),
                            week_pl_units=wpl,
                            outcome_bucket=tag,
                            is_test=False,
                            ts=_now_iso(),
                        )
                        
                        # Invalidate caches so Overview/Stats show new data
                        invalidate_player_totals_cache(st.session_state["user_db_id"])
                        invalidate_closed_weeks_cache(st.session_state["user_db_id"])
                        
                except Exception as e:
                    print(f"[tracker] log_week_closure (lod_end_now) error: {e!r}")

                try:
                    if active_id:
                        _set_sessions_this_week(active_id, 0)
                except Exception:
                    pass

                wk_title, wk_body = _week_close_modal_copy(tag, wpl)
                queue_modal(wk_title, wk_body, kind="week")

            _persist_active_track()
            st.rerun()

# ---- Handle W/L/T clicks ----
if clicked in {"W", "L", "T"}:
    record_hand(clicked)
    st.rerun()

# ------------------------ Event Feed (Live) ------------------------
with st.expander("🗓️ Event Feed (Live)", expanded=False):
    st.markdown(
        """
<p style="color:#9ca3af;font-size:.88rem;margin-bottom:8px;">
The Event Feed shows <b>only live events</b>:
line & session closes, Defensive <b>ON/OFF</b> flips, cap changes, and week closures.
<br><br>
<strong>Note:</strong> Anything you do in <b>Testing Mode</b> is sandboxed — it will not appear here
and does not touch your live weekly history.
</p>
""",
        unsafe_allow_html=True,
    )

    kinds = ["all", "line", "session", "week", "defensive", "optimizer"]
    kind_filter = st.selectbox("Filter", kinds, index=0, label_visibility="collapsed")

    limit = 50  # last 50 only (DB also prunes beyond 50 per track)

    events: List[Dict[str, Any]] = []
    try:
        active_id = st.session_state.get("active_track_id")
        if active_id:
            events = fetch_track_events(st.session_state["user_db_id"], active_id, limit=limit)
    except Exception as e:
        print(f"[EventFeed] fetch_track_events error: {e!r}")
        events = []

    if kind_filter != "all":
        events = [e for e in events if str(e.get("kind", "")) == kind_filter]

    if not events:
        st.info("No recent events logged yet.")
    else:
        for e in events:
            ts    = e.get("ts", "")
            title = e.get("title", "")
            body  = e.get("body", "")
            kind  = e.get("kind", "")

            if kind == "line":
                icon = "✂️"
            elif kind == "session":
                icon = "📘"
            elif kind == "week":
                icon = "📅"
            elif kind == "defensive":
                icon = "🛡️"
            elif kind == "optimizer":
                icon = "🧠"
            else:
                icon = "💡"

            st.markdown(
                f"""
                <div style="margin:8px 0;padding:12px 14px;border-radius:12px;
                            border:1px solid #2b2b2b;background:linear-gradient(180deg,#101010,#171717);
                            color:#eaeaea;">
                    <div style="font-weight:700;font-size:1rem;">{icon} {title}</div>
                    <div style="color:#c5c5c5;margin-top:4px;">{body}</div>
                    <div style="color:#777;font-size:.8rem;margin-top:6px;">{ts}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

    st.caption(
        "Event Feed is persisted per track (last 50 events). The engine still enforces all rules automatically."
    )

# ------------------------ Daily pacing explainer — bottom ------------------------
with st.expander("🧭 What’s happening right now?"):
    active_id = st.session_state.get("active_track_id")
    nb_raw  = _get_nb(active_id) if active_id else 0
    lod_raw = _get_lod(active_id) if active_id else 0

    nb_used  = min(nb_raw, SESSIONS_PER_DAY_MAX)
    lod_used = min(lod_raw, LINES_PER_SESSION_MAX)

    tone_name = str(st.session_state.get("_tone_name", "neutral")).lower()
    cap_target = int(getattr(week.state, "cap_target", 0))
    guard_val = getattr(week.state, "weekly_guard", getattr(week, "weekly_guard", -400))

    # Re-use the same lock flags as main body
    week_locked_local = getattr(week.state, "closed", False)
    nb_locked_local  = nb_used >= SESSIONS_PER_DAY_MAX
    lod_locked_local = lod_used >= LINES_PER_SESSION_MAX

    # Time until nb reset
    hms = _until_next_reset_hms()
    tz_label = getattr(_TZ, "key", "local time") if _TZ else "local time"

    st.markdown(
        f"""
### Track status (today)

- **nb — sessions today on this Track:** `{nb_used}/{SESSIONS_PER_DAY_MAX}`  
- **LOD — lines in this session:** `{lod_used}/{LINES_PER_SESSION_MAX}`  
- **Tone:** `{tone_name}` · **cap:** `+{cap_target}u` · **guard:** `{guard_val}u`  
- **Week locked?** `{"Yes" if week_locked_local else "No"}`  
- **Day locked (nb max)?** `{"Yes" if nb_locked_local else "No"}`  
- **Session LOD reached?** `{"Yes" if lod_locked_local else "No"}`  

### Daily reset

- `nb` (sessions/day) resets at **local midnight ({tz_label})**.  
- Time until reset: `{hms}`.  
- `LOD` (lines/session) resets **every time you bank a session**  
  (either auto-close or **End Session Now**).

### How to read this

- When **nb hits its cap**, this Track is **done for the day** — even if the week is still open.  
- When **LOD hits its cap**, you must use **End Session Now** to bank this session and start a fresh one.  
- When the **week locks**, you can’t play this Track again until you hit **Start Next Week**.  
- Tone (`green / neutral / red`) and the cap/guard are coming from the same week logic used on the
  other pages — this box is just a snapshot of where you are in that lifecycle right now.
""",
        unsafe_allow_html=True,
    )

# ------------------------ DEV: Force Week Close (admin only) ------------------------
if DEV_MODE and (not bool(st.session_state.get("testing_mode", False))) and _is_admin():
    with st.expander("⚠️ DEV — Force Week Close (Admin Only)", expanded=False):
        st.caption("Closes the current week immediately for the active track (for testing). Uses DB-unique week_closures to prevent duplicates on refresh.")

        tid = st.session_state.get("active_track_id")
        if not tid:
            st.warning("No active track selected.")
        else:
            # show current truth
            try:
                current_week_no = int(getattr(week.state, "week_number", 1) or 1)
            except Exception:
                current_week_no = 1

            st.write({
                "active_track_id": str(tid),
                "week_number": current_week_no,
                "week_closed": bool(getattr(week.state, "closed", False)),
                "closed_reason": getattr(week.state, "closed_reason", ""),
                "week_pl": float(getattr(week.state, "week_pl", 0.0) or 0.0),
            })

            reason = st.selectbox(
                "Closed reason (bucket)",
                [
                    "week_cap+400",
                    "week_cap+300",
                    "small_green_lock",
                    "red_stabilizer_lock",
                    "week_guard-400",
                    "DEV_FORCE_CLOSE",
                ],
                index=5,
                key="dev_force_week_reason",
            )

            if st.button("Force Close Week Now", type="primary", key="dev_force_week_close"):
                # 1) Force-close in WeekManager state (source of truth)
                try:
                    week.state.closed = True
                    week.state.closed_reason = str(reason)
                    week.state.allow_new_entries = False
                    week.state.locked = True
                    # keep lock_kind meaningful
                    week.state.lock_kind = "DEV_FORCE_CLOSE"
                except Exception as e:
                    st.error(f"Failed to force-close week state: {e!r}")
                    st.stop()

                # 2) Log week closure to DB (LIVE only)
                try:
                    if st.session_state.get("user_db_id") and tid:
                        log_week_closure(
                            user_id=st.session_state["user_db_id"],
                            track_id=str(tid),
                            week_number=_current_week_number(),
                            week_pl_units=float(getattr(week.state, "week_pl", 0.0) or 0.0),
                            outcome_bucket=str(reason),
                            is_test=False,
                            ts=_now_iso(),
                        )
                except Exception as e:
                    st.error(f"DB log_week_closure failed: {e!r}")
                    # Still persist state so UI shows closed; DB safety is handled by unique/upsert anyway.

                # 3) Persist track state so refresh/device matches
                _persist_active_track()

                try:
                    st.toast("Week forced closed. Now refresh to test duplicate protection.", icon="✅")
                except Exception:
                    pass

                st.rerun()

# 🔧 DEV ONLY: force-close active line (testing escape hatch)
if DEV_MODE and _is_admin():
    with st.expander("🧯 Dev Tools — Line Recovery"):
        try:
            any_active = bool(getattr(eng, "line_active", False))
        except Exception:
            any_active = False

        if any_active:
            st.warning("Active line detected. This blocks starting the next week.")

            if st.button("Force Close Line (DEV ONLY)", type="secondary"):
                try:
                    # Clear engine line state
                    if hasattr(eng, "line_active"):
                        eng.line_active = False
                    if hasattr(eng, "line_pl_units"):
                        eng.line_pl_units = 0.0

                    # Reset LOD safely for this track
                    tid = st.session_state.get("active_track_id")
                    if tid:
                        _set_lod(tid, 0)

                    # Clear line timer
                    st.session_state.line_started_at = None

                    _persist_active_track()

                    st.toast("Line force-closed. You may now start the next week.", icon="🧯")
                    st.rerun()

                except Exception as e:
                    st.error(f"Force-close failed: {e!r}")
        else:
            st.info("No active line detected.")

if DEV_MODE and _is_admin():
    with st.expander("🧪 DEBUG — Identity & Session State", expanded=False):
        tid = st.session_state.get("active_track_id")
        tid_s = str(tid) if tid else None

        # ensure cache hydrated for active track before debug reads it
        if tid_s:
            _hydrate_track_caches_from_bundle_and_db(tid_s)

        # per-track cadence (authoritative)
        nb = _get_nb(tid) if tid else None
        lod = _get_lod(tid) if tid else None

        # cached maps
        sess_map = st.session_state.get("sessions_this_week_by_track", {}) or {}

        # bundle week number truth
        bundle_week_no = None
        try:
            if tid:
                b = tm.ensure(tid)
                bundle_week_no = int(getattr(b.week.state, "week_number", 1) or 1)
        except Exception:
            pass

        # DB truth for sessions/week (use bundle week)
        db_sessions_week = None
        try:
            if tid and bundle_week_no is not None:
                db_sessions_week = _get_sessions_this_week_db(tid, int(bundle_week_no))
        except Exception:
            pass

        st.write({
            "auth_id": AUTH_ID,
            "user_db_id": USER_ID,
            "active_track_id": tid_s,
            "tracks_in_tm": tm.all_ids(),

            "sessions_today(active_track)": nb,
            "lines_in_session(active_track)": lod,

            "sessions_this_week_cached_map": sess_map,
            "sessions_this_week_cached_for_active": sess_map.get(tid_s) if tid_s else None,

            "sessions_this_week_db_for_active": get_sessions_this_week_count(
                st.session_state["user_db_id"], tid_s, int(bundle_week_no)
            ) if tid_s else None,

            "week_no_bundle_for_active": bundle_week_no,

            "testing_mode": st.session_state.get("testing_mode"),
        })

# ------------------------ Bet tightening verifier (live) ------------------------
SHOW_BET_TIGHTENING_VERIFIER = False  # set True when you want to debug this

if SHOW_BET_TIGHTENING_VERIFIER:
    with st.expander("🔎 Bet tightening verifier (live)"):
        try:
            current_tone = getattr(eng, "_tone", {"tau_delta": 0.0, "glide_scale": 1.0})

            def _tone_dict(label: str):
                if label == "neutral":
                    return {"tau_delta": 0.0, "glide_scale": 1.0}
                if label == "green":
                    return {"tau_delta": -0.02, "glide_scale": 0.80}
                if label == "red":
                    return {"tau_delta": -0.02, "glide_scale": 0.70}
                return dict(current_tone)

            def preview_with_tone(tone_dict: dict) -> tuple[float, float]:
                eng.update_week_tone(tone_dict)
                pv = eng.preview_next_bet()
                units_planned = float(pv.get("units", 0.0))
                eff_units     = float(pv.get("effective_units", units_planned))
                return units_planned, eff_units

            units_neutral, eff_neutral = preview_with_tone(_tone_dict("neutral"))
            units_green,   eff_green   = preview_with_tone(_tone_dict("green"))
            units_red,     eff_red     = preview_with_tone(_tone_dict("red"))
            units_live,    eff_live    = preview_with_tone(dict(current_tone))

            # restore original tone
            eng.update_week_tone(dict(current_tone))

            def pct_tight(x, base):
                return 0.0 if base <= 1e-9 else (1.0 - (x / base)) * 100.0

            st.write({
                "Planned Units — NEUTRAL": round(units_neutral, 3),
                "Planned Units — GREEN":   round(units_green, 3),
                "Planned Units — RED":     round(units_red, 3),
                "Planned Units — LIVE":    round(units_live, 3),
                "Tight vs NEUTRAL — GREEN (%)": round(pct_tight(units_green, units_neutral), 2),
                "Tight vs NEUTRAL — RED (%)":   round(pct_tight(units_red, units_neutral), 2),
                "Tight vs NEUTRAL — LIVE (%)":  round(pct_tight(units_live, units_neutral), 2),
                "Effective Units — NEUTRAL": round(eff_neutral, 3),
                "Effective Units — GREEN":   round(eff_green, 3),
                "Effective Units — RED":     round(eff_red, 3),
                "Effective Units — LIVE":    round(eff_live, 3),
            })

            score, choppy = eng._fused_fragility_score()
            tau = eng._tau_target(choppy)
            st.caption(
                f"fused_score={score:.3f} • choppy={choppy} • τ_effective={tau:.3f} • "
                f"live week P/L={st.session_state.get('_wpl_live', 0.0):.2f}u"
            )
        except Exception as e:
            st.caption(f"(bet tightening verifier suppressed an error: {e})")
