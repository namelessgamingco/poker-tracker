# cache.py — Session-scoped caching for Supabase data
#
# Reduces DB round-trips by caching track lists, track states, and player totals
# in st.session_state. Each cache is invalidated explicitly when data changes.

import streamlit as st
from typing import Optional, Dict, Any, List, Callable


# ============================================================
#  TRACKS LIST CACHE
# ============================================================

def get_cached_tracks(user_id: str, loader_fn: Callable[[str], List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """
    Cache the track list for this user. Only reload on explicit invalidation.
    
    Usage:
        from cache import get_cached_tracks
        tracks = get_cached_tracks(USER_ID, get_tracks_for_user)
    """
    if not user_id:
        return []
    
    cache_key = f"_cache_tracks_{user_id}"
    
    if cache_key not in st.session_state:
        try:
            st.session_state[cache_key] = loader_fn(user_id) or []
        except Exception as e:
            print(f"[cache] get_cached_tracks loader error: {e!r}")
            return []
    
    return st.session_state[cache_key]


def invalidate_tracks_cache(user_id: str) -> None:
    """
    Call after creating or deleting a track.
    """
    if not user_id:
        return
    cache_key = f"_cache_tracks_{user_id}"
    if cache_key in st.session_state:
        del st.session_state[cache_key]


# ============================================================
#  TRACK STATE CACHE (per track)
# ============================================================

def get_cached_track_state(
    user_id: str,
    track_id: str,
    loader_fn: Callable[[str, str], Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Cache track state for a specific track. Invalidated on save or track switch.
    
    Usage:
        from cache import get_cached_track_state
        state = get_cached_track_state(USER_ID, track_id, load_track_state)
    """
    if not user_id or not track_id:
        return {}
    
    cache_key = f"_cache_track_state_{user_id}_{track_id}"
    
    if cache_key not in st.session_state:
        try:
            st.session_state[cache_key] = loader_fn(user_id, track_id) or {}
        except Exception as e:
            print(f"[cache] get_cached_track_state loader error: {e!r}")
            return {}
    
    return st.session_state[cache_key]


def set_cached_track_state(user_id: str, track_id: str, state: Dict[str, Any]) -> None:
    """
    Update cache after a local state change (avoids re-fetch from DB).
    Call this after save_track_state() succeeds.
    """
    if not user_id or not track_id:
        return
    cache_key = f"_cache_track_state_{user_id}_{track_id}"
    st.session_state[cache_key] = state or {}


def invalidate_track_state_cache(user_id: str, track_id: str) -> None:
    """
    Force re-fetch on next access. Use sparingly.
    """
    if not user_id or not track_id:
        return
    cache_key = f"_cache_track_state_{user_id}_{track_id}"
    if cache_key in st.session_state:
        del st.session_state[cache_key]


def invalidate_all_track_state_caches(user_id: str) -> None:
    """
    Invalidate all track state caches for a user.
    Useful after bulk operations.
    """
    if not user_id:
        return
    prefix = f"_cache_track_state_{user_id}_"
    keys_to_delete = [k for k in st.session_state.keys() if k.startswith(prefix)]
    for k in keys_to_delete:
        del st.session_state[k]


# ============================================================
#  PLAYER TOTALS CACHE (for Overview / Player Stats)
# ============================================================

def get_cached_player_totals(
    user_id: str,
    loader_fn: Callable[[str], Dict[str, float]]
) -> Dict[str, float]:
    """
    Cache player totals (all_time_units, month_units, week_units, ev_diff_units).
    Invalidate after session/week closes.
    
    Usage:
        from cache import get_cached_player_totals
        totals = get_cached_player_totals(USER_ID, get_player_totals)
    """
    if not user_id:
        return {}
    
    cache_key = f"_cache_player_totals_{user_id}"
    
    if cache_key not in st.session_state:
        try:
            st.session_state[cache_key] = loader_fn(user_id) or {}
        except Exception as e:
            print(f"[cache] get_cached_player_totals loader error: {e!r}")
            return {}
    
    return st.session_state[cache_key]


def invalidate_player_totals_cache(user_id: str) -> None:
    """
    Call after a session closes or week closes.
    """
    if not user_id:
        return
    cache_key = f"_cache_player_totals_{user_id}"
    if cache_key in st.session_state:
        del st.session_state[cache_key]


# ============================================================
#  CLOSED WEEKS DISTRIBUTION CACHE
# ============================================================

def get_cached_closed_weeks_distribution(
    user_id: str,
    loader_fn: Callable[[str], Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Cache closed weeks distribution for Overview page.
    """
    if not user_id:
        return {}
    
    cache_key = f"_cache_closed_weeks_dist_{user_id}"
    
    if cache_key not in st.session_state:
        try:
            st.session_state[cache_key] = loader_fn(user_id) or {}
        except Exception as e:
            print(f"[cache] get_cached_closed_weeks_distribution loader error: {e!r}")
            return {}
    
    return st.session_state[cache_key]


def invalidate_closed_weeks_cache(user_id: str) -> None:
    """
    Call after a week closes.
    """
    if not user_id:
        return
    cache_key = f"_cache_closed_weeks_dist_{user_id}"
    if cache_key in st.session_state:
        del st.session_state[cache_key]


# ============================================================
#  SESSIONS THIS WEEK CACHE (for Tracker header)
# ============================================================

def get_cached_sessions_this_week(
    user_id: str,
    track_id: str,
    week_no: int,
    loader_fn: Callable[[str, str, int], int]
) -> int:
    """
    Cache sessions-this-week count per track.
    """
    if not user_id or not track_id:
        return 0
    
    cache_key = f"_cache_sessions_week_{user_id}_{track_id}_{week_no}"
    
    if cache_key not in st.session_state:
        try:
            st.session_state[cache_key] = int(loader_fn(user_id, track_id, week_no) or 0)
        except Exception as e:
            print(f"[cache] get_cached_sessions_this_week loader error: {e!r}")
            return 0
    
    return st.session_state[cache_key]


def set_cached_sessions_this_week(user_id: str, track_id: str, week_no: int, count: int) -> None:
    """
    Update after a session closes.
    """
    if not user_id or not track_id:
        return
    cache_key = f"_cache_sessions_week_{user_id}_{track_id}_{week_no}"
    st.session_state[cache_key] = int(count)


def invalidate_sessions_this_week_cache(user_id: str, track_id: str, week_no: int) -> None:
    """
    Force re-fetch.
    """
    if not user_id or not track_id:
        return
    cache_key = f"_cache_sessions_week_{user_id}_{track_id}_{week_no}"
    if cache_key in st.session_state:
        del st.session_state[cache_key]


# ============================================================
#  HYDRATION FLAG (prevents re-hydrating bundles on every rerun)
# ============================================================

def is_hydrated(user_id: str) -> bool:
    """
    Check if we've already done initial DB hydration this session.
    """
    if not user_id:
        return False
    return bool(st.session_state.get(f"_cache_hydrated_{user_id}", False))


def mark_hydrated(user_id: str) -> None:
    """
    Mark that initial hydration is complete.
    """
    if not user_id:
        return
    st.session_state[f"_cache_hydrated_{user_id}"] = True


def clear_hydration_flag(user_id: str) -> None:
    """
    Force re-hydration on next page load.
    """
    if not user_id:
        return
    key = f"_cache_hydrated_{user_id}"
    if key in st.session_state:
        del st.session_state[key]


# ============================================================
#  CONVENIENCE: Invalidate all caches for a user
# ============================================================

def invalidate_all_caches(user_id: str) -> None:
    """
    Nuclear option: clear all cached data for a user.
    Use after major state changes (e.g., week reset).
    """
    if not user_id:
        return
    
    invalidate_tracks_cache(user_id)
    invalidate_all_track_state_caches(user_id)
    invalidate_player_totals_cache(user_id)
    invalidate_closed_weeks_cache(user_id)
    clear_hydration_flag(user_id)

def clear_all_user_caches() -> None:
    """
    Clear ALL user-specific caches regardless of user_id.
    Call on logout/login to ensure no data bleeds between users.
    """
    prefixes = (
        "_cache_tracks_",
        "_cache_track_state_",
        "_cache_player_totals_",
        "_cache_closed_weeks_dist_",
        "_cache_sessions_week_",
        "_cache_hydrated_",
    )
    keys_to_delete = [k for k in list(st.session_state.keys()) if any(k.startswith(p) for p in prefixes)]
    for k in keys_to_delete:
        del st.session_state[k]