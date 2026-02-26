# =============================================================================
# 08_Master_Your_Play.py — Master Your Play: The Complete Playbook
# =============================================================================

import streamlit as st

st.set_page_config(
    page_title="Master Your Play | Poker Decision App",
    page_icon="🏆",
    layout="wide",
)

from auth import require_auth
from sidebar import render_sidebar

user = require_auth()
render_sidebar()

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');
.block-container { max-width: 1400px; }

/* Hero */
.m-hero {
    background: linear-gradient(160deg, #2e1065 0%, #4c1d95 50%, #5b21b6 100%);
    border-radius: 20px; padding: 56px 48px; text-align: center; color: white;
    margin-bottom: 40px; position: relative; overflow: hidden;
}
.m-hero::before {
    content: ''; position: absolute; bottom: -30%; left: -10%; width: 400px; height: 400px;
    background: radial-gradient(circle, rgba(255,255,255,0.04) 0%, transparent 70%); pointer-events: none;
}
.m-hero h1 { font-family: 'DM Sans', sans-serif; font-size: 38px; font-weight: 700; margin-bottom: 16px; }
.m-hero p { font-size: 18px; opacity: 0.9; max-width: 700px; margin: 0 auto; line-height: 1.7; }

/* Section headers */
.sec {
    background: linear-gradient(135deg, #1f2937 0%, #111827 100%);
    border-radius: 14px; padding: 24px 32px; margin: 44px 0 24px 0;
}
.sec-num {
    display: inline-flex; align-items: center; justify-content: center;
    background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
    color: white; width: 32px; height: 32px; border-radius: 50%;
    font-weight: 700; font-size: 14px; margin-right: 12px;
}
.sec h2 { display: inline; font-family: 'DM Sans', sans-serif; font-size: 22px; font-weight: 700; color: white; }
.sec p { font-size: 14px; color: #9ca3af; margin-top: 8px; margin-bottom: 0; }

/* Mindset quote */
.mquote {
    background: linear-gradient(135deg, #0f172a 0%, #162032 100%);
    border-left: 4px solid #8b5cf6; border-radius: 0 14px 14px 0;
    padding: 28px; margin: 20px 0;
}
.mquote-text { font-size: 18px; font-style: italic; color: #e2e8f0; line-height: 1.65; margin-bottom: 12px; }
.mquote-src { font-size: 14px; color: #8b5cf6; font-weight: 600; }

/* Do/Don't */
.do-c {
    display: flex; align-items: center; gap: 12px; padding: 14px 18px;
    background: rgba(34,197,94,0.06); border: 1px solid rgba(34,197,94,0.2);
    border-radius: 10px; margin-bottom: 8px; font-size: 14px; color: #d1fae5;
}
.dont-c {
    display: flex; align-items: center; gap: 12px; padding: 14px 18px;
    background: rgba(239,68,68,0.06); border: 1px solid rgba(239,68,68,0.2);
    border-radius: 10px; margin-bottom: 8px; font-size: 14px; color: #fecaca;
}

/* Golden rules */
.grule {
    background: linear-gradient(135deg, rgba(245,158,11,0.08) 0%, rgba(245,158,11,0.04) 100%);
    border: 1px solid rgba(245,158,11,0.25); border-radius: 12px; padding: 20px; margin-bottom: 12px;
}
.grule-num {
    display: inline-flex; align-items: center; justify-content: center;
    background: #f59e0b; color: white; width: 28px; height: 28px;
    border-radius: 50%; font-weight: 700; font-size: 14px; margin-right: 12px;
}
.grule-title { display: inline; font-size: 16px; font-weight: 600; color: #fbbf24; }
.grule-detail { font-size: 14px; color: #d4d4d8; margin-top: 8px; padding-left: 40px; line-height: 1.65; }

/* Timeline */
.tl-item { display: flex; gap: 20px; margin-bottom: 24px; }
.tl-marker {
    width: 48px; height: 48px; background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
    border-radius: 50%; display: flex; align-items: center; justify-content: center;
    color: white; font-size: 20px; flex-shrink: 0;
}
.tl-content {
    flex: 1; background: linear-gradient(135deg, #0f172a 0%, #162032 100%);
    border: 1px solid #1e293b; border-radius: 14px; padding: 22px;
}
.tl-title { font-size: 18px; font-weight: 600; color: #f1f5f9; margin-bottom: 8px; }
.tl-desc { font-size: 14px; color: #94a3b8; line-height: 1.65; }
.tl-list { margin-top: 12px; padding-left: 0; list-style: none; }
.tl-list li { font-size: 14px; color: #cbd5e1; padding: 4px 0 4px 24px; position: relative; }
.tl-list li:before { content: "✓"; position: absolute; left: 0; color: #22c55e; font-weight: 700; }

/* Leak cards */
.lcard {
    background: linear-gradient(135deg, #0f172a 0%, #162032 100%);
    border: 1px solid #1e293b; border-left: 4px solid #ef4444;
    border-radius: 0 12px 12px 0; padding: 20px; margin-bottom: 12px;
}
.lcard-title { font-size: 16px; font-weight: 600; color: #f1f5f9; margin-bottom: 4px; display: flex; align-items: center; gap: 10px; }
.lcard-cost { background: rgba(239,68,68,0.15); color: #ef4444; padding: 2px 10px; border-radius: 6px; font-size: 12px; font-weight: 600; }
.lcard-desc { font-size: 14px; color: #94a3b8; line-height: 1.6; margin: 8px 0; }
.lcard-fix { font-size: 13px; color: #22c55e; font-weight: 500; }

/* Variance */
.vbox {
    background: linear-gradient(135deg, #0f172a 0%, #162032 100%);
    border: 1px solid #1e293b; border-radius: 14px; padding: 28px; margin: 16px 0;
}
.vbox h3 { font-size: 18px; font-weight: 600; color: #f1f5f9; margin: 0 0 12px 0; }
.vbox p { font-size: 14px; color: #94a3b8; line-height: 1.7; margin: 0; }

.vstat {
    background: rgba(59,130,246,0.1); border: 1px solid rgba(59,130,246,0.3);
    border-radius: 10px; padding: 18px; text-align: center; margin: 8px 0;
}
.vstat-val { font-size: 28px; font-weight: 700; color: #60a5fa; }
.vstat-label { font-size: 12px; color: #94a3b8; margin-top: 4px; }

/* Data table */
.dtable { width: 100%; border-collapse: collapse; margin: 16px 0; }
.dtable th { background: #1e293b; color: #94a3b8; padding: 12px 16px; text-align: left; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 1px solid #334155; }
.dtable td { padding: 12px 16px; border-bottom: 1px solid #1e293b; font-size: 14px; color: #e2e8f0; }
.dtable tr:hover { background: rgba(59,130,246,0.06); }
.pos { color: #22c55e; font-weight: 600; }
.neg { color: #ef4444; font-weight: 600; }

/* Info/warning boxes */
.ibox {
    background: linear-gradient(135deg, rgba(34,197,94,0.08) 0%, rgba(34,197,94,0.03) 100%);
    border-left: 4px solid #22c55e; border-radius: 0 10px 10px 0; padding: 18px 22px; margin: 16px 0;
}
.ibox h4 { font-size: 14px; font-weight: 600; color: #22c55e; margin: 0 0 8px 0; }
.ibox p { font-size: 14px; color: #e2e8f0; line-height: 1.65; margin: 0; }

.wbox {
    background: linear-gradient(135deg, rgba(245,158,11,0.08) 0%, rgba(245,158,11,0.03) 100%);
    border-left: 4px solid #f59e0b; border-radius: 0 10px 10px 0; padding: 18px 22px; margin: 16px 0;
}
.wbox h4 { font-size: 14px; font-weight: 600; color: #f59e0b; margin: 0 0 8px 0; }
.wbox p { font-size: 14px; color: #e2e8f0; line-height: 1.65; margin: 0; }

/* Bankroll discipline boxes */
.disc-box {
    background: linear-gradient(135deg, #7c3aed 0%, #6366f1 100%);
    border-radius: 14px; padding: 24px; color: white; margin: 16px 0;
}
.disc-box h3 { font-size: 18px; font-weight: 600; margin: 0 0 12px 0; }
.disc-box p { font-size: 14px; opacity: 0.92; line-height: 1.7; margin: 0; }

.disc-box-red {
    background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
    border-radius: 14px; padding: 24px; color: white; margin: 16px 0;
}
.disc-box-red h3 { font-size: 18px; font-weight: 600; margin: 0 0 12px 0; }
.disc-box-red p { font-size: 14px; opacity: 0.92; line-height: 1.7; margin: 0; }

/* Profit formula card */
.fcard-big {
    background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
    border-radius: 16px; padding: 36px; color: white; text-align: center; margin: 24px 0;
}
.fcard-eq { font-size: 22px; font-weight: 700; margin-bottom: 16px; font-family: 'DM Sans', monospace; }
.fcard-bd { font-size: 14px; opacity: 0.9; line-height: 1.8; }

/* Pillar cards for profit formula */
.pf-card {
    background: rgba(34,197,94,0.06); border: 1px solid rgba(34,197,94,0.2);
    border-radius: 14px; padding: 24px; text-align: center; height: 100%;
}
.pf-card-icon { font-size: 32px; margin-bottom: 8px; }
.pf-card-title { font-size: 16px; font-weight: 600; color: #22c55e; margin-bottom: 6px; }
.pf-card-desc { font-size: 13px; color: #94a3b8; line-height: 1.5; }
</style>
""", unsafe_allow_html=True)


def main():
    # ===== HERO =====
    st.markdown("""
        <div class="m-hero">
            <h1>🏆 Master Your Play</h1>
            <p>
                Everything you need to maximize your profits. Follow these rules,
                avoid these mistakes, and trust the process. This is your complete
                playbook for consistent poker income.
            </p>
        </div>
    """, unsafe_allow_html=True)

    # ===== SECTION 1: WINNING MINDSET =====
    st.markdown('<div class="sec"><span class="sec-num">1</span><h2>The Winning Mindset</h2><p>The mental framework that separates winners from losers</p></div>', unsafe_allow_html=True)

    st.markdown("""
        <div class="mquote">
            <div class="mquote-text">
                "You are not a poker player anymore. You are an execution machine.
                Your job is to input the situation, receive the optimal action, and execute it
                without hesitation, emotion, or second-guessing. The math does the thinking.
                You do the clicking."
            </div>
            <div class="mquote-src">— The Core Philosophy</div>
        </div>
    """, unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### The Old Way (Losing)")
        st.markdown("""
            <div class="dont-c">✗&nbsp;&nbsp; "I feel like he's bluffing"</div>
            <div class="dont-c">✗&nbsp;&nbsp; "This hand is too good to fold"</div>
            <div class="dont-c">✗&nbsp;&nbsp; "I need to win this pot back"</div>
            <div class="dont-c">✗&nbsp;&nbsp; "Let me just play one more hour"</div>
            <div class="dont-c">✗&nbsp;&nbsp; "I run so bad, the app must be wrong"</div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown("#### The New Way (Winning)")
        st.markdown("""
            <div class="do-c">✓&nbsp;&nbsp; "The app says fold. I fold."</div>
            <div class="do-c">✓&nbsp;&nbsp; "The math says call. I call."</div>
            <div class="do-c">✓&nbsp;&nbsp; "I hit my stop-loss. Session over."</div>
            <div class="do-c">✓&nbsp;&nbsp; "3 hours done. Time to quit."</div>
            <div class="do-c">✓&nbsp;&nbsp; "Variance happens. Trust the process."</div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ===== SECTION 2: THE 10 GOLDEN RULES =====
    st.markdown('<div class="sec"><span class="sec-num">2</span><h2>The 10 Golden Rules</h2><p>Non-negotiable principles for profitable poker</p></div>', unsafe_allow_html=True)

    rules = [
        ("Follow Every Decision the App Gives You",
         "No exceptions. No overrides. No gut feelings. The app's decision is always the decision you make. Every time you deviate, you're introducing -EV."),
        ("Never Play Above Your Bankroll",
         "If Bankroll Health says you're at $1/$2, you play $1/$2. Not $2/$5 because you're 'feeling good.' Stakes are determined by math, not emotion."),
        ("End Sessions When Told To",
         "Hit your stop-loss? Stop. Hit your stop-win? Stop. Hit 3 hours? Stop. The app ends sessions at optimal points — not when you feel like it."),
        ("Track Every Session Accurately",
         "Log your true results — wins and losses. The data only helps you if it's honest. Lying to the app means lying to yourself."),
        ("Never Chase Losses",
         "Down a buy-in? That's normal variance, not a signal to play differently. The next hand's math is the same whether you're up or down."),
        ("Never Play Tired, Drunk, or Tilted",
         "If you're not at 100% mental capacity, don't sit down. The app can give perfect advice, but you need to execute it properly."),
        ("Use the App Every Single Hand",
         "Not just the 'tough' spots. Every. Single. Hand. The edge comes from consistency, not occasional use."),
        ("Trust the Process During Downswings",
         "You will have losing weeks. Maybe losing months. If you're following the app perfectly, the math will catch up. Don't abandon ship."),
        ("Move Down When Required",
         "If your bankroll drops below the threshold, move down immediately. Ego has no place in bankroll management."),
        ("Treat Poker as a Job, Not Entertainment",
         "You're not here to have fun or gamble. You're here to execute a profitable system. Discipline is the product, profit is the result."),
    ]

    c1, c2 = st.columns(2)
    for i, (rule, detail) in enumerate(rules):
        with c1 if i < 5 else c2:
            st.markdown(f"""
                <div class="grule">
                    <span class="grule-num">{i+1}</span>
                    <span class="grule-title">{rule}</span>
                    <div class="grule-detail">{detail}</div>
                </div>
            """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ===== SECTION 3: SESSION EXCELLENCE =====
    st.markdown('<div class="sec"><span class="sec-num">3</span><h2>Session Excellence</h2><p>Before, during, and after every session</p></div>', unsafe_allow_html=True)

    st.markdown("""
        <div class="tl-item">
            <div class="tl-marker">📋</div>
            <div class="tl-content">
                <div class="tl-title">Before You Start</div>
                <div class="tl-desc">Set yourself up for a profitable session</div>
                <ul class="tl-list">
                    <li>Check Bankroll Health — confirm you're at the right stakes</li>
                    <li>Mental check — are you focused, rested, and emotion-free?</li>
                    <li>Environment — minimize distractions, have the app ready</li>
                    <li>Time — do you have 2-3 uninterrupted hours?</li>
                    <li>Start Session in the app — lock in your stakes and buy-in</li>
                </ul>
            </div>
        </div>

        <div class="tl-item">
            <div class="tl-marker">🎯</div>
            <div class="tl-content">
                <div class="tl-title">During Play</div>
                <div class="tl-desc">Execute with discipline and precision</div>
                <ul class="tl-list">
                    <li>Input every hand into the app — no exceptions</li>
                    <li>Execute the exact action given — no modifications</li>
                    <li>Record each outcome (Won/Lost/Folded)</li>
                    <li>On postflop streets, update the player count as opponents fold out</li>
                    <li>Monitor session time — respect the alerts</li>
                    <li>If stop-loss or stop-win triggers, end immediately</li>
                    <li>If tilt warning appears after consecutive losses, take it seriously</li>
                </ul>
            </div>
        </div>

        <div class="tl-item">
            <div class="tl-marker">📊</div>
            <div class="tl-content">
                <div class="tl-title">After the Session</div>
                <div class="tl-desc">Review, record, and reset</div>
                <ul class="tl-list">
                    <li>End Session properly — enter your final stack</li>
                    <li>Review the session summary — note any patterns</li>
                    <li>Check your bluff success rate — are you executing the bluff spots?</li>
                    <li>Update bankroll if needed</li>
                    <li>Take a break before the next session (minimum 30 min)</li>
                    <li>Don't dwell on bad beats — the math is still the math</li>
                </ul>
            </div>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ===== SECTION 4: COMMON LEAKS =====
    st.markdown('<div class="sec"><span class="sec-num">4</span><h2>Common Leaks That Destroy Your Edge</h2><p>Mistakes that cost real money — and how to fix them</p></div>', unsafe_allow_html=True)

    leaks = [
        ("Overriding the App's Decisions", "-2 to -4 BB/100",
         "Every time you think you know better, you're usually wrong. The app has calculated thousands of scenarios you haven't considered.",
         "Remove the option. Decide now that you will never override. Make it automatic."),
        ("Playing Too Long", "-1 to -2 BB/100",
         "After 3-4 hours, your decision quality degrades significantly. The extra hands you play at reduced capacity cost more than they make.",
         "Set a hard timer. When it goes off, you're done. No exceptions."),
        ("Ignoring Stop-Loss", "-3 to -5 BB/100",
         "Chasing losses leads to tilted play, which leads to bigger losses. One bad session becomes a catastrophic session.",
         "Treat the stop-loss as a circuit breaker. It's protecting you from yourself."),
        ("Playing Wrong Stakes", "Risk of Ruin",
         "Playing $2/$5 on a $1/$2 bankroll means one bad session can cripple you. Proper stakes protect your ability to keep playing.",
         "Check Bankroll Health before every session. Play only at approved stakes."),
        ("Selective App Usage", "-1 to -2 BB/100",
         "Only using the app for 'tough spots' and playing your own strategy otherwise. The edge comes from consistency across ALL hands.",
         "Every hand. Every street. Every decision. No exceptions."),
        ("Emotional Decision-Making", "-2 to -3 BB/100",
         "Playing differently because you're frustrated, excited, or bored. Your emotional state should never change your actions.",
         "If you feel emotional, take a break. Resume when calm. Or end the session."),
        ("Playing Distracted", "-1 to -2 BB/100",
         "Watching TV, texting, or browsing while playing. You miss bet sizes, misread boards, and make input errors.",
         "Poker only. Full attention. Treat it like a job that requires focus."),
        ("Results-Oriented Thinking", "Psychological",
         "Judging decisions by outcomes instead of process. A fold that 'would have won' was still the right fold.",
         "Focus on execution, not results. Did you follow the app? Good. That's all that matters."),
        ("Bluffing When the App Says Check", "-1 to -3 BB/100",
         "Firing bluffs in multiway pots, on wet boards, or in spots where the engine says CHECK. The engine only bluffs in heads-up pots with calculated fold equity.",
         "If the app says CHECK, check. The engine has already evaluated whether a bluff is +EV in this exact spot."),
        ("Ignoring Tilt Warnings", "-2 to -4 BB/100",
         "The app tracks your loss streaks and warns you when tilt risk is high. Dismissing these warnings and continuing to play is one of the most expensive leaks.",
         "When the tilt warning appears, take a 15-minute break minimum. If you can't reset, end the session."),
    ]

    c1, c2 = st.columns(2)
    for i, (title, cost, desc, fix) in enumerate(leaks):
        with c1 if i % 2 == 0 else c2:
            st.markdown(f"""
                <div class="lcard">
                    <div class="lcard-title">⚠️ {title} <span class="lcard-cost">{cost}</span></div>
                    <div class="lcard-desc">{desc}</div>
                    <div class="lcard-fix">✓ {fix}</div>
                </div>
            """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ===== SECTION 5: VARIANCE REALITY =====
    st.markdown('<div class="sec"><span class="sec-num">5</span><h2>The Variance Reality</h2><p>What to expect — even when doing everything right</p></div>', unsafe_allow_html=True)

    c1, c2 = st.columns([2, 1])
    with c1:
        st.markdown("""
            <div class="vbox">
                <h3>You Will Lose — Sometimes for Weeks</h3>
                <p>
                    Even with a +7 BB/100 win rate, losing streaks are mathematically guaranteed.
                    This is not the app failing. This is not bad luck targeting you.
                    This is variance — and it's temporary.
                    <br><br>
                    <strong>The players who profit are not the ones who avoid downswings —
                    they're the ones who survive them without abandoning their strategy.</strong>
                </p>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("""
            <div class="ibox">
                <h4>💡 Key Insight</h4>
                <p>
                    A player with +7 BB/100 win rate can easily lose 10 buy-ins over 20,000 hands
                    due to normal variance. That's not unusual — it happens roughly 5% of the time.
                    This is why bankroll management exists. This is why you never play above your stakes.
                    <strong>Survive the downswing, and the math delivers.</strong>
                </p>
            </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown("""
            <div class="vstat">
                <div class="vstat-val">5-10</div>
                <div class="vstat-label">Buy-in downswings are normal</div>
            </div>
            <div class="vstat">
                <div class="vstat-val">10,000+</div>
                <div class="vstat-label">Hands to see true win rate</div>
            </div>
            <div class="vstat">
                <div class="vstat-val">50-100</div>
                <div class="vstat-label">Sessions for reliable data</div>
            </div>
            <div class="vstat">
                <div class="vstat-val">~25%</div>
                <div class="vstat-label">Of months will be negative</div>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("""
        <table class="dtable">
            <thead>
                <tr><th>Scenario</th><th>What Happens</th><th>How Often</th><th>Your Response</th></tr>
            </thead>
            <tbody>
                <tr>
                    <td>Lose 3 sessions in a row</td>
                    <td>Down ~$600 at $1/$2</td>
                    <td>~20% of the time</td>
                    <td class="pos">Keep playing. Normal variance.</td>
                </tr>
                <tr>
                    <td>Lose 5 buy-ins over 2 weeks</td>
                    <td>Down ~$1,000 at $1/$2</td>
                    <td>~10% of the time</td>
                    <td class="pos">Check stakes, keep going.</td>
                </tr>
                <tr>
                    <td>Breakeven for a month</td>
                    <td>No profit despite playing well</td>
                    <td>~20% of the time</td>
                    <td class="pos">Frustrating but expected. See EV System page.</td>
                </tr>
                <tr>
                    <td>Lose 10 buy-ins</td>
                    <td>Down ~$2,000 at $1/$2</td>
                    <td>~5% of the time</td>
                    <td class="neg">Move down if bankroll requires.</td>
                </tr>
                <tr>
                    <td>Negative month</td>
                    <td>Net loss for the entire month</td>
                    <td>~25% of months</td>
                    <td class="pos">The math works over quarters, not weeks. Keep executing.</td>
                </tr>
            </tbody>
        </table>
    """, unsafe_allow_html=True)

    st.markdown("""
        <div class="wbox">
            <h4>⚠️ The Danger Zone</h4>
            <p>
                The moment you start thinking "the app doesn't work" during a downswing is the moment
                you're most likely to abandon your strategy and start bleeding money. Roughly 1 in 4 months
                will be negative even with perfect play. The app works over <strong>thousands of hands</strong>,
                not dozens. Any 6-month stretch of disciplined play will show positive results.
            </p>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ===== SECTION 6: BANKROLL DISCIPLINE =====
    st.markdown('<div class="sec"><span class="sec-num">6</span><h2>Bankroll Discipline</h2><p>The rules that keep you in the game</p></div>', unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("""
            <div class="disc-box">
                <h3>💰 When to Move Up</h3>
                <p>
                    You move up when Bankroll Health says you can — not when you want to.
                    Typically this means 15+ buy-ins at the new stake level.
                    <br><br>
                    <strong>Wrong:</strong> "I won 3 sessions, time for $2/$5!"<br>
                    <strong>Right:</strong> "Bankroll Health shows I can play $2/$5. Moving up."
                </p>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("""
            <table class="dtable">
                <thead><tr><th>Stakes</th><th>Min Bankroll</th><th>Safe Bankroll</th></tr></thead>
                <tbody>
                    <tr><td>$0.50/$1</td><td>$1,300</td><td>$2,000</td></tr>
                    <tr><td>$1/$2</td><td>$2,600</td><td>$4,000</td></tr>
                    <tr><td>$2/$5</td><td>$6,500</td><td>$10,000</td></tr>
                    <tr><td>$5/$10</td><td>$13,000</td><td>$20,000</td></tr>
                </tbody>
            </table>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown("""
            <div class="disc-box-red">
                <h3>📉 When to Move Down</h3>
                <p>
                    You move down immediately when your bankroll drops below the threshold.
                    Not "after one more session." Not "when I win it back." Immediately.
                    <br><br>
                    <strong>If you can't handle moving down, you can't handle winning at poker.</strong>
                    Moving down is not failure — it's survival.
                </p>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("""
            <div class="ibox">
                <h4>🔑 The Move-Down Rule</h4>
                <p>
                    Drop below 12 buy-ins at your current stake? Move down immediately.
                    No negotiation. This is how you protect your bankroll and ensure
                    you can always keep playing. The stakes will be there when you're ready.
                </p>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("""
            <div class="wbox">
                <h4>⚠️ Higher Stakes = Tougher Competition</h4>
                <p>
                    At $2/$5 and $5/$10, you face more regulars and fewer recreational players.
                    Your BB/100 win rate will be lower even with perfect play. The dollar profit
                    still increases because the stakes are bigger, but don't expect the same
                    edge you have at $1/$2. Move up for the right reasons — bankroll, not ego.
                </p>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ===== SECTION 7: HOW THE ENGINE PROTECTS YOU =====
    st.markdown('<div class="sec"><span class="sec-num">7</span><h2>How the Engine Protects You</h2><p>Built-in safeguards that prevent costly mistakes</p></div>', unsafe_allow_html=True)

    st.markdown("""
        <p style="font-size:14px;color:#94a3b8;line-height:1.7;margin-bottom:16px;">
            The decision engine doesn't just tell you what to bet — it actively prevents the most
            common and expensive mistakes that losing players make. Here's how:
        </p>
    """, unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("""
            <div class="ibox">
                <h4>🛡️ Multiway Pot Protection</h4>
                <p>The engine asks how many players are in the hand on every street. In 3+ player pots,
                it automatically stops you from firing bluffs (no fold equity) and shifts to bigger
                protection bets with strong hands. This alone prevents one of the biggest leaks in poker.</p>
            </div>
            <div class="ibox">
                <h4>🛡️ Bluff Discipline</h4>
                <p>Every bluff the engine recommends has a calculated EV — break-even fold percentage
                vs estimated opponent fold rate. If the math doesn't support it, the engine says CHECK.
                No more "I feel like they'll fold" bluffs that torch your stack.</p>
            </div>
            <div class="ibox">
                <h4>🛡️ Villain-Adjusted Sizing</h4>
                <p>Against fish, the engine automatically sizes up value bets by 20% because they call
                too wide. Against nits, it bluffs more and folds to their aggression. You get the right
                strategy for the opponent in front of you, every time.</p>
            </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown("""
            <div class="ibox">
                <h4>🛡️ Tilt Detection</h4>
                <p>The app monitors consecutive losses in real time. After a streak of losses,
                it triggers a tilt warning before your emotional state degrades your decisions.
                Combined with the 1 buy-in stop-loss, this prevents the #1 bankroll killer.</p>
            </div>
            <div class="ibox">
                <h4>🛡️ Check-Raise Defense</h4>
                <p>When an opponent check-raises you, most players either always fold (too tight) or
                always call (too loose). The engine calculates the exact right response based on
                your hand strength, pot odds, and board texture. No more guessing.</p>
            </div>
            <div class="ibox">
                <h4>🛡️ Investment Tracking</h4>
                <p>The app tracks exactly how much you've invested across every street of every hand.
                You always know your exposure. Combined with pot size tracking, you never lose track
                of the math — even in complex multi-street pots.</p>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ===== SECTION 8: THE PROFIT FORMULA =====
    st.markdown('<div class="sec"><span class="sec-num">8</span><h2>The Profit Formula</h2><p>Put it all together</p></div>', unsafe_allow_html=True)

    st.markdown("""
        <div class="fcard-big">
            <div class="fcard-eq">Perfect Execution + Proper Bankroll + Session Discipline = Consistent Profit</div>
            <div class="fcard-bd">
                Follow every decision × Play correct stakes × End sessions on time<br>
                = +5 to +8 BB/100 win rate = $9,800 to $54,000+/year net profit depending on stakes<br>
                <span style="font-size:12px;opacity:0.8;">(after $299/month subscription · app covers its cost in 4-11 sessions)</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("""
            <div class="pf-card">
                <div class="pf-card-icon">🎯</div>
                <div class="pf-card-title">Perfect Execution</div>
                <div class="pf-card-desc">Follow every app decision<br>without exception</div>
            </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown("""
            <div class="pf-card">
                <div class="pf-card-icon">💰</div>
                <div class="pf-card-title">Proper Bankroll</div>
                <div class="pf-card-desc">Play stakes your bankroll<br>supports — always</div>
            </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown("""
            <div class="pf-card">
                <div class="pf-card-icon">⏱️</div>
                <div class="pf-card-title">Session Discipline</div>
                <div class="pf-card-desc">End sessions at optimal<br>points — every time</div>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ===== FINAL STATEMENT =====
    st.markdown("""
        <div class="mquote" style="border-left-color:#22c55e;background:linear-gradient(135deg,rgba(34,197,94,0.06) 0%,rgba(34,197,94,0.02) 100%);">
            <div class="mquote-text" style="color:#d1fae5;">
                "The difference between a losing player and a winning player is not talent,
                luck, or reads. It's discipline. The math is available to everyone.
                The willingness to follow it perfectly — that's rare. That's what you're paying for.
                That's what makes you profitable."
            </div>
            <div class="mquote-src" style="color:#22c55e;">— Your Edge</div>
        </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()