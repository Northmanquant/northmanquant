"""Agents Duel - v3: evidence-based duel.

4 agents run a backtest on the same coin AND then take a final position that is
fully justified by real evidence: candles, market structure, trend, liquidity
(sweeps / pools / equal highs-lows), money flow in/out (CMF / MFI / OBV / volume),
momentum, FVG / BVG and support/resistance. Every agent gets its own evidence
table + structural entry / stop / 3 targets. The best (consensus) position can be
saved to 👥 تحلیل‌های کاربران.
"""
import json
import os
from datetime import datetime

import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Agents Duel", page_icon="🤖", layout="wide")
st.title("🤖 دوئل ایجنت‌ها — کدوم ربات می‌بره؟")
st.caption("۴ ربات روی ۱ ارز بک‌تست می‌شوند و بعد هرکدام بر اساس **مدرک واقعی** (کندل‌ها، ساختار و جهت بازار، "
           "نقدینگی، ورود/خروج پول، مومنتوم، FVG/BVG و سطوح) پوزیشن نهایی می‌دهد — بدون حدس.")

# دقیق مثل app_base - همه 8 تا صرافی
EXCHANGES = ["KuCoin", "OKX", "Binance", "Bybit", "Lighter", "XT", "LBank", "KCEX"]
COMMUNITY_FILE = "community_analyses.json"
POS_FA = {"LONG": "لانگ 🟢", "SHORT": "شورت 🔴", "FLAT": "خنثی ⚪ (بدون پوزیشن)"}
POS_COL = {"LONG": "#16a34a", "SHORT": "#ef4444", "FLAT": "#94a3b8"}


def save_duel(entry):
    rows = []
    if os.path.exists(COMMUNITY_FILE):
        try:
            with open(COMMUNITY_FILE, "r", encoding="utf-8") as f:
                rows = json.load(f)
        except Exception:
            rows = []
    rows.insert(0, entry)
    rows = rows[:200]
    try:
        with open(COMMUNITY_FILE, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False)
        return True
    except Exception as e:
        st.warning(f"ذخیره نشد: {e}")
        return False


def get_df(exchange, symbol, interval):
    """دیتا از app_base میاد که Lighter و KCEX رو هم بلده (با FVG/BVG و همه اندیکاتورها)"""
    import app_base as B
    sym = B.normalize_symbol(symbol, exchange)
    df = B.fetch_candles(exchange, sym, interval, 500)
    d = B.add_indicators(df)
    sc, comp = B.confluence(d)
    return B, d, sc, comp, sym


def rule_signals(d):
    """Per-bar rule of each agent (used for the backtest track record)."""
    c = d["close"]
    sig_trend = np.sign((c - d["ema50"]).fillna(0).to_numpy())
    mom = c.diff(10).fillna(0).to_numpy()
    sig_mom = np.where(mom > 0, 1, np.where(mom < 0, -1, 0))
    sma20 = c.rolling(20).mean()
    std20 = c.rolling(20).std().replace(0, np.nan)
    z = ((c - sma20) / std20).fillna(0)
    sig_mr = np.where(z < -1, 1, np.where(z > 1, -1, 0))
    fvg = d.get("fvg_score", pd.Series(0.0, index=d.index)).fillna(0)
    bvg = d.get("bvg_score", pd.Series(0.0, index=d.index)).fillna(0)
    cmf = (d["cmf"].fillna(0) * 3).clip(-1, 1)
    sm = (fvg * 0.5 + bvg * 0.3 + cmf * 0.2).to_numpy()
    sig_sm = np.where(sm > 0.1, 1, np.where(sm < -0.1, -1, 0))
    return {"Trend Rider📊": sig_trend, "Momentum🧠": sig_mom, "MeanRev🎯": sig_mr, "Smart Money💧": sig_sm}


def backtest(sig, close, balance, fee=0.0006):
    rets = np.zeros(len(close))
    rets[1:] = (close[1:] - close[:-1]) / close[:-1]
    strat = np.zeros(len(close))
    strat[1:] = sig[:-1] * rets[1:]
    strat = strat - (np.abs(np.diff(sig, prepend=0)) > 0) * fee
    eq = np.cumprod(1 + strat) * balance
    total = (eq[-1] / balance - 1) * 100
    wins, losses = (strat > 0).sum(), (strat < 0).sum()
    peak = np.maximum.accumulate(eq)
    return {"eq": eq, "total": float(total), "win": float(wins / max(1, wins + losses) * 100),
            "trades": int((np.abs(np.diff(sig)) > 0).sum()), "dd": float(((peak - eq) / peak).max() * 100),
            "rule_state": "LONG" if sig[-1] > 0 else "SHORT" if sig[-1] < 0 else "FLAT"}


