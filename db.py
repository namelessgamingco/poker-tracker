# db.py — persistence helpers for profiles + tracks + track_state + track_events

from __future__ import annotations

from typing import Any, Dict, Optional, List
import datetime as dt
import json  # needed to decode jsonb coming back as strings

import os

import time
import httpx

from supabase_client import get_supabase, get_supabase_admin

# =========================
# Admin / Service-role client (bypasses RLS)
# Single source of truth: supabase_client.get_supabase_admin()
# =========================

def _admin_required():
    """
    Returns the service-role Supabase client (bypasses RLS).
    This is required for admin operations like create/delete users, list profiles, etc.
    """
    sb = get_supabase_admin()
    if sb is None:
        raise RuntimeError(
            "Admin client not configured. Add SUPABASE_SERVICE_ROLE_KEY_* to secrets "
            "for the active APP_ENV (dev/prod)."
        )
    return sb

def _sid(x: Any) -> str:
    """Safe id normalize (uuid.UUID -> str, None -> '')."""
    if x is None:
        return ""
    try:
        return str(x)
    except Exception:
        return ""

def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()

def _execute_with_retry(q, *, tries: int = 3, base_sleep: float = 0.2):
    """
    Retry wrapper for transient PostgREST/httpx read/connect hiccups (common on Streamlit Cloud).
    q must be a PostgREST query object that supports .execute().
    """
    last_err = None
    for attempt in range(tries):
        try:
            return q.execute()
        except (httpx.ReadError, httpx.ConnectError, httpx.TimeoutException) as e:
            last_err = e
            time.sleep(base_sleep * (2 ** attempt))  # 0.2, 0.4, 0.8
    raise last_err  # bubble after retries

# --- PST day key helper (canonical) ---
def _pst_today_key() -> str:
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo("America/Los_Angeles")
        return dt.datetime.now(tz).strftime("%Y-%m-%d")
    except Exception:
        # fallback: utc date (not ideal, but better than crashing)
        return dt.datetime.utcnow().strftime("%Y-%m-%d")

# ---------- USERS (profiles) ----------

def get_or_create_user(auth_id: str, email: str) -> Dict[str, Any]:
    sb = get_supabase()

    if not auth_id:
        raise RuntimeError("Missing auth_id (supabase user id). Refusing to map user.")

    email = (email or "").strip().lower()
    if not email:
        raise RuntimeError("Missing email. Refusing to create profile without email.")

    # ✅ Look up by auth user id (profiles.user_id)
    res = (
        sb.table("profiles")
        .select("*")
        .eq("user_id", auth_id)
        .maybe_single()
        .execute()
    )
    row = res.data

    if not row:
        payload = {
            "user_id": auth_id,
            "email": email,
            "role": "player",
            "is_active": True,
            "is_admin": False,
            "allowed": True,
        }

        # Try anon first
        try:
            insert_res = sb.table("profiles").insert(payload).execute()
            if insert_res.data:
                row = insert_res.data[0]
            else:
                raise RuntimeError("Anon insert returned no data.")
        except Exception:
            # Fallback: service-role bypasses RLS
            admin = _admin_required()
            insert_res = admin.table("profiles").insert(payload).execute()
            if not insert_res.data:
                raise RuntimeError("Failed to insert profile row in 'profiles' (admin fallback).")
            row = insert_res.data[0]

    role = row.get("role", "player")
    is_active = bool(row.get("is_active", True))

    return {
        "user_id": row.get("user_id"),
        "email": row.get("email"),
        "role": role,
        "is_active": is_active,
        "is_admin": bool(role == "admin" or row.get("is_admin")),
        "allowed": row.get("allowed", True),
    }

def ensure_profile(auth_id: str, email: str) -> Dict[str, Any]:
    """
    Canonical helper used by app.py and pages:
    Ensures a profiles row exists for this Supabase auth user id.
    """
    return get_or_create_user(auth_id=auth_id, email=email)

# =========================
# ADMIN READ HELPERS (service-role, RLS bypass)
# =========================

def get_tracks_for_user_admin(user_id: str) -> List[Dict[str, Any]]:
    sb = _admin_required()
    user_id = _sid(user_id)
    if not user_id:
        return []
    q = (
        sb.table("tracks")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=False)
    )
    res = _execute_with_retry(q)
    return list(res.data or [])


def load_track_state_admin(user_id: str, track_id: str) -> Dict[str, Any]:
    admin = _admin_required()
    user_id = _sid(user_id)
    track_id = _sid(track_id)
    if not user_id or not track_id:
        return {}

    try:
        res = (
            admin.table("track_state")
            .select(
                "engine_state_json,week_state_json,sessions_today,lines_in_session,updated_at,week_number,week_pl"
            )
            .eq("user_id", user_id)
            .eq("track_id", track_id)
            .limit(1)
            .execute()
        )

        rows = getattr(res, "data", None) or []
        if not rows:
            return {}

        row = rows[0] or {}

        raw_engine = row.get("engine_state_json") or {}
        raw_week   = row.get("week_state_json") or {}

        if isinstance(raw_engine, str):
            try:
                raw_engine = json.loads(raw_engine)
            except Exception:
                raw_engine = {}
        if isinstance(raw_week, str):
            try:
                raw_week = json.loads(raw_week)
            except Exception:
                raw_week = {}

        return {
            "engine": raw_engine if isinstance(raw_engine, dict) else {},
            "week": raw_week if isinstance(raw_week, dict) else {},
            "sessions_today": row.get("sessions_today", 0) or 0,
            "lines_in_session": row.get("lines_in_session", 0) or 0,
            "updated_at": row.get("updated_at"),
            "week_number": row.get("week_number"),
            "week_pl": row.get("week_pl"),
        }

    except Exception as e:
        print(f"[db] load_track_state_admin error user={user_id} track={track_id}: {e!r}")
        return {}

