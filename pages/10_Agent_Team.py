# -*- coding: utf-8 -*-
"""اتاقِ تیمِ تحلیل 🤝 — پنج عامل + شاهدِ کرونوس، سرِ یک ارز
====================================================
درخواستِ کاربر: یک بخشِ جدا از همه‌چیز — تیمی که سرِ یک ارز جلسه می‌گذارد:
  📰 خبرنگار   → چرا قیمت تکون می‌خورد؟ (تیترِ واقعی + داده)
  👁️ دیدبان    → دنبال حجمِ مشکوک می‌گردد (اسپایک / churn / فشارِ پنهان)
  📊 چارت‌خوان → ورود/حدضرر/اهداف از موتورِ QC-دارِ اپ
  💼 مدیرِ ریسک → اندازه‌ی پوزیشن از سرمایه‌ی تو (قانونِ ۱–۲٪ + کارمزد، بدونِ اهرم)
  🔮 کرونوس    → شاهدِ احتمالاتی (فازِ یکِ نقشه‌راه — حالتِ سایه): توزیعِ مسیرها +
                 باندِ چارکی؛ روی حکمِ تیم اثری ندارد تا دروازه‌ی ۲۰۰ جلسه‌ای پر شود
  🧐 شکاک      → هر ادعا را محک می‌زند — حتی ریاضیاتِ مدیرِ ریسک را بازمحاسبه می‌کند
حکمِ نهایی فقط وقتی «هم‌نظمی» است که شکاک اعتراضِ سخت نداشته باشد."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from core import team_room as TR
from core import kronos_witness as KW
from core.help import hint
from core.i18n import setup_i18n

st.set_page_config(page_title="اتاق تیم | Agent Team", page_icon="🤝", layout="wide")
setup_i18n(page="p10")

st.title("🤝 اتاقِ تیمِ تحلیل — پنج عامل + شاهدِ کرونوس، سرِ یک ارز")
hint("هر عامل مسئولیتِ خودش را دارد و همیشه «مدرک» می‌آورد: خبرنگار می‌گوید حرکت از خبر است یا "
     "از پول؛ دیدبان دنبال حجمِ مشکوک می‌گردد؛ چارت‌خوان فقط از موتورِ QC-دارِ خودِ اپ ورود/خروج "
     "می‌دهد؛ مدیرِ ریسک با قانونِ ۱–۲٪ اندازه‌ی پوزیشن را از سرمایه‌ی تو حساب می‌کند (بدون اهرم، "
     "با احتسابِ کارمزد)؛ کرونوس به‌عنوان شاهدِ ششم فقط آمارِ احتمالاتیِ مسیرها می‌دهد و در حالتِ "
     "سایه روی حکم اثری ندارد؛ و شکاک ادعای همه را با داده محک می‌زند — اعتراضِ شکاک یعنی معامله "
     "ممنوع. این اتاق از خودِ ارزهای بی‌نام و نقش خبر ندارد؛ هر جلسه روی داده‌ی زنده‌ی صرافی اجرا می‌شود.")

# ----------------------------------------------------------------- کنترل‌ها
QUICK = {"BTC": "BTC-USDT", "ETH": "ETH-USDT", "SOL": "SOL-USDT", "XRP": "XRP-USDT",
         "DOGE": "DOGE-USDT", "AVAX": "AVAX-USDT", "LINK": "LINK-USDT", "TON": "TON-USDT"}
EXCHANGES = ["OKX", "KuCoin"]

c1, c2, c3, c4 = st.columns([1.0, 1.6, 1.0, 1.4])
with c1:
    exchange = st.selectbox("صرافی", EXCHANGES, index=0)
with c2:
    symbol = st.text_input("نماد", value=st.session_state.get("team_symbol", "BTC-USDT"))
with c3:
    interval = st.selectbox("تایم‌فریم", TR.INTERVALS, index=0)
with c4:
    with_news = st.toggle("خبر هم بگیر (RSS واقعی)", value=True)

c5, c6, c7, c8 = st.columns([1.1, 1.5, 1.3, 1.9])
with c5:
    capital = st.number_input("سرمایه ($)", min_value=10.0, step=50.0,
                              value=float(st.session_state.get("team_capital", 1000.0)))
with c6:
    risk_pct = st.slider("ریسکِ هر معامله (٪ سرمایه)", 0.25, 5.0,
                         float(st.session_state.get("team_risk_pct", 1.0)), 0.25, format="%.2f")
with c7:
    with_witness = st.toggle("🔮 شاهدِ کرونوس (حالتِ سایه)",
                             value=st.session_state.get("team_witness", True),
                             help="شاهدِ احتمالاتی از نقشه‌راهِ گزارشِ کرونوس: توزیعِ مسیرها + "
                                  "باندِ چارکی؛ روی حکمِ تیم اثری ندارد تا دروازه‌ی هم‌جهتیِ "
                                  "۵۵٪ روی ۲۰۰ جلسه پر شود.")
with c8:
    st.caption(f"قانونِ مدیرِ ریسک: حداکثر **{capital * risk_pct / 100.0:,.2f}$** در خطر در هر معامله — "
               "بالای ۳٪ را شکاک اعتراض می‌کند.")
st.session_state["team_capital"] = float(capital)
st.session_state["team_risk_pct"] = float(risk_pct)
st.session_state["team_witness"] = bool(with_witness)

chips = st.columns(len(QUICK))
for i, (k, sym) in enumerate(QUICK.items()):
    if chips[i].button(k, key=f"team_{k}", use_container_width=True):
        st.session_state["team_symbol"] = sym
        st.rerun()

if st.button("🎙 شروعِ جلسه‌ی تیم", type="primary", use_container_width=True):
    st.session_state["team_symbol"] = symbol
    with st.spinner("عامل‌ها سرِ کارند — داده‌ی زنده + خبر + بازرسیِ شکاک + مسیرهای شاهد…"):
        room_new = TR.investigate(exchange=exchange, symbol=symbol, interval=interval,
                                  with_news=with_news, capital=float(capital),
                                  risk_pct=float(risk_pct), with_witness=bool(with_witness))
    if room_new.get("ok"):
        KW.log_session(room_new)  # ثبتِ جلسه برای دروازه‌ی فازِ یک — fail-soft و بی‌صدا
    st.session_state["team_room"] = room_new
    st.rerun()

room: dict | None = st.session_state.get("team_room")

# ----------------------------------------------------------------- خروجی
if not room:
    st.info("نماد را انتخاب کن و «شروعِ جلسه‌ی تیم» را بزن — پنج عامل با هم سرِ همان ارز جلسه می‌گذارند.")
    st.stop()

if not room.get("ok"):
    st.error(f"⚠️ {room.get('error', 'جلسه برنگشت')}")
    st.stop()

sym = room["symbol"]
dec = room["dec"]
price = room["price"]

# ---- سربرگِ جلسه
hc = st.columns([1.2, 1.2, 1.4, 1.2])
hc[0].metric("نماد", sym)
hc[1].metric("قیمتِ لحظه", f"{price:,.{dec}f}")
hc[2].metric("تایم‌فریم · صرافی", f"{room['interval']} · {room['exchange']}")
hc[3].metric("زمانِ جلسه (تهران)", room["ts"])

# ---- حکمِ نهایی — اول نشان می‌دهیم، جزئیات بعد
vd = room["verdict"]
box = {"align": st.success, "wait": st.info, "object": st.warning}.get(vd["state"], st.warning)
box(f"**{vd['title']}** — {vd['text']}")
cap = st.columns(3)
cap[0].caption(f"اعتراض‌ها: {vd['n_obj']}")
cap[1].caption(f"هشدارها: {vd['n_warn']}")
cap[2].caption(f"تاییدها: {vd['n_confirm']}")

st.divider()

# ---- کارتِ عامل‌ها (ترتیبِ جلسه)
ORDER = ["news", "watchdog", "chart", "risk", "kronos"]
TITLES = {"news": "پیام‌های خبرنگار", "watchdog": "گزارشِ دیدبان",
          "chart": "پروپوزالِ چارت‌خوان", "risk": "محاسبه‌ی مدیرِ ریسک",
          "kronos": "پیش‌بینیِ احتمالاتیِ شاهد"}
for key in ORDER:
    a = room["agents"].get(key)
    if not a:
        continue
    with st.container(border=True):
        st.markdown(f"### {a['emoji']} {a['name']} — «{TITLES[key]}»")
        st.caption(a["role"])
        for m in a["msgs"]:
            st.markdown(f"• {m['text']}", unsafe_allow_html=True)
            st.caption(f"دلیل/مدرک: {m['why']}")
        if key == "chart":
            plan = room["plan"]
            entry, stop, tps = plan.get("entry"), plan.get("stop"), plan.get("targets") or []
            rows = [{"سطح": "ورود", "قیمت": entry}, {"سطح": "حدضرر", "قیمت": stop}]
            for i, t in enumerate(tps[:3], start=1):
                tp = t[0] if isinstance(t, tuple) else t
                rows.append({"سطح": f"هدفِ {i}", "قیمت": tp})
            df_lv = pd.DataFrame([r for r in rows if r["قیمت"] is not None])
            if not df_lv.empty:
                st.dataframe(df_lv, hide_index=True, use_container_width=True)
        if key == "kronos":
            pred = a.get("pred") or {}
            if pred.get("predicting"):
                kc1, kc2, kc3 = st.columns(3)
                side_fa = {1: "صعودی ⬆️", -1: "نزولی ⬇️", 0: "بی‌جهت ➖"}.get(pred.get("side"), "؟")
                kc1.metric("جهتِ اکثریتِ مسیرها", side_fa, f"{pred.get('agree_pct')}٪")
                kc2.metric("میانه‌ی بازده در افق", f"{pred.get('ret_med', 0):+.2f}٪",
                           f"{pred.get('n_paths')} مسیر × {pred.get('horizon')} کندل")
                kc3.metric("آخرین قیمت", f"{pred.get('last_px'):,.{dec}f}",
                           f"زمینه: {pred.get('ctx_len')} کندل")
                rows_b = [{"باند": "۵٪ کمینه", "قیمت": pred.get("p5")},
                          {"باند": "میانه (۵۰٪)", "قیمت": pred.get("p50")},
                          {"باند": "۹۵٪ بیشینه", "قیمت": pred.get("p95")}]
                st.dataframe(pd.DataFrame(rows_b), hide_index=True, use_container_width=True)
            back = (pred.get("backend") or "؟")
            back_fa = ("🧪 شبیه‌سازِ آفلاینِ مونت‌کارلو — مدلِ واقعی نصب نیست "
                       "(فعال‌سازی با اپراتور: KRONOS_BACKEND=kronos + KRONOS_REPO)"
                       if back == "offline" else f"✅ مدلِ واقعی: {pred.get('model')}")
            st.caption(f"پشتیبان: {back_fa} · {pred.get('settings_fa')}"
                       + (f" · {pred['note_fa']}" if pred.get("note_fa") else ""))

# ---- شکاک — آخرِ جلسه، قاضیِ اتاق
sk = room["skeptic"]
with st.container(border=True):
    st.markdown(f"### {sk['emoji']} {sk['name']} — «داوری‌ها»")
    st.caption(sk["role"] + " — جدولِ زیر یعنی: چه ادعایی، علیهِ چه کسی، با چه دلیلی. "
               "داوری‌های «سایه» (کرونوس) فقط هشدار/تاییدِ ثبت‌شده‌اند و روی حکمِ نهایی اثر ندارند.")
    if sk["checks"]:
        st.dataframe(pd.DataFrame(sk["checks"]), hide_index=True, use_container_width=True)

# ---- دروازه‌ی فازِ یک — شاهدِ سایه تا انتشار (جدول ۴ گزارشِ کرونوس)
gate = KW.gate_stats()
if gate.get("ok"):
    real, stub = gate.get("real") or {}, gate.get("stub") or {}
    with st.container(border=True):
        st.markdown("### 🚦 دروازه‌ی فازِ یک — «شاهدِ سایه» تا انتشار")
        st.caption("قانونِ نقشه‌راه: کرونوس فقط وقتی از حالتِ سایه بیرون می‌آید که جهتِ اکثریتِ مسیرهایش "
                   "روی بیش از ۵۵٪ از ۲۰۰ جلسه‌ی paper-trade با سیگنالِ چارت هم‌جهت باشد — و دروازه‌ی "
                   "رسمی فقط با جلساتِ مدلِ واقعی جمع می‌خورد؛ جلساتِ شبیه‌ساز «تمرینِ لوله‌کشی» است.")
        g1, g2, g3 = st.columns(3)
        g1.metric("جلسه‌های مدلِ واقعی", f"{real.get('n', 0)}/۲۰۰",
                  gate.get("gate_fa", "").replace("⏳ ", ""))
        g2.metric("هم‌جهتیِ مدلِ واقعی", f"{real.get('rate', 0) if real.get('rate') is not None else '—'}٪",
                  "دروازه: >۵۵٪")
        g3.metric("تمرینِ شبیه‌ساز", f"{stub.get('n', 0)} جلسه",
                  (f"هم‌جهتیِ {stub.get('rate')}٪" if stub.get("rate") is not None else "بدونِ جلسه‌ی سیگنال‌دار"))
        if gate.get("gate_pass"):
            st.success("✅ دروازه‌ی فازِ یک گذشت — می‌توان سراغ فازِ دو (انتشارِ ستونِ احتمال در گزارشِ روزانه) رفت.")
        last = gate.get("last") or {}
        if last:
            st.caption(f"آخرین جلسه‌ی ثبت‌شده: {last.get('ts')} — {last.get('symbol')} · "
                       f"پشتیبان: {last.get('backend')} · حکمِ تیم: {last.get('verdict_state')}")

st.divider()
st.caption("قاعده‌ی اتاق: هر پیامِ بی‌مدرک حقِ حضور ندارد — اگر عاملی دلیل نیاورد، شکاک حقِ حذفِ ادعایش را دارد.")
