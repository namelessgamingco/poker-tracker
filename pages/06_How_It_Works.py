# =============================================================================
# 06_How_It_Works.py — How It Works Guide
# =============================================================================
#
# PURPOSE:
# - Build confidence in the system
# - Teach users how to use the app effectively  
# - Set realistic expectations
# - Reinforce the $299/month value proposition
#
# SECTIONS:
# 1. The Promise - What this app does
# 2. The Three Pillars - Decision Engine, Bankroll, Sessions
# 3. How To Use It - Step-by-step during play
# 4. The Math Behind It - Why it works
# 5. Your Commitment - What's required from the user
# 6. Quick Start Checklist - Get started now
# 7. FAQ - Common questions
#
# =============================================================================

import streamlit as st

st.set_page_config(
    page_title="How It Works | Poker Decision App",
    page_icon="📖",
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
.hero-section {
    background: linear-gradient(135deg, #1f2937 0%, #374151 100%);
    border-radius: 16px;
    padding: 48px;
    text-align: center;
    color: white;
    margin-bottom: 32px;
}
.hero-title {
    font-size: 36px;
    font-weight: 700;
    margin-bottom: 16px;
}
.hero-subtitle {
    font-size: 20px;
    opacity: 0.9;
    max-width: 600px;
    margin: 0 auto;
    line-height: 1.6;
}

/* Pillar cards */
.pillar-card {
    background: white;
    border: 2px solid #e5e7eb;
    border-radius: 16px;
    padding: 32px;
    text-align: center;
    height: 100%;
    transition: all 0.3s ease;
}
.pillar-card:hover {
    border-color: #3b82f6;
    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.15);
}
.pillar-icon {
    font-size: 48px;
    margin-bottom: 16px;
}
.pillar-title {
    font-size: 20px;
    font-weight: 600;
    color: #111827;
    margin-bottom: 12px;
}
.pillar-description {
    font-size: 15px;
    color: #6b7280;
    line-height: 1.6;
}

/* Step cards */
.step-container {
    display: flex;
    align-items: flex-start;
    gap: 24px;
    padding: 24px;
    background: #f8fafc;
    border-radius: 12px;
    margin-bottom: 16px;
}
.step-number {
    background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
    color: white;
    width: 48px;
    height: 48px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 20px;
    font-weight: 700;
    flex-shrink: 0;
}
.step-content {
    flex: 1;
}
.step-title {
    font-size: 18px;
    font-weight: 600;
    color: #111827;
    margin-bottom: 8px;
}
.step-description {
    font-size: 15px;
    color: #6b7280;
    line-height: 1.6;
}

/* Math box */
.math-box {
    background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
    border: 2px solid #22c55e;
    border-radius: 12px;
    padding: 24px;
    margin: 16px 0;
}
.math-title {
    font-size: 18px;
    font-weight: 600;
    color: #166534;
    margin-bottom: 12px;
}
.math-content {
    font-size: 15px;
    color: #166534;
    line-height: 1.8;
}
.math-highlight {
    background: #22c55e;
    color: white;
    padding: 2px 8px;
    border-radius: 4px;
    font-weight: 600;
}

/* Commitment box */
.commitment-box {
    background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
    border: 2px solid #f59e0b;
    border-radius: 12px;
    padding: 24px;
    margin: 16px 0;
}
.commitment-title {
    font-size: 18px;
    font-weight: 600;
    color: #92400e;
    margin-bottom: 12px;
}
.commitment-content {
    font-size: 15px;
    color: #92400e;
    line-height: 1.8;
}

/* Checklist */
.checklist-item {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 16px;
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    margin-bottom: 8px;
}
.checklist-icon {
    font-size: 20px;
    flex-shrink: 0;
}
.checklist-text {
    font-size: 15px;
    color: #374151;
    line-height: 1.5;
}

/* FAQ */
.faq-question {
    font-size: 16px;
    font-weight: 600;
    color: #111827;
    margin-bottom: 8px;
}
.faq-answer {
    font-size: 15px;
    color: #6b7280;
    line-height: 1.6;
    padding-left: 16px;
    border-left: 3px solid #e5e7eb;
}

/* Section headers */
.section-header {
    font-size: 24px;
    font-weight: 700;
    color: #111827;
    margin-bottom: 8px;
}
.section-subheader {
    font-size: 16px;
    color: #6b7280;
    margin-bottom: 24px;
}

/* Result showcase */
.result-card {
    background: linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%);
    border-radius: 12px;
    padding: 24px;
    text-align: center;
    color: white;
}
.result-value {
    font-size: 36px;
    font-weight: 700;
    margin-bottom: 4px;
}
.result-label {
    font-size: 14px;
    opacity: 0.9;
}

