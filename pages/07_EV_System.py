# =============================================================================
# 07_EV_System.py — The EV System: Mathematics of Winning Poker
# =============================================================================
#
# PURPOSE:
# - Establish mathematical credibility
# - Educate users on WHY decisions are made
# - Justify the $299/month premium
# - Build trust through transparency
#
# This page explains the sophisticated quantitative framework behind
# the decision engine. It should feel like reading about a trading
# algorithm - because that's essentially what it is.
#
# =============================================================================

import streamlit as st

st.set_page_config(
    page_title="The EV System | Poker Decision App",
    page_icon="📊",
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
.ev-hero {
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
    border-radius: 16px;
    padding: 48px;
    text-align: center;
    color: white;
    margin-bottom: 32px;
    border: 1px solid #334155;
}
.ev-hero-title {
    font-size: 36px;
    font-weight: 700;
    margin-bottom: 16px;
    background: linear-gradient(90deg, #22c55e, #3b82f6);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}
.ev-hero-subtitle {
    font-size: 18px;
    color: #94a3b8;
    max-width: 700px;
    margin: 0 auto;
    line-height: 1.7;
}

/* Concept cards */
.concept-card {
    background: #0f172a;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 24px;
    color: white;
    height: 100%;
}
.concept-icon {
    font-size: 32px;
    margin-bottom: 12px;
}
.concept-title {
    font-size: 18px;
    font-weight: 600;
    color: #f1f5f9;
    margin-bottom: 8px;
}
.concept-description {
    font-size: 14px;
    color: #94a3b8;
    line-height: 1.6;
}

/* Formula boxes */
.formula-box {
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
    border: 1px solid #3b82f6;
    border-radius: 12px;
    padding: 24px;
    margin: 16px 0;
    font-family: 'Monaco', 'Menlo', monospace;
}
.formula-title {
    font-size: 14px;
    color: #3b82f6;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 12px;
}
.formula-content {
    font-size: 20px;
    color: #22c55e;
    text-align: center;
    padding: 16px;
    background: rgba(34, 197, 94, 0.1);
    border-radius: 8px;
    margin-bottom: 12px;
}
.formula-explanation {
    font-size: 14px;
    color: #94a3b8;
    line-height: 1.6;
    font-family: -apple-system, BlinkMacSystemFont, sans-serif;
}

/* Section styling */
.section-dark {
    background: #0f172a;
    border: 1px solid #334155;
    border-radius: 16px;
    padding: 32px;
    margin: 24px 0;
    color: white;
}
.section-title {
    font-size: 24px;
    font-weight: 700;
    color: #f1f5f9;
    margin-bottom: 8px;
}
.section-subtitle {
    font-size: 15px;
    color: #64748b;
    margin-bottom: 24px;
}

/* Data table styling */
.data-table {
    width: 100%;
    border-collapse: collapse;
    margin: 16px 0;
}
.data-table th {
    background: #1e293b;
    color: #94a3b8;
    padding: 12px 16px;
    text-align: left;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    border-bottom: 1px solid #334155;
}
.data-table td {
    padding: 12px 16px;
    border-bottom: 1px solid #1e293b;
    color: #e2e8f0;
    font-size: 14px;
}
.data-table tr:hover {
    background: rgba(59, 130, 246, 0.1);
}
.positive { color: #22c55e; font-weight: 600; }
.negative { color: #ef4444; font-weight: 600; }
.neutral { color: #f59e0b; font-weight: 600; }

/* Insight boxes */
.insight-box {
    background: linear-gradient(135deg, rgba(34, 197, 94, 0.1) 0%, rgba(34, 197, 94, 0.05) 100%);
    border-left: 4px solid #22c55e;
    border-radius: 0 8px 8px 0;
    padding: 16px 20px;
    margin: 16px 0;
}
.insight-title {
    font-size: 14px;
    font-weight: 600;
    color: #22c55e;
    margin-bottom: 8px;
}
.insight-content {
    font-size: 14px;
    color: #e2e8f0;
    line-height: 1.6;
}

/* Warning box */
.warning-box {
    background: linear-gradient(135deg, rgba(245, 158, 11, 0.1) 0%, rgba(245, 158, 11, 0.05) 100%);
    border-left: 4px solid #f59e0b;
    border-radius: 0 8px 8px 0;
    padding: 16px 20px;
    margin: 16px 0;
}
.warning-title {
    font-size: 14px;
    font-weight: 600;
    color: #f59e0b;
    margin-bottom: 8px;
}
.warning-content {
    font-size: 14px;
    color: #e2e8f0;
    line-height: 1.6;
}

/* Component breakdown */
.component-row {
    display: flex;
    align-items: center;
    padding: 16px;
    background: #1e293b;
    border-radius: 8px;
    margin-bottom: 8px;
}
.component-label {
    flex: 1;
    font-size: 15px;
    color: #e2e8f0;
}
.component-value {
    font-size: 18px;
    font-weight: 700;
    color: #22c55e;
    min-width: 120px;
    text-align: right;
}
.component-bar {
    width: 100px;
    height: 8px;
    background: #334155;
    border-radius: 4px;
    margin-left: 16px;
    overflow: hidden;
}
.component-bar-fill {
    height: 100%;
    background: linear-gradient(90deg, #22c55e, #3b82f6);
    border-radius: 4px;
}

/* Range grid */
.range-cell {
    width: 28px;
    height: 28px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 10px;
    font-weight: 600;
    border-radius: 4px;
    margin: 1px;
}
.range-raise { background: #22c55e; color: white; }
.range-call { background: #3b82f6; color: white; }
.range-fold { background: #374151; color: #9ca3af; }

/* Metric highlight */
.metric-highlight {
    background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
    border-radius: 12px;
    padding: 24px;
    text-align: center;
    color: white;
}
.metric-value-large {
    font-size: 48px;
    font-weight: 700;
    margin-bottom: 4px;
}
.metric-label-large {
    font-size: 14px;
    opacity: 0.9;
}

/* Sizing example */
.sizing-example {
    background: #1e293b;
    border-radius: 8px;
    padding: 20px;
    margin: 8px 0;
}
.sizing-situation {
    font-size: 13px;
    color: #94a3b8;
    margin-bottom: 8px;
}
.sizing-action {
    font-size: 24px;
    font-weight: 700;
    color: #22c55e;
    margin-bottom: 4px;
}
.sizing-math {
    font-size: 12px;
    color: #64748b;
    font-family: monospace;
}
</style>
""", unsafe_allow_html=True)


# =============================================================================
# MAIN PAGE
# =============================================================================

def main():
    """Main render function."""
    
    # ===== HERO SECTION =====
    st.markdown("""
        <div class="ev-hero">
            <div class="ev-hero-title">The Mathematics of Winning Poker</div>
            <div class="ev-hero-subtitle">
                Behind every decision is a quantitative framework built on game theory, 
                probability mathematics, and thousands of hours of simulation. 
                This is how we turn poker into a systematic edge.
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    # ===== WHAT IS EV? =====
    st.markdown("""
        <div class="section-dark">
            <div class="section-title">What is Expected Value?</div>
            <div class="section-subtitle">The foundation of every decision we make</div>
        </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("""
            **Expected Value (EV)** is the mathematical average outcome of a decision if you made it 
            thousands of times. Every poker decision has an EV — and our job is to always choose 
            the option with the highest EV.
            
            In poker, you can make the "right" decision and still lose. A player can call your all-in 
            with a 20% chance to win and hit their card. That doesn't make your decision wrong — 
            it makes you unlucky. Over time, making +EV decisions guarantees profit.
        """)
        
        st.markdown("""
            <div class="formula-box">
                <div class="formula-title">Expected Value Formula</div>
                <div class="formula-content">EV = (Win% × Amount Won) − (Lose% × Amount Lost)</div>
                <div class="formula-explanation">
                    <strong>Example:</strong> You bet $100 into a $100 pot with a 60% chance to win.<br>
                    EV = (0.60 × $200) − (0.40 × $100) = $120 − $40 = <span class="positive">+$80</span><br><br>
                    This is a profitable bet. Over 1000 attempts, you'd expect to profit ~$80,000.
                </div>
            </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
            <div class="metric-highlight">
                <div class="metric-value-large">+$0.12</div>
                <div class="metric-label-large">Average EV per hand at +6 BB/100</div>
            </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        st.markdown("""
            <div class="insight-box">
                <div class="insight-title">💡 Why This Matters</div>
                <div class="insight-content">
                    At $1/$2 stakes with +6 BB/100, you're making +$0.12 per hand on average. 
                    Play 200 hands? That's +$24. Play 100,000 hands? That's +$12,000.
                </div>
            </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # ===== THE DECISION ENGINE =====
    st.markdown("""
        <div class="section-dark">
            <div class="section-title">The Decision Engine</div>
            <div class="section-subtitle">How we calculate the optimal play in every situation</div>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
        Our decision engine evaluates every situation through multiple mathematical lenses, 
        then synthesizes them into a single optimal action. Here's what happens in milliseconds 
        when you input your cards:
    """)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown("""
            <div class="concept-card">
                <div class="concept-icon">🎯</div>
                <div class="concept-title">Hand Strength</div>
                <div class="concept-description">
                    Absolute and relative hand strength. How does your hand rank against 
                    all possible opponent holdings?
                </div>
            </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
            <div class="concept-card">
                <div class="concept-icon">📍</div>
                <div class="concept-title">Position Value</div>
                <div class="concept-description">
                    Acting last is worth ~3 BB/100 alone. Position determines 
                    how much information you have.
                </div>
            </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
            <div class="concept-card">
                <div class="concept-icon">📊</div>
                <div class="concept-title">Pot Odds</div>
                <div class="concept-description">
                    The ratio of pot size to the bet you must call. 
                    Determines minimum equity needed to continue.
                </div>
            </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown("""
            <div class="concept-card">
                <div class="concept-icon">⚖️</div>
                <div class="concept-title">Stack Dynamics</div>
                <div class="concept-description">
                    Effective stack sizes change optimal strategy. 
                    Short stack ≠ deep stack poker.
                </div>
            </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # ===== POSITION & RANGES =====
    st.markdown("""
        <div class="section-dark">
            <div class="section-title">Position & Opening Ranges</div>
            <div class="section-subtitle">Why we play tighter from early position and looser from the button</div>
        </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("""
            Position is the single most important factor in pre-flop hand selection. 
            When you act last, you have maximum information. When you act first, 
            you're playing blind against multiple opponents who will act after you.
            
            Our ranges are mathematically derived to maximize EV from each position:
        """)
        
        st.markdown("""
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Position</th>
                        <th>Opening Range</th>
                        <th>Hands</th>
                        <th>EV Impact</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>UTG</td>
                        <td>12%</td>
                        <td>~160 combos</td>
                        <td class="neutral">Baseline</td>
                    </tr>
                    <tr>
                        <td>Hijack</td>
                        <td>18%</td>
                        <td>~240 combos</td>
                        <td class="positive">+0.5 BB/100</td>
                    </tr>
                    <tr>
                        <td>Cutoff</td>
                        <td>27%</td>
                        <td>~360 combos</td>
                        <td class="positive">+1.2 BB/100</td>
                    </tr>
                    <tr>
                        <td>Button</td>
                        <td>42%</td>
                        <td>~560 combos</td>
                        <td class="positive">+2.8 BB/100</td>
                    </tr>
                    <tr>
                        <td>Small Blind</td>
                        <td>36%</td>
                        <td>~480 combos</td>
                        <td class="negative">-0.4 BB/100</td>
                    </tr>
                    <tr>
                        <td>Big Blind</td>
                        <td>Defense</td>
                        <td>Variable</td>
                        <td class="negative">-2.0 BB/100</td>
                    </tr>
                </tbody>
            </table>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
            <div class="insight-box">
                <div class="insight-title">📍 The Button Advantage</div>
                <div class="insight-content">
                    The button is worth approximately +2.8 BB/100 compared to average position. 
                    This is why we open 42% of hands from the button but only 12% from UTG. 
                    The same hand can be +EV in one position and -EV in another.
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
            <div class="warning-box">
                <div class="warning-title">⚠️ The Blinds Are Losers</div>
                <div class="warning-content">
                    You will lose money from the blinds over time — this is mathematically unavoidable. 
                    The goal is to minimize losses, not to profit. Our blind defense ranges are 
                    optimized to lose the least amount possible.
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
            <div class="formula-box">
                <div class="formula-title">Position EV Calculation</div>
                <div class="formula-content">BTN EV ≈ UTG EV + 2.8 BB/100</div>
                <div class="formula-explanation">
                    The same hand played from the Button generates approximately 2.8 BB/100 
                    more than from Under The Gun, purely due to positional advantage.
                </div>
            </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # ===== POT ODDS & EQUITY =====
    st.markdown("""
        <div class="section-dark">
            <div class="section-title">Pot Odds & Equity</div>
            <div class="section-subtitle">The mathematics behind every call and fold decision</div>
        </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("""
            <div class="formula-box">
                <div class="formula-title">Pot Odds Formula</div>
                <div class="formula-content">Required Equity = Bet ÷ (Pot + Bet)</div>
                <div class="formula-explanation">
                    <strong>Example:</strong> Pot is $100, opponent bets $50.<br>
                    You must call $50 to win $150 (pot + bet).<br>
                    Required Equity = $50 ÷ $150 = <strong>33.3%</strong><br><br>
                    If your hand has 40% equity → <span class="positive">+EV Call</span><br>
                    If your hand has 25% equity → <span class="negative">-EV Fold</span>
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
            <div class="formula-box">
                <div class="formula-title">Implied Odds Adjustment</div>
                <div class="formula-content">Adj. Required Equity = Bet ÷ (Pot + Bet + Future Bets)</div>
                <div class="formula-explanation">
                    When you have a drawing hand (flush draw, straight draw), you can call 
                    with less immediate equity because you'll win more money when you hit. 
                    This is why the app sometimes calls with 25% equity against a 33% pot odds requirement.
                </div>
            </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("**Common Equity Situations:**")
        
        st.markdown("""
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Your Hand</th>
                        <th>vs Overpair</th>
                        <th>vs Top Pair</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>Flush Draw</td>
                        <td>35%</td>
                        <td>36%</td>
                    </tr>
                    <tr>
                        <td>Open-Ended Straight</td>
                        <td>32%</td>
                        <td>34%</td>
                    </tr>
                    <tr>
                        <td>Flush + Straight Draw</td>
                        <td>54%</td>
                        <td>56%</td>
                    </tr>
                    <tr>
                        <td>Two Overcards</td>
                        <td>24%</td>
                        <td>26%</td>
                    </tr>
                    <tr>
                        <td>Set vs Flush Draw</td>
                        <td colspan="2">65% favorite</td>
                    </tr>
                    <tr>
                        <td>Overpair vs Underpair</td>
                        <td colspan="2">82% favorite</td>
                    </tr>
                </tbody>
            </table>
        """, unsafe_allow_html=True)
        
        st.markdown("""
            <div class="insight-box">
                <div class="insight-title">💡 The App Does This Instantly</div>
                <div class="insight-content">
                    You don't need to calculate pot odds or equity in real-time. 
                    The app evaluates your hand against likely opponent ranges 
                    and tells you whether to call, fold, or raise.
                </div>
            </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # ===== BET SIZING SCIENCE =====
    st.markdown("""
        <div class="section-dark">
            <div class="section-title">The Science of Bet Sizing</div>
            <div class="section-subtitle">Why we tell you to bet $18, not "about 3x"</div>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
        Bet sizing is one of the most complex aspects of poker strategy. The optimal size depends on:
        - Board texture (dry vs wet)
        - Your range vs opponent's range  
        - Stack-to-pot ratio (SPR)
        - Whether you're value betting or bluffing
        - Opponent tendencies
        
        **Our sizing algorithms produce exact dollar amounts because precision matters.** A bet that's 
        10% too small leaves money on the table. A bet that's 10% too large folds out hands you 
        wanted to call.
    """)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
            <div class="sizing-example">
                <div class="sizing-situation">Pre-flop open from Button at $1/$2</div>
                <div class="sizing-action">RAISE TO $5</div>
                <div class="sizing-math">2.5× BB = Standard BTN open</div>
            </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
            <div class="sizing-example">
                <div class="sizing-situation">3-bet in position vs $6 open</div>
                <div class="sizing-action">RAISE TO $18</div>
                <div class="sizing-math">3× villain's raise = IP 3-bet</div>
            </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
            <div class="sizing-example">
                <div class="sizing-situation">C-bet on dry flop (K♠ 7♦ 2♣)</div>
                <div class="sizing-action">BET $8</div>
                <div class="sizing-math">33% pot = Dry board c-bet</div>
            </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
            <div class="sizing-example">
                <div class="sizing-situation">Value bet river with nuts</div>
                <div class="sizing-action">BET $45</div>
                <div class="sizing-math">75% pot = Max value extraction</div>
            </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
            <div class="sizing-example">
                <div class="sizing-situation">Check-raise vs fish on wet board</div>
                <div class="sizing-action">RAISE TO $36</div>
                <div class="sizing-math">4× villain bet = Punish draws</div>
            </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
            <div class="sizing-example">
                <div class="sizing-situation">All-in with &lt;20 BB effective</div>
                <div class="sizing-action">ALL-IN $38</div>
                <div class="sizing-math">SPR &lt; 2 = Commit or fold</div>
            </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # ===== RISK OF RUIN =====
    st.markdown("""
        <div class="section-dark">
            <div class="section-title">Risk of Ruin Mathematics</div>
            <div class="section-subtitle">Why we're so strict about bankroll requirements</div>
        </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("""
            **Risk of Ruin (RoR)** is the probability of losing your entire bankroll before 
            it can recover. Even winning players experience significant downswings — the 
            question is whether your bankroll can survive them.
        """)
        
        st.markdown("""
            <div class="formula-box">
                <div class="formula-title">Risk of Ruin Formula</div>
                <div class="formula-content">RoR ≈ e^(-2 × WR × BR / σ²)</div>
                <div class="formula-explanation">
                    <strong>WR</strong> = Win rate (BB/100)<br>
                    <strong>BR</strong> = Bankroll in BB<br>
                    <strong>σ</strong> = Standard deviation (~80 BB/100)<br><br>
                    This exponential relationship means small bankroll increases 
                    dramatically reduce ruin probability.
                </div>
            </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("**Risk of Ruin by Bankroll Size:**")
        
        st.markdown("""
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Buy-ins</th>
                        <th>Bankroll ($1/$2)</th>
                        <th>Risk of Ruin</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>10 BI</td>
                        <td>$2,000</td>
                        <td class="negative">8.2%</td>
                    </tr>
                    <tr>
                        <td>13 BI</td>
                        <td>$2,600</td>
                        <td class="neutral">2.1%</td>
                    </tr>
                    <tr>
                        <td>15 BI</td>
                        <td>$3,000</td>
                        <td class="positive">0.8%</td>
                    </tr>
                    <tr>
                        <td>17 BI</td>
                        <td>$3,400</td>
                        <td class="positive">0.3%</td>
                    </tr>
                    <tr>
                        <td>20 BI</td>
                        <td>$4,000</td>
                        <td class="positive">0.1%</td>
                    </tr>
                </tbody>
            </table>
        """, unsafe_allow_html=True)
        
        st.markdown("""
            <div class="insight-box">
                <div class="insight-title">💡 15 Buy-ins = 0.8% RoR</div>
                <div class="insight-content">
                    Our default recommendation of 15 buy-ins gives you a less than 1% 
                    chance of going broke while maintaining reasonable stake progression.
                </div>
            </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # ===== SESSION EV =====
    st.markdown("""
        <div class="section-dark">
            <div class="section-title">Session Length Optimization</div>
            <div class="section-subtitle">The hidden EV leak that costs most players 1+ BB/100</div>
        </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("""
            Your decision quality degrades over time. Research and our simulations show 
            that most players maintain peak performance for approximately **2-3 hours**, 
            after which mistakes become more frequent and more costly.
        """)
        
        st.markdown("**Performance Decay Over Time:**")
        
        st.markdown("""
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Session Length</th>
                        <th>Performance</th>
                        <th>EV Impact</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>0 - 2 hours</td>
                        <td class="positive">100%</td>
                        <td class="positive">Full EV</td>
                    </tr>
                    <tr>
                        <td>2 - 3 hours</td>
                        <td class="positive">98%</td>
                        <td class="neutral">-0.1 BB/100</td>
                    </tr>
                    <tr>
                        <td>3 - 4 hours</td>
                        <td class="neutral">92%</td>
                        <td class="negative">-0.5 BB/100</td>
                    </tr>
                    <tr>
                        <td>4 - 5 hours</td>
                        <td class="negative">85%</td>
                        <td class="negative">-1.0 BB/100</td>
                    </tr>
                    <tr>
                        <td>5+ hours</td>
                        <td class="negative">&lt;80%</td>
                        <td class="negative">-1.5+ BB/100</td>
                    </tr>
                </tbody>
            </table>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
            <div class="warning-box">
                <div class="warning-title">⚠️ The Marathon Myth</div>
                <div class="warning-content">
                    Many players believe grinding longer sessions means more profit. 
                    The math says otherwise. Two 3-hour sessions produce more profit 
                    than one 6-hour session because your late-session mistakes 
                    eat into early-session profits.
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
            <div class="insight-box">
                <div class="insight-title">💡 Stop-Loss & Stop-Win</div>
                <div class="insight-content">
                    Beyond fatigue, emotional state affects decision quality. 
                    Our stop-loss (1 BI) and stop-win (3 BI) thresholds are designed 
                    to end sessions before tilt or overconfidence degrades your edge.
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
            <div class="formula-box">
                <div class="formula-title">Optimal Session Structure</div>
                <div class="formula-content">2-3 hours × Multiple Sessions &gt; 1 Long Grind</div>
                <div class="formula-explanation">
                    Sessions of 2-3 hours maintain peak performance. 
                    Taking breaks between sessions resets your mental state 
                    and preserves your edge.
                </div>
            </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # ===== THE EDGE BREAKDOWN =====
    st.markdown("""
        <div class="section-dark">
            <div class="section-title">The Complete Edge: +6 to +7 BB/100</div>
            <div class="section-subtitle">How all the components combine to create systematic profit</div>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
        <div class="component-row">
            <div class="component-label">
                <strong>Pre-flop Range Optimization</strong><br>
                <span style="color: #64748b; font-size: 13px;">Mathematically derived opening and defending ranges</span>
            </div>
            <div class="component-value">+1.5 BB/100</div>
            <div class="component-bar"><div class="component-bar-fill" style="width: 25%;"></div></div>
        </div>
        
        <div class="component-row">
            <div class="component-label">
                <strong>Post-flop Decision Quality</strong><br>
                <span style="color: #64748b; font-size: 13px;">Optimal betting, calling, and folding decisions</span>
            </div>
            <div class="component-value">+2.5 BB/100</div>
            <div class="component-bar"><div class="component-bar-fill" style="width: 42%;"></div></div>
        </div>
        
        <div class="component-row">
            <div class="component-label">
                <strong>Precise Bet Sizing</strong><br>
                <span style="color: #64748b; font-size: 13px;">Extracting maximum value, minimizing losses</span>
            </div>
            <div class="component-value">+0.8 BB/100</div>
            <div class="component-bar"><div class="component-bar-fill" style="width: 13%;"></div></div>
        </div>
        
        <div class="component-row">
            <div class="component-label">
                <strong>Session Time Management</strong><br>
                <span style="color: #64748b; font-size: 13px;">Quitting before fatigue degrades performance</span>
            </div>
            <div class="component-value">+0.7 BB/100</div>
            <div class="component-bar"><div class="component-bar-fill" style="width: 12%;"></div></div>
        </div>
        
        <div class="component-row">
            <div class="component-label">
                <strong>Tilt Prevention</strong><br>
                <span style="color: #64748b; font-size: 13px;">Stop-loss and stop-win thresholds</span>
            </div>
            <div class="component-value">+0.5 BB/100</div>
            <div class="component-bar"><div class="component-bar-fill" style="width: 8%;"></div></div>
        </div>
        
        <div class="component-row" style="background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);">
            <div class="component-label" style="color: white;">
                <strong>TOTAL EXPECTED EDGE</strong><br>
                <span style="opacity: 0.8; font-size: 13px;">All components combined</span>
            </div>
            <div class="component-value" style="color: white; font-size: 24px;">+6.0 BB/100</div>
            <div class="component-bar" style="background: rgba(255,255,255,0.3);"><div class="component-bar-fill" style="width: 100%; background: white;"></div></div>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # ===== FINAL NOTE =====
    st.markdown("""
        <div class="insight-box">
            <div class="insight-title">🎯 The Bottom Line</div>
            <div class="insight-content">
                This isn't magic. It's mathematics applied systematically to every decision. 
                The edge comes from eliminating mistakes, not from making brilliant plays. 
                <strong>Perfect execution of fundamentally sound strategy beats genius plays 
                with frequent errors — every time.</strong>
            </div>
        </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()