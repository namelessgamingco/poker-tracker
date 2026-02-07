# =============================================================================
# 05_Settings.py — Settings Page for Poker Decision App
# =============================================================================
#
# DESIGN PRINCIPLES:
# - Minimal settings (only what's essential)
# - Clean, organized sections
# - Immediate feedback on changes
# - No overwhelming options
#
# SECTIONS:
# 1. Bankroll & Risk - Core financial settings
# 2. Session Preferences - Alerts and reminders
# 3. Account - Email, subscription, sign out
# 4. Support - Help and documentation links
#
# =============================================================================

import streamlit as st
from datetime import datetime, timezone
from typing import Optional

st.set_page_config(
    page_title="Settings | Poker Decision App",
    page_icon="⚙️",
    layout="wide",
)

from auth import require_auth, sign_out
from sidebar import render_sidebar
from db import update_user_settings, get_user_settings

# ---------- Auth Gate ----------
user = require_auth()
render_sidebar()


# =============================================================================
# CONFIGURATION
# =============================================================================

STAKES_OPTIONS = [
    "$0.50/$1",
    "$1/$2",
    "$2/$5",
    "$5/$10",
    "$10/$20",
    "$25/$50",
]

RISK_MODES = {
    "aggressive": {
        "name": "Aggressive",
        "emoji": "🔥",
        "buy_ins": 13,
        "description": "Higher risk, faster stake progression. For experienced players comfortable with variance.",
    },
    "balanced": {
        "name": "Balanced",
        "emoji": "⚖️",
        "buy_ins": 15,
        "description": "Recommended for most players. Good balance of growth and bankroll protection.",
    },
    "conservative": {
        "name": "Conservative",
        "emoji": "🛡️",
        "buy_ins": 17,
        "description": "Lower risk, slower progression. Prioritizes bankroll preservation.",
    },
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
# CUSTOM CSS
# =============================================================================

st.markdown("""
<style>
/* Settings sections */
.settings-section {
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    padding: 24px;
    margin-bottom: 24px;
}
.settings-section-title {
    font-size: 18px;
    font-weight: 600;
    color: #111827;
    margin-bottom: 20px;
    display: flex;
    align-items: center;
    gap: 8px;
}

/* Setting row */
.setting-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 0;
    border-bottom: 1px solid #f3f4f6;
}
.setting-row:last-child {
    border-bottom: none;
}
.setting-label {
    font-weight: 500;
    color: #374151;
}
.setting-description {
    font-size: 13px;
    color: #6b7280;
    margin-top: 4px;
}
.setting-value {
    color: #111827;
    font-weight: 500;
}

/* Risk mode cards */
.risk-mode-card {
    border: 2px solid #e5e7eb;
    border-radius: 12px;
    padding: 16px;
    text-align: center;
    cursor: pointer;
    transition: all 0.2s ease;
}
.risk-mode-card.selected {
    border-color: #3b82f6;
    background: #eff6ff;
}
.risk-mode-card:hover {
    border-color: #9ca3af;
}
.risk-mode-emoji {
    font-size: 32px;
    margin-bottom: 8px;
}
.risk-mode-name {
    font-size: 16px;
    font-weight: 600;
    margin-bottom: 4px;
}
.risk-mode-bis {
    font-size: 14px;
    color: #3b82f6;
    font-weight: 600;
    margin-bottom: 8px;
}
.risk-mode-desc {
    font-size: 12px;
    color: #6b7280;
}

/* Account info */
.account-info {
    background: #f8fafc;
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 16px;
}
.account-label {
    font-size: 12px;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.account-value {
    font-size: 16px;
    font-weight: 500;
    color: #111827;
    margin-top: 4px;
}

/* Subscription badge */
.subscription-badge {
    display: inline-block;
    background: linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%);
    color: white;
    padding: 4px 12px;
    border-radius: 16px;
    font-size: 13px;
    font-weight: 600;
}

/* Success message */
.success-message {
    background: #f0fdf4;
    border: 1px solid #22c55e;
    color: #166534;
    padding: 12px 16px;
    border-radius: 8px;
    margin: 16px 0;
    display: flex;
    align-items: center;
    gap: 8px;
}

/* Support links */
.support-link {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 16px;
    background: #f8fafc;
    border-radius: 8px;
    margin-bottom: 12px;
    text-decoration: none;
    color: #374151;
    transition: background 0.2s ease;
}
.support-link:hover {
    background: #f1f5f9;
}
.support-link-icon {
    font-size: 24px;
}
.support-link-text {
    flex: 1;
}
.support-link-title {
    font-weight: 500;
    color: #111827;
}
.support-link-desc {
    font-size: 13px;
    color: #6b7280;
}
</style>
""", unsafe_allow_html=True)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_user_id() -> Optional[str]:
    """Get current user's database ID from session state."""
    return st.session_state.get("user_db_id")


def get_user_email() -> str:
    """Get current user's email from session state."""
    return st.session_state.get("user_email", "Not available")


def format_money(amount: float) -> str:
    """Format money value."""
    if amount is None:
        return "—"
    return f"${amount:,.2f}"


def save_settings_to_session(key: str, value):
    """Save a setting to session state."""
    st.session_state[key] = value


def get_setting(key: str, default=None):
    """Get a setting from session state."""
    return st.session_state.get(key, default)


# =============================================================================
# RENDER FUNCTIONS
# =============================================================================

def render_bankroll_risk_section():
    """Render Bankroll & Risk settings section."""
    
    st.markdown("### 💰 Bankroll & Risk")
    
    # Current Bankroll
    current_bankroll = get_setting("bankroll", 0.0)
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        new_bankroll = st.number_input(
            "Current Bankroll",
            min_value=0.0,
            value=float(current_bankroll),
            step=100.0,
            format="%.2f",
            help="Your total poker bankroll available for play",
            key="settings_bankroll"
        )
    
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Update", key="update_bankroll", use_container_width=True):
            save_settings_to_session("bankroll", new_bankroll)
            st.success("Bankroll updated!")
    
    st.markdown("---")
    
    # Risk Mode
    st.markdown("**Risk Mode**")
    st.caption("Determines how many buy-ins you need at each stake level")
    
    current_risk_mode = get_setting("risk_mode", "balanced")
    
    cols = st.columns(3)
    
    for i, (mode_key, mode) in enumerate(RISK_MODES.items()):
        with cols[i]:
            is_selected = mode_key == current_risk_mode
            
            # Card container
            container = st.container()
            with container:
                st.markdown(f"""
                    <div class="risk-mode-card {'selected' if is_selected else ''}">
                        <div class="risk-mode-emoji">{mode['emoji']}</div>
                        <div class="risk-mode-name">{mode['name']}</div>
                        <div class="risk-mode-bis">{mode['buy_ins']} Buy-ins</div>
                        <div class="risk-mode-desc">{mode['description']}</div>
                    </div>
                """, unsafe_allow_html=True)
                
                if st.button(
                    "Selected" if is_selected else "Select",
                    key=f"select_{mode_key}",
                    disabled=is_selected,
                    use_container_width=True
                ):
                    save_settings_to_session("risk_mode", mode_key)
                    st.rerun()
    
    st.markdown("---")
    
    # Default Stakes
    current_stakes = get_setting("default_stakes", "$1/$2")
    stakes_index = STAKES_OPTIONS.index(current_stakes) if current_stakes in STAKES_OPTIONS else 1
    
    new_stakes = st.selectbox(
        "Default Stakes",
        options=STAKES_OPTIONS,
        index=stakes_index,
        help="Pre-selected stakes when starting a new session",
        key="settings_default_stakes"
    )
    
    if new_stakes != current_stakes:
        save_settings_to_session("default_stakes", new_stakes)


def render_session_preferences_section():
    """Render Session Preferences section."""
    
    st.markdown("### ⏱️ Session Preferences")
    
    # Time Alerts
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("**Session Time Alerts**")
        st.caption("Get warned when you've been playing too long")
    
    with col2:
        time_alerts = st.toggle(
            "Enabled",
            value=get_setting("time_alerts_enabled", True),
            key="settings_time_alerts"
        )
        save_settings_to_session("time_alerts_enabled", time_alerts)
    
    if time_alerts:
        warning_hours = st.slider(
            "Warning at (hours)",
            min_value=1,
            max_value=6,
            value=get_setting("time_warning_hours", 3),
            help="You'll receive a warning after playing this many hours",
            key="settings_warning_hours"
        )
        save_settings_to_session("time_warning_hours", warning_hours)
    
    st.markdown("---")
    
    # Stop-Loss/Win Alerts
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("**Stop-Loss Alerts**")
        st.caption("Alert when you hit your stop-loss threshold")
    
    with col2:
        stop_loss_alerts = st.toggle(
            "Enabled",
            value=get_setting("stop_loss_alerts_enabled", True),
            key="settings_stop_loss_alerts_enabled"
        )
        save_settings_to_session("stop_loss_alerts_enabled", stop_loss_alerts)
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("**Stop-Win Alerts**")
        st.caption("Alert when you hit your stop-win threshold")
    
    with col2:
        stop_win_alerts = st.toggle(
            "Enabled",
            value=get_setting("stop_win_alerts_enabled", True),
            key="settings_stop_win_alerts_enabled"
        )
        save_settings_to_session("stop_win_alerts_enabled", stop_win_alerts)
    
    st.markdown("---")
    
    # Table Check Reminder
    st.markdown("**Table Check Reminder**")
    st.caption("Periodic reminder to assess table quality")
    
    current_interval = get_setting("table_check_interval", 20)
    
    # Find current selection
    interval_labels = [opt[0] for opt in TABLE_CHECK_OPTIONS]
    interval_values = [opt[1] for opt in TABLE_CHECK_OPTIONS]
    
    try:
        current_index = interval_values.index(current_interval)
    except ValueError:
        current_index = 1  # Default to 20 minutes
    
    new_interval_label = st.selectbox(
        "Reminder frequency",
        options=interval_labels,
        index=current_index,
        key="settings_table_check"
    )
    
    new_interval = interval_values[interval_labels.index(new_interval_label)]
    save_settings_to_session("table_check_interval", new_interval)


def render_account_section():
    """Render Account section."""
    
    st.markdown("### 👤 Account")
    
    # Email
    email = get_user_email()
    st.markdown(f"""
        <div class="account-info">
            <div class="account-label">Email</div>
            <div class="account-value">{email}</div>
        </div>
    """, unsafe_allow_html=True)
    
    # Subscription
    # In production, this would come from the database
    subscription_status = "Premium"
    subscription_price = "$299/month"
    next_billing = "March 5, 2026"  # Would be calculated from actual data
    
    st.markdown(f"""
        <div class="account-info">
            <div class="account-label">Subscription</div>
            <div class="account-value">
                <span class="subscription-badge">{subscription_status}</span>
                <span style="color: #6b7280; margin-left: 8px;">{subscription_price}</span>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown(f"""
        <div class="account-info">
            <div class="account-label">Next Billing Date</div>
            <div class="account-value">{next_billing}</div>
        </div>
    """, unsafe_allow_html=True)
    
    # Sign Out
    st.markdown("---")
    
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col2:
        if st.button("🚪 Sign Out", use_container_width=True, type="secondary"):
            sign_out()
            st.rerun()


def render_support_section():
    """Render Support section."""
    
    st.markdown("### 🆘 Support")
    
    # Contact Support
    st.markdown("""
        <a href="mailto:support@pokerapp.com" class="support-link" style="text-decoration: none;">
            <div class="support-link-icon">📧</div>
            <div class="support-link-text">
                <div class="support-link-title">Contact Support</div>
                <div class="support-link-desc">Get help with any issues or questions</div>
            </div>
            <div style="color: #9ca3af;">→</div>
        </a>
    """, unsafe_allow_html=True)
    
    # Documentation
    st.markdown("""
        <a href="#" class="support-link" style="text-decoration: none;">
            <div class="support-link-icon">📚</div>
            <div class="support-link-text">
                <div class="support-link-title">Documentation</div>
                <div class="support-link-desc">Learn how to use the app effectively</div>
            </div>
            <div style="color: #9ca3af;">→</div>
        </a>
    """, unsafe_allow_html=True)
    
    # Discord Community
    st.markdown("""
        <a href="#" class="support-link" style="text-decoration: none;">
            <div class="support-link-icon">💬</div>
            <div class="support-link-text">
                <div class="support-link-title">Discord Community</div>
                <div class="support-link-desc">Connect with other players</div>
            </div>
            <div style="color: #9ca3af;">→</div>
        </a>
    """, unsafe_allow_html=True)


def render_danger_zone():
    """Render danger zone with destructive actions."""
    
    with st.expander("⚠️ Danger Zone", expanded=False):
        st.warning("These actions cannot be undone.")
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.markdown("**Reset All Settings**")
            st.caption("Reset all settings to their default values")
        
        with col2:
            if st.button("Reset", type="secondary", key="reset_settings"):
                # Reset to defaults
                defaults = {
                    "bankroll": 0.0,
                    "risk_mode": "balanced",
                    "default_stakes": "$1/$2",
                    "time_alerts_enabled": True,
                    "time_warning_hours": 3,
                    "stop_loss_alerts_enabled": True,
                    "stop_win_alerts_enabled": True,
                    "table_check_interval": 20,
                }
                for key, value in defaults.items():
                    st.session_state[key] = value
                st.success("Settings reset to defaults")
                st.rerun()
        
        st.markdown("---")
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.markdown("**Clear Session History**")
            st.caption("Delete all your session data (cannot be undone)")
        
        with col2:
            if st.button("Clear", type="secondary", key="clear_history"):
                st.error("This feature requires confirmation. Contact support.")


# =============================================================================
# MAIN PAGE
# =============================================================================

def main():
    """Main render function for Settings page."""
    
    st.title("⚙️ Settings")
    st.caption("Manage your preferences and account")
    
    user_id = get_user_id()
    
    if not user_id:
        st.warning("Please log in to access settings.")
        return
    
    # Two-column layout for larger screens
    col1, col2 = st.columns([1, 1])
    
    with col1:
        render_bankroll_risk_section()
        render_session_preferences_section()
    
    with col2:
        render_account_section()
        render_support_section()
        render_danger_zone()


if __name__ == "__main__":
    main()