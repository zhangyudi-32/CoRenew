import json
import numpy as np
from utils.utils import (
    load_public_service_projects,
)

def _cfg_flag(cfg, name: str, default: bool) -> bool:
    value = getattr(cfg, name, default) if cfg is not None else default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        token = value.strip().lower()
        if token in {"true", "1", "yes", "y", "on"}:
            return True
        if token in {"false", "0", "no", "n", "off"}:
            return False
    return default


def _answer_tag_instructions(enable_scratchpad: bool) -> str:
    if enable_scratchpad:
        return """
    - You must organize your response using exactly these two tags:
    1. <SCRATCHPAD>
    - Use this tag for reasoning, tradeoff analysis, constraint checks, and intermediate judgments.
    - Content inside this tag will not be parsed or counted by the system.
    2. <ANSWER>
    - You must output the full <SCRATCHPAD> before <ANSWER>.
    - **Provide your final decision only inside this tag**
    - Every numeric value inside <ANSWER> must be a floating-point number.
    """.rstrip()

    return """
    - Use only the following tag in your response:
    1. <ANSWER>
    - **Provide your final decision only inside this tag**
    - Every numeric value inside <ANSWER> must be a floating-point number.
    """.rstrip()


def build_planner_prompt(obs, role_desc: str, cfg=None) -> str:
    enable_scratchpad = _cfg_flag(cfg, "prompt_enable_scratchpad", True)
    agree_ratio = float(obs[0])
    required_ratio = float(obs[1])
    step_ratio = float(obs[2])
    base_price = float(obs[3])
    extension_price = float(obs[4])
    parking_fee = float(obs[5])
    max_extension_ratio = float(obs[6])
    extension_ratio = float(obs[7])
    extension_price_anchor = float(obs[8])
    total_ext_area_last = float(obs[9])
    parking_rate_last = float(obs[10])
    is_subsidy_round = int(obs[11])
    cash_subsidy_cap = float(obs[12])
    low_income_ratio = float(obs[13])
    subsidy_low_income_only = int(round(float(obs[14])))
    last_ext_ratio = float(obs[15])
    last_subsidy_ratio = float(obs[16])
    service_demand = float(obs[17])
    effective_cap = min(0.1, max(0.0, cash_subsidy_cap))

    EXT_RATIO_EPS = 1e-4
    can_subsidize = (
        extension_ratio >= max_extension_ratio - EXT_RATIO_EPS
        and effective_cap > 0
    )

    if can_subsidize:
        if subsidy_low_income_only == 1:
            target_text = "The subsidy applies only to low-income residents (targeted subsidy)."
        else:
            target_text = "The subsidy applies to all residents (universal subsidy)."

        subsidy_rule_text = f"""
        [Cash Subsidy Permission]
        - The current extension ratio is close to or at the institutional cap, so zoning expansion room is exhausted.
        - You may therefore use a cash subsidy as an auxiliary policy tool.
        - Institutional rule: {target_text}
        - You may set:
        - cash_subsidy_ratio ∈ [0.0, {effective_cap:.3f}]
        - `cash_subsidy_ratio` means a cash subsidy proportional to each resident's personal cost.
        - Any value outside this range will be clipped automatically by the system.
        """.rstrip()
    else:
        subsidy_rule_text = f"""
        [Cash Subsidy Permission]
        - You may not use a cash subsidy.
        - Set `cash_subsidy_ratio` explicitly to `0.0`.
        - Any non-zero value will be ignored and treated as `0.0`.
        """.rstrip()
    targeting_block = f"""
    [Community Structure]
    - Share of low-income residents: {low_income_ratio:.1%}
    - Subsidy scheme: {"Targeted (low-income only)" if subsidy_low_income_only == 1 else "Universal (all residents)"}
    """.rstrip()

    prompt = f"""
    {role_desc} Your goal is to push the resident agreement rate above the activation threshold for self-renewal by adjusting the FAR policy.
    [Resident Feedback This Round]
    - Agreement rate: {agree_ratio:.2%} (activation threshold: {required_ratio:.2%})
    - Current progress: {step_ratio:.2%}
    - Total resident extension demand: {total_ext_area_last:.1f} sqm
    - Parking selection rate: {parking_rate_last:.2%}
    [Current Policy Parameters]
    - Base-area price: {base_price:.0f} RMB/sqm
    - Extension-area price: {extension_price:.0f} RMB/sqm
    - Current extension ratio: {extension_ratio:.3f}
    {subsidy_rule_text}
    - Your extension ratio last round: {last_ext_ratio:.3f}
    - Your cash subsidy ratio last round: {last_subsidy_ratio:.3f}
    {targeting_block}
    [Decision Variables You Control]
    - `extension_ratio`: allowed extension ratio (0.0 - {max_extension_ratio:.3f})
    - `cash_subsidy_ratio`: cash subsidy ratio (use `0.0` if the policy is disabled or unavailable this round)
    Analyze resident demand and provide your decision.
    {_answer_tag_instructions(enable_scratchpad)}
    - Return strictly in the following format:
    <ANSWER>
    {{
      "extension_ratio": ...,
      "cash_subsidy_ratio": ...
    }}
    </ANSWER>
    """
    return prompt

