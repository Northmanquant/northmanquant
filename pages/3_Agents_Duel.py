"""Agents Duel v3 — چهار ایجنت با «مدرک»: کندل‌ها، ساختار بازار، نقدینگی، جریان پول، FVG/BVG
هر ایجنت یک جدول دلیل دارد و در پایان «بهترین پوزیشن» از اجماعِ وزن‌دار ساخته می‌شود.
"""
from __future__ import annotations

import json
import time
import os
from datetime import datetime

import numpy as np
import pandas as pd
import streamlit as st
from core.i18n import setup_i18n
from core.duel_engine import (AGENTS, FACTOR_FA, agent_scores, backtest, build_features,
                              build_position, calculate_duel, describe, get_df, pos_text,
                              signals_with_hysteresis, _dec_for, _swings, _verdict)

st.set_page_config(page_title="Agents Duel", page_icon="🤖", layout="wide")
setup_i18n(page="p3")   # زبان + منوی ترجمه‌شده + پچ ترجمه‌ی کل صفحه
st.title("🤖 دوئل ایجنت‌ها — کدوم ربات می‌بره؟ (با مدرک)")
st.caption("NorthmanQuant · Agents Duel v5.0 (+ شکار بازار · ستاپ اعتبارسنجی‌شده) · صفحه آماده‌ی اجراست؛ داده فقط با «شروع دوئل» دریافت می‌شود.")
st.caption("۴ ایجنت روی ۱ ارز با قانون‌های شفاف پوزیشن می‌گیرند؛ هر کدام جدول دلیل و مدرک دارد. "
           "برنده + پوزیشن اجماعی با SL/TP به 👥 تحلیل‌های کاربران می‌رود.")

EXCHANGES = ["KuCoin", "OKX", "Binance", "Bybit", "Lighter", "XT", "LBank", "KCEX"]

try:
    from core import gaps as G
except Exception:  # noqa: BLE001
    G = None

try:
    from core import community_store as _cstore
except Exception:  # noqa: BLE001
    _cstore = None


