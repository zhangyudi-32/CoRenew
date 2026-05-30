import numpy as np
from gymnasium.spaces import Box
from entities.base_entity import BaseEntity

class PlannerEntity(BaseEntity):
    name = "planner"
    def __init__(self, cfg, scenario_config):

        super().__init__()
        self.cfg = cfg
        self.agent_id = getattr(cfg, "agent_id", None)
        self.extension_ratio = float(scenario_config.get("extension_ratio", 0.3))
        self.cash_subsidy_ratio = 0.0
        self.action_dim = 2
        self.real_action_min = np.array([0.0, 0.0], dtype=np.float32)
        self.real_action_max = np.array([0.5, 0.1], dtype=np.float32)
        self.action_space = Box(low=self.real_action_min, high=self.real_action_max, shape=(2,), dtype=np.float32)
        utility_cfg = getattr(cfg, "utility", {}) or {}
        self.utility_weights = utility_cfg.get("planner", {}) if isinstance(utility_cfg, dict) else {}
        self._pending_action = None


    def reset(self, society=None):
        self._pending_action = None


    def get_action(self, action: np.ndarray):
        self._pending_action = action


    def step(self, society):
        if self._pending_action is not None:
            self.extension_ratio = float(self._pending_action[0])
            self.cash_subsidy_ratio = float(self._pending_action[1])


        society.scenario_config["extension_ratio"] = self.extension_ratio
        society.scenario_config["cash_subsidy_ratio"] = self.cash_subsidy_ratio

    def get_reward(self, society):
        w = self.utility_weights if isinstance(self.utility_weights, dict) else {}
        w_agree = float(w.get("agree_ratio", 1.0))
        w_dev_profit = float(w.get("developer_profit_rate", 0.0))
        w_res_utility = float(w.get("resident_mean_utility", 0.0))

        agree_part = w_agree * float(getattr(society, "agree_ratio", 0.0))
        dev_part = w_dev_profit * float(getattr(society, "developer_profit_rate", 0.0))
        res_util = getattr(society.residents, "utility", None)
        res_part = w_res_utility * (float(np.mean(res_util)) if res_util is not None and len(res_util) > 0 else 0.0)

        reward = agree_part + dev_part + res_part
        return np.array([reward], dtype=np.float32)

    def is_terminal(self):
        return False