def build_developer_prompt(obs: dict, role_prompt,cfg) -> str:
    agree_ratio = float(obs[0])
    required_ratio = float(obs[1])
    step_ratio = float(obs[2])
    base_price = float(obs[3])
    extension_price = float(obs[4])
    parking_fee = float(obs[5])
    max_extension_ratio = float(obs[6])
    extension_ratio = float(obs[7])
    extension_price_anchor = float(obs[8])

    parking_anchor = float(obs[9])
    profit_rate = float(obs[10])
    total_ext_area_last = float(obs[11])
    parking_rate_last = float(obs[12])
    profit = float(obs[13])

    forced_public_service = bool(obs[14] >= 0.5)

    prompt = f"""
    {role_prompt} Your goal is to maximize resident agreement while keeping the profit rate (`profit_rate`) **at or above 0% at all times**.
    [Resident Feedback This Round]
    - Agreement rate: {agree_ratio:.2%} (activation threshold: {required_ratio:.2%})
    - Total resident extension demand: {total_ext_area_last:.1f} sqm
    - Parking selection rate: {parking_rate_last:.2%}
    [Exogenous Public Service Constraint]
    - Public service construction is fixed exogenously by the institution: {"build" if forced_public_service else "do not build"}
    - You cannot change this item through your action this round.
    [Current Planning Policy]
    - Maximum allowed extension ratio: {extension_ratio:.2%}
    [Current Prices]
    - Base-area price: {base_price:.0f} RMB/sqm
    - Extension-area price: {extension_price:.0f} RMB/sqm (current market anchor: {extension_price_anchor:.0f} RMB/sqm)
    - Parking fee: {parking_fee:.0f} RMB/slot (community anchor: {parking_anchor:.0f} RMB/slot)
    - Profit rate: {profit_rate:.2%}
    - Profit: {profit:.0f} RMB

    [Cost and Revenue Structure]
    - Each square meter of extension area generates extension revenue.
    - Each parking purchase generates additional revenue.
    - Public service construction is institutionally fixed and is not your decision.
    - Public service area + resident extension area must not exceed the maximum allowed expansion area.

    [Decision Variables You Control]
    - `base_price`: renovation price for existing area
    - `extension_price`: renovation price for extension area
    - `parking_fee`: parking fee
    - `build_public_service`: this field will be ignored by the system and executed according to the exogenous setting

    [Hard Constraints]
    1. After execution, **profit_rate must remain >= 0%**. Any plan with `profit_rate < 0%` is invalid.
    2. You may not justify `profit_rate < 0%` using arguments such as "lose first, profit later", "long-term return", or "social responsibility".
    3. In `<SCRATCHPAD>`, you must first perform a risk check:
      - Lower prices reduce revenue.
      - Under the current exogenous public-service setting, verify whether profit rate remains >= 0%.

    [Safe Default Plan]
    - Keep current prices unchanged.
    - Set `build_public_service` to `false` if needed; the system will ignore it.

    {_answer_tag_instructions(True)}
    - Return strictly in the following format:
    <ANSWER>
    {{
      "base_price": ...,
      "extension_price": ...,
      "parking_fee": ...,
      "build_public_service": true/false
      }}
    </ANSWER>

    [If uncertain, output the following safe default plan exactly]
    <ANSWER>
    {{
      "base_price": {base_price:.6f},
      "extension_price": {extension_price:.6f},
      "parking_fee": {parking_fee:.6f},
      "build_public_service": false
      }}
    </ANSWER>
    """
    return prompt

