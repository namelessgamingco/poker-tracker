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
    
    # Display: specific hand type for user-facing text (e.g. "set", "flush", "quads")
    # Engine logic uses hand_strength enum; this is ONLY for explanation text
    hand_strength_display: Optional[str] = None
    
    # True when the player holds the best possible hand given the board
    is_nuts: bool = False


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
    "monster": "a very strong hand",
    # Specific monster subtypes — shown to user for excitement + clarity
    "royal_flush": "a royal flush",
    "straight_flush": "a straight flush",
    "quads": "four of a kind",
    "full_house": "a full house",
    "flush": "a flush",
    "straight": "a straight",
    "set": "a set",
    "trips": "trips",
    # Standard hand types
    "two_pair": "two pair",
    "overpair": "an overpair",
    "tptk": "top pair top kicker",
    "top_pair": "top pair",
    "middle_pair": "middle pair",
    "bottom_pair": "bottom pair",
    "underpair": "an underpair",
    "combo_draw": "a combo draw",
    "flush_draw": "a flush draw",
    "oesd": "an open-ended straight draw",
    "gutshot": "a gutshot draw",
    "overcards": "overcards",
    "air": "nothing",
}

def _hs(hand_strength, display_name: str = None) -> str:
    """Get display name for hand strength (with article: 'a', 'an', 'the').
    
    Always uses display_name when available — this is what the player actually has.
    The engine enum may differ due to board-danger downgrades (e.g. TWO_PAIR→OVERPAIR
    on a counterfeited board), but the user should see 'two pair' not 'overpair'.
    """
    # Always prefer the specific display name (what you actually have)
    if display_name and display_name in HAND_DISPLAY:
        return HAND_DISPLAY[display_name]
    val = hand_strength.value if hasattr(hand_strength, 'value') else str(hand_strength)
    return HAND_DISPLAY.get(val, val)

def _hs_bare(hand_strength, display_name: str = None) -> str:
    """Get display name WITHOUT leading article — use after 'your', 'fold', etc."""
    text = _hs(hand_strength, display_name)
    for prefix in ("a ", "an ", "the "):
        if text.startswith(prefix):
            return text[len(prefix):]
    return text

