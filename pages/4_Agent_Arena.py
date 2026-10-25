"""🏟️ Agent Arena — میدان ایجنت‌ها (لیگ معاملاتی کاغذی)
هر شرکت‌کننده (۴ ایجنت + کمیسیون) مستقلاً صرافی را اسکن می‌کند، ارز خودش را
انتخاب می‌کند، معامله‌ی کاغذی باز می‌کند و تا TP/SL/تایم‌اوت مدیریت می‌شود.
لیدربورد: امتیاز R-based + وین‌ریت + ایکوییتی.
"""
from __future__ import annotations

import time
from datetime import datetime

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
    "۵ شرکت‌کننده (۴ ایجنت + کمیسیون) روی صرافی انتخابی تو، خودشان ارزهای پرقدرت را پیدا می‌کنند، "
    "تحلیل می‌کنند و معامله‌ی کاغذی باز می‌کنند. معامله‌ها بین بازدیدها زنده می‌مانند و تا TP/SL/تایم‌اوت مدیریت می‌شوند. "
    "در پایان: کدوم ایجنت بهترین وین‌ریت و امتیاز را می‌گیرد؟",
    "5 participants (4 agents + Committee) hunt strong coins on your exchange, analyze them and open paper trades. "
    "Trades persist between visits and are managed until TP/SL/timeout. Who ends up with the best winrate and score?"))

from core import arena as A  # noqa: E402
from core import arena_store  # noqa: E402
from core.duel_engine import _dec_for  # noqa: E402

EXCHANGES = ["KuCoin", "OKX", "Binance", "Bybit", "Lighter", "XT", "LBank", "KCEX"]
_store = arena_store.get_store()

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
if _hc.get("backend") != "supabase":
    st.warning(L(
        "داده‌ی میدان الان روی فایل محلی ذخیره می‌شود (با redeploy پاک می‌شود). برای ذخیره‌ی همیشگی، "
        "فایل sql/arena_setup.sql را یک‌بار در Supabase → SQL Editor اجرا کن.",
        "Arena data is stored in a local file (lost on redeploy). Run sql/arena_setup.sql once in Supabase → SQL Editor for persistent storage."))

_m1, _m2, _m3, _m4 = st.columns(4)
_m1.metric(L("پوزیشن‌های باز", "Open positions"), len(_open_trades))
_m2.metric(L("معاملات بسته‌شده", "Closed trades"), len(_closed_trades))
_m3.metric(L("شرکت‌کننده‌ها", "Participants"), len(A.participants()))
_m4.metric(L("ریسک هر معامله", "Risk per trade"), f"{A.RISK_PCT:.0f}%")

