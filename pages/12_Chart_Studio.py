"""🎨 چارت‌استودیو — میزِ تحلیلِ اختصاصی — NorthmanQuant
================================================================
درخواستِ کاربر: «چارت جدا بشه، کلاً یک بخشِ جداگانه؛ خیلی پیشرفته‌تر؛
چیزی از تریدینگ‌ویو کم نداشته باشه.» این صفحه میزِ اختصاصیِ همان موتورِ
کاملِ چارت است (core/tv_chart.py — ۲۶ تایم‌فریم از ثانیه تا ماه، ۹ نوعِ
نمودار، ~۳۰ اندیکاتور، ابزارِ رسم با انتخاب/جابه‌جایی/واگرد، نواحی FVG/BVG،
آلرت، اسکرین‌شات، همگام‌سازیِ ابریِ رسم‌ها) + چیزهایی که صفحاتِ جاسازی‌شده
جایشان نبود:

  ▸ انتخابِ منبعِ کندل: Binance (مرجعِ بازار، باندلِ کامل + ثانیه‌ایِ مرورگر)
    یا کندلِ بومیِ هر ۸ صرافیِ رجیستری — قاعده‌ی «هر بخش، همه‌ی صرافی‌ها»
  ▸ واچ‌لیستِ شخصی (در session) — چیپ‌های جابه‌جاییِ سریعِ نماد
  ▸ خطوطِ پلنِ اتاقِ تیم روی چارت — ورود/حدضرر/هدف‌ها از همان ستاپِ واک‌فوروار-
    تأییدشده‌ای که حکم می‌دهد (بدونِ ادعای تازه؛ فقط نمایشِ همان مسیر)
  ▸ نوارِ وضعیتِ بازار — تیکِ زنده‌ی صرافی، RSI/ATR/فاصله از EMA50، تغییرِ ۲۴س
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from core.crypto_candles import candles_bundle, decimals_for as crypto_decimals
from core.exchanges import EXCHANGES_ALL
from core.help import hint
from core.i18n import setup_i18n, tr
from core.team_daily import CANDIDATES
from core.tv_chart import build_tv_chart_html
from core.webview import iframe_html

st.set_page_config(page_title="چارت‌استودیو | Chart Studio",
                   page_icon="🎨", layout="wide")
LANG = setup_i18n(page="p12")

VTF = ("15min", "1hour", "4hour", "1day")   # باندلِ بومیِ صرافی — چهار پنجره‌ی پرکاربرد
DEFAULT_WATCH = ["BTC-USDT", "ETH-USDT", "SOL-USDT", "XRP-USDT", "DOGE-USDT"]

st.session_state.setdefault("cs_watch", list(DEFAULT_WATCH))
st.session_state.setdefault("cs_sym", "BTC-USDT")


def _L(fa: str, en: str) -> str:
    return en if LANG == "en" else fa


def _norm_symbol(raw: str) -> str | None:
    s = str(raw or "").strip().upper().replace("/", "-").replace("_", "-")
    if not s:
        return None
    if "-" not in s:
        s = f"{s}-USDT"
    b, q = (s.split("-") + ["USDT"])[:2]
    return f"{b}-{q}" if b and q else None


def _rows_from_bundle(rows: list[list]) -> list[list]:
    """باندلِ Binance آماده است — فقط NaN → None."""
    out = []
    for a in rows:
        out.append([a[0]] + [(None if x is None or pd.isna(x) else float(x)) for x in a[1:6]])
    return out


def _rows_from_df(d: pd.DataFrame) -> list[list]:
    """dfِ بومیِ صرافی (time میلی‌ثانیه) → [t_s, o, h, l, c, v] با None."""
    out = []
    for r in d.itertuples(index=False):
        t = int(getattr(r, "time")) // 1000
        vals = []
        for name in ("open", "high", "low", "close", "volume"):
            x = getattr(r, name)
            vals.append(None if pd.isna(x) else float(x))
        out.append([t] + vals)
    return out


st.title("🎨 " + tr("چارت‌استودیو — میزِ تحلیلِ اختصاصی",
                    "Chart Studio — the dedicated analysis desk"))
hint(tr(
    "کلِ موتورِ چارت اینجاست، بدونِ شلوغیِ صفحه‌ی دیگر: ۲۶ تایم‌فریم (حتی ثانیه‌ای)، ۹ نوعِ نمودار، "
    "~۳۰ اندیکاتور با پنلِ جداگانه، ابزارِ رسم (خط روند، فیبوناچی، خط‌کش، پوزیشن با RR، پاک‌کن، واگرد)، "
    "نواحی FVG/BVG، آلرتِ قیمتی و ذخیره‌ی خودکارِ رسم‌ها در مرورگرِ خودت (به تفکیکِ نماد+تایم‌فریم). "
    "منبعِ کندل را می‌توانی Binance (مرجعِ بازار) یا کندلِ بومیِ هر صرافیِ رجیستری بگذاری؛ خطوطِ "
    "پلنِ اتاقِ تیم (ورود/حدضرر/هدف) هم اگر ستاپی فعال باشد روی چارت می‌نشیند.",
    "The full chart engine lives here: 26 timeframes (even 1s), 9 chart types, ~30 indicators with "
    "separate panes, drawing tools (trend, fib, ruler, position with RR, eraser, undo), FVG/BVG zones, "
    "price alerts and per-symbol+timeframe localStorage persistence. Candle source: Binance reference "
    "or native candles from any of the 8 registry venues; the team-room plan lines (entry/stop/targets) "
    "sit on the chart whenever a setup is active."))

# ── کنترل‌های نماد و منبع ─────────────────────────────────────────────────────
c1, c2, c3 = st.columns([2, 2, 3])
with c1:
    source = st.radio(
        tr("منبعِ کندل", "Candle source"),
        [tr("Binance — مرجعِ بازار", "Binance — market reference"),
         tr("کندلِ بومیِ صرافی", "Native venue candles")],
        index=0, horizontal=False)
    if source.startswith("Binance") or "Binance" in source:
        venue = "Binance"
    else:
        with c2:
            venue = st.selectbox(tr("صرافی", "Venue"), list(EXCHANGES_ALL))
with c2 if not (source.startswith("Binance") or "Binance" in source) else c3:
    quick = list(dict.fromkeys(list(CANDIDATES) + list(st.session_state.cs_watch)))
    sym_sel = st.selectbox(tr("نمادِ سریع", "Quick symbol"), quick,
                           index=quick.index(st.session_state.cs_sym)
                           if st.session_state.cs_sym in quick else 0)
with c3:
    sym_text = st.text_input(tr("یا نمادِ دلخواه (مثلاً TON-USDT)",
                                "or any symbol (e.g. TON-USDT)"), value="")
symbol = _norm_symbol(sym_text) or _norm_symbol(sym_sel) or "BTC-USDT"
st.session_state.cs_sym = symbol

# چیپ‌های واچ‌لیست — جابه‌جاییِ سریع (همان الگوی دکمه‌های تریدینگ‌ویو)
chip_cols = st.columns(max(1, len(st.session_state.cs_watch) + 1))
for i, w in enumerate(st.session_state.cs_watch):
    if chip_cols[i].button(w, key=f"chip:{w}",
                           type="primary" if w == symbol else "secondary"):
        st.session_state.cs_sym = w
        st.rerun()
if chip_cols[-1].button("➕ به واچ‌لیست", key="chip:add",
                        disabled=symbol in st.session_state.cs_watch):
    st.session_state.cs_watch.append(symbol)
    st.rerun()

# ── داده — باندلِ چندتایم‌فریمی ──────────────────────────────────────────────
from app_base import add_indicators, fetch_candles, fetch_tick, setup_plan  # noqa: E402

tfs: dict[str, list[list]] = {}
base_tf = "1hour"
venue_note = ""
if venue == "Binance":
    base = symbol.split("-")[0]
    bundle = candles_bundle(base)
    if bundle:
        tfs = {tf: _rows_from_bundle(rows) for tf, rows in bundle.items()}
        base_tf = "1hour" if "1hour" in tfs else next(iter(tfs))
    else:
        st.warning(tr("کندلِ Binance برای این نماد نیامد — شبکه یا لیست‌نبودنِ روی صرافی.",
                      "Binance candles unavailable for this symbol."))
else:
    for tf in VTF:
        try:
            d = fetch_candles(venue, symbol, tf, limit=400)
            if d is not None and len(d) >= 30:
                tfs[tf] = _rows_from_df(d)
        except Exception:  # noqa: BLE001 — یک تایم‌فریمِ خراب، استودیو را نمی‌بُرد
            continue
    if tfs:
        base_tf = "1hour" if "1hour" in tfs else next(iter(tfs))
        venue_note = tr(f"کندلِ بومیِ {venue} — پنجره‌های ۱۵د/۱س/۴س/۱D (سقفِ تاریخچه‌ی صرافی)",
                        f"native {venue} candles — 15m/1H/4H/1D (venue history cap)")

if not tfs:
    st.info(tr("کندل برای این نماد از هیچ منبعی نیامد — نمادِ دیگری امتحان کن.",
               "No candles from any source — try another symbol."))
    st.stop()

rows_base = tfs[base_tf]
last_px = rows_base[-1][4] or 0.0
df_i = add_indicators(pd.DataFrame(rows_base, columns=["time", "open", "high", "low", "close", "volume"]))

# ── نوارِ وضعیتِ بازار ───────────────────────────────────────────────────────
m = st.columns(6)
tick = None
try:
    tick = fetch_tick(venue if venue != "Binance" else "OKX", symbol)
except Exception:  # noqa: BLE001
    tick = None
row = df_i.iloc[-1]
sec = (rows_base[-1][0] - rows_base[-2][0]) if len(rows_base) > 1 else 3600
n24 = max(1, min(int(86400 / max(sec, 1)), len(rows_base) - 1))
px24 = rows_base[-1 - n24][4] if rows_base[-1 - n24][4] else last_px
chg24 = (last_px - px24) / px24 * 100.0 if px24 else None
rsi = row.get("rsi"); ema50 = row.get("ema50"); atr = row.get("atr")
m[0].metric(tr("تیکِ زنده‌ی صرافی", "Venue live tick"),
            f"{tick['price']:.{crypto_decimals(last_px)}f}" if tick and tick.get("price") else "—")
m[1].metric(tr("کلوزِ کندل", "Candle close"),
            f"{last_px:.{crypto_decimals(last_px)}f}")
m[2].metric(tr("تغییرِ ۲۴س (کندل)", "24h change (candles)"),
            f"{chg24:+.2f}٪" if chg24 is not None else "—")
m[3].metric("RSI 14", f"{rsi:.1f}" if pd.notna(rsi) else "—")
m[4].metric("ATR %", f"{(atr / last_px * 100.0):.2f}٪" if pd.notna(atr) and last_px else "—")
m[5].metric(tr("فاصله از EMA50", "Distance to EMA50"),
            f"{((last_px - ema50) / ema50 * 100.0):+.2f}٪" if pd.notna(ema50) and ema50 else "—")

# ── پلنِ اتاقِ تیم → خطوطِ چارت ──────────────────────────────────────────────
levels: list[dict] = []
plan = None
try:
    plan = setup_plan(df_i.copy())
except Exception:  # noqa: BLE001 — پلن نمایشی است؛ خرابی‌اش چارت را نمی‌بُرد
    plan = None
if plan and plan.get("status") == "active":
    e, s, tps = plan.get("entry"), plan.get("stop"), plan.get("targets") or []
    if e:
        levels.append({"price": float(e), "name": tr("ورود", "Entry"), "color": "#2962ff", "dash": False})
    if s:
        levels.append({"price": float(s), "name": tr("حدضرر", "Stop"), "color": "#ef5350", "dash": True})
    for i, t in enumerate(tps[:3]):
        levels.append({"price": float(t), "name": tr(f"هدفِ {i + 1}", f"TP{i + 1}"),
                       "color": "#26a69a", "dash": True})
    st.caption("🎯 " + tr(
        f"پلنِ فعالِ اتاق: {plan.get('direction')} · اطمینانِ {plan.get('confidence')}٪ — خطوطِ ورود/حدضرر/هدف روی چارت (خاموش‌کردن از منوی اندیکاتورها).",
        f"Active team plan: {plan.get('direction')} · confidence {plan.get('confidence')}% — entry/stop/target lines on the chart (toggle in indicator menu)."))
elif plan:
    st.caption("⏸ " + tr(
        f"ستاپِ فعالِ الان نیست — {str(plan.get('why', ''))[:110]}",
        f"No active setup — {str(plan.get('why', ''))[:110]}"))

# ── موتورِ کاملِ چارت ────────────────────────────────────────────────────────
if venue_note:
    st.caption("📌 " + venue_note)
iframe_html(
    build_tv_chart_html(
        candles=rows_base, tfs=tfs, base_tf=base_tf,
        symbol=f"{symbol.split('-')[0]}/USDT",
        zones=[], levels=levels,
        title=f"{symbol} · {venue} · {base_tf}",
        dec=crypto_decimals(last_px), initial_bars=400),
    height=880,
)

st.caption(tr(
    "💡 رسم‌ها و اندیکاتورها در localStorage مرورگرِ خودت ذخیره می‌شوند (به تفکیکِ نماد و تایم‌فریم)؛ "
    "دکمه‌ی ☁ اگر فعال باشد رسم‌ها را بینِ دستگاه‌ها همگام می‌کند. آلرتِ قیمتی از دکمه‌ی 🔔 داخلِ چارت.",
    "Drawings and indicators persist in your browser's localStorage (per symbol+timeframe); the ☁ button "
    "syncs drawings across devices when enabled. Price alerts via the 🔔 button inside the chart."))
