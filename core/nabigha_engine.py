# -*- coding: utf-8 -*-
"""نبیه — موتورِ پیش‌بینیِ بومیِ نورث‌من‌کوانت (فازِ اول: سایه)
=================================================================
درخواستِ کاربر: «کرونوس آن‌قدر مهم نیست که حتماً از خودش استفاده کنیم —
ازش داده بگیر و چیزی شبیه خودش بساز». نبیه همان نظم را دارد، ولی مالِ خودِ
پروژه است: بدونِ وزنِ خارجی، بدونِ torch، تماماً قطعی و تفسیرپذیر.

هر پیش‌بینی = مجموعه‌ای از سیگنال‌های ساده‌ی قابلِ توضیح که هرکدام رأیِ
±۱ با وزن می‌دهند؛ جمعِ وزنی → سمت (±۱/۰) و اطمینانِ داخلی (٪). همان
کندل‌هایی که اتاقِ تیم می‌بیند ورودی‌اند تا مقایسه‌ی «نبیه در برابر چارت»
منصف باشد.

  • روندِ EMA (۹/۲۱ + شیبِ ۶کندلی)   وزن ۲
  • مومنتومِ ۱۰ کندلی                وزن ۱
  • RSI(۱۴)                          وزن ۱
  • فشارِ حجم                        وزن ۰٫۵
  • شکستِ کانالِ ۲۰ کندلی           وزن ۱٫۵

سمت فقط وقتی ادعا می‌شود که جمعِ وزنی از آستانه گذرد؛ در حالتِ سایه هیچ
اثری در حکمِ اتاق ندارد — فقط در دفترِ خودش ثبت می‌شود (append-only) تا
مثلِ کرونوس، روزی با قراردادِ پیش‌ثبت‌شده آزموده شود. گرِیدرِ پیامدِ مشترک
(core/paper_grader.py) بعدها hit-rate واقعی هر دو را می‌سنجد.
"""
from __future__ import annotations

import json
import math
import os
from datetime import datetime

import numpy as np
import pandas as pd

ENGINE = "nabigha"
ENGINE_VERSION = 1
SIDE_THRESHOLD = 1.0          # حداقلِ جمعِ وزنی برای ادعای جهت
GATE_MIN_SESSIONS = 200       # هم‌شکلِ کرونوس — بعداً با قراردادِ پیش‌ثبت‌شده قفل می‌شود
GATE_MIN_AGREE_PCT = 55.0

_SIGNALS = [
    ("ema_trend", "روندِ EMA", 2.0),
    ("momentum", "مومنتومِ ۱۰ کندلی", 1.0),
    ("rsi", "RSI(۱۴)", 1.0),
    ("volume", "فشارِ حجم", 0.5),
    ("breakout", "شکستِ کانالِ ۲۰ کندلی", 1.5),
]


def _sign(x: float, eps: float = 1e-12) -> int:
    if x > eps:
        return 1
    if x < -eps:
        return -1
    return 0


