# db_stats.py

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone

from supabase import Client
from supabase_client import get_supabase


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _safe_float(x, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def _parse_ts(value) -> datetime | None:
    """
    Robust parse for timestamptz coming back from Supabase.
    Expects ISO strings like '2025-12-02T15:30:12.345678+00:00' or '...Z'.
    """
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return None
    try:
        # Supabase often returns Z; datetime.fromisoformat doesn't like bare 'Z'
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except Exception:
        return None


# ---------- Player totals (all tracks) ----------

def get_player_totals(user_id: str, sb: Optional[Client] = None) -> Dict[str, float]:
    """
    Aggregate units AND dollars for this player across ALL tracks from Supabase.

    Source: session_results (the proper source of truth for P/L)

      - user_id           (uuid)
      - track_id          (uuid)
      - session_pl_units  (numeric)
      - unit_value        (numeric)  ← stored unit size at time of session
      - is_test           (bool)
      - created_at        (timestamptz)

    Rows with is_test = TRUE are excluded.
    Rows with is_test = NULL are treated as real (non-test).
    
    Dollar calculations use the stored unit_value per record, so historical
    dollar amounts remain accurate even if the user changes their unit size.
    """
    zero = {
        "all_time_units": 0.0,
        "all_time_dollars": 0.0,
        "month_units": 0.0,
        "month_dollars": 0.0,
        "week_units": 0.0,
        "week_dollars": 0.0,
        "ev_diff_units": 0.0,
    }

    if not user_id:
        return zero

    sb = sb or get_supabase()
    now = _now_utc()

    # Calendar month + week boundaries (UTC)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    weekday = now.weekday()  # Monday = 0
    week_start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=weekday)

    try:
        # Pull ALL non-test (or null) session results for this user
        res = (
            sb.table("session_results")
            .select("session_pl_units, unit_value, created_at, is_test")
            .eq("user_id", user_id)
            .or_("is_test.is.null,is_test.eq.false")
            .execute()
        )
        rows = res.data or []
    except Exception as e:
        print(f"[db_stats.get_player_totals] query error: {e!r}")
        return zero

    all_time_units = 0.0
    all_time_dollars = 0.0
    month_units = 0.0
    month_dollars = 0.0
    week_units = 0.0
    week_dollars = 0.0

    for r in rows:
        # Get session P/L in units
        pu = _safe_float(r.get("session_pl_units", 0.0), 0.0)
        
        # Get stored unit_value, default to 1.0 for old records
        uv = _safe_float(r.get("unit_value", 1.0), 1.0)
        if uv <= 0:
            uv = 1.0  # Safety fallback
        
        dollars = pu * uv  # Calculate actual dollars using stored unit_value
        
        all_time_units += pu
        all_time_dollars += dollars

        ts = _parse_ts(r.get("created_at"))
        if isinstance(ts, datetime):
            if ts >= month_start:
                month_units += pu
                month_dollars += dollars
            if ts >= week_start:
                week_units += pu
                week_dollars += dollars

    # EV diff: can't calculate precisely from session totals (no per-hand wager info)
    ev_diff_units = 0.0

    return {
        "all_time_units": float(all_time_units),
        "all_time_dollars": float(all_time_dollars),
        "month_units": float(month_units),
        "month_dollars": float(month_dollars),
        "week_units": float(week_units),
        "week_dollars": float(week_dollars),
        "ev_diff_units": float(ev_diff_units),
    }


# ---------- Closed weeks distribution ----------

def get_closed_weeks_distribution(user_id: str, sb: Optional[Client] = None) -> Dict[str, Any]:
    """
    Distribution of how closed weeks ended, across ALL tracks for this user.

    Source: week_closures

      - user_id        (uuid)
      - track_id       (uuid)
      - week_number    (int)
      - week_pl_units  (numeric)
      - outcome_bucket (text)
      - is_test        (bool)

    outcome_bucket is expected to include values like:
      - week_cap+400 / week_cap+8       → primary cap
      - week_cap+300 / week_cap+6       → optimizer cap
      - small_green_lock                → small green lock
      - red_stabilizer_lock             → red week stabilizer
      - week_guard-400 / week_guard-8   → weekly guard

    """
    sb = sb or get_supabase()

    try:
        res = (
            sb.table("week_closures")
            .select("outcome_bucket, week_pl_units, is_test")
            .eq("user_id", user_id)
            .or_("is_test.is.null,is_test.eq.false")
            .execute()
        )
        rows = res.data or []
    except Exception:
        rows = []

    # Semantic buckets keyed for UI copy, not raw numbers.
    counts = {
        "primary_cap": 0,      # hit +400
        "optimizer_cap": 0,    # hit +300
        "small_green": 0,      # small_green_lock / +160-style weeks
        "red_stabilizer": 0,   # red_stabilizer_lock / -85-style locks
        "weekly_guard": 0,     # full weekly guard (e.g., -400)
        "other": 0,            # anything unrecognized
    }
    total_closed = 0

    for r in rows:
        bucket_raw = (r.get("outcome_bucket") or "").strip()
        bucket = bucket_raw.lower()
        total_closed += 1

        # Normalize FAST_TEST tokens (e.g. week_cap+8, week_cap+6, week_guard-8)
        is_primary = ("week_cap+400" in bucket) or ("+400" in bucket) or ("week_cap+8" in bucket) or ("+8" in bucket)
        is_optimizer = ("week_cap+300" in bucket) or ("+300" in bucket) or ("week_cap+6" in bucket) or ("+6" in bucket)
        is_guard = ("week_guard-400" in bucket) or ("-400" in bucket) or ("week_guard-8" in bucket) or ("-8" in bucket)

        if is_primary:
            counts["primary_cap"] += 1
        elif is_optimizer:
            counts["optimizer_cap"] += 1
        elif "small_green" in bucket or "+160" in bucket:
            counts["small_green"] += 1
        elif "red_stabilizer" in bucket or "-85" in bucket:
            counts["red_stabilizer"] += 1
        elif is_guard:
            counts["weekly_guard"] += 1
        else:
            counts["other"] += 1

    return {
        "counts": counts,
        "total_closed": total_closed,
    }


# ---------- Recent events feed ----------

def get_recent_events(user_id: str, limit: int = 8) -> List[Dict[str, Any]]:
    """
    Recent cross-track events for this user.

    Uses ownership via tracks → track_events(track_id).
    No need for track_events.user_id.
    """
    if not user_id:
        return []

    sb = get_supabase()

    try:
        # 1) Get this user's track ids
        tr = (
            sb.table("tracks")
            .select("id")
            .eq("user_id", user_id)
            .execute()
        )
        track_ids = [row["id"] for row in (tr.data or []) if row.get("id")]
        if not track_ids:
            return []

        # 2) Pull recent events across those tracks
        res = (
            sb.table("track_events")
            .select("ts, kind, title, body, track_id")
            .in_("track_id", track_ids)
            .order("ts", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data or []
    except Exception:
        return []