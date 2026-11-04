"""Live Trading with API Key - NorthmanQuant — v2 امن‌شده"""
import time

import streamlit as st
from core.i18n import setup_i18n, tr
from core import trade_guard as G
from core import trade_log as TL

try:
    from core import lighter as LIT   # لایتر: عمومیِ بدون‌کلید (پرپ DEX)
except Exception:                     # noqa: BLE001
    LIT = None

st.set_page_config(page_title="ترید مستقیم | Live Trading", page_icon="💹", layout="wide")
setup_i18n(page="p2")   # زبان + منوی ترجمه‌شده + پچ ترجمه‌ی کل صفحه
st.title("💹 ترید مستقیم — بدون رفتن به صرافی")
st.caption(tr(
    "کلیدها فقط در حافظه‌ی همین نشست می‌مانند و جایی ذخیره نمی‌شوند · سقف هر سفارش و سقف روزانه فعال است · بعد از ۳۰ دقیقه بی‌کاری، اتصال خودکار پاک می‌شود.",
    "Keys stay only in this session's memory and are never stored · per-order and daily caps are enforced · the connection auto-clears after 30 minutes of idle time."))

EX_MAP = {"KuCoin": "kucoin", "Binance": "binance", "Bybit": "bybit", "OKX": "okx",
          "XT": "xt", "LBank": "lbank", "Kraken": "kraken", "Gate": "gateio",
          "MEXC": "mexc", "Bitget": "bitget", "KCEX": "kcex", "Lighter": "lighter"}


def _venue_has(cid: str) -> bool:
    """ccxt واقعاً می‌شناسد، یا لایترِ اختصاصی ما در دسترس است (عمومیِ بدون‌کلید)."""
    if cid == "lighter":
        return LIT is not None
    try:
        import ccxt
        return hasattr(ccxt, cid)
    except Exception:
        return False


REAL_EX = G.filter_real_exchanges(EX_MAP, _venue_has)   # فقط صرافی‌هایی که واقعاً کار می‌کنند
if not REAL_EX:
    st.error(tr("کتابخانه‌ی ccxt در دسترس نیست؛ ترید مستقیم فعلاً غیرفعال است.",
                "The ccxt library is unavailable; direct trading is disabled for now."))
    st.stop()


# ---------------------------------------------------------------- وضعیت نشست
st.session_state.setdefault("trade_cfg", {})
st.session_state.setdefault("ts_activity", 0.0)
st.session_state.setdefault("pending_order", None)


def _clear_conn():
    st.session_state.trade_cfg = {}
    st.session_state.pending_order = None


def _watchdog():
    """پاک‌کردن اتصالِ بی‌کار با تایمر — حتی وقتی کاربر هیچ کلیدی نمی‌زند."""
    try:
        if st.session_state.get("trade_cfg") and G.expired(st.session_state.get("ts_activity")):
            _clear_conn()
    except Exception:
        pass


if hasattr(st, "fragment"):
    st.fragment(run_every=60)(_watchdog)()

# انقضای بی‌کاری: قبل از ثبت فعالیتِ رندر جدید بررسی شود
cfg = st.session_state.trade_cfg
if cfg and G.expired(st.session_state.ts_activity):
    _clear_conn()
    st.info(tr("⏱ اتصال بعد از ۳۰ دقیقه بی‌کاری پاک شد (امنیت).",
               "⏱ Connection cleared after 30 minutes of idle time (security)."))
    cfg = {}
if cfg:
    st.session_state.ts_activity = time.time()
    cfg = st.session_state.trade_cfg

is_real = bool(cfg) and str(cfg.get("mode", "")).startswith("Real")


def get_client():
    import ccxt
    if cfg.get("ex") == "Lighter":   # دفاعی: لایتر فقط Paper است
        st.error(tr("ترید واقعی روی Lighter فعال نیست؛ Paper آزاد است.",
                    "Real trading on Lighter is not enabled; Paper stays open."))
        st.stop()
    cid = EX_MAP.get(cfg["ex"])
    if not cid or not hasattr(ccxt, cid):
        st.error(tr("این صرافی در ccxt نیست؛ آن را قطع کن و صرافی دیگری انتخاب کن.",
                    "This exchange is not in ccxt; disconnect and pick another one."))
        st.stop()
    params = {"apiKey": cfg["key"], "secret": cfg["secret"], "enableRateLimit": True, "timeout": 20000}
    if cfg.get("pass"):
        params["password"] = cfg["pass"]
    ex = getattr(ccxt, cid)(params)
    try:
        ex.load_markets()
    except Exception as e:
        st.warning(tr("load_markets: ", "load_markets: ") + G.scrub(e, cfg.get("key"), cfg.get("secret")))
    return ex


