from typing import Any
from models import ServiceStatus, LogEntry

TASKS = {
    "task_1_easy": {
        "id": "task_1_easy",
        "description": "payment-service has crashed. Restart it.",
        "target": "payment-service",
        "initial_state": "crashed",
    },
    "task_2_medium": {
        "id": "task_2_medium",
        "description": "auth-service memory leak. Clear cache and scale up.",
        "target": "auth-service",
        "initial_state": "degraded",
        "metrics_override": {"mem_usage": 95.0},
    },
    "task_3_hard": {
        "id": "task_3_hard",
        "description": "Database overload causing cascading failure.",
        "target": "database",
        "initial_state": "degraded",
        "metrics_override": {"latency_ms": 850.0},
    },
    "task_4_recovery": {
        "id": "task_4_recovery",
        "description": "order-service crashed after bad rollout.",
        "target": "order-service",
        "initial_state": "crashed",
    },
    "task_5_edge_database_crash": {
        "id": "task_5_edge_database_crash",
        "description": "Database crashed under extreme load.",
        "target": "database",
        "initial_state": "crashed",
    },
}

def get_public_task_catalog() -> list[dict[str, Any]]:
    catalog = []
    for task_id in TASKS:
        catalog.append({
            "id": task_id,
            "task_id": task_id,
            "name": task_id,
            "description": TASKS[task_id]["description"],
            "grader": "graders.grade_submission",
            "grader_enabled": True,
            "has_grader": True,
            "score_range": {"min_exclusive": 0.0, "max_exclusive": 1.0},
        })
    return catalog

def apply_task_scenario(env, task_id: str):
    if task_id not in TASKS:
        return
    config = TASKS[task_id]
    target = config["target"]
    status_map = {"crashed": ServiceStatus.CRASHED, "degraded": ServiceStatus.DEGRADED}
    env.services[target].status = status_map.get(config["initial_state"], ServiceStatus.DEGRADED)
    if "metrics_override" in config:
        for metric, value in config["metrics_override"].items():
            setattr(env.services[target], metric, value)
