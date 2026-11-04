"""core/arena.py — موتور «میدان ایجنت‌ها» (Agent Arena)
========================================================
لیگ معاملاتی کاغذی با اسکن دومرحله‌ای کل بازار:
  مرحله ۱ — غربالگری: کل بازار صرافی (بدون سقف تعداد) در یک فراخوانی گرفته می‌شود؛
           ارزهای مرده و استیبل‌کوین حذف و «قدرت» هر ارز سنجیده می‌شود
           (مومنتوم ۲۴ ساعته + نقدینگی + دامنه‌ی نوسان). فقط بهترین‌ها از صدک
           قدرت رد می‌شوند — تعداد برگزیدگان دینامیک است، عدد ثابت نیست.
  مرحله ۲ — تحلیل عمیق: برگزیدگان از موتور مشترک ۴ ایجنت (بک‌تست + ستاپ
           walk-forward + R:R) رد می‌شوند و هر بازیکن با وزن‌های خودش تصمیم
           می‌گیرد. معامله‌ی کاغذی تا TP/SL/تایم‌اوت مدیریت می‌شود.
خروجی: وین‌ریت، امتیاز R-based، ایکوییتی و لیدربورد.

قواعد انصاف:
  • همه با همان universe ارز، تایم‌فریم، کارمزد و ریسک ثابت ۱٪ در هر معامله.
  • هزینه‌های واقعی لحاظ می‌شود: کارمزد taker هر سمت + لغزش هر سمت — از R خالص کسر می‌شود؛
    امتیاز نردبان (TP1/TP2/TP3) از R ناخالص حساب می‌شود تا «رسیدن به کدام هدف» معنا بماند.
  • حداکثر ۳ پوزیشن همزمان برای هر شرکت‌کننده، سقف کل ۱۵ پوزیشن باز.
  • هر ارز فقط یک پوزیشن باز برای هر شرکت‌کننده + cooldown بعد از بستن معامله.
  • در هر کندل اول استاپ چک می‌شود (محافظه‌کارانه — SL-first)، بعد تارگت‌ها.
  • خروج نردبانی: TP1 → استاپ به ورود · TP2 → استاپ به TP1 · TP3 → بستن کامل.

امتیازدهی R-based:
  TP3 کامل = +۵ | TP2 = +۲ | TP1 = +۱ | سر‌به‌سر = ۰ | استاپ (لیکویید) = −۱
  تایم‌اوت = ±۰٫۵ بر اساس علامت سود/زیان
وین‌ریت = بردها ÷ (بردها + باخت‌ها) — سر‌به‌سر و تایم‌اوت‌های صفر حساب نمی‌شوند.
"""
from __future__ import annotations

import math
import time
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from core.duel_engine import AGENTS, calculate_duel, get_df

# ----------------------------------------------------------------------------- constants
RISK_PCT = 1.0            # ریسک هر معامله = ۱٪ ایکوییتی ایجنت
MAX_POS_PER_AGENT = 3     # حداکثر پوزیشن باز هر شرکت‌کننده
GLOBAL_CAP = 15           # سقف کل پوزیشن‌های باز میدان
TIMEOUT_CANDLES = 100     # بستن اجباری معامله‌ی سرگردان بعد از ۱۰۰ کندل
COOLDOWN_CANDLES = 10     # فاصله‌ی اجباری تا معامله‌ی دوباره روی همان نماد/جهت
FEE_PCT = 0.06            # کارمزد بک‌تست موتور مشترک (calculate_duel)
START_EQUITY = 10000.0    # ایکوییتی شروع هر شرکت‌کننده (دلار کاغذی)

# ---- هزینه‌های واقعی معامله‌ی زنده (شبیه‌سازی Arena) ----------------------------
# کارمزد taker هر سمت + لغزش هر سمت → گرد به گرد ≈ ۰٫۳٪ نوشنال.
# این عدد از R «خالص» کسر می‌شود تا وین‌ریت/ایکوییتی واقع‌بینانه بماند؛
# با ریسک ۱٪ یعنی هر معامله حدود ۰٫۳R هزینه‌ی ثابت دارد — بردهای کوچک
# بدون این کسر توهم سود می‌ساختند.
TAKER_FEE_PCT = 0.10      # ٪ هر سمت (KuCoin/OKX/Binance/Bybit اسپات ≈ ۰٫۰۸–۰٫۱)
SLIPPAGE_PCT = 0.05       # ٪ هر سمت — محافظه‌کارانه برای ارزهای نقدشونده
COST_RT_PCT = 2 * (TAKER_FEE_PCT + SLIPPAGE_PCT) / 100.0   # = 0.003

# ---- فیلتر رژیم بازار ----------------------------------------------------------
# جهت معامله‌ها محدود می‌شود به جهت روندِ کل بازار: BTC/USDT روی تایم‌فریم ۴ساعته
# با میانگین متحرک ساده. بالای میانگین = بازار صعودی → فقط لانگ؛ زیرش = نزولی →
# فقط شورت. «باد پشت سر» — شورت‌زدن در پامپ و خرید در سقوطِ بازارِ نزولی از
# بزرگ‌ترین عامل‌های نابودی حساب‌های کوچک است. اگر دیتای BTC نبود، فیلتر خاموش
# می‌شود (dir=0) تا اسکن بی‌دلیل از کار نیفتد.
REGIME_SYMBOL = "BTC/USDT"
REGIME_TF = "4hour"
REGIME_MA_N = 50          # ~۸ روز — تعادل بین واکنش‌سرعت و نویز
REGIME_TTL_S = 600.0      # کش ۱۰ دقیقه‌ای — هر رندر صفحه درخواست شبکه نزند

INTERVAL_MIN = {"15min": 15, "1hour": 60, "4hour": 240, "1day": 1440}

