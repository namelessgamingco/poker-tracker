from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

# ----------------------------- Tunables -----------------------------

# Production caps
PRIMARY_CAP_PROD   = 400    # default weekly cap
SECONDARY_CAP_PROD = 300    # optimizer/green-mode cap
GUARD_PROD         = -400   # weekly stop

# Production tone triggers
GREEN_TRIG_PROD = 160       # enter green-week tone at +160
RED_TRIG_PROD   = -85       # enter red-week stabilizer at −85

# +233 Diamond+ Soft Shield thresholds
SOFT_SHIELD_ENTRY = -300    # instant entry when week_pl drops to this
SOFT_SHIELD_EXIT  = -200    # sticky exit (hysteresis) when week_pl recovers to this

def _thresholds() -> Dict[str, int]:
    return dict(
        primary=PRIMARY_CAP_PROD,
        secondary=SECONDARY_CAP_PROD,
        guard=GUARD_PROD,
        green=GREEN_TRIG_PROD,
        red=RED_TRIG_PROD,
        soft_shield_entry=SOFT_SHIELD_ENTRY,
        soft_shield_exit=SOFT_SHIELD_EXIT,
    )


# ----------------------------- State -----------------------------


@dataclass
class WeekState:
    week_pl: float = 0.0
    cap_target: int = PRIMARY_CAP_PROD
    closed: bool = False
    # "week_cap+400", "week_cap+300", "week_guard-400", "small_green_lock", "red_stabilizer_lock"
    closed_reason: str = ""
    # unified gating + lock metadata
    allow_new_entries: bool = True
    locked: bool = False
    lock_kind: str = ""  # "SMALL_GREEN_LOCK" | "RED_STABILIZER_LOCK" | "CAP_300" | "CAP_400" | "FULL_RED_GUARD"
    locked_at_iso: Optional[str] = None

    # ---- Week roll-forward UX flags ----
    week_number: int = 1  # current week index for this track
    just_closed: bool = False  # flips True immediately after a week rolls
    last_closed_week: Optional[int] = None  # the week number that just closed

    # ---- Aggregated closed-week stats (across lifetime of this track) ----
    # e.g. {"week_cap+400": 3, "week_cap+300": 1, "small_green_lock": 2, ...}
    closed_buckets: Dict[str, int] = field(default_factory=dict)
    closed_weeks_count: int = 0

    # ---- +233 Diamond+ Soft Shield ----
    soft_shield_active: bool = False


