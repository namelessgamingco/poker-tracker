# supabase_client.py — Supabase Connection Client
# Handles both regular (anon) and admin (service role) connections
# Auto-refreshes clients every 10 minutes to prevent stale connections

from __future__ import annotations

import os
import time as _time
from typing import Optional

import streamlit as st
from supabase import create_client, Client


# ---------- Secret/Env Helpers ----------

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


def _get_app_env() -> str:
    """Get current environment (dev or prod)."""
    return str(_get_secret("APP_ENV", "prod")).lower().strip()


# ---------- Connection URLs and Keys ----------

def _get_supabase_url() -> str:
    """Get Supabase URL based on environment."""
    env = _get_app_env()
    if env == "dev":
        return str(_get_secret("SUPABASE_URL_DEV") or "")
    return str(_get_secret("SUPABASE_URL_PROD") or "")


def _get_supabase_anon_key() -> str:
    """Get Supabase anon key based on environment."""
    env = _get_app_env()
    if env == "dev":
        return str(_get_secret("SUPABASE_ANON_KEY_DEV") or "")
    return str(_get_secret("SUPABASE_ANON_KEY_PROD") or "")


def _get_supabase_service_role_key() -> str:
    """Get Supabase service role key based on environment."""
    env = _get_app_env()
    if env == "dev":
        return str(_get_secret("SUPABASE_SERVICE_ROLE_KEY_DEV") or "")
    return str(_get_secret("SUPABASE_SERVICE_ROLE_KEY_PROD") or "")


# ---------- Client Instances ----------

# Module-level cache for clients + creation timestamps
_supabase_client: Optional[Client] = None
_supabase_admin_client: Optional[Client] = None
_supabase_client_created_at: float = 0
_supabase_admin_client_created_at: float = 0

_CLIENT_MAX_AGE_SECONDS = 180  # 3 minutes — Railway/Supabase connections go stale fast


def get_supabase() -> Client:
    """
    Get the regular Supabase client (uses anon key).
    
    This client respects Row Level Security (RLS).
    Use for normal user operations.
    Auto-recreates every 10 minutes to prevent stale connections.
    """
    global _supabase_client, _supabase_client_created_at
    
    now = _time.time()
    if _supabase_client is not None and (now - _supabase_client_created_at) < _CLIENT_MAX_AGE_SECONDS:
        return _supabase_client
    
    if _supabase_client is not None:
        print("[supabase_client] anon client expired, recreating...")
    
    url = _get_supabase_url()
    key = _get_supabase_anon_key()
    
    if not url or not key:
        raise RuntimeError(
            "Supabase not configured. "
            "Set SUPABASE_URL_PROD/DEV and SUPABASE_ANON_KEY_PROD/DEV in secrets."
        )
    
    _supabase_client = create_client(url, key)
    _supabase_client_created_at = now
    return _supabase_client


def get_supabase_admin() -> Client:
    """
    Get the admin Supabase client (uses service role key).
    
    This client BYPASSES Row Level Security (RLS).
    Use only for admin operations like:
    - Creating users
    - Managing profiles across all users
    - Webhook handlers
    Auto-recreates every 10 minutes to prevent stale connections.
    """
    global _supabase_admin_client, _supabase_admin_client_created_at
    
    now = _time.time()
    if _supabase_admin_client is not None and (now - _supabase_admin_client_created_at) < _CLIENT_MAX_AGE_SECONDS:
        return _supabase_admin_client
    
    if _supabase_admin_client is not None:
        print("[supabase_client] admin client expired, recreating...")
    
    url = _get_supabase_url()
    key = _get_supabase_service_role_key()
    
    if not url or not key:
        raise RuntimeError(
            "Supabase admin not configured. "
            "Set SUPABASE_SERVICE_ROLE_KEY_PROD/DEV in secrets."
        )
    
    _supabase_admin_client = create_client(url, key)
    _supabase_admin_client_created_at = now
    return _supabase_admin_client


def get_supabase_admin_fresh() -> Client:
    """Force a fresh admin client — call this after connection errors."""
    global _supabase_admin_client, _supabase_admin_client_created_at
    _supabase_admin_client = None
    _supabase_admin_client_created_at = 0
    import time
    time.sleep(0.5)  # Brief pause to let connection fully establish
    return get_supabase_admin()


def reset_supabase_client():
    """
    Reset the cached Supabase client.
    
    Call this when:
    - User logs out (clear session binding)
    - Switching environments
    - After auth errors
    """
    global _supabase_client, _supabase_client_created_at
    _supabase_client = None
    _supabase_client_created_at = 0


def reset_supabase_admin_client():
    """Reset the cached admin client."""
    global _supabase_admin_client, _supabase_admin_client_created_at
    _supabase_admin_client = None
    _supabase_admin_client_created_at = 0


# ---------- Connection Test ----------

def test_connection() -> dict:
    """
    Test the Supabase connection.
    
    Returns dict with connection status and details.
    Useful for System Health page.
    """
    result = {
        "env": _get_app_env(),
        "url_configured": bool(_get_supabase_url()),
        "anon_key_configured": bool(_get_supabase_anon_key()),
        "service_role_configured": bool(_get_supabase_service_role_key()),
        "connection_ok": False,
        "error": None,
    }
    
    try:
        client = get_supabase()
        # Try a simple query to verify connection
        response = client.table("poker_stakes_reference").select("stakes_label").limit(1).execute()
        result["connection_ok"] = True
        result["test_query"] = "poker_stakes_reference OK"
    except Exception as e:
        result["error"] = str(e)
    
    return result