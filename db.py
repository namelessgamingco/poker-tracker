# db.py — Database Operations for Poker Decision App
# All Supabase queries and mutations

from __future__ import annotations

import os
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
from decimal import Decimal

import streamlit as st

from supabase_client import get_supabase, get_supabase_admin


# ---------- Helpers ----------

def _now_iso() -> str:
    """Get current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def _get_secret(name: str, default=None):
    """Read from env var or Streamlit secrets."""
    v = os.getenv(name)
    if v:
        return v
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return default


def _admin_required():
    """Get admin client or raise error."""
    try:
        return get_supabase_admin()
    except Exception as e:
        raise RuntimeError(f"Admin client not available: {e}")


# =============================================================================
# PROFILE OPERATIONS
# =============================================================================

def get_profile_by_auth_id(auth_id: str) -> Optional[dict]:
    """Get profile by auth user ID."""
    if not auth_id:
        return None
    
    try:
        sb = get_supabase_admin()
        resp = (
            sb.table("poker_profiles")
            .select("*")
            .eq("user_id", auth_id)
            .maybe_single()
            .execute()
        )
        return resp.data if resp.data else None
    except Exception as e:
        print(f"[db] get_profile_by_auth_id error: {e}")
        return None


def get_profile_by_email(email: str) -> Optional[dict]:
    """Get profile by email."""
    if not email:
        return None
    
    try:
        sb = get_supabase_admin()
        resp = (
            sb.table("poker_profiles")
            .select("*")
            .eq("email", email.lower().strip())
            .maybe_single()
            .execute()
        )
        return resp.data if resp.data else None
    except Exception as e:
        print(f"[db] get_profile_by_email error: {e}")
        return None


def update_profile(user_id: str, updates: dict) -> bool:
    """Update profile fields."""
    if not user_id or not updates:
        return False
    
    try:
        sb = get_supabase_admin()
        updates["updated_at"] = _now_iso()
        sb.table("poker_profiles").update(updates).eq("user_id", user_id).execute()
        return True
    except Exception as e:
        print(f"[db] update_profile error: {e}")
        return False


def update_user_settings(user_id: str, settings: dict) -> bool:
    """
    Update user settings.
    
    Accepts a dict with any of these keys:
        - bankroll (maps to current_bankroll)
        - risk_mode (maps to user_mode)
        - default_stakes
        - buy_in_count
        - stop_loss_bi
        - stop_win_bi
        - time_alerts_enabled
        - time_warning_hours
        - stop_loss_alerts_enabled
        - stop_win_alerts_enabled
        - table_check_interval
        - show_explanations
        - sound_enabled
        - theme
    """
    if not user_id or not settings:
        return False
    
    try:
        # Map our friendly names to actual column names
        column_mapping = {
            "bankroll": "current_bankroll",
            "risk_mode": "user_mode",
        }
        
        # Build update dict with correct column names
        updates = {}
        for key, value in settings.items():
            # Use mapped name if exists, otherwise use as-is
            col_name = column_mapping.get(key, key)
            updates[col_name] = value
        
        # Special handling for bankroll - also update timestamp
        if "current_bankroll" in updates:
            updates["bankroll_updated_at"] = _now_iso()
        
        updates["updated_at"] = _now_iso()
        
        sb = get_supabase_admin()
        sb.table("poker_profiles").update(updates).eq("user_id", user_id).execute()
        return True
        
    except Exception as e:
        print(f"[db] update_user_settings error: {e}")
        return False


def update_user_bankroll(user_id: str, bankroll: float) -> bool:
    """Update user's current bankroll."""
    return update_profile(user_id, {
        "current_bankroll": bankroll,
        "bankroll_updated_at": _now_iso(),
    })


# =============================================================================
# SESSION OPERATIONS
# =============================================================================

def create_session(
    user_id: str,
    stakes: str,
    bb_size: float,
    buy_in_amount: float,
    bankroll_at_start: float = None,
    stop_loss_amount: float = None,
    stop_win_amount: float = None,
) -> Optional[dict]:
    """
    Create a new poker session.
    
    Args:
        user_id: User's UUID
        stakes: Stakes label (e.g., "$1/$2")
        bb_size: Big blind size in dollars
        buy_in_amount: Starting stack amount
        bankroll_at_start: User's bankroll when session started
        stop_loss_amount: Dollar amount for stop-loss threshold
        stop_win_amount: Dollar amount for stop-win threshold
    
    Returns:
        Created session dict or None
    """
    if not user_id:
        return None
    
    try:
        sb = get_supabase_admin()
        
        session_data = {
            "user_id": user_id,
            "stakes": stakes,
            "bb_size": bb_size,
            "buy_in_amount": buy_in_amount,
            "bankroll_at_start": bankroll_at_start,
            "stop_loss_amount": stop_loss_amount,
            "stop_win_amount": stop_win_amount,
            "started_at": _now_iso(),
            "status": "active",
            "hands_played": 0,
            "decisions_requested": 0,
            "outcomes_won": 0,
            "outcomes_lost": 0,
            "outcomes_folded": 0,
            "is_test": False,
        }
        
        resp = sb.table("poker_sessions").insert(session_data).execute()
        
        if resp.data and len(resp.data) > 0:
            return resp.data[0]
        return None
        
    except Exception as e:
        print(f"[db] create_session error: {e}")
        return None


