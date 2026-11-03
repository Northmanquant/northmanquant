-- ============================================================
-- Agent Arena (میدان ایجنت‌ها) — جدول معاملات لیگ کاغذی
-- یک‌بار در Supabase → SQL Editor اجرا شود.
-- ============================================================
create table if not exists arena_trades (
  id         text primary key,
  agent      text,
  symbol     text,
  status     text default 'open',   -- open | closed
  data       jsonb,                 -- تمام جزئیات معامله
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

alter table arena_trades enable row level security;

drop policy if exists "arena read"   on arena_trades;
drop policy if exists "arena insert" on arena_trades;
drop policy if exists "arena update" on arena_trades;

create policy "arena read"   on arena_trades for select to anon, authenticated using (true);
create policy "arena insert" on arena_trades for insert to anon, authenticated with check (true);
create policy "arena update" on arena_trades for update to anon, authenticated using (true) with check (true);

create index if not exists arena_trades_status_idx on arena_trades (status);
create index if not exists arena_trades_agent_idx  on arena_trades (agent);

-- ============================================================
-- هشدارهای میدان — باز/بسته‌شدن معامله، تغییر رژیم بازار
-- (اجرای مجدد این فایل بی‌خطر است — if not exists)
-- ============================================================
create table if not exists arena_alerts (
  id         text primary key,          -- op:{trade_id} | cl:{trade_id} | rg:{dir}:{ts}
  kind       text,                      -- open | close | regime | bot (bot = نشانگر ضدتکرار بات تلگرام)
  symbol     text,
  data       jsonb,                     -- تمام جزئیات هشدار
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

alter table arena_alerts enable row level security;

drop policy if exists "alerts read"   on arena_alerts;
drop policy if exists "alerts insert" on arena_alerts;

create policy "alerts read"   on arena_alerts for select to anon, authenticated using (true);
create policy "alerts insert" on arena_alerts for insert to anon, authenticated with check (true);

create index if not exists arena_alerts_created_idx on arena_alerts (created_at);
create index if not exists arena_alerts_kind_idx    on arena_alerts (kind);
