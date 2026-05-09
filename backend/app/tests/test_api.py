import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import init_db


@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    yield


client = TestClient(app)


class TestHealthEndpoints:
    def test_healthz(self):
        resp = client.get("/healthz")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_health(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert "status" in resp.json()
        assert "version" in resp.json()


class TestSettingsEndpoints:
    def test_get_settings(self):
        resp = client.get("/settings")
        assert resp.status_code == 200
        data = resp.json()
        assert "settings" in data
        assert "warnings" in data

    def test_update_settings(self):
        resp = client.post("/settings", json={"symbol": "ETH/USDT", "initial_balance": 20.0})
        assert resp.status_code == 200
        data = resp.json()
        assert data["settings"]["symbol"] == "ETH/USDT"
        assert data["settings"]["initial_balance"] == "20.0"


class TestMetricsEndpoint:
    def test_get_metrics(self):
        resp = client.get("/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "mode" in data
        assert "initial_balance" in data
        assert "current_balance" in data
        assert "return_pct" in data
        assert "warnings" in data


class TestTradesEndpoint:
    def test_get_trades_empty(self):
        resp = client.get("/trades")
        assert resp.status_code == 200
        assert "trades" in resp.json()

    def test_get_trades_with_filter(self):
        resp = client.get("/trades?mode=backtest")
        assert resp.status_code == 200


class TestEquityCurveEndpoint:
    def test_get_equity_curve(self):
        resp = client.get("/equity-curve")
        assert resp.status_code == 200
        assert "equity_curve" in resp.json()


class TestPaperEndpoints:
    def test_paper_status_not_initialized(self):
        resp = client.get("/paper/status")
        assert resp.status_code == 200

    def test_paper_reset(self):
        resp = client.post("/paper/reset")
        assert resp.status_code == 200


class TestLiveEndpoints:
    def test_live_status(self):
        resp = client.get("/live/status")
        assert resp.status_code == 200

    def test_live_start_disabled(self):
        resp = client.post("/live/start?confirmed=true")
        assert resp.status_code == 403  # Live trading disabled by default


class TestModelEndpoints:
    def test_model_status(self):
        resp = client.get("/model/status")
        assert resp.status_code == 200

    def test_model_list(self):
        resp = client.get("/model/list")
        assert resp.status_code == 200
        assert "models" in resp.json()


class TestBacktestEndpoints:
    def test_backtest_list(self):
        resp = client.get("/backtest/list")
        assert resp.status_code == 200
        assert "backtests" in resp.json()

    def test_backtest_results_not_found(self):
        resp = client.get("/backtest/results/9999")
        assert resp.status_code == 404