def predict(d: pd.DataFrame | None, min_rows: int = 60) -> dict:
    """پیش‌بینیِ قطعیِ جهت از کندل‌ها — fail-soft: خطا یعنی پیش‌بینیِ نداریم.

    d: DataFrame با ستون‌های close/high/low/volume (open اختیاری) — همان
    خروجیِ app_base.fetch_candles. خروجی دیکته‌ای با signals[]ِ تفسیرپذیر است.
    """
    try:
        if d is None or not isinstance(d, pd.DataFrame) or len(d) < max(min_rows, 22):
            return {"ok": False, "engine": ENGINE,
                    "error": "کندلِ کافی نیست — حداقلِ ۶۰ کندل لازم است"}
        close = d["close"].astype(float).reset_index(drop=True)
        high = d["high"].astype(float).reset_index(drop=True)
        low = d["low"].astype(float).reset_index(drop=True)
        vol = d["volume"].astype(float).reset_index(drop=True)
        openc = (d["open"].astype(float).reset_index(drop=True)
                 if "open" in d.columns else close.shift(1))

        votes: dict[str, int] = {}
        notes: dict[str, str] = {}

        # ۱) روندِ EMA — جهت + شیب باید هم‌علامت باشند وگرنه رأیِ ندارد
        ema9 = close.ewm(span=9, adjust=False).mean()
        ema21 = close.ewm(span=21, adjust=False).mean()
        dirn = _sign(float(ema9.iloc[-1] - ema21.iloc[-1]))
        slope = _sign(float(ema21.iloc[-1] - ema21.iloc[-6]))
        votes["ema_trend"] = dirn if dirn != 0 and dirn == slope else 0
        notes["ema_trend"] = (f"EMA۹ {'بالا' if dirn > 0 else 'پایینِ'} EMA۲۱"
                              + (f"، شیبِ {'مثبت' if slope > 0 else 'منفی'}" if slope != 0 else "، شیبِ خنثی"))

        # ۲) مومنتومِ ۱۰ کندلی — فقط حرکتِ معنادار رأی می‌دهد
        ret10 = float(close.iloc[-1] / close.iloc[-11] - 1.0) if close.iloc[-11] else 0.0
        votes["momentum"] = _sign(ret10, eps=1e-4)
        notes["momentum"] = f"بازدهِ ۱۰کندلی {ret10 * 100:+.2f}٪"

        # ۳) RSI(۱۴) — باندِ ۴۵–۵۵ خنثی است
        diff = close.diff()
        gain = diff.clip(lower=0).rolling(14).mean()
        loss = (-diff).clip(lower=0).rolling(14).mean()
        rsi_last = float("nan")
        try:
            rs = gain.iloc[-1] / loss.iloc[-1] if float(loss.iloc[-1]) > 0 else float("inf")
            rsi_last = 100.0 - 100.0 / (1.0 + rs) if math.isfinite(rs) else 100.0
        except (ZeroDivisionError, ValueError):
            pass
        if math.isnan(rsi_last):
            votes["rsi"] = 0
            notes["rsi"] = "RSI در دسترس نیست"
        elif rsi_last > 55:
            votes["rsi"] = 1
            notes["rsi"] = f"RSI={rsi_last:.0f} — منطقه‌ی اشباعِ خرید"
        elif rsi_last < 45:
            votes["rsi"] = -1
            notes["rsi"] = f"RSI={rsi_last:.0f} — منطقه‌ی اشباعِ فروش"
        else:
            votes["rsi"] = 0
            notes["rsi"] = f"RSI={rsi_last:.0f} — خنثی"

        # ۴) فشارِ حجم — انبساطِ حجم فقط اگر با بدنه‌ی آخر هم‌جهت باشد
        v5 = float(vol.iloc[-5:].mean())
        v_prev = float(vol.iloc[-25:-5].mean()) if len(vol) >= 25 else 0.0
        body = float(close.iloc[-1] - (openc.iloc[-1] if openc.iloc[-1] == openc.iloc[-1] else close.iloc[-2]))
        votes["volume"] = _sign(body) if (v_prev > 0 and v5 > v_prev) else 0
        notes["volume"] = ("حجمِ ۵ کندلیِ آخر گسترده‌تر از ۲۰ کندلِ قبلِ آن"
                           if (v_prev > 0 and v5 > v_prev) else "حجمِ ۵ کندلیِ آخر گسترده نیست")

        # ۵) شکستِ کانالِ ۲۰ کندلی — کلوزِ آخر بیرون از کانالِ ۲۰ کندلِ قبل
        hh = float(high.iloc[-21:-1].max())
        ll = float(low.iloc[-21:-1].min())
        last = float(close.iloc[-1])
        votes["breakout"] = 1 if last > hh else (-1 if last < ll else 0)
        notes["breakout"] = (f"کلوز {last:,.4f} در برابرِ کانالِ [{ll:,.4f} … {hh:,.4f}]")

        score = 0.0
        active_w = 0.0
        agree_w = 0.0
        signals_out = []
        for key, fa, w in _SIGNALS:
            v = int(votes.get(key, 0))
            score += w * v
            if v != 0:
                active_w += w
            signals_out.append({"name": key, "fa": fa, "vote": v, "weight": w,
                                "note_fa": notes.get(key, "")})

        if score >= SIDE_THRESHOLD:
            side = 1
        elif score <= -SIDE_THRESHOLD:
            side = -1
        else:
            side = 0
        if side != 0 and active_w > 0:
            agree_w = sum(w for key, _fa, w in _SIGNALS
                          if int(votes.get(key, 0)) == side)
            conf = round(100.0 * agree_w / active_w)
        else:
            conf = None

        return {"ok": True, "engine": ENGINE, "version": ENGINE_VERSION,
                "side": side, "score": round(score, 2),
                "confidence_pct": conf, "active_weight": round(active_w, 2),
                "signals": signals_out,
                "note_fa": _note_fa(side, score, conf, signals_out)}
    except Exception as exc:  # noqa: BLE001 — پیش‌بینیِ نبود، بچ را نمی‌بُرد
        return {"ok": False, "engine": ENGINE,
                "error": f"{type(exc).__name__}: {exc}"}


