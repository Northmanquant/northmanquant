"""ماکت بورس ایران — ترید کاغذی با ۱۰۰ میلیون تومان مجازی
(بدون پول واقعی؛ ترید واقعیِ بورس فقط از طریق کارگزار ممکن است)"""
from __future__ import annotations

import time

import pandas as pd
import streamlit as st

from core import tse as T
from core import tse_paper as P
from core.i18n import get_lang, setup_i18n, tr

st.set_page_config(page_title="ماکت بورس | TSE Paper", page_icon="🧾", layout="wide")
setup_i18n(page="p7")

st.title("🧾 " + tr("ماکت بورس ایران — تمرین با پول مجازی",
                    "TSE Paper Trading — practice with virtual money"))
st.caption(tr(
    "۱۰۰ میلیون تومان مجازی · قیمت زنده/پایانی واقعی از TSETMC · کارمزد تقریبی واقعی (خرید ≈۰٫۳۷٪، فروش ≈۰٫۸۸٪ با مالیات) · "
    "پرتفوی تا پایان نشست می‌ماند · ترید واقعیِ بورس فقط از طریق کارگزار ممکن است — این‌جا فقط تمرینِ استراتژی است.",
    "Virtual 100M tomans · real live/close prices from TSETMC · realistic fees (buy ≈0.37%, sell ≈0.88% incl. tax) · "
    "the portfolio lives for this session · real TSE trading goes through a broker — this is strategy practice only."))

# ---------------------------------------------------------------- وضعیت نشست
st.session_state.setdefault("tse_paper", P.new_portfolio())
port = st.session_state.tse_paper


@st.cache_data(ttl=30, show_spinner=False)
def _snap(ins_code: str) -> dict:
    return T.snapshot(ins_code)


@st.cache_data(ttl=3600, show_spinner=False)
def _hist(ins_code: str) -> pd.DataFrame:
    return T.history(ins_code)


def _price_of(ins_code: str) -> tuple[float, bool]:
    """قیمت معامله: زنده (باز) یا آخرین قیمت پایانی. خروجی: (قیمت، زنده؟)"""
    snap = _snap(ins_code)
    if snap.get("last", 0) > 0:
        return float(snap["last"]), True
    df = _hist(ins_code)
    if not df.empty:
        return float(df["close"].iloc[-1]), False
    return 0.0, False


def _prices_map() -> dict[str, float]:
    out = {}
    for code in list((port.get("positions") or {}).keys()):
        px, _ = _price_of(code)
        if px > 0:
            out[code] = px
    return out


# ---------------------------------------------------------------- انتخاب نماد
st.subheader("🛒 " + tr("سفارش جدید", "New order"))
with st.container(border=True):
    c1, c2 = st.columns([2, 3])
    with c1:
        q = st.text_input(tr("نام نماد (مثل فولاد، وبملت، شپنا)",
                             "Symbol (e.g. فولاد, وبملت, شپنا)"), key="tse_paper_q")
    with c2:
        found = []
        if q.strip():
            found = T.search(q.strip())
            if not found:
                st.warning(tr("نمادی با این نام پیدا نشد.", "No symbol matched."))
        if found:
            opts = [f"{r['symbol']} — {r.get('name', '')}" for r in found]
            pick = st.selectbox(tr("نماد", "Symbol"), opts, key="tse_paper_pick")
            sel = found[opts.index(pick)]
        else:
            sel = None

    if sel is None:
        st.info(tr("اول یک نماد پیدا کن.", "Find a symbol first."))
    else:
        ins = sel["ins_code"]
        price, live = _price_of(ins)
        ss = T.session_status()
        if price <= 0:
            st.error(tr("قیمت این نماد گرفته نشد — چند لحظه بعد دوباره امتحان کن.",
                        "Price fetch failed — try again shortly."))
        else:
            st.caption(
                (tr("قیمت زنده", "Live price") if live else tr("آخرین قیمت پایانی", "Last close"))
                + f": **{price:,.0f} ریال**"
                + ("" if live else " · " + tr("بازار الان بسته است", "market is closed now")))

            b1, b2 = st.columns(2)
            with b1:
                st.markdown("**" + tr("🟢 خرید", "🟢 Buy") + "**")
                qty_b = st.number_input(tr("تعداد سهم", "Shares"), min_value=0,
                                        value=0, step=1, key="qty_b")
                fee_b = P.buy_fee(qty_b, price)
                st.caption(tr(f"هزینه‌ی کل با کارمزد: {(qty_b * price + fee_b):,.0f} ریال",
                              f"Total incl. fee: {(qty_b * price + fee_b):,.0f} rials"))
                if st.button("🟢 " + tr("خرید مجازی", "Virtual buy"),
                             type="primary", use_container_width=True,
                             disabled=qty_b <= 0):
                    ok, msg_fa, msg_en = P.apply_order(
                        port, "buy", ins, sel["symbol"], qty_b, price,
                        when=time.strftime("%Y-%m-%d %H:%M"))
                    (st.success if ok else st.error)(msg_fa if get_lang() != "en" else msg_en)
                    if ok:
                        st.rerun()
            with b2:
                st.markdown("**" + tr("🔴 فروش", "🔴 Sell") + "**")
                owned = (port.get("positions") or {}).get(ins)
                max_own = int(owned["qty"]) if owned else 0
                qty_s = st.number_input(tr("تعداد سهم", "Shares"), min_value=0,
                                        value=0, step=1, max_value=max_own or None,
                                        key="qty_s")
                fee_s = P.sell_fee(qty_s, price)
                st.caption(tr(f"عایدی خالص با کارمزد: {(qty_s * price - fee_s):,.0f} ریال",
                              f"Net proceeds: {(qty_s * price - fee_s):,.0f} rials"))
                if st.button("🔴 " + tr("فروش مجازی", "Virtual sell"),
                             use_container_width=True,
                             disabled=qty_s <= 0 or max_own <= 0):
                    ok, msg_fa, msg_en = P.apply_order(
                        port, "sell", ins, sel["symbol"], qty_s, price,
                        when=time.strftime("%Y-%m-%d %H:%M"))
                    (st.success if ok else st.error)(msg_fa if get_lang() != "en" else msg_en)
                    if ok:
                        st.rerun()
                if max_own <= 0:
                    st.caption(tr("این نماد را نداری.", "You don't own this symbol."))

