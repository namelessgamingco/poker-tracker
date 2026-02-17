import os
import streamlit.components.v1 as components

_DEVELOP_MODE = os.environ.get("POKER_INPUT_DEV", "false").lower() == "true"

if _DEVELOP_MODE:
    _component_func = components.declare_component(
        "poker_input",
        url="http://localhost:5173",
    )
else:
    _parent_dir = os.path.dirname(os.path.abspath(__file__))
    build_dir = os.path.join(_parent_dir, "frontend", "dist")
    _component_func = components.declare_component(
        "poker_input",
        path=build_dir,
    )


def poker_input(
    mode="standard",
    stakes="$1/$2",
    bb_size=2.0,
    stack_size=200.0,
    decision_result=None,
    decision_table_id=1,
    show_second_table=False,
    active_table=1,
    primary_holds_table=1,
    # NEW: Explicit table1 and table2 data
    table1_game_state=None,
    table1_step=None,
    table1_decision=None,
    table1_board_entry_index=None,
    table2_game_state=None,
    table2_step=None,
    table2_decision=None,
    table2_board_entry_index=None,
    # Legacy t2_* for backward compatibility
    t2_game_state=None,
    t2_step=None,
    t2_decision=None,
    restore_state=None,
    session_active=True,
    key=None,
):
    """
    Render the poker input component.

    Args:
        mode: "standard" | "keyboard" | "two_table"
        stakes: Current stakes string
        bb_size: Big blind size in dollars
        stack_size: Our current stack
        decision_result: Dict with decision to display (from engine)
        decision_table_id: Which table (1 or 2) the decision is for
        show_second_table: Whether second table is visible
        active_table: Which table is currently active (1 or 2)
        primary_holds_table: Which table's data is in primary state variables
        table1_game_state: Table 1's game state
        table1_step: Table 1's current input step
        table1_decision: Table 1's decision result
        table1_board_entry_index: Table 1's board card entry index
        table2_game_state: Table 2's game state
        table2_step: Table 2's current input step
        table2_decision: Table 2's decision result
        table2_board_entry_index: Table 2's board card entry index
        t2_game_state: Legacy - Table 2 game state
        t2_step: Legacy - Table 2 step
        t2_decision: Legacy - Table 2 decision
        restore_state: Dict with game state to restore after rerun
        session_active: Whether session is active
        key: Streamlit component key

    Returns:
        Dict with game_state when user completes input, or None
    """
    return _component_func(
        mode=mode,
        stakes=stakes,
        bb_size=bb_size,
        stack_size=stack_size,
        decision_result=decision_result,
        decision_table_id=decision_table_id,
        show_second_table=show_second_table,
        active_table=active_table,
        primary_holds_table=primary_holds_table,
        table1_game_state=table1_game_state,
        table1_step=table1_step,
        table1_decision=table1_decision,
        table1_board_entry_index=table1_board_entry_index,
        table2_game_state=table2_game_state,
        table2_step=table2_step,
        table2_decision=table2_decision,
        table2_board_entry_index=table2_board_entry_index,
        t2_game_state=t2_game_state,
        t2_step=t2_step,
        t2_decision=t2_decision,
        restore_state=restore_state,
        session_active=session_active,
        key=key,
        default=None,
    )