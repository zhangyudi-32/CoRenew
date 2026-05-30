from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import posixpath
import random
import re
import shutil
import subprocess
import sys
import threading
import tempfile
import uuid
from datetime import datetime
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlencode

import geopandas as gpd
import gradio as gr
import matplotlib
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml
from fastapi import FastAPI, Query, UploadFile, File, Body
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, JSONResponse
from matplotlib.colors import Normalize, to_hex
from scipy.spatial.distance import cdist
from sklearn.cluster import KMeans
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from shapely.geometry import Point

try:
    from adjustText import adjust_text

    HAS_ADJUST_TEXT = True
except Exception:
    HAS_ADJUST_TEXT = False


matplotlib.use("Agg")


ROOT = Path(__file__).resolve().parent.parent




_PROJECT_CACHE_KEY = hashlib.sha1(str(ROOT.resolve()).encode("utf-8")).hexdigest()[:10]
TMP_UI_DIR = Path(
    os.environ.get(
        "CORENEW_UI_RUNTIME_DIR",
        str(Path(tempfile.gettempdir()) / "corenew_ui" / _PROJECT_CACHE_KEY),
    )
).expanduser().resolve()
TMP_UI_DIR.mkdir(parents=True, exist_ok=True)
RUN_METADATA_DIR = TMP_UI_DIR / "run_metadata"
RUN_METADATA_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATE_DIR = TMP_UI_DIR / "templates"
TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_CACHE_DIR = TMP_UI_DIR / "upload_cache"
UPLOAD_CACHE_DIR.mkdir(parents=True, exist_ok=True)

RUN_JOBS: dict[str, dict[str, Any]] = {}
RUN_JOBS_LOCK = threading.Lock()

DEFAULT_TEMPLATE_CONFIG = ROOT / "cfg" / "rule-based" / "base+subsidyall.yaml"
GLOBAL_RULE_SEARCH_CONFIG_CANDIDATES = [
    ROOT / "cfg" / "rule-based" / "global_rule_search.yaml",
    ROOT.parent.parent / "cfg" / "rule-based" / "global_rule_search.yaml",
]
DEFAULT_PHASE2_ROOT = ROOT / "output" / "ui_runs"
DEFAULT_OFFICIAL_CSV = ROOT / "data" / "agents_official" / "official_agents.csv"
PREFERRED_THESIS_PYTHON = Path.home() / "anaconda3" / "envs" / "thesis" / "bin" / "python"
DEFAULT_API_BASE_URL = ""
LOCAL_REFERENCE_CONFIG_CANDIDATES: list[Path] = []
DEFAULT_MEDIA_PUBLICITY_POLICY_TEXT = """近期，关于老旧小区自主更新的案例在本地媒体、社区公众号、短视频平台和业主微信群中被频繁讨论。你多次看到一些已经完成更新的小区案例，内容包括环境改善、停车条件优化、公共设施提升，以及居民对更新结果的评价。整体而言，这一议题在你所在社区的线上线下讨论中明显增多。"""

DEFAULT_SHP_CANDIDATES = [
    ROOT / "data" / "geodata" / "residentialarea_qianli.shp",
    ROOT / "data" / "geodata" / "residential_area_huadu.shp",
]

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

COMMUNITY_NAME_MAP = {
    "花都光明巷小区": "HuaduGuangmingxiangXiaoqu",
    "荷景苑": "Hejingyuan",
    "金联西座": "JinlianXizuo",
    "万胜楼": "WanshengLou",
    "中华楼": "ZhonghuaLou",
    "花城南路小区": "HuachengNanluXiaoqu",
    "龙华楼": "LonghuaLou",
    "雅图花园": "YatuHuayuan",
    "永大新城": "YongdaXincheng",
    "钻石花苑": "ZuanshiHuayuan",
    "富临楼": "FulinLou",
}

NAME_COLUMN_CANDIDATES = ["小区", "community", "community_name", "name", "小区名称"]
MAP_METRICS = {
    "final_agree_ratio": "Final Agreement Rate",
    "avg_extension_ratio": "Final Extension Policy",
    "avg_subsidy_ratio": "Final Subsidy Policy",
}
COMPARISON_METRICS = {
    "final_agree_ratio": {"label": "Agreement Rate", "goal": "max", "format": "ratio"},
    "developer_profit": {"label": "Developer Profit", "goal": "max", "format": "currency"},
    "resident_mean_utility": {"label": "Resident Mean Utility", "goal": "max", "format": "currency"},
    "utility_gini": {"label": "Utility Gini", "goal": "min", "format": "float"},
    "subsidy_total_cost": {"label": "Subsidy Cost", "goal": "min", "format": "currency"},
    "extension_ratio_final": {"label": "Extension Ratio", "goal": "max", "format": "ratio"},
}
ROUND_UI_RENAME = {
    "轮次": "Round",
    "同意户数": "Agreeing Households",
    "总户数": "Total Households",
    "同意率": "Agreement Rate",
    "规划扩面比例": "Planner Extension Ratio",
    "规划补贴比例": "Planner Subsidy Ratio",
    "开发商原面积报价": "Developer Base Price",
    "开发商扩面报价": "Developer Extension Price",
    "开发商停车费": "Developer Parking Fee",
    "平均意向扩面面积": "Avg Expected Extension Area",
    "平均心理原面积价格": "Avg Expected Base Price",
    "平均心理扩面价格": "Avg Expected Extension Price",
    "平均报出原面积价格": "Avg Quoted Base Price",
    "平均报出扩面价格": "Avg Quoted Extension Price",
}
RESIDENT_UI_RENAME = {
    "住户ID": "Resident ID",
    "是否同意": "Agree",
    "本轮选择扩面面积": "Selected Extension Area",
    "是否要车位": "Needs Parking",
    "心理原面积价格": "Expected Base Price",
    "心理扩面价格": "Expected Extension Price",
    "报出原面积价格": "Quoted Base Price",
    "报出扩面价格": "Quoted Extension Price",
    "期望扩面面积": "Expected Extension Area",
}
COMMUNITY_REQUIRED_COLUMNS = {
    "小区",
    "area",
    "容积率",
    "建成年代",
    "parking_slots_per_capita",
    "parking_price",
    "nearby_max_price",
    "房价（元/平）",
}
COMMUNITY_AGENT_GENERATION_COLUMNS = COMMUNITY_REQUIRED_COLUMNS | {
    "户数",
    "dominant unit type",
    "rent_rate",
}
COMMUNITY_POPULATION_COLUMNS = {
    "小区",
    "户数",
    "dominant unit type",
    "rent_rate",
    "房价（元/平）",
}
COMMUNITY_POPULATION_FIELD_LABELS = [
    ("小区", "Community Name"),
    ("户数", "Household Count"),
    ("dominant unit type", "Dominant Unit Type"),
    ("rent_rate", "Rent Rate"),
    ("房价（元/平）", "Pre-renewal House Price"),
]
COMMUNITY_SIMULATION_FIELD_LABELS = [
    ("area", "Community Area"),
    ("容积率", "FAR"),
    ("建成年代", "Build Year"),
    ("parking_slots_per_capita", "Parking Slots / Capita"),
    ("parking_price", "Parking Price"),
    ("nearby_max_price", "Nearby Max Price"),
]
AGENT_REQUIRED_COLUMNS = {
    "community",
    "agent_id",
    "unit_size_sqm",
    "final_voting_weight",
    "annual_income_rmb",
    "household_size",
    "household_monthly_income_rmb",
}
ALL_AGENT_REQUIRED_COLUMNS = {"community", "unit_size_sqm"}
MODEL_OPTIONS = [
    ("DeepSeek V3.2", "DeepSeek-V3.2"),
    ("GPT-4o Mini", "gpt-4o-mini"),
    ("GPT-4.1 Mini", "gpt-4.1-mini"),
    ("GPT-4o", "gpt-4o"),
    ("DeepSeek Chat", "deepseek-chat"),
]
PLANNER_POLICY_OPTIONS = [
    ("Baseline", "baseline"),
]
DEVELOPER_POLICY_OPTIONS = [
    ("Baseline", "baseline"),
    ("Conservative", "conservative"),
    ("Aggressive", "aggressive"),
]
PLANNER_COST_BENEFIT_OPTIONS = [
    ("Agreement rate", "agreement_rate"),
    ("Public subsidy spend", "subsidy_cost"),
    ("Developer viability", "developer_viability"),
    ("Resident welfare", "resident_welfare"),
    ("Urban service upgrade", "public_service_benefit"),
]
DEVELOPER_COST_BENEFIT_OPTIONS = [
    ("Base-area sales income", "base_sale_income"),
    ("Extension sales income", "extension_sale_income"),
    ("Parking income", "parking_income"),
    ("Construction cost", "construction_cost"),
    ("Subsidy interaction", "subsidy_interaction"),
    ("Public service cost", "public_service_cost"),
]
RESIDENT_COST_BENEFIT_OPTIONS = [
    ("Status quo housing value", "status_quo_value"),
    ("Post-renewal housing value", "post_renewal_value"),
    ("Extension area gain", "extension_gain"),
    ("Cash subsidy", "cash_subsidy"),
    ("Parking payment", "parking_payment"),
    ("Relocation / disruption cost", "relocation_cost"),
    ("Public service benefit", "public_service_benefit"),
]
DEFAULT_COMMUNITY_CSV = ROOT / "community_example.csv"
DEFAULT_BOUNDARY_SHP = ROOT / "data" / "geodata" / "residential_area_huadu.shp"
DEFAULT_RESIDENTS_PER_HOUSEHOLD = 1.84
DEFAULT_VACANCY_RATIO = 0.30
DEFAULT_REPRESENTATIVES_PER_COMMUNITY = 5
DEFAULT_HARDSHIP_QUANTILE = 0.20
DEFAULT_DEVELOPER_MIN_PROFIT_RATE = 0.00
DEFAULT_SELECTED_UTILITY_CATEGORIES = ["base", "extension", "parking", "subsidy"]
DEFAULT_AGREEMENT_RULE_ROWS = pd.DataFrame(
    [
        {"max_age": 50, "ratio": 0.90},
        {"max_age": 60, "ratio": 0.80},
        {"max_age": 70, "ratio": 0.70},
        {"max_age": None, "ratio": 0.65},
    ]
)
UTILITY_CATEGORY_DEFS = {
    "base": {
        "label": "Base",
        "impacts": {"planner": "neutral", "developer": "inflow", "resident": "outflow"},
        "modules": {
            "planner": [],
            "developer": ["base_sale_income"],
            "resident": ["base_payment"],
        },
    },
    "extension": {
        "label": "Extension",
        "impacts": {"planner": "neutral", "developer": "inflow", "resident": "outflow"},
        "modules": {
            "planner": [],
            "developer": ["extension_sale_income"],
            "resident": ["extension_payment", "extension_gain"],
        },
    },
    "parking": {
        "label": "Parking",
        "impacts": {"planner": "neutral", "developer": "inflow", "resident": "outflow"},
        "modules": {
            "planner": [],
            "developer": ["parking_income"],
            "resident": ["parking_payment"],
        },
    },
    "subsidy": {
        "label": "Subsidy",
        "impacts": {"planner": "outflow", "developer": "neutral", "resident": "inflow"},
        "modules": {
            "planner": ["subsidy_cost"],
            "developer": ["subsidy_interaction"],
            "resident": ["cash_subsidy"],
        },
    },
}
UTILITY_FIELD_DEFS = [
    {
        "key": "subsidy_cost",
        "label": "Subsidy cost",
        "agent": "planner",
        "category": "subsidy",
        "direction": "outflow",
        "builtin": True,
        "enabled": True,
        "value_mode": "fixed",
        "fixed_value": 0.1,
        "community_field": None,
        "description": "Planner-side subsidy spend.",
    },
    {
        "key": "base_sale_income",
        "label": "Base sale income",
        "agent": "developer",
        "category": "base",
        "direction": "inflow",
        "builtin": True,
        "enabled": True,
        "value_mode": "fixed",
        "fixed_value": 0.0,
        "community_field": None,
        "description": "Developer revenue from base-area sales.",
    },
    {
        "key": "extension_sale_income",
        "label": "Extension sale income",
        "agent": "developer",
        "category": "extension",
        "direction": "inflow",
        "builtin": True,
        "enabled": True,
        "value_mode": "fixed",
        "fixed_value": 0.0,
        "community_field": None,
        "description": "Developer revenue from extension-area sales.",
    },
    {
        "key": "parking_income",
        "label": "Parking income",
        "agent": "developer",
        "category": "parking",
        "direction": "inflow",
        "builtin": True,
        "enabled": True,
        "value_mode": "fixed",
        "fixed_value": 0.0,
        "community_field": None,
        "description": "Developer revenue from parking fees.",
    },
    {
        "key": "subsidy_interaction",
        "label": "Subsidy interaction",
        "agent": "developer",
        "category": "subsidy",
        "direction": "input",
        "builtin": True,
        "enabled": True,
        "value_mode": "fixed",
        "fixed_value": 0.0,
        "community_field": None,
        "description": "Developer-side interaction with subsidy policy.",
    },
    {
        "key": "base_payment",
        "label": "Base payment",
        "agent": "resident",
        "category": "base",
        "direction": "outflow",
        "builtin": True,
        "enabled": True,
        "value_mode": "fixed",
        "fixed_value": 0.0,
        "community_field": None,
        "description": "Resident payment on the base-area transaction.",
    },
    {
        "key": "extension_payment",
        "label": "Extension payment",
        "agent": "resident",
        "category": "extension",
        "direction": "outflow",
        "builtin": True,
        "enabled": True,
        "value_mode": "fixed",
        "fixed_value": 0.0,
        "community_field": None,
        "description": "Resident payment associated with extension area.",
    },
    {
        "key": "extension_gain",
        "label": "Extension gain",
        "agent": "resident",
        "category": "extension",
        "direction": "inflow",
        "builtin": True,
        "enabled": True,
        "value_mode": "fixed",
        "fixed_value": 0.0,
        "community_field": None,
        "description": "Resident benefit or gain from extension area.",
    },
    {
        "key": "parking_payment",
        "label": "Parking payment",
        "agent": "resident",
        "category": "parking",
        "direction": "outflow",
        "builtin": True,
        "enabled": True,
        "value_mode": "fixed",
        "fixed_value": 0.0,
        "community_field": None,
        "description": "Resident payment for parking.",
    },
    {
        "key": "cash_subsidy",
        "label": "Cash subsidy",
        "agent": "resident",
        "category": "subsidy",
        "direction": "inflow",
        "builtin": True,
        "enabled": True,
        "value_mode": "fixed",
        "fixed_value": 0.0,
        "community_field": None,
        "description": "Resident-side cash subsidy inflow.",
    },
]
VALUE_FLOW_META_EXEMPT_COLUMNS = {"小区", "community", "户数", "dominant unit type", "rent_rate", "建成年代"}

