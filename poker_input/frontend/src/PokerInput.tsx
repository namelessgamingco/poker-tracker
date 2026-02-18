import React, { useEffect, useState, useCallback, useRef } from "react"
import ReactDOM from "react-dom/client"
import {
  Streamlit,
  withStreamlitConnection,
  ComponentProps,
} from "streamlit-component-lib"

// =============================================================================
// TYPES
// =============================================================================

type InputStep =
  | "position"
  | "card1_rank"
  | "card1_suit"
  | "card2_rank"
  | "card2_suit"
  | "street"
  | "action"
  | "amount"
  | "limper_count"
  | "board_rank"
  | "board_suit"
  | "pot_size"
  | "board_texture"
  | "hand_strength"
  | "villain_type"
  | "ready"
  | "showing_decision"
  | "outcome_select"


type Street = "preflop" | "flop" | "turn" | "river"

interface CardData {
  rank: string
  suit: string
}

interface GameState {
  position: string | null
  card1: CardData | null
  card2: CardData | null
  street: Street
  action_facing: string
  facing_bet: number
  num_limpers: number
  board_cards: (CardData | null)[]
  pot_size: number
  board_texture: string | null
  hand_strength: string | null
  villain_type: string
  we_are_aggressor: boolean
}

interface BluffContext {
  spot_type: string          // 'river_barrel', 'river_probe', 'dry_board_cbet'
  delivery: string           // 'choice' or 'auto'
  recommended_action: string // 'BET' or 'CHECK'
  bet_amount: number
  pot_size: number
  ev_of_bet: number
  ev_of_check: number
  break_even_pct: number
  estimated_fold_pct: number
  explanation_bet: string
  explanation_check: string
}

interface DecisionResult {
  action: string
  amount: number | null
  display: string
  explanation: string
  calculation: string | null
  confidence: number
  bluff_context?: BluffContext | null
  alternative?: DecisionResult | null
}

// =============================================================================
// CONSTANTS
// =============================================================================

const POSITIONS = [
  { id: "UTG", label: "UTG", fullName: "Under the Gun", desc: "First to act · tightest range", key: "1", order: 1 },
  { id: "HJ", label: "HJ", fullName: "Hijack", desc: "Middle position · fairly tight", key: "2", order: 2 },
  { id: "CO", label: "CO", fullName: "Cutoff", desc: "One before button · opens wider", key: "3", order: 3 },
  { id: "BTN", label: "BTN", fullName: "Button", desc: "Best position · widest range", key: "4", order: 4 },
  { id: "SB", label: "SB", fullName: "Small Blind", desc: "Half blind posted · first postflop", key: "5", order: 5 },
  { id: "BB", label: "BB", fullName: "Big Blind", desc: "Full blind posted · defends wide", key: "6", order: 6 },
]
const RANKS = [
  { rank: "A", display: "A", fullName: "Ace", isFace: true },
  { rank: "K", display: "K", fullName: "King", isFace: true },
  { rank: "Q", display: "Q", fullName: "Queen", isFace: true },
  { rank: "J", display: "J", fullName: "Jack", isFace: true },
  { rank: "T", display: "10", fullName: "Ten", isFace: true },
  { rank: "9", display: "9", fullName: null, isFace: false },
  { rank: "8", display: "8", fullName: null, isFace: false },
  { rank: "7", display: "7", fullName: null, isFace: false },
  { rank: "6", display: "6", fullName: null, isFace: false },
  { rank: "5", display: "5", fullName: null, isFace: false },
  { rank: "4", display: "4", fullName: null, isFace: false },
  { rank: "3", display: "3", fullName: null, isFace: false },
  { rank: "2", display: "2", fullName: null, isFace: false },
]
const SUITS = [
  { key: "h", symbol: "♥", name: "Hearts", color: "#FF4B5C" },
  { key: "d", symbol: "♦", name: "Diamonds", color: "#4BA3FF" },
  { key: "c", symbol: "♣", name: "Clubs", color: "#50D890" },
  { key: "s", symbol: "♠", name: "Spades", color: "#C8C8D0" },
]

// Initial preflop actions — what can happen before your first action
const PREFLOP_ACTIONS_INITIAL = [
  { key: "f", id: "none", label: "Nobody Bet Yet", desc: "Folded to you, or only blinds in", needsAmount: false },
  { key: "l", id: "limp", label: "Limper(s)", desc: "One or more players called the blind", needsAmount: false, needsCount: true },
  { key: "r", id: "raise", label: "Facing a Raise", desc: "Someone raised before you", needsAmount: true, amountLabel: "Their raise to $" },
]

// All preflop actions including escalations (for engine mapping)
const PREFLOP_ACTIONS_ALL = [
  ...PREFLOP_ACTIONS_INITIAL,
  { key: "e", id: "3bet", label: "Facing a Re-Raise", desc: "I raised, they re-raised", needsAmount: true, amountLabel: "Their 3-bet to $" },
  { key: "b", id: "4bet", label: "Facing a 4-Bet", desc: "I 3-bet, they raised again", needsAmount: true, amountLabel: "Their 4-bet to $" },
]

// Initial postflop actions — what can happen before your first action on this street
const POSTFLOP_ACTIONS_INITIAL = [
  { key: "f", id: "none", label: "Checked to Me", desc: "No bet yet on this street", needsAmount: false },
  { key: "r", id: "bet", label: "Facing a Bet", desc: "Opponent bet — enter their amount", needsAmount: true, amountLabel: "Their bet $" },
]

// All postflop actions including escalations
const POSTFLOP_ACTIONS_ALL = [
  ...POSTFLOP_ACTIONS_INITIAL,
  { key: "x", id: "check_raise", label: "Facing a Raise", desc: "I bet, they raised", needsAmount: true, amountLabel: "Their raise to $" },
]

const BOARD_TEXTURES = [
  { id: "dry", label: "Dry", desc: "Rainbow, unconnected" },
  { id: "semi_wet", label: "Semi-Wet", desc: "Some draws" },
  { id: "wet", label: "Wet", desc: "Connected, flush possible" },
  { id: "paired", label: "Paired", desc: "Board has a pair" },
]

const HAND_STRENGTHS = [
  { id: "nuts", label: "Nuts", cat: "monster" },
  { id: "monster", label: "Monster", cat: "monster" },
  { id: "two_pair", label: "Two Pair", cat: "strong" },
  { id: "overpair", label: "Overpair", cat: "strong" },
  { id: "tptk", label: "Top Pair Top Kicker", cat: "strong" },
  { id: "top_pair", label: "Top Pair", cat: "medium" },
  { id: "middle_pair", label: "Middle Pair", cat: "medium" },
  { id: "bottom_pair", label: "Bottom Pair", cat: "weak" },
  { id: "combo_draw", label: "Combo Draw", cat: "draw" },
  { id: "flush_draw", label: "Flush Draw", cat: "draw" },
  { id: "oesd", label: "Open-Ended Straight", cat: "draw" },
  { id: "gutshot", label: "Gutshot", cat: "draw" },
  { id: "overcards", label: "Overcards", cat: "weak" },
  { id: "air", label: "Air / Nothing", cat: "weak" },
]

const VILLAIN_TYPES = [
  { id: "unknown", label: "Not Sure", desc: "Default — balanced strategy", key: "1" },
  { id: "fish", label: "Weak Player", desc: "Calls too much · bet bigger for value", key: "2" },
  { id: "reg", label: "Good Player", desc: "Plays solid · tighter strategy", key: "3" },
]

// =============================================================================
// TWO-TABLE MODE CONSTANTS (NEW)
// =============================================================================

const FRESH_GAME_STATE: GameState = {
  position: null,
  card1: null,
  card2: null,
  street: "preflop",
  action_facing: "none",
  facing_bet: 0,
  num_limpers: 0,
  board_cards: [null, null, null, null, null],
  pot_size: 0,
  board_texture: null,
  hand_strength: null,
  villain_type: "unknown",
  we_are_aggressor: false,
}

const TABLE_COLORS = {
  1: {
    accent: "#4BA3FF",
    name: "TABLE 1",
    borderActive: "2px solid #4BA3FF",
    borderInactive: "1px solid rgba(75, 163, 255, 0.2)",
    bgActive: "rgba(75, 163, 255, 0.05)",
  },
  2: {
    accent: "#FFB300",
    name: "TABLE 2",
    borderActive: "2px solid #FFB300",
    borderInactive: "1px solid rgba(255, 179, 0, 0.2)",
    bgActive: "rgba(255, 179, 0, 0.05)",
  },
}

// =============================================================================
// HELPER FUNCTIONS
// =============================================================================

function cardToString(card: CardData | null): string {
  if (!card) return ""
  return card.rank + card.suit
}

function parseCard(str: string | null | undefined): CardData | null {
  if (!str || str.length < 2) return null
  return { rank: str[0].toUpperCase(), suit: str[1].toLowerCase() }
}

function parseBoard(boardStr: string | null | undefined): (CardData | null)[] {
  const result: (CardData | null)[] = [null, null, null, null, null]
  if (!boardStr) return result
  for (let i = 0; i < boardStr.length - 1; i += 2) {
    const idx = i / 2
    if (idx < 5) {
      result[idx] = { rank: boardStr[i].toUpperCase(), suit: boardStr[i + 1].toLowerCase() }
    }
  }
  return result
}

// Hand strength display names for human-readable explanations
const HAND_STRENGTH_DISPLAY: Record<string, string> = {
  "tptk": "Top Pair, Top Kicker",
  "top_pair_top_kicker": "Top Pair, Top Kicker",
  "top_pair": "Top Pair",
  "overpair": "Overpair",
  "two_pair": "Two Pair",
  "monster": "Very Strong Hand",
  "nuts": "The Nuts",
  "middle_pair": "Middle Pair",
  "bottom_pair": "Bottom Pair",
  "combo_draw": "Combo Draw",
  "flush_draw": "Flush Draw",
  "oesd": "Straight Draw",
  "gutshot": "Gutshot Draw",
  "overcards": "Overcards",
  "air": "Nothing",
  "premium": "Premium Hand",
  "strong": "Strong Hand",
  "playable": "Playable Hand",
  "marginal": "Marginal Hand",
  "trash": "Weak Hand",
}

function humanizeExplanation(text: string): string {
  if (!text) return ""
  let result = text
  // Replace shorthand hand strengths with readable names
  for (const [key, val] of Object.entries(HAND_STRENGTH_DISPLAY)) {
    const regex = new RegExp(`\\b${key}\\b`, "gi")
    result = result.replace(regex, val)
  }
  // Capitalize first letter
  return result.charAt(0).toUpperCase() + result.slice(1)
}

function roundBetDisplay(display: string): string {
  // Round dollar amounts to whole numbers: "BET $4.62" → "BET $5"
  return display.replace(/\$(\d+\.\d+)/g, (_, amount) => {
    return "$" + Math.round(parseFloat(amount))
  })
}

function roundCalculation(calc: string): string {
  if (!calc) return ""
  // Round amounts in calculation: "33% pot = $4.62" → "33% pot = $5"
  return calc.replace(/\$(\d+\.\d+)/g, (_, amount) => {
    return "$" + Math.round(parseFloat(amount))
  })
}

function suitSymbol(suit: string): string {
  const s = SUITS.find((x) => x.key === suit)
  return s ? s.symbol : suit
}

function suitColor(suit: string): string {
  const s = SUITS.find((x) => x.key === suit)
  return s ? s.color : "#fff"
}

function isCardUsed(
  rank: string,
  suit: string,
  card1: CardData | null,
  card2: CardData | null,
  boardCards: (CardData | null)[]
): boolean {
  const check = (c: CardData | null) => c && c.rank === rank && c.suit === suit
  if (check(card1) || check(card2)) return true
  return boardCards.some((c) => check(c))
}

function requiredBoardCards(street: Street): number {
  if (street === "flop") return 3
  if (street === "turn") return 4
  if (street === "river") return 5
  return 0
}

// =============================================================================
// TWO-TABLE MODE HELPER (NEW)
// =============================================================================

function getStepDescription(step: InputStep): string {
  switch (step) {
    case "position": return "Selecting position..."
    case "card1_rank":
    case "card1_suit": return "Entering card 1..."
    case "card2_rank":
    case "card2_suit": return "Entering card 2..."
    case "action": return "Selecting action..."
    case "amount": return "Entering amount..."
    case "limper_count": return "Entering limper count..."
    case "board_rank":
    case "board_suit": return "Entering board..."
    case "pot_size": return "Entering pot size..."
    case "board_texture": return "Selecting board texture..."
    case "hand_strength": return "Selecting hand strength..."
    case "villain_type": return "Selecting villain type..."
    case "ready": return "Calculating..."
    case "showing_decision": return ""
    case "outcome_select": return "Recording result..."
    default: return ""
  }
}

// =============================================================================
// AUTO-DETECTION: Board Texture & Hand Strength
// =============================================================================

const RANK_VALUES: Record<string, number> = {
  "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8,
  "9": 9, "T": 10, "J": 11, "Q": 12, "K": 13, "A": 14,
}

function detectBoardTexture(boardCards: (CardData | null)[]): string {
  const cards = boardCards.filter((c): c is CardData => c !== null)
  if (cards.length < 3) return "dry"

  const suits = cards.map((c) => c.suit)
  const ranks = cards.map((c) => RANK_VALUES[c.rank] || 0).sort((a, b) => a - b)

  // Paired board?
  const rankCounts = new Map<number, number>()
  ranks.forEach((r) => rankCounts.set(r, (rankCounts.get(r) || 0) + 1))
  const hasPair = [...rankCounts.values()].some((v) => v >= 2)
  if (hasPair) return "paired"

  // Suit analysis
  const suitCounts = new Map<string, number>()
  suits.forEach((s) => suitCounts.set(s, (suitCounts.get(s) || 0) + 1))
  const maxSameSuit = Math.max(...suitCounts.values())
  const isMonotone = maxSameSuit >= 3
  // For 5-card boards (river), 2 suited is trivially common — require 3+ for flush relevance
  // For 3-4 card boards (flop/turn), 2+ same suit means flush draws exist
  const flushDrawPossible = cards.length >= 5 ? maxSameSuit >= 3 : maxSameSuit >= 2

  // Monotone = always wet
  if (isMonotone) return "wet"

  // Connectedness: count adjacent (gap=1) and one-gap (gap=2) pairs
  const uniqueRanks = [...new Set(ranks)].sort((a, b) => a - b)
  let adjacentCount = 0
  let oneGapCount = 0
  for (let i = 0; i < uniqueRanks.length; i++) {
    for (let j = i + 1; j < uniqueRanks.length; j++) {
      const gap = uniqueRanks[j] - uniqueRanks[i]
      if (gap === 1) adjacentCount++
      else if (gap === 2) oneGapCount++
    }
  }
  // Ace-low connectivity — only adds to one-gap, never adjacent
  // (A-2 in poker context is a one-gap connection for wheel draws, not a strong adjacent)
  if (uniqueRanks.includes(14)) {
    const lowCards = uniqueRanks.filter((r) => r >= 2 && r <= 5)
    if (lowCards.length >= 2) {
      oneGapCount++
    }
  }

  const boardSpan = uniqueRanks[uniqueRanks.length - 1] - uniqueRanks[0]
  const straightRelevant = boardSpan <= 4

  // Check for a CONSECUTIVE RUN of 3+ cards (e.g. 7-8-9 or Q-J-T)
  // This is different from just having 2 adjacent pairs at different parts of the board
  let maxConsecutiveRun = 1
  let currentRun = 1
  for (let i = 1; i < uniqueRanks.length; i++) {
    if (uniqueRanks[i] - uniqueRanks[i - 1] === 1) {
      currentRun++
      maxConsecutiveRun = Math.max(maxConsecutiveRun, currentRun)
    } else {
      currentRun = 1
    }
  }

  // Wet: flush draw + adjacent connection, or 3+ consecutive cards in a run,
  // or multiple adjacent pairs in a tight span (like J-T-8-7: two adjacent pairs within 5 ranks)
  if (flushDrawPossible && adjacentCount >= 1 && straightRelevant) return "wet"
  if (maxConsecutiveRun >= 3) return "wet"
  // Multiple adjacent pairs within a 5-rank span = highly connected
  if (adjacentCount >= 2) {
    const span = uniqueRanks[uniqueRanks.length - 1] - uniqueRanks[0]
    if (span <= 5) return "wet"
  }

  // Semi-wet: flush draw possible (two-tone) OR meaningful connection
  if (flushDrawPossible) return "semi_wet"
  if (adjacentCount >= 1 && straightRelevant) return "semi_wet"
  // One-gap only counts as semi_wet if cards are in straight-relevant range (5+)
  const meaningfulOneGap = oneGapCount >= 1 && uniqueRanks.some((r) => r >= 5 && r <= 13 && 
    uniqueRanks.some((r2) => r2 !== r && Math.abs(r2 - r) === 2 && r2 >= 5))
  if (meaningfulOneGap) return "semi_wet"

  // Dry: rainbow and no connections
  return "dry"
}

