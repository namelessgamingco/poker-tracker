"""
Test page for Phase 2+3+4: Full input component with decision engine integration.
Now supports two-table mode with proper decision routing.

Run with:
  Terminal 1: cd poker_input/frontend && npm run dev
  Terminal 2: POKER_INPUT_DEV=true streamlit run test_component.py
"""

import streamlit as st

st.set_page_config(page_title="Component Test", layout="wide")

from poker_input import poker_input
from engine import (
    get_decision,
    classify_preflop_hand,
    normalize_hand,
)

# The engine's create_game_state does HandStrength[name.upper()] (name lookup, not value lookup)
# So we need to pass the enum NAME (e.g. "top_pair_top_kicker") not the value (e.g. "tptk")
HAND_STRENGTH_VALUE_TO_NAME = {
    "premium": "premium",
    "strong": "strong",
    "playable": "playable",
    "marginal": "marginal",
    "trash": "trash",
    "monster": "monster",
    "nuts": "nuts",
    "two_pair": "two_pair",
    "overpair": "overpair",
    "tptk": "top_pair_top_kicker",
    "top_pair": "top_pair",
    "middle_pair": "middle_pair",
    "bottom_pair": "bottom_pair",
    "combo_draw": "combo_draw",
    "flush_draw": "flush_draw",
    "oesd": "oesd",
    "gutshot": "gutshot",
    "overcards": "overcards",
    "air": "air",
}

BOARD_TEXTURE_VALUE_TO_NAME = {
    "dry": "dry",
    "semi_wet": "semi_wet",
    "wet": "wet",
    "paired": "paired",
}


def parse_board_cards(board_str):
    """Parse board string like 'Kd7c2h' into list of (rank, suit) tuples."""
    cards = []
    if not board_str:
        return cards
    i = 0
    while i < len(board_str) - 1:
        rank = board_str[i].upper()
        suit = board_str[i + 1].lower()
        cards.append((rank, suit))
        i += 2
    return cards


def auto_classify_board_texture(board_str):
    """Classify board texture from board cards string."""
    cards = parse_board_cards(board_str)
    if len(cards) < 3:
        return "dry"

    ranks = [c[0] for c in cards]
    suits = [c[1] for c in cards]

    # Check for paired board
    if len(set(ranks)) < len(ranks):
        return "paired"

    # Check flush possibility (2+ same suit)
    suit_counts = {}
    for s in suits:
        suit_counts[s] = suit_counts.get(s, 0) + 1
    has_flush_draw = any(v >= 2 for v in suit_counts.values())
    has_flush = any(v >= 3 for v in suit_counts.values())

    # Check straight connectivity
    rank_values = {"A": 14, "K": 13, "Q": 12, "J": 11, "T": 10,
                   "9": 9, "8": 8, "7": 7, "6": 6, "5": 5, "4": 4, "3": 3, "2": 2}
    vals = sorted([rank_values.get(r, 0) for r in ranks])
    spread = vals[-1] - vals[0] if vals else 10
    connected = spread <= 4  # Cards within 4 ranks of each other

    if has_flush or (has_flush_draw and connected):
        return "wet"
    elif has_flush_draw or connected:
        return "semi_wet"
    else:
        return "dry"


