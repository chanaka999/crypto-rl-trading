import logging
import threading
import time
from datetime import datetime
from typing import Optional
from app.trading.execution import OrderExecutor
from app.trading.risk_manager import RiskConfig, RiskManager
from app.database import get_connection

logger = logging.getLogger(__name__)


class LiveTrader:
    def __init__(
        self,
        symbol: str = "BTC/USDT",
        api_key: str = "",
        api_secret: str = "",
        risk_config: Optional[RiskConfig] = None,
    ):
        self.symbol = symbol
        self.api_key = api_key
        self.api_secret = api_secret
        self.risk_config = risk_config or RiskConfig()
        self.executor = OrderExecutor(
            mode="live", api_key=api_key, api_secret=api_secret,
            risk_config=self.risk_config,
        )
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self.model = None
        self.balance = 0.0
        self.coin_held = 0.0
        self.avg_buy_price = 0.0
        self.trade_history: list = []
        self.connected = False

    def check_connection(self) -> dict:
        try:
            balance = self.executor.get_account_balance()
            if "error" in balance:
                self.connected = False
                return {"connected": False, "error": balance["error"]}
            self.connected = True
            self.balance = balance.get("total_usdt", 0)
            return {"connected": True, "balance": balance}
        except Exception as e:
            self.connected = False
            return {"connected": False, "error": str(e)}

    def set_model(self, model):
        self.model = model

    def start(self, confirmed: bool = False) -> dict:
        if not confirmed:
            return {
                "status": "confirmation_required",
                "message": "WARNING: You are about to enable LIVE trading with REAL money. "
                           "Losses are possible and not guaranteed to be recoverable. "
                           "Please confirm to proceed.",
            }

        if self.running:
            return {"status": "already_running"}

        if not self.api_key or not self.api_secret:
            return {"status": "error", "message": "Binance API key and secret are required"}

        conn_status = self.check_connection()
        if not conn_status.get("connected"):
            return {"status": "error", "message": f"Cannot connect to Binance: {conn_status.get('error')}"}

        warnings = self.executor.risk_manager.get_small_account_warnings(self.balance)

        self.running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

        return {
            "status": "started",
            "balance": self.balance,
            "warnings": warnings,
        }

    def stop(self) -> dict:
        self.running = False
        if self._thread:
            self._thread.join(timeout=10)
        return {
            "status": "stopped",
            "balance": self.balance,
            "coin_held": self.coin_held,
        }

    def emergency_stop(self) -> dict:
        self.running = False
        self.executor.risk_manager.activate_emergency_stop()
        if self._thread:
            self._thread.join(timeout=10)

        result = {"status": "emergency_stopped", "balance": self.balance}

        if self.coin_held > 0:
            try:
                price = self.executor.get_current_price(self.symbol)
                sell_result = self.executor.execute_market_sell(
                    self.symbol, self.coin_held, self.coin_held,
                    price, self.avg_buy_price, self.balance,
                )
                if sell_result.get("executed"):
                    self.balance = sell_result["balance_after"]
                    self.coin_held = 0
                    result["emergency_sell"] = sell_result
            except Exception as e:
                logger.error(f"Emergency sell failed: {e}")
                result["emergency_sell_error"] = str(e)

        return result

    def get_status(self) -> dict:
        equity = self.balance
        if self.coin_held > 0:
            price = self.executor.get_current_price(self.symbol)
            equity += self.coin_held * price

        return {
            "running": self.running,
            "connected": self.connected,
            "symbol": self.symbol,
            "balance": round(self.balance, 6),
            "coin_held": round(self.coin_held, 8),
            "equity": round(equity, 6),
            "avg_buy_price": round(self.avg_buy_price, 6),
            "num_trades": len(self.trade_history),
            "emergency_stop_active": self.executor.risk_manager.emergency_stop,
        }

    def _run_loop(self):
        logger.info(f"Live trading loop started for {self.symbol}")
        while self.running:
            try:
                balance_info = self.executor.get_account_balance()
                if "error" not in balance_info:
                    self.balance = balance_info.get("total_usdt", self.balance)

                if self.model is not None:
                    action = self._get_model_action()
                    if action != 0:
                        self._execute_action(action)

                price = self.executor.get_current_price(self.symbol)
                equity = self.balance + self.coin_held * price
                self.executor.risk_manager.update_peak_equity(equity)

                conn = get_connection()
                conn.execute(
                    """INSERT INTO equity_curve (mode, balance, equity, drawdown)
                       VALUES ('live', ?, ?, ?)""",
                    (self.balance, equity,
                     self.executor.risk_manager.get_current_drawdown(equity)),
                )
                conn.commit()
                conn.close()

                time.sleep(60)
            except Exception as e:
                logger.error(f"Live trading error: {e}")
                self.executor.risk_manager.record_api_failure()
                time.sleep(30)

    def _execute_action(self, action: int):
        price = self.executor.get_current_price(self.symbol)
        if price <= 0:
            return

        if action in [1, 2, 3]:
            fractions = {1: 0.25, 2: 0.50, 3: 1.0}
            spend = self.balance * fractions[action]
            result = self.executor.execute_market_buy(
                self.symbol, spend, self.balance, price
            )
            if result.get("executed"):
                self.balance = result["balance_after"]
                qty = result["quantity"]
                if self.coin_held > 0:
                    total_cost = self.avg_buy_price * self.coin_held + result["price"] * qty
                    self.coin_held += qty
                    self.avg_buy_price = total_cost / self.coin_held
                else:
                    self.coin_held = qty
                    self.avg_buy_price = result["price"]
                self.trade_history.append(result)

        elif action in [4, 5, 6]:
            fractions = {4: 0.25, 5: 0.50, 6: 1.0}
            qty = self.coin_held * fractions[action]
            result = self.executor.execute_market_sell(
                self.symbol, qty, self.coin_held,
                price, self.avg_buy_price, self.balance
            )
            if result.get("executed"):
                self.balance = result["balance_after"]
                self.coin_held -= result["quantity"]
                if self.coin_held < 0.00001:
                    self.coin_held = 0.0
                    self.avg_buy_price = 0.0
                self.trade_history.append(result)

    def _get_model_action(self) -> int:
        return 0
