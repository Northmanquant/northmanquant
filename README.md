# 📈 NorthmanQuant — نسخه‌ی رایگان (Lite)

> تحلیل زنده‌ی بازار کریپتو با **داده‌ی واقعی** از APIهای عمومی صرافی‌ها — بدون ثبت‌نام، بدون کلید API، بدون دیتابیس.

این نسخه برای دیپلوی رایگان روی **Streamlit Community Cloud** (یا Hugging Face Spaces) ساخته شده است.
همه‌ی قیمت‌ها، کندل‌ها و اندیکاتورها واقعی و مستقیماً از مستندات رسمی صرافی‌ها خوانده می‌شوند.

---

## ✨ قابلیت‌ها

| بخش | توضیح |
| --- | --- |
| 📊 تحلیل زنده | کندل + EMA20/EMA50 + بولینگر، حجم، خطوط ورود/حد ضرر/اهداف |
| 🌀 کهکشان همگرایی | نمودار چرخان SVG از ۹ اندیکاتور وزن‌دار |
| 🧱 حمایت و مقاومت | سطوح سوئینگ خوشه‌بندی‌شده با قدرت و فاصله |
| 📜 رویدادهای ورود/خروج | ماشین حالت روی امتیاز همگرانی (±۴۰ ورود، −۱۰ خروج) |
| 🎯 طرح معامله | ورود/حد ضرر ATR‑محور، دو هدف، R:R و درصد اطمینان |
| 🔴 حالت زنده | قیمت هر ۵ ثانیه با فلش سبز/سرخ + شمارش معکوس بسته‌شدن کندل |
| 🏆 برترین‌ها | بیشترین سود/ریزش/حجم ۲۴ ساعته |
| 📰 اخبار | سه فید RSS با امتیازدهی واژه‌ای مثبت/منفی |
| 🖼️ تصویر تحلیل | نماد را وارد کن (ETH/BTC/…) تا خودش از داده‌ی واقعی یک **تصویر چارت آماده** با ورود/حد ضرر/اهداف و حمایت/مقاومت بسازد — قابل دانلود |
| 📚 منابع داده | فهرست اندپوینت‌ها و لینک مستندات رسمی هر صرافی |

---

## 🏦 صرافی‌های پشتیبانی‌شده (همه واقعی و مستندسازی‌شده)

