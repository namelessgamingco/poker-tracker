# auth.py — Authentication & Subscription Access Control
# Handles login, session management, and subscription-based access

from __future__ import annotations

import os
from typing import Any, Optional
from datetime import datetime, timezone

import streamlit as st
import httpx

from supabase_client import get_supabase, get_supabase_admin, reset_supabase_client


# ---------- Helpers ----------

def _get_secret(name: str, default: Any = None) -> Any:
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


def _get_app_env() -> str:
    """Get current environment."""
    return str(_get_secret("APP_ENV", "prod")).lower().strip()


def _supabase_url() -> str:
    env = _get_app_env()
    return str(_get_secret("SUPABASE_URL_DEV" if env == "dev" else "SUPABASE_URL_PROD") or "")


def _supabase_anon_key() -> str:
    env = _get_app_env()
    return str(_get_secret("SUPABASE_ANON_KEY_DEV" if env == "dev" else "SUPABASE_ANON_KEY_PROD") or "")


APP_ENV = _get_app_env()

ADMIN_EMAILS = {
    e.strip().lower()
    for e in str(_get_secret("ADMIN_EMAILS", "")).split(",")
    if e.strip()
}


# ---------- GoTrue REST Login ----------

def _gotrue_password_login(email: str, password: str) -> dict:
    """Direct REST call to Supabase GoTrue for password auth."""
    url = _supabase_url().rstrip("/")
    key = _supabase_anon_key().strip()
    
    if not url or not key:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_ANON_KEY in secrets.")

    endpoint = f"{url}/auth/v1/token?grant_type=password"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    payload = {"email": email, "password": password}

    r = httpx.post(endpoint, headers=headers, json=payload, timeout=20.0)
    
    if r.status_code >= 400:
        error_detail = r.text
        try:
            error_json = r.json()
            error_detail = error_json.get("error_description") or error_json.get("msg") or r.text
        except Exception:
            pass
        raise RuntimeError(f"Login failed: {error_detail}")

    return r.json()


# ---------- Session State Helpers ----------

