"""Live Trading with API Key - NorthmanQuant — v3 امن‌شده + چارت + Paper واقع‌گرا"""
import time

import streamlit as st
import streamlit.components.v1 as components
from core.i18n import setup_i18n, tr
from core import trade_guard as G
from core import trade_log as TL
from core import xlsx_export as XE
from core import crypto_candles as CC
from core import paper as PP
from core.tv_chart import build_tv_chart_html

try:
    from core import lighter as LIT   # لایتر: عمومیِ بدون‌کلید (پرپ DEX)
except Exception:                     # noqa: BLE001
    LIT = None

from core import lighter_real as LREAL   # سفارش واقعی لایتر با SDK رسمی (لازی؛ خودش import امن است)

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
st.session_state.setdefault("paper_bal", 10000.0)
st.session_state.setdefault("paper_pos", {})      # نماد → {"qty", "avg"}
st.session_state.setdefault("paper_realized", 0.0)
st.session_state.setdefault("amt_seq", 0)          # نسخه‌ی ورودی «مقدار» برای سایز سریع
st.session_state.setdefault("prc_seq", 0)          # نسخه‌ی ورودی «قیمت» برای پیش‌پرکردن


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
        api_key = api_secret = passphrase = ""
        lit_account = lit_key = ""
        lit_key_index = 0
        if is_real_new and ex_name == "Lighter":
            st.info(tr(
                "سفارش واقعی لایتر با **کلید API** کار می‌کند، نه کلید کیف‌پول: در lighter.xyz به Account ← API Keys برو، کلید بساز و «private key» نمایش‌داده‌شده را این‌جا بگذار. کلید API سفارش می‌گذارد ولی **برداشت نمی‌تواند** — برداشت فقط با امضای کیف‌پول است. تا وقتی صفحه باز است، کلید فقط در حافظه‌ی همین نشست می‌ماند.",
                "Real orders on Lighter use an **API key**, not the wallet key: on lighter.xyz go to Account ← API Keys, create one and paste the shown private key here. An API key can place orders but **cannot withdraw** (withdrawals need wallet signature). While this page is open, the key stays only in this session's memory."))
        if is_real_new and ex_name != "Lighter":
            k1, k2, k3 = st.columns(3)
            with k1:
                api_key = st.text_input("API Key", type="password")
            with k2:
                api_secret = st.text_input("API Secret", type="password")
            with k3:
                passphrase = st.text_input(
                    tr("Passphrase (KuCoin/OKX لازم دارند)", "Passphrase (required by KuCoin/OKX)"),
                    type="password")
        if is_real_new and ex_name == "Lighter":
            l1, l2, l3 = st.columns([1, 2, 1])
            with l1:
                lit_account = st.text_input(
                    tr("شماره‌ی حساب (Account Index)", "Account Index"),
                    help=tr("عدد کنار نام حساب در lighter.xyz — یا آدرس کیف‌پول را پایین بزن تا پیدایش کنیم.",
                            "The number next to your account name on lighter.xyz — or use the wallet-address lookup below."))
            with l2:
                lit_key = st.text_input("API Private Key", type="password")
            with l3:
                lit_key_index = st.number_input("Key Index", min_value=0, max_value=15, value=0, step=1)
            find_addr = st.text_input(
                tr("پیدا کردن شماره‌ی حساب از آدرس کیف‌پول (اختیاری)", "Find account index from wallet address (optional)"),
                placeholder="0x…")
            if st.button(tr("🔍 پیدا کردن شماره‌ی حساب", "🔍 Find account index")):
                found = LREAL.find_account_by_address(find_addr)
                if found is None:
                    st.warning(tr("حسابی برای این آدرس پیدا نشد.", "No account found for this address."))
                else:
                    st.success(tr(
                        f"حساب مادر: {found} — همین عدد را در «شماره‌ی حساب» بگذار.",
                        f"Master account: {found} — put this number in «Account Index»."))
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
            if not _sym_ok:
                pass
            elif is_real_new and ex_name == "Lighter":
                _ok, _msg = LREAL.check_connection(lit_account, lit_key, int(lit_key_index))
                if not _ok:
                    st.error(_msg)
                else:
                    st.session_state.trade_cfg = {
                        "ex": "Lighter", "key": "", "secret": "", "pass": "",
                        "symbol": _sym, "mode": "Real",
                        "account_index": int(lit_account),
                        "lit_key": lit_key.strip(), "lit_key_index": int(lit_key_index),
                    }
                    st.session_state.ts_activity = time.time()
                    st.session_state.pending_order = None
                    st.rerun()
            elif is_real_new and (not api_key or not api_secret):
                st.error(tr("برای حالت Real، کلید و رمز لازم است.",
                            "Real mode requires an API key and secret."))
            else:
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
        _top = LIT.book_top(cfg["symbol"]) if LIT is not None else None
        _sub = f"{_chg:+.2f}% · Mark {float(_tk.get('mark') or 0.0):,.4f}"
        if _top:
            tick["bid"], tick["ask"] = float(_top["bid"]), float(_top["ask"])
            _sub += tr(f" · بهترین Bid {float(_top['bid']):,.2f} / Ask {float(_top['ask']):,.2f}",
                       f" · best Bid {float(_top['bid']):,.2f} / Ask {float(_top['ask']):,.2f}")
        st.metric(tr(f"قیمت {cfg['symbol']} پرپ در Lighter",
                      f"{cfg['symbol']} perp price on Lighter"),
                  f"{_tk['last']:,.4f}",
                  _sub)
        # نرخ فاندینگ — تنها هزینه‌ی ماندن در پوزیشن پرپ؛ بدون کلید از API عمومی
        _mid = _tk.get("market_id")
        if _mid is not None:
            _fr = CC.funding_rate(int(_mid))
            if _fr is not None:
                st.caption(tr(f"💰 نرخ فاندینگ فعلی: {_fr * 100:+.4f}% (نرخِ خامِ هر بازه‌ی فاندینگ — بسته به جهت پوزیشن می‌پردازی یا می‌گیری)",
                              f"💰 Current funding rate: {_fr * 100:+.4f}% (raw rate per funding interval — you pay or receive depending on position side)"))
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

