import json
import os
import re
import time
import threading
import hashlib
import numpy as np
from openai import OpenAI
import pandas as pd
from datetime import datetime

from .prompts import (
    build_planner_prompt,
    build_developer_prompt,
    build_resident_prompt,
)

_LLM_LOCK = threading.Lock()
_LAST_LLM_CALL = 0.0
_LLM_LOG_LOCK = threading.Lock()


MIN_LLM_INTERVAL = 5.0


def _sanitize_llm_error(err: Exception) -> str:
    text = str(err)
    text = re.sub(r"sk-[A-Za-z0-9_\-.]{4,}", "sk-****", text)
    text = re.sub(
        r"Received API Key\s*=\s*[^,}\n]+",
        "Received API Key = [redacted]",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"Key Hash \(Token\)\s*=\s*[A-Fa-f0-9]{16,}",
        "Key Hash (Token) = [redacted]",
        text,
    )
    return text


def _is_auth_error(err: Exception) -> bool:
    text = str(err).lower()
    return (
        "401" in text
        or "authentication error" in text
        or "invalid proxy server token" in text
        or "token_not_found_in_db" in text
        or "invalid api key" in text
    )


def safe_llm_call(
    client: OpenAI,
    *,
    min_interval_seconds=MIN_LLM_INTERVAL,
    serialize=False,
    **kwargs,
):
    global _LAST_LLM_CALL

    if not serialize:
        return client.chat.completions.create(**kwargs)

    with _LLM_LOCK:
        now = time.time()
        wait = float(min_interval_seconds) - (now - _LAST_LLM_CALL)
        if wait > 0:
            time.sleep(wait)

        resp = client.chat.completions.create(**kwargs)
        _LAST_LLM_CALL = time.time()
        return resp

