# -*- coding: utf-8 -*-
"""core/showcase_daily.py — آلبومِ روزانه‌ی ارائه‌ی تلگرام
=========================================================
هر روز یک‌بار: موتورِ اپ بازار را می‌کَود، ستاپ‌های فعالِ QC-دار را پیدا می‌کند،
تصاویرِ مهرشده با «QC 14/14» می‌سازد و یک پیامِ خلاصه‌ی فارسی + آلبومِ عکس
به چت تلگرام می‌فرستد (از همان باتِ موجود با Secretهای TELEGRAM_BOT_TOKEN /
TELEGRAM_CHAT_ID).

اجرا:  python -m core.showcase_daily      (روی GitHub Actions هر روز ۱۰:۰۰ تهران)
منطق:
  • اگر بات تنظیم نباشد → بی‌صدا رد می‌شود (exit 0 — Actions قرمز نمی‌شود)
  • اگر اسکنِ بازار به‌کلی شکست بخورد → یک notify_failure می‌فرستد (exit 0)
  • هیچ‌وقت exception بالا نمی‌دهد — ارائه هرگز نباید توقفت کند
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone, timedelta

from core import telegram as TG

sys.path.insert(0, __file__.rsplit("/", 2)[0])  # ریشه‌ی پروژه برای import اپ

import app_base as nq  # noqa: E402

EXCHANGE = "OKX"
CANDIDATES = [
    "BTC-USDT", "ETH-USDT", "SOL-USDT", "XRP-USDT", "BNB-USDT",
    "DOGE-USDT", "ADA-USDT", "AVAX-USDT", "LINK-USDT", "TON-USDT",
    "SUI-USDT", "NEAR-USDT", "LTC-USDT", "DOT-USDT",
]
INTERVALS = ["1hour", "2hour", "4hour", "1day"]
MAX_IMAGES = 8

TEHRAN = timezone(timedelta(hours=3, minutes=30))
_WEEK_FA = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه", "شنبه", "یکشنبه"]


# ------------------------------------------------------------------ تحلیل
def analyse_one(symbol: str, interval: str, exchange: str = EXCHANGE):
    """خط لوله‌ی کامل موتور + دروازه‌ی QC برای یک نماد/تایم‌فریم — dict یا None."""
    try:
        df = nq.fetch_candles(exchange, symbol, interval, limit=500)
        d = nq.add_indicators(df)
        if len(d) < 60:
            return None
        score_s, _ = nq.confluence(d)
        score = float(score_s.iloc[-1])
        lv = nq.swing_levels(d)
        plan = nq.setup_plan(d, lv)
        price = float(d["close"].iloc[-1])
        dec = 2 if price >= 1000 else 4 if price >= 1 else 6
        qc = plan.get("qc") or {}
        return {
            "symbol": symbol, "interval": interval, "d": d, "plan": plan,
            "levels": lv, "score": score, "dec": dec, "price": price,
            "qc_ok": not qc.get("issues"),
            "active": plan.get("entry") is not None,
            "rr": plan.get("rr") or 0,
        }
    except Exception as exc:  # noqa: BLE001 — یک نماد خراب، کل گزارش را نمی‌بُرد
        print(f"  ! {symbol} {interval}: {type(exc).__name__}: {exc}", flush=True)
        return None


def collect(exchange: str = EXCHANGE, intervals=None, candidates=None) -> list:
    """اسکنِ همه‌ی نمادها — فقط نتایجِ QC-پاس‌شده برمی‌گردد."""
    intervals = list(intervals or INTERVALS)
    candidates = list(candidates or CANDIDATES)
    out = []
    for interval in intervals:
        for sym in candidates:
            r = analyse_one(sym, interval, exchange)
            if r and r["qc_ok"]:
                out.append(r)
    return out


def select(results: list, max_images: int = MAX_IMAGES) -> list:
    """انتخابِ نهایی — اول ستاپ‌های فعال (بر اساس قدرت + R:R)، بعد نام‌های شاخص."""
    actives = sorted([r for r in results if r["active"]],
                     key=lambda r: (abs(r["score"]) + 10 * r["rr"]), reverse=True)
    waits = [r for r in results if not r["active"]]
    btc_eth = [r for r in waits if r["symbol"] in ("BTC-USDT", "ETH-USDT")]
    other_waits = sorted([r for r in waits if r not in btc_eth],
                         key=lambda r: abs(r["score"]), reverse=True)
    picked = actives[:max_images]
    for r in btc_eth + other_waits:
        if len(picked) >= max_images:
            break
        if r not in picked:
            picked.append(r)
    return picked


# ------------------------------------------------------------------ قالب‌بندی
def _iv_fa(iv: str) -> str:
    return {"1hour": "1h", "2hour": "2h", "4hour": "4h", "1day": "1d"}.get(iv, iv)


def describe_plain(res) -> str:
    """یک خط توصیفِ فارسی برای README و لاگ."""
    p = res["plan"]
    if res["active"]:
        d1 = res["dec"]
        return (f"{res['symbol']} ({_iv_fa(res['interval'])}) — {p['direction']} · "
                f"ورود {p['entry']:,.{d1}f} · حدضرر {p['stop']:,.{d1}f} · "
                f"هدفِ اول {p['targets'][0][0]:,.{d1}f} · "
                f"R:R یک‌به‌{p['rr']} · بردِ TP1 در تست {p['confidence']}٪")
    return (f"{res['symbol']} ({_iv_fa(res['interval'])}) — ⏸ انتظار "
            f"(ستاپِ معتبر نبود — محافظتِ QC) · امتیاز {res['score']:+.0f}")


def build_summary_text(picked: list) -> str:
    """پیامِ خلاصه‌ی روزانه — HTML تلگرام، سقفِ ۳۹۰۰ نویسه."""
    now = datetime.now(TEHRAN)
    head = (f"📊 <b>گزارش روزانه‌ی NorthmanQuant</b>\n"
            f"{_WEEK_FA[now.weekday()]} · {now.strftime('%Y-%m-%d %H:%M')} تهران "
            f"· داده‌ی زنده‌ی {EXCHANGE}")
    actives = [r for r in picked if r["active"]]
    waits = [r for r in picked if not r["active"]]
    lines = [head, ""]
    if actives:
        lines.append(f"🟢 <b>ستاپ‌های فعالِ امروز: {len(actives)}</b>")
        lines.append("")
        for r in actives[:6]:
            p = r["plan"]
            d1 = r["dec"]
            lines.append(
                f"• <b>{r['symbol']}</b> ({_iv_fa(r['interval'])}) — {p['direction']}\n"
                f"  ورود <b>{p['entry']:,.{d1}f}</b> · حدضرر {p['stop']:,.{d1}f} · "
                f"هدفِ اول {p['targets'][0][0]:,.{d1}f} · "
                f"بردِ TP1 در تست {p['confidence']}٪")
        lines.append("")
    if waits:
        wl = "، ".join(f"{r['symbol']} ({_iv_fa(r['interval'])})" for r in waits[:8])
        lines.append(f"⏸ <b>بدون ستاپِ معتبر: {len(waits)}</b> — {wl}")
        lines.append("اینجا موتور عمداً معامله نداده — ستاپِ تست‌شده نبود؛ این محافظت است، نه ضعف.")
        lines.append("")
    lines.append("✅ هر سیگنال قبل از انتشار <b>۱۴ بازرسیِ خودکار</b> (سلامتِ داده + سلامتِ طرح) "
                 "را پاس می‌کند — مُهرِ سبزِ QC 14/14 روی همه‌ی تصاویر.")
    lines.append("📷 تصاویرِ نمودار در پیامِ بعدی…")
    return "\n".join(lines)[:TG.MAX_TEXT]


def build_album_caption() -> str:
    now = datetime.now(TEHRAN)
    return (f"📷 NorthmanQuant — نمودارهای مهرشده با QC 14/14 · "
            f"{now.strftime('%H:%M')} تهران\n"
            f"خطِ سبزِ بالای هر تصویر = ۱۴ بازرسیِ خودکار، همه پاس شده")


def build_album(picked: list) -> list:
    """ساختِ تصاویر — لیستِ (نام‌فایل، بایت‌های PNG)."""
    out = []
    for i, r in enumerate(picked, 1):
        try:
            png = nq.render_analysis_png(
                r["d"], r["plan"], r["levels"], r["score"],
                r["symbol"], EXCHANGE, r["interval"], r["dec"])
            if not png or len(png) < 5000:
                continue
        except Exception as exc:  # noqa: BLE001 — یک تصویر خراب، آلبوم را نمی‌بُرد
            print(f"  ! render {r['symbol']}: {type(exc).__name__}: {exc}", flush=True)
            continue
        state = "LONG" if str(r["plan"]["direction"]).startswith("لانگ") else \
                "SHORT" if r["active"] else "WAIT"
        out.append((f"{i:02d}_{r['symbol'].replace('-', '')}_{r['interval']}_{state}.png", png))
    return out


def build_media_payload(images: list, caption: str) -> tuple:
    """ساختِ بارِ JSON و فایل‌ها برای sendMediaGroup — جدا شده تا تستِ بدونِ شبکه شود."""
    return TG._build_album_parts(images, caption)


# ------------------------------------------------------------------ اجرا
def run() -> str:
    """کلِ جریانِ روزانه — رشته‌ی وضعیت برمی‌گرداند، هیچ‌وقت exception نمی‌دهد."""
    if not TG.enabled():
        print("🔇 تلگرام تنظیم نیست — TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID — رد شد", flush=True)
        return "غیرفعال"
    try:
        picked = select(collect())
    except Exception as exc:  # noqa: BLE001
        TG.notify_failure("showcase-daily/collect", f"{type(exc).__name__}: {exc}")
        return "خطای اسکن"
    if not picked:
        TG.notify_failure("showcase-daily", "اسکن انجام شد ولی هیچ نتیجه‌ی QC-داری نیامد (شبکه/صرافی؟)")
        return "بدون نتیجه"
    text = build_summary_text(picked)
    ok_text = TG.send(text)
    images = build_album(picked)
    ok_album = TG.send_album(images, build_album_caption()) if images else False
    print(f"✅ متن: {'OK' if ok_text else 'FAIL'} · آلبوم {len(images)} تصویر: "
          f"{'OK' if ok_album else 'FAIL'}", flush=True)
    for r in picked:
        print("  · " + describe_plain(r), flush=True)
    return "فرستاده شد" if (ok_text and ok_album) else "ناقص"


def main() -> int:
    print(f"== NorthmanQuant — آلبومِ روزانه‌ی تلگرام ({EXCHANGE}) ==", flush=True)
    status = run()
    print(f"وضعیت: {status}", flush=True)
    return 0  # Actions هیچ‌وقت قرمز نمی‌شود — وضعیت از طریق خود تلگرام معلوم است


if __name__ == "__main__":
    raise SystemExit(main())