# ----------------------------------------------------------------------------- storage
def save_duel(entry: dict) -> None:
    """ثبت نتیجه دوئل در برد مشترک — Supabase اگر ست باشد، وگرنه JSON محلی."""
    if _cstore is not None:
        try:
            _cstore.save_community(entry)
            return
        except Exception as e:  # noqa: BLE001
            st.warning(f"ذخیره در بک‌اند اصلی نشد؛ fallback محلی: {e}")
    rows = []
    if os.path.exists("community_analyses.json"):
        try:
            with open("community_analyses.json", "r", encoding="utf-8") as f:
                rows = json.load(f)
        except Exception:  # noqa: BLE001
            rows = []
    rows.insert(0, entry)
    rows = rows[:200]
    try:
        with open("community_analyses.json", "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False)
    except Exception as e:  # noqa: BLE001
        st.warning(f"ذخیره نشد: {e}")

# ----------------------------------------------------------------------------- UI helpers
def render_position(p: dict, dec: int, tone: str) -> None:
    if p["direction"] == 0:
        st.info("این ایجنت فعلاً پوزیشن نمی‌گیرد (امتیاز زیر آستانه) — ولی تمایلش در جدول دیده می‌شود.")
        return
    cols = st.columns(5)
    cols[0].metric("جهت", "لانگ 🟢" if p["direction"] > 0 else "شورت 🔴")
    cols[1].metric("ورود", f"{p['entry']:,.{dec}f}")
    cols[2].metric("حد ضرر", f"{p['stop']:,.{dec}f}", f"{(p['stop'] / p['entry'] - 1) * 100:+.2f}%")
    for j, (tp, rr, why) in enumerate(p["targets"][:2]):
        cols[3 + j].metric(f"TP{j + 1}", f"{tp:,.{dec}f}", f"{rr}R")
    st.markdown(
        f"<div dir='rtl' style='font-size:12px;color:#94a3b8;border-right:3px solid {tone};padding-right:8px'>"
        f"دلیل حد ضرر: {p['sl_reason']} − ۰.۲۵ ATR<br>"
        + "<br>".join(f"TP{i + 1}: {tp:,.{dec}f} ← {why}" for i, (tp, rr, why) in enumerate(p["targets"]))
        + "</div>", unsafe_allow_html=True)


# =============================================================================
# 🔎 شکار بازار — ایجنت‌ها کل صرافی را می‌گردند و بهترین لانگ/شورت‌ها را می‌دهند
#   • دقیقاً همان موتور دوئل (calculate_duel) روی هر ارز پرحجم اجرا می‌شود — نه قانون تازه.
#   • یک ارز فقط وقتی «برگزیده» می‌شود که هر سه فیلتر زیر را رد کند:
#       ۱) اجماع وزن‌دار ایجنت‌ها قوی باشد (|امتیاز| ≥ آستانه)
#       ۲) حداقل ۳ ایجنت از ۴ هم‌جهت باشند
#       ۳) ایجنت(های) هم‌جهت روی خود همان ارز در بک‌تست سودده بوده باشند (PF > 1 و بازده مثبت)
#     → چیزی که این سه فیلتر را رد کند، «نظر خالی» نیست؛ پشتش عدد است.
# =============================================================================
HUNT_POOL_FALLBACK = ["BTC-USDT", "ETH-USDT", "SOL-USDT", "XRP-USDT", "BNB-USDT", "DOGE-USDT",
                      "ADA-USDT", "AVAX-USDT", "LINK-USDT", "TRX-USDT", "LTC-USDT", "DOT-USDT"]


def _hunt_pool(exchange: str, n: int) -> list[str]:
    try:
        import app_base as B
        tops = B.fetch_top_coins(exchange, 1_000_000, 40)
        pool = pd.concat([tops["volume"], tops["gainers"], tops["losers"]]).drop_duplicates("symbol")
        syms = [s for s in pool["symbol"].tolist() if not str(s).upper().startswith(("USDC", "USDT", "DAI", "TUSD", "FDUSD"))]
        return syms[:n] or HUNT_POOL_FALLBACK[:n]
    except Exception:  # noqa: BLE001
        return HUNT_POOL_FALLBACK[:n]


def _hunt_one(exchange: str, symbol: str, interval: str, balance: float, fee_pct: float):
    """یک ارز را از همان موتور دوئل رد می‌کند و خلاصه‌ی قابل رتبه‌بندی برمی‌گرداند."""
    try:
        S_ = calculate_duel(exchange, symbol, interval, 300, balance, fee_pct)
    except Exception as exc:  # noqa: BLE001
        return {"symbol": symbol, "error": f"{type(exc).__name__}: {exc}"}
    res, fd, fp = S_["results"], S_["final_dir"], S_["final_pos"]
    # «موافق» = تمایل ایجنت (همان lean صفحه‌ی دوئل: |امتیاز| ≥ ۰.۱۵) هم‌جهت با اجماع
    agree = [n for n, r in res.items() if fd != 0 and np.sign(r["score"]) == fd and abs(r["score"]) >= 0.15]
    open_pos = [n for n, r in res.items() if r["sig"] == fd and fd != 0]   # ایجنت‌هایی که همین الان پوزیشن باز دارند
    aligned_bt = [res[n]["bt"] for n in agree]
    prof = [b for b in aligned_bt if b["pf"] > 1.0 and b["total"] > 0]
    best_bt = max(aligned_bt, key=lambda b: (b["pf"], b["total"])) if aligned_bt else None
    # دلایل: سه فاکتور با بیشترین سهم در جهتِ تصمیم، از بین ایجنت‌های موافق
    reasons = []
    for n in agree:
        for row in res[n]["rows"]:
            if np.sign(row["سهم در تصمیم"]) == fd and abs(row["سهم در تصمیم"]) > 0.02:
                reasons.append((abs(row["سهم در تصمیم"]), f"{row['فاکتور']}: {row['مدرک (مشاهده‌ی واقعی)']}"))
    seen, top_reasons = set(), []
    for _, txt in sorted(reasons, key=lambda x: -x[0]):
        key = txt.split(":")[0]
        if key not in seen:
            seen.add(key)
            top_reasons.append(txt)
        if len(top_reasons) == 3:
            break
    d_ = S_["d"]
    adx = float(d_["adx"].iloc[-1]) if "adx" in d_.columns and np.isfinite(d_["adx"].iloc[-1]) else 0.0
    # فیلتر ۴: موتور ستاپ اعتبارسنجی‌شده‌ی app_base (walk-forward روی همین ارز) باید فعال و هم‌جهت باشد
    try:
        import app_base as _B
        vp = _B.setup_plan(d_)
        v_ok = vp["status"] == "active" and ((vp["direction"].startswith("لانگ") and fd > 0) or (vp["direction"].startswith("شورت") and fd < 0))
        v_txt = vp.get("why", "") if v_ok else ("ستاپ معتبر فعال نیست" if vp["status"] != "active" else "ستاپ معتبر خلاف جهت ایجنت‌هاست")
        v_stats = vp["stats"]
    except Exception as _e:  # noqa: BLE001
        vp, v_ok, v_txt, v_stats = None, False, f"اعتبارسنجی انجام نشد: {_e}", {}
    return {
        "symbol": S_["sym"], "dir": fd, "score": S_["final_s"], "confidence": S_["confidence"],
        "agree": agree, "n_agree": len(agree), "n_prof": len(prof), "open_pos": open_pos,
        "best_pf": best_bt["pf"] if best_bt else 0.0, "best_ret": best_bt["total"] if best_bt else 0.0,
        "best_win": best_bt["win"] if best_bt else 0.0, "best_trades": best_bt["trades"] if best_bt else 0,
        "pos": fp, "dec": S_["dec"], "price": float(d_["close"].iloc[-1]), "adx": adx,
        "reasons": top_reasons, "winner": S_["winner"], "fvg_txt": "",
        "v_ok": v_ok, "v_txt": v_txt, "v_plan": vp,
        "ts": S_["ts"],
    }


def run_hunt(exchange: str, interval: str, n_pool: int, balance: float, fee_pct: float,
             min_score: float, min_agree: int, workers: int = 6) -> tuple[list[dict], list[dict], list[str]]:
    from concurrent.futures import ThreadPoolExecutor
    import threading
    pool = _hunt_pool(exchange, n_pool)
    init = None
    try:
        from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx
        ctx = get_script_run_ctx()
        if ctx is not None:
            def init():  # noqa: E306
                add_script_run_ctx(threading.current_thread(), ctx)
    except Exception:  # noqa: BLE001
        init = None
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(pool))), initializer=init) as ex:
        out = list(ex.map(lambda s: _hunt_one(exchange, s, interval, balance, fee_pct), pool))
    errors = [f"{o['symbol']} — {o['error']}" for o in out if o.get("error")]
    ok = [o for o in out if not o.get("error")]
    picks = [o for o in ok
             if o["dir"] != 0 and abs(o["score"]) >= min_score and o["n_agree"] >= min_agree and o["n_prof"] >= 1
             and o["pos"]["direction"] != 0 and o["pos"]["rr"] >= 1.0 and o.get("v_ok")]
    # سطوح نهایی از موتور اعتبارسنجی‌شده (ورود در لحظه‌ی ستاپ، SL ساختاری، TP نردبانی)
    for o in picks:
        vp = o.get("v_plan") or {}
        if vp.get("entry") is not None:
            o["pos"] = {"direction": o["dir"], "entry": vp["entry"], "stop": vp["stop"], "rr": vp["rr"],
                        "targets": [(t[0], t[1], w) for t, w in zip(vp["targets"], vp.get("target_why", ["1R", "2R", "3R"]))],
                        "sl_reason": vp.get("stop_why", ""), "atr": vp.get("atr", 0)}
    # رتبه: قدرت اجماع × تعداد موافق × کیفیت بک‌تست × R:R
    for o in picks:
        o["rank"] = abs(o["score"]) * (1 + 0.25 * o["n_agree"]) * min(2.5, o["best_pf"]) * (1 + min(o["pos"]["rr"], 3) / 4)
    picks.sort(key=lambda o: -o["rank"])
    return picks, ok, errors


