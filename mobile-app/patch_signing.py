#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تزریق signingConfig پایدار در build.gradle اندرویدِ تولیدشده توسط Capacitor.
قالب Capacitor هیچ signingConfig ای ندارد → هر رانر CI کلید دیباگ تصادفی می‌سازد
→ امضای هر APK متفاوت → آپدیت با خطای «package conflicts» رد می‌شود.
این اسکریپت buildType دیباگ را به stable.keystore (کنار ماژول اپ) وصل می‌کند.
Idempotent نیست عمداً: در CI هر بار android/ از نو ساخته می‌شود."""
from pathlib import Path

APP = Path(__file__).resolve().parent / "android" / "app"
P = APP / "build.gradle"

s = P.read_text(encoding="utf-8")
assert "signingConfigs" not in s, "build.gradle already patched"
anchor = "    buildTypes {\n"
assert s.count(anchor) == 1, "buildTypes anchor not unique — template changed?"

block = """    signingConfigs {
        stable {
            storeFile file('stable.keystore')
            storePassword 'android'
            keyAlias 'androiddebugkey'
            keyPassword 'android'
        }
    }
    buildTypes {
        debug {
            signingConfig signingConfigs.stable
        }
"""
P.write_text(s.replace(anchor, block, 1), encoding="utf-8")
print("signingConfig injected ->", P)
