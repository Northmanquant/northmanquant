"""فارم و ایردراپ رایگان — داده‌ی واقعی، نه وعده
بازده واقعی DeFi از API رایگان DefiLlama + آزمایشگر ضدکلاهبرداری +
فهرست دست‌چین تست‌نت/ایردراپ با هزینه‌ی صفر. فلسفه: «رایگان + سود خوب +
مطمئن» با هم وجود ندارند — سود واقعی سرمایه، زمان یا مهارت می‌گیرد."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from core import opportunities as OP
from core.help import hint
from core.i18n import get_lang, setup_i18n, tr

st.set_page_config(page_title="فارم و ایردراپ | Farm & Airdrops", page_icon="🌱", layout="wide")
LANG = setup_i18n(page="p9")


def _L(fa_list: list, en_list: list) -> list:
    """انتخاب لیست بر اساس زبان — برای محتواهای طولانی که tr() رشته‌ای‌اند."""
    return en_list if LANG == "en" else fa_list


@st.cache_data(ttl=3600, show_spinner=False)
def _pools_cached() -> tuple:
    return OP.fetch_llama_pools()


@st.cache_data(ttl=86400, show_spinner=False)
def _sites_cached() -> dict:
    """نقشه‌ی slug→وب‌سایت رسمی — کش ۲۴ ساعته؛ خطا یعنی نقشه‌ی خالی (نه کرش)."""
    sites, _err = OP.fetch_project_urls()
    return sites


st.title("🌱 " + tr("فارم و ایردراپ رایگان — با داده‌ی واقعی", "Farm & Free Airdrops — real data only"))
hint(tr(
    "اینجا سه چیز هست: ① بازدهِ زنده‌ی استخرهای DeFi مستقیم از DefiLlama با تفکیک «APY واقعیِ کارمزدی» "
    "از «APY توکن پاداشِ ایمی‌شونده» و امتیازِ صداقت؛ ② یک آزمایشگر ضدکلاهبرداری که هر پروژه‌ای را با "
    "چک‌لیست وزن‌دار می‌سنجد؛ ③ فهرست تست‌نت‌های فعال با هزینه‌ی صفر (فقط زمان). قانون طلایی: "
    "«رایگان + سود خوب + مطمئن» با هم وجود ندارند — هر کس هر سه را قول داد، کلاهبردار است.",
    "Three things live here: ① live DeFi pool yields straight from DefiLlama, separating real fee APY "
    "from emitted reward APY, with an honesty score; ② a scam-checker with a weighted checklist; "
    "③ curated zero-cost testnet hunts. Golden rule: 'free + high profit + guaranteed' never coexist."))

t1, t2, t3 = st.tabs([tr("🌾 بازده واقعی", "🌾 Real yields"),
                      tr("🛡 آزمایشگر ضدکلاهبرداری", "🛡 Scam checker"),
                      tr("🪂 تست‌نت/ایردراپ رایگان", "🪂 Testnet/airdrop hunts")])

# --------------------------------------------------------------------------- #
# تب ۱ — بازده واقعی                                                          #
# --------------------------------------------------------------------------- #
with t1:
    rows, err = _pools_cached()
    if err:
        st.warning(tr(
            f"دریافت از DefiLlama الان پاسخ نداد ({err}) — صفحه به‌هرحال کار می‌کند؛ چند دقیقه بعد رفرش کن. "
            "مرجع زنده: defillama.com/yields",
            f"DefiLlama did not answer just now ({err}) — the page still works; retry in a few minutes."))
    if not rows:
        st.info(tr("هنوز داده‌ای نرسیده — بعد از رفرش دوباره امتحان کن.",
                   "No data yet — try again after a refresh."))
    else:
        c1, c2, c3, c4 = st.columns([1.1, 1, 1, 0.8])
        with c1:
            min_tvl_m = st.slider(tr("حداقل TVL (میلیون دلار)", "Min TVL ($M)"), 1, 100, 10,
                                  help=tr("استخرهای خیلی کوچک راحت rug می‌شوند — پیش‌فرض ۱۰ میلیون.",
                                          "Tiny pools are easy rug targets — default $10M."))
        with c2:
            max_apy = st.slider(tr("سقف APY نمایش (٪)", "Max APY shown (%)"), 20, 300, 80,
                                help=tr("APY بالاتر از این معمولاً ایمیِشن موقتی است که می‌ریزد.",
                                        "Beyond this, APY is usually temporary emission that collapses."))
        with c3:
            stable_only = st.toggle(tr("فقط استیبل‌کوین (بدون زیان ناپایدار)", "Stables only (no IL)"),
                                    value=True)
        with c4:
            top_n = st.slider(tr("تعداد", "Count"), 5, 40, 15)

        sel_chains = st.multiselect(tr("زنجیره‌ها (خالی = همه)", "Chains (empty = all)"),
                                    options=OP.top_chains(rows))
        picks = OP.honest_pools(rows, min_tvl=min_tvl_m * 1e6, stable_only=stable_only,
                                chains=sel_chains or None, max_apy=float(max_apy), top=top_n,
                                sites=_sites_cached())

        m1, m2, m3, m4 = st.columns(4)
        m1.metric(tr("استخرهای پایش‌شده", "Pools tracked"), f"{len(rows):,}")
        m2.metric(tr("پس از فیلتر صداقت", "After honesty filter"), f"{len(picks):,}")
        if picks:
            m3.metric(tr("بالاترین APY کارمزدی", "Top fee APY"),
                      f"{max(p['apy_base'] for p in picks):.1f}%")
            m4.metric(tr("بالاترین امتیاز صداقت", "Top honesty score"),
                      f"{max(p['score'] for p in picks)}")
        if picks:
            # ورود مستقیم به سه برتر — یک کلیک، داخل پروژه
            st.markdown(f"**🚀 {tr('سه برتر — ورود مستقیم', 'Top 3 — enter directly')}**")
            cols3 = st.columns(3)
            for i, p in enumerate(picks[:3]):
                with cols3[i]:
                    st.markdown(
                        f"<div dir='rtl' style='border:1px solid rgba(148,163,184,.35);border-radius:12px;"
                        f"padding:10px 12px;margin-bottom:4px'><b>{p['project']}</b><br>"
                        f"<span style='font-size:12px;opacity:.85'>{p['chain']} · {p['symbol']} · "
                        f"{tr('امتیاز', 'Score')} {p['score']} · APY {p['apy_base']:.1f}%</span></div>",
                        unsafe_allow_html=True)
                    _btn = (tr("🌾 ورود به بخش فارم", "🌾 Go to the farm page")
                            if p["site_kind"] == "app" else tr("🌐 ورود به پروژه", "🌐 Open project"))
                    st.link_button(_btn, p["site"] or p["url"], use_container_width=True)
                    st.link_button("📊 " + tr("صفحه‌ی استخر", "Pool page"),
                                   p["url"], use_container_width=True)

            sc_lbl = tr("امتیاز صداقت", "Honesty score")
            pool_lbl = tr("🔗 صفحه‌ی استخر", "🔗 Pool page")
            site_lbl = tr("🌐 ورود مستقیم", "🌐 Direct entry")
            df = pd.DataFrame([{
                tr("پروژه", "Project"): p["project"],
                tr("زنجیره", "Chain"): p["chain"],
                tr("دارایی", "Asset"): p["symbol"],
                tr("TVL (میلیون $)", "TVL ($M)"): round(p["tvl_usd"] / 1e6, 1),
                tr("APY کارمزدی ٪", "Fee APY %"): round(p["apy_base"], 2),
                tr("APY پاداش ٪", "Reward APY %"): round(p["apy_reward"], 2),
                tr("APY ۳۰روزه ٪", "30d APY %"): round(p["apy_mean30d"], 2),
                tr("نوسان", "Volatility"): round(p["sigma"], 3),
                tr("پیش‌بینی DefiLlama", "Prediction"): p["predicted"] or "—",
                sc_lbl: p["score"],
                pool_lbl: p["url"],
                site_lbl: p["site"],
            } for p in picks])
            st.dataframe(
                df.sort_values(sc_lbl, ascending=False),
                width="stretch", hide_index=True,
                column_config={
                    tr("TVL (میلیون $)", "TVL ($M)"): st.column_config.NumberColumn(format="%.1f"),
                    tr("APY کارمزدی ٪", "Fee APY %"): st.column_config.NumberColumn(format="%.2f"),
                    tr("APY پاداش ٪", "Reward APY %"): st.column_config.NumberColumn(format="%.2f"),
                    tr("APY ۳۰روزه ٪", "30d APY %"): st.column_config.NumberColumn(format="%.2f"),
                    sc_lbl: st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d"),
                    pool_lbl: st.column_config.LinkColumn(pool_lbl, display_text="باز کن ↗"),
                    site_lbl: st.column_config.LinkColumn(site_lbl, display_text="ورود ↗"),
                })
            st.caption(tr(
                "👆 «باز کن ↗» نمودار و تاریخچه‌ی بازده‌ی استخر را باز می‌کند؛ «ورود ↗» مستقیم می‌رود سراغ "
                "خود پروژه — برای پروژه‌های شناخته‌شده (Aave، Kamino، Pendle، Lido، Jupiter و…) این لینک "
                "مستقیم به صفحه‌ی اپ/فارم می‌رسد، نه صفحه‌ی شلوغِ خانه‌ی سایت. لینک‌ها از ایندکس رسمی "
                "DefiLlama و نقشه‌ی بررسی‌شده‌ی خودمان می‌آیند، نه گوگل؛ وقتی خالی است یعنی آدرس رسمی "
                "معتبری ثبت نشده — دنبالش نگرد، از همین‌جا بی‌خطر رد شو.",
                "👆 'Open ↗' shows the pool chart and yield history; 'Enter ↗' goes straight to the "
                "project — for well-known ones (Aave, Kamino, Pendle, Lido, Jupiter…) it lands directly "
                "on the app/farm page, not the busy marketing home. Links come from DefiLlama's official "
                "index and our vetted map, not Google; empty means no verified official address — don't "
                "hunt it, safely skip it."))
            st.caption(tr(
                "🌾 APY کارمزدی = سودِ واقعی از کارمزد/نرخ وام (همان که وارد رتبه می‌شود) · APY پاداش = "
                "توکن ایمی‌شونده که معمولاً به‌محض فروش می‌ریزد و در امتیاز لحاظ نشده · نوسان (sigma) "
                "بزرگ‌تر یعنی بازده دنس‌سویی‌ست · «Down» یعنی خود DefiLlama انتظار افت بازده دارد.",
                "🌾 Fee APY = real yield from fees/lending rates (what is ranked) · Reward APY = emitted "
                "token that usually dumps on sale, not ranked · larger sigma = swingy yield · 'Down' = "
                "DefiLlama itself expects the yield to fall."))
            st.caption(tr(
                "مقایسه: سپرده‌ی دلاری بانکی ≈ ۰-۵٪ سالانه — بازده ۳-۸٪ استیبل‌های بلوچیپ واقعی است؛ "
                "هر عددی خیلی بالاتر، یعنی ریسکی که هنوز ندیده‌ای. صفحه‌ی هر استخر: defillama.com/yields",
                "For scale: bank USD deposits ≈ 0-5%/yr — 3-8% on blue-chip stables is real; anything far "
                "higher hides risk you have not seen yet. Pool pages: defillama.com/yields"))
        else:
            st.info(tr("با این فیلترها استخری پیدا نشد — سقف APY یا حداقل TVL را بازتر کن.",
                       "No pool passes these filters — relax the APY cap or TVL floor."))

# --------------------------------------------------------------------------- #
# تب ۲ — آزمایشگر ضدکلاهبرداری                                                #
# --------------------------------------------------------------------------- #
with t2:
    st.caption(tr(
        "پروژه‌ای که می‌خواهی امتحانش کنی را در ذهنت بگیر و به ۱۰ سؤال جواب بده — «نمی‌دانم» هم پاسخ "
        "بی‌طرف است. اگر «بله»ی اول برایت پیش آمد، اصلاً ادامه نده.",
        "Pick the project you are evaluating and answer 10 questions — 'I don't know' is neutral. "
        "If the first red flag applies, stop right there."))
    answers: dict = {}
    gq1, gq2 = st.columns(2)
    for i, q in enumerate(OP.SCAM_QUESTIONS):
        with (gq1 if i % 2 == 0 else gq2):
            icon = "🔴 " if q["kind"] == "red" else "🟢 "
            answers[q["key"]] = st.radio(
                icon + tr(q["q"], q["en"]),
                [OP.YES, OP.NO, OP.UNKNOWN], index=2, key=f"scam_{q['key']}",
                horizontal=True)
    if st.button("⚖️ " + tr("محاسبه‌ی سطح خطر", "Compute risk"), type="primary"):
        res = OP.scam_check(answers)
        st.markdown(
            f"<div dir='rtl' style='border:2px solid {res['color']};border-radius:14px;padding:14px 16px;"
            f"background:rgba(148,163,184,.05)'>"
            f"<div style='display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px'>"
            f"<span style='font-size:19px;font-weight:800;color:{res['color']}'>{res['level']}</span>"
            f"<span style='font-family:ui-monospace,monospace;font-size:15px;color:{res['color']}'>"
            f"{tr('خطر', 'Risk')}: {res['risk']}/100</span></div>"
            f"<div style='margin-top:8px;font-size:14px'>{res['verdict']}</div></div>",
            unsafe_allow_html=True)
        st.progress(res["risk"] / 100.0)
        for tip in res["tips"]:
            st.markdown(f"- {tip}")
    st.divider()
    st.markdown(f"**🚩 {tr('الگوهای رایج کلاهبرداری «ماینینگ/فارم رایگان»', 'Common \"free mining/farm\" scam patterns')}**")
    for flag in _L(
        [
            "«ماینینگ ابری رایگان» که برای برداشت، کارمزد فعال‌سازی می‌خواهد — سودِ روی صفحه فقط طعمه است.",
            "سایت‌هایی که فقط با دعوت‌نامه باز می‌شوند و «رتبه‌ی VIP» با سپرده‌ی بیشتر می‌دهند — هرمی.",
            "بات تلگرامی که می‌گوید «تپ کن، ساعت ۱۲ ایردراپ می‌ده» و آخرش ورود به کیف پول را می‌خواهد.",
            "قراردادی که آدرسش را فقط خودشان می‌دهند و در اکسپلورر مستقل TVL‌شان صفر است.",
            "هر جایی که Seed Phrase برای «مهاجرت/آپگرید» خواسته شد — ۱۰۰٪ سرقت.",
        ],
        [
            "'Free cloud mining' that charges an activation fee to withdraw — the on-screen profit is bait.",
            "Invite-only sites granting 'VIP tiers' for bigger deposits — pyramid schemes.",
            "Telegram bots saying 'tap now, airdrop at 12' that end up asking for your wallet seed.",
            "Contracts whose address is only published by themselves, with zero TVL on independent explorers.",
            "Anywhere a seed phrase is requested for 'migration/upgrade' — 100% theft.",
        ],
    ):
        st.markdown(f"- 🚩 {flag}")
    st.divider()
    st.markdown(f"**🧪 {tr('خودت چک کن — ابزارهای راستی‌آزمایی با لینک مستقیم', 'Check it yourself — verification tools with direct links')}**")
    st.caption(tr(
        "به جای اینکه اسم پروژه را در گوگل بزنی (جایی که اولین نتیجه‌ها اغلب سایت‌های فیشینگِ تبلیغ‌شده‌اند)، "
        "از همین‌جا با یک کلیک وارد ابزار رسمیِ هر بررسی شو:",
        "Instead of googling the project name (where top results are often advertised phishing sites), "
        "click straight into the official tool for each check:"))
    for r in range(0, len(OP.VERIFY_TOOLS), 2):
        tc1, tc2 = st.columns(2)
        for j, col in enumerate((tc1, tc2)):
            idx = r + j
            if idx >= len(OP.VERIFY_TOOLS):
                break
            t = OP.VERIFY_TOOLS[idx]
            with col:
                st.link_button(f"🔎 {t['name']}", t["url"], use_container_width=True)
                st.markdown(
                    f"<div dir='rtl' style='font-size:13px;opacity:.9;margin-top:-6px'>"
                    f"{tr(t['what'], t['what_en'])}</div>", unsafe_allow_html=True)

# --------------------------------------------------------------------------- #
# تب ۳ — تست‌نت/ایردراپ                                                       #
# --------------------------------------------------------------------------- #
with t3:
    st.caption(tr(
        "تنها دسته‌ی «رایگانِ واقعی» با سابقه‌ی پرداخت: تست‌نت‌ها — روی شبکه‌ی آزمایشی با توکنِ بی‌ارزش "
        "بازی می‌کنی؛ اگر پروژه توکن واقعی بدهد، تسترهای اولیه سهم می‌گیرند. تضمینی نیست — هر ورودی یک "
        "بلیت لاتاری است. هزینه‌ی واقعی: زمان.",
        "The only genuinely 'free' category with payout history: testnets — you play on an experimental "
        "network with valueless tokens; if the project launches, early testers get an allocation. Not "
        "guaranteed — each entry is a lottery ticket. Real cost: your time."))
    st.link_button("🪂 " + tr("ورود به فهرست زنده‌ی تست‌نت‌ها (مرجع بررسی‌شده)",
                             "Open the live testnet list (vetted source)"),
                   OP.AIRDROP_SOURCE_URL, use_container_width=True)
    st.dataframe(
        pd.DataFrame(OP.testnet_rows()), width="stretch", hide_index=True,
        column_config={"منبع": st.column_config.LinkColumn(
            "منبع" if LANG != "en" else "Source", display_text="airdropalert ↗")})
    st.warning(tr(
        "🧭 «چطور وارد پروژه شوم؟» — روی دکمه یا ستون «airdropalert ↗» کلیک کن؛ در صفحه‌ی مرجع، نام همان "
        "پروژه را پیدا کن و از لینکِ رسمیِ داخل همان صفحه واردش شو. عمداً لینک مستقیمِ دست‌ساز اینجا "
        "نمی‌گذاریم: دامنه‌های جعلی (فیشینگ) در دنیای ایردراپ بیداد می‌کنند و یک حرف جابه‌جا در آدرس یعنی "
        "کیف پول خالی. همیشه دامنه را با چشم خودت چک کن.",
        "🧭 'How do I enter the project?' — click the button or the 'airdropalert ↗' column; find the "
        "project name on the source page and enter via the official link inside it. We deliberately "
        "avoid hand-written direct links: fake (phishing) domains run rampant in airdrops and one "
        "swapped letter in a URL means an emptied wallet. Always read the domain with your own eyes."))
    h1, h2 = st.columns(2)
    with h1:
        st.markdown(f"**🧭 {tr('شروع از صفر', 'Starting from zero')}**")
        for step in _L(OP.STARTER_GUIDE, OP.STARTER_GUIDE_EN):
            st.markdown(f"- {step}")
    with h2:
        st.markdown(f"**🛰 {tr('قواعد ضدسفل (Sybil)', 'Anti-Sybil rules')}**")
        for rule in _L(OP.SYBIL_RULES, OP.SYBIL_RULES_EN):
            st.markdown(f"- {rule}")
    st.caption(tr(
        f"فهرست دست‌چین‌شده (بررسی: نوامبر ۲۰۲۶) — منبع زنده: {OP.AIRDROP_SOURCE_URL} · ترتیب هیچ‌گونه "
        "توصیه‌ای نیست؛ هر هفته دوباره چک کن.",
        f"Hand-curated (checked: Nov 2026) — live source: {OP.AIRDROP_SOURCE_URL} · ordering is not a "
        "recommendation; re-check weekly."))

st.warning(tr(f"⚠️ {OP.DISCLAIMER}", f"⚠️ {OP.DISCLAIMER_EN}"))
