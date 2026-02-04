# play_counters.py — reason classification only (NO state mutation)
# +233 Core Config v2.1
from __future__ import annotations

from typing import Optional

__all__ = ["normalize_reason", "is_line_close", "is_session_close"]

# Line close reasons — these reset the line and increment LOD
# Engine emits these when line-level guards trigger
LINE_CLOSE_REASONS = {
    "smart_trim",       # Fragility ≥ τ (0.68 base, dynamic by session P/L)
    "trailing_stop",    # Arms at +60u line P/L, fires when peak ≥ +100u and drops 60u
    "kicker",           # Line P/L ≥ +50u with fragility < 0.45 and peak < +60u
    "kicker_hit",       # Alias for kicker
    "line_cap",         # Line P/L ≥ +180u (or +120u in defensive mode)
    "line_complete",    # True Labouchere: line array becomes empty
    "line_closed",      # Generic/manual line close
}

# Session close reasons — these book the session into the week and increment NB
# Engine emits these when session-level boundaries are hit
SESSION_CLOSE_REASONS = {
    "session_goal",     # Session P/L ≥ +30u
    "session_cap",      # Alias for session_goal
    "session_stop",     # Session P/L ≤ -60u (or -40u under Soft Shield)
    "session_guard",    # Alias for session_stop
    "session_closed",   # Manual session close
    "profit_preserve",  # Smart Trim + (session >= +20 OR bet >= 22) = END SESSION
}

# Map engine output reasons to canonical names
REASON_ALIASES = {
    "session_goal": "session_goal",
    "session_cap": "session_goal",
    "session_stop": "session_stop",
    "session_guard": "session_stop",
    "kicker_hit": "kicker",
}

def normalize_reason(reason: Optional[str]) -> str:
    """Normalize a reason string to its canonical form."""
    r = str(reason or "").strip().lower()
    return REASON_ALIASES.get(r, r)

def is_line_close(reason: Optional[str]) -> bool:
    """Check if the reason indicates a line-level close."""
    return normalize_reason(reason) in LINE_CLOSE_REASONS

def is_session_close(reason: Optional[str]) -> bool:
    """Check if the reason indicates a session-level close."""
    return normalize_reason(reason) in SESSION_CLOSE_REASONS