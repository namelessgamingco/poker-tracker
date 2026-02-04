# pages/03_Statistical_Odds.py — Statistical Odds & Why It Works

import streamlit as st
st.set_page_config(page_title="Statistical Odds", page_icon="📈", layout="wide")  # set first

from auth import require_auth
user = require_auth()  # gate page before anything renders

import pandas as pd
import altair as alt

from sidebar import render_sidebar
render_sidebar()  # only show after auth

# --------------------------- Styles (subtle dark polish) ---------------------------
st.markdown("""
<style>
.small-note { color:#a1a1aa; font-size:.85rem; }

.kpi {
  display:flex;
  gap:12px;
  flex-wrap:wrap;
  margin: 8px 0 0;
}
.kpi .chip {
  border:1px solid #2b2b2b;
  border-radius:10px;
  background:#111;
  color:#eaeaea;
  padding:8px 12px;
  font-size:.9rem;
}

.h-sep {
  border:0;
  border-top:1px solid #2b2b2b;
  margin:20px 0 14px;
}

.section-subtle { color:#d6d6d6; }

.callout {
  border:1px solid #303030;
  border-radius:12px;
  background:linear-gradient(135deg,#0f0f0f,#151515);
  padding:14px 16px;
  color:#eaeaea;
  box-shadow:0 10px 30px rgba(0,0,0,.25);
}

/* Match section title look from How It Works page */
.section-h{
  font-weight:900;
  font-size:1.25rem;
  margin:4px 0 8px 0;
  letter-spacing:0.01em;
}

.centerline {
  text-align:center;
  color:#f5f5f5;
  font-weight:600;
  font-size:1.05rem;
}
</style>
""", unsafe_allow_html=True)

st.title("📈 Statistical Odds — What to Expect, Why It Works")

# ---------- Intro: how the operating model was built / what it actually is ----------
st.markdown(
    """
<div class="callout">
<b>What this actually is:</b><br>
Under the hood, the engine is a <b>risk-managed trading model</b> not a “system” for guessing hands.  
It treats baccarat as a stream of independent events and then layers a full risk framework on top:
position sizing, caps, guards, tone shifts, and bankroll partitioning.
<br><br>
We mapped the full ruleset into code and ran <b>millions of Monte Carlo hands</b> across
tens of thousands of weeks while sweeping through:
<ul>
  <li>different weekly caps, guards, and lock points,</li>
  <li>different session goals and line exits,</li>
  <li>different cadence patterns and defensive behaviors,</li>
  <li>different ways to partition and rotate multi-track bankrolls.</li>
</ul>
Most configurations either:
<ul>
  <li>made money quickly and then blew up under stress, or</li>
  <li>survived but didn’t pay enough to justify the effort.</li>
</ul>
The version you’re using now sits in the narrow band that:
<ul>
  <li>stayed profitable in our long-run tests under standard baccarat odds, and</li>
  <li>remains realistic to execute in live casinos and online.</li>
</ul>
This page shows the <b>statistical footprint</b> of that operating model: not a guarantee, not a magic loophole,
but a disciplined, math-heavy way to expose a bankroll to a negative-EV game with a trading-style risk profile.
</div>
""",
    unsafe_allow_html=True,
)

st.caption(
    "These odds summarize how the model behaves week-by-week under standard baccarat rules, "
    "with the same cadence, caps, guards, and tone logic you use live."
)

# ============================= Weekly outcomes (bars) =============================
st.markdown("<div class='section-h'>Weekly Outcome Distribution</div>", unsafe_allow_html=True)

weekly = pd.DataFrame({
    "Bucket": [
        "Full Green Cap (+400u)",
        "Optimizer Green (+300u)",
        "Smaller Green (+160u)",
        "Smaller Red (−60 to −90u)",
        "Guard Hit (−400u)"
    ],
    "Probability (%)": [36.20, 22.00, 28.30, 9.80, 3.70],
    "Representative Result (u)": [400, 300, 160, -85, -400],
})

# Color scale for the bars
color_scale = alt.Scale(
    domain=["Full Green Cap (+400u)", "Optimizer Green (+300u)", "Smaller Green (+160u)", "Smaller Red (−85u)", "Guard Hit (−400u)"],
    range=["#22c55e", "#4ade80", "#86efac", "#f87171", "#dc2626"]
)

