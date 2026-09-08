"""Gymnasium adapter; the physical core does not require the RL dependencies."""
import gymnasium as gym
from gymnasium import spaces
import numpy as np
from .config import Config
from .core import EnergySystem


class IESEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, days, cfg=None):
        super().__init__()
        if not days:
            raise ValueError("At least one day is required")
        self.days, self.cfg = days, cfg or Config()
        self.action_space = spaces.Box(-1.0, 1.0, shape=(5,), dtype=np.float32)
        self.observation_space = spaces.Box(-np.inf, np.inf, shape=(13,), dtype=np.float32)
        self.system = None

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        index = (options or {}).get("day_index")
        if index is None:
            index = int(self.np_random.integers(len(self.days)))
        if not isinstance(index, (int, np.integer)) or not 0 <= index < len(self.days):
            raise ValueError("Invalid day_index")
        self.system = EnergySystem(self.days[index], self.cfg)
        return self.system.observe(), {"day_index": int(index)}

    def step(self, action):
        if self.system is None:
            raise RuntimeError("Call reset before step")
        obs, reward, terminated, info = self.system.step(action)
        # Daily terminal objective and remaining-time observation define the horizon.
        return obs, reward, terminated, False, info
