"""فارکس و بروکرها — قیمت زنده‌ی مِیجرها (یاهو) + چارت حرفه‌ای و آزمایشگاه ایجنت‌ها + مقایسه‌ی ۵ بروکر"""
from __future__ import annotations

import time

import pandas as pd
import streamlit as st

from core.webview import iframe_html

from app_base import (add_indicators, build_agents_svg, build_neural_shell_svg,
                      compute_agents, confluence, fvg_summary, make_plan,
                      signal_card_parts, signal_events, swing_levels)
from core import forex as F
from core.i18n import get_lang, setup_i18n, tr
from core.tv_chart import build_tv_chart_html

st.set_page_config(page_title="فارکس و بروکرها | Forex & Brokers", page_icon="💱", layout="wide")
setup_i18n(page="p3")

st.title("💱 " + tr("بازار فارکس و معرفی بروکرها", "Forex Market & Broker Guide"))
st.caption(tr(
    "قیمت زنده‌ی جفت‌ارزهای مِیجر از یاهو فایننس (منبع خنثی، میان‌دلالی) + چارت حرفه‌ای و آزمایشگاه ایجنت‌ها + "
    "مقایسه‌ی ۵ بروکر معتبر — قیمت هر بروکر فقط چند پیپ حول همین mid باز می‌شود.",
    "Live major-pair prices from Yahoo Finance (neutral mid-market source) plus a pro chart, the agents lab and a "
    "5-broker comparison — each broker quotes only a few pips around this mid."))

# ---------------------------------------------------------------------------
# ۱) قیمت زنده‌ی مِیجرها
# ---------------------------------------------------------------------------
st.subheader("🌍 " + tr("قیمت زنده‌ی مِیجرها", "Live Majors"))
c1, c2 = st.columns([1, 2])
with c1:
    refresh = st.select_slider(tr("سرعت بروزرسانی", "Refresh rate"),
                               options=[10, 30, 60], value=30,
                               format_func=lambda x: f"{x} {tr('ثانیه', 'sec')}")
with c2:
    auto = st.checkbox("🔄 " + tr("بروزرسانی خودکار", "Auto refresh"), value=True)
    manual = st.button("🔄 " + tr("دستی آپدیت کن", "Refresh now"))


def _fx_grid(force: bool = False) -> None:
    quotes = F.fx_quotes(force=force)
    en_now = get_lang() == "en"          # زنده — نه مقدار قدیمیِ ابتدای صفحه
    st.caption("⏰ " + tr("آخرین به‌روزرسانی", "Last update") + f": {time.strftime('%H:%M:%S')}")
    if not quotes:
        st.error(tr("قیمتی از یاهو گرفته نشد — چند لحظه بعد خودکار دوباره تلاش می‌شود.",
                    "No quotes from Yahoo right now — retrying automatically in a moment."))
        return
    cols = st.columns(len(F.PAIRS))
    for col, (pair, (fa, en)) in zip(cols, F.PAIRS.items()):
        d = quotes.get(pair)
        with col:
            st.metric(label=(en if en_now else fa), value=F.fmt_price(d["price"]) if d else "—",
                      delta=(f"{d['change_pct']:+.2f}%") if d else None,
                      delta_color="normal" if d else "off")
            st.caption(f"{pair} · " + (tr("۲۴ ساعت", "24h") if d else tr("بدون داده", "no data")))


_fx_grid(force=manual)
if auto and hasattr(st, "fragment"):
    st.fragment(run_every=refresh)(_fx_grid)()

# ---------------------------------------------------------------------------
# ۲) چارت حرفه‌ای + آزمایشگاه ایجنت‌ها روی فارکس
#    همان موتور تحلیل داشبورد کریپتو — این‌بار روی کندل یاهو فایننس
# ---------------------------------------------------------------------------
st.markdown("---")
st.subheader("📈 " + tr("چارت حرفه‌ای و آزمایشگاه ایجنت‌ها", "Pro Chart & The Agents Lab"))
st.caption(tr(
    "همان موتور تحلیل داشبورد کریپتو — این‌بار روی مِیجرهای فارکس: همگرایی اندیکاتورها، پوسته‌ی مدل‌ها، "
    "۸ ایجنت با بک‌تست زنده و طرح معامله‌ی اعتبارسنجی‌شده (walk-forward). سوئیچر تایم‌فریم داخل خود چارت است.",
    "The crypto dashboard's analysis engine — now on FX majors: indicator confluence, the neural shell, "
    "8 agents with a live backtest and a walk-forward-validated trade plan. Timeframes switch inside the chart."))

