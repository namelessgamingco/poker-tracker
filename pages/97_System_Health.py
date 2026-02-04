# pages/97_System_Health.py — Admin system health + Supabase checks

import os
import time
import streamlit as st

from auth import require_auth
from sidebar import render_sidebar
from supabase_client import get_supabase

from db import (
    list_profiles_for_admin,
    get_recent_sessions_for_user,
    get_recent_lines_for_user,
    get_tracks_for_user,
)

st.set_page_config(page_title="System Health", page_icon="🩺", layout="wide")

# ---------- Auth + admin gate ----------

user = require_auth()
render_sidebar()

role = st.session_state.get("role", "player")
is_admin = bool(st.session_state.get("is_admin", False))
is_active = bool(st.session_state.get("is_active", True))
email = st.session_state.get("email", "unknown@example.com")

if not is_admin:
    st.error("System Health is admin-only.")
    st.stop()

# ---------- Page chrome ----------

st.title("🩺 System Health")

top1, top2, top3, top4 = st.columns(4)
with top1:
    st.metric("Current user", email)
with top2:
    st.metric("Role", role)
with top3:
    st.metric("Active", "Yes" if is_active else "No")
with top4:
    st.metric("Admin", "Yes" if is_admin else "No")

st.divider()

# ---------- Supabase connectivity checks ----------

sb_status = "unknown"
sb_error = None
service_role_status = "unknown"
service_role_error = None
auth_status = "unknown"
auth_error = None

# 1) Anon client connectivity (+ simple latency)
sb = None
anon_latency_ms = None
try:
    t0 = time.perf_counter()
    sb = get_supabase()
    _ = (
        sb.table("profiles")
        .select("user_id, email")
        .limit(1)
        .execute()
    )
    t1 = time.perf_counter()
    anon_latency_ms = round((t1 - t0) * 1000, 1)
    sb_status = "OK"
except Exception as e:
    sb_status = "ERROR"
    sb_error = repr(e)

# 2) Auth session health (uses anon client)
if sb is not None and sb_status == "OK":
    try:
        got = sb.auth.get_user()
        if getattr(got, "user", None) is not None:
            auth_status = "OK"
        else:
            auth_status = "WARN"
    except Exception as e:
        auth_status = "ERROR"
        auth_error = repr(e)

# 3) Service-role / admin client check
service_role_key_present = bool(
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or st.secrets.get("SUPABASE_SERVICE_ROLE_KEY", None)
)
try:
    if service_role_key_present:
        rows = list_profiles_for_admin()
        _ = len(rows)
        service_role_status = "OK"
    else:
        service_role_status = "NOT CONFIGURED"
except Exception as e:
    service_role_status = "ERROR"
    service_role_error = repr(e)

c1, c2, c3 = st.columns(3)
with c1:
    st.subheader("Supabase anon client")
    if sb_status == "OK":
        if anon_latency_ms is not None:
            st.success(f"✅ Anon client connected. Query OK (~{anon_latency_ms} ms).")
        else:
            st.success("✅ Anon client connected and basic query succeeded.")
    elif sb_status == "ERROR":
        st.error("❌ Anon client failed.")
        if sb_error:
            st.code(sb_error, language="python")
    else:
        st.warning("Anon client status unknown.")

with c2:
    st.subheader("Auth session")
    if auth_status == "OK":
        st.success("✅ sb.auth.get_user() returned a valid user.")
    elif auth_status == "WARN":
        st.warning("⚠️ sb.auth.get_user() returned no user (session may be missing).")
    elif auth_status == "ERROR":
        st.error("❌ Auth session check failed.")
        if auth_error:
            st.code(auth_error, language="python")
    else:
        st.caption("Auth not checked (anon client unavailable).")

with c3:
    st.subheader("Service-role (admin) client")
    if service_role_status == "OK":
        st.success("✅ Service-role client active; list_profiles_for_admin() succeeded.")
    elif service_role_status == "NOT CONFIGURED":
        st.warning("Service-role key is not configured. Admin features may be limited.")
    else:
        st.error("❌ Service-role client check failed.")
        if not service_role_key_present:
            st.caption("SUPABASE_SERVICE_ROLE_KEY is not set in the environment.")
        if service_role_error:
            st.code(service_role_error, language="python")

st.divider()

# ---------- Env sanity ----------

st.subheader("Environment variables")

env_rows = []
for name in [
    "APP_ENV",
    "SUPABASE_URL_DEV", "SUPABASE_URL_PROD",
    "SUPABASE_ANON_KEY_DEV", "SUPABASE_ANON_KEY_PROD",
    "SUPABASE_SERVICE_ROLE_KEY",
]:
    val = os.getenv(name)
    env_rows.append(
        {
            "name": name,
            "present": bool(val),
            "length": len(val) if val else 0,
        }
    )

st.dataframe(env_rows, use_container_width=True, height=150)

st.divider()

# ---------- Core tables sanity (sample rows) ----------

st.subheader("Core tables sample data")

if sb is None or sb_status != "OK":
    st.warning("Skipping table checks because anon client is not available.")