def render_hunt(exchange: str, interval: str, balance: float, fee_pct: float) -> None:
    st.caption("ایجنت‌ها خودشان پرحجم‌ترین ارزهای صرافی را یکی‌یکی از همان موتور دوئل رد می‌کنند و فقط ارزهایی را "
               "برمی‌گزینند که ۱) اجماع قوی دارند، ۲) حداقل ۳ ایجنت هم‌جهت‌اند، ۳) ایجنت هم‌جهت روی همان ارز در بک‌تست سودده بوده و "
               "۴) موتور ستاپ اعتبارسنجی‌شده (walk-forward روی همان ارز) همین الان ستاپ هم‌جهت داده باشد. "
               "اگر چیزی این فیلترها را رد نکند، چیزی نشان داده نمی‌شود — بهتر از سیگنال الکی.")
    h1, h2, h3, h4 = st.columns([1, 1, 1, 0.8])
    with h1:
        n_pool = st.select_slider("چند ارز بررسی شود", options=[12, 20, 30, 40], value=20, key="hunt_n")
    with h2:
        min_score = st.select_slider("حداقل قدرت اجماع", options=[0.15, 0.20, 0.25, 0.30, 0.40], value=0.20, key="hunt_min")
    with h3:
        min_agree = st.select_slider("حداقل ایجنت موافق", options=[2, 3, 4], value=3, key="hunt_agree")
    with h4:
        st.write("")
        go_hunt = st.button("🔎 شروع شکار بازار", type="primary", use_container_width=True, key="hunt_go")

    if go_hunt:
        t0 = time.time()
        with st.spinner(f"ایجنت‌ها در حال بررسی {n_pool} ارز روی {exchange} · {interval} … (۳۰–۹۰ ثانیه)"):
            picks, allres, errors = run_hunt(exchange, interval, int(n_pool), float(balance), fee_pct, float(min_score), int(min_agree))
        st.session_state["hunt"] = {"picks": picks, "all": allres, "errors": errors, "exchange": exchange,
                                    "interval": interval, "took": time.time() - t0, "ts": datetime.now().strftime("%Y-%m-%d %H:%M")}

    H = st.session_state.get("hunt")
    if not H:
        st.info("روی «🔎 شروع شکار بازار» بزن.")
        return
    picks, allres, errors = H["picks"], H["all"], H["errors"]
    st.caption(f"{len(allres)} ارز تحلیل شد روی {H['exchange']} · {H['interval']} در {H['took']:.0f} ثانیه · {H['ts']}"
               + (f" · {len(errors)} ارز خطا داد" if errors else ""))
    if errors and len(errors) >= max(2, len(allres)):
        st.error("تحلیل اکثر ارزها خطا داد — نمونه: " + errors[0][:200])

    longs = [p for p in picks if p["dir"] > 0]
    shorts = [p for p in picks if p["dir"] < 0]
    m1, m2, m3 = st.columns(3)
    m1.metric("برگزیده‌ها", len(picks))
    m2.metric("لانگ 🟢", len(longs))
    m3.metric("شورت 🔴", len(shorts))

    if not picks:
        st.warning("هیچ ارزی هر سه فیلتر را رد نکرد. یعنی الان ستاپ با لبه‌ی واضح در این تایم‌فریم نیست — "
                   "می‌توانی تایم‌فریم دیگری را امتحان کنی یا «حداقل ایجنت موافق» را روی ۲ بگذاری (ریسک بالاتر).")
    else:
        for rank_i, p in enumerate(picks, 1):
            pos, dec = p["pos"], p["dec"]
            is_long = p["dir"] > 0
            tone = "#16a34a" if is_long else "#ef4444"
            entry, stop = pos["entry"], pos["stop"]
            sl_pct = (stop / entry - 1) * 100
            tps = pos["targets"][:3]

            def _cell(lbl, val, sub, bg, col="#e2e8f0", lc="#94a3b8"):
                return (f"<div style='background:{bg};border-radius:10px;padding:8px'>"
                        f"<div style='font-size:10px;color:{lc}'>{lbl}</div>"
                        f"<div style='font-family:ui-monospace,monospace;font-weight:800;font-size:14px;color:{col}'>{val}</div>"
                        f"<div style='font-size:9px;color:#94a3b8'>{sub}</div></div>")

            cells = _cell("ورود", f"{entry:,.{dec}f}", "قیمت فعلی", "rgba(148,163,184,.08)") \
                + _cell("حد ضرر (SL)", f"{stop:,.{dec}f}", f"{sl_pct:+.2f}% · {pos['sl_reason']}", "rgba(239,68,68,.12)", "#ef4444", "#fca5a5")
            for i, (tp, rr, why) in enumerate(tps):
                cells += _cell(f"TP{i + 1} · {rr}R", f"{tp:,.{dec}f}", f"{(tp / entry - 1) * 100:+.2f}% · {why}",
                               f"rgba(34,197,94,{.10 + i * .04})", "#16a34a", "#86efac")
            agents_txt = " · ".join(p["agree"])
            reasons_html = "".join(f"<li>{r}</li>" for r in p["reasons"]) or "<li>—</li>"
            st.markdown(
                f"<div dir='rtl' style='border:1px solid rgba(148,163,184,.2);border-right:5px solid {tone};border-radius:14px;"
                f"padding:14px 16px;margin:10px 0;background:rgba(148,163,184,.05)'>"
                f"<div style='display:flex;justify-content:space-between;flex-wrap:wrap;gap:10px;align-items:center'>"
                f"<span style='font-size:18px;font-weight:800'>#{rank_i} {p['symbol']}</span>"
                f"<span style='font-family:ui-monospace,monospace;font-size:15px;color:{tone};font-weight:800'>{'لانگ 🟢' if is_long else 'شورت 🔴'}</span>"
                f"<span style='font-size:12px;color:#94a3b8'>اجماع {p['score']:+.2f} · اطمینان {p['confidence']}% · {p['n_agree']}/4 ایجنت موافق · ADX {p['adx']:.0f}</span>"
                f"</div>"
                f"<div style='display:grid;grid-template-columns:repeat({2 + len(tps)},1fr);gap:8px;margin-top:12px;text-align:center'>{cells}</div>"
                f"<div style='margin-top:10px;font-size:12px;color:#cbd5e1'>"
                f"<b>ایجنت‌های موافق:</b> {agents_txt}" + (f" · <b>پوزیشن باز:</b> {' · '.join(p['open_pos'])}" if p.get('open_pos') else "") + "<br>"
                f"<b>بک‌تست بهترین ایجنت هم‌جهت روی همین ارز:</b> بازده {p['best_ret']:+.2f}% · PF {p['best_pf']:.2f} · وین {p['best_win']:.0f}% · {p['best_trades']} معامله<br>"
                f"<b>✅ ستاپ اعتبارسنجی‌شده:</b> {p.get('v_txt', '')}"
                f"</div>"
                f"<div style='margin-top:8px;font-size:12px;color:#e2e8f0'><b>چرا؟</b><ul style='margin:4px 18px 0 0;padding:0;line-height:1.9'>{reasons_html}</ul></div>"
                f"</div>",
                unsafe_allow_html=True,
            )

        # جدول خلاصه + CSV
        rows = []
        for p in picks:
            tps = [t[0] for t in p["pos"]["targets"]] + [None, None, None]
            rows.append({"نماد": p["symbol"], "جهت": "لانگ 🟢" if p["dir"] > 0 else "شورت 🔴", "اجماع": round(p["score"], 2),
                         "اطمینان%": p["confidence"], "ایجنت موافق": f"{p['n_agree']}/4", "PF بک‌تست": round(p["best_pf"], 2),
                         "بازده بک‌تست%": round(p["best_ret"], 2), "ورود": p["pos"]["entry"], "SL": p["pos"]["stop"],
                         "TP1": tps[0], "TP2": tps[1], "TP3": tps[2], "R:R": p["pos"]["rr"]})
        hunt_df = pd.DataFrame(rows)
        st.dataframe(hunt_df, use_container_width=True, hide_index=True)
        st.download_button("💾 ذخیره برگزیده‌ها (CSV)", data=hunt_df.to_csv(index=False).encode("utf-8"),
                           file_name=f"hunt_{H['exchange']}_{H['interval']}.csv", mime="text/csv", key="hunt_csv")

        if st.button("💾 ذخیره‌ی برگزیده‌ها در 👥 تحلیل‌های کاربران", key="hunt_save"):
            for p in picks[:5]:
                tps = [t[0] for t in p["pos"]["targets"]] + [None, None, None]
                dec = p["dec"]
                txt = (f"شکار بازار {H['exchange']}/{H['interval']} — {p['n_agree']}/4 ایجنت موافق ({', '.join(p['agree'])}) · اجماع {p['score']:+.2f}\n"
                       f"بک‌تست بهترین ایجنت هم‌جهت روی همین ارز: {p['best_ret']:+.2f}% · PF {p['best_pf']:.2f} · وین {p['best_win']:.0f}%\n"
                       f"حد ضرر: {p['pos']['sl_reason']}\n" + "\n".join(f"TP{i + 1} {tp:,.{dec}f} ({rr}R) ← {why}" for i, (tp, rr, why) in enumerate(p["pos"]["targets"]))
                       + "\nدلایل: " + " | ".join(p["reasons"]) + "\nتحلیل قانون‌محور + بک‌تست؛ توصیه‌ی سرمایه‌گذاری نیست.")
                save_duel({"name": "🔎 شکار بازار (ایجنت‌ها)", "symbol": p["symbol"].upper(), "exchange": H["exchange"],
                           "bias": "لانگ 🟢" if p["dir"] > 0 else "شورت 🔴", "tf": H["interval"], "entry": float(p["pos"]["entry"]),
                           "stop": float(p["pos"]["stop"]), "tp1": tps[0], "tp2": tps[1], "tp3": tps[2],
                           "rr": f"1:{p['pos']['rr']}", "confidence": int(p["confidence"]), "text": txt, "image": "",
                           "ts": datetime.now().strftime("%Y-%m-%d %H:%M")})
            st.success(f"{min(5, len(picks))} تحلیل ذخیره شد → صفحه‌ی اصلی → «تحلیل‌ها» → تب «👥 تحلیل‌های کاربران».")

    with st.expander(f"📋 همه‌ی {len(allres)} ارز بررسی‌شده (چرا بقیه انتخاب نشدند)", expanded=False):
        rows = []
        for o in sorted(allres, key=lambda o: -abs(o["score"])):
            why = []
            if o["dir"] == 0 or abs(o["score"]) < min_score:
                why.append("اجماع ضعیف")
            if o["n_agree"] < min_agree:
                why.append(f"فقط {o['n_agree']} ایجنت موافق")
            if o["n_prof"] == 0:
                why.append("ایجنت هم‌جهت در بک‌تست سودده نبود")
            if o["pos"]["direction"] != 0 and o["pos"]["rr"] < 1.0:
                why.append("R:R زیر ۱")
            if not o.get("v_ok"):
                why.append(o.get("v_txt", "ستاپ معتبر ندارد"))
            rows.append({"نماد": o["symbol"], "تمایل": "لانگ 🟢" if o["dir"] > 0 else "شورت 🔴" if o["dir"] < 0 else "خنثی ⚪",
                         "اجماع": round(o["score"], 2), "ایجنت موافق": f"{o['n_agree']}/4", "PF هم‌جهت": round(o["best_pf"], 2),
                         "نتیجه": "✅ برگزیده" if not why else " · ".join(why)})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        if errors:
            st.caption("خطاها: " + " | ".join(errors[:5]))


