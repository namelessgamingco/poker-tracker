# engine.py — Poker Decision Engine
# Complete decision engine for Texas Hold'em No-Limit 6-Max Cash Games
# Based on specs 1-14 from the master specification

from __future__ import annotations

from typing import Optional, Tuple, List
from dataclasses import dataclass
from enum import Enum


# =============================================================================
# ENUMS AND DATA STRUCTURES
# =============================================================================

class Position(Enum):
    UTG = "UTG"
    HJ = "HJ"
    CO = "CO"
    BTN = "BTN"
    SB = "SB"
    BB = "BB"


class Street(Enum):
    PREFLOP = "preflop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"


class Action(Enum):
    FOLD = "FOLD"
    CHECK = "CHECK"
    CALL = "CALL"
    BET = "BET"
    RAISE = "RAISE"
    ALL_IN = "ALL-IN"


class HandStrength(Enum):
    # Pre-flop categories
    PREMIUM = "premium"           # AA, KK, QQ, AKs, AKo
    STRONG = "strong"             # JJ, TT, AQs, AQo, AJs
    PLAYABLE = "playable"         # 99-22, suited connectors, suited aces
    MARGINAL = "marginal"         # Weak suited hands
    TRASH = "trash"               # Everything else
    
    # Post-flop categories  
    NUTS = "nuts"                 # Best possible hand
    MONSTER = "monster"           # Sets, straights, flushes, full house+
    TWO_PAIR = "two_pair"
    OVERPAIR = "overpair"         # Pair higher than board
    TOP_PAIR_TOP_KICKER = "tptk"
    TOP_PAIR = "top_pair"
    MIDDLE_PAIR = "middle_pair"
    BOTTOM_PAIR = "bottom_pair"
    COMBO_DRAW = "combo_draw"     # Flush draw + straight draw (12+ outs)
    FLUSH_DRAW = "flush_draw"     # 9 outs
    OESD = "oesd"                 # Open-ended straight draw (8 outs)
    GUTSHOT = "gutshot"           # 4 outs
    OVERCARDS = "overcards"       # Two cards higher than board
    AIR = "air"                   # Nothing


class BoardTexture(Enum):
    DRY = "dry"           # K-7-2 rainbow, unconnected
    SEMI_WET = "semi_wet" # K-J-5 two-tone or some connectivity
    WET = "wet"           # J-T-8 two-tone, highly connected
    PAIRED = "paired"     # Board has a pair


class VillainType(Enum):
    UNKNOWN = "unknown"   # Default - play standard
    FISH = "fish"         # Loose passive - bet bigger for value
    REG = "reg"           # Tight aggressive - play standard


class ActionFacing(Enum):
    NONE = "none"                 # No action, we can open or check
    LIMP = "limp"                 # One or more limpers
    RAISE = "raise"               # Facing a raise
    THREE_BET = "3bet"            # Facing a 3-bet (we opened, they raised)
    FOUR_BET = "4bet"             # Facing a 4-bet
    BET = "bet"                   # Post-flop: facing a bet
    CHECK_RAISE = "check_raise"   # We bet, they check-raised


@dataclass
class GameState:
    """Complete game state for decision making."""
    # Stakes
    stakes: str                   # '$1/$2', '$2/$5', etc.
    bb_size: float
    sb_size: float
    
    # Stacks
    our_stack: float
    villain_stack: float
    effective_stack: float        # min(our_stack, villain_stack)
    effective_stack_bb: float     # In big blinds
    
    # Pot and betting
    pot_size: float
    facing_bet: float             # Amount we need to call (0 if no bet)
    
    # Position
    our_position: Position
    villain_position: Optional[Position]
    
    # Street
    street: Street
    
    # Hand info
    our_hand: str                 # 'AhKs', 'QcQd', etc.
    hand_strength: HandStrength
    
    # Board (post-flop)
    board: Optional[str]          # 'Kh7c2d' etc.
    board_texture: Optional[BoardTexture]
    
    # Context
    num_players: int              # Players in hand
    num_limpers: int              # Number of limpers (pre-flop)
    we_are_aggressor: bool        # Did we make the last aggressive action?
    action_facing: ActionFacing   # What action are we facing?
    
    # Villain
    villain_type: VillainType
    
    # Calculated
    spr: Optional[float]          # Stack-to-pot ratio (post-flop)


@dataclass
class BluffContext:
    """Metadata for bluff-eligible hands."""
    spot_type: str              # 'river_barrel', 'river_probe', 'dry_board_cbet'
    delivery: str               # 'choice' or 'auto'
    recommended_action: str     # 'BET' or 'CHECK'
    bet_amount: float
    pot_size: float
    ev_of_bet: float
    ev_of_check: float          # Usually 0
    break_even_pct: float       # Fold % needed to break even
    estimated_fold_pct: float   # Population fold frequency
    explanation_bet: str        # Plain English text for BET option
    explanation_check: str      # Plain English text for CHECK option


@dataclass
class Decision:
    """Complete decision output."""
    action: Action
    amount: Optional[float]       # None for FOLD/CHECK
    display: str                  # "RAISE TO $12.00" - shown to user
    explanation: str              # Why this action
    calculation: Optional[str]    # Math breakdown (optional display)
    confidence: float             # 0.0 to 1.0
    # Bluff context (None for non-bluff hands)
    bluff_context: Optional[BluffContext] = None
    # Alternative decision for choice spots (None for single-answer)
    alternative: Optional['Decision'] = None


# =============================================================================
# STAKES CONFIGURATION
# =============================================================================

STAKES_CONFIG = {
    "$0.50/$1": {"sb": 0.50, "bb": 1.00, "buy_in": 100},
    "$1/$2": {"sb": 1.00, "bb": 2.00, "buy_in": 200},
    "$2/$5": {"sb": 2.00, "bb": 5.00, "buy_in": 500},
    "$5/$10": {"sb": 5.00, "bb": 10.00, "buy_in": 1000},
    "$10/$20": {"sb": 10.00, "bb": 20.00, "buy_in": 2000},
    "$25/$50": {"sb": 25.00, "bb": 50.00, "buy_in": 5000},
}


# =============================================================================
# HAND CLASSIFICATION
# =============================================================================

# Premium hands (top ~5%)
PREMIUM_HANDS = {
    "AA", "KK", "QQ", "AKs", "AKo"
}

# Strong hands (top ~10%)
STRONG_HANDS = {
    "JJ", "TT", "AQs", "AQo", "AJs", "KQs"
}

# 3-bet value hands by position
THREE_BET_VALUE = {
    "AA", "KK", "QQ", "JJ", "TT", "AKs", "AKo", "AQs", "AQo", "AJs", "KQs"
}

# 3-bet bluff hands (blockers)
THREE_BET_BLUFF = {
    "A5s", "A4s", "A3s", "A2s", "76s", "65s", "54s"
}

# 4-bet value hands
FOUR_BET_VALUE = {
    "AA", "KK", "QQ", "AKs", "AKo"
}

# Call 4-bet hands
CALL_FOUR_BET = {
    "JJ", "TT", "AQs"
}

# TIER1-FIX: Fish sizing multiplier — +20% on all postflop value bets vs fish
FISH_SIZE_MULT = 1.20

# Hand strength display names — premium user-facing text
HAND_DISPLAY = {
    "premium": "a premium hand",
    "strong": "a strong hand",
    "playable": "a playable hand",
    "marginal": "a marginal hand",
    "trash": "a weak hand",
    "nuts": "the nuts",
    "monster": "a monster hand",
    "two_pair": "two pair",
    "overpair": "an overpair",
    "tptk": "top pair, top kicker",
    "top_pair": "top pair",
    "middle_pair": "middle pair",
    "bottom_pair": "bottom pair",
    "combo_draw": "a combo draw",
    "flush_draw": "a flush draw",
    "oesd": "an open-ended straight draw",
    "gutshot": "a gutshot draw",
    "overcards": "overcards",
    "air": "nothing",
}

def _hs(hand_strength) -> str:
    """Get premium display name for hand strength."""
    val = hand_strength.value if hasattr(hand_strength, 'value') else str(hand_strength)
    return HAND_DISPLAY.get(val, val)

# Open ranges by position (hands to open-raise with)
# Format: set of hand strings
OPEN_RANGES = {
    Position.UTG: {
        "AA", "KK", "QQ", "JJ", "TT", "99", "88", "77",
        "AKs", "AQs", "AJs", "ATs", "KQs", "KJs", "KTs", "QJs",
        "AKo", "AQo", "AJo"
    },
    Position.HJ: {
        "AA", "KK", "QQ", "JJ", "TT", "99", "88", "77", "66",
        "AKs", "AQs", "AJs", "ATs", "A9s", "KQs", "KJs", "KTs", "QJs", "QTs", "JTs",
        "AKo", "AQo", "AJo", "KQo"
    },
    Position.CO: {
        "AA", "KK", "QQ", "JJ", "TT", "99", "88", "77", "66", "55", "44",
        "AKs", "AQs", "AJs", "ATs", "A9s", "A8s", "A7s", "A6s", "A5s", "A4s", "A3s", "A2s",
        "KQs", "KJs", "KTs", "K9s", "QJs", "QTs", "Q9s", "JTs", "J9s", "T9s", "98s", "87s", "76s", "65s",
        "AKo", "AQo", "AJo", "ATo", "KQo", "KJo", "QJo"
    },
    Position.BTN: {
        "AA", "KK", "QQ", "JJ", "TT", "99", "88", "77", "66", "55", "44", "33", "22",
        "AKs", "AQs", "AJs", "ATs", "A9s", "A8s", "A7s", "A6s", "A5s", "A4s", "A3s", "A2s",
        "KQs", "KJs", "KTs", "K9s", "K8s", "K7s", "K6s", "K5s",
        "QJs", "QTs", "Q9s", "Q8s", "JTs", "J9s", "J8s", "T9s", "T8s", "98s", "97s", "87s", "86s", "76s", "75s", "65s", "64s", "54s", "53s", "43s",
        "AKo", "AQo", "AJo", "ATo", "A9o", "KQo", "KJo", "KTo", "QJo", "QTo", "JTo"
    },
    Position.SB: {
        "AA", "KK", "QQ", "JJ", "TT", "99", "88", "77", "66", "55", "44", "33", "22",
        "AKs", "AQs", "AJs", "ATs", "A9s", "A8s", "A7s", "A6s", "A5s", "A4s", "A3s", "A2s",
        "KQs", "KJs", "KTs", "K9s", "K8s", "K7s", "K6s",
        "QJs", "QTs", "Q9s", "Q8s", "JTs", "J9s", "J8s", "T9s", "T8s", "98s", "97s", "87s", "86s", "76s", "75s", "65s", "64s", "54s",
        "AKo", "AQo", "AJo", "ATo", "A9o", "KQo", "KJo", "KTo", "QJo", "QTo", "JTo"
    },
}

