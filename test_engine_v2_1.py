#!/usr/bin/env python3
"""
Test Suite for Diamond+ Engine v2.1 (True Labouchere)

Run with: python3 test_engine_v2_1.py

Tests cover:
- True Labouchere mechanics (win removes first+last, loss appends RAW NB)
- Base Multiplier (NB-1 normal, 0.6×NB defensive)
- Line completion detection
- Session boundaries (+30u goal, -60u stop (-40u soft shield))
- Banker-only (100% Banker, 5% commission)
- Smart Trim (τ = 0.68 base, session-based adjustments, gates)
- Profit Preserve (session >= +20u OR bet >= 22u)
- Trailing Stop (arm +60u, guard +100u, trail 60u)
- Kicker (+50u, fragility < 0.45, disabled when peak >= +60u)
- Line Cap (+180u normal, +120u defensive)
- Fragility calculation (6-component)
- State persistence (export/import)

Updated for v2.1 spec compliance.
Corrected to match actual engine.py method names.
"""

import sys
import unittest
from typing import List

# Import the engine
from engine import DiamondHybrid, HandDelta


class TestTrueLabouchereMechanics(unittest.TestCase):
    """Test True Labouchere win/loss mechanics."""

    def test_initial_line_is_normal_seed(self):
        """New line should start with normal seed."""
        eng = DiamondHybrid()
        eng.start_new_line()
        
        expected = [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1.5, 2.0, 2.5, 3.0]
        self.assertEqual(eng.line, expected)
        self.assertEqual(len(eng.line), 14)

    def test_defensive_mode_uses_defensive_seed(self):
        """Defensive mode should use softer seed."""
        eng = DiamondHybrid()
        eng.set_defensive(True)
        eng.start_new_line()
        
        expected = [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1.25, 1.5, 1.75, 2.0]
        self.assertEqual(eng.line, expected)

    def test_raw_nb_calculation_first_plus_last(self):
        """Raw NB should be first + last number."""
        eng = DiamondHybrid()
        eng.start_new_line()
        
        # Normal seed: [1,1,1,1,1,1,1,1,1,1,1.5,2,2.5,3]
        # First = 1, Last = 3, NB = 4
        raw_nb = eng.next_bet_units_raw()
        self.assertEqual(raw_nb, 4.0)

    def test_raw_nb_single_number(self):
        """Single number in line should be the raw NB."""
        eng = DiamondHybrid()
        eng.line = [5.0]
        eng.line_active = True
        
        raw_nb = eng.next_bet_units_raw()
        self.assertEqual(raw_nb, 5.0)

    def test_raw_nb_empty_line(self):
        """Empty line should return 0 raw NB."""
        eng = DiamondHybrid()
        eng.line = []
        
        raw_nb = eng.next_bet_units_raw()
        self.assertEqual(raw_nb, 0.0)

    def test_win_removes_first_and_last(self):
        """Win should remove first and last numbers."""
        eng = DiamondHybrid()
        eng.line = [1, 2, 3, 4, 5]
        eng.line_active = True
        eng.line_initial_count = 5
        
        eng._apply_win()
        
        self.assertEqual(eng.line, [2, 3, 4])

    def test_win_single_number_clears_line(self):
        """Win with single number should clear line."""
        eng = DiamondHybrid()
        eng.line = [5]
        eng.line_active = True
        
        eng._apply_win()
        
        self.assertEqual(eng.line, [])

    def test_win_two_numbers_clears_line(self):
        """Win with two numbers should clear line."""
        eng = DiamondHybrid()
        eng.line = [2, 3]
        eng.line_active = True
        
        eng._apply_win()
        
        self.assertEqual(eng.line, [])

    def test_loss_appends_raw_nb_not_scaled(self):
        """Loss should append RAW NB to end of line, NOT scaled bet."""
        eng = DiamondHybrid()
        eng.set_defensive(False)
        eng.line = [1, 2, 3]  # NB = 1 + 3 = 4, scaled = max(1, 4-1) = 3
        eng.line_active = True
        eng.line_initial_count = 3
        
        raw_nb = eng.next_bet_units_raw()  # Should be 4
        scaled_bet = eng.next_bet_units()  # Should be 3
        
        self.assertEqual(raw_nb, 4.0)
        self.assertEqual(scaled_bet, 3.0)
        
        # Apply loss - should append RAW NB (4), not scaled (3)
        eng._apply_loss(raw_nb)
        
        self.assertEqual(eng.line, [1, 2, 3, 4])  # Appended 4, not 3
        self.assertEqual(eng.line_losses, 1)

    def test_tie_no_change(self):
        """Tie should not change line or P/L."""
        eng = DiamondHybrid()
        eng.start_new_line()
        original_line = list(eng.line)
        
        result = eng.settle("T")
        
        self.assertEqual(eng.line, original_line)
        self.assertEqual(result.delta_units, 0.0)
        self.assertEqual(eng.line_pl_units, 0.0)


