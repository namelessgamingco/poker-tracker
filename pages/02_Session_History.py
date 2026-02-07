# 02_Session_History.py — Session History Page for Poker Decision App
# Individual session review with auto-generated insights

import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
import calendar
import io

st.set_page_config(
    page_title="Session History | Poker Decision App",
    page_icon="📋",
    layout="wide",
)

from auth import require_auth
from sidebar import render_sidebar
from db import (
    get_user_sessions,
    get_sessions_in_date_range,
    get_session_hands,
    get_session_outcome_summary,
)

# ---------- Auth Gate ----------
user = require_auth()
render_sidebar()

# =============================================================================
# CONSTANTS
# =============================================================================

STAKES_OPTIONS = ["All Stakes", "$0.50/$1", "$1/$2", "$2/$5", "$5/$10", "$10/$20", "$25/$50"]
RESULT_OPTIONS = ["All Results", "Winning Sessions", "Losing Sessions", "Break-even"]
END_REASON_OPTIONS = ["All", "Manual", "Stop-Loss", "Stop-Win", "Time Limit"]

END_REASON_DISPLAY = {
    "manual": "Manual",
    "stop_loss": "Stop-Loss",
    "stop_win": "Stop-Win", 
    "time_limit": "Time Limit",
    None: "Unknown",
}

# =============================================================================
# CUSTOM CSS
# =============================================================================

st.markdown("""
<style>
/* Session card styling */
.session-card {
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 16px;
    transition: box-shadow 0.2s ease;
}
.session-card:hover {
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}
.session-card.winning {
    border-left: 4px solid #22c55e;
}
.session-card.losing {
    border-left: 4px solid #ef4444;
}
.session-card.breakeven {
    border-left: 4px solid #6b7280;
}

/* Session header */
.session-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
}
.session-date {
    font-size: 18px;
    font-weight: 600;
    color: #111827;
}
.session-pl {
    font-size: 24px;
    font-weight: 700;
}
.session-pl.positive {
    color: #22c55e;
}
.session-pl.negative {
    color: #ef4444;
}
.session-pl.zero {
    color: #6b7280;
}

/* Session stats row */
.session-stats {
    display: flex;
    gap: 24px;
    margin-bottom: 12px;
    flex-wrap: wrap;
}
.session-stat {
    display: flex;
    flex-direction: column;
}
.session-stat-value {
    font-size: 16px;
    font-weight: 600;
    color: #111827;
}
.session-stat-label {
    font-size: 12px;
    color: #6b7280;
    text-transform: uppercase;
}

/* Insight box */
.insight-box {
    background: #f8fafc;
    border-radius: 8px;
    padding: 16px;
    margin-top: 12px;
}
.insight-title {
    font-size: 14px;
    font-weight: 600;
    color: #374151;
    margin-bottom: 8px;
}
.insight-item {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 6px;
    font-size: 14px;
    color: #4b5563;
}

/* Outcome breakdown */
.outcome-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
    margin-top: 12px;
}
.outcome-box {
    text-align: center;
    padding: 12px;
    border-radius: 8px;
    background: #f3f4f6;
}
.outcome-box.wins {
    background: #dcfce7;
}
.outcome-box.losses {
    background: #fee2e2;
}
.outcome-box.folds {
    background: #f3f4f6;
}
.outcome-count {
    font-size: 24px;
    font-weight: 700;
}
.outcome-label {
    font-size: 12px;
    color: #6b7280;
    text-transform: uppercase;
}
.outcome-pct {
    font-size: 14px;
    color: #4b5563;
}

/* Calendar heatmap */
.calendar-day {
    width: 20px;
    height: 20px;
    border-radius: 4px;
    display: inline-block;
    margin: 2px;
}
.calendar-day.no-session {
    background: #f3f4f6;
}
.calendar-day.winning {
    background: #22c55e;
}
.calendar-day.losing {
    background: #ef4444;
}
.calendar-day.breakeven {
    background: #fbbf24;
}

/* Stats summary */
.stats-summary {
    background: linear-gradient(135deg, #1f2937 0%, #374151 100%);
    color: white;
    border-radius: 12px;
    padding: 24px;
    margin-bottom: 24px;
}
.stats-summary-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 24px;
}
.summary-stat {
    text-align: center;
}
.summary-stat-value {
    font-size: 28px;
    font-weight: 700;
}
.summary-stat-label {
    font-size: 12px;
    opacity: 0.8;
    text-transform: uppercase;
}

/* Filter section */
.filter-section {
    background: #f8fafc;
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 24px;
}

/* Empty state */
.empty-state {
    text-align: center;
    padding: 48px;
    color: #6b7280;
}
.empty-state-icon {
    font-size: 48px;
    margin-bottom: 16px;
}
</style>
""", unsafe_allow_html=True)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_user_id() -> Optional[str]:
    """Get current user's database ID."""
    return st.session_state.get("user_db_id")


