import os
import json
import numpy as np
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from environment.set_observation import UrbanObservations


class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


class Runner:
    def __init__(self, env, agents_policy, args):
        self.env = env
        self.args = args
        self.agents_policy = agents_policy
        self.output_dir = args.output_dir
        self.outcome = "fail"
        self.termination_reason = None
        self.checkpoint_path = os.path.join(self.output_dir, "round_checkpoint.json")
        self.history = {
            "rounds": []
        }

    def _resident_concurrency(self, resident_count):
        if not bool(getattr(self.args, "llm_parallel_residents", True)):
            return 1

        raw_workers = getattr(self.args, "resident_llm_concurrency", None)
        if raw_workers is None:
            raw_workers = getattr(self.args, "llm_concurrency", None)

        try:
            workers = int(raw_workers) if raw_workers is not None else min(8, resident_count)
        except (TypeError, ValueError):
            workers = min(8, resident_count)

        return max(1, min(workers, resident_count))


    def run(self):
        obs = self.env.reset()
        planner_policy = self.agents_policy.get("planner", None)
        if planner_policy is not None and hasattr(planner_policy, "reset"):
            planner_policy.reset()
        start_round = 0
        resumed = self._load_checkpoint()
        if resumed:
            obs = UrbanObservations(self.env).get_obs()
            start_round = int(self.env.step_cnt)
            print(
                f"[RESUME] Restored from checkpoint: {start_round} rounds completed, "
                f"current agreement rate {self.env.agree_ratio:.2%}"
            )
        print(f"[{datetime.now()}] >>> Urban renewal negotiation simulation started")
        community_name = (
            self.env.community_info.get("name")
            or self.env.community_info.get("community")
            or "Unnamed"
        )
        print(f"[SCENE] Target community: {community_name}")
        print(f"[INFO] Target agreement rate: {self.env.required_ratio:.2%}")
        print("-" * 50)

        max_rounds = getattr(self.args, "rounds_num", 5)

        if self.env.is_terminal():
            if self.env.agree_ratio >= self.env.required_ratio:
                self.outcome = "success"
                self.termination_reason = "agreement_reached"
            else:
                self.outcome = "fail"
                self.termination_reason = "terminated_without_agreement"
            self.save_logs()
            return
        for r in range(start_round, max_rounds):
            print(f"Starting negotiation round {r+1} / {max_rounds}...")

            actions = self._collect_actions(obs)
            self._record_round_history(r, actions)
            obs, rewards, done = self.env.step(actions)

            self._print_round_summary(r)
            self._save_checkpoint()

            if done:
                if self.env.agree_ratio >= self.env.required_ratio:
                    self.outcome = "success"
                    self.termination_reason = "agreement_reached"
                    print(f"\n[SUCCESS] Consensus reached in round {r+1}.")
                else:
                    self.outcome = "fail"
                    self.termination_reason = "terminated_without_agreement"
                    print(f"\n[FAIL] Negotiation ended in round {r+1} without reaching the required agreement rate.")
                break


        self.save_logs()


    def _collect_actions(self, obs):
        actions = {}

        planner_policy = self.agents_policy["planner"]
        planner_action = planner_policy.get_action(obs["planner"])
        actions["planner"] = planner_action


        planner_action_clipped = self.env.check_agent_action(
            self.env.planner, planner_action, "planner"
        )
        self.env.last_planner_extension_ratio = float(planner_action_clipped[0])
        self.env.last_planner_subsidy_ratio = float(planner_action_clipped[1])
        self.env.planner.get_action(planner_action_clipped)
        self.env.planner.step(self.env)

        desired_subsidy = self.env.last_planner_subsidy_ratio
        if self.env.cash_subsidy_cap > 0.0:
            self.env.cash_subsidy_ratio = float(
                min(max(desired_subsidy, 0.0), self.env.cash_subsidy_cap, 0.1)
            )
        else:
            self.env.cash_subsidy_ratio = 0.0
        self.env.is_subsidy_round = bool(self.env.cash_subsidy_ratio > 0.0)

        refreshed_obs = UrbanObservations(self.env).get_obs()

        developer_policy = self.agents_policy["developer"]
        actions["developer"] = developer_policy.get_action(refreshed_obs["developer"])

        resident_policies = self.agents_policy["residents"]
        resident_items = list(resident_policies.items())
        worker_count = self._resident_concurrency(len(resident_items))
        resident_actions = [None] * len(resident_items)

        if worker_count == 1:
            for i, (_, sub_policy) in enumerate(resident_items):
                resident_actions[i] = sub_policy.get_action(refreshed_obs["residents"][i])
        else:
            print(
                f"[RESIDENTS] Collecting {len(resident_items)} actions "
                f"with {worker_count} parallel workers",
                flush=True,
            )
            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                future_to_index = {
                    executor.submit(sub_policy.get_action, refreshed_obs["residents"][i]): i
                    for i, (_, sub_policy) in enumerate(resident_items)
                }
                completed = 0
                for future in as_completed(future_to_index):
                    i = future_to_index[future]
                    agent_id = resident_items[i][0]
                    resident_actions[i] = future.result()
                    completed += 1
                    print(
                        f"[RESIDENTS] Completed {completed}/{len(resident_items)} "
                        f"agent_id={agent_id}",
                        flush=True,
                    )

        actions["residents"] = np.vstack(resident_actions)

        return actions

    def _record_round_history(self, round_idx, actions):
            round_record = {
                "round": int(round_idx + 1),

                "planner": {
                    "extension_ratio": float(actions["planner"][0]),
                    "cash_subsidy_ratio": float(actions["planner"][1]),
                },

                "developer": {
                    "base_price": float(actions["developer"][0]),
                    "extension_price": float(actions["developer"][1]),
                    "parking_fee": float(actions["developer"][2]),
                    "build_public_service": bool(getattr(self.env.developer, "build_public_service", False)),
                },

                "residents": []
            }

            resident_actions = actions["residents"]
            resident_policies = self.agents_policy["residents"]

            for i, (agent_id, _) in enumerate(resident_policies.items()):
                a = resident_actions[i]

                resident_record = {
                    "agent_id": agent_id,
                    "agree": bool(a[0] >= 0.5),
                    "chosen_extension_area": float(a[1]),
                    "want_parking": bool(a[2] >= 0.5),
                    "expected_base_price": float(a[3]),
                    "expected_extension_price": float(a[4]),
                    "quoted_base_price": float(a[5]) if len(a) > 5 else float(a[3]),
                    "quoted_extension_price": float(a[6]) if len(a) > 6 else float(a[4]),
                    "expected_extension_area": float(a[7]) if len(a) > 7 else float(a[1]),
                }

                round_record["residents"].append(resident_record)

            self.history["rounds"].append(round_record)


    def _print_round_summary(self, round_idx):
        print("  > Round summary:")
        print(f"    - Current base-area price: {self.env.developer.base_price:.2f}")
        print(f"    - Current extension-area price: {self.env.developer.extension_price:.2f}")
        print(f"    - Current agreement rate: {self.env.agree_ratio:.2%}")
        print(f"    - Developer profit: {self.env.developer.profit:.2f}")
        print(f"    - Developer cost: {self.env.developer.cost:.2f}")
        print(f"    - Developer profit rate: {self.env.developer.profit_rate:.2%}")

    def save_logs(self):
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = os.path.join(
            self.output_dir, f"negotiation_log_{timestamp}.json"
        )

        dev = self.env.developer

        build_public_service = bool(getattr(dev, "build_public_service", False))

        public_service_area = 0.0
        public_service_cost = 0.0
        if build_public_service and hasattr(dev, "public_service"):
            public_service_area = float(dev.public_service.get("min_area", 0.0))
            public_service_cost = float(
                dev.public_service.get("min_area", 0.0)
                * dev.public_service.get("unit_cost", 0.0)
            )

        final_log = {
            "community_info": self.env.community_info,
            "outcome": self.outcome,
            "termination_reason": self.termination_reason,
            "final_metrics": {
                "final_agree_ratio": float(self.env.agree_ratio),
                "final_profit": float(dev.profit),
                "final_profit_rate": float(dev.profit_rate),
            },
            "final_policy": {
                "planner": {
                    "extension_ratio": float(self.env.planner.extension_ratio),
                    "cash_subsidy_ratio": float(self.env.cash_subsidy_ratio),
                },
                "developer": {
                    "base_price": float(dev.base_price),
                    "extension_price": float(dev.extension_price),
                    "parking_fee": float(dev.parking_fee),
                    "build_public_service": build_public_service,
                    "derived": {
                        "public_service_area": public_service_area,
                        "public_service_cost": public_service_cost,
                    }
                }
            },
            "rounds": int(self.env.step_cnt),
            "negotiation_history": self.history["rounds"],
        }

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(final_log, f, cls=NumpyEncoder, ensure_ascii=False, indent=4)

        print("-" * 50)
        print(f"Negotiation finished. Log saved to: {file_path}")

    def _save_checkpoint(self):
        os.makedirs(self.output_dir, exist_ok=True)
        payload = {
            "outcome": self.outcome,
            "termination_reason": self.termination_reason,
            "history": self.history,
            "env_state": self.env.get_checkpoint_state(),
        }
        with open(self.checkpoint_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, cls=NumpyEncoder, ensure_ascii=False, indent=2)

    def _load_checkpoint(self):
        resume_enabled = getattr(self.args, "resume_from_checkpoint", True)
        if isinstance(resume_enabled, str):
            resume_enabled = resume_enabled.strip().lower() in {"1", "true", "yes", "y", "on"}
        if not resume_enabled:
            return False
        if not os.path.exists(self.checkpoint_path):
            return False
        try:
            with open(self.checkpoint_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception:
            return False

        env_state = payload.get("env_state")
        if not isinstance(env_state, dict):
            return False

        self.outcome = payload.get("outcome", self.outcome)
        self.termination_reason = payload.get("termination_reason", self.termination_reason)
        history = payload.get("history", {})
        if isinstance(history, dict) and isinstance(history.get("rounds"), list):
            self.history = history
        else:
            self.history = {"rounds": []}
        self.env.load_checkpoint_state(env_state)
        return True

    def _clear_checkpoint(self):
        if os.path.exists(self.checkpoint_path):
            try:
                os.remove(self.checkpoint_path)
            except OSError:
                pass

    def clear_checkpoint(self):
        self._clear_checkpoint()
