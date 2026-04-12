import json
import os
import re
from typing import List, Optional

import httpx
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4.1-mini")
HF_TOKEN = os.getenv("HF_TOKEN")
DASHBOARD_URL = os.getenv("DASHBOARD_URL", "http://localhost:7860")
TASK_NAME = os.getenv("TASK_ID", "task_3_hard")
BENCHMARK = os.getenv("BENCHMARK", "autosre")
MAX_STEPS = 10
REQUEST_TIMEOUT = 30.0

if HF_TOKEN is None:
    raise ValueError("HF_TOKEN environment variable is required")

client = OpenAI(
    base_url=API_BASE_URL,
    api_key=HF_TOKEN,
)

# --- Helper Functions ---

def _clamp(value: float) -> float:
    """Ensures scores are strictly between 0 and 1 per Meta rules."""
    try:
        val = float(value)
    except (TypeError, ValueError):
        val = 0.02
    return max(0.02, min(0.98, val))

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

def _extract_service_snapshot(state_text: str, service_name: str) -> Optional[dict]:
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

# --- SRE Logic Functions ---

def _fallback_action(state_text: str) -> tuple[str, str]:
    """Heuristic-based SRE logic used if the LLM fails."""
    service_names = ["api-gateway", "auth-service", "order-service", "payment-service", "database"]
    snapshots = {name: _extract_service_snapshot(state_text, name) for name in service_names}
    
    db = snapshots.get("database")
    if db and (db["cpu"] > 90 or db["latency"] > 500 or "crashed" in db["status"]):
        return "scale_up", "database"

    for name in ["auth-service", "payment-service", "api-gateway"]:
        s = snapshots.get(name)
        if s and "crashed" in s["status"]:
            return "restart_service", name
            
    return "noop", "api-gateway"

def choose_action(state_text: str) -> tuple[str, str]:
    """Attempts LLM inference, falls back to heuristics on error."""
    prompt = f"Analyze state and return JSON {{'action': '...', 'target': '...'}}:\n{state_text}"

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=50,
        )
        decision = _extract_json(response.choices[0].message.content or "")
        return decision.get("action", "noop"), decision.get("target", "api-gateway")
    except Exception:
        return _fallback_action(state_text)

# --- Logging Functions ---

def log_start(task: str, env_name: str, model: str) -> None:
    print(f"[START] task={task} env={env_name} model={model}", flush=True)

def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    e = error if error else "null"
    print(f"[STEP] step={step} action={action} reward={_clamp(reward):.2f} done={str(done).lower()} error={e}", flush=True)

def log_end(success: bool, steps: int, rewards: List[float]) -> None:
    safe_rewards = rewards or [0.02]
    rewards_str = ",".join(f"{_clamp(r):.2f}" for r in safe_rewards)
    print(f"[END] success={str(success).lower()} steps={steps} rewards={rewards_str}", flush=True)

# --- Environment Interaction ---

def reset_environment(task_id: str) -> dict:
    resp = httpx.post(f"{DASHBOARD_URL}/reset", params={"task_id": task_id}, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()

def take_action(action: str, target: str) -> dict:
    resp = httpx.post(f"{DASHBOARD_URL}/step", json={"action": action, "target": target}, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()

def run_agent(task_id: str) -> None:
    rewards: List[float] = []
    steps_taken = 0
    success = False
    
    log_start(task_id, BENCHMARK, MODEL_NAME)

    try:
        reset_environment(task_id)
        for step in range(1, MAX_STEPS + 1):
            steps_taken = step
            
            # 1. Get State
            resp = httpx.get(f"{DASHBOARD_URL}/", timeout=REQUEST_TIMEOUT)
            state_text = resp.text
            
            # 2. Decide and Act
            action, target = choose_action(state_text)
            result = take_action(action, target)
            
            # 3. Parse Result
            reward = _clamp(result.get("reward", 0.01))
            done = bool(result.get("done", False))
            health = _clamp(result.get("observation", {}).get("system_health_score", 0.01))
            
            rewards.append(reward)
            log_step(step, f"{action}({target})", reward, done, None)
            
            if done or health >= 0.98:
                success = True
                break
    except Exception:
        if not rewards:
            rewards = [0.02]
            steps_taken = max(steps_taken, 1)
    finally:
        log_end(success, steps_taken, rewards)

if __name__ == "__main__":
    run_agent(TASK_NAME)
