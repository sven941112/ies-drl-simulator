"""Strict input validation: complete, ordered, consecutive 24-hour days."""
from pathlib import Path
import numpy as np
import pandas as pd

POWER_COLUMNS = ["electric_load_kw", "heat_load_kw", "cooling_load_kw", "pv_kw", "wind_kw"]
VALUE_COLUMNS = POWER_COLUMNS + ["buy_price_cny_per_kwh", "sell_price_cny_per_kwh"]
COLUMNS = ["timestamp"] + VALUE_COLUMNS


def load_days(path):
    frame = pd.read_csv(Path(path))
    missing = set(COLUMNS) - set(frame.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")
    frame = frame[COLUMNS].copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="raise")
    ts = frame["timestamp"]
    if ts.isna().any() or ts.duplicated().any() or not ts.is_monotonic_increasing:
        raise ValueError("Timestamps must be unique, non-null and increasing")
    if len(frame) == 0 or len(frame) % 24:
        raise ValueError("Need a non-empty whole number of 24-hour days")
    if not ts.diff().iloc[1:].eq(pd.Timedelta(hours=1)).all():
        raise ValueError("Missing or irregular hourly timestamps")
    if ts.iloc[0] != ts.iloc[0].normalize():
        raise ValueError("Data must begin at midnight; use a fixed timezone without DST")
    frame[VALUE_COLUMNS] = frame[VALUE_COLUMNS].apply(pd.to_numeric, errors="raise")
    if not np.isfinite(frame[VALUE_COLUMNS].to_numpy(dtype=float)).all():
        raise ValueError("NaN/Inf inputs are not accepted")
    if (frame[POWER_COLUMNS] < 0).any().any():
        raise ValueError("Loads and renewable availability must be nonnegative")
    if (frame["sell_price_cny_per_kwh"] > frame["buy_price_cny_per_kwh"]).any():
        raise ValueError("v0.1 requires sell price <= buy price")
    return [frame.iloc[i:i+24].reset_index(drop=True) for i in range(0, len(frame), 24)]