# BB defense ranges (hands to call or 3-bet vs opens)
BB_DEFENSE_3BET = {
    Position.UTG: {"AA", "KK", "QQ", "AKs"},
    Position.HJ: {"AA", "KK", "QQ", "AKs", "AKo"},
    Position.CO: {"AA", "KK", "QQ", "JJ", "AKs", "AKo", "AQs", "A5s"},
    Position.BTN: {"AA", "KK", "QQ", "JJ", "TT", "AKs", "AKo", "AQs", "AQo", "A5s", "A4s"},
    Position.SB: {"AA", "KK", "QQ", "JJ", "TT", "99", "AKs", "AKo", "AQs", "AQo", "AJs", "A5s", "A4s", "A3s"},
}


def normalize_hand(hand: str) -> str:
    """
    Normalize hand string to standard format.
    
    Input formats:
        'AhKs', 'Ah Ks', 'AK suited', 'AKs', 'AKo', 'AA'
    
    Output format:
        'AKs', 'AKo', 'AA' (no suits, just suited/offsuit/pair indicator)
    """
    if not hand:
        return ""
    
    hand = hand.strip().upper().replace(" ", "")
    
    # Already in correct format
    if len(hand) == 2:
        return hand  # Pair like 'AA'
    if len(hand) == 3 and hand[2] in ('S', 'O'):
        return hand[0:2] + hand[2].lower()
    
    # Extract ranks from 'AhKs' format
    if len(hand) == 4:
        rank1 = hand[0]
        suit1 = hand[1].lower()
        rank2 = hand[2]
        suit2 = hand[3].lower()
        
        # Pair
        if rank1 == rank2:
            return rank1 + rank2
        
        # Order ranks (higher first)
        rank_order = "AKQJT98765432"
        if rank_order.index(rank1) > rank_order.index(rank2):
            rank1, rank2 = rank2, rank1
            suit1, suit2 = suit2, suit1
        
        # Suited or offsuit
        if suit1 == suit2:
            return rank1 + rank2 + "s"
        else:
            return rank1 + rank2 + "o"
    
    return hand


def classify_preflop_hand(hand: str) -> HandStrength:
    """Classify a pre-flop hand into strength categories."""
    h = normalize_hand(hand)
    
    if h in PREMIUM_HANDS:
        return HandStrength.PREMIUM
    if h in STRONG_HANDS:
        return HandStrength.STRONG
    
    # Pairs 99-22
    if len(h) == 2 and h[0] == h[1]:
        rank = h[0]
        if rank in "AKQJT":
            return HandStrength.STRONG
        if rank in "98765":
            return HandStrength.PLAYABLE
        return HandStrength.MARGINAL
    
    # Suited aces
    if len(h) == 3 and h[0] == 'A' and h[2] == 's':
        return HandStrength.PLAYABLE
    
    # Suited connectors
    if len(h) == 3 and h[2] == 's':
        rank_order = "AKQJT98765432"
        r1 = rank_order.index(h[0])
        r2 = rank_order.index(h[1])
        gap = abs(r1 - r2)
        if gap <= 2:  # Connected or 1-gap
            return HandStrength.PLAYABLE
    
    # Broadway cards
    if h[0] in "AKQJT" and h[1] in "AKQJT":
        return HandStrength.PLAYABLE
    
    return HandStrength.TRASH


# =============================================================================
# SIZING CALCULATIONS
# =============================================================================

def calculate_open_size(position: Position, bb_size: float, num_limpers: int = 0, villain_is_fish: bool = False) -> float:
    """
    Calculate exact open raise amount.
    
    Sizing from spec:
        UTG-CO: 3 BB
        BTN-SB: 2.5 BB
        +1 BB per limper
        +0.5 BB vs fish (TIER1-FIX)
    """
    if position in [Position.UTG, Position.HJ, Position.CO]:
        base_multiplier = 3.0
    else:  # BTN, SB
        base_multiplier = 2.5
    
    # TIER1-FIX: Size up vs fish — they call too much, bigger sizing = more value
    if villain_is_fish:
        base_multiplier += 0.5
    
    total_bb = base_multiplier + num_limpers
    return round(bb_size * total_bb, 2)


def calculate_3bet_size(
    villain_raise: float, 
    we_have_position: bool, 
    villain_is_fish: bool = False
) -> float:
    """
    Calculate exact 3-bet amount.
    
    Sizing from spec:
        In position: 3x their open
        Out of position: 3.5x their open
        vs Fish: 4x their open
    """
    if villain_is_fish:
        multiplier = 4.0
    elif we_have_position:
        multiplier = 3.0
    else:
        multiplier = 3.5
    
    return round(villain_raise * multiplier, 2)


def calculate_4bet_size(villain_3bet: float, our_stack: float) -> Tuple[float, bool]:
    """
    Calculate 4-bet amount.
    
    From spec:
        Standard: 2.2-2.5x their 3-bet
        All-in if 4-bet would be >40% of stack
    
    Returns: (amount, is_all_in)
    """
    standard = round(villain_3bet * 2.3, 2)
    
    if standard > our_stack * 0.4:
        return round(our_stack, 2), True
    
    return standard, False


def calculate_iso_raise_size(bb_size: float, num_limpers: int) -> float:
    """
    Calculate isolation raise size vs limpers.
    
    From spec: 4 BB + 1 BB per limper
    """
    total_bb = 4 + num_limpers
    return round(bb_size * total_bb, 2)


def calculate_cbet_size(pot_size: float, board_texture: BoardTexture, villain_is_fish: bool = False) -> Tuple[float, float]:
    """
    Calculate c-bet size based on board texture.
    
    Returns: (bet_amount, percentage)
    
    From spec:
        Dry: 33% pot
        Semi-wet: 50% pot
        Wet: 66% pot
        Paired: 33-50% pot (use 40%)
        vs Fish: +20% sizing (TIER1-FIX)
    """
    if board_texture == BoardTexture.DRY:
        pct = 0.33
    elif board_texture == BoardTexture.SEMI_WET:
        pct = 0.50
    elif board_texture == BoardTexture.WET:
        pct = 0.66
    elif board_texture == BoardTexture.PAIRED:
        pct = 0.40
    else:
        pct = 0.50  # Default
    
    # TIER1-FIX: Larger sizing vs fish — they call too wide
    if villain_is_fish:
        pct = min(pct * FISH_SIZE_MULT, 1.0)
    
    return round(pot_size * pct, 2), pct


def calculate_value_bet_size(
    pot_size: float, 
    street: Street, 
    hand_strength: HandStrength,
    villain_is_fish: bool = False
) -> Tuple[float, float]:
    """
    Calculate value bet size.
    
    Returns: (bet_amount, percentage)
    
    From spec:
        Turn: 66-75% pot for monsters, 50-66% for top pair
        River: 66-100% pot for value
        vs Fish: +20% sizing (TIER1-FIX)
    """
    if street == Street.RIVER:
        if hand_strength in [HandStrength.NUTS, HandStrength.MONSTER]:
            pct = 1.00  # TIER2-FIX: Overbet river with nuts/monster per spec 12
        elif hand_strength in [HandStrength.TWO_PAIR, HandStrength.OVERPAIR, HandStrength.TOP_PAIR_TOP_KICKER]:
            pct = 0.66
        else:
            pct = 0.50  # Thin value
    else:  # Turn
        if hand_strength in [HandStrength.NUTS, HandStrength.MONSTER]:
            pct = 0.70
        elif hand_strength in [HandStrength.TWO_PAIR, HandStrength.OVERPAIR, HandStrength.TOP_PAIR_TOP_KICKER]:
            pct = 0.60
        else:
            pct = 0.50
    
    # TIER1-FIX: Larger sizing vs fish — they call too wide
    if villain_is_fish:
        pct = min(pct * FISH_SIZE_MULT, 1.0)
    
    return round(pot_size * pct, 2), pct


def calculate_check_raise_size(facing_bet: float, villain_is_fish: bool = False) -> float:
    """
    Calculate check-raise size.
    
    From spec: 3x their bet (3.5x vs fish — TIER1-FIX)
    """
    multiplier = 3.5 if villain_is_fish else 3.0
    return round(facing_bet * multiplier, 2)


def calculate_pot_odds(pot_size: float, call_amount: float) -> float:
    """
    Calculate pot odds as equity needed to call.
    
    Formula: call / (pot + call + call)
    
    Reference:
        33% bet = 20% equity needed
        50% bet = 25% equity needed
        66% bet = 29% equity needed
        100% bet = 33% equity needed
    """
    if call_amount <= 0:
        return 0.0
    
    total_pot = pot_size + call_amount + call_amount
    return round(call_amount / total_pot, 2)


def get_draw_equity(hand_strength: HandStrength, street: Street) -> float:
    """
    Get draw equity based on hand type and street.
    
    From spec:
        Flush draw: 36% flop, 18% turn
        OESD: 32% flop, 16% turn
        Gutshot: 16% flop, 8% turn
        Combo draw: 45% flop, 30% turn
    """
    equity_map = {
        (HandStrength.COMBO_DRAW, Street.FLOP): 0.45,
        (HandStrength.COMBO_DRAW, Street.TURN): 0.30,
        (HandStrength.FLUSH_DRAW, Street.FLOP): 0.36,
        (HandStrength.FLUSH_DRAW, Street.TURN): 0.18,
        (HandStrength.OESD, Street.FLOP): 0.32,
        (HandStrength.OESD, Street.TURN): 0.16,
        (HandStrength.GUTSHOT, Street.FLOP): 0.16,
        (HandStrength.GUTSHOT, Street.TURN): 0.08,
    }
    
    return equity_map.get((hand_strength, street), 0.0)


# TIER1-FIX: Helper to check if villain is fish
def _is_fish(state: GameState) -> bool:
    """Check if villain is identified as fish."""
    return state.villain_type == VillainType.FISH


# =============================================================================
# SERIALIZATION — Decision to Dict for React Component
# =============================================================================

def decision_to_dict(decision: Decision) -> dict:
    """
    Serialize Decision to dict for React component prop.
    
    This is the bridge between engine.py and the React component.
    The Play Session page calls decision_to_dict(decision) and passes
    the result as decision_result to poker_input().
    """
    result = {
        "action": decision.display.split()[0],  # "BET", "CHECK", "FOLD", etc.
        "amount": decision.amount,
        "display": decision.display,
        "explanation": decision.explanation,
        "calculation": decision.calculation,
        "confidence": decision.confidence,
    }
    
    if decision.bluff_context:
        ctx = decision.bluff_context
        result["bluff_context"] = {
            "spot_type": ctx.spot_type,
            "delivery": ctx.delivery,
            "recommended_action": ctx.recommended_action,
            "bet_amount": ctx.bet_amount,
            "pot_size": ctx.pot_size,
            "ev_of_bet": ctx.ev_of_bet,
            "ev_of_check": ctx.ev_of_check,
            "break_even_pct": ctx.break_even_pct,
            "estimated_fold_pct": ctx.estimated_fold_pct,
            "explanation_bet": ctx.explanation_bet,
            "explanation_check": ctx.explanation_check,
        }
    
    if decision.alternative:
        result["alternative"] = decision_to_dict(decision.alternative)
    
    return result


