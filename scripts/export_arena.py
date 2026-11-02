# -*- coding: utf-8 -*-
"""scripts/export_arena.py — خروجی کامل تاریخچه‌ی میدان (برای تحلیل فاز ۹)
==========================================================================
اجرا از ریشه‌ی ریپو:
    python scripts/export_arena.py

خروجی: فایل «arena_export.json» — همه‌ی معامله‌های قابل‌قبول (تا ۲۰۰۰ رکورد
اخیر، همان مسیر و فیلتر خود اپ) + هشدارهای اخیر + متادیتا.
زیر GitHub Actions همین فایل به‌صورت Artifact آپلود می‌شود
(ورک‌فلو arena-export.yml) تا از بیرون هم قابل دانلود باشد.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    from core import alerts as AL
    from core import arena_store

    store = arena_store.get_store()
    backend = store.backend
    trades = store.load_all()
    alerts = AL.recent_alerts(200)

    payload = {
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "backend": backend,
        "n_trades": len(trades),
        "n_alerts": len(alerts),
        "trades": trades,
        "alerts": alerts,
    }
    out = Path("arena_export.json")
    out.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    closed = sum(1 for t in trades if str(t.get("status")) == "closed")
    print(f"✅ {out} — بک‌اند: {backend} · {len(trades)} معامله ({closed} بسته) · {len(alerts)} هشدار")
    if backend != "supabase":
        print("❗ هشدار: Supabase در دسترس نبود؛ خواندن از fallback محلی.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