# ---------------------------------------------------------------- چارت مرجع (کندل Binance spot)
_chart_base = str(cfg.get("symbol") or "").split("/")[0].split("-")[0].strip().upper()
if _chart_base:
    with st.expander(tr("📈 چارت مرجع — موتور کامل (کندل از Binance spot)",
                        "📈 Reference chart — full engine (candles from Binance spot)"),
                     expanded=False):
        _cb = CC.candles_bundle(_chart_base)
        if not _cb:
            st.caption(tr("کندل گرفته نشد — احتمالاً این ارز روی Binance لیست نیست یا شبکه موقتاً کند است؛ قیمتِ زنده‌ی بالا مستقل کار می‌کند.",
                          "Could not fetch candles — the coin may not be listed on Binance, or the network is slow; the live price above works independently."))
        else:
            _btf = "1hour" if "1hour" in _cb else next(iter(_cb))
            _lpx = _cb[_btf][-1][4] if _cb[_btf] else 0.0
            components.html(
                build_tv_chart_html(candles=_cb[_btf], tfs=_cb, base_tf=_btf,
                                    symbol=str(cfg["symbol"]), zones=[], levels=[],
                                    title=f"{cfg['symbol']} · {_btf}",
                                    dec=CC.decimals_for(_lpx), initial_bars=320),
                height=640, scrolling=False,
            )

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
_lit_meta = None
if cfg.get("ex") == "Lighter" and LIT is not None:
    _lit_meta = LIT.market_meta(cfg["symbol"])
if _lit_meta:
    st.caption(tr(
        f"نماد {cfg['symbol']} در لایتر: حداقل مقدار {float(_lit_meta['min_base']):g} · حداقل ارزش {float(_lit_meta['min_quote']):g} USDT"
        + (tr(" · سفارش بازار با سپر لغزش ۰٫۵٪ فرستاده می‌شود (بدترین قیمت قابل‌قبول).",
              " · market orders are sent with a 0.5% slippage guard (worst acceptable price).")
           if is_real else "")))
o1, o2, o3, o4 = st.columns(4)

