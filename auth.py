# auth.py — Session-state only auth (no cookies, no refresh persistence)
# Streamlit Cloud compatible. Hard refresh = re-login.
from __future__ import annotations

import os
from typing import Any, Optional

import streamlit as st
import httpx

from supabase_client import get_supabase, get_supabase_admin


# ---------------- Helpers ----------------
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


def _supabase_url() -> str:
    env = str(_get_secret("APP_ENV", "prod")).lower().strip()
    return str(_get_secret("SUPABASE_URL_DEV" if env == "dev" else "SUPABASE_URL_PROD") or "")


def _supabase_anon_key() -> str:
    env = str(_get_secret("APP_ENV", "prod")).lower().strip()
    return str(_get_secret("SUPABASE_ANON_KEY_DEV" if env == "dev" else "SUPABASE_ANON_KEY_PROD") or "")


APP_ENV = str(_get_secret("APP_ENV", "prod")).lower().strip()

ADMIN_EMAILS = {
    e.strip().lower()
    for e in str(_get_secret("ADMIN_EMAILS", "admin@namelessgaming.co")).split(",")
    if e.strip()
}


# ---------------- GoTrue REST login ----------------
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


# ---------------- Session state helpers ----------------
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
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _clear_auth_state():
    """Clear all auth-related session state."""
    keys_to_clear = [
        "authenticated",
        "access_token", 
        "refresh_token",
        "user",
        "email",
        "is_admin",
        "role",
        "is_active",
        "profile_created",
    ]
    for key in keys_to_clear:
        st.session_state[key] = None if key not in ("authenticated", "is_admin", "is_active", "profile_created") else False
    
    st.session_state["authenticated"] = False
    st.session_state["is_active"] = True
    st.session_state["role"] = "player"
    
    # ✅ Clear Supabase client so next login gets a fresh one
    try:
        from supabase_client import reset_supabase_client
        reset_supabase_client()
    except Exception:
        pass
    
    # ✅ Clear all user data caches to prevent bleed between users
    try:
        from cache import clear_all_user_caches
        clear_all_user_caches()
    except Exception:
        pass


# ---------------- UI helpers ----------------
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


# ---------------- Logout ----------------
def sign_out():
    """Clear session and force re-render to login screen."""
    _clear_auth_state()
    st.rerun()


# ---------------- Login UI ----------------
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

    st.title("Bacc Core Tracker — Login")
    
    # Show environment indicator in dev
    if APP_ENV == "dev":
        st.caption("🔧 Development Environment")
    
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
            
            # ✅ Clear any stale caches from previous user BEFORE setting new auth
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
            
            # ✅ Reset Supabase client to ensure fresh state for this user
            try:
                from supabase_client import reset_supabase_client
                reset_supabase_client()
            except Exception:
                pass
            
            # Bind session to fresh Supabase client for RLS
            try:
                sb = get_supabase()
                sb.auth.set_session(access_token, refresh_token)
            except Exception:
                pass  # Non-fatal, we have the tokens
            
            st.rerun()
            
        except Exception as e:
            st.error(f"Login failed: {e}")

    st.stop()


# ---------------- Profile gate ----------------
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
            sb_admin.table("profiles")
            .select("user_id, email, role, is_active, is_admin, allowed")
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

    # Create new profile
    try:
        new_profile = {
            "user_id": user_id,
            "email": email,
            "role": "player",
            "is_active": True,
            "is_admin": False,
            "allowed": True,
        }
        
        sb_admin.table("profiles").insert(new_profile).execute()
        st.session_state["profile_created"] = True
        
        return new_profile
        
    except Exception as e:
        st.error(f"Could not create profile: {e}")
        return None


# ---------------- Main auth gate ----------------
def require_auth():
    """
    Main authentication gate. Call at the top of every protected page.
    
    Returns the user object if authenticated.
    Shows login UI and stops execution if not authenticated.
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
        # If session binding fails, clear and re-login
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
        st.error("Could not load or create your profile. Please contact an admin.")
        if st.button("Sign Out"):
            sign_out()
        st.stop()
    
    # Check access permissions
    allowed = profile.get("allowed", True)
    is_active = profile.get("is_active", True)
    
    if not allowed:
        st.error("Your access has been revoked. Please contact an admin.")
        if st.button("Sign Out"):
            sign_out()
        st.stop()
    
    if not is_active:
        st.error("Your account has been disabled. Please contact an admin.")
        if st.button("Sign Out"):
            sign_out()
        st.stop()
    
    # Update session state with profile data
    role = str(profile.get("role", "player") or "player")
    is_admin_db = bool(profile.get("is_admin", False))
    
    st.session_state["role"] = role
    st.session_state["is_active"] = is_active
    st.session_state["is_admin"] = is_admin_db or (email in ADMIN_EMAILS) or (role == "admin")
    
    return st.session_state["user"]