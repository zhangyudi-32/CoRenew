import os
import argparse
import pandas as pd
import numpy as np
import copy
import yaml
from datetime import datetime

from agents.llm.llm_agent import llm_agent as UrbanLLMAgent
from environment.urban_renew_env import UrbanRenewEnv
from runner import Runner
from utils.utils import (
    build_community_facility_summary,
    get_community_stats,
    build_community_context,
    normalize_community_df_columns,
)
from agents.rule_based.rules_core import rule_agent


class Config:
    def __init__(self, entries):
        self.__dict__.update(entries)
        if not hasattr(self, "llm_name"):
            self.llm_name = getattr(self, "model", "gpt-4o-mini")
        if not hasattr(self, "llm_base_url"):
            self.llm_base_url = getattr(self, "base_url", "")
        if not hasattr(self, "temperature"):
            self.temperature = getattr(self, "temp", 0.2)

    def get(self, key, default=None):
        return getattr(self, key, default)


def load_config(config_path):
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return Config(data)


agent_algorithms = {
    "llm": UrbanLLMAgent,
    "rule_based": rule_agent,
}


def select_agent(
    alg,
    cfg,
    agent_name,
    agent_type=None,
    agent_id=None,
    row_data=None,
    csv_path=None,
    community_context=None,
    community_name=None,
    env=None,
):
    if alg not in agent_algorithms:
        raise ValueError(f"Unsupported algorithm: {alg}")

    if alg == "rule_based":
        return agent_algorithms[alg](
            envs=env,
            args=cfg,
            agent_name=agent_name,
        )

    return agent_algorithms[alg](
        cfg,
        agent_name,
        agent_id,
        row_data=row_data,
        csv_path=csv_path,
        community_context=community_context,
        community_name=community_name,
    )


