"""Static engineering plots from evaluation CSVs; no invented performance figures."""
import argparse
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--evaluation", default="runs/evaluation")
    p.add_argument("--day", type=int, default=0)
    p.add_argument("--training", help="Optional training directory for the actual return curve")
    args = p.parse_args()
    out = Path(args.evaluation)
    df = pd.read_csv(out/"dispatch.csv")
    df = df[df.day_index == args.day]
    if df.empty:
        p.error("Requested day is absent")
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(3, 2, figsize=(14, 11), layout="constrained")
    hour = df.hour
    electric_supply = df.pv_kw+df.wind_kw-df.renewable_curtailed_kw+df.chp_electric_kw+df.grid_import_kw+df.battery_kw.clip(lower=0)
    electric_demand = df.electric_load_kw+df.hp_electric_kw+df.ec_electric_kw+df.grid_export_kw+(-df.battery_kw).clip(lower=0)
    heat_supply = df.chp_heat_kw+df.hp_heat_kw+df.boiler_heat_kw+df.tes_kw.clip(lower=0)
    heat_demand = df.heat_load_kw+df.ac_heat_kw+(-df.tes_kw).clip(lower=0)+df.heat_dump_kw
    for ax, supply, demand, title in [(axes[0,0], electric_supply, electric_demand, "Electricity balance (excludes virtual slack)"),
                                    (axes[0,1], heat_supply, heat_demand, "Heat balance (excludes virtual slack)"),
                                    (axes[1,0], df.ac_cooling_kw+df.ec_cooling_kw, df.cooling_load_kw, "Cooling balance")]:
        ax.plot(hour, supply, label="Supply", linewidth=2)
        ax.plot(hour, demand, "--", label="Demand / sinks", linewidth=2)
        ax.set(title=title, ylabel="kW"); ax.legend()
    axes[1,1].plot(hour+1, df.battery_soc, label="Battery SOC")
    axes[1,1].plot(hour+1, df.tes_soc, label="Thermal storage SOC")
    axes[1,1].set(title="Storage at end of each interval", ylabel="SOC", ylim=(0,1)); axes[1,1].legend()
    axes[2,0].bar(hour, df.operating_cost_cny, label="Operating cost")
    axes[2,0].plot(hour, df.objective_cny, color="#b14c30", label="Objective incl. penalties")
    axes[2,0].set(title="Cost accounting", ylabel="CNY / interval"); axes[2,0].legend()
    for col in ["electric_slack_kw", "heat_slack_kw", "cooling_slack_kw", "electric_dump_kw"]:
        axes[2,1].plot(hour, df[col], label=col.removesuffix("_kw"))
    axes[2,1].set(title="Infeasibility diagnostics", ylabel="kW"); axes[2,1].legend(fontsize=8)
    for ax in axes.flat:
        ax.set_xlabel("Hour"); ax.grid(alpha=.2)
    fig.suptitle(f"Integrated energy dispatch | {df.iloc[0].timestamp[:10]}", fontsize=16)
    fig.savefig(out/"dispatch.png", dpi=150); plt.close(fig)
    if args.training:
        train = pd.read_csv(Path(args.training)/"train.monitor.csv", skiprows=1)
        fig, ax = plt.subplots(figsize=(9,4), layout="constrained")
        ax.plot(train.l.cumsum(), train.r, alpha=.3, label="Episode return")
        ax.plot(train.l.cumsum(), train.r.rolling(20, min_periods=1).mean(), label="20-episode mean")
        ax.set(xlabel="Environment steps", ylabel="Undiscounted episode return", title="Recorded training returns")
        ax.legend(); ax.grid(alpha=.2)
        fig.savefig(out/"learning_curve.png", dpi=150); plt.close(fig)
    print(f"Figures written to {out}")


if __name__ == "__main__":
    main()
