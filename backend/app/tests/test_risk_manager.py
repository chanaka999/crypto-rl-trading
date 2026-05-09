import pytest
from app.trading.risk_manager import RiskManager, RiskConfig


class TestRiskManager:
    def setup_method(self):
        self.config = RiskConfig(
            fee_pct=0.1,
            slippage_pct=0.05,
            daily_max_loss_pct=10.0,
            max_drawdown_stop_pct=20.0,
            min_notional=5.0,
            min_qty=0.00001,
            cooldown_seconds=0,
        )
        self.rm = RiskManager(self.config)

    def test_can_trade_initially(self):
        ok, msg = self.rm.can_trade(100.0, 100.0)
        assert ok

    def test_emergency_stop_blocks_trading(self):
        self.rm.activate_emergency_stop()
        ok, msg = self.rm.can_trade(100.0, 100.0)
        assert not ok
        assert "Emergency" in msg

    def test_deactivate_emergency_stop(self):
        self.rm.activate_emergency_stop()
        self.rm.deactivate_emergency_stop()
        ok, msg = self.rm.can_trade(100.0, 100.0)
        assert ok

    def test_daily_loss_limit(self):
        self.rm.daily_pnl = -11.0  # 11% loss on 100 balance
        self.rm.daily_reset_time = None  # Force reset check
        self.rm.reset_daily()
        # After reset, daily_pnl resets to 0 since it's a new day check
        # Set it again after the reset
        self.rm.daily_pnl = -11.0
        # Prevent reset from clearing it by setting reset time to now
        from datetime import datetime
        self.rm.daily_reset_time = datetime.utcnow()
        ok, msg = self.rm.can_trade(89.0, 100.0)
        assert not ok
        assert "Daily max loss" in msg

    def test_max_drawdown_stop(self):
        self.rm.peak_equity = 100.0
        ok, msg = self.rm.can_trade(79.0, 100.0)  # 21% drawdown
        assert not ok
        assert "Max drawdown" in msg

    def test_consecutive_failures(self):
        for _ in range(5):
            self.rm.record_api_failure()
        ok, msg = self.rm.can_trade(100.0, 100.0)
        assert not ok
        assert "failures" in msg

    def test_validate_buy_insufficient_balance(self):
        ok, msg = self.rm.validate_buy(5.0, 10.0, 50000.0)
        assert not ok
        assert "Insufficient" in msg

    def test_validate_buy_below_min_notional(self):
        ok, msg = self.rm.validate_buy(100.0, 3.0, 50000.0)
        assert not ok
        assert "notional" in msg

    def test_validate_buy_ok(self):
        ok, msg = self.rm.validate_buy(100.0, 50.0, 50000.0)
        assert ok

    def test_validate_sell_insufficient_holdings(self):
        ok, msg = self.rm.validate_sell(0.001, 0.01, 50000.0)
        assert not ok
        assert "Insufficient" in msg

    def test_validate_sell_below_min_qty(self):
        ok, msg = self.rm.validate_sell(0.001, 0.000001, 50000.0)
        assert not ok
        assert "minimum quantity" in msg

    def test_validate_sell_ok(self):
        ok, msg = self.rm.validate_sell(0.01, 0.005, 50000.0)
        assert ok

    def test_small_account_warnings(self):
        warnings = self.rm.get_small_account_warnings(10.0)
        assert len(warnings) >= 2
        assert any("small" in w.lower() or "10" in w for w in warnings)

    def test_very_small_account_warning(self):
        warnings = self.rm.get_small_account_warnings(3.0)
        assert any("minimum notional" in w.lower() for w in warnings)

    def test_aggressive_target_warning(self):
        self.config.monthly_target_return_pct = 100.0
        rm = RiskManager(self.config)
        warnings = rm.get_small_account_warnings(10.0)
        assert any("aggressive" in w.lower() for w in warnings)

    def test_record_trade_updates_daily_pnl(self):
        self.rm.record_trade(5.0)
        assert self.rm.daily_pnl == 5.0
        self.rm.record_trade(-2.0)
        assert self.rm.daily_pnl == 3.0

    def test_update_peak_equity(self):
        self.rm.update_peak_equity(100.0)
        assert self.rm.peak_equity == 100.0
        self.rm.update_peak_equity(90.0)
        assert self.rm.peak_equity == 100.0  # Peak unchanged
        self.rm.update_peak_equity(110.0)
        assert self.rm.peak_equity == 110.0
