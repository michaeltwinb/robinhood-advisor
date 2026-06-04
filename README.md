# Robinhood Investment Advisor

A reactive web dashboard that surfaces up to **10 stock ideas per trading week**
(Monday–Friday), each with a suggested **buy day, sell day, rationale, risk
level and a ~$50 budget** — then tracks them in a **paper-trading simulation**
with live P&L. Every stock has a Yahoo-Finance-style detail view (price chart,
fundamentals, news).

> ⚠️ **Not financial advice.** Picks are algorithmic ideas for a paper-trading
> *simulation* — no real money, no real orders. Short-term prices are not
> reliably predictable.

## Features

- **Weekly watchlist** — up to 10 picks per week with buy/sell windows and reasoning
- **Auto-rotation** — picks lock Mon–Fri and roll to a fresh set every Saturday
- **Intraday re-evaluation** — "Re-evaluate" re-pulls prices and re-times picks
- **Paper portfolio** — ~$50/stock simulated positions with live P&L
- **Yahoo-style stock pages** — price chart, fundamentals, and recent news
- **Works without an API key** — a momentum/mean-reversion heuristic generates
  picks by default; add a Claude key to get richer AI rationale

## Setup

### Prerequisites
- Python 3.10+
- (Optional) a Claude API key for AI-written rationale

### Installation

1. Clone the repository:
```bash
git clone https://github.com/michaeltwinb/robinhood-advisor.git
cd robinhood-advisor
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. (Optional) create a `.env` file for richer AI rationale:
```
CLAUDE_API_KEY=sk-ant-...
```
Without a key the app still works fully using the built-in heuristic engine.
Market data comes from Yahoo Finance and needs no credentials.

## Usage

```bash
python -m app.main
```
Then open **http://localhost:5000** in your browser.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Dashboard (single-page app) |
| GET | `/api/health` | Status + whether Claude is enabled |
| GET | `/api/week` | This week's picks (generates & caches) |
| POST | `/api/week/refresh` | Intraday re-evaluation of the current week |
| GET | `/api/portfolio` | Paper-trading positions + P&L |
| GET | `/api/stock/<symbol>` | Quote, fundamentals, and news |
| GET | `/api/stock/<symbol>/history?range=6mo` | OHLC history for charts |

## How it works

- **Data:** [`yfinance`](https://pypi.org/project/yfinance/) (Yahoo Finance) — no login required.
- **Picks:** the universe in `app/market_data.py` is scored by momentum/trend in
  `app/advisor.py`. If `CLAUDE_API_KEY` is set, Claude refines the shortlist and
  writes the rationale; otherwise the heuristic does.
- **Weeks:** Mon–Fri are "locked" and cached under `data/`. On Saturday the
  target rolls to next week, so the dashboard shows a new set.
- **Paper trading:** `app/paper.py` snapshots a ~$50 entry per pick and marks it
  to live prices for P&L. All simulated.

## Deployment notes

This runs as a normal Flask app (`gunicorn app.main:app` for production — see the
`Dockerfile`). The weekly auto-rotation and persisted state (`data/`) require an
always-on host; on an ephemeral/free tier they reset when the host sleeps.
