"""Simulated ($50/stock) paper-trading portfolio for the current week's picks.

No real money, no real orders. On first view of a week we snapshot an entry
price for each pick (~$50 worth of shares) and then mark it to live prices to
show hypothetical P&L. Resets when the week's picks change.
"""
from datetime import date

from . import advisor, market_data, store


def _ensure_positions(week: dict) -> dict:
    """Create the entry snapshot for this week if it doesn't exist yet."""
    key = week["week_key"]
    saved = store.load(f"portfolio_{key}")
    if saved:
        return saved
    positions = []
    for p in week["picks"]:
        entry = p["price_at_pick"]
        positions.append({
            "symbol": p["symbol"],
            "entry_price": entry,
            "shares": p["shares"],
            "cost_basis": round(entry * p["shares"], 2),
            "buy_day": p["buy_day"],
            "sell_day": p["sell_day"],
        })
    snapshot = {
        "week_key": key,
        "opened_at": date.today().isoformat(),
        "positions": positions,
    }
    store.save(f"portfolio_{key}", snapshot)
    return snapshot


def get_portfolio() -> dict:
    week = advisor.get_week()
    snapshot = _ensure_positions(week)

    rows = []
    total_cost = total_value = 0.0
    for pos in snapshot["positions"]:
        quote = market_data.get_quote(pos["symbol"])
        cur = quote.get("price") or pos["entry_price"]
        value = round(cur * pos["shares"], 2)
        pnl = round(value - pos["cost_basis"], 2)
        pnl_pct = round((cur / pos["entry_price"] - 1) * 100, 2) if pos["entry_price"] else 0.0
        total_cost += pos["cost_basis"]
        total_value += value
        rows.append({
            **pos,
            "current_price": cur,
            "current_value": value,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "day_change_pct": quote.get("change_pct"),
        })

    total_pnl = round(total_value - total_cost, 2)
    return {
        "week_key": snapshot["week_key"],
        "opened_at": snapshot["opened_at"],
        "positions": rows,
        "summary": {
            "invested": round(total_cost, 2),
            "value": round(total_value, 2),
            "pnl": total_pnl,
            "pnl_pct": round((total_value / total_cost - 1) * 100, 2) if total_cost else 0.0,
            "num_positions": len(rows),
        },
        "note": "Simulated paper trading -- no real money or orders.",
    }
