"""وضعیت شاهدها — داشبوردِ شفافیتِ دفترهای اندازه‌گیری — NorthmanQuant
================================================================
یک صفحه برای «کی دارد چه چیزی را اندازه می‌گیرد و تا کجاست؟» — همه‌چیز
فقط-خواندنی از core/data و هیچ بخشی از اپ را تغییر نمی‌دهد:

  ⚖️ قاضیِ ک↔ن — حکمِ فعلیِ متنِ قفل‌شده + شمارِ پیامدهای نمره‌شده
  🔮 دروازه‌ی کرونوس و 🧭 دروازه‌ی نبیه — آمارِ رسمیِ gate_stats
  🗺 نقشه‌ی نشاط — کدام نماد×تایم‌فریم چارتِ حکم‌شان همین حالا زنده است
  🎯 پیامدهای نمره‌شده — hit-rateِ واقعیِ بازار به تفکیکِ موتور/تایم‌فریم
  💓 ضربانِ صرافی‌ها — کیفیتِ زنده‌ی هر ۸ صرافیِ رجیستری از جابِ پوشش

هر بخش fail-soft است: نبودِ فایل یعنی «هنوز داده‌ای ثبت نشده»، نه خطا.
"""
from __future__ import annotations

import json
import os

import pandas as pd
import streamlit as st

from core.help import hint
from core.i18n import setup_i18n, tr

st.set_page_config(page_title="وضعیت شاهدها | Witness Status",
                   page_icon="🧭", layout="wide")
LANG = setup_i18n(page="p11")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "core", "data")


def _L(fa: str, en: str) -> str:
    return en if LANG == "en" else fa


def _read_jsonl(path: str) -> list[dict]:
    try:
        rows: list[dict] = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    e = json.loads(line)
                except ValueError:
                    continue  # خطِ خرابِ وسطِ دفتر، دفتر را نمی‌بُرد
                if isinstance(e, dict):
                    rows.append(e)
        return rows
    except Exception:  # noqa: BLE001 — نبودِ دفتر یعنی هنوز داده نیست
        return []


def _paper_summary() -> dict:
    """خلاصه‌ی پیامدها به تفکیکِ موتور — همان قواعدِ گرِیدرِ مشترک."""
    rows = _read_jsonl(os.path.join(DATA, "paper_outcomes.jsonl"))
    out: dict = {}
    for eng in ("kronos", "nabigha"):
        rs = [r for r in rows if r.get("engine") == eng]
        decided = [r for r in rs if r.get("outcome") in (1, -1)]  # باندِ مرده حذف
        hits = sum(1 for r in decided if r.get("hit"))
        out[eng] = {
            "graded": len(rs), "decided": len(decided), "hits": hits,
            "rate": round(hits / len(decided) * 100.0, 1) if decided else None,
            "intervals": {},
        }
        for itv in sorted({str(r.get("interval")) for r in decided}):
            di = [r for r in decided if str(r.get("interval")) == itv]
            hi = sum(1 for r in di if r.get("hit"))
            out[eng]["intervals"][itv] = (len(di), round(hi / len(di) * 100.0, 1))
    return out


st.title("🧭 " + tr("وضعیت شاهدها — قاضی، دروازه‌ها، نقشه‌ی نشاط",
                    "Witness status — judge, gates, signal map"))
hint(tr(
    "این صفحه فقط نمایش است: هر عددی که جاب‌های Actions اندازه می‌گیرند اینجا بدونِ واسطه از "
    "core/data خوانده می‌شود — قاضیِ ک↔ن (حکمِ مقایسه‌ایِ متنِ قفل‌شده)، دو دروازه‌ی ۲۰۰ جلسه‌ای، "
    "نقشه‌ی نشاط (نمادهایی که چارت‌شان همین حالا زنده است)، پیامدهای نمره‌شده (hit-rateِ واقعیِ "
    "بازار، جدا از هم‌جهتیِ چارت) و ضربانِ کیفیتِ هر ۸ صرافی. هیچ دکمه‌ای ندارد چون هیچ‌چیز را "
    "تغییر نمی‌دهد.",
    "This page is display-only: every number the Actions jobs measure is read straight from "
    "core/data — the k↔n judge (locked-contract verdict), both 200-session gates, the signal map "
    "(charts that are live right now), graded outcomes (true market hit-rate, separate from chart "
    "agreement) and the quality heartbeat of all 8 exchanges. No buttons, because it changes nothing."))

