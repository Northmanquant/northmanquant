# -*- coding: utf-8 -*-
"""
NorthmanQuant — نقطه‌ی ورود (نسخه‌ی نازک)
==========================================
app_base.py فایل اصلی است و همه‌چیز (ترجمه‌ی چندزبانه، بخش‌ها، اسکنر)
داخل خودش کامل است. این فایل فقط آن را اجرا می‌کند.

اجرا:  streamlit run app.py
"""
from __future__ import annotations

import streamlit as st

import app_base as B

if __name__ == "__main__":
    try:
        B.main()
    except Exception as e:  # noqa: BLE001
        st.exception(e)
        st.error("An unexpected error occurred — please refresh the page (F5).")