COMMITTEE = {"name": "Committee 🤝", "fa": "کمیسیون 🤝", "color": "#94a3b8"}

POOL_FALLBACK = ["BTC-USDT", "ETH-USDT", "SOL-USDT", "XRP-USDT", "BNB-USDT", "DOGE-USDT",
                 "ADA-USDT", "AVAX-USDT", "LINK-USDT", "TRX-USDT", "LTC-USDT", "DOT-USDT"]

# غربالگری کل بازار — مرحله ۱
MIN_TURNOVER_M = 0.5     # حداقل گردش مالی ۲۴ ساعته (میلیون دلار) — حذف ارزهای مرده
STRENGTH_TOP_PCT = 85.0  # برگزیدگان = صدک ۸۵ قدرت (دینامیک؛ عدد ثابت نیست)
DEEP_CAP = 60            # فقط ترمز فنی سهمیه‌بندی API — به‌ندرت فعال می‌شود

# اشتهاي ریسک فیلتر ستاپ (دروازه‌ی اعتبارسنجی)
#   strict   = فقط ستاپ تازه + لبه‌ی walk-forward اثبات‌شده (همان رفتار قدیمی — به‌ندرت معامله)
#   balanced = ستاپ تازه در ۶ کندل اخیر کافی است (لبه‌ی اندازه‌گیری‌شده لازم نیست)
#   hunter   = فیلتر ستاپ خاموش — فقط ایجنت‌ها تصمیم می‌گیرند
APPETITES = {
    "strict":   {"fa": "سخت‌گیر — فقط ستاپ اثبات‌شده", "en": "Strict — proven setups only"},
    "balanced": {"fa": "متعادل — ستاپ تازه کافی است", "en": "Balanced — fresh setup is enough"},
    "hunter":   {"fa": "شکارچی — فقط ایجنت‌ها", "en": "Hunter — agents only"},
}
DEFAULT_APPETITE = "hunter"

_STABLE_QUOTES = ("USDC", "USDT", "DAI", "TUSD", "FDUSD", "BUSD", "USDP")


def participants() -> list[dict]:
    """۵ شرکت‌کننده‌ی میدان: ۴ ایجنت + کمیسیون (همان اجماع قدیمی، حالا بازیکن مستقل)."""
    out = [{"name": n, "color": spec["color"], "kind": "agent"} for n, spec in AGENTS.items()]
    out.append({"name": COMMITTEE["name"], "color": COMMITTEE["color"], "kind": "committee"})
    return out


# ----------------------------------------------------------------------------- time helpers
def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def to_ts(v) -> pd.Timestamp:
    """تبدیل امن به Timestamp UTC (چند بار ذخیره/خواندن ISO را تحمل می‌کند)."""
    try:
        ts = pd.Timestamp(v)
        if ts is pd.NaT or pd.isna(ts):
            return pd.NaT
        if ts.tzinfo is None:
            return ts.tz_localize("UTC")
        return ts.tz_convert("UTC")
    except Exception:  # noqa: BLE001
        return pd.NaT


# ----------------------------------------------------------------------------- scoring
def points_for(realized_r: float, exit_reason: str | None) -> float:
    """امتیاز R-based یک معامله‌ی بسته‌شده."""
    if exit_reason == "timeout":
        if realized_r > 0:
            return 0.5
        if realized_r < 0:
            return -0.5
        return 0.0
    if realized_r >= 1.9:
        return 5.0          # نردبان کامل (≈ ۲.۰R واقعی)
    if realized_r >= 0.9:
        return 2.0          # TP2 گرفته شد
    if realized_r > 0.05:
        return 1.0          # TP1 و بعد خروج با تریل
    if realized_r > -0.05:
        return 0.0          # سر‌به‌سر
    return -1.0             # استاپ = لیکویید ایجنت


def result_label(realized_r: float, points: float, exit_reason: str | None) -> str:
    if exit_reason == "timeout":
        return "timeout_win" if realized_r > 0 else "timeout_loss" if realized_r < 0 else "timeout_be"
    return "win" if points > 0 else "loss" if points < 0 else "be"


EXIT_FA = {"tp3": "🏆 TP3 کامل", "trail": "🛡️ خروج با تریل", "sl": "💀 استاپ (لیکویید)",
           "timeout": "⏱️ تایم‌اوت"}