UNIT_SHARE = {
    "S": {"S": 0.65, "M": 0.25, "L": 0.10},
    "M": {"S": 0.20, "M": 0.60, "L": 0.20},
    "L": {"S": 0.10, "M": 0.30, "L": 0.60},
}
UNIT_AREA_RANGE = {
    "S": (45, 65),
    "M": (70, 90),
    "L": (95, 130),
}
UNIT_HH_RANGE = {
    "S": (1, 2),
    "M": (2, 3),
    "L": (3, 5),
}
VAC_SIG, VAC_LO, VAC_HI = 0.08, 0.15, 0.60
INCOME_PTS = [
    (0.10, 35000),
    (0.25, 45000),
    (0.50, 55712),
    (0.75, 80000),
    (0.90, 120000),
]
TENURE_FACTOR = {"renter": 0.95, "owner_occupier": 1.00}
RESIDENT_NOISE_SIGMA = 0.25
VACANT_OWNER_NOISE_SIGMA = 0.40
VACANT_OWNER_PREMIUM = 1.45
OWNER_AGE_MU, OWNER_AGE_SIG, OWNER_AGE_LO, OWNER_AGE_HI = 52, 10, 35, 80
INCOME_PRICE_ELASTICITY = 0.45
INCOME_SCALE_CLIP = (0.70, 1.50)


