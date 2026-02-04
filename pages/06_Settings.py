# pages/06_Settings.py — central place for $/unit + testing toggle

import streamlit as st
st.set_page_config(page_title="Settings", page_icon="⚙️", layout="wide")  # set FIRST

from auth import require_auth
user = require_auth()  # gate before anything renders

from sidebar import render_sidebar
render_sidebar()  # only show after auth

from track_manager import TrackManager  # ← use TrackManager / TrackBundle as the source of truth

st.markdown("""
<style>
.card{border:1px solid #2b2b2b;border-radius:14px;padding:16px 18px;
      background:linear-gradient(135deg,#0f0f0f,#171717);color:#eaeaea;margin:8px 0 18px 0;}
.h{font-weight:900;font-size:1.05rem;margin-bottom:6px}
.help{color:#a0a0a0;font-size:.92rem}
.warning{color:#fbbf24;font-size:.88rem;margin-top:6px}
</style>
""", unsafe_allow_html=True)

st.title("Settings")

# ---------- Session / Managers ----------
# Load user-specific unit_value from DB
if "unit_value" not in st.session_state:
    st.session_state.unit_value = 1.0

if "tm" not in st.session_state:
    st.session_state.tm = TrackManager(unit_value=float(st.session_state.unit_value))

tm: TrackManager = st.session_state.tm

def _as_engine(obj):
    """
    Accepts either a DiamondHybrid engine or a TrackBundle-like object.
    Returns the underlying engine instance.
    """
    if hasattr(obj, "set_defensive") and hasattr(obj, "preview_next_bet"):
        return obj
    for attr in ("eng", "engine"):
        if hasattr(obj, attr):
            return getattr(obj, attr)
    if isinstance(obj, dict):
        return obj.get("eng") or obj.get("engine")
    return obj

# ---------- Helper to check if any session is active ----------
def _any_session_active() -> bool:
    """Check if any track has an active session or line."""
    for tid in tm.all_ids():
        try:
            bundle = tm.ensure(tid)
            engine = _as_engine(bundle)
            if engine:
                sess_pl = float(getattr(engine, "session_pl_units", 0.0) or 0.0)
                line_pl = float(getattr(engine, "line_pl_units", 0.0) or 0.0)
                if abs(sess_pl) > 0.001 or abs(line_pl) > 0.001:
                    return True
        except Exception:
            pass
    return False

# ---------- Unit size ----------
with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="h">Unit Size ($ / unit)</div>', unsafe_allow_html=True)

    current = float(st.session_state.get("unit_value", 1.0))
    is_locked = _any_session_active()
    
    # Get user_db_id from session state
    user_db_id = st.session_state.get("user_db_id")
    
    # ✅ Load user-specific unit_value from DB if needed
    if user_db_id and st.session_state.get("_unit_value_user") != user_db_id:
        try:
            from db import get_user_unit_value
            st.session_state.unit_value = get_user_unit_value(user_db_id)
            st.session_state._unit_value_user = user_db_id
            current = float(st.session_state.unit_value)  # Update current after load
        except Exception as e:
            print(f"[settings] unit_value load error: {e!r}")
    
    if is_locked:
        # Locked state - show warning and disabled input
        st.markdown(
            '<div class="warning" style="margin-bottom:12px;">'
            '🔒 <b>Unit size is locked while a session is active.</b><br>'
            '<span style="font-size:.85rem;color:#9ca3af;">'
            'Close all active sessions on the Tracker page before changing unit size.'
            '</span></div>',
            unsafe_allow_html=True,
        )
        st.number_input(
            "$/unit",
            min_value=0.5,
            step=0.5,
            value=current,
            label_visibility="collapsed",
            disabled=True,
        )
    else:
        # Normal editable state
        new_unit = st.number_input(
            "$/unit",
            min_value=0.5,
            step=0.5,
            value=current,
            label_visibility="collapsed",
        )

        if st.button("Apply Unit Size", type="primary"):
            st.session_state.unit_value = float(new_unit)
            # ✅ Persist to DB for this user
            if user_db_id:
                try:
                    from db import set_user_unit_value
                    set_user_unit_value(user_db_id, float(new_unit))
                except Exception:
                    pass

            # propagate to all tracks via TrackBundle → engine
            try:
                for tid in tm.all_ids():
                    bundle = tm.ensure(tid)
                    engine = _as_engine(bundle)
                    if engine and hasattr(engine, "set_unit_value"):
                        engine.set_unit_value(float(new_unit))
            except Exception:
                pass

            st.success(f"Unit size set to ${float(new_unit):.2f}/u across all tracks.")

    st.markdown('<div class="warning">⚠️ <b>This applies globally to all tracks.</b></div>', unsafe_allow_html=True)
    st.markdown('<div class="help">When you change the unit size, it affects all future bets on every track. Historical P/L records preserve the unit value they were logged with, so past $ amounts won\'t change.</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ---------- Testing Mode ----------
with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="h">Testing Mode</div>', unsafe_allow_html=True)

    curr_test = bool(st.session_state.get("testing_mode", False))
    toggled = st.toggle("Enable Testing Mode (sandbox: no live stats affected)", value=curr_test)

    if toggled != curr_test:
        st.session_state.testing_mode = bool(toggled)
        st.success(f"Testing Mode is now {'ON' if toggled else 'OFF'}.")

        # Clear per-session artifacts so test/live data never mix visually
        st.session_state.pop("modal_queue_history", None)
        st.session_state.pop("hand_outcomes", None)
        st.session_state.pop("session_results", None)
        st.session_state.pop("line_events", None)

        # Force a clean rerender with the new mode
        st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)