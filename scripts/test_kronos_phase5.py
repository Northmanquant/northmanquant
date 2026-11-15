# -*- coding: utf-8 -*-
"""آزمونِ فازِ پنجِ کرونوس — بستنِ حلقه‌ی «روزِ حکمِ خودکار»
==========================================================================
قرارداد قفل است (فازِ دو/سه) و وضعیتش زنده از دفتر می‌آید (فازِ چهار)؛
اینجا حلقه‌ی آخر قفل می‌شود: اگر بچی (روزانه یا هفتگی) دروازه را رد کند،
همان ران باید قرارداد را اجرا کند — بنرِ حکم، ثبتِ idempotentِ روزِ حکم،
آرشیوِ بازنشستگی — و تا موعد نرسیده، همه‌چیز کاملاً ساکت بماند.

همه‌ی آزمون‌ها قطعی و بدونِ شبکه‌اند؛ هر فایلی در tmp ساخته می‌شود و به
دفترِ واقعیِ مخزن دست نمی‌زند.

اجرا:  python scripts/test_kronos_phase5.py
"""
import json
import os
import sys
import tempfile
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
os.environ.setdefault("STREAMLIT_SERVER_HEADLESS", "true")

from core import kronos_promotion as KP  # noqa: E402
import kronos_session as KS  # noqa: E402 — جلسه‌گیر؛ اجرای حکم اینجاست

ok = 0
fail = 0


def check(name, fn):
    global ok, fail
    try:
        fn()
        ok += 1
        print(f"  OK   {name}")
    except Exception as exc:  # noqa: BLE001 — گزارشِ آزمون
        fail += 1
        print(f"  FAIL {name}: {type(exc).__name__}: {exc}")


def _gate(n, rate):
    """دیکته‌ی هم‌شکلِ خروجیِ kronos_witness.gate_stats — بدونِ I/O."""
    return {"ok": True, "real": {"n": n, "rate": rate},
            "stub": {"n": 0, "rate": None}, "gate_fa": "آزمایشی"}


def _now():
    return datetime(2026, 11, 15, 12, 0, 0)  # naive = وقتِ دیوارِ تهران


# ---- ثبتِ روزِ حکم (ماژولِ قرارداد) --------------------------------------

def t1_continue_records_nothing():
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "kronos_verdict_record.json")
        res = KP.record_verdict(gate=_gate(18, 72.2), path=p, now=_now())
        assert res.get("ok") and not res.get("recorded"), res
        assert "موعد" in (res.get("why_fa") or ""), res
        assert not os.path.isfile(p), "ادامه نباید هیچ فایلی بسازد"


def t2_promote_records_milestone():
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "kronos_verdict_record.json")
        res = KP.record_verdict(gate=_gate(205, 60.0), path=p, now=_now())
        assert res.get("recorded") is True, res
        rec = json.load(open(p, encoding="utf-8"))
        assert rec["verdict"] == "promote", rec
        assert rec["n"] == 205 and rec["rate"] == 60.0, rec
        assert rec["sessions_threshold"] == 200 and rec["agree_threshold_pct"] == 55.0, rec
        assert rec["contract_locked_at"] == KP.LOCKED_AT, rec
        ts = datetime.fromisoformat(rec["ts"])
        assert ts.utcoffset() is not None, "ts باید سازگارِ منطقه باشد"


def t3_record_is_idempotent_against_new_verdicts():
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "kronos_verdict_record.json")
        assert KP.record_verdict(gate=_gate(205, 60.0), path=p, now=_now()).get("recorded")
        # حکمِ مخالفِ بعدی حقِ بازنویسیِ تاریخ را ندارد
        res = KP.record_verdict(gate=_gate(210, 48.0), path=p, now=_now())
        assert res.get("ok") and not res.get("recorded"), res
        assert "idempotent" in (res.get("why_fa") or ""), res
        assert json.load(open(p, encoding="utf-8"))["verdict"] == "promote"


def t4_retire_records_with_reason():
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "kronos_verdict_record.json")
        res = KP.record_verdict(gate=_gate(210, 48.0), path=p, now=_now())
        assert res.get("recorded") is True, res
        rec = json.load(open(p, encoding="utf-8"))
        assert rec["verdict"] == "retire", rec
        assert rec["reasons_fa"], "بازنشستگی باید دلیلِ عددی داشته باشد"


def t5_verdict_record_readback():
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "none.json")
        r0 = KP.verdict_record(p)
        assert r0.get("ok") and not r0.get("exists"), r0
        KP.record_verdict(gate=_gate(205, 60.0), path=p, now=_now())
        r1 = KP.verdict_record(p)
        assert r1.get("exists") and r1["record"]["verdict"] == "promote", r1


