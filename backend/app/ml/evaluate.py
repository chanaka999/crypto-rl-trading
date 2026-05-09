import numpy as np
from typing import Optional
from app.data.preprocessing import add_technical_indicators
from app.trading.environment import CryptoTradingEnv
from app.ml.train import load_model


def evaluate_model(
    model,
    df,
    initial_balance: float = 10.0,
    fee_pct: float = 0.1,
    slippage_pct: float = 0.05,
) -> dict:
    df_processed = add_technical_indicators(df)
    if len(df_processed) < 10:
        return {"error": "Insufficient data for evaluation"}

    env = CryptoTradingEnv(
        df=df_processed,
        initial_balance=initial_balance,
        fee_pct=fee_pct,
        slippage_pct=slippage_pct,
    )

    obs, _ = env.reset()
    done = False
    total_reward = 0
    actions_taken = []

    while not done:
        action, _ = model.predict(obs, deterministic=True)
        action = int(action)
        obs, reward, done, truncated, info = env.step(action)
        total_reward += reward
        actions_taken.append(action)
        if truncated:
            break

    metrics = env.get_metrics()

    action_counts = {}
    action_names = {0: "Hold", 1: "Buy25%", 2: "Buy50%", 3: "Buy100%",
                    4: "Sell25%", 5: "Sell50%", 6: "Sell100%"}
    for a in actions_taken:
        name = action_names.get(a, f"Action_{a}")
        action_counts[name] = action_counts.get(name, 0) + 1

    return {
        "total_reward": round(total_reward, 4),
        "metrics": metrics,
        "action_distribution": action_counts,
        "total_steps": len(actions_taken),
        "equity_curve": [
            {"step": i, "equity": round(eq, 6)}
            for i, eq in enumerate(env.equity_history)
        ],
    }


def compare_models(
    model_configs: list,
    df,
    initial_balance: float = 10.0,
    fee_pct: float = 0.1,
    slippage_pct: float = 0.05,
) -> list:
    results = []
    for config in model_configs:
        model_name = config.get("model_name", "")
        model_type = config.get("model_type", "PPO")
        model = load_model(model_name, model_type)
        if model is None:
            results.append({"model_name": model_name, "error": "Model not found"})
            continue

        eval_result = evaluate_model(model, df, initial_balance, fee_pct, slippage_pct)
        eval_result["model_name"] = model_name
        eval_result["model_type"] = model_type
        results.append(eval_result)

    results.sort(
        key=lambda x: x.get("metrics", {}).get("sharpe_ratio", -999),
        reverse=True,
    )

    return results
