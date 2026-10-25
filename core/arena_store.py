"""core/arena_store.py — ذخیره‌سازی معاملات «میدان ایجنت‌ها»
=============================================================
اولویت: جدول `arena_trades` در Supabase (اگر SUPABASE_URL/KEY ست باشد).
fallback: فایل `arena_trades.json` کنار اپ (موقتی — با redeploy پاک می‌شود).

شکل جدول: (id text pk, agent text, symbol text, status text, data jsonb,
created_at, updated_at) — همه‌ی جزئیات معامله داخل data است؛ RLS برای anon
اجازه‌ی select/insert/update می‌دهد (بدون delete).
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

TABLE = "arena_trades"
LOCAL_FILE = "arena_trades.json"
_LOCK = threading.RLock()


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _secrets_get(key: str) -> Optional[str]:
    try:
        import streamlit as st
        try:
            if key in st.secrets:  # type: ignore[operator]
                return str(st.secrets[key])
        except Exception:  # noqa: BLE001
            pass
    except Exception:  # noqa: BLE001
        pass
    return os.environ.get(key)


def _json_safe(value: Any) -> Any:
    """تبدیل numpy/NaN/Inf/datetime به نوع‌های JSON."""
    import math

    import numpy as _np
    import pandas as _pd

    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (_np.integer,)):
        return int(value)
    if isinstance(value, (_np.floating,)):
        f = float(value)
        return f if math.isfinite(f) else None
    if isinstance(value, (_np.bool_,)):
        return bool(value)
    if isinstance(value, (_pd.Timestamp, datetime)):
        try:
            return value.isoformat()
        except Exception:  # noqa: BLE001
            return str(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    return str(value)


class ArenaStore:
    def __init__(self) -> None:
        self._client = None
        self._client_tried = False

    # ----- client ---------------------------------------------------------------
    def _get_client(self):
        if not self._client_tried:
            self._client_tried = True
            url = _secrets_get("SUPABASE_URL")
            key = _secrets_get("SUPABASE_KEY") or _secrets_get("SUPABASE_ANON_KEY")
            if url and key:
                try:
                    from supabase import create_client  # type: ignore
                    self._client = create_client(url, key)
                except Exception:  # noqa: BLE001
                    self._client = None
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
                return json.load(f)
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
    def load_all(self) -> List[Dict[str, Any]]:
        client = self._get_client()
        if client is not None:
            try:
                res = (client.table(TABLE)
                       .select("id, agent, symbol, status, data, created_at, updated_at")
                       .order("created_at", desc=True).limit(2000).execute())
                out: List[Dict[str, Any]] = []
                for row in (res.data or []):
                    d = dict(row.get("data") or {})
                    d.setdefault("id", row.get("id"))
                    d["id"] = row.get("id") or d.get("id")
                    if row.get("status"):
                        d["status"] = row["status"]
                    out.append(d)
                return out
            except Exception:  # noqa: BLE001
                pass
        return self._load_local()

    def insert(self, rec: Dict[str, Any]) -> Dict[str, Any]:
        rec = {**rec,
               "id": rec.get("id") or __import__("uuid").uuid4().hex,
               "created_at": rec.get("created_at") or _utcnow_iso(),
               "updated_at": _utcnow_iso()}
        client = self._get_client()
        if client is not None:
            try:
                row = {"id": str(rec["id"]), "agent": str(rec.get("agent", "")),
                       "symbol": str(rec.get("symbol", "")), "status": str(rec.get("status", "open")),
                       "data": _json_safe(rec), "created_at": rec["created_at"], "updated_at": rec["updated_at"]}
                client.table(TABLE).insert(row).execute()
                return rec
            except Exception:  # noqa: BLE001
                pass
        with _LOCK:
            rows = self._load_local()
            rows.insert(0, _json_safe(rec))
            self._write_local(rows[:2000])
        return rec

    def update(self, rec_id: str, patch: Dict[str, Any]) -> bool:
        patch = dict(patch)
        patch["updated_at"] = _utcnow_iso()
        client = self._get_client()
        if client is not None:
            try:
                sel = client.table(TABLE).select("data").eq("id", rec_id).limit(1).execute()
                data = dict(((sel.data or [{}])[0]).get("data") or {})
                data.update(_json_safe(patch))
                client.table(TABLE).update({
                    "data": data, "status": str(data.get("status", "open")), "updated_at": patch["updated_at"],
                }).eq("id", rec_id).execute()
                return True
            except Exception:  # noqa: BLE001
                pass
        with _LOCK:
            rows = self._load_local()
            hit = False
            for i, r in enumerate(rows):
                if r.get("id") == rec_id:
                    rows[i] = {**r, **_json_safe(patch)}
                    hit = True
                    break
            if hit:
                self._write_local(rows)
            return hit

    def healthcheck(self) -> Dict[str, Any]:
        info: Dict[str, Any] = {"backend": self.backend, "table": TABLE}
        client = self._get_client()
        if client is not None:
            try:
                res = client.table(TABLE).select("id", count="exact").limit(1).execute()
                info["ok"] = True
                info["rows"] = getattr(res, "count", None)
            except Exception as e:  # noqa: BLE001
                info.update(ok=False, backend="supabase(خطا، fallback محلی)", error=str(e))
        else:
            info.update(ok=os.path.exists(LOCAL_FILE), rows=len(self._load_local()))
        return info


_STORE: Optional[ArenaStore] = None


def get_store() -> ArenaStore:
    global _STORE
    if _STORE is None:
        _STORE = ArenaStore()
    return _STORE


# توابع کوتاه سازگار
def load_trades() -> List[Dict[str, Any]]:
    return get_store().load_all()


def insert_trade(rec: Dict[str, Any]) -> Dict[str, Any]:
    return get_store().insert(rec)


def update_trade(rec_id: str, patch: Dict[str, Any]) -> bool:
    return get_store().update(rec_id, patch)
