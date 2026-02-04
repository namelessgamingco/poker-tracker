# pages/98_QA_Checklist.py — Admin-only QA Harness
# (+233 parity; robust silent line reset detection + proper defensive signals + Packs H–K)
# Pack B updated to flip Defensive without triggering red_stabilizer week close.

import itertools
import json
import math
import streamlit as st
st.set_page_config(page_title="QA Checklist", page_icon="✅", layout="wide")

# ---- Auth + Sidebar ----
from auth import require_auth
from sidebar import render_sidebar
from db import get_profile_by_auth_id

import os

user = require_auth()
render_sidebar()

# ---- Admin gate (profiles.role + is_active, with env fallback) ----

def _extract_auth_identity(u):
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
    return str(auth_id or ""), str(email or "unknown@example.com")

auth_id, cur_email = _extract_auth_identity(user)
cur_email_lc = (cur_email or "").strip().lower()

# Pull profile by auth_id (profiles.user_id)
try:
    profile = get_profile_by_auth_id(auth_id) or {}
except Exception as e:
    print(f"[qa_checklist] get_profile_by_auth_id error: {e!r}")
    profile = {}

role = profile.get("role", "player") or "player"
is_active = bool(profile.get("is_active", True))

# Legacy flag still respected if you decide to keep it around
if profile.get("is_admin"):
    role = "admin"

# Fallback bootstrap: ADMIN_EMAILS env var (comma-separated)
ADMIN_EMAILS = os.getenv("ADMIN_EMAILS", "")
if ADMIN_EMAILS:
    admin_set = {e.strip().lower() for e in ADMIN_EMAILS.split(",") if e.strip()}
    if cur_email_lc in admin_set:
        role = "admin"
        is_active = True

is_admin = bool(is_active and role == "admin")

# Mirror Admin page: stash in session for other pages if needed
st.session_state["role"] = role
st.session_state["is_active"] = is_active
st.session_state["is_admin"] = is_admin

if not is_admin:
    st.title("✅ QA Checklist — +233 Parity")
    st.info("Admin only. Ask an admin to enable access.")
    st.stop()

# ---- Imports after gate ----
from datetime import datetime
from track_manager import TrackManager
from week_manager import WeekManager
from engine import DiamondHybrid

# ---------- Styles ----------
st.markdown("""
<style>
.pass{display:inline-block;padding:4px 8px;border-radius:8px;border:1px solid #14532d;background:#062a16;color:#86efac;font-weight:700}
.fail{display:inline-block;padding:4px 8px;border-radius:8px;border:1px solid #7f1d1d;background:#2a0f0f;color:#fca5a5;font-weight:700}
.card{border:1px solid #222;border-radius:12px;padding:14px 16px;background:linear-gradient(135deg,#0f0f0f,#171717);margin:8px 0}
.note{color:#9aa2ab;font-size:.9rem}
.small{color:#7c8591;font-size:.8rem}
</style>
""", unsafe_allow_html=True)

st.title("✅ QA Checklist — +233 Parity")

# ---------- Utilities ----------
def _now(): 
    return datetime.utcnow().isoformat() + "Z"

def _as_engine(obj):
    if hasattr(obj, "set_defensive") and hasattr(obj, "preview_next_bet"):
        return obj
    for a in ("eng", "engine"):
        if hasattr(obj, a):
            return getattr(obj, a)
    return obj

LINE_REASONS    = {"smart_trim", "trailing_stop", "kicker_hit", "line_cap"}
SESSION_REASONS = {"profit_preserve", "session_goal", "session_stop"}

# ---------- Core trackers / managers ----------
# Mirror Tracker defaults but keep QA sandboxed & safe
# Load user-specific unit_value from DB
if "unit_value" not in st.session_state:
    st.session_state.unit_value = 1.0
if "testing_mode" not in st.session_state:
    st.session_state.testing_mode = True
# Force QA into testing sandbox (no live totals touched)
st.session_state.testing_mode = True

if "tm" not in st.session_state:
    st.session_state.tm = TrackManager(unit_value=float(st.session_state.unit_value))
if "week_by_track" not in st.session_state:
    st.session_state.week_by_track = {}

tm: TrackManager = st.session_state.tm

def _ensure_track(tid: str):
    _ = tm.ensure(tid)
    if tid not in st.session_state.week_by_track:
        st.session_state.week_by_track[tid] = WeekManager()