st.divider()

# ---------------------------------------------------------------- پرتفوی
st.subheader("💼 " + tr("پرتفوی من", "My portfolio"))
prices = _prices_map()
sm = P.summary(port, prices)
s1, s2, s3, s4 = st.columns(4)
s1.metric(tr("نقد (تومان)", "Cash (toman)"), f"{sm['cash'] / 10:,.0f}")
s2.metric(tr("ارزش مبلغ‌ها (تومان)", "Positions (toman)"), f"{sm['positions_value'] / 10:,.0f}")
s3.metric(tr("ارزش کل (تومان)", "Equity (toman)"), f"{sm['equity'] / 10:,.0f}")
s4.metric(tr("سود/زیان", "P&L"), f"{sm['pnl'] / 10:,.0f}",
          f"{(sm['pnl'] / sm['start'] * 100.0) if sm.get('start') else 0.0:+.2f}%",
          delta_color="normal" if sm["pnl"] >= 0 else "inverse")

tbl = P.portfolio_table(port, prices)
if tbl.empty:
    st.info(tr("هنوز سهمی نداری — بالا یک نماد پیدا کن و اولین خرید مجازی را بزن.",
               "No positions yet — find a symbol above and place your first virtual buy."))
else:
    st.dataframe(tbl, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------- دفتر سفارش‌ها
st.divider()
st.subheader("🧾 " + tr("دفتر سفارش‌های مجازی", "Virtual order ledger"))
orders = list(reversed(port.get("orders", [])))
if not orders:
    st.caption(tr("هنوز سفارشی ثبت نشده.", "No orders yet."))
else:
    _o_rows = [{
        tr("زمان", "Time"): o.get("when", ""),
        tr("جهت", "Side"): ("خرید 🟢" if o["side"] == "buy" else "فروش 🔴") if get_lang() != "en"
        else ("Buy 🟢" if o["side"] == "buy" else "Sell 🔴"),
        tr("نماد", "Symbol"): o["symbol"],
        tr("تعداد", "Qty"): f"{o['qty']:,.0f}",
        tr("قیمت (ریال)", "Price (Rial)"): f"{o['price']:,.0f}",
        tr("کارمزد (ریال)", "Fee (Rial)"): f"{o['fee']:,.0f}",
    } for o in orders[:30]]
    st.dataframe(pd.DataFrame(_o_rows), use_container_width=True, hide_index=True)

# ---------------------------------------------------------------- شروع دوباره
st.divider()
r1, r2 = st.columns([4, 1])
with r1:
    st.caption(tr("پرتفوی ماکت فقط در همین نشست ذخیره می‌شود و با بستن مرورگر صفر می‌شود.",
                  "The paper portfolio lives only in this session and resets when the browser closes."))
with r2:
    if st.button("♻️ " + tr("شروع دوباره", "Reset"), use_container_width=True):
        st.session_state.tse_paper = P.new_portfolio()
        st.rerun()
