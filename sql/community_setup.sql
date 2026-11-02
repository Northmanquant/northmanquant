-- ============================================================
-- برد تحلیل‌های اجتماعی — جدول `community_analyses`
-- یک‌بار در Supabase → SQL Editor اجرا شود.
-- اجرای مجدد این فایل بی‌خطر است (if not exists).
-- ============================================================
create table if not exists community_analyses (
  id         text primary key,        -- uuid (اپ خودش تولید می‌کند)
  created_at text,                    -- ISO-8601 UTC — اپ به‌صورت متن می‌نویسد
  symbol     text,
  timeframe  text,
  direction  text,                    -- long | short | neutral
  author     text,
  payload    jsonb                    -- تمام جزئیات تحلیل (متنی و اسکورها)
);

alter table community_analyses enable row level security;

drop policy if exists "community read"   on community_analyses;
drop policy if exists "community insert" on community_analyses;

create policy "community read"   on community_analyses for select to anon, authenticated using (true);
create policy "community insert" on community_analyses for insert to anon, authenticated with check (true);

create index if not exists community_analyses_created_idx on community_analyses (created_at desc);
create index if not exists community_analyses_symbol_idx  on community_analyses (symbol);