def get_active_session(user_id: str) -> Optional[dict]:
    """Get user's currently active session."""
    if not user_id:
        return None
    
    try:
        sb = get_supabase()
        resp = (
            sb.table("poker_sessions")
            .select("*")
            .eq("user_id", user_id)
            .eq("status", "active")
            .order("started_at", desc=True)
            .limit(1)
            .maybe_single()
            .execute()
        )
        return resp.data if resp.data else None
    except Exception as e:
        print(f"[db] get_active_session error: {e}")
        return None


def update_session(session_id: str, updates: dict) -> bool:
    """Update session fields."""
    if not session_id or not updates:
        return False
    
    try:
        sb = get_supabase()
        sb.table("poker_sessions").update(updates).eq("id", session_id).execute()
        return True
    except Exception as e:
        print(f"[db] update_session error: {e}")
        return False


def increment_session_stats(session_id: str, hands: int = 0, decisions: int = 0) -> bool:
    """Increment hands played and decisions requested counters."""
    if not session_id:
        return False
    
    try:
        sb = get_supabase()
        
        # Get current values
        resp = (
            sb.table("poker_sessions")
            .select("hands_played, decisions_requested")
            .eq("id", session_id)
            .single()
            .execute()
        )
        
        if not resp.data:
            return False
        
        current_hands = resp.data.get("hands_played", 0) or 0
        current_decisions = resp.data.get("decisions_requested", 0) or 0
        
        # Update with new values
        sb.table("poker_sessions").update({
            "hands_played": current_hands + hands,
            "decisions_requested": current_decisions + decisions,
        }).eq("id", session_id).execute()
        
        return True
    except Exception as e:
        print(f"[db] increment_session_stats error: {e}")
        return False


def end_session(
    session_id: str,
    cash_out_amount: float,
    end_reason: str = "manual",
) -> Optional[dict]:
    """
    End a poker session and calculate P/L.
    
    Args:
        session_id: Session UUID
        cash_out_amount: Final stack amount
        end_reason: 'manual', 'stop_loss', 'stop_win', 'time_limit', 'bankroll_alert'
    
    Returns:
        Updated session dict or None
    """
    if not session_id:
        return None
    
    try:
        sb = get_supabase()
        
        # Get session to calculate P/L
        resp = (
            sb.table("poker_sessions")
            .select("*")
            .eq("id", session_id)
            .single()
            .execute()
        )
        
        if not resp.data:
            return None
        
        session = resp.data
        buy_in = float(session.get("buy_in_amount", 0))
        bb_size = float(session.get("bb_size", 2))
        started_at = session.get("started_at")
        
        # Calculate P/L
        profit_loss = cash_out_amount - buy_in
        profit_loss_bb = profit_loss / bb_size if bb_size > 0 else 0
        
        # Calculate duration
        duration_minutes = None
        duration_sec = None
        if started_at:
            try:
                start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                delta = now - start
                duration_sec = int(delta.total_seconds())
                duration_minutes = int(delta.total_seconds() / 60)
            except Exception:
                pass
        
        # Update session
        updates = {
            "ended_at": _now_iso(),
            "cash_out_amount": cash_out_amount,
            "profit_loss": profit_loss,
            "profit_loss_bb": profit_loss_bb,
            "session_pl_units": profit_loss_bb,  # Alias for compatibility
            "duration_minutes": duration_minutes,
            "duration_sec": duration_sec,
            "end_reason": end_reason,
            "status": "completed",
        }
        
        sb.table("poker_sessions").update(updates).eq("id", session_id).execute()
        
        # Return updated session
        session.update(updates)
        return session
        
    except Exception as e:
        print(f"[db] end_session error: {e}")
        return None


def get_user_sessions(
    user_id: str,
    limit: int = 50,
    include_test: bool = False,
) -> List[dict]:
    """Get user's session history."""
    if not user_id:
        return []
    
    try:
        sb = get_supabase()
        query = (
            sb.table("poker_sessions")
            .select("*")
            .eq("user_id", user_id)
            .eq("status", "completed")
        )
        
        if not include_test:
            query = query.eq("is_test", False)
        
        resp = query.order("started_at", desc=True).limit(limit).execute()
        
        return resp.data if resp.data else []
    except Exception as e:
        print(f"[db] get_user_sessions error: {e}")
        return []


def get_sessions_in_date_range(
    user_id: str,
    start_date: datetime,
    end_date: datetime,
    include_test: bool = False,
) -> List[dict]:
    """Get sessions within a date range."""
    if not user_id:
        return []
    
    try:
        sb = get_supabase()
        query = (
            sb.table("poker_sessions")
            .select("*")
            .eq("user_id", user_id)
            .eq("status", "completed")
            .gte("started_at", start_date.isoformat())
            .lte("started_at", end_date.isoformat())
        )
        
        if not include_test:
            query = query.eq("is_test", False)
        
        resp = query.order("started_at", desc=True).execute()
        
        return resp.data if resp.data else []
    except Exception as e:
        print(f"[db] get_sessions_in_date_range error: {e}")
        return []


# =============================================================================
# BANKROLL OPERATIONS
# =============================================================================

