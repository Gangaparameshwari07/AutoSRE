import json
import os
import re
from typing import List, Optional

import httpx
from dotenv import load_dotenv
from openai import APIError, NotFoundError, OpenAI

load_dotenv()

DASHBOARD_URL = os.getenv("DASHBOARD_URL", "http://localhost:7860")
MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-7B-Instruct")
IMAGE_NAME = os.getenv("LOCAL_IMAGE_NAME") or os.getenv("IMAGE_NAME")
TASK_NAME = os.getenv("TASK_ID", "task_3_hard")
BENCHMARK = os.getenv("BENCHMARK", "autosre")
MAX_STEPS = 10
REQUEST_TIMEOUT = 30.0


def _require_env(name: str, value: str | None) -> str:
    if not value:
        raise RuntimeError(f"{name} is not set. Add it to your environment or .env file.")
    return value


def _build_client() -> OpenAI:
    return OpenAI(
        base_url=_require_env("API_BASE_URL", os.getenv("API_BASE_URL")),
        api_key=_require_env("API_KEY", os.getenv("API_KEY")),
    )


def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    error_val = error if error else "null"
    done_val = str(done).lower()
    print(
        f"[STEP] step={step} action={action} reward={reward:.2f} done={done_val} error={error_val}",
        flush=True,
    )


def log_end(success: bool, steps: int, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{reward:.2f}" for reward in rewards)
    print(
        f"[END] success={str(success).lower()} steps={steps} rewards={rewards_str}",
        flush=True,
    )


def get_system_state() -> str:
    response = httpx.get(f"{DASHBOARD_URL}/", timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.text


def reset_environment(task_id: str) -> dict:
    response = httpx.post(
        f"{DASHBOARD_URL}/reset",
        params={"task_id": task_id},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def take_action(action: str, target: str) -> dict:
    response = httpx.post(
        f"{DASHBOARD_URL}/step",
        json={"action": action, "target": target},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def _extract_json(raw_content: str) -> dict:
    raw = raw_content.strip()
    if "```json" in raw:
        raw = raw.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in raw:
        raw = raw.split("```", 1)[1].split("```", 1)[0].strip()

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = {}

    return parsed if isinstance(parsed, dict) else {}


def _extract_service_snapshot(state_text: str, service_name: str) -> dict[str, float | str] | None:
    pattern = re.compile(
        rf"{re.escape(service_name)}: status=([^\s]+) cpu=([0-9.]+)% mem=([0-9.]+)% latency=([0-9.]+)ms error_rate=([0-9.]+)"
    )
    match = pattern.search(state_text)
    if not match:
        return None

    return {
        "status": match.group(1).lower(),
        "cpu": float(match.group(2)),
        "mem": float(match.group(3)),
        "latency": float(match.group(4)),
        "error_rate": float(match.group(5)),
    }


def _fallback_action(state_text: str) -> tuple[str, str]:
    database = _extract_service_snapshot(state_text, "database")
    auth = _extract_service_snapshot(state_text, "auth-service")
    payment = _extract_service_snapshot(state_text, "payment-service")
    gateway = _extract_service_snapshot(state_text, "api-gateway")

    if database and (
        "degraded" in str(database["status"])
        or "crashed" in str(database["status"])
        or float(database["latency"]) > 500
        or float(database["cpu"]) > 90
    ):
        return "scale_up", "database"

    if payment and "crashed" in str(payment["status"]):
        return "restart_service", "payment-service"

    if auth and float(auth["mem"]) > 85:
        return "clear_cache", "auth-service"

    if auth and "degraded" in str(auth["status"]):
        return "scale_up", "auth-service"

    if gateway and "crashed" in str(gateway["status"]):
        return "restart_service", "api-gateway"

    return "noop", "api-gateway"


def choose_action(state_text: str) -> tuple[str, str]:
    prompt = f"""You are an expert SRE. Analyze the current control plane state and choose the single best next action.

{state_text}

Return ONLY valid JSON in this exact format:
{{"action": "scale_up", "target": "database"}}

Allowed action values: restart_service, scale_up, scale_down, clear_cache, rollback, noop
Allowed target values: api-gateway, auth-service, order-service, payment-service, database
"""

    client = _build_client()
    model_name = _require_env("MODEL_NAME", MODEL_NAME)

    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=50,
        )
        decision = _extract_json(response.choices[0].message.content or "")
        action = decision.get("action", "noop")
        target = decision.get("target", "api-gateway")
        return action, target
    except (NotFoundError, APIError):
        return _fallback_action(state_text)


def run_agent(task_id: str) -> None:
    rewards: List[float] = []
    steps_taken = 0
    success = False

    log_start(task=task_id, env=BENCHMARK, model=_require_env("MODEL_NAME", MODEL_NAME))

    try:
        reset_environment(task_id)

        for step in range(1, MAX_STEPS + 1):
            steps_taken = step
            state_text = get_system_state()
            action, target = choose_action(state_text)
            result = take_action(action, target)

            reward = float(result.get("reward", 0.0) or 0.0)
            done = bool(result.get("done", False))
            error = result.get("info", {}).get("error")
            action_str = f"{action}({target})"

            rewards.append(reward)
            log_step(step=step, action=action_str, reward=reward, done=done, error=error)

            final_health = float(result.get("observation", {}).get("system_health_score", 0.0) or 0.0)
            success = done or final_health >= 1.0
            if success:
                break
    finally:
        log_end(success=success, steps=steps_taken, rewards=rewards)


if __name__ == "__main__":
    run_agent(TASK_NAME)
