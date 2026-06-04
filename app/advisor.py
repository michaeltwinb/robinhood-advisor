"""Weekly stock advisor.

Produces up to 10 picks for the current trading week (Mon-Fri), each with a
suggested buy day, sell day, rationale, risk level and ~$50 budget. Picks are
locked for the week and cached; on Saturday the target rolls to next week, so
the dashboard refreshes to a new set. An intraday re-evaluation can nudge the
buy/sell days as prices move.

Two engines:
  * heuristic  -- momentum / mean-reversion scoring over the universe. Always
                  available, needs no API key. This is the default.
  * claude     -- if a working CLAUDE_API_KEY is present, Claude refines the
                  shortlist and writes the rationale. Falls back to heuristic
                  on any error.

NOT FINANCIAL ADVICE. These are algorithmic ideas / a simulation, not a
prediction. Short-term price moves are not reliably predictable.
"""
import os
import json
import statistics
from datetime import date, timedelta

from . import market_data, store

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
BUDGET_PER_STOCK = 50.0
MAX_PICKS = 10


# --------------------------------------------------------------------------- #
# Week bookkeeping
# --------------------------------------------------------------------------- #
def target_monday(today: date | None = None) -> date:
    """Monday of the week we're advising on. Weekends roll to next Monday."""
    today = today or date.today()
    wd = today.weekday()  # Mon=0 .. Sun=6
    if wd >= 5:  # Sat/Sun -> next week
        return today + timedelta(days=(7 - wd))
    return today - timedelta(days=wd)


def week_key(today: date | None = None) -> str:
    return target_monday(today).isoformat()


def week_meta(today: date | None = None) -> dict:
    mon = target_monday(today)
    fri = mon + timedelta(days=4)
    return {
        "week_key": mon.isoformat(),
        "monday": mon.isoformat(),
        "friday": fri.isoformat(),
        "label": f"{mon.strftime('%b %d')} - {fri.strftime('%b %d, %Y')}",
    }


# --------------------------------------------------------------------------- #
# Signal computation
# --------------------------------------------------------------------------- #
def _returns(closes: list[float]) -> list[float]:
    return [(closes[i] / closes[i - 1] - 1) for i in range(1, len(closes))]


def _score_universe() -> list[dict]:
    """Rank the universe by a blended momentum / trend signal."""
    closes = market_data.batch_closes(market_data.UNIVERSE, period="1mo")
    rows = []
    for sym, series in closes.items():
        if len(series) < 10:
            continue
        last = series[-1]
        ret_5d = series[-1] / series[-6] - 1 if len(series) >= 6 else 0.0
        ret_21d = series[-1] / series[0] - 1
        rets = _returns(series)
        vol = statistics.pstdev(rets) if len(rets) > 1 else 0.0
        # Favour names trending up over the month with healthy (not extreme)
        # recent momentum; penalise very high volatility a touch.
        score = 0.55 * ret_21d + 0.45 * ret_5d - 0.5 * vol
        rows.append({
            "symbol": sym,
            "price": round(last, 2),
            "ret_5d": round(ret_5d * 100, 2),
            "ret_21d": round(ret_21d * 100, 2),
            "vol": round(vol * 100, 2),
            "score": round(score * 100, 3),
        })
    rows.sort(key=lambda r: r["score"], reverse=True)
    return rows


def _risk_from_vol(vol_pct: float) -> str:
    if vol_pct < 2.0:
        return "Low"
    if vol_pct < 3.5:
        return "Medium"
    return "High"


def _window(row: dict) -> dict:
    """Heuristic buy/sell days within the week, with a plain-English reason."""
    up_trend = row["ret_21d"] > 0
    hot = row["ret_5d"] > 4
    cooling = row["ret_5d"] < -1

    if up_trend and cooling:
        buy, sell = "Monday", "Thursday"
        reason = ("Up over the month but pulled back this week -- buy the dip "
                  "early, take profit before Friday positioning.")
    elif hot:
        buy, sell = "Tuesday", "Friday"
        reason = ("Running hot; wait for a Monday cooldown, then ride momentum "
                  "into the Friday close.")
    elif up_trend:
        buy, sell = "Monday", "Friday"
        reason = "Steady uptrend -- hold the full week to capture the drift."
    else:
        buy, sell = "Wednesday", "Friday"
        reason = ("Weak/mixed trend -- wait for mid-week confirmation before a "
                  "small position.")
    return {"buy_day": buy, "sell_day": sell, "timing_reason": reason}


def _shares(price: float) -> float:
    return round(BUDGET_PER_STOCK / price, 4) if price else 0.0