def auto_classify_hand_strength(hand_str, board_str):
    """Classify hand strength from hole cards + board."""
    if not board_str or len(board_str) < 6:
        return "top_pair"  # fallback

    # Parse hole cards (format: "Ah Ks" or "AhKs")
    hand_clean = hand_str.replace(" ", "")
    if len(hand_clean) < 4:
        return "air"

    h1_rank = hand_clean[0].upper()
    h1_suit = hand_clean[1].lower()
    h2_rank = hand_clean[2].upper()
    h2_suit = hand_clean[3].lower()

    board_cards = parse_board_cards(board_str)
    board_ranks = [c[0] for c in board_cards]
    board_suits = [c[1] for c in board_cards]

    rank_values = {"A": 14, "K": 13, "Q": 12, "J": 11, "T": 10,
                   "9": 9, "8": 8, "7": 7, "6": 6, "5": 5, "4": 4, "3": 3, "2": 2}

    h1_val = rank_values.get(h1_rank, 0)
    h2_val = rank_values.get(h2_rank, 0)
    board_vals = sorted([rank_values.get(r, 0) for r in board_ranks], reverse=True)

    # Check for pocket pair hitting set
    if h1_rank == h2_rank:
        if h1_rank in board_ranks:
            return "monster"  # Set
        if h1_val > board_vals[0]:
            return "overpair"
        return "middle_pair"

    # Count how many hole cards match board ranks
    h1_matches = h1_rank in board_ranks
    h2_matches = h2_rank in board_ranks

    # Check for two pair
    if h1_matches and h2_matches:
        return "two_pair"

    # Check for top pair
    if h1_matches or h2_matches:
        matching_rank = h1_rank if h1_matches else h2_rank
        matching_val = rank_values.get(matching_rank, 0)
        kicker_val = h2_val if h1_matches else h1_val

        if matching_val == board_vals[0]:
            # Top pair — check kicker
            if kicker_val >= 12:  # A, K, Q kicker
                return "tptk"
            return "top_pair"
        elif len(board_vals) >= 2 and matching_val == board_vals[1]:
            return "middle_pair"
        else:
            return "bottom_pair"

    # Check for flush draw
    hand_suits = [h1_suit, h2_suit]
    for suit in set(hand_suits):
        suit_count = board_suits.count(suit) + hand_suits.count(suit)
        if suit_count >= 4:
            # Check for combo draw (flush draw + straight draw)
            all_vals = sorted([h1_val, h2_val] + board_vals)
            for i in range(len(all_vals) - 3):
                if all_vals[i + 3] - all_vals[i] <= 4:
                    return "combo_draw"
            return "flush_draw"

    # Check for straight draws
    all_vals = sorted(set([h1_val, h2_val] + board_vals))
    # Check for OESD (4 in a row)
    for i in range(len(all_vals) - 3):
        if all_vals[i + 3] - all_vals[i] == 3:
            return "oesd"
    # Check for gutshot (4 out of 5 in sequence)
    for i in range(len(all_vals) - 3):
        if all_vals[i + 3] - all_vals[i] == 4:
            return "gutshot"

    # Check for overcards
    if h1_val > board_vals[0] and h2_val > board_vals[0]:
        return "overcards"
    if h1_val > board_vals[0] or h2_val > board_vals[0]:
        return "overcards"

    return "air"

# Initialize session state
if "decision_result" not in st.session_state:
    st.session_state.decision_result = None
if "decision_table_id" not in st.session_state:
    st.session_state.decision_table_id = 1
if "game_state" not in st.session_state:
    st.session_state.game_state = None
if "hands_tested" not in st.session_state:
    st.session_state.hands_tested = 0
if "show_second_table" not in st.session_state:
    st.session_state.show_second_table = False
if "active_table" not in st.session_state:
    st.session_state.active_table = 1
if "primary_holds_table" not in st.session_state:
    st.session_state.primary_holds_table = 1
if "t2_game_state" not in st.session_state:
    st.session_state.t2_game_state = None
if "t2_step" not in st.session_state:
    st.session_state.t2_step = "position"
if "t2_decision" not in st.session_state:
    st.session_state.t2_decision = None
# NEW: Explicit table1 and table2 state
if "table1_game_state" not in st.session_state:
    st.session_state["table1_game_state"] = None
if "table1_step" not in st.session_state:
    st.session_state["table1_step"] = "position"
if "table1_decision" not in st.session_state:
    st.session_state["table1_decision"] = None
if "table1_board_entry_index" not in st.session_state:
    st.session_state["table1_board_entry_index"] = 0