# ----------------------------------------------------------------------------- simulation
def simulate_trade(t: dict, d: pd.DataFrame) -> dict:
    """پیش‌بردن یک معامله‌ی باز روی کندل‌های تازه (فقط کندل‌های بعد از last_candle).
    خروجی: پچ دیکشنری برای ذخیره‌سازی (خالی = چیزی عوض نشده)."""
    if not isinstance(d, pd.DataFrame) or d.empty or "dt" not in d.columns:
        return {}
    d = d.sort_values("dt").reset_index(drop=True)
    opened_ts = to_ts(t.get("opened_candle"))
    last_ts = to_ts(t.get("last_candle")) if t.get("last_candle") else opened_ts
    if last_ts is pd.NaT:
        return {}
    new = d[d["dt"] > last_ts]
    if new.empty:
        return {}

    direction = int(t["direction"])
    entry = float(t["entry"])
    stop0 = float(t["stop"])
    risk0 = abs(entry - stop0)
    if not np.isfinite(risk0) or risk0 <= 0:
        risk0 = entry * 0.01

    cur_stop = float(t.get("cur_stop") or t.get("stop") or stop0)
    tp1, tp2, tp3 = float(t["tp1"]), float(t["tp2"]), float(t["tp3"])
    frac = 1.0
    gross = float(t.get("gross_r") or 0.0)          # R ناخالص (بدون هزینه) — مبنای امتیاز نردبان
    realized = float(t.get("realized_r") or 0.0)   # R خالص (بعد از کارمزد+لغزش) — مبنای ایکوییتی
    tp1_done = bool(t.get("tp1_done"))
    tp2_done = bool(t.get("tp2_done"))
    status, exit_reason = "open", None
    # هزینه‌ی گردبه‌گرد بر حسب R (نسبت به ریسک اولیه‌ی همین معامله)
    cost_r = COST_RT_PCT * entry / risk0

    for _, row in new.iterrows():
        hi, lo = float(row["high"]), float(row["low"])
        if direction > 0:
            if lo <= cur_stop:                      # SL-first — محافظه‌کارانه
                leg = frac * (cur_stop - entry) / risk0
                gross += leg
                realized += leg - frac * cost_r
                frac = 0.0
                status, exit_reason = "closed", ("sl" if not tp1_done else "trail")
                break
            if not tp1_done and hi >= tp1:
                tp1_done = True
                leg = (1 / 3) * (tp1 - entry) / risk0
                gross += leg
                realized += leg - (1 / 3) * cost_r
                cur_stop = max(cur_stop, entry)
                frac -= 1 / 3
            if tp1_done and not tp2_done and hi >= tp2:
                tp2_done = True
                leg = (1 / 3) * (tp2 - entry) / risk0
                gross += leg
                realized += leg - (1 / 3) * cost_r
                cur_stop = max(cur_stop, tp1)
                frac -= 1 / 3
            if tp2_done and hi >= tp3:
                leg = frac * (tp3 - entry) / risk0
                gross += leg
                realized += leg - frac * cost_r
                frac = 0.0
                status, exit_reason = "closed", "tp3"
                break
        else:
            if hi >= cur_stop:
                leg = frac * (entry - cur_stop) / risk0
                gross += leg
                realized += leg - frac * cost_r
                frac = 0.0
                status, exit_reason = "closed", ("sl" if not tp1_done else "trail")
                break
            if not tp1_done and lo <= tp1:
                tp1_done = True
                leg = (1 / 3) * (entry - tp1) / risk0
                gross += leg
                realized += leg - (1 / 3) * cost_r
                cur_stop = min(cur_stop, entry)
                frac -= 1 / 3
            if tp1_done and not tp2_done and lo <= tp2:
                tp2_done = True
                leg = (1 / 3) * (entry - tp2) / risk0
                gross += leg
                realized += leg - (1 / 3) * cost_r
                cur_stop = min(cur_stop, tp1)
                frac -= 1 / 3
            if tp2_done and lo <= tp3:
                leg = frac * (entry - tp3) / risk0
                gross += leg
                realized += leg - frac * cost_r
                frac = 0.0
                status, exit_reason = "closed", "tp3"
                break

    last_dt = new["dt"].iloc[-1]

    # تایم‌اوت: کل کندل‌های بعد از ورود ≥ سقف → بستن با آخرین قیمت
    if status == "open" and opened_ts is not pd.NaT:
        elapsed = int((d["dt"] > opened_ts).sum())
        if elapsed >= TIMEOUT_CANDLES:
            cl = float(d["close"].iloc[-1])
            leg = frac * ((cl - entry) if direction > 0 else (entry - cl)) / risk0
            gross += leg
            realized += leg - frac * cost_r
            frac = 0.0
            status, exit_reason = "closed", "timeout"

    patch: dict = {"last_candle": str(last_dt), "cur_stop": float(cur_stop),
                   "tp1_done": tp1_done, "tp2_done": tp2_done,
                   "realized_r": float(realized), "gross_r": float(gross)}
    if status == "closed":
        # امتیاز نردبان از R ناخالص (خوانایی «رسیدن به کدام TP»)؛ تایم‌اوت با علامتِ R خالص
        pts = points_for(realized if exit_reason == "timeout" else gross, exit_reason)
        patch.update({"status": "closed", "exit_reason": exit_reason, "points": float(pts),
                      "result": result_label(realized, pts, exit_reason),
                      "closed_at": _now_iso(), "closed_price": float(d["close"].iloc[-1])})
    return patch


# ----------------------------------------------------------------------------- trade record
def make_trade_record(agent_name: str, coin: dict, pick: dict, exchange: str, interval: str) -> dict:
    """رکورد معامله‌ی جدید از یک برگزیده‌ی اسکن."""
    pos = pick["pos"]
    tps = list(pos.get("targets") or []) + [None, None, None]
    dec = int(coin.get("dec", 4))
    last_dt = coin.get("last_dt", "")
    if agent_name == COMMITTEE["name"]:
        color = COMMITTEE["color"]
        conf = int(pick.get("confidence", 0))
    else:
        color = AGENTS.get(agent_name, {}).get("color", "#94a3b8")
        conf = int(min(95, 40 + abs(float(pick.get("score", 0))) * 80))
    direction = int(pick["dir"])
    t1 = float(tps[0][0]) if tps[0] else float(pos["entry"])
    t2 = float(tps[1][0]) if tps[1] else t1
    t3 = float(tps[2][0]) if tps[2] else t2
    return {
        "id": uuid.uuid4().hex,
        "agent": agent_name,
        "color": color,
        "exchange": exchange,
        "interval": interval,
        "symbol": coin["symbol"],
        "direction": direction,
        "entry": float(pos["entry"]),
        "stop": float(pos["stop"]),
        "tp1": t1, "tp2": t2, "tp3": t3,
        "rr": float(pos.get("rr") or 0),
        "risk_pct": RISK_PCT,
        "score": round(float(pick.get("score", 0)), 3),
        "confidence": conf,
        "evidence": str(pick.get("evidence", ""))[:400],
        "adx": float(coin.get("adx", 0) or 0),
        "dec": dec,
        "status": "open",
        "opened_at": _now_iso(),
        "opened_candle": last_dt,
        "last_candle": last_dt,
        "cur_stop": float(pos["stop"]),
        "tp1_done": False,
        "tp2_done": False,
        "realized_r": 0.0,
        "gross_r": 0.0,
        "created_at": _now_iso(),
    }


