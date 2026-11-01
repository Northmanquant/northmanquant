# -*- coding: utf-8 -*-
"""core/net.py — لایه‌ی شبکه با تلاش مجدد (retry + backoff)
==========================================================
همه‌ی فراخوانی‌های GET به APIهای عمومی صرافی‌ها از اینجا رد می‌شوند:
  • خطای موقت (تایم‌اوت، قطع اتصال، 429، 5xx) → تلاش مجدد با backoff نمایی + jitter
  • احترام به هدر Retry-After صرافی‌ها
  • خطاهای دائمی (400/403/404/…) بلافاصله بالا پرتاب می‌شوند — بی‌خود منتظر نمی‌مانیم

چرا؟ روی Streamlit Community Cloud چند اپ از IPهای مشترک استفاده می‌کنند و
صرافی‌ها (مخصوصاً Binance) به‌راحتی محدود می‌کنند. بدون retry، یک لغزش موقت
یعنی صفحه‌ی خالی برای کاربر؛ با این لایه نرخ خطای دیده‌شده به‌شدت پایین می‌آید.
"""
from __future__ import annotations

import random
import time
from typing import Any, Optional

import requests

_RETRY_STATUS = {429, 500, 502, 503, 504}
_MAX_SLEEP = 8.0


def _delay(attempt: int, retry_after: Optional[str]) -> float:
    """تأخیر تا تلاش بعدی: اولویت با Retry-After صرافی، وگرنه backoff نمایی + jitter."""
    if retry_after:
        try:
            return min(float(retry_after), _MAX_SLEEP)
        except (TypeError, ValueError):
            pass
    return min(0.8 * (2 ** attempt) + random.uniform(0.0, 0.4), _MAX_SLEEP)


def get_json(url: str, *, params=None, headers=None, timeout: float = 10.0,
             retries: int = 2, session: Optional[requests.Session] = None) -> Any:
    """GET با تلاش مجدد — خروجی: JSON پارس‌شده.

    retries = تعداد تلاشِ مجدد (مجموعاً retries+1 بار تلاش می‌شود).
    خطاهای شبکه‌ای/پارس (تایم‌اوت، قطع اتصال، JSON خراب) و وضعیت‌های
    429/5xx دوباره تلاش می‌شوند؛ بقیه‌ی خطاهای HTTP بلافاصله raise می‌شوند.
    """
    retries = max(0, int(retries))
    getter = session.get if session is not None else requests.get
    last_exc: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            r = getter(url, params=params, headers=headers, timeout=timeout)
            if r.status_code in _RETRY_STATUS and attempt < retries:
                time.sleep(_delay(attempt, r.headers.get("Retry-After")))
                continue
            r.raise_for_status()
            return r.json()
        except (requests.Timeout, requests.ConnectionError, ValueError) as e:
            # خطای شبکه‌ای یا JSON خراب — قابل تلاش مجدد
            last_exc = e
            if attempt >= retries:
                raise
            time.sleep(_delay(attempt, None))
    raise last_exc  # pragma: no cover — حلقه همیشه یا برمی‌گردد یا raise کرده است
