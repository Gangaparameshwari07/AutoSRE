import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from environment import AutoSREEnv
from models import Action
import uvicorn

app = FastAPI(title="AutoSRE OpenEnv")
env = AutoSREEnv()
PORT = int(os.getenv("PORT", "7860"))


def _serialize_step_result(result):
    if hasattr(result, "_asdict"):
        payload = result._asdict()
    elif isinstance(result, dict):
        payload = result
    else:
        raise TypeError(f"Unsupported step result type: {type(result).__name__}")

    observation = payload["observation"]
    payload["observation"] = observation.model_dump() if hasattr(observation, "model_dump") else observation
    return payload


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
async def reset_endpoint(task_id: str = "task_3_hard"):
    """
    Called by the validator and the agent to start a fresh incident.
    Defaulting to 'hard' because we want to test the best logic.
    """
    obs = env.reset(task_id=task_id)
    return {"observation": obs, "status": "initialized"}


@app.get("/state")
async def state_endpoint():
    """Return the current cluster state as JSON."""
    obs = env.state()
    return {"observation": obs}

@app.post("/step")
async def step_endpoint(action: Action):
    """Run a single environment action and return a JSON-safe payload."""
    try:
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
        "server:app", 
        host="0.0.0.0", 
        port=PORT, 
        reload=False,
        proxy_headers=True,
        forwarded_allow_ips="*"
    )


if __name__ == "__main__":
    main()