# =============================================================================
# MAIN DECISION ENGINE
# =============================================================================

class PokerDecisionEngine:
    """
    The unified poker decision engine.
    
    Takes complete game state, returns exact decision with exact amount.
    One answer. No ambiguity.
    """
    
    def __init__(self):
        pass
    
    def get_decision(self, state: GameState) -> Decision:
        """
        Main entry point - get the exact decision.
        
        Args:
            state: Complete game state
            
        Returns:
            Decision with exact action and amount
        """
        # Check for push/fold mode (very short stack)
        if state.effective_stack_bb < 20:
            return self._push_fold_decision(state)
        
        # Route to correct street handler
        if state.street == Street.PREFLOP:
            # TIER2-FIX: Short stack mode (20-50BB) — more 3-bet/fold, less flatting
            if state.effective_stack_bb < 50:
                return self._short_stack_preflop(state)
            return self._preflop_decision(state)
        else:
            return self._postflop_decision(state)
    
    # -------------------------------------------------------------------------
    # PRE-FLOP DECISIONS
    # -------------------------------------------------------------------------
    
    def _preflop_decision(self, state: GameState) -> Decision:
        """Handle all pre-flop decisions."""
        
        hand = normalize_hand(state.our_hand)
        
        # Facing 4-bet
        if state.action_facing == ActionFacing.FOUR_BET:
            return self._facing_4bet(state, hand)
        
        # Facing 3-bet (we opened, they raised)
        if state.action_facing == ActionFacing.THREE_BET:
            return self._facing_3bet(state, hand)
        
        # Facing open raise
        if state.action_facing == ActionFacing.RAISE:
            return self._facing_open(state, hand)
        
        # Facing limp(s)
        if state.action_facing == ActionFacing.LIMP:
            return self._facing_limp(state, hand)
        
        # No action yet - we can open
        if state.action_facing == ActionFacing.NONE:
            return self._open_decision(state, hand)
        
        # Default fold
        return Decision(
            action=Action.FOLD,
            amount=None,
            display="FOLD",
            explanation="Check if possible, otherwise fold. No clear edge here.",
            calculation=None,
            confidence=0.8
        )
    
    def _open_decision(self, state: GameState, hand: str) -> Decision:
        """Should we open raise?"""
        
        position = state.our_position
        
        # BB can't open (already posted)
        if position == Position.BB:
            return Decision(
                action=Action.CHECK,
                amount=None,
                display="CHECK",
                explanation="Check. Free flop from the big blind — see what comes.",
                calculation=None,
                confidence=0.95
            )
        
        # Check if hand is in our open range for this position
        open_range = OPEN_RANGES.get(position, set())
        
        if hand in open_range:
            # TIER1-FIX: Pass fish flag to open sizing (+0.5 BB vs fish)
            fish = _is_fish(state)
            amount = calculate_open_size(position, state.bb_size, 0, fish)
            base = 3.0 if position in [Position.UTG, Position.HJ, Position.CO] else 2.5
            if fish:
                base += 0.5
            return Decision(
                action=Action.RAISE,
                amount=amount,
                display=f"RAISE TO ${amount:.2f}",
                explanation=f"Open-raise from {position.value}. You're ahead of most hands — raise and take control.",
                calculation=f"{'Sized up against weaker opponent' if fish else 'Standard open from ' + position.value}",
                confidence=0.90
            )
        
        # Hand not in range - fold (or complete from SB)
        if position == Position.SB:
            # Could complete with some speculative hands, but folding is fine
            return Decision(
                action=Action.FOLD,
                amount=None,
                display="FOLD",
                explanation=f"Fold — {hand} doesn't play well from the small blind.",
                calculation=None,
                confidence=0.85
            )
        
        return Decision(
            action=Action.FOLD,
            amount=None,
            display="FOLD",
            explanation=f"Fold from {position.value}. {hand} isn't profitable here — be patient.",
            calculation=None,
            confidence=0.90
        )
    
    def _facing_limp(self, state: GameState, hand: str) -> Decision:
        """Facing one or more limpers."""
        
        hand_strength = classify_preflop_hand(hand)
        
        # Strong hands - isolate
        if hand_strength in [HandStrength.PREMIUM, HandStrength.STRONG]:
            amount = calculate_iso_raise_size(state.bb_size, state.num_limpers)
            return Decision(
                action=Action.RAISE,
                amount=amount,
                display=f"RAISE TO ${amount:.2f}",
                explanation=f"Iso-raise with {hand}. Punish the limper — make them pay to see a flop.",
                calculation=f"Iso-raise: sized to punish the limper{"s" if state.num_limpers > 1 else ""}",
                confidence=0.90
            )
        
        # Playable hands - iso-raise if hand is in our open range for this position
        # BUG FIX: Previously only iso'd from BTN/CO. If we'd open-raise it, we should iso-raise over limpers.
        if hand_strength == HandStrength.PLAYABLE:
            open_range = OPEN_RANGES.get(state.our_position, set())
            normalized = normalize_hand(state.our_hand)
            if state.our_position == Position.BB:
                # BB: check with playable hands to see cheap flop
                return Decision(
                    action=Action.CHECK,
                    amount=None,
                    display="CHECK",
                    explanation=f"Check your option. See a free flop and re-evaluate.",
                    calculation=None,
                    confidence=0.85
                )
            elif normalized in open_range:
                # In our open range for this position — iso-raise
                amount = calculate_iso_raise_size(state.bb_size, state.num_limpers)
                return Decision(
                    action=Action.RAISE,
                    amount=amount,
                    display=f"RAISE TO ${amount:.2f}",
                    explanation=f"Raise with {hand}. Don't let them see a cheap flop — make them pay.",
                    calculation=f"Iso-raise sized for {state.num_limpers} limper{"s" if state.num_limpers > 1 else ""}",
                    confidence=0.80
                )
        
        # Marginal hands - limp behind from button only
        if hand_strength == HandStrength.MARGINAL and state.our_position == Position.BTN:
            return Decision(
                action=Action.CALL,
                amount=state.bb_size,
                display=f"CALL ${state.bb_size:.2f}",
                explanation=f"Limp behind. See a cheap flop and try to connect.",
                calculation=None,
                confidence=0.70
            )
        
        # BB with limpers
        if state.our_position == Position.BB:
            if hand_strength in [HandStrength.PREMIUM, HandStrength.STRONG]:
                amount = calculate_iso_raise_size(state.bb_size, state.num_limpers)
                return Decision(
                    action=Action.RAISE,
                    amount=amount,
                    display=f"RAISE TO ${amount:.2f}",
                    explanation=f"Raise from the big blind with {hand}. Charge the limpers.",
                    calculation=f"Iso-raise sized for {state.num_limpers} limper{"s" if state.num_limpers > 1 else ""}",
                    confidence=0.90
                )
            else:
                return Decision(
                    action=Action.CHECK,
                    amount=None,
                    display="CHECK",
                    explanation="Check. Nothing worth raising — take a free flop.",
                    calculation=None,
                    confidence=0.90
                )
        
        return Decision(
            action=Action.FOLD,
            amount=None,
            display="FOLD",
            explanation=f"Fold. {hand} isn't profitable here, even against limpers.",
            calculation=None,
            confidence=0.85
        )
    
    def _facing_open(self, state: GameState, hand: str) -> Decision:
        """Facing an open raise."""
        
        hand_strength = classify_preflop_hand(hand)
        villain_pos = state.villain_position
        we_have_position = self._have_position(state.our_position, villain_pos)
        is_fish = state.villain_type == VillainType.FISH
        
        # BB defense
        if state.our_position == Position.BB:
            return self._bb_defense(state, hand, hand_strength, villain_pos, is_fish)
        
        # 3-bet with value hands
        if hand in THREE_BET_VALUE:
            amount = calculate_3bet_size(state.facing_bet, we_have_position, is_fish)
            
            # TIER2-FIX: Squeeze sizing — add +1x per caller between raiser and us
            # num_limpers represents callers when action_facing is RAISE
            if state.num_limpers > 0:
                squeeze_add = state.facing_bet * state.num_limpers
                amount = round(amount + squeeze_add, 2)
            
            # Check if we should 4-bet size (short effective stacks)
            if amount > state.effective_stack * 0.3:
                return Decision(
                    action=Action.ALL_IN,
                    amount=state.our_stack,
                    display=f"ALL-IN ${state.our_stack:.2f}",
                    explanation=f"All-in with {hand}. Too short to 3-bet/fold — shove and put maximum pressure on.",
                    calculation=None,
                    confidence=0.90
                )
            
            return Decision(
                action=Action.RAISE,
                amount=amount,
                display=f"RAISE TO ${amount:.2f}",
                explanation=f"3-bet with {hand}.{' Squeeze out the caller and take' if state.num_limpers > 0 else ' Take'} control of the pot.",
                calculation=f"{"Squeeze — sized up for the caller" if state.num_limpers > 0 else "Sized up against weaker opponent" if is_fish else "Standard 3-bet"}",
                confidence=0.90
            )
        
        # 3-bet bluff with blockers (from late position only)
        if hand in THREE_BET_BLUFF and state.our_position in [Position.BTN, Position.CO, Position.SB]:
            # Only bluff vs late position opens
            if villain_pos in [Position.CO, Position.HJ]:
                # TIER1-FIX: Don't 3-bet bluff vs fish — they call too much
                if is_fish:
                    return Decision(
                        action=Action.FOLD,
                        amount=None,
                        display="FOLD",
                        explanation=f"Fold {hand}. This player calls too much — don't bluff-raise them.",
                        calculation=None,
                        confidence=0.80
                    )
                amount = calculate_3bet_size(state.facing_bet, we_have_position, is_fish)
                # TIER2-FIX: Squeeze sizing for bluffs too
                if state.num_limpers > 0:
                    amount = round(amount + state.facing_bet * state.num_limpers, 2)
                return Decision(
                    action=Action.RAISE,
                    amount=amount,
                    display=f"RAISE TO ${amount:.2f}",
                    explanation=f"3-bet bluff with {hand}. You block their calling range — great spot to re-raise.",
                    calculation="Light 3-bet — you have good blockers",
                    confidence=0.75
                )
        
        # Call with speculative hands in position
        if hand_strength in [HandStrength.STRONG, HandStrength.PLAYABLE] and we_have_position:
            # JJ, TT can flat
            if hand in ["JJ", "TT"]:
                return Decision(
                    action=Action.CALL,
                    amount=state.facing_bet,
                    display=f"CALL ${state.facing_bet:.2f}",
                    explanation=f"Call with {hand} in position. You'll have a postflop edge.",
                    calculation=None,
                    confidence=0.85
                )
            # Suited connectors, small pairs - need good odds
            if state.facing_bet <= state.bb_size * 3:
                return Decision(
                    action=Action.CALL,
                    amount=state.facing_bet,
                    display=f"CALL ${state.facing_bet:.2f}",
                    explanation=f"Call with {hand}. Good implied odds — if you connect, you'll win a big pot.",
                    calculation=None,
                    confidence=0.75
                )
        
        return Decision(
            action=Action.FOLD,
            amount=None,
            display="FOLD",
            explanation=f"Fold. {hand} can't continue profitably against this raise.",
            calculation=None,
            confidence=0.85
        )
    
    def _bb_defense(
        self, 
        state: GameState, 
        hand: str, 
        hand_strength: HandStrength,
        villain_pos: Position,
        is_fish: bool
    ) -> Decision:
        """BB defense vs open raise."""
        
        # Get 3-bet range for this position
        three_bet_range = BB_DEFENSE_3BET.get(villain_pos, set())
        
        # 3-bet with value hands
        if hand in three_bet_range:
            amount = calculate_3bet_size(state.facing_bet, False, is_fish)  # BB is always OOP
            return Decision(
                action=Action.RAISE,
                amount=amount,
                display=f"RAISE TO ${amount:.2f}",
                explanation=f"3-bet from the big blind with {hand}. Make them pay to continue.",
                calculation=f"{'4×' if is_fish else '3.5×'} their raise = ${amount:.2f}",
                confidence=0.88
            )
        
        # Call with playable hands
        if hand_strength in [HandStrength.PREMIUM, HandStrength.STRONG, HandStrength.PLAYABLE]:
            # Check pot odds
            pot_after_call = state.pot_size + state.facing_bet
            pot_odds = state.facing_bet / (pot_after_call + state.facing_bet)
            
            # Generally call if getting decent odds
            if pot_odds < 0.35:  # Less than 35% of pot to call
                return Decision(
                    action=Action.CALL,
                    amount=state.facing_bet,
                    display=f"CALL ${state.facing_bet:.2f}",
                    explanation=f"Defend your big blind. Call with {hand} and play the flop.",
                    calculation=f"Getting {(1-pot_odds)*100:.0f}% pot odds",
                    confidence=0.80
                )
        
        return Decision(
            action=Action.FOLD,
            amount=None,
            display="FOLD",
            explanation=f"Fold. {hand} isn't worth defending against this sizing.",
            calculation=None,
            confidence=0.85
        )
    
    def _facing_3bet(self, state: GameState, hand: str) -> Decision:
        """Facing a 3-bet after we opened."""
        
        # 4-bet with premium hands
        if hand in FOUR_BET_VALUE:
            amount, is_all_in = calculate_4bet_size(state.facing_bet, state.our_stack)
            
            if is_all_in:
                return Decision(
                    action=Action.ALL_IN,
                    amount=state.our_stack,
                    display=f"ALL-IN ${state.our_stack:.2f}",
                    explanation=f"All-in with {hand}. Too short to 4-bet/fold — get it all in.",
                    calculation="Stack too shallow for standard 4-bet",
                    confidence=0.92
                )
            
            return Decision(
                action=Action.RAISE,
                amount=amount,
                display=f"RAISE TO ${amount:.2f}",
                explanation=f"4-bet with {hand}. Too strong to flat — put them to a decision.",
                calculation=f"2.3× their 3-bet = ${amount:.2f}",
                confidence=0.90
            )
        
        # Call with JJ, TT, AQs if deep enough
        if hand in CALL_FOUR_BET or hand in ["JJ", "TT"]:
            # Need sufficient stack depth
            if state.effective_stack_bb >= 80:
                return Decision(
                    action=Action.CALL,
                    amount=state.facing_bet,
                    display=f"CALL ${state.facing_bet:.2f}",
                    explanation=f"Call the 3-bet with {hand}. Play the flop in position.",
                    calculation=None,
                    confidence=0.80
                )
        
        # Fold everything else (including our 3-bet bluffs)
        return Decision(
            action=Action.FOLD,
            amount=None,
            display="FOLD",
            explanation=f"Fold {hand}. Their 3-bet is too strong — don't chase.",
            calculation=None,
            confidence=0.88
        )
    
    def _facing_4bet(self, state: GameState, hand: str) -> Decision:
        """Facing a 4-bet after we 3-bet."""
        
        # 5-bet all-in with AA, KK
        if hand in ["AA", "KK"]:
            return Decision(
                action=Action.ALL_IN,
                amount=state.our_stack,
                display=f"ALL-IN ${state.our_stack:.2f}",
                explanation=f"Get it all in. {hand} is a monster — this is the spot you wait for.",
                calculation="Best possible spot to go all-in",
                confidence=0.95
            )
        
        # Call with QQ, AKs, AKo if deep
        if hand in ["QQ", "AKs", "AKo"]:
            if state.effective_stack_bb >= 100:
                return Decision(
                    action=Action.CALL,
                    amount=state.facing_bet,
                    display=f"CALL ${state.facing_bet:.2f}",
                    explanation=f"Call the 4-bet with {hand}. You have the hand to see a flop here.",
                    calculation=None,
                    confidence=0.78
                )
            else:
                # Shallow - just go all-in
                return Decision(
                    action=Action.ALL_IN,
                    amount=state.our_stack,
                    display=f"ALL-IN ${state.our_stack:.2f}",
                    explanation=f"All-in with {hand}. You're too strong to fold — go with it.",
                    calculation="Too shallow to flat",
                    confidence=0.82
                )
        
        # JJ, TT - call if very deep only
        if hand in ["JJ", "TT"] and state.effective_stack_bb >= 150:
            return Decision(
                action=Action.CALL,
                amount=state.facing_bet,
                display=f"CALL ${state.facing_bet:.2f}",
                explanation=f"Call with {hand}. Deep stacks give you great implied odds postflop.",
                calculation=None,
                confidence=0.70
            )
        
        # Fold all bluffs and weaker hands
        return Decision(
            action=Action.FOLD,
            amount=None,
            display="FOLD",
            explanation=f"Fold {hand}. A 4-bet means they have it — save your chips.",
            calculation=None,
            confidence=0.90
        )
    
    def _push_fold_decision(self, state: GameState) -> Decision:
        """Short stack push/fold decisions (<20BB)."""
        
        hand = normalize_hand(state.our_hand)
        hand_strength = classify_preflop_hand(hand)
        
        # Push range widens as stack gets shorter
        push_hands = set()
        
        if state.effective_stack_bb < 10:
            # Very short - push wide
            push_hands = PREMIUM_HANDS | STRONG_HANDS | {
                "99", "88", "77", "66", "55",
                "A9s", "A8s", "A7s", "A6s", "A5s", "A4s", "A3s", "A2s",
                "A9o", "ATo", "KQs", "KJs", "KTs", "QJs",
            }
        elif state.effective_stack_bb < 15:
            # Short - push reasonably wide
            push_hands = PREMIUM_HANDS | STRONG_HANDS | {
                "99", "88", "77",
                "ATs", "A9s", "A8s", "A5s", "A4s",
                "KQs", "KJs",
            }
        else:  # 15-20 BB
            # Somewhat short - push tighter
            push_hands = PREMIUM_HANDS | STRONG_HANDS | {
                "99", "ATs", "A5s", "KQs"
            }
        
        if hand in push_hands:
            return Decision(
                action=Action.ALL_IN,
                amount=state.our_stack,
                display=f"ALL-IN ${state.our_stack:.2f}",
                explanation=f"All-in with {hand}. Clear shove at this stack depth.",
                calculation="Short stack mode",
                confidence=0.88
            )
        
        return Decision(
            action=Action.FOLD,
            amount=None,
            display="FOLD",
            explanation=f"Fold. {hand} isn't strong enough to shove — wait for a better spot.",
            calculation=None,
            confidence=0.85
        )
    
    # TIER2-FIX: Short stack preflop (20-50BB)
    def _short_stack_preflop(self, state: GameState) -> Decision:
        """
        Short stack (20-50BB) preflop adjustments per spec 11.
        
        20-30BB: 3-bet ALL-IN or fold (no standard 3-bet), all-in or fold vs 3-bet
        30-50BB: 3-bet/fold > flatting, no flat calling speculative hands
        Open ranges unchanged.
        """
        hand = normalize_hand(state.our_hand)
        hand_strength = classify_preflop_hand(hand)
        is_very_short = state.effective_stack_bb < 30
        is_fish = state.villain_type == VillainType.FISH
        
        # Facing 4-bet: all-in with premiums, fold rest
        if state.action_facing == ActionFacing.FOUR_BET:
            if hand in {"AA", "KK", "QQ", "AKs", "AKo"}:
                return Decision(
                    action=Action.ALL_IN, amount=state.our_stack,
                    display=f"ALL-IN ${state.our_stack:.2f}",
                    explanation=f"All-in with {hand}. You're pot-committed — push now.",
                    calculation=f"{state.effective_stack_bb:.0f}BB - must commit",
                    confidence=0.92)
            return Decision(
                action=Action.FOLD, amount=None, display="FOLD",
                explanation=f"Fold {hand}. Their 4-bet is too strong.",
                calculation=None, confidence=0.90)
        
        # Facing 3-bet: all-in or fold (no calling — SPR too low)
        if state.action_facing == ActionFacing.THREE_BET:
            jam_range = {"AA", "KK", "QQ", "AKs", "AKo"}
            if not is_very_short:
                jam_range |= {"JJ", "TT", "AQs"}
            if hand in jam_range:
                return Decision(
                    action=Action.ALL_IN, amount=state.our_stack,
                    display=f"ALL-IN ${state.our_stack:.2f}",
                    explanation=f"All-in with {hand}. A 3-bet would pot-commit you anyway — shove now.",
                    calculation="Short stack - 3-bet/fold, not flat",
                    confidence=0.88)
            return Decision(
                action=Action.FOLD, amount=None, display="FOLD",
                explanation=f"Fold. Too short-stacked to call a 3-bet with {hand}.",
                calculation=None, confidence=0.88)
        
        # Facing open raise: 3-bet/fold, minimal flatting
        if state.action_facing == ActionFacing.RAISE:
            # Value 3-bet hands → jam at 20-30BB, normal 3-bet at 30-50BB
            if hand in THREE_BET_VALUE:
                if is_very_short:
                    return Decision(
                        action=Action.ALL_IN, amount=state.our_stack,
                        display=f"ALL-IN ${state.our_stack:.2f}",
                        explanation=f"All-in with {hand}. A 3-bet commits you anyway — shove clean.",
                        calculation="Short stack — push is better than a small 3-bet", confidence=0.90)
                we_ip = self._have_position(state.our_position, state.villain_position)
                amount = calculate_3bet_size(state.facing_bet, we_ip, is_fish)
                if amount > state.our_stack * 0.3:
                    return Decision(
                        action=Action.ALL_IN, amount=state.our_stack,
                        display=f"ALL-IN ${state.our_stack:.2f}",
                        explanation=f"All-in with {hand}. Cleaner than a small 3-bet at this depth.",
                        calculation=None, confidence=0.90)
                return Decision(
                    action=Action.RAISE, amount=amount,
                    display=f"RAISE TO ${amount:.2f}",
                    explanation=f"3-bet with {hand}. You have enough chips to put real pressure on.",
                    calculation=None, confidence=0.88)
            
            # JJ/TT can flat at 30-50BB in position only
            if not is_very_short and hand in ["JJ", "TT"]:
                if self._have_position(state.our_position, state.villain_position):
                    return Decision(
                        action=Action.CALL, amount=state.facing_bet,
                        display=f"CALL ${state.facing_bet:.2f}",
                        explanation=f"Call with {hand} in position. Good depth for set-mining.",
                        calculation=None, confidence=0.75)
            
            # Everything else: fold (not enough implied odds)
            return Decision(
                action=Action.FOLD, amount=None, display="FOLD",
                explanation=f"Fold. Not deep enough to call profitably with {hand}.",
                calculation=None, confidence=0.85)
        
        # Open / limp: use standard logic
        if state.action_facing == ActionFacing.NONE:
            return self._open_decision(state, hand)
        if state.action_facing == ActionFacing.LIMP:
            return self._facing_limp(state, hand)
        
        # Fallback to standard
        return self._preflop_decision(state)
    
    # -------------------------------------------------------------------------
    # POST-FLOP DECISIONS
    # -------------------------------------------------------------------------
    
    def _postflop_decision(self, state: GameState) -> Decision:
        """Handle all post-flop decisions."""
        
        # Facing check-raise
        if state.action_facing == ActionFacing.CHECK_RAISE:
            return self._facing_check_raise(state)
        
        # Facing bet/raise
        if state.action_facing == ActionFacing.BET or state.facing_bet > 0:
            return self._facing_bet(state)
        
        # Checked to us
        if state.we_are_aggressor:
            return self._as_aggressor(state)
        else:
            return self._as_defender(state)
    
    def _as_aggressor(self, state: GameState) -> Decision:
        """We were the pre-flop aggressor, it's checked to us."""
        
        # C-bet decision on flop
        if state.street == Street.FLOP:
            return self._cbet_decision(state)
        
        # Turn/river as aggressor
        return self._continue_aggression(state)
    
    def _cbet_decision(self, state: GameState) -> Decision:
        """C-bet decision on the flop."""
        
        hand_strength = state.hand_strength
        board_texture = state.board_texture or BoardTexture.SEMI_WET
        fish = _is_fish(state)  # TIER1-FIX
        
        # Strong hands - always c-bet (size up vs fish)
        if hand_strength in [HandStrength.NUTS, HandStrength.MONSTER, HandStrength.TWO_PAIR, 
                            HandStrength.OVERPAIR, HandStrength.TOP_PAIR_TOP_KICKER]:
            amount, pct = calculate_cbet_size(state.pot_size, board_texture, fish)  # TIER1-FIX: pass fish
            return Decision(
                action=Action.BET,
                amount=amount,
                display=f"BET ${amount:.2f}",
                explanation=f"Bet for value with {_hs(hand_strength)}. They'll call with worse.",
                calculation=None,
                confidence=0.90
            )
        
        # Top pair - usually c-bet (size up vs fish)
        if hand_strength == HandStrength.TOP_PAIR:
            # Reduce frequency on wet boards multiway
            if state.num_players > 2 and board_texture == BoardTexture.WET:
                return Decision(
                    action=Action.CHECK,
                    amount=None,
                    display="CHECK",
                    explanation="Check. Too many opponents on a dangerous board — proceed carefully.",
                    calculation=None,
                    confidence=0.75
                )
            
            amount, pct = calculate_cbet_size(state.pot_size, board_texture, fish)  # TIER1-FIX: pass fish
            return Decision(
                action=Action.BET,
                amount=amount,
                display=f"BET ${amount:.2f}",
                explanation="Bet with top pair. Charge draws and get value from worse hands.",
                calculation=None,
                confidence=0.85
            )
        
        # Draws - semi-bluff on wet boards (standard sizing, no fish adjust on bluffs)
        if hand_strength in [HandStrength.COMBO_DRAW, HandStrength.FLUSH_DRAW, HandStrength.OESD]:
            equity = get_draw_equity(hand_strength, state.street)
            
            # Semi-bluff with good equity
            if equity >= 0.30 or board_texture in [BoardTexture.WET, BoardTexture.SEMI_WET]:
                amount, pct = calculate_cbet_size(state.pot_size, board_texture)
                return Decision(
                    action=Action.BET,
                    amount=amount,
                    display=f"BET ${amount:.2f}",
                    explanation=f"Semi-bluff with {_hs(hand_strength)}. Win the pot now or improve on later streets.",
                    calculation=None,
                    confidence=0.80
                )
        
        # Dry board - can c-bet air sometimes, but NOT vs fish
        # BLUFF SPOT 3: Dry board c-bet with air (auto-bluff, tagged with BluffContext)
        if board_texture == BoardTexture.DRY and hand_strength in [HandStrength.OVERCARDS, HandStrength.AIR]:
            # Only heads-up
            if state.num_players == 2:
                # TIER1-FIX: Don't bluff c-bet vs fish — they call too much
                if fish:
                    return Decision(
                        action=Action.CHECK,
                        amount=None,
                        display="CHECK",
                        explanation="Check. This player calls too much to bluff — wait for a real hand.",
                        calculation=None,
                        confidence=0.80
                    )
                amount, pct = calculate_cbet_size(state.pot_size, board_texture)
                break_even_pct = round(amount / (state.pot_size + amount), 2)
                estimated_fold_pct = 0.55
                ev_of_bet = round(
                    (estimated_fold_pct * state.pot_size) - ((1 - estimated_fold_pct) * amount), 2
                )
                bluff_ctx = BluffContext(
                    spot_type='dry_board_cbet',
                    delivery='auto',
                    recommended_action='BET',
                    bet_amount=amount,
                    pot_size=state.pot_size,
                    ev_of_bet=ev_of_bet,
                    ev_of_check=0.0,
                    break_even_pct=break_even_pct,
                    estimated_fold_pct=estimated_fold_pct,
                    explanation_bet=(
                        f"Dry board, you raised pre. "
                        f"${amount:.0f} to win ${state.pot_size:.0f} — "
                        f"only needs to work {break_even_pct*100:.0f}% of the time."
                    ),
                    explanation_check="",
                )
                return Decision(
                    action=Action.BET,
                    amount=amount,
                    display=f"BET ${amount:.2f}",
                    explanation=bluff_ctx.explanation_bet,
                    calculation=f"${amount:.0f} to win ${state.pot_size:.0f}",
                    confidence=0.70,
                    bluff_context=bluff_ctx,
                )
        
        # Default - check
        return Decision(
            action=Action.CHECK,
            amount=None,
            display="CHECK",
            explanation=f"Check with {_hs(hand_strength)}. Re-evaluate on the next street.",
            calculation=None,
            confidence=0.80
        )
    
    def _continue_aggression(self, state: GameState) -> Decision:
        """Continue betting on turn/river after c-betting."""
        
        hand_strength = state.hand_strength
        fish = _is_fish(state)  # TIER1-FIX
        
        # Value hands - keep betting (size up vs fish)
        if hand_strength in [HandStrength.NUTS, HandStrength.MONSTER, HandStrength.TWO_PAIR,
                            HandStrength.OVERPAIR, HandStrength.TOP_PAIR_TOP_KICKER]:
            amount, pct = calculate_value_bet_size(state.pot_size, state.street, hand_strength, fish)  # TIER1-FIX: pass fish
            return Decision(
                action=Action.BET,
                amount=amount,
                display=f"BET ${amount:.2f}",
                explanation=f"Keep betting. You still have {_hs(hand_strength)} — stay aggressive.",
                calculation=None,
                confidence=0.88
            )
        
        # Top pair on turn - bet for protection/value (size up vs fish)
        if hand_strength == HandStrength.TOP_PAIR and state.street == Street.TURN:
            amount, pct = calculate_value_bet_size(state.pot_size, state.street, hand_strength, fish)  # TIER1-FIX: pass fish
            return Decision(
                action=Action.BET,
                amount=amount,
                display=f"BET ${amount:.2f}",
                explanation="Bet with top pair. Keep charging draws and extracting value.",
                calculation=None,
                confidence=0.80
            )
        
        # River with top pair — TIER1-FIX: thin value bet vs fish, check vs reg
        if hand_strength == HandStrength.TOP_PAIR and state.street == Street.RIVER:
            if fish:
                amount, pct = calculate_value_bet_size(state.pot_size, state.street, hand_strength, True)
                return Decision(
                    action=Action.BET,
                    amount=amount,
                    display=f"BET ${amount:.2f}",
                    explanation="Bet for thin value. This player pays off with worse — exploit that.",
                    calculation=None,
                    confidence=0.72
                )
            return Decision(
                action=Action.CHECK,
                amount=None,
                display="CHECK",
                explanation="Check. Top pair is likely best — control the pot and get to showdown.",
                calculation=None,
                confidence=0.75
            )
        
        # Draws - continue semi-bluffing on turn (but NOT vs fish)
        if hand_strength in [HandStrength.COMBO_DRAW, HandStrength.FLUSH_DRAW, HandStrength.OESD]:
            if state.street == Street.TURN:
                equity = get_draw_equity(hand_strength, state.street)
                if equity >= 0.15:
                    # TIER1-FIX: Don't semi-bluff turn vs fish — they don't fold
                    if fish:
                        return Decision(
                            action=Action.CHECK,
                            amount=None,
                            display="CHECK",
                            explanation=f"Check. This player won't fold — save your bluffs for better opponents.",
                            calculation=None,
                            confidence=0.75
                        )
                    amount = round(state.pot_size * 0.50, 2)
                    return Decision(
                        action=Action.BET,
                        amount=amount,
                        display=f"BET ${amount:.2f}",
                        explanation=f"Semi-bluff with {_hs(hand_strength)}. Win it now or hit on the river.",
                        calculation=f"Medium bet — standard sizing",
                        confidence=0.75
                    )
        
        # BLUFF SPOT 1: Missed draw on river — BLUFF CHOICE SPOT
        if hand_strength == HandStrength.AIR and state.street == Street.RIVER:
            fish = _is_fish(state)
            
            # Only offer bluff if: heads-up, we were aggressor, villain isn't fish
            if state.num_players == 2 and state.we_are_aggressor and not fish:
                bet_amount = round(state.pot_size * 0.66, 2)
                break_even_pct = round(bet_amount / (state.pot_size + bet_amount), 2)
                estimated_fold_pct = 0.50  # Population average for river folds vs triple barrel
                ev_of_bet = round(
                    (estimated_fold_pct * state.pot_size) - ((1 - estimated_fold_pct) * bet_amount), 2
                )
                
                bluff_ctx = BluffContext(
                    spot_type='river_barrel',
                    delivery='choice',
                    recommended_action='BET',
                    bet_amount=bet_amount,
                    pot_size=state.pot_size,
                    ev_of_bet=ev_of_bet,
                    ev_of_check=0.0,
                    break_even_pct=break_even_pct,
                    estimated_fold_pct=estimated_fold_pct,
                    explanation_bet=(
                        f"You bet flop and turn — one more bet tells a believable story. "
                        f"${bet_amount:.0f} to win ${state.pot_size:.0f}, "
                        f"works about 5 out of 10 times."
                    ),
                    explanation_check="Give up. Checking wins $0 but risks nothing.",
                )
                
                # Primary recommendation: BET
                bet_decision = Decision(
                    action=Action.BET,
                    amount=bet_amount,
                    display=f"BET ${bet_amount:.2f}",
                    explanation=bluff_ctx.explanation_bet,
                    calculation=f"${bet_amount:.0f} to win ${state.pot_size:.0f} — needs {break_even_pct*100:.0f}%",
                    confidence=0.65,
                    bluff_context=bluff_ctx,
                )
                
                # Alternative: CHECK
                check_decision = Decision(
                    action=Action.CHECK,
                    amount=None,
                    display="CHECK",
                    explanation=bluff_ctx.explanation_check,
                    calculation="Checking wins $0",
                    confidence=0.65,
                    bluff_context=bluff_ctx,
                )
                
                bet_decision.alternative = check_decision
                return bet_decision
            
            # Fish or multiway — no bluff
            return Decision(
                action=Action.CHECK,
                amount=None,
                display="CHECK",
                explanation="Check. This player calls too much — save your bluffs." if _is_fish(state)
                    else "Your draw missed. Give up — chasing would be throwing money away.",
                calculation=None,
                confidence=0.85
            )
        
        # Default check
        return Decision(
            action=Action.CHECK,
            amount=None,
            display="CHECK",
            explanation=f"Check. Nothing worth betting with {_hs(hand_strength)}.",
            calculation=None,
            confidence=0.80
        )
    
    def _as_defender(self, state: GameState) -> Decision:
        """We were not the aggressor, it's checked to us."""
        
        hand_strength = state.hand_strength
        fish = _is_fish(state)  # TIER1-FIX
        
        # Can check-raise with monsters (size up vs fish)
        if hand_strength in [HandStrength.NUTS, HandStrength.MONSTER]:
            # But usually just bet for value
            amount, pct = calculate_value_bet_size(state.pot_size, state.street, hand_strength, fish)  # TIER1-FIX: pass fish
            return Decision(
                action=Action.BET,
                amount=amount,
                display=f"BET ${amount:.2f}",
                explanation=f"Value bet with {_hs(hand_strength)}. You're ahead — get paid.",
                calculation=None,
                confidence=0.88
            )
        
        # BLUFF SPOT 2: River probe bluff — villain showed weakness by checking twice
        if state.street == Street.RIVER and state.num_players == 2:
            if not fish and hand_strength in [HandStrength.AIR, HandStrength.OVERCARDS]:
                bet_amount = round(state.pot_size * 0.50, 2)
                break_even_pct = round(bet_amount / (state.pot_size + bet_amount), 2)
                estimated_fold_pct = 0.60
                ev_of_bet = round(
                    (estimated_fold_pct * state.pot_size) - ((1 - estimated_fold_pct) * bet_amount), 2
                )
                
                bluff_ctx = BluffContext(
                    spot_type='river_probe',
                    delivery='choice',
                    recommended_action='BET',
                    bet_amount=bet_amount,
                    pot_size=state.pot_size,
                    ev_of_bet=ev_of_bet,
                    ev_of_check=0.0,
                    break_even_pct=break_even_pct,
                    estimated_fold_pct=estimated_fold_pct,
                    explanation_bet=(
                        f"They checked twice — they don't trust their hand. "
                        f"${bet_amount:.0f} to win ${state.pot_size:.0f}, "
                        f"works about 6 out of 10 times."
                    ),
                    explanation_check="Give up. They showed weakness but betting risks chips.",
                )
                
                bet_decision = Decision(
                    action=Action.BET,
                    amount=bet_amount,
                    display=f"BET ${bet_amount:.2f}",
                    explanation=bluff_ctx.explanation_bet,
                    calculation=f"${bet_amount:.0f} to win ${state.pot_size:.0f}",
                    confidence=0.72,
                    bluff_context=bluff_ctx,
                )
                check_decision = Decision(
                    action=Action.CHECK,
                    amount=None,
                    display="CHECK",
                    explanation=bluff_ctx.explanation_check,
                    calculation="Checking wins $0",
                    confidence=0.72,
                    bluff_context=bluff_ctx,
                )
                bet_decision.alternative = check_decision
                return bet_decision
        
        # Check medium strength hands to pot control
        if hand_strength in [HandStrength.TOP_PAIR, HandStrength.MIDDLE_PAIR, HandStrength.OVERPAIR]:
            return Decision(
                action=Action.CHECK,
                amount=None,
                display="CHECK",
                explanation="Check. Your hand is good but vulnerable — control the pot size.",
                calculation=None,
                confidence=0.80
            )
        
        # Check draws (unless good semi-bluff spot)
        if hand_strength in [HandStrength.FLUSH_DRAW, HandStrength.OESD, HandStrength.COMBO_DRAW]:
            return Decision(
                action=Action.CHECK,
                amount=None,
                display="CHECK",
                explanation=f"Check. Take a free card with {_hs(hand_strength)}.",
                calculation=None,
                confidence=0.75
            )
        
        # Check everything else
        return Decision(
            action=Action.CHECK,
            amount=None,
            display="CHECK",
            explanation="Check. Nothing to gain by betting here.",
            calculation=None,
            confidence=0.85
        )
    
    def _facing_bet(self, state: GameState) -> Decision:
        """Facing a bet or raise post-flop."""
        
        hand_strength = state.hand_strength
        pot_odds = calculate_pot_odds(state.pot_size, state.facing_bet)
        street = state.street
        
        # Calculate bet size relative to pot
        bet_ratio = state.facing_bet / state.pot_size if state.pot_size > 0 else 1.0
        
        # TIER1-FIX: SPR commitment — in low SPR pots, commit with top pair+
        if state.spr is not None and state.spr < 4:
            if hand_strength in [HandStrength.NUTS, HandStrength.MONSTER, HandStrength.TWO_PAIR,
                                HandStrength.OVERPAIR, HandStrength.TOP_PAIR_TOP_KICKER, HandStrength.TOP_PAIR]:
                fish = _is_fish(state)
                if state.facing_bet >= state.our_stack * 0.5:
                    return Decision(
                        action=Action.ALL_IN,
                        amount=state.our_stack,
                        display=f"ALL-IN ${state.our_stack:.2f}",
                        explanation=f"All-in. You're pot-committed with {_hs(hand_strength)} — go with it.",
                        calculation="Pot-committed",
                        confidence=0.90
                    )
                amt = calculate_check_raise_size(state.facing_bet, fish)
                if amt >= state.our_stack * 0.5:
                    return Decision(
                        action=Action.ALL_IN,
                        amount=state.our_stack,
                        display=f"ALL-IN ${state.our_stack:.2f}",
                        explanation=f"All-in. Pot is too big to fold {_hs(hand_strength)} — you're committed.",
                        calculation=f"Pot-committed — too much invested to fold",
                        confidence=0.88
                    )
                return Decision(
                    action=Action.RAISE,
                    amount=amt,
                    display=f"RAISE TO ${amt:.2f}",
                    explanation=f"Call. You're committed with {_hs(hand_strength)} at this pot size.",
                    calculation=f"SPR {state.spr:.1f} < 4, committed",
                    confidence=0.88
                )
        
        # TIER1-FIX: Multiway tightening — tighter ranges when facing bets multiway
        if state.num_players > 2:
            return self._facing_bet_multiway(state, hand_strength, pot_odds, bet_ratio)
        
        # RIVER RAISES ARE 85-95% VALUE - KEY INSIGHT FROM SPEC 10
        if street == Street.RIVER and state.action_facing == ActionFacing.BET and bet_ratio > 0.5:
            return self._facing_river_bet(state, hand_strength, pot_odds, bet_ratio)
        
        # TURN RAISES ARE 75-85% VALUE
        if street == Street.TURN and bet_ratio > 0.5:
            return self._facing_turn_bet(state, hand_strength, pot_odds, bet_ratio)
        
        # Flop/small bets - more standard
        return self._facing_standard_bet(state, hand_strength, pot_odds, bet_ratio)
    
    # TIER1-FIX: NEW METHOD — Multiway pot facing bet adjustments
    def _facing_bet_multiway(
        self,
        state: GameState,
        hand_strength: HandStrength,
        pot_odds: float,
        bet_ratio: float
    ) -> Decision:
        """Tighter ranges when facing bets in multiway pots (3+ players)."""
        
        fish = _is_fish(state)
        
        # Nuts/monster: always raise for value
        if hand_strength in [HandStrength.NUTS, HandStrength.MONSTER]:
            amt = calculate_check_raise_size(state.facing_bet, fish)
            return Decision(
                action=Action.RAISE,
                amount=amt,
                display=f"RAISE TO ${amt:.2f}",
                explanation=f"Raise for value with {_hs(hand_strength)}. You're ahead of everyone — build the pot.",
                calculation="Sized up against weaker opponent" if fish else "Standard raise sizing",
                confidence=0.92
            )
        
        # Two pair: call (don't raise into multiple opponents without nuts)
        if hand_strength == HandStrength.TWO_PAIR:
            return Decision(
                action=Action.CALL,
                amount=state.facing_bet,
                display=f"CALL ${state.facing_bet:.2f}",
                explanation="Call with two pair. Strong but not invincible multiway — proceed carefully.",
                calculation=None,
                confidence=0.85
            )
        
        # Overpair/TPTK: call, but fold to large bets on river
        if hand_strength in [HandStrength.OVERPAIR, HandStrength.TOP_PAIR_TOP_KICKER]:
            if state.street == Street.RIVER and bet_ratio >= 0.66:
                return Decision(
                    action=Action.FOLD,
                    amount=None,
                    display="FOLD",
                    explanation=f"Fold. Big river bet multiway — someone has you beat.",
                    calculation=None,
                    confidence=0.85
                )
            return Decision(
                action=Action.CALL,
                amount=state.facing_bet,
                display=f"CALL ${state.facing_bet:.2f}",
                explanation=f"Call with {_hs(hand_strength)}. Probably ahead, but stay cautious.",
                calculation=None,
                confidence=0.80
            )
        
        # Top pair: only call small bets on flop, fold turn/river
        if hand_strength == HandStrength.TOP_PAIR:
            if state.street == Street.FLOP and bet_ratio <= 0.50:
                return Decision(
                    action=Action.CALL,
                    amount=state.facing_bet,
                    display=f"CALL ${state.facing_bet:.2f}",
                    explanation="Call. Top pair is good on the flop — see what the turn brings.",
                    calculation=None,
                    confidence=0.70
                )
            return Decision(
                action=Action.FOLD,
                amount=None,
                display="FOLD",
                explanation=f"Fold. Top pair isn't enough on the {state.street.value} against this many opponents.",
                calculation=None,
                confidence=0.80
            )
        
        # Middle/bottom pair: always fold multiway
        if hand_strength in [HandStrength.MIDDLE_PAIR, HandStrength.BOTTOM_PAIR]:
            return Decision(
                action=Action.FOLD,
                amount=None,
                display="FOLD",
                explanation=f"Fold. Too many opponents for {_hs(hand_strength)} — you're likely behind.",
                calculation=None,
                confidence=0.85
            )
        
        # Draws: call if odds are there, never raise multiway (no fold equity)
        if hand_strength in [HandStrength.COMBO_DRAW, HandStrength.FLUSH_DRAW, HandStrength.OESD]:
            equity = get_draw_equity(hand_strength, state.street)
            # Multiway gives better implied odds, use 0.85x needed equity
            if equity >= pot_odds * 0.85:
                return Decision(
                    action=Action.CALL,
                    amount=state.facing_bet,
                    display=f"CALL ${state.facing_bet:.2f}",
                    explanation=f"Call. Good pot odds to chase {_hs(hand_strength)} multiway.",
                    calculation=f"Equity {equity*100:.0f}% vs {pot_odds*100:.0f}% needed (multiway implied odds)",
                    confidence=0.78
                )
            return Decision(
                action=Action.FOLD,
                amount=None,
                display="FOLD",
                explanation=f"Fold. Not enough equity to chase {_hs(hand_strength)} here.",
                calculation=None,
                confidence=0.80
            )
        
        # Everything else: fold
        return Decision(
            action=Action.FOLD,
            amount=None,
            display="FOLD",
            explanation=f"Fold. {_hs(hand_strength).capitalize()} can't handle the pressure multiway.",
            calculation=None,
            confidence=0.85
        )
    
    def _facing_river_bet(
        self, 
        state: GameState, 
        hand_strength: HandStrength, 
        pot_odds: float,
        bet_ratio: float
    ) -> Decision:
        """
        Facing river bet - CRITICAL: River raises are 85-95% value.
        DO NOT hero call with one pair.
        """
        
        fish = _is_fish(state)  # TIER1-FIX
        
        # Nuts/near-nuts - raise for value (bigger vs fish)
        if hand_strength == HandStrength.NUTS:
            amount = calculate_check_raise_size(state.facing_bet, fish)  # TIER1-FIX: pass fish
            return Decision(
                action=Action.RAISE,
                amount=amount,
                display=f"RAISE TO ${amount:.2f}",
                explanation="Raise. You have the nuts — extract maximum value.",
                calculation="Sized up against weaker opponent" if fish else "Standard raise sizing",
                confidence=0.95
            )
        
        # Monsters - call
        if hand_strength in [HandStrength.MONSTER, HandStrength.TWO_PAIR]:
            return Decision(
                action=Action.CALL,
                amount=state.facing_bet,
                display=f"CALL ${state.facing_bet:.2f}",
                explanation=f"Call with {_hs(hand_strength)}. You're in good shape.",
                calculation=None,
                confidence=0.85
            )
        
        # Overpair and top pair - FOLD to big bets (but CALL vs fish)
        if hand_strength in [HandStrength.OVERPAIR, HandStrength.TOP_PAIR_TOP_KICKER, HandStrength.TOP_PAIR]:
            if bet_ratio >= 0.66:
                # TIER1-FIX: vs fish, river bets are LESS reliable as value — fish overvalue weaker hands
                if fish and hand_strength in [HandStrength.OVERPAIR, HandStrength.TOP_PAIR_TOP_KICKER]:
                    return Decision(
                        action=Action.CALL,
                        amount=state.facing_bet,
                        display=f"CALL ${state.facing_bet:.2f}",
                        explanation=f"Call. This player overvalues their hand — {_hs(hand_strength)} is ahead.",
                        calculation=None,
                        confidence=0.72
                    )
                return Decision(
                    action=Action.FOLD,
                    amount=None,
                    display="FOLD",
                    explanation=f"Fold. Big river bets mean business — don't be a hero with {_hs(hand_strength)}.",
                    calculation=None,
                    confidence=0.88
                )
            else:
                # Small bet - can call
                return Decision(
                    action=Action.CALL,
                    amount=state.facing_bet,
                    display=f"CALL ${state.facing_bet:.2f}",
                    explanation=f"Call. Small bet gives you the right price with {_hs(hand_strength)}.",
                    calculation=None,
                    confidence=0.70
                )
        
        # Everything else - fold
        return Decision(
            action=Action.FOLD,
            amount=None,
            display="FOLD",
            explanation=f"Fold. You're not beating their betting range with {_hs(hand_strength)}.",
            calculation=None,
            confidence=0.90
        )
    
    def _facing_turn_bet(
        self,
        state: GameState,
        hand_strength: HandStrength,
        pot_odds: float,
        bet_ratio: float
    ) -> Decision:
        """Facing turn bet - raises are 75-85% value."""
        
        fish = _is_fish(state)  # TIER1-FIX
        
        # Strong hands - raise (bigger vs fish)
        if hand_strength in [HandStrength.NUTS, HandStrength.MONSTER]:
            amount = calculate_check_raise_size(state.facing_bet, fish)  # TIER1-FIX: pass fish
            return Decision(
                action=Action.RAISE,
                amount=amount,
                display=f"RAISE TO ${amount:.2f}",
                explanation=f"Raise with {_hs(hand_strength)}. Make them pay to see more cards.",
                calculation="Sized up against weaker opponent" if fish else "Standard raise sizing",
                confidence=0.90
            )
        
        # Two pair, overpair, TPTK - call
        if hand_strength in [HandStrength.TWO_PAIR, HandStrength.OVERPAIR, HandStrength.TOP_PAIR_TOP_KICKER]:
            return Decision(
                action=Action.CALL,
                amount=state.facing_bet,
                display=f"CALL ${state.facing_bet:.2f}",
                explanation=f"Call. {_hs(hand_strength).capitalize()} is ahead of most of their range.",
                calculation=None,
                confidence=0.85
            )
        
        # Top pair - call smaller bets, fold to big
        if hand_strength == HandStrength.TOP_PAIR:
            if bet_ratio <= 0.66:
                return Decision(
                    action=Action.CALL,
                    amount=state.facing_bet,
                    display=f"CALL ${state.facing_bet:.2f}",
                    explanation="Call. Top pair beats most of their betting range.",
                    calculation=None,
                    confidence=0.75
                )
            else:
                return Decision(
                    action=Action.FOLD,
                    amount=None,
                    display="FOLD",
                    explanation="Fold. An overbet this size means they have it. One pair isn't enough.",
                    calculation=None,
                    confidence=0.75
                )
        
        # Draws - check equity vs pot odds
        if hand_strength in [HandStrength.COMBO_DRAW, HandStrength.FLUSH_DRAW, HandStrength.OESD]:
            equity = get_draw_equity(hand_strength, state.street)
            if equity >= pot_odds:
                return Decision(
                    action=Action.CALL,
                    amount=state.facing_bet,
                    display=f"CALL ${state.facing_bet:.2f}",
                    explanation=f"Call. The pot odds justify continuing with {_hs(hand_strength)}.",
                    calculation=f"Equity {equity*100:.0f}% >= {pot_odds*100:.0f}% pot odds",
                    confidence=0.80
                )
            else:
                return Decision(
                    action=Action.FOLD,
                    amount=None,
                    display="FOLD",
                    explanation=f"Fold. The price isn't right to chase {_hs(hand_strength)}.",
                    calculation=f"Equity {equity*100:.0f}% < {pot_odds*100:.0f}% needed",
                    confidence=0.80
                )
        
        # Gutshot - usually fold
        if hand_strength == HandStrength.GUTSHOT:
            equity = get_draw_equity(hand_strength, state.street)
            if equity >= pot_odds and bet_ratio <= 0.33:
                return Decision(
                    action=Action.CALL,
                    amount=state.facing_bet,
                    display=f"CALL ${state.facing_bet:.2f}",
                    explanation="Call. Small bet gives you the odds to draw.",
                    calculation=None,
                    confidence=0.65
                )
        
        # Fold weak hands
        return Decision(
            action=Action.FOLD,
            amount=None,
            display="FOLD",
            explanation=f"Fold. Not the right spot to continue with {_hs(hand_strength)}.",
            calculation=None,
            confidence=0.85
        )
    
    def _facing_standard_bet(
        self,
        state: GameState,
        hand_strength: HandStrength,
        pot_odds: float,
        bet_ratio: float
    ) -> Decision:
        """Facing standard bet (flop or small sizing)."""
        
        fish = _is_fish(state)  # TIER1-FIX
        
        # Monsters - raise (bigger vs fish)
        if hand_strength in [HandStrength.NUTS, HandStrength.MONSTER, HandStrength.TWO_PAIR]:
            amount = calculate_check_raise_size(state.facing_bet, fish)  # TIER1-FIX: pass fish
            return Decision(
                action=Action.RAISE,
                amount=amount,
                display=f"RAISE TO ${amount:.2f}",
                explanation=f"Raise with {_hs(hand_strength)}. Make them pay for continuing.",
                calculation="Sized up against weaker opponent" if fish else "Standard raise sizing",
                confidence=0.90
            )
        
        # Top pair and better - call
        if hand_strength in [HandStrength.OVERPAIR, HandStrength.TOP_PAIR_TOP_KICKER, HandStrength.TOP_PAIR]:
            return Decision(
                action=Action.CALL,
                amount=state.facing_bet,
                display=f"CALL ${state.facing_bet:.2f}",
                explanation=f"Call. You're ahead with {_hs(hand_strength)} — keep going.",
                calculation=None,
                confidence=0.85
            )
        
        # Middle pair - call small bets, fold to big
        if hand_strength == HandStrength.MIDDLE_PAIR:
            if bet_ratio <= 0.50:
                return Decision(
                    action=Action.CALL,
                    amount=state.facing_bet,
                    display=f"CALL ${state.facing_bet:.2f}",
                    explanation="Call. Middle pair can peel one more card here.",
                    calculation=None,
                    confidence=0.70
                )
            else:
                return Decision(
                    action=Action.FOLD,
                    amount=None,
                    display="FOLD",
                    explanation="Fold. The bet is too large for middle pair — you're probably behind.",
                    calculation=None,
                    confidence=0.75
                )
        
        # Draws - call if odds are there
        if hand_strength in [HandStrength.COMBO_DRAW, HandStrength.FLUSH_DRAW, HandStrength.OESD]:
            equity = get_draw_equity(hand_strength, state.street)
            # Can also raise as semi-bluff (but NOT vs fish)
            if equity >= 0.30:
                # TIER1-FIX: Don't semi-bluff raise vs fish — they don't fold
                if fish:
                    return Decision(
                        action=Action.CALL,
                        amount=state.facing_bet,
                        display=f"CALL ${state.facing_bet:.2f}",
                        explanation=f"Call with {_hs(hand_strength)}. This player won't fold to a raise — just draw.",
                        calculation=f"Equity {equity*100:.0f}%",
                        confidence=0.80
                    )
                amount = calculate_check_raise_size(state.facing_bet)
                return Decision(
                    action=Action.RAISE,
                    amount=amount,
                    display=f"RAISE TO ${amount:.2f}",
                    explanation=f"Raise as a semi-bluff with {_hs(hand_strength)}. Win now or improve.",
                    calculation=f"{equity*100:.0f}% equity - fold equity + value",
                    confidence=0.80
                )
            elif equity >= pot_odds:
                return Decision(
                    action=Action.CALL,
                    amount=state.facing_bet,
                    display=f"CALL ${state.facing_bet:.2f}",
                    explanation=f"Call. Good equity with {_hs(hand_strength)} — see the next card.",
                    calculation=f"Equity {equity*100:.0f}% >= {pot_odds*100:.0f}% pot odds",
                    confidence=0.80
                )
        
        # Fold air and weak hands
        return Decision(
            action=Action.FOLD,
            amount=None,
            display="FOLD",
            explanation=f"Fold. {_hs(hand_strength).capitalize()} can't continue here.",
            calculation=None,
            confidence=0.85
        )
    
    def _facing_check_raise(self, state: GameState) -> Decision:
        """
        Facing a check-raise.
        
        From spec: Check-raises are polarized (60% monsters, 30% draws, 10% bluffs)
        """
        
        hand_strength = state.hand_strength
        fish = _is_fish(state)  # TIER1-FIX
        
        # TIER1-FIX: SPR commitment for check-raises too
        if state.spr is not None and state.spr < 4:
            if hand_strength in [HandStrength.NUTS, HandStrength.MONSTER, HandStrength.TWO_PAIR,
                                HandStrength.OVERPAIR, HandStrength.TOP_PAIR_TOP_KICKER, HandStrength.TOP_PAIR]:
                return Decision(
                    action=Action.ALL_IN,
                    amount=state.our_stack,
                    display=f"ALL-IN ${state.our_stack:.2f}",
                    explanation=f"All-in. Pot-committed with {_hs(hand_strength)} — go with it.",
                    calculation=f"SPR < 4, committed",
                    confidence=0.88
                )
        
        # Monsters - re-raise (bigger vs fish)
        if hand_strength in [HandStrength.NUTS, HandStrength.MONSTER]:
            amount = round(state.facing_bet * (3.0 if fish else 2.5), 2)  # TIER1-FIX: bigger re-raise vs fish
            return Decision(
                action=Action.RAISE,
                amount=amount,
                display=f"RAISE TO ${amount:.2f}",
                explanation=f"Re-raise. They walked into your {_hs(hand_strength)} — punish them.",
                calculation=f"{'3×' if fish else '2.5×'} their raise = ${amount:.2f}",
                confidence=0.90
            )
        
        # Overpair/TPTK - call but proceed with caution
        if hand_strength in [HandStrength.OVERPAIR, HandStrength.TOP_PAIR_TOP_KICKER]:
            return Decision(
                action=Action.CALL,
                amount=state.facing_bet,
                display=f"CALL ${state.facing_bet:.2f}",
                explanation=f"Call. Respect the check-raise — proceed carefully with {_hs(hand_strength)}.",
                calculation=None,
                confidence=0.75
            )
        
        # Top pair (not top kicker) — TIER1-FIX: call vs fish, fold vs reg
        if hand_strength == HandStrength.TOP_PAIR:
            if fish:
                return Decision(
                    action=Action.CALL,
                    amount=state.facing_bet,
                    display=f"CALL ${state.facing_bet:.2f}",
                    explanation="Call. This player overplays their hands — your top pair is likely good.",
                    calculation=None,
                    confidence=0.68
                )
            return Decision(
                action=Action.FOLD,
                amount=None,
                display="FOLD",
                explanation="Fold. Check-raises mean real strength — top pair isn't enough.",
                calculation=None,
                confidence=0.80
            )
        
        # Strong draws - call if odds
        if hand_strength in [HandStrength.COMBO_DRAW, HandStrength.FLUSH_DRAW]:
            equity = get_draw_equity(hand_strength, state.street)
            pot_odds = calculate_pot_odds(state.pot_size, state.facing_bet)
            if equity >= pot_odds:
                return Decision(
                    action=Action.CALL,
                    amount=state.facing_bet,
                    display=f"CALL ${state.facing_bet:.2f}",
                    explanation=f"Call. You have the odds to continue with {_hs(hand_strength)}.",
                    calculation=f"Equity {equity*100:.0f}% >= {pot_odds*100:.0f}% pot odds",
                    confidence=0.75
                )
        
        # Fold everything else
        return Decision(
            action=Action.FOLD,
            amount=None,
            display="FOLD",
            explanation="Fold. The check-raise shows real strength — let this one go.",
            calculation=None,
            confidence=0.85
        )
    
    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------
    
    def _have_position(self, our_pos: Position, villain_pos: Optional[Position]) -> bool:
        """Check if we have position on villain."""
        if villain_pos is None:
            return True
        
        position_order = [Position.SB, Position.BB, Position.UTG, Position.HJ, Position.CO, Position.BTN]
        our_idx = position_order.index(our_pos)
        villain_idx = position_order.index(villain_pos)
        
        return our_idx > villain_idx