# ── ⚖️ قاضیِ ک↔ن ─────────────────────────────────────────────────────────────
st.header("⚖️ " + _L("قاضیِ کرونوس ↔ نبیه", "Kronos ↔ Nabigha judge"))
try:
    with open(os.path.join(DATA, "kronos_nabigha_report.md"), encoding="utf-8") as f:
        rep = f.read()
    verdict_text = rep.split("## حکمِ فعلی")[-1].strip()
    st.info(verdict_text)
except Exception:  # noqa: BLE001
    st.info(_L("هنوز گزارشِ قاضی ساخته نشده — اولین رانِ جابِ روزانه آن را می‌سازد.",
               "Judge report not built yet — the first daily run creates it."))
ps = _paper_summary()
st.caption(_L(
    f"پیامدهای نمره‌شده — کرونوس: {ps['kronos']['graded']} · نبیه: {ps['nabigha']['graded']} "
    f"· آستانه‌ی حکمِ مقایسه‌ای: ۳۰ برای هر دو (قراردادِ پیش‌ثبت‌شده، بدونِ تغییر پس از دیدنِ داده)",
    f"Graded outcomes — kronos: {ps['kronos']['graded']} · nabigha: {ps['nabigha']['graded']} "
    f"· verdict threshold: 30 for each (pre-registered contract, never edited after seeing data)"))

# ── 🔮🧭 دو دروازه ────────────────────────────────────────────────────────────
st.header(_L("دو دروازه‌ی paper — قراردادِ قفل‌شده: ۲۰۰ جلسه · هم‌جهتیِ ≥۵۵٪",
             "Two paper gates — locked contract: 200 sessions · ≥55% agreement"))
from core import kronos_witness as KW  # noqa: E402 — بعد از set_page_config
from core import nabigha_engine as NE  # noqa: E402
from core.signal_map import map_age_h  # noqa: E402

gk = KW.gate_stats()
gn = NE.gate_stats()
c1, c2 = st.columns(2)
with c1:
    st.subheader("🔮 " + _L("شاهدِ کرونوس", "Kronos witness"))
    if gk.get("ok"):
        m1, m2, m3 = st.columns(3)
        m1.metric(_L("جلسه‌ی مدلِ واقعی", "real-model sessions"), f"{gk['real']['n']}/200")
        m2.metric(_L("هم‌جهتی", "agreement"),
                  f"{gk['real']['rate']}٪" if gk["real"]["rate"] is not None else "—")
        m3.metric(_L("تمرینِ شبیه‌ساز", "simulator drills"), gk["stub"]["n"])
        last = gk.get("last") or {}
        st.caption(_L(
            f"آخرین جلسه: {last.get('ts', '—')} · {last.get('symbol', '—')} · {last.get('interval', '—')}",
            f"last session: {last.get('ts', '—')} · {last.get('symbol', '—')} · {last.get('interval', '—')}"))
    else:
        st.info(_L("دفترِ کرونوس هنوز خالی است.", "Kronos log is still empty."))
