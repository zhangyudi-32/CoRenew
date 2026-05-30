import numpy as np


class UrbanObservations:

    def __init__(self, society):
        self.society = society


    def get_global_obs(self) -> np.ndarray:
        step_ratio = self.society.step_cnt / max(self.society.max_rounds, 1)

        return np.array([
            float(self.society.agree_ratio),
            float(self.society.required_ratio),
            float(step_ratio),
            float(self.society.developer.base_price),
            float(self.society.developer.extension_price),
            float(self.society.developer.parking_fee),
            float(self.society.max_extension_ratio),
            float(self.society.planner.extension_ratio),
            float(self.society.developer.extension_price_anchor),
        ], dtype=np.float32)


    def get_residents_obs(self) -> np.ndarray:
        g = self.get_global_obs()
        r = self.society.residents

        is_subsidy_round = 1.0 if getattr(self.society, "is_subsidy_round", False) else 0.0
        cash_subsidy_cap = float(getattr(self.society, "cash_subsidy_cap", 0.0))
        subsidy_signal = np.array(
            [is_subsidy_round, cash_subsidy_cap],
            dtype=np.float32
        )
        global_with_subsidy = np.concatenate([g, subsidy_signal])

        private = np.column_stack([
            r.orig_area,
            r.ext_area,
            r.want_parking.astype(float),
            r.utility,
            r.last_expected_base_price,
            r.last_expected_extension_price,
            np.full(r.N, float(getattr(self.society, "cash_subsidy_ratio", 0.0)), dtype=np.float32),
            r.subsidy_amount,
            r.household_size,
            r.household_income_total,
            r.last_agree.astype(float),
        ]).astype(np.float32)

        global_rep = np.tile(global_with_subsidy, (r.N, 1))

        dev_build_public_service = float(
            getattr(self.society.developer, "build_public_service", 0.0)
        )
        dev_service_rep = np.full(
            (r.N, 1),
            dev_build_public_service,
            dtype=np.float32
        )

        return np.concatenate(
            [global_rep, private, dev_service_rep],
            axis=1
        )


    def get_planner_obs(self) -> np.ndarray:
        g = self.get_global_obs()
        r = self.society.residents

        private_scalar = np.array([
            self.society.total_ext_area_last,
            self.society.parking_demand_rate,
        ], dtype=np.float32)

        is_subsidy_round = 1.0 if getattr(self.society, "is_subsidy_round", False) else 0.0
        cash_subsidy_cap = float(getattr(self.society, "cash_subsidy_cap", 0.0))

        subsidy_info = np.array([
            is_subsidy_round,
            cash_subsidy_cap,
        ], dtype=np.float32)

        low_income_ratio = float(
            np.mean(r.is_low_income)
        )

        subsidy_low_income_only = float(
            r.low_income_only
        )
        targeting_info = np.array([
            low_income_ratio,
            subsidy_low_income_only,
        ], dtype=np.float32)

        planner_memory = np.array([
            float(self.society.last_planner_extension_ratio),
            float(self.society.last_planner_subsidy_ratio),
        ], dtype=np.float32)

        forced_public_service = np.array([
            float(getattr(self.society.developer, "build_public_service", 0.0))
        ], dtype=np.float32)

        return np.concatenate([
            g,
            private_scalar,
            subsidy_info,
            targeting_info,
            planner_memory,
            forced_public_service,
        ]).astype(np.float32)


    def get_developer_obs(self) -> np.ndarray:
        g = self.get_global_obs()
        dev = self.society.developer

        private_scalar = np.array([
            dev.parking_price_anchor,
            dev.profit_rate,
            self.society.total_ext_area_last,
            self.society.parking_demand_rate,
            dev.profit,
        ], dtype=np.float32)
        delta_agree = float(
            self.society.agree_ratio
            - getattr(self.society, "last_agree_ratio", 0.0)
        )

        forced_public_service = np.array([
            float(getattr(self.society.developer, "build_public_service", 0.0))
        ], dtype=np.float32)

        return np.concatenate([
            g,
            private_scalar,
            forced_public_service,
            np.array([delta_agree], dtype=np.float32),
        ]).astype(np.float32)


    def get_obs(self) -> dict:
        return {
            "residents": self.get_residents_obs(),
            "planner": self.get_planner_obs(),
            "developer": self.get_developer_obs(),
        }