def record_bankroll_change(
    user_id: str,
    bankroll_amount: float,
    change_amount: float,
    change_type: str,
    session_id: str = None,
    notes: str = None,
    current_stakes: str = None,
) -> bool:
    """
    Record a bankroll change in history.
    
    Args:
        change_type: 'session_result', 'deposit', 'withdrawal', 'adjustment', 'initial'
    """
    if not user_id:
        return False
    
    try:
        sb = get_supabase()
        
        # Calculate buy-ins available (assuming $1/$2 = $200 buy-in as default)
        # This should be adjusted based on actual stakes
        stakes_to_buyin = {
            "$0.50/$1": 100,
            "$1/$2": 200,
            "$2/$5": 500,
            "$5/$10": 1000,
            "$10/$20": 2000,
            "$25/$50": 5000,
        }
        buyin = stakes_to_buyin.get(current_stakes, 200)
        buy_ins_available = bankroll_amount / buyin if buyin > 0 else 0
        
        record = {
            "user_id": user_id,
            "bankroll_amount": bankroll_amount,
            "change_amount": change_amount,
            "change_type": change_type,
            "session_id": session_id,
            "buy_ins_available": round(buy_ins_available, 2),
            "current_stakes": current_stakes,
            "notes": notes,
            "recorded_at": _now_iso(),
        }
        
        sb.table("poker_bankroll_history").insert(record).execute()
        return True
        
    except Exception as e:
        print(f"[db] record_bankroll_change error: {e}")
        return False


def get_bankroll_history(user_id: str, limit: int = 100) -> List[dict]:
    """Get user's bankroll history."""
    if not user_id:
        return []
    
    try:
        sb = get_supabase()
        resp = (
            sb.table("poker_bankroll_history")
            .select("*")
            .eq("user_id", user_id)
            .order("recorded_at", desc=True)
            .limit(limit)
            .execute()
        )
        return resp.data if resp.data else []
    except Exception as e:
        print(f"[db] get_bankroll_history error: {e}")
        return []


# =============================================================================
# STATS OPERATIONS
# =============================================================================

def get_player_stats(user_id: str, include_test: bool = False) -> dict:
    """
    Get aggregated player statistics.
    
    Returns dict with:
        - total_sessions
        - total_hands
        - total_hours
        - total_profit_loss
        - total_profit_loss_bb
        - win_rate_bb_100 (BB/100 hands)
        - winning_sessions
        - losing_sessions
        - biggest_win
        - biggest_loss
    """
    if not user_id:
        return {}
    
    try:
        sessions = get_user_sessions(user_id, limit=1000, include_test=include_test)
        
        if not sessions:
            return {
                "total_sessions": 0,
                "total_hands": 0,
                "total_hours": 0,
                "total_profit_loss": 0,
                "total_profit_loss_bb": 0,
                "win_rate_bb_100": 0,
                "winning_sessions": 0,
                "losing_sessions": 0,
                "biggest_win": 0,
                "biggest_loss": 0,
            }
        
        total_sessions = len(sessions)
        total_hands = sum(s.get("hands_played", 0) or 0 for s in sessions)
        total_minutes = sum(s.get("duration_minutes", 0) or 0 for s in sessions)
        total_hours = round(total_minutes / 60, 1)
        
        total_profit_loss = sum(float(s.get("profit_loss", 0) or 0) for s in sessions)
        total_profit_loss_bb = sum(float(s.get("profit_loss_bb", 0) or 0) for s in sessions)
        
        # Calculate win rate (BB/100 hands)
        win_rate_bb_100 = 0
        if total_hands > 0:
            win_rate_bb_100 = round((total_profit_loss_bb / total_hands) * 100, 2)
        
        # Session outcomes
        winning_sessions = sum(1 for s in sessions if float(s.get("profit_loss", 0) or 0) > 0)
        losing_sessions = sum(1 for s in sessions if float(s.get("profit_loss", 0) or 0) < 0)
        
        # Biggest win/loss
        profits = [float(s.get("profit_loss", 0) or 0) for s in sessions]
        biggest_win = max(profits) if profits else 0
        biggest_loss = min(profits) if profits else 0
        
        return {
            "total_sessions": total_sessions,
            "total_hands": total_hands,
            "total_hours": total_hours,
            "total_profit_loss": round(total_profit_loss, 2),
            "total_profit_loss_bb": round(total_profit_loss_bb, 2),
            "win_rate_bb_100": win_rate_bb_100,
            "winning_sessions": winning_sessions,
            "losing_sessions": losing_sessions,
            "biggest_win": round(biggest_win, 2),
            "biggest_loss": round(biggest_loss, 2),
        }
        
    except Exception as e:
        print(f"[db] get_player_stats error: {e}")
        return {}


def get_today_stats(user_id: str) -> dict:
    """Get today's session stats."""
    if not user_id:
        return {"sessions": 0, "profit_loss": 0}
    
    try:
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        today_end = today_start + timedelta(days=1)
        
        sessions = get_sessions_in_date_range(user_id, today_start, today_end)
        
        total_pl = sum(float(s.get("profit_loss", 0) or 0) for s in sessions)
        
        return {
            "sessions": len(sessions),
            "profit_loss": round(total_pl, 2),
        }
        
    except Exception as e:
        print(f"[db] get_today_stats error: {e}")
        return {"sessions": 0, "profit_loss": 0}


# =============================================================================
# STAKES REFERENCE
# =============================================================================

