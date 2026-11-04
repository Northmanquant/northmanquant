# -*- coding: utf-8 -*-
"""
core/lighter_real.py — ترید واقعی روی Lighter با SDK رسمی (lighter-sdk)
=======================================================================
این ماژول قولِ معوقِ «سفارش واقعی لایتر» را کامل می‌کند:

* SDK رسمی «lighter-sdk» (elliottech/lighter-python) — امضای L2 داخل خود SDK است.
* با **کلید API** کار می‌کند نه کلید کیف‌پول: کلید API لایتر سفارش می‌گذارد ولی
  برداشت نمی‌تواند بزند (برداشت نیاز به امضای L1 کیف‌پول دارد) — همان قانون
  طلایی «کلید فقط-ترید» که صفحه‌ی ترید مستقیم می‌گوید.
* کلیدها فقط به‌عنوان آرگومان می‌آیند؛ در هیچ خروجی/خطایی برنمی‌گردند
  (scrub) و هیچ‌جا ذخیره نمی‌شوند.

مقیاس‌بندی (از مستندات و examples رسمی):
* base_amount → عدد صحیح × ۱۰^size_decimals (مثلاً 0.1 ETH با size_decimals=4 → 1000)
* price       → عدد صحیح × ۱۰^price_decimals (مثلاً $3000 با price_decimals=2 → 300000)
* این مقیاس‌ها per-market از orderBookDetails می‌آیند (core.lighter.market_meta).

الگوی پروژه: هیچ تابعی exception به UI نمی‌اندازد — خرابی = {"ok": False, "err": ...}.
توابع خالص (scale، parse‌ها، build) با تزریق، بدون شبکه تست‌پذیرند؛ فقط
توابعِ ارسال سفارش واقعاً SDK صدا می‌زنند و در تست با ماژول فیک جایگزین می‌شوند.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.net import get_json
from core import lighter as LIT

BASE = "https://mainnet.zklighter.elliot.ai"
HEADERS = {"User-Agent": "Mozilla/5.0 (NorthmanQuant; live trading)"}
FETCH_TIMEOUT = 15.0

# حداکثر لغزش مجاز سفارش بازار (درصد) — بدترین قیمتِ قابل‌قبول از این ساخته می‌شود
MARKET_SLIPPAGE_PCT = 0.5

_Fetch = Callable[..., Any]

last_error: Optional[str] = None


def _reset_for_tests() -> None:
    global last_error
    last_error = None


# ---------------------------------------------------------------- در دسترس بودن SDK
def sdk_available() -> bool:
    """SDK رسمی نصب است؟ (لازی — فقط اولین بار import واقعی می‌شود)"""
    try:
        import lighter  # noqa: F401  (پکیج lighter-sdk از PyPI)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------- پاکسازی کلید از خطا
def scrub(text: Any, *secrets: str) -> str:
    """متن خطا بدون هیچ کلیدی — کلیدها با *** جایگزین می‌شوند."""
    s = str(text or "")
    for sec in secrets:
        if sec and len(str(sec)) >= 8:
            s = s.replace(str(sec), "***")
    return s


# ---------------------------------------------------------------- اعداد و مقیاس
def scale_value(value: float, decimals: int) -> Optional[int]:
    """مقدار اعشاری → عدد صحیح مقیاس‌شده برای تراکنش لایتر.
    ورودی نامعتبر/منفی/غیرمتناهی = None (هرگز raise نمی‌کند)."""
    try:
        x = float(value)
        d = int(decimals)
    except (TypeError, ValueError):
        return None
    if d < 0 or d > 18:
        return None
    import math
    if not math.isfinite(x) or x <= 0:
        return None
    scaled = x * (10 ** d)
    if scaled >= 2 ** 63:
        return None
    scaled_i = int(round(scaled))
    if scaled_i == 0:
        # زیرِ حدّ نمای‌پذیری این بازار — سفارش صفر معنا ندارد
        return None
    return scaled_i


def unscale_value(scaled: int, decimals: int) -> float:
    """برعکسِ scale_value — برای نمایش (پوزیشن‌ها و قیمت‌های حساب)."""
    try:
        return float(scaled) / (10 ** int(decimals))
    except (TypeError, ValueError, OverflowError):
        return 0.0


def client_order_index() -> int:
    """شناسه‌ی یکتای سمت-کلاینت برای هر سفارش (میلی‌ثانیه — در عمل یکتا)."""
    return int(time.time() * 1000) % (10 ** 12)


def worst_price(side: str, last_price: float, slippage_pct: float = MARKET_SLIPPAGE_PCT) -> Optional[float]:
    """بدترین قیمتِ قابل‌قبول سفارش بازار (سپر لغزش): خرید = بالاتر، فروش = پایین‌تر."""
    try:
        p = float(last_price)
        s = float(slippage_pct)
    except (TypeError, ValueError):
        return None
    if p <= 0 or s < 0 or s > 50:
        return None
    f = 1.0 + (s / 100.0)
    return p * f if str(side).lower() == "buy" else p * (2.0 - f)


# ---------------------------------------------------------------- اتصال
def check_connection(account_index: Any, api_key_private: str,
                     api_key_index: int = 0) -> Tuple[bool, str]:
    """صحت اتصال: ساخت SignerClient داخل event loop + check_client.
    (ok, پیام) — پیام فارسیِ مهربان برای هر دو حالت."""
    try:
        acc = int(account_index)
    except (TypeError, ValueError):
        return False, "شماره‌ی حساب (account index) باید عدد باشد."
    if acc < 0:
        return False, "شماره‌ی حساب نمی‌تواند منفی باشد."
    key = str(api_key_private or "").strip()
    if len(key) < 40:
        return False, "کلید API خیلی کوتاه است — کلید API لایتر را از صفحه‌ی API Keys سایت کپی کن."
    if not sdk_available():
        return False, "کتابخانه‌ی lighter-sdk نصب نیست — در requirements اضافه شود."

    try:
        import lighter

        async def _run() -> Optional[str]:
            client = lighter.SignerClient(
                url=BASE,
                account_index=acc,
                api_private_keys={int(api_key_index): key},
            )
            try:
                err = client.check_client()
                if err is not None:
                    return str(err)
                return None
            finally:
                try:
                    await client.close()
                except Exception:
                    pass

        err = asyncio.run(_run())
    except Exception as e:  # noqa: BLE001
        return False, ("اتصال برقرار نشد: " + scrub(e, key))
    if err:
        return False, ("کلید/حساب تأیید نشد: " + scrub(err, key))
    return True, "اتصال به لایتر تأیید شد ✅"


# ---------------------------------------------------------------- ارسال سفارش
def build_order_payload(*, order_kind: str, side: str, amount: float,
                        price: float, last_price: float,
                        size_decimals: int, price_decimals: int,
                        slippage_pct: float = MARKET_SLIPPAGE_PCT) -> Dict[str, Any]:
    """ساخت payload مقیاس‌شده‌ی سفارش — خالص و تست‌پذیر.
    خروجی: {"ok", "err", "base_amount", "price", "avg_execution_price",
            "is_ask", "order_type", "time_in_force", "client_order_index"}
    order_kind: "limit" | "market" — side: "buy" | "sell"."""
    out: Dict[str, Any] = {"ok": False, "err": "", "base_amount": 0, "price": 0,
                           "avg_execution_price": 0, "is_ask": False,
                           "order_type": 0, "time_in_force": 1, "client_order_index": 0}
    kind = str(order_kind or "").lower()
    sd = str(side or "").lower()
    if kind not in ("limit", "market"):
        return {**out, "err": "نوع سفارش باید limit یا market باشد."}
    if sd not in ("buy", "sell"):
        return {**out, "err": "جهت سفارش باید buy یا sell باشد."}
    base_amount = scale_value(amount, size_decimals)
    if base_amount is None:
        return {**out, "err": "مقدار نامعتبر است (باید عدد مثبت قابل‌مقیاس باشد)."}
    is_ask = sd == "sell"
    # limit: قیمتِ خود سفارش؛ market: قیمت اجرای متوسط = بدترین قیمتِ مجاز (سپر لغزش)
    if kind == "limit":
        scaled_price = scale_value(price, price_decimals)
        if scaled_price is None:
            return {**out, "err": "برای سفارش limit قیمت مثبت لازم است."}
        out["price"] = scaled_price
        out["avg_execution_price"] = scaled_price
        out["order_type"] = 0      # ORDER_TYPE_LIMIT
        out["time_in_force"] = 1   # GOOD_TILL_TIME
    else:
        wp = worst_price(sd, last_price, slippage_pct)
        if wp is None:
            return {**out, "err": "برای سفارش market قیمت زنده در دسترس نیست."}
        scaled_price = scale_value(wp, price_decimals)
        if scaled_price is None:
            return {**out, "err": "مقیاس‌بندی قیمت ناموفق بود."}
        out["price"] = 0
        out["avg_execution_price"] = scaled_price
        out["order_type"] = 1      # ORDER_TYPE_MARKET
        out["time_in_force"] = 0   # IMMEDIATE_OR_CANCEL
    out.update({"ok": True, "base_amount": base_amount, "is_ask": is_ask,
                "client_order_index": client_order_index()})
    return out


def submit_order(*, account_index: Any, api_key_private: str, api_key_index: int,
                 market_index: int, size_decimals: int, price_decimals: int,
                 order_kind: str, side: str, amount: float,
                 price: float = 0.0, last_price: float = 0.0,
                 reduce_only: bool = False,
                 slippage_pct: float = MARKET_SLIPPAGE_PCT,
                 _sdk: Optional[Any] = None) -> Dict[str, Any]:
    """ثبت سفارش واقعی روی لایتر. خروجی:
    {"ok": bool, "err": str فارسی, "tx_hash", "order_index", "client_order_index"}.
    _sdk فقط برای تست است (ماژول فیک)."""
    global last_error
    payload = build_order_payload(
        order_kind=order_kind, side=side, amount=amount, price=price,
        last_price=last_price, size_decimals=size_decimals,
        price_decimals=price_decimals, slippage_pct=slippage_pct)
    res = {"ok": False, "err": "", "tx_hash": "", "order_index": None,
           "client_order_index": payload.get("client_order_index") or 0}
    if not payload["ok"]:
        res["err"] = payload["err"]
        last_error = res["err"]
        return res
    key = str(api_key_private or "").strip()
    if not sdk_available() and _sdk is None:
        res["err"] = "کتابخانه‌ی lighter-sdk نصب نیست."
        last_error = res["err"]
        return res
    try:
        acc = int(account_index)
        mid = int(market_index)
        kidx = int(api_key_index)
    except (TypeError, ValueError):
        res["err"] = "شماره‌ی حساب/بازار نامعتبر است."
        last_error = res["err"]
        return res

    try:
        if _sdk is not None:
            mod = _sdk
        else:
            import lighter as mod  # noqa: PLC0415

        async def _run() -> Tuple[Optional[str], Optional[Any]]:
            client = mod.SignerClient(
                url=BASE, account_index=acc,
                api_private_keys={kidx: key})
            try:
                if payload["order_type"] == 1:   # market
                    tx, resp, err = await client.create_market_order(
                        market_index=mid,
                        client_order_index=payload["client_order_index"],
                        base_amount=payload["base_amount"],
                        avg_execution_price=payload["avg_execution_price"],
                        is_ask=payload["is_ask"],
                        reduce_only=reduce_only,
                    )
                else:                            # limit
                    tx, resp, err = await client.create_order(
                        market_index=mid,
                        client_order_index=payload["client_order_index"],
                        base_amount=payload["base_amount"],
                        price=payload["price"],
                        is_ask=payload["is_ask"],
                        order_type=payload["order_type"],
                        time_in_force=payload["time_in_force"],
                        reduce_only=reduce_only,
                    )
                if err is not None:
                    return str(err), None
                return None, resp
            finally:
                try:
                    await client.close()
                except Exception:
                    pass

        err, resp = asyncio.run(_run())
    except Exception as e:  # noqa: BLE001
        res["err"] = ("ارسال سفارش ناموفق بود: " + scrub(e, key))
        last_error = res["err"]
        return res
    if err:
        res["err"] = ("لایتر سفارش را نپذیرفت: " + scrub(err, key))
        last_error = res["err"]
        return res
    # resp = RespSendTx — hash و کد نتیجه
    tx_hash = ""
    try:
        tx_hash = str(getattr(resp, "tx_hash", "") or "")
    except Exception:
        pass
    last_error = None
    return {"ok": True, "err": "", "tx_hash": tx_hash,
            "order_index": None, "client_order_index": payload["client_order_index"]}


def cancel_all_orders(*, account_index: Any, api_key_private: str,
                      api_key_index: int = 0, market_index: Optional[int] = None,
                      _sdk: Optional[Any] = None) -> Dict[str, Any]:
    """لغو همه‌ی سفارش‌های باز (یا فقط یک بازار). خروجی {"ok","err"}."""
    key = str(api_key_private or "").strip()
    try:
        acc = int(account_index)
        kidx = int(api_key_index)
        mid = int(market_index) if market_index is not None else 255  # 255 = همه‌ی بازارها
    except (TypeError, ValueError):
        return {"ok": False, "err": "شماره‌ی حساب نامعتبر است."}
    try:
        if _sdk is not None:
            mod = _sdk
        else:
            import lighter as mod  # noqa: PLC0415

        async def _run() -> Optional[str]:
            client = mod.SignerClient(url=BASE, account_index=acc,
                                      api_private_keys={kidx: key})
            try:
                tx, resp, err = await client.cancel_all_orders(
                    time_in_force=mod.SignerClient.CANCEL_ALL_TIF_IMMEDIATE,
                    timestamp_ms=int(time.time() * 1000),
                    cancel_all_market_index=mid,
                )
                if err is not None:
                    return str(err)
                return None
            finally:
                try:
                    await client.close()
                except Exception:
                    pass

        err = asyncio.run(_run())
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "err": ("لغو سفارش‌ها ناموفق بود: " + scrub(e, key))}
    if err:
        return {"ok": False, "err": ("لایتر نپذیرفت: " + scrub(err, key))}
    return {"ok": True, "err": ""}


# ---------------------------------------------------------------- حساب عمومی (بدون کلید)
def _parse_account(data: Any) -> Optional[Dict[str, Any]]:
    """پاسخ /api/v1/account → خلاصه‌ی حساب: موجودی، پوزیشن‌ها، سفارش‌های باز."""
    try:
        if not isinstance(data, dict):
            return None
        accs = data.get("accounts")
        if not isinstance(accs, list) or not accs:
            return None
        a = accs[0] if isinstance(accs[0], dict) else {}
        if not a:
            return None
        positions: List[Dict[str, Any]] = []
        for p in (a.get("positions") or []):
            if not isinstance(p, dict):
                continue
            try:
                size = float(p.get("position") or 0)
            except (TypeError, ValueError):
                size = 0.0
            if size == 0:
                continue
            sign = int(p.get("sign") or 0)
            positions.append({
                "symbol": str(p.get("symbol") or ""),
                "market_id": p.get("market_id"),
                "side": "long" if sign == 1 else ("short" if sign == -1 else "?"),
                "size": abs(size),
                "entry": float(p.get("avg_entry_price") or 0),
                "value": float(p.get("position_value") or 0),
                "upnl": float(p.get("unrealized_pnl") or 0),
                "liq_price": float(p.get("liquidation_price") or 0),
            })
        try:
            open_orders = len(a.get("open_orders") or [])
        except TypeError:
            open_orders = 0
        return {
            "index": a.get("index"),
            "collateral": float(a.get("collateral") or 0),
            "available": float(a.get("available_balance") or 0),
            "open_orders": open_orders,
            "positions": positions,
        }
    except Exception:
        return None


def account_summary(account_index: Any, _fetch: Optional[_Fetch] = None) -> Optional[Dict[str, Any]]:
    """خلاصه‌ی عمومی حساب لایتر (بدون هیچ کلیدی — این داده عمومی است). خرابی = None."""
    try:
        acc = int(account_index)
    except (TypeError, ValueError):
        return None
    if acc < 0:
        return None
    fetch = _fetch or get_json
    try:
        data = fetch(f"{BASE}/api/v1/account",
                     params={"by": "index", "value": str(acc)},
                     headers=HEADERS, timeout=FETCH_TIMEOUT)
    except Exception:
        return None
    return _parse_account(data)


def find_account_by_address(l1_address: str, _fetch: Optional[_Fetch] = None) -> Optional[int]:
    """آدرس کیف‌پول (0x...) → کوچک‌ترین account index (حساب مادر). پیدا نشد = None."""
    addr = str(l1_address or "").strip()
    if not addr.lower().startswith("0x") or len(addr) != 42:
        return None
    fetch = _fetch or get_json
    try:
        data = fetch(f"{BASE}/api/v1/account",
                     params={"by": "l1_address", "value": addr},
                     headers=HEADERS, timeout=FETCH_TIMEOUT)
    except Exception:
        return None
    try:
        accs = (data or {}).get("accounts") or []
        idxs = [int(a.get("index")) for a in accs
                if isinstance(a, dict) and a.get("index") is not None]
        return min(idxs) if idxs else None
    except Exception:
        return None