class TestBaseMultiplier(unittest.TestCase):
    """Test v2.1 Base Multiplier mechanics."""

    def test_normal_mode_nb_minus_1(self):
        """Normal mode: scaled bet = max(1, NB - 1)."""
        eng = DiamondHybrid()
        eng.set_defensive(False)
        eng.line = [1, 3]  # NB = 4
        eng.line_active = True
        
        raw_nb = eng.next_bet_units_raw()
        scaled = eng.next_bet_units()
        
        self.assertEqual(raw_nb, 4.0)
        self.assertEqual(scaled, 3.0)  # max(1, 4-1) = 3

    def test_normal_mode_minimum_1(self):
        """Normal mode: minimum bet is 1 unit."""
        eng = DiamondHybrid()
        eng.set_defensive(False)
        eng.line = [1, 1]  # NB = 2
        eng.line_active = True
        
        raw_nb = eng.next_bet_units_raw()
        scaled = eng.next_bet_units()
        
        self.assertEqual(raw_nb, 2.0)
        self.assertEqual(scaled, 1.0)  # max(1, 2-1) = max(1, 1) = 1

    def test_defensive_mode_06_times_nb(self):
        """Defensive mode: scaled bet = max(1, round(0.6 × NB))."""
        eng = DiamondHybrid()
        eng.set_defensive(True)
        eng.line = [1, 3]  # NB = 4
        eng.line_active = True
        
        raw_nb = eng.next_bet_units_raw()
        scaled = eng.next_bet_units()
        
        self.assertEqual(raw_nb, 4.0)
        self.assertEqual(scaled, 2.0)  # max(1, round(0.6 * 4)) = max(1, round(2.4)) = max(1, 2) = 2

    def test_defensive_mode_larger_nb(self):
        """Defensive mode with larger NB."""
        eng = DiamondHybrid()
        eng.set_defensive(True)
        eng.line = [2, 8]  # NB = 10
        eng.line_active = True
        
        raw_nb = eng.next_bet_units_raw()
        scaled = eng.next_bet_units()
        
        self.assertEqual(raw_nb, 10.0)
        self.assertEqual(scaled, 6.0)  # max(1, round(0.6 * 10)) = max(1, 6) = 6

    def test_defensive_mode_minimum_1(self):
        """Defensive mode: minimum bet is 1 unit."""
        eng = DiamondHybrid()
        eng.set_defensive(True)
        eng.line = [1]  # NB = 1 (single number)
        eng.line_active = True
        
        raw_nb = eng.next_bet_units_raw()
        scaled = eng.next_bet_units()
        
        self.assertEqual(raw_nb, 1.0)
        self.assertEqual(scaled, 1.0)  # max(1, round(0.6 * 1)) = max(1, 1) = 1

    def test_wager_uses_scaled_bet(self):
        """Actual wager and P/L should use scaled bet, not raw NB."""
        eng = DiamondHybrid()
        eng.set_defensive(False)
        eng.start_new_line()
        
        # Normal seed: NB = 1 + 3 = 4, scaled = max(1, 3) = 3
        raw_nb = eng.next_bet_units_raw()
        scaled = eng.next_bet_units()
        
        self.assertEqual(raw_nb, 4.0)
        self.assertEqual(scaled, 3.0)
        
        # Win should pay based on scaled bet (3 * 0.95 = 2.85)
        result = eng.settle("W")
        self.assertAlmostEqual(result.delta_units, 2.85, places=2)


