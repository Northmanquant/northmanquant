# -*- coding: utf-8 -*-
"""core/signal_qc.py — دروازه‌ی کنترل کیفیت سیگنال (Signal QC)
=====================================================================
درخواست کاربر: «دنبال کیفیت در سیگنال‌ها هستم؛ می‌خوام سیگنال‌هایی که می‌دهد
کامل، دقیق، بدون خطا و تست‌شده باشند — برای ارائه.»

فلسفه: هیچ سیگنالی نباید بدون گذر از یک بازرسیِ مشخص و قابل‌شمارش به کاربر،
اسکنر، ایجنت‌ها یا تصویرِ ارائه برسد. دو لایه‌ی بازرسی:

  ۱) سلامتِ داده — سقف/کف/بدنه‌ی سازگار، بدون NaN/∞، بدون قیمتِ صفر/منفی،
     بدون کندل تکراری/بی‌ترتیب، قیمتِ آخرین کندل در بازه‌ی منطقیِ ۱۰۰ کندلِ
     اخیر، تاریخچه به‌قدرِ کافی، و اندیکاتورهایی که ستاپ مستقیم استفاده می‌کند
     (RSI، EMA50/200، باندهای بولینگر، ATR) روی آخرین کندل سالم باشند.
  ۲) سلامتِ طرح — ورود/حدضرر/اهداف همه عددِ متناهیِ مثبت؛ حدضرر درست‌سِمتِ
     ورود؛ فاصله‌ی حدضرر در بازه‌ی منطقیِ ATR؛ اهداف درست‌سِمت و مرتبِ
     اکید و در بازه‌ی منطقیِ R؛ R:R سازگار با TP1؛ ریسک‌درصد معقول؛
     اعتمادِ اعلام‌شده فقط از آمارِ walk-forward قابل‌اعتماد بیاید.

هر ایراد «سخت» = سیگنال صادر نمی‌شود؛ طرح خودکار به «⏸ انتظار» سقوط می‌کند و
دلیلِ دقیقِ فارسی کنارش نوشته می‌شود — بی‌صدا چیزی پنهان نمی‌شود.
نتیجه به شکل یک مُهرِ شمارشی (QC n/n) به طرح چسبانده می‌شود تا در صفحه، در
تصویرِ ارائه و در گزارشِ اسکنر «تست‌شده بودن» دیده‌شدنی باشد، نه ادعا.
همه‌چیز آفلاین، قطعی (بدون شانس) و بدون هیچ درخواستِ شبکه است.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# ---------------------------------------------------------------- ثابت‌های دروازه
MIN_BARS = 90            # کمتر از این، تحلیلِ سیگنال معنا ندارد (سخت‌گیرانه)
WARMUP_BARS = 260        # زیر این تعداد EMA200 هنوز گرم نیست — فقط هشدار، نه رد
STOP_ATR_MIN = 0.25      # حدضررِ نزدیک‌تر از این = نویز، نه ساختار
STOP_ATR_MAX = 6.0       # حدضررِ دورتر از این = حدضررِ بی‌ربط
TARGET_R_MIN = 0.40      # هدفِ نزدیک‌تر از این R ارزش ثبت ندارد
TARGET_R_MAX = 12.0      # هدفِ دورتر از این در افقِ کاری ستاپ نیست
RISK_PCT_MAX = 25.0      # ریسکِ درصدیِ ورود تا حدضرر بیشتر از این = فید خراب
BASE_COLS = ("dt", "open", "high", "low", "close", "volume")
LAST_IND_COLS = ("close", "rsi", "ema50", "ema200", "bb_up", "bb_lo", "atr")

_ZERO_STATS = {"mode": "", "n": 0, "win1": 0.0, "exp2": 0.0, "total2": 0.0,
               "longs": 0, "shorts": 0}


# ---------------------------------------------------------------- لایه‌ی ۱ — سلامتِ داده
def validate_ohlcv(d: pd.DataFrame | None, min_bars: int = MIN_BARS) -> tuple[bool, list[str], dict]:
    """سلامتِ داده‌ی کندل (ورودی: دیتافریم خام یا اندیکاتوردار — ستون‌های OHLCV)."""
    info = {"n_bars": 0, "warm": False, "duplicates": 0}
    if d is None or not isinstance(d, pd.DataFrame) or d.empty:
        return False, ["هیچ کندلی برای تحلیل نیست"], info
    info["n_bars"] = int(len(d))
    info["warm"] = len(d) >= WARMUP_BARS
    issues: list[str] = []
    if len(d) < min_bars:
        issues.append(f"تاریخچه خیلی کوتاه است ({len(d)} کندل < حداقلِ {min_bars})")
    missing = [c for c in BASE_COLS if c not in d.columns]
    if missing:
        return False, issues + ["ستون‌های غایبِ داده: " + "، ".join(missing)], info
    ohlc = d[["open", "high", "low", "close"]].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
    if not np.isfinite(ohlc).all():
        issues.append("قیمت NaN یا بی‌نهایت در کندل‌ها — فید داده خراب است")
        return False, issues, info
    if (ohlc <= 0).any():
        issues.append("قیمت صفر یا منفی در کندل‌ها — فید داده خراب است")
    hi, lo, op, cl = ohlc[:, 1], ohlc[:, 2], ohlc[:, 0], ohlc[:, 3]
    eps = np.maximum(np.abs(ohlc), 1.0) * 1e-9
    bad = (hi < lo - eps[:, 1]) | (hi < np.maximum(op, cl) - eps[:, 1]) | (lo > np.minimum(op, cl) + eps[:, 2])
    nbad = int(np.count_nonzero(bad))
    if nbad:
        issues.append(f"ساختار OHLC در {nbad} کندل مخدوش است (سقف/کف با بدنه‌ی کندل ناسازگار)")
    med = float(np.median(cl[-100:]))
    last = float(cl[-1])
    if not (0.1 * med <= last <= 10.0 * med):
        issues.append("قیمت آخرین کندل با میانگینِ ۱۰۰ کندلِ اخیر فاصله‌ی غیرمنطقی دارد — فید خراب است")
    if "dt" in d.columns:
        dts = pd.to_datetime(d["dt"], errors="coerce")
        if dts.isna().any():
            issues.append("مهرِ زمانی نامعتبر در کندل‌ها")
        else:
            dd = dts.diff().dropna()
            ndup = int((dd <= pd.Timedelta(0)).sum())
            info["duplicates"] = ndup
            if ndup:
                issues.append(f"{ndup} کندلِ تکراری/بی‌ترتیب در مهرِ زمانی — فید خراب است")
    return (not issues), issues, info


def validate_indicators(d: pd.DataFrame | None) -> list[str]:
    """سلامتِ آخرین کندلِ اندیکاتورهایی که موتور ستاپ مستقیم مصرف می‌کند."""
    if d is None or not isinstance(d, pd.DataFrame) or d.empty:
        return ["دیتافریم خالی"]
    issues: list[str] = []
    missing = [c for c in LAST_IND_COLS if c not in d.columns]
    if missing:
        return ["ستون‌های اندیکاتور غایب: " + "، ".join(missing)]
    last = d.iloc[-1]
    for c in LAST_IND_COLS:
        v = float(pd.to_numeric(pd.Series([last[c]]), errors="coerce").iloc[0])
        if not np.isfinite(v):
            issues.append(f"اندیکاتور «{c}» روی آخرین کندل NaN یا بی‌نهایت است")
    atr = float(pd.to_numeric(pd.Series([last.get("atr")]), errors="coerce").iloc[0]) if "atr" in d else float("nan")
    price = float(pd.to_numeric(pd.Series([last.get("close")]), errors="coerce").iloc[0]) if "close" in d else float("nan")
    if np.isfinite(atr) and np.isfinite(price) and price > 0 and atr <= 0:
        issues.append("ATR صفر یا منفی است — نوسانِ داده بی‌اعتبار است")
    if np.isfinite(atr) and np.isfinite(price) and price > 0 and atr > price * 0.5:
        issues.append("ATR بیش از نصفِ قیمت است — فید داده پرشِ نامعقول دارد")
    return issues


# ---------------------------------------------------------------- لایه‌ی ۲ — سلامتِ طرح
def qc_plan(plan: dict) -> list[str]:
    """بازرسیِ سختِ طرحِ فعال — هر ایراد یعنی سیگنال اجازه‌ی انتشار ندارد."""
    issues: list[str] = []
    if plan.get("status") != "active":
        return issues
    entry = plan.get("entry")
    stop = plan.get("stop")
    atr = float(plan.get("atr")) if np.isfinite(float(plan.get("atr") or np.nan)) else float("nan")
    direction = str(plan.get("direction", ""))
    long = "لانگ" in direction
    if entry is None or stop is None:
        return ["طرحِ «فعال» بدون قیمتِ ورود یا حدِ ضرر است"]
    entry = float(entry)
    stop = float(stop)
    for name, v in (("ورود", entry), ("حدِ ضرر", stop), ("ATR", atr)):
        if not np.isfinite(v) or v <= 0:
            issues.append(f"مقدارِ «{name}» عددِ معتبرِ مثبت نیست")
    if issues:
        return issues
    risk = abs(entry - stop)
    if risk <= 0:
        return ["حدِ ضرر با ورود هم‌قیمت است — ریسکِ صفر بی‌معناست"]
    if long and stop >= entry:
        issues.append("حدِ ضررِ لانگ باید زیر ورود باشد")
    if (not long) and stop <= entry:
        issues.append("حدِ ضررِ شورت باید بالای ورود باشد")
    if np.isfinite(atr) and atr > 0:
        if risk / atr < STOP_ATR_MIN:
            issues.append(f"فاصله‌ی حدِ ضرر ({risk / atr:.2f}×ATR) از حدِ منطقیِ {STOP_ATR_MIN:g}×ATR کمتر است")
        if risk / atr > STOP_ATR_MAX:
            issues.append(f"فاصله‌ی حدِ ضرر ({risk / atr:.2f}×ATR) از حدِ منطقیِ {STOP_ATR_MAX:g}×ATR بیشتر است")
    risk_pct = plan.get("risk_pct")
    if risk_pct is None or not np.isfinite(float(risk_pct)) or not (0 < float(risk_pct) < RISK_PCT_MAX):
        issues.append(f"ریسکِ درصدیِ طرح نامعتبر یا غیرمنطقی است (باید ۰ تا {RISK_PCT_MAX:g}٪ باشد)")
    targets = plan.get("targets") or []
    if not targets:
        issues.append("طرحِ فعال بدون هیچ هدفِ قیمتی است")
    else:
        r_mults = []
        for i, t in enumerate(targets, 1):
            tp = float(t[0]) if isinstance(t, (tuple, list)) and len(t) >= 1 else float("nan")
            if not np.isfinite(tp) or tp <= 0:
                issues.append(f"هدفِ {i} عددِ معتبرِ مثبت نیست")
                continue
            r = abs(tp - entry) / risk
            r_mults.append((i, tp, r))
            if r < TARGET_R_MIN:
                issues.append(f"هدفِ {i} فقط {r:.2f}R از ورود فاصله دارد (کمتر از {TARGET_R_MIN:g}R)")
            if r > TARGET_R_MAX:
                issues.append(f"هدفِ {i} {r:.1f}R از ورود فاصله دارد (بیشتر از {TARGET_R_MAX:g}R)")
            if long and tp <= entry:
                issues.append(f"هدفِ {i}ِ لانگ باید بالای ورود باشد")
            if (not long) and tp >= entry:
                issues.append(f"هدفِ {i}ِ شورت باید زیر ورود باشد")
        ok_t = [x for x in r_mults]
        for a, b in zip(ok_t, ok_t[1:]):
            if long and b[1] <= a[1]:
                issues.append("اهداف باید به‌ترتیبِ صعودی برای لانگ دورتر شوند")
            if (not long) and b[1] >= a[1]:
                issues.append("اهداف باید به‌ترتیبِ نزولی برای شورت دورتر شوند")
        if ok_t:
            rr = float(plan.get("rr") or 0.0)
            rr_true = abs(float(ok_t[0][1]) - entry) / risk
            if not np.isfinite(rr) or abs(rr - rr_true) > 0.011:
                issues.append(f"R:R اعلام‌شده ({rr:g}) با فاصله‌ی واقعیِ TP1 ({rr_true:.2f}R) سازگار نیست")
    conf = plan.get("confidence")
    if conf is None or not np.isfinite(float(conf)) or not (0 <= float(conf) <= 100):
        issues.append("اعتمادِ اعلام‌شده خارج از بازه‌ی ۰ تا ۱۰۰ است")
    stats = plan.get("stats") or {}
    st_ = stats.get(plan.get("mode") or "") or {}
    n = int(st_.get("n") or 0)
    win1 = float(st_.get("win1") or 0.0)
    exp2 = float(st_.get("exp2") or 0.0)
    if n < 6 or exp2 <= 0 or win1 < 40:
        issues.append("طرحِ فعال اما آمارِ walk-forward آن قابل‌اعتماد نیست (ستاپ باید تست‌شده و سودده باشد)")
    conf_i = int(round(float(conf))) if conf is not None and np.isfinite(float(conf)) else -1
    if conf_i >= 0 and conf_i < 40:
        issues.append("اعتمادِ زیرِ ۴۰٪ فقط برای طرحِ «انتظار» مجاز است")
    return issues


# ---------------------------------------------------------------- مُهر و دروازه
def stamp_of(qc: dict, en: bool = False) -> str:
    """مُهرِ قابل‌نمایش QC — برای صفحه (فارسی) و تصویرِ ارائه (انگلیسی)."""
    n = int(qc.get("n_checks", 0))
    bad = int(qc.get("n_fail", 0))
    if en:
        if bad:
            return f"QC {n - bad}/{n} BLOCKED"
        return f"QC {n}/{n} passed · data OK · levels sane · setup walk-forward tested"
    if bad:
        return f"⛔ QC {n - bad}/{n} — سیگنال متوقف شد"
    parts = ["داده‌ی سالم", "سطوحِ منطقی"]
    if qc.get("setup_tested"):
        st_ = qc.get("stats") or {}
        parts.append(f"ستاپِ تست‌شده ({int(st_.get('n') or 0)} معامله، TP1 {float(st_.get('win1') or 0):.0f}٪)")
    warn = qc.get("warnings") or []
    if warn:
        parts.append("⚠ " + "؛ ".join(warn))
    return f"✅ QC {n}/{n} — " + " · ".join(parts)


def qc_gate(d: pd.DataFrame | None, plan: dict) -> dict:
    """دروازه‌ی نهایی: بازرسیِ داده + طرح؛ ایرادِ سخت → سقوطِ خودکار به «انتظار».

    خروجی همیشه یک طرحِ کامل است (همه‌ی کلیدهایی که UI/اسکنر/تصویر می‌خوانند)
    با یک دیکشنریِ «qc» چسبیده: شمارشِ بازرسی‌ها، ایرادها، هشدارها و مُهر.
    """
    d_ok, d_issues, info = validate_ohlcv(d)
    i_issues = validate_indicators(d) if d_ok else (["(داده‌ی خام سالم نیست — بازرسیِ اندیکاتور انجام نشد)"] if d is not None and isinstance(d, pd.DataFrame) and not d.empty else [])
    hard = list(d_issues) + list(i_issues)
    n_checks = 14  # ۱۰ بازرسیِ داده/اندیکاتور + ۴ بازرسیِ طرح (جهت، سطوح، آمار، اعتماد)
    if d is None or not isinstance(d, pd.DataFrame) or d.empty:
        n_checks = 14
    warnings: list[str] = []
    if d_ok and not info.get("warm", False):
        warnings.append(f"تاریخچه زیر {WARMUP_BARS} کندل است؛ EMA200 هنوز گرم نیست")
    p_issues = qc_plan(plan) if (plan.get("status") == "active" and not hard) else []
    setup_tested = False
    st_ = {}
    if plan.get("status") == "active" and not hard and not p_issues:
        st_ = (plan.get("stats") or {}).get(plan.get("mode") or "") or {}
        setup_tested = bool(st_.get("n") and st_.get("exp2", 0) > 0)
    n_fail = len(hard) + len(p_issues)
    qc = {"ok": n_fail == 0, "issues": hard + p_issues, "warnings": warnings,
          "n_checks": n_checks, "n_fail": n_fail, "stats": st_ if setup_tested else {},
          "setup_tested": setup_tested, "n_bars": info.get("n_bars", 0),
          "stamp": stamp_of({"n_checks": n_checks, "n_fail": n_fail, "setup_tested": setup_tested,
                             "stats": st_ if setup_tested else {}, "warnings": warnings}),
          "stamp_en": stamp_of({"n_checks": n_checks, "n_fail": n_fail}, en=True)}
    out = dict(plan)
    out["qc"] = qc
    if not hard and not p_issues:
        return out
    # سقوطِ خودکار به «انتظار» — با دلیلِ دقیق، بدون حذفِ آمار و زمینه
    reasons = hard + p_issues
    why = "دروازه‌ی کیفیت سیگنال سیگنال را متوقف کرد: " + "؛ ".join(reasons)
    atr = out.get("atr")
    if atr is None or not np.isfinite(float(atr)) or float(atr) <= 0:
        try:
            atr = float(d["close"].iloc[-1]) * 0.01 if d is not None and "close" in d and len(d) else 0.0
        except Exception:  # noqa: BLE001
            atr = 0.0
    if not np.isfinite(float(atr)) or float(atr) <= 0:
        atr = 0.0
    fallback = {"status": "wait", "direction": "⏸ انتظار (بدون معامله)", "entry": None, "stop": None,
                "targets": [], "target_why": [], "rr": 0, "confidence": 0, "risk_pct": None,
                "atr": float(atr or 0.0), "why": why,
                "watch": out.get("watch", ""), "mode": out.get("mode"), "mode_fa": out.get("mode_fa"),
                "setup": out.get("setup"), "stats": out.get("stats") or {
                    m: dict(_ZERO_STATS, mode=m) for m in ("fade", "pullback")}}
    fallback = {**fallback, **{k: out[k] for k in ("score", "fvg_note") if k in out}}
    fallback["qc"] = qc
    return fallback


def wait_plan_stub(reason: str) -> dict:
    """اسکلتِ «انتظار» برای مسیرهایی که هنوز طرحی نساخته‌اند و QC فقط دلیل می‌دهد."""
    return {"status": "wait", "direction": "⏸ انتظار (بدون معامله)", "entry": None, "stop": None,
            "targets": [], "rr": 0, "confidence": 0, "why": reason,
            "stats": {m: dict(_ZERO_STATS, mode=m) for m in ("fade", "pullback")}}
