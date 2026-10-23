# -*- coding: utf-8 -*-
"""
core/community_store.py
========================
بک‌اند پایدار برای «برد تحلیل‌های اجتماعی» (community_analyses).

منبع داده (به ترتیب اولویت):
  1) Supabase      — اگر SUPABASE_URL و SUPABASE_KEY در st.secrets یا متغیر محیطی باشد
  2) فایل JSON محلی — fallback (رفتار قدیمی؛ روی Streamlit Cloud با هر redeploy پاک می‌شود)

ویژگی‌ها:
  * drop-in بودن: load_community() لیست dict برمی‌گرداند و save_community(record)
    همان dict قبلی را می‌گیرد؛ شکل داده‌ها backward-compatible می‌ماند.
  * فیلدهای اضافه‌ای که UI قدیمی داخل رکورد می‌نوشت، داخل payload حفظ و
    هنگام خواندن دوباره surface می‌شوند (کد نمایش فعلی بدون تغییر کار می‌کند).
  * خطاها هرگز اپ را نمی‌کشند: هر خرابیِ Supabase → fallback محلی + پیام در sidebar.
  * نوشتن اتمیک فایل محلی (tmp + os.replace) با قفل thread و سقف تعداد رکورد.
  * مقادیر numpy / NaN / Inf / datetime به شکل JSON-safe تبدیل می‌شوند.
"""

from __future__ import annotations

import json
import math
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st

# ---------------------------------------------------------------- تنظیمات
LOCAL_JSON_PATH = Path(os.environ.get("COMMUNITY_JSON_PATH", "community_analyses.json"))
TABLE = "community_analyses"
FETCH_LIMIT = 500            # حداکثر رکورد دریافتی از Supabase در هر خواندن
MAX_LOCAL_RECORDS = 1000     # سقف رکوردهای فایل محلی (تا بی‌نهایت بزرگ نشود)
CACHE_TTL_SEC = 20           # کش کوتاه خواندن از Supabase
CONNECT_TIMEOUT_SEC = 10     # تایم‌اوت اتصال به Supabase
ROW_KEYS = ("id", "created_at", "symbol", "timeframe", "direction", "author", "payload")

try:
    from supabase import create_client  # type: ignore
    SUPABASE_INSTALLED = True
except Exception:
    create_client = None  # type: ignore[assignment]
    SUPABASE_INSTALLED = False

_local_lock = threading.Lock()
_UNSAVED_KEY = "community_store_session_unsaved"
_BANNER_KEY = "community_store_banner_shown"


# ---------------------------------------------------------------- ابزارهای کمکی
def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _valid_ts(value: str) -> bool:
    try:
        datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return True
    except Exception:
        return False


def _json_safe(value: Any) -> Any:
    """هر مقداری را به چیزی تبدیل می‌کند که json و Supabase بتوانند ذخیره کنند."""
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if hasattr(value, "isoformat"):  # datetime / date
        return value.isoformat()
    if hasattr(value, "item"):  # numpy scalar
        try:
            return _json_safe(value.item())
        except Exception:
            return str(value)
    try:
        json.dumps(value)
        return value
    except Exception:
        return str(value)


def _secrets_get(key: str) -> Optional[str]:
    """خواندن کلید از متغیر محیطی (لوکال/CI) یا st.secrets (کلاد)."""
    val = os.environ.get(key)
    if val:
        return val.strip()
    try:
        val = st.secrets[key]  # type: ignore[index]
        return str(val).strip() if val else None
    except Exception:
        return None


def _normalize_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """رکورد خام ورودی را به شکل استاندارد ۷ ستونه تبدیل می‌کند.

    هر فیلد اضافه (مثلاً متن تحلیل، اسکورها، ...) داخل payload حفظ می‌شود تا
    کد نمایش قدیمی که به آن فیلدها تکیه دارد نشکند.
    """
    src = dict(record or {})
    rec: Dict[str, Any] = {
        "id": str(src.pop("id", "") or uuid.uuid4()),
        "created_at": str(src.pop("created_at", "") or ""),
        "symbol": str(src.pop("symbol", "") or "").upper().strip() or "UNKNOWN",
        "timeframe": str(src.pop("timeframe", "") or "").strip() or "-",
        "direction": str(src.pop("direction", "") or "").lower().strip() or "neutral",
        "author": str(src.pop("author", "") or "").strip()[:40] or "ناشناس",
    }
    try:
        rec["id"] = str(uuid.UUID(rec["id"]))
    except ValueError:
        rec["id"] = str(uuid.uuid4())
    if not _valid_ts(rec["created_at"]):
        rec["created_at"] = _utcnow_iso()

    payload = src.pop("payload", None)
    if not isinstance(payload, dict):
        payload = {}
    # هر فیلد اضافه‌ای که UI قدیمی می‌نوشت، داخل payload حفظ می‌شود
    payload.update({k: _json_safe(v) for k, v in src.items()})
    rec["payload"] = _json_safe(payload)
    return rec


