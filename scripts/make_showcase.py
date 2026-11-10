# -*- coding: utf-8 -*-
"""
بسته‌ی ارائه‌ی NorthmanQuant — تصاویرِ تحلیلِ مهرشده با QC 14/14
Generate QC-stamped analysis PNGs for the best real-market setups,
ready to share (Discord / Telegram / anywhere).

منطقِ مشترک با آلبومِ روزانه‌ی تلگرام در core/showcase_daily.py است —
این اسکریپت فقط خروجیِ فایل (PNG + README + ZIP) می‌سازد.

Run:  python scripts/make_showcase.py
Out:  /home/z/my-project/download/northmanquant-showcase/*.png + README_FA.txt
"""
import os
import re
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import showcase_daily as SD  # noqa: E402

OUT = "/home/z/my-project/download/northmanquant-showcase"
os.makedirs(OUT, exist_ok=True)
MAX_IMAGES = SD.MAX_IMAGES


def main():
    print(f"== NorthmanQuant showcase — {SD.EXCHANGE} ==")
    results = SD.collect()
    print(f"  QC-passing results: {len(results)}")
    picked = SD.select(results, MAX_IMAGES)
    if not picked:
        print("NO QC-PASSING RESULTS — market too unhealthy right now")
        return 1

    # render + save
    saved = []
    for i, r in enumerate(picked, 1):
        state = "LONG" if str(r["plan"]["direction"]).startswith("لانگ") else \
                "SHORT" if r["active"] else "WAIT"
        fname = f"{i:02d}_{r['symbol'].replace('-', '')}_{r['interval']}_{state}.png"
        try:
            png = SD.build_album([r])[0][1]
        except Exception as exc:  # noqa: BLE001
            print(f"  ! skip {r['symbol']}: {type(exc).__name__}: {exc}")
            continue
        if not png or len(png) < 5000:
            print(f"  ! skip {r['symbol']} (bad png)")
            continue
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
        lines.append(f"{fname} — {SD.describe_plain(r)}")
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