# ----------------------------------------------------------------------------- screening (مرحله ۱)
def market_screen(exchange: str) -> tuple[list[dict], int, bool]:
    """غربالگری کل بازار بدون سقف تعداد.

    کل جفت‌ارزهای صرافی در یک فراخوانی گرفته می‌شود (همان تیکر ۲۴ ساعته که
    داشبورد استفاده می‌کند)، ارزهای مرده و استیبل‌کوین حذف می‌شوند و برای هر
    ارز «قدرت» محاسبه می‌شود:
        ۵۵٪ مومنتوم ۲۴ ساعته (قدرمطلق — هم پامپ هم دامپ، چون شورت هم داریم)
      + ۳۰٪ نقدینگی (لگاریتم گردش مالی)
      + ۱۵٪ دامنه‌ی نوسان روز (تفاضل سقف/کف به قیمت)
    هر چیزی که از صدک ۸۵ این امتیاز رد شود وارد تحلیل عمیق می‌شود — یعنی
    تعداد برگزیدگان بسته به حال بازار دینامیک است، نه یک عدد ثابت. فقط سقف
    فنی DEEP_CAP (محافظت از سهمیه‌ی API صرافی) روی تعداد اعمال می‌شود.

    خروجی: (برگزیدگان مرتب‌شده بر اساس قدرت, تعداد کل بازار, fallback فعال بود؟)
    """
    try:
        import app_base as B
        tops = B.fetch_top_coins(exchange, MIN_TURNOVER_M * 1e6, 10_000)
        full = (pd.concat([tops["volume"], tops["gainers"], tops["losers"]])
                .drop_duplicates("symbol").reset_index(drop=True))
        full = full[pd.to_numeric(full["price"], errors="coerce").fillna(0) > 0]
        full = full[full["turnoverM$"] >= MIN_TURNOVER_M]
        full = full[~full["symbol"].astype(str).str.upper().str.startswith(_STABLE_QUOTES)]
        if full.empty:
            raise ValueError("بعد از فیلترها بازار خالی بود")

        mom = pd.to_numeric(full["change%"], errors="coerce").abs().fillna(0.0)
        liq = np.log1p(pd.to_numeric(full["turnoverM$"], errors="coerce").clip(lower=0))
        rng = (pd.to_numeric(full["high"], errors="coerce") - pd.to_numeric(full["low"], errors="coerce")) \
            / pd.to_numeric(full["price"], errors="coerce").replace(0, np.nan) * 100.0
        rng = rng.clip(lower=0, upper=100).fillna(0.0)  # دامنه‌های مسخره‌ی تیکر خراب را خنثی کن

        strength = (0.55 * mom.rank(pct=True)
                    + 0.30 * liq.rank(pct=True)
                    + 0.15 * rng.rank(pct=True))
        full = full.assign(strength=strength).sort_values("strength", ascending=False)

        cut = float(np.percentile(strength, STRENGTH_TOP_PCT))
        top = full[full["strength"] >= cut].head(DEEP_CAP)
        finalists = [{"symbol": str(r["symbol"]), "price": float(r["price"]),
                      "change24": float(r["change%"]), "turnover": float(r["turnoverM$"]),
                      "strength": float(r["strength"])} for _, r in top.iterrows()]
        return finalists, int(len(full)), False
    except Exception:  # noqa: BLE001 — صرافی در دسترس نبود: ۱۲.major امن
        return ([{"symbol": s, "price": 0.0, "change24": 0.0, "turnover": 0.0,
                  "strength": 0.0} for s in POOL_FALLBACK], len(POOL_FALLBACK), True)


# ----------------------------------------------------------------------------- regime filter
def _regime_allows(regime: int, direction: int) -> bool:
    """آیا این جهت با رژیم فعلی بازار سازگار است؟ (regime=۰ یعنی فیلتر خاموش/نامشخص)"""
    return regime == 0 or direction == regime


def _regime_from_close(close: pd.Series) -> dict:
    """محاسبه‌ی خالص رژیم از سری قیمت — بدون شبکه، قابل تست.
    خروجی: {dir: +1/-1/0, ma, price, n} — dir=0 یعنی دیتا ناکافی/نامشخص."""
    s = pd.to_numeric(pd.Series(close), errors="coerce").dropna()
    price = float(s.iloc[-1]) if len(s) else 0.0
    if len(s) < REGIME_MA_N:
        return {"dir": 0, "ma": 0.0, "price": price, "n": int(len(s))}
    ma = float(s.rolling(REGIME_MA_N).mean().iloc[-1])
    d = 1 if price > ma else -1 if price < ma else 0
    return {"dir": d, "ma": ma, "price": price, "n": int(len(s))}


_REGIME_CACHE: dict = {}


def market_regime(exchange: str = "KuCoin", max_age_s: float = REGIME_TTL_S) -> dict:
    """رژیم بازار: BTC/USDT ۴ساعته بالای/زیر میانگین متحرک REGIME_MA_N کندل.
    کش ۱۰ دقیقه‌ای — هر رندر صفحه درخواست شبکه‌ی تازه نمی‌زند.
    اگر صرافی انتخابی جواب نداد، KuCoin امتحان می‌شود؛ اگر هیچ‌کدام → dir=0."""
    key = str(exchange)
    now = time.time()
    c = _REGIME_CACHE.get(key)
    if c and now - c["ts"] <= max_age_s:
        return c["val"]
    for ex in (exchange, "KuCoin"):
        try:
            sym = "BTC" if ex == "Lighter" else REGIME_SYMBOL
            d, _s, src = get_df(ex, sym, REGIME_TF, REGIME_MA_N + 120)
            val = _regime_from_close(d["close"])
            if val["dir"] == 0 and val["n"] < REGIME_MA_N:
                continue          # دیتای این صرافی کافی نبود → صرافی بعدی
            val["exchange"], val["src"] = ex, src
            _REGIME_CACHE[key] = {"ts": now, "val": val}
            return val
        except Exception:  # noqa: BLE001
            continue
    return {"dir": 0, "ma": 0.0, "price": 0.0, "n": 0, "exchange": exchange, "src": "none"}


