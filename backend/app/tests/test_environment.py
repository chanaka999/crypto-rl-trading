import pytest
import numpy as np
import pandas as pd
from app.trading.environment import CryptoTradingEnv
from app.data.preprocessing import add_technical_indicators


def make_sample_df(n=300, start_price=50000):
    np.random.seed(42)
    prices = [start_price]
    for _ in range(n - 1):
        change = np.random.normal(0, 0.01)
        prices.append(prices[-1] * (1 + change))

    df = pd.DataFrame({
        "timestamp": range(n),
        "open": prices,
        "high": [p * 1.005 for p in prices],
        "low": [p * 0.995 for p in prices],
        "close": prices,
        "volume": [np.random.uniform(100, 1000) for _ in range(n)],
    })
    return df


def make_env(n=300, balance=10.0):
    df = make_sample_df(n)
    df = add_technical_indicators(df)
    return CryptoTradingEnv(df=df, initial_balance=balance, fee_pct=0.1, slippage_pct=0.05)


class TestCryptoTradingEnv:
    def test_reset(self):
        env = make_env()
        obs, info = env.reset()
        assert obs.shape[0] > 0
        assert env.balance == 10.0
        assert env.coin_held == 0.0
        assert env.total_trades == 0

    def test_action_space(self):
        env = make_env()
        assert env.action_space.n == 7

    def test_hold_action(self):
        env = make_env()
        obs, _ = env.reset()
        obs, reward, done, truncated, info = env.step(0)
        assert env.balance == 10.0
        assert env.coin_held == 0.0
        assert env.total_trades == 0

    def test_buy_action(self):
        env = make_env(balance=100.0)
        env.reset()
        obs, reward, done, truncated, info = env.step(3)  # Buy 100%
        assert env.coin_held > 0
        assert env.balance < 100.0
        assert env.total_trades == 1

    def test_sell_without_holdings(self):
        env = make_env()
        env.reset()
        obs, reward, done, truncated, info = env.step(6)  # Sell 100%
        assert env.coin_held == 0.0
        assert env.total_trades == 0  # No trade executed

    def test_buy_then_sell(self):
        env = make_env(balance=100.0)
        env.reset()
        env.step(3)  # Buy 100%
        assert env.coin_held > 0
        initial_coin = env.coin_held
        env.step(6)  # Sell 100%
        assert env.coin_held == 0.0
        assert env.total_trades == 2

    def test_partial_buy(self):
        env = make_env(balance=100.0)
        env.reset()
        env.step(1)  # Buy 25%
        assert env.balance > 70.0
        assert env.coin_held > 0

    def test_partial_sell(self):
        env = make_env(balance=100.0)
        env.reset()
        env.step(3)  # Buy 100%
        full_holdings = env.coin_held
        env.step(4)  # Sell 25%
        assert env.coin_held < full_holdings
        assert env.coin_held > 0

    def test_fees_applied(self):
        env = make_env(balance=100.0)
        env.reset()
        initial_balance = env.balance
        env.step(3)  # Buy 100%
        env.step(6)  # Sell 100%
        # After round-trip, balance should be less due to fees
        assert env.balance < initial_balance

    def test_observation_shape(self):
        env = make_env()
        obs, _ = env.reset()
        assert len(obs.shape) == 1
        assert obs.shape == env.observation_space.shape

    def test_no_nan_in_obs(self):
        env = make_env()
        obs, _ = env.reset()
        assert not np.any(np.isnan(obs))

    def test_episode_ends(self):
        env = make_env(n=300)
        obs, _ = env.reset()
        done = False
        steps = 0
        while not done and steps < 500:
            obs, _, done, truncated, _ = env.step(0)
            steps += 1
            if truncated:
                break
        assert done or steps >= 200

    def test_metrics(self):
        env = make_env(balance=100.0)
        env.reset()
        env.step(3)
        env.step(0)
        env.step(6)
        metrics = env.get_metrics()
        assert "initial_balance" in metrics
        assert "final_balance" in metrics
        assert "return_pct" in metrics
        assert "max_drawdown" in metrics
        assert "win_rate" in metrics
        assert "sharpe_ratio" in metrics

    def test_min_notional_prevents_small_buys(self):
        env = make_env(balance=1.0)  # Very small balance
        env.reset()
        obs, reward, done, truncated, info = env.step(1)  # Buy 25% of $1 = $0.25
        # Should not execute since 0.25 < min_notional (5.0)
        assert env.coin_held == 0.0

    def test_slippage_increases_buy_price(self):
        env = make_env(balance=100.0)
        env.reset()
        price = env._get_current_price()
        exec_price = env._apply_slippage(price, "buy")
        assert exec_price > price

    def test_slippage_decreases_sell_price(self):
        env = make_env(balance=100.0)
        env.reset()
        price = env._get_current_price()
        exec_price = env._apply_slippage(price, "sell")
        assert exec_price < price


class TestRewardFunction:
    def test_hold_reward_is_small(self):
        env = make_env()
        env.reset()
        _, reward, _, _, _ = env.step(0)
        assert abs(reward) < 1.0

    def test_reward_bounded(self):
        env = make_env(balance=100.0)
        env.reset()
        for _ in range(50):
            action = np.random.randint(0, 7)
            _, reward, done, truncated, _ = env.step(action)
            assert -10 <= reward <= 10
            if done or truncated:
                break