def _configure_font() -> fm.FontProperties | None:
    local_font = next((path for path in sorted(ROOT.glob("*.ttf")) if path.is_file()), None)
    if local_font is not None:
        fm.fontManager.addfont(str(local_font))
        font_prop = fm.FontProperties(fname=str(local_font))
        plt.rcParams.update(
            {
                "font.sans-serif": [font_prop.get_name()],
                "axes.unicode_minus": False,
                "pdf.fonttype": 42,
                "ps.fonttype": 42,
            }
        )
        return font_prop

    candidates = ["PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "SimHei"]
    available = {font.name for font in fm.fontManager.ttflist}
    picked = next((name for name in candidates if name in available), "DejaVu Sans")
    plt.rcParams.update(
        {
            "font.sans-serif": [picked],
            "axes.unicode_minus": False,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )
    return None


FONT_PROP = _configure_font()


def _runtime_python() -> str:
    if "envs/thesis" in sys.executable:
        return sys.executable
    if PREFERRED_THESIS_PYTHON.exists():
        return str(PREFERRED_THESIS_PYTHON)
    return sys.executable


def _font_kwargs() -> dict[str, Any]:
    return {"fontproperties": FONT_PROP} if FONT_PROP is not None else {}


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _temp_png(prefix: str) -> str:
    path = TMP_UI_DIR / f"{prefix}_{_timestamp()}_{os.getpid()}.png"
    return str(path)


def _strip_str(value: Any) -> str:
    return str(value or "").strip()


def _first_non_empty(*values: Any) -> str:
    for value in values:
        text = _strip_str(value)
        if text:
            return text
    return ""


def mask_api_key(api_key: str | None) -> str:
    key = _strip_str(api_key)
    if not key:
        return ""
    if len(key) <= 8:
        return "****"
    return f"{key[:3]}****{key[-4:]}"


def _redact_sensitive_text(text: Any, sensitive_values: list[str] | tuple[str, ...] = ()) -> str:
    redacted = str(text or "")
    for value in sensitive_values:
        secret = _strip_str(value)
        if secret:
            redacted = redacted.replace(secret, mask_api_key(secret) or "[redacted]")
    redacted = re.sub(r"sk-[A-Za-z0-9_\-]{8,}", "sk-****", redacted)
    return redacted


def _read_dotenv_local(path: Path | None = None) -> dict[str, str]:
    env_path = path or (ROOT / ".env.local")
    values: dict[str, str] = {}
    if not env_path.exists():
        return values
    try:
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("'").strip('"')
            if key:
                values[key] = value
    except OSError:
        return {}
    return values


def _load_local_reference_api_config() -> dict[str, str]:
    for path in LOCAL_REFERENCE_CONFIG_CANDIDATES:
        if not path.exists():
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        return {
            "api_key": _strip_str(data.get("api_key")),
            "base_url": _first_non_empty(data.get("llm_base_url"), data.get("base_url")),
            "model": _first_non_empty(data.get("llm_name"), data.get("model")),
            "source": str(path),
        }
    return {}


def load_local_api_defaults() -> dict[str, str]:
    dotenv = _read_dotenv_local()
    reference = _load_local_reference_api_config()

    api_key = _first_non_empty(
        os.environ.get("OPENAI_API_KEY"),
        os.environ.get("LLM_API_KEY"),
        dotenv.get("OPENAI_API_KEY"),
        dotenv.get("LLM_API_KEY"),
        reference.get("api_key"),
    )
    base_url = _first_non_empty(
        os.environ.get("OPENAI_BASE_URL"),
        os.environ.get("LLM_BASE_URL"),
        dotenv.get("OPENAI_BASE_URL"),
        dotenv.get("LLM_BASE_URL"),
        reference.get("base_url"),
        DEFAULT_API_BASE_URL,
    )
    model = _first_non_empty(
        os.environ.get("OPENAI_MODEL"),
        os.environ.get("LLM_MODEL"),
        os.environ.get("LLM_NAME"),
        dotenv.get("OPENAI_MODEL"),
        dotenv.get("LLM_MODEL"),
        dotenv.get("LLM_NAME"),
        reference.get("model"),
        _load_template_config().get("llm_name") if DEFAULT_TEMPLATE_CONFIG.exists() else "",
        "gpt-4o-mini",
    )
    source = "manual"
    if api_key:
        if os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY"):
            source = "environment"
        elif dotenv.get("OPENAI_API_KEY") or dotenv.get("LLM_API_KEY"):
            source = ".env.local"
        elif reference.get("api_key"):
            source = "local reference config"
    return {
        "api_key": api_key,
        "api_key_masked": mask_api_key(api_key),
        "api_key_source": source,
        "base_url": base_url,
        "model": model,
    }


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass

    if isinstance(value, (int, float, np.integer, np.floating)):
        return float(value)

    text = _strip_str(value)
    if not text or text.lower() in {"nan", "none", "null", "n/a", "na", "--"}:
        return default

    is_percent = text.endswith("%")
    if is_percent:
        text = text[:-1]

    text = (
        text.replace(",", "")
        .replace("¥", "")
        .replace("$", "")
        .strip()
    )

    try:
        numeric = float(text)
    except Exception:
        return default
    return numeric / 100.0 if is_percent else numeric


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if pd.isna(value):
            return default
        return int(value)
    except Exception:
        return default


def _display_path(path: str | Path | None) -> str:
    if path is None:
        return "Not provided"
    raw = _strip_str(path)
    if not raw:
        return "Not provided"
    p = Path(raw).expanduser()
    try:
        return p.resolve().relative_to(ROOT).as_posix()
    except Exception:
        if p.is_absolute():
            return p.name or "External path"
        return raw


def _resolve_app_path(path: str | Path | None) -> str:
    raw = _strip_str(path)
    if not raw:
        return ""
    p = Path(raw).expanduser()
    if p.is_absolute():
        return str(p)
    return str((ROOT / p).resolve())


def _default_output_dir_ui() -> str:
    return "output/ui_runs"


def _default_agents_output_dir_ui() -> str:
    return "data/agents_by_community"


def _new_run_job() -> str:
    job_id = f"job_{uuid.uuid4().hex}"
    with RUN_JOBS_LOCK:
        RUN_JOBS[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "progress": 0.0,
            "current_round": 0,
            "total_rounds": None,
            "message": "Queued",
            "log": "",
            "result": None,
            "error": None,
            "cancel_requested": False,
            "process": None,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
    return job_id


def _update_run_job(job_id: str, **updates):
    with RUN_JOBS_LOCK:
        job = RUN_JOBS.get(job_id)
        if not job:
            return
        job.update(updates)
        job["updated_at"] = datetime.now().isoformat()


def _append_run_job_log(job_id: str | None, text: str):
    if not job_id or not text:
        return
    with RUN_JOBS_LOCK:
        job = RUN_JOBS.get(job_id)
        if not job:
            return
        job["log"] = (job.get("log") or "") + text
        job["updated_at"] = datetime.now().isoformat()


def _public_run_job(job_id: str) -> dict[str, Any]:
    with RUN_JOBS_LOCK:
        job = dict(RUN_JOBS.get(job_id) or {})
    job.pop("process", None)
    return job


def _parse_progress_line(job_id: str, line: str):
    match = re.search(r"Starting negotiation round\s+(\d+)\s*/\s*(\d+)", line)
    if match:
        current = int(match.group(1))
        total = max(1, int(match.group(2)))
        _update_run_job(
            job_id,
            current_round=current,
            total_rounds=total,
            progress=min(0.95, current / total),
            message=f"Round {current} / {total}",
        )
    elif match := re.search(r"\[LLMPolicy:([^\]]+)\]\s+requesting action\s+agent_id=([^\s]+)", line):
        _update_run_job(job_id, message=f"Waiting for {match.group(1)} {match.group(2)}")
    elif match := re.search(r"\[LLMPolicy:([^\]]+)\]\s+completed action\s+agent_id=([^\s]+)", line):
        _update_run_job(job_id, message=f"Completed {match.group(1)} {match.group(2)}")
    elif match := re.search(r"\[RESIDENTS\]\s+Collecting\s+(\d+)\s+actions\s+with\s+(\d+)", line):
        _update_run_job(job_id, message=f"Collecting {match.group(1)} resident actions with {match.group(2)} workers")
    elif match := re.search(r"\[RESIDENTS\]\s+Completed\s+(\d+)/(\d+)\s+agent_id=([^\s]+)", line):
        _update_run_job(job_id, message=f"Resident responses {match.group(1)} / {match.group(2)}")
    elif "[LLMPolicy:" in line and "fallback due to error" in line:
        _update_run_job(job_id, message="LLM timeout or error; using fallback action")
    elif "[SUCCESS]" in line:
        _update_run_job(job_id, message="Consensus reached")
    elif "[FAIL]" in line:
        _update_run_job(job_id, message="Negotiation finished without consensus")


def _mean_or_nan(values: list[Any]) -> float:
    series = pd.to_numeric(pd.Series(values), errors="coerce").dropna()
    return float(series.mean()) if not series.empty else np.nan


def _json_ready(value: Any) -> Any:
    if isinstance(value, pd.DataFrame):
        return [_json_ready(record) for record in value.to_dict(orient="records")]
    if isinstance(value, pd.Series):
        return {str(key): _json_ready(item) for key, item in value.to_dict().items()}
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if pd.isna(value) else float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    return value


def _humanize_identifier(value: Any) -> str:
    text = _strip_str(value)
    if not text:
        return "N/A"
    return text.replace("_", " ").strip().title()


def _resolve_file_input(file_value: Any) -> list[str]:
    if not file_value:
        return []
    if isinstance(file_value, (list, tuple)):
        raw_items = file_value
    else:
        raw_items = [file_value]

    paths: list[str] = []
    for item in raw_items:
        if item is None:
            continue
        if isinstance(item, str):
            paths.append(item)
            continue
        if hasattr(item, "name") and getattr(item, "name"):
            paths.append(str(item.name))
            continue
        if isinstance(item, dict):
            candidate = item.get("path") or item.get("name")
            if candidate:
                paths.append(str(candidate))
    return [p for p in paths if p]


def _resolve_shape_path(uploaded_files: Any) -> str | None:
    for file_path in _resolve_file_input(uploaded_files):
        suffix = Path(file_path).suffix.lower()
        if suffix in {".shp", ".geojson", ".gpkg"}:
            return _resolve_app_path(file_path)
    if DEFAULT_BOUNDARY_SHP.exists():
        return str(DEFAULT_BOUNDARY_SHP.resolve())
    for candidate in DEFAULT_SHP_CANDIDATES:
        if candidate.exists():
            return str(candidate)
    return None


def _copy_or_convert_table(source_path: str | Path, target_dir: Path, stem: str) -> str:
    source = Path(_resolve_app_path(source_path))
    target_dir.mkdir(parents=True, exist_ok=True)

    if source.suffix.lower() in {".csv", ".txt"}:
        target = target_dir / f"{stem}.csv"
        shutil.copy2(source, target)
        return str(target)

    if source.suffix.lower() in {".xlsx", ".xls"}:
        df = pd.read_excel(source)
        target = target_dir / f"{stem}.csv"
        df.to_csv(target, index=False, encoding="utf-8-sig")
        return str(target)

    raise gr.Error(f"Unsupported table format: {source.suffix}")


def _read_table(table_path: str | Path, normalize_aliases: bool = True) -> pd.DataFrame:
    path = Path(_resolve_app_path(table_path))
    if path.suffix.lower() in {".csv", ".txt"}:
        df = pd.read_csv(path, encoding="utf-8-sig")
        if not normalize_aliases:
            return df
        rename_map = {
            src: dst for src, dst in COMMUNITY_COLUMN_ALIASES.items()
            if src in df.columns and dst not in df.columns
        }
        return df.rename(columns=rename_map) if rename_map else df
    if path.suffix.lower() in {".xlsx", ".xls"}:
        df = pd.read_excel(path)
        if not normalize_aliases:
            return df
        rename_map = {
            src: dst for src, dst in COMMUNITY_COLUMN_ALIASES.items()
            if src in df.columns and dst not in df.columns
        }
        return df.rename(columns=rename_map) if rename_map else df
    raise gr.Error(f"Unsupported table format: {path.suffix}")


def _validate_columns(df: pd.DataFrame, required_columns: set[str]) -> list[str]:
    return sorted(column for column in required_columns if column not in df.columns)


def _normalize_community_name(value: Any) -> str:
    token = _strip_str(value)
    return COMMUNITY_NAME_MAP.get(token, token)


def _find_name_column(gdf: gpd.GeoDataFrame) -> str:
    for column in NAME_COLUMN_CANDIDATES:
        if column in gdf.columns:
            return column
    raise KeyError(f"Could not find a community name field in the boundary file. Available columns: {list(gdf.columns)}")


def _community_list_from_data(
    community_df: pd.DataFrame | None = None,
    agent_df: pd.DataFrame | None = None,
) -> list[str]:
    communities: set[str] = set()
    if community_df is not None and "小区" in community_df.columns:
        communities.update(
            community_df["小区"].astype(str).str.strip().map(_normalize_community_name).replace("", np.nan).dropna().tolist()
        )
    if agent_df is not None and "community" in agent_df.columns:
        communities.update(
            agent_df["community"].astype(str).str.strip().map(_normalize_community_name).replace("", np.nan).dropna().tolist()
        )
    return sorted(communities)


def _format_ratio(value: Any) -> str:
    try:
        if value is None or pd.isna(value):
            return "N/A"
    except Exception:
        if value is None:
            return "N/A"
    numeric = _safe_float(value, np.nan)
    if pd.isna(numeric):
        return "N/A"
    return f"{numeric:.1%}"


def _format_currency(value: Any) -> str:
    numeric = _safe_float(value, np.nan)
    if pd.isna(numeric):
        return "N/A"
    return f"{numeric:,.0f}"


def _format_number(value: Any) -> str:
    if value is None:
        return "N/A"
    try:
        if pd.isna(value):
            return "N/A"
    except Exception:
        pass
    try:
        numeric = float(value)
    except Exception:
        text = _strip_str(value)
        return "N/A" if text.lower() in {"nan", "none", "null", "n/a", "na", "--"} else (text or "N/A")
    if pd.isna(numeric):
        return "N/A"
    if numeric.is_integer():
        return f"{int(numeric)}"
    return f"{numeric:.4f}".rstrip("0").rstrip(".")


def _format_metric_value(metric: str, value: Any) -> str:
    numeric = _safe_float(value, np.nan)
    if pd.isna(numeric):
        return "N/A"
    if metric in {"final_agree_ratio", "avg_extension_ratio", "avg_subsidy_ratio"}:
        return _format_ratio(numeric)
    return _format_number(numeric)


def _map_value_series(df: pd.DataFrame, metric: str) -> pd.Series:
    if metric not in df.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(df[metric], errors="coerce")


def _policy_ratio_from_row(row: Any, candidate_columns: list[str]) -> float:
    for column in candidate_columns:
        try:
            if column in row:
                value = _safe_float(row.get(column), np.nan)
                if not pd.isna(value):
                    return float(value)
        except Exception:
            continue
    return np.nan


def _policy_ratio_to_bps(value: Any) -> int | None:
    value = _safe_float(value, np.nan)
    if pd.isna(value):
        return None
    return int(round(float(value) * 10000))


def _policy_bps_to_ratio(value: int | None) -> float:
    return np.nan if value is None else float(value) / 10000.0


def _policy_rule_id_from_ratios(extension_value: Any, subsidy_value: Any) -> str:
    ext_bps = _policy_ratio_to_bps(extension_value)
    sub_bps = _policy_ratio_to_bps(subsidy_value)
    ext_part = "na" if ext_bps is None else str(ext_bps)
    sub_part = "na" if sub_bps is None else str(sub_bps)
    return f"policy_ext_{ext_part}_subsidy_{sub_part}"


def _policy_rule_content(extension_value: Any, subsidy_value: Any) -> str:
    ext = _safe_float(extension_value, np.nan)
    sub = _safe_float(subsidy_value, np.nan)
    ext_text = "N/A" if pd.isna(ext) else f"{ext:.0%}"
    sub_text = "N/A" if pd.isna(sub) else f"{sub:.0%}"
    return f"ext<={ext_text} · subsidy<={sub_text}"


@lru_cache(maxsize=1)
def _configured_rule_cap_lookup() -> dict[str, tuple[float, float]]:
    for path in GLOBAL_RULE_SEARCH_CONFIG_CANDIDATES:
        if not path.exists():
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception:
            continue
        search_cfg = data.get("global_rule_search", {}) if isinstance(data, dict) else {}
        search_space = search_cfg.get("search_space", {}) if isinstance(search_cfg, dict) else {}
        extension_caps = search_space.get("extension_caps", []) or []
        subsidy_caps = search_space.get("subsidy_caps", []) or []
        excluded = {
            (round(_safe_float(item.get("extension_cap"), np.nan), 10), round(_safe_float(item.get("subsidy_cap"), np.nan), 10))
            for item in (search_cfg.get("exclude_pairs", []) or [])
            if isinstance(item, dict)
        }
        lookup: dict[str, tuple[float, float]] = {}
        rule_index = 1
        for extension_cap in extension_caps:
            ext = _safe_float(extension_cap, np.nan)
            for subsidy_cap in subsidy_caps:
                sub = _safe_float(subsidy_cap, np.nan)
                if (round(ext, 10), round(sub, 10)) in excluded:
                    continue
                lookup[f"rule_{rule_index:04d}"] = (float(ext), float(sub))
                rule_index += 1
        for item in search_cfg.get("extra_pairs", []) or []:
            if not isinstance(item, dict):
                continue
            rule_id = _strip_str(item.get("rule_id"))
            if rule_id:
                lookup[rule_id] = (
                    _safe_float(item.get("extension_cap"), np.nan),
                    _safe_float(item.get("subsidy_cap"), np.nan),
                )
        return lookup
    return {}


@lru_cache(maxsize=16)
def _phase2_rule_cap_lookup(phase2_root: str) -> dict[str, tuple[float, float]]:
    lookup = dict(_configured_rule_cap_lookup())
    path = Path(phase2_root) / "phase2_global_rule_results.csv"
    if path.exists():
        try:
            df = pd.read_csv(path)
            if {"rule_id", "extension_cap", "subsidy_cap"}.issubset(df.columns):
                for row in df.itertuples(index=False):
                    rule_id = _strip_str(getattr(row, "rule_id", ""))
                    ext = _safe_float(getattr(row, "extension_cap", np.nan), np.nan)
                    sub = _safe_float(getattr(row, "subsidy_cap", np.nan), np.nan)
                    if rule_id and not pd.isna(ext) and not pd.isna(sub):
                        lookup[rule_id] = (float(ext), float(sub))
        except Exception:
            pass
    return lookup


def _apply_phase2_rule_caps(df: pd.DataFrame, phase2_root: str | None = None) -> pd.DataFrame:
    if df is None or df.empty or "rule_id" not in df.columns:
        return pd.DataFrame() if df is None else df
    lookup = _phase2_rule_cap_lookup(phase2_root) if phase2_root else _configured_rule_cap_lookup()
    if not lookup:
        return df
    if "extension_cap" not in df.columns:
        df["extension_cap"] = np.nan
    if "subsidy_cap" not in df.columns:
        df["subsidy_cap"] = np.nan
    for idx, row in df.iterrows():
        rule_id = _strip_str(row.get("rule_id"))
        caps = lookup.get(rule_id)
        if not caps:
            continue
        if pd.isna(_safe_float(row.get("extension_cap"), np.nan)):
            df.at[idx, "extension_cap"] = caps[0]
        if pd.isna(_safe_float(row.get("subsidy_cap"), np.nan)):
            df.at[idx, "subsidy_cap"] = caps[1]
    return df


def _annotate_phase2_policy_groups(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame() if df is None else df.copy()
    annotated = df.copy()
    for column in [
        "extension_cap",
        "subsidy_cap",
        "extension_ratio_final",
        "cash_subsidy_ratio_final",
        "avg_extension_ratio",
        "avg_subsidy_ratio",
    ]:
        if column in annotated.columns:
            annotated[column] = pd.to_numeric(annotated[column], errors="coerce")

    extension_candidates = ["extension_cap"]
    subsidy_candidates = ["subsidy_cap"]

    policy_extension = []
    policy_subsidy = []
    policy_rule_ids = []
    for _, row in annotated.iterrows():
        ext = _policy_ratio_from_row(row, extension_candidates)
        sub = _policy_ratio_from_row(row, subsidy_candidates)
        policy_extension.append(ext)
        policy_subsidy.append(sub)
        if "rule_id" in annotated.columns:
            policy_rule_ids.append(str(row.get("rule_id")))
        else:
            policy_rule_ids.append(_policy_rule_id_from_ratios(ext, sub))

    annotated["source_rule_id"] = annotated["rule_id"].astype(str) if "rule_id" in annotated.columns else ""
    annotated["policy_rule_id"] = policy_rule_ids
    annotated["policy_extension_cap"] = policy_extension
    annotated["policy_subsidy_cap"] = policy_subsidy
    annotated["policy_rule_content"] = [
        _policy_rule_content(ext, sub) for ext, sub in zip(policy_extension, policy_subsidy)
    ]
    return annotated


def _read_phase2_csv_files(phase2_root: str, filename: str) -> pd.DataFrame:
    root = Path(_resolve_app_path(phase2_root))
    if not root.exists():
        return pd.DataFrame()

    direct = root / filename
    csv_paths = [direct] if direct.exists() else sorted(
        path for path in root.rglob(filename)
        if path.is_file() and not any(part.startswith(".") or part == "__MACOSX" for part in path.parts)
    )
    if not csv_paths:
        return pd.DataFrame()

    frames: list[pd.DataFrame] = []
    for csv_path in csv_paths:
        try:
            frame = pd.read_csv(csv_path)
        except Exception:
            continue
        if frame.empty:
            continue
        frame = frame.copy()
        frame["_phase2_source_dir"] = str(csv_path.parent.resolve())
        frames.append(frame)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True, sort=False)


def _load_yaml_file(path: Path) -> dict[str, Any]:
    try:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}
    return {}


def _phase2_log_run_dir(log_path: Path, root: Path) -> Path:
    """Return the experiment folder that owns a raw negotiation log."""
    try:
        resolved_root = root.resolve()
        parents = [log_path.parent, *log_path.parents]
        for parent in parents:
            if (parent / "ui_run.yaml").exists():
                return parent.resolve()
            if parent.resolve() == resolved_root:
                break
        try:
            relative = log_path.resolve().relative_to(resolved_root)
            if len(relative.parts) > 1:
                return (resolved_root / relative.parts[0]).resolve()
        except Exception:
            pass
        return resolved_root
    except Exception:
        return log_path.parent.resolve()


def _phase2_log_has_own_summary_csv(log_path: Path, root: Path) -> bool:
    run_dir = _phase2_log_run_dir(log_path, root)
    return (run_dir / "phase2_community_results_by_rule.csv").exists()


def _config_for_log_path(log_path: Path, root: Path) -> dict[str, Any]:
    candidates: list[Path] = []
    try:
        for parent in [log_path.parent, *log_path.parents]:
            candidates.append(parent / "ui_run.yaml")
            if parent.resolve() == root.resolve():
                break
        candidates.append(root / "ui_run.yaml")
    except Exception:
        candidates.append(root / "ui_run.yaml")
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate.resolve()) if candidate.exists() else str(candidate)
        if key in seen:
            continue
        seen.add(key)
        data = _load_yaml_file(candidate)
        if data:
            return data
    return {}


def _phase2_config_rule_id(cfg: dict[str, Any], fallback: str) -> str:
    if not isinstance(cfg, dict) or not cfg:
        return fallback
    ext = _safe_float(cfg.get("max_extension_ratio"), np.nan)
    sub = _safe_float(cfg.get("cash_subsidy_cap"), np.nan)
    natural_policy = _strip_str(cfg.get("planner_soft_policy_text"))
    if pd.isna(ext) and pd.isna(sub) and not natural_policy:
        return fallback
    ext_part = "na" if pd.isna(ext) else str(_policy_ratio_to_bps(ext))
    sub_part = "na" if pd.isna(sub) else str(_policy_ratio_to_bps(sub))
    text_part = "none" if not natural_policy else hashlib.sha1(natural_policy.encode("utf-8")).hexdigest()[:8]
    return f"config_ext_{ext_part}_subsidy_{sub_part}_nl_{text_part}"


def _phase2_policy_text_short_name(policy_text: Any) -> str:
    text = _strip_str(policy_text).replace("\n", " ").strip()
    if not text:
        return ""
    parts = re.findall(r"[A-Za-z0-9_\-]+|[\u4e00-\u9fff]", text)
    return parts[0] if parts else text.split()[0]


def _phase2_config_rule_content(cfg: dict[str, Any], extension_cap: Any, subsidy_cap: Any) -> str:
    base = _policy_rule_content(extension_cap, subsidy_cap)
    natural_policy = _strip_str(cfg.get("planner_soft_policy_text")) if isinstance(cfg, dict) else ""
    short_policy = _phase2_policy_text_short_name(natural_policy)
    if short_policy:
        return f"{base} · NL policy: {short_policy}"
    return base


@lru_cache(maxsize=16)
def _read_boundary(boundary_path: str) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(_resolve_app_path(boundary_path))
    name_col = _find_name_column(gdf)
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    gdf = gdf.copy()
    gdf["community_name"] = gdf[name_col].astype(str).str.strip().map(_normalize_community_name)
    return gdf


def _aggregate_phase2_global_from_community(community_df: pd.DataFrame, phase2_root: str | None = None) -> pd.DataFrame:
    community_df = _annotate_phase2_policy_groups(community_df)
    if community_df.empty or {"policy_rule_id", "community_name"}.difference(community_df.columns):
        return pd.DataFrame()

    for column in [
        "is_success",
        "utility_gini",
        "low_income_mean_utility",
        "subsidy_total_cost",
        "extension_ratio_final",
        "cash_subsidy_ratio_final",
        "policy_extension_cap",
        "policy_subsidy_cap",
        "seed",
        "source_rule_id",
        "rule_content",
        "planner_soft_policy_text",
    ]:
        if column not in community_df.columns:
            community_df[column] = np.nan

    pair_means = (
        community_df.groupby(["policy_rule_id", "community_name"], as_index=False, dropna=False)
        .agg(
            sample_count=("seed", "count"),
            source_rule_count=("source_rule_id", "nunique"),
            source_rule_ids=("source_rule_id", lambda values: ",".join(sorted({str(v) for v in values if str(v) and str(v) != "nan"}))),
            rule_content=("rule_content", lambda values: next((_strip_str(v) for v in values if _strip_str(v)), "")),
            planner_soft_policy_text=("planner_soft_policy_text", lambda values: next((_strip_str(v) for v in values if _strip_str(v)), "")),
            is_success=("is_success", "mean"),
            utility_gini=("utility_gini", "mean"),
            low_income_mean_utility=("low_income_mean_utility", "mean"),
            subsidy_total_cost=("subsidy_total_cost", "mean"),
            extension_ratio_final=("extension_ratio_final", "mean"),
            cash_subsidy_ratio_final=("cash_subsidy_ratio_final", "mean"),
            policy_extension_cap=("policy_extension_cap", "mean"),
            policy_subsidy_cap=("policy_subsidy_cap", "mean"),
        )
    )
    grouped = (
        pair_means.groupby("policy_rule_id", as_index=False, dropna=False)
        .agg(
            community_count=("community_name", "nunique"),
            run_count=("sample_count", "sum"),
            source_rule_count=("source_rule_count", "sum"),
            rule_content=("rule_content", lambda values: next((_strip_str(v) for v in values if _strip_str(v)), "")),
            planner_soft_policy_text=("planner_soft_policy_text", lambda values: next((_strip_str(v) for v in values if _strip_str(v)), "")),
            success_count=("is_success", "sum"),
            success_rate=("is_success", "mean"),
            avg_utility_gini=("utility_gini", "mean"),
            avg_low_income_mean_utility=("low_income_mean_utility", "mean"),
            total_subsidy_cost=("subsidy_total_cost", "sum"),
            extension_cap=("policy_extension_cap", "mean"),
            subsidy_cap=("policy_subsidy_cap", "mean"),
        )
        .rename(columns={"policy_rule_id": "rule_id"})
        .sort_values(["success_count", "success_rate", "extension_cap", "subsidy_cap"], ascending=[False, False, True, True])
        .reset_index(drop=True)
    )
    grouped = _apply_phase2_rule_caps(grouped, phase2_root) if phase2_root else grouped
    computed_rule_content = grouped.apply(lambda row: _policy_rule_content(row["extension_cap"], row["subsidy_cap"]), axis=1)
    if "rule_content" in grouped.columns:
        existing_rule_content = grouped["rule_content"].map(_strip_str)
        grouped["rule_content"] = existing_rule_content.where(existing_rule_content.astype(bool), computed_rule_content)
    else:
        grouped["rule_content"] = computed_rule_content
    return grouped


def _prepare_phase2_global_csv(df: pd.DataFrame, phase2_root: str) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    for column in ["extension_cap", "subsidy_cap"]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    df = _apply_phase2_rule_caps(df, phase2_root)
    if "community_count" not in df.columns:
        if "total_communities" in df.columns:
            df["community_count"] = pd.to_numeric(df["total_communities"], errors="coerce")
        elif "sampled_communities" in df.columns:
            df["community_count"] = pd.to_numeric(df["sampled_communities"], errors="coerce")
        else:
            df["community_count"] = np.nan
    if "run_count" not in df.columns:
        df["run_count"] = np.nan
    if {"extension_cap", "subsidy_cap"}.issubset(df.columns):
        computed_rule_content = df.apply(lambda row: _policy_rule_content(row["extension_cap"], row["subsidy_cap"]), axis=1)
        if "rule_content" in df.columns:
            existing_rule_content = df["rule_content"].map(_strip_str)
            df["rule_content"] = existing_rule_content.where(existing_rule_content.astype(bool), computed_rule_content)
        else:
            df["rule_content"] = computed_rule_content
    return df


@lru_cache(maxsize=16)
def _load_phase2_global_results(phase2_root: str) -> pd.DataFrame:
    csv_df = _prepare_phase2_global_csv(_read_phase2_csv_files(phase2_root, "phase2_global_rule_results.csv"), phase2_root)

    log_df = _load_negotiation_logs_as_phase2_results(phase2_root)
    if not log_df.empty and "_has_summary_csv" in log_df.columns:
        log_df = log_df.loc[~log_df["_has_summary_csv"].astype(bool)].copy()
    log_global_df = _aggregate_phase2_global_from_community(log_df, phase2_root) if not log_df.empty else pd.DataFrame()

    frames = [frame for frame in [csv_df, log_global_df] if frame is not None and not frame.empty]
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True, sort=False)
    if "rule_id" in df.columns:
        df = df.drop_duplicates(subset=["rule_id"], keep="first")
    sort_columns = [
        column
        for column in ["success_count", "avg_utility_gini", "avg_low_income_mean_utility", "total_subsidy_cost"]
        if column in df.columns
    ]
    if sort_columns:
        ascending = [False, True, False, True][: len(sort_columns)]
        df = df.sort_values(sort_columns, ascending=ascending)
    return df.reset_index(drop=True)


