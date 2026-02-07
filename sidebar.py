# sidebar.py — Navigation Sidebar for Poker Decision App

import streamlit as st
from auth import sign_out


def render_sidebar():
    """
    Render the sidebar with navigation, session status, and user info.
    
    Call this at the top of every page after require_auth().
    """
    
    with st.sidebar:
        # ---------- Branding ----------
        st.markdown("## 🃏 Poker Decision App")
        
        # ---------- User Info ----------
        email = st.session_state.get("email", "")
        role = st.session_state.get("role", "player")
        is_admin = st.session_state.get("is_admin", False)
        
        # Show role badge for admin
        if is_admin:
            st.caption(f"👤 {email}")
            st.caption("🔐 Admin")
        else:
            st.caption(f"👤 {email}")
        
        # ---------- Subscription Warning ----------
        subscription_status = st.session_state.get("subscription_status", "active")
        
        if subscription_status == "grace_period":
            st.warning("⚠️ Payment overdue", icon="⚠️")
        elif subscription_status == "trial":
            trial_ends = st.session_state.get("trial_ends_at")
            if trial_ends:
                try:
                    from datetime import datetime, timezone
                    if isinstance(trial_ends, str):
                        trial_end = datetime.fromisoformat(trial_ends.replace("Z", "+00:00"))
                    else:
                        trial_end = trial_ends
                    now = datetime.now(timezone.utc)
                    days_left = max(0, (trial_end - now).days)
                    if days_left <= 1:
                        st.warning(f"⏰ Trial ends today!", icon="⏰")
                    elif days_left <= 3:
                        st.warning(f"⏰ {days_left} days left in trial", icon="⏰")
                    else:
                        st.info(f"🎁 {days_left} days left in trial", icon="🎁")
                except Exception:
                    st.info("🎁 Free trial active", icon="🎁")
            else:
                st.info("🎁 Free trial active", icon="🎁")
        
        st.markdown("---")
        
        # ---------- Active Session Status ----------
        # This will be populated by Play Session page when a session is active
        active_session = st.session_state.get("active_session")
        
        if active_session:
            st.markdown("### 📍 Active Session")
            
            stakes = active_session.get("stakes", "$1/$2")
            started_at = active_session.get("started_at", "")
            
            st.markdown(f"**Stakes:** {stakes}")
            
            # Calculate session duration
            if started_at:
                try:
                    from datetime import datetime, timezone
                    start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                    now = datetime.now(timezone.utc)
                    duration = now - start
                    hours = int(duration.total_seconds() // 3600)
                    minutes = int((duration.total_seconds() % 3600) // 60)
                    st.markdown(f"**Duration:** {hours}h {minutes}m")
                except Exception:
                    pass
            
            # Session P/L (updated by Play Session page)
            session_pl = st.session_state.get("session_pl", 0)
            pl_color = "green" if session_pl >= 0 else "red"
            pl_sign = "+" if session_pl >= 0 else ""
            st.markdown(f"**Session P/L:** :{pl_color}[{pl_sign}${session_pl:.2f}]")
            
            # Quick link to Play Session
            if st.button("← Back to Session", use_container_width=True):
                st.switch_page("pages/01_Play_Session.py")
            
            st.markdown("---")
        
        # ---------- Quick Stats ----------
        st.markdown("### 📊 Today")
        
        today_pl = st.session_state.get("today_pl", 0)
        today_sessions = st.session_state.get("today_sessions", 0)
        
        col1, col2 = st.columns(2)
        with col1:
            pl_color = "green" if today_pl >= 0 else "red"
            pl_sign = "+" if today_pl >= 0 else ""
            st.metric("P/L", f"{pl_sign}${today_pl:.2f}")
        with col2:
            st.metric("Sessions", today_sessions)
        
        st.markdown("---")
        
        # ---------- Bankroll Health ----------
        current_bankroll = st.session_state.get("current_bankroll", 0)
        default_stakes = st.session_state.get("default_stakes", "$1/$2")
        user_mode = st.session_state.get("user_mode", "balanced")
        
        if current_bankroll and current_bankroll > 0:
            st.markdown("### 💰 Bankroll")
            st.markdown(f"**${current_bankroll:,.2f}**")
            
            # Calculate buy-ins available
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
            
            # Mode requirements
            mode_buyins = {
                "aggressive": 13,
                "balanced": 15,
                "conservative": 17,
            }
            required_buyins = mode_buyins.get(user_mode, 15)
            
            # Health indicator
            if buyins_available >= required_buyins:
                st.markdown(f"✅ {buyins_available:.1f} buy-ins ({default_stakes})")
            elif buyins_available >= 12:
                st.markdown(f"⚠️ {buyins_available:.1f} buy-ins ({default_stakes})")
                st.caption("Consider moving down")
            else:
                st.markdown(f"🔴 {buyins_available:.1f} buy-ins ({default_stakes})")
                st.caption("Move down recommended")
            
            st.markdown("---")
        
        # ---------- Navigation ----------
        st.markdown("### Navigation")
        
        # Main pages
        if st.button("🎯 Play Session", use_container_width=True):
            st.switch_page("pages/01_Play_Session.py")
        
        if st.button("📜 Session History", use_container_width=True):
            st.switch_page("pages/02_Session_History.py")
        
        if st.button("📈 Player Stats", use_container_width=True):
            st.switch_page("pages/03_Player_Stats.py")
        
        if st.button("💰 Bankroll Health", use_container_width=True):
            st.switch_page("pages/04_Bankroll_Health.py")
        
        # Expandable section for less-used pages
        with st.expander("More", expanded=False):
            if st.button("⚙️ Settings", use_container_width=True):
                st.switch_page("pages/05_Settings.py")
            
            if st.button("❓ How It Works", use_container_width=True):
                st.switch_page("pages/06_How_It_Works.py")
            
            if st.button("📐 EV System", use_container_width=True):
                st.switch_page("pages/07_EV_System.py")
            
            if st.button("🎓 Master Your Play", use_container_width=True):
                st.switch_page("pages/08_Master_Your_Play.py")
        
        # Admin section (only visible to admins)
        if is_admin:
            st.markdown("---")
            st.markdown("### 🔐 Admin")
            
            if st.button("👥 User Management", use_container_width=True):
                st.switch_page("pages/99_Admin.py")
            
            if st.button("🔧 System Health", use_container_width=True):
                st.switch_page("pages/97_System_Health.py")
        
        # ---------- Need Help ----------
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
        
        # ---------- Sign Out ----------
        if st.button("🚪 Sign Out", use_container_width=True):
            sign_out()


def update_sidebar_session_info(session: dict, session_pl: float = 0):
    """
    Update session state with active session info for sidebar display.
    
    Call this from Play Session page when session is active.
    """
    st.session_state["active_session"] = session
    st.session_state["session_pl"] = session_pl


def clear_sidebar_session_info():
    """
    Clear active session info from sidebar.
    
    Call this when session ends.
    """
    st.session_state["active_session"] = None
    st.session_state["session_pl"] = 0


def update_sidebar_today_stats(profit_loss: float, sessions: int):
    """
    Update today's stats in sidebar.
    
    Call this when stats are loaded.
    """
    st.session_state["today_pl"] = profit_loss
    st.session_state["today_sessions"] = sessions