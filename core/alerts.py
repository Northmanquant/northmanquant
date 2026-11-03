# -*- coding: utf-8 -*-
"""core/alerts.py — هشدارهای «میدان ایجنت‌ها»
=============================================
رویدادهای مهم میدان به‌صورت دائمی ثبت می‌شوند:
  • open    — معامله‌ی تازه باز شد (ایجنت، نماد، جهت، ورود/استاپ)
  • close   — معامله بسته شد (نتیجه، R خالص، امتیاز)
  • regime  — رژیم بازار BTC عوض شد (بالای/زیر میانگین متحرک)

ذخیره‌سازی: جدول `arena_alerts` در Supabase (اگر SUPABASE_URL/KEY ست باشد)
وگرنه فایل `arena_alerts.json` کنار اپ (fallback محلی — مثل arena_store).

چرا id قطعی (deterministic)؟ جلوگیری از هشدار تکراری: id بازشدن = «op:{trade_id}»
و بسته‌شدن = «cl:{trade_id}» — هر معامله حداکثر یک هشدار باز و یک هشدار بسته
دارد، حتی اگر کد دو بار اجرا شود. مثل arena_trades، RLS به anon اجازه‌ی insert
می‌دهد پس موقعِ خواندن فقط رکوردهای منطقی (valid_alert) پذیرفته می‌شوند.
"""
from __future__ import annotations

import json
import math
import os
import re
import threading
import time
from typing import Any, Dict, List, Optional

from core.arena_store import _json_safe, _secrets_get, _SYMBOL_RE, _utcnow_iso

TABLE = "arena_alerts"
LOCAL_FILE = "arena_alerts.json"
_LOCK = threading.RLock()

# «bot» — نشانگرهای وضعیت بات تلگرام (مثل «خلاصه‌ی روزانه ارسال شد»)؛
# فقط برای ضدتکرار — در فید اپ نمایش داده نمی‌شود و فقط یک‌بار درج می‌شود.
KINDS = ("open", "close", "regime", "bot")
REGIME_SYMBOL = "BTCUSDT"          # بدون «/» — با regex نمادها سازگار است
MAX_TEXT = 400
_MAX_ROWS = 300                    # سقف رکورد در fallback محلی


# ------------------------------------------------------------- اعتبارسنجی رکورد
def valid_alert(d: Any) -> bool:
    """True فقط برای هشدارهای منطقی — بقیه موقع خواندن دور ریخته می‌شوند."""
    if not isinstance(d, dict):
        return False
    kind = str(d.get("kind") or "")
    if kind not in KINDS:
        return False
    sym = str(d.get("symbol") or "").strip()
    if kind == "regime":
        if sym != REGIME_SYMBOL:
            return False
    else:
        if not _SYMBOL_RE.match(sym):
            return False
        agent = str(d.get("agent") or "").strip()
        if not agent or len(agent) > 40:
            return False
    try:
        direction = int(d.get("direction"))
    except (TypeError, ValueError):
        return False
    if direction not in (-1, 0, 1):
        return False
    for k in ("entry", "stop", "r", "points", "ma", "price"):
        v = d.get(k)
        if v is not None:
            try:
                x = float(v)
            except (TypeError, ValueError):
                return False
            if not math.isfinite(x) or abs(x) > 1e12:
                return False
    try:
        result = d.get("result")
        if result is not None and str(result) not in (
                "win", "loss", "be", "timeout_win", "timeout_loss", "timeout_be"):
            return False
    except Exception:  # noqa: BLE001
        return False
    if len(str(d.get("evidence") or "")) > MAX_TEXT:
        return False
    return True


# ------------------------------------------------------------- سازنده‌های هشدار
def _f(t: dict, key: str) -> Optional[float]:
    try:
        x = float(t.get(key))
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def open_alert(t: dict) -> dict:
    """هشدار بازشدن معامله از رکورد make_trade_record."""
    ev = str(t.get("evidence") or "")[:200]
    return {"id": f"op:{t.get('id')}", "kind": "open",
            "agent": str(t.get("agent") or ""), "symbol": str(t.get("symbol") or "").upper(),
            "direction": int(t.get("direction") or 0),
            "entry": _f(t, "entry"), "stop": _f(t, "stop"), "tp1": _f(t, "tp1"),
            "rr": _f(t, "rr"), "interval": str(t.get("interval") or ""),
            "exchange": str(t.get("exchange") or ""), "evidence": ev,
            "created_at": _utcnow_iso()}


def close_alert(t: dict) -> dict:
    """هشدار بسته‌شدن معامله از رکورد ادغام‌شده ({**trade, **patch})."""
    return {"id": f"cl:{t.get('id')}", "kind": "close",
            "agent": str(t.get("agent") or ""), "symbol": str(t.get("symbol") or "").upper(),
            "direction": int(t.get("direction") or 0),
            "result": str(t.get("result") or ""), "r": _f(t, "realized_r"),
            "points": _f(t, "points"), "exit": str(t.get("exit_reason") or ""),
            "entry": _f(t, "entry"), "closed_price": _f(t, "closed_price"),
            "created_at": _utcnow_iso()}


