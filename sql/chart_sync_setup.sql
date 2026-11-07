-- ============================================================
-- همگام‌سازی ابری رسم‌های چارت (سبک تریدینگ‌ویو)
-- یک‌بار در Supabase → SQL Editor اجرا شود.
-- هر ردیف = رسم‌های یک «نماد:تایم‌فریم» (scope کلید اصلی است)
-- اجرای مجدد این فایل بی‌خطر است — if not exists
-- ============================================================
create table if not exists chart_drawings (
  scope      text primary key,          -- "BTCUSDT:15m" · "EURUSD:1H" · "فولاد:1D"
  symbol     text,
  timeframe  text,
  drawings   jsonb,                     -- لیست رسم‌ها (همان قالب localStorage چارت)
  updated_by text,                      -- شناسه‌ی دستگاه/مرورگر آخرین تغییر
  updated_at timestamptz default now()
);

alter table chart_drawings enable row level security;

drop policy if exists "drawings read"   on chart_drawings;
drop policy if exists "drawings insert" on chart_drawings;
drop policy if exists "drawings update" on chart_drawings;

create policy "drawings read"   on chart_drawings for select to anon, authenticated using (true);
create policy "drawings insert" on chart_drawings for insert to anon, authenticated with check (true);
create policy "drawings update" on chart_drawings for update to anon, authenticated using (true) with check (true);

-- زمان last-writer-wins همیشه از سرور بیاید (نه ساعت مرورگر)
create or replace function chart_drawings_touch() returns trigger as $$
begin
  new.updated_at = now();
  return new;
end $$ language plpgsql;

drop trigger if exists chart_drawings_touch_trg on chart_drawings;
create trigger chart_drawings_touch_trg
  before insert or update on chart_drawings
  for each row execute function chart_drawings_touch();

create index if not exists chart_drawings_symbol_idx on chart_drawings (symbol);
create index if not exists chart_drawings_updated_idx on chart_drawings (updated_at desc);