class WeekManager:
    """
    Aggregates real (non-test) session P/L into weekly P/L and manages
    weekly tone & stop/cap mechanics for the +233 core config.
    
    +233 Diamond+ additions:
    - Soft Shield: Activates at week_pl <= -300, exits at week_pl >= -200
    - When active: session stop = -40u (engine handles this)
    NOTE: Smart Trim sensitivity (τ) is fully owned by the engine.
    WeekManager does not participate in trim or fragility logic.
    τ is computed dynamically by the engine based on session P/L.
    - Supersedes Defensive Mode (no stacking)
    """
    def import_state(self, data: dict) -> None:
        # alias to whatever you currently support
        if hasattr(self, "load_state"):
            self.load_state(data)  # type: ignore[attr-defined]

    def __init__(self) -> None:
        th = _thresholds()

        self.state: WeekState = WeekState(
            week_pl=0.0,
            cap_target=th["primary"],
            closed=False,
            closed_reason="",
            allow_new_entries=True,
            locked=False,
            lock_kind="",
            soft_shield_active=False,
        )

        # tone flags
        self.defensive_mode: bool = False
        self.green_mode: bool = False
        self.red_mode: bool = False
        self.stabilizer_active: bool = False
        self.green_tone_strength: Optional[str] = None
        self.was_green_week: bool = False

        # sentinel/fragility trackers
        self._recent_session_results: List[float] = []
        self._hands_window: int = 0
        self._smart_trim_count: int = 0
        self._hands_total: int = 0

        # continuation / limit signals (fed by engine/UI)
        self._glide_ok: bool = True
        self._lod_limit_hit: bool = False

        # cache thresholds for current process
        self._primary_cap: int = th["primary"]
        self._secondary_cap: int = th["secondary"]
        self._weekly_guard: int = th["guard"]
        self._green_trigger: int = th["green"]
        self._red_trigger: int = th["red"]
        self._soft_shield_entry: int = th["soft_shield_entry"]
        self._soft_shield_exit: int = th["soft_shield_exit"]

        # LIVE delta buffer (accumulates in-session hand deltas)
        self._live_delta: float = 0.0

    # ---------------------- Soft Shield API ----------------------

    def is_soft_shield_active(self) -> bool:
        """Check if Soft Shield is currently active."""
        return bool(self.state.soft_shield_active)

    def get_session_stop(self) -> float:
        """
        Returns the session stop threshold.
        Normal: -60u, Soft Shield: -40u
        """
        if self.state.soft_shield_active:
            return -40.0
        return -60.0

    def _update_soft_shield(self) -> None:
        """
        Update Soft Shield state based on current week_pl.
        - Entry: instant at week_pl <= -300
        - Exit: sticky at week_pl >= -200 (hysteresis)
        """
        wpl = float(self.state.week_pl)

        if not self.state.soft_shield_active:
            # Check for entry
            if wpl <= self._soft_shield_entry:
                self.state.soft_shield_active = True
                # Soft Shield supersedes Defensive Mode
                self.defensive_mode = True
        else:
            # Check for exit (hysteresis)
            if wpl >= self._soft_shield_exit:
                self.state.soft_shield_active = False
                # Note: defensive_mode may still be active from other conditions

    # ---------------------- External API ----------------------

    def feed_live_delta(self, du: float, is_test: bool = False) -> None:
        """
        Accumulate *in-session* P/L so tone can reflect week_pl + live_delta
        between session boundaries.
        """
        if is_test or self.state.closed:
            return
        self._live_delta += float(du)

    def clear_live_delta(self) -> None:
        """Clear the in-session buffer (call after booking a session or on reset)."""
        self._live_delta = 0.0

    # engine hooks to set continuation/limit context
    def set_glide_ok(self, ok: bool) -> None:
        self._glide_ok = bool(ok)

    def set_lod_limit_hit(self, hit: bool) -> None:
        self._lod_limit_hit = bool(hit)

    # ------- per-hand accounting -------

    def note_hand_played(self, is_test: bool = False) -> None:
        """Call once per hand so fragility rate has a real denominator."""
        if is_test:
            return
        self._hands_total += 1
        self._hands_window += 1
        # reset the trim counter every ~40 hands to keep fragility responsive
        if self._hands_window >= 40:
            self._hands_window = 0
            self._smart_trim_count = 0
            # keep _hands_total as the week's running total

    def record_hand_reason(self, reason: str, is_test: bool = False) -> None:
        """
        Feed per-hand reasons for a simple fragility rate.
        Count both Smart-Trim and Profit-Preserve as 'trimmy'.
        """
        if is_test:
            return
        if reason in {"smart_trim", "profit_preserve"}:
            self._smart_trim_count += 1

    def end_session(self, session_pl_units: float, is_test: bool = False) -> None:
        """
        Book a session result into the weekly state (unless testing).
        May flip caps, set green/red modes, close week, and update defensive sentinel.
        
        CLOSURE PRIORITY ORDER:
        1. Weekly Guard (≤ -400u) — hard stop, always first
        2. Cap Target (≥ +300/+400u) — primary profit rule
        3. Small Green Lock (≥ +160u + fragility/weak continuation) — profit protection
        4. Red Stabilizer Lock (≤ -85u + fragility/sentinel conditions) — loss containment
        """
        if self.state.closed:
            return
        if is_test:
            return

        # 1) Book P/L and track recent results
        self.state.week_pl += float(session_pl_units)
        self._recent_session_results.append(float(session_pl_units))
        if len(self._recent_session_results) > 10:
            self._recent_session_results.pop(0)

        # 2) Update Soft Shield state
        self._update_soft_shield()

        # 3) Green tone trigger (sticky within the week)
        if not self.green_mode and self.state.week_pl >= self._green_trigger:
            self.green_mode = True
            self.green_tone_strength = "tight"
            self.was_green_week = True
            # In green-mode, we target the secondary (optimizer) cap
            self.state.cap_target = self._secondary_cap

        # 4) Red tone trigger (sticky within the week)
        if not self.red_mode and self.state.week_pl <= self._red_trigger:
            self.red_mode = True
            self.stabilizer_active = True
            # Early defensive tilt when red-mode engages
            self.defensive_mode = True

        # 5) Fragility-based optimizer flip inside +140..+220 band
        if (self._green_trigger - 20 <= self.state.week_pl <= self._green_trigger + 60) and self._is_fragile_now():
            # Do not raise cap if already forced to secondary by green-mode
            self.state.cap_target = min(self.state.cap_target, self._secondary_cap)

        # 6) Apply sentinel + tone harmonization
        self._maybe_flip_defensive()
        self._apply_tone()

        # ============================================================
        # CLOSURE CHECKS — PRIORITY ORDER
        # ============================================================

        # PRIORITY 1: Weekly Guard (≤ -400u) — hard stop, always first
        if self.state.week_pl <= self._weekly_guard:
            self._close_week(
                reason=f"week_guard{self._weekly_guard}",
                kind="FULL_RED_GUARD",
            )
            return

        # PRIORITY 2: Cap Target (≥ +300/+400u) — primary profit rule
        if self.state.week_pl >= self.state.cap_target:
            self._close_week(
                reason=f"week_cap+{self.state.cap_target}",
                kind=(
                    "CAP_400"
                    if self.state.cap_target == self._primary_cap and self._primary_cap >= 400
                    else "CAP_300"
                ),
            )
            return

        # PRIORITY 3: Small Green Lock (≥ +160u + weak continuation/fragility)
        # Locks profit early when conditions suggest pushing further risks giving it back
        if self.state.week_pl >= self._green_trigger:
            if (not self._glide_ok) or self._is_fragile_now() or self._lod_limit_hit:
                self._close_week(
                    reason="small_green_lock",
                    kind="SMALL_GREEN_LOCK",
                )
                return

        # PRIORITY 4: Red Stabilizer Lock (≤ -85u + fragility/sentinel conditions)
        # Controlled early closure to contain red weeks before they spiral to -400u
        # Only closes if BOTH in the red zone AND fragility/sentinel conditions are met
        if self.state.week_pl <= self._red_trigger:
            should_stabilize = (
                self._three_reds_in_row() or
                self._is_fragile_now() or
                (self.red_mode and self.defensive_mode and len(self._recent_session_results) >= 3)
            )
            if should_stabilize:
                self._close_week(
                    reason="red_stabilizer_lock",
                    kind="RED_STABILIZER_LOCK",
                )
                return

        # No closure → clear live buffer now that session is booked
        self.clear_live_delta()

    def reset_for_new_week(
        self,
        *,
        increment: bool = True,
        last_closed_week: Optional[int] = None,
    ) -> None:
        """
        Reset the *live* week while preserving closed-week aggregate stats.
        """
        th = _thresholds()
        next_week_number = self.state.week_number + 1 if increment else 1

        # Preserve aggregates
        prev_buckets = dict(getattr(self.state, "closed_buckets", {}) or {})
        prev_closed_ct = int(getattr(self.state, "closed_weeks_count", 0) or 0)

        # Rebuild state with fresh week
        self.state = WeekState(
            week_pl=0.0,
            cap_target=th["primary"],
            closed=False,
            closed_reason="",
            allow_new_entries=True,
            locked=False,
            lock_kind="",
            locked_at_iso=None,
            week_number=next_week_number,
            just_closed=True if last_closed_week is not None else False,
            last_closed_week=last_closed_week,
            soft_shield_active=False,  # Reset Soft Shield on new week
        )
        self.state.closed_buckets = prev_buckets
        self.state.closed_weeks_count = prev_closed_ct

        # Reset tone flags
        self.defensive_mode = False
        self.green_mode = False
        self.red_mode = False
        self.stabilizer_active = False
        self.green_tone_strength = None
        self.was_green_week = False

        # Reset fragility / continuation
        self._recent_session_results.clear()
        self._hands_window = 0
        self._smart_trim_count = 0
        self._hands_total = 0
        self._glide_ok = True
        self._lod_limit_hit = False
        self.clear_live_delta()

        # Refresh thresholds
        self._primary_cap = th["primary"]
        self._secondary_cap = th["secondary"]
        self._weekly_guard = th["guard"]
        self._green_trigger = th["green"]
        self._red_trigger = th["red"]
        self._soft_shield_entry = th["soft_shield_entry"]
        self._soft_shield_exit = th["soft_shield_exit"]

    # ============================================================
    #  Persistence helpers — used by Supabase (export/load)
    # ============================================================

    def export_state(self) -> dict:
        s = self.state

        def _get(obj, name, default=None):
            return getattr(obj, name, default)

        return {
            "week_pl": float(_get(s, "week_pl", 0.0)),
            "cap_target": int(_get(s, "cap_target", 0)),
            "week_number": int(_get(s, "week_number", 1)),
            "closed": bool(_get(s, "closed", False)),
            "closed_reason": _get(s, "closed_reason", ""),
            "allow_new_entries": bool(_get(s, "allow_new_entries", True)),
            "locked": bool(_get(s, "locked", False)),
            "lock_kind": _get(s, "lock_kind", ""),
            "locked_at_iso": _get(s, "locked_at_iso", None),
            "just_closed": bool(_get(s, "just_closed", False)),
            "last_closed_week": _get(s, "last_closed_week", None),
            "closed_buckets": dict(_get(s, "closed_buckets", {}) or {}),
            "closed_weeks_count": int(_get(s, "closed_weeks_count", 0) or 0),
            "soft_shield_active": bool(_get(s, "soft_shield_active", False)),
            "defensive_mode": bool(_get(self, "defensive_mode", False)),
            "green_mode": bool(_get(self, "green_mode", False)),
            "red_mode": bool(_get(self, "red_mode", False)),
            "stabilizer_active": bool(_get(self, "stabilizer_active", False)),
            "green_tone_strength": _get(self, "green_tone_strength", None),
            "was_green_week": bool(_get(self, "was_green_week", False)),
            "recent_session_results": list(_get(self, "_recent_session_results", [])),
            "hands_window": int(_get(self, "_hands_window", 0)),
            "smart_trim_count": int(_get(self, "_smart_trim_count", 0)),
            "hands_total": int(_get(self, "_hands_total", 0)),
            "glide_ok": bool(_get(self, "_glide_ok", True)),
            "lod_limit_hit": bool(_get(self, "_lod_limit_hit", False)),
            "live_delta": float(_get(self, "_live_delta", 0.0)),
        }

    def load_state(self, data: dict) -> None:
        if not isinstance(data, dict):
            return

        s = self.state

        def _f(name: str, default: float = 0.0) -> float:
            try:
                return float(data.get(name, default))
            except Exception:
                return float(default)

        def _i(name: str, default: int = 0) -> int:
            try:
                return int(data.get(name, default))
            except Exception:
                return int(default)

        def _b(name: str, default: bool = False) -> bool:
            try:
                return bool(data.get(name, default))
            except Exception:
                return bool(default)

        # core numeric state
        try:
            s.week_pl = _f("week_pl", 0.0)
        except Exception:
            pass

        try:
            s.cap_target = _i("cap_target", getattr(s, "cap_target", 0))
        except Exception:
            pass

        if "week_number" in data:
            try:
                s.week_number = _i("week_number", getattr(s, "week_number", 1))
            except Exception:
                pass

        # flags
        if "closed" in data:
            try:
                s.closed = _b("closed", False)
            except Exception:
                pass

        if "closed_reason" in data:
            try:
                s.closed_reason = data.get("closed_reason", "") or ""
            except Exception:
                pass

        if "allow_new_entries" in data:
            try:
                s.allow_new_entries = _b("allow_new_entries", True)
            except Exception:
                pass

        if "locked" in data:
            try:
                s.locked = _b("locked", False)
            except Exception:
                pass

        if "lock_kind" in data:
            try:
                s.lock_kind = data.get("lock_kind", "") or ""
            except Exception:
                pass

        if "locked_at_iso" in data:
            try:
                s.locked_at_iso = data.get("locked_at_iso", None)
            except Exception:
                pass

        if "just_closed" in data:
            try:
                s.just_closed = _b("just_closed", False)
            except Exception:
                pass

        if "last_closed_week" in data:
            try:
                s.last_closed_week = data.get("last_closed_week", None)
            except Exception:
                pass

        # Soft Shield
        if "soft_shield_active" in data:
            try:
                s.soft_shield_active = _b("soft_shield_active", False)
            except Exception:
                pass

        # aggregates
        if "closed_buckets" in data:
            try:
                raw = data.get("closed_buckets", {}) or {}
                s.closed_buckets = dict(raw)
            except Exception:
                s.closed_buckets = {}
        if "closed_weeks_count" in data:
            try:
                s.closed_weeks_count = _i("closed_weeks_count", 0)
            except Exception:
                pass

        # tone flags
        if "defensive_mode" in data:
            try:
                self.defensive_mode = _b("defensive_mode", False)
            except Exception:
                pass
        if "green_mode" in data:
            try:
                self.green_mode = _b("green_mode", False)
            except Exception:
                pass
        if "red_mode" in data:
            try:
                self.red_mode = _b("red_mode", False)
            except Exception:
                pass
        if "stabilizer_active" in data:
            try:
                self.stabilizer_active = _b("stabilizer_active", False)
            except Exception:
                pass
        if "green_tone_strength" in data:
            try:
                self.green_tone_strength = data.get("green_tone_strength", None)
            except Exception:
                pass
        if "was_green_week" in data:
            try:
                self.was_green_week = _b("was_green_week", False)
            except Exception:
                pass

        # fragility counters
        if "recent_session_results" in data:
            try:
                self._recent_session_results = list(
                    data.get("recent_session_results", []) or []
                )
            except Exception:
                self._recent_session_results = []
        if "hands_window" in data:
            try:
                self._hands_window = _i("hands_window", 0)
            except Exception:
                pass
        if "smart_trim_count" in data:
            try:
                self._smart_trim_count = _i("smart_trim_count", 0)
            except Exception:
                pass
        if "hands_total" in data:
            try:
                self._hands_total = _i("hands_total", 0)
            except Exception:
                pass

        # continuation flags
        if "glide_ok" in data:
            try:
                self._glide_ok = _b("glide_ok", True)
            except Exception:
                pass
        if "lod_limit_hit" in data:
            try:
                self._lod_limit_hit = _b("lod_limit_hit", False)
            except Exception:
                pass

        # live delta
        if "live_delta" in data:
            try:
                self._live_delta = _f("live_delta", 0.0)
            except Exception:
                pass

        # Re-harmonize tone flags with loaded modes
        try:
            self._apply_tone()
        except Exception:
            pass

    # ---------------------- Compatibility ----------------------

    def is_fast_test(self) -> bool:
        """Compatibility shim: FAST_TEST removed; always production behavior."""
        return False

    # ---------------------- Tone (LIVE-aware) ----------------------

    def current_tone(self, live_session_pl: float = 0.0) -> Dict[str, Any]:
        """
        Return the week tone using week_pl + live_delta so the UI can show
        live-aware tone without waiting for session boundaries.
        """
        live_pl = float(self.state.week_pl) + float(self._live_delta) + float(live_session_pl)

        green = live_pl >= self._green_trigger
        red = live_pl <= self._red_trigger

        tone = "neutral"
        tau_delta = 0.0
        glide_scale = 1.0

        if green:
            tone = "green"
            tau_delta = -0.01
            glide_scale = 1.00
        elif red:
            tone = "red"
            tau_delta = +0.02
            glide_scale = 0.92

        return {
            "tone": tone,
            "tau_delta": tau_delta,
            "glide_scale": glide_scale,
            "cap_target": self.state.cap_target,
            "live_pl": live_pl,
            "base_week_pl": self.state.week_pl,
            "defensive": self.defensive_mode,
            "green_mode": self.green_mode,
            "red_mode": self.red_mode,
            "stabilizer": self.stabilizer_active,
            "soft_shield": self.state.soft_shield_active,
            "allow_new_entries": self.state.allow_new_entries,
            "locked": self.state.locked,
            "lock_kind": self.state.lock_kind,
            "closed": self.state.closed,
            "closed_reason": self.state.closed_reason,
            "week_number": self.state.week_number,
            "just_closed": self.state.just_closed,
            "last_closed_week": self.state.last_closed_week,
        }

    def current_tone_live(self, live_session_pl: float = 0.0) -> Dict[str, Any]:
        """
        Compatibility shim for any older engine call sites.
        """
        try:
            if hasattr(self, "_current_tone_live_impl"):
                return self._current_tone_live_impl(live_session_pl)
            return self.current_tone(live_session_pl=live_session_pl)  # type: ignore
        except TypeError:
            return self.current_tone()

    # ---------------------- Internals ----------------------

    def _is_fragile_now(self) -> bool:
        """Return True if smart-trim rate is high in the recent window."""
        if self._hands_total < 15:
            return False
        rate = self._smart_trim_count / max(1, self._hands_total)
        return rate >= 0.20

    def _three_reds_in_row(self) -> bool:
        if len(self._recent_session_results) < 3:
            return False
        last3 = self._recent_session_results[-3:]
        return all(x < 0 for x in last3)

    def _maybe_flip_defensive(self) -> None:
        """
        Defensive sentinel:
          - drawdown
          - 3 reds in a row
          - elevated fragility
          - red_mode
          - Soft Shield active (supersedes)
        Clears only after improvement.
        """
        # Soft Shield supersedes - always defensive when active
        if self.state.soft_shield_active:
            self.defensive_mode = True
            return

        drawdown = self.state.week_pl <= -250
        three_reds = self._three_reds_in_row()
        elevated_trims = self._is_fragile_now()

        if drawdown or three_reds or elevated_trims or self.red_mode:
            self.defensive_mode = True
            return

        # Exit conditions
        recent = self._recent_session_results[-3:]
        greens = sum(1 for x in recent if x > 0)
        if greens >= 2 and self.state.week_pl >= -100:
            self.defensive_mode = False
            self.stabilizer_active = False
            self.red_mode = False

    def _apply_tone(self) -> None:
        """
        Harmonize defensive_mode with red/green/stabilizer/soft_shield flags.
        """
        # Soft Shield supersedes everything
        if self.state.soft_shield_active:
            self.defensive_mode = True
        elif self.red_mode or self.stabilizer_active:
            self.defensive_mode = True
        elif self.green_mode:
            self.defensive_mode = False

    def _close_week(self, reason: str, kind: str) -> None:
        """
        Unified week closure helper:
          - mark closed / locked
          - bump reason bucket + total closed weeks
          - clear live delta
        """
        # bump aggregates
        try:
            buckets = dict(getattr(self.state, "closed_buckets", {}) or {})
        except Exception:
            buckets = {}
        buckets[reason] = int(buckets.get(reason, 0)) + 1
        self.state.closed_buckets = buckets
        self.state.closed_weeks_count = (
            int(getattr(self.state, "closed_weeks_count", 0) or 0) + 1
        )

        # mark closed/locked for this week
        self.state.closed = True
        self.state.closed_reason = reason
        self.state.allow_new_entries = False
        self.state.locked = True
        self.state.lock_kind = kind
        if self.state.locked_at_iso is None:
            from datetime import datetime, timezone

            self.state.locked_at_iso = datetime.now(timezone.utc).isoformat()

        # Clear any remaining live buffer so the next week starts clean
        self.clear_live_delta()

    # ---------------------- UI helpers ----------------------

    def mark_week_banner_seen(self) -> None:
        """Called by UI once the 'Week X complete' banner was shown."""
        self.state.just_closed = False
        self.state.last_closed_week = None