# auth.py — Authentication & Subscription Access Control
# Handles login, session management, and subscription-based access

from __future__ import annotations

import os
from typing import Any, Optional
from datetime import datetime, timezone

import streamlit as st
import httpx

from supabase_client import get_supabase_admin, get_supabase_admin_fresh, reset_supabase_client


# ---------- Retry Helper ----------

def _admin_query_with_retry(query_fn, label="auth"):
    """Run an admin DB query with one retry on stale connection."""
    try:
        return query_fn(get_supabase_admin())
    except Exception as e:
        err = str(e).lower()
        retryable = any(k in err for k in [
            "server disconnected", "'nonetype'", "connection",
            "closed", "broken pipe", "timed out", "reset by peer",
        ])
        if retryable:
            import time as _time
            _time.sleep(0.5)
            try:
                print(f"[auth] {label}: retrying with fresh client...")
                return query_fn(get_supabase_admin_fresh())
            except Exception as retry_err:
                print(f"[auth] {label}: retry also failed: {retry_err}")
                raise retry_err
        raise


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


def _gotrue_refresh(refresh_token: str) -> Optional[dict]:
    """Exchange a refresh token for new access + refresh tokens via GoTrue REST API.
    
    Used for silent re-authentication when Streamlit's server-side session resets
    (e.g., Railway container restart, WebSocket collision). The refresh token
    survives in st.query_params (browser URL) while st.session_state is wiped.
    """
    url = _supabase_url().rstrip("/")
    key = _supabase_anon_key().strip()
    if not url or not key:
        return None
    
    endpoint = f"{url}/auth/v1/token?grant_type=refresh_token"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    r = httpx.post(endpoint, headers=headers, json={"refresh_token": refresh_token}, timeout=10.0)
    if r.status_code >= 400:
        return None
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
    # Remove persisted refresh token from URL
    try:
        if "_rt" in st.query_params:
            del st.query_params["_rt"]
    except Exception:
        pass
    st.rerun()



# ---------- Login UI ----------

def _login_ui():
    """Render login form and handle authentication."""
    _hide_sidebar_while_logged_out()

    st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700;800&family=Inter:wght@400;500;600;700&display=swap');
