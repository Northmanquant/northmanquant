#!/usr/bin/env bash
# احیای محیطِ کرونوس — درسِ سندباکس: بعد از هر recycle، venv وزن‌های سنگین
# (torch و زنجیره‌ی import مدل) را گم می‌کند و بچ‌ها «خاموشِ آفلاین» می‌شوند.
# این اسکریپت idempotent است: اگر زنجیره سالم باشد فقط می‌گوید و تمام.
set -u

cd "$(dirname "$0")/.."   # ریشه‌ی مخزن — مهم نیست از کجا صدا زده شده

echo "🔧 احیای محیط — مرحله‌ی ۱: torch فقط-CPU + زنجیره‌ی importِ مدل"
python -m pip install --quiet --upgrade pip
python -m pip install --quiet torch --index-url https://download.pytorch.org/whl/cpu \
  || { echo "❌ نصبِ torch نشد — اینترنت/میزبان را چک کن"; exit 1; }
python -m pip install --quiet einops huggingface_hub safetensors tqdm

echo "🔧 مرحله‌ی ۲: پیش‌پروازِ زنجیره (بدونِ لودِ وزن)"
python - <<'PY'
import os, sys
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.getcwd(), ".env"), override=False)
except ImportError:
    pass
try:
    import einops, safetensors, torch, tqdm  # noqa: F401
    print("   torch", torch.__version__, "— OK")
    repo = os.environ.get("KRONOS_REPO", "")
    if repo and os.path.isdir(repo):
        sys.path.insert(0, repo)
        import model as _m  # noqa: F401
        print("   پکیجِ رسمیِ کرونوس از", repo, "— OK")
    else:
        print("   ⚠️ KRONOS_REPO ست نیست — مدلِ واقعی لود نمی‌شود (.env را چک کن)")
        sys.exit(2)
except ImportError as e:
    print("   ❌ زنجیره ناقص:", e)
    sys.exit(1)
PY
rc=$?
[ $rc -eq 0 ] && echo "✅ محیط سالم است — بچِ واقعی می‌توانی بگیری" && exit 0
[ $rc -eq 2 ] && echo "ℹ️ torch سالم است؛ فقط KRONOS_REPO/وزن‌ها را ست کن (HF_HOME را هم ببین)" && exit 0
exit 1
