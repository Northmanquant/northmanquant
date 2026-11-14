# -*- coding: utf-8 -*-
"""core/team_room.py — اتاقِ تیمِ تحلیل: چهار عاملِ مستقل روی یک ارز
====================================================================
درخواستِ کاربر: «یک تیم سرِ یک ارز تحلیل کنه؛ هرکدوم مسئول یک چیز باشه:
ربات خبری بفهمه قیمت چرا تکون می‌خوره، ربات دیدبان دنبال حجمِ مشکوک بگرده،
ربات چارت نقطه‌ی ورود/خروج بده، و شکاک دنبال دلیل و منطق از ایجنت‌ها باشه.»

عامل‌ها (بدون LLM — همه‌ی استدلال از خودِ داده و تیترهای واقعی ساخته می‌شود،
پس قابلِ تست و تکرار است و هیچ‌وقت «از خودش» حرف نمی‌زند):
  📰 خبرنگار  — چرا قیمت حرکت کرد؟ تیترهای واقعی RSS + خوانشِ حرکت/حجم
  👁️ دیدبان   — جست‌وجوی حجمِ مشکوک: اسپایک، churn/واش‌ترید، واگراییِ حجم
  📊 چارت‌خوان — ورود/حدضرر/اهداف از همان موتورِ QC-دارِ اپ (setup_plan) —
                یعنی همان سیگنالی که صفحه‌ی تحلیل می‌دهد، نه قاعده‌ی موازی
  💼 مدیرِ ریسک — اندازه‌ی پوزیشن از سرمایه‌ی کاربر: قانونِ ۱–۲٪، کارمزد، بدونِ اهرم
  🧐 شکاک     — هر ادعا را با داده محک می‌زند: تایید/اعتراض/هشدار + دلیل
                (ریاضیاتِ مدیرِ ریسک را هم بازمحاسبه می‌کند!)

قواعدِ اتاق:
  • هر پیام دو بخش دارد: «متن» و «مدرک/دلیل» — پیامِ بی‌دلیل ممنوع.
  • شکاک اعتراضِ سخت داشته باشد → حکمِ تیم «صبر» است، حتی اگر چارت سیگنال داده باشد.
  • اگر داده/خبر نیست، عامل صادقانه می‌گوید «نمی‌دانم» — حدس نمی‌زند.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd

sys_root = __file__.rsplit("/", 2)[0]
import sys  # noqa: E402
sys.path.insert(0, sys_root)

import app_base as nq  # noqa: E402
from core import news as NEWS  # noqa: E402
from core import kronos_witness as KW  # noqa: E402

EXCHANGE_DEFAULT = "OKX"
INTERVAL_DEFAULT = "1hour"
INTERVALS = ["1hour", "2hour", "4hour", "1day"]
NEWS_WINDOW = 24          # چند کندلِ اخیر «حرکتِ اخیر» حساب شود
SPIKE_X = 2.5             # کندلِ چندبرابرِ میانگینِ حجم = اسپایک
WASH_X = 3.0              # اسپایکِ شدید + رنجِ بسته = churn/واش‌ترید
FEE_RT = 0.002            # کارمزدِ رفت‌وبرگشت (~۰.۱٪ هر سمت، taker)
MAX_RISK_PCT = 3.0        # سقفِ ریسکِ منطقی در هر معامله — بالاتر = اعتراضِ شکاک
TEHRAN = timezone(timedelta(hours=3, minutes=30))

# --------------------------------------------------------------- تیترها
# (کلمه، جهت) — با مرزِ کلمه روی تیترِ بزرگ‌شده؛ اول بلندترها تا «ETF APPROVAL» نصف نشود
_BULL_WORDS = [
    ("ETF APPROVAL", 1), ("APPROVES", 1), ("ALL-TIME HIGH", 1), ("BREAKOUT", 1),
    ("RECOVER", 1), ("REBOUND", 1), ("PARTNERSHIP", 1), ("ADOPTION", 1),
    ("UPGRADE", 1), ("RECORD", 1), ("INFLOW", 1), ("LAUNCHES", 1), ("LAUNCH", 1),
    ("SURGE", 1), ("SOARS", 1), ("RALLY", 1), ("JUMPS", 1), ("PUMPS", 1),
    ("GAINS", 1), ("BULLISH", 1), ("ACCUMULAT", 1), ("BOOST", 1), ("INVESTS", 1),
    ("INVESTMENT", 1), ("STAKE", 1), ("RISES", 1), ("CLIMBS", 1),
]
_BEAR_WORDS = [
    ("ETF REJECT", -1), ("REJECTS", -1), ("ALL-TIME LOW", -1), ("HALTED", -1),
    ("FREEZES", -1), ("SEIZES", -1), ("BANKRUPT", -1), ("LIQUIDATION", -1),
    ("DELIST", -1), ("INVESTIGATION", -1), ("EXPLOIT", -1), ("FRAUD", -1),
    ("SCAM", -1), ("LAWSUIT", -1), ("SUES", -1), ("BANS", -1), ("BAN", -1),
    ("OUTFLOW", -1), ("CRASH", -1), ("PLUNGE", -1), ("SINKS", -1), ("DUMPS", -1),
    ("HACK", -1), ("BREACH", -1), ("PROBE", -1), ("BEARISH", -1), ("SLASH", -1),
    ("LOSES", -1), ("WARN", -1), ("TUMBLES", -1), ("SLIDES", -1),
]


def read_title(title: str) -> int:
    """جهتِ تیتر از کلمات کلیدی — +1 مثبت، -1 منفی، 0 خنثی/نامشخص."""
    t = re.sub(r"[^A-Z ]", " ", str(title or "").upper())
    for w, s in _BEAR_WORDS + _BULL_WORDS:  # منفی‌ها اول — حساس‌ترند
        if re.search(rf"\b{w}", t):
            return s
    return 0


def base_of(symbol: str) -> str:
    """«BTC-USDT» → «BTC» — برای تگِ تیترها."""
    return str(symbol).split("-")[0].split("/")[0].upper()


def _fmt(p, dec: int) -> str:
    return nq.fmt_price(p, dec)


def _chg_vol(d: pd.DataFrame) -> tuple[float, float]:
    """(درصدِ حرکتِ اخیر، نسبتِ حجمِ آخرین کندل به میانگینِ ~۱۰۰ کندل)."""
    c = d["close"].to_numpy(dtype=float)
    v = d["volume"].to_numpy(dtype=float)
    w = min(NEWS_WINDOW, max(1, len(c) - 1))
    chg = (c[-1] / c[-1 - w] - 1.0) * 100.0 if c[-1 - w] else 0.0
    prev = v[-101:-1] if len(v) > 101 else v[:-1]
    m = float(np.mean(prev)) if len(prev) else 0.0
    ratio = float(v[-1] / m) if m > 0 else 0.0
    return float(chg), ratio


# ================================================================ عامل‌ها
def news_agent(symbol: str, d: pd.DataFrame, dec: int,
               items: list | None, stale: bool) -> dict:
    """📰 چرا قیمت تکون خورد؟ تیترهای واقعیِ نماد + خوانشِ حرکت/حجم."""
    msgs: list[dict] = []
    claims: list[dict] = []
    base = base_of(symbol)
    chg, vr = _chg_vol(d)
    c = float(d["close"].iloc[-1])
    move_side = 1 if chg > 0.5 else -1 if chg < -0.5 else 0

    hits = [it for it in (items or []) if base in (it.get("symbols") or [])][:3]
    if stale:
        msgs.append({"text": "فیدِ خبری الان در دسترس نبود — پس فقط از خودِ داده‌ی بازار حرف می‌زنم، نه از خبر.",
                     "why": "هیچ‌کدام از ۳ منبع جواب نداد؛ حدسِ خبری ممنوع."})
    elif not hits:
        msgs.append({"text": f"در تیترهای تازه‌ی ۳ منبع، هیچ خبری برای {base} نیست — "
                             f"پس حرکتِ اخیر را باید از خودِ چارت خواند، نه از خبر.",
                     "why": "تگِ نماد داخل تیتر پیدا نشد؛ خبرِ غایب هم اطلاعات است."})
    for it in hits:
        side = read_title(it.get("title"))
        if side == 0:
            msgs.append({"text": f"«{it.get('title')}» ({it.get('source')}) — محتوایش جهتِ روشنی ندارد، حسابش نمی‌کنم.",
                         "why": "هیچ کلمه‌ی کلیدیِ جهت‌دار در تیتر نبود."})
            continue
        fa = "مثبت" if side > 0 else "منفی"
        msgs.append({"text": f"خبرِ {fa}: «{it.get('title')}» ({it.get('source')}).",
                     "why": f"کلمه‌ی کلیدیِ جهت‌دار در تیتر + زمان: {it.get('ts') or 'نامشخص'}"})
        claims.append({"by": "news", "side": side, "claim": it.get("title", "")[:120],
                       "evidence": f"{it.get('source')} · {it.get('ts') or '؟'}"})

    vol_word = ("حجم بالا رفته — پولِ واقعی پشت حرکت است" if vr >= 1.5 else
                "حجم همیشه‌ی روز است — حرکتِ معمولی" if vr >= 0.7 else
                "حجم کمتر از همیشه — حرکتِ بی‌پشتیبان")
    msgs.append({"text": f"خودِ داده: قیمت در {NEWS_WINDOW} کندلِ اخیر <b>{chg:+.1f}٪</b> راه رفته "
                         f"و حجمِ آخرین کندل <b>{vr:.1f}×</b> میانگین است — {vol_word}.",
                 "why": f"close آخر {c:,.{dec}f} نسبت به {NEWS_WINDOW} کندل قبل + مقایسه‌ی volume با میانگینِ بلندمدت"})
    if abs(chg) > 2.0 and vr < 0.8:
        claims.append({"by": "news", "side": 0,
                       "claim": f"حرکتِ {chg:+.1f}٪ بدون پشتیبانیِ حجم ({vr:.1f}×) — کیفیتِ حرکت پایین",
                       "evidence": "قانون: حرکتِ بزرگ باید با حجمِ بزرگ همراه باشد"})
    elif move_side != 0:
        claims.append({"by": "news", "side": move_side,
                       "claim": f"حرکتِ {chg:+.1f}٪ اخیر با حجمِ {vr:.1f}× همراه است",
                       "evidence": f"volume آخرین کندل / میانگینِ ۱۰۰ کندل = {vr:.2f}"})
    return {"key": "news", "emoji": "📰", "name": "خبرنگار",
            "role": "می‌فهمد قیمت چرا تکون خورده — خبرِ واقعی یا فقط داده‌ی بازار",
            "msgs": msgs, "claims": claims, "ok": True}


def watchdog_agent(d: pd.DataFrame, dec: int) -> dict:
    """👁️ دیدبانِ حجم — دنبال حجمِ مشکوک: اسپایک، churn، واگرایی."""
    msgs: list[dict] = []
    flags: list[dict] = []
    claims: list[dict] = []
    v = d["volume"].to_numpy(dtype=float)
    o = d["open"].to_numpy(dtype=float)
    h = d["high"].to_numpy(dtype=float)
    l = d["low"].to_numpy(dtype=float)
    c = d["close"].to_numpy(dtype=float)
    atr = float(d["atr"].iloc[-1]) if "atr" in d and np.isfinite(d["atr"].iloc[-1]) and d["atr"].iloc[-1] > 0 \
        else float(c[-1]) * 0.01

    prev = v[-101:-1] if len(v) > 101 else v[:-1]
    m = float(np.mean(prev)) if len(prev) else 0.0
    sd = float(np.std(prev)) if len(prev) > 2 else 0.0
    ratio = float(v[-1] / m) if m > 0 else 0.0
    z = float((v[-1] - m) / sd) if sd > 0 else 0.0

    msgs.append({"text": f"حجمِ آخرین کندل <b>{ratio:.1f}×</b> میانگینِ ۱۰۰ کندل است (z={z:+.1f}).",
                 "why": "میانگین/انحرافِ معیارِ volume در ~۱۰۰ کندلِ اخیر — عدد، نه حس"})

    spikes = [i for i in range(max(0, len(v) - 10), len(v)) if m > 0 and v[i] > SPIKE_X * m]
    if spikes:
        msgs.append({"text": f"در ۱۰ کندلِ اخیر <b>{len(spikes)}</b> اسپایکِ حجم (> {SPIKE_X}× میانگین) دیده‌ام.",
                     "why": f"شاخصِ کندل‌ها: {spikes} — حجمِ هرکدام چندبرابرِ میانگینِ بلندمدت"})
        claims.append({"by": "watchdog", "side": 0,
                       "claim": f"{len(spikes)} اسپایکِ حجم در ۱۰ کندل اخیر",
                       "evidence": f"v > {SPIKE_X}× میانگینِ ۱۰۰ کندل"})

    rng = float(h[-1] - l[-1])
    if ratio >= WASH_X and atr > 0 and rng < 0.6 * atr:
        flags.append({"level": "red", "side": 0,
                      "text": f"🚩 <b>حجمِ مشکوک (churn)</b>: حجم {ratio:.1f}× ولی رنجِ کندل فقط "
                              f"{rng / atr:.1f}×ATR — خرید و فروشِ زیاد بدون حرکتِ قیمت.",
                      "why": "قانونِ دیدبان: حجمِ ≥3× میانگین + رنجِ <0.6×ATR = churn/واش‌تریدِ احتمالی"})
        claims.append({"by": "watchdog", "side": 0,
                       "claim": "حجمِ مشکوک روی آخرین کندل (churn) — قبل از اعتماد به هر سیگنالی حل شود",
                       "evidence": f"ratio={ratio:.1f} · range={rng / atr:.2f}×ATR"})
    elif z >= 2.5:
        fa = "صعودی" if c[-1] >= o[-1] else "نزولی"
        flags.append({"level": "yellow", "side": 1 if c[-1] >= o[-1] else -1,
                      "text": f"اسپایکِ واقعیِ حجمِ {fa} (z=+{z:.1f}) — پولِ تازه وارد است، دنبالش کن.",
                      "why": "z-scoreِ حجم > 2.5 یعنی از ۹۹٪ کندل‌های اخیر پرحجم‌تر"})
        claims.append({"by": "watchdog", "side": 1 if c[-1] >= o[-1] else -1,
                       "claim": f"اسپایکِ حجمِ {fa} (z={z:.1f})",
                       "evidence": f"z-score بر پایه‌ی ۱۰۰ کندل"})

    if len(c) >= 6:
        cp = float(np.mean((c[-5:] - l[-5:]) / np.maximum(h[-5:] - l[-5:], 1e-12)))
        if cp >= 0.65:
            msgs.append({"text": "در ۵ کندلِ اخیر، بستن‌ها نزدیکِ سقفِ رنج است — <b>فشارِ خریدِ</b> غالب.",
                         "why": f"میانگینِ (close−low)/(high−low) در ۵ کندل = {cp:.2f}"})
            claims.append({"by": "watchdog", "side": 1, "claim": "فشارِ خرید در کندل‌های اخیر",
                           "evidence": f"close-position = {cp:.2f}"})
        elif cp <= 0.35:
            msgs.append({"text": "در ۵ کندلِ اخیر، بستن‌ها نزدیکِ کفِ رنج است — <b>فشارِ فروشِ</b> غالب.",
                         "why": f"میانگینِ (close−low)/(high−low) در ۵ کندل = {cp:.2f}"})
            claims.append({"by": "watchdog", "side": -1, "claim": "فشارِ فروش در کندل‌های اخیر",
                           "evidence": f"close-position = {cp:.2f}"})

    if not flags:
        msgs.append({"text": "چیزِ مشکوکی پیدا نکردم — حجم با روندِ عادی سازگار است.",
                     "why": "نه churn بود، نه اسپایکِ z>2.5، نه تضادِ جهت/حجم"})
    for f in flags:
        msgs.append({"text": f["text"], "why": f["why"]})
    return {"key": "watchdog", "emoji": "👁️", "name": "دیدبان",
            "role": "دنبال حجمِ مشکوک می‌گردد — اسپایک، churn، فشارِ پنهانِ خرید/فروش",
            "msgs": msgs, "claims": claims, "flags": flags, "ok": True}


def chart_agent(d: pd.DataFrame, dec: int) -> dict:
    """📊 چارت‌خوان — ورود/خروج از همان موتورِ QC-دارِ اپ؛ هیچ قاعده‌ی موازی‌ای نمی‌سازد."""
    d_ind = nq.add_indicators(d.copy())
    plan = nq.setup_plan(d_ind)
    msgs: list[dict] = []
    claims: list[dict] = []
    qc = plan.get("qc") or {}
    stamp = qc.get("stamp") or ""
    if plan.get("status") == "active":
        entry, stop = plan.get("entry"), plan.get("stop")
        tps = plan.get("targets") or []
        side = 1 if "لانگ" in str(plan.get("direction")) else -1 if "شورت" in str(plan.get("direction")) else 0
        msgs.append({"text": f"سیگنالِ فعال: <b>{plan.get('direction')}</b> — اعتمادِ <b>{plan.get('confidence')}٪</b> "
                             f"(بردِ TP1 در تستِ همین ستاپ روی همین نماد).",
                     "why": f"ستاپِ «{plan.get('mode_fa') or plan.get('mode')}» از موتورِ اپ؛ اعتماد فقط از آمارِ تست‌شده می‌آید"})
        if entry and stop:
            msgs.append({"text": f"ورود <b>{_fmt(entry, dec)}</b> · حدضرر <b>{_fmt(stop, dec)}</b>"
                                 f" · ریسکِ هر معامله ~{plan.get('risk_pct', 0) or 0:.1f}٪",
                         "why": str(plan.get("why") or "ساختارِ بازار (نقدینگی/FVG)")})
            for i, t in enumerate(list(tps)[:3], start=1):
                tp, tw = (t if isinstance(t, tuple) else (t, ""))
                msgs.append({"text": f"هدفِ {i}: <b>{_fmt(tp, dec)}</b>",
                             "why": str(tw or "سطحِ ساختاری")})
            msgs.append({"text": f"R:R هدفِ اول = <b>{plan.get('rr')}R</b> · مُهرِ کیفیت: <b>{stamp}</b>",
                         "why": f"{len(qc.get('issues') or [])} ایرادِ سخت، {len(qc.get('warnings') or [])} هشدار در ۱۴ بازرسیِ QC"})
        claims.append({"by": "chart", "side": side,
                       "claim": f"{plan.get('direction')} — ورود {_fmt(entry, dec) if entry else '؟'}",
                       "evidence": f"QC: {stamp} · R:R={plan.get('rr')}"})
    else:
        msgs.append({"text": "الان ورودِ تمیز نمی‌دهم — سیستم عمداً روی «انتظار» است.",
                     "why": str(plan.get("why") or "ستاپِ معتبرِ تست‌شده روی چارت فعلی نیست")})
        if plan.get("watch"):
            msgs.append({"text": f"برای معتبر شدنِ ستاپ: {plan.get('watch')}",
                         "why": "انتظارِ بدونِ شرط، حدس است؛ شرطِ دقیق = قابلِ تست"})
        msgs.append({"text": f"با این حال بازرسیِ کیفیتِ داده انجام شد: <b>{stamp}</b>",
                     "why": "حتی وقتی سیگنال نیست، سلامتِ داده باید مُهر بخورد"})
        claims.append({"by": "chart", "side": 0, "claim": "بدون ورودِ تمیز — انتظار",
                       "evidence": str(plan.get("why") or "")[:120]})
    return {"key": "chart", "emoji": "📊", "name": "چارت‌خوان",
            "role": "نقطه‌ی ورود/خروج — فقط از موتورِ QC-دارِ اپ، با آمارِ تست‌شده",
            "msgs": msgs, "claims": claims, "plan": plan, "d_ind": d_ind, "ok": True}


# ================================================================ شکاک
def risk_agent(d_ind: pd.DataFrame, dec: int, plan: dict,
               capital: float = 1000.0, risk_pct: float = 1.0) -> dict:
    """💼 مدیرِ ریسک — اندازه‌ی پوزیشن از سرمایه‌ی کاربر؛ قانونِ ۱–۲٪، کارمزد، بدونِ اهرم."""
    msgs: list[dict] = []
    claims: list[dict] = []
    cap = max(0.0, float(capital or 0))
    rp = max(0.0, min(100.0, float(risk_pct or 0)))
    head = {"key": "risk", "emoji": "💼", "name": "مدیرِ ریسک",
            "role": "اندازه‌ی پوزیشن از سرمایه‌ی تو — قانونِ ۱–۲٪ + کارمزد + بدونِ اهرم",
            "msgs": msgs, "claims": claims, "ok": True}
    if cap <= 0:
        msgs.append({"text": "سرمایه‌ای وارد نشده — بدونِ عدد، اندازه‌ای هم نیست؛ حدسِ اندازه = قمار.",
                     "why": "ورودیِ سرمایه در بالای صفحه صفر است؛ من حدس نمی‌زنم."})
        msgs.append({"text": f"قاعده‌ی ثابت من برای وقتی عدد آمد: حداکثر <b>{rp:g}٪</b> سرمایه در خطر در هر معامله.",
                     "why": "قانونِ ۱–۲٪ کلاسیک — با ضررهای پیاپی، سرمایه زنده می‌ماند تا لبه‌ی آماری کار کند."})
        return head
    msgs.append({"text": f"قاعده‌ی ثابت من: در هر معامله فقط <b>{rp:g}٪</b> از <b>{cap:,.0f}</b> در خطر باشد — "
                         f"یعنی حداکثر <b>{cap * rp / 100.0:,.2f}</b>.",
                 "why": "قانونِ ۱–۲٪ کلاسیک؛ حتی ۵–۶ ضررِ پیاپی هم سرمایه را نمی‌کُشد تا لبه‌ی آماری فرصتِ جبران بدهد."})
    if plan.get("status") != "active" or not plan.get("entry") or not plan.get("stop"):
        msgs.append({"text": "الان پوزیشنی برای اندازه‌دادن نیست — چارت‌خوان سیگنالِ فعال نداد.",
                     "why": f"وضعیتِ طرح: {plan.get('status')} — اول ستاپِ معتبر، بعد اندازه؛ ریسک قبل از سیگنال بی‌معناست."})
        claims.append({"by": "risk", "side": 0, "claim": "بدون سیگنالِ فعال — اندازه‌ای صادر نشد",
                       "evidence": f"plan.status={plan.get('status')}"})
        return head
    entry, stop = float(plan["entry"]), float(plan["stop"])
    dist = abs(entry - stop)
    if dist <= 0:
        msgs.append({"text": "فاصله‌ی ورود تا حدضرر صفر است — چنین طرحی را اصلاً حساب نمی‌کنم.",
                     "why": "ورود و حدضرر برابرند؛ این طرح از دروازه‌ی QC هم باید رد شود."})
        return head
    risk_amount = cap * rp / 100.0
    size = risk_amount / dist
    notional = size * entry
    fee_cost = notional * FEE_RT
    fee_drag_r = (fee_cost / risk_amount) if risk_amount > 0 else 0.0
    msgs.append({"text": f"اندازه‌ی پوزیشن: <b>{size:,.4f}</b> واحد (ارزشِ اسمی <b>{notional:,.2f}</b>).",
                 "why": f"فرمول: (سرمایه×ریسک٪) ÷ فاصله‌ی حدضرر = {risk_amount:,.2f} ÷ {_fmt(dist, dec)}"})
    msgs.append({"text": f"اگر حدضرر بخورد: دقیقاً <b>{risk_amount:,.2f}</b> ({rp:g}٪ سرمایه) از دست می‌دهی — نه یک واحدِ بیشتر.",
                 "why": f"اندازه×فاصله = {size:,.4f}×{_fmt(dist, dec)} = {risk_amount:,.2f} — ریسکِ تعریف‌شده، نه شانس"})
    msgs.append({"text": f"کارمزدِ رفت‌وبرگشت (~{FEE_RT * 100:.1f}٪ ارزشِ اسمی) ≈ <b>{fee_cost:,.2f}</b> = {fee_drag_r:.2f}R.",
                 "why": "کارمزد بخشی از ریسکِ واقعی است — با R نرمالیزه‌اش کردم تا با لبه‌ی آماریِ ستاپ مقایسه شود."})
    if fee_drag_r > 0.5:
        msgs.append({"text": "🚩 کارمزد بیش از نیمی از ریسک را می‌خورد — حدضررِ این‌قدر دور یعنی معامله‌ی گران.",
                     "why": f"{fee_drag_r:.2f}R > 0.5R — قانونِ من: کارمزد زیرِ نصفِ ریسک بماند."})
    msgs.append({"text": "اهرم؟ نه — اهرم فقط اندازه را ضرب می‌کند، نه لبه را؛ لبه از آمارِ ستاپ می‌آید.",
                 "why": "سیاستِ ثابتِ اتاق: منطقِ اسپات — اهرم ریسک را بدونِ افزودنِ برد، بزرگ می‌کند."})
    claims.append({"by": "risk", "side": 0,
                   "claim": f"اندازه‌ی {size:,.4f} واحد — ضررِ حداکثریِ {risk_amount:,.2f} ({rp:g}٪ سرمایه)",
                   "evidence": f"size=({cap:,.0f}×{rp:g}%)÷{_fmt(dist, dec)} · fee={fee_drag_r:.2f}R",
                   "capital": cap, "risk_pct": rp, "size": size, "fee_drag_r": fee_drag_r})
    return head


# ================================================================ شکاک
def skeptic_checks(claims: list[dict], d_ind: pd.DataFrame, plan: dict) -> list[dict]:
    """🧐 شکاک — هر ادعا را با داده محک می‌زند؛ خروجی: لیستِ داوری‌ها."""
    checks: list[dict] = []
    c_last = float(d_ind["close"].iloc[-1])
    ema200 = float(d_ind["ema200"].iloc[-1]) if "ema200" in d_ind and np.isfinite(d_ind["ema200"].iloc[-1]) else np.nan

    chart = next((cl for cl in claims if cl["by"] == "chart"), None)
    side = chart["side"] if chart else 0
    active = plan.get("status") == "active" and side != 0

    # ۱) ادعای چارت در برابر روندِ کلان
    if active and np.isfinite(ema200):
        if side > 0 and c_last < ema200:
            checks.append({"target": "چارت‌خوان", "about": "جهتِ سیگنال در برابر روندِ کلان",
                           "verdict": "اعتراض",
                           "reason": f"لانگ می‌دهی ولی قیمت ({_fmt(c_last, 4)}) زیرِ EMA200 ({_fmt(ema200, 4)}) است — "
                                     f"تو روندِ کلان را نادیده گرفتی؛ توضیح بده."})
        elif side < 0 and c_last > ema200:
            checks.append({"target": "چارت‌خوان", "about": "جهتِ سیگنال در برابر روندِ کلان",
                           "verdict": "اعتراض",
                           "reason": f"شورت می‌دهی ولی قیمت ({_fmt(c_last, 4)}) بالایِ EMA200 ({_fmt(ema200, 4)}) است — "
                                     f"روندِ کلان با تو مخالف است؛ توضیح بده."})
    # ۲) نسبتِ ریسک/سود و اعتماد
    if active:
        rr = float(plan.get("rr") or 0)
        conf = int(plan.get("confidence") or 0)
        if rr < 1.0:
            checks.append({"target": "چارت‌خوان", "about": "R:R هدفِ اول",
                           "verdict": "اعتراض",
                           "reason": f"هدفِ اول فقط {rr}R است — ریسکِ بیشتر از سود؛ هدفِ اول را جابه‌جا کن یا بی‌خیال سیگنال."})
        if conf < 40:
            checks.append({"target": "چارت‌خوان", "about": "اعتمادِ سیگنال",
                           "verdict": "هشدار",
                           "reason": f"اعتماد فقط {conf}٪ است — آمارِ تست‌شده‌ی کم؛ اندازه‌ی پوزیشن باید کوچک باشد."})
    # ۳) ادعاهای دیدبان
    for cl in claims:
        if cl["by"] == "watchdog" and "churn" in str(cl["claim"]):
            checks.append({"target": "دیدبان", "about": "حجمِ مشکوک (churn)",
                           "verdict": "اعتراض",
                           "reason": f"حق با توست و این خطِ قرمزِ من هم هست: {cl['claim']} — "
                                     f"تا وقتی حجمِ غیرعادی معنا نشده، هیچ ورودی نباید اجرا شود."})
        elif cl["by"] == "watchdog" and active and cl["side"] != 0 and cl["side"] != side:
            checks.append({"target": "دیدبان", "about": "فشارِ خرید/فروشِ مخالفِ سیگنال",
                           "verdict": "اعتراض",
                           "reason": f"چارت {('لانگ' if side > 0 else 'شورت')} می‌دهد ولی داده‌ی تو فشارِ "
                                     f"{('فروش' if cl['side'] < 0 else 'خرید')} را نشان می‌دهد ({cl['evidence']}) — یکی از ما اشتباه می‌کند."})
    # ۴) ادعاهای خبرنگار در برابر چارت
    for cl in claims:
        if cl["by"] == "news" and cl["side"] != 0 and active and cl["side"] != side:
            checks.append({"target": "خبرنگار", "about": "خبرِ مخالفِ سیگنال",
                           "verdict": "اعتراض",
                           "reason": f"این تیتر با سیگنالِ چارت تضاد دارد: «{cl['claim']}» ({cl['evidence']}) — "
                                     f"چارت‌خوان باید بگوید چرا این خبر قیمت را برنمی‌گرداند."})
    # ۴.۵) ادعای مدیرِ ریسک — بازمحاسبه‌ی کاملِ ریاضیاتش
    for cl in claims:
        if cl["by"] != "risk":
            continue
        rp = float(cl.get("risk_pct") or 0)
        if rp > MAX_RISK_PCT:
            checks.append({"target": "مدیرِ ریسک", "about": "درصدِ ریسکِ انتخابی",
                           "verdict": "اعتراض",
                           "reason": f"{rp:g}٪ ریسک در هر معامله یعنی ۳ ضررِ پشت‌سرهم ≈ "
                                     f"−{((1 - (1 - rp / 100.0) ** 3) * 100):.0f}٪ سرمایه — سقفِ من {MAX_RISK_PCT:g}٪ است؛ "
                                     f"ریسک را کم کن تا لبه‌ی آماری فرصتِ کار کند."})
        his = float(cl.get("size") or 0)
        entry, stop = plan.get("entry"), plan.get("stop")
        cap = float(cl.get("capital") or 0)
        if active and his > 0 and cap > 0 and entry and stop:
            dist = abs(float(entry) - float(stop))
            my_size = ((cap * rp / 100.0) / dist) if dist > 0 else 0.0
            if my_size > 0 and abs(his - my_size) > my_size * 0.01:
                checks.append({"target": "مدیرِ ریسک", "about": "محاسبه‌ی اندازه‌ی پوزیشن",
                               "verdict": "اعتراض",
                               "reason": f"عددِ تو ({his:,.4f}) با بازمحاسبه‌ی من ({my_size:,.4f}) جور درنمی‌آید — "
                                         f"فرمول: اندازه = (سرمایه×ریسک٪) ÷ فاصله‌ی حدضرر. برگرد و چک کن."})
            else:
                checks.append({"target": "مدیرِ ریسک", "about": "محاسبه‌ی اندازه‌ی پوزیشن",
                               "verdict": "تایید",
                               "reason": f"بازمحاسبه کردم: {my_size:,.4f} واحد — عددت درست است و "
                                         f"ضررِ حداکثری همان {rp:g}٪ سرمایه می‌ماند."})
        fdr = float(cl.get("fee_drag_r") or 0)
        if fdr > 0.5:
            checks.append({"target": "مدیرِ ریسک", "about": "کارمزد در برابر ریسک",
                           "verdict": "هشدار",
                           "reason": f"کارمزدِ رفت‌وبرگشت ≈ {fdr:.2f}R می‌خورد — پولِ زیادی برای این فاصله‌ی حدضرر "
                                     f"می‌پردازی؛ یا ستاپِ با حدضررِ نزدیک‌تر، یا نگذار."})
    # ۵) تاییدها — وقتی چیزی واقعاً هم‌جهت است
    if active:
        chg, vr = _chg_vol(d_ind)
        if vr >= 1.2 and (1 if chg > 0 else -1 if chg < 0 else 0) == side:
            checks.append({"target": "داده", "about": "هم‌جهتیِ حرکت و حجم",
                           "verdict": "تایید",
                           "reason": f"حرکتِ {chg:+.1f}٪ با حجمِ {vr:.1f}× همراه است — پول با سیگنال هم‌جهت است."})
        qc = plan.get("qc") or {}
        if qc.get("setup_tested"):
            st_ = qc.get("stats") or {}
            checks.append({"target": "چارت‌خوان", "about": "پشتوانه‌ی آماری",
                           "verdict": "تایید",
                           "reason": f"ستاپ روی همین نماد تست شده: {st_.get('n', '؟')} معامله، "
                                     f"TP1 در {st_.get('win1', '؟')}٪ — عددِ واقعی، نه ادعا."})
        score = plan.get("score")
        if isinstance(score, (int, float)) and abs(score) >= 0.15 and (1 if score > 0 else -1) == side:
            checks.append({"target": "شواهد", "about": "رأیِ شواهدِ چندابزاری",
                           "verdict": "تایید",
                           "reason": f"امتیازِ شواهد {score:+.2f} هم‌جهتِ سیگنال است — چارت‌خوان تنها نیست."})
    if not checks:
        checks.append({"target": "همه", "about": "وضعیتِ کلی",
                       "verdict": "بی‌طرف",
                       "reason": "ادعای قابلِ محک‌زدنی ندارم — نه سیگنالِ فعالی هست، نه ادعای مخالف."})
    return checks


def team_verdict(plan: dict, checks: list[dict]) -> dict:
    """حکمِ نهاییِ اتاق — فقط بر پایه‌ی داوری‌های شکاک و دروازه‌ی QC."""
    hard = [x for x in checks if x["verdict"] == "اعتراض"]
    warns = [x for x in checks if x["verdict"] == "هشدار"]
    goods = [x for x in checks if x["verdict"] == "تایید"]
    active = plan.get("status") == "active"
    if not active:
        state, title = "wait", "⏸ تیم روی «انتظار» است"
        text = ("موتورِ QC ورودِ تمیز نداد و شکاک هم مخالفِ معامله‌ی بی‌ستاپ است — "
                "شرطِ معتبرشدن را چارت‌خوان گفته؛ آن شرط که خورد، دوباره جلسه بگیرید.")
        if hard:
            text += (f" ضمناً شکاک {len(hard)} اعتراضِ جدا هم ثبت کرده (حجمِ مشکوک/تضادِ خبر) — "
                     "یعنی همین الان هم که سیگنال نیست، زیرِ پایتان ناجور است.")
    elif hard:
        state, title = "object", "🧐 شکاک اعتراض دارد — تا حل نشود، معامله ممنوع"
        text = ("چارت‌خوان سیگنال داده ولی شکاک " + str(len(hard)) + " اعتراضِ داده‌محور دارد؛ "
                "در این اتاق حکمِ شکاک از سیگنال بالاتر است — اعتراض‌ها را بخوانید.")
    else:
        state, title = "align", "✅ تیم هم‌نظر است — با استدلالِ قابلِ بررسی"
        text = ("هیچ اعتراضِ سختِای وجود ندارد" +
                (f" و {len(goods)} تاییدِ داده‌محور ثبت شد" if goods else "") +
                ("؛ هشدارها را جدی بگیر (اندازه‌ی پوزیشن)." if warns else "."))
    return {"state": state, "title": title, "text": text,
            "n_obj": len(hard), "n_warn": len(warns), "n_confirm": len(goods)}


# ================================================================ جلسه
def investigate(exchange: str = EXCHANGE_DEFAULT, symbol: str = "BTC-USDT",
                interval: str = INTERVAL_DEFAULT, with_news: bool = True,
                df: pd.DataFrame | None = None, news: dict | None = None,
                ts: str | None = None, limit: int = 400,
                capital: float = 1000.0, risk_pct: float = 1.0,
                with_witness: bool = True) -> dict:
    """یک جلسه‌ی کاملِ اتاقِ تیم روی یک ارز — fail-soft: هیچ‌وقت exception بالا نمی‌دهد."""
    out: dict = {"exchange": exchange, "symbol": symbol, "interval": interval,
                 "ts": ts or datetime.now(TEHRAN).strftime("%Y-%m-%d %H:%M"), "ok": False}
    try:
        if df is None:
            df = nq.fetch_candles(exchange, symbol, interval, limit=limit)
        if df is None or not isinstance(df, pd.DataFrame) or df.empty:
            out["error"] = "کندلی برای این نماد/تایم‌فریم برنگشت — نماد را چک کن."
            return out
        d_ind = nq.add_indicators(df.copy())
        price = float(d_ind["close"].iloc[-1])
        dec = 2 if price >= 1000 else 4 if price >= 1 else 6
        out.update({"price": price, "dec": dec})

        n_items, n_stale = [], False
        if with_news:
            try:
                nd = news or NEWS.fetch_news()
                n_items, n_stale = list(nd.get("items") or []), bool(nd.get("stale"))
            except Exception:  # noqa: BLE001
                n_items, n_stale = [], True

        def _agent(fn):
            try:
                return fn()
            except Exception as exc:  # noqa: BLE001 — یک عامل نباید جلسه را بیندازد
                return {"key": "err", "emoji": "⚠️", "name": "عاملِ خاموش",
                        "role": "این عامل موقتاً از کار افتاد", "ok": False,
                        "msgs": [{"text": "نتوانستم تحلیل کنم — به‌جای حدس، سکوت.",
                                  "why": f"خطا: {type(exc).__name__}"}], "claims": []}

        news_a = _agent(lambda: news_agent(symbol, d_ind, dec, n_items, n_stale))
        watch_a = _agent(lambda: watchdog_agent(d_ind, dec))
        chart_a = _agent(lambda: chart_agent(d_ind, dec))
        # مدیرِ ریسک بعد از چارت می‌آید — به طرحِ او نیاز دارد
        plan = (chart_a.get("plan") if isinstance(chart_a, dict) else None) or \
            {"status": "wait", "direction": "⏸ انتظار", "entry": None, "stop": None,
             "targets": [], "rr": 0, "confidence": 0, "why": "طرح ساخته نشد"}
        risk_a = _agent(lambda: risk_agent(d_ind, dec, plan, capital, risk_pct))
        agents = [news_a, watch_a, chart_a, risk_a]
        # شاهدِ ششم — کرونوس در حالتِ سایه (فازِ یکِ نقشه‌راه): نظر است، نه رأی؛
        # خاموشی‌اش (env یا پارامتر) و حتی خرابی‌اش هرگز جلسه را نمی‌بَرد.
        wit = None
        if with_witness and os.environ.get("KRONOS_WITNESS", "").strip().lower() not in ("0", "off", "false"):
            wit = _agent(lambda: KW.witness(d_ind, dec, interval=interval))
            agents.append(wit)
        out["agents"] = {a["key"]: a for a in agents if isinstance(a, dict) and a.get("key")}

        chart = out["agents"].get("chart") or {}
        plan = chart.get("plan") or {"status": "wait", "direction": "⏸ انتظار",
                                     "entry": None, "stop": None, "targets": [],
                                     "rr": 0, "confidence": 0, "why": "طرح ساخته نشد"}
        claims = [cl for a in agents for cl in (a.get("claims") or [])]
        checks = skeptic_checks(claims, d_ind, plan)
        # داوریِ شکاک درباره‌ی ادعای شاهدِ کرونوس — فقط هشدار/تاییدِ ثبت‌شده؛
        # در حالتِ سایه هیچ اعتراضِ سختی از این مسیر بیرون نمی‌آید و حکمِ تیم
        # دست‌نخورده می‌ماند.
        chart_cl = next((cl for cl in claims if cl["by"] == "chart"), None)
        checks.extend(KW.skeptic_kronos_check(wit, (chart_cl or {}).get("side", 0), plan))
        out["skeptic"] = {"key": "skeptic", "emoji": "🧐", "name": "شکاک",
                          "role": "دنبال دلیل و منطق می‌گردد — هر ادعا را با داده محک می‌زند",
                          "checks": checks}
        out["verdict"] = team_verdict(plan, checks)
        out["plan"] = plan
        out["ok"] = True
        return out
    except Exception as exc:  # noqa: BLE001
        out["error"] = f"جلسه شکست خورد: {type(exc).__name__}: {exc}"
        return out