def get_stakes_options() -> List[dict]:
    """Get all supported stakes from reference table."""
    try:
        sb = get_supabase()
        resp = (
            sb.table("poker_stakes_reference")
            .select("*")
            .order("display_order")
            .execute()
        )
        return resp.data if resp.data else []
    except Exception as e:
        print(f"[db] get_stakes_options error: {e}")
        # Return hardcoded fallback
        return [
            {"stakes_label": "$0.50/$1", "bb_size": 1.0, "standard_buy_in": 100},
            {"stakes_label": "$1/$2", "bb_size": 2.0, "standard_buy_in": 200},
            {"stakes_label": "$2/$5", "bb_size": 5.0, "standard_buy_in": 500},
            {"stakes_label": "$5/$10", "bb_size": 10.0, "standard_buy_in": 1000},
            {"stakes_label": "$10/$20", "bb_size": 20.0, "standard_buy_in": 2000},
            {"stakes_label": "$25/$50", "bb_size": 50.0, "standard_buy_in": 5000},
        ]


def get_stakes_info(stakes_label: str) -> Optional[dict]:
    """Get info for specific stakes level."""
    try:
        sb = get_supabase()
        resp = (
            sb.table("poker_stakes_reference")
            .select("*")
            .eq("stakes_label", stakes_label)
            .maybe_single()
            .execute()
        )
        return resp.data if resp.data else None
    except Exception as e:
        print(f"[db] get_stakes_info error: {e}")
        return None


# =============================================================================
# ADMIN OPERATIONS
# =============================================================================

def list_profiles_for_admin() -> List[dict]:
    """List all profiles for admin console."""
    try:
        sb = _admin_required()
        resp = (
            sb.table("poker_profiles")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )
        return resp.data if resp.data else []
    except Exception as e:
        print(f"[db] list_profiles_for_admin error: {e}")
        return []


def admin_create_user(
    email: str,
    password: str,
    role: str = "player",
    is_active: bool = False,
    subscription_status: str = "pending",
    subscription_plan: str = "monthly",
    subscription_amount: float = 299.00,
    start_trial: bool = False,
    trial_days: int = 7,
) -> dict:
    """
    Create a new user (admin only).
    
    Creates auth user and profile with subscription settings.
    """
    admin = _admin_required()
    
    email = (email or "").strip().lower()
    password = (password or "").strip()
    
    if not email or not password:
        raise ValueError("Email and password required.")
    
    # Create auth user
    auth_resp = admin.auth.admin.create_user({
        "email": email,
        "password": password,
        "email_confirm": True,
    })
    
    user_id = auth_resp.user.id
    now = _now_iso()
    
    # Set up trial if requested
    trial_ends_at = None
    if start_trial:
        subscription_status = "trial"
        is_active = True
        trial_ends_at = (datetime.now(timezone.utc) + timedelta(days=trial_days)).isoformat()
    
    # Generate payment link URL
    payment_link_base = _get_secret("RADOM_PAYMENT_LINK_BASE")
    payment_link_url = f"{payment_link_base}?user_email={email}" if payment_link_base else None
    
    # Create profile
    profile_data = {
        "user_id": user_id,
        "email": email,
        "role": role,
        "role_assigned_at": now,
        "is_active": is_active,
        "is_admin": role == "admin",
        "allowed": True,
        "subscription_status": subscription_status,
        "subscription_plan": subscription_plan,
        "subscription_amount": subscription_amount,
        "subscription_currency": "USD",
        "payment_link_url": payment_link_url,
        "trial_ends_at": trial_ends_at,
        "is_trial": start_trial,
        "user_mode": "balanced",
        "default_stakes": "$1/$2",
        "created_at": now,
    }
    
    admin.table("poker_profiles").insert(profile_data).execute()
    
    return {
        "user_id": user_id,
        "email": email,
        "subscription_status": subscription_status,
        "payment_link_url": payment_link_url,
        "trial_ends_at": trial_ends_at,
    }


def admin_delete_user(user_id: str) -> bool:
    """Delete auth user (admin only). Profile cascades."""
    if not user_id:
        return False
    
    try:
        admin = _admin_required()
        admin.auth.admin.delete_user(user_id)
        return True
    except Exception as e:
        print(f"[db] admin_delete_user error: {e}")
        return False


def delete_profile_by_user_id(user_id: str) -> bool:
    """Delete profile directly (backup if cascade fails)."""
    if not user_id:
        return False
    
    try:
        admin = _admin_required()
        admin.table("poker_profiles").delete().eq("user_id", user_id).execute()
        return True
    except Exception as e:
        print(f"[db] delete_profile_by_user_id error: {e}")
        return False


def admin_update_user_email(user_id: str, new_email: str) -> bool:
    """Update user's email in auth.users."""
    if not user_id or not new_email:
        return False
    
    try:
        admin = _admin_required()
        admin.auth.admin.update_user_by_id(user_id, {"email": new_email.lower().strip()})
        # Also update profile
        admin.table("poker_profiles").update({"email": new_email.lower().strip()}).eq("user_id", user_id).execute()
        return True
    except Exception as e:
        print(f"[db] admin_update_user_email error: {e}")
        return False


def admin_set_user_password(user_id: str, new_password: str) -> bool:
    """Set user's password (admin only)."""
    if not user_id or not new_password:
        return False
    
    try:
        admin = _admin_required()
        admin.auth.admin.update_user_by_id(user_id, {"password": new_password})
        return True
    except Exception as e:
        print(f"[db] admin_set_user_password error: {e}")
        return False