def _init_session_state():
    """Initialize all auth-related session state with defaults."""
    defaults = {
        "authenticated": False,
        "access_token": None,
        "refresh_token": None,
        "user": None,
        "email": None,
        "is_admin": False,
        "role": "player",
        "is_active": True,
        "profile_created": False,
        # Subscription fields
        "subscription_status": "pending",
        "subscription_plan": None,
        "admin_override_active": False,
        "trial_ends_at": None,
        "payment_link_url": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _clear_auth_state():
    """Clear all auth-related session state."""
    keys_to_clear = [
        "authenticated", "access_token", "refresh_token", "user", "email",
        "is_admin", "role", "is_active", "profile_created",
        "subscription_status", "subscription_plan", "admin_override_active",
        "trial_ends_at", "payment_link_url",
    ]
    for key in keys_to_clear:
        if key in ["authenticated", "is_admin", "is_active", "profile_created", "admin_override_active"]:
            st.session_state[key] = False
        else:
            st.session_state[key] = None
    
    st.session_state["authenticated"] = False
    st.session_state["is_active"] = True
    st.session_state["role"] = "player"
    st.session_state["subscription_status"] = "pending"
    
    # Clear Supabase client
    try:
        reset_supabase_client()
    except Exception:
        pass
    
    # Clear user data caches
    try:
        from cache import clear_all_user_caches
        clear_all_user_caches()
    except Exception:
        pass


# ---------- UI Helpers ----------

def _hide_sidebar_while_logged_out():
    """Hide sidebar navigation when user is not logged in."""
    st.markdown(
        """
        <style>
            section[data-testid="stSidebar"] > div:first-child {
                padding-top: 2rem;
            }
            section[data-testid="stSidebar"] [data-testid="stSidebarNav"] {
                display: none !important;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ---------- Logout ----------

def sign_out():
    """Clear session and force re-render to login screen."""
    _clear_auth_state()
    st.rerun()


# ---------- Login UI ----------

def _login_ui():
    """Render login form and handle authentication."""
    _hide_sidebar_while_logged_out()

    # Hide Streamlit branding on login screen
    st.markdown(
        """
        <style>
          div[data-testid="stToolbar"] {display: none !important;}
          header[data-testid="stHeader"] {height: 0rem !important;}
          footer {visibility: hidden !important;}
          .stDeployButton {display: none !important;}
          [data-testid="stDecoration"] {display: none !important;}
          .viewerBadge_container__r5tak {display: none !important;}
          .styles_viewerBadge__CvC9N {display: none !important;}
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("🃏 Poker Decision App")
    st.markdown("**One answer. No thinking required.**")
    
    # Show environment indicator in dev
    if APP_ENV == "dev":
        st.caption("🔧 Development Environment")
    
    st.markdown("---")
    
    email_input = st.text_input("Email", key="login_email_input")
    password_input = st.text_input("Password", type="password", key="login_password_input")

    if st.button("Sign In", type="primary", use_container_width=True):
        if not email_input or not password_input:
            st.error("Please enter both email and password.")
            return
        
        try:
            email = email_input.strip().lower()
            
            # Authenticate via GoTrue
            data = _gotrue_password_login(email, password_input)
            
            access_token = data.get("access_token")
            refresh_token = data.get("refresh_token")
            user_obj = data.get("user")
            
            if not access_token:
                st.error("Login failed: No access token received.")
                return
            
            # Clear any stale caches from previous user
            try:
                from cache import clear_all_user_caches
                clear_all_user_caches()
            except Exception:
                pass
            
            # Store in session state
            st.session_state["authenticated"] = True
            st.session_state["access_token"] = access_token
            st.session_state["refresh_token"] = refresh_token
            st.session_state["user"] = user_obj
            
            # Extract email from user object
            if isinstance(user_obj, dict):
                user_email = (user_obj.get("email") or "").strip().lower()
            else:
                user_email = email
            
            st.session_state["email"] = user_email
            st.session_state["is_admin"] = user_email in ADMIN_EMAILS
            
            # Reset Supabase client for fresh state
            try:
                reset_supabase_client()
            except Exception:
                pass
            
            # Bind session to Supabase client for RLS
            try:
                sb = get_supabase()
                sb.auth.set_session(access_token, refresh_token)
            except Exception:
                pass
            
            st.rerun()
            
        except Exception as e:
            st.error(f"Login failed: {e}")

    st.stop()


# ---------- Profile & Subscription Management ----------

def _ensure_profile(user_id: str, email: str) -> Optional[dict]:
    """
    Check if profile exists, create if not.
    Returns profile dict or None on failure.
    Uses admin client to bypass RLS.
    """
    try:
        sb_admin = get_supabase_admin()
    except Exception as e:
        st.error(f"Database configuration error: {e}")
        return None

    # Try to fetch existing profile
    try:
        resp = (
            sb_admin.table("poker_profiles")
            .select("*")
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
        
        profile = resp.data if hasattr(resp, "data") else None
        
        if profile:
            return profile
            
    except Exception as e:
        st.error(f"Error checking profile: {e}")
        return None

    # Create new profile (shouldn't happen normally - admin creates users)
    try:
        new_profile = {
            "user_id": user_id,
            "email": email,
            "role": "player",
            "is_active": False,  # Inactive until subscription
            "is_admin": False,
            "allowed": True,
            "subscription_status": "pending",
            "user_mode": "balanced",
            "default_stakes": "$1/$2",
        }
        
        sb_admin.table("poker_profiles").insert(new_profile).execute()
        st.session_state["profile_created"] = True
        
        return new_profile
        
    except Exception as e:
        st.error(f"Could not create profile: {e}")
        return None


def check_subscription_access(profile: dict) -> tuple[bool, str, Optional[str]]:
    """
    Check if user has access based on subscription status.
    
    Returns:
        (has_access, status_message, payment_link_url)
    
    Access granted if:
    - admin_override_active = True (admin gave free access)
    - subscription_status = 'active'
    - subscription_status = 'grace_period' (with warning)
    - subscription_status = 'trial' AND trial not expired
    """
    
    # Admin override trumps everything
    if profile.get("admin_override_active"):
        return True, "Admin access granted", None
    
    status = profile.get("subscription_status", "pending")
    payment_link = profile.get("payment_link_url")
    
    # Active subscription
    if status == "active":
        return True, "active", None
    
    # Grace period - allow with warning
    if status == "grace_period":
        return True, "grace_period", payment_link
    
    # Trial period - check expiration
    if status == "trial":
        trial_ends_at = profile.get("trial_ends_at")
        if trial_ends_at:
            try:
                # Parse the trial end date
                if isinstance(trial_ends_at, str):
                    trial_end = datetime.fromisoformat(trial_ends_at.replace("Z", "+00:00"))
                else:
                    trial_end = trial_ends_at
                
                now = datetime.now(timezone.utc)
                
                if now < trial_end:
                    days_left = (trial_end - now).days
                    return True, f"trial_{days_left}_days", payment_link
                else:
                    return False, "trial_expired", payment_link
            except Exception:
                pass
        
        # Trial without end date - allow (shouldn't happen)
        return True, "trial", payment_link
    
    # Pending - never paid
    if status == "pending":
        return False, "pending", payment_link
    
    # Overdue - past grace period
    if status == "overdue":
        return False, "overdue", payment_link
    
    # Cancelled
    if status == "cancelled":
        return False, "cancelled", payment_link
    
    # Expired
    if status == "expired":
        return False, "expired", payment_link
    
    # Unknown status - deny access
    return False, "unknown", payment_link


def _show_lockout_screen(status: str, payment_link: Optional[str]):
    """Show lockout screen when user doesn't have access."""
    
    _hide_sidebar_while_logged_out()
    
    st.title("🃏 Poker Decision App")
    st.markdown("---")
    
    if status == "pending":
        st.error("### Complete Your Subscription")
        st.markdown(
            """
            Your account has been created but you haven't completed payment yet.
            
            Subscribe to get access to:
            - **Mathematically optimal decisions** for every poker situation
            - **Exact bet sizing** — "$12", not "raise 3x"
            - **Session management** — know when to stop
            - **Expected win rate: +6-7 BB/100**
            """
        )
    
    elif status == "trial_expired":
        st.error("### Your Free Trial Has Ended")
        st.markdown(
            """
            We hope you enjoyed your trial! Subscribe now to continue using
            the app and keep making +EV decisions at the table.
            """
        )
    
    elif status == "overdue":
        st.error("### Payment Overdue")
        st.markdown(
            """
            Your subscription payment failed and the grace period has ended.
            
            Please update your payment method to restore access.
            """
        )
    
    elif status == "cancelled":
        st.warning("### Subscription Cancelled")
        st.markdown(
            """
            Your subscription has been cancelled. 
            
            You can resubscribe anytime to regain access.
            """
        )
    
    elif status == "expired":
        st.warning("### Subscription Expired")
        st.markdown(
            """
            Your subscription has expired.
            
            Renew now to continue making optimal decisions at the table.
            """
        )
    
    else:
        st.error("### Access Denied")
        st.markdown("Please contact support if you believe this is an error.")
    
    # Payment button
    if payment_link:
        st.markdown("---")
        st.link_button(
            "💳 Subscribe Now — $299/month",
            payment_link,
            type="primary",
            use_container_width=True,
        )
        st.caption("Secure crypto payment via Radom. Cancel anytime.")
    
    st.markdown("---")
    
    # Sign out button
    if st.button("Sign Out", use_container_width=True):
        sign_out()
    
    st.stop()


# ---------- Main Auth Gate ----------

def require_auth():
    """
    Main authentication gate. Call at the top of every protected page.
    
    Returns the user object if authenticated and has access.
    Shows login UI or lockout screen and stops execution if not.
    """
    _init_session_state()
    
    # Check if already authenticated this session
    if not st.session_state.get("authenticated"):
        _login_ui()
        st.stop()
    
    # Validate we have required data
    access_token = st.session_state.get("access_token")
    user = st.session_state.get("user")
    
    if not access_token or not user:
        _clear_auth_state()
        _login_ui()
        st.stop()
    
    # Ensure Supabase client has the session bound
    try:
        sb = get_supabase()
        refresh_token = st.session_state.get("refresh_token") or ""
        sb.auth.set_session(access_token, refresh_token)
    except Exception:
        _clear_auth_state()
        _login_ui()
        st.stop()
    
    # Extract user ID
    if isinstance(user, dict):
        user_id = user.get("id") or user.get("user_id") or user.get("sub")
    else:
        user_id = getattr(user, "id", None) or getattr(user, "user_id", None)
    
    if not user_id:
        st.error("Authentication error: Could not determine user ID.")
        if st.button("Sign Out"):
            sign_out()
        st.stop()
    
    user_id = str(user_id)
    email = str(st.session_state.get("email") or "")
    
    # Profile gate
    profile = _ensure_profile(user_id, email)
    
    if not profile:
        st.error("Could not load or create your profile. Please contact support.")
        if st.button("Sign Out"):
            sign_out()
        st.stop()
    
    # Check basic access (allowed flag)
    allowed = profile.get("allowed", True)
    if not allowed:
        st.error("Your access has been revoked. Please create a support ticket.")
        if st.button("Sign Out"):
            sign_out()
        st.stop()
    
    # Check subscription access
    has_access, status_msg, payment_link = check_subscription_access(profile)
    
    # Store subscription info in session state
    st.session_state["subscription_status"] = profile.get("subscription_status", "pending")
    st.session_state["user_db_id"] = profile.get("id") or user_id
    st.session_state["subscription_plan"] = profile.get("subscription_plan")
    st.session_state["admin_override_active"] = profile.get("admin_override_active", False)
    st.session_state["trial_ends_at"] = profile.get("trial_ends_at")
    st.session_state["payment_link_url"] = payment_link
    
    if not has_access:
        _show_lockout_screen(status_msg, payment_link)
        st.stop()
    
    # Show grace period warning (but allow access)
    if status_msg == "grace_period":
        st.session_state["show_grace_period_warning"] = True
    
    # Update session state with profile data
    role = str(profile.get("role", "player") or "player")
    is_admin_db = bool(profile.get("is_admin", False))
    is_active = bool(profile.get("is_active", True))
    
    st.session_state["role"] = role
    st.session_state["is_active"] = is_active
    st.session_state["is_admin"] = is_admin_db or (email in ADMIN_EMAILS) or (role == "admin")
    
    # Store user settings from profile
    st.session_state["user_mode"] = profile.get("user_mode", "balanced")
    st.session_state["default_stakes"] = profile.get("default_stakes", "$1/$2")
    st.session_state["current_bankroll"] = profile.get("current_bankroll", 0)
    
    return st.session_state["user"]


# ---------- Session Start Access Check ----------

def check_access_for_session_start() -> tuple[bool, str]:
    """
    Additional access check when starting a new poker session.
    
    Called from Play Session page before allowing session start.
    Re-checks subscription status to catch mid-session expiration.
    
    Returns:
        (can_start, message)
    """
    user = st.session_state.get("user")
    if not user:
        return False, "Not authenticated"
    
    # Get fresh profile data
    try:
        if isinstance(user, dict):
            user_id = user.get("id") or user.get("user_id") or user.get("sub")
        else:
            user_id = getattr(user, "id", None) or getattr(user, "user_id", None)
        
        sb_admin = get_supabase_admin()
        resp = (
            sb_admin.table("poker_profiles")
            .select("subscription_status, admin_override_active, trial_ends_at, payment_link_url")
            .eq("user_id", str(user_id))
            .single()
            .execute()
        )
        
        if not resp.data:
            return False, "Profile not found"
        
        profile = resp.data
        has_access, status_msg, _ = check_subscription_access(profile)
        
        if not has_access:
            return False, f"Subscription {status_msg}. Please renew to start a session."
        
        return True, "OK"
        
    except Exception as e:
        # On error, allow session (don't break user flow)
        return True, f"Warning: Could not verify subscription ({e})"