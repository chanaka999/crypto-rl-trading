import ccxt
import pandas as pd
import sqlite3
import time
from datetime import datetime
from typing import Optional
from app.config import settings, DATA_DIR
from app.database import get_connection


def get_exchange(api_key: str = "", api_secret: str = "") -> ccxt.binance:
    config = {"enableRateLimit": True}
    if api_key and api_secret:
        config["apiKey"] = api_key
        config["secret"] = api_secret
    return ccxt.binance(config)


def download_ohlcv(
    symbol: str = "BTC/USDT",
    timeframe: str = "1h",
    since: Optional[str] = None,
    until: Optional[str] = None,
    limit: int = 1000,
) -> pd.DataFrame:
    exchange = get_exchange()
    since_ts = None
    if since:
        since_ts = exchange.parse8601(since + "T00:00:00Z")

    until_ts = None
    if until:
        until_ts = exchange.parse8601(until + "T23:59:59Z")

    all_ohlcv = []
    current_since = since_ts

    while True:
        try:
            ohlcv = exchange.fetch_ohlcv(
                symbol, timeframe, since=current_since, limit=limit
            )
        except Exception as e:
            print(f"Error fetching data: {e}")
            break

        if not ohlcv:
            break

        all_ohlcv.extend(ohlcv)

        last_ts = ohlcv[-1][0]
        if until_ts and last_ts >= until_ts:
            break

        if len(ohlcv) < limit:
            break

        current_since = last_ts + 1
        time.sleep(exchange.rateLimit / 1000)

    if not all_ohlcv:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

    df = pd.DataFrame(all_ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = df["timestamp"].astype(int)

    if until_ts:
        df = df[df["timestamp"] <= until_ts]

    df = df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
    return df


def cache_ohlcv(df: pd.DataFrame, symbol: str, timeframe: str):
    if df.empty:
        return
    conn = get_connection()
    for _, row in df.iterrows():
        try:
            conn.execute(
                """INSERT OR IGNORE INTO market_data
                   (symbol, timeframe, timestamp, open, high, low, close, volume)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (symbol, timeframe, int(row["timestamp"]),
                 row["open"], row["high"], row["low"], row["close"], row["volume"]),
            )
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    conn.close()


def load_cached_ohlcv(
    symbol: str, timeframe: str,
    since: Optional[str] = None, until: Optional[str] = None,
) -> pd.DataFrame:
    conn = get_connection()
    query = "SELECT timestamp, open, high, low, close, volume FROM market_data WHERE symbol=? AND timeframe=?"
    params: list = [symbol, timeframe]

    if since:
        exchange = get_exchange()
        since_ts = exchange.parse8601(since + "T00:00:00Z")
        query += " AND timestamp >= ?"
        params.append(since_ts)

    if until:
        exchange = get_exchange()
        until_ts = exchange.parse8601(until + "T23:59:59Z")
        query += " AND timestamp <= ?"
        params.append(until_ts)

    query += " ORDER BY timestamp ASC"
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df


def fetch_or_load(
    symbol: str, timeframe: str,
    since: Optional[str] = None, until: Optional[str] = None,
) -> pd.DataFrame:
    cached = load_cached_ohlcv(symbol, timeframe, since, until)
    if not cached.empty and len(cached) > 10:
        return cached

    df = download_ohlcv(symbol, timeframe, since, until)
    if not df.empty:
        cache_ohlcv(df, symbol, timeframe)
    return df


def get_latest_price(symbol: str = "BTC/USDT") -> float:
    try:
        exchange = get_exchange()
        ticker = exchange.fetch_ticker(symbol)
        return ticker["last"]
    except Exception:
        return 0.0
