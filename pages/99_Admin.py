# pages/99_Admin.py — Admin Console (Supabase-backed)

import streamlit as st
st.set_page_config(page_title="Admin Console", page_icon="🔐", layout="wide")

from auth import require_auth
from sidebar import render_sidebar

from datetime import datetime, timezone, timedelta
from math import isfinite
import os
import json

# DB helpers
from db import (
    get_tracks_for_user_admin,
    load_track_state_admin,
    get_profile_by_auth_id,
    list_profiles_for_admin,
    set_profile_role,
    set_profile_active,
    admin_create_user,
    admin_delete_user,
    admin_update_user_email,
    admin_set_user_password,
    delete_profile_by_user_id,
    get_recent_sessions_for_user_admin,
    get_recent_lines_for_user_admin,
    get_recent_closed_weeks_for_user_admin,
)

# Correct import for admin supabase client
from supabase_client import get_supabase_admin

from db_stats import get_player_totals, get_closed_weeks_distribution

from track_manager import TrackManager
from week_manager import WeekManager

# Get admin client (may be None if not configured)
try:
    sb_admin = get_supabase_admin()
except Exception:
    sb_admin = None

# ---------- Auth + admin gate ----------

user = require_auth()
render_sidebar()

def _extract_auth_identity(u):
    auth_id = None
    email = None
    if isinstance(u, dict):
        auth_id = u.get("id") or u.get("user_id") or u.get("sub") or u.get("uid")
        email = u.get("email") or u.get("primary_email")
    else:
        for key in ("id", "user_id", "sub", "uid"):
            if hasattr(u, key):
                auth_id = getattr(u, key)
                break
        for key in ("email", "primary_email"):
            if hasattr(u, key):
                email = getattr(u, key)
                break
    return str(auth_id or ""), str(email or "unknown@example.com")

auth_id, cur_email = _extract_auth_identity(user)

# Pull profile so we know role/is_active
try:
    profile = get_profile_by_auth_id(auth_id) or {}
except Exception as e:
    print(f"[admin] get_profile_by_auth_id error: {e!r}")
    profile = {}

role = profile.get("role", "player") or "player"
is_active = bool(profile.get("is_active", True))

# Fallback: env ADMIN_EMAILS still works for bootstrapping
ADMIN_EMAILS = os.getenv("ADMIN_EMAILS", "")
if ADMIN_EMAILS:
    admin_set = {e.strip().lower() for e in ADMIN_EMAILS.split(",") if e.strip()}
    if cur_email.strip().lower() in admin_set:
        role, is_active = "admin", True

st.session_state["role"] = role
st.session_state["is_active"] = is_active
st.session_state["is_admin"] = bool(is_active and role == "admin")
st.session_state["email"] = cur_email

if not st.session_state["is_admin"]:
    reason = "inactive" if not is_active else f"role = '{role}'"
    st.error(f"You don't have access to the Admin Console ({reason}).")
    st.page_link("app.py", label="← Back to Home", icon="🏠")
    st.stop()

# ---------- Shared helpers ----------

def _safe_float(x, default=0.0):
    try:
        v = float(x)
        return v if isfinite(v) else default
    except Exception:
        return default

def _fmt_u(units: float) -> str:
    u = _safe_float(units)
    sign = "+" if u >= 0 else ""
    return f"{sign}{u:.2f}u"

def _fmt_ts(ts_raw) -> str:
    """Format ISO timestamp → 'YYYY-MM-DD HH:MM' (UTC)."""
    if not ts_raw:
        return "—"
    try:
        dt = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
        dt_utc = dt.astimezone(timezone.utc)
        return dt_utc.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(ts_raw)


def _sec_to_min_str(sec) -> str:
    """Convert seconds → minutes string with 1 decimal."""
    s = _safe_float(sec)
    if s <= 0:
        return "0.0"
    return f"{s / 60.0:.1f}"

