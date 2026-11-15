# -*- coding: utf-8 -*-
"""گرِیدرِ پیامد — به هر پیش‌بینیِ ثبت‌شده، «چه شد بعداً» می‌چسباند
==============================================================================
هم برای کرونوس هم برای نبیه — یک لوله‌ی مشترک. دروازه‌ی فعلی فقط «هم‌جهتی
با چارت» را می‌سنجد؛ آزمونِ واقعیِ هر موتور این است: بعد از افقِ N کندل،
قیمت به کدام سمت رفت؟ این ماژول برای هر سطرِ جهت‌دارِ دفتر که هنوز پیامد
ندارد، کندلِ بعد از افق را از همان صرافی/تایم‌فریم می‌گیرد و ثبت می‌کند:

  outcome = +۱ اگر قیمت بالاتر رفت · -۱ اگر پایین‌تر · ۰ داخلِ باندِ مرده
  hit     = (side == outcome)  — برای outcome==0 «بی‌نتیجه» است نه خورده

نتایج append-only در core/data/paper_outcomes.jsonl با کلیدِ یکتا →
idempotent: هر پیش‌بینی فقط یک‌بار نمره می‌گیرد و تاریخِ دفتر دست نمی‌خورد.
شبکه از طریقِ fetcher تزریقی می‌آید تا آزمون‌ها تماماً قطعی باشند.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

# تهران — دفترِ پروژه به وقتِ دیوارِ تهران نوشته می‌شود (naive)
_TEHRAN = timezone(timedelta(hours=3, minutes=30))

_INTERVAL_MS = {
    "5min": 5 * 60_000, "15min": 15 * 60_000, "30min": 30 * 60_000,
    "1hour": 60 * 60_000, "4hour": 4 * 60 * 60_000, "1day": 24 * 60 * 60_000,
}
_SIDE_FIELD = {"kronos": "kronos_side", "nabigha": "nabigha_side"}


def outcomes_path() -> str:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, "core", "data", "paper_outcomes.jsonl")


def _key(engine: str, e: dict) -> str:
    return f"{engine}|{e.get('exchange')}|{e.get('symbol')}|{e.get('interval')}|{e.get('ts')}"


def _load_jsonl(p: str) -> list[dict]:
    rows: list[dict] = []
    try:
        with open(p, encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if isinstance(r, dict):  # null/[1,2] و هر غیرِ dict = خطِ خراب
                    rows.append(r)
    except FileNotFoundError:
        return []
    return rows


def _ts_ms(e: dict):
    """tsِ دفتر → میلی‌ثانیه‌ی epoch (naive = دیوارِ تهران) — None اگر نشد."""
    raw = str(e.get("ts") or "")
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        try:
            dt = datetime.strptime(raw, "%Y-%m-%d %H:%M")
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_TEHRAN)
    return int(dt.timestamp() * 1000)


def _existing_keys(p: str) -> set[str]:
    return {r.get("key") for r in _load_jsonl(p) if r.get("key")}


def pending_rows(engine: str, ledger_path: str | None = None,
                 outcomes_file: str | None = None) -> list[dict]:
    """سطرهای جهت‌داری که هنوز پیامد ندارند — برای هر دو موتور کار می‌کند."""
    if engine not in _SIDE_FIELD:
        return []
    field = _SIDE_FIELD[engine]
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    lp = ledger_path or (f"{root}/core/data/kronos_log.jsonl"
                         if engine == "kronos" else
                         f"{root}/core/data/nabigha_log.jsonl")
    op = outcomes_file or outcomes_path()
    done = _existing_keys(op)
    out = []
    for e in _load_jsonl(lp):
        if e.get("backend") != engine:
            continue
        if e.get(field) not in (1, -1):
            continue  # بی‌ادعا پیامد ندارد
        if not e.get("symbol") or not e.get("interval"):
            continue
        if _key(engine, e) in done:
            continue
        out.append(e)
    return out


def _pick_forward(df, horizon_end_ms: int):
    """اولین کندلی که باز شدنش بعد از افق است → (close، زمانِ باز شدن)."""
    if df is None or len(df) == 0 or "close" not in df.columns:
        return None
    times = df["time"].astype("int64") if "time" in df.columns else None
    if times is None:
        return None
    for i, t in enumerate(times):
        if int(t) >= horizon_end_ms:
            return float(df["close"].iloc[i]), int(t)
    return None


def grade_pending(engine: str, ledger_path: str | None = None,
                  outcomes_file: str | None = None, fetcher=None,
                  horizon: int = 3, deadband: float = 0.0005,
                  max_rows: int = 200) -> dict:
    """نمره‌دادنِ پیامدهای در انتظار — append-only و idempotent.

    fetcher(exchange, symbol, interval, limit) → DataFrame کندل‌ها یا None.
    پیش‌فرضِ زنده: app_base.fetch_candles (فقط در CLI بگذار — آزمون‌ها تزریقی‌اند).
    """
    op = outcomes_file or outcomes_path()
    try:
        if fetcher is None:
            from app_base import fetch_candles as fetcher  # noqa: E402
        field = _SIDE_FIELD.get(engine)
        if field is None:
            return {"ok": False, "graded": 0, "error": f"موتورِ ناشناس: {engine}"}
        rows = pending_rows(engine, ledger_path, op)[:max(1, max_rows)]
        done = _existing_keys(op)
        graded = skipped = 0
        os.makedirs(os.path.dirname(op), exist_ok=True)
        with open(op, "a", encoding="utf-8") as f:
            for e in rows:
                k = _key(engine, e)
                if k in done:
                    continue
                try:
                    t_ms = _ts_ms(e)
                    ims = _INTERVAL_MS.get(str(e.get("interval")), 60 * 60_000)
                    if t_ms is None:
                        skipped += 1
                        continue
                    limit = horizon + 30  # حاشیه برای کندل‌های بعد از افق
                    df = fetcher(e.get("exchange"), e.get("symbol"),
                                 e.get("interval"), limit)
                    pick = _pick_forward(df, t_ms + horizon * ims)
                    if pick is None:
                        skipped += 1
                        continue  # تاریخچه هنوز به افق نرسیده — رانِ بعدی
                    price_after, t_after = pick
                    price_at = e.get("price")
                    if not isinstance(price_at, (int, float)) or price_at <= 0:
                        skipped += 1
                        continue
                    move = price_after / float(price_at) - 1.0
                    outcome = 1 if move > deadband else (-1 if move < -deadband else 0)
                    side = int(e[field])
                    rec = {"key": k, "engine": engine,
                           "ts": e.get("ts"), "symbol": e.get("symbol"),
                           "interval": e.get("interval"), "exchange": e.get("exchange"),
                           "side": side, "price_at": float(price_at),
                           "price_after": price_after, "t_after": t_after,
                           "horizon": horizon, "move_pct": round(move * 100.0, 4),
                           "outcome": outcome,
                           "hit": (side == outcome) if outcome != 0 else None,
                           "graded_at": datetime.now(_TEHRAN).strftime("%Y-%m-%d %H:%M")}
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    done.add(k)
                    graded += 1
                except Exception:  # noqa: BLE001 — یک سطر خراب، بقیه را نمی‌بُرد
                    skipped += 1
        return {"ok": True, "engine": engine, "graded": graded,
                "skipped": skipped, "outcomes_path": op}
    except Exception as exc:  # noqa: BLE001 — گرِیدر هرگز جاب را قرمز نمی‌کند
        return {"ok": False, "engine": engine, "graded": 0,
                "error": f"{type(exc).__name__}: {exc}"}


def outcomes_stats(engine: str | None = None, path: str | None = None) -> dict:
    """آمارِ پیامدها — hit-rateِ واقعی؛ outcome==0 به نرخ نمی‌خورد (بی‌نتیجه)."""
    try:
        rows = _load_jsonl(path or outcomes_path())
        if engine:
            rows = [r for r in rows if r.get("engine") == engine]
        decided = [r for r in rows if r.get("outcome") in (1, -1)]
        hits = sum(1 for r in decided if r.get("hit") is True)
        rate = round(hits / len(decided) * 100.0, 1) if decided else None

        def _by(key: str) -> dict:
            g: dict[str, list] = {}
            for r in decided:
                g.setdefault(str(r.get(key) or "?"), []).append(r)
            out = {}
            for k, v in g.items():
                h = sum(1 for r in v if r.get("hit") is True)
                out[k] = {"n": len(v), "hits": h,
                          "rate": round(h / len(v) * 100.0, 1)}
            return dict(sorted(out.items()))

        return {"ok": True, "engine": engine, "n_graded": len(rows),
                "n_decided": len(decided), "hits": hits, "rate": rate,
                "by_interval": _by("interval"), "by_symbol": _by("symbol")}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
