# engine.py — Diamond+ Core Engine v2.1
# +233 CORE CONFIG — TRUE LABOUCHERE IMPLEMENTATION
#
# LOCKED PARAMETERS (from +233-237u/week sim):
# - Banker-only (100%)
# - Session: +30u goal, -60u stop (-40u under Soft Shield)
# - Line: True Labouchere (cancel on win, append on loss)
# - Base Multiplier: Normal = NB-1, Defensive = 0.6×NB (min 1)
# - τ = 0.68 base, dynamic: +0.05 if session>=+20, -0.05 if session<=-300
# - Trailing stop: arm +60u, fire guard +100u, trail 60u
# - Kicker: +50u, fragility < 0.45, disabled when peak >= +60u
# - Line cap: +180u (normal), +120u (defensive)
# - Profit Preserve: Smart Trim + (session>=+20 OR bet>=22) = END SESSION
# - NO glide behavior
#
# CRITICAL: On LOSS, append RAW bet (NB) to line, not scaled bet

from dataclasses import dataclass
from typing import Literal, Optional, List, Dict, Any
import math

Outcome = Literal["W", "L", "T"]


@dataclass
class HandDelta:
    """Returned from each hand to drive UI + modals."""
    stake_units: float
    stake_dollars: float
    delta_units: float
    delta_dollars: float
    side: str = "B"  # Always Banker in v2.0
    reason: Optional[str] = None


