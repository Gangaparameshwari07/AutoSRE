from typing import Any
from models import ServiceStatus, LogEntry



SCORE_FLOOR = 0.0
SCORE_CEILING = 1.0

TASK_GRADER_PATHS = {
    "task_1_easy": "server.graders:EasyGrader",
    "task_2_medium": "server.graders:MediumGrader",
    "task_3_hard": "server.graders:HardGrader",
}

def _build_task(
    task_id: str,
    description: str,
    target: str,
    initial_state: str,
    metrics_override: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Build task configuration with grader enabled"""
    task = {
        "id": task_id,
        "task_id": task_id,
        "name": task_id,
        "description": description,
        "target": target,
        "initial_state": initial_state,
        "grader": TASK_GRADER_PATHS[task_id],
        "grader_enabled": True,  # CRITICAL: Must be True
        "has_grader": True,  # CRITICAL: Must be True
        "grading": {
            "enabled": True,
            "path": TASK_GRADER_PATHS[task_id],
        },
        "score_range": {
            "min_exclusive": SCORE_FLOOR,
            "max_exclusive": SCORE_CEILING,
        },
        "score_bounds": {
            "min": SCORE_FLOOR,
            "max": SCORE_CEILING,
            "strict": True,
        },
        "validator_hints": {
            "score_must_be_strictly_between_zero_and_one": True,
            "grader_path": TASK_GRADER_PATHS[task_id],
        },
    }
    if metrics_override:
        task["metrics_override"] = metrics_override
    return task

TASKS = {
    "task_1_easy": _build_task(
        task_id="task_1_easy",
        description="Simple Service Failure: The 'payment-service' has crashed. Restart it to restore service.",
        target="payment-service",
        initial_state="crashed",
    ),
    "task_2_medium": _build_task(
        task_id="task_2_medium",
        description="Resource Exhaustion: The 'auth-service' is experiencing a memory leak (95% RAM). Clear the cache and scale up to stabilize.",
        target="auth-service",
        initial_state="degraded",
        metrics_override={"mem_usage": 95.0, "latency_ms": 450.0},
    ),
    "task_3_hard": _build_task(
        task_id="task_3_hard",
        description="Cascading Failure: The 'database' is overwhelmed with high latency (>800ms), causing the 'api-gateway' to crash. You MUST fix the Database FIRST.",
        target="database",
        initial_state="degraded",
        metrics_override={"latency_ms": 850.0, "cpu_usage": 98.0},
    ),
}

def get_public_task_catalog() -> list[dict[str, Any]]:
    """Return task metadata for validators"""
    catalog = []
    for task_id, config in TASKS.items():
        catalog.append({
            "id": config["id"],
            "task_id": config["task_id"],
            "name": config["name"],
            "description": config["description"],
            "grader": config["grader"],
            "grader_enabled": True,  # FORCED to True
            "has_grader": True,  # FORCED to True
            "grading": {
                "enabled": True,
                "path": config["grader"],
            },
            "score_range": {
                "min_exclusive": 0.0,
                "max_exclusive": 1.0,
            },
        })
    return catalog

def apply_task_scenario(env, task_id: str):
    """Inject failure scenario into environment"""
    if task_id not in TASKS:
        return
    
    config = TASKS[task_id]
    target = config["target"]
    
    status_map = {
        "crashed": ServiceStatus.CRASHED,
        "degraded": ServiceStatus.DEGRADED,
        "running": ServiceStatus.RUNNING
    }
    
    env.services[target].status = status_map.get(config["initial_state"], ServiceStatus.DEGRADED)
    
    if "metrics_override" in config:
        for metric, value in config["metrics_override"].items():
            setattr(env.services[target], metric, value)
    
    env.logs.append(LogEntry(
        timestamp="00:01",
        level="CRITICAL" if config["initial_state"] == "crashed" else "WARN",
        service=target,
        message=f"Alert: {target} is {config['initial_state']} - {config['description']}"
    ))