| صرافی | نوع بازار | اندپوینت کندل | اندپوینت تیکر | مستندات |
| --- | --- | --- | --- | --- |
| KuCoin | Spot | `/api/v1/market/candles` | `/api/v1/market/orderbook/level1` | [kucoin.com/docs](https://www.kucoin.com/docs/rest/spot/market-data/get-klines) |
| OKX | Spot | `/api/v5/market/candles` | `/api/v5/market/ticker` | [okx.com/docs-v5](https://www.okx.com/docs-v5/en/#order-book-trading-market-data) |
| Binance | Spot | `/api/v3/klines` | `/api/v3/ticker/bookTicker` | [developers.binance.com](https://developers.binance.com/docs/binance-spot-api-docs/rest-api/market-data-endpoints) |
| Bybit | Spot | `/v5/market/kline` | `/v5/market/tickers` | [bybit-exchange.github.io](https://bybit-exchange.github.io/docs/v5/market/kline) |
| **Lighter** | **Perp (DEX)** | `/api/v1/candles` | `/api/v1/orderBookDetails` + `/api/v1/orderBookOrders` | [apidocs.lighter.xyz](https://apidocs.lighter.xyz/reference/candles) |

**نکته‌های مهم پیاده‌سازی (براساس مستندات)**

* **KuCoin** ردیف کندل را `[time, open, close, high, low, volume, turnover]` برمی‌گرداند — ترتیب `open/close` با بقیه متفاوت است.
* **Bybit** و **OKX** لیست را از جدید به قدیم می‌دهند؛ قبل از استفاده sort می‌شود.
* **Lighter** حداکثر **۵۰۰ کندل** در هر درخواست می‌دهد و مقادیر صفر را از پاسخ حذف می‌کند (با مقدار پیش‌فرض هندل شده). مارکت‌ها perp هستند (`BTC` بدون پسوند) و `market_id` از `orderBookDetails` resolve می‌شود — هیچ شناسه‌ای هاردکد نیست. علاوه بر قیمت، **Mark Price** و **Open Interest** واقعی نمایش داده می‌شود.
* اگر یک صرافی در منطقه‌ی شما مسدود باشد، کد به‌ترتیب بقیه‌ی صرافی‌ها **fallback** می‌کند.

---

## 🚀 اجرای محلی

```bash
git clone https://github.com/<your-username>/northmanquant-lite.git
cd northmanquant-lite

python -m venv .venv
source .venv/bin/activate        # ویندوز: .venv\Scripts\activate

pip install -r requirements.txt
streamlit run app.py
```

برنامه روی `http://localhost:8501` باز می‌شود.

بررسی سلامت APIها (اختیاری):

```bash
python scripts/verify_apis.py     # ۲۱ تست زنده روی همه‌ی صرافی‌ها
```

---

## ☁️ دیپلوی روی Streamlit Community Cloud

1. این ریپو را روی **GitHub** بفرستید (فایل `app.py` باید در روت باشد):

   ```bash
   git init
   git add .
   git commit -m "NorthmanQuant Lite"
   git branch -M main
   git remote add origin https://github.com/<your-username>/northmanquant-lite.git
   git push -u origin main
   ```

2. به [share.streamlit.io](https://share.streamlit.io) بروید → **Sign in with GitHub**.
3. **New app** → ریپو، برنچ `main` و فایل اصلی `app.py` را انتخاب کنید → **Deploy**.
4. چند ثانیه بعد اپ روی `https://<username>-northmanquant-lite.streamlit.app` زنده است.

> نیازی به `secrets.toml` یا هیچ کلید API نیست — همه‌ی اندپوینت‌ها عمومی هستند.
> اگر خواستید اپ همیشه بیدار بماند، Streamlit Community Cloud را با GitHub Actions یا سرویس‌هایی مثل UptimeRobot پینگ کنید.

---

## 📁 ساختار پروژه

```
northmanquant-lite/
├── app.py                    # کل اپلیکیشن Streamlit (ورود اصلی)
├── requirements.txt          # وابستگی‌ها
├── README.md
├── .gitignore
├── .streamlit/
│   └── config.toml           # تم تاریک + تنظیمات سرور
└── scripts/
    └── verify_apis.py        # تست زنده‌ی اندپوینت‌های صرافی‌ها
```

---

## 🧠 موتور تحلیل

۹ اندیکاتور با وزن، تبدیل به یک امتیاز همگرانی بین ‎−۱۰۰‎ و ‎+۱۰۰‎ می‌شوند:

| اندیکاتور | وزن |
| --- | --- |
| روند EMA50 | ۱۸٪ |
| MACD | ۱۶٪ |
| RSI(14) | ۱۳٪ |
| سوپرترند (10,3) | ۱۴٪ |
| ورتکس (14) | ۱۰٪ |
| جریان پول CMF (20) | ۱۰٪ |
| استوکاستیک (14,3) | ۹٪ |
| CCI (20) | ۵٪ |
| MFI (14) | ۵٪ |

* **ورود**: امتیاز ≥ ‎+۴۰‎ (لانگ) یا ≤ ‎−۴۰‎ (شورت)
* **خروج**: امتیاز ≤ ‎−۱۰‎ در پوزیشن لانگ، یا ≥ ‎+۱۰‎ در پوزیشن شورت
* اندیکاتورهای دیگر: EMA20/50/200، ATR(14) وایلدر، بولینگر(20,2)، VWAP(60)، ADX/±DI

---

## ⚠️ سلب مسئولیت

این ابزار صرفاً آموزشی/تحلیلی است و **توصیه‌ی سرمایه‌گذاری نیست**. داده‌ها از APIهای عمومی صرافی‌ها
با کش ۶۰ ثانیه‌ای خوانده می‌شوند و ممکن است تأخیر داشته باشند.

---

## 📄 لایسنس

MIT — استفاده و تغییر آزاد است.
