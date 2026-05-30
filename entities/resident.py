import numpy as np
from gymnasium.spaces import Box
from entities.base_entity import BaseEntity
import pandas as pd
from utils.utils import load_public_service_projects


class ResidentEntity(BaseEntity):
    name = "residents"

    def __init__(self, resident_df, comm_info,cfg):
        super().__init__()

        self.N = len(resident_df)

        self.agent_ids = resident_df["agent_id"].values
        self.orig_area = resident_df["unit_size_sqm"].astype(float).values
        self.community_name = resident_df["community"].values
        self.voting_weight = resident_df["final_voting_weight"].astype(float).values
        self.sum_weight = float(self.voting_weight.sum()) if self.N > 0 else 1.0
        self.share = self.voting_weight / self.sum_weight
        self.annual_income = resident_df["annual_income_rmb"].to_numpy(dtype=float)
        subsidy_cfg = cfg.get("subsidy", {})
        self.low_income_only = subsidy_cfg.get("low_income_only", False)
        self.low_income_threshold = subsidy_cfg.get(
            "low_income_threshold",
            float("inf")
        )

        self.is_low_income = self.annual_income < self.low_income_threshold

        self.household_size = resident_df["household_size"].astype(float).values
        self.household_income_total = resident_df["household_monthly_income_rmb"].astype(float).values


        self.objective = resident_df.get("objective", pd.Series(["balanced"] * self.N)).values

        self.comm_info = comm_info
        self.service_projects = load_public_service_projects()

        utility_cfg = getattr(cfg, "utility", {}) or {}
        self.utility_weights = (
            utility_cfg.get("resident", {}) if isinstance(utility_cfg, dict) else {}
        )

        self.reset()


        self.action_dim = 8
        self.real_action_min = np.array(
            [0, 0, 0, 0, 0, 0, 0, 0], dtype=np.float32
        )
        self.real_action_max = np.array(
            [1, 60, 1, 100000, 100000, 100000, 100000, 60], dtype=np.float32
        )

        self.action_space = Box(
            low=np.tile(self.real_action_min, (self.N, 1)),
            high=np.tile(self.real_action_max, (self.N, 1)),
            dtype=np.float32,
        )


    def reset(self):
        self.agree = np.zeros(self.N, dtype=int)
        self.ext_area = np.zeros(self.N)
        self.want_parking = np.zeros(self.N, dtype=int)
        self.expected_base_price = np.zeros(self.N)
        self.last_expected_base_price = np.zeros(self.N)
        self.expected_extension_price = np.zeros(self.N)
        self.last_expected_extension_price = np.zeros(self.N)
        self.quoted_base_price = np.zeros(self.N)
        self.last_quoted_base_price = np.zeros(self.N)
        self.quoted_extension_price = np.zeros(self.N)
        self.last_quoted_extension_price = np.zeros(self.N)
        self.expected_extension_area = np.zeros(self.N)
        self.last_expected_extension_area = np.zeros(self.N)
        self.utility = np.zeros(self.N)
        self.last_agree = np.zeros(self.N, dtype=int)
        self.subsidy_ratio = 0.0
        self.subsidy_amount = np.zeros(self.N)
        self.last_subsidy_amount = np.zeros(self.N)


    def get_action(self, actions: np.ndarray):

        self._pending_actions = actions


    def step(self, society):
        if not hasattr(self, "_pending_actions"):
            return

        a = self._pending_actions
        self.agree = (a[:, 0] >= 0.5).astype(int)
        self.last_agree = self.agree.copy()
        self.last_expected_base_price = self.expected_base_price.copy()
        self.last_expected_extension_price = self.expected_extension_price.copy()
        self.last_quoted_base_price = self.quoted_base_price.copy()
        self.last_quoted_extension_price = self.quoted_extension_price.copy()
        self.last_expected_extension_area = self.expected_extension_area.copy()

        self.ext_area = a[:, 1]
        self.want_parking = (a[:, 2] >= 0.5).astype(int)
        self.expected_base_price = a[:, 3]
        self.expected_extension_price = a[:, 4]
        self.quoted_base_price = a[:, 5]
        self.quoted_extension_price = a[:, 6]
        self.expected_extension_area = a[:, 7]




        subsidy_ratio = float(getattr(society, "cash_subsidy_ratio", 0.0))
        subsidy_ratio = min(max(subsidy_ratio, 0.0), 0.99)
        offered_base = float(society.developer.base_price) * (1.0 - subsidy_ratio)
        offered_ext = float(society.developer.extension_price) * (1.0 - subsidy_ratio)
        available_ext_area = self.orig_area * float(getattr(society.planner, "extension_ratio", society.max_extension_ratio))
        force_agree_mask = (
            (offered_base <= self.expected_base_price)
            & (offered_ext <= self.expected_extension_price)
            & (available_ext_area >= self.expected_extension_area)
        )
        self.agree[force_agree_mask] = 1
        self.last_agree = self.agree.copy()

        self.utility = self.compute_utility(society)



    def compute_utility(self, society):
        orig_area = self.orig_area
        comm = self.comm_info

        w = self.utility_weights if isinstance(self.utility_weights, dict) else {}
        w_base_cost = float(w.get("base_cost", 1.0))
        w_extension_cost = float(w.get("extension_cost", 1.0))
        w_parking_cost = float(w.get("parking_cost", 1.0))
        w_market_value = float(w.get("market_value", 1.0))
        w_subsidy = float(w.get("subsidy", 1.0))

        service = self.service_projects[0]
        public_service_area = (
            service["min_area"]
            if society.developer.build_public_service
            else 0.0
        )

        total_existing_area = float(comm["total_existing_area"])

        if total_existing_area <= 0:
            effective_ext_ratio = 0.0
        else:
            effective_ext_ratio = max(
                0.0,
                float(getattr(society.planner, "extension_ratio", society.max_extension_ratio))
                - public_service_area / total_existing_area
            )

        max_ext_area = orig_area * effective_ext_ratio

        base_price = float(society.developer.base_price)
        ext_cost_price = float(society.developer.extension_price) * 0.8
        market_price = float(comm["extension_price"])
        parking_fee = float(society.developer.parking_fee)

        chosen_ext = np.minimum(self.ext_area, max_ext_area)
        base_cost = w_base_cost * (orig_area * base_price)
        ext_cost = w_extension_cost * (chosen_ext * ext_cost_price)
        parking_cost = w_parking_cost * (parking_fee * self.want_parking)

        expand_cost = base_cost + ext_cost + parking_cost
        no_expand_cost = base_cost + parking_cost

        base_value = w_market_value * (orig_area * market_price)
        ext_value = w_market_value * (chosen_ext * market_price)

        expand_value = base_value + ext_value
        no_expand_value = base_value

        utility_expand = expand_value - expand_cost
        utility_no_expand = no_expand_value - no_expand_cost
        cost = np.where(chosen_ext > 0, expand_cost, no_expand_cost)

        self.subsidy_ratio = float(getattr(society, "cash_subsidy_ratio", 0.0))

        cost = np.where(chosen_ext > 0, expand_cost, no_expand_cost)

        if self.subsidy_ratio > 0 and w_subsidy != 0.0:
            subsidy = cost * self.subsidy_ratio * w_subsidy

            if self.low_income_only:
                self.subsidy_amount = np.where(
                    self.is_low_income,
                    subsidy,
                    0.0
                )
            else:
                self.subsidy_amount = subsidy
        else:
            self.subsidy_amount = np.zeros_like(cost)


        self.last_subsidy_amount = self.subsidy_amount.copy()
        self.total_cost = float(np.sum(cost))

        utility = np.where(
            chosen_ext > 0,
            utility_expand + self.subsidy_amount,
            utility_no_expand + self.subsidy_amount
        )
        return utility
    def get_reward(self, society):
        return self.utility.astype(np.float32)

    def is_terminal(self):
        return False
