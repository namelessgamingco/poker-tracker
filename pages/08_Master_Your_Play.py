# =============================================================================
# 08_Master_Your_Play.py — Master Your Play: The Complete Playbook
# =============================================================================
#
# PURPOSE:
# - Provide the complete actionable playbook for success
# - Emphasize behaviors that maximize profit
# - Warn against common mistakes that destroy edges
# - Set realistic expectations about variance
# - Reinforce the discipline required
#
# This is the practical guide - not theory, but RULES and BEHAVIORS.
#
# =============================================================================

import streamlit as st

st.set_page_config(
    page_title="Master Your Play | Poker Decision App",
    page_icon="🏆",
    layout="wide",
)

from auth import require_auth
from sidebar import render_sidebar

# ---------- Auth Gate ----------
user = require_auth()
render_sidebar()


# =============================================================================
# CUSTOM CSS
# =============================================================================

st.markdown("""
<style>
/* Hero section */
.mastery-hero {
    background: linear-gradient(135deg, #7c3aed 0%, #4f46e5 100%);
    border-radius: 16px;
    padding: 48px;
    text-align: center;
    color: white;
    margin-bottom: 32px;
}
.mastery-hero-title {
    font-size: 36px;
    font-weight: 700;
    margin-bottom: 16px;
}
.mastery-hero-subtitle {
    font-size: 18px;
    opacity: 0.9;
    max-width: 700px;
    margin: 0 auto;
    line-height: 1.7;
}

/* Section headers */
.section-header-dark {
    background: linear-gradient(135deg, #1f2937 0%, #111827 100%);
    border-radius: 12px;
    padding: 24px 32px;
    margin: 32px 0 24px 0;
}
.section-number {
    display: inline-block;
    background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
    color: white;
    width: 32px;
    height: 32px;
    border-radius: 50%;
    text-align: center;
    line-height: 32px;
    font-weight: 700;
    font-size: 14px;
    margin-right: 12px;
}
.section-title-text {
    font-size: 22px;
    font-weight: 700;
    color: white;
    display: inline;
}
.section-subtitle-text {
    font-size: 14px;
    color: #9ca3af;
    margin-top: 8px;
}

/* Golden rule cards */
.golden-rule {
    background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
    border: 2px solid #f59e0b;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 12px;
}
.golden-rule-number {
    background: #f59e0b;
    color: white;
    width: 28px;
    height: 28px;
    border-radius: 50%;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    font-size: 14px;
    margin-right: 12px;
}
.golden-rule-text {
    font-size: 16px;
    font-weight: 600;
    color: #92400e;
    display: inline;
}
.golden-rule-detail {
    font-size: 14px;
    color: #a16207;
    margin-top: 8px;
    padding-left: 40px;
    line-height: 1.6;
}

/* Do/Don't cards */
.do-card {
    background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
    border: 2px solid #22c55e;
    border-radius: 12px;
    padding: 16px 20px;
    margin-bottom: 8px;
}
.do-icon {
    color: #22c55e;
    font-weight: 700;
    margin-right: 12px;
}
.do-text {
    font-size: 15px;
    color: #166534;
}

.dont-card {
    background: linear-gradient(135deg, #fef2f2 0%, #fecaca 100%);
    border: 2px solid #ef4444;
    border-radius: 12px;
    padding: 16px 20px;
    margin-bottom: 8px;
}
.dont-icon {
    color: #ef4444;
    font-weight: 700;
    margin-right: 12px;
}
.dont-text {
    font-size: 15px;
    color: #991b1b;
}

/* Timeline/process */
.timeline-item {
    display: flex;
    gap: 20px;
    margin-bottom: 24px;
}
.timeline-marker {
    width: 48px;
    height: 48px;
    background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-size: 20px;
    flex-shrink: 0;
}
.timeline-content {
    flex: 1;
    background: #f8fafc;
    border-radius: 12px;
    padding: 20px;
    border: 1px solid #e2e8f0;
}
.timeline-title {
    font-size: 18px;
    font-weight: 600;
    color: #1e293b;
    margin-bottom: 8px;
}
.timeline-description {
    font-size: 14px;
    color: #64748b;
    line-height: 1.6;
}
.timeline-checklist {
    margin-top: 12px;
    padding-left: 0;
    list-style: none;
}
.timeline-checklist li {
    font-size: 14px;
    color: #475569;
    padding: 4px 0;
    padding-left: 24px;
    position: relative;
}
.timeline-checklist li:before {
    content: "✓";
    position: absolute;
    left: 0;
    color: #22c55e;
    font-weight: 700;
}

/* Leak cards */
.leak-card {
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 12px;
    border-left: 4px solid #ef4444;
}
.leak-title {
    font-size: 16px;
    font-weight: 600;
    color: #1f2937;
    margin-bottom: 8px;
    display: flex;
    align-items: center;
    gap: 8px;
}
.leak-cost {
    background: #fef2f2;
    color: #ef4444;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 600;
}
.leak-description {
    font-size: 14px;
    color: #6b7280;
    line-height: 1.6;
    margin-bottom: 8px;
}
.leak-fix {
    font-size: 13px;
    color: #22c55e;
    font-weight: 500;
}

/* Variance reality */
.variance-box {
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
    border-radius: 12px;
    padding: 24px;
    color: white;
    margin: 16px 0;
}
.variance-title {
    font-size: 18px;
    font-weight: 600;
    margin-bottom: 12px;
    color: #f1f5f9;
}
.variance-content {
    font-size: 14px;
    color: #94a3b8;
    line-height: 1.7;
}
.variance-stat {
    background: rgba(59, 130, 246, 0.2);
    border: 1px solid #3b82f6;
    border-radius: 8px;
    padding: 16px;
    text-align: center;
    margin: 8px 0;
}
.variance-stat-value {
    font-size: 28px;
    font-weight: 700;
    color: #3b82f6;
}
.variance-stat-label {
    font-size: 12px;
    color: #94a3b8;
    margin-top: 4px;
}

/* Discipline box */
.discipline-box {
    background: linear-gradient(135deg, #7c3aed 0%, #6366f1 100%);
    border-radius: 12px;
    padding: 24px;
    color: white;
    margin: 16px 0;
}
.discipline-title {
    font-size: 18px;
    font-weight: 600;
    margin-bottom: 12px;
}
.discipline-content {
    font-size: 14px;
    opacity: 0.9;
    line-height: 1.7;
}

/* Profit formula */
.formula-card {
    background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
    border-radius: 16px;
    padding: 32px;
    color: white;
    text-align: center;
    margin: 24px 0;
}
.formula-equation {
    font-size: 24px;
    font-weight: 700;
    margin-bottom: 16px;
    font-family: 'Monaco', monospace;
}
.formula-breakdown {
    font-size: 14px;
    opacity: 0.9;
    line-height: 1.8;
}

/* Mindset quote */
.mindset-quote {
    background: #f8fafc;
    border-left: 4px solid #8b5cf6;
    border-radius: 0 12px 12px 0;
    padding: 24px;
    margin: 24px 0;
}
.mindset-quote-text {
    font-size: 18px;
    font-style: italic;
    color: #1e293b;
    line-height: 1.6;
    margin-bottom: 12px;
}
.mindset-quote-source {
    font-size: 14px;
    color: #64748b;
}

/* Key insight */
.key-insight {
    background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
    border: 2px solid #3b82f6;
    border-radius: 12px;
    padding: 20px;
    margin: 16px 0;
}
.key-insight-title {
    font-size: 14px;
    font-weight: 600;
    color: #1d4ed8;
    margin-bottom: 8px;
    display: flex;
    align-items: center;
    gap: 8px;
}
.key-insight-content {
    font-size: 14px;
    color: #1e40af;
    line-height: 1.6;
}

/* Stakes table */
.stakes-table {
    width: 100%;
    border-collapse: collapse;
    margin: 16px 0;
    background: white;
    border-radius: 8px;
    overflow: hidden;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}
.stakes-table th {
    background: #1f2937;
    color: white;
    padding: 12px 16px;
    text-align: left;
    font-size: 13px;
    font-weight: 600;
}
.stakes-table td {
    padding: 12px 16px;
    border-bottom: 1px solid #e5e7eb;
    font-size: 14px;
    color: #374151;
}
.stakes-table tr:last-child td {
    border-bottom: none;
}
.highlight-green { color: #22c55e; font-weight: 600; }
.highlight-red { color: #ef4444; font-weight: 600; }
</style>
""", unsafe_allow_html=True)


