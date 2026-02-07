# pages/99_Admin.py — Admin Console for Poker Decision App
# =============================================================================
#
# COMPLETE CONTROL CENTER FOR $299/MONTH SUBSCRIPTION MANAGEMENT
#
# TABS:
# 1. Dashboard - Revenue metrics, user counts, quick stats
# 2. User Management - Create/Edit/Delete users
# 3. Subscriptions - Subscription control, trials, overrides
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
# HELPERS
# =============================================================================

def _safe_float(x, default=0.0):
    try:
        v = float(x)
        return v if isfinite(v) else default
    except Exception:
        return default


def _fmt_currency(amount: float) -> str:
    """Format as currency."""
    return f"${amount:,.2f}"


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


def _fmt_date(ts_raw) -> str:
    """Format ISO timestamp → 'YYYY-MM-DD'."""
    if not ts_raw:
        return "—"
    try:
        dt = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return str(ts_raw)


def _days_until(ts_raw) -> int:
    """Days until a future timestamp."""
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
    """Days since a past timestamp."""
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


def _status_color(status: str) -> str:
    """Return color for subscription status."""
    colors = {
        "active": "🟢",
        "trial": "🔵",
        "grace_period": "🟡",
        "pending": "⚪",
        "overdue": "🟠",
        "cancelled": "🔴",
        "expired": "⚫",
    }
    return colors.get(status, "⚪")


# =============================================================================
# PAGE HEADER
# =============================================================================

st.title("🔐 Admin Console")

top1, top2, top3 = st.columns(3)
with top1:
    st.metric("Admin User", cur_email)
with top2:
    st.metric("Role", role)
with top3:
    env = os.getenv("APP_ENV", "unknown")
    st.metric("Environment", env.upper())

st.divider()


# =============================================================================
# LOAD ALL PROFILES ONCE
# =============================================================================

all_profiles = list_profiles_for_admin()


# =============================================================================
# TABS
# =============================================================================

tabs = st.tabs(["📊 Dashboard", "👤 User Management", "💳 Subscriptions", "🔍 Player Detail"])


# =============================================================================
# TAB 1: DASHBOARD
# =============================================================================

with tabs[0]:
    st.subheader("📊 Revenue Dashboard")
    
    # Calculate metrics
    total_users = len(all_profiles)
    
    active_subs = [p for p in all_profiles if p.get("subscription_status") == "active"]
    trial_users = [p for p in all_profiles if p.get("subscription_status") == "trial"]
    pending_users = [p for p in all_profiles if p.get("subscription_status") == "pending"]
    cancelled_users = [p for p in all_profiles if p.get("subscription_status") in ("cancelled", "expired")]
    override_users = [p for p in all_profiles if p.get("admin_override_active")]
    
    # MRR calculation ($299/month per active subscriber)
    mrr = len(active_subs) * 299
    
    # Revenue at risk (trials expiring in 3 days)
    trials_expiring_soon = []
    for p in trial_users:
        trial_ends = p.get("trial_ends_at")
        if trial_ends and _days_until(trial_ends) <= 3:
            trials_expiring_soon.append(p)
    
    # Display metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Users", total_users)
    with col2:
        st.metric("Active Subscribers", len(active_subs), 
                  help="Users with subscription_status = 'active'")
    with col3:
        st.metric("Monthly Revenue (MRR)", _fmt_currency(mrr))
    with col4:
        st.metric("Trial Users", len(trial_users),
                  help="Users currently in trial period")
    
    col5, col6, col7, col8 = st.columns(4)
    
    with col5:
        st.metric("Pending Signup", len(pending_users),
                  help="Users who haven't completed payment")
    with col6:
        st.metric("Cancelled/Expired", len(cancelled_users))
    with col7:
        st.metric("Admin Overrides", len(override_users),
                  help="Users with free access granted")
    with col8:
        st.metric("Trials Expiring Soon", len(trials_expiring_soon),
                  help="Trial users expiring in 3 days or less")
    
    st.divider()
    
    # Subscription breakdown
    st.markdown("#### Subscription Status Breakdown")
    
    status_counts = {}
    for p in all_profiles:
        status = p.get("subscription_status", "unknown") or "unknown"
        status_counts[status] = status_counts.get(status, 0) + 1
    
    status_data = []
    for status, count in sorted(status_counts.items(), key=lambda x: -x[1]):
        status_data.append({
            "Status": f"{_status_color(status)} {status}",
            "Count": count,
            "% of Total": f"{count/total_users*100:.1f}%" if total_users > 0 else "0%",
        })
    
    st.dataframe(status_data, use_container_width=True, height=250)
    
    # Trials expiring soon
    if trials_expiring_soon:
        st.markdown("#### ⚠️ Trials Expiring Soon")
        expiring_data = []
        for p in trials_expiring_soon:
            expiring_data.append({
                "Email": p.get("email"),
                "Trial Ends": _fmt_date(p.get("trial_ends_at")),
                "Days Left": _days_until(p.get("trial_ends_at")),
            })
        st.dataframe(expiring_data, use_container_width=True, height=150)
    
    # Recent activity
    st.markdown("#### Recent User Activity")
    
    recent_activity = []
    for p in all_profiles:
        last_active = p.get("updated_at") or p.get("created_at")
        recent_activity.append({
            "email": p.get("email"),
            "status": p.get("subscription_status"),
            "last_active": last_active,
            "days_ago": _days_ago(last_active),
        })
    
    # Sort by most recent
    recent_activity.sort(key=lambda x: x["days_ago"])
    
    activity_display = []
    for a in recent_activity[:10]:
        activity_display.append({
            "Email": a["email"],
            "Status": f"{_status_color(a['status'])} {a['status']}",
            "Last Active": _fmt_date(a["last_active"]),
            "Days Ago": a["days_ago"],
        })
    
    st.dataframe(activity_display, use_container_width=True, height=300)