def build_resident_prompt(obs: np.ndarray, role_desc: str, comm_desc:str,cfg) -> str:
    agree_ratio = float(obs[0])
    required_ratio = float(obs[1])
    step_ratio = float(obs[2])
    base_price = float(obs[3])
    extension_price = float(obs[4])
    parking_fee = float(obs[5])
    max_extension_ratio = float(obs[6])
    extension_ratio = float(obs[7])
    extension_price_anchor = float(obs[8])

    is_subsidy_round = int(obs[9])
    cash_subsidy_cap = float(obs[10])
    effective_cap = min(0.1, max(0.0, cash_subsidy_cap))

    orig_area = float(obs[11])
    last_ext_area = float(obs[12])
    want_parking_last = bool(obs[13])
    utility_last = float(obs[14])
    last_exp_base = float(obs[15])
    last_exp_ext = float(obs[16])

    subsidy_ratio_current = float(obs[17])
    subsidy_amount_current = float(obs[18])
    household_size = float(obs[19])
    household_monthly_income = float(obs[20])
    last_agree = int(round(obs[21]))
    dev_build_public_service = float(obs[22])

    current_allowed_ratio = extension_ratio
    max_ext_area_raw = orig_area * current_allowed_ratio
    max_ext_area = 0.0 if max_ext_area_raw < 1.0 else max_ext_area_raw

    subsidy_block = ""
    if subsidy_ratio_current > 0:
        subsidy_block = f"""
    [Government Cash Subsidy]
    - Current subsidy ratio: {subsidy_ratio_current:.2%}
    - Subsidy amount available to you this round under your current choice: {subsidy_amount_current:.0f} RMB
    """.rstrip()

    show_history = step_ratio > 0.0
    history_block = ""
    if show_history:
        history_block = f"""
    [Your Previous-Round State]
    - Your stance last round: {"Agree" if last_agree == 1 else "Oppose"}
    - Existing area: {orig_area:.1f} sqm
    - Extension choice last round: {last_ext_area:.1f} sqm
    - Parking choice last round: {"Yes" if want_parking_last else "No"}
    - Net utility last round: {utility_last:.0f}
    - Base-area price you considered acceptable last round: {last_exp_base:.0f}
    - Extension-area price you considered acceptable last round: {last_exp_ext:.0f}
    """.rstrip()
    provided_service_block = "[Public Service Promised by the Developer This Round]\n"
    if dev_build_public_service >= 0.5:
        provided_service_block += "- Exogenous institutional setting: build the public service facility."
    else:
        provided_service_block += "- Exogenous institutional setting: do not build the public service facility."

    agree_status_line = f"- Activation threshold: {required_ratio:.2%}"
    prompt = f"""
    {role_desc}
    {comm_desc}
    [Current Renewal Proposal]
    - Renovation price for existing area: {base_price:.0f} RMB/sqm (you must pay this for your full existing housing area; the market construction cost is 3800 RMB/sqm, so a lower price implies the developer loses money)
    - Extension-area price: {extension_price:.0f} RMB/sqm (the renovation cost you pay for newly added area)
    - Maximum extension area currently allowed: {max_ext_area:.1f} sqm
    - After renewal, both the original area and extension area can be sold for profit. The current sale reference is {extension_price_anchor:.0f} RMB/sqm, so more extension area can increase upside but also raises cost.
    - Parking fee: {parking_fee:.0f} RMB/slot (paid only if you choose to purchase parking)
    {agree_status_line}
    {history_block}
    {subsidy_block}
    {provided_service_block}
    Based on your income, household needs, and risk tolerance, weigh cost against potential upside and decide:
    1. Whether to agree to renewal (`agree`)
    2. Extension area (`chosen_extension_area`, use `0` for no extension)
    3. Whether to buy parking (`want_parking`)
    4. Your personally acceptable prices: `expected_base_price` / `expected_extension_price`
    5. The prices you publicly quote to the developer and planner: `quoted_base_price` / `quoted_extension_price` (these may differ from your internal acceptable prices)
    6. Your preferred extension area: `expected_extension_area`
    [Failure Consequence]
    - If negotiation ultimately fails, you will not obtain renewal gains and cannot use this project to increase the value of your property.
    {_answer_tag_instructions(True)}
    - Return strictly in the following format:
    <ANSWER>
    {{
      "agree": true/false,
      "chosen_extension_area": ...,
      "want_parking": true/false,
      "expected_base_price": ...,
      "expected_extension_price": ...,
      "quoted_base_price": ...,
      "quoted_extension_price": ...,
      "expected_extension_area": ...
      }}
    </ANSWER>
    [Consistency Rules]
    - If you choose `agree = 0` (do not accept the current proposal):
      - You may still provide the prices under which you might agree.
      - Those values are visible only to you and do not mean you accept the current proposal.
      - `chosen_extension_area` may be `0` or may represent your ideal-case preference only.
    - If you choose `agree = 1` (accept the current proposal):
      - Your `chosen_extension_area`, `expected_base_price`, and `expected_extension_price` must be consistent with already accepting the current proposal.
      - These values must not be materially above the published policy terms or contradict the current proposal.
    - Responses that violate these consistency rules will be treated as irrational decisions.
    - In your decision, consider not only potential upside but also whether the costs are affordable at your current income level.
    """
    return prompt
