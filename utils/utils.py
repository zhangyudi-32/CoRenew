



import json
import pandas as pd
import os
import time
from collections import defaultdict,Counter
import re
from transformers import AutoTokenizer, pipeline, AutoModelForCausalLM, AutoConfig
import openai
import numpy as np
import random
from utils.save_utils import extract_answer
import json
from pathlib import Path
from datetime import datetime

COMMUNITY_COLUMN_ALIASES = {
    "community": "小区",
    "building_type": "建筑类型",
    "tenure_category": "权属类别",
    "building_quality": "建筑质量",
    "build_year": "建成年代",
    "comment_count": "留言数量",
    "greening_rate": "绿化率",
    "residual_far": "剩余容积率",
    "potential_score": "潜力得分",
    "house_price_rmb_sqm": "房价（元/平）",
    "far": "容积率",
    "household_count": "户数",
    "parking": "停车位",
}

DEFAULT_PUBLIC_SERVICE_PROJECTS = [
    {
        "id": "community_center",
        "name": "Community Center",
        "min_area": 180,
        "unit_cost": 2600,
    }
]


def normalize_community_df_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    rename_map = {
        src: dst for src, dst in COMMUNITY_COLUMN_ALIASES.items()
        if src in df.columns and dst not in df.columns
    }
    if rename_map:
        df = df.rename(columns=rename_map)
    return df

def read_jsonl_file(file_path: str):
    data = []
    obj = ""
    c = 0
    with open(file_path, 'r') as file:
        for line in file:
            c += 1
            try:
                json_object = json.loads(obj)
                data.append(json_object)
                obj = line
            except json.JSONDecodeError as e:
                obj += line
    return data

def get_history(logger):
    string = ""
    logs = read_jsonl_file(logger.handlers[0].baseFilename)
    for l in logs:
        string += f'name={l["name"]}\nmsg={l["msg"]}\n'
        if "text" in l:
            string += "Text: " + l['text']
        elif "prompt" in l:
            string += "Prompt: " + l["prompt"]
        elif "_backward_through_llm" in l:
            string +=  "Backward: " + l["_backward_through_llm"]
        elif "optimizer.response" in l:
            string += "optimizer.response: " + l["optimizer.response"]

        string += "\n********************\n"
    return logs, string

def setup_hf_model(model_name, cache_dir=None, max_new_tokens=7000):
    cache_root = cache_dir or os.environ.get("HF_HOME") or str(Path.home() / ".cache" / "huggingface")
    model_cache_dir = os.path.join(cache_root, model_name)
    config = AutoConfig.from_pretrained(model_name, use_cache=True, cache_dir=model_cache_dir, device_map='auto')
    model = AutoModelForCausalLM.from_pretrained(model_name, config=config, cache_dir=model_cache_dir, device_map='auto')
    model.eval()
    tokenizer = AutoTokenizer.from_pretrained(model_name, use_cache=True)
    tokenizer.pad_token = tokenizer.eos_token
    pipeline_gen = pipeline("text-generation", model=model, tokenizer=tokenizer, max_new_tokens=max_new_tokens,
                                 return_full_text=False)
    return model, tokenizer, pipeline_gen


def load_setup(game_dir, agents_num):
    with open(os.path.join(game_dir,'config.txt'), 'r') as f:
        agents_config_file = f.readlines()


    agents = {}
    role_to_agents = {}
    assert len(agents_config_file) == agents_num

    for line in agents_config_file:
        agent_game_name, file_name, role, incentive, model = line.split(',')
        model = model.strip()
        agents[agent_game_name]={'file_name': file_name, 'role':role, 'incentive': incentive, 'model': model}
        if not role in role_to_agents: role_to_agents[role] = []
        role_to_agents[role].append(agent_game_name)


    with open(os.path.join(game_dir,'initial_deal.txt'), 'r') as file:
        initial_deal = file.readline().strip()

    for role in role_to_agents:
        if len(role_to_agents[role]) == 1:
            role_to_agents[role] = role_to_agents[role][0]

    return agents,initial_deal,role_to_agents