div[data-testid="stToolbar"] {display: none !important;}
header[data-testid="stHeader"] {height: 0rem !important;}
footer {visibility: hidden !important;}
.stDeployButton {display: none !important;}
[data-testid="stDecoration"] {display: none !important;}
[data-testid="stSidebarNav"] {display: none !important;}
section[data-testid="stSidebar"] {display: none !important;}
[data-testid="stAppViewContainer"] {background: #0A0A12;}
.block-container {max-width: 440px; padding-top: 4rem !important;}
.stTextInput > div > div > input {
    background: rgba(255,255,255,0.04) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 10px !important; color: #E0E0E0 !important;
    padding: 12px 16px !important; font-size: 14px !important;
}
.stTextInput > div > div > input:focus {
    border-color: rgba(105,240,174,0.4) !important;
    box-shadow: 0 0 0 1px rgba(105,240,174,0.15) !important;
}
.stTextInput > label {
    color: rgba(255,255,255,0.4) !important; font-size: 12px !important;
    letter-spacing: 0.03em !important; text-transform: uppercase !important;
}
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #69F0AE 0%, #4CAF50 100%) !important;
    color: #0A0A12 !important; font-weight: 700 !important;
    border: none !important; border-radius: 10px !important;
    padding: 12px 24px !important; font-size: 15px !important;
}
</style>""", unsafe_allow_html=True)

    st.markdown('<div style="text-align:center;padding:0 0 32px 0"><div style="font-family:JetBrains Mono,monospace;font-size:28px;font-weight:800;letter-spacing:0.08em;color:#E0E0E0;margin-bottom:10px">NAMELESS POKER</div><div style="font-size:14px;color:rgba(255,255,255,0.35)">One answer. No thinking required.</div></div>', unsafe_allow_html=True)

    if APP_ENV == "dev":
        st.markdown('<div style="text-align:center;margin-bottom:16px"><span style="font-size:11px;color:rgba(255,255,255,0.2);background:rgba(255,255,255,0.04);padding:4px 10px;border-radius:4px">DEV ENVIRONMENT</span></div>', unsafe_allow_html=True)

    st.markdown('<div style="height:1px;background:rgba(255,255,255,0.06);margin:0 0 24px 0"></div>', unsafe_allow_html=True)

    email_input = st.text_input("Email", key="login_email_input")
    password_input = st.text_input("Password", type="password", key="login_password_input")

    _err = '<div style="text-align:center;padding:12px;background:rgba(255,82,82,0.08);border:1px solid rgba(255,82,82,0.2);border-radius:8px;margin-top:8px"><span style="color:#FF5252;font-size:13px">{}</span></div>'

    if st.button("Sign In", type="primary", use_container_width=True):
        if not email_input or not password_input:
            st.markdown(_err.format("Enter your email and password to continue."), unsafe_allow_html=True)
            return

        try:
            email = email_input.strip().lower()
            data = _gotrue_password_login(email, password_input)
            access_token = data.get("access_token")
            refresh_token = data.get("refresh_token")
            user_obj = data.get("user")

            if not access_token:
                st.markdown(_err.format("Authentication failed. Please try again."), unsafe_allow_html=True)
                return

            try:
                from cache import clear_all_user_caches
                clear_all_user_caches()
            except Exception:
                pass

            st.session_state["authenticated"] = True
            st.session_state["access_token"] = access_token
            st.session_state["refresh_token"] = refresh_token
            st.session_state["user"] = user_obj

            if isinstance(user_obj, dict):
                user_email = (user_obj.get("email") or "").strip().lower()
            else:
                user_email = email

            st.session_state["email"] = user_email
            st.session_state["is_admin"] = user_email in ADMIN_EMAILS

            # Persist refresh token in URL for session-reset survival
            # When Streamlit kills a session ("already connected"), query_params
            # survive because they're in the browser URL, not server memory.
            try:
                st.query_params["_rt"] = refresh_token
            except Exception:
                pass

            try:
                reset_supabase_client()
            except Exception:
                pass

            st.rerun()

        except Exception as e:
            error_msg = str(e)
            if "Invalid login credentials" in error_msg:
                display_msg = "Incorrect email or password."
            elif "Email not confirmed" in error_msg:
                display_msg = "Check your email for a confirmation link."
            elif "too many requests" in error_msg.lower():
                display_msg = "Too many attempts. Wait a moment and try again."
            elif "connection" in error_msg.lower() or "timed out" in error_msg.lower():
                display_msg = "Connection issue. Please try again."
            else:
                display_msg = "Unable to sign in. Please check your credentials."
            st.markdown(_err.format(display_msg), unsafe_allow_html=True)

    # ── Apply + Support links ──
    st.markdown("""
    <div style="margin-top:32px;display:flex;flex-direction:column;gap:10px;">
        <a href="https://namelessgaming.co/#sqs-form" target="_blank" style="
            display:block;text-align:center;padding:12px 16px;
            background:rgba(0,210,106,0.06);border:1px solid rgba(0,210,106,0.2);
            border-radius:10px;text-decoration:none;
        ">
            <div style="font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:700;color:#69F0AE;letter-spacing:0.04em;">REQUEST ACCESS</div>
            <div style="font-size:11px;color:rgba(255,255,255,0.3);margin-top:4px;">Don't have an account? Limited spots available.</div>
        </a>
        <a href="https://discord.com/channels/1169748589522718770/1268729463500439553" target="_blank" style="
            display:block;text-align:center;padding:12px 16px;
            background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);
            border-radius:10px;text-decoration:none;
        ">
            <div style="font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:600;color:rgba(255,255,255,0.5);letter-spacing:0.04em;">💬 NEED HELP?</div>
            <div style="font-size:11px;color:rgba(255,255,255,0.2);margin-top:4px;">Open a support ticket on Discord</div>
        </a>
    </div>
    <div style="text-align:center;padding:24px 0 0 0"><div style="font-family:JetBrains Mono,monospace;font-size:10px;color:rgba(255,255,255,0.12);letter-spacing:0.05em">Texas Hold&#39;em NL 6-Max Cash</div></div>
    """, unsafe_allow_html=True)

    st.stop()

# ---------- Profile & Subscription Management ----------

def _ensure_profile(user_id: str, email: str) -> Optional[dict]:
    """
    Check if profile exists, create if not.
    Returns profile dict or None on failure.
    Uses admin client to bypass RLS. Retries on stale connections.
    """
    # Fetch existing profile WITH RETRY
    try:
        def _fetch(sb_admin):
            resp = (
                sb_admin.table("poker_profiles")
                .select("*")
                .eq("user_id", user_id)
                .maybe_single()
                .execute()
            )
            return resp.data if hasattr(resp, "data") else None

        profile = _admin_query_with_retry(_fetch, "ensure_profile_fetch")
        if profile:
            return profile

    except Exception as e:
        print(f"[auth] _ensure_profile fetch failed after retry: {e}")
        return None

    # Create new profile WITH RETRY (shouldn't happen normally - admin creates users)
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

        def _create(sb_admin):
            sb_admin.table("poker_profiles").insert(new_profile).execute()
            return new_profile

        result = _admin_query_with_retry(_create, "ensure_profile_create")
        st.session_state["profile_created"] = True
        return result

    except Exception as e:
        print(f"[auth] _ensure_profile create failed after retry: {e}")
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
    
    # Banned
    if status == "banned":
        return False, "banned", None
    
    # Unknown status - deny access
    return False, "unknown", payment_link



def _show_lockout_screen(status, payment_link):
    """Show lockout screen when user does not have access."""

    _hide_sidebar_while_logged_out()

    st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700;800&family=Inter:wght@400;500;600;700&display=swap');
div[data-testid="stToolbar"] {display: none !important;}
header[data-testid="stHeader"] {height: 0rem !important;}
footer {visibility: hidden !important;}
.stDeployButton {display: none !important;}
[data-testid="stSidebarNav"] {display: none !important;}
section[data-testid="stSidebar"] {display: none !important;}
[data-testid="stAppViewContainer"] {background: #0A0A12;}
.block-container {max-width: 520px; padding-top: 3rem !important;}
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #69F0AE 0%, #4CAF50 100%) !important;
    color: #0A0A12 !important; font-weight: 700 !important;
    border: none !important; border-radius: 10px !important;
    padding: 12px 24px !important; font-size: 15px !important;
}
</style>""", unsafe_allow_html=True)

    st.markdown('<div style="text-align:center;padding:0 0 24px 0"><div style="font-family:JetBrains Mono,monospace;font-size:24px;font-weight:800;letter-spacing:0.08em;color:#E0E0E0">NAMELESS POKER</div></div>', unsafe_allow_html=True)
    st.markdown('<div style="height:1px;background:rgba(255,255,255,0.06);margin:0 0 28px 0"></div>', unsafe_allow_html=True)

    msgs = {
        "pending": ("&#x1F512;", "Complete Your Subscription", "Your account is ready. Subscribe to unlock real-time poker decisions, exact bet sizing, session management, and an expected win rate of +6-7 BB/100."),
        "trial_expired": ("&#x23F0;", "Your Free Trial Has Ended", "We hope you saw the value. Subscribe now to keep making +EV decisions at the table and let the math work for you."),
        "overdue": ("&#x26A0;", "Payment Overdue", "Your payment failed and the grace period has ended. Update your payment method to restore access immediately."),
        "cancelled": ("&#x270B;", "Subscription Cancelled", "Your subscription has been cancelled. You can resubscribe anytime to regain access to all features."),
        "expired": ("&#x1F4C5;", "Subscription Expired", "Your subscription has expired. Renew now to continue making optimal decisions at the table."),
        "banned": ("&#x26D4;", "Account Suspended", "Your account has been suspended. Please contact admin for more information."),
    }

    icon, title, body = msgs.get(status, ("&#x1F512;", "Access Denied", "Please contact support if you believe this is an error."))

    st.markdown(f'<div style="background:linear-gradient(135deg,#0F0F1A 0%,#151520 100%);border:1px solid rgba(255,255,255,0.06);border-radius:14px;padding:32px 28px;text-align:center"><div style="font-size:36px;margin-bottom:16px">{icon}</div><div style="font-size:20px;font-weight:700;color:#E0E0E0;margin-bottom:12px">{title}</div><div style="font-size:14px;color:rgba(255,255,255,0.45);line-height:1.7;max-width:400px;margin:0 auto">{body}</div></div>', unsafe_allow_html=True)

    if payment_link:
        st.markdown('<div style="margin-top:20px"></div>', unsafe_allow_html=True)
        st.link_button("Subscribe Now", payment_link, type="primary", use_container_width=True)
        st.markdown('<div style="text-align:center;margin-top:8px"><span style="font-size:11px;color:rgba(255,255,255,0.2)">Secure payment via Radom. Cancel anytime.</span></div>', unsafe_allow_html=True)

    st.markdown('<div style="margin-top:24px"></div>', unsafe_allow_html=True)

    if st.button("Sign Out", use_container_width=True):
        sign_out()

    st.stop()

