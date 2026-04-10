from typing import Any
from models import ServiceStatus, LogEntry
import graders

GRADER_FUNCTION = graders.grade_submission

SCORE_FLOOR = 0.0
SCORE_CEILING = 1.0


def _build_task(
    task_id: str,
    description: str,
    target: str,
    initial_state: str,
    metrics_override: dict[str, float] | None = None,
) -> dict[str, Any]:
    task = {
        "id": task_id,
        "task_id": task_id,
        "name": task_id,
        "description": description,
        "target": target,
        "initial_state": initial_state,
        "grader": GRADER_FUNCTION,
        "grader_enabled": True,
        "has_grader": True,
        "grading": {
            "enabled": True,
            "path": "graders.grade_submission",
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
            "grader_path": "graders.grade_submission",
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
    "task_4_recovery": _build_task(
        task_id="task_4_recovery",
        description="Cross-Service Recovery: The 'order-service' has crashed after a bad rollout. Restore it quickly to bring the platform back to full health.",
        target="order-service",
        initial_state="crashed",
    ),
    "task_5_edge_database_crash": _build_task(
        task_id="task_5_edge_database_crash",
        description="Edge-Case Cascade: The 'database' has crashed under extreme load, which knocks the authentication and gateway path offline. Recover the database first to restore the platform.",
        target="database",
        initial_state="crashed",
        metrics_override={"latency_ms": 900.0, "cpu_usage": 99.0},
    ),
}


def get_public_task_catalog() -> list[dict[str, Any]]:
    """Return serializable task metadata so hosted validators can discover graded tasks."""
    catalog = []
    for task_id, config in TASKS.items():
        catalog.append(
            {
                "id": config["id"],
                "task_id": config["task_id"],
                "name": config["name"],
                "description": config["description"],
                "grader": "graders.grade_submission",
                "grader_enabled": bool(config.get("grader_enabled", False)),
                "has_grader": True,
                "grading": dict(config.get("grading", {})),
                "score_range": dict(config.get("score_range", {})),
                "score_bounds": dict(config.get("score_bounds", {})),
                "validator_hints": dict(config.get("validator_hints", {})),
            }
        )
    return catalog


def apply_task_scenario(env, task_id: str):
    """Injects the specific failure into our AutoSRE environment."""
    if task_id not in TASKS:
        return

    config = TASKS[task_id]
    target = config["target"]

    status_map = {"crashed": ServiceStatus.CRASHED, "degraded": ServiceStatus.DEGRADED, "running": ServiceStatus.RUNNING}
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
