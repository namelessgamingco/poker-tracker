# =============================================================================
# 05_Settings.py — Settings Page (Premium Dark Theme)
# =============================================================================

import streamlit as st
from datetime import datetime, timezone
from typing import Optional

st.set_page_config(
    page_title="Settings | Nameless Poker",
    page_icon="⚙️",
    layout="wide",
)

from auth import require_auth, sign_out
from sidebar import render_sidebar
from db import get_user_settings, update_user_settings, update_user_bankroll

# ---------- Auth Gate ----------
user = require_auth()
render_sidebar()
st.session_state["visited_settings"] = True

# Discord support ticket channel
DISCORD_SUPPORT_URL = "https://discord.com/channels/1169748589522718770/1268729463500439553"

# =============================================================================
# CONFIGURATION
# =============================================================================

STAKES_OPTIONS = [
    "$0.50/$1", "$1/$2", "$2/$5", "$5/$10", "$10/$20", "$25/$50",
]

RISK_MODES = {
    "aggressive": {
        "name": "Aggressive", "icon": "🔥", "color": "#FF5252",
        "buy_ins": 13, "stop_loss": 0.75, "stop_win": 3.0, "ror": "~0.28%",
        "desc": "Faster stake progression, tighter stop-loss. For experienced players comfortable with variance.",
    },
    "balanced": {
        "name": "Balanced", "icon": "⚖️", "color": "#4BA3FF",
        "buy_ins": 15, "stop_loss": 1.0, "stop_win": 3.0, "ror": "~0.08%",
        "desc": "Recommended for most players. Good balance of growth and bankroll protection.",
    },
    "conservative": {
        "name": "Conservative", "icon": "🛡️", "color": "#69F0AE",
        "buy_ins": 17, "stop_loss": 1.25, "stop_win": 3.0, "ror": "<0.01%",
        "desc": "Maximum protection, slower progression. Prioritizes bankroll preservation.",
    },
}

BUY_IN_MAP = {
    "$0.50/$1": 100, "$1/$2": 200, "$2/$5": 500,
    "$5/$10": 1000, "$10/$20": 2000, "$25/$50": 5000,
}

TABLE_CHECK_OPTIONS = [
    ("Every 15 minutes", 15),
    ("Every 20 minutes", 20),
    ("Every 30 minutes", 30),
    ("Every 45 minutes", 45),
    ("Every hour", 60),
    ("Off", 0),
]


# =============================================================================
# CSS
# =============================================================================

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');
.block-container { max-width: 1400px; }

.pg-hdr { text-align: left; margin-bottom: 32px; }
.pg-hdr h1 { font-family: Inter, sans-serif; font-size: 28px; font-weight: 700; color: #FFFFFF; margin: 0 0 4px 0; }
.pg-hdr p { font-family: Inter, sans-serif; font-size: 13px; color: rgba(255,255,255,0.35); margin: 0; }

.s-card {
    background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.06);
    border-radius: 12px; padding: 24px 28px; margin-bottom: 24px;
}
.s-title {
    font-family: Inter, sans-serif; font-size: 11px; font-weight: 600;
    color: rgba(255,255,255,0.30); text-transform: uppercase;
    letter-spacing: 0.08em; margin-bottom: 18px;
}
.s-subtitle {
    font-family: Inter, sans-serif; font-size: 12px;
    color: rgba(255,255,255,0.30); margin-bottom: 12px; line-height: 1.6;
}
.info-row {
    display: flex; justify-content: space-between; align-items: center;
    padding: 12px 0; border-bottom: 1px solid rgba(255,255,255,0.04);
}
.info-row:last-child { border-bottom: none; }
.info-label { font-family: Inter, sans-serif; font-size: 13px; color: rgba(255,255,255,0.45); }
.info-val { font-family: JetBrains Mono, monospace; font-size: 13px; color: #E0E0E0; font-weight: 500; }

.rm-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: 12px; }
.rm-card {
    background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.08);
    border-radius: 10px; padding: 18px 14px; text-align: center;
}
.rm-card.active { border-color: rgba(255,255,255,0.25); background: rgba(255,255,255,0.04); }
.rm-icon { font-size: 24px; margin-bottom: 6px; }
.rm-name { font-family: Inter, sans-serif; font-size: 14px; font-weight: 600; color: #E0E0E0; margin-bottom: 2px; }
.rm-bis { font-family: JetBrains Mono, monospace; font-size: 12px; font-weight: 600; margin-bottom: 6px; }
.rm-desc { font-family: Inter, sans-serif; font-size: 10px; color: rgba(255,255,255,0.25); line-height: 1.5; }
.rm-stats { margin-top: 8px; font-family: JetBrains Mono, monospace; font-size: 10px; color: rgba(255,255,255,0.20); }

.acct-badge {
    display: inline-block; padding: 3px 10px; border-radius: 12px;
    font-family: Inter, sans-serif; font-size: 11px; font-weight: 600;
}
.support-btn {
    display: block; padding: 14px 18px;
    background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.06);
    border-radius: 10px; text-decoration: none; color: #E0E0E0;
    transition: background 0.15s ease; margin-bottom: 10px;
}
.support-btn:hover { background: rgba(255,255,255,0.05); }