# =============================================================================
# MAIN PAGE
# =============================================================================

def main():
    """Main render function."""
    
    # ===== HERO SECTION =====
    st.markdown("""
        <div class="mastery-hero">
            <div class="mastery-hero-title">🏆 Master Your Play</div>
            <div class="mastery-hero-subtitle">
                Everything you need to know to maximize your profits. 
                Follow these rules, avoid these mistakes, and trust the process. 
                This is your complete playbook for consistent poker income.
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    # ===== SECTION 1: THE WINNING MINDSET =====
    st.markdown("""
        <div class="section-header-dark">
            <span class="section-number">1</span>
            <span class="section-title-text">The Winning Mindset</span>
            <div class="section-subtitle-text">The mental framework that separates winners from losers</div>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
        <div class="mindset-quote">
            <div class="mindset-quote-text">
                "You are not a poker player anymore. You are an execution machine. 
                Your job is to input the situation, receive the optimal action, and execute it 
                without hesitation, emotion, or second-guessing. The math does the thinking. 
                You do the clicking."
            </div>
            <div class="mindset-quote-source">— The Core Philosophy</div>
        </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### The Old Way (Losing)")
        st.markdown("""
            <div class="dont-card">
                <span class="dont-icon">✗</span>
                <span class="dont-text">"I feel like he's bluffing"</span>
            </div>
            <div class="dont-card">
                <span class="dont-icon">✗</span>
                <span class="dont-text">"This hand is too good to fold"</span>
            </div>
            <div class="dont-card">
                <span class="dont-icon">✗</span>
                <span class="dont-text">"I need to win this pot back"</span>
            </div>
            <div class="dont-card">
                <span class="dont-icon">✗</span>
                <span class="dont-text">"Let me just play one more hour"</span>
            </div>
            <div class="dont-card">
                <span class="dont-icon">✗</span>
                <span class="dont-text">"I run so bad, the app must be wrong"</span>
            </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("#### The New Way (Winning)")
        st.markdown("""
            <div class="do-card">
                <span class="do-icon">✓</span>
                <span class="do-text">"The app says fold. I fold."</span>
            </div>
            <div class="do-card">
                <span class="do-icon">✓</span>
                <span class="do-text">"The math says call. I call."</span>
            </div>
            <div class="do-card">
                <span class="do-icon">✓</span>
                <span class="do-text">"I hit my stop-loss. Session over."</span>
            </div>
            <div class="do-card">
                <span class="do-icon">✓</span>
                <span class="do-text">"3 hours done. Time to quit."</span>
            </div>
            <div class="do-card">
                <span class="do-icon">✓</span>
                <span class="do-text">"Variance happens. Trust the process."</span>
            </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # ===== SECTION 2: THE 10 GOLDEN RULES =====
    st.markdown("""
        <div class="section-header-dark">
            <span class="section-number">2</span>
            <span class="section-title-text">The 10 Golden Rules</span>
            <div class="section-subtitle-text">Non-negotiable principles for profitable poker</div>
        </div>
    """, unsafe_allow_html=True)
    
    rules = [
        {
            "rule": "Follow Every Decision the App Gives You",
            "detail": "No exceptions. No overrides. No gut feelings. The app's decision is always the decision you make. Every time you deviate, you're introducing -EV."
        },
        {
            "rule": "Never Play Above Your Bankroll",
            "detail": "If Bankroll Health says you're at $1/$2, you play $1/$2. Not $2/$5 because you're 'feeling good.' Stakes are determined by math, not emotion."
        },
        {
            "rule": "End Sessions When Told To",
            "detail": "Hit your stop-loss? Stop. Hit your stop-win? Stop. Hit 3 hours? Stop. The app ends sessions at optimal points — not when you feel like it."
        },
        {
            "rule": "Track Every Session Accurately",
            "detail": "Log your true results — wins and losses. The data only helps you if it's honest. Lying to the app means lying to yourself."
        },
        {
            "rule": "Never Chase Losses",
            "detail": "Down a buy-in? That's normal variance, not a signal to play differently. The next hand's math is the same whether you're up or down."
        },
        {
            "rule": "Never Play Tired, Drunk, or Tilted",
            "detail": "If you're not at 100% mental capacity, don't sit down. The app can give perfect advice, but you need to execute it properly."
        },
        {
            "rule": "Use the App Every Single Hand",
            "detail": "Not just the 'tough' spots. Every. Single. Hand. The edge comes from consistency, not occasional use."
        },
        {
            "rule": "Trust the Process During Downswings",
            "detail": "You will have losing weeks. Maybe losing months. If you're following the app perfectly, the math will catch up. Don't abandon ship."
        },
        {
            "rule": "Move Down When Required",
            "detail": "If your bankroll drops below the threshold, move down immediately. Ego has no place in bankroll management."
        },
        {
            "rule": "Treat Poker as a Job, Not Entertainment",
            "detail": "You're not here to have fun or gamble. You're here to execute a profitable system. Discipline is the product, profit is the result."
        },
    ]
    
    col1, col2 = st.columns(2)
    
    for i, rule in enumerate(rules):
        with col1 if i < 5 else col2:
            st.markdown(f"""
                <div class="golden-rule">
                    <span class="golden-rule-number">{i+1}</span>
                    <span class="golden-rule-text">{rule['rule']}</span>
                    <div class="golden-rule-detail">{rule['detail']}</div>
                </div>
            """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # ===== SECTION 3: SESSION EXCELLENCE =====
    st.markdown("""
        <div class="section-header-dark">
            <span class="section-number">3</span>
            <span class="section-title-text">Session Excellence</span>
            <div class="section-subtitle-text">Before, during, and after every session</div>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
        <div class="timeline-item">
            <div class="timeline-marker">📋</div>
            <div class="timeline-content">
                <div class="timeline-title">Before You Start</div>
                <div class="timeline-description">Set yourself up for a profitable session</div>
                <ul class="timeline-checklist">
                    <li>Check Bankroll Health — confirm you're at the right stakes</li>
                    <li>Mental check — are you focused, rested, and emotion-free?</li>
                    <li>Environment — minimize distractions, have the app ready</li>
                    <li>Time — do you have 2-3 uninterrupted hours?</li>
                    <li>Start Session in the app — lock in your stakes and buy-in</li>
                </ul>
            </div>
        </div>
        
        <div class="timeline-item">
            <div class="timeline-marker">🎯</div>
            <div class="timeline-content">
                <div class="timeline-title">During Play</div>
                <div class="timeline-description">Execute with discipline and precision</div>
                <ul class="timeline-checklist">
                    <li>Input every hand into the app — no exceptions</li>
                    <li>Execute the exact action given — no modifications</li>
                    <li>Record each outcome (Won/Lost/Folded)</li>
                    <li>Monitor session time — respect the alerts</li>
                    <li>If stop-loss or stop-win triggers, end immediately</li>
                    <li>Take table quality checks when prompted</li>
                </ul>
            </div>
        </div>
        
        <div class="timeline-item">
            <div class="timeline-marker">📊</div>
            <div class="timeline-content">
                <div class="timeline-title">After the Session</div>
                <div class="timeline-description">Review, record, and reset</div>
                <ul class="timeline-checklist">
                    <li>End Session properly — enter your final stack</li>
                    <li>Review the session summary — note any patterns</li>
                    <li>Update bankroll if needed</li>
                    <li>Take a break before the next session (minimum 30 min)</li>
                    <li>Don't dwell on bad beats — the math is still the math</li>
                </ul>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # ===== SECTION 4: COMMON LEAKS =====
    st.markdown("""
        <div class="section-header-dark">
            <span class="section-number">4</span>
            <span class="section-title-text">Common Leaks That Destroy Your Edge</span>
            <div class="section-subtitle-text">Mistakes that cost real money — and how to fix them</div>
        </div>
    """, unsafe_allow_html=True)
    
    leaks = [
        {
            "title": "Overriding the App's Decisions",
            "cost": "-2 to -4 BB/100",
            "description": "Every time you think you know better, you're usually wrong. The app has calculated thousands of scenarios you haven't considered.",
            "fix": "Fix: Remove the option. Decide now that you will never override. Make it automatic."
        },
        {
            "title": "Playing Too Long",
            "cost": "-1 to -2 BB/100",
            "description": "After 3-4 hours, your decision quality degrades significantly. The extra hands you play at reduced capacity cost more than they make.",
            "fix": "Fix: Set a hard timer. When it goes off, you're done. No exceptions."
        },
        {
            "title": "Ignoring Stop-Loss",
            "cost": "-3 to -5 BB/100",
            "description": "Chasing losses leads to tilted play, which leads to bigger losses. One bad session becomes a catastrophic session.",
            "fix": "Fix: Treat the stop-loss as a circuit breaker. It's protecting you from yourself."
        },
        {
            "title": "Playing Wrong Stakes",
            "cost": "Risk of Ruin",
            "description": "Playing $2/$5 on a $1/$2 bankroll means one bad session can cripple you. Proper stakes protect your ability to keep playing.",
            "fix": "Fix: Check Bankroll Health before every session. Play only at approved stakes."
        },
        {
            "title": "Selective App Usage",
            "cost": "-1 to -2 BB/100",
            "description": "Only using the app for 'tough spots' and playing your own strategy otherwise. The edge comes from consistency across ALL hands.",
            "fix": "Fix: Every hand. Every street. Every decision. No exceptions."
        },
        {
            "title": "Emotional Decision-Making",
            "cost": "-2 to -3 BB/100",
            "description": "Playing differently because you're frustrated, excited, or bored. Your emotional state should never change your actions.",
            "fix": "Fix: If you feel emotional, take a break. Resume when calm. Or end the session."
        },
        {
            "title": "Playing Distracted",
            "cost": "-1 to -2 BB/100",
            "description": "Watching TV, texting, or browsing while playing. You miss bet sizes, misread boards, and make input errors.",
            "fix": "Fix: Poker only. Full attention. Treat it like a job that requires focus."
        },
        {
            "title": "Results-Oriented Thinking",
            "cost": "Psychological",
            "description": "Judging decisions by outcomes instead of process. A fold that 'would have won' was still the right fold.",
            "fix": "Fix: Focus on execution, not results. Did you follow the app? Good. That's all that matters."
        },
    ]
    
    col1, col2 = st.columns(2)
    
    for i, leak in enumerate(leaks):
        with col1 if i % 2 == 0 else col2:
            st.markdown(f"""
                <div class="leak-card">
                    <div class="leak-title">
                        ⚠️ {leak['title']}
                        <span class="leak-cost">{leak['cost']}</span>
                    </div>
                    <div class="leak-description">{leak['description']}</div>
                    <div class="leak-fix">✓ {leak['fix']}</div>
                </div>
            """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # ===== SECTION 5: VARIANCE REALITY =====
    st.markdown("""
        <div class="section-header-dark">
            <span class="section-number">5</span>
            <span class="section-title-text">The Variance Reality</span>
            <div class="section-subtitle-text">What to expect — even when doing everything right</div>
        </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("""
            <div class="variance-box">
                <div class="variance-title">You Will Lose — Sometimes for Weeks</div>
                <div class="variance-content">
                    Even with a +6 BB/100 win rate, losing streaks are mathematically guaranteed. 
                    This is not the app failing. This is not bad luck targeting you. 
                    This is variance — and it's temporary.
                    <br><br>
                    <strong>The players who profit are not the ones who avoid downswings — 
                    they're the ones who survive them without abandoning their strategy.</strong>
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
            <div class="key-insight">
                <div class="key-insight-title">💡 Key Insight</div>
                <div class="key-insight-content">
                    A player with +6 BB/100 win rate can easily lose 10 buy-ins over 20,000 hands 
                    due to normal variance. That's not unusual — it's expected roughly 5% of the time. 
                    This is why bankroll management exists. This is why you never play above your stakes. 
                    <strong>Survive the downswing, and the math delivers.</strong>
                </div>
            </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
            <div class="variance-stat">
                <div class="variance-stat-value">5-10</div>
                <div class="variance-stat-label">Buy-in downswings are normal</div>
            </div>
            
            <div class="variance-stat">
                <div class="variance-stat-value">10,000+</div>
                <div class="variance-stat-label">Hands to see true win rate</div>
            </div>
            
            <div class="variance-stat">
                <div class="variance-stat-value">50-100</div>
                <div class="variance-stat-label">Sessions for reliable data</div>
            </div>
        """, unsafe_allow_html=True)
    
    st.markdown("""
        <table class="stakes-table">
            <thead>
                <tr>
                    <th>Scenario</th>
                    <th>What Happens</th>
                    <th>How Often</th>
                    <th>Your Response</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>Lose 3 sessions in a row</td>
                    <td>Down ~$600 at $1/$2</td>
                    <td>~20% of the time</td>
                    <td class="highlight-green">Keep playing. Normal variance.</td>
                </tr>
                <tr>
                    <td>Lose 5 buy-ins over 2 weeks</td>
                    <td>Down ~$1,000 at $1/$2</td>
                    <td>~10% of the time</td>
                    <td class="highlight-green">Check stakes, keep going.</td>
                </tr>
                <tr>
                    <td>Breakeven for a month</td>
                    <td>No profit despite playing well</td>
                    <td>~15% of the time</td>
                    <td class="highlight-green">Frustrating but expected.</td>
                </tr>
                <tr>
                    <td>Lose 10 buy-ins</td>
                    <td>Down ~$2,000 at $1/$2</td>
                    <td>~5% of the time</td>
                    <td class="highlight-red">Move down if bankroll requires.</td>
                </tr>
            </tbody>
        </table>
    """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # ===== SECTION 6: BANKROLL DISCIPLINE =====
    st.markdown("""
        <div class="section-header-dark">
            <span class="section-number">6</span>
            <span class="section-title-text">Bankroll Discipline</span>
            <div class="section-subtitle-text">The rules that keep you in the game</div>
        </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
            <div class="discipline-box">
                <div class="discipline-title">💰 When to Move Up</div>
                <div class="discipline-content">
                    You move up when Bankroll Health says you can — not when you want to. 
                    Typically this means 15+ buy-ins at the new stake level.
                    <br><br>
                    <strong>Wrong:</strong> "I won 3 sessions, time for $2/$5!"<br>
                    <strong>Right:</strong> "Bankroll Health shows I can play $2/$5. Moving up."
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
            <table class="stakes-table">
                <thead>
                    <tr>
                        <th>Stakes</th>
                        <th>Min Bankroll</th>
                        <th>Safe Bankroll</th>
                    </tr>
                </thead>
                <tbody>
                    <tr><td>$0.50/$1</td><td>$1,300</td><td>$2,000</td></tr>
                    <tr><td>$1/$2</td><td>$2,600</td><td>$4,000</td></tr>
                    <tr><td>$2/$5</td><td>$6,500</td><td>$10,000</td></tr>
                    <tr><td>$5/$10</td><td>$13,000</td><td>$20,000</td></tr>
                </tbody>
            </table>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
            <div class="discipline-box" style="background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);">
                <div class="discipline-title">📉 When to Move Down</div>
                <div class="discipline-content">
                    You move down immediately when your bankroll drops below the threshold. 
                    Not "after one more session." Not "when I win it back." Immediately.
                    <br><br>
                    <strong>If you can't handle moving down, you can't handle winning at poker.</strong>
                    Moving down is not failure — it's survival.
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
            <div class="key-insight">
                <div class="key-insight-title">🔑 The Move-Down Rule</div>
                <div class="key-insight-content">
                    Drop below 12 buy-ins at your current stake? Move down immediately. 
                    No negotiation. This is how you protect your bankroll and ensure 
                    you can always keep playing. The stakes will be there when you're ready.
                </div>
            </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # ===== SECTION 7: THE PROFIT FORMULA =====
    st.markdown("""
        <div class="section-header-dark">
            <span class="section-number">7</span>
            <span class="section-title-text">The Profit Formula</span>
            <div class="section-subtitle-text">Put it all together</div>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
        <div class="formula-card">
            <div class="formula-equation">
                Perfect Execution + Proper Bankroll + Session Discipline = Consistent Profit
            </div>
            <div class="formula-breakdown">
                Follow every decision × Play correct stakes × End sessions on time<br>
                = +6 BB/100 win rate = $20,000+/year at $1/$2
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
            <div class="do-card" style="text-align: center; padding: 24px;">
                <div style="font-size: 32px; margin-bottom: 8px;">🎯</div>
                <div style="font-size: 16px; font-weight: 600; color: #166534;">Perfect Execution</div>
                <div style="font-size: 13px; color: #22c55e; margin-top: 8px;">
                    Follow every app decision<br>without exception
                </div>
            </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
            <div class="do-card" style="text-align: center; padding: 24px;">
                <div style="font-size: 32px; margin-bottom: 8px;">💰</div>
                <div style="font-size: 16px; font-weight: 600; color: #166534;">Proper Bankroll</div>
                <div style="font-size: 13px; color: #22c55e; margin-top: 8px;">
                    Play stakes your bankroll<br>supports — always
                </div>
            </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
            <div class="do-card" style="text-align: center; padding: 24px;">
                <div style="font-size: 32px; margin-bottom: 8px;">⏱️</div>
                <div style="font-size: 16px; font-weight: 600; color: #166534;">Session Discipline</div>
                <div style="font-size: 13px; color: #22c55e; margin-top: 8px;">
                    End sessions at optimal<br>points — every time
                </div>
            </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # ===== FINAL STATEMENT =====
    st.markdown("""
        <div class="mindset-quote" style="background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%); border-color: #22c55e;">
            <div class="mindset-quote-text" style="color: #166534;">
                "The difference between a losing player and a winning player is not talent, 
                luck, or reads. It's discipline. The math is available to everyone. 
                The willingness to follow it perfectly — that's rare. That's what you're paying for. 
                That's what makes you profitable."
            </div>
            <div class="mindset-quote-source" style="color: #22c55e;">— Your Edge</div>
        </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()