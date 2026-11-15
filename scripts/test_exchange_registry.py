"""
Static registry guard — «هر بخش، همه‌ی صرافی‌ها» (قاعده‌ی پروژه).

Usage (from the repository root):
    python scripts/test_exchange_registry.py

No network, no runtime — pure AST audit of the repository.

Rule enforced:
  The single source of truth for the exchange list is
  core/exchanges/__init__.py (EXCHANGES_ALL = 8 venues). No module may
  hardcode a PARTIAL list of exchange names under an EXCHANGES-like name:
  that is exactly the bug class where a local literal shadows the registry
  import (e.g. `from core.exchanges import EXCHANGES_ALL as EXCHANGES`
  followed later by `EXCHANGES = ["OKX", "KuCoin"]`) and the UI silently
  drops back to 2 venues.

What is scanned:
  app_base.py, every pages/*.py, every core/*.py and core/exchanges/*.

What is flagged:
  A module-level assignment to a name matching /EXCHANGES/ whose value is a
  pure string-literal list/tuple containing at least 2 known exchange names
  but missing at least one of the 8 registry venues.

Allowlisted (documented, intentional subsets):
  - core/exchanges/__init__.py: NATIVE_EXCHANGES / EXTRA_EXCHANGES — the
    registry itself, split by fetch path (native vs CCXT/extras).

Exits non-zero if any violation is found.
"""
import ast
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.exchanges import EXCHANGES_ALL as REGISTRY  # noqa: E402

# نام‌های شناخته‌شده‌ی صرافی (رجیستری + venueهای CCXTِ مجاز برای پسوندِ لیست‌ها)
KNOWN = set(REGISTRY) | {
    "Kraken", "Coinbase", "Gate", "Gateio", "MEXC", "Bitget", "Gemini",
    "Bitstamp", "Bitfinex", "HTX", "Huobi", "Crypto.com", "Cryptocom", "Upbit",
}

NAME_RE = re.compile(r"EXCHANGES")   # EXCHANGES، EXCHANGES_ALL، NATIVE_EXCHANGES، …

# زیرمجموعه‌های عمدی و مستند — فقط داخل خودِ رجیستری
ALLOW = {
    ("core/exchanges/__init__.py", "NATIVE_EXCHANGES"),
    ("core/exchanges/__init__.py", "EXTRA_EXCHANGES"),
}


def _literal_str_list(node) -> list | None:
    """اگر گره، لیست/تاپلِ خالصِ رشته‌ای باشد → عناصرش؛ وگرنه None (فراخوانی/بیانِ دیگر)."""
    if isinstance(node, (ast.List, ast.Tuple)) and node.elts:
        vals = []
        for e in node.elts:
            if isinstance(e, ast.Constant) and isinstance(e.value, str):
                vals.append(e.value)
            else:
                return None
        return vals
    return None


def violations_in(tree: ast.Module, path: str) -> list[tuple[str, str, list, list]]:
    """جستجوی انتساب‌های ماژول‌سطح به نام‌های EXCHANGES-مانند با لیستِ ناقصِ لفظی."""
    out = []
    for node in tree.body:
        targets: list[str] = []
        if isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            targets = [node.target.id]
        for name in targets:
            if not NAME_RE.search(name) or (path, name) in ALLOW:
                continue
            vals = _literal_str_list(node.value)
            if not vals:
                continue
            if sum(1 for v in vals if v in KNOWN) >= 2:
                missing = [r for r in REGISTRY if r not in vals]
                if missing:
                    out.append((path, name, vals, missing))
    return out


def _files() -> list[str]:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    picks = [os.path.join(root, "app_base.py")]
    for d in ("pages", "core", os.path.join("core", "exchanges")):
        full = os.path.join(root, d)
        for f in sorted(os.listdir(full)):
            if f.endswith(".py") and f != "__init__.py":
                picks.append(os.path.join(full, f))
    return picks


def main() -> int:
    # --- خودآزمونِ نگهبان: نمونه‌ی باگِ واقعی باید گرفته شود، نمونه‌ی سالم نباید
    bug = ast.parse('EXCHANGES = ["OKX", "KuCoin"]')
    good = ast.parse("EXCHANGES = list(EXCHANGES_ALL)")
    assert violations_in(bug, "sample.py"), "نگهبان نمونه‌ی باگ را نگرفت!"
    assert not violations_in(good, "sample.py"), "نگهبان نمونه‌ی سالم را خطا گرفت!"
    print("guard self-test: OK (bug pattern caught, registry pattern clean)")

    # --- ممیزیِ کل مخزن
    violations: list[tuple[str, str, list, list]] = []
    for path in _files():
        rel = os.path.relpath(path, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        with open(path, "r", encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        violations.extend((rel, n, v, m) for (rp, n, v, m) in violations_in(tree, rel))

    if violations:
        print(f"FAIL — {len(violations)} لیستِ صرافیِ ناقصِ هاردکد پیدا شد:")
        for path, name, vals, missing in violations:
            print(f"  · {path} :: {name} = {vals}  →  جاافتاده: {missing}")
        print("قاعده: هر بخش باید از core.exchanges.EXCHANGES_ALL بخواند — لیستِ محلیِ ممنوع.")
        return 1

    print(f"PASS — هیچ لیستِ ناقصی نیست؛ رجیستریِ رسمی: {', '.join(REGISTRY)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
