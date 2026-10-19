"""Agents Duel - 3 bots duel + save to community - v2 with Lighter"""
import os
import json
import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="Agents Duel", page_icon="🤖", layout="wide")
st.title("🤖 دوئل ایجنت‌ها — کدوم ربات می‌بره؟")
st.caption("3 ربات روی 1 ارز پوزیشن باز می‌کنن، نتیجه + تحلیل برنده میره توی 👥 تحلیل‌های کاربران")

# دقیق مثل app_base - همه 8 تا صرافی
EXCHANGES = ["KuCoin", "OKX", "Binance", "Bybit", "Lighter", "XT", "LBank", "KCEX"]

COMMUNITY_FILE = "community_analyses.json"

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
    except Exception as e:
        st.warning(f"ذخیره نشد: {e}")

def get_df(exchange, symbol, interval):
    """دیتا از app_base میاد که Lighter و KCEX رو هم بلده"""
    try:
        import app_base as B
        sym = B.normalize_symbol(symbol, exchange)
        df = B.fetch_candles(exchange, sym, interval, 300)
        d = B.add_indicators(df)
        sc, _ = B.confluence(d)
        return d, sc, sym
    except Exception as e:
        st.warning(f"app_base نشد ({e}) — fallback KuCoin")
        import requests
        tfmap = {"15min": "15min", "1hour": "1hour", "4hour": "4hour", "1day": "1day", "1week": "1week"}
        r = requests.get(
            "https://api.kucoin.com/api/v1/market/candles",
            params={"symbol": symbol.replace("/", "-").upper(), "type": tfmap.get(interval, "1hour")},
            timeout=20
        ).json()
        rows = [
            {"time": int(x[0]) * 1000, "open": float(x[1]), "close": float(x[2]),
             "high": float(x[3]), "low": float(x[4]), "volume": float(x[5])}
            for x in (r.get("data") or [])
        ]
        df = pd.DataFrame(rows).sort_values("time").reset_index(drop=True)
        df["dt"] = pd.to_datetime(df["time"], unit="ms", utc=True)
        df["ema50"] = df["close"].ewm(span=50).mean()
        sc = pd.Series(np.where(df["close"] > df["ema50"], 50, -50))
        return df, sc, symbol

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
    d, score, sym_used = get_df(exchange, symbol, interval)
    st.caption(f"دیتا: {sym_used} روی {exchange} - {len(d)} کندل")
    close = d["close"].to_numpy()

    sig_trend = np.sign((d["close"] - d["ema50"]).fillna(0).to_numpy())
    mom = d["close"].diff(10).fillna(0).to_numpy()
    sig_mom = np.where(mom > 0, 1, np.where(mom < 0, -1, 0))
    sma20 = d["close"].rolling(20).mean()
    std20 = d["close"].rolling(20).std().fillna(1)
    z = (d["close"] - sma20) / std20
    sig_mr = np.where(z < -1, 1, np.where(z > 1, -1, 0))

    agents = {"Trend Rider📊": sig_trend, "Momentum🧠": sig_mom, "MeanRev🎯": sig_mr}
    rets = np.zeros(len(close))
    rets[1:] = (close[1:] - close[:-1]) / close[:-1]

    results = []
    import plotly.graph_objects as go
    fig = go.Figure()
    for name, sig in agents.items():
        strat = np.zeros(len(close))
        strat[1:] = sig[:-1] * rets[1:]
        strat = strat - (np.abs(np.diff(sig, prepend=0)) > 0) * 0.0006
        eq = np.cumprod(1 + strat) * balance
        total = (eq[-1] / balance - 1) * 100
        wins = (strat > 0).sum()
        losses = (strat < 0).sum()
        winrate = wins / max(1, wins + losses) * 100
        trades = int((np.abs(np.diff(sig)) > 0).sum())
        peak = np.maximum.accumulate(eq)
        dd = float(((peak - eq) / peak).max() * 100)
        state = "LONG" if sig[-1] > 0 else "SHORT" if sig[-1] < 0 else "FLAT"
        results.append({"name": name, "total": total, "eq": eq, "trades": trades, "win": winrate, "dd": dd, "state": state, "last_sig": sig[-1]})
        fig.add_trace(go.Scatter(y=eq, mode="lines", name=f"{name} ({total:+.2f}%)"))

    fig.update_layout(template="plotly_dark", height=420, title="Equity — موجودی هر ربات")
    st.plotly_chart(fig, use_container_width=True)

    dfres = pd.DataFrame([
        {"ربات": r["name"], "بازده%": round(r["total"], 2), "معاملات": r["trades"],
         "وین%": round(r["win"], 1), "DD%": round(r["dd"], 2), "پوزیشن": r["state"]}
        for r in results
    ]).sort_values("بازده%", ascending=False)
    st.dataframe(dfres, use_container_width=True, hide_index=True)

    winner = max(results, key=lambda x: x["total"])
    st.success(f"🏆 برنده: {winner['name']} با {winner['total']:+.2f}% — {winner['trades']} معامله — وین {winner['win']:.0f}%")

    bias = "لانگ 🟢" if winner["last_sig"] > 0 else "شورت 🔴" if winner["last_sig"] < 0 else "خنثی ⚪"
    analysis_text = (
        f"دوئل روی {sym_used} ({exchange}/{interval})\n"
        + "\n".join([f"{r['name']}: {r['total']:+.2f}% | {r['trades']} ترید | DD {r['dd']:.1f}%" for r in results])
        + f"\nبرنده {winner['name']} چون روی روند واقعی سوار شد. این نتیجه بک‌تست است نه سیگنال قطعی."
    )
    st.text_area("📝 تحلیل برنده (می‌ره تو تحلیل کاربران)", value=analysis_text, height=120, key="duel_txt")

    if st.button("💾 ذخیره در 👥 تحلیل‌های کاربران"):
        from datetime import datetime
        save_duel({
            "name": f"🤖 {winner['name']}", "symbol": sym_used.upper(), "exchange": exchange,
            "bias": bias, "tf": interval, "entry": float(close[-1]),
            "stop": None, "tp1": None, "tp2": None, "tp3": None, "rr": "",
            "confidence": 70, "text": st.session_state.get("duel_txt", analysis_text),
            "image": "", "ts": datetime.now().strftime("%Y-%m-%d %H:%M")
        })
        st.success("ذخیره شد! برو بخش 👥 تحلیل‌های کاربران تو صفحه اصلی ببین.")
