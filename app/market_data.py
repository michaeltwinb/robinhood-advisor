"""Market data via yfinance (Yahoo Finance) -- no login required.

Everything degrades gracefully: if a field or a whole call fails (rate limit,
network blip, delisted ticker) we return partial data rather than raising, so
the dashboard never goes blank.
"""
import time

import yfinance as yf

# Candidate universe the weekly advisor picks from: liquid large/mega caps plus
# popular high-volume movers. Tweak freely.
UNIVERSE = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "AMD", "NFLX",
    "AVGO", "JPM", "V", "MA", "DIS", "PYPL", "INTC", "CRM", "ADBE", "COST",
    "WMT", "KO", "PEP", "BA", "CAT", "GE", "F", "GM", "UBER", "ABNB", "SHOP",
    "PLTR", "COIN", "SOFI", "RIVN", "MARA", "SNAP", "PINS", "ROKU", "DKNG",
    "NKE", "SBUX", "MCD", "XOM", "CVX", "T", "QCOM", "ORCL", "MU", "SQ", "LLY",
]

_cache: dict[str, tuple[float, object]] = {}
_TTL = 300  # seconds


def _cached(key: str, fn, ttl: int = _TTL):
    now = time.time()
    hit = _cache.get(key)
    if hit and now - hit[0] < ttl:
        return hit[1]
    val = fn()
    _cache[key] = (now, val)
    return val


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def get_quote(symbol: str) -> dict:
    """Live-ish snapshot: price, day change, market cap, volume."""
    symbol = symbol.upper()

    def build():
        t = yf.Ticker(symbol)
        fi = t.fast_info
        last = _safe(lambda: float(fi.last_price))
        prev = _safe(lambda: float(fi.previous_close))
        change = change_pct = None
        if last is not None and prev:
            change = round(last - prev, 2)
            change_pct = round((last - prev) / prev * 100, 2)
        return {
            "symbol": symbol,
            "price": last,
            "previous_close": prev,
            "change": change,
            "change_pct": change_pct,
            "day_high": _safe(lambda: float(fi.day_high)),
            "day_low": _safe(lambda: float(fi.day_low)),
            "year_high": _safe(lambda: float(fi.year_high)),
            "year_low": _safe(lambda: float(fi.year_low)),
            "market_cap": _safe(lambda: float(fi.market_cap)),
            "volume": _safe(lambda: int(fi.last_volume)),
            "currency": _safe(lambda: fi.currency) or "USD",
        }

    return _cached(f"quote:{symbol}", build, ttl=60)


def get_history(symbol: str, period: str = "6mo", interval: str = "1d") -> list[dict]:
    """OHLC series for charting -> [{t, open, high, low, close, volume}]."""
    symbol = symbol.upper()

    def build():
        df = yf.Ticker(symbol).history(period=period, interval=interval)
        out = []
        for idx, row in df.iterrows():
            out.append({
                "t": idx.isoformat(),
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
            })
        return out

    return _cached(f"hist:{symbol}:{period}:{interval}", build, ttl=300) or []


def get_fundamentals(symbol: str) -> dict:
    """The Yahoo-style stat block. .info is slow/flaky so we cache it hard."""
    symbol = symbol.upper()

    def build():
        info = _safe(lambda: yf.Ticker(symbol).info, {}) or {}
        keys = [
            "longName", "shortName", "sector", "industry", "website",
            "longBusinessSummary", "trailingPE", "forwardPE", "priceToBook",
            "dividendYield", "beta", "fiftyTwoWeekHigh", "fiftyTwoWeekLow",
            "trailingEps", "marketCap", "averageVolume", "fullTimeEmployees",
            "profitMargins", "revenueGrowth", "recommendationKey",
            "targetMeanPrice", "fiftyDayAverage", "twoHundredDayAverage",
        ]
        return {k: info.get(k) for k in keys}

    return _cached(f"fund:{symbol}", build, ttl=3600) or {}


def get_news(symbol: str, limit: int = 6) -> list[dict]:
    """Recent headlines. yfinance has changed this shape across versions, so we
    defend against both the old flat dicts and the newer nested 'content' form.
    """
    symbol = symbol.upper()

    def build():
        raw = _safe(lambda: yf.Ticker(symbol).news, []) or []
        items = []
        for n in raw[:limit]:
            content = n.get("content", n)
            title = content.get("title") or n.get("title")
            if not title:
                continue
            link = (
                (content.get("canonicalUrl") or {}).get("url")
                or content.get("clickThroughUrl", {}).get("url")
                or n.get("link")
            )
            publisher = (
                (content.get("provider") or {}).get("displayName")
                or n.get("publisher")
            )
            items.append({
                "title": title,
                "publisher": publisher,
                "link": link,
                "published": content.get("pubDate") or n.get("providerPublishTime"),
            })
        return items

    return _cached(f"news:{symbol}", build, ttl=900) or []


def _extract_close(data, symbol: str, single: bool) -> list[float]:
    """Pull Close prices from a yfinance DataFrame regardless of column layout."""
    import pandas as pd
    cols = data.columns
    if isinstance(cols, pd.MultiIndex):
        for key in (("Close", symbol), (symbol, "Close")):
            if key in cols:
                return [round(float(v), 4) for v in data[key].dropna()]
        try:
            return [round(float(v), 4) for v in data[symbol]["Close"].dropna()]
        except Exception:
            return []
    if single and "Close" in cols:
        return [round(float(v), 4) for v in data["Close"].dropna()]
    for candidate in (f"Close_{symbol}", symbol):
        if candidate in cols:
            col = data[candidate]
            s = col["Close"] if hasattr(col, "columns") and "Close" in col.columns else col
            return [round(float(v), 4) for v in s.dropna()]
    return []


def batch_closes(symbols: list[str], period: str = "1mo") -> dict[str, list[float]]:
    """Closing prices for many tickers in one request -> {symbol: [closes]}."""
    def build():
        kwargs = dict(period=period, interval="1d", progress=False)
        try:
            data = yf.download(symbols, **kwargs, multi_level_index=False)
        except TypeError:
            data = yf.download(symbols, **kwargs, group_by="ticker")
        if data.empty:
            return {}
        out: dict[str, list[float]] = {}
        single = len(symbols) == 1
        for s in symbols:
            closes = _extract_close(data, s, single)
            if closes:
                out[s] = closes
        return out

    return _cached(f"batch:{','.join(sorted(symbols))}:{period}", build, ttl=600) or {}
