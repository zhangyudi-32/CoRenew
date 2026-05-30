import numpy as np


class DeveloperRules:

    @staticmethod
    def get_action(policy_type, obs, *, dev_entity, society):
        del policy_type, obs
        return DeveloperRules._search_best_policy(dev_entity=dev_entity, society=society)

    @staticmethod
    def _weighted_agree_ratio(mask, weights):
        total = float(np.sum(weights))
        if total <= 0:
            return 0.0
        return float(np.sum(weights[mask]) / total)

    @staticmethod
    def _quantized_grid(values, fallback, lo=0.0, hi=100000.0):
        v = np.asarray(values, dtype=float)
        v = v[np.isfinite(v)]
        if v.size == 0:
            return np.array([fallback], dtype=float)

        q = np.quantile(v, [0.1, 0.25, 0.5, 0.75, 0.9])
        candidates = np.unique(np.concatenate([q, np.array([fallback], dtype=float)]))
        candidates = np.clip(candidates, lo, hi)
        return np.unique(candidates)

    @staticmethod
    def _search_best_policy(*, dev_entity, society):
        r = society.residents

        quoted_base = np.asarray(
            getattr(r, "quoted_base_price", getattr(r, "expected_base_price", np.zeros(r.N))),
            dtype=float,
        )
        quoted_ext = np.asarray(
            getattr(r, "quoted_extension_price", getattr(r, "expected_extension_price", np.zeros(r.N))),
            dtype=float,
        )
        expected_area = np.asarray(
            getattr(r, "expected_extension_area", getattr(r, "ext_area", np.zeros(r.N))),
            dtype=float,
        )
        weights = np.asarray(r.voting_weight, dtype=float)
        available_ext_area = np.asarray(r.orig_area, dtype=float) * float(
            getattr(society.planner, "extension_ratio", society.max_extension_ratio)
        )
        ext_price_floor = 0.6 * float(getattr(dev_entity, "extension_price_anchor", dev_entity.extension_price))

        base_grid = DeveloperRules._quantized_grid(
            quoted_base, fallback=float(dev_entity.base_price), lo=0.0, hi=100000.0
        )

        has_extension_demand = bool(np.any(expected_area > 0))
        if has_extension_demand:
            ext_grid = DeveloperRules._quantized_grid(
                quoted_ext,
                fallback=float(dev_entity.extension_price),
                lo=ext_price_floor,
                hi=100000.0,
            )
        else:
            ext_grid = np.array(
                [max(float(dev_entity.extension_price), ext_price_floor)],
                dtype=float,
            )

        best = None
        for base_price in base_grid:
            for extension_price in ext_grid:
                agree_mask = (
                    (base_price <= quoted_base)
                    & (extension_price <= quoted_ext)
                    & (available_ext_area >= expected_area)
                )
                agree_ratio_pred = DeveloperRules._weighted_agree_ratio(agree_mask, weights)

                profit_rate = dev_entity.evaluate_profit_rate(
                    base_price=float(base_price),
                    extension_price=float(extension_price),
                    parking_fee=float(dev_entity.parking_fee),
                    build_public_service=False,
                    society=society,
                )

                if profit_rate <= 0:
                    continue

                score = (
                    agree_ratio_pred,
                    -float(base_price),
                    -float(extension_price),
                    float(profit_rate),
                )

                if best is None or score > best["score"]:
                    best = {
                        "score": score,
                        "base_price": float(base_price),
                        "extension_price": float(extension_price),
                    }

        if best is None:
            candidate = np.array(
                [
                    float(dev_entity.base_price),
                    max(float(dev_entity.extension_price), ext_price_floor),
                    float(dev_entity.parking_fee),
                    0.0,
                ],
                dtype=np.float32,
            )
        else:
            candidate = np.array(
                [
                    float(best["base_price"]),
                    max(float(best["extension_price"]), ext_price_floor),
                    float(dev_entity.parking_fee),
                    0.0,
                ],
                dtype=np.float32,
            )


        return DeveloperRules._ensure_non_negative_profit(
            action=candidate,
            dev_entity=dev_entity,
            society=society,
            ext_price_floor=ext_price_floor,
        )

    @staticmethod
    def _ensure_non_negative_profit(*, action, dev_entity, society, ext_price_floor):
        base_price = float(action[0])
        extension_price = max(float(action[1]), float(ext_price_floor))
        parking_fee = float(action[2])

        profit_rate = dev_entity.evaluate_profit_rate(
            base_price=base_price,
            extension_price=extension_price,
            parking_fee=parking_fee,
            build_public_service=False,
            society=society,
        )
        if profit_rate >= 0:
            return np.array([base_price, extension_price, parking_fee, 0.0], dtype=np.float32)


        anchor = max(float(getattr(dev_entity, "extension_price_anchor", extension_price)), 1.0)
        for mult in [1.0, 1.1, 1.2, 1.4, 1.6, 2.0]:
            ext_try = max(ext_price_floor, anchor * mult)
            pr = dev_entity.evaluate_profit_rate(
                base_price=base_price,
                extension_price=ext_try,
                parking_fee=parking_fee,
                build_public_service=False,
                society=society,
            )
            if pr >= 0:
                return np.array([base_price, ext_try, parking_fee, 0.0], dtype=np.float32)


        base_anchor = max(float(getattr(dev_entity, "base_price_anchor", base_price)), 1.0)
        for bmult in [1.0, 1.1, 1.2, 1.4]:
            base_try = base_anchor * bmult
            ext_try = max(ext_price_floor, anchor * 1.2)
            pr = dev_entity.evaluate_profit_rate(
                base_price=base_try,
                extension_price=ext_try,
                parking_fee=parking_fee,
                build_public_service=False,
                society=society,
            )
            if pr >= 0:
                return np.array([base_try, ext_try, parking_fee, 0.0], dtype=np.float32)


        return np.array([base_anchor * 1.4, max(ext_price_floor, anchor * 1.2), parking_fee, 0.0], dtype=np.float32)
