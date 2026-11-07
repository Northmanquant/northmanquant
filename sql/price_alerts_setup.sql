-- ============================================================
-- هشدارهای قیمتی — یک‌بار در Supabase → SQL Editor اجرا شود.
-- هر ردیف = هشدارهای یک «نماد» (scope کلید اصلی است)
-- هم‌تراز sql/chart_sync_setup.sql — اجرای مجدد بی‌خطر است (if not exists)
-- ============================================================
create table if not exists price_alerts (
  scope      text primary key,          -- "BTC/USDT" · "EURUSD" · "فولاد"
  alerts     jsonb,                     -- لیست هشدارها (همان قالب localStorage چارت)
  updated_by text,                      -- شناسه‌ی دستگاه/چکر آخرین تغییر
  updated_at timestamptz default now()
);

alter table price_alerts enable row level security;

drop policy if exists "alerts read"   on price_alerts;
drop policy if exists "alerts insert" on price_alerts;
drop policy if exists "alerts update" on price_alerts;

create policy "alerts read"   on price_alerts for select to anon, authenticated using (true);
create policy "alerts insert" on price_alerts for insert to anon, authenticated with check (true);
create policy "alerts update" on price_alerts for update to anon, authenticated using (true) with check (true);

-- زمان last-writer-wins همیشه از سرور بیاید (نه ساعت مرورگر)
create or replace function price_alerts_touch() returns trigger as $$
begin
  new.updated_at = now();
  return new;
end $$ language plpgsql;

drop trigger if exists price_alerts_touch_trg on price_alerts;
create trigger price_alerts_touch_trg
  before insert or update on price_alerts
  for each row execute function price_alerts_touch();

create index if not exists price_alerts_updated_idx on price_alerts (updated_at desc);
