# -*- coding: utf-8 -*-
"""core/help.py — «؟» کوچک: توضیحات اضافی از صفحه حذف و داخل علامت سوال پنهان می‌شوند
======================================================================================
الگوی جدید صفحه‌ها: به‌جای caption/info طولانی زیر عنوان‌ها، یک «؟» کوچک می‌گذاریم؛
کاربر با کلیک روی آن توضیحات همان بخش را می‌بیند و صفحه تمیز و کوتاه می‌ماند.

استفاده:
    from core.help import hint
    st.title("📊 قیمت‌های زنده بازار")
    hint(tr("توضیح فارسی بلند...", "Long English explanation..."))

نکته‌ها:
  * متن را همان لحظه از tr()/L() بگیر — hint خودش ترجمه نمی‌کند، هرچه بدهی همان را نشان می‌دهد.
  * fail-soft: popover نبود → expander؛ هر مشکل دیگری → هیچ. صفحه هرگز به‌خاطر راهنما نمی‌شکند.
  * در AppTest هم امن است (popover فقط رندر می‌شود و باز نمی‌گردد).
"""
from __future__ import annotations


def _qmark() -> str:
    """برچسب دکمه — «؟» برای فارسی، «?» برای انگلیسی."""
    try:
        from core.i18n import get_lang
        return "?" if (get_lang() or "fa") == "en" else "؟"
    except Exception:  # noqa: BLE001 — bare mode / تست
        return "؟"


def hint(*texts: str, title: str | None = None) -> None:
    """علامت سوال کوچک — با کلیک، توضیحات بخش نشان داده می‌شود (popover).

    Args:
        *texts: یک یا چند پاراگراف توضیح؛ متن‌های خالی نادیده گرفته می‌شوند.
        title:  عنوان اختیاری داخل پاپ‌اور (بولد، بالای متن).
    """
    body = "\n\n".join(t for t in texts if isinstance(t, str) and t.strip())
    if not body:
        return
    import streamlit as st

    def _render() -> None:
        if title:
            st.markdown(f"**{title}**")
        st.markdown(body)

    try:
        pop = getattr(st, "popover", None)
        if pop is not None:
            try:
                with pop(_qmark()):
                    _render()
                return
            except Exception:  # noqa: BLE001 — popover شکست → بیفت روی expander
                pass
        # فال‌بک نسخه‌های خیلی قدیمی یا popover شکسته: expander جمع‌شده — باز هم از صفحه بیرون است
        with st.expander(_qmark() + " راهنما", expanded=False):
            _render()
    except Exception:  # noqa: BLE001 — هیچ‌وقت به‌خاطر راهنما صفحه نشکند
        pass