def _load_phase2_community_csv_results(phase2_root: str) -> pd.DataFrame:
    df = _read_phase2_csv_files(phase2_root, "phase2_community_results_by_rule.csv")
    if df.empty:
        return pd.DataFrame()
    df = df.copy()
    if "community_name" in df.columns:
        df["community_name"] = df["community_name"].astype(str).str.strip().map(_normalize_community_name)
    df["_source_kind"] = "summary_csv"
    return df


@lru_cache(maxsize=16)
def _load_phase2_community_results(phase2_root: str) -> pd.DataFrame:
    csv_df = _load_phase2_community_csv_results(phase2_root)
    log_df = _load_negotiation_logs_as_phase2_results(phase2_root)
    if not log_df.empty and "_has_summary_csv" in log_df.columns:
        # If a run already provides a summary CSV, keep that CSV as the aggregate source
        # and reserve its raw logs for click-through negotiation details. This prevents
        # summary rows and raw log rows from double-counting the same experiment.
        log_df = log_df.loc[~log_df["_has_summary_csv"].astype(bool)].copy()
    frames = [frame for frame in [csv_df, log_df] if frame is not None and not frame.empty]
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True, sort=False)


def _rule_id_from_log_path(log_path: Path) -> str:
    for parent in log_path.parents:
        if re.fullmatch(r"rule_\d{4}", parent.name):
            return parent.name
    match = re.search(r"negotiation_log_(\d{8}_\d{6})", log_path.name)
    timestamp = match.group(1) if match else datetime.fromtimestamp(log_path.stat().st_mtime).strftime("%Y%m%d_%H%M%S")
    community = _normalize_community_name(log_path.parent.name.replace("sim_", "")) or "community"
    digest = hashlib.sha1(str(log_path.resolve()).encode("utf-8")).hexdigest()[:6]
    return f"run_{timestamp}_{community}_{digest}"


def _seed_from_log_path(log_path: Path) -> str:
    match = re.search(r"negotiation_log_(\d{8}_\d{6})", log_path.name)
    return match.group(1) if match else str(int(log_path.stat().st_mtime))



def _phase2_gini(values: Any) -> float:
    arr = pd.to_numeric(pd.Series(list(values) if isinstance(values, (list, tuple, np.ndarray, pd.Series)) else []), errors="coerce").dropna().to_numpy(dtype=float)
    if arr.size == 0:
        return np.nan
    arr = np.maximum(arr, 0.0)
    total = float(arr.sum())
    if total <= 0:
        return 0.0
    arr.sort()
    n = arr.size
    return float((2.0 * np.arange(1, n + 1).dot(arr)) / (n * total) - (n + 1.0) / n)


@lru_cache(maxsize=16)
def _phase2_agents_table_for_root(root_str: str) -> pd.DataFrame:
    root = Path(root_str)
    candidates: list[Path] = []
    for base in [root, ROOT]:
        candidates.extend([
            base / "data" / "agents_by_community" / "ALL_agents.csv",
            base / "data" / "agents_official" / "official_agents.csv",
        ])
    try:
        for csv_path in root.rglob("*.csv"):
            name = csv_path.name.lower()
            if "agent" in name and csv_path not in candidates:
                candidates.append(csv_path)
    except Exception:
        pass

    frames: list[pd.DataFrame] = []
    seen: set[str] = set()
    for path in candidates:
        try:
            key = str(path.resolve())
        except Exception:
            key = str(path)
        if key in seen or not path.exists():
            continue
        seen.add(key)
        try:
            frame = pd.read_csv(path)
        except Exception:
            continue
        if {"agent_id", "unit_size_sqm"}.issubset(frame.columns):
            frame = frame.copy()
            if "community" in frame.columns:
                frame["_community_norm"] = frame["community"].astype(str).map(_normalize_community_name)
            else:
                frame["_community_norm"] = ""
            frames.append(frame)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True, sort=False).drop_duplicates(subset=["agent_id"], keep="first")



@lru_cache(maxsize=16)
def _phase2_agent_lookup_for_root(root_str: str) -> dict[str, dict[str, Any]]:
    agents = _phase2_agents_table_for_root(root_str)
    if agents.empty or "agent_id" not in agents.columns:
        return {}
    return agents.set_index(agents["agent_id"].astype(str)).to_dict(orient="index")

def _phase2_resident_rows(log_data: dict[str, Any]) -> list[dict[str, Any]]:
    history = log_data.get("negotiation_history")
    if isinstance(history, list) and history:
        for entry in reversed(history):
            residents = entry.get("residents") if isinstance(entry, dict) else None
            if isinstance(residents, list) and residents:
                return [r for r in residents if isinstance(r, dict)]
    residents = log_data.get("residents")
    if isinstance(residents, list):
        return [r for r in residents if isinstance(r, dict)]
    return []


