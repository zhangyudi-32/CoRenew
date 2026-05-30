import copy
import json
import os
import numpy as np
from datetime import datetime

from .planner import PlannerRules
from .developer import DeveloperRules


class rule_agent:

    def __init__(self, envs, args, agent_name=None, type=None):
        self.envs = envs
        self.eval_env = copy.copy(envs)
        self.args = args
        self.agent_name = agent_name
        self.agent_type = type
        self.on_policy = True

        if self.agent_name == "planner":
            planner_cfg = getattr(self.args, "planner_rule", {})
            self.planner_policy = planner_cfg.get("policy", "baseline")
            self.planner_noise = planner_cfg.get("noise_scale", 0.0)


            PlannerRules.reset()

        base_log_dir = getattr(self.args, "base_log_dir", "./log")

        run_timestamp = getattr(self.args, "run_timestamp", "unknown_run")

        community_name = getattr(self.envs, "community_info", {}).get(
            "name", "unknown_community"
        )
        safe_community = str(community_name).strip().replace("/", "_").replace(" ", "_")

        run_log_dir = os.path.join(
            base_log_dir,
            safe_community,
            run_timestamp
        )
        os.makedirs(run_log_dir, exist_ok=True)

        self.log_path = os.path.join(run_log_dir, f"rule_raw_{self.agent_name}.jsonl")
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)


    def get_action(self, obs_tensor):
        name = self.agent_name
        if self.agent_name == "planner":
            planner_cfg = getattr(self.args, "planner_rule", {})
            self.agent_type = planner_cfg.get("policy", "baseline")
        elif self.agent_name == "developer":
            developer_cfg = getattr(self.args, "developer_rule", {})
            self.agent_type = developer_cfg.get("policy", "baseline")
        else:
            self.agent_type = "unknown"

        if name == "planner":
            max_ext = getattr(self.envs, "max_extension_ratio", 0.3)
            max_subsidy = getattr(self.args, "cash_subsidy_cap", 0.10)
            global_rule_params = getattr(self.args, "global_rule_params", None)

            action = PlannerRules.get_action(
                policy_type=self.planner_policy,
                obs=obs_tensor,
                max_extension_ratio=max_ext,
                max_subsidy_ratio=max_subsidy,
                noise_scale=self.planner_noise,
                society=self.envs,
                rule_params=global_rule_params,
            )
        elif name == "developer":
            dev_entity = self.envs.developer

            dev_cfg = getattr(self.args, "developer_rule", {})
            dev_policy = dev_cfg.get("policy", "baseline")

            self.agent_type = dev_policy

            action = DeveloperRules.get_action(
                policy_type=dev_policy,
                obs=obs_tensor,
                dev_entity=dev_entity,
                society=self.envs,
            )

        else:
            raise ValueError(f"Unknown rule-based agent_name: {name}")

        self._log_rule_action(obs_tensor, action)

        return action


    def _log_rule_action(self, obs, action):
        record = {
            "timestamp": datetime.now().isoformat(),
            "agent_name": self.agent_name,
            "agent_type": self.agent_type,
            "obs": obs.tolist() if hasattr(obs, "tolist") else obs,
            "action": action.tolist() if hasattr(action, "tolist") else action,
        }
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def reset(self):
        if self.agent_name == "planner":
            PlannerRules.reset()

    def train(self, transition):
        return 0, 0

    def save(self, dir_path):
        pass