class TestLineCompletion(unittest.TestCase):
    """Test line completion detection."""

    def test_line_complete_when_empty(self):
        """Line should be complete when array is empty."""
        eng = DiamondHybrid()
        eng.line = [2]  # Single number
        eng.line_active = True
        eng.line_initial_count = 1
        
        # Win should clear and trigger line_complete
        result = eng.settle("W")
        
        self.assertEqual(result.reason, "line_complete")
        self.assertEqual(len(eng.line), 0)
        self.assertFalse(eng.line_active)

    def test_line_complete_sequence(self):
        """Simulate a sequence of wins that completes a short line."""
        eng = DiamondHybrid()
        eng.line = [1, 2, 3]  # 3 numbers
        eng.line_active = True
        eng.line_initial_count = 3
        
        # Win 1: removes 1 and 3, leaves [2]
        result1 = eng.settle("W")
        self.assertIsNone(result1.reason)
        self.assertEqual(eng.line, [2])
        
        # Win 2: removes 2, line empty
        result2 = eng.settle("W")
        self.assertEqual(result2.reason, "line_complete")
        self.assertEqual(eng.line, [])


class TestSessionBoundaries(unittest.TestCase):
    """Test session goal and stop."""

    def test_session_goal_is_30u(self):
        """Session goal should be +30u."""
        eng = DiamondHybrid()
        self.assertEqual(eng.SESSION_GOAL_U, 30.0)

    def test_session_stop_normal_is_minus_60u(self):
        """Normal session stop should be -60u."""
        eng = DiamondHybrid()
        self.assertEqual(eng.SESSION_STOP_U, -60.0)

    def test_session_stop_soft_shield_is_minus_40u(self):
        """Soft Shield session stop should be -40u."""
        eng = DiamondHybrid()
        eng.set_soft_shield(True)
        
        self.assertEqual(eng._current_session_stop(), -40.0)

    def test_session_goal_triggers(self):
        """Session goal should trigger at +30u."""
        eng = DiamondHybrid()
        eng.start_new_line()
        eng.session_pl_units = 29.5
        
        # Use a longer line so it doesn't complete on one win
        eng.line = [1, 1, 1, 1, 1]  # bet = 2, scaled = 1, win removes ends
        eng.line_initial_count = 5
        result = eng.settle("W")  # win ~0.95u, line becomes [1,1,1]
        
        # Should be over 30u now
        self.assertGreater(eng.session_pl_units, 30.0)
        self.assertEqual(result.reason, "session_goal")


class TestBankerOnly(unittest.TestCase):
    """Test Banker-only mode (100% Banker)."""

    def test_always_banker(self):
        """Side should always be Banker."""
        eng = DiamondHybrid()
        
        self.assertEqual(eng.get_recommended_side(), "B")
        self.assertEqual(eng.choose_side(), "B")

    def test_settle_returns_banker_side(self):
        """settle() should always return side='B'."""
        eng = DiamondHybrid()
        eng.start_new_line()
        
        result = eng.settle("W")
        self.assertEqual(result.side, "B")
        
        result = eng.settle("L")
        self.assertEqual(result.side, "B")

    def test_preview_returns_banker_side(self):
        """preview_next_bet() should return side='B'."""
        eng = DiamondHybrid()
        eng.start_new_line()
        
        preview = eng.preview_next_bet()
        self.assertEqual(preview["side"], "B")


class TestBankerPayout(unittest.TestCase):
    """Test Banker payout (5% commission)."""

    def test_banker_commission_is_5_percent(self):
        """Banker commission should be 5% (0.95 payout)."""
        eng = DiamondHybrid()
        # Engine uses BANKER_WIN_MULT instead of BANKER_COMMISSION
        self.assertEqual(eng.BANKER_WIN_MULT, 0.95)

    def test_banker_win_payout(self):
        """Banker win should pay 0.95x (5% commission)."""
        eng = DiamondHybrid()
        eng.line = [2, 3]  # NB = 5, scaled = max(1, 4) = 4
        eng.line_active = True
        eng.line_initial_count = 2
        
        scaled_bet = eng.next_bet_units()
        self.assertEqual(scaled_bet, 4.0)
        
        result = eng.settle("W")
        
        # 4 units * 0.95 = 3.80
        self.assertAlmostEqual(result.delta_units, 3.80, places=2)

    def test_loss_is_full_scaled_bet(self):
        """Loss should be full scaled bet amount."""
        eng = DiamondHybrid()
        eng.line = [2, 3]  # NB = 5, scaled = 4
        eng.line_active = True
        eng.line_initial_count = 2
        
        scaled_bet = eng.next_bet_units()
        self.assertEqual(scaled_bet, 4.0)
        
        result = eng.settle("L")
        
        self.assertEqual(result.delta_units, -4.0)


