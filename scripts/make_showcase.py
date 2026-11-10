# -*- coding: utf-8 -*-
"""
بسته‌ی ارائه‌ی NorthmanQuant — تصاویرِ تحلیلِ مهرشده با QC 14/14
Generate QC-stamped analysis PNGs for the best real-market setups,
ready to share (Discord / Telegram / anywhere).

Run:  python scripts/make_showcase.py
Out:  /home/z/my-project/download/northmanquant-showcase/*.png + README_FA.txt
"""
import os
import re
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app_base as nq  # noqa: E402

OUT = "/home/z/my-project/download/northmanquant-showcase"
os.makedirs(OUT, exist_ok=True)

# recognized, liquid names first — good for a presentation audience
CANDIDATES = [
    "BTC-USDT", "ETH-USDT", "SOL-USDT", "XRP-USDT", "BNB-USDT",
    "DOGE-USDT", "ADA-USDT", "AVAX-USDT", "LINK-USDT", "TON-USDT",
    "SUI-USDT", "NEAR-USDT", "LTC-USDT", "DOT-USDT",
]
EXCHANGE = "OKX"
INTERVALS = ["1hour", "2hour", "4hour", "1day"]
MAX_IMAGES = 8


def analyse(symbol: str, interval: str):
    """Full engine pipeline + QC gate. Returns dict or None."""
    try:
        df = nq.fetch_candles(EXCHANGE, symbol, interval, limit=500)
        d = nq.add_indicators(df)
        if len(d) < 60:
            return None
        score_s, _ = nq.confluence(d)
        score = float(score_s.iloc[-1])
        lv = nq.swing_levels(d)
        plan = nq.setup_plan(d, lv)
        plan["score"] = score
        plan["fvg_note"] = ""
        try:
            plan["fvg_note"] = nq.fvg_summary(d)["text"]
        except Exception:  # noqa: BLE001
            pass
        price = float(d["close"].iloc[-1])
        dec = 2 if price >= 1000 else 4 if price >= 1 else 6
        qc = plan.get("qc") or {}
        return {
            "symbol": symbol, "interval": interval, "d": d, "plan": plan,
            "levels": lv, "score": score, "dec": dec, "price": price,
            "qc_ok": not qc.get("issues"),
            "active": plan.get("entry") is not None,
            "rr": plan.get("rr") or 0,
        }
    except Exception as exc:  # noqa: BLE001
        print(f"  ! {symbol} {interval}: {type(exc).__name__}: {exc}")
        return None


def render(res) -> bytes:
    return nq.render_analysis_png(
        res["d"], res["plan"], res["levels"], res["score"],
        res["symbol"], EXCHANGE, res["interval"], res["dec"],
    )


