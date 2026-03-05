# sidebar.py — Navigation Sidebar for Poker Decision App

import streamlit as st
from auth import sign_out


def render_sidebar():
    """
    Render the sidebar with navigation, session status, and user info.
    Call this at the top of every page after require_auth().
    """

    with st.sidebar:

        # ── Hide Streamlit's default page navigation ──
        st.markdown("""
        <style>
        [data-testid="stSidebarNav"] { display: none; }
        </style>
        """, unsafe_allow_html=True)

        # ── Branding ──
        st.markdown("""
        <div style="padding: 4px 0 8px 0;">
            <div style="width: 28px; height: 28px; background: #22c55e; border-radius: 6px; margin-bottom: 8px; display: flex; align-items: center; justify-content: center;">
                <span style="font-size: 14px; font-weight: 900; color: #0a0f1a; font-family: 'JetBrains Mono', monospace; letter-spacing: -1px;">N</span>
            </div>
            <div style="font-family: 'JetBrains Mono', monospace; font-size: 15px; font-weight: 700; letter-spacing: 0.05em; color: #E0E0E0;">NAMELESS POKER</div>
            <div style="font-size: 12px; color: rgba(255,255,255,0.35); margin-top: 4px;">""" + (st.session_state.get("email", "")) + ("  ·  🔐 Admin" if st.session_state.get("is_admin", False) else "") + """</div>
        </div>
        """, unsafe_allow_html=True)
        is_admin = st.session_state.get("is_admin", False)

        # ── Subscription Status ──
        subscription_status = st.session_state.get("subscription_status", "active")
        payment_link = st.session_state.get("payment_link_url")

        if subscription_status == "grace_period":
            st.markdown("""<div style="padding: 8px 0;">
<div style="font-size: 13px; color: rgba(255,255,255,0.4); font-weight: 600; margin-bottom: 6px;">⚠️ PAYMENT OVERDUE</div>
<div style="font-size: 13px; color: #FF5252; font-family: 'JetBrains Mono', monospace; font-weight: 600;">Update payment to keep access</div>
</div>""", unsafe_allow_html=True)
            if payment_link:
                st.markdown(f"""<a href="{payment_link}" target="_blank" style="display:block;text-align:center;padding:8px 12px;background:rgba(255,82,82,0.15);border:1px solid rgba(255,82,82,0.3);border-radius:6px;color:#FF5252;text-decoration:none;font-family:'JetBrains Mono',monospace;font-weight:600;font-size:13px;margin:6px 0 0 0;">💳 Update Payment</a>""", unsafe_allow_html=True)
            st.markdown("---")

        elif subscription_status == "trial":
            trial_ends = st.session_state.get("trial_ends_at")
            days_left = None
            if trial_ends:
                try:
                    from datetime import datetime, timezone
                    if isinstance(trial_ends, str):
                        trial_end = datetime.fromisoformat(trial_ends.replace("Z", "+00:00"))
                    else:
                        trial_end = trial_ends
                    now = datetime.now(timezone.utc)
                    days_left = max(0, (trial_end - now).days)
                except Exception:
                    days_left = None

            if days_left is not None and days_left <= 3:
                # Urgent — red/amber styling
                if days_left <= 1:
                    label = "TRIAL ENDS TODAY"
                    color = "#FF5252"
                    sub = "Subscribe now to keep your edge"
                else:
                    label = f"TRIAL · {days_left} DAYS LEFT"
                    color = "#FFB300"
                    sub = "Subscribe before your trial expires"

                st.markdown(f"""<div style="padding: 8px 0;">
<div style="font-size: 13px; color: rgba(255,255,255,0.4); font-weight: 600; margin-bottom: 6px;">⏰ {label}</div>
<div style="font-size: 13px; color: {color}; font-family: 'JetBrains Mono', monospace; font-weight: 600;">{sub}</div>
</div>""", unsafe_allow_html=True)
                if payment_link:
                    st.markdown(f"""<a href="{payment_link}" target="_blank" style="display:block;text-align:center;padding:8px 12px;background:rgba(105,240,174,0.1);border:1px solid rgba(105,240,174,0.25);border-radius:6px;color:#69F0AE;text-decoration:none;font-family:'JetBrains Mono',monospace;font-weight:600;font-size:13px;margin:6px 0 0 0;">💳 Subscribe — $299/mo</a>""", unsafe_allow_html=True)
                st.markdown("---")

            else:
                # Calm — subtle styling
                days_display = f"{days_left} days left" if days_left is not None else "Active"
                st.markdown(f"""<div style="padding: 8px 0;">
<div style="font-size: 13px; color: rgba(255,255,255,0.4); font-weight: 600; margin-bottom: 6px;">🎁 FREE TRIAL</div>
<div style="font-family: 'JetBrains Mono', monospace; font-size: 16px; font-weight: 700; color: #4BA3FF;">{days_display}</div>
</div>""", unsafe_allow_html=True)
                st.markdown("---")

        elif subscription_status == "active":
            # Active subscribers — clean, no clutter
            st.markdown("---")

        else:
            st.markdown("---")

        # ── Active Session ──
        active_session = st.session_state.get("active_session")

        if active_session:
            stakes_raw = active_session.get("stakes", "$1/$2")
            stakes = stakes_raw if stakes_raw.startswith("$") else f"${stakes_raw}"
            started_at = active_session.get("started_at", "")
            session_pl = st.session_state.get("session_pl", 0)
            hands_played = st.session_state.get("hands_played", 0)
            if hands_played == 0 and active_session.get("hands_played"):
                hands_played = int(active_session.get("hands_played", 0) or 0)
                st.session_state["hands_played"] = hands_played
            bb_size = float(active_session.get("bb_size", 2.0))

            # Duration
            duration_str = ""
            if started_at:
                try:
                    from datetime import datetime, timezone
                    start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                    now = datetime.now(timezone.utc)
                    duration = now - start
                    hours = int(duration.total_seconds() // 3600)
                    minutes = int((duration.total_seconds() % 3600) // 60)
                    duration_str = f"{hours}h {minutes}m"
                except Exception:
                    duration_str = ""

            # P/L formatting
            pl_sign = "+" if session_pl >= 0 else ""
            pl_display = f"{pl_sign}${session_pl:.2f}"
            pl_html_color = "#69F0AE" if session_pl >= 0 else "#FF5252"

            # BB/100 calculation
            bb100_html = ""
            if hands_played > 0 and bb_size > 0:
                bb_won = session_pl / bb_size
                bb_per_100 = (bb_won / hands_played) * 100
                bb100_html = f'<span style="color: rgba(255,255,255,0.15); margin: 0 6px;">·</span><span style="color: rgba(255,255,255,0.45);">{bb_per_100:+.1f} BB/100</span>'

            st.markdown(f"""<div style="padding: 8px 0;">
<div style="font-size: 13px; color: rgba(255,255,255,0.4); font-weight: 600; margin-bottom: 6px;">📍 ACTIVE SESSION</div>
<div style="font-family: 'JetBrains Mono', monospace; font-size: 16px; font-weight: 700; color: #E0E0E0;">{stakes} <span style="font-weight: 400; color: rgba(255,255,255,0.3);">·</span> <span style="font-size: 13px; color: rgba(255,255,255,0.5);">{duration_str}</span></div>
<div style="margin-top: 6px; font-size: 13px;"><span style="color: rgba(255,255,255,0.45);">P/L:</span> <span style="color: {pl_html_color}; font-family: 'JetBrains Mono', monospace; font-weight: 700;">{pl_display}</span><span style="color: rgba(255,255,255,0.15); margin: 0 6px;">·</span><span style="color: rgba(255,255,255,0.45);">Hands:</span> <span style="color: #E0E0E0; font-family: 'JetBrains Mono', monospace;">{hands_played}</span>{bb100_html}</div>
</div>""", unsafe_allow_html=True)

            if st.button("← Back to Session", use_container_width=True):
                st.switch_page("pages/01_Play_Session.py")

            st.markdown("---")

        # ── Bankroll Health ──
        current_bankroll = st.session_state.get("bankroll", 0) or st.session_state.get("current_bankroll", 0)
        default_stakes = st.session_state.get("default_stakes", "$1/$2")
        user_mode = st.session_state.get("risk_mode", "balanced") or st.session_state.get("user_mode", "balanced")

        if current_bankroll and current_bankroll > 0:
            stakes_to_buyin = {
                "$0.50/$1": 100,
                "$1/$2": 200,
                "$2/$5": 500,
                "$5/$10": 1000,
                "$10/$20": 2000,
                "$25/$50": 5000,
            }
            buyin = stakes_to_buyin.get(default_stakes, 200)
            buyins_available = current_bankroll / buyin

            mode_buyins = {
                "aggressive": 13,
                "balanced": 15,
                "conservative": 17,
            }
            required_buyins = mode_buyins.get(user_mode, 15)

            if buyins_available >= required_buyins:
                health_color = "#69F0AE"
                health_icon = "✅"
            elif buyins_available >= 12:
                health_color = "#FFB300"
                health_icon = "⚠️"
            else:
                health_color = "#FF5252"
                health_icon = "🔴"

            br_display = f"${current_bankroll:,.0f}"
            stakes_display = default_stakes if default_stakes.startswith("$") else f"${default_stakes}"
            mode_label = user_mode.capitalize()

            st.markdown(f"""<div style="padding: 8px 0;">
<div style="font-size: 13px; color: rgba(255,255,255,0.4); font-weight: 600; margin-bottom: 6px;">💰 BANKROLL</div>
<div style="font-family: 'JetBrains Mono', monospace; font-size: 16px; font-weight: 700; color: #E0E0E0;">{br_display} <span style="font-weight: 400; color: rgba(255,255,255,0.3);">·</span> <span style="font-size: 13px; color: rgba(255,255,255,0.5);">{mode_label}</span></div>
<div style="margin-top: 6px; font-size: 13px;"><span style="color: {health_color}; font-family: 'JetBrains Mono', monospace; font-weight: 600;">{health_icon} {buyins_available:.0f} buy-ins</span><span style="color: rgba(255,255,255,0.15); margin: 0 6px;">·</span><span style="color: rgba(255,255,255,0.45);">at {stakes_display}</span></div>
</div>""", unsafe_allow_html=True)

            st.markdown("---")

        # ── Navigation ──
        if st.button("🏠 Home", use_container_width=True):
            st.switch_page("app.py")

        if st.button("🎯 Play Session", use_container_width=True):
            st.switch_page("pages/01_Play_Session.py")

        if st.button("📜 Session History", use_container_width=True):
            st.switch_page("pages/02_Session_History.py")

        if st.button("📈 Player Stats", use_container_width=True):
            st.switch_page("pages/03_Player_Stats.py")

        if st.button("💰 Bankroll Health", use_container_width=True):
            st.switch_page("pages/04_Bankroll_Health.py")

        if st.button("⚙️ Settings", use_container_width=True):
            st.switch_page("pages/05_Settings.py")

        if st.button("❓ How It Works", use_container_width=True):
            st.switch_page("pages/06_How_It_Works.py")

        if st.button("📐 EV System", use_container_width=True):
            st.switch_page("pages/07_EV_System.py")

        if st.button("🎓 Master Your Play", use_container_width=True):
            st.switch_page("pages/08_Master_Your_Play.py")

        # Admin section
        if is_admin:
            st.markdown("---")
            st.caption("🔐 Admin")

            if st.button("👥 User Management", use_container_width=True):
                st.switch_page("pages/99_Admin.py")

            if st.button("🔧 System Health", use_container_width=True):
                st.switch_page("pages/97_System_Health.py")

            if st.button("✅ QA Checklist", use_container_width=True):
                st.switch_page("pages/98_QA_Checklist.py")

        # ── Help + Sign Out ──
        st.markdown("---")

        st.markdown(
            """
            <a href="https://discord.com/channels/1169748589522718770/1268729463500439553"
               target="_blank"
               style="
                 display:block;
                 text-align:center;
                 padding:8px 12px;
                 background:#1f2937;
                 border:1px solid #374151;
                 border-radius:6px;
                 color:white;
                 text-decoration:none;
                 font-weight:600;
                 margin:6px 0 10px 0;
               ">
               💬 Need Help?
            </a>
            """,
            unsafe_allow_html=True,
        )

        if st.button("🚪 Sign Out", use_container_width=True):
            sign_out()


def update_sidebar_session_info(session: dict, session_pl: float = 0):
    """Update session state with active session info for sidebar display."""
    st.session_state["active_session"] = session
    st.session_state["session_pl"] = session_pl


def clear_sidebar_session_info():
    """Clear active session info from sidebar."""
    st.session_state["active_session"] = None
    st.session_state["session_pl"] = 0


def update_sidebar_today_stats(profit_loss: float, sessions: int):
    """Update today's stats in sidebar."""
    st.session_state["today_pl"] = profit_loss
    st.session_state["today_sessions"] = sessions