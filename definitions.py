from typing import Any, Dict
from models import ServiceStatus, LogEntry

# These are the 'Starting Conditions' for each level of the hackathon.
# The environment will use these to break the system before the agent starts.

TASKS = {
    "task_1_easy": {
        "description": "Simple Service Failure: The 'payment-service' has crashed. Restart it to restore service.",
        "target": "payment-service",
        "initial_state": "crashed",
        "grader": "graders.grade_submission",
        "grader_enabled": True,
    },
    "task_2_medium": {
        "description": "Resource Exhaustion: The 'auth-service' is experiencing a memory leak (95% RAM). Clear the cache and scale up to stabilize.",
        "target": "auth-service",
        "initial_state": "degraded",
        "metrics_override": {"mem_usage": 95.0, "latency_ms": 450.0},
        "grader": "graders.grade_submission",
        "grader_enabled": True,
    },
    "task_3_hard": {
        "description": "Cascading Failure: The 'database' is overwhelmed with high latency (>800ms), causing the 'api-gateway' to crash. You MUST fix the Database FIRST.",
        "target": "database",
        "initial_state": "degraded",
        "metrics_override": {"latency_ms": 850.0, "cpu_usage": 98.0},
        "grader": "graders.grade_submission",
        "grader_enabled": True,
    }
}


def get_public_task_catalog() -> list[dict[str, Any]]:
    """
    Return serializable task metadata so hosted validators can discover
    graded tasks without importing local modules.
    """
    catalog = []
    for task_id, config in TASKS.items():
        catalog.append(
            {
                "id": task_id,
                "description": config["description"],
                "grader": config.get("grader"),
                "grader_enabled": bool(config.get("grader_enabled", False)),
                "score_range": {"min_exclusive": 0.0, "max_exclusive": 1.0},
            }
        )
    return catalog

# This helper helps the Environment.reset() function set up the 'Chaos'
def apply_task_scenario(env, task_id: str):
    """Injects the specific failure into our AutoSRE environment."""
    if task_id not in TASKS:
        return
    
    config = TASKS[task_id]
    target = config["target"]
    
    # 1. Apply the primary failure
    service = env.services[target]
    status_map = {"crashed": ServiceStatus.CRASHED, "degraded": ServiceStatus.DEGRADED, "running": ServiceStatus.RUNNING}
    service.status = status_map.get(config["initial_state"], ServiceStatus.DEGRADED)
    
    # 2. If there are specific metric spikes (like 95% RAM), apply them here
    if "metrics_override" in config:
        for metric, value in config["metrics_override"].items():
            setattr(service, metric, value)
            
    # 3. Add a realistic log entry so the agent has a 'clue'
    env.logs.append(LogEntry(
        timestamp="00:01",
        level="CRITICAL" if config["initial_state"] == "crashed" else "WARN",
        service=target,
        message=f"Alert: {target} is {config['initial_state']} - {config['description']}"
    ))
