import gymnasium as gym
from gymnasium import spaces
import numpy as np
import pandas as pd
from typing import Optional


class CryptoTradingEnv(gym.Env):
    """Custom Gymnasium environment for crypto spot trading with RL."""

    metadata = {"render_modes": ["human"]}

    # Actions: 0=Hold, 1=Buy25%, 2=Buy50%, 3=Buy100%, 4=Sell25%, 5=Sell50%, 6=Sell100%
    ACTION_HOLD = 0
    ACTION_BUY_25 = 1
    ACTION_BUY_50 = 2
    ACTION_BUY_100 = 3
    ACTION_SELL_25 = 4
    ACTION_SELL_50 = 5
    ACTION_SELL_100 = 6

    FEATURE_COLUMNS = [
        "open", "high", "low", "close", "volume",
        "rsi", "macd", "macd_signal", "macd_hist",
        "ema_9", "ema_21", "ema_50", "ema_200",
        "bb_upper", "bb_middle", "bb_lower", "bb_width",
        "atr", "volume_change", "returns", "returns_5", "returns_10",
        "volatility", "bb_position",
    ]

    def __init__(
        self,
        df: pd.DataFrame,
        initial_balance: float = 10.0,
        fee_pct: float = 0.1,
        slippage_pct: float = 0.05,
        max_position_pct: float = 100.0,
        stop_loss_pct: float = 5.0,
        take_profit_pct: float = 10.0,
        daily_max_loss_pct: float = 10.0,
        monthly_target_return_pct: float = 100.0,
        min_notional: float = 5.0,
        min_qty: float = 0.00001,
        min_profit_over_fees: bool = True,
        window_size: int = 1,
    ):
        super().__init__()

        self.df = df.reset_index(drop=True)
        self.initial_balance = initial_balance
        self.fee_pct = fee_pct / 100.0
        self.slippage_pct = slippage_pct / 100.0
        self.max_position_pct = max_position_pct / 100.0
        self.stop_loss_pct = stop_loss_pct / 100.0
        self.take_profit_pct = take_profit_pct / 100.0
        self.daily_max_loss_pct = daily_max_loss_pct / 100.0
        self.monthly_target_return_pct = monthly_target_return_pct / 100.0
        self.min_notional = min_notional
        self.min_qty = min_qty
        self.min_profit_over_fees = min_profit_over_fees
        self.window_size = window_size

        available = [c for c in self.FEATURE_COLUMNS if c in df.columns]
        self.feature_columns = available

        n_features = len(self.feature_columns)
        # Observation: market features + [balance_ratio, holdings_ratio, unrealized_pnl_ratio, position_flag, drawdown, steps_ratio]
        obs_size = n_features + 6

        self.action_space = spaces.Discrete(7)
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf, shape=(obs_size,), dtype=np.float32
        )

        self.reset()

    def _normalize_market_data(self):
        data = self.df[self.feature_columns].values.astype(np.float32)
        self._mean = np.nanmean(data, axis=0)
        self._std = np.nanstd(data, axis=0)
        self._std[self._std == 0] = 1.0
        self._normalized_data = (data - self._mean) / self._std

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.balance = self.initial_balance
        self.coin_held = 0.0
        self.avg_buy_price = 0.0
        self.current_step = 0
        self.total_trades = 0
        self.wins = 0
        self.losses = 0
        self.peak_equity = self.initial_balance
        self.max_drawdown = 0.0
        self.trade_history = []
        self.equity_history = [self.initial_balance]
        self.daily_pnl = 0.0
        self.last_trade_step = -999

        self._normalize_market_data()

        return self._get_observation(), {}

    def _get_current_price(self) -> float:
        return float(self.df.iloc[self.current_step]["close"])

    def _get_equity(self) -> float:
        price = self._get_current_price()
        return self.balance + self.coin_held * price

    def _get_unrealized_pnl(self) -> float:
        if self.coin_held <= 0:
            return 0.0
        price = self._get_current_price()
        return (price - self.avg_buy_price) * self.coin_held

    def _get_observation(self) -> np.ndarray:
        market_features = self._normalized_data[self.current_step]

        equity = self._get_equity()
        balance_ratio = self.balance / self.initial_balance
        holdings_value = self.coin_held * self._get_current_price()
        holdings_ratio = holdings_value / self.initial_balance if self.initial_balance > 0 else 0.0
        unrealized_pnl_ratio = self._get_unrealized_pnl() / self.initial_balance if self.initial_balance > 0 else 0.0
        position_flag = 1.0 if self.coin_held > 0 else 0.0
        drawdown = (self.peak_equity - equity) / self.peak_equity if self.peak_equity > 0 else 0.0
        steps_ratio = self.current_step / max(len(self.df) - 1, 1)

        account_features = np.array([
            balance_ratio, holdings_ratio, unrealized_pnl_ratio,
            position_flag, drawdown, steps_ratio,
        ], dtype=np.float32)

        obs = np.concatenate([market_features, account_features])
        obs = np.nan_to_num(obs, nan=0.0, posinf=0.0, neginf=0.0)
        return obs

    def _apply_slippage(self, price: float, side: str) -> float:
        if side == "buy":
            return price * (1 + self.slippage_pct)
        else:
            return price * (1 - self.slippage_pct)

    def _calculate_fee(self, notional: float) -> float:
        return notional * self.fee_pct

    def _execute_buy(self, fraction: float) -> dict:
        price = self._get_current_price()
        exec_price = self._apply_slippage(price, "buy")

        max_spend = self.balance * fraction * self.max_position_pct
        if max_spend < self.min_notional:
            return {"executed": False, "reason": "below_min_notional"}

        fee = self._calculate_fee(max_spend)
        spend_after_fee = max_spend - fee
        qty = spend_after_fee / exec_price

        if qty < self.min_qty:
            return {"executed": False, "reason": "below_min_qty"}

        if self.min_profit_over_fees:
            expected_fee_round_trip = self._calculate_fee(max_spend) * 2
            if max_spend * 0.02 < expected_fee_round_trip:
                pass  # Allow but note it

        balance_before = self.balance
        self.balance -= max_spend

        if self.coin_held > 0:
            total_cost = self.avg_buy_price * self.coin_held + exec_price * qty
            self.coin_held += qty
            self.avg_buy_price = total_cost / self.coin_held
        else:
            self.coin_held = qty
            self.avg_buy_price = exec_price

        self.total_trades += 1
        self.last_trade_step = self.current_step

        trade = {
            "executed": True,
            "side": "BUY",
            "price": exec_price,
            "quantity": qty,
            "fee": fee,
            "slippage": abs(exec_price - price) * qty,
            "balance_before": balance_before,
            "balance_after": self.balance,
            "pnl": 0.0,
        }
        self.trade_history.append(trade)
        return trade

    def _execute_sell(self, fraction: float) -> dict:
        if self.coin_held <= 0:
            return {"executed": False, "reason": "no_holdings"}

        price = self._get_current_price()
        exec_price = self._apply_slippage(price, "sell")
        qty = self.coin_held * fraction

        if qty < self.min_qty:
            return {"executed": False, "reason": "below_min_qty"}

        notional = qty * exec_price
        if notional < self.min_notional:
            if fraction < 1.0:
                return {"executed": False, "reason": "below_min_notional"}
            # Allow full sell even if below notional to exit position

        fee = self._calculate_fee(notional)
        proceeds = notional - fee
        pnl = (exec_price - self.avg_buy_price) * qty - fee

        balance_before = self.balance
        self.balance += proceeds
        self.coin_held -= qty

        if self.coin_held < self.min_qty:
            self.coin_held = 0.0
            self.avg_buy_price = 0.0

        self.total_trades += 1
        self.last_trade_step = self.current_step

        if pnl > 0:
            self.wins += 1
        elif pnl < 0:
            self.losses += 1

        self.daily_pnl += pnl

        trade = {
            "executed": True,
            "side": "SELL",
            "price": exec_price,
            "quantity": qty,
            "fee": fee,
            "slippage": abs(exec_price - price) * qty,
            "balance_before": balance_before,
            "balance_after": self.balance,
            "pnl": pnl,
        }
        self.trade_history.append(trade)
        return trade

    def _check_stop_loss_take_profit(self):
        if self.coin_held <= 0:
            return

        price = self._get_current_price()
        pnl_pct = (price - self.avg_buy_price) / self.avg_buy_price if self.avg_buy_price > 0 else 0

        if pnl_pct <= -self.stop_loss_pct:
            self._execute_sell(1.0)
        elif pnl_pct >= self.take_profit_pct:
            self._execute_sell(1.0)

    def step(self, action: int):
        prev_equity = self._get_equity()

        self._check_stop_loss_take_profit()

        trade_result = {"executed": False}
        if action == self.ACTION_BUY_25:
            trade_result = self._execute_buy(0.25)
        elif action == self.ACTION_BUY_50:
            trade_result = self._execute_buy(0.50)
        elif action == self.ACTION_BUY_100:
            trade_result = self._execute_buy(1.0)
        elif action == self.ACTION_SELL_25:
            trade_result = self._execute_sell(0.25)
        elif action == self.ACTION_SELL_50:
            trade_result = self._execute_sell(0.50)
        elif action == self.ACTION_SELL_100:
            trade_result = self._execute_sell(1.0)

        self.current_step += 1
        done = self.current_step >= len(self.df) - 1

        current_equity = self._get_equity()
        self.equity_history.append(current_equity)

        if current_equity > self.peak_equity:
            self.peak_equity = current_equity
        current_drawdown = (self.peak_equity - current_equity) / self.peak_equity
        self.max_drawdown = max(self.max_drawdown, current_drawdown)

        if current_drawdown >= self.daily_max_loss_pct:
            done = True

        reward = self._calculate_reward(prev_equity, current_equity, trade_result, action)

        truncated = False
        info = {
            "equity": current_equity,
            "balance": self.balance,
            "holdings": self.coin_held,
            "drawdown": current_drawdown,
            "max_drawdown": self.max_drawdown,
            "total_trades": self.total_trades,
            "trade_result": trade_result,
        }

        return self._get_observation(), reward, done, truncated, info

    def _calculate_reward(self, prev_equity: float, curr_equity: float, trade: dict, action: int) -> float:
        equity_change = (curr_equity - prev_equity) / self.initial_balance

        # Drawdown penalty
        current_dd = (self.peak_equity - curr_equity) / self.peak_equity if self.peak_equity > 0 else 0
        drawdown_penalty = -current_dd * 0.5

        # Overtrading penalty
        steps_since_last = self.current_step - self.last_trade_step
        overtrading_penalty = 0.0
        if trade.get("executed", False) and steps_since_last < 3:
            overtrading_penalty = -0.001

        # Fee penalty
        fee_penalty = 0.0
        if trade.get("executed", False):
            fee_penalty = -trade.get("fee", 0) / self.initial_balance * 2

        # Failed trade penalty
        failed_penalty = 0.0
        if action != self.ACTION_HOLD and not trade.get("executed", False):
            failed_penalty = -0.001

        # Survival bonus
        survival_bonus = 0.0001

        # Aggressive target bonus
        target_bonus = 0.0
        total_return = (curr_equity - self.initial_balance) / self.initial_balance
        if total_return > 0:
            target_bonus = total_return * 0.01

        reward = (
            equity_change * 10.0
            + drawdown_penalty
            + overtrading_penalty
            + fee_penalty
            + failed_penalty
            + survival_bonus
            + target_bonus
        )

        return float(np.clip(reward, -10.0, 10.0))

    def get_metrics(self) -> dict:
        equity = self._get_equity()
        net_profit = equity - self.initial_balance
        return_pct = (net_profit / self.initial_balance) * 100 if self.initial_balance > 0 else 0
        win_rate = (self.wins / max(self.total_trades, 1)) * 100

        returns = []
        for i in range(1, len(self.equity_history)):
            r = (self.equity_history[i] - self.equity_history[i-1]) / self.equity_history[i-1]
            returns.append(r)

        sharpe = 0.0
        if returns:
            avg_ret = np.mean(returns)
            std_ret = np.std(returns)
            if std_ret > 0:
                sharpe = (avg_ret / std_ret) * np.sqrt(252)

        wins_list = [t["pnl"] for t in self.trade_history if t.get("pnl", 0) > 0]
        losses_list = [t["pnl"] for t in self.trade_history if t.get("pnl", 0) < 0]
        avg_win = np.mean(wins_list) if wins_list else 0.0
        avg_loss = np.mean(losses_list) if losses_list else 0.0
        total_wins = sum(wins_list)
        total_losses = abs(sum(losses_list))
        profit_factor = total_wins / total_losses if total_losses > 0 else float("inf") if total_wins > 0 else 0.0

        return {
            "initial_balance": self.initial_balance,
            "final_balance": round(equity, 6),
            "net_profit": round(net_profit, 6),
            "return_pct": round(return_pct, 2),
            "max_drawdown": round(self.max_drawdown * 100, 2),
            "num_trades": self.total_trades,
            "win_rate": round(win_rate, 2),
            "avg_win": round(avg_win, 6),
            "avg_loss": round(avg_loss, 6),
            "profit_factor": round(profit_factor, 2),
            "sharpe_ratio": round(sharpe, 2),
        }
