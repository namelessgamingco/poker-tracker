# Canvas 1 — Core Project Files (REBUILD)

This canvas contains the **top-level files** you’ll copy into your project root.

## 📁 File tree

```
.
├── README.md
├── requirements.txt
├── .streamlit/
│   └── config.toml
├── .env.sample
├── supabase_client.py   # in Canvas 2
├── auth.py              # in Canvas 2
├── engine.py            # in Canvas 2
├── app.py               # in Canvas 2
├── pages/               # in Canvas 3
└── db/schema.sql        # in Canvas 4
```

---

## README.md

```markdown
# Bacc Core Tracker (Streamlit + Supabase)

Secure, multi-user baccarat tracker implementing the **Diamond+ core config** scaffolding, Testing Mode, Reset Week (Admin), and an **Admin Console** for user management and P/L summaries.

## Features
- Supabase Auth (email/password or magic link) with profiles (is_admin, allowed)
- Testing Mode toggle (excludes test rows from P/L)
- Week lifecycle: auto-close at +400 / +300 / +160 / −85 / −400; auto-start next week
- Session goals/stops (+30/−60 units)
- Admin Console: list users, grant/revoke access, promote/demote admin, view daily/weekly/monthly/lifetime P/L
- True net P/L accounting (Banker +0.95×stake, −1 on loss, ties push). Stakes rounded up to whole $

> **Note**: `engine.py` (in Canvas 2) ships as a stub so you can run the app now; later replace TODOs with your full Diamond+ engine (Smart-Trim, Glide, Trailing, Line Cap +180, small-week logic, Defensive Mode).

## Quickstart
1. **Create Supabase project** → Settings → API → copy Project URL + anon key.
2. **Run schema**: paste `db/schema.sql` (Canvas 4) into Supabase SQL editor → Run.
3. **Create first user** via app, then in Supabase → Table Editor → `profiles` set your user `is_admin=true`.
4. **Local env**: copy `.env.sample` → `.env` and fill in URL/key.
5. **Install**: `pip install -r requirements.txt`
6. **Run**: `streamlit run app.py`

## Deploy
- **Streamlit Community Cloud** or your own VPS.
- Set env vars to match `.env.sample`.

## Security
- Row Level Security enabled everywhere. Users see only their data; Admins see all.
- Set `profiles.allowed=false` to revoke access.
```

---

## requirements.txt

```txt
streamlit==1.38.0
pandas==2.2.2
python-dotenv==1.0.1
supabase==2.6.0
```

---

## .streamlit/config.toml

```toml
[theme]
base = "dark"
primaryColor = "#7c3aed"
backgroundColor = "#0b0f19"
secondaryBackgroundColor = "#121829"
textColor = "#f3f4f6"
```

---

## .env.sample

```env
SUPABASE_URL=https://YOUR-PROJECT.supabase.co
SUPABASE_ANON_KEY=YOUR_ANON_KEY
# Optional: set to true in hosting if you want Streamlit to trust proxies
STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
```

---

### Next

When you’ve **downloaded this canvas** (••• → Download → Markdown), say “Canvas 2” and I’ll regenerate **Canvas 2 (Python Core)**: `supabase_client.py`, `auth.py`, `engine.py`, `app.py`.