def regime_alert(reg: dict) -> dict:
    """هشدار تغییر رژیم بازار — جهت رژیم، فاصله‌ی قیمت از میانگین."""
    d = int(reg.get("dir") or 0)
    return {"id": f"rg:{d}:{int(time.time())}", "kind": "regime",
            "agent": "", "symbol": REGIME_SYMBOL, "direction": d,
            "ma": _f(reg, "ma"), "price": _f(reg, "price"),
            "created_at": _utcnow_iso()}


# ------------------------------------------------------------- تغییر رژیم
def push_regime_change(alerts: "AlertStore", reg: dict) -> bool:
    """اگر رژیم نسبت به آخرین هشدار رژیم عوض شده باشد، هشدار تازه ثبت می‌کند.
    همان جهت قبلی یا دیتای نامشخص (dir=0) → کاری نکن."""
    d = int(reg.get("dir") or 0)
    if d == 0:
        return False
    try:
        recent = alerts.load_recent(30)
    except Exception:  # noqa: BLE001
        return False
    for a in recent:                       # تازه‌ترین اول
        if a.get("kind") == "regime":
            if int(a.get("direction") or 0) == d:
                return False               # رژیم عوض نشده
            break
    try:
        return bool(alerts.insert(regime_alert(reg)))
    except Exception:  # noqa: BLE001
        return False


# ------------------------------------------------------------- Store
class AlertStore:
    """همان الگوی ArenaStore: اول Supabase، بعد فایل محلی."""

    def __init__(self) -> None:
        self._client = None
        self._client_tried = False
        self._client_err = ""

    def _get_client(self):
        if not self._client_tried:
            self._client_tried = True
            url = _secrets_get("SUPABASE_URL")
            key = _secrets_get("SUPABASE_KEY") or _secrets_get("SUPABASE_ANON_KEY")
            if url and key:
                try:
                    from supabase import create_client  # type: ignore
                    self._client = create_client(url, key)
                except Exception as e:  # noqa: BLE001
                    self._client = None
                    self._client_err = str(e)
        return self._client

    @property
    def backend(self) -> str:
        return "supabase" if self._get_client() is not None else "local"

    # ----- local json ------------------------------------------------------------
    def _load_local(self) -> List[Dict[str, Any]]:
        if not os.path.exists(LOCAL_FILE):
            return []
        try:
            with open(LOCAL_FILE, "r", encoding="utf-8") as f:
                rows = json.load(f)
            return rows if isinstance(rows, list) else []
        except Exception:  # noqa: BLE001
            return []

    def _write_local(self, rows: List[Dict[str, Any]]) -> None:
        tmp = LOCAL_FILE + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(rows, f, ensure_ascii=False)
            os.replace(tmp, LOCAL_FILE)
        except Exception:  # noqa: BLE001
            pass

    # ----- api -------------------------------------------------------------------
    def load_recent(self, limit: int = 80) -> List[Dict[str, Any]]:
        """تازه‌ترین هشدارها — فقط رکوردهای منطقی (ضد تزریق مثل arena_store)."""
        limit = max(1, min(int(limit), 200))
        client = self._get_client()
        if client is not None:
            try:
                res = (client.table(TABLE)
                       .select("id, kind, symbol, data, created_at")
                       .order("created_at", desc=True).limit(limit).execute())
                out: List[Dict[str, Any]] = []
                for row in (res.data or []):
                    d = dict(row.get("data") or {})
                    d["created_at"] = row.get("created_at") or d.get("created_at")
                    if row.get("kind"):
                        d["kind"] = row["kind"]
                    if row.get("symbol"):
                        d["symbol"] = row["symbol"]
                    if valid_alert(d):
                        out.append(d)
                return out
            except Exception:  # noqa: BLE001
                pass
        return [d for d in self._load_local() if valid_alert(d)][:limit]

    def insert(self, a: dict) -> bool:
        """هشدار تازه — اگر id تکراری باشد False (بدون نوشتن دوباره)."""
        rec = {**a, "created_at": a.get("created_at") or _utcnow_iso()}
        if not valid_alert(rec):
            return False
        rec["id"] = str(rec.get("id") or "")
        if not rec["id"]:
            return False
        client = self._get_client()
        if client is not None:
            try:
                row = {"id": rec["id"], "kind": str(rec.get("kind")),
                       "symbol": str(rec.get("symbol")), "data": _json_safe(rec),
                       "created_at": rec["created_at"], "updated_at": _utcnow_iso()}
                client.table(TABLE).insert(row).execute()
                return True
            except Exception as e:  # noqa: BLE001
                s = str(e)
                if "23505" in s or "duplicate" in s.lower():
                    return False           # هشدار تکراری — خطا نیست
                # خطای شبکه‌ای → fallback محلی
        with _LOCK:
            rows = self._load_local()
            if any(str(r.get("id")) == rec["id"] for r in rows):
                return False
            rows.insert(0, _json_safe(rec))
            self._write_local(rows[:_MAX_ROWS])
        return True


_ALERTS: Optional[AlertStore] = None


def get_alerts() -> AlertStore:
    global _ALERTS
    if _ALERTS is None:
        _ALERTS = AlertStore()
    return _ALERTS


# توابع کوتاه سازگار
def recent_alerts(limit: int = 80) -> List[Dict[str, Any]]:
    return get_alerts().load_recent(limit)


def push_alert(a: dict) -> bool:
    return get_alerts().insert(a)
