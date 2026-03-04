# pages/99_Admin.py — Admin Console for Poker Decision App
# =============================================================================
#
# COMPLETE CONTROL CENTER FOR $299/MONTH SUBSCRIPTION MANAGEMENT
#
# TABS:
# 1. Dashboard - Revenue metrics, user counts, quick stats
# 2. User Management - Create/Edit/Delete users
# 3. Subscriptions - Subscription control, trials, overrides, ban
# 4. Player Detail - Deep dive into individual user data
#
# =============================================================================

import streamlit as st
st.set_page_config(page_title="Admin Console", page_icon="🔐", layout="wide")

from auth import require_auth
from sidebar import render_sidebar

from datetime import datetime, timezone, timedelta
from math import isfinite
import os

# DB helpers
from db import (
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
    get_player_stats,
    get_user_settings,
    admin_grant_free_access,
    admin_revoke_free_access,
    admin_set_subscription_status,
    admin_get_subscription_details,
    admin_extend_trial,
    admin_resend_payment_link,
    admin_ban_user,
    admin_unban_user,
)

from supabase_client import get_supabase_admin

# Get admin client
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

# Pull profile for role check
try:
    profile = get_profile_by_auth_id(auth_id) or {}
except Exception as e:
    print(f"[admin] get_profile_by_auth_id error: {e!r}")
    profile = {}

role = profile.get("role", "player") or "player"
is_active = bool(profile.get("is_active", True))

# Fallback: env ADMIN_EMAILS for bootstrapping
ADMIN_EMAILS = os.getenv("ADMIN_EMAILS", "")
if ADMIN_EMAILS:
    admin_set = {e.strip().lower() for e in ADMIN_EMAILS.split(",") if e.strip()}
    if cur_email.strip().lower() in admin_set:
        role, is_active = "admin", True

st.session_state["role"] = role
st.session_state["is_active"] = is_active
st.session_state["is_admin"] = bool(is_active and role == "admin")
st.session_state["user_email"] = cur_email

if not st.session_state["is_admin"]:
    reason = "inactive" if not is_active else f"role = '{role}'"
    st.error(f"You don't have access to the Admin Console ({reason}).")
    st.page_link("app.py", label="← Back to Home", icon="🏠")
    st.stop()


# =============================================================================
# CSS — Premium dark theme matching the rest of the app
# =============================================================================

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700;800&family=Inter:wght@400;500;600;700;800&display=swap');

[data-testid="stAppViewContainer"] { background: #0A0A12; }
.block-container { max-width: 1400px; }

/* Header */
.admin-header {
    font-family: 'JetBrains Mono', monospace;
    font-size: 24px;
    font-weight: 800;
    letter-spacing: 0.06em;
    color: #E0E0E0;
    margin-bottom: 4px;
}
.admin-sub {
    font-family: 'Inter', sans-serif;
    font-size: 13px;
    color: rgba(255,255,255,0.3);
}

/* Section headers */
.section-title {
    font-family: 'JetBrains Mono', monospace;
    font-size: 14px;
    font-weight: 700;
    color: rgba(255,255,255,0.5);
    letter-spacing: 0.06em;
    text-transform: uppercase;
    margin: 24px 0 12px 0;
}

/* Stat cards */
.stat-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin-bottom: 20px;
}
.stat-card {
    background: linear-gradient(135deg, #0F0F1A 0%, #151520 100%);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 12px;
    padding: 16px;
}
.stat-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 22px;
    font-weight: 700;
    color: #E0E0E0;
}
.stat-label {
    font-size: 11px;
    color: rgba(255,255,255,0.3);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-top: 4px;
}