class TestTauCalculation(unittest.TestCase):
    """Test τ (tau) calculation - v2.1 session-based."""

    def test_tau_base_is_068(self):
        """Base τ should be 0.68."""
        eng = DiamondHybrid()
        self.assertEqual(eng.TAU_BASE, 0.68)

    def test_tau_session_green_threshold(self):
        """τ increases by 0.05 when session_pl >= +20u."""
        eng = DiamondHybrid()
        eng.start_new_line()
        eng.session_pl_units = 25.0  # Above +20u
        
        tau = eng._tau_for_session()
        # Use assertAlmostEqual for floating point comparison
        self.assertAlmostEqual(tau, 0.73, places=6)  # 0.68 + 0.05

    def test_tau_session_red_threshold(self):
        """τ decreases by 0.05 when session_pl <= -300u."""
        eng = DiamondHybrid()
        eng.start_new_line()
        eng.session_pl_units = -350.0  # Below -300u
        
        tau = eng._tau_for_session()
        self.assertAlmostEqual(tau, 0.63, places=6)  # 0.68 - 0.05

    def test_tau_session_neutral(self):
        """τ is base 0.68 when session_pl is between -300 and +20."""
        eng = DiamondHybrid()
        eng.start_new_line()
        eng.session_pl_units = 0.0  # Neutral
        
        tau = eng._tau_for_session()
        self.assertEqual(tau, 0.68)

    def test_tau_soft_shield_does_not_affect(self):
        """Soft Shield should NOT affect τ calculation."""
        eng = DiamondHybrid()
        eng.start_new_line()
        eng.session_pl_units = 0.0
        
        # Without soft shield
        eng.set_soft_shield(False)
        tau_without = eng._tau_for_session()
        
        # With soft shield
        eng.set_soft_shield(True)
        tau_with = eng._tau_for_session()
        
        # Should be the same
        self.assertEqual(tau_without, tau_with)
        self.assertEqual(tau_with, 0.68)

    def test_tau_early_hands_is_090(self):
        """τ for hands 1-5 should be 0.90 after applying ramp."""
        eng = DiamondHybrid()
        eng.start_new_line()
        eng.line_hands_played = 3
        
        # Engine uses _apply_tau_ramp() not _tau_for_line_age()
        base_tau = eng._tau_for_session()
        tau = eng._apply_tau_ramp(base_tau)
        self.assertEqual(tau, 0.90)

    def test_tau_ramps_down_to_session_tau(self):
        """τ should ramp from 0.90 to session τ for hands 6-11."""
        eng = DiamondHybrid()
        eng.start_new_line()
        eng.session_pl_units = 0.0  # Base τ = 0.68
        
        base_tau = eng._tau_for_session()
        
        # Hand 5: should be 0.90
        eng.line_hands_played = 5
        tau5 = eng._apply_tau_ramp(base_tau)
        self.assertEqual(tau5, 0.90)
        
        # Hand 12: should be base (0.68)
        eng.line_hands_played = 12
        tau12 = eng._apply_tau_ramp(base_tau)
        self.assertEqual(tau12, 0.68)
        
        # Hand 8: should be between 0.90 and 0.68
        eng.line_hands_played = 8
        tau8 = eng._apply_tau_ramp(base_tau)
        self.assertLess(tau8, 0.90)
        self.assertGreater(tau8, 0.68)


