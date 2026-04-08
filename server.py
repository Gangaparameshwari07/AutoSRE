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
    return clamp_open_interval(score)


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
    resolved = body_task_id or task_id or "task_3_hard"
    if resolved not in TASKS:
        raise HTTPException(status_code=400, detail=f"Unknown task_id: {resolved}")
    return resolved


def _render_dashboard_text():
    obs = env._get_observation()
    service_lines = [
        f"- {name}: status={service.status} cpu={service.cpu_usage}% mem={service.mem_usage}% latency={service.latency_ms}ms error_rate={service.error_rate}"
        for name, service in obs.services.items()
    ]
    log_lines = [f"[{log.level}] {log.service}: {log.message}" for log in obs.recent_logs]
    return "\n".join([
        "AutoSRE Control Plane",
        f"Task: {obs.task_description}",
        f"System Health: {obs.system_health_score}",
        "Services:",
        *service_lines,
        "Recent Logs:",
        *log_lines,
    ])

# --- HACKATHON MANDATORY ENDPOINTS ---

@app.post("/reset")
async def reset_endpoint(task_id: str | None = None, payload: dict[str, Any] | None = Body(default=None)):
    """
    Called by the validator and the agent to start a fresh incident.
    Supports both query-param and JSON-body task selection for compatibility.
    """
    task_id = _resolve_task_id(task_id, payload)
    if proxy_env_present():
        warm_proxy_once()
    obs = _public_observation(env.reset(task_id=task_id))
    return {
        "observation": obs,
        "status": "initialized",
        "task_id": task_id,
        "available_tasks": list(TASKS),
        "graded_task_count": len([task for task in TASKS.values() if task.get("grader_enabled") and task.get("grader")]),
        "tasks": get_public_task_catalog(),
    }


@app.get("/tasks")
async def tasks_endpoint():
    tasks = get_public_task_catalog()
    return {
        "tasks": tasks,
        "count": len(tasks),
        "graded_task_count": len([task for task in tasks if task.get("has_grader")]),
    }


@app.get("/health")
async def health_endpoint():
    return {"status": "healthy"}


@app.get("/metadata")
async def metadata_endpoint():
    return {
        "name": "AutoSRE",
        "description": "A professional microservices SRE simulation with cascading failures.",
        "task_count": len(TASKS),
        "graded_task_count": len([task for task in TASKS.values() if task.get("grader_enabled") and task.get("grader")]),
    }


@app.get("/schema")
async def schema_endpoint():
    action_schema = Action.model_json_schema() if hasattr(Action, "model_json_schema") else {}
    observation_schema = type(env.state()).model_json_schema() if hasattr(type(env.state()), "model_json_schema") else {}
    return {
        "action": action_schema,
        "observation": observation_schema,
        "state": observation_schema,
    }


@app.get("/state")
async def state_endpoint():
    """Return the current cluster state as JSON."""
    if proxy_env_present():
        warm_proxy_once()
    obs = _public_observation(env.state())
    return {"observation": obs}

@app.post("/step")
async def step_endpoint(action: Action):
    """Run a single environment action and return a JSON-safe payload."""
    try:
        if proxy_env_present():
            warm_proxy_once()
        result = env.step(action)
        
        return _serialize_step_result(result)
        
    except Exception as e:
        print(f"❌ SERVER CRASHED ON STEP: {e}")
        raise HTTPException(status_code=400, detail=str(e))

# --- BOOTCAMP COMPLIANCE: WEB UI ---

@app.get("/", response_class=HTMLResponse)
async def root_ui():
    """
    A simple dashboard so you (and the judges) can see the cluster status.
    This fulfills the 'Enable Web Interface' suggestion from the bootcamp.
    """
    if proxy_env_present():
        warm_proxy_once()
    obs = env._get_observation()
    dashboard_text = _render_dashboard_text()
    services_html = "".join([
        f"<li><b>{name}:</b> {s.status} (CPU: {s.cpu_usage}%, Memory: {s.mem_usage}%, Latency: {s.latency_ms}ms)</li>"
        for name, s in obs.services.items()
    ])
    
    return f"""
    <html>
        <head><title>AutoSRE Dashboard</title></head>
        <body style="font-family: sans-serif; padding: 20px;">
            <h1>🚀 AutoSRE Control Plane</h1>
            <h3>Current System Health: {obs.system_health_score * 100}%</h3>
            <hr>
            <h4>Live Cluster Status:</h4>
            <ul>{services_html}</ul>
            <h4>Recent Logs:</h4>
            <pre>{chr(10).join([f"[{l.level}] {l.service}: {l.message}" for l in obs.recent_logs])}</pre>
            <h4>Agent View:</h4>
            <pre>{dashboard_text}</pre>
            <p><i>Use /reset and /step API endpoints to interact.</i></p>
        </body>
    </html>
    """

def main() -> None:
    uvicorn.run(
        app,
        host="0.0.0.0", 
        port=PORT, 
        reload=False,
        proxy_headers=True,
        forwarded_allow_ips="*"
    )


if __name__ == "__main__":
    main()