def _caps_caption():
    st.caption(tr(
        f"🛡 سقف‌های سخت: هر سفارش ≤ {G.MAX_ORDER_USD:,.0f} USDT · مجموع روزانه ≤ {G.MAX_DAILY_USD:,.0f} USDT · "
        f"{G.WARMUP_ORDERS} سفارش واقعی اول ≤ {G.WARMUP_MAX_ORDER_USD:,.0f} USDT · "
        f"این سقف‌ها فقط از متغیر محیطی قابل تغییرند و از رابط قابل دور زدن نیستند.",
        f"🛡 Hard caps: per order ≤ {G.MAX_ORDER_USD:,.0f} USDT · daily total ≤ {G.MAX_DAILY_USD:,.0f} USDT · "
        f"first {G.WARMUP_ORDERS} real orders ≤ {G.WARMUP_MAX_ORDER_USD:,.0f} USDT · "
        f"caps can only be changed via environment variables, not from the UI."))


def _store_setup_expander():
    with st.expander(tr("راه‌اندازی جدول دفتر (یک‌بار در Supabase اجرا کن)",
                        "Ledger table setup (run once in Supabase)")):
        st.caption(tr(
            "این SQL جدول trade_log را با RLS می‌سازد. تا وقتی جدول نباشد، برای امنیت سفارشِ واقعی بسته است (Paper آزاد است).",
            "This SQL creates the trade_log table with RLS. Until the table exists, real orders stay locked for safety (Paper is open)."))
        st.code(TL.SETUP_SQL, language="sql")


# ---------------------------------------------------------------- کارت اتصال
if not cfg:
    st.info(tr("اول اتصال رو بزن. برای Paper نیازی به کلید نیست.",
               "Press Connect first. Paper mode needs no keys."))
    with st.container(border=True):
        st.subheader(tr("🔌 اتصال به صرافی", "🔌 Connect to an exchange"))
        m1, m2 = st.columns(2)
        with m1:
            mode = st.radio(tr("حالت", "Mode"),
                            ["Paper (مجازی برای تست)", "Real (پول واقعی)"],
                            horizontal=True, index=0)
        with m2:
            ex_name = st.selectbox(tr("صرافی", "Exchange"), REAL_EX, index=0, help=tr(
                "فقط صرافی‌هایی که واقعاً پشتیبانی می‌شوند در فهرست‌اند.",
                "Only exchanges that are actually supported are listed."))
        is_real_new = mode.startswith("Real")
        if is_real_new and ex_name == "Lighter":
            st.warning(tr(
                "Lighter فعلاً فقط Paper است (سفارش واقعی‌اش به SDK رسمی نیاز دارد) — برای Real صرافی دیگری انتخاب کن.",
                "Lighter is Paper-only for now (real orders need the official SDK) — pick another exchange for Real."))
        api_key = api_secret = passphrase = ""
        if is_real_new:
            k1, k2, k3 = st.columns(3)
            with k1:
                api_key = st.text_input("API Key", type="password")
            with k2:
                api_secret = st.text_input("API Secret", type="password")
            with k3:
                passphrase = st.text_input(
                    tr("Passphrase (KuCoin/OKX لازم دارند)", "Passphrase (required by KuCoin/OKX)"),
                    type="password")
        if ex_name == "Lighter":
            st.caption(tr(
                "Lighter پرپ DEX است — نمادها بدون USDT (مثل BTC، ETH).",
                "Lighter is a perp DEX — symbols have no USDT (e.g. BTC, ETH)."))
            _lit_syms = LIT.symbols() if LIT is not None else []
            if _lit_syms:
                st.caption("🟢 " + " · ".join(_lit_syms[:12]))
        symbol = st.text_input(
            tr("نماد پرپ (مثل BTC)", "Perp symbol (e.g. BTC)") if ex_name == "Lighter"
            else tr("نماد (ccxt فرمت)", "Symbol (ccxt format)"),
            value="BTC" if ex_name == "Lighter" else "BTC/USDT")
        _caps_caption()
        st.caption(tr(
            "⚠️ قانون طلایی: کلیدی که اجازه‌ی برداشت دارد را هرگز وارد نکن — فقط کلیدِ فقط-ترید در یک زیرحساب با موجودی کم.",
            "⚠️ Golden rule: never enter a key with withdrawal permission — use a trade-only key on a sub-account with a small balance."))
        if st.button("🔌 اتصال", type="primary"):
            if is_real_new and ex_name == "Lighter":
                st.error(tr(
                    "تریدِ واقعی روی Lighter هنوز فعال نیست — فعلاً با Paper امتحانش کن.",
                    "Real trading on Lighter is not enabled yet — try it with Paper for now."))
            elif is_real_new and (not api_key or not api_secret):
                st.error(tr("برای حالت Real، کلید و رمز لازم است.",
                            "Real mode requires an API key and secret."))
            else:
                _sym = (symbol or ("BTC" if ex_name == "Lighter" else "BTC/USDT")).strip()
                _sym_ok = True
                if ex_name == "Lighter" and LIT is not None:
                    _sym = LIT.normalize(_sym)
                    _known = LIT.symbols()
                    if _known and _sym not in _known:
                        st.error(tr(
                            f"نماد «{_sym}» روی Lighter پیدا نشد — یکی از این‌ها: " + " · ".join(_known[:12]),
                            f"Symbol «{_sym}» was not found on Lighter — use one of: " + " · ".join(_known[:12])))
                        _sym_ok = False
                if _sym_ok:
                    st.session_state.trade_cfg = {
                        "ex": ex_name, "key": api_key, "secret": api_secret,
                        "pass": passphrase, "symbol": _sym,
                        "mode": "Real" if is_real_new else "Paper",
                    }
                    st.session_state.ts_activity = time.time()
                    st.session_state.pending_order = None
                    st.rerun()
    _store_setup_expander()
    st.stop()

