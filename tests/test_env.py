import importlib.util
import unittest
import numpy as np


@unittest.skipUnless(importlib.util.find_spec("stable_baselines3"), "Install the [rl] extra")
class EnvironmentTests(unittest.TestCase):
    def test_sb3_api_and_seed_reproducibility(self):
        from stable_baselines3.common.env_checker import check_env
        from ies_drl.env import IESEnv
        from ies_drl.generate_data import generate
        frame = generate(20, 42)
        days = [frame.iloc[i:i+24] for i in range(0, len(frame), 24)]
        env = IESEnv(days)
        check_env(env, warn=True)
        obs1, _ = env.reset(seed=10)
        obs2, _ = env.reset(seed=10)
        np.testing.assert_array_equal(obs1, obs2)
        for t in range(24):
            obs, _, terminated, truncated, _ = env.step(np.zeros(5))
            self.assertTrue(env.observation_space.contains(obs))
            self.assertEqual(terminated, t == 23)
            self.assertFalse(truncated)
        self.assertEqual(obs[2], 0)


if __name__ == "__main__":
    unittest.main()