# ---------- TRACKS ----------

def get_tracks_for_user(user_id: str) -> List[Dict[str, Any]]:
    sb = get_supabase()
    user_id = _sid(user_id)
    if not user_id:
        return []

    q = (
        sb.table("tracks")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=False)
    )
    res = _execute_with_retry(q)
    tracks = res.data or []

    # Seed track_state so Overview/Snapshot works even before Tracker loads
    for t in tracks:
        tid = _sid(t.get("id"))
        if not tid:
            continue
        try:
            ensure_track_state(user_id, tid)
        except Exception:
            pass

    return tracks

def create_track_for_user(user_id: str, name: str) -> Dict[str, Any]:
    sb = get_supabase()

    insert_res = sb.table("tracks").insert(
        {"user_id": user_id, "track_label": name}
    ).execute()

    if not insert_res.data:
        raise RuntimeError("Failed to insert track row in 'tracks' table.")

    new_track = insert_res.data[0]

    # ✅ Seed track_state so Overview works immediately
    try:
        ensure_track_state(user_id, str(new_track["id"]))
    except Exception as e:
        print(f"[create_track_for_user] ensure_track_state failed: {e!r}")

    return new_track

def _user_owns_track(sb, user_id: str, track_id: str) -> bool:
    user_id = _sid(user_id)
    track_id = _sid(track_id)
    if not user_id or not track_id:
        return False

    try:
        tr = (
            sb.table("tracks")
            .select("id")
            .eq("id", track_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        return bool(tr.data)
    except Exception:
        return False

# ---------- TRACK STATE (engine + week + cadence counters) ----------

def ensure_track_state(user_id: str, track_id: str) -> None:
    sb = get_supabase()
    user_id = _sid(user_id)
    track_id = _sid(track_id)
    if not user_id or not track_id:
        return

    if not _user_owns_track(sb, user_id, track_id):
        print(f"[ensure_track_state] blocked: track_id={track_id} not owned by user_id={user_id}")
        return

    # existence check
    try:
        existing = (
            sb.table("track_state")
            .select("track_id")  # safer than "id"
            .eq("user_id", user_id)
            .eq("track_id", track_id)
            .limit(1)
            .execute()
        )
        if existing.data:
            return
    except Exception as e:
        print(f"[ensure_track_state] existence check failed track_id={track_id}: {e!r}")

    # insert seed row (minimal week defaults)
    seed_week = {
        "week_number": 1,
        "week_pl": 0.0,
        "cap_target": 0,
        "closed": False,
        "closed_reason": "",
        "green_mode": False,
        "red_mode": False,
        "defensive_mode": False,
        "stabilizer_active": False,
    }

    # --- NEW: seed a real default engine/week so Snapshot works before Tracker ---
    seed_engine: Dict[str, Any] = {}
    seed_week_state: Dict[str, Any] = seed_week

    try:
        from track_manager import TrackBundle  # safe: track_manager does not import db

        b = TrackBundle(unit_value=1.0)
        exported = b.export_state() or {}
        seed_engine = exported.get("engine") or {}
        seed_week_state = exported.get("week") or seed_week
    except Exception as e:
        print(f"[ensure_track_state] TrackBundle seed fallback used: {e!r}")
        seed_engine = {}
        seed_week_state = seed_week

    payload = {
        "user_id": user_id,
        "track_id": track_id,
        "engine_state_json": seed_engine,
        "week_state_json": seed_week_state,
        "sessions_today": 0,
        "lines_in_session": 0,
        "day_key": _pst_today_key(),

        # summary columns (keep aligned with week_state_json)
        "week_number": int(seed_week_state.get("week_number", 1) or 1),
        "week_pl": float(seed_week_state.get("week_pl", 0.0) or 0.0),
        "cap_target": int(seed_week_state.get("cap_target", 0) or 0),
        "week_closed": bool(seed_week_state.get("closed", False)),
        "week_closed_reason": str(seed_week_state.get("closed_reason", "") or ""),
        "green_mode": bool(seed_week_state.get("green_mode", False)),
        "red_mode": bool(seed_week_state.get("red_mode", False)),
        "defensive_mode": bool(seed_week_state.get("defensive_mode", False)),
        "stabilizer_active": bool(seed_week_state.get("stabilizer_active", False)),

        "updated_at": _now_iso(),
    }

    try:
        sb.table("track_state").insert(payload).execute()
    except Exception as e:
        msg = str(e).lower()
        if "duplicate" in msg or "conflict" in msg or "23505" in msg:
            return
        print(f"[ensure_track_state] insert failed for track_id={track_id}: {e!r}")

def save_track_state(user_id: str, track_id: str, bundle_state: Dict[str, Any]) -> None:
    sb = get_supabase()
    user_id = _sid(user_id)
    track_id = _sid(track_id)

    if not user_id or not track_id or not isinstance(bundle_state, dict):
        print(f"[save_track_state] invalid args user_id={user_id} track_id={track_id} type(bundle_state)={type(bundle_state)}")
        return

    if not _user_owns_track(sb, user_id, track_id):
        print(f"[save_track_state] blocked: track_id={track_id} not owned by user_id={user_id}")
        return

    week = bundle_state.get("week", {}) or {}

    payload = {
        "user_id": user_id,
        "track_id": track_id,

        "engine_state_json": bundle_state.get("engine", {}) or {},
        "week_state_json": week,

        "sessions_today": int(bundle_state.get("sessions_today", 0) or 0),
        "lines_in_session": int(bundle_state.get("lines_in_session", 0) or 0),
        "day_key": str(bundle_state.get("day_key") or _pst_today_key()),

        "week_number": int(week.get("week_number", 1) or 1),
        "week_pl": float(week.get("week_pl", 0.0) or 0.0),
        "cap_target": int(week.get("cap_target", 0) or 0),
        "week_closed": bool(week.get("closed", False)),
        "week_closed_reason": str(week.get("closed_reason", "") or ""),
        "green_mode": bool(week.get("green_mode", False)),
        "red_mode": bool(week.get("red_mode", False)),
        "defensive_mode": bool(week.get("defensive_mode", False)),
        "stabilizer_active": bool(week.get("stabilizer_active", False)),

        "updated_at": _now_iso(),
    }

    try:
        # ✅ real upsert by (user_id, track_id)
        sb.table("track_state").upsert(
            payload,
            on_conflict="user_id,track_id",
        ).execute()
    except Exception as e:
        print(f"[save_track_state] error while saving track_id={track_id}: {e!r}")

def load_track_state(user_id: str, track_id: str) -> Optional[Dict[str, Any]]:
    sb = get_supabase()
    user_id = _sid(user_id)
    track_id = _sid(track_id)

    if not user_id or not track_id:
        return None

    # Ownership guard
    if not _user_owns_track(sb, user_id, track_id):
        print(f"[load_track_state] blocked: track_id={track_id} not owned by user_id={user_id}")
        return None

    try:
        res = (
            sb.table("track_state")
            .select("*")
            .eq("track_id", track_id)
            .eq("user_id", user_id)
            .order("updated_at", desc=True)
            .limit(1)
            .execute()
        )
    except Exception as e:
        print(f"[load_track_state] error for track_id={track_id}: {e!r}")
        return None

    # If missing, seed once and retry once (THIS fixes snapshot needing tracker)
    if not res.data:
        ensure_track_state(user_id, track_id)
        try:
            res = (
                sb.table("track_state")
                .select("*")
                .eq("track_id", track_id)
                .eq("user_id", user_id)
                .order("updated_at", desc=True)
                .limit(1)
                .execute()
            )
        except Exception as e:
            print(f"[load_track_state] retry error for track_id={track_id}: {e!r}")
            return None

    if not res.data:
        return None

    row = res.data[0]

    # ✅ Canonical midnight reset (PST) — DB source of truth
    try:
        today_key = _pst_today_key()
        row_day_key = str(row.get("day_key") or "")

        if row_day_key != today_key:
            # reset counters in DB
            sb.table("track_state").update({
                "day_key": today_key,
                "sessions_today": 0,
                "lines_in_session": 0,
                "updated_at": _now_iso(),
            }).eq("user_id", user_id).eq("track_id", track_id).execute()

            # also reset the in-memory row we return
            row["day_key"] = today_key
            row["sessions_today"] = 0
            row["lines_in_session"] = 0
    except Exception as e:
        print(f"[load_track_state] day_key reset check suppressed: {e!r}")

    raw_engine = row.get("engine_state_json") or {}
    raw_week = row.get("week_state_json") or {}

    if isinstance(raw_engine, str):
        try:
            raw_engine = json.loads(raw_engine)
        except Exception:
            print("[load_track_state] failed to json.loads(engine_state_json); using empty dict.")
            raw_engine = {}

    if isinstance(raw_week, str):
        try:
            raw_week = json.loads(raw_week)
        except Exception:
            print("[load_track_state] failed to json.loads(week_state_json); using empty dict.")
            raw_week = {}

    # --- NEW: legacy reseed if this track_state was created with empty engine/week ---
    try:
        engine_empty = (not isinstance(raw_engine, dict)) or (len(raw_engine) == 0)
        week_empty = (not isinstance(raw_week, dict)) or (len(raw_week) == 0)

        if engine_empty or week_empty:
            from track_manager import TrackBundle

            b = TrackBundle(unit_value=1.0)
            exported = b.export_state() or {}

            if engine_empty:
                raw_engine = exported.get("engine") or {}
            if week_empty:
                raw_week = exported.get("week") or raw_week

            save_track_state(
                user_id,
                track_id,
                {
                    "engine": raw_engine,
                    "week": raw_week,
                    "sessions_today": row.get("sessions_today", 0),
                    "lines_in_session": row.get("lines_in_session", 0),
                },
            )
    except Exception as e:
        print(f"[load_track_state] legacy reseed failed: {e!r}")

# --- NEW: hydrate week_pl from session_results so Snapshot works without Tracker ---
    try:
        week_number = int(raw_week.get("week_number") or row.get("week_number") or 1)
        booked_data = get_week_pl_booked(user_id, track_id, week_number)
        # Handle both dict (new) and float (legacy) return types
        if isinstance(booked_data, dict):
            raw_week["week_pl"] = float(booked_data.get("units", 0.0))
        else:
            raw_week["week_pl"] = float(booked_data or 0.0)
    except Exception as e:
        print(f"[load_track_state] week_pl hydrate failed: {e!r}")

    return {
        "engine": raw_engine,
        "week": raw_week,
        "sessions_today": row.get("sessions_today", 0),
        "lines_in_session": row.get("lines_in_session", 0),
        "day_key": row.get("day_key"),
    }

# ---------- TRACK EVENTS (Event Feed) ----------

def log_track_event(user_id: str, track_id: str, kind: str, title: str, body: str, ts: Optional[str] = None) -> None:
    """
    Append a single major event for a track into track_events, and hard-prune
    older rows so we only keep ~50 per track.

    kind ∈ { "line", "session", "week", "defensive", "optimizer" } (and future variants)
    """
    sb = get_supabase()

    # normalize ids
    user_id = _sid(user_id)
    track_id = _sid(track_id)

    # ✅ Ownership guard (prevents writing events to someone else's track)
    if not user_id or not track_id:
        return
    if not _user_owns_track(sb, user_id, track_id):
        print(f"[log_track_event] blocked: track_id={track_id} not owned by user_id={user_id}")
        return

    if ts is None:
        ts = _now_iso()

    payload = {
        "track_id": track_id,
        "kind": kind,
        "title": title,
        "body": body,
        "ts": ts,
    }

    try:
        sb.table("track_events").insert(payload).execute()
    except Exception as e:
        print(f"[log_track_event] insert failed for track_id={track_id}: {e!r}")
        return

    # Hard-prune: keep ONLY the most recent ~50 rows per track
    try:
        while True:
            old = (
                sb.table("track_events")
                .select("id")
                .eq("track_id", track_id)
                .order("ts", desc=True)
                .offset(50)   # skip the newest 50
                .limit(500)   # grab older rows to delete in chunks
                .execute()
            )
            if not old.data:
                break

            old_ids = [row["id"] for row in old.data if "id" in row]
            if not old_ids:
                break

            sb.table("track_events").delete().in_("id", old_ids).execute()

            # If fewer than 500 came back, we just cleared everything beyond 50
            if len(old.data) < 500:
                break
    except Exception as e:
        print(f"[log_track_event] prune failed for track_id={track_id}: {e!r}")


def fetch_track_events(user_id: str, track_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Fetch the most recent N events for a given track, newest first.
    """
    sb = get_supabase()

    # normalize ids
    user_id = _sid(user_id)
    track_id = _sid(track_id)

    # ✅ Ownership guard (prevents data bleed)
    if not user_id or not track_id:
        return []

    if not _user_owns_track(sb, user_id, track_id):
        print(f"[fetch_track_events] blocked: track_id={track_id} not owned by user_id={user_id}")
        return []

    try:
        res = (
            sb.table("track_events")
            .select("*")
            .eq("track_id", track_id)
            .order("ts", desc=True)
            .limit(limit)
            .execute()
        )
    except Exception as e:
        print(f"[fetch_track_events] error for track_id={track_id}: {e!r}")
        return []

    return res.data or []

# ---------- HAND OUTCOMES (Live + Testing) ----------

def log_hand_outcome(
    user_id: str,
    track_id: str,
    week_number: int,
    session_index: int,
    hand_index: int,
    delta_units: float,
    outcome: str,
    ts: Optional[str] = None,
    unit_value: Optional[float] = None,
):
    """
    Log a single hand outcome (Win / Loss / Tie), fully session-scoped.
    """
    sb = get_supabase()

    if ts is None:
        ts = _now_iso()

    from streamlit import session_state as ss
    is_test = bool(ss.get("testing_mode", False))

    # ✅ Get unit_value from session state if not provided
    if unit_value is None:
        try:
            from streamlit import session_state as ss
            unit_value = float(ss.get("unit_value", 1.0))
        except Exception:
            unit_value = 1.0

    payload = {
        "user_id": user_id,
        "track_id": track_id,
        "week_number": int(week_number),
        "session_index": int(session_index),
        "hand_index": int(hand_index),
        "delta_units": float(delta_units),
        "outcome": outcome,   # 'W', 'L', or 'T'
        "is_test": is_test,
        "ts": ts,
        "unit_value": float(unit_value),
    }

    try:
        sb.table("hand_outcomes").insert(payload).execute()
    except Exception as e:
        print(f"[log_hand_outcome] insert failed: {e!r}")

# ---------- LINE EVENTS (Live only) ----------

def log_line_event(
    user_id: str,
    track_id: str,
    week_number: int,
    session_index: int,
    reason: str,
    ts: Optional[str] = None,
    line_duration_sec: Optional[float] = None,
    unit_value: Optional[float] = None,
) -> None:
    """
    Persist a single line-close event into line_events.
    """
    sb = get_supabase()

    if ts is None:
        ts = _now_iso()

    from streamlit import session_state as ss
    is_test = bool(ss.get("testing_mode", False))

    # ✅ Get unit_value from session state if not provided
    if unit_value is None:
        try:
            from streamlit import session_state as ss
            unit_value = float(ss.get("unit_value", 1.0))
        except Exception:
            unit_value = 1.0

    payload = {
        "user_id": user_id,
        "track_id": track_id,
        "week_number": int(week_number),
        "session_index": int(session_index),
        "reason": reason,
        "is_test": is_test,
        "created_at": ts,
        "unit_value": float(unit_value),
    }

    if line_duration_sec is not None:
        try:
            payload["line_duration_sec"] = float(line_duration_sec)
        except Exception:
            pass

    try:
        sb.table("line_events").insert(payload).execute()
    except Exception as e:
        print(f"[log_line_event] insert failed: {e!r}")

# ---------- SESSION RESULTS (Live + Testing; marked by is_test) ----------

def close_session(
    user_id: str,
    track_id: str,
    week_number: int,
    session_index: int,
    session_pl_units: float,
    end_reason: str,
    ts: Optional[str] = None,
    duration_sec: Optional[float] = None,
    unit_value: Optional[float] = None,
    soft_shield_active: Optional[bool] = None,  # ✅ NEW: +233 Diamond+ Soft Shield
) -> None:
    """
    Canonical session close write.
    Writes one row to session_results with session_index + is_test so we can:
      - compute sessions_today reliably
      - compute week_pl_booked reliably
      - rehydrate Tracker (LOD/nb) across track switches / refresh
    """
    sb = get_supabase()

    if ts is None:
        ts = _now_iso()

    from streamlit import session_state as ss
    is_test = bool(ss.get("testing_mode", False))

    # ✅ Get unit_value from session state if not provided
    if unit_value is None:
        try:
            from streamlit import session_state as ss
            unit_value = float(ss.get("unit_value", 1.0))
        except Exception:
            unit_value = 1.0

    # ✅ Get soft_shield_active from session state if not provided
    if soft_shield_active is None:
        try:
            from streamlit import session_state as ss
            soft_shield_active = bool(ss.get("soft_shield_active", False))
        except Exception:
            soft_shield_active = False

    payload = {
        "user_id": user_id,
        "track_id": track_id,
        "week_number": int(week_number),
        "session_index": int(session_index),
        "session_pl_units": float(session_pl_units),
        "end_reason": str(end_reason),
        "is_test": is_test,
        "created_at": ts,  # keep explicit for deterministic ordering
        "unit_value": float(unit_value),
        "soft_shield_active": bool(soft_shield_active),  # ✅ NEW: +233 Diamond+
    }

    if duration_sec is not None:
        try:
            payload["duration_sec"] = float(duration_sec)
        except Exception:
            pass

    try:
        sb.table("session_results").upsert(
            payload,
            on_conflict="user_id,track_id,week_number,session_index,is_test",
        ).execute()
        return
    except Exception:
        pass

    try:
        sb.table("session_results").insert(payload).execute()
    except Exception as e:
        msg = repr(e)
        if ("23505" in msg) or ("duplicate key" in msg.lower()) or ("unique" in msg.lower()):
            return
        print(f"[close_session] insert failed: {e!r}")
        raise

# ---------- SESSION RESULTS (Live only) ----------

def log_session_result(
    user_id: str,
    track_id: str,
    week_number: int,
    session_index: int,
    session_pl_units: float,
    end_reason: str,
    ts: Optional[str] = None,
    duration_sec: Optional[float] = None,
    unit_value: Optional[float] = None,
    soft_shield_active: Optional[bool] = None,  # ✅ NEW: +233 Diamond+ Soft Shield
) -> None:
    """
    Backwards-friendly wrapper that writes the canonical session close row.

    session_results (current schema):
      - id               (uuid, PK)
      - user_id          (uuid)
      - track_id         (uuid)
      - week_number      (int4)
      - session_index    (int4)
      - session_pl_units (numeric)
      - end_reason       (text)
      - is_test          (bool)
      - created_at       (timestamptz)
      - duration_sec     (numeric, optional)
      - unit_value       (numeric)
      - soft_shield_active (bool)  ✅ NEW: +233 Diamond+
    """
    close_session(
        user_id=user_id,
        track_id=track_id,
        week_number=int(week_number),
        session_index=int(session_index),
        session_pl_units=float(session_pl_units),
        end_reason=str(end_reason),
        ts=ts,
        duration_sec=duration_sec,
        unit_value=unit_value,
        soft_shield_active=soft_shield_active,  # ✅ NEW
    )

# ---------- WEEK CLOSURES (Live only) ----------
def log_week_closure(
    user_id: str,
    track_id: str,
    week_number: int,
    week_pl_units: float,
    outcome_bucket: str,
    is_test: bool = False,
    ts: Optional[str] = None,
    unit_value: Optional[float] = None,
) -> None:
    """
    Persist a single closed week into week_closures.
    Bulletproof against refresh/device duplicates via DB unique index:
      (user_id, track_id, week_number, is_test)

    Strategy: INSERT-first, ignore 23505 duplicates.
    """
    sb = get_supabase()

    from streamlit import session_state as ss
    if bool(ss.get("testing_mode", False)):
        return

    if ts is None:
        ts = _now_iso()

    # ✅ Get unit_value from session state if not provided
    if unit_value is None:
        try:
            from streamlit import session_state as ss
            unit_value = float(ss.get("unit_value", 1.0))
        except Exception:
            unit_value = 1.0

    data = {
        "user_id": str(user_id),
        "track_id": str(track_id),
        "week_number": int(week_number),
        "week_pl_units": float(week_pl_units),
        "outcome_bucket": str(outcome_bucket),
        "is_test": bool(is_test),
        "ts": ts,
        "unit_value": float(unit_value),
    }

    try:
        sb.table("week_closures").insert(data).execute()
    except Exception as e:
        msg = str(e)

        # ✅ Unique violation (Postgres 23505) = already logged → treat as success
        if ("23505" in msg) or ("duplicate key value violates unique constraint" in msg):
            return

        print(f"[db.log_week_closure] suppressed error: {e!r}")


# ---------- ADMIN HELPERS (profiles via service-role) ---------

def get_profile_by_email(email: str) -> Optional[Dict[str, Any]]:
    raise RuntimeError(
        "Do not query profiles by email. Use get_profile_by_auth_id(auth_id) "
        "where profiles.user_id == auth.users.id."
    )

def get_profile_by_auth_id(auth_id: str) -> Optional[Dict[str, Any]]:
    if not auth_id:
        return None

    sb = get_supabase()
    try:
        res = (
            sb.table("profiles")
            .select("*")
            .eq("user_id", auth_id)
            .maybe_single()
            .execute()
        )
        row = res.data
    except Exception as e:
        print(f"[db.get_profile_by_auth_id] error: {e!r}")
        return None

    if not row:
        return None

    row.setdefault("role", row.get("role", "player"))
    row.setdefault("is_active", row.get("is_active", True))
    return row


def list_profiles_for_admin() -> List[Dict[str, Any]]:
    admin = _admin_required()
    res = (
        admin.table("profiles")
        .select("user_id, email, role, is_active, created_at, role_assigned_at")
        .order("created_at", desc=True)
        .execute()
    )
    return list(res.data or [])

# ---------- TELEMETRY HELPERS (per-user recent data) ----------

def get_sessions_this_week_count(user_id: str, track_id: str, week_number: int) -> int:
    if not user_id or not track_id or not week_number:
        return 0

    sb = get_supabase()

    def _run(with_is_test: bool) -> int:
        q = (
            sb.table("session_results")
            .select("id", count="exact")
            .eq("user_id", str(user_id))
            .eq("track_id", str(track_id))
            .eq("week_number", int(week_number))
        )
        if with_is_test:
            q = q.eq("is_test", False)
        res = q.execute()
        c = getattr(res, "count", None)
        if c is not None:
            return int(c or 0)
        data = getattr(res, "data", None) or []
        return int(len(data))

    try:
        # try with is_test filter first (if schema supports it)
        return _run(with_is_test=True)
    except Exception as e:
        msg = str(e)
        # column does not exist -> retry without is_test
        if ("42703" in msg and "is_test" in msg) or ("does not exist" in msg and "is_test" in msg):
            try:
                return _run(with_is_test=False)
            except Exception as e2:
                print(f"[db.get_sessions_this_week_count] fallback error: {e2!r}")
                return 0

        print(f"[db.get_sessions_this_week_count] error: {e!r}")
        return 0

def get_week_pl_booked(user_id: str, track_id: str, week_number: int) -> Dict[str, float]:
    """
    Sum of CLOSED session P/L for this user/track/week.
    Returns both units and dollars (using stored unit_value per session).
    Source of truth = session_results table.
    """
    result = {"units": 0.0, "dollars": 0.0}
    
    if not user_id or not track_id or not week_number:
        return result

    sb = get_supabase()

    def _run(with_is_test: bool) -> Dict[str, float]:
        q = (
            sb.table("session_results")
            .select("session_pl_units, unit_value")
            .eq("user_id", str(user_id))
            .eq("track_id", str(track_id))
            .eq("week_number", int(week_number))
        )
        if with_is_test:
            q = q.eq("is_test", False)

        res = q.execute()
        total_units = 0.0
        total_dollars = 0.0
        for r in (res.data or []):
            try:
                u = float(r.get("session_pl_units") or 0.0)
                uv = float(r.get("unit_value") or 1.0)
                if uv <= 0:
                    uv = 1.0
                total_units += u
                total_dollars += u * uv
            except Exception:
                pass
        return {"units": total_units, "dollars": total_dollars}

    try:
        return _run(with_is_test=True)
    except Exception as e:
        msg = str(e)
        if ("42703" in msg and "is_test" in msg) or ("does not exist" in msg and "is_test" in msg):
            try:
                return _run(with_is_test=False)
            except Exception as e2:
                print(f"[db.get_week_pl_booked] fallback error: {e2!r}")
                return result

        print(f"[db.get_week_pl_booked] error: {e!r}")
        return result

def get_recent_sessions_for_user_admin(user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    sb = _admin_required()
    user_id = _sid(user_id)
    if not user_id:
        return []
    res = (
        sb.table("session_results")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return list(res.data or [])

def get_recent_lines_for_user_admin(user_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    sb = _admin_required()
    user_id = _sid(user_id)
    if not user_id:
        return []
    res = (
        sb.table("line_events")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return list(res.data or [])

def get_recent_closed_weeks_for_user_admin(user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    sb = _admin_required()
    user_id = _sid(user_id)
    if not user_id:
        return []
    res = (
        sb.table("week_closures")
        .select("*")
        .eq("user_id", user_id)
        .eq("is_test", False)
        .order("week_number", desc=True)
        .limit(limit)
        .execute()
    )
    return list(res.data or [])

def get_closed_weeks_distribution_admin(user_id: str, limit: int = 200) -> Dict[str, int]:
    sb = _admin_required()
    user_id = _sid(user_id)
    if not user_id:
        return {}

    res = (
        sb.table("week_closures")
        .select("outcome_bucket")
        .eq("user_id", user_id)
        .eq("is_test", False)
        .order("week_number", desc=True)
        .limit(limit)
        .execute()
    )

    buckets: Dict[str, int] = {}
    for r in (res.data or []):
        k = (r.get("outcome_bucket") or "").strip() or "unknown"
        buckets[k] = buckets.get(k, 0) + 1
    return buckets

def delete_profile_by_user_id(user_id: str) -> bool:
    if not user_id:
        return False
    sb = _admin_required()
    try:
        sb.table("profiles").delete().eq("user_id", str(user_id)).execute()
        return True
    except Exception as e:
        print(f"[db.delete_profile_by_user_id] error: {e!r}")
        return False

def get_recent_sessions_for_user(user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Fetch recent live sessions for a user, newest first.
    """
    if not user_id:
        return []

    sb = get_supabase()
    try:
        res = (
            sb.table("session_results")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data or []
    except Exception as e:
        print(f"[db.get_recent_sessions_for_user] error: {e!r}")
        return []


def get_recent_lines_for_user(user_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Fetch recent line_close events for a user, newest first.
    """
    if not user_id:
        return []

    sb = get_supabase()
    try:
        res = (
            sb.table("line_events")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data or []
    except Exception as e:
        print(f"[db.get_recent_lines_for_user] error: {e!r}")
        return []

def get_closed_weeks_distribution(user_id: str, limit: int = 200) -> Dict[str, int]:
    if not user_id:
        return {}

    sb = get_supabase()

    def _run(with_is_test: bool) -> Dict[str, int]:
        q = (
            sb.table("week_closures")
            .select("outcome_bucket")
            .eq("user_id", user_id)
            .order("week_number", desc=True)
            .limit(limit)
        )
        if with_is_test:
            q = q.eq("is_test", False)

        res = q.execute()
        buckets: Dict[str, int] = {}
        for r in (res.data or []):
            k = (r.get("outcome_bucket") or "").strip() or "unknown"
            buckets[k] = buckets.get(k, 0) + 1
        return buckets

    try:
        return _run(with_is_test=True)
    except Exception as e:
        msg = str(e)
        if "42703" in msg or "does not exist" in msg or "is_test" in msg:
            try:
                return _run(with_is_test=False)
            except Exception as e2:
                print(f"[db.get_closed_weeks_distribution] fallback error: {e2!r}")
                return {}
        print(f"[db.get_closed_weeks_distribution] error: {e!r}")
        return {}

def get_recent_closed_weeks_for_user(user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Fetch recent closed weeks for a user, newest first (by week_number).
    """
    if not user_id:
        return []

    sb = get_supabase()
    try:
        res = (
            sb.table("week_closures")
            .select("*")
            .eq("user_id", user_id)
            .eq("is_test", False)
            .order("week_number", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data or []
    except Exception as e:
        print(f"[db.get_recent_closed_weeks_for_user] error: {e!r}")
        return []

# ---------- AUTH ADMIN HELPERS (create / delete / email / password) ----------

def admin_create_user(
    email: str,
    password: str,
    role: str = "player",
    is_active: bool = True,
) -> Dict[str, Any]:
    admin = _admin_required()

    email = (email or "").strip().lower()
    if not email:
        raise ValueError("Email is required.")
    if not password:
        raise ValueError("Password is required.")

    # 1) Create auth user
    auth_res = admin.auth.admin.create_user({
        "email": email,
        "password": password,
        "email_confirm": True,
    })

    auth_user = getattr(auth_res, "user", None) or getattr(auth_res, "data", None) or auth_res
    auth_id = auth_user.get("id") if isinstance(auth_user, dict) else getattr(auth_user, "id", None)
    if not auth_id:
        raise RuntimeError("create_user did not return a user id.")

    # 2) Upsert profile row (profiles.user_id == auth.users.id)
    profile_payload = {
        "user_id": auth_id,
        "email": email,
        "role": role,
        "is_active": is_active,
        "role_assigned_at": _now_iso(),
    }

    # Only include these if your schema actually has them (prevents PGRST204)
    # If you're 100% sure they exist, you can inline them above instead.
    try:
        profile_payload["allowed"] = True
    except Exception:
        pass
    try:
        profile_payload["is_admin"] = (role == "admin")
    except Exception:
        pass

    admin.table("profiles").upsert(profile_payload, on_conflict="user_id").execute()

    return {"user_id": auth_id, "email": email, "role": role, "is_active": is_active}

def admin_delete_user(user_id: str) -> None:
    admin = _admin_required()
    if not user_id:
        raise ValueError("user_id required.")

    # delete auth user
    admin.auth.admin.delete_user(user_id)

    # delete profile row
    admin.table("profiles").delete().eq("user_id", user_id).execute()

def admin_update_user_email(user_id: str, new_email: str) -> None:
    admin = _admin_required()

    new_email = (new_email or "").strip().lower()
    if not user_id:
        raise ValueError("user_id required.")
    if not new_email:
        raise ValueError("new_email required.")

    admin.auth.admin.update_user_by_id(user_id, {"email": new_email, "email_confirm": True})
    admin.table("profiles").update({"email": new_email}).eq("user_id", user_id).execute()

def admin_set_user_password(user_id: str, new_password: str) -> None:
    admin = _admin_required()

    new_password = (new_password or "").strip()
    if not user_id:
        raise ValueError("user_id required.")
    if not new_password:
        raise ValueError("new_password required.")

    admin.auth.admin.update_user_by_id(user_id, {"password": new_password})

def set_profile_role(user_id: str, new_role: str) -> None:
    admin = _admin_required()
    if not user_id:
        raise ValueError("user_id required.")

    admin.table("profiles").update({
        "role": new_role,
        "role_assigned_at": _now_iso(),
    }).eq("user_id", user_id).execute()

def set_profile_active(user_id: str, is_active: bool) -> None:
    admin = _admin_required()
    if not user_id:
        raise ValueError("user_id required.")

    admin.table("profiles").update({"is_active": bool(is_active)}).eq("user_id", user_id).execute()

# ---------- USER UNIT VALUE (per-user persistence) ----------

def get_user_unit_value(user_id: str) -> float:
    """Get the user's unit_value from profiles, default 1.0."""
    if not user_id:
        return 1.0
    sb = get_supabase()
    try:
        res = (
            sb.table("profiles")
            .select("unit_value")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        if res.data and res.data[0].get("unit_value") is not None:
            return float(res.data[0]["unit_value"])
    except Exception as e:
        print(f"[db.get_user_unit_value] error: {e!r}")
    return 1.0


def set_user_unit_value(user_id: str, unit_value: float) -> None:
    """Persist the user's unit_value to profiles."""
    if not user_id:
        return
    sb = get_supabase()
    try:
        sb.table("profiles").update({"unit_value": float(unit_value)}).eq("user_id", user_id).execute()
    except Exception as e:
        print(f"[db.set_user_unit_value] error: {e!r}")

def save_bankroll_plan(user_id: str, plan: dict) -> bool:
    """
    Save a user's bankroll plan to the database.
    
    Creates or updates a row in bankroll_plans table:
    - user_id (uuid, primary key)
    - active_usd (numeric)
    - reserve_usd (numeric)
    - track_count (int)
    - updated_at (timestamptz)
    
    Returns True on success, False on failure.
    """
    if not user_id:
        return False
    
    try:
        sb = get_supabase()
        
        data = {
            "user_id": user_id,
            "active_usd": float(plan.get("active_usd", 0.0)),
            "reserve_usd": float(plan.get("reserve_usd", 0.0)),
            "track_count": int(plan.get("track_count", 1)),
            "updated_at": _now_iso(),
        }
        
        # Upsert - insert or update if exists
        sb.table("bankroll_plans").upsert(data, on_conflict="user_id").execute()
        return True
        
    except Exception as e:
        print(f"[db] save_bankroll_plan error: {e!r}")
        return False


def load_bankroll_plan(user_id: str) -> dict | None:
    """
    Load a user's saved bankroll plan from the database.
    
    Returns dict with keys: active_usd, reserve_usd, track_count
    Returns None if no plan exists or on error.
    """
    if not user_id:
        return None
    
    try:
        sb = get_supabase()
        
        resp = (
            sb.table("bankroll_plans")
            .select("active_usd, reserve_usd, track_count")
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
        
        if resp.data:
            return {
                "active_usd": float(resp.data.get("active_usd", 0.0)),
                "reserve_usd": float(resp.data.get("reserve_usd", 0.0)),
                "track_count": int(resp.data.get("track_count", 1)),
            }
        
        return None
        
    except Exception as e:
        print(f"[db] load_bankroll_plan error: {e!r}")
        return None