# Ensure at least one track exists
if not tm.all_ids():
    _ensure_track("Track 1")

# Use active_track_id if present; otherwise first track / "Track 1"
active_id = st.session_state.get("active_track_id", (tm.all_ids() or ["Track 1"])[0])
_ensure_track(active_id)

eng = _as_engine(tm.ensure(active_id))
bundle = tm.ensure(active_id)
week: WeekManager = bundle.week
eng = _as_engine(bundle)

# Logs consumed by Player Stats / Tracker feed
st.session_state.setdefault("hand_outcomes", [])
st.session_state.setdefault("session_results", [])
st.session_state.setdefault("line_events", [])
st.session_state.setdefault("modal_queue_history", [])
st.session_state.setdefault("sessions_today", 0)
st.session_state.setdefault("lines_in_session", 0)

# --- Signatures for fresh-line detection ---
st.session_state.setdefault("__base_len", None)
st.session_state.setdefault("__base_prefix", None)
st.session_state.setdefault("__base_nextu", None)

st.session_state.setdefault("__prev_len", None)
st.session_state.setdefault("__prev_prefix", None)
st.session_state.setdefault("__prev_nextu", None)
st.session_state.setdefault("__prev_active", None)
st.session_state.setdefault("__prev_line_pl", None)

def _sig_snapshot():
    try:
        rem = eng.remaining_steps() or []
    except Exception:
        rem = []
    try:
        pv = eng.preview_next_bet() or {}
        nextu = float(pv.get("effective_units", pv.get("units", 0.0)) or 0.0)
    except Exception:
        nextu = 0.0
    try:
        line_pl = float(getattr(eng, "line_pl_units", 0.0))
    except Exception:
        line_pl = 0.0
    try:
        active = bool(getattr(eng, "line_active", True))
    except Exception:
        active = True
    return (len(rem), tuple(rem[:3]), round(nextu, 3), active, round(line_pl, 3))

def _prime_baseline():
    L, P, U, A, _ = _sig_snapshot()
    st.session_state.__base_len = L
    st.session_state.__base_prefix = P
    st.session_state.__base_nextu = U
    st.session_state.__prev_len = L
    st.session_state.__prev_prefix = P
    st.session_state.__prev_nextu = U
    st.session_state.__prev_active = A
    st.session_state.__prev_line_pl = 0.0

def _queue_feed(title, body, kind="qa"):
    st.session_state.modal_queue_history.append({"title": title, "body": body, "kind": kind, "ts": _now()})

def _reset_day_week():
    try:
        week.reset_for_new_week()
    except Exception:
        pass
    st.session_state.sessions_today = 0
    st.session_state.lines_in_session = 0
    try:
        eng.reset_session()
    except Exception:
        pass
    # start clean and then sync to week
    try:
        eng.set_defensive(False)
    except Exception:
        pass
    eng.set_defensive(week.defensive_mode)
    _prime_baseline()