# ---------- Main Auth Gate ----------

def require_auth():
    """
    Main authentication gate. Call at the top of every protected page.
    
    Returns the user object if authenticated and has access.
    Shows login UI or lockout screen and stops execution if not.
    
    If Streamlit's server resets the session ("Session with id X is already 
    connected! Connecting to a new session"), st.session_state is wiped but 
    the refresh token survives in st.query_params (browser URL). This function
    detects that scenario and silently re-authenticates without showing login.
    """
    _init_session_state()
    
    # Check if already authenticated this session
    if not st.session_state.get("authenticated"):
        # ── Silent re-auth: recover from Streamlit session reset ──
        # query_params survive session resets because they're in the browser URL.
        rt = st.query_params.get("_rt")
        if rt:
            try:
                reauth = _gotrue_refresh(rt)
                if reauth and reauth.get("access_token"):
                    access_token = reauth["access_token"]
                    refresh_token = reauth.get("refresh_token", rt)
                    user_obj = reauth.get("user", {})
                    user_email = ""
                    if isinstance(user_obj, dict):
                        user_email = (user_obj.get("email") or "").strip().lower()
                    
                    # Re-populate session state
                    st.session_state["authenticated"] = True
                    st.session_state["access_token"] = access_token
                    st.session_state["refresh_token"] = refresh_token
                    st.session_state["user"] = user_obj
                    st.session_state["email"] = user_email
                    st.session_state["is_admin"] = user_email in ADMIN_EMAILS
                    
                    # Rotate the stored refresh token
                    try:
                        st.query_params["_rt"] = refresh_token
                    except Exception:
                        pass
                    
                    print(f"[auth] Silent re-auth successful for {user_email}")
                    st.rerun()
                else:
                    # Refresh failed (token expired/revoked) — clear and show login
                    print("[auth] Silent re-auth: refresh token invalid, clearing")
                    try:
                        del st.query_params["_rt"]
                    except Exception:
                        pass
            except Exception as e:
                print(f"[auth] Silent re-auth failed: {e}")
                try:
                    del st.query_params["_rt"]
                except Exception:
                    pass
        
        _login_ui()
        st.stop()
    
    # Validate we have required data
    access_token = st.session_state.get("access_token")
    user = st.session_state.get("user")
    
    if not access_token or not user:
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
    
    # Profile gate (with cached fallback for transient DB errors)
    profile = _ensure_profile(user_id, email)
    
    # Cache profile on success for fallback during transient failures
    cache_key = f"_profile_cache_{user_id}"
    if profile:
        st.session_state[cache_key] = profile
    else:
        # Fallback: use cached profile from a previous successful fetch
        cached = st.session_state.get(cache_key)
        if cached and isinstance(cached, dict):
            print("[auth] Using cached profile after _ensure_profile failure")
            profile = cached
    
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
    st.session_state["is_trial"] = profile.get("is_trial", False)
    st.session_state["trial_ends_at"] = profile.get("trial_ends_at")
    st.session_state["payment_link_url"] = payment_link
    
    if not has_access:
        # Auto-update expired trials in DB so admin dashboard is accurate
        if status_msg == "trial_expired":
            try:
                from db import update_profile
                update_profile(user_id, {"subscription_status": "expired", "is_trial": False})
            except Exception:
                pass  # Non-critical — access is already denied
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
    
    # Get fresh profile data WITH RETRY
    try:
        if isinstance(user, dict):
            user_id = user.get("id") or user.get("user_id") or user.get("sub")
        else:
            user_id = getattr(user, "id", None) or getattr(user, "user_id", None)
        
        def _fetch_sub(sb_admin):
            resp = (
                sb_admin.table("poker_profiles")
                .select("subscription_status, admin_override_active, trial_ends_at, payment_link_url")
                .eq("user_id", str(user_id))
                .single()
                .execute()
            )
            if not resp.data:
                raise Exception("Profile not found")
            return resp.data
        
        profile = _admin_query_with_retry(_fetch_sub, "check_access_session")
        has_access, status_msg, _ = check_subscription_access(profile)
        
        if not has_access:
            return False, f"Subscription {status_msg}. Please renew to start a session."
        
        return True, "OK"
        
    except Exception as e:
        # On error, allow session (don't break user flow)
        return True, f"Warning: Could not verify subscription ({e})"