def _coerce_counts(dist: dict) -> tuple[dict, int]:
    """
    Supports multiple shapes:
      A) {"counts": {...}, "total_closed": n}
      B) {"counts": [{"bucket":"primary_cap","count":3}, ...], "total_closed": n}
      C) {"counts": "<json string>", "total_closed": n}
      D) {"primary_cap": 3, "optimizer_cap": 2, ..., "total_closed": n}  (flat)
    """
    if not isinstance(dist, dict):
        return ({}, 0)

    total_closed = int(_safe_float(dist.get("total_closed", 0) or 0))

    counts_raw = dist.get("counts", None)

    # D) flat shape (no "counts" key)
    if counts_raw is None:
        # treat all non-total_closed keys as counts
        flat = {k: v for k, v in dist.items() if k != "total_closed"}
        if flat:
            return (flat, total_closed)

    # C) counts is a JSON string
    if isinstance(counts_raw, str):
        try:
            counts_raw = json.loads(counts_raw)
        except Exception:
            return ({}, total_closed)

    # A) counts is already a dict
    if isinstance(counts_raw, dict):
        return (counts_raw, total_closed)

    # B) counts is a list of objects
    if isinstance(counts_raw, list):
        out = {}
        for item in counts_raw:
            if not isinstance(item, dict):
                continue
            k = str(item.get("bucket") or item.get("key") or "")
            v = item.get("count") if "count" in item else item.get("value")
            if k:
                out[k] = v
        return (out, total_closed)

    return ({}, total_closed)

if "tm" not in st.session_state:
    st.session_state.tm = TrackManager(unit_value=float(st.session_state.get("unit_value", 1.0)))
tm: TrackManager = st.session_state.tm

# ---------- Page chrome ----------

st.title("🔐 Admin Console")

top1, top2, top3 = st.columns(3)
with top1:
    st.metric("Admin User", cur_email)
with top2:
    st.metric("Role", role)
with top3:
    st.metric("Active", "Yes" if is_active else "No")

st.divider()

tabs = st.tabs(["👤 Users & Roles", "📂 Player Detail"])