# =============================================================================
# TAB 2: USER MANAGEMENT
# =============================================================================

with tabs[1]:
    st.subheader("👤 User Management")
    
    # ----- Create new user -----
    with st.expander("➕ Create New User", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            new_email = st.text_input("Email", key="admin_new_email")
            new_pw = st.text_input("Password", type="password", key="admin_new_pw")
        
        with col2:
            new_role = st.selectbox(
                "Role",
                ["player", "admin"],
                index=0,
                key="admin_new_role",
            )
            new_active = st.checkbox("Active immediately", value=False, key="admin_new_active")
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
                        is_active=new_active or start_trial,
                        start_trial=start_trial,
                    )
                    st.success(f"✅ Created user: {created.get('email')}")
                    if created.get("payment_link_url"):
                        st.info(f"Payment link: {created.get('payment_link_url')}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to create user: {e!r}")
    
    # ----- Edit existing user -----
    if all_profiles:
        with st.expander("🛠 Edit Existing User", expanded=False):
            # Build selection
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
                # Editable fields
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
                    
                    temp_pw = st.text_input(
                        "Set new password (optional)",
                        type="password",
                        key="admin_edit_temp_pw",
                    )
                
                # Action buttons
                col_a, col_b, col_c = st.columns(3)
                
                with col_a:
                    if st.button("💾 Save Changes", type="primary", key="admin_save_changes"):
                        something_changed = False
                        
                        # Email change
                        try:
                            old_email = (selected.get("email") or "").strip().lower()
                            new_email_clean = (email_val or "").strip().lower()
                            if new_email_clean and new_email_clean != old_email:
                                admin_update_user_email(sel_user_id, new_email_clean)
                                something_changed = True
                        except Exception as e:
                            st.error(f"Email update failed: {e!r}")
                        
                        # Role/active
                        try:
                            if new_role != cur_role:
                                set_profile_role(sel_user_id, new_role)
                                something_changed = True
                            if new_active != cur_active:
                                set_profile_active(sel_user_id, new_active)
                                something_changed = True
                        except Exception as e:
                            st.error(f"Role/active update failed: {e!r}")
                        
                        # Password
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
    
    # ----- All profiles table -----
    st.markdown("#### All Users")
    
    if not all_profiles:
        st.info("No users found.")
    else:
        table = []
        now_utc = datetime.now(timezone.utc)
        
        for p in all_profiles:
            created_raw = p.get("created_at")
            created_str = _fmt_date(created_raw)
            
            status = p.get("subscription_status", "unknown")
            override = "✓" if p.get("admin_override_active") else ""
            
            table.append({
                "Email": p.get("email"),
                "Status": f"{_status_color(status)} {status}",
                "Role": p.get("role", "player"),
                "Active": "✓" if p.get("is_active") else "✗",
                "Override": override,
                "Created": created_str,
            })
        
        st.dataframe(table, use_container_width=True, height=400)


# =============================================================================
# TAB 3: SUBSCRIPTIONS
# =============================================================================

