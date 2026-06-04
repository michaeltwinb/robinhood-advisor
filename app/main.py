from flask import Flask, jsonify, request
import robin_stocks as rh
from anthropic import Anthropic
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
client = Anthropic(api_key=os.getenv("CLAUDE_API_KEY"))

# Robinhood credentials
RH_EMAIL = os.getenv('RH_EMAIL')
RH_PASSWORD = os.getenv('RH_PASSWORD')

@app.route('/', methods=['GET'])
def home():
    return jsonify({"message": "Robinhood Advisor API is running!"})

@app.route('/api/login', methods=['POST'])
def login_robinhood():
    """Login to Robinhood"""
    try:
        result = rh.robinhood.login(RH_EMAIL, RH_PASSWORD)
        return jsonify({"status": "Logged in successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/api/portfolio', methods=['GET'])
def get_portfolio():
    """Get your Robinhood portfolio"""
    try:
        rh.robinhood.login(RH_EMAIL, RH_PASSWORD)
        positions = rh.robinhood.account.build_holdings()
        portfolio_value = rh.robinhood.account.load_portfolio_profile()

        return jsonify({
            "positions": positions,
            "portfolio_value": portfolio_value
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/api/recommendation', methods=['POST'])
def get_recommendation():
    """Get Claude AI investment recommendation"""
    try:
        data = request.json
        portfolio_data = data.get('portfolio', 'No portfolio data provided')

        prompt = f"""You are an expert investment advisor. Based on this portfolio data, provide 3-5 stock recommendations:

Portfolio Data: {portfolio_data}

For each recommendation provide:
1. Stock ticker
2. Buy/Hold/Sell recommendation
3. Why you recommend this
4. Risk level (Low/Medium/High)
5. Price target

IMPORTANT: This is not professional financial advice. Always remind users to do their own research."""

        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1024,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        return jsonify({
            "recommendation": message.content[0].text
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/api/quote/<symbol>', methods=['GET'])
def get_quote(symbol):
    """Get stock quote"""
    try:
        quote = rh.robinhood.get_quotes(symbol)
        return jsonify(quote)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

if __name__ == '__main__':
    app.run(debug=True, port=5000)