def _phase2_compute_objectives_from_log(log_data: dict[str, Any], log_path: Path, root: Path, run_cfg: dict[str, Any] | None = None) -> dict[str, float]:
    """Compute per-community objective metrics from a raw negotiation log.

    New UI runs do not necessarily write phase2 summary CSVs or community_result.json.
    This helper reconstructs the six comparison objectives from the final log state so
    the community detail cards and Policy Comparison are not dependent on summary files.
    """
    final_metrics = log_data.get("final_metrics", {}) or {}
    final_policy = log_data.get("final_policy", {}) or {}
    planner = final_policy.get("planner", {}) or {}
    developer = final_policy.get("developer", {}) or {}
    community_info = log_data.get("community_info", {}) or {}
    residents = _phase2_resident_rows(log_data)

    extension_ratio = _safe_float(planner.get("extension_ratio"), _safe_float(community_info.get("extension_ratio"), 0.0))
    subsidy_ratio = _safe_float(planner.get("cash_subsidy_ratio"), 0.0)
    final_agree_ratio = _safe_float(final_metrics.get("final_agree_ratio"), np.nan)
    if pd.isna(final_agree_ratio) and residents:
        agree_values = [_safe_float(r.get("agree"), np.nan) for r in residents]
        agree_values = [v for v in agree_values if not pd.isna(v)]
        final_agree_ratio = float(np.mean(agree_values)) if agree_values else np.nan

    developer_profit = _safe_float(final_metrics.get("final_profit", developer.get("profit")), np.nan)
    developer_profit_rate = _safe_float(final_metrics.get("final_profit_rate", developer.get("profit_rate")), np.nan)

    if not residents:
        return {
            "final_agree_ratio": final_agree_ratio,
            "extension_ratio_final": extension_ratio,
            "cash_subsidy_ratio_final": subsidy_ratio,
            "developer_profit": developer_profit,
            "developer_profit_rate": developer_profit_rate,
            "resident_mean_utility": np.nan,
            "low_income_mean_utility": np.nan,
            "utility_std": np.nan,
            "utility_gini": np.nan,
            "subsidy_total_cost": np.nan,
        }

    agent_by_id = _phase2_agent_lookup_for_root(str(root.resolve()))

    cfg = run_cfg if isinstance(run_cfg, dict) else {}
    utility_cfg = cfg.get("utility", {}) if isinstance(cfg.get("utility", {}), dict) else {}
    resident_weights = utility_cfg.get("resident", {}) if isinstance(utility_cfg.get("resident", {}), dict) else {}
    subsidy_cfg = cfg.get("subsidy", {}) if isinstance(cfg.get("subsidy", {}), dict) else {}
    low_income_only = bool(subsidy_cfg.get("low_income_only", False))
    low_income_threshold = _safe_float(subsidy_cfg.get("low_income_threshold"), np.inf)

    w_base_cost = _safe_float(resident_weights.get("base_cost"), 1.0)
    w_extension_cost = _safe_float(resident_weights.get("extension_cost"), 1.0)
    w_parking_cost = _safe_float(resident_weights.get("parking_cost"), 1.0)
    w_market_value = _safe_float(resident_weights.get("market_value"), 1.0)
    w_subsidy = _safe_float(resident_weights.get("subsidy"), 1.0)

    total_existing_area = _safe_float(community_info.get("total_existing_area"), np.nan)
    if pd.isna(total_existing_area) or total_existing_area <= 0:
        total_existing_area = np.nan
    public_service_area = 180.0 if bool(developer.get("build_public_service", False)) else 0.0
    effective_ext_ratio = max(0.0, extension_ratio - (public_service_area / total_existing_area if not pd.isna(total_existing_area) and total_existing_area > 0 else 0.0))

    base_price = _safe_float(developer.get("base_price"), 0.0)
    extension_price = _safe_float(developer.get("extension_price"), _safe_float(community_info.get("extension_price"), 0.0))
    ext_cost_price = extension_price * 0.8
    market_price = _safe_float(community_info.get("extension_price"), _safe_float(community_info.get("current_price"), extension_price))
    parking_fee = _safe_float(developer.get("parking_fee"), 0.0)

    default_orig_area = np.nan
    if not pd.isna(total_existing_area) and len(residents) > 0:
        default_orig_area = total_existing_area / float(len(residents))

    utilities: list[float] = []
    subsidy_amounts: list[float] = []
    low_income_utilities: list[float] = []
    orig_areas: list[float] = []

    for resident in residents:
        agent_id = _strip_str(resident.get("agent_id"))
        agent = agent_by_id.get(agent_id, {}) if agent_id else {}
        orig_area = _safe_float(agent.get("unit_size_sqm"), np.nan)
        if pd.isna(orig_area) or orig_area <= 0:
            expected_ext = _safe_float(resident.get("expected_extension_area"), np.nan)
            if not pd.isna(expected_ext) and effective_ext_ratio > 0:
                orig_area = max(expected_ext / effective_ext_ratio, 1.0)
            elif not pd.isna(default_orig_area) and default_orig_area > 0:
                orig_area = default_orig_area
            else:
                orig_area = 1.0
        orig_areas.append(orig_area)

        selected_ext = _safe_float(resident.get("chosen_extension_area", resident.get("ext_area")), 0.0)
        chosen_ext = max(0.0, min(selected_ext, orig_area * effective_ext_ratio))
        want_parking = 1.0 if _safe_float(resident.get("want_parking"), 0.0) >= 0.5 else 0.0

        base_cost = w_base_cost * (orig_area * base_price)
        ext_cost = w_extension_cost * (chosen_ext * ext_cost_price)
        parking_cost = w_parking_cost * (parking_fee * want_parking)
        expand_cost = base_cost + ext_cost + parking_cost
        no_expand_cost = base_cost + parking_cost
        cost = expand_cost if chosen_ext > 0 else no_expand_cost

        base_value = w_market_value * (orig_area * market_price)
        ext_value = w_market_value * (chosen_ext * market_price)
        expand_value = base_value + ext_value
        no_expand_value = base_value
        utility_expand = expand_value - expand_cost
        utility_no_expand = no_expand_value - no_expand_cost

        subsidy_amount = 0.0
        if subsidy_ratio > 0 and w_subsidy != 0.0:
            raw_subsidy = cost * subsidy_ratio * w_subsidy
            annual_income = _safe_float(agent.get("annual_income_rmb"), np.nan)
            is_low_income = (not pd.isna(annual_income)) and annual_income < low_income_threshold
            subsidy_amount = raw_subsidy if (not low_income_only or is_low_income) else 0.0
        utility = (utility_expand if chosen_ext > 0 else utility_no_expand) + subsidy_amount
        utilities.append(float(utility))
        subsidy_amounts.append(float(subsidy_amount))

        annual_income = _safe_float(agent.get("annual_income_rmb"), np.nan)
        if not pd.isna(annual_income) and annual_income < low_income_threshold:
            low_income_utilities.append(float(utility))

    utility_arr = np.asarray(utilities, dtype=float)
    resident_mean_utility = float(np.mean(utility_arr)) if utility_arr.size else np.nan
    utility_std = float(np.std(utility_arr)) if utility_arr.size else np.nan
    utility_gini = _phase2_gini(utility_arr)
    low_income_mean_utility = float(np.mean(low_income_utilities)) if low_income_utilities else resident_mean_utility

    subsidy_total_cost = float(np.sum(subsidy_amounts)) if subsidy_amounts else 0.0
    if subsidy_total_cost > 0 and not pd.isna(total_existing_area) and sum(orig_areas) > 0:
        # Raw logs often store representative residents rather than every household.
        # Scale subsidy from the logged representatives to the community floor area.
        subsidy_total_cost = subsidy_total_cost * float(total_existing_area) / float(np.sum(orig_areas))

    return {
        "final_agree_ratio": final_agree_ratio,
        "extension_ratio_final": extension_ratio,
        "cash_subsidy_ratio_final": subsidy_ratio,
        "developer_profit": developer_profit,
        "developer_profit_rate": developer_profit_rate,
        "resident_mean_utility": resident_mean_utility,
        "low_income_mean_utility": low_income_mean_utility,
        "utility_std": utility_std,
        "utility_gini": utility_gini,
        "subsidy_total_cost": subsidy_total_cost,
    }


def _phase2_metric_value(community_result: dict[str, Any], computed: dict[str, Any], key: str, fallback: Any = np.nan) -> float:
    value = community_result.get(key, np.nan) if isinstance(community_result, dict) else np.nan
    if not pd.isna(_safe_float(value, np.nan)):
        return _safe_float(value, np.nan)
    value = computed.get(key, fallback) if isinstance(computed, dict) else fallback
    return _safe_float(value, fallback)

def _load_negotiation_logs_as_phase2_results(phase2_root: str) -> pd.DataFrame:
    root = Path(_resolve_app_path(phase2_root))
    if not root.exists():
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for log_path in sorted(root.rglob("negotiation_log_*.json"), key=lambda p: (p.stat().st_mtime, str(p))):
        try:
            log_data = _load_json(str(log_path.resolve()))
        except Exception:
            continue
        final_metrics = log_data.get("final_metrics", {}) or {}
        final_policy = log_data.get("final_policy", {}) or {}
        planner = final_policy.get("planner", {}) or {}
        developer = final_policy.get("developer", {}) or {}
        community_result_path = log_path.parent / "community_result.json"
        community_result: dict[str, Any] = {}
        if community_result_path.exists():
            try:
                loaded_result = _load_json(str(community_result_path.resolve()))
                if isinstance(loaded_result, dict):
                    community_result = loaded_result
            except Exception:
                community_result = {}
        run_dir = _phase2_log_run_dir(log_path, root)
        has_summary_csv = _phase2_log_has_own_summary_csv(log_path, root)
        run_cfg = _config_for_log_path(log_path, root)
        config_extension_cap = _safe_float(run_cfg.get("max_extension_ratio"), np.nan) if run_cfg else np.nan
        config_subsidy_cap = _safe_float(run_cfg.get("cash_subsidy_cap"), np.nan) if run_cfg else np.nan
        fallback_rule_id = _rule_id_from_log_path(log_path)
        config_rule_id = _phase2_config_rule_id(run_cfg, fallback_rule_id)
        config_rule_content = _phase2_config_rule_content(run_cfg, config_extension_cap, config_subsidy_cap)
        community_name = _normalize_community_name(
            _strip_str(log_data.get("community_info", {}).get("name")) or log_path.parent.name.replace("sim_", "")
        )
        computed_objectives = _phase2_compute_objectives_from_log(log_data, log_path, root, run_cfg)
        final_agree_ratio = _phase2_metric_value(community_result, computed_objectives, "final_agree_ratio", final_metrics.get("final_agree_ratio"))
        threshold = _safe_float(
            community_result.get("threshold", log_data.get("community_info", {}).get("required_agree_ratio")),
            0.0,
        )
        subsidy_ratio = _phase2_metric_value(community_result, computed_objectives, "cash_subsidy_ratio_final", planner.get("cash_subsidy_ratio"))
        extension_ratio = _phase2_metric_value(community_result, computed_objectives, "extension_ratio_final", planner.get("extension_ratio"))
        rows.append(
            {
                "rule_id": config_rule_id,
                "source_rule_id": fallback_rule_id,
                "rule_content": config_rule_content,
                "extension_cap": config_extension_cap,
                "subsidy_cap": config_subsidy_cap,
                "planner_soft_policy_text": _strip_str(run_cfg.get("planner_soft_policy_text")) if run_cfg else "",
                "community_name": community_name,
                "seed": _seed_from_log_path(log_path),
                "threshold": threshold,
                "is_success": _safe_float(community_result.get("is_success"), 1.0 if not pd.isna(final_agree_ratio) and final_agree_ratio >= threshold else 0.0),
                "final_agree_ratio": final_agree_ratio,
                "avg_extension_ratio": extension_ratio,
                "avg_subsidy_ratio": subsidy_ratio,
                "extension_ratio_final": extension_ratio,
                "cash_subsidy_ratio_final": subsidy_ratio,
                "developer_profit": _phase2_metric_value(community_result, computed_objectives, "developer_profit", final_metrics.get("final_profit")),
                "developer_profit_rate": _phase2_metric_value(community_result, computed_objectives, "developer_profit_rate", final_metrics.get("final_profit_rate")),
                "resident_mean_utility": _phase2_metric_value(community_result, computed_objectives, "resident_mean_utility"),
                "low_income_mean_utility": _phase2_metric_value(community_result, computed_objectives, "low_income_mean_utility"),
                "utility_std": _phase2_metric_value(community_result, computed_objectives, "utility_std"),
                "utility_gini": _phase2_metric_value(community_result, computed_objectives, "utility_gini"),
                "subsidy_total_cost": _phase2_metric_value(community_result, computed_objectives, "subsidy_total_cost"),
                "developer_base_price": _safe_float(developer.get("base_price"), np.nan),
                "developer_extension_price": _safe_float(developer.get("extension_price"), np.nan),
                "community_result_path": str(community_result_path.resolve()) if community_result_path.exists() else "",
                "log_path": str(log_path.resolve()),
                "rounds": _safe_int(log_data.get("rounds"), 0),
                "outcome": _strip_str(log_data.get("outcome")) or "unknown",
                "_source_kind": "raw_log",
                "_phase2_source_dir": str(run_dir.resolve()),
                "_has_summary_csv": bool(has_summary_csv),
            }
        )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(["seed", "community_name", "rule_id"]).reset_index(drop=True)


