"""فارم و ماینینگ — اول دسته‌بندی، بعد ورود
دسته‌بندی ۴گانه به درخواست کاربر («بیشترشون رایگان نیستن… گیج نشن و دنبالش
نگردن»): هر فرصت با برچسب هزینه (🟢 رایگان / 🔴 پولی) و در تبِ خودش:
  🌾 فارمینگ — پولی: بازده واقعی DeFi از DefiLlama (واریز سرمایه لازم است)
  ⛏️ ماینینگ — سه دنیا: موبایلی (رایگان) / هاردواری (پولی) / ابری (پرخطر)
  🎁 رایگان — تست‌نت/ایردراپ: هزینه‌ی صفر، فقط زمان
  🤖 میدان کاوشگرها — ۵ ایجنت فرصت‌ها را تست می‌کنند، داور بهترین برنامه را
     انتخاب می‌کند؛ برنامه‌ی برنده = چک‌لیستِ اجرای دستیِ کاربر (ایجنت‌ها
     کلیک/لاگین نمی‌کنند — ضدسفل + امنیت کلید)
  🛡 ضدکلاهبرداری — چک‌لیست + ابزارهای راستی‌آزمایی
فلسفه: «رایگان + سود خوب + مطمئن» با هم وجود ندارند — سود واقعی سرمایه،
زمان یا مهارت می‌گیرد."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from core import opportunities as OP
from core import scouts as SC
from core.help import hint
from core.i18n import get_lang, setup_i18n, tr

st.set_page_config(page_title="فارم و ماینینگ | Farm & Mining", page_icon="🌱", layout="wide")
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


st.title("🌱 " + tr("فارم و ماینینگ — اول دسته‌بندی، بعد ورود",
                    "Farm & Mining — categories first, then enter"))
hint(tr(
    "چهار دسته، همان‌طور که از هر چیزی انتظار داری: 🌾 فارمینگ (🔴 پولی — استخرهای بازده واقعی که "
    "برای شروع باید سرمایه واریز کنی) · ⛏️ ماینینگ (سه دنیای متفاوت: موبایلیِ 🟢 رایگان، هاردواریِ "
    "🔴 پولی، ابریِ 🔴 پرخطر) · 🎁 رایگان (تست‌نت و ایردراپ — بدون حتی یک دلار، فقط زمان) · 🛡 "
    "ضدکلاهبرداری. نشانِ 🟢/🔴 کنار هر چیز می‌گوید از تو پول می‌خواهند یا زمان. قانون طلایی: "
    "«رایگان + سود خوب + مطمئن» با هم وجود ندارند — هر کس هر سه را قول داد، کلاهبردار است.",
    "Four categories: 🌾 farming (🔴 paid yield pools — you must deposit), ⛏️ mining (three different "
    "worlds: 🟢 free mobile, 🔴 paid hardware, 🔴 risky cloud), 🎁 free (testnets & airdrops — zero "
    "dollars, time only) and 🛡 anti-scam. The 🟢/🔴 tag on everything says whether it wants your "
    "money or your time. Golden rule: 'free + high profit + guaranteed' never coexist."))

# --------------------------------------------------------------------------- #
# نوار دسته‌بندی — چهار کارت، همان چهار کلمه‌ای که کاربر خواست                 #
# --------------------------------------------------------------------------- #
_chips = [
    ("🌾", tr("فارمینگ", "Farming"),
     tr("🔴 پولی — سرمایه لازم", "🔴 Paid — needs capital"), "#ef4444",
     tr("استخرهای بازده واقعی؛ برای شروع باید واریز کنی.",
        "Real yield pools; you must deposit to start.")),
    ("⛏️", tr("ماینینگ", "Mining"),
     tr("🟢 موبایلی / 🔴 هاردواری و ابری", "🟢 mobile / 🔴 hardware & cloud"), "#f59e0b",
     tr("سه دنیای متفاوت با یک نام — تفاوتشان را بدان.",
        "Three different worlds, one name — know the difference.")),
    ("🎁", tr("رایگان", "Free"),
     tr("🟢 بدون حتی ۱ دلار — فقط زمان", "🟢 zero dollars — time only"), "#16a34a",
     tr("تست‌نت و ایردراپ: پول نمی‌خواهد، تضمین هم ندارد.",
        "Testnets and airdrops: no money, no guarantees.")),
    ("🔴", tr("پولی", "Paid"),
     tr("اول پول، بعد سود", "money first, profit later"), "#ef4444",
     tr("هر بخشی با این نشان یعنی سرمایه لازم دارد.",
        "Anything with this tag needs capital.")),
]
for (_ic, _ti, _co, _clr, _de), _c in zip(_chips, st.columns(4)):
    with _c:
        st.markdown(
            f"<div dir='rtl' style='border:1px solid rgba(148,163,184,.35);border-radius:12px;"
            f"padding:8px 10px;margin-bottom:2px'><b>{_ic} {_ti}</b><br>"
            f"<span style='font-size:12px;font-weight:800;color:{_clr}'>{_co}</span><br>"
            f"<span style='font-size:12px;opacity:.85'>{_de}</span></div>",
            unsafe_allow_html=True)

t_farm, t_mine, t_free, t_scout, t_scam = st.tabs([
    tr("🌾 فارمینگ — پولی (سرمایه لازم)", "🌾 Farming — paid (needs capital)"),
    tr("⛏️ ماینینگ — رایگان یا پولی", "⛏️ Mining — free or paid"),
    tr("🎁 رایگان — بدون سرمایه", "🎁 Free — zero capital"),
    tr("🤖 میدان کاوشگرها — بهترین را انتخاب کن", "🤖 Scout arena — let the best plan win"),
    tr("🛡 ضدکلاهبرداری", "🛡 Anti-scam"),
])

# --------------------------------------------------------------------------- #
# تب ۱ — فارمینگ (پولی)                                                       #
# --------------------------------------------------------------------------- #
with t_farm:
    st.error(tr(
        "🔴 این بخش پولی است — برای شروع در هر استخر باید سرمایه واریز کنی. «رایگان» اینجا فقط یعنی "
        "نمایشِ داده رایگان است، نه شرکتِ بدون پول. قاعده: با کمترین مبلغ شروع کن و اولین برداشت را "
        "هرچه زودتر تست کن.",
        "🔴 This section is paid — every pool requires a deposit to enter. 'Free' here only means the "
        "data display is free, not that participation costs nothing. Rule: start with the smallest "
        "amount and test your first withdrawal as soon as possible."))
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
                        f"{tr('امتیاز', 'Score')} {p['score']} · APY {p['apy_base']:.1f}%</span><br>"
                        f"<span style='font-size:12px;font-weight:800;color:#ef4444'>{OP.COST_PAID} — "
                        f"{tr('سرمایه لازم', 'capital needed')}</span></div>",
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
# تب ۲ — ماینینگ (سه دنیا)                                                    #
# --------------------------------------------------------------------------- #
with t_mine:
    st.caption(tr(
        "کلمه‌ی «ماینینگ» سه دنیای کاملاً متفاوت را پوشش می‌دهد — اشتباه گرفتنشان گران تمام می‌شود. "
        "اول دسته را تشخیص بده، بعد تصمیم بگیر. هیچ‌کدام از این سه، «پولِ آسان» نیستند.",
        "'Mining' covers three completely different worlds — confusing them is expensive. Identify the "
        "category first, decide second. None of the three is 'easy money'."))
    for _col, _k in zip(st.columns(3), OP.MINING_KINDS):
        with _col:
            st.markdown(
                f"<div dir='rtl' style='border:1px solid rgba(148,163,184,.35);border-radius:12px;"
                f"padding:10px 12px'><b>{_k['icon']} {tr(_k['title'], _k['title_en'])}</b><br>"
                f"<span style='font-size:13px;font-weight:800;color:{_k['color']}'>"
                f"{tr(_k['cost'], _k['cost_en'])}</span><br>"
                f"<span style='font-size:12px;opacity:.9'>{tr(_k['what'], _k['what_en'])}</span></div>",
                unsafe_allow_html=True)
    st.divider()
    for _k in OP.MINING_KINDS:
        st.markdown(f"**{_k['icon']} {tr(_k['title'], _k['title_en'])} · "
                    f"{tr(_k['cost'], _k['cost_en'])} — {tr(_k['verdict'], _k['verdict_en'])}**")
        for _r in _L(_k["rules"], _k["rules_en"]):
            st.markdown(f"- {_r}")
    st.info(tr(
        "⚖️ قبل از هر ورود: تب «ضدکلاهبرداری» را کامل کن — ۱۰ سؤال + ابزارهای راستی‌آزمایی با لینک مستقیم.",
        "⚖️ Before entering anything: complete the Anti-scam tab — 10 questions + verification tools "
        "with direct links."))

# --------------------------------------------------------------------------- #
# تب ۳ — رایگان (تست‌نت/ایردراپ)                                              #
# --------------------------------------------------------------------------- #
with t_free:
    st.success(tr(
        "🟢 رایگان — بدون حتی یک دلار؛ هزینه‌ی واقعی فقط زمان تو است. هر «فرصت رایگانی» که از تو پول "
        "خواست، رایگان نیست — برو تب «ضدکلاهبرداری».",
        "🟢 Free — not even one dollar; the real cost is your time. Any 'free opportunity' that asks "
        "for money is not free — go to the Anti-scam tab."))
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
    st.markdown(tr(
        "⛏️ ماینینگ موبایلی هم بدون پول است — اما بلیت لاتاری است؛ قواعدش در تب «ماینینگ».",
        "⛏️ Mobile mining is free too — but a lottery ticket; its rules live in the Mining tab."))
    st.caption(tr(
        f"فهرست دست‌چین‌شده (بررسی: نوامبر ۲۰۲۶) — منبع زنده: {OP.AIRDROP_SOURCE_URL} · ترتیب هیچ‌گونه "
        "توصیه‌ای نیست؛ هر هفته دوباره چک کن.",
        f"Hand-curated (checked: Nov 2026) — live source: {OP.AIRDROP_SOURCE_URL} · ordering is not a "
        "recommendation; re-check weekly."))

# --------------------------------------------------------------------------- #
# تب ۴ — میدان کاوشگرها (ایجنت‌ها)                                           #
# --------------------------------------------------------------------------- #
with t_scout:
    st.caption(tr(
        "۵ ایجنت با استراتژی‌های متفاوت روی همین داده‌ی زنده‌ی صفحه مسابقه می‌دهند: هرکدام فرصت‌ها را "
        "تست می‌کند (استخر زنده است؟ پیش‌بینی Down؟ نوسان بالا؟ در بودجه‌ی پول/زمانش جا می‌شود؟)، "
        "برنامه‌ی شخصی می‌سازد و داورِ قطعی بهترین را انتخاب می‌کند. برنامه‌ی برنده = چک‌لیستِ اجرای تو.",
        "5 agents with different strategies compete on this page's live data: each tests every "
        "opportunity (pool alive? prediction Down? high sigma? fits its money/time budget?), builds "
        "a personal plan, and a deterministic judge picks the best. The winner's plan = your checklist."))
    st.info(tr(
        "🧑‍⚖️ مرزِ صادقانه: ایجنت‌ها «انجام نمی‌دهند» — کلیک، لاگین و کیف پول فقط با توست. چرا؟ "
        "سیستم‌های ضدسفلِ خودِ پروژه‌ها بات‌ها را یکجا حذف می‌کنند و کلیدِ داخل اپ یعنی خطر. "
        "ایجنت تست می‌کند و انتخاب می‌کند؛ اجرا با انسان است — این همان کاری است که نتیجه می‌دهد.",
        "🧑‍⚖️ Honest boundary: agents do not execute — clicking, login and wallets stay human-only. "
        "Anti-Sybil systems wipe bots in one sweep and keys inside an app are a liability. Agents "
        "test and choose; humans execute — that is what actually pays."))
    if st.button("🚀 " + tr("اجرای میدان — مسابقه روی داده‌ی زنده", "Run the arena — race on live data"),
                 type="primary"):
        _rows_s, _err_s = _pools_cached()
        _judged = SC.run_arena(_rows_s, OP.TESTNET_HUNTS)
        if _err_s:
            st.caption(tr(
                f"⚠️ داده‌ی استخرها الان نرسید ({_err_s}) — مسابقه با تست‌نت‌های محلی برگزار شد؛ "
                "چند دقیقه بعد دوباره اجرا کن تا استخرها هم در مسابقه باشند.",
                f"⚠️ Pool data did not arrive ({_err_s}) — the race ran on local testnets only; rerun "
                "in a few minutes to include pools."))
        for _i, _r in enumerate(_judged):
            _a, _pl = _r["agent"], _r["plan"]
            _hdr = (f"🏆 {_a['icon']} {tr(_a['name'], _a['name_en'])} — {_r['score']}/100"
                    if _i == 0 else f"{_a['icon']} {tr(_a['name'], _a['name_en'])} — {_r['score']}/100")
            _box = st.container() if _i == 0 else st.expander(_hdr)
            with _box:
                if _i == 0:
                    st.markdown(f"### 🏆 {tr(_a['name'], _a['name_en'])} — {_r['score']}/100")
                st.progress(min(int(_r["score"]), 100) / 100.0)
                st.caption(f"{tr(_a['style'], _a['style_en'])} · "
                           f"{tr(_r['verdict'], _r['verdict_en'])}")
                if _pl["steps"]:
                    st.markdown(tr(
                        f"**برنامه ({_pl['total_time']} دقیقه در روز):**",
                        f"**The plan ({_pl['total_time']} min/day):**"))
                    for _j, _s in enumerate(_pl["steps"], 1):
                        _cfa, _cen = SC.cost_for(_s["kind"])
                        _cost = _cfa if LANG != "en" else _cen
                        st.markdown(
                            f"- **{_j}) {tr(_s['title'], _s['title_en'])}** · "
                            f"{_cost} · ⏱ ~{_s['time_min']} دقیقه — {tr(_s['why'], _s['why_en'])}")
                else:
                    st.info(tr("برنامه‌ای ساخته نشد — داده‌ی ورودی خالی بود.",
                               "No plan was built — the input data was empty."))
                for _n in _L(_pl.get("notes", []), _pl.get("notes_en", [])):
                    st.caption(f"ℹ️ {_n}")
                if _r["flags"]:
                    st.caption("🚩 " + tr(
                        "فلگ‌های داور: " + "، ".join(_r["flags"]),
                        "Judge flags: " + ", ".join(_r["flags"])))
    st.caption(tr(
        "چرا باتِ اجرا نمی‌سازیم؟ تجربه‌ی کل صنعت: کیف پول‌های هم‌الگو (اسکریپتی) توسط سیستم ضدسفل "
        "یکجا حذف می‌شوند و چند ماه فعالیت، صفر می‌شود؛ به‌علاوه هیچ اپی نباید کلید تو را ببیند. "
        "برنامه‌ی ایجنت + اجرای دستیِ تو = امن، انسانی و مؤثر.",
        "Why no execution bot? Industry-wide experience: look-alike scripted wallets get wiped by "
        "anti-Sybil systems in one sweep, and no app should ever see your keys. Agent plan + your "
        "manual execution = safe, human, effective."))

# --------------------------------------------------------------------------- #
# تب ۵ — ضدکلاهبرداری                                                         #
# --------------------------------------------------------------------------- #
with t_scam:
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

st.warning(tr(f"⚠️ {OP.DISCLAIMER}", f"⚠️ {OP.DISCLAIMER_EN}"))