def _setup_dir(d: pd.DataFrame, appetite: str = DEFAULT_APPETITE) -> tuple[bool, int, str]:
    """دروازه‌ی ستاپ بر اساس اشتهاي ریسک:
      strict   → موتور کامل walk-forward (ستاپ تازه + لبه‌ی اثبات‌شده روی همان نماد)
      balanced → ستاپ تازه در ۶ کندل اخیر (حتی بدون لبه‌ی اندازه‌گیری‌شده)
      hunter   → همیشه باز؛ جهت محدودکننده نیست
    خروجی: (عبور؟, جهتِ ستاپ (+1/-1/0), توضیح)"""
    try:
        import app_base as B
        if appetite == "hunter":
            return True, 0, "فیلتر ستاپ خاموش — ایجنت‌ها تصمیم می‌گیرند"
        if appetite == "balanced":
            bs = B.best_setup(d, recent_bars=6)
            dr = int(bs.get("dir") or 0)
            if dr != 0:
                why = ("ستاپ تازه + لبه‌ی اثبات‌شده" if bs.get("active")
                       else "ستاپ تازه (لبه‌ی این نماد هنوز اندازه‌گیری نشده)")
                return True, dr, why
            return False, 0, "ستاپ تازه‌ای در ۶ کندل اخیر نیست"
        # strict — همان موتور اعتبارسنجی کامل
        vp = B.setup_plan(d)
        ok = vp.get("status") == "active"
        dr = 1 if str(vp.get("direction", "")).startswith("لانگ") else -1 if str(vp.get("direction", "")).startswith("شورت") else 0
        return ok, dr, str(vp.get("why", ""))
    except Exception as e:  # noqa: BLE001
        return False, 0, f"اعتبارسنجی انجام نشد: {e}"


def scan_coin(exchange: str, symbol: str, interval: str, balance: float = START_EQUITY,
              fee_pct: float = FEE_PCT, appetite: str = DEFAULT_APPETITE, regime: int = 0,
              verdicts: dict | None = None, edge_mode: str = "off") -> dict:
    """یک ارز را از موتور مشترک ایجنت‌ها رد می‌کند و برای هر شرکت‌کننده تکلیف را روشن می‌کند.
    regime: +1 فقط لانگ · −1 فقط شورت · 0 فیلتر خاموش — فرصت خلاف رژیم «blocked_by_regime» می‌شود.
    verdicts/edge_mode (فاز ۵): حکم لبه‌ی هر ایجنت از بازپخش چندپنجره‌ای + حالت گیت —
    ایجنت بنچ‌شده اجازه‌ی باز کردن معامله ندارد («edge_blocked») و اجماع کمیسیون وزنی می‌شود
    (بدون دیتا همه وزن‌ها ۱ — رفتار عیناً مثل قبل)."""
    from core import edge as E   # ایمپورت تنبل — چرخه‌ی ایمپورت arena↔edge نمی‌سازد
    try:
        S_ = calculate_duel(exchange, symbol, interval, 300, balance, fee_pct)
    except Exception as exc:  # noqa: BLE001
        return {"symbol": symbol, "error": f"{type(exc).__name__}: {exc}"}

    d_ = S_["d"]
    v_ok, v_dir, v_txt = _setup_dir(d_, appetite)
    dt_col = d_["dt"] if "dt" in d_.columns else None
    out = {
        "symbol": S_["sym"], "error": None, "price": float(d_["close"].iloc[-1]), "dec": S_["dec"],
        "adx": float(d_["adx"].iloc[-1]) if "adx" in d_.columns and np.isfinite(d_["adx"].iloc[-1]) else 0.0,
        "v_ok": v_ok, "v_dir": v_dir, "v_txt": v_txt,
        "last_dt": str(dt_col.iloc[-1]) if dt_col is not None else "",
        "agents": {}, "committee": None,
    }

    for name, r in S_["results"].items():
        spec = AGENTS[name]
        pos, bt, sc, sig = r["position"], r["bt"], r["score"], r["sig"]
        ok_pre = (sig != 0 and np.sign(sc) == sig and abs(sc) >= spec["thr"]
                  and bt["pf"] > 1.0 and bt["total"] > 0
                  and v_ok and (appetite == "hunter" or v_dir == sig)
                  and pos["direction"] != 0 and float(pos.get("rr") or 0) >= 1.0)
        reg_ok = _regime_allows(regime, int(sig))
        edge_ok = E.allows(verdicts, name, edge_mode)
        ok = ok_pre and reg_ok and edge_ok
        top_rows = sorted(r["rows"], key=lambda x: -abs(float(x["سهم در تصمیم"])))[:2]
        evidence = " · ".join(f"{row['فاکتور']}: {row['مدرک (مشاهده‌ی واقعی)']}" for row in top_rows)
        out["agents"][name] = {
            "dir": int(sig), "score": float(sc), "ok": bool(ok), "pos": pos, "bt": bt,
            "evidence": evidence, "blocked_by_regime": bool(ok_pre and not reg_ok),
            "edge_blocked": bool(ok_pre and reg_ok and not edge_ok),
            "edge": (verdicts or {}).get(name),
            "quality": abs(sc) * min(2.5, max(float(bt["pf"]), 0.0)) * min(float(pos.get("rr") or 0), 3),
        }

    fd = S_["final_dir"]
    fpos = S_["final_pos"]
    n_agree = sum(1 for n, r in S_["results"].items() if fd != 0 and r["sig"] == fd)
    n_against = sum(1 for n, r in S_["results"].items() if fd != 0 and r["sig"] == -fd)
    n_neutral = sum(1 for n, r in S_["results"].items() if r["sig"] == 0)
    if fd != 0:
        _split = (f" · {n_against} مخالف" if n_against
                  else f" · {n_neutral} خنثی" if n_neutral else " · اجماع کامل")
        c_ev = f"اجماع {n_agree}/4 ایجنت{_split}"
    else:
        c_ev = "بدون اجماع جهت‌دار — کمیسیون می‌ایستد"
    w_ok, w_agree = E.committee_weighted_ok(verdicts, {n: r["sig"] for n, r in S_["results"].items()}, int(fd))
    c_ok_pre = (fd != 0 and abs(S_["final_s"]) >= 0.15 and w_ok
                and v_ok and (appetite == "hunter" or v_dir == fd)
                and fpos["direction"] != 0 and float(fpos.get("rr") or 0) >= 1.0)
    c_reg_ok = _regime_allows(regime, int(fd))
    out["committee"] = {
        "dir": int(fd), "score": float(S_["final_s"]), "ok": bool(c_ok_pre and c_reg_ok), "pos": fpos,
        "confidence": int(S_["confidence"]), "n_agree": int(n_agree), "w_agree": round(w_agree, 2),
        "evidence": c_ev, "blocked_by_regime": bool(c_ok_pre and not c_reg_ok),
    }
    return out


