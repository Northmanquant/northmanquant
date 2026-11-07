# -*- coding: utf-8 -*-
"""چکر سمت سرور هشدارهای قیمتی — لایه‌ی پشتیبان وقتی اپ باز نیست.
=================================================================
هر اجرا:
  ۱) همه‌ی ردیف‌های جدول `price_alerts` از Supabase خوانده می‌شود.
  ۲) برای هر نماد با هشدار فعال، قیمت آخر گرفته می‌شود:
       • کریپتو  → کندل ۱ دقیقه‌ی Binance (core.crypto_candles)
       • فارکس   → کوتی یاهو (core.forex.fetch_quote)
       • بورس ایران → فعلاً سمت سرور پشتیبانی نمی‌شود (فقط چارت/اپ)
  ۳) هشدار «بالای/زیر» برخورده → غیرفعال می‌شود (active=false) و
     با یک پیام تلگرام جمع برای مالک اعلام می‌گردد.
  ۴) ردیف‌های تغییرکرده به Supabase برمی‌گردند — چکر بعدی دوباره اعلام نمی‌کند.

اجرا: `python -m scripts.check_price_alerts` یا `python scripts/check_price_alerts.py`
Secrets لازم: SUPABASE_URL، SUPABASE_KEY (+ اختیاری TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID)
اصل طراحی: fail-soft — هر خطا فقط لاگ می‌شود، اجرا همیشه با 0 تمام می‌کند
(مثل بات تلگرام؛ Actions نباید به‌خاطر نوسان شبکه قرمز شود).
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.arena_store import _secrets_get

TABLE = "price_alerts"
MAX_ALERTS = 100
_MAX_SYMBOL_PER_RUN = 25          # سقف فراخوانی شبکه در هر اجرا


def _log(msg: str) -> None:
    print(msg, flush=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fetch_json(url: str, timeout: float = 10.0) -> Optional[Any]:
    """GET ساده با urllib — هر خطایی = None."""
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={"User-Agent": "northmanquant/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            import json
            return json.loads(r.read().decode("utf-8"))
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------- قیمت‌ها
def _crypto_price(symbol: str) -> Optional[float]:
    """آخرین قیمت کریپتو از کندل ۱ دقیقه‌ی Binance (میرور بدون محدودیت جغرافیایی)."""
    try:
        from core.crypto_candles import fetch_candles
        base = str(symbol or "").split("/")[0].split("-")[0].strip().upper()
        if not base:
            return None
        rows = fetch_candles(base, "1min")
        if not rows:
            return None
        close = float(rows[-1][4])
        return close if close == close and close > 0 else None
    except Exception:  # noqa: BLE001
        return None


def _fx_price(symbol: str) -> Optional[float]:
    """آخرین قیمت جفت‌ارز از یاهو."""
    try:
        from core.forex import fetch_quote
        q = fetch_quote(str(symbol or ""))
        if not q:
            return None
        for k in ("price", "last", "close"):
            v = q.get(k)
            if v is not None:
                try:
                    f = float(v)
                    if f == f and f > 0:
                        return f
                except (TypeError, ValueError):
                    continue
        return None
    except Exception:  # noqa: BLE001
        return None


def _is_fx_symbol(symbol: str) -> bool:
    """جفت‌ارز: دقیقاً ۶ حرف لاتین (EURUSD, USDJPY…) — مثل yahoo_symbol در core.forex."""
    import re
    return bool(re.match(r"^[A-Z]{6}$", str(symbol or "").upper().replace("/", "")))


def _is_crypto_symbol(symbol: str) -> bool:
    """کریپتو: حروف/عدد لاتین با پسوند استیبل (BTC/USDT، ETHUSDC، DOGE-USDT…)."""
    import re
    s = str(symbol or "").upper().replace("/", "").replace("-", "")
    return bool(re.match(r"^[A-Z0-9]{2,10}(USDT|USDC|USD|FDUSD|BUSD)$", s)) and not _is_fx_symbol(symbol)


def price_for(symbol: str) -> Optional[float]:
    s = str(symbol or "").upper()
    if _is_crypto_symbol(s):
        return _crypto_price(s)
    if _is_fx_symbol(s):
        return _fx_price(s)
    return None          # بورس ایران و نمادهای ناشناخته — فقط سمت چارت


# ---------------------------------------------------------------- جدول
def _load_rows(client) -> List[Dict[str, Any]]:
    res = (client.table(TABLE)
           .select("scope, alerts, updated_by")
           .limit(200).execute())
    return list(res.data or [])


def _save_row(client, scope: str, alerts: List[Dict[str, Any]], by: str) -> bool:
    try:
        (client.table(TABLE)
         .update({"alerts": alerts, "updated_by": by})
         .eq("scope", scope).execute())
        return True
    except Exception as e:  # noqa: BLE001
        _log(f"  ⚠ ذخیره‌ی {scope} ناموفق: {str(e)[:120]}")
        return False


def _telegram(text: str) -> bool:
    token = _secrets_get("TELEGRAM_BOT_TOKEN")
    chat = _secrets_get("TELEGRAM_CHAT_ID")
    if not (token and chat):
        return False
    try:
        from core.tg_bot import _send_chat
        return bool(_send_chat(token, chat, text))
    except Exception:  # noqa: BLE001
        return False


def _fmt(v: Any) -> str:
    try:
        f = float(v)
        return f"{f:,.6g}"
    except (TypeError, ValueError):
        return str(v)


# ---------------------------------------------------------------- اصلی
def run() -> Tuple[int, int, int]:
    """بررسی همه‌ی ردیف‌ها → (scope بررسی‌شده، هشدار فعال، هشدار تریگرشده)."""
    url = _secrets_get("SUPABASE_URL")
    key = _secrets_get("SUPABASE_KEY") or _secrets_get("SUPABASE_ANON_KEY")
    if not (url and key):
        _log("⏭ SUPABASE_URL/KEY ست نیست — چکر هشدار رد شد")
        return (0, 0, 0)
    try:
        from supabase import create_client  # type: ignore
        client = create_client(url, key)
    except Exception as e:  # noqa: BLE001
        _log(f"⚠ اتصال Supabase نشد: {str(e)[:120]}")
        return (0, 0, 0)

    try:
        rows = _load_rows(client)
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        if "PGRST205" in msg or "Could not find the table" in msg or "does not exist" in msg.lower():
            _log("⏭ جدول price_alerts هنوز ساخته نشده — یک‌بار sql/price_alerts_setup.sql را اجرا کن")
        else:
            _log(f"⚠ خواندن جدول ناموفق: {msg[:150]}")
        return (0, 0, 0)

    checked = active_n = triggered = 0
    tg_lines: List[str] = []
    for row in rows[:_MAX_SYMBOL_PER_RUN]:
        scope = str(row.get("scope") or "").strip()
        alerts = row.get("alerts")
        if not scope or not isinstance(alerts, list):
            continue
        actives = [a for a in alerts if isinstance(a, dict) and a.get("active")]
        if not actives:
            continue
        price = price_for(scope)
        if price is None:
            _log(f"  • {scope}: قیمت گرفتن نشد — این دور رد شد ({len(actives)} هشدار فعال)")
            continue
        checked += 1
        changed = False
        for a in actives:
            try:
                ap = float(a.get("price"))
            except (TypeError, ValueError):
                continue
            hit = (price <= ap) if str(a.get("dir")) == "below" else (price >= ap)
            if not hit:
                continue
            a["active"] = False
            a["triggered_at"] = _now_iso()
            a["trigger_price"] = price
            triggered += 1
            changed = True
            arrow = "⬇ زیر" if str(a.get("dir")) == "below" else "⬆ بالای"
            tg_lines.append(f"🔔 <b>{scope}</b> {arrow} {_fmt(ap)} رسید\n   قیمت الان: <b>{_fmt(price)}</b>")
        active_n += len(actives)
        if changed:
            if _save_row(client, scope, alerts[:MAX_ALERTS], "checker"):
                _log(f"  ✓ {scope}: {triggered} هشدار تریگر شد — قیمت {_fmt(price)}")

    if tg_lines:
        text = ("🚨 <b>هشدار قیمتی</b>\n\n" + "\n".join(tg_lines[:20])
                + f"\n\n🕐 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC")
        if _telegram(text):
            _log(f"  📨 تلگرام ارسال شد ({len(tg_lines)} هشدار)")
        else:
            _log("  ⚠ تلگرام ارسال نشد (توکن/چت ست نیست یا خطا) — هشدارها در جدول غیرفعال شده‌اند")
    return (checked, active_n, triggered)


def main() -> int:
    _log("🔔 چکر هشدار قیمتی — شروع")
    try:
        checked, active_n, triggered = run()
        _log(f"✅ تمام شد — {checked} نماد بررسی شد، {active_n} هشدار فعال، {triggered} تریگر")
    except Exception as e:  # noqa: BLE001 — fail-soft مطلق
        _log(f"⚠ خطای غیرمنتظره (غیربحرانی): {str(e)[:200]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
