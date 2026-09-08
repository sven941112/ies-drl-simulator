"""Synthetic demonstration profiles; no claim of measured plant data."""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
from .data import COLUMNS


def generate(days=60, seed=42):
    if days < 20:
        raise ValueError("At least 20 days are needed for the three demo splits")
    rng = np.random.default_rng(seed)
    rows = []
    start = pd.Timestamp("2025-01-01")
    for day in range(days):
        demand = rng.uniform(0.85, 1.15)
        sun = rng.uniform(0.6, 1.05)
        for hour in range(24):
            daytime = max(0.0, np.sin(np.pi * (hour - 6) / 12))
            el = max(0, demand * (280 + 100 * daytime) + rng.normal(0, 12))
            heat = max(0, demand * (250 + 65 * np.cos(2*np.pi*(hour-5)/24)) + rng.normal(0, 8))
            cold = max(0, demand * (160 + 160 * daytime) + rng.normal(0, 8))
            pv = max(0, 300 * sun * daytime * rng.uniform(0.90, 1.05))
            wind = np.clip(90 + 45 * np.sin(2*np.pi*(hour+day)/24) + rng.normal(0, 12), 0, 180)
            buy = 0.35 if hour < 7 or hour >= 23 else (1.05 if 17 <= hour <= 21 else 0.65)
            rows.append([start + pd.Timedelta(days=day, hours=hour), el, heat, cold, pv, wind, buy, 0.25])
    return pd.DataFrame(rows, columns=COLUMNS)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", default="data/demo")
    p.add_argument("--days", type=int, default=60)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    frame = generate(args.days, args.seed)
    n_train, n_val = int(args.days * .7), int(args.days * .15)
    bounds = [("train", 0, n_train), ("val", n_train, n_train+n_val),
              ("test", n_train+n_val, args.days)]
    meta = {"source": "synthetic demonstration only", "seed": args.seed, "days": args.days, "splits": {}}
    for name, begin, end in bounds:
        subset = frame.iloc[begin*24:end*24]
        subset.to_csv(out / f"{name}.csv", index=False, float_format="%.6f")
        meta["splits"][name] = {"days": end-begin, "start": str(subset.iloc[0]["timestamp"]),
                                "end": str(subset.iloc[-1]["timestamp"])}
    (out / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
