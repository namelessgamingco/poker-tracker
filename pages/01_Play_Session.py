# 01_Play_Session.py — Main Play Session Page for Poker Decision App
# Complete implementation with outcome recording, EV modals, and session summary

import streamlit as st
import html as _html
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

st.set_page_config(
    page_title="Play Session | Poker Decision App",
    page_icon="🎯",
    layout="centered",
)

from auth import require_auth
from sidebar import render_sidebar, update_sidebar_session_info, clear_sidebar_session_info
from db import (
    get_profile_by_auth_id,
    create_session,
    get_active_session,
    update_session,
    increment_session_stats,
    end_session,
    update_user_bankroll,
    record_bankroll_change,
    get_stakes_options,
    get_stakes_info,
    record_hand_outcome,
    get_session_outcome_summary,
)
from engine import (
    get_decision,
    Action,
    HandStrength,
    BoardTexture,
    classify_preflop_hand,
    normalize_hand,
)

# ---------- Auth Gate ----------
user = require_auth()
render_sidebar()

# =============================================================================
# CONSTANTS
# =============================================================================

# Risk mode configurations
MODE_CONFIG = {
    "aggressive": {"buy_ins": 13, "stop_loss_bi": 0.75, "stop_win_bi": 3.0, "label": "Aggressive"},
    "balanced": {"buy_ins": 15, "stop_loss_bi": 1.0, "stop_win_bi": 3.0, "label": "Balanced"},
    "conservative": {"buy_ins": 17, "stop_loss_bi": 1.25, "stop_win_bi": 3.0, "label": "Conservative"},
}

# Stakes to buy-in mapping
STAKES_BUY_INS = {
    "$0.50/$1": {"bb": 1.0, "buy_in": 100},
    "$1/$2": {"bb": 2.0, "buy_in": 200},
    "$2/$5": {"bb": 5.0, "buy_in": 500},
    "$5/$10": {"bb": 10.0, "buy_in": 1000},
    "$10/$20": {"bb": 20.0, "buy_in": 2000},
    "$25/$50": {"bb": 50.0, "buy_in": 5000},
}

# Card display
SUIT_DISPLAY = {"h": "♥", "d": "♦", "c": "♣", "s": "♠"}
SUIT_COLORS = {"h": "#ef4444", "d": "#3b82f6", "c": "#22c55e", "s": "#111827"}
RANKS = ["A", "K", "Q", "J", "T", "9", "8", "7", "6", "5", "4", "3", "2"]
SUITS = ["h", "d", "c", "s"]

# Position labels
POSITIONS = ["UTG", "HJ", "CO", "BTN", "SB", "BB"]

# =============================================================================
# CUSTOM CSS
# =============================================================================

st.markdown("""
<style>
/* Decision display box */
.decision-box {
    padding: 24px;
    border-radius: 12px;
    text-align: center;
    margin: 16px 0;
}
.decision-box.aggressive {
    background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
    color: white;
}
.decision-box.passive {
    background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
    color: white;
}
.decision-box.fold {
    background: linear-gradient(135deg, #6b7280 0%, #4b5563 100%);
    color: white;
}
.decision-box.allin {
    background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
    color: white;
}
.decision-action {
    font-size: 32px;
    font-weight: 800;
    margin-bottom: 8px;
    letter-spacing: 1px;
}
.decision-explanation {
    font-size: 14px;
    opacity: 0.9;
}

/* Card display */
.card-display {
    display: inline-block;
    padding: 8px 12px;
    border-radius: 8px;
    background: white;
    border: 2px solid #e5e7eb;
    margin: 4px;
    font-size: 18px;
    font-weight: 700;
}
.card-display.hearts, .card-display.diamonds {
    color: #ef4444;
}
.card-display.clubs, .card-display.spades {
    color: #111827;
}

/* Alert boxes */
.alert-box {
    padding: 16px;
    border-radius: 8px;
    margin: 12px 0;
    display: flex;
    align-items: flex-start;
    gap: 12px;
}
.alert-box.warning {
    background: #fef3c7;
    border: 1px solid #f59e0b;
}
.alert-box.danger {
    background: #fee2e2;
    border: 1px solid #ef4444;
}
.alert-box.success {
    background: #dcfce7;
    border: 1px solid #22c55e;
}
.alert-box.info {
    background: #dbeafe;
    border: 1px solid #3b82f6;
}
.alert-box span:first-child {
    font-size: 24px;
}

/* Session header */
.session-header {
    background: #1f2937;
    color: white;
    padding: 16px;
    border-radius: 8px;
    margin-bottom: 16px;
}
.session-stat {
    text-align: center;
}
.session-stat-value {
    font-size: 24px;
    font-weight: 700;
}
.session-stat-label {
    font-size: 12px;
    opacity: 0.7;
    text-transform: uppercase;
}

/* Modal styling */
.modal-card {
    background: white;
    border-radius: 12px;
    padding: 24px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    margin: 16px 0;
}
.modal-title {
    font-size: 24px;
    font-weight: 700;
    margin-bottom: 16px;
    text-align: center;
}
.modal-body {
    font-size: 16px;
    line-height: 1.6;
}

/* Outcome buttons */
.outcome-btn {
    padding: 16px 24px;
    font-size: 18px;
    font-weight: 700;
    border-radius: 8px;
    width: 100%;
}
</style>
""", unsafe_allow_html=True)


# =============================================================================
# SESSION STATE INITIALIZATION
# =============================================================================