cA, cB, cC = st.columns([2, 2, 1])
_TF_LABELS = {"15min": ("۱۵ دقیقه", "15 min"), "1hour": ("۱ ساعت", "1 hour"),
              "4hour": ("۴ ساعت", "4 hours"), "1day": ("روزانه", "Daily")}


def _pair_label(p: str) -> str:
    fa, en = F.PAIRS.get(p, (p, p))
    return f"{p} — {en if get_lang() == 'en' else fa}"      # زبان زنده → بدون نشت در تغییر زبان


with cA:
    # کلید وابسته به زبان → با تغییر زبان ویجت دوباره ساخته می‌شود و
    # برچسب گزینه‌ها (نقص کشِ فرانت استریم‌لیت) همیشه با زبان فعلی می‌ماند
    pair = st.selectbox(tr("جفت‌ارز", "Pair"), list(F.PAIRS),
                        format_func=_pair_label, key=f"fx_pair_{get_lang()}")
with cB:
    tf_sel = st.selectbox(tr("تایم‌فریم تحلیل", "Analysis timeframe"),
                          list(_TF_LABELS), index=1, key=f"fx_tf_{get_lang()}",
                          format_func=lambda t: _TF_LABELS.get(t, (t, t))[1 if get_lang() == "en" else 0])
with cC:
    st.write("")
    fresh = st.button("🔄 " + tr("کندل تازه", "Fresh"), width="stretch")


def _score_label(s: float) -> str:
    if s > 40:
        return tr("خرید قوی", "Strong Buy")
    if s > 12:
        return tr("خرید", "Buy")
    if s > -12:
        return tr("خنثی", "Neutral")
    if s > -40:
        return tr("فروش", "Sell")
    return tr("فروش قوی", "Strong Sell")


def _dir_label(direction: str) -> str:
    if get_lang() != "en":
        return direction
    return ("LONG (Buy) 🟢" if str(direction).startswith("لانگ") else
            "SHORT (Sell) 🔴" if str(direction).startswith("شورت") else str(direction))


_EV_EN = {"ورود لانگ 🟢": "Long entry 🟢", "ورود شورت 🔴": "Short entry 🔴",
          "خروج از لانگ ◆": "Long exit ◆", "خروج از شورت ◆": "Short exit ◆"}