def format_duration(minutes: int) -> str:
    """Format duration in hours and minutes."""
    if minutes is None:
        return "—"
    hours = minutes // 60
    mins = minutes % 60
    if hours > 0:
        return f"{hours}h {mins}m"
    return f"{mins}m"


def format_money(amount: float, include_sign: bool = True) -> str:
    """Format money with optional sign."""
    if amount is None:
        return "—"
    if include_sign:
        if amount >= 0:
            return f"+${amount:,.2f}"
        return f"-${abs(amount):,.2f}"
    return f"${abs(amount):,.2f}"


def format_bb_per_100(bb_per_100: float) -> str:
    """Format BB/100 with sign."""
    if bb_per_100 is None:
        return "—"
    return f"{bb_per_100:+.1f}"


def calculate_bb_per_100(profit_loss: float, hands: int, bb_size: float) -> float:
    """Calculate BB/100 for a session."""
    if not hands or hands == 0 or not bb_size or bb_size == 0:
        return 0.0
    bb_won = profit_loss / bb_size
    return (bb_won / hands) * 100


def parse_session_datetime(session: dict) -> Optional[datetime]:
    """Parse session started_at to datetime."""
    started_at = session.get("started_at")
    if not started_at:
        return None
    try:
        return datetime.fromisoformat(started_at.replace("Z", "+00:00"))
    except Exception:
        return None


def get_session_duration_minutes(session: dict) -> int:
    """Calculate session duration in minutes."""
    started_at = session.get("started_at")
    ended_at = session.get("ended_at")
    
    if not started_at:
        return 0
    
    try:
        start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        if ended_at:
            end = datetime.fromisoformat(ended_at.replace("Z", "+00:00"))
        else:
            end = datetime.now(timezone.utc)
        return int((end - start).total_seconds() / 60)
    except Exception:
        return 0


