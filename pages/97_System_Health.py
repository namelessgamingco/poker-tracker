# pages/97_System_Health.py — System Health Dashboard
# =============================================================================
# Quick-glance health check for all critical systems.
# Green = good, Red = broken, Yellow = warning.
# =============================================================================

import os
import time
import streamlit as st

from auth import require_auth
from sidebar import render_sidebar
from supabase_client import get_supabase, get_supabase_admin

from db import (
    list_profiles_for_admin,
    get_user_sessions,
    get_player_stats,
    get_user_settings,
)

st.set_page_config(page_title="System Health", page_icon="🩺", layout="wide")

# ---------- Auth + admin gate ----------

user = require_auth()
render_sidebar()

role = st.session_state.get("role", "player")
is_admin = bool(st.session_state.get("is_admin", False))
is_active = bool(st.session_state.get("is_active", True))
email = st.session_state.get("user_email", "unknown@example.com")

if not is_admin:
    st.error("System Health is admin-only.")
    st.stop()

# ---------- CSS ----------

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700;800&family=Inter:wght@400;500;600;700&display=swap');

[data-testid="stAppViewContainer"] { background: #0A0A12; }

.health-header {
    font-family: 'JetBrains Mono', monospace;
    font-size: 24px; font-weight: 800;
    letter-spacing: 0.06em; color: #E0E0E0;
    margin-bottom: 4px;
}
.health-sub {
    font-size: 13px; color: rgba(255,255,255,0.3);
    margin-bottom: 20px;
}
.section-title {
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px; font-weight: 700;
    color: rgba(255,255,255,0.4);
    letter-spacing: 0.06em; text-transform: uppercase;
    margin: 24px 0 12px 0;
}
.check-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px; margin-bottom: 20px;
}
.check-card {
    background: linear-gradient(135deg, #0F0F1A 0%, #151520 100%);
    border-radius: 12px; padding: 16px 18px;
}
.check-card.ok { border: 1px solid rgba(105,240,174,0.2); }
.check-card.warn { border: 1px solid rgba(255,179,0,0.2); }
.check-card.err { border: 1px solid rgba(255,82,82,0.2); }
.check-icon { font-size: 20px; margin-bottom: 6px; }
.check-title {
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px; font-weight: 700;
    color: rgba(255,255,255,0.5);
    letter-spacing: 0.04em; text-transform: uppercase;
    margin-bottom: 4px;
}
.check-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 15px; font-weight: 700; color: #E0E0E0;
}
.check-detail {
    font-size: 11px; color: rgba(255,255,255,0.25);
    margin-top: 4px;
}
.env-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 8px; margin-bottom: 16px;
}
.env-item {
    background: rgba(255,255,255,0.02);
    border: 1px solid rgba(255,255,255,0.04);
    border-radius: 8px; padding: 10px 14px;
    display: flex; justify-content: space-between; align-items: center;
}
.env-name {
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px; color: rgba(255,255,255,0.5);
}
.env-status {
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px; font-weight: 700;
}
.stat-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px; margin-bottom: 16px;
}
.stat-card {
    background: linear-gradient(135deg, #0F0F1A 0%, #151520 100%);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 12px; padding: 16px;
}
.stat-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 22px; font-weight: 700; color: #E0E0E0;
}
.stat-label {
    font-size: 11px; color: rgba(255,255,255,0.3);
    text-transform: uppercase; letter-spacing: 0.05em;
    margin-top: 4px;
}
</style>
""", unsafe_allow_html=True)

# ---------- Header ----------

env_name = os.getenv("APP_ENV", "unknown").upper()
st.markdown(f"""
<div class="health-header">🩺 SYSTEM HEALTH</div>
<div class="health-sub">{email} · {env_name} environment · {time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())}</div>
""", unsafe_allow_html=True)

st.markdown('<div style="height:1px;background:rgba(255,255,255,0.06);margin:0 0 20px 0"></div>', unsafe_allow_html=True)


# =============================================================================
# CONNECTIVITY CHECKS
# =============================================================================

sb_status = "unknown"
sb_error = None
service_role_status = "unknown"
service_role_error = None
auth_status = "unknown"
auth_error = None

# 1) Anon client
sb = None
anon_latency_ms = None
try:
    t0 = time.perf_counter()
    sb = get_supabase()
    _ = sb.table("poker_profiles").select("user_id, email").limit(1).execute()
    t1 = time.perf_counter()
    anon_latency_ms = round((t1 - t0) * 1000, 1)
    sb_status = "OK"
except Exception as e:
    sb_status = "ERROR"
    sb_error = repr(e)

# 2) Auth session (check Streamlit session state, not anon client)
try:
    auth_id = st.session_state.get("user_db_id") or st.session_state.get("auth_id")
    auth_email = st.session_state.get("user_email")
    if auth_id and auth_email:
        auth_status = "OK"
        auth_detail_msg = auth_email
    else:
        auth_status = "WARN"
        auth_detail_msg = "No user in session state"
except Exception as e:
    auth_status = "ERROR"
    auth_error = repr(e)

# 3) Service-role client
service_role_key_present = bool(
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or st.secrets.get("SUPABASE_SERVICE_ROLE_KEY", None)
)
try:
    if service_role_key_present:
        rows = list_profiles_for_admin()
        service_role_status = "OK"
    else:
        service_role_status = "NOT CONFIGURED"
except Exception as e:
    service_role_status = "ERROR"
    service_role_error = repr(e)

# Build status cards
def _card_class(status):
    if status == "OK":
        return "ok"
    elif status in ("ERROR", "NOT CONFIGURED"):
        return "err"
    return "warn"

def _card_icon(status):
    if status == "OK":
        return "✅"
    elif status in ("ERROR", "NOT CONFIGURED"):
        return "❌"
    return "⚠️"

anon_detail = f"{anon_latency_ms}ms latency" if anon_latency_ms else (sb_error[:60] if sb_error else "")
auth_detail = ""
if auth_status == "WARN":
    auth_detail = "No user in session"
elif auth_error:
    auth_detail = auth_error[:60]

sr_detail = ""
if service_role_status == "NOT CONFIGURED":
    sr_detail = "SUPABASE_SERVICE_ROLE_KEY not set"
elif service_role_error:
    sr_detail = service_role_error[:60]

st.markdown(f"""
<div class="section-title">Connectivity</div>
<div class="check-grid">
    <div class="check-card {_card_class(sb_status)}">
        <div class="check-icon">{_card_icon(sb_status)}</div>
        <div class="check-title">Supabase (Anon)</div>
        <div class="check-value">{sb_status}</div>
        <div class="check-detail">{anon_detail}</div>
    </div>
    <div class="check-card {_card_class(auth_status)}">
        <div class="check-icon">{_card_icon(auth_status)}</div>
        <div class="check-title">Auth Session</div>
        <div class="check-value">{auth_status}</div>
        <div class="check-detail">{auth_detail}</div>
    </div>
    <div class="check-card {_card_class(service_role_status)}">
        <div class="check-icon">{_card_icon(service_role_status)}</div>
        <div class="check-title">Service Role (Admin)</div>
        <div class="check-value">{service_role_status}</div>
        <div class="check-detail">{sr_detail}</div>
    </div>
