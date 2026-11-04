# -*- coding: utf-8 -*-
"""core/tse_paper.py — موتور ماکتِ بورس ایران (ترید کاغذی، بدون پول واقعی)
==========================================================================
پرتفوی مجازی با موجودی ریالی، خرید/فروش با قیمت زنده یا آخرین قیمت پایانی،
و کارمزد واقعیِ تقریبی بورس تهران:
  · هزینه‌ی خرید ≈ ۰٫۳۷۲٪ (کارمزد بروکار+کارگزار+…)
  · هزینه‌ی فروش ≈ ۰٫۸۷۸٪ (کارمزد + مالیات ۰٫۵٪)
منبع درصد‌ها: جدول کارمزد رسمی شرکت بورس تهران (سهم بورسی، آنلاین).

الگوی پروژه: توابع خالص — ورودی/خروجی ساده، بدون streamlit، بدون شبکه؛
همه‌چیز با تستِ بدون شبکه پوشش داده می‌شود. پیام‌ها دوزبانه (fa, en) هستند.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

# موجودی شروع: ۱٬۰۰۰٬۰۰۰٬۰۰۰ ریال = ۱۰۰ میلیون تومان
START_CASH_RIAL = 1_000_000_000.0

BUY_FEE = 0.003716     # هزینه‌ی تقریبی خرید
SELL_FEE = 0.008780    # هزینه‌ی تقریبی فروش (شامل مالیات ۰٫۵٪)


def new_portfolio(cash: float = START_CASH_RIAL) -> Dict[str, Any]:
    """پرتفوی تازه: نقد ریالی + مبلغ‌های باز (ins_code → ردیف)."""
    return {"cash": float(cash), "start": float(cash), "positions": {}, "orders": []}


def buy_fee(qty: float, price: float) -> float:
    """کارمزد تقریبی خرید (ریال)."""
    return float(qty) * float(price) * BUY_FEE


def sell_fee(qty: float, price: float) -> float:
    """کارمزد + مالیات تقریبی فروش (ریال)."""
    return float(qty) * float(price) * SELL_FEE


def apply_order(port: Dict[str, Any], side: str, ins_code: str, symbol: str,
                qty: float, price: float,
                when: str = "") -> Tuple[bool, str, str]:
    """ثبت سفارش مجازی. خروجی: (موفق؟, پیام fa, پیام en).
    سفارشِ خراب هرگز پرتفوی را خراب نمی‌کند (همه‌چیز قبل از اعمال چک می‌شود)."""
    try:
        q = float(qty)
        p = float(price)
    except (TypeError, ValueError):
        return False, "مقدار یا قیمت نامعتبر است.", "Invalid amount or price."
    if not ins_code or not str(ins_code).strip():
        return False, "نماد انتخاب نشده است.", "No symbol selected."
    if q <= 0 or q != int(q):
        return False, "تعداد سهم باید عدد صحیحِ مثبت باشد.", "Quantity must be a positive whole number."
    if p <= 0:
        return False, "قیمت باید بزرگ‌تر از صفر باشد.", "Price must be greater than zero."
    code = str(ins_code).strip()
    sym = str(symbol or code)
    pos: Dict[str, Any] = port.get("positions", {})
    orders: List[Dict[str, Any]] = port.setdefault("orders", [])

    if side == "buy":
        gross = q * p
        fee = buy_fee(q, p)
        total = gross + fee
        if total > port.get("cash", 0.0) + 1e-6:
            _fa = (f"موجودی نقد کافی نیست: لازم {total:,.0f} ریال · "
                   f"موجودی {port.get('cash', 0.0):,.0f} ریال.")
            _en = (f"Not enough cash: need {total:,.0f} rials · "
                   f"available {port.get('cash', 0.0):,.0f} rials.")
            return False, _fa, _en
        port["cash"] = float(port.get("cash", 0.0)) - total
        row = pos.get(code)
        if row:
            nq = row["qty"] + q
            row["avg"] = (row["avg"] * row["qty"] + gross) / nq if nq else p
            row["qty"] = nq
        else:
            pos[code] = {"symbol": sym, "qty": q, "avg": p}
        orders.append({"when": when, "side": "buy", "symbol": sym,
                       "qty": q, "price": p, "fee": fee})
        _fa = f"خرید {q:,.0f} سهم {sym} در {p:,.0f} ریال — کارمزد {fee:,.0f} ریال."
        _en = f"Bought {q:,.0f} {sym} at {p:,.0f} rials — fee {fee:,.0f} rials."
        return True, _fa, _en

    if side == "sell":
        row = pos.get(code)
        if not row or row.get("qty", 0.0) <= 0:
            return False, "این نماد را نداری — چیزی برای فروش نیست.", "You don't own this symbol — nothing to sell."
        have = row["qty"]
        if q > have + 1e-6:
            return False, (f"فقط {have:,.0f} سهم از {sym} داری."), \
                           (f"You only own {have:,.0f} shares of {sym}.")
        gross = q * p
        fee = sell_fee(q, p)
        net = gross - fee
        port["cash"] = float(port.get("cash", 0.0)) + net
        row["qty"] = have - q
        if row["qty"] <= 1e-9:
            pos.pop(code, None)
        orders.append({"when": when, "side": "sell", "symbol": sym,
                       "qty": q, "price": p, "fee": fee})
        _fa = f"فروش {q:,.0f} سهم {sym} در {p:,.0f} ریال — عایدی خالص {net:,.0f} ریال."
        _en = f"Sold {q:,.0f} {sym} at {p:,.0f} rials — net proceeds {net:,.0f} rials."
        return True, _fa, _en

    return False, "جهت سفارش باید buy یا sell باشد.", "Side must be buy or sell."


def portfolio_table(port: Dict[str, Any], prices: Optional[Dict[str, float]] = None) -> pd.DataFrame:
    """جدول مبلغ‌های باز با قیمت فعلی: ارزش، سود/زیان ریالی و درصدی."""
    prices = prices or {}
    rows = []
    for code, row in (port.get("positions") or {}).items():
        q = float(row.get("qty", 0.0))
        avg = float(row.get("avg", 0.0))
        px = float(prices.get(code, 0.0)) or avg
        value = q * px
        cost = q * avg
        rows.append({
            "ins_code": code,
            "نماد": row.get("symbol", code),
            "تعداد": q,
            "میانگین خرید (ریال)": avg,
            "قیمت فعلی (ریال)": px,
            "ارزش (ریال)": value,
            "سود/زیان (ریال)": value - cost,
            "سود/زیان ٪": ((px - avg) / avg * 100.0) if avg > 0 else 0.0,
        })
    return pd.DataFrame(rows)


def summary(port: Dict[str, Any], prices: Optional[Dict[str, float]] = None) -> Dict[str, float]:
    """نقد + ارزش مبلغ‌ها + ارزش کل پرتفوی + کل سود/زیان نسبت به شروع."""
    prices = prices or {}
    pos_value = 0.0
    for code, row in (port.get("positions") or {}).items():
        px = float(prices.get(code, 0.0)) or float(row.get("avg", 0.0))
        pos_value += float(row.get("qty", 0.0)) * px
    cash = float(port.get("cash", 0.0))
    equity = cash + pos_value
    return {"cash": cash, "positions_value": pos_value, "equity": equity,
            "pnl": equity - float(port.get("start", START_CASH_RIAL)),
            "start": float(port.get("start", START_CASH_RIAL))}
