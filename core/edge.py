# -*- coding: utf-8 -*-
"""core/edge.py — موتور لبه (فاز ۵)
=============================================================
حلقه‌ی گمشده‌ی میدان: دروازه‌های فعلی فقط می‌پرسند «این ایجنت روی این ارز
الان بک‌تست سودده دارد؟» ولی هیچ دروازه‌ای نمی‌پرسد «خودِ این ایجنت در گذشته
سودده بوده؟» — یعنی ایجنتی با PF تاریخی ۰٫۲ همان حق رأی را دارد که ایجنتی با
PF تاریخی ۴٫۷. موتور لبه این شکاف را با شواهدِ بازپخش چندپنجره‌ای می‌بندد:

  ۱) بازپخش چندپنجره‌ای — یک بازپخش کامل روی کل تاریخچه، بعد تفکیک معامله‌ها
     به پنجره‌های زمانیِ جدا بر اساس «کندلِ ورود» (استاندارد تعلق عملکرد:
     معامله به دوره‌ای تعلق دارد که ورودش در آن رخ داده). پنجره‌ها روی ناحیه‌ی
     پس از گرم‌شدن (۳۰۰ کندل اول = پنجره‌ی بک‌تست) بریده می‌شوند و دُمِ آخر
     (۱۲۰ کندل فرصت بستن) هم به آخرین پنجره تعلق می‌گیرد.
  ۲) حکم لبه — قواعد ثابت و شفاف برای هر ایجنت (کمیسیون حکم ندارد؛ خودش
     مجموعِ ایجنت‌هاست):
       ❌ زیان‌ده   — حداقل معامله کافی + انتظاری کل زیر −۰٫۱۰R + زیان در
                      بیشتر از نیمِ پنجره‌های فعال
       ✅ سودده    — حداقل معامله کافی + انتظاری کل بالای +۰٫۰۵R + PF کل > ۱ +
                      هیچ پنجره‌ی فاجعه‌بار (انتظاری زیر −۰٫۲۵R) + زیان در
                      حداکثر نیمِ پنجره‌های فعال
       ⚠️ بی‌لبه   — بقیه (نمونه کم یا نتایج مخلوط) — بی‌حکم یعنی سقفِ مجاز
  ۳) گیت زنده — در اسکن زنده، ایجنتِ بنچ‌شده اجازه‌ی باز کردن معامله‌ی تازه
     ندارد (سه حالت: خاموش / بنچ زیان‌ده‌ها / فقط سودده‌ها).
  ۴) کمیسیون وزن‌دار — رأی ایجنت سودده ۱٫۲ و زیان‌ده ۰٫۸ شمرده می‌شود؛ اجماع
     وزنی ≥ ۳٫۰ لازم است. بدون دیتا همه وزن‌ها ۱ ⇒ رفتار عیناً مثل قبل.

صداقت روش (جایی پنهان نمی‌شود):
  • حکم‌ها از بازپخش می‌آیند نه از آینده‌بینی؛ جهانِ بازپخش نمادهای انتخابی
    کاربر است (غربالگری لحظه‌ایِ گذشته بازسازی‌شدنی نیست) و جای شواهد زنده را
    نمی‌گیرد — در صفحه هم همین گفته می‌شود.
  • بدون دیتای بازپخش یا با دیتای کهنه (بیش از EDGE_TTL_S)، گیت عملاً خنثی
    است و صفحه همان‌طور هشدار می‌دهد.
  • حکم‌ها و پنجره‌ها در فایل arena_edge.json ذخیره می‌شود (مثل fallback محلی
    میدان — با redeploy پاک می‌شود و دوباره بازپخش می‌گیرد).
"""
from __future__ import annotations

import json
import math
import os
import time
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from core import arena as A
from core import replay as RP
from core.arena_store import _utcnow_iso

# ---------------------------------------------------------------- ثابت‌های حکم
MIN_TRADES = 12          # حداقل معاملات کل برای صدور هر حکمی غیر از «بی‌لبه»
WIN_EXP = 0.05           # انتظاری کل بالای این = شرط سوددهی
LOSE_EXP = -0.10         # انتظاری کل زیر این = شرط زیان‌دهی
BAD_WIN_EXP = -0.25      # پنجره‌ای با انتظاری زیر این، حکم «سودده» را باطل می‌کند
WIN_PF = 1.0             # PF کل باید بالای این باشد برای حکم سودده

WEIGHTS = {"win": 1.2, "flat": 1.0, "lose": 0.8}   # وزن رأی ایجنت در کمیسیون
W_AGREE_MIN = 3.0        # اجماع وزنی لازمِ کمیسیون (معادل ۳ رأی خنثی ۱٫۰)

# ---------------------------------------------------------------- حالت‌های گیت
MODES = ("off", "bench_losers", "winners_only")
DEFAULT_MODE = "bench_losers"
MODE_FA = {"off": "خاموش — همه معامله می‌کنند",
           "bench_losers": "بنچ زیان‌ده‌ها (پیش‌فرض)",
           "winners_only": "سخت‌گیر — فقط سودده‌ها"}
