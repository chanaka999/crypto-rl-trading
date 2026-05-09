import json
import threading
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from app.database import (
    get_connection, get_all_config, get_config_value,
    set_config_value, init_db,
)
from app.data.binance_data import download_ohlcv, cache_ohlcv, fetch_or_load, get_latest_price
from app.data.preprocessing import prepare_data_for_training
from app.ml.train import train_model, load_model, list_models, get_model_run
from app.ml.evaluate import evaluate_model, compare_models
from app.trading.backtester import Backtester
from app.trading.paper_trader import PaperTrader
from app.trading.live_trader import LiveTrader
from app.trading.risk_manager import RiskConfig, RiskManager

router = APIRouter()

# Global state for running traders
_paper_trader: Optional[PaperTrader] = None
_live_trader: Optional[LiveTrader] = None
_training_status = {"running": False, "progress": "", "result": None}


# ─── Settings ──────────────────────────────────────────────

class SettingsUpdate(BaseModel):
    symbol: Optional[str] = None
    timeframe: Optional[str] = None
    initial_balance: Optional[float] = None
    fee_pct: Optional[float] = None
    slippage_pct: Optional[float] = None
    max_position_pct: Optional[float] = None
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None
    daily_max_loss_pct: Optional[float] = None
    monthly_target_return_pct: Optional[float] = None
    min_confidence_threshold: Optional[float] = None
    live_trading_enabled: Optional[bool] = None
    trading_mode: Optional[str] = None
    cooldown_seconds: Optional[int] = None
    max_drawdown_stop_pct: Optional[float] = None
    min_profit_over_fees: Optional[bool] = None
    binance_api_key: Optional[str] = None
    binance_api_secret: Optional[str] = None


@router.get("/settings")
def get_settings():
    config = get_all_config()
    risk_mgr = RiskManager(RiskConfig())
    balance = float(config.get("initial_balance", "10"))
    warnings = risk_mgr.get_small_account_warnings(balance)

    monthly_target = float(config.get("monthly_target_return_pct", "100"))
    if monthly_target > 50:
        warnings.append(
            f"Monthly target of {monthly_target:.0f}% is extremely aggressive. "
            "Actual results may be significantly lower. The system will show honest performance."
        )

    return {"settings": config, "warnings": warnings}


@router.post("/settings")
def update_settings(data: SettingsUpdate):
    updates = data.model_dump(exclude_none=True)
    for key, value in updates.items():
        set_config_value(key, str(value))
    return {"status": "updated", "settings": get_all_config()}


# ─── Data ──────────────────────────────────────────────────

class DataDownloadRequest(BaseModel):
    symbol: str = "BTC/USDT"
    timeframe: str = "1h"
    since: Optional[str] = None
    until: Optional[str] = None