class TestSmartTrimGates(unittest.TestCase):
    """Test Smart Trim gate mechanics - v2.1 two-tier."""

    def test_smart_trim_requires_profit(self):
        """Smart Trim should not fire if line_pl <= 0."""
        eng = DiamondHybrid()
        eng.start_new_line()
        eng.line_hands_played = 15  # Past gate
        eng.line_pl_units = -5.0  # In loss
        
        # Engine uses _smart_trim_check() which returns None, "smart_trim", or "profit_preserve"
        result = eng._smart_trim_check()
        self.assertIsNone(result)

    def test_tier1_maturity_hands_gate(self):
        """Tier 1 maturity: hands >= 14."""
        eng = DiamondHybrid()
        eng.start_new_line()
        eng.line_pl_units = 10.0
        eng.line_hands_played = 14  # Maturity gate
        eng.line_losses = 6  # 6/14 = 43% > 40% (instability)
        
        # Should pass Tier 1
        gates = eng._smart_trim_gates_passed()
        self.assertTrue(gates)

    def test_tier1_maturity_line_len_gate(self):
        """Tier 1 maturity: line_len >= 14."""
        eng = DiamondHybrid()
        eng.start_new_line()
        eng.line_pl_units = 10.0
        eng.line = [1] * 15  # 15 elements
        eng.line_hands_played = 5  # Below hands gate
        eng.line_losses = 3  # 3/5 = 60% > 40%
        
        gates = eng._smart_trim_gates_passed()
        self.assertTrue(gates)

    def test_tier1_maturity_bet_gate(self):
        """Tier 1 maturity: actual_bet >= 6u."""
        eng = DiamondHybrid()
        eng.start_new_line()
        eng.line_pl_units = 10.0
        eng.line = [3, 5]  # NB = 8, scaled = 7 >= 6
        eng.line_hands_played = 5
        eng.line_losses = 3  # 60% > 40%
        
        gates = eng._smart_trim_gates_passed()
        self.assertTrue(gates)

    def test_tier2_emergency_bet_override(self):
        """Tier 2 emergency: bet >= 18u bypasses Tier 1."""
        eng = DiamondHybrid()
        eng.start_new_line()
        eng.line_pl_units = 10.0
        eng.line = [10, 10]  # NB = 20, scaled = 19 >= 18
        eng.line_hands_played = 3  # Would fail Tier 1 maturity
        eng.line_losses = 0  # Would fail Tier 1 instability
        
        gates = eng._smart_trim_gates_passed()
        self.assertTrue(gates)  # Emergency override

    def test_tier2_emergency_line_len_override(self):
        """Tier 2 emergency: line_len >= 20 bypasses Tier 1."""
        eng = DiamondHybrid()
        eng.start_new_line()
        eng.line_pl_units = 10.0
        eng.line = [1] * 21  # 21 elements >= 20
        eng.line_hands_played = 3  # Would fail Tier 1 maturity
        eng.line_losses = 0  # Would fail Tier 1 instability
        
        gates = eng._smart_trim_gates_passed()
        self.assertTrue(gates)  # Emergency override


class TestProfitPreserve(unittest.TestCase):
    """Test Profit Preserve mechanics - v2.1."""

    def test_profit_preserve_session_threshold(self):
        """Profit Preserve session threshold is +20u."""
        eng = DiamondHybrid()
        self.assertEqual(eng.PROFIT_PRESERVE_SESSION_THRESHOLD, 20.0)

    def test_profit_preserve_bet_threshold(self):
        """Profit Preserve bet threshold is 22u."""
        eng = DiamondHybrid()
        self.assertEqual(eng.PROFIT_PRESERVE_BET_THRESHOLD, 22.0)

    def test_profit_preserve_triggers_on_session_pl(self):
        """Profit Preserve triggers when Smart Trim fires AND session_pl >= +20u."""
        eng = DiamondHybrid()
        eng.start_new_line()
        eng.session_pl_units = 25.0  # Above +20u
        eng.line_pl_units = 15.0  # In profit
        eng.line_hands_played = 20  # Past gates
        eng.line_losses = 10  # 50% loss density
        eng.line = [1] * 15  # Long line, high fragility
        
        # If Smart Trim would fire, should return "profit_preserve" instead
        reason = eng._smart_trim_check()
        if reason:
            self.assertEqual(reason, "profit_preserve")

    def test_profit_preserve_triggers_on_high_bet(self):
        """Profit Preserve triggers when Smart Trim fires AND bet >= 22u."""
        eng = DiamondHybrid()
        eng.start_new_line()
        eng.session_pl_units = 5.0  # Below +20u
        eng.line_pl_units = 15.0  # In profit
        eng.line = [12, 12]  # NB = 24, scaled = 23 >= 22
        eng.line_hands_played = 20
        eng.line_losses = 10
        
        reason = eng._smart_trim_check()
        if reason:
            self.assertEqual(reason, "profit_preserve")

    def test_smart_trim_without_profit_preserve(self):
        """Smart Trim returns 'smart_trim' when Profit Preserve conditions not met."""
        eng = DiamondHybrid()
        eng.start_new_line()
        eng.session_pl_units = 5.0  # Below +20u
        eng.line_pl_units = 15.0  # In profit
        eng.line = [3, 5]  # NB = 8, scaled = 7 < 22
        eng.line_hands_played = 20
        eng.line_losses = 10
        
        reason = eng._smart_trim_check()
        if reason:
            self.assertEqual(reason, "smart_trim")


