import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
import numpy as np
from ies_drl.config import Config
from ies_drl.core import EnergySystem, storage_dispatch
from ies_drl.data import load_days
from ies_drl.generate_data import generate


class PhysicsTests(unittest.TestCase):
    def setUp(self):
        self.day = generate(20, 0).iloc[:24].reset_index(drop=True)

    def test_hand_calculated_dispatch_and_cost(self):
        for key, value in dict(electric_load_kw=100, heat_load_kw=90, cooling_load_kw=80,
                               pv_kw=20, wind_kw=10, buy_price_cny_per_kwh=.65,
                               sell_price_cny_per_kwh=.25).items():
            self.day[key] = value
        _, _, _, info = EnergySystem(self.day).step([-1, -1, 0, 0, -1])
        self.assertAlmostEqual(info["grid_import_kw"], 90)
        self.assertAlmostEqual(info["gas_kw"], 100)
        self.assertAlmostEqual(info["emission_kg"], 69.5)
        self.assertAlmostEqual(info["operating_cost_cny"], 92.06)
        self.assertFalse(info["infeasible"])

    def test_storage_efficiency_and_boundaries(self):
        c = Config()
        p, e = storage_dispatch(-120, 250, 500, 120, .95, .95, c)
        self.assertEqual(p, -120)
        self.assertAlmostEqual(e, 364)
        p, e = storage_dispatch(120, 60, 500, 120, .95, .95, c)
        self.assertAlmostEqual(p, 9.5)
        self.assertAlmostEqual(e, 50)
        p, e = storage_dispatch(-120, 449, 500, 120, .95, .95, c)
        self.assertAlmostEqual(e, 450)
        self.assertAlmostEqual(p, -1/.95)

    def test_random_trajectories_conserve_energy_and_respect_limits(self):
        rng, c = np.random.default_rng(4), Config()
        for _ in range(20):
            system, previous_chp = EnergySystem(self.day, c), 0
            for t in range(24):
                _, reward, done, info = system.step(rng.uniform(-1.5, 1.5, 5))
                self.assertTrue(np.isfinite(reward))
                for key in ["electric_residual_kw", "heat_residual_kw", "cooling_residual_kw"]:
                    self.assertLess(abs(info[key]), 1e-8)
                for key in ["battery_soc", "tes_soc"]:
                    self.assertGreaterEqual(info[key], c.soc_min-1e-10)
                    self.assertLessEqual(info[key], c.soc_max+1e-10)
                self.assertLessEqual(abs(info["chp_gas_kw"]-previous_chp), c.chp_ramp_kw_per_hour+1e-10)
                self.assertLessEqual(info["grid_import_kw"], c.grid_import_max_kw)
                self.assertEqual(info["grid_import_kw"]*info["grid_export_kw"], 0)
                previous_chp = info["chp_gas_kw"]
                self.assertEqual(done, t == 23)
            with self.assertRaises(RuntimeError):
                system.step(np.zeros(5))

    def test_shortages_are_not_hidden_by_balance_slack(self):
        c = replace(Config(), grid_import_max_kw=0, boiler_heat_max_kw=0, ec_cooling_max_kw=0)
        self.day[["pv_kw", "wind_kw"]] = 0.0
        _, _, _, info = EnergySystem(self.day, c).step([-1, -1, 0, 0, -1])
        self.assertTrue(info["infeasible"])
        self.assertGreater(info["electric_slack_kw"], 0)
        self.assertGreater(info["heat_slack_kw"], 0)
        self.assertGreater(info["cooling_slack_kw"], 0)
        self.assertAlmostEqual(info["electric_residual_kw"], 0)

    def test_renewable_curtailment_and_terminal_penalty(self):
        self.day["pv_kw"] = 2000.0
        system = EnergySystem(self.day)
        for _ in range(24):
            _, _, _, info = system.step([-1, -1, -1, -1, -1])
        self.assertGreater(info["renewable_curtailed_kw"], 0)
        self.assertEqual(info["electric_dump_kw"], 0)
        self.assertGreater(info["terminal_gap_kwh"], 0)
        self.assertAlmostEqual(info["terminal_penalty_cny"], 2*info["terminal_gap_kwh"])

    def test_invalid_action_and_config_rejected(self):
        for a in ([0, 0], [0, 0, 0, 0, np.nan]):
            with self.assertRaises(ValueError):
                EnergySystem(self.day).step(a)
        for kwargs in ({"battery_capacity_kwh": 0}, {"boiler_eff": 2}, {"dt_hours": .25}):
            with self.assertRaises(ValueError):
                Config(**kwargs)

    def test_csv_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"day.csv"
            self.day.to_csv(path, index=False)
            self.assertEqual(len(load_days(path)), 1)
            for bad in (self.day.iloc[:-1], self.day.assign(pv_kw=np.nan),
                        self.day.assign(timestamp=self.day.iloc[0].timestamp)):
                bad.to_csv(path, index=False)
                with self.assertRaises(ValueError):
                    load_days(path)


if __name__ == "__main__":
    unittest.main()