class llm_agent:

    def __init__(
        self,
        args,
        agent_name: str,
        agent_id: str = None,
        row_data: dict | None = None,
        csv_path=None,
        community_context=None,
        community_name=None,
    ):
        self.args = args
        self.agent_name = agent_name
        self.agent_id = agent_id
        self.llm_name = getattr(args, "llm_name", getattr(args, "model", "gpt-4o-mini"))
        self.csv_path = csv_path
        self.community_context = community_context or ""
        self.community_name = community_name
        self.min_llm_interval = float(getattr(args, "min_llm_interval", MIN_LLM_INTERVAL))
        self.llm_timeout_seconds = float(getattr(args, "llm_timeout_seconds", 30.0))
        self.llm_timeout_retry_attempts = int(getattr(args, "llm_timeout_retry_attempts", 0))
        self.llm_timeout_retry_delay_seconds = float(
            getattr(args, "llm_timeout_retry_delay_seconds", 3.0)
        )
        self.serialize_llm_calls = bool(getattr(args, "serialize_llm_calls", False))

        self.api_key = self._first_non_empty(
            os.environ.get("LLM_API_KEY"),
            os.environ.get("OPENAI_API_KEY"),
            getattr(args, "api_key", None),
        )
        if not self.api_key:
            raise ValueError("LLM API key not found. Set LLM_API_KEY, OPENAI_API_KEY, or api_key in the config.")

        self.llm_base_url = self._first_non_empty(
            os.environ.get("LLM_BASE_URL"),
            os.environ.get("OPENAI_BASE_URL"),
            getattr(args, "llm_base_url", None),
            getattr(args, "base_url", None),
        )
        client_kwargs = {
            "api_key": self.api_key,
            "timeout": self.llm_timeout_seconds,
            "max_retries": 0,
        }
        if self.llm_base_url:
            client_kwargs["base_url"] = self.llm_base_url
        self.client = OpenAI(**client_kwargs)

        self.role_prompt = self._prepare_role_prompt(row_data)

        base_log_dir = getattr(
            self.args,
            "log_dir",
            getattr(self.args, "base_log_dir", "./log")
        )
        run_timestamp = getattr(self.args, "run_timestamp", "unknown_run")

        safe_community = (
            str(self.community_name or "unknown_community")
            .strip()
            .replace("/", "_")
            .replace(" ", "_")
        )

        run_log_dir = os.path.join(
            base_log_dir,
            safe_community,
            run_timestamp
        )
        os.makedirs(run_log_dir, exist_ok=True)

        self.log_path = os.path.join(
            run_log_dir,
            f"llm_raw_{agent_name}.jsonl"
        )
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)

        if not os.path.exists(self.log_path):
            with open(self.log_path, "w", encoding="utf-8"):
                pass


        self._action_cache = {}
        self._last_valid_action = None
        self._load_action_cache_from_log()

    @staticmethod
    def _first_non_empty(*values):
        for value in values:
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
        return None

    def _make_action_cache_key(self, obs_np: np.ndarray, prompt: str) -> str:
        obs_list = np.asarray(obs_np, dtype=np.float64).round(6).tolist()
        payload = {
            "agent": self.agent_name,
            "agent_id": self.agent_id,
            "obs": obs_list,
            "prompt": prompt,
        }
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _load_action_cache_from_log(self):
        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except Exception:
                        continue
                    parsed = rec.get("parsed_action", None)
                    obs = rec.get("obs", None)
                    prompt = rec.get("prompt", None)
                    if parsed is None or obs is None or prompt is None:
                        continue
                    try:
                        obs_np = np.asarray(obs, dtype=np.float32)
                        key = self._make_action_cache_key(obs_np, prompt)
                        self._action_cache[key] = parsed
                        self._last_valid_action = self.parse_action(parsed)
                    except Exception:
                        continue
        except FileNotFoundError:
            return


    def _prepare_role_prompt(self, row):
        if row is None:
            return f"You are the {self.agent_name} (ID {self.agent_id})."

        if "role_prompt" in row:
            existing = row.get("role_prompt", None)
            if existing and str(existing).strip() not in ["", "nan"]:
                return str(existing)

        if self.agent_name == "resident":
            ROLE_MAP = {
                "resident": "owner-occupier",
                "landlord": "landlord",
                "absentee_owner_vacant": "vacant owner",
            }
            role_prompt = (
                f"You are a {row.get('age', 'unknown')}-year-old "
                f"{ROLE_MAP.get(str(row.get('agent_role', 'resident')), 'owner')} "
                f"with an annual personal income of about "
                f"{row.get('annual_income_rmb', 'unknown')} RMB and a current "
                f"housing area of about {row.get('unit_size_sqm', 'unknown')} sqm."
            )
            if not bool(getattr(self.args, "llm_generate_role_prompt", False)):
                return role_prompt

            agent_info = {
                "Role": ROLE_MAP.get(str(row.get("agent_role", "resident")), "unknown owner"),
                "Age": row.get("age", "unknown"),
                "Annual personal income": f'{row.get("annual_income_rmb", "unknown")} RMB',
                "Current housing area": f'{row.get("unit_size_sqm")} sqm',
            }
        else:
            role_prompt = f"You are the {self.agent_name} in an urban renewal simulation."
            if not bool(getattr(self.args, "llm_generate_role_prompt", False)):
                return role_prompt

            agent_info = {
                "Role": self.agent_name,
                "Task": row.get("info", "none"),
            }

        input_text = "\n".join([f"{k}: {v}" for k, v in agent_info.items()])

        generate_prompt = f"""
The following text contains information about a person:
{input_text}

Write a brief description in the second person.
Start with "You are..." and do not add extra information.
""".strip()

        try:
            response = self._call_llm_with_timeout_retry(
                model=self.llm_name,
                messages=[{"role": "user", "content": generate_prompt}],
                temperature=0.3,
                timeout=self.llm_timeout_seconds,
            )
            role_prompt = response.choices[0].message.content.strip()
        except Exception:
            role_prompt = f"You are the {self.agent_name} in an urban renewal simulation."

        if self.csv_path:
            try:
                df = pd.read_csv(self.csv_path)
                if "agent_id" in df.columns:
                    if "role_prompt" not in df.columns:
                        df["role_prompt"] = ""
                    mask = df["agent_id"] == row.get("agent_id", self.agent_id)
                    df.loc[mask, "role_prompt"] = role_prompt
                    df.to_csv(self.csv_path, index=False)
            except Exception:
                pass

        return role_prompt

    @staticmethod
    def _is_timeout_error(err: Exception) -> bool:
        msg = str(err).lower()
        return ("timed out" in msg) or ("timeout" in msg)

    def _call_llm_with_timeout_retry(self, **kwargs):
        total_attempts = max(1, 1 + self.llm_timeout_retry_attempts)
        for attempt_idx in range(total_attempts):
            try:
                return safe_llm_call(
                    self.client,
                    min_interval_seconds=self.min_llm_interval,
                    serialize=self.serialize_llm_calls,
                    **kwargs,
                )
            except Exception as e:
                is_timeout = self._is_timeout_error(e)
                is_last_attempt = (attempt_idx >= total_attempts - 1)
                if (not is_timeout) or is_last_attempt:
                    raise

                sleep_s = self.llm_timeout_retry_delay_seconds * (attempt_idx + 1)
                print(
                    f"[LLMPolicy:{self.agent_name}] timeout detected, "
                    f"retrying in {sleep_s:.1f}s "
                    f"(attempt {attempt_idx + 2}/{total_attempts})",
                    flush=True,
                )
                time.sleep(max(0.0, sleep_s))

    def get_action(self, obs_np: np.ndarray) -> np.ndarray:
        prompt = self.build_prompt(obs_np)
        cache_key = self._make_action_cache_key(obs_np, prompt)


        if cache_key in self._action_cache:
            cached_decision = self._action_cache[cache_key]
            action = self.parse_action(cached_decision)
            self._last_valid_action = action.copy()
            self._log_llm_interaction(
                obs_np,
                prompt,
                "[cache hit]",
                cached_decision,
                source="cache",
            )
            print(
                f"[LLMPolicy:{self.agent_name}] cache hit agent_id={self.agent_id}",
                flush=True,
            )
            return action

        try:
            print(
                f"[LLMPolicy:{self.agent_name}] requesting action "
                f"agent_id={self.agent_id} timeout={self.llm_timeout_seconds:.1f}s",
                flush=True,
            )
            response = self._call_llm_with_timeout_retry(
                model=self.llm_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=getattr(self.args, "temperature", 0.2),
                timeout=self.llm_timeout_seconds,
            )

            raw_text = response.choices[0].message.content
            decision = self.extract_json(raw_text)

            self._log_llm_interaction(
                obs_np,
                prompt,
                raw_text,
                decision,
            )

            if decision is None:
                raise ValueError("JSON parse failed")

            self._action_cache[cache_key] = decision
            action = self.parse_action(decision)
            self._last_valid_action = action.copy()
            print(
                f"[LLMPolicy:{self.agent_name}] completed action agent_id={self.agent_id}",
                flush=True,
            )
            return action

        except Exception as e:
            safe_error = _sanitize_llm_error(e)
            if _is_auth_error(e):
                raise RuntimeError(
                    "[LLMPolicy] Authentication failed. The API key was rejected by "
                    f"the configured provider ({self.llm_base_url or 'default OpenAI endpoint'}). "
                    "Set a valid OPENAI_API_KEY/.env.local value or enter a valid key in /run/setup. "
                    f"Provider message: {safe_error}"
                ) from None
            print(f"[LLMPolicy:{self.agent_name}] fallback due to error: {safe_error}", flush=True)
            fallback = self.fallback_action(obs_np)
            self._log_llm_interaction(
                obs_np,
                prompt,
                f"[fallback due to error] {safe_error}",
                self._action_to_decision(fallback),
                source="fallback",
                error=safe_error,
            )
            return fallback


    def _log_llm_interaction(self, obs, prompt, raw_response, parsed_action, source="llm", error=None):
        record = {
            "timestamp": datetime.now().isoformat(),
            "agent": self.agent_name,
            "agent_id": self.agent_id,
            "source": source,
            "obs": obs.tolist(),
            "prompt": prompt,
            "raw_response": raw_response,
            "parsed_action": parsed_action,
        }
        if error:
            record["error"] = error
        with _LLM_LOG_LOCK:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")


    def build_prompt(self, obs_np: np.ndarray) -> str:
        if self.agent_name == "planner":
            return build_planner_prompt(obs_np, self.role_prompt, self.args)
        elif self.agent_name == "developer":
            return build_developer_prompt(obs_np, self.role_prompt, self.args)
        elif self.agent_name == "resident":
            return build_resident_prompt(
                obs_np, self.role_prompt, self.community_context, self.args
            )
        else:
            raise ValueError(f"Unsupported agent_name: {self.agent_name}")


    def parse_action(self, decision: dict) -> np.ndarray:
        if self.agent_name == "planner":
            return np.array(
                [
                    float(decision.get("extension_ratio", 0.3)),
                    float(decision.get("cash_subsidy_ratio", 0.0)),
                ],
                dtype=np.float32,
            )

        elif self.agent_name == "developer":
            return np.array(
                [
                    float(decision.get("base_price", 3800.0)),
                    float(decision.get("extension_price", 4500.0)),
                    float(decision.get("parking_fee", 0.0)),
                    1.0 if decision.get("build_public_service", False) else 0.0,
                ],
                dtype=np.float32,
            )

        elif self.agent_name == "resident":
            return np.array(
                [
                    1.0 if decision.get("agree", False) else 0.0,
                    float(decision.get("chosen_extension_area", 0.0)),
                    1.0 if decision.get("want_parking", False) else 0.0,
                    float(decision.get("expected_base_price", 0.0)),
                    float(decision.get("expected_extension_price", 0.0)),
                    float(decision.get("quoted_base_price", decision.get("expected_base_price", 0.0))),
                    float(decision.get("quoted_extension_price", decision.get("expected_extension_price", 0.0))),
                    float(decision.get("expected_extension_area", decision.get("chosen_extension_area", 0.0))),
                ],
                dtype=np.float32,
            )

        else:
            raise ValueError(f"Unsupported agent_name: {self.agent_name}")

    def _action_to_decision(self, action: np.ndarray) -> dict:
        values = np.asarray(action, dtype=np.float32).tolist()
        if self.agent_name == "planner":
            return {
                "extension_ratio": float(values[0]),
                "cash_subsidy_ratio": float(values[1]),
            }
        if self.agent_name == "developer":
            return {
                "base_price": float(values[0]),
                "extension_price": float(values[1]),
                "parking_fee": float(values[2]),
                "build_public_service": bool(values[3] >= 0.5),
            }
        if self.agent_name == "resident":
            return {
                "agree": bool(values[0] >= 0.5),
                "chosen_extension_area": float(values[1]),
                "want_parking": bool(values[2] >= 0.5),
                "expected_base_price": float(values[3]),
                "expected_extension_price": float(values[4]),
                "quoted_base_price": float(values[5]),
                "quoted_extension_price": float(values[6]),
                "expected_extension_area": float(values[7]),
            }
        return {"action": values}


    def fallback_action(self, obs_np: np.ndarray | None = None) -> np.ndarray:
        if self.agent_name == "planner":
            return np.array([0.3, 0.0], dtype=np.float32)
        elif self.agent_name == "developer":
            return np.array([3800.0, 4500.0, 0.0, 0.0], dtype=np.float32)
        elif self.agent_name == "resident":
            if self._last_valid_action is not None:
                return self._last_valid_action.copy()

            if obs_np is None:
                return np.zeros(8, dtype=np.float32)

            obs = np.asarray(obs_np, dtype=np.float32)
            last_ext_area = float(obs[12]) if obs.shape[0] > 12 else 0.0
            want_parking_last = 1.0 if (obs.shape[0] > 13 and float(obs[13]) >= 0.5) else 0.0
            last_exp_base = float(obs[15]) if obs.shape[0] > 15 else 0.0
            last_exp_ext = float(obs[16]) if obs.shape[0] > 16 else 0.0
            last_agree = 1.0 if (obs.shape[0] > 21 and float(obs[21]) >= 0.5) else 0.0

            return np.array(
                [
                    last_agree,
                    last_ext_area,
                    want_parking_last,
                    last_exp_base,
                    last_exp_ext,
                    last_exp_base,
                    last_exp_ext,
                    last_ext_area,
                ],
                dtype=np.float32,
            )


    @staticmethod
    def extract_json(text: str):
        try:
            return json.loads(text)
        except Exception:
            pass

        patterns = [
            r"```json\s*([\s\S]*?)\s*```",
            r"```([\s\S]*?)```",
            r"<ANSWER>(.*?)</ANSWER>",
        ]
        for pat in patterns:
            m = re.search(pat, text, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(1).strip())
                except Exception:
                    pass

        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and start < end:
            try:
                return json.loads(text[start:end + 1])
            except Exception:
                pass

        return None
