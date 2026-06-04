# Robinhood Investment Advisor

An AI-powered investment recommendation app that connects to your Robinhood account and uses Claude AI to provide personalized stock recommendations.

## Features

- Login to Robinhood account
- View your portfolio
- Get AI-powered investment recommendations from Claude
- Get real-time stock quotes

## Setup

### Prerequisites
- Python 3.10+
- Robinhood account
- Claude API key

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

4. Set up environment variables — create a `.env` file in the project root:
```
RH_EMAIL=your_email@gmail.com
RH_PASSWORD=your_password
CLAUDE_API_KEY=sk-...
```

## Usage

Run the application:
```bash
python app/main.py
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Health check |
| POST | `/api/login` | Login to Robinhood |
| GET | `/api/portfolio` | Get your portfolio |
| POST | `/api/recommendation` | Get AI recommendation |
| GET | `/api/quote/<symbol>` | Get stock quote |
