# =============================================================================
# 06_How_It_Works.py — How It Works Guide
# =============================================================================

import streamlit as st

st.set_page_config(
    page_title="How It Works | Poker Decision App",
    page_icon="📖",
    layout="wide",
)

from auth import require_auth
from sidebar import render_sidebar

user = require_auth()
render_sidebar()

st.session_state["visited_how_it_works"] = True

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');
.block-container { max-width: 1400px; }

/* Hero */
.hero-hw {
    background: linear-gradient(160deg, #0c1220 0%, #162032 50%, #1a2940 100%);
    border-radius: 20px;
    padding: 56px 48px;
    text-align: center;
    color: white;
    margin-bottom: 40px;
    position: relative;
    overflow: hidden;
    border: 1px solid rgba(59, 130, 246, 0.15);
}
.hero-hw::before {
    content: '';
    position: absolute;
    top: -50%;
    right: -20%;
    width: 400px;
    height: 400px;
    background: radial-gradient(circle, rgba(34, 197, 94, 0.08) 0%, transparent 70%);
    pointer-events: none;
}
.hero-hw h1 {
    font-family: 'DM Sans', sans-serif;
    font-size: 38px;
    font-weight: 700;
    margin-bottom: 16px;
    letter-spacing: -0.5px;
}
.hero-hw p {
    font-size: 18px;
    color: #94a3b8;
    max-width: 640px;
    margin: 0 auto;
    line-height: 1.7;
}

/* Section dividers */
.sdiv {
    background: linear-gradient(135deg, #111827 0%, #1a2332 100%);
    border-radius: 14px;
    padding: 28px 32px;
    margin: 44px 0 24px 0;
    border-left: 4px solid #22c55e;
}
.sdiv h2 { font-family: 'DM Sans', sans-serif; font-size: 24px; font-weight: 700; color: #f1f5f9; margin: 0 0 4px 0; }
.sdiv p { font-size: 14px; color: #64748b; margin: 0; }

/* Pillar cards */
.pcard {
    background: linear-gradient(145deg, #0f172a 0%, #1e293b 100%);
    border: 1px solid #334155;
    border-radius: 16px;
    padding: 32px 24px;
    text-align: center;
    height: 100%;
    transition: border-color 0.3s ease;
}
.pcard:hover { border-color: #22c55e; }
.pcard-icon { font-size: 40px; margin-bottom: 16px; }
.pcard-title { font-size: 18px; font-weight: 700; color: #f1f5f9; margin-bottom: 10px; }
.pcard-desc { font-size: 14px; color: #94a3b8; line-height: 1.7; }

/* Step flow */
.sflow {
    display: flex; align-items: flex-start; gap: 20px; padding: 24px;
    background: linear-gradient(135deg, #0f172a 0%, #162032 100%);
    border: 1px solid #1e293b; border-radius: 14px; margin-bottom: 14px;
}
.sflow-badge {
    background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
    color: white; min-width: 44px; height: 44px; border-radius: 12px;
    display: flex; align-items: center; justify-content: center;
    font-size: 18px; font-weight: 700; flex-shrink: 0;
}
.sflow-title { font-size: 17px; font-weight: 600; color: #f1f5f9; margin-bottom: 6px; }
.sflow-desc { font-size: 14px; color: #94a3b8; line-height: 1.65; }

/* Decision showcase */
.dshow {
    background: linear-gradient(145deg, #0f172a 0%, #111827 100%);
    border: 1px solid #334155; border-radius: 16px;
    padding: 40px; text-align: center; margin: 24px 0;
}
.dshow-scenario { font-size: 14px; color: #64748b; margin-bottom: 12px; }
.dshow-action { font-size: 44px; font-weight: 700; color: #22c55e; margin-bottom: 8px; letter-spacing: -1px; font-family: 'DM Sans', sans-serif; }
.dshow-why { font-size: 14px; color: #94a3b8; max-width: 480px; margin: 0 auto; line-height: 1.6; }

/* Feature cards */
.fcard {
    background: linear-gradient(145deg, #0f172a 0%, #1e293b 100%);
    border: 1px solid #334155; border-radius: 14px; padding: 24px;
    margin-bottom: 12px; transition: border-color 0.3s;
}
.fcard:hover { border-color: #3b82f6; }
.fcard-title { font-size: 16px; font-weight: 600; color: #f1f5f9; margin-bottom: 8px; display: flex; align-items: center; gap: 10px; }
.fcard-body { font-size: 14px; color: #94a3b8; line-height: 1.65; }
.ftag {
    display: inline-block; background: rgba(34, 197, 94, 0.15); color: #22c55e;
    padding: 2px 10px; border-radius: 6px; font-size: 11px; font-weight: 600;
    text-transform: uppercase; letter-spacing: 0.5px;
}
.ftag-blue { background: rgba(59, 130, 246, 0.15); color: #60a5fa; }
.ftag-amber { background: rgba(245, 158, 11, 0.15); color: #fbbf24; }

/* Commitment */
.cbox {
    background: linear-gradient(135deg, rgba(245, 158, 11, 0.08) 0%, rgba(245, 158, 11, 0.03) 100%);
    border: 1px solid rgba(245, 158, 11, 0.3); border-left: 4px solid #f59e0b;
    border-radius: 0 14px 14px 0; padding: 28px; margin: 16px 0;
}
.cbox h3 { font-size: 17px; font-weight: 600; color: #f59e0b; margin: 0 0 12px 0; }
.cbox p { font-size: 14px; color: #e2e8f0; line-height: 1.7; margin: 0; }

/* Do/Don't */
.do-i {
    display: flex; align-items: center; gap: 12px; padding: 14px 18px;
    background: rgba(34, 197, 94, 0.06); border: 1px solid rgba(34, 197, 94, 0.2);
    border-radius: 10px; margin-bottom: 8px; font-size: 14px; color: #d1fae5;
}
.dont-i {
    display: flex; align-items: center; gap: 12px; padding: 14px 18px;
    background: rgba(239, 68, 68, 0.06); border: 1px solid rgba(239, 68, 68, 0.2);
    border-radius: 10px; margin-bottom: 8px; font-size: 14px; color: #fecaca;
}

/* Quick start */
.qs {
    display: flex; align-items: center; gap: 16px; padding: 18px 20px;
    background: linear-gradient(135deg, #0f172a 0%, #162032 100%);
    border: 1px solid #1e293b; border-radius: 12px; margin-bottom: 10px;
}
.qs-n {
    background: #3b82f6; color: white; min-width: 36px; height: 36px;
    border-radius: 10px; display: flex; align-items: center; justify-content: center;
    font-weight: 700; font-size: 15px; flex-shrink: 0;
}
.qs-t { font-size: 14px; color: #e2e8f0; line-height: 1.5; }
</style>
""", unsafe_allow_html=True)


def main():
    # ===== HERO =====
    st.markdown("""
        <div class="hero-hw">
            <h1>One Answer. Every Hand. No Thinking.</h1>
            <p>
                This app tells you exactly what to do in every poker situation.
                Not suggestions. Not ranges. One clear action with the exact dollar amount.
                Built on game theory, exploitative adjustments, and thousands of hours
                of simulation — delivered in under 5 seconds.
            </p>
        </div>
    """, unsafe_allow_html=True)

    # ===== THREE PILLARS =====
    st.markdown('<div class="sdiv"><h2>The Three Pillars</h2><p>Everything you need to win consistently</p></div>', unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("""<div class="pcard"><div class="pcard-icon">🎯</div><div class="pcard-title">Decision Engine</div><div class="pcard-desc">Tells you exactly what to do every hand — pre-flop through river. Adjusted for opponent type, board texture, position, stack depth, and player count. Outputs exact dollar amounts: "RAISE TO $18."</div></div>""", unsafe_allow_html=True)
    with c2:
        st.markdown("""<div class="pcard"><div class="pcard-icon">💰</div><div class="pcard-title">Bankroll Management</div><div class="pcard-desc">Protects you from going broke. Tells you exactly what stakes to play, when to move up, and when to move down. Risk of ruin calculations ensure you survive variance.</div></div>""", unsafe_allow_html=True)
    with c3:
        st.markdown("""<div class="pcard"><div class="pcard-icon">⏱️</div><div class="pcard-title">Session Management</div><div class="pcard-desc">Stops you before tired mistakes. Automatic stop-loss, stop-win, and session time alerts. Tilt detection monitors loss streaks and warns before emotional play costs money.</div></div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ===== HOW TO USE IT =====
    st.markdown('<div class="sdiv"><h2>How To Use It</h2><p>Your flow during a poker session</p></div>', unsafe_allow_html=True)

    st.markdown("""
        <div class="sflow"><div class="sflow-badge">1</div><div><div class="sflow-title">Enter Your Cards & Situation</div><div class="sflow-desc">Tap your two hole cards, select your position, and tell the app what action you're facing. On postflop streets, enter board cards, pot size, and how many players remain. The entire input takes 3-5 seconds.</div></div></div>
        <div class="sflow"><div class="sflow-badge">2</div><div><div class="sflow-title">Get Your Decision Instantly</div><div class="sflow-desc">The engine evaluates hand strength, board texture, position, opponent type, and stack depth — then delivers one clear action: <strong style="color:#22c55e">RAISE TO $18</strong>, <strong style="color:#3b82f6">CALL $6</strong>, or <strong style="color:#ef4444">FOLD</strong>. Every decision includes a coaching explanation so you learn <em>why</em>.</div></div></div>
        <div class="sflow"><div class="sflow-badge">3</div><div><div class="sflow-title">Continue Through Every Street</div><div class="sflow-desc">If the hand continues to the turn or river, add the new board card and get your next decision. The app tracks your investment across every street — you always know exactly how much you have in the pot.</div></div></div>
        <div class="sflow"><div class="sflow-badge">4</div><div><div class="sflow-title">Record the Result</div><div class="sflow-desc">When the hand ends, tap Won, Lost, or Folded. For won/lost hands, enter the total pot — the app calculates your profit automatically. Your result instantly appears in the <strong>Hand Log</strong> at the bottom of the screen.</div></div></div>
        <div class="sflow"><div class="sflow-badge">5</div><div><div class="sflow-title">Review in the Hand Log</div><div class="sflow-desc">Every completed hand appears in an inline log below the input — no pop-ups, no interruptions. The latest hand auto-expands to show your action, the engine's reasoning, EV math, and bluff stats. Previous hands collapse to a single line showing cards, position, action, and P/L. Click any hand to expand its full detail. Collapse the entire log to a summary bar showing your win/loss count and session P/L. You're always ready for the next hand — zero clicks required to continue.</div></div></div>
    """, unsafe_allow_html=True)

    st.markdown("""
        <div class="dshow">
            <div class="dshow-scenario">You have A♠ K♥ on the Button facing a $6 raise</div>
            <div class="dshow-action">RAISE TO $18</div>
            <div class="dshow-why">3-bet for value with premium hand in position. AK plays best heads-up with initiative. Sizing: 3× the open to isolate and build the pot.</div>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ===== ENGINE FEATURES =====
    st.markdown('<div class="sdiv"><h2>What the Engine Handles</h2><p>Every scenario, every street — here\'s what runs under the hood</p></div>', unsafe_allow_html=True)

    st.markdown('<p style="font-size:14px;color:#94a3b8;line-height:1.7;margin-bottom:20px;">The decision engine isn\'t a simple lookup table. It\'s a layered system that evaluates dozens of variables in real time and synthesizes them into one optimal action.</p>', unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("""
            <div class="fcard"><div class="fcard-title"><span class="ftag">Pre-flop</span> Position-Based Opening Ranges</div><div class="fcard-body">Mathematically derived ranges for every position (UTG through BB). Tighter from early position, wider from late position. Adjusted for limpers, stack depth, and opponent type. Includes open-raise, over-limp, and isolate strategies.</div></div>
            <div class="fcard"><div class="fcard-title"><span class="ftag">Pre-flop</span> 3-Bet & 4-Bet Strategy</div><div class="fcard-body">Position-aware 3-bet ranges for value and as bluffs using blockers (suited aces, suited broadways). 4-bet/fold and 4-bet/call thresholds based on stack depth and opponent tendencies.</div></div>
            <div class="fcard"><div class="fcard-title"><span class="ftag-blue ftag">Postflop</span> Continuation Betting</div><div class="fcard-body">Automatic c-bet sizing based on board texture: 33% pot on dry boards, 50% semi-wet, 66% wet, 50% paired. Strong hands always c-bet. Medium hands check on dangerous boards. Weak hands only bluff heads-up on dry textures.</div></div>
            <div class="fcard"><div class="fcard-title"><span class="ftag-blue ftag">Postflop</span> Multiway Pot Adjustments</div><div class="fcard-body">When 3+ players are in the pot, the engine shifts to tighter, protection-oriented strategy. No bluffs fire multiway. Strong hands bet bigger (75% pot). Medium hands check instead of thin-value betting. Player count updates each street as opponents fold out.</div></div>
            <div class="fcard"><div class="fcard-title"><span class="ftag-amber ftag">Advanced</span> Bluff Detection & EV Tracking</div><div class="fcard-body">Identifies profitable bluff spots — dry board c-bets, river barrels, turn probes. Calculates break-even fold %, estimated opponent fold rate, and exact EV per bluff. Your bluff success rate is tracked across sessions.</div></div>
            <div class="fcard"><div class="fcard-title"><span class="ftag-amber ftag">Advanced</span> Check-Raise Strategy</div><div class="fcard-body">Sets, two-pair on wet boards, and nut flush draws qualify for check-raises. Sizing: 3× their bet (3.5× vs fish). Also handles <em>facing</em> a check-raise — tells you when to call, fold, or re-raise.</div></div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown("""
            <div class="fcard"><div class="fcard-title"><span class="ftag-blue ftag">Postflop</span> Turn & River Barreling</div><div class="fcard-body">Continued aggression logic for value and bluffs. Strong hands keep betting. Drawing hands barrel as semi-bluffs. Air gives up when fold equity is low. Sizing increases on later streets to build the pot or maximize pressure.</div></div>
            <div class="fcard"><div class="fcard-title"><span class="ftag-blue ftag">Postflop</span> Delayed C-Bets & Probe Bets</div><div class="fcard-body">When you check the flop and get checked to on the turn — the engine fires delayed c-bets. Also handles probe bets when the aggressor checks and you seize initiative. Both limited to heads-up pots where they're profitable.</div></div>
            <div class="fcard"><div class="fcard-title"><span class="ftag">Sizing</span> Exact Dollar Outputs</div><div class="fcard-body">Every bet and raise is expressed as an exact dollar amount rounded to clean numbers. Not "bet 2/3 pot" — the app says "BET $23." Sizing adapts to board texture, hand strength, stack-to-pot ratio, and opponent type (bigger vs fish).</div></div>
            <div class="fcard"><div class="fcard-title"><span class="ftag">Opponent</span> Villain Type Adjustments</div><div class="fcard-body">Three profiles — Regular, Fish, and Nit. Against fish: +20% value sizing, wider value ranges, fewer bluffs. Against nits: more bluffs, smaller bets, more folds to aggression. Default carries between hands.</div></div>
            <div class="fcard"><div class="fcard-title"><span class="ftag-amber ftag">Advanced</span> Donk Bet & Overbet Handling</div><div class="fcard-body">Handles facing non-standard plays: donk bets from defenders and overbets. Calculates pot odds, adjusts for implied odds with draws, and provides tight calling ranges proportional to the overbet size.</div></div>
            <div class="fcard"><div class="fcard-title"><span class="ftag-amber ftag">Safety</span> Tilt Detection & Session Alerts</div><div class="fcard-body">Monitors loss streaks in real time. After consecutive losses, triggers tilt warnings before emotional play costs money. Combined with stop-loss, stop-win, and session time alerts to protect your bankroll from yourself.</div></div>
        """, unsafe_allow_html=True)

    st.markdown("""
        <div class="fcard" style="border-color:#8b5cf6;">
            <div class="fcard-title" style="font-size:17px;"><span style="display:inline-block;background:rgba(139,92,246,0.15);color:#a78bfa;padding:2px 10px;border-radius:6px;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;margin-right:10px;">Feature</span> Multi-Table Support</div>
            <div class="fcard-body" style="line-height:1.7;">
                Play two tables simultaneously from one screen. The app manages both tables
                independently — separate hands, separate decisions, separate tracking. Switch
                between tables with a single tap or keyboard shortcut. Multi-tabling doubles
                your hands per hour without adding session time, effectively doubling your
                hourly earn rate. Each table maintains its own board cards, pot size, player
                count, and investment tracker.
            </div>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ===== THE MATH — WHY IT'S WORTH IT =====
    st.markdown('<div class="sdiv"><h2>The Math — Why It\'s Worth $299/Month</h2><p>Conservative projections based on realistic play volume</p></div>', unsafe_allow_html=True)

    c1, c2 = st.columns([2, 1])
    with c1:
        st.markdown("""
            <div class="fcard" style="border-color: #22c55e;">
                <div class="fcard-title" style="font-size:18px;">📊 Sim-Verified Win Rate: +5 to +8 BB/100</div>
                <div class="fcard-body" style="line-height:2.0;">
                    <strong>Backed by a 10,000,000-hand Monte Carlo simulation against the actual engine:</strong><br><br>
                    <strong style="color:#22c55e;">Decision Engine:</strong> +5.5 to +6.0 BB/100<br>
                    <span style="color:#64748b;">— Pre-flop ranges, postflop c-betting, check-raises, bluff EV, villain adjustments, multiway protection</span><br><br>
                    <strong style="color:#22c55e;">Session & Tilt Management:</strong> +1.0 BB/100<br>
                    <span style="color:#64748b;">— Fatigue prevention, stop-loss discipline, loss streak detection</span><br><br>
                    <strong style="color:#22c55e;">Sizing & Opponent Exploitation:</strong> +1.0 BB/100<br>
                    <span style="color:#64748b;">— Exact dollar bets, +20% sizing vs fish, board-aware adjustments</span><br><br>
                    <span style="background:#22c55e;color:white;padding:4px 12px;border-radius:6px;font-weight:700;">
                        Total: +5 to +8 BB/100
                    </span>
                    <span style="color:#64748b;font-size:13px;margin-left:8px;">at $1/$2 (higher at soft tables, lower at tough ones)</span>
                </div>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("""
            <div class="fcard" style="margin-top:12px;border-color:#3b82f6;">
                <div class="fcard-title" style="font-size:15px;">📈 The Assumptions</div>
                <div class="fcard-body" style="line-height:1.9;">
                    40 sessions per month (about 10 per week) · 200 hands per session ·
                    2-3 hours per session · <strong>100% compliance — which is what the app delivers</strong>.
                    The app is the execution layer. Your job is to input the situation and follow
                    the decision. See <strong>EV System</strong> page for full projections at every
                    volume tier with gross and net breakdowns.
                </div>
            </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown("""
            <div style="background:linear-gradient(135deg,#8b5cf6 0%,#6366f1 100%);border-radius:14px;padding:28px;text-align:center;color:white;margin-bottom:14px;">
                <div style="font-size:36px;font-weight:700;margin-bottom:4px;">$13,440</div>
                <div style="font-size:14px;opacity:0.9;">Annual gross at $1/$2</div>
                <div style="font-size:13px;opacity:0.75;margin-top:4px;">$9,852/yr after subscription</div>
            </div>
            <div style="background:linear-gradient(135deg,#8b5cf6 0%,#6366f1 100%);border-radius:14px;padding:28px;text-align:center;color:white;margin-bottom:14px;">
                <div style="font-size:36px;font-weight:700;margin-bottom:4px;">$33,600</div>
                <div style="font-size:14px;opacity:0.9;">Annual gross at $2/$5</div>
                <div style="font-size:13px;opacity:0.75;margin-top:4px;">$30,012/yr after subscription</div>
            </div>
            <div style="background:linear-gradient(135deg,#8b5cf6 0%,#6366f1 100%);border-radius:14px;padding:28px;text-align:center;color:white;margin-bottom:14px;">
                <div style="font-size:36px;font-weight:700;margin-bottom:4px;">$57,600</div>
                <div style="font-size:14px;opacity:0.9;">Annual gross at $5/$10</div>
                <div style="font-size:13px;opacity:0.75;margin-top:4px;">$54,012/yr after subscription</div>
            </div>
            <div style="background:linear-gradient(135deg,#8b5cf6 0%,#6366f1 100%);border-radius:14px;padding:28px;text-align:center;color:white;margin-bottom:14px;">
                <div style="font-size:36px;font-weight:700;margin-bottom:4px;">$96,000</div>
                <div style="font-size:14px;opacity:0.9;">Annual gross at $10/$20</div>
                <div style="font-size:13px;opacity:0.75;margin-top:4px;">$92,412/yr after subscription</div>
            </div>
            <div style="background:linear-gradient(135deg,#8b5cf6 0%,#6366f1 100%);border-radius:14px;padding:28px;text-align:center;color:white;">
                <div style="font-size:36px;font-weight:700;margin-bottom:4px;">$192,000</div>
                <div style="font-size:14px;opacity:0.9;">Annual gross at $25/$50</div>
                <div style="font-size:13px;opacity:0.75;margin-top:4px;">$188,412/yr after subscription</div>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("""
        <div style="background:linear-gradient(135deg,#22c55e 0%,#16a34a 100%);border-radius:14px;padding:28px;text-align:center;color:white;margin-top:16px;">
            <div style="font-size:14px;opacity:0.85;margin-bottom:8px;">Subscription: $299/month · The app covers its cost in 11 sessions at $1/$2 — or just 4 sessions at $2/$5</div>
            <div style="font-size:24px;font-weight:700;">4× to 53× return on investment depending on stakes</div>
            <div style="font-size:14px;opacity:0.85;margin-top:8px;">Every dollar you spend on this app should return $4–$53 in poker profit</div>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ===== COMMITMENT =====
    st.markdown('<div class="sdiv"><h2>Your Commitment</h2><p>This system only works if you follow it exactly</p></div>', unsafe_allow_html=True)

    st.markdown("""
        <div class="cbox">
            <h3>⚠️ The Math Only Works With Perfect Execution</h3>
            <p>Every time you override the app, you introduce negative expected value. The edge comes from eliminating mistakes across hundreds of hands — not from making one brilliant play. Your job is simple: <strong>Input the situation. Execute the decision. Repeat.</strong></p>
        </div>
    """, unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### ✅ Do This")
        st.markdown("""
            <div class="do-i">✓&nbsp;&nbsp; Follow every decision — no exceptions</div>
            <div class="do-i">✓&nbsp;&nbsp; End sessions when alerts trigger</div>
            <div class="do-i">✓&nbsp;&nbsp; Play only the stakes your bankroll supports</div>
            <div class="do-i">✓&nbsp;&nbsp; Track every session honestly</div>
            <div class="do-i">✓&nbsp;&nbsp; Trust the process during downswings</div>
            <div class="do-i">✓&nbsp;&nbsp; Use the app for every single hand</div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown("#### ❌ Don't Do This")
        st.markdown("""
            <div class="dont-i">✗&nbsp;&nbsp; Override decisions based on gut feeling</div>
            <div class="dont-i">✗&nbsp;&nbsp; Keep playing after hitting stop-loss</div>
            <div class="dont-i">✗&nbsp;&nbsp; Move up stakes before your bankroll allows</div>
            <div class="dont-i">✗&nbsp;&nbsp; Skip tracking when you lose</div>
            <div class="dont-i">✗&nbsp;&nbsp; Panic and quit during normal variance</div>
            <div class="dont-i">✗&nbsp;&nbsp; Only use the app for "tough spots"</div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ===== QUICK START =====
    st.markdown('<div class="sdiv"><h2>Quick Start — 5 Minutes</h2><p>Everything you need to begin your first session</p></div>', unsafe_allow_html=True)

    st.markdown("""
        <div class="qs"><div class="qs-n">1</div><div class="qs-t"><strong>Set your bankroll</strong> — Go to Settings and enter your total poker bankroll</div></div>
        <div class="qs"><div class="qs-n">2</div><div class="qs-t"><strong>Choose your risk mode</strong> — Balanced is recommended for most players</div></div>
        <div class="qs"><div class="qs-n">3</div><div class="qs-t"><strong>Check Bankroll Health</strong> — Confirm you're playing the right stakes</div></div>
        <div class="qs"><div class="qs-n">4</div><div class="qs-t"><strong>Start a session</strong> — Go to Play Session when you sit down at a table</div></div>
        <div class="qs"><div class="qs-n">5</div><div class="qs-t"><strong>Follow every decision</strong> — Input your cards, get your action, execute it</div></div>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ===== FAQ =====
    st.markdown('<div class="sdiv"><h2>Frequently Asked Questions</h2><p>Common questions from new users</p></div>', unsafe_allow_html=True)

    with st.expander("How fast can I input my cards and get a decision?"):
        st.markdown("About **3-5 seconds** for most situations. The app is designed for speed — you'll have your answer well before your turn timer runs out. With practice, many users get it down to 2-3 seconds.")

    with st.expander("What if the app tells me to fold a hand I want to play?"):
        st.markdown("**Fold it.** The app isn't trying to make poker fun — it's trying to make you money. That \"fun\" hand is likely costing you money long-term. Trust the math.")

    with st.expander("How long until I see results?"):
        st.markdown("Poker has variance. Most users see their true win rate emerge after **50-100 sessions** (10,000-20,000 hands). See the **EV System** page for detailed monthly expectations.")

    with st.expander("What stakes should I play?"):
        st.markdown("The app tells you based on your bankroll. Check the **Bankroll Health** page — it shows exactly what stakes you can safely play and when you can move up. Never play stakes your bankroll doesn't support.")

    with st.expander("Does this work for tournaments?"):
        st.markdown("**No.** This app is designed specifically for **6-max No-Limit Hold'em cash games**. Tournament poker has different considerations (ICM, stack sizes, blind levels) that this app doesn't account for.")

    with st.expander("How does it handle bluffs?"):
        st.markdown("The engine identifies profitable bluff spots — dry board c-bets, river barrels, turn probes — and calculates exact EV: break-even fold %, estimated opponent fold rate, and expected profit per bluff. All bluffs are limited to heads-up pots where fold equity exists. Your bluff stats are tracked over time.")

    with st.expander("What about multiway pots (3+ players)?"):
        st.markdown("The engine asks how many players are in the hand on every postflop street. In multiway pots: no bluffs, bigger protection bets with strong hands (75% pot), and checks with medium hands. Player count updates as players fold between streets.")

    with st.expander("Why is the subscription $299/month?"):
        st.markdown("At $1/$2 stakes playing 10 sessions/week, the sim-verified expected monthly gross is **$1,120** (net **$821 after the $299 subscription**). At $2/$5 it's **$2,800 gross / $2,501 net**. The app pays for itself in roughly **11 sessions at $1/$2** or **4 sessions at $2/$5**. See the **EV System** page for the full breakdown.")

    with st.expander("What about rakeback?"):
        st.markdown("Rakeback is money your poker site returns to you from the rake collected on every hand — and it stacks on top of your win rate. At $1/$2 with a typical 30% rakeback deal, you can collect **$336–$480/month** in rakeback alone, which more than covers the $299 subscription before your table winnings even factor in. If you're not collecting rakeback, you're leaving real money on the table. See the **EV System** page for the full rakeback breakdown by stakes.")


if __name__ == "__main__":
    main()