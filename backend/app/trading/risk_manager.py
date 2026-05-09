from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional


@dataclass
class RiskConfig:
    max_position_pct: float = 100.0
    stop_loss_pct: float = 5.0
    take_profit_pct: float = 10.0
    daily_max_loss_pct: float = 10.0
    max_drawdown_stop_pct: float = 20.0
    cooldown_seconds: int = 60
    min_notional: float = 5.0
    min_qty: float = 0.00001
    min_profit_over_fees: bool = True
    fee_pct: float = 0.1
    slippage_pct: float = 0.05
    monthly_target_return_pct: float = 100.0


class RiskManager:
    def __init__(self, config: RiskConfig):
        self.config = config
        self.daily_pnl = 0.0
        self.daily_reset_time: Optional[datetime] = None
        self.last_trade_time: Optional[datetime] = None
        self.peak_equity = 0.0
        self.emergency_stop = False
        self.consecutive_failures = 0
        self.max_consecutive_failures = 5

    def reset_daily(self):
        now = datetime.utcnow()
        if self.daily_reset_time is None or now.date() > self.daily_reset_time.date():
            self.daily_pnl = 0.0
            self.daily_reset_time = now

    def update_peak_equity(self, equity: float):
        if equity > self.peak_equity:
            self.peak_equity = equity

    def get_current_drawdown(self, equity: float) -> float:
        if self.peak_equity <= 0:
            return 0.0
        return (self.peak_equity - equity) / self.peak_equity * 100

    def can_trade(self, equity: float, initial_balance: float) -> tuple[bool, str]:
        if self.emergency_stop:
            return False, "Emergency stop is active"

        self.reset_daily()

        if self.consecutive_failures >= self.max_consecutive_failures:
            return False, f"Too many consecutive API failures ({self.consecutive_failures})"

        daily_loss_pct = abs(self.daily_pnl) / initial_balance * 100 if initial_balance > 0 else 0
        if self.daily_pnl < 0 and daily_loss_pct >= self.config.daily_max_loss_pct:
            return False, f"Daily max loss reached ({daily_loss_pct:.2f}%)"

        drawdown = self.get_current_drawdown(equity)
        if drawdown >= self.config.max_drawdown_stop_pct:
            return False, f"Max drawdown reached ({drawdown:.2f}%)"

        if self.last_trade_time:
            elapsed = (datetime.utcnow() - self.last_trade_time).total_seconds()
            if elapsed < self.config.cooldown_seconds:
                return False, f"Cooldown active ({self.config.cooldown_seconds - elapsed:.0f}s remaining)"

        return True, "OK"

    def validate_buy(
        self, balance: float, spend_amount: float, price: float,
    ) -> tuple[bool, str]:
        if spend_amount > balance:
            return False, "Insufficient balance"

        notional = spend_amount
        if notional < self.config.min_notional:
            return False, f"Below minimum notional ({self.config.min_notional} USDT)"

        qty = spend_amount / price
        if qty < self.config.min_qty:
            return False, f"Below minimum quantity ({self.config.min_qty})"

        if self.config.min_profit_over_fees:
            round_trip_fees = notional * (self.config.fee_pct / 100) * 2
            slippage_cost = notional * (self.config.slippage_pct / 100) * 2
            total_cost = round_trip_fees + slippage_cost
            min_profit_needed = total_cost * 1.5
            if notional * 0.01 < total_cost:
                return True, f"Warning: Expected fees+slippage ({total_cost:.4f}) may exceed potential profit on small moves"

        return True, "OK"

    def validate_sell(
        self, coin_held: float, sell_qty: float, price: float,
    ) -> tuple[bool, str]:
        if sell_qty > coin_held:
            return False, "Insufficient holdings"

        if sell_qty < self.config.min_qty:
            return False, f"Below minimum quantity ({self.config.min_qty})"

        notional = sell_qty * price
        if notional < self.config.min_notional and sell_qty < coin_held:
            return False, f"Below minimum notional ({self.config.min_notional} USDT)"

        return True, "OK"

    def record_trade(self, pnl: float):
        self.daily_pnl += pnl
        self.last_trade_time = datetime.utcnow()
        self.consecutive_failures = 0

    def record_api_failure(self):
        self.consecutive_failures += 1

    def record_api_success(self):
        self.consecutive_failures = 0

    def activate_emergency_stop(self):
        self.emergency_stop = True

    def deactivate_emergency_stop(self):
        self.emergency_stop = False
        self.consecutive_failures = 0

    def get_small_account_warnings(self, balance: float) -> list[str]:
        warnings = []
        if balance < 20:
            warnings.append(
                f"Account balance ({balance:.2f} USDT) is very small. "
                "Many Binance pairs require minimum order sizes of 5-10 USDT."
            )
            warnings.append(
                "Trading fees will heavily impact profitability on small accounts."
            )
            warnings.append(
                "Consider using pairs with low minimum order sizes (e.g., some altcoin/USDT pairs)."
            )
        if balance < self.config.min_notional:
            warnings.append(
                f"Balance ({balance:.2f} USDT) is below minimum notional value ({self.config.min_notional} USDT). "
                "Cannot place any orders."
            )
        monthly_target = self.config.monthly_target_return_pct
        if monthly_target > 50:
            warnings.append(
                f"Monthly target of {monthly_target:.0f}% is extremely aggressive. "
                "This level of return is rarely achievable consistently and carries very high risk of total loss."
            )
        return warnings
