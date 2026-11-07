"""بورس ایران — دیده‌بان بازار تهران: وضعیت بازار، شاخص‌ها، برترین‌ها و تحلیل نماد
(همان موتور تحلیلِ داشبورد کریپتو — این‌بار روی داده‌ی بورس تهران)"""
from __future__ import annotations

import time

import pandas as pd
import streamlit as st

from core.webview import iframe_html

from app_base import (add_indicators, build_agents_svg, build_neural_shell_svg,
                      compute_agents, confluence, fvg_summary, make_plan,
                      signal_card_parts, signal_events, swing_levels)
from core import macro_ir as M
from core import tse as T
from core.help import hint
from core.i18n import get_lang, setup_i18n, tr
from core.tv_chart import build_tv_chart_html

st.set_page_config(page_title="بورس ایران | TSE Watch", page_icon="🇮🇷", layout="wide")
setup_i18n(page="p6")

st.title("🏛️ " + tr("بورس ایران — دیده‌بان بازار تهران", "Tehran Stock Exchange — Market Watch"))
hint(tr(
    "داده از سرورهای عمومی TSETMC (بدون کلید) · شنبه تا چهارشنبه ۰۸:۴۵ تا ۱۲:۳۰ · "
    "تحلیل با همان موتور داشبورد (همگرایی + پوسته مدل‌ها + طرح معامله walk-forward). "
    "اگر داده نیامد: سرورهای بورس بعضی IPهای خارج از ایران را بسته‌اند — اجرای لوکال از داخل ایران همیشه کار می‌کند.",
    "Data from public TSETMC servers (no keys) · Sat–Wed 08:45–12:30 Tehran · "
    "analyzed by the same engine as the crypto dashboard. If data fails: TSE servers block some "
    "non-Iranian IPs — running locally from inside Iran always works."))


# ---------------------------------------------------------------- کش داده
@st.cache_data(ttl=45, show_spinner=False)
def _mw_rows() -> list[dict]:
    return T.market_watch()


@st.cache_data(ttl=30, show_spinner=False)
def _snap(ins_code: str) -> dict:
    return T.snapshot(ins_code)


@st.cache_data(ttl=30, show_spinner=False)
def _idx_all() -> dict:
    return T.indices()


@st.cache_data(ttl=3600, show_spinner=False)
def _hist(ins_code: str) -> pd.DataFrame:
    return T.history(ins_code)


@st.cache_data(ttl=300, show_spinner=False)
def _macro() -> dict:
    return M.quotes()


_WEEK_FA = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه", "شنبه", "یکشنبه"]
_WEEK_EN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _status_row() -> None:
    ss = T.session_status()
    en = get_lang() == "en"
    days = _WEEK_EN if en else _WEEK_FA
    wd = days[ss["weekday"]]
    state = (tr("🟢 باز", "🟢 Open") if ss["open"] else
             (tr("🟡 روز معاملاتی — بسته", "🟡 Trading day — closed") if ss["trading_day"]
              else tr("🔴 تعطیل (پنجشنبه/جمعه)", "🔴 Closed (Thu/Fri)")))
    c1, c2, c3 = st.columns(3)
    c1.metric(tr("وضعیت بازار", "Market status"), state)
    c2.metric(tr("ساعت تهران", "Tehran time"), f"{ss['hhmm']}")
    c3.metric(tr("روز هفته", "Weekday"), wd)
    hint(tr(
        "تعطیلات رسمی (مناسبت‌ها) از راه دور قابل تشخیص نیست — فقط الگوی هفتگی هفته‌ی معاملاتی.",
        "Official holidays can't be detected remotely — only the weekly trading pattern is applied."))


