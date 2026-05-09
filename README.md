# Crypto RL Trading Bot

A complete crypto spot trading system using Reinforcement Learning with a modern web dashboard. Supports Binance spot trading, paper trading, historical backtesting, model training/evaluation, and full trading history.

> **DISCLAIMER:** Trading cryptocurrencies involves significant risk. Past performance does not guarantee future results. This system does NOT guarantee profits. Use at your own risk. Start with paper trading before risking real money.

## Features

- **RL-Based Trading**: Train PPO, A2C, and DQN models using Stable-Baselines3
- **Backtesting**: Realistic historical backtesting with fees, slippage, and Binance order rules
- **Paper Trading**: Simulated trading with real-time market data
- **Live Trading**: Binance spot trading with safety controls and emergency stop
- **Dashboard**: Modern React + Tailwind CSS dashboard with 7 pages
- **Risk Management**: Stop-loss, take-profit, max drawdown, daily loss limits, cooldown
- **Small Account Awareness**: Warnings for small balances, fee impact analysis
- **Honest Reporting**: No fake profits, realistic execution, fee/slippage included

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python, FastAPI |
| RL/ML | Stable-Baselines3, Gymnasium, PyTorch |
| Data | pandas, numpy, ta (technical analysis) |
| Exchange | ccxt (Binance) |
| Database | SQLite |
| Frontend | React, TypeScript, Tailwind CSS |
| Charts | Recharts |
| Deployment | Docker Compose |

## Quick Start

### Prerequisites
- Python 3.12+
- Node.js 18+
- Poetry (Python package manager)

### Backend Setup

```bash
cd backend
cp .env.example .env
# Edit .env with your Binance API keys (optional, only for live trading)
poetry install
poetry run fastapi dev app/main.py
```

The API server runs at http://localhost:8000

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

The dashboard runs at http://localhost:5173

### Docker Compose (Production)

```bash
cp backend/.env.example backend/.env
# Edit backend/.env with your settings
docker-compose up --build
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000

## Dashboard Pages

1. **Overview** — Current balance, P&L, equity curve, warnings
2. **Backtest** — Run backtests with configurable parameters, view results with charts
3. **Paper Trading** — Simulated live trading, start/stop/reset
4. **Live Trading** — Binance spot trading with confirmation modal and emergency stop
5. **Model** — Train/evaluate RL models, view training rewards, model registry
6. **History** — Complete trade history with filtering and CSV export
7. **Settings** — Configure pair, timeframe, fees, risk parameters, API keys

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /health | Health check |
| GET | /settings | Get all settings |
| POST | /settings | Update settings |
| POST | /data/download | Download OHLCV data |
| POST | /model/train | Start model training |
| GET | /model/status | Training status |
| POST | /model/evaluate | Evaluate a model |
| GET | /model/list | List trained models |
| POST | /backtest/run | Run backtest |
| GET | /backtest/results/{id} | Get backtest results |
| GET | /backtest/list | List backtest runs |
| POST | /paper/start | Start paper trading |
| POST | /paper/stop | Stop paper trading |
| POST | /paper/reset | Reset paper balance |
| GET | /paper/status | Paper trading status |
| POST | /live/start | Start live trading |
| POST | /live/stop | Stop live trading |
| POST | /live/emergency-stop | Emergency stop |
| GET | /live/status | Live trading status |
| GET | /trades | Get trade history |
| GET | /equity-curve | Get equity curve |
| GET | /metrics | Get performance metrics |

## RL Environment

The custom Gymnasium environment supports:

- **7 discrete actions**: Hold, Buy 25%, Buy 50%, Buy 100%, Sell 25%, Sell 50%, Sell 100%
- **Observation space**: OHLCV + 19 technical indicators + 6 account features
- **Technical indicators**: RSI, MACD, EMA (9/21/50/200), Bollinger Bands, ATR, volume change, returns, volatility
- **Realistic execution**: Fees, slippage, minimum order sizes, minimum notional values
- **Reward function**: Equity change + drawdown penalty + overtrading penalty + fee penalty + survival bonus

## Risk Management

- Maximum position size limit
- Stop-loss and take-profit
- Daily maximum loss limit
- Maximum drawdown stop
- Cooldown between trades
- Emergency stop button
- Live trading disabled by default
- Confirmation required before live trading
- Small account warnings (< 20 USDT)
- Fee impact warnings

## Small Account Notes (10 USDT)

- Many Binance pairs require minimum order sizes of 5-10 USDT
- Trading fees (0.1%) heavily impact profitability on small accounts
- The 100% monthly target is extremely aggressive — the system will show honest results
- Consider low-fee, low-frequency strategies
- The system prevents trades where expected profit < estimated fees + slippage

## Running Tests

```bash
cd backend
poetry run pytest app/tests/ -v
```

## Connecting Binance API

1. Create a Binance account at https://www.binance.com
2. Go to API Management and create a new API key
3. Enable **Spot Trading** permission only
4. **Do NOT enable** Futures, Margin, or Withdrawal permissions
5. Add your API key and secret to `backend/.env` or via the Settings page
6. API keys are stored in the database — never hardcoded

## Project Structure

```
/crypto-rl-trading
  /backend
    /app
      main.py              # FastAPI application
      config.py            # Configuration and settings
      database.py          # SQLite database setup
      /api
        routes.py           # All API endpoints
      /trading
        environment.py      # Custom Gymnasium RL environment
        backtester.py       # Backtesting engine
        paper_trader.py     # Paper trading module
        live_trader.py      # Binance live trading
        risk_manager.py     # Risk management
        execution.py        # Order execution
      /ml
        train.py            # Model training pipeline
        evaluate.py         # Model evaluation
        feature_engineering.py
      /data
        binance_data.py     # OHLCV data download
        preprocessing.py    # Technical indicators
      /tests
        test_environment.py
        test_risk_manager.py
        test_api.py
        test_preprocessing.py
  /frontend
    /src
      /pages               # 7 dashboard pages
      /components          # Shared components
      /services            # API client
      App.tsx              # Router setup
  docker-compose.yml
  README.md
```

## License

This project is for educational and personal use. Use at your own risk.
