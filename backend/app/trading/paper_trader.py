import logging
import threading
import time
from datetime import datetime
from typing import Optional
from app.trading.execution import OrderExecutor
from app.trading.risk_manager import RiskConfig
from app.database import get_connection
from app.data.binance_data import get_latest_price

logger = logging.getLogger(__name__)


class PaperTrader:
    def __init__(
        self,
        symbol: str = "BTC/USDT",
        initial_balance: float = 10.0,
        risk_config: Optional[RiskConfig] = None,
    ):
        self.symbol = symbol
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.coin_held = 0.0
        self.avg_buy_price = 0.0
        self.risk_config = risk_config or RiskConfig()
        self.executor = OrderExecutor(mode="paper", risk_config=self.risk_config)
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self.session_id: Optional[int] = None
        self.trade_history: list = []
        self.equity_history: list = []
        self.model = None

    def set_model(self, model):
        self.model = model

    def start(self) -> dict:
        if self.running:
            return {"status": "already_running"}

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO paper_sessions (initial_balance, current_balance, symbol, status, started_at)
               VALUES (?, ?, ?, 'running', ?)""",
            (self.initial_balance, self.balance, self.symbol, datetime.utcnow().isoformat()),
        )
        conn.commit()
        self.session_id = cursor.lastrowid
        conn.close()

        self.running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

        return {"status": "started", "session_id": self.session_id}

    def stop(self) -> dict:
        self.running = False
        if self._thread:
            self._thread.join(timeout=10)

        if self.session_id:
            conn = get_connection()
            conn.execute(
                """UPDATE paper_sessions SET status='stopped', current_balance=?,
                   coin_holdings=?, stopped_at=? WHERE id=?""",
                (self.balance, self.coin_held, datetime.utcnow().isoformat(), self.session_id),
            )
            conn.commit()
            conn.close()

        return {
            "status": "stopped",
            "balance": self.balance,
            "coin_held": self.coin_held,
            "equity": self.get_equity(),
        }

    def reset(self, new_balance: Optional[float] = None) -> dict:
        was_running = self.running
        if was_running:
            self.stop()

        self.balance = new_balance or self.initial_balance
        self.initial_balance = self.balance
        self.coin_held = 0.0
        self.avg_buy_price = 0.0
        self.trade_history = []
        self.equity_history = []

        return {"status": "reset", "balance": self.balance}

    def get_equity(self) -> float:
        price = get_latest_price(self.symbol)
        return self.balance + self.coin_held * price

    def get_unrealized_pnl(self) -> float:
        if self.coin_held <= 0:
            return 0.0
        price = get_latest_price(self.symbol)
        return (price - self.avg_buy_price) * self.coin_held

    def get_status(self) -> dict:
        equity = self.get_equity()
        pnl = equity - self.initial_balance
        return {
            "running": self.running,
            "session_id": self.session_id,
            "symbol": self.symbol,
            "initial_balance": self.initial_balance,
            "current_balance": round(self.balance, 6),
            "coin_held": round(self.coin_held, 8),
            "equity": round(equity, 6),
            "unrealized_pnl": round(self.get_unrealized_pnl(), 6),
            "pnl": round(pnl, 6),
            "return_pct": round(pnl / self.initial_balance * 100, 2) if self.initial_balance > 0 else 0,
            "num_trades": len(self.trade_history),
        }

    def execute_action(self, action: int) -> dict:
        price = get_latest_price(self.symbol)
        if price <= 0:
            return {"executed": False, "reason": "Cannot fetch price"}

        result = {"executed": False}

        if action in [1, 2, 3]:
            fractions = {1: 0.25, 2: 0.50, 3: 1.0}
            fraction = fractions[action]
            spend = self.balance * fraction
            result = self.executor.execute_market_buy(
                self.symbol, spend, self.balance, price
            )
            if result.get("executed"):
                self.balance -= spend
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
            fraction = fractions[action]
            qty = self.coin_held * fraction
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

        equity = self.get_equity()
        self.equity_history.append({
            "timestamp": datetime.utcnow().isoformat(),
            "equity": equity,
            "balance": self.balance,
        })

        if self.session_id:
            conn = get_connection()
            conn.execute(
                "UPDATE paper_sessions SET current_balance=?, coin_holdings=? WHERE id=?",
                (self.balance, self.coin_held, self.session_id),
            )
            conn.execute(
                """INSERT INTO equity_curve (mode, session_id, balance, equity, drawdown)
                   VALUES ('paper', ?, ?, ?, ?)""",
                (self.session_id, self.balance, equity, 0),
            )
            conn.commit()
            conn.close()

        return result

    def _run_loop(self):
        logger.info(f"Paper trading loop started for {self.symbol}")
        while self.running:
            try:
                if self.model is not None:
                    action = self._get_model_action()
                    if action != 0:
                        self.execute_action(action)
                time.sleep(60)
            except Exception as e:
                logger.error(f"Paper trading error: {e}")
                time.sleep(30)

    def _get_model_action(self) -> int:
        # Simplified: in production, build observation from live data
        # For now, return hold
        return 0
