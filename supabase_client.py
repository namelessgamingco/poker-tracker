# supabase_client.py — per-session anon client + cached service-role admin client
from __future__ import annotations

import os
import streamlit as st

from supabase import create_client, Client

# ---- client options import (version-proof) ----
try:
    # newer supabase-py versions
    from supabase.lib.client_options import ClientOptions as _ClientOptions
except Exception:
    _ClientOptions = None  # type: ignore


class SupabaseConfigError(RuntimeError):
    pass


def _get_secret(name: str, default: str | None = None) -> str | None:
    v = os.getenv(name)
    if v:
        return v
    try:
        if name in st.secrets:
            v2 = st.secrets[name]
            if v2:
                return str(v2)
    except Exception:
        pass
    return default


def _env() -> str:
    return (_get_secret("APP_ENV", "prod") or "prod").lower().strip()


def _cfg():
    env = _env()

    if env == "dev":
        url = _get_secret("SUPABASE_URL_DEV")
        anon = _get_secret("SUPABASE_ANON_KEY_DEV")
        svc = _get_secret("SUPABASE_SERVICE_ROLE_KEY_DEV") or _get_secret("SUPABASE_SERVICE_ROLE_KEY")
    else:
        url = _get_secret("SUPABASE_URL_PROD")
        anon = _get_secret("SUPABASE_ANON_KEY_PROD")
        svc = _get_secret("SUPABASE_SERVICE_ROLE_KEY_PROD") or _get_secret("SUPABASE_SERVICE_ROLE_KEY")

    if not url or not anon:
        raise SupabaseConfigError(
            "Missing Supabase credentials. Need SUPABASE_URL_* and SUPABASE_ANON_KEY_* for active APP_ENV."
        )

    return env, url, anon, svc


def _make_client(url: str, key: str) -> Client:
    """
    We are NOT using the SDK's local persistence/refresh.
    Auth is handled by our own cookies + GoTrue refresh flow.
    """
    if _ClientOptions is None:
        # Older supabase-py: no client options available
        return create_client(url, key)

    opts = _ClientOptions(
        persist_session=False,
        auto_refresh_token=False,
    )
    return create_client(url, key, options=opts)  # type: ignore[arg-type]


def get_supabase() -> Client:
    """Per-Streamlit-session ANON client (RLS enforced)."""
    if st.session_state.get("supabase_client_anon") is not None:
        return st.session_state.supabase_client_anon

    _, url, anon, _ = _cfg()
    st.session_state.supabase_client_anon = _make_client(url, anon)
    return st.session_state.supabase_client_anon


def get_supabase_admin() -> Client:
    """Cached SERVICE ROLE client (bypasses RLS)."""
    if st.session_state.get("supabase_client_admin") is not None:
        return st.session_state.supabase_client_admin

    _, url, _, svc = _cfg()
    if not svc:
        raise SupabaseConfigError(
            "Missing service role key. Provide SUPABASE_SERVICE_ROLE_KEY_DEV/PROD (or SUPABASE_SERVICE_ROLE_KEY)."
        )

    st.session_state.supabase_client_admin = _make_client(url, svc)
    return st.session_state.supabase_client_admin

def reset_supabase_client():
    """
    Force creation of a new anon client on next get_supabase() call.
    Call this after login to ensure no stale auth state bleeds between users.
    """
    st.session_state.pop("supabase_client_anon", None)