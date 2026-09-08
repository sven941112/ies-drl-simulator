"""All energy and monetary parameters are illustrative, not field-calibrated."""
from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path


@dataclass(frozen=True)
class Config:
    dt_hours: float = 1.0
    horizon: int = 24
    chp_gas_max_kw: float = 350.0
    chp_ramp_kw_per_hour: float = 150.0
    chp_electric_eff: float = 0.35
    chp_heat_eff: float = 0.45
    boiler_heat_max_kw: float = 500.0
    boiler_eff: float = 0.9
    hp_electric_max_kw: float = 180.0
    hp_cop: float = 3.0
    ac_heat_max_kw: float = 180.0
    ac_cop: float = 0.7
    ec_cooling_max_kw: float = 600.0
    ec_cop: float = 4.0
    battery_capacity_kwh: float = 500.0
    battery_power_kw: float = 120.0
    battery_charge_eff: float = 0.95
    battery_discharge_eff: float = 0.95
    tes_capacity_kwh: float = 600.0
    tes_power_kw: float = 160.0
    tes_charge_eff: float = 0.95
    tes_discharge_eff: float = 0.95
    soc_min: float = 0.1
    soc_max: float = 0.9
    initial_soc: float = 0.5
    grid_import_max_kw: float = 1000.0
    grid_export_max_kw: float = 200.0
    gas_price_cny_per_kwh: float = 0.28
    grid_emission_kg_per_kwh: float = 0.55
    gas_emission_kg_per_kwh: float = 0.20
    carbon_cost_cny_per_kg: float = 0.08
    battery_wear_cny_per_kwh: float = 0.03
    tes_wear_cny_per_kwh: float = 0.005
    curtail_penalty_cny_per_kwh: float = 0.1
    heat_dump_penalty_cny_per_kwh: float = 0.02
    infeasible_penalty_cny_per_kwh: float = 100.0
    terminal_penalty_cny_per_kwh: float = 2.0
    reward_scale_cny: float = 1000.0

    def __post_init__(self):
        for name, value in asdict(self).items():
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and nonnegative")
        if self.dt_hours != 1.0 or self.horizon != 24:
            raise ValueError("v0.1 supports 24 hourly intervals only")
        for name in ("chp_electric_eff", "chp_heat_eff", "boiler_eff",
                     "battery_charge_eff", "battery_discharge_eff",
                     "tes_charge_eff", "tes_discharge_eff"):
            if not 0 < getattr(self, name) <= 1:
                raise ValueError(f"{name} must be in (0, 1]")
        if self.chp_electric_eff + self.chp_heat_eff > 1:
            raise ValueError("CHP output efficiencies cannot sum to more than one")
        for name in ("chp_gas_max_kw", "hp_electric_max_kw", "ac_heat_max_kw",
                     "battery_power_kw", "tes_power_kw", "battery_capacity_kwh",
                     "tes_capacity_kwh", "hp_cop", "ac_cop", "ec_cop", "reward_scale_cny"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        if not 0 <= self.soc_min < self.initial_soc < self.soc_max <= 1:
            raise ValueError("Require 0 <= soc_min < initial_soc < soc_max <= 1")

    @classmethod
    def load(cls, path=None):
        return cls(**json.loads(Path(path).read_text(encoding="utf-8"))) if path else cls()

    def save(self, path):
        Path(path).write_text(json.dumps(asdict(self), indent=2) + "\n", encoding="utf-8")
