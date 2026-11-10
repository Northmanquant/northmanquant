"""Live Prices v4 - نمای کلی بازار + سرچ ارز + مقایسه صرافی‌ها + چارت کندل"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

import requests
import streamlit as st

from core.webview import iframe_html
from core.crypto_candles import candles_bundle, decimals_for as crypto_decimals
from core.help import hint
from core.i18n import setup_i18n, tr
from core.tv_chart import build_tv_chart_html


@st.cache_data(ttl=60, show_spinner=False)
def _arena_trades() -> list:
    """معامله‌های میدان برای پل «عقیده‌ی ایجنت‌ها» — کش ۶۰ثانیه‌ای، خرابی = []."""
    try:
        from core import arena_store as AST
        return AST.load_trades() or []
    except Exception:  # noqa: BLE001
        return []


def _dir_fa(d) -> str:
    try:
        d = int(d or 0)
    except (TypeError, ValueError):
        d = 0
    return "لانگ 🟢" if d > 0 else "شورت 🔴" if d < 0 else "—"


def _opinion_rows(ops: list) -> list[dict]:
    """آخرین معامله‌ی هر شرکت‌کننده روی نماد → جدول کوچک صادقانه."""
    out = []
    for t in ops:
        status = str(t.get("status") or "")
        if status == "open":
            state, r = "باز ⏳", "—"
        elif status == "closed":
            res = str(t.get("result") or "")
            state = {"win": "برد ✅", "loss": "باخت ❌"}.get(res, "سر‌به‌سر ⚪")
            try:
                r = f"{float(t.get('realized_r') or 0.0):+.2f}R"
            except (TypeError, ValueError):
                r = "—"
        else:
            state, r = "—", "—"
        out.append({"ایجنت": str(t.get("agent") or "—"),
                    "جهت": _dir_fa(t.get("direction")),
                    "وضعیت": state, "R خالص": r,
                    "ورود": f"{float(t.get('entry')):,.6g}" if t.get("entry") else "—"})
    return out

st.set_page_config(page_title="قیمت‌های زنده | Live Prices", page_icon="📊", layout="wide")
setup_i18n(page="p1")   # زبان + منوی ترجمه‌شده + پچ ترجمه‌ی کل صفحه
st.title("📊 قیمت‌های زنده بازار")
hint(tr("اول صرافی رو انتخاب کن، بعد ارز رو سرچ کن — مقایسه KuCoin + Binance + Bybit + OKX + Lighter",
        "Pick an exchange, search a coin — compare KuCoin + Binance + Bybit + OKX + Lighter"))

EXCHANGES = ["KuCoin", "OKX", "Binance", "Bybit", "Lighter", "XT", "LBank", "KCEX"]
COMPARE_EX = ["KuCoin", "Binance", "Bybit", "OKX", "Lighter"]   # KCEX از ابر/دیتاسنتر کلاً ۴۰۳ می‌دهد — حذف شد
HEADERS = {"User-Agent": "northmanquant-lite/1.0", "accept": "application/json"}


def _get_json(url: str, params: dict | None = None, timeout: float = 6):
    """GET → JSON یا None. هیچ‌وقت exception نمی‌دهد (پاسخ HTML/خالی/۴۰۳ = None).
    پشت‌صحنه از core/net با تلاش مجدد استفاده می‌کند (retries=1 تا UI کند نشود)."""
    from core.net import get_json as _retry_json
    try:
        return _retry_json(url, params=params, headers=HEADERS, timeout=timeout, retries=1)
    except Exception:  # noqa: BLE001
        return None


def _bybit_json(params: dict, timeout: float = 10):
    """Bybit از بعضی شبکه‌ها/ابرهای آمریکایی فیلتر می‌شود؛ بعد از شکست، دامنه‌ی جایگزینِ رسمی (bytick) هم امتحان می‌شود."""
    r = _get_json("https://api.bybit.com/v5/market/tickers", params, timeout=timeout)
    if isinstance(r, dict) and r.get("retCode") == 0:
        return r
    return _get_json("https://api.bytick.com/v5/market/tickers", params, timeout=timeout)


def _f(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


# ---------- لیست ارزهای هر صرافی (کش 10 دقیقه) ----------
@st.cache_data(ttl=600, show_spinner=False)
def get_symbols(exchange: str) -> list[str]:
    try:
        if exchange == "KuCoin":
            r = _get_json("https://api.kucoin.com/api/v1/market/allTickers", timeout=15) or {}
            tickers = (r.get("data") or {}).get("ticker") or []
            out = sorted([t["symbol"] for t in tickers if str(t.get("symbol", "")).endswith("-USDT")])
            return out or ["BTC-USDT", "ETH-USDT", "SOL-USDT"]
        if exchange == "Binance":
            r = _get_json("https://data-api.binance.vision/api/v3/ticker/24hr", timeout=15) or []
            out = []
            for t in r if isinstance(r, list) else []:
                s = str(t.get("symbol", ""))
                if s.endswith("USDT") and not s.endswith(("UPUSDT", "DOWNUSDT")):
                    out.append(f"{s[:-4]}-USDT")
            return sorted(out) or ["BTC-USDT", "ETH-USDT"]
        if exchange == "Bybit":
            r = _bybit_json({"category": "spot"}, timeout=15) or {}
            lst = (r.get("result") or {}).get("list") or []
            out = [f"{t['symbol'][:-4]}-USDT" for t in lst if str(t.get("symbol", "")).endswith("USDT")]
            return sorted(out) or ["BTC-USDT", "ETH-USDT"]
        if exchange == "OKX":
            r = _get_json("https://www.okx.com/api/v5/market/tickers", {"instType": "SPOT"}, timeout=15) or {}
            out = sorted([t["instId"] for t in (r.get("data") or []) if str(t.get("instId", "")).endswith("-USDT")])
            return out or ["BTC-USDT", "ETH-USDT"]
        if exchange == "Lighter":
            r = _get_json("https://mainnet.zklighter.elliot.ai/api/v1/orderBookDetails", timeout=20) or {}
            out = sorted([str(row.get("symbol", "")).upper() for row in (r.get("order_book_details") or [])
                          if row.get("symbol") and row.get("status") == "active"])
            return out or ["BTC", "ETH", "SOL"]
        if exchange == "KCEX":
            for url in ["https://api.kcex.com/api/v1/market/tickers", "https://api.kcex.com/api/v1/tickers"]:
                r = _get_json(url, timeout=10)
                data = r.get("data", r) if isinstance(r, dict) else r
                if isinstance(data, list) and data:
                    out = set()
                    for t in data:
                        s = str(t.get("symbol", "")).upper().replace("/", "-")
                        if "USDT" in s:
                            if "-" not in s:
                                s = s.replace("USDT", "-USDT")
                            out.add(s)
                    if out:
                        return sorted(out)
            return ["BTC-USDT", "ETH-USDT", "SOL-USDT", "XRP-USDT", "DOGE-USDT", "BNB-USDT"]
        if exchange in ("XT", "LBank"):
            import ccxt
            cid = "xt" if exchange == "XT" else "lbank"
            ex = getattr(ccxt, cid)({"enableRateLimit": True, "timeout": 15000})
            mk = ex.load_markets()
            out = sorted([s.replace("/", "-") for s in mk.keys() if s.endswith("/USDT")])
            return out or ["BTC-USDT", "ETH-USDT"]
    except Exception as e:  # noqa: BLE001
        print(f"symbols {exchange} err: {e}")
    return ["BTC-USDT", "ETH-USDT", "SOL-USDT"]


def parse_base(symbol_selected: str, main_ex: str) -> str:
    s = symbol_selected.strip().upper()
    if main_ex == "Lighter":
        return s.replace("-USDT", "").replace("/USDT", "").replace("USDT", "")
    if "-" in s:
        return s.split("-")[0]
    if "/" in s:
        return s.split("/")[0]
    if s.endswith("USDT"):
        return s[:-4]
    return s


# ---------- نمای کلی بازار (Binance spot — کش 60 ثانیه) ----------
_LEV_SUFFIX = ("UPUSDT", "DOWNUSDT", "BULLUSDT", "BEARUSDT")


@st.cache_data(ttl=60, show_spinner=False)
def _overview_rows() -> list[dict]:
    """یک درخواست 24hr کل بازار → ردیف‌های تمیز (بدون توکن‌های لوریج‌دار).
    خرابی = [] و UI صادقانه می‌گوید نمای کلی نیست."""
    r = _get_json("https://data-api.binance.vision/api/v3/ticker/24hr", timeout=12) or []
    out = []
    for t in r if isinstance(r, list) else []:
        s = str(t.get("symbol", ""))
        if not s.endswith("USDT") or s.endswith(_LEV_SUFFIX):
            continue
        last, chg = _f(t.get("lastPrice")), _f(t.get("priceChangePercent"))
        qv = _f(t.get("quoteVolume"))
        if last <= 0 or qv <= 0:
            continue
        out.append({"base": s[:-4], "last": last, "chg": chg, "qv": qv})
    return out


def _mover_table(rows: list[dict], title: str) -> None:
    if not rows:
        st.caption("—")
        return
    data = [{"ارز": r["base"], "قیمت": f"${r['last']:,.6g}",
             "۲۴ساعته": f"{r['chg']:+.2f}%"} for r in rows]
    st.caption(title)
    st.dataframe(data, width="stretch", hide_index=True, height=232)


# ---------------------------------------------------------------- نمای کلی بازار
with st.expander(tr("🌍 نمای کلی بازار — برنده‌ها · بازنده‌ها · پرحجم‌ترین‌ها (۲۴ ساعت)",
                    "🌍 Market overview — top gainers · losers · most active (24h)"),
                 expanded=True):
    _ov = _overview_rows()
    if not _ov:
        st.caption(tr("نمای کلی از Binance گرفته نشد — احتمالاً موقتی است؛ قیمت‌های پایین صفحه همچنان کار می‌کنند.",
                      "Overview feed from Binance failed — probably temporary; the live prices below still work."))
    else:
        _gain = sorted(_ov, key=lambda r: r["chg"], reverse=True)[:8]
        _lose = sorted(_ov, key=lambda r: r["chg"])[:8]
        _vol = sorted(_ov, key=lambda r: r["qv"], reverse=True)[:8]
        _g, _l, _v = st.columns(3)
        with _g:
            _mover_table(_gain, "🟢 " + tr("بیشترین رشد", "Top gainers"))
        with _l:
            _mover_table(_lose, "🔴 " + tr("بیشترین افت", "Top losers"))
        with _v:
            _mover_table(_vol, "💧 " + tr("پرحجم‌ترین‌ها", "Most active"))
        hint(tr("منبع: Binance spot · حجم دلاری ۲۴ ساعت — فقط برای جهت‌گیری؛ قیمتِ هر صرافی پایین‌تر زنده گرفته می‌شود.",
                "Source: Binance spot · 24h quote volume — for orientation only; per-exchange prices below are live."))

st.markdown("---")


@st.cache_data(ttl=2, show_spinner=False)
def _lighter_book() -> dict:
    """یک‌بار برای همه‌ی ارزها (نه یک درخواست سنگین به‌ازای هر ارز)."""
    r = _get_json("https://mainnet.zklighter.elliot.ai/api/v1/orderBookDetails", timeout=8) or {}
    out = {}
    for row in r.get("order_book_details") or []:
        sym = str(row.get("symbol", "")).upper()
        last = _f(row.get("last_trade_price")) or _f(row.get("mark_price"))
        if sym and last > 0:
            out[sym] = last
    return out


def fetch_price(target: str, base: str) -> dict | None:
    try:
        if target == "KuCoin":
            r = _get_json("https://api.kucoin.com/api/v1/market/orderbook/level1", {"symbol": f"{base}-USDT"}) or {}
            d = r.get("data") or {}
            last = _f(d.get("price"))
            if last > 0:
                return {"exchange": target, "last": last, "bid": _f(d.get("bestBid")), "ask": _f(d.get("bestAsk"))}
        elif target == "Binance":
            r = _get_json("https://data-api.binance.vision/api/v3/ticker/24hr", {"symbol": f"{base}USDT"}) or {}
            last = _f(r.get("lastPrice"))
            if last > 0:
                return {"exchange": target, "last": last, "bid": _f(r.get("bidPrice")), "ask": _f(r.get("askPrice")),
                        "change": _f(r.get("priceChangePercent"))}
        elif target == "Bybit":
            r = _bybit_json({"category": "spot", "symbol": f"{base}USDT"}) or {}
            row = ((r.get("result") or {}).get("list") or [{}])[0]
            last = _f(row.get("lastPrice"))
            if last > 0:
                return {"exchange": target, "last": last, "bid": _f(row.get("bid1Price")), "ask": _f(row.get("ask1Price")),
                        "change": _f(row.get("price24hPcnt")) * 100}
        elif target == "OKX":
            r = _get_json("https://www.okx.com/api/v5/market/ticker", {"instId": f"{base}-USDT"}) or {}
            row = (r.get("data") or [{}])[0]
            last = _f(row.get("last"))
            if last > 0:
                return {"exchange": target, "last": last, "bid": _f(row.get("bidPx")), "ask": _f(row.get("askPx"))}
        elif target == "KCEX":
            for url, params in [("https://api.kcex.com/api/v1/ticker", {"symbol": f"{base}-USDT"}),
                                ("https://api.kcex.com/api/v1/market/ticker", {"symbol": f"{base}USDT"})]:
                j = _get_json(url, params)
                if j is None:
                    continue
                d = j.get("data", j) if isinstance(j, dict) else {}
                if isinstance(d, list) and d:
                    d = d[0]
                if not isinstance(d, dict):
                    continue
                last = _f(d.get("last")) or _f(d.get("lastPrice")) or _f(d.get("price"))
                bid, ask = _f(d.get("buy")) or _f(d.get("bid")), _f(d.get("sell")) or _f(d.get("ask"))
                if last > 0 or (bid > 0 and ask > 0):
                    price = (bid + ask) / 2 if bid > 0 and ask > 0 else last
                    return {"exchange": target, "last": price, "bid": bid, "ask": ask}
        elif target == "Lighter":
            last = _lighter_book().get(base.upper(), 0.0)
            if last > 0:
                # bid/ask واقعی از دفتر سفارش؛ اگر دفتر نیامد، None — هرگز عدد ساختگی
                try:
                    from core import lighter as _lit
                    _top = _lit.book_top(base)
                except Exception:
                    _top = None
                if _top and _top.get("bid", 0) > 0 and _top.get("ask", 0) > 0:
                    return {"exchange": target, "last": last,
                            "bid": float(_top["bid"]), "ask": float(_top["ask"])}
                return {"exchange": target, "last": last, "bid": 0.0, "ask": 0.0}
    except Exception as e:  # noqa: BLE001
        print(f"price {target}/{base} err: {e}")
    return None


def fetch_all(base: str) -> dict:
    """قیمت همه‌ی صرافی‌ها هم‌زمان (حداکثر ~۶ ثانیه به‌جای ۳۶)."""
    with ThreadPoolExecutor(max_workers=len(COMPARE_EX)) as ex:
        results = list(ex.map(lambda t: fetch_price(t, base), COMPARE_EX))
    return {t: d for t, d in zip(COMPARE_EX, results) if d}


# ---------- UI ----------
c1, c2, c3 = st.columns([1.2, 1.5, 1.5])
with c1:
    main_ex = st.selectbox("🏦 صرافی (لیست ارز از اینجا میاد)", EXCHANGES, index=0)
with c2:
    refresh = st.select_slider("سرعت بروزرسانی", options=[1, 2, 3, 5, 10, 30], value=2, format_func=lambda x: f"{x} ثانیه")
with c3:
    auto = st.checkbox("🔄 بروزرسانی خودکار", value=True)
    manual = st.button("🔄 دستی آپدیت کن")

with st.spinner(f"در حال گرفتن لیست ارزهای {main_ex}..."):
    all_syms = get_symbols(main_ex)

if len(all_syms) <= 5:
    st.warning(f"⚠️ فهرست کامل {main_ex} گرفته نشد — فعلاً {len(all_syms)} نمادِ نمونه نشان داده می‌شود؛ "
               "چند لحظه بعد دوباره امتحان کن یا صرافی دیگری انتخاب کن.")
else:
    st.success(f"✅ {len(all_syms)} ارز در {main_ex} پیدا شد")

s1, s2 = st.columns([1, 2])
with s1:
    query = st.text_input("🔍 سرچ ارز", placeholder="مثلا BTC یا DOGE یا SOL...", value="")
with s2:
    if query:
        q = query.strip().upper()
        filtered = [s for s in all_syms if q in s.upper()]
        if not filtered:
            st.warning(f"چیزی با '{query}' پیدا نشد — همه رو نشون میدم")
            filtered = all_syms[:100]
        else:
            st.info(f"🔎 {len(filtered)} نتیجه برای '{query}'")
    else:
        popular = [s for s in ["BTC-USDT", "BTC", "ETH-USDT", "ETH", "SOL-USDT", "SOL", "XRP-USDT", "XRP",
                               "DOGE-USDT", "DOGE", "BNB-USDT"] if s in all_syms]
        rest = [s for s in all_syms if s not in popular][:90]
        filtered = popular + rest

default_sym = [filtered[0]] if filtered else []
selected = st.multiselect(f"ارزها (از {main_ex} انتخاب کن — حداکثر 5 تا)", options=filtered,
                          default=default_sym, max_selections=5)

st.markdown("---")
if not selected:
    st.info("👆 اول یه ارز رو سرچ و انتخاب کن")
    st.stop()


def _render_prices(selected: list[str], main_ex: str) -> None:
    st.caption(f"⏰ آخرین به‌روزرسانی: {time.strftime('%H:%M:%S')}")
    for sym_sel in selected:
        base = parse_base(sym_sel, main_ex)
        st.subheader(f"💎 {base} / USDT  (انتخاب از {main_ex}: {sym_sel})")
        prices = fetch_all(base)
        if not prices:
            st.error("قیمتی گرفته نشد — در به‌روزرسانی بعدی دوباره تلاش می‌شود")
            continue
        lasts = [v["last"] for v in prices.values() if v["last"] > 0]
        if len(lasts) >= 2:
            mn, mx = min(lasts), max(lasts)
            spread = (mx - mn) / mn * 100 if mn > 0 else 0
            if spread > 0.3:
                st.success(f"⚡ اختلاف **{spread:.3f}%** | کمترین ${mn:,.4f} | بیشترین ${mx:,.4f} — فرصت آربیتراژ!")
            else:
                st.info(f"📊 اختلاف **{spread:.3f}%** | ${mn:,.4f} تا ${mx:,.4f}")
        cols = st.columns(3)
        for i, exn in enumerate(COMPARE_EX):
            d = prices.get(exn)
            with cols[i % 3]:
                if d:
                    ch = d.get("change", 0)
                    st.metric(f"🏦 {exn}", f"${d['last']:,.4f}", delta=f"{ch:.2f}%" if ch else None)
                    if d.get("bid") and d.get("ask"):
                        st.caption(f"Bid ${d['bid']:,.4f} | Ask ${d['ask']:,.4f}")
                    else:
                        st.caption("Bid/Ask —")
                else:
                    st.caption(f"🔸 {exn}: این لحظه پاسخ نداد — در به‌روزرسانی بعدی دوباره تلاش می‌شود")
        st.markdown("---")


if auto and hasattr(st, "fragment"):
    # non-blocking auto refresh: only this block re-runs every `refresh` seconds
    st.fragment(run_every=refresh)(_render_prices)(selected, main_ex)
else:
    _render_prices(selected, main_ex)
    if auto:  # very old Streamlit without fragments → old behaviour
        time.sleep(refresh)
        st.rerun()


# ---------------------------------------------------------------- چارت کندل (خارج از فرگمنت)
st.markdown("---")
st.subheader(tr("📈 نمودار کندل — موتور کامل (تایم‌فریم · اندیکاتور · ابزار)",
                "📈 Candle chart — full engine (timeframes · indicators · tools)"))
_c1, _c2 = st.columns([2, 3])
with _c1:
    chart_sel = st.selectbox(tr("نمودار برای کدام ارز؟", "Chart which coin?"), selected,
                             help=tr("کندل از Binance spot می‌آید — مرجعِ بازار؛ قیمتِ صرافی‌ها بالایی زنده است.",
                                     "Candles come from Binance spot — the market reference; exchange prices above are live."))
chart_base = parse_base(chart_sel, main_ex)
_bundle = candles_bundle(chart_base)
if not _bundle:
    st.caption(tr(f"کندل برای {chart_base} از Binance گرفته نشد — احتمالاً این ارز روی Binance لیست نیست یا شبکه موقتاً کند است؛ مقایسه‌ی قیمت بالا همچنان کار می‌کند.",
                  f"Could not fetch candles for {chart_base} from Binance — the coin may not be listed there, or the network is slow; the price comparison above still works."))
else:
    _base_tf = "1hour" if "1hour" in _bundle else next(iter(_bundle))
    _last_px = _bundle[_base_tf][-1][4] if _bundle[_base_tf] else 0.0
    iframe_html(
        build_tv_chart_html(candles=_bundle[_base_tf], tfs=_bundle, base_tf=_base_tf,
                            symbol=f"{chart_base}/USDT", zones=[], levels=[],
                            title=f"{chart_base}/USDT · {_base_tf}",
                            dec=crypto_decimals(_last_px), initial_bars=320),
        height=700,
    )

# ---------------------------------------------------------------- عقیده‌ی میدان درباره‌ی همین ارز
with st.expander(tr("🏟️ عقیده‌ی میدان درباره‌ی همین ارز — آخرین معامله‌ی هر ایجنت",
                    "🏟️ What the arena thinks — each agent's latest trade on this coin"),
                 expanded=False):
    _ops = []
    try:
        from core import arena as AR
        _ops = AR.symbol_opinions(_arena_trades(), chart_base)
    except Exception:  # noqa: BLE001
        _ops = []
    if not _ops:
        st.caption(tr(
            "هنوز هیچ ایجنتی روی این نماد در میدان معامله باز/بسته نکرده — میدان هر ۳۰ دقیقه کل بازار را اسکن می‌کند و فقط برگزیدگانش را معامله می‌کند.",
            "No arena participant has traded this symbol yet — the arena rescans the whole market every 30 minutes and only trades its finalists."))
    else:
        st.dataframe(_opinion_rows(_ops), width="stretch", hide_index=True)
        hint(tr(
            "این‌ها معامله‌های کاغذیِ میدان روی داده‌ی واقعی‌اند (نه سفارش واقعی) — جزئیات کامل و جدول قهرمانی در «میدان ایجنت‌ها».",
            "These are the arena's paper trades on real data (not real orders) — full details and the championship table live on the «Agent Arena» page."))
