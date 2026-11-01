"""core/replay.py — بازپخش تاریخی میدان (Walk-Forward Replay)
=============================================================
همان موتور و همان دروازه‌های «اسکن زنده»ی میدان ایجنت‌ها، این‌بار روی کندل‌های
تاریخی پخش می‌شود تا بدون انتظار هفته‌ها برای ۱۰۰+ معامله‌ی زنده، مشخص شود این
ترکیب در گذشته سودده بوده یا نه (شواهدِ قانون آهنین: پول واقعی فقط با ۱۰۰+
معامله و انتظاری مثبت).

دو مرحله (عیناً مثل زنده، فقط روی تاریخ):
  مرحله ۱ — رخدادها: روی هر نماد، از کندل ۳۰۰ام به بعد (کامل‌شدن پنجره‌ی
           بک‌تست ۳۰۰تایی مثل اسکن زنده) در هر کندل برای هر ۴ ایجنت و کمیسیون
           دروازه‌ها به‌ترتیب ارزانی→گرانی چک می‌شود:
             سیگنال ≠ صفر · علامت امتیاز هم‌جهت · امتیاز ≥ آستانه · فیلتر رژیم BTC
             → بک‌تست دقیق روی همان پنجره‌ی ۳۰۰تایی (PF>1 و total>0 — همان
               هیسترزیسِ تازه روی همان پنجره، مثل فریم ۳۰۰تاییِ اسکن زنده)
             → ساخت پوزیشن روی تاریخچه‌ی بریده‌شده تا همان کندل (سوییپ/زون‌ها
               علّی‌اند) → R:R ≥ ۱
           خروجی: فهرست «رخداد» با کیفیت (همان فرمول quality اسکن زنده).
  مرحله ۲ — زمان‌بند: رخدادها به‌ترتیب زمان (و کیفیت) پردازش می‌شوند و سهمیه‌ها
           اعمال می‌شود: حداکثر ۳ پوزیشن باز هر شرکت‌کننده، سقف ۱۵ کل میدان،
           یک پوزیشن باز به‌ازای هر نماد/شرکت‌کننده و cooldown ده‌کندلی بعد از
           بستن. هر معامله‌ی بازشده بلافاصله با همان simulate_trade موتور زنده
           (استاپ اول، نردبان TP، تایم‌اوت، کارمزد+لغزش واقعی) تا بسته‌شدن
           پیش برده می‌شود — کندل خروج با جست‌وجوی دودویی روی طول پیشوند پیدا
           می‌شود تا closed_at/closed_price تاریخیِ دقیق ثبت شود.

صداقت روش (محدودیت‌ها که جایی پنهان نمی‌شوند):
  • جهانِ بازپخش = نمادهای انتخابی کاربر (پیش‌فرض ۱۲ ارز بزرگ) — غربالگریِ
    «قدرتِ لحظه‌ای» بازار در گذشته بازسازی‌شدنی نیست (تیکر تاریخی از API عمومی
    نمی‌آید)؛ پس انتظاری را باید در سطح ایجنت خواند، نه ادعای بازپخشِ کل بازار.
  • دروازه‌ی ستاپ سه‌سطحیِ ورود (سخت‌گیر/متعادل) در بازپخش اعمال نمی‌شود —
    رفتار معادل سطح «شکارچی» (پیش‌فرض زنده) بازسازی می‌شود.
  • اندیکاتورها روی کل تاریخچه‌ی گرفته‌شده حساب می‌شوند (گرم‌شدنِ بهتر از فریم
    ۳۰۰تایی زنده) — کمی خوش‌بین‌تر از زنده، ولی کاملاً علّی: هیچ تصمیمی در کندل
    t از داده‌ی بعد از t استفاده نمی‌کند.
  • همه‌چیز determinstic است: همان ورودی → همان خروجی.
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

from core import arena as A
from core import gaps as G
from core.duel_engine import AGENTS, FACTOR_FA, _dec_for, agent_scores, backtest, build_features, build_position, describe, get_df, signals_with_hysteresis

REPLAY_WINDOW = 300        # پنجره‌ی بک‌تست هر ایجنت — مثل اسکن زنده (۳۰۰ کندل)
DEFAULT_CANDLES = 700      # طول تاریخچه‌ی هر نماد (کندل) — ۳۰۰تای اول گرم‌شدن است
CANDLE_CHOICES = [500, 700, 1000]
MAX_SYMBOLS = 20           # ترمز بارِ شبکه — بیشتر از این جهانِ بازپخش نمی‌گیرد


def _iso(ts) -> str:
    """تبدیل امن Timestamp به رشته‌ی ISO UTC (برای فیلدهای رکورد)."""
    t = A.to_ts(ts)
    return "" if t is pd.NaT else t.strftime("%Y-%m-%dT%H:%M:%SZ")


# ----------------------------------------------------------------------------- regime (فیلتر BTC)
def _regime_lookup(btc_d: pd.DataFrame):
    """تابعِ نگاه‌بندی رژیم: برای هر لحظه، آخرین کندل BTC با dt ≤ همان لحظه
    (asof — علّی؛ کندلِ در حالِ شکل‌گیریِ بعدی هرگز استفاده نمی‌شود).
    dir = +1 بالای MA50 · −1 زیرش · ۰ گرم‌نشده/بدون دیتا (فیلتر خاموش — مثل زنده)."""
    if not isinstance(btc_d, pd.DataFrame) or btc_d.empty or "dt" not in btc_d.columns:
        return lambda _t: 0
    btc = btc_d.sort_values("dt").reset_index(drop=True)
    s = pd.to_numeric(btc["close"], errors="coerce")
    ma = s.rolling(A.REGIME_MA_N).mean()          # min_periods پیش‌فرض = پنجره → گرم‌نشده = NaN
    d_arr = np.where(s > ma, 1, np.where(s < ma, -1, 0)).astype(int)
    bad = np.isnan(s.to_numpy(dtype=float)) | np.isnan(ma.to_numpy(dtype=float))
    d_arr[bad] = 0
    keys = np.asarray(pd.to_datetime(btc["dt"]), dtype="datetime64[ns]").astype("int64")
    return lambda t: int(d_arr[max(0, int(np.searchsorted(keys, A.to_ts(t).value, side="right") - 1))])


# ----------------------------------------------------------------------------- مرحله ۱ — رخدادها
def candidate_events(symbol: str, d: pd.DataFrame, regime_at, appetite: str = "hunter",
                     fee_pct: float = A.FEE_PCT, balance: float = A.START_EQUITY) -> tuple[list[dict], int]:
    """روی یک نماد، از کندل REPLAY_WINDOW به بعد در هر کندل دروازه‌ها را چک می‌کند.
    خروجی: (رخدادهای واجد شرایط, شمارِ ایجنت-کندل‌های خلاف رژیم)"""
    if not isinstance(d, pd.DataFrame) or d.empty or "dt" not in d.columns:
        return [], 0
    if len(d) < REPLAY_WINDOW + 5:
        return [], 0
    d = d.sort_values("dt").reset_index(drop=True)
    try:
        F, extras = build_features(d)
    except Exception:  # noqa: BLE001 — دیتای خراب: این نماد بدون رخداد رد می‌شود
        return [], 0
    close = d["close"].to_numpy(dtype=float)
    n = len(d)
    dec = _dec_for(float(close[-1]))
    has_adx = "adx" in d.columns

    # امتیاز هر ایجنت روی کل تاریخچه — یک‌بار (فاکتورها همه علّی‌اند)
    scores = {name: agent_scores(F, spec) for name, spec in AGENTS.items()}

    events: list[dict] = []
    n_reg_blocked = 0

    for i in range(REPLAY_WINDOW, n):
        reg = int(regime_at(d["dt"].iloc[i]) or 0)
        lo = max(0, i - REPLAY_WINDOW + 1)
        win_close = close[lo:i + 1]
        d_i = F_i = extras_i = None      # تاریخچه‌ی بریده تا کندل i — هر کندل از نو و فقط در صورت نیاز

        # سیگنالِ پنجره‌ای هر ایجنت + بک‌تست دقیق همان پنجره (یک‌بار برای هر دو مصرف: ایجنت و کمیسیون)
        per: dict[str, dict] = {}
        for name, spec in AGENTS.items():
            sw = signals_with_hysteresis(scores[name][lo:i + 1], spec["thr"])
            bt = backtest(win_close, sw, balance, fee_pct)
            per[name] = {"g": int(sw[-1]), "sw": sw, "bt": bt, "s_i": float(scores[name][i])}

        # ---- ایجنت‌ها ------------------------------------------------------------
        for name, spec in AGENTS.items():
            p = per[name]
            gi, si = p["g"], p["s_i"]
            if gi == 0 or np.sign(si) != gi or abs(si) < spec["thr"]:
                continue
            if reg != 0 and gi != reg:
                n_reg_blocked += 1
                continue
            bt = p["bt"]
            if not (bt["pf"] > 1.0 and bt["total"] > 0):
                continue
            if d_i is None:
                d_i = d.iloc[:i + 1].reset_index(drop=True)
                F_i = F.iloc[:i + 1].reset_index(drop=True)
                extras_i = {"gaps": G.gap_analysis(d_i),
                            "close10": float(close[i - 10]),
                            "prior_hi": float(extras["prior_hi"].iloc[i]),
                            "prior_lo": float(extras["prior_lo"].iloc[i])}
            pos = build_position(d_i, F_i, extras_i, gi, dec)
            if pos["direction"] == 0 or float(pos.get("rr") or 0) < 1.0:
                continue
            r_i = F.iloc[i]
            top2 = sorted(spec["weights"], key=lambda k: -abs(float(np.nan_to_num(r_i[k])) * spec["weights"][k]))[:2]
            ev_text = " · ".join(f"{FACTOR_FA[k]}: {describe(k, r_i, d_i.iloc[-1], dec, extras_i)}" for k in top2)
            quality = abs(si) * min(2.5, max(float(bt["pf"]), 0.0)) * min(float(pos.get("rr") or 0), 3.0)
            events.append({"who": name, "symbol": symbol, "dir": gi, "score": si, "pos": pos,
                           "evidence": ev_text[:400], "quality": quality, "row": i, "dt": _iso(d["dt"].iloc[i]),
                           "dec": dec, "adx": float(d["adx"].iloc[i]) if has_adx else 0.0})

        # ---- کمیسیون (اجماع وزن‌دار — عیناً فرمول calculate_duel) --------------------
        weights = {}
        for name, spec in AGENTS.items():
            bt = per[name]["bt"]
            q = np.clip(bt["total"] / 10, -1, 2) + np.clip(bt["pf"] - 1, -1, 1) + (bt["win"] - 50) / 50 - bt["dd"] / 50
            weights[name] = float(max(0.15, 1 + q))
        tot_w = sum(weights.values()) or 1.0
        final_s = sum(weights[nm] * per[nm]["s_i"] for nm in per) / tot_w
        fd = 1 if final_s > 0.15 else -1 if final_s < -0.15 else 0
        if fd == 0:
            continue
        n_agree = sum(1 for nm in per if per[nm]["g"] == fd)
        if n_agree < 3:
            continue
        if reg != 0 and fd != reg:
            n_reg_blocked += 1
            continue
        if d_i is None:
            d_i = d.iloc[:i + 1].reset_index(drop=True)
            F_i = F.iloc[:i + 1].reset_index(drop=True)
            extras_i = {"gaps": G.gap_analysis(d_i),
                        "close10": float(close[i - 10]),
                        "prior_hi": float(extras["prior_hi"].iloc[i]),
                        "prior_lo": float(extras["prior_lo"].iloc[i])}
        fpos = build_position(d_i, F_i, extras_i, fd, dec)
        if fpos["direction"] == 0 or float(fpos.get("rr") or 0) < 1.0:
            continue
        n_against = sum(1 for nm in per if per[nm]["g"] == -fd)
        n_neutral = len(per) - n_agree - n_against
        split = f" · {n_against} مخالف" if n_against else (f" · {n_neutral} خنثی" if n_neutral else " · اجماع کامل")
        events.append({"who": A.COMMITTEE["name"], "symbol": symbol, "dir": fd, "score": final_s, "pos": fpos,
                       "evidence": f"اجماع {n_agree}/4 ایجنت{split}", "confidence": int(min(95, 40 + abs(final_s) * 80 + n_agree * 7)),
                       "quality": abs(final_s) * (1 + 0.2 * n_agree), "row": i, "dt": _iso(d["dt"].iloc[i]),
                       "dec": dec, "adx": float(d["adx"].iloc[i]) if has_adx else 0.0})

    return events, n_reg_blocked


# ----------------------------------------------------------------------------- شبیه‌سازی تا بسته‌شدن
def _simulate_to_close(rec: dict, d: pd.DataFrame, open_row: int) -> tuple[dict, int | None]:
    """معامله‌ی تازه‌بازشده را با موتور زنده (simulate_trade) تا بسته‌شدن پیش می‌برد.
    خروجی: (رکورد نهایی, شماره‌ی ردیف کندل خروج — یا None اگر تا انتهای تاریخچه باز بماند).
    کندل خروج با جست‌وجوی دودویی روی طول پیشوند پیدا می‌شود (بسته‌شدن نسبت به طول
    پیشوند یک‌نوا است) تا closed_at/closed_price تاریخیِ دقیق ثبت شود."""
    base = dict(rec)
    full = A.simulate_trade(base, d)
    if not full or full.get("status") != "closed":
        return {**base, **(full or {})}, None
    lo, hi = open_row + 2, len(d)          # طول پیشوند: دست‌کم یک کندل بعد از ورود
    while lo < hi:
        mid = (lo + hi) // 2
        p = A.simulate_trade(base, d.iloc[:mid])
        if p.get("status") == "closed":
            hi = mid
        else:
            lo = mid + 1
    patch = A.simulate_trade(base, d.iloc[:lo]) or {}
    exit_row = lo - 1
    out = {**base, **patch, "closed_at": _iso(d["dt"].iloc[exit_row])}
    return out, exit_row


# ----------------------------------------------------------------------------- مرحله ۲ — زمان‌بند
def _schedule(events: list[dict], dfs: dict[str, pd.DataFrame], exchange: str, interval: str) -> dict:
    """رخدادها به‌ترتیب زمان (بعد کیفیت)؛ سهمیه‌ها و cooldown عیناً مثل زنده.
    پوزیشنِ باز یعنی close_row ≥ ردیفِ فعلی (کندل خروج هم اشغال حساب می‌شود — محافظه‌کارانه)."""
    events = sorted(events, key=lambda e: (str(e["dt"]), -float(e["quality"]), e["symbol"], e["who"]))
    active: list[dict] = []       # {who, symbol, dir, close_row, opened_row}
    last_close: dict[tuple, int] = {}
    closed: list[dict] = []
    opens: list[dict] = []
    blocked_full = blocked_cool = blocked_busy = 0

    for ev in events:
        who, sym, dr = ev["who"], ev["symbol"], int(ev["dir"])
        row_i = int(ev["row"])
        live_rows = [a for a in active if a["close_row"] >= row_i]
        if sum(1 for a in live_rows if a["who"] == who) >= A.MAX_POS_PER_AGENT or len(live_rows) >= A.GLOBAL_CAP:
            blocked_full += 1
            continue
        if any(a["who"] == who and a["symbol"] == sym for a in live_rows):
            blocked_busy += 1
            continue
        lc = last_close.get((who, sym, dr))
        if lc is not None and row_i - lc < A.COOLDOWN_CANDLES:
            blocked_cool += 1
            continue
        rec = A.make_trade_record(who, {"symbol": sym, "dec": ev["dec"], "last_dt": ev["dt"], "adx": ev["adx"]},
                                  ev, exchange, interval)
        rec["opened_at"] = ev["dt"]
        rec["opened_candle"] = ev["dt"]
        rec["last_candle"] = ev["dt"]
        rec, close_row = _simulate_to_close(rec, dfs[sym], row_i)
        active.append({"who": who, "symbol": sym, "dir": dr,
                       "close_row": float("inf") if close_row is None else close_row, "opened_row": row_i})
        if close_row is None:
            opens.append(rec)
        else:
            closed.append(rec)
            last_close[(who, sym, dr)] = close_row

    return {"closed": closed, "opens": opens, "blocked_full": blocked_full,
            "blocked_cool": blocked_cool, "blocked_busy": blocked_busy}


# ----------------------------------------------------------------------------- تجمیع و گزارش
def _per_symbol(closed: list[dict]) -> list[dict]:
    agg: dict[str, dict] = {}
    for t in closed:
        k = str(t.get("symbol"))
        a = agg.setdefault(k, {"symbol": k, "n": 0, "total_r": 0.0, "wins": 0, "losses": 0})
        r = float(t.get("realized_r") or 0.0)
        a["n"] += 1
        a["total_r"] += r
        a["wins"] += 1 if r > 0 else 0
        a["losses"] += 1 if r < 0 else 0
    return sorted(({"symbol": a["symbol"], "n": a["n"], "total_r": round(a["total_r"], 2),
                    "expectancy": round(a["total_r"] / a["n"], 3), "wins": a["wins"], "losses": a["losses"]}
                   for a in agg.values()), key=lambda x: -x["total_r"])


def replay_from_dfs(dfs: dict[str, pd.DataFrame], btc_d, exchange: str, interval: str,
                    appetite: str = "hunter", fee_pct: float = A.FEE_PCT) -> dict:
    """بازپخش کامل از روی دیتای آماده (بدون شبکه — قابل تست)."""
    t0 = time.time()
    # مرتب‌سازی دفاعی: اندیسِ ردیف در رخدادها باید با فریمِ زمان‌بند یکی باشد
    for sym in list(dfs):
        d = dfs[sym]
        if isinstance(d, pd.DataFrame) and "dt" in d.columns:
            dfs[sym] = d.sort_values("dt").reset_index(drop=True)
    regime_at = _regime_lookup(btc_d)
    events: list[dict] = []
    reg_blocked = 0
    errors: list[str] = []
    used: list[str] = []
    for sym, d in dfs.items():
        try:
            evs, rb = candidate_events(sym, d, regime_at, appetite, fee_pct)
            events.extend(evs)
            reg_blocked += rb
            used.append(sym)
        except Exception as e:  # noqa: BLE001
            errors.append(f"{sym}: {type(e).__name__}: {e}")

    sched = _schedule(events, dfs, exchange, interval)
    closed, opens = sched["closed"], sched["opens"]
    summary = A.arena_summary(closed)
    board = A.leaderboard(closed, opens)
    curve = A.equity_curve(closed)

    times = [str(t.get("opened_candle") or "") for t in closed + opens] + [str(t.get("closed_at") or "") for t in closed]
    times = [t for t in times if t]
    span_days = 0.0
    if len(times) >= 2:
        t_a, t_b = A.to_ts(min(times)), A.to_ts(max(times))
        if t_a is not pd.NaT and t_b is not pd.NaT:
            span_days = (t_b - t_a).total_seconds() / 86400.0

    return {
        "summary": summary, "board": board, "closed": closed, "opens": opens,
        "curve": curve, "per_symbol": _per_symbol(closed),
        "meta": {"exchange": exchange, "interval": interval, "symbols": used, "errors": errors,
                 "n_events": len(events), "reg_blocked": reg_blocked,
                 "blocked_full": sched["blocked_full"], "blocked_cool": sched["blocked_cool"],
                 "blocked_busy": sched["blocked_busy"],
                 "from": min(times) if times else "", "to": max(times) if times else "",
                 "span_days": round(span_days, 1), "took": round(time.time() - t0, 1)},
    }


# ----------------------------------------------------------------------------- لایه‌ی شبکه (صفحه)
def fetch_dfs(exchange: str, symbols: list[str], interval: str, candles: int,
              workers: int = 6) -> tuple[dict[str, pd.DataFrame], pd.DataFrame | None, list[str]]:
    """دریافت موازی کندل‌های نمادها + BTC/USDT چهارساعته برای فیلتر رژیم.
    خروجی: ({نماد: دیتا فریم}, دیتای BTC, خطاها)"""
    out: dict[str, pd.DataFrame] = {}
    errors: list[str] = []

    def _one(sym: str):
        d, _s, _src = get_df(exchange, sym, interval, int(candles))
        return sym, d

    init = None
    try:
        from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx
        ctx = get_script_run_ctx()
        if ctx is not None:
            def init():  # noqa: E306
                add_script_run_ctx(A.threading_current(), ctx)
    except Exception:  # noqa: BLE001
        init = None

    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(symbols) + 1)), initializer=init) as ex:
        futs = [ex.submit(_one, s) for s in symbols]
        reg_sym = "BTC" if exchange == "Lighter" else A.REGIME_SYMBOL
        fut_btc = ex.submit(get_df, exchange, reg_sym, A.REGIME_TF, int(candles + A.REGIME_MA_N + 60))
        for f in futs:
            try:
                sym, d = f.result()
                if isinstance(d, pd.DataFrame) and not d.empty:
                    out[sym] = d
            except Exception as e:  # noqa: BLE001
                errors.append(f"{f.args[0] if f.args else '?'}: {type(e).__name__}: {e}")
        btc_d = None
        try:
            btc_d = fut_btc.result()[0]
        except Exception:  # noqa: BLE001
            btc_d = None
    return out, btc_d, errors