def _note_fa(side: int, score: float, conf, signals: list[dict]) -> str:
    arrow = {1: "↑ صعودی", -1: "↓ نزولی", 0: "— بی‌ادعا"}[side]
    parts = [f"نبیه: {arrow} (امتیازِ {score:g}"]
    if conf is not None:
        parts.append(f"· اطمینانِ {conf}٪")
    parts.append(")")
    talkers = [s["fa"] for s in signals if s["vote"] != 0]
    if talkers:
        parts.append(" · رأی‌دهنده‌ها: " + "، ".join(talkers))
    return "".join(parts) if side != 0 else \
        f"نبیه: بی‌ادعا (امتیازِ {score:g} — از آستانه‌ی {SIDE_THRESHOLD:g} نگذشت)"


# ================================================================ دفترِ سایه + دروازه

def log_path() -> str:
    """مسیرِ دفترِ سایه‌ی نبیه — کنارِ دفترِ کرونوس در core/data/."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, "core", "data", "nabigha_log.jsonl")


def log_pred(symbol: str, interval: str, exchange: str, price: float,
             pred: dict, team_side: int = 0, signal_active: bool = False,
             ts: str | None = None, path: str | None = None,
             verdict_state: str | None = None) -> dict:
    """ثبتِ append-onlyِ یک پیش‌بینیِ سایه — fail-soft؛ هرگز بچ را نمی‌بُرد."""
    p = path or log_path()
    try:
        entry = {
            "ts": ts or datetime.now().strftime("%Y-%m-%d %H:%M"),
            "symbol": symbol, "interval": interval, "exchange": exchange,
            "price": price,
            "backend": ENGINE, "engine_version": ENGINE_VERSION,
            "nabigha_side": (int(pred["side"]) if pred.get("ok") and pred.get("side") in (1, -1) else None),
            "confidence_pct": (pred.get("confidence_pct") if pred.get("ok") else None),
            "score": (pred.get("score") if pred.get("ok") else None),
            "team_side": int(team_side) if team_side in (1, -1) else None,
            "signal_active": bool(signal_active),
            "note_fa": pred.get("note_fa"),
            "verdict_state": verdict_state,
        }
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return {"logged": True, "entry": entry, "path": p}
    except Exception as exc:  # noqa: BLE001
        return {"logged": False, "error": f"{type(exc).__name__}: {exc}"}


def _chart_side_of(room: dict) -> int:
    """جهتِ سیگنالِ چارت — همان مبنای شکاکِ اصلی (کپیِ منطقِ kronos_witness)."""
    for cl in ((room or {}).get("agents") or {}).get("chart", {}).get("claims") or []:
        if cl.get("by") == "chart":
            return int(cl.get("side") or 0)
    return 0


def gate_stats(path: str | None = None) -> dict:
    """آمارِ دروازه‌ی نبیه — همان قواعدِ صداقتِ کرونوس: فقط ادعای جهت‌دارِ دوطرفه.

    rate = هم‌جهتیِ نبیه با سیگنالِ چارت روی جلساتِ سیگنال‌دارِ واقعی؛
    جلساتِ بی‌ادعا ثبت می‌شوند ولی در آمار حذف‌اند (بی‌ادعا ≠ مخالفت).
    """
    p = path or log_path()
    entries: list[dict] = []
    try:
        with open(p, encoding="utf-8") as f:
            for line in f:
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                if isinstance(e, dict):  # null/[1,2] و هر غیرِ dict = خطِ خراب
                    entries.append(e)
    except FileNotFoundError:
        entries = []
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    sig = [e for e in entries
           if e.get("backend") == ENGINE and e.get("signal_active")
           and e.get("nabigha_side") in (1, -1) and e.get("team_side") in (1, -1)]
    agree = sum(1 for e in sig if int(e["nabigha_side"]) == int(e["team_side"]))
    rate = round(agree / len(sig) * 100.0, 1) if sig else None
    gate_pass = bool(len(sig) >= GATE_MIN_SESSIONS
                     and (rate or 0.0) >= GATE_MIN_AGREE_PCT)
    last = entries[-1] if entries else None
    return {"ok": True, "engine": ENGINE, "n_total": len(entries),
            "n_signal": len(sig), "agree": agree, "rate": rate,
            "gate_pass": gate_pass,
            "gate_fa": ("✅ دروازه‌ی نبیه گذشت" if gate_pass else
                        f"⏳ {len(sig)}/{GATE_MIN_SESSIONS} جلسه‌ی سیگنال‌دارِ نبیه" +
                        (f" · هم‌جهتیِ {rate}٪" if rate is not None else "")),
            "last": last}
