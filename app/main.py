"""Robinhood Advisor -- weekly paper-trading dashboard.

Flask serves a single-page dashboard plus a small JSON API. Market data comes
from Yahoo Finance (yfinance, no login). Weekly picks come from the advisor
(heuristic, or Claude if a key is set). The $50/stock portfolio is simulated.

Run:  python app/main.py   ->  http://localhost:5000
"""
import os

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

try:
    from . import advisor, market_data, paper
except ImportError:  # allow `python app/main.py` as well as `python -m app.main`
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from app import advisor, market_data, paper

load_dotenv()

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/health")
def health():
    has_key = bool(
        (os.getenv("CLAUDE_API_KEY") or os.getenv("ANTHROPIC_API_KEY"))
        and "your_" not in (os.getenv("CLAUDE_API_KEY") or "your_")
    )
    return jsonify({"status": "ok", "claude_enabled": has_key})


@app.route("/api/week")
def week():
    return jsonify(advisor.get_week())


@app.route("/api/week/refresh", methods=["POST"])
def refresh():
    """Intraday re-evaluation -- re-pick / re-time for the current week."""
    return jsonify(advisor.reevaluate())


@app.route("/api/portfolio")
def portfolio():
    return jsonify(paper.get_portfolio())


@app.route("/api/stock/<symbol>")
def stock(symbol):
    return jsonify({
        "quote": market_data.get_quote(symbol),
        "fundamentals": market_data.get_fundamentals(symbol),
        "news": market_data.get_news(symbol),
    })


@app.route("/api/stock/<symbol>/history")
def stock_history(symbol):
    period = request.args.get("range", "6mo")
    interval = request.args.get("interval", "1d")
    return jsonify(market_data.get_history(symbol, period=period, interval=interval))


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(debug=True, host="0.0.0.0", port=port)