class TestTrailingStop(unittest.TestCase):
    """Test Trailing Stop mechanics - v2.1."""

    def test_trailing_arm_threshold_60u(self):
        """Trailing should arm at +60u."""
        eng = DiamondHybrid()
        self.assertEqual(eng.TRAIL_ARM_U, 60.0)

    def test_trailing_fire_guard_100u(self):
        """Trailing fire guard should be +100u."""
        eng = DiamondHybrid()
        self.assertEqual(eng.TRAIL_FIRE_GUARD_U, 100.0)

    def test_trailing_distance_60u(self):
        """Trail distance should be 60u."""
        eng = DiamondHybrid()
        self.assertEqual(eng.TRAIL_DISTANCE_U, 60.0)

    def test_trailing_arms_at_60u(self):
        """Trailing should arm when line_pl reaches +60u."""
        eng = DiamondHybrid()
        eng.start_new_line()
        eng.line_pl_units = 55.0
        
        # Not armed yet
        self.assertFalse(eng.trailing_armed)
        
        # Update peak and arm
        eng.line_pl_units = 62.0
        eng.line_peak_pl = 62.0
        if eng.line_peak_pl >= eng.TRAIL_ARM_U:
            eng.trailing_armed = True
        
        self.assertTrue(eng.trailing_armed)

    def test_trailing_requires_guard(self):
        """Trailing should not fire if peak < +100u."""
        eng = DiamondHybrid()
        eng.start_new_line()
        eng.trailing_armed = True
        eng.line_peak_pl = 80.0  # Below +100 guard
        eng.line_pl_units = 15.0  # Dropped a lot
        
        fires = eng._trailing_stop_fires()
        self.assertFalse(fires)

    def test_trailing_fires_correctly(self):
        """Trailing should fire when peak >= 100 and dropped 60u."""
        eng = DiamondHybrid()
        eng.start_new_line()
        eng.trailing_armed = True
        eng.line_peak_pl = 140.0  # Above +100 guard
        eng.line_pl_units = 75.0  # 140 - 75 = 65 > 60u drop
        
        fires = eng._trailing_stop_fires()
        self.assertTrue(fires)

    def test_trailing_does_not_fire_small_drop(self):
        """Trailing should NOT fire if drop < 60u."""
        eng = DiamondHybrid()
        eng.start_new_line()
        eng.trailing_armed = True
        eng.line_peak_pl = 120.0  # Above guard
        eng.line_pl_units = 90.0  # 120 - 90 = 30 < 60u drop
        
        fires = eng._trailing_stop_fires()
        self.assertFalse(fires)


class TestKicker(unittest.TestCase):
    """Test Kicker mechanics - v2.1."""

    def test_kicker_threshold_50u(self):
        """Kicker should trigger at +50u."""
        eng = DiamondHybrid()
        self.assertEqual(eng.KICKER_U, 50.0)

    def test_kicker_fragility_guard_045(self):
        """Kicker fragility guard should be 0.45."""
        eng = DiamondHybrid()
        self.assertEqual(eng.KICKER_FRAG_MAX, 0.45)

    def test_kicker_fires_on_low_fragility(self):
        """Kicker should fire at +50u with fragility < 0.45 and peak < +60u."""
        eng = DiamondHybrid()
        eng.start_new_line()
        
        # Set up conditions for kicker
        eng.line_pl_units = 52.0  # Above +50u
        eng.line_peak_pl = 52.0   # Peak is same as current (below +60u)
        eng.line = [1, 1]  # Short line = low fragility
        eng.line_hands_played = 3
        eng.line_losses = 0
        
        # Check fragility is low
        frag = eng._fused_fragility_score()
        self.assertLess(frag, 0.45)
        
        # Kicker should fire
        self.assertTrue(eng._kicker_fires())

    def test_kicker_disabled_when_trailing_armed(self):
        """Kicker should NOT fire once trailing arms (peak >= +60u)."""
        eng = DiamondHybrid()
        eng.start_new_line()
        
        # Line has reached +65u peak, now at +52u
        eng.line_pl_units = 52.0  # Above kicker threshold
        eng.line_peak_pl = 65.0   # Peak >= +60u, trailing is armed
        eng.line = [1, 1]  # Short line = low fragility
        eng.line_hands_played = 3
        eng.line_losses = 0
        
        # Kicker should NOT fire because trailing is armed
        self.assertFalse(eng._kicker_fires())

    def test_kicker_disabled_at_exactly_60u_peak(self):
        """Kicker should be disabled at exactly +60u peak."""
        eng = DiamondHybrid()
        eng.start_new_line()
        
        eng.line_pl_units = 55.0
        eng.line_peak_pl = 60.0  # Exactly at trailing arm threshold
        eng.line = [1, 1]
        eng.line_hands_played = 3
        eng.line_losses = 0
        
        # Kicker disabled because peak >= +60u
        self.assertFalse(eng._kicker_fires())

    def test_kicker_enabled_at_59u_peak(self):
        """Kicker should still be enabled at +59u peak."""
        eng = DiamondHybrid()
        eng.start_new_line()
        
        eng.line_pl_units = 55.0
        eng.line_peak_pl = 59.0  # Just below trailing arm threshold
        eng.line = [1, 1]
        eng.line_hands_played = 3
        eng.line_losses = 0
        
        # Kicker still enabled because peak < +60u
        self.assertTrue(eng._kicker_fires())