with c2:
    st.subheader("🧭 " + _L("شاهدِ نبیه (سایه)", "Nabigha witness (shadow)"))
    if gn.get("ok"):
        m1, m2, m3 = st.columns(3)
        m1.metric(_L("جلسه‌ی سیگنال‌دار", "signal sessions"), f"{gn['n_signal']}/200")
        m2.metric(_L("هم‌جهتی", "agreement"),
                  f"{gn['rate']}٪" if gn["rate"] is not None else "—")
        m3.metric(_L("کلِ سطرها", "total rows"), gn["n_total"])
        last = gn.get("last") or {}
        st.caption(_L(
            f"آخرین جلسه: {last.get('ts', '—')} · {last.get('symbol', '—')} · {last.get('interval', '—')}",
            f"last session: {last.get('ts', '—')} · {last.get('symbol', '—')} · {last.get('interval', '—')}"))
    else:
        st.info(_L("دفترِ نبیه هنوز خالی است.", "Nabigha log is still empty."))
st.caption(gk.get("gate_fa", "") + " · " + gn.get("gate_fa", ""))

# ── 🗺 نقشه‌ی نشاط ────────────────────────────────────────────────────────────
st.header("🗺 " + _L("نقشه‌ی نشاط — چارتِ حکم‌شان زنده است",
                     "Signal map — charts that are live right now"))
age = map_age_h()
try:
    with open(os.path.join(DATA, "nabigha_signal_map.json"), encoding="utf-8") as f:
        m = json.load(f)
except Exception:  # noqa: BLE001
    m = None
if m is None:
    st.info(_L("نقشه‌ای هنوز ثبت نشده — جابِ نبیه هر ۳ ساعت می‌سازدش.",
               "No map yet — the nabigha job builds one every 3 hours."))
else:
    act = [c for c in m.get("combos", []) if c.get("active")]
    st.caption(_L(
        f"ثبت: {m.get('ts_tehran', '—')} (تهران) · عمر: "
        f"{'—' if age is None else f'{age:.1f} ساعت'} · استخر: {m.get('total', '—')} خانه × ۳ تایم‌فریم · "
        f"گاردِ تازگی: ۴ ساعت — نقشه‌ی کهنه یعنی چرخشِ تقویمی",
        f"snapshot: {m.get('ts_tehran', '—')} (Tehran) · age: "
        f"{'—' if age is None else f'{age:.1f} h'} · pool: {m.get('total', '—')} cells × 3 timeframes · "
        f"freshness guard: 4h — a stale map means calendar rotation"))
    if act:
        rows = [{
            "نماد": c.get("symbol"), "تایم‌فریم": c.get("interval"),
            "جهت": {1: "↑ لانگ", -1: "↓ شورت"}.get(c.get("side"), "—"),
            "طرح": c.get("mode") or "—", "اطمینان": f"{c.get('confidence', 0)}٪",
            "چرا": c.get("why") or "—",
        } for c in act]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.caption(_L("جلسه‌گیرها (کرونوس و نبیه) با --hot همین‌ها را اول می‌چینند.",
                      "Both witnesses (kronos & nabigha) pick these first via --hot."))
    else:
        st.info(_L("هیچ خانه‌ای زنده نیست — جلسه‌گیرها به چرخشِ تقویمی برمی‌گردند.",
                   "No live cells — witnesses fall back to calendar rotation."))

# ── 🎯 پیامدهای نمره‌شده ─────────────────────────────────────────────────────
st.header("🎯 " + _L("پیامدهای نمره‌شده — بازار، نه فقط چارت",
                     "Graded outcomes — the market, not just the chart"))
st.caption(_L(
    "هم‌جهتیِ دروازه می‌گوید «با تیمِ تحلیل موافق بود؟»؛ این جدول می‌گوید «بعدش بازار واقعاً همان‌طور رفت؟» "
    "— outcome ±۱/۰ با باندِ مرده‌ی ۰٫۰۵٪؛ دو عددِ کاملاً جدا که کنارِ هم گزارش می‌شوند.",
    "Gate agreement answers 'did it match the team?'; this table answers 'did the market actually "
    "move that way?' — outcome ±1/0 with a 0.05% dead band; two separate numbers, reported side by side."))
