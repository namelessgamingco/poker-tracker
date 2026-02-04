# pages/05_How_It_Works.py — high-level guide
# (+ Live vs Testing, lifecycle, multi-track bankrolls with bust odds, rotation playbook, bonuses, and bankroll calculator)
import streamlit as st
st.set_page_config(page_title="How the App Works", page_icon="📘", layout="wide")  # set FIRST

from auth import require_auth
user = require_auth()  # gate before anything renders

from sidebar import render_sidebar
from week_manager import WeekManager  # typing only

render_sidebar()  # only show after auth

# ------------------------ Styles ------------------------
st.markdown("""
<style>
.hiw-card{
  border:1px solid #2b2b2b;
  border-radius:14px;
  padding:16px 18px;
  background:linear-gradient(135deg,#0f0f0f,#171717);
  color:#eaeaea;
  margin:8px 0 18px 0;
}

/* Bigger, punchier section titles for each card */
.hiw-h{
  font-weight:900;
  font-size:1.25rem;   /* was 1.05rem */
  margin-bottom:8px;   /* a bit more breathing room */
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
  margin-top:8px;
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
.tldr ul{
  margin:8px 0 0 18px;
}
.tldr li{
  margin:6px 0;
}
.tldr .warn{
  margin-top:10px;
  padding-top:10px;
  border-top:1px solid rgba(255,255,255,.08);
  color:#e5e7eb;
  font-size:.95rem;
}
.kv{
  display:flex;
  gap:10px;
  align-items:flex-start;
}
.kv .k{
  min-width:170px;
  color:#9ba3af;
}
.kv .v{
  flex:1;
}

.badge{
  display:inline-block;
  border:1px solid #3a3a3a;
  border-radius:999px;
  padding:2px 8px;
  margin-right:6px;
  font-size:.85rem;
  color:#cbd5e1;
}

td, th { white-space: nowrap; }
</style>
""", unsafe_allow_html=True)

# Live hints (tone + cap)
tone_name = st.session_state.get("_tone_name", "neutral")
cap_target = "—"
def_mode = "OFF"
soft_shield_mode = "OFF"
try:
    active_id = st.session_state.get("active_track_id", "Track 1")
    wk: WeekManager | None = st.session_state.get("week_by_track", {}).get(active_id)
    if wk:
        cap_target = int(getattr(wk.state, "cap_target", 300))
        def_mode = "ON" if getattr(wk, "defensive_mode", False) else "OFF"
        soft_shield_mode = "ON" if getattr(wk.state, "soft_shield_active", False) else "OFF"
except Exception:
    pass

# ------------------------ TL;DR (Impatient Players) ------------------------
st.markdown("""
<div class="tldr">
  <div class="tldr-h">⚡ TL;DR (If You Refuse To Read)</div>

  <ul>
    <li><b>Start in Testing Mode.</b> Run <b>multiple full test sessions</b> before any real money.</li>
    <li><b>Banker only.</b> No Player bets. No side bets. No “just one for fun.”</li>
    <li><b>Next Bet is law.</b> If you freelance even once, you’re not running the engine.</li>
    <li><b>Respect locks + cadence.</b> Week locks end play on that Track. nb/LOD caps exist to control volatility.</li>
    <li><b>Expect variance.</b> Red weeks happen. The goal is controlled downside + stacking clean weeks.</li>
  </ul>

  <div class="warn">
    <b>Read the full page anyway:</b> If you don’t understand <i>how lines/sessions/weeks end</i> and what tone means,
    you’ll make the exact mistakes that kill the model.
  </div>
</div>
""", unsafe_allow_html=True)