# ---------------------------------------------------------------- نوار وضعیت اتصال
b1, b2 = st.columns([4, 1])
with b1:
    st.success(tr(
        f"متصل: {cfg['ex']} · {cfg['symbol']} · حالت {cfg['mode']}",
        f"Connected: {cfg['ex']} · {cfg['symbol']} · {cfg['mode']} mode"))
with b2:
    if st.button(tr("⛔ قطع اتصال", "⛔ Disconnect"), use_container_width=True):
        _clear_conn()
        st.rerun()

# ---------------------------------------------------------------- قیمت زنده
tick = None
if cfg["ex"] == "Lighter":
    _tk = LIT.ticker(cfg["symbol"]) if LIT is not None else None
    if _tk is None:
        st.warning(tr("قیمت لایتر گرفته نشد؛ نماد را چک کن (مثل BTC) یا دوباره «اتصال» بزن.",
                      "Lighter price failed; check the symbol (e.g. BTC) or press «Connect» again."))
    else:
        tick = {"last": float(_tk["last"]), "bid": None, "ask": None}
        _chg = float(_tk.get("change_pct") or 0.0)
        st.metric(tr(f"قیمت {cfg['symbol']} پرپ در Lighter",
                      f"{cfg['symbol']} perp price on Lighter"),
                  f"{_tk['last']:,.4f}",
                  f"{_chg:+.2f}% · Mark {float(_tk.get('mark') or 0.0):,.4f}")
else:
    try:
        import ccxt
        _cid = EX_MAP.get(cfg["ex"])
        if not _cid or not hasattr(ccxt, _cid):
            raise RuntimeError(tr("این صرافی در ccxt پشتیبانی نمی‌شود",
                                  "this exchange is not supported by ccxt"))
        pub = getattr(ccxt, _cid)({"enableRateLimit": True, "timeout": 15000})
        tick = pub.fetch_ticker(cfg["symbol"])
        _last = tick.get("last") or tick.get("close") or 0
        if not _last:
            raise RuntimeError(tr("قیمت آخر خالی برگشت", "empty last price"))
        tick["last"] = float(_last)
        st.metric(tr(f"قیمت {cfg['symbol']} در {cfg['ex']}",
                      f"{cfg['symbol']} price on {cfg['ex']}"), f"{tick['last']:,.4f}",
                  f"Bid {tick.get('bid')} / Ask {tick.get('ask')}")
    except Exception as e:
        tick = None
        st.warning(tr("قیمت گرفته نشد: ", "Live price failed: ")
                   + G.scrub(e, cfg.get("key"), cfg.get("secret")))

