import copy
import numpy as np
from gymnasium.spaces import Box, Dict
from datetime import datetime
import pandas as pd
from .set_observation import UrbanObservations
from entities.developer import DeveloperEntity
from entities.planner import PlannerEntity
from entities.resident import ResidentEntity
from utils.utils import load_public_service_projects

class UrbanRenewEnv:
    def __init__(self, cfg, scenario_config, resident_df, community_info):
        self.cfg = cfg
        self.max_rounds = cfg.get("rounds_num", 10)
        self.community_info = community_info
        self.scenario_config = scenario_config.copy()
        self.step_cnt = 0
        self.max_extension_ratio = float(scenario_config.get("max_extension_ratio", 0.3))

        assert hasattr(cfg, "all_agents_path"), "cfg must define all_agents_path"
        all_df = pd.read_csv(cfg.all_agents_path)
        community = (
            community_info.get("community")
            if isinstance(community_info, dict) and "community" in community_info
            else resident_df["community"].iloc[0]
        )

        all_comm = all_df[all_df["community"] == community].copy()

        self.all_N = len(all_comm)
        self.all_total_orig_area = float(all_comm["unit_size_sqm"].astype(float).sum())

        self.community_info["total_existing_area"] = self.all_total_orig_area
        self.subsidy_limit_ratio = float(scenario_config.get("subsidy_limit_ratio", 0.0))
        self.current_subsidy_ratio = 0.0

        self.public_service_projects = load_public_service_projects()

        assert len(self.public_service_projects) == 1,\
            "Only ONE public service is supported in binary build/not-build setting"

        self.community_info = copy.deepcopy(community_info)
        self.scenario_config = copy.deepcopy(scenario_config)
        self.agents = {
            "residents": ResidentEntity(resident_df, community_info,cfg),
            "planner": PlannerEntity(cfg, scenario_config),
            "developer": DeveloperEntity(scenario_config, community_info,cfg),
        }
        self.residents = self.agents["residents"]
        self.planner = self.agents["planner"]
        self.developer = self.agents["developer"]
        observations_dict = self.reset()

        for name, entity in self.agents.items():
            obs = observations_dict[name]
            if isinstance(obs, np.ndarray) and obs.ndim == 2:
                entity.observation_space = Box(low=-np.inf, high=np.inf, shape=(obs.shape[-1],), dtype=np.float32)
            else:
                entity.observation_space = Box(low=-np.inf, high=np.inf, shape=(obs.shape[-1],), dtype=np.float32)
        self.cash_subsidy_ratio = 0.0
        self.cash_subsidy_cap = float(scenario_config.get("cash_subsidy_cap", 0.0))
        self.is_subsidy_round = (self.step_cnt >= self.max_rounds - 3)
        self.display_mode = False
        self.last_planner_extension_ratio = 0.0
        self.last_planner_subsidy_ratio = 0.0
        self.developer_no_change_streak = 0
        self._last_dev_base_price = float(self.developer.base_price)
        self._last_dev_extension_price = float(self.developer.extension_price)
        self._last_dev_parking_fee = float(self.developer.parking_fee)
        self._last_dev_build_public_service = bool(self.developer.build_public_service)
    @property
    def action_spaces(self):
        return {
            self.residents.name: self.residents.action_space,
            self.planner.name: self.planner.action_space,
            self.developer.name: self.developer.action_space,
        }

    @property
    def observation_spaces(self):
        return {
            self.residents.name: self.residents.observation_space,
            self.planner.name: self.planner.observation_space,
            self.developer.name: self.developer.observation_space,
        }

    def is_valid(self, action_dict):
        expected = set(self.agents.keys())
        received = set(action_dict.keys())
        if expected != received:
            raise ValueError(f"Invalid actions. Expected agents: {expected}, Received: {received}")
        return action_dict

    def action_wrapper(self, action_dict):
        processed = {}
        for agent_name, agent_action in action_dict.items():
            processed[agent_name] = self.check_agent_action(self.agents[agent_name], agent_action, agent_name)
        return processed

    @staticmethod
    def check_agent_action(agent, agent_action, agent_name):
        expected_dim = agent.action_dim
        if expected_dim == 0:
            return None


        action = np.array(agent_action, dtype=np.float32)


        if agent_name == "residents":
            if action.ndim != 2 or action.shape[-1] != expected_dim:
                raise ValueError(f"Invalid actions for {agent_name}. Expected (N,{expected_dim}), got {action.shape}")
        else:
            if action.ndim != 1 or action.shape[-1] != expected_dim:
                raise ValueError(f"Invalid actions for {agent_name}. Expected ({expected_dim},), got {action.shape}")


        amin = np.array(agent.real_action_min, dtype=np.float32)
        amax = np.array(agent.real_action_max, dtype=np.float32)


        return np.clip(action, amin, amax)

    def get_actions(self, action_dict):
        valid = self.is_valid(action_dict)
        processed = self.action_wrapper(valid)

        if processed["planner"] is not None:
            self.last_planner_extension_ratio = float(processed["planner"][0])
            self.last_planner_subsidy_ratio = float(processed["planner"][1])
        else:
            self.last_planner_extension_ratio = 0.0
            self.last_planner_subsidy_ratio = 0.0

        desired_subsidy = self.last_planner_subsidy_ratio

        if self.cash_subsidy_cap > 0.0:
            self.cash_subsidy_ratio = float(
                min(max(desired_subsidy, 0.0), self.cash_subsidy_cap, 0.1)
            )
        else:
            self.cash_subsidy_ratio = 0.0

        self.is_subsidy_round = bool(self.cash_subsidy_ratio > 0.0)

        self.residents.get_action(processed["residents"])
        self.planner.get_action(processed["planner"])
        self.developer.get_action(processed["developer"])

        return processed


    def step(self, action_dict, t=None):
        self.get_actions(action_dict)


        self.planner.step(self)
        self.residents.step(self)
        self.developer.step(self)
        self._update_developer_policy_stability()

        self.update_metrics()
        self.step_cnt += 1
        self.done = self.is_terminal()

        next_obs = UrbanObservations(self).get_obs()


        self.last_agree_ratio = copy.copy(self.agree_ratio)

        return next_obs, self.rewards, self.done

    def _update_developer_policy_stability(self):
        eps = 1e-6
        cur_base = float(self.developer.base_price)
        cur_ext = float(self.developer.extension_price)
        cur_park = float(self.developer.parking_fee)
        cur_service = bool(self.developer.build_public_service)


        if int(self.step_cnt) == 0:
            self.developer_no_change_streak = 0
        else:
            unchanged = (
                abs(cur_base - self._last_dev_base_price) <= eps
                and abs(cur_ext - self._last_dev_extension_price) <= eps
                and abs(cur_park - self._last_dev_parking_fee) <= eps
                and cur_service == self._last_dev_build_public_service
            )
            if unchanged:
                self.developer_no_change_streak += 1
            else:
                self.developer_no_change_streak = 0

        self._last_dev_base_price = cur_base
        self._last_dev_extension_price = cur_ext
        self._last_dev_parking_fee = cur_park
        self._last_dev_build_public_service = cur_service


    def update_metrics(self):

        w = self.residents.voting_weight
        self.agree_ratio = float(np.average(self.residents.agree, weights=w)) if self.residents.N > 0 else 0.0

        self.required_ratio = float(self.community_info.get("required_agree_ratio", 0.90))


        self.developer_profit = float(getattr(self.developer, "profit", 0.0))
        self.developer_profit_rate = float(getattr(self.developer, "profit_rate", 0.0))


        ALL_N = float(self.all_N)
        share = self.residents.share

        self.total_ext_area_last = float(np.sum(self.residents.ext_area * (share * ALL_N)))

        parking_slots_total = float(np.sum(self.residents.want_parking * (share * ALL_N)))
        self.parking_demand_rate = float(parking_slots_total / max(ALL_N, 1.0))


        self.service_demand = float(getattr(self.developer, "build_public_service", 0.0))


        self.rewards = {
            self.residents.name: self.residents.get_reward(self),
            self.planner.name: self.planner.get_reward(self),
            self.developer.name: self.developer.get_reward(self),
        }

    def is_terminal(self):

        if self.agree_ratio >= self.required_ratio:
            return True

        if self.step_cnt >= self.max_rounds:
            return True

        if any([self.residents.is_terminal(), self.planner.is_terminal(), self.developer.is_terminal()]):
            return True
        return False

    def reset(self, **custom_cfg):
        from agents.rule_based.planner import PlannerRules
        PlannerRules.reset()
        self.step_cnt = 0
        self.done = False
        self.cash_subsidy_ratio = 0.0
        self.is_subsidy_round = False
        self.last_planner_extension_ratio = 0.0
        self.last_planner_subsidy_ratio = 0.0
        self.developer_no_change_streak = 0
        self._last_dev_base_price = float(self.developer.base_price)
        self._last_dev_extension_price = float(self.developer.extension_price)
        self._last_dev_parking_fee = float(self.developer.parking_fee)
        self._last_dev_build_public_service = bool(self.developer.build_public_service)

        self.scenario_config = copy.deepcopy(self.cfg.get("initial_scenario", self.scenario_config))

        self.planner.reset(self)
        self.developer.reset(self.scenario_config)
        self.residents.reset()


        self.agree_ratio = 0.0
        self.last_agree_ratio = 0.0
        self.total_ext_area_last = 0.0
        self.parking_demand_rate = 0.0
        self.service_demand_by_type = 0.0
        self.update_metrics()

        return UrbanObservations(self).get_obs()

    def get_checkpoint_state(self):
        return {
            "step_cnt": int(self.step_cnt),
            "done": bool(getattr(self, "done", False)),
            "agree_ratio": float(getattr(self, "agree_ratio", 0.0)),
            "last_agree_ratio": float(getattr(self, "last_agree_ratio", 0.0)),
            "required_ratio": float(
                getattr(self, "required_ratio", self.community_info.get("required_agree_ratio", 0.9))
            ),
            "cash_subsidy_ratio": float(getattr(self, "cash_subsidy_ratio", 0.0)),
            "cash_subsidy_cap": float(getattr(self, "cash_subsidy_cap", 0.0)),
            "is_subsidy_round": bool(getattr(self, "is_subsidy_round", False)),
            "max_extension_ratio": float(getattr(self, "max_extension_ratio", 0.0)),
            "last_planner_extension_ratio": float(getattr(self, "last_planner_extension_ratio", 0.0)),
            "last_planner_subsidy_ratio": float(getattr(self, "last_planner_subsidy_ratio", 0.0)),
            "developer_no_change_streak": int(getattr(self, "developer_no_change_streak", 0)),
            "_last_dev_base_price": float(getattr(self, "_last_dev_base_price", 0.0)),
            "_last_dev_extension_price": float(getattr(self, "_last_dev_extension_price", 0.0)),
            "_last_dev_parking_fee": float(getattr(self, "_last_dev_parking_fee", 0.0)),
            "_last_dev_build_public_service": bool(getattr(self, "_last_dev_build_public_service", False)),
            "total_ext_area_last": float(getattr(self, "total_ext_area_last", 0.0)),
            "parking_demand_rate": float(getattr(self, "parking_demand_rate", 0.0)),
            "service_demand": float(getattr(self, "service_demand", 0.0)),
            "scenario_config": copy.deepcopy(self.scenario_config),
            "planner": {
                "extension_ratio": float(self.planner.extension_ratio),
                "cash_subsidy_ratio": float(self.planner.cash_subsidy_ratio),
            },
            "developer": {
                "base_price": float(self.developer.base_price),
                "extension_price": float(self.developer.extension_price),
                "parking_fee": float(self.developer.parking_fee),
                "build_public_service": bool(self.developer.build_public_service),
                "profit": float(self.developer.profit),
                "profit_rate": float(self.developer.profit_rate),
                "cost": float(self.developer.cost),
            },
            "residents": {
                "agree": self.residents.agree.copy(),
                "ext_area": self.residents.ext_area.copy(),
                "want_parking": self.residents.want_parking.copy(),
                "expected_base_price": self.residents.expected_base_price.copy(),
                "last_expected_base_price": self.residents.last_expected_base_price.copy(),
                "expected_extension_price": self.residents.expected_extension_price.copy(),
                "last_expected_extension_price": self.residents.last_expected_extension_price.copy(),
                "quoted_base_price": self.residents.quoted_base_price.copy(),
                "last_quoted_base_price": self.residents.last_quoted_base_price.copy(),
                "quoted_extension_price": self.residents.quoted_extension_price.copy(),
                "last_quoted_extension_price": self.residents.last_quoted_extension_price.copy(),
                "expected_extension_area": self.residents.expected_extension_area.copy(),
                "last_expected_extension_area": self.residents.last_expected_extension_area.copy(),
                "utility": self.residents.utility.copy(),
                "last_agree": self.residents.last_agree.copy(),
                "subsidy_ratio": float(self.residents.subsidy_ratio),
                "subsidy_amount": self.residents.subsidy_amount.copy(),
                "last_subsidy_amount": self.residents.last_subsidy_amount.copy(),
            },
        }

    def load_checkpoint_state(self, state):
        self.step_cnt = int(state.get("step_cnt", 0))
        self.done = bool(state.get("done", False))
        self.agree_ratio = float(state.get("agree_ratio", 0.0))
        self.last_agree_ratio = float(state.get("last_agree_ratio", 0.0))
        self.required_ratio = float(
            state.get("required_ratio", self.community_info.get("required_agree_ratio", 0.9))
        )
        self.cash_subsidy_ratio = float(state.get("cash_subsidy_ratio", 0.0))
        self.cash_subsidy_cap = float(state.get("cash_subsidy_cap", self.cash_subsidy_cap))
        self.is_subsidy_round = bool(state.get("is_subsidy_round", False))
        self.max_extension_ratio = float(state.get("max_extension_ratio", self.max_extension_ratio))
        self.last_planner_extension_ratio = float(state.get("last_planner_extension_ratio", 0.0))
        self.last_planner_subsidy_ratio = float(state.get("last_planner_subsidy_ratio", 0.0))
        self.developer_no_change_streak = int(state.get("developer_no_change_streak", 0))
        self._last_dev_base_price = float(state.get("_last_dev_base_price", self.developer.base_price))
        self._last_dev_extension_price = float(
            state.get("_last_dev_extension_price", self.developer.extension_price)
        )
        self._last_dev_parking_fee = float(state.get("_last_dev_parking_fee", self.developer.parking_fee))
        self._last_dev_build_public_service = bool(
            state.get("_last_dev_build_public_service", self.developer.build_public_service)
        )
        self.total_ext_area_last = float(state.get("total_ext_area_last", 0.0))
        self.parking_demand_rate = float(state.get("parking_demand_rate", 0.0))
        self.service_demand = float(state.get("service_demand", 0.0))
        self.scenario_config = copy.deepcopy(state.get("scenario_config", self.scenario_config))

        planner_state = state.get("planner", {})
        self.planner.extension_ratio = float(planner_state.get("extension_ratio", self.planner.extension_ratio))
        self.planner.cash_subsidy_ratio = float(
            planner_state.get("cash_subsidy_ratio", self.planner.cash_subsidy_ratio)
        )
        self.planner._pending_action = None

        developer_state = state.get("developer", {})
        self.developer.base_price = float(developer_state.get("base_price", self.developer.base_price))
        self.developer.extension_price = float(
            developer_state.get("extension_price", self.developer.extension_price)
        )
        self.developer.parking_fee = float(developer_state.get("parking_fee", self.developer.parking_fee))
        self.developer.build_public_service = bool(
            developer_state.get("build_public_service", self.developer.build_public_service)
        )
        self.developer.profit = float(developer_state.get("profit", 0.0))
        self.developer.profit_rate = float(developer_state.get("profit_rate", 0.0))
        self.developer.cost = float(developer_state.get("cost", 0.0))

        resident_state = state.get("residents", {})

        def _arr(name, dtype=float):
            cur = getattr(self.residents, name)
            return np.asarray(resident_state.get(name, cur), dtype=dtype)

        self.residents.agree = _arr("agree", dtype=int)
        self.residents.ext_area = _arr("ext_area", dtype=float)
        self.residents.want_parking = _arr("want_parking", dtype=int)
        self.residents.expected_base_price = _arr("expected_base_price", dtype=float)
        self.residents.last_expected_base_price = _arr("last_expected_base_price", dtype=float)
        self.residents.expected_extension_price = _arr("expected_extension_price", dtype=float)
        self.residents.last_expected_extension_price = _arr("last_expected_extension_price", dtype=float)
        self.residents.quoted_base_price = _arr("quoted_base_price", dtype=float)
        self.residents.last_quoted_base_price = _arr("last_quoted_base_price", dtype=float)
        self.residents.quoted_extension_price = _arr("quoted_extension_price", dtype=float)
        self.residents.last_quoted_extension_price = _arr("last_quoted_extension_price", dtype=float)
        self.residents.expected_extension_area = _arr("expected_extension_area", dtype=float)
        self.residents.last_expected_extension_area = _arr("last_expected_extension_area", dtype=float)
        self.residents.utility = _arr("utility", dtype=float)
        self.residents.last_agree = _arr("last_agree", dtype=int)
        self.residents.subsidy_ratio = float(
            resident_state.get("subsidy_ratio", getattr(self.residents, "subsidy_ratio", 0.0))
        )
        self.residents.subsidy_amount = _arr("subsidy_amount", dtype=float)
        self.residents.last_subsidy_amount = _arr("last_subsidy_amount", dtype=float)
        if hasattr(self.residents, "_pending_actions"):
            delattr(self.residents, "_pending_actions")

        self.update_metrics()
        self.done = bool(state.get("done", self.is_terminal()))