@lru_cache(maxsize=64)
def _load_json(log_path: str) -> dict[str, Any]:
    with open(log_path, "r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=64)
def _index_phase2_logs(phase2_root: str, rule_id: str) -> dict[str, list[dict[str, str]]]:
    """Index raw negotiation logs independently from summary CSV files."""
    index: dict[str, list[dict[str, str]]] = {}
    log_df = _load_negotiation_logs_as_phase2_results(phase2_root)
    if log_df.empty or "log_path" not in log_df.columns:
        return index

    annotated = _annotate_phase2_policy_groups(log_df)
    filter_col = "policy_rule_id" if "policy_rule_id" in annotated.columns else "rule_id"
    if filter_col not in annotated.columns:
        return index
    filtered = annotated.loc[annotated[filter_col].astype(str) == str(rule_id)].copy()
    if filtered.empty and "rule_id" in annotated.columns:
        filtered = annotated.loc[annotated["rule_id"].astype(str) == str(rule_id)].copy()
    if filtered.empty:
        return index

    for row in filtered.itertuples(index=False):
        log_path = getattr(row, "log_path", None)
        if not log_path:
            continue
        community_name = _normalize_community_name(getattr(row, "community_name", ""))
        if not community_name:
            continue
        seed = str(getattr(row, "seed", "") or _seed_from_log_path(Path(log_path)))
        item = {
            "seed": seed,
            "log_path": str(log_path),
        }
        community_result_path = _strip_str(getattr(row, "community_result_path", ""))
        if community_result_path:
            item["community_result_path"] = community_result_path
        index.setdefault(community_name, []).append(item)

    for community_name in index:
        deduped: dict[str, dict[str, str]] = {}
        for item in index[community_name]:
            deduped[str(item["seed"])] = item
        index[community_name] = sorted(
            deduped.values(),
            key=lambda item: int(item["seed"]) if str(item["seed"]).isdigit() else str(item["seed"]),
        )
    return index


@lru_cache(maxsize=64)
def _available_phase2_seeds(phase2_root: str, rule_id: str) -> tuple[str, ...]:
    seeds: set[str] = set()
    results_df = _load_phase2_community_results(phase2_root)
    if not results_df.empty and "seed" in results_df.columns:
        annotated = _annotate_phase2_policy_groups(results_df)
        filter_col = "policy_rule_id" if "policy_rule_id" in annotated.columns else "rule_id"
        if filter_col in annotated.columns:
            seeds.update(
                annotated.loc[annotated[filter_col].astype(str) == str(rule_id), "seed"]
                .dropna()
                .astype(str)
                .tolist()
            )

    for candidates in _index_phase2_logs(phase2_root, rule_id).values():
        seeds.update(str(item.get("seed", "")) for item in candidates if str(item.get("seed", "")))

    return tuple(sorted(seeds, key=lambda item: int(item) if str(item).isdigit() else str(item)))


@lru_cache(maxsize=128)
def _load_phase2_seed_results(phase2_root: str, rule_id: str, seed: str) -> pd.DataFrame:
    seed_dir = Path(phase2_root) / rule_id / f"seed_{seed}"
    rows: list[dict[str, Any]] = []
    if not seed_dir.exists():
        results_df = _load_phase2_community_results(phase2_root)
        if results_df.empty or "rule_id" not in results_df.columns or "seed" not in results_df.columns:
            return pd.DataFrame()
        filtered = results_df.loc[
            (_annotate_phase2_policy_groups(results_df).pipe(lambda d: d["policy_rule_id"].astype(str) == str(rule_id) if "policy_rule_id" in d.columns else d["rule_id"].astype(str) == str(rule_id))) & (results_df["seed"].astype(str) == str(seed))
        ].copy()
        return filtered.sort_values("community_name").reset_index(drop=True) if not filtered.empty else pd.DataFrame()

    for sim_dir in sorted(seed_dir.glob("sim_*")):
        result_path = sim_dir / "community_result.json"
        if not result_path.exists():
            continue
        result_data = _load_json(str(result_path.resolve()))
        log_candidates = sorted(sim_dir.glob("negotiation_log_*.json"))
        latest_log = str(log_candidates[-1].resolve()) if log_candidates else None
        community_name = _normalize_community_name(
            _strip_str(result_data.get("community_name")) or sim_dir.name.replace("sim_", "")
        )
        rows.append(
            {
                "community_name": community_name,
                "seed": str(result_data.get("seed", seed)),
                "threshold": _safe_float(result_data.get("threshold"), np.nan),
                "is_success": _safe_float(result_data.get("is_success"), np.nan),
                "final_agree_ratio": _safe_float(result_data.get("final_agree_ratio"), np.nan),
                "avg_extension_ratio": _safe_float(result_data.get("extension_ratio_final"), np.nan),
                "avg_subsidy_ratio": _safe_float(result_data.get("cash_subsidy_ratio_final"), np.nan),
                "developer_profit": _safe_float(result_data.get("developer_profit"), np.nan),
                "developer_profit_rate": _safe_float(result_data.get("developer_profit_rate"), np.nan),
                "resident_mean_utility": _safe_float(result_data.get("resident_mean_utility"), np.nan),
                "low_income_mean_utility": _safe_float(result_data.get("low_income_mean_utility"), np.nan),
                "utility_std": _safe_float(result_data.get("utility_std"), np.nan),
                "utility_gini": _safe_float(result_data.get("utility_gini"), np.nan),
                "subsidy_total_cost": _safe_float(result_data.get("subsidy_total_cost"), np.nan),
                "community_result_path": str(result_path.resolve()),
                "log_path": latest_log,
            }
        )

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("community_name").reset_index(drop=True)


def _load_template_config() -> dict[str, Any]:
    with open(DEFAULT_TEMPLATE_CONFIG, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _default_community_csv() -> str:
    if DEFAULT_COMMUNITY_CSV.exists():
        return str(DEFAULT_COMMUNITY_CSV.resolve())
    configured = _load_template_config().get("community_csv", ROOT / "community_example.csv")
    return str(Path(configured).resolve())


def _default_agent_csv() -> str:
    return str(
        Path(
            _load_template_config().get(
                "resident_csv",
                ROOT / "data" / "agents_by_community" / "community_representatives_list.csv",
            )
        ).resolve()
    )


def _default_all_agents_csv() -> str:
    return str(
        Path(
            _load_template_config().get(
                "all_agents_path",
                ROOT / "data" / "agents_by_community" / "ALL_agents.csv",
            )
        ).resolve()
    )


def _default_model_name() -> str:
    return _first_non_empty(load_local_api_defaults().get("model"), _load_template_config().get("llm_name"), "gpt-4o-mini")


def _default_llm_base_url() -> str:
    return _first_non_empty(
        load_local_api_defaults().get("base_url"),
        DEFAULT_API_BASE_URL,
    )


def _field_chip_markup(field_pairs: list[tuple[str, str]]) -> str:
    return "".join(
        f'<span class="field-chip"><span class="field-chip-label">{html.escape(label)}</span></span>'
        for code, label in field_pairs
    )


def _required_upload_data_markup() -> str:
    return f"""
    <div class="required-data-card">
      <div class="required-data-grid">
        <div class="required-data-group">
          <div class="required-data-group-title">Population Synthesis Fields</div>
          <div class="field-chip-row">{_field_chip_markup(COMMUNITY_POPULATION_FIELD_LABELS)}</div>
        </div>
        <div class="required-data-group">
          <div class="required-data-group-title">Simulation Core Fields</div>
          <div class="field-chip-row">{_field_chip_markup(COMMUNITY_SIMULATION_FIELD_LABELS)}</div>
        </div>
      </div>
    </div>
    """


def _ensure_run_template_excel() -> Path:
    template_path = TEMPLATE_DIR / "community_population_template.xlsx"
    if template_path.exists():
        return template_path

    ordered_columns = [code for code, _ in COMMUNITY_POPULATION_FIELD_LABELS] + [
        code for code, _ in COMMUNITY_SIMULATION_FIELD_LABELS
    ]
    sample_row = {column: "" for column in ordered_columns}
    sample_row["小区"] = "Example Community A"
    template_df = pd.DataFrame([sample_row], columns=ordered_columns)
    template_df.to_excel(template_path, index=False)
    return template_path


def _run_template_download_markup() -> str:
    template_url = _file_url(str(_ensure_run_template_excel()))
    return f"""
    <div class="template-download-row">
      <div class="template-download-copy">Template Excel</div>
      <a class="template-download-button" href="{html.escape(template_url or '#')}" download>Download Template Excel</a>
    </div>
    """


def _run_workflow_markup() -> str:
    return """
    <div class="run-workflow-shell">
      <div class="workflow-step is-active"><span class="workflow-step-index">1</span><span class="workflow-step-title">Input</span></div>
      <div class="workflow-step is-active"><span class="workflow-step-index">2</span><span class="workflow-step-title">Validate</span></div>
      <div class="workflow-step"><span class="workflow-step-index">3</span><span class="workflow-step-title">Configure & Launch</span></div>
    </div>
    """


def _run_step_intro(step_number: int, title: str, description: str | None = None) -> str:
    copy_html = f'<div class="section-copy">{html.escape(description)}</div>' if _strip_str(description) else ""
    return f"""
    <div class="section-head compact step-head">
      <div class="step-kicker">Step {step_number}</div>
      <div class="section-title">{html.escape(title)}</div>
      {copy_html}
    </div>
    """


def _system_current_year() -> int:
    return int(datetime.now().year)


def _agreement_visibility_updates(mode: str | None):
    mode_value = _strip_str(mode) or "by_build_year"
    fixed_visible = mode_value == "fixed"
    stepped_visible = mode_value == "by_build_year"
    return (
        gr.update(visible=fixed_visible),
        gr.update(value=_system_current_year(), visible=False),
        gr.update(visible=stepped_visible),
    )


def _normalize_selected_utility_categories(selected_categories: Any = None) -> list[str]:
    if isinstance(selected_categories, dict):
        raw_values = [key for key, enabled in selected_categories.items() if enabled]
    elif isinstance(selected_categories, (list, tuple, set)):
        raw_values = [str(value) for value in selected_categories]
    elif _strip_str(selected_categories):
        raw_values = [str(selected_categories)]
    else:
        raw_values = list(DEFAULT_SELECTED_UTILITY_CATEGORIES)

    normalized: list[str] = []
    for category in DEFAULT_SELECTED_UTILITY_CATEGORIES:
        if category in raw_values and category not in normalized:
            normalized.append(category)
    for category in raw_values:
        if category in UTILITY_CATEGORY_DEFS and category not in normalized:
            normalized.append(category)
    return normalized


def _normalize_component_selection(value: Any) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if _strip_str(item)]
    if _strip_str(value):
        return [str(value)]
    return []


def _slugify_utility_key(value: Any) -> str:
    slug = re.sub(r"[^a-z0-9_]+", "_", _strip_str(value).lower()).strip("_")
    return slug or f"custom_field_{uuid.uuid4().hex[:8]}"


def _default_configured_utility_fields(selected_categories: Any = None) -> list[dict[str, Any]]:
    categories = set(_normalize_selected_utility_categories(selected_categories))
    fields: list[dict[str, Any]] = []
    for field in UTILITY_FIELD_DEFS:
        if field.get("category") not in categories:
            continue
        fields.append(
            {
                "key": field["key"],
                "label": field["label"],
                "agent": field["agent"],
                "category": field["category"],
                "direction": field["direction"],
                "builtin": True,
                "enabled": bool(field.get("enabled", True)),
                "is_overridden": False,
                "value_mode": field.get("value_mode", "fixed"),
                "fixed_value": field.get("fixed_value"),
                "community_field": field.get("community_field"),
                "description": field.get("description"),
            }
        )
    return fields


def _community_csv_columns_for_path(community_path: str | None) -> list[str]:
    path = _strip_str(community_path) or _default_community_csv()
    if not path:
        return []
    try:
        df = _read_table(path)
    except Exception:
        return []
    return [str(column) for column in df.columns.tolist()]


def _normalize_configured_utility_fields(
    configured_utility_fields: Any,
    selected_categories: Any = None,
) -> list[dict[str, Any]]:
    categories = set(_normalize_selected_utility_categories(selected_categories))
    builtin_defaults = {field["key"]: field for field in _default_configured_utility_fields(categories)}
    normalized_fields: list[dict[str, Any]] = []
    seen_custom_keys: set[str] = set()

    raw_fields = configured_utility_fields if isinstance(configured_utility_fields, list) else []
    builtin_updates = {field.get("key"): field for field in raw_fields if isinstance(field, dict) and field.get("builtin")}

    for key, default_field in builtin_defaults.items():
        merged = {**default_field}
        update = builtin_updates.get(key) or {}
        is_overridden = bool(update.get("is_overridden", False))
        merged.update(
            {
                "enabled": bool(update.get("enabled", default_field["enabled"])),
                "is_overridden": is_overridden,
                "value_mode": (update.get("value_mode", default_field["value_mode"]) if is_overridden else default_field["value_mode"]) or "fixed",
                "fixed_value": update.get("fixed_value", default_field["fixed_value"]) if is_overridden else default_field["fixed_value"],
                "community_field": update.get("community_field", default_field["community_field"]) if is_overridden else default_field["community_field"],
                "description": update.get("description", default_field.get("description")) if is_overridden else default_field.get("description"),
            }
        )
        normalized_fields.append(merged)

    for field in raw_fields:
        if not isinstance(field, dict) or field.get("builtin"):
            continue
        category = _strip_str(field.get("category") or field.get("custom_category") or "custom") or "custom"
        if category != "custom" and category not in categories:
            continue
        custom_key = _slugify_utility_key(field.get("custom_key") or field.get("key") or field.get("label"))
        if custom_key in builtin_defaults or custom_key in seen_custom_keys:
            raise ValueError(f"Duplicate custom utility field key: {custom_key}")
        seen_custom_keys.add(custom_key)
        normalized_fields.append(
            {
                "key": custom_key,
                "label": _strip_str(field.get("label") or field.get("custom_label") or custom_key),
                "custom_label": _strip_str(field.get("custom_label") or field.get("label") or custom_key),
                "custom_key": custom_key,
                "agent": _strip_str(field.get("agent") or "resident") or "resident",
                "category": category,
                "direction": _strip_str(field.get("direction") or "neutral") or "neutral",
                "builtin": False,
                "enabled": bool(field.get("enabled", True)),
                "is_overridden": bool(field.get("is_overridden", True)),
                "value_mode": _strip_str(field.get("value_mode") or "fixed") or "fixed",
                "fixed_value": field.get("fixed_value"),
                "community_field": _strip_str(field.get("community_field")) or None,
                "description": _strip_str(field.get("description")) or None,
                "impact_description": _strip_str(field.get("impact_description")) or None,
            }
        )
    return normalized_fields


def _validate_configured_utility_fields(
    configured_utility_fields: Any,
    community_df: pd.DataFrame | None,
    selected_categories: Any = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    normalized_fields = _normalize_configured_utility_fields(configured_utility_fields, selected_categories)
    community_columns = [str(column) for column in community_df.columns.tolist()] if community_df is not None else []
    errors: list[str] = []
    for field in normalized_fields:
        if not field.get("enabled", True):
            continue
        mode = _strip_str(field.get("value_mode") or "fixed") or "fixed"
        if mode == "fixed":
            try:
                value = field.get("fixed_value")
                if value is None or (isinstance(value, str) and not _strip_str(value)):
                    raise ValueError
                field["fixed_value"] = float(value)
            except Exception:
                errors.append(f"{field['label']}: fixed mode requires a numeric fixed value.")
        elif mode == "community_field":
            community_field = _strip_str(field.get("community_field"))
            if not community_field:
                errors.append(f"{field['label']}: community-field mode requires a selected CSV field.")
                continue
            if community_field not in community_columns:
                errors.append(f"{field['label']}: community field '{community_field}' does not exist in the active community CSV.")
                continue
            if community_df is not None:
                series = pd.to_numeric(community_df[community_field], errors="coerce")
                if series.isna().any():
                    errors.append(f"{field['label']}: community field '{community_field}' contains missing or non-numeric values.")
        else:
            errors.append(f"{field['label']}: unsupported value mode '{mode}'.")
    if errors:
        raise ValueError("\n".join(errors))
    return normalized_fields, community_columns


def _compute_value_flow_state(
    selected_categories: Any = None,
    configured_utility_fields: Any = None,
    community_columns: list[str] | None = None,
    planner_components: Any = None,
    developer_components: Any = None,
    resident_components: Any = None,
) -> dict[str, Any]:
    categories = _normalize_selected_utility_categories(selected_categories)
    fields = _normalize_configured_utility_fields(configured_utility_fields, categories)
    impact_specs = {
        "inflow": ("+", "Inflow", "inflow"),
        "outflow": ("−", "Outflow", "outflow"),
        "input": ("●", "Input", "input"),
        "transfer": ("↔", "Transfer", "transfer"),
        "neutral": ("—", "Neutral", "neutral"),
    }

    planner_options: list[str] = []
    developer_options: list[str] = []
    resident_options: list[str] = []

    def _append_unique(target: list[str], values: list[str]) -> None:
        for item in values:
            if item not in target:
                target.append(item)

    for field in fields:
        if not field.get("enabled", True):
            continue
        agent = field.get("agent")
        if agent == "planner":
            _append_unique(planner_options, [field["key"]])
        elif agent == "developer":
            _append_unique(developer_options, [field["key"]])
        elif agent == "resident":
            _append_unique(resident_options, [field["key"]])

    planner_selected = _normalize_component_selection(planner_components)
    developer_selected = _normalize_component_selection(developer_components)
    resident_selected = _normalize_component_selection(resident_components)

    planner_values = [value for value in (planner_selected if planner_selected is not None else planner_options) if value in planner_options]
    developer_values = [value for value in (developer_selected if developer_selected is not None else developer_options) if value in developer_options]
    resident_values = [value for value in (resident_selected if resident_selected is not None else resident_options) if value in resident_options]

    rows_html = []
    grouped_fields: dict[str, list[dict[str, Any]]] = {}
    for field in fields:
        if not field.get("enabled", True):
            continue
        grouped_fields.setdefault(field.get("category") or "custom", []).append(field)

    for category in [*categories, "custom"]:
        category_fields = grouped_fields.get(category, [])
        if not category_fields:
            continue
        rows_html.append(
            f'<tr><td class="flow-empty-cell" colspan="4" style="text-align:left;font-weight:700;background:#f8fafc;">{html.escape((UTILITY_CATEGORY_DEFS.get(category, {}).get("label") if category != "custom" else "Custom"))}</td></tr>'
        )
        for field in category_fields:
            cells = []
            for actor in ["planner", "developer", "resident"]:
                direction = field.get("direction", "neutral") if field.get("agent") == actor else "neutral"
                symbol, label, tone = impact_specs.get(direction, impact_specs["neutral"])
                cells.append(
                    f'<td><span class="flow-pill {tone}"><span class="flow-pill-symbol">{symbol}</span><span>{html.escape(label)}</span></span></td>'
                )
            source_label = (
                (
                    f"Default · {_format_number(field.get('fixed_value'))}"
                    if (field.get("value_mode") or "fixed") == "fixed"
                    else f"Default · {html.escape(_strip_str(field.get('community_field')) or 'N/A')}"
                )
                if field.get("builtin") and not field.get("is_overridden", False)
                else (
                    f"Fixed · {_format_number(field.get('fixed_value'))}"
                    if (field.get("value_mode") or "fixed") == "fixed"
                    else f"Community field · {html.escape(_strip_str(field.get('community_field')) or 'N/A')}"
                )
            )
            rows_html.append(
                f"""
                <tr>
                  <td class="flow-factor-cell">
                    <span class="flow-factor-dot {'outflow' if field.get('direction') == 'outflow' else ('inflow' if field.get('direction') == 'inflow' else 'neutral')}"></span>
                    <span>{html.escape(field['label'])}</span>
                    <div class="value-flow-subtitle" style="font-size:11px;">{source_label}</div>
                  </td>
                  {''.join(cells)}
                </tr>
                """
            )
    if not rows_html:
        rows_html.append(
            """
            <tr>
              <td class="flow-empty-cell" colspan="4">No utility fields configured.</td>
            </tr>
            """
        )

    panel_html = f"""
    <div class="value-flow-card">
      <div class="value-flow-head">
        <div class="value-flow-title-row">
          <div class="value-flow-title">Utility Setting</div>
          <div class="value-flow-subtitle">Configured from utility categories and field sources</div>
        </div>
        <div class="value-flow-meta">{len([field for field in fields if field.get('enabled', True)])} active fields · {len(community_columns or [])} community columns</div>
      </div>
      <div class="value-flow-table-shell">
        <table class="value-flow-table">
          <thead>
            <tr>
              <th>Factor</th>
              <th>Planner</th>
              <th>Developer</th>
              <th>Resident</th>
            </tr>
          </thead>
          <tbody>
            {''.join(rows_html)}
          </tbody>
        </table>
      </div>
    </div>
    """
    return {
        "selected_utility_categories": categories,
        "configured_utility_fields": fields,
        "community_csv_columns": list(community_columns or []),
        "value_flow_model_html": panel_html,
        "planner_components": planner_values,
        "developer_components": developer_values,
        "resident_components": resident_values,
        "planner_options": planner_options,
        "developer_options": developer_options,
        "resident_options": resident_options,
    }


def _derive_value_flow_model(
    community_df: pd.DataFrame | None,
    selected_categories: Any = None,
    planner_components: Any = None,
    developer_components: Any = None,
    resident_components: Any = None,
):
    state = _compute_value_flow_state(
        selected_categories=selected_categories,
        planner_components=planner_components,
        developer_components=developer_components,
        resident_components=resident_components,
    )
    return (
        state["value_flow_model_html"],
        state["planner_components"],
        state["developer_components"],
        state["resident_components"],
    )


def _run_preflight_markup(
    target_community: str | None,
    model_name: str | None,
    rounds_num: Any,
    agreement_mode: str | None,
    max_extension_ratio: Any,
    cash_subsidy_cap: Any,
    developer_min_profit_rate: Any,
    output_dir: str | None,
    generated_bundle_state: dict[str, Any] | None,
    planner_soft_policy_text: str | None = None,
) -> str:
    soft_policy_text = _strip_str(planner_soft_policy_text)
    items = [
        ("Target", _strip_str(target_community) or "All Communities"),
        ("Model", _strip_str(model_name) or _default_model_name()),
        ("Rounds", str(_safe_int(rounds_num, 8))),
        ("Agreement", "Fixed" if _strip_str(agreement_mode) == "fixed" else "By build year"),
        ("Extension cap", _format_ratio(_safe_float(max_extension_ratio, 0.3))),
        ("Subsidy cap", _format_ratio(_safe_float(cash_subsidy_cap, 0.1))),
        ("Min profit", _format_ratio(_safe_float(developer_min_profit_rate, 0.0))),
        ("Policy text", "Custom" if soft_policy_text else "None"),
    ]
    item_html = "".join(
        f'<div class="launch-summary-item" title="{html.escape(f"{label}: {value}")}"><span class="launch-summary-key">{html.escape(label)}:</span><span class="launch-summary-value">{html.escape(value)}</span></div>'
        for label, value in items
    )
    return f"""
    <div class="launch-summary">
      <div class="launch-summary-grid">{item_html}</div>
    </div>
    """


def _sanitize_filename(name: Any) -> str:
    return re.sub(r"[\\/:*?\"<>|]", "_", str(name)).strip() or "unknown"


def _truncnorm(mu: float, sig: float, lo: float, hi: float) -> float:
    return float(np.clip(np.random.normal(mu, sig), lo, hi))


def _interp_income(rank_value: float) -> float:
    rank_value = float(np.clip(rank_value, 0.10, 0.90))
    for (p1, y1), (p2, y2) in zip(INCOME_PTS, INCOME_PTS[1:]):
        if p1 <= rank_value <= p2:
            ratio = (rank_value - p1) / (p2 - p1)
            return y1 + ratio * (y2 - y1)
    return INCOME_PTS[-1][1]


def _age_factor(age: int) -> float:
    if age < 15:
        return 0.0
    if age <= 24:
        return 0.75
    if age <= 34:
        return 0.95
    if age <= 54:
        return 1.10
    if age <= 59:
        return 1.00
    if age <= 64:
        return 0.75
    return 0.55


def _household_size_from_rank(rank_value: float, unit_type: str) -> int:
    lo, hi = UNIT_HH_RANGE[unit_type]
    return int(np.clip(lo + round(rank_value * (hi - lo)), lo, hi))


def _normalize_agreement_rule_rows(raw_rows: Any) -> list[dict[str, Any]]:
    if isinstance(raw_rows, pd.DataFrame):
        df = raw_rows.copy()
    else:
        try:
            df = pd.DataFrame(raw_rows or [], columns=["max_age", "ratio"])
        except Exception:
            df = pd.DataFrame(columns=["max_age", "ratio"])
    if df.empty:
        df = DEFAULT_AGREEMENT_RULE_ROWS.copy()
    if "max_age" not in df.columns:
        df["max_age"] = np.nan
    if "ratio" not in df.columns:
        df["ratio"] = np.nan
    normalized: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        max_age = row.get("max_age")
        ratio = _safe_float(row.get("ratio"), np.nan)
        if pd.isna(ratio):
            continue
        normalized.append(
            {
                "max_age": None if pd.isna(max_age) or _strip_str(max_age).lower() in {"", "none", "null", "nan"} else int(float(max_age)),
                "ratio": float(ratio),
            }
        )
    return normalized or DEFAULT_AGREEMENT_RULE_ROWS.to_dict(orient="records")


def _normalize_unit_type(value: Any) -> str:
    token = _strip_str(value).upper()
    if token in UNIT_SHARE:
        return token
    if token.startswith("SMALL"):
        return "S"
    if token.startswith("MED"):
        return "M"
    return "L"


def _build_role_prompt(agent_row: dict[str, Any]) -> str:
    role_map = {
        "resident": "owner-occupier",
        "renter": "tenant representative",
        "owner_occupier": "owner-occupier",
        "absentee_owner_vacant": "vacant owner",
    }
    agent_role = _strip_str(agent_row.get("agent_role")) or _strip_str(agent_row.get("tenure")) or "resident"
    role_name = role_map.get(agent_role, "owner representative")
    age = _safe_int(agent_row.get("age"), 45)
    income = _format_currency(agent_row.get("annual_income_rmb"))
    area = round(_safe_float(agent_row.get("unit_size_sqm"), 0.0), 1)
    return f"You are a {age}-year-old {role_name} with an annual personal income of about {income} RMB and a current housing area of about {area} sqm."


def _estimate_generation_summary(
    community_df: pd.DataFrame,
    residents_per_household: float,
    representatives_per_community: int,
) -> tuple[int, int, int]:
    if community_df.empty or "户数" not in community_df.columns:
        return 0, 0, 0
    households = int(pd.to_numeric(community_df["户数"], errors="coerce").fillna(0).sum())
    communities = len(_community_list_from_data(community_df=community_df))
    residents = int(round(households * float(residents_per_household)))
    representatives = int(communities * int(representatives_per_community))
    return households, residents, representatives



def _select_community_representatives_fast(
    community_agents: pd.DataFrame,
    representatives_per_community: int,
    hardship_quantile: float,
    seed: int = 42,
) -> pd.DataFrame:
    community_agents = community_agents.copy()
    n_agents = len(community_agents)
    k_reps = max(1, min(int(representatives_per_community), n_agents))

    if n_agents <= k_reps:
        community_agents["ideal_weight"] = 1.0
        community_agents["cluster"] = range(n_agents)
        community_agents["final_voting_weight"] = 1.0
        return community_agents

    rng = np.random.default_rng(seed)
    numeric_features = [
        "age",
        "annual_income_rmb",
        "unit_size_sqm",
        "household_size",
        "household_monthly_income_rmb",
    ]

    feature_frame = pd.DataFrame(index=community_agents.index)
    for col in numeric_features:
        values = pd.to_numeric(community_agents.get(col), errors="coerce")
        if values.isna().all():
            values = pd.Series(0.0, index=community_agents.index)
        else:
            values = values.fillna(values.median())
        std = float(values.std(ddof=0))
        feature_frame[col] = 0.0 if std <= 0 or not np.isfinite(std) else (values - float(values.mean())) / std


    for col in ["tenure", "unit_type"]:
        codes = pd.Categorical(community_agents.get(col, pd.Series("", index=community_agents.index)).fillna("").astype(str)).codes
        values = pd.Series(codes, index=community_agents.index, dtype="float64")
        std = float(values.std(ddof=0))
        feature_frame[col] = 0.0 if std <= 0 or not np.isfinite(std) else (values - float(values.mean())) / std


    med = feature_frame.median(axis=0)
    distance_to_median = ((feature_frame - med) ** 2).sum(axis=1).pow(0.5)
    community_agents["ideal_weight"] = (1.0 / (1.0 + distance_to_median)).astype(float)

    adult_mask = pd.to_numeric(community_agents.get("age"), errors="coerce").fillna(0) >= 20
    candidate_df = community_agents[adult_mask].copy()
    if candidate_df.empty:
        candidate_df = community_agents.copy()



    strat_score = pd.Series(0.0, index=candidate_df.index)
    for col, weight in [("annual_income_rmb", 0.45), ("age", 0.25), ("unit_size_sqm", 0.20), ("household_size", 0.10)]:
        values = pd.to_numeric(candidate_df.get(col), errors="coerce")
        if values.notna().sum() > 1:
            strat_score += weight * values.rank(pct=True).fillna(0.5)
        else:
            strat_score += weight * 0.5

    strat_score += pd.Series(rng.random(len(candidate_df)) * 1e-9, index=candidate_df.index)
    candidate_df["_strat_score"] = strat_score

    selected_indices: list[Any] = []
    sorted_candidates = candidate_df.sort_values("_strat_score")
    bins = np.array_split(sorted_candidates.index.to_numpy(), k_reps)
    for cluster_idx, bin_indices in enumerate(bins):
        if len(bin_indices) == 0:
            continue
        bin_df = candidate_df.loc[bin_indices]
        chosen_idx = bin_df["ideal_weight"].idxmax()
        if chosen_idx not in selected_indices:
            selected_indices.append(chosen_idx)

    if len(selected_indices) < k_reps:
        filler = candidate_df.drop(index=selected_indices, errors="ignore").sort_values("ideal_weight", ascending=False)
        selected_indices.extend(list(filler.index[: k_reps - len(selected_indices)]))

    reps_df = community_agents.loc[selected_indices[:k_reps]].copy()
    reps_df["cluster"] = range(len(reps_df))

    eligible_pool = community_agents[adult_mask].copy()
    eligible_pool["household_monthly_income_rmb"] = pd.to_numeric(
        eligible_pool.get("household_monthly_income_rmb"), errors="coerce"
    )
    eligible_pool = eligible_pool.dropna(subset=["household_monthly_income_rmb"])
    if not eligible_pool.empty and not reps_df.empty:
        hardship_threshold = eligible_pool["household_monthly_income_rmb"].quantile(float(hardship_quantile))
        hardship_pool = eligible_pool[eligible_pool["household_monthly_income_rmb"] <= hardship_threshold]
        reps_have_hardship = (
            pd.to_numeric(reps_df.get("household_monthly_income_rmb"), errors="coerce") <= hardship_threshold
        ).any()
        if not reps_have_hardship and not hardship_pool.empty:
            hardship_candidate = hardship_pool.loc[hardship_pool["ideal_weight"].idxmax()]
            if hardship_candidate.get("agent_id") not in set(reps_df.get("agent_id", pd.Series(dtype=str)).astype(str)):
                replace_idx = reps_df["ideal_weight"].idxmin()
                reps_df.loc[replace_idx] = hardship_candidate

    denom = float(pd.to_numeric(reps_df["ideal_weight"], errors="coerce").fillna(0).sum())
    if denom <= 0 or not np.isfinite(denom):
        reps_df["final_voting_weight"] = n_agents / max(len(reps_df), 1)
    else:
        reps_df["final_voting_weight"] = reps_df["ideal_weight"] * (n_agents / denom)
    reps_df = reps_df.drop(columns=["_strat_score"], errors="ignore")
    return reps_df

def _generate_agent_bundle(
    community_df: pd.DataFrame,
    staging_dir: Path,
    residents_per_household: float,
    vacancy_ratio: float,
    representatives_per_community: int,
    hardship_quantile: float,
    seed: int = 42,
) -> tuple[str, str]:
    np.random.seed(seed)
    random.seed(seed)

    community_df = community_df.copy()
    community_df["房价（元/平）"] = pd.to_numeric(community_df["房价（元/平）"], errors="coerce")
    price_median = float(community_df["房价（元/平）"].median()) if not community_df["房价（元/平）"].dropna().empty else 1.0
    price_rank = (
        community_df["房价（元/平）"].rank(pct=True).fillna(0.5).values
        if "房价（元/平）" in community_df.columns
        else np.full(len(community_df), 0.5)
    )

    agent_id = 1
    unit_id = 1
    household_id = 1
    all_agents_frames: list[pd.DataFrame] = []

    for idx, row in community_df.iterrows():
        community_name = _strip_str(row.get("小区")) or f"Community {idx + 1}"
        n_households = max(1, _safe_int(row.get("户数"), 1))
        dominant_type = _normalize_unit_type(row.get("dominant unit type", "M"))
        rent_rate = float(np.clip(_safe_float(row.get("rent_rate"), 0.3), 0.0, 1.0))
        resident_population = max(1, int(round(n_households * float(residents_per_household))))
        community_price = _safe_float(row.get("房价（元/平）"), price_median)
        income_scale = (community_price / max(price_median, 1.0)) ** INCOME_PRICE_ELASTICITY
        income_scale = float(np.clip(income_scale, *INCOME_SCALE_CLIP))

        unit_types: list[str] = []
        for unit_type, share in UNIT_SHARE[dominant_type].items():
            unit_types += [unit_type] * int(round(n_households * share))
        unit_types = (unit_types + [dominant_type] * n_households)[:n_households]
        random.shuffle(unit_types)
        unit_sizes = [float(np.random.uniform(*UNIT_AREA_RANGE[unit_type])) for unit_type in unit_types]

        vacancy_rate = _truncnorm(float(vacancy_ratio), VAC_SIG, VAC_LO, VAC_HI)
        vacant_indices = set(random.sample(range(n_households), int(round(n_households * vacancy_rate))))

        income_rank_by_household: dict[int, float] = {}
        for house_idx in range(n_households):
            if house_idx in vacant_indices:
                continue
            base = {"S": 0.30, "M": 0.55, "L": 0.80}[unit_types[house_idx]]
            income_rank_by_household[house_idx] = float(np.clip(np.random.normal(base, 0.10), 0.05, 0.95))

        household_sizes = [
            0 if house_idx in vacant_indices else _household_size_from_rank(income_rank_by_household[house_idx], unit_types[house_idx])
            for house_idx in range(n_households)
        ]
        age_pool = list(np.random.randint(0, 90, resident_population))
        random.shuffle(age_pool)

        renter_household_incomes: list[float] = []
        for house_idx in range(n_households):
            if house_idx in vacant_indices:
                continue
            if random.random() < rent_rate:
                hh_income = (
                    _interp_income(income_rank_by_household[house_idx])
                    * income_scale
                    * TENURE_FACTOR["renter"]
                    * np.random.lognormal(0, 0.15)
                )
                renter_household_incomes.append(float(hh_income))

        renter_floor = (
            float(np.percentile(renter_household_incomes, 85))
            if renter_household_incomes
            else _interp_income(price_rank[idx]) * income_scale
        )
        high_anchor = _interp_income(min(0.9, float(price_rank[idx]) + 0.25)) * income_scale

        community_agents: list[dict[str, Any]] = []
        for house_idx in range(n_households):
            unit_type = unit_types[house_idx]
            unit_size = unit_sizes[house_idx]
            current_unit_id = f"U{unit_id:09d}"
            unit_id += 1

            if house_idx in vacant_indices:
                annual_income = (
                    max(high_anchor, renter_floor * 1.30)
                    * VACANT_OWNER_PREMIUM
                    * np.random.lognormal(0, VACANT_OWNER_NOISE_SIGMA)
                )
                annual_income = max(annual_income, renter_floor * 1.35)
                monthly_income = annual_income / 12.0
                agent_row = {
                    "community": community_name,
                    "agent_id": f"A{agent_id:09d}",
                    "agent_role": "absentee_owner_vacant",
                    "tenure": "owner_occupier",
                    "live_here": 0,
                    "household_id": "",
                    "household_size": 0,
                    "household_monthly_income_rmb": round(monthly_income, 2),
                    "unit_id": current_unit_id,
                    "unit_type": unit_type,
                    "unit_size_sqm": round(unit_size, 2),
                    "age": int(_truncnorm(OWNER_AGE_MU, OWNER_AGE_SIG, OWNER_AGE_LO, OWNER_AGE_HI)),
                    "annual_income_rmb": round(annual_income, 2),
                }
                agent_row["role_prompt"] = _build_role_prompt(agent_row)
                community_agents.append(agent_row)
                agent_id += 1
                continue

            current_household_id = f"H{household_id:09d}"
            household_id += 1
            hh_size = household_sizes[house_idx]
            tenure = "renter" if random.random() < rent_rate else "owner_occupier"
            household_annual_income = (
                _interp_income(income_rank_by_household[house_idx])
                * income_scale
                * TENURE_FACTOR[tenure]
                * np.random.lognormal(0, 0.15)
            )
            household_monthly_income = household_annual_income / 12.0

            for _ in range(max(1, hh_size)):
                age = age_pool.pop() if age_pool else random.randint(20, 70)
                individual_annual_income = (
                    household_annual_income
                    * _age_factor(age)
                    * np.random.lognormal(0, RESIDENT_NOISE_SIGMA)
                )
                agent_row = {
                    "community": community_name,
                    "agent_id": f"A{agent_id:09d}",
                    "agent_role": "resident",
                    "tenure": tenure,
                    "live_here": 1,
                    "household_id": current_household_id,
                    "household_size": max(1, hh_size),
                    "household_monthly_income_rmb": round(household_monthly_income, 2),
                    "unit_id": current_unit_id,
                    "unit_type": unit_type,
                    "unit_size_sqm": round(unit_size, 2),
                    "age": int(age),
                    "annual_income_rmb": round(individual_annual_income, 2),
                }
                agent_row["role_prompt"] = _build_role_prompt(agent_row)
                community_agents.append(agent_row)
                agent_id += 1

        community_dir = staging_dir / _sanitize_filename(community_name)
        community_dir.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(community_agents).to_csv(community_dir / f"{_sanitize_filename(community_name)}_agents.csv", index=False, encoding="utf-8-sig")
        all_agents_frames.append(pd.DataFrame(community_agents))

    all_agents_df = pd.concat(all_agents_frames, ignore_index=True) if all_agents_frames else pd.DataFrame()
    all_agents_path = staging_dir / "ALL_agents.csv"
    all_agents_df.to_csv(all_agents_path, index=False, encoding="utf-8-sig")

    representatives: list[pd.DataFrame] = []

    for community_name in all_agents_df["community"].dropna().astype(str).unique():
        community_agents = all_agents_df[all_agents_df["community"] == community_name].copy()
        if community_agents.empty:
            continue
        representatives.append(
            _select_community_representatives_fast(
                community_agents,
                representatives_per_community=representatives_per_community,
                hardship_quantile=hardship_quantile,
                seed=seed,
            )
        )

    representatives_df = pd.concat(representatives, ignore_index=True) if representatives else pd.DataFrame()
    representative_path = staging_dir / "community_representatives_list.csv"
    representatives_df.to_csv(representative_path, index=False, encoding="utf-8-sig")
    return str(representative_path), str(all_agents_path)


def _select_representatives_from_all_agents(
    all_agents_df: pd.DataFrame,
    staging_dir: Path,
    representatives_per_community: int,
    hardship_quantile: float,
    seed: int = 42,
) -> str:
    representatives: list[pd.DataFrame] = []
    all_agents_df = all_agents_df.copy()

    for community_name in all_agents_df["community"].dropna().astype(str).unique():
        community_agents = all_agents_df[all_agents_df["community"] == community_name].copy()
        if community_agents.empty:
            continue
        representatives.append(
            _select_community_representatives_fast(
                community_agents,
                representatives_per_community=representatives_per_community,
                hardship_quantile=hardship_quantile,
                seed=seed,
            )
        )

    representatives_df = pd.concat(representatives, ignore_index=True) if representatives else pd.DataFrame()
    representative_path = staging_dir / "community_representatives_list.csv"
    representatives_df.to_csv(representative_path, index=False, encoding="utf-8-sig")
    return str(representative_path)