if "table2_game_state" not in st.session_state:
    st.session_state["table2_game_state"] = None
if "table2_step" not in st.session_state:
    st.session_state["table2_step"] = "position"
if "table2_decision" not in st.session_state:
    st.session_state["table2_decision"] = None
if "table2_board_entry_index" not in st.session_state:
    st.session_state["table2_board_entry_index"] = 0

st.title("🧪 Poker Input Component — Phase 4 Test")
st.caption("Two-table mode with dynamic toggle")
st.markdown("---")

# Render the component — pass decision_table_id so component knows which table the decision is for
result = poker_input(
    mode="keyboard",
    stakes="$1/$2",
    bb_size=2.0,
    stack_size=200.0,
    decision_result=st.session_state.decision_result,
    decision_table_id=st.session_state.decision_table_id,
    show_second_table=st.session_state.show_second_table,
    active_table=st.session_state.active_table,
    primary_holds_table=st.session_state.primary_holds_table,
    # NEW: Explicit table1 and table2 data
    table1_game_state=st.session_state.get("table1_game_state"),
    table1_step=st.session_state.get("table1_step"),
    table1_decision=st.session_state.get("table1_decision"),
    table1_board_entry_index=st.session_state.get("table1_board_entry_index"),
    table2_game_state=st.session_state.get("table2_game_state"),
    table2_step=st.session_state.get("table2_step"),
    table2_decision=st.session_state.get("table2_decision"),
    table2_board_entry_index=st.session_state.get("table2_board_entry_index"),
    # Legacy - keep for backward compatibility
    t2_game_state=st.session_state.t2_game_state,
    t2_step=st.session_state.t2_step,
    t2_decision=st.session_state.t2_decision,
    restore_state=st.session_state.game_state,
)

st.markdown("---")

