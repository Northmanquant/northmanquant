"""🏟️ Agent Arena — میدان ایجنت‌ها (لیگ معاملاتی کاغذی)
هر شرکت‌کننده (۴ ایجنت + کمیسیون) مستقلاً صرافی را اسکن می‌کند، ارز خودش را
انتخاب می‌کند، معامله‌ی کاغذی باز می‌کند و تا TP/SL/تایم‌اوت مدیریت می‌شود.
لیدربورد: امتیاز R-based + وین‌ریت + ایکوییتی.
"""
from __future__ import annotations

import time
from datetime import datetime
from html import escape as _esc

import numpy as np
import pandas as pd
import streamlit as st
from core.i18n import setup_i18n, get_lang

st.set_page_config(page_title="Agent Arena", page_icon="🏟️", layout="wide")
LANG = setup_i18n(page="p4")   # زبان + منوی ترجمه‌شده + پچ ترجمه‌ی کل صفحه


def L(fa: str, en: str) -> str:
    return en if LANG == "en" else fa


st.title("🏟️ " + L("میدان ایجنت‌ها — لیگ معاملاتی", "Agent Arena — Trading League"))
st.caption(L(
    "۵ شرکت‌کننده (۴ ایجنت + کمیسیون) اول کل بازار صرافی را غربال می‌کنند تا قوی‌ترین ارزها را پیدا کنند، "
    "بعد همان‌ها را با موتور تحلیل و بک‌تست خودشان عمیق بررسی و معامله‌ی کاغذی باز می‌کنند. "
    "معامله‌ها بین بازدیدها زنده می‌مانند و تا TP/SL/تایم‌اوت مدیریت می‌شوند. "
    "در پایان: کدوم ایجنت بهترین وین‌ریت و امتیاز را می‌گیرد؟",
    "5 participants (4 agents + Committee) first screen the WHOLE exchange market to find the strongest coins, "
    "then deep-analyze those with their own engine and open paper trades. "
    "Trades persist between visits and are managed until TP/SL/timeout. Who ends up with the best winrate and score?"))

from core import arena as A  # noqa: E402
from core import alerts as AL  # noqa: E402
from core import news as NW  # noqa: E402
from core import replay as RP  # noqa: E402
from core import edge as EG  # noqa: E402
from core import arena_store  # noqa: E402
from core.duel_engine import _dec_for  # noqa: E402

EXCHANGES = ["KuCoin", "OKX", "Binance", "Bybit", "Lighter", "XT", "LBank", "KCEX"]
_store = arena_store.get_store()

# فاز ۵ — حکم‌های لبه از بازپخش چندپنجره‌ای: فقط حکمِ تازه گیت می‌شود، کهنه فقط نمایش داده می‌شود
_edge_state_any = EG.load_edge()
_edge_fresh = EG.load_edge(EG.EDGE_TTL_S)
_verdicts = (_edge_fresh or {}).get("verdicts")
_edge_mode = st.session_state.get("edge_mode", EG.DEFAULT_MODE)

DIR_FA = {1: "لانگ 🟢", -1: "شورت 🔴", 0: "خنثی ⚪"}
RESULT_FA = {"win": " برد ✅", "loss": "باخت 💀", "be": "سر‌به‌سر ➖",
             "timeout_win": "تایم‌اوت سودده 🟡", "timeout_loss": "تایم‌اوت زیان‌ده 🟠", "timeout_be": "تایم‌اوت خنثی ⚪"}
RESULT_EN = {"win": "Win ✅", "loss": "Loss 💀", "be": "Breakeven ➖",
             "timeout_win": "Timeout profit 🟡", "timeout_loss": "Timeout loss 🟠", "timeout_be": "Timeout flat ⚪"}


def _res_badge(res: str) -> str:
    return (RESULT_EN if LANG == "en" else RESULT_FA).get(res, res)