def set_profile_role(user_id: str, role: str) -> bool:
    """Set user's role."""
    if not user_id:
        return False
    
    try:
        admin = _admin_required()
        admin.table("poker_profiles").update({
            "role": role,
            "role_assigned_at": _now_iso(),
            "is_admin": role == "admin",
        }).eq("user_id", user_id).execute()
        return True
    except Exception as e:
        print(f"[db] set_profile_role error: {e}")
        return False


def set_profile_active(user_id: str, is_active: bool) -> bool:
    """Set user's active status."""
    if not user_id:
        return False
    
    try:
        admin = _admin_required()
        admin.table("poker_profiles").update({
            "is_active": is_active,
        }).eq("user_id", user_id).execute()
        return True
    except Exception as e:
        print(f"[db] set_profile_active error: {e}")
        return False


# =============================================================================
# SUBSCRIPTION ADMIN OPERATIONS
# =============================================================================

def admin_grant_free_access(user_id: str, reason: str = "Admin override") -> bool:
    """Grant free access to a user (admin override)."""
    if not user_id:
        return False
    
    try:
        admin = _admin_required()
        admin.table("poker_profiles").update({
            "admin_override_active": True,
            "is_active": True,
            "lockout_reason": None,
        }).eq("user_id", user_id).execute()
        return True
    except Exception as e:
        print(f"[db] admin_grant_free_access error: {e}")
        return False


def admin_revoke_free_access(user_id: str) -> bool:
    """Revoke admin override - user needs valid subscription."""
    if not user_id:
        return False
    
    try:
        admin = _admin_required()
        
        # Get current subscription status
        resp = (
            admin.table("poker_profiles")
            .select("subscription_status")
            .eq("user_id", user_id)
            .single()
            .execute()
        )
        
        current_status = resp.data.get("subscription_status", "pending") if resp.data else "pending"
        should_be_active = current_status in ("active", "grace_period", "trial")
        
        admin.table("poker_profiles").update({
            "admin_override_active": False,
            "is_active": should_be_active,
        }).eq("user_id", user_id).execute()
        return True
    except Exception as e:
        print(f"[db] admin_revoke_free_access error: {e}")
        return False


def admin_set_subscription_status(user_id: str, status: str) -> bool:
    """Force subscription status (admin only)."""
    valid_statuses = ["pending", "trial", "active", "grace_period", "overdue", "cancelled", "expired"]
    if not user_id or status not in valid_statuses:
        return False
    
    try:
        admin = _admin_required()
        
        is_active = status in ("active", "grace_period", "trial")
        
        admin.table("poker_profiles").update({
            "subscription_status": status,
            "is_active": is_active,
        }).eq("user_id", user_id).execute()
        return True
    except Exception as e:
        print(f"[db] admin_set_subscription_status error: {e}")
        return False


def admin_get_subscription_details(user_id: str) -> Optional[dict]:
    """Get full subscription details for a user."""
    if not user_id:
        return None
    
    try:
        admin = _admin_required()
        resp = (
            admin.table("poker_profiles")
            .select(
                "email, subscription_status, subscription_plan, subscription_amount, "
                "subscription_started_at, subscription_current_period_end, "
                "last_successful_payment_at, failed_payment_count, admin_override_active, "
                "payment_link_url, trial_ends_at, is_trial"
            )
            .eq("user_id", user_id)
            .single()
            .execute()
        )
        return resp.data if resp.data else None
    except Exception as e:
        print(f"[db] admin_get_subscription_details error: {e}")
        return None


def admin_extend_trial(user_id: str, days: int = 7) -> bool:
    """Extend user's trial period."""
    if not user_id or days <= 0:
        return False
    
    try:
        admin = _admin_required()
        
        # Get current trial end
        resp = (
            admin.table("poker_profiles")
            .select("trial_ends_at")
            .eq("user_id", user_id)
            .single()
            .execute()
        )
        
        current_end = None
        if resp.data and resp.data.get("trial_ends_at"):
            try:
                current_end = datetime.fromisoformat(
                    resp.data["trial_ends_at"].replace("Z", "+00:00")
                )
            except Exception:
                pass
        
        # Extend from current end or from now
        base = current_end if current_end else datetime.now(timezone.utc)
        new_end = base + timedelta(days=days)
        
        admin.table("poker_profiles").update({
            "trial_ends_at": new_end.isoformat(),
            "subscription_status": "trial",
            "is_trial": True,
            "is_active": True,
        }).eq("user_id", user_id).execute()
        
        return True
    except Exception as e:
        print(f"[db] admin_extend_trial error: {e}")
        return False


def admin_resend_payment_link(user_id: str) -> Optional[str]:
    """Get payment link for a user (to resend)."""
    if not user_id:
        return None
    
    try:
        admin = _admin_required()
        resp = (
            admin.table("poker_profiles")
            .select("payment_link_url")
            .eq("user_id", user_id)
            .single()
            .execute()
        )
        return resp.data.get("payment_link_url") if resp.data else None
    except Exception as e:
        print(f"[db] admin_resend_payment_link error: {e}")
        return None

# =============================================================================
# HAND OUTCOME RECORDING
# =============================================================================