/* Action cards */
.action-card {
    background: linear-gradient(135deg, #0F0F1A 0%, #151520 100%);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 12px;
    padding: 16px 18px;
    margin-bottom: 8px;
}
.action-card-title {
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px;
    font-weight: 700;
    color: #E0E0E0;
    margin-bottom: 4px;
}
.action-card-desc {
    font-size: 12px;
    color: rgba(255,255,255,0.35);
    line-height: 1.5;
}

/* Alert cards */
.alert-card {
    border-radius: 10px;
    padding: 14px 16px;
    margin-bottom: 8px;
}
.alert-warn {
    background: rgba(255,179,0,0.06);
    border: 1px solid rgba(255,179,0,0.15);
}
.alert-danger {
    background: rgba(255,82,82,0.06);
    border: 1px solid rgba(255,82,82,0.15);
}
.alert-success {
    background: rgba(105,240,174,0.06);
    border: 1px solid rgba(105,240,174,0.15);
}
.alert-text {
    font-size: 13px;
    color: rgba(255,255,255,0.5);
}

/* Info row */
.info-row {
    display: flex;
    gap: 24px;
    margin-bottom: 16px;
    flex-wrap: wrap;
}
.info-item {
    min-width: 120px;
}
.info-label {
    font-size: 10px;
    color: rgba(255,255,255,0.25);
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.info-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 15px;
    font-weight: 600;
    color: #E0E0E0;
    margin-top: 2px;
}
</style>
""", unsafe_allow_html=True)


# =============================================================================
# HELPERS
# =============================================================================

def _safe_float(x, default=0.0):
    try:
        v = float(x)
        return v if isfinite(v) else default
    except Exception:
        return default

def _fmt_currency(amount: float) -> str:
    return f"${amount:,.2f}"

def _fmt_ts(ts_raw) -> str:
    if not ts_raw:
        return "—"
    try:
        dt = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
        dt_utc = dt.astimezone(timezone.utc)
        return dt_utc.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(ts_raw)

def _fmt_date(ts_raw) -> str:
    if not ts_raw:
        return "—"
    try:
        dt = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return str(ts_raw)

def _days_until(ts_raw) -> int:
    if not ts_raw:
        return 0
    try:
        dt = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
        dt_utc = dt.astimezone(timezone.utc)
        now_utc = datetime.now(timezone.utc)
        delta = dt_utc - now_utc
        return max(0, delta.days)
    except Exception:
        return 0

def _days_ago(ts_raw) -> int:
    if not ts_raw:
        return 999
    try:
        dt = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
        dt_utc = dt.astimezone(timezone.utc)
        now_utc = datetime.now(timezone.utc)
        delta = now_utc - dt_utc
        return max(0, delta.days)
    except Exception:
        return 999

def _status_emoji(status: str) -> str:
    return {
        "active": "🟢", "trial": "🔵", "grace_period": "🟡",
        "pending": "⚪", "overdue": "🟠", "cancelled": "🔴",
        "expired": "⚫", "banned": "⛔",
    }.get(status, "⚪")


# =============================================================================
# PAGE HEADER
# =============================================================================

st.markdown(f"""
<div style="margin-bottom: 8px;">
    <div class="admin-header">🔐 ADMIN CONSOLE</div>
    <div class="admin-sub">{cur_email}  ·  {os.getenv("APP_ENV", "unknown").upper()} environment</div>
</div>
""", unsafe_allow_html=True)

st.markdown('<div style="height:1px;background:rgba(255,255,255,0.06);margin:8px 0 20px 0"></div>', unsafe_allow_html=True)


# =============================================================================
# LOAD ALL PROFILES ONCE
# =============================================================================

all_profiles = list_profiles_for_admin()


# =============================================================================
# TABS
# =============================================================================

tabs = st.tabs(["📊 Dashboard", "👤 Users", "💳 Subscriptions", "🔍 Player Detail"])


# =============================================================================
# TAB 1: DASHBOARD
# =============================================================================

with tabs[0]:

    total_users = len(all_profiles)
    active_subs = [p for p in all_profiles if p.get("subscription_status") == "active" and not p.get("admin_override_active")]
    trial_users = [p for p in all_profiles if p.get("subscription_status") == "trial"]
    pending_users = [p for p in all_profiles if p.get("subscription_status") == "pending"]
    cancelled_users = [p for p in all_profiles if p.get("subscription_status") in ("cancelled", "expired")]
    override_users = [p for p in all_profiles if p.get("admin_override_active")]
    banned_users = [p for p in all_profiles if p.get("subscription_status") == "banned"]

    mrr = len(active_subs) * 299

    # Lifetime revenue calculation
    total_lifetime_revenue = 0
    avg_customer_months = 0
    paying_count = 0
    for p in all_profiles:
        sub_started = p.get("subscription_started_at")
        if sub_started and p.get("subscription_status") in ("active", "cancelled", "expired", "overdue"):
            try:
                start_dt = datetime.fromisoformat(str(sub_started).replace("Z", "+00:00"))
                months = max(1, round((datetime.now(timezone.utc) - start_dt).days / 30))
                total_lifetime_revenue += months * 299
                avg_customer_months += months
                paying_count += 1
            except Exception:
                pass
    avg_customer_months = (avg_customer_months / paying_count) if paying_count > 0 else 0

    # Conversion rate: users who went from trial/pending to active
    ever_paid = len([p for p in all_profiles if p.get("subscription_status") in ("active", "cancelled", "expired", "overdue") or p.get("subscription_started_at")])
    non_admin_users = len([p for p in all_profiles if p.get("role") != "admin"])
    conversion_rate = (ever_paid / non_admin_users * 100) if non_admin_users > 0 else 0

    trials_expiring_soon = []
    for p in trial_users:
        trial_ends = p.get("trial_ends_at")
        if trial_ends and _days_until(trial_ends) <= 3:
            trials_expiring_soon.append(p)

    # Revenue stats
    rev_color = "#69F0AE" if total_lifetime_revenue > 0 else "rgba(255,255,255,0.2)"
    st.markdown(f"""
    <div class="stat-grid">
        <div class="stat-card">
            <div class="stat-value" style="color: #69F0AE;">{_fmt_currency(mrr)}</div>
            <div class="stat-label">Monthly Revenue (MRR)</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" style="color: {rev_color};">{_fmt_currency(total_lifetime_revenue)}</div>
            <div class="stat-label">Lifetime Revenue</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{len(active_subs)}</div>
            <div class="stat-label">Active Subscribers</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{total_users}</div>
            <div class="stat-label">Total Users</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="stat-grid">
        <div class="stat-card">
            <div class="stat-value" style="color: #4BA3FF;">{len(trial_users)}</div>
            <div class="stat-label">Trial Users</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{len(pending_users)}</div>
            <div class="stat-label">Pending Signup</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{avg_customer_months:.1f}</div>
            <div class="stat-label">Avg Customer Tenure (mo)</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" style="color: {'#FFB300' if trials_expiring_soon else 'rgba(255,255,255,0.2)'};">{len(trials_expiring_soon)}</div>
            <div class="stat-label">Trials Expiring ≤3 Days</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Trials expiring alert
    if trials_expiring_soon:
        st.markdown('<div class="section-title">⚠️ Trials Expiring Soon</div>', unsafe_allow_html=True)
        expiring_data = []
        for p in trials_expiring_soon:
            expiring_data.append({
                "Email": p.get("email"),
                "Trial Ends": _fmt_date(p.get("trial_ends_at")),
                "Days Left": _days_until(p.get("trial_ends_at")),
            })
        st.dataframe(expiring_data, use_container_width=True, hide_index=True)

    # Status breakdown
    st.markdown('<div class="section-title">Status Breakdown</div>', unsafe_allow_html=True)

    status_counts = {}
    for p in all_profiles:
        if p.get("admin_override_active"):
            s = "free access"
        else:
            s = p.get("subscription_status", "unknown") or "unknown"
        status_counts[s] = status_counts.get(s, 0) + 1

    status_data = []
    for s, count in sorted(status_counts.items(), key=lambda x: -x[1]):
        status_data.append({
            "Status": f"{'🎁' if s == 'free access' else _status_emoji(s)} {s}",
            "Count": count,
            "% of Total": f"{count/total_users*100:.1f}%" if total_users > 0 else "0%",
        })

    st.dataframe(status_data, use_container_width=True, hide_index=True, height=200)

    # Recent activity
    st.markdown('<div class="section-title">Recent Activity</div>', unsafe_allow_html=True)

    recent_activity = []
    for p in all_profiles:
        last_active = p.get("updated_at") or p.get("created_at")
        recent_activity.append({
            "email": p.get("email"),
            "status": p.get("subscription_status"),
            "last_active": last_active,
            "days_ago": _days_ago(last_active),
        })

    recent_activity.sort(key=lambda x: x["days_ago"])

    activity_display = []
    for a in recent_activity[:10]:
        # Find the profile to check override
        prof = next((p for p in all_profiles if p.get("email") == a["email"]), {})
        if prof.get("admin_override_active"):
            display_status = "🎁 free access"
        else:
            display_status = f"{_status_emoji(a['status'])} {a['status']}"
        activity_display.append({
            "Email": a["email"],
            "Status": display_status,
            "Last Active": _fmt_date(a["last_active"]),
            "Days Ago": a["days_ago"],
        })

    st.dataframe(activity_display, use_container_width=True, hide_index=True, height=300)


# =============================================================================
# TAB 2: USER MANAGEMENT
# =============================================================================

with tabs[1]:

    # ── Create New User ──
    st.markdown('<div class="section-title">Create New User</div>', unsafe_allow_html=True)
    st.caption("Create a new player account. They'll receive a 7-day trial by default, or you can require immediate payment.")

    with st.expander("➕ New User", expanded=False):
        col1, col2 = st.columns(2)

        with col1:
            new_email = st.text_input("Email", key="admin_new_email")
            new_pw = st.text_input("Password", type="password", key="admin_new_pw")

        with col2:
            new_role = st.selectbox("Role", ["player", "admin"], index=0, key="admin_new_role")
            start_trial = st.checkbox("Start 7-day trial", value=True, key="admin_start_trial")

        if st.button("Create User", type="primary", key="admin_create_user_btn"):
            if not new_email.strip() or not new_pw.strip():
                st.error("Email and password are required.")
            else:
                try:
                    created = admin_create_user(
                        email=new_email,
                        password=new_pw,
                        role=new_role,
                        is_active=start_trial,
                        start_trial=start_trial,
                    )
                    st.success(f"✅ Created user: {created.get('email')}")
                    if created.get("payment_link_url"):
                        st.code(created.get("payment_link_url"), language=None)
                        st.caption("Send this payment link to the user.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to create user: {e!r}")

    # ── Edit Existing User ──
    if all_profiles:
        st.markdown('<div class="section-title">Edit User</div>', unsafe_allow_html=True)
        st.caption("Change email, role, password, or active status for an existing user.")

        with st.expander("🛠 Edit User", expanded=False):
            labels = []
            label_to_profile = {}

            for p in all_profiles:
                email = (p.get("email") or "—").strip()
                status = p.get("subscription_status", "unknown")
                label = f"{email} ({status})"
                labels.append(label)
                label_to_profile[label] = p

            sel_label = st.selectbox("Select user", options=labels, key="admin_select_user")
            selected = label_to_profile.get(sel_label, {})

            sel_user_id = str(selected.get("user_id") or "")
            if not sel_user_id:
                st.error("Selected profile has no user_id.")
            else:
                col1, col2 = st.columns(2)

                with col1:
                    email_val = st.text_input("Email", value=selected.get("email", ""), key="admin_edit_email")
                    cur_role = selected.get("role", "player") or "player"
                    role_choices = ["player", "admin"]
                    if cur_role not in role_choices:
                        role_choices.insert(0, cur_role)
                    new_role = st.selectbox("Role", role_choices,
                                           index=role_choices.index(cur_role), key="admin_edit_role")

                with col2:
                    cur_active = bool(selected.get("is_active", True))
                    new_active = st.checkbox("Active", value=cur_active, key="admin_edit_active")
                    temp_pw = st.text_input("Set new password (optional)", type="password", key="admin_edit_temp_pw")

                col_a, col_b, col_c = st.columns(3)

                with col_a:
                    if st.button("💾 Save Changes", type="primary", key="admin_save_changes"):
                        something_changed = False

                        try:
                            old_email = (selected.get("email") or "").strip().lower()
                            new_email_clean = (email_val or "").strip().lower()
                            if new_email_clean and new_email_clean != old_email:
                                admin_update_user_email(sel_user_id, new_email_clean)
                                something_changed = True
                        except Exception as e:
                            st.error(f"Email update failed: {e!r}")

                        try:
                            if new_role != cur_role:
                                set_profile_role(sel_user_id, new_role)
                                something_changed = True
                            if new_active != cur_active:
                                set_profile_active(sel_user_id, new_active)
                                something_changed = True
                        except Exception as e:
                            st.error(f"Role/active update failed: {e!r}")

                        try:
                            if temp_pw:
                                admin_set_user_password(sel_user_id, temp_pw)
                                something_changed = True
                        except Exception as e:
                            st.error(f"Password update failed: {e!r}")

                        if something_changed:
                            st.success("✅ User updated.")
                            st.rerun()
                        else:
                            st.info("No changes to save.")

                with col_c:
                    if st.button("🗑️ Delete User", type="secondary", key="admin_delete_user"):
                        try:
                            admin_delete_user(sel_user_id)
                            delete_profile_by_user_id(sel_user_id)
                            st.success("✅ User deleted.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to delete user: {e!r}")

    # ── All Users Table ──
    st.markdown('<div class="section-title">All Users</div>', unsafe_allow_html=True)

    if not all_profiles:
        st.info("No users found.")
    else:
        table = []
        for p in all_profiles:
            status = p.get("subscription_status", "unknown")
            override = p.get("admin_override_active", False)
            if override:
                display_status = "🎁 free access"
            else:
                display_status = f"{_status_emoji(status)} {status}"
            table.append({
                "Email": p.get("email"),
                "Status": display_status,
                "Role": p.get("role", "player"),
                "Active": "✓" if p.get("is_active") else "✗",
                "Created": _fmt_date(p.get("created_at")),
            })

        st.dataframe(table, use_container_width=True, hide_index=True, height=400)


# =============================================================================
# TAB 3: SUBSCRIPTIONS
# =============================================================================

with tabs[2]:

    if not all_profiles:
        st.info("No users found.")
    else:
        # Select user
        labels = []
        label_to_profile = {}

        for p in all_profiles:
            email = (p.get("email") or "—").strip()
            status = p.get("subscription_status", "unknown")
            label = f"{_status_emoji(status)} {email}"
            labels.append(label)
            label_to_profile[label] = p

        sel_label = st.selectbox("Select user", options=labels, key="sub_select_user")
        selected = label_to_profile.get(sel_label, {})
        sel_user_id = str(selected.get("user_id") or "")

        if not sel_user_id:
            st.error("No user selected.")
        else:
            sub_details = admin_get_subscription_details(sel_user_id) or {}

            # ── Current Status ──
            st.markdown('<div class="section-title">Current Status</div>', unsafe_allow_html=True)

            status = selected.get("subscription_status", "unknown")
            override = selected.get("admin_override_active", False)
            is_trial = selected.get("is_trial", False)
            trial_ends = selected.get("trial_ends_at")
            user_active = selected.get("is_active", False)

            st.markdown(f"""
            <div class="stat-grid">
                <div class="stat-card">
                    <div class="stat-value">{_status_emoji(status)} {status}</div>
                    <div class="stat-label">Subscription Status</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{"🎁 Free" if override else "💳 Paid"}</div>
                    <div class="stat-label">Access Type</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{"✅ Yes" if user_active else "🔒 No"}</div>
                    <div class="stat-label">Can Access App</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{f"{_days_until(trial_ends)} days" if is_trial and trial_ends else "N/A"}</div>
                    <div class="stat-label">Trial Remaining</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Payment details
            started = sub_details.get("subscription_started_at")
            period_end = sub_details.get("subscription_current_period_end")
            last_payment = sub_details.get("last_successful_payment_at")
            failed = sub_details.get("failed_payment_count", 0) or 0

            st.markdown(f"""
            <div class="info-row">
                <div class="info-item">
                    <div class="info-label">Sub Started</div>
                    <div class="info-value">{_fmt_date(started) if started else "—"}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Period Ends</div>
                    <div class="info-value">{_fmt_date(period_end) if period_end else "—"}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Last Payment</div>
                    <div class="info-value">{_fmt_date(last_payment) if last_payment else "—"}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Failed Payments</div>
                    <div class="info-value" style="color: {'#FF5252' if failed > 0 else '#E0E0E0'}">{failed}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # ── Access Control ──
            st.markdown('<div class="section-title">Access Control</div>', unsafe_allow_html=True)

            col_a, col_b = st.columns(2)

            with col_a:
                st.markdown("""<div class="action-card">
                    <div class="action-card-title">🎁 Grant Free Access</div>
                    <div class="action-card-desc">Give full access without payment. Bypasses all subscription checks. Use for VIPs, testers, or comp'd users.</div>
                </div>""", unsafe_allow_html=True)
                if st.button("Grant Free Access", key="sub_grant_access", use_container_width=True):
                    try:
                        admin_grant_free_access(sel_user_id, "Admin granted")
                        st.success("✅ Free access granted.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed: {e!r}")

            with col_b:
                st.markdown("""<div class="action-card">
                    <div class="action-card-title">🚫 Remove Free Access</div>
                    <div class="action-card-desc">Remove the override. User falls back to their subscription status. If they don't have one, they see the lockout screen.</div>
                </div>""", unsafe_allow_html=True)
                if st.button("Remove Free Access", key="sub_revoke_access", use_container_width=True):
                    try:
                        admin_revoke_free_access(sel_user_id)
                        st.success("✅ Free access removed.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed: {e!r}")

            # ── Trial Management ──
            st.markdown('<div class="section-title">Trial Management</div>', unsafe_allow_html=True)

            col_c, col_d = st.columns(2)

            with col_c:
                st.markdown("""<div class="action-card">
                    <div class="action-card-title">⏰ Extend Trial</div>
                    <div class="action-card-desc">Add days to the trial. Extends from current end date, or starts from today if no trial exists.</div>
                </div>""", unsafe_allow_html=True)
                extend_days = st.number_input("Days to add", min_value=1, max_value=90, value=7, key="sub_extend_days")
                if st.button("Extend Trial", key="sub_extend_trial", use_container_width=True):
                    try:
                        admin_extend_trial(sel_user_id, days=extend_days)
                        st.success(f"✅ Trial extended by {extend_days} days.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed: {e!r}")

            with col_d:
                st.markdown("""<div class="action-card">
                    <div class="action-card-title">🔗 Payment Link</div>
                    <div class="action-card-desc">Copy and send to the user so they can subscribe. This link is unique to their account.</div>
                </div>""", unsafe_allow_html=True)
                payment_link = admin_resend_payment_link(sel_user_id)
                if payment_link:
                    st.code(payment_link, language=None)
                else:
                    st.caption("No payment link generated for this user.")

            # ── Ban User ──
            st.markdown('<div class="section-title">Ban / Suspend</div>', unsafe_allow_html=True)

            is_banned = selected.get("subscription_status") == "banned"

            if is_banned:
                st.markdown("""<div class="alert-card alert-danger">
                    <div class="alert-text">⛔ <strong>This user is BANNED.</strong> They cannot access the app regardless of payment status. Unban them to restore access.</div>
                </div>""", unsafe_allow_html=True)
                if st.button("✅ Unban User", key="sub_unban_user", use_container_width=True):
                    try:
                        admin_unban_user(sel_user_id)
                        st.success("✅ User unbanned — set to pending. Grant free access or let them subscribe.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed: {e!r}")
            else:
                st.markdown("""<div class="action-card">
                    <div class="action-card-title">⛔ Ban User</div>
                    <div class="action-card-desc">Permanently lock this user out. They'll see "Account Suspended — contact admin." Even paying won't get them back in. Only you can unban them.</div>
                </div>""", unsafe_allow_html=True)
                ban_reason = st.text_input("Reason (shown to user)", key="sub_ban_reason", placeholder="e.g. Violated terms of service")
                if st.button("Ban User", type="secondary", key="sub_ban_user", use_container_width=True):
                    try:
                        admin_ban_user(sel_user_id, reason=ban_reason or "Account suspended by admin. Contact support for details.")
                        st.success("⛔ User banned — locked out immediately.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed: {e!r}")

            # ── Advanced ──
            with st.expander("⚙️ Advanced: Force Status Change", expanded=False):
                st.caption("Manually override subscription status. Use only if the controls above don't cover your situation.")

                col1, col2 = st.columns([2, 1])

                with col1:
                    new_status = st.selectbox(
                        "New Status",
                        ["pending", "trial", "active", "grace_period", "overdue", "cancelled", "expired", "banned"],
                        key="sub_new_status"
                    )
                    descs = {
                        "pending": "Not paid. Sees 'Complete Your Subscription' screen.",
                        "trial": "Free trial. Needs trial_ends_at set.",
                        "active": "Paid subscriber. Full access.",
                        "grace_period": "Payment failed, temporary access with warning banner.",
                        "overdue": "Payment failed past grace. Locked out.",
                        "cancelled": "Cancelled. Locked out.",
                        "expired": "Term ended. Locked out.",
                        "banned": "Admin banned. Locked out. Can't resubscribe.",
                    }
                    st.caption(descs.get(new_status, ""))

                with col2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("⚡ Force Status", type="secondary", key="sub_force_status"):
                        try:
                            if new_status == "banned":
                                admin_ban_user(sel_user_id, reason="Banned via admin force status")
                            elif new_status == "trial":
                                admin_set_subscription_status(sel_user_id, new_status)
                                admin_extend_trial(sel_user_id, days=7)
                            else:
                                admin_set_subscription_status(sel_user_id, new_status)
                            st.success(f"✅ Status → {new_status}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed: {e!r}")


# =============================================================================
# TAB 4: PLAYER DETAIL
# =============================================================================

with tabs[3]:

    if not all_profiles:
        st.info("No users found.")
    else:
        email_to_profile = {p.get("email", ""): p for p in all_profiles}
        emails_sorted = sorted(email_to_profile.keys())

        sel_email = st.selectbox("Select player", options=emails_sorted, key="detail_player_email")
        sel_profile = email_to_profile.get(sel_email, {})
        sel_user_id = str(sel_profile.get("user_id") or "")

        if not sel_user_id:
            st.warning("Selected profile has no user_id.")
        else:
            # Status header
            status = sel_profile.get("subscription_status", "unknown")
            override = sel_profile.get("admin_override_active", False)
            created = sel_profile.get("created_at")

            # Calculate subscription value
            sub_started = sel_profile.get("subscription_started_at")
            months_subscribed = 0
            user_revenue = 0
            if sub_started:
                try:
                    start_dt = datetime.fromisoformat(str(sub_started).replace("Z", "+00:00"))
                    delta = datetime.now(timezone.utc) - start_dt
                    months_subscribed = max(1, round(delta.days / 30))
                    user_revenue = months_subscribed * 299
                except Exception:
                    pass

            if override:
                display_status = "🎁 free access"
            else:
                display_status = f"{_status_emoji(status)} {status}"

            rev_color = "#69F0AE" if user_revenue > 0 else "rgba(255,255,255,0.2)"

            st.markdown(f"""
            <div class="info-row" style="margin-top: 16px;">
                <div class="info-item">
                    <div class="info-label">Status</div>
                    <div class="info-value">{display_status}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Active</div>
                    <div class="info-value">{"✅" if sel_profile.get("is_active") else "🔒"}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Member Since</div>
                    <div class="info-value">{_fmt_date(created)}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Role</div>
                    <div class="info-value">{sel_profile.get("role", "player")}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Months Subscribed</div>
                    <div class="info-value">{months_subscribed if months_subscribed > 0 else "—"}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Total Revenue</div>
                    <div class="info-value" style="color:{rev_color}">{_fmt_currency(user_revenue) if user_revenue > 0 else "—"}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Settings
            st.markdown('<div class="section-title">Settings</div>', unsafe_allow_html=True)

            try:
                settings = get_user_settings(sel_user_id)
            except Exception as e:
                st.error(f"Could not load settings: {e!r}")
                settings = {}

            bankroll = settings.get("bankroll", 0)
            stakes = settings.get("default_stakes", "—")
            risk_mode = settings.get("risk_mode", "balanced")

            st.markdown(f"""
            <div class="info-row">
                <div class="info-item">
                    <div class="info-label">Bankroll</div>
                    <div class="info-value">{_fmt_currency(bankroll)}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Default Stakes</div>
                    <div class="info-value">{stakes}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Risk Mode</div>
                    <div class="info-value">{risk_mode.title()}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Load sessions for detailed stats
            st.markdown('<div class="section-title">Statistics</div>', unsafe_allow_html=True)

            try:
                sessions_list = get_recent_sessions_for_user_admin(sel_user_id, limit=100)
            except Exception as e:
                st.error(f"Could not load sessions: {e!r}")
                sessions_list = []

            # Calculate stats from raw sessions
            completed = [s for s in sessions_list if s.get("status") == "completed"]
            total_sessions = len(completed)
            total_hands = sum(int(s.get("hands_played") or 0) for s in completed)
            total_decisions = sum(int(s.get("decisions_requested") or 0) for s in completed)
            total_duration_min = sum(int(s.get("duration_minutes") or 0) for s in completed)
            total_hours = total_duration_min / 60 if total_duration_min > 0 else 0

            profits = [_safe_float(s.get("profit_loss", 0)) for s in completed]
            total_profit = sum(profits)
            winning_sessions = sum(1 for pl in profits if pl > 0)
            losing_sessions = sum(1 for pl in profits if pl < 0)
            breakeven_sessions = sum(1 for pl in profits if pl == 0)
            win_pct = (winning_sessions / total_sessions * 100) if total_sessions > 0 else 0

            biggest_win = max(profits) if profits else 0
            biggest_loss = min(profits) if profits else 0

            avg_session_min = (total_duration_min / total_sessions) if total_sessions > 0 else 0
            avg_hands_per_session = (total_hands / total_sessions) if total_sessions > 0 else 0

            # BB/100 from raw data
            total_bb_won = sum(_safe_float(s.get("profit_loss_bb", 0)) for s in completed)
            bb_per_100 = (total_bb_won / total_hands * 100) if total_hands > 0 else 0

            # Win/loss outcomes
            total_won = sum(int(s.get("outcomes_won") or 0) for s in completed)
            total_lost = sum(int(s.get("outcomes_lost") or 0) for s in completed)
            total_folded = sum(int(s.get("outcomes_folded") or 0) for s in completed)
            total_outcomes = total_won + total_lost + total_folded
            fold_pct = (total_folded / total_outcomes * 100) if total_outcomes > 0 else 0
            win_at_showdown = (total_won / (total_won + total_lost) * 100) if (total_won + total_lost) > 0 else 0

            # Last active
            last_session = completed[0] if completed else None
            last_active_date = _fmt_date(last_session.get("started_at")) if last_session else "Never"
            days_since_active = _days_ago(last_session.get("started_at")) if last_session else 999

            # Current streak
            streak = 0
            streak_type = ""
            for pl in profits:
                if streak == 0:
                    streak_type = "W" if pl > 0 else ("L" if pl < 0 else "")
                    streak = 1 if streak_type else 0
                elif (streak_type == "W" and pl > 0) or (streak_type == "L" and pl < 0):
                    streak += 1
                else:
                    break

            streak_display = f"{streak}{streak_type}" if streak > 0 else "—"
            streak_color = "#69F0AE" if streak_type == "W" else "#FF5252" if streak_type == "L" else "#E0E0E0"

            # Player tier
            PROFIT_TIERS = [
                {"name": "Grinder",         "emoji": "🌱", "min": 0,     "color": "#6b7280"},
                {"name": "Winning Player",  "emoji": "📈", "min": 1000,  "color": "#22c55e"},
                {"name": "Shark",           "emoji": "🎯", "min": 5000,  "color": "#3b82f6"},
                {"name": "High Roller",     "emoji": "💰", "min": 15000, "color": "#f59e0b"},
                {"name": "Diamond Crusher", "emoji": "💎", "min": 35000, "color": "#8b5cf6"},
                {"name": "Poker Royalty",   "emoji": "👑", "min": 75000, "color": "#ec4899"},
            ]
            tier = PROFIT_TIERS[0]
            for t in PROFIT_TIERS:
                if total_profit >= t["min"]:
                    tier = t

            # Tier card
            st.markdown(f"""
            <div style="background:linear-gradient(135deg,#0F0F1A 0%,#151520 100%);border:1px solid rgba(255,255,255,0.06);border-radius:12px;padding:16px 20px;margin-bottom:16px;display:flex;align-items:center;gap:16px;">
                <div style="font-size:36px;">{tier['emoji']}</div>
                <div>
                    <div style="font-family:'JetBrains Mono',monospace;font-size:18px;font-weight:700;color:{tier['color']}">{tier['name']}</div>
                    <div style="font-size:12px;color:rgba(255,255,255,0.35);">Based on {_fmt_currency(total_profit)} lifetime profit</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Main stats
            profit_color = "#69F0AE" if total_profit >= 0 else "#FF5252"
            profit_sign = "+" if total_profit >= 0 else ""

            st.markdown(f"""
            <div class="stat-grid">
                <div class="stat-card">
                    <div class="stat-value" style="color: {profit_color}">{profit_sign}{_fmt_currency(total_profit)}</div>
                    <div class="stat-label">Total Profit/Loss</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{bb_per_100:+.1f}</div>
                    <div class="stat-label">BB/100</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{total_sessions}</div>
                    <div class="stat-label">Sessions ({win_pct:.0f}% win)</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{total_hands:,}</div>
                    <div class="stat-label">Hands · {total_hours:.1f}h played</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Engagement & performance row
            st.markdown(f"""
            <div class="stat-grid">
                <div class="stat-card">
                    <div class="stat-value" style="color:{'#69F0AE' if days_since_active <= 3 else '#FFB300' if days_since_active <= 7 else '#FF5252'}">{last_active_date}</div>
                    <div class="stat-label">Last Active · {days_since_active}d ago</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" style="color:{streak_color}">{streak_display}</div>
                    <div class="stat-label">Current Streak</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" style="color:#69F0AE">{_fmt_currency(biggest_win)}</div>
                    <div class="stat-label">Biggest Win</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" style="color:#FF5252">{_fmt_currency(biggest_loss)}</div>
                    <div class="stat-label">Biggest Loss</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Detailed stats
            st.markdown(f"""
            <div class="stat-grid">
                <div class="stat-card">
                    <div class="stat-value">{avg_session_min:.0f}m</div>
                    <div class="stat-label">Avg Session Length</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{avg_hands_per_session:.0f}</div>
                    <div class="stat-label">Avg Hands / Session</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{total_decisions:,}</div>
                    <div class="stat-label">Decisions Requested</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{fold_pct:.0f}%</div>
                    <div class="stat-label">Fold Rate · {win_at_showdown:.0f}% W@SD</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Recent sessions
            st.markdown('<div class="section-title">Recent Sessions</div>', unsafe_allow_html=True)

            if not sessions_list:
                st.caption("No sessions recorded yet.")
            else:
                sess_rows = []
                for s in sessions_list[:20]:
                    pl = _safe_float(s.get("profit_loss", 0))
                    pl_str = f"+${pl:.2f}" if pl >= 0 else f"-${abs(pl):.2f}"
                    dur = int(s.get("duration_minutes") or 0)
                    dur_str = f"{dur // 60}h {dur % 60}m" if dur >= 60 else f"{dur}m"

                    sess_rows.append({
                        "Date": _fmt_date(s.get("started_at")),
                        "Stakes": s.get("stakes", "—"),
                        "Duration": dur_str,
                        "Hands": s.get("hands_played", 0) or 0,
                        "P/L": pl_str,
                        "W/L/F": f"{s.get('outcomes_won', 0)}/{s.get('outcomes_lost', 0)}/{s.get('outcomes_folded', 0)}",
                        "End": s.get("end_reason", "—") or "—",
                    })

                st.dataframe(sess_rows, use_container_width=True, hide_index=True, height=400)


# =============================================================================
# FOOTER
# =============================================================================

st.markdown('<div style="height:1px;background:rgba(255,255,255,0.06);margin:32px 0 12px 0"></div>', unsafe_allow_html=True)
st.markdown('<div style="text-align:center;font-size:11px;color:rgba(255,255,255,0.15);font-family:JetBrains Mono,monospace;letter-spacing:0.03em;">NAMELESS POKER · Admin Console · Handle with care</div>', unsafe_allow_html=True)