@router.post("/data/download")
def download_data(req: DataDownloadRequest):
    try:
        df = download_ohlcv(req.symbol, req.timeframe, req.since, req.until)
        if df.empty:
            return {"status": "no_data", "rows": 0}
        cache_ohlcv(df, req.symbol, req.timeframe)
        return {
            "status": "ok",
            "rows": len(df),
            "symbol": req.symbol,
            "timeframe": req.timeframe,
            "start": df.iloc[0]["timestamp"],
            "end": df.iloc[-1]["timestamp"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Model Training ───────────────────────────────────────

class TrainRequest(BaseModel):
    model_type: str = "PPO"
    total_timesteps: int = 50000
    symbol: str = "BTC/USDT"
    timeframe: str = "1h"
    since: Optional[str] = None
    until: Optional[str] = None
    initial_balance: float = 10.0
    fee_pct: float = 0.1
    slippage_pct: float = 0.05
    learning_rate: float = 0.0003
    model_name: Optional[str] = None


def _run_training(req: TrainRequest):
    global _training_status
    _training_status = {"running": True, "progress": "Downloading data...", "result": None}

    try:
        df = fetch_or_load(req.symbol, req.timeframe, req.since, req.until)
        if df.empty or len(df) < 100:
            _training_status = {"running": False, "progress": "error", "result": {"error": "Insufficient data"}}
            return

        train_df, val_df, test_df = prepare_data_for_training(df)

        _training_status["progress"] = f"Training {req.model_type} model..."
        result = train_model(
            train_df,
            model_type=req.model_type,
            total_timesteps=req.total_timesteps,
            initial_balance=req.initial_balance,
            fee_pct=req.fee_pct,
            slippage_pct=req.slippage_pct,
            symbol=req.symbol,
            timeframe=req.timeframe,
            model_name=req.model_name,
            learning_rate=req.learning_rate,
        )

        _training_status = {"running": False, "progress": "completed", "result": result}
    except Exception as e:
        _training_status = {"running": False, "progress": "error", "result": {"error": str(e)}}


@router.post("/model/train")
def start_training(req: TrainRequest, background_tasks: BackgroundTasks):
    global _training_status
    if _training_status.get("running"):
        return {"status": "already_training"}

    background_tasks.add_task(_run_training, req)
    return {"status": "training_started", "model_type": req.model_type}


@router.get("/model/status")
def get_training_status():
    return _training_status


class EvalRequest(BaseModel):
    model_name: str
    model_type: str = "PPO"
    symbol: str = "BTC/USDT"
    timeframe: str = "1h"
    since: Optional[str] = None
    until: Optional[str] = None
    initial_balance: float = 10.0
    fee_pct: float = 0.1
    slippage_pct: float = 0.05


@router.post("/model/evaluate")
def evaluate_model_endpoint(req: EvalRequest):
    model = load_model(req.model_name, req.model_type)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")

    df = fetch_or_load(req.symbol, req.timeframe, req.since, req.until)
    if df.empty:
        raise HTTPException(status_code=400, detail="No data available")

    _, _, test_df = prepare_data_for_training(df)
    if test_df.empty or len(test_df) < 10:
        test_df = df

    result = evaluate_model(model, test_df, req.initial_balance, req.fee_pct, req.slippage_pct)
    return result


@router.get("/model/list")
def list_models_endpoint():
    models = list_models()
    return {"models": models}


# ─── Backtest ──────────────────────────────────────────────

class BacktestRequest(BaseModel):
    symbol: str = "BTC/USDT"
    timeframe: str = "1h"
    since: Optional[str] = None
    until: Optional[str] = None
    initial_balance: float = 10.0
    fee_pct: float = 0.1
    slippage_pct: float = 0.05
    stop_loss_pct: float = 5.0
    take_profit_pct: float = 10.0
    model_name: Optional[str] = None
    model_type: str = "PPO"


@router.post("/backtest/run")
def run_backtest(req: BacktestRequest):
    df = fetch_or_load(req.symbol, req.timeframe, req.since, req.until)
    if df.empty or len(df) < 50:
        raise HTTPException(status_code=400, detail="Insufficient data for backtesting")

    model = None
    if req.model_name:
        model = load_model(req.model_name, req.model_type)
        if model is None:
            raise HTTPException(status_code=404, detail="Model not found")
    else:
        from stable_baselines3 import PPO
        from app.data.preprocessing import add_technical_indicators
        from app.trading.environment import CryptoTradingEnv

        df_proc = add_technical_indicators(df)
        env = CryptoTradingEnv(df=df_proc, initial_balance=req.initial_balance)
        model = PPO("MlpPolicy", env, verbose=0)

    backtester = Backtester(
        df=df,
        initial_balance=req.initial_balance,
        fee_pct=req.fee_pct,
        slippage_pct=req.slippage_pct,
        stop_loss_pct=req.stop_loss_pct,
        take_profit_pct=req.take_profit_pct,
    )

    result = backtester.run(model, req.symbol, req.timeframe)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    model_name = req.model_name or "untrained"
    run_id = backtester.save_result(result, model_name)
    result["run_id"] = run_id

    return result


@router.get("/backtest/results/{run_id}")
def get_backtest_results(run_id: int):
    conn = get_connection()
    row = conn.execute("SELECT * FROM backtest_runs WHERE id=?", (run_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Backtest run not found")

    result = dict(row)
    for json_field in ["trades_json", "equity_curve_json", "monthly_returns_json"]:
        if result.get(json_field):
            try:
                result[json_field.replace("_json", "")] = json.loads(result[json_field])
            except json.JSONDecodeError:
                pass
            del result[json_field]
    return result


@router.get("/backtest/list")
def list_backtests():
    conn = get_connection()
    rows = conn.execute(
        """SELECT id, symbol, timeframe, start_date, end_date, initial_balance,
                  final_balance, return_pct, max_drawdown, num_trades, win_rate,
                  sharpe_ratio, model_name, created_at
           FROM backtest_runs ORDER BY created_at DESC LIMIT 50"""
    ).fetchall()
    conn.close()
    return {"backtests": [dict(r) for r in rows]}


# ─── Paper Trading ─────────────────────────────────────────

@router.post("/paper/start")
def start_paper_trading():
    global _paper_trader
    config = get_all_config()
    symbol = config.get("symbol", "BTC/USDT")
    balance = float(config.get("initial_balance", "10"))

    risk_config = RiskConfig(
        fee_pct=float(config.get("fee_pct", "0.1")),
        slippage_pct=float(config.get("slippage_pct", "0.05")),
        stop_loss_pct=float(config.get("stop_loss_pct", "5.0")),
        take_profit_pct=float(config.get("take_profit_pct", "10.0")),
        daily_max_loss_pct=float(config.get("daily_max_loss_pct", "10.0")),
        cooldown_seconds=int(config.get("cooldown_seconds", "60")),
    )

    if _paper_trader is None or not _paper_trader.running:
        _paper_trader = PaperTrader(symbol=symbol, initial_balance=balance, risk_config=risk_config)

    return _paper_trader.start()


@router.post("/paper/stop")
def stop_paper_trading():
    global _paper_trader
    if _paper_trader is None:
        return {"status": "not_running"}
    return _paper_trader.stop()


@router.post("/paper/reset")
def reset_paper_trading():
    global _paper_trader
    config = get_all_config()
    balance = float(config.get("initial_balance", "10"))
    if _paper_trader is None:
        _paper_trader = PaperTrader(initial_balance=balance)
    return _paper_trader.reset(balance)


@router.get("/paper/status")
def get_paper_status():
    global _paper_trader
    if _paper_trader is None:
        return {"running": False, "message": "Paper trader not initialized"}
    return _paper_trader.get_status()


# ─── Live Trading ──────────────────────────────────────────

@router.post("/live/start")
def start_live_trading(confirmed: bool = False):
    global _live_trader
    config = get_all_config()

    if config.get("live_trading_enabled", "false").lower() != "true":
        raise HTTPException(status_code=403, detail="Live trading is disabled in settings")

    api_key = config.get("binance_api_key", "")
    api_secret = config.get("binance_api_secret", "")
    symbol = config.get("symbol", "BTC/USDT")

    if not api_key or not api_secret:
        raise HTTPException(status_code=400, detail="Binance API key and secret are required")

    risk_config = RiskConfig(
        fee_pct=float(config.get("fee_pct", "0.1")),
        slippage_pct=float(config.get("slippage_pct", "0.05")),
        stop_loss_pct=float(config.get("stop_loss_pct", "5.0")),
        take_profit_pct=float(config.get("take_profit_pct", "10.0")),
        daily_max_loss_pct=float(config.get("daily_max_loss_pct", "10.0")),
        cooldown_seconds=int(config.get("cooldown_seconds", "60")),
        max_drawdown_stop_pct=float(config.get("max_drawdown_stop_pct", "20.0")),
    )

    if _live_trader is None or not _live_trader.running:
        _live_trader = LiveTrader(
            symbol=symbol, api_key=api_key, api_secret=api_secret,
            risk_config=risk_config,
        )

    return _live_trader.start(confirmed=confirmed)


@router.post("/live/stop")
def stop_live_trading():
    global _live_trader
    if _live_trader is None:
        return {"status": "not_running"}
    return _live_trader.stop()


@router.post("/live/emergency-stop")
def emergency_stop():
    global _live_trader
    if _live_trader is None:
        return {"status": "not_running"}
    return _live_trader.emergency_stop()


@router.get("/live/status")
def get_live_status():
    global _live_trader
    if _live_trader is None:
        return {"running": False, "connected": False, "message": "Live trader not initialized"}
    return _live_trader.get_status()


# ─── Trades & Metrics ─────────────────────────────────────

@router.get("/trades")
def get_trades(mode: Optional[str] = None, symbol: Optional[str] = None, limit: int = 100):
    conn = get_connection()
    query = "SELECT * FROM trades WHERE 1=1"
    params: list = []

    if mode:
        query += " AND mode=?"
        params.append(mode)
    if symbol:
        query += " AND symbol=?"
        params.append(symbol)

    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return {"trades": [dict(r) for r in rows]}


@router.get("/equity-curve")
def get_equity_curve(mode: Optional[str] = None, limit: int = 500):
    conn = get_connection()
    query = "SELECT * FROM equity_curve WHERE 1=1"
    params: list = []

    if mode:
        query += " AND mode=?"
        params.append(mode)

    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return {"equity_curve": [dict(r) for r in reversed(rows)]}


@router.get("/metrics")
def get_metrics():
    config = get_all_config()
    initial_balance = float(config.get("initial_balance", "10"))
    mode = config.get("trading_mode", "backtest")

    conn = get_connection()

    trades = conn.execute(
        "SELECT * FROM trades WHERE mode=? ORDER BY timestamp DESC LIMIT 1000",
        (mode,),
    ).fetchall()

    total_trades = len(trades)
    wins = sum(1 for t in trades if t["pnl"] > 0)
    losses = sum(1 for t in trades if t["pnl"] < 0)
    total_pnl = sum(t["pnl"] for t in trades)
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0

    current_balance = initial_balance + total_pnl
    if trades:
        current_balance = trades[0]["balance_after"]

    return_pct = ((current_balance - initial_balance) / initial_balance * 100) if initial_balance > 0 else 0

    equity_rows = conn.execute(
        "SELECT equity, drawdown FROM equity_curve WHERE mode=? ORDER BY timestamp DESC LIMIT 500",
        (mode,),
    ).fetchall()

    max_drawdown = max((r["drawdown"] for r in equity_rows), default=0)

    conn.close()

    monthly_target = float(config.get("monthly_target_return_pct", "100"))
    target_warning = ""
    if monthly_target > 50 and return_pct < monthly_target:
        target_warning = (
            f"Current return ({return_pct:.1f}%) is below monthly target ({monthly_target:.0f}%). "
            "This target is extremely aggressive and may not be achievable."
        )

    risk_mgr = RiskManager(RiskConfig())
    small_warnings = risk_mgr.get_small_account_warnings(current_balance)

    return {
        "mode": mode,
        "symbol": config.get("symbol", "BTC/USDT"),
        "initial_balance": initial_balance,
        "current_balance": round(current_balance, 6),
        "total_pnl": round(total_pnl, 6),
        "return_pct": round(return_pct, 2),
        "num_trades": total_trades,
        "win_rate": round(win_rate, 2),
        "max_drawdown": round(max_drawdown, 2),
        "monthly_target_return_pct": monthly_target,
        "target_warning": target_warning,
        "warnings": small_warnings,
    }


@router.get("/health")
def health():
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
    }
