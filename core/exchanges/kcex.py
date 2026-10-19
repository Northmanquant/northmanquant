"""اتصال به صرافی KCEX - نسخه سازگار با Streamlit Cloud"""
import requests
import time

class KCEXExchange:
    BASE_URL = "https://api.kcex.com"

    def __init__(self, api_key=None, api_secret=None):
        self.api_key = api_key
        self.api_secret = api_secret

    def get_ticker(self, symbol="BTC/USDT"):
        """گرفتن قیمت لحظه ای"""
        try:
            symbol_fmt = symbol.replace("/", "-")
            r = requests.get(
                f"{self.BASE_URL}/api/v1/ticker",
                params={"symbol": symbol_fmt},
                timeout=10
            )
            if r.status_code == 200:
                data = r.json()
                # بعضی API ها دیتا رو داخل data میزارن
                if "data" in data and isinstance(data["data"], dict):
                    data = data["data"]
                return {
                    "exchange": "KCEX",
                    "symbol": symbol,
                    "last": float(data.get("last", 0) or 0),
                    "bid": float(data.get("buy", 0) or data.get("bid", 0) or 0),
                    "ask": float(data.get("sell", 0) or data.get("ask", 0) or 0),
                    "volume": float(data.get("vol", 0) or 0),
                    "timestamp": time.time()
                }
        except Exception as e:
            print(f"KCEX Error: {e}")
        return None
