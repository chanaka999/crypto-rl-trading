import os
from pathlib import Path
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data_cache"
MODEL_DIR = BASE_DIR / "saved_models"
DB_PATH = BASE_DIR / "trading.db"

DATA_DIR.mkdir(exist_ok=True)
MODEL_DIR.mkdir(exist_ok=True)


class Settings(BaseSettings):
    binance_api_key: str = ""
    binance_api_secret: str = ""
    database_url: str = f"sqlite+aiosqlite:///{DB_PATH}"
    default_symbol: str = "BTC/USDT"
    default_timeframe: str = "1h"
    default_initial_balance: float = 10.0
    default_fee_pct: float = 0.1
    default_slippage_pct: float = 0.05
    max_position_pct: float = 100.0
    stop_loss_pct: float = 5.0
    take_profit_pct: float = 10.0
    daily_max_loss_pct: float = 10.0
    monthly_target_return_pct: float = 100.0
    min_confidence_threshold: float = 0.0
    live_trading_enabled: bool = False
    cooldown_seconds: int = 60
    max_drawdown_stop_pct: float = 20.0
    min_profit_over_fees: bool = True

    class Config:
        env_file = ".env"


settings = Settings()
