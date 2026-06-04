"""Market data from Yahoo Finance (yfinance). Cached in-memory + on disk."""
import os
import json
import pickle
from datetime import datetime, timedelta
from pathlib import Path

import yfinance as yf

UNIVERSE = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META", "BRK.B", "JNJ", "V",
    "WMT", "JPM", "PG", "MA", "INTC", "BA", "NFLX", "IBM", "AMD", "QCOM",
]

# In-memory cache: key -> (value, timestamp)
_mem_cache = {}
_cache_dir = Path(__file__).parent.parent / "data"
_cache_dir.mkdir(exist_ok=True)


def _cached(key: str, fn, ttl: int = 3600) -> dict | None:
    """Check in-memory cache, then disk, then call fn(). Cache for ttl seconds."""
    now = datetime.now().timestamp()
    
    # Check memory
    if key in _mem_cache:
        val, ts = _mem_cache[key]
        if now - ts < ttl:
            return val
    
    # Check disk
    disk_key = _cache_dir / f"{key}.json"
    if disk_key.exists():
        try:
            with open(disk_key) as f:
                val = json.load(f)
            ts = disk_key.stat().st_mtime
            if now - ts < ttl:
                _mem_cache[key] = (val, ts)
                return val
        except Exception:
            pass
    
    # Call function
    try:
        val = fn()
        if val:
            _mem_cache[key] = (val, now)
            try:
                with open(disk_key, "w") as f:
                    json.dump(val, f)
            except Exception:
                pass
        return val
    except Exception:
        return None


def batch_closes(symbols: list[str], period: str = "1mo") -> dict[str, list[float]]:
    """Download close prices for multiple symbols. Returns dict symbol -> list of closes."""
    def build():
        data = yf.download(
            " ".join(symbols),
            period=period,
            interval="1d",
            multi_level_index=False,
            progress=False,
        )
        if data.empty:
            return {}
        result = {}
        if len(symbols) == 1:
            result[symbols[0]] = data["Close"].tolist()
        else:
            for sym in symbols:
                if sym in data.columns:
                    col_name = ("Close", sym)
                    if col_name in data.columns:
                        result[sym] = data[col_name].tolist()
                    else:
                        result[sym] = data[sym].tolist()
        return result
    
    return _cached(f"batch:{':'.join(symbols)}:{period}", build, ttl=900) or {}


def get_quote(symbol: str) -> dict:
    """Get current quote for a symbol."""
    def build():
        ticker = yf.Ticker(symbol)
        data = ticker.info or {}
        return {
            "price": data.get("currentPrice") or data.get("regularMarketPrice"),
            "change": data.get("regularMarketChange"),
            "change_pct": data.get("regularMarketChangePercent"),
            "day_high": data.get("dayHigh"),
            "day_low": data.get("dayLow"),
            "year_high": data.get("fiftyTwoWeekHigh"),
            "year_low": data.get("fiftyTwoWeekLow"),
            "volume": data.get("volume"),
            "market_cap": data.get("marketCap"),
        }
    
    return _cached(f"quote:{symbol}", build, ttl=300) or {}


def get_fundamentals(symbol: str) -> dict:
    """Get fundamental metrics for a symbol."""
    def build():
        ticker = yf.Ticker(symbol)
        data = ticker.info or {}
        return {
            "trailingPE": data.get("trailingPE"),
            "forwardPE": data.get("forwardPE"),
            "priceToBook": data.get("priceToBook"),
            "dividendYield": data.get("dividendYield"),
            "beta": data.get("beta"),
            "sector": data.get("sector"),
            "industry": data.get("industry"),
        }
    
    return _cached(f"fund:{symbol}", build, ttl=3600) or {}


def get_news(symbol: str) -> list[dict]:
    """Get recent news for a symbol."""
    def build():
        ticker = yf.Ticker(symbol)
        news = ticker.news or []
        return [
            {
                "title": item.get("title", ""),
                "publisher": item.get("publisher", ""),
                "link": item.get("link", ""),
            }
            for item in news[:5]
        ]
    
    return _cached(f"news:{symbol}", build, ttl=3600) or []


def get_history(symbol: str, period: str = "6mo", interval: str = "1d") -> dict:
    """Get historical data for a symbol."""
    def build():
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period, interval=interval)
        if hist.empty:
            return {"dates": [], "closes": [], "volumes": []}
        return {
            "dates": hist.index.strftime("%Y-%m-%d").tolist(),
            "closes": hist["Close"].tolist(),
            "volumes": hist["Volume"].astype(int).tolist(),
        }
    
    return _cached(f"hist:{symbol}:{period}:{interval}", build, ttl=900) or {}
