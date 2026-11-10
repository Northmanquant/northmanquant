"""فرصت‌های رایگان + کارگاه کیفیت — چیدمانِ تمیزِ سه‌تبی
========================================================
بازطراحی به درخواست کاربر: «خوشم نیومد، زیادی شلوغ شد؛ اون بخش‌ها کلا حذفش کن
و هرچیزی که مربوط بهش میشه. بریم به فکر پروژه‌ی خودمون باشیم، کیفیتش رو ببریم
بالا.» — همه‌ی بخش‌های بیرونی و پولی حذف شدند؛ صفحه اکنون فقط دو کار دارد:
فرصت‌های بی‌هزینه و کیفیتِ خودِ پروژه.

سه تب، هر کدام یک کارِ روشن:
  🎁 رایگان — تست‌نت/ایردراپ: هزینه‌ی صفر (فقط زمان) + قواعد ضدسفل + راهنمای شروع
  🤖 کارگاه کیفیت — ۵ ایجنت روی «پروژه‌ی خودمان»: مخزنِ NorthmanQuant واقعاً
     اسکن می‌شود، طرحِ بهبودِ کیفیت ساخته می‌شود و داور بهترین طرح را برمی‌گزیند
  🛡 ضدکلاهبرداری — چک‌لیست ۱۰ سؤالی + ابزارهای راستی‌آزمایی با لینک مستقیم
فلسفه: «رایگان + سود خوب + مطمئن» با هم وجود ندارند — و کیفیت هم معجزه ندارد:
سنجشِ مداوم + اصلاحِ کوچکِ هفتگی."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from core import opportunities as OP
from core import scouts as SC
from core.help import hint
from core.i18n import get_lang, setup_i18n, tr

st.set_page_config(page_title="فرصت‌های رایگان | Free Opportunities",
                   page_icon="🎁", layout="wide")
LANG = setup_i18n(page="p9")


def _L(fa_list: list, en_list: list) -> list:
    """انتخاب لیست بر اساس زبان — برای محتواهای طولانی که tr() رشته‌ای‌اند."""
    return en_list if LANG == "en" else fa_list


st.title("🎁 " + tr("فرصت‌های رایگان — و کارگاه کیفیتِ پروژه‌ی خودمان",
                    "Free opportunities — and our own project's quality workshop"))
hint(tr(
    "سه کارِ روشن: 🎁 رایگان (تست‌نت و ایردراپ — بدون حتی یک دلار، فقط زمان؛ تضمین هم صفر) · "
    "🤖 کارگاه کیفیت (۵ ایجنتِ پروژه‌ی خودمان — مخزنِ NorthmanQuant را واقعاً اسکن می‌کنند و طرحِ "
    "بهبودِ کیفیت می‌دهند) · 🛡 ضدکلاهبرداری (۱۰ سؤال + ابزارهای رسمی). نشانِ 🟢 یعنی فقط زمان "
    "می‌خواهد، نه پول. قانون طلایی: «رایگان + سود خوب + مطمئن» با هم وجود ندارند — و کیفیت هم "
    "معجزه ندارد: سنجشِ هفتگی + اصلاحِ کوچک.",
    "Three clear jobs: 🎁 free (testnets & airdrops — zero dollars, time only) · 🤖 quality workshop "
    "(5 agents of our own project — they really scan the NorthmanQuant repo and propose quality plans) · "
    "🛡 anti-scam (10 questions + official tools). The 🟢 tag means time, not money. Golden rule: "
    "'free + high profit + guaranteed' never coexist — and quality has no miracle either: weekly "
    "measurement plus small fixes."))

# --------------------------------------------------------------------------- #
# نوار کارت‌ها — سه کارت                                                      #
# --------------------------------------------------------------------------- #
_chips = [
    ("🎁", tr("رایگان", "Free"),
     tr("🟢 بدون حتی ۱ دلار — فقط زمان", "🟢 zero dollars — time only"), "#16a34a",
     tr("تست‌نت و ایردراپ: پول نمی‌خواهد، تضمین هم ندارد.",
        "Testnets and airdrops: no money, no guarantees.")),
    ("🤖", tr("کارگاه کیفیت", "Quality workshop"),
     tr("۵ ایجنت روی پروژه‌ی خودمان", "5 agents on our own project"), "#2563eb",
     tr("مخزن واقعی اسکن می‌شود؛ بهترین طرحِ بهبود برنده است.",
        "The real repo gets scanned; the best improvement plan wins.")),
    ("🛡", tr("ضدکلاهبرداری", "Anti-scam"),
     tr("اول چک، بعد ورود", "check first, enter later"), "#ef4444",
     tr("هر بخشی که پول و عجله بخواهد، مشکوک است.",
        "Anything demanding money and urgency is suspect.")),
]
for (_ic, _ti, _co, _clr, _de), _c in zip(_chips, st.columns(3)):
    with _c:
        st.markdown(
            f"<div dir='rtl' style='border:1px solid rgba(148,163,184,.35);border-radius:12px;"
            f"padding:8px 10px;margin-bottom:2px'><b>{_ic} {_ti}</b><br>"
            f"<span style='font-size:12px;font-weight:800;color:{_clr}'>{_co}</span><br>"
            f"<span style='font-size:12px;opacity:.85'>{_de}</span></div>",
            unsafe_allow_html=True)

t_free, t_scout, t_scam = st.tabs([
    tr("🎁 رایگان — تست‌نت و ایردراپ", "🎁 Free — testnets & airdrops"),
    tr("🤖 کارگاه کیفیت — ایجنت‌ها روی پروژه‌ی خودمان",
       "🤖 Quality workshop — agents on our own project"),
    tr("🛡 ضدکلاهبرداری", "🛡 Anti-scam"),
])

# --------------------------------------------------------------------------- #
# تب ۱ — رایگان (تست‌نت/ایردراپ)                                              #
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
    st.caption(tr(
        f"فهرست دست‌چین‌شده (بررسی: نوامبر ۲۰۲۶) — منبع زنده: {OP.AIRDROP_SOURCE_URL} · ترتیب هیچ‌گونه "
        "توصیه‌ای نیست؛ هر هفته دوباره چک کن.",
        f"Hand-curated (checked: Nov 2026) — live source: {OP.AIRDROP_SOURCE_URL} · ordering is not a "
        "recommendation; re-check weekly."))

# --------------------------------------------------------------------------- #
# تب ۲ — کارگاه کیفیت (ایجنت‌ها روی پروژه‌ی خودمان)                            #
# --------------------------------------------------------------------------- #
with t_scout:
    st.caption(tr(
        "اینجا ایجنت‌ها دنبال فرصت بیرونی نمی‌گردند — روی «پروژه‌ی خودمان» کار می‌کنند: مخزنِ "
        "NorthmanQuant را اسکن می‌کنند (فایل‌ها، خط‌ها، تست‌ها، TODOها، پوششِ fail-soft و کش و "
        "مستندسازی) و هر کدام با استراتژیِ خودش یک «طرحِ بهبودِ کیفیت» می‌سازند؛ داور طرح‌ها را نمره "
        "می‌دهد و بهترین طرح = نقشه‌ی کیفیتِ همین هفته.",
        "Here agents don't hunt external opportunities — they work on our own project: they scan the "
        "NorthmanQuant repo (files, lines, tests, TODOs, fail-soft/cache/docs coverage) and each builds "
        "a 'quality improvement plan' with its own strategy; the judge scores them and the best plan = "
        "this week's quality map."))
    st.success(tr(
        "🌿 قانون کارگاه: بودجه‌ی صفر — همه‌ی گام‌ها فقط زمان و دقت‌اند. هر طرحی که گامِ پولی بگذارد "
        "(API پولی، سرور اجاره‌ای، خرید داده) از داور ۴۵ نمره جریمه می‌گیرد؛ کیفیت با پول خریدنی نیست.",
        "🌿 Workshop law: zero budget — every step costs only time and care. Any plan with a paid step "
        "(paid API, rented server, bought data) takes a 45-point penalty; quality is not bought."))
    st.info(tr(
        "🧑‍⚖️ مرزِ صادقانه: ایجنت‌ها کد را تغییر نمی‌دهند — اسکن می‌کنند، نقشه می‌کشند و داوری می‌کنند؛ "
        "اجرا با انسان است. اسکن کاملاً آفلاین است و هیچ فایلی دست نمی‌خورد.",
        "🧑‍⚖️ Honest boundary: agents never modify code — they scan, map and judge; execution is human. "
        "The scan is fully offline and touches no file."))
    if st.button("🚀 " + tr("اجرای کارگاه — اسکن مخزن و مسابقه",
                            "Run the workshop — scan the repo and race"), type="primary"):
        _scan = SC.repo_scan()
        if not _scan.get("files"):
            st.warning(tr("اسکنِ مخزن چیزی پیدا نکرد — دوباره اجرا کن.",
                          "The repo scan found nothing — run it again."))
        else:
            _m1, _m2, _m3, _m4 = st.columns(4)
            _m1.metric(tr("فایل‌های پایتون", "Python files"), SC.fa_num(_scan["n_files"]))
            _m2.metric(tr("خط‌های کد", "Lines of code"), SC.fa_num(_scan["n_lines"]))
            _m3.metric(tr("اسکریپت‌های تست", "Test scripts"), SC.fa_num(_scan["n_tests"]))
            _m4.metric(tr("TODOهای باز", "Open TODOs"), SC.fa_num(_scan["n_todo"]))
            _judged = SC.run_arena(_scan)
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
                            f"**طرح ({_pl['total_time']} دقیقه در هفته):**",
                            f"**The plan ({_pl['total_time']} min/week):**"))
                        for _j, _s in enumerate(_pl["steps"], 1):
                            _cfa, _cen = SC.cost_for(_s["kind"])
                            _afa, _aen = SC.area_for(_s["area"])
                            _cost = _cfa if LANG != "en" else _cen
                            _area = _afa if LANG != "en" else _aen
                            st.markdown(
                                f"- **{_j}) {tr(_s['title'], _s['title_en'])}** · {_area} · {_cost} · "
                                f"⏱ ~{_s['time_min']} دقیقه · 🎯 `{_s['target']}` — "
                                f"{tr(_s['why'], _s['why_en'])}")
                    else:
                        st.info(tr("طرحی ساخته نشد — اسکن خالی بود.",
                                   "No plan was built — the scan was empty."))
                    for _n in _L(_pl.get("notes", []), _pl.get("notes_en", [])):
                        st.caption(f"ℹ️ {_n}")
                    if _r["flags"]:
                        st.caption("🚩 " + tr(
                            "فلگ‌های داور: " + "، ".join(_r["flags"]),
                            "Judge flags: " + ", ".join(_r["flags"])))
    st.caption(tr(
        "چرا ایجنت مستقیم کد را عوض نمی‌کند؟ تغییرِ بی‌تست، پروژه را شکننده می‌کند؛ نقشه‌ی ایجنت + "
        "اجرای آگاهانه‌ی تو + تستِ کاملِ قبل از پوش = کیفیتِ پایدار. اسکن هر بار که دکمه را بزنی تازه "
        "انجام می‌شود — عددها همیشه واقعی‌اند.",
        "Why doesn't the agent edit code directly? Untested change makes the repo fragile; agent map + "
        "your conscious execution + full tests before push = durable quality. The scan re-runs on every "
        "button press — the numbers are always real."))

# --------------------------------------------------------------------------- #
# تب ۳ — ضدکلاهبرداری                                                         #
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
    st.markdown(f"**🚩 {tr('الگوهای رایج کلاهبرداری «سودِ آسان»', 'Common \"easy profit\" scam patterns')}**")
    for flag in _L(
        [
            "«سود روزانه‌ی ثابت» که برای برداشت، کارمزد فعال‌سازی می‌خواهد — سودِ روی صفحه فقط طعمه است.",
            "سایت‌هایی که فقط با دعوت‌نامه باز می‌شوند و «رتبه‌ی VIP» با سپرده‌ی بیشتر می‌دهند — هرمی.",
            "بات تلگرامی که می‌گوید «تپ کن، ساعت ۱۲ ایردراپ می‌ده» و آخرش ورود به کیف پول را می‌خواهد.",
            "قراردادی که آدرسش را فقط خودشان می‌دهند و در اکسپلورر مستقل TVL‌شان صفر است.",
            "هر جایی که Seed Phrase برای «مهاجرت/آپگرید» خواسته شد — ۱۰۰٪ سرقت.",
        ],
        [
            "'Fixed daily profit' that charges an activation fee to withdraw — the on-screen profit is bait.",
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
