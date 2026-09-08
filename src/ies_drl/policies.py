"""Causal rule baseline; accesses current measurements and stored energy only."""
import numpy as np


def rule_action(system):
    c, r = system.cfg, system.current
    price = r["buy_price_cny_per_kwh"]
    peak = price >= 0.9
    chp_gas = c.chp_gas_max_kw if peak else 0.0
    # Account for the ramp limiter when calculating the residual heat request.
    chp_gas = float(np.clip(chp_gas,
        max(0, system.previous_chp_gas_kw-c.chp_ramp_kw_per_hour*c.dt_hours),
        min(c.chp_gas_max_kw, system.previous_chp_gas_kw+c.chp_ramp_kw_per_hour*c.dt_hours)))
    hp_e = 0.0
    if price/c.hp_cop <= c.gas_price_cny_per_kwh/c.boiler_eff:
        hp_e = np.clip((r["heat_load_kw"]-chp_gas*c.chp_heat_eff)/c.hp_cop, 0, c.hp_electric_max_kw)
    batt = 0.0
    # End-of-day restoration is an explicit causal heuristic, not free resetting.
    if system.t >= 22:
        gap = c.initial_soc*c.battery_capacity_kwh-system.battery_kwh
        hours = c.horizon-system.t
        batt = -gap/(hours*c.dt_hours*(c.battery_charge_eff if gap >= 0 else 1/c.battery_discharge_eff))
    elif price < 0.4 and system.battery_kwh < 0.8*c.battery_capacity_kwh:
        batt = -c.battery_power_kw
    elif peak and system.battery_kwh > c.initial_soc*c.battery_capacity_kwh:
        batt = min(c.battery_power_kw,
            (system.battery_kwh-c.initial_soc*c.battery_capacity_kwh)*c.battery_discharge_eff/c.dt_hours)
    return np.clip(np.array([2*chp_gas/c.chp_gas_max_kw-1, 2*hp_e/c.hp_electric_max_kw-1,
                           batt/c.battery_power_kw, 0.0, -1.0], dtype=np.float32), -1, 1)
