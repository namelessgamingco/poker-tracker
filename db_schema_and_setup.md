# Canvas 4 — Database Schema + Setup Guide (REBUILD)

This canvas contains the **exact SQL** for Supabase and a **click-by-click setup guide**.

---

## 1) SQL — paste in Supabase → SQL → New Query → **Run**
```sql
-- Enable UUID helper (safe to rerun)
create extension if not exists pgcrypto;

-- =================
-- TABLES
-- =================
create table if not exists public.profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  email text unique,
  is_admin boolean not null default false,
  allowed boolean not null default true,
  created_at timestamptz not null default now()
);

create table if not exists public.sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  started_at timestamptz not null default now(),
  ended_at timestamptz,
  session_pnl_units numeric not null default 0,
  is_test boolean not null default false
);

create table if not exists public.weeks (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  week_start_date date not null,
  week_pnl_units numeric not null default 0,
  is_test boolean not null default false
);

-- =================
-- RLS
-- =================
alter table public.profiles enable row level security;
alter table public.sessions enable row level security;
alter table public.weeks enable row level security;

-- =================
-- POLICIES (drop + create)
-- =================
-- PROFILES
drop policy if exists "read own profile or admin any" on public.profiles;
create policy "read own profile or admin any"
on public.profiles
for select
to authenticated
using (
  auth.uid() = user_id
  or exists (
    select 1 from public.profiles p
    where p.user_id = auth.uid() and p.is_admin = true
  )
);

drop policy if exists "admin update profiles" on public.profiles;
create policy "admin update profiles"
on public.profiles
for update
to authenticated
using (
  exists (
    select 1 from public.profiles p
    where p.user_id = auth.uid() and p.is_admin = true
  )
);

drop policy if exists "admin insert profiles" on public.profiles;
create policy "admin insert profiles"
on public.profiles
for insert
to authenticated
with check (
  exists (
    select 1 from public.profiles p
    where p.user_id = auth.uid() and p.is_admin = true
  )
);

-- (Optional) also allow a signed-in user to insert their own profile row
-- Useful if you want profiles to auto-provision on first login
-- You can keep both policies; RLS will allow insert if any with-check passes

drop policy if exists "user insert own profile" on public.profiles;
create policy "user insert own profile"
on public.profiles
for insert
to authenticated
with check (user_id = auth.uid());

-- SESSIONS
drop policy if exists "read own sessions or admin any" on public.sessions;
create policy "read own sessions or admin any"
on public.sessions
for select
to authenticated
using (
  user_id = auth.uid()
  or exists (
    select 1 from public.profiles p
    where p.user_id = auth.uid() and p.is_admin = true
  )
);

drop policy if exists "write own sessions" on public.sessions;
create policy "write own sessions"
on public.sessions
for insert
to authenticated
with check (user_id = auth.uid());

drop policy if exists "update own sessions" on public.sessions;
create policy "update own sessions"
on public.sessions
for update
to authenticated
using (user_id = auth.uid());

-- WEEKS
drop policy if exists "read own weeks or admin any" on public.weeks;
create policy "read own weeks or admin any"
on public.weeks
for select
to authenticated
using (
  user_id = auth.uid()
  or exists (
    select 1 from public.profiles p
    where p.user_id = auth.uid() and p.is_admin = true
  )
);

drop policy if exists "write own weeks" on public.weeks;
create policy "write own weeks"
on public.weeks
for insert
to authenticated
with check (user_id = auth.uid());

drop policy if exists "update own weeks" on public.weeks;
create policy "update own weeks"
on public.weeks
for update
to authenticated
using (user_id = auth.uid());
```

---

## 2) Supabase setup — exact clicks

1. **Auth → Providers** → Turn **Email** ON (you can disable email confirmations during local tests).
2. **Auth → Users** → (Optional) **Add User** with your email+password to seed an admin.
3. **Table Editor** → confirm `profiles`, `sessions`, `weeks` exist.
4. **Table Editor → profiles** → if you created a user in step 2, insert a row with that user’s UUID as `user_id`, your email, `is_admin=true`, `allowed=true`.

---

## 3) Local environment quick recap (Mac)

```bash
# From your project folder
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt   # or: pip install streamlit pandas python-dotenv supabase

# Put your Supabase creds in .env
cat > .env <<'EOF'
SUPABASE_URL=https://YOUR-PROJECT.supabase.co
SUPABASE_ANON_KEY=YOUR_ANON_KEY
STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
EOF

# Run
streamlit run app.py
```

---

## 4) Final checklist

- [ ] You can **sign up / sign in**.
- [ ] Your profile row exists and `allowed=true`.
- [ ] You toggled `is_admin=true` for your account (either by insert or editing the row).
- [ ] Tracker page updates **Session P/L** and **Week P/L** in units when you click Win/Loss/Tie.
- [ ] Session auto-closes at **+30u** or **−60u** (stub behavior).
- [ ] Week auto-closes at **+400u** or **−400u** (stub behavior).
- [ ] Testing Mode toggle is visible.

> Next iteration: swap `engine.py` for your full Diamond+ engine and wire DB writes (hands/sessions/weeks) so Admin reports populate.