with tabs[2]:
    st.subheader("💳 Subscription Management")
    
    if not all_profiles:
        st.info("No users found.")
    else:
        # Select user
        labels = []
        label_to_profile = {}
        
        for p in all_profiles:
            email = (p.get("email") or "—").strip()
            status = p.get("subscription_status", "unknown")
            label = f"{_status_color(status)} {email}"
            labels.append(label)
            label_to_profile[label] = p
        
        sel_label = st.selectbox("Select user", options=labels, key="sub_select_user")
        selected = label_to_profile.get(sel_label, {})
        sel_user_id = str(selected.get("user_id") or "")
        
        if not sel_user_id:
            st.error("No user selected.")
        else:
            # Get subscription details
            sub_details = admin_get_subscription_details(sel_user_id) or {}
            
            # Display current status
            st.markdown("---")
            st.markdown("#### Current Subscription Status")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                status = selected.get("subscription_status", "unknown")
                st.metric("Status", f"{_status_color(status)} {status}")
            
            with col2:
                plan = selected.get("subscription_plan", "—")
                amount = selected.get("subscription_amount", 299)
                st.metric("Plan", f"{plan} (${amount}/mo)")
            
            with col3:
                is_trial = selected.get("is_trial", False)
                trial_ends = selected.get("trial_ends_at")
                if is_trial and trial_ends:
                    days_left = _days_until(trial_ends)
                    st.metric("Trial Ends", f"{_fmt_date(trial_ends)} ({days_left} days)")
                else:
                    st.metric("Trial", "N/A")
            
            with col4:
                override = selected.get("admin_override_active", False)
                st.metric("Admin Override", "✅ Active" if override else "❌ None")
            
            # Additional details
            col5, col6, col7, col8 = st.columns(4)
            
            with col5:
                started = sub_details.get("subscription_started_at")
                st.metric("Started", _fmt_date(started) if started else "—")
            
            with col6:
                period_end = sub_details.get("subscription_current_period_end")
                st.metric("Period Ends", _fmt_date(period_end) if period_end else "—")
            
            with col7:
                last_payment = sub_details.get("last_successful_payment_at")
                st.metric("Last Payment", _fmt_date(last_payment) if last_payment else "—")
            
            with col8:
                failed = sub_details.get("failed_payment_count", 0) or 0
                st.metric("Failed Payments", failed)
            
            # Quick actions
            st.markdown("---")
            st.markdown("#### Quick Actions")
            
            col_a, col_b, col_c, col_d = st.columns(4)
            
            with col_a:
                if st.button("🎁 Grant Free Access", key="sub_grant_access"):
                    try:
                        admin_grant_free_access(sel_user_id, "Admin granted")
                        st.success("✅ Free access granted.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed: {e!r}")
            
            with col_b:
                if st.button("🚫 Revoke Override", key="sub_revoke_access"):
                    try:
                        admin_revoke_free_access(sel_user_id)
                        st.success("✅ Override revoked.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed: {e!r}")
            
            with col_c:
                extend_days = st.number_input("Days", min_value=1, max_value=30, value=7, key="sub_extend_days")
                if st.button("⏰ Extend Trial", key="sub_extend_trial"):
                    try:
                        admin_extend_trial(sel_user_id, days=extend_days)
                        st.success(f"✅ Trial extended by {extend_days} days.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed: {e!r}")
            
            with col_d:
                payment_link = admin_resend_payment_link(sel_user_id)
                if payment_link:
                    st.markdown(f"[📧 Payment Link]({payment_link})")
                    st.caption("Copy and send to user")
                else:
                    st.caption("No payment link")
            
            # Force status change
            st.markdown("---")
            st.markdown("#### Force Status Change")
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                new_status = st.selectbox(
                    "New Status",
                    ["pending", "trial", "active", "grace_period", "overdue", "cancelled", "expired"],
                    key="sub_new_status"
                )
            
            with col2:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("⚡ Force Status", type="secondary", key="sub_force_status"):
                    try:
                        admin_set_subscription_status(sel_user_id, new_status)
                        st.success(f"✅ Status changed to {new_status}.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed: {e!r}")
            
            st.caption("⚠️ Use with caution. This directly overrides the subscription status.")


# =============================================================================
# TAB 4: PLAYER DETAIL
# =============================================================================