class DiamondHybrid:
    """
    +233 Core Config Engine v2.1 — TRUE LABOUCHERE
    
    LOCKED PARAMETERS (DO NOT MODIFY without re-validation):
    - Banker-only (100%)
    - Session: +30u goal, -60u stop (-40u under Soft Shield)
    - Line: True Labouchere (cancel on win, append on loss)
    - τ = 0.68 base (dynamic adjustment based on session P/L)
    - Kicker: +50u, fragility < 0.45, peak < +60u
    - Trailing: arm +60u, guard +100u, trail 60u
    - Line cap: +180u (normal), +120u (defensive)
    - Profit Preserve: session-level exit when Smart Trim + profit qualifier
    """

    # ============================================================
    # SEEDS
    # ============================================================
    SEED_NORMAL: List[float] = [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1.5, 2.0, 2.5, 3.0]
    SEED_DEFENSIVE: List[float] = [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1.25, 1.5, 1.75, 2.0]

    # ============================================================
    # SESSION BOUNDARIES
    # ============================================================
    SESSION_GOAL_U: float = 30.0      # +233 v2.0: +30u
    SESSION_STOP_U: float = -60.0     # Normal stop
    SESSION_STOP_SOFT_SHIELD: float = -40.0  # Soft Shield stop

    # ============================================================
    # LINE GUARDS
    # ============================================================
    LINE_CAP_NORMAL: float = 180.0
    LINE_CAP_DEFENSIVE: float = 120.0
    
    KICKER_U: float = 50.0
    KICKER_FRAG_MAX: float = 0.45

    # ============================================================
    # TRAILING STOP (+233 LOCKED)
    # ============================================================
    TRAIL_ARM_U: float = 60.0          # Arm when line_pl >= +60u
    TRAIL_FIRE_GUARD_U: float = 100.0  # Only fire if peak >= +100u
    TRAIL_DISTANCE_U: float = 60.0     # Fire when line_pl <= peak - 60u

    # ============================================================
    # SMART TRIM (+233 LOCKED — CORRECTED)
    # ============================================================
    # τ is DYNAMIC based on session P/L, NOT Soft Shield
    TAU_BASE: float = 0.68
    TAU_SESSION_GREEN_BONUS: float = 0.05   # Add when session >= +20
    TAU_SESSION_RED_PENALTY: float = 0.05   # Subtract when session <= -300
    TAU_SESSION_GREEN_THRESHOLD: float = 20.0
    TAU_SESSION_RED_THRESHOLD: float = -300.0
    
    # Early line protection (ramp)
    TAU_EARLY_VALUE: float = 0.90
    TAU_EARLY_HANDS: int = 5
    TAU_RAMP_END_HANDS: int = 12
    
    # Gate Set C — Two-tier eligibility
    # Tier 1 Normal: Maturity (A) AND Instability (B)
    GATE_MATURITY_HANDS: int = 14
    GATE_MATURITY_LINE_LEN: int = 14
    GATE_MATURITY_BET: float = 6.0
    GATE_INSTABILITY_LOSS_DENSITY: float = 0.40
    
    # Tier 2 Emergency: Always eligible
    GATE_EMERGENCY_BET: float = 18.0
    GATE_EMERGENCY_LINE_LEN: int = 20

    # ============================================================
    # PROFIT PRESERVE (+233 LOCKED)
    # ============================================================
    PROFIT_PRESERVE_SESSION_THRESHOLD: float = 20.0
    PROFIT_PRESERVE_BET_THRESHOLD: float = 22.0

    # ============================================================
    # FRAGILITY WEIGHTS
    # ============================================================
    FRAG_W_LINE_LENGTH: float = 0.22
    FRAG_W_MAX_NUMBER: float = 0.20
    FRAG_W_CURRENT_BET: float = 0.18
    FRAG_W_LOSS_DENSITY: float = 0.20
    FRAG_W_DISTANCE_COMPLETION: float = 0.10
    FRAG_W_BLOWUP_PROB: float = 0.10

    # ============================================================
    # PAYOUT
    # ============================================================
    BANKER_WIN_MULT: float = 0.95  # 5% commission

    # ============================================================
    # DEFENSIVE MODE TRIGGERS
    # ============================================================
    DEFENSIVE_WEEK_PL_TRIGGER: float = -200.0
    DEFENSIVE_FRAGILITY_TRIGGER: float = 0.75

    def __init__(self, unit_value: float = 1.0):
        self._unit_value: float = float(unit_value)
        
        # Line state (True Labouchere)
        self.line: List[float] = []
        self.line_pl_units: float = 0.0
        self.line_hands_played: int = 0
        self.line_losses: int = 0
        self.line_initial_count: int = 0  # For distance-to-completion
        
        # Trailing stop state
        self.line_peak_pl: float = 0.0
        self.trailing_armed: bool = False
        
        # Session state
        self.session_pl_units: float = 0.0
        self.session_hands: int = 0
        self.line_active: bool = False
        
        # Week state (fed from WeekManager)
        self.week_pl_units: float = 0.0
        
        # Mode flags
        self._defensive_mode: bool = False
        self._soft_shield: bool = False
        
        # Blowup probability table (simplified)
        self._blowup_table: Dict[str, float] = self._build_blowup_table()

    # ============================================================
    # UNIT VALUE
    # ============================================================
    def set_unit_value(self, v: float) -> None:
        self._unit_value = max(0.01, float(v))

    def get_unit_value(self) -> float:
        return self._unit_value

    # ============================================================
    # MODE SETTERS
    # ============================================================
    def set_defensive(self, on: bool) -> None:
        """Set defensive mode (called by WeekManager)."""
        self._defensive_mode = bool(on)

    def set_soft_shield(self, on: bool) -> None:
        """
        Set soft shield mode (called by WeekManager when week_pl <= -300).
        Note: In +233 config, Soft Shield affects session stop but NOT tau.
        """
        self._soft_shield = bool(on)

    @property
    def defensive_mode(self) -> bool:
        return self._defensive_mode

    @property
    def soft_shield(self) -> bool:
        return self._soft_shield

    # ============================================================
    # LINE MANAGEMENT
    # ============================================================
    def start_new_line(self) -> None:
        """Initialize a new line with the appropriate seed."""
        seed = self.SEED_DEFENSIVE if self._defensive_mode else self.SEED_NORMAL
        self.line = list(seed)  # Copy the seed
        self.line_pl_units = 0.0
        self.line_hands_played = 0
        self.line_losses = 0
        self.line_initial_count = len(self.line)
        self.line_peak_pl = 0.0
        self.trailing_armed = False
        self.line_active = True

    def _current_line_cap(self) -> float:
        """Return the current line cap based on mode."""
        return self.LINE_CAP_DEFENSIVE if self._defensive_mode else self.LINE_CAP_NORMAL

    def _current_session_stop(self) -> float:
        """Return the current session stop based on Soft Shield."""
        return self.SESSION_STOP_SOFT_SHIELD if self._soft_shield else self.SESSION_STOP_U

    # ============================================================
    # BET CALCULATION (True Labouchere + Base Multiplier)
    # ============================================================
    def next_bet_units_raw(self) -> float:
        """
        Calculate RAW Labouchere bet (NB) - used for line mechanics.
        
        - Empty line: 0 (line complete)
        - Single number: that number
        - Multiple: first + last
        
        This is the "seed-units" value used for:
        - Appending to line on loss
        - Line completion detection
        """
        if not self.line:
            return 0.0
        if len(self.line) == 1:
            return self.line[0]
        return self.line[0] + self.line[-1]

    def next_bet_units(self) -> float:
        """
        Calculate ACTUAL bet after mode scaling - used for wagering.
        
        Normal Mode: max(1, NB - 1)
        Defensive Mode: max(1, round(0.6 × NB))
        
        This is the "execution-layer" value used for:
        - Actual wager placed
        - P/L calculation
        - Dollar conversion
        """
        nb = self.next_bet_units_raw()
        if nb == 0:
            return 0.0
        
        if self._defensive_mode:
            # Defensive Mode: 0.6 × NB, rounded
            scaled = round(0.6 * nb)
        else:
            # Normal Mode: NB - 1
            scaled = nb - 1
        
        # Minimum bet is always 1 unit
        return max(1.0, scaled)

    def preview_next_bet(self) -> Dict[str, Any]:
        """Return preview of next bet for UI display."""
        raw_units = self.next_bet_units_raw()
        actual_units = self.next_bet_units()
        dollars = actual_units * self._unit_value
        
        return {
            "units": actual_units,
            "raw_units": raw_units,  # For debugging/display
            "effective_units": actual_units,
            "dollars": dollars,
            "side": "B",  # Always Banker
            "line_length": len(self.line),
            "line_pl": self.line_pl_units,
            "session_pl": self.session_pl_units,
            "mode": "defensive" if self._defensive_mode else "normal",
        }

    # ============================================================
    # HAND SETTLEMENT
    # ============================================================
    def settle(self, outcome: Outcome) -> HandDelta:
        """
        Settle a hand outcome using True Labouchere mechanics.
        
        CRITICAL: 
        - ACTUAL BET (scaled) is used for P/L calculation
        - RAW BET (NB) is used for line append on loss
        
        Returns HandDelta with reason if line/session should close.
        """
        # Start line if not active
        if not self.line_active or not self.line:
            self.start_new_line()

        # Get both raw and scaled bets
        raw_bet_units = self.next_bet_units_raw()  # For line mechanics
        actual_bet_units = self.next_bet_units()   # For wagering/P/L
        bet_dollars = actual_bet_units * self._unit_value

        # Calculate delta based on outcome (using ACTUAL bet for P/L)
        if outcome == "T":
            # Tie: no change to line or P/L
            delta_units = 0.0
            delta_dollars = 0.0
        elif outcome == "W":
            # Win: profit at Banker rate, remove first+last from line
            delta_units = actual_bet_units * self.BANKER_WIN_MULT
            delta_dollars = delta_units * self._unit_value
            self._apply_win()
        else:  # "L"
            # Loss: lose the ACTUAL bet amount
            delta_units = -actual_bet_units
            delta_dollars = delta_units * self._unit_value
            # Append RAW bet (NB) to line, not the scaled bet
            self._apply_loss(raw_bet_units)

        # Update P/L trackers
        self.line_pl_units += delta_units
        self.session_pl_units += delta_units
        self.line_hands_played += 1
        self.session_hands += 1

        # Update trailing stop tracking
        if self.line_pl_units > self.line_peak_pl:
            self.line_peak_pl = self.line_pl_units
        if self.line_pl_units >= self.TRAIL_ARM_U:
            self.trailing_armed = True

        # Check exit conditions (priority order)
        reason = self._check_exits()

        return HandDelta(
            stake_units=actual_bet_units,
            stake_dollars=bet_dollars,
            delta_units=delta_units,
            delta_dollars=delta_dollars,
            side="B",
            reason=reason,
        )

    def _apply_win(self) -> None:
        """Apply win: remove first and last numbers from line."""
        if len(self.line) >= 2:
            self.line = self.line[1:-1]
        elif len(self.line) == 1:
            self.line = []
        # len == 0: already empty, nothing to do

    def _apply_loss(self, bet_units: float) -> None:
        """Apply loss: append bet amount to end of line."""
        self.line.append(bet_units)
        self.line_losses += 1

    # ============================================================
    # EXIT CHECKS (Priority Order)
    # ============================================================
    def _check_exits(self) -> Optional[str]:
        """
        Check all exit conditions in priority order.
        Returns reason string if exit triggered, None otherwise.
        
        PRIORITY ORDER (from +233 spec):
        1. Line Complete (array empty)
        2. Line Cap (+180u / +120u) — hard ceiling
        3. Trailing Stop — protects big peaks
        4. Smart Trim (with Profit Preserve branching) — risk control
        5. Kicker — ONLY if trailing NOT armed (peak < +60u)
        6. Session Goal (+30u)
        7. Session Stop (-60u / -40u)
        """
        # PRIORITY 1: Line Complete (True Labouchere)
        if len(self.line) == 0:
            self.line_active = False
            return "line_complete"

        # PRIORITY 2: Line Cap (hard ceiling)
        line_cap = self._current_line_cap()
        if self.line_pl_units >= line_cap:
            self.line_active = False
            return "line_cap"

        # PRIORITY 3: Trailing Stop (protects big peaks)
        if self._trailing_stop_fires():
            self.line_active = False
            return "trailing_stop"

        # PRIORITY 4: Smart Trim (with Profit Preserve branching)
        smart_trim_result = self._smart_trim_check()
        if smart_trim_result == "profit_preserve":
            # Profit Preserve: END SESSION (not just line)
            self.line_active = False
            return "profit_preserve"
        elif smart_trim_result == "smart_trim":
            # Normal Smart Trim: END LINE only
            self.line_active = False
            return "smart_trim"

        # PRIORITY 5: Kicker (+50u, fragility < 0.45)
        # CRITICAL: Kicker is DISABLED once trailing arms (peak >= +60u)
        if self._kicker_fires():
            self.line_active = False
            return "kicker"

        # PRIORITY 6: Session Goal
        if self.session_pl_units >= self.SESSION_GOAL_U:
            return "session_goal"
        
        # PRIORITY 7: Session Stop
        session_stop = self._current_session_stop()
        if self.session_pl_units <= session_stop:
            return "session_stop"

        return None

    def _smart_trim_check(self) -> Optional[str]:
        """
        Check Smart Trim with Profit Preserve branching.
        
        Returns:
        - "profit_preserve" if Smart Trim fires AND profit qualifier met (SESSION close)
        - "smart_trim" if Smart Trim fires WITHOUT profit qualifier (LINE close)
        - None if Smart Trim doesn't fire
        
        +233 LOCKED LOGIC:
        1. Check gates (two-tier: normal AND/OR emergency)
        2. Check fragility >= τ (dynamic based on session P/L)
        3. If fires, check Profit Preserve qualifier
        """
        # Must be in profit for Smart Trim
        if self.line_pl_units <= 0:
            return None

        # Check gates (two-tier system)
        if not self._smart_trim_gates_passed():
            return None

        # Calculate dynamic τ based on session P/L
        tau = self._tau_for_session()
        
        # Apply early-line ramp (hands 1-5 use higher τ)
        tau = self._apply_tau_ramp(tau)
        
        # Check fragility against τ
        frag = self._fused_fragility_score()
        if frag < tau:
            return None

        # Smart Trim fires! Now check Profit Preserve qualifier
        # Use SCALED bet for risk threshold (actual exposure)
        actual_bet = self.next_bet_units()
        
        profit_preserve_qualifies = (
            self.session_pl_units >= self.PROFIT_PRESERVE_SESSION_THRESHOLD or
            actual_bet >= self.PROFIT_PRESERVE_BET_THRESHOLD
        )
        
        if profit_preserve_qualifies:
            return "profit_preserve"
        else:
            return "smart_trim"

    def _smart_trim_gates_passed(self) -> bool:
        """
        Check Smart Trim eligibility gates (Gate Set C — two-tier).
        
        Tier 1 (Normal): Maturity AND Instability
        Tier 2 (Emergency): Always eligible if extreme conditions
        
        NOTE: We use the SCALED bet (actual wager) for gate checks,
        as the thresholds are about real risk exposure.
        
        Returns True if eligible to check fragility.
        """
        actual_bet = self.next_bet_units()  # Scaled bet (NB-1 or 0.6×NB)
        line_len = len(self.line)
        
        # TIER 2: Emergency override (always eligible)
        if actual_bet >= self.GATE_EMERGENCY_BET:
            return True
        if line_len >= self.GATE_EMERGENCY_LINE_LEN:
            return True
        
        # TIER 1: Normal gate (Maturity AND Instability)
        
        # A) Maturity condition (any one)
        maturity_met = (
            self.line_hands_played >= self.GATE_MATURITY_HANDS or
            line_len >= self.GATE_MATURITY_LINE_LEN or
            actual_bet >= self.GATE_MATURITY_BET
        )
        
        if not maturity_met:
            return False
        
        # B) Instability condition (any one)
        loss_density = self.line_losses / max(1, self.line_hands_played)
        tau = self._tau_for_session()
        frag = self._fused_fragility_score()
        
        instability_met = (
            loss_density >= self.GATE_INSTABILITY_LOSS_DENSITY or
            frag >= tau  # This is checked again later, but gates need it
        )
        
        return instability_met

    def _tau_for_session(self) -> float:
        """
        Calculate τ threshold based on SESSION P/L.
        
        +233 LOCKED FORMULA:
        tau = 0.68 + (0.05 if session >= +20) - (0.05 if session <= -300)
        
        Result:
        - Session >= +20: τ = 0.73 (harder to trim, let it run)
        - Session -299 to +19: τ = 0.68 (base)
        - Session <= -300: τ = 0.63 (easier to trim, cut losses)
        
        NOTE: Soft Shield does NOT affect τ in +233 config.
        """
        tau = self.TAU_BASE
        
        if self.session_pl_units >= self.TAU_SESSION_GREEN_THRESHOLD:
            tau += self.TAU_SESSION_GREEN_BONUS
        
        if self.session_pl_units <= self.TAU_SESSION_RED_THRESHOLD:
            tau -= self.TAU_SESSION_RED_PENALTY
        
        return tau

    def _apply_tau_ramp(self, tau_target: float) -> float:
        """
        Apply early-line protection ramp to τ.
        
        - Hands 1-5: τ = 0.90 (very conservative early)
        - Hands 6-11: linear ramp from 0.90 → τ_target
        - Hands 12+: τ = τ_target
        """
        hands = self.line_hands_played
        
        if hands <= self.TAU_EARLY_HANDS:
            return self.TAU_EARLY_VALUE
        
        if hands >= self.TAU_RAMP_END_HANDS:
            return tau_target
        
        # Linear interpolation for hands 6-11
        ramp_range = self.TAU_RAMP_END_HANDS - self.TAU_EARLY_HANDS
        progress = (hands - self.TAU_EARLY_HANDS) / ramp_range
        return self.TAU_EARLY_VALUE - progress * (self.TAU_EARLY_VALUE - tau_target)

    def _kicker_fires(self) -> bool:
        """
        Check if Kicker should fire.
        
        Kicker is an early profit-take for clean momentum lines.
        
        Requirements:
        1. line_pl >= +50u
        2. fragility < 0.45 (line is still healthy)
        3. line_peak < +60u (trailing NOT armed yet)
        
        The peak guard is critical: once trailing arms at +60u,
        Kicker is disabled and trailing owns the line from that point.
        """
        # Must have sufficient profit
        if self.line_pl_units < self.KICKER_U:
            return False
        
        # Trailing must NOT be armed (peak < +60u)
        # Once peak >= +60u, the line has earned the right to run
        if self.line_peak_pl >= self.TRAIL_ARM_U:
            return False
        
        # Fragility must be low (line is still healthy)
        frag = self._fused_fragility_score()
        if frag >= self.KICKER_FRAG_MAX:
            return False
        
        return True

    def _trailing_stop_fires(self) -> bool:
        """
        Check if trailing stop should fire.
        
        Requirements:
        1. Must be armed (line_pl reached +60u at some point)
        2. Peak must have reached +100u (fire guard)
        3. Current line_pl must be 60u below peak
        """
        if not self.trailing_armed:
            return False
        
        if self.line_peak_pl < self.TRAIL_FIRE_GUARD_U:
            return False
        
        return self.line_pl_units <= (self.line_peak_pl - self.TRAIL_DISTANCE_U)

    # ============================================================
    # FRAGILITY CALCULATION
    # ============================================================
    def _fused_fragility_score(self) -> float:
        """
        Calculate 6-component fused fragility score.
        
        Components (weights):
        - Line length (22%): longer = more fragile
        - Max number in line (20%): higher = more fragile
        - Current bet (18%): larger = more fragile
        - Loss density (20%): more losses = more fragile
        - Distance to completion (10%): further = more fragile
        - Blowup probability (10%): from lookup table
        
        Returns value in [0, 1].
        """
        if not self.line:
            return 0.0

        # Component 1: Line length (normalized to 20)
        line_length_norm = min(len(self.line) / 20.0, 1.0)
        
        # Component 2: Max number in line (normalized to 10)
        max_num = max(self.line) if self.line else 1.0
        max_num_norm = min(max_num / 10.0, 1.0)
        
        # Component 3: Current bet (normalized to 12)
        current_bet = self.next_bet_units()
        current_bet_norm = min(current_bet / 12.0, 1.0)
        
        # Component 4: Loss density
        loss_density = self.line_losses / max(1, self.line_hands_played)
        
        # Component 5: Distance to completion
        if self.line_initial_count > 0:
            cancelled = self.line_initial_count - len(self.line)
            # More cancelled = closer to completion = less fragile
            # So we invert: further from completion = more fragile
            distance_completion = 1.0 - (cancelled / self.line_initial_count)
        else:
            distance_completion = 1.0
        
        # Component 6: Blowup probability (from table)
        blowup_prob = self._lookup_blowup_prob()
        
        # Weighted sum
        score = (
            self.FRAG_W_LINE_LENGTH * line_length_norm +
            self.FRAG_W_MAX_NUMBER * max_num_norm +
            self.FRAG_W_CURRENT_BET * current_bet_norm +
            self.FRAG_W_LOSS_DENSITY * loss_density +
            self.FRAG_W_DISTANCE_COMPLETION * distance_completion +
            self.FRAG_W_BLOWUP_PROB * blowup_prob
        )
        
        # Clamp to [0, 1]
        return max(0.0, min(1.0, score))

    def _lookup_blowup_prob(self) -> float:
        """
        Look up blowup probability from table based on current state.
        
        Uses simplified bucketing based on:
        - Line length
        - Max bet seen
        - Loss density
        """
        if not self.line:
            return 0.0
        
        # Bucket line length
        line_len = len(self.line)
        if line_len <= 10:
            len_bucket = "short"
        elif line_len <= 16:
            len_bucket = "medium"
        else:
            len_bucket = "long"
        
        # Bucket max number
        max_num = max(self.line)
        if max_num <= 3:
            max_bucket = "low"
        elif max_num <= 6:
            max_bucket = "medium"
        else:
            max_bucket = "high"
        
        # Bucket loss density
        loss_density = self.line_losses / max(1, self.line_hands_played)
        if loss_density <= 0.3:
            loss_bucket = "low"
        elif loss_density <= 0.5:
            loss_bucket = "medium"
        else:
            loss_bucket = "high"
        
        key = f"{len_bucket}_{max_bucket}_{loss_bucket}"
        return self._blowup_table.get(key, 0.5)

    def _build_blowup_table(self) -> Dict[str, float]:
        """Build the blowup probability lookup table."""
        return {
            # Short line
            "short_low_low": 0.05,
            "short_low_medium": 0.10,
            "short_low_high": 0.15,
            "short_medium_low": 0.10,
            "short_medium_medium": 0.20,
            "short_medium_high": 0.30,
            "short_high_low": 0.15,
            "short_high_medium": 0.30,
            "short_high_high": 0.45,
            
            # Medium line
            "medium_low_low": 0.15,
            "medium_low_medium": 0.25,
            "medium_low_high": 0.35,
            "medium_medium_low": 0.25,
            "medium_medium_medium": 0.40,
            "medium_medium_high": 0.55,
            "medium_high_low": 0.35,
            "medium_high_medium": 0.55,
            "medium_high_high": 0.70,
            
            # Long line
            "long_low_low": 0.30,
            "long_low_medium": 0.45,
            "long_low_high": 0.60,
            "long_medium_low": 0.45,
            "long_medium_medium": 0.60,
            "long_medium_high": 0.75,
            "long_high_low": 0.60,
            "long_high_medium": 0.75,
            "long_high_high": 0.90,
        }

    # ============================================================
    # SESSION/LINE RESET
    # ============================================================
    def reset_for_new_session(self) -> None:
        """Reset session state (called when session closes)."""
        self.session_pl_units = 0.0
        self.session_hands = 0
        self.line_active = False
        self.line = []
        self.line_pl_units = 0.0
        self.line_hands_played = 0
        self.line_losses = 0
        self.line_initial_count = 0
        self.line_peak_pl = 0.0
        self.trailing_armed = False

    def reset_for_new_line(self) -> None:
        """Reset line state only (session continues)."""
        self.line = []
        self.line_pl_units = 0.0
        self.line_hands_played = 0
        self.line_losses = 0
        self.line_initial_count = 0
        self.line_peak_pl = 0.0
        self.trailing_armed = False
        self.line_active = False

    # ============================================================
    # COMPATIBILITY METHODS
    # ============================================================
    def update_week_tone(self, tone: Dict[str, Any]) -> None:
        """Update engine state from WeekManager tone."""
        self._defensive_mode = bool(tone.get("defensive", False))
        self._soft_shield = bool(tone.get("soft_shield", False))

    def apply_week_tone(self, tone: Dict[str, Any]) -> None:
        """Alias for update_week_tone (compatibility)."""
        self.update_week_tone(tone)

    # ============================================================
    # STATE PERSISTENCE
    # ============================================================
    def export_state(self) -> Dict[str, Any]:
        """Export engine state for persistence."""
        return {
            "unit_value": self._unit_value,
            "line": list(self.line),
            "line_pl_units": self.line_pl_units,
            "line_hands_played": self.line_hands_played,
            "line_losses": self.line_losses,
            "line_initial_count": self.line_initial_count,
            "line_peak_pl": self.line_peak_pl,
            "trailing_armed": self.trailing_armed,
            "session_pl_units": self.session_pl_units,
            "session_hands": self.session_hands,
            "line_active": self.line_active,
            "week_pl_units": self.week_pl_units,
            "defensive_mode": self._defensive_mode,
            "soft_shield": self._soft_shield,
        }

    def import_state(self, data: Dict[str, Any]) -> None:
        """Import engine state from persistence."""
        if not isinstance(data, dict):
            return

        def _f(key: str, default: float = 0.0) -> float:
            try:
                return float(data.get(key, default))
            except:
                return default

        def _i(key: str, default: int = 0) -> int:
            try:
                return int(data.get(key, default))
            except:
                return default

        def _b(key: str, default: bool = False) -> bool:
            try:
                return bool(data.get(key, default))
            except:
                return default

        self._unit_value = _f("unit_value", 1.0)
        
        # Line state
        raw_line = data.get("line", [])
        if isinstance(raw_line, list):
            self.line = [float(x) for x in raw_line]
        else:
            self.line = []
        
        self.line_pl_units = _f("line_pl_units", 0.0)
        self.line_hands_played = _i("line_hands_played", 0)
        self.line_losses = _i("line_losses", 0)
        self.line_initial_count = _i("line_initial_count", 0)
        self.line_peak_pl = _f("line_peak_pl", 0.0)
        self.trailing_armed = _b("trailing_armed", False)
        
        # Session state
        self.session_pl_units = _f("session_pl_units", 0.0)
        self.session_hands = _i("session_hands", 0)
        self.line_active = _b("line_active", False)
        
        # Week state
        self.week_pl_units = _f("week_pl_units", 0.0)
        
        # Mode flags
        self._defensive_mode = _b("defensive_mode", False)
        self._soft_shield = _b("soft_shield", False)

    def load_state(self, data: Dict[str, Any]) -> None:
        """Alias for import_state (compatibility)."""
        self.import_state(data)

    # ============================================================
    # DEPRECATED METHODS (kept for compatibility)
    # ============================================================
    def get_recommended_side(self) -> str:
        """Always returns Banker in v2.0."""
        return "B"

    def choose_side(self) -> str:
        """Always returns Banker in v2.0."""
        return "B"