# --------------------------------------------------------------------------- #
# Engines
# --------------------------------------------------------------------------- #
def _heuristic_picks(ranked: list[dict]) -> list[dict]:
    picks = []
    for row in ranked[:MAX_PICKS]:
        win = _window(row)
        direction = "up" if row["ret_21d"] > 0 else "down"
        picks.append({
            "symbol": row["symbol"],
            "price_at_pick": row["price"],
            "shares": _shares(row["price"]),
            "budget": BUDGET_PER_STOCK,
            "buy_day": win["buy_day"],
            "sell_day": win["sell_day"],
            "risk": _risk_from_vol(row["vol"]),
            "target": round(row["price"] * (1 + max(row["ret_5d"], 1) / 100), 2),
            "rationale": (
                f"{row['symbol']} is {row['ret_21d']:+.1f}% over the past month "
                f"and {row['ret_5d']:+.1f}% this week (trending {direction}). "
                f"{win['timing_reason']}"
            ),
            "signals": {
                "ret_5d": row["ret_5d"],
                "ret_21d": row["ret_21d"],
                "volatility": row["vol"],
                "score": row["score"],
            },
            "engine": "heuristic",
        })
    return picks


def _claude_picks(ranked: list[dict]) -> list[dict] | None:
    api_key = os.getenv("CLAUDE_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
    if not api_key or "your_" in api_key:
        return None
    try:
        from anthropic import Anthropic

        client = Anthropic(api_key=api_key)
        shortlist = ranked[:20]
        meta = week_meta()
        prompt = (
            "You are a disciplined swing-trading analyst. From the candidate "
            "list below, choose up to 10 stocks for the trading week "
            f"{meta['label']}. Each gets a ~$50 simulated (paper) budget.\n\n"
            "For EACH pick return: symbol, buy_day and sell_day (one of Monday, "
            "Tuesday, Wednesday, Thursday, Friday), risk (Low/Medium/High), "
            "target (number), and a one-sentence rationale tied to the signals.\n\n"
            "Candidates (symbol, price, 5d %, 21d %, volatility %):\n"
            + "\n".join(
                f"{r['symbol']} ${r['price']} {r['ret_5d']:+}% {r['ret_21d']:+}% "
                f"{r['vol']}%" for r in shortlist
            )
            + "\n\nReturn ONLY a JSON array of objects with keys: symbol, "
            "buy_day, sell_day, risk, target, rationale."
        )
        msg = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text
        start, end = text.find("["), text.rfind("]")
        data = json.loads(text[start:end + 1])

        by_sym = {r["symbol"]: r for r in ranked}
        picks = []
        for item in data[:MAX_PICKS]:
            sym = str(item.get("symbol", "")).upper()
            row = by_sym.get(sym)
            if not row:
                continue
            picks.append({
                "symbol": sym,
                "price_at_pick": row["price"],
                "shares": _shares(row["price"]),
                "budget": BUDGET_PER_STOCK,
                "buy_day": item.get("buy_day", "Monday"),
                "sell_day": item.get("sell_day", "Friday"),
                "risk": item.get("risk", _risk_from_vol(row["vol"])),
                "target": item.get("target", row["price"]),
                "rationale": item.get("rationale", ""),
                "signals": {
                    "ret_5d": row["ret_5d"],
                    "ret_21d": row["ret_21d"],
                    "volatility": row["vol"],
                    "score": row["score"],
                },
                "engine": "claude",
            })
        return picks or None
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def _build(force: bool = False) -> dict:
    ranked = _score_universe()
    picks = _claude_picks(ranked) or _heuristic_picks(ranked)
    meta = week_meta()
    payload = {
        **meta,
        "generated_at": date.today().isoformat(),
        "engine": picks[0]["engine"] if picks else "heuristic",
        "budget_per_stock": BUDGET_PER_STOCK,
        "picks": picks,
        "disclaimer": (
            "Algorithmic ideas for a paper-trading simulation. NOT financial "
            "advice. Short-term prices are not reliably predictable."
        ),
    }
    return payload


def get_week(force: bool = False) -> dict:
    """Return this week's picks, generating + caching them if needed."""
    key = week_key()
    cached = store.load(f"picks_{key}")
    if cached and not force:
        return cached
    payload = _build(force=force)
    store.save(f"picks_{key}", payload)
    # Reset the paper portfolio snapshot whenever the week's picks change.
    store.save(f"portfolio_{key}", None)
    return payload


def reevaluate() -> dict:
    """Intraday nudge: re-pull prices and let the engine re-pick / re-time for
    the current week (keeps the same week key, overwrites the picks)."""
    return get_week(force=True)