tab_scan, tab_pos, tab_board = st.tabs([
    "🔎 " + L("اسکن و معامله‌ی جدید", "Scan & new trades"),
    "📊 " + L("پوزیشن‌های باز", "Open positions"),
    "🏆 " + L("لیدربورد و تاریخچه", "Leaderboard & history"),
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
    st.markdown(
        f"<div dir='rtl' style='border:1px solid rgba(148,163,184,.25);border-right:5px solid {color};"
        f"border-radius:14px;padding:12px 14px;margin:8px 0;background:rgba(148,163,184,.05)'>"
        f"<div style='display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;align-items:center'>"
        f"<span>{_chip(t.get('agent',''), color)} <b style='font-size:16px'>{t.get('symbol')}</b> {_dir_badge(int(t.get('direction') or 0))}</span>"
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
        f"قیمت زنده: {lp_txt} · R:R {t.get('rr', 0):.1f} · امتیاز ورود {t.get('score', 0):+.2f} · {t.get('interval')} · {_age_label(t)}"
        f"</div>"
        + (f"<div style='margin-top:6px;font-size:11px;color:#cbd5e1'><b>مدرک:</b> {t.get('evidence','')}</div>" if t.get("evidence") else "")
        + "</div>",
        unsafe_allow_html=True,
    )


def _unrealized_r(t: dict, live_price: float | None) -> float | None:
    """R تخمینی الان = رآلیزه‌شده + باقیمانده‌ی پوزیشن با قیمت زنده."""
    if not live_price:
        return None
    entry = float(t.get("entry"))
    risk0 = abs(entry - float(t.get("stop")))
    if risk0 <= 0:
        return None
    frac = 1.0 - (1 / 3 if t.get("tp1_done") else 0) - (1 / 3 if t.get("tp2_done") else 0)
    move = (float(live_price) - entry) * (1 if int(t.get("direction") or 0) > 0 else -1)
    return float(t.get("realized_r") or 0.0) + max(0.0, frac) * move / risk0


# =============================================================================
# تب ۱ — اسکن
with tab_scan:
    st.caption(L(
        "هر شرکت‌کننده با وزن‌های خودش همه‌ی ارزهای اسکن‌شده را ارزیابی می‌کند؛ فقط جایی معامله باز می‌کند که: "
        "۱) امتیاز خودش از آستانه‌اش رد شده، ۲) بک‌تست خودش روی همان ارز سودده بوده (PF>1)، "
        "۳) موتور ستاپ walk-forward هم‌جهت تأیید کرده، ۴) R:R ≥ ۱. کمیسیون هم با اجماع ۳/۴ ایجنت وارد می‌شود.",
        "Each participant evaluates every scanned coin with its own weights and only trades when: "
        "1) its own score passes its threshold, 2) its own backtest on that coin is profitable (PF>1), "
        "3) the walk-forward validated setup agrees, 4) R:R ≥ 1. The Committee enters on 3/4 consensus."))

    c1, c2, c3, c4 = st.columns([1.3, 1, 1, 1.1])
    with c1:
        exchange = st.selectbox(L("صرافی", "Exchange"), EXCHANGES, index=0, key="arena_exch")
    with c2:
        interval = st.selectbox(L("تایم‌فریم (برای همه)", "Timeframe (for all)"),
                                ["15min", "1hour", "4hour", "1day"], index=1, key="arena_tf")
    with c3:
        n_pool = st.select_slider(L("تعداد ارز اسکن", "Coins to scan"), options=[12, 20, 30], value=20, key="arena_n")
    with c4:
        st.write("")
        go = st.button("🔎 " + L("شروع اسکن", "Run scan"), type="primary", use_container_width=True, key="arena_go")

    if exchange == "Lighter":
        st.info(L("Lighter پرپ است — نمادها بدون USDT هستند.", "Lighter is perp — symbols without USDT."))

    if go:
        t0 = time.time()
        try:
            with st.spinner(L(f"ایجنت‌ها در حال بررسی {n_pool} ارز روی {exchange} · {interval} … (۳۰–۹۰ ثانیه)",
                              f"Agents are scanning {n_pool} coins on {exchange} · {interval} … (30–90s)")):
                scans, errors = A.run_scan(exchange, interval, int(n_pool))
                opened, blocked = A.open_trades_from_scan(scans, exchange, interval, _store)
            st.session_state["arena_scan"] = {
                "scans": scans, "errors": errors, "opened": opened, "blocked": blocked,
                "exchange": exchange, "interval": interval, "n": int(n_pool),
                "took": time.time() - t0, "ts": datetime.now().strftime("%Y-%m-%d %H:%M")}
            st.session_state.pop("_arena_upd", None)
        except Exception as exc:  # noqa: BLE001
            st.error(L(f"اسکن اجرا نشد: {exc}", f"Scan failed: {exc}"))

    H = st.session_state.get("arena_scan")
    if not H:
        st.info(L("روی «🔎 شروع اسکن» بزن — ایجنت‌ها خودشان می‌گردند و بهترین فرصت‌ها را معامله می‌کنند.",
                  "Hit 'Run scan' — agents will hunt and trade the best opportunities themselves."))
    else:
        scans, opened = H["scans"], H["opened"]
        ok_scans = [s for s in scans if not s.get("error")]
        n_agents_ok = sum(1 for s in ok_scans if any(a["ok"] for a in s.get("agents", {}).values()))
        n_com_ok = sum(1 for s in ok_scans if (s.get("committee") or {}).get("ok"))
        k1, k2, k3, k4 = st.columns(4)
        k1.metric(L("ارز بررسی‌شده", "Coins scanned"), len(scans))
        k2.metric(L("معامله‌ی باز‌شده", "Trades opened"), len(opened))
        k3.metric(L("ایجنت‌های واجد شرایط", "Agents qualified"), n_agents_ok)
        k4.metric(L("کمیسیون واجد شرایط", "Committee qualified"), n_com_ok)
        st.caption(L(f"{H['exchange']} · {H['interval']} · {H['n']} ارز در {H['took']:.0f} ثانیه · {H['ts']}"
                     + (f" · {len(H['errors'])} ارز خطا داد" if H["errors"] else ""),
                     f"{H['exchange']} · {H['interval']} · {H['n']} coins in {H['took']:.0f}s · {H['ts']}"
                     + (f" · {len(H['errors'])} errors" if H["errors"] else "")))

        if opened:
            st.subheader("🆕 " + L("معامله‌های تازه", "Fresh trades"))
            for t in opened:
                _trade_card(t, _live.get(t.get("symbol")), _unrealized_r(t, _live.get(t.get("symbol"))))
        else:
            v_pass = sum(1 for s in ok_scans if s.get("v_ok"))
            st.warning(L(
                f"هیچ معامله‌ی تازه‌ای باز نشد — از {len(ok_scans)} ارز، فقط {v_pass} تا ستاپ اعتبارسنجی‌شده داشتند و "
                f"هیچ شرکت‌کننده‌ای (یا سهمیه‌ی خالی‌ای) هم‌جهتش نبود. یعنی الان لبه‌ی واضحی نیست — سیگنال الکی بهتر از بی‌معامله‌ای نیست.",
                f"No new trades — of {len(ok_scans)} coins only {v_pass} had a validated setup and no participant "
                f"(or free slot) matched direction. No clear edge right now — better no trade than a random one."))

        with st.expander(L("📋 ریز اسکن (همه‌ی ارزها)", "📋 Scan details (all coins)"), expanded=False):
            rows = []
            for s in sorted(ok_scans, key=lambda s: -abs(float((s.get("committee") or {}).get("score", 0)))):
                com = s.get("committee") or {}
                best = max(s.get("agents", {}).values(), key=lambda a: a["quality"], default=None)
                rows.append({
                    L("نماد", "Symbol"): s.get("symbol"),
                    L("کمیسیون", "Committee"): f"{com.get('score', 0):+.2f}",
                    L("موافق", "Agree"): f"{com.get('n_agree', 0)}/4",
                    L("ستاپ معتبر", "Valid setup"): "✅" if s.get("v_ok") else "—",
                    L("بهترین ایجنت", "Best agent"): (f"{best['score']:+.2f}" if best else "—"),
                    L("واجد", "Qualified"): ("✅" if (com.get("ok") or any(a["ok"] for a in s.get("agents", {}).values())) else "—"),
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            if H["errors"]:
                st.caption(L("خطاها: ", "Errors: ") + " | ".join(H["errors"][:5]))

    with st.expander("⚖️ " + L("قواعد انصاف و امتیازدهی", "Fairness & scoring rules"), expanded=False):
        st.markdown(L(
            "**امتیاز هر معامله:** TP3 کامل = **+۵** · TP2 = **+۲** · TP1 و خروج با تریل = **+۱** · سر‌به‌سر = **۰** · "
            "استاپ (لیکویید ایجنت) = **−۱** · تایم‌اوت = **±۰٫۵** بر اساس علامت سود/زیان.\n\n"
            "**وین‌ریت** = بردها ÷ (بردها + باخت‌ها) — سر‌به‌سر‌ها شمرده نمی‌شوند.\n\n"
            "**قواعد انصاف:** همه با یک universe ارز، یک تایم‌فریم، کارمزد یکسان، ریسک ثابت **۱٪** در هر معامله، "
            "حداکثر **۳ پوزیشن** همزمان برای هر شرکت‌کننده و سقف **۱۵** پوزیشن برای کل میدان. "
            "هر ارز فقط یک پوزیشن باز برای هر شرکت‌کننده + cooldown پس از بستن معامله. "
            "در هر کندل اول استاپ چک می‌شود (محافظه‌کارانه)، بعد تارگت‌ها — یعنی نتایج به واقعیت بدبینانه‌تر نزدیک است.\n\n"
            "**خروج نردبانی:** TP1 → استاپ به ورود · TP2 → استاپ به TP1 · TP3 → بستن کامل. "
            "معامله‌ی سرگردان بعد از ۱۰۰ کندل با قیمت بازار بسته می‌شود.",
            "**Trade score:** full TP3 = **+5** · TP2 = **+2** · TP1 then trail-out = **+1** · breakeven = **0** · "
            "stop (agent liquidation) = **−1** · timeout = **±0.5** by PnL sign.\n\n"
            "**Winrate** = wins ÷ (wins + losses) — breakevens excluded.\n\n"
            "**Fairness:** same coin universe, timeframe, fees, fixed **1%** risk per trade, max **3 concurrent** "
            "positions per participant, **15** for the whole arena. One open position per symbol per participant + "
            "cooldown after closing. Stops are checked first each candle (conservative) — results skew realistic/pessimistic.\n\n"
            "**Ladder exit:** TP1 → stop to entry · TP2 → stop to TP1 · TP3 → full close. "
            "Stalled trades close at market after 100 candles."))

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
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.caption(L("معامله‌ها هر بار که صفحه باز شود با کندل‌های تازه پیش برده می‌شوند (حداکثر هر ۶۰ ثانیه).",
                     "Trades are advanced with fresh candles whenever this page loads (at most once per 60s)."))
        for t in sorted(_open_trades, key=lambda t: t.get("agent", "")):
            _trade_card(t, _live.get(t.get("symbol")), _unrealized_r(t, _live.get(t.get("symbol"))))

# =============================================================================
# تب ۳ — لیدربورد و تاریخچه
with tab_board:
    board = A.leaderboard(_closed_trades, _open_trades)
    MEDALS = ["🥇", "🥈", "🥉"]
    rows = []
    for i, r in enumerate(board):
        streak = r["streak"]
        streak_txt = f"🔥 {streak}" if streak > 1 else f"🧊 {-streak}" if streak < -1 else "—"
        rows.append({
            L("رتبه", "Rank"): MEDALS[i] if i < 3 and r["trades"] else f"{i + 1}",
            L("شرکت‌کننده", "Participant"): r["agent"],
            L("ایکوییتی $", "Equity $"): f"{r['equity']:,.0f}",
            L("وین‌ریت", "Winrate"): f"{r['winrate']:.0f}%" if r["trades"] else "—",
            L("امتیاز", "Points"): f"{r['points']:+.1f}" if r["trades"] else "—",
            "R کل": f"{r['total_r']:+.2f}" if r["trades"] else "—",
            "PF": f"{r['pf']:.2f}" if r["trades"] else "—",
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
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

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
        st.plotly_chart(fig, use_container_width=True)

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
        st.dataframe(hdf, use_container_width=True, hide_index=True)
        st.download_button("💾 " + L("دانلود تاریخچه (CSV)", "Download history (CSV)"),
                           data=hdf.to_csv(index=False).encode("utf-8"),
                           file_name="arena_history.csv", mime="text/csv", key="arena_csv")

    st.caption(L(f"بک‌اند: {_hc.get('backend')} · جدول: arena_trades",
                 f"Backend: {_hc.get('backend')} · table: arena_trades"))