# =============================================================================
# HELPER FUNCTIONS FOR GAME STATE CREATION
# =============================================================================

def create_game_state(
    stakes: str,
    our_stack: float,
    villain_stack: float,
    pot_size: float,
    facing_bet: float,
    our_position: str,
    villain_position: Optional[str],
    street: str,
    our_hand: str,
    hand_strength: str,
    board: Optional[str] = None,
    board_texture: Optional[str] = None,
    num_players: int = 2,
    num_limpers: int = 0,
    we_are_aggressor: bool = False,
    action_facing: str = "none",
    villain_type: str = "unknown",
) -> GameState:
    """
    Helper to create GameState from simple inputs.
    
    This is the main interface for the UI to create game states.
    """
    
    stakes_info = STAKES_CONFIG.get(stakes, {"sb": 1.0, "bb": 2.0})
    bb_size = stakes_info["bb"]
    sb_size = stakes_info["sb"]
    
    effective_stack = min(our_stack, villain_stack)
    
    # Parse enums
    pos = Position[our_position.upper()]
    villain_pos = Position[villain_position.upper()] if villain_position else None
    st = Street[street.upper()]
    hs_key = hand_strength.upper().replace(" ", "_")
    hs_key = {"TPTK": "TOP_PAIR_TOP_KICKER"}.get(hs_key, hs_key)
    hs = HandStrength[hs_key]
    bt = BoardTexture[board_texture.upper()] if board_texture else None
    af = ActionFacing[action_facing.upper().replace("-", "_").replace("3", "THREE_").replace("4", "FOUR_")]
    vt = VillainType[villain_type.upper()]
    
    # Calculate SPR
    spr = None
    if pot_size > 0 and st != Street.PREFLOP:
        spr = effective_stack / pot_size
    
    return GameState(
        stakes=stakes,
        bb_size=bb_size,
        sb_size=sb_size,
        our_stack=our_stack,
        villain_stack=villain_stack,
        effective_stack=effective_stack,
        effective_stack_bb=effective_stack / bb_size,
        pot_size=pot_size,
        facing_bet=facing_bet,
        our_position=pos,
        villain_position=villain_pos,
        street=st,
        our_hand=our_hand,
        hand_strength=hs,
        board=board,
        board_texture=bt,
        num_players=num_players,
        num_limpers=num_limpers,
        we_are_aggressor=we_are_aggressor,
        action_facing=af,
        villain_type=vt,
        spr=spr,
    )


