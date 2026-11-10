# -*- coding: utf-8 -*-
"""آزمون‌های core/showcase_daily.py — آلبومِ روزانه‌ی تلگرام (بدونِ شبکه).
اجرا:  python scripts/test_showcase_daily.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("STREAMLIT_SERVER_HEADLESS", "true")

from core import showcase_daily as SD  # noqa: E402
from core import telegram as TG  # noqa: E402

ok = 0
fail = 0


def check(name, fn):
    global ok, fail
    try:
        res = fn()
        msg = res if isinstance(res, str) else "ok"
        print(f"  OK   {name}" + (f" — {msg}" if msg != "ok" else ""))
        ok += 1
    except Exception as e:  # noqa: BLE001
        print(f"  FAIL {name} — {type(e).__name__}: {e}")
        fail += 1


def _wait_res(sym="BTC-USDT", iv="1hour", score=-35.0):
    return {"symbol": sym, "interval": iv, "score": score, "dec": 2, "price": 60000.0,
            "active": False, "rr": 0,
            "plan": {"status": "wait", "direction": "⏸ انتظار (بدون معامله)",
                     "entry": None, "stop": None, "targets": [], "rr": 0,
                     "confidence": 0, "atr": 500.0, "mode": None}}


def _active_res(sym="ETH-USDT", iv="4hour", score=-59.0, rr=1.0, conf=62):
    return {"symbol": sym, "interval": iv, "score": score, "dec": 2, "price": 2000.0,
            "active": True, "rr": rr,
            "plan": {"status": "active", "direction": "لانگ (خرید) 🟢",
                     "entry": 2045.18, "stop": 1997.12,
                     "targets": [(2093.24, 1.0), (2141.31, 2.0), (2189.37, 3.0)],
                     "rr": rr, "confidence": conf, "atr": 39.4, "mode": "fade"}}


print("== select (اولویتِ فعال‌ها) ==")
def _sel():
    rs = [_wait_res("BTC-USDT", "1hour", -35), _active_res("ETH-USDT", "4hour"),
          _wait_res("SOL-USDT", "1hour", -53), _wait_res("BTC-USDT", "1day", -52)]
    p = SD.select(rs, max_images=3)
    assert p[0]["active"], "first pick must be the ACTIVE setup"
    assert len(p) == 3
    # ۲ فعال با قدرتِ متفاوت — قوی‌تر اول
    rs2 = [_active_res("A-USDT", score=-10), _active_res("B-USDT", score=-80)]
    p2 = SD.select(rs2, max_images=8)
    assert p2[0]["symbol"] == "B-USDT", "stronger |score| first among actives"
    return f"picked {len(p)} then {len(p2)}"
check("select ordering (active first, strong first)", _sel)

print("== describe_plain ==")
def _desc():
    a = SD.describe_plain(_active_res())
    assert "ETH-USDT" in a and "ورود 2,045.18" in a and "حدضرر 1,997.12" in a
    assert "هدفِ اول 2,093.24" in a and "62٪" in a
    w = SD.describe_plain(_wait_res())
    assert "انتظار" in w and "BTC-USDT" in w and "-35" in w
    return "active+wait formats"
check("describe_plain (active + wait)", _desc)

print("== build_summary_text ==")
def _txt():
    picked = [_active_res(), _active_res("SOL-USDT", "1day", -61, conf=55), _wait_res()]
    t = SD.build_summary_text(picked)
    assert "گزارش روزانه‌ی NorthmanQuant" in t
    assert "ستاپ‌های فعالِ امروز: 2" in t
    assert "بدون ستاپِ معتبر: 1" in t
    assert "۱۴ بازرسیِ خودکار" in t
    assert len(t) <= TG.MAX_TEXT, f"text too long: {len(t)}"
    assert "<b>" in t  # HTML
    # متنِ طولانیِ ساختگی — سقف حفظ شود
    many = [_active_res(f"S{i}-USDT") for i in range(10)] + [_wait_res(f"W{i}-USDT") for i in range(20)]
    t2 = SD.build_summary_text(many)
    assert len(t2) <= TG.MAX_TEXT
    return f"{len(t)} chars · truncate ok ({len(t2)})"
check("build_summary_text (content + cap)", _txt)

print("== album payload ==")
def _payload():
    imgs = [(f"{i:02d}_img.png", b"\x89PNG" + b"x" * 50) for i in range(1, 13)]
    media_s, files = SD.build_media_payload(imgs, "caption here")
    import json
    media = json.loads(media_s)
    assert len(media) == 10, "max 10 photos per album"
    assert len(files) == 10
    for i, m in enumerate(media):
        assert m["media"] == f"attach://file{i}"
        assert f"file{i}" in files
    assert media[0]["caption"] == "caption here"
    assert media[0]["parse_mode"] == "HTML"
    assert "caption" not in media[1]
    long_cap = "ک" * 2000
    media2, _ = TG._build_album_parts(imgs, long_cap)
    import json as j2
    assert len(j2.loads(media2)[0]["caption"]) <= 1024
    return "10 max · attach refs · caption on #1"
check("sendMediaGroup payload shape", _payload)

print("== disabled behavior (بدون شبکه) ==")
def _disabled():
    # در این محیط توکن تلگرام نیست → enabled False و همه‌ی مسیرها بی‌خطرند
    assert not TG.enabled()
    assert TG.send_album([("a.png", b"x" * 100)], "cap") is False
    assert TG.send_album([], "cap") is False  # خالی = False، نه exception
    status = SD.run()
    assert status == "غیرفعال", f"unexpected status: {status}"
    return f"run() → {status}"
check("disabled: no send, no crash", _disabled)

print("== collect نماد خراب را نمی‌بُرد ==")
def _collect_resilient():
    bad = SD.analyse_one("NOT-EXISTING-USDT", "1hour")
    assert bad is None or isinstance(bad, dict)  # None یا نتیجه — هرگز exception
    return "no exception on bad symbol"
check("analyse_one resilient to bad symbol", _collect_resilient)

print(f"\n===== {ok} passed, {fail} failed =====")
sys.exit(1 if fail else 0)