# ---------------------------------------------------------------- گیت واقعی: دفتر + سقف‌ها
cap = 0.0
spent = 0.0
if is_real:
    warm = TL.count_real_orders()
    _sp = TL.todays_spent()
    store_ok = warm is not None and _sp is not None
    cap = G.order_cap(warm) if store_ok else 0.0
    spent = float(_sp) if (_sp is not None) else 0.0
    if not store_ok or cap <= 0:
        st.error(tr(
            "دفتر سفارش‌ها (Supabase) در دسترس نیست — برای امنیت، سفارشِ واقعی بسته است؛ Paper آزاد است.",
            "The order ledger (Supabase) is unavailable — for safety, real orders are locked; Paper stays open."))
        if TL.last_error and "تنظیم نشده" not in str(TL.last_error):
            # فقط خطاهای غیرِبدیهی را نشان بده (خطای «تنظیم نشده» خودِ پیام بالا توضیح می‌دهد)
            st.caption(G.scrub(TL.last_error, cfg.get("key"), cfg.get("secret")))
        _store_setup_expander()
    else:
        st.info(tr(
            f"🛡 سقف این سفارش: {cap:,.0f} USDT · مصرف امروز: {spent:,.2f} از {G.MAX_DAILY_USD:,.0f} USDT",
            f"🛡 Cap for this order: {cap:,.0f} USDT · used today: {spent:,.2f} of {G.MAX_DAILY_USD:,.0f} USDT"))
        if warm < G.WARMUP_ORDERS:
            st.caption(tr(
                f"دوره‌ی گرم‌کردن: {warm} از {G.WARMUP_ORDERS} سفارش واقعی اول با سقف {G.WARMUP_MAX_ORDER_USD:,.0f} USDT — بعدش سقف به {G.MAX_ORDER_USD:,.0f} USDT می‌رسد.",
                f"Warm-up: {warm} of first {G.WARMUP_ORDERS} real orders are capped at {G.WARMUP_MAX_ORDER_USD:,.0f} USDT — afterwards the cap rises to {G.MAX_ORDER_USD:,.0f} USDT."))

# ---------------------------------------------------------------- فرم سفارش
st.divider()
st.subheader("🛒 ثبت سفارش")
o1, o2, o3, o4 = st.columns(4)
with o1:
    side = st.selectbox(tr("جهت", "Side"), ["buy", "sell"])
with o2:
    otype = st.selectbox(tr("نوع", "Type"), ["market", "limit"])
with o3:
    amount = st.number_input("مقدار (ارز پایه)", min_value=0.0, value=0.001, format="%.6f")
with o4:
    price = st.number_input("قیمت لیمیت (فقط limit)", min_value=0.0, value=0.0)

if is_real:
    agree = st.checkbox("می‌فهمم پول واقعی است و مسئولیت با من است")
else:
    agree = st.checkbox("شروع پیپر ترید (مجازی)")

if not is_real:
    if "paper_bal" not in st.session_state:
        st.session_state.paper_bal = 10000.0
    st.info(f"موجودی مجازی: {st.session_state.paper_bal:,.2f} USDT")
    if st.button("✅ اجرای سفارش مجازی", disabled=not agree):
        if tick is None:
            st.error(tr("قیمت زنده در دسترس نیست؛ سفارش مجازی ثبت نشد. صرافی/نماد را عوض کن یا دوباره «اتصال» بزن.",
                        "Live price unavailable; virtual order not placed. Change exchange/symbol or press «Connect» again."))
        elif amount <= 0:
            st.error(tr("مقدار باید بزرگ‌تر از صفر باشد.", "Amount must be greater than zero."))
        else:
            last = float(tick["last"])
            cost = amount * last
            if side == "buy" and cost > st.session_state.paper_bal:
                st.error(f"موجودی مجازی کافی نیست: نیاز {cost:,.2f} · موجودی {st.session_state.paper_bal:,.2f}")
            else:
                st.session_state.paper_bal += -cost if side == "buy" else cost
                st.success(f"انجام شد در قیمت {last:,.4f} — بالانس جدید {st.session_state.paper_bal:,.2f}")