# ============================
# TAB 1 — Users & Roles
# ============================
with tabs[0]:
    st.subheader("Users & Roles")

    # ----- Create new user -----
    with st.expander("➕ Create new user", expanded=False):
        new_email = st.text_input("Email", key="admin_new_email")
        new_pw = st.text_input("Password", type="password", key="admin_new_pw")
        new_role = st.selectbox(
            "Role",
            ["trial_player", "player", "admin"],
            index=1,
            key="admin_new_role",
        )
        new_active = st.checkbox("Active", value=True, key="admin_new_active")

        if st.button("Create user", type="primary", key="admin_create_user_btn"):
            if not new_email.strip() or not new_pw.strip():
                st.error("Email and password are required.")
            else:
                try:
                    created = admin_create_user(
                        email=new_email,
                        password=new_pw,   # not optional anymore
                        role=new_role,
                        is_active=new_active,
                    )
                    st.success(f"Created user {created.get('email')}.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to create user: {e!r}")

    # ----- Existing profiles & editing -----
    profiles = list_profiles_for_admin()

    if not profiles:
        st.info(
            "No profiles found yet. If you already have users in Supabase, double-check "
            "that SUPABASE_SERVICE_ROLE_KEY is configured for this app. "
            "New users created above will appear here once they're saved."
        )
        st.caption(
            "Auth users are still managed here via the service-role client. "
            "Schema changes and deep DB admin still live in the Supabase console."
        )
    else:
        with st.expander("🛠 Edit existing user", expanded=False):
            # 1) Build labels + lookup map
            labels: list[str] = []
            label_to_profile: dict[str, dict] = {}

            for p in profiles:
                email = (p.get("email") or "—").strip()
                user_id = str(p.get("user_id") or "")
                short = user_id[:8] if user_id else "--------"

                label = f"{email} · {short}"
                labels.append(label)
                label_to_profile[label] = p

            # 2) Select user (ONE time, outside the loop)
            sel_label = st.selectbox(
                "Select user",
                options=labels,
                key="admin_select_user",
            )

            selected = label_to_profile.get(sel_label, {}) or {}

            # 3) Canonical id used everywhere
            sel_user_id = str(selected.get("user_id") or "")
            if not sel_user_id:
                st.error("Selected profile has no user_id.")
                st.stop()

            # Editable fields
            email_val = st.text_input("Email", value=selected.get("email", ""), key="admin_edit_email")

            col_a, col_b, col_c = st.columns(3)
            with col_a:
                cur_role = selected.get("role", "player") or "player"
                role_choices = ["trial_player", "player", "admin"]
                if cur_role not in role_choices:
                    role_choices.insert(0, cur_role)
                new_role = st.selectbox("Role", role_choices, index=role_choices.index(cur_role))
            with col_b:
                cur_active = bool(selected.get("is_active", True))
                new_active = st.checkbox("Active", value=cur_active, key="admin_edit_active")
            with col_c:
                role_since_raw = selected.get("role_assigned_at") or selected.get("created_at")
                role_since_str = "—"
                role_days_str = "—"
                if role_since_raw:
                    try:
                        ts = datetime.fromisoformat(str(role_since_raw).replace("Z", "+00:00"))
                        # Use timezone-aware UTC datetimes instead of deprecated utcnow()
                        now_utc = datetime.now(timezone.utc)
                        ts_utc = ts.astimezone(timezone.utc)
                        days = (now_utc - ts_utc).days

                        role_since_str = ts_utc.strftime("%Y-%m-%d")
                        role_days_str = f"{days} days"
                    except Exception:
                        role_since_str = str(role_since_raw)

                st.markdown(f"**Role since:** {role_since_str}")
                st.markdown(f"**In role:** {role_days_str}")

            temp_pw = st.text_input(
                "Set new TEMP password (optional)",
                type="password",
                key="admin_edit_temp_pw",
                help="If set, this will overwrite their password. Give it to them directly."
            )

            action_cols = st.columns(2)

            with action_cols[0]:
                if st.button("Save changes", type="primary", key="admin_save_changes"):
                    if not sel_user_id:
                        st.error("Selected profile has no user_id.")
                        st.stop()

                    something_changed = False

                    # 1) Email change (AUTH)
                    try:
                        old_email = (selected.get("email") or "").strip().lower()
                        new_email_clean = (email_val or "").strip().lower()
                        if new_email_clean and new_email_clean != old_email:
                            admin_update_user_email(sel_user_id, new_email_clean)  # auth.users update
                            something_changed = True
                    except Exception as e:
                        st.error(f"Email update failed: {e!r}")

                    # 2) Role / active flags (profiles table)
                    try:
                        if new_role != cur_role:
                            set_profile_role(sel_user_id, new_role)
                            something_changed = True
                        if new_active != cur_active:
                            set_profile_active(sel_user_id, new_active)
                            something_changed = True
                    except Exception as e:
                        st.error(f"Role/active update failed: {e!r}")

                    # 3) Temp password (AUTH)
                    try:
                        if temp_pw:
                            admin_set_user_password(sel_user_id, temp_pw)  # auth.users update
                            something_changed = True
                    except Exception as e:
                        st.error(f"Password update failed: {e!r}")

                    if something_changed:
                        st.success("User updated.")
                        st.rerun()
                    else:
                        st.info("No changes to save.")

            with action_cols[1]:
                if st.button("Delete user", type="secondary", key="admin_delete_user"):
                    if not sel_user_id:
                        st.error("Selected profile has no user_id.")
                        st.stop()

                    try:
                        # Delete auth user
                        admin_delete_user(sel_user_id)

                        # Also delete profile row (prevents ghost rows in admin lists)
                        # You need a DB helper for this if you don't already have one:
                        delete_profile_by_user_id(sel_user_id)

                        st.success("User deleted.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to delete user: {e!r}")

        # ----- All profiles table -----
        st.markdown("#### All profiles")

        table = []
        now_utc = datetime.now(timezone.utc)

        for p in profiles:
            # role_since: prefer role_assigned_at, fall back to created_at
            role_since_raw = p.get("role_assigned_at") or p.get("created_at")
            role_since_str = "—"
            days_in_role = None

            if role_since_raw:
                try:
                    ts = datetime.fromisoformat(str(role_since_raw).replace("Z", "+00:00"))
                    ts_utc = ts.astimezone(timezone.utc)
                    role_since_str = ts_utc.strftime("%Y-%m-%d")
                    days_in_role = (now_utc - ts_utc).days
                except Exception:
                    role_since_str = str(role_since_raw)

            created_raw = p.get("created_at")
            created_str = "—"
            if created_raw:
                try:
                    cts = datetime.fromisoformat(str(created_raw).replace("Z", "+00:00"))
                    created_str = cts.astimezone(timezone.utc).strftime("%Y-%m-%d")
                except Exception:
                    created_str = str(created_raw)

            table.append({
                "email": p.get("email"),
                "role": p.get("role", "player"),
                "is_active": p.get("is_active", True),
                "role_since": role_since_str,
                "days_in_role": days_in_role,
                "created_at": created_str,
                "user_id": p.get("user_id"),
            })

        st.dataframe(table, use_container_width=True, height=360)

        st.caption(
            "Auth users are now managed here via the service-role client. "
            "Schema changes and deep DB admin still live in the Supabase console."
        )