def _macro_row() -> None:
    """چشم‌انداز کلان — دلار/یورو/طلا/سکه (الگوی پورت‌شده از TITAN)."""
    q = _macro()
    if not any(q.values()):
        st.caption("💡 " + tr(
            "قیمت‌های کلان (دلار/طلا/سکه) از TGJU گرفته نشد — این بخش تکمیلی است و مانع بورس نمی‌شود.",
            "Macro prices (USD/gold/coin) could not be fetched from TGJU — this strip is optional; the TSE section still works."))
        if M.last_error:
            st.caption("· " + M.last_error)
        return
    st.caption("🌐 " + tr("چشم‌انداز کلان — منبع: TGJU · قیمت به تومان",
                          "Macro backdrop — source: TGJU · prices in toman"))
    cols = st.columns(len(M.PROFILES))
    for i, (key, prof) in enumerate(M.PROFILES.items()):
        row = q.get(key)
        with cols[i]:
            label = f"{prof['icon']} {tr(prof['fa'], prof['en'])}"
            if row:
                st.metric(label, f"{row['price']:,.0f}")
            else:
                st.metric(label, "—", delta_color="off")


def _indices_row() -> None:
    idx = _idx_all()
    cols = st.columns(max(1, len(T.INDEXES)))
    en = get_lang() == "en"
    for i, name in enumerate(T.INDEXES):
        row = idx.get(name)
        label = name if not en else ("TEDPIX (total)" if i == 0 else "Equal-weight")
        with cols[i]:
            if row:
                st.metric(label, f"{row['last']:,.0f}",
                          f"{row['change_pct']:+.2f}%" + ("" if row.get("live") else " · " + tr("آخرین روز", "last day")))
            else:
                st.metric(label, "—", delta_color="off")


def _clean_rows(rows: list[dict]) -> list[dict]:
    """حذف شاخص‌ها و حق‌تقدم‌ها از لیست‌های برترین‌ها."""
    return [r for r in rows
            if r.get("last", 0) > 0 and r.get("volume", 0) > 0
            and "شاخص" not in r.get("name", "")
            and not str(r.get("symbol", "")).startswith("ح")]


def _fmt_rows(rows: list[dict], n: int = 12) -> pd.DataFrame:
    out = []
    for r in rows[:n]:
        out.append({
            tr("نماد", "Symbol"): r["symbol"],
            tr("نام", "Name"): r.get("name", ""),
            tr("آخرین (ریال)", "Last (Rial)"): f"{r['last']:,.0f}",
            tr("پایانی (ریال)", "Adj. close (Rial)"): f"{r['adj_close']:,.0f}",
            tr("تغییر ٪", "Change %"): f"{r['change_pct']:+.2f}%",
            tr("حجم (میلیون)", "Vol (M)"): f"{r['volume'] / 1e6:,.1f}",
            tr("ارزش (میلیارد ریال)", "Value (B Rial)"): f"{r['value'] / 1e9:,.1f}",
        })
    return pd.DataFrame(out)


# ---------------------------------------------------------------- بدنه
_status_row()
st.divider()
_macro_row()
_indices_row()
st.divider()

rows = _mw_rows()
if not rows:
    st.error("⛔ " + tr(
        "داده‌ی بورس گرفته نشد.",
        "Could not fetch TSE data."))
    if T.last_error:
        st.caption("💡 " + (T.last_error if get_lang() != "en" else
                            "TSE servers did not respond — they block many non-Iranian IPs; "
                            "run the app locally from inside Iran, then retry."))
    st.stop()

rows = _clean_rows(rows)

st.subheader("🏆 " + tr("برترین‌های امروز", "Today's leaders"))
tb1, tb2, tb3 = st.tabs([
    "🚀 " + tr("بیشترین رشد", "Top gainers"),
    "🩸 " + tr("بیشترین افت", "Top losers"),
    "🔥 " + tr("بیشترین حجم", "Most active"),
])
with tb1:
    st.dataframe(_fmt_rows(sorted(rows, key=lambda r: -r["change_pct"])),
                 width="stretch", hide_index=True)
with tb2:
    st.dataframe(_fmt_rows(sorted(rows, key=lambda r: r["change_pct"])),
                 width="stretch", hide_index=True)
with tb3:
    st.dataframe(_fmt_rows(sorted(rows, key=lambda r: -r["volume"])),
                 width="stretch", hide_index=True)

st.divider()
st.subheader("🔎 " + tr("تحلیل نماد", "Symbol analysis"))