/* Example decision */
.decision-example {
    background: #111827;
    border-radius: 12px;
    padding: 32px;
    text-align: center;
    color: white;
    margin: 24px 0;
}
.decision-action {
    font-size: 48px;
    font-weight: 700;
    color: #22c55e;
    margin-bottom: 8px;
}
.decision-context {
    font-size: 14px;
    opacity: 0.7;
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
        <div class="hero-section">
            <div class="hero-title">One Answer. Every Hand. No Thinking.</div>
            <div class="hero-subtitle">
                This app tells you exactly what to do in every poker situation. 
                Not suggestions. Not ranges. One clear action with the exact dollar amount.
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    # ===== THE THREE PILLARS =====
    st.markdown('<div class="section-header">The Three Pillars</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-subheader">Everything you need to win consistently</div>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
            <div class="pillar-card">
                <div class="pillar-icon">🎯</div>
                <div class="pillar-title">Decision Engine</div>
                <div class="pillar-description">
                    Tells you exactly what to do every hand. 
                    Pre-flop through river. Mathematically optimal 
                    decisions that maximize your expected value.
                </div>
            </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
            <div class="pillar-card">
                <div class="pillar-icon">💰</div>
                <div class="pillar-title">Bankroll Management</div>
                <div class="pillar-description">
                    Protects you from going broke. Tells you exactly 
                    what stakes to play, when to move up, and when 
                    to move down. Never risk too much.
                </div>
            </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
            <div class="pillar-card">
                <div class="pillar-icon">⏱️</div>
                <div class="pillar-title">Session Management</div>
                <div class="pillar-description">
                    Stops you before you make tired mistakes. 
                    Automatic stop-loss and stop-win thresholds. 
                    Quit at the right time, every time.
                </div>
            </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # ===== HOW TO USE IT =====
    st.markdown('<div class="section-header">How To Use It</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-subheader">During your poker session</div>', unsafe_allow_html=True)
    
    st.markdown("""
        <div class="step-container">
            <div class="step-number">1</div>
            <div class="step-content">
                <div class="step-title">Enter Your Cards & Situation</div>
                <div class="step-description">
                    Tap your hole cards, select your position, and tell the app what action you're facing. 
                    Takes about 3 seconds. The app remembers your cards throughout the hand.
                </div>
            </div>
        </div>
        
        <div class="step-container">
            <div class="step-number">2</div>
            <div class="step-content">
                <div class="step-title">Get Your Decision</div>
                <div class="step-description">
                    The app instantly shows you exactly what to do: <strong>RAISE TO $12</strong>, 
                    <strong>CALL</strong>, or <strong>FOLD</strong>. No thinking required. 
                    Just follow the instruction.
                </div>
            </div>
        </div>
        
        <div class="step-container">
            <div class="step-number">3</div>
            <div class="step-content">
                <div class="step-title">Execute & Record</div>
                <div class="step-description">
                    Make the play the app recommends. After the hand, tap whether you won, lost, or folded. 
                    The app tracks your results automatically.
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    # Example decision
    st.markdown("""
        <div class="decision-example">
            <div class="decision-context">You have A♠ K♥ on the Button facing a $6 raise</div>
            <div class="decision-action">RAISE TO $18</div>
            <div class="decision-context">3-bet for value with premium hand in position</div>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # ===== THE MATH BEHIND IT =====
    st.markdown('<div class="section-header">The Math Behind It</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-subheader">Why this system produces consistent profits</div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("""
            <div class="math-box">
                <div class="math-title">📊 Expected Win Rate: +6 to +7 BB/100</div>
                <div class="math-content">
                    <strong>Where does this come from?</strong><br><br>
                    
                    • <strong>Decision Engine:</strong> +4 to +5 BB/100<br>
                    &nbsp;&nbsp;&nbsp;Mathematically optimal plays in every situation<br><br>
                    
                    • <strong>Session Management:</strong> +1 to +1.5 BB/100<br>
                    &nbsp;&nbsp;&nbsp;Avoiding tired mistakes and tilt<br><br>
                    
                    • <strong>Bankroll Protection:</strong> +0.5 to +1 BB/100<br>
                    &nbsp;&nbsp;&nbsp;Playing the right stakes, never going broke<br><br>
                    
                    <span class="math-highlight">Total: +6 to +7 BB/100</span>
                </div>
            </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
            <div class="result-card">
                <div class="result-value">$21,000</div>
                <div class="result-label">Annual profit at $1/$2</div>
            </div>
            <br>
            <div class="result-card">
                <div class="result-value">$52,500</div>
                <div class="result-label">Annual profit at $2/$5</div>
            </div>
        """, unsafe_allow_html=True)
    
    st.markdown("""
        <div class="math-box" style="background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%); border-color: #3b82f6;">
            <div class="math-title" style="color: #1e40af;">📈 The Assumptions</div>
            <div class="math-content" style="color: #1e40af;">
                • 500 sessions per year (about 10 per week)<br>
                • 200 hands per session average<br>
                • 2-3 hours per session<br>
                • <strong>100% compliance with app recommendations</strong>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # ===== YOUR COMMITMENT =====
    st.markdown('<div class="section-header">Your Commitment</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-subheader">What\'s required from you to succeed</div>', unsafe_allow_html=True)
    
    st.markdown("""
        <div class="commitment-box">
            <div class="commitment-title">⚠️ This Only Works If You Follow It Exactly</div>
            <div class="commitment-content">
                The math only works if you execute every decision the app gives you. 
                <strong>No exceptions.</strong> No "I have a feeling." No "But this time is different."
                <br><br>
                Every time you override the app, you're introducing negative expected value.
                The edge comes from perfect execution of mathematically optimal strategy.
                <br><br>
                <strong>Your job is simple: Input the situation. Execute the decision. Repeat.</strong>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### ✅ Do This")
        st.markdown("""
            <div class="checklist-item">
                <div class="checklist-icon">✓</div>
                <div class="checklist-text">Follow every decision the app gives you</div>
            </div>
            <div class="checklist-item">
                <div class="checklist-icon">✓</div>
                <div class="checklist-text">End sessions when the app tells you to</div>
            </div>
            <div class="checklist-item">
                <div class="checklist-icon">✓</div>
                <div class="checklist-text">Play the stakes your bankroll supports</div>
            </div>
            <div class="checklist-item">
                <div class="checklist-icon">✓</div>
                <div class="checklist-text">Track every session accurately</div>
            </div>
            <div class="checklist-item">
                <div class="checklist-icon">✓</div>
                <div class="checklist-text">Trust the process during downswings</div>
            </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("#### ❌ Don't Do This")
        st.markdown("""
            <div class="checklist-item">
                <div class="checklist-icon">✗</div>
                <div class="checklist-text">Override decisions based on "gut feeling"</div>
            </div>
            <div class="checklist-item">
                <div class="checklist-icon">✗</div>
                <div class="checklist-text">Keep playing after hitting stop-loss</div>
            </div>
            <div class="checklist-item">
                <div class="checklist-icon">✗</div>
                <div class="checklist-text">Move up in stakes before you're ready</div>
            </div>
            <div class="checklist-item">
                <div class="checklist-icon">✗</div>
                <div class="checklist-text">Skip tracking when you lose</div>
            </div>
            <div class="checklist-item">
                <div class="checklist-icon">✗</div>
                <div class="checklist-text">Panic and quit during normal variance</div>
            </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # ===== QUICK START CHECKLIST =====
    st.markdown('<div class="section-header">Quick Start Checklist</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-subheader">Get set up in 5 minutes</div>', unsafe_allow_html=True)
    
    st.markdown("""
        <div class="checklist-item">
            <div class="checklist-icon">1️⃣</div>
            <div class="checklist-text">
                <strong>Set your bankroll</strong> — Go to Settings and enter your total poker bankroll
            </div>
        </div>
        <div class="checklist-item">
            <div class="checklist-icon">2️⃣</div>
            <div class="checklist-text">
                <strong>Choose your risk mode</strong> — Balanced is recommended for most players
            </div>
        </div>
        <div class="checklist-item">
            <div class="checklist-icon">3️⃣</div>
            <div class="checklist-text">
                <strong>Check Bankroll Health</strong> — Confirm you're playing the right stakes
            </div>
        </div>
        <div class="checklist-item">
            <div class="checklist-icon">4️⃣</div>
            <div class="checklist-text">
                <strong>Start a session</strong> — Go to Play Session when you sit down at a table
            </div>
        </div>
        <div class="checklist-item">
            <div class="checklist-icon">5️⃣</div>
            <div class="checklist-text">
                <strong>Follow every decision</strong> — Input your cards, get your action, execute
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # ===== FAQ =====
    st.markdown('<div class="section-header">Frequently Asked Questions</div>', unsafe_allow_html=True)
    
    with st.expander("How fast can I input my cards and get a decision?"):
        st.markdown("""
            About **3-5 seconds** for most situations. The app is designed for speed — you'll have your 
            answer well before your turn timer runs out. With practice, many users get it down to 2 seconds.
        """)
    
    with st.expander("What if the app tells me to fold a hand I want to play?"):
        st.markdown("""
            **Fold it.** The app isn't trying to make poker fun — it's trying to make you money. 
            That "fun" hand you want to play is likely costing you money in the long run. 
            Trust the math and fold when the app says fold.
        """)
    
    with st.expander("How long until I see results?"):
        st.markdown("""
            Poker has variance. You might run bad for weeks even while playing perfectly. 
            Most users see their true win rate emerge after **50-100 sessions** (about 10,000-20,000 hands). 
            Trust the process and keep executing.
        """)
    
    with st.expander("What stakes should I play?"):
        st.markdown("""
            The app tells you based on your bankroll. Check the **Bankroll Health** page — it shows 
            exactly what stakes you can safely play and when you can move up. Never play stakes 
            your bankroll doesn't support.
        """)
    
    with st.expander("Does this work for tournaments?"):
        st.markdown("""
            **No.** This app is designed specifically for **6-max No-Limit Hold'em cash games**. 
            Tournament poker has different considerations (ICM, stack sizes, blind levels) that 
            this app doesn't account for.
        """)
    
    with st.expander("What if I'm playing live instead of online?"):
        st.markdown("""
            The strategy is the same. You'll have more time to input your cards in live games. 
            The only difference is you'll need to estimate pot sizes and bet amounts rather than 
            seeing exact numbers on screen.
        """)
    
    with st.expander("Is this considered cheating?"):
        st.markdown("""
            **Check your poker site's terms of service.** Most sites allow decision-assistance tools 
            that don't directly read or interact with the poker software. This app requires manual 
            input — you type in your cards, it doesn't read them from your screen. However, policies 
            vary by site, so verify before using.
        """)
    
    with st.expander("Why is the subscription $299/month?"):
        st.markdown("""
            Because it works. At $1/$2 stakes, the expected annual profit is ~$21,000. 
            The subscription costs $3,588/year — a **500% return on investment**. 
            If you play $2/$5, the ROI is even higher. This isn't an expense, it's an investment 
            in your poker income.
        """)


if __name__ == "__main__":
    main()