# ---- اجرای خودکار در پایانِ بچ (جلسه‌گیر) --------------------------------

def t6_check_verdict_silent_before_due():
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "kronos_verdict_record.json")
        cap: list[str] = []
        res = KS.check_verdict(gate=_gate(18, 72.2), record_path=p, out=cap.append)
        assert res == {"executed": False, "verdict": "continue"}, res
        assert cap == [], f"ادامه باید ساکت باشد: {cap}"
        assert not os.path.isfile(p)


def t7_check_verdict_executes_on_promote():
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "kronos_verdict_record.json")
        cap: list[str] = []
        res = KS.check_verdict(gate=_gate(205, 60.0), record_path=p, out=cap.append)
        assert res.get("executed") and res.get("verdict") == "promote", res
        assert res.get("recorded") is True, res
        text = "\n".join(cap)
        assert "قراردادِ پیش‌ثبت‌شده" in text, text
        assert "روزِ حکم رسید" in text, text
        assert os.path.isfile(p)


def t8_rerun_does_not_repeat_banner():
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "kronos_verdict_record.json")
        KS.check_verdict(gate=_gate(205, 60.0), record_path=p, out=lambda *a: None)
        cap: list[str] = []
        res = KS.check_verdict(gate=_gate(205, 60.0), record_path=p, out=cap.append)
        assert res.get("executed") and not res.get("recorded"), res
        text = "\n".join(cap)
        assert "قبلاً اجرا شده" in text, text
        assert "قراردادِ پیش‌ثبت‌شده" not in text, "بنر فقط در اولین گذر است"


def t9_check_verdict_retire_archives_tmp_ledger():
    with tempfile.TemporaryDirectory() as td:
        led = os.path.join(td, "kronos_log.jsonl")
        with open(led, "w", encoding="utf-8") as f:
            f.write('{"backend":"kronos","ts":"2026-11-15T09:00:00"}\n')
            f.write('{"backend":"kronos","ts":"2026-11-15T10:00:00"}\n')
        p = os.path.join(td, "kronos_verdict_record.json")
        cap: list[str] = []
        res = KS.check_verdict(gate=_gate(210, 48.0), record_path=p,
                               archive_ledger=led, out=cap.append)
        assert res.get("executed") and res.get("verdict") == "retire", res
        assert res.get("archived") is True, res
        text = "\n".join(cap)
        assert "آرشیو" in text and "کپی، نه پاک‌کاری" in text, text
        arc = [f for f in os.listdir(td) if f.startswith("kronos_log_archive_")]
        assert len(arc) == 1 and os.path.isfile(os.path.join(td, arc[0])), arc


def t10_check_verdict_never_raises():
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "kronos_verdict_record.json")
        cap: list[str] = []
        res = KS.check_verdict(gate={"ok": False}, record_path=p, out=cap.append)
        assert res == {"executed": False, "verdict": "continue"}, res
        # بدونِ gate — از دفترِ واقعی می‌خواند (۱۸/۲۰۰ → ادامه؛ ساکت و بی‌نوشتن)
        res2 = KS.check_verdict(gate=None, record_path=p, out=cap.append)
        assert res2.get("verdict") == "continue", res2
        assert not os.path.isfile(p), "هیچ‌کدام نباید فایل بسازند"


if __name__ == "__main__":
    print("== آزمونِ فازِ پنجِ کرونوس — روزِ حکمِ خودکار ==")
    check("ادامه — هیچ ثبت و هیچ فایلی", t1_continue_records_nothing)
    check("ارتقا — ثبتِ لحظه‌ی گذر با اعدادِ قرارداد", t2_promote_records_milestone)
    check("idempotence — حکمِ بعدی تاریخ را بازنویسی نمی‌کند", t3_record_is_idempotent_against_new_verdicts)
    check("بازنشستگی — ثبت با دلیلِ عددی", t4_retire_records_with_reason)
    check("خواندنِ سابقه — نبود/هست", t5_verdict_record_readback)
    check("جلسه‌گیر — پیش از موعد ساکت", t6_check_verdict_silent_before_due)
    check("جلسه‌گیر — اجرای روزِ حکم در گذر", t7_check_verdict_executes_on_promote)
    check("جلسه‌گیر — رانِ بعدی بنر را تکرار نمی‌کند", t8_rerun_does_not_repeat_banner)
    check("جلسه‌گیر — بازنشستگی آرشیو می‌کند (دفترِ موقت)", t9_check_verdict_retire_archives_tmp_ledger)
    check("جلسه‌گیر — هرگز استثنا نمی‌دهد", t10_check_verdict_never_raises)
    print(f"\nنتیجه: {ok} سبز · {fail} قرمز")
    sys.exit(1 if fail else 0)