def _age_label(t: dict) -> str:
    oc = A.to_ts(t.get("opened_candle"))
    if oc is pd.NaT:
        return "—"
    mins = A.INTERVAL_MIN.get(t.get("interval", "1hour"), 60)
    elapsed = int((pd.Timestamp.now(tz="UTC") - oc).total_seconds() // 60 // max(1, mins))
    return f"{elapsed}/{A.TIMEOUT_CANDLES}" + L(" کندل", " candles")


# =============================================================================
# پیش‌بردن خودکار معاملات باز (هر ۶۰ ثانیه حداکثر یک‌بار)
_live: dict = {}
_just_closed: list[dict] = []
try:
    _now = time.time()
    if _now - st.session_state.get("_arena_upd", 0) >= 60:
        st.session_state["_arena_upd"] = _now
        _live, _just_closed = A.update_all_trades(_store)
        st.session_state["_arena_live"] = _live
        for _t in _just_closed:          # هشدار بسته‌شدن — دائمی در Supabase/فایل
            try:
                AL.get_alerts().insert(AL.close_alert(_t))
            except Exception:  # noqa: BLE001
                pass
    else:
        _live = st.session_state.get("_arena_live", {})
except Exception as _e:  # noqa: BLE001
    st.caption(L(f"به‌روزرسانی معاملات انجام نشد: {_e}", f"Trade update failed: {_e}"))

_all_trades = _store.load_all()
_open_trades = [t for t in _all_trades if t.get("status") == "open"]
_closed_trades = [t for t in _all_trades if t.get("status") == "closed"]

if _just_closed:
    for _t in _just_closed[:6]:
        pts = float(_t.get("points") or 0)
        emoji = "🏆" if pts >= 5 else "✅" if pts > 0 else "💀" if pts < 0 else "➖"
        st.toast(f"{emoji} {_t.get('agent')} · {_t.get('symbol')} → "
                 f"{_res_badge(str(_t.get('result')))} ({float(_t.get('realized_r') or 0):+.2f}R · {pts:+.0f} امتیاز)")

_hc = _store.healthcheck()
if _hc.get("reason") == "table_error":
    _err = str(_hc.get("error") or "")
    if "does not exist" in _err.lower() or "42p01" in _err.lower():
        st.warning(L(
            "اتصال به Supabase ✅ برقرار است اما جدول arena_trades هنوز ساخته نشده — "
            "فایل sql/arena_setup.sql را یک‌بار در Supabase → SQL Editor اجرا کن و صفحه را رفرش کن.",
            "Supabase ✅ connected but the arena_trades table doesn't exist yet — "
            "run sql/arena_setup.sql once in Supabase → SQL Editor, then refresh."))
    else:
        st.warning(L(
            f"اتصال به Supabase برقرار است اما خواندن جدول خطا داد: {_err[:140]}",
            f"Supabase connected but table read failed: {_err[:140]}"))
elif _hc.get("reason") == "client_error":
    st.warning(L(
        f"SUPABASE_URL و SUPABASE_KEY خوانده شدند اما ساخت کلاینت شکست خورد: {str(_hc.get('error') or '')[:120]} — "
        "چک کن URL دقیقاً شبیه https://xxxx.supabase.co باشد (بدون / آخر).",
        f"SUPABASE_URL/SUPABASE_KEY read but client creation failed: {str(_hc.get('error') or '')[:120]} — "
        "URL must look exactly like https://xxxx.supabase.co (no trailing slash)."))
elif _hc.get("reason") == "no_secrets":
    _miss = " و ".join(_hc.get("missing") or ["SUPABASE_URL", "SUPABASE_KEY"])
    _toml = 'SUPABASE_URL = "https://xxxx.supabase.co"\nSUPABASE_KEY = "eyJhbGci...anon-key"'
    st.warning(L(
        f"داده‌ی میدان الان روی فایل محلی ذخیره می‌شود (با redeploy پاک می‌شود). دو قدم تا اتصال دائمی:\n\n"
        f"۱️⃣ **اجرای SQL**: فایل `sql/arena_setup.sql` را در Supabase → SQL Editor یک‌بار اجرا کن.\n\n"
        f"۲️⃣ **افزودن Secrets**: در Streamlit Cloud → Manage app → Settings → Secrets این دو خط را اضافه کن "
        f"(الان {_miss} پیدا نمی‌شود):\n\n"
        f"```toml\n{_toml}\n```\n\n"
        f"URL را از Supabase → Settings → API → Project URL بگیر و KEY همان **anon public** است (نه service_role). "
        f"بعد از Save، اپ خودش ری‌استارت می‌شود و این هشدار محو می‌شود.",
        f"Arena data is stored in a local file (lost on redeploy). Two steps to connect:\n\n"
        f"1️⃣ **Run SQL**: run `sql/arena_setup.sql` once in Supabase → SQL Editor.\n\n"
        f"2️⃣ **Add Secrets**: in Streamlit Cloud → Manage app → Settings → Secrets add these two lines "
        f"(currently {_miss} is missing):\n\n"
        f"```toml\n{_toml}\n```\n\n"
        f"Get the URL from Supabase → Settings → API → Project URL; KEY is the **anon public** key (not service_role). "
        f"After Save the app restarts and this warning disappears."))

_m1, _m2, _m3, _m4 = st.columns(4)
_m1.metric(L("پوزیشن‌های باز", "Open positions"), len(_open_trades))
_m2.metric(L("معاملات بسته‌شده", "Closed trades"), len(_closed_trades))
_m3.metric(L("شرکت‌کننده‌ها", "Participants"), len(A.participants()))
_m4.metric(L("ریسک هر معامله", "Risk per trade"), f"{A.RISK_PCT:.0f}%")

tab_scan, tab_pos, tab_alerts, tab_news, tab_board, tab_replay, tab_edge = st.tabs([
    "🔎 " + L("اسکن و معامله‌ی جدید", "Scan & new trades"),
    "📊 " + L("پوزیشن‌های باز", "Open positions"),
    "🔔 " + L("هشدارها", "Alerts"),
    "📰 " + L("اخبار بازار", "Market news"),
    "🏆 " + L("لیدربورد و تاریخچه", "Leaderboard & history"),
    "🧪 " + L("بازپخش تاریخی", "Historical replay"),
    "⚖️ " + L("اعتبار لبه", "Edge credibility"),
])

# =============================================================================
# ابزارهای نمایش
def _dir_badge(direction: int) -> str:
    tone = "#16a34a" if direction > 0 else "#ef4444"
    label = DIR_FA.get(direction) if LANG != "en" else {1: "LONG 🟢", -1: "SHORT 🔴", 0: "FLAT ⚪"}.get(direction)
    return f"<span style='color:{tone};font-weight:800'>{label}</span>"


def _chip(agent: str, color: str) -> str:
    return (f"<span style='background:{color}22;border:1px solid {color}55;border-radius:8px;"
            f"padding:2px 8px;font-size:12px;font-weight:700'>{agent}</span>")


def _trade_card(t: dict, live_price: float | None, unrealized: float | None) -> None:
    dec = int(t.get("dec", 4))
    color = t.get("color", "#94a3b8")
    done1 = "✅" if t.get("tp1_done") else "▫️"
    done2 = "✅" if t.get("tp2_done") else "▫️"
    stop_now = float(t.get("cur_stop") or t.get("stop"))
    ur_txt = "—" if unrealized is None else f"{unrealized:+.2f}R"
    ur_col = "#16a34a" if (unrealized or 0) > 0 else "#ef4444" if (unrealized or 0) < 0 else "#94a3b8"
    lp_txt = "—" if not live_price else f"{live_price:,.{dec}f}"
    # امنیت: فیلدهای رشته‌ای که ممکن است از دیتابیس/دیتای صرافی آمده باشند escape می‌شوند
    _agent = _esc(str(t.get("agent", "")))
    _sym = _esc(str(t.get("symbol", "")))
    _interval = _esc(str(t.get("interval", "")))
    _evidence = _esc(str(t.get("evidence", ""))) if t.get("evidence") else ""
    st.markdown(
        f"<div dir='rtl' style='border:1px solid rgba(148,163,184,.25);border-right:5px solid {color};"
        f"border-radius:14px;padding:12px 14px;margin:8px 0;background:rgba(148,163,184,.05)'>"
        f"<div style='display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;align-items:center'>"
        f"<span>{_chip(_agent, color)} <b style='font-size:16px'>{_sym}</b> {_dir_badge(int(t.get('direction') or 0))}</span>"
        f"<span style='font-family:ui-monospace,monospace;font-size:14px;color:{ur_col}'>R فعلی: {ur_txt}</span>"
        f"</div>"
        f"<div style='display:grid;grid-template-columns:repeat(5,1fr);gap:6px;margin-top:10px;text-align:center;font-size:12px'>"
        f"<div><div style='color:#94a3b8'>ورود</div><b>{t.get('entry'):,.{dec}f}</b></div>"
        f"<div><div style='color:#94a3b8'>SL فعلی</div><b style='color:#ef4444'>{stop_now:,.{dec}f}</b></div>"
        f"<div><div style='color:#94a3b8'>TP1 {done1}</div><b style='color:#16a34a'>{t.get('tp1'):,.{dec}f}</b></div>"
        f"<div><div style='color:#94a3b8'>TP2 {done2}</div><b style='color:#16a34a'>{t.get('tp2'):,.{dec}f}</b></div>"
        f"<div><div style='color:#94a3b8'>TP3</div><b style='color:#16a34a'>{t.get('tp3'):,.{dec}f}</b></div>"
        f"</div>"
        f"<div style='margin-top:8px;font-size:11px;color:#94a3b8'>"
        f"قیمت زنده: {lp_txt} · R:R {t.get('rr', 0):.1f} · امتیاز ورود {t.get('score', 0):+.2f} · {_interval} · {_age_label(t)}"
        f"</div>"
        + (f"<div style='margin-top:6px;font-size:11px;color:#cbd5e1'><b>مدرک:</b> {_evidence}</div>" if t.get("evidence") else "")
        + "</div>",
        unsafe_allow_html=True,
    )


def _unrealized_r(t: dict, live_price: float | None) -> float | None:
    """R تخمینی الان = خالصِ رآلیزه‌شده + باقیمانده‌ی پوزیشن با قیمت زنده − هزینه‌ی باقیمانده."""
    if not live_price:
        return None
    entry = float(t.get("entry"))
    risk0 = abs(entry - float(t.get("stop")))
    if risk0 <= 0:
        return None
    frac = 1.0 - (1 / 3 if t.get("tp1_done") else 0) - (1 / 3 if t.get("tp2_done") else 0)
    rem = max(0.0, frac)
    move = (float(live_price) - entry) * (1 if int(t.get("direction") or 0) > 0 else -1)
    cost_r = A.COST_RT_PCT * entry / risk0
    return float(t.get("realized_r") or 0.0) + rem * move / risk0 - rem * cost_r


# =============================================================================
# تب ۱ — اسکن
with tab_scan:
    st.caption(L(
        "هر شرکت‌کننده با وزن‌های خودش برگزیدگان را ارزیابی می‌کند؛ فقط جایی معامله باز می‌کند که: "
        "۱) امتیاز خودش از آستانه‌اش رد شده، ۲) بک‌تست خودش روی همان ارز سودده بوده (PF>1)، "
        "۳) ستاپ تازه هم‌جهت باشد (به تناسب سطح فیلتر ورود)، ۴) R:R ≥ ۱. کمیسیون هم با اجماع ۳/۴ ایجنت وارد می‌شود.",
        "Each participant evaluates every finalist with its own weights and only trades when: "
        "1) its own score passes its threshold, 2) its own backtest on that coin is profitable (PF>1), "
        "3) a fresh setup agrees (per the entry-filter level), 4) R:R ≥ 1. The Committee enters on 3/4 consensus."))

    c1, c2, c3, c4 = st.columns([1.2, 0.9, 1.3, 1.1])
    with c1:
        exchange = st.selectbox(L("صرافی", "Exchange"), EXCHANGES, index=0, key="arena_exch")
    with c2:
        interval = st.selectbox(L("تایم‌فریم (برای همه)", "Timeframe (for all)"),
                                ["15min", "1hour", "4hour", "1day"], index=1, key="arena_tf")
    with c3:
        appetite = st.select_slider(
            L("قدرت فیلتر ورود", "Entry filter strength"),
            options=list(A.APPETITES),
            format_func=lambda k: A.APPETITES[k]["fa"] if LANG != "en" else A.APPETITES[k]["en"],
            value=A.DEFAULT_APPETITE, key="arena_appetite")
    with c4:
        st.write("")
        go = st.button("🔎 " + L("اسکن کل بازار", "Scan whole market"), type="primary", width="stretch", key="arena_go")

    st.caption(L(
        "سخت‌گیر: فقط ستاپ تازه + لبه‌ی walk-forward اثبات‌شده (کم‌معامله ولی بی‌رحم) · "
        "متعادل: ستاپ تازه در ۶ کندل اخیر کافی است · شکارچی: فیلتر ستاپ خاموش — ایجنت‌ها با امتیاز و بک‌تست خودشان تصمیم می‌گیرند.",
        "Strict: fresh setup + proven walk-forward edge only (rare but ruthless) · "
        "Balanced: a fresh setup in the last 6 candles is enough · Hunter: setup filter off — agents decide with their own score & backtest."))

    # ---- بنر رژیم بازار (کش ۱۰ دقیقه‌ای — یک درخواست BTC ۴ساعته) ----
    _reg = A.market_regime(exchange)
    _rd = int(_reg.get("dir") or 0)
    if time.time() - st.session_state.get("_arena_reg", 0) >= 60:   # ثبت تغییر رژیم — حداکثر هر ۶۰ث
        st.session_state["_arena_reg"] = time.time()
        try:
            AL.push_regime_change(AL.get_alerts(), _reg)
        except Exception:  # noqa: BLE001
            pass
    if _rd > 0:
        _dist = (_reg["price"] / _reg["ma"] - 1.0) * 100.0
        st.info("🌊 " + L(
            f"رژیم بازار: **صعودی** — BTC/USDT روی ۴ساعته {_dist:+.1f}٪ بالای میانگین متحرک {A.REGIME_MA_N} کندل است → فقط لانگ باز می‌شود.",
            f"Market regime: **BULLISH** — BTC/USDT 4h is {_dist:+.1f}% above its {A.REGIME_MA_N}-candle MA → longs only."))
    elif _rd < 0:
        _dist = (1.0 - _reg["price"] / _reg["ma"]) * 100.0
        st.info("🌊 " + L(
            f"رژیم بازار: **نزولی** — BTC/USDT روی ۴ساعته {_dist:.1f}٪ زیر میانگین متحرک {A.REGIME_MA_N} کندل است → فقط شورت باز می‌شود.",
            f"Market regime: **BEARISH** — BTC/USDT 4h is {_dist:.1f}% below its {A.REGIME_MA_N}-candle MA → shorts only."))
    else:
        st.warning("🌊 " + L(
            "رژیم بازار نامشخص است (دیتای BTC در دسترس نبود) — فیلتر جهت موقتاً خاموش است و هر دو جهت باز می‌شود.",
            "Market regime unknown (BTC data unavailable) — direction filter temporarily OFF, both directions allowed."))

    # ---- بنر گیت لبه (فاز ۵) ----
    if _verdicts:
        _benched = [p["name"] for p in A.participants()
                    if p["kind"] == "agent" and not EG.allows(_verdicts, p["name"], _edge_mode)]
        _mlbl = (EG.MODE_FA if LANG != "en" else EG.MODE_EN).get(_edge_mode, _edge_mode)
        if _benched:
            st.info("⚖️ " + L(
                f"گیت لبه فعال ({_mlbl}) — بنچ: {'، '.join(_benched)} · رأی کمیسیون وزن‌دار است.",
                f"Edge gate active ({_mlbl}) — benched: {', '.join(_benched)} · committee votes are edge-weighted."))
        else:
            st.caption("⚖️ " + L(
                f"حکم‌های لبه فعال ({_mlbl}) — هیچ ایجنتی بنچ نیست؛ کمیسیون وزن‌دار است.",
                f"Edge verdicts active ({_mlbl}) — nobody benched; committee is edge-weighted."))
    elif _edge_state_any:
        st.caption("⚖️ " + L(
            "حکم‌های لبه کهنه‌اند (بیش از یک هفته) — در تب «اعتبار لبه» دوباره بازپخش بگیر تا گیت مسلح شود.",
            "Edge verdicts are stale (over a week) — rerun the replay in the 'Edge credibility' tab to re-arm the gate."))

    if exchange == "Lighter":
        st.info(L("Lighter پرپ است — نمادها بدون USDT هستند.", "Lighter is perp — symbols without USDT."))

    if go:
        t0 = time.time()
        try:
            with st.spinner(L(f"اول کل بازار {exchange} غربال می‌شود، بعد برگزیدگان تحلیل عمیق می‌شوند · {interval} … (۳۰–۹۰ ثانیه)",
                              f"Screening the whole {exchange} market first, then deep-analyzing the best ones · {interval} … (30–90s)")):
                scans, errors, meta = A.run_scan(exchange, interval, appetite=appetite,
                                                 verdicts=_verdicts, edge_mode=_edge_mode)
                opened, blocked = A.open_trades_from_scan(scans, exchange, interval, _store)
                for _t in opened:        # هشدار بازشدن — دائمی در Supabase/فایل
                    try:
                        AL.get_alerts().insert(AL.open_alert(_t))
                    except Exception:  # noqa: BLE001
                        pass
                if opened:
                    st.session_state.pop("_arena_alerts_ts", None)   # کش تب هشدارها تازه شود
            st.session_state["arena_scan"] = {
                "scans": scans, "errors": errors, "opened": opened, "blocked": blocked, "meta": meta,
                "exchange": exchange, "interval": interval,
                "took": time.time() - t0, "ts": datetime.now().strftime("%Y-%m-%d %H:%M")}
            st.session_state.pop("_arena_upd", None)
        except Exception as exc:  # noqa: BLE001
            st.error(L(f"اسکن اجرا نشد: {exc}", f"Scan failed: {exc}"))

    H = st.session_state.get("arena_scan")
    if not H:
        st.info(L("روی «🔎 اسکن کل بازار» بزن — ایجنت‌ها اول کل بازار را غربال می‌کنند تا بهترین‌ها را پیدا کنند، بعد همان‌ها را تحلیل و معامله می‌کنند.",
                  "Hit 'Scan whole market' — agents first screen the entire market for the strongest coins, then analyze and trade those."))
    else:
        scans, opened, meta = H["scans"], H["opened"], H.get("meta", {})
        ok_scans = [s for s in scans if not s.get("error")]
        n_agents_ok = sum(1 for s in ok_scans if any(a["ok"] for a in s.get("agents", {}).values()))
        n_com_ok = sum(1 for s in ok_scans if (s.get("committee") or {}).get("ok"))
        k1, k2, k3, k4 = st.columns(4)
        k1.metric(L("بازار غربال‌شده", "Market screened"), meta.get("total", len(scans)))
        k2.metric(L("برگزیدگان تحلیل عمیق", "Deep-analyzed finalists"), meta.get("finalists", len(scans)))
        k3.metric(L("معامله‌ی باز‌شده", "Trades opened"), len(opened))
        k4.metric(L("فرصت واجد شرایط", "Qualified setups"), n_agents_ok + n_com_ok)
        if meta.get("fallback"):
            st.warning(L("تیکر صرافی در دسترس نبود — اسکن با ۱۲ ارز اصلی انجام شد.",
                         "Exchange ticker unavailable — scanned the 12 major coins instead."))
        st.caption(L(f"{H['exchange']} · {H['interval']} · {A.APPETITES.get(meta.get('appetite', 'balanced'), {}).get('fa', '') if LANG != 'en' else A.APPETITES.get(meta.get('appetite', 'balanced'), {}).get('en', '')} · کل بازار: {meta.get('total', '—')} ارز → تحلیل عمیق: {meta.get('finalists', '—')} برگزیده در {H['took']:.0f} ثانیه · {H['ts']}"
                     + (f" · {len(H['errors'])} ارز خطا داد" if H["errors"] else ""),
                     f"{H['exchange']} · {H['interval']} · {A.APPETITES.get(meta.get('appetite', 'balanced'), {}).get('en', '')} · whole market: {meta.get('total', '—')} coins → deep analysis: {meta.get('finalists', '—')} finalists in {H['took']:.0f}s · {H['ts']}"
                     + (f" · {len(H['errors'])} errors" if H["errors"] else "")))
        _regm = meta.get("regime") or {}
        _rlbl = {1: L("صعودی — فقط لانگ", "bullish — longs only"),
                 -1: L("نزولی — فقط شورت", "bearish — shorts only")}.get(
            int(_regm.get("dir") or 0), L("نامشخص — فیلتر خاموش", "unknown — filter off"))
        _rb = int(meta.get("regime_blocked") or 0)
        st.caption("🌊 " + L(f"رژیم این اسکن: {_rlbl}", f"Regime for this scan: {_rlbl}")
                   + (" · " + L(f"{_rb} فرصت به‌خاطر خلاف‌رژیم‌بودن رد شد", f"{_rb} setups rejected for going against the regime") if _rb else ""))
        _eb = int(meta.get("edge_blocked") or 0)
        if _eb:
            st.caption("⚖️ " + L(f"{_eb} فرصت به‌خاطر بنچ‌بودن ایجنت (گیت لبه) رد شد",
                                 f"{_eb} setups rejected because the agent is benched (edge gate)"))

        if opened:
            st.subheader("🆕 " + L("معامله‌های تازه", "Fresh trades"))
            for t in opened:
                _trade_card(t, _live.get(t.get("symbol")), _unrealized_r(t, _live.get(t.get("symbol"))))
        else:
            _app = meta.get("appetite", "balanced")
            v_pass = sum(1 for s in ok_scans if s.get("v_ok"))
            if _app == "hunter":
                st.warning(L(
                    f"هیچ معامله‌ی تازه‌ای باز نشد — از {len(ok_scans)} برگزیده، هیچ شرکت‌کننده‌ای امتیاز کافی + بک‌تست سودده (PF>1) + R:R≥۱ هم‌جهت نداشت "
                    "(یا سهمیه‌اش پر بود). یعنی ایجنت‌ها الان لبه‌ی واضحی نمی‌بینند — سیگنال الکی بهتر از بی‌معامله‌ای نیست.",
                    f"No new trades — of {len(ok_scans)} finalists, no participant had enough score + profitable backtest (PF>1) + R:R≥1 "
                    "aligned (or its slots were full). The agents see no clear edge right now — better no trade than a random one."))
            else:
                st.warning(L(
                    f"هیچ معامله‌ی تازه‌ای باز نشد — از {len(ok_scans)} برگزیده، فقط {v_pass} تا ستاپ تازه داشتند و "
                    f"هیچ شرکت‌کننده‌ای (یا سهمیه‌ی خالی‌ای) هم‌جهتش نبود. یعنی الان لبه‌ی واضحی نیست — سیگنال الکی بهتر از بی‌معامله‌ای نیست.",
                    f"No new trades — of {len(ok_scans)} finalists only {v_pass} had a fresh setup and no participant "
                    f"(or free slot) matched direction. No clear edge right now — better no trade than a random one."))

        with st.expander(L("📋 ریز اسکن (همه‌ی برگزیدگان)", "📋 Scan details (all finalists)"), expanded=False):
            rows = []
            for s in sorted(ok_scans, key=lambda s: -abs(float((s.get("committee") or {}).get("score", 0)))):
                com = s.get("committee") or {}
                best = max(s.get("agents", {}).values(), key=lambda a: a["quality"], default=None)
                rows.append({
                    L("نماد", "Symbol"): s.get("symbol"),
                    L("کمیسیون", "Committee"): f"{com.get('score', 0):+.2f}",
                    L("موافق", "Agree"): f"{com.get('n_agree', 0)}/4",
                    L("⚖️ وزنی", "⚖️ Weighted"): f"{float(com.get('w_agree', com.get('n_agree', 0)) or 0):.1f}",
                    L("ستاپ", "Setup"): "✅" if s.get("v_ok") else "—",
                    L("چرا رد شد", "Why not"): (str(s.get("v_txt", ""))[:44] if not (com.get("ok") or any(a["ok"] for a in s.get("agents", {}).values())) else "—"),
                    L("بهترین ایجنت", "Best agent"): (f"{best['score']:+.2f}" if best else "—"),
                    L("واجد", "Qualified"): ("✅" if (com.get("ok") or any(a["ok"] for a in s.get("agents", {}).values())) else "—"),
                })
            st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
            if H["errors"]:
                st.caption(L("خطاها: ", "Errors: ") + " | ".join(H["errors"][:5]))

    with st.expander("⚖️ " + L("قواعد انصاف و امتیازدهی", "Fairness & scoring rules"), expanded=False):
        st.markdown(L(
            "**قدرت فیلتر ورود (سه سطح):** «سخت‌گیر» فقط ستاپ تازه + لبه‌ی walk-forward اثبات‌شده روی همان نماد — بی‌رحم ولی کم‌معامله. "
            "«متعادل» (پیش‌فرض) ستاپ تازه در ۶ کندل اخیر را کافی می‌داند و لبه‌ی اندازه‌گیری‌شده را لازم ندارد. "
            "«شکارچی» فیلتر ستاپ را کلاً خاموش می‌کند — ایجنت‌ها فقط با امتیاز و بک‌تست خودشان تصمیم می‌گیرند. "
            "بقیه‌ی دروازه‌ها (آستانه‌ی امتیاز، بک‌تست PF>1، R:R≥۱) در هر سه سطح فعال‌اند.\n\n"
            "**غربالگری دومرحله‌ای (بدون سقف تعداد):** هر اسکن اول کل بازار صرافی را در یک فراخوانی می‌گیرد — نه یک عدد دست‌ساز. "
            "ارزهای مرده (گردش < ۰٫۵ میلیون دلار) و استیبل‌کوین‌ها حذف می‌شوند؛ قدرت هر ارز = "
            "۵۵٪ مومنتوم ۲۴ ساعته (قدرمطلق — پامپ و دامپ هر دو، چون شورت هم داریم) + ۳۰٪ نقدینگی + ۱۵٪ دامنه‌ی نوسان. "
            "هر چه از صدک ۸۵ قدرت رد شود وارد تحلیل عمیق می‌شود — یعنی تعداد برگزیدگان بسته به حال بازار بالا و پایین می‌شود "
            "(فقط سقف فنی ۶۰ تایی برای محافظت از سهمیه‌ی API صرافی وجود دارد).\n\n"
            "**امتیاز هر معامله:** TP3 کامل = **+۵** · TP2 = **+۲** · TP1 و خروج با تریل = **+۱** · سر‌به‌سر = **۰** · "
            "استاپ (لیکویید ایجنت) = **−۱** · تایم‌اوت = **±۰٫۵** بر اساس علامت سود/زیان.\n\n"
            "**وین‌ریت** = بردها ÷ (بردها + باخت‌ها) — سر‌به‌سر‌ها شمرده نمی‌شوند.\n\n"
            "**قواعد انصاف:** همه با یک تایم‌فریم، کارمزد یکسان، ریسک ثابت **۱٪** در هر معامله، "
            "حداکثر **۳ پوزیشن** همزمان برای هر شرکت‌کننده و سقف **۱۵** پوزیشن برای کل میدان. "
            "هر ارز فقط یک پوزیشن باز برای هر شرکت‌کننده + cooldown پس از بستن معامله. "
            "در هر کندل اول استاپ چک می‌شود (محافظه‌کارانه)، بعد تارگت‌ها — یعنی نتایج به واقعیت بدبینانه‌تر نزدیک است.\n\n"
            "**خروج نردبانی:** TP1 → استاپ به ورود · TP2 → استاپ به TP1 · TP3 → بستن کامل. "
            "معامله‌ی سرگردان بعد از ۱۰۰ کندل با قیمت بازار بسته می‌شود.\n\n"
            "**فیلتر رژیم بازار:** پیش از هر اسکن، جهت BTC/USDT روی تایم‌فریم ۴ساعته نسبت به میانگین متحرک "
            f"{A.REGIME_MA_N} کندل سنجیده می‌شود — بالای میانگین فقط لانگ، زیرش فقط شورت. "
            "ستاپِ خلاف رژیم حتی اگر همه‌ی دروازه‌های دیگر را رد کند باز نمی‌شود و تعدادش در خلاصه‌ی اسکن شمرده می‌شود. "
            "اگر دیتای BTC در دسترس نباشد فیلتر موقتاً خاموش است.\n\n"
            "**بازپخش تاریخی (تب 🧪):** همان دروازه‌ها روی کندل‌های تاریخی پخش می‌شود تا شواهد سوددهی بدون انتظار هفته‌ها به‌دست بیاید: "
            "در هر کندلِ گذشته، هر شرکت‌کننده با همان آستانه‌ها و همان بک‌تست ۳۰۰تایی سنجیده می‌شود، رژیمِ همان لحظه‌ی BTC (علّی) اعمال می‌شود، "
            "سهمیه‌ها و cooldown رعایت می‌شود و هر معامله با همان موتور خروج نردبانی (استاپ اول + کارمزد و لغزش واقعی) تا بسته‌شدن پیش می‌رود. "
            "جهانِ بازپخش نمادهای انتخابی شماست (غربالگریِ لحظه‌ایِ گذشته بازسازی‌شدنی نیست) و دروازه‌ی ستاپ سه‌سطحی در بازپخش اعمال نمی‌شود — "
            "یعنی رفتار معادل سطح «شکارچی». نتیجه‌ی بازپخش جای معاملات زنده را نمی‌گیرد؛ فقط شاهد آماری است.\n\n"
            "**موتور لبه (تب ⚖️):** دروازه‌های عادی فقط می‌پرسند «این ایجنت روی این ارز الان بک‌تست سودده دارد؟» — هیچ‌کدام نمی‌پرسند "
            "«خودِ این ایجنت تاریحاً سودده بوده؟». تب اعتبار لبه با بازپخش چندپنجره‌ای (تفکیک معامله‌ها بر اساس کندل ورود) حکم ✅/⚠️/❌ می‌دهد و در اسکن زنده اعمال می‌شود: "
            "ایجنت بنچ‌شده معامله باز نمی‌کند و رأی کمیسیون وزن می‌گیرد (سودده ۱٫۲ · خنثی ۱٫۰ · زیان‌ده ۰٫۸ — بدون دیتا همه ۱). "
            "گیت فقط با حکم تازه (زیر یک هفته) مسلح می‌شود و جهانش نمادهای انتخابی توست — شاهد آماری، نه تضمین.\n\n"
            "**آمار کلی میدان:** معیارهای واقعی سوددهی — انتظاری (میانگین R خالص هر معامله)، PF، پی‌آف و MaxDD — "
            "از معاملات بسته‌شده با کارمزد و لغزش واقعی حساب می‌شوند. قانون تصمیم: تا ۳۰ معامله هیچ عددی اعتبار آماری ندارد، "
            "بین ۳۰ تا ۱۰۰ فقط جهت‌گیری است، و فقط با ۱۰۰+ معامله و انتظاری مثبت می‌شود به سیستم اعتماد کرد.\n\n"
            "**هشدارها و اخبار:** باز و بسته‌شدن معامله‌ها و تغییر رژیم بازار در تب «🔔 هشدارها» دائمی ثبت می‌شود؛ "
            "تیترهای تازه‌ی خبری با تگ نماد در تب «📰 اخبار بازار» می‌آید — خبری که نمادِ پوزیشن باز تو را داشته باشد ستاره ⭐ می‌گیرد.",
            "**Entry filter strength (three levels):** 'Strict' requires a fresh setup + proven walk-forward edge on that exact coin — ruthless but rare. "
            "'Balanced' (default) accepts any setup formed in the last 6 candles, without requiring a measured edge. "
            "'Hunter' turns the setup filter off entirely — agents decide purely with their own score and backtest. "
            "All other gates (score threshold, backtest PF>1, R:R≥1) stay active on every level.\n\n"
            "**Two-stage screening (no fixed count):** every scan first pulls the WHOLE exchange market in a single call — no hand-picked number. "
            "Dead coins (< $0.5M daily turnover) and stablecoins are removed; strength = "
            "55% 24h momentum (absolute — pumps and dumps both count, shorts exist) + 30% liquidity + 15% daily range. "
            "Everything above the 85th percentile of strength enters deep analysis — the number of finalists floats with market conditions "
            "(only a technical 60-cap exists to protect the exchange API quota).\n\n"
            "**Trade score:** full TP3 = **+5** · TP2 = **+2** · TP1 then trail-out = **+1** · breakeven = **0** · "
            "stop (agent liquidation) = **−1** · timeout = **±0.5** by PnL sign.\n\n"
            "**Winrate** = wins ÷ (wins + losses) — breakevens excluded.\n\n"
            "**Fairness:** one timeframe, identical fees, fixed **1%** risk per trade, max **3 concurrent** "
            "positions per participant, **15** for the whole arena. One open position per symbol per participant + "
            "cooldown after closing. Stops are checked first each candle (conservative) — results skew realistic/pessimistic.\n\n"
            "**Ladder exit:** TP1 → stop to entry · TP2 → stop to TP1 · TP3 → full close. "
            "Stalled trades close at market after 100 candles.\n\n"
            "**Market regime filter:** before every scan, BTC/USDT on the 4-hour timeframe is measured against its "
            f"{A.REGIME_MA_N}-candle moving average — above it only longs, below it only shorts. "
            "A setup against the regime stays closed even if it passes every other gate, and the rejected count is shown in the scan summary. "
            "If BTC data is unavailable the filter is temporarily off.\n\n"
            "**Historical replay (🧪 tab):** the same gates replayed over past candles so profitability evidence arrives without waiting weeks: "
            "at every past candle each participant is measured with the same thresholds and the same 300-candle backtest, "
            "the causal BTC regime of that moment applies, quotas and cooldown are respected, and every trade is walked forward with the "
            "same ladder-exit engine (stop-first, real fees & slippage). The replay universe is your selected symbols (the live moment-in-time "
            "screening of the past cannot be reconstructed) and the three-level setup gate is not applied — equivalent to 'Hunter' behavior. "
            "Replay results never replace live trades; they are statistical evidence only.\n\n"
            "**Edge engine (⚖️ tab):** the regular gates only ask 'does this agent have a profitable backtest on this coin right now?' — "
            "none asks 'has the agent itself been profitable historically?'. The edge tab runs a multi-window replay (trades split by entry candle), "
            "issues a ✅/⚠️/❌ verdict and enforces it in the live scan: benched agents cannot open trades and committee votes become edge-weighted "
            "(profitable 1.2 · neutral 1.0 · losing 0.8 — all 1.0 without data). Only fresh verdicts (under a week) arm the gate; "
            "the universe is your selected symbols — statistical evidence, not a guarantee.\n\n"
            "**Arena-wide stats:** the real profitability metrics — expectancy (average net R per trade), PF, payoff and MaxDD — "
            "are computed from closed trades with real fees and slippage. Decision rule: below 30 trades nothing means anything; "
            "30–100 is directional only; only 100+ trades with positive expectancy earn trust.\n\n"
            "**Alerts & news:** trade opens/closes and regime flips are logged permanently in the '🔔 Alerts' tab; "
            "fresh headlines with symbol tags live in the '📰 Market news' tab — a headline mentioning a symbol you hold open gets a ⭐."))

# =============================================================================
# تب ۲ — پوزیشن‌های باز
with tab_pos:
    if not _open_trades:
        st.info(L("هنوز پوزیشن بازی نداریم — از تب «اسکن» شروع کن.", "No open positions yet — start from the Scan tab."))
    else:
        rows = []
        for t in sorted(_open_trades, key=lambda t: t.get("agent", "")):
            lp = _live.get(t.get("symbol"))
            ur = _unrealized_r(t, lp)
            dec = int(t.get("dec", 4))
            rows.append({
                L("ایجنت", "Agent"): t.get("agent"), L("نماد", "Symbol"): t.get("symbol"),
                L("جهت", "Side"): DIR_FA.get(int(t.get("direction") or 0), "—"),
                L("ورود", "Entry"): f"{t.get('entry'):,.{dec}f}",
                L("SL فعلی", "Cur SL"): f"{float(t.get('cur_stop') or t.get('stop')):,.{dec}f}",
                "TP1": "✅" if t.get("tp1_done") else "—", "TP2": "✅" if t.get("tp2_done") else "—",
                L("قیمت زنده", "Live"): (f"{lp:,.{dec}f}" if lp else "—"),
                L("R باز", "Open R"): ("—" if ur is None else f"{ur:+.2f}"),
            })
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
        st.caption(L("معامله‌ها هر بار که صفحه باز شود با کندل‌های تازه پیش برده می‌شوند (حداکثر هر ۶۰ ثانیه).",
                     "Trades are advanced with fresh candles whenever this page loads (at most once per 60s)."))
        for t in sorted(_open_trades, key=lambda t: t.get("agent", "")):
            _trade_card(t, _live.get(t.get("symbol")), _unrealized_r(t, _live.get(t.get("symbol"))))

# =============================================================================
# تب ۳ — هشدارها
with tab_alerts:
    st.subheader("🔔 " + L("هشدارهای میدان", "Arena alerts"))
    st.caption(L(
        "رویدادهای مهم میدان — باز و بسته‌شدن معامله‌ها و تغییر رژیم بازار — دائمی ثبت می‌شوند؛ تازه‌ترین‌ها بالای فهرست. هشدارِ تکراری ساخته نمی‌شود (هر معامله حداکثر یک بازشدن و یک بسته‌شدن دارد).",
        "Key arena events — trades opening/closing and regime flips — are stored permanently; newest first. No duplicate alerts (each trade yields at most one open and one close alert)."))
    if time.time() - st.session_state.get("_arena_alerts_ts", 0) >= 15 or "_arena_alerts_val" not in st.session_state:
        st.session_state["_arena_alerts_ts"] = time.time()
        try:
            st.session_state["_arena_alerts_val"] = AL.get_alerts().load_recent(80)
        except Exception:  # noqa: BLE001
            st.session_state["_arena_alerts_val"] = st.session_state.get("_arena_alerts_val") or []
    _alerts = st.session_state.get("_arena_alerts_val") or []
    if not _alerts:
        st.info(L("هنوز هشداری ثبت نشده — بعد از اولین اسکن یا اولین معامله‌ی بسته‌شده اینجا پر می‌شود.",
                  "No alerts yet — the list fills after the first scan or first closed trade."))
    else:
        _c1, _c2, _c3, _c4 = st.columns(4)
        _c1.metric(L("هشدارهای اخیر", "Recent alerts"), len(_alerts))
        _c2.metric(L("بازشدن", "Opens"), sum(1 for a in _alerts if a.get("kind") == "open"))
        _c3.metric(L("بسته‌شدن", "Closes"), sum(1 for a in _alerts if a.get("kind") == "close"))
        _c4.metric(L("تغییر رژیم", "Regime flips"), sum(1 for a in _alerts if a.get("kind") == "regime"))
        _arows = []
        _DIR_EN = {1: "LONG 🟢", -1: "SHORT 🔴", 0: "— ⚪"}
        for a in _alerts:
            _kind = str(a.get("kind"))
            _when = str(a.get("created_at") or "")[:16].replace("T", " ")
            if _kind == "open":
                _ev = "🟢 " + L("باز شد", "OPENED")
                _det = (L("ورود", "Entry") + f" {float(a.get('entry') or 0):,.6g} · "
                        + L("استاپ", "Stop") + f" {float(a.get('stop') or 0):,.6g}"
                        + (f" · {a.get('interval')}" if a.get("interval") else ""))
            elif _kind == "close":
                _ev = "🏁 " + L("بسته شد", "CLOSED") + " — " + _res_badge(str(a.get("result") or ""))
                _det = f"{float(a.get('r') or 0):+.2f}R · {float(a.get('points') or 0):+.1f} " + L("امتیاز", "pts")
            else:
                _d = int(a.get("direction") or 0)
                _ev = "🌊 " + (L("رژیم صعودی شد", "Turned bullish") if _d > 0 else L("رژیم نزولی شد", "Turned bearish"))
                _ma, _pr = float(a.get("ma") or 0), float(a.get("price") or 0)
                _det = (f"BTC {_pr:,.0f} · MA{A.REGIME_MA_N}: {_ma:,.0f} · {_pr / _ma * 100.0 - 100.0:+.1f}%"
                        if _ma > 0 and _pr > 0 else "BTC/USDT 4h")
            _arows.append({
                L("زمان", "Time"): _when, L("رویداد", "Event"): _ev,
                L("ایجنت", "Agent"): (a.get("agent") or "—"),
                L("نماد", "Symbol"): a.get("symbol"),
                L("جهت", "Side"): (DIR_FA if LANG != "en" else _DIR_EN).get(int(a.get("direction") or 0), "—"),
                L("جزئیات", "Details"): _det,
            })
        st.dataframe(pd.DataFrame(_arows), width="stretch", hide_index=True)
    _ab = AL.get_alerts().backend
    st.caption(("🟢 " if _ab == "supabase" else "🟡 ")
               + L(f"بک‌اند هشدارها: {_ab} · جدول: arena_alerts",
                   f"Alerts backend: {_ab} · table: arena_alerts"))

# =============================================================================
# تب ۴ — اخبار بازار
with tab_news:
    st.subheader("📰 " + L("اخبار بازار", "Market news"))
    st.caption(L(
        "تیترهای تازه از Decrypt، Cointelegraph و NewsBTC — به انگلیسی می‌مانند چون ترجمه‌ی ماشینی اخبار مالی خطا می‌سازد. "
        "زمان‌ها UTC · کش ۱۰ دقیقه‌ای · ⭐ = تیتر به نمادی می‌خورد که پوزیشن باز داری.",
        "Fresh headlines from Decrypt, Cointelegraph and NewsBTC. Times in UTC · 10-min cache · ⭐ = headline mentions a symbol you hold open."))
    _sym_open = {str(t.get("symbol") or "").split("/")[0].upper() for t in _open_trades}
    try:
        _news = NW.fetch_news()
    except Exception:  # noqa: BLE001
        _news = {"items": [], "stale": True}
    if _news.get("stale"):
        st.warning(L("هیچ فید خبری در دسترس نبود — بعداً دوباره چک کن.",
                     "No news feed was reachable — try again later."))
    else:
        for _it in (_news.get("items") or [])[:18]:
            _syms = _it.get("symbols") or []
            _hit = " ⭐" if any(s in _sym_open for s in _syms) else ""
            _when = (str(_it.get("ts") or "")[:16].replace("T", " ")) or "—"
            _chips = ("  \n" + " ".join(f"`{s}`" for s in _syms)) if _syms else ""
            st.markdown(f"{_when} UTC · **{_it.get('source')}**{_hit}  \n"
                        f"[{_esc(str(_it.get('title')))}]({_esc(str(_it.get('link')))})" + _chips)

# =============================================================================
# تب ۵ — لیدربورد و تاریخچه
with tab_board:
    # ---- آمار کلی میدان: آیا این سیستم واقعاً سوده است؟ ----
    _summ = A.arena_summary(_closed_trades)
    st.subheader("📊 " + L("آمار کلی میدان", "Arena-wide stats"))
    _b1, _b2, _b3, _b4, _b5 = st.columns(5)
    _b1.metric(L("معاملات بسته", "Closed trades"), _summ["n"])
    _b2.metric(L("انتظاری هر معامله", "Expectancy / trade"), f"{_summ['expectancy']:+.2f}R")
    _b3.metric(L("وین‌ریت", "Winrate"), f"{_summ['winrate']:.0f}%")
    _b4.metric("PF", f"{_summ['pf']:.2f}")
    _b5.metric(L("بیشترین افت", "Max drawdown"), f"{_summ['maxdd']:.1f}%")
    _rel = _summ["reliability"]
    if _rel == "low":
        st.error(L(
            f"⚠️ نمونه کوچک است ({_summ['n']} معامله) — تا ۳۰ معامله این اعداد هیچ اعتبار آماری ندارند و تا ۱۰۰ معامله فقط جهت‌گیری‌اند. "
            "تصمیم پول واقعی فقط با ۱۰۰+ معامله و انتظاری مثبت.",
            f"⚠️ Small sample ({_summ['n']} trades) — below 30 these numbers carry no statistical weight; 30–100 is directional only. "
            "Real-money decisions need 100+ trades with positive expectancy."))
    elif _rel == "mid":
        st.warning(L(
            f"🟠 {_summ['n']} معامله — قابل مشاهده ولی نه قطعی؛ تا رسیدن به ۱۰۰ معامله فقط جهت‌گیری در نظر بگیر.",
            f"🟠 {_summ['n']} trades — observable but not conclusive; treat as directional until 100 trades."))
    else:
        st.success(L(
            f"🟢 {_summ['n']} معامله — نمونه‌ی آماری کافی است؛ حالا می‌شود به انتظاری و PF اعتماد بیشتری کرد.",
            f"🟢 {_summ['n']} trades — statistically usable sample; expectancy and PF can now be trusted more."))
    st.caption(L(
        "انتظاری = میانگین R خالص هر معامله (بعد از کارمزد و لغزش) · PF = مجموع بردها ÷ مجموع باخت‌ها · "
        "MaxDD = بیشترین افت ایکوییتی ترکیبی با ریسک ۱٪ (انگار یک حساب همه‌ی میدان را می‌گرفت).",
        "Expectancy = average net R per trade (after fees & slippage) · PF = gross wins ÷ gross losses · "
        "MaxDD = deepest drop of the combined 1%-risk equity (as if one account took every arena trade)."))

    board = A.leaderboard(_closed_trades, _open_trades)
    MEDALS = ["🥇", "🥈", "🥉"]
    rows = []
    for i, r in enumerate(board):
        streak = r["streak"]
        streak_txt = f"🔥 {streak}" if streak > 1 else f"🧊 {-streak}" if streak < -1 else "—"
        rows.append({
            L("رتبه", "Rank"): MEDALS[i] if i < 3 and r["trades"] else f"{i + 1}",
            L("شرکت‌کننده", "Participant"): r["agent"],
            L("⚖️ حکم", "⚖️ Edge"): (EG.VERDICT_FA if LANG != "en" else EG.VERDICT_EN).get((_verdicts or {}).get(r["agent"]), "—"),
            L("ایکوییتی $", "Equity $"): f"{r['equity']:,.0f}",
            L("وین‌ریت", "Winrate"): f"{r['winrate']:.0f}%" if r["trades"] else "—",
            L("امتیاز", "Points"): f"{r['points']:+.1f}" if r["trades"] else "—",
            "R کل": f"{r['total_r']:+.2f}" if r["trades"] else "—",
            "PF": f"{r['pf']:.2f}" if r["trades"] else "—",
            L("انتظاری R", "Exp. R"): f"{r['avg_r']:+.2f}" if r["trades"] else "—",
            L("پی‌آف", "Payoff"): f"{r['payoff']:.2f}" if r["trades"] else "—",
            "MaxDD": f"{r['maxdd']:.1f}%" if r["trades"] else "—",
            L("برد/باخت", "W/L"): f"{r['wins']}/{r['losses']}" if r["trades"] else "—",
            L("زنجیره", "Streak"): streak_txt if r["trades"] else "—",
            L("باز", "Open"): r["open"],
            L("کل", "Total"): r["trades"],
            L("آمار", "Sample"): L("⚠️ کم", "⚠️ small") if 0 < r["trades"] < 10 else ("✅" if r["trades"] >= 10 else "—"),
        })
    st.subheader("🏆 " + L("جدول قهرمانی", "Championship table"))
    st.caption(L("رتبه‌بندی بر اساس امتیاز؛ ایکوییتی از ۱۰٬۰۰۰$ کاغذی با ریسک ۱٪ در هر معامله مرکب می‌شود. "
                 "وین‌ریت با کمتر از ۱۰ معامله معنای آماری مطمئنی ندارد.",
                 "Ranked by points; equity compounds from a paper $10,000 at 1% risk per trade. "
                 "Winrates under 10 trades are not statistically meaningful."))
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    traded = [r for r in board if r["trades"]]
    if traded:
        import plotly.graph_objects as go  # noqa: E402
        fig = go.Figure()
        for r in traded:
            eq = A.equity_curve(r["_history"])
            label = f"{r['agent']} ({r['equity']:,.0f}$)"
            fig.add_trace(go.Scatter(y=eq, mode="lines", name=label, line=dict(color=r["color"], width=2)))
        fig.update_layout(template="plotly_dark", height=380,
                          title=L("ایکوییتی هر شرکت‌کننده (معاملات بسته‌شده)", "Equity per participant (closed trades)"),
                          margin=dict(l=20, r=20, t=50, b=20), legend=dict(orientation="h"))
        st.plotly_chart(fig, width="stretch")

    st.subheader("📜 " + L("تاریخچه‌ی معاملات", "Trade history"))
    if not _closed_trades:
        st.info(L("هنوز معامله‌ای بسته نشده.", "No closed trades yet."))
    else:
        hrows = []
        for t in sorted(_closed_trades, key=lambda t: str(t.get("closed_at")), reverse=True):
            dec = int(t.get("dec", 4))
            ca = str(t.get("closed_at", ""))[:16].replace("T", " ")
            hrows.append({
                L("زمان بستن", "Closed at"): ca,
                L("ایجنت", "Agent"): t.get("agent"), L("نماد", "Symbol"): t.get("symbol"),
                L("جهت", "Side"): DIR_FA.get(int(t.get("direction") or 0), "—"),
                L("ورود", "Entry"): f"{t.get('entry'):,.{dec}f}",
                L("خروج", "Exit"): f"{float(t.get('closed_price') or 0):,.{dec}f}",
                L("نتیجه", "Result"): _res_badge(str(t.get("result"))),
                "R": f"{float(t.get('realized_r') or 0):+.2f}",
                L("امتیاز", "Points"): f"{float(t.get('points') or 0):+.1f}",
                L("دلیل", "Reason"): A.EXIT_FA.get(t.get("exit_reason"), t.get("exit_reason") or "—") if LANG != "en" else str(t.get("exit_reason") or "—"),
            })
        hdf = pd.DataFrame(hrows)
        st.dataframe(hdf, width="stretch", hide_index=True)
        st.download_button("💾 " + L("دانلود تاریخچه (CSV)", "Download history (CSV)"),
                           data=hdf.to_csv(index=False).encode("utf-8"),
                           file_name="arena_history.csv", mime="text/csv", key="arena_csv")

    _st_icon = "🟢" if _hc.get("reason") == "ok" else "🟡"
    st.caption(_st_icon + " " + L(f"بک‌اند: {_hc.get('backend')} · جدول: arena_trades",
                                  f"Backend: {_hc.get('backend')} · table: arena_trades"))

# =============================================================================
# تب ۶ — بازپخش تاریخی
with tab_replay:
    st.subheader("🧪 " + L("بازپخش تاریخی میدان", "Historical arena replay"))
    st.caption(L(
        "همان موتور و همان دروازه‌های اسکن زنده — امتیاز ایجنت، بک‌تست PF>1 روی پنجره‌ی ۳۰۰تایی، R:R≥۱، فیلتر رژیم BTC، "
        "سهمیه‌ی ۳ پوزیشن هر شرکت‌کننده، سقف ۱۵ کل میدان، cooldown و کارمزد+لغزش واقعی — روی کندل‌های تاریخی پخش می‌شود "
        "تا بدون انتظار هفته‌ها ببینی این ترکیب در گذشته سودده بوده یا نه. هیچ چیزی در جدول معاملات ذخیره نمی‌شود.",
        "The exact live-scan engine and gates — agent score, 300-candle PF>1 backtest, R:R≥1, BTC regime filter, "
        "3-position quota per participant, arena cap of 15, cooldown and real fees+slippage — replayed over historical candles "
        "so you can see whether this setup was profitable in the past without waiting weeks. Nothing is saved to the trades table."))

    _rc1, _rc2, _rc3 = st.columns([1.1, 2.3, 1.1])
    with _rc1:
        rep_candles = st.selectbox(L("طول تاریخچه (کندل)", "History length (candles)"),
                                   RP.CANDLE_CHOICES, index=RP.CANDLE_CHOICES.index(RP.DEFAULT_CANDLES),
                                   key="arena_rep_candles")
    with _rc2:
        rep_syms = st.multiselect(L("نمادهای بازپخش (حداکثر ۲۰)", "Replay symbols (max 20)"),
                                  A.POOL_FALLBACK, default=A.POOL_FALLBACK,
                                  max_selections=RP.MAX_SYMBOLS, key="arena_rep_syms")
    with _rc3:
        st.write("")
        rep_go = st.button("🧪 " + L("اجرای بازپخش", "Run replay"), type="primary",
                           width="stretch", key="arena_rep_go")

    if rep_go:
        if not rep_syms:
            st.warning(L("حداقل یک نماد انتخاب کن.", "Pick at least one symbol."))
        else:
            try:
                with st.spinner(L(
                    f"{len(rep_syms)} نماد + BTC گرفته می‌شود و بعد {len(rep_syms)}×{rep_candles} کندل کندل‌به‌کندل بازپخش می‌شود … (۱–۳ دقیقه)",
                    f"Fetching {len(rep_syms)} symbols + BTC, then replaying {len(rep_syms)}×{rep_candles} candles one by one … (1–3 min)")):
                    _dfs, _btc_d, _ferr = RP.fetch_dfs(exchange, rep_syms, interval, int(rep_candles))
                    _rres = RP.replay_from_dfs(_dfs, _btc_d, exchange, interval)
                    _rres["meta"]["fetch_errors"] = _ferr
                st.session_state["arena_replay"] = _rres
            except Exception as exc:  # noqa: BLE001
                st.error(L(f"بازپخش اجرا نشد: {exc}", f"Replay failed: {exc}"))

    _R = st.session_state.get("arena_replay")
    if not _R:
        st.info(L(
            "روی «🧪 اجرای بازپخش» بزن. پیش‌فرض ۱۲ ارز بزرگ با ۷۰۰ کندل چهارساعته (~۱۱۶ روز) است — "
            "می‌توانی نمادها را عوض کنی یا تاریخچه را تا ۱۰۰۰ کندل بلند کنی.",
            "Hit 'Run replay'. Default is 12 major coins × 700 4-hour candles (~116 days) — "
            "you can change the symbols or extend the history up to 1,000 candles."))
    else:
        _rs, _rm = _R["summary"], _R["meta"]
        _q1, _q2, _q3, _q4, _q5, _q6 = st.columns(6)
        _q1.metric(L("معاملات بسته", "Closed trades"), _rs["n"])
        _q2.metric(L("انتظاری هر معامله", "Expectancy / trade"), f"{_rs['expectancy']:+.2f}R")
        _q3.metric("PF", f"{_rs['pf']:.2f}")
        _q4.metric(L("وین‌ریت", "Winrate"), f"{_rs['winrate']:.0f}%")
        _q5.metric(L("بیشترین افت", "Max drawdown"), f"{_rs['maxdd']:.1f}%")
        _q6.metric(L("بازه‌ی زمانی", "Time span"), f"{_rm.get('span_days', 0):.0f} " + L("روز", "days"))
        _rel = _rs["reliability"]
        if _rel == "low":
            st.error(L(
                f"⚠️ بازپخش فقط {_rs['n']} معامله ساخت — تا ۳۰ معامله هیچ عددی اعتبار آماری ندارد. "
                "نمادهای بیشتری اضافه کن یا تاریخچه را بلندتر کن.",
                f"⚠️ Replay produced only {_rs['n']} trades — below 30 nothing is statistically meaningful. "
                "Add more symbols or extend the history."))
        elif _rel == "mid":
            st.warning(L(
                f"🟠 {_rs['n']} معامله در بازپخش — جهت‌گیری خوب است ولی برای قطعیت به ۱۰۰+ و تأیید زنده نیاز داری.",
                f"🟠 {_rs['n']} replayed trades — good for direction, but 100+ plus live confirmation needed for certainty."))
        else:
            st.success(L(
                f"🟢 {_rs['n']} معامله در بازپخش — نمونه‌ی معناداری است؛ حالا با انتظاری زنده مقایسه کن.",
                f"🟢 {_rs['n']} replayed trades — a meaningful sample; now compare against live expectancy."))
        st.caption(L(
            f"{_rm['exchange']} · {_rm['interval']} · {len(_rm['symbols'])} نماد · از {_rm.get('from', '—')[:16].replace('T', ' ')} تا {_rm.get('to', '—')[:16].replace('T', ' ')} "
            f"· {len(_R['opens'])} پوزیشن هنوز باز مانده · {_rm.get('took', 0):.0f} ثانیه",
            f"{_rm['exchange']} · {_rm['interval']} · {len(_rm['symbols'])} symbols · from {_rm.get('from', '—')[:16].replace('T', ' ')} to {_rm.get('to', '—')[:16].replace('T', ' ')} "
            f"· {len(_R['opens'])} still open at history end · {_rm.get('took', 0):.0f}s"))
        _rgc = int(_rm.get("reg_blocked") or 0)
        _bf, _bc, _bb = int(_rm.get("blocked_full") or 0), int(_rm.get("blocked_cool") or 0), int(_rm.get("blocked_busy") or 0)
        _gparts = []
        if _rgc:
            _gparts.append(L(f"{_rgc} ایجنت-کندل خلاف رژیم", f"{_rgc} agent-candles against regime"))
        if _bf:
            _gparts.append(L(f"{_bf} سهمیه پر", f"{_bf} quota-full"))
        if _bb:
            _gparts.append(L(f"{_bb} نمادِ تکراری", f"{_bb} duplicate symbol"))
        if _bc:
            _gparts.append(L(f"{_bc} cooldown", f"{_bc} cooldown"))
        if _gparts:
            st.caption("🚧 " + L("رخدادهای ردشده: ", "Rejected events: ") + " · ".join(_gparts))
        if _rm.get("fetch_errors") or _rm.get("errors"):
            st.caption("⚠️ " + L("خطاها: ", "Errors: ") + " | ".join((_rm.get("fetch_errors") or []) + (_rm.get("errors") or []))[:400])

        # ---- جدول شرکت‌کننده‌های بازپخش ----
        st.subheader("🏆 " + L("نتایج هر شرکت‌کننده در گذشته", "Per-participant results in the past"))
        _rrows = []
        for i, r in enumerate(_R["board"]):
            _rrows.append({
                L("رتبه", "Rank"): f"{i + 1}",
                L("شرکت‌کننده", "Participant"): r["agent"],
                L("ایکوییتی $", "Equity $"): f"{r['equity']:,.0f}",
                L("معاملات", "Trades"): r["trades"],
                L("وین‌ریت", "Winrate"): f"{r['winrate']:.0f}%" if r["trades"] else "—",
                "R کل": f"{r['total_r']:+.2f}" if r["trades"] else "—",
                L("انتظاری R", "Exp. R"): f"{r['avg_r']:+.2f}" if r["trades"] else "—",
                "PF": f"{r['pf']:.2f}" if r["trades"] else "—",
                L("پی‌آف", "Payoff"): f"{r['payoff']:.2f}" if r["trades"] else "—",
                "MaxDD": f"{r['maxdd']:.1f}%" if r["trades"] else "—",
                L("برد/باخت", "W/L"): f"{r['wins']}/{r['losses']}" if r["trades"] else "—",
            })
        st.dataframe(pd.DataFrame(_rrows), width="stretch", hide_index=True)

        # ---- نمودار ایکوییتی: حساب ترکیبی + هر شرکت‌کننده ----
        import plotly.graph_objects as go  # noqa: E402
        _rfig = go.Figure()
        _rfig.add_trace(go.Scatter(y=_R["curve"], mode="lines", name=L("کل میدان", "Whole arena"),
                                   line=dict(color="#e2e8f0", width=3)))
        for r in _R["board"]:
            if r["trades"]:
                eq = A.equity_curve(r["_history"])
                _rfig.add_trace(go.Scatter(y=eq, mode="lines", name=f"{r['agent']} ({r['equity']:,.0f}$)",
                                           line=dict(color=r["color"], width=2)))
        _rfig.add_hline(y=A.START_EQUITY, line_dash="dot", line_color="#64748b")
        _rfig.update_layout(template="plotly_dark", height=380,
                            title=L("ایکوییتی بازپخش (۱۰٬۰۰۰$ کاغذی · ریسک ۱٪ · کارمزد و لغزش واقعی)",
                                    "Replay equity (paper $10,000 · 1% risk · real fees & slippage)"),
                            margin=dict(l=20, r=20, t=50, b=20), legend=dict(orientation="h"))
        st.plotly_chart(_rfig, width="stretch")

        # ---- جدول نمادها ----
        if _R["per_symbol"]:
            st.subheader("🪙 " + L("به تفکیک نماد", "Per symbol"))
            st.dataframe(pd.DataFrame(_R["per_symbol"]), width="stretch", hide_index=True)

        # ---- تاریخچه‌ی بازپخش ----
        with st.expander(L("📜 معاملات بسته‌شده‌ی بازپخش", "📜 Replayed closed trades"), expanded=False):
            if not _R["closed"]:
                st.info(L("هیچ معامله‌ای بسته نشده.", "No trades closed."))
            else:
                _hrows = []
                for t in sorted(_R["closed"], key=lambda t: str(t.get("closed_at")), reverse=True)[:80]:
                    dec = int(t.get("dec", 4))
                    _hrows.append({
                        L("بسته‌شده", "Closed"): str(t.get("closed_at", ""))[:16].replace("T", " "),
                        L("شرکت‌کننده", "Participant"): t.get("agent"), L("نماد", "Symbol"): t.get("symbol"),
                        L("جهت", "Side"): DIR_FA.get(int(t.get("direction") or 0), "—"),
                        L("ورود", "Entry"): f"{t.get('entry'):,.{dec}f}",
                        L("خروج", "Exit"): f"{float(t.get('closed_price') or 0):,.{dec}f}",
                        L("نتیجه", "Result"): _res_badge(str(t.get("result"))),
                        "R": f"{float(t.get('realized_r') or 0):+.2f}",
                        L("دلیل", "Reason"): A.EXIT_FA.get(t.get("exit_reason"), t.get("exit_reason") or "—") if LANG != "en" else str(t.get("exit_reason") or "—"),
                    })
                st.dataframe(pd.DataFrame(_hrows), width="stretch", hide_index=True)

        st.caption(L(
            "محدودیت‌های صداقت‌آمیز: جهانِ بازپخش نمادهای انتخابی توست (غربالگریِ لحظه‌ایِ گذشته بازسازی‌شدنی نیست) · "
            "دروازه‌ی ستاپ سه‌سطحی اعمال نمی‌شود (معادل سطح شکارچی) · اندیکاتورها روی کل تاریخچه گرم می‌شوند (کمی بهتر از فریم زنده) · "
            "معاملات هنوز‌بازِ انتهای دوره در آمار نیستند. بازپخش شاهد آماری است، نه جای معاملات زنده.",
            "Honest limits: the replay universe is your selected symbols (the past's live screening can't be reconstructed) · "
            "the three-level setup gate is not applied (equivalent to Hunter) · indicators warm up on the whole history (slightly better than the live frame) · "
            "trades still open at history end are excluded. Replay is statistical evidence, not a replacement for live trades."))

# =============================================================================
# تب ۷ — اعتبار لبه (فاز ۵)
with tab_edge:
    st.subheader("⚖️ " + L("اعتبار لبه ایجنت‌ها", "Agent edge credibility"))
    st.caption(L(
        "پاسخِ سؤالی که هیچ دروازه‌ی فعلی نمی‌پرسد: «خودِ این ایجنت تاریحاً سودده بوده؟» — یک بازپخش کامل روی کل تاریخچه اجرا می‌شود "
        "و معامله‌های هر ایجنت به پنجره‌های زمانیِ جدا (بر اساس کندل ورود) تفکیک می‌شود: ایجنتی که فقط در یک دوره خوب بوده شانسی است؛ "
        "حکم فقط با ثبات بین پنجره‌ها صادر می‌شود. حکم‌ها روی اسکن زنده اثر می‌گذارند (بنچ + وزن رأی کمیسیون).",
        "Answers the question no current gate asks: 'has this agent itself been profitable historically?' — one full replay over the whole "
        "history with each agent's trades split into separate time windows (by entry candle): an agent good in only one period is luck; "
        "verdicts require consistency across windows. Verdicts affect the live scan (bench + committee vote weights)."))

    _E = st.session_state.get("edge_state") or _edge_state_any

    _ec1, _ec2, _ec3, _ec4 = st.columns([0.8, 0.9, 2.2, 1.1])
    with _ec1:
        edge_wins = st.select_slider(L("تعداد پنجره", "Windows"), options=[2, 3, 4], value=3, key="edge_wins")
    with _ec2:
        edge_cpw = st.selectbox(L("کندل هر پنجره", "Candles / window"),
                                [150, 200, 250, 300, 350, 400], index=3, key="edge_cpw")
    with _ec3:
        edge_syms = st.multiselect(L("نمادها (حداکثر ۲۰)", "Symbols (max 20)"),
                                   A.POOL_FALLBACK, default=A.POOL_FALLBACK,
                                   max_selections=RP.MAX_SYMBOLS, key="edge_syms")
    with _ec4:
        st.write("")
        edge_go = st.button("⚖️ " + L("بازپخش چندپنجره‌ای", "Multi-window replay"), type="primary",
                            width="stretch", key="edge_go")

    if edge_go:
        if not edge_syms:
            st.warning(L("حداقل یک نماد انتخاب کن.", "Pick at least one symbol."))
        else:
            try:
                with st.spinner(L(
                    f"{len(edge_syms)} نماد × {EG.REPLAY_WARMUP + edge_wins * edge_cpw + EG.RESOLVE_TAIL} کندل گرفته می‌شود، "
                    f"بعد بازپخش کامل + تفکیک {edge_wins} پنجره‌ای … (۱–۳ دقیقه)",
                    f"Fetching {len(edge_syms)} symbols × {EG.REPLAY_WARMUP + edge_wins * edge_cpw + EG.RESOLVE_TAIL} candles, "
                    f"then full replay + {edge_wins}-window split … (1–3 min)")):
                    _eres = EG.run_multi_window(exchange, interval, edge_syms,
                                                windows=int(edge_wins), candles_per_window=int(edge_cpw))
                if _eres.get("error"):
                    st.error(L(f"بازپخش چندپنجره‌ای انجام نشد: {_eres['error']}",
                               f"Multi-window replay failed: {_eres['error']}"))
                else:
                    EG.save_edge(_eres)
                    st.session_state["edge_state"] = _eres
                    _E = _eres
            except Exception as exc:  # noqa: BLE001
                st.error(L(f"بازپخش چندپنجره‌ای اجرا نشد: {exc}", f"Multi-window replay failed: {exc}"))

    if not _E:
        st.info(L(
            "هنوز حکمی وجود ندارد — روی «⚖️ بازپخش چندپنجره‌ای» بزن. پیش‌فرض ۱۲ ارز بزرگ × ۳ پنجره‌ی ۳۰۰کندلی است "
            "(هر پنجره ~۵۰ روز چهارساعته). تا حکم صادر نشود گیت لبه بی‌اثر است و رفتار میدان عیناً مثل قبل است.",
            "No verdicts yet — hit '⚖️ Multi-window replay'. Default: 12 major coins × 3 windows of 300 candles "
            "(~50 days each on 4h). Until verdicts exist the edge gate is inert and arena behavior is exactly as before."))
    else:
        _em = _E.get("meta") or {}
        _age = int(_em.get("age_s") or 0)
        if _age >= EG.EDGE_TTL_S:
            st.warning(L(
                "این حکم‌ها کهنه‌اند (بیش از یک هفته) — گیت فقط با حکم تازه مسلح می‌شود؛ دوباره بازپخش بگیر.",
                "These verdicts are stale (over a week) — the gate only arms with fresh verdicts; rerun the replay."))
        _es = _E.get("summary") or {}
        _f1, _f2, _f3, _f4 = st.columns(4)
        _f1.metric(L("پنجره‌ها", "Windows"), _em.get("windows", "—"))
        _f2.metric(L("معاملات بسته‌ی بازپخش", "Replayed closed trades"), _es.get("n", 0))
        _f3.metric(L("انتظاری کل بازپخش", "Replay expectancy"), f"{_es.get('expectancy', 0):+.2f}R")
        _f4.metric(L("بازه‌ی تاریخچه", "History span"), f"{_em.get('span_days', 0):.0f} " + L("روز", "days"))

        _vrows = []
        for _nm in [p["name"] for p in A.participants() if p["kind"] == "agent"]:
            _d = (_E.get("detail") or {}).get(_nm) or {}
            _row = {L("ایجنت", "Agent"): _nm}
            for _wi, _wst in enumerate(_d.get("windows") or []):
                _row[L(f"پنجره {_wi + 1}", f"Window {_wi + 1}")] = f"{_wst.get('exp', 0):+.2f}R · n={_wst.get('n', 0)}"
            _tot = _d.get("total") or {}
            _row[L("کل", "Total")] = f"{_tot.get('exp', 0):+.2f}R"
            _row["PF"] = f"{_tot.get('pf', 0):.2f}"
            _row[L("حکم", "Verdict")] = (EG.VERDICT_FA if LANG != "en" else EG.VERDICT_EN).get(_d.get("verdict"), "—")
            _row[L("وزن رأی", "Vote weight")] = f"{EG.weight_for(_E.get('verdicts'), _nm):.1f}×"
            _vrows.append(_row)
        st.dataframe(pd.DataFrame(_vrows), width="stretch", hide_index=True)
        st.caption(L(
            "قواعد حکم (ثابت و شفاف): ❌ زیان‌ده = حداقل ۱۲ معامله + انتظاری کل زیر −۰٫۱۰R + زیان در بیشتر از نیمِ پنجره‌های فعال · "
            "✅ سودده = حداقل ۱۲ معامله + انتظاری کل بالای +۰٫۰۵R + PF کل > ۱ + هیچ پنجره‌ای بدتر از −۰٫۲۵R + زیان در حداکثر نیمِ پنجره‌ها · "
            "⚠️ بقیه (نمونه‌ی کم یا مخلوط). معامله به پنجره‌ی «ورودش» تعلق دارد؛ دُمِ آخر (فرصت بستن) هم به پنجره‌ی آخر می‌رود.",
            "Verdict rules (fixed & transparent): ❌ losing = 12+ trades + total expectancy < −0.10R + losses in more than half the active windows · "
            "✅ profitable = 12+ trades + total expectancy > +0.05R + total PF > 1 + no window worse than −0.25R + losses in at most half the windows · "
            "⚠️ otherwise (small or mixed sample). A trade belongs to the window of its entry; the closing tail belongs to the last window."))

    st.subheader("🎛️ " + L("گیت لبه در اسکن زنده", "Edge gate in live scan"))
    st.radio(L("حالت گیت", "Gate mode"), EG.MODES,
             format_func=lambda m: (EG.MODE_FA if LANG != "en" else EG.MODE_EN).get(m, m),
             key="edge_mode", horizontal=True)
    st.caption(L(
        "بنچ یعنی «معامله‌ی تازه باز نمی‌کند» — پوزیشن‌های بازِ او طبق قواعد معمول (TP/SL/تایم‌اوت) مدیریت می‌شوند. "
        "بدون حکم تازه، هر سه حالت عملاً یک‌اند و رفتار میدان مثل قبل است.",
        "Benching means 'no new trades' — their open positions are still managed by the normal rules (TP/SL/timeout). "
        "Without fresh verdicts all three modes are equivalent and arena behavior is unchanged."))
    if _verdicts:
        _benched2 = [p["name"] for p in A.participants()
                     if p["kind"] == "agent" and not EG.allows(_verdicts, p["name"], _edge_mode)]
        if _benched2:
            st.info("⚖️ " + L(f"الان بنچ: {'، '.join(_benched2)}",
                              f"Currently benched: {', '.join(_benched2)}"))
        else:
            st.success("⚖️ " + L("هیچ ایجنتی بنچ نیست — همه با لبه‌ی تأییدشده یا بی‌حکم معامله می‌کنند.",
                                 "Nobody is benched — everyone trades with a verified edge or without a verdict."))
    else:
        st.info("⚖️ " + L("گیت بی‌سلاح است (حکم تازه‌ای نیست) — با بازپخش چندپنجره‌ای مسلحش کن.",
                          "The gate is unarmed (no fresh verdicts) — arm it with a multi-window replay."))