def run_scan(exchange: str, interval: str, balance: float = START_EQUITY,
             fee_pct: float = FEE_PCT, workers: int = 6,
             appetite: str = DEFAULT_APPETITE,
             verdicts: dict | None = None, edge_mode: str = "off") -> tuple[list[dict], list[str], dict]:
    """اسکن دومرحله‌ای: غربالگری کل بازار → تحلیل عمیق برگزیدگان (موازی).
    verdicts/edge_mode به scan_coin پاس داده می‌شود (گیت لبه — فاز ۵).
    خروجی: (نتایج تحلیل, خطاها, متادیتا {total/finalists/fallback/min_strength/appetite})"""
    finalists, total, fallback = market_screen(exchange)
    pool = [f["symbol"] for f in finalists] or list(POOL_FALLBACK)
    reg = market_regime(exchange)          # یک‌بار برای کل اسکن — نه هر ارز
    meta = {"total": int(total), "finalists": len(pool), "fallback": bool(fallback),
            "min_strength": float(finalists[-1]["strength"]) if finalists else 0.0,
            "appetite": appetite, "regime": reg}
    init = None
    try:
        from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx
        ctx = get_script_run_ctx()
        if ctx is not None:
            def init():  # noqa: E306
                add_script_run_ctx(threading_current(), ctx)
    except Exception:  # noqa: BLE001
        init = None
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(pool))), initializer=init) as ex:
        scans = list(ex.map(lambda s: scan_coin(exchange, s, interval, balance, fee_pct, appetite,
                                                int(reg["dir"]), verdicts, edge_mode), pool))
    errors = [f"{o['symbol']} — {o['error']}" for o in scans if o.get("error")]
    reg_blocked = sum(1 for o in scans for a in o.get("agents", {}).values() if a.get("blocked_by_regime")) \
        + sum(1 for o in scans if (o.get("committee") or {}).get("blocked_by_regime"))
    meta["regime_blocked"] = int(reg_blocked)
    meta["edge_blocked"] = sum(1 for o in scans for a in o.get("agents", {}).values() if a.get("edge_blocked"))
    return scans, errors, meta


def threading_current():
    import threading
    return threading.current_thread()