# ----------------------------------------------------------------------------- inputs
c1, c2, c3, c4, c5 = st.columns([1.3, 1, 1, 1, 1])
with c1:
    symbol = st.text_input("ارز", value="BTC-USDT", help="برای Lighter فقط BTC بنویس (بدون USDT)")
with c2:
    exchange = st.selectbox("صرافی", EXCHANGES, index=0)
with c3:
    interval = st.selectbox("تایم‌فریم", ["15min", "1hour", "4hour", "1day"], index=1)
with c4:
    balance = st.number_input("بالانس شروع", value=10000, min_value=100)
with c5:
    n_candles = st.select_slider("تعداد کندل", options=[200, 300, 400, 500], value=300)
fee_pct = 0.06

if exchange == "Lighter":
    st.info("Lighter پرپ هست - مثلا BTC یا ETH بنویس، نه BTC-USDT")

tab_duel, tab_hunt = st.tabs(["⚔️ دوئل روی یک ارز", "🔎 شکار بازار — بهترین لانگ/شورت‌های صرافی"])

with tab_hunt:
    render_hunt(exchange, interval, float(balance), fee_pct)

with tab_duel:
    if st.button("🚀 شروع دوئل", type="primary", use_container_width=True):
        try:
            with st.spinner("در حال گرفتن کندل‌ها و ساختن مدارک…"):
                new_result = calculate_duel(exchange, symbol, interval, n_candles, balance, fee_pct)
            st.session_state["duel"] = new_result
            # A second run must not keep the editable report from the first run.
            st.session_state.pop("duel_txt", None)
        except Exception as exc:
            st.error(f"دوئل اجرا نشد: {exc}")
            st.info("اتصال به صرافی، نماد و تایم‌فریم را بررسی کن و دوباره «شروع دوئل» را بزن.")
            if st.session_state.get("duel"):
                st.warning("نتایج زیر مربوط به اجرای موفق قبلی‌اند؛ تحلیل تازه‌ای تولید نشده است.")

    # ----------------------------------------------------------------------------- results
    S = st.session_state.get("duel")
    if not S:
        st.info("یک ارز انتخاب کن و «🚀 شروع دوئل» را بزن.")
    else:

        d, F, extras, results, dec = S["d"], S["F"], S["extras"], S["results"], S["dec"]
        price = float(d["close"].iloc[-1])
        st.caption(f"دیتا: {S['sym']} روی {S['exchange']} · {S['interval']} · {len(d)} کندل · منبع: {S['src']} · "
                   f"آخرین کندل {str(d['dt'].iloc[-1])[:16] if 'dt' in d.columns else ''} · قیمت {price:,.{dec}f} · {S['ts']}")

        # --- equity chart -------------------------------------------------------------------
        import plotly.graph_objects as go  # noqa: E402
        fig = go.Figure()
        for name, r in results.items():
            fig.add_trace(go.Scatter(y=r["bt"]["eq"], mode="lines", name=f"{name} ({r['bt']['total']:+.2f}%)",
                                     line=dict(color=r["spec"]["color"], width=2)))
        fig.update_layout(template="plotly_dark", height=380, title="Equity — موجودی هر ایجنت روی همین کندل‌ها (با کارمزد)",
                          margin=dict(l=20, r=20, t=50, b=20), legend=dict(orientation="h"))
        st.plotly_chart(fig, use_container_width=True)

        dfres = pd.DataFrame([{
            "ایجنت": n, "بازده%": round(r["bt"]["total"], 2), "معاملات": r["bt"]["trades"], "وین%": round(r["bt"]["win"], 1),
            "PF": round(r["bt"]["pf"], 2), "DD%": round(r["bt"]["dd"], 2), "در بازار%": round(r["bt"]["exposure"], 0),
            "۲۰ کندل اخیر%": round(r["bt"]["recent"], 2), "امتیاز الان": round(r["score"], 2),
            "پوزیشن الان": "LONG 🟢" if r["sig"] > 0 else "SHORT 🔴" if r["sig"] < 0 else "FLAT ⚪",
            "وزن در اجماع": round(S["weights"][n] / sum(S["weights"].values()) * 100, 0),
        } for n, r in results.items()]).sort_values("بازده%", ascending=False)
        st.dataframe(dfres, use_container_width=True, hide_index=True)
        w = results[S["winner"]]
        st.success(f"🏆 برنده‌ی بک‌تست: {S['winner']} با {w['bt']['total']:+.2f}% — {w['bt']['trades']} معامله — وین {w['bt']['win']:.0f}% — PF {w['bt']['pf']:.2f}")

        # --- final consensus position -----------------------------------------------------
        st.divider()
        st.subheader("🎯 بهترین پوزیشن (اجماع وزن‌دار ایجنت‌ها)")
        try:
            import app_base as _B
            _vp = _B.setup_plan(d)
            _agree = _vp["status"] == "active" and ((_vp["direction"].startswith("لانگ") and S["final_dir"] > 0) or (_vp["direction"].startswith("شورت") and S["final_dir"] < 0))
            if _agree:
                st.success(f"✅ موتور ستاپ اعتبارسنجی‌شده هم‌جهت است — {_vp['why']}")
            elif _vp["status"] == "active":
                st.error(f"⚠️ موتور ستاپ اعتبارسنجی‌شده **خلاف** نظر ایجنت‌هاست ({_vp['direction']}) — {_vp['why']}. در تست walk-forward، ورود بر اساس اجماع اندیکاتورها به‌تنهایی لبه نداشت؛ این پوزیشن را نگیر.")
            else:
                st.warning(f"⏸ موتور ستاپ اعتبارسنجی‌شده می‌گوید انتظار: {_vp.get('why', '')} · {_vp.get('watch', '')}")
            with st.expander("📐 اعتبار ستاپ‌ها روی همین نماد (walk-forward)", expanded=False):
                st.dataframe(_B.setup_stats_table(_vp["stats"]), use_container_width=True, hide_index=True)
        except Exception as _e:  # noqa: BLE001
            st.caption(f"اعتبارسنجی ستاپ انجام نشد: {_e}")
        fd = S["final_dir"]
        tone = "#16a34a" if fd > 0 else "#ef4444" if fd < 0 else "#94a3b8"
        st.markdown(
            f"<div dir='rtl' style='border:1px solid {tone}66;border-right:6px solid {tone};border-radius:14px;padding:14px 16px;background:{tone}12'>"
            f"<b style='font-size:18px'>{'لانگ 🟢' if fd > 0 else 'شورت 🔴' if fd < 0 else 'خنثی ⚪ — صبر'}</b> · امتیاز اجماع {S['final_s']:+.2f} · اطمینان {S['confidence']}٪ · "
            f"وزن هر ایجنت از عملکرد واقعی‌اش روی همین {len(d)} کندل می‌آید (بازده، PF، وین‌ریت، دراودان).</div>",
            unsafe_allow_html=True)
        render_position(S["final_pos"], dec, tone)

        # master evidence
        master_keys = ["ema_align", "struct", "di_adx", "supertrend", "macd", "roc", "cmf", "money_delta", "obv",
                       "sweep", "brk", "fvg", "bvg", "candle", "z_fade", "rsi_ext"]
        r_last = F.iloc[-1]
        used_by = {k: [n for n, r in results.items() if k in r["spec"]["weights"]] for k in master_keys}
        master = pd.DataFrame([{
            "حوزه": ("جهت بازار" if k in ("ema_align", "struct", "di_adx", "supertrend") else
                     "مومنتوم" if k in ("macd", "roc", "brk") else
                     "جریان پول" if k in ("cmf", "money_delta", "obv") else
                     "نقدینگی" if k == "sweep" else "گپ‌ها (FVG/BVG)" if k in ("fvg", "bvg") else
                     "کندل" if k == "candle" else "بازگشت به میانگین"),
            "فاکتور": FACTOR_FA[k], "مدرک": describe(k, r_last, d.iloc[-1], dec, extras),
            "امتیاز": round(float(np.nan_to_num(r_last[k])), 2), "رأی": _verdict(float(np.nan_to_num(r_last[k]))),
            "استفاده‌کننده": "، ".join(x.split(" ")[0] for x in used_by[k]) or "—",
        } for k in master_keys])
        st.markdown("**جدول مدارک نهایی (همه‌ی ابزارها در یک نگاه)**")
        st.dataframe(master, use_container_width=True, hide_index=True)

        # --- per-agent evidence tables ---------------------------------------------------------
        st.divider()
        st.subheader("🧾 جدول دلیل و پوزیشن هر ایجنت")
        for name, r in results.items():
            col = r["spec"]["color"]
            with st.expander(f"{name} — {r['lean']} · امتیاز {r['score']:+.2f} (آستانه ±{r['spec']['thr']}) · بک‌تست {r['bt']['total']:+.2f}%", expanded=True):
                st.markdown(f"<div dir='rtl' style='color:#94a3b8;font-size:13px;border-right:3px solid {col};padding-right:8px'>{r['spec']['desc']}</div>",
                            unsafe_allow_html=True)
                st.dataframe(pd.DataFrame(r["rows"]), use_container_width=True, hide_index=True)
                contrib = sum(x["سهم در تصمیم"] for x in r["rows"])
                st.caption(f"جمع سهم‌ها = {contrib:+.3f} → {'LONG' if r['sig'] > 0 else 'SHORT' if r['sig'] < 0 else 'FLAT'} "
                           f"(ورود وقتی |امتیاز| > {r['spec']['thr']}، خروج وقتی < {r['spec']['thr'] * 0.4:.2f}) · "
                           f"همین قانون‌ها در بک‌تست کندل‌به‌کندل اعمال شده‌اند.")
                render_position(r["position"], dec, col)

        # --- proof: candles / liquidity / flow / gaps / structure -------------------------------
        st.divider()
        st.subheader("📎 مدارک خام")
        p1, p2 = st.columns(2)
        with p1:
            with st.expander("🕯️ ۱۲ کندل آخر (آناتومی)", expanded=False):
                tail = d.tail(12).copy()
                ftail = F.tail(12)
                cand = pd.DataFrame({
                    "زمان": tail["dt"].astype(str).str[:16] if "dt" in tail.columns else tail.index.astype(str),
                    "باز": tail["open"].round(dec), "بالا": tail["high"].round(dec), "پایین": tail["low"].round(dec), "بسته": tail["close"].round(dec),
                    "رنگ": np.where(tail["close"] >= tail["open"], "🟢", "🔴"),
                    "بدنه٪": ftail["body_pct"].round(0).values, "حجم×میانگین": ftail["vol_ratio"].round(2).values,
                    "الگو": ftail["candle_name"].values, "FVG": ftail["fvg"].round(2).values, "BVG": ftail["bvg"].round(2).values,
                }).iloc[::-1]
                st.dataframe(cand, use_container_width=True, hide_index=True)
            with st.expander("💧 نقدینگی (سوییپ‌ها و استخرها)", expanded=False):
                sw = F[F["sweep_raw"] != 0].tail(8)
                if sw.empty:
                    st.write("در این بازه سوییپ ثبت نشده.")
                else:
                    st.dataframe(pd.DataFrame({
                        "زمان": d.loc[sw.index, "dt"].astype(str).str[:16] if "dt" in d.columns else sw.index.astype(str),
                        "نوع": np.where(sw["sweep_raw"] > 0, "سوییپ کف → صعودی 🟢", "سوییپ سقف → نزولی 🔴"),
                        "قیمت بسته": d.loc[sw.index, "close"].round(dec).values,
                    }).iloc[::-1], use_container_width=True, hide_index=True)
                highs, lows = _swings(d.tail(120).reset_index(drop=True))
                st.write(f"استخر نقدینگی بالا (equal highs): {'بله' if F['eqh'].iloc[-1] else 'خیر'} · "
                         f"پایین (equal lows): {'بله' if F['eql'].iloc[-1] else 'خیر'} · "
                         f"سقف ۲۰ کندل {extras['prior_hi']:,.{dec}f} · کف ۲۰ کندل {extras['prior_lo']:,.{dec}f}")
                lv = pd.DataFrame(
                    [{"نوع": "سقف سوئینگ (نقدینگی خریداران)", "سطح": round(p, dec)} for _, p in highs[-5:]] +
                    [{"نوع": "کف سوئینگ (نقدینگی فروشندگان)", "سطح": round(p, dec)} for _, p in lows[-5:]])
                if not lv.empty:
                    st.dataframe(lv.sort_values("سطح", ascending=False), use_container_width=True, hide_index=True)
        with p2:
            with st.expander("💸 جریان پول (ورود/خروج)", expanded=False):
                rl = F.iloc[-1]
                st.dataframe(pd.DataFrame([
                    {"سنجه": "CMF (۲۰)", "مقدار": f"{float(d['cmf'].iloc[-1]) if 'cmf' in d.columns else 0:+.3f}", "تفسیر": "ورود پول" if rl["cmf"] > 0.1 else "خروج پول" if rl["cmf"] < -0.1 else "خنثی"},
                    {"سنجه": "MFI (۱۴)", "مقدار": f"{float(d['mfi'].iloc[-1]) if 'mfi' in d.columns else 50:.1f}", "تفسیر": "فشار خرید" if rl["mfi_c"] > 0.2 else "فشار فروش" if rl["mfi_c"] < -0.2 else "متعادل"},
                    {"سنجه": "شیب OBV (۱۰)", "مقدار": f"{float(rl['obv']):+.2f}", "تفسیر": "انباشت" if rl["obv"] > 0.1 else "توزیع" if rl["obv"] < -0.1 else "خنثی"},
                    {"سنجه": "دلتای خرید/فروش (۲۰)", "مقدار": f"{float(rl['money_delta']):+.2f}", "تفسیر": "خریدار تهاجمی" if rl["money_delta"] > 0.1 else "فروشنده تهاجمی" if rl["money_delta"] < -0.1 else "متعادل"},
                    {"سنجه": "حجم سبز/قرمز (۲۰)", "مقدار": f"{float(rl['upvol20']):,.0f} / {float(rl['dnvol20']):,.0f}", "تفسیر": "حجم با خریدارهاست" if rl["upvol20"] > rl["dnvol20"] else "حجم با فروشنده‌هاست"},
                    {"سنجه": "حجم کندل آخر", "مقدار": f"{float(rl['vol_ratio']):.2f}× میانگین", "تفسیر": "حجم بالا" if rl["vol_ratio"] > 1.3 else "حجم عادی/کم"},
                ]), use_container_width=True, hide_index=True)
            with st.expander("🧱 زون‌های FVG / BVG فعال", expanded=False):
                if extras.get("gaps") is not None and G is not None:
                    zf = G.zones_frame(extras["gaps"], price, dec)
                    if zf.empty:
                        st.write("زون فعالی نزدیک قیمت نیست.")
                    else:
                        st.dataframe(zf, use_container_width=True, hide_index=True)
                    st.caption(G.GAP_HELP["FVG"] + " · " + G.GAP_HELP["BVG"])
                else:
                    st.write("موتور FVG/BVG در دسترس نیست.")

        # --- price chart with zones, liquidity and final position --------------------------------
        with st.expander("📈 چارت با زون‌ها، سطوح نقدینگی و پوزیشن نهایی", expanded=True):
            dc = d.tail(160).reset_index(drop=True)
            fig2 = go.Figure()
            fig2.add_trace(go.Candlestick(x=dc["dt"] if "dt" in dc.columns else dc.index, open=dc["open"], high=dc["high"], low=dc["low"], close=dc["close"],
                                          increasing_line_color="#26a69a", decreasing_line_color="#ef5350", name="قیمت"))
            for col_name, colr in (("ema20", "#2962ff"), ("ema50", "#ff9800")):
                if col_name in dc.columns:
                    fig2.add_trace(go.Scatter(x=dc["dt"], y=dc[col_name], line=dict(color=colr, width=1.2), name=col_name.upper()))
            if extras.get("gaps") is not None and G is not None:
                shapes, notes = G.plotly_shapes(extras["gaps"], x_end=dc["dt"].iloc[-1], price=price)
                x0 = dc["dt"].iloc[0]
                for s_ in shapes:
                    if s_["x0"] < x0:
                        s_["x0"] = x0
                    fig2.add_shape(**s_)
                for n_ in notes:
                    if n_["x"] >= x0:
                        fig2.add_annotation(**n_)
            fp = S["final_pos"]
            if fp["direction"] != 0:
                fig2.add_hline(y=fp["entry"], line_color="#f59e0b", line_width=1.3, annotation_text="ENTRY", annotation_position="right")
                fig2.add_hline(y=fp["stop"], line_color="#ef4444", line_dash="dash", annotation_text="SL", annotation_position="right")
                for i, (tp, rr, _) in enumerate(fp["targets"]):
                    fig2.add_hline(y=tp, line_color="#22c55e", line_dash="dash", annotation_text=f"TP{i + 1} {rr}R", annotation_position="right")
            fig2.add_hline(y=extras["prior_hi"], line_color="rgba(148,163,184,.6)", line_dash="dot", annotation_text="سقف ۲۰", annotation_position="left")
            fig2.add_hline(y=extras["prior_lo"], line_color="rgba(148,163,184,.6)", line_dash="dot", annotation_text="کف ۲۰", annotation_position="left")
            fig2.update_layout(template="plotly_dark", height=560, xaxis_rangeslider_visible=False, margin=dict(l=10, r=70, t=30, b=10),
                               legend=dict(orientation="h"))
            st.plotly_chart(fig2, use_container_width=True)

        # --- save to community ----------------------------------------------------------------
        st.divider()
        fp = S["final_pos"]
        lines = [f"دوئل ایجنت‌ها روی {S['sym']} ({S['exchange']}/{S['interval']}) · {len(d)} کندل · {S['ts']}",
                 f"پوزیشن اجماعی: {pos_text(fp, dec)} · اطمینان {S['confidence']}٪ · امتیاز {S['final_s']:+.2f}"]
        if fp["direction"] != 0:
            lines.append(f"حد ضرر بر اساس: {fp['sl_reason']} · اهداف: " + " | ".join(f"TP{i + 1} ← {why}" for i, (_, _, why) in enumerate(fp["targets"])))
        lines.append("— ایجنت‌ها —")
        for n, r in results.items():
            lines.append(f"{n}: {r['lean']} (امتیاز {r['score']:+.2f}) · بک‌تست {r['bt']['total']:+.2f}% · {r['bt']['trades']} ترید · وین {r['bt']['win']:.0f}% · PF {r['bt']['pf']:.2f} · DD {r['bt']['dd']:.1f}%")
            top = sorted(r["rows"], key=lambda x: abs(x["سهم در تصمیم"]), reverse=True)[:3]
            lines.append("   دلایل اصلی: " + " | ".join(f"{x['فاکتور']}: {x['مدرک (مشاهده‌ی واقعی)']}" for x in top))
        lines.append("— مدارک کلیدی —")
        for _, m in master.head(10).iterrows():
            lines.append(f"{m['حوزه']} / {m['فاکتور']}: {m['مدرک']} → {m['رأی']}")
        lines.append(f"برنده‌ی بک‌تست: {S['winner']}. این نتیجه بک‌تست + تحلیل قانون‌محور است، نه سیگنال قطعی؛ مدیریت ریسک الزامی است.")
        analysis_text = "\n".join(lines)
        st.text_area("📝 تحلیل کامل (می‌ره تو 👥 تحلیل‌های کاربران)", value=analysis_text, height=260, key="duel_txt")

        if st.button("💾 ذخیره در 👥 تحلیل‌های کاربران", type="primary"):
            bias = "لانگ 🟢" if fp["direction"] > 0 else "شورت 🔴" if fp["direction"] < 0 else "خنثی ⚪"
            tps = [t[0] for t in fp["targets"]] + [None, None, None]
            save_duel({
                "name": f"🤖 اجماع ایجنت‌ها (برنده: {S['winner']})", "symbol": S["sym"].upper(), "exchange": S["exchange"],
                "bias": bias, "tf": S["interval"], "entry": float(fp["entry"]),
                "stop": float(fp["stop"]) if fp["stop"] else None,
                "tp1": float(tps[0]) if tps[0] else None, "tp2": float(tps[1]) if tps[1] else None, "tp3": float(tps[2]) if tps[2] else None,
                "rr": f"1:{fp['rr']}" if fp["rr"] else "",
                "confidence": int(S["confidence"]), "text": st.session_state.get("duel_txt", analysis_text),
                "image": "", "ts": datetime.now().strftime("%Y-%m-%d %H:%M"),
            })
            st.success("ذخیره شد! در صفحه‌ی اصلی → بخش «🧩 تحلیل‌ها» → تب «👥 تحلیل‌های کاربران» ببین.")
