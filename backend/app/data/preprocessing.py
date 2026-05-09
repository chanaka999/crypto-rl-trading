import numpy as np
import pandas as pd
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands, AverageTrueRange


def add_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    # RSI
    df["rsi"] = RSIIndicator(close=close, window=14).rsi()

    # MACD
    macd = MACD(close=close)
    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    df["macd_hist"] = macd.macd_diff()

    # EMAs
    for period in [9, 21, 50, 200]:
        df[f"ema_{period}"] = EMAIndicator(close=close, window=period).ema_indicator()

    # Bollinger Bands
    bb = BollingerBands(close=close, window=20, window_dev=2)
    df["bb_upper"] = bb.bollinger_hband()
    df["bb_middle"] = bb.bollinger_mavg()
    df["bb_lower"] = bb.bollinger_lband()
    df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["bb_middle"]

    # ATR
    df["atr"] = AverageTrueRange(high=high, low=low, close=close, window=14).average_true_range()

    # Volume change
    df["volume_change"] = volume.pct_change()

    # Price returns
    df["returns"] = close.pct_change()
    df["returns_5"] = close.pct_change(5)
    df["returns_10"] = close.pct_change(10)

    # Volatility
    df["volatility"] = close.rolling(window=20).std() / close.rolling(window=20).mean()

    # Price position relative to BBands
    df["bb_position"] = (close - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"])

    df = df.dropna().reset_index(drop=True)
    return df


def normalize_features(df: pd.DataFrame, feature_columns: list) -> pd.DataFrame:
    df = df.copy()
    for col in feature_columns:
        if col in df.columns:
            mean = df[col].mean()
            std = df[col].std()
            if std > 0:
                df[col] = (df[col] - mean) / std
            else:
                df[col] = 0.0
    return df


FEATURE_COLUMNS = [
    "rsi", "macd", "macd_signal", "macd_hist",
    "ema_9", "ema_21", "ema_50", "ema_200",
    "bb_upper", "bb_middle", "bb_lower", "bb_width",
    "atr", "volume_change", "returns", "returns_5", "returns_10",
    "volatility", "bb_position",
]


def prepare_data_for_training(
    df: pd.DataFrame,
    train_ratio: float = 0.7,
    val_ratio: float = 0.15,
) -> tuple:
    df_with_indicators = add_technical_indicators(df)

    n = len(df_with_indicators)
    train_end = int(n * train_ratio)
    val_end = int(n * (train_ratio + val_ratio))

    train_df = df_with_indicators.iloc[:train_end].reset_index(drop=True)
    val_df = df_with_indicators.iloc[train_end:val_end].reset_index(drop=True)
    test_df = df_with_indicators.iloc[val_end:].reset_index(drop=True)

    return train_df, val_df, test_df