def fmt(v, dec):
    return "—" if v is None else f"{v:,.{dec}f}"


def narrative(name, dec_, plan, dec):
    """Human-readable reasoning built ONLY from the evidence rows."""
    s = dec_["score"]
    rows = [r for r in dec_["rows"] if r["w"] > 0 and abs(r["contrib"]) > 1e-9]
    sup = sorted([r for r in rows if (r["contrib"] > 0) == (s > 0)], key=lambda r: -abs(r["contrib"]))[:4]
    opp = sorted([r for r in rows if (r["contrib"] > 0) != (s > 0)], key=lambda r: -abs(r["contrib"]))[:3]
    out = [f"تصمیم {name}: {POS_FA[dec_['position']]} · اطمینان {dec_['confidence']}% · امتیاز شواهد {s:+.2f} "
           f"· هم‌راستایی شواهد {dec_['agree'] * 100:.0f}%"]
    if dec_["position"] == "FLAT":
        out.append("دلیل خنثی ماندن: شواهد صعودی و نزولی تقریباً هم‌وزن‌اند؛ ورود بدون لبه‌ی آماری توصیه نمی‌شود.")
        out.append(plan.get("entry_why", ""))
    if sup:
        out.append("دلایل اصلی: " + " ؛ ".join(f"{r['tool']} ({r['value']}) ← {r['reading']}" for r in sup))
    if opp:
        out.append("شواهد مخالف / ریسک: " + " ؛ ".join(f"{r['tool']} ({r['value']}) ← {r['reading']}" for r in opp))
    if plan.get("entry") is not None:
        out.append(f"ورود {fmt(plan['entry'], dec)} ({plan['entry_why']}) · حد ضرر {fmt(plan['stop'], dec)} ({plan['stop_why']})")
        out.append(" · ".join(f"TP{i + 1} {fmt(t[0], dec)} ({t[1]})" for i, t in enumerate(plan["tps"]))
                   + f" · R:R تا TP1 = 1:{plan['rr']}")
    return out


def plan_table(plan, price, dec):
    if plan.get("entry") is None:
        return pd.DataFrame([{"مورد": "وضعیت", "قیمت": "—", "فاصله از قیمت%": "—", "دلیل / مدرک": plan.get("entry_why", "")}])
    rows = [{"مورد": "ورود", "قیمت": fmt(plan["entry"], dec),
             "فاصله از قیمت%": round((plan["entry"] - price) / price * 100, 2), "دلیل / مدرک": plan["entry_why"]},
            {"مورد": "حد ضرر", "قیمت": fmt(plan["stop"], dec),
             "فاصله از قیمت%": round((plan["stop"] - price) / price * 100, 2), "دلیل / مدرک": plan["stop_why"]}]
    risk = abs(plan["entry"] - plan["stop"]) or 1e-12
    for i, (tp, why) in enumerate(plan["tps"]):
        rows.append({"مورد": f"TP{i + 1} ({abs(tp - plan['entry']) / risk:.1f}R)", "قیمت": fmt(tp, dec),
                     "فاصله از قیمت%": round((tp - price) / price * 100, 2), "دلیل / مدرک": why})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ inputs
c1, c2, c3, c4 = st.columns(4)
with c1:
    symbol = st.text_input("ارز", value="BTC-USDT", help="برای Lighter فقط BTC بنویس (بدون USDT)")
with c2:
    exchange = st.selectbox("صرافی", EXCHANGES, index=0)
with c3:
    interval = st.selectbox("تایم‌فریم", ["15min", "1hour", "4hour", "1day"], index=1)
with c4:
    balance = st.number_input("بالانس شروع", value=10000)

if exchange == "Lighter":
    st.info("Lighter پرپ هست - مثلا BTC یا ETH بنویس، نه BTC-USDT")

