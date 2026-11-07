# -*- coding: utf-8 -*-
"""
core/paper.py — منطق خالصِ ترید مجازی (Paper)
=============================================
قبلاً Paper فقط یک عدد بالانس بود: «فروش» بدون داشتن پوزیشن، پول تازه اضافه
می‌کرد و پوزیشن/سود و زیان هیچ‌جا ثبت نمی‌شد. این ماژول منطق را خالص و
تست‌پذیر می‌کند:

  * خرید: اگر موجودی کافی باشد، میانگین قیمت خرید به‌روز می‌شود و بالانس کم می‌شود.
  * فروش: فقط به‌اندازه‌ی مقداری که واقعاً داری — سود/زیانِ تحقق‌یافته ثبت می‌شود.
    (Short لخت در Paper مجاز نیست؛ صادقانه رد می‌شود.)
  * هر ورودی خراب = رد با پیام فارسیِ صادقانه — هیچ‌چیز تغییر نمی‌کند (fail-closed).

positions: {symbol: {"qty": float, "avg": float}} — خرید تازه با نمادِ جدید کلید
می‌سازد؛ وقتی مقدار به صفر رسید کلید حذف می‌شود.
"""
from __future__ import annotations

import math
from typing import Any, Dict, Tuple

_EPS = 1e-9


def _f(v: Any) -> float:
    try:
        x = float(v)
        return x if (math.isfinite(x) and x > 0) else 0.0
    except (TypeError, ValueError):
        return 0.0


def apply_fill(positions: Dict[str, Any], side: str, symbol: str,
               amount: Any, price: Any, balance: Any) -> Tuple[Dict[str, Any], float, float, str]:
    """یک پرشدنِ مجازی را روی وضعیت اعمال می‌کند.
    ورودی: positions (dict نماد → qty/avg)، side (buy/sell)، amount، price، balance.
    خروجی: (positions_تازه، balance_تازه، realized_delta، پیام)
      * ok   → پیام خالی نیست و مثبت است، وضعیت تازه برگردانده می‌شود.
      * رد   → پیام با «✗» شروع می‌شود و وضعیتِ ورودی دست‌نخورده برمی‌گردد.
    """
    sym = str(symbol or "").strip().upper()
    amt = _f(amount)
    prc = _f(price)
    bal = _f(balance)
    if not sym:
        return positions, bal, 0.0, "✗ نماد خالی است — سفارش مجازی ثبت نشد."
    if amt <= 0 or prc <= 0:
        return positions, bal, 0.0, "✗ مقدار و قیمت باید بزرگ‌تر از صفر باشند."
    side_n = str(side or "").strip().lower()

    # کپی عمیقِ سطح یک — وضعیت ورودی هرگز تغییر نمی‌کند
    pos: Dict[str, Dict[str, float]] = {}
    for k, v in (positions or {}).items():
        try:
            q = _f((v or {}).get("qty"))
            a = _f((v or {}).get("avg"))
            if q > 0:
                pos[str(k).strip().upper()] = {"qty": q, "avg": a}
        except Exception:  # noqa: BLE001 — ردیف خراب حذف می‌شود
            continue

    cur = pos.get(sym, {"qty": 0.0, "avg": 0.0})
    if side_n == "buy":
        cost = amt * prc
        if cost > bal + _EPS:
            return positions, bal, 0.0, (f"✗ موجودی مجازی کافی نیست — نیاز {cost:,.2f} · "
                                         f"موجودی {bal:,.2f} USDT")
        new_qty = cur["qty"] + amt
        new_avg = ((cur["qty"] * cur["avg"]) + cost) / new_qty if new_qty > 0 else prc
        pos[sym] = {"qty": new_qty, "avg": new_avg}
        msg = (f"خرید مجازی {amt:g} {sym} در {prc:,.4f} — ارزش {cost:,.2f} USDT · "
               f"بالانس جدید {bal - cost:,.2f}")
        return pos, bal - cost, 0.0, msg

    if side_n == "sell":
        if amt > cur["qty"] + _EPS:
            if cur["qty"] <= 0:
                return positions, bal, 0.0, ("✗ پوزیشنی از این نماد نداری — در Paper فروشِ "
                                             "بدون خرید مجاز نیست.")
            return positions, bal, 0.0, (f"✗ بیش از مقداری که داری: داری {cur['qty']:g} {sym} · "
                                         f"فروش درخواستی {amt:g}")
        realized = amt * (prc - cur["avg"])
        new_qty = cur["qty"] - amt
        if new_qty <= _EPS:
            pos.pop(sym, None)
        else:
            pos[sym] = {"qty": new_qty, "avg": cur["avg"]}
        msg = (f"فروش مجازی {amt:g} {sym} در {prc:,.4f} — "
               f"سود/زیان تحقق‌یافته {realized:+,.2f} USDT · بالانس جدید {bal + amt * prc:,.2f}")
        return pos, bal + amt * prc, realized, msg

    return positions, bal, 0.0, "✗ جهت سفارش باید buy یا sell باشد."


def unrealized_pnl(positions: Dict[str, Any], symbol: str, live_price: Any) -> float:
    """سود/زیانِ بازِ یک نماد با قیمت زنده. داده‌ی ناقص = 0.0 (هیچ‌وقت عدد ساختگی)."""
    sym = str(symbol or "").strip().upper()
    lp = _f(live_price)
    try:
        entry = (positions or {}).get(sym) or {}
        qty = _f(entry.get("qty"))
        avg = _f(entry.get("avg"))
        if qty <= 0 or avg <= 0 or lp <= 0:
            return 0.0
        v = (lp - avg) * qty
        return v if math.isfinite(v) else 0.0
    except Exception:  # noqa: BLE001
        return 0.0
