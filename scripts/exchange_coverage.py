"""جابِ پوششِ اجراییِ ۸ صرافی — ضربانِ زنده‌ی داده در هر venue — NorthmanQuant
==============================================================
هر ران از «مسیرِ واقعیِ اپ» می‌رود ولی بدونِ فال‌بکِ میان‌ونکیته:
- tick    → app_base._fetch_tick_one  — چون fetch_tickِ عمومی روی خرابی/بلاکِ
            جغرافیایی به venueهای دیگر برمی‌گردد و خرابیِ یک صرافی را ماسک می‌کند.
- candles → بومی: _fetch_candles_paginated · تکمیلی (XT/LBank/KCEX): _fetch_candles_ccxt
            — چون fetch_candlesِ عمومی هم فال‌بک دارد و کندلِ venueِ دیگر برمی‌گرداند.
- coins   → fetch_top_coins (بدونِ فال‌بکِ داخلی — تک‌ونکیته).
قاعده‌ی رجیستری: لیستِ صرافی‌ها فقط از core.exchanges می‌آید (EXCHANGES_ALL = 8).

خروجی:
- core/data/exchange_coverage.json       ← آخرین وضعیت (برای داشبورد/بات)
- core/data/exchange_coverage_log.jsonl  ← یک سطر به‌ازای هر ران (تاریخچه)
- جدولِ فارسی در stdout برای لاگِ Actions

exit: 0 اگر حداقلِ یک venue سالم است · 1 اگر همه مرده‌اند (خرابیِ زیرساخت).
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

TEHRAN = timezone(timedelta(hours=3, minutes=30))
SYMBOL = "BTC-USDT"
# نمادِ کاوش و فهرستِ رله از خودِ رجیستری می‌آید — تک‌منبعِ حقیقت (PROBE_SYMBOLS / RELAY_EXCHANGES)
INTERVAL = "1hour"
LIMIT = 50
FRESH_MAX_AGE_MIN = 120          # کندلِ یک‌ساعته بالای ۲ ساعت = کهنه
CCXT_VENUES = {"XT", "LBank", "KCEX"}   # بومیِ کندل ندارند/تأییدنشده — مسیرِ CCXT

def main() -> int:
    from app_base import (  # noqa: E402 — ایمپورتِ سنگین داخلِ main
        _fetch_candles_ccxt,
        _fetch_candles_paginated,
        _fetch_tick_one,
        fetch_top_coins,
    )
    from core.exchanges import (  # noqa: E402
        EXCHANGES_ALL,
        PROBE_SYMBOLS,
        RELAY_EXCHANGES,
    )

    now = datetime.now(timezone.utc)
    venues: list[dict] = []
    print(f"== پوششِ اجراییِ صرافی‌ها — {SYMBOL} · {INTERVAL} · بدونِ فال‌بک ==")
    print(f"{'صرافی':<10}{'تیک':<22}{'کندل':<30}{'ارزها':<8}{'نمره'}")
    for ex in EXCHANGES_ALL:
        row: dict = {"name": ex, "checks_pass": 0, "checks_total": 3}
        sym = PROBE_SYMBOLS.get(ex, SYMBOL)
        # ۱) تیکِ تک‌ونکیته
        t0 = time.perf_counter()
        try:
            tick = _fetch_tick_one(ex, sym)
            ms = int((time.perf_counter() - t0) * 1000)
            price = float(tick.get("price")) if tick and tick.get("price") else None
            row.update(tick_ok=price is not None, price=price, tick_ms=ms)
        except Exception as e:  # noqa: BLE001 — گزارشِ پوشش باید هر خرابی را ببلعد
            row.update(tick_ok=False, price=None, tick_ms=int((time.perf_counter() - t0) * 1000), tick_err=str(e)[:80])
        # ۲) کندلِ تک‌ونکیته (بومی یا CCXT — بدونِ فال‌بک) · رله‌ها بدونِ کاوش ثبت می‌شوند
        c0 = time.perf_counter()
        if ex in RELAY_EXCHANGES:
            row.update(candles_ok=False, candle_rows=0, candle_age_min=None, candle_fresh=False,
                       candle_path="relay",
                       candle_note="مسیرِ مستقل ندارد — اپ کندل را از فال‌بکِ venueهای دیگر می‌چسبد (مستندِ رجیستری)")
        else:
            try:
                path = "ccxt" if ex in CCXT_VENUES else "native"
                fn = _fetch_candles_ccxt if path == "ccxt" else _fetch_candles_paginated
                df = fn(ex, sym, INTERVAL, LIMIT)
                age = None
                if df is not None and len(df) and "dt" in df.columns:
                    age = round((now - df["dt"].iloc[-1].to_pydatetime().replace(tzinfo=timezone.utc)).total_seconds() / 60, 1)
                row.update(candles_ok=df is not None and len(df) > 0, candle_rows=int(len(df)) if df is not None else 0,
                           candle_age_min=age, candle_fresh=age is not None and age <= FRESH_MAX_AGE_MIN,
                           candle_path=path, candle_ms=int((time.perf_counter() - c0) * 1000))
            except Exception as e:  # noqa: BLE001
                row.update(candles_ok=False, candle_rows=0, candle_age_min=None, candle_fresh=False,
                           candle_path=path, candle_err=str(e)[:80])
        # ۳) فهرستِ ارزها — خروجیِ واقعیِ تابع: {"gainers": df, "losers": df, "volume": df}
        try:
            coins = fetch_top_coins(ex, limit=5)
            n = len(coins.get("gainers")) if isinstance(coins, dict) and coins.get("gainers") is not None else 0
            row.update(coins_ok=n > 0, coins=n)
        except Exception as e:  # noqa: BLE001
            row.update(coins_ok=False, coins=0, coins_err=str(e)[:80])
        row["checks_pass"] = sum(bool(row.get(k)) for k in ("tick_ok", "candles_ok", "coins_ok"))
        venues.append(row)
        tick_s = f"✅ ${row.get('price'):,.2f} {row.get('tick_ms')}ms" if row.get("tick_ok") else "❌ تیک"
        cand_s = (f"✅ {row.get('candle_rows')} سطر · عمر {row.get('candle_age_min')}د · {row.get('candle_path')}"
                  if row.get("candles_ok") else "❌ کندل")
        coins_s = f"✅ {row.get('coins')}" if row.get("coins_ok") else "❌ ارزها"
        score = "کامل" if row["checks_pass"] == 3 else f"{row['checks_pass']}/3"
        print(f"{ex:<10}{tick_s:<22}{cand_s:<30}{coins_s:<8}{score}")

    ok = sum(1 for v in venues if v["checks_pass"] == 3)
    fresh = sum(1 for v in venues if v.get("candle_fresh"))
    snap = {
        "ts_utc": now.isoformat(timespec="seconds"),
        "ts_tehran": datetime.now(TEHRAN).isoformat(timespec="seconds"),
        "symbol": SYMBOL, "interval": INTERVAL,
        "coverage_pct": round(100 * ok / len(venues)),
        "fresh_candles": fresh,
        "venues": venues,
    }
    datadir = os.path.join(ROOT, "core", "data")
    os.makedirs(datadir, exist_ok=True)
    with open(os.path.join(datadir, "exchange_coverage.json"), "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False, indent=1)
    with open(os.path.join(datadir, "exchange_coverage_log.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(snap, ensure_ascii=False) + "\n")
    broken = [v["name"] for v in venues if v["checks_pass"] < 3]
    print(f"\n== جمع‌بندی == پوششِ کامل: {ok}/{len(venues)} · کندلِ تازه: {fresh}/{len(venues)}"
          + (f" · شکسته‌ها: {', '.join(broken)}" if broken else " · همه‌چیز سبز ✅"))
    return 1 if ok == 0 else 0

if __name__ == "__main__":
    sys.exit(main())
