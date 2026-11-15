"""فهرستِ رسمیِ صرافی‌ها — تک‌منبعِ حقیقتِ کل اپ
=================================================
قاعده‌ی پروژه: هر بخش/ماژولِ جدید باید «همه‌ی» صرافی‌های این فهرست را پوشش بدهد —
هیچ صفحه یا باتی حق ندارد لیستِ صرافیِ محلیِ خودش را کوتاه‌تر از اینجا کند.
اگر صرافی تازه اضافه شد، اول همین‌جا ثبتش کن؛ بعد پوششِ داده‌اش را در app_base
(tick / candles / top_coins) کامل کن؛ همه‌ی UIها خودکار از اینجا می‌خوانند."""
from .base import BaseExchange
from .kcex import KCEXExchange

# صرافی‌هایی که app_base برایشان fetchِ بومی دارد (تیک/کندل/فهرست ارز)
NATIVE_EXCHANGES = ["KuCoin", "OKX", "Binance", "Bybit", "Lighter"]

# صرافی‌های تکمیلی: KCEX تیک/فهرستِ بومی دارد (کندل‌اش از مسیر فال‌بکِ venueهای
# دیگر می‌رود — اندپوینتِ عمومیِ کندلش تأییدنشده است)؛ XT و LBank از مسیر CCXT می‌آیند.
EXTRA_EXCHANGES = ["KCEX", "XT", "LBank"]

# فهرستِ کاملِ UI — تنها لیستی که selectboxها مجازند نمایش بدهند
EXCHANGES_ALL = NATIVE_EXCHANGES + EXTRA_EXCHANGES

__all__ = ["BaseExchange", "KCEXExchange",
           "NATIVE_EXCHANGES", "EXTRA_EXCHANGES", "EXCHANGES_ALL"]