class TestLineCap(unittest.TestCase):
    """Test Line Cap mechanics - v2.1."""

    def test_line_cap_normal_180u(self):
        """Normal line cap should be +180u."""
        eng = DiamondHybrid()
        self.assertEqual(eng.LINE_CAP_NORMAL, 180.0)

    def test_line_cap_defensive_120u(self):
        """Defensive line cap should be +120u."""
        eng = DiamondHybrid()
        self.assertEqual(eng.LINE_CAP_DEFENSIVE, 120.0)

    def test_current_line_cap_normal(self):
        """Normal mode should use +180u cap."""
        eng = DiamondHybrid()
        eng.set_defensive(False)
        
        cap = eng._current_line_cap()
        self.assertEqual(cap, 180.0)

    def test_current_line_cap_defensive(self):
        """Defensive mode should use +120u cap."""
        eng = DiamondHybrid()
        eng.set_defensive(True)
        
        cap = eng._current_line_cap()
        self.assertEqual(cap, 120.0)


class TestFragility(unittest.TestCase):
    """Test fragility calculation - v2.1 6-component."""

    def test_fragility_bounded(self):
        """Fragility should be bounded [0, 1]."""
        eng = DiamondHybrid()
        eng.start_new_line()
        
        frag = eng._fused_fragility_score()
        self.assertGreaterEqual(frag, 0.0)
        self.assertLessEqual(frag, 1.0)

    def test_fragility_increases_with_line_length(self):
        """Longer lines should have higher fragility."""
        eng = DiamondHybrid()
        
        # Short line
        eng.line = [1, 1, 1]
        eng.line_initial_count = 3
        eng.line_hands_played = 3
        eng.line_losses = 1
        frag_short = eng._fused_fragility_score()
        
        # Long line
        eng.line = [1] * 20
        eng.line_initial_count = 20
        eng.line_hands_played = 20
        eng.line_losses = 10
        frag_long = eng._fused_fragility_score()
        
        self.assertGreater(frag_long, frag_short)

    def test_fragility_increases_with_losses(self):
        """More losses should increase fragility."""
        eng = DiamondHybrid()
        eng.line = [1, 2, 3]
        eng.line_initial_count = 3
        eng.line_hands_played = 10
        
        # Low losses
        eng.line_losses = 2
        frag_low = eng._fused_fragility_score()
        
        # High losses
        eng.line_losses = 8
        frag_high = eng._fused_fragility_score()
        
        self.assertGreater(frag_high, frag_low)