# Handle component output
if result is not None:
    msg_type = result.get("type", "")
    table_id = result.get("table_id", 1)  # Get table_id from component
    # Persist two-table state
    st.session_state.show_second_table = result.get("show_second_table", False)
    st.session_state.active_table = result.get("active_table", 1)
    st.session_state.primary_holds_table = result.get("primary_holds_table", 1)
    
    # NEW: Store BOTH tables' data explicitly
    if result.get("table1_game_state"):
        st.session_state["table1_game_state"] = result.get("table1_game_state")
    if result.get("table1_step"):
        st.session_state["table1_step"] = result.get("table1_step")
    if "table1_decision" in result:
        st.session_state["table1_decision"] = result.get("table1_decision")
    if "table1_board_entry_index" in result:
        st.session_state["table1_board_entry_index"] = result.get("table1_board_entry_index")
        
    if result.get("table2_game_state"):
        st.session_state["table2_game_state"] = result.get("table2_game_state")
    if result.get("table2_step"):
        st.session_state["table2_step"] = result.get("table2_step")
    if "table2_decision" in result:
        st.session_state["table2_decision"] = result.get("table2_decision")
    if "table2_board_entry_index" in result:
        st.session_state["table2_board_entry_index"] = result.get("table2_board_entry_index")
    
    # Legacy - keep for backward compatibility
    st.session_state.t2_game_state = result.get("t2_game_state")
    st.session_state.t2_step = result.get("t2_step", "position")
    st.session_state.t2_decision = result.get("t2_decision")

    if msg_type == "decision_request":
        hand_str = result.get("hand", "")
        street = result.get("street", "preflop")
        position = result.get("position", "BTN")

        if street == "preflop":
            normalized = normalize_hand(hand_str)
            hand_strength = classify_preflop_hand(normalized).value
            board_texture = None
        else:
            # Auto-compute board texture from board cards
            board_str = result.get("board") or ""
            board_texture = auto_classify_board_texture(board_str)
            # Auto-compute hand strength from hole cards + board
            hand_strength = auto_classify_hand_strength(hand_str, board_str)

        try:
            # Map auto-detected values to enum names the engine expects
            hs_name = HAND_STRENGTH_VALUE_TO_NAME.get(hand_strength, hand_strength)
            bt_name = BOARD_TEXTURE_VALUE_TO_NAME.get(board_texture, board_texture) if board_texture else None
            
            # Debug: show what we computed
            st.caption(f"Table {table_id} | Auto-detected: hand_strength={hand_strength} → {hs_name}, board_texture={board_texture} → {bt_name}")
            
            decision = get_decision(
                stakes="$1/$2",
                our_stack=200.0,
                villain_stack=200.0,
                pot_size=float(result.get("pot_size", 0) or 0),
                facing_bet=float(result.get("facing_bet", 0) or 0),
                our_position=position,
                villain_position=None,
                street=street,
                our_hand=hand_str,
                hand_strength=hs_name,
                board=result.get("board") or None,
                board_texture=bt_name,
                num_players=2,
                num_limpers=int(result.get("num_limpers", 0) or 0),
                we_are_aggressor=bool(result.get("we_are_aggressor", False)),
                action_facing=result.get("action_facing", "none"),
                villain_type=result.get("villain_type", "unknown"),
            )

            # Save the game state (persists across reruns)
            st.session_state.game_state = {
                "position": result.get("position"),
                "card1": result.get("card1"),
                "card2": result.get("card2"),
                "street": result.get("street"),
                "action_facing": result.get("action_facing"),
                "facing_bet": result.get("facing_bet"),
                "board": result.get("board"),
                "pot_size": result.get("pot_size"),
                "board_texture": result.get("board_texture"),
                "hand_strength": result.get("hand_strength"),
                "villain_type": result.get("villain_type"),
            }

            # Save the decision AND the table_id it's for
            st.session_state.decision_result = {
                "action": decision.action.value,
                "amount": decision.amount,
                "display": decision.display,
                "explanation": decision.explanation,
                "calculation": decision.calculation,
                "confidence": decision.confidence,
            }
            st.session_state.decision_table_id = table_id  # Track which table this decision is for
            st.session_state.hands_tested += 1
            st.rerun()

        except Exception as e:
            st.error(f"Engine error: {e}")
            st.json(result)

    elif msg_type == "new_hand":
        st.session_state.decision_result = None
        st.session_state.game_state = None
        st.rerun()

    elif msg_type == "hand_complete":
        # Log the outcome for testing
        outcome = result.get("outcome", "unknown")
        action_taken = result.get("action_taken", "")
        hand_context = result.get("hand_context", {})
        st.toast(f"✅ Hand recorded: {outcome.upper()} | Action: {action_taken} | Position: {hand_context.get('position', '?')}")
        st.session_state.decision_result = None
        st.session_state.game_state = None
        st.session_state.hands_tested += 1
        st.rerun()

    elif msg_type == "continue_street":
        # Clear decision but keep game state, update street
        gs = st.session_state.game_state or {}
        gs["street"] = result.get("street", "flop")
        # If we raised preflop, we're the aggressor on the flop
        if gs.get("action_facing") == "none":
            gs["we_are_aggressor"] = True
        st.session_state.game_state = gs
        st.session_state.decision_result = None
        st.rerun()

    else:
        st.json(result)

# Stats
st.markdown("---")
col1, col2 = st.columns(2)
with col1:
    st.metric("Hands Tested", st.session_state.hands_tested)
with col2:
    st.metric("Mode", "Keyboard (+ Table 2 toggle)")

with st.expander("Debug: Raw Component Data"):
    st.json(result if result else {"status": "waiting for input"})
    if st.session_state.game_state:
        st.markdown("**Persisted Game State:**")
        st.json(st.session_state.game_state)
    if st.session_state.decision_result:
        st.markdown("**Last Decision (for Table {}):**".format(st.session_state.decision_table_id))
        st.json(st.session_state.decision_result)