else:
    st.caption(tr(
        "سفارش واقعی دومرحله‌ای است: اول «بررسی سفارش»، بعد تأیید نهایی.",
        "Real orders are two-step: review first, then final confirm."))

    p = st.session_state.pending_order
    if p is None:
        if st.button(tr("🔎 بررسی سفارش", "🔎 Review order"), type="primary", disabled=not agree):
            if cap <= 0:
                st.error(tr(
                    "دفتر سفارش‌ها در دسترس نیست؛ برای امنیت، سفارش واقعی بسته است.",
                    "The order ledger is unavailable; real orders are locked for safety."))
            else:
                price_est = price if (otype == "limit" and price > 0) else (tick["last"] if tick else 0.0)
                if price_est <= 0:
                    st.error(tr(
                        "برای سفارش market باید قیمت زنده در دسترس باشد؛ برای limit قیمت را وارد کن.",
                        "Market orders need a live price; for limit orders enter the price."))
                else:
                    ok, why = G.check_order(amount, price_est, cap=cap, daily_spent=spent)
                    if ok:
                        st.session_state.pending_order = G.build_preview(
                            exchange=cfg["ex"], symbol=cfg["symbol"], side=side,
                            otype=otype, amount=amount, price=price_est, cap=cap)
                        st.rerun()
                    else:
                        st.error(why)
    elif G.preview_stale(p):
        st.session_state.pending_order = None
        st.warning(tr("پیش‌نمایش قدیمی شد؛ دوباره «بررسی سفارش» بزن.",
                      "The preview expired; press «Review order» again."))
    else:
        st.warning("⚠️ " + tr(G.preview_text(p), G.preview_text(p, en=True)))
        c_ok, c_no = st.columns(2)
        if c_no.button(tr("✖ انصراف", "✖ Cancel")):
            st.session_state.pending_order = None
            st.rerun()
        if c_ok.button(tr("✅ تأیید و ارسال سفارش واقعی", "✅ Confirm and send real order"), type="primary"):
            sp = TL.todays_spent()
            if sp is None:
                cap_now = 0.0
                sp = 0.0
            else:
                cap_now = cap
            price_now = p["price"] if p["otype"] == "limit" else (tick["last"] if tick else 0.0)
            ok, why = G.check_order(p["amount"], price_now, cap=cap_now, daily_spent=sp)
            if not ok:
                st.session_state.pending_order = None
                st.error(why)
            else:
                try:
                    client = get_client()
                    if p["otype"] == "market":
                        order = client.create_market_order(p["symbol"], p["side"], p["amount"])
                    else:
                        order = client.create_limit_order(p["symbol"], p["side"], p["amount"], p["price"])
                    oid = str(order.get("id") or "")
                    st.success(tr("ثبت شد: ", "Placed: ") + oid)
                    st.json(order)
                    logged = TL.log_real_order(
                        exchange=cfg["ex"], symbol=p["symbol"], side=p["side"],
                        otype=p["otype"], amount=p["amount"], price=p["price"],
                        notional_usd=p["notional"], order_id=oid)
                    if not logged:
                        st.error(tr(
                            "سفارش ثبت شد ولی در دفتر نیفتاد — تا رفع نشود، سفارش واقعی بعدی بسته می‌ماند (سقف قابل راستی‌آزمایی نیست).",
                            "The order was placed but could not be logged — until this is fixed, the next real order stays locked (caps can't be verified)."))
                        _store_setup_expander()
                    st.session_state.pending_order = None
                except Exception as e:
                    st.error(tr("خطا: ", "Error: ")
                             + G.scrub(e, cfg.get("key"), cfg.get("secret")))

# ---------------------------------------------------------------- سفارشات باز / بالانس (Real)
st.divider()
st.subheader("📋 سفارشات باز / بالانس (Real)")
if is_real and cfg.get("key"):
    cc1, cc2 = st.columns(2)
    with cc1:
        if st.button("💰 موجودی"):
            try:
                client = get_client()
                bal = client.fetch_balance()
                st.json({k: v for k, v in bal["total"].items() if v and v > 0})
            except Exception as e:
                st.error(G.scrub(e, cfg.get("key"), cfg.get("secret")))
    with cc2:
        if st.button("📄 سفارشات باز"):
            try:
                client = get_client()
                orders = client.fetch_open_orders(cfg["symbol"])
                if not orders:
                    st.info(tr("سفارش بازی نیست", "No open orders"))
                else:
                    st.dataframe(orders)
            except Exception as e:
                st.error(G.scrub(e, cfg.get("key"), cfg.get("secret")))
else:
    st.caption(tr("در حالت Paper بالانس/اوردر واقعی نداریم.",
                  "In Paper mode there is no real balance/orders."))

# ---------------------------------------------------------------- دفتر سفارش‌های واقعی
st.divider()
st.subheader(tr("🧾 دفتر سفارش‌های واقعی", "🧾 Real order ledger"))
st.caption(tr(
    "هر سفارش واقعی بدون هیچ کلیدی این‌جا ثبت می‌شود — پایه‌ی سقف روزانه و دوره‌ی گرم‌کردن.",
    "Every real order is logged here without any keys — the basis of the daily cap and warm-up period."))
_rows = TL.recent(20)
if _rows:
    st.dataframe(_rows, use_container_width=True)
elif TL.last_error:
    st.info(tr("دفتر در دسترس نیست؛ جزئیات بالا آمده است.",
               "The ledger is unavailable; details are shown above."))
else:
    st.info(tr("هنوز سفارش واقعی ثبت نشده.", "No real orders logged yet."))
_store_setup_expander()