MODE_EN = {"off": "Off — everyone trades",
           "bench_losers": "Bench losers (default)",
           "winners_only": "Strict — winners only"}
VERDICT_FA = {"win": "✅ سودده", "flat": "⚠️ بی‌لبه", "lose": "❌ زیان‌ده"}
VERDICT_EN = {"win": "✅ Profitable", "flat": "⚠️ No edge", "lose": "❌ Losing"}

# ---------------------------------------------------------------- ذخیره‌سازی
EDGE_FILE = "arena_edge.json"
EDGE_TTL_S = 7 * 24 * 3600     # اعتبار حکم‌ها: یک هفته — بعدش «کهنه»

# ---------------------------------------------------------------- هندسه‌ی پنجره
REPLAY_WARMUP = RP.REPLAY_WINDOW            # ۳۰۰ کندل گرم‌شدن — تولید رخداد از اینجا شروع می‌شود
RESOLVE_TAIL = A.TIMEOUT_CANDLES + 20       # دُمِ آخر: فرصت بستن معامله‌های وارده‌ی پنجره‌ی آخر


# =============================================================== منطقِ حکم (خالص — بدون شبکه)
def weight_for(verdicts: dict | None, agent: str) -> float:
    """وزن رأی ایجنت در کمیسیون — بدون دیتا = ۱٫۰ (رفتار قدیمی)."""
    v = (verdicts or {}).get(agent)
    return float(WEIGHTS.get(v, 1.0))


def allows(verdicts: dict | None, agent: str, mode: str) -> bool:
    """آیا این ایجنت مجاز به باز کردن معامله‌ی تازه است؟ (بی‌دیتا یا گیت خاموش = بله)"""
    v = (verdicts or {}).get(agent)
    if not v or mode not in ("bench_losers", "winners_only"):
        return True
    if mode == "winners_only":
        return v == "win"
    return v != "lose"


def committee_weighted_ok(verdicts: dict | None, agents_sig: dict, fd: int) -> tuple[bool, float]:
    """اجماع وزنی کمیسیون.
    agents_sig: {نام ایجنت: سیگنال (±۱/۰)} · fd: جهت نهایی کمیسیون.
    بدون دیتا همه وزن‌ها ۱ ⇒ معادل همان قانون قدیمی «۳ رأی از ۴»."""
    w = sum(weight_for(verdicts, nm) for nm, sg in agents_sig.items() if int(sg) == fd)
    return (w >= W_AGREE_MIN), float(w)


def agent_stats(closed: list[dict]) -> dict:
    """آمار یک دسته از معاملات بسته — n/انتظاری/PF/برد/باخت (R خالص بعد از هزینه)."""
    rs = [float(t.get("realized_r") or 0.0) for t in closed]
    n = len(rs)
    wins = [r for r in rs if r > 0.0]
    losses = [r for r in rs if r < 0.0]
    gross, loss_sum = sum(wins), -sum(losses)
    pf = (gross / loss_sum) if loss_sum > 0 else (99.0 if gross > 0 else 0.0)
    return {"n": n,
            "exp": (sum(rs) / n) if n else 0.0,
            "total_r": sum(rs),
            "pf": min(pf, 99.0),
            "wins": len(wins), "losses": len(losses)}


def verdict_for(window_stats: list[dict], total: dict) -> str:
    """حکم لبه از آمار پنجره‌ها + آمار کل یک ایجنت — قواعد ثابت بالای فایل.
    total باید از معاملات واقعی حساب شده باشد (PF سطح معامله، نه سطح پنجره)."""
    n_total = int(total.get("n") or 0)
    if n_total < MIN_TRADES:
        return "flat"
    active = [w for w in window_stats if w.get("n", 0) > 0]
    if not active:
        return "flat"
    n_lose_w = sum(1 for w in active if w["exp"] < 0)
    if total["exp"] < LOSE_EXP and n_lose_w * 2 > len(active):
        return "lose"
    has_bad_window = any(w["exp"] < BAD_WIN_EXP for w in active)
    if (total["exp"] > WIN_EXP and total["pf"] > WIN_PF
            and n_lose_w * 2 <= len(active) and not has_bad_window):
        return "win"
    return "flat"


def build_verdicts(window_trades: list[list[dict]], agents: list[str] | None = None) -> dict:
    """ورودی: معاملات بسته‌ی هر پنجره → خروجی {ایجنت: حکم} برای هر ۴ ایجنت (کمیسیون بدون حکم)."""
    names = list(agents) if agents else [p["name"] for p in A.participants() if p["kind"] == "agent"]
    out: dict[str, str] = {}
    for nm in names:
        ws = [agent_stats([t for t in wt if t.get("agent") == nm]) for wt in window_trades]
        tot = agent_stats([t for wt in window_trades for t in wt if t.get("agent") == nm])
        out[nm] = verdict_for(ws, tot)
    return out


# =============================================================== تفکیک پنجره‌ای
def _ts(v) -> pd.Timestamp:
    """تبدیل امن به Timestamp (UTC) — NaT برای ورودی خراب."""
    try:
        t = pd.Timestamp(v)
        if t.tzinfo is None:
            t = t.tz_localize("UTC")
        return t.tz_convert("UTC")
    except Exception:  # noqa: BLE001
        return pd.NaT


