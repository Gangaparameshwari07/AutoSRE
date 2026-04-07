import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from definitions import TASKS
from environment import AutoSREEnv
from llm_proxy import proxy_env_present, warm_proxy_once
from models import Action
import uvicorn

app = FastAPI(title="AutoSRE OpenEnv")
env = AutoSREEnv()
PORT = int(os.getenv("PORT", "7860"))
MIN_PUBLIC_SCORE = 0.01
MAX_PUBLIC_SCORE = 0.99


def _clamp_public_score(score: float) -> float:
    return round(min(MAX_PUBLIC_SCORE, max(MIN_PUBLIC_SCORE, float(score))), 2)


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


def _render_dashboard_text():
    obs = env.state()
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


@app.post("/reset")
async def reset_endpoint(task_id: str = "task_3_hard"):
    if task_id not in TASKS:
        raise HTTPException(status_code=400, detail=f"Unknown task_id: {task_id}")
    if proxy_env_present():
        try:
            warm_proxy_once()
        except Exception as exc:
            print(f"[WARN] LiteLLM proxy warmup failed: {exc}", flush=True)
    obs = _public_observation(env.reset(task_id=task_id))
    return {"observation": obs, "status": "initialized", "available_tasks": list(TASKS)}


@app.get("/state")
async def state_endpoint():
    return {"observation": _public_observation(env.state())}


@app.post("/step")
async def step_endpoint(action: Action):
    try:
        return _serialize_step_result(env.step(action))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/", response_class=HTMLResponse)
async def root_ui():
    obs = env.state()
    dashboard_text = _render_dashboard_text()
    services_html = "".join([
        f"<li><b>{name}:</b> {s.status} (CPU: {s.cpu_usage}%, Memory: {s.mem_usage}%, Latency: {s.latency_ms}ms)</li>"
        for name, s in obs.services.items()
    ])
    return f"""
    <html>
        <head><title>AutoSRE Dashboard</title></head>
        <body style="font-family: sans-serif; padding: 20px;">
            <h1>AutoSRE Control Plane</h1>
            <h3>Current System Health: {obs.system_health_score * 100}%</h3>
            <hr>
            <h4>Live Cluster Status:</h4>
            <ul>{services_html}</ul>
            <h4>Recent Logs:</h4>
            <pre>{chr(10).join([f"[{l.level}] {l.service}: {l.message}" for l in obs.recent_logs])}</pre>
            <h4>Agent View:</h4>
            <pre>{dashboard_text}</pre>
        </body>
    </html>
    """


def main() -> None:
    uvicorn.run(
        "server.app:app",
        host="0.0.0.0",
        port=PORT,
        reload=False,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )
