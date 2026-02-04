# pages/08_Master_Your_Play.py — advanced operator guide
# (Scaling, multi-track execution, error protocols, fatigue detection, environment discipline)

import streamlit as st
st.set_page_config(page_title="Master Your Play", page_icon="🧠", layout="wide")  # set FIRST

from auth import require_auth
user = require_auth()  # gate before anything renders

from sidebar import render_sidebar
render_sidebar()

# ------------------------ Styles ------------------------
st.markdown("""
<style>
.card{
  border:1px solid #2b2b2b;
  border-radius:14px;
  padding:16px 18px;
  background:linear-gradient(135deg,#0f0f0f,#171717);
  color:#eaeaea;
  margin:8px 0 18px 0;
}
.h{
  font-weight:950;
  font-size:1.25rem;
  margin-bottom:8px;
  letter-spacing:0.01em;
}
.sub{
  color:#9ca3af;
  font-size:.94rem;
  margin-top:4px;
  margin-bottom:10px;
}
.subh{
  font-weight:800;
  font-size:1.02rem;
  margin:10px 0 6px 0;
  letter-spacing:0.01em;
}
.small{
  color:#a7a7a7;
  font-size:.92rem;
}
.callout{
  border:1px solid #334155;
  background:linear-gradient(135deg,#0f1115,#121821);
  color:#e5e7eb;
  border-radius:12px;
  padding:14px 16px;
  margin-top:10px;
}
.tldr{
  border:1px solid #3b2f1a;
  background:linear-gradient(135deg,#14110a,#1a1410);
  color:#f3f4f6;
  border-radius:14px;
  padding:16px 18px;
  margin:8px 0 18px 0;
}
.tldr-h{
  font-weight:950;
  font-size:1.15rem;
  letter-spacing:0.01em;
  margin-bottom:8px;
}
.tldr ul{ margin:8px 0 0 18px; }
.tldr li{ margin:6px 0; }
.tldr .warn{
  margin-top:10px;
  padding-top:10px;
  border-top:1px solid rgba(255,255,255,.08);
  color:#e5e7eb;
  font-size:.95rem;
}
.badge{
  display:inline-block;
  border:1px solid #3a3a3a;
  border-radius:999px;
  padding:2px 10px;
  margin-right:6px;
  font-size:.82rem;
  color:#cbd5e1;
  background:#101010;
}
hr{
  border:none;
  border-top:1px solid #2b2b2b;
  margin:12px 0;
}
</style>
""", unsafe_allow_html=True)

st.title("🧠 Master Your Play")

st.markdown(
    "<div class='sub'>This page is the <b>operator manual</b> for advanced execution. "
    "It’s designed to help you scale safely, run multiple Tracks correctly, and avoid the subtle execution errors "
    "that quietly destroy otherwise profitable systems.</div>",
    unsafe_allow_html=True
)

# ------------------------ TL;DR ------------------------
st.markdown("""
<div class="tldr">
  <div class="tldr-h">⚡ TL;DR (Advanced Execution Rules)</div>

  <ul>
    <li><b>Scale only when earned.</b> Bankroll structure + clean weeks decide — not confidence.</li>
    <li><b>Start sequential.</b> One Track at a time until execution feels boring.</li>
    <li><b>Simultaneous play is advanced.</b> If logging isn’t perfect, don’t do it.</li>
    <li><b>Error protocol:</b> when uncertain, end clean — never reconstruct.</li>
    <li><b>Fatigue is risk.</b> Two warning signs = stop immediately.</li>
  </ul>

  <div class="warn">
    <b>This is how disciplined operators survive variance:</b> protect distributions, reduce human error,
    and stack clean weeks.
  </div>
</div>
""", unsafe_allow_html=True)

# ------------------------ 1) What This Page Is ------------------------
with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="h">1) 🎯 What This Page Is (And Is Not)</div>', unsafe_allow_html=True)
    st.markdown("""
**This is not a strategy page.** You already have the engine.

This page focuses on:
- **Execution quality**
- **Risk containment**
- **Scaling without breaking the model**
- **Avoiding silent, compounding mistakes**

If *How It Works* teaches rules, **Master Your Play** teaches disciplined execution.
""")
    st.markdown("""
<div class="callout">
<b>Operator mindset:</b> You are running a rule-enforced process.  
The objective is clean execution and controlled downside — not short-term wins.
</div>
""", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ------------------------ Progression Timeline ------------------------
with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="h">📆 Your Progression Timeline</div>', unsafe_allow_html=True)
    st.markdown("""
**Week 1 (Testing Mode ON)**
- Goal: Learn the UI and flow
- Run 5-10 complete test sessions
- Experience every type of closure (line, session, week)
- Make mistakes here — that's the point
- ✅ Ready to advance when: You can explain what closes a line, session, and week

**Week 2-3 (First Live Weeks)**
- Goal: Clean execution on 1 Track
- Keep $/unit conservative
- Focus on process, ignore P/L
- End sessions early if uncertain
- ✅ Ready to advance when: You complete 2 weeks without freelancing

**Month 2 (Building Consistency)**
- Goal: Establish rhythm
- Same time, same Track, same process
- Start weekly reviews
- Consider adding Track 2 only if execution is boring
- ✅ Ready to advance when: Weekly reviews show no red flags

**Month 3+ (Scaling Phase)**
- Goal: Optimize and compound
- Evaluate $/unit increases (if conditions met)
- Multi-track rotation (if ready)
- The process should feel automatic
- ✅ Success metric: You barely think about individual hands
""")
    st.markdown("""
<div class="callout">
<b>Testing Mode guidance:</b> Run at least <b>5 complete sessions</b> with at least one of each:<br>
- Line closure (Smart Trim, Kicker, or Trailing Stop)<br>
- Session closure (Goal or Stop)<br>
- Week closure (any lock type)<br><br>
If you haven't experienced all three closure types, you haven't tested enough.
</div>
""", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ------------------------ 2) Scaling Units ------------------------
with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="h">2) 📈 Scaling Units Correctly (Non-Negotiable)</div>', unsafe_allow_html=True)
    st.markdown("""
Scaling is where most systems fail — not because the model breaks,
but because execution discipline does.

**You do not scale because you feel ready.**  
You scale because your **bankroll structure proves readiness.**
""")
    st.markdown("""
**✅ Required conditions to increase $/unit (ALL must be true):**
- **2+ recent green weeks**
- **Total bankroll exceeds target units** for your Track count
- **No Track is in Defensive Mode**
- Execution has been **clean** (no freelancing, no recovery attempts)

**🧱 Correct scaling behavior:**
- Increase in **small increments**
- **$/unit is global** — the app enforces identical sizing across all Tracks automatically
- Never scale **mid-week**
- Never scale **mid-session** (unit size is locked during active play)
- Never scale to recover losses
""")
    st.markdown("""
<div class="callout">
<b>Execution principle:</b> scale when risk decreases — not when confidence increases.
</div>
""", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ------------------------ 3) Multi-Track Execution ------------------------
with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="h">3) 🧭 Multi-Track Execution: Sequential vs Simultaneous</div>', unsafe_allow_html=True)

    st.markdown('<div class="subh">✅ Start with sequential execution (recommended)</div>', unsafe_allow_html=True)
    st.markdown("""
When building execution skill:
- Run **one Track at a time**
- Finish the **entire line** before switching
- Treat each Track as a separate business unit

This minimizes:
- Logging errors
- Cognitive load
- Emotional bleed between Tracks
""")

    st.markdown('<div class="subh">⚠️ Simultaneous execution (advanced only)</div>', unsafe_allow_html=True)
    st.markdown("""
Running multiple Tracks simultaneously can increase volume —
but it also increases **human error surface area**.

Consider it **only if**:
- You have weeks of clean execution
- You are calm, unrushed, and focused
- You can log every hand perfectly

**Strict rules:**
- Log immediately — no delays
- No guessing or reconstruction
- **$/unit is global** — the app handles this automatically
- If you feel rushed: **stop immediately**
""")

    st.markdown("""
<div class="callout">
<b>Reality:</b> Advanced operators earn more by avoiding errors than by chasing volume.
</div>
""", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ------------------------ 4) Error Recovery ------------------------
with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="h">4) 🧯 Error Recovery Protocol</div>', unsafe_allow_html=True)
    st.markdown("""
If **any** of these occur:
- Missed hand logging
- Wrong bet size
- Uncertainty about Next Bet
- App disconnect mid-line
- Lost context after refresh

**Execute this protocol immediately:**
1. Stop the line  
2. End the session  
3. Do not reconstruct  
4. Do not manually fix  

Ending early preserves the distribution.
""")
    st.markdown("""
<div class="callout">
<b>Execution principle:</b> protect the system, not your pride.
</div>
""", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ------------------------ 5) Track Rotation ------------------------
with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="h">5) 🔄 Track Specialization vs Rotation</div>', unsafe_allow_html=True)

    st.markdown('<div class="subh">🎯 Track specialization</div>', unsafe_allow_html=True)
    st.markdown("""
Best when:
- Fatigue is present
- Precision matters
- Scaling units

Benefits:
- Lower error rate
- Cleaner weeks
- Reduced emotional noise
""")

    st.markdown('<div class="subh">🧭 Track rotation</div>', unsafe_allow_html=True)
    st.markdown("""
Best when:
- Focus is high
- Multiple Tracks are Neutral or Green
- Cadence efficiency is the goal

Rules:
- Never rotate mid-line
- Never rotate to chase outcomes
- Rotate to manage fatigue — not excitement
""")

    st.markdown("""
<div class="callout">
<b>Rule:</b> rotate to protect execution quality.
</div>
""", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ------------------------ 6) Fatigue Detection ------------------------
with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="h">6) 🧠 Fatigue Detection (Silent Risk)</div>', unsafe_allow_html=True)

    st.markdown('<div class="subh">Warning signs</div>', unsafe_allow_html=True)
    st.markdown("""
- Rushing inputs
- Irritation with stops or caps
- Second-guessing Next Bet
- Urge to “just finish”
""")

    st.markdown('<div class="subh">Hard rule</div>', unsafe_allow_html=True)
    st.markdown("""
If **two or more** appear — end the session immediately.

Fatigue creates mistakes before awareness.
""")

    st.markdown("""
<div class="callout">
<b>Disciplined operators quit early.</b> Amateurs quit after damage.
</div>
""", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ------------------------ 6.5) Red Flags (Stop Immediately) ------------------------
with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="h">🚩 Red Flags (Stop Immediately)</div>', unsafe_allow_html=True)
    st.markdown("""
If you notice **any** of these behaviors in yourself, stop playing immediately:

- **Justifying a freelance bet** ("just this once," "I have a feeling")
- **Anger at the app** for closing a line or session "too early"
- **Calculating how many wins you need** to get back to even
- **Playing past cadence limits** "because I'm on a roll"
- **Hiding results** from yourself (not checking P/L, avoiding Player Stats)
- **Increasing $/unit after a loss** to recover faster
- **Playing while distracted** (TV, conversations, other tabs)
- **Feeling like you "need" to play** today

These are not personality flaws — they're warning signs that emotional interference is active.  
The correct response is always: **stop, walk away, return tomorrow.**
""")
    st.markdown("""
<div class="callout">
<b>Self-awareness is edge.</b> The operators who last longest are the ones who recognize tilt before it costs them.
</div>
""", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ------------------------ 7) Environment ------------------------
with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="h">7) 🧰 Environment Discipline</div>', unsafe_allow_html=True)
    st.markdown("""
This engine assumes professional-grade conditions.

**Required setup:**
- Stable internet
- One screen minimum
- No multitasking mid-line
- No alcohol
- No distractions
""")
    st.markdown("""
<div class="callout">
<b>Clean environment → clean execution → clean data.</b>
</div>
""", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ------------------------ 8) Volume Fallacy ------------------------
with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="h">8) 🧮 The Volume Fallacy</div>', unsafe_allow_html=True)
    st.markdown("""
More volume does not guarantee more profit.

What scales faster than results:
- Error rate
- Fatigue
- Emotional interference

The engine already runs aggressive cadence.
Outpacing execution capacity erodes edge.
""")
    st.markdown("""
<div class="callout">
<b>Consistency beats intensity.</b>
</div>
""", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ------------------------ 9) Operator Mindset ------------------------
with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="h">9) 🧊 Operator vs Gambler</div>', unsafe_allow_html=True)
    st.markdown("""
**Gambler mindset**
- Predicts outcomes
- Feels urgency
- Chases runs
- Attaches identity to results

**Operator mindset**
- Executes instructions
- Accepts variance
- Protects downside
- Repeats clean processes
""")
    st.markdown("""
<div class="callout">
<b>The engine creates cash flow.</b> Discipline preserves it.
</div>
""", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ------------------------ 10) Weekly Review Protocol ------------------------
with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="h">10) 📅 Weekly Review Protocol</div>', unsafe_allow_html=True)
    st.markdown("""
At the end of each calendar week, spend 10 minutes reviewing your execution:

**Execution Quality:**
- Did I follow Next Bet 100% of the time?
- Did I respect all line/session/week closures?
- Did I stay within cadence limits?
- Did I log every hand including ties?

**Emotional Quality:**
- Did I feel rushed or impatient at any point?
- Did I have any urges to freelance?
- Did I stop when fatigue appeared?
- Did I accept red sessions/weeks without chasing?

**Process Quality:**
- Was my environment clean and distraction-free?
- Did I play at consistent times?
- Did I track bonuses and allocate them properly?
- Did I review my Player Stats page?

**Action Items:**
- If execution was clean → continue as normal
- If 1-2 minor slips → note them, recommit
- If multiple slips → consider a Testing Mode reset week
- If major deviation (freelancing, chasing) → mandatory 3-day break
""")
    st.markdown("""
<div class="callout">
<b>The review is not optional.</b> Operators who don't reflect repeat mistakes. Operators who reflect compound gains.
</div>
""", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ------------------------ 11) Long-Term Mindset ------------------------
with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="h">11) 🎯 Long-Term Mindset</div>', unsafe_allow_html=True)
    st.markdown("""
This system is designed for **months and years**, not days and weeks.

**What to expect over 3 months:**
- ~12 weeks of data (assuming consistent play)
- 8-10 green weeks, 2-3 small red weeks, 0-1 guard hits (statistically)
- Clear patterns in your Player Stats
- Confidence in the process (if execution is clean)

**What to expect over 12 months:**
- ~50 weeks of data
- Meaningful compounding if $/unit scaled appropriately
- Deep understanding of your own execution patterns
- The ability to run the system almost automatically

**What separates winners from losers over time:**
- Winners: same $/unit, same cadence, same rules — week after week
- Losers: constantly adjusting, chasing, "improving," freelancing

**The boring truth:**
The players who make the most money are the ones you'd never notice.  
They don't have stories about big wins or clever plays.  
They just executed the same process 500 times.
""")
    st.markdown("""
<div class="callout">
<b>Your goal is not to win this week.</b> Your goal is to still be executing cleanly 52 weeks from now.
</div>
""", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ------------------------ Closing ------------------------
with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="h">✅ Final Reminder</div>', unsafe_allow_html=True)
    st.markdown("""
You don’t need clever ideas.  
You need consistent execution.

- Follow **Next Bet**
- Respect **tone**
- Protect the **week**
- End early when uncertain

That’s how disciplined operators win quietly.
""")
    st.markdown("</div>", unsafe_allow_html=True)