# ------------------------ Boring Is The Edge (Core Config Reality) ------------------------
with st.container():
    st.markdown('<div class="hiw-card">', unsafe_allow_html=True)
    st.markdown('<div class="hiw-h">Boring Is The Edge</div>', unsafe_allow_html=True)
    st.markdown("""
Most of your hands will feel **flat** and **uneventful** — and that’s by design.

This engine isn’t trying to entertain you. It’s trying to **produce a repeatable cash-flow profile over many weeks**
by doing the hard work behind the scenes:
- controlling exposure when conditions get fragile  
- closing lines and sessions before you over-extend  
- protecting good weeks with caps and tightening  
- containing bad weeks with defense, stabilizers, and guards  

**Your job is brutally simple:**  
**Bet Banker only. Follow Next Bet. Respect locks.**  

If you “spice it up,” you’re not improving anything — you’re just reintroducing human error.
The core config is built to win by being **boring enough to survive variance**.

<div class="callout">
<b>Fight your human behavior:</b> If it feels too slow, too repetitive, or “too easy”… good.  
That’s the exact emotional state that makes people freelance and torch the model.
</div>
""", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


# ------------------------ Engine Hierarchy (How Everything Ties Together) ------------------------
with st.container():
    st.markdown('<div class="hiw-card">', unsafe_allow_html=True)
    st.markdown('<div class="hiw-h">Engine Hierarchy (How It All Connects)</div>', unsafe_allow_html=True)
    st.markdown("""
Everything in the app is the same engine operating at different time scales.  
Think of it like nested containers:

<div class="callout">
<b>Track</b> → contains Weeks (independent engine per Track)<br>
<b>Week</b> → contains Days + Sessions until a weekly lock fires<br>
<b>Day</b> → enforces daily cadence (nb) per Track (resets at local midnight)<br>
<b>Session</b> → contains Lines and banks into the Week when it ends<br>
<b>Line</b> → the hand-by-hand progression (14-step ladder) that auto-closes by rules
</div>

**Why this matters:**
- **Line rules** manage *micro-risk* (when to trim, stop, or lock a line).
- **Session rules** keep play *bite-sized* and bank results cleanly.
- **Day cadence (nb/LOD)** controls total daily volatility so you don’t binge risk.
- **Week logic** is the real “profit protection layer” (caps, optimizer, stabilizers, guards).
- **Track** is the sandbox: multiple Tracks = multiple independent engines with independent weeks.

If you understand this hierarchy, the app becomes obvious:  
**you’re never making judgment calls — you’re just moving through the lifecycle.**
""", unsafe_allow_html=True)
    st.markdown("""
<div class="callout small">
<b>Two different “orders” exist:</b><br>
• <b>Play order:</b> Track → Line → (repeat) → Session → (repeat) → Week Close<br>
• <b>Container order:</b> Track contains Week contains Day contains Session contains Line
</div>
""", unsafe_allow_html=True)    
    st.markdown("</div>", unsafe_allow_html=True)

# ------------------------ Understanding the Tracker UI ------------------------
with st.container():
    st.markdown('<div class="hiw-card">', unsafe_allow_html=True)
    st.markdown('<div class="hiw-h">Understanding the Tracker UI</div>', unsafe_allow_html=True)
    st.markdown("""
When you open the Tracker, here's what you'll see:

**Header Strip (top)**
- **Track selector** — switch between your Tracks
- **Week #** — which week you're on for this Track
- **Week P/L** — running total for this Track's week
- **Tone indicator** — Neutral (white), Green (profit mode), Red (defensive)
- **Cadence chips** — `nb X/6` (sessions today) and `LOD X/2` (lines this session)

**Next Bet Card (center)**
- Shows exactly what to bet: amount and side (always Banker)
- **Green highlight** = week trending well, protect profits
- **Red highlight** = defensive conditions, stay strict
- **No highlight** = normal conditions

**Outcome Buttons**
- **Win** — Banker won (you won)
- **Loss** — Player won (you lost)
- **Tie** — Push (still log it — ties affect engine state)

**Session Controls (bottom)**
- **End Session Now** — use sparingly (see guidance below)
- **Start Next Week** — appears only when week is locked

**Event Feed (right side)**
- Shows recent actions: hands logged, line closures, session events
- Helps you track what just happened
""")
    st.markdown("""
<div class="callout">
<b>When to use "End Session Now":</b><br>
- You need to leave and can't continue<br>
- You're fatigued and recognize warning signs<br>
- Something feels wrong (connection issues, uncertainty)<br><br>
<b>When NOT to use it:</b><br>
- To "lock in" a small profit (let the system manage this)<br>
- Because you're frustrated with the line<br>
- To start fresh after a loss (this is chasing behavior)
</div>
""", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ------------------------ How to Use This Page ------------------------
with st.container():
    st.markdown('<div class="hiw-card">', unsafe_allow_html=True)
    st.markdown('<div class="hiw-h">How to Use This Page (Read This First)</div>', unsafe_allow_html=True)
    st.markdown("""
This page is your **operating manual** for the Core Engine (the framework behind all app behavior).

**How to use it to succeed:**
- **Read Core Flow once** so you understand how play moves (**hands → line → session → week**) and how Tracks stay independent.
- **Memorize the Basics** so you don’t accidentally break the model (banker-only, no freelancing, test first).
- **Internalize “What to Expect”** so variance doesn’t shake your confidence or trigger bad decisions.

If you do those three things, the app becomes simple:  
**follow Next Bet, respect locks, and let the system do the risk management.**
""")
    st.markdown(
        """
<div class="callout">
<b>Rule #1:</b> This app is not “a tracker.” It is a <b>rule enforcement system</b>.  
Your job is execution — the app handles structure, limits, and guardrails.
</div>
""",
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

# ------------------------ Core Flow ------------------------
with st.container():
    st.markdown('<div class="hiw-card">', unsafe_allow_html=True)
    st.markdown('<div class="hiw-h">Core Flow</div>', unsafe_allow_html=True)
    st.markdown("""
1. **Pick a Track** → each Track has its own engine, tone, and independent week state.  
2. **Play a Line** → the **Next Bet** card tells you exactly what to bet each hand.  

<div class="callout small">
<b>Next Bet highlight colors (what they mean):</b><br>
• <b>No highlight</b> = normal conditions. Just follow the card.<br>
• <b style="color:#22c55e;">Green highlight</b> = the week is trending well (protect profits). The engine will often tighten behavior to lock in the week efficiently.<br>
• <b style="color:#ef4444;">Red highlight</b> = higher-risk conditions (fragility detected / defensive behavior active). The bet is still valid — it’s a signal to stay strict and avoid extra volume or freelancing.
</div>

3. **Settle Hands** (Win / Loss / Tie) → line, session, and week P/L all update automatically.  
4. **Auto-controls** kick in when needed (Smart Trim, Kicker, Trailing Stop, Profit Preserve, Session Goal/Stop):  
   you'll see a clear notification any time one of these rules fires.  
   - **Smart Trim / Kicker / Trailing Stop** → close the LINE  
   - **Profit Preserve** → closes the SESSION (Smart Trim + profit qualifier)  
   - **Session Goal / Session Stop** → close the SESSION 
5. **Weekly controls** (Optimizer Cap, Primary Cap, Red Week Stabilizer, Weekly Guard)  
   are also automatic and will notify you immediately when a week locks.  
6. **Cadence (per Track)** mirrors the profile engine and is enforced automatically on each Track:  
   - **nb = sessions/day per Track** → up to **6 sessions/day** for that Track  
   - **LOD = lines/session per Track** → up to **2 lines/session** for that Track  
   - **Midnight reset (local)** → daily nb/LOD counters reset at local midnight for each Track  
   - The UI shows chips like `nb a/b` and `LOD c/d`; you’ll get a notice when you approach or hit a limit.
""", unsafe_allow_html=True)
    st.markdown(
        """
<div class="callout">
<b>Why it’s built this way:</b> the core config is not just “a strategy” — it’s a full
<b>lifecycle</b> from per-hand → per-line → per-session → per-week.  
The app is wired so you don’t have to remember rules mid-play; it simply tells you:
what to bet next, when a line or session is done, and when a week is over.
</div>
""",
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

# ------------------------ The Basics ------------------------
with st.container():
    st.markdown('<div class="hiw-card">', unsafe_allow_html=True)
    st.markdown('<div class="hiw-h">The Basics (Non-Negotiables)</div>', unsafe_allow_html=True)
    st.markdown("""
These are the rules that keep the framework intact. Break these and you’re no longer running the model.

**Betting Basics**
- **Bet Banker only.** No Player bets, no side bets, no “I’ll just mix one in.”
- Use standard baccarat rules and normal payouts (or only variants you’ve tested and confirmed behave the same).

**Execution Basics**
- **The Next Bet card is law.** If it says 3u Banker, you bet 3u Banker — nothing else.
- **Do not place hands off-app** while a line is live. Skipped/unsynced hands corrupt the whole distribution.
- **Don’t “fix” the system mid-run.** No manual stops, no manual sizing changes, no pattern overrides.

**Getting Started (Do this first)**
- Start in **Testing Mode** and run **multiple full test sessions**.
- **Do not bet real money** until you can confidently explain:
  - how a line ends  
  - how a session ends  
  - what tone means (Neutral/Green/Red)  
  - what locks a week and what you do next  
- Once you’re comfortable: turn Testing Mode OFF and play live inside cadence limits.

**Money Basics**
- Set your **$/unit once** in Settings or in the Tracker — it applies globally to all Tracks automatically.
- You cannot set different unit sizes per Track; this is intentional to prevent bankroll fragmentation.
- Don't size up because you "feel good." Size up only when your bankroll plan supports it.

If you follow the basics, the system is boring — and that’s the point.
""")
    st.markdown(
        """
<div class="callout">
<b>Fast sanity check:</b> If you ever catch yourself thinking “just this one time,” that’s your signal to stop.  
The system is designed to remove “one time.”
</div>
""",
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

# ------------------------ First Week Checklist ------------------------
with st.container():
    st.markdown('<div class="hiw-card">', unsafe_allow_html=True)
    st.markdown('<div class="hiw-h">✅ First Week Checklist</div>', unsafe_allow_html=True)
    st.markdown("""
Use this checklist during your first week to build proper habits:

**Before Your First Session:**
- [ ] Read this entire page
- [ ] Read Statistical Odds page
- [ ] Read Master Your Play page
- [ ] Turn ON Testing Mode
- [ ] Set your $/unit in Settings (start conservative)
- [ ] Understand: Line → Session → Week lifecycle

**During Testing Mode (aim for 5+ test sessions):**
- [ ] Complete at least one full line without errors
- [ ] Experience a line closure (Smart Trim, Kicker, or Trailing Stop)
- [ ] Experience a session closure (Goal or Stop)
- [ ] See tone shift from Neutral to Green or Red
- [ ] Practice using "End Session Now" cleanly
- [ ] Try switching between Tracks mid-session (finish line first)

**Before Going Live:**
- [ ] Can you explain what closes a line? A session? A week?
- [ ] Do you understand why cadence limits exist?
- [ ] Have you experienced a controlled red session without panicking?
- [ ] Is your bankroll at target levels for your Track count?
- [ ] Turn OFF Testing Mode only when execution feels boring

**Your first live week:**
- [ ] Follow Next Bet without exception
- [ ] End sessions clean — no "one more hand"
- [ ] If uncertain about anything: stop, don't guess
- [ ] Log every hand including ties
- [ ] Accept the week's result without chasing
""")
    st.markdown("""
<div class="callout">
<b>Success metric:</b> Your first week is successful if you followed the process perfectly —  
regardless of whether the P/L was green or red.
</div>
""", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ------------------------ Session Goals & Weekly Goals ------------------------
with st.container():
    st.markdown('<div class="hiw-card">', unsafe_allow_html=True)
    st.markdown('<div class="hiw-h">Session Goals & Weekly Goals</div>', unsafe_allow_html=True)

    st.markdown("""
**Session Goals (per Track):**  
- **Session Goal:** **+30u**. When hit, the session banks and closes automatically.  
- **Session Stop:** **-60u** (Normal) or **-40u** (under Soft Shield). When hit, the session closes and banks the loss.  
- **Daily cadence limits:** up to **6 sessions/day** and **2 lines/session** per Track.
""")

    st.markdown(
        """
<div class="callout">
<b>Important:</b> A “Week” in this app is <b>NOT a calendar week</b>.  
A Track’s week ends when it hits a <b>weekly lock condition</b> (cap/guard/stabilizer/lock) — which can happen <b>any day</b>, including mid-week.  
Your <b>Week #</b> increases only when that Track closes from a weekly lock condition.<br><br>
<b>Tracks are independent engines:</b> Track 1 can be on <b>Week 7</b> while Track 2 is on <b>Week 3</b>.  
Each Track closes and advances weeks on its own timeline.
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown("""
**Weekly Goals (per Track):**  
- **Primary Cap (win):** **+400u** — closes that Track’s week.  
- **Optimizer Cap (win):** **+300u** — tighter cap that can engage when the week is fragile.  
- **Weekly Guard (loss):** **−400u** — hard stop that closes that Track’s week.  
- **Tone Triggers (live awareness):**  
  - 🟩 **Green** at ~+160u → “good week” tone with tighter behavior  
  - 🟥 **Red** at ~−85u → enters defensive mode; may lock early (−60 to −90u) if conditions worsen


**When these hit:**  
- **Session Goal / Session Stop:**  
  The session ends immediately, banks the result, and you can start a new session  
  (as long as daily nb/LOD limits for that Track allow).  

- **Week Close (cap, guard, stabilizer, or lock):**  
  When a Track hits a weekly condition, that Track’s week is **finished and locked** — immediately.  
  - You **cannot keep playing that Track** until you press **Start Next Week** on the Tracker.  
  - Pressing **Start Next Week** moves that Track to **Week N+1** (because the prior week closed).  
  - Other Tracks are unaffected and can keep playing normally — they have their own weeks and their own locks.
""")

    st.markdown(
        """
<div class="callout">
<b>Why these exist:</b> the engine profile assumes you’ll protect good weeks and cap bad ones.
Session goals keep things “bite-sized” so you don’t chase or over-extend.  
Weekly caps and guards enforce a ceiling on upside and downside so you stack weeks,
not hero-ball one giant session.
</div>
""",
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

# ------------------------ What to Expect ------------------------
with st.container():
    st.markdown('<div class="hiw-card">', unsafe_allow_html=True)
    st.markdown('<div class="hiw-h">What to Expect (So You Don’t Self-Destruct)</div>', unsafe_allow_html=True)
    st.markdown("""
The engine is built for **structured cash-flow behavior over many weeks**, not guaranteed short-term outcomes.
If you don’t expect variance, you’ll panic at the exact wrong time.

**Returns & Variance**
- You will have **bad runs**. Some days/weeks will be red. That is normal.
- The framework is designed so red weeks are **controlled** (guards, stabilizer, defensive behavior).
- The goal is not “win every session.” The goal is to **survive variance and stack clean weeks**.

**Stress & Decision Pressure**
- The most stressful moments are usually:
  - after a string of losses  
  - when you’re close to a cap/lock  
  - when you feel urgency to “make it back”  
- The app exists to prevent emotional decisions. If you follow it, the stress drops over time.

**What success actually looks like**
- Lots of “boring” sessions.
- Week locks that feel early sometimes (that’s protection, not failure).
- A long track record of **executed lifecycles** — not heroic comebacks.

**If you feel tilted**
- Stop the session clean (don’t freelance).
- Walk away.
- Come back later or the next day. The system will still be there.

Your job isn’t to predict outcomes — it’s to execute the process.
""")
    st.markdown(
        """
<div class="callout">
<b>Non-negotiable mindset:</b> If you can’t tolerate a controlled red week without spiraling, you shouldn’t play live yet.  
Use Testing Mode until the process feels routine.
</div>
""",
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

# ------------------------ Definitions: Lines, Sessions, Weeks ------------------------
with st.container():
    st.markdown('<div class="hiw-card">', unsafe_allow_html=True)
    st.markdown('<div class="hiw-h">Definitions: Line, Session, Day, Week, Track</div>', unsafe_allow_html=True)
    st.markdown("""
**Line**  
- A **line** is a single progression of hands with a fixed starting bet path (the 14-step ladder).  
- A line ends when any of these fire:  
  - **Line Complete** — all numbers cancelled via wins (natural completion)  
  - **Line Cap** — hit +180u (normal) or +120u (defensive)  
  - **Trailing Stop** — protected a big peak, gave back 60u from peak  
  - **Smart Trim** — fragility too high, gates passed, line in profit  
  - **Kicker** — +50u profit with low fragility, before trailing arms  
- When a line ends, the app automatically starts a **fresh line** (unless you're at the LOD limit).

**Session**  
- A **session** is a block of play on one Track, made up of one or more lines.  
- A session ends when:  
  - **Session Goal** hits (+30u)  
  - **Session Stop** hits (-60u normal, -40u under Soft Shield)  
  - **Profit Preserve** fires (Smart Trim + session ≥ +20u or bet ≥ 22u)  
  - You choose **End Session Now**, or  
  - You hit the per-session line limit (**LOD**).  
- When a session ends, the result is **banked into the week**, nb increments, and the engine resets for the next session.

**Day**  
- A “day” is simply the **daily cadence window** for a Track.  
- At local midnight, the Track’s **nb/LOD counters reset** for the next day.  
- Daily cadence exists to prevent binge-volume and keep volatility controlled.

**Week**  
- A **week** is a Track-level container that continues until a **weekly lock** fires.  
- It is **not tied to the calendar**. A week can end on Monday, Thursday, or five minutes after it starts.  
- A week closes when:  
  - Weekly Primary Cap (+400u) or Optimizer Cap (+300u) hits  
  - Weekly Guard (−400u) hits  
  - Small Green Lock (+160u with fragility) triggers  
  - Red Week Stabilizer triggers (−85u zone + worsening conditions → closes −60 to −90u)
- When a week closes:  
  - That Track is **locked** (no more play on that Track).  
  - You must press **Start Next Week** on the Tracker to move that Track to **Week N+1**.  
  - Your **Week # increases only when a week closes** (cap/guard/stabilizer/lock).  
- **Tracks are independent engines:** each Track has its own week timeline, so different Tracks can be on different week numbers at the same time.

**Track**  
- A Track is an independent engine with its own Week, tone, cadence, and locks.  
- Switching Tracks changes what you’re driving — it doesn’t reset the others.
""")
    st.markdown("</div>", unsafe_allow_html=True)

# ------------------------ What Happens When... ------------------------
with st.container():
    st.markdown('<div class="hiw-card">', unsafe_allow_html=True)
    st.markdown('<div class="hiw-h">❓ What Happens When...</div>', unsafe_allow_html=True)
    st.markdown("""
**...I need to leave mid-line?**  
End the session cleanly using "End Session Now." Don't leave a line hanging — it corrupts state.

**...I accidentally log the wrong outcome?**  
Use "Undo last hand" if available. If not, end the session and start fresh. Don't try to "fix" it manually.

**...my internet disconnects mid-hand?**  
Refresh the page. Your state is saved. Continue from where you left off. If uncertain, end the session.

**...I hit a week lock but want to keep playing?**  
Switch to a different Track. The locked Track stays locked until you press "Start Next Week."

**...I want to play but all Tracks are locked?**  
Wait. This is the system protecting you. Start new weeks when you're ready, not when you're impatient.

**...I have a bad feeling about a shoe?**  
Feelings are not inputs. The model doesn't care about shoe quality. If you're anxious, that's fatigue — stop playing.

**...I want to increase my $/unit?**  
Check: 2+ green weeks? Bankroll above target? No Tracks in Defensive Mode? If all yes, step up in small increments.

**...I had a terrible week and want to recover?**  
Don't. Start the next week clean with the same $/unit. Chasing is how people turn -85u into -400u.
""")
    st.markdown("</div>", unsafe_allow_html=True)

# ------------------------ Table & Shoe Selection ------------------------
with st.container():
    st.markdown('<div class="hiw-card">', unsafe_allow_html=True)
    st.markdown('<div class="hiw-h">Table & Shoe Selection (What Actually Matters)</div>', unsafe_allow_html=True)

    st.markdown("""
Short version: **you do NOT need to hunt “good shoes” or “hot tables.”**

The **engine** is designed to operate under:
- Standard baccarat rules  
- **Banker-only betting** with normal ~5% commission  
- Random shoes (no “perfect entry point,” no pattern dependence)

**What this means in practice:**
- It is **irrelevant which shoe you join** or **what hand number** you start on.
- You can sit **mid-shoe, leave, and come back later** — the engine only cares about your own  
  **line → session → week** state, not the casino’s shoe history.
- Roads, streaks, chop/run, and visual patterns are optional entertainment —  
  **they are not inputs to the engine.**
""")

    st.markdown("""
<div class="callout">
  <b>Maximize time, not “table quality.”</b><br>
  The real bottleneck with this model is <b>time</b>, not finding the perfect shoe.<br><br>
  <b>Use Speed Baccarat or Super Speed Baccarat whenever possible.</b><br>
  It’s the simplest way to get more completed lines/sessions with less real-life time spent staring at a table.
</div>
""", unsafe_allow_html=True)

    st.markdown("""
**Non-negotiables:**
- **Banker bets only.** No Player bets. No side bets. No “just one for fun.”
- Standard main-game baccarat only (no rule variants that materially change payouts unless you’ve tested them).
- No using side bets to “smooth” variance — they add noise and break the risk profile.

**Why this works:**
The cash-flow profile does **not** come from predicting shoes.  
It comes from **structured exposure, capped downside, cadence control, and week-level protection**.

Your edge is discipline — not table selection.
""")

    st.markdown("</div>", unsafe_allow_html=True)

# ------------------------ How to Screw This Up ------------------------
with st.container():
    st.markdown('<div class="hiw-card">', unsafe_allow_html=True)
    st.markdown('<div class="hiw-h">How to Screw This Up</div>', unsafe_allow_html=True)
    st.markdown("""
The system is built to survive variance and extract predictable cash flow — but it only works if you respect the structure.  
These are the exact ways people blow it up:

- **Freelancing bets.** Ignoring the **Next Bet** card for “just one hand” breaks the entire risk model.  
- **Pushing past week locks.** Once a week is capped or guarded and you keep playing that Track, you’re no longer running a weekly avg of +233 — you’re gambling.  
- **Breaking the sequence.** You *can* switch tables, join mid-shoe, or leave and come back. What kills the model is
  playing hands off-app, skipping entries, or mixing in unlogged “side action” while a line is live.  
- **Skipping Ties (or not logging them).** A tie might feel like “nothing happened,” but it still affects the engine’s internal progression and pacing.  
  If you ignore ties, your line/session state can drift, and the Next Bet + tone behavior can desync over time.
- **Chasing a bad session.** The philosophy is “finish the line / session / week clean.” Chasing outside that structure corrupts the distribution completely.  
- **Randomly changing $/unit.** The unit structure is tied to your drawdown ceiling. If you size up without the bankroll, the downside gets very real, very fast. Unit size is locked during active sessions to prevent mid-play changes.
- **Messy Track mixing.** Rotating Tracks is fine — but not mid-line and not when a Track is locked or defensive. ($/unit is now global, so mismatched sizing is no longer possible.)
- **Override mode.** If you’re routinely ignoring cadence limits, tone shifts, or locks because you’re “feeling it,” the model can’t protect you.
""")
    st.markdown(
        """
<div class="callout">
<b>Bottom line:</b> the edge comes from limiting your “human error surface area.”  
The moment you try to outsmart the framework, the edge disappears and you’re just another gambler.
</div>
""",
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

# ------------------------ How to Maximize This ------------------------
with st.container():
    st.markdown('<div class="hiw-card">', unsafe_allow_html=True)
    st.markdown('<div class="hiw-h">How to Maximize This</div>', unsafe_allow_html=True)
    st.markdown("""
This model is built to produce **clean, repeatable, compounding cash flow** — but only when you run it the way it’s designed.  
Here’s how to get the absolute most out of it:

---

<div style="font-weight:700; font-size:1rem; margin-top:12px;">1. Treat the Next Bet card as law.</div>
No freelancing, no “improvements,” no side-bets.<br>

- If the engine says <b>3u Banker</b>, it’s <b>3u Banker</b> — nothing else.<br>
- Trying to outsmart the engine is how people torch good weeks.

---

<div style="font-weight:700; font-size:1rem; margin-top:12px;">2. Run full lifecycles, not hero sessions.</div>
The power comes from the model’s structure:

- Line → Session → Week  
- Trim → Kicker → Stops → Caps → Guards  

The compounding happens when you **stack many clean weeks**, not one adrenaline session.

---

<div style="font-weight:700; font-size:1rem; margin-top:12px;">3. Respect cadence — it’s already aggressive.</div>

- **6 sessions/day** per Track  
- **2 lines/session** per Track  

Trying to force extra volume only adds unnecessary volatility.  
Hitting cadence consistently is more than enough to maximize output.

---

<div style="font-weight:700; font-size:1rem; margin-top:12px;">4. Use Speed / Super Speed Baccarat to compress time.</div>

- The model’s main constraint is <b>time</b> — not shoe selection.  
- Speed tables let you finish sessions in a fraction of the time without changing the rules.  
- This makes it easier to run the system <b>calmly</b> and <b>consistently</b>, without getting mentally dragged into the casino “experience.”

<div class="callout small" style="margin-top:10px;">
<b>Mindset:</b> treat this like executing reps in the gym — clean form, no ego, no improvising.<br>
Speed helps you stay detached and prevents “boredom freelancing.”
</div>

---

<div style="font-weight:700; font-size:1rem; margin-top:12px;">5. Play multiple Tracks the right way.</div>
This is where total profit comes from — but only with discipline:

- Treat each Track like its own business unit  
- **Never overlap lines** between Tracks  
- Finish a line before rotating to another Track  
- **$/unit is global** — the app enforces this automatically 
- Favor Tracks in Neutral or Green tone  
- Let Red Tracks cool off — that’s the purpose of defensive mode  

<div class="callout small" style="margin-top:10px;">
<b>What that actually means:</b><br>
When a Track turns red (~-85u), the engine is detecting fragility and volatility you can’t see.  
Defensive mode automatically tightens exposure, closes lines faster, and caps the week if needed.  
<b>You don’t change anything manually — just keep following the cadence.</b>  
The app handles the brake pedal for you.<br><br>

<b>Tone Map:</b><br>
🟩 <b>Green = Build</b> (week is strong, behavior tightens, profits bank fast)<br>
⚪ <b>Neutral = Normal</b> (standard behavior)<br>
🟥 <b>Red = Protect</b> (fragility detected; defensive behavior auto-engages)

<br><br>
Clean rotation = more sessions, more capped weeks, more consistent cash flow.
</div>

---

<div style="font-weight:700; font-size:1rem; margin-top:12px;">6. Follow tone and trust the defensive behavior.</div>

- **Green = Build**  
- **Neutral = Normal**  
- **Red = Protect**  

Good weeks take care of themselves.  
The biggest long-term gains come from **low, controlled red weeks**, not monster green ones.  
Defense is where the edge is created.

---

<div style="font-weight:700; font-size:1rem; margin-top:12px;">7. Use Testing Mode intentionally.</div>
Use it to:

- shake off rust  
- test a casino  
- verify timing  

When Testing is OFF, commit to perfect execution.

---

<div style="font-weight:700; font-size:1rem; margin-top:12px;">8. Follow the bankroll plan exactly.</div>

- Keep **Active vs Strategic Reserve** split as shown  
- Top up from Reserve only  
- Never mix bankrolls across Tracks  
- Never change $/unit on one Track without changing all Tracks  

This preserves the downside ceiling and protects compounding.

---

<div style="font-weight:700; font-size:1rem; margin-top:12px;">9. Step up slowly and only when justified.</div>

Increase $/unit only when:

1. You’ve had **2+ recent green weeks**  
2. Your bankroll is above the target Total (u)  
3. No Track is in Defensive Mode  

Then step up in **small increments** so your risk curve stays stable.

---

<div style="font-weight:700; font-size:1rem; margin-top:12px;">10. Keep your mental game boring.</div>

- No table-hunting  
- No pattern-hunting  
- No chasing streaks  

Your edge comes from structure — not prediction.
""", unsafe_allow_html=True)

    st.markdown("""
<div class="callout">
<b>Bottom line:</b> the engine does the heavy lifting — your job is to execute cleanly.  
Run disciplined Tracks, hit your cadence, rotate smartly, and let weekly caps do their job.  
That’s how you unlock the full cash-flow profile of the model.
</div>
""", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

# ------------------------ Modes & What Counts Toward Stats ------------------------
with st.container():
    st.markdown('<div class="hiw-card">', unsafe_allow_html=True)
    st.markdown('<div class="hiw-h">Modes & What Counts Toward Stats</div>', unsafe_allow_html=True)
    st.markdown(
        """
<span class="badge">Live</span> Real play. <b>Counts</b> toward all P/L, streaks, cadence, and week logic.  
<span class="badge">Testing</span> Safety switch. <b>Does not count</b> toward any P/L or limits (ignored in stats).  
<span class="badge">Simulation</span> Sandboxed runs. <b>Does not count</b> toward any live stats or week logic.
""",
        unsafe_allow_html=True,
    )
    st.markdown("""
**What’s included in stats:**  
- Only **Live** entries with **Testing Mode OFF** are included in **Overall / Monthly / Weekly / Daily P/L**.  
- Testing Mode or Sim runs are excluded everywhere (dashboards, admin, “Last played”).  
- Time windows for stats are based on your local time.
""")
    st.markdown("</div>", unsafe_allow_html=True)

# ------------------------ Weekly Tone Triggers ------------------------
with st.container():
    st.markdown('<div class="hiw-card">', unsafe_allow_html=True)
    st.markdown('<div class="hiw-h">Weekly Tone Triggers</div>', unsafe_allow_html=True)
    st.markdown("""
- 🟩 **Green Week Trigger** → around **+160u**.  
  - Tightens behavior and lowers the working cap to **+300u** on that Track.  
  - Signals "good week in progress, protect it."  

- 🟥 **Red Week Stabilizer Trigger** → around **−85u**.  
  - Flips the week into **defensive mode** (tighter exposure, faster closures).  
  - Does NOT immediately close the week — the week can still recover.  
  - Closes as a **controlled red (−60 to −90u)** only if conditions worsen:  
    - 3+ consecutive losing sessions, or  
    - Elevated fragility (high trim rate), or  
    - Sustained defensive mode with no improvement  
  - This prevents small dips from spiraling toward the −400u guard.

- ⚠️ **Soft Shield** → activates at **−300u** week P/L.  
  - Emergency damage control when a week is going very badly.  
  - **Tightens session stop** from −60u to **−40u** (smaller per-session losses).  
  - **Forces Defensive Mode always active** (softer seed, reduced bet scaling).  
  - Exits when week P/L recovers to **−200u** (sticky/hysteresis).  
  - Soft Shield does NOT affect Smart Trim τ threshold — that remains session-based.

All triggers fire automatically and generate notifications so you know exactly when tone shifts.
""")
    st.markdown(
        """
<div class="callout">
<b>Why tone exists:</b> instead of treating every hand the same, the engine respects the bigger picture.
When the week is trending well, it tightens and protects.  
When it’s going badly, it gets defensive early so you live to fight the next week.
</div>
""",
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

# ------------------------ Live Tone & Caps (Current Track Snapshot) ------------------------
with st.container():
    st.markdown('<div class="hiw-card">', unsafe_allow_html=True)
    st.markdown('<div class="hiw-h">Live Tone & Caps (Current Track)</div>', unsafe_allow_html=True)
    st.markdown(
        f"""- **Current Tone:** **{tone_name}**  
- **Cap target:** **+{cap_target}u**  
- **Defensive Mode:** **{def_mode}**  
- **Soft Shield:** **{soft_shield_mode}**"""
    )
    st.markdown("""
These are pulled from your **active Track** on the Tracker page.  
Tone and caps are Track-specific — switching Tracks can show different tone / cap states.
""")
    st.markdown("</div>", unsafe_allow_html=True)

# ------------------------ Playing Multiple Tracks & Bankroll Requirements ------------------------
with st.container():
    st.markdown('<div class="hiw-card">', unsafe_allow_html=True)
    st.markdown('<div class="hiw-h">Playing Multiple Tracks & Bankroll Requirements</div>', unsafe_allow_html=True)
    st.markdown("""
**Tracks are independent.**  
Each Track has its own cadence, line state, tone, and week logic. When you switch Tracks from the header/sidebar,
you’re just changing which engine you’re driving — the others keep their state until you return.

Because weeks end via **weekly lock conditions**, it’s completely normal for:
- **Track A** to be on **Week 7**
- **Track B** to be on **Week 3**

Each Track advances weeks on its **own timeline**, based solely on when that Track hits a cap, guard, or stabilizer.

**Clean multi-track rules:**  
- Play **one Track at a time**; finish the current **line** before switching.  
- **$/unit is global** — set once in Settings or on the Tracker and it applies to all Tracks automatically.  
- Don't mix bankrolls:
  - **Active (on-platform)** = funds in your playing account (e.g., Stake).  
  - **Strategic Reserve (off-platform)** = funds in bank / exchange / wallet used to top up, not punt.
""")

    st.markdown("""
**Recommended unit structure:**
""")
    data = [
        {
            "Tracks": "1 Track",
            "Total Units": 2000,
            "Active": 1000,
            "Reserve": 1000,
            "Bust Odds — Active": "1 / 5,556",
            "Bust Odds — Reserve": "1 / 66,667",
            "Bust Odds — Total": "1 / 166,667",
        },
        {
            "Tracks": "2 Tracks",
            "Total Units": 2800,
            "Active": 1200,
            "Reserve": 1600,
            "Bust Odds — Active": "1 / 7,144",
            "Bust Odds — Reserve": "1 / 100,000",
            "Bust Odds — Total": "1 / 166,667",
        },
        {
            "Tracks": "3 Tracks",
            "Total Units": 3400,
            "Active": 1200,
            "Reserve": 2200,
            "Bust Odds — Active": "1 / 4,762",
            "Bust Odds — Reserve": "1 / 100,000",
            "Bust Odds — Total": "1 / 166,667",
        },
    ]
    st.dataframe(data, use_container_width=True, hide_index=True)

    st.markdown(
        """
<div class="small">
  <ul>
    <li><b>Active (on-platform)</b> = units you keep in the live account.</li>
    <li><b>Strategic Reserve (off-platform)</b> = units you hold off-platform for safety and top-ups.</li>
    <li><b>Bust Odds</b> = chance of full depletion before recovery, under engine assumptions.</li>
    <li>Reserves scale with Track count so a bad run on one Track doesn’t threaten the others.</li>
  </ul>
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown("### Optimal Rotation Playbook")
    st.markdown("""
- **When a LINE ends:** continue on the same Track if LOD allows.  
- **When a SESSION ends:** bank, then either continue on that Track or rotate.  
- **When the DAY is maxed on that Track (nb lock):** switch to another Track with sessions available.  
- **When the WEEK closes on a Track:** start the next week on that Track when you’re ready, and finish other Tracks’ weeks in their own time.

**Priority rules:**  
1. Never overlap lines.  
2. Favor Tracks in healthy tone.  
3. Rotate A → B → C evenly over time.  
4. Keep $/unit identical across Tracks.
""")

    st.markdown("</div>", unsafe_allow_html=True)

# ------------------------ Bankroll Calculator ------------------------
with st.container():
    st.markdown('<div class="hiw-card">', unsafe_allow_html=True)
    st.markdown('<div class="hiw-h">Bankroll Calculator</div>', unsafe_allow_html=True)

    default_unit = float(st.session_state.get("unit_value", 1.0))
    col1, _ = st.columns([1, 2])
    with col1:
        unit_input = st.number_input(
            "$/unit",
            min_value=0.1,
            step=0.5,
            value=round(default_unit, 2),
        )

    reqs = [
        ("1 Track", 1000, 1000, 2000),
        ("2 Tracks", 1200, 1600, 2800),
        ("3 Tracks", 1200, 2200, 3400),
    ]
    rows = []
    for label, a, r, t in reqs:
        rows.append({
            "Tracks": label,
            "Active (u)": f"{a:,}",
            "Reserve (u)": f"{r:,}",
            "Total (u)": f"{t:,}",
            "Active ($)": f"${a * unit_input:,.0f}",
            "Reserve ($)": f"${r * unit_input:,.0f}",
            "Total ($)": f"${t * unit_input:,.0f}",
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)
    st.markdown(
        """
<div class="small">
• Converts fixed unit requirements using your chosen <b>$/unit</b>.  
• Keep <b>$/unit consistent across Tracks</b>.  
• Change the global unit size in <b>Settings</b> when you actually step up.
</div>
""",
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

# ------------------------ Casino Bonuses & Rakeback ------------------------
with st.container():
    st.markdown('<div class="hiw-card">', unsafe_allow_html=True)
    st.markdown('<div class="hiw-h">Casino Bonuses & Rakeback</div>', unsafe_allow_html=True)
    st.markdown("""
Bonuses and rakeback are **free edge** — take full advantage of them.

**Why they matter:**
- They're effectively **risk-free additions** to your bankroll.
- Over time, consistent bonus collection compounds significantly.
- They create a buffer that absorbs variance and accelerates scaling.

**Claim everything available:**  
- Weekly and monthly bonuses (reloads, cashback)  
- Rakeback from volume  
- VIP perks, loyalty rewards, promotional offers

**How to allocate (recommended split):**  
- **50% → Strategic Reserve** (safety buffer, top-up fuel)  
- **50% → Active** (session fuel, or save toward $/unit step-up)

Alternatively, use bonuses for:
- **Safety:** 100% to Reserve if your bankroll is under target  
- **Scaling:** Save toward the next $/unit step-up  
- **Profit:** Withdraw as pure profit once bankroll targets are met  

**Step-up rule:** only increase $/unit when:  
1. You've had **2+ recent green weeks**, and  
2. Your bankroll is above the target **Total (u)** for your Track count, and  
3. No Track is in **Defensive Mode**.  

Then step up in small increments (for example, `$0.50 → $1.00` per unit). The app enforces global $/unit across all Tracks automatically.
""")
    st.markdown("""
<div class="callout">
<b>Don't leave money on the table:</b> Most players underutilize bonuses.  
Treat bonus collection as part of your operating discipline — it's free fuel for compounding.
</div>
""", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