def record_hand_outcome(
    session_id: str,
    user_id: str,
    outcome: str,  # 'won', 'lost', 'folded', 'they_folded'
    profit_loss: float,
    pot_size: float,
    our_position: str,
    street_reached: str,
    our_hand: str = None,
    board: str = None,
    action_taken: str = None,
    recommendation_given: str = None,
    we_were_aggressor: bool = False,
    bluff_context: dict = None,  # NEW: JSONB bluff metadata — None for non-bluff hands
) -> Optional[dict]:
    """
    Record a hand outcome to poker_hands table.
    
    Called after user clicks WIN/LOSS/FOLD/THEY FOLDED button.
    """
    if not session_id or not user_id:
        return None
    
    try:
        sb = get_supabase()
        
        # Get current hand count for this session
        resp = (
            sb.table("poker_hands")
            .select("id")
            .eq("session_id", session_id)
            .execute()
        )
        hand_number = len(resp.data) + 1 if resp.data else 1
        
        hand_data = {
            "session_id": session_id,
            "user_id": user_id,
            "hand_number": hand_number,
            "played_at": _now_iso(),
            "result": outcome,
            "profit_loss": profit_loss,
            "pot_size": pot_size,
            "our_position": our_position,
            "street_reached": street_reached,
            "our_hand": our_hand,
            "board": board,
            "action_taken": action_taken,
            "recommendation_given": recommendation_given,
            "we_were_aggressor": we_were_aggressor,
            "followed_recommendation": True,
            "is_test": False,
            "bluff_context": bluff_context,  # JSONB — None for non-bluff hands
        }
        
        resp = sb.table("poker_hands").insert(hand_data).execute()
        
        if resp.data and len(resp.data) > 0:
            return resp.data[0]
        return None
        
    except Exception as e:
        print(f"[db] record_hand_outcome error: {e}")
        return None


def get_session_hands(session_id: str) -> List[dict]:
    """Get all hands for a session."""
    if not session_id:
        return []
    
    try:
        sb = get_supabase()
        resp = (
            sb.table("poker_hands")
            .select("*")
            .eq("session_id", session_id)
            .order("hand_number", desc=False)
            .execute()
        )
        return resp.data if resp.data else []
    except Exception as e:
        print(f"[db] get_session_hands error: {e}")
        return []


def get_session_outcome_summary(session_id: str) -> dict:
    """Get outcome breakdown for a session (wins/losses/folds)."""
    if not session_id:
        return {"wins": 0, "losses": 0, "folds": 0, "total": 0}
    
    try:
        hands = get_session_hands(session_id)
        
        wins = sum(1 for h in hands if h.get("result") == "won")
        losses = sum(1 for h in hands if h.get("result") == "lost")
        folds = sum(1 for h in hands if h.get("result") == "folded")
        
        return {
            "wins": wins,
            "losses": losses,
            "folds": folds,
            "total": len(hands),
        }
    except Exception as e:
        print(f"[db] get_session_outcome_summary error: {e}")
        return {"wins": 0, "losses": 0, "folds": 0, "total": 0}

# =============================================================================
# ADMIN SESSION QUERIES
# =============================================================================

def get_recent_sessions_for_user_admin(user_id: str, limit: int = 50) -> List[dict]:
    """Get recent sessions for a user (admin view)."""
    if not user_id:
        return []
    
    try:
        admin = _admin_required()
        resp = (
            admin.table("poker_sessions")
            .select("*")
            .eq("user_id", user_id)
            .order("started_at", desc=True)
            .limit(limit)
            .execute()
        )
        return resp.data if resp.data else []
    except Exception as e:
        print(f"[db] get_recent_sessions_for_user_admin error: {e}")
        return []
    
# =============================================================================
# NEW FUNCTION: get_user_settings()
# =============================================================================
# Add this function to get all user settings for Settings page