if st.button("🚀 شروع دوئل", type="primary"):
    try:
        with st.spinner("در حال دریافت داده، بک‌تست و جمع‌آوری مدارک…"):
            B, d, score, comp, sym_used = get_df(exchange, symbol, interval)
            close = d["close"].to_numpy()
            evidence, ctx = B.market_evidence(d)
            results = []
            for name, sig in rule_signals(d).items():
                bt = backtest(np.asarray(sig, dtype=float), close, balance)
                persona = B.AGENT_PERSONAS[name]
                dec_ = B.agent_decision(evidence, persona["w"])
                plan = B.structured_plan(dec_["position"], ctx, style=persona.get("style", "fvg"))
                results.append({"name": name, "desc": persona["desc"], "w": persona["w"], "style": persona.get("style", "fvg"), **bt,
                                "decision": dec_, "plan": plan})
            # consensus: weight each agent's evidence-weights by its backtest quality
            perf = {r["name"]: float(np.clip(1 + r["total"] / 20, 0.3, 2.0) * (0.5 + r["win"] / 100)) for r in results}
            tot = sum(perf.values()) or 1.0
            cats = set().union(*[r["w"].keys() for r in results])
            w_cons = {c: sum(perf[r["name"]] * r["w"].get(c, 0) for r in results) / tot for c in cats}
            final_dec = B.agent_decision(evidence, w_cons, flat_band=0.1)
            final_plan = B.structured_plan(final_dec["position"], ctx)
            st.session_state["duel_res"] = {
                "sym": sym_used, "exchange": exchange, "interval": interval, "balance": balance,
                "d": d, "score": float(score.iloc[-1]), "evidence": evidence, "ctx": ctx,
                "results": results, "perf": perf, "w_cons": w_cons,
                "final_dec": final_dec, "final_plan": final_plan,
                "ts": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }
            st.session_state.pop("duel_saved", None)
    except Exception as e:  # noqa: BLE001
        st.error(f"دوئل انجام نشد: {e}")
        st.info("نماد را مثل BTC-USDT بنویس؛ اگر صرافی مسدود است KuCoin یا OKX را امتحان کن.")

res = st.session_state.get("duel_res")
if not res:
    st.info("ارز، صرافی و تایم‌فریم را انتخاب کن و «🚀 شروع دوئل» را بزن.")
    st.stop()

import app_base as B  # noqa: E402
import plotly.graph_objects as go  # noqa: E402

d, ctx, results = res["d"], res["ctx"], res["results"]
price, dec = ctx["price"], ctx["dec"]
st.caption(f"دیتا: {res['sym']} روی {res['exchange']} · {res['interval']} · {len(d)} کندل · {res['ts']} · "
           f"قیمت فعلی {fmt(price, dec)} · ATR {fmt(ctx['atr'], dec)} · همگرایی {res['score']:+.0f}")

# ------------------------------------------------------------------ 1) equity race
fig = go.Figure()
for r in results:
    fig.add_trace(go.Scatter(y=r["eq"], mode="lines", name=f"{r['name']} ({r['total']:+.2f}%)"))
fig.update_layout(template="plotly_dark", height=380, title="Equity — موجودی هر ربات (بک‌تست قانون هر ایجنت)",
                  margin=dict(l=8, r=8, t=40, b=8))
st.plotly_chart(fig, use_container_width=True)

# ------------------------------------------------------------------ 2) scoreboard
winner = max(results, key=lambda x: x["total"])
board = []
for r in results:
    p, dc = r["plan"], r["decision"]
    tps = [t[0] for t in p.get("tps", [])] + [None, None, None]
    board.append({
        "ربات": r["name"], "بازده بک‌تست%": round(r["total"], 2), "معاملات": r["trades"], "وین%": round(r["win"], 1),
        "DD%": round(r["dd"], 2), "پوزیشن نهایی (با مدرک)": POS_FA[dc["position"]], "اطمینان%": dc["confidence"],
        "ورود": fmt(p.get("entry"), dec), "حد ضرر": fmt(p.get("stop"), dec),
        "TP1": fmt(tps[0], dec), "TP2": fmt(tps[1], dec), "TP3": fmt(tps[2], dec),
        "R:R": f"1:{p['rr']}" if p.get("rr") else "—",
    })
st.subheader("🏁 جدول نتایج دوئل")
st.dataframe(pd.DataFrame(board).sort_values("بازده بک‌تست%", ascending=False), use_container_width=True, hide_index=True)
st.success(f"🏆 برنده‌ی بک‌تست: {winner['name']} با {winner['total']:+.2f}% — {winner['trades']} معامله — وین {winner['win']:.0f}% "
           f"· پوزیشن نهایی‌اش: {POS_FA[winner['decision']['position']]}")

