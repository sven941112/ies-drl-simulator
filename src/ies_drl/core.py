"""Single-bus hourly dispatch simulator. See docs/MODEL.md for slack semantics."""
import numpy as np
from .config import Config


def storage_dispatch(request_kw, energy_kwh, capacity_kwh, power_kw, eta_c, eta_d, cfg):
    """Signed bus power: positive = discharge; negative = charge."""
    low, high = cfg.soc_min * capacity_kwh, cfg.soc_max * capacity_kwh
    discharge_limit = min(power_kw, max(0.0, energy_kwh-low) * eta_d / cfg.dt_hours)
    charge_limit = min(power_kw, max(0.0, high-energy_kwh) / eta_c / cfg.dt_hours)
    power = float(np.clip(request_kw, -charge_limit, discharge_limit))
    next_energy = energy_kwh + (eta_c * max(-power, 0) - max(power, 0) / eta_d) * cfg.dt_hours
    return power, float(next_energy)


class EnergySystem:
    def __init__(self, day, cfg=None):
        self.cfg = cfg or Config()
        if len(day) != self.cfg.horizon:
            raise ValueError("One complete 24-hour day is required")
        self.day = day.reset_index(drop=True)
        self.values = self.day.drop(columns="timestamp").to_dict("records")
        self.t = 0
        self.battery_kwh = self.cfg.initial_soc * self.cfg.battery_capacity_kwh
        self.tes_kwh = self.cfg.initial_soc * self.cfg.tes_capacity_kwh
        self.previous_chp_gas_kw = 0.0

    @property
    def current(self):
        if self.t >= self.cfg.horizon:
            raise RuntimeError("Episode has ended; reset before acting")
        return self.values[self.t]

    def observe(self):
        # A finite-horizon terminal state has no next-day exogenous information.
        if self.t >= self.cfg.horizon:
            obs = np.zeros(13, dtype=np.float32)
            obs[10:13] = [self.battery_kwh/self.cfg.battery_capacity_kwh,
                          self.tes_kwh/self.cfg.tes_capacity_kwh,
                          self.previous_chp_gas_kw/self.cfg.chp_gas_max_kw]
            return obs
        r = self.current
        return np.array([
            np.sin(2*np.pi*self.t/24), np.cos(2*np.pi*self.t/24), (24-self.t)/24,
            r["electric_load_kw"]/1000, r["heat_load_kw"]/1000, r["cooling_load_kw"]/1000,
            r["pv_kw"]/1000, r["wind_kw"]/1000,
            r["buy_price_cny_per_kwh"], r["sell_price_cny_per_kwh"],
            self.battery_kwh/self.cfg.battery_capacity_kwh,
            self.tes_kwh/self.cfg.tes_capacity_kwh,
            self.previous_chp_gas_kw/self.cfg.chp_gas_max_kw,
        ], dtype=np.float32)

    def step(self, action):
        r, c = self.current, self.cfg
        raw = np.asarray(action, dtype=float)
        if raw.shape != (5,) or not np.isfinite(raw).all():
            raise ValueError("Action must contain exactly five finite numbers")
        a = np.clip(raw, -1.0, 1.0)
        chp_requested = (a[0]+1)/2 * c.chp_gas_max_kw
        ramp = c.chp_ramp_kw_per_hour * c.dt_hours
        chp_gas = float(np.clip(chp_requested, max(0, self.previous_chp_gas_kw-ramp),
                                min(c.chp_gas_max_kw, self.previous_chp_gas_kw+ramp)))
        chp_e, chp_h = chp_gas*c.chp_electric_eff, chp_gas*c.chp_heat_eff
        hp_e = (a[1]+1)/2 * c.hp_electric_max_kw
        hp_h = hp_e*c.hp_cop
        batt, next_batt = storage_dispatch(a[2]*c.battery_power_kw, self.battery_kwh,
            c.battery_capacity_kwh, c.battery_power_kw, c.battery_charge_eff, c.battery_discharge_eff, c)
        tes, next_tes = storage_dispatch(a[3]*c.tes_power_kw, self.tes_kwh,
            c.tes_capacity_kwh, c.tes_power_kw, c.tes_charge_eff, c.tes_discharge_eff, c)
        # Automatic residual equipment is deterministic, not another learned agent.
        ac_h = min((a[4]+1)/2*c.ac_heat_max_kw, r["cooling_load_kw"]/c.ac_cop)
        ac_c = ac_h*c.ac_cop
        ec_c = min(c.ec_cooling_max_kw, max(0, r["cooling_load_kw"]-ac_c))
        ec_e = ec_c/c.ec_cop
        cold_slack = max(0, r["cooling_load_kw"]-ac_c-ec_c)
        heat_residual = r["heat_load_kw"] + ac_h - chp_h - hp_h - tes
        boiler_h = min(c.boiler_heat_max_kw, max(0, heat_residual))
        boiler_gas = boiler_h/c.boiler_eff
        heat_slack = max(0, heat_residual-boiler_h)
        heat_dump = max(0, -heat_residual)
        renewable = r["pv_kw"]+r["wind_kw"]
        net_import = r["electric_load_kw"] + hp_e + ec_e - renewable - chp_e - batt
        grid_buy = min(c.grid_import_max_kw, max(0, net_import))
        grid_sell = min(c.grid_export_max_kw, max(0, -net_import))
        electric_slack = max(0, net_import-grid_buy)
        excess = max(0, -net_import-grid_sell)
        curtailed = min(renewable, excess)
        electric_dump = max(0, excess-curtailed)
        gas = chp_gas+boiler_gas
        emission = c.dt_hours*(grid_buy*c.grid_emission_kg_per_kwh + gas*c.gas_emission_kg_per_kwh)
        grid_cost = c.dt_hours*(grid_buy*r["buy_price_cny_per_kwh"]-grid_sell*r["sell_price_cny_per_kwh"])
        gas_cost = gas*c.gas_price_cny_per_kwh*c.dt_hours
        wear_cost = c.dt_hours*(abs(batt)*c.battery_wear_cny_per_kwh + abs(tes)*c.tes_wear_cny_per_kwh)
        carbon_cost = emission*c.carbon_cost_cny_per_kg
        operating_cost = grid_cost+gas_cost+wear_cost+carbon_cost
        # Electrical dumping is not an installed device: its use is infeasible.
        infeasible_kw = electric_slack+heat_slack+cold_slack+electric_dump
        constraint_penalty = c.dt_hours*(infeasible_kw*c.infeasible_penalty_cny_per_kwh
            + curtailed*c.curtail_penalty_cny_per_kwh + heat_dump*c.heat_dump_penalty_cny_per_kwh)
        terminal_gap = 0.0
        if self.t == c.horizon-1:
            terminal_gap = abs(next_batt-c.initial_soc*c.battery_capacity_kwh) + abs(next_tes-c.initial_soc*c.tes_capacity_kwh)
        terminal_penalty = terminal_gap*c.terminal_penalty_cny_per_kwh
        objective = operating_cost+constraint_penalty+terminal_penalty
        executed = np.array([2*chp_gas/c.chp_gas_max_kw-1, 2*hp_e/c.hp_electric_max_kw-1,
            batt/c.battery_power_kw, tes/c.tes_power_kw, 2*ac_h/c.ac_heat_max_kw-1])
        info = {
            "timestamp": str(self.day.iloc[self.t]["timestamp"]), "hour": self.t,
            **r,
            "chp_gas_kw": chp_gas, "chp_electric_kw": chp_e, "chp_heat_kw": chp_h,
            "hp_electric_kw": hp_e, "hp_heat_kw": hp_h,
            "ac_heat_kw": ac_h, "ac_cooling_kw": ac_c, "ec_cooling_kw": ec_c, "ec_electric_kw": ec_e,
            "boiler_heat_kw": boiler_h, "gas_kw": gas,
            "battery_kw": batt, "tes_kw": tes,
            "battery_energy_before_kwh": self.battery_kwh, "tes_energy_before_kwh": self.tes_kwh,
            "battery_energy_kwh": next_batt, "tes_energy_kwh": next_tes,
            "battery_soc": next_batt/c.battery_capacity_kwh, "tes_soc": next_tes/c.tes_capacity_kwh,
            "grid_import_kw": grid_buy, "grid_export_kw": grid_sell,
            "renewable_curtailed_kw": curtailed, "heat_dump_kw": heat_dump,
            "electric_slack_kw": electric_slack, "heat_slack_kw": heat_slack,
            "cooling_slack_kw": cold_slack, "electric_dump_kw": electric_dump,
            "infeasible": bool(infeasible_kw > 1e-6),
            "action_correction_l1": float(np.abs(raw-executed).sum()),
            "electric_residual_kw": renewable-curtailed+chp_e+batt+grid_buy+electric_slack
                -r["electric_load_kw"]-hp_e-ec_e-grid_sell-electric_dump,
            "heat_residual_kw": chp_h+hp_h+boiler_h+tes+heat_slack-r["heat_load_kw"]-ac_h-heat_dump,
            "cooling_residual_kw": ac_c+ec_c+cold_slack-r["cooling_load_kw"],
            "grid_cost_cny": grid_cost, "gas_cost_cny": gas_cost, "wear_cost_cny": wear_cost,
            "carbon_cost_cny": carbon_cost, "operating_cost_cny": operating_cost,
            "emission_kg": emission, "constraint_penalty_cny": constraint_penalty,
            "terminal_gap_kwh": terminal_gap, "terminal_penalty_cny": terminal_penalty,
            "objective_cny": objective, "reward": -objective/c.reward_scale_cny,
        }
        for i in range(5):
            info[f"action_raw_{i}"] = float(raw[i])
            info[f"action_executed_{i}"] = float(executed[i])
        self.battery_kwh, self.tes_kwh = next_batt, next_tes
        self.previous_chp_gas_kw = chp_gas
        self.t += 1
        return self.observe(), float(info["reward"]), self.t == c.horizon, info