def set_constants(args):
    api_key = getattr(args, "api_key", "") or os.environ.get("LLM_API_KEY", "")
    base_url = getattr(args, "llm_base_url", "") or getattr(args, "base_url", "")

    openai.api_key = api_key

    hf_home = getattr(args, "hf_home", "")
    if hf_home:
        os.environ["TRANSFORMERS_CACHE"] = hf_home
        os.environ["HF_HOME"] = hf_home
    if api_key:
        os.environ["LLM_API_KEY"] = api_key
        os.environ["OPENAI_API_KEY"] = api_key
    if base_url:
        os.environ["LLM_BASE_URL"] = base_url
        os.environ["OPENAI_BASE_URL"] = base_url

def randomize_agents_order(agents, p1, rounds):
    round_assign = []
    names = [name for name in agents.keys()]
    last_agent = p1
    for i in range(0,int(np.ceil(rounds/len(agents)))):
        shuffled = random.sample(names, len(names))
        while shuffled[0] == last_agent or shuffled[-1]==p1: shuffled = random.sample(names, len(names))
        round_assign += shuffled
        last_agent = shuffled[-1]
    return round_assign

def summarize_votes(
    history_content,
    round_idx=None,
    agents_num=None
):

    agree = 0
    total = 0

    rounds = history_content.get("rounds", [])

    if round_idx is not None and agents_num is not None:
        records = rounds[-agents_num:]
    else:
        records = rounds

    for record in records:
        role = record.get("role", "")
        if role != "player":
            continue

        raw = record.get("public_answer", "")
        if not raw:
            continue

        decision = extract_answer(raw)
        if not isinstance(decision, dict):
            continue

        try:
            agree_flag = int(decision.get("agree", -1))
        except Exception:
            continue

        if agree_flag not in (0, 1):
            continue

        total += 1
        if agree_flag == 1:
            agree += 1

    if total == 0:
        return {
            "agree": 0,
            "total": 0,
            "agree_ratio": 0.0
        }

    return {
        "agree": agree,
        "total": total,
        "agree_ratio": agree / total
    }


def export_vote_matrix(history_content, role_to_agent_names, output_dir, filename_prefix="vote_matrix"):
    rounds = history_content.get("rounds", [])


    round_records = []
    skip_no_answer = 0
    skip_no_tag = 0
    skip_p1_p2 = 0

    for idx, r in enumerate(rounds):



        agent = r.get("agent")
        if agent is None:
            print(f"[WARN] round {idx} missing 'agent'")
            continue

        if agent in [role_to_agent_names.get('p1', ''), role_to_agent_names.get('p2', '')]:
            skip_p1_p2 += 1
            continue

        public_answer = r.get("public_answer")
        if public_answer is None:
            skip_no_answer += 1
            continue

        answer = public_answer.strip()
        if answer.startswith("[Agree]"):
            val = 1
        elif answer.startswith("[Disagree]"):
            val = 0
        else:
            skip_no_tag += 1
            continue

        round_records.append({
            "round_index": idx,
            "agent": agent,
            "vote": val
        })


    print(f"  valid votes: {len(round_records)}")
    print(f"  skipped p1/p2: {skip_p1_p2}")
    print(f"  skipped missing public_answer: {skip_no_answer}")
    print(f"  skipped unrecognized answer tag: {skip_no_tag}")

    if not round_records:
        print("[ERROR] No valid voting records extracted. Vote matrix not generated.")
        return

    vote_df = pd.DataFrame(round_records)

    print(vote_df.head())

    vote_df["round_num"] = vote_df.groupby("agent").cumcount() + 1

    vote_matrix = vote_df.pivot(index="agent", columns="round_num", values="vote").fillna("")

    agree_rate = (vote_matrix == 1).sum() / (vote_matrix != "").sum()
    agree_rate_row = pd.DataFrame([agree_rate], index=["Agreement Rate"])
    vote_matrix = pd.concat([vote_matrix, agree_rate_row])

    time_str = time.strftime("%H_%M_%S", time.localtime())
    filename = f"{filename_prefix}_{time_str}.csv"
    csv_path = os.path.join(output_dir, filename)

    vote_matrix.to_csv(csv_path, encoding="utf-8-sig")
    print(f"[OK] Vote matrix saved to: {csv_path}")