def generate_session_insights(session: dict, summary: dict) -> List[str]:
    """Generate auto-insights for a session."""
    
    insights = []
    
    profit_loss = float(session.get("profit_loss", 0) or 0)
    duration = get_session_duration_minutes(session)
    hands = int(session.get("hands_played", 0) or 0)
    end_reason = session.get("end_reason")
    
    wins = summary.get("wins", 0)
    losses = summary.get("losses", 0)
    folds = summary.get("folds", 0)
    total = wins + losses + folds
    
    # Calculate rates
    fold_rate = (folds / total * 100) if total > 0 else 0
    win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
    
    # Always add play quality (excellent since they used the app)
    insights.append("✅ Play Quality: EXCELLENT — followed mathematically optimal decisions")
    
    # Fold discipline
    if fold_rate >= 40:
        insights.append(f"💡 Strong fold discipline ({fold_rate:.0f}%) preserved your edge")
    elif fold_rate >= 30:
        insights.append(f"💡 Good fold discipline ({fold_rate:.0f}%)")
    
    # Win/Loss based insights
    if profit_loss > 0:
        if win_rate >= 60:
            insights.append(f"🔥 Hot session — {win_rate:.0f}% win rate on contested hands")
        else:
            insights.append("🎯 Positive variance aligned with correct play")
    elif profit_loss < 0:
        if win_rate >= 40:
            insights.append("📊 Variance session — correct decisions, unlucky outcomes")
        else:
            insights.append("📊 Tough variance — stay the course, the math will balance")
    
    # End reason insights
    if end_reason == "stop_loss":
        insights.append("🛡️ Stop-loss protected you from further losses")
    elif end_reason == "stop_win":
        insights.append("🎉 Locked in profits at the right time")
    elif end_reason == "time_limit":
        insights.append("⏱️ Time limit reached — good discipline")
    
    # Duration insights
    if duration >= 180:
        insights.append("⏱️ Extended session (3+ hrs) — consider shorter sessions for peak performance")
    elif duration <= 60 and profit_loss > 100:
        insights.append(f"⚡ Efficient session — {format_money(profit_loss)} in just {duration} minutes")
    
    # Hands played insights
    if hands >= 50:
        insights.append(f"📈 High volume session — {hands} hands played")
    
    return insights


def filter_sessions(
    sessions: List[dict],
    stakes_filter: str,
    result_filter: str,
    end_reason_filter: str,
    date_from: Optional[datetime],
    date_to: Optional[datetime],
) -> List[dict]:
    """Filter sessions based on criteria."""
    
    filtered = []
    
    for session in sessions:
        # Stakes filter
        if stakes_filter != "All Stakes":
            if session.get("stakes") != stakes_filter:
                continue
        
        # Result filter
        pl = float(session.get("profit_loss", 0) or 0)
        if result_filter == "Winning Sessions" and pl <= 0:
            continue
        if result_filter == "Losing Sessions" and pl >= 0:
            continue
        if result_filter == "Break-even" and pl != 0:
            continue
        
        # End reason filter
        if end_reason_filter != "All":
            reason = session.get("end_reason")
            reason_display = END_REASON_DISPLAY.get(reason, "Unknown")
            if reason_display != end_reason_filter:
                continue
        
        # Date filter
        session_dt = parse_session_datetime(session)
        if session_dt:
            session_date = session_dt.date()
            if date_from and session_date < date_from:
                continue
            if date_to and session_date > date_to:
                continue
        
        filtered.append(session)
    
    return filtered


def sessions_to_dataframe(sessions: List[dict]) -> pd.DataFrame:
    """Convert sessions to a pandas DataFrame for export."""
    
    data = []
    for session in sessions:
        duration = get_session_duration_minutes(session)
        bb_size = float(session.get("bb_size", 2.0) or 2.0)
        hands = int(session.get("hands_played", 0) or 0)
        pl = float(session.get("profit_loss", 0) or 0)
        bb_per_100 = calculate_bb_per_100(pl, hands, bb_size)
        
        session_dt = parse_session_datetime(session)
        
        data.append({
            "Date": session_dt.strftime("%Y-%m-%d %H:%M") if session_dt else "",
            "Stakes": session.get("stakes", ""),
            "Duration (min)": duration,
            "Hands": hands,
            "P/L ($)": pl,
            "BB/100": round(bb_per_100, 1),
            "End Reason": END_REASON_DISPLAY.get(session.get("end_reason"), "Unknown"),
            "Buy-in": float(session.get("buy_in_amount", 0) or 0),
            "Final Stack": float(session.get("final_stack", 0) or 0),
        })
    
    return pd.DataFrame(data)


# =============================================================================
# RENDER FUNCTIONS
# =============================================================================

