# -*- coding: utf-8 -*-
"""core/kronos_witness.py — شاهدِ ششم: 🔮 کرونوس (فازِ یکِ نقشه‌راه — حالتِ سایه)
================================================================================
بر پایه‌ی گزارشِ تحقیقیِ کرونوس (جدول ۴)، این ماژول «فازِ یک — شاهدِ سایه» را
می‌سازد: کرونوس به‌عنوان «شاهدِ احتمالاتیِ مکمل» وارد جلسه‌ی اتاقِ تیم می‌شود،
نه موتورِ جایگزین — موتورِ QC-دارِ اپ تصمیم‌گیرِ اصلی می‌ماند.

قواعدِ طراحی (از خودِ گزارش، فصل‌های ۷ و ۸ و ۹):
  • حالتِ سایه (shadow): هیچ چیزِ این شاهد روی حکمِ نهاییِ تیم اثر ندارد؛
    شکاکِ موجود ادعای او را فقط «هشدار/تاییدِ ثبت‌شده» بازرسی می‌کند — اعتراضِ
    سختِ کرونوس در فازِ یک وجود ندارد.
  • خروجی احتمالاتی است، نه قطعی: به‌جای «قیمتِ نهاییِ واحد»، آماره‌ی تجمیعیِ
    مسیرها می‌دهیم — درصدِ هم‌جهتیِ مسیرها + باندِ چارکیِ قیمت در افق.
  • تکرارپذیری: نسخه‌ی مدل، seed و تنظیماتِ نمونه‌گیری ثبت می‌شود و در
    «مدرکِ» هر ادعا می‌آید.
  • fail-soft: مدلِ واقعی نصب نباشد یا شبکه/داده نباشد، جلسه بدونِ شاهدِ واقعی
    ادامه می‌یابد؛ هیچ‌وقت exception بالا نمی‌دهد.

دو پشتیبان (backend):
  • «offline» — شبیه‌سازِ مونت‌کارلوی GBM روی خودِ کندل‌ها؛ فقط برای آزمایشِ
    لوله‌کشی و تست‌های قطعی. صادقانه برچسب می‌خورد («شبیه‌ساز») و هیچ‌وقت
    حکمِ واقعیِ کرونوس نیست. پیش‌فرض است — بارگیریِ صفحه هرگز مدل دانلود نمی‌کند.
  • «kronos» — مدلِ واقعی از مخزنِ رسمی (github.com/shiyu-coder/Kronos،
    مدل‌ها روی HF با پیشوندِ NeoQuasar/). مخزنِ رسمی پکیجِ pip نیست، پس فقط با
    انتخابِ صریحِ اپراتور فعال می‌شود:
        KRONOS_BACKEND=kronos
        KRONOS_REPO=/مسیرِ/کلونِ/Kronos      (شامل پوشه‌ی model/)
    مدلِ پیش‌فرض: NeoQuasar/Kronos-mini (سبک و CPU-پسند؛ توکنایزرِ 2k).

دروازه‌ی خروجِ فازِ یک (جدول ۴ گزارش): هم‌جهتیِ >۵۵٪ روی ۲۰۰ جلسه‌ی
paper-trade + سوییتِ آزمون‌ها سبز. جلسات در core/data/kronos_log.jsonl
(append-only) ثبت می‌شوند و آمارِ دروازه با gate_stats() می‌آید — مقایسه‌ی
جهتِ اکثریتِ مسیرها با جهتِ سیگنالِ چارت، فقط برای جلساتی که سیگنالِ فعال
داشتند؛ و دروازه‌ی رسمی فقط با جلساتِ مدلِ واقعی جمع می‌خورد، نه شبیه‌ساز.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

sys_root = __file__.rsplit("/", 2)[0]
if sys_root not in sys.path:
    sys.path.insert(0, sys_root)

# --------------------------------------------------------------- ثابت‌ها
BACKENDS = ("offline", "kronos")
MODEL_PAIR = {  # مدلِ HF → توکنایزرِ جفتِ رسمی‌اش (از جدولِ ۲ گزارش)
    "NeoQuasar/Kronos-mini": "NeoQuasar/Kronos-Tokenizer-2k",
    "NeoQuasar/Kronos-small": "NeoQuasar/Kronos-Tokenizer-base",
    "NeoQuasar/Kronos-base": "NeoQuasar/Kronos-Tokenizer-base",
}
CTX_OF = {"NeoQuasar/Kronos-mini": 2048, "NeoQuasar/Kronos-small": 512,
          "NeoQuasar/Kronos-base": 512}
TEMPERATURE = 1.0        # T — ثبت‌شده برای تکرارپذیری
TOP_P = 0.9              # nucleus sampling — ثبت‌شده برای تکرارپذیری
DEFAULT_SEED = 42
DEFAULT_PATHS = 32       # تعدادِ مسیرهای نمونه‌گیری‌شده
DEFAULT_HORIZON = 24     # افقِ پیش‌بینی: چند کندلِ جلو
MAJORITY = 0.55          # اکثریتِ جهت‌دارِ مسیرها = آستانه‌ی ۵۵٪ دروازه
EPS = 0.001              # حرکتِ کمتر از ۰٫۱٪ در افق = «بی‌جهت» حساب می‌شود
MIN_CTX = 60             # کمتر از این کندل → صادقانه «نمی‌توانم» — حدس ممنوع
STUB_CTX = 400           # شبیه‌سازِ آفلاین حداکثر از این کندل‌های اخیر آمار می‌گیرد
INTERVAL_TO_FREQ = {"1hour": "1h", "2hour": "2h", "4hour": "4h", "1day": "1D"}
_LOG_DEFAULT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "data", "kronos_log.jsonl")
_FREQ_FALLBACK = "1h"


def log_path() -> str:
    """مسیرِ دفترِ ثبتِ جلسات — با env قابلِ تغییر (برای تست‌ها و اجرای موازی)."""
    return os.environ.get("KRONOS_LOG", _LOG_DEFAULT)


def _cfg() -> dict:
    """خوانشِ تنظیمات از env — با سقفِ منطقی، تا ورودیِ بد هرگز مسیر را نکند."""
    backend = str(os.environ.get("KRONOS_BACKEND", "offline")).strip().lower()
    if backend not in BACKENDS:
        backend = "offline"

    def _int(key, default, lo, hi):
        try:
            return int(max(lo, min(hi, int(os.environ.get(key, default)))))
        except (TypeError, ValueError):
            return default

    model = str(os.environ.get("KRONOS_MODEL", "NeoQuasar/Kronos-mini")).strip()
    if model not in MODEL_PAIR:
        model = "NeoQuasar/Kronos-mini"
    return {"backend": backend,
            "model": model,
            "repo": str(os.environ.get("KRONOS_REPO", "")).strip(),
            "seed": _int("KRONOS_SEED", DEFAULT_SEED, 0, 2**31 - 1),
            "n_paths": _int("KRONOS_PATHS", DEFAULT_PATHS, 4, 128),
            "horizon": _int("KRONOS_HORIZON", DEFAULT_HORIZON, 1, 64)}


def _settings_fa(c: dict) -> str:
    """خطِ تکرارپذیری — مدرکِ هر ادعا همین را حمل می‌کند."""
    return (f"backend={c['backend']} · model={c['model']} · seed={c['seed']} · "
            f"T={TEMPERATURE} · top_p={TOP_P} · paths={c['n_paths']} · horizon={c['horizon']}")


# ================================================================ مسیرها
def _stub_paths(d: pd.DataFrame, c: dict) -> dict:
    """شبیه‌سازِ آفلاین — GBM با seed ثابت روی بازدهِ لگاریتمیِ خودِ کندل‌ها.

    این کرونوس نیست و هرگز ادعایش نمی‌شود؛ فقط خروجیِ هم‌شکلِ مدل می‌سازد تا
    لوله‌کشیِ شاهد، داوریِ شکاک و دروازه‌ی ۲۰۰ جلسه‌ای قبل از نصبِ مدل واقعی
    تست شود."""
    close = d["close"].to_numpy(dtype=float)
    last_px = float(close[-1])
    r = np.log(close[1:] / np.maximum(close[:-1], 1e-12))
    r = r[-STUB_CTX:]
    if len(r) < MIN_CTX - 1 or not np.isfinite(r).all():
        return {"ok": False, "why": f"داده برای آمارِ معتبرِ بازده کافی نیست ({len(r)} بازده)"}
    mu = float(np.mean(r))
    sigma = float(np.std(r, ddof=1))
    if sigma <= 0 or not np.isfinite(sigma):
        return {"ok": False, "why": f"پراکندگیِ بازده صفر است — پیش‌بینیِ معناداری از چارتِ راکد ندارم"}
    rng = np.random.default_rng(c["seed"])
    z = rng.standard_normal((c["n_paths"], c["horizon"]))
    cum = np.cumsum(mu + sigma * z, axis=1)
    finals = last_px * np.exp(cum[:, -1])
    rets = finals / last_px - 1.0
    return {"ok": True, "finals": finals, "rets": rets, "last_px": last_px,
            "ctx_len": int(min(len(d), STUB_CTX + 1))}


_PRED_CACHE: dict = {}  # (model, repo) → (tokenizer, net) — بارگیریِ یک‌بار در هر فرایند


def _load_net(c: dict):
    """بارگیریِ توکنایزر و مدل با کشِ فرایندی — وزن‌ها از HF Hub (رفتارِ رسمیِ مخزن)."""
    key = (c["model"], c["repo"])
    if key not in _PRED_CACHE:
        # اول مسیرِ مخزنِ رسمی، بعد import — وگرنه «model» پیدا نمی‌شود
        repo_dir = os.path.abspath(os.path.expanduser(c["repo"]))
        if repo_dir not in sys.path:
            sys.path.insert(0, repo_dir)
        import torch  # noqa: E402
        from model import Kronos, KronosTokenizer  # noqa: E402 — ماژولِ مخزنِ رسمی

        tokenizer = KronosTokenizer.from_pretrained(MODEL_PAIR[c["model"]])
        net = Kronos.from_pretrained(c["model"])
        _PRED_CACHE[key] = (tokenizer, net)
    return _PRED_CACHE[key]


def _kronos_paths(d: pd.DataFrame, c: dict, interval: str) -> dict:
    """مدلِ واقعی — فقط وقتی اپراتور صریحاً KRONOS_BACKEND=kronos داده باشد.

    مخزنِ رسمی پکیجِ pip نیست؛ از KRONOS_REPO (کلونِ شامل پوشه‌ی model/)
    import می‌کنیم. هر خطا → exception به بالا؛ تماس‌گیرنده به آفلاین برمی‌گردد."""
    if not c["repo"]:
        raise RuntimeError("KRONOS_REPO تنظیم نشده — مسیرِ کلونِ مخزنِ رسمی کرونوس لازم است")
    # اول مسیرِ مخزنِ رسمی، بعد import — وگرنه «model» پیدا نمی‌شود
    repo_dir = os.path.abspath(os.path.expanduser(c["repo"]))
    if repo_dir not in sys.path:
        sys.path.insert(0, repo_dir)
    import torch  # noqa: E402
    from model import KronosPredictor  # noqa: E402 — ماژولِ مخزنِ رسمی

    tokenizer, net = _load_net(c)
    torch.manual_seed(c["seed"])
    ctx = CTX_OF.get(c["model"], 512)
    price_ok = d.dropna(subset=["open", "high", "low", "close"])  # کندلِ ناقص حذف می‌شود
    x = price_ok.tail(ctx).copy()
    x["timestamps"] = pd.to_datetime(
        x["dt"] if "dt" in x.columns else pd.to_datetime(x["time"], unit="ms"))
    cols = ["open", "high", "low", "close", "volume", "amount"]
    for col in ("amount", "volume"):
        if col not in x.columns:
            x[col] = 0.0
    x_df = x[cols].astype(float).fillna(0.0)  # حجمِ گمشده = صفر (رفتارِ رسمیِ مخزن)
    x_ts = pd.Series(x["timestamps"].to_numpy())
    freq = INTERVAL_TO_FREQ.get(interval, _FREQ_FALLBACK)
    y_ts = pd.Series(pd.date_range(
        x["timestamps"].iloc[-1] + pd.Timedelta(freq), periods=c["horizon"], freq=freq))

    predictor = KronosPredictor(net, tokenizer, device="cpu", max_context=ctx)
    finals: list[float] = []
    for _ in range(c["n_paths"]):  # هر مسیر جدا — آماره‌ی تجمیعی به‌جای میانگینِ یک‌جا
        pred = predictor.predict(df=x_df, x_timestamp=x_ts, y_timestamp=y_ts,
                                 pred_len=c["horizon"], T=TEMPERATURE,
                                 top_p=TOP_P, sample_count=1, verbose=False)
        finals.append(float(pred["close"].iloc[-1]))
    finals = np.asarray(finals, dtype=float)
    last_px = float(price_ok["close"].iloc[-1])
    rets = finals / last_px - 1.0
    return {"ok": True, "finals": finals, "rets": rets, "last_px": last_px,
            "ctx_len": int(min(len(d), ctx))}


def _aggregate(paths: dict, c: dict) -> dict:
    """آمارِ تجمیعیِ مسیرها — تنها چیزی که از خروجیِ احتمالاتی حکم می‌شود (فصلِ ۷ گزارش)."""
    finals, rets = paths["finals"], paths["rets"]
    p_up = float(np.mean(rets > EPS))
    p_dn = float(np.mean(rets < -EPS))
    if p_up >= MAJORITY and p_up > p_dn:
        side = 1
    elif p_dn >= MAJORITY and p_dn > p_up:
        side = -1
    else:
        side = 0
    p5, p50, p95 = (float(x) for x in np.percentile(finals, [5, 50, 95]))
    return {"backend": c["backend"], "model": c["model"], "seed": c["seed"],
            "n_paths": c["n_paths"], "horizon": c["horizon"],
            "ctx_len": paths["ctx_len"], "predicting": True,
            "side": side, "agree_pct": round(max(p_up, p_dn) * 100.0, 1),
            "p_up": round(p_up * 100.0, 1), "p_dn": round(p_dn * 100.0, 1),
            "ret_med": round(float(np.median(rets)) * 100.0, 3),
            "last_px": paths["last_px"], "p5": p5, "p50": p50, "p95": p95,
            "settings_fa": _settings_fa(c)}


# ================================================================ عاملِ شاهد
def witness(d: pd.DataFrame, dec: int, backend: str | None = None,
            interval: str = "1hour") -> dict:
    """🔮 شاهدِ کرونوس — توزیعِ مسیرها + باندِ چارکی؛ همیشه fail-soft و صادق."""
    c = _cfg()
    if backend:
        c["backend"] = backend
    msgs: list[dict] = []
    claims: list[dict] = []
    note = ""
    paths = None
    if c["backend"] == "kronos":
        try:
            paths = _kronos_paths(d, c, interval)
        except Exception as exc:  # noqa: BLE001 — مدل نبود/شبکه نبود → آفلاینِ صادق
            note = f"بارگیریِ مدلِ واقعی شکست خورد ({type(exc).__name__}) — به شبیه‌سازِ آفلاین برگشتم؛ این خروجی کرونوس نیست."
            c["backend"] = "offline"
            paths = None
    if paths is None:
        paths = _stub_paths(d, c)

    head = {"key": "kronos", "emoji": "🔮", "name": "کرونوس",
            "role": "شاهدِ احتمالاتی — توزیعِ مسیرهای پیشِ رو؛ در حالتِ سایه نظر است، نه رأی",
            "msgs": msgs, "claims": claims, "ok": True, "pred": None}

    if not paths.get("ok"):
        msgs.append({"text": f"امروز پیش‌بینیِ معتبری ندارم — {paths.get('why', 'داده ناکافی است')}. "
                             f"به‌جای حدس از داده‌ی لاغر، سکوت می‌کنم.",
                     "why": f"قانونِ شاهد: حدِاقلِ {MIN_CTX} کندلِ سالم لازم است؛ دادهی فعلی را کافی ندیدم."})
        head["pred"] = {"backend": c["backend"], "model": c["model"], "seed": c["seed"],
                        "n_paths": c["n_paths"], "horizon": c["horizon"],
                        "ctx_len": int(len(d)), "predicting": False,
                        "side": 0, "agree_pct": 0.0, "p_up": 0.0, "p_dn": 0.0,
                        "ret_med": 0.0, "last_px": None, "p5": None, "p50": None,
                        "p95": None, "settings_fa": _settings_fa(c), "note_fa": paths.get("why", "")}
        return head

    pred = _aggregate(paths, c)
    pred["note_fa"] = note
    head["pred"] = pred
    stub_word = ("شبیه‌سازِ آفلاینِ مونت‌کارلو (مدلِ واقعی نصب نیست — فعال‌سازی: KRONOS_BACKEND=kronos)"
                 if c["backend"] == "offline" else f"مدلِ واقعیِ {c['model']} از KRONOS_REPO")

    side_fa = {1: "به بالا", -1: "به پایین", 0: "بدونِ جهتِ معنادار"}[pred["side"]]
    if pred["side"] == 0:
        msgs.append({"text": f"از <b>{pred['n_paths']}</b> مسیرِ پیشِ رو، هیچ جهتی اکثریتِ "
                             f"{int(MAJORITY * 100)}٪ را نگرفت (بالا {pred['p_up']}٪ / پایین {pred['p_dn']}٪) — "
                             f"می‌گویم «نمی‌دانم» و فقط باندِ قیمت را ثبت می‌کنم.",
                     "why": f"قانونِ شاهد: جهت فقط با اکثریتِ ≥{int(MAJORITY * 100)}٪ مسیرها اعلام می‌شود — نه با حس"})
    else:
        msgs.append({"text": f"از <b>{pred['n_paths']}</b> مسیرِ پیشِ رو، <b>{pred['agree_pct']}٪</b> "
                             f"<b>{side_fa}</b> می‌روند؛ میانه‌ی بازده در افقِ {pred['horizon']} کندل: "
                             f"<b>{pred['ret_med']:+.2f}٪</b>. — {stub_word}",
                     "why": f"آمارِ تجمیعیِ مسیرها؛ {pred['settings_fa']}"})
    if pred["last_px"] and pred["p5"] is not None:
        msgs.append({"text": f"باندِ ۵–۹۵٪ قیمت در افق: <b>{pred['p5']:,.{dec}f}</b> تا "
                             f"<b>{pred['p95']:,.{dec}f}</b> (میانه <b>{pred['p50']:,.{dec}f}</b>).",
                     "why": f"چارکِ ۵/۵۰/۹۵ روی قیمتِ پایانیِ {pred['n_paths']} مسیر — باندِ احتمالاتی، نه هدفِ معامله"})
    msgs.append({"text": "حالتِ سایه‌ام: روی حکمِ تیم اثری ندارم — فقط ثبت می‌شوم تا دروازه‌ی "
                         f"«هم‌جهتیِ >۵۵٪ روی ۲۰۰ جلسه» پر شود؛ تازه در فازِ دو اجازه‌ی انتشار می‌گیرم.",
                 "why": "نقشه‌راهِ سه‌فازیِ گزارشِ کرونوس (جدول ۴) — هر فاز دروازه‌ی خروجِ خودش را دارد"})
    claims.append({"by": "kronos", "side": pred["side"],
                   "claim": f"{pred['agree_pct']}٪ مسیرها {side_fa} · میانه {pred['ret_med']:+.2f}٪ در {pred['horizon']} کندل",
                   "evidence": f"{pred['settings_fa']} · ctx={pred['ctx_len']} کندل"})
    return head


# ================================================================ شکاک (فقط هشدار/تایید — حالتِ سایه)
def skeptic_kronos_check(witness_out: dict, chart_side: int, plan: dict) -> list[dict]:
    """داوریِ شکاک درباره‌ی ادعای شاهد — در فازِ یک هیچ اعتراضِ سختی ندارد:
    مخالفت = هشدارِ ثبت‌شده، هم‌جهتی = تاییدِ بدونِ وزنِ تصمیم؛ حدضررِ خارج از
    باند هم هشدار است (فصلِ ۸ گزارش: مطابقتِ باند را بازرسی کن)."""
    checks: list[dict] = []
    pred = (witness_out or {}).get("pred") or {}
    if not pred.get("predicting"):
        return checks  # شاهد پیش‌بینی نکرده — چیزی برای محک‌زدن نیست
    band_fa = (f"باندِ ۵–۹۵٪ او [{pred['p5']:,.4f} … {pred['p95']:,.4f}]")
    if chart_side != 0 and pred["side"] != 0:
        if pred["side"] == chart_side:
            checks.append({"target": "کرونوس", "about": "هم‌جهتیِ مسیرها با سیگنال",
                           "verdict": "تایید", "shadow": True,
                           "reason": f"اکثریتِ {pred['agree_pct']}٪ مسیرها با سیگنالِ چارت هم‌جهت‌اند — "
                                     f"شاهدِ احتمالاتی است و وزنِ تصمیم ندارد، فقط ثبت می‌شود ({band_fa})."})
        else:
            checks.append({"target": "کرونوس", "about": "مخالفتِ مسیرها با سیگنال",
                           "verdict": "هشدار", "shadow": True,
                           "reason": f"اکثریتِ {pred['agree_pct']}٪ مسیرهای شاهد برخلاف سیگنالِ چارت می‌روند "
                                     f"({band_fa}) — در حالتِ سایه حکم را عوض نمی‌کند، ولی ثبت می‌شود "
                                     "تا آمارِ دروازه‌ی ۲۰۰ جلسه‌ای واقعی بماند."})
    if plan.get("status") == "active" and plan.get("stop"):
        stop = float(plan["stop"])
        if pred["p5"] is not None and not (pred["p5"] <= stop <= pred["p95"]):
            checks.append({"target": "کرونوس", "about": "حدضرر در برابر باندِ احتمالاتی",
                           "verdict": "هشدار", "shadow": True,
                           "reason": f"حدضررِ تو ({stop:,.4f}) داخلِ {band_fa} نیست — "
                                     "یعنی سناریویِ مسیرها حدضرر را با احتمالِ بیش از ۵٪ می‌بیند؛ "
                                     "فقط هشدارِ ثبت‌شده، نه وتو."})
    return checks


# ================================================================ دروازه‌ی فازِ یک
def _chart_side_of(room: dict) -> int:
    """جهتِ سیگنالِ چارت از ادعای چارت‌خوان — همان مبنایی که شکاکِ اصلی استفاده می‌کند."""
    for cl in ((room.get("agents") or {}).get("chart") or {}).get("claims") or []:
        if cl.get("by") == "chart":
            return int(cl.get("side") or 0)
    return 0


def log_session(room: dict, path: str | None = None) -> dict:
    """ثبتِ یک جلسه‌ی paper-trade برای دروازه‌ی فازِ یک — append-only و fail-soft."""
    p = path or log_path()
    try:
        if not (room or {}).get("ok") or not (room or {}).get("symbol"):
            return {"logged": False, "error": "جلسه‌ی معتبری برای ثبت نیست — فقط جلساتِ ok ثبت می‌شوند"}
        plan = room.get("plan") or {}
        pred = ((room.get("agents") or {}).get("kronos") or {}).get("pred") or {}
        entry = {
            "ts": room.get("ts") or datetime.now().strftime("%Y-%m-%d %H:%M"),
            "symbol": room.get("symbol"), "interval": room.get("interval"),
            "exchange": room.get("exchange"),
            "signal_active": plan.get("status") == "active",
            "team_side": _chart_side_of(room),
            "kronos_side": (int(pred["side"]) if pred.get("predicting") else None),
            "kronos_agree_pct": (pred.get("agree_pct") if pred.get("predicting") else None),
            "backend": pred.get("backend"), "model": pred.get("model"),
            "seed": pred.get("seed"),
            "verdict_state": (room.get("verdict") or {}).get("state"),
        }
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return {"logged": True, "entry": entry, "path": p}
    except Exception as exc:  # noqa: BLE001 — ثبتِ نبود جلسه را نمی‌بُرد
        return {"logged": False, "error": f"{type(exc).__name__}: {exc}"}


def gate_stats(path: str | None = None) -> dict:
    """آمارِ دروازه‌ی فازِ یک — هم‌جهتیِ >۵۵٪ روی ۲۰۰ جلسه (جدول ۴ گزارش).

    دروازه‌ی رسمی فقط با جلساتِ «مدلِ واقعی» جمع می‌خورد؛ جلساتِ شبیه‌ساز
    «تمرینِ لوله‌کشی» حساب می‌شوند و جداگانه گزارش می‌شوند — صادقانه."""
    p = path or log_path()
    entries: list[dict] = []
    try:
        with open(p, encoding="utf-8") as f:
            for line in f:
                try:
                    entries.append(json.loads(line))
                except ValueError:
                    continue  # خطِ خرابِ وسطِ دفتر، دفتر را نمی‌بُرد
    except FileNotFoundError:
        entries = []
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    def _rate(rows: list[dict]) -> dict:
        # فقط جلساتی با ادعای جهت‌دار (هر دو سمت ±۱) واردِ آمار می‌شوند؛
        # «بی‌جهتِ» شاهد و بی‌سیگنالیِ چارت = بدونِ ادعا، نه مخالفت
        sig = [e for e in rows if e.get("signal_active")
               and e.get("kronos_side") in (1, -1) and e.get("team_side") in (1, -1)]
        agree = sum(1 for e in sig if int(e["kronos_side"]) == int(e["team_side"]))
        rate = round(agree / len(sig) * 100.0, 1) if sig else None
        return {"n": len(sig), "agree": agree, "rate": rate}

    real = _rate([e for e in entries if e.get("backend") == "kronos"])
    stub = _rate([e for e in entries if e.get("backend") == "offline"])
    gate_pass = bool(real["n"] >= 200 and (real["rate"] or 0.0) > 55.0)
    last = entries[-1] if entries else None
    return {"ok": True, "n_total": len(entries),
            "real": real, "stub": stub,
            "gate_pass": gate_pass,
            "gate_fa": ("✅ دروازه گذشت" if gate_pass else
                        f"⏳ {real['n']}/۲۰۰ جلسه‌ی مدلِ واقعی" +
                        (f" · هم‌جهتیِ {real['rate']}٪" if real["rate"] is not None else "")),
            "last": last}
