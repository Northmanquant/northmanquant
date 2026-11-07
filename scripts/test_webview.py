#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/test_webview.py — تست پوشش iframe ضد deprecation (صفر-شبکه)
اجرا: python3 scripts/test_webview.py"""
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.webview import iframe_html  # noqa: E402

PASS = 0


def ok(cond, name):
    global PASS
    assert cond, f"FAIL: {name}"
    PASS += 1
    print(f"  ✓ {name}")


calls = []


def _make_fake_st(has_iframe=True):
    """ماکت استریم‌لیت — دو حالت: با st.iframe (نسخه‌ی تازه) و بدون آن (قدیمی)."""
    fake = types.ModuleType("streamlit")
    fake.session_state = {}   # get_lang/set_lang روی این کار می‌کنند
    if has_iframe:
        def iframe(src, **k):
            calls.append(("iframe", src, k))
            return None
        fake.iframe = iframe
    comp_mod = types.ModuleType("streamlit.components.v1")

    def html(body="", *a, **k):
        calls.append(("components.html", body, k))
        return None

    comp_mod.html = html
    comp_main = types.ModuleType("streamlit.components")
    comp_main.v1 = comp_mod
    sys.modules["streamlit.components"] = comp_main
    sys.modules["streamlit.components.v1"] = comp_mod
    return fake


def _install(fake):
    sys.modules["streamlit"] = fake
    # streamlit درون تابع import می‌شود — کش ماژول باید ماکت باشد
    sys.modules["streamlit"].__spec__ = None


from core import i18n  # noqa: E402

# --- حالت ۱: نسخه‌ی تازه (st.iframe موجود) ---
calls.clear()
_install(_make_fake_st(has_iframe=True))
iframe_html("<b>سلام دنیا</b>", height=420)
ok(len(calls) == 1 and calls[0][0] == "iframe", "نسخه‌ی تازه — st.iframe صدا زده شد")
ok(calls[0][2].get("height") == 420, "height پاس داده شد")
ok("سلام" in calls[0][1], "حالت fa — محتوای فارسی دست‌نخورده")

# --- حالت ۲: حالت انگلیسی — deep_en روی HTML اعمال می‌شود ---
# (bare mode session_state ندارد — get_lang مستقیم mock می‌شود)
calls.clear()
_orig_get = i18n.get_lang
i18n.get_lang = lambda: "en"  # type: ignore[method-assign]
try:
    iframe_html("<b>ورود</b>", height=300)
    ok("ورود" not in calls[0][1] and "entry" in calls[0][1], "حالت en — HTML ترجمه شد")
finally:
    i18n.get_lang = _orig_get  # type: ignore[method-assign]

# --- حالت ۳: نسخه‌ی قدیمی (بدون st.iframe) — فال‌بک components.v1.html ---
calls.clear()
_install(_make_fake_st(has_iframe=False))
iframe_html("<b>ورود</b>", height=640, scrolling=False)
ok(len(calls) == 1 and calls[0][0] == "components.html", "نسخه‌ی قدیمی — فال‌بک components")
ok(calls[0][2].get("height") == 640 and calls[0][2].get("scrolling") is False,
   "height و scrolling در فال‌بک پاس داده شدند")

# --- حالت ۴: ورودی خراب — بدون raise ---
calls.clear()
_install(_make_fake_st(has_iframe=True))
iframe_html(None)  # type: ignore[arg-type]
ok(len(calls) == 1, "ورودی None — بدون raise رد می‌شود")

# --- حالت ۵: deep_en خراب — رندر نمی‌شکند ---
calls.clear()
_orig = i18n.deep_en
i18n.deep_en = lambda s: (_ for _ in ()).throw(RuntimeError("boom"))  # type: ignore
try:
    iframe_html("<b>x</b>", height=100)
    ok(True, "خرابی deep_en — رندر همچنان کار می‌کند")
finally:
    i18n.deep_en = _orig  # type: ignore

# --- حالت ۶: صفحات دیگر از webview استفاده می‌کنند و import سالم است ---
import glob  # noqa: E402
import py_compile  # noqa: E402

pages_using = 0
for p in glob.glob("pages/*.py"):
    with open(p, encoding="utf-8") as f:
        if "iframe_html" in f.read():
            pages_using += 1
ok(pages_using >= 5, f"{pages_using} صفحه از iframe_html استفاده می‌کنند")
for p in glob.glob("pages/*.py") + ["core/webview.py"]:
    py_compile.compile(p, doraise=True)
ok(True, "همه‌ی صفحات + webview کامپایل می‌شوند")

print(f"\n✅ همه‌ی {PASS} تست webview پاس شد")