# سایز سریع: درصدی از سقفِ همین سفارش — فقط با قیمتِ زنده‌ی در دسترس
_price_est_now = float(tick.get("last") or 0.0) if tick else 0.0
if is_real and cap > 0 and _price_est_now > 0:
    st.caption(tr(f"⚡ سایز سریع از سقفِ همین سفارش ({cap:,.0f} USDT) — کلیک کن:",
                  f"⚡ Quick size from this order's cap ({cap:,.0f} USDT) — click:"))
    _qs = st.columns(4)
    for _i, _pct in enumerate((10, 25, 50, 100)):
        with _qs[_i]:
            if st.button(f"{_pct}%", use_container_width=True, key=f"qs_{_pct}"):
                _usd = cap * _pct / 100.0
                st.session_state["amt_preset"] = round(_usd / _price_est_now, 8)
                st.session_state["amt_seq"] = int(st.session_state.get("amt_seq", 0)) + 1
                st.rerun()
elif is_real:
    st.caption(tr("برای سایز سریع، قیمتِ زنده و سقفِ مثبت لازم است — اگر سقف صفر است، وضعیت دفتر را چک کن.",
                  "Quick sizing needs a live price and a positive cap — if the cap is zero, check the ledger status."))

with o1:
    side = st.selectbox(tr("جهت", "Side"), ["buy", "sell"])
with o2:
    otype = st.selectbox(tr("نوع", "Type"), ["market", "limit"])
with o3:
    amount = st.number_input("مقدار (ارز پایه)", min_value=0.0,
                             value=float(st.session_state.get("amt_preset") or 0.001),
                             format="%.8f", key=f"amt_{st.session_state.get('amt_seq', 0)}")
with o4:
    if st.button(tr("💡 قیمت لحظه‌ای", "💡 Use live price"), key="px_live_btn",
                 help=tr("قیمت لیمیت را با قیمتِ زنده‌ی همین لحظه پر می‌کند.",
                         "Fills the limit price with the current live price.")):
        if _price_est_now > 0:
            st.session_state["prc_preset"] = _price_est_now
            st.session_state["prc_seq"] = int(st.session_state.get("prc_seq", 0)) + 1
            st.rerun()
        else:
            st.warning(tr("قیمت زنده الان در دسترس نیست.", "Live price is unavailable right now."))
    price = st.number_input("قیمت لیمیت (فقط limit)", min_value=0.0,
                            value=float(st.session_state.get("prc_preset") or 0.0),
                            format="%.8f", key=f"prc_{st.session_state.get('prc_seq', 0)}")

_price_est = price if (otype == "limit" and price > 0) else _price_est_now
if amount > 0 and _price_est > 0:
    st.caption(tr(f"≈ ارزش سفارش: {amount * _price_est:,.2f} USDT",
                  f"≈ Order value: {amount * _price_est:,.2f} USDT"))

if is_real:
    agree = st.checkbox("می‌فهمم پول واقعی است و مسئولیت با من است")
else:
    agree = st.checkbox("شروع پیپر ترید (مجازی)")