</div>
""", unsafe_allow_html=True)


# =============================================================================
# ENVIRONMENT VARIABLES
# =============================================================================

env_vars_to_check = {
    "APP_ENV": "always",
    "SUPABASE_URL_DEV": "dev",
    "SUPABASE_URL_PROD": "prod",
    "SUPABASE_ANON_KEY_DEV": "dev",
    "SUPABASE_ANON_KEY_PROD": "prod",
    "SUPABASE_SERVICE_ROLE_KEY": "always",
    "RADOM_PAYMENT_LINK_BASE": "always",
    "RADOM_WEBHOOK_KEY": "webhook",
}

app_env = os.getenv("APP_ENV", "dev")
env_html = ""
for name, required_in in env_vars_to_check.items():
    val = os.getenv(name)
    # Skip vars not needed in this environment
    if required_in == "dev" and app_env == "prod":
        continue
    if required_in == "prod" and app_env == "dev":
        continue
    if required_in == "webhook" and app_env != "webhook":
        # Show as optional, not missing
        if val:
            status_color = "#69F0AE"
            status_text = "SET"
        else:
            status_color = "rgba(255,255,255,0.25)"
            status_text = "N/A"
        env_html += f"""
        <div class="env-item">
            <div class="env-name">{name}</div>
            <div class="env-status" style="color:{status_color}">{status_text}</div>
        </div>"""
        continue

    if val:
        status_color = "#69F0AE"
        status_text = "SET"
    else:
        status_color = "#FF5252"
        status_text = "MISSING"
    env_html += f"""
    <div class="env-item">
        <div class="env-name">{name}</div>
        <div class="env-status" style="color:{status_color}">{status_text}</div>
    </div>"""

st.markdown(f"""
<div class="section-title">Environment Variables</div>
<div class="env-grid">{env_html}</div>
""", unsafe_allow_html=True)


# =============================================================================
# DATABASE TABLES
# =============================================================================

st.markdown('<div class="section-title">Database Tables</div>', unsafe_allow_html=True)

if sb is None or sb_status != "OK":
    st.caption("Skipped — anon client unavailable.")
else:
    core_tables = [
        "poker_profiles",
        "poker_sessions",
        "poker_hands",
        "poker_stakes_reference",
        "poker_bankroll_history",
    ]

    table_html = ""
    for tname in core_tables:
        try:
            res = sb.table(tname).select("*", count="exact").limit(1).execute()
            count = getattr(res, "count", "?")
            t_status = "ok"
            t_icon = "✅"
            t_detail = f"{count} rows"
        except Exception as e:
            t_status = "err"
            t_icon = "❌"
            t_detail = str(e)[:50]

        table_html += f"""
        <div class="check-card {t_status}" style="padding:12px 16px;margin-bottom:8px;display:flex;align-items:center;gap:12px;">
            <div style="font-size:16px;">{t_icon}</div>
            <div style="flex:1;">
                <div style="font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:600;color:#E0E0E0;">{tname}</div>
            </div>
            <div style="font-family:'JetBrains Mono',monospace;font-size:12px;color:rgba(255,255,255,0.4);">{t_detail}</div>
        </div>"""

    st.markdown(table_html, unsafe_allow_html=True)


# =============================================================================
# SUBSCRIPTION OVERVIEW
# =============================================================================

st.markdown('<div class="section-title">Subscription Overview</div>', unsafe_allow_html=True)

if service_role_status == "OK":
    try:
        all_profiles = list_profiles_for_admin()

        status_counts = {}
        for p in all_profiles:
            s = p.get("subscription_status", "unknown") or "unknown"
            status_counts[s] = status_counts.get(s, 0) + 1

        total = len(all_profiles)
        active = status_counts.get("active", 0)
        trial = status_counts.get("trial", 0)
        pending = status_counts.get("pending", 0)
        overdue = status_counts.get("overdue", 0)
        banned = status_counts.get("banned", 0)
        override = sum(1 for p in all_profiles if p.get("admin_override_active"))

        st.markdown(f"""
        <div class="stat-grid">
            <div class="stat-card">
                <div class="stat-value">{total}</div>
                <div class="stat-label">Total Users</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color:#69F0AE">{active}</div>
                <div class="stat-label">Active Subscribers</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color:#4BA3FF">{trial}</div>
                <div class="stat-label">Trial</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{override}</div>
                <div class="stat-label">Free Access</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        if overdue > 0 or banned > 0 or pending > 0:
            alerts = ""
            if overdue > 0:
                alerts += f'<div style="color:#FFB300;font-size:13px;">⚠️ {overdue} overdue</div>'
            if banned > 0:
                alerts += f'<div style="color:#FF5252;font-size:13px;">⛔ {banned} banned</div>'
            if pending > 0:
                alerts += f'<div style="color:rgba(255,255,255,0.4);font-size:13px;">⚪ {pending} pending signup</div>'
            st.markdown(alerts, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Error loading subscription overview: {e!r}")
else:
    st.caption("Requires service-role access.")


# =============================================================================
# RLS CHECKS
# =============================================================================

uid = str(st.session_state.get("user_db_id") or "")

if sb is not None and sb_status == "OK" and uid:
    st.markdown('<div class="section-title">RLS Checks (Current User)</div>', unsafe_allow_html=True)

    rls_results = []

    # Profile check
    try:
        res = sb.table("poker_profiles").select("user_id, email, role, is_active, subscription_status").eq("user_id", uid).execute()
        n = len(res.data or [])
        if n == 1:
            rls_results.append(("poker_profiles", "ok", "✅", "1 row visible (correct)"))
        elif n == 0:
            rls_results.append(("poker_profiles", "warn", "⚠️", "0 rows — RLS or data issue"))
        else:
            rls_results.append(("poker_profiles", "err", "❌", f"{n} rows — should be 1"))
    except Exception as e:
        rls_results.append(("poker_profiles", "err", "❌", str(e)[:50]))

    # Sessions check
    try:
        res = sb.table("poker_sessions").select("id, stakes, profit_loss, status").eq("user_id", uid).limit(3).execute()
        n = len(res.data or [])
        rls_results.append(("poker_sessions", "ok", "✅", f"{n} rows visible"))
    except Exception as e:
        rls_results.append(("poker_sessions", "err", "❌", str(e)[:50]))

    rls_html = ""
    for tname, cls, icon, detail in rls_results:
        rls_html += f"""
        <div class="check-card {cls}" style="padding:12px 16px;margin-bottom:8px;display:flex;align-items:center;gap:12px;">
            <div style="font-size:16px;">{icon}</div>
            <div style="flex:1;">
                <div style="font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:600;color:#E0E0E0;">{tname}</div>
            </div>
            <div style="font-family:'JetBrains Mono',monospace;font-size:12px;color:rgba(255,255,255,0.4);">{detail}</div>
        </div>"""

    st.markdown(rls_html, unsafe_allow_html=True)


# =============================================================================
# FOOTER
# =============================================================================

st.markdown('<div style="height:1px;background:rgba(255,255,255,0.06);margin:32px 0 12px 0"></div>', unsafe_allow_html=True)
st.markdown('<div style="text-align:center;font-size:11px;color:rgba(255,255,255,0.15);font-family:JetBrains Mono,monospace;">All green = ship it. Any red = fix before deploying.</div>', unsafe_allow_html=True)