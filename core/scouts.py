# -*- coding: utf-8 -*-
"""core/scouts.py — کارگاه کیفیت پروژه (Quality Workshop) — ایجنت‌ها روی «پروژه‌ی خودمان»
========================================================================================
پرسش کاربر: «بریم به فکر پروژه‌ی خودمون باشیم، کیفیتش رو ببریم بالا.» و پیش از آن:
«اون بخش فارمینگ و ماینینگ کلا حذفش کن و هرچیزی که مربوط بهش میشه.»

تاریخچه: ایجنت‌ها قبلاً دنبال فرصتِ بیرونی می‌گشتند؛ آن بخش کامل حذف شد و میدانِ
ایجنت‌ها چرخید به سمتِ همین مخزن — NorthmanQuant. حالا ۵ ایجنت روی پروژه‌ی خودمان
کار می‌کنند: بدون اینترنت، بدون پول، بدون تغییرِ هیچ فایلی.
  ۱) **اسکن** — آمار واقعیِ مخزن: فایل‌ها و خط‌ها، اسکریپت‌های تست، TODOهای باز،
     پوششِ fail-soft (try/except)، کشِ داده (st.cache) و مستندسازیِ ماژول‌ها.
  ۲) **تشخیص** — کجا ضعیف است: بزرگ‌ترین فایل‌ها، ماژول‌های بی‌مستندات، فایل‌های
     پرِTODO، نسبتِ تست به کد.
  ۳) **طرح** — گام‌های مشخص روی فایل‌های واقعیِ همین مخزن با زمانِ تخمینی و دلیلِ
     فارسی؛ همه‌ی گام‌ها 🟢 رایگان‌اند (فقط زمان و دقت).
  ۴) **داوری** — نمره‌ی قطعی ۰-۱۰۰: هر گامِ پولی (API پولی، سرور اجاره‌ای، خرید
     داده) −۴۵؛ سرریزِ زمان جریمه‌ی متناسب؛ پوششِ حوزه‌ها پاداش؛ دو ستونِ کیفیت
     (تست + مستندات) پاداشِ ویژه؛ اشاره‌ی واقعی به فایل‌های مخزن پاداش.

مرزِ صادقانه (نوشته‌شده در صفحه هم هست): ایجنت‌ها **کد را تغییر نمی‌دهند** —
اسکن می‌کنند، نقشه می‌کشند و داوری می‌کنند؛ اجرا با انسان است. تغییرِ بی‌تست،
پروژه را شکننده می‌کند؛ نقشه‌ی ایجنت + اجرای آگاهانه‌ی انسان + تستِ کامل =
کیفیتِ پایدار.

۵ شخصیت با استراتژی متفاوت روی همین مخزن: 🆓 صفر-پول (کوچک‌ترین اصلاح‌ها اول) ·
🛡 محتاط (پایداری و تازگیِ داده، بدون بازسازیِ پرخطر) · ⚡ جاه‌طلب (بیشترین پوششِ
حوزه‌ها) · ⏱ کم‌وقت (۱۵ دقیقه سفت‌وسخت) · 🧮 ریاضی‌دان (اعداد اول؛ EV کیفیت
نامعین است و صادقانه «نامعین» نوشته می‌شود — قیمتِ قطعی فقط زمان است).
همه‌ی توابع قطعی و fail-soft هستند — اسکنِ مسیرِ خراب/خالی کرش نمی‌سازد؛ دو اجرا
با یک ورودی، دقیقاً یک خروجی می‌دهد.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.opportunities import COST_FREE, COST_PAID

# --------------------------------------------------------------------------- #
# نشانِ هزینه و حوزه‌های کیفیت                                                #
# --------------------------------------------------------------------------- #
# شش نوعِ گامِ رایگان + سه نوعِ ممنوع (پولی) — داور گامِ پولی را سنگین جریمه می‌کند.
FREE_KINDS: Tuple[str, ...] = ("audit", "test", "docs", "refactor", "ux", "data")
PAID_KINDS: Tuple[str, ...] = ("paid_api", "cloud_server", "buy_data")

COST_FOR: Dict[str, Tuple[str, str]] = {
    "audit": (COST_FREE, "🟢 Free"),
    "test": (COST_FREE, "🟢 Free"),
    "docs": (COST_FREE, "🟢 Free"),
    "refactor": (COST_FREE, "🟢 Free"),
    "ux": (COST_FREE, "🟢 Free"),
    "data": (COST_FREE, "🟢 Free"),
    "paid_api": (COST_PAID, "🔴 Paid"),
    "cloud_server": (COST_PAID, "🔴 Paid"),
    "buy_data": (COST_PAID, "🔴 Paid"),
}


def cost_for(kind: str) -> Tuple[str, str]:
    """(نشان فارسی، نشان انگلیسی) برای هر نوع گام — نوع ناشناخته → «؟»."""
    return COST_FOR.get(str(kind or ""), ("؟", "?"))


# حوزه‌های کیفیت — هر گام به یک حوزه تعلق دارد؛ پوششِ حوزه‌ها در داوری پاداش دارد.
AREA_FOR: Dict[str, Tuple[str, str]] = {
    "tests": ("🧪 تست‌ها", "🧪 Tests"),
    "stability": ("🛡 پایداری", "🛡 Stability"),
    "docs": ("📚 مستندات", "📚 Docs"),
    "ux": ("🎨 تجربه‌ی کاربری", "🎨 UX"),
    "data": ("🗄 داده و کش", "🗄 Data & cache"),
    "cleanup": ("🧹 تمیزکاری", "🧹 Cleanup"),
}


def area_for(area: str) -> Tuple[str, str]:
    """(برچسب فارسی، برچسب انگلیسی) برای هر حوزه — ناشناخته → «؟»."""
    return AREA_FOR.get(str(area or ""), ("؟", "?"))


_EN2FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def fa_num(n: Any) -> str:
    """عدد با ارقام فارسی برای نمایش در صفحه — ورودی خراب → «؟»."""
    try:
        return str(int(n)).translate(_EN2FA_DIGITS)
    except (TypeError, ValueError):
        return "؟"


# --------------------------------------------------------------------------- #
# شخصیت‌ها — پنج ایجنت، پنج استراتژی، یک مخزنِ مشترک: پروژه‌ی خودمان           #
# --------------------------------------------------------------------------- #
# قانون مشترک کارگاه (به درخواست کاربر): بودجه‌ی صفر — هیچ ایجنتی گامِ پولی
# نمی‌گذارد؛ تفاوت استراتژی‌ها فقط در «کدام اصلاح‌ها را و به چه ترتیبی».
# budget: free (هیچ پولی نه). risk: ۰ (محتاط) تا ۱ (جاه‌طلب).
# time_budget: دقیقه در هفته.
SCOUT_AGENTS: List[Dict[str, Any]] = [
    {
        "key": "zero", "icon": "🆓",
        "name": "صفر-پول", "name_en": "Zero-Budget",
        "style": "کوچک‌ترین اصلاح‌ها اول — کمترین خطِ کد، کمترین زمان؛ کیفیت، جمعِ اصلاح‌های کوچک است.",
        "style_en": "Smallest fixes first — fewest lines, least time; quality is the sum of small fixes.",
        "budget": "free", "risk": 0.2, "time_budget": 30,
    },
    {
        "key": "cautious", "icon": "🛡",
        "name": "محتاط", "name_en": "Cautious",
        "style": "اول پایداری: پوششِ fail-soft و تازگیِ داده؛ هیچ بازسازیِ پرخطری نه.",
        "style_en": "Stability first: fail-soft coverage and data freshness; no risky refactors.",
        "budget": "free", "risk": 0.1, "time_budget": 20,
    },
    {
        "key": "aggressive", "icon": "⚡",
        "name": "جاه‌طلب", "name_en": "Aggressive",
        "style": "بیشترین پوششِ ممکن: تست، مستندات، رابط کاربری و تمیزکاری — همه‌ی حوزه‌ها تا سقف ۶۰ دقیقه.",
        "style_en": "Maximum coverage: tests, docs, UX and cleanup — every area up to 60 minutes.",
        "budget": "free", "risk": 0.7, "time_budget": 60,
    },
    {
        "key": "busy", "icon": "⏱",
        "name": "کم‌وقت", "name_en": "Time-Poor",
        "style": "۱۵ دقیقه در روز برای پروژه — فقط اسکنِ سریع و اجرای تست‌های موجود.",
        "style_en": "15 minutes a day for the project — quick scan and running existing tests only.",
        "budget": "free", "risk": 0.4, "time_budget": 15,
    },
    {
        "key": "quant", "icon": "🧮",
        "name": "ریاضی‌دان", "name_en": "Quant",
        "style": "اعداد اول: نسبتِ تست به کد، پوششِ مستندات و کش؛ EV کیفیت نامعین است و صادقانه نوشته می‌شود.",
        "style_en": "Numbers first: test ratio, docs and cache coverage; quality-EV is honestly 'unknowable'.",
        "budget": "free", "risk": 0.5, "time_budget": 40,
    },
]


# --------------------------------------------------------------------------- #
# اسکنِ واقعیِ مخزن — آفلاین، قطعی، fail-soft                                 #
# --------------------------------------------------------------------------- #
_SKIP_DIRS = {".git", "__pycache__", ".github", ".streamlit", "assets",
              "mobile-app", "node_modules", "sql", ".idea", ".vscode"}


def _module_doc(txt: str) -> int:
    """۱ اگر فایل docstringِ ماژول دارد — با ast؛ خطای پارس → ۰ (fail-soft)."""
    try:
        tree = ast.parse(txt)
        return 1 if (tree.body and isinstance(tree.body[0], ast.Expr)
                     and isinstance(tree.body[0].value, ast.Constant)
                     and isinstance(tree.body[0].value.value, str)) else 0
    except Exception:  # noqa: BLE001
        return 0


def repo_scan(root: Optional[str] = None) -> Dict[str, Any]:
    """اسکنِ واقعی و آفلاینِ مخزن — آمار خام برای ایجنت‌ها؛ قطعی و fail-soft.

    خروجی: {"root", "files": {مسیر: آمار}, "n_files", "n_lines", "n_todo",
    "n_doc", "n_cache", "n_soft", "n_pages", "n_core", "n_tests", "biggest",
    "todo_files", "docless"} — مسیرِ خراب/نایافتنی → اسکنِ خالی، بدون کرش.
    هرگز محتوای فایل را نمی‌خوانَد که نمایش دهد؛ فقط می‌شمارد.
    """
    root_p = Path(root) if root else Path(__file__).resolve().parent.parent
    files: Dict[str, Dict[str, int]] = {}
    try:
        for p in sorted(root_p.rglob("*.py")):
            if any(part in _SKIP_DIRS for part in p.parts):
                continue
            rel = p.relative_to(root_p).as_posix()
            try:
                txt = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:  # noqa: BLE001 — فایلِ ناخوانا حذف می‌شود، نه کرش
                continue
            files[rel] = {
                "lines": len(txt.splitlines()),
                "funcs": len(re.findall(r"^\s*def\s+", txt, re.M)),
                "todo": len(re.findall(r"\b(?:TODO|FIXME|XXX)\b", txt)),
                "doc": _module_doc(txt),
                "cache": 1 if ("st.cache_data" in txt or "st.cache_resource" in txt) else 0,
                "soft": 1 if "except" in txt else 0,
                "page": 1 if rel.startswith("pages/") else 0,
                "core": 1 if rel.startswith("core/") else 0,
                "test": 1 if Path(rel).name.startswith("test_") else 0,
            }
    except Exception:  # noqa: BLE001 — مخزنِ نایافتنی → اسکنِ خالی
        files = {}

    def _cnt(flag: str) -> int:
        return sum(1 for f in files.values() if f.get(flag))

    _by_lines = sorted(files, key=lambda r: (-int(files[r]["lines"]), r))
    todo_files = sorted((r for r, f in files.items() if f.get("todo")),
                        key=lambda r: (-int(files[r]["todo"]), r))
    docless = sorted((r for r, f in files.items()
                      if not f.get("doc") and not f.get("test")
                      and int(f.get("lines") or 0) >= 25),
                     key=lambda r: (-int(files[r]["lines"]), r))
    return {
        "root": str(root_p),
        "files": files,
        "n_files": len(files),
        "n_lines": sum(int(f["lines"]) for f in files.values()),
        "n_todo": sum(int(f["todo"]) for f in files.values()),
        "n_doc": _cnt("doc"),
        "n_cache": _cnt("cache"),
        "n_soft": _cnt("soft"),
        "n_pages": _cnt("page"),
        "n_core": _cnt("core"),
        "n_tests": _cnt("test"),
        "biggest": _by_lines[:6],
        "todo_files": todo_files[:6],
        "docless": docless[:6],
    }


# --------------------------------------------------------------------------- #
# انتخابِ هدف — فقط فایل‌های واقعیِ اسکن‌شده                                  #
# --------------------------------------------------------------------------- #
def _pick(seq: Any, i: int = 0, default: str = "") -> str:
    try:
        return str((list(seq) or [default])[i] or default)
    except Exception:  # noqa: BLE001
        return default


def _flagged(scan: dict, flag: str, i: int = 0) -> str:
    """i-اُمین فایلِ دارای فلگ (مرتب بر حسب تعداد خط، نزولی) — «» اگر نبود."""
    files = scan.get("files") or {}
    try:
        cand = sorted((r for r, f in files.items() if f.get(flag)),
                      key=lambda r: (-int(files[r].get("lines") or 0), r))
    except Exception:  # noqa: BLE001
        return ""
    return _pick(cand, i)


def _docless_target(scan: dict, i: int = 0) -> str:
    """i-اُمین ماژولِ بی‌مستندات (نه تست، ≥۲۵ خط) — بزرگ‌تر اول."""
    files = scan.get("files") or {}
    try:
        cand = sorted((r for r, f in files.items()
                       if not f.get("doc") and not f.get("test")
                       and int(f.get("lines") or 0) >= 25),
                      key=lambda r: (-int(files[r].get("lines") or 0), r))
    except Exception:  # noqa: BLE001
        return ""
    return _pick(cand, i)


def _fast_test_target(scan: dict) -> str:
    """کوچک‌ترین اسکریپتِ تست (سریع‌ترین اجرا) — برای ایجنتِ کم‌وقت."""
    files = scan.get("files") or {}
    try:
        cand = sorted((r for r, f in files.items() if f.get("test")),
                      key=lambda r: (int(files[r].get("lines") or 0), r))
    except Exception:  # noqa: BLE001
        return ""
    return _pick(cand, 0)


def _step(kind: str, area: str, title_fa: str, title_en: str, target: str,
          time_min: int, why_fa: str, why_en: str, ev: bool = False) -> dict:
    """یک گامِ طرح — همه‌ی گام‌ها رایگان‌اند؛ هدفِ گام فایلِ واقعیِ مخزن است."""
    s = {
        "kind": kind, "area": area,
        "title": title_fa, "title_en": title_en,
        "target": target, "time_min": int(time_min),
        "why": why_fa, "why_en": why_en, "flags": [],
    }
    if ev:
        s["ev"] = int(time_min)
    return s


# --------------------------------------------------------------------------- #
# ساختِ طرح — استراتژیِ هر شخصیت روی مخزنِ واقعی                              #
# --------------------------------------------------------------------------- #
def build_plan(agent: dict, scan: Optional[dict]) -> dict:
    """طرحِ کیفیتِ شخصیِ ایجنت از اسکنِ واقعیِ مخزن — قطعی و بدون شبکه.

    قانونِ مشترک کارگاه: همه‌ی گام‌ها رایگان‌اند (فقط زمان و دقت)؛ هدفِ هر گام
    فایلِ واقعیِ همین مخزن است. اسکنِ خالی/None → برنامه‌ی خالیِ صادقانه (بدون کرش).
    خروجی: {"agent_key", "steps", "total_time", "has_paid", "notes", "notes_en"}
    """
    key = str(agent.get("key") or "?")
    tb = int(agent.get("time_budget") or 30)
    sc = scan if isinstance(scan, dict) else {}
    steps: List[dict] = []
    notes: List[str] = []
    notes_en: List[str] = []

    if not sc.get("files"):
        return {"agent_key": key, "steps": [], "total_time": 0, "has_paid": False,
                "notes": ["اسکنِ مخزن در دسترس نبود — برنامه‌ای ساخته نشد؛ دکمه‌ی اجرا را دوباره بزن."],
                "notes_en": ["Repo scan unavailable — no plan was built; press run again."]}

    big = _pick(sc.get("biggest"))
    page1 = _flagged(sc, "page") or big
    core1 = _flagged(sc, "core") or big
    core2 = _flagged(sc, "core", 1) or core1
    page2 = _flagged(sc, "page", 1) or page1
    _dl = _docless_target(sc)
    _td = _flagged(sc, "todo")
    _cc = _flagged(sc, "cache")
    _ft = _fast_test_target(sc)

    if key == "zero":
        # کوچک‌ترین اصلاح‌ها اول — سه گامِ کوتاه و مطمئن در بودجه‌ی ۳۰ دقیقه
        if page1:
            steps.append(_step(
                "test", "tests", "تستِ رفتار اصلیِ بزرگ‌ترین صفحه",
                "Test the biggest page's core behaviour", page1, 15,
                "بزرگ‌ترین صفحه‌ی رابط بیشترین احتمال باگ را دارد؛ یک تستِ ساده رفتارِ اصلیش را قفل می‌کند.",
                "The biggest UI page hides the most bugs; one simple test locks its core behaviour."))
        if _dl or core2:
            steps.append(_step(
                "docs", "docs", "مستندسازی یا به‌روزرسانیِ مستنداتِ ماژول",
                "Write or refresh a module's docs", _dl or core2, 5,
                "چند خط فارسیِ به‌روز سرِ ماژول، فهمش را برای هفته‌های بعد آسان می‌کند.",
                "A few fresh Persian lines at the top make the module understandable weeks later."))
        if _td or core1:
            steps.append(_step(
                "audit", "cleanup", "فهرستِ TODOهای باز",
                "List open TODOs", _td or core1, 10,
                "TODO بدهیِ فراموش‌شده است؛ فهرستِ دقیقش نصفِ بدهی را می‌پوشاند.",
                "TODOs are forgotten debt; a precise list pays half of it."))
        notes.append("هر سه گام کوچک و در بودجه‌اند — کیفیت، جمعِ اصلاح‌های کوچکِ مداوم است.")
        notes_en.append("All three steps are small and in-budget — quality is the sum of small steady fixes.")

    elif key == "cautious":
        # اول پایداری — بدون بازسازیِ پرخطر
        if core1:
            steps.append(_step(
                "audit", "stability", "بازبینیِ fail-soft هسته",
                "Audit the core's fail-soft coverage", core1, 10,
                "مسیرهای شبکه‌ای و داده‌ی خراب باید با try/except مهار شوند — نه با کرش.",
                "Network paths and bad data must be tamed with try/except — not with crashes."))
        if _cc or page1:
            steps.append(_step(
                "data", "data", "چکِ تازگیِ داده و TTL کش",
                "Check data freshness and cache TTL", _cc or page1, 10,
                "داده‌ی کهنه یعنی تصمیمِ کهنه — TTL هر کش باید با سرعتِ تغییرِ منبعش هم‌تراز باشد.",
                "Stale data means stale decisions — each cache TTL must match its source's speed."))
        notes.append("این ایجنت بازسازیِ ساختاری نمی‌کند — تغییرِ پرخطر با تستِ کامل، کارِ روزهای آرام است.")
        notes_en.append("This agent does no structural refactor — risky change with full tests belongs to calm days.")

    elif key == "aggressive":
        # بیشترین پوشش — پنج حوزه در یک ساعت، همه با گام‌های واقعی
        if page1:
            steps.append(_step(
                "test", "tests", "تستِ بزرگ‌ترین صفحه",
                "Test the biggest page", page1, 15,
                "قفل کردنِ رفتارِ اصلیِ پرترافیک‌ترین صفحه — بیشترین بازدهِ کیفیت به ازای دقیقه.",
                "Locking the busiest page's core behaviour — the best quality per minute."))
        if core2 and core2 != core1:
            steps.append(_step(
                "test", "tests", "تستِ ماژولِ سنگینِ هسته",
                "Test the heaviest core module", core2, 10,
                "منطقِ اصلیِ پروژه اینجاست؛ تستِ اینجا یعنی آرامشِ خوابِ بعد از هر تغییر.",
                "The project's real logic lives here; testing it means calm sleep after any change."))
        if _dl or core1:
            steps.append(_step(
                "docs", "docs", "مستندسازی یا به‌روزرسانیِ مستنداتِ ماژول",
                "Write or refresh a module's docs", _dl or core1, 10,
                "مستنداتِ کوتاهِ به‌روزِ فارسی سرِ ماژول — نسلِ بعدیِ خودت تشکر می‌کند.",
                "Short fresh Persian docs at the module top — your future self says thanks."))
        if page2 and page2 != page1:
            steps.append(_step(
                "ux", "ux", "بهبودِ متن‌ها و چیدمانِ صفحه‌ی دوم",
                "Improve the second page's copy and layout", page2, 10,
                "متنِ کوتاه‌تر و ترتیبِ درستِ ابزارها — تجربه‌ی کاربر بی‌کلام بهتر می‌شود.",
                "Shorter copy and better tool order — the user experience improves quietly."))
        if _td:
            steps.append(_step(
                "refactor", "cleanup", "تمیزکاریِ فایلِ پرِTODO",
                "Clean up the TODO-heavy file", _td, 10,
                "رفتار عوض نمی‌شود؛ فقط نام‌ها، تکرارها و بخش‌های مرده تمیز می‌شوند — با تستِ کامل بعدش.",
                "Behaviour unchanged; names, duplicates and dead code only — full tests right after."))
        if _cc:
            steps.append(_step(
                "data", "data", "چکِ پوششِ کشِ داده",
                "Check data-cache coverage", _cc, 5,
                "هر منبعِ کند باید پشتِ کش باشد؛ شمارشش هزینه‌ای ندارد و سرعتِ صفحه را نجات می‌دهد.",
                "Every slow source must sit behind a cache; counting it is free and saves page speed."))
        notes.append("هر گام رایگان است؛ پوششِ پنج حوزه در یک ساعت — اما هر تغییر با تستِ کامل پوش می‌شود.")
        notes_en.append("Every step is free; five areas in one hour — but every change lands behind full tests.")

    elif key == "busy":
        # ۱۵ دقیقه سفت‌وسخت — نگاهِ دقیق + اجرای تست‌ها
        if big:
            steps.append(_step(
                "audit", "cleanup", "اسکنِ سریعِ بزرگ‌ترین فایل",
                "Quick scan of the biggest file", big, 10,
                "ده دقیقه نگاهِ دقیقِ بدونِ تغییر: TODOها، بخش‌های مرده و کدهای بی‌تستِ همین فایل.",
                "Ten minutes of careful looking without touching: TODOs, dead code and untested parts."))
        if _ft or page1:
            steps.append(_step(
                "test", "tests", "اجرای کاملِ تست‌های موجود",
                "Run the existing test suite", _ft or page1, 5,
                "سبز بودنِ تست‌ها پایه‌ی هر اصلاح است — قبل از هر تغییر، خطِ پایه را قفل کن.",
                "Green tests are the base of every fix — lock the baseline before touching anything."))
        notes.append("قانونِ این ایجنت: ۱۵ دقیقه در روز — نه یک ثانیه بیشتر؛ بازسازی‌ها برای روزهای آرام.")
        notes_en.append("This agent's law: 15 minutes a day — not a second more; refactors belong to calm days.")

    elif key == "quant":
        # اعداد اول — سنجش، سپس اصلاح؛ EV کیفیت صادقانه «نامعین»
        if core1:
            steps.append(_step(
                "audit", "tests", "سنجشِ نسبتِ تست به کد",
                "Measure the test-to-code ratio", core1, 15,
                "عددِ امروز، خطِ پایه‌ی کیفیت است؛ بدون سنجش، «بهبود» فقط حس است.",
                "Today's number is the quality baseline; without measuring, 'improvement' is a feeling.", ev=True))
        if core2:
            steps.append(_step(
                "test", "tests", "تست برای ماژولِ دومِ هسته",
                "Test the second core module", core2, 10,
                "پوششِ تست باید به سنگین‌ترین ماژول‌ها برسد — ریسکِ واقعی همان‌جاست.",
                "Test coverage must reach the heaviest modules — that is where real risk lives.", ev=True))
        if _dl or page2:
            steps.append(_step(
                "docs", "docs", "پوششِ شکافِ مستندسازی",
                "Cover the docs gap", _dl or page2, 10,
                "ماژول‌های بی‌مستندات یا مستنداتِ کهنه شمرده می‌شوند؛ بزرگ‌ترینش اول اصلاح می‌شود.",
                "Undocumented or stale-doc modules get counted; the biggest one gets fixed first.", ev=True))
        if _cc or page1:
            steps.append(_step(
                "data", "data", "سنجشِ پوششِ کش",
                "Measure cache coverage", _cc or page1, 5,
                "شمارشِ منابعِ پشتِ کش — عددِ ساده‌ای که سوءتفاهمِ «چرا کند است؟» را می‌بندد.",
                "Count what sits behind cache — a simple number that closes the 'why is it slow?' debate.", ev=True))
        for _s in steps:
            _s["why"] += f" · EV کیفیت: نامعین — قیمتِ قطعی: فقط {_s['time_min']} دقیقه"
            _s["why_en"] += f" · quality-EV: unknowable — the hard price: only {_s['time_min']} min"
    else:
        # شخصیت ناشناخته → مینیممِ امن: نگاهِ دقیق بدون تغییر
        if big:
            steps.append(_step(
                "audit", "cleanup", "بازبینیِ امنِ یک فایل",
                "Safe review of one file", big, min(10, tb),
                "شخصیتِ ناشناخته — مینیممِ امن: نگاهِ دقیق، بدون هیچ تغییری.",
                "Unknown persona — safe minimum: careful look, no change at all."))

    total = sum(int(s.get("time_min") or 0) for s in steps)
    return {
        "agent_key": key,
        "steps": steps,
        "total_time": total,
        "has_paid": any(str(s.get("kind") or "") in PAID_KINDS for s in steps),
        "notes": notes,
        "notes_en": notes_en,
    }


# --------------------------------------------------------------------------- #
# داوری — نمره‌ی قطعی ۰-۱۰۰ برای هر طرح                                       #
# --------------------------------------------------------------------------- #
def judge_plan(agent: dict, plan: dict, scan: Optional[dict] = None) -> Tuple[int, List[str]]:
    """(نمره، فلگ‌ها) — داورِ قطعی کارگاه؛ بدون شبکه، بدون شانس.

    قواعد:
      • گامِ پولی (paid_api / cloud_server / buy_data یا has_paid) → −۴۵ +
        budget_violation — قانونِ کارگاه برای «همه‌ی» ایجنت‌هاست: کیفیت با پول
        خریدنی نیست، با دقت ساخته می‌شود.
      • سرریزِ زمان → جریمه‌ی متناسب تا ۳۰ + time_over
      • پوششِ ≥۲ حوزه +۸ · پوششِ ≥۴ حوزه +۷
      • دو ستونِ کیفیت (تست + مستندات با هم) +۱۰
      • ≥۴ گام +۵ · EV صریح روی حداقل یک گام +۵
      • همه‌ی هدف‌ها فایلِ واقعیِ اسکن +۵ (فقط وقتی اسکن داده شده — «طرحِ زمینی»)
      • شخصیتِ محتاط (risk ≤ ۰٫۲) با گامِ بازسازی → −۱۵ + risk_mismatch
    """
    steps = [s for s in (plan.get("steps") or []) if isinstance(s, dict)]
    score = 55.0 if steps else 5.0
    flags: List[str] = []
    tb = max(int(agent.get("time_budget") or 30), 1)

    paid = bool(plan.get("has_paid")) or any(
        str(s.get("kind") or "") in PAID_KINDS or str(s.get("kind") or "") == "paid"
        for s in steps)
    if paid:
        score -= 45.0
        flags.append("budget_violation")
    excess = int(plan.get("total_time") or 0) - tb
    if excess > 0:
        score -= min(30.0, excess / tb * 30.0)
        flags.append("time_over")
    areas = {str(s.get("area") or "") for s in steps} - {""}
    if len(areas) >= 2:
        score += 8.0
    if len(areas) >= 4:
        score += 7.0
    if {"tests", "docs"} <= areas:
        score += 10.0                   # دو ستونِ کیفیت: تست + مستندات با هم
    if len(steps) >= 4:
        score += 5.0
    if scan:
        real = set((scan.get("files") or {}).keys())
        if steps and all(str(s.get("target") or "") in real for s in steps):
            score += 5.0                # طرحِ زمینی: همه‌ی هدف‌ها فایلِ واقعی‌اند
    if any("ev" in s for s in steps):
        score += 5.0
    if float(agent.get("risk", 0.5)) <= 0.2 and any(
            str(s.get("kind") or "") == "refactor" for s in steps):
        score -= 15.0
        flags.append("risk_mismatch")
    return int(round(max(0.0, min(100.0, score)))), flags


def _verdict(score: int) -> Tuple[str, str]:
    if score >= 70:
        return ("طرحِ برنده: مشخص، زمان‌بندی‌شده و بدون هزینه",
                "Winning plan: concrete, time-boxed and free")
    if score >= 55:
        return ("قوی — چند اصلاحِ جزئی دارد", "Strong — a few minor tweaks")
    if score >= 35:
        return ("متوسط — پوششِ حوزه‌ها نامتوازن است", "Average — area coverage is unbalanced")
    return ("ضعیف — نگاهی به طرحِ رقیب بینداز", "Weak — check a rival's plan")


def run_arena(scan: Optional[dict]) -> List[dict]:
    """مسابقه‌ی کامل: همه‌ی ایجنت‌ها روی اسکنِ واقعی طرح می‌سازند، داور نمره می‌دهد.

    خروجی مرتب (برنده اول): {"agent", "plan", "score", "verdict", "verdict_en",
    "flags"} — قطعی؛ دو اجرا با یک اسکن، یک خروجی. اسکنِ خالی/None هم مسابقه‌ی
    بدون کرش برگزار می‌کند (نمره‌ها پایین می‌مانند).
    """
    out: List[dict] = []
    for agent in SCOUT_AGENTS:
        try:
            plan = build_plan(agent, scan)
            score, flags = judge_plan(agent, plan, scan if isinstance(scan, dict) else None)
        except Exception:  # noqa: BLE001 — یک ایجنتِ خراب بقیه را نمی‌سوزاند
            plan = {"agent_key": str(agent.get("key") or "?"), "steps": [],
                    "total_time": 0, "has_paid": False, "notes": [], "notes_en": []}
            score, flags = 0, ["engine_error"]
        v_fa, v_en = _verdict(score)
        out.append({"agent": agent, "plan": plan, "score": score,
                    "verdict": v_fa, "verdict_en": v_en, "flags": flags})
    out.sort(key=lambda r: (-int(r["score"]), int(r["plan"].get("total_time") or 0),
                            str(r["agent"].get("key") or "")))
    return out