# ============================
# TAB 2 — Player Detail
# ============================
with tabs[1]:
    st.subheader("Player Detail")

    profiles = list_profiles_for_admin()
    if not profiles:
        st.info("No profiles; can't show player stats.")
    else:
        email_to_profile = {p.get("email", ""): p for p in profiles}
        emails_sorted = sorted(email_to_profile.keys())

        sel_email = st.selectbox("Select player", options=emails_sorted, key="admin_player_detail_email")
        sel_profile = email_to_profile.get(sel_email, {}) or {}

        # ✅ Single canonical id everywhere: profiles.user_id == auth.users.id
        sel_user_id = str(sel_profile.get("user_id") or "")
        if not sel_user_id:
            st.warning("Selected profile has no user_id.")
            st.stop()

        # ⚠️ Admin client guard (RLS safety)
        if not sb_admin:
            st.error(
                "Admin client not configured (SUPABASE_SERVICE_ROLE_KEY missing). "
                "Player totals and distributions may appear as 0 due to RLS."
            )

        # ---------- Calendar P/L ----------
        all_u = month_u = week_u = ev_diff_u = 0.0

        try:
            totals = get_player_totals(user_id=sel_user_id, sb=sb_admin) or {}

            all_u = _safe_float(totals.get("all_time_units", 0.0))
            month_u = _safe_float(totals.get("month_units", 0.0))
            week_u = _safe_float(totals.get("week_units", 0.0))
            ev_diff_u = _safe_float(totals.get("ev_diff_units", 0.0))

        except Exception as e:
            st.error(f"get_player_totals error: {e!r}")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("All-time", _fmt_u(all_u))
        c2.metric("This month", _fmt_u(month_u))
        c3.metric("This week", _fmt_u(week_u))
        c4.metric("EV diff (all-time)", _fmt_u(ev_diff_u))

        st.caption(
            "Calendar ranges from Supabase: week = Monday–Sunday (UTC). "
            "These ignore testing_mode and sim data (same filters as Overview)."
        )

        with st.expander("Closed weeks distribution"):
            try:
                dist = get_closed_weeks_distribution(user_id=sel_user_id, sb=sb_admin) or {}
                counts, total_closed = _coerce_counts(dist)

                rows = [
                    {"Bucket": "+400", "Count": int(_safe_float(counts.get("primary_cap", 0)))},
                    {"Bucket": "+300", "Count": int(_safe_float(counts.get("optimizer_cap", 0)))},
                    {"Bucket": "+160", "Count": int(_safe_float(counts.get("small_green", 0)))},
                    {"Bucket": "-85",  "Count": int(_safe_float(counts.get("red_stabilizer", 0)))},
                    {"Bucket": "-400", "Count": int(_safe_float(counts.get("weekly_guard", 0)))},
                    {"Bucket": "other","Count": int(_safe_float(counts.get("other", 0)))},
                ]

                st.write(f"Total closed weeks: **{total_closed}**")
                st.dataframe(rows, use_container_width=True, height=240)

            except Exception as e:
                st.info(f"Could not load closed-week distribution: {e!r}")

        # ---------- Tracks snapshot (per-track P/L + tone) ----------
        st.markdown("### Tracks snapshot")

        try:
            db_tracks = get_tracks_for_user_admin(sel_user_id)
        except Exception as e:
            st.error(f"get_tracks_for_user error: {e!r}")
            db_tracks = []

        track_label_by_id = {}
        rows = []

        if not db_tracks:
            st.info("No tracks for this user yet.")
        else:
            for idx, t in enumerate(db_tracks, start=1):
                tid = str(t.get("id"))
                label = (
                    t.get("track_label")
                    or t.get("name")
                    or f"Track {idx}"
                )
                track_label_by_id[tid] = label

                state = {}
                try:
                    state = load_track_state_admin(sel_user_id, tid)
                except Exception as e:
                    print(f"[admin] load_track_state error for user={sel_user_id} track={tid}: {e!r}")
                    state = {}

                wk_state = state.get("week") or {}
                eng_state = state.get("engine") or {}

                # Week P/L should come from week.week_pl (your JSON shows this)
                week_pl = _safe_float(wk_state.get("week_pl", 0.0))

                # Session/line P/L come from engine.*
                session_pl = _safe_float(eng_state.get("session_pl_units", 0.0))
                line_pl = _safe_float(eng_state.get("line_pl_units", 0.0))

                # Optional: if you ever want the engine's running week total
                engine_week_pl = _safe_float(eng_state.get("week_pl_units", 0.0))

                tone = (
                    wk_state.get("tone")
                    or wk_state.get("tone_name")
                    or wk_state.get("current_tone")
                    or "neutral"
                )
                tone = str(tone).lower()

                rows.append({
                    "track_id": tid,
                    "label": label,
                    "tone": tone,
                    "week_pl_u": week_pl,
                    "session_pl_u": session_pl,
                    "line_pl_u": line_pl,
                })

            st.dataframe(rows, use_container_width=True, height=260)
            st.caption(
                "Week P/L comes from persisted WeekManager state; "
                "session/line P/L come from the last saved engine state for that track."
            )

        # ---------- Recent closed weeks ----------
        st.markdown("### Recent closed weeks")

        closed_weeks = get_recent_closed_weeks_for_user_admin(sel_user_id, limit=50)
        if not closed_weeks:
            st.info("No closed weeks recorded yet for this player.")
        else:
            week_rows = []
            for w in closed_weeks:
                tid = str(w.get("track_id") or "")
                raw_ts = w.get("ts") or w.get("created_at")   # 👈 prefer ts, fallback to created_at
                week_rows.append(
                    {
                        "week_number": w.get("week_number"),
                        "track": track_label_by_id.get(tid, tid[:8]) if tid else "—",
                        "week_pl_u": _safe_float(w.get("week_pl_units", 0.0)),
                        "bucket": w.get("outcome_bucket"),
                        "is_test": bool(w.get("is_test", False)),
                        "closed_at": _fmt_ts(raw_ts),         # 👈 same formatter as sessions
                    }
                )
            st.dataframe(week_rows, use_container_width=True, height=260)

        # ---------- Recent sessions ----------
        st.markdown("### Recent sessions (live)")

        sessions = get_recent_sessions_for_user_admin(sel_user_id, limit=50)
        if not sessions:
            st.info("No live sessions recorded yet for this player.")
        else:
            sess_rows = []
            for s in sessions:
                tid = str(s.get("track_id") or "")
                sess_rows.append(
                    {
                        "created_at": _fmt_ts(s.get("created_at")),
                        "track": track_label_by_id.get(tid, tid[:8]),
                        "week_number": s.get("week_number"),
                        "session_pl_u": _safe_float(s.get("session_pl_units", 0.0)),
                        "end_reason": s.get("end_reason"),
                        "duration_min": _sec_to_min_str(s.get("duration_sec", 0.0)),
                    }
                )
            st.dataframe(sess_rows, use_container_width=True, height=260)

        # ---------- Recent closed lines ----------
        st.markdown("### Recent closed lines")

        lines = get_recent_lines_for_user_admin(sel_user_id, limit=100)
        if not lines:
            st.info("No closed lines logged yet for this player.")
        else:
            line_rows = []
            for le in lines:
                tid = str(le.get("track_id") or "")
                line_rows.append(
                    {
                        "created_at": _fmt_ts(le.get("created_at")),
                        "track": track_label_by_id.get(tid, tid[:8]),
                        "week_number": le.get("week_number"),
                        "reason": le.get("reason"),
                        "duration_min": _sec_to_min_str(le.get("line_duration_sec", 0.0)),
                    }
                )
            st.dataframe(line_rows, use_container_width=True, height=260)