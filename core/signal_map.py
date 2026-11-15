# -*- coding: utf-8 -*-
"""core/signal_map.py — نقشه‌ی نشاطِ سیگنال، قالبِ مشترکِ کرونوس و نبیه
================================================================
سوییپِ نشاط (scripts/nabigha_signal_sweep.py) با همان موتورِ چارتِ اپ
(add_indicators + setup_plan + دروازه‌ی QC) کلِ استخر × سه تایم‌فریم را
می‌کوبد و core/data/nabigha_signal_map.json می‌نویسد. این ماژول تک‌منبعِ
مصرفِ آن نقشه است — «چارتِ حکم» برای هر دو موتور یکی است، پس نمادِ داغ
برای شاهدِ کرونوس و نبیه یکان است و هر دو جلسه‌گیر با --hot از همین‌جا
می‌خوانند.

- hot_picks(interval, n): نمادهایِ زنده از نقشه‌ی تازه (<fresh_h ساعت) —
  اولِ خانه‌هایِ فعالِ همین تایم‌فریم، بعدِ سایر تایم‌فریم‌ها. نقشه‌ی
  نبود/کهنه/خراب = [] یعنی فال‌بکِ امن به چرخشِ تقویمی، نه شکستِ جلسه.
- get_pool(): استخرِ سوییپ = نمادهایِ اصلیِ چرخش (CANDIDATES — قطعی و
  یکتا برای rotate) + پرکردن تا سقف با پرگردش‌هایِ زنده‌ی KuCoin؛
  شبکه‌ی خراب = فقطِ اصلی‌ها (fail-soft).

درسِ ۰/۴۲ (۱۴۰۴/۰۸/۲۴): ستاپ‌های چارت فقط در آستانه‌ی شکل‌گیری (۲ کندلِ
آخر) + واک‌فوروارِ همان نماد فعال می‌شوند؛ جلسه‌ی روزانه روی نمادِ سرد
برای دروازه‌ی ۲۰۰ سیگنال‌دار هدررفت است — نقشه + چیدمانِ داغ + کادانسِ
هر-۳-ساعت همان را درمان کرد (اولین سیگنال‌دارِ نبیه: ADA-USDT·1day).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

TEHRAN = timezone(timedelta(hours=3, minutes=30))


def map_path() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "core", "data", "nabigha_signal_map.json")


def map_age_h() -> float | None:
    """عمرِ نقشه به ساعت — None یعنی نقشه نیست/خراب (فال‌بک، نه خطا)."""
    try:
        with open(map_path(), encoding="utf-8") as f:
            m = json.load(f)
        ts = datetime.fromisoformat(m["ts_tehran"])
        return (datetime.now(TEHRAN) - ts).total_seconds() / 3600
    except Exception:  # noqa: BLE001 — نبودِ نقشه داده نیست
        return None


def hot_picks(interval: str, n: int, fresh_h: float = 4.0) -> list[str]:
    """نمادهایِ زنده از نقشه‌ی نشاط — همان قراردادِ جلسه‌گیرهای کرونوس و نبیه."""
    if n <= 0:
        return []
    age = map_age_h()
    if age is None or age > fresh_h:
        return []
    try:
        with open(map_path(), encoding="utf-8") as f:
            combos = json.load(f).get("combos", [])
    except Exception:  # noqa: BLE001 — نقشه‌ی خراب یعنی چرخشِ عادی
        return []
    act = [c["symbol"] for c in combos
           if c.get("active") and c.get("interval") == interval]
    if len(act) < n:
        act += [c["symbol"] for c in combos
                if c.get("active") and c.get("interval") != interval
                and c["symbol"] not in act]
    return act[:n]


def get_pool(max_total: int = 30) -> list[str]:
    """استخرِ سوییپ: اصلی‌هایِ چرخش + پرکردن تا سقف با پرگردش‌هایِ KuCoin.

    اصلی‌ها (CANDIDATES) قطعی‌اند چون rotate رویشان می‌چرخد؛ افزوده‌ها فقط
    برای نقشه‌ی نشاط‌اند و قطعی‌بودن لازم ندارند.
    """
    from core.team_daily import CANDIDATES  # noqa — ایمپورتِ داخلِ تابع (چرخه‌ی ایمپورت نشود)
    pool = list(CANDIDATES)
    if len(pool) >= max_total:
        return pool[:max_total]
    try:
        from app_base import fetch_top_coins  # noqa — ایمپورتِ سنگینِ داخلِ تابع
        vol = fetch_top_coins("KuCoin", limit=max_total).get("volume")
        if vol is not None and "symbol" in getattr(vol, "columns", []):
            for s in vol["symbol"]:
                s = str(s).upper().strip()
                if s.endswith("-USDT") and s not in pool:
                    pool.append(s)
                if len(pool) >= max_total:
                    break
    except Exception:  # noqa: BLE001 — شبکه‌ی خراب یعنی فقطِ اصلی‌ها
        pass
    return pool