def main():
    def _parse_bool_like(v, default=False):
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return bool(v)
        if isinstance(v, str):
            t = v.strip().lower()
            if t in {"true", "1", "yes", "y", "on"}:
                return True
            if t in {"false", "0", "no", "n", "off"}:
                return False
        return default

    parser = argparse.ArgumentParser(description="Urban Renewal Simulation Main")
    parser.add_argument(
        "--config", type=str, default="config.yaml", help="Path to config.yaml"
    )
    parser.add_argument(
        "--target_community",
        type=str,
        default=None,
        help="Target community name (override YAML if provided)",
    )
    parser.add_argument(
        "--run_timestamp",
        type=str,
        default=None,
        help="Fixed run timestamp for resume (same value will reuse the same log folder).",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=None,
        help="Override LLM sampling temperature.",
    )
    parser.add_argument(
        "--prompt_enable_scratchpad",
        type=str,
        default=None,
        help="Override whether prompts require <SCRATCHPAD>.",
    )
    parser.add_argument(
        "--prompt_show_resident_agree_rate",
        type=str,
        default=None,
        help="Override whether resident prompts show community agreement rate.",
    )
    parser.add_argument(
        "--prompt_show_resident_last_agree",
        type=str,
        default=None,
        help="Override whether resident prompts show the resident's own last-round stance.",
    )
    args = parser.parse_args()

    cfg = load_config(args.config)

    if args.target_community is not None:
        cfg.target_community = args.target_community

    if args.temperature is not None:
        cfg.temperature = float(args.temperature)

    prompt_flag_overrides = {
        "prompt_enable_scratchpad": args.prompt_enable_scratchpad,
        "prompt_show_resident_agree_rate": args.prompt_show_resident_agree_rate,
        "prompt_show_resident_last_agree": args.prompt_show_resident_last_agree,
    }
    for key, raw_value in prompt_flag_overrides.items():
        if raw_value is not None:
            setattr(cfg, key, _parse_bool_like(raw_value, default=True))

    os.environ["PYTHONHASHSEED"] = str(cfg.seed)

    if args.run_timestamp is not None and str(args.run_timestamp).strip() != "":
        cfg.run_timestamp = str(args.run_timestamp).strip()
    elif not hasattr(cfg, "run_timestamp"):
        cfg.run_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    community_df = normalize_community_df_columns(pd.read_csv(cfg.community_csv))
    resident_df = pd.read_csv(cfg.resident_csv)
    official_df = pd.read_csv(cfg.official_csv)

    community_info_map = get_community_stats(
        community_df, cfg.extension_ratio, cfg
    )

    for community_name, group_df in resident_df.groupby("community"):
        target = str(cfg.target_community).strip()
        if target.lower() != "none" and str(community_name).strip() != target:
            continue

        print(f"\n[SYSTEM] Residential Area: {community_name}")
        comm_row = (
            community_df.loc[
                community_df["小区"].astype(str).str.strip() == community_name
            ]
            .iloc[0]
        )

        comm_info = copy.deepcopy(community_info_map[community_name])
        comm_info["name"] = community_name

        scenario_config = {
            "base_price": cfg.base_price,
            "extension_ratio": cfg.extension_ratio,
            "max_extension_ratio": cfg.max_extension_ratio,
            "force_build_public_service": _parse_bool_like(
                getattr(cfg, "force_build_public_service", False),
                default=False,
            ),
            "extension_price": float(comm_info["extension_price"]),
            "cash_subsidy_cap": float(getattr(cfg, "cash_subsidy_cap", 0.0)),
            "parking_fee": float(comm_info["parking_price"]) * 30.0,
            "build_year": float(comm_info["build_year"]),
            "parking_slots_per_capita": float(
                comm_info["parking_slots_per_capita"]
            ),
            **build_community_facility_summary(comm_row),
        }

        community_context = build_community_context(
            community_name=community_name,
            comm_info=comm_info,
            comm_row=comm_row,
        )

        soft_policy_text = str(
            getattr(cfg, "planner_soft_policy_text", "") or ""
        ).strip()
        if soft_policy_text:
            community_context = (
                f"{community_context}\n"
                f"{soft_policy_text}\n"
            )

        env = UrbanRenewEnv(
            cfg,
            scenario_config=scenario_config,
            resident_df=group_df,
            community_info=comm_info,
        )

        agents_policy = {}

        for _, row in official_df.iterrows():
            role = row["role"]
            if role not in ["planner", "developer"]:
                continue

            alg = cfg.gov_alg if role == "planner" else cfg.dev_alg

            agent = select_agent(
                alg,
                cfg,
                role,
                agent_id=row["agent_id"],
                row_data=row.to_dict(),
                csv_path=cfg.official_csv,
                community_context=community_context,
                community_name=community_name,
                env=env,
            )

            if hasattr(agent, "reset"):
                agent.reset()

            agents_policy[role] = agent

        resident_policies = {}

        for idx, row in group_df.iterrows():
            rid = row["agent_id"]
            try:
                agent = select_agent(
                    cfg.house_alg,
                    cfg,
                    "resident",
                    agent_id=rid,
                    row_data=row.to_dict(),
                    csv_path=cfg.resident_csv,
                    community_context=community_context,
                    community_name=community_name,
                )

                if hasattr(agent, "reset"):
                    agent.reset()

                resident_policies[rid] = agent
            except Exception as e:
                print(
                    f"[ERROR] FAILED building resident agent_id={rid} "
                    f"idx={idx}: {e}"
                )

        if len(resident_policies) != len(group_df):
            raise RuntimeError(
                f"[FATAL] Resident policy count mismatch in {community_name}: "
                f"{len(resident_policies)} policies vs {len(group_df)} residents"
            )

        agents_policy["residents"] = resident_policies

        comm_cfg = copy.deepcopy(cfg)
        comm_cfg.output_dir = os.path.join(
            cfg.output_dir, f"sim_{community_name}"
        )

        runner = Runner(env=env, agents_policy=agents_policy, args=comm_cfg)
        runner.run()


if __name__ == "__main__":
    main()