else:
    core_tables = [
        "profiles",
        "tracks",
        "track_state",
        "week_closures",
        "session_results",
        "line_events",
        "hand_outcomes",
        "track_events",
    ]

    table_rows = []
    for tname in core_tables:
        status = "OK"
        row_count = None
        error = ""
        try:
            res = sb.table(tname).select("*").limit(5).execute()
            data = res.data or []
            row_count = len(data)
        except Exception as e:
            status = "ERROR"
            error = repr(e)

        table_rows.append(
            {
                "table": tname,
                "status": status,
                "sample_rows": row_count,
                "error": error[:140] if error else "",
            }
        )

    st.dataframe(table_rows, use_container_width=True, height=260)

st.divider()

# ---------- Row-count snapshot ----------

st.subheader("Row-count snapshot (key tables)")

count_rows = []
if sb is not None and sb_status == "OK":
    for tname in ["profiles", "tracks", "week_closures", "session_results", "line_events"]:
        total = None
        status = "OK"
        err = ""
        try:
            # COUNT(*) using Supabase exact count
            # Some tables don't have an "id" column (e.g., profiles uses user_id)
            count_col = {
                "profiles": "user_id",
                "tracks": "id",
                "week_closures": "id",
                "session_results": "id",
                "line_events": "id",
            }.get(tname, "id")

            res = (
                sb.table(tname)
                .select(count_col, count="exact")
                .limit(1)
                .execute()
            )
            total = getattr(res, "count", None)
        except Exception as e:
            status = "ERROR"
            err = repr(e)

        count_rows.append(
            {
                "table": tname,
                "status": status,
                "total_rows": total,
                "error": err[:140] if err else "",
            }
        )

    st.dataframe(count_rows, use_container_width=True, height=220)
else:
    st.caption("Row-count snapshot skipped (anon client unavailable).")

st.divider()

# ---------- RLS sanity for current user ----------

st.subheader("RLS sanity checks (current user)")

uid = getattr(user, "id", None) or getattr(user, "user_id", None) or ""
uid = str(uid or "")

c_rls1, c_rls2 = st.columns(2)

if sb is not None and sb_status == "OK" and uid:
    # 1) profiles row for this user_id
    with c_rls1:
        st.markdown("**profiles → current user**")
        try:
            res = (
                sb.table("profiles")
                .select("user_id, email, role, is_active")
                .eq("user_id", uid)
                .execute()
            )
            n = len(res.data or [])
            if n == 1:
                st.success("✅ Exactly one profile row visible for this user_id.")
            elif n == 0:
                st.warning("⚠️ No profile row visible for this user_id (RLS or data issue).")
            else:
                st.error(f"❌ {n} profile rows visible for this user_id (should be 1).")
            st.json(res.data or [])
        except Exception as e:
            st.error("profiles RLS check failed.")
            st.code(repr(e), language="python")

    # 2) session_results visibility for this user
    with c_rls2:
        st.markdown("**session_results → current user**")
        try:
            res = (
                sb.table("session_results")
                .select("id, week_number, session_pl_units, created_at")
                .eq("user_id", uid)
                .limit(3)
                .execute()
            )
            n = len(res.data or [])
            if n >= 0:
                st.success(f"✅ RLS allowed {n} session_results rows for this user (showing up to 3).")
            st.json(res.data or [])
        except Exception as e:
            st.error("session_results RLS check failed.")
            st.code(repr(e), language="python")
else:
    st.caption("RLS checks skipped (no anon client or no current user id).")

st.divider()

# ---------- Current user data sanity ----------

st.subheader("Current user data sanity")

tracks = []
sessions = []
lines = []

cols = st.columns(3)

with cols[0]:
    st.markdown("**Tracks**")
    try:
        tracks = get_tracks_for_user(uid) if uid else []
        st.write(f"Count: **{len(tracks)}**")
    except Exception as e:
        st.error("Error loading tracks")
        st.code(repr(e), language="python")

with cols[1]:
    st.markdown("**Recent sessions (live)**")
    try:
        sessions = get_recent_sessions_for_user(uid, limit=5) if uid else []
        st.write(f"Count: **{len(sessions)}** (showing up to 5)")
    except Exception as e:
        st.error("Error loading sessions")
        st.code(repr(e), language="python")

with cols[2]:
    st.markdown("**Recent closed lines**")
    try:
        lines = get_recent_lines_for_user(uid, limit=5) if uid else []
        st.write(f"Count: **{len(lines)}** (showing up to 5)")
    except Exception as e:
        st.error("Error loading closed lines")
        st.code(repr(e), language="python")

if tracks:
    st.markdown("##### Sample tracks")
    st.dataframe(
        [{"id": t.get("id"), "label": t.get("track_label")} for t in tracks[:5]],
        use_container_width=True,
        height=200,
    )

if sessions:
    st.markdown("##### Sample recent sessions")
    sess_rows = [
        {
            "created_at": s.get("created_at"),
            "track_id": s.get("track_id"),
            "week_number": s.get("week_number"),
            "session_pl_units": s.get("session_pl_units"),
        }
        for s in sessions[:5]
    ]
    st.dataframe(sess_rows, use_container_width=True, height=200)

if lines:
    st.markdown("##### Sample recent closed lines")
    line_rows = [
        {
            "created_at": le.get("created_at"),
            "track_id": le.get("track_id"),
            "week_number": le.get("week_number"),
            "reason": le.get("reason"),
        }
        for le in lines[:5]
    ]
    st.dataframe(line_rows, use_container_width=True, height=200)

st.caption(
    "Use this page to quickly see if Supabase connectivity, service-role access, "
    "RLS, environment variables, or core tables are failing before blaming the tracker."
)