def main():
    print(f"== NorthmanQuant showcase — {EXCHANGE} ==")
    results = []
    for interval in INTERVALS:
        print(f"-- {interval} --")
        for sym in CANDIDATES:
            r = analyse(sym, interval)
            if r:
                tag = "ACTIVE" if r["active"] else "wait  "
                qct = "QC 14/14" if r["qc_ok"] else "QC issue"
                print(f"  {sym:<12} {tag} score {r['score']:+5.0f} rr 1:{r['rr']:<4} {qct}")
                if r["qc_ok"]:
                    results.append(r)

    # selection: active setups first (by |score| then R:R), then recognizable names
    actives = sorted([r for r in results if r["active"]],
                     key=lambda r: (abs(r["score"]) + 10 * r["rr"]), reverse=True)
    waits = [r for r in results if not r["active"]]
    btc_eth = [r for r in waits if r["symbol"] in ("BTC-USDT", "ETH-USDT")]
    other_waits = sorted([r for r in waits if r not in btc_eth],
                         key=lambda r: abs(r["score"]), reverse=True)
    picked = actives[:MAX_IMAGES]
    for r in btc_eth + other_waits:
        if len(picked) >= MAX_IMAGES:
            break
        if r not in picked:
            picked.append(r)

    if not picked:
        print("NO QC-PASSING RESULTS — market too unhealthy right now")
        return 1

    # render + save
    saved = []
    for i, r in enumerate(picked, 1):
        png = render(r)
        if not png or len(png) < 5000:
            print(f"  ! skip {r['symbol']} (bad png)")
            continue
        state = "LONG" if str(r["plan"]["direction"]).startswith("لانگ") else \
                "SHORT" if r["plan"]["entry"] is not None else "WAIT"
        fname = f"{i:02d}_{r['symbol'].replace('-','')}_{r['interval']}_{state}.png"
        path = os.path.join(OUT, fname)
        with open(path, "wb") as f:
            f.write(png)
        saved.append((fname, r, len(png)))
        print(f"  saved {fname}  ({len(png):,} bytes)")

    # Persian README for the non-technical user
    lines = [
        "بسته‌ی ارائه‌ی NorthmanQuant — تصاویرِ آماده‌ی اشتراک‌گذاری",
        "=" * 60,
        "",
        "هر تصویر یک تحلیلِ واقعی از بازار است که مستقیم از موتورِ اپ ساخته شده:",
        "· کندل‌های واقعی صرافی OKX (نه تصویرِ تقلبی)",
        "· خطِ نارنجی = نقطه‌ی ورود، خطِ قرمز = حدضرر، خط‌های آبی = سه هدفِ سود",
        "· خطِ سبزِ بالای تصویر = مُهرِ QC 14/14 یعنی ۱۴ بازرسیِ سلامتِ داده و طرح، همه پاس شده",
        "· اگر روی تصویر نوشته WAIT یعنی موتور عمداً معامله نداده چون ستاپِ معتبری نبود —",
        "  این نقطه‌ی قوتِ سیستم است، ضعف نیست.",
        "",
        "این تصاویر را می‌توانید در دیسکورد، تلگرام یا هرجای دیگر بگذارید.",
        "زیرِ هر تصویر برند NorthmanQuant هست و تصویر از داده‌ی زنده ساخته شده،",
        "پس هرگز ادعای دروغ در آن نیست.",
        "",
        "-" * 60,
        "فهرستِ تصاویر:",
        "",
    ]
    for fname, r, _ in saved:
        p = r["plan"]
        if r["active"]:
            d1 = 2 if r["price"] >= 1000 else 4
            line = (f"{fname} — {p['direction']} · ورود {p['entry']:,.{d1}f} · "
                    f"حدضرر {p['stop']:,.{d1}f} · هدفِ اول {p['targets'][0][0]:,.{d1}f} · "
                    f"R:R یک‌به‌{p['rr']} · بردِ TP1 در تست {p['confidence']}٪")
        else:
            line = f"{fname} — ⏸ انتظار (ستاپِ معتبر نبود — محافظتِ QC) · امتیاز {r['score']:+.0f}"
        lines.append(line)
    lines += ["", "-" * 60, "",
              "نکته برای ارائه: بگویید «سیستم من هر سیگنال را قبل از نمایش با ۱۴ بازرسی",
              "اتوماتیک چک می‌کند؛ اگر یکی هم رد شود، سیگنال اصلاً منتشر نمی‌شود و به حالت",
              "انتظار می‌رود.» همین تصاویر مدرکِ آن است.", ""]
    with open(os.path.join(OUT, "README_FA.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    # zip everything (only files referenced by the README — no stale leftovers)
    zpath = "/home/z/my-project/download/NorthmanQuant-Showcase.zip"
    keep = set(re.findall(r"\d{2}_\w+\.png", "\n".join(lines)))
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for fname, _, _ in saved:
            if fname in keep:
                z.write(os.path.join(OUT, fname), arcname=f"northmanquant-showcase/{fname}")
        z.write(os.path.join(OUT, "README_FA.txt"),
                arcname="northmanquant-showcase/README_FA.txt")
    print(f"\nZIP: {zpath}  ({os.path.getsize(zpath):,} bytes)")
    print(f"TOTAL: {len(saved)} images · README_FA.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