def init_session_state():
    """Initialize all session state variables."""
    defaults = {
        # Session mode
        "session_mode": "setup",  # 'setup', 'play', 'outcome', 'ending'
        
        # Session data
        "current_session": None,
        "session_pl": 0.0,
        "our_stack": 0.0,
        "hands_played": 0,
        "decisions_requested": 0,
        
        # Hand tracking
        "hand_outcomes": [],  # List of {outcome, profit_loss, street, position}
        
        # Current hand state
        "street": "preflop",
        "our_cards": ["", ""],
        "board_cards": ["", "", "", "", ""],
        "our_position": None,
        "action_facing": "none",
        "facing_bet": 0.0,
        "pot_size": 0.0,
        "num_limpers": 0,
        "villain_type": "unknown",
        "hand_strength": None,
        "board_texture": None,
        "we_are_aggressor": False,
        
        # Decision state
        "last_decision": None,
        "last_hand_context": {},
        
        # Modal queue
        "modal_queue": [],
        
        # Table check
        "table_check_due": False,
        "last_table_check": None,
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_session_state()


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_user_profile() -> dict:
    """Get current user's profile."""
    user_id = st.session_state.get("user_db_id")
    if not user_id:
        return {}
    return get_profile_by_auth_id(user_id) or {}


def get_session_duration_minutes() -> int:
    """Get current session duration in minutes."""
    session = st.session_state.get("current_session")
    if not session:
        return 0
    
    started_at = session.get("started_at")
    if not started_at:
        return 0
    
    try:
        start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        return int((now - start).total_seconds() / 60)
    except Exception:
        return 0


def format_card(card: str) -> str:
    """Format card for display (e.g., 'Ah' -> 'A♥')."""
    if not card or len(card) < 2:
        return "?"
    rank = card[0].upper()
    suit = card[1].lower()
    return f"{rank}{SUIT_DISPLAY.get(suit, '?')}"


def format_money(amount: float) -> str:
    """Format money with sign."""
    if amount >= 0:
        return f"+${amount:.2f}"
    return f"-${abs(amount):.2f}"


def queue_modal(modal_type: str, data: dict):
    """Add a modal to the queue."""
    st.session_state.modal_queue.append({"type": modal_type, "data": data})


def dismiss_modal():
    """Remove the current modal from queue."""
    if st.session_state.modal_queue:
        st.session_state.modal_queue.pop(0)


def clear_hand_state():
    """Clear current hand state for next hand."""
    st.session_state.our_cards = ["", ""]
    st.session_state.board_cards = ["", "", "", "", ""]
    st.session_state.our_position = None
    st.session_state.action_facing = "none"
    st.session_state.facing_bet = 0.0
    st.session_state.pot_size = 0.0
    st.session_state.num_limpers = 0
    st.session_state.hand_strength = None
    st.session_state.board_texture = None
    st.session_state.we_are_aggressor = False
    st.session_state.last_decision = None
    st.session_state.last_hand_context = {}
    st.session_state.street = "preflop"


# =============================================================================
# MODAL RENDERING
# =============================================================================

def render_modals() -> bool:
    """Render any queued modals. Returns True if modal was rendered."""
    if not st.session_state.modal_queue:
        return False
    
    modal = st.session_state.modal_queue[0]
    modal_type = modal.get("type")
    data = modal.get("data", {})
    
    if modal_type == "outcome":
        return render_outcome_modal(data)
    elif modal_type == "session_end":
        return render_session_end_modal(data)
    elif modal_type == "table_check":
        return render_table_check_modal(data)
    
    return False


def render_outcome_modal(data: dict) -> bool:
    """Render the post-hand outcome modal with EV education."""
    
    outcome = data.get("outcome")  # "won", "lost", "folded"
    decision = data.get("decision")
    hand_context = data.get("hand_context", {})
    profit_loss = data.get("profit_loss", 0)
    
    st.markdown("---")
    
    # Determine modal theme
    if outcome == "folded":
        icon = "🛡️"
        title = "Good Fold"
        theme = "info"
    elif outcome == "won":
        icon = "✅"
        title = "Correct Play + Win"
        theme = "success"
    else:  # lost
        icon = "📊"
        title = "Correct Play, Unlucky Result"
        theme = "info"
    
    # Build explanation
    action_display = data.get("action_taken", "")
    explanation = decision.explanation if decision else ""
    calculation = decision.calculation if decision else ""
    
    col1, col2, col3 = st.columns([1, 4, 1])
    with col2:
        st.markdown(f"### {icon} {title}")
        
        if action_display:
            st.markdown(f"**You:** {action_display}")
        
        if explanation:
            st.markdown(f"*{explanation}*")
        
        if calculation:
            st.info(f"**Math:** {calculation}")
        
        # Outcome-specific messaging
        if outcome == "won":
            st.markdown(
                """
                <div class="alert-box success">
                    <span>🎯</span>
                    <div>
                        <strong>Math + Luck = Great Result</strong><br>
                        You made the +EV play and it worked out. Keep making these decisions 
                        and the results will keep coming.
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
        elif outcome == "lost":
            st.markdown(
                """
                <div class="alert-box info">
                    <span>💡</span>
                    <div>
                        <strong>This is how winning players play.</strong><br>
                        Variance means you'll lose some +EV spots. Over hundreds of hands, 
                        these mathematically correct decisions add up to significant profit.
                        <br><br>
                        <em>Stick to the math. Variance is temporary, +EV is forever.</em>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
        else:  # folded
            st.markdown(
                """
                <div class="alert-box info">
                    <span>🛡️</span>
                    <div>
                        <strong>Folding IS winning.</strong><br>
                        Every -EV call you avoid is money saved. The best players fold 
                        more than recreational players — that's part of why they win.
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
        
        st.markdown("")
        if st.button("Got it → Next Hand", type="primary", use_container_width=True, key="modal_dismiss"):
            dismiss_modal()
            clear_hand_state()
            st.rerun()
    
    return True


def render_session_end_modal(data: dict) -> bool:
    """Render session summary modal."""
    
    st.markdown("---")
    st.markdown("## 📊 Session Complete")
    
    # Session stats
    duration_minutes = data.get("duration_minutes", 0)
    hours = duration_minutes // 60
    mins = duration_minutes % 60
    total_hands = data.get("total_hands", 0)
    session_pl = data.get("session_pl", 0)
    wins = data.get("wins", 0)
    losses = data.get("losses", 0)
    folds = data.get("folds", 0)
    bb_size = data.get("bb_size", 2.0)
    
    # Calculate BB/100
    bb_per_100 = 0
    if total_hands > 0 and bb_size > 0:
        bb_won = session_pl / bb_size
        bb_per_100 = (bb_won / total_hands) * 100
    
    # Display metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Duration", f"{hours}h {mins}m")
    with col2:
        st.metric("Hands", total_hands)
    with col3:
        pl_display = format_money(session_pl)
        st.metric("Session P/L", pl_display)
    with col4:
        st.metric("BB/100", f"{bb_per_100:+.1f}")
    
    st.markdown("---")
    
    # Play quality
    st.markdown("### 🌟 Your Play Quality")
    st.markdown(
        """
        <div class="alert-box success">
            <span>✅</span>
            <div>
                <strong>EXCELLENT</strong><br>
                You followed mathematically optimal decisions throughout this session. 
                This is exactly how winning players play.
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Outcome breakdown
    if total_hands > 0:
        st.markdown("### 📈 Hand Outcomes")
        col1, col2, col3 = st.columns(3)
        with col1:
            win_pct = (wins / total_hands) * 100 if total_hands > 0 else 0
            st.metric("Wins", f"{wins} ({win_pct:.0f}%)")
        with col2:
            loss_pct = (losses / total_hands) * 100 if total_hands > 0 else 0
            st.metric("Losses", f"{losses} ({loss_pct:.0f}%)")
        with col3:
            fold_pct = (folds / total_hands) * 100 if total_hands > 0 else 0
            st.metric("Folds", f"{folds} ({fold_pct:.0f}%)")
    
    st.markdown("---")
    
    # Variance education for losing sessions
    if session_pl > 0:
        st.markdown(
            """
            <div class="alert-box success">
                <span>🎉</span>
                <div>
                    <strong>Great session!</strong><br>
                    You played mathematically sound poker and the results showed it. 
                    Keep up this level of play!
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
    elif session_pl < 0:
        st.markdown(
            """
            <div class="alert-box info">
                <span>📊</span>
                <div>
                    <strong>Variance happens.</strong><br>
                    You made +EV decisions throughout this session. Players who maintain 
                    this level of play average <strong>+$20,000-24,000/year</strong> at $1/$2.
                    <br><br>
                    <em>Keep playing correctly. The math always wins long-term.</em>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            """
            <div class="alert-box info">
                <span>📊</span>
                <div>
                    <strong>Break-even session.</strong><br>
                    You played solid poker. The wins will come with continued good play.
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    st.markdown("")
    if st.button("Close Session", type="primary", use_container_width=True, key="close_session_modal"):
        dismiss_modal()
        st.session_state.session_mode = "setup"
        st.session_state.current_session = None
        clear_sidebar_session_info()
        st.rerun()
    
    return True


def render_table_check_modal(data: dict) -> bool:
    """Render table quality check modal."""
    
    st.markdown("---")
    st.markdown("## 🎯 Quick Table Check")
    st.caption("Answer these 3 quick questions about the last 10 hands")
    
    # Question 1: Players to flop
    players_to_flop = st.radio(
        "How many players typically see the flop?",
        ["2-3 (Tight)", "3-4 (Average)", "4-5 (Loose)", "5-6 (Very Loose)"],
        key="table_check_q1",
        horizontal=True
    )
    
    # Question 2: Limpers
    has_limpers = st.radio(
        "Are there limpers?",
        ["Yes", "No"],
        key="table_check_q2",
        horizontal=True
    )
    
    # Question 3: 3-bet frequency
    three_bet_freq = st.radio(
        "Is anyone 3-betting a lot?",
        ["No (Good)", "Sometimes", "Yes (Reg-heavy)"],
        key="table_check_q3",
        horizontal=True
    )
    
    # Calculate score
    score = 50  # Base score
    
    if "5-6" in players_to_flop:
        score += 30
    elif "4-5" in players_to_flop:
        score += 20
    elif "3-4" in players_to_flop:
        score += 10
    else:
        score -= 10
    
    if has_limpers == "Yes":
        score += 15
    else:
        score -= 5
    
    if "No" in three_bet_freq:
        score += 15
    elif "Sometimes" in three_bet_freq:
        score += 0
    else:
        score -= 15
    
    score = max(0, min(100, score))
    
    st.markdown("---")
    
    # Display result
    if score >= 60:
        st.success(f"**Table Score: {score}/100** ✅ Good table - stay and play!")
    elif score >= 40:
        st.warning(f"**Table Score: {score}/100** ⚠️ Average table")
    else:
        st.error(f"**Table Score: {score}/100** 🔴 Tough table - consider leaving")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Done", type="primary", use_container_width=True, key="table_check_done"):
            st.session_state.last_table_check = datetime.now(timezone.utc)
            st.session_state.table_check_due = False
            dismiss_modal()
            st.rerun()
    with col2:
        if st.button("Skip", use_container_width=True, key="table_check_skip"):
            st.session_state.table_check_due = False
            dismiss_modal()
            st.rerun()
    
    return True


# =============================================================================
# SETUP MODE
# =============================================================================

def render_setup_mode():
    """Render session setup interface."""
    
    st.title("🎯 Start New Session")
    
    profile = get_user_profile()
    user_mode = profile.get("user_mode", "balanced")
    current_bankroll = float(profile.get("current_bankroll", 0) or 0)
    default_stakes = profile.get("default_stakes", "$1/$2")
    
    mode_config = MODE_CONFIG.get(user_mode, MODE_CONFIG["balanced"])
    
    # Check for active session
    user_id = st.session_state.get("user_db_id")
    active_session = get_active_session(user_id) if user_id else None
    
    if active_session:
        st.warning("You have an active session. Would you like to continue or end it?")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Continue Session", type="primary", use_container_width=True):
                st.session_state.current_session = active_session
                st.session_state.session_mode = "play"
                st.session_state.our_stack = float(active_session.get("buy_in_amount", 200))
                st.session_state.session_pl = float(active_session.get("profit_loss", 0) or 0)
                update_sidebar_session_info(active_session, st.session_state.session_pl)
                st.rerun()
        with col2:
            if st.button("End Previous Session", use_container_width=True):
                end_session(active_session["id"], active_session.get("buy_in_amount", 0), "manual")
                st.rerun()
        return
    
    st.markdown("---")
    
    # Stakes selection
    stakes_options = list(STAKES_BUY_INS.keys())
    default_idx = stakes_options.index(default_stakes) if default_stakes in stakes_options else 1
    
    selected_stakes = st.selectbox(
        "Stakes",
        stakes_options,
        index=default_idx,
        help="Select the stakes you're playing"
    )
    
    stakes_info = STAKES_BUY_INS.get(selected_stakes, {"bb": 2.0, "buy_in": 200})
    bb_size = stakes_info["bb"]
    standard_buy_in = stakes_info["buy_in"]
    
    # Buy-in input
    buy_in = st.number_input(
        "Buy-in Amount ($)",
        min_value=float(standard_buy_in * 0.2),
        max_value=float(standard_buy_in * 4),
        value=float(standard_buy_in),
        step=float(bb_size * 10),
        help="Enter your buy-in amount"
    )
    
    # Stack depth indicator
    stack_bb = buy_in / bb_size
    if stack_bb < 40:
        st.warning(f"⚠️ {stack_bb:.0f} BB — Short stack mode active")
    elif stack_bb > 150:
        st.info(f"📈 {stack_bb:.0f} BB — Deep stack adjustments active")
    else:
        st.caption(f"= {stack_bb:.0f} BB (standard)")
    
    st.markdown("---")
    
    # Bankroll check
    required_buy_ins = mode_config["buy_ins"]
    required_bankroll = standard_buy_in * required_buy_ins
    
    if current_bankroll > 0:
        buy_ins_available = current_bankroll / standard_buy_in
        
        st.markdown(f"**Your Bankroll:** ${current_bankroll:,.2f} ({buy_ins_available:.1f} buy-ins at {selected_stakes})")
        
        if buy_ins_available < required_buy_ins:
            st.markdown(
                f"""
                <div class="alert-box warning">
                    <span>⚠️</span>
                    <div>
                        <strong>Bankroll Warning</strong><br>
                        Your {mode_config['label']} mode requires {required_buy_ins} buy-ins (${required_bankroll:,.0f}) 
                        for {selected_stakes}. You have {buy_ins_available:.1f} buy-ins.
                        <br><br>
                        Consider moving down or switching to a more conservative mode.
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
            
            override = st.checkbox("I understand the risk and want to play anyway", key="bankroll_override")
        else:
            override = True
            st.success(f"✅ Bankroll adequate for {selected_stakes} ({mode_config['label']} mode)")
    else:
        override = True
        st.info("💡 Set your bankroll in Settings to enable bankroll tracking")
    
    st.markdown("---")
    
    # Session limits display
    stop_loss = standard_buy_in * mode_config["stop_loss_bi"]
    stop_win = standard_buy_in * mode_config["stop_win_bi"]
    
    st.markdown("### Session Limits")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Stop-Loss", f"${stop_loss:.0f}", help=f"{mode_config['stop_loss_bi']} buy-in")
    with col2:
        st.metric("Stop-Win", f"${stop_win:.0f}", help=f"{mode_config['stop_win_bi']} buy-ins")
    
    st.caption(f"Mode: {mode_config['label']} | Time limit: 4 hours")
    
    st.markdown("---")
    
    # Start session button
    if st.button("▶️ Start Session", type="primary", use_container_width=True, disabled=not override):
        # Create session in database
        session = create_session(
            user_id=user_id,
            stakes=selected_stakes,
            bb_size=bb_size,
            buy_in_amount=buy_in,
            bankroll_at_start=current_bankroll if current_bankroll > 0 else None,
        )
        
        if session:
            st.session_state.current_session = session
            st.session_state.session_mode = "play"
            st.session_state.our_stack = buy_in
            st.session_state.session_pl = 0.0
            st.session_state.hands_played = 0
            st.session_state.decisions_requested = 0
            st.session_state.hand_outcomes = []
            clear_hand_state()
            update_sidebar_session_info(session, 0)
            st.rerun()
        else:
            st.error("Failed to create session. Please try again.")


# =============================================================================
# PLAY MODE
# =============================================================================

def render_play_mode():
    """Render main play interface."""
    
    # Check for modals first
    if render_modals():
        return
    
    session = st.session_state.current_session
    if not session:
        st.session_state.session_mode = "setup"
        st.rerun()
        return
    
    # Render session header
    render_session_header()
    
    # Check for session alerts
    check_session_alerts()
    
    # Check if we're showing outcome buttons (after a decision)
    if st.session_state.last_decision is not None:
        render_outcome_recording()
        return
    
    # Render decision interface
    render_decision_interface()


def render_session_header():
    """Render session status header."""
    
    session = st.session_state.current_session
    stakes = session.get("stakes", "$1/$2")
    duration = get_session_duration_minutes()
    hours = duration // 60
    mins = duration % 60
    
    session_pl = st.session_state.session_pl
    our_stack = st.session_state.our_stack
    bb_size = float(session.get("bb_size", 2.0))
    stack_bb = our_stack / bb_size if bb_size > 0 else 0
    
    st.markdown(
        f"""
        <div class="session-header">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div class="session-stat">
                    <div class="session-stat-label">Stakes</div>
                    <div class="session-stat-value">{stakes}</div>
                </div>
                <div class="session-stat">
                    <div class="session-stat-label">Time</div>
                    <div class="session-stat-value">{hours}h {mins}m</div>
                </div>
                <div class="session-stat">
                    <div class="session-stat-label">P/L</div>
                    <div class="session-stat-value" style="color: {'#22c55e' if session_pl >= 0 else '#ef4444'};">
                        {format_money(session_pl)}
                    </div>
                </div>
                <div class="session-stat">
                    <div class="session-stat-label">Stack</div>
                    <div class="session-stat-value">{stack_bb:.0f} BB</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def check_session_alerts():
    """Check and display session alerts."""
    
    session = st.session_state.current_session
    if not session:
        return
    
    duration = get_session_duration_minutes()
    session_pl = st.session_state.session_pl
    
    stakes = session.get("stakes", "$1/$2")
    stakes_info = STAKES_BUY_INS.get(stakes, {"buy_in": 200})
    standard_buy_in = stakes_info["buy_in"]
    
    profile = get_user_profile()
    user_mode = profile.get("user_mode", "balanced")
    mode_config = MODE_CONFIG.get(user_mode, MODE_CONFIG["balanced"])
    
    stop_loss = standard_buy_in * mode_config["stop_loss_bi"]
    stop_win = standard_buy_in * mode_config["stop_win_bi"]
    
    alerts = []
    
    # Time alerts
    if duration >= 240:  # 4 hours
        alerts.append(("danger", "🛑", "4-Hour Limit", "Session ending after this hand. Hard stop reached."))
    elif duration >= 180:  # 3 hours
        alerts.append(("warning", "⏱️", "3-Hour Warning", "Performance typically declines. Consider wrapping up."))
    elif duration >= 90 and session_pl > 0:  # 90 minutes and winning
        alerts.append(("info", "💡", "Optimal Time Reached", "You're at optimal session length and winning. Consider stopping."))
    
    # Stop-loss alert
    if session_pl <= -stop_loss:
        alerts.append(("danger", "🛑", "Stop-Loss Hit", f"You've reached your stop-loss of ${stop_loss:.0f}. Session ending after this hand."))
    
    # Stop-win alert
    if session_pl >= stop_win:
        alerts.append(("success", "🎉", "Stop-Win Hit!", f"Congratulations! You've reached your stop-win of ${stop_win:.0f}. Lock in your profit!"))
    
    # Table check reminder (every 20 minutes)
    if duration > 0 and duration % 20 == 0 and not st.session_state.table_check_due:
        last_check = st.session_state.last_table_check
        if not last_check or (datetime.now(timezone.utc) - last_check).total_seconds() > 1200:  # 20 min
            st.session_state.table_check_due = True
    
    # Render alerts
    for alert_type, icon, title, message in alerts:
        st.markdown(
            f"""
            <div class="alert-box {alert_type}">
                <span>{icon}</span>
                <div>
                    <strong>{title}</strong><br>
                    {message}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    # Table check button
    if st.session_state.table_check_due:
        if st.button("🎯 Quick Table Check", use_container_width=True):
            queue_modal("table_check", {})
            st.rerun()


def render_decision_interface():
    """Render the main decision input interface."""
    
    session = st.session_state.current_session
    stakes = session.get("stakes", "$1/$2")
    bb_size = float(session.get("bb_size", 2.0))
    
    st.markdown("### 🃏 Enter Hand Details")
    
    # Street selection
    street = st.radio(
        "Street",
        ["Pre-Flop", "Flop", "Turn", "River"],
        horizontal=True,
        key="street_select"
    )
    st.session_state.street = street.lower().replace("-", "")
    
    st.markdown("---")
    
    # Card input section
    render_card_input()
    
    st.markdown("---")
    
    # Position selection
    st.markdown("**Your Position**")
    position = st.radio(
        "Position",
        POSITIONS,
        horizontal=True,
        key="position_select",
        label_visibility="collapsed"
    )
    st.session_state.our_position = position
    
    st.markdown("---")
    
    # Action facing
    render_action_facing()
    
    # Post-flop specific inputs
    if st.session_state.street != "preflop":
        st.markdown("---")
        render_postflop_inputs()
    
    # Villain type (optional)
    st.markdown("---")
    villain_type = st.selectbox(
        "Villain Type (optional)",
        ["Unknown", "Fish (loose/passive)", "Reg (tight/aggressive)"],
        index=0,
        key="villain_type_select"
    )
    st.session_state.villain_type = villain_type.split()[0].lower()
    
    st.markdown("---")
    
    # Get Decision button
    can_get_decision = validate_inputs()
    
    if st.button("🎯 GET DECISION", type="primary", use_container_width=True, disabled=not can_get_decision):
        decision = calculate_decision()
        if decision:
            st.session_state.last_decision = decision
            st.session_state.last_hand_context = build_hand_context()
            
            # Increment decisions counter
            session_id = session.get("id")
            if session_id:
                increment_session_stats(session_id, hands=0, decisions=1)
            
            st.session_state.decisions_requested += 1
            st.rerun()
    
    # End session button
    st.markdown("---")
    if st.button("🏁 End Session", use_container_width=True):
        st.session_state.session_mode = "ending"
        st.rerun()


def render_card_input():
    """Render card input section."""
    
    st.markdown("**Your Cards**")
    
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        # Card 1
        card1_rank = st.selectbox("Card 1 Rank", [""] + RANKS, key="card1_rank", label_visibility="collapsed")
        card1_suit = st.selectbox("Card 1 Suit", [""] + ["♥ Hearts", "♦ Diamonds", "♣ Clubs", "♠ Spades"], key="card1_suit", label_visibility="collapsed")
        
        if card1_rank and card1_suit:
            suit_map = {"♥ Hearts": "h", "♦ Diamonds": "d", "♣ Clubs": "c", "♠ Spades": "s"}
            st.session_state.our_cards[0] = card1_rank + suit_map.get(card1_suit, "")
    
    with col2:
        # Card 2
        card2_rank = st.selectbox("Card 2 Rank", [""] + RANKS, key="card2_rank", label_visibility="collapsed")
        card2_suit = st.selectbox("Card 2 Suit", [""] + ["♥ Hearts", "♦ Diamonds", "♣ Clubs", "♠ Spades"], key="card2_suit", label_visibility="collapsed")
        
        if card2_rank and card2_suit:
            suit_map = {"♥ Hearts": "h", "♦ Diamonds": "d", "♣ Clubs": "c", "♠ Spades": "s"}
            st.session_state.our_cards[1] = card2_rank + suit_map.get(card2_suit, "")
    
    with col3:
        if st.button("Clear", key="clear_cards"):
            st.session_state.our_cards = ["", ""]
            st.rerun()
    
    # Display cards
    cards = st.session_state.our_cards
    if cards[0] and cards[1]:
        st.markdown(f"**Your hand:** {format_card(cards[0])} {format_card(cards[1])}")


def render_action_facing():
    """Render action facing selection."""
    
    street = st.session_state.street
    
    if street == "preflop":
        st.markdown("**Action Before You**")
        
        action = st.radio(
            "Action",
            ["No one raised", "Someone raised", "I raised, someone 3-bet me", "Limper(s)"],
            key="preflop_action",
            label_visibility="collapsed"
        )
        
        if action == "No one raised":
            st.session_state.action_facing = "none"
            st.session_state.facing_bet = 0
        elif action == "Someone raised":
            st.session_state.action_facing = "raise"
            raise_amount = st.number_input(
                "Raise to ($)",
                min_value=0.0,
                value=6.0,
                step=1.0,
                key="raise_amount"
            )
            st.session_state.facing_bet = raise_amount
        elif action == "I raised, someone 3-bet me":
            st.session_state.action_facing = "3bet"
            three_bet_amount = st.number_input(
                "3-bet to ($)",
                min_value=0.0,
                value=18.0,
                step=1.0,
                key="three_bet_amount"
            )
            st.session_state.facing_bet = three_bet_amount
            st.session_state.we_are_aggressor = True
        elif action == "Limper(s)":
            st.session_state.action_facing = "limp"
            num_limpers = st.number_input(
                "How many limpers?",
                min_value=1,
                max_value=5,
                value=1,
                key="num_limpers"
            )
            st.session_state.num_limpers = num_limpers
    
    else:  # Post-flop
        st.markdown("**Action Before You**")
        
        action = st.radio(
            "Action",
            ["Checked to me", "Someone bet", "I bet, someone raised"],
            key="postflop_action",
            label_visibility="collapsed"
        )
        
        if action == "Checked to me":
            st.session_state.action_facing = "none"
            st.session_state.facing_bet = 0
        elif action == "Someone bet":
            st.session_state.action_facing = "bet"
            bet_amount = st.number_input(
                "Bet amount ($)",
                min_value=0.0,
                value=10.0,
                step=1.0,
                key="bet_amount"
            )
            st.session_state.facing_bet = bet_amount
        elif action == "I bet, someone raised":
            st.session_state.action_facing = "check_raise"
            raise_amount = st.number_input(
                "Raise to ($)",
                min_value=0.0,
                value=30.0,
                step=1.0,
                key="check_raise_amount"
            )
            st.session_state.facing_bet = raise_amount
            st.session_state.we_are_aggressor = True


def render_postflop_inputs():
    """Render post-flop specific inputs."""
    
    st.markdown("**Board Cards**")
    
    street = st.session_state.street
    num_board_cards = {"flop": 3, "turn": 4, "river": 5}.get(street, 3)
    
    cols = st.columns(5)
    for i in range(num_board_cards):
        with cols[i]:
            rank = st.selectbox(f"Board {i+1} Rank", [""] + RANKS, key=f"board_{i}_rank", label_visibility="collapsed")
            suit = st.selectbox(f"Board {i+1} Suit", [""] + ["♥", "♦", "♣", "♠"], key=f"board_{i}_suit", label_visibility="collapsed")
            
            if rank and suit:
                suit_map = {"♥": "h", "♦": "d", "♣": "c", "♠": "s"}
                st.session_state.board_cards[i] = rank + suit_map.get(suit, "")
    
    # Pot size
    st.markdown("**Pot Size**")
    pot_size = st.number_input(
        "Pot ($)",
        min_value=0.0,
        value=st.session_state.pot_size if st.session_state.pot_size > 0 else 10.0,
        step=5.0,
        key="pot_size_input"
    )
    st.session_state.pot_size = pot_size
    
    # Board texture
    st.markdown("**Board Texture**")
    texture = st.radio(
        "Texture",
        ["Dry (unconnected, rainbow)", "Semi-wet (some draws)", "Wet (connected, flush possible)", "Paired board"],
        key="board_texture",
        horizontal=True,
        label_visibility="collapsed"
    )
    texture_map = {
        "Dry (unconnected, rainbow)": "dry",
        "Semi-wet (some draws)": "semi_wet",
        "Wet (connected, flush possible)": "wet",
        "Paired board": "paired"
    }
    st.session_state.board_texture = texture_map.get(texture, "semi_wet")
    
    # Hand strength
    st.markdown("**Your Hand Strength**")
    strength = st.selectbox(
        "Hand Strength",
        [
            "Nuts / Near-nuts",
            "Monster (set, straight, flush, full house+)",
            "Two pair",
            "Overpair",
            "Top pair, top kicker",
            "Top pair",
            "Middle pair",
            "Bottom pair",
            "Combo draw (flush + straight)",
            "Flush draw",
            "Straight draw (open-ended)",
            "Gutshot",
            "Overcards",
            "Nothing (air)"
        ],
        key="hand_strength_select"
    )
    
    strength_map = {
        "Nuts / Near-nuts": "nuts",
        "Monster (set, straight, flush, full house+)": "monster",
        "Two pair": "two_pair",
        "Overpair": "overpair",
        "Top pair, top kicker": "tptk",
        "Top pair": "top_pair",
        "Middle pair": "middle_pair",
        "Bottom pair": "bottom_pair",
        "Combo draw (flush + straight)": "combo_draw",
        "Flush draw": "flush_draw",
        "Straight draw (open-ended)": "oesd",
        "Gutshot": "gutshot",
        "Overcards": "overcards",
        "Nothing (air)": "air"
    }
    st.session_state.hand_strength = strength_map.get(strength, "top_pair")


def validate_inputs() -> bool:
    """Validate that all required inputs are provided."""
    
    # Need both cards
    cards = st.session_state.our_cards
    if not cards[0] or not cards[1]:
        return False
    
    # Need position
    if not st.session_state.our_position:
        return False
    
    # Post-flop needs board cards and pot size
    if st.session_state.street != "preflop":
        num_required = {"flop": 3, "turn": 4, "river": 5}.get(st.session_state.street, 3)
        board = st.session_state.board_cards
        filled = sum(1 for c in board if c)
        if filled < num_required:
            return False
        if st.session_state.pot_size <= 0:
            return False
    
    return True


def build_hand_context() -> dict:
    """Build the hand context dictionary."""
    
    session = st.session_state.current_session
    
    return {
        "stakes": session.get("stakes", "$1/$2"),
        "bb_size": float(session.get("bb_size", 2.0)),
        "our_stack": st.session_state.our_stack,
        "our_cards": "".join(st.session_state.our_cards),
        "our_position": st.session_state.our_position,
        "street": st.session_state.street,
        "board": "".join([c for c in st.session_state.board_cards if c]),
        "pot_size": st.session_state.pot_size,
        "facing_bet": st.session_state.facing_bet,
        "action_facing": st.session_state.action_facing,
        "num_limpers": st.session_state.num_limpers,
        "villain_type": st.session_state.villain_type,
        "hand_strength": st.session_state.hand_strength,
        "board_texture": st.session_state.board_texture,
        "we_are_aggressor": st.session_state.we_are_aggressor,
    }


def calculate_decision():
    """Calculate the decision from the engine."""
    
    ctx = build_hand_context()
    
    # Determine hand strength for pre-flop
    if ctx["street"] == "preflop":
        hand = normalize_hand(ctx["our_cards"])
        hs = classify_preflop_hand(hand)
        ctx["hand_strength"] = hs.value
    
    # Map action facing to engine format
    action_map = {
        "none": "none",
        "raise": "raise",
        "3bet": "3bet",
        "limp": "limp",
        "bet": "bet",
        "check_raise": "check_raise",
    }
    
    try:
        decision = get_decision(
            stakes=ctx["stakes"],
            our_stack=ctx["our_stack"],
            villain_stack=ctx["our_stack"],  # Assume similar stack
            pot_size=ctx["pot_size"],
            facing_bet=ctx["facing_bet"],
            our_position=ctx["our_position"],
            villain_position=None,  # Unknown
            street=ctx["street"],
            our_hand=ctx["our_cards"],
            hand_strength=ctx["hand_strength"] or "playable",
            board=ctx["board"] or None,
            board_texture=ctx["board_texture"],
            num_players=2,
            num_limpers=ctx["num_limpers"],
            we_are_aggressor=ctx["we_are_aggressor"],
            action_facing=action_map.get(ctx["action_facing"], "none"),
            villain_type=ctx["villain_type"],
        )
        return decision
    except Exception as e:
        st.error(f"Error calculating decision: {e}")
        return None


def render_outcome_recording():
    """Render the outcome recording interface after a decision."""
    
    decision = st.session_state.last_decision
    context = st.session_state.last_hand_context
    
    # Display the decision
    render_decision_display(decision)
    
    st.markdown("---")
    st.markdown("### 📝 What Happened?")
    
    # Different UI based on action
    action = decision.action
    
    if action == Action.FOLD:
        st.markdown("You folded — good discipline saves money.")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Record Fold", type="primary", use_container_width=True, key="record_fold"):
                record_outcome("folded", 0)
        with col2:
            if st.button("← Change Input", use_container_width=True, key="change_fold"):
                st.session_state.last_decision = None
                st.rerun()
    
    else:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("✅ WIN", type="primary", use_container_width=True, key="record_win"):
                # Calculate win amount (pot + any bets)
                pot = context.get("pot_size", 0)
                facing = context.get("facing_bet", 0)
                win_amount = pot + facing if pot > 0 else decision.amount or 0
                record_outcome("won", win_amount)
        
        with col2:
            if st.button("❌ LOSS", use_container_width=True, key="record_loss"):
                # Loss amount is what we put in
                loss_amount = decision.amount if decision.amount else context.get("facing_bet", 0)
                record_outcome("lost", -loss_amount)
        
        with col3:
            if st.button("← Back", use_container_width=True, key="change_decision"):
                st.session_state.last_decision = None
                st.rerun()
    
    st.caption("Recording outcomes helps track your play quality and provides personalized feedback.")


def render_decision_display(decision):
    """Render the decision in a prominent display box."""
    
    action = decision.action
    display = decision.display
    explanation = decision.explanation
    
    # Determine box color
    if action == Action.FOLD:
        box_class = "fold"
    elif action == Action.ALL_IN:
        box_class = "allin"
    elif action in [Action.RAISE, Action.BET]:
        box_class = "aggressive"
    else:  # CALL, CHECK
        box_class = "passive"
    
    st.markdown(
        f"""
        <div class="decision-box {box_class}">
            <div class="decision-action">{display}</div>
            <div class="decision-explanation">{explanation}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def record_outcome(outcome: str, profit_loss: float):
    """Record hand outcome and show EV modal."""
    
    session = st.session_state.current_session
    context = st.session_state.last_hand_context
    decision = st.session_state.last_decision
    
    if not session:
        return
    
    session_id = session.get("id")
    user_id = st.session_state.get("user_db_id")
    
    # Record to database
    record_hand_outcome(
        session_id=session_id,
        user_id=user_id,
        outcome=outcome,
        profit_loss=profit_loss,
        pot_size=context.get("pot_size", 0),
        our_position=context.get("our_position", ""),
        street_reached=context.get("street", "preflop"),
        our_hand=context.get("our_cards"),
        board=context.get("board"),
        action_taken=decision.display if decision else None,
        recommendation_given=decision.display if decision else None,
        we_were_aggressor=context.get("we_are_aggressor", False),
    )
    
    # Update session stats
    increment_session_stats(session_id, hands=1, decisions=0)
    
    # Update local state
    st.session_state.hands_played += 1
    st.session_state.hand_outcomes.append({
        "outcome": outcome,
        "profit_loss": profit_loss,
        "street": context.get("street"),
        "position": context.get("our_position"),
    })
    
    # Update session P/L and stack
    if outcome == "won":
        st.session_state.session_pl += profit_loss
        st.session_state.our_stack += profit_loss
    elif outcome == "lost":
        st.session_state.session_pl += profit_loss  # profit_loss is already negative
        st.session_state.our_stack += profit_loss
    # Fold doesn't change P/L
    
    # Update sidebar
    update_sidebar_session_info(session, st.session_state.session_pl)
    
    # Queue the outcome modal
    queue_modal("outcome", {
        "outcome": outcome,
        "decision": decision,
        "hand_context": context,
        "action_taken": decision.display if decision else "",
        "profit_loss": profit_loss,
    })
    
    st.rerun()


# =============================================================================
# END SESSION
# =============================================================================

def render_end_session():
    """Render end session interface."""
    
    session = st.session_state.current_session
    if not session:
        st.session_state.session_mode = "setup"
        st.rerun()
        return
    
    st.title("🏁 End Session")
    
    # Show current stats
    duration = get_session_duration_minutes()
    session_pl = st.session_state.session_pl
    hands_played = st.session_state.hands_played
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Duration", f"{duration // 60}h {duration % 60}m")
    with col2:
        st.metric("Hands Played", hands_played)
    with col3:
        st.metric("Current P/L", format_money(session_pl))
    
    st.markdown("---")
    
    # Final stack input
    st.markdown("### Enter Your Final Stack")
    
    buy_in = float(session.get("buy_in_amount", 200))
    current_stack = st.session_state.our_stack
    
    final_stack = st.number_input(
        "Final Stack ($)",
        min_value=0.0,
        value=max(0.0, current_stack),
        step=10.0,
        help="Enter your final chip stack"
    )
    
    calculated_pl = final_stack - buy_in
    st.markdown(f"**Calculated P/L:** {format_money(calculated_pl)}")
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("✅ Confirm & End Session", type="primary", use_container_width=True):
            # End session in database
            session_id = session.get("id")
            end_reason = "manual"
            
            # Check if stop-loss/win was hit
            stakes = session.get("stakes", "$1/$2")
            stakes_info = STAKES_BUY_INS.get(stakes, {"buy_in": 200})
            standard_buy_in = stakes_info["buy_in"]
            
            profile = get_user_profile()
            user_mode = profile.get("user_mode", "balanced")
            mode_config = MODE_CONFIG.get(user_mode, MODE_CONFIG["balanced"])
            
            if calculated_pl <= -(standard_buy_in * mode_config["stop_loss_bi"]):
                end_reason = "stop_loss"
            elif calculated_pl >= standard_buy_in * mode_config["stop_win_bi"]:
                end_reason = "stop_win"
            elif duration >= 240:
                end_reason = "time_limit"
            
            ended_session = end_session(session_id, final_stack, end_reason)
            
            # Update bankroll
            user_id = st.session_state.get("user_db_id")
            current_bankroll = float(profile.get("current_bankroll", 0) or 0)
            
            if current_bankroll > 0:
                new_bankroll = current_bankroll + calculated_pl
                update_user_bankroll(user_id, new_bankroll)
                record_bankroll_change(
                    user_id=user_id,
                    bankroll_amount=new_bankroll,
                    change_amount=calculated_pl,
                    change_type="session_result",
                    session_id=session_id,
                    current_stakes=stakes,
                )
            
            # Get outcome summary
            summary = get_session_outcome_summary(session_id)
            
            # Queue session end modal
            queue_modal("session_end", {
                "duration_minutes": duration,
                "total_hands": hands_played,
                "session_pl": calculated_pl,
                "wins": summary.get("wins", 0),
                "losses": summary.get("losses", 0),
                "folds": summary.get("folds", 0),
                "bb_size": float(session.get("bb_size", 2.0)),
            })
            
            st.session_state.session_mode = "play"  # Show modal in play mode
            st.rerun()
    
    with col2:
        if st.button("← Back to Session", use_container_width=True):
            st.session_state.session_mode = "play"
            st.rerun()


# =============================================================================
# MAIN RENDER
# =============================================================================

def main():
    """Main render function."""
    
    mode = st.session_state.session_mode
    
    if mode == "setup":
        render_setup_mode()
    elif mode == "play":
        render_play_mode()
    elif mode == "ending":
        render_end_session()
    else:
        render_setup_mode()


if __name__ == "__main__":
    main()