c1, c2 = st.columns(2)
with c1:
    st.subheader("🔮 " + _L("کرونوس", "Kronos"))
    p = ps["kronos"]
    if p["graded"]:
        m1, m2, m3 = st.columns(3)
        m1.metric(_L("نمره‌شده", "graded"), p["graded"])
        m2.metric(_L("تعیین‌سرنوشت", "decided"), p["decided"])
        m3.metric(_L("hit-rateِ بازار", "market hit-rate"),
                  f"{p['rate']}٪" if p["rate"] is not None else "—")
        if p["intervals"]:
            st.caption(" · ".join(f"{itv}: {n} ({r}٪)" for itv, (n, r) in p["intervals"].items()))
    else:
        st.info(_L("هنوز پیامدی نمره نگرفته.", "No graded outcomes yet."))
with c2:
    st.subheader("🧭 " + _L("نبیه", "Nabigha"))
    p = ps["nabigha"]
    if p["graded"]:
        m1, m2, m3 = st.columns(3)
        m1.metric(_L("نمره‌شده", "graded"), p["graded"])
        m2.metric(_L("تعیین‌سرنوشت", "decided"), p["decided"])
        m3.metric(_L("hit-rateِ بازار", "market hit-rate"),
                  f"{p['rate']}٪" if p["rate"] is not None else "—")
        if p["intervals"]:
            st.caption(" · ".join(f"{itv}: {n} ({r}٪)" for itv, (n, r) in p["intervals"].items()))
    else:
        st.info(_L("هنوز پیامدی نمره نگرفته.", "No graded outcomes yet."))

# ── 💓 ضربانِ صرافی‌ها ────────────────────────────────────────────────────────
st.header("💓 " + _L("ضربانِ صرافی‌ها — هر ۸ صرافیِ رجیستری",
                     "Exchange heartbeat — all 8 registry venues"))
try:
    with open(os.path.join(DATA, "exchange_coverage.json"), encoding="utf-8") as f:
        cov = json.load(f)
    venues = cov.get("venues") or []
    if venues:
        rows = [{
            "صرافی": v.get("name"),
            "تیکِ زنده": "✅" if v.get("tick_ok") else "❌",
            "کندل": "✅" if v.get("candles_ok") else "❌",
            "مسیرِ کندل": v.get("candle_path") or "—",
            "ردیفِ کندل": v.get("candle_rows"),
            "عمرِ کندل (دقیقه)": v.get("candle_age_min"),
            "چکِ موفق": f"{v.get('checks_pass', 0)}/{v.get('checks_total', 0)}",
        } for v in venues]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.caption(_L(
            f"آخرین ضربان: {cov.get('ts_tehran', '—')} (تهران) · نمادِ سنجش: {cov.get('symbol', '—')} · "
            f"تایم‌فریم: {cov.get('interval', '—')} · پوششِ کل: {cov.get('coverage_pct', '—')}٪ · "
            f"کندلِ تازه: {cov.get('fresh_candles', '—')}/۸",
            f"last beat: {cov.get('ts_tehran', '—')} (Tehran) · probe: {cov.get('symbol', '—')} · "
            f"interval: {cov.get('interval', '—')} · total coverage: {cov.get('coverage_pct', '—')}% · "
            f"fresh candles: {cov.get('fresh_candles', '—')}/8"))
    else:
        st.info(_L("ضربانی هنوز ثبت نشده.", "No heartbeat recorded yet."))
except Exception:  # noqa: BLE001
    st.info(_L("فایلِ ضربان هنوز ساخته نشده — جابِ پوششِ روزانه می‌سازدش.",
               "Heartbeat file not built yet — the daily coverage job creates it."))

st.caption("🧭 " + _L(
    "این صفحه فقط از دفترها می‌خواند؛ ادعای تازه‌ای نمی‌سازد. دفترها append-only اند و قراردادها قفل.",
    "This page only reads the ledgers; it makes no new claims. Ledgers are append-only and contracts locked."))
