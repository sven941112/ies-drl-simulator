"""PPO/SAC training with chronological split checks and full validation sweeps."""
import argparse
from importlib.metadata import version
import json
from pathlib import Path
import platform
from time import perf_counter
import pandas as pd
import torch
from stable_baselines3 import PPO, SAC
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.env_checker import check_env
from stable_baselines3.common.monitor import Monitor
from .config import Config
from .data import load_days
from .env import IESEnv
from .evaluate import rollout, sha256


class ValidationCallback(BaseCallback):
    def __init__(self, days, cfg, out, interval):
        super().__init__()
        self.days, self.cfg, self.out, self.interval = days, cfg, out, interval
        self.best, self.rows, self.last_step = None, [], -1

    def validate(self):
        if self.last_step == self.num_timesteps:
            return
        _, daily = rollout(self.days, self.cfg, model=self.model)
        score = (int(daily.infeasible_hours.sum()), float(daily.slack_energy_kwh.sum()),
                 float(daily.objective_cny.mean()))
        row = {"timesteps": self.num_timesteps, "infeasible_hours": score[0],
               "slack_energy_kwh": score[1], "mean_objective_cny": score[2],
               "mean_operating_cost_cny": float(daily.operating_cost_cny.mean()),
               "mean_terminal_gap_kwh": float(daily.terminal_gap_kwh.mean())}
        self.rows.append(row)
        pd.DataFrame(self.rows).to_csv(self.out/"validation.csv", index=False)
        if self.best is None or score < self.best:
            self.best = score
            self.model.save(self.out/"best_model.zip")
            (self.out/"best_validation.json").write_text(json.dumps(row, indent=2), encoding="utf-8")
        self.last_step = self.num_timesteps

    def _on_step(self):
        if self.num_timesteps % self.interval == 0:
            self.validate()
        return True

    def _on_training_end(self):
        self.validate()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--algo", choices=["ppo", "sac"], default="ppo")
    p.add_argument("--train-data", default="data/demo/train.csv")
    p.add_argument("--val-data", default="data/demo/val.csv")
    p.add_argument("--config", default="configs/default.json")
    p.add_argument("--steps", type=int, default=100000)
    p.add_argument("--eval-every", type=int, default=4096)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out", default="runs/ppo_seed42")
    args = p.parse_args()
    if args.steps < 1 or args.eval_every < 1:
        p.error("steps and eval-every must be positive")
    out = Path(args.out)
    if out.exists() and any(out.iterdir()):
        p.error("Output directory is not empty; choose another --out")
    cfg = Config.load(args.config)
    train_days, val_days = load_days(args.train_data), load_days(args.val_data)
    train_end = train_days[-1].iloc[-1]["timestamp"]
    val_start = val_days[0].iloc[0]["timestamp"]
    if train_end >= val_start:
        p.error("Training data must precede validation data with no overlap")
    check_env(IESEnv(train_days, cfg), warn=True)
    torch.set_num_threads(1)
    out.mkdir(parents=True, exist_ok=True)
    cfg.save(out/"config.json")
    env = Monitor(IESEnv(train_days, cfg), str(out/"train.monitor.csv"))
    common = dict(policy="MlpPolicy", env=env, seed=args.seed, device="cpu", learning_rate=3e-4,
                  gamma=1.0, policy_kwargs={"net_arch": [64, 64]}, verbose=0)
    if args.algo == "ppo":
        model = PPO(**common, n_steps=1024, batch_size=64, n_epochs=10,
                    gae_lambda=0.95, clip_range=0.2, target_kl=0.03)
    else:
        model = SAC(**common, buffer_size=100000, learning_starts=1024, batch_size=128,
                    train_freq=1, gradient_steps=1, tau=0.005, ent_coef="auto")
    meta = {**vars(args), "python": platform.python_version(), "platform": platform.platform(),
            "device": "cpu", "torch_threads": 1,
            "versions": {name: version(name) for name in ("numpy", "pandas", "torch", "gymnasium", "stable-baselines3")},
            "train_sha256": sha256(args.train_data), "val_sha256": sha256(args.val_data),
            "config_sha256": sha256(out/"config.json"), "train_end": str(train_end),
            "val_end": str(val_days[-1].iloc[-1]["timestamp"])}
    (out/"metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    callback = ValidationCallback(val_days, cfg, out, args.eval_every)
    training_started = perf_counter()
    model.learn(total_timesteps=args.steps, callback=callback)
    meta["training_wall_seconds_including_validation"] = perf_counter()-training_started
    model.save(out/"last_model.zip")
    meta["actual_timesteps"] = model.num_timesteps
    (out/"metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    env.close()
    print(f"Saved {args.algo} run to {out}; actual steps={model.num_timesteps}. See validation.csv.")


if __name__ == "__main__":
    main()