function detectHandStrength(
  card1: CardData | null,
  card2: CardData | null,
  boardCards: (CardData | null)[]
): string {
  if (!card1 || !card2) return "air"
  const board = boardCards.filter((c): c is CardData => c !== null)
  if (board.length === 0) return "air" // preflop — engine uses classify_preflop_hand

  const holeRanks = [RANK_VALUES[card1.rank] || 0, RANK_VALUES[card2.rank] || 0].sort((a, b) => b - a)
  const holeSuits = [card1.suit, card2.suit]
  const boardRanks = board.map((c) => RANK_VALUES[c.rank] || 0).sort((a, b) => b - a)
  const boardSuits = board.map((c) => c.suit)
  const allRanks = [...holeRanks, ...boardRanks].sort((a, b) => b - a)
  const allSuits = [...holeSuits, ...boardSuits]
  const allCards = [card1, card2, ...board]

  // Count rank occurrences across all 5-7 cards
  const rankCounts = new Map<number, number>()
  allRanks.forEach((r) => rankCounts.set(r, (rankCounts.get(r) || 0) + 1))

  // Count suit occurrences
  const suitCounts = new Map<string, number>()
  allSuits.forEach((s) => suitCounts.set(s, (suitCounts.get(s) || 0) + 1))

  // Check if hole cards contribute to the hand (not just board)
  const holeInvolved = (rank: number) => holeRanks.includes(rank)

  // === MADE HANDS (check strongest first) ===

  // Four of a kind
  for (const [rank, count] of rankCounts) {
    if (count >= 4 && holeInvolved(rank)) return "monster"
  }

  // Full house: three of a kind + pair, with hole cards involved
  const trips: number[] = []
  const pairs: number[] = []
  for (const [rank, count] of rankCounts) {
    if (count >= 3) trips.push(rank)
    else if (count >= 2) pairs.push(rank)
  }
  if (trips.length > 0 && (pairs.length > 0 || trips.length > 1)) {
    if (trips.some((r) => holeInvolved(r)) || pairs.some((r) => holeInvolved(r))) {
      return "monster"
    }
  }

  // Flush: 5+ cards same suit with at least one hole card
  for (const [suit, count] of suitCounts) {
    if (count >= 5 && holeSuits.includes(suit)) return "monster"
  }

  // Straight: 5 consecutive ranks with hole card involvement
  const uniqueRanks = [...new Set(allRanks)].sort((a, b) => a - b)
  // Add low ace for wheel
  if (uniqueRanks.includes(14)) uniqueRanks.unshift(1)
  for (let i = 0; i <= uniqueRanks.length - 5; i++) {
    if (uniqueRanks[i + 4] - uniqueRanks[i] === 4) {
      const straightRanks = uniqueRanks.slice(i, i + 5)
      // Check if at least one hole card is in the straight
      const holeR1 = holeRanks[0] === 14 ? [14, 1] : [holeRanks[0]]
      const holeR2 = holeRanks[1] === 14 ? [14, 1] : [holeRanks[1]]
      if (holeR1.some((r) => straightRanks.includes(r)) || holeR2.some((r) => straightRanks.includes(r))) {
        return "monster"
      }
    }
  }

  // Three of a kind (set or trips) with hole card
  if (trips.length > 0 && trips.some((r) => holeInvolved(r))) {
    // Set: pocket pair hit the board
    const isPocketPair = holeRanks[0] === holeRanks[1]
    if (isPocketPair && trips.includes(holeRanks[0])) return "monster" // set
    return "two_pair" // trips (one hole card + board pair) — treated as strong but not monster
  }

// Two pair with hole cards
  const holePairs = pairs.filter((r) => holeInvolved(r))
  if (holePairs.length >= 2) return "two_pair"
  if (holePairs.length === 1 && trips.some((r) => holeInvolved(r))) return "two_pair"
  // Both hole cards paired with board
  const hole1Paired = boardRanks.includes(holeRanks[0])
  const hole2Paired = boardRanks.includes(holeRanks[1])
  if (hole1Paired && hole2Paired && holeRanks[0] !== holeRanks[1]) return "two_pair"

  // === FIX: Check if board already has a pair ===
  const boardRankCounts = new Map<number, number>()
  boardRanks.forEach((r) => boardRankCounts.set(r, (boardRankCounts.get(r) || 0) + 1))
  const boardPairRanks = [...boardRankCounts.entries()]
    .filter(([_, count]) => count >= 2)
    .map(([rank, _]) => rank)

  // Pocket pair + board has a different pair = two pair
  // Example: We have 77, board is Jc Js 8d 3h → 77 + JJ = two pair
  const isPocketPair = holeRanks[0] === holeRanks[1]
  if (isPocketPair && boardPairRanks.length > 0 && !boardPairRanks.includes(holeRanks[0])) {
    return "two_pair"
  }

  // One pair with hole card
  if (hole1Paired || hole2Paired) {
    const pairedRank = hole1Paired ? holeRanks[0] : holeRanks[1]
    const unpairedHoleRank = hole1Paired ? holeRanks[1] : holeRanks[0]

    // Our pair + board's different pair = two pair
    // Example: We have K7, board is Kc Qs Qh 8d → KK + QQ = two pair
    if (boardPairRanks.length > 0 && !boardPairRanks.includes(pairedRank)) {
      return "two_pair"
    }

    // Overpair: pocket pair above all board cards
    if (holeRanks[0] === holeRanks[1] && holeRanks[0] > boardRanks[0]) return "overpair"

    // Top pair
    if (pairedRank === boardRanks[0]) {
      // Top kicker? (other hole card is A or K)
      if (unpairedHoleRank >= 13) return "tptk"
      return "top_pair"
    }

    // Middle pair
    if (boardRanks.length >= 2 && pairedRank > boardRanks[boardRanks.length - 1] && pairedRank < boardRanks[0]) {
      return "middle_pair"
    }

    // Bottom pair
    return "bottom_pair"
  }

  // Overpair: pocket pair above all board cards (no board match needed since it's a pair in hand)
  if (holeRanks[0] === holeRanks[1] && holeRanks[0] > boardRanks[0]) return "overpair"
  // Underpair (pocket pair below board) — treat as bottom_pair
  if (holeRanks[0] === holeRanks[1]) return "bottom_pair"

  // === DRAWS ===

  // Flush draw: 4 cards same suit including hole card
  let hasFlushDraw = false
  for (const [suit, count] of suitCounts) {
    if (count === 4 && holeSuits.includes(suit)) {
      hasFlushDraw = true
      break
    }
  }

  // Straight draw detection
  // Strategy: check every possible 5-card straight window (A-5 through T-A)
  // For each window, count how many of our cards (hole + board) fill it
  // 4 of 5 filled = draw. Then check if hole cards are involved and if it's OESD or gutshot.
  let hasStraightDraw = false
  let straightDrawType = ""

  // All straight windows: [low, low+1, low+2, low+3, low+4]
  // A-low = [1,2,3,4,5], then [2,3,4,5,6] ... [10,11,12,13,14]
  const allUniqueRanks = new Set(allRanks)
  // Add ace as 1 for wheel
  if (allUniqueRanks.has(14)) allUniqueRanks.add(1)

  const holeRankSet = new Set(holeRanks)
  if (holeRanks.includes(14)) holeRankSet.add(1)

  for (let low = 1; low <= 10; low++) {
    const window = [low, low + 1, low + 2, low + 3, low + 4]
    const filled = window.filter((r) => allUniqueRanks.has(r))
    const holeInWindow = window.filter((r) => holeRankSet.has(r))

    if (filled.length === 5) {
      // Made straight — already caught above, skip
      continue
    }

    if (filled.length === 4 && holeInWindow.length >= 1) {
      // We have 4 of 5 cards for this straight and at least one hole card contributes
      hasStraightDraw = true

      // Determine OESD vs gutshot:
      // OESD: the missing card is at either end of the window
      // Gutshot: the missing card is in the middle
      const missing = window.filter((r) => !allUniqueRanks.has(r))
      if (missing.length === 1) {
        const missingRank = missing[0]
        if (missingRank === window[0] || missingRank === window[4]) {
          // Missing card is at the edge — but check if the straight is capped
          // E.g., A-2-3-4 is NOT open-ended (can only make 5 high straight)
          // And J-Q-K-A is NOT open-ended (can only go one way)
          if (window[4] === 14 || window[0] === 1) {
            // One end is blocked (ace-high or ace-low)
            straightDrawType = straightDrawType || "gutshot"
          } else {
            straightDrawType = "oesd" // prefer OESD over gutshot
          }
        } else {
          straightDrawType = straightDrawType || "gutshot"
        }
      }
    }
  }

  // Combo draw: flush draw + straight draw
  if (hasFlushDraw && hasStraightDraw) return "combo_draw"
  if (hasFlushDraw) return "flush_draw"
  if (hasStraightDraw && straightDrawType === "oesd") return "oesd"
  if (hasStraightDraw) return "gutshot"

  // Overcards: both hole cards above all board cards
  if (holeRanks[0] > boardRanks[0] && holeRanks[1] > boardRanks[0]) return "overcards"

  // Nothing
  return "air"
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

const PokerInputComponent: React.FC<ComponentProps> = (props) => {
  const { args } = props
  const mode = (args["mode"] as string) || "standard"
  const stakes = (args["stakes"] as string) || "$1/$2"
  const bbSize = (args["bb_size"] as number) || 2.0
  const stackSize = (args["stack_size"] as number) || 200.0
  const decisionFromPython = args["decision_result"] as DecisionResult | null
  const restoreState = args["restore_state"] as Record<string, any> | null
  // NEW: Track which table the decision is for (Python should send this back)
  const decisionTableId = (args["decision_table_id"] as number) || 1
  const showSecondTableFromPython = args["show_second_table"] as boolean | undefined
  const activeTableFromPython = args["active_table"] as (1 | 2) | undefined
  const primaryHoldsTableFromPython = args["primary_holds_table"] as (1 | 2) | undefined
  // Legacy t2_* args (keep for backward compatibility)
  const t2GameStateFromPython = args["t2_game_state"] as GameState | undefined
  const t2StepFromPython = args["t2_step"] as InputStep | undefined
  const t2DecisionFromPython = args["t2_decision"] as DecisionResult | null | undefined

  // NEW: Explicit table1_* and table2_* args
  const table1GameStateFromPython = args["table1_game_state"] as GameState | undefined
  const table1StepFromPython = args["table1_step"] as InputStep | undefined
  const table1DecisionFromPython = args["table1_decision"] as DecisionResult | null | undefined
  const table2GameStateFromPython = args["table2_game_state"] as GameState | undefined
  const table2StepFromPython = args["table2_step"] as InputStep | undefined
  const table2DecisionFromPython = args["table2_decision"] as DecisionResult | null | undefined
  const table1BoardEntryIndexFromPython = args["table1_board_entry_index"] as number | undefined
  const table2BoardEntryIndexFromPython = args["table2_board_entry_index"] as number | undefined

  // ---- Game State ----
  // On mount, restore from props if available (survives Streamlit reruns)
  const [gameState, setGameState] = useState<GameState>(() => {
    // Primary state holds the ACTIVE table's data
    // If primaryHoldsTable is 1: primary=Table1
    // If primaryHoldsTable is 2: primary=Table2
    
    // First try new explicit table args
    if (primaryHoldsTableFromPython === 1 && table1GameStateFromPython) {
      return table1GameStateFromPython
    } else if (primaryHoldsTableFromPython === 2 && table2GameStateFromPython) {
      return table2GameStateFromPython
    }
    
    // Fallback to legacy restoreState
    const rs = restoreState
    if (rs) {
      return {
        position: rs.position || null,
        card1: parseCard(rs.card1) || null,
        card2: parseCard(rs.card2) || null,
        street: rs.street || "preflop",
        action_facing: rs.action_facing || "none",
        facing_bet: rs.facing_bet || 0,
        num_limpers: rs.num_limpers || 0,
        board_cards: rs.board ? parseBoard(rs.board) : [null, null, null, null, null],
        pot_size: rs.pot_size || 0,
        board_texture: rs.board_texture || null,
        hand_strength: rs.hand_strength || null,
        villain_type: rs.villain_type || "unknown",
        we_are_aggressor: rs.we_are_aggressor || false,
      }
    }
    return { ...FRESH_GAME_STATE }
  })

  // ---- UI State ----
  // If we have a decision from Python, start in showing_decision
  // If we have restore_state but no decision, we're continuing to next street
  const [step, setStep] = useState<InputStep>(() => {
    if (decisionFromPython) return "showing_decision"
    
    // Try new explicit table args first
    if (primaryHoldsTableFromPython === 1 && table1StepFromPython) {
      return table1StepFromPython
    } else if (primaryHoldsTableFromPython === 2 && table2StepFromPython) {
      return table2StepFromPython
    }
    
    // Fallback to legacy restoreState
    if (restoreState && !decisionFromPython) {
      const street = restoreState.street || "preflop"
      if (street !== "preflop") return "board_rank"
      return "position"
    }
    return "position"
  })
  const [pendingRank, setPendingRank] = useState<string>("")
  const [amountStr, setAmountStr] = useState<string>("")
  const [amountLabel, setAmountLabel] = useState<string>("Enter Amount")
  const [amountContext, setAmountContext] = useState<string | null>(null) // Context for "they raised me" scenario
  const [potStr, setPotStr] = useState<string>("")
  const [limperCount, setLimperCount] = useState<number>(0)
  const [boardEntryIndex, setBoardEntryIndex] = useState<number>(() => {
      // Try new explicit table args first
      if (primaryHoldsTableFromPython === 1 && table1BoardEntryIndexFromPython !== undefined) {
        return table1BoardEntryIndexFromPython
      } else if (primaryHoldsTableFromPython === 2 && table2BoardEntryIndexFromPython !== undefined) {
        return table2BoardEntryIndexFromPython
      }
      
      // Fallback to legacy restoreState
      if (restoreState && !decisionFromPython) {
        const street = restoreState.street || "preflop"
        const board = restoreState.board || ""
        const existingCards = Math.floor(board.length / 2)
        if (street === "flop" && existingCards < 3) return existingCards
        if (street === "turn") return existingCards < 4 ? existingCards : 3
        if (street === "river") return existingCards < 5 ? existingCards : 4
      }
      return 0
    })
    const [chosenBluffAction, setChosenBluffAction] = useState<"BET" | "CHECK" | null>(null)
    const [decision, setDecision] = useState<DecisionResult | null>(() => {
    if (decisionFromPython) return decisionFromPython
    
    // Try new explicit table args
    if (primaryHoldsTableFromPython === 1 && table1DecisionFromPython !== undefined) {
      return table1DecisionFromPython
    } else if (primaryHoldsTableFromPython === 2 && table2DecisionFromPython !== undefined) {
      return table2DecisionFromPython
    }
    
    return null
  })
  const [keyboardActive, setKeyboardActive] = useState(mode !== "standard")
  const [showOverlay, setShowOverlay] = useState(false)
  const [showCloseConfirm, setShowCloseConfirm] = useState(false)

  // =========================================================================
  // TWO-TABLE MODE STATE (NEW)
  // =========================================================================
  const [activeTable, setActiveTable] = useState<1 | 2>(activeTableFromPython ?? 1)
  const [showSecondTable, setShowSecondTable] = useState(showSecondTableFromPython ?? false)
  const [primaryHoldsTable, setPrimaryHoldsTable] = useState<1 | 2>(primaryHoldsTableFromPython ?? 1)
  const [pendingDecisionTable, setPendingDecisionTable] = useState<1 | 2 | null>(null)  // NEW: Track which table is waiting for decision
  const [t2PendingRank, setT2PendingRank] = useState<string>("")
  const [t2AmountStr, setT2AmountStr] = useState<string>("")
  const [t2AmountLabel, setT2AmountLabel] = useState<string>("Enter Amount")
  const [t2PotStr, setT2PotStr] = useState<string>("")
  const [t2LimperCount, setT2LimperCount] = useState<number>(1)
  const [t2BoardEntryIndex, setT2BoardEntryIndex] = useState<number>(() => {
    if (primaryHoldsTableFromPython === 1 && table2BoardEntryIndexFromPython !== undefined) {
      return table2BoardEntryIndexFromPython
    } else if (primaryHoldsTableFromPython === 2 && table1BoardEntryIndexFromPython !== undefined) {
      return table1BoardEntryIndexFromPython
    }
    return 0
  })
  // Initialize t2 state - needs to hold the INACTIVE table's data
  // If primaryHoldsTable is 1: primary=Table1, t2=Table2
  // If primaryHoldsTable is 2: primary=Table2, t2=Table1
  const [t2GameState, setT2GameState] = useState<GameState>(() => {
    if (primaryHoldsTableFromPython === 1 && table2GameStateFromPython) {
      return table2GameStateFromPython
    } else if (primaryHoldsTableFromPython === 2 && table1GameStateFromPython) {
      return table1GameStateFromPython
    }
    // Fallback to legacy or fresh
    return t2GameStateFromPython ?? { ...FRESH_GAME_STATE }
  })

  const [t2Step, setT2Step] = useState<InputStep>(() => {
    if (primaryHoldsTableFromPython === 1 && table2StepFromPython) {
      return table2StepFromPython
    } else if (primaryHoldsTableFromPython === 2 && table1StepFromPython) {
      return table1StepFromPython
    }
    return t2StepFromPython ?? "position"
  })

  const [t2Decision, setT2Decision] = useState<DecisionResult | null>(() => {
    if (primaryHoldsTableFromPython === 1 && table2DecisionFromPython !== undefined) {
      return table2DecisionFromPython
    } else if (primaryHoldsTableFromPython === 2 && table1DecisionFromPython !== undefined) {
      return table1DecisionFromPython
    }
    return t2DecisionFromPython ?? null
  })

  const containerRef = useRef<HTMLDivElement>(null)
  const amountRef = useRef<HTMLInputElement>(null)
  const potRef = useRef<HTMLInputElement>(null)

  // ---- Set frame height ----
  useEffect(() => {
    Streamlit.setFrameHeight()
  })

  // ---- Focus amount input when step changes ----
  useEffect(() => {
    if ((step === "amount" || step === "limper_count") && amountRef.current) {
      setTimeout(() => amountRef.current?.focus(), 50)
    }
    if (step === "pot_size" && potRef.current) {
      setTimeout(() => potRef.current?.focus(), 50)
    }
    // For all other steps, focus the container so keyboard shortcuts work immediately
    if (step !== "amount" && step !== "pot_size" && step !== "limper_count" && containerRef.current) {
      setTimeout(() => containerRef.current?.focus(), 50)
    }
  }, [step])

  // =========================================================================
  // DECISION ROUTING: Route incoming decisions to correct table
  // =========================================================================
  // Track the last decision we processed to avoid re-applying on every render
  const lastProcessedDecisionRef = useRef<string | null>(null)
  
  useEffect(() => {
    if (!decisionFromPython) {
      lastProcessedDecisionRef.current = null
      return
    }
    
    // Create a unique key for this decision to detect if it's new
    const decisionKey = `${decisionTableId}-${decisionFromPython.display}-${decisionFromPython.action}`
    
    // Only process if this is a NEW decision we haven't seen
    if (lastProcessedDecisionRef.current === decisionKey) {
      return // Already processed this exact decision
    }
    
    // Mark as processed
    lastProcessedDecisionRef.current = decisionKey
    
    // Route decision based on which table's data is in primary vs t2
    if (decisionTableId === primaryHoldsTable) {
      setDecision(decisionFromPython)
      setStep("showing_decision")
    } else {
      setT2Decision(decisionFromPython)
      setT2Step("showing_decision")
    }
    setPendingDecisionTable(null)
  }, [decisionFromPython, decisionTableId, primaryHoldsTable])

  // =========================================================================
  // TWO-TABLE MODE: SWITCH TABLE FUNCTION (NEW)
  // =========================================================================
  const switchTable = useCallback(() => {
    // Only allow switching if second table is visible
    if (mode !== "two_table" && !showSecondTable) return

    // Save current primary state
    const saveGs = gameState
    const saveStep = step
    const savePendingRank = pendingRank
    const saveAmountStr = amountStr
    const saveAmountLabel = amountLabel
    const savePotStr = potStr
    const saveLimperCount = limperCount
    const saveBoardEntryIndex = boardEntryIndex
    const saveDecision = decision

    // Load t2 state into primary
    setGameState(t2GameState)
    setStep(t2Step)
    setPendingRank(t2PendingRank)
    setAmountStr(t2AmountStr)
    setAmountLabel(t2AmountLabel)
    setPotStr(t2PotStr)
    setLimperCount(t2LimperCount)
    setBoardEntryIndex(t2BoardEntryIndex)
    setDecision(t2Decision)

    // Save old primary into t2
    setT2GameState(saveGs)
    setT2Step(saveStep)
    setT2PendingRank(savePendingRank)
    setT2AmountStr(saveAmountStr)
    setT2AmountLabel(saveAmountLabel)
    setT2PotStr(savePotStr)
    setT2LimperCount(saveLimperCount)
    setT2BoardEntryIndex(saveBoardEntryIndex)
    setT2Decision(saveDecision)

    // Toggle active table
    setActiveTable((t) => (t === 1 ? 2 : 1))
    setPrimaryHoldsTable((t) => (t === 1 ? 2 : 1))  // FIX: Track the swap
  }, [
    mode, showSecondTable, gameState, step, pendingRank, amountStr, amountLabel, potStr, limperCount, boardEntryIndex, decision,
    t2GameState, t2Step, t2PendingRank, t2AmountStr, t2AmountLabel, t2PotStr, t2LimperCount, t2BoardEntryIndex, t2Decision
  ])

  // ---- Toggle second table visibility ----
  const toggleSecondTable = useCallback(() => {
    if (showSecondTable) {
      // Closing second table - reset it and ensure we're on table 1
      setT2GameState({ ...FRESH_GAME_STATE })
      setT2Step("position")
      setT2PendingRank("")
      setT2AmountStr("")
      setT2AmountLabel("Enter Amount")
      setT2PotStr("")
      setT2LimperCount(1)
      setT2BoardEntryIndex(0)
      setT2Decision(null)
      // If we were on table 2, switch back to table 1
      if (activeTable === 2) {
        // Swap states so table 1 is primary
        switchTable()
      }
      setActiveTable(1)
      setPrimaryHoldsTable(1)
    }
    setShowSecondTable(!showSecondTable)
  }, [showSecondTable, activeTable, switchTable])

  // Check if Table 2 has meaningful data that would be lost
  const getTable2DataStatus = useCallback(() => {
    // When activeTable is 1, Table 2 data is in t2 variables
    // When activeTable is 2, Table 2 data is in primary variables (swapped)
    const t2Gs = activeTable === 1 ? t2GameState : gameState
    const t2CurrentStep = activeTable === 1 ? t2Step : step
    const t2CurrentDecision = activeTable === 1 ? t2Decision : decision

    const hasPosition = !!t2Gs.position
    const hasCards = !!t2Gs.card1 || !!t2Gs.card2
    const hasDecision = t2CurrentStep === "showing_decision" && !!t2CurrentDecision
    const isInProgress = hasPosition && t2CurrentStep !== "position"

    return {
      isEmpty: !hasPosition,
      hasDecision,
      isInProgress: isInProgress && !hasDecision,
      position: t2Gs.position,
      card1: t2Gs.card1,
      card2: t2Gs.card2,
      step: t2CurrentStep,
      decision: t2CurrentDecision,
    }
  }, [activeTable, gameState, t2GameState, step, t2Step, decision, t2Decision])

  // Handle closing Table 2 with confirmation if needed
  const handleCloseTable2 = useCallback(() => {
    const status = getTable2DataStatus()
    
    if (status.isEmpty) {
      // No data, safe to close immediately
      toggleSecondTable()
    } else {
      // Has data, show confirmation
      setShowCloseConfirm(true)
    }
  }, [getTable2DataStatus, toggleSecondTable])

  // Confirm close - actually close the table
  const confirmCloseTable2 = useCallback(() => {
    setShowCloseConfirm(false)
    
    // If we're on Table 2, switch to Table 1 first
    if (activeTable === 2) {
      // Reset Table 2 data (which is currently in primary state)
      setGameState({ ...FRESH_GAME_STATE })
      setStep("position")
      setPendingRank("")
      setAmountStr("")
      setAmountLabel("Enter Amount")
      setAmountContext(null)
      setPotStr("")
      setLimperCount(0)
      setBoardEntryIndex(0)
      setDecision(null)
      
      // Swap to put Table 1 back in primary
      switchTable()
    }
    
    // Now close
    toggleSecondTable()
  }, [activeTable, switchTable, toggleSecondTable])

  // Cancel close
  const cancelCloseTable2 = useCallback(() => {
    setShowCloseConfirm(false)
  }, [])

  // ---- Reset for new hand ----
  const resetHand = useCallback(() => {
    setGameState({ ...FRESH_GAME_STATE })
    setStep("position")
    setPendingRank("")
    setAmountStr("")
    setAmountContext(null)
    setPotStr("")
    setLimperCount(1)
    setBoardEntryIndex(0)
    setDecision(null)
    setChosenBluffAction(null)
  }, [])

  // ---- Submit game state to Streamlit ----
  const submitDecisionRequest = useCallback(() => {
    const gs = gameState
    const handStr = cardToString(gs.card1) + cardToString(gs.card2)

    const autoTexture = gs.street !== "preflop"
      ? detectBoardTexture(gs.board_cards)
      : null
    const autoStrength = gs.street !== "preflop"
      ? detectHandStrength(gs.card1, gs.card2, gs.board_cards)
      : null

    // Determine which state holds which table's data
    const table1GameState = primaryHoldsTable === 1 ? gameState : t2GameState
    const table1Step = primaryHoldsTable === 1 ? step : t2Step
    const table1Decision = primaryHoldsTable === 1 ? decision : t2Decision
    const table1BoardEntryIndex = primaryHoldsTable === 1 ? boardEntryIndex : t2BoardEntryIndex
    
    const table2GameState = primaryHoldsTable === 2 ? gameState : t2GameState
    const table2Step = primaryHoldsTable === 2 ? step : t2Step
    const table2Decision = primaryHoldsTable === 2 ? decision : t2Decision
    const table2BoardEntryIndex = primaryHoldsTable === 2 ? boardEntryIndex : t2BoardEntryIndex

    Streamlit.setComponentValue({
      type: "decision_request",
      table_id: primaryHoldsTable,
      position: gs.position,
      card1: cardToString(gs.card1),
      card2: cardToString(gs.card2),
      hand: handStr,
      street: gs.street,
      action_facing: gs.action_facing,
      facing_bet: gs.facing_bet,
      num_limpers: gs.num_limpers,
      board: gs.board_cards
        .filter((c) => c !== null)
        .map((c) => cardToString(c))
        .join(""),
      pot_size: gs.pot_size,
      board_texture: gs.board_texture || autoTexture,
      hand_strength: gs.hand_strength || autoStrength,
      villain_type: gs.villain_type,
      we_are_aggressor: gs.we_are_aggressor,
      show_second_table: showSecondTable,
      active_table: activeTable,
      primary_holds_table: primaryHoldsTable,
      // Send BOTH tables' data explicitly
      table1_game_state: table1GameState,
      table1_step: table1Step,
      table1_decision: table1Decision,
      table2_game_state: table2GameState,
      table2_step: table2Step,
      table2_decision: table2Decision,
      table1_board_entry_index: table1BoardEntryIndex,
      table2_board_entry_index: table2BoardEntryIndex,
    })
  }, [gameState, activeTable, primaryHoldsTable, showSecondTable, step, decision, t2GameState, t2Step, t2Decision])

  // ---- Send outcome to Streamlit (new hand without decision) ----
  const sendNewHand = useCallback(() => {
    // Reset local state FIRST (before sending to Python)
    resetHand()
    
    // For the table that just reset, send fresh state
    const freshState = { ...FRESH_GAME_STATE }
    
    const table1GameState = primaryHoldsTable === 1 ? freshState : t2GameState
    const table1Step = primaryHoldsTable === 1 ? "position" : t2Step
    const table1Decision = primaryHoldsTable === 1 ? null : t2Decision
    const table1BoardEntryIndex = primaryHoldsTable === 1 ? 0 : t2BoardEntryIndex
    
    const table2GameState = primaryHoldsTable === 2 ? freshState : t2GameState
    const table2Step = primaryHoldsTable === 2 ? "position" : t2Step
    const table2Decision = primaryHoldsTable === 2 ? null : t2Decision
    const table2BoardEntryIndex = primaryHoldsTable === 2 ? 0 : t2BoardEntryIndex

    Streamlit.setComponentValue({ 
      type: "new_hand", 
      table_id: primaryHoldsTable,
      show_second_table: showSecondTable,
      active_table: activeTable,
      primary_holds_table: primaryHoldsTable,
      table1_game_state: table1GameState,
      table1_step: table1Step,
      table1_decision: table1Decision,
      table1_board_entry_index: table1BoardEntryIndex,
      table2_game_state: table2GameState,
      table2_step: table2Step,
      table2_decision: table2Decision,
      table2_board_entry_index: table2BoardEntryIndex,
    })
  }, [resetHand, primaryHoldsTable, showSecondTable, activeTable, t2GameState, t2Step, t2Decision, t2BoardEntryIndex])

  // ---- Send hand complete with outcome to Streamlit ----
  const sendHandComplete = useCallback((outcome: "won" | "lost" | "folded") => {
    const gs = gameState
    const handStr = cardToString(gs.card1) + cardToString(gs.card2)

    const autoTexture = gs.street !== "preflop"
      ? detectBoardTexture(gs.board_cards)
      : null
    const autoStrength = gs.street !== "preflop"
      ? detectHandStrength(gs.card1, gs.card2, gs.board_cards)
      : null

    const handContext = {
      position: gs.position,
      cards: handStr,
      street: gs.street,
      action_facing: gs.action_facing,
      facing_bet: gs.facing_bet,
      pot_size: gs.pot_size,
      board: gs.board_cards.filter((c) => c !== null).map((c) => cardToString(c)).join(""),
      board_texture: gs.board_texture || autoTexture,
      hand_strength: gs.hand_strength || autoStrength,
      villain_type: gs.villain_type,
      we_are_aggressor: gs.we_are_aggressor,
      num_limpers: gs.num_limpers,
    }

    const freshState = { ...FRESH_GAME_STATE }

    const table1GameState = primaryHoldsTable === 1 ? freshState : t2GameState
    const table1Step = primaryHoldsTable === 1 ? "position" as InputStep : t2Step
    const table1Decision = primaryHoldsTable === 1 ? null : t2Decision
    const table1BoardEntryIndex = primaryHoldsTable === 1 ? 0 : t2BoardEntryIndex

    const table2GameState = primaryHoldsTable === 2 ? freshState : t2GameState
    const table2Step = primaryHoldsTable === 2 ? "position" as InputStep : t2Step
    const table2Decision = primaryHoldsTable === 2 ? null : t2Decision
    const table2BoardEntryIndex = primaryHoldsTable === 2 ? 0 : t2BoardEntryIndex

    // Build bluff data if this was a bluff hand
    const bluff_data = decision?.bluff_context ? {
      spot_type: decision.bluff_context.spot_type,
      delivery: decision.bluff_context.delivery,
      recommended: decision.bluff_context.recommended_action,
      user_action: chosenBluffAction || "BET",
      outcome: outcome === "won" ? "call_won" 
        : outcome === "lost" ? "call_lost" 
        : "fold",
      profit: 0,
      bet_amount: decision.bluff_context.bet_amount,
      pot_size: decision.bluff_context.pot_size,
      ev_of_bet: decision.bluff_context.ev_of_bet,
      break_even_pct: decision.bluff_context.break_even_pct,
      estimated_fold_pct: decision.bluff_context.estimated_fold_pct,
    } : null

    Streamlit.setComponentValue({
      type: "hand_complete",
      table_id: primaryHoldsTable,
      outcome: outcome,
      action_taken: decision?.display || "",
      hand_context: handContext,
      bluff_data: bluff_data,
      show_second_table: showSecondTable,
      active_table: activeTable,
      primary_holds_table: primaryHoldsTable,
      table1_game_state: table1GameState,
      table1_step: table1Step,
      table1_decision: table1Decision,
      table1_board_entry_index: table1BoardEntryIndex,
      table2_game_state: table2GameState,
      table2_step: table2Step,
      table2_decision: table2Decision,
      table2_board_entry_index: table2BoardEntryIndex,
    })

    resetHand()
  }, [gameState, decision, chosenBluffAction, primaryHoldsTable, showSecondTable, activeTable, t2GameState, t2Step, t2Decision, t2BoardEntryIndex, resetHand])

  // ---- They raised me back — re-query same street with new action ----
  const theyRaisedMe = useCallback(() => {
      const currentAction = gameState.action_facing
      const street = gameState.street

      // Capture what our action was before they raised
      let ourAction = ""
      let ourAmount = ""
      if (decision) {
        ourAction = decision.display
        // Extract amount if present (e.g., "RAISE TO $12" -> "$12")
        const match = decision.display.match(/\$([\d.]+)/)
        if (match) {
          ourAmount = "$" + Math.round(parseFloat(match[1]))
        }
      }

      let newAction = "check_raise" // default for postflop

      if (street === "preflop") {
        if (currentAction === "none" || currentAction === "limp") {
          newAction = "raise"
        } else if (currentAction === "raise") {
          newAction = "3bet"
        } else if (currentAction === "3bet") {
          newAction = "4bet"
        } else {
          newAction = "4bet"
        }
      } else {
        newAction = "check_raise"
      }

      setGameState((s) => ({
        ...s,
        action_facing: newAction,
        facing_bet: 0,
        we_are_aggressor: true,
      }))
      // Don't clear decision yet — keep it visible if user goes back
      // Decision will be replaced when new one arrives
      setAmountStr("")
      
      // Set contextual label and context message
      if (street === "preflop") {
        if (newAction === "raise") {
          setAmountLabel("Their raise to $")
          setAmountContext(ourAmount ? `You raised to ${ourAmount}` : `You raised`)
        } else if (newAction === "3bet") {
          setAmountLabel("Their 3-bet to $")
          setAmountContext(ourAmount ? `You 3-bet to ${ourAmount}` : `You 3-bet`)
        } else {
          setAmountLabel("Their 4-bet to $")
          setAmountContext(ourAmount ? `You 4-bet to ${ourAmount}` : `You 4-bet`)
        }
      } else {
        setAmountLabel("Their raise to $")
        setAmountContext(ourAmount ? `You bet ${ourAmount}` : `You bet`)
      }
      
      setStep("amount")
      setTimeout(() => {
        amountRef.current?.focus()
      }, 100)
    }, [gameState.action_facing, gameState.street, decision])

  // ---- They bet after we checked — re-query same street ----
  const theyBet = useCallback(() => {
      setGameState((s) => ({
        ...s,
        action_facing: "bet",
        facing_bet: 0,
        we_are_aggressor: false,
      }))
      // Don't clear decision yet — keep it visible if user goes back  
      setAmountStr("")
      setAmountLabel("Their bet $")
      setAmountContext("You checked")
      setStep("amount")
      setTimeout(() => {
        amountRef.current?.focus()
      }, 50)
    }, [])

  // ---- Step navigation ----
  const goBack = useCallback(() => {
      switch (step) {
        // === PREFLOP BACK FLOW ===
        case "card1_rank":
          setGameState((s) => ({ ...s, position: null }))
          setStep("position")
          break
          
        case "card1_suit":
          setPendingRank("")
          setStep("card1_rank")
          break
          
        case "card2_rank":
          setGameState((s) => ({ ...s, card1: null }))
          setStep("card1_rank")
          break
          
        case "card2_suit":
          setPendingRank("")
          setStep("card2_rank")
          break
          
        case "action":
          if (gameState.street === "preflop") {
            setGameState((s) => ({ ...s, card2: null }))
            setStep("card2_rank")
          } else {
            setPotStr(gameState.pot_size > 0 ? gameState.pot_size.toString() : "")
            setStep("pot_size")
          }
          break
          
        case "amount":
          setAmountStr("")
          // If we got here from "They Raised Me" or "They Bet" (re-raise flow),
          // go back to showing the previous decision instead of the action step
          if (amountContext) {
            // Restore game state from before they raised/bet
            setGameState((s) => ({
              ...s,
              action_facing: s.we_are_aggressor ? "none" : s.action_facing,
              facing_bet: 0,
            }))
            setAmountContext("")
            setAmountLabel("")
            setStep("showing_decision")
          } else {
            setGameState((s) => ({ ...s, facing_bet: 0 }))
            setStep("action")
          }
          break
          
        case "limper_count":
          setAmountStr("")
          setGameState((s) => ({ ...s, num_limpers: 0 }))
          setStep("action")
          break
          
        case "villain_type":
          if (gameState.action_facing === "raise" || 
              gameState.action_facing === "3bet" || 
              gameState.action_facing === "4bet" ||
              gameState.action_facing === "bet" ||
              gameState.action_facing === "check_raise") {
            setAmountStr(gameState.facing_bet > 0 ? gameState.facing_bet.toString() : "")
            setStep("amount")
          } else if (gameState.action_facing === "limp") {
            setAmountStr(gameState.num_limpers > 0 ? gameState.num_limpers.toString() : "")
            setStep("limper_count")
          } else {
            setStep("action")
          }
          break
          
        case "ready":
          setStep("villain_type")
          break

        // === POST-FLOP BACK FLOW ===
        case "board_rank":
          {
            const streetStartIndex = gameState.street === "flop" ? 0 : gameState.street === "turn" ? 3 : 4
            
            if (boardEntryIndex === streetStartIndex) {
              if (gameState.street === "flop") {
                setGameState((s) => ({
                  ...s,
                  street: "preflop",
                  board_cards: [null, null, null, null, null],
                  pot_size: 0,
                }))
                setBoardEntryIndex(0)
                setStep("villain_type")
              } else if (gameState.street === "turn") {
                setGameState((s) => ({ ...s, street: "flop" }))
                setBoardEntryIndex(3)
                setStep("villain_type")
              } else if (gameState.street === "river") {
                setGameState((s) => ({ ...s, street: "turn" }))
                setBoardEntryIndex(4)
                setStep("villain_type")
              }
            } else {
              const prevIdx = boardEntryIndex - 1
              const newBoard = [...gameState.board_cards]
              newBoard[prevIdx] = null
              setGameState((s) => ({ ...s, board_cards: newBoard }))
              setBoardEntryIndex(prevIdx)
              setPendingRank("")
            }
          }
          break
          
        case "board_suit":
          setPendingRank("")
          setStep("board_rank")
          break
          
        case "pot_size":
          {
            const needed = requiredBoardCards(gameState.street)
            const lastIdx = needed - 1
            const newBoard = [...gameState.board_cards]
            newBoard[lastIdx] = null
            setGameState((s) => ({ ...s, board_cards: newBoard }))
            setBoardEntryIndex(lastIdx)
            setPotStr("")
            setStep("board_rank")
          }
          break
          
        // showing_decision: handled by UI buttons, not goBack
          
        default:
          break
      }
    }, [step, boardEntryIndex, gameState])

  // ---- Handle position select ----
  const selectPosition = useCallback((pos: string) => {
    setGameState((s) => ({ ...s, position: pos }))
    setStep("card1_rank")
  }, [])

  // ---- Handle card rank select ----
  const selectRank = useCallback(
    (rank: string) => {
      if (step === "card1_rank" || step === "card2_rank" || step === "board_rank") {
        setPendingRank(rank)
        if (step === "card1_rank") setStep("card1_suit")
        else if (step === "card2_rank") setStep("card2_suit")
        else setStep("board_suit")
      }
    },
    [step]
  )

  // ---- Handle card suit select ----
  const selectSuit = useCallback(
    (suit: string) => {
      if (!pendingRank) return

      // Check for duplicates
      if (isCardUsed(pendingRank, suit, gameState.card1, gameState.card2, gameState.board_cards)) {
        setPendingRank("")
        if (step === "card1_suit") setStep("card1_rank")
        else if (step === "card2_suit") setStep("card2_rank")
        else setStep("board_rank")
        return
      }

      const card: CardData = { rank: pendingRank, suit }
      setPendingRank("")

      if (step === "card1_suit") {
        setGameState((s) => ({ ...s, card1: card }))
        setStep("card2_rank")
      } else if (step === "card2_suit") {
        setGameState((s) => ({ ...s, card2: card }))
        setStep("action")
      } else if (step === "board_suit") {
        const newBoard = [...gameState.board_cards]
        newBoard[boardEntryIndex] = card
        setGameState((s) => ({ ...s, board_cards: newBoard }))
        const nextIdx = boardEntryIndex + 1
        const needed = requiredBoardCards(gameState.street)
        if (nextIdx >= needed) {
          setBoardEntryIndex(nextIdx)
          setStep("pot_size")
        } else {
          setBoardEntryIndex(nextIdx)
          setStep("board_rank")
        }
      }
    },
    [pendingRank, step, gameState, boardEntryIndex]
  )

  // ---- Handle action select ----
  const selectAction = useCallback(
    (actionId: string, needsAmount: boolean, needsCount?: boolean) => {
      setGameState((s) => {
        // On post-flop streets, preserve preflop aggressor status
        let aggressor = s.we_are_aggressor
        if (s.street === "preflop") {
          // Preflop: we don't know our decision yet, keep default false
          // Aggressor will be correctly set in continueToStreet based on actual decision
          aggressor = false
        } else {
          // Post-flop: "none" (checked to us) preserves existing aggressor status
          // "bet" means they bet into us, so they have initiative (but we may have been preflop aggressor)
          // Keep existing aggressor status — it carries from preflop
          if (actionId === "check_raise") {
            aggressor = true // We check-raised, we're definitely the aggressor now
          }
        }
        return {
          ...s,
          action_facing: actionId,
          we_are_aggressor: aggressor,
        }
      })

      if (needsCount) {
        // Limper count — ask how many
        setAmountStr("")
        setAmountLabel("How many limpers?")
        setStep("limper_count")
      } else if (needsAmount) {
      // Set contextual label for the amount input
        const actions = gameState.street === "preflop" ? PREFLOP_ACTIONS_ALL : POSTFLOP_ACTIONS_ALL
        const action = actions.find((a) => a.id === actionId)
        setAmountLabel(action?.amountLabel || "Their raise to $")
        setAmountContext(null) // Clear context for normal action selection
        setAmountStr("")
        setStep("amount")
      } else {
        setStep("villain_type")
      }
    },
    [gameState.street]
  )

  // ---- Handle amount confirm ----
  const confirmAmount = useCallback(() => {
    const amt = parseFloat(amountStr)
    if (isNaN(amt) || amt <= 0) return
    setGameState((s) => ({ ...s, facing_bet: amt }))
    setStep("villain_type")
  }, [amountStr])

  // ---- Handle limper count confirm ----
  const confirmLimperCount = useCallback(() => {
    const count = parseInt(amountStr)
    if (isNaN(count) || count < 1) return
    setGameState((s) => ({ ...s, num_limpers: Math.min(count, 5) }))
    setStep("villain_type")
  }, [amountStr])

  // ---- Handle pot size confirm ----
  const confirmPotSize = useCallback(() => {
    const pot = parseFloat(potStr)
    if (isNaN(pot) || pot <= 0) return
    setGameState((s) => ({ ...s, pot_size: pot }))
    setStep("action")  // Post-flop: ask what action faces us
  }, [potStr])

  // ---- Handle street change to post-flop ----
  const continueToStreet = useCallback(
    (street: Street) => {
      const newBoardEntryIndex = street === "flop" ? 0 : street === "turn" ? 3 : 4
      
      setGameState((s) => {
        let wasAggressor = false
        if (decision) {
          const d = decision.display.toUpperCase()
          wasAggressor = ["RAISE", "BET", "RE-RAISE", "3-BET", "4-BET", "ALL-IN", "ALL IN", "ISO"].some(
            (a) => d.includes(a)
          )
        }
        return { 
          ...s, 
          street,
          action_facing: "none",
          facing_bet: 0,
          we_are_aggressor: wasAggressor,
        }
      })
      setBoardEntryIndex(newBoardEntryIndex)
      setStep("board_rank")
      setDecision(null)

      // Determine which state holds which table's data
      // Note: We need to use the NEW gameState values, but setGameState is async
      // So we compute what the new state will be
      const newPrimaryGameState = {
        ...gameState,
        street,
        action_facing: "none",
        facing_bet: 0,
        we_are_aggressor: decision ? ["RAISE", "BET", "RE-RAISE", "3-BET", "4-BET", "ALL-IN", "ALL IN", "ISO"].some(
          (a) => decision.display.toUpperCase().includes(a)
        ) : false,
      }
      
      const table1GameState = primaryHoldsTable === 1 ? newPrimaryGameState : t2GameState
      const table1Step = primaryHoldsTable === 1 ? "board_rank" : t2Step
      const table1Decision = primaryHoldsTable === 1 ? null : t2Decision
      const table1BoardEntryIndex = primaryHoldsTable === 1 ? newBoardEntryIndex : t2BoardEntryIndex
      
      const table2GameState = primaryHoldsTable === 2 ? newPrimaryGameState : t2GameState
      const table2Step = primaryHoldsTable === 2 ? "board_rank" : t2Step
      const table2Decision = primaryHoldsTable === 2 ? null : t2Decision
      const table2BoardEntryIndex = primaryHoldsTable === 2 ? newBoardEntryIndex : t2BoardEntryIndex

      Streamlit.setComponentValue({ 
        type: "continue_street", 
        street, 
        table_id: primaryHoldsTable,
        show_second_table: showSecondTable,
        active_table: activeTable,
        primary_holds_table: primaryHoldsTable,
        table1_game_state: table1GameState,
        table1_step: table1Step,
        table1_decision: table1Decision,
        table1_board_entry_index: table1BoardEntryIndex,
        table2_game_state: table2GameState,
        table2_step: table2Step,
        table2_decision: table2Decision,
        table2_board_entry_index: table2BoardEntryIndex,
      })
    },
    [decision, gameState, activeTable, primaryHoldsTable, showSecondTable, t2GameState, t2Step, t2Decision]
  )

  // ---- Preflop submit (skip board) ----
  const submitPreflop = useCallback(() => {
    submitDecisionRequest()
    setStep("showing_decision")
  }, [submitDecisionRequest])

  // ---- Postflop submit ----
  const submitPostflop = useCallback(() => {
    submitDecisionRequest()
    setStep("showing_decision")
  }, [submitDecisionRequest])

  // ---- Select villain type and auto-submit ----
  const selectVillainType = useCallback(
    (vt: string) => {
      setGameState((s) => ({ ...s, villain_type: vt }))
      // Always auto-submit after villain type (last step for both streets)
      setStep("ready")
    },
    []
  )

  // ---- Auto-submit when step is "ready" ----
  useEffect(() => {
    if (step === "ready") {
      submitDecisionRequest()
      setStep("showing_decision")
    }
  }, [step, submitDecisionRequest])

  // ---- Select board texture ----
  const selectBoardTexture = useCallback((bt: string) => {
    setGameState((s) => ({ ...s, board_texture: bt }))
    setStep("hand_strength")
  }, [])

  // ---- Select hand strength → villain type ----
  const selectHandStrength = useCallback(
    (hs: string) => {
      setGameState((s) => ({ ...s, hand_strength: hs }))
      setStep("villain_type")
    },
    []
  )

  // ==========================================================================
  // KEYBOARD HANDLER
  // ==========================================================================

  useEffect(() => {
    if (!keyboardActive) return

    const handleKeyDown = (e: KeyboardEvent) => {
      // =====================================================================
      // TWO-TABLE MODE: Tab switches tables (works in two_table mode OR when second table shown)
      // =====================================================================
      if (e.key === "Tab" && (mode === "two_table" || showSecondTable)) {
        e.preventDefault()
        switchTable()
        return
      }

      const key = e.key.toLowerCase()

      // Esc always works, even from input fields
      if (key === "escape") {
        e.preventDefault()
        // If in an input field, just blur it
        if (e.target instanceof HTMLInputElement) {
          (e.target as HTMLInputElement).blur()
          return
        }
        // From outcome select: go back to decision
        if (step === "outcome_select") {
          setStep("showing_decision")
          return
        }
        // From decision screen: Escape does nothing - use the action buttons
        if (step === "showing_decision") {
          return
        }
        goBack()
        return
      }

      // All other keys: skip if in an input field
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return

      // Bluff choice: 1 = BET, 2 = CHECK (when two-option display is showing)
      if (step === "showing_decision" && decision?.alternative) {
        if (key === "1") {
          e.preventDefault()
          setChosenBluffAction("BET")
          setDecision({ ...decision, alternative: undefined })
          setStep("outcome_select")
          return
        }
        if (key === "2") {
          e.preventDefault()
          setChosenBluffAction("CHECK")
          setDecision({ ...decision, alternative: undefined })
          setStep("outcome_select")
          return
        }
      }

      if ((key === "n" || key === " ") && step === "showing_decision") {
        e.preventDefault()
        if (decision) {
          const d = decision.display.toUpperCase()
          if (d.includes("FOLD")) {
            sendHandComplete("folded")
          } else {
            setStep("outcome_select")
          }
        } else {
          sendNewHand()
        }
        return
      }

      if (step === "outcome_select" && "123".includes(key)) {
        e.preventDefault()
        if (key === "1") sendHandComplete("won")
        else if (key === "2") sendHandComplete("lost")
        else if (key === "3") sendHandComplete("folded")
        return
      }

      // Position step
      if (step === "position" && "123456".includes(key)) {
        e.preventDefault()
        selectPosition(POSITIONS[parseInt(key) - 1].id)
        return
      }

      // Card rank steps
      if (
        (step === "card1_rank" || step === "card2_rank" || step === "board_rank") &&
        "akqjt98765432".includes(key)
      ) {
        e.preventDefault()
        const rank = key === "t" ? "T" : key.toUpperCase()
        selectRank(rank)
        return
      }

      // Card suit steps
      if ((step === "card1_suit" || step === "card2_suit" || step === "board_suit") && "shdc".includes(key)) {
        e.preventDefault()
        selectSuit(key)
        return
      }

      // Action step
      if (step === "action") {
        const actions = gameState.street === "preflop" ? PREFLOP_ACTIONS_INITIAL : POSTFLOP_ACTIONS_INITIAL
        const action = actions.find((a) => a.key === key)
        if (action) {
          e.preventDefault()
          selectAction(action.id, action.needsAmount || false, action.needsCount)
          return
        }
      }

      // Villain type step
      if (step === "villain_type" && "123".includes(key)) {
        e.preventDefault()
        const vt = VILLAIN_TYPES[parseInt(key) - 1]
        if (vt) selectVillainType(vt.id)
        return
      }

      // Limper count quick select (1-5)
      if (step === "limper_count" && "12345".includes(key)) {
        e.preventDefault()
        setAmountStr(key)
        return
      }

      // Enter to confirm amount/pot/limper count
      if (key === "enter") {
        e.preventDefault()
        if (step === "amount") confirmAmount()
        if (step === "pot_size") confirmPotSize()
        if (step === "limper_count") confirmLimperCount()
        return
      }

      // Showing decision - continue to flop/turn/river, they raised me, or they bet
      if (step === "showing_decision" && decision) {
        const d = decision.display.toUpperCase()
        const isAllIn = d.includes("ALL-IN") || d.includes("ALL IN")
        const isAggressive = !isAllIn && ["RAISE", "BET", "RE-RAISE", "3-BET", "4-BET", "ISO"].some(
          (a) => d.includes(a)
        )
        const isCheck = d.includes("CHECK")
        const isFold = d.includes("FOLD")
        const handOver = isFold || isAllIn

        if (key === "r" && isAggressive) {
          e.preventDefault()
          theyRaisedMe()
          return
        }
        if (key === "b" && isCheck && gameState.street !== "preflop") {
          e.preventDefault()
          theyBet()
          return
        }
        if (key === "1" && !handOver && gameState.street === "preflop") {
          e.preventDefault()
          continueToStreet("flop")
          return
        }
        if (key === "2" && !handOver && gameState.street === "flop") {
          e.preventDefault()
          continueToStreet("turn")
          return
        }
        if (key === "3" && !handOver && gameState.street === "turn") {
          e.preventDefault()
          continueToStreet("river")
          return
        }
      }
    }

    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [
    keyboardActive, step, gameState.street, pendingRank, decision, mode, showSecondTable,
    selectPosition, selectRank, selectSuit, selectAction,
    confirmAmount, confirmLimperCount, confirmPotSize, goBack, sendNewHand, sendHandComplete, continueToStreet, theyRaisedMe, theyBet,
    switchTable, chosenBluffAction,
  ])

  // ==========================================================================
  // STYLES
  // ==========================================================================

  // Dynamic accent color for two-table mode or when second table is shown
  const currentAccent = (mode === "two_table" || showSecondTable) ? TABLE_COLORS[activeTable].accent : "#4BA3FF"

  const theme = {
    bg: "#0A0A12",
    panel: "#0F0F1A",
    border: "rgba(255,255,255,0.08)",
    borderLight: "rgba(255,255,255,0.12)",
    text: "rgba(255,255,255,0.90)",
    textMuted: "rgba(255,255,255,0.45)",
    textDim: "rgba(255,255,255,0.25)",
    accent: currentAccent,  // CHANGED: Dynamic based on active table
    green: "#00C853",
    amber: "#FFB300",
    red: "#FF4B5C",
    mono: "'JetBrains Mono', 'Fira Code', monospace",
    sans: "'Inter', -apple-system, sans-serif",
  }

  const S: Record<string, React.CSSProperties> = {
    container: {
      background: theme.bg,
      borderRadius: 12,
      padding: "20px 24px",
      color: theme.text,
      fontFamily: theme.sans,
      position: "relative",
      outline: "none",
    },
    header: {
      display: "flex",
      justifyContent: "space-between",
      alignItems: "center",
      marginBottom: 16,
      paddingBottom: 12,
      borderBottom: `1px solid ${theme.border}`,
    },
    sectionLabel: {
      fontSize: 11,
      fontWeight: 600,
      textTransform: "uppercase" as const,
      letterSpacing: "0.08em",
      color: theme.textMuted,
      marginBottom: 8,
      marginTop: 16,
    },
    prompt: {
      background: "rgba(255,255,255,0.03)",
      borderRadius: 8,
      padding: "10px 14px",
      fontSize: 13,
      fontFamily: theme.mono,
      color: theme.textMuted,
      marginBottom: 16,
      display: "flex",
      alignItems: "center",
      gap: 8,
    },
    row: {
      display: "flex",
      gap: 8,
      flexWrap: "wrap" as const,
    },
    btn: {
      padding: "10px 16px",
      borderRadius: 8,
      border: `1px solid ${theme.borderLight}`,
      background: "rgba(255,255,255,0.03)",
      color: "rgba(255,255,255,0.65)",
      fontSize: 13,
      fontWeight: 600,
      fontFamily: theme.mono,
      cursor: "pointer",
      transition: "all 0.12s ease",
      position: "relative" as const,
      textAlign: "center" as const,
    },
    btnActive: {
      border: `2px solid ${theme.accent}`,
      background: mode === "two_table" && activeTable === 2 
        ? "rgba(255, 179, 0, 0.1)" 
        : "rgba(75, 163, 255, 0.1)",
      color: theme.accent,
    },
    hint: {
      position: "absolute" as const,
      top: 3,
      right: 5,
      fontSize: 11,
      fontWeight: 600,
      color: "rgba(255,255,255,0.45)",
      fontFamily: theme.mono,
    },
    card: {
      width: 56,
      height: 78,
      borderRadius: 10,
      display: "flex",
      flexDirection: "column" as const,
      alignItems: "center",
      justifyContent: "center",
      fontFamily: theme.mono,
      transition: "all 0.15s ease",
      cursor: "pointer",
    },
    input: {
      background: "rgba(255,255,255,0.06)",
      border: `1px solid ${theme.borderLight}`,
      borderRadius: 8,
      padding: "10px 14px",
      color: "#fff",
      fontSize: 16,
      fontFamily: theme.mono,
      outline: "none",
      width: 120,
    },
  }

  // ==========================================================================
  // BREADCRUMB
  // ==========================================================================

  const renderBreadcrumb = () => {
    // Helper to format card display with colored suit
    const cardStr = (c: CardData | null) => {
      if (!c) return null
      return { rank: c.rank, suit: suitSymbol(c.suit), color: suitColor(c.suit) }
    }

    // Helper to get readable action label
    const actionLabel = () => {
      const a = gameState.action_facing
      if (a === "none" && gameState.street === "preflop") return "Open"
      if (a === "none") return "Checked"
      if (a === "limp") return "Limp"
      if (a === "raise") return gameState.facing_bet ? `$${gameState.facing_bet} Raise` : "Raise"
      if (a === "3bet") return gameState.facing_bet ? `$${gameState.facing_bet} 3-Bet` : "3-Bet"
      if (a === "4bet") return gameState.facing_bet ? `$${gameState.facing_bet} 4-Bet` : "4-Bet"
      if (a === "bet") return gameState.facing_bet ? `$${gameState.facing_bet} Bet` : "Bet"
      if (a === "check_raise") return gameState.facing_bet ? `$${gameState.facing_bet} CR` : "Check-Raise"
      return a
    }

    // Helper to get street label
    const streetLabel = () => {
      const s = gameState.street
      if (s === "preflop") return null
      return s.charAt(0).toUpperCase() + s.slice(1)
    }

    // Build segments
    type Segment = {
      id: string
      done: boolean
      current: boolean
      render: () => React.ReactNode
    }

    const segments: Segment[] = []

    // Position
    const posActive = step === "position"
    const posDone = !!gameState.position
    segments.push({
      id: "pos",
      done: posDone,
      current: posActive,
      render: () => posDone ? <strong>{gameState.position}</strong> : <>Position</>,
    })

    // Hand (combined card1 + card2)
    const c1 = cardStr(gameState.card1)
    const c2 = cardStr(gameState.card2)
    const handActive = step === "card1_rank" || step === "card1_suit" || step === "card2_rank" || step === "card2_suit"
    const handDone = !!gameState.card1 && !!gameState.card2
    segments.push({
      id: "hand",
      done: handDone,
      current: handActive,
      render: () => {
        if (handDone && c1 && c2) {
          return (
            <span style={{ display: "inline-flex", gap: 3, alignItems: "center" }}>
              <span style={{ color: c1.color, fontWeight: 700 }}>{c1.rank}{c1.suit}</span>
              <span style={{ color: c2.color, fontWeight: 700 }}>{c2.rank}{c2.suit}</span>
            </span>
          )
        }
        if (c1 && !c2) {
          return (
            <span style={{ display: "inline-flex", gap: 3, alignItems: "center" }}>
              <span style={{ color: c1.color, fontWeight: 700 }}>{c1.rank}{c1.suit}</span>
              <span style={{ opacity: 0.4 }}>__</span>
            </span>
          )
        }
        return <>Hand</>
      },
    })

    // Action
    const actionActive = step === "action" || step === "amount" || step === "limper_count"
    const actionDone = !posActive && !handActive && !actionActive &&
      (step === "villain_type" || step === "ready" || step === "showing_decision" ||
       step === "board_rank" || step === "board_suit" || step === "pot_size" ||
       step === "board_texture" || step === "hand_strength")
    segments.push({
      id: "action",
      done: actionDone,
      current: actionActive,
      render: () => actionDone ? <>{actionLabel()}</> : <>Action</>,
    })

    // Board + Pot (only on postflop)
    if (gameState.street !== "preflop") {
      const boardActive = step === "board_rank" || step === "board_suit" || step === "pot_size"
      const boardDone = step === "action" || step === "amount" || step === "limper_count" || step === "villain_type" ||
        step === "ready" || step === "showing_decision" ||
        step === "board_texture" || step === "hand_strength"
      const sl = streetLabel()
      segments.push({
        id: "board",
        done: boardDone,
        current: boardActive,
        render: () => {
          if (boardDone) {
            // Show board cards inline
            const filledCards = gameState.board_cards.filter(c => c !== null) as CardData[]
            return (
              <span style={{ display: "inline-flex", gap: 2, alignItems: "center" }}>
                <span style={{ opacity: 0.5, marginRight: 2 }}>{sl}</span>
                {filledCards.map((c, i) => (
                  <span key={i} style={{ color: suitColor(c.suit), fontWeight: 600 }}>
                    {c.rank}{suitSymbol(c.suit)}
                  </span>
                ))}
              </span>
            )
          }
          return <>{sl || "Board"}</>
        },
      })
    }

    // Decision
    const decActive = step === "showing_decision"
    segments.push({
      id: "decision",
      done: decActive,
      current: decActive,
      render: () => <>Decision</>,
    })

    // Dynamic accent RGB for breadcrumb styling
    const accentRgb = mode === "two_table" && activeTable === 2 ? "255,179,0" : "75,163,255"

    return (
      <div style={{
        display: "flex",
        gap: 6,
        alignItems: "center",
        marginBottom: 16,
        flexWrap: "wrap",
        padding: "8px 0",
      }}>
        {segments.map((seg, i) => (
          <React.Fragment key={seg.id}>
            {i > 0 && (
              <span style={{
                color: "rgba(255,255,255,0.15)",
                fontSize: 12,
                margin: "0 2px",
                fontWeight: 300,
              }}>›</span>
            )}
            <span
              style={{
                fontSize: 13,
                fontWeight: seg.current ? 700 : seg.done ? 600 : 400,
                fontFamily: theme.mono,
                color: seg.done
                  ? theme.green
                  : seg.current
                  ? "#fff"
                  : "rgba(255,255,255,0.25)",
                padding: "4px 10px",
                borderRadius: 6,
                background: seg.current
                  ? `rgba(${accentRgb},0.12)`
                  : "transparent",
                border: seg.current
                  ? `1px solid rgba(${accentRgb},0.2)`
                  : "1px solid transparent",
                transition: "all 0.15s ease",
              }}
            >
              {seg.render()}
            </span>
          </React.Fragment>
        ))}
      </div>
    )
  }

  // ==========================================================================
  // CARD DISPLAY
  // ==========================================================================

  const renderCardSlot = (card: CardData | null, label: string, isActive: boolean) => {
    const filled = !!card
    // Dynamic accent RGB for card styling
    const accentRgb = mode === "two_table" && activeTable === 2 ? "255,179,0" : "75,163,255"
    return (
      <div
        style={{
          ...S.card,
          border: filled
            ? `1.5px solid rgba(${accentRgb},0.3)`
            : isActive
            ? `1.5px solid ${theme.accent}`
            : `1.5px dashed ${theme.borderLight}`,
          background: filled
            ? "linear-gradient(145deg, #1a1a2e, #0f0f1a)"
            : "rgba(255,255,255,0.02)",
          boxShadow: filled ? `0 0 16px rgba(${accentRgb},0.08)` : "none",
        }}
      >
        {filled ? (
          <>
            <span style={{ fontSize: 22, fontWeight: 700, color: "#fff" }}>{card!.rank}</span>
            <span style={{ fontSize: 20, color: suitColor(card!.suit) }}>{suitSymbol(card!.suit)}</span>
          </>
        ) : (
          <span style={{ fontSize: 12, color: isActive ? theme.accent : theme.textDim }}>
            {pendingRank && isActive ? pendingRank + "?" : label}
          </span>
        )}
      </div>
    )
  }

  // ==========================================================================
  // BLUFF CHOICE (two-option river barrel UI)
  // ==========================================================================

  const renderBluffChoice = () => {
    if (!decision || !decision.alternative) return null
    
    const alt = decision.alternative
    
    return (
      <div style={{ margin: "20px 0" }}>
        {/* Header */}
        <div style={{
          textAlign: "center",
          marginBottom: 16,
          padding: "10px 14px",
          background: "rgba(255,179,0,0.06)",
          border: "1px solid rgba(255,179,0,0.15)",
          borderRadius: 8,
        }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: theme.amber, marginBottom: 2 }}>
            ⚡ YOUR CALL
          </div>
          <div style={{ fontSize: 11, color: theme.textMuted }}>
            This spot is profitable long-term — but it's your choice
          </div>
        </div>

        {/* Two options side by side */}
        <div style={{ display: "flex", gap: 12 }}>
          {/* BET option (recommended) */}
          <button
            onClick={() => {
              setChosenBluffAction("BET")
              setDecision({ ...decision, alternative: undefined })
              setStep("outcome_select")
            }}
            style={{
              flex: 1,
              background: "rgba(0,200,83,0.06)",
              border: "2px solid rgba(0,200,83,0.4)",
              borderRadius: 12,
              padding: "16px 14px",
              cursor: "pointer",
              textAlign: "center",
              transition: "all 0.15s ease",
            }}
          >
            <div style={{ fontSize: 10, fontWeight: 700, color: theme.green, marginBottom: 6, letterSpacing: "0.08em" }}>
              ★ RECOMMENDED
            </div>
            <div style={{ fontSize: 22, fontWeight: 800, fontFamily: theme.mono, color: "#fff", marginBottom: 8 }}>
              {roundBetDisplay(decision.display)}
            </div>
            <div style={{ fontSize: 12, color: "rgba(255,255,255,0.7)", lineHeight: 1.5 }}>
              {decision.explanation}
            </div>
            {decision.calculation && (
              <div style={{ fontSize: 10, color: theme.textMuted, marginTop: 6, fontFamily: theme.mono }}>
                {roundCalculation(decision.calculation)}
              </div>
            )}
          </button>

          {/* CHECK option */}
          <button
            onClick={() => {
              setChosenBluffAction("CHECK")
              setDecision({ ...decision, alternative: undefined })
              setStep("outcome_select")
            }}
            style={{
              flex: 1,
              background: "rgba(255,255,255,0.02)",
              border: "1px solid rgba(255,255,255,0.12)",
              borderRadius: 12,
              padding: "16px 14px",
              cursor: "pointer",
              textAlign: "center",
              transition: "all 0.15s ease",
            }}
          >
            <div style={{ fontSize: 10, fontWeight: 700, color: theme.textDim, marginBottom: 6, letterSpacing: "0.08em" }}>
              SAFE OPTION
            </div>
            <div style={{ fontSize: 22, fontWeight: 800, fontFamily: theme.mono, color: "rgba(255,255,255,0.5)", marginBottom: 8 }}>
              {alt.display}
            </div>
            <div style={{ fontSize: 12, color: "rgba(255,255,255,0.45)", lineHeight: 1.5 }}>
              {alt.explanation}
            </div>
          </button>
        </div>

        {/* Keyboard hints */}
        {keyboardActive && (
          <div style={{
            marginTop: 10, textAlign: "center",
            fontSize: 11, color: theme.textDim, fontFamily: theme.mono,
          }}>
            Press <span style={{ color: "rgba(255,255,255,0.5)" }}>1</span> for BET ·
            <span style={{ color: "rgba(255,255,255,0.5)" }}> 2</span> for CHECK
          </div>
        )}
      </div>
    )
  }

  // ==========================================================================
  // DECISION BADGE
  // ==========================================================================

  const renderDecision = () => {
    if (!decision) return null

    // TWO-OPTION DISPLAY: River barrel choice
    if (decision.alternative && step === "showing_decision") {
      return renderBluffChoice()
    }

    const action = decision.action || decision.display
    let bg = "linear-gradient(135deg, #546E7A, #78909C)" // fold default
    let textColor = "#fff"
    let glow = "0 4px 20px rgba(84,110,122,0.2)"

    if (["RAISE", "BET", "RE-RAISE", "3-BET", "4-BET"].some((a) => decision.display.includes(a))) {
      bg = "linear-gradient(135deg, #00C853, #00E676)"
      textColor = "#000"
      glow = "0 4px 24px rgba(0,200,83,0.25)"
    } else if (["CALL", "CHECK"].some((a) => decision.display.includes(a))) {
      bg = "linear-gradient(135deg, #FFB300, #FFC107)"
      textColor = "#000"
      glow = "0 4px 24px rgba(255,179,0,0.25)"
    } else if (decision.display.includes("ALL-IN")) {
      bg = "linear-gradient(135deg, #D32F2F, #F44336)"
      textColor = "#fff"
      glow = "0 4px 24px rgba(211,47,47,0.25)"
    }

    // Show bluff indicator for auto-bluffs (probe, c-bet)
    const isAutoBluff = decision.bluff_context && decision.bluff_context.delivery === "auto"

    return (
      <div style={{ margin: "20px 0" }}>
        {/* Auto-bluff indicator */}
        {isAutoBluff && (
          <div style={{
            background: "rgba(255,179,0,0.08)",
            border: "1px solid rgba(255,179,0,0.2)",
            borderRadius: 8,
            padding: "8px 14px",
            marginBottom: 10,
            fontSize: 11,
            color: theme.amber,
            fontFamily: theme.mono,
            display: "flex",
            alignItems: "center",
            gap: 8,
          }}>
            <span>⚡</span>
            <span>Aggressive play — the math favors betting here</span>
          </div>
        )}

        <div
          style={{
            background: bg,
            borderRadius: 12,
            padding: "20px 24px",
            textAlign: "center",
            boxShadow: glow,
          }}
        >
          <div
            style={{
              fontSize: 30,
              fontWeight: 800,
              fontFamily: theme.mono,
              color: textColor,
              letterSpacing: "0.04em",
            }}
          >
            {roundBetDisplay(decision.display)}
          </div>
          {decision.explanation && (
            <div style={{ fontSize: 13, color: textColor, opacity: 0.8, marginTop: 6 }}>
              {humanizeExplanation(decision.explanation)}
            </div>
          )}
          {decision.calculation && (
            <div style={{ fontSize: 11, color: textColor, opacity: 0.6, marginTop: 4, fontFamily: theme.mono }}>
              {roundCalculation(decision.calculation)}
            </div>
          )}
        </div>

        {/* Post-decision actions */}
        {(() => {
          const d = decision?.display?.toUpperCase() || ""
          const isAllIn = d.includes("ALL-IN") || d.includes("ALL IN")
          const isAggressive = !isAllIn && ["RAISE", "BET", "RE-RAISE", "3-BET", "4-BET", "ISO"].some(
            (a) => d.includes(a)
          )
          const isCheck = d.includes("CHECK")
          const isFold = d.includes("FOLD")
          const handOver = isFold || isAllIn
          const accentRgb = mode === "two_table" && activeTable === 2 ? "255,179,0" : "75,163,255"
          const streetBtnStyle = {
            ...S.btn,
            flex: 1,
            background: `rgba(${accentRgb},0.08)`,
            borderColor: `rgba(${accentRgb},0.25)`,
            color: theme.accent,
          }

          return (
            <div>
              {/* Action buttons */}
              <div style={{ display: "flex", gap: 8, marginTop: 12, flexWrap: "wrap" }}>
                {/* Primary action: record result */}
                <button
                  onClick={() => {
                    if (isFold) {
                      sendHandComplete("folded")
                    } else {
                      setStep("outcome_select")
                    }
                  }}
                  style={{
                    ...S.btn,
                    flex: 1,
                    background: isFold
                      ? "rgba(255,255,255,0.06)"
                      : "linear-gradient(135deg, rgba(75,163,255,0.15), rgba(75,163,255,0.08))",
                    borderColor: isFold
                      ? "rgba(255,255,255,0.15)"
                      : "rgba(75,163,255,0.4)",
                    color: isFold ? "#fff" : theme.accent,
                    fontWeight: 700,
                  }}
                >
                  {keyboardActive && <span style={S.hint}>N</span>}
                  {isFold ? "Next Hand →" : "🏁 Hand Over — Record Result"}
                </button>

                {isAggressive && (
                  <button
                    onClick={theyRaisedMe}
                    style={{
                      ...S.btn,
                      flex: 1,
                      background: "rgba(255,179,0,0.08)",
                      borderColor: "rgba(255,179,0,0.25)",
                      color: theme.amber,
                    }}
                  >
                    {keyboardActive && <span style={S.hint}>R</span>}
                    They Raised Me
                  </button>
                )}

                {isCheck && gameState.street !== "preflop" && (
                  <button
                    onClick={theyBet}
                    style={{
                      ...S.btn,
                      flex: 1,
                      background: "rgba(255,179,0,0.08)",
                      borderColor: "rgba(255,179,0,0.25)",
                      color: theme.amber,
                    }}
                  >
                    {keyboardActive && <span style={S.hint}>B</span>}
                    They Bet
                  </button>
                )}

                {!handOver && gameState.street === "preflop" && (
                  <button onClick={() => continueToStreet("flop")} style={streetBtnStyle}>
                    {keyboardActive && <span style={S.hint}>1</span>}→ Flop
                  </button>
                )}
                {!handOver && gameState.street === "flop" && (
                  <button onClick={() => continueToStreet("turn")} style={streetBtnStyle}>
                    {keyboardActive && <span style={S.hint}>2</span>}→ Turn
                  </button>
                )}
                {!handOver && gameState.street === "turn" && (
                  <button onClick={() => continueToStreet("river")} style={streetBtnStyle}>
                    {keyboardActive && <span style={S.hint}>3</span>}→ River
                  </button>
                )}
              </div>

              {/* Helper text */}
              <div style={{
                marginTop: 12,
                padding: "8px 12px",
                background: "rgba(255,255,255,0.02)",
                borderRadius: 6,
                fontSize: 11,
                color: theme.textDim,
                textAlign: "center",
              }}>
                {handOver ? (
                  <>Press <span style={{ color: theme.textMuted, fontWeight: 600 }}>N</span> to record and start next hand</>
                ) : (
                  <>Continue on the next street, or press <span style={{ color: theme.textMuted, fontWeight: 600 }}>N</span> when the hand is over</>
                )}
              </div>
            </div>
          )
        })()}
      </div>
    )
  }

  // ==========================================================================
  // RANK GRID
  // ==========================================================================

  const renderRankGrid = () => {
    // Split into face cards (top row) and number cards (bottom rows)
    const faceCards = RANKS.filter(r => r.isFace)
    const numberCards = RANKS.filter(r => !r.isFace)
    
    return (
      <div>
        {/* Face cards - premium display */}
        <div style={{ 
          display: "grid", 
          gridTemplateColumns: "repeat(5, 1fr)", 
          gap: 8,
          marginBottom: 10,
        }}>
          {faceCards.map((r) => (
            <button
              key={r.rank}
              onClick={() => selectRank(r.rank)}
              style={{
                ...S.btn,
                padding: "12px 8px",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: 2,
                background: "rgba(255,255,255,0.04)",
                borderColor: "rgba(255,255,255,0.15)",
              }}
            >
              {keyboardActive && (
                <span style={S.hint}>{r.rank === "T" ? "t" : r.rank.toLowerCase()}</span>
              )}
              <span style={{ 
                fontSize: 20, 
                fontWeight: 800,
                color: "#fff",
              }}>
                {r.display}
              </span>
              <span style={{ 
                fontSize: 9, 
                color: theme.textMuted, 
                fontWeight: 500,
                letterSpacing: "0.02em",
              }}>
                {r.fullName}
              </span>
            </button>
          ))}
        </div>
        
        {/* Number cards - compact grid */}
        <div style={{ 
          display: "grid", 
          gridTemplateColumns: "repeat(8, 1fr)", 
          gap: 6,
        }}>
          {numberCards.map((r) => (
            <button
              key={r.rank}
              onClick={() => selectRank(r.rank)}
              style={{
                ...S.btn,
                padding: "10px 0",
                fontSize: 16,
                fontWeight: 700,
              }}
            >
              {keyboardActive && (
                <span style={S.hint}>{r.rank}</span>
              )}
              {r.display}
            </button>
          ))}
        </div>
      </div>
    )
  }

  // ==========================================================================
  // SUIT SELECTOR
  // ==========================================================================

  const renderSuitSelector = () => {
    return (
      <div style={{ display: "flex", gap: 8, justifyContent: "center", marginTop: 8 }}>
        {SUITS.map((suit) => {
          const used = pendingRank
            ? isCardUsed(pendingRank, suit.key, gameState.card1, gameState.card2, gameState.board_cards)
            : false
          return (
            <button
              key={suit.key}
              onClick={() => !used && selectSuit(suit.key)}
              style={{
                ...S.btn,
                padding: "12px 20px",
                fontSize: 24,
                color: suit.color,
                opacity: used ? 0.2 : 1,
                cursor: used ? "not-allowed" : "pointer",
              }}
            >
              {keyboardActive && <span style={S.hint}>{suit.key}</span>}
              {suit.symbol}
            </button>
          )
        })}
      </div>
    )
  }

  // ==========================================================================
  // PROMPT TEXT
  // ==========================================================================

  const getPrompt = (): string => {
    switch (step) {
      case "position":
        return keyboardActive ? "Press 1-6 for your seat..." : "Where are you sitting?"
      case "card1_rank":
        return keyboardActive ? "First card — type rank (a,k,q,j,t,9...)..." : "Your first card rank..."
      case "card1_suit":
        return `${pendingRank} — pick the suit...`
      case "card2_rank":
        return keyboardActive ? "Second card — type rank..." : "Your second card rank..."
      case "card2_suit":
        return `${pendingRank} — pick the suit...`
      case "action":
        return gameState.street === "preflop" ? "What happened before your turn?" : "What happened on this street?"
      case "amount":
        return `${amountLabel} Type amount, then Enter...`
      case "limper_count":
        return "How many players limped in? Enter..."
      case "board_rank": {
        const needed = requiredBoardCards(gameState.street)
        const have = gameState.board_cards.filter((c) => c !== null).length
        return `Board card ${have + 1} of ${needed} — type rank...`
      }
      case "board_suit":
        return `${pendingRank} — now pick the suit...`
      case "pot_size":
        return "How much is in the pot? Type amount, then Enter..."
      case "board_texture":
        return "Select board texture..."
      case "hand_strength":
        return "What's your hand strength?"
      case "villain_type":
        return keyboardActive ? "Press 1 if unsure, 2 for weak player, 3 for good player..." : "What type of player are you against? Pick 'Not Sure' if unsure."
      case "ready":
        return "Calculating..."
      case "showing_decision": {
              if (!decision) return "Calculating..."
              const d2 = decision.display.toUpperCase()
              const isAllIn2 = d2.includes("ALL-IN") || d2.includes("ALL IN")
              const isAgg = !isAllIn2 && ["RAISE", "BET", "RE-RAISE", "3-BET", "4-BET", "ISO"].some(
                (a) => d2.includes(a)
              )
              const isChk = d2.includes("CHECK")
              const isFld = d2.includes("FOLD")
              const isCall = d2.includes("CALL")
              
              if (isFld || isAllIn2) {
                return "Hand complete · Press N to start new hand"
              }
              if (isAgg) {
                return "Press R if they re-raised · N for new hand · or continue to next street →"
              }
              if (isChk && gameState.street !== "preflop") {
                return "Press B if they bet · N for new hand · or continue to next street →"
              }
              if (isCall) {
                return "Press N for new hand · or continue to next street →"
              }
              return "Press N for new hand · or continue to next street →"
            }
            case "outcome_select":
              return keyboardActive ? "Press 1 Won · 2 Lost · 3 Folded" : "How did this hand end?"
            default:
              return ""
          }
        }

  // ==========================================================================
  // TWO-TABLE MODE: INACTIVE PANEL RENDER (PREMIUM VERSION)
  // ==========================================================================

  const renderInactivePanel = (
    tableNum: 1 | 2,
    gs: GameState,
    tableStep: InputStep,
    tableDecision: DecisionResult | null
  ) => {
    const colors = TABLE_COLORS[tableNum]
    const accentRgb = tableNum === 1 ? "75,163,255" : "255,179,0"

    // Render mini card graphic
    const renderMiniCard = (c: CardData | null) => {
      if (!c) return null
      return (
        <div
          style={{
            width: 36,
            height: 50,
            borderRadius: 6,
            background: "linear-gradient(145deg, #1a1a2e, #12121f)",
            border: `1px solid rgba(${accentRgb}, 0.25)`,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            boxShadow: "0 2px 8px rgba(0,0,0,0.3)",
          }}
        >
          <span style={{ fontSize: 14, fontWeight: 700, color: "#fff", lineHeight: 1 }}>
            {c.rank}
          </span>
          <span style={{ fontSize: 14, color: suitColor(c.suit), lineHeight: 1 }}>
            {suitSymbol(c.suit)}
          </span>
        </div>
      )
    }

    // Get contextual step label with street awareness
    const getStepLabel = (): string => {
      if (tableStep === "showing_decision") return ""
      if (tableStep === "ready") return "Calculating..."
      if (tableStep === "position") return "Select position"
      if (tableStep === "card1_rank" || tableStep === "card1_suit") return "Card 1"
      if (tableStep === "card2_rank" || tableStep === "card2_suit") return "Card 2"
      if (tableStep === "action") return gs.street === "preflop" ? "Preflop action" : `${gs.street.charAt(0).toUpperCase() + gs.street.slice(1)} action`
      if (tableStep === "amount") return "Enter amount"
      if (tableStep === "limper_count") return "Limper count"
      if (tableStep === "villain_type") return "Villain type"
      if (tableStep === "board_rank" || tableStep === "board_suit") {
        const needed = requiredBoardCards(gs.street)
        const have = gs.board_cards.filter((c) => c !== null).length
        return `${gs.street.charAt(0).toUpperCase() + gs.street.slice(1)} · Card ${have + 1}/${needed}`
      }
      if (tableStep === "pot_size") return `${gs.street.charAt(0).toUpperCase() + gs.street.slice(1)} · Pot size`
      if (tableStep === "board_texture") return "Board texture"
      if (tableStep === "hand_strength") return "Hand strength"
      return ""
    }

    // Progress percentage
    const getProgressPercent = (): number => {
      if (tableStep === "showing_decision") return 100
      if (tableStep === "ready") return 95
      if (tableStep === "position") return 8
      if (tableStep === "card1_rank" || tableStep === "card1_suit") return 20
      if (tableStep === "card2_rank" || tableStep === "card2_suit") return 35
      if (tableStep === "action") return gs.street === "preflop" ? 50 : 70
      if (tableStep === "amount" || tableStep === "limper_count") return gs.street === "preflop" ? 60 : 75
      if (tableStep === "villain_type") return 85
      if (tableStep === "board_rank" || tableStep === "board_suit") return 55
      if (tableStep === "pot_size") return 65
      if (tableStep === "board_texture") return 72
      if (tableStep === "hand_strength") return 78
      return 0
    }

    // Render mini decision badge
    const renderMiniDecision = () => {
      if (!tableDecision) return null
      const d = tableDecision.display.toUpperCase()
      let bg = "linear-gradient(135deg, #546E7A, #78909C)"
      let textCol = "#fff"
      if (["RAISE", "BET", "RE-RAISE", "3-BET", "4-BET"].some((a) => d.includes(a))) {
        bg = "linear-gradient(135deg, #00C853, #00E676)"
        textCol = "#000"
      } else if (["CALL", "CHECK"].some((a) => d.includes(a))) {
        bg = "linear-gradient(135deg, #FFB300, #FFC107)"
        textCol = "#000"
      } else if (d.includes("ALL-IN")) {
        bg = "linear-gradient(135deg, #D32F2F, #F44336)"
        textCol = "#fff"
      }

      return (
        <div
          style={{
            background: bg,
            borderRadius: 8,
            padding: "10px 14px",
            textAlign: "center",
            boxShadow: "0 2px 12px rgba(0,0,0,0.25)",
          }}
        >
          <div
            style={{
              fontSize: 16,
              fontWeight: 800,
              fontFamily: theme.mono,
              color: textCol,
              letterSpacing: "0.02em",
            }}
          >
            {roundBetDisplay(tableDecision.display)}
          </div>
        </div>
      )
    }

    const progress = getProgressPercent()
    const stepLabel = getStepLabel()

    return (
      <div
        onClick={switchTable}
        style={{
          flex: 1,
          border: colors.borderInactive,
          borderRadius: 12,
          padding: 16,
          background: "rgba(255,255,255,0.015)",
          cursor: "pointer",
          transition: "all 0.2s ease",
          position: "relative",
          overflow: "hidden",
          minHeight: 200,
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = "rgba(255,255,255,0.035)"
          e.currentTarget.style.borderColor = colors.accent
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = "rgba(255,255,255,0.015)"
          e.currentTarget.style.borderColor = tableNum === 1
            ? "rgba(75, 163, 255, 0.2)"
            : "rgba(255, 179, 0, 0.2)"
        }}
      >
        {/* Header */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: 14,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span
              style={{
                width: 6,
                height: 6,
                borderRadius: "50%",
                background: colors.accent,
                opacity: 0.6,
              }}
            />
            <span
              style={{
                fontSize: 10,
                fontWeight: 700,
                letterSpacing: "0.1em",
                color: colors.accent,
                fontFamily: theme.mono,
                textTransform: "uppercase",
              }}
            >
              {colors.name}
            </span>
          </div>
          <span
            style={{
              fontSize: 9,
              color: "rgba(255,255,255,0.35)",
              fontFamily: theme.mono,
              padding: "3px 8px",
              background: "rgba(255,255,255,0.05)",
              borderRadius: 4,
              letterSpacing: "0.02em",
            }}
          >
            Tab to switch
          </span>
        </div>

        {/* Content */}
        {gs.position ? (
          <>
            {/* Position Badge */}
            <div
              style={{
                display: "inline-block",
                background: `rgba(${accentRgb}, 0.12)`,
                border: `1px solid rgba(${accentRgb}, 0.25)`,
                color: colors.accent,
                padding: "5px 12px",
                borderRadius: 6,
                fontSize: 12,
                fontWeight: 700,
                fontFamily: theme.mono,
                marginBottom: 12,
                letterSpacing: "0.03em",
              }}
            >
              {gs.position}
            </div>

            {/* Hole Cards as Mini Graphics */}
            {gs.card1 && (
              <div style={{ display: "flex", gap: 6, marginBottom: 14 }}>
                {renderMiniCard(gs.card1)}
                {renderMiniCard(gs.card2)}
              </div>
            )}

            {/* Board Cards (postflop) */}
            {gs.street !== "preflop" && gs.board_cards.some((c) => c !== null) && (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  marginBottom: 14,
                  padding: "8px 10px",
                  background: "rgba(255,255,255,0.03)",
                  borderRadius: 6,
                  borderLeft: `2px solid rgba(${accentRgb}, 0.4)`,
                }}
              >
                <span
                  style={{
                    color: colors.accent,
                    fontSize: 9,
                    fontWeight: 700,
                    textTransform: "uppercase",
                    letterSpacing: "0.08em",
                    opacity: 0.8,
                  }}
                >
                  {gs.street}
                </span>
                <div style={{ display: "flex", gap: 4 }}>
                  {gs.board_cards
                    .filter((c) => c !== null)
                    .map((c, i) => (
                      <span
                        key={i}
                        style={{
                          color: suitColor((c as CardData).suit),
                          fontWeight: 700,
                          fontSize: 13,
                          fontFamily: theme.mono,
                        }}
                      >
                        {(c as CardData).rank}{suitSymbol((c as CardData).suit)}
                      </span>
                    ))}
                </div>
              </div>
            )}

            {/* Decision or Progress */}
            {tableStep === "showing_decision" ? (
              renderMiniDecision()
            ) : (
              <div style={{ marginTop: "auto" }}>
                {/* Progress Bar */}
                <div
                  style={{
                    height: 3,
                    background: "rgba(255,255,255,0.06)",
                    borderRadius: 2,
                    overflow: "hidden",
                    marginBottom: 10,
                  }}
                >
                  <div
                    style={{
                      height: "100%",
                      width: `${progress}%`,
                      background: `linear-gradient(90deg, rgba(${accentRgb}, 0.5), rgba(${accentRgb}, 0.8))`,
                      borderRadius: 2,
                      transition: "width 0.3s ease",
                    }}
                  />
                </div>
                {/* Step Label */}
                <div
                  style={{
                    fontSize: 11,
                    color: "rgba(255,255,255,0.5)",
                    fontFamily: theme.mono,
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                  }}
                >
                  <span
                    style={{
                      width: 4,
                      height: 4,
                      borderRadius: "50%",
                      background: colors.accent,
                      opacity: 0.7,
                    }}
                  />
                  {stepLabel}
                </div>
              </div>
            )}
          </>
        ) : (
          /* Empty State */
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              height: 120,
              opacity: 0.4,
            }}
          >
            <div
              style={{
                width: 32,
                height: 44,
                borderRadius: 6,
                border: `1.5px dashed rgba(${accentRgb}, 0.3)`,
                marginBottom: 10,
              }}
            />
            <span
              style={{
                fontSize: 11,
                color: theme.textDim,
                fontFamily: theme.mono,
              }}
            >
              Waiting for hand...
            </span>
          </div>
        )}
      </div>
    )
  }

  // ==========================================================================
  // RENDER
  // ==========================================================================

  // =========================================================================
  // TWO-TABLE MODE RENDER (when mode === "two_table" OR showSecondTable is true)
  // =========================================================================
  if (mode === "two_table" || showSecondTable) {
    return (
      <div ref={containerRef} style={{ ...S.container, padding: "16px 20px" }} tabIndex={0}>
        <style>{`
          @keyframes pulse {
            0%, 100% { opacity: 0.4; transform: scale(1); }
            50% { opacity: 1; transform: scale(1.2); }
          }
          button:hover {
            filter: brightness(1.15);
          }
        `}</style>

        {/* SHARED HEADER */}
        <div style={S.header}>
          <div style={{ fontSize: 14, fontWeight: 700, letterSpacing: "0.03em", fontFamily: theme.mono }}>
            NAMELESS POKER
          </div>
          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            {/* Close Table 2 button */}
            <button
              onClick={handleCloseTable2}
              style={{
                background: "rgba(255,75,92,0.08)",
                border: "1px solid rgba(255,75,92,0.2)",
                borderRadius: 6,
                padding: "4px 10px",
                color: theme.red,
                fontSize: 11,
                fontFamily: theme.mono,
                cursor: "pointer",
                transition: "all 0.15s ease",
                display: "flex",
                alignItems: "center",
                gap: 4,
              }}
            >
              <span style={{ fontSize: 10 }}>✕</span>
              Close T2
            </button>
            <button
              onClick={() => setShowOverlay(!showOverlay)}
              style={{
                background: "none",
                border: `1px solid ${theme.borderLight}`,
                borderRadius: 6,
                padding: "3px 8px",
                color: theme.textMuted,
                fontSize: 11,
                fontFamily: theme.mono,
                cursor: "pointer",
              }}
            >
              ?
            </button>
            <span
              style={{
                fontSize: 11,
                color: theme.textDim,
                fontFamily: theme.mono,
              }}
            >
              {stakes} · {Math.round(stackSize / bbSize)}BB
            </span>
          </div>
        </div>

        {/* SHORTCUT OVERLAY */}
        {showOverlay && (
          <div
            style={{
              position: "absolute",
              top: 50,
              right: 24,
              background: "#1a1a2e",
              border: `1px solid ${theme.borderLight}`,
              borderRadius: 10,
              padding: 16,
              zIndex: 100,
              width: 260,
              boxShadow: "0 8px 32px rgba(0,0,0,0.5)",
            }}
          >
            <div style={{ fontSize: 12, fontWeight: 700, color: theme.text, marginBottom: 10 }}>
              KEYBOARD SHORTCUTS
            </div>
            {[
              ["Tab", "Switch table"],
              ["1-6", "Position (UTG→BB)"],
              ["a,k,q,j,t,9-2", "Card rank"],
              ["s, h, d, c", "Suit (♠♥♦♣)"],
              ["f", "Fold to me / Check to me"],
              ["l", "Limper(s)"],
              ["r", "Raise / Facing bet"],
              ["e", "3-Bet"],
              ["Esc", "Undo / Reset"],
              ["Enter", "Confirm amount"],
              ["N / Space", "New hand"],
              ["1,2,3", "Continue → Flop/Turn/River"],
            ].map(([key, desc]) => (
              <div
                key={key}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  fontSize: 11,
                  fontFamily: theme.mono,
                  padding: "3px 0",
                  color: theme.textMuted,
                }}
              >
                <span style={{ color: "rgba(255,255,255,0.7)" }}>{key}</span>
                <span>{desc}</span>
              </div>
            ))}
            <button
              onClick={() => setShowOverlay(false)}
              style={{
                ...S.btn,
                width: "100%",
                marginTop: 10,
                padding: "6px",
                fontSize: 11,
              }}
            >
              Close
            </button>
          </div>
        )}

        {/* TWO PANELS SIDE BY SIDE */}
        <div style={{ display: "flex", gap: 12 }}>
          {/* Left panel: Table 1 */}
          {activeTable === 1 ? (
            <div
              style={{
                flex: 1,
                border: TABLE_COLORS[1].borderActive,
                borderRadius: 12,
                padding: 16,
                background: TABLE_COLORS[1].bgActive,
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  marginBottom: 12,
                  paddingBottom: 8,
                  borderBottom: `1px solid ${theme.border}`,
                }}
              >
                <span
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: "50%",
                    background: TABLE_COLORS[1].accent,
                    animation: "pulse 1.5s ease-in-out infinite",
                  }}
                />
                <span
                  style={{
                    fontSize: 12,
                    fontWeight: 700,
                    letterSpacing: "0.05em",
                    color: TABLE_COLORS[1].accent,
                    fontFamily: theme.mono,
                  }}
                >
                  TABLE 1 — ACTIVE
                </span>
              </div>
              {/* Active table content rendered below */}
              {renderActiveTableContent()}
            </div>
          ) : (
            renderInactivePanel(1, t2GameState, t2Step, t2Decision)
          )}

          {/* Divider */}
          <div style={{ width: 1, background: "rgba(255,255,255,0.08)" }} />

          {/* Right panel: Table 2 */}
          {activeTable === 2 ? (
            <div
              style={{
                flex: 1,
                border: TABLE_COLORS[2].borderActive,
                borderRadius: 12,
                padding: 16,
                background: TABLE_COLORS[2].bgActive,
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  marginBottom: 12,
                  paddingBottom: 8,
                  borderBottom: `1px solid ${theme.border}`,
                }}
              >
                <span
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: "50%",
                    background: TABLE_COLORS[2].accent,
                    animation: "pulse 1.5s ease-in-out infinite",
                  }}
                />
                <span
                  style={{
                    fontSize: 12,
                    fontWeight: 700,
                    letterSpacing: "0.05em",
                    color: TABLE_COLORS[2].accent,
                    fontFamily: theme.mono,
                  }}
                >
                  TABLE 2 — ACTIVE
                </span>
              </div>
              {/* Active table content rendered below */}
              {renderActiveTableContent()}
            </div>
          ) : (
            renderInactivePanel(2, t2GameState, t2Step, t2Decision)
          )}
        </div>

        {/* Tab hint footer */}
        <div
          style={{
            textAlign: "center",
            marginTop: 12,
            fontSize: 11,
            color: theme.textDim,
            fontFamily: theme.mono,
          }}
        >
          Press <span style={{ color: "rgba(255,255,255,0.5)" }}>Tab</span> to switch tables
        </div>

        {/* Close Table 2 Confirmation Modal */}
        {showCloseConfirm && (
          <div
            style={{
              position: "fixed",
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              background: "rgba(0,0,0,0.75)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              zIndex: 1000,
            }}
            onClick={cancelCloseTable2}
          >
            <div
              style={{
                background: "#1a1a2e",
                border: "1px solid rgba(255,179,0,0.3)",
                borderRadius: 12,
                padding: "24px",
                maxWidth: 400,
                width: "90%",
                boxShadow: "0 8px 32px rgba(0,0,0,0.5)",
              }}
              onClick={(e) => e.stopPropagation()}
            >
              {/* Header */}
              <div style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                marginBottom: 16,
              }}>
                <div style={{
                  width: 36,
                  height: 36,
                  borderRadius: 8,
                  background: "rgba(255,179,0,0.15)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}>
                  <span style={{ fontSize: 18 }}>⚠️</span>
                </div>
                <div>
                  <div style={{
                    fontSize: 16,
                    fontWeight: 700,
                    color: theme.text,
                  }}>
                    Close Table 2?
                  </div>
                  <div style={{
                    fontSize: 11,
                    color: theme.textMuted,
                  }}>
                    This will discard the hand in progress
                  </div>
                </div>
              </div>

              {/* Table 2 Summary */}
              {(() => {
                const status = getTable2DataStatus()
                return (
                  <div style={{
                    background: "rgba(255,179,0,0.08)",
                    border: "1px solid rgba(255,179,0,0.2)",
                    borderRadius: 8,
                    padding: "12px 14px",
                    marginBottom: 20,
                  }}>
                    <div style={{
                      fontSize: 10,
                      fontWeight: 700,
                      color: TABLE_COLORS[2].accent,
                      letterSpacing: "0.08em",
                      marginBottom: 8,
                      textTransform: "uppercase",
                    }}>
                      TABLE 2 DATA
                    </div>
                    
                    {status.hasDecision ? (
                      <div>
                        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                          <span style={{
                            background: "rgba(255,179,0,0.2)",
                            color: TABLE_COLORS[2].accent,
                            padding: "3px 8px",
                            borderRadius: 4,
                            fontSize: 12,
                            fontWeight: 700,
                            fontFamily: theme.mono,
                          }}>
                            {status.position}
                          </span>
                          {status.card1 && (
                            <span style={{ fontFamily: theme.mono, fontSize: 13, fontWeight: 600 }}>
                              <span style={{ color: suitColor(status.card1.suit) }}>
                                {status.card1.rank}{suitSymbol(status.card1.suit)}
                              </span>
                              {status.card2 && (
                                <span style={{ color: suitColor(status.card2.suit), marginLeft: 2 }}>
                                  {status.card2.rank}{suitSymbol(status.card2.suit)}
                                </span>
                              )}
                            </span>
                          )}
                        </div>
                        <div style={{
                          fontSize: 14,
                          fontWeight: 700,
                          color: theme.green,
                          fontFamily: theme.mono,
                        }}>
                          Decision: {roundBetDisplay(status.decision?.display || "")}
                        </div>
                      </div>
                    ) : status.isInProgress ? (
                      <div>
                        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                          {status.position && (
                            <span style={{
                              background: "rgba(255,179,0,0.2)",
                              color: TABLE_COLORS[2].accent,
                              padding: "3px 8px",
                              borderRadius: 4,
                              fontSize: 12,
                              fontWeight: 700,
                              fontFamily: theme.mono,
                            }}>
                              {status.position}
                            </span>
                          )}
                          {status.card1 && (
                            <span style={{ fontFamily: theme.mono, fontSize: 13, fontWeight: 600 }}>
                              <span style={{ color: suitColor(status.card1.suit) }}>
                                {status.card1.rank}{suitSymbol(status.card1.suit)}
                              </span>
                              {status.card2 && (
                                <span style={{ color: suitColor(status.card2.suit), marginLeft: 2 }}>
                                  {status.card2.rank}{suitSymbol(status.card2.suit)}
                                </span>
                              )}
                            </span>
                          )}
                        </div>
                        <div style={{
                          fontSize: 12,
                          color: theme.textMuted,
                        }}>
                          Hand in progress · {getStepDescription(status.step)}
                        </div>
                      </div>
                    ) : (
                      <div style={{ fontSize: 12, color: theme.textMuted }}>
                        Position selected: {status.position}
                      </div>
                    )}
                  </div>
                )
              })()}

              {/* Actions */}
              <div style={{ display: "flex", gap: 10 }}>
                <button
                  onClick={cancelCloseTable2}
                  style={{
                    ...S.btn,
                    flex: 1,
                    padding: "12px",
                    fontSize: 13,
                    fontWeight: 600,
                  }}
                >
                  Cancel
                </button>
                <button
                  onClick={confirmCloseTable2}
                  style={{
                    ...S.btn,
                    flex: 1,
                    padding: "12px",
                    fontSize: 13,
                    fontWeight: 600,
                    background: "rgba(255,75,92,0.15)",
                    borderColor: "rgba(255,75,92,0.3)",
                    color: theme.red,
                  }}
                >
                  Close Table 2
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    )
  }

  // Helper function to render active table content (shared between both tables)
  function renderActiveTableContent() {
    return (
      <>
        {/* BREADCRUMB */}
        {renderBreadcrumb()}

        {/* PROMPT */}
        <div style={S.prompt}>
          <div
            style={{
              width: 7,
              height: 7,
              borderRadius: "50%",
              background: theme.accent,
              animation: step !== "showing_decision" ? "pulse 1.5s ease-in-out infinite" : "none",
              opacity: step === "showing_decision" ? 0 : 1,
            }}
          />
          {getPrompt()}
          {step !== "position" && step !== "showing_decision" && (
            <button
              onClick={goBack}
              style={{
                marginLeft: "auto",
                background: "none",
                border: "none",
                color: theme.textDim,
                fontSize: 11,
                fontFamily: theme.mono,
                cursor: "pointer",
                padding: "2px 6px",
              }}
            >
              {keyboardActive ? "Esc" : "← Back"}
            </button>
          )}
        </div>

        {/* HOLE CARDS DISPLAY */}
        <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 12 }}>
          {renderCardSlot(
            gameState.card1,
            "1",
            step === "card1_rank" || step === "card1_suit"
          )}
          {renderCardSlot(
            gameState.card2,
            "2",
            step === "card2_rank" || step === "card2_suit"
          )}

          {/* Board cards (post-flop) */}
          {gameState.street !== "preflop" && (
            <>
              <div style={{ width: 1, height: 40, background: theme.border, margin: "0 6px" }} />
              {gameState.board_cards.slice(0, requiredBoardCards(gameState.street)).map((bc, i) => (
                <div key={`board-${i}`}>
                  {renderCardSlot(
                    bc,
                    `B${i + 1}`,
                    (step === "board_rank" || step === "board_suit") && i === boardEntryIndex
                  )}
                </div>
              ))}
            </>
          )}
        </div>

        {/* Step-specific UI */}
        {renderStepUI()}

        {/* ALWAYS-VISIBLE SHORTCUT REFERENCE BAR */}
        {keyboardActive && step !== "showing_decision" && (
          <div
            style={{
              marginTop: 20,
              padding: "10px 14px",
              borderRadius: 8,
              background: "rgba(255,255,255,0.02)",
              border: `1px solid rgba(255,255,255,0.05)`,
              display: "flex",
              gap: 16,
              flexWrap: "wrap",
              fontSize: 11,
              fontFamily: theme.mono,
              color: theme.textDim,
            }}
          >
            {step === "position" && (
              <span><span style={{ color: "rgba(255,255,255,0.5)" }}>1-6</span> position</span>
            )}
            {(step === "card1_rank" || step === "card2_rank" || step === "board_rank") && (
              <>
                <span><span style={{ color: "rgba(255,255,255,0.5)" }}>a-2</span> rank</span>
                <span><span style={{ color: "rgba(255,255,255,0.5)" }}>t</span> = ten</span>
              </>
            )}
            {(step === "card1_suit" || step === "card2_suit" || step === "board_suit") && (
              <>
                <span><span style={{ color: "#C8C8D0" }}>s</span>=♠</span>
                <span><span style={{ color: "#FF4B5C" }}>h</span>=♥</span>
                <span><span style={{ color: "#4BA3FF" }}>d</span>=♦</span>
                <span><span style={{ color: "#50D890" }}>c</span>=♣</span>
              </>
            )}
            {step === "action" && gameState.street === "preflop" && (
              <>
                <span><span style={{ color: "rgba(255,255,255,0.5)" }}>f</span> nobody bet</span>
                <span><span style={{ color: "rgba(255,255,255,0.5)" }}>l</span> limpers</span>
                <span><span style={{ color: "rgba(255,255,255,0.5)" }}>r</span> raise</span>
              </>
            )}
            {step === "action" && gameState.street !== "preflop" && (
              <>
                <span><span style={{ color: "rgba(255,255,255,0.5)" }}>f</span> checked to me</span>
                <span><span style={{ color: "rgba(255,255,255,0.5)" }}>r</span> facing bet</span>
              </>
            )}
            {step === "villain_type" && (
              <>
                <span><span style={{ color: "rgba(255,255,255,0.5)" }}>1</span> not sure</span>
                <span><span style={{ color: "rgba(255,255,255,0.5)" }}>2</span> weak player</span>
                <span><span style={{ color: "rgba(255,255,255,0.5)" }}>3</span> good player</span>
              </>
            )}
            {(step === "amount" || step === "pot_size" || step === "limper_count") && (
              <span><span style={{ color: "rgba(255,255,255,0.5)" }}>Enter</span> confirm</span>
            )}
            {step === "outcome_select" && (
              <>
                <span><span style={{ color: theme.green }}>1</span> won</span>
                <span><span style={{ color: theme.red }}>2</span> lost</span>
                <span><span style={{ color: theme.textMuted }}>3</span> folded</span>
              </>
            )}
            <span style={{ marginLeft: "auto" }}>
              <span style={{ color: "rgba(255,255,255,0.5)" }}>Esc</span> back
            </span>
            <span>
              <span style={{ color: "rgba(255,255,255,0.5)" }}>Tab</span> switch table
            </span>
          </div>
        )}
      </>
    )
  }

  // Helper function to render step-specific UI (shared)
  function renderStepUI() {
    return (
      <>
        {/* POSITION BAR */}
        {step === "position" && (
          <div>
            <div style={S.sectionLabel}>Your Seat Position</div>
            
            {/* Visual order indicator */}
            <div style={{ 
              display: "flex", 
              alignItems: "center", 
              justifyContent: "center",
              gap: 4,
              marginBottom: 16,
              padding: "10px 16px",
              background: "rgba(255,255,255,0.02)",
              borderRadius: 8,
              border: `1px solid ${theme.border}`,
            }}>
              <span style={{ fontSize: 10, color: theme.textDim, marginRight: 6, fontFamily: theme.mono }}>ACTION ORDER:</span>
              {POSITIONS.map((pos, i) => (
                <React.Fragment key={pos.id}>
                  <span style={{ 
                    fontSize: 11, 
                    fontWeight: 600, 
                    color: theme.textMuted,
                    fontFamily: theme.mono,
                  }}>
                    {pos.label}
                  </span>
                  {i < POSITIONS.length - 1 && (
                    <span style={{ color: theme.textDim, fontSize: 10 }}>→</span>
                  )}
                </React.Fragment>
              ))}
            </div>

            {/* Position grid */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10 }}>
              {POSITIONS.map((pos) => (
                <button
                  key={pos.id}
                  onClick={() => selectPosition(pos.id)}
                  style={{
                    ...S.btn,
                    flexDirection: "column" as const,
                    display: "flex",
                    alignItems: "center",
                    gap: 4,
                    padding: "14px 10px",
                    position: "relative",
                    ...(gameState.position === pos.id ? S.btnActive : {}),
                  }}
                >
                  {keyboardActive && <span style={S.hint}>{pos.key}</span>}
                  <span style={{
                    position: "absolute",
                    top: 6,
                    left: 8,
                    fontSize: 9,
                    fontWeight: 700,
                    color: theme.textDim,
                    fontFamily: theme.mono,
                    background: "rgba(255,255,255,0.05)",
                    padding: "2px 5px",
                    borderRadius: 3,
                  }}>
                    {pos.order}
                  </span>
                  <span style={{ fontSize: 18, fontWeight: 800, letterSpacing: "0.02em" }}>{pos.label}</span>
                  <span style={{ fontSize: 10, color: theme.accent, fontWeight: 600, opacity: 0.8 }}>{pos.fullName}</span>
                  <span style={{ fontSize: 9, color: theme.textDim, fontWeight: 400, textAlign: "center", lineHeight: 1.3 }}>{pos.desc}</span>
                </button>
              ))}
            </div>

            {/* Helper for different table sizes */}
            <div style={{
              marginTop: 14,
              padding: "10px 14px",
              background: "rgba(255,179,0,0.05)",
              border: "1px solid rgba(255,179,0,0.15)",
              borderRadius: 8,
            }}>
              <div style={{
                fontSize: 11,
                color: theme.amber,
                fontWeight: 600,
                marginBottom: 4,
              }}>
                Playing with fewer than 6 players?
              </div>
              <div style={{
                fontSize: 10,
                color: theme.textMuted,
                lineHeight: 1.5,
              }}>
                Select the position that best matches where you sit relative to the button. 
                At a 4-handed table, use <span style={{ color: theme.text, fontWeight: 600 }}>CO</span>, <span style={{ color: theme.text, fontWeight: 600 }}>BTN</span>, <span style={{ color: theme.text, fontWeight: 600 }}>SB</span>, <span style={{ color: theme.text, fontWeight: 600 }}>BB</span>. 
                The key is your distance from the button — closer = wider range.
              </div>
            </div>
          </div>
        )}

        {/* RANK GRID */}
        {(step === "card1_rank" || step === "card2_rank" || step === "board_rank") && (
          <div>
            <div style={S.sectionLabel}>
              {step === "board_rank" ? "Board Card Rank" : `Card ${step === "card1_rank" ? "1" : "2"} Rank`}
            </div>
            {renderRankGrid()}
          </div>
        )}

        {/* SUIT SELECTOR */}
        {(step === "card1_suit" || step === "card2_suit" || step === "board_suit") && (
          <div>
            <div style={S.sectionLabel}>
              {pendingRank} — Select Suit
            </div>
            {renderSuitSelector()}
          </div>
        )}

        {/* ACTION BUTTONS */}
        {step === "action" && (
          <div>
            <div style={S.sectionLabel}>
              {gameState.street === "preflop" ? "What Happened Before You?" : "What Happened on This Street?"}
            </div>
            <div style={{ display: "grid", gridTemplateColumns: gameState.street === "preflop" ? "repeat(3, 1fr)" : "repeat(2, 1fr)", gap: 8 }}>
              {(gameState.street === "preflop" ? PREFLOP_ACTIONS_INITIAL : POSTFLOP_ACTIONS_INITIAL).map((action) => (
                <button
                  key={action.id}
                  onClick={() => selectAction(action.id, action.needsAmount || false, action.needsCount)}
                  style={{
                    ...S.btn,
                    flexDirection: "column" as const,
                    display: "flex",
                    alignItems: "center",
                    gap: 2,
                    padding: "12px 8px",
                  }}
                >
                  {keyboardActive && <span style={S.hint}>{action.key}</span>}
                  <span style={{ fontSize: 13, fontWeight: 600 }}>{action.label}</span>
                  <span style={{ fontSize: 10, color: theme.textDim, fontWeight: 400 }}>{action.desc}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* AMOUNT INPUT */}
        {step === "amount" && (
          <div>
            {/* Context banner for "They Raised Me" / "They Bet" scenarios */}
            {amountContext && (
              <div style={{
                background: "rgba(75, 163, 255, 0.08)",
                border: "1px solid rgba(75, 163, 255, 0.2)",
                borderRadius: 8,
                padding: "10px 14px",
                marginBottom: 14,
                display: "flex",
                alignItems: "center",
                gap: 10,
              }}>
                <div style={{
                  width: 32,
                  height: 32,
                  borderRadius: "50%",
                  background: "rgba(75, 163, 255, 0.15)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 14,
                }}>
                  ↩️
                </div>
                <div>
                  <div style={{
                    fontSize: 13,
                    fontWeight: 600,
                    color: theme.accent,
                    marginBottom: 2,
                  }}>
                    {amountContext}
                  </div>
                  <div style={{
                    fontSize: 11,
                    color: theme.textMuted,
                  }}>
                    {amountContext === "You checked" 
                      ? "They've bet — enter their bet amount"
                      : "Now they've raised — enter their new total"}
                  </div>
                </div>
              </div>
            )}
            
            <div style={S.sectionLabel}>{amountLabel}</div>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <span style={{ color: theme.textMuted, fontSize: 18, fontFamily: theme.mono }}>$</span>
              <input
                ref={amountRef}
                type="number"
                value={amountStr}
                onChange={(e) => setAmountStr(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault()
                    confirmAmount()
                  }
                }}
                style={S.input}
                placeholder="0.00"
                autoFocus
              />
              <button onClick={confirmAmount} style={{ ...S.btn, background: "rgba(0,200,83,0.08)", borderColor: "rgba(0,200,83,0.2)", color: theme.green }}>
                Confirm
              </button>
            </div>
          </div>
        )}

        {/* LIMPER COUNT INPUT */}
        {step === "limper_count" && (
          <div>
            <div style={S.sectionLabel}>How Many Limpers?</div>
            
            {/* Context explanation */}
            <div style={{
              background: "rgba(255,255,255,0.02)",
              border: `1px solid ${theme.border}`,
              borderRadius: 8,
              padding: "12px 14px",
              marginBottom: 14,
            }}>
              <div style={{
                fontSize: 12,
                color: theme.text,
                marginBottom: 8,
                fontWeight: 500,
              }}>
                A <span style={{ color: theme.amber, fontWeight: 700 }}>limper</span> is a player who just called the big blind instead of raising.
              </div>
              <div style={{
                fontSize: 11,
                color: theme.textMuted,
                lineHeight: 1.5,
              }}>
                Count how many players called $2 before you. This affects your raising size and range.
              </div>
            </div>

            {/* Visual limper count selector */}
            <div style={{
              display: "flex",
              gap: 8,
              marginBottom: 12,
            }}>
              {[1, 2, 3, 4, 5].map((num) => (
                <button
                  key={num}
                  onClick={() => {
                    setAmountStr(num.toString())
                  }}
                  style={{
                    ...S.btn,
                    flex: 1,
                    padding: "14px 8px",
                    fontSize: 18,
                    fontWeight: 700,
                    background: amountStr === num.toString() 
                      ? "rgba(75, 163, 255, 0.15)" 
                      : "rgba(255,255,255,0.03)",
                    borderColor: amountStr === num.toString()
                      ? theme.accent
                      : theme.borderLight,
                    color: amountStr === num.toString()
                      ? theme.accent
                      : theme.text,
                  }}
                >
                  {keyboardActive && <span style={S.hint}>{num}</span>}
                  {num}
                </button>
              ))}
            </div>

            {/* Confirm button */}
            <button 
              onClick={confirmLimperCount} 
              disabled={!amountStr}
              style={{ 
                ...S.btn, 
                width: "100%",
                padding: "12px",
                background: amountStr ? "rgba(0,200,83,0.12)" : "rgba(255,255,255,0.02)", 
                borderColor: amountStr ? "rgba(0,200,83,0.3)" : theme.border, 
                color: amountStr ? theme.green : theme.textDim,
                fontWeight: 600,
                fontSize: 13,
                cursor: amountStr ? "pointer" : "not-allowed",
              }}
            >
              {keyboardActive && amountStr && <span style={{...S.hint, color: theme.green}}>↵</span>}
              {amountStr ? `Confirm ${amountStr} Limper${amountStr !== "1" ? "s" : ""}` : "Select a number above"}
            </button>
          </div>
        )}

        {/* POT SIZE INPUT */}
        {step === "pot_size" && (
          <div>
            <div style={S.sectionLabel}>Pot Size</div>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <span style={{ color: theme.textMuted, fontSize: 18, fontFamily: theme.mono }}>$</span>
              <input
                ref={potRef}
                type="number"
                value={potStr}
                onChange={(e) => setPotStr(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault()
                    confirmPotSize()
                  }
                }}
                style={S.input}
                placeholder="0.00"
                autoFocus
              />
              <button onClick={confirmPotSize} style={{ ...S.btn, background: "rgba(0,200,83,0.08)", borderColor: "rgba(0,200,83,0.2)", color: theme.green }}>
                Confirm
              </button>
            </div>
          </div>
        )}

        {/* BOARD TEXTURE */}
        {step === "board_texture" && (
          <div>
            <div style={S.sectionLabel}>Board Texture</div>
            <div style={S.row}>
              {BOARD_TEXTURES.map((bt) => (
                <button
                  key={bt.id}
                  onClick={() => selectBoardTexture(bt.id)}
                  style={{ ...S.btn, flex: 1, flexDirection: "column", display: "flex", alignItems: "center", gap: 2 }}
                >
                  <span style={{ fontSize: 13, fontWeight: 600 }}>{bt.label}</span>
                  <span style={{ fontSize: 10, color: theme.textDim, fontWeight: 400 }}>{bt.desc}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* HAND STRENGTH */}
        {step === "hand_strength" && (
          <div>
            <div style={S.sectionLabel}>Your Hand Strength</div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 6 }}>
              {HAND_STRENGTHS.map((hs) => {
                let catColor = theme.textMuted
                if (hs.cat === "monster") catColor = theme.green
                else if (hs.cat === "strong") catColor = theme.accent
                else if (hs.cat === "draw") catColor = theme.amber
                else if (hs.cat === "weak") catColor = "rgba(255,255,255,0.3)"

                return (
                  <button
                    key={hs.id}
                    onClick={() => selectHandStrength(hs.id)}
                    style={{
                      ...S.btn,
                      padding: "8px 6px",
                      fontSize: 11,
                      borderLeftColor: catColor,
                      borderLeftWidth: 3,
                    }}
                  >
                    {hs.label}
                  </button>
                )
              })}
            </div>
          </div>
        )}

        {/* VILLAIN TYPE */}
        {step === "villain_type" && (
          <div>
            <div style={S.sectionLabel}>Who Are You Playing Against?</div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8 }}>
              {VILLAIN_TYPES.map((vt) => (
                <button
                  key={vt.id}
                  onClick={() => selectVillainType(vt.id)}
                  style={{
                    ...S.btn,
                    flexDirection: "column" as const,
                    display: "flex",
                    alignItems: "center",
                    gap: 2,
                    padding: "12px 8px",
                  }}
                >
                  {keyboardActive && <span style={S.hint}>{vt.key}</span>}
                  <span style={{ fontSize: 13, fontWeight: 600 }}>{vt.label}</span>
                  <span style={{ fontSize: 10, color: theme.textDim, fontWeight: 400 }}>{vt.desc}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* DECISION DISPLAY */}
        {step === "showing_decision" && renderDecision()}

        {/* OUTCOME RECORDING */}
        {step === "outcome_select" && (
          <div>
            <div style={S.sectionLabel}>How Did This Hand End?</div>

            {/* Bluff hands get 4-button layout */}
            {decision?.bluff_context ? (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 10 }}>
                <button
                  onClick={() => sendHandComplete("won")}
                  style={{
                    ...S.btn, padding: "18px 10px",
                    display: "flex", flexDirection: "column" as const, alignItems: "center", gap: 8,
                    background: "rgba(0,200,83,0.08)", borderColor: "rgba(0,200,83,0.3)",
                  }}
                >
                  {keyboardActive && <span style={S.hint}>1</span>}
                  <span style={{ fontSize: 24 }}>✅</span>
                  <span style={{ fontSize: 15, fontWeight: 700, color: theme.green }}>Won</span>
                  <span style={{ fontSize: 10, color: theme.textDim }}>They called, I won</span>
                </button>

                <button
                  onClick={() => {
                    const gs = gameState
                    const handStr = cardToString(gs.card1) + cardToString(gs.card2)
                    const autoTexture = gs.street !== "preflop" ? detectBoardTexture(gs.board_cards) : null
                    const autoStrength = gs.street !== "preflop" ? detectHandStrength(gs.card1, gs.card2, gs.board_cards) : null

                    const handContext = {
                      position: gs.position, cards: handStr, street: gs.street,
                      action_facing: gs.action_facing, facing_bet: gs.facing_bet,
                      pot_size: gs.pot_size,
                      board: gs.board_cards.filter(c => c !== null).map(c => cardToString(c)).join(""),
                      board_texture: gs.board_texture || autoTexture,
                      hand_strength: gs.hand_strength || autoStrength,
                      villain_type: gs.villain_type, we_are_aggressor: gs.we_are_aggressor,
                      num_limpers: gs.num_limpers,
                    }

                    const bluff_data = decision?.bluff_context ? {
                      spot_type: decision.bluff_context.spot_type,
                      delivery: decision.bluff_context.delivery,
                      recommended: decision.bluff_context.recommended_action,
                      user_action: chosenBluffAction || "BET",
                      outcome: "fold",
                      profit: decision.bluff_context.pot_size,
                      bet_amount: decision.bluff_context.bet_amount,
                      pot_size: decision.bluff_context.pot_size,
                      ev_of_bet: decision.bluff_context.ev_of_bet,
                      break_even_pct: decision.bluff_context.break_even_pct,
                      estimated_fold_pct: decision.bluff_context.estimated_fold_pct,
                    } : null

                    const freshState = { ...FRESH_GAME_STATE }
                    const table1GameState = primaryHoldsTable === 1 ? freshState : t2GameState
                    const table1Step = primaryHoldsTable === 1 ? "position" as InputStep : t2Step
                    const table1Decision = primaryHoldsTable === 1 ? null : t2Decision
                    const table1BoardEntryIndex = primaryHoldsTable === 1 ? 0 : t2BoardEntryIndex
                    const table2GameState = primaryHoldsTable === 2 ? freshState : t2GameState
                    const table2Step = primaryHoldsTable === 2 ? "position" as InputStep : t2Step
                    const table2Decision = primaryHoldsTable === 2 ? null : t2Decision
                    const table2BoardEntryIndex = primaryHoldsTable === 2 ? 0 : t2BoardEntryIndex

                    Streamlit.setComponentValue({
                      type: "hand_complete",
                      table_id: primaryHoldsTable,
                      outcome: "won",
                      action_taken: decision?.display || "",
                      hand_context: handContext,
                      bluff_data: bluff_data,
                      show_second_table: showSecondTable,
                      active_table: activeTable,
                      primary_holds_table: primaryHoldsTable,
                      table1_game_state: table1GameState, table1_step: table1Step,
                      table1_decision: table1Decision, table1_board_entry_index: table1BoardEntryIndex,
                      table2_game_state: table2GameState, table2_step: table2Step,
                      table2_decision: table2Decision, table2_board_entry_index: table2BoardEntryIndex,
                    })
                    resetHand()
                  }}
                  style={{
                    ...S.btn, padding: "18px 10px",
                    display: "flex", flexDirection: "column" as const, alignItems: "center", gap: 8,
                    background: "rgba(255,179,0,0.08)", borderColor: "rgba(255,179,0,0.3)",
                  }}
                >
                  {keyboardActive && <span style={S.hint}>2</span>}
                  <span style={{ fontSize: 24 }}>🏳️</span>
                  <span style={{ fontSize: 15, fontWeight: 700, color: theme.amber }}>They Folded</span>
                  <span style={{ fontSize: 10, color: theme.textDim }}>Bluff worked!</span>
                </button>

                <button
                  onClick={() => sendHandComplete("lost")}
                  style={{
                    ...S.btn, padding: "18px 10px",
                    display: "flex", flexDirection: "column" as const, alignItems: "center", gap: 8,
                    background: "rgba(255,75,92,0.08)", borderColor: "rgba(255,75,92,0.3)",
                  }}
                >
                  {keyboardActive && <span style={S.hint}>3</span>}
                  <span style={{ fontSize: 24 }}>❌</span>
                  <span style={{ fontSize: 15, fontWeight: 700, color: theme.red }}>Lost</span>
                  <span style={{ fontSize: 10, color: theme.textDim }}>They called, I lost</span>
                </button>

                <button
                  onClick={() => setStep("showing_decision")}
                  style={{
                    ...S.btn, padding: "18px 10px",
                    display: "flex", flexDirection: "column" as const, alignItems: "center", gap: 8,
                    background: "rgba(255,255,255,0.03)", borderColor: "rgba(255,255,255,0.12)",
                  }}
                >
                  <span style={{ fontSize: 24 }}>←</span>
                  <span style={{ fontSize: 15, fontWeight: 700, color: theme.textMuted }}>Back</span>
                </button>
              </div>
            ) : (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10 }}>
                <button
                  onClick={() => sendHandComplete("won")}
                  style={{
                    ...S.btn, padding: "18px 10px",
                    display: "flex", flexDirection: "column" as const, alignItems: "center", gap: 8,
                    background: "rgba(0,200,83,0.08)", borderColor: "rgba(0,200,83,0.3)",
                  }}
                >
                  {keyboardActive && <span style={S.hint}>1</span>}
                  <span style={{ fontSize: 24 }}>✅</span>
                  <span style={{ fontSize: 15, fontWeight: 700, color: theme.green }}>Won</span>
                </button>

                <button
                  onClick={() => sendHandComplete("lost")}
                  style={{
                    ...S.btn, padding: "18px 10px",
                    display: "flex", flexDirection: "column" as const, alignItems: "center", gap: 8,
                    background: "rgba(255,75,92,0.08)", borderColor: "rgba(255,75,92,0.3)",
                  }}
                >
                  {keyboardActive && <span style={S.hint}>2</span>}
                  <span style={{ fontSize: 24 }}>❌</span>
                  <span style={{ fontSize: 15, fontWeight: 700, color: theme.red }}>Lost</span>
                </button>

                <button
                  onClick={() => sendHandComplete("folded")}
                  style={{
                    ...S.btn, padding: "18px 10px",
                    display: "flex", flexDirection: "column" as const, alignItems: "center", gap: 8,
                    background: "rgba(255,255,255,0.03)", borderColor: "rgba(255,255,255,0.12)",
                  }}
                >
                  {keyboardActive && <span style={S.hint}>3</span>}
                  <span style={{ fontSize: 24 }}>🏳️</span>
                  <span style={{ fontSize: 15, fontWeight: 700, color: theme.textMuted }}>Folded</span>
                </button>
              </div>
            )}

            {/* Hand summary reminder */}
            {decision && (
              <div style={{
                marginTop: 14,
                padding: "10px 14px",
                background: "rgba(255,255,255,0.02)",
                borderRadius: 8,
                border: `1px solid ${theme.border}`,
                display: "flex",
                alignItems: "center",
                gap: 10,
                fontSize: 12,
                color: theme.textMuted,
              }}>
                <span style={{ fontWeight: 600, color: theme.text }}>{gameState.position}</span>
                {gameState.card1 && (
                  <span style={{ fontFamily: theme.mono }}>
                    <span style={{ color: suitColor(gameState.card1.suit) }}>
                      {gameState.card1.rank}{suitSymbol(gameState.card1.suit)}
                    </span>
                    {gameState.card2 && (
                      <span style={{ color: suitColor(gameState.card2.suit), marginLeft: 2 }}>
                        {gameState.card2.rank}{suitSymbol(gameState.card2.suit)}
                      </span>
                    )}
                  </span>
                )}
                <span style={{ color: theme.textDim }}>→</span>
                <span style={{ fontWeight: 600 }}>{roundBetDisplay(decision.display)}</span>
              </div>
            )}

            <button
              onClick={() => setStep("showing_decision")}
              style={{
                ...S.btn,
                width: "100%",
                marginTop: 10,
                padding: "8px",
                fontSize: 11,
                color: theme.textDim,
              }}
            >
            ← Back to Decision
            </button>
          </div>
        )}
      </>
    )
  }

  // ==========================================================================
  // STANDARD / KEYBOARD MODE RENDER (UNCHANGED FROM ORIGINAL)
  // ==========================================================================

  return (
    <div ref={containerRef} style={S.container} tabIndex={0}>
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 0.4; transform: scale(1); }
          50% { opacity: 1; transform: scale(1.2); }
        }
        button:hover {
          filter: brightness(1.15);
        }
      `}</style>

      {/* HEADER */}
      <div style={S.header}>
        <div style={{ fontSize: 14, fontWeight: 700, letterSpacing: "0.03em", fontFamily: theme.mono }}>
          NAMELESS POKER
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          {/* +Table 2 toggle (only in keyboard mode, not standard) */}
          {keyboardActive && mode !== "two_table" && (
            <button
              onClick={showSecondTable ? handleCloseTable2 : toggleSecondTable}
              style={{
                background: showSecondTable 
                  ? "rgba(255,75,92,0.1)" 
                  : "rgba(75,163,255,0.08)",
                border: showSecondTable
                  ? "1px solid rgba(255,75,92,0.25)"
                  : `1px solid ${theme.borderLight}`,
                borderRadius: 6,
                padding: "4px 10px",
                color: showSecondTable ? theme.red : theme.textMuted,
                fontSize: 11,
                fontFamily: theme.mono,
                cursor: "pointer",
                transition: "all 0.15s ease",
              }}
            >
              {showSecondTable ? "✕ Close T2" : "+ Table 2"}
            </button>
          )}
          {keyboardActive && (
            <button
              onClick={() => setShowOverlay(!showOverlay)}
              style={{
                background: "none",
                border: `1px solid ${theme.borderLight}`,
                borderRadius: 6,
                padding: "3px 8px",
                color: theme.textMuted,
                fontSize: 11,
                fontFamily: theme.mono,
                cursor: "pointer",
              }}
            >
              ?
            </button>
          )}
          <span
            style={{
              fontSize: 11,
              color: theme.textDim,
              fontFamily: theme.mono,
            }}
          >
            {stakes} · {Math.round(stackSize / bbSize)}BB
          </span>
        </div>
      </div>

      {/* SHORTCUT OVERLAY */}
      {showOverlay && (
        <div
          style={{
            position: "absolute",
            top: 50,
            right: 24,
            background: "#1a1a2e",
            border: `1px solid ${theme.borderLight}`,
            borderRadius: 10,
            padding: 16,
            zIndex: 100,
            width: 260,
            boxShadow: "0 8px 32px rgba(0,0,0,0.5)",
          }}
        >
          <div style={{ fontSize: 12, fontWeight: 700, color: theme.text, marginBottom: 10 }}>
            KEYBOARD SHORTCUTS
          </div>
          {[
            ["1-6", "Position (UTG→BB)"],
            ["a,k,q,j,t,9-2", "Card rank"],
            ["s, h, d, c", "Suit (♠♥♦♣)"],
            ["f", "Fold to me / Check to me"],
            ["l", "Limper(s)"],
            ["r", "Raise / Facing bet"],
            ["e", "3-Bet"],
            ["Esc", "Undo / Reset"],
            ["Enter", "Confirm amount"],
            ["N / Space", "New hand"],
            ["1,2,3", "Continue → Flop/Turn/River"],
          ].map(([key, desc]) => (
            <div
              key={key}
              style={{
                display: "flex",
                justifyContent: "space-between",
                fontSize: 11,
                fontFamily: theme.mono,
                padding: "3px 0",
                color: theme.textMuted,
              }}
            >
              <span style={{ color: "rgba(255,255,255,0.7)" }}>{key}</span>
              <span>{desc}</span>
            </div>
          ))}
          <button
            onClick={() => setShowOverlay(false)}
            style={{
              ...S.btn,
              width: "100%",
              marginTop: 10,
              padding: "6px",
              fontSize: 11,
            }}
          >
            Close
          </button>
        </div>
      )}

      {/* BREADCRUMB */}
      {renderBreadcrumb()}

      {/* PROMPT */}
      <div style={S.prompt}>
        <div
          style={{
            width: 7,
            height: 7,
            borderRadius: "50%",
            background: theme.accent,
            animation: step !== "showing_decision" ? "pulse 1.5s ease-in-out infinite" : "none",
            opacity: step === "showing_decision" ? 0 : 1,
          }}
        />
        {getPrompt()}
        {step !== "position" && step !== "showing_decision" && (
          <button
            onClick={goBack}
            style={{
              marginLeft: "auto",
              background: "none",
              border: "none",
              color: theme.textDim,
              fontSize: 11,
              fontFamily: theme.mono,
              cursor: "pointer",
              padding: "2px 6px",
            }}
          >
            {keyboardActive ? "Esc" : "← Back"}
          </button>
        )}
      </div>

      {/* HOLE CARDS DISPLAY */}
      <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 12 }}>
        {renderCardSlot(
          gameState.card1,
          "1",
          step === "card1_rank" || step === "card1_suit"
        )}
        {renderCardSlot(
          gameState.card2,
          "2",
          step === "card2_rank" || step === "card2_suit"
        )}

        {/* Board cards (post-flop) */}
        {gameState.street !== "preflop" && (
          <>
            <div style={{ width: 1, height: 40, background: theme.border, margin: "0 6px" }} />
            {gameState.board_cards.slice(0, requiredBoardCards(gameState.street)).map((bc, i) => (
              <div key={`board-${i}`}>
                {renderCardSlot(
                  bc,
                  `B${i + 1}`,
                  (step === "board_rank" || step === "board_suit") && i === boardEntryIndex
                )}
              </div>
            ))}
          </>
        )}
      </div>

      {/* POSITION BAR */}
      {step === "position" && (
        <div>
          <div style={S.sectionLabel}>Your Seat Position</div>
          
          {/* Visual order indicator */}
          <div style={{ 
            display: "flex", 
            alignItems: "center", 
            justifyContent: "center",
            gap: 4,
            marginBottom: 16,
            padding: "10px 16px",
            background: "rgba(255,255,255,0.02)",
            borderRadius: 8,
            border: `1px solid ${theme.border}`,
          }}>
            <span style={{ fontSize: 10, color: theme.textDim, marginRight: 6, fontFamily: theme.mono }}>ACTION ORDER:</span>
            {POSITIONS.map((pos, i) => (
              <React.Fragment key={pos.id}>
                <span style={{ 
                  fontSize: 11, 
                  fontWeight: 600, 
                  color: theme.textMuted,
                  fontFamily: theme.mono,
                }}>
                  {pos.label}
                </span>
                {i < POSITIONS.length - 1 && (
                  <span style={{ color: theme.textDim, fontSize: 10 }}>→</span>
                )}
              </React.Fragment>
            ))}
          </div>

          {/* Position grid */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10 }}>
            {POSITIONS.map((pos) => (
              <button
                key={pos.id}
                onClick={() => selectPosition(pos.id)}
                style={{
                  ...S.btn,
                  flexDirection: "column" as const,
                  display: "flex",
                  alignItems: "center",
                  gap: 4,
                  padding: "14px 10px",
                  position: "relative",
                  ...(gameState.position === pos.id ? S.btnActive : {}),
                }}
              >
                {keyboardActive && <span style={S.hint}>{pos.key}</span>}
                <span style={{
                  position: "absolute",
                  top: 6,
                  left: 8,
                  fontSize: 9,
                  fontWeight: 700,
                  color: theme.textDim,
                  fontFamily: theme.mono,
                  background: "rgba(255,255,255,0.05)",
                  padding: "2px 5px",
                  borderRadius: 3,
                }}>
                  {pos.order}
                </span>
                <span style={{ fontSize: 18, fontWeight: 800, letterSpacing: "0.02em" }}>{pos.label}</span>
                <span style={{ fontSize: 10, color: theme.accent, fontWeight: 600, opacity: 0.8 }}>{pos.fullName}</span>
                <span style={{ fontSize: 9, color: theme.textDim, fontWeight: 400, textAlign: "center", lineHeight: 1.3 }}>{pos.desc}</span>
              </button>
            ))}
          </div>

          {/* Helper for different table sizes */}
          <div style={{
            marginTop: 14,
            padding: "10px 14px",
            background: "rgba(255,179,0,0.05)",
            border: "1px solid rgba(255,179,0,0.15)",
            borderRadius: 8,
          }}>
            <div style={{
              fontSize: 11,
              color: theme.amber,
              fontWeight: 600,
              marginBottom: 4,
            }}>
              Playing with fewer than 6 players?
            </div>
            <div style={{
              fontSize: 10,
              color: theme.textMuted,
              lineHeight: 1.5,
            }}>
              Select the position that best matches where you sit relative to the button. 
              At a 4-handed table, use <span style={{ color: theme.text, fontWeight: 600 }}>CO</span>, <span style={{ color: theme.text, fontWeight: 600 }}>BTN</span>, <span style={{ color: theme.text, fontWeight: 600 }}>SB</span>, <span style={{ color: theme.text, fontWeight: 600 }}>BB</span>. 
              The key is your distance from the button — closer = wider range.
            </div>
          </div>
        </div>
      )}

      {/* RANK GRID */}
      {(step === "card1_rank" || step === "card2_rank" || step === "board_rank") && (
        <div>
          <div style={S.sectionLabel}>
            {step === "board_rank" ? "Board Card Rank" : `Card ${step === "card1_rank" ? "1" : "2"} Rank`}
          </div>
          {renderRankGrid()}
        </div>
      )}

      {/* SUIT SELECTOR */}
      {(step === "card1_suit" || step === "card2_suit" || step === "board_suit") && (
        <div>
          <div style={S.sectionLabel}>
            {pendingRank} — Select Suit
          </div>
          {renderSuitSelector()}
        </div>
      )}

      {/* ACTION BUTTONS */}
      {step === "action" && (
        <div>
          <div style={S.sectionLabel}>
            {gameState.street === "preflop" ? "What Happened Before You?" : "What Happened on This Street?"}
          </div>
          <div style={{ display: "grid", gridTemplateColumns: gameState.street === "preflop" ? "repeat(3, 1fr)" : "repeat(2, 1fr)", gap: 8 }}>
            {(gameState.street === "preflop" ? PREFLOP_ACTIONS_INITIAL : POSTFLOP_ACTIONS_INITIAL).map((action) => (
              <button
                key={action.id}
                onClick={() => selectAction(action.id, action.needsAmount || false, action.needsCount)}
                style={{
                  ...S.btn,
                  flexDirection: "column" as const,
                  display: "flex",
                  alignItems: "center",
                  gap: 2,
                  padding: "12px 8px",
                }}
              >
                {keyboardActive && <span style={S.hint}>{action.key}</span>}
                <span style={{ fontSize: 13, fontWeight: 600 }}>{action.label}</span>
                <span style={{ fontSize: 10, color: theme.textDim, fontWeight: 400 }}>{action.desc}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* AMOUNT INPUT */}
      {step === "amount" && (
        <div>
          {/* Context banner for "They Raised Me" / "They Bet" scenarios */}
          {amountContext && (
            <div style={{
              background: "rgba(75, 163, 255, 0.08)",
              border: "1px solid rgba(75, 163, 255, 0.2)",
              borderRadius: 8,
              padding: "10px 14px",
              marginBottom: 14,
              display: "flex",
              alignItems: "center",
              gap: 10,
            }}>
              <div style={{
                width: 32,
                height: 32,
                borderRadius: "50%",
                background: "rgba(75, 163, 255, 0.15)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 14,
              }}>
                ↩️
              </div>
              <div>
                <div style={{
                  fontSize: 13,
                  fontWeight: 600,
                  color: theme.accent,
                  marginBottom: 2,
                }}>
                  {amountContext}
                </div>
                <div style={{
                  fontSize: 11,
                  color: theme.textMuted,
                }}>
                  {amountContext === "You checked" 
                    ? "They've bet — enter their bet amount"
                    : "Now they've raised — enter their new total"}
                </div>
              </div>
            </div>
          )}
          
          <div style={S.sectionLabel}>{amountLabel}</div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <span style={{ color: theme.textMuted, fontSize: 18, fontFamily: theme.mono }}>$</span>
            <input
              ref={amountRef}
              type="number"
              value={amountStr}
              onChange={(e) => setAmountStr(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault()
                  confirmAmount()
                }
              }}
              style={S.input}
              placeholder="0.00"
              autoFocus
            />
            <button onClick={confirmAmount} style={{ ...S.btn, background: "rgba(0,200,83,0.08)", borderColor: "rgba(0,200,83,0.2)", color: theme.green }}>
              Confirm
            </button>
          </div>
        </div>
      )}

      {/* LIMPER COUNT INPUT */}
      {step === "limper_count" && (
        <div>
          <div style={S.sectionLabel}>How Many Limpers?</div>
          
          {/* Context explanation */}
          <div style={{
            background: "rgba(255,255,255,0.02)",
            border: `1px solid ${theme.border}`,
            borderRadius: 8,
            padding: "12px 14px",
            marginBottom: 14,
          }}>
            <div style={{
              fontSize: 12,
              color: theme.text,
              marginBottom: 8,
              fontWeight: 500,
            }}>
              A <span style={{ color: theme.amber, fontWeight: 700 }}>limper</span> is a player who just called the big blind instead of raising.
            </div>
            <div style={{
              fontSize: 11,
              color: theme.textMuted,
              lineHeight: 1.5,
            }}>
              Count how many players called $2 before you. This affects your raising size and range.
            </div>
          </div>

          {/* Visual limper count selector */}
          <div style={{
            display: "flex",
            gap: 8,
            marginBottom: 12,
          }}>
            {[1, 2, 3, 4, 5].map((num) => (
              <button
                key={num}
                onClick={() => {
                  setAmountStr(num.toString())
                }}
                style={{
                  ...S.btn,
                  flex: 1,
                  padding: "14px 8px",
                  fontSize: 18,
                  fontWeight: 700,
                  background: amountStr === num.toString() 
                    ? "rgba(75, 163, 255, 0.15)" 
                    : "rgba(255,255,255,0.03)",
                  borderColor: amountStr === num.toString()
                    ? theme.accent
                    : theme.borderLight,
                  color: amountStr === num.toString()
                    ? theme.accent
                    : theme.text,
                }}
              >
                {keyboardActive && <span style={S.hint}>{num}</span>}
                {num}
              </button>
            ))}
          </div>

          {/* Confirm button */}
          <button 
            onClick={confirmLimperCount} 
            disabled={!amountStr}
            style={{ 
              ...S.btn, 
              width: "100%",
              padding: "12px",
              background: amountStr ? "rgba(0,200,83,0.12)" : "rgba(255,255,255,0.02)", 
              borderColor: amountStr ? "rgba(0,200,83,0.3)" : theme.border, 
              color: amountStr ? theme.green : theme.textDim,
              fontWeight: 600,
              fontSize: 13,
              cursor: amountStr ? "pointer" : "not-allowed",
            }}
          >
            {keyboardActive && amountStr && <span style={{...S.hint, color: theme.green}}>↵</span>}
            {amountStr ? `Confirm ${amountStr} Limper${amountStr !== "1" ? "s" : ""}` : "Select a number above"}
          </button>
        </div>
      )}

      {/* POT SIZE INPUT */}
      {step === "pot_size" && (
        <div>
          <div style={S.sectionLabel}>Pot Size</div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <span style={{ color: theme.textMuted, fontSize: 18, fontFamily: theme.mono }}>$</span>
            <input
              ref={potRef}
              type="number"
              value={potStr}
              onChange={(e) => setPotStr(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault()
                  confirmPotSize()
                }
              }}
              style={S.input}
              placeholder="0.00"
              autoFocus
            />
            <button onClick={confirmPotSize} style={{ ...S.btn, background: "rgba(0,200,83,0.08)", borderColor: "rgba(0,200,83,0.2)", color: theme.green }}>
              Confirm
            </button>
          </div>
        </div>
      )}

      {/* BOARD TEXTURE */}
      {step === "board_texture" && (
        <div>
          <div style={S.sectionLabel}>Board Texture</div>
          <div style={S.row}>
            {BOARD_TEXTURES.map((bt) => (
              <button
                key={bt.id}
                onClick={() => selectBoardTexture(bt.id)}
                style={{ ...S.btn, flex: 1, flexDirection: "column", display: "flex", alignItems: "center", gap: 2 }}
              >
                <span style={{ fontSize: 13, fontWeight: 600 }}>{bt.label}</span>
                <span style={{ fontSize: 10, color: theme.textDim, fontWeight: 400 }}>{bt.desc}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* HAND STRENGTH */}
      {step === "hand_strength" && (
        <div>
          <div style={S.sectionLabel}>Your Hand Strength</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 6 }}>
            {HAND_STRENGTHS.map((hs) => {
              let catColor = theme.textMuted
              if (hs.cat === "monster") catColor = theme.green
              else if (hs.cat === "strong") catColor = theme.accent
              else if (hs.cat === "draw") catColor = theme.amber
              else if (hs.cat === "weak") catColor = "rgba(255,255,255,0.3)"

              return (
                <button
                  key={hs.id}
                  onClick={() => selectHandStrength(hs.id)}
                  style={{
                    ...S.btn,
                    padding: "8px 6px",
                    fontSize: 11,
                    borderLeftColor: catColor,
                    borderLeftWidth: 3,
                  }}
                >
                  {hs.label}
                </button>
              )
            })}
          </div>
        </div>
      )}

      {/* VILLAIN TYPE */}
      {step === "villain_type" && (
        <div>
          <div style={S.sectionLabel}>Who Are You Playing Against?</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8 }}>
            {VILLAIN_TYPES.map((vt) => (
              <button
                key={vt.id}
                onClick={() => selectVillainType(vt.id)}
                style={{
                  ...S.btn,
                  flexDirection: "column" as const,
                  display: "flex",
                  alignItems: "center",
                  gap: 2,
                  padding: "12px 8px",
                }}
              >
                {keyboardActive && <span style={S.hint}>{vt.key}</span>}
                <span style={{ fontSize: 13, fontWeight: 600 }}>{vt.label}</span>
                <span style={{ fontSize: 10, color: theme.textDim, fontWeight: 400 }}>{vt.desc}</span>
              </button>
            ))}
          </div>
        </div>
      )}

    {/* DECISION DISPLAY */}
      {step === "showing_decision" && renderDecision()}

      {/* OUTCOME RECORDING */}
      {step === "outcome_select" && (
          <div>
            <div style={S.sectionLabel}>How Did This Hand End?</div>

            {/* Bluff hands get 4-button layout */}
            {decision?.bluff_context ? (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 10 }}>
                <button
                  onClick={() => sendHandComplete("won")}
                  style={{
                    ...S.btn, padding: "18px 10px",
                    display: "flex", flexDirection: "column" as const, alignItems: "center", gap: 8,
                    background: "rgba(0,200,83,0.08)", borderColor: "rgba(0,200,83,0.3)",
                  }}
                >
                  {keyboardActive && <span style={S.hint}>1</span>}
                  <span style={{ fontSize: 24 }}>✅</span>
                  <span style={{ fontSize: 15, fontWeight: 700, color: theme.green }}>Won</span>
                  <span style={{ fontSize: 10, color: theme.textDim }}>They called, I won</span>
                </button>

                <button
                  onClick={() => {
                    const gs = gameState
                    const handStr = cardToString(gs.card1) + cardToString(gs.card2)
                    const autoTexture = gs.street !== "preflop" ? detectBoardTexture(gs.board_cards) : null
                    const autoStrength = gs.street !== "preflop" ? detectHandStrength(gs.card1, gs.card2, gs.board_cards) : null

                    const handContext = {
                      position: gs.position, cards: handStr, street: gs.street,
                      action_facing: gs.action_facing, facing_bet: gs.facing_bet,
                      pot_size: gs.pot_size,
                      board: gs.board_cards.filter(c => c !== null).map(c => cardToString(c)).join(""),
                      board_texture: gs.board_texture || autoTexture,
                      hand_strength: gs.hand_strength || autoStrength,
                      villain_type: gs.villain_type, we_are_aggressor: gs.we_are_aggressor,
                      num_limpers: gs.num_limpers,
                    }

                    const bluff_data = decision?.bluff_context ? {
                      spot_type: decision.bluff_context.spot_type,
                      delivery: decision.bluff_context.delivery,
                      recommended: decision.bluff_context.recommended_action,
                      user_action: chosenBluffAction || "BET",
                      outcome: "fold",
                      profit: decision.bluff_context.pot_size,
                      bet_amount: decision.bluff_context.bet_amount,
                      pot_size: decision.bluff_context.pot_size,
                      ev_of_bet: decision.bluff_context.ev_of_bet,
                      break_even_pct: decision.bluff_context.break_even_pct,
                      estimated_fold_pct: decision.bluff_context.estimated_fold_pct,
                    } : null

                    const freshState = { ...FRESH_GAME_STATE }
                    const table1GameState = primaryHoldsTable === 1 ? freshState : t2GameState
                    const table1Step = primaryHoldsTable === 1 ? "position" as InputStep : t2Step
                    const table1Decision = primaryHoldsTable === 1 ? null : t2Decision
                    const table1BoardEntryIndex = primaryHoldsTable === 1 ? 0 : t2BoardEntryIndex
                    const table2GameState = primaryHoldsTable === 2 ? freshState : t2GameState
                    const table2Step = primaryHoldsTable === 2 ? "position" as InputStep : t2Step
                    const table2Decision = primaryHoldsTable === 2 ? null : t2Decision
                    const table2BoardEntryIndex = primaryHoldsTable === 2 ? 0 : t2BoardEntryIndex

                    Streamlit.setComponentValue({
                      type: "hand_complete",
                      table_id: primaryHoldsTable,
                      outcome: "won",
                      action_taken: decision?.display || "",
                      hand_context: handContext,
                      bluff_data: bluff_data,
                      show_second_table: showSecondTable,
                      active_table: activeTable,
                      primary_holds_table: primaryHoldsTable,
                      table1_game_state: table1GameState, table1_step: table1Step,
                      table1_decision: table1Decision, table1_board_entry_index: table1BoardEntryIndex,
                      table2_game_state: table2GameState, table2_step: table2Step,
                      table2_decision: table2Decision, table2_board_entry_index: table2BoardEntryIndex,
                    })
                    resetHand()
                  }}
                  style={{
                    ...S.btn, padding: "18px 10px",
                    display: "flex", flexDirection: "column" as const, alignItems: "center", gap: 8,
                    background: "rgba(255,179,0,0.08)", borderColor: "rgba(255,179,0,0.3)",
                  }}
                >
                  {keyboardActive && <span style={S.hint}>2</span>}
                  <span style={{ fontSize: 24 }}>🏳️</span>
                  <span style={{ fontSize: 15, fontWeight: 700, color: theme.amber }}>They Folded</span>
                  <span style={{ fontSize: 10, color: theme.textDim }}>Bluff worked!</span>
                </button>

                <button
                  onClick={() => sendHandComplete("lost")}
                  style={{
                    ...S.btn, padding: "18px 10px",
                    display: "flex", flexDirection: "column" as const, alignItems: "center", gap: 8,
                    background: "rgba(255,75,92,0.08)", borderColor: "rgba(255,75,92,0.3)",
                  }}
                >
                  {keyboardActive && <span style={S.hint}>3</span>}
                  <span style={{ fontSize: 24 }}>❌</span>
                  <span style={{ fontSize: 15, fontWeight: 700, color: theme.red }}>Lost</span>
                  <span style={{ fontSize: 10, color: theme.textDim }}>They called, I lost</span>
                </button>

                <button
                  onClick={() => setStep("showing_decision")}
                  style={{
                    ...S.btn, padding: "18px 10px",
                    display: "flex", flexDirection: "column" as const, alignItems: "center", gap: 8,
                    background: "rgba(255,255,255,0.03)", borderColor: "rgba(255,255,255,0.12)",
                  }}
                >
                  <span style={{ fontSize: 24 }}>←</span>
                  <span style={{ fontSize: 15, fontWeight: 700, color: theme.textMuted }}>Back</span>
                </button>
              </div>
            ) : (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10 }}>
                <button
                  onClick={() => sendHandComplete("won")}
                  style={{
                    ...S.btn, padding: "18px 10px",
                    display: "flex", flexDirection: "column" as const, alignItems: "center", gap: 8,
                    background: "rgba(0,200,83,0.08)", borderColor: "rgba(0,200,83,0.3)",
                  }}
                >
                  {keyboardActive && <span style={S.hint}>1</span>}
                  <span style={{ fontSize: 24 }}>✅</span>
                  <span style={{ fontSize: 15, fontWeight: 700, color: theme.green }}>Won</span>
                </button>

                <button
                  onClick={() => sendHandComplete("lost")}
                  style={{
                    ...S.btn, padding: "18px 10px",
                    display: "flex", flexDirection: "column" as const, alignItems: "center", gap: 8,
                    background: "rgba(255,75,92,0.08)", borderColor: "rgba(255,75,92,0.3)",
                  }}
                >
                  {keyboardActive && <span style={S.hint}>2</span>}
                  <span style={{ fontSize: 24 }}>❌</span>
                  <span style={{ fontSize: 15, fontWeight: 700, color: theme.red }}>Lost</span>
                </button>

                <button
                  onClick={() => sendHandComplete("folded")}
                  style={{
                    ...S.btn, padding: "18px 10px",
                    display: "flex", flexDirection: "column" as const, alignItems: "center", gap: 8,
                    background: "rgba(255,255,255,0.03)", borderColor: "rgba(255,255,255,0.12)",
                  }}
                >
                  {keyboardActive && <span style={S.hint}>3</span>}
                  <span style={{ fontSize: 24 }}>🏳️</span>
                  <span style={{ fontSize: 15, fontWeight: 700, color: theme.textMuted }}>Folded</span>
                </button>
              </div>
            )}

            {/* Hand summary reminder */}
            {decision && (
              <div style={{
                marginTop: 14,
                padding: "10px 14px",
                background: "rgba(255,255,255,0.02)",
                borderRadius: 8,
                border: `1px solid ${theme.border}`,
                display: "flex",
                alignItems: "center",
                gap: 10,
                fontSize: 12,
                color: theme.textMuted,
              }}>
                <span style={{ fontWeight: 600, color: theme.text }}>{gameState.position}</span>
                {gameState.card1 && (
                  <span style={{ fontFamily: theme.mono }}>
                    <span style={{ color: suitColor(gameState.card1.suit) }}>
                      {gameState.card1.rank}{suitSymbol(gameState.card1.suit)}
                    </span>
                    {gameState.card2 && (
                      <span style={{ color: suitColor(gameState.card2.suit), marginLeft: 2 }}>
                        {gameState.card2.rank}{suitSymbol(gameState.card2.suit)}
                      </span>
                    )}
                  </span>
                )}
                <span style={{ color: theme.textDim }}>→</span>
                <span style={{ fontWeight: 600 }}>{roundBetDisplay(decision.display)}</span>
              </div>
            )}

            <button
              onClick={() => setStep("showing_decision")}
              style={{
                ...S.btn,
                width: "100%",
                marginTop: 10,
                padding: "8px",
                fontSize: 11,
                color: theme.textDim,
              }}
            >
              ← Back to Decision
            </button>
          </div>
        )}

      {/* ALWAYS-VISIBLE SHORTCUT REFERENCE BAR */}
      {keyboardActive && step !== "showing_decision" && (
        <div
          style={{
            marginTop: 20,
            padding: "10px 14px",
            borderRadius: 8,
            background: "rgba(255,255,255,0.02)",
            border: `1px solid rgba(255,255,255,0.05)`,
            display: "flex",
            gap: 16,
            flexWrap: "wrap",
            fontSize: 11,
            fontFamily: theme.mono,
            color: theme.textDim,
          }}
        >
          {step === "position" && (
            <span><span style={{ color: "rgba(255,255,255,0.5)" }}>1-6</span> position</span>
          )}
          {(step === "card1_rank" || step === "card2_rank" || step === "board_rank") && (
            <>
              <span><span style={{ color: "rgba(255,255,255,0.5)" }}>a-2</span> rank</span>
              <span><span style={{ color: "rgba(255,255,255,0.5)" }}>t</span> = ten</span>
            </>
          )}
          {(step === "card1_suit" || step === "card2_suit" || step === "board_suit") && (
            <>
              <span><span style={{ color: "#C8C8D0" }}>s</span>=♠</span>
              <span><span style={{ color: "#FF4B5C" }}>h</span>=♥</span>
              <span><span style={{ color: "#4BA3FF" }}>d</span>=♦</span>
              <span><span style={{ color: "#50D890" }}>c</span>=♣</span>
            </>
          )}
          {step === "action" && gameState.street === "preflop" && (
            <>
              <span><span style={{ color: "rgba(255,255,255,0.5)" }}>f</span> nobody bet</span>
              <span><span style={{ color: "rgba(255,255,255,0.5)" }}>l</span> limpers</span>
              <span><span style={{ color: "rgba(255,255,255,0.5)" }}>r</span> raise</span>
            </>
          )}
          {step === "action" && gameState.street !== "preflop" && (
            <>
              <span><span style={{ color: "rgba(255,255,255,0.5)" }}>f</span> checked to me</span>
              <span><span style={{ color: "rgba(255,255,255,0.5)" }}>r</span> facing bet</span>
            </>
          )}
          {step === "villain_type" && (
            <>
              <span><span style={{ color: "rgba(255,255,255,0.5)" }}>1</span> not sure</span>
              <span><span style={{ color: "rgba(255,255,255,0.5)" }}>2</span> weak player</span>
              <span><span style={{ color: "rgba(255,255,255,0.5)" }}>3</span> good player</span>
            </>
          )}
          {(step === "amount" || step === "pot_size" || step === "limper_count") && (
            <span><span style={{ color: "rgba(255,255,255,0.5)" }}>Enter</span> confirm</span>
          )}
          {step === "outcome_select" && (
            <>
              <span><span style={{ color: theme.green }}>1</span> won</span>
              <span><span style={{ color: theme.red }}>2</span> lost</span>
              <span><span style={{ color: theme.textMuted }}>3</span> folded</span>
            </>
          )}
          <span style={{ marginLeft: "auto" }}>
            <span style={{ color: "rgba(255,255,255,0.5)" }}>Esc</span> back
          </span>
        </div>
      )}
    </div>
  )
}

// =============================================================================
// MOUNT
// =============================================================================

const WrappedComponent = withStreamlitConnection(PokerInputComponent)

const root = ReactDOM.createRoot(document.getElementById("root")!)
root.render(
  <React.StrictMode>
    <WrappedComponent />
  </React.StrictMode>
)
