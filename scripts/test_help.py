#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/test_help.py — تست «؟» راهنما (core/help.py) — صفر-شبکه
اجرا: python3 scripts/test_help.py
پوشش: popover/fa، popover/en، فال‌بک expander، ورودی خالی، title، شکست‌خوردگی fail-soft،
      استفاده در همه‌ی صفحات، کامپایل همه‌ی فایل‌ها."""
import glob
import os
import py_compile
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASS = 0


def ok(cond, name):
    global PASS
    assert cond, f"FAIL: {name}"
    PASS += 1
    print(f"  ✓ {name}")


_md = []          # رخدادهای رندر: ("popover-label", lbl) / ("expander-label", lbl) / متن markdown


def _make_fake_st(has_popover=True, broken=False):
    """ماکت استریم‌لیت — سه حالت: popover دار، بدون popover، popover خراب."""
    fake = types.ModuleType("streamlit")
    fake.session_state = {}

    def markdown(body="", **k):
        _md.append(body)

    fake.markdown = markdown

    class _Pop:
        def __init__(self, label, **k):
            _md.append(("popover-label", label))

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def popover(label, **k):
        if broken:
            raise RuntimeError("popover boom")
        return _Pop(label, **k)

    class _Exp:
        def __init__(self, label, **k):
            _md.append(("expander-label", label))

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def expander(label, **k):
        return _Exp(label, **k)

    if has_popover:
        fake.popover = popover
    fake.expander = expander
    return fake


def _install(fake):
    sys.modules["streamlit"] = fake
    sys.modules["streamlit"].__spec__ = None


_install(_make_fake_st(has_popover=True))
from core import i18n  # noqa: E402  (بعد از نصب ماکت — streamlit فیک قفل می‌شود)
from core.help import hint  # noqa: E402

# --- ۱) ورودی خالی — هیچی رندر نمی‌شود، بدون raise ---
_md.clear()
hint()
hint("")
hint(None)  # type: ignore[arg-type]
hint("   ")
ok(len(_md) == 0, "ورودی خالی — هیچ رندری نمی‌شود")

# --- ۲) حالت فارسی — popover با برچسب «؟» ---
_md.clear()
hint("توضیح آزمایشی برای بخش", "پاراگراف دوم")
_labels = [x for x in _md if isinstance(x, tuple) and x[0] == "popover-label"]
_ok_labels = [x for x in _labels if x[1] == "؟"]
ok(len(_ok_labels) == 1, f"حالت fa — popover با برچسب «؟» ({len(_ok_labels)}بار)")
_bodies = [x for x in _md if isinstance(x, str)]
ok(len(_bodies) == 1 and "توضیح آزمایشی برای بخش" in _bodies[0] and "پاراگراف دوم" in _bodies[0],
   "دو پاراگراف در یک markdown داخل popover رندر شد")

# --- ۳) حالت انگلیسی — برچسب «?» (get_lang مستقیم mock می‌شود؛ bare mode) ---
_md.clear()
_orig_get = i18n.get_lang
i18n.get_lang = lambda: "en"  # type: ignore[method-assign]
try:
    hint("English explanation here")
    _labels = [x for x in _md if isinstance(x, tuple) and x[0] == "popover-label"]
    ok(len(_labels) == 1 and _labels[0][1] == "?", "حالت en — برچسب «?»")
finally:
    i18n.get_lang = _orig_get  # type: ignore[method-assign]

# --- ۴) title اختیاری — بولد بالای متن ---
_md.clear()
hint("بدنه‌ی توضیح", title="عنوان بخش")
_bodies = [x for x in _md if isinstance(x, str)]
ok(_bodies[0] == "**عنوان بخش**" and _bodies[1] == "بدنه‌ی توضیح", "title بولد بالای بدنه")

# --- ۵) فال‌بک: بدون st.popover → expander ---
_install(_make_fake_st(has_popover=False))
_md.clear()
hint("راهنمای قدیمی")
_labels = [x for x in _md if isinstance(x, tuple) and x[0] == "expander-label"]
ok(len(_labels) == 1 and _labels[0][1].startswith("؟"), "بدون popover — فال‌بک expander با برچسب «؟ …»")

# --- ۶) popover خراب — fail-soft، بدون raise (فال‌بک expander جان می‌گیرد) ---
_install(_make_fake_st(has_popover=True, broken=True))
_md.clear()
hint("راهنما روی نسخه‌ی خراب")
ok(any(isinstance(x, tuple) and x[0] == "expander-label" for x in _md),
   "popover خراب — بدون raise به expander می‌افتد")

# --- ۷) expander هم خراب — بدون raise و بدون رندر (صفحه نمی‌شکند) ---
class _Boom:
    def __init__(self, *a, **k):
        raise RuntimeError("expander boom")

_install(_make_fake_st(has_popover=False))
sys.modules["streamlit"].expander = _Boom  # type: ignore[attr-defined]
_md.clear()
try:
    hint("راهنمای روی نسخه‌ی خیلی خراب")
    ok(True, "expander خراب — بدون raise رد می‌شود")
except Exception as e:  # noqa: BLE001
    raise AssertionError(f"FAIL: fail-soft شکست خورد: {e}")

# --- ۸) استفاده در همه‌ی صفحات + کامپایل ---
_install(_make_fake_st(has_popover=True))   # پاک‌سازی — py_compile به ماکت نیاز ندارد ولی تمیزتر است
pages = sorted(glob.glob("pages/*.py"))
pages_with_hint = [p for p in pages if "hint(" in open(p, encoding="utf-8").read()]
ok(len(pages_with_hint) == len(pages) == 9,
   f"هر ۹ صفحه از hint استفاده می‌کنند ({len(pages_with_hint)}/{len(pages)})")
for p in pages + ["core/help.py", "core/webview.py", "core/i18n.py"]:
    py_compile.compile(p, doraise=True)
ok(True, "همه‌ی صفحات + core/help.py کامپایل می‌شوند")

print(f"\n✅ همه‌ی {PASS} تست help پاس شد")
