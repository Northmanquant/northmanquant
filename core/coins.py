# -*- coding: utf-8 -*-
"""core/coins.py — نام کامل ارزها و نمادِ نمایشی
================================================
رکوردهای میدان فقط «نماد صرافی» را دارند (مثل BTC-USDT یا BTCUSDT)؛ برای
پیام‌های تلگرام نامِ خوانا (فارسی + انگلیسی) و جفت‌نماد تمیز (BTC/USDT)
می‌سازیم تا کاربر بداند «از کدام صرافی، چه ارزی، با چه نمادی».

طراحی:
  • فهرست استاتیک و سبک — بدون شبکه؛ برای ارز ناشناخته فقط جفت‌نماد تمیز
    برمی‌گردد (هیچ‌وقت خراب نمی‌شود).
  • سه شکل نماد را می‌فهمد: «BTC-USDT» (KuCoin/OKX)، «BTC/USDT»،
    «BTCUSDT» (Binance — بدون جداکننده).
"""
from __future__ import annotations

# پسوندهای ارز مبنای معامله (با طول بیشتر اول — تا USDT قبل از USDC و ...)
_QUOTES = ("USDT", "USDC", "FDUSD", "TUSD", "DAI", "BTC", "ETH")

# نماد پایه → (فارسی، انگلیسی) — ارزهای رایج صرافی‌ها
NAMES: dict[str, tuple[str, str]] = {
    "BTC": ("بیت‌کوین", "Bitcoin"),
    "ETH": ("اتریوم", "Ethereum"),
    "SOL": ("سولانا", "Solana"),
    "BNB": ("بی‌ان‌بی", "BNB"),
    "XRP": ("ریپل", "XRP"),
    "DOGE": ("دوج‌کوین", "Dogecoin"),
    "ADA": ("کاردانو", "Cardano"),
    "AVAX": ("آوالانچ", "Avalanche"),
    "DOT": ("پولکادات", "Polkadot"),
    "LINK": ("چین‌لینک", "Chainlink"),
    "TRX": ("ترون", "TRON"),
    "LTC": ("لایت‌کوین", "Litecoin"),
    "BCH": ("بیت‌کوین کش", "Bitcoin Cash"),
    "SHIB": ("شیبا اینو", "Shiba Inu"),
    "UNI": ("یونی‌سواپ", "Uniswap"),
    "ATOM": ("کازموس", "Cosmos"),
    "XLM": ("استلار", "Stellar"),
    "NEAR": ("نیر پروتکل", "NEAR Protocol"),
    "APT": ("اپتوس", "Aptos"),
    "ARB": ("آربیتروم", "Arbitrum"),
    "OP": ("اپتیمیزم", "Optimism"),
    "FIL": ("فایل‌کوین", "Filecoin"),
    "INJ": ("اینجکتیو", "Injective"),
    "SUI": ("سویی", "Sui"),
    "SEI": ("سی", "Sei"),
    "TIA": ("سلستیا", "Celestia"),
    "PEPE": ("پپه", "Pepe"),
    "WIF": ("داگ‌وی‌هت", "dogwifhat"),
    "BONK": ("بونک", "Bonk"),
    "FLOKI": ("فلوکی", "Floki"),
    "TON": ("تون‌کوین", "Toncoin"),
    "ETC": ("اتریوم کلاسیک", "Ethereum Classic"),
    "HBAR": ("هدرا", "Hedera"),
    "VET": ("وچین", "VeChain"),
    "ALGO": ("الگورند", "Algorand"),
    "ICP": ("اینترنت کامپیوتر", "Internet Computer"),
    "STX": ("استکس", "Stacks"),
    "GRT": ("گراف", "The Graph"),
    "AAVE": ("آوه", "Aave"),
    "MKR": ("میکر", "Maker"),
    "RUNE": ("ثورچین", "THORChain"),
    "FTM": ("فانتوم", "Fantom"),
    "S": ("سونیک", "Sonic"),
    "LDO": ("لیدو دی‌او", "Lido DAO"),
    "CRV": ("کیووی", "Curve DAO"),
    "SAND": ("سندباکس", "The Sandbox"),
    "MANA": ("دیسنترالند", "Decentraland"),
    "AXS": ("اکسی اینفینیتی", "Axie Infinity"),
    "GALA": ("گالا", "Gala"),
    "CHZ": ("چیلیز", "Chiliz"),
    "ENA": ("ائنا", "Ethena"),
    "WLD": ("ورلدکوین", "Worldcoin"),
    "JUP": ("جوپیتر", "Jupiter"),
    "PYTH": ("پایت", "Pyth Network"),
    "ORDI": ("اردی", "Ordinals"),
    "KCS": ("توکن کوکوین", "KuCoin Token"),
    "ZEC": ("زی‌کش", "Zcash"),
    "DASH": ("دش", "Dash"),
    "EOS": ("ایاس", "EOS"),
    "XTZ": ("تزوس", "Tezos"),
    "CAKE": ("پنکیک‌سواپ", "PancakeSwap"),
    "EGLD": ("مالتی‌ورس ایکس", "MultiversX"),
    "FLOW": ("فلو", "Flow"),
    "KAS": ("کاسپا", "Kaspa"),
    "POL": ("پالیگان", "Polygon"),
    "MATIC": ("پالیگان", "Polygon"),
    "TRUMP": ("ترامپ", "OFFICIAL TRUMP"),
    "AR": ("آروِیو", "Arweave"),
    "IMX": ("ایموتبل ایکس", "Immutable"),
    "RNDR": ("رندر", "Render"),
    "FET": ("فتچ‌ای‌آی", "Fetch.ai"),
}


def base(symbol: str) -> str:
    """نماد پایه: «BTC» از «BTC-USDT» / «BTC/USDT» / «BTCUSDT» / «BTC»."""
    s = str(symbol or "").upper().strip().replace("/", "-").replace("_", "-")
    if "-" in s:
        return s.split("-", 1)[0]
    for q in _QUOTES:                      # Binance: بدون جداکننده
        if s.endswith(q) and len(s) > len(q):
            return s[: -len(q)]
    return s


def quote(symbol: str) -> str:
    """ارز مبنای معامله: «USDT» از «BTC-USDT»؛ پیش‌فرض USDT."""
    s = str(symbol or "").upper().strip().replace("/", "-").replace("_", "-")
    if "-" in s:
        parts = s.split("-", 1)
        return parts[1] if parts[1] else "USDT"
    for q in _QUOTES:
        if s.endswith(q) and len(s) > len(q):
            return q
    return "USDT"


def pair_display(symbol: str) -> str:
    """جفت‌نماد تمیز: «BTC/USDT» — هر ورودی، یک خروجی خوانا."""
    b, q = base(symbol), quote(symbol)
    return f"{b}/{q}" if b else "—"


def name_pair(symbol: str) -> tuple[str, str]:
    """(نام فارسی، نام انگلیسی) — ناشناخته = («», «»)."""
    return NAMES.get(base(symbol), ("", ""))


def coin_label(symbol: str) -> str:
    """برچسب خوانا برای پیام: «بیت‌کوین (BTC/USDT)» یا برای ناشناخته «XYZ/USDT»."""
    fa, _en = name_pair(symbol)
    pair = pair_display(symbol)
    return f"{fa} ({pair})" if fa else pair
