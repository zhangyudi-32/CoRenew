import numpy as np


class PlannerRules:

    _rng = np.random.default_rng(42)

    @staticmethod
    def reset():
        PlannerRules._rng = np.random.default_rng(42)

    @staticmethod
    def get_action(
        policy_type,
        obs,
        *,
        max_extension_ratio=0.3,
        max_subsidy_ratio=0.10,
        noise_scale=0.0,
        society=None,
        rule_params=None,
    ):
        del policy_type, obs, noise_scale

        if society is None:
            return np.array([0.0, 0.0], dtype=np.float32)

        if not rule_params or not bool(rule_params.get("enabled", False)):
            return PlannerRules._legacy_get_action(
                society=society,
                max_extension_ratio=max_extension_ratio,
                max_subsidy_ratio=max_subsidy_ratio,
            )

        return PlannerRules._global_rule_get_action(
            society=society,
            default_max_extension_ratio=max_extension_ratio,
            default_max_subsidy_ratio=max_subsidy_ratio,
            rule_params=rule_params,
        )

    @staticmethod
    def _legacy_get_action(
        *,
        society,
        max_extension_ratio,
        max_subsidy_ratio,
    ):
        cur_ext = float(getattr(society.planner, "extension_ratio", 0.0))
        cur_sub = float(getattr(society, "cash_subsidy_ratio", 0.0))
        step_cnt = int(getattr(society, "step_cnt", 0))
        agree_ratio = float(getattr(society, "agree_ratio", 0.0))
        required_ratio = float(getattr(society, "required_ratio", 1.0))
        dev_profit_rate = float(getattr(society.developer, "profit_rate", 0.0))

        activate_by_profit = dev_profit_rate < 0.0
        activate_by_round = (step_cnt >= 4) and (agree_ratio < required_ratio)
        activate_by_dev_stall = int(getattr(society, "developer_no_change_streak", 0)) >= 2
        planner_active = activate_by_profit or activate_by_round or activate_by_dev_stall

        if not planner_active:
            return np.array(
                [
                    cur_ext,
                    cur_sub,
                ],
                dtype=np.float32,
            )

        return PlannerRules._random_search(
            society=society,
            max_extension_ratio=max_extension_ratio,
            max_subsidy_ratio=max_subsidy_ratio,
            n_samples=100,
            force_policy_start=planner_active,
        )

    @staticmethod
    def _global_rule_get_action(
        *,
        society,
        default_max_extension_ratio,
        default_max_subsidy_ratio,
        rule_params,
    ):
        extension_cap = float(
            rule_params.get("extension_cap", default_max_extension_ratio)
        )
        subsidy_cap = float(
            rule_params.get("subsidy_cap", default_max_subsidy_ratio)
        )
        return PlannerRules._legacy_get_action(
            society=society,
            max_extension_ratio=extension_cap,
            max_subsidy_ratio=subsidy_cap,
        )

    @staticmethod
    def _weighted_agree_ratio(mask, weights):
        total = float(np.sum(weights))
        if total <= 0:
            return 0.0
        return float(np.sum(weights[mask]) / total)

    @staticmethod
    def _estimate_target_subsidy_from_disagreed(*, society, max_subsidy_ratio):
        r = society.residents
        dev = society.developer

        disagree_mask = np.asarray(getattr(r, "agree", np.zeros(r.N)) < 0.5, dtype=bool)
        if not np.any(disagree_mask):
            return float(getattr(society, "cash_subsidy_ratio", 0.0))

        weights = np.asarray(r.voting_weight, dtype=float)
        q_base = np.asarray(
            getattr(r, "quoted_base_price", getattr(r, "expected_base_price", np.zeros(r.N))),
            dtype=float,
        )
        q_ext = np.asarray(
            getattr(r, "quoted_extension_price", getattr(r, "expected_extension_price", np.zeros(r.N))),
            dtype=float,
        )

        offered_base = max(float(dev.base_price), 1e-6)
        offered_ext = max(float(dev.extension_price), 1e-6)



        need_base = np.maximum(0.0, 1.0 - q_base / offered_base)
        need_ext = np.maximum(0.0, 1.0 - q_ext / offered_ext)
        need = 0.5 * (need_base + need_ext)

        dw = weights[disagree_mask]
        dn = need[disagree_mask]
        if dw.size == 0 or float(np.sum(dw)) <= 0:
            target = float(np.mean(dn)) if dn.size > 0 else 0.0
        else:
            target = float(np.sum(dw * dn) / np.sum(dw))

        return float(np.clip(target, 0.0, float(max_subsidy_ratio)))

    @staticmethod
    def _random_search(
        *,
        society,
        max_extension_ratio,
        max_subsidy_ratio,
        n_samples=100,
        force_policy_start=False,
    ):
        r = society.residents
        dev = society.developer

        expected_base = np.asarray(getattr(r, "expected_base_price", np.zeros(r.N)), dtype=float)
        expected_ext = np.asarray(getattr(r, "expected_extension_price", np.zeros(r.N)), dtype=float)
        expected_area = np.asarray(
            getattr(r, "expected_extension_area", getattr(r, "ext_area", np.zeros(r.N))),
            dtype=float,
        )
        weights = np.asarray(r.voting_weight, dtype=float)
        orig_area = np.asarray(r.orig_area, dtype=float)

        cur_ext = float(getattr(society.planner, "extension_ratio", 0.0))
        cur_sub = float(getattr(society, "cash_subsidy_ratio", 0.0))
        target_subsidy = PlannerRules._estimate_target_subsidy_from_disagreed(
            society=society,
            max_subsidy_ratio=max_subsidy_ratio,
        )
        dev_profit_rate = float(getattr(society.developer, "profit_rate", 0.0))
        force_relief = dev_profit_rate < 0.0

        max_add_ext = max(float(max_extension_ratio) - cur_ext, 0.0)
        max_add_sub = max(float(max_subsidy_ratio) - cur_sub, 0.0)




        low_factor = 0.01 if force_relief else 0.0
        if force_policy_start:

            ext_low = 0.05 if max_add_ext > 0 else 0.0
            sub_low = 0.05 if max_add_sub > 0 else 0.0
        else:
            ext_low = low_factor
            sub_low = low_factor

        ext_factor = PlannerRules._rng.uniform(ext_low, 0.5, int(n_samples))
        sub_factor = PlannerRules._rng.uniform(sub_low, 0.5, int(n_samples))
        add_ext = max_add_ext * ext_factor
        add_sub = max_add_sub * sub_factor
        sampled_ext = np.clip(cur_ext + add_ext, 0.0, float(max_extension_ratio))
        sampled_sub = np.clip(cur_sub + add_sub, 0.0, float(max_subsidy_ratio))


        if not force_relief and not force_policy_start:
            sampled_ext = np.concatenate([sampled_ext, np.array([cur_ext])])
            sampled_sub = np.concatenate([sampled_sub, np.array([cur_sub])])

        best = None
        for ext_ratio, subsidy_ratio in zip(sampled_ext, sampled_sub):
            if force_relief:

                if max_add_ext > 0 and ext_ratio <= cur_ext:
                    continue
                if max_add_sub > 0 and subsidy_ratio <= cur_sub:
                    continue
            if force_policy_start:
                if max_add_ext > 0 and ext_ratio <= cur_ext:
                    continue
                if max_add_sub > 0 and subsidy_ratio <= cur_sub:
                    continue

            eff_base = float(dev.base_price) * (1.0 - float(subsidy_ratio))
            eff_ext = float(dev.extension_price) * (1.0 - float(subsidy_ratio))
            available_ext_area = orig_area * float(ext_ratio)

            agree_mask = (
                (eff_base <= expected_base)
                & (eff_ext <= expected_ext)
                & (available_ext_area >= expected_area)
            )
            agree_ratio_pred = PlannerRules._weighted_agree_ratio(agree_mask, weights)

            score = (
                agree_ratio_pred,
                -abs(float(subsidy_ratio) - target_subsidy),
                -float(subsidy_ratio),
                -float(ext_ratio),
            )
            if best is None or score > best["score"]:
                best = {
                    "score": score,
                    "extension_ratio": float(ext_ratio),
                    "cash_subsidy_ratio": float(subsidy_ratio),
                }

        if best is None:
            fallback_ext = cur_ext + (max_add_ext * 0.01 if max_add_ext > 0 else 0.0)
            fallback_sub = cur_sub + (max_add_sub * 0.01 if max_add_sub > 0 else 0.0)
            return np.array(
                [
                    float(np.clip(fallback_ext, 0.0, float(max_extension_ratio))),
                    float(np.clip(fallback_sub, 0.0, float(max_subsidy_ratio))),
                ],
                dtype=np.float32,
            )

        return np.array([best["extension_ratio"], best["cash_subsidy_ratio"]], dtype=np.float32)