# ------------------------------------------------------------------ 3) best (consensus) position
fd, fp = res["final_dec"], res["final_plan"]
st.subheader("🎯 بهترین پوزیشن نهایی — اجماع وزنی ایجنت‌ها")
st.caption("وزن هر ایجنت = کیفیت بک‌تست (بازده و وین‌ریت). وزن دسته‌های مدرک از ترکیب وزنی ایجنت‌ها ساخته می‌شود.")
m1, m2, m3, m4 = st.columns(4)
m1.metric("جهت", POS_FA[fd["position"]])
m2.metric("اطمینان", f"{fd['confidence']}%", f"امتیاز {fd['score']:+.2f}")
m3.metric("ورود", fmt(fp.get("entry"), dec))
m4.metric("حد ضرر", fmt(fp.get("stop"), dec), (f"ریسک {fp['risk_pct']:.2f}%" if fp.get("risk_pct") else None))
if fp.get("tps"):
    tc = st.columns(3)
    risk = abs(fp["entry"] - fp["stop"]) or 1e-12
    for i, (tp, why) in enumerate(fp["tps"]):
        tc[i].metric(f"TP{i + 1} · {abs(tp - fp['entry']) / risk:.1f}R", fmt(tp, dec), why, delta_color="off")
for line in narrative("اجماع", fd, fp, dec):
    if line:
        st.markdown(f"<div dir='rtl' style='line-height:2'>• {line}</div>", unsafe_allow_html=True)
st.markdown("**📐 جدول دلیل سطوح پوزیشن**")
st.dataframe(plan_table(fp, price, dec), use_container_width=True, hide_index=True)

# chart: candles + FVG/BVG + final plan lines
dc_ = d.tail(140)
cf = go.Figure(go.Candlestick(x=dc_["dt"], open=dc_["open"], high=dc_["high"], low=dc_["low"], close=dc_["close"],
                              increasing_line_color="#26a69a", decreasing_line_color="#ef5350", name="قیمت"))
fz = ctx["fvg"]
x_last, x_first = dc_["dt"].iloc[-1], dc_["dt"].iloc[0]
for z, fc, tag in ([(z, "rgba(38,166,154,0.18)", "FVG▲") for z in fz["bulls"][:4]]
                   + [(z, "rgba(239,83,80,0.18)", "FVG▼") for z in fz["bears"][:4]]
                   + [(b, "rgba(168,85,247,0.22)", "BVG") for b in fz["bvgs"][:3]]):
    x0 = z["dt"] if z["dt"] >= x_first else x_first
    cf.add_shape(type="rect", x0=x0, x1=x_last, y0=z["bottom"], y1=z["top"], fillcolor=fc, line_width=0, layer="below")
    cf.add_annotation(x=x0, y=z["top"], text=tag, showarrow=False, xanchor="left", yanchor="bottom", font=dict(size=9))
if fp.get("entry") is not None:
    for yv, col, nm in ([(fp["entry"], "#f59e0b", "ENTRY"), (fp["stop"], "#ef4444", "SL")]
                        + [(t[0], "#38bdf8", f"TP{i + 1}") for i, t in enumerate(fp["tps"])]):
        cf.add_hline(y=yv, line_color=col, line_dash="dash", annotation_text=f"{nm} {yv:,.{dec}f}",
                     annotation_position="right")
for p in ctx["bsl"][:2]:
    cf.add_hline(y=p, line_color="rgba(250,204,21,.5)", line_dash="dot", annotation_text="BSL", annotation_position="left")
for p in ctx["ssl"][:2]:
    cf.add_hline(y=p, line_color="rgba(250,204,21,.5)", line_dash="dot", annotation_text="SSL", annotation_position="left")
cf.update_layout(template="plotly_dark", height=520, xaxis_rangeslider_visible=False, margin=dict(l=8, r=90, t=30, b=8),
                 title="چارت مدرک: FVG/BVG · نقدینگی (BSL/SSL) · سطوح پوزیشن نهایی")
st.plotly_chart(cf, use_container_width=True)