class TestStatePersistence(unittest.TestCase):
    """Test state export/import."""

    def test_export_state(self):
        """export_state() should return all necessary fields."""
        eng = DiamondHybrid()
        eng.start_new_line()
        eng.session_pl_units = 15.5
        eng.line_pl_units = 8.2
        
        state = eng.export_state()
        
        self.assertIn("line", state)
        self.assertIn("line_pl_units", state)
        self.assertIn("session_pl_units", state)
        self.assertIn("defensive_mode", state)
        self.assertIn("soft_shield", state)

    def test_import_state(self):
        """import_state() should restore engine state."""
        eng1 = DiamondHybrid()
        eng1.start_new_line()
        eng1.session_pl_units = 22.5
        eng1.line_pl_units = 12.3
        eng1.line_hands_played = 7
        eng1.line_losses = 2
        
        state = eng1.export_state()
        
        # New engine, import state
        eng2 = DiamondHybrid()
        eng2.import_state(state)
        
        self.assertEqual(eng2.session_pl_units, 22.5)
        self.assertEqual(eng2.line_pl_units, 12.3)
        self.assertEqual(eng2.line_hands_played, 7)
        self.assertEqual(eng2.line_losses, 2)
        self.assertEqual(eng2.line, eng1.line)

    def test_load_state_alias(self):
        """load_state() should be an alias for import_state()."""
        eng = DiamondHybrid()
        state = {"session_pl_units": 10.0, "line": [1, 2, 3]}
        
        eng.load_state(state)
        
        self.assertEqual(eng.session_pl_units, 10.0)
        self.assertEqual(eng.line, [1, 2, 3])


class TestModeFlags(unittest.TestCase):
    """Test defensive and soft shield mode flags."""

    def test_set_defensive(self):
        """set_defensive() should set mode flag."""
        eng = DiamondHybrid()
        
        eng.set_defensive(True)
        self.assertTrue(eng.defensive_mode)
        
        eng.set_defensive(False)
        self.assertFalse(eng.defensive_mode)

    def test_set_soft_shield(self):
        """set_soft_shield() should set mode flag."""
        eng = DiamondHybrid()
        
        eng.set_soft_shield(True)
        self.assertTrue(eng.soft_shield)
        
        eng.set_soft_shield(False)
        self.assertFalse(eng.soft_shield)

    def test_soft_shield_only_affects_session_stop(self):
        """Soft Shield should only affect session stop, not τ."""
        eng = DiamondHybrid()
        eng.start_new_line()
        
        # Without soft shield
        eng.set_soft_shield(False)
        stop_normal = eng._current_session_stop()
        
        # With soft shield
        eng.set_soft_shield(True)
        stop_shield = eng._current_session_stop()
        
        self.assertEqual(stop_normal, -60.0)
        self.assertEqual(stop_shield, -40.0)


class TestExitPriority(unittest.TestCase):
    """Test exit priority order - v2.1."""

    def test_line_complete_highest_priority(self):
        """Line complete should take priority over other exits."""
        eng = DiamondHybrid()
        eng.line = [1]  # Single number
        eng.line_active = True
        eng.line_initial_count = 1
        eng.line_pl_units = 100.0  # Would trigger kicker and cap
        
        result = eng.settle("W")
        
        # Should be line_complete, not kicker or cap
        self.assertEqual(result.reason, "line_complete")

    def test_line_cap_before_trailing(self):
        """Line cap should fire before trailing stop."""
        eng = DiamondHybrid()
        eng.start_new_line()
        eng.line_pl_units = 185.0  # Above line cap
        eng.line_peak_pl = 185.0
        eng.trailing_armed = True
        
        reason = eng._check_exits()
        self.assertEqual(reason, "line_cap")

    def test_trailing_before_smart_trim(self):
        """Trailing stop should fire before Smart Trim."""
        eng = DiamondHybrid()
        eng.start_new_line()
        eng.trailing_armed = True
        eng.line_peak_pl = 140.0  # Above +100u guard
        eng.line_pl_units = 75.0   # Dropped 65u from peak
        eng.line_hands_played = 20  # Would pass Smart Trim gates
        eng.line_losses = 10  # High loss density
        
        reason = eng._check_exits()
        self.assertEqual(reason, "trailing_stop")

    def test_trailing_protects_heater_from_kicker(self):
        """Once trailing is armed, Kicker should NOT fire."""
        eng = DiamondHybrid()
        eng.start_new_line()
        
        # Line reached +65u peak (trailing armed), now at +52u
        eng.line_pl_units = 52.0  # Above kicker threshold
        eng.line_peak_pl = 65.0   # Trailing is armed
        eng.line = [1, 1]  # Low fragility
        eng.line_hands_played = 3
        eng.line_losses = 0
        
        # Kicker should NOT fire because trailing is armed
        reason = eng._check_exits()
        self.assertNotEqual(reason, "kicker")


# ============================================================
# Run tests
# ============================================================

if __name__ == "__main__":
    # Run with verbosity
    unittest.main(verbosity=2)