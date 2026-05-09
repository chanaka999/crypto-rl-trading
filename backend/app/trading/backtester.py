import json
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Optional
from app.trading.environment import CryptoTradingEnv
from app.data.preprocessing import add_technical_indicators
from app.database import get_connection


class Backtester:
    def __init__(
        self,
        df: pd.DataFrame,
        initial_balance: float = 10.0,
        fee_pct: float = 0.1,
        slippage_pct: float = 0.05,
        stop_loss_pct: float = 5.0,
        take_profit_pct: float = 10.0,
        min_notional: float = 5.0,
        min_qty: float = 0.00001,
        min_profit_over_fees: bool = True,
    ):
        self.raw_df = df
        self.initial_balance = initial_balance
        self.fee_pct = fee_pct
        self.slippage_pct = slippage_pct
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.min_notional = min_notional
        self.min_qty = min_qty
        self.min_profit_over_fees = min_profit_over_fees

    def run(self, model, symbol: str = "BTC/USDT", timeframe: str = "1h") -> dict:
        df = add_technical_indicators(self.raw_df)
        if df.empty or len(df) < 10:
            return {"error": "Insufficient data after adding indicators"}

        env = CryptoTradingEnv(
            df=df,
            initial_balance=self.initial_balance,
            fee_pct=self.fee_pct,
            slippage_pct=self.slippage_pct,
            stop_loss_pct=self.stop_loss_pct,
            take_profit_pct=self.take_profit_pct,
            min_notional=self.min_notional,
            min_qty=self.min_qty,
            min_profit_over_fees=self.min_profit_over_fees,
        )

        obs, _ = env.reset()
        done = False
        step_actions = []

        while not done:
            action, _ = model.predict(obs, deterministic=True)
            obs, reward, done, truncated, info = env.step(int(action))
            step_actions.append({
                "step": env.current_step,
                "action": int(action),
                "equity": info["equity"],
                "balance": info["balance"],
            })
            if truncated:
                break

        metrics = env.get_metrics()

        trades_for_db = []
        for t in env.trade_history:
            step_idx = len(trades_for_db)
            timestamp_ms = int(df.iloc[min(step_idx, len(df)-1)].get("timestamp", 0))
            trades_for_db.append({
                "timestamp": datetime.utcfromtimestamp(timestamp_ms / 1000).isoformat() if timestamp_ms else datetime.utcnow().isoformat(),
                "side": t["side"],
                "price": t["price"],
                "quantity": t["quantity"],
                "fee": t["fee"],
                "slippage": t["slippage"],
                "pnl": t.get("pnl", 0),
                "balance_before": t["balance_before"],
                "balance_after": t["balance_after"],
            })

        equity_curve = []
        for i, eq in enumerate(env.equity_history):
            dd = 0.0
            peak = max(env.equity_history[:i+1])
            if peak > 0:
                dd = (peak - eq) / peak * 100
            equity_curve.append({"step": i, "equity": round(eq, 6), "drawdown": round(dd, 2)})

        monthly_returns = self._calculate_monthly_returns(df, env.equity_history)

        start_date = ""
        end_date = ""
        if "timestamp" in df.columns and len(df) > 0:
            start_date = datetime.utcfromtimestamp(int(df.iloc[0]["timestamp"]) / 1000).strftime("%Y-%m-%d")
            end_date = datetime.utcfromtimestamp(int(df.iloc[-1]["timestamp"]) / 1000).strftime("%Y-%m-%d")

        result = {
            **metrics,
            "symbol": symbol,
            "timeframe": timeframe,
            "start_date": start_date,
            "end_date": end_date,
            "fee_pct": self.fee_pct,
            "slippage_pct": self.slippage_pct,
            "trades": trades_for_db,
            "equity_curve": equity_curve,
            "monthly_returns": monthly_returns,
        }

        return result

    def _calculate_monthly_returns(self, df: pd.DataFrame, equity_history: list) -> list:
        if "timestamp" not in df.columns or len(equity_history) < 2:
            return []

        monthly = {}
        for i in range(len(equity_history)):
            if i >= len(df):
                break
            ts = int(df.iloc[i]["timestamp"])
            dt = datetime.utcfromtimestamp(ts / 1000)
            month_key = dt.strftime("%Y-%m")
            if month_key not in monthly:
                monthly[month_key] = {"start_equity": equity_history[i]}
            monthly[month_key]["end_equity"] = equity_history[i]

        result = []
        for month, data in monthly.items():
            start_eq = data["start_equity"]
            end_eq = data["end_equity"]
            ret_pct = ((end_eq - start_eq) / start_eq * 100) if start_eq > 0 else 0
            result.append({"month": month, "return_pct": round(ret_pct, 2)})

        return result

    def save_result(self, result: dict, model_name: str = "") -> int:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO backtest_runs
               (symbol, timeframe, start_date, end_date, initial_balance, final_balance,
                net_profit, return_pct, max_drawdown, num_trades, win_rate,
                avg_win, avg_loss, profit_factor, sharpe_ratio,
                fee_pct, slippage_pct, model_name,
                trades_json, equity_curve_json, monthly_returns_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                result.get("symbol", ""),
                result.get("timeframe", ""),
                result.get("start_date", ""),
                result.get("end_date", ""),
                result.get("initial_balance", 0),
                result.get("final_balance", 0),
                result.get("net_profit", 0),
                result.get("return_pct", 0),
                result.get("max_drawdown", 0),
                result.get("num_trades", 0),
                result.get("win_rate", 0),
                result.get("avg_win", 0),
                result.get("avg_loss", 0),
                result.get("profit_factor", 0),
                result.get("sharpe_ratio", 0),
                result.get("fee_pct", 0.1),
                result.get("slippage_pct", 0.05),
                model_name,
                json.dumps(result.get("trades", [])),
                json.dumps(result.get("equity_curve", [])),
                json.dumps(result.get("monthly_returns", [])),
            ),
        )
        conn.commit()
        run_id = cursor.lastrowid
        conn.close()

        for trade in result.get("trades", []):
            self._save_trade(trade, "backtest", result.get("symbol", ""))

        return run_id

    def _save_trade(self, trade: dict, mode: str, symbol: str):
        conn = get_connection()
        conn.execute(
            """INSERT INTO trades
               (timestamp, mode, symbol, side, price, quantity, fee, slippage,
                pnl, balance_before, balance_after)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                trade.get("timestamp", datetime.utcnow().isoformat()),
                mode, symbol,
                trade["side"], trade["price"], trade["quantity"],
                trade["fee"], trade["slippage"], trade.get("pnl", 0),
                trade["balance_before"], trade["balance_after"],
            ),
        )
        conn.commit()
        conn.close()