# ----------------------------------------------------------------------------- opening
def open_trades_from_scan(scans: list[dict], exchange: str, interval: str, store,
                          source: str = "manual", lab: dict | None = None,
                          regime_dir: int = 0,
                          dossier: dict | None = None) -> tuple[list[dict], int]:
    """از نتایج اسکن، بهترین برگزیده‌ها را برای هر شرکت‌کننده (با سهمیه و cooldown) باز می‌کند.
    source: برچسب منبع بازکردن («autopilot» از اتوپایلوت / «manual» از اپ)
    — فاز ۹: برای تفکیک دوره‌ها در گزارش روزانه و تحلیل سوددهی.
    فاز ۱۳ — lab (خروجی agent_lab.compute_adaptations) اختیاری است:
      · cool_mult>۱ برای ایجنتِ زنجیره‌ضرر → cooldown نماد/جهت × ضریب
      · ممنوعیت نماد (ایجنت، نماد) → هر جهتی
      · regime_only → فقط ورود هم‌جهت رژیم فعلی
    فاز ۱۴ — dossier (خروجی dossier.compute_dossier) اختیاری است — نسخه‌های پژوهشی:
      · suspended → ورود جدید ممنوع تا وقتی شرط پنجره برقرار است (خود-التیام)
      · max_pos → سقف پوزیشن هم‌زمان این ایجنت (کمتر از سقف عمومی)
      · score_floor → فقط سیگنال با |score| ≥ آستانه‌ی خودش
    بدون lab/dossier همه‌چیز مثل قبل است (backward compatible)."""
    existing = store.load_all()
    opens = [t for t in existing if t.get("status") == "open"]
    counts = Counter(t["agent"] for t in opens)
    global_open = len(opens)

    cool_min = COOLDOWN_CANDLES * INTERVAL_MIN.get(interval, 60)
    now_ts = pd.Timestamp.now(tz="UTC")
    cutoff = now_ts - pd.Timedelta(minutes=cool_min)

    # فاز ۱۳ — آماده‌سازی پنالتی‌های آزمایشگاه
    lab_agents: dict = (lab or {}).get("agents") or {}
    sym_banned: set[tuple[str, str]] = {
        (str(b.get("agent") or ""), str(b.get("symbol") or ""))
        for b in (lab or {}).get("symbol_bans") or []}
    lab_blocked = 0

    # فاز ۱۴ — آماده‌سازی نسخه‌های پرونده‌ی بهبود
    ds_agents: dict = (dossier or {}).get("agents") or {}
    ds_blocked = 0

    recent: set = set()
    for t in existing:
        if t.get("status") == "closed":
            nm = t.get("agent")
            mult = float((lab_agents.get(nm) or {}).get("cool_mult") or 1.0)
            cut_a = now_ts - pd.Timedelta(minutes=cool_min * max(1.0, mult))
            ca = to_ts(t.get("closed_at"))
            if ca is not pd.NaT and ca >= cut_a:
                recent.add((nm, t.get("symbol"), int(t.get("direction") or 0)))

    cands = []
    for coin in scans:
        if coin.get("error"):
            continue
        for name, a in coin.get("agents", {}).items():
            if a["ok"] and a["dir"] != 0:
                cands.append((float(a["quality"]), name, coin, a))
        c = coin.get("committee")
        if c and c["ok"]:
            cands.append((abs(float(c["score"])) * (1 + 0.2 * int(c["n_agree"])), COMMITTEE["name"], coin, c))
    cands.sort(key=lambda x: -x[0])

    opened, blocked_cool, blocked_full = [], 0, 0
    for _q, name, coin, a in cands:
        _ds = ds_agents.get(name) or {}
        _lim = _ds.get("limits") or _ds
        if _lim.get("suspended"):
            ds_blocked += 1         # فاز ۱۴: تعلیق مشروط — ورود جدید ممنوع
            continue
        if counts.get(name, 0) >= min(MAX_POS_PER_AGENT, int(_lim.get("max_pos") or MAX_POS_PER_AGENT)):
            blocked_full += 1
            continue
        if global_open >= GLOBAL_CAP:
            break
        if any(o["agent"] == name and o["symbol"] == coin["symbol"] for o in opens):
            continue
        _la = lab_agents.get(name) or {}
        if (name, coin["symbol"]) in sym_banned:
            lab_blocked += 1        # فاز ۱۳: نماد ممنوع‌شده‌ی آزمایشگاه
            continue
        if _la.get("regime_only") and int(a["dir"]) != regime_dir:
            lab_blocked += 1        # فاز ۱۳: انضباط رژیم — فقط هم‌جهت رژیم
            continue
        _floor = float(_lim.get("score_floor") or 0.0)
        if _floor > 0 and abs(float(a.get("score") or 0)) < _floor:
            ds_blocked += 1         # فاز ۱۴: فیلتر کیفیت — سیگنال ضعیف‌تر از میانه‌ی خودش
            continue
        if (name, coin["symbol"], int(a["dir"])) in recent:
            blocked_cool += 1
            continue
        rec = make_trade_record(name, coin, a, exchange, interval)
        rec["source"] = source
        store.insert(rec)
        opens.append(rec)
        counts[name] += 1
        global_open += 1
        opened.append(rec)
    return opened, blocked_cool + blocked_full + lab_blocked + ds_blocked


# ----------------------------------------------------------------------------- update loop
def update_all_trades(store) -> tuple[dict, list[dict]]:
    """همه‌ی معاملات باز را با کندل‌های تازه پیش می‌برد.
    خروجی: ({symbol: last_close}, [معاملاتی که همین الان بسته شدند])"""
    trades = store.load_all()
    opens = [t for t in trades if t.get("status") == "open"]
    live: dict[str, float] = {}
    just_closed: list[dict] = []
    groups: dict[tuple, list[dict]] = {}
    for t in opens:
        groups.setdefault((t.get("exchange"), t.get("interval"), t.get("symbol")), []).append(t)

    for (_ex, _itv, _sym), ts in groups.items():
        try:
            d, _sym_used, _src = get_df(_ex, _sym, _itv, 400)
        except Exception:  # noqa: BLE001
            continue
        if not isinstance(d, pd.DataFrame) or d.empty or "dt" not in d.columns:
            continue
        d = d.sort_values("dt").reset_index(drop=True)
        live[_sym] = float(d["close"].iloc[-1])
        for t in ts:
            try:
                patch = simulate_trade(t, d)
            except Exception:  # noqa: BLE001
                continue
            if patch:
                store.update(t["id"], patch)
                if patch.get("status") == "closed":
                    just_closed.append({**t, **patch})
    return live, just_closed


# ----------------------------------------------------------------------------- leaderboard
# ----------------------------------------------------------------------------- stats
# معیارهای واقعی «آیا این سیستم سوده است؟» — همه از R خالص (بعد از کارمزد+لغزش).
# قانون تصمیم: تا ۳۰ معامله هیچ عددی اعتبار آماری ندارد؛ ۳۰ تا ۱۰۰ فقط جهت‌گیری؛
# فقط با ۱۰۰+ معامله و انتظاری مثبت می‌شود به سیستم اعتماد کرد (و حتی آن‌وقت
# اول روی حساب کوچک).
SAMPLE_MIN = 30
SAMPLE_OK = 100


def wilson_ci(wins: int, n: int) -> tuple[float, float]:
    """بازه‌ی اطمینان ۹۵٪ نرخ برد (فاصله‌ی امتیاز ویلسون) — پورت از TITAN.
    صداقت آماری: «وین‌ریت ۵۴٪» تنها با نمونه‌ی بزرگ معنی دارد؛ این بازه
    نشان می‌دهد با همین نمونه، نرخ برد واقعی بین چند تا چند درصد است.
    خروجی: (کمینه٪، بیشینه٪) — n=0 → (0.0, 100.0) یعنی «هنوز نمی‌دانیم»."""
    if n <= 0:
        return (0.0, 100.0)
    w = max(0, min(int(wins), int(n)))
    p = w / float(n)
    z = 1.96
    den = 1.0 + z * z / n
    center = (p + z * z / (2.0 * n)) / den
    half = z * math.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n)) / den
    return (max(0.0, center - half) * 100.0, min(100.0, center + half) * 100.0)