def get_user_settings(user_id: str) -> dict:
    """
    Get all user settings for the Settings page.
    
    Returns dict with all configurable settings, with defaults if not set.
    """
    if not user_id:
        return _default_user_settings()
    
    try:
        sb = get_supabase_admin()
        resp = (
            sb.table("poker_profiles")
            .select(
                "current_bankroll, user_mode, default_stakes, "
                "buy_in_count, stop_loss_bi, stop_win_bi, "
                "time_alerts_enabled, time_warning_hours, "
                "stop_loss_alerts_enabled, stop_win_alerts_enabled, "
                "table_check_interval, show_explanations, sound_enabled, theme"
            )
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
        
        if not resp.data:
            return _default_user_settings()
        
        data = resp.data
        
        # Return with defaults for any None values
        return {
            "bankroll": float(data.get("current_bankroll") or 0),
            "risk_mode": data.get("user_mode") or "balanced",
            "default_stakes": data.get("default_stakes") or "$1/$2",
            "buy_in_count": int(data.get("buy_in_count") or 15),
            "stop_loss_bi": float(data.get("stop_loss_bi") or 1.0),
            "stop_win_bi": float(data.get("stop_win_bi") or 3.0),
            "time_alerts_enabled": data.get("time_alerts_enabled", True),
            "time_warning_hours": int(data.get("time_warning_hours") or 3),
            "stop_loss_alerts_enabled": data.get("stop_loss_alerts_enabled", True),
            "stop_win_alerts_enabled": data.get("stop_win_alerts_enabled", True),
            "table_check_interval": int(data.get("table_check_interval") or 20),
            "show_explanations": data.get("show_explanations", True),
            "sound_enabled": data.get("sound_enabled", False),
            "theme": data.get("theme") or "dark",
        }
        
    except Exception as e:
        print(f"[db] get_user_settings error: {e}")
        return _default_user_settings()


def _default_user_settings() -> dict:
    """Return default settings."""
    return {
        "bankroll": 0.0,
        "risk_mode": "balanced",
        "default_stakes": "$1/$2",
        "buy_in_count": 15,
        "stop_loss_bi": 1.0,
        "stop_win_bi": 3.0,
        "time_alerts_enabled": True,
        "time_warning_hours": 3,
        "stop_loss_alerts_enabled": True,
        "stop_win_alerts_enabled": True,
        "table_check_interval": 20,
        "show_explanations": True,
        "sound_enabled": False,
        "theme": "dark",
    }

# =============================================================================
# NEW FUNCTION: update_session_outcome()
# =============================================================================
# Add this function to increment outcome counters

def update_session_outcome(session_id: str, outcome: str) -> bool:
    """
    Increment the appropriate outcome counter for a session.
    
    Args:
        session_id: Session UUID
        outcome: 'won', 'lost', or 'folded'
    
    Returns:
        True if successful
    """
    if not session_id or outcome not in ('won', 'lost', 'folded'):
        return False
    
    try:
        sb = get_supabase()
        
        # Map outcome to column name
        column_map = {
            'won': 'outcomes_won',
            'lost': 'outcomes_lost',
            'folded': 'outcomes_folded',
        }
        column = column_map[outcome]
        
        # Get current value
        resp = (
            sb.table("poker_sessions")
            .select(column)
            .eq("id", session_id)
            .single()
            .execute()
        )
        
        if not resp.data:
            return False
        
        current_value = resp.data.get(column, 0) or 0
        
        # Increment
        sb.table("poker_sessions").update({
            column: current_value + 1
        }).eq("id", session_id).execute()
        
        return True
        
    except Exception as e:
        print(f"[db] update_session_outcome error: {e}")
        return False
    
# =============================================================================
# NEW FUNCTION: get_session_outcomes_from_session()
# =============================================================================
# Get outcome counts directly from session (faster than counting hands)

def get_session_outcomes_from_session(session_id: str) -> dict:
    """
    Get outcome counts from the session record itself.
    
    This is faster than counting from poker_hands table.
    Falls back to counting hands if session columns are empty.
    """
    if not session_id:
        return {"won": 0, "lost": 0, "folded": 0, "total": 0}
    
    try:
        sb = get_supabase()
        resp = (
            sb.table("poker_sessions")
            .select("outcomes_won, outcomes_lost, outcomes_folded")
            .eq("id", session_id)
            .single()
            .execute()
        )
        
        if not resp.data:
            return {"won": 0, "lost": 0, "folded": 0, "total": 0}
        
        won = resp.data.get("outcomes_won", 0) or 0
        lost = resp.data.get("outcomes_lost", 0) or 0
        folded = resp.data.get("outcomes_folded", 0) or 0
        
        return {
            "won": won,
            "lost": lost,
            "folded": folded,
            "total": won + lost + folded,
        }
        
    except Exception as e:
        print(f"[db] get_session_outcomes_from_session error: {e}")
        return {"won": 0, "lost": 0, "folded": 0, "total": 0}


# =============================================================================
# NEW FUNCTION: calculate_stop_amounts()
# =============================================================================
# Helper to calculate stop-loss/win amounts from settings

def calculate_stop_amounts(buy_in: float, stop_loss_bi: float, stop_win_bi: float) -> dict:
    """
    Calculate dollar amounts for stop-loss and stop-win.
    
    Args:
        buy_in: Buy-in amount in dollars
        stop_loss_bi: Stop-loss in buy-ins (e.g., 1.0 = 1 buy-in)
        stop_win_bi: Stop-win in buy-ins (e.g., 3.0 = 3 buy-ins)
    
    Returns:
        dict with stop_loss_amount and stop_win_amount
    """
    return {
        "stop_loss_amount": buy_in * stop_loss_bi,
        "stop_win_amount": buy_in * stop_win_bi,
    }


# =============================================================================
# NEW FUNCTION: sync_settings_to_session_state()
# =============================================================================
# Helper to sync DB settings to Streamlit session state

def sync_settings_to_session_state(user_id: str) -> None:
    """
    Load user settings from DB and sync to st.session_state.
    
    Call this after login or when settings might have changed.
    """
    import streamlit as st
    
    settings = get_user_settings(user_id)
    
    # Sync to session state
    st.session_state["bankroll"] = settings.get("bankroll", 0)
    st.session_state["risk_mode"] = settings.get("risk_mode", "balanced")
    st.session_state["default_stakes"] = settings.get("default_stakes", "$1/$2")
    st.session_state["buy_in_count"] = settings.get("buy_in_count", 15)
    st.session_state["stop_loss_bi"] = settings.get("stop_loss_bi", 1.0)
    st.session_state["stop_win_bi"] = settings.get("stop_win_bi", 3.0)
    st.session_state["time_alerts_enabled"] = settings.get("time_alerts_enabled", True)
    st.session_state["time_warning_hours"] = settings.get("time_warning_hours", 3)
    st.session_state["stop_loss_alerts_enabled"] = settings.get("stop_loss_alerts_enabled", True)
    st.session_state["stop_win_alerts_enabled"] = settings.get("stop_win_alerts_enabled", True)
    st.session_state["table_check_interval"] = settings.get("table_check_interval", 20)


# =============================================================================
# BLUFF STATS OPERATIONS
# =============================================================================

def update_session_bluff_stats(session_id: str, user_bet: bool, opponent_folded: bool, profit: float) -> bool:
    """
    Increment bluff aggregate counters on session record.
    
    Called after each bluff-eligible hand is completed.
    
    Args:
        session_id: Session UUID
        user_bet: True if user chose to bet (or auto-bluff fired)
        opponent_folded: True if opponent folded to our bluff
        profit: Dollar profit/loss from this bluff hand
    """
    if not session_id:
        return False
    try:
        sb = get_supabase()
        resp = (
            sb.table("poker_sessions")
            .select("bluff_spots_total, bluff_spots_bet, bluff_spots_checked, bluff_folds_won, bluff_profit")
            .eq("id", session_id)
            .single()
            .execute()
        )
        if not resp.data:
            return False
        
        d = resp.data
        updates = {
            "bluff_spots_total": (d.get("bluff_spots_total") or 0) + 1,
            "bluff_profit": float(d.get("bluff_profit") or 0) + profit,
        }
        if user_bet:
            updates["bluff_spots_bet"] = (d.get("bluff_spots_bet") or 0) + 1
            if opponent_folded:
                updates["bluff_folds_won"] = (d.get("bluff_folds_won") or 0) + 1
        else:
            updates["bluff_spots_checked"] = (d.get("bluff_spots_checked") or 0) + 1
        
        sb.table("poker_sessions").update(updates).eq("id", session_id).execute()
        return True
    except Exception as e:
        print(f"[db] update_session_bluff_stats error: {e}")
        return False


def get_session_bluff_stats(session_id: str) -> dict:
    """
    Bluff stats for a single session from session record.
    
    Returns dict with: total_spots, times_bet, times_checked,
    folds_won, total_profit, bet_pct, fold_success_pct, avg_per_attempt
    """
    if not session_id:
        return _empty_bluff_stats()
    try:
        sb = get_supabase()
        resp = (
            sb.table("poker_sessions")
            .select("bluff_spots_total, bluff_spots_bet, bluff_spots_checked, bluff_folds_won, bluff_profit")
            .eq("id", session_id)
            .single()
            .execute()
        )
        if not resp.data:
            return _empty_bluff_stats()
        d = resp.data
        total = d.get("bluff_spots_total") or 0
        bet = d.get("bluff_spots_bet") or 0
        folds_won = d.get("bluff_folds_won") or 0
        profit = float(d.get("bluff_profit") or 0)
        return {
            "total_spots": total,
            "times_bet": bet,
            "times_checked": (d.get("bluff_spots_checked") or 0),
            "folds_won": folds_won,
            "total_profit": round(profit, 2),
            "bet_pct": round(bet / total * 100, 1) if total > 0 else 0,
            "fold_success_pct": round(folds_won / bet * 100, 1) if bet > 0 else 0,
            "avg_per_attempt": round(profit / bet, 2) if bet > 0 else 0,
        }
    except Exception as e:
        print(f"[db] get_session_bluff_stats error: {e}")
        return _empty_bluff_stats()


def get_user_bluff_stats(user_id: str) -> dict:
    """
    Aggregated bluff stats across all completed sessions (lifetime).
    
    Returns dict with: total_spots, times_bet, times_checked,
    folds_won, total_profit, bet_pct, fold_success_pct, avg_per_attempt
    """
    if not user_id:
        return _empty_bluff_stats()
    try:
        sb = get_supabase()
        resp = (
            sb.table("poker_sessions")
            .select("bluff_spots_total, bluff_spots_bet, bluff_spots_checked, bluff_folds_won, bluff_profit")
            .eq("user_id", user_id)
            .eq("status", "completed")
            .execute()
        )
        if not resp.data:
            return _empty_bluff_stats()
        
        total = sum(s.get("bluff_spots_total") or 0 for s in resp.data)
        bet = sum(s.get("bluff_spots_bet") or 0 for s in resp.data)
        checked = sum(s.get("bluff_spots_checked") or 0 for s in resp.data)
        folds_won = sum(s.get("bluff_folds_won") or 0 for s in resp.data)
        profit = sum(float(s.get("bluff_profit") or 0) for s in resp.data)
        
        return {
            "total_spots": total,
            "times_bet": bet,
            "times_checked": checked,
            "folds_won": folds_won,
            "total_profit": round(profit, 2),
            "bet_pct": round(bet / total * 100, 1) if total > 0 else 0,
            "fold_success_pct": round(folds_won / bet * 100, 1) if bet > 0 else 0,
            "avg_per_attempt": round(profit / bet, 2) if bet > 0 else 0,
        }
    except Exception as e:
        print(f"[db] get_user_bluff_stats error: {e}")
        return _empty_bluff_stats()


def _empty_bluff_stats() -> dict:
    """Return empty bluff stats structure."""
    return {
        "total_spots": 0,
        "times_bet": 0,
        "times_checked": 0,
        "folds_won": 0,
        "total_profit": 0,
        "bet_pct": 0,
        "fold_success_pct": 0,
        "avg_per_attempt": 0,
    }