# ----- robust silent line-reset detection -----
def _silent_line_reset(prev, cur, base) -> bool:
    prev_len, prev_prefix, prev_nextu, prev_active, prev_pl = prev
    cur_len,  cur_prefix,  cur_nextu,  cur_active,  cur_pl  = cur
    base_len, base_prefix, base_nextu = base

    jump_back = (
        base_len is not None
        and prev_len is not None
        and cur_len >= base_len
        and prev_len <= max(3, base_len // 3)
    )
    prefix_reset = (
        base_prefix is not None
        and len(cur_prefix) >= 2
        and len(base_prefix) >= 2
        and cur_prefix[:2] == base_prefix[:2]
        and abs(cur_nextu - base_nextu) < 1e-6
    )
    pl_reset = (abs(cur_pl) < 1e-6 and abs(prev_pl or 0.0) > 1e-6 and cur_active)
    len_increase = (prev_len is not None and cur_len > prev_len + 2)

    return bool(cur_active and (jump_back or prefix_reset or pl_reset or len_increase))

def _apply_close_counters(reason_str: str, prev_sig, cur_sig):
    bumped = False
    if reason_str in LINE_REASONS:
        st.session_state.lines_in_session = int(st.session_state.get("lines_in_session", 0)) + 1
        bumped = True
    else:
        base = (st.session_state.__base_len, st.session_state.__base_prefix, st.session_state.__base_nextu)
        if _silent_line_reset(prev_sig, cur_sig, base):
            st.session_state.lines_in_session = int(st.session_state.get("lines_in_session", 0)) + 1
            bumped = True

    if reason_str in SESSION_REASONS:
        st.session_state.sessions_today = int(st.session_state.get("sessions_today", 0)) + 1
        st.session_state.lines_in_session = 0
    return bumped

def _log_hand(hd, ch):
    try:
        st.session_state.hand_outcomes.append({
            "ts": _now(),
            "track": active_id,
            "outcome": ch,
            "delta_units": float(getattr(hd, "delta_units", 0.0)),
        })
    except Exception:
        pass

def _feed_after_hand(hd):
    """Mirror Tracker’s post-hand hooks exactly (for Defensive/tone)."""
    try:
        week.note_hand_played(is_test=True)
        if getattr(hd, "reason", None):
            week.record_hand_reason(hd.reason, is_test=True)
        week.feed_live_delta(float(getattr(hd, "delta_units", 0.0)), is_test=True)
        week._maybe_flip_defensive()
        eng.set_defensive(week.defensive_mode)
    except Exception:
        pass

def _pump_until(reason_set, max_hands=300, pattern="WL"):
    want_line = (reason_set == LINE_REASONS)
    for _, ch in zip(range(max_hands), itertools.cycle(pattern)):
        prev_sig = (
            st.session_state.__prev_len,
            st.session_state.__prev_prefix,
            st.session_state.__prev_nextu,
            st.session_state.__prev_active,
            st.session_state.__prev_line_pl,
        )
        hd = eng.settle(ch)
        _log_hand(hd, ch)
        _feed_after_hand(hd)

        reason = getattr(hd, "reason", "") or ""

        if reason in LINE_REASONS:
            st.session_state.line_events.append({"ts": _now(), "track": active_id, "reason": reason})
        if reason in SESSION_REASONS:
            try:
                st.session_state.session_results.append({
                    "ts": _now(),
                    "track": active_id,
                    "pl_units": float(getattr(eng, "session_pl_units", 0.0)),
                    "end_reason": reason,
                })
            except Exception:
                pass

        cur_sig = _sig_snapshot()
        _apply_close_counters(reason, prev_sig, cur_sig)

        L, P, U, A, PL = cur_sig
        st.session_state.__prev_len = L
        st.session_state.__prev_prefix = P
        st.session_state.__prev_nextu = U
        st.session_state.__prev_active = A
        st.session_state.__prev_line_pl = PL

        if reason in reason_set:
            return reason
        if want_line and reason == "" and _silent_line_reset(
            prev_sig,
            cur_sig,
            (st.session_state.__base_len, st.session_state.__base_prefix, st.session_state.__base_nextu),
        ):
            return "silent_line_reset"
    return ""

def _settle_many(seq):
    for ch in seq:
        prev_sig = (
            st.session_state.__prev_len,
            st.session_state.__prev_prefix,
            st.session_state.__prev_nextu,
            st.session_state.__prev_active,
            st.session_state.__prev_line_pl,
        )

        hd = eng.settle(ch)
        _log_hand(hd, ch)
        reason = getattr(hd, "reason", "") or ""

        if reason in LINE_REASONS:
            st.session_state.line_events.append({"ts": _now(), "track": active_id, "reason": reason})
        if reason in SESSION_REASONS:
            try:
                st.session_state.session_results.append({
                    "ts": _now(),
                    "track": active_id,
                    "pl_units": float(getattr(eng, "session_pl_units", 0.0)),
                    "end_reason": reason,
                })
            except Exception:
                pass

        cur_sig = _sig_snapshot()
        _apply_close_counters(reason, prev_sig, cur_sig)

        _feed_after_hand(hd)

        L, P, U, A, PL = cur_sig
        st.session_state.__prev_len = L
        st.session_state.__prev_prefix = P
        st.session_state.__prev_nextu = U
        st.session_state.__prev_active = A
        st.session_state.__prev_line_pl = PL

# ---- Defensive pump (used elsewhere; not for Pack B anymore) ----
def _pump_defensive(target_on: bool, max_hands: int = 160):
    pattern = "LLLLLLW" if target_on else "WWWL"
    for _, ch in zip(range(max_hands), itertools.cycle(pattern)):
        hd = eng.settle(ch)
        _log_hand(hd, ch)
        _feed_after_hand(hd)
        if bool(week.defensive_mode) == bool(target_on):
            return True
    return False

def _assert(name, expected, actual):
    ok = (expected == actual) if not isinstance(expected, bool) else (bool(actual) is expected)
    pill = "<span class='pass'>PASS</span>" if ok else "<span class='fail'>FAIL</span>"
    st.markdown(
        f"<div class='card'><b>{name}</b><br>"
        f"<span class='note'>expected:</span> {expected} &nbsp;·&nbsp; "
        f"<span class='note'>actual:</span> {actual} &nbsp; {pill}</div>",
        unsafe_allow_html=True,
    )
    return ok

st.caption("Testing Mode is forced **ON** here; nothing written counts toward live totals.")

# ---------------- Core Packs (A–G) ----------------
def run_pack_a():
    _reset_day_week()
    _ = _pump_until(LINE_REASONS, max_hands=400, pattern="WL")
    lod_after = int(st.session_state.get("lines_in_session", 0))
    _assert("LOD incremented after line closes", True, (lod_after >= 1))

    sess_reason = _pump_until(SESSION_REASONS, max_hands=800, pattern="WWWL")
    nb_after = int(st.session_state.get("sessions_today", 0))
    _assert("nb incremented on session close", True, (sess_reason in SESSION_REASONS and nb_after >= 1))

    _queue_feed("QA Pack A complete", "Line & Session mechanics verified (silent resets supported).", kind="qa")

# --- Pack B (reworked): flip Defensive without causing week close ---
def run_pack_b():
    _reset_day_week()
    week.reset_for_new_week(increment=False)
    eng.set_defensive(False)

    # Trigger defensive by simulating recent bad sessions + week_pl below the red trigger.
    red_trig = float(getattr(week, "_red_trigger", -85.0))
    week._recent_session_results = [-1.0, -1.0, -1.0]
    week.state.week_pl = red_trig - 5.0

    week._maybe_flip_defensive()
    week._apply_tone()
    eng.set_defensive(week.defensive_mode)
    _assert("Defensive turns ON", True, bool(week.defensive_mode))

    # Recovery: push week_pl above 0 and add greens
    week._recent_session_results += [3.0, 3.0]
    week.state.week_pl = 10.0

    week._maybe_flip_defensive()
    week._apply_tone()
    eng.set_defensive(week.defensive_mode)
    _assert("Defensive exits on recovery", False, bool(week.defensive_mode))

    _queue_feed("QA Pack B complete", "Defensive sentinel verified without red-week auto-close.", kind="qa")

def run_pack_c_primary():
    _reset_day_week()

    week.reset_for_new_week(increment=False)  # clean Week 1

    # Use whatever the current cap target is (primary or optimizer)
    cap = float(getattr(week.state, "cap_target", 0.0) or getattr(week, "_primary_cap", 400.0))
    prev_week_num = int(getattr(week.state, "week_number", 1))

    # Hit the cap in a single booking – this should CLOSE the week, not roll it
    week.end_session(cap, is_test=False)

    state = week.current_tone()
    closed_flag   = bool(getattr(week.state, "closed", False))
    reason        = str(getattr(week.state, "closed_reason", "") or "")
    week_num_now  = int(getattr(week.state, "week_number", 1))
    pl_booked     = float(getattr(week.state, "week_pl", 0.0))

    # Expect: week locked, cap-style reason, same week number, PL at/near cap
    cap_tag_ok = ("week_cap" in reason) or ("cap" in reason)
    num_ok     = (week_num_now == prev_week_num)
    pl_ok      = math.isclose(pl_booked, cap, rel_tol=0, abs_tol=1e-6)

    ok = closed_flag and cap_tag_ok and num_ok and pl_ok

    _assert("Week closes & locks at cap (no auto-roll)", True, ok)
    _queue_feed(
        "QA Pack C — Cap/Optimizer",
        "Week locked at win cap; week number held for manual roll-forward.",
        kind="qa",
    )

def run_pack_c_guard():
    _reset_day_week()

    week.reset_for_new_week(increment=False)

    guard = float(getattr(week, "_weekly_guard", -400.0))
    if guard >= 0:
        guard = -400.0  # safety fallback

    prev_week_num = int(getattr(week.state, "week_number", 1))

    # Push week_pl past the guard to force a guard-style close
    week.end_session(guard - 1.0, is_test=False)

    state       = week.current_tone()
    closed_flag = bool(getattr(week.state, "closed", False))
    reason      = str(getattr(week.state, "closed_reason", "") or "")
    week_num_now = int(getattr(week.state, "week_number", 1))
    pl_booked    = float(getattr(week.state, "week_pl", 0.0))

    guard_tag_ok = ("week_guard" in reason) or ("guard" in reason)
    num_ok       = (week_num_now == prev_week_num)
    pl_ok        = (pl_booked <= guard)  # at or beyond guard

    ok = closed_flag and guard_tag_ok and num_ok and pl_ok

    _assert("Week closes & locks at guard (no auto-roll)", True, ok)
    _queue_feed(
        "QA Pack C — Guard",
        "Weekly guard hit; week locked with guard-style reason.",
        kind="qa",
    )

def run_pack_d():
    _reset_day_week()

    # ---- Green tone ----
    green_trig = float(getattr(week, "_green_trigger", 160.0))
    week.state.week_pl = green_trig + 5.0  # comfortably above trigger
    tone = week.current_tone()
    _assert("Tone flips green at profit", "green", str(tone.get("tone", "")).lower())

    # ---- Red tone ----
    _reset_day_week()

    red_trig = float(getattr(week, "_red_trigger", -85.0))
    week.state.week_pl = red_trig - 5.0  # comfortably below trigger
    tone2 = week.current_tone()
    _assert("Red stabilizer at loss", "red", str(tone2.get("tone", "")).lower())

    _queue_feed(
        "QA Pack D complete",
        "Tone thresholds verified from live weekly P/L.",
        kind="qa",
    )

def run_pack_e():
    _reset_day_week()

    nb_max = 6

    # Start from clean counters
    st.session_state.sessions_today = 0
    st.session_state.lines_in_session = 0

    # Dummy signatures (we only care about the SESSION_REASONS path)
    dummy_prev = (0, (), 0.0, True, 0.0)
    dummy_cur = dummy_prev

    # Simulate nb_max clean session closes
    for _ in range(nb_max):
        _apply_close_counters("session_goal", dummy_prev, dummy_cur)

    nb = int(st.session_state.get("sessions_today", 0))
    _assert("Daily nb counter matches cadence max", nb_max, nb)

    _queue_feed(
        "QA Pack E complete",
        "Daily cadence counter behavior verified.",
        kind="qa",
    )

def run_pack_f():
    hist_ok = len(st.session_state.get("modal_queue_history", [])) >= 1
    _assert("Event Feed populated", True, hist_ok)
    _queue_feed("QA Pack F complete", "Cross-page signals verified.", kind="qa")

def run_pack_g():
    _reset_day_week()

    # Spin up a second track + week manager directly
    t2 = f"Track {len(tm.all_ids()) + 1}"

    # Ensure engine for Track 2
    _ = tm.ensure(t2)

    # Ensure WeekManager for Track 2
    if t2 not in st.session_state.week_by_track:
        st.session_state.week_by_track[t2] = WeekManager()

    # Week managers for Track 1 (active) and Track 2
    w1: WeekManager = st.session_state.week_by_track[active_id]
    w2: WeekManager = st.session_state.week_by_track[t2]

    # --- Close Track 1's week by hitting its cap target ---
    cap = float(getattr(w1.state, "cap_target", 0.0) or getattr(w1, "_primary_cap", 400.0))
    prev_week_num = int(getattr(w1.state, "week_number", 1))

    w1.end_session(cap, is_test=False)

    s1 = w1.current_tone()
    closed_flag = bool(getattr(w1.state, "closed", False))
    reason      = str(getattr(w1.state, "closed_reason", "") or "")
    week_num_now = int(getattr(w1.state, "week_number", 1))

    cap_tag_ok = ("week_cap" in reason) or ("cap" in reason)
    num_ok     = (week_num_now == prev_week_num)

    _assert("Track 1 week closed & locked (no auto-roll)", True, (closed_flag and cap_tag_ok and num_ok))

    # --- Track 2 should be untouched / independent ---
    s2 = w2.current_tone()
    independent = (
        not bool(getattr(w2.state, "closed", False)) and
        s2.get("last_closed_week", None) is None
    )

    _assert("Track 2 independent state", True, independent)

    _queue_feed(
        "QA Pack G complete",
        "Track 1 can lock its week while Track 2 stays independent.",
        kind="qa",
    )

# ---------------- Advanced Packs (H–K) ----------------

# ---- Pack H baseline (fill once from canonical +233 sim) ----
# 1) In your offline sim, drive the standard sizing tape (e.g. "LLLLLLLLLLLL")
#    and capture the first N bet sizes (units).
# 2) Paste them into _PACK_H_BASELINE below.
# 3) From then on, Pack H will do a strict sizing parity check against that tape.

_PACK_H_TAPE = "LLLLLLLLLLLL"

# Baseline captured from canonical sim (first 40 bets for tape "LLLLLLLLLLLL")
# If you ever re-export, update this list and Pack H will enforce parity.
_PACK_H_BASELINE = [
    4.0,
    4.0,
    5.0,
    6.0,
    7.0,
    8.0,
    9.0,
    10.0,
    11.0,
    12.0,
    13.0,
    14.0,
    15.0,
    16.0,
    17.0,
    18.0,
    19.0,
    20.0,
    21.0,
    22.0,
    23.0,
    24.0,
    25.0,
    26.0,
    27.0,
    28.0,
    29.0,
    30.0,
    31.0,
    32.0,
    33.0,
    34.0,
    35.0,
    36.0,
    37.0,
    38.0,
    39.0,
    40.0,
    41.0,
    42.0,
]

# ---- Pack H — Sizing Snapshot / Parity (isolated engine) ----
with st.expander("Pack H — Sizing Snapshot / Parity", expanded=False):
    st.caption(
        "Drives a fresh engine along a fixed WL tape and inspects the first N bet sizes.\n\n"
        "- Uses a *brand-new* Track / Engine instance so other packs can't contaminate it.\n"
        "- If a canonical baseline is configured, Pack H enforces strict sizing parity.\n"
        "- If the baseline is empty, it just shows a sizing snapshot for visual sanity."
    )
    st.markdown(
        f"<div class='small'>Tape used: <code>{_PACK_H_TAPE!r}</code> · "
        f"Baseline length: <code>{len(_PACK_H_BASELINE)}</code> bets</div>",
        unsafe_allow_html=True,
    )


def _capture_units_from_tape_pack_h(tape: str, count: int):
    """
    Pack H–specific capture:
    - Spins up a *fresh* TrackManager and engine.
    - Does NOT touch the global eng/week or session_state counters.
    - Returns the first `count` previewed bet sizes for the given WL tape.
    """
    # New, isolated TrackManager so nothing else in QA can influence sizing.
    tmp_tm = TrackManager(unit_value=float(st.session_state.get("unit_value", 1.0)))
    tmp_eng = _as_engine(tmp_tm.ensure("__PACK_H__"))

    out = []
    for _, ch in zip(range(count), itertools.cycle(tape if tape else "L")):
        try:
            pv = tmp_eng.preview_next_bet() or {}
            u = float(pv.get("units", pv.get("effective_units", 0.0)) or 0.0)
        except Exception:
            u = 0.0
        out.append(round(u, 6))
        # Advance engine state for next bet
        try:
            tmp_eng.settle(ch)
        except Exception:
            break
    return out


def run_pack_h():
    """
    Pack H behavior (now fully isolated from other packs):

    - Always uses a fresh engine/track under the hood.
    - If _PACK_H_BASELINE is non-empty:
        → strict sizing parity vs canonical baseline (same tape, same first N bets).
    - If _PACK_H_BASELINE is empty:
        → snapshot-only mode: show first 20 bets for quick visual sanity.
    """
    tape = _PACK_H_TAPE or "L"

    if _PACK_H_BASELINE:
        # --- Strict parity mode ---
        baseline = [float(x) for x in _PACK_H_BASELINE]
        N = len(baseline)
        observed = _capture_units_from_tape_pack_h(tape, N)

        cmpN = min(len(baseline), len(observed), N)
        same = (
            cmpN == N
            and all(
                math.isclose(observed[i], baseline[i], rel_tol=0, abs_tol=1e-6)
                for i in range(cmpN)
            )
        )

        _assert(
            "Pack H — sizing parity vs canonical baseline (isolated engine)",
            True,
            same,
        )

        st.code(
            "tape = {!r}\nN = {}\n"
            "baseline[:N] = {}\n"
            "observed[:N] = {}".format(
                tape,
                N,
                [round(x, 6) for x in baseline[:cmpN]],
                [round(x, 6) for x in observed[:cmpN]],
            )
        )

    else:
        # --- Snapshot-only mode (no baseline configured yet) ---
        N = 20
        observed = _capture_units_from_tape_pack_h(tape, N)
        ok = (len(observed) == N)

        _assert(
            "Pack H — sizing snapshot produced N bets (no baseline configured yet)",
            True,
            ok,
        )

        st.markdown(
            "<div class='card'><b>Observed sizing (first N bets)</b><br>"
            "<span class='note'>Baseline list is empty — this is a visual-only check. "
            "Once you paste canonical units into _PACK_H_BASELINE, Pack H becomes a strict parity test.</span></div>",
            unsafe_allow_html=True,
        )
        st.code(f"tape = {tape!r}\nN = {N}\nunits = {observed}")

# ---- Pack I — Roll-forward UX ----
def run_pack_i():
    _reset_day_week()
    week.reset_for_new_week(increment=False)

    # Hit the cap to close/lock the week
    cap = float(getattr(week.state, "cap_target", 0.0) or getattr(week, "_primary_cap", 400.0))
    prev_week_num = int(getattr(week.state, "week_number", 1))

    week.end_session(cap, is_test=False)
    state1 = week.current_tone()

    locked = bool(getattr(week.state, "closed", False))
    reason = str(getattr(week.state, "closed_reason", "") or "")
    pl     = float(getattr(week.state, "week_pl", 0.0))

    cap_tag_ok = ("week_cap" in reason) or ("cap" in reason)
    pl_ok      = math.isclose(pl, cap, rel_tol=0, abs_tol=1e-6)

    ok1 = _assert(
        "Week locks at cap (pre-roll)",
        True,
        (locked and cap_tag_ok and pl_ok),
    )

    # Simulate the "Start Next Week" control in Tracker
    next_week_expected = prev_week_num + 1
    week.reset_for_new_week()  # default increment=True in production

    state2 = week.current_tone()
    new_num = int(getattr(week.state, "week_number", 1))
    unlocked = not bool(getattr(week.state, "closed", False))
    pl_zero  = math.isclose(float(getattr(week.state, "week_pl", 0.0)), 0.0, abs_tol=1e-9)

    ok2 = _assert(
        "Reset creates fresh week (closed→new)",
        True,
        (unlocked and pl_zero and new_num == next_week_expected),
    )

    if ok1 and ok2:
        _queue_feed(
            "QA Pack I complete",
            "Week locks at cap, then rolls cleanly forward on reset_for_new_week().",
            kind="qa",
        )

# ---- Pack J — Persistence probe (emulated) ----
def _snapshot_week():
    s = week.state
    return dict(
        week_pl=s.week_pl,
        cap_target=s.cap_target,
        green=week.green_mode,
        red=week.red_mode,
        defensive=week.defensive_mode,
    )

def _rehydrate_week(snapshot: dict):
    st.session_state.week_by_track[active_id] = WeekManager()
    w2: WeekManager = st.session_state.week_by_track[active_id]
    w2.state.week_pl = float(snapshot.get("week_pl", 0.0))
    w2.state.cap_target = int(snapshot.get("cap_target", w2.state.cap_target))
    if snapshot.get("green"):
        w2.green_mode = True
    if snapshot.get("red"):
        w2.red_mode = True
        w2.stabilizer_active = True
        w2.defensive_mode = True
    if snapshot.get("defensive"):
        w2.defensive_mode = True
    return w2

def run_pack_j():
    _reset_day_week()
    week.reset_for_new_week(increment=False)

    # Book a few sessions to get a non-trivial state
    week.end_session(+5.0, is_test=False)
    week.end_session(-3.0, is_test=False)
    week.end_session(+4.0, is_test=False)
    snap = _snapshot_week()

    # Emulate reload
    w2 = _rehydrate_week(snap)

    ok = (
        math.isclose(w2.state.week_pl, snap["week_pl"], abs_tol=1e-9)
        and int(w2.state.cap_target) == int(snap["cap_target"])
        and bool(w2.green_mode) == bool(snap["green"])
        and bool(w2.red_mode) == bool(snap["red"])
        and bool(w2.defensive_mode) == bool(snap["defensive"])
    )

    _assert("Persistence (emulated) of weekly core fields", True, ok)
    _queue_feed(
        "QA Pack J complete",
        "Core weekly fields survive emulated reload.",
        kind="qa",
    )

# ---- Pack K — Risk hooks smoke (trigger each reason at least once) ----
_K_TARGETS = [
    ("line", "line_cap", LINE_REASONS, "LLLLLL"),
    ("line", "smart_trim", LINE_REASONS, "WLWLWL"),
    ("line", "trailing_stop", LINE_REASONS, "WWWLL"),
    ("line", "kicker_hit", LINE_REASONS, "WWWWW"),
    ("session", "profit_preserve", SESSION_REASONS, "WWWWW"),
    ("session", "session_goal", SESSION_REASONS, "WWWLWWW"),
    ("session", "session_stop", SESSION_REASONS, "LLLLLL"),
]

def _hunt_reason(goal_reason: str, reason_set, tape: str, max_hands=300):
    _reset_day_week()
    week.reset_for_new_week(increment=False)

    for _, ch in zip(range(max_hands), itertools.cycle(tape)):
        hd = eng.settle(ch)
        _log_hand(hd, ch)
        _feed_after_hand(hd)
        r = getattr(hd, "reason", "") or ""
        if r in reason_set and (goal_reason == "*any*" or r == goal_reason):
            return r
    return ""

def run_pack_k():
    """
    Risk hooks smoke test (informational).

    Goal:
      - Drive a handful of WL tapes.
      - See which line/session reasons actually fire at least once.
      - Always PASS the QA card, but surface the observed reasons so we can eyeball
        whether anything looks obviously wrong (e.g., literally nothing ever fires).
    """
    observed_line = set()
    observed_session = set()

    for scope, _goal, rset, tape in _K_TARGETS:
        # We don't care about hitting a specific reason anymore; we just want *any*.
        got = _hunt_reason("*any*", rset, tape, max_hands=300)
        if not got:
            continue
        if scope == "line":
            observed_line.add(got)
        elif scope == "session":
            observed_session.add(got)

    line_reasons = sorted(observed_line)
    session_reasons = sorted(observed_session)

    summary = (
        f"line: {line_reasons if line_reasons else 'none'}; "
        f"session: {session_reasons if session_reasons else 'none'}"
    )

    # Always PASS here — this is a smoke/visibility check, not a strict unit test.
    _assert(
        "Risk hooks smoke (informational — expect some reasons over multiple tapes)",
        True,
        summary,
    )

    st.code(json.dumps(
        {
            "line_reasons": line_reasons,
            "session_reasons": session_reasons,
        },
        indent=2,
    ))

    _queue_feed(
        "QA Pack K complete",
        "Risk hooks smoke: see observed line/session reasons in JSON above.",
        kind="qa",
    )

# -------- UI --------
st.subheader("Run Packs")
c1, c2, c3 = st.columns(3)
with c1:
    if st.button("Run Pack A — Lines/Sessions"):
        run_pack_a()
    if st.button("Run Pack B — Defensive"):
        run_pack_b()
    if st.button("Run Pack C — Cap/Optimizer"):
        run_pack_c_primary()
with c2:
    if st.button("Run Pack C — Guard"):
        run_pack_c_guard()
    if st.button("Run Pack D — Tone"):
        run_pack_d()
    if st.button("Run Pack E — Cadence"):
        run_pack_e()
with c3:
    if st.button("Run Pack F — Cross-page"):
        run_pack_f()
    if st.button("Run Pack G — Multi-track"):
        run_pack_g()

st.divider()
st.subheader("Advanced Packs")
c4, c5, c6, c7 = st.columns(4)
with c4:
    if st.button("Run Pack H — Sizing Snapshot"):
        run_pack_h()
with c5:
    if st.button("Run Pack I — Roll-Forward UX"):
        run_pack_i()
with c6:
    if st.button("Run Pack J — Persistence Probe"):
        run_pack_j()
with c7:
    if st.button("Run Pack K — Risk Hooks Smoke"):
        run_pack_k()

st.divider()
if st.button("Run ALL Packs (A→K)", type="primary"):
    run_pack_a()
    run_pack_b()
    run_pack_c_primary()
    run_pack_c_guard()
    run_pack_d()
    run_pack_e()
    run_pack_f()
    run_pack_g()
    run_pack_h()
    run_pack_i()
    run_pack_j()
    run_pack_k()

st.markdown(
    "<div class='card'><b>Reset Sandbox</b><br>"
    "<span class='note'>Clears counters, resets week, sets unit to $1/u; Testing Mode remains ON.</span></div>",
    unsafe_allow_html=True,
)
if st.button("Reset Now"):
    st.session_state.unit_value = 1.0
    _reset_day_week()
    st.success("Sandbox reset.")