def multi_window_from_dfs(dfs: dict[str, pd.DataFrame], btc_d, exchange: str, interval: str,
                          windows: int = 3, candles_per_window: int = 250) -> dict:
    """یک بازپخش کامل روی کل تاریخچه + تفکیک پنجره‌ای بر اساس کندلِ ورود.
    بدون شبکه — قابل تست. مرز پنجره‌ها از ردیف‌های دیتای اولین نماد خوانده می‌شود."""
    if not dfs:
        return {"error": "هیچ دیتایی در دسترس نیست"}
    res = RP.replay_from_dfs(dfs, btc_d, exchange, interval)
    first = next(iter(dfs.values()))
    n_rows = len(first)
    start_row = REPLAY_WARMUP
    end_row = min(n_rows, start_row + windows * candles_per_window)
    if end_row - start_row < candles_per_window:
        return {"error": "تاریخچه برای این تعداد پنجره کوتاه است — کندل‌های بیشتری لازم است"}

    # مرزهای زمانی پنجره‌ها (از ردیف‌های واقعی دیتا — مستقل از بازپخش)
    bounds = [_ts(first["dt"].iloc[min(start_row + i * candles_per_window, n_rows - 1)])
              for i in range(windows)]

    w_trades: list[list[dict]] = [[] for _ in range(windows)]
    dropped = 0
    for t in res["closed"]:
        ot = _ts(t.get("opened_candle") or t.get("opened_at"))
        if ot is pd.NaT:
            dropped += 1
            continue
        w_idx = 0
        for i in range(1, windows):
            if ot >= bounds[i]:
                w_idx = i
        w_trades[w_idx].append(t)
    # (معامله‌های وارده در دُمِ آخر هم به آخرین پنجره تعلق می‌گیرند — تازه‌ترین شواهد)

    agents = [p["name"] for p in A.participants() if p["kind"] == "agent"]
    verdicts = build_verdicts(w_trades, agents)

    detail: dict[str, dict] = {}
    for nm in agents:
        ws = [agent_stats([t for t in wt if t.get("agent") == nm]) for wt in w_trades]
        tot = agent_stats([t for wt in w_trades for t in wt if t.get("agent") == nm])
        detail[nm] = {"windows": [{k: (round(v, 3) if isinstance(v, float) else v)
                                   for k, v in w.items()} for w in ws],
                      "total": {k: (round(v, 3) if isinstance(v, float) else v)
                                for k, v in tot.items()},
                      "verdict": verdicts[nm]}

    m = dict(res["meta"])
    m.update({"windows": int(windows), "candles_per_window": int(candles_per_window),
              "bounds": [b.strftime("%Y-%m-%dT%H:%M:%SZ") if b is not pd.NaT else "" for b in bounds],
              "dropped_no_time": int(dropped), "generated_at": _utcnow_iso()})
    return {"verdicts": verdicts, "detail": detail, "summary": res["summary"],
            "meta": m, "board": res["board"]}


def run_multi_window(exchange: str, interval: str, symbols: list[str], windows: int = 3,
                     candles_per_window: int = 250, workers: int = 6) -> dict:
    """لایه‌ی شبکه: کل تاریخچه‌ی لازم (گرم‌شدن + پنجره‌ها + دُم) گرفته می‌شود و بازپخش چندپنجره‌ای اجرا می‌شود."""
    total = REPLAY_WARMUP + int(windows) * int(candles_per_window) + RESOLVE_TAIL
    dfs, btc_d, errs = RP.fetch_dfs(exchange, symbols, interval, total, workers=workers)
    out = multi_window_from_dfs(dfs, btc_d, exchange, interval, int(windows), int(candles_per_window))
    if isinstance(out, dict):
        out.setdefault("meta", {}).setdefault("fetch_errors", errs)
    return out


# =============================================================== ذخیره‌سازی
def save_edge(data: dict) -> bool:
    """ذخیره‌ی حکم‌ها در arena_edge.json (اتمیک — مثل arena_store)."""
    try:
        tmp = EDGE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, EDGE_FILE)
        return True
    except Exception:  # noqa: BLE001
        return False


def load_edge(max_age_s: int | None = None) -> dict | None:
    """خواندن حکم‌ها — None برای فایل غایب/خراب/کهنه‌تر از max_age_s.
    max_age_s=None یعنی بدون چک سن (برای نمایش کهنگی در صفحه)."""
    if not os.path.exists(EDGE_FILE):
        return None
    try:
        with open(EDGE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or not isinstance(data.get("verdicts"), dict):
            return None
        gen = _ts(data.get("meta", {}).get("generated_at"))
        if gen is not pd.NaT:
            age = time.time() - gen.timestamp()
            data.setdefault("meta", {})["age_s"] = int(max(0, age))
            if max_age_s is not None and age > max_age_s:
                return None
        return data
    except Exception:  # noqa: BLE001
        return None
