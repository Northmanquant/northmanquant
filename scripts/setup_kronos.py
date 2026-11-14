# -*- coding: utf-8 -*-
"""scripts/setup_kronos.py — برپاییِ یک‌باره‌ی مدلِ واقعیِ کرونوس برای شاهدِ ششم
================================================================================
چهار کار می‌کند (هر کدام idempotent — اجرای دوباره بی‌ضرر است):
  ۱. وابستگی‌ها را چک می‌کند: torch (CPU کافی است)، einops، huggingface_hub
  ۲. مخزنِ رسمیِ کرونوس را کلون می‌کند (پکیجِ pip نیست — شاملِ ماژولِ model/)
  ۳. وزن‌های مدل و توکنایزر را از HF Hub می‌گیرد (Kronos-mini ≈ ۱۶ مگابایت)
  ۴. envهای لازم را در .envِ پروژه می‌نویسد و یک جلسه‌ی آزمایشی می‌گیرد

اجرا:
  python scripts/setup_kronos.py                # چک + کلون + دانلود + تست
  python scripts/setup_kronos.py --install      # وابستگیِ جاافتاده را خودش نصب می‌کند
  python scripts/setup_kronos.py --model NeoQuasar/Kronos-small   # مدلِ بزرگ‌تر
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

OFFICIAL_REPO = "https://github.com/shiyu-coder/Kronos"
TORCH_CPU_INDEX = "https://download.pytorch.org/whl/cpu"
MODEL_PAIR = {
    "NeoQuasar/Kronos-mini": "NeoQuasar/Kronos-Tokenizer-2k",
    "NeoQuasar/Kronos-small": "NeoQuasar/Kronos-Tokenizer-base",
    "NeoQuasar/Kronos-base": "NeoQuasar/Kronos-Tokenizer-base",
}


def step(title: str) -> None:
    print(f"\n== {title} ==")


def check_deps(install: bool) -> None:
    step("۱/۴ وابستگی‌ها")
    missing: list[str] = []
    for mod in ("torch", "einops", "huggingface_hub"):
        try:
            __import__(mod)
            print(f"  ✅ {mod}")
        except ImportError:
            missing.append(mod)
    if missing and not install:
        print(f"  ⚠️ نصب نیست: {', '.join(missing)}")
        print("     خودت نصب کن یا همین اسکریپت را با --install اجرا کن:")
        print(f"       pip install {' '.join(missing) if 'torch' not in missing else ''}")
        print(f"       pip install torch --index-url {TORCH_CPU_INDEX}")
        sys.exit(1)
    if missing:
        for mod in missing:
            if mod == "torch":
                subprocess.check_call([sys.executable, "-m", "pip", "install",
                                       "torch", "--index-url", TORCH_CPU_INDEX])
            else:
                subprocess.check_call([sys.executable, "-m", "pip", "install", mod])
            print(f"  ✅ نصب شد: {mod}")


def clone_repo(target: str) -> str:
    step("۲/۴ مخزنِ رسمیِ کرونوس")
    if os.path.isdir(os.path.join(target, "model")):
        print(f"  ✅ از قبل هست: {target}")
        return target
    os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
    subprocess.check_call(["git", "clone", "--depth", "1", OFFICIAL_REPO, target])
    print(f"  ✅ کلون شد: {target}")
    return target


def download_weights(model_id: str) -> None:
    step("۳/۴ وزن‌ها از HF Hub")
    from huggingface_hub import snapshot_download
    for repo in (MODEL_PAIR[model_id], model_id):
        p = snapshot_download(repo)
        print(f"  ✅ {repo}")


def write_env(repo_dir: str) -> None:
    step("۴/۴ envِ پروژه")
    env_path = os.path.join(ROOT, ".env")
    lines, seen = [], set()
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            lines = f.read().splitlines()
        seen = {ln.split("=", 1)[0].strip() for ln in lines if "=" in ln}
    want = {"KRONOS_BACKEND": "kronos", "KRONOS_REPO": repo_dir}
    added = False
    with open(env_path, "a", encoding="utf-8") as f:
        for k, v in want.items():
            if k not in seen:
                f.write(f"{k}={v}\n")
                print(f"  ✅ {k}={v}")
                added = True
            else:
                print(f"  ⏭ {k} از قبل ست است")
    if not added:
        print("  (چیزی اضافه نشد)")


def smoke_test(model_id: str) -> None:
    import numpy as np
    import pandas as pd
    from core import kronos_witness as KW

    t = np.arange(400, dtype=float)
    close = 64000.0 * (1.0 + 0.0004 * t + 0.02 * np.sin(t / 12.0))
    open_ = np.roll(close, 1)
    ms = pd.date_range("2026-11-01", periods=400, freq="1h")
    d = pd.DataFrame({"time": (ms.astype("int64") // 10**9) * 1000,
                      "open": open_, "high": np.maximum(open_, close) * 1.004,
                      "low": np.minimum(open_, close) * 0.996, "close": close,
                      "volume": 1000.0, "dt": ms})
    w = KW.witness(d, 2, backend="kronos")
    pred = w["pred"]
    if pred.get("backend") == "kronos" and pred.get("predicting"):
        print(f"\n🎉 جلسه‌ی آزمایشی با مدلِ واقعی: {pred['agree_pct']}٪ مسیرها هم‌جهت · "
              f"باندِ {pred['p5']:.2f}–{pred['p95']:.2f}")
    else:
        print(f"\n⚠️ مسیرِ واقعی فعال نشد: {pred.get('note_fa')}")
        sys.exit(1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--install", action="store_true", help="وابستگیِ جاافتاده را خودش نصب کند")
    ap.add_argument("--model", default="NeoQuasar/Kronos-mini", choices=list(MODEL_PAIR))
    ap.add_argument("--repo-dir", default=os.path.join(os.path.expanduser("~"), "Kronos"),
                    help="مسیرِ کلونِ مخزنِ رسمی (پیش‌فرض: ~/Kronos)")
    args = ap.parse_args()
    check_deps(args.install)
    repo_dir = clone_repo(args.repo_dir)
    download_weights(args.model)
    write_env(repo_dir)
    os.environ.setdefault("KRONOS_REPO", repo_dir)
    smoke_test(args.model)
    print("\n== تمام شد — حالا صفحه‌ی «اتاق تیم» شاهدِ واقعی دارد؛ "
          "برای جمع شدنِ دروازه: python scripts/kronos_session.py ==")