class ConsensusTracker:
    def __init__(self, output_path="consensus_log.json", excluded_agents=None):
        self.output_path = output_path
        self.excluded_agents = excluded_agents or []
        self.round_data = []
        self.agent_opinions = defaultdict(list)
        os.makedirs(os.path.dirname(self.output_path), exist_ok=True)
        if os.path.exists(self.output_path):
            os.remove(self.output_path)

    def record_opinion(self, round_idx, agent_name, opinion):
        if agent_name in self.excluded_agents:
            return

        self.round_data.append({
            "round": round_idx,
            "agent": agent_name,
            "opinion": opinion
        })

        self.agent_opinions[agent_name].append((round_idx, opinion))

        with open(self.output_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(self.round_data[-1], ensure_ascii=False) + "\n")

    def get_current_opinions(self, exclude_agent=None):
        latest = {}
        for agent, records in self.agent_opinions.items():
            if records:
                if agent != exclude_agent:
                    latest[agent] = records[-1][1]
        return latest

    def get_agent_history(self, agent_name):
        return self.agent_opinions.get(agent_name, [])

    def get_full_round_data(self):
        return self.round_data
    def get_opinion_summary(self, round_idx):
        if round_idx <= 0:
            return "(No previous-round opinion summary yet)"

        opinions = [
            record["opinion"]
            for record in self.round_data
            if record["round"] == round_idx - 1
        ]
        if not opinions:
            return "(No previous-round opinions recorded)"

        counts = Counter(opinions)
        total = sum(counts.values())

        lines = []
        for opinion, count in counts.items():
            pct = 100 * count / total
            lines.append(f"{opinion}: {count} residents ({pct:.1f}%)")

        return "\n".join(lines)

def extract_opinion_from_response(agent_response):
    pattern = r"<ANSWER>\s*\[([^\[\]]+?)\]"
    match = re.search(pattern, agent_response)

    if match:
        return match.group(1).strip()
    else:
        return "No explicit stance"

def build_community_facility_summary(comm_row):
    def describe_level(count, name):
        if count == 0:
            return f"Almost no {name} nearby"
        elif count <= 2:
            return f"Limited {name} nearby"
        elif count <= 5:
            return f"Adequate {name} nearby"
        else:
            return f"Abundant {name} nearby"

    education = describe_level(comm_row.get("school", 0), "education facilities")

    clinic = comm_row.get("clinic", 0)
    hospital = comm_row.get("general_hospital", 0)
    if hospital > 0:
        medical = "A general hospital is nearby, so medical access is strong"
    else:
        medical = describe_level(clinic, "medical facilities")

    commercial = describe_level(
        comm_row.get("restaurant", 0)
        + comm_row.get("shopping", 0)
        + comm_row.get("leisure", 0)
        + comm_row.get("sports_facility", 0),
        "commercial and daily-life amenities"
    )

    metro = comm_row.get("metro_station", 0)
    park = comm_row.get("park_square", 0)
    if metro > 0 and park > 0:
        transport = "Near a metro station and public open space, with strong commuting and leisure access"
    elif metro > 0:
        transport = "Near a metro station, with good public transport access"
    elif park > 0:
        transport = "Some public open space is nearby, but transit access is average"
    else:
        transport = "Transit access and public open space are both fairly limited"

    return {
        "education": education,
        "medical": medical,
        "commercial": commercial,
        "transport": transport,
    }

def get_required_agree_ratio(build_year, cfg):
    rule_cfg = cfg.get("agreement_rule", {})
    mode = rule_cfg.get("mode", "by_build_year")

    if mode == "fixed":
        return float(rule_cfg.get("fixed_ratio", 1.0))

    if mode == "by_build_year":
        by_age_cfg = rule_cfg.get("by_build_year", {})
        current_year = by_age_cfg.get("current_year")
        if current_year is None:
            current_year = datetime.now().year

        age = current_year - int(build_year)

        for rule in by_age_cfg.get("rules", []):
            max_age = rule.get("max_age")
            if max_age is None or age < max_age:
                return float(rule["ratio"])

    return 0.9