# =============================================================================
# MAIN ENGINE INSTANCE
# =============================================================================

# Singleton engine instance
_engine: Optional[PokerDecisionEngine] = None


def get_engine() -> PokerDecisionEngine:
    """Get the poker decision engine instance."""
    global _engine
    if _engine is None:
        _engine = PokerDecisionEngine()
    return _engine


def get_decision(
    stakes: str,
    our_stack: float,
    villain_stack: float,
    pot_size: float,
    facing_bet: float,
    our_position: str,
    villain_position: Optional[str],
    street: str,
    our_hand: str,
    hand_strength: str,
    board: Optional[str] = None,
    board_texture: Optional[str] = None,
    num_players: int = 2,
    num_limpers: int = 0,
    we_are_aggressor: bool = False,
    action_facing: str = "none",
    villain_type: str = "unknown",
) -> Decision:
    """
    Main entry point - get a decision from the engine.
    
    This is the primary function the UI should call.
    """
    state = create_game_state(
        stakes=stakes,
        our_stack=our_stack,
        villain_stack=villain_stack,
        pot_size=pot_size,
        facing_bet=facing_bet,
        our_position=our_position,
        villain_position=villain_position,
        street=street,
        our_hand=our_hand,
        hand_strength=hand_strength,
        board=board,
        board_texture=board_texture,
        num_players=num_players,
        num_limpers=num_limpers,
        we_are_aggressor=we_are_aggressor,
        action_facing=action_facing,
        villain_type=villain_type,
    )
    
    engine = get_engine()
    decision = engine.get_decision(state)
    
    # ── Cap bet/raise amounts to remaining stack ──
    # If the recommended bet is ≥90% of stack, convert to ALL-IN
    # (a weird-sized bet near stack size is worse than a clean shove)
    if decision.amount is not None and decision.amount > 0 and state.our_stack > 0:
        remaining = state.our_stack
        if decision.amount >= remaining * 0.9:
            decision = Decision(
                action=Action.ALL_IN,
                amount=round(remaining, 2),
                display=f"ALL-IN ${remaining:.2f}",
                explanation=decision.explanation,
                calculation=f"Stack: ${remaining:.0f} — shove is cleaner than a near-stack bet",
                confidence=decision.confidence,
            )
    
    return decision