import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from definitions import TASKS, get_public_task_catalog
from environment import AutoSREEnv
from llm_proxy import proxy_env_present, warm_proxy_once
from models import Action
from scoring import clamp_open_interval
import uvicorn

env = AutoSREEnv()
PORT = int(os.getenv("PORT", "7860"))

@asynccontextmanager
async def lifespan(_: FastAPI):
    if proxy_env_present():
        warm_proxy_once()
    yield

app = FastAPI(title="AutoSRE OpenEnv", lifespan=lifespan)

def _clamp_public_score(score: float) -> float:
    # Forces score strictly between 0 and 1 (e.g., 0.01 to 0.99)
    return clamp_open_interval(float(score))

# --- NEW GRADER ENDPOINTS AS REQUESTED BY META ---

@app.get("/grade/task_1_easy")
async def grade_task_1():
    score = _clamp_public_score(env.state().system_health_score)
    return {"score": score, "reward": score}

@app.get("/grade/task_2_medium")
async def grade_task_2():
    score = _clamp_public_score(env.state().system_health_score)
    return {"score": score, "reward": score}

@app.get("/grade/task_3_hard")
async def grade_task_3():
    score = _clamp_public_score(env.state().system_health_score)
    return {"score": score, "reward": score}

# ------------------------------------------------

def _public_observation(observation):
    if hasattr(observation, "model_copy"):
        return observation.model_copy(
            update={"system_health_score": _clamp_public_score(observation.system_health_score)}
        )
    observation.system_health_score = _clamp_public_score(observation.system_health_score)
    return observation

def _serialize_step_result(result):
    if hasattr(result, "_asdict"):
        payload = result._asdict()
    elif isinstance(result, dict):
        payload = result
    else:
        raise TypeError(f"Unsupported step result type: {type(result).__name__}")

    observation = _public_observation(payload["observation"])
    payload["observation"] = observation.model_dump() if hasattr(observation, "model_dump") else observation
    if "reward" in payload:
        payload["reward"] = _clamp_public_score(payload["reward"])
    return payload

def _resolve_task_id(task_id: str | None, payload: dict[str, Any] | None) -> str:
    body_task_id = None
    if isinstance(payload, dict):
        body_task_id = payload.get("task_id") or payload.get("task") or payload.get("id")
    
    # Map incoming generic IDs to your specific task names
    resolved = body_task_id or task_id or "task_3_hard"
    if resolved == "task_1": resolved = "task_1_easy"
    if resolved == "task_2": resolved = "task_2_medium"
    if resolved == "task_3": resolved = "task_3_hard"

    if resolved not in TASKS:
        raise HTTPException(status_code=400, detail=f"Unknown task_id: {resolved}")
    return resolved

# ... [Keep your _render_dashboard_text, reset_endpoint, tasks_endpoint, etc. same as before] ...

@app.post("/step")
async def step_endpoint(action: Action):
    try:
        if proxy_env_present():
            warm_proxy_once()
        # Ensure the underlying env result is passed through the clamp serializer
        return _serialize_step_result(env.step(action))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

# ... [Keep the rest of your file same] ...