def get_community_stats(comm_df, extension_ratio, cfg):

    comm_df = comm_df.copy()
    comm_df['小区'] = comm_df['小区'].astype(str).str.strip()

    current_year = 2026
    stats = {}

    for _, row in comm_df.iterrows():
        name = row['小区']

        lot_area = float(row['area'])
        far = float(row['容积率'])
        build_year = int(row['建成年代'])
        parking_slots_per_capita = row['parking_slots_per_capita']
        total_existing_area = lot_area * far

        max_expandable_area = total_existing_area * extension_ratio

        required_agree_ratio = get_required_agree_ratio(
            build_year=build_year,
            cfg=cfg
        )

        stats[name] = {
            "max_expandable_area": max_expandable_area,
            "extension_ratio":extension_ratio,
            "total_existing_area": total_existing_area,
            "current_price": float(row['房价（元/平）']),
            "build_year": build_year,
            "parking_slots_per_capita":parking_slots_per_capita,
            "building_age": current_year - build_year,
            "required_agree_ratio": required_agree_ratio,
            "parking_price": float(row["parking_price"]),
            "extension_price": float(row['nearby_max_price'])
        }

    return stats

def build_community_context(
    community_name: str,
    comm_info: dict,
    comm_row: pd.Series,
) -> str:

    build_year = comm_info.get("建成年代") or comm_info.get("build_year", "unknown")
    parking_slots_per_capita = comm_info.get("parking_slots_per_capita", "unknown")
    current_price = comm_info.get("current_price")
    building_quality = None
    if "建筑质量" in comm_row:
        try:
            building_quality = float(comm_row["建筑质量"])
        except Exception:
            building_quality = None

    if current_price is None and "房价（元/平）" in comm_row:
        try:
            current_price = float(comm_row["房价（元/平）"])
        except Exception:
            current_price = None

    facility_summary = build_community_facility_summary(comm_row)

    if current_price is not None:
        price_block = (
            f"- Current community housing price: {float(current_price):.0f} RMB/sqm\n"
            f"- If you choose not to renew this round, a reference market price is {float(current_price):.0f} RMB/sqm"
        )
    else:
        price_block = "- Current community housing price: unavailable"

    if building_quality is None:
        quality_block = "- Housing quality information: unavailable"
    elif building_quality >= 0.5:
        quality_block = (
            "- Housing quality: your current dwelling has been classified as unsafe and faces serious safety risks. "
            "Self-renewal could replace it with a newly built unit on the original site, but you would bear the renewal cost."
        )
    elif building_quality >= 0.15:
        quality_block = (
            "- Housing quality: your current dwelling is relatively old and has noticeable safety concerns. "
            "Self-renewal could improve it into a newly built unit on the original site, but you would bear the associated renewal cost."
        )
    else:
        quality_block = (
            "- Housing quality: your current dwelling is aging and requires attention to safety and maintenance. "
            "Self-renewal may improve living conditions, but you would bear the renewal cost."
        )

    context = f"""
[Community Overview]
- Community name: {community_name}
- Build year: {build_year}
- Current parking slots per capita: {parking_slots_per_capita}
{price_block}
{quality_block}
""".strip()

    return context

def load_public_service_projects(path: str | None = None):
    if path is None or str(path).strip() == "":
        return [dict(project) for project in DEFAULT_PUBLIC_SERVICE_PROJECTS]

    path = Path(path)
    if not path.exists():
        return [dict(project) for project in DEFAULT_PUBLIC_SERVICE_PROJECTS]

    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    projects = cfg.get("community_services", [])
    return projects or [dict(project) for project in DEFAULT_PUBLIC_SERVICE_PROJECTS]
def render_public_service_prompt(projects):
    lines = ["[Optional Public Service Facilities Funded by the Developer]"]

    for p in projects:
        line = (
            f"- {p['name']}: "
            f"minimum area {p['min_area']} sqm, "
            f"construction cost {p['unit_cost']} RMB/sqm"
        )
        lines.append(line)

    lines.append(
        "- Once built, each facility must satisfy its minimum area requirement.\n"
    )

    return "\n".join(lines)