try:
    tfs = F.fx_candles(pair, force=fresh)
    base_rows = (tfs or {}).get(tf_sel)
    if not base_rows or not tfs:
        st.error(tr("کندل از یاهو گرفته نشد — چند لحظه بعد دوباره امتحان کن یا «کندل تازه» را بزن.",
                    "No candles from Yahoo right now — try again shortly or hit «Fresh»."))
    else:
        df = F.candles_to_df(base_rows)
        d = add_indicators(df)
        score_series, _comp = confluence(d)
        score = float(score_series.iloc[-1])
        levels = swing_levels(d)
        plan = make_plan(d, score, levels)
        events, state = signal_events(d, score_series)
        fvg_info = fvg_summary(d)
        price = float(d["close"].iloc[-1])
        dec = F.decimals_for(price)

        # ---- نوار متریک ----------------------------------------------------
        m1, m2, m3, m4 = st.columns(4)
        m1.metric(tr("قیمت لحظه‌ای", "Live price"), f"{price:,.{dec}f}")
        m2.metric(tr("همگرایی اندیکاتورها", "Indicator confluence"),
                  f"{score:+.0f} · {_score_label(score)}")
        m3.metric("ATR", f"{plan['atr']:,.{dec}f}" if plan.get("atr") else "—")
        _lbl4, _val4, _delta4 = signal_card_parts(state, get_lang())
        m4.metric(_lbl4, _val4, delta=_delta4)

        # ---- پوسته‌ی مدل‌ها (بالای چارت — مثل داشبورد) ----------------------
        iframe_html(
            "<div style='background:#f6f8fb;margin:0;padding:2px;border-radius:12px'>"
            + build_neural_shell_svg(_comp, score, fvg=fvg_info, price=price)
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
            build_tv_chart_html(candles=tfs[tf_sel], tfs=tfs, base_tf=tf_sel,
                                symbol=pair, zones=_tv_zones, levels=_tv_levels,
                                title=f"{pair} · {tf_sel}", dec=dec,
                                initial_bars=320, fx=True),
            height=760,
        )
        st.divider()

        # ---- دفتر ایجنت‌ها — بک‌تست زنده روی همین داده -----------------------
        st.subheader("◈ " + tr("دفتر ایجنت‌ها (The Agents) — بک‌تست زنده روی فارکس",
                               "The Agents — live backtest on FX"))
        agent_cards = compute_agents(d)
        iframe_html(
            "<div style='background:#f6f8fb;margin:0;padding:2px;border-radius:14px'>"
            + build_agents_svg(agent_cards)
            + "</div>",
            height=520 if len(agent_cards) <= 6 else 730,
        )
        st.divider()

        # ---- طرح معامله ------------------------------------------------------
        st.subheader("🎯 " + tr("طرح معامله — ستاپ اعتبارسنجی‌شده (walk-forward روی همین جفت‌ارز)",
                                "Trade plan — walk-forward-validated on this pair"))
        if plan.get("status") == "wait" or plan.get("entry") is None:
            _fa_view = get_lang() != "en"
            st.warning("⏸ **" + tr("بدون معامله.", "No trade.") + "** "
                       + (plan.get("why", "") if _fa_view else
                          tr("ستاپ هنوز معتبر نشده — شرایط ورود کامل نیست و موتور اجازه‌ی ورود نمی‌دهد.",
                             "The setup is not validated yet — entry conditions are incomplete, so the engine stays out.")))
            if _fa_view and plan.get("watch"):
                st.caption("چه چیزی لازم است: " + plan["watch"])
        else:
            p1, p2, p3, p4 = st.columns(4)
            _fa_view = get_lang() != "en"
            p1.metric(tr("جهت", "Direction"), _dir_label(plan["direction"]),
                      plan.get("mode_fa", "") if _fa_view else "", delta_color="off")
            p2.metric(tr("ورود", "Entry"), f"{plan['entry']:,.{dec}f}")
            p3.metric(tr("حد ضرر", "Stop"), f"{plan['stop']:,.{dec}f}",
                      f"{(plan['stop'] / plan['entry'] - 1) * 100:+.2f}%", delta_color="off")
            p4.metric(tr("احتمال TP1 قبل از SL (اندازه‌گیری‌شده)", "TP1-before-SL odds (measured)"),
                      f"{plan['confidence']}{'٪' if get_lang() != 'en' else '%'}",
                      f"R:R 1:{plan['rr']}", delta_color="off")
            tcols = st.columns(max(1, len(plan["targets"])))
            for _i, (_tp, _rr) in enumerate(plan["targets"]):
                tcols[_i].metric(f"{tr('هدف', 'Target')} {_i + 1}", f"{_tp:,.{dec}f}",
                                 f"{_rr}R", delta_color="off")
            st.caption("✅ " + (plan.get("why", "") + " · حد ضرر: " + plan.get("stop_why", "")
                                if get_lang() != "en" else
                                tr("ستاپ از همان موتور walk-forward داشبورد است؛ فقط وقتی اجازه‌ی معامله می‌دهد که در گذشته‌ی همین نماد آماره‌ی قابل‌اعتماد داشته باشد.",
                                   "The setup comes from the dashboard's walk-forward engine; it only allows a trade with trusted stats on this symbol's own past.")))
        if plan.get("fvg_note"):
            st.caption("🟪 FVG/BVG: " + plan["fvg_note"])
        st.divider()

        # ---- رویدادهای ورود/خروج ---------------------------------------------
        st.subheader("📜 " + tr("رویدادهای ورود/خروج همگرایی", "Confluence entry/exit events"))
        if events.empty:
            st.info(tr("در این بازه رویدادی ثبت نشده است.", "No events recorded in this window."))
        else:
            ev = events.tail(12).iloc[::-1].copy()
            if get_lang() == "en":
                ev["رویداد"] = ev["رویداد"].replace(_EV_EN)
                ev = ev.rename(columns={"زمان": "Time", "رویداد": "Event",
                                        "قیمت": "Price", "امتیاز": "Score"})
            st.dataframe(ev, width="stretch", hide_index=True)
        st.caption(tr(
            "داده: یاهو فایننس (میان‌دلالی، کش ۱۲۰ ثانیه‌ای) — بدون اسپرد/سوآپ بروکر. "
            "این ابزار توصیه‌ی سرمایه‌گذاری نیست.",
            "Data: Yahoo Finance (mid-market, 120s cache) — no broker spread/swap. "
            "This tool is not investment advice."))