with st.container(border=True):
    q = st.text_input(tr("نام نماد را بنویس (مثل فولاد، فملی، شپنا، وبملت)",
                         "Type a symbol (e.g. فولاد, فملی, شپنا, وبملت)"), value="")
    found = []
    if q.strip():
        with st.spinner(tr("در حال جست‌وجو…", "Searching…")):
            found = T.search(q.strip())
        if not found:
            st.warning(tr("نمادی با این نام پیدا نشد.", "No symbol matched."))
    if found:
        opts = [f"{r['symbol']} — {r.get('name', '')}" for r in found]
        pick = st.selectbox(tr("نماد", "Symbol"), opts,
                            format_func=lambda o, _o=opts: _o[_o.index(o)] if o in _o else o)
        sel = found[opts.index(pick)] if pick in opts else found[0]
        ins = sel["ins_code"]
        st.caption(f"insCode: `{ins}`")

        df = _hist(ins)
        if df.empty:
            st.error(tr("تاریخ روزانه‌ی این نماد گرفته نشد — چند لحظه بعد دوباره امتحان کن.",
                        "Daily history failed — try again shortly."))
            if T.last_error:
                st.caption("⚠️ " + tr("دلیل: ", "Reason: ") + T.last_error)
            st.stop()
        d = df.tail(420).copy().reset_index(drop=True)
        d = add_indicators(d)
        score_series, comp_table = confluence(d)
        score = float(score_series.iloc[-1])
        levels = swing_levels(d)
        plan = make_plan(d, score, levels)
        events, state = signal_events(d, score_series)
        fvg_info = fvg_summary(d)
        price = float(d["close"].iloc[-1])
        dec = 2 if price < 100 else 0

        # اسنپ‌شات زنده (اگر بازار باز باشد قیمت امروز است)
        snap = _snap(ins)
        live_last = float(snap.get("last") or 0)
        yes = float(snap.get("yesterday") or 0) or float(d["yesterday"].iloc[-1] or 0)
        chg = ((live_last - yes) / yes * 100.0) if (live_last > 0 and yes > 0) else 0.0
        shown = live_last if live_last > 0 else price

        m1, m2, m3, m4 = st.columns(4)
        m1.metric(sel["symbol"], f"{shown:,.{dec}f}",
                  f"{chg:+.2f}%" if chg else None)
        m2.metric(tr("همگرایی اندیکاتورها", "Indicator confluence"),
                  f"{score:+.0f} · " + (tr("خرید قوی", "Strong Buy") if score > 40 else
                                        tr("خرید", "Buy") if score > 12 else
                                        tr("خنثی", "Neutral") if score > -12 else
                                        tr("فروش", "Sell") if score > -40 else
                                        tr("فروش قوی", "Strong Sell")))
        m3.metric("ATR", f"{plan['atr']:,.{dec}f}" if plan.get("atr") else "—")
        _lbl, _val, _delta = signal_card_parts(state, get_lang())
        m4.metric(_lbl, _val, delta=_delta)
        if snap.get("state"):
            st.caption(tr(f"وضعیت نماد: {T.STATE_FA.get(snap['state'], snap['state'])}",
                          f"Instrument state: {snap['state']}"))

        iframe_html(
            "<div style='background:#f6f8fb;margin:0;padding:2px;border-radius:12px'>"
            + build_neural_shell_svg(comp_table, score, fvg=fvg_info, price=price)
            + "</div>",
            height=420,
        )
        if fvg_info.get("text"):
            st.caption("🟪 " + fvg_info["text"])
        st.divider()

        # ---- چارت TV با نواحی FVG و سطوح طرح معامله ------------------------
        def _zone(z: dict, kind: str, tag: str) -> dict:
            return {"t0": int(pd.Timestamp(z["dt"]).timestamp()),
                    "top": z["top"], "bottom": z["bottom"], "kind": kind, "tag": tag}

        def _to_candles(dd: pd.DataFrame) -> list[list]:
            out = []
            for _, r in dd.iterrows():
                vals = [r["open"], r["high"], r["low"], r["close"], r["volume"]]
                if any(pd.isna(v) for v in vals):
                    continue
                out.append([int(pd.Timestamp(r["date"]).timestamp()),
                            float(vals[0]), float(vals[1]), float(vals[2]),
                            float(vals[3]), float(vals[4])])
            return out

        candles = _to_candles(d)
        _tv_zones = ([_zone(z, "bull", "FVG▲") for z in fvg_info["bulls"][:4]]
                     + [_zone(z, "bear", "FVG▼") for z in fvg_info["bears"][:4]]
                     + [_zone(z, "bvg", "BVG") for z in fvg_info["bvgs"][:3]])
        _tv_levels: list = []
        if plan.get("entry") is not None:
            _tv_levels = [{"price": plan["entry"], "name": tr("ورود", "Entry"), "color": "#f59e0b", "dash": False},
                          {"price": plan["stop"], "name": tr("حد ضرر", "Stop"), "color": "#ef5350", "dash": True}]
            for _i, (_tp, _rr) in enumerate(plan["targets"]):
                _tv_levels.append({"price": _tp, "name": f"{tr('هدف', 'TP')}{_i + 1} · {_rr}R",
                                   "color": "#2962ff", "dash": True})
        iframe_html(
            build_tv_chart_html(candles=candles, tfs={"1D": candles}, base_tf="1D",
                                symbol=sel["symbol"], zones=_tv_zones, levels=_tv_levels,
                                title=f"{sel['symbol']} · TSE · 1D", dec=dec,
                                initial_bars=320),
            height=700,
        )

        # ---- طرح معامله ----------------------------------------------------
        st.subheader("🎯 " + tr("طرح معامله — ستاپ اعتبارسنجی‌شده (walk-forward روی همین نماد)",
                                "Trade plan — walk-forward-validated on this symbol"))
        if plan.get("status") == "wait" or plan.get("entry") is None:
            st.warning("⏸ **" + tr("بدون معامله.", "No trade.") + "** "
                       + (plan.get("why", "") if get_lang() != "en" else
                          tr("ستاپ هنوز معتبر نشده — شرایط ورود کامل نیست و موتور اجازه‌ی ورود نمی‌دهد.",
                             "The setup is not validated yet — the engine stays out.")))
        else:
            p1, p2, p3, p4 = st.columns(4)
            _dir = plan["direction"] if get_lang() != "en" else (
                "LONG (Buy) 🟢" if str(plan["direction"]).startswith("لانگ") else
                "SHORT (Sell) 🔴" if str(plan["direction"]).startswith("شورت") else plan["direction"])
            p1.metric(tr("جهت", "Direction"), _dir, delta_color="off")
            p2.metric(tr("ورود", "Entry"), f"{plan['entry']:,.{dec}f}")
            p3.metric(tr("حد ضرر", "Stop"), f"{plan['stop']:,.{dec}f}",
                      f"{(plan['stop'] / plan['entry'] - 1) * 100:+.2f}%", delta_color="off")
            if plan.get("targets"):
                _tp1, _rr1 = plan["targets"][0]
                p4.metric(f"{tr('هدف', 'TP')}1", f"{_tp1:,.{dec}f}", f"{_rr1}R", delta_color="off")
            if plan.get("targets"):
                st.caption(" · ".join(f"TP{_i + 1}: {_tp:,.{dec}f} ({_rr}R)"
                                      for _i, (_tp, _rr) in enumerate(plan["targets"])))

        # ---- دفتر ایجنت‌ها ---------------------------------------------------
        st.divider()
        st.subheader("◈ " + tr("دفتر ایجنت‌ها — بک‌تست زنده روی همین نماد",
                               "The Agents — live backtest on this symbol"))
        agent_cards = compute_agents(d)
        iframe_html(
            "<div style='background:#f6f8fb;margin:0;padding:2px;border-radius:14px'>"
            + build_agents_svg(agent_cards)
            + "</div>",
            height=520 if len(agent_cards) <= 6 else 730,
        )

st.caption("⏰ " + tr("آخرین به‌روزرسانی صفحه", "Page refreshed") + f": {time.strftime('%H:%M:%S')}")
