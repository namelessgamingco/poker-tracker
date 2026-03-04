# pages/98_QA_Checklist.py — Poker App QA Checklist
# =============================================================================
# Automated tests for all critical poker app systems.
# Run before deploying to production.
# =============================================================================

import os
import time
import streamlit as st
st.set_page_config(page_title="QA Checklist", page_icon="✅", layout="wide")

from auth import require_auth
from sidebar import render_sidebar

user = require_auth()
render_sidebar()

# ---------- Admin gate ----------

role = st.session_state.get("role", "player")
is_admin = bool(st.session_state.get("is_admin", False))

if not is_admin:
    st.error("QA Checklist is admin-only.")
    st.stop()

# ---------- CSS ----------

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700;800&family=Inter:wght@400;500;600;700&display=swap');

[data-testid="stAppViewContainer"] { background: #0A0A12; }

.qa-header {
    font-family: 'JetBrains Mono', monospace;
    font-size: 24px; font-weight: 800;
    letter-spacing: 0.06em; color: #E0E0E0;
    margin-bottom: 4px;
}
.qa-sub {
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
.test-row {
    display: flex; align-items: center; gap: 12px;
    background: linear-gradient(135deg, #0F0F1A 0%, #151520 100%);
    border-radius: 10px; padding: 12px 16px; margin-bottom: 6px;
}
.test-row.pass { border: 1px solid rgba(105,240,174,0.15); }
.test-row.fail { border: 1px solid rgba(255,82,82,0.15); }
.test-row.skip { border: 1px solid rgba(255,255,255,0.06); }
.test-icon { font-size: 18px; flex-shrink: 0; }
.test-name {
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px; font-weight: 600; color: #E0E0E0;
    flex: 1;
}
.test-detail {
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px; color: rgba(255,255,255,0.35);
}
.summary-bar {
    display: flex; gap: 24px; margin: 16px 0;
    padding: 16px 20px;
    background: linear-gradient(135deg, #0F0F1A 0%, #151520 100%);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 12px;
}
.summary-item {
    font-family: 'JetBrains Mono', monospace;
    font-size: 18px; font-weight: 700;
}
.summary-label {
    font-size: 11px; color: rgba(255,255,255,0.3);
    text-transform: uppercase; letter-spacing: 0.05em;
}
</style>
""", unsafe_allow_html=True)

# ---------- Header ----------

st.markdown(f"""
<div class="qa-header">✅ QA CHECKLIST</div>
<div class="qa-sub">Automated tests for all critical systems. Run before deploying.</div>
""", unsafe_allow_html=True)

st.markdown('<div style="height:1px;background:rgba(255,255,255,0.06);margin:0 0 16px 0"></div>', unsafe_allow_html=True)


# =============================================================================
# TEST RUNNER
# =============================================================================

class QARunner:
    def __init__(self):
        self.results = []  # list of (section, name, passed, detail)

    def test(self, section, name, passed, detail=""):
        self.results.append((section, name, bool(passed), str(detail)))

    def render(self):
        # Summary
        total = len(self.results)
        passed = sum(1 for _, _, p, _ in self.results if p)
        failed = total - passed

        pass_color = "#69F0AE" if failed == 0 else "#E0E0E0"
        fail_color = "#FF5252" if failed > 0 else "rgba(255,255,255,0.2)"

        st.markdown(f"""
        <div class="summary-bar">
            <div>
                <div class="summary-item" style="color:{pass_color}">{passed}</div>
                <div class="summary-label">Passed</div>
            </div>
            <div>
                <div class="summary-item" style="color:{fail_color}">{failed}</div>
                <div class="summary-label">Failed</div>
            </div>
            <div>
                <div class="summary-item">{total}</div>
                <div class="summary-label">Total</div>
            </div>
            <div style="flex:1;display:flex;align-items:center;justify-content:flex-end;">
                <div class="summary-item" style="color:{'#69F0AE' if failed == 0 else '#FF5252'}">
                    {'ALL CLEAR ✅' if failed == 0 else f'{failed} ISSUE{"S" if failed != 1 else ""} ❌'}
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Group by section
        current_section = None
        for section, name, passed, detail in self.results:
            if section != current_section:
                st.markdown(f'<div class="section-title">{section}</div>', unsafe_allow_html=True)
                current_section = section

            cls = "pass" if passed else "fail"
            icon = "✅" if passed else "❌"
            detail_html = f'<div class="test-detail">{detail}</div>' if detail else ""

            st.markdown(f"""
            <div class="test-row {cls}">
                <div class="test-icon">{icon}</div>
                <div class="test-name">{name}</div>
                {detail_html}
            </div>
            """, unsafe_allow_html=True)


# =============================================================================
# RUN TESTS
# =============================================================================

if st.button("🚀 Run All Tests", type="primary", use_container_width=True):

    qa = QARunner()

    # ── 1. Environment ──

    env_checks = [
        "APP_ENV",
        "SUPABASE_URL_DEV", "SUPABASE_URL_PROD",
        "SUPABASE_ANON_KEY_DEV", "SUPABASE_ANON_KEY_PROD",
        "SUPABASE_SERVICE_ROLE_KEY",
        "RADOM_PAYMENT_LINK_BASE",
    ]
    for var in env_checks:
        val = os.getenv(var)
        # Only require _DEV vars in dev, _PROD in prod
        app_env = os.getenv("APP_ENV", "dev")
        if "_DEV" in var and app_env == "prod":
            continue
        if "_PROD" in var and app_env == "dev":
            continue
        qa.test("Environment", f"{var} is set", bool(val),
                f"length={len(val)}" if val else "MISSING")

    # ── 2. Supabase Connectivity ──

    from supabase_client import get_supabase, get_supabase_admin

    try:
        sb = get_supabase()
        t0 = time.perf_counter()
        res = sb.table("poker_profiles").select("user_id").limit(1).execute()
        latency = round((time.perf_counter() - t0) * 1000, 1)
        qa.test("Database", "Supabase anon client connects", True, f"{latency}ms")
    except Exception as e:
        sb = None
        qa.test("Database", "Supabase anon client connects", False, str(e)[:80])

    try:
        sb_admin = get_supabase_admin()
        from db import list_profiles_for_admin
        profiles = list_profiles_for_admin()
        qa.test("Database", "Service role client works", True, f"{len(profiles)} profiles loaded")
    except Exception as e:
        profiles = []
        qa.test("Database", "Service role client works", False, str(e)[:80])

    # Auth session
    try:
        got = sb.auth.get_user() if sb else None
        has_user = getattr(got, "user", None) is not None if got else False
        qa.test("Database", "Auth session valid", has_user)
    except Exception as e:
        qa.test("Database", "Auth session valid", False, str(e)[:80])

    # ── 3. Core Tables ──

    if sb:
        core_tables = [
            "poker_profiles", "poker_sessions", "poker_hands",
            "poker_stakes_reference", "poker_bankroll_history",
        ]
        for tname in core_tables:
            try:
                res = sb.table(tname).select("*", count="exact").limit(1).execute()
                count = getattr(res, "count", "?")
                qa.test("Tables", f"{tname} accessible", True, f"{count} rows")
            except Exception as e:
                qa.test("Tables", f"{tname} accessible", False, str(e)[:80])

    # ── 4. Subscription System ──

    if profiles:
        # Check that all status values are valid
        valid_statuses = {"pending", "trial", "active", "grace_period", "overdue", "cancelled", "expired", "banned"}
        bad_statuses = []
        for p in profiles:
            s = p.get("subscription_status")
            if s and s not in valid_statuses:
                bad_statuses.append(f"{p.get('email')}: {s}")

        qa.test("Subscriptions", "All statuses are valid", len(bad_statuses) == 0,
                ", ".join(bad_statuses[:3]) if bad_statuses else f"{len(profiles)} users checked")

        # Check admin override consistency
        override_issues = []
        for p in profiles:
            if p.get("admin_override_active") and not p.get("is_active"):
                override_issues.append(p.get("email"))

        qa.test("Subscriptions", "Override users are active", len(override_issues) == 0,
                ", ".join(override_issues[:3]) if override_issues else "All consistent")

        # Check trial users have trial_ends_at
        trial_issues = []
        for p in profiles:
            if p.get("subscription_status") == "trial" and p.get("is_trial") and not p.get("trial_ends_at"):
                trial_issues.append(p.get("email"))

        qa.test("Subscriptions", "Trial users have end dates", len(trial_issues) == 0,
                ", ".join(trial_issues[:3]) if trial_issues else "All consistent")

        # Check payment link exists
        payment_link_base = os.getenv("RADOM_PAYMENT_LINK_BASE")
        qa.test("Subscriptions", "Payment link base configured", bool(payment_link_base),
                payment_link_base[:40] + "..." if payment_link_base else "MISSING")

    # ── 5. Auth Functions ──

    try:
        from auth import check_subscription_access

        # Test with mock active profile
        mock_active = {"subscription_status": "active", "admin_override_active": False}
        has_access, msg, _ = check_subscription_access(mock_active)
        qa.test("Auth Logic", "Active user gets access", has_access, msg)

        # Test with mock banned profile
        mock_banned = {"subscription_status": "banned", "admin_override_active": False}
        has_access, msg, _ = check_subscription_access(mock_banned)
        qa.test("Auth Logic", "Banned user denied access", not has_access, msg)

        # Test with mock override profile
        mock_override = {"subscription_status": "pending", "admin_override_active": True}
        has_access, msg, _ = check_subscription_access(mock_override)
        qa.test("Auth Logic", "Override bypasses status", has_access, msg)

        # Test with mock overdue profile
        mock_overdue = {"subscription_status": "overdue", "admin_override_active": False}
        has_access, msg, _ = check_subscription_access(mock_overdue)
        qa.test("Auth Logic", "Overdue user denied access", not has_access, msg)

    except Exception as e:
        qa.test("Auth Logic", "Auth functions importable", False, str(e)[:80])

    # ── 6. Decision Engine ──

    try:
        from engine import get_decision
        qa.test("Engine", "engine.py importable", True)
    except ImportError as e:
        qa.test("Engine", "engine.py importable", False, str(e)[:80])

    try:
        # Test a basic preflop decision
        result = get_decision(
            hole_cards="AhKs",
            position="BTN",
            street="preflop",
            pot_size=3.0,
            stack_size=200.0,
            bb_size=2.0,
            num_players=6,
            action_history=[],
            board_cards="",
        )
        has_action = "action" in result or "recommendation" in result or "decision" in result
        qa.test("Engine", "Preflop decision returns result", has_action,
                str(result.get("action") or result.get("recommendation") or result.get("decision", ""))[:60])
    except Exception as e:
        qa.test("Engine", "Preflop decision returns result", False, str(e)[:80])

    try:
        # Test a postflop decision
        result = get_decision(
            hole_cards="AhKs",
            position="BTN",
            street="flop",
            pot_size=15.0,
            stack_size=185.0,
            bb_size=2.0,
            num_players=2,
            action_history=[],
            board_cards="As7h2d",
        )
        has_action = "action" in result or "recommendation" in result or "decision" in result
        qa.test("Engine", "Postflop decision returns result", has_action,
                str(result.get("action") or result.get("recommendation") or result.get("decision", ""))[:60])
    except Exception as e:
        qa.test("Engine", "Postflop decision returns result", False, str(e)[:80])

    # ── 7. DB Functions ──

    try:
        from db import (
            admin_grant_free_access, admin_revoke_free_access,
            admin_set_subscription_status, admin_ban_user, admin_unban_user,
            admin_extend_trial, admin_resend_payment_link,
        )
        qa.test("DB Functions", "Subscription admin functions importable", True)
    except ImportError as e:
        qa.test("DB Functions", "Subscription admin functions importable", False, str(e)[:80])

    try:
        from db import get_user_settings, get_player_stats, get_user_sessions
        qa.test("DB Functions", "Player data functions importable", True)
    except ImportError as e:
        qa.test("DB Functions", "Player data functions importable", False, str(e)[:80])

    # ── 8. Webhook Server ──

    webhook_key = os.getenv("RADOM_WEBHOOK_KEY")
    qa.test("Webhooks", "RADOM_WEBHOOK_KEY set (if webhook service)", bool(webhook_key) or os.getenv("APP_ENV") != "webhook",
            "Set" if webhook_key else "Not set (OK if this is the main app)")

    # ── 9. Page Imports ──

    page_modules = {
        "sidebar": "sidebar",
        "auth": "auth",
        "db": "db",
        "supabase_client": "supabase_client",
    }
    for display_name, module_name in page_modules.items():
        try:
            __import__(module_name)
            qa.test("Imports", f"{display_name} module loads", True)
        except Exception as e:
            qa.test("Imports", f"{display_name} module loads", False, str(e)[:80])

    # ── Render Results ──
    qa.render()

else:
    st.markdown("""
    <div style="text-align:center;padding:60px 0;">
        <div style="font-size:48px;margin-bottom:16px;">🧪</div>
        <div style="font-family:'JetBrains Mono',monospace;font-size:16px;color:#E0E0E0;margin-bottom:8px;">Ready to test</div>
        <div style="font-size:13px;color:rgba(255,255,255,0.3);">Click the button above to run all automated checks.</div>
    </div>
    """, unsafe_allow_html=True)


# =============================================================================
# FOOTER
# =============================================================================

st.markdown('<div style="height:1px;background:rgba(255,255,255,0.06);margin:32px 0 12px 0"></div>', unsafe_allow_html=True)
st.markdown('<div style="text-align:center;font-size:11px;color:rgba(255,255,255,0.15);font-family:JetBrains Mono,monospace;">Run before every deploy. All green = ship it.</div>', unsafe_allow_html=True)