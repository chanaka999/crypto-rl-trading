import pytest
import numpy as np
import pandas as pd
from app.data.preprocessing import add_technical_indicators, prepare_data_for_training


def make_sample_df(n=300):
    np.random.seed(42)
    prices = [50000.0]
    for _ in range(n - 1):
        change = np.random.normal(0, 0.01)
        prices.append(prices[-1] * (1 + change))

    return pd.DataFrame({
        "timestamp": range(n),
        "open": prices,
        "high": [p * 1.005 for p in prices],
        "low": [p * 0.995 for p in prices],
        "close": prices,
        "volume": [np.random.uniform(100, 1000) for _ in range(n)],
    })


class TestTechnicalIndicators:
    def test_adds_rsi(self):
        df = add_technical_indicators(make_sample_df())
        assert "rsi" in df.columns
        assert not df["rsi"].isna().any()

    def test_adds_macd(self):
        df = add_technical_indicators(make_sample_df())
        assert "macd" in df.columns
        assert "macd_signal" in df.columns
        assert "macd_hist" in df.columns

    def test_adds_emas(self):
        df = add_technical_indicators(make_sample_df())
        for period in [9, 21, 50, 200]:
            assert f"ema_{period}" in df.columns

    def test_adds_bollinger_bands(self):
        df = add_technical_indicators(make_sample_df())
        assert "bb_upper" in df.columns
        assert "bb_lower" in df.columns
        assert "bb_width" in df.columns

    def test_adds_atr(self):
        df = add_technical_indicators(make_sample_df())
        assert "atr" in df.columns

    def test_adds_returns(self):
        df = add_technical_indicators(make_sample_df())
        assert "returns" in df.columns
        assert "returns_5" in df.columns

    def test_no_nans_after_processing(self):
        df = add_technical_indicators(make_sample_df())
        assert not df.isna().any().any()

    def test_preserves_ohlcv(self):
        df = add_technical_indicators(make_sample_df())
        for col in ["open", "high", "low", "close", "volume"]:
            assert col in df.columns


class TestDataSplitting:
    def test_train_val_test_split(self):
        df = make_sample_df(500)
        train, val, test = prepare_data_for_training(df)
        assert len(train) > 0
        assert len(val) > 0
        assert len(test) > 0
        assert len(train) > len(val)
        assert len(train) > len(test)

    def test_no_data_leakage(self):
        df = make_sample_df(500)
        train, val, test = prepare_data_for_training(df)
        total = len(train) + len(val) + len(test)
        original = len(add_technical_indicators(df))
        assert total == original