.setting-item { margin-bottom: 16px; padding-bottom: 16px; border-bottom: 1px solid rgba(255,255,255,0.04); }
.setting-item:last-child { border-bottom: none; margin-bottom: 0; padding-bottom: 0; }
.setting-name { font-family: Inter, sans-serif; font-size: 13px; font-weight: 600; color: #E0E0E0; }
.setting-why {
    font-family: Inter, sans-serif; font-size: 11px; color: rgba(255,255,255,0.25);
    line-height: 1.6; margin-top: 3px;
}
</style>
""", unsafe_allow_html=True)


# =============================================================================
# HELPERS
# =============================================================================

def get_user_id() -> Optional[str]:
    return st.session_state.get("user_db_id")

def get_user_email() -> str:
    return st.session_state.get("email") or st.session_state.get("user_email") or ""

def fmtc(v):
    if v is None: return "—"
    return f"${v:,.0f}" if v == int(v) else f"${v:,.2f}"

def get_subscription_display():
    """Build subscription status from auth session state."""
    status = st.session_state.get("subscription_status", "pending")
    override = st.session_state.get("admin_override_active", False)
    trial_ends = st.session_state.get("trial_ends_at")

    if override:
        return "Admin Access", "#69F0AE", "Complimentary access granted by admin", None

    if status == "active":
        return "Premium", "#8b5cf6", "$299/month", None

    if status == "trial":
        if trial_ends:
            try:
                if isinstance(trial_ends, str):
                    end = datetime.fromisoformat(trial_ends.replace("Z", "+00:00"))
                else:
                    end = trial_ends
                days_left = max(0, (end - datetime.now(timezone.utc)).days)
                return "Free Trial", "#FFB300", f"{days_left} days remaining", None
            except Exception:
                pass
        return "Free Trial", "#FFB300", "Active", None

    if status == "grace_period":
        return "Grace Period", "#FF5252", "Payment overdue — update payment to avoid lockout", st.session_state.get("payment_link_url")

    return "Inactive", "#FF5252", "No active subscription", st.session_state.get("payment_link_url")


def save_setting(user_id, key, value):
    """Save a single setting to DB and session state."""
    st.session_state[key] = value
    update_user_settings(user_id, {key: value})


# =============================================================================
# MAIN
# =============================================================================

def main():
    st.markdown("""
        <div class="pg-hdr">
            <h1>⚙️ Settings</h1>
            <p>Manage your bankroll, risk preferences, and account</p>
        </div>
    """, unsafe_allow_html=True)

    user_id = get_user_id()
    if not user_id:
        st.warning("Please log in to access settings.")
        return

    # Load settings from DB
    settings = get_user_settings(user_id)

    # Sync to session state
    current_bankroll = settings["bankroll"]
    current_mode = settings["risk_mode"] if settings["risk_mode"] in RISK_MODES else "balanced"
    current_stakes = settings["default_stakes"] if settings["default_stakes"] in STAKES_OPTIONS else "$1/$2"

    if not st.session_state.get("bankroll") and current_bankroll > 0:
        st.session_state["bankroll"] = current_bankroll
    if not st.session_state.get("risk_mode"):
        st.session_state["risk_mode"] = current_mode
    if not st.session_state.get("default_stakes"):
        st.session_state["default_stakes"] = current_stakes

    current_bankroll = st.session_state.get("bankroll", current_bankroll)
    current_mode = st.session_state.get("risk_mode", current_mode)
    current_stakes = st.session_state.get("default_stakes", current_stakes)
    mode = RISK_MODES[current_mode]
    bi = BUY_IN_MAP.get(current_stakes, 200)

    # =====================================================================
    col_left, col_right = st.columns([1.2, 0.8], gap="large")

    # =====================================================================
    # LEFT COLUMN
    # =====================================================================
    with col_left:

        # --- BANKROLL ---
        st.markdown('<div class="s-card"><div class="s-title">💰 Bankroll</div>', unsafe_allow_html=True)
        bc1, bc2 = st.columns([3, 1])
        with bc1:
            new_bankroll = st.number_input(
                "Current Bankroll ($)", min_value=0.0,
                value=float(current_bankroll), step=100.0, format="%.2f",
                key="settings_bankroll_input", label_visibility="collapsed",
            )
        with bc2:
            st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
            if st.button("Update", key="settings_update_br", use_container_width=True):
                st.session_state["bankroll"] = new_bankroll
                update_user_bankroll(user_id, new_bankroll)
                st.rerun()

        buy_ins_avail = current_bankroll / bi if bi > 0 else 0
        healthy = buy_ins_avail >= mode["buy_ins"]
        hc = "#69F0AE" if healthy else "#FFB300" if buy_ins_avail >= 10 else "#FF5252"
        hw = "Healthy" if healthy else "Low" if buy_ins_avail >= 10 else "Critical"
        st.markdown(
            f'<div style="font-family:JetBrains Mono,monospace;font-size:13px;color:{hc};margin:8px 0 4px 0;">'
            f'{buy_ins_avail:.1f} buy-ins at {current_stakes} · {hw}</div>'
            f'<div style="font-family:Inter,sans-serif;font-size:10px;color:rgba(255,255,255,0.20);">'
            f'{mode["name"]} mode requires {mode["buy_ins"]} buy-ins ({fmtc(mode["buy_ins"] * bi)})</div>',
            unsafe_allow_html=True
        )
        st.markdown('</div>', unsafe_allow_html=True)

        # --- RISK MODE ---
        st.markdown('<div class="s-card"><div class="s-title">🎯 Risk Mode</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="s-subtitle">'
            'Controls bankroll requirements and stop-loss limits. '
            'Does not change poker decisions — you get the same optimal plays in all modes.'
            '</div>', unsafe_allow_html=True
        )
        cards_html = '<div class="rm-grid">'
        for mk, mv in RISK_MODES.items():
            active = "active" if mk == current_mode else ""
            sl_d = fmtc(mv["stop_loss"] * bi)
            cards_html += (
                f'<div class="rm-card {active}">'
                f'<div class="rm-icon">{mv["icon"]}</div>'
                f'<div class="rm-name">{mv["name"]}</div>'
                f'<div class="rm-bis" style="color:{mv["color"]};">{mv["buy_ins"]} Buy-ins</div>'
                f'<div class="rm-desc">{mv["desc"]}</div>'
                f'<div class="rm-stats">Stop-loss: {mv["stop_loss"]} BI ({sl_d})<br>Risk of ruin: {mv["ror"]}</div>'
                f'</div>'
            )
        cards_html += '</div>'
        st.markdown(cards_html, unsafe_allow_html=True)

        mc1, mc2, mc3 = st.columns(3)
        for col, (mk, mv) in zip([mc1, mc2, mc3], RISK_MODES.items()):
            with col:
                is_current = (mk == current_mode)
                if st.button("✓ Selected" if is_current else "Select", key=f"settings_rm_{mk}",
                             disabled=is_current, use_container_width=True):
                    st.session_state["risk_mode"] = mk
                    save_setting(user_id, "risk_mode", mk)
                    st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        # --- DEFAULT STAKES ---
        st.markdown('<div class="s-card"><div class="s-title">🎰 Default Stakes</div>', unsafe_allow_html=True)
        st.markdown('<div class="s-subtitle">Pre-selected when starting a new session</div>', unsafe_allow_html=True)
        stakes_idx = STAKES_OPTIONS.index(current_stakes) if current_stakes in STAKES_OPTIONS else 1
        new_stakes = st.selectbox("Stakes", options=STAKES_OPTIONS, index=stakes_idx,
                                  key="settings_stakes_sel", label_visibility="collapsed")
        if new_stakes != current_stakes:
            st.session_state["default_stakes"] = new_stakes
            save_setting(user_id, "default_stakes", new_stakes)
        st.markdown('</div>', unsafe_allow_html=True)

        # --- SESSION ALERTS ---
        st.markdown('<div class="s-card"><div class="s-title">⏱️ Session Alerts</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="s-subtitle">'
            'These alerts protect your edge by warning you before fatigue, tilt, or overconfidence '
            'erode your decision quality. Every setting here is backed by the performance data on '
            'the EV System page — this is where the math becomes discipline.'
            '</div>', unsafe_allow_html=True
        )

        # -- Time Warning --
        st.markdown(
            '<div class="setting-item">'
            '<div class="setting-name">Session Time Warning</div>'
            '<div class="setting-why">'
            'Decision quality drops ~8% at 3 hours and ~15% at 4+ hours. '
            'You\'ll see a warning banner after this many hours to help you quit while you\'re still sharp.'
            '</div></div>', unsafe_allow_html=True
        )
        warning_hours = st.slider(
            "Warning at (hours)", min_value=1, max_value=6,
            value=int(settings.get("time_warning_hours", 3)),
            key="settings_time_warn",
        )
        if warning_hours != settings.get("time_warning_hours", 3):
            save_setting(user_id, "time_warning_hours", warning_hours)

        # -- Stop-Loss Alert --
        sa1, sa2 = st.columns([3, 1])
        with sa1:
            st.markdown(
                f'<div class="setting-item">'
                f'<div class="setting-name">Stop-Loss Alert</div>'
                f'<div class="setting-why">'
                f'Warns when session losses reach {mode["stop_loss"]} BI ({fmtc(mode["stop_loss"] * bi)}). '
                f'Continuing past this point significantly increases risk of tilt-driven decisions '
                f'that can turn a bad session into a catastrophic one.'
                f'</div></div>', unsafe_allow_html=True
            )
        with sa2:
            sl_alert = st.toggle("Enabled", value=settings.get("stop_loss_alerts_enabled", True),
                                 key="settings_sl_alert")
            if sl_alert != settings.get("stop_loss_alerts_enabled", True):
                save_setting(user_id, "stop_loss_alerts_enabled", sl_alert)

        # -- Stop-Win Alert --
        sw1, sw2 = st.columns([3, 1])
        with sw1:
            st.markdown(
                f'<div class="setting-item">'
                f'<div class="setting-name">Stop-Win Alert</div>'
                f'<div class="setting-why">'
                f'Alerts when you\'ve won {mode["stop_win"]} BI ({fmtc(mode["stop_win"] * bi)}). '
                f'Locking in a big win protects against overconfidence — '
                f'the urge to "keep going" after a heater is one of the biggest leaks in poker.'
                f'</div></div>', unsafe_allow_html=True
            )
        with sw2:
            sw_alert = st.toggle("Enabled", value=settings.get("stop_win_alerts_enabled", True),
                                 key="settings_sw_alert")
            if sw_alert != settings.get("stop_win_alerts_enabled", True):
                save_setting(user_id, "stop_win_alerts_enabled", sw_alert)

        # -- Table Check Reminder --
        st.markdown(
            '<div class="setting-item">'
            '<div class="setting-name">Table Check Reminder</div>'
            '<div class="setting-why">'
            'Periodic reminder to assess whether your table still has enough recreational players. '
            'A good table is worth +2-3 BB/100 over a tough one — '
            'this reminder ensures you never grind a dead table by accident.'
            '</div><div style="height:8px"></div></div>', unsafe_allow_html=True
        )
        current_interval = settings.get("table_check_interval", 20)
        interval_labels = [opt[0] for opt in TABLE_CHECK_OPTIONS]
        interval_values = [opt[1] for opt in TABLE_CHECK_OPTIONS]
        try:
            tc_idx = interval_values.index(current_interval)
        except ValueError:
            tc_idx = 1
        new_interval_label = st.selectbox("Frequency", options=interval_labels, index=tc_idx,
                                          key="settings_tc_freq", label_visibility="collapsed")
        new_interval = interval_values[interval_labels.index(new_interval_label)]
        if new_interval != current_interval:
            save_setting(user_id, "table_check_interval", new_interval)

        st.markdown('</div>', unsafe_allow_html=True)

    # =====================================================================
    # RIGHT COLUMN
    # =====================================================================
    with col_right:

        # --- ACCOUNT ---
        st.markdown('<div class="s-card"><div class="s-title">👤 Account</div>', unsafe_allow_html=True)
        email = get_user_email()
        sub_name, sub_color, sub_detail, payment_link = get_subscription_display()

        st.markdown(
            f'<div class="info-row"><div class="info-label">Email</div>'
            f'<div class="info-val">{email or "Not available"}</div></div>',
            unsafe_allow_html=True
        )
        st.markdown(
            f'<div class="info-row"><div class="info-label">Subscription</div>'
            f'<div class="info-val">'
            f'<span class="acct-badge" style="background:{sub_color};color:#fff;">{sub_name}</span>'
            f'</div></div>', unsafe_allow_html=True
        )
        if sub_detail:
            st.markdown(
                f'<div style="font-family:Inter,sans-serif;font-size:11px;color:rgba(255,255,255,0.25);'
                f'padding:4px 0 8px 0;">{sub_detail}</div>', unsafe_allow_html=True
            )
        if payment_link and sub_name not in ("Premium", "Admin Access"):
            st.link_button("Subscribe Now", payment_link, type="primary", use_container_width=True)

        st.markdown(
            f'<div class="info-row"><div class="info-label">Risk Mode</div>'
            f'<div class="info-val" style="color:{mode["color"]};">{mode["icon"]} {mode["name"]}</div></div>',
            unsafe_allow_html=True
        )
        st.markdown(
            f'<div class="info-row"><div class="info-label">Default Stakes</div>'
            f'<div class="info-val">{current_stakes}</div></div>',
            unsafe_allow_html=True
        )
        st.markdown(
            f'<div class="info-row"><div class="info-label">Bankroll</div>'
            f'<div class="info-val" style="color:#69F0AE;">{fmtc(current_bankroll)}</div></div>',
            unsafe_allow_html=True
        )
        st.markdown('</div>', unsafe_allow_html=True)

        # --- SUPPORT ---
        st.markdown('<div class="s-card"><div class="s-title">💬 Support</div>', unsafe_allow_html=True)
        st.markdown(f"""
            <a href="{DISCORD_SUPPORT_URL}" target="_blank" class="support-btn">
                <div style="display:flex;align-items:center;gap:12px;">
                    <div style="font-size:20px;">💬</div>
                    <div>
                        <div style="font-family:Inter,sans-serif;font-size:14px;font-weight:600;color:#E0E0E0;">
                            Open a Support Ticket</div>
                        <div style="font-family:Inter,sans-serif;font-size:11px;color:rgba(255,255,255,0.25);margin-top:2px;">
                            Get help on Discord — we typically respond within a few hours</div>
                    </div>
                    <div style="margin-left:auto;color:rgba(255,255,255,0.15);">→</div>
                </div>
            </a>
        """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # --- SIGN OUT ---
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        if st.button("🚪  Sign Out", key="settings_sign_out", use_container_width=True):
            sign_out()
            st.rerun()
        st.markdown(
            '<div style="font-family:Inter,sans-serif;font-size:10px;color:rgba(255,255,255,0.12);'
            'text-align:center;margin-top:24px;">Nameless Poker v1.0</div>',
            unsafe_allow_html=True
        )


if __name__ == "__main__":
    main()