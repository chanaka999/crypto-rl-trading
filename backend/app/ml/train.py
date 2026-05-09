import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
from stable_baselines3 import PPO, A2C, DQN
from stable_baselines3.common.callbacks import BaseCallback

from app.config import MODEL_DIR
from app.data.preprocessing import add_technical_indicators
from app.trading.environment import CryptoTradingEnv
from app.database import get_connection

logger = logging.getLogger(__name__)

MODEL_CLASSES = {"PPO": PPO, "A2C": A2C, "DQN": DQN}


class RewardTrackingCallback(BaseCallback):
    def __init__(self, verbose=0):
        super().__init__(verbose)
        self.episode_rewards: list = []
        self.current_rewards: list = []

    def _on_step(self) -> bool:
        for info in self.locals.get("infos", []):
            if "episode" in info:
                self.episode_rewards.append(info["episode"]["r"])
        return True


def train_model(
    df,
    model_type: str = "PPO",
    total_timesteps: int = 50000,
    initial_balance: float = 10.0,
    fee_pct: float = 0.1,
    slippage_pct: float = 0.05,
    symbol: str = "BTC/USDT",
    timeframe: str = "1h",
    model_name: Optional[str] = None,
    learning_rate: float = 0.0003,
) -> dict:
    df_processed = add_technical_indicators(df)
    if len(df_processed) < 50:
        return {"error": "Insufficient data for training (need at least 50 candles after indicators)"}

    env = CryptoTradingEnv(
        df=df_processed,
        initial_balance=initial_balance,
        fee_pct=fee_pct,
        slippage_pct=slippage_pct,
    )

    if model_type not in MODEL_CLASSES:
        return {"error": f"Unknown model type: {model_type}. Use PPO, A2C, or DQN"}

    model_cls = MODEL_CLASSES[model_type]
    callback = RewardTrackingCallback()

    if model_name is None:
        model_name = f"{model_type}_{symbol.replace('/', '_')}_{timeframe}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO model_runs
           (model_type, model_name, symbol, timeframe, total_timesteps, status, config_json, created_at)
           VALUES (?, ?, ?, ?, ?, 'training', ?, ?)""",
        (model_type, model_name, symbol, timeframe, total_timesteps,
         json.dumps({"learning_rate": learning_rate, "fee_pct": fee_pct, "slippage_pct": slippage_pct}),
         datetime.utcnow().isoformat()),
    )
    conn.commit()
    run_id = cursor.lastrowid
    conn.close()

    try:
        if model_type == "DQN":
            model = model_cls(
                "MlpPolicy", env,
                learning_rate=learning_rate,
                buffer_size=10000,
                batch_size=64,
                verbose=0,
            )
        else:
            model = model_cls(
                "MlpPolicy", env,
                learning_rate=learning_rate,
                n_steps=256,
                verbose=0,
            )

        model.learn(total_timesteps=total_timesteps, callback=callback)

        save_path = str(MODEL_DIR / model_name)
        model.save(save_path)

        obs, _ = env.reset()
        done = False
        total_reward = 0
        while not done:
            action, _ = model.predict(obs, deterministic=True)
            obs, reward, done, truncated, info = env.step(int(action))
            total_reward += reward
            if truncated:
                break

        metrics = env.get_metrics()

        conn = get_connection()
        conn.execute(
            """UPDATE model_runs SET status='completed', file_path=?,
               training_reward=?, eval_reward=?, eval_return_pct=?,
               eval_sharpe=?, eval_max_drawdown=?,
               reward_history_json=?, completed_at=?
               WHERE id=?""",
            (save_path, total_reward, total_reward,
             metrics["return_pct"], metrics["sharpe_ratio"], metrics["max_drawdown"],
             json.dumps(callback.episode_rewards[-100:] if callback.episode_rewards else []),
             datetime.utcnow().isoformat(), run_id),
        )
        conn.commit()
        conn.close()

        return {
            "status": "completed",
            "model_name": model_name,
            "model_type": model_type,
            "run_id": run_id,
            "file_path": save_path,
            "total_timesteps": total_timesteps,
            "training_reward": round(total_reward, 4),
            "metrics": metrics,
            "reward_history": callback.episode_rewards[-100:] if callback.episode_rewards else [],
        }
    except Exception as e:
        logger.error(f"Training error: {e}")
        conn = get_connection()
        conn.execute(
            "UPDATE model_runs SET status='failed' WHERE id=?", (run_id,)
        )
        conn.commit()
        conn.close()
        return {"error": str(e), "run_id": run_id}


def load_model(model_name: str, model_type: str = "PPO"):
    model_path = MODEL_DIR / model_name
    zip_path = str(model_path) + ".zip"

    if not os.path.exists(zip_path) and not os.path.exists(str(model_path)):
        alt_path = str(model_path)
        if not os.path.exists(alt_path):
            return None

    model_cls = MODEL_CLASSES.get(model_type)
    if model_cls is None:
        return None

    try:
        return model_cls.load(str(model_path))
    except Exception as e:
        logger.error(f"Error loading model: {e}")
        return None


def list_models() -> list:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM model_runs ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_model_run(run_id: int) -> Optional[dict]:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM model_runs WHERE id=?", (run_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None