# Open ranges by position (hands to open-raise with)
# Format: set of hand strings
# AUDIT FIX: Expanded all ranges to match 6-max GTO targets
# UTG ~10%, HJ ~14%, CO ~25%, BTN ~43%, SB ~40%
OPEN_RANGES = {
    Position.UTG: {
        "AA", "KK", "QQ", "JJ", "TT", "99", "88", "77", "66",
        "AKs", "AQs", "AJs", "ATs", "A9s", "KQs", "KJs", "KTs", "QJs", "QTs", "JTs",
        "AKo", "AQo", "AJo"
    },
    Position.HJ: {
        "AA", "KK", "QQ", "JJ", "TT", "99", "88", "77", "66", "55",
        "AKs", "AQs", "AJs", "ATs", "A9s", "A8s",
        "KQs", "KJs", "KTs", "K9s", "QJs", "QTs", "JTs", "J9s", "T9s", "98s", "87s",
        "AKo", "AQo", "AJo", "ATo", "KQo", "KJo"
    },
    Position.CO: {
        "AA", "KK", "QQ", "JJ", "TT", "99", "88", "77", "66", "55", "44", "33", "22",
        "AKs", "AQs", "AJs", "ATs", "A9s", "A8s", "A7s", "A6s", "A5s", "A4s", "A3s", "A2s",
        "KQs", "KJs", "KTs", "K9s", "K8s", "K7s",
        "QJs", "QTs", "Q9s", "JTs", "J9s", "J8s", "T9s", "T8s", "98s", "97s",
        "87s", "86s", "76s", "75s", "65s", "64s", "54s",
        "AKo", "AQo", "AJo", "ATo", "A9o", "KQo", "KJo", "KTo", "QJo", "QTo", "JTo"
    },
    Position.BTN: {
        "AA", "KK", "QQ", "JJ", "TT", "99", "88", "77", "66", "55", "44", "33", "22",
        "AKs", "AQs", "AJs", "ATs", "A9s", "A8s", "A7s", "A6s", "A5s", "A4s", "A3s", "A2s",
        "KQs", "KJs", "KTs", "K9s", "K8s", "K7s", "K6s", "K5s", "K4s", "K3s", "K2s",
        "QJs", "QTs", "Q9s", "Q8s", "Q7s", "Q6s", "Q5s",
        "JTs", "J9s", "J8s", "J7s",
        "T9s", "T8s", "T7s",
        "98s", "97s", "96s",
        "87s", "86s", "85s",
        "76s", "75s", "74s",
        "65s", "64s", "63s",
        "54s", "53s", "52s",
        "43s",
        "AKo", "AQo", "AJo", "ATo", "A9o", "A8o", "A7o", "A6o", "A5o",
        "KQo", "KJo", "KTo", "K9o",
        "QJo", "QTo", "Q9o",
        "JTo", "J9o", "J8o",
        "T9o", "T8o",
        "98o", "97o",
        "87o",
    },
    Position.SB: {
        # Mirror BTN range (spec: "similar to BTN")
        "AA", "KK", "QQ", "JJ", "TT", "99", "88", "77", "66", "55", "44", "33", "22",
        "AKs", "AQs", "AJs", "ATs", "A9s", "A8s", "A7s", "A6s", "A5s", "A4s", "A3s", "A2s",
        "KQs", "KJs", "KTs", "K9s", "K8s", "K7s", "K6s", "K5s", "K4s", "K3s", "K2s",
        "QJs", "QTs", "Q9s", "Q8s", "Q7s", "Q6s", "Q5s",
        "JTs", "J9s", "J8s", "J7s",
        "T9s", "T8s", "T7s",
        "98s", "97s", "96s",
        "87s", "86s", "85s",
        "76s", "75s", "74s",
        "65s", "64s", "63s",
        "54s", "53s", "52s",
        "43s",
        "AKo", "AQo", "AJo", "ATo", "A9o", "A8o", "A7o", "A6o", "A5o",
        "KQo", "KJo", "KTo", "K9o",
        "QJo", "QTo", "Q9o",
        "JTo", "J9o", "J8o",
        "T9o", "T8o",
        "98o", "97o",
        "87o",
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

# FIX 1.1: BB DEFENSE FLOOR — hands that ALWAYS defend from BB vs standard opens (≤5BB raise)
# These hands have too much equity and/or implied odds to ever fold from BB at these pot odds.
# Covers gaps where classify_preflop_hand returns MARGINAL or TRASH for hands that should defend.
BB_ALWAYS_DEFEND = {
    # All pairs (set-mining value alone justifies call)
    "AA","KK","QQ","JJ","TT","99","88","77","66","55","44","33","22",
    # All suited aces (nut flush potential)
    "AKs","AQs","AJs","ATs","A9s","A8s","A7s","A6s","A5s","A4s","A3s","A2s",
    # Strong offsuit aces
    "AKo","AQo","AJo","ATo","A9o","A8o",
    # Broadway combos
    "KQs","KJs","KTs","KQo","KJo",
    "QJs","QTs","QJo",
    "JTs",
    # Suited connectors and 1-gappers (playability + implied odds)
    "T9s","98s","87s","76s","65s","54s",
    "J9s","T8s","97s","86s","75s",
    # Suited kings/queens that play well postflop
    "K9s","K8s","K7s","K6s","K5s",
    "Q9s","Q8s",
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
    if not hand or len(hand) < 2:
        return HandStrength.PLAYABLE
    h = normalize_hand(hand)
    if not h or len(h) < 2:
        return HandStrength.PLAYABLE
    
    if h in PREMIUM_HANDS:
        return HandStrength.PREMIUM
    if h in STRONG_HANDS:
        return HandStrength.STRONG
    
    # Pairs 99-22 (AA-TT already caught by PREMIUM_HANDS/STRONG_HANDS above)
    if len(h) == 2 and h[0] == h[1]:
        rank = h[0]
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
    
    # Offsuit connectors (87o, 98o, T9o, etc.) — marginal implied odds hands
    # Good enough to limp behind on BTN but not strong enough to open-raise
    if len(h) == 3 and h[2] == 'o':
        rank_order = "AKQJT98765432"
        r1 = rank_order.index(h[0])
        r2 = rank_order.index(h[1])
        gap = abs(r1 - r2)
        # Only connected (gap=1) offsuit with at least one card 5+ (not 32o, 43o)
        if gap == 1 and r1 <= 8:  # T9o through 54o
            return HandStrength.MARGINAL
    
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
    villain_is_fish: bool = False,
    board_texture: Optional[BoardTexture] = None
) -> Tuple[float, float]:
    """
    Calculate value bet size.
    
    Returns: (bet_amount, percentage)
    
    From spec:
        Turn: 66-75% pot for monsters, 50-66% for top pair
        River: 66-100% pot for value
        vs Fish: +20% sizing (TIER1-FIX)
        
    Board texture adjustment:
        Wet boards: +10% pot (charge draws, protect equity)
        Dry boards: -10% pot (only better hands call big bets)
        Paired boards: -5% pot (fewer combos call)
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
    
    # Board texture adjustment — size up on wet boards, down on dry
    if board_texture == BoardTexture.WET:
        pct = min(pct + 0.10, 1.25)  # Charge draws heavily
    elif board_texture == BoardTexture.DRY:
        pct = max(pct - 0.10, 0.33)  # Smaller on dry — only better calls big
    elif board_texture == BoardTexture.PAIRED:
        pct = max(pct - 0.05, 0.33)  # Slightly smaller on paired boards
    
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


# ── FIX 3.1: BET ROUNDING ──
def round_bet(amount: float, stakes: str) -> float:
    """Round bet to clean amount appropriate for the stakes."""
    round_to = {
        '$0.50/$1': 0.50, '$1/$2': 1.00, '$2/$5': 1.00,
        '$5/$10': 5.00, '$10/$20': 5.00, '$25/$50': 10.00,
    }.get(stakes, 1.00)
    rounded = round(amount / round_to) * round_to
    return max(round_to, rounded)  # Never round to 0


# Draw outs for coaching text
DRAW_OUTS = {
    HandStrength.COMBO_DRAW: ("combo draw", "12+ outs"),
    HandStrength.FLUSH_DRAW: ("flush draw", "9 outs"),
    HandStrength.OESD: ("open-ended straight draw", "8 outs"),
    HandStrength.GUTSHOT: ("gutshot", "4 outs"),
}

def _draw_desc(hs: HandStrength, street: Street) -> str:
    """Return draw description with outs and equity for coaching text."""
    info = DRAW_OUTS.get(hs)
    if not info:
        return ""
    name, outs = info
    equity = get_draw_equity(hs, street)
    return f"{name} ({outs}, ~{equity*100:.0f}% to hit)"


# ── FIX 3.2: BLUFF FREQUENCY ESTIMATION ──
def estimate_fold_frequency(spot_type: str, bet_pct_of_pot: float, villain_type: VillainType) -> float:
    """Estimate villain fold frequency based on spot type, sizing, and villain."""
    base_folds = {
        'river_barrel': 0.48,
        'river_probe': 0.58,
        'dry_board_cbet': 0.53,
        'turn_probe': 0.53,
    }.get(spot_type, 0.50)
    
    # Larger bets get more folds (0.5 pot → base, 1.0 pot → +10%)
    sizing_adjustment = (bet_pct_of_pot - 0.50) * 0.20
    
    # Fish fold much less — should never bluff them (handled elsewhere)
    if villain_type == VillainType.FISH:
        return 0.25
    
    # Regs fold slightly more
    if villain_type == VillainType.REG:
        base_folds += 0.03
    
    return min(0.80, max(0.20, base_folds + sizing_adjustment))


# ── FIX 3.5: MADE HAND EQUITY ESTIMATES ──
MADE_HAND_EQUITY = {
    (HandStrength.NUTS, 'small'): 0.95,
    (HandStrength.NUTS, 'large'): 0.90,
    (HandStrength.MONSTER, 'small'): 0.85,
    (HandStrength.MONSTER, 'large'): 0.78,
    (HandStrength.TWO_PAIR, 'small'): 0.72,
    (HandStrength.TWO_PAIR, 'large'): 0.60,
    (HandStrength.OVERPAIR, 'small'): 0.70,
    (HandStrength.OVERPAIR, 'large'): 0.55,
    (HandStrength.TOP_PAIR_TOP_KICKER, 'small'): 0.65,
    (HandStrength.TOP_PAIR_TOP_KICKER, 'large'): 0.50,
    (HandStrength.TOP_PAIR, 'small'): 0.60,
    (HandStrength.TOP_PAIR, 'large'): 0.42,
    (HandStrength.MIDDLE_PAIR, 'small'): 0.45,
    (HandStrength.MIDDLE_PAIR, 'large'): 0.30,
}

def get_made_hand_ev(hand_strength: HandStrength, pot_size: float, facing_bet: float, pot_odds: float) -> str:
    """Get EV calculation string for made hand decisions.
    Shows equity math — does NOT recommend an action (the engine handles that
    based on additional factors like bet sizing, river dynamics, and villain range)."""
    bet_ratio = facing_bet / pot_size if pot_size > 0 else 0.5
    size_cat = 'small' if bet_ratio <= 0.50 else 'large'
    equity = MADE_HAND_EQUITY.get((hand_strength, size_cat), 0.50)
    ev_call = round((equity * (pot_size + facing_bet)) - ((1 - equity) * facing_bet), 2)
    return f"~{equity*100:.0f}% equity vs their range, need {pot_odds*100:.0f}% (EV: ${ev_call:+.0f})"


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
        "hand_strength_display": None,  # populated by caller if available
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
# FIX 1.5: BOARD-RELATIVE HAND STRENGTH ADJUSTMENT
# =============================================================================

RANK_VALUES = {"A":14,"K":13,"Q":12,"J":11,"T":10,"9":9,"8":8,"7":7,"6":6,"5":5,"4":4,"3":3,"2":2}

def _parse_board_cards(board: str) -> list:
    """Parse board string into list of (rank, suit) tuples.
    Handles formats: '7cJcQdKdTd', '7c Jc Qd Kd Td', 'Kh7c2d'
    """
    if not board:
        return []
    board = board.strip().replace(" ", "")
    cards = []
    i = 0
    while i < len(board) - 1:
        rank = board[i].upper()
        suit = board[i+1].lower()
        if rank in RANK_VALUES and suit in "hdcs":
            cards.append((rank, suit))
            i += 2
        else:
            i += 1
    return cards

def _has_four_to_straight(board_cards: list) -> bool:
    """Check if 4+ board cards form a near-straight (within 4-rank span)."""
    if len(board_cards) < 4:
        return False
    ranks = sorted(set(RANK_VALUES[c[0]] for c in board_cards), reverse=True)
    # Check every 4-card window
    for i in range(len(ranks) - 3):
        window = ranks[i:i+4]
        if window[0] - window[3] <= 4:  # 4 cards within a 5-rank span = straight possible
            return True
    return False

def _count_flush_suits(board_cards: list) -> int:
    """Return the count of the most common suit on board."""
    if not board_cards:
        return 0
    from collections import Counter
    suit_counts = Counter(c[1] for c in board_cards)
    return suit_counts.most_common(1)[0][1]

def _hand_has_suit(our_hand: str, suit: str) -> bool:
    """Check if our hand contains the given suit."""
    if not our_hand or len(our_hand) < 4:
        return False
    hand = our_hand.strip().replace(" ", "")
    return (len(hand) >= 2 and hand[1].lower() == suit) or (len(hand) >= 4 and hand[3].lower() == suit)

def _get_board_flush_suit(board_cards: list) -> Optional[str]:
    """Return the suit with 3+ cards on board, or None."""
    if not board_cards:
        return None
    from collections import Counter
    suit_counts = Counter(c[1] for c in board_cards)
    for suit, count in suit_counts.most_common():
        if count >= 3:
            return suit
    return None

# Hand strength downgrade map: current → downgraded
STRENGTH_DOWNGRADE = {
    HandStrength.NUTS: HandStrength.MONSTER,
    HandStrength.MONSTER: HandStrength.TWO_PAIR,
    HandStrength.TWO_PAIR: HandStrength.OVERPAIR,
    HandStrength.OVERPAIR: HandStrength.TOP_PAIR_TOP_KICKER,
    HandStrength.TOP_PAIR_TOP_KICKER: HandStrength.TOP_PAIR,
    HandStrength.TOP_PAIR: HandStrength.MIDDLE_PAIR,
    HandStrength.MIDDLE_PAIR: HandStrength.BOTTOM_PAIR,
}

def adjust_hand_strength_for_board(
    hand_strength: HandStrength,
    board: Optional[str],
    our_hand: Optional[str],
) -> HandStrength:
    """
    FIX 1.5: Downgrade hand strength when board is dangerous.
    
    A set on K-7-2 rainbow is a monster.
    A set on T-J-Q-K with flush draw is barely strong.
    
    Danger signals:
    1. Four-to-a-straight on board → downgrade 1 tier
    2. Four-to-a-flush on board (we don't have it) → downgrade 1 tier
    3. Both dangers → downgrade 2 tiers
    4. Monotone board (3+ same suit, we don't have flush card) → downgrade 1 tier
    
    Only applies to strong made hands (NUTS through TWO_PAIR).
    Draws and weak hands are not affected.
    """
    # Only adjust strong made hands (NUTS through TWO_PAIR)
    # Weaker hands (top pair, middle pair, etc.) don't need board-danger adjustments
    # because they're already played cautiously
    ADJUSTABLE_HANDS = {
        HandStrength.NUTS, HandStrength.MONSTER, HandStrength.TWO_PAIR,
        HandStrength.OVERPAIR, HandStrength.TOP_PAIR_TOP_KICKER,
    }
    if hand_strength not in ADJUSTABLE_HANDS:
        return hand_strength
    
    if not board:
        return hand_strength
    
    board_cards = _parse_board_cards(board)
    if len(board_cards) < 3:
        return hand_strength
    
    downgrades = 0
    
    # Check for four-to-a-straight
    # BUT: Don't downgrade MONSTER/NUTS for this — if we're MONSTER, we likely
    # HAVE the straight (or a set/flush that beats it). Only downgrade weaker hands.
    if _has_four_to_straight(board_cards):
        if hand_strength not in [HandStrength.NUTS, HandStrength.MONSTER]:
            downgrades += 1
    
    # Check for flush danger
    flush_suit = _get_board_flush_suit(board_cards)
    flush_count = _count_flush_suits(board_cards)
    
    if flush_count >= 4:
        # Four-to-a-flush or completed flush on board
        we_have_flush = our_hand and flush_suit and _hand_has_suit(our_hand, flush_suit)
        if not we_have_flush:
            # MONSTER (set/trips) on 4-flush: still strong (can fill up), don't downgrade
            # Only downgrade weaker hands (two pair, overpair, etc.)
            if hand_strength not in [HandStrength.NUTS, HandStrength.MONSTER]:
                downgrades += 1
    elif flush_count >= 3:
        # Monotone board — mild danger
        we_have_suit = our_hand and flush_suit and _hand_has_suit(our_hand, flush_suit)
        if not we_have_suit:
            # Only downgrade below-monster hands on 3-flush
            if hand_strength not in [HandStrength.NUTS, HandStrength.MONSTER]:
                downgrades += 1
    
    # Pocket pair on paired board detection:
    # When we have a pocket pair (e.g. 66) and the board is paired (e.g. 3-7-3),
    # the frontend classifies this as TWO_PAIR (66+33). But EVERYONE has the board
    # pair — our real strength is just our pocket pair relative to the other board cards.
    # Example: 66 on 3♠7♠3♥ → "two pair" but any 7x has better two pair, any 3x has trips.
    # Downgrade to OVERPAIR if PP > all non-paired board cards, else MIDDLE_PAIR.
    if hand_strength == HandStrength.TWO_PAIR and our_hand:
        hand_clean = our_hand.strip().replace(" ", "")
        hole_ranks = []
        hi = 0
        while hi < len(hand_clean) - 1:
            r = hand_clean[hi].upper()
            s = hand_clean[hi+1].lower()
            if r in RANK_VALUES and s in "hdcs":
                hole_ranks.append(RANK_VALUES[r])
                hi += 2
            else:
                hi += 1
        
        if len(hole_ranks) >= 2 and hole_ranks[0] == hole_ranks[1]:
            # We have a pocket pair — check if board is paired with a DIFFERENT rank
            pp_rank = hole_ranks[0]
            board_ranks = [RANK_VALUES.get(c[0], 0) for c in board_cards]
            from collections import Counter
            board_rank_counts = Counter(board_ranks)
            board_pairs = [r for r, cnt in board_rank_counts.items() if cnt >= 2]
            
            if board_pairs and pp_rank not in board_pairs:
                # Board is paired but NOT with our rank → our "two pair" is fake
                # (pocket pair + shared board pair, everyone has the board pair)
                non_paired_board = [r for r in board_ranks if board_rank_counts[r] < 2]
                max_non_paired = max(non_paired_board) if non_paired_board else 0
                
                if pp_rank > max_non_paired:
                    # PP above all other board cards → effectively an overpair
                    downgrades += 1  # TWO_PAIR → OVERPAIR
                else:
                    # PP below at least one non-paired board card → middle pair territory
                    downgrades += 2  # TWO_PAIR → OVERPAIR → TPTK (or further)
    
    # Board-pair counterfeit detection:
    # When board has a high pair (e.g. AA on board) and we have "two pair",
    # our two pair is effectively just one pair + board pair — much weaker.
    # Example: We have KJ, board is K-J-A-A → our "two pair" is AA+KK but any Ax crushes us.
    if hand_strength == HandStrength.TWO_PAIR and our_hand and len(board_cards) >= 4:
        board_ranks = [RANK_VALUES.get(c[0], 0) for c in board_cards]
        from collections import Counter
        board_rank_counts = Counter(board_ranks)
        board_pairs = [r for r, cnt in board_rank_counts.items() if cnt >= 2]
        
        if board_pairs:
            # Parse our hole cards
            hand_clean = our_hand.strip().replace(" ", "")
            hole_ranks = []
            hi = 0
            while hi < len(hand_clean) - 1:
                r = hand_clean[hi].upper()
                s = hand_clean[hi+1].lower()
                if r in RANK_VALUES and s in "hdcs":
                    hole_ranks.append(RANK_VALUES[r])
                    hi += 2
                else:
                    hi += 1
            
            if len(hole_ranks) >= 2:
                # If board pair is higher than both our hole cards, our two pair is counterfeited
                # (board pair dominates — anyone with a card matching the board pair has trips+)
                max_board_pair = max(board_pairs)
                if max_board_pair > max(hole_ranks):
                    downgrades += 1  # Downgrade TWO_PAIR → OVERPAIR tier
    
    # Apply downgrades
    result = hand_strength
    for _ in range(downgrades):
        if result in STRENGTH_DOWNGRADE:
            result = STRENGTH_DOWNGRADE[result]
        else:
            break
    
    return result


# =============================================================================
# MAIN DECISION ENGINE
# =============================================================================



# =============================================================================
# COACHING TEXT SYSTEM
# =============================================================================
# Generates rich, situational coaching text that feels like a pro
# whispering in your ear. Uses actual game math from each decision point.
# =============================================================================


def _fold_text(msg: str, state: GameState) -> str:
    """Add 'Save the $X' when folding to a bet, plus discipline closer."""
    if state.facing_bet and state.facing_bet > 0:
        return f"{msg} Save the ${state.facing_bet:.0f} and live to play the next hand. Discipline wins long-term."
    return msg

def _hand_read(state: GameState) -> str:
    """What you have, why it matters on THIS board. One sentence."""
    dn = state.hand_strength_display or ""
    nuts = state.is_nuts
    bt = state.board_texture
    street = state.street
    board = state.board or ""
    fish = state.villain_type == VillainType.FISH
    
    # ── NUTS ──
    if nuts:
        return {
            "royal_flush": "You have a royal flush — the best hand in poker",
            "straight_flush": "You have a straight flush — virtually unbeatable",
            "quads": "You have quads — you literally cannot lose this hand",
            "flush": "You have the nut flush — no better flush exists on this board",
            "straight": "You have the nut straight — nothing beats you right now",
            "full_house": "You have the top full house — only quads beats this",
            "set": "You have top set — you dominate every other made hand on this board",
            "trips": "You have the best possible hand here",
        }.get(dn, "You have the best possible hand")
    
    # ── SET (hidden monster — they can't see it) ──
    if dn == "set":
        if street == Street.RIVER:
            if bt == BoardTexture.WET:
                return "You've got a set — your hand is hidden and the board is scary, but if they had the flush or straight they'd have raised by now"
            return "You've got a set on the river — your hand is invisible and they'll pay off with worse"
        if bt == BoardTexture.WET:
            return "You've got a set and it's completely hidden, but this board is draw-heavy — bet big to charge draws now"
        return "You've got a set — your hand is invisible and they'll overplay top pair against you"
    
    # ── TRIPS (visible — pair on board, kicker wars) ──
    if dn == "trips":
        if street == Street.RIVER:
            return "You have trips, but the pair is on the board so better kickers and full houses are in play"
        return "You have trips — strong, but the pair on the board means anyone with a higher kicker has you beat"
    
    # ── FLUSH ──
    if dn == "flush":
        board_cards = _parse_board_cards(board)
        flush_count = _count_flush_suits(board_cards) if board_cards else 0
        if bt == BoardTexture.PAIRED:
            return "You have a flush but the board is paired — full houses are possible and that limits how aggressive you can be"
        if street == Street.TURN:
            return "You have a flush — you're ahead of every one-pair and two-pair hand right now"
        if flush_count >= 4:
            return "You have a flush on a four-flush board — be aware that a higher flush card beats you"
        return "You have a flush — the only hands beating you are a higher flush or a full house"
    
    # ── STRAIGHT ──
    if dn == "straight":
        board_cards = _parse_board_cards(board)
        flush_count = _count_flush_suits(board_cards) if board_cards else 0
        if flush_count >= 3:
            if street == Street.RIVER:
                return "You have a straight — but the flush-possible board means you could be behind if they have it"
            return "You have a straight but there's a flush draw on the board — you need to charge draws now before they get there"
        if bt == BoardTexture.PAIRED:
            return "You have a straight but the paired board means full houses are possible"
        return "You have a straight — you beat every pair, two pair, and set on this board"
    
    # ── FULL HOUSE ──
    if dn == "full_house":
        return "You have a full house — only quads or a bigger boat can beat you here"
    
    # ── QUADS ──
    if dn == "quads":
        return "You have four of a kind — the only challenge is extracting maximum value without scaring them away"
    
    # ── ROYAL / STRAIGHT FLUSH ──
    if dn == "royal_flush":
        return "You have a royal flush — the best hand in poker"
    if dn == "straight_flush":
        return "You have a straight flush — virtually unbeatable"
    
    return ""


def _coach(state: GameState, action: str, fallback: str = "", **ctx) -> str:
    """
    Build a complete coaching explanation with real game data.
    
    Args:
        state: Full game state
        action: What we're recommending ("bet_value", "raise", "check_trap", etc.)
        fallback: Generic text if no specific coaching applies
        **ctx: Contextual numbers from the call site:
            amount: bet/raise amount
            pot_pct: bet as percentage of pot (0.33, 0.66, etc.)
            facing: bet we're facing
            pot_odds: equity needed to call
            equity: our estimated equity
            cr_size: planned check-raise size
            bet_ratio: their bet / pot
            spr: stack-to-pot ratio
    """
    hand_read = _hand_read(state)
    dn = state.hand_strength_display or ""
    nuts = state.is_nuts
    fish = state.villain_type == VillainType.FISH
    reg = state.villain_type == VillainType.REG
    street = state.street
    pot = state.pot_size
    multiway = state.num_players > 2
    has_position = True  # default
    if state.villain_position:
        pos_order = [Position.SB, Position.BB, Position.UTG, Position.HJ, Position.CO, Position.BTN]
        try:
            has_position = pos_order.index(state.our_position) > pos_order.index(state.villain_position)
        except ValueError:
            pass
    
    amount = ctx.get("amount", 0)
    pot_pct = ctx.get("pot_pct", 0)
    facing = ctx.get("facing", state.facing_bet)
    pot_odds = ctx.get("pot_odds", 0)
    cr_size = ctx.get("cr_size", 0)
    bet_ratio = ctx.get("bet_ratio", 0)
    spr = state.spr
    
    # If no hand read (non-monster hand), return fallback
    if not hand_read:
        return fallback
    
    # ══════════════════════════════════════════════
    # BET FOR VALUE (checked to us)
    # ══════════════════════════════════════════════
    if action == "bet_value":
        sizing_desc = f"${amount:.0f}" if amount else ""
        pct_desc = f"{pot_pct*100:.0f}% of the pot" if pot_pct else ""
        
        if nuts:
            if fish:
                return f"{hand_read}. This player calls way too much — bet {pct_desc or sizing_desc} and let them pay you off."
            return f"{hand_read}. Bet {pct_desc or sizing_desc} for value — you want to build the biggest pot possible."
        
        if dn == "set":
            if fish:
                return f"{hand_read}. Bet {pct_desc or sizing_desc} — this player will call with any pair and you'll stack them."
            return f"{hand_read}. Bet {pct_desc or sizing_desc} to build the pot while your hand is disguised."
        
        if dn == "trips":
            return f"{hand_read}. Bet {pct_desc or sizing_desc} for value, but don't overplay it if you face a raise."
        
        if dn == "flush":
            if state.board_texture == BoardTexture.PAIRED:
                return f"{hand_read}. Bet {pct_desc or sizing_desc} for value but fold to a big raise — a full house is the one hand that beats you."
            return f"{hand_read}. Bet {pct_desc or sizing_desc} — one-pair hands will call and you crush them."
        
        if dn == "straight":
            return f"{hand_read}. Bet {pct_desc or sizing_desc} to charge draws and get value from two pair and sets."
        
        if dn in ("full_house", "quads", "royal_flush", "straight_flush"):
            if fish:
                return f"{hand_read}. Size up — this player won't fold, so every dollar you bet prints money."
            return f"{hand_read}. Bet {pct_desc or sizing_desc} to build the pot — you can handle any action."
        
        if fish:
            return f"{hand_read}. Bet {pct_desc or sizing_desc} — this player calls with worse hands, so every dollar you bet prints value."
        return f"{hand_read}. Bet {pct_desc or sizing_desc} for value."
    
    # ══════════════════════════════════════════════
    # BET VALUE MULTIWAY (3+ players)
    # ══════════════════════════════════════════════
    if action == "bet_value_multiway":
        if nuts:
            return f"{hand_read}. Multiple opponents in the pot — bet big, someone is paying you off."
        if dn in ("set", "trips"):
            return f"{hand_read}. Bet {pot_pct*100:.0f}% pot — with this many opponents, someone has a piece and will call." if pot_pct else f"{hand_read}. Bet to protect and extract — someone at this table has a hand they like."
        return f"{hand_read}. Size up into multiple opponents — you want callers."
    
    # ══════════════════════════════════════════════
    # CONTINUE AGGRESSION (turn/river barrel)
    # ══════════════════════════════════════════════
    if action == "continue_aggression":
        st_name = street.value if street else "this street"
        if nuts:
            if fish:
                return f"{hand_read}. Keep betting — this player will keep calling and you want every dollar in the pot."
            return f"{hand_read}. Fire another bet on the {st_name} — your hand is too strong to slow down."
        if dn == "set":
            if fish:
                return f"{hand_read}. Keep betting — this player overvalues one-pair hands and will pay off your set."
            return f"{hand_read}. Bet the {st_name} — your set is hidden and they'll put you on a bluff or overpair."
        if dn == "flush":
            if street == Street.RIVER:
                return f"{hand_read}. Bet for value on the river — worse hands will call trying to catch a bluff."
            return f"{hand_read}. Keep the pressure on — you're ahead of everything except a bigger flush."
        if dn == "straight":
            return f"{hand_read}. Bet the {st_name} to deny equity to flush draws and get value from worse made hands."
        if dn in ("full_house", "quads"):
            return f"{hand_read}. Keep building the pot — you can play for stacks."
        return f"{hand_read}. Keep the pressure on."
    
    # ══════════════════════════════════════════════
    # CHECK-TRAP (defender with monster)
    # ══════════════════════════════════════════════
    if action in ("check_trap", "check_trap_disguised"):
        cr_desc = f" If they bet, raise to ~${cr_size:.0f}." if cr_size else ""
        if dn == "quads":
            return f"{hand_read}. Let them do the betting — if they stab, raise and they'll think you're bluffing.{cr_desc}"
        if dn == "set":
            return f"{hand_read}. Check to let them bet — they'll fire with any pair thinking they're good.{cr_desc}"
        if nuts:
            return f"{hand_read}. Check and let them hang themselves — when they bet, spring the trap.{cr_desc}"
        return f"{hand_read}. Check to disguise your hand and let them bet into you.{cr_desc}"
    
    # ══════════════════════════════════════════════
    # RAISE FACING BET (they bet, we raise)
    # ══════════════════════════════════════════════
    if action == "raise_facing_bet":
        if nuts:
            if fish:
                return f"{hand_read}. Raise big — this player bet into the nuts and won't fold. Make them pay maximum."
            return f"{hand_read}. Raise to ${amount:.0f} — you have the best hand and want all the money in." if amount else f"{hand_read}. Raise — get as much money in as possible."
        if dn == "set":
            return f"{hand_read}. Raise to ${amount:.0f} — they bet into your hidden set. They'll think you're bluffing with how concealed your hand is." if amount else f"{hand_read}. Raise — they have no idea what they just bet into."
        if dn == "straight":
            return f"{hand_read}. Raise to ${amount:.0f} to charge any draws and get value — you currently have the board locked up." if amount else f"{hand_read}. Raise for value — you have the board crushed."
        if dn in ("full_house", "quads"):
            return f"{hand_read}. Raise — you want their entire stack."
        return f"{hand_read}. Raise to ${amount:.0f} — you're ahead of their betting range." if amount else f"{hand_read}. Raise for value."
    
    # ══════════════════════════════════════════════
    # RAISE VALUE (general raise for value)
    # ══════════════════════════════════════════════
    if action == "raise_value":
        if nuts:
            return f"{hand_read}. Raise to ${amount:.0f} — you cannot lose this pot, so get as much in as possible." if amount else f"{hand_read}. Get as much money in as possible."
        return f"{hand_read}. Raise to ${amount:.0f} to build the pot while you're way ahead." if amount else f"{hand_read}. Raise and build the pot."
    
    # ══════════════════════════════════════════════
    # RAISE FACING CHECK-RAISE
    # ══════════════════════════════════════════════
    if action == "raise_facing_checkraise":
        if nuts:
            return f"{hand_read}. They check-raised into the nuts — re-raise and get stacks in."
        if dn == "set":
            return f"{hand_read}. They check-raised into your hidden set — re-raise. They likely have two pair or a draw and you dominate both."
        if dn in ("full_house", "quads"):
            return f"{hand_read}. They check-raised thinking they're strong — re-raise and play for stacks."
        return f"{hand_read}. Re-raise — their check-raise ran into a better hand."
    
    # ══════════════════════════════════════════════
    # RAISE FACING DONK BET
    # ══════════════════════════════════════════════
    if action == "raise_facing_donk":
        if fish:
            return f"{hand_read}. Their donk bet usually means they hit something — but you have them crushed. Raise and they'll call."
        return f"{hand_read}. They led out, which usually means a one-pair hand at these stakes. Raise — your hand dominates their range."
    
    # ══════════════════════════════════════════════
    # CALL STRONG (facing bet with monster)
    # ══════════════════════════════════════════════
    if action == "call_strong":
        if facing and pot:
            call_pct = facing / pot * 100
            if dn == "flush" and state.board_texture == BoardTexture.PAIRED:
                return f"{hand_read}. Call the ${facing:.0f} — you beat most of their value range, but a full house is possible so don't raise."
            if dn == "trips":
                return f"{hand_read}. Call the ${facing:.0f} — you're ahead of most betting hands, but raising could isolate you against only better holdings."
            if nuts:
                return f"{hand_read}. Just call the ${facing:.0f} to keep their bluffs in — raising might fold out everything you beat."
            return f"{hand_read}. Call — you're near the top of your range at {call_pct:.0f}% pot."
        return f"{hand_read}. Call — you're near the top of your range."
    
    # ══════════════════════════════════════════════
    # CALL MONSTER VS RAISE (they raised, we just call)
    # ══════════════════════════════════════════════
    if action == "call_monster_vs_raise":
        if dn == "set":
            return f"{hand_read}. Their raise is strong — probably two pair or a big draw. Just call and let them keep putting money in on later streets."
        if dn == "flush":
            return f"{hand_read}. Their raise is concerning but your flush beats most of their value range. Call and reassess."
        return f"{hand_read}. Their raise is strong but so is your hand. Call and play the next street carefully."
    
    # ══════════════════════════════════════════════
    # ALL-IN COMMITTED (low SPR shove)
    # ══════════════════════════════════════════════
    if action == "all_in_commit":
        spr_desc = f"SPR is only {spr:.1f}" if spr else "You're pot-committed"
        if nuts:
            return f"{hand_read}. {spr_desc} — shove and get paid."
        return f"{hand_read}. {spr_desc} — too much invested to fold. Get it in."
    
    # ══════════════════════════════════════════════
    # FALLBACK
    # ══════════════════════════════════════════════
    return f"{hand_read}." if hand_read else fallback




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
        
        # Default — unrecognized action_facing
        if state.our_position == Position.BB:
            return Decision(
                action=Action.CHECK,
                amount=None,
                display="CHECK",
                explanation=f"Check with {hand}. See a free flop from the big blind.",
                calculation="BB check — free flop",
                confidence=0.70
            )
        return Decision(
            action=Action.FOLD,
            amount=None,
            display="FOLD",
            explanation=f"Fold {hand}. This isn't a spot worth playing — wait for a cleaner opportunity.",
            calculation="Outside playable range",
            confidence=0.70
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
                explanation=f"Check with {hand}. Free flop from the big blind — see what comes.",
                calculation="BB check — see a free flop",
                confidence=0.95
            )
        
        # ── FIX 2.5: BLIND VS BLIND — SB opens much wider vs BB only ──
        # When folded to SB, it's essentially heads-up. Open very wide.
        if position == Position.SB and state.num_players == 2:
            # SB vs BB — open almost any two cards with value
            bvb_open = OPEN_RANGES.get(Position.SB, set())
            # Add extra hands for BvB (any suited, any Ax, connected)
            bvb_extras = {
                "K9o", "K8o", "K7o", "K6o", "K5o",
                "Q9o", "Q8o", "J9o", "J8o", "T9o", "T8o",
                "97o", "87o", "76o", "65o",
                "K5s", "K4s", "K3s", "K2s",
                "Q7s", "Q6s", "Q5s", "Q4s",
                "J7s", "J6s", "T7s", "T6s",
                "96s", "85s", "74s", "63s", "53s", "43s",
                "A8o", "A7o", "A6o", "A5o", "A4o", "A3o", "A2o",
            }
            if hand in bvb_open or hand in bvb_extras:
                fish = _is_fish(state)
                amount = calculate_open_size(position, state.bb_size, 0, fish)
                return Decision(
                    action=Action.RAISE,
                    amount=amount,
                    display=f"RAISE TO ${amount:.2f}",
                    explanation=f"Raise. Blind vs blind — open wide and put pressure on the big blind.",
                    calculation="BvB — wider open range",
                    confidence=0.85
                )
            # Even trash can complete from SB in BvB
            return Decision(
                action=Action.CALL,
                amount=state.bb_size * 0.5,
                display=f"CALL ${state.bb_size * 0.5:.2f}",
                explanation=f"Complete the small blind. Cheap look at a flop heads-up.",
                calculation="BvB — complete for half a BB",
                confidence=0.65
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
            
            # Hand-specific open-raise coaching
            hs = classify_preflop_hand(hand)
            if hs == HandStrength.PREMIUM:
                expl = f"Raise with {hand}. You have a premium hand — build the pot and punish callers."
            elif hs == HandStrength.STRONG:
                expl = f"Raise with {hand} from {position.value}. Strong hand — put pressure on the table."
            elif hand[0] == hand[1] if len(hand) == 2 else False:
                expl = f"Raise with {hand} from {position.value}. Pocket pair — set-mine postflop if called."
            elif len(hand) == 3 and hand[2] == 's':
                expl = f"Raise with {hand} from {position.value}. Suited hand plays well postflop."
            else:
                expl = f"Raise with {hand} from {position.value}. In range — take control of the hand."
            if fish:
                expl = expl.rstrip('.') + " — size up against this weaker opponent."
            
            return Decision(
                action=Action.RAISE,
                amount=amount,
                display=f"RAISE TO ${amount:.2f}",
                explanation=expl,
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
                explanation=f"Fold. {hand} is too weak to open from the small blind.",
                calculation="SB fold — outside open range",
                confidence=0.88
            )
        
        return Decision(
            action=Action.FOLD,
            amount=None,
            display="FOLD",
            explanation=f"Fold. {hand} from {position.value} doesn't make money long-term. Wait for a better spot.",
            calculation=f"Outside open range for {position.value}",
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
                calculation=f"Iso-raise — {state.num_limpers} limper{'s' if state.num_limpers > 1 else ''} × $1BB extra",
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
                    explanation="Check your option. Not strong enough to raise — take the free flop.",
                    calculation="BB check vs limpers",
                    confidence=0.88
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
            elif state.our_position in [Position.BTN, Position.CO, Position.HJ]:
                # Playable hand but not in our open range — limp behind for implied odds
                return Decision(
                    action=Action.CALL,
                    amount=state.bb_size,
                    display=f"CALL ${state.bb_size:.2f}",
                    explanation=f"Limp behind with {hand}. Cheap flop in a multiway pot — play for a big hand.",
                    calculation="Limp behind — implied odds in position",
                    confidence=0.70
                )
        
        # Marginal hands - limp behind from button or cutoff
        if hand_strength == HandStrength.MARGINAL and state.our_position in [Position.BTN, Position.CO]:
            return Decision(
                action=Action.CALL,
                amount=state.bb_size,
                display=f"CALL ${state.bb_size:.2f}",
                explanation=f"Limp behind with {hand}. Cheap flop — try to hit something big.",
                calculation="Limp behind — implied odds play",
                confidence=0.68
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
                    explanation="Check. Not strong enough to iso-raise — see a free flop.",
                    calculation="BB check — free flop vs limpers",
                    confidence=0.90
                )
        
        return Decision(
            action=Action.FOLD,
            amount=None,
            display="FOLD",
            explanation=f"Fold. {hand} isn't strong enough to play, even with limpers in the pot.",
            calculation="Outside playable range vs limpers",
            confidence=0.87
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
                    explanation=f"All-in with {hand}. Your stack is too short for a normal 3-bet — shove for maximum pressure.",
                    calculation=f"Stack ${state.our_stack:.0f} — shove-or-fold territory",
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
                        explanation=f"Fold {hand}. They call too wide — bluff 3-betting won't work here.",
                        calculation="Villain calls too much — no fold equity",
                        confidence=0.82
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
                    explanation=f"Call with {hand}. You have position — outplay them after the flop.",
                    calculation="In position — postflop advantage",
                    confidence=0.83
                )
            # Suited connectors, small pairs - need good odds
            if state.facing_bet <= state.bb_size * 3:
                return Decision(
                    action=Action.CALL,
                    amount=state.facing_bet,
                    display=f"CALL ${state.facing_bet:.2f}",
                    explanation=f"Call with {hand}. If you hit, you'll win a big pot — good implied odds.",
                    calculation="Speculative call — set/straight/flush potential",
                    confidence=0.73
                )
        
        return Decision(
            action=Action.FOLD,
            amount=None,
            display="FOLD",
            explanation=f"Fold. {hand} isn't strong enough to play against this raise.",
            calculation="Outside range vs this raise",
            confidence=0.88
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
        
        # Get 3-bet range for this position (default to widest range if villain position unknown)
        three_bet_range = BB_DEFENSE_3BET.get(villain_pos, BB_DEFENSE_3BET.get(Position.BTN, set()))
        
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
        
        # FIX 1.1: BB DEFENSE FLOOR — never fold hands with clear equity/implied odds
        # This catches hands classified as MARGINAL or TRASH that should always defend
        # Only applies vs standard opens (≤5BB / ≤2.5x the big blind)
        if hand in BB_ALWAYS_DEFEND and state.facing_bet <= state.bb_size * 5:
            return Decision(
                action=Action.CALL,
                amount=state.facing_bet,
                display=f"CALL ${state.facing_bet:.2f}",
                explanation=f"Defend your big blind. {hand} is too strong to fold at this price.",
                calculation=f"BB defense — always defend {hand} vs standard open",
                confidence=0.82
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
            explanation=f"Fold. {hand} can't make money defending here — the price isn't right.",
            calculation="Outside BB defense range at this sizing",
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
        
        # Call with JJ, TT, AQs if deep enough and in position
        if hand in CALL_FOUR_BET or hand in ["JJ", "TT"]:
            we_have_position = self._have_position(state.our_position, state.villain_position)
            # Need sufficient stack depth
            if state.effective_stack_bb >= 80:
                if we_have_position:
                    return Decision(
                        action=Action.CALL,
                        amount=state.facing_bet,
                        display=f"CALL ${state.facing_bet:.2f}",
                        explanation=f"Call the 3-bet with {hand}. Play the flop in position.",
                        calculation="Calling the 3-bet in position",
                        confidence=0.80
                    )
                elif hand in ["JJ", "TT"]:
                    # OOP with JJ/TT — tighter: only call JJ, fold TT
                    if hand == "JJ":
                        return Decision(
                            action=Action.CALL,
                            amount=state.facing_bet,
                            display=f"CALL ${state.facing_bet:.2f}",
                            explanation=f"Call the 3-bet with {hand}. Strong enough to play OOP but proceed carefully.",
                            calculation="Calling 3-bet OOP — reassess on flop",
                            confidence=0.72
                        )
                    else:
                        return Decision(
                            action=Action.FOLD,
                            amount=None,
                            display="FOLD",
                            explanation=f"Fold {hand}. OOP vs a 3-bet with tens is a losing spot long-term.",
                            calculation="TT folds OOP vs 3-bet",
                            confidence=0.78
                        )
                else:
                    # AQs OOP — fold (per M4: AQs only flats in position)
                    return Decision(
                        action=Action.FOLD,
                        amount=None,
                        display="FOLD",
                        explanation=f"Fold {hand}. Out of position vs a 3-bet — hard to realize equity.",
                        calculation="Fold OOP vs 3-bet",
                        confidence=0.80
                    )
        
        # Fold everything else (including our 3-bet bluffs)
        return Decision(
            action=Action.FOLD,
            amount=None,
            display="FOLD",
            explanation=f"Fold {hand}. Their 3-bet is too strong — don't chase.",
            calculation="Outside continue range vs 3-bet",
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
                    calculation=f"Call ${state.facing_bet:.0f} at {state.effective_stack_bb:.0f}BB deep — implied odds postflop",
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
                calculation=f"Call ${state.facing_bet:.0f} at {state.effective_stack_bb:.0f}BB — set-mining implied odds",
                confidence=0.70
            )
        
        # Fold all bluffs and weaker hands
        return Decision(
            action=Action.FOLD,
            amount=None,
            display="FOLD",
            explanation=f"Fold {hand}. A 4-bet means they have it — save your chips.",
            calculation="Only premiums continue vs 4-bet",
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
            calculation=f"Outside push range at {state.effective_stack_bb:.0f}BB",
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
                calculation="Outside continue range vs 4-bet", confidence=0.90)
        
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
                calculation="Too shallow to call — fold and wait", confidence=0.88)
        
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
                        calculation=f"${state.our_stack:.0f} — shove vs 3-bet", confidence=0.90)
                return Decision(
                    action=Action.RAISE, amount=amount,
                    display=f"RAISE TO ${amount:.2f}",
                    explanation=f"3-bet with {hand}. You have enough chips to put real pressure on.",
                    calculation=f"${state.our_stack:.0f} — shove vs 3-bet", confidence=0.88)
            
            # JJ/TT can flat at 30-50BB in position only
            if not is_very_short and hand in ["JJ", "TT"]:
                if self._have_position(state.our_position, state.villain_position):
                    return Decision(
                        action=Action.CALL, amount=state.facing_bet,
                        display=f"CALL ${state.facing_bet:.2f}",
                        explanation=f"Call with {hand} in position. Good depth for set-mining.",
                        calculation="Outside continue range vs 3-bet", confidence=0.75)
            
            # Everything else: fold (not enough implied odds)
            return Decision(
                action=Action.FOLD, amount=None, display="FOLD",
                explanation=f"Fold. Not deep enough to call profitably with {hand}.",
                calculation="Outside continue range vs 3-bet", confidence=0.85)
        
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
        
        # FIX 1.5: Adjust hand strength based on board danger
        # This prevents overbetting vulnerable hands on scary boards
        adjusted_strength = adjust_hand_strength_for_board(
            state.hand_strength, state.board, state.our_hand
        )
        if adjusted_strength != state.hand_strength:
            from dataclasses import replace
            state = replace(state, hand_strength=adjusted_strength)
        
        # Facing check-raise
        if state.action_facing == ActionFacing.CHECK_RAISE:
            return self._facing_check_raise(state)
        
        # FIX 3.4: Donk bet — villain leads into us when we were the preflop aggressor
        if (state.we_are_aggressor 
            and state.action_facing == ActionFacing.BET 
            and state.street == Street.FLOP
            and state.facing_bet > 0):
            return self._facing_donk_bet(state)
        
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

        # Multiway c-bet adjustment: tighten range, size up for protection
        if state.num_players > 2:
            if hand_strength in [HandStrength.NUTS, HandStrength.MONSTER]:
                amount = round(state.pot_size * 0.75, 2)
                if fish:
                    amount = round(amount * 1.2, 2)
                return Decision(
                    action=Action.BET,
                    amount=amount,
                    display=f"BET ${amount:.2f}",
                    explanation=_coach(state, "bet_value_multiway", f"Bet bigger for value with {_hs(hand_strength, state.hand_strength_display)}. Multiple opponents — charge them all.", amount=amount, pot_pct=0.75),
                    calculation=f"Multiway value bet — 75% pot",
                    confidence=0.92
                )
            if hand_strength == HandStrength.TWO_PAIR:
                amount = round(state.pot_size * 0.66, 2)
                if fish:
                    amount = round(amount * 1.2, 2)
                return Decision(
                    action=Action.BET,
                    amount=amount,
                    display=f"BET ${amount:.2f}",
                    explanation=f"Bet with two pair. Protect against draws with this many opponents.",
                    calculation=f"Multiway value bet — 66% pot",
                    confidence=0.88
                )
            if hand_strength in [HandStrength.OVERPAIR, HandStrength.TOP_PAIR_TOP_KICKER]:
                if board_texture in [BoardTexture.WET, BoardTexture.SEMI_WET]:
                    # TPTK/overpair should BET wet boards multiway for protection
                    # Draws are exactly what we're charging — checking lets them see free cards
                    amount = round(state.pot_size * 0.55, 2)
                    if fish:
                        amount = round(amount * 1.2, 2)
                    return Decision(
                        action=Action.BET,
                        amount=amount,
                        display=f"BET ${amount:.2f}",
                        explanation=f"Bet ${amount:.0f} with {_hs(hand_strength, state.hand_strength_display)} for protection. Wet board with multiple opponents — charge the draws now or they'll get there for free.",
                        calculation=f"Multiway protection bet — 55% pot",
                        confidence=0.80
                    )
                amount = round(state.pot_size * 0.50, 2)
                return Decision(
                    action=Action.BET,
                    amount=amount,
                    display=f"BET ${amount:.2f}",
                    explanation=f"Bet with {_hs(hand_strength, state.hand_strength_display)}. Dry board — charge worse hands, but keep the sizing controlled.",
                    calculation=f"Multiway value bet — 50% pot",
                    confidence=0.78
                )
            if hand_strength == HandStrength.TOP_PAIR:
                if board_texture == BoardTexture.DRY:
                    amount = round(state.pot_size * 0.40, 2)
                    return Decision(
                        action=Action.BET,
                        amount=amount,
                        display=f"BET ${amount:.2f}",
                        explanation=f"Small bet with top pair. Dry board helps but multiple opponents means caution.",
                        calculation=f"Multiway thin value — 40% pot",
                        confidence=0.70
                    )
                return Decision(
                    action=Action.CHECK,
                    amount=None,
                    display="CHECK",
                    explanation=f"Check. Top pair isn't strong enough to bet into this many opponents.",
                    calculation="Multiway + top pair = check",
                    confidence=0.78
                )
            if hand_strength in [HandStrength.COMBO_DRAW, HandStrength.FLUSH_DRAW, HandStrength.OESD]:
                return Decision(
                    action=Action.CHECK,
                    amount=None,
                    display="CHECK",
                    explanation=f"Check. Too many opponents to semi-bluff — you need fold equity to bet draws.",
                    calculation="Multiway pot — no semi-bluff fold equity",
                    confidence=0.80
                )
            return Decision(
                action=Action.CHECK,
                amount=None,
                display="CHECK",
                explanation=f"Check. Your {_hs_bare(hand_strength, state.hand_strength_display)} isn't strong enough to bet into multiple opponents.",
                calculation="Multiway pot — check and reassess",
                confidence=0.82
            )

        # Strong hands - always c-bet (size up vs fish)
        if hand_strength in [HandStrength.NUTS, HandStrength.MONSTER, HandStrength.TWO_PAIR, 
                            HandStrength.OVERPAIR, HandStrength.TOP_PAIR_TOP_KICKER]:
            amount, pct = calculate_cbet_size(state.pot_size, board_texture, fish)  # TIER1-FIX: pass fish
            return Decision(
                action=Action.BET,
                amount=amount,
                display=f"BET ${amount:.2f}",
                explanation=_coach(state, "bet_value", f"You have {_hs(hand_strength, state.hand_strength_display)} — bet ${amount:.0f} ({pct*100:.0f}% pot) to charge draws and get value from worse hands. Make them pay to continue.", amount=amount, pot_pct=pct),
                calculation="Value bet — charge draws and weaker hands",
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
                    explanation="Check. Top pair isn't strong enough to bet into multiple opponents on a wet board.",
                    calculation="Multiway + wet board = check",
                    confidence=0.78
                )
            
            amount, pct = calculate_cbet_size(state.pot_size, board_texture, fish)  # TIER1-FIX: pass fish
            # Board-aware and fish-aware coaching
            if fish:
                tp_expl = f"You have top pair — bet ${amount:.0f} ({pct*100:.0f}% pot). This player calls with worse hands, so every dollar you bet prints value."
            elif board_texture == BoardTexture.WET:
                tp_expl = f"You have top pair on a draw-heavy board — bet ${amount:.0f} ({pct*100:.0f}% pot) to charge the draws. Don't let them see a free card."
            elif board_texture == BoardTexture.DRY:
                tp_expl = f"You have top pair on a dry board — bet ${amount:.0f} ({pct*100:.0f}% pot) for thin value. Worse pairs and ace-highs will call."
            else:
                tp_expl = f"You have top pair — bet ${amount:.0f} ({pct*100:.0f}% pot) to charge draws and deny free cards."
            return Decision(
                action=Action.BET,
                amount=amount,
                display=f"BET ${amount:.2f}",
                explanation=tp_expl,
                calculation=f"C-bet — {pct*100:.0f}% pot with top pair",
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
                    explanation=f"You have {_draw_desc(hand_strength, state.street)} — semi-bluff ${amount:.0f} into ${state.pot_size:.0f}. Either they fold and you win now, or you have a strong chance to hit on later streets.",
                    calculation=f"Semi-bluff — {get_draw_equity(hand_strength, state.street)*100:.0f}% equity",
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
                        calculation="Not enough value or fold equity to c-bet",
                        confidence=0.80
                    )
                amount, pct = calculate_cbet_size(state.pot_size, board_texture)
                break_even_pct = round(amount / (state.pot_size + amount), 2)
                bet_pct_of_pot = amount / state.pot_size if state.pot_size > 0 else 0.5
                estimated_fold_pct = estimate_fold_frequency('dry_board_cbet', bet_pct_of_pot, state.villain_type)
                margin = estimated_fold_pct - break_even_pct
                
                # FIX 3.2: Only bluff with sufficient margin
                if margin < 0.15:
                    return Decision(
                        action=Action.CHECK,
                        amount=None,
                        display="CHECK",
                        explanation="Check. They're not folding enough to make a bluff profitable here.",
                        calculation=f"They fold ~{estimated_fold_pct*100:.0f}% but we need more — not worth the risk",
                        confidence=0.72
                    )
                
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
                        f"Dry board, you raised pre — they'll fold to aggression here. "
                        f"${amount:.0f} to win ${state.pot_size:.0f}, "
                        f"only needs to work {break_even_pct*100:.0f}% of the time. "
                        f"Estimated fold rate: ~{estimated_fold_pct*100:.0f}%."
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
            explanation=f"Check with {_hs(hand_strength, state.hand_strength_display)}. Re-evaluate on the next street.",
            calculation="See the next card first",
            confidence=0.80
        )
    
    def _continue_aggression(self, state: GameState) -> Decision:
        """Continue betting on turn/river after c-betting (or delayed c-bet)."""
        
        hand_strength = state.hand_strength
        
        # Reclassify draws and overcards as air on the river
        # Draws missed, overcards didn't pair — enables river barrel bluff analysis for AK/AQ
        if state.street == Street.RIVER and hand_strength in [
            HandStrength.FLUSH_DRAW, HandStrength.OESD,
            HandStrength.COMBO_DRAW, HandStrength.GUTSHOT,
            HandStrength.OVERCARDS,
        ]:
            hand_strength = HandStrength.AIR
        
        fish = _is_fish(state)
        
        # Multiway: only bet strong value hands, no bluffs or thin value
        if state.num_players > 2:
            if hand_strength in [HandStrength.NUTS, HandStrength.MONSTER]:
                amount = round(state.pot_size * 0.75, 2)
                if fish:
                    amount = round(amount * 1.2, 2)
                return Decision(
                    action=Action.BET,
                    amount=amount,
                    display=f"BET ${amount:.2f}",
                    explanation=_coach(state, "bet_value_multiway", f"Keep betting with {_hs(hand_strength, state.hand_strength_display)} — strong enough multiway."),
                    calculation="Multiway value bet — 75% pot",
                    confidence=0.90
                )
            if hand_strength == HandStrength.TWO_PAIR:
                amount = round(state.pot_size * 0.66, 2)
                two_pair_expl = ("Bet with two pair for value — extract from worse hands." 
                                 if state.street == Street.RIVER 
                                 else "Bet with two pair for value and protection against multiple opponents.")
                return Decision(
                    action=Action.BET,
                    amount=amount,
                    display=f"BET ${amount:.2f}",
                    explanation=two_pair_expl,
                    calculation="Multiway value bet — 66% pot",
                    confidence=0.85
                )
            if hand_strength in [HandStrength.OVERPAIR, HandStrength.TOP_PAIR_TOP_KICKER]:
                if state.street == Street.TURN:
                    amount = round(state.pot_size * 0.50, 2)
                    return Decision(
                        action=Action.BET,
                        amount=amount,
                        display=f"BET ${amount:.2f}",
                        explanation=f"Bet with {_hs(hand_strength, state.hand_strength_display)}. Still strong enough for a controlled bet multiway.",
                        calculation="Multiway value bet — 50% pot",
                        confidence=0.75
                    )
                return Decision(
                    action=Action.CHECK,
                    amount=None,
                    display="CHECK",
                    explanation=f"Check. Your {_hs_bare(hand_strength, state.hand_strength_display)} is likely best but betting into multiple opponents on the river only gets called by better. Take the showdown.",
                    calculation="Multiway pot control",
                    confidence=0.78
                )
            return Decision(
                action=Action.CHECK,
                amount=None,
                display="CHECK",
                explanation=f"Check. Your {_hs_bare(hand_strength, state.hand_strength_display)} isn't strong enough to bet into {state.num_players} opponents on the {state.street.value}.",
                calculation=f"Multiway pot — check and control on {state.street.value}",
                confidence=0.80
            )

        # ── FIX 2.4: DELAYED C-BET ──
        # If we checked the flop as aggressor and it's now the turn,
        # many hands benefit from a delayed c-bet (especially on turns
        # that improve our perceived range like A, K, Q)
        # This is handled automatically since _continue_aggression fires
        # on turn when we_are_aggressor is True, even if we checked flop.
        # The logic below already covers value hands and bluffs.
        
        # Value hands - keep betting (size up vs fish)
        if hand_strength in [HandStrength.NUTS, HandStrength.MONSTER, HandStrength.TWO_PAIR,
                            HandStrength.OVERPAIR, HandStrength.TOP_PAIR_TOP_KICKER]:
            amount, pct = calculate_value_bet_size(state.pot_size, state.street, hand_strength, fish, state.board_texture)  # TIER1-FIX: pass fish
            return Decision(
                action=Action.BET,
                amount=amount,
                display=f"BET ${amount:.2f}",
                explanation=_coach(state, "continue_aggression", f"You still have {_hs(hand_strength, state.hand_strength_display)} — bet ${amount:.0f} ({pct*100:.0f}% pot) on the {state.street.value}. Don't slow down.", amount=amount, pot_pct=pct),
                calculation=f"Value bet — {pct*100:.0f}% pot on the {state.street.value}",
                confidence=0.88
            )
        
        # Top pair on turn - bet for protection/value (size up vs fish)
        if hand_strength == HandStrength.TOP_PAIR and state.street == Street.TURN:
            amount, pct = calculate_value_bet_size(state.pot_size, state.street, hand_strength, fish, state.board_texture)  # TIER1-FIX: pass fish
            return Decision(
                action=Action.BET,
                amount=amount,
                display=f"BET ${amount:.2f}",
                explanation=f"Still top pair on the turn — bet ${amount:.0f} to keep charging draws. Don't let them see a free river.",
                calculation=f"Turn value bet — {pct*100:.0f}% pot",
                confidence=0.80
            )
        
        # River with top pair — TIER1-FIX: thin value bet vs fish, check vs reg
        if hand_strength == HandStrength.TOP_PAIR and state.street == Street.RIVER:
            if fish:
                amount, pct = calculate_value_bet_size(state.pot_size, state.street, hand_strength, True, state.board_texture)
                return Decision(
                    action=Action.BET,
                    amount=amount,
                    display=f"BET ${amount:.2f}",
                    explanation=f"This player calls with weaker hands — bet ${amount:.0f} for thin value. They'll pay off with worse pairs.",
                    calculation=f"River thin value vs fish — {pct*100:.0f}% pot",
                    confidence=0.72
                )
            return Decision(
                action=Action.CHECK,
                amount=None,
                display="CHECK",
                explanation="Check with top pair. You're probably ahead — get to showdown without bloating the pot. Only better hands call a river bet.",
                calculation="Pot control — get to showdown",
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
                            calculation="No fold equity vs this player",
                            confidence=0.75
                        )
                    amount = round(state.pot_size * 0.50, 2)
                    return Decision(
                        action=Action.BET,
                        amount=amount,
                        display=f"BET ${amount:.2f}",
                        explanation=f"You still have {_draw_desc(hand_strength, state.street)} — bet ${amount:.0f} as a semi-bluff. One more card to hit, and the bet alone wins it often enough.",
                        calculation=f"Turn semi-bluff — {get_draw_equity(hand_strength, state.street)*100:.0f}% equity on last card",
                        confidence=0.75
                    )
        
        # FIX 2.4: Delayed c-bet with overcards on turn
        # We raised pre, checked flop, now stab the turn with overcards
        if hand_strength == HandStrength.OVERCARDS and state.street == Street.TURN:
            if state.num_players == 2 and not fish:
                amount = round(state.pot_size * 0.50, 2)
                return Decision(
                    action=Action.BET,
                    amount=amount,
                    display=f"BET ${amount:.2f}",
                    explanation="Delayed c-bet. You checked the flop — now bet the turn to take it down.",
                    calculation="Delayed c-bet — representing the turn card",
                    confidence=0.70
                )
        
        # BLUFF SPOT 1: Missed draw on river — BLUFF CHOICE SPOT
        # Also handles delayed c-bet scenario (checked flop, now betting turn)
        if hand_strength == HandStrength.AIR and state.street == Street.RIVER:
            fish = _is_fish(state)
            
            # Only offer bluff if: heads-up, we were aggressor, villain isn't fish
            if state.num_players == 2 and state.we_are_aggressor and not fish:
                bet_amount = round(state.pot_size * 0.66, 2)
                break_even_pct = round(bet_amount / (state.pot_size + bet_amount), 2)
                bet_pct_of_pot = bet_amount / state.pot_size if state.pot_size > 0 else 0.66
                estimated_fold_pct = estimate_fold_frequency('river_barrel', bet_pct_of_pot, state.villain_type)
                margin = estimated_fold_pct - break_even_pct
                
                # FIX 3.2: Thin margin — don't recommend river barrel
                if margin < 0.15:
                    return Decision(
                        action=Action.CHECK,
                        amount=None,
                        display="CHECK",
                        explanation="Give up. A third bet isn't believable enough here — they'll call too often.",
                        calculation=f"They only fold ~{estimated_fold_pct*100:.0f}% — not enough to profit",
                        confidence=0.72
                    )
                
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
                        f"${bet_amount:.0f} to win ${state.pot_size:.0f} — "
                        f"only needs to work {break_even_pct*100:.0f}% of the time. "
                        f"Estimated fold rate: ~{estimated_fold_pct*100:.0f}%."
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
                calculation="Too many opponents to bluff",
                confidence=0.85
            )
        
        # Default check
        return Decision(
            action=Action.CHECK,
            amount=None,
            display="CHECK",
            explanation="Check. No hand worth betting — wait for a better spot." if hand_strength == HandStrength.AIR
                else f"Check. {_hs(hand_strength, state.hand_strength_display).capitalize()} isn't worth betting here.",
            calculation="Not strong enough to keep betting",
            confidence=0.80
        )
    
    def _as_defender(self, state: GameState) -> Decision:
        """We were not the aggressor, it's checked to us."""
        
        hand_strength = state.hand_strength
        
        # Reclassify draws and overcards as air on the river
        if state.street == Street.RIVER and hand_strength in [
            HandStrength.FLUSH_DRAW, HandStrength.OESD,
            HandStrength.COMBO_DRAW, HandStrength.GUTSHOT,
            HandStrength.OVERCARDS,
        ]:
            hand_strength = HandStrength.AIR
        
        fish = _is_fish(state)
        board_texture = state.board_texture or BoardTexture.SEMI_WET
        
        # ── FIX 2.1: CHECK-RAISE INITIATION ──
        # HU only, not vs fish (fish don't bet enough to check-raise profitably)
        if state.num_players == 2 and not fish:
            # Monsters on any board: check to trap, plan to raise
            if hand_strength in [HandStrength.NUTS, HandStrength.MONSTER]:
                cr_size = calculate_check_raise_size(state.pot_size * 0.5, False)
                return Decision(
                    action=Action.CHECK,
                    amount=None,
                    display="CHECK",
                    explanation=_coach(state, "check_trap_disguised", f"Check and trap with {_hs(hand_strength, state.hand_strength_display)}. If they bet, raise to ~${cr_size:.0f}.", cr_size=cr_size),
                    calculation=f"Plan: check-raise to ~${cr_size:.0f}",
                    confidence=0.88
                )
            
            # Two pair on wet boards: check-raise for value + protection
            if hand_strength == HandStrength.TWO_PAIR and board_texture in [BoardTexture.WET, BoardTexture.SEMI_WET]:
                cr_size = calculate_check_raise_size(state.pot_size * 0.5, False)
                return Decision(
                    action=Action.CHECK,
                    amount=None,
                    display="CHECK",
                    explanation=f"Check. If they bet, raise — two pair needs protection on this board.",
                    calculation=f"Plan: check-raise for value + protection",
                    confidence=0.82
                )
        
        # Multiway as defender: only bet monsters and strong value
        if state.num_players > 2:
            if hand_strength in [HandStrength.NUTS, HandStrength.MONSTER]:
                amount = round(state.pot_size * 0.75, 2)
                if fish:
                    amount = round(amount * 1.2, 2)
                return Decision(
                    action=Action.BET,
                    amount=amount,
                    display=f"BET ${amount:.2f}",
                    explanation=_coach(state, "bet_value_multiway", f"Bet with {_hs(hand_strength, state.hand_strength_display)} — everyone is behind you.", amount=amount, pot_pct=0.75),
                    calculation="Multiway value bet — 75% pot",
                    confidence=0.90
                )
            if hand_strength == HandStrength.TWO_PAIR:
                amount = round(state.pot_size * 0.60, 2)
                two_pair_expl = ("Bet with two pair for value — extract from worse hands." 
                                 if state.street == Street.RIVER 
                                 else "Bet with two pair. Protect against draws with this many opponents.")
                return Decision(
                    action=Action.BET,
                    amount=amount,
                    display=f"BET ${amount:.2f}",
                    explanation=two_pair_expl,
                    calculation="Multiway value bet — 60% pot",
                    confidence=0.82
                )
            # Overpair/TPTK on wet boards: bet for protection even as defender
            if hand_strength in [HandStrength.OVERPAIR, HandStrength.TOP_PAIR_TOP_KICKER]:
                if board_texture in [BoardTexture.WET, BoardTexture.SEMI_WET]:
                    amount = round(state.pot_size * 0.50, 2)
                    if fish:
                        amount = round(amount * 1.2, 2)
                    return Decision(
                        action=Action.BET,
                        amount=amount,
                        display=f"BET ${amount:.2f}",
                        explanation=f"Bet ${amount:.0f} with {_hs(hand_strength, state.hand_strength_display)}. Wet board with multiple opponents — charge the draws or they'll get there for free.",
                        calculation=f"Multiway protection bet — 50% pot",
                        confidence=0.78
                    )
                # Dry board: check for pot control (bet only gets called by better)
                if state.street == Street.RIVER:
                    return Decision(
                        action=Action.CHECK,
                        amount=None,
                        display="CHECK",
                        explanation=f"Check. Your {_hs_bare(hand_strength, state.hand_strength_display)} is likely best but betting into multiple opponents on the river only gets called by better. Take the showdown.",
                        calculation="Multiway pot control",
                        confidence=0.78
                    )
                amount = round(state.pot_size * 0.40, 2)
                return Decision(
                    action=Action.BET,
                    amount=amount,
                    display=f"BET ${amount:.2f}",
                    explanation=f"Bet ${amount:.0f} with {_hs(hand_strength, state.hand_strength_display)}. Dry board helps — charge worse hands but keep the sizing controlled.",
                    calculation=f"Multiway value bet — 40% pot",
                    confidence=0.75
                )
            return Decision(
                action=Action.CHECK,
                amount=None,
                display="CHECK",
                explanation="Check. You don't have a hand worth betting into multiple opponents." if hand_strength == HandStrength.AIR
                    else f"Check. {_hs(hand_strength, state.hand_strength_display).capitalize()} isn't strong enough to lead into multiple opponents.",
                calculation="Multiway as defender = check",
                confidence=0.78
            )

        # ── FIX 2.3: DEFENDER VALUE BETTING ──
        # Monsters vs fish — just bet, they'll call with worse
        if hand_strength in [HandStrength.NUTS, HandStrength.MONSTER]:
            amount, pct = calculate_value_bet_size(state.pot_size, state.street, hand_strength, fish, state.board_texture)
            return Decision(
                action=Action.BET,
                amount=amount,
                display=f"BET ${amount:.2f}",
                explanation=_coach(state, "bet_value", f"You have {_hs(hand_strength, state.hand_strength_display)} — bet ${amount:.0f} ({pct*100:.0f}% pot) for value. You're ahead and want to get paid.", amount=amount, pot_pct=pct),
                calculation=f"Value bet — {pct*100:.0f}% pot",
                confidence=0.88
            )
        
        # Two pair on dry boards or vs fish — bet for value
        if hand_strength == HandStrength.TWO_PAIR:
            amount, pct = calculate_value_bet_size(state.pot_size, state.street, hand_strength, fish, state.board_texture)
            return Decision(
                action=Action.BET,
                amount=amount,
                display=f"BET ${amount:.2f}",
                explanation=f"You have two pair — bet ${amount:.0f} to build the pot. You beat any one-pair hand they're holding.",
                calculation=f"Value bet — {pct*100:.0f}% pot",
                confidence=0.85
            )
        
        # Overpair / TPTK on flop/turn — bet for value and protection
        if hand_strength in [HandStrength.OVERPAIR, HandStrength.TOP_PAIR_TOP_KICKER]:
            if state.street in [Street.FLOP, Street.TURN]:
                amount, pct = calculate_value_bet_size(state.pot_size, state.street, hand_strength, fish, state.board_texture)
                return Decision(
                    action=Action.BET,
                    amount=amount,
                    display=f"BET ${amount:.2f}",
                    explanation=f"You have {_hs(hand_strength, state.hand_strength_display)} — bet ${amount:.0f} for value and protection. Worse hands will call, draws will pay too much.",
                    calculation=f"Value bet — {pct*100:.0f}% pot",
                    confidence=0.80
                )
            # River — check to control pot
            return Decision(
                action=Action.CHECK,
                amount=None,
                display="CHECK",
                explanation=f"Check. Your {_hs_bare(hand_strength, state.hand_strength_display)} is likely the best hand — check to guarantee you see showdown without risking a raise.",
                calculation="Pot control — don't bloat the pot",
                confidence=0.78
            )
        
        # ── FIX 2.6: TURN PROBE BLUFF ──
        # Villain bet flop, then checked turn — they gave up. Stab with air.
        if state.street == Street.TURN and state.num_players == 2 and not fish:
            if hand_strength in [HandStrength.AIR, HandStrength.OVERCARDS]:
                bet_amount = round(state.pot_size * 0.50, 2)
                break_even_pct = round(bet_amount / (state.pot_size + bet_amount), 2)
                bet_pct_of_pot = 0.50
                estimated_fold_pct = estimate_fold_frequency('turn_probe', bet_pct_of_pot, state.villain_type)
                margin = estimated_fold_pct - break_even_pct
                
                # FIX 3.2: Margin check
                if margin < 0.15:
                    return Decision(
                        action=Action.CHECK,
                        amount=None,
                        display="CHECK",
                        explanation="Check. A bet here won't get enough folds to be profitable — save your chips.",
                        calculation=f"Fold est. {estimated_fold_pct*100:.0f}%, need {break_even_pct*100:.0f}%",
                        confidence=0.70
                    )
                
                ev_of_bet = round(
                    (estimated_fold_pct * state.pot_size) - ((1 - estimated_fold_pct) * bet_amount), 2
                )
                
                bluff_ctx = BluffContext(
                    spot_type='turn_probe',
                    delivery='choice',
                    recommended_action='BET',
                    bet_amount=bet_amount,
                    pot_size=state.pot_size,
                    ev_of_bet=ev_of_bet,
                    ev_of_check=0.0,
                    break_even_pct=break_even_pct,
                    estimated_fold_pct=estimated_fold_pct,
                    explanation_bet=(
                        f"They checked the turn — they're giving up. "
                        f"${bet_amount:.0f} to win ${state.pot_size:.0f} — "
                        f"only needs to work {break_even_pct*100:.0f}% of the time. "
                        f"Estimated fold rate: ~{estimated_fold_pct*100:.0f}%."
                    ),
                    explanation_check="Check and give up. Save your chips for a better spot.",
                )
                
                bet_decision = Decision(
                    action=Action.BET,
                    amount=bet_amount,
                    display=f"BET ${bet_amount:.2f}",
                    explanation=bluff_ctx.explanation_bet,
                    calculation=f"${bet_amount:.0f} to win ${state.pot_size:.0f}",
                    confidence=0.68,
                    bluff_context=bluff_ctx,
                )
                check_decision = Decision(
                    action=Action.CHECK,
                    amount=None,
                    display="CHECK",
                    explanation=bluff_ctx.explanation_check,
                    calculation="Checking wins $0",
                    confidence=0.68,
                    bluff_context=bluff_ctx,
                )
                bet_decision.alternative = check_decision
                return bet_decision
        
        # BLUFF SPOT 2: River probe bluff — villain showed weakness by checking twice
        if state.street == Street.RIVER and state.num_players == 2:
            if not fish and hand_strength in [HandStrength.AIR, HandStrength.OVERCARDS]:
                bet_amount = round(state.pot_size * 0.50, 2)
                break_even_pct = round(bet_amount / (state.pot_size + bet_amount), 2)
                bet_pct_of_pot = 0.50
                estimated_fold_pct = estimate_fold_frequency('river_probe', bet_pct_of_pot, state.villain_type)
                margin = estimated_fold_pct - break_even_pct
                
                # FIX 3.2: Margin check
                if margin < 0.15:
                    return Decision(
                        action=Action.CHECK,
                        amount=None,
                        display="CHECK",
                        explanation="Check. They're not folding often enough to make a bet profitable here.",
                        calculation=f"Fold est. {estimated_fold_pct*100:.0f}%, need {break_even_pct*100:.0f}%",
                        confidence=0.70
                    )
                
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
                        f"${bet_amount:.0f} to win ${state.pot_size:.0f} — "
                        f"only needs to work {break_even_pct*100:.0f}% of the time. "
                        f"Estimated fold rate: ~{estimated_fold_pct*100:.0f}%."
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
        
        # Top pair — check to pot control
        if hand_strength == HandStrength.TOP_PAIR:
            return Decision(
                action=Action.CHECK,
                amount=None,
                display="CHECK",
                explanation="Check with top pair. You're likely ahead, but betting risks getting raised off your hand. Keep the pot small and get to showdown.",
                calculation="Pot control — protect your equity without building a big pot",
                confidence=0.78
            )
        
        # Middle pair — always check
        if hand_strength == HandStrength.MIDDLE_PAIR:
            return Decision(
                action=Action.CHECK,
                amount=None,
                display="CHECK",
                explanation="Check. Middle pair is too vulnerable to bet for value — if you bet and get raised, you're stuck. Take the free card and see if you improve.",
                calculation="Pot control — avoid building a pot you can't win",
                confidence=0.80
            )
        
        # Draws — check for free card (or give up on river)
        if hand_strength in [HandStrength.FLUSH_DRAW, HandStrength.OESD, HandStrength.COMBO_DRAW]:
            if state.street == Street.RIVER:
                return Decision(
                    action=Action.CHECK,
                    amount=None,
                    display="CHECK",
                    explanation="Check. Your draw missed — no value in betting, and you'll only get called by better hands.",
                    calculation="Missed draw on river = give up",
                    confidence=0.80
                )
            return Decision(
                action=Action.CHECK,
                amount=None,
                display="CHECK",
                explanation=f"Check. You have {_draw_desc(hand_strength, state.street)} — take the free card. You don't have fold equity to semi-bluff from this position, but the draw is strong enough to see another card.",
                calculation="Free card — draw without risking chips",
                confidence=0.75
            )
        
        # Check everything else
        return Decision(
            action=Action.CHECK,
            amount=None,
            display="CHECK",
            explanation="Check. You don't have a hand worth betting — any bet only gets called by hands that beat you.",
            calculation="No value from betting — check and move on",
            confidence=0.85
        )
    
    def _facing_bet(self, state: GameState) -> Decision:
        """Facing a bet or raise post-flop."""
        
        hand_strength = state.hand_strength
        
        # Reclassify draws and overcards as air on the river
        if state.street == Street.RIVER and hand_strength in [
            HandStrength.FLUSH_DRAW, HandStrength.OESD,
            HandStrength.COMBO_DRAW, HandStrength.GUTSHOT,
            HandStrength.OVERCARDS,
        ]:
            hand_strength = HandStrength.AIR
        
        pot_odds = calculate_pot_odds(state.pot_size, state.facing_bet)
        street = state.street
        
        # Calculate bet size relative to pot
        bet_ratio = state.facing_bet / state.pot_size if state.pot_size > 0 else 1.0
        
        # ── FIX 2.7: OVERBET HANDLING (>100% pot) ──
        # Overbets are extremely polarized — fold everything except monsters
        if bet_ratio > 1.2:
            if hand_strength in [HandStrength.NUTS, HandStrength.MONSTER]:
                amount = calculate_check_raise_size(state.facing_bet, _is_fish(state))
                return Decision(
                    action=Action.RAISE,
                    amount=amount,
                    display=f"RAISE TO ${amount:.2f}",
                    explanation=_coach(state, "raise_facing_bet", f"Raise. Their overbet is polarized — {_hs(hand_strength, state.hand_strength_display)} crushes their range.", amount=amount, bet_ratio=bet_ratio),
                    calculation=f"Overbet {bet_ratio*100:.0f}% pot — they're polarized",
                    confidence=0.90
                )
            # AUDIT FIX 4: Overpair added — overbets are polarized (nuts or bluff),
            # overpair has ~50%+ equity vs that polarized range at low stakes
            if hand_strength in [HandStrength.TWO_PAIR, HandStrength.OVERPAIR]:
                return Decision(
                    action=Action.CALL,
                    amount=state.facing_bet,
                    display=f"CALL ${state.facing_bet:.2f}",
                    explanation=f"Call. Overbet is scary but {_hs(hand_strength, state.hand_strength_display)} beats enough of their bluffs in this polarized spot.",
                    calculation=f"Overbet {bet_ratio*100:.0f}% pot — polarized range",
                    confidence=0.65
                )
            # Fold everything else vs overbets
            return Decision(
                action=Action.FOLD,
                amount=None,
                display="FOLD",
                explanation=_fold_text("An overbet this size is almost always the nuts or a big bluff — you don't have a hand to call with.", state) if hand_strength == HandStrength.AIR
                    else _fold_text(f"An overbet this size is almost always the nuts or a big bluff — {_hs(hand_strength, state.hand_strength_display)} can't call.", state),
                calculation=f"Facing {bet_ratio*100:.0f}% pot overbet",
                confidence=0.85
            )
        
        # ── FIX 2.2: POSTFLOP RAISE vs BET ──
        # If action_facing is RAISE (they raised our bet), their range is MUCH stronger
        # Tighten calling ranges significantly
        is_raise = state.action_facing == ActionFacing.RAISE
        
        # TIER1-FIX: SPR commitment — in low SPR pots, commit with top pair+
        # AUDIT FIX: Exclude river — no future streets, so commitment logic
        # (RAISE/ALL-IN to deny equity) doesn't apply. River decisions should
        # go through the sizing-aware _facing_river_bet path instead.
        if state.spr is not None and state.spr < 4 and state.street != Street.RIVER:
            if hand_strength in [HandStrength.NUTS, HandStrength.MONSTER, HandStrength.TWO_PAIR,
                                HandStrength.OVERPAIR, HandStrength.TOP_PAIR_TOP_KICKER, HandStrength.TOP_PAIR]:
                fish = _is_fish(state)
                if state.facing_bet >= state.our_stack * 0.5:
                    return Decision(
                        action=Action.ALL_IN,
                        amount=state.our_stack,
                        display=f"ALL-IN ${state.our_stack:.2f}",
                        explanation=_coach(state, "all_in_commit", f"All-in — pot-committed with {_hs(hand_strength, state.hand_strength_display)}.", spr=state.spr),
                        calculation="Pot-committed",
                        confidence=0.90
                    )
                amt = calculate_check_raise_size(state.facing_bet, fish)
                if amt >= state.our_stack * 0.5:
                    return Decision(
                        action=Action.ALL_IN,
                        amount=state.our_stack,
                        display=f"ALL-IN ${state.our_stack:.2f}",
                        explanation=f"All-in. Pot is too big to fold {_hs_bare(hand_strength, state.hand_strength_display)} — you're committed.",
                        calculation=f"Pot-committed — too much invested to fold",
                        confidence=0.88
                    )
                return Decision(
                    action=Action.RAISE,
                    amount=amt,
                    display=f"RAISE TO ${amt:.2f}",
                    explanation=f"Raise. You're committed with {_hs(hand_strength, state.hand_strength_display)} at this pot size — build the pot now.",
                    calculation=f"SPR {state.spr:.1f} < 4, committed",
                    confidence=0.88
                )
        
        # TIER1-FIX: Multiway tightening — tighter ranges when facing bets multiway
        if state.num_players > 2:
            return self._facing_bet_multiway(state, hand_strength, pot_odds, bet_ratio)
        
        # ── FACING A RAISE (they raised our bet) — much tighter ──
        if is_raise:
            # Nuts — re-raise
            if hand_strength == HandStrength.NUTS:
                amount = calculate_check_raise_size(state.facing_bet, _is_fish(state))
                return Decision(
                    action=Action.RAISE,
                    amount=amount,
                    display=f"RAISE TO ${amount:.2f}",
                    explanation=_coach(state, "raise_value", f"Re-raise with {_hs(hand_strength, state.hand_strength_display)}. Build the biggest pot possible.", amount=amount),
                    calculation="Re-raise for max value",
                    confidence=0.92
                )
            # Monsters, two pair — call
            if hand_strength in [HandStrength.MONSTER, HandStrength.TWO_PAIR]:
                return Decision(
                    action=Action.CALL,
                    amount=state.facing_bet,
                    display=f"CALL ${state.facing_bet:.2f}",
                    explanation=_coach(state, "call_monster_vs_raise", f"Call. A raise is strong but {_hs(hand_strength, state.hand_strength_display)} is ahead enough.", facing=state.facing_bet),
                    calculation="Facing raise — their range is strong",
                    confidence=0.80
                )
            # Overpair, TPTK on flop — call one street
            if hand_strength in [HandStrength.OVERPAIR, HandStrength.TOP_PAIR_TOP_KICKER] and street == Street.FLOP:
                return Decision(
                    action=Action.CALL,
                    amount=state.facing_bet,
                    display=f"CALL ${state.facing_bet:.2f}",
                    explanation=f"Call. Their raise is concerning, but {_hs(hand_strength, state.hand_strength_display)} is too strong to fold on the flop.",
                    calculation="Raises are strong — reassess on later streets",
                    confidence=0.72
                )
            # AUDIT FIX: Top pair — call on flop, fold on turn/river
            # Raises are strong, but top pair has enough equity on the flop to continue.
            # On later streets, a raise after bet-call usually means a stronger hand.
            if hand_strength == HandStrength.TOP_PAIR:
                if street == Street.FLOP:
                    return Decision(
                        action=Action.CALL,
                        amount=state.facing_bet,
                        display=f"CALL ${state.facing_bet:.2f}",
                        explanation=f"Call. A raise is concerning, but top pair is too strong to fold on the flop. Reassess on the turn.",
                        calculation="Facing raise on flop — peel one street with top pair",
                        confidence=0.68
                    )
                return Decision(
                    action=Action.FOLD,
                    amount=None,
                    display="FOLD",
                    explanation=_fold_text(f"A raise on the {street.value} means real strength — top pair isn't enough.", state),
                    calculation="Facing raise — tighten up",
                    confidence=0.82
                )
            # Strong draws — call with equity
            # AUDIT FIX 5: Added OESD (was excluded, only combo/flush checked)
            if hand_strength in [HandStrength.COMBO_DRAW, HandStrength.FLUSH_DRAW, HandStrength.OESD]:
                equity = get_draw_equity(hand_strength, state.street)
                if equity >= pot_odds:
                    return Decision(
                        action=Action.CALL,
                        amount=state.facing_bet,
                        display=f"CALL ${state.facing_bet:.2f}",
                        explanation=f"Call the ${state.facing_bet:.0f}. Their raise is strong but your {_draw_desc(hand_strength, state.street)} has enough equity at this price.",
                        calculation=f"Equity {equity*100:.0f}% >= {pot_odds*100:.0f}% pot odds",
                        confidence=0.75
                    )
            # AUDIT FIX 5: Pot odds safety net for RAISE branch (was missing entirely)
            if pot_odds <= 0.15:
                return Decision(
                    action=Action.CALL,
                    amount=state.facing_bet,
                    display=f"CALL ${state.facing_bet:.2f}",
                    explanation=f"Call the ${state.facing_bet:.0f}. The raise is small relative to the pot — you only need {pot_odds*100:.0f}% equity and that's too cheap to fold.",
                    calculation=f"Pot odds: {pot_odds*100:.1f}% — mandatory call at this price",
                    confidence=0.75
                )
            # Fold everything else vs a raise
            return Decision(
                action=Action.FOLD,
                amount=None,
                display="FOLD",
                explanation=_fold_text("A raise means real strength — you don't have a hand to continue with.", state) if hand_strength == HandStrength.AIR
                    else _fold_text(f"A raise means real strength — {_hs(hand_strength, state.hand_strength_display)} isn't enough to continue.", state),
                calculation="Facing raise — tighten up",
                confidence=0.85
            )
        
        # ── FACING A BET (standard) — normal ranges ──
        # RIVER BETS ARE 85-95% VALUE - KEY INSIGHT FROM SPEC 10
        if street == Street.RIVER and bet_ratio > 0.5:
            return self._facing_river_bet(state, hand_strength, pot_odds, bet_ratio)
        
        # TURN BETS ARE 75-85% VALUE
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
                explanation=_coach(state, "raise_value", f"Raise with {_hs(hand_strength, state.hand_strength_display)} — build a big pot.", amount=amt),
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
                calculation="Multiway pot — tighter range required",
                confidence=0.85
            )
        
        # Overpair/TPTK: call, but fold to large bets on river
        if hand_strength in [HandStrength.OVERPAIR, HandStrength.TOP_PAIR_TOP_KICKER]:
            if state.street == Street.RIVER and bet_ratio >= 0.66:
                return Decision(
                    action=Action.FOLD,
                    amount=None,
                    display="FOLD",
                    explanation=_fold_text(f"Big river bet multiway — someone has you beat.", state),
                    calculation="Multiway pot — tighter range required",
                    confidence=0.85
                )
            return Decision(
                action=Action.CALL,
                amount=state.facing_bet,
                display=f"CALL ${state.facing_bet:.2f}",
                explanation=f"Call with {_hs(hand_strength, state.hand_strength_display)}. Probably ahead, but stay cautious.",
                calculation="Multiway pot — tighter range required",
                confidence=0.80
            )
        
        # Top pair: call small bets on flop AND turn, fold large bets and river
        if hand_strength == HandStrength.TOP_PAIR:
            if state.street in [Street.FLOP, Street.TURN] and bet_ratio <= 0.50:
                return Decision(
                    action=Action.CALL,
                    amount=state.facing_bet,
                    display=f"CALL ${state.facing_bet:.2f}",
                    explanation=f"Call the ${state.facing_bet:.0f}. Top pair beats most of what they're betting at this sizing.",
                    calculation="Multiway pot — tighter range required",
                    confidence=0.70
                )
            return Decision(
                action=Action.FOLD,
                amount=None,
                display="FOLD",
                explanation=_fold_text(f"Top pair isn't enough on the {state.street.value} against this many opponents.", state),
                calculation="Multiway pot — tighter range required",
                confidence=0.80
            )
        
        # Middle/bottom pair: call tiny bets (getting amazing pot odds), fold standard+ bets
        if hand_strength in [HandStrength.MIDDLE_PAIR, HandStrength.BOTTOM_PAIR]:
            if bet_ratio <= 0.15:
                # Tiny bet — pot odds are too good to fold any pair
                return Decision(
                    action=Action.CALL,
                    amount=state.facing_bet,
                    display=f"CALL ${state.facing_bet:.2f}",
                    explanation=f"Call the ${state.facing_bet:.0f}. The bet is tiny relative to the pot — you only need {pot_odds*100:.0f}% equity and {_hs(hand_strength, state.hand_strength_display)} has more than enough at this price.",
                    calculation=f"Pot odds: need {pot_odds*100:.0f}% equity — easy call",
                    confidence=0.72
                )
            if state.street == Street.FLOP and bet_ratio <= 0.40:
                return Decision(
                    action=Action.CALL,
                    amount=state.facing_bet,
                    display=f"CALL ${state.facing_bet:.2f}",
                    explanation=f"Call the ${state.facing_bet:.0f}. Small bet with {_hs(hand_strength, state.hand_strength_display)} multiway — worth one card to see if you improve.",
                    calculation=f"Multiway pot — small bet ({bet_ratio*100:.0f}% pot)",
                    confidence=0.65
                )
            return Decision(
                action=Action.FOLD,
                amount=None,
                display="FOLD",
                explanation=_fold_text(f"Too many opponents for {_hs(hand_strength, state.hand_strength_display)} — you're likely behind.", state),
                calculation="Multiway pot — tighter range required",
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
                    explanation=f"Call the ${state.facing_bet:.0f}. You have {_draw_desc(hand_strength, state.street)} and the multiway pot gives you the price. Multiple opponents means better implied odds when you hit.",
                    calculation=f"Equity {equity*100:.0f}% vs {pot_odds*100:.0f}% needed (multiway implied odds)",
                    confidence=0.78
                )
            return Decision(
                action=Action.FOLD,
                amount=None,
                display="FOLD",
                explanation=_fold_text(f"The price isn't right to chase your {_hs_bare(hand_strength, state.hand_strength_display)} here.", state),
                calculation="Multiway pot — tighter range required",
                confidence=0.80
            )
        
        # Gutshot multiway: call if getting good enough price (implied odds matter multiway)
        if hand_strength == HandStrength.GUTSHOT:
            equity = get_draw_equity(hand_strength, state.street)
            implied_equity = equity * 1.5 if state.street == Street.FLOP else equity * 1.2
            if implied_equity >= pot_odds and bet_ratio <= 0.33:
                return Decision(
                    action=Action.CALL,
                    amount=state.facing_bet,
                    display=f"CALL ${state.facing_bet:.2f}",
                    explanation=f"Call the ${state.facing_bet:.0f}. Gutshot with 4 outs — the small bet and multiway pot give you the implied odds to chase.",
                    calculation=f"~{equity*100:.0f}% equity + multiway implied odds vs {pot_odds*100:.0f}% needed",
                    confidence=0.62
                )
            return Decision(
                action=Action.FOLD,
                amount=None,
                display="FOLD",
                explanation=_fold_text("Not getting the right price for a gutshot multiway.", state),
                calculation="Multiway pot — tighter range required",
                confidence=0.80
            )
        
        # Everything else: fold (but call small bets with any showdown value)
        # AUDIT FIX: Raised from 10% to 15% for consistency across all methods
        if pot_odds <= 0.15:
            return Decision(
                action=Action.CALL,
                amount=state.facing_bet,
                display=f"CALL ${state.facing_bet:.2f}",
                explanation=f"Call the ${state.facing_bet:.0f}. The bet is small relative to the pot — you only need {pot_odds*100:.0f}% equity and that's too cheap to fold even multiway.",
                calculation=f"Pot odds: {pot_odds*100:.1f}% — mandatory call at this price",
                confidence=0.75
            )
        return Decision(
            action=Action.FOLD,
            amount=None,
            display="FOLD",
            explanation=_fold_text("You don't have a hand that can handle the pressure multiway.", state) if hand_strength == HandStrength.AIR
                else _fold_text(f"{_hs(hand_strength, state.hand_strength_display).capitalize()} can't handle the pressure multiway.", state),
            calculation="Multiway pot — tighter range required",
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
        
        # Reclassify draws and overcards as air on the river
        if hand_strength in [
            HandStrength.FLUSH_DRAW, HandStrength.OESD,
            HandStrength.COMBO_DRAW, HandStrength.GUTSHOT,
            HandStrength.OVERCARDS,
        ]:
            hand_strength = HandStrength.AIR
        
        fish = _is_fish(state)  # TIER1-FIX
        
        # Nuts/near-nuts - raise for value (bigger vs fish)
        if hand_strength == HandStrength.NUTS:
            amount = calculate_check_raise_size(state.facing_bet, fish)  # TIER1-FIX: pass fish
            return Decision(
                action=Action.RAISE,
                amount=amount,
                display=f"RAISE TO ${amount:.2f}",
                explanation=_coach(state, "raise_value", "Raise. You have the nuts — extract maximum value.", amount=amount, facing=state.facing_bet),
                calculation="Sized up against weaker opponent" if fish else "Standard raise sizing",
                confidence=0.95
            )
        
        # Monsters - call
        if hand_strength in [HandStrength.MONSTER, HandStrength.TWO_PAIR]:
            return Decision(
                action=Action.CALL,
                amount=state.facing_bet,
                display=f"CALL ${state.facing_bet:.2f}",
                explanation=_coach(state, "call_strong", f"Call with {_hs(hand_strength, state.hand_strength_display)}.", facing=state.facing_bet),
                calculation=get_made_hand_ev(hand_strength, state.pot_size, state.facing_bet, pot_odds),
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
                        explanation=f"Call. This player overvalues their hand — {_hs(hand_strength, state.hand_strength_display)} is ahead.",
                        calculation=get_made_hand_ev(hand_strength, state.pot_size, state.facing_bet, pot_odds),
                        confidence=0.72
                    )
                return Decision(
                    action=Action.FOLD,
                    amount=None,
                    display="FOLD",
                    explanation=_fold_text(f"Big river bets mean business — {_hs(hand_strength, state.hand_strength_display)} isn't strong enough to call here.", state),
                    calculation=get_made_hand_ev(hand_strength, state.pot_size, state.facing_bet, pot_odds),
                    confidence=0.88
                )
            else:
                # Small bet - can call
                return Decision(
                    action=Action.CALL,
                    amount=state.facing_bet,
                    display=f"CALL ${state.facing_bet:.2f}",
                    explanation=f"Call the ${state.facing_bet:.0f}. Small bet gives you a good price — your {_hs_bare(hand_strength, state.hand_strength_display)} beats their weaker value bets and bluffs.",
                    calculation=get_made_hand_ev(hand_strength, state.pot_size, state.facing_bet, pot_odds),
                    confidence=0.70
                )
        
        # AUDIT FIX 1: Bottom pair — call small river bets (was missing, fell to fold)
        if hand_strength == HandStrength.BOTTOM_PAIR:
            if bet_ratio <= 0.33:
                return Decision(
                    action=Action.CALL,
                    amount=state.facing_bet,
                    display=f"CALL ${state.facing_bet:.2f}",
                    explanation=f"Call the ${state.facing_bet:.0f}. Small bet — bottom pair has enough equity at this price to look them up.",
                    calculation=get_made_hand_ev(hand_strength, state.pot_size, state.facing_bet, pot_odds),
                    confidence=0.55
                )
        
        # Pot odds safety net — if the bet is tiny relative to the pot, call with anything
        # AUDIT FIX: Raised from 10% to 15% to close gap between safety net and hand-specific thresholds
        # Example: $6 into $215 = 2.7% pot odds — call with any hand that has any showdown value
        if pot_odds <= 0.15:
            return Decision(
                action=Action.CALL,
                amount=state.facing_bet,
                display=f"CALL ${state.facing_bet:.2f}",
                explanation=f"Call the ${state.facing_bet:.0f}. The bet is small relative to the pot — you only need {pot_odds*100:.0f}% equity and that's too cheap to fold.",
                calculation=f"Pot odds: {pot_odds*100:.1f}% — mandatory call at this price",
                confidence=0.78
            )
        
        # Everything else - fold
        return Decision(
            action=Action.FOLD,
            amount=None,
            display="FOLD",
            explanation=_fold_text(f"You're not beating their betting range with {_hs(hand_strength, state.hand_strength_display)}.", state),
            calculation=f"Need {pot_odds*100:.0f}% equity — not enough to call",
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
                explanation=_coach(state, "raise_facing_bet", f"Raise with {_hs(hand_strength, state.hand_strength_display)} — charge max.", amount=amount),
                calculation="Sized up against weaker opponent" if fish else "Standard raise sizing",
                confidence=0.90
            )
        
        # Two pair, overpair, TPTK - call
        if hand_strength in [HandStrength.TWO_PAIR, HandStrength.OVERPAIR, HandStrength.TOP_PAIR_TOP_KICKER]:
            return Decision(
                action=Action.CALL,
                amount=state.facing_bet,
                display=f"CALL ${state.facing_bet:.2f}",
                explanation=f"Call the ${state.facing_bet:.0f}. Your {_hs_bare(hand_strength, state.hand_strength_display)} is ahead of most of their betting range — reassess on the river.",
                calculation=get_made_hand_ev(hand_strength, state.pot_size, state.facing_bet, pot_odds),
                confidence=0.85
            )
        
        # Top pair - call smaller bets, fold to big
        if hand_strength == HandStrength.TOP_PAIR:
            if bet_ratio <= 0.66:
                return Decision(
                    action=Action.CALL,
                    amount=state.facing_bet,
                    display=f"CALL ${state.facing_bet:.2f}",
                    explanation=f"Call the ${state.facing_bet:.0f}. Top pair beats most of what they're betting on the turn — but be ready to fold if the river brings a big bet.",
                    calculation=get_made_hand_ev(hand_strength, state.pot_size, state.facing_bet, pot_odds),
                    confidence=0.75
                )
            else:
                return Decision(
                    action=Action.FOLD,
                    amount=None,
                    display="FOLD",
                    explanation=_fold_text("An overbet this size means they have it. One pair isn't enough.", state),
                    calculation=get_made_hand_ev(hand_strength, state.pot_size, state.facing_bet, pot_odds),
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
                    explanation=f"Call the ${state.facing_bet:.0f}. You have {_draw_desc(hand_strength, state.street)} — one card left and the pot is giving you the right price. The math says call.",
                    calculation=f"Equity {equity*100:.0f}% >= {pot_odds*100:.0f}% pot odds",
                    confidence=0.80
                )
            else:
                return Decision(
                    action=Action.FOLD,
                    amount=None,
                    display="FOLD",
                    explanation=_fold_text(f"The price isn't right to chase {_hs(hand_strength, state.hand_strength_display)}.", state),
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
                    explanation="Call. Small bet gives you the odds to chase the gutshot.",
                    calculation=f"Equity {equity*100:.0f}% >= {pot_odds*100:.0f}% pot odds",
                    confidence=0.65
                )
            return Decision(
                action=Action.FOLD,
                amount=None,
                display="FOLD",
                explanation=_fold_text("Not getting the right price for a gutshot.", state),
                calculation=f"Need {pot_odds*100:.0f}% odds, only have ~{equity*100:.0f}%",
                confidence=0.80
            )
        
        # AUDIT FIX: Overcards on turn — call small bets (~12% equity, 6 outs)
        if hand_strength == HandStrength.OVERCARDS:
            if bet_ratio <= 0.33:
                return Decision(
                    action=Action.CALL,
                    amount=state.facing_bet,
                    display=f"CALL ${state.facing_bet:.2f}",
                    explanation=f"Call the ${state.facing_bet:.0f}. Two overcards with ~12% to pair up — the bet is small enough to take one more card.",
                    calculation=f"~12% equity vs {pot_odds*100:.0f}% pot odds",
                    confidence=0.52
                )
        
        # Middle pair — call small turn bets, fold large
        # AUDIT FIX 2: Threshold raised from 0.40 to 0.55
        # Routing sends bet_ratio > 0.50 here, so threshold must exceed 0.50 to work.
        # Middle pair has ~30-35% equity; pot odds at 55% = 26% → math supports the call.
        if hand_strength == HandStrength.MIDDLE_PAIR:
            if bet_ratio <= 0.55:
                return Decision(
                    action=Action.CALL,
                    amount=state.facing_bet,
                    display=f"CALL ${state.facing_bet:.2f}",
                    explanation=f"Call the ${state.facing_bet:.0f}. Middle pair at this price — worth one more card to see if you improve.",
                    calculation=get_made_hand_ev(hand_strength, state.pot_size, state.facing_bet, pot_odds),
                    confidence=0.60
                )
        
        # AUDIT FIX 1: Bottom pair — call small turn bets (was missing, fell to fold)
        if hand_strength == HandStrength.BOTTOM_PAIR:
            if bet_ratio <= 0.33:
                return Decision(
                    action=Action.CALL,
                    amount=state.facing_bet,
                    display=f"CALL ${state.facing_bet:.2f}",
                    explanation=f"Call the ${state.facing_bet:.0f}. Small bet — bottom pair has enough equity at this price to take one more card.",
                    calculation=get_made_hand_ev(hand_strength, state.pot_size, state.facing_bet, pot_odds),
                    confidence=0.55
                )
        
        # AUDIT FIX: Pot odds safety net — 15% floor (raised from no safety net)
        if pot_odds <= 0.15:
            return Decision(
                action=Action.CALL,
                amount=state.facing_bet,
                display=f"CALL ${state.facing_bet:.2f}",
                explanation=f"Call the ${state.facing_bet:.0f}. The bet is small relative to the pot — you only need {pot_odds*100:.0f}% equity and that's too cheap to fold.",
                calculation=f"Pot odds: {pot_odds*100:.1f}% — mandatory call at this price",
                confidence=0.78
            )
        
        # Fold weak hands
        return Decision(
            action=Action.FOLD,
            amount=None,
            display="FOLD",
            explanation=_fold_text(f"Not the right spot to continue with {_hs(hand_strength, state.hand_strength_display)}.", state),
            calculation=f"Need {pot_odds*100:.0f}% equity vs their range — fold",
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
                explanation=_coach(state, "raise_facing_bet", f"Raise with {_hs(hand_strength, state.hand_strength_display)} — make them pay.", amount=amount),
                calculation="Sized up against weaker opponent" if fish else "Standard raise sizing",
                confidence=0.90
            )
        
        # Top pair and better - call
        if hand_strength in [HandStrength.OVERPAIR, HandStrength.TOP_PAIR_TOP_KICKER, HandStrength.TOP_PAIR]:
            return Decision(
                action=Action.CALL,
                amount=state.facing_bet,
                display=f"CALL ${state.facing_bet:.2f}",
                explanation=f"Call the ${state.facing_bet:.0f}. Your {_hs_bare(hand_strength, state.hand_strength_display)} beats most of what they're betting here." if state.street == Street.RIVER else f"Call the ${state.facing_bet:.0f}. Your {_hs_bare(hand_strength, state.hand_strength_display)} beats most of what they're betting — reassess on the {'river' if state.street == Street.TURN else 'turn'}.",
                calculation=get_made_hand_ev(hand_strength, state.pot_size, state.facing_bet, pot_odds),
                confidence=0.85
            )
        
        # Middle pair - call small bets, fold to big
        if hand_strength == HandStrength.MIDDLE_PAIR:
            if bet_ratio <= 0.50:
                return Decision(
                    action=Action.CALL,
                    amount=state.facing_bet,
                    display=f"CALL ${state.facing_bet:.2f}",
                    explanation=f"Call the ${state.facing_bet:.0f}. Middle pair at a small bet — you beat bluffs and draws at this price." + (" Reassess on the next street." if state.street != Street.RIVER else " You're catching bluffs at this price."),
                    calculation=get_made_hand_ev(hand_strength, state.pot_size, state.facing_bet, pot_odds),
                    confidence=0.70
                )
            else:
                return Decision(
                    action=Action.FOLD,
                    amount=None,
                    display="FOLD",
                    explanation=_fold_text("The bet is too large for middle pair — you're probably behind.", state),
                    calculation=get_made_hand_ev(hand_strength, state.pot_size, state.facing_bet, pot_odds),
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
                        explanation=f"Call the ${state.facing_bet:.0f}. You have {_draw_desc(hand_strength, state.street)} — normally you'd raise, but this player won't fold. Just call and draw.",
                        calculation=f"Equity {equity*100:.0f}% — calling over raising vs this player",
                        confidence=0.80
                    )
                amount = calculate_check_raise_size(state.facing_bet)
                return Decision(
                    action=Action.RAISE,
                    amount=amount,
                    display=f"RAISE TO ${amount:.2f}",
                    explanation=f"You have {_draw_desc(hand_strength, state.street)} — raise to ${amount:.0f} as a semi-bluff. You either take the pot now or you're drawing with strong equity if called.",
                    calculation=f"{equity*100:.0f}% equity + fold equity",
                    confidence=0.80
                )
            elif equity >= pot_odds:
                return Decision(
                    action=Action.CALL,
                    amount=state.facing_bet,
                    display=f"CALL ${state.facing_bet:.2f}",
                    explanation=f"Call the ${state.facing_bet:.0f}. You have {_draw_desc(hand_strength, state.street)} and you need {pot_odds*100:.0f}% equity to call — you have it. The math says call.",
                    calculation=f"Equity {equity*100:.0f}% >= {pot_odds*100:.0f}% pot odds",
                    confidence=0.80
                )
        
        # FIX 3.3: Gutshot — call small bets on flop (implied odds), fold otherwise
        if hand_strength == HandStrength.GUTSHOT:
            equity = get_draw_equity(hand_strength, state.street)
            # On flop, implied odds boost effective equity by ~50% (hitting pays off big)
            implied_equity = equity * 1.5 if state.street == Street.FLOP else equity
            if state.street == Street.FLOP and implied_equity >= pot_odds and bet_ratio <= 0.40:
                return Decision(
                    action=Action.CALL,
                    amount=state.facing_bet,
                    display=f"CALL ${state.facing_bet:.2f}",
                    explanation=f"Call the ${state.facing_bet:.0f}. You have a gutshot (4 outs, ~{equity*100:.0f}% to hit) but the implied odds make it worth it — if you hit, you'll win a big pot.",
                    calculation=f"~{equity*100:.0f}% equity + implied odds vs {pot_odds*100:.0f}% pot odds",
                    confidence=0.62
                )
            elif state.street == Street.TURN and equity >= pot_odds and bet_ratio <= 0.25:
                return Decision(
                    action=Action.CALL,
                    amount=state.facing_bet,
                    display=f"CALL ${state.facing_bet:.2f}",
                    explanation=f"Call the ${state.facing_bet:.0f}. Gutshot with 4 outs (~{equity*100:.0f}%) — the bet is small enough to take one more card.",
                    calculation=f"Equity {equity*100:.0f}% vs {pot_odds*100:.0f}% pot odds",
                    confidence=0.60
                )
            return Decision(
                action=Action.FOLD,
                amount=None,
                display="FOLD",
                explanation=_fold_text("Not getting the right price for a gutshot.", state),
                calculation=f"Need {pot_odds*100:.0f}% odds, only have ~{equity*100:.0f}%",
                confidence=0.80
            )
        
        # Bottom pair — call small bets
        # AUDIT FIX 1: Expanded from flop-only to all streets (turn/river fell to fold)
        if hand_strength == HandStrength.BOTTOM_PAIR:
            if state.street == Street.FLOP and bet_ratio <= 0.40:
                return Decision(
                    action=Action.CALL,
                    amount=state.facing_bet,
                    display=f"CALL ${state.facing_bet:.2f}",
                    explanation=f"Call the ${state.facing_bet:.0f}. Bottom pair is weak, but the bet is small enough ({bet_ratio*100:.0f}% pot) to take one more card. Fold to aggression on the turn.",
                    calculation=f"Small bet ({bet_ratio*100:.0f}% pot) — worth one card",
                    confidence=0.60
                )
            elif state.street in [Street.TURN, Street.RIVER] and bet_ratio <= 0.33:
                return Decision(
                    action=Action.CALL,
                    amount=state.facing_bet,
                    display=f"CALL ${state.facing_bet:.2f}",
                    explanation=f"Call the ${state.facing_bet:.0f}. Small bet — bottom pair has enough equity at this price to look them up.",
                    calculation=get_made_hand_ev(hand_strength, state.pot_size, state.facing_bet, pot_odds),
                    confidence=0.55
                )
        
        # Overcards — call small bets (6 outs: ~24% flop, ~12% turn)
        # AUDIT FIX: Was flop-only, now handles turn too
        if hand_strength == HandStrength.OVERCARDS:
            if state.street == Street.FLOP and bet_ratio <= 0.40:
                return Decision(
                    action=Action.CALL,
                    amount=state.facing_bet,
                    display=f"CALL ${state.facing_bet:.2f}",
                    explanation=f"Call the ${state.facing_bet:.0f}. You have two overcards (~24% to pair up) and the bet is small enough to take a card. If you hit top pair, you'll likely have the best hand.",
                    calculation=f"~24% to pair up vs {pot_odds*100:.0f}% pot odds",
                    confidence=0.58
                )
            elif state.street == Street.TURN and bet_ratio <= 0.33:
                return Decision(
                    action=Action.CALL,
                    amount=state.facing_bet,
                    display=f"CALL ${state.facing_bet:.2f}",
                    explanation=f"Call the ${state.facing_bet:.0f}. Two overcards with ~12% to pair up on the river — the bet is small enough to take one more card.",
                    calculation=f"~12% to pair up vs {pot_odds*100:.0f}% pot odds",
                    confidence=0.52
                )
        
        # Pot odds safety net — if the bet is small relative to the pot, call with anything
        # AUDIT FIX: Raised from 10% to 15% to close the gap between safety net and hand-specific thresholds
        if pot_odds <= 0.15:
            return Decision(
                action=Action.CALL,
                amount=state.facing_bet,
                display=f"CALL ${state.facing_bet:.2f}",
                explanation=f"Call the ${state.facing_bet:.0f}. The bet is small relative to the pot — you only need {pot_odds*100:.0f}% equity and that's too cheap to fold.",
                calculation=f"Pot odds: {pot_odds*100:.1f}% — mandatory call at this price",
                confidence=0.78
            )
        
        # Fold air and weak hands
        return Decision(
            action=Action.FOLD,
            amount=None,
            display="FOLD",
            explanation=_fold_text("You don't have a hand worth continuing with here.", state) if hand_strength == HandStrength.AIR
                else _fold_text(f"{_hs(hand_strength, state.hand_strength_display).capitalize()} can't continue here.", state),
            calculation=f"Pot odds need {pot_odds*100:.0f}% — not enough equity",
            confidence=0.85
        )
    
    # ── FIX 3.4: FACING DONK BET ──
    def _facing_donk_bet(self, state: GameState) -> Decision:
        """
        Facing a donk bet (villain leads into preflop aggressor on flop).
        At low stakes, donk bets are heavily value-weighted — fish love to
        lead out with top pair. Adjust accordingly.
        """
        hand_strength = state.hand_strength
        fish = _is_fish(state)
        pot_odds = calculate_pot_odds(state.pot_size, state.facing_bet)
        bet_ratio = state.facing_bet / state.pot_size if state.pot_size > 0 else 0.5
        
        # Monsters: raise for value — they're telling us they have a hand
        if hand_strength in [HandStrength.NUTS, HandStrength.MONSTER, HandStrength.TWO_PAIR]:
            amount = calculate_check_raise_size(state.facing_bet, fish)
            return Decision(
                action=Action.RAISE,
                amount=amount,
                display=f"RAISE TO ${amount:.2f}",
                explanation=_coach(state, "raise_facing_donk", f"Raise — your {_hs_bare(hand_strength, state.hand_strength_display)} crushes their lead.", amount=amount),
                calculation=get_made_hand_ev(hand_strength, state.pot_size, state.facing_bet, pot_odds),
                confidence=0.90
            )
        
        # Overpair / TPTK / TP: call — they probably have a piece but we're ahead
        if hand_strength in [HandStrength.OVERPAIR, HandStrength.TOP_PAIR_TOP_KICKER, HandStrength.TOP_PAIR]:
            return Decision(
                action=Action.CALL,
                amount=state.facing_bet,
                display=f"CALL ${state.facing_bet:.2f}",
                explanation=f"Call. Donk bets at this level usually mean a piece of the board. Your {_hs_bare(hand_strength, state.hand_strength_display)} is likely ahead.",
                calculation=get_made_hand_ev(hand_strength, state.pot_size, state.facing_bet, pot_odds),
                confidence=0.82
            )
        
        # Draws: call if getting odds
        if hand_strength in [HandStrength.COMBO_DRAW, HandStrength.FLUSH_DRAW, HandStrength.OESD]:
            equity = get_draw_equity(hand_strength, state.street)
            if equity >= pot_odds:
                return Decision(
                    action=Action.CALL,
                    amount=state.facing_bet,
                    display=f"CALL ${state.facing_bet:.2f}",
                    explanation=f"Call. Your {_hs_bare(hand_strength, state.hand_strength_display)} has a good shot at improving against their likely made hand.",
                    calculation=f"Equity {equity*100:.0f}% >= {pot_odds*100:.0f}% pot odds",
                    confidence=0.78
                )
        
        # Gutshot: call small donk bets
        if hand_strength == HandStrength.GUTSHOT:
            equity = get_draw_equity(hand_strength, state.street)
            if equity >= pot_odds and bet_ratio <= 0.33:
                return Decision(
                    action=Action.CALL,
                    amount=state.facing_bet,
                    display=f"CALL ${state.facing_bet:.2f}",
                    explanation=f"Call the ${state.facing_bet:.0f}. Their small donk bet gives you the right price for your gutshot — 4 outs with implied odds if you hit.",
                    calculation=f"Equity {equity*100:.0f}% >= {pot_odds*100:.0f}% pot odds",
                    confidence=0.62
                )
        
        # Middle pair: call small bets only
        if hand_strength == HandStrength.MIDDLE_PAIR and bet_ratio <= 0.40:
            return Decision(
                action=Action.CALL,
                amount=state.facing_bet,
                display=f"CALL ${state.facing_bet:.2f}",
                explanation=f"Call the ${state.facing_bet:.0f}. Their donk bet usually means a weak hand at these stakes — your {_hs_bare(hand_strength, state.hand_strength_display)} has enough equity to take one more card.",
                calculation="Donk bet — adjust for value-heavy range",
                confidence=0.60
            )
        
        # AUDIT FIX 7: Pot odds safety net for donk bets (was missing)
        if pot_odds <= 0.15:
            return Decision(
                action=Action.CALL,
                amount=state.facing_bet,
                display=f"CALL ${state.facing_bet:.2f}",
                explanation=f"Call the ${state.facing_bet:.0f}. The donk bet is small relative to the pot — too cheap to fold.",
                calculation=f"Pot odds: {pot_odds*100:.1f}% — mandatory call at this price",
                confidence=0.75
            )
        
        # Everything else: fold
        return Decision(
            action=Action.FOLD,
            amount=None,
            display="FOLD",
            explanation="Fold. Their donk bet likely means a made hand, and you don't have anything to fight back with." if hand_strength == HandStrength.AIR
                else f"Fold. Their donk bet likely means a made hand, and your {_hs_bare(hand_strength, state.hand_strength_display)} isn't strong enough.",
            calculation="Donk bet — adjust for value-heavy range",
            confidence=0.82
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
                    explanation=_coach(state, "all_in_commit", f"All-in. Pot-committed with {_hs(hand_strength, state.hand_strength_display)} — go with it.", spr=state.spr),
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
                explanation=_coach(state, "raise_facing_checkraise", f"Re-raise — they check-raised into your {_hs_bare(hand_strength, state.hand_strength_display)}.", amount=amount),
                calculation=f"{'3×' if fish else '2.5×'} their raise = ${amount:.2f}",
                confidence=0.90
            )
        
        # ── OVERBET CHECK-RAISE (>2x pot) ──
        # A massive check-raise is almost always the nuts or a huge draw.
        # At $1/$2-$5/$10, overbet check-raises are 90%+ value (trips, sets, straights).
        # Only continue with real two pair+. Everything else folds.
        cr_bet_ratio = state.facing_bet / state.pot_size if state.pot_size > 0 else 1.0
        if cr_bet_ratio > 2.0:
            if hand_strength == HandStrength.TWO_PAIR:
                return Decision(
                    action=Action.CALL,
                    amount=state.facing_bet,
                    display=f"CALL ${state.facing_bet:.2f}",
                    explanation=f"Call. The check-raise is massive but two pair is strong enough to continue — be ready to fold if the aggression continues.",
                    calculation=f"Overbet check-raise ({cr_bet_ratio:.0f}× pot) — two pair calls once",
                    confidence=0.65
                )
            # Overpair, TPTK, and below → fold to overbet check-raise
            return Decision(
                action=Action.FOLD,
                amount=None,
                display="FOLD",
                explanation=_fold_text(f"A check-raise this size means a monster — {_hs(hand_strength, state.hand_strength_display)} can't call.", state),
                calculation=f"Overbet check-raise ({cr_bet_ratio:.0f}× pot) — only monsters continue",
                confidence=0.88
            )
        
        # AUDIT FIX 6a: Two pair — call (was missing entirely, fell to catch-all fold)
        if hand_strength == HandStrength.TWO_PAIR:
            return Decision(
                action=Action.CALL,
                amount=state.facing_bet,
                display=f"CALL ${state.facing_bet:.2f}",
                explanation=f"Call. Two pair is strong enough to continue against a check-raise — reassess on the next street.",
                calculation="Two pair vs check-raise — call and reassess",
                confidence=0.82
            )
        
        # Overpair/TPTK - call but proceed with caution
        if hand_strength in [HandStrength.OVERPAIR, HandStrength.TOP_PAIR_TOP_KICKER]:
            return Decision(
                action=Action.CALL,
                amount=state.facing_bet,
                display=f"CALL ${state.facing_bet:.2f}",
                explanation=f"Call. Respect the check-raise — proceed carefully with {_hs(hand_strength, state.hand_strength_display)}.",
                calculation="Strong enough to call the check-raise",
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
                    calculation="Fish overvalue — top pair is good enough to call",
                    confidence=0.68
                )
            return Decision(
                action=Action.FOLD,
                amount=None,
                display="FOLD",
                explanation=_fold_text("Check-raises mean real strength — top pair isn't enough.", state),
                calculation="Check-raises are heavily value-weighted — fold",
                confidence=0.80
            )
        
        # Strong draws - call if odds
        if hand_strength in [HandStrength.COMBO_DRAW, HandStrength.FLUSH_DRAW, HandStrength.OESD]:
            equity = get_draw_equity(hand_strength, state.street)
            pot_odds = calculate_pot_odds(state.pot_size, state.facing_bet)
            if equity >= pot_odds:
                return Decision(
                    action=Action.CALL,
                    amount=state.facing_bet,
                    display=f"CALL ${state.facing_bet:.2f}",
                    explanation=f"Call the ${state.facing_bet:.0f}. Their check-raise is strong, but your {_draw_desc(hand_strength, state.street)} gives you enough equity at this price.",
                    calculation=f"Equity {equity*100:.0f}% >= {pot_odds*100:.0f}% pot odds",
                    confidence=0.75
                )
        
        # AUDIT FIX 6b: Pot odds safety net for check-raises
        pot_odds_cr = calculate_pot_odds(state.pot_size, state.facing_bet)
        if pot_odds_cr <= 0.15:
            return Decision(
                action=Action.CALL,
                amount=state.facing_bet,
                display=f"CALL ${state.facing_bet:.2f}",
                explanation=f"Call the ${state.facing_bet:.0f}. The check-raise is small relative to the pot — you only need {pot_odds_cr*100:.0f}% equity and that's too cheap to fold.",
                calculation=f"Pot odds: {pot_odds_cr*100:.1f}% — mandatory call at this price",
                confidence=0.75
            )
        
        # Fold everything else
        return Decision(
            action=Action.FOLD,
            amount=None,
            display="FOLD",
            explanation=_fold_text("The check-raise shows real strength — let this one go.", state),
            calculation="Check-raise = real strength — save your chips",
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
    is_nuts: bool = False,
) -> GameState:
    """
    Helper to create GameState from simple inputs.
    
    This is the main interface for the UI to create game states.
    """
    
    stakes_info = STAKES_CONFIG.get(stakes, {"sb": 1.0, "bb": 2.0})
    bb_size = stakes_info["bb"]
    sb_size = stakes_info["sb"]
    
    # ── INPUT SANITIZATION — never crash on bad UI data ──
    pot_size = max(0, pot_size or 0)
    facing_bet = max(0, facing_bet or 0)
    our_stack = max(0, our_stack or 0)
    villain_stack = max(0, villain_stack or 0)
    
    effective_stack = min(our_stack, villain_stack)
    
    # Parse enums — defensive, never crash on bad input
    try:
        pos = Position[our_position.upper()]
    except (KeyError, AttributeError):
        pos = Position.BTN
    
    villain_pos = None
    if villain_position and villain_position not in ('', 'none', 'None', 'null', 'unknown'):
        try:
            villain_pos = Position[villain_position.upper()]
        except (KeyError, AttributeError):
            villain_pos = None
    
    try:
        st = Street[street.upper()]
    except (KeyError, AttributeError):
        st = Street.PREFLOP
    
    # Save original hand type for display before mapping to engine enum
    hs_display = (hand_strength or "playable").lower().replace(" ", "_")
    
    hs_key = (hand_strength or "playable").upper().replace(" ", "_")
    # Map specific hand types to engine enums (keeps decision logic unchanged)
    _HS_ENUM_MAP = {
        "TPTK": "TOP_PAIR_TOP_KICKER",
        "NOTHING": "AIR", "HIGH_CARD": "AIR",
        "UNDERPAIR": "BOTTOM_PAIR",
        # Monster subtypes → MONSTER for engine decisions
        "SET": "MONSTER", "TRIPS": "MONSTER", "QUADS": "MONSTER",
        "FULL_HOUSE": "MONSTER", "FLUSH": "MONSTER", "STRAIGHT": "MONSTER",
        "ROYAL_FLUSH": "MONSTER", "STRAIGHT_FLUSH": "MONSTER",
    }
    hs_key = _HS_ENUM_MAP.get(hs_key, hs_key)
    try:
        hs = HandStrength[hs_key]
    except (KeyError, AttributeError):
        hs = HandStrength.PLAYABLE
    
    # When the frontend detects the actual nuts, upgrade MONSTER → NUTS
    # so the engine uses the more aggressive NUTS decision path
    if is_nuts and hs == HandStrength.MONSTER:
        hs = HandStrength.NUTS
    
    try:
        bt = BoardTexture[board_texture.upper()] if board_texture else None
    except (KeyError, AttributeError):
        bt = None
    
    af_raw = (action_facing or "none").upper().replace("-", "_")
    # Explicit mapping for all known action_facing values (safe, no global string replace)
    af_map = {
        "CHECKED": "NONE", "CHECK": "NONE", "NONE": "NONE", "CALL": "NONE",
        "OPEN": "RAISE", "LIMP": "LIMP",
        "BET": "BET", "RAISE": "RAISE",
        "3BET": "THREE_BET", "3_BET": "THREE_BET", "THREE_BET": "THREE_BET",
        "4BET": "FOUR_BET", "4_BET": "FOUR_BET", "FOUR_BET": "FOUR_BET",
        "CHECK_RAISE": "CHECK_RAISE",
    }
    af_raw = af_map.get(af_raw, af_raw)
    try:
        af = ActionFacing[af_raw]
    except (KeyError, AttributeError):
        af = ActionFacing.NONE
    
    # ── CONTRADICTORY STATE GUARD ──
    # If facing_bet is 0 but action says we're facing a bet/raise, override to NONE
    # Prevents degenerate CALL $0 or stuck states from bad UI data
    if facing_bet <= 0 and af in (ActionFacing.BET, ActionFacing.RAISE,
                                   ActionFacing.CHECK_RAISE, ActionFacing.THREE_BET,
                                   ActionFacing.FOUR_BET):
        af = ActionFacing.NONE
    
    try:
        vt = VillainType[villain_type.upper()] if villain_type else VillainType.UNKNOWN
    except (KeyError, AttributeError):
        vt = VillainType.UNKNOWN
    
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
        hand_strength_display=hs_display,
        is_nuts=is_nuts,
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
    is_nuts: bool = False,
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
        is_nuts=is_nuts,
    )
    
    # ── Stack guard: can't play with no chips ──
    if state.our_stack <= 0:
        if state.facing_bet > 0:
            return Decision(
                action=Action.FOLD,
                amount=None,
                display="FOLD",
                explanation="Fold. You're out of chips — end the session or re-buy.",
                calculation="No chips remaining",
                confidence=1.0,
            )
        return Decision(
            action=Action.CHECK,
            amount=None,
            display="CHECK",
            explanation="Check. You're out of chips — end the session or re-buy.",
            calculation="No chips remaining",
            confidence=1.0,
        )
    
    engine = get_engine()
    decision = engine.get_decision(state)
    
    # ── FIX 3.1: ROUND BETS TO CLEAN AMOUNTS ──
    if decision.amount is not None and decision.amount > 0:
        rounded_amt = round_bet(decision.amount, stakes)
        if rounded_amt != decision.amount:
            action_word = "BET" if decision.action == Action.BET else \
                         "RAISE TO" if decision.action == Action.RAISE else \
                         "CALL" if decision.action == Action.CALL else \
                         "ALL-IN" if decision.action == Action.ALL_IN else ""
            decision = Decision(
                action=decision.action,
                amount=rounded_amt,
                display=f"{action_word} ${rounded_amt:.0f}" if action_word else decision.display,
                explanation=decision.explanation,
                calculation=decision.calculation,
                confidence=decision.confidence,
                bluff_context=decision.bluff_context,
                alternative=decision.alternative,
            )
    
    # ── MINIMUM BET FLOOR: Never bet less than 1 BB ──
    # Can happen with tiny pot sizes (e.g. $8 pot at $5/$10 → 33% = $2.64)
    # AUDIT FIX: Also catches zero-amount bets (e.g. 33% of $0 pot)
    if decision.action in (Action.BET, Action.RAISE) and decision.amount is not None:
        if decision.amount <= 0:
            # Can't bet $0 — convert to CHECK
            decision = Decision(
                action=Action.CHECK,
                amount=None,
                display="CHECK",
                explanation=decision.explanation,
                calculation=decision.calculation,
                confidence=decision.confidence,
            )
        elif decision.amount < state.bb_size:
            floored_amt = round_bet(state.bb_size, stakes)
            action_word = "BET" if decision.action == Action.BET else "RAISE TO"
            # Recalculate pot percentage for explanation
            pct = floored_amt / state.pot_size if state.pot_size > 0 else 1.0
            decision = Decision(
                action=decision.action,
                amount=floored_amt,
                display=f"{action_word} ${floored_amt:.0f}",
                explanation=decision.explanation,
                calculation=decision.calculation,
                confidence=decision.confidence,
                bluff_context=decision.bluff_context,
                alternative=decision.alternative,
            )
    
    # ── Cap bet/raise amounts to remaining stack ──
    # No bet can ever exceed what the player actually has
    if decision.amount is not None and decision.amount > 0:
        remaining = max(0, state.our_stack)
        if remaining <= 0:
            # Player has no chips — can only check or fold
            if decision.action in (Action.BET, Action.RAISE, Action.ALL_IN):
                decision = Decision(
                    action=Action.CHECK,
                    amount=None,
                    display="CHECK",
                    explanation="Check. You're out of chips — end the session or re-buy.",
                    calculation="No chips remaining",
                    confidence=1.0,
                )
        elif decision.amount > remaining:
            # Bet exceeds stack — convert to ALL-IN
            decision = Decision(
                action=Action.ALL_IN,
                amount=round(remaining, 2),
                display=f"ALL-IN ${remaining:.0f}",
                explanation=decision.explanation,
                calculation=f"Stack: ${remaining:.0f} — all-in is the maximum you can bet",
                confidence=decision.confidence,
            )
        elif decision.amount >= remaining * 0.9:
            # Bet is ≥90% of stack — cleaner to just shove
            decision = Decision(
                action=Action.ALL_IN,
                amount=round(remaining, 2),
                display=f"ALL-IN ${remaining:.0f}",
                explanation=decision.explanation,
                calculation=f"Stack: ${remaining:.0f} — shove is cleaner than a near-stack bet",
                confidence=decision.confidence,
            )
    
    return decision