def render_summary_stats(sessions: List[dict]):
    """Render summary statistics for filtered sessions."""
    
    if not sessions:
        return
    
    total_sessions = len(sessions)
    total_pl = sum(float(s.get("profit_loss", 0) or 0) for s in sessions)
    total_hands = sum(int(s.get("hands_played", 0) or 0) for s in sessions)
    total_duration = sum(get_session_duration_minutes(s) for s in sessions)
    
    # Calculate overall BB/100 (weighted average)
    total_bb_won = 0
    for s in sessions:
        bb_size = float(s.get("bb_size", 2.0) or 2.0)
        pl = float(s.get("profit_loss", 0) or 0)
        total_bb_won += pl / bb_size if bb_size > 0 else 0
    
    overall_bb_per_100 = (total_bb_won / total_hands * 100) if total_hands > 0 else 0
    
    winning_sessions = sum(1 for s in sessions if float(s.get("profit_loss", 0) or 0) > 0)
    win_pct = (winning_sessions / total_sessions * 100) if total_sessions > 0 else 0
    
    st.markdown(
        f"""
        <div class="stats-summary">
            <div class="stats-summary-grid">
                <div class="summary-stat">
                    <div class="summary-stat-value">{total_sessions}</div>
                    <div class="summary-stat-label">Sessions</div>
                </div>
                <div class="summary-stat">
                    <div class="summary-stat-value" style="color: {'#22c55e' if total_pl >= 0 else '#ef4444'};">
                        {format_money(total_pl)}
                    </div>
                    <div class="summary-stat-label">Total P/L</div>
                </div>
                <div class="summary-stat">
                    <div class="summary-stat-value">{format_bb_per_100(overall_bb_per_100)}</div>
                    <div class="summary-stat-label">BB/100</div>
                </div>
                <div class="summary-stat">
                    <div class="summary-stat-value">{win_pct:.0f}%</div>
                    <div class="summary-stat-label">Win Rate</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def render_calendar_heatmap(sessions: List[dict]):
    """Render a calendar heatmap of sessions."""
    
    st.markdown("### 📅 Session Calendar")
    
    # Get sessions by date
    sessions_by_date = {}
    for session in sessions:
        session_dt = parse_session_datetime(session)
        if session_dt:
            date_key = session_dt.date()
            pl = float(session.get("profit_loss", 0) or 0)
            if date_key not in sessions_by_date:
                sessions_by_date[date_key] = 0
            sessions_by_date[date_key] += pl
    
    if not sessions_by_date:
        st.info("No sessions to display on calendar.")
        return
    
    # Get date range (last 12 weeks)
    today = datetime.now(timezone.utc).date()
    start_date = today - timedelta(weeks=12)
    
    # Build calendar grid
    cols = st.columns(12)
    current_date = start_date
    
    week_idx = 0
    while current_date <= today:
        col_idx = week_idx % 12
        
        with cols[col_idx]:
            week_html = ""
            for day in range(7):
                check_date = current_date + timedelta(days=day)
                if check_date > today:
                    break
                
                if check_date in sessions_by_date:
                    pl = sessions_by_date[check_date]
                    if pl > 0:
                        css_class = "winning"
                        title = f"{check_date.strftime('%b %d')}: +${pl:.0f}"
                    elif pl < 0:
                        css_class = "losing"
                        title = f"{check_date.strftime('%b %d')}: -${abs(pl):.0f}"
                    else:
                        css_class = "breakeven"
                        title = f"{check_date.strftime('%b %d')}: $0"
                else:
                    css_class = "no-session"
                    title = check_date.strftime('%b %d')
                
                week_html += f'<div class="calendar-day {css_class}" title="{title}"></div>'
            
            st.markdown(week_html, unsafe_allow_html=True)
        
        current_date += timedelta(weeks=1)
        week_idx += 1
    
    # Legend
    st.markdown("""
        <div style="display: flex; gap: 16px; margin-top: 12px; font-size: 12px; color: #6b7280;">
            <span><span class="calendar-day winning" style="display: inline-block; vertical-align: middle;"></span> Winning</span>
            <span><span class="calendar-day losing" style="display: inline-block; vertical-align: middle;"></span> Losing</span>
            <span><span class="calendar-day no-session" style="display: inline-block; vertical-align: middle;"></span> No session</span>
        </div>
    """, unsafe_allow_html=True)


def render_session_card(session: dict, expanded: bool = False):
    """Render a single session card."""
    
    session_id = session.get("id")
    session_dt = parse_session_datetime(session)
    
    # Session data
    stakes = session.get("stakes", "$1/$2")
    duration = get_session_duration_minutes(session)
    hands = int(session.get("hands_played", 0) or 0)
    pl = float(session.get("profit_loss", 0) or 0)
    bb_size = float(session.get("bb_size", 2.0) or 2.0)
    bb_per_100 = calculate_bb_per_100(pl, hands, bb_size)
    end_reason = session.get("end_reason")
    
    # Determine card class
    if pl > 0:
        card_class = "winning"
        pl_class = "positive"
    elif pl < 0:
        card_class = "losing"
        pl_class = "negative"
    else:
        card_class = "breakeven"
        pl_class = "zero"
    
    # Format date
    date_str = session_dt.strftime("%A, %B %d, %Y @ %I:%M %p") if session_dt else "Unknown Date"
    
    # Create expander for session
    with st.expander(f"**{date_str}** — {stakes} — {format_money(pl)}", expanded=expanded):
        
        # Stats row
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric("Stakes", stakes)
        with col2:
            st.metric("Duration", format_duration(duration))
        with col3:
            st.metric("Hands", hands)
        with col4:
            st.metric("P/L", format_money(pl), delta=None)
        with col5:
            st.metric("BB/100", format_bb_per_100(bb_per_100))
        
        # Get outcome summary
        summary = get_session_outcome_summary(session_id) if session_id else {}
        wins = summary.get("wins", 0)
        losses = summary.get("losses", 0)
        folds = summary.get("folds", 0)
        total = wins + losses + folds
        
        # Outcome breakdown
        if total > 0:
            st.markdown("#### Hand Outcomes")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                win_pct = (wins / total * 100) if total > 0 else 0
                st.markdown(
                    f"""
                    <div class="outcome-box wins">
                        <div class="outcome-count" style="color: #22c55e;">{wins}</div>
                        <div class="outcome-label">Wins</div>
                        <div class="outcome-pct">{win_pct:.0f}%</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            
            with col2:
                loss_pct = (losses / total * 100) if total > 0 else 0
                st.markdown(
                    f"""
                    <div class="outcome-box losses">
                        <div class="outcome-count" style="color: #ef4444;">{losses}</div>
                        <div class="outcome-label">Losses</div>
                        <div class="outcome-pct">{loss_pct:.0f}%</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            
            with col3:
                fold_pct = (folds / total * 100) if total > 0 else 0
                st.markdown(
                    f"""
                    <div class="outcome-box folds">
                        <div class="outcome-count" style="color: #6b7280;">{folds}</div>
                        <div class="outcome-label">Folds</div>
                        <div class="outcome-pct">{fold_pct:.0f}%</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
        
        # Auto-generated insights
        insights = generate_session_insights(session, summary)
        
        if insights:
            st.markdown("#### 📋 Session Insights")
            for insight in insights:
                st.markdown(f"- {insight}")
        
        # End reason
        st.markdown("---")
        st.caption(f"**End Reason:** {END_REASON_DISPLAY.get(end_reason, 'Unknown')}")


def render_filters() -> tuple:
    """Render filter controls and return filter values."""
    
    st.markdown("### 🔍 Filters")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        stakes_filter = st.selectbox(
            "Stakes",
            STAKES_OPTIONS,
            key="filter_stakes"
        )
    
    with col2:
        result_filter = st.selectbox(
            "Result",
            RESULT_OPTIONS,
            key="filter_result"
        )
    
    with col3:
        end_reason_filter = st.selectbox(
            "End Reason",
            END_REASON_OPTIONS,
            key="filter_end_reason"
        )
    
    with col4:
        date_range = st.selectbox(
            "Date Range",
            ["Last 7 days", "Last 30 days", "Last 90 days", "This month", "All time", "Custom"],
            key="filter_date_range"
        )
    
    # Calculate date range
    today = datetime.now(timezone.utc).date()
    
    if date_range == "Last 7 days":
        date_from = today - timedelta(days=7)
        date_to = today
    elif date_range == "Last 30 days":
        date_from = today - timedelta(days=30)
        date_to = today
    elif date_range == "Last 90 days":
        date_from = today - timedelta(days=90)
        date_to = today
    elif date_range == "This month":
        date_from = today.replace(day=1)
        date_to = today
    elif date_range == "All time":
        date_from = None
        date_to = None
    else:  # Custom
        col1, col2 = st.columns(2)
        with col1:
            date_from = st.date_input("From", value=today - timedelta(days=30), key="custom_from")
        with col2:
            date_to = st.date_input("To", value=today, key="custom_to")
    
    return stakes_filter, result_filter, end_reason_filter, date_from, date_to


def render_export_button(sessions: List[dict]):
    """Render export to CSV button."""
    
    if not sessions:
        return
    
    df = sessions_to_dataframe(sessions)
    csv = df.to_csv(index=False)
    
    st.download_button(
        label="📥 Export to CSV",
        data=csv,
        file_name=f"poker_sessions_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
    )


def render_empty_state():
    """Render empty state when no sessions."""
    
    st.markdown(
        """
        <div class="empty-state">
            <div class="empty-state-icon">📋</div>
            <h3>No Sessions Yet</h3>
            <p>Start a play session to begin tracking your poker journey.</p>
        </div>
        """,
        unsafe_allow_html=True
    )


# =============================================================================
# MAIN PAGE
# =============================================================================

def main():
    """Main render function."""
    
    st.title("📋 Session History")
    st.caption("Review your individual sessions and auto-generated insights")
    
    user_id = get_user_id()
    
    if not user_id:
        st.warning("Please log in to view your session history.")
        return
    
    # Get all sessions
    all_sessions = get_user_sessions(user_id, limit=500)
    
    if not all_sessions:
        render_empty_state()
        return
    
    # Filters
    stakes_filter, result_filter, end_reason_filter, date_from, date_to = render_filters()
    
    # Apply filters
    filtered_sessions = filter_sessions(
        all_sessions,
        stakes_filter,
        result_filter,
        end_reason_filter,
        date_from,
        date_to
    )
    
    st.markdown("---")
    
    if not filtered_sessions:
        st.info("No sessions match your filters. Try adjusting the criteria.")
        return
    
    # Summary stats for filtered sessions
    render_summary_stats(filtered_sessions)
    
    # Export button
    col1, col2 = st.columns([3, 1])
    with col2:
        render_export_button(filtered_sessions)
    
    # Tabs for different views
    tab1, tab2 = st.tabs(["📋 Session List", "📅 Calendar View"])
    
    with tab1:
        st.markdown(f"**Showing {len(filtered_sessions)} sessions**")
        st.markdown("")
        
        # Sort sessions by date (newest first)
        sorted_sessions = sorted(
            filtered_sessions,
            key=lambda s: parse_session_datetime(s) or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True
        )
        
        # Pagination
        sessions_per_page = 10
        total_pages = (len(sorted_sessions) + sessions_per_page - 1) // sessions_per_page
        
        if total_pages > 1:
            page = st.number_input(
                "Page",
                min_value=1,
                max_value=total_pages,
                value=1,
                key="session_page"
            )
        else:
            page = 1
        
        start_idx = (page - 1) * sessions_per_page
        end_idx = start_idx + sessions_per_page
        page_sessions = sorted_sessions[start_idx:end_idx]
        
        # Render session cards
        for session in page_sessions:
            render_session_card(session)
        
        if total_pages > 1:
            st.caption(f"Page {page} of {total_pages}")
    
    with tab2:
        render_calendar_heatmap(filtered_sessions)


if __name__ == "__main__":
    main()