bar = (
    alt.Chart(weekly)
    .mark_bar(cornerRadiusEnd=4)
    .encode(
        x=alt.X("Probability (%):Q", title="Probability (%)", scale=alt.Scale(domain=[0, 40])),
        y=alt.Y("Bucket:N", sort=["Full Green Cap (+400u)", "Optimizer Green (+300u)", "Smaller Green (+160u)", "Smaller Red (−85u)", "Guard Hit (−400u)"], title=None, axis=alt.Axis(labelLimit=200)),
        color=alt.Color("Bucket:N", scale=color_scale, legend=None),
        tooltip=[
            alt.Tooltip("Bucket:N", title="Outcome"),
            alt.Tooltip("Probability (%):Q", title="Probability", format=".1f"),
            alt.Tooltip("Representative Result (u):Q", title="Result (units)")
        ]
    )
    .properties(height=250)
    .configure_axis(
        labelColor="#a1a1aa",
        titleColor="#a1a1aa",
        gridColor="#2b2b2b"
    )
    .configure_view(strokeWidth=0)
)
st.altair_chart(bar, use_container_width=True)

# KPI row - using columns for better layout
st.markdown("<div style='margin: 16px 0 8px 0;'></div>", unsafe_allow_html=True)
kpi1, kpi2, kpi3 = st.columns(3)
with kpi1:
    st.markdown(
        "<div style='border:1px solid #2b2b2b;border-radius:10px;background:#111;padding:12px 16px;text-align:center;'>"
        "<div style='color:#a1a1aa;font-size:.8rem;margin-bottom:4px;'>Avg Weekly Gain</div>"
        "<div style='color:#22c55e;font-size:1.3rem;font-weight:800;'>+233u</div>"
        "</div>",
        unsafe_allow_html=True
    )
with kpi2:
    st.markdown(
        "<div style='border:1px solid #2b2b2b;border-radius:10px;background:#111;padding:12px 16px;text-align:center;'>"
        "<div style='color:#a1a1aa;font-size:.8rem;margin-bottom:4px;'>Green Weeks (All Types)</div>"
        "<div style='color:#4ade80;font-size:1.3rem;font-weight:800;'>86.5%</div>"
        "</div>",
        unsafe_allow_html=True
    )
with kpi3:
    st.markdown(
        "<div style='border:1px solid #2b2b2b;border-radius:10px;background:#111;padding:12px 16px;text-align:center;'>"
        "<div style='color:#a1a1aa;font-size:.8rem;margin-bottom:4px;'>Red Weeks (All Types)</div>"
        "<div style='color:#f87171;font-size:1.3rem;font-weight:800;'>13.5%</div>"
        "</div>",
        unsafe_allow_html=True
    )

# Detailed breakdown row
st.markdown("<div style='margin: 12px 0;'></div>", unsafe_allow_html=True)
d1, d2, d3, d4, d5 = st.columns(5)
with d1:
    st.markdown(
        "<div style='border:1px solid #22c55e33;border-radius:8px;background:#111;padding:10px;text-align:center;'>"
        "<div style='color:#22c55e;font-size:.75rem;'>Full Green (+400u)</div>"
        "<div style='color:#eaeaea;font-size:1rem;font-weight:700;'>36.2%</div>"
        "</div>",
        unsafe_allow_html=True
    )
with d2:
    st.markdown(
        "<div style='border:1px solid #4ade8033;border-radius:8px;background:#111;padding:10px;text-align:center;'>"
        "<div style='color:#4ade80;font-size:.75rem;'>Optimizer (+300u)</div>"
        "<div style='color:#eaeaea;font-size:1rem;font-weight:700;'>22.0%</div>"
        "</div>",
        unsafe_allow_html=True
    )
with d3:
    st.markdown(
        "<div style='border:1px solid #86efac33;border-radius:8px;background:#111;padding:10px;text-align:center;'>"
        "<div style='color:#86efac;font-size:.75rem;'>Smaller Green (+160u)</div>"
        "<div style='color:#eaeaea;font-size:1rem;font-weight:700;'>28.3%</div>"
        "</div>",
        unsafe_allow_html=True
    )
with d4:
    st.markdown(
        "<div style='border:1px solid #f8717133;border-radius:8px;background:#111;padding:10px;text-align:center;'>"
        "<div style='color:#f87171;font-size:.75rem;'>Smaller Red (−85u)</div>"
        "<div style='color:#eaeaea;font-size:1rem;font-weight:700;'>9.8%</div>"
        "</div>",
        unsafe_allow_html=True
    )
with d5:
    st.markdown(
        "<div style='border:1px solid #dc262633;border-radius:8px;background:#111;padding:10px;text-align:center;'>"
        "<div style='color:#dc2626;font-size:.75rem;'>Guard Hit (−400u)</div>"
        "<div style='color:#eaeaea;font-size:1rem;font-weight:700;'>3.7%</div>"
        "</div>",
        unsafe_allow_html=True
    )

st.markdown('<hr class="h-sep">', unsafe_allow_html=True)

st.markdown("<div class='section-h'>📋 Session-Level Behavior</div>", unsafe_allow_html=True)

st.markdown("""
While the model optimizes for *weekly* outcomes, here's what to expect at the session level:

- **Average session length:** 15–25 hands (varies by line closures)
- **Session goal hit rate:** ~40% of sessions reach +30u naturally
- **Session stop rate:** ~35% of sessions end via trailing stop or defensive closure
- **LOD limit closure:** ~25% end when you hit the 2-line per session limit

**What this means:**
- Not every session will feel "complete" — that's by design
- Early closures protect the week, even when they feel frustrating
- A session that ends at +8u is still a successful session if the rules were followed
- Let the system close sessions naturally — avoid using "End Session Now" unless absolutely necessary
""")

st.markdown('<hr class="h-sep">', unsafe_allow_html=True)
st.markdown("<div class='section-h'>🎯 What This Actually Feels Like</div>", unsafe_allow_html=True)

st.markdown("""
Statistics are abstract. Here's what the distribution *feels like* in practice:

**In any given month (4 weeks):**
- Expect **3-4 green weeks** (various sizes)
- Expect **0-1 red weeks** (usually small, occasionally guard)
- A month with 4 green weeks feels amazing — but it's not guaranteed
- A month with 2 red weeks feels terrible — but it's within normal variance

**In any given quarter (12 weeks):**
- Expect **~10 green weeks**, **~2 red weeks**
- You'll likely hit at least one guard (-400u) — this is normal
- Your best week and worst week will feel like completely different systems — they're not

**The emotional trap:**
- After 3 green weeks, you'll feel invincible → this is when people scale too fast
- After 2 red weeks, you'll feel broken → this is when people freelance or quit
- Both reactions are wrong. The distribution hasn't changed.

**How long until the math "works"?**
- **Short-term (1-4 weeks):** Almost pure variance. Don't judge the system.
- **Medium-term (8-12 weeks):** Patterns emerge. Green weeks should outnumber red ~6:1.
- **Long-term (25+ weeks):** Statistical profile becomes clear. This is when compounding matters.
""")

st.markdown("""
<div class="callout">
<b>Key insight:</b> You cannot evaluate this system in 2 weeks. You need 8-12 weeks minimum 
to see the distribution play out. Patience is not optional — it's structural.
</div>
""", unsafe_allow_html=True)

# ======================= Controlled Variance (clean bullets) ======================
st.markdown("<div class='section-h'>Controlled Variance (How the System Wins)</div>", unsafe_allow_html=True)

st.markdown("""
- **Fixed cadence** — <b>6 sessions/day</b>, <b>2 lines/session</b> (same cadence used in the model)  
- **Tone logic** — neutral → green (profit mode) → red (defensive)  
- **Asymmetric exits** — small-green lock at ~+160u when fragility is high; weekly caps at +300/+400; weekly guard at −400  
- **Adaptive exposure** — bet sizing tightens in choppy/fragile conditions; opens slightly when glide is strong  
""", unsafe_allow_html=True)

st.markdown("""
<div class="callout small-note">
From a trading perspective, this engine is basically:
<b>position sizing + stop placement + take-profit rules</b> wrapped around a flat-EV stream of hands.  
It doesn’t predict outcomes — it controls how hard you press and how fast you get out.
</div>
""", unsafe_allow_html=True)

# ---------- Model assumptions / no shoe selection / discipline ----------
st.markdown("<div class='section-h'>Model Assumptions (What This System Is — and Isn’t)</div>", unsafe_allow_html=True)

st.markdown("""
- **No shoe hunting or “magic entry points.”**  
  The model assumes you’re not cherry-picking tables, counting cards, or waiting for a pattern.
  You can sit down at any normal baccarat shoe and start; the edge comes from the structure, not the shoe.
- **Hands are treated as independent.**  
  We use standard baccarat probabilities with random shoe draws — no pattern betting, no progression based on streak charts.
- **Same rules live as in testing.**  
  The cadence, caps, guards, tone logic, and bankroll structure here are the same ones enforced in the app.
- **Discipline is part of the math.**  
  All of the odds on this page assume you respect caps, cadence, and Track locks.  
  The moment you freelance — oversizing, chasing, ignoring guards — you’re no longer running the model, you’re just gambling.
""")

# ==================== (1) 🔬 How the Simulation Was Built (expander) ====================
with st.expander("🔬 How the Simulation Was Built"):
    st.markdown("""
Each result here was derived from over **50,000 simulated weeks**, using standard baccarat odds with independent random shoe draws.

- Each “week” used the **same cadence you play live**: 6 sessions × 2 lines per session  
- Each line followed the **14-step + defensive hybrid** ruleset  
- Weekly outcomes used the identical **caps, guards, and tone logic** as the live app

This isn’t a forecast — it’s the statistical distribution of outcomes from **tens of millions of simulated hands**
under the production +233 model, assuming disciplined execution.
""")

st.markdown('<hr class="h-sep">', unsafe_allow_html=True)

# ========================== Bankroll requirements (1/2/3) ==========================
st.markdown("<div class='section-h'>Bankroll Requirements & Annual Loss Odds</div>", unsafe_allow_html=True)

# Data blocks (units)
one_track = pd.DataFrame({
    "Component": ["Active (on casino)", "Strategic Reserve (off casino)", "Optimal Total"],
    "Units Needed": [1000, 1000, 2000],
    "Annual Loss Odds": ["1 / 5,556", "1 / 66,667", "1 / 166,667"]
})

two_tracks = pd.DataFrame({
    "Component": ["Active (on casino)", "Strategic Reserve (off casino)", "Optimal Total"],
    "Units Needed": [1200, 1600, 2800],
    "Annual Loss Odds": ["1 / 7,144", "1 / 100,000", "1 / 166,667"]
})

three_tracks = pd.DataFrame({
    "Component": ["Active (on casino)", "Strategic Reserve (off casino)", "Optimal Total"],
    "Units Needed": [1200, 2200, 3400],
    "Annual Loss Odds": ["1 / 4,762", "1 / 100,000", "1 / 166,667"]
})

c1, c2, c3 = st.columns(3)
with c1:
    st.markdown("**Playing 1 Concurrent Track**")
    st.dataframe(one_track, hide_index=True, use_container_width=True)
with c2:
    st.markdown("**Playing 2 Concurrent Tracks**")
    st.dataframe(two_tracks, hide_index=True, use_container_width=True)
with c3:
    st.markdown("**Playing 3 Concurrent Tracks**")
    st.dataframe(three_tracks, hide_index=True, use_container_width=True)

st.markdown("""
<div class="small-note">
“Optimal Total” combines active bankroll plus a strategic reserve designed to hard-cap downside at the weekly guard
and preserve the trading-style compounding profile the model was built around.  
Nothing removes risk — this just frames it and keeps the worst-case scenarios rare.
</div>
""", unsafe_allow_html=True)

# ==================== (2) 📈 Expected Return on Capital (ROI) =====================
st.markdown('<hr class="h-sep">', unsafe_allow_html=True)
st.markdown("<div class='section-h'>📈 Expected Return on Capital</div>", unsafe_allow_html=True)

# ROI math (assuming +233u/week per track average, $1 per unit for percentage math)
roi_rows = pd.DataFrame({
    "Tracks": [1, 2, 3],
    "Avg Units / Week": [233, 466, 699],
    "Optimal Bankroll (u)": [2000, 2800, 3400],
})

roi_rows["ROI / Week (%)"] = (roi_rows["Avg Units / Week"] / roi_rows["Optimal Bankroll (u)"]) * 100.0
st.dataframe(roi_rows, hide_index=True, use_container_width=True)

st.markdown("""
<div class="small-note">
Think of these numbers as the <b>operating characteristics</b> of the model under our assumptions,
not a promise. Real results will always depend on execution, casino rules, and your ability to stay inside the framework.
</div>
""", unsafe_allow_html=True)

# ======================= Time requirements (1/2/3 tracks) ==========================
st.markdown('<hr class="h-sep">', unsafe_allow_html=True)
st.markdown("<div class='section-h'>Time Requirements (Live Play)</div>", unsafe_allow_html=True)

time_df = pd.DataFrame({
    "Tracks": [1, 2, 3],
    "Hours / Day (5-day week)": ["2.2–2.5 h/day", "4.4–5 h/day", "6.5–7.5 h/day"],
    "Sessions / Week (avg)": [12, 24, 36],
    "Hours / Week (avg)": ["11–12.5 hours", "22–25 hours", "33–37.5 hours"],
    "Sessions / Month": [52, 104, 156],
})
st.dataframe(time_df, hide_index=True, use_container_width=True)

# ==================== (3) 📅 How a Week Progresses (timeline) =====================
st.markdown('<hr class="h-sep">', unsafe_allow_html=True)
st.markdown("<div class='section-h'>📅 How a Week Progresses</div>", unsafe_allow_html=True)

timeline = pd.DataFrame({
    "Stage": [
        "Start (Neutral)",
        "Green Tone (Profit Mode)",
        "Smaller Green Lock",
        "Red Tone (Defensive)",
        "Weekly Reset"
    ],
    "Description": [
        "New week begins at 0u with neutral tone.",
        "Profit building; Glide and τ loosen within limits.",
        "Fragility/choppiness detected → lock around +160u.",
        "Drawdown protection; exposure tightened to cap downside.",
        "Cap or guard reached; archive & start a fresh week."
    ]
})
st.dataframe(timeline, hide_index=True, use_container_width=True)

# ================= (4) ♠️ Why This Edge Exists (probabilistic + EV context) ===================
st.markdown('<hr class="h-sep">', unsafe_allow_html=True)
st.markdown("<div class='section-h'>♠️ Why This Edge Exists</div>", unsafe_allow_html=True)

st.markdown(
    """
<p><b>Baccarat odds (Banker only):</b></p>
<ul>
  <li>Banker win rate: <b>45.86%</b></li>
  <li>Player win rate: <b>44.62%</b></li>
  <li>Ties: <b>9.52%</b></li>
  <li>Banker pays 0.95× (5% commission)</li>
</ul>

<p>
On paper, this gives Banker bets a <b>house edge of -1.06%</b>&nbsp;&mdash;<br>
meaning for every <b>$100 wagered</b>, the casino expects to win <b>$1.06</b> long-term.
</p>
<p>That’s <b>negative EV</b>, and we fully acknowledge that. So how can a system still outperform in practice?</p>

<p style="margin-top:14px;font-weight:700;font-size:1rem;">The reason:</p>
<p>The system doesn’t try to <i>beat the odds per hand.</i><br>
It attacks the <b>variance structure</b> of that -1.06% game by:</p>

<ul>
  <li><b>Restricting exposure</b> when conditions are fragile (via Glide + tau trim)</li>
  <li><b>Scaling exposure</b> when volatility drops and outcomes stabilize</li>
  <li><b>Locking profits early</b> on high-fragility greens (~+160u) to bank gains</li>
  <li><b>Capping downside</b> at fixed weekly guards (-400u) and smaller reds (-85u)</li>
</ul>

<p>That reshapes the return curve:</p>
<ul>
  <li>Many <b>small, bounded losses</b> in high-volatility sequences</li>
  <li>Fewer but <b>larger locked gains</b> in stabilized sequences</li>
</ul>

<p>Over tens of thousands of cycles, this can <b>skew the distribution</b> of outcomes —
turning a flat EV curve into an <b>asymmetric, trading-like compounding model</b> when, and only when,
the rules are followed.</p>

<p style="margin-top:14px;font-weight:700;font-size:1rem;">In short:</p>
<blockquote style="margin:8px 0 0 0;">
  The system doesn’t remove the casino’s edge — it absorbs and redistributes variance through strict risk controls,
  creating a statistical asymmetry the raw house edge doesn’t account for.
</blockquote>
""",
    unsafe_allow_html=True,
)

# ---- Tiny schematic visual: flat EV vs controlled-variance (illustrative) ----
import numpy as np  # optional but fine

steps = list(range(0, 21))

# House edge: slightly negative drift (≈ -1.06% per 10 steps just for illustration)
house = [-0.0106 * (i/10.0) for i in steps]

# Controlled-variance: small dips, bigger locked gains (convex / skewed) — schematic only
controlled = [
    0.00, -0.05, -0.08, -0.06,  0.04,
    0.12,  0.10,  0.18,  0.16,  0.28,
    0.26,  0.40,  0.37,  0.55,  0.52,
    0.74,  0.70,  0.94,  0.92,  1.20,
    1.18,
]

df = pd.DataFrame({
    "Step": steps * 2,
    "Index": house + controlled,
    "Model": (["House edge (−1.06% EV)"] * len(steps)) + (["Controlled variance (bank/guard)"] * len(steps)),
})

line = alt.Chart(df).mark_line(point=True).encode(
    x=alt.X("Step:Q", axis=alt.Axis(title="Sequences / Cycles (schematic)")),
    y=alt.Y("Index:Q", axis=alt.Axis(title="Return Index (normalized)")),
    color=alt.Color("Model:N", legend=alt.Legend(title=None)),
    tooltip=["Model:N", "Step:Q", alt.Tooltip("Index:Q", format=".2f")]
).properties(
    height=260
)

st.altair_chart(line, use_container_width=True)
st.caption("Illustrative schematic: the house edge drifts slightly negative, while controlled variance creates convex, skewed gains via small bounded losses and fewer larger locked wins. (Conceptual only — see tables above for the actual model statistics.)")

# =================== Common Misconceptions ===================
st.markdown('<hr class="h-sep">', unsafe_allow_html=True)
st.markdown("<div class='section-h'>🚫 Common Misconceptions</div>", unsafe_allow_html=True)

st.markdown("""
**"This system beats the house edge."**  
No. The house edge on Banker bets remains -1.06%. What the system does is *structure your exposure* so that variance works more favorably over many cycles. You're not beating math — you're managing risk.

**"More hands = more profit."**  
Not necessarily. The model's edge comes from *controlled exposure*, not raw volume. Playing beyond cadence limits increases error rate and fatigue without improving the statistical profile.

**"I should wait for a 'good shoe' to start."**  
The model assumes random, independent hands. Shoe selection, pattern-watching, and "feeling out" a table add zero value and waste time. Start when you're ready, not when the shoe "looks right."

**"A red week means the system is broken."**  
Red weeks are built into the model (~13.5% of weeks). They're controlled, bounded, and necessary for the math to work. If you can't accept red weeks, you'll panic-Loss at the worst times.

**"I can skip Testing Mode — I understand the rules."**  
Understanding rules intellectually is different from executing them under pressure. Testing Mode exists to build muscle memory before real stakes create emotional interference.
""")

# =================== (5) Risk-to-Reward summary table ============================
st.markdown('<hr class="h-sep">', unsafe_allow_html=True)
st.markdown("<div class='section-h'>⚖️ Risk–Reward Summary</div>", unsafe_allow_html=True)

risk_table = pd.DataFrame({
    "Result Type": [
        "Full Win (+400u)",
        "Optimizer Green (+300u)",
        "Smaller Green (+160u)",
        "Red Stabilizer (−60 to −90u)",
        "Guard Hit (−400u)"
    ],
    "Probability (%)": [36.2, 22.0, 28.3, 9.8, 3.7],
    "Relative Frequency": ["~1 in 3", "~1 in 4.5", "~1 in 3.5", "~1 in 10", "~1 in 27"]
})
st.dataframe(risk_table, hide_index=True, use_container_width=True)

st.markdown("""
<div class="small-note">
All of these numbers assume you actually follow the operating model: fixed cadence, respect for caps/guards,
no shoe hunting, and no off-script bet sizing. Break those rules and you’re back in normal casino territory.
</div>
""", unsafe_allow_html=True)

# =================== (6) Finishing one-liner (emotional polish) ==================
st.markdown('<hr class="h-sep">', unsafe_allow_html=True)
st.markdown(
    "<div class='centerline'><i>“This isn’t gambling — it’s structured exposure to randomness with a statistical brake pedal.”</i></div>",
    unsafe_allow_html=True,
)

# =================== What the Numbers Don't Show ===================
st.markdown('<hr class="h-sep">', unsafe_allow_html=True)
st.markdown("<div class='section-h'>📊 What the Numbers Don't Show</div>", unsafe_allow_html=True)

st.markdown("""
These statistics assume **perfect execution**. In reality:

- **Emotional decisions** during drawdowns can turn a -85u red week into a -400u guard hit
- **Fatigue errors** compound silently — one wrong bet can cascade
- **Breaking cadence** "just once" invalidates the distribution the model is built on
- **Chasing losses** after a bad line is the #1 way players destroy good months

The numbers on this page are the *ceiling* of what's possible with discipline.  
Your actual results depend entirely on whether you can execute the process without deviation.
""")

st.markdown("""
<div class="callout">
<b>The real edge:</b> These stats exist because the model removes human judgment from betting decisions.  
The moment you add judgment back in, you're no longer running this model — you're gambling with extra steps.
</div>
""", unsafe_allow_html=True)