# ------------------------------------------------------------------ 4) per-agent full reasoning
st.subheader("🧾 تحلیل کامل هر ایجنت — مدرک، دلیل و پوزیشن")
tabs = st.tabs([f"{r['name']} · {POS_FA[r['decision']['position']].split(' (')[0]}" for r in results])
for tab, r in zip(tabs, results):
    with tab:
        dc, p = r["decision"], r["plan"]
        col = POS_COL[dc["position"]]
        st.markdown(
            f"<div dir='rtl' style='border-right:5px solid {col};padding:10px 14px;border-radius:12px;"
            f"background:rgba(148,163,184,.06)'><b style='font-size:17px'>{r['name']}</b> — {r['desc']}<br>"
            f"<span style='color:{col};font-weight:800'>{POS_FA[dc['position']]}</span> · اطمینان {dc['confidence']}% · "
            f"امتیاز شواهد {dc['score']:+.2f} · بک‌تست {r['total']:+.2f}% (وین {r['win']:.0f}% · DD {r['dd']:.1f}% · "
            f"{r['trades']} معامله) · سیگنال قانون بک‌تست الان: {r['rule_state']}</div>",
            unsafe_allow_html=True,
        )
        for line in narrative(r["name"], dc, p, dec):
            if line:
                st.markdown(f"<div dir='rtl' style='line-height:2'>• {line}</div>", unsafe_allow_html=True)
        st.markdown("**📊 جدول مدارک و سهم هرکدام در تصمیم**")
        st.dataframe(B.evidence_table(dc["rows"]), use_container_width=True, hide_index=True)
        # category summary
        cat_rows = []
        for cat in B.EV_CATS:
            rr = [x for x in dc["rows"] if x["cat"] == cat]
            if not rr:
                continue
            s = sum(x["contrib"] for x in rr)
            cat_rows.append({"دسته": cat, "وزن ایجنت": r["w"].get(cat, 0), "تعداد مدرک": len(rr),
                             "برآیند": "🟢 صعودی" if s > 0.05 else "🔴 نزولی" if s < -0.05 else "⚪ خنثی",
                             "سهم%": round(sum(x["share"] for x in rr), 1)})
        st.markdown("**🧭 خلاصه‌ی دسته‌ها**")
        st.dataframe(pd.DataFrame(cat_rows), use_container_width=True, hide_index=True)
        st.markdown("**📐 دلیل ورود / حد ضرر / اهداف**")
        st.dataframe(plan_table(p, price, dec), use_container_width=True, hide_index=True)

# ------------------------------------------------------------------ 5) save to community
bias = {"LONG": "لانگ 🟢", "SHORT": "شورت 🔴", "FLAT": "خنثی ⚪"}[fd["position"]]
analysis_text = (
    f"دوئل ایجنت‌ها روی {res['sym']} ({res['exchange']}/{res['interval']}) · قیمت {fmt(price, dec)}\n"
    + "\n".join(f"{r['name']}: بک‌تست {r['total']:+.2f}% | {r['trades']} ترید | DD {r['dd']:.1f}% | "
                f"پوزیشن {POS_FA[r['decision']['position']]} ({r['decision']['confidence']}%)" for r in results)
    + "\n\n— بهترین پوزیشن (اجماع) —\n"
    + "\n".join(x for x in narrative("اجماع", fd, fp, dec) if x)
    + "\n\nاین نتیجه تحلیلی/بک‌تست است و توصیه‌ی سرمایه‌گذاری نیست."
)
st.text_area("📝 تحلیل نهایی (می‌ره تو تحلیل کاربران)", value=analysis_text, height=260, key="duel_txt")

if st.button("💾 ذخیره در 👥 تحلیل‌های کاربران", type="primary"):
    tps = [t[0] for t in fp.get("tps", [])] + [None, None, None]
    ok = save_duel({
        "name": "🤖 دوئل ایجنت‌ها (اجماع)", "symbol": res["sym"].upper(), "exchange": res["exchange"],
        "bias": bias, "tf": res["interval"],
        "entry": fp.get("entry") if fp.get("entry") is not None else float(price),
        "stop": fp.get("stop"), "tp1": tps[0], "tp2": tps[1], "tp3": tps[2],
        "rr": f"1:{fp['rr']}" if fp.get("rr") else "",
        "confidence": fd["confidence"], "text": st.session_state.get("duel_txt", analysis_text),
        "image": "", "ts": datetime.now().strftime("%Y-%m-%d %H:%M"),
    })
    if ok:
        st.session_state["duel_saved"] = True
if st.session_state.get("duel_saved"):
    st.success("ذخیره شد! برو صفحه اصلی → بخش «🧑‍💻 تحلیل‌ها» → تب «👥 تحلیل‌های کاربران».")
