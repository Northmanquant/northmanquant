"""🔬 Agent Lab — آزمایشگاه ایجنت‌ها (فاز ۱۳: تحقیق و خودبهبود)
اینجا میدان فقط اجرا نمی‌شود، «موردکاوی» می‌شود:
  • کارنامه‌ی تحقیقاتی هر ایجنت از معاملات زنده (وین‌ریت/انتظاری/PF/زنجیره/فرم)
  • کالبدشکافی معاملات بسته — چرا مردند؟ (استاپ تنگ، خلاف رژیم، تایم‌اوت بدون سود…)
  • تطبیق فعال — سیستم از همین تحلیل چه محدودیت‌هایی برای خودش ساخته است
"""
from __future__ import annotations

import pandas as pd
import streamlit as st
from core.i18n import setup_i18n, get_lang

st.set_page_config(page_title="آزمایشگاه ایجنت‌ها | Agent Lab", page_icon="🔬", layout="wide")
LANG = setup_i18n(page="p5")


def L(fa: str, en: str) -> str:
    return en if LANG == "en" else fa


st.title("🔬 " + L("آزمایشگاه ایجنت‌ها — تحقیق و خودبهبود",
                   "Agent Lab — Research & Self-Improvement"))
st.caption(L(
    "اینجا به جای «چند تا برد؟» می‌پرسیم «چرا باخت؟ و سیستم چه یاد گرفت؟» "
    "هر معامله‌ی بسته کالبدشکافی می‌شود (استاپ تنگ، خلاف رژیم، تایم‌اوت بدون سود…) "
    "و از دل همان شواهد، محدودیت‌های محافظه‌کارانه‌ی خودکار ساخته می‌شود: "
    "سرد شدن ایجنتِ زنجیره‌ضرر، ممنوعیت نمادِ چاه، انضباط رژیم. "
    "هیچ پنالتی ریسک را بزرگ نمی‌کند — فقط ورودهای بی‌احتیاط را می‌بندد.",
    "Instead of just “how many wins?”, we ask “why did it lose — and what did the system learn?” "
    "Every closed trade gets an autopsy (tight stop, against regime, timeout without profit…) "
    "and the same evidence drives automatic conservative guardrails: cooling down losing-streak "
    "agents, banning repeat-loser symbols, regime discipline. No penalty ever increases risk — "
    "they only close careless entries."))

from core import agent_lab as LAB  # noqa: E402
from core import alerts as AL  # noqa: E402
from core import arena as A  # noqa: E402
from core import arena_store  # noqa: E402
from core import dossier as DOS  # noqa: E402
from core import edge as EG  # noqa: E402
from core.autopsy import TAG_FA  # noqa: E402

_store = arena_store.get_store()
try:
    _trades = _store.load_all()
except Exception as e:  # noqa: BLE001
    st.error(L(f"خواندن میدان ناموفق: {e}", f"Failed to load arena: {e}"))
    st.stop()

_regime_alerts = AL.recent_alerts(200)
_closed = LAB.closed_sorted(_trades)
_report = LAB.agent_report(_trades, _regime_alerts)
_lab = LAB.compute_adaptations(_trades, regime_alerts=_regime_alerts)
_dossier = DOS.compute_dossier(_trades, regime_alerts=_regime_alerts)
_edge = EG.load_edge() or {}

if not _closed:
    st.info(L("هنوز معامله‌ی بسته‌شده‌ای نیست — آزمایشگاه بعد از اولین بسته‌شدن‌ها جان می‌گیرد. 🌱",
              "No closed trades yet — the lab wakes up after the first closures. 🌱"))
    st.stop()

# ---------------------------------------------------------------- KPI
_c = sum(1 for t in _closed if str(t.get("source")) in ("autopilot", "manual"))
_tot_r = sum(float(t.get("realized_r") or 0.0) for t in _closed)
_best = max(_report.items(), key=lambda kv: kv[1]["exp"], default=None)
_worst = min((kv for kv in _report.items() if kv[1]["n"] >= 2),
             key=lambda kv: kv[1]["exp"], default=None)

k1, k2, k3, k4 = st.columns(4)
k1.metric(L("معاملات بسته‌شده", "Closed trades"), len(_closed),
          L(f"{_c} برچسب‌دار", f"{_c} labeled"))
k2.metric(L("جمع R کل", "Total R"), f"{_tot_r:+.2f}R")
k3.metric(L("بهترین ایجنت (انتظاری)", "Best agent (expectancy)"),
          (_best[0] or "—") if _best else "—",
          f"{_best[1]['exp']:+.2f}R" if _best else "")
k4.metric(L("ضعیف‌ترین (n≥2)", "Weakest (n≥2)"),
          (_worst[0] or "—") if _worst else "—",
          f"{_worst[1]['exp']:+.2f}R" if _worst else "")