except Exception:  # noqa: BLE001 — هیچ خطایی به UI نشت نمی‌کند (الگوی کل پروژه)
    st.error(tr("تحلیل این‌جا کامل نشد — داده‌ی یاهو شاید موقتاً ناقص باشد. چند لحظه بعد دوباره تلاش کن.",
                "Analysis did not complete — Yahoo data may be temporarily incomplete. Please retry in a moment."))

# ---------------------------------------------------------------------------
# ۳) چطور بروکر انتخاب کنیم؟
# ---------------------------------------------------------------------------
st.markdown("---")
st.subheader("🧭 " + tr("قبل از انتخاب بروکر به این‌ها نگاه کن", "What to check before picking a broker"))
st.info("\n".join([
    "• " + tr("**مدارک نظارتی نهادِ حساب** را چک کن — همان نهادی که پولت نزد اوست مهم است، نه نام بزرگ برند.",
              "Check the **regulation of the exact entity** holding your funds — not just the big brand name."),
    "• " + tr("هزینه واقعی = **اسپرد + کمیسیون** با هم؛ فقط «اسپرد از 0.0» را نبین.",
              "True cost = **spread + commission** together; don't just look at «from 0.0 pips»."),
    "• " + tr("اول **حساب دمو** بگیر و سرعت برداشت را با مبلغ کوچک تست کن.",
              "Start on a **demo**, then test withdrawal speed with a small amount."),
    "• " + tr("اهرم بالا = ریسک بالا؛ اهرمِ نهاد اروپایی/آمریکایی معمولاً محدودتر و امن‌تر است.",
              "High leverage = high risk; EU/US entities cap leverage (safer by design)."),
]))

# ---------------------------------------------------------------------------
# ۴) جدول مقایسه‌ی بروکرها
# ---------------------------------------------------------------------------
st.subheader("🏦 " + tr("مقایسه‌ی ۵ بروکر معتبر فارکس", "Trusted Forex Brokers Compared"))
st.markdown(F.broker_table_html(get_lang()), unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# ۵) سلب مسئولیت
# ---------------------------------------------------------------------------
st.warning(tr(
    "⚠️ قیمت‌ها و کندل‌ها میان‌دلالی یاهو فایننس است و شامل اسپرد/سوآپ بروکرها نیست؛ برای اجرای سفارش به پلتفرم بروکر خودت نگاه کن. "
    "نتایج بک‌تست آزمایشگاه بر پایه‌ی گذشته است و تضمین آینده نیست. اطلاعات جدول خلاصه و مخصوص معرفی است و ممکن است تغییر کند — "
    "قبل از افتتاح حساب از **سایت رسمی بروکر** تأیید بگیر. "
    "معامله با اهرم بالا ریسک از دست دادن کل سرمایه دارد و این صفحه توصیه‌ی سرمایه‌گذاری نیست.",
    "⚠️ Prices and candles are Yahoo's mid-market data and exclude broker spreads/swaps; check your own broker's platform for execution. "
    "Lab backtests are based on the past and guarantee nothing about the future. The table is a brief introduction and may change — "
    "always verify with the **broker's official site** before opening an account. "
    "Leveraged trading risks losing your entire capital; this page is not investment advice."),
)
