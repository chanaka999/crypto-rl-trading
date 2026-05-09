import sqlite3
import json
from datetime import datetime
from pathlib import Path
from app.config import DB_PATH


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS bot_config (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key TEXT UNIQUE NOT NULL,
        value TEXT NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS market_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        timeframe TEXT NOT NULL,
        timestamp INTEGER NOT NULL,
        open REAL NOT NULL,
        high REAL NOT NULL,
        low REAL NOT NULL,
        close REAL NOT NULL,
        volume REAL NOT NULL,
        UNIQUE(symbol, timeframe, timestamp)
    );

    CREATE INDEX IF NOT EXISTS idx_market_data_symbol_tf
        ON market_data(symbol, timeframe, timestamp);

    CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        mode TEXT NOT NULL,
        symbol TEXT NOT NULL,
        side TEXT NOT NULL,
        price REAL NOT NULL,
        quantity REAL NOT NULL,
        fee REAL NOT NULL DEFAULT 0,
        slippage REAL NOT NULL DEFAULT 0,
        pnl REAL DEFAULT 0,
        balance_before REAL NOT NULL,
        balance_after REAL NOT NULL,
        model_action INTEGER,
        reason TEXT,
        confidence REAL
    );

    CREATE INDEX IF NOT EXISTS idx_trades_mode ON trades(mode);
    CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
    CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp);

    CREATE TABLE IF NOT EXISTS backtest_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        timeframe TEXT NOT NULL,
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        initial_balance REAL NOT NULL,
        final_balance REAL NOT NULL,
        net_profit REAL NOT NULL,
        return_pct REAL NOT NULL,
        max_drawdown REAL NOT NULL,
        num_trades INTEGER NOT NULL,
        win_rate REAL NOT NULL,
        avg_win REAL NOT NULL DEFAULT 0,
        avg_loss REAL NOT NULL DEFAULT 0,
        profit_factor REAL NOT NULL DEFAULT 0,
        sharpe_ratio REAL NOT NULL DEFAULT 0,
        fee_pct REAL NOT NULL DEFAULT 0.1,
        slippage_pct REAL NOT NULL DEFAULT 0.05,
        model_name TEXT,
        trades_json TEXT,
        equity_curve_json TEXT,
        monthly_returns_json TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS model_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        model_type TEXT NOT NULL,
        model_name TEXT NOT NULL,
        symbol TEXT NOT NULL,
        timeframe TEXT NOT NULL,
        total_timesteps INTEGER NOT NULL,
        training_reward REAL,
        eval_reward REAL,
        eval_return_pct REAL,
        eval_sharpe REAL,
        eval_max_drawdown REAL,
        status TEXT NOT NULL DEFAULT 'pending',
        file_path TEXT,
        config_json TEXT,
        reward_history_json TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS paper_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        initial_balance REAL NOT NULL,
        current_balance REAL NOT NULL,
        symbol TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'stopped',
        coin_holdings REAL NOT NULL DEFAULT 0,
        started_at TIMESTAMP,
        stopped_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS equity_curve (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mode TEXT NOT NULL,
        session_id INTEGER,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        balance REAL NOT NULL,
        equity REAL NOT NULL,
        drawdown REAL NOT NULL DEFAULT 0
    );

    CREATE INDEX IF NOT EXISTS idx_equity_mode ON equity_curve(mode);
    """)

    defaults = {
        "symbol": "BTC/USDT",
        "timeframe": "1h",
        "initial_balance": "10.0",
        "fee_pct": "0.1",
        "slippage_pct": "0.05",
        "max_position_pct": "100.0",
        "stop_loss_pct": "5.0",
        "take_profit_pct": "10.0",
        "daily_max_loss_pct": "10.0",
        "monthly_target_return_pct": "100.0",
        "min_confidence_threshold": "0.0",
        "live_trading_enabled": "false",
        "trading_mode": "backtest",
        "cooldown_seconds": "60",
        "max_drawdown_stop_pct": "20.0",
        "min_profit_over_fees": "true",
    }

    for key, value in defaults.items():
        cursor.execute(
            "INSERT OR IGNORE INTO bot_config (key, value) VALUES (?, ?)",
            (key, value),
        )

    conn.commit()
    conn.close()


def get_config_value(key: str, default: str = "") -> str:
    conn = get_connection()
    row = conn.execute(
        "SELECT value FROM bot_config WHERE key = ?", (key,)
    ).fetchone()
    conn.close()
    return row["value"] if row else default


def set_config_value(key: str, value: str):
    conn = get_connection()
    conn.execute(
        """INSERT INTO bot_config (key, value, updated_at) VALUES (?, ?, ?)
           ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""",
        (key, value, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def get_all_config() -> dict:
    conn = get_connection()
    rows = conn.execute("SELECT key, value FROM bot_config").fetchall()
    conn.close()
    return {row["key"]: row["value"] for row in rows}
