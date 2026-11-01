# -*- coding: utf-8 -*-
"""core/news.py — پنل خبر کریپتو (RSS رایگان، بدون کلید)
========================================================
تیترهای تازه از سه منبع شناخته‌شده + تگ‌کردن نمادهای مرتبط داخل هر تیتر.
  • کش ۱۰ دقیقه‌ای — هر رندر صفحه درخواست شبکه‌ی تازه نمی‌زند
  • اگر یک فید از کار افتاد، بقیه پوشش می‌دهند؛ اگر همه شکست خوردند stale=True
  • تحلیل تیتر با regex و مرزِ کلمه — «SOLUTION» را SOL نمی‌گیرد
تیترها به انگلیسی می‌مانند (ترجمه‌ی ماشینی اخبار مالی خطا می‌سازد).
"""
from __future__ import annotations

import re
import time
from datetime import timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List
from xml.etree import ElementTree as ET

from core.net import get_text

NEWS_TTL_S = 600.0

FEEDS = [
    ("Decrypt", "https://decrypt.co/feed"),
    ("Cointelegraph", "https://cointelegraph.com/rss"),
    ("NewsBTC", "https://www.newsbtc.com/feed/"),
]

# (کلمه در تیتر، نماد) — اول بلندترین‌ها چک می‌شوند تا «ETHEREUM» قبل از «ETH»
_SYMBOL_WORDS = [
    ("BITCOIN", "BTC"), ("ETHEREUM", "ETH"), ("DOGECOIN", "DOGE"), ("SOLANA", "SOL"),
    ("CARDANO", "ADA"), ("AVALANCHE", "AVAX"), ("CHAINLINK", "LINK"), ("RIPPLE", "XRP"),
    ("BINANCE COIN", "BNB"), ("SHIBA INU", "SHIB"), ("POLKADOT", "DOT"), ("LITECOIN", "LTC"),
    ("TRON", "TRX"), ("TONCOIN", "TON"), ("BITCOIN CASH", "BCH"),
    ("BTC", "BTC"), ("ETH", "ETH"), ("SOL", "SOL"), ("XRP", "XRP"), ("DOGE", "DOGE"),
    ("ADA", "ADA"), ("AVAX", "AVAX"), ("LINK", "LINK"), ("DOT", "DOT"), ("LTC", "LTC"),
    ("BNB", "BNB"), ("SHIB", "SHIB"), ("TRX", "TRX"), ("TON", "TON"), ("BCH", "BCH"),
]

_CACHE: Dict[str, Any] = {"ts": 0.0, "val": None}


def tag_symbols(title: str, max_tags: int = 3) -> List[str]:
    """نمادهای مرتبط با تیتر — با مرزِ کلمه، بدون تکرار، حداکثر max_tags."""
    t = str(title or "").upper()
    out: List[str] = []
    for word, sym in _SYMBOL_WORDS:
        if sym in out:
            continue
        if re.search(rf"\b{re.escape(word)}\b", t):
            out.append(sym)
            if len(out) >= max_tags:
                break
    return out


def parse_feed(xml_text: str, source: str, max_items: int = 8) -> List[Dict[str, Any]]:
    """پارس RSS 2.0 — خروجی: [{source, title, link, ts, symbols}] (تازه‌تر اول نیست — به‌ترتیب فید)."""
    root = ET.fromstring(str(xml_text or ""))
    items: List[Dict[str, Any]] = []
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        pub = (it.findtext("pubDate") or "").strip()
        ts = ""
        if pub:
            try:
                ts = parsedate_to_datetime(pub).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            except Exception:  # noqa: BLE001
                ts = ""
        if not title or not link:
            continue
        items.append({"source": source, "title": title[:200], "link": link,
                      "ts": ts, "symbols": tag_symbols(title)})
        if len(items) >= max_items:
            break
    return items


def fetch_news(max_per: int = 8, max_age_s: float = NEWS_TTL_S) -> Dict[str, Any]:
    """خبرهای تازه — کش‌شده تا max_age_s ثانیه.
    خروجی: {items, ts, stale, cached} — stale=True یعنی هیچ فیدی جواب نداد."""
    now = time.time()
    val = _CACHE.get("val")
    if val and now - float(_CACHE.get("ts") or 0.0) <= max_age_s:
        return {**val, "cached": True}
    items: List[Dict[str, Any]] = []
    for name, url in FEEDS:
        try:
            xml_text = get_text(url, timeout=8.0, retries=1,
                                headers={"User-Agent": "Mozilla/5.0 (compatible; arena-news/1.0)"})
            items.extend(parse_feed(xml_text, name, max_per))
        except Exception:  # noqa: BLE001
            continue
    items.sort(key=lambda x: str(x.get("ts") or ""), reverse=True)
    out = {"items": items[:24], "ts": now, "stale": not items, "cached": False}
    if items:
        _CACHE["ts"], _CACHE["val"] = now, out
    return out
