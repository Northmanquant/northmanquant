"""core/webview.py — نمایش HTML داخل iframe، ضد deprecation استریم‌لیت.

Streamlit تازه (≥۱٫۵۵) ``st.iframe`` دارد و ``components.v1.html`` را
منسوخ کرده (حذف بعد از ۲۰۲۶-۰۶-۰۱)؛ نسخه‌های قدیمی‌تر مثل ۱٫۵۴ که
requirements می‌قفل کند اصلاً ``st.iframe`` ندارند. این پوشش هر دو
دنیا را پوشش می‌دهد: ``st.iframe`` اگر موجود بود، وگرنه فال‌بک به
``components.v1.html`` — امضای مشترک و بدون زنگ خطر در هیچ نسخه‌ای.

ترجمه: پنل‌های SVG متن فارسی دارند و در حالت انگلیسی باید با ``deep_en``
پوشش شوند — پچ i18n فقط ``components.v1.html`` را می‌بیند، پس این لایه
خودش ترجمه را اعمال می‌کند تا مسیر ``st.iframe`` هم ترجمه بماند.
"""
from __future__ import annotations

from typing import Any


def iframe_html(html: str, *, height: int = 600, scrolling: bool = False,
                **kwargs: Any) -> None:
    """HTML را داخل iframe کامل‌عرض رندر می‌کند — سازگار با هر نسخه‌ی استریم‌لیت.

    ترجمه‌ی en روی محتوا اعمال می‌شود (deep_en روی رشته) و ورودی خراب
    امن است: non-str = بدون ترجمه رد می‌شود.
    """
    try:
        from core.i18n import deep_en
        if isinstance(html, str):
            html = deep_en(html)
    except Exception:  # noqa: BLE001 — ترجمه هرگز رندر را نمی‌شکند
        pass

    import streamlit as st

    if hasattr(st, "iframe"):
        # st.iframe خودش HTML خام را در srcdoc جاسازی می‌کند؛ عرض پیش‌فرض stretch است
        st.iframe(html, height=height)
    else:
        import streamlit.components.v1 as components

        components.html(html, height=height, scrolling=scrolling, **kwargs)
