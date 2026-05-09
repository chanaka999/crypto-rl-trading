import ccxt
import logging
from datetime import datetime
from typing import Optional
from app.config import settings
from app.trading.risk_manager import RiskManager, RiskConfig
from app.database import get_connection

logger = logging.getLogger(__name__)


class OrderExecutor:
    """Handles order execution for both paper and live trading."""

    def __init__(
        self,
        mode: str = "paper",
        api_key: str = "",
        api_secret: str = "",
        risk_config: Optional[RiskConfig] = None,
    ):
        self.mode = mode
        self.risk_manager = RiskManager(risk_config or RiskConfig())

        if mode == "live" and api_key and api_secret:
            self.exchange = ccxt.binance({
                "apiKey": api_key,
                "secret": api_secret,
                "enableRateLimit": True,
                "options": {"defaultType": "spot"},
            })
        else:
            self.exchange = ccxt.binance({"enableRateLimit": True})

    def get_symbol_info(self, symbol: str) -> dict:
        try:
            markets = self.exchange.load_markets()
            if symbol in markets:
                market = markets[symbol]
                return {
                    "min_qty": market.get("limits", {}).get("amount", {}).get("min", 0.00001),
                    "min_notional": market.get("limits", {}).get("cost", {}).get("min", 5.0),
                    "qty_step": market.get("precision", {}).get("amount", 8),
                    "price_precision": market.get("precision", {}).get("price", 8),
                }
        except Exception as e:
            logger.error(f"Error loading market info: {e}")
        return {"min_qty": 0.00001, "min_notional": 5.0, "qty_step": 8, "price_precision": 8}

    def get_current_price(self, symbol: str) -> float:
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return ticker["last"]
        except Exception as e:
            logger.error(f"Error fetching price: {e}")
            return 0.0

    def get_account_balance(self) -> dict:
        if self.mode != "live":
            return {"error": "Not in live mode"}
        try:
            balance = self.exchange.fetch_balance()
            return {
                "USDT": {
                    "free": balance.get("USDT", {}).get("free", 0),
                    "used": balance.get("USDT", {}).get("used", 0),
                    "total": balance.get("USDT", {}).get("total", 0),
                },
                "total_usdt": balance.get("USDT", {}).get("total", 0),
            }
        except Exception as e:
            logger.error(f"Error fetching balance: {e}")
            self.risk_manager.record_api_failure()
            return {"error": str(e)}

    def execute_market_buy(
        self, symbol: str, spend_amount: float, balance: float, price: float,
    ) -> dict:
        can_trade, reason = self.risk_manager.can_trade(balance, balance)
        if not can_trade:
            return {"executed": False, "reason": reason}

        valid, msg = self.risk_manager.validate_buy(balance, spend_amount, price)
        if not valid:
            return {"executed": False, "reason": msg}

        slippage = price * (self.risk_manager.config.slippage_pct / 100)
        exec_price = price + slippage
        fee_amount = spend_amount * (self.risk_manager.config.fee_pct / 100)
        qty = (spend_amount - fee_amount) / exec_price

        if self.mode == "live":
            try:
                order = self.exchange.create_market_buy_order(symbol, qty)
                self.risk_manager.record_api_success()
                exec_price = order.get("average", exec_price)
                qty = order.get("filled", qty)
                fee_amount = sum(f.get("cost", 0) for f in order.get("fees", []))

                result = {
                    "executed": True,
                    "side": "BUY",
                    "price": exec_price,
                    "quantity": qty,
                    "fee": fee_amount,
                    "slippage": slippage * qty,
                    "order_id": order.get("id", ""),
                    "balance_before": balance,
                    "balance_after": balance - spend_amount,
                    "pnl": 0.0,
                }
                self._log_trade(result, symbol)
                self.risk_manager.record_trade(0)
                return result
            except Exception as e:
                logger.error(f"Live buy error: {e}")
                self.risk_manager.record_api_failure()
                return {"executed": False, "reason": str(e)}
        else:
            result = {
                "executed": True,
                "side": "BUY",
                "price": exec_price,
                "quantity": qty,
                "fee": fee_amount,
                "slippage": slippage * qty,
                "balance_before": balance,
                "balance_after": balance - spend_amount,
                "pnl": 0.0,
            }
            self._log_trade(result, symbol)
            self.risk_manager.record_trade(0)
            return result

    def execute_market_sell(
        self, symbol: str, qty: float, coin_held: float,
        price: float, avg_buy_price: float, balance: float,
    ) -> dict:
        can_trade, reason = self.risk_manager.can_trade(balance, balance)
        if not can_trade:
            return {"executed": False, "reason": reason}

        valid, msg = self.risk_manager.validate_sell(coin_held, qty, price)
        if not valid:
            return {"executed": False, "reason": msg}

        slippage = price * (self.risk_manager.config.slippage_pct / 100)
        exec_price = price - slippage
        notional = qty * exec_price
        fee_amount = notional * (self.risk_manager.config.fee_pct / 100)
        proceeds = notional - fee_amount
        pnl = (exec_price - avg_buy_price) * qty - fee_amount

        if self.mode == "live":
            try:
                order = self.exchange.create_market_sell_order(symbol, qty)
                self.risk_manager.record_api_success()
                exec_price = order.get("average", exec_price)
                qty = order.get("filled", qty)
                fee_amount = sum(f.get("cost", 0) for f in order.get("fees", []))
                proceeds = qty * exec_price - fee_amount
                pnl = (exec_price - avg_buy_price) * qty - fee_amount

                result = {
                    "executed": True,
                    "side": "SELL",
                    "price": exec_price,
                    "quantity": qty,
                    "fee": fee_amount,
                    "slippage": slippage * qty,
                    "order_id": order.get("id", ""),
                    "balance_before": balance,
                    "balance_after": balance + proceeds,
                    "pnl": pnl,
                }
                self._log_trade(result, symbol)
                self.risk_manager.record_trade(pnl)
                return result
            except Exception as e:
                logger.error(f"Live sell error: {e}")
                self.risk_manager.record_api_failure()
                return {"executed": False, "reason": str(e)}
        else:
            result = {
                "executed": True,
                "side": "SELL",
                "price": exec_price,
                "quantity": qty,
                "fee": fee_amount,
                "slippage": slippage * qty,
                "balance_before": balance,
                "balance_after": balance + proceeds,
                "pnl": pnl,
            }
            self._log_trade(result, symbol)
            self.risk_manager.record_trade(pnl)
            return result

    def _log_trade(self, trade: dict, symbol: str):
        conn = get_connection()
        conn.execute(
            """INSERT INTO trades
               (timestamp, mode, symbol, side, price, quantity, fee, slippage,
                pnl, balance_before, balance_after)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                datetime.utcnow().isoformat(),
                self.mode, symbol,
                trade["side"], trade["price"], trade["quantity"],
                trade["fee"], trade["slippage"], trade.get("pnl", 0),
                trade["balance_before"], trade["balance_after"],
            ),
        )
        conn.commit()
        conn.close()
