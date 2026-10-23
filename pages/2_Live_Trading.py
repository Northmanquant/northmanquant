"""Live Trading with API Key - NorthmanQuant"""
import streamlit as st
from core.i18n import setup_i18n

st.set_page_config(page_title="Live Trading", page_icon="💹", layout="wide")
setup_i18n(page="p2")   # زبان + منوی ترجمه‌شده + پچ ترجمه‌ی کل صفحه
st.title("💹 ترید مستقیم — بدون رفتن به صرافی")
st.caption("کلیدها فقط در حافظه مرورگر شما (session) می‌ماند و در گیت‌هاب ذخیره نمی‌شود.")

EX_MAP = {"KuCoin":"kucoin","Binance":"binance","Bybit":"bybit","OKX":"okx","KCEX":"kcex","XT":"xt","LBank":"lbank","Kraken":"kraken","Gate":"gateio","MEXC":"mexc","Bitget":"bitget"}

if "trade_cfg" not in st.session_state:
    st.session_state.trade_cfg = {}

c1,c2,c3 = st.columns(3)
with c1:
    ex_name = st.selectbox("صرافی", list(EX_MAP.keys()), index=0,
                           help="KCEX در کتابخانه‌ی ccxt پشتیبانی نمی‌شود؛ برای ترید واقعی KuCoin/OKX/Bybit/Binance را انتخاب کن.")
with c2:
    api_key = st.text_input("API Key", type="password")
with c3:
    api_secret = st.text_input("API Secret", type="password")
passphrase = st.text_input("Passphrase (اگه صرافی می‌خواد مثل KCEX/KuCoin/OKX)", type="password")

col_a,col_b = st.columns(2)
with col_a:
    symbol = st.text_input("نماد (ccxt فرمت)", value="BTC/USDT", help="مثل BTC/USDT")
with col_b:
    mode = st.radio("حالت", ["Paper (مجازی برای تست)", "Real (پول واقعی)"], horizontal=True)

if st.button("🔌 اتصال", type="primary"):
    st.session_state.trade_cfg = {"ex":ex_name,"key":api_key,"secret":api_secret,"pass":passphrase,"symbol":symbol,"mode":mode}
    st.success("ذخیره شد در session")

cfg = st.session_state.trade_cfg
if not cfg:
    st.info("اول اتصال رو بزن. برای Paper نیازی به کلید نیست.")
    st.stop()

def get_client():
    import ccxt
    cid = EX_MAP[cfg["ex"]]
    if not hasattr(ccxt, cid):
        st.error(f"صرافی {cfg['ex']} در ccxt نیست")
        st.stop()
    params = {"apiKey": cfg["key"], "secret": cfg["secret"], "enableRateLimit": True, "timeout":20000}
    if cfg.get("pass"):
        params["password"] = cfg["pass"]
    ex = getattr(ccxt, cid)(params)
    # برای اسپات
    try:
        ex.load_markets()
    except Exception as e:
        st.warning(f"load_markets: {e}")
    return ex

# قیمت زنده
tick = None  # BUGFIX: قبلاً اگر قیمت گرفته نمی‌شد، tick تعریف نمی‌شد و سفارش مجازی NameError می‌داد
try:
    import ccxt
    _cid = EX_MAP[cfg["ex"]]
    if not hasattr(ccxt, _cid):
        raise RuntimeError(f"صرافی {cfg['ex']} در ccxt پشتیبانی نمی‌شود — صرافی دیگری انتخاب کن")
    pub = getattr(ccxt, _cid)({"enableRateLimit": True, "timeout": 15000})
    tick = pub.fetch_ticker(cfg["symbol"])
    _last = tick.get("last") or tick.get("close") or 0
    if not _last:
        raise RuntimeError("قیمت آخر خالی برگشت")
    tick["last"] = float(_last)
    st.metric(f"قیمت {cfg['symbol']} در {cfg['ex']}", f"{tick['last']:,.4f}", f"Bid {tick.get('bid')} / Ask {tick.get('ask')}")
except Exception as e:
    tick = None
    st.warning(f"قیمت گرفته نشد: {e}")

st.divider()
st.subheader("🛒 ثبت سفارش")
o1,o2,o3,o4 = st.columns(4)
with o1:
    side = st.selectbox("جهت", ["buy","sell"])
with o2:
    otype = st.selectbox("نوع", ["market","limit"])
with o3:
    amount = st.number_input("مقدار (ارز پایه)", min_value=0.0, value=0.001, format="%.6f")
with o4:
    price = st.number_input("قیمت لیمیت (فقط limit)", min_value=0.0, value=0.0)

agree = st.checkbox("می‌فهمم پول واقعی است و مسئولیت با من است" if cfg["mode"].startswith("Real") else "شروع پیپر ترید (مجازی)")
if cfg["mode"].startswith("Paper"):
    if "paper_bal" not in st.session_state:
        st.session_state.paper_bal = 10000.0
    st.info(f"موجودی مجازی: {st.session_state.paper_bal:,.2f} USDT")
    if st.button("✅ اجرای سفارش مجازی", disabled=not agree):
        if tick is None:
            st.error("قیمت زنده در دسترس نیست؛ سفارش مجازی ثبت نشد. صرافی/نماد را عوض کن یا دوباره «اتصال» بزن.")
        elif amount <= 0:
            st.error("مقدار باید بزرگ‌تر از صفر باشد.")
        else:
            last = float(tick["last"])
            cost = amount * last
            if side == "buy" and cost > st.session_state.paper_bal:
                st.error(f"موجودی مجازی کافی نیست: نیاز {cost:,.2f} · موجودی {st.session_state.paper_bal:,.2f}")
            else:
                st.session_state.paper_bal += -cost if side == "buy" else cost
                st.success(f"انجام شد در قیمت {last:,.4f} — بالانس جدید {st.session_state.paper_bal:,.2f}")
else:
    if st.button("✅ ارسال سفارش واقعی", type="primary", disabled=not agree):
        if not cfg["key"] or not cfg["secret"]:
            st.error("کلید وارد کن")
            st.stop()
        try:
            client = get_client()
            if otype=="market":
                order = client.create_market_order(cfg["symbol"], side, amount)
            else:
                if price<=0:
                    st.error("قیمت لیمیت بده")
                    st.stop()
                order = client.create_limit_order(cfg["symbol"], side, amount, price)
            st.success(f"ثبت شد: {order.get('id')}")
            st.json(order)
        except Exception as e:
            st.error(f"خطا: {e}")

st.divider()
st.subheader("📋 سفارشات باز / بالانس (Real)")
if cfg["mode"].startswith("Real") and cfg["key"]:
    cc1,cc2 = st.columns(2)
    with cc1:
        if st.button("💰 موجودی"):
            try:
                client = get_client()
                bal = client.fetch_balance()
                st.json({k:v for k,v in bal["total"].items() if v and v>0})
            except Exception as e:
                st.error(str(e))
    with cc2:
        if st.button("📄 سفارشات باز"):
            try:
                client = get_client()
                orders = client.fetch_open_orders(cfg["symbol"])
                if not orders:
                    st.info("سفارش بازی نیست")
                else:
                    st.dataframe(orders)
            except Exception as e:
                st.error(str(e))
else:
    st.caption("در حالت Paper بالانس/اوردر واقعی نداریم.")