with tabs[3]:
    st.subheader("🔍 Player Detail")
    
    if not all_profiles:
        st.info("No users found.")
    else:
        # Select user
        email_to_profile = {p.get("email", ""): p for p in all_profiles}
        emails_sorted = sorted(email_to_profile.keys())
        
        sel_email = st.selectbox("Select player", options=emails_sorted, key="detail_player_email")
        sel_profile = email_to_profile.get(sel_email, {})
        sel_user_id = str(sel_profile.get("user_id") or "")
        
        if not sel_user_id:
            st.warning("Selected profile has no user_id.")
        else:
            # User info header
            st.markdown("---")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                status = sel_profile.get("subscription_status", "unknown")
                st.metric("Status", f"{_status_color(status)} {status}")
            
            with col2:
                st.metric("Active", "✓" if sel_profile.get("is_active") else "✗")
            
            with col3:
                created = sel_profile.get("created_at")
                st.metric("Member Since", _fmt_date(created))
            
            with col4:
                override = sel_profile.get("admin_override_active", False)
                st.metric("Free Access", "✓" if override else "✗")
            
            # Settings
            st.markdown("---")
            st.markdown("#### Player Settings")
            
            try:
                settings = get_user_settings(sel_user_id)
            except Exception as e:
                st.error(f"Could not load settings: {e!r}")
                settings = {}
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                bankroll = settings.get("bankroll", 0)
                st.metric("Bankroll", _fmt_currency(bankroll))
            
            with col2:
                stakes = settings.get("default_stakes", "—")
                st.metric("Default Stakes", stakes)
            
            with col3:
                risk_mode = settings.get("risk_mode", "balanced")
                st.metric("Risk Mode", risk_mode.title())
            
            with col4:
                buy_ins = settings.get("buy_in_count", 15)
                st.metric("Buy-in Requirement", f"{buy_ins} BI")
            
            # Stats
            st.markdown("---")
            st.markdown("#### Player Statistics")
            
            try:
                stats = get_player_stats(sel_user_id)
            except Exception as e:
                st.error(f"Could not load stats: {e!r}")
                stats = {}
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                sessions = stats.get("total_sessions", 0)
                st.metric("Total Sessions", sessions)
            
            with col2:
                hands = stats.get("total_hands", 0)
                st.metric("Total Hands", f"{hands:,}")
            
            with col3:
                hours = stats.get("total_hours", 0)
                st.metric("Total Hours", f"{hours:.1f}")
            
            with col4:
                profit = stats.get("total_profit_loss", 0)
                color = "normal" if profit >= 0 else "inverse"
                st.metric("Total Profit/Loss", _fmt_currency(profit), delta_color=color)
            
            col5, col6, col7, col8 = st.columns(4)
            
            with col5:
                win_rate = stats.get("win_rate_bb_100", 0)
                st.metric("Win Rate", f"{win_rate:+.2f} BB/100")
            
            with col6:
                winning = stats.get("winning_sessions", 0)
                st.metric("Winning Sessions", winning)
            
            with col7:
                losing = stats.get("losing_sessions", 0)
                st.metric("Losing Sessions", losing)
            
            with col8:
                if sessions > 0:
                    win_pct = (winning / sessions) * 100
                    st.metric("Win %", f"{win_pct:.1f}%")
                else:
                    st.metric("Win %", "—")
            
            # Recent sessions
            st.markdown("---")
            st.markdown("#### Recent Sessions")
            
            try:
                sessions_list = get_recent_sessions_for_user_admin(sel_user_id, limit=20)
            except Exception as e:
                st.error(f"Could not load sessions: {e!r}")
                sessions_list = []
            
            if not sessions_list:
                st.info("No sessions recorded yet.")
            else:
                sess_rows = []
                for s in sessions_list:
                    pl = _safe_float(s.get("profit_loss", 0))
                    pl_str = f"+${pl:.2f}" if pl >= 0 else f"-${abs(pl):.2f}"
                    
                    sess_rows.append({
                        "Date": _fmt_date(s.get("started_at")),
                        "Stakes": s.get("stakes", "—"),
                        "Duration": f"{s.get('duration_minutes', 0) or 0} min",
                        "Hands": s.get("hands_played", 0) or 0,
                        "P/L": pl_str,
                        "P/L (BB)": f"{_safe_float(s.get('profit_loss_bb', 0)):+.1f}",
                        "End Reason": s.get("end_reason", "—"),
                    })
                
                st.dataframe(sess_rows, use_container_width=True, height=400)
            
            # Session distribution
            if sessions_list:
                st.markdown("#### Session P/L Distribution")
                
                # Group by outcome
                wins = sum(1 for s in sessions_list if _safe_float(s.get("profit_loss", 0)) > 0)
                losses = sum(1 for s in sessions_list if _safe_float(s.get("profit_loss", 0)) < 0)
                breakeven = sum(1 for s in sessions_list if _safe_float(s.get("profit_loss", 0)) == 0)
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("🟢 Winning", wins)
                with col2:
                    st.metric("🔴 Losing", losses)
                with col3:
                    st.metric("⚪ Breakeven", breakeven)


# =============================================================================
# FOOTER
# =============================================================================

st.divider()
st.caption(
    "Admin Console for Poker Decision App. "
    "All subscription management operations are logged. "
    "Use with appropriate caution."
)