def _maxdd_from_rs(rs: list[float]) -> float:
    """بیشترین افت سرمایه (٪) روی منحنی مرکب با ریسک ثابت ۱٪ — خالص R پشت سر هم."""
    eq = peak = 1.0
    mdd = 0.0
    for r in rs:
        eq = max(0.0, eq * (1.0 + RISK_PCT / 100.0 * float(r)))
        peak = max(peak, eq)
        if peak > 0:
            mdd = max(mdd, (peak - eq) / peak)
    return mdd * 100.0


def arena_summary(closed: list[dict]) -> dict:
    """آمار کل میدان از معاملات بسته‌شده — مبنای تصمیم «سوده است یا نه؟».
      انتظاری = میانگین R خالص هر معامله (بعد از کارمزد و لغزش)
      PF = مجموع بردها ÷ مجموع باخت‌ها · پی‌آف = میانگین برد ÷ میانگین باخت
      MaxDD = بیشترین افت ایکوییتی ترکیبی (انگار یک حساب با ۱٪ ریسک همه را گرفته بود)
    reliability: low (<۳۰) · mid (۳۰–۹۹) · ok (۱۰۰+)"""
    ts = sorted(closed, key=lambda t: str(t.get("closed_at") or ""))
    rs = [float(t.get("realized_r") or 0.0) for t in ts]
    n = len(rs)
    wins = [r for r in rs if r > 0.0]
    losses = [r for r in rs if r < 0.0]
    gross, loss_sum = sum(wins), -sum(losses)
    pf = (gross / loss_sum) if loss_sum > 0 else (99.0 if gross > 0 else 0.0)
    avg_win = (gross / len(wins)) if wins else 0.0
    avg_loss = (loss_sum / len(losses)) if losses else 0.0
    payoff = (avg_win / avg_loss) if avg_loss > 0 else (99.0 if avg_win > 0 else 0.0)
    return {
        "n": n,
        "expectancy": (sum(rs) / n) if n else 0.0,
        "total_r": sum(rs),
        "pf": min(pf, 99.0),
        "payoff": min(payoff, 99.0),
        "winrate": len(wins) / max(1, len(wins) + len(losses)) * 100.0,
        "wins": len(wins), "losses": len(losses),
        "winrate_ci": wilson_ci(len(wins), len(wins) + len(losses)),
        "maxdd": _maxdd_from_rs(rs),
        "reliability": "low" if n < SAMPLE_MIN else "mid" if n < SAMPLE_OK else "ok",
    }


def _streak(points_hist: list[float]) -> int:
    s = 0
    for p in reversed(points_hist):
        if p == 0:
            break
        sign = 1 if p > 0 else -1
        if s == 0 or (s > 0) == (sign > 0):
            s += sign
        else:
            break
    return s


def leaderboard(closed: list[dict], opens: list[dict]) -> list[dict]:
    """جدول قهرمانی: یک ردیف برای هر شرکت‌کننده (حتی بدون معامله)."""
    rows = []
    for part in participants():
        name = part["name"]
        ts = [t for t in closed if t.get("agent") == name]
        os_ = [t for t in opens if t.get("agent") == name]
        ts_sorted = sorted(ts, key=lambda t: str(t.get("closed_at") or ""))
        rs = [float(t.get("realized_r") or 0.0) for t in ts_sorted]
        pts = [float(t.get("points") or 0.0) for t in ts_sorted]
        wins = sum(1 for p in pts if p > 0)
        losses = sum(1 for p in pts if p < 0)
        wins_list = [r for r in rs if r > 0]
        losses_list = [r for r in rs if r < 0]
        avg_win = (sum(wins_list) / len(wins_list)) if wins_list else 0.0
        avg_loss = (-sum(losses_list) / len(losses_list)) if losses_list else 0.0
        payoff = (avg_win / avg_loss) if avg_loss > 0 else (99.0 if avg_win > 0 else 0.0)
        eq = START_EQUITY
        for r in rs:
            eq *= (1 + RISK_PCT / 100.0 * r)
        eq = max(0.0, eq)
        gross = sum(r for r in rs if r > 0)
        loss_sum = -sum(r for r in rs if r < 0)
        pf = (gross / loss_sum) if loss_sum > 0 else (99.0 if gross > 0 else 0.0)
        wr = wins / max(1, wins + losses) * 100
        rows.append({
            "agent": name, "color": part["color"], "kind": part["kind"],
            "equity": eq, "trades": len(ts), "open": len(os_),
            "wins": wins, "losses": losses, "winrate": wr,
            "winrate_ci": wilson_ci(wins, wins + losses),
            "total_r": sum(rs),
            "pf": min(pf, 99.0), "points": sum(pts), "streak": _streak(pts),
            "avg_r": (sum(rs) / len(rs)) if rs else 0.0,
            "payoff": min(payoff, 99.0), "maxdd": _maxdd_from_rs(rs),
            "best_r": max(rs) if rs else 0.0, "worst_r": min(rs) if rs else 0.0,
            "_history": ts_sorted,
        })
    rows.sort(key=lambda r: (-r["points"], -r["total_r"]))
    return rows


def equity_curve(closed_for_agent: list[dict]) -> list[float]:
    ts_sorted = sorted(closed_for_agent, key=lambda t: str(t.get("closed_at") or ""))
    eq, out = START_EQUITY, [START_EQUITY]
    for t in ts_sorted:
        eq = max(0.0, eq * (1 + RISK_PCT / 100.0 * float(t.get("realized_r") or 0.0)))
        out.append(eq)
    return out