# ---------------------------------------------------------------- کلاس اصلی
class CommunityStore:
    """لایه ذخیره‌سازی برد مشترک با اولویت Supabase و fallback فایل محلی."""

    def __init__(self) -> None:
        self._client: Any = None
        self._sb_checked = False
        self._cache: Optional[List[Dict[str, Any]]] = None
        self._cache_ts = 0.0
        # پیام‌های قابل نمایش به کاربر
        self.client_err: Optional[str] = None
        self.last_error: Optional[str] = None

    # ---------------- Supabase ----------------
    def _get_client(self) -> Any:
        """کلاینت Supabase را فقط یک‌بار می‌سازد؛ در نبود کلید/پکیج، None برمی‌گرداند."""
        if self._sb_checked:
            return self._client
        self._sb_checked = True

        if not SUPABASE_INSTALLED:
            self.client_err = "پکیج supabase نصب نیست (pip install supabase==2.11.0)"
            return None
        url = _secrets_get("SUPABASE_URL")
        key = _secrets_get("SUPABASE_KEY")
        if not url or not key:
            self.client_err = "SUPABASE_URL / SUPABASE_KEY تنظیم نشده است"
            return None
        try:
            try:
                from supabase import ClientOptions  # type: ignore
                opts = ClientOptions(postgrest_client_timeout=CONNECT_TIMEOUT_SEC)
                self._client = create_client(url, key, options=opts)
            except Exception:
                # نسخه‌های قدیمی‌تر پارامتر options را ندارند
                self._client = create_client(url, key)
        except Exception as e:
            self.client_err = f"ساخت کلاینت Supabase ناموفق بود: {e}"
            self._client = None
        return self._client

    @property
    def backend(self) -> str:
        return "supabase" if self._get_client() is not None else "local-json"

    def _fetch_remote(self) -> Optional[List[Dict[str, Any]]]:
        """خواندن از Supabase؛ در خطا None برمی‌گرداند تا caller به محلی برود."""
        client = self._get_client()
        if client is None:
            return None
        now = time.monotonic()
        if self._cache is not None and (now - self._cache_ts) < CACHE_TTL_SEC:
            return self._cache
        try:
            res = (
                client.table(TABLE)
                .select(", ".join(ROW_KEYS))
                .order("created_at", desc=True)
                .limit(FETCH_LIMIT)
                .execute()
            )
            rows = res.data or []
            self._cache = rows
            self._cache_ts = now
            self.last_error = None
            return rows
        except Exception as e:
            self.last_error = f"خواندن از Supabase ناموفق بود، به فایل محلی برمی‌گردیم: {e}"
            return None

    # ---------------- fallback محلی ----------------
    def _load_local(self) -> List[Dict[str, Any]]:
        try:
            if not LOCAL_JSON_PATH.exists():
                return []
            with _local_lock:
                data = json.loads(LOCAL_JSON_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):  # فرمت‌های قدیمی {"analyses": [...]}
                data = data.get("analyses") or data.get("items") or []
            if not isinstance(data, list):
                return []
            return [r for r in data if isinstance(r, dict)]
        except Exception as e:
            self.last_error = f"خواندن فایل محلی ناموفق بود: {e}"
            return []

    def _save_local(self, rec: Dict[str, Any]) -> None:
        """نوشتن اتمیک: اول tmp بعد جایگزینی — تا وسط redeploy فایل نیمه‌کاره نماند."""
        items = self._load_local()
        items.insert(0, rec)
        items = items[:MAX_LOCAL_RECORDS]
        tmp = LOCAL_JSON_PATH.with_suffix(".json.tmp")
        try:
            payload = json.dumps(items, ensure_ascii=False, indent=2)
            with _local_lock:
                tmp.write_text(payload, encoding="utf-8")
                os.replace(tmp, LOCAL_JSON_PATH)
        except Exception as e:
            self.last_error = f"نوشتن فایل محلی ناموفق بود: {e}"
            # آخرین پناه: نگه‌داشتن رکورد در session فعلی تا کاربر حداقل خودش ببیند
            try:
                st.session_state.setdefault(_UNSAVED_KEY, []).insert(0, rec)
            except Exception:
                pass

    # ---------------- ادغام و یکسان‌سازی شکل داده ----------------
    @staticmethod
    def _flatten(row: Dict[str, Any]) -> Dict[str, Any]:
        """رکورد ۷ ستونه را به dict تخت تبدیل می‌کند: payload + ستون‌های اصلی.

        خروجی یک superset از رکوردهای قدیمی است؛ پس کد نمایش فعلی
        (که مثلاً rec["text"] را می‌خواند) بدون تغییر کار می‌کند.
        """
        payload = row.get("payload")
        flat: Dict[str, Any] = dict(payload) if isinstance(payload, dict) else {}
        for k in ROW_KEYS:
            v = row.get(k)
            if v is not None:
                flat[k] = v
        return flat

    @staticmethod
    def _merge_unsaved(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """رکوردهایی که این session ذخیره شده ولی روی دیسک/کلود جا نشده‌اند را اضافه می‌کند."""
        try:
            unsaved = st.session_state.get(_UNSAVED_KEY) or []
        except Exception:
            unsaved = []
        if not unsaved:
            return rows
        have = {str(r.get("id")) for r in rows}
        extra = [r for r in unsaved if str(r.get("id")) not in have]
        return extra + rows

    # ---------------- API عمومی ----------------
    def load_all(self) -> List[Dict[str, Any]]:
        """همه تحلیل‌ها (تازه‌ترین اول) به شکل لیست dict تخت."""
        rows = self._fetch_remote()
        if rows is None:
            rows = self._load_local()
        rows = self._merge_unsaved(rows)
        return [self._flatten(r) for r in rows]

    def save(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """ذخیره یک تحلیل جدید؛ خروجی: رکورد نرمال‌شده تخت‌شده."""
        rec = _normalize_record(record)
        client = self._get_client()
        if client is not None:
            try:
                row = {k: rec[k] for k in ROW_KEYS}
                client.table(TABLE).insert(row).execute()
                self.last_error = None
                self._cache = None  # کش را باطل کن تا خواندن بعدی رکورد جدید را بیاورد
                return self._flatten(rec)
            except Exception as e:
                self.last_error = f"نوشتن در Supabase ناموفق بود، به فایل محلی برمی‌گردیم: {e}"
        self._save_local(rec)
        try:
            st.session_state.setdefault(_UNSAVED_KEY, []).insert(0, rec)
        except Exception:
            pass
        return self._flatten(rec)

    def healthcheck(self) -> Dict[str, Any]:
        """گزارش وضعیت بک‌اند — برای دکمه «تست اتصال» در اپ یا CI."""
        info: Dict[str, Any] = {
            "backend": "local-json",
            "ok": True,
            "count": None,
            "latency_ms": None,
            "error": self.client_err,
        }
        client = self._get_client()
        if client is not None:
            try:
                t0 = time.perf_counter()
                res = client.table(TABLE).select("id", count="exact").limit(1).execute()
                info.update(
                    backend="supabase",
                    count=res.count,
                    latency_ms=round((time.perf_counter() - t0) * 1000),
                    error=None,
                )
            except Exception as e:
                info.update(backend="supabase(خطا، fallback محلی)", error=str(e))
        else:
            info["count"] = len(self._load_local())
        return info


# ---------------------------------------------------------------- نمونه مشترک
@st.cache_resource(show_spinner=False)
def get_store() -> CommunityStore:
    """یک نمونه Store برای کل اپ (بین rerunها و sessionها حفظ می‌شود)."""
    return CommunityStore()


# ---------------------------------------------------------------- API سازگار با کد قدیمی
def load_community() -> List[Dict[str, Any]]:
    """جایگزین مستقیم تابع قدیمی در app_base.py — امضا و خروجی همان."""
    return get_store().load_all()


def save_community(record: Dict[str, Any]) -> Dict[str, Any]:
    """جایگزین مستقیم تابع قدیمی در app_base.py — همان dict قبلی را بدهید."""
    return get_store().save(record)


def render_backend_banner() -> None:
    """یک‌بار در هر session، وضعیت بک‌اند را در پایین سایدبار نشان می‌دهد.

    در main() بعد از ساخت عنوان سایدبار صدا بزنید:
        render_backend_banner()
    """
    try:
        if st.session_state.get(_BANNER_KEY):
            return
        st.session_state[_BANNER_KEY] = True
    except Exception:
        return
    store = get_store()
    if store.backend == "supabase":
        st.sidebar.caption("برد مشترک: Supabase (پایدار)")
    else:
        st.sidebar.caption(
            "برد مشترک: فایل محلی (موقتی) — "
            + (store.client_err or "کلیدهای Supabase تنظیم نشده‌اند")
        )
    if store.last_error:
        st.sidebar.caption(f"هشدار: {store.last_error}")