_tab1, _tab2, _tab3, _tab4 = st.tabs([
    "🎓 " + L("کارنامه‌ی ایجنت‌ها", "Agent report cards"),
    "🔬 " + L("کالبدشکافی ضعف‌ها", "Weakness autopsy"),
    "🧊 " + L("تطبیق فعال", "Active adaptations"),
    "📋 " + L("پرونده‌ی بهبود", "Improvement dossier"),
])

# ================================================================ تب ۱ — کارنامه
with _tab1:
    rows = []
    for nm, r in _report.items():
        # ترتیب ستون‌ها مهم‌به-مهم است — در موبایل ستون‌های اول دیده می‌شوند
        rows.append({
            L("ایجنت", "Agent"): nm,
            L("انتظاری", "Expectancy"): f"{r['exp']:+.2f}R",
            L("جمع R", "Total R"): f"{r['total_r']:+.2f}",
            L("وین‌ریت", "Winrate"): (f"{r['winrate']}%" if r["winrate"] is not None else "—"),
            L("بسته‌شده", "Closed"): r["n"],
            "PF": r["pf"],
            L("زنجیره‌ی باخت", "Loss streak"): r["streak"],
            L("فرم ۱۰تایی", "Last-10 form"): f"{r['form10_r']:+.2f}R",
            L("حکم لبه (بک‌تست)", "Edge verdict (backtest)"):
                EG.VERDICT_FA.get(_edge.get("verdicts", {}).get(nm), "—")
                if LANG == "fa" else EG.VERDICT_EN.get(_edge.get("verdicts", {}).get(nm), "—"),
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(L("انتظاری", "Expectancy"), ascending=False)
    st.dataframe(df, width="stretch", hide_index=True)
    st.caption(L(
        "انتظاری = میانگین R هر معامله (مهم‌ترین عدد — بعد از ~۳۰ معامله معنادار است). "
        "حکم لبه از بازپخش بک‌تست می‌آید (صفحه‌ی میدان)؛ بقیه از معاملات زنده.",
        "Expectancy = average R per trade (the key number — meaningful after ~30 trades). "
        "The edge verdict comes from backtest replay (Arena page); the rest from live trades."))

# ================================================================ تب ۲ — کالبدشکافی
with _tab2:
    counts = LAB.AU.autopsy_all(_closed, _regime_alerts)["_counts"]
    if not counts:
        st.info(L("هنوز برچسب ضعفی ثبت نشده — با بسته‌شدن معامله‌ها پر می‌شود.",
                  "No weakness tags yet — fills up as trades close."))
    else:
        import plotly.express as px  # noqa: PLC0415

        lbl = {c: (TAG_FA.get(c, c) if LANG == "fa" else c) for c in counts}
        cdf = pd.DataFrame({"tag": [lbl[c] for c in counts],
                            "n": list(counts.values())}).sort_values("n", ascending=False)
        fig = px.bar(cdf, x="tag", y="n",
                     labels={"tag": L("برچسب ضعف", "Weakness tag"),
                             "n": L("تعداد معامله", "Trades")},
                     title=L("دلایل مرگ معامله‌ها (همه‌ی ایجنت‌ها)",
                             "Why trades died (all agents)"),
                     color_discrete_sequence=["#f97316"])
        fig.update_layout(height=380, margin=dict(t=50, b=20))
        st.plotly_chart(fig, width="stretch")

        pick = st.selectbox(L("کالبدشکافی تفصیلی ایجنت", "Detailed autopsy of agent"),
                            ["—"] + sorted(_report.keys()))
        if pick != "—":
            mine = [t for t in reversed(_closed) if str(t.get("agent")) == pick][:20]
            au = LAB.AU.autopsy_all(_closed, _regime_alerts)
            rows = []
            for t in mine:
                codes = (au.get(str(t.get("id"))) or {}).get("codes", [])
                rows.append({
                    L("نماد", "Symbol"): t.get("symbol"),
                    L("جهت", "Dir"): "🟢" if int(t.get("direction") or 0) > 0 else "🔴",
                    "R": f"{float(t.get('realized_r') or 0):+.2f}",
                    L("خروج", "Exit"): str(t.get("exit_reason") or "—"),
                    L("ضعف‌ها", "Weaknesses"): " · ".join(
                        (TAG_FA.get(c, c) if LANG == "fa" else c) for c in codes) or "—",
                    L("زمان بستن", "Closed at"): str(t.get("closed_at") or "")[:16],
                })
            st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

# ================================================================ تب ۳ — تطبیق
with _tab3:
    st.info(L(
        "این‌ها قواعد ثابت و شفاف‌اند — سیستم هر بار از صفر از روی تاریخچه محاسبه‌شان می‌کند "
        "(بدون حافظه‌ی مخفی): زنجیره‌ی باخت ≥۳ → cooldown ×۲، ≥۵ → ×۳، ≥۷ → ×۴؛ "
        "(ایجنت، نماد) با ≥۳ باخت و ۰ برد در ۱۴ روز → ۷ روز ممنوع؛ "
        "≥۶۰٪ باخت‌های «خلاف رژیم» (حداقل ۴) → فقط ورود هم‌جهت رژیم.",
        "These are fixed, transparent rules — recomputed from scratch from history every time "
        "(no hidden memory): loss streak ≥3 → cooldown ×2, ≥5 → ×3, ≥7 → ×4; "
        "(agent, symbol) with ≥3 losses and 0 wins in 14 days → banned for 7 days; "
        "≥60% “against-regime” losses (min 4) → only with-regime entries."))

    c = _lab.get("counts", {})
    m1, m2, m3 = st.columns(3)
    m1.metric(L("ایجنت سردشده", "Cooled-down agents"), c.get("penalized", 0))
    m2.metric(L("انضباط رژیم", "Regime discipline"), c.get("regime_only", 0))
    m3.metric(L("نماد ممنوع", "Banned symbols"), c.get("bans", 0))

    penal = [(nm, a) for nm, a in (_lab.get("agents") or {}).items()
             if float(a.get("cool_mult") or 1.0) > 1.0]
    if penal:
        st.subheader("🧊 " + L("سرد شدن فعال", "Active cooldowns"))
        rows = [{"🤖": nm, L("زنجیره", "Streak"): a["streak"],
                 L("ضریب cooldown", "Cooldown mult"): f"×{a['cool_mult']:g}",
                 L("فرم ۱۰تایی", "Last-10 form"): f"{a['form10_r']:+.2f}R"}
                for nm, a in sorted(penal, key=lambda kv: -kv[1]["streak"])]
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    bans = _lab.get("symbol_bans") or []
    if bans:
        st.subheader("⛔ " + L("نمادهای ممنوع", "Banned symbols"))
        rows = [{"🤖": b["agent"], "💎": b["symbol"],
                 L("باخت در پنجره", "Losses in window"): b["losses"],
                 L("تا", "Until"): str(b["until"])[:16]}
                for b in bans]
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    rego = [(nm, a) for nm, a in (_lab.get("agents") or {}).items() if a.get("regime_only")]
    if rego:
        st.subheader("🧭 " + L("انضباط رژیم", "Regime discipline"))
        st.markdown(" · ".join(f"**{nm}**" for nm, _ in rego)
                    + " — " + L("فقط هم‌جهت رژیم مجاز است", "only with-regime entries allowed"))
    if not penal and not bans and not rego:
        st.success(L("فعلاً هیچ پنالتی‌ای فعال نیست — همه‌ی ایجنت‌ها در آستانه‌های سالم‌اند. ✅",
                     "No penalties active — all agents are within healthy thresholds. ✅"))

# ================================================================ تب ۴ — پرونده‌ی بهبود (فاز ۱۴)
with _tab4:
    st.info(L(
        "پرونده‌ی پزشکی هر ایجنت: تشخیص (از کالبدشکافی) → نسخه (سه درمان محافظه‌کارانه) → "
        "اعتبارسنجی ضدواقعی (اگر نسخه از اول بود، چند ضرر حذف می‌شد و چند سود از دست می‌رفت؟). "
        "گیت علمی: نسخه فقط وقتی کار می‌شود که «ضرر حذف‌شده ≥ سود ازدست‌رفته». "
        "تعلیق خود-التیام است: بدون ترید تازه، پنجره‌ی ۲۱ روزه کهنه می‌شود و ایجنت خودش برمی‌گردد.",
        "A medical chart per agent: diagnosis (from autopsy) → prescription (three conservative "
        "treatments) → counterfactual validation (had it been active, how many losses avoided vs "
        "wins missed?). Scientific gate: a prescription only activates if saved ≥ missed. "
        "Suspension self-heals: with no new trades the 21-day window ages out and the agent returns."))

    dc = _dossier.get("counts", {})
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("🚫 " + L("تعلیق مشروط", "Suspended"), dc.get("suspended", 0))
    d2.metric("🎯 " + L("سهمیه‌ی تک‌پوزیشن", "Single-slot quota"), dc.get("quota_cut", 0))
    d3.metric("🎚️ " + L("فیلتر کیفیت", "Quality filter"), dc.get("score_floor", 0))
    d4.metric("👁️ " + L("در حال پایش", "Monitoring"),
              sum(1 for a in _dossier.get("agents", {}).values() if a.get("status") == "monitoring"))

    VAL_FA = {"suspension": "🚫 تعلیق", "quota": "🎯 سهمیه", "quality": "🎚️ کیفیت"}
    VAL_EN = {"suspension": "🚫 Suspension", "quota": "🎯 Quota", "quality": "🎚️ Quality"}
    VERDICT_FA = {"ok": "مناسب ✅", "reject": "رد ❌"}

    _active = [(nm, a) for nm, a in _dossier.get("agents", {}).items()
               if a.get("limits")]
    _weak = [(nm, a) for nm, a in _dossier.get("agents", {}).items()
             if not a.get("limits") and a.get("status") == "monitoring"]

    if _active:
        st.subheader("📋 " + L("پرونده‌های فعال", "Active dossiers"))
        for nm, a in sorted(_active, key=lambda kv: kv[1]["exp"]):
            mine = [t for t in _closed if str(t.get("agent")) == nm]
            diag = DOS.diagnose(mine, _regime_alerts, lang=LANG)
            head = (f"{nm} · انتظاری {a['exp']:+.2f}R · PF {a['pf']:g} · n={a['n']}")
            with st.expander(head):
                st.markdown("**🩺 " + L("تشخیص", "Diagnosis") + "**")
                _note = diag.get("note_fa") or diag.get("note_en") or "—"
                st.markdown(f"- {_note}")
                if a.get("weakness"):
                    st.markdown("- " + " · ".join(
                        f"{TAG_FA.get(c, c) if LANG == 'fa' else c}: {n}"
                        for c, n in list(a["weakness"].items())[:4]))

                st.markdown("**💊 " + L("نسخه‌ی فعال", "Active prescription") + "**")
                lim = a.get("limits") or {}
                lines = []
                if lim.get("suspended"):
                    lines.append("🚫 " + L("تعلیق مشروط — ورود جدید ممنوع تا رفع شرط",
                                           "Conditional suspension — no new entries"))
                if lim.get("max_pos"):
                    lines.append("🎯 " + L(f"سهمیه: حداکثر {lim['max_pos']} پوزیشن هم‌زمان",
                                           f"Quota: max {lim['max_pos']} concurrent position(s)"))
                if lim.get("score_floor"):
                    lines.append("🎚️ " + L(f"فیلتر کیفیت: |score| ≥ {lim['score_floor']:g}",
                                           f"Quality filter: |score| ≥ {lim['score_floor']:g}"))
                for ln in lines:
                    st.markdown(f"- {ln}")

                st.markdown("**🧪 " + L("اعتبارسنجی ضدواقعی (روی تاریخچه‌ی خود ایجنت)",
                                        "Counterfactual validation (on the agent's own history)") + "**")
                vrows = []
                for k, v in (a.get("validation") or {}).items():
                    lbl = (VAL_FA if LANG == "fa" else VAL_EN).get(k, k)
                    verd = VERDICT_FA.get(v.get("verdict"), v.get("verdict")) if LANG == "fa" \
                        else ("pass ✅" if v.get("verdict") == "ok" else "reject ❌")
                    vrows.append({
                        L("نسخه", "Rx"): lbl,
                        L("بلاک‌شده", "Blocked"): v.get("blocked_n", 0),
                        L("ضرر حذف‌شده", "Saved loss"): f"{v.get('saved_loss_r', 0):+.2f}R",
                        L("سود ازدست‌رفته", "Missed win"): f"-{v.get('missed_win_r', 0):.2f}R",
                        "net": f"{v.get('net', 0):+.2f}R",
                        L("حکم", "Verdict"): verd,
                    })
                if vrows:
                    st.dataframe(pd.DataFrame(vrows), width="stretch", hide_index=True)
    if _weak:
        st.subheader("👁️ " + L("در حال پایش (شواهد کافی نیست)", "Monitoring (not enough evidence)"))
        rows = [{"🤖": nm, "n": a["n"], "انتظاری" if LANG == "fa" else "Exp": f"{a['exp']:+.2f}R",
                 "PF": a["pf"]} for nm, a in sorted(_weak, key=lambda kv: kv[1]["exp"])]
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    if not _active and not _weak:
        st.success(L("هیچ پرونده‌ی فعالی نیست — همه‌ی ایجنت‌ها در محدوده‌ی سالم‌اند. ✅",
                     "No active dossiers — all agents are healthy. ✅"))

    st.caption(L("قواعد نسخه‌ها در core/dossier.py — آستانه‌ها بالای فایل و شفاف‌اند.",
                 "Prescription rules live in core/dossier.py — thresholds at the top, fully transparent."))

st.divider()
st.caption(L(f"🔬 محاسبه‌ی زنده از {_store.backend} · قواعد آزمایشگاه در core/agent_lab.py · نسخه‌های بهبود در core/dossier.py",
             f"🔬 Live computation from {_store.backend} · lab rules in core/agent_lab.py · prescriptions in core/dossier.py"))
