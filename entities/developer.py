import numpy as np
from gymnasium.spaces import Box
from entities.base_entity import BaseEntity
from utils.utils import load_public_service_projects


class DeveloperEntity(BaseEntity):
    name = "developer"

    @staticmethod
    def _parse_force_build(value):
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        v = str(value).strip().lower()
        if v in {"true", "1", "yes", "y", "on"}:
            return True
        if v in {"false", "0", "no", "n", "off"}:
            return False
        return None

    def __init__(self, scenario_config, comm_info, cfg):
        super().__init__()
        self.cfg = cfg
        utility_cfg = getattr(cfg, "utility", {}) or {}
        self.utility_weights = utility_cfg.get("developer", {}) if isinstance(utility_cfg, dict) else {}

        self.public_service_projects = load_public_service_projects()
        assert len(self.public_service_projects) == 1
        self.public_service = self.public_service_projects[0]
        self.force_build_public_service = self._parse_force_build(
            scenario_config.get("force_build_public_service", None)
        )
        self.build_public_service = (
            bool(self.force_build_public_service)
            if self.force_build_public_service is not None
            else False
        )

        self.parking_price_anchor = float(comm_info["parking_price"]) * 30.0
        self.base_price_anchor = float(
            scenario_config.get("base_price", 3800.0)
        )
        self.extension_price_anchor = float(
            comm_info.get(
                "extension_price",
                scenario_config.get("extension_price", 10000.0),
            )
        )

        self.base_price = self.base_price_anchor
        self.extension_price = float(
            scenario_config.get("extension_price", self.extension_price_anchor)
        )
        self.parking_fee = float(
            scenario_config.get("parking_fee", self.parking_price_anchor)
        )

        self.action_dim = 4
        self.real_action_min = np.array([0.0, 0.0, 0.0, 0.0], dtype=np.float32)
        self.real_action_max = np.array([50000000.0, 50000000.0, 5000000.0, 1.0], dtype=np.float32)
        self.action_space = Box(
            low=self.real_action_min,
            high=self.real_action_max,
            shape=(self.action_dim,),
            dtype=np.float32,
        )

        self.profit = 0.0
        self.profit_rate = 0.0
        self.cost = 0.0


    def reset(self, scenario_config=None):
        if scenario_config is not None:
            self.base_price = float(
                scenario_config.get("base_price", self.base_price_anchor)
            )
            self.extension_price = float(
                scenario_config.get("extension_price", self.extension_price_anchor)
            )
            self.parking_fee = float(
                scenario_config.get("parking_fee", self.parking_price_anchor)
            )

        if scenario_config is not None:
            self.force_build_public_service = self._parse_force_build(
                scenario_config.get("force_build_public_service", self.force_build_public_service)
            )

        self.build_public_service = (
            bool(self.force_build_public_service)
            if self.force_build_public_service is not None
            else False
        )
        self.profit = 0.0
        self.profit_rate = 0.0
        self.cost = 0.0

    def get_action(self, action: np.ndarray):
        a = np.asarray(action, dtype=np.float32)

        old_base = self.base_price
        old_ext = self.extension_price
        old_park = self.parking_fee
        old_service = self.build_public_service

        self.base_price = float(a[0])
        self.extension_price = float(a[1])
        self.parking_fee = float(a[2])
        if self.force_build_public_service is None:
            self.build_public_service = bool(a[3] >= 0.5)
        else:
            self.build_public_service = bool(self.force_build_public_service)

        print(
            "[DEV ACTION UPDATE]\n"
            f"  base_price: {old_base:.2f} → {self.base_price:.2f} "
            f"(Δ={self.base_price - old_base:+.2f})\n"
            f"  extension_price: {old_ext:.2f} → {self.extension_price:.2f} "
            f"(Δ={self.extension_price - old_ext:+.2f})\n"
            f"  parking_fee: {old_park:.2f} → {self.parking_fee:.2f} "
            f"(Δ={self.parking_fee - old_park:+.2f})\n"
            f"  build_public_service: {old_service} → {self.build_public_service}"
        )


    def step(self, society):
        residents = society.residents
        ALL_N = float(society.all_N)
        ALL_ORIG_AREA = float(society.all_total_orig_area)
        share = residents.share


        planner_ratio = float(getattr(society.planner, "extension_ratio", society.max_extension_ratio))

        public_service_area = 0.0
        public_service_cost = 0.0
        if self.build_public_service:
            public_service_area = self.public_service["min_area"]
            public_service_cost = (
                self.public_service["min_area"]
                * self.public_service["unit_cost"]
            )

        total_existing_area = float(getattr(society, "all_total_orig_area", 0.0))
        if total_existing_area > 0:
            effective_ratio = max(0.0, planner_ratio - public_service_area / total_existing_area)
        else:
            effective_ratio = 0.0

        per_household_cap = residents.orig_area * effective_ratio
        feasible_ext_area = np.minimum(residents.ext_area, per_household_cap)
        feasible_ext_area = np.maximum(feasible_ext_area, 0.0)

        ext_area_total = float(
            np.sum(feasible_ext_area * (share * ALL_N))
        )
        parking_slots_total = float(
            np.sum(residents.want_parking * (share * ALL_N))
        )

        max_total_ext_area = float(getattr(society.planner, "extension_ratio", society.max_extension_ratio)) * ALL_ORIG_AREA
        if ext_area_total + public_service_area > max_total_ext_area:

            ext_area_total = max(0.0, max_total_ext_area - public_service_area)

        w = self.utility_weights if isinstance(self.utility_weights, dict) else {}
        w_base_rev = float(w.get("base_revenue", 1.0))
        w_ext_rev = float(w.get("extension_revenue", 1.0))
        w_park_rev = float(w.get("parking_revenue", 1.0))
        w_base_cost = float(w.get("base_cost", 1.0))
        w_ext_cost = float(w.get("extension_cost", 1.0))
        w_park_cost = float(w.get("parking_cost", 1.0))
        w_service_cost = float(w.get("public_service_cost", 1.0))

        revenue = (
            w_base_rev * ALL_ORIG_AREA * self.base_price
            + w_ext_rev * ext_area_total * self.extension_price
            + w_park_rev * parking_slots_total * self.parking_fee
        )

        unit_construction_cost = 0.95 * self.base_price_anchor
        construction_cost = (
            w_base_cost * ALL_ORIG_AREA * unit_construction_cost
            + w_ext_cost * ext_area_total * unit_construction_cost
        )

        parking_construction_cost = (
            w_park_cost
            * parking_slots_total
            * society.cfg.get("parking_area_per_slot", 25.0)
            * society.cfg.get("parking_unit_construction_cost", 2500.0)
        )

        cost = construction_cost + parking_construction_cost + w_service_cost * public_service_cost

        self.cost = cost
        self.profit = revenue - cost
        self.profit_rate = float(self.profit / max(cost, 1e-8))

        society.scenario_config["base_price"] = self.base_price
        society.scenario_config["extension_price"] = self.extension_price
        society.scenario_config["parking_fee"] = self.parking_fee


    def evaluate_profit_rate(
        self,
        *,
        base_price: float,
        extension_price: float,
        parking_fee: float,
        build_public_service: bool,
        society
    ) -> float:

        residents = society.residents
        ALL_N = float(society.all_N)
        ALL_ORIG_AREA = float(society.all_total_orig_area)
        share = residents.share

        planner_ratio = float(getattr(society.planner, "extension_ratio", society.max_extension_ratio))

        public_service_area = 0.0
        public_service_cost = 0.0
        if build_public_service:
            public_service_area = self.public_service["min_area"]
            public_service_cost = (
                self.public_service["min_area"]
                * self.public_service["unit_cost"]
            )

        total_existing_area = float(getattr(society, "all_total_orig_area", 0.0))
        if total_existing_area > 0:
            effective_ratio = max(0.0, planner_ratio - public_service_area / total_existing_area)
        else:
            effective_ratio = 0.0

        per_household_cap = residents.orig_area * effective_ratio
        feasible_ext_area = np.minimum(residents.ext_area, per_household_cap)
        feasible_ext_area = np.maximum(feasible_ext_area, 0.0)

        ext_area_total = float(
            np.sum(feasible_ext_area * (share * ALL_N))
        )
        parking_slots_total = float(
            np.sum(residents.want_parking * (share * ALL_N))
        )

        max_total_ext_area = float(getattr(society.planner, "extension_ratio", society.max_extension_ratio)) * ALL_ORIG_AREA
        if ext_area_total + public_service_area > max_total_ext_area:
            ext_area_total = max(0.0, max_total_ext_area - public_service_area)

        w = self.utility_weights if isinstance(self.utility_weights, dict) else {}
        w_base_rev = float(w.get("base_revenue", 1.0))
        w_ext_rev = float(w.get("extension_revenue", 1.0))
        w_park_rev = float(w.get("parking_revenue", 1.0))
        w_base_cost = float(w.get("base_cost", 1.0))
        w_ext_cost = float(w.get("extension_cost", 1.0))
        w_park_cost = float(w.get("parking_cost", 1.0))
        w_service_cost = float(w.get("public_service_cost", 1.0))


        base_area_revenue = w_base_rev * ALL_ORIG_AREA * base_price
        extension_revenue = w_ext_rev * ext_area_total * extension_price
        parking_revenue = w_park_rev * parking_slots_total * parking_fee

        revenue = (
            base_area_revenue
            + extension_revenue
            + parking_revenue
        )


        unit_construction_cost = 0.95 * self.base_price_anchor

        construction_cost = (
            w_base_cost * ALL_ORIG_AREA * unit_construction_cost
            + w_ext_cost * ext_area_total * unit_construction_cost
        )

        parking_area_per_slot = society.cfg.get(
            "parking_area_per_slot", 25.0
        )
        parking_unit_cost = society.cfg.get(
            "parking_unit_construction_cost", 2500.0
        )
        parking_construction_cost = (
            w_park_cost
            * parking_slots_total
            * parking_area_per_slot
            * parking_unit_cost
        )

        cost = (
            construction_cost
            + parking_construction_cost
            + w_service_cost * public_service_cost
        )


        profit = revenue - cost
        profit_rate = float(profit / max(cost, 1e-8))

        return profit_rate


    def get_reward(self, society):
        return np.array([self.profit_rate], dtype=np.float32)

    def is_terminal(self):
        return False
