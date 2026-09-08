"""Evaluate each supplied day exactly once, with separate feasibility metrics."""
import argparse
import hashlib
import json
from pathlib import Path
from time import perf_counter
import numpy as np
import pandas as pd
from .config import Config
from .core import EnergySystem
from .data import load_days
from .policies import rule_action


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rollout(days, cfg, model=None, policy="rule", seed=42):
    records, metrics = [], []
    rng = np.random.default_rng(seed)
    for day_index, day in enumerate(days):
        system, rows = EnergySystem(day, cfg), []
        for _ in range(cfg.horizon):
            begin = perf_counter()
            if model is not None:
                action, _ = model.predict(system.observe(), deterministic=True)
            elif policy == "rule":
                action = rule_action(system)
            elif policy == "random":
                action = rng.uniform(-1, 1, 5)
            else:
                raise ValueError(f"Unknown policy: {policy}")
            latency = (perf_counter()-begin)*1000
            _, _, _, info = system.step(action)
            rows.append({"day_index": day_index, **info, "decision_ms": latency})
        table = pd.DataFrame(rows)
        available = (table.pv_kw+table.wind_kw).sum()*cfg.dt_hours
        curtailed = table.renewable_curtailed_kw.sum()*cfg.dt_hours
        slack_cols = ["electric_slack_kw", "heat_slack_kw", "cooling_slack_kw", "electric_dump_kw"]
        metrics.append({
            "day_index": day_index, "date": str(day.iloc[0]["timestamp"].date()),
            "return": float(table.reward.sum()),
            "operating_cost_cny": float(table.operating_cost_cny.sum()),
            "objective_cny": float(table.objective_cny.sum()),
            "emission_kg": float(table.emission_kg.sum()),
            "renewable_available_kwh": float(available), "renewable_curtailed_kwh": float(curtailed),
            "renewable_utilization": float(1-curtailed/available) if available > 0 else None,
            "infeasible_hours": int(table.infeasible.sum()),
            "slack_energy_kwh": float(table[slack_cols].sum().sum()*cfg.dt_hours),
            "terminal_gap_kwh": float(table.terminal_gap_kwh.sum()),
            "action_correction_rate": float((table.action_correction_l1 > 1e-6).mean()),
            "max_balance_residual_kw": float(np.abs(table[["electric_residual_kw", "heat_residual_kw", "cooling_residual_kw"]]).to_numpy().max()),
            "decision_median_ms": float(table.decision_ms.median()),
            "decision_p95_ms": float(table.decision_ms.quantile(.95)),
        })
        records.extend(rows)
    return pd.DataFrame(records), pd.DataFrame(metrics)


def summarize(dispatch, daily):
    available = float(daily.renewable_available_kwh.sum())
    return {
        "days": len(daily), "mean_daily_operating_cost_cny": float(daily.operating_cost_cny.mean()),
        "mean_daily_objective_cny": float(daily.objective_cny.mean()),
        "mean_daily_emission_kg": float(daily.emission_kg.mean()),
        "mean_daily_terminal_gap_kwh": float(daily.terminal_gap_kwh.mean()),
        "infeasible_hours": int(daily.infeasible_hours.sum()),
        "slack_energy_kwh": float(daily.slack_energy_kwh.sum()),
        "renewable_utilization": float(1-daily.renewable_curtailed_kwh.sum()/available) if available > 0 else None,
        "max_balance_residual_kw": float(daily.max_balance_residual_kw.max()),
        "decision_median_ms": float(dispatch.decision_ms.median()),
        "decision_p95_ms": float(dispatch.decision_ms.quantile(.95)),
        "note": "Low cost is not a feasible result when slack is nonzero; terminal SOC is a soft target.",
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", default="data/demo/test.csv")
    p.add_argument("--policy", choices=["rule", "random", "ppo", "sac"], default="rule")
    p.add_argument("--run", help="Training output directory, required for PPO/SAC")
    p.add_argument("--config", help="For rule/random only; RL reuses the saved training config")
    p.add_argument("--out", default="runs/evaluation")
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()
    days = load_days(args.data)
    model, meta = None, None
    if args.policy in ("ppo", "sac"):
        if not args.run or args.config:
            p.error("PPO/SAC requires --run and uses its config; omit --config")
        from stable_baselines3 import PPO, SAC
        run = Path(args.run)
        meta = json.loads((run/"metadata.json").read_text(encoding="utf-8"))
        if meta["algo"] != args.policy:
            p.error("--policy differs from the saved algorithm")
        if days[0].iloc[0]["timestamp"] <= pd.Timestamp(meta["val_end"]):
            p.error("Held-out evaluation data must occur after the validation data")
        cfg = Config.load(run/"config.json")
        if sha256(run/"config.json") != meta["config_sha256"]:
            p.error("Saved config has changed since training")
        model = {"ppo": PPO, "sac": SAC}[args.policy].load(run/"best_model.zip", device="cpu")
    else:
        cfg = Config.load(args.config)
    out = Path(args.out)
    if out.exists() and any(out.iterdir()):
        p.error("Output directory is not empty; choose another --out")
    out.mkdir(parents=True, exist_ok=True)
    dispatch, daily = rollout(days, cfg, model=model, policy=args.policy, seed=args.seed)
    dispatch.to_csv(out/"dispatch.csv", index=False)
    daily.to_csv(out/"daily_metrics.csv", index=False)
    report = {"policy": args.policy, "seed": args.seed, "data_sha256": sha256(args.data),
              **summarize(dispatch, daily)}
    if meta:
        report["training_seed"] = meta["seed"]
        report["model_sha256"] = sha256(Path(args.run)/"best_model.zip")
    cfg.save(out/"config.json")
    (out/"summary.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
