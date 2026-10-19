"""
core/gaps.py — موتور FVG / BVG برای NorthmanQuant
====================================================
FVG  = Fair Value Gap (گپ ارزش منصفانه)
       ناترازی سه‌کندلی: وقتی «سایه‌ی» کندل ۱ و کندل ۳ همپوشانی ندارند.
       صعودی: low[t] > high[t-2]   ·   نزولی: high[t] < low[t-2]
BVG  = Body-Volume Gap (گپ بدنه با تأیید حجم)
       ناترازی سه‌کندلی روی «بدنه‌ها» (نه سایه‌ها) که کندل وسط (کندل جابه‌جایی)
       حجمی بالاتر از میانگین ۲۰ کندل دارد. در کریپتو که بازار ۲۴/۷ است و گپِ
       بین دو کندل متوالی تقریباً وجود ندارد، این تعریف جای «Volume Imbalance» را می‌گیرد.
IFVG = اگر قیمت با «کلوز» از آن‌سوی یک FVG عبور کند، زون معکوس می‌شود (حمایت ↔ مقاومت).

همه‌چیز «علّی» (causal) است: امتیاز کندل t فقط از داده‌ی ≤ t استفاده می‌کند،
بنابراین می‌توان با خیال راحت روی آن بک‌تست گرفت.

خروجی اصلی: gap_analysis(df) -> dict
    fvg_score / bvg_score : آرایه‌ی امتیاز هر کندل در بازه‌ی [-1, +1]
    fvg_zones / bvg_zones : فهرست زون‌ها (فعال و پرشده) با جزئیات
    fvg_info  / bvg_info  : خلاصه‌ی کندل آخر (برای جدول/Neural Shell)
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

__all__ = [
    "gap_analysis", "gap_scores", "active_zones", "short_label", "table_rows",
    "plotly_shapes", "zones_frame", "GAP_HELP",
]

GAP_HELP = {
    "FVG": "FVG (Fair Value Gap): ناترازی سه‌کندلی؛ سایه‌ی کندل ۱ و ۳ همپوشانی ندارند. "
           "زون صعودی زیر قیمت = حمایت/ناحیه‌ی ورود لانگ، زون نزولی بالای قیمت = مقاومت/ناحیه‌ی ورود شورت. "
           "عبور با کلوز از زون، آن را به IFVG (معکوس) تبدیل می‌کند.",
    "BVG": "BVG (Body-Volume Gap): ناترازی سه‌کندلی روی بدنه‌ی کندل‌ها که کندل وسط حجمی ≥۱.۲ برابر "
           "میانگین ۲۰ کندل دارد؛ یعنی جابه‌جایی قیمت با پولِ واقعی انجام شده است.",
}


# ----------------------------------------------------------------------------- helpers
def _col(d: pd.DataFrame, name: str, default: np.ndarray | None = None) -> np.ndarray:
    if name in d.columns:
        return pd.to_numeric(d[name], errors="coerce").to_numpy(dtype=float)
    if default is None:
        raise KeyError(name)
    return default


def _atr_fallback(h: np.ndarray, l: np.ndarray, c: np.ndarray, n: int = 14) -> np.ndarray:
    prev_c = np.roll(c, 1)
    prev_c[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))
    return pd.Series(tr).ewm(alpha=1 / n, adjust=False).mean().to_numpy()


def _clamp(x: float) -> float:
    if not np.isfinite(x):
        return 0.0
    return float(max(-1.0, min(1.0, x)))


# ----------------------------------------------------------------------------- engine
def gap_analysis(
    d: pd.DataFrame,
    min_fvg_atr: float = 0.10,
    min_bvg_atr: float = 0.10,
    bvg_vol_ratio: float = 1.20,
    max_age: int = 400,
    fresh_window: int = 12,
) -> dict:
    """تحلیل کامل FVG و BVG روی یک DataFrame کندل (ستون‌های open/high/low/close/volume)."""
    n = len(d)
    out = {
        "fvg_score": np.zeros(n), "bvg_score": np.zeros(n),
        "fvg_zones": [], "bvg_zones": [],
        "fvg_info": _empty_info(), "bvg_info": _empty_info(),
    }
    if n < 5:
        return out

    o = _col(d, "open")
    h = _col(d, "high")
    l = _col(d, "low")
    c = _col(d, "close")
    v = _col(d, "volume", np.ones(n))
    v = np.where(np.isfinite(v), v, 0.0)

    atr = _col(d, "atr", _atr_fallback(h, l, c))
    atr = np.where(np.isfinite(atr) & (atr > 0), atr, np.nan)
    if np.all(np.isnan(atr)):
        atr = np.abs(c) * 0.01
    atr = pd.Series(atr).ffill().bfill().to_numpy()
    atr = np.where(atr > 0, atr, np.abs(c) * 0.01 + 1e-12)

    vol_sma = pd.Series(v).rolling(20, min_periods=5).mean().to_numpy()
    body_top = np.maximum(o, c)
    body_bot = np.minimum(o, c)

    times = None
    if "dt" in d.columns:
        times = list(d["dt"])
    elif "time" in d.columns:
        times = list(d["time"])

    fvg_active: list[dict] = []
    bvg_active: list[dict] = []
    fvg_all: list[dict] = []
    bvg_all: list[dict] = []
    fvg_fresh: list[tuple[int, float]] = []   # (index, signed strength)
    bvg_fresh: list[tuple[int, float]] = []

    for t in range(n):
        a = atr[t]
        price = c[t]

        # ---- 1) mitigation / inversion of existing zones using candle t --------
        _update_zones(fvg_active, t, h[t], l[t], c[t], allow_inversion=True)
        _update_zones(bvg_active, t, h[t], l[t], c[t], allow_inversion=False)
        fvg_active = [z for z in fvg_active if not z["mitigated"] and t - z["i"] <= max_age]
        bvg_active = [z for z in bvg_active if not z["mitigated"] and t - z["i"] <= max_age]

        if t >= 2:
            vr_mid = float(v[t - 1] / vol_sma[t - 1]) if np.isfinite(vol_sma[t - 1]) and vol_sma[t - 1] > 0 else 1.0
            rng_mid = h[t - 1] - l[t - 1]
            body_mid_ratio = float((body_top[t - 1] - body_bot[t - 1]) / rng_mid) if rng_mid > 0 else 0.0

            # ---- 2) FVG (wick based) -----------------------------------------
            if l[t] > h[t - 2] and (l[t] - h[t - 2]) >= min_fvg_atr * a:
                z = _mk_zone("FVG", +1, bot=h[t - 2], top=l[t], i=t, a=a, vr=vr_mid, body=body_mid_ratio, times=times)
                fvg_active.append(z); fvg_all.append(z); fvg_fresh.append((t, +z["strength"]))
            elif h[t] < l[t - 2] and (l[t - 2] - h[t]) >= min_fvg_atr * a:
                z = _mk_zone("FVG", -1, bot=h[t], top=l[t - 2], i=t, a=a, vr=vr_mid, body=body_mid_ratio, times=times)
                fvg_active.append(z); fvg_all.append(z); fvg_fresh.append((t, -z["strength"]))

            # ---- 3) BVG (body based + volume confirmation) -------------------
            if vr_mid >= bvg_vol_ratio and body_mid_ratio >= 0.55:
                if body_bot[t] > body_top[t - 2] and (body_bot[t] - body_top[t - 2]) >= min_bvg_atr * a and c[t - 1] > o[t - 1]:
                    z = _mk_zone("BVG", +1, bot=body_top[t - 2], top=body_bot[t], i=t, a=a, vr=vr_mid, body=body_mid_ratio, times=times)
                    bvg_active.append(z); bvg_all.append(z); bvg_fresh.append((t, +z["strength"]))
                elif body_top[t] < body_bot[t - 2] and (body_bot[t - 2] - body_top[t]) >= min_bvg_atr * a and c[t - 1] < o[t - 1]:
                    z = _mk_zone("BVG", -1, bot=body_top[t], top=body_bot[t - 2], i=t, a=a, vr=vr_mid, body=body_mid_ratio, times=times)
                    bvg_active.append(z); bvg_all.append(z); bvg_fresh.append((t, -z["strength"]))

        # ---- 4) per-bar scores -------------------------------------------------
        fvg_fresh = [(i, s) for i, s in fvg_fresh if t - i <= fresh_window]
        bvg_fresh = [(i, s) for i, s in bvg_fresh if t - i <= fresh_window]
        out["fvg_score"][t] = _score(fvg_active, fvg_fresh, t, price, a)
        out["bvg_score"][t] = _score(bvg_active, bvg_fresh, t, price, a)

    last_price = float(c[-1])
    out["fvg_zones"] = fvg_all
    out["bvg_zones"] = bvg_all
    out["fvg_info"] = _summarize(fvg_all, last_price, float(atr[-1]), n - 1, float(out["fvg_score"][-1]))
    out["bvg_info"] = _summarize(bvg_all, last_price, float(atr[-1]), n - 1, float(out["bvg_score"][-1]))
    return out


def _mk_zone(kind, typ, bot, top, i, a, vr, body, times) -> dict:
    size = float(top - bot)
    strength = float(min(1.5, size / a)) * (0.7 + 0.3 * min(1.0, body))
    if kind == "BVG":
        strength *= min(1.6, 0.6 + vr / 2.0)  # volume-weighted
    strength = float(min(1.5, strength))
    return {
        "kind": kind, "type": int(typ), "bot": float(bot), "top": float(top), "mid": float((top + bot) / 2),
        "i": int(i), "time": (times[i] if times is not None else i),
        "size": size, "size_atr": float(size / a), "vol_ratio": float(vr), "body_ratio": float(body),
        "strength": strength, "touched": False, "touched_i": None,
        "mitigated": False, "mit_i": None, "mit_time": None, "inverted": False,
    }


def _update_zones(zones: list[dict], t: int, hi: float, lo: float, cl: float, allow_inversion: bool) -> None:
    for z in zones:
        if z["mitigated"] or z["i"] == t:
            continue
        if z["type"] == +1:
            if lo <= z["top"] and not z["touched"]:
                z["touched"], z["touched_i"] = True, t
            if lo <= z["bot"]:
                if allow_inversion and cl < z["bot"] and not z["inverted"]:
                    # قیمت با کلوز از زیر زون صعودی عبور کرد → IFVG نزولی (مقاومت)
                    z["inverted"], z["type"], z["touched"] = True, -1, False
                    z["inv_i"] = t
                else:
                    z["mitigated"], z["mit_i"] = True, t
        else:
            if hi >= z["bot"] and not z["touched"]:
                z["touched"], z["touched_i"] = True, t
            if hi >= z["top"]:
                if allow_inversion and cl > z["top"] and not z["inverted"]:
                    z["inverted"], z["type"], z["touched"] = True, +1, False
                    z["inv_i"] = t
                else:
                    z["mitigated"], z["mit_i"] = True, t


def _score(active: list[dict], fresh: list[tuple[int, float]], t: int, price: float, a: float) -> float:
    # (الف) جابه‌جایی تازه: گپ‌های تازه در جهت ایمپالس
    disp = 0.0
    for i, s in fresh:
        disp += s * math.exp(-(t - i) / 6.0)
    disp = _clamp(disp)

    # (ب) موقعیت قیمت نسبت به نزدیک‌ترین زون‌های فعال
    inside_bull = 0.0
    inside_bear = 0.0
    support = 0.0
    resist = 0.0
    for z in active:
        w = 0.6 + 0.4 * min(1.0, z["strength"])
        if z["bot"] <= price <= z["top"]:
            if z["type"] > 0:
                inside_bull = max(inside_bull, w)
            else:
                inside_bear = max(inside_bear, w)
        elif z["type"] > 0 and z["top"] < price:
            dist = (price - z["top"]) / a
            support = max(support, w * math.exp(-dist / 1.5))
        elif z["type"] < 0 and z["bot"] > price:
            dist = (z["bot"] - price) / a
            resist = max(resist, w * math.exp(-dist / 1.5))
    if inside_bull or inside_bear:
        zone = inside_bull - inside_bear          # داخل زون: حمایت (+) یا مقاومت (−)
    else:
        zone = support - resist                   # نزدیکی به زون زیر/بالای قیمت
    return _clamp(0.55 * disp + 0.45 * zone)


def _empty_info() -> dict:
    return {"active_bull": 0, "active_bear": 0, "inside": None, "nearest_support": None,
            "nearest_resist": None, "last_gap": None, "score": 0.0, "total": 0, "filled": 0, "inverted": 0}


def _summarize(zones: list[dict], price: float, a: float, last_i: int, score: float) -> dict:
    info = _empty_info()
    info["score"] = score
    info["total"] = len(zones)
    info["filled"] = sum(1 for z in zones if z["mitigated"])
    info["inverted"] = sum(1 for z in zones if z["inverted"])
    act = [z for z in zones if not z["mitigated"]]
    info["active_bull"] = sum(1 for z in act if z["type"] > 0)
    info["active_bear"] = sum(1 for z in act if z["type"] < 0)
    inside = [z for z in act if z["bot"] <= price <= z["top"]]
    if inside:
        info["inside"] = max(inside, key=lambda z: z["strength"])
    sup = [z for z in act if z["type"] > 0 and z["top"] < price]
    res = [z for z in act if z["type"] < 0 and z["bot"] > price]
    if sup:
        z = max(sup, key=lambda z: z["top"])
        info["nearest_support"] = {**z, "dist_atr": (price - z["top"]) / a}
    if res:
        z = min(res, key=lambda z: z["bot"])
        info["nearest_resist"] = {**z, "dist_atr": (z["bot"] - price) / a}
    if zones:
        z = zones[-1]
        info["last_gap"] = {**z, "age": last_i - z["i"]}
    return info


# ----------------------------------------------------------------------------- convenience
def gap_scores(d: pd.DataFrame) -> tuple[pd.Series, pd.Series, dict]:
    res = gap_analysis(d)
    idx = d.index
    return (pd.Series(res["fvg_score"], index=idx), pd.Series(res["bvg_score"], index=idx), res)


def active_zones(res: dict, kind: str = "FVG", price: float | None = None, limit: int = 8) -> list[dict]:
    zones = [z for z in res.get(f"{kind.lower()}_zones", []) if not z["mitigated"]]
    if price is not None:
        zones.sort(key=lambda z: abs(z["mid"] - price))
    return zones[:limit]


def short_label(info: dict, kind: str = "FVG") -> str:
    """متن کوتاه برای ستون «مقدار» (Neural Shell جا ندارد)."""
    if info.get("inside") is not None:
        z = info["inside"]
        return f"داخل {kind} {'صعودی' if z['type'] > 0 else 'نزولی'}{' (IFVG)' if z.get('inverted') else ''}"
    parts = [f"{info.get('active_bull', 0)}🟢 {info.get('active_bear', 0)}🔴"]
    s, r = info.get("nearest_support"), info.get("nearest_resist")
    if s is not None and (r is None or s["dist_atr"] <= r["dist_atr"]):
        parts.append(f"حمایت {s['dist_atr']:.1f}ATR↓")
    elif r is not None:
        parts.append(f"مقاومت {r['dist_atr']:.1f}ATR↑")
    else:
        parts.append("زون فعالی نزدیک نیست")
    return " · ".join(parts)


def _dir_label(v: float) -> str:
    return "خرید 🟢" if v > 0.15 else "فروش 🔴" if v < -0.15 else "خنثی ⚪"


def table_rows(res: dict) -> list[dict]:
    """ردیف‌های آماده برای جدول «اجزای همگرایی» (همان ستون‌های app_base)."""
    f, b = res["fvg_info"], res["bvg_info"]
    return [
        {"اندیکاتور": "FVG گپ ارزش", "مقدار": short_label(f, "FVG"), "جهت": _dir_label(f["score"]),
         "امتیاز": round(float(f["score"]), 2)},
        {"اندیکاتور": "BVG گپ حجمی", "مقدار": short_label(b, "BVG"), "جهت": _dir_label(b["score"]),
         "امتیاز": round(float(b["score"]), 2)},
    ]


def zones_frame(res: dict, price: float, dec: int = 4, limit: int = 14) -> pd.DataFrame:
    """جدول خوانا از زون‌های فعال FVG/BVG (نزدیک‌ترین‌ها اول)."""
    rows = []
    for kind in ("FVG", "BVG"):
        for z in active_zones(res, kind, price, limit):
            role = "حمایت" if z["type"] > 0 else "مقاومت"
            where = "داخل زون" if z["bot"] <= price <= z["top"] else ("زیر قیمت" if z["top"] < price else "بالای قیمت")
            rows.append({
                "نوع": kind + (" (IFVG)" if z.get("inverted") else ""),
                "جهت": ("صعودی 🟢" if z["type"] > 0 else "نزولی 🔴"),
                "نقش": role,
                "پایین زون": f"{z['bot']:,.{dec}f}",
                "بالای زون": f"{z['top']:,.{dec}f}",
                "اندازه/ATR": round(z["size_atr"], 2),
                "حجم کندل وسط": f"{z['vol_ratio']:.2f}×",
                "موقعیت قیمت": where,
                "لمس شده": "بله" if z["touched"] else "خیر",
                "زمان شکل‌گیری": str(z["time"])[:16],
            })
    return pd.DataFrame(rows)


def plotly_shapes(res: dict, x_end, price: float, max_fvg: int = 8, max_bvg: int = 6) -> tuple[list[dict], list[dict]]:
    """شکل‌ها و برچسب‌های Plotly برای زون‌های فعال (بدون نیاز به import plotly)."""
    shapes, notes = [], []
    spec = [
        ("FVG", max_fvg, "rgba(34,197,94,0.16)", "rgba(239,68,68,0.16)", "#22c55e", "#ef4444", "solid"),
        ("BVG", max_bvg, "rgba(59,130,246,0.14)", "rgba(168,85,247,0.14)", "#3b82f6", "#a855f7", "dot"),
    ]
    for kind, lim, fill_up, fill_dn, col_up, col_dn, dash in spec:
        for z in active_zones(res, kind, price, lim):
            up = z["type"] > 0
            col = col_up if up else col_dn
            shapes.append(dict(
                type="rect", xref="x", yref="y", x0=z["time"], x1=x_end, y0=z["bot"], y1=z["top"],
                fillcolor=fill_up if up else fill_dn, line=dict(color=col, width=1, dash=dash), layer="below",
            ))
            notes.append(dict(
                x=z["time"], y=z["top"] if up else z["bot"], xref="x", yref="y",
                text=f"{kind}{' (IFVG)' if z.get('inverted') else ''} {'▲' if up else '▼'}",
                showarrow=False, xanchor="left", yanchor="bottom" if up else "top",
                font=dict(size=9, color=col),
            ))
    return shapes, notes
