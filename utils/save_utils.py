import json
import os
import time
import re

def extract_proposal(text):
    if not text:
        return None

    m = re.search(r"<PROPOSAL>\s*(.*?)\s*</PROPOSAL>", text, re.S)
    if not m:
        return None

    raw = m.group(1)
    return [x.strip() for x in raw.split(",") if x.strip()]
def extract_answer(answer):
    if not answer:
        return None
    if hasattr(answer, "content"):
        answer = answer.content

    answer = str(answer).strip()
    answer = re.sub(r"^```json", "", answer, flags=re.IGNORECASE).strip()
    answer = re.sub(r"^```", "", answer).strip()
    answer = re.sub(r"```$", "", answer).strip()
    try:
        return json.loads(answer)
    except Exception:
        pass
    match = re.search(r"\{[\s\S]*\}", answer)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            return None
    return None
def extract_price(answer):
    if not isinstance(answer, str):
        return None
    if "<PRICE>" in answer and "</PRICE>" in answer:
        raw = answer.split("<PRICE>")[1].split("</PRICE>")[0].strip()
        try:
            return int(raw)
        except ValueError:
            return None
    return None

def extract_plan_with_fallback(answer):
    if not isinstance(answer, str):
        return "", "none"

    if "<PLAN>" in answer and "</PLAN>" in answer:
        plan = answer.split("<PLAN>")[1].split("</PLAN>")[0].strip()
        return plan, "explicit"

    fallback_patterns = [
        r"(Next round[^.\n]*)",
        r"(I will[^.\n]*)",
        r"(My plan is[^.\n]*)",
    ]
    for p in fallback_patterns:
        m = re.search(p, answer)
        if m:
            return m.group(1).strip(), "fallback"

    return "", "none"



class PlanTracker:
    def __init__(self):
        self.data = {}

    def ensure_agent(self, agent_name):
        if agent_name not in self.data:
            self.data[agent_name] = {}

    def record(self, agent_name, round_idx, plan, source, role):
        self.ensure_agent(agent_name)
        self.data[agent_name][str(round_idx)] = {
            "plan": plan,
            "source": source,
            "role": role
        }

    def to_dict(self):
        return self.data

def extract_plan_with_fallback(answer):
    if not isinstance(answer, str):
        return "", "none"

    if "<PLAN>" in answer and "</PLAN>" in answer:
        plan = answer.split("<PLAN>")[1].split("</PLAN>")[0].strip()
        return plan, "explicit"

    fallback_patterns = [
        r"(Next round.*)",
        r"(I will.*)",
        r"(My plan is.*)",
    ]
    for p in fallback_patterns:
        m = re.search(p, answer)
        if m:
            return m.group(1).strip(), "fallback"

    return "", "none"


def write_json(obj, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def save_conversation(
    history,
    agent_name,
    full_answer,
    prompt,
    round_idx,
    role,
    round_assign=None,
    initial=False
):

    if hasattr(full_answer, "content"):
        full_answer = full_answer.content

    if initial:
        history["content"] = {
            "slot_assignment": round_assign or [],
            "rounds": [],
            "finished_rounds": 0
        }

        base, _ = os.path.splitext(history["file"])
        history["plan_file"] = base + ".plan_tracker.json"
        history["price_file"] = base + ".price_tracker.json"
        history["proposal_file"] = base + ".proposal_tracker.json"

        write_json({}, history["plan_file"])
        write_json({}, history["price_file"])
        write_json({}, history["proposal_file"])

    else:
        history["content"]["finished_rounds"] += 1

    public_answer = extract_answer(full_answer)
    price = extract_price(full_answer)
    plan, plan_source = extract_plan_with_fallback(full_answer)
    proposal = extract_proposal(full_answer)
    history["content"]["rounds"].append({
        "round": round_idx,
        "agent": agent_name,
        "role": role,
        "prompt": prompt,
        "full_answer": full_answer,
        "public_answer": public_answer
    })

    write_json(history["content"], history["file"])

    return history

def create_outfiles(args, OUTPUT_DIR):
    if not os.path.isdir(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    history = {}

    if args.restart:
        history["file"] = os.path.join(OUTPUT_DIR, args.output_file)
        with open(history["file"], "r", encoding="utf-8") as f:
            history["content"] = json.load(f)

        round_start = int(history["content"].get("finished_rounds", 0))
        round_assign = history["content"].get("slot_assignment", [])

        base, _ = os.path.splitext(history["file"])
        history["plan_file"] = base + ".plan_tracker.json"
        history["price_file"] = base + ".price_tracker.json"
        history["proposal_file"] = base + ".proposal_tracker.json"

    else:
        time_str = time.strftime("%H_%M_%S", time.localtime())
        output_file = os.path.join(
            OUTPUT_DIR,
            args.output_file.replace(".json", f"_{time_str}.json")
        )

        history = {"file": output_file}
        round_start = 0
        round_assign = []

    return round_assign, round_start, history