if not is_real:
    st.info(tr(
        f"موجودی مجازی: {st.session_state.paper_bal:,.2f} USDT · "
        f"سود/زیان تحقق‌یافته: {float(st.session_state.get('paper_realized', 0.0)):+,.2f} USDT",
        f"Virtual balance: {st.session_state.paper_bal:,.2f} USDT · "
        f"realized PnL: {float(st.session_state.get('paper_realized', 0.0)):+,.2f} USDT"))
    if st.button("✅ اجرای سفارش مجازی", disabled=not agree):
        if tick is None:
            st.error(tr("قیمت زنده در دسترس نیست؛ سفارش مجازی ثبت نشد. صرافی/نماد را عوض کن یا دوباره «اتصال» بزن.",
                        "Live price unavailable; virtual order not placed. Change exchange/symbol or press «Connect» again."))
        else:
            _pos, _bal, _r, _msg = PP.apply_fill(
                st.session_state.paper_pos, side, cfg["symbol"], amount,
                float(tick["last"]), st.session_state.paper_bal)
            if _msg.startswith("✗"):
                st.error(_msg)
            else:
                st.session_state.paper_pos = _pos
                st.session_state.paper_bal = _bal
                st.session_state.paper_realized = float(st.session_state.get("paper_realized", 0.0)) + _r
                st.success(_msg)
                # ثبت در دفتر مشترک با mode=paper — خارج از سقف‌های واقعی، برای تاریخچه
                TL.log_real_order(exchange=cfg["ex"], symbol=cfg["symbol"], side=side,
                                  otype=otype, amount=amount, price=float(tick["last"]),
                                  notional_usd=amount * float(tick["last"]),
                                  order_id="paper", mode="paper")
                st.rerun()
    # پوزیشن‌های باز مجازی + سود/زیان بازِ نمادِ همین صفحه
    if st.session_state.paper_pos:
        st.caption(tr("📊 پوزیشن‌های باز مجازی (سود/زیان باز فقط برای نمادِ همین صفحه با قیمت زنده محاسبه می‌شود):",
                      "📊 Open virtual positions (unrealized PnL is computed only for this page's symbol with the live price):"))
        _rows = []
        for _sym, _p in st.session_state.paper_pos.items():
            _same = (_sym == str(cfg["symbol"]).strip().upper())
            _up = PP.unrealized_pnl(st.session_state.paper_pos, _sym,
                                    float(tick["last"]) if (tick and _same) else None)
            _rows.append({"نماد": _sym, "مقدار": f"{float(_p['qty']):g}",
                          "میانگین خرید": f"{float(_p['avg']):,.4f}",
                          "سود/زیان باز": (f"{_up:+,.2f} USDT" if _same else "—")})
        st.dataframe(_rows, use_container_width=True, hide_index=True)
        if st.button("🧹 صفر کردن حساب مجازی (بالانس ۱۰٬۰۰۰)", key="paper_reset"):
            st.session_state.paper_bal = 10000.0
            st.session_state.paper_pos = {}
            st.session_state.paper_realized = 0.0
            st.rerun()
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
                elif _lit_meta and otype == "limit" and price <= 0:
                    st.error(tr("برای سفارش limit قیمت را وارد کن.", "Enter a price for limit orders."))
                elif _lit_meta and amount < float(_lit_meta["min_base"]):
                    st.error(tr(
                        f"مقدار کمتر از حداقل بازار لایتر است: {cfg['symbol']} ≥ {float(_lit_meta['min_base']):g}",
                        f"Amount is below the Lighter market minimum: {cfg['symbol']} ≥ {float(_lit_meta['min_base']):g}"))
                elif _lit_meta and amount * price_est < float(_lit_meta["min_quote"]):
                    st.error(tr(
                        f"ارزش سفارش کمتر از حداقل بازار لایتر است: ≥ {float(_lit_meta['min_quote']):g} USDT",
                        f"Order value is below the Lighter market minimum: ≥ {float(_lit_meta['min_quote']):g} USDT"))
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
            if p["otype"] == "limit":
                price_now = p["price"]
            else:
                price_now = float(tick.get("last") or 0.0) if tick else 0.0
            # گارد دومرحله‌ای: سقف‌ها + جابه‌جایی قیمتِ بازار بین بررسی و تأیید
            _blocked = ""
            if p["otype"] == "market" and price_now <= 0:
                _blocked = tr(
                    "قیمت زنده الان در دسترس نیست — سفارش ارسال نشد؛ چند لحظه بعد دوباره «تأیید» بزن.",
                    "Live price is unavailable right now — order not sent; press «Confirm» again shortly.")
            else:
                ok, why = G.check_order(p["amount"], price_now, cap=cap_now, daily_spent=sp)
                if not ok:
                    _blocked = why
                    st.session_state.pending_order = None
                elif p["otype"] == "market":
                    _dok, _dwhy = G.price_drift_ok(p["price"], price_now)
                    if not _dok:
                        _blocked = _dwhy
                        st.session_state.pending_order = None
            if _blocked:
                st.error(_blocked)
            elif cfg["ex"] == "Lighter":
                # مسیر اختصاصی لایتر: SDK رسمی + کلید API (بدون ccxt)
                _meta = LIT.market_meta(p["symbol"]) if LIT is not None else None
                if _meta is None:
                    st.error(tr(
                        "متادیتای بازار لایتر گرفته نشد — دوباره «بررسی سفارش» بزن.",
                        "Could not fetch Lighter market metadata — press «Review order» again."))
                else:
                    _res = LREAL.submit_order(
                        account_index=cfg.get("account_index"),
                        api_key_private=cfg.get("lit_key") or "",
                        api_key_index=int(cfg.get("lit_key_index") or 0),
                        market_index=int(_meta["market_id"]),
                        size_decimals=int(_meta["size_decimals"]),
                        price_decimals=int(_meta["price_decimals"]),
                        order_kind=p["otype"], side=p["side"],
                        amount=float(p["amount"]),
                        price=float(p["price"] or 0.0),
                        last_price=float(tick["last"]) if tick else 0.0,
                    )
                    if not _res.get("ok"):
                        st.session_state.pending_order = None
                        st.error(_res.get("err") or tr("ارسال ناموفق بود.", "Submission failed."))
                    else:
                        _oid = str(_res.get("tx_hash") or f"cli-{_res.get('client_order_index')}")
                        st.success(tr("ثبت شد در لایتر: ", "Placed on Lighter: ") + (_oid[:66] or "—"))
                        st.json({"tx_hash": _res.get("tx_hash"),
                                 "client_order_index": _res.get("client_order_index"),
                                 "symbol": p["symbol"], "side": p["side"], "otype": p["otype"],
                                 "amount": p["amount"], "price_est": p["price"]})
                        logged = TL.log_real_order(
                            exchange="Lighter", symbol=p["symbol"], side=p["side"],
                            otype=p["otype"], amount=p["amount"], price=p["price"],
                            notional_usd=p["notional"], order_id=_oid)
                        if not logged:
                            st.error(tr(
                                "سفارش ثبت شد ولی در دفتر نیفتاد — تا رفع نشود، سفارش واقعی بعدی بسته می‌ماند (سقف قابل راستی‌آزمایی نیست).",
                                "The order was placed but could not be logged — until this is fixed, the next real order stays locked (caps can't be verified)."))
                            _store_setup_expander()
                        st.session_state.pending_order = None
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
if is_real and cfg.get("ex") == "Lighter":
    _acc = LREAL.account_summary(cfg.get("account_index"))
    if _acc is None:
        st.warning(tr(
            "حساب لایتر از API عمومی خوانده نشد — شماره‌ی حساب را چک کن یا دوباره بیا.",
            "Could not read the Lighter account from the public API — check the account index and retry."))
    else:
        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric(tr("وثیقه (Collateral)", "Collateral"), f"{_acc['collateral']:,.2f} USDT")
        with m2:
            st.metric(tr("قابل‌برداشت/آزاد", "Available"), f"{_acc['available']:,.2f} USDT")
        with m3:
            st.metric(tr("سفارش بازی", "Open orders"), f"{_acc['open_orders']}")
        st.caption(tr(
            "این داده از API عمومی لایتر خوانده می‌شود — بدون هیچ کلیدی (اطلاعات حساب روی لایتر عمومی است).",
            "Read from Lighter's public API — with no keys at all (account data on Lighter is public)."))
        if _acc["positions"]:
            st.dataframe(_acc["positions"], use_container_width=True)
        else:
            st.info(tr("پوزیشن بازی نداری.", "No open positions."))
        if st.button("🛑 لغو همه‌ی سفارش‌های باز در لایتر", type="secondary"):
            _cres = LREAL.cancel_all_orders(
                account_index=cfg.get("account_index"),
                api_key_private=cfg.get("lit_key") or "",
                api_key_index=int(cfg.get("lit_key_index") or 0))
            if _cres.get("ok"):
                st.success(tr("دستور لغو همه ثبت شد.", "Cancel-all submitted."))
            else:
                st.error(_cres.get("err") or tr("لغو ناموفق بود.", "Cancellation failed."))
elif is_real and cfg.get("key"):
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
    st.download_button("📗 " + tr("خروجی اکسل دفتر سفارش‌ها", "Ledger Excel export"),
                       data=XE.trade_log_workbook(_rows),
                       file_name="trade_log.xlsx", mime=XE.MIME, key="trade_log_xlsx",
                       help=tr("همه‌ی ستون‌ها (سقف روزانه و گرم‌کردن روی همین دفتر راستی‌آزمایی می‌شود) بدون فرمول.",
                               "Every column (daily cap and warm-up are audited from this ledger) — formula-free."))
elif TL.last_error:
    st.info(tr("دفتر در دسترس نیست؛ جزئیات بالا آمده است.",
               "The ledger is unavailable; details are shown above."))
else:
    st.info(tr("هنوز سفارش واقعی ثبت نشده.", "No real orders logged yet